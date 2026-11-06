#!/usr/bin/env python3
"""LetsBuild Hub — message bus for manager <-> workers (chat only).

A tiny stdlib-only HTTP server. No dependencies, so it runs on any
worker/host machine with Python 3.10+.

What it is: a chat room server. Manager and workers exchange direct
messages here (questions, answers, quick coordination) — near
real-time, polled. It does NOT replace the task board: task
assignment, claims and submissions still go through the git repo
(board/ + protocol.md). Hub = talking, board = working.

Transport: Tailscale tailnet (traffic is WireGuard-encrypted, so plain
HTTP on the tailnet is fine). The server must run on a machine that
accepts connections (Han's PC or an always-on worker machine) — the
manager VM is client-only and cannot host it.

Auth: one bearer token per participant. The server maps token -> name
from tokens.json in the data dir; the `from` field is derived from the
token, never self-asserted. Tokens are created with:
    python3 server.py add-token <name> [--data-dir DIR]
Give each token to its owner privately (1:1 chat). NEVER commit
tokens.json or messages.jsonl to the repo — they live only on the
host machine.

Usage:
    python3 server.py [--host 0.0.0.0] [--port 8899] [--data-dir ./hub-data]

Endpoints (all JSON; all except /health and / need Authorization: Bearer <token>):
    GET  /health                          -> {"ok": true}
    GET  /                                -> read-only viewer (HTML, no auth:
                                              host-only page so Han can watch
                                              the team chat; auto-refreshes)
    GET  /rooms                           -> {"rooms": [...]}
    POST /rooms/<room>/messages           {"text": "..."} -> the message
    GET  /rooms/<room>/messages?since=<id>&limit=<n>
    POST /admin/tokens                    {"name": "..."} -> {"name", "token"}
    GET  /admin/tokens                    -> {"names": [...]} (names only)

The two /admin endpoints take the ADMIN token (not a participant
token). The admin token lets the manager mint a token for ANY Muse
remotely — no hardcoded participant list, no host access needed to
onboard someone new. Minting is idempotent: minting an existing name
returns its current token.

Message: {"id": int, "room": str, "from": str, "ts": ISO8601 UTC, "text": str}
IDs increment globally, so clients poll with since=<last seen id>.
"""

