"""Nhúng các biểu tượng SVG của Bootstrap Icons (MIT) vào tkb/giao_dien/static/index.html, giữa hai dòng
<!-- BIEU_TUONG --> và <!-- /BIEU_TUONG -->: mỗi biểu tượng một <symbol id="i-<tên>">, trang dùng
<svg class="ic"><use href="#i-<tên>"></use></svg> (app.js: icon(tên)). Nhúng sẵn trong trang nên chạy không cần Internet.

Thêm biểu tượng: thêm một dòng vào ICONS (tên dùng trong trang → tên file của Bootstrap Icons, xem
https://icons.getbootstrap.com), tải gói rồi chạy lại:
  npm pack bootstrap-icons@1.11.3 && tar xzf bootstrap-icons-1.11.3.tgz
  python tools/bieu_tuong.py package/icons
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tkb" / "giao_dien" / "static" / "index.html"
VERSION = "1.11.3"
START, END = "<!-- BIEU_TUONG -->", "<!-- /BIEU_TUONG -->"
ICONS = {
    "undo": "arrow-counterclockwise", "redo": "arrow-clockwise", "caret": "chevron-down", "chevron": "chevron-right",
    "back": "arrow-left", "next": "arrow-right", "close": "x-lg", "trash": "trash3", "up": "arrow-up",
    "down": "arrow-down", "plus": "plus-lg", "minus": "dash-lg", "ok": "check-circle-fill",
    "bad": "exclamation-triangle-fill", "wait": "question-circle", "lock": "lock-fill", "unlock": "unlock",
    "excel": "file-earmark-spreadsheet", "open": "folder2-open", "download": "download",
    "template": "file-earmark-plus", "save": "floppy", "restart": "arrow-repeat", "erase": "eraser",
    "mode": "sliders", "board": "grid-3x3", "clock": "clock", "book": "book", "people": "people",
    "badge": "person-badge", "person": "person-vcard", "rules": "list-check", "play": "play-fill",
    "stop": "stop-fill", "gear": "gear", "calendar": "calendar3", "info": "info-circle", "eye": "eye",
    "edit": "pencil-square", "paste": "clipboard-plus", "check": "clipboard-check", "folder": "folder2",
    "door": "door-open", "files": "files", "star": "stars",
}


def sprite(folder: Path) -> str:
    symbols = []
    for name, file in ICONS.items():
        svg = (folder / f"{file}.svg").read_text(encoding="utf-8")
        view = re.search(r'viewBox="([^"]+)"', svg).group(1)
        inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg, flags=re.S).strip()
        inner = re.sub(r"\s*\n\s*", "", inner)
        symbols.append(f'<symbol id="i-{name}" viewBox="{view}">{inner}</symbol>')
    note = (f"<!-- Bootstrap Icons {VERSION} (https://icons.getbootstrap.com), MIT License, Copyright (c) 2019-2024 The "
            "Bootstrap Authors. Sinh bởi tools/bieu_tuong.py, đừng sửa tay. -->")
    return "\n".join([START, note, '<svg xmlns="http://www.w3.org/2000/svg" hidden>', *symbols, "</svg>", END])


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    page = PAGE.read_text(encoding="utf-8")
    block = sprite(Path(argv[0]))
    if START in page:
        page = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: block, page, flags=re.S)
    else:
        page = page.replace("<body>\n", "<body>\n" + block + "\n", 1)
    PAGE.write_text(page, encoding="utf-8")
    print(f"Đã ghi {len(ICONS)} biểu tượng vào {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
