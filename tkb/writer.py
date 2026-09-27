"""Xuất ra Excel: TKB (chỉ các sheet Khối); file thống kê (số tiết từng môn của mỗi giáo viên); file vào
cập nhật.

Style (phông, cỡ chữ, viền, căn lề, chiều cao dòng) chép từ file vào (xem tkb/style.py).
"""
from __future__ import annotations

from collections import Counter
from copy import copy
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter

from . import config
from .solver import Solution
from .staff import Teacher, _find_columns, class_sort_key, normalize, staff_sheet
from .style import CellStyle, Style

MAX_DAY_WIDTH = 30  # cột ngày trong TKB: tên dài hơn thì xuống dòng
BLOCK_GAP = 2  # số dòng trống giữa hai lớp (giống template)
LABEL_PAD = 4  # cột BUỔI, TIẾT của TKB: rộng thêm so với chữ dài nhất cho dễ nhìn
HIRE_LABEL = "tuyển thêm"  # tên của người cần tuyển trong file thống kê
CODE_HEADER = "Mã GV"
LOAD_HEADER = "Số Tiết Thực Dạy"
OVERTIME_HEADER = "Số Tiết Bù"
STATS_SHEET = "Thống kê"
SHORTAGE_SHEET = "Thiếu tiết"
TOTAL_HEADER = "Tổng Tiết"
# File thống kê: tô nền cả dòng để biết ai dạy bù (chế độ bù giờ), ai là người cần tuyển (chế độ tuyển thêm).
OVERTIME_FILL = "FFEB9C"  # vàng nhạt
HIRE_FILL = "C6EFCE"  # xanh lá nhạt
OVERTIME_LEGEND = "Dạy bù (vượt định mức)"
HIRE_LEGEND = "Cần tuyển thêm"


def teacher_labels(teachers: dict[str, Teacher], with_codes: bool = False) -> dict[str, str]:
    """Chức vụ -> tên hiển thị dưới tên môn trong TKB.

    Ghi tên giáo viên; tên để trống hoặc người cần tuyển thêm thì ghi Mã GV (vd "Bộ Môn 6"), tên trùng
    nhau thì kèm Mã GV. with_codes: thêm một dòng Mã GV dưới tên (file TKB có chức vụ).
    """
    counts = Counter(t.name.strip() for t in teachers.values() if t.name.strip())
    labels = {}
    for title, t in teachers.items():
        name = t.name.strip()
        if not name or t.supplementary:
            labels[title] = t.code
        elif with_codes:
            labels[title] = f"{name}\n{t.code}"
        elif counts[name] > 1:
            labels[title] = f"{name} ({t.code})"
        else:
            labels[title] = name
    return labels


def session_rows() -> list[tuple[config.Session, int]]:
    """Các hàng của bảng TKB: (buổi, tiết trong ngày). Cột TIẾT ghi tiết trong ngày: sáng 1–4, chiều 5–7."""
    sessions: dict[str, config.Session] = {}
    for d in sorted(config.DAY_SESSIONS):
        for s in config.DAY_SESSIONS[d]:
            sessions.setdefault(s.name, s)
    ordered = sorted(sessions.values(), key=lambda s: s.periods[0])
    return [(s, p) for s in ordered for p in s.periods]


def _merge(ws, style: Style, r1: int, c1: int, r2: int, c2: int, value) -> None:
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            style.body_cell(ws, r, c, None, bold=True)
    ws.cell(r1, c1, value)
    if (r1, c1) != (r2, c2):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


def _grade_sheets(wb, solution: Solution, style: Style, with_codes: bool = False) -> None:
    grid = {(l.class_name, l.day, l.period): l for l in solution.lessons}
    days = sorted(config.DAY_SESSIONS)
    rows = session_rows()
    day_periods = {d: {p for s in config.DAY_SESSIONS[d] for p in s.periods} for d in days}
    first_day_col = 4
    problem = solution.problem
    names = teacher_labels(problem.teachers, with_codes)
    header = ["LỚP", "BUỔI", "TIẾT", *[config.DAYS[d].upper() for d in days]]
    # Cột ngày: cùng độ rộng ở mọi sheet Khối, nới theo dòng dài nhất của cả trường (tối đa MAX_DAY_WIDTH).
    texts = {line for les in solution.lessons
             for t in (problem.subject_label(les.subject), names[les.teacher]) for line in t.split("\n")}
    day_width = min(MAX_DAY_WIDTH, max(style.text_width(t) for t in [*header[3:], config.OFF_LABEL, *texts]))
    for grade in sorted({int(c.split("/")[0]) for c in problem.classes}):
        ws = wb.create_sheet(f"Khối {grade}")
        classes = sorted((c for c in problem.classes if int(c.split("/")[0]) == grade), key=class_sort_key)
        widths = [max(style.text_width(t) for t in [header[0], *(f"LỚP {c}" for c in classes)]),
                  max(style.text_width(t) for t in [header[1], *(s.name.upper() for s, _ in rows)]) + LABEL_PAD,
                  style.text_width(header[2]) + LABEL_PAD]
        for i, width in enumerate(widths + [day_width] * len(days), start=1):
            ws.column_dimensions[get_column_letter(i)].width = round(width, 1)
        # In: khổ ngang, co vừa 1 trang theo chiều rộng.
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        top = 1
        for cls in classes:
            ws.row_dimensions[top].height = style.row_height
            for col, text in enumerate(header, start=1):
                style.header_cell(ws, top, col, text)
            first = top + 1
            _merge(ws, style, first, 1, first + len(rows) - 1, 1, f"LỚP {cls}")
            r = first
            for session in dict.fromkeys(s for s, _ in rows):
                n = sum(1 for s, _ in rows if s is session)
                _merge(ws, style, r, 2, r + n - 1, 2, session.name.upper())
                r += n
            for j, (_, period) in enumerate(rows):
                r = first + j
                lines = 2  # môn + tên giáo viên
                style.body_cell(ws, r, 3, period)
                for i, d in enumerate(days):
                    value = None
                    if period not in day_periods[d]:
                        value = config.OFF_LABEL
                    elif (les := grid.get((cls, d, period))) is not None:
                        value = f"{problem.subject_label(les.subject)}\n{names[les.teacher]}"
                        lines = max(lines, style.lines(value, day_width))
                    style.body_cell(ws, r, first_day_col + i, value)
                ws.row_dimensions[r].height = max(style.row_height, style.line_height * lines)
            top = first + len(rows) + BLOCK_GAP


