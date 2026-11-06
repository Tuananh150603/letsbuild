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

Endpoints (all JSON; all except /health, /, /board, /board.json and
/preview/* need Authorization: Bearer <token>):
    GET  /health                          -> {"ok": true}
    GET  /                                -> read-only viewer (HTML, no auth:
                                              host-only page so Han can watch
                                              the team chat; auto-refreshes)
    GET  /board                           -> live board viewer (HTML, no auth;
                                              the T-005 board viewer, served
                                              by the hub; auto-refreshes)
    GET  /board.json                      -> current board data (no auth)
    GET  /preview/<name>                  -> preview wrapper page (HTML, no
                                              auth; iframe + auto-refresh)
    GET  /preview/<name>/<path>           -> a preview file (no auth)
    GET  /rooms                           -> {"rooms": [...]}
    POST /rooms/<room>/messages           {"text": "..."} -> the message
    GET  /rooms/<room>/messages?since=<id>&limit=<n>
    POST /admin/tokens                    {"name": "..."} -> {"name", "token"}
    GET  /admin/tokens                    -> {"names": [...]} (names only)
    POST /admin/board                     <board json> -> {"ok": true}
                                              (manager pushes board.json here
                                              after every board change)
    POST /admin/preview/<name>/<path>     <raw file bytes> -> {"ok": true}
                                              (manager pushes a worker's web
                                              output here after QA)

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
PREVIEW_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_TEXT = 5000
DEFAULT_LIMIT = 50
MAX_BOARD_BYTES = 1 * 1024 * 1024
MAX_PREVIEW_BYTES = 10 * 1024 * 1024

# Content types for preview files, by extension. Anything else is
# served as a download, never executed.
PREVIEW_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".ico": "image/x-icon",
}

# Live board viewer page (the T-005 board viewer, inlined so the hub
# serves it from this single file). Filled in by tools/build_board_page.py
# from the viewer sources; the placeholder is replaced at build time.
BOARD_PAGE_HTML = '<!DOCTYPE html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<meta http-equiv="refresh" content="15">\n<title>LetsBuild Board</title>\n<style>\n/* LetsBuild Board — minimal, clean. One accent colour: #2563eb (blue). */\n* { box-sizing: border-box; }\n\nbody {\n  margin: 0;\n  background: #ffffff;\n  color: #1a1a1a;\n  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;\n  font-size: 15px;\n  line-height: 1.5;\n}\n\ncode { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.9em; }\n\n/* ---------- Header ---------- */\n.topbar { border-bottom: 1px solid #e5e5e5; padding: 20px 24px 12px; }\n.topbar-inner {\n  max-width: 1440px; margin: 0 auto;\n  display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;\n}\n.topbar h1 { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }\n.subtitle { margin: 4px 0 0; color: #666; font-size: 14px; }\n.topbar-right { text-align: right; }\n.updated { margin: 0 0 8px; color: #666; font-size: 14px; }\n.updated span { color: #1a1a1a; font-weight: 600; }\n\n#refresh-btn {\n  font: inherit; font-size: 14px; cursor: pointer;\n  background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 14px;\n}\n#refresh-btn:hover { background: #1d4ed8; }\n#refresh-btn:focus-visible { outline: 2px solid #1d4ed8; outline-offset: 2px; }\n\n.data-source {\n  max-width: 1440px; margin: 10px auto 0; padding: 8px 12px;\n  background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;\n  color: #713f12; font-size: 13px;\n}\n\n/* ---------- Board ---------- */\n.board {\n  max-width: 1440px; margin: 0 auto; padding: 20px 24px;\n  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px;\n  align-items: start;\n}\n.column {\n  background: #f7f7f7; border: 1px solid #e5e5e5; border-radius: 12px; padding: 12px;\n  min-width: 0;\n}\n.column h2 {\n  margin: 0 0 12px; font-size: 14px; font-weight: 700;\n  text-transform: uppercase; letter-spacing: 0.06em; color: #333;\n  display: flex; justify-content: space-between; align-items: center;\n}\n.count {\n  background: #e5e5e5; color: #333; border-radius: 999px;\n  font-size: 12px; font-weight: 700; padding: 1px 8px; min-width: 24px; text-align: center;\n}\n.cards { display: flex; flex-direction: column; gap: 10px; }\n.column-empty { color: #999; font-size: 13px; text-align: center; padding: 12px 0; margin: 0; }\n\n/* ---------- Cards ---------- */\n.card {\n  background: #fff; border: 1px solid #e5e5e5; border-left: 3px solid #2563eb;\n  border-radius: 10px; padding: 12px 14px; cursor: pointer; text-align: left;\n  font: inherit; width: 100%;\n}\n.card:hover { border-color: #2563eb; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08); }\n.card:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }\n.card-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }\n.card-id { font-weight: 700; font-size: 13px; color: #2563eb; }\n.card-title { margin: 0 0 8px; font-size: 15px; font-weight: 600; line-height: 1.4; overflow-wrap: break-word; }\n.card-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; color: #666; font-size: 13px; }\n.card-meta span { white-space: nowrap; }\n.card-meta .worker { color: #1a1a1a; font-weight: 600; }\n\n.priority {\n  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;\n  border-radius: 999px; padding: 2px 8px; white-space: nowrap;\n}\n.priority-high { background: #fee2e2; color: #b91c1c; }\n.priority-medium { background: #fef3c7; color: #92400e; }\n.priority-low { background: #e5e5e5; color: #555; }\n\n/* ---------- Modal ---------- */\n.modal { position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center; padding: 20px; }\n.modal[hidden] { display: none; }\n.modal-backdrop { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.45); }\n.modal-box {\n  position: relative; background: #fff; border-radius: 14px; padding: 24px;\n  width: 100%; max-width: 520px; max-height: 85vh; overflow: auto;\n  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);\n}\n.modal-close {\n  position: absolute; top: 10px; right: 14px; border: none; background: none;\n  font-size: 28px; line-height: 1; color: #666; cursor: pointer; padding: 4px 8px;\n}\n.modal-close:hover { color: #1a1a1a; }\n.modal-id { margin: 0 0 6px; font-weight: 700; color: #2563eb; display: flex; gap: 10px; align-items: center; }\n.modal-box h3 { margin: 0 0 16px; font-size: 20px; line-height: 1.35; overflow-wrap: break-word; }\n.detail-list { margin: 0; }\n.detail-list div {\n  display: flex; justify-content: space-between; gap: 16px;\n  padding: 10px 0; border-top: 1px solid #eee;\n}\n.detail-list dt { color: #666; flex-shrink: 0; }\n.detail-list dd { margin: 0; font-weight: 600; text-align: right; overflow-wrap: break-word; }\n\n/* ---------- Misc ---------- */\n.empty-state { text-align: center; color: #666; padding: 40px 20px; }\n.footer { max-width: 1440px; margin: 0 auto; padding: 0 24px 24px; color: #999; font-size: 13px; }\n\n/* ---------- Narrow screens ---------- */\n@media (max-width: 1100px) {\n  .board { grid-template-columns: repeat(2, minmax(0, 1fr)); }\n}\n@media (max-width: 640px) {\n  .board { grid-template-columns: 1fr; padding: 16px; }\n  .topbar { padding: 16px 16px 10px; }\n  .topbar-right { text-align: left; }\n}\n\n</style>\n</head>\n<body>\n<header class="topbar">\n  <div class="topbar-inner">\n    <div>\n      <h1>LetsBuild Board</h1>\n      <p class="subtitle">Bảng công việc của team — đọc từ <code>board.json</code></p>\n    </div>\n    <div class="topbar-right">\n      <p class="updated">Cập nhật: <span id="updated-at">…</span></p>\n      <button id="refresh-btn" type="button">Tải lại dữ liệu</button>\n    </div>\n  </div>\n  <p id="data-source" class="data-source" hidden></p>\n</header>\n\n<main id="board" class="board" aria-live="polite">\n  <section class="column" data-column="queue">\n    <h2>Queue <span class="count" id="count-queue">0</span></h2>\n    <div class="cards" id="cards-queue"></div>\n  </section>\n  <section class="column" data-column="doing">\n    <h2>Doing <span class="count" id="count-doing">0</span></h2>\n    <div class="cards" id="cards-doing"></div>\n  </section>\n  <section class="column" data-column="done">\n    <h2>Done <span class="count" id="count-done">0</span></h2>\n    <div class="cards" id="cards-done"></div>\n  </section>\n  <section class="column" data-column="archive">\n    <h2>Archive <span class="count" id="count-archive">0</span></h2>\n    <div class="cards" id="cards-archive"></div>\n  </section>\n</main>\n\n<p id="empty-state" class="empty-state" hidden>Chưa tải được dữ liệu board.</p>\n\n<div id="modal" class="modal" hidden>\n  <div class="modal-backdrop" id="modal-backdrop"></div>\n  <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">\n    <button id="modal-close" class="modal-close" type="button" aria-label="Đóng">×</button>\n    <p class="modal-id"><span id="modal-id"></span> <span id="modal-priority" class="priority"></span></p>\n    <h3 id="modal-title"></h3>\n    <dl class="detail-list">\n      <div><dt>Trạng thái</dt><dd id="modal-status"></dd></div>\n      <div><dt>Người làm</dt><dd id="modal-worker"></dd></div>\n      <div><dt>Loại task</dt><dd id="modal-type"></dd></div>\n      <div><dt>Ngày tạo</dt><dd id="modal-created"></dd></div>\n      <div id="modal-claimed-row"><dt>Claim lúc</dt><dd id="modal-claimed"></dd></div>\n    </dl>\n  </div>\n</div>\n\n<footer class="footer">\n  <p>LetsBuild — board viewer live trên hub. Dữ liệu do quản lý đẩy lên hub mỗi khi board thay đổi; trang tự làm mới mỗi 15 giây, bấm “Tải lại dữ liệu” để tải ngay. Xem chat team tại <a href="/">trang chủ hub</a>.</p>\n</footer>\n\n<script>\n"use strict";\n\n/* Board viewer — reads board.json from the same folder and renders it.\n *\n * Data source: fetch("board.json"). If that fails (e.g. Chrome blocks\n * fetch from file:// when the page is opened by double-click), the page\n * falls back to FALLBACK_DATA below — a snapshot of the same board.json\n * shipped with the page — and shows a notice. To always read the live\n * JSON, open the folder through a local server, e.g.:\n *   python3 -m http.server 8000\n * then visit http://localhost:8000/index.html\n */\n\nvar COLUMNS = [\n  { key: "queue", label: "Queue" },\n  { key: "doing", label: "Doing" },\n  { key: "done", label: "Done" },\n  { key: "archive", label: "Archive" }\n];\n\nvar PRIORITY_LABELS = { high: "Cao", medium: "Trung bình", low: "Thấp" };\n\n/* Snapshot of board.json, used only when fetch is blocked (file://). */\nvar FALLBACK_DATA = {\n  "updated_at": "2026-11-06T12:32:10Z",\n  "columns": {\n    "queue": [],\n    "doing": [],\n    "done": [],\n    "archive": [\n      {\n        "id": "T-001",\n        "title": "Verify worker setup — chạy setup 1 lệnh + báo self-test",\n        "type": "other",\n        "priority": "high",\n        "created": "2026-11-06",\n        "worker": "Muse 1"\n      },\n      {\n        "id": "T-002",\n        "title": "Verify worker setup — chạy setup 1 lệnh + báo self-test (worker 2)",\n        "type": "other",\n        "priority": "high",\n        "created": "2026-11-06",\n        "worker": "worker 2"\n      },\n      {\n        "id": "T-003",\n        "title": "Nghiên cứu repo hướng dẫn agent vẽ Figma + báo cáo cách team áp dụng (worker 1)",\n        "type": "research",\n        "priority": "high",\n        "created": "2026-11-06",\n        "worker": "Muse 1"\n      },\n      {\n        "id": "T-004",\n        "title": "Nghiên cứu repo hướng dẫn agent vẽ Figma + báo cáo cách team áp dụng (worker 2)",\n        "type": "research",\n        "priority": "high",\n        "created": "2026-11-06",\n        "worker": "worker 2"\n      },\n      {\n        "id": "T-005",\n        "title": "Thiết kế + code giao diện web xem board LetsBuild (worker 1)",\n        "type": "code",\n        "priority": "high",\n        "created": "2026-11-06",\n        "worker": "Muse 1",\n        "claimed_at": "2026-11-06T11:13:52Z"\n      },\n      {\n        "id": "T-006",\n        "title": "Script xuất dữ liệu board LetsBuild ra JSON (worker 2)",\n        "type": "code",\n        "priority": "high",\n        "created": "2026-11-06",\n        "worker": "worker 2"\n      }\n    ]\n  }\n};\n\nfunction escapeHtml(value) {\n  return String(value == null ? "" : value)\n    .replace(/&/g, "&amp;")\n    .replace(/</g, "&lt;")\n    .replace(/>/g, "&gt;")\n    .replace(/"/g, "&quot;")\n    .replace(/\'/g, "&#39;");\n}\n\nfunction formatDate(value) {\n  if (!value) return "—";\n  var d = new Date(value);\n  if (isNaN(d.getTime())) return String(value);\n  return d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });\n}\n\nfunction formatDay(value) {\n  if (!value) return "—";\n  var d = new Date(value.length === 10 ? value + "T00:00:00Z" : value);\n  if (isNaN(d.getTime())) return String(value);\n  return d.toLocaleDateString("vi-VN");\n}\n\nfunction priorityHtml(priority) {\n  var p = (priority || "low").toLowerCase();\n  var label = PRIORITY_LABELS[p] || priority || "—";\n  return \'<span class="priority priority-\' + escapeHtml(p) + \'">\' + escapeHtml(label) + "</span>";\n}\n\nfunction cardHtml(task, columnLabel) {\n  var worker = task.worker ? \'<span class="worker">\' + escapeHtml(task.worker) + "</span>" : "";\n  var created = task.created ? "<span>Tạo " + escapeHtml(formatDay(task.created)) + "</span>" : "";\n  return (\n    \'<button type="button" class="card" data-id="\' + escapeHtml(task.id) + \'" data-column="\' + escapeHtml(columnLabel) + \'">\' +\n      \'<span class="card-top"><span class="card-id">\' + escapeHtml(task.id) + "</span>" + priorityHtml(task.priority) + "</span>" +\n      \'<span class="card-title">\' + escapeHtml(task.title || "(không có tiêu đề)") + "</span>" +\n      \'<span class="card-meta">\' + worker + created + "</span>" +\n    "</button>"\n  );\n}\n\nfunction render(data) {\n  var columns = data.columns || {};\n  var total = 0;\n  COLUMNS.forEach(function (col) {\n    var tasks = Array.isArray(columns[col.key]) ? columns[col.key] : [];\n    total += tasks.length;\n    document.getElementById("count-" + col.key).textContent = String(tasks.length);\n    var box = document.getElementById("cards-" + col.key);\n    if (tasks.length === 0) {\n      box.innerHTML = \'<p class="column-empty">Chưa có task</p>\';\n    } else {\n      box.innerHTML = tasks.map(function (t) { return cardHtml(t, col.label); }).join("");\n    }\n  });\n  document.getElementById("updated-at").textContent = formatDate(data.updated_at);\n  document.getElementById("empty-state").hidden = total > 0;\n  document.getElementById("board").hidden = total === 0;\n}\n\nfunction openDetail(task, columnLabel) {\n  document.getElementById("modal-id").textContent = task.id || "";\n  var pr = document.getElementById("modal-priority");\n  var p = (task.priority || "low").toLowerCase();\n  pr.className = "priority priority-" + p;\n  pr.textContent = PRIORITY_LABELS[p] || task.priority || "—";\n  document.getElementById("modal-title").textContent = task.title || "(không có tiêu đề)";\n  document.getElementById("modal-status").textContent = columnLabel;\n  document.getElementById("modal-worker").textContent = task.worker || "—";\n  document.getElementById("modal-type").textContent = task.type || "—";\n  document.getElementById("modal-created").textContent = formatDay(task.created);\n  var claimedRow = document.getElementById("modal-claimed-row");\n  if (task.claimed_at) {\n    claimedRow.hidden = false;\n    document.getElementById("modal-claimed").textContent = formatDate(task.claimed_at);\n  } else {\n    claimedRow.hidden = true;\n  }\n  document.getElementById("modal").hidden = false;\n}\n\nfunction closeDetail() {\n  document.getElementById("modal").hidden = true;\n}\n\nvar currentData = null;\n\nfunction loadBoard() {\n  return fetch("board.json", { cache: "no-store" })\n    .then(function (resp) {\n      if (!resp.ok) throw new Error("HTTP " + resp.status);\n      return resp.json();\n    })\n    .then(function (data) {\n      currentData = data;\n      var note = document.getElementById("data-source");\n      note.hidden = true;\n      note.textContent = "";\n      render(data);\n    })\n    .catch(function () {\n      /* fetch blocked (file:// in Chrome) or board.json missing/unparsable:\n         show the embedded snapshot and say so. */\n      currentData = FALLBACK_DATA;\n      var note = document.getElementById("data-source");\n      note.hidden = false;\n      note.textContent =\n        "Đang hiển thị dữ liệu nhúng sẵn — trình duyệt chặn đọc file board.json khi mở trực tiếp. " +\n        "Để xem dữ liệu live từ board.json, chạy: python3 -m http.server 8000 rồi mở http://localhost:8000/index.html";\n      render(FALLBACK_DATA);\n    });\n}\n\ndocument.getElementById("board").addEventListener("click", function (event) {\n  var card = event.target.closest(".card");\n  if (!card || !currentData) return;\n  var colKey = COLUMNS.filter(function (c) { return c.label === card.getAttribute("data-column"); })[0];\n  var tasks = (currentData.columns || {})[colKey ? colKey.key : ""] || [];\n  var task = null;\n  for (var i = 0; i < tasks.length; i++) {\n    if (tasks[i].id === card.getAttribute("data-id")) { task = tasks[i]; break; }\n  }\n  if (task) openDetail(task, card.getAttribute("data-column"));\n});\n\ndocument.getElementById("modal-close").addEventListener("click", closeDetail);\ndocument.getElementById("modal-backdrop").addEventListener("click", closeDetail);\ndocument.addEventListener("keydown", function (event) {\n  if (event.key === "Escape") closeDetail();\n});\ndocument.getElementById("refresh-btn").addEventListener("click", loadBoard);\n\nloadBoard();\n\n</script>\n</body>\n</html>\n'


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

    # ---- Live board + previews (manager pushes, Han watches) ----
    @property
    def board_path(self):
        return os.path.join(self.data_dir, "board.json")

    @property
    def previews_dir(self):
        return os.path.join(self.data_dir, "previews")

    def read_board(self):
        """Current board data, or an empty board when nothing was
        pushed yet. The board.json format is the T-006 exporter format:
        {"updated_at": ..., "columns": {"queue": [...], ...}}."""
        empty = {
            "updated_at": None,
            "columns": {"queue": [], "doing": [], "done": [], "archive": []},
        }
        if not os.path.exists(self.board_path):
            return empty
        try:
            with open(self.board_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or not isinstance(
                data.get("columns"), dict
            ):
                return empty
            return data
        except (ValueError, OSError):
            return empty

    def write_board(self, data):
        """Atomic board write (tmp + replace), thread-safe."""
        with self.lock:
            tmp = self.board_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.board_path)

    def _preview_fs_path(self, name, relpath):
        """Validated filesystem path for a preview file, or None when
        the name/path is unsafe. No absolute paths, no '..' segments."""
        if not PREVIEW_NAME_RE.match(name or ""):
            return None
        parts = [p for p in (relpath or "").split("/") if p not in ("", ".")]
        if not parts or any(p == ".." for p in parts):
            return None
        # Reject anything that is not a plain relative file path.
        if any(os.sep in p or p in (".", "..") for p in parts):
            return None
        return os.path.join(self.previews_dir, name, *parts)

    def write_preview(self, name, relpath, data_bytes):
        """Atomic preview-file write (tmp + replace), thread-safe.
        Returns the stored relative path, or None when unsafe."""
        target = self._preview_fs_path(name, relpath)
        if target is None:
            return None
        with self.lock:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            tmp = target + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
            return relpath

    def read_preview(self, name, relpath):
        """Preview file bytes, or None when missing/unsafe."""
        target = self._preview_fs_path(name, relpath)
        if target is None or not os.path.exists(target):
            return None
        try:
            with open(target, "rb") as f:
                return f.read()
        except OSError:
            return None

    def preview_has_index(self, name):
        target = self._preview_fs_path(name, "index.html")
        return bool(target) and os.path.exists(target)


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

    def _send_file(self, status, data_bytes, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data_bytes)))
        self.end_headers()
        self.wfile.write(data_bytes)

    def _board_page(self):
        """Live board viewer (no auth): the T-005 board viewer, served
        by the hub. It fetches /board.json, so it always shows the
        board the manager last pushed. Auto-refreshes every 15 s."""
        if not BOARD_PAGE_HTML:
            return self._send_html(
                200,
                "<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
                "<title>LetsBuild Board</title></head><body>"
                "<p>Board viewer chưa được nhúng vào server này — "
                "cần bản server.py đã build kèm viewer.</p></body></html>",
            )
        return self._send_html(200, BOARD_PAGE_HTML)

    def _preview_wrapper(self, name):
        """Preview wrapper page (no auth): an iframe showing the
        preview's index.html, auto-refreshing every 15 s so Han sees
        the newest push without reloading by hand."""
        import html as html_mod

        safe = html_mod.escape(name)
        if not self.store.preview_has_index(name):
            return self._send_html(
                200,
                "<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                f"<title>Preview — {safe}</title>"
                "<style>body{font-family:system-ui,sans-serif;max-width:760px;"
                "margin:0 auto;padding:16px;color:#1a1a1a}"
                "a{color:#2563eb}</style></head><body>"
                f"<h1>Preview: {safe}</h1>"
                "<p>Chưa có preview này — quản lý đẩy file lên hub rồi "
                "mở lại trang này.</p>"
                "<p><a href=\"/board\">← Board</a> · "
                "<a href=\"/\">Chat</a></p></body></html>",
            )
        html = (
            "<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
            "<meta http-equiv=\"refresh\" content=\"15\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>Preview — {safe}</title>"
            "<style>body{margin:0;font-family:system-ui,sans-serif}"
            ".bar{padding:8px 12px;background:#f7f7f7;border-bottom:1px solid #e5e5e5;"
            "font-size:14px;color:#333;display:flex;justify-content:space-between;gap:12px}"
            ".bar a{color:#2563eb}"
            "iframe{border:0;width:100%;height:calc(100vh - 41px);display:block}</style>"
            "</head><body>"
            f"<div class=\"bar\"><span>Preview: <b>{safe}</b> — tự làm mới mỗi 15 giây</span>"
            "<span><a href=\"/board\">← Board</a> · <a href=\"/\">Chat</a></span></div>"
            f"<iframe src=\"/preview/{safe}/index.html\"></iframe>"
            "</body></html>"
        )
        return self._send_html(200, html)

    def _preview_file(self, name, relpath):
        data = self.store.read_preview(name, relpath)
        if data is None:
            return self._send(404, {"error": "not found"})
        _, ext = os.path.splitext(relpath)
        content_type = PREVIEW_TYPES.get(
            ext.lower(), "application/octet-stream"
        )
        return self._send_file(200, data, content_type)

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
        if path == "/board":
            return self._board_page()
        if path == "/board.json":
            return self._send(200, self.store.read_board())
        if path == "/preview" or path.startswith("/preview/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) == 2:
                return self._preview_wrapper(parts[1])
            if len(parts) >= 3:
                return self._preview_file(parts[1], "/".join(parts[2:]))
            return self._send(404, {"error": "not found"})
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
        if parts == ["admin", "board"]:
            if not self._admin_auth():
                return self._send(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "bad length"})
            if length <= 0 or length > MAX_BOARD_BYTES:
                return self._send(400, {"error": "bad length"})
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"error": "bad json"})
            if not isinstance(data, dict) or not isinstance(
                data.get("columns"), dict
            ):
                return self._send(400, {"error": "bad board"})
            self.store.write_board(data)
            return self._send(200, {"ok": True})
        if len(parts) >= 4 and parts[0] == "admin" and parts[1] == "preview":
            if not self._admin_auth():
                return self._send(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "bad length"})
            if length < 0 or length > MAX_PREVIEW_BYTES:
                return self._send(400, {"error": "bad length"})
            raw = self.rfile.read(length) if length > 0 else b""
            stored = self.store.write_preview(
                parts[2], "/".join(parts[3:]), raw
            )
            if stored is None:
                return self._send(400, {"error": "bad name/path"})
            return self._send(
                200, {"ok": True, "name": parts[2], "path": stored}
            )
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
    print("Han xem board live: /board — xem preview code: /preview/<ten>/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
