"""Trường mẫu tên giả gấp k lần (tkb/truong_mau.py) để đo tốc độ và bộ nhớ khi trường lớn hơn.

Khối 1–4 mỗi khối 6k lớp, khối 5 có 5k lớp; nhân sự theo cùng tỉ lệ (mỗi lớp một GVCN định mức 19; bộ môn, GV chuyên
biệt gấp k lần, định mức 23; một quản lý), chương trình học như trường mẫu. Tên giả, không phải dữ liệu của trường.
k = 1 gần giống trường mẫu (trường mẫu có GVCN 5/5 và Bộ Môn 5 định mức thấp hơn).
  python tools/truong_lon.py 2 out/truong_x2.xlsx      # 58 lớp, 89 nhân sự
  python -m tkb out/truong_x2.xlsx -o out/x2/TKB.xlsx --mode bu_gio
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tkb.staff import Teacher, clean_name, make_teacher, normalize  # noqa: E402
from tkb.template import write_staff_template  # noqa: E402
from tkb.truong_mau import CURRICULUM  # noqa: E402

# (Chức Vụ, chữ viết tắt trong tên giả, số người của trường mẫu)
_ROLES = [("Bộ Môn", "BM", 5), ("Tiếng Anh", "TA", 4), ("Thể Dục", "TD", 3), ("Âm Nhạc", "ÂN", 1),
          ("Mỹ Thuật", "MT", 1), ("Tin Học", "TH", 1)]


def staff_rows(k: int) -> list[tuple[str, str, str | None, int]]:
    """Dòng sheet NHÂN SỰ (Họ và Tên, Chức Vụ, Lớp, Số Tiết/Tuần) của trường gấp k lần."""
    classes = [f"{g}/{n}" for g in sorted(CURRICULUM) for n in range(1, (6 if g < 5 else 5) * k + 1)]
    rows = [(f"Giáo viên CN {i}", "Chủ Nhiệm", c, 19) for i, c in enumerate(classes, start=1)]
    for title, short, count in _ROLES:
        rows += [(f"Giáo viên {short} {i}", title, None, 23) for i in range(1, count * k + 1)]
    rows.append(("Giáo viên QL 1", "Quản Lý", None, 4))
    return rows


def staff(k: int) -> list[Teacher]:
    """Nhân sự đánh số trong từng chức vụ theo thứ tự dòng, như khi đọc file vào (truong_mau.sample_staff)."""
    count: dict[str, int] = defaultdict(int)
    teachers = []
    for row, (name, title, class_name, lessons) in enumerate(staff_rows(k), start=2):
        role = normalize(title)
        index = None
        if class_name is None:
            count[role] += 1
            index = count[role]
        teachers.append(make_teacher(name, role, index, class_name, lessons, row=row, label=clean_name(title)))
    return teachers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ghi file vào của trường mẫu tên giả gấp k lần")
    parser.add_argument("k", type=int, help="gấp mấy lần trường mẫu 29 lớp (>= 1)")
    parser.add_argument("output", type=Path, help="file .xlsx ghi ra")
    args = parser.parse_args(argv)
    if args.k < 1:
        parser.error("k phải >= 1")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_staff_template(args.output, staff(args.k), CURRICULUM)
    rows = staff_rows(args.k)
    print(f"Đã ghi {args.output}: {sum(1 for r in rows if r[2])} lớp, {len(rows)} nhân sự")
    return 0


if __name__ == "__main__":
    sys.exit(main())
