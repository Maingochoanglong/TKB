"""Chạy: python -m tkb <file nhân sự.xlsx> [-o TKB.xlsx] [--program chương trình.xlsx] ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .checker import check
from .program import read_program
from .solver import SolveError, solve
from .staff import InputError, read_staff
from .writer import write_timetable, write_updated_staff


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tkb", description="Xếp thời khóa biểu tự động")
    ap.add_argument("staff", help="File Excel danh sách nhân sự (cột Tên, Chức vụ, Số tiết)")
    ap.add_argument("-o", "--output", default="out/TKB.xlsx", help="File TKB xuất ra (mặc định out/TKB.xlsx)")
    ap.add_argument("--staff-out", help="File nhân sự cập nhật (mặc định <thư mục output>/<tên input>_cap_nhat.xlsx)")
    ap.add_argument("--program", help="File chương trình học (mặc định dùng chương trình trong tkb/config.py)")
    ap.add_argument("--time-limit", type=float, default=240,
                    help="Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 240)")
    ap.add_argument("--non-reproducible", action="store_true",
                    help="Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau")
    ap.add_argument("--workers", type=int, default=8, help="Số luồng CP-SAT (mặc định 8)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-student-rules", action="store_true",
                    help="Tắt luật bảo vệ học sinh (tối đa 2 tiết TV, 2 tiết Toán mỗi buổi)")
    args = ap.parse_args(argv)

    settings = config.Settings(student_rules=not args.no_student_rules,
                               time_limit=args.time_limit, workers=args.workers, seed=args.seed,
                               reproducible=not args.non_reproducible)
    try:
        staff = read_staff(args.staff)
        curriculum = read_program(args.program) if args.program else None
        print(f"Đọc {len(staff)} nhân sự, {sum(1 for t in staff if t.class_name)} lớp.")
        solution = solve(staff, curriculum, settings)
    except (InputError, SolveError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1

    errors = check(solution.problem, solution.lessons, settings.student_rules)
    output = Path(args.output)
    staff_out = Path(args.staff_out) if args.staff_out else output.parent / f"{Path(args.staff).stem}_cap_nhat.xlsx"
    write_timetable(solution, output, errors, solution.problem.warnings)
    write_updated_staff(solution, args.staff, staff_out)

    load = solution.teacher_load()
    extra = solution.used_supplements()
    print(f"Kết quả: {solution.status}, kiểm tra luật bắt buộc: {'ĐẠT' if not errors else 'KHÔNG ĐẠT'}")
    if extra:
        print(f"Cần bổ sung {len(extra)} GV cho {sum(load[t.title] for t in extra)} tiết thiếu:")
        for t in extra:
            print(f"  {t.name} | {t.title} | {t.max_lessons} tiết (thực dạy {load[t.title]})")
    else:
        print("Không cần bổ sung giáo viên.")
    for e in errors[:20]:
        print(f"  LỖI: {e}")
    print(f"Đã ghi: {output}")
    print(f"Đã ghi: {staff_out}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
