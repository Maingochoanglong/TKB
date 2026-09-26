"""Chạy: python -m tkb <file vào.xlsx> [-o TKB.xlsx] [--program chương trình.xlsx] ..."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import config
from .checker import check
from .program import load_curriculum
from .solver import SolveError, ortools_version, solve
from .staff import InputError, read_staff
from .style import Style
from .writer import write_statistics, write_timetable, write_updated_staff


def use_utf8_output() -> None:
    """In tiếng Việt không lỗi khi output bị chuyển hướng trên Windows (mặc định bảng mã cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    ap = argparse.ArgumentParser(prog="python -m tkb", description="Xếp thời khóa biểu tự động")
    ap.add_argument("staff", help="File vào: sheet NHÂN SỰ và sheet CHƯƠNG TRÌNH HỌC")
    ap.add_argument("-o", "--output", default="out/TKB.xlsx",
                    help="File TKB xuất ra, chỉ gồm các sheet Khối (mặc định out/TKB.xlsx)")
    ap.add_argument("--staff-out", help="File nhân sự cập nhật (mặc định <thư mục output>/<tên input>_cap_nhat.xlsx)")
    ap.add_argument("--stats-out", help="File nhân sự và thống kê (mặc định <thư mục output>/Thong_Ke.xlsx)")
    ap.add_argument("--program", help="File chương trình học riêng (mặc định: sheet CHƯƠNG TRÌNH HỌC của file vào)")
    ap.add_argument("--time-limit", type=float, default=240,
                    help="Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 240; 0 = không giới hạn)")
    ap.add_argument("--non-reproducible", action="store_true",
                    help="Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau")
    ap.add_argument("--workers", type=int, default=8, help="Số luồng CP-SAT (mặc định 8)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mode", choices=config.MODES, default=config.MODE_HIRE,
                    help="Khi thiếu người: tuyen_them = thêm GV \"chưa có\"; bu_gio = GVCN/bộ môn dạy bù "
                         "(mặc định tuyen_them)")
    ap.add_argument("--max-overtime", type=int, default=config.OVERTIME_MAX,
                    help=f"Chế độ bù giờ: số tiết bù tối đa mỗi người (mặc định {config.OVERTIME_MAX})")
    ap.add_argument("--no-student-rules", action="store_true",
                    help="Tắt luật bảo vệ học sinh (tối đa 2 tiết TV, 2 tiết Toán mỗi buổi; môn có từ 2 tiết "
                         "trong buổi phải học liền nhau)")
    args = ap.parse_args(argv)

    if args.max_overtime < 0:
        ap.error("--max-overtime phải >= 0")
    if args.time_limit < 0:
        ap.error("--time-limit phải >= 0 (0 = không giới hạn)")
    settings = config.Settings(student_rules=not args.no_student_rules,
                               mode=args.mode, overtime_max=args.max_overtime,
                               time_limit=args.time_limit or None, workers=args.workers, seed=args.seed,
                               reproducible=not args.non_reproducible)
    if settings.reproducible and ortools_version() != config.ORTOOLS_VERSION:
        print(f"CẢNH BÁO: đang dùng OR-Tools {ortools_version()}, khác bản {config.ORTOOLS_VERSION} đã ghim; kết quả "
              f"có thể khác máy khác. Cài đúng bản bằng:  pip install -r requirements.txt", file=sys.stderr)
    try:
        curriculum, source = load_curriculum(args.staff, args.program)
        staff = read_staff(args.staff, subjects=[s for req in curriculum.values() for s in req])
        n_subjects = len({s for req in curriculum.values() for s in req})
        print(f"Đọc {len(staff)} nhân sự, {sum(1 for t in staff if t.class_name)} lớp; "
              f"chương trình học ({n_subjects} môn): {source}.")
        solution = solve(staff, curriculum, settings)
    except (InputError, SolveError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1

    errors = check(solution.problem, solution.lessons, settings.student_rules)
    output = Path(args.output)
    staff_out = Path(args.staff_out) if args.staff_out else output.parent / f"{Path(args.staff).stem}_cap_nhat.xlsx"
    style = Style.from_file(args.staff)  # các file ra dùng style của file vào
    write_timetable(solution, output, style)
    write_updated_staff(solution, args.staff, staff_out)
    stats_out = Path(args.stats_out) if args.stats_out else output.parent / "Thong_Ke.xlsx"
    write_statistics(solution, stats_out, style, errors, solution.problem.warnings)

    load = solution.teacher_load()
    extra = solution.used_supplements()
    print(f"Kết quả: {solution.status}, kiểm tra luật bắt buộc: {'ĐẠT' if not errors else 'KHÔNG ĐẠT'}")
    print(f"Mã kết quả: {solution.fingerprint()} (cùng mã là cùng TKB; xếp giờ mất {solution.wall_time:.0f} giây)")
    if extra:
        print(f"Cần bổ sung {len(extra)} GV cho {sum(load[t.title] for t in extra)} tiết thiếu:")
        for t in extra:
            print(f"  {t.name} | {t.title} | {t.max_lessons} tiết (thực dạy {load[t.title]})")
    else:
        print("Không cần bổ sung giáo viên.")
    if solution.problem.overtime_mode():
        overtime = solution.overtime()
        teachers = solution.problem.teachers
        homeroom = {g: n for g, n in overtime.items() if teachers[g].class_name}
        general = {g: n for g, n in overtime.items() if not teachers[g].class_name}
        print(f"Dạy bù {sum(overtime.values())} tiết: GVCN {sum(homeroom.values())} tiết ({len(homeroom)} người), "
              f"bộ môn {sum(general.values())} tiết ({len(general)} người)")
        levels = Counter(overtime.values())
        if levels:
            print("  " + ", ".join(f"{levels[k]} người bù +{k}" for k in sorted(levels, reverse=True)))
    late = sum(1 for les in solution.lessons
               if les.subject in config.HEAVY_SUBJECTS and les.period in config.HEAVY_LATE_PERIODS)
    print(f"Môn nặng ở tiết {', '.join(map(str, sorted(config.HEAVY_LATE_PERIODS)))}: {late} tiết "
          f"(mục tiêu mềm, càng ít càng tốt)")
    for e in errors[:20]:
        print(f"  LỖI: {e}")
    print(f"Đã ghi: {output}")
    print(f"Đã ghi: {staff_out}")
    print(f"Đã ghi: {stats_out}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
