#!/usr/bin/env bash
# LetsBuild worker toolkit — one-command setup (tested end-to-end 2026-11-06
# on a clean dir; torch is fetched with curl because pip stalls on the big
# wheel behind some proxies — see section A).
#
# What it installs, on the worker's own machine (nothing is hosted on the manager):
#   A. Kokoro voice: venv + kokoro 0.9.4, transformers PINNED to 4.49.0 (5.x breaks kokoro),
#      voice am_michael only, speed 1.2 (long) / 1.21 (short), voice loudnormed to
#      -14 LUFS / TP -1 dB before it goes into any draft.
#   B. VectCutAPI draft server: clone sun-guannan/VectCutAPI, own venv, requirements.txt.
#   C. ffmpeg + a self-test that must print OK before the worker takes voice/draft tasks.
#
# Usage:  bash tools/setup-worker.sh [install-dir]
#   Default install dir: $HOME/letsbuild-worker
#   Re-running is safe: existing venvs / clone are reused, not wiped.
#   No credentials, API keys or accounts are created or copied by this script.
#   Worker machines differ (Python version, disk, network) — on failure, send the
#   full log back to the manager; do not hand-edit the script on your own.
set -euo pipefail

DIR="${1:-$HOME/letsbuild-worker}"
mkdir -p "$DIR"
cd "$DIR"
echo "LetsBuild worker setup -> $DIR"

# --- 0. Pre-flight -----------------------------------------------------------
command -v python3 >/dev/null || { echo "FAIL: python3 not found"; exit 1; }
command -v git >/dev/null || { echo "FAIL: git not found"; exit 1; }
command -v ffmpeg >/dev/null || { echo "FAIL: ffmpeg not found (install it first)"; exit 1; }
python3 -c "import sys; assert sys.version_info >= (3, 10), sys.version" \
  || { echo "FAIL: need Python 3.10+"; exit 1; }
echo "preflight OK: $(python3 --version), $(ffmpeg -version | head -1)"

# --- A. Kokoro voice ---------------------------------------------------------
if [ ! -x "$DIR/venv-kokoro/bin/python" ]; then
  python3 -m venv "$DIR/venv-kokoro"
fi
"$DIR/venv-kokoro/bin/pip" install -q --upgrade pip
# transformers pinned: 5.x breaks kokoro imports.
# Torch is the big download, and pip's own downloader stalls on very large
# wheels behind some proxies (observed on this VM: the 539 MB PyPI torch
# wheel stuck at 199 MB, 12 resumes, 0 bytes progress), while curl with
# resume (curl -C -) gets through the same proxy fine. Workers are CPU-only
# (the manager's own venv runs torch +cpu), so prefer the CPU wheel from the
# PyTorch CPU index: one ~190 MB file and NO nvidia-* deps (the PyPI CUDA
# wheel pulls ~1.5 GB of nvidia-* packages through pip). Download the wheel
# with curl first, install it from the local file, then pip-install the rest
# (torch already satisfied, so pip will not re-download it).
# Fallbacks, in order: PyPI CUDA wheel via curl, then plain `pip install
# torch` (works on a normal home network). If curl is missing, skip straight
# to the pip fallback. The wheel URL is picked for THIS interpreter/platform
# (cp tag + manylinux + arch) from the upstream index, never hardcoded.
mkdir -p "$DIR/wheels"
cat > "$DIR/select-torch-wheel.py" <<'PYEOF'
"""Print the download URL of the torch wheel for this interpreter.
Usage: select-torch-wheel.py [cpu|pypi]  (default cpu)
cpu  -> latest +cpu wheel from the PyTorch CPU simple index.
pypi -> latest manylinux wheel from the PyPI JSON API.
Prints an empty line when nothing matches (caller falls back)."""
import json, platform, re, sys, urllib.request

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "letsbuild-setup/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "cpu"
    maj, minor = sys.version_info[:2]
    cptag = "cp%d%d-cp%d%d" % (maj, minor, maj, minor)
    machine = platform.machine()
    cands = []
    if mode == "cpu":
        html = fetch("https://download.pytorch.org/whl/cpu/torch/").decode("utf-8", "replace")
        for href in re.findall(r'href="([^"]+)"', html):
            href = href.split("#")[0]
            if ".whl" not in href:
                continue
            fn = href.split("/")[-1].replace("%2B", "+")
            m = re.match(r"torch-(\d+)\.(\d+)\.(\d+)\+cpu", fn)
            if (m and cptag in fn and "manylinux" in fn
                    and fn.endswith(machine + ".whl")):
                cands.append((tuple(int(x) for x in m.groups()), href))
    else:
        data = json.loads(fetch("https://pypi.org/pypi/torch/json"))
        for u in data["urls"]:
            fn = u["filename"]
            if (u["packagetype"] == "bdist_wheel" and cptag in fn
                    and "manylinux" in fn and fn.endswith(machine + ".whl")):
                m = re.search(r"manylinux_(\d+)_(\d+)", fn)
                mltag = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
                cands.append((mltag, u["url"]))
    cands.sort()
    print(cands[-1][1] if cands else "")

try:
    main()
except Exception as e:  # noqa: BLE001 - no match / no network -> empty, caller falls back
    print("WARN: wheel select failed: %s" % e, file=sys.stderr)
    print("")
