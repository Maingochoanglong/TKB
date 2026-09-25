"""Xuất TKB ra Excel: sheet Khối, Danh sách nhân sự, Thống kê và file nhân sự cập nhật."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import config
from .solver import Solution
from .staff import Teacher, _find_columns, class_sort_key, staff_sheet

THIN = Side(style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
# Định dạng theo Output_Template_TKB_V5_Formatted.xlsx, cỡ chữ phóng to cho dễ đọc.
FONT_NAME = "Times New Roman"
FONT_SIZE = 14
NORMAL = Font(name=FONT_NAME, size=FONT_SIZE)
BOLD = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
TITLE_FONT = Font(name=FONT_NAME, size=FONT_SIZE + 2, bold=True)
HEADER_FONT = BOLD
HEADER_FILL = PatternFill("solid", fgColor="F0F0F0")
LESSON_ROW_HEIGHT = 42  # tối thiểu 2 dòng (môn + tên giáo viên) ở cỡ chữ 14
LINE_HEIGHT = 21  # chiều cao mỗi dòng chữ cỡ 14
HEADER_ROW_HEIGHT = 24
COLUMN_WIDTHS = {"class": 11, "session": 11, "period": 8, "day": 24}  # "day": độ rộng tối thiểu
MAX_DAY_WIDTH = 30  # tên dài hơn thì xuống dòng

BLOCK_GAP = 2  # số dòng trống giữa hai lớp (giống template)


def subject_label(subject: str) -> str:
    return config.DISPLAY_NAMES.get(subject, subject)


def teacher_labels(teachers: dict[str, Teacher]) -> dict[str, str]:
    """Chức vụ -> tên hiển thị dưới tên môn trong TKB.

    Ghi tên giáo viên; người bổ sung ("chưa có"), tên trùng nhau hoặc để trống thì kèm/ghi chức vụ.
    """
    counts = Counter(t.name.strip() for t in teachers.values())
    labels = {}
    for title, t in teachers.items():
        name = t.name.strip()
        if not name:
            labels[title] = title
        elif t.supplementary or counts[name] > 1:
            labels[title] = f"{name} ({title})"
        else:
            labels[title] = name
    return labels


def _text_width(text: str) -> float:
    """Độ rộng ước lượng (đơn vị cột Excel) của một dòng chữ Times New Roman cỡ 14."""
    return len(text) * 1.2 + 2


def _lines(text: str, width: float) -> int:
    return max(1, math.ceil(_text_width(text) / width))


def session_rows() -> list[tuple[config.Session, int, int]]:
    """Các hàng của bảng TKB: (buổi, tiết trong ngày, số thứ tự tiết trong buổi)."""
    sessions: dict[str, config.Session] = {}
    for d in sorted(config.DAY_SESSIONS):
        for s in config.DAY_SESSIONS[d]:
            sessions.setdefault(s.name, s)
    ordered = sorted(sessions.values(), key=lambda s: s.periods[0])
    return [(s, p, i) for s in ordered for i, p in enumerate(s.periods, start=1)]


def _style(cell, font=NORMAL, fill=None, align=CENTER):
    cell.border = BORDER
    cell.alignment = align
    cell.font = font
    if fill:
        cell.fill = fill


def _merge(ws, r1: int, c1: int, r2: int, c2: int, value, font=BOLD) -> None:
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            _style(ws.cell(r, c), font)
    ws.cell(r1, c1, value)
    if (r1, c1) != (r2, c2):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


def _grade_sheets(wb, solution: Solution) -> None:
    grid = {(l.class_name, l.day, l.period): l for l in solution.lessons}
    days = sorted(config.DAY_SESSIONS)
    rows = session_rows()
    day_periods = {d: {p for s in config.DAY_SESSIONS[d] for p in s.periods} for d in days}
    first_day_col = 4
    problem = solution.problem
    names = teacher_labels(problem.teachers)
    for grade in sorted({int(c.split("/")[0]) for c in problem.classes}):
        ws = wb.create_sheet(f"Khối {grade}")
        texts = [t for les in solution.lessons if int(les.class_name.split("/")[0]) == grade
                 for t in (subject_label(les.subject), names[les.teacher])]
        day_width = min(MAX_DAY_WIDTH, max([COLUMN_WIDTHS["day"], *map(_text_width, texts)]))
        ws.column_dimensions["A"].width = COLUMN_WIDTHS["class"]
        ws.column_dimensions["B"].width = COLUMN_WIDTHS["session"]
        ws.column_dimensions["C"].width = COLUMN_WIDTHS["period"]
        for i in range(len(days)):
            ws.column_dimensions[get_column_letter(first_day_col + i)].width = day_width
        # In: khổ ngang, co vừa 1 trang theo chiều rộng.
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        classes = sorted((c for c in problem.classes if int(c.split("/")[0]) == grade), key=class_sort_key)
        top = 1
        for cls in classes:
            header = ["LỚP", "BUỔI", "TIẾT", *[config.DAYS[d].upper() for d in days]]
            ws.row_dimensions[top].height = HEADER_ROW_HEIGHT
            for col, text in enumerate(header, start=1):
                _style(ws.cell(top, col, text), HEADER_FONT, HEADER_FILL)
            first = top + 1
            _merge(ws, first, 1, first + len(rows) - 1, 1, f"LỚP {cls}")
            r = first
            for session in dict.fromkeys(s for s, _, _ in rows):
                n = sum(1 for s, _, _ in rows if s is session)
                _merge(ws, r, 2, r + n - 1, 2, session.name.upper())
                r += n
            for j, (_, period, number) in enumerate(rows):
                r = first + j
                lines = 2
                _style(ws.cell(r, 3, number))
                for i, d in enumerate(days):
                    cell = ws.cell(r, first_day_col + i)
                    _style(cell)
                    if period not in day_periods[d]:
                        cell.value = config.OFF_LABEL
                        continue
                    les = grid.get((cls, d, period))
                    if les is not None:
                        subject, name = subject_label(les.subject), names[les.teacher]
                        cell.value = f"{subject}\n{name}"
                        lines = max(lines, _lines(subject, day_width) + _lines(name, day_width))
                ws.row_dimensions[r].height = max(LESSON_ROW_HEIGHT, LINE_HEIGHT * lines)
            top = first + len(rows) + BLOCK_GAP


def _write_table(ws, row: int, title: str, header: list[str], rows: list[list]) -> int:
    ws.cell(row, 1, title).font = TITLE_FONT
    row += 1
    for i, h in enumerate(header, start=1):
        _style(ws.cell(row, i, h), HEADER_FONT, HEADER_FILL)
    for values in rows:
        row += 1
        for i, v in enumerate(values, start=1):
            _style(ws.cell(row, i, v), align=LEFT if isinstance(v, str) else CENTER)
    return row + 2


def daily_loads(solution: Solution) -> dict[str, Counter]:
    per: dict[str, Counter] = defaultdict(Counter)
    for les in solution.lessons:
        per[les.teacher][les.day] += 1
    return per


def staff_rows(solution: Solution) -> list[Teacher]:
    """GV thật theo thứ tự file gốc, sau đó GV bổ sung được dùng."""
    real = [t for t in solution.problem.teachers.values() if not t.supplementary]
    real.sort(key=lambda t: (t.row is None, t.row or 0))
    return real + solution.used_supplements()


def mode_label(problem) -> str:
    if not problem.overtime_mode():
        return "Tuyển thêm (thiếu người thì thêm GV \"chưa có\")"
    return (f"Bù giờ (GVCN, bộ môn bù tối đa {problem.overtime_max} tiết/người, "
            f"người hưởng thai sản không bù)")


def overtime_details(solution: Solution) -> dict[str, str]:
    """GVCN -> các môn dạy bù ở lớp mình, vd "TV tăng cường ×2"."""
    problem = solution.problem
    result = {}
    for g in solution.overtime():
        t = problem.teachers[g]
        if not t.class_name:
            continue
        got = Counter(les.subject for les in solution.lessons
                      if les.teacher == g and les.class_name == t.class_name)
        extra = got - Counter(problem.homeroom_take.get(t.class_name, {}))
        result[g] = "; ".join(f"{subject_label(s)} ×{n}" for s, n in sorted(extra.items()))
    return result


def _staff_sheet(wb, solution: Solution) -> None:
    ws = wb.create_sheet("Danh sách nhân sự")
    load = solution.teacher_load()
    overtime = solution.overtime()
    with_ot = solution.problem.overtime_mode()
    rows = []
    for t in staff_rows(solution):
        spare = t.max_lessons - load[t.title]
        if t.supplementary:
            note = "Cần tuyển bổ sung" + (f", còn dư {spare} tiết" if spare > 0 else "")
        else:
            note = f"Còn dư {spare} tiết" if spare > 0 else ""
        # Người bổ sung được tuyển theo định mức đầy đủ của chức vụ (vd bộ môn 23 tiết).
        row = [t.name, t.title, t.max_lessons, load[t.title]]
        if with_ot:
            row.append(overtime.get(t.title))
        rows.append(row + [note])
    header = ["Tên", "Chức vụ", "Số tiết", "Số tiết thực dạy"] + (["Số tiết bù"] if with_ot else []) + ["Ghi chú"]
    _write_table(ws, 1, "DANH SÁCH NHÂN SỰ (đã cập nhật)", header, rows)
    widths = (38, 26, 12, 22) + ((16,) if with_ot else ()) + (46,)
    for col, width in zip("ABCDEF", widths):
        ws.column_dimensions[col].width = width


def role_summary(solution: Solution) -> list[list]:
    problem = solution.problem
    load = solution.teacher_load()
    roles = [config.ROLE_HOMEROOM, config.ROLE_GENERAL, *config.SPECIALIST_ROLES, config.ROLE_MANAGER]
    rows = []
    for role in roles:
        real = [t for t in problem.teachers.values() if t.role == role and not t.supplementary]
        extra = [t for t in solution.used_supplements() if t.role == role]
        if not real and not extra:
            continue
        cap = sum(t.max_lessons for t in real)
        used = sum(load[t.title] for t in real)
        spare = sum(max(0, t.max_lessons - load[t.title]) for t in real)
        row = [role, len(real), cap, used, spare]
        if problem.overtime_mode():
            row.append(sum(max(0, load[t.title] - t.max_lessons) for t in real))
        rows.append(row + [sum(load[t.title] for t in extra), len(extra)])
    return rows


def _stats_sheet(wb, solution: Solution, errors: list[str], warnings: list[str]) -> None:
    ws = wb.create_sheet("Thống kê")
    problem = solution.problem
    load = solution.teacher_load()
    overtime = solution.overtime()
    with_ot = problem.overtime_mode()
    row = 1
    ws.cell(row, 1, "THỐNG KÊ XẾP THỜI KHÓA BIỂU").font = Font(name=FONT_NAME, size=FONT_SIZE + 4, bold=True)
    row += 1
    info = [
        ("Chế độ", mode_label(problem)),
        ("Kiểm tra luật bắt buộc", "ĐẠT" if not errors else f"KHÔNG ĐẠT ({len(errors)} lỗi)"),
        ("Trạng thái solver", f"{solution.status} ({solution.stage})"),
        ("Thời gian xếp giờ (giây)", round(solution.wall_time, 1)),
        ("Số lớp", len(problem.classes)),
        ("Tổng số tiết/tuần", len(solution.lessons)),
        ("Tổng số tiết thiếu (giao cho GV bổ sung)", sum(load[t.title] for t in solution.used_supplements())),
        ("Số GV cần bổ sung", len(solution.used_supplements())),
    ]
    if with_ot:
        info.append(("Tổng số tiết dạy bù", sum(overtime.values())))
    for k, v in info + [("Ghi chú", note) for note in solution.notes + warnings]:
        ws.cell(row, 1, k).font = BOLD
        ws.cell(row, 2, v).font = NORMAL
        ws.cell(row, 2).alignment = Alignment(horizontal="left")
        row += 1
    row += 1

    details: dict[str, Counter] = defaultdict(Counter)
    for les in solution.lessons:
        details[les.teacher][(les.class_name, les.subject)] += 1
    sup_rows = []
    for t in solution.used_supplements():
        items = sorted(details[t.title].items(), key=lambda kv: (class_sort_key(kv[0][0]), kv[0][1]))
        text = "; ".join(f"{c} {subject_label(s)} ×{n}" for (c, s), n in items)
        sup_rows.append([t.title, t.name, load[t.title], text])
    if sup_rows:
        sup_rows.append(["Tổng", "", sum(r[2] for r in sup_rows), ""])
    else:
        sup_rows.append(["(không thiếu)", "", 0, ""])
    number = iter(range(1, 10))
    row = _write_table(ws, row, f"{next(number)}. CHỨC VỤ THIẾU VÀ SỐ TIẾT THIẾU (GV bổ sung \"chưa có\")",
                       ["Chức vụ", "Tên", "Số tiết thiếu", "Chi tiết (lớp môn × số tiết)"], sup_rows)

    if with_ot:
        subjects = overtime_details(solution)
        # Cùng bố cục với bảng 1: cột D (rộng) là phần chi tiết.
        ot_rows = [[t.title, t.name, overtime[t.title], subjects.get(t.title, ""), t.max_lessons, load[t.title]]
                   for t in staff_rows(solution) if t.title in overtime]
        ot_rows.append(["Tổng", "", sum(overtime.values()), "", "", ""])
        row = _write_table(ws, row, f"{next(number)}. DẠY BÙ (vượt định mức)",
                           ["Chức vụ", "Tên", "Số tiết bù", "Môn bù (GVCN, lớp mình)", "Định mức", "Thực dạy"],
                           ot_rows)

    row = _write_table(ws, row, f"{next(number)}. THEO NHÓM CHỨC VỤ",
                       ["Chức vụ", "Số GV hiện có", "Tổng định mức", "Đã dạy", "Dư (chưa dùng)",
                        *(["Dạy bù"] if with_ot else []), "Tiết thiếu", "Số GV bổ sung"], role_summary(solution))

    days = sorted(config.DAY_SESSIONS)
    per_day = daily_loads(solution)
    classes_of: dict[str, set] = defaultdict(set)
    for les in solution.lessons:
        classes_of[les.teacher].add(les.class_name)
    load_rows = []
    for t in staff_rows(solution):
        load_rows.append([t.title, t.name, t.max_lessons, load[t.title], max(0, t.max_lessons - load[t.title]),
                          *([overtime.get(t.title, 0)] if with_ot else []),
                          *[per_day[t.title][d] for d in days], len(classes_of[t.title])])
    row = _write_table(ws, row, f"{next(number)}. TẢI TỪNG GIÁO VIÊN",
                       ["Chức vụ", "Tên", "Định mức", "Thực dạy", "Dư", *(["Bù"] if with_ot else []),
                        *[config.DAYS[d] for d in days], "Số lớp dạy"], load_rows)

    if errors:
        row = _write_table(ws, row, f"{next(number)}. LỖI KIỂM TRA", ["Lỗi"], [[e] for e in errors])

    ws.column_dimensions["A"].width = 54
    ws.column_dimensions["B"].width = 38
    for col in "CDEFGHIJKL":
        ws.column_dimensions[col].width = 18
    ws.column_dimensions["D"].width = 80  # cột chi tiết của bảng 1


def write_timetable(solution: Solution, path: str | Path, errors: list[str], warnings: list[str]) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _grade_sheets(wb, solution)
    _staff_sheet(wb, solution)
    _stats_sheet(wb, solution, errors, warnings)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


HIRE_LABEL = "tuyển thêm"  # tên của người cần tuyển trong file thống kê


def _stats_name(t: Teacher) -> str:
    return HIRE_LABEL if t.supplementary else t.name


def statistics_rows(solution: Solution) -> list[list]:
    """Tên | Chức vụ | Số tiết quy định | Số tiết bù | Số tiết thực dạy | Số tiết còn dư."""
    load = solution.teacher_load()
    overtime = solution.overtime()
    return [[_stats_name(t), t.title, t.max_lessons, overtime.get(t.title, 0), load[t.title],
             max(0, t.max_lessons - load[t.title])] for t in staff_rows(solution)]


def assignment_rows(solution: Solution) -> list[list]:
    """Phân công chuyên môn: Tên | Chức vụ | Lớp | Môn | Số tiết (theo thứ tự danh sách nhân sự)."""
    count = Counter((les.teacher, les.class_name, les.subject) for les in solution.lessons)
    subject_order = {s: i for i, s in enumerate(config.SUBJECTS)}
    rows = []
    for t in staff_rows(solution):
        items = sorted(((c, s, n) for (g, c, s), n in count.items() if g == t.title),
                       key=lambda x: (class_sort_key(x[0]), subject_order.get(x[1], len(subject_order))))
        rows += [[_stats_name(t), t.title, c, subject_label(s), n] for c, s, n in items]
    return rows


def daily_rows(solution: Solution) -> list[list]:
    """Tên | Chức vụ | số tiết từng ngày | Tổng."""
    per_day = daily_loads(solution)
    days = sorted(config.DAY_SESSIONS)
    return [[_stats_name(t), t.title, *[per_day[t.title][d] for d in days], sum(per_day[t.title].values())]
            for t in staff_rows(solution)]


def role_rows(solution: Solution) -> list[list]:
    """Chức vụ | Số người | Quy định | Thực dạy | Bù | Còn dư | Số người tuyển thêm | Số tiết tuyển thêm."""
    load = solution.teacher_load()
    overtime = solution.overtime()
    teachers = staff_rows(solution)
    rows = []
    for role in [config.ROLE_HOMEROOM, config.ROLE_GENERAL, *config.SPECIALIST_ROLES, config.ROLE_MANAGER]:
        real = [t for t in teachers if t.role == role and not t.supplementary]
        hired = [t for t in teachers if t.role == role and t.supplementary]
        if not real and not hired:
            continue
        rows.append([role, len(real), sum(t.max_lessons for t in real), sum(load[t.title] for t in real),
                     sum(overtime.get(t.title, 0) for t in real),
                     sum(max(0, t.max_lessons - load[t.title]) for t in real),
                     len(hired), sum(load[t.title] for t in hired)])
    return rows


def _stats_sheet_table(ws, title: str, header: list[str], rows: list[list], widths: tuple[int, ...],
                       total_from: int | None = None) -> None:
    """Bảng có tiêu đề, lọc, cố định dòng tiêu đề; total_from: cộng các cột từ vị trí này vào dòng Tổng."""
    data = [[i, *r] for i, r in enumerate(rows, start=1)]
    if total_from is not None:
        data.append([None, "Tổng", *[None] * (total_from - 2),
                     *[sum(r[c] for r in data) for c in range(total_from, len(header))]])
    last = _write_table(ws, 1, title, header, data) - 2
    if total_from is not None:
        for cell in ws[last]:
            cell.font = BOLD
    ws.auto_filter.ref = f"A2:{get_column_letter(len(header))}{last - (total_from is not None)}"
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A3"


def write_statistics(solution: Solution, path: str | Path) -> None:
    """File Excel thống kê giáo viên: số tiết, phân công, tải theo ngày, tổng hợp theo chức vụ."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Thống kê giáo viên"
    _stats_sheet_table(ws, "THỐNG KÊ SỐ TIẾT GIÁO VIÊN",
                       ["STT", "Tên giáo viên", "Chức vụ", "Số tiết quy định", "Số tiết bù", "Số tiết thực dạy",
                        "Số tiết còn dư"], statistics_rows(solution), (7, 38, 24, 20, 14, 20, 18), total_from=3)
    _stats_sheet_table(wb.create_sheet("Phân công"), "PHÂN CÔNG CHUYÊN MÔN",
                       ["STT", "Tên giáo viên", "Chức vụ", "Lớp", "Môn", "Số tiết"],
                       assignment_rows(solution), (7, 38, 24, 10, 22, 12))
    days = [config.DAYS[d] for d in sorted(config.DAY_SESSIONS)]
    _stats_sheet_table(wb.create_sheet("Theo ngày"), "SỐ TIẾT TỪNG NGÀY CỦA GIÁO VIÊN",
                       ["STT", "Tên giáo viên", "Chức vụ", *days, "Tổng"], daily_rows(solution),
                       (7, 38, 24, *[12] * len(days), 10), total_from=3)
    _stats_sheet_table(wb.create_sheet("Theo chức vụ"), "TỔNG HỢP THEO CHỨC VỤ",
                       ["STT", "Chức vụ", "Số người", "Số tiết quy định", "Số tiết thực dạy", "Số tiết bù",
                        "Số tiết còn dư", "Số người tuyển thêm", "Số tiết tuyển thêm"],
                       role_rows(solution), (7, 16, 12, 20, 20, 14, 18, 22, 22), total_from=2)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_updated_staff(solution: Solution, source: str | Path, path: str | Path) -> None:
    """Chép file nhân sự gốc và thêm các GV bổ sung ("chưa có") vào cuối danh sách.

    Mẫu V7 (có cột Lớp) ghi chức vụ không kèm số thứ tự, vd "Bộ Môn": khi đọc lại, chương trình tự
    đánh số tiếp theo (bộ môn 6, 7...). Mẫu cũ ghi đủ chức vụ, vd "bộ môn 6".
    """
    wb = openpyxl.load_workbook(source)
    ws = staff_sheet(wb)
    _, cols = _find_columns(ws)
    last = max((r for r in range(1, ws.max_row + 1)
                if ws.cell(r, cols["title"]).value not in (None, "")), default=1)
    v7 = "class" in cols
    for i, t in enumerate(solution.used_supplements(), start=1):
        r = last + i
        if "stt" in cols:  # STT: chép công thức (vd =ROW()-1) hoặc tăng số của dòng trên
            above = ws.cell(r - 1, cols["stt"]).value
            ws.cell(r, cols["stt"], above if isinstance(above, str) and above.startswith("=")
                    else above + 1 if isinstance(above, int) else None)
        ws.cell(r, cols["name"], t.name)
        ws.cell(r, cols["title"], config.ROLE_LABELS.get(t.role, t.role) if v7 else t.title)
        ws.cell(r, cols["lessons"], t.max_lessons)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
