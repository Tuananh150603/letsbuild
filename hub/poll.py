#!/usr/bin/env python3
"""Poll the LetsBuild hub for new messages (manager + worker cron).

Reads every room, prints only messages newer than the saved watermark,
then advances the watermark. Prints NOTHING when there is nothing new,
so a cron running this stays silent until someone actually wrote.

Usage: python3 poll.py [--config ~/.config/letsbuild-hub]
       [--state ~/.hub-last-seen.json]

Config file (KEY=value): HUB_URL, HUB_TOKEN.
HUB_PROXY is derived fresh from $HTTPS_PROXY on every run (the egress
password rotates; a saved proxy value goes stale within minutes).
"""

import argparse
import json
import os
import sys
import urllib.request

DEFAULT_CONFIG = os.path.expanduser("~/.config/letsbuild-hub")
DEFAULT_STATE = os.path.expanduser("~/.hub-last-seen.json")


def load_config(path):
    cfg = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def get(path, cfg, proxy):
    url = cfg["HUB_URL"].rstrip("/") + path
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer " + cfg["HUB_TOKEN"])
    req.add_header("User-Agent", "letsbuild-hub-poll")
    opener = urllib.request.build_opener()
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    with opener.open(req, timeout=20) as resp:
        return json.load(resp)


def main():
    ap = argparse.ArgumentParser(description="Poll LetsBuild hub for new messages")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--state", default=DEFAULT_STATE)
    args = ap.parse_args()

    cfg = load_config(args.config)
    if not cfg.get("HUB_URL") or not cfg.get("HUB_TOKEN"):
        print("poll: HUB_URL/HUB_TOKEN missing in config", file=sys.stderr)
        return 2
    proxy = cfg.get("HUB_PROXY")
    if not proxy and os.environ.get("HTTPS_PROXY"):
        proxy = os.environ["HTTPS_PROXY"].rsplit(":", 1)[0] + ":3130"

    state = {}
    if os.path.exists(args.state):
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)

    try:
        rooms = get("/rooms", cfg, proxy).get("rooms", [])
    except Exception as e:
        print(f"poll: cannot reach hub: {e}", file=sys.stderr)
        return 1

    new = []
    for room in rooms:
        since = int(state.get(room, 0))
        try:
            data = get(f"/rooms/{room}/messages?since={since}&limit=200",
                       cfg, proxy)
        except Exception as e:
            print(f"poll: room {room}: {e}", file=sys.stderr)
            continue
        for m in data.get("messages", []):
            new.append(m)
            state[room] = max(state.get(room, 0), int(m["id"]))

    if not new:
        return 0
    # Advance the watermark only after a successful read.
    tmp = args.state + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, args.state)
    new.sort(key=lambda m: int(m["id"]))
    for m in new:
        print(f"[{m['room']}] {m['from']} ({m['ts']}): {m['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