import argparse
import json
import os
import re
import secrets
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOM_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_TEXT = 5000
DEFAULT_LIMIT = 50


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Store:
    """Append-only JSONL store. Thread-safe; fsyncs every write."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.tokens_path = os.path.join(data_dir, "tokens.json")
        self.admin_path = os.path.join(data_dir, "admin-token.txt")
        self.messages_path = os.path.join(data_dir, "messages.jsonl")
        self.lock = threading.Lock()
        self.next_id = 1
        self._load()

    def get_admin_token(self):
        """Admin token: created once, kept in the data dir. The host
        operator gives it to the manager privately (one time). The
        manager uses it to mint participant tokens remotely, so ANY
        Muse can be onboarded without touching the host machine."""
        if os.path.exists(self.admin_path):
            with open(self.admin_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        with self.lock:
            if os.path.exists(self.admin_path):
                with open(self.admin_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            token = secrets.token_urlsafe(32)
            tmp = self.admin_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(token + "\n")
            os.replace(tmp, self.admin_path)
            return token

    def _load(self):
        if os.path.exists(self.messages_path):
            with open(self.messages_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        self.next_id = max(self.next_id, int(msg["id"]) + 1)
                    except (ValueError, KeyError):
                        continue

    def load_tokens(self):
        if not os.path.exists(self.tokens_path):
            return {}
        with open(self.tokens_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def add_token(self, name):
        with self.lock:
            tokens = self.load_tokens()
            if name in tokens:
                return tokens[name]
            token = secrets.token_urlsafe(32)
            tokens[name] = token
            tmp = self.tokens_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2)
            os.replace(tmp, self.tokens_path)
            return token

    def append(self, room, sender, text):
        with self.lock:
            msg = {
                "id": self.next_id,
                "room": room,
                "from": sender,
                "ts": utcnow(),
                "text": text,
            }
            self.next_id += 1
            with open(self.messages_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            return msg

    def read(self, room, since=0, limit=DEFAULT_LIMIT):
        out = []
        if not os.path.exists(self.messages_path):
            return out
        with open(self.messages_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("room") == room and int(msg["id"]) > since:
                    out.append(msg)
                    if len(out) >= limit:
                        break
        return out

    def rooms(self):
        seen = set()
        if not os.path.exists(self.messages_path):
            return []
        with open(self.messages_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                seen.add(msg.get("room"))
        return sorted(r for r in seen if r)

    def read_all(self, limit_per_room=200):
        """All messages grouped by room (for the viewer page)."""
        out = {}
        if not os.path.exists(self.messages_path):
            return out
        with open(self.messages_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                room = msg.get("room")
                if not room:
                    continue
                out.setdefault(room, []).append(msg)
        return {r: msgs[-limit_per_room:] for r, msgs in sorted(out.items())}


class Handler(BaseHTTPRequestHandler):
    store = None  # set in main()
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, html_str):
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _viewer(self):
        """Read-only chat viewer (no auth): the host watches the team
        talk. Rendered server-side from messages.jsonl, so no token
        is needed. Auto-refreshes every 15 s."""
        import html as html_mod

        grouped = self.store.read_all()
        parts = [
            "<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
            "<meta http-equiv=\"refresh\" content=\"15\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>LetsBuild Hub — xem chat</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:760px;"
            "margin:0 auto;padding:16px;color:#1a1a1a;background:#fafafa}"
            "h1{font-size:20px}h2{font-size:16px;margin-top:28px;"
            "border-bottom:1px solid #ddd;padding-bottom:4px}"
            ".msg{margin:8px 0}.ts{color:#888;font-size:12px}"
            ".from{font-weight:700}.note{color:#666;font-size:13px}"
            "</style></head><body>",
            "<h1>LetsBuild Hub — xem chat</h1>",
            "<p class=\"note\">Chỉ xem (không gửi được từ đây). Tự làm mới "
            "mỗi 15 giây. Chat vẫn đi qua hub, task vẫn qua board.</p>",
        ]
        if not grouped:
            parts.append("<p>Chưa có tin nhắn nào.</p>")
        for room, msgs in grouped.items():
            parts.append(f"<h2>#{html_mod.escape(room)}</h2>")
            for m in msgs:
                ts = html_mod.escape(str(m.get("ts", "")))
                who = html_mod.escape(str(m.get("from", "?")))
                text = html_mod.escape(str(m.get("text", ""))).replace("\n", "<br>")
                parts.append(
                    f"<div class=\"msg\"><span class=\"ts\">{ts}</span> "
                    f"<span class=\"from\">{who}</span>: {text}</div>"
                )
        parts.append("</body></html>")
        return self._send_html(200, "".join(parts))

    def _auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth[len("Bearer "):].strip()
        if not token:
            return None
        tokens = self.store.load_tokens()
        for name, tok in tokens.items():
            if secrets.compare_digest(tok, token):
                return name
        return None

    def _admin_auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        token = auth[len("Bearer "):].strip()
        return bool(token) and secrets.compare_digest(
            token, self.store.get_admin_token()
        )

    def _room(self):
        # path: /rooms/<room> or /rooms/<room>/messages
        parts = [p for p in self.path.split("?", 1)[0].split("/") if p]
        if len(parts) < 2 or parts[0] != "rooms":
            return None
        room = parts[1]
        if not ROOM_RE.match(room):
            return None
        return room

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._send(200, {"ok": True})
        if path == "/":
            return self._viewer()
        if path == "/admin/tokens":
            if not self._admin_auth():
                return self._send(401, {"error": "unauthorized"})
            names = sorted(self.store.load_tokens().keys())
            return self._send(200, {"names": names})
        who = self._auth()
        if who is None:
            return self._send(401, {"error": "unauthorized"})
        if path == "/rooms":
            return self._send(200, {"rooms": self.store.rooms()})
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "messages":
            room = self._room()
            if room is None:
                return self._send(400, {"error": "bad room"})
            qs = self._query()
            try:
                since = int(qs.get("since", ["0"])[0])
                limit = int(qs.get("limit", [str(DEFAULT_LIMIT)])[0])
            except ValueError:
                return self._send(400, {"error": "bad since/limit"})
            limit = max(1, min(limit, 200))
            msgs = self.store.read(room, since=since, limit=limit)
            return self._send(200, {"room": room, "messages": msgs})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in self.path.split("?", 1)[0].split("/") if p]
        if parts == ["admin", "tokens"]:
            if not self._admin_auth():
                return self._send(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"error": "bad json"})
            name = payload.get("name", "")
            if not isinstance(name, str) or not re.match(
                r"^[a-z0-9][a-z0-9_-]{0,63}$", name
            ):
                return self._send(400, {"error": "bad name"})
            token = self.store.add_token(name)
            return self._send(201, {"name": name, "token": token})
        who = self._auth()
        if who is None:
            return self._send(401, {"error": "unauthorized"})
        if len(parts) != 3 or parts[0] != "rooms" or parts[2] != "messages":
            return self._send(404, {"error": "not found"})
        room = self._room()
        if room is None:
            return self._send(400, {"error": "bad room"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, {"error": "bad length"})
        if length <= 0 or length > 65536:
            return self._send(400, {"error": "bad length"})
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "bad json"})
        text = payload.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return self._send(400, {"error": "empty text"})
        msg = self.store.append(room, who, text.strip()[:MAX_TEXT])
        return self._send(201, msg)

    def _query(self):
        from urllib.parse import parse_qs, urlparse

        return parse_qs(urlparse(self.path).query)


def main():
    parser = argparse.ArgumentParser(description="LetsBuild Hub server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--data-dir", default="./hub-data")
    sub = parser.add_subparsers(dest="cmd")
    add = sub.add_parser("add-token", help="create a token for a participant")
    add.add_argument("name")
    add.add_argument("--data-dir", default="./hub-data")
    args = parser.parse_args()

    store = Store(args.data_dir)
    if args.cmd == "add-token":
        if not re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", args.name):
            print("bad name (lowercase letters, digits, _-)", file=sys.stderr)
            raise SystemExit(2)
        token = store.add_token(args.name)
        print(f"token for {args.name}: {token}")
        print("Give it to its owner privately. NEVER commit tokens.json.")
        return

    Handler.store = store
    admin_created = not os.path.exists(store.admin_path)
    store.get_admin_token()
    if admin_created:
        print(f"admin token created at {store.admin_path} — give it to the manager privately (once).")
    else:
        print(f"admin token lives at {store.admin_path} (manager already has it).")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"LetsBuild Hub on http://{args.host}:{args.port} data={args.data_dir}")
    print("Chat only — tasks still go through the board (protocol.md).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
