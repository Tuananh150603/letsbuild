#!/usr/bin/env python3
"""Manager CLI for the tier-3 Muse-team board (file-based, stdlib only).

Root = parent of tools/ dir, so the whole letsbuild folder can be copied to
shared Drive/Git and the script keeps working.

Usage:
  board.py new --title "..." --type research --channel psychology
  board.py list
  board.py approve T-001
  board.py rework T-001 --note "what to fix"

board.py also appends every approve/rework outcome to
board/worker-log.md (date, task, worker, outcome) so the manager can
track each worker's rework rate = the training signal.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "board"
TEMPLATE = ROOT / "tasks" / "task-template.md"
STATES = ("queue", "doing", "done", "archive")
STALE_HOURS = 24
MAX_REWORKS = 2


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def read_claim_worker(task_id):
    claim = BOARD / "doing" / f"{task_id}.claim.json"
    if not claim.exists():
        return "unknown"
    try:
        return json.loads(claim.read_text(encoding="utf-8")).get(
            "worker", "unknown")
    except (json.JSONDecodeError, OSError):
        return "unknown"


def log_outcome(task_id, worker, outcome):
    log = BOARD / "worker-log.md"
    if not log.exists():
        log.write_text("| date | task | worker | outcome |\n|---|---|---|---|\n",
                       encoding="utf-8")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"| {date} | {task_id} | {worker} | {outcome} |\n")


def find_task(task_id):
    """Return (state, path) for a task file, or (None, None)."""
    for state in STATES:
        # doing/ holds claim files, not task files
        if state == "doing":
            continue
        p = BOARD / state / f"{task_id}.md"
        if p.exists():
            return state, p
    return None, None


def next_id():
    nums = []
    for state in STATES:
        if state == "doing":
            continue
        for p in (BOARD / state).glob("T-*.md"):
            m = re.match(r"T-(\d+)\.md$", p.name)
            if m:
                nums.append(int(m.group(1)))
    return f"T-{max(nums, default=0) + 1:03d}"


def cmd_new(args):
    if not TEMPLATE.exists():
        fail(f"template not found: {TEMPLATE}")
    text = TEMPLATE.read_text(encoding="utf-8")
    task_id = next_id()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = (text.replace("{{ID}}", task_id)
            .replace("{{TITLE}}", args.title)
            .replace("{{TYPE}}", args.type)
            .replace("{{CHANNEL}}", args.channel)
            .replace("{{DATE}}", today))
    dest = BOARD / "queue" / f"{task_id}.md"
    dest.write_text(text, encoding="utf-8")
    print(f"created {task_id} -> board/queue/{task_id}.md")
    print("Next: fill in spec + acceptance criteria in the task file.")


def parse_claims():
    """Return {task_id: claim dict} from board/doing/*.claim.json."""
    claims = {}
    for p in sorted((BOARD / "doing").glob("*.claim.json")):
        try:
            claims[p.name.replace(".claim.json", "")] = json.loads(
                p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            claims[p.name.replace(".claim.json", "")] = {"_broken": True}
    return claims


def cmd_list(_args):
    claims = parse_claims()
    now = datetime.now(timezone.utc)
    for state in ("queue", "done", "archive"):
        files = sorted((BOARD / state).glob("T-*.md"))
        print(f"{state}: {len(files)}")
        for p in files:
            title = ""
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith("- **Tiêu đề:**"):
                    title = line.split(":**", 1)[1].strip()
                    break
            print(f"  {p.stem}  {title}")
    print(f"doing (claims): {len(claims)}")
    for task_id, claim in claims.items():
        stale = ""
        try:
            claimed = datetime.fromisoformat(
                claim["claimed_at"].replace("Z", "+00:00"))
            hours = (now - claimed).total_seconds() / 3600
            if hours > STALE_HOURS:
                stale = f"  STALE ({hours:.0f}h)"
        except (KeyError, ValueError):
            stale = "  (unparseable claim)"
        worker = claim.get("worker", "?")
        print(f"  {task_id}  worker={worker}{stale}")


def cmd_approve(args):
    state, path = find_task(args.task_id)
    if state != "done":
        fail(f"{args.task_id} is not in done/ (found: {state})")
    dest = BOARD / "archive" / path.name
    path.rename(dest)
    worker = read_claim_worker(args.task_id)
    log_outcome(args.task_id, worker, "approved")
    claim = BOARD / "doing" / f"{args.task_id}.claim.json"
    if claim.exists():
        claim.unlink()
    print(f"approved {args.task_id} -> board/archive/")


def cmd_rework(args):
    state, path = find_task(args.task_id)
    if state != "done":
        fail(f"{args.task_id} is not in done/ (found: {state})")
    text = path.read_text(encoding="utf-8")
    prev_reworks = text.count("QA rework:")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    note = f"\n- [{stamp}] QA rework: {args.note}\n"
    if "## Ghi chú QA" in text:
        text = text.replace("## Ghi chú QA (quản lý điền)",
                            "## Ghi chú QA (quản lý điền)" + note, 1)
    else:
        text += "\n## Ghi chú QA\n" + note
    path.write_text(text, encoding="utf-8")
    dest = BOARD / "queue" / path.name
    path.rename(dest)
    worker = read_claim_worker(args.task_id)
    log_outcome(args.task_id, worker, "rework")
    claim = BOARD / "doing" / f"{args.task_id}.claim.json"
    if claim.exists():
        claim.unlink()
    print(f"rework {args.task_id} -> board/queue/ (claim cleared)")
    if prev_reworks >= MAX_REWORKS:
        print(f"WARNING: {args.task_id} already reworked {prev_reworks} "
              f"times (this is #{prev_reworks + 1}) — consider taking "
              f"over or escalating to Han.")


def main():
    parser = argparse.ArgumentParser(description="Tier-3 board manager CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="create a task in queue/")
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--type", required=True)
    p_new.add_argument("--channel", required=True)
    p_new.set_defaults(fn=cmd_new)

    p_list = sub.add_parser("list", help="show board state")
    p_list.set_defaults(fn=cmd_list)

    p_ap = sub.add_parser("approve", help="move done/ task to archive/")
    p_ap.add_argument("task_id")
    p_ap.set_defaults(fn=cmd_approve)

    p_rw = sub.add_parser("rework", help="return done/ task to queue/")
    p_rw.add_argument("task_id")
    p_rw.add_argument("--note", required=True)
    p_rw.set_defaults(fn=cmd_rework)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
