"""Chạy xếp TKB file FILE_VAO với các hằng số mặc định của main.py (mặc định 2 lần); các lần phải ra cùng mã.

Dùng trong workflow kiểm chứng: ghi một dòng "<máy> | <mã kết quả>" vào ma_ket_qua.txt để job so sánh gom mã
của mọi máy lại. FILE_VAO là file thật của trường (có tên giáo viên): workflow chỉ được tải lên ma_ket_qua.txt,
không tải các file ra trong out/.

Chạy: python .github/scripts/chay_mau.py <tên máy> [--lan N]
  --lan N       số lần chạy (mặc định 2)
"""
from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


class _Tee(io.TextIOBase):
    """Vừa in ra màn hình vừa giữ lại chữ đã in."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text: str) -> int:
        for stream in self.streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def run_once(source: Path, out: Path) -> tuple[int, str | None]:
    """Chạy main.run; trả về (mã thoát, mã kết quả đọc từ dòng "Mã kết quả: ..." in ra màn hình)."""
    printed = io.StringIO()
    with contextlib.redirect_stdout(_Tee(sys.stdout, printed)):
        status = main.run(source, out)
    m = re.search(r"Mã kết quả: (\S+)", printed.getvalue())
    return status, m.group(1) if m else None


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label", nargs="?", default="máy này")
    ap.add_argument("--lan", type=int, default=2, help="số lần chạy")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # tiếng Việt trên Windows khi output bị chuyển hướng
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    source = main._resolve(main.FILE_VAO)
    info = ROOT / "may.txt"
    machine = info.read_text(encoding="utf-8-sig").strip() if info.is_file() else ""
    codes = []
    for i in range(1, args.lan + 1):
        out = ROOT / "out" / f"lan{i}"
        status, code = run_once(source, out)
        if status != 0 or code is None:
            print(f"LỖI: lần chạy {i} trả về mã thoát {status}" + ("" if code else ", không thấy mã kết quả"))
            return status or 1
        codes.append(code)
        print(f"Lần {i}: mã kết quả {codes[-1]}")
    line = " | ".join(part for part in (args.label, machine, codes[0]) if part)
    (ROOT / "ma_ket_qua.txt").write_text(line + "\n", encoding="utf-8", newline="\n")  # job so sánh chạy Linux
    print(line)
    if len(set(codes)) != 1:
        print(f"LỖI: cùng máy, cùng cấu hình mà {args.lan} lần chạy ra mã khác nhau: {', '.join(codes)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
