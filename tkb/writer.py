"""Xuất TKB ra Excel: sheet Khối, Danh sách nhân sự, Thống kê; file thống kê; file vào cập nhật.

Style (phông, cỡ chữ, viền, căn lề, chiều cao dòng) chép từ file vào (xem tkb/style.py).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import copy
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from . import config
from .solver import Solution
from .staff import MATERNITY_LABEL, Teacher, _find_columns, class_sort_key, normalize, staff_sheet
from .style import CellStyle, Style

MAX_DAY_WIDTH = 30  # cột ngày trong TKB: tên dài hơn thì xuống dòng
BLOCK_GAP = 2  # số dòng trống giữa hai lớp (giống template)
HIRE_LABEL = "tuyển thêm"  # tên của người cần tuyển trong file thống kê
CODE_HEADER = "Mã GV"
LOAD_HEADER = "Số Tiết Thực Dạy"
OVERTIME_HEADER = "Số Tiết Bù"


def teacher_labels(teachers: dict[str, Teacher]) -> dict[str, str]:
    """Chức vụ -> tên hiển thị dưới tên môn trong TKB.

    Ghi tên giáo viên; tên để trống hoặc người cần tuyển thêm thì ghi Mã GV (vd "Bộ Môn 6"), tên trùng
    nhau thì kèm Mã GV.
    """
    counts = Counter(t.name.strip() for t in teachers.values() if t.name.strip())
    labels = {}
    for title, t in teachers.items():
        name = t.name.strip()
        if not name or t.supplementary:
            labels[title] = t.code
        elif counts[name] > 1:
            labels[title] = f"{name} ({t.code})"
        else:
            labels[title] = name
    return labels


def session_rows() -> list[tuple[config.Session, int, int]]:
    """Các hàng của bảng TKB: (buổi, tiết trong ngày, số thứ tự tiết trong buổi)."""
    sessions: dict[str, config.Session] = {}
    for d in sorted(config.DAY_SESSIONS):
        for s in config.DAY_SESSIONS[d]:
            sessions.setdefault(s.name, s)
    ordered = sorted(sessions.values(), key=lambda s: s.periods[0])
    return [(s, p, i) for s in ordered for i, p in enumerate(s.periods, start=1)]


def _merge(ws, style: Style, r1: int, c1: int, r2: int, c2: int, value) -> None:
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            style.body_cell(ws, r, c, None, bold=True)
    ws.cell(r1, c1, value)
    if (r1, c1) != (r2, c2):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


def _grade_sheets(wb, solution: Solution, style: Style) -> None:
    grid = {(l.class_name, l.day, l.period): l for l in solution.lessons}
    days = sorted(config.DAY_SESSIONS)
    rows = session_rows()
    day_periods = {d: {p for s in config.DAY_SESSIONS[d] for p in s.periods} for d in days}
    first_day_col = 4
    problem = solution.problem
    names = teacher_labels(problem.teachers)
    header = ["LỚP", "BUỔI", "TIẾT", *[config.DAYS[d].upper() for d in days]]
    for grade in sorted({int(c.split("/")[0]) for c in problem.classes}):
        ws = wb.create_sheet(f"Khối {grade}")
        classes = sorted((c for c in problem.classes if int(c.split("/")[0]) == grade), key=class_sort_key)
        texts = [t for les in solution.lessons if int(les.class_name.split("/")[0]) == grade
                 for t in (problem.subject_label(les.subject), names[les.teacher])]
        day_width = min(MAX_DAY_WIDTH, max(style.text_width(t) for t in [*header[3:], config.OFF_LABEL, *texts]))
        widths = [max(style.text_width(t) for t in [header[0], *(f"LỚP {c}" for c in classes)]),
                  max(style.text_width(t) for t in [header[1], *(s.name.upper() for s, _, _ in rows)]),
                  style.text_width(header[2])]
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
            for session in dict.fromkeys(s for s, _, _ in rows):
                n = sum(1 for s, _, _ in rows if s is session)
                _merge(ws, style, r, 2, r + n - 1, 2, session.name.upper())
                r += n
            for j, (_, period, number) in enumerate(rows):
                r = first + j
                lines = 2  # môn + tên giáo viên
                style.body_cell(ws, r, 3, number)
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


def role_label(solution: Solution, role: str) -> str:
    """Chức vụ như ghi trong file vào (vd "Tiếng Anh"), ba chức vụ đặc biệt theo config."""
    labels = {t.role: t.label for t in solution.problem.teachers.values() if t.label}
    return labels.get(role) or config.ROLE_LABELS.get(role, role)


def mode_label(problem) -> str:
    if not problem.overtime_mode():
        return "Tuyển thêm (thiếu người thì thêm GV \"chưa có\")"
    return f"Bù giờ (GVCN, bộ môn bù tối đa {problem.overtime_max} tiết/người)"


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
        result[g] = "; ".join(f"{problem.subject_label(s)} ×{n}" for s, n in sorted(extra.items()))
    return result


def staff_table(solution: Solution, style: Style) -> tuple[list[str], list[list]]:
    """Danh sách nhân sự đã cập nhật: các cột của file vào + Mã GV, số tiết thực dạy, bù, ghi chú."""
    load = solution.teacher_load()
    overtime = solution.overtime()
    with_ot = solution.problem.overtime_mode()
    h = style.staff_headers
    header = [h["name"], h["title"], h["class"], h["lessons"], h["maternity"], CODE_HEADER, LOAD_HEADER,
              *([OVERTIME_HEADER] if with_ot else []), "Ghi Chú"]
    rows = []
    for t in staff_rows(solution):
        spare = t.max_lessons - load[t.title]
        if t.supplementary:
            note = "Cần tuyển thêm" + (f", còn dư {spare} tiết" if spare > 0 else "")
        else:
            note = f"Còn dư {spare} tiết" if spare > 0 else None
        rows.append([t.name or None, role_label(solution, t.role), t.class_name, t.max_lessons,
                     MATERNITY_LABEL if t.maternity else None, t.code, load[t.title],
                     *([overtime.get(t.title)] if with_ot else []), note])
    return header, rows


def _staff_sheet(wb, solution: Solution, style: Style) -> None:
    ws = wb.create_sheet("Danh sách nhân sự")
    header, rows = staff_table(solution, style)
    style.table(ws, header, rows)
    ws.freeze_panes = "A2"
    style.fit_columns(ws)


def role_summary(solution: Solution) -> list[list]:
    problem = solution.problem
    load = solution.teacher_load()
    rows = []
    for role in problem.roles():
        real = [t for t in problem.teachers.values() if t.role == role and not t.supplementary]
        extra = [t for t in solution.used_supplements() if t.role == role]
        if not real and not extra:
            continue
        cap = sum(t.max_lessons for t in real)
        used = sum(load[t.title] for t in real)
        spare = sum(max(0, t.max_lessons - load[t.title]) for t in real)
        row = [role_label(solution, role), len(real), cap, used, spare]
        if problem.overtime_mode():
            row.append(sum(max(0, load[t.title] - t.max_lessons) for t in real))
        rows.append(row + [sum(load[t.title] for t in extra), len(extra)])
    return rows


def _stats_sheet(wb, solution: Solution, errors: list[str], warnings: list[str], style: Style) -> None:
    ws = wb.create_sheet("Thống kê")
    problem = solution.problem
    load = solution.teacher_load()
    overtime = solution.overtime()
    with_ot = problem.overtime_mode()
    skip = {1}  # các dòng tựa: không tính vào độ rộng cột
    style.title_cell(ws, 1, 1, "THỐNG KÊ XẾP THỜI KHÓA BIỂU")
    row = 2
    info = [
        ("Chế độ", mode_label(problem)),
        ("Kiểm tra luật bắt buộc", "ĐẠT" if not errors else f"KHÔNG ĐẠT ({len(errors)} lỗi)"),
        ("Trạng thái solver", f"{solution.status} ({solution.stage})"),
        ("Thời gian xếp giờ (giây)", round(solution.wall_time, 1)),
        ("Số lớp", len(problem.classes)),
        ("Tổng số tiết/tuần", len(solution.lessons)),
        ("Tổng số tiết thiếu (giao cho GV tuyển thêm)", sum(load[t.title] for t in solution.used_supplements())),
        ("Số GV cần tuyển thêm", len(solution.used_supplements())),
    ]
    if with_ot:
        info.append(("Tổng số tiết dạy bù", sum(overtime.values())))
    for k, v in info + [("Ghi chú", note) for note in solution.notes + warnings]:
        style.body_cell(ws, row, 1, k, bold=True, horizontal="left")
        style.body_cell(ws, row, 2, v, horizontal="left")
        ws.row_dimensions[row].height = style.row_height
        row += 1
    row += 1

    def titled(title: str, header: list[str], rows: list[list], bold_last: bool = False) -> None:
        nonlocal row
        style.title_cell(ws, row, 1, title)
        skip.add(row)
        row = style.table(ws, header, rows, top=row + 1, bold_last=bold_last) + 2

    details: dict[str, Counter] = defaultdict(Counter)
    for les in solution.lessons:
        details[les.teacher][(les.class_name, les.subject)] += 1
    sup_rows = []
    for t in solution.used_supplements():
        items = sorted(details[t.title].items(), key=lambda kv: (class_sort_key(kv[0][0]), kv[0][1]))
        text = "; ".join(f"{c} {problem.subject_label(s)} ×{n}" for (c, s), n in items)
        sup_rows.append([t.code, t.name, load[t.title], text])
    if sup_rows:
        sup_rows.append(["Tổng", None, sum(r[2] for r in sup_rows), None])
    else:
        sup_rows.append(["(không thiếu)", None, 0, None])
    number = iter(range(1, 10))
    titled(f"{next(number)}. CHỨC VỤ THIẾU VÀ SỐ TIẾT THIẾU (GV tuyển thêm \"{config.SUPPLEMENT_NAME}\")",
           [CODE_HEADER, "Tên", "Số Tiết Thiếu", "Chi Tiết (lớp môn × số tiết)"], sup_rows, bold_last=True)

    if with_ot:
        subjects = overtime_details(solution)
        ot_rows = [[t.code, t.name or None, overtime[t.title], subjects.get(t.title), t.max_lessons, load[t.title]]
                   for t in staff_rows(solution) if t.title in overtime]
        ot_rows.append(["Tổng", None, sum(overtime.values()), None, None, None])
        titled(f"{next(number)}. DẠY BÙ (vượt định mức)",
               [CODE_HEADER, "Tên", "Số Tiết Bù", "Môn Bù (GVCN, lớp mình)", "Định Mức", "Thực Dạy"], ot_rows,
               bold_last=True)

    titled(f"{next(number)}. THEO NHÓM CHỨC VỤ",
           ["Chức Vụ", "Số GV Hiện Có", "Tổng Định Mức", "Đã Dạy", "Dư (chưa dùng)",
            *(["Dạy Bù"] if with_ot else []), "Tiết Thiếu", "Số GV Tuyển Thêm"], role_summary(solution))

    days = sorted(config.DAY_SESSIONS)
    per_day = daily_loads(solution)
    classes_of: dict[str, set] = defaultdict(set)
    for les in solution.lessons:
        classes_of[les.teacher].add(les.class_name)
    load_rows = [[t.code, t.name or None, t.max_lessons, load[t.title], max(0, t.max_lessons - load[t.title]),
                  *([overtime.get(t.title, 0)] if with_ot else []),
                  *[per_day[t.title][d] for d in days], len(classes_of[t.title])] for t in staff_rows(solution)]
    titled(f"{next(number)}. TẢI TỪNG GIÁO VIÊN",
           [CODE_HEADER, "Tên", "Định Mức", "Thực Dạy", "Dư", *(["Bù"] if with_ot else []),
            *[config.DAYS[d] for d in days], "Số Lớp Dạy"], load_rows)

    if errors:
        titled(f"{next(number)}. LỖI KIỂM TRA", ["Lỗi"], [[e] for e in errors])
    style.fit_columns(ws, skip_rows=skip)


def write_timetable(solution: Solution, path: str | Path, errors: list[str], warnings: list[str],
                    style: Style | None = None) -> None:
    style = style or Style()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _grade_sheets(wb, solution, style)
    _staff_sheet(wb, solution, style)
    _stats_sheet(wb, solution, errors, warnings, style)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _stats_name(t: Teacher) -> str:
    return HIRE_LABEL if t.supplementary else t.name or None


def statistics_rows(solution: Solution) -> list[list]:
    """Tên | Chức vụ | Mã GV | Số tiết quy định | Số tiết bù | Số tiết thực dạy | Số tiết còn dư."""
    load = solution.teacher_load()
    overtime = solution.overtime()
    return [[_stats_name(t), role_label(solution, t.role), t.code, t.max_lessons, overtime.get(t.title, 0),
             load[t.title], max(0, t.max_lessons - load[t.title])] for t in staff_rows(solution)]


def assignment_rows(solution: Solution) -> list[list]:
    """Phân công chuyên môn: Tên | Mã GV | Lớp | Môn | Số tiết (theo thứ tự danh sách nhân sự)."""
    problem = solution.problem
    count = Counter((les.teacher, les.class_name, les.subject) for les in solution.lessons)
    subject_order = {s: i for i, s in enumerate(problem.subject_order)}
    rows = []
    for t in staff_rows(solution):
        items = sorted(((c, s, n) for (g, c, s), n in count.items() if g == t.title),
                       key=lambda x: (class_sort_key(x[0]), subject_order.get(x[1], len(subject_order))))
        rows += [[_stats_name(t), t.code, c, problem.subject_label(s), n] for c, s, n in items]
    return rows


def daily_rows(solution: Solution) -> list[list]:
    """Tên | Mã GV | số tiết từng ngày | Tổng."""
    per_day = daily_loads(solution)
    days = sorted(config.DAY_SESSIONS)
    return [[_stats_name(t), t.code, *[per_day[t.title][d] for d in days], sum(per_day[t.title].values())]
            for t in staff_rows(solution)]


def role_rows(solution: Solution) -> list[list]:
    """Chức vụ | Số người | Quy định | Thực dạy | Bù | Còn dư | Số người tuyển thêm | Số tiết tuyển thêm."""
    load = solution.teacher_load()
    overtime = solution.overtime()
    teachers = staff_rows(solution)
    rows = []
    for role in solution.problem.roles():
        real = [t for t in teachers if t.role == role and not t.supplementary]
        hired = [t for t in teachers if t.role == role and t.supplementary]
        if not real and not hired:
            continue
        rows.append([role_label(solution, role), len(real), sum(t.max_lessons for t in real),
                     sum(load[t.title] for t in real), sum(overtime.get(t.title, 0) for t in real),
                     sum(max(0, t.max_lessons - load[t.title]) for t in real),
                     len(hired), sum(load[t.title] for t in hired)])
    return rows


def _stats_table(ws, style: Style, header: list[str], rows: list[list], total_from: int | None = None) -> None:
    """Bảng như sheet nhân sự của file vào (tiêu đề ở dòng 1); total_from: cộng các cột từ vị trí này."""
    data = [[i, *r] for i, r in enumerate(rows, start=1)]
    if total_from is not None:
        data.append([None, "Tổng", *[None] * (total_from - 2),
                     *[sum(r[c] or 0 for r in data) for c in range(total_from, len(header))]])
    style.table(ws, header, data, bold_last=total_from is not None)
    ws.freeze_panes = "A2"
    style.fit_columns(ws)


def write_statistics(solution: Solution, path: str | Path, style: Style | None = None) -> None:
    """File Excel thống kê giáo viên: số tiết, phân công, tải theo ngày, tổng hợp theo chức vụ."""
    style = style or Style()
    name = style.staff_headers["name"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Thống kê giáo viên"
    _stats_table(ws, style, ["STT", name, "Chức Vụ", CODE_HEADER, "Số Tiết Quy Định", "Số Tiết Bù",
                             "Số Tiết Thực Dạy", "Số Tiết Còn Dư"], statistics_rows(solution), total_from=4)
    _stats_table(wb.create_sheet("Phân công"), style, ["STT", name, CODE_HEADER, "Lớp", "Môn", "Số Tiết"],
                 assignment_rows(solution))
    days = [config.DAYS[d] for d in sorted(config.DAY_SESSIONS)]
    _stats_table(wb.create_sheet("Theo ngày"), style, ["STT", name, CODE_HEADER, *days, "Tổng"],
                 daily_rows(solution), total_from=3)
    _stats_table(wb.create_sheet("Theo chức vụ"), style,
                 ["STT", "Chức Vụ", "Số Người", "Số Tiết Quy Định", "Số Tiết Thực Dạy", "Số Tiết Bù",
                  "Số Tiết Còn Dư", "Số Người Tuyển Thêm", "Số Tiết Tuyển Thêm"], role_rows(solution), total_from=2)
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
