"""Chạy: python -m tkb.giao_dien [--cong 8765] [--thu-muc <thư mục TKB>] [--khong-mo-trinh-duyet]"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--cli"]:  # bản đóng gói: tiến trình con xếp TKB (server.cli_command)
        from ..__main__ import main as tkb_main
        return tkb_main(argv[1:])
    from ..__main__ import use_utf8_output
    from .server import PORT, serve

    use_utf8_output()
    ap = argparse.ArgumentParser(prog="python -m tkb.giao_dien", description="Giao diện web xếp thời khóa biểu")
    ap.add_argument("--cong", type=int, default=PORT, help=f"Cổng trên máy này (mặc định {PORT}; bận thì lấy cổng khác)")
    ap.add_argument("--thu-muc", help="Thư mục TKB: mọi file trang đọc, ghi đều ở đây (mặc định out/ của dự án; bản "
                    "đóng gói: thư mục có TKB.exe)")
    ap.add_argument("--khong-mo-trinh-duyet", action="store_true", help="Không tự mở trình duyệt")
    args = ap.parse_args(argv)
    return serve(args.cong, not args.khong_mo_trinh_duyet, args.thu_muc)


if __name__ == "__main__":
    sys.exit(main())
