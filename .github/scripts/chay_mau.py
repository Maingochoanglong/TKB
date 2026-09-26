"""Chạy xếp TKB file FILE_VAO với các hằng số mặc định của main.py (mặc định 2 lần); các lần phải ra cùng mã.

Dùng trong workflow kiểm chứng: ghi một dòng "<máy> | <mã kết quả>" vào ma_ket_qua.txt để job so sánh gom mã
của mọi máy lại. FILE_VAO là file thật của trường (có tên giáo viên): workflow chỉ được tải lên ma_ket_qua.txt,
không tải các file ra trong out/.

Chạy: python .github/scripts/chay_mau.py <tên máy> [--lan N]
  --lan N       số lần chạy (mặc định 2)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

import main  # noqa: E402

def result_code(stats_file: Path) -> str:
    ws = openpyxl.load_workbook(stats_file)["Tổng quan"]
    return next(row[1] for row in ws.iter_rows(values_only=True) if row[0] == "Mã kết quả")


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label", nargs="?", default="máy này")
    ap.add_argument("--lan", type=int, default=2, help="số lần chạy")
    args = ap.parse_args(argv)
    source = main._resolve(main.FILE_VAO)
    info = ROOT / "may.txt"
    machine = info.read_text(encoding="utf-8-sig").strip() if info.is_file() else ""
    codes = []
    for i in range(1, args.lan + 1):
        out = ROOT / "out" / f"lan{i}"
        status = main.run(source, out)
        if status != 0:
            print(f"LỖI: lần chạy {i} trả về mã thoát {status}")
            return status
        codes.append(result_code(out / main.FILE_THONG_KE))
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
