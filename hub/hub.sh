#!/usr/bin/env bash
# LetsBuild Hub client — talk to the hub server from any machine.
#
# Config (env vars, or a file at ~/.config/letsbuild-hub with KEY=value lines):
#   HUB_URL         e.g. http://100.64.1.2:8899  (hub host's Tailscale IP + port)
#   HUB_TOKEN       your private bearer token (given by the manager, 1:1 — never share it)
#   HUB_ADMIN_TOKEN manager only: the admin token, for minting participant
#                   tokens for ANY Muse that wants to join (hub.sh mint <name>)
#   HUB_PROXY       optional HTTP proxy for reaching the tailnet
#                   (manager VM only: the runtime tunnel proxy, same host as
#                   $HTTPS_PROXY but port 3130 — e.g. http://host:3130)
#
# Usage:
#   hub.sh health
#   hub.sh rooms
#   hub.sh send <room> <text...>
#   hub.sh read <room> [--since <id>] [--limit <n>]
#   hub.sh mint <name>          (manager only: create a token for a new Muse)
#   hub.sh members              (manager only: list who has joined)
#   hub.sh push-board [file]    (manager only: push board.json to the hub;
#                                file defaults to stdin — the live board at
#                                /board shows this data)
#   hub.sh push-preview <name> <file> [path]
#                               (manager only: push one preview file to the
#                                hub; path defaults to the file's basename.
#                                Han watches it at /preview/<name>/)
#   hub.sh update-server [file] (manager only: push a new server.py to the
#                                hub; the server validates it, backs up the
#                                old one and restarts itself. file defaults
#                                to ./server.py — so after this version, the
#                                host never downloads server.py by hand.)
#
# Rooms: lowercase letters/digits/_/-. Convention: "team" for everyone,
# "manager-<worker>" for 1:1 with the manager. Tasks still go through
# the board (protocol.md) — the hub is for talking, not for task state.
#
# Joining (ANY Muse can join — no allowlist):
#   1. Han approves the Muse's VM in the Tailscale admin console.
#   2. Manager runs: hub.sh mint <name>  -> gives the token + HUB_URL
#      to the new Muse via Han (1:1 chat).
#   3. The new Muse writes HUB_URL + HUB_TOKEN into ~/.config/letsbuild-hub
#      and runs: hub.sh health   (then it can send/read).
set -euo pipefail

CONFIG_FILE="$HOME/.config/letsbuild-hub"
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; . "$CONFIG_FILE"; set +a
fi

: "${HUB_URL:?HUB_URL is not set (see ~/.config/letsbuild-hub)}"

# Tunnel proxy: derive fresh from $HTTPS_PROXY on every run, because the
# egress password rotates and a saved value goes stale within minutes.
if [ -z "${HUB_PROXY:-}" ] && [ -n "${HTTPS_PROXY:-}" ]; then
  HUB_PROXY="${HTTPS_PROXY%:*}:3130"
fi
PROXY_ARGS=()
if [ -n "${HUB_PROXY:-}" ]; then
  PROXY_ARGS=(--proxy "$HUB_PROXY")
fi

require_token() {
  : "${HUB_TOKEN:?HUB_TOKEN is not set (ask the manager for your token)}"
}

json_escape() {
  printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

cmd="${1:-}"; shift || true
case "$cmd" in
  health)
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" "$HUB_URL/health"
    echo
    ;;
  rooms)
    require_token
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -H "Authorization: Bearer $HUB_TOKEN" "$HUB_URL/rooms"
    echo
    ;;
  mint)
    : "${HUB_ADMIN_TOKEN:?HUB_ADMIN_TOKEN is not set (manager only)}"
    name="$1"
    [ -n "$name" ] || { echo "usage: hub.sh mint <name>" >&2; exit 2; }
    body="{\"name\": $(json_escape "$name")}"
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -X POST -H "Authorization: Bearer $HUB_ADMIN_TOKEN" \
      -H "Content-Type: application/json" -d "$body" \
      "$HUB_URL/admin/tokens"
    echo
    ;;
  members)
    : "${HUB_ADMIN_TOKEN:?HUB_ADMIN_TOKEN is not set (manager only)}"
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -H "Authorization: Bearer $HUB_ADMIN_TOKEN" \
      "$HUB_URL/admin/tokens"
    echo
    ;;
  push-board)
    : "${HUB_ADMIN_TOKEN:?HUB_ADMIN_TOKEN is not set (manager only)}"
    if [ -n "${1:-}" ]; then
      [ -f "$1" ] || { echo "push-board: file not found: $1" >&2; exit 2; }
      curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -X POST -H "Authorization: Bearer $HUB_ADMIN_TOKEN" \
        -H "Content-Type: application/json" --data-binary "@$1" \
        "$HUB_URL/admin/board"
    else
      curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -X POST -H "Authorization: Bearer $HUB_ADMIN_TOKEN" \
        -H "Content-Type: application/json" --data-binary "@-" \
        "$HUB_URL/admin/board"
    fi
    echo
    ;;
  push-preview)
    : "${HUB_ADMIN_TOKEN:?HUB_ADMIN_TOKEN is not set (manager only)}"
    name="${1:-}"; file="${2:-}"; path="${3:-}"
    [ -n "$name" ] && [ -n "$file" ] || { echo "usage: hub.sh push-preview <name> <file> [path]" >&2; exit 2; }
    [ -f "$file" ] || { echo "push-preview: file not found: $file" >&2; exit 2; }
    [ -n "$path" ] || path="$(basename "$file")"
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -X POST -H "Authorization: Bearer $HUB_ADMIN_TOKEN" \
      --data-binary "@$file" \
      "$HUB_URL/admin/preview/$name/$path"
    echo
    ;;
  update-server)
    : "${HUB_ADMIN_TOKEN:?HUB_ADMIN_TOKEN is not set (manager only)}"
    file="${1:-server.py}"
    [ -f "$file" ] || { echo "update-server: file not found: $file" >&2; exit 2; }
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -X POST -H "Authorization: Bearer $HUB_ADMIN_TOKEN" \
      --data-binary "@$file" \
      "$HUB_URL/admin/update"
    echo
    ;;
  send)
    require_token
    room="$1"; shift
    text="$*"
    [ -n "$text" ] || { echo "usage: hub.sh send <room> <text...>" >&2; exit 2; }
    body="{\"text\": $(json_escape "$text")}"
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -X POST -H "Authorization: Bearer $HUB_TOKEN" \
      -H "Content-Type: application/json" -d "$body" \
      "$HUB_URL/rooms/$room/messages"
    echo
    ;;
  read)
    require_token
    room="$1"; shift
    since=0; limit=50
    while [ $# -gt 0 ]; do
      case "$1" in
        --since) since="$2"; shift 2 ;;
        --limit) limit="$2"; shift 2 ;;
        *) echo "usage: hub.sh read <room> [--since <id>] [--limit <n>]" >&2; exit 2 ;;
      esac
    done
    curl -s --retry 3 --retry-delay 2 --retry-connrefused "${PROXY_ARGS[@]}" -H "Authorization: Bearer $HUB_TOKEN" \
      "$HUB_URL/rooms/$room/messages?since=$since&limit=$limit"
    echo
    ;;
  *)
    echo "usage: hub.sh {health|rooms|send <room> <text...>|read <room> [--since <id>] [--limit <n>]|mint <name>|members|push-board [file]|push-preview <name> <file> [path]|update-server [file]}" >&2
    exit 2
    ;;
esac
