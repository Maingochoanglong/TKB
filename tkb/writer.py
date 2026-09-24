"""Xuất TKB ra Excel: sheet Khối, Danh sách nhân sự, Thống kê và file nhân sự cập nhật."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import config
from .solver import Solution
from .staff import Teacher, _find_columns, class_sort_key

THIN = Side(style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
# Định dạng theo Output_Template_TKB_V5_Formatted.xlsx
FONT_NAME = "Times New Roman"
FONT_SIZE = 10
NORMAL = Font(name=FONT_NAME, size=FONT_SIZE)
BOLD = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
TITLE_FONT = Font(name=FONT_NAME, size=12, bold=True)
HEADER_FONT = BOLD
HEADER_FILL = PatternFill("solid", fgColor="F0F0F0")
LESSON_ROW_HEIGHT = 28
COLUMN_WIDTHS = {"class": 8, "session": 8, "period": 6, "day": 25}

BLOCK_GAP = 2  # số dòng trống giữa hai lớp (giống template)


def subject_label(subject: str) -> str:
    return config.DISPLAY_NAMES.get(subject, subject)


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
    for grade in sorted({int(c.split("/")[0]) for c in problem.classes}):
        ws = wb.create_sheet(f"Khối {grade}")
        ws.column_dimensions["A"].width = COLUMN_WIDTHS["class"]
        ws.column_dimensions["B"].width = COLUMN_WIDTHS["session"]
        ws.column_dimensions["C"].width = COLUMN_WIDTHS["period"]
        for i in range(len(days)):
            ws.column_dimensions[get_column_letter(first_day_col + i)].width = COLUMN_WIDTHS["day"]
        classes = sorted((c for c in problem.classes if int(c.split("/")[0]) == grade), key=class_sort_key)
        top = 1
        for cls in classes:
            header = ["LỚP", "BUỔI", "TIẾT", *[config.DAYS[d].upper() for d in days]]
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
                ws.row_dimensions[r].height = LESSON_ROW_HEIGHT
                _style(ws.cell(r, 3, number))
                for i, d in enumerate(days):
                    cell = ws.cell(r, first_day_col + i)
                    _style(cell)
                    if period not in day_periods[d]:
                        cell.value = config.OFF_LABEL
                        continue
                    les = grid.get((cls, d, period))
                    if les is not None:
                        cell.value = f"{subject_label(les.subject)}\n{les.teacher}"
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


def _staff_sheet(wb, solution: Solution) -> None:
    ws = wb.create_sheet("Danh sách nhân sự")
    load = solution.teacher_load()
    rows = []
    for t in staff_rows(solution):
        spare = t.max_lessons - load[t.title]
        if t.supplementary:
            note = "Cần tuyển bổ sung" + (f", còn dư {spare} tiết" if spare > 0 else "")
        else:
            note = f"Còn dư {spare} tiết" if spare > 0 else ""
        # Người bổ sung được tuyển theo định mức đầy đủ của chức vụ (vd bộ môn 23 tiết).
        rows.append([t.name, t.title, t.max_lessons, load[t.title], note])
    _write_table(ws, 1, "DANH SÁCH NHÂN SỰ (đã cập nhật)",
                 ["Tên", "Chức vụ", "Số tiết", "Số tiết thực dạy", "Ghi chú"], rows)
    for col, width in zip("ABCDE", (30, 22, 10, 16, 36)):
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
        rows.append([role, len(real), cap, used, cap - used, sum(load[t.title] for t in extra), len(extra)])
    return rows


def _stats_sheet(wb, solution: Solution, errors: list[str], warnings: list[str]) -> None:
    ws = wb.create_sheet("Thống kê")
    problem = solution.problem
    load = solution.teacher_load()
    row = 1
    ws.cell(row, 1, "THỐNG KÊ XẾP THỜI KHÓA BIỂU").font = Font(name=FONT_NAME, size=14, bold=True)
    row += 1
    info = [
        ("Kiểm tra luật bắt buộc", "ĐẠT" if not errors else f"KHÔNG ĐẠT ({len(errors)} lỗi)"),
        ("Trạng thái solver", f"{solution.status} ({solution.stage})"),
        ("Thời gian xếp giờ (giây)", round(solution.wall_time, 1)),
        ("Số lớp", len(problem.classes)),
        ("Tổng số tiết/tuần", len(solution.lessons)),
        ("Tổng số tiết thiếu (giao cho GV bổ sung)", sum(load[t.title] for t in solution.used_supplements())),
        ("Số GV cần bổ sung", len(solution.used_supplements())),
    ]
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
    row = _write_table(ws, row, "1. CHỨC VỤ THIẾU VÀ SỐ TIẾT THIẾU (GV bổ sung \"chưa có\")",
                       ["Chức vụ", "Tên", "Số tiết thiếu", "Chi tiết (lớp môn × số tiết)"], sup_rows)

    row = _write_table(ws, row, "2. THEO NHÓM CHỨC VỤ",
                       ["Chức vụ", "Số GV hiện có", "Tổng định mức", "Đã dạy", "Dư (chưa dùng)",
                        "Tiết thiếu", "Số GV bổ sung"], role_summary(solution))

    days = sorted(config.DAY_SESSIONS)
    per_day = daily_loads(solution)
    classes_of: dict[str, set] = defaultdict(set)
    for les in solution.lessons:
        classes_of[les.teacher].add(les.class_name)
    load_rows = []
    for t in staff_rows(solution):
        load_rows.append([t.title, t.name, t.max_lessons, load[t.title], t.max_lessons - load[t.title],
                          *[per_day[t.title][d] for d in days], len(classes_of[t.title])])
    row = _write_table(ws, row, "3. TẢI TỪNG GIÁO VIÊN",
                       ["Chức vụ", "Tên", "Định mức", "Thực dạy", "Dư", *[config.DAYS[d] for d in days],
                        "Số lớp dạy"], load_rows)

    if errors:
        row = _write_table(ws, row, "4. LỖI KIỂM TRA", ["Lỗi"], [[e] for e in errors])

    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 30
    for col in "CDEFGHIJK":
        ws.column_dimensions[col].width = 14
    ws.column_dimensions["D"].width = 60  # cột chi tiết của bảng 1


def write_timetable(solution: Solution, path: str | Path, errors: list[str], warnings: list[str]) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _grade_sheets(wb, solution)
    _staff_sheet(wb, solution)
    _stats_sheet(wb, solution, errors, warnings)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_updated_staff(solution: Solution, source: str | Path, path: str | Path) -> None:
    """Chép file nhân sự gốc và thêm các GV bổ sung ("chưa có") vào cuối danh sách."""
    wb = openpyxl.load_workbook(source)
    ws = wb.worksheets[0]
    _, cols = _find_columns(ws)
    last = max((r for r in range(1, ws.max_row + 1)
                if ws.cell(r, cols["title"]).value not in (None, "")), default=1)
    for i, t in enumerate(solution.used_supplements(), start=1):
        r = last + i
        ws.cell(r, cols["name"], t.name)
        ws.cell(r, cols["title"], t.title)
        ws.cell(r, cols["lessons"], t.max_lessons)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