def staff_rows(solution: Solution) -> list[Teacher]:
    """GV thật theo thứ tự file gốc, sau đó GV bổ sung được dùng."""
    real = [t for t in solution.problem.teachers.values() if not t.supplementary]
    real.sort(key=lambda t: (t.row is None, t.row or 0))
    return real + solution.used_supplements()


def write_timetable(solution: Solution, path: str | Path, style: Style | None = None,
                    with_codes: bool = False) -> None:
    """File TKB: chỉ các sheet Khối. Nhân sự và thống kê ghi ở file thống kê (write_statistics).
    with_codes: mỗi ô thêm dòng Mã GV (chức vụ) dưới tên giáo viên."""
    style = style or Style()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _grade_sheets(wb, solution, style, with_codes)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _stats_name(t: Teacher) -> str:
    return HIRE_LABEL if t.supplementary else t.name or None


def subject_table(solution: Solution, style: Style) -> tuple[list[str], list[list]]:
    """Họ và Tên | Chức Vụ (Mã GV) | số tiết từng môn | Tổng Tiết, mỗi giáo viên một dòng; cuối bảng có dòng Tổng.

    Chỉ có cột cho các môn có người dạy, theo thứ tự môn trong chương trình học; ô trống là không dạy môn đó.
    """
    problem = solution.problem
    count = Counter((les.teacher, les.subject) for les in solution.lessons)
    order = {s: i for i, s in enumerate(problem.subject_order)}
    subjects = sorted({s for _, s in count}, key=lambda s: (order.get(s, len(order)), s))
    header = [style.staff_headers["name"], "Chức Vụ", *(problem.subject_label(s) for s in subjects), TOTAL_HEADER]
    rows = []
    for t in staff_rows(solution):
        per = [count[t.title, s] for s in subjects]
        rows.append([_stats_name(t), t.code, *(n or None for n in per), sum(per)])
    rows.append(["Tổng", None, *(sum(r[c] or 0 for r in rows) for c in range(2, len(header)))])
    return header, rows


def _fill(color: str) -> PatternFill:
    return PatternFill(fill_type="solid", start_color=color, end_color=color)


def row_marks(solution: Solution) -> dict[str, tuple[str, int]]:
    """GV -> (màu nền, số tiết): người dạy bù (số tiết bù) và người cần tuyển thêm (số tiết thực dạy)."""
    load = solution.teacher_load()
    marks = {g: (OVERTIME_FILL, n) for g, n in solution.overtime().items()}
    marks.update({t.title: (HIRE_FILL, load[t.title]) for t in solution.used_supplements()})
    return marks


def _mark_rows(ws, solution: Solution, width: int, top: int, style: Style) -> list[int]:
    """Tô nền dòng người dạy bù và người cần tuyển (bảng bắt đầu ở dòng 1); dưới bảng, từ dòng `top`, ghi chú
    thích màu kèm số người, số tiết. Trả về các dòng chú thích."""
    marks = row_marks(solution)
    for r, t in enumerate(staff_rows(solution), start=2):
        if t.title in marks:
            for c in range(1, width + 1):
                ws.cell(r, c).fill = _fill(marks[t.title][0])
    legend = []
    for color, label in ((OVERTIME_FILL, OVERTIME_LEGEND), (HIRE_FILL, HIRE_LEGEND)):
        lessons = [n for mark, n in marks.values() if mark == color]
        if lessons:
            style.body_cell(ws, top, 1, None).fill = _fill(color)
            cell = ws.cell(top, 2, f"{label}: {len(lessons)} người, {sum(lessons)} tiết")
            cell.font = copy(style.body.font)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[top].height = style.row_height
            legend.append(top)
            top += 1
    return legend


