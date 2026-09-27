"""Chạy: python -m tkb <file vào.xlsx> [-o TKB.xlsx] ..."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import config
from .checker import check
from .program import read_program
from .solver import ShortageError, SolveError, ortools_version, solve
from .staff import InputError, read_staff
from .style import Style
from .writer import write_shortage, write_statistics, write_timetable, write_updated_staff


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
    ap.add_argument("--stats-out", help="File thống kê số tiết từng môn của mỗi giáo viên; chế độ bù giờ mà thiếu "
                                        "tiết thì là bảng tiết thiếu (mặc định <thư mục output>/Thong_Ke.xlsx)")
    ap.add_argument("--roles-out", help="File TKB ghi thêm chức vụ (Mã GV) trong mỗi ô "
                                        "(mặc định <thư mục output>/TKB_chuc_vu.xlsx)")
    ap.add_argument("--time-limit", type=float, default=480,
                    help="Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 480; 0 = không giới hạn)")
    ap.add_argument("--non-reproducible", action="store_true",
                    help="Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau")
    ap.add_argument("--workers", type=int, default=8, help="Số luồng CP-SAT (mặc định 8)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mode", choices=config.MODES, default=config.MODE_HIRE,
                    help="Khi thiếu người: bu_gio = GVCN/bộ môn dạy bù, bù không đủ thì báo lỗi; tuyen_them = "
                         "thêm GV \"chưa có\" dạy đúng các ô bù (cùng TKB với bu_gio) và phần còn thiếu "
                         "(mặc định tuyen_them)")
    ap.add_argument("--max-overtime", type=int, default=config.OVERTIME_MAX,
                    help=f"Số tiết bù tối đa mỗi người; chế độ tuyển: người mới nhận các tiết bù này "
                         f"(mặc định {config.OVERTIME_MAX})")
    ap.add_argument("--no-student-rules", action="store_true",
                    help="Tắt luật bảo vệ học sinh (mỗi nhóm môn tối đa 2 tiết mỗi buổi; Toán mỗi ngày 1 tiết; "
                         "TV ghép cặp 2 tiết liền; môn có từ 2 tiết trong buổi phải học liền nhau)")
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
    output = Path(args.output)
    staff_out = Path(args.staff_out) if args.staff_out else output.parent / f"{Path(args.staff).stem}_cap_nhat.xlsx"
    stats_out = Path(args.stats_out) if args.stats_out else output.parent / "Thong_Ke.xlsx"
    roles_out = Path(args.roles_out) if args.roles_out else output.parent / "TKB_chuc_vu.xlsx"
    try:
        curriculum = read_program(args.staff)
        staff = read_staff(args.staff, subjects=[s for req in curriculum.values() for s in req])
        n_subjects = len({s for req in curriculum.values() for s in req})
        print(f"Đọc {len(staff)} nhân sự, {sum(1 for t in staff if t.class_name)} lớp; "
              f"chương trình học: {n_subjects} môn (sheet {config.PROGRAM_SHEET}).")
        solution = solve(staff, curriculum, settings)
    except ShortageError as exc:
        rows = exc.rows()
        print(f"LỖI: {exc}. Không xếp TKB. Các tiết không ai dạy được:", file=sys.stderr)
        for cls, subject, n, reason in rows:
            print(f"  Lớp {cls}: {subject} thiếu {n} tiết ({reason})", file=sys.stderr)
        print("Cách sửa: tăng số tiết bù tối đa, sửa định mức/nhân sự trong file vào, hoặc chạy chế độ tuyen_them.",
              file=sys.stderr)
        write_shortage(rows, stats_out, Style.from_file(args.staff))
        print(f"Đã ghi: {stats_out}")
        return 3
    except (InputError, SolveError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1

    errors = check(solution.problem, solution.lessons, settings.student_rules)
    style = Style.from_file(args.staff)  # các file ra dùng style của file vào
    write_timetable(solution, output, style)
    write_timetable(solution, roles_out, style, with_codes=True)
    write_updated_staff(solution, args.staff, staff_out)
    write_statistics(solution, stats_out, style)

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
    core = [les for les in solution.lessons if les.subject in config.MORNING_SUBJECTS]
    if core:
        names = ", ".join(solution.problem.subject_label(s) for s in sorted(config.MORNING_SUBJECTS)
                          if any(les.subject == s for les in core))
        afternoon = sum(1 for les in core if les.period not in config.MORNING.periods)
        print(f"{names} ở buổi chiều: {afternoon}/{len(core)} tiết (mục tiêu mềm: dành buổi sáng cho các môn này)")
    for e in errors[:20]:
        print(f"  LỖI: {e}")
    print(f"Đã ghi: {output}")
    print(f"Đã ghi: {roles_out}")
    print(f"Đã ghi: {staff_out}")
    print(f"Đã ghi: {stats_out}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
