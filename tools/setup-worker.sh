#!/usr/bin/env bash
# LetsBuild worker toolkit — one-command setup (DRAFT, manager to test on a clean dir first).
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
# transformers pinned: 5.x breaks kokoro imports. kokoro pulls torch; on a CPU-only
# machine this is the large download (~2 GB) — that is expected, not an error.
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
"$DIR/venv-vectcut/bin/python" -c "import flask, pyJianYingDraft; print('draft imports OK')"

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
