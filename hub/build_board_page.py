#!/usr/bin/env python3
"""Build the inlined board viewer page and inject it into hub/server.py.

Reads the T-005 board viewer sources (index.html, styles.css, app.js),
inlines the CSS/JS, adds a 15 s auto-refresh, swaps the embedded
FALLBACK_DATA snapshot for the CURRENT board.json, and writes the
result as the BOARD_PAGE_HTML constant in server.py (replacing the
placeholder line). Stdlib only.
"""
import json
import re
import sys
from pathlib import Path

VIEWER_DIR = Path("/tmp/board-viewer")
BOARD_JSON = Path("/tmp/board-current.json")
SERVER_PY = Path("/home/hatch/workspace/letsbuild/hub/server.py")
PLACEHOLDER = 'BOARD_PAGE_HTML = ""  # __BOARD_PAGE_HTML__'


def main():
    index_html = (VIEWER_DIR / "index.html").read_text(encoding="utf-8")
    css = (VIEWER_DIR / "styles.css").read_text(encoding="utf-8")
    js = (VIEWER_DIR / "app.js").read_text(encoding="utf-8")
    board = json.loads(BOARD_JSON.read_text(encoding="utf-8"))

    # 1. Swap the stale FALLBACK_DATA snapshot for the current board.
    #    The block runs from "var FALLBACK_DATA = {" to the "};" just
    #    before "function escapeHtml".
    start = js.index("var FALLBACK_DATA = {")
    end_marker = "\n};\n\nfunction escapeHtml"
    end = js.index(end_marker, start) + len("\n};")
    js = js[:start] + "var FALLBACK_DATA = " + json.dumps(board, ensure_ascii=False, indent=2) + ";" + js[end:]

    # 1b. Fix B1 (QA T-007): an empty board hid all 4 columns and showed
    #     "Chưa tải được dữ liệu board." even though the data HAD loaded.
    #     The board must always stay visible (each empty column shows
    #     "Chưa có task"); the empty-state note is only for a failed load,
    #     which cannot happen here because FALLBACK_DATA is embedded.
    js = js.replace(
        'document.getElementById("empty-state").hidden = total > 0;',
        'document.getElementById("empty-state").hidden = true;',
        1,
    )
    js = js.replace(
        'document.getElementById("board").hidden = total === 0;',
        'document.getElementById("board").hidden = false;',
        1,
    )

    # 2. Add auto-refresh to the page head.
    index_html = index_html.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<meta http-equiv="refresh" content="15">',
        1,
    )

    # 3. Inline the CSS and JS.
    index_html = index_html.replace(
        '<link rel="stylesheet" href="styles.css">',
        "<style>\n" + css + "\n</style>",
        1,
    )
    index_html = index_html.replace(
        '<script src="app.js"></script>',
        "<script>\n" + js + "\n</script>",
        1,
    )

    # 4. Footer: hub version (live data, auto-refresh) instead of the
    #    file:// note.
    footer_old = re.search(r"<footer.*?</footer>", index_html, re.DOTALL)
    if footer_old:
        footer_new = (
            "<footer class=\"footer\">\n"
            "  <p>LetsBuild — board viewer live trên hub. Dữ liệu do quản lý đẩy lên "
            "hub mỗi khi board thay đổi; trang tự làm mới mỗi 15 giây, bấm "
            "“Tải lại dữ liệu” để tải ngay. Xem chat team tại <a href=\"/\">trang chủ hub</a>.</p>\n"
            "</footer>"
        )
        index_html = index_html[: footer_old.start()] + footer_new + index_html[footer_old.end():]

    page = index_html
    assert "<style>" in page and "<script>" in page
    assert "http-equiv=\"refresh\" content=\"15\"" in page
    assert "FALLBACK_DATA = {" in page
    # The page must not reference the separate files anymore.
    assert 'href="styles.css"' not in page and 'src="app.js"' not in page

    text = SERVER_PY.read_text(encoding="utf-8")
    const = "BOARD_PAGE_HTML = " + repr(page)
    # Replace the placeholder on first build, or the existing constant
    # line on rebuilds (the repr is a single line, so ^...$ matches it).
    if PLACEHOLDER in text:
        text = text.replace(PLACEHOLDER, const, 1)
    else:
        # Use a lambda as the replacement so the repr's backslash
        # escapes (\n, \', ...) are inserted literally — re.sub would
        # otherwise interpret them (e.g. \n becomes a real newline and
        # breaks the string literal across lines).
        new_text, n = re.subn(
            r"^BOARD_PAGE_HTML = .*$",
            lambda m: const,
            text,
            count=1,
            flags=re.MULTILINE,
        )
        assert n == 1, "BOARD_PAGE_HTML assignment not found in server.py"
        text = new_text
    SERVER_PY.write_text(text, encoding="utf-8")
    print(f"injected BOARD_PAGE_HTML ({len(page)} chars) into server.py")


if __name__ == "__main__":
    main()