def write_statistics(solution: Solution, path: str | Path, style: Style | None = None) -> None:
    """File thống kê: một bảng số tiết từng môn của mỗi giáo viên (xem subject_table). Dòng người dạy bù tô
    vàng, dòng người cần tuyển tô xanh, chú thích dưới bảng."""
    style = style or Style()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = STATS_SHEET
    header, rows = subject_table(solution, style)
    last = style.table(ws, header, rows, bold_last=True)
    legend = _mark_rows(ws, solution, len(header), last + 2, style)
    ws.freeze_panes = "C2"  # giữ cột tên, chức vụ và dòng tiêu đề khi cuộn
    style.fit_columns(ws, skip_rows=legend)  # chú thích tràn sang các ô trống bên phải, không nới cột
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_shortage(rows: list[tuple[str, str, int, str]], path: str | Path, style: Style | None = None) -> None:
    """File thống kê khi chế độ bù giờ không đủ: sheet SHORTAGE_SHEET liệt kê các tiết không ai dạy được."""
    style = style or Style()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHORTAGE_SHEET
    body = [list(r) for r in rows] + [["Tổng", None, sum(r[2] for r in rows), None]]
    style.table(ws, ["Lớp", "Môn", "Số Tiết Thiếu", "Lý Do"], body, bold_last=True)
    ws.freeze_panes = "A2"
    style.fit_columns(ws)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _copy_style(src, dst) -> None:
    if src.has_style:
        dst._style = copy(src._style)


def write_updated_staff(solution: Solution, source: str | Path, path: str | Path) -> None:
    """Chép file vào, thêm người cần tuyển vào cuối danh sách nhân sự và các cột Mã GV, số tiết thực dạy
    (và số tiết bù). Dòng, cột mới chép style của file vào; đọc lại file này làm file vào vẫn được.

    Mẫu V8 (có cột Lớp) ghi chức vụ không kèm số thứ tự, vd "Bộ Môn": khi đọc lại, chương trình tự
    đánh số tiếp theo (bộ môn 6, 7...). Mẫu cũ ghi đủ chức vụ, vd "bộ môn 6".
    """
    wb = openpyxl.load_workbook(source)
    ws = staff_sheet(wb)
    header_row, cols = _find_columns(ws)
    title_col = cols["title"]
    last = max((r for r in range(header_row + 1, ws.max_row + 1)
                if ws.cell(r, title_col).value not in (None, "")), default=header_row)
    v8 = "class" in cols
    by_row = {t.row: t for t in solution.problem.teachers.values() if not t.supplementary and t.row}
    for i, t in enumerate(solution.used_supplements(), start=1):
        r = last + i
        for c in range(1, ws.max_column + 1):
            _copy_style(ws.cell(last, c), ws.cell(r, c))
        if ws.row_dimensions[last].height:
            ws.row_dimensions[r].height = ws.row_dimensions[last].height
        if "stt" in cols:  # STT: chép công thức (vd =ROW()-1) hoặc tăng số của dòng trên
            above = ws.cell(r - 1, cols["stt"]).value
            ws.cell(r, cols["stt"], above if isinstance(above, str) and above.startswith("=")
                    else above + 1 if isinstance(above, int) else None)
        ws.cell(r, cols["name"], t.name)
        ws.cell(r, title_col, t.label if v8 else t.title)
        ws.cell(r, cols["lessons"], t.max_lessons)
        by_row[r] = t

    # Cột kết quả: ghi đè nếu file đã có (chạy lại trên file cập nhật), không thì thêm vào bên phải.
    load = solution.teacher_load()
    overtime = solution.overtime()
    values = {CODE_HEADER: lambda t: t.code, LOAD_HEADER: lambda t: load[t.title],
              OVERTIME_HEADER: lambda t: overtime.get(t.title)}
    wanted = [CODE_HEADER, LOAD_HEADER, *([OVERTIME_HEADER] if solution.problem.overtime_mode() else [])]
    headers = {normalize(ws.cell(header_row, c).value): c for c in range(1, ws.max_column + 1)
               if ws.cell(header_row, c).value not in (None, "")}
    next_col = max(headers.values(), default=0) + 1
    style = Style(body=CellStyle.of(ws.cell(header_row, title_col)))
    for h in values:
        c = headers.get(normalize(h))
        if c is None and h not in wanted:
            continue
        if c is None:
            c, next_col = next_col, next_col + 1
        ws.cell(header_row, c, h if h in wanted else None)
        _copy_style(ws.cell(header_row, title_col), ws.cell(header_row, c))
        for r in range(header_row + 1, max(ws.max_row, last) + 1):
            t = by_row.get(r)
            ws.cell(r, c, values[h](t) if t is not None and h in wanted else None)
            if t is not None:
                _copy_style(ws.cell(r, title_col), ws.cell(r, c))
        letter = get_column_letter(c)
        ws.column_dimensions[letter].width = max(ws.column_dimensions[letter].width or 0,
                                                 round(style.text_width(h), 1))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