PYEOF

TORCH_WHL=""
if command -v curl >/dev/null 2>&1; then
  for MODE in cpu pypi; do
    if [ -n "$TORCH_WHL" ]; then break; fi
    TORCH_URL="$(python3 "$DIR/select-torch-wheel.py" "$MODE" 2>/dev/null)" || TORCH_URL=""
    if [ -z "$TORCH_URL" ]; then
      echo "WARN: no torch wheel URL from $MODE index"
      continue
    fi
    echo "torch wheel ($MODE): $TORCH_URL"
    # Keep the ORIGINAL wheel filename: pip rejects a renamed wheel file
    # ("Invalid wheel filename (wrong number of parts)").
    FN="$(basename "${TORCH_URL%%\#*}")"
    FN="${FN//%2B/+}"
    OUT="$DIR/wheels/$FN"
    if curl -C - -L --retry 3 --retry-all-errors --connect-timeout 30 \
        -o "$OUT" "$TORCH_URL"; then
      if python3 -c "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print('wheel zip OK,', len(z.namelist()), 'entries')" "$OUT" 2>/dev/null; then
        TORCH_WHL="$OUT"
      else
        echo "WARN: downloaded file is not a valid wheel, discarding"
        rm -f "$OUT"
      fi
    else
      echo "WARN: curl download of torch wheel ($MODE) failed"
      rm -f "$OUT"
    fi
  done
else
  echo "WARN: curl not found, falling back to pip for torch"
fi

if [ -n "$TORCH_WHL" ]; then
  echo "installing torch from local wheel: $TORCH_WHL"
  "$DIR/venv-kokoro/bin/pip" install -q "$TORCH_WHL" \
    || { echo "FAIL: pip install of local torch wheel failed"; exit 1; }
else
  echo "installing torch via pip (no local wheel)"
  "$DIR/venv-kokoro/bin/pip" install -q torch \
    || { echo "FAIL: could not install torch (curl + pip both failed)"; exit 1; }
fi
"$DIR/venv-kokoro/bin/pip" install -q "kokoro==0.9.4" "transformers==4.49.0" soundfile numpy
"$DIR/venv-kokoro/bin/python" -c "import kokoro, transformers; assert transformers.__version__ == '4.49.0', transformers.__version__; print('kokoro OK, transformers', transformers.__version__)"

# --- B. VectCutAPI draft server ----------------------------------------------
if [ ! -d "$DIR/VectCutAPI/.git" ]; then
  git clone https://github.com/sun-guannan/VectCutAPI.git "$DIR/VectCutAPI"
fi
if [ ! -x "$DIR/venv-vectcut/bin/python" ]; then
  python3 -m venv "$DIR/venv-vectcut"
fi
"$DIR/venv-vectcut/bin/pip" install -q --upgrade pip
"$DIR/venv-vectcut/bin/pip" install -q -r "$DIR/VectCutAPI/requirements.txt"
test -f "$DIR/VectCutAPI/capcut_server.py" || { echo "FAIL: capcut_server.py missing"; exit 1; }
echo "vectcut OK: $DIR/VectCutAPI/capcut_server.py present"

# --- C. Self-test (must pass before taking voice/draft tasks) ----------------
cat > "$DIR/selftest-voice.py" <<'PYEOF'
import sys, numpy as np, soundfile as sf
from kokoro import KPipeline
pipeline = KPipeline(lang_code='a')
chunks = [audio for _g, _p, audio in pipeline("LetsBuild toolkit test.", voice='am_michael', speed=1.2)]
x = np.concatenate(chunks)
sf.write(sys.argv[1], x, 24000)
print(f"voice OK: {len(x)/24000:.2f}s")
PYEOF
"$DIR/venv-kokoro/bin/python" "$DIR/selftest-voice.py" "$DIR/selftest-voice.wav"
test -s "$DIR/selftest-voice.wav" || { echo "FAIL: voice test produced no file"; exit 1; }
# NOTE: pyJianYingDraft is NOT a PyPI package and is NOT in
# requirements.txt — it is vendored inside the VectCutAPI repo
# (VectCutAPI/pyJianYingDraft/). capcut_server.py imports it, which only
# works with the repo dir on sys.path — exactly how the server is launched
# (CWD = repo dir). So the import check must run from the repo dir too.
(cd "$DIR/VectCutAPI" && "$DIR/venv-vectcut/bin/python" -c "import flask, pyJianYingDraft; print('draft imports OK')") \
  || { echo "FAIL: draft imports failed (flask/pyJianYingDraft)"; exit 1; }

cat > "$DIR/config.txt" <<EOF
# LetsBuild worker config (filled by setup-worker.sh)
voice=am_michael
speed_long=1.2
speed_short=1.21
loudnorm=-14 LUFS, true-peak -1 dB (before draft, volume 1.0 in CapCut)
style=flat mid-century modern, palette navy #0F2A43 / cream #F5EEDD / gold #E3A008 / red #C0392B / slate #5A6C7D
EOF

echo "ALL OK — report this to the manager with the self-test output, then wait for a task."
echo "voice venv: $DIR/venv-kokoro | draft venv: $DIR/venv-vectcut | server: $DIR/VectCutAPI/capcut_server.py"
