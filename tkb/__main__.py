"""Chạy: python -m tkb <file vào.xlsx> [-o TKB.xlsx] ..."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import config
from .checker import check
from .program import read_program
from .rules import applied, changed, read_rules
from .rules import code as rules_code
from .solver import ShortageError, SolveError, ortools_version, reuse, solve
from .staff import InputError, grade_of, read_saved_timetable, read_staff
from .style import Style
from .writer import campus_paths, write_shortage, write_statistics, write_timetable, write_updated_staff


def use_utf8_output() -> None:
    """In tiếng Việt không lỗi khi output bị chuyển hướng trên Windows (mặc định bảng mã cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    ap = argparse.ArgumentParser(prog="python -m tkb", description="Xếp thời khóa biểu tự động")
    ap.add_argument("staff", help="File vào: sheet NHÂN SỰ, CHƯƠNG TRÌNH HỌC (kèm cột quy định của môn) và (không bắt buộc) QUY ĐỊNH")
    ap.add_argument("-o", "--output", default="out/TKB.xlsx",
                    help="File TKB xuất ra, chỉ gồm các sheet Khối (mặc định out/TKB.xlsx). Trường có lớp ở cơ sở 2 "
                         "thì tách thành <tên>_diem_chinh.xlsx (cơ sở 1) và <tên>_diem_phu.xlsx (cơ sở 2)")
    ap.add_argument("--staff-out", help="File nhân sự cập nhật (mặc định <thư mục output>/<tên input>_cap_nhat.xlsx)")
    ap.add_argument("--stats-out", help="File thống kê số tiết từng môn của mỗi giáo viên; chế độ bù giờ mà thiếu "
                                        "tiết thì là bảng tiết thiếu (mặc định <thư mục output>/Thong_Ke.xlsx)")
    ap.add_argument("--roles-out", help="File TKB ghi thêm chức vụ (Mã GV) trong mỗi ô "
                                        "(mặc định <thư mục output>/TKB_chuc_vu.xlsx; hai cơ sở thì tách như -o)")
    ap.add_argument("--time-limit", type=float, default=1200,
                    help="Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 1200; 0 = không giới hạn: xếp "
                         "lại từng vùng đến khi hết cải thiện)")
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
    ap.add_argument("--xep-lai", action="store_true",
                    help=f"File vào có sheet {config.SAVED_SHEET} (file vào cập nhật của lần chạy trước): bỏ qua TKB "
                         f"đó, xếp lại từ đầu. Mặc định dùng lại TKB đó nếu vẫn đúng mọi luật")
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
        rules = read_rules(args.staff, warn=lambda text: print(f"Cảnh báo: {text}"))
    except InputError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    if rules is None:
        print(f"Quy định: mặc định của chương trình (file vào không có cột quy định ở sheet {config.PROGRAM_SHEET}, "
              f"không có sheet {config.RULES_SHEET}).")
    else:
        diff = changed(rules)
        print("Quy định: đọc từ file vào" + (f", khác mặc định: {', '.join(diff)}." if diff else ", giống mặc định."))
    with applied(rules):  # quy định trong file vào thay giá trị mặc định trong tkb/config.py
        return _run(args, settings)


def _run(args, settings: config.Settings) -> int:
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
        solution = None
        saved = None if args.xep_lai else read_saved_timetable(args.staff)
        if saved is not None and saved.rules_code not in (None, rules_code()):
            print(f"Quy định đã sửa so với lúc xếp TKB lưu trong file vào (sheet {config.SAVED_SHEET}): xếp lại từ "
                  f"đầu theo quy định mới.")
            saved = None
        if saved is not None:
            solution, why = reuse(staff, curriculum, settings, saved.rows)
            if solution is not None:
                print(f"Dùng lại TKB đã xếp trong file vào (sheet {config.SAVED_SHEET}), không xếp lại. Muốn xếp lại "
                      f"từ đầu: đặt GIU_TKB_DA_XEP = False trong main.py (dòng lệnh: --xep-lai).")
            else:
                print(f"Không dùng lại được TKB đã xếp trong file vào (sheet {config.SAVED_SHEET}), xếp lại từ đầu:")
                for reason in why[:10]:
                    print(f"  {reason}")
                if len(why) > 10:
                    print(f"  ... và {len(why) - 10} lý do khác")
        if solution is None:
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
    timetables = []  # trường có hai cơ sở: mỗi loại TKB tách thành file điểm chính và file điểm phụ
    for base, with_codes in ((output, False), (roles_out, True)):
        for path, classes in campus_paths(base, solution.problem):
            write_timetable(solution, path, style, with_codes=with_codes, classes=classes)
            timetables.append(path)
    write_updated_staff(solution, args.staff, staff_out, settings)
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
    print_teacher_rules(solution)
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
    if config.CUSTOM_RULES:  # luật riêng ưu tiên: số lần không theo
        from .luat_rieng import soft_report
        for line in soft_report(solution.problem, solution.lessons):
            print(f"{line} (ưu tiên, càng ít càng tốt)")
    for e in errors[:20]:
        print(f"  LỖI: {e}")
    for path in timetables:
        print(f"Đã ghi: {path}")
    print(f"Đã ghi: {staff_out}")
    print(f"Đã ghi: {stats_out}")
    return 0 if not errors else 2


def print_teacher_rules(solution) -> None:
    """In số liệu các luật về GV: hai cơ sở, thai sản, buổi nghỉ, giữ phân công của TKB cũ (chỉ in khi file vào
    có dùng các cột đó)."""
    problem, lessons = solution.problem, solution.lessons
    teachers = problem.teachers
    if problem.campus2:
        both = {les.teacher for les in lessons if les.class_name in problem.campus2} & \
               {les.teacher for les in lessons if les.class_name not in problem.campus2}
        days = {}  # (GV, ngày) -> các cơ sở
        for les in lessons:
            days.setdefault((les.teacher, les.day), set()).add(les.class_name in problem.campus2)
        switch = [g for (g, _), cs in days.items() if len(cs) > 1]
        print(f"Cơ sở 2: {len(problem.campus2)} lớp; {len(both)} GV dạy ở cả hai cơ sở, mỗi buổi chỉ ở một cơ sở; "
              f"sáng một cơ sở, chiều cơ sở kia: {len(switch)} lần ({len(set(switch))} GV)")
    maternity = [t for t in teachers.values() if t.maternity]
    if maternity:
        load = solution.teacher_load()
        print(f"Thai sản: {len(maternity)} người, không dạy bù ("
              + ", ".join(f"{t.title} {load[t.title]}/{t.max_lessons} tiết" for t in maternity) + "), chỉ dạy cơ sở 2")
    off = [t for t in teachers.values() if t.off_sessions or t.off_any]
    if off:
        print(f"Buổi nghỉ theo nguyện vọng: {len(off)} người ({', '.join(t.title for t in off)})")
    kept = [les for les in lessons if teachers[les.teacher].history and not teachers[les.teacher].class_name]
    if kept:
        grade = sum(1 for les in kept
                    if grade_of(les.class_name) in {grade_of(c) for c in teachers[les.teacher].history})
        same = sum(1 for les in kept if les.class_name in teachers[les.teacher].history)
        people = len({les.teacher for les in kept})
        print(f"Giữ phân công TKB cũ ({people} GV có Lớp Đang Dạy): đúng khối cũ {grade}/{len(kept)} tiết, "
              f"đúng lớp cũ {same}/{len(kept)} tiết")


if __name__ == "__main__":
    sys.exit(main())
