"""Kịch bản của một trường cho giao diện (tkb/giao_dien): toàn bộ nội dung file vào V8 dưới dạng dữ liệu JSON.

Giao diện không có luật riêng: kịch bản chỉ là các bảng của file vào (NHÂN SỰ, CHƯƠNG TRÌNH HỌC kèm cột quy định,
QUY ĐỊNH), mỗi cột quy định lấy từ tkb/rules.py (`Col`: tiêu đề, khóa, loại ô, ghi chú) nên thêm một quy định vào
rules.py là giao diện tự có ô nhập. Xuất kịch bản ra Excel dùng đúng hàm ghi file mẫu (tkb/template.py); kiểm tra
kịch bản = xuất ra file tạm rồi đọc lại bằng chính các hàm đọc của chương trình, nên giao diện và dòng lệnh luôn hiểu
file vào như nhau.

Kịch bản:
    staff    : [{name, role, class, lessons, maternity, contract, campus2, history, off}] theo thứ tự dòng
    grades   : [1, 2, ...] các cột Khối
    subjects : [{name, lessons: {"1": số tiết hoặc None, ...}, rules: {khóa Col: giá trị}}]
    general  : {khóa Col: giá trị} (bảng Quy định | Giá trị)
    days     : [{khóa Col: giá trị}] Thứ 2 … Thứ 7
    periods  : [{khóa Col: giá trị}] tiết 1, 2, ...
    saved    : các dòng của sheet TKB đã xếp (file vào cập nhật) hoặc None
Giá trị theo loại ô: "yes" → true/false; "int", "order" → số hoặc None; "text" → chữ.
"""
from __future__ import annotations

import datetime
import tempfile
from pathlib import Path

import openpyxl

from . import config
from .program import read_program
from .rules import (DAY_COLS, DAY_KEY, GENERAL, GENERAL_KEY, MAX_DAYS, NO, PERIOD_COLS, PERIOD_KEY, SUBJECT_COLS, VALUE,
                    YES, _day_name, applied, read_rules, rule_tables, subject_columns)
from .staff import (InputError, _find_columns, _fold, _NO, _YES, clean_name, find_sheet, normalize, read_staff,
                    staff_sheet)
from .template import NOTES, STAFF_HEADERS, program_rows, write_input

VERSION = 1
# Các cột của sheet NHÂN SỰ: (khóa trong kịch bản, khóa của staff._find_columns, loại ô); tiêu đề là STAFF_HEADERS.
STAFF_COLS = (("name", "name", "text"), ("role", "title", "role"), ("class", "class", "text"),
              ("lessons", "lessons", "int"), ("maternity", "maternity", "yes"), ("contract", "contract", "yes"),
              ("campus2", "campus2", "yes"), ("history", "history", "text"), ("off", "off", "text"))
_HEADERS = {key: head for (key, _, _), head in zip(STAFF_COLS, STAFF_HEADERS)}
ROLES = [config.ROLE_LABELS[r] for r in (config.ROLE_HOMEROOM, config.ROLE_GENERAL, config.ROLE_MANAGER)]


def _col(c) -> dict:
    return {"key": c.key, "header": c.header, "kind": c.kind, "note": c.note}


def schema() -> dict:
    """Mô tả các bảng, cột cho giao diện (sinh ô nhập theo đây)."""
    return {
        "version": VERSION,
        "staff": [{"key": key, "header": _HEADERS[key], "kind": kind, "note": NOTES[_HEADERS[key]]}
                  for key, _, kind in STAFF_COLS],
        "roles": ROLES,
        "subject": [_col(c) for c in SUBJECT_COLS],
        "general": [_col(c) for c in GENERAL],
        "day": [_col(c) for c in DAY_COLS],
        "period": [_col(c) for c in PERIOD_COLS],
        "days": [_day_name(d) for d in range(MAX_DAYS)],
        "sheets": {"staff": config.STAFF_SHEET, "program": config.PROGRAM_SHEET, "rules": config.RULES_SHEET,
                   "saved": config.SAVED_SHEET},
    }


# ---- đọc file Excel thành kịch bản ----

def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _number(value):
    """Số nguyên nếu ô là số nguyên, ô trống là None, còn lại giữ chữ (kiểm tra sẽ báo lỗi)."""
    if _blank(value) or isinstance(value, bool):
        return None if _blank(value) else str(value)
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, int):
        return value
    text = clean_name(value)
    return int(text) if text.isdigit() else text


def _text(value) -> str:
    if _blank(value):
        return ""
    if isinstance(value, float) and value == int(value):
        value = int(value)
    return clean_name(value)


def _read_staff_rows(wb, warnings: list[str]) -> list[dict]:
    """Các dòng của sheet nhân sự đúng như chữ trong file (không kiểm tra; dòng trống bỏ qua)."""
    ws = staff_sheet(wb)
    header_row, cols = _find_columns(ws)
    rows = []
    for r in range(header_row + 1, ws.max_row + 1):
        raw = {key: ws.cell(r, cols[col]).value if col in cols else None for key, col, _ in STAFF_COLS}
        if all(_blank(v) for v in raw.values()):
            continue
        row = {}
        for key, _, kind in STAFF_COLS:
            value = raw[key]
            if kind == "yes":
                folded = "" if _blank(value) else _fold(value)
                row[key] = value is True or folded in _YES
                if folded and folded not in _YES | _NO and not isinstance(value, bool):
                    warnings.append(f"{ws.title}, dòng {r}: cột {_HEADERS[key]} ghi {value!r}, đã đọc là không")
            elif kind == "int":
                row[key] = _number(value)
            elif isinstance(value, (datetime.date, datetime.datetime)):
                row[key] = f"{value.day}/{value.month}"
                warnings.append(f"{ws.title}, dòng {r}: ô {value:%d/%m/%Y} là ngày tháng (Excel tự đổi), đã đọc "
                                f"thành lớp {row[key]}; hãy kiểm tra lại")
            else:
                row[key] = _text(value)
        rows.append(row)
    return rows


def _read_program_rows(wb) -> tuple[list[int], list[tuple[str, dict]]]:
    """Các khối và các dòng (môn, {khối: số tiết}) của sheet CHƯƠNG TRÌNH HỌC đúng như trong file."""
    ws = find_sheet(wb, config.PROGRAM_SHEET)
    if ws is None:
        raise InputError(f"File vào thiếu sheet {config.PROGRAM_SHEET} (Môn học, Khối 1, Khối 2...)")
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 20)):
        heads = {normalize(c.value): c.column for c in row if not _blank(c.value)}
        grades = {int(h.split()[1]): c for h, c in heads.items() if h.startswith("khối ") and h[5:].isdigit()}
        if "môn học" in heads and grades:
            header_row, subject_col = row[0].row, heads["môn học"]
            break
    else:
        raise InputError(f"Sheet {config.PROGRAM_SHEET} phải có cột 'Môn học' và các cột 'Khối k'")
    rows = []
    for r in range(header_row + 1, ws.max_row + 1):
        name = ws.cell(r, subject_col).value
        if _blank(name) or normalize(name) in ("tổng", "tổng cộng"):
            continue
        rows.append((clean_name(name), {str(g): _number(ws.cell(r, c).value) for g, c in sorted(grades.items())}))
    return sorted(grades), rows


def _from_cell(col, value):
    if col.kind == "yes":
        return value == YES
    if col.kind == "text":
        return _text(value)
    return value


def _json_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _read_saved(wb) -> list[list] | None:
    ws = find_sheet(wb, config.SAVED_SHEET)
    if ws is None:
        return None
    rows = [[_json_value(v) for v in row] for row in ws.iter_rows(values_only=True)]
    while rows and all(v is None for v in rows[-1]):
        rows.pop()
    return [row[:max((i + 1 for i, v in enumerate(row) if v is not None), default=0)] for row in rows]


def _rules_part(subject_names: list[str]) -> tuple[dict, list[dict], list[dict], dict[str, dict], list[str]]:
    """Các quy định đang dùng (config) theo dạng kịch bản: (chung, ngày, tiết, {môn: quy định}, các môn có quy
    định mà chương trình học không có)."""
    general_t, days_t, periods_t = rule_tables()
    general = {c.key: _from_cell(c, value) for c, (_, value) in zip(GENERAL, general_t[1])}
    days = [{c.key: _from_cell(c, v) for c, v in zip(DAY_COLS, row[1:])} for row in days_t[1]]
    periods = [{c.key: _from_cell(c, v) for c, v in zip(PERIOD_COLS, row[1:])} for row in periods_t[1]]
    _, values, rest = subject_columns(subject_names)
    subjects = {name: {c.key: _from_cell(c, v) for c, v in zip(SUBJECT_COLS, row)} for name, row in values.items()}
    return general, days, periods, subjects, rest


def from_excel(path: str | Path) -> tuple[dict, list[str]]:
    """Đọc file vào V8 (cả file vào cập nhật *_cap_nhat.xlsx) thành kịch bản: (kịch bản, các cảnh báo). Nhân sự và số
    tiết đọc đúng như chữ trong file (lỗi sẽ hiện khi kiểm tra); quy định đọc bằng rules.read_rules, cột/bảng không
    có thì lấy giá trị mặc định như khi chạy. Quy định sai cách ghi thì báo lỗi (InputError)."""
    warnings: list[str] = []
    wb = openpyxl.load_workbook(path, data_only=True)
    staff = _read_staff_rows(wb, warnings)
    grades, program = _read_program_rows(wb)
    rules = read_rules(path, warn=warnings.append)
    with applied(rules):
        general, days, periods, by_subject, rest = _rules_part([name for name, _ in program])
    subjects = [{"name": name, "lessons": lessons, "rules": by_subject[name]} for name, lessons in program]
    subjects += [{"name": name, "lessons": {str(g): None for g in grades}, "rules": by_subject[name]}
                 for name in rest]
    scenario = {"version": VERSION, "staff": staff, "grades": grades, "subjects": subjects, "general": general,
                "days": days, "periods": periods, "saved": _read_saved(wb)}
    return scenario, warnings


def default_scenario() -> dict:
    """Kịch bản trống như file mẫu (python -m tkb.template): chưa có nhân sự, các môn có quy định mặc định với số tiết
    để trống, mọi quy định là giá trị mặc định."""
    grades, _, rows = program_rows(None)
    names = [row[0] for row in rows]
    general, days, periods, by_subject, _ = _rules_part(names)
    return {"version": VERSION, "staff": [], "grades": grades,
            "subjects": [{"name": n, "lessons": {str(g): None for g in grades}, "rules": by_subject[n]} for n in names],
            "general": general, "days": days, "periods": periods, "saved": None}


# ---- ghi kịch bản ra file Excel ----

def _to_cell(col, value):
    if col.kind == "yes":
        return YES if value is True or (isinstance(value, str) and _fold(value) in _YES) else NO
    if col.kind == "text":
        return _text(value) or None
    return _number(value)


def _staff_row(row: dict) -> list:
    out = []
    for key, _, kind in STAFF_COLS:
        value = row.get(key)
        if kind == "yes":
            out.append(YES if value is True or (isinstance(value, str) and _fold(value) in _YES) else None)
        elif kind == "int":
            out.append(_number(value))
        else:
            out.append(_text(value) or None)
    return out


def to_excel(scenario: dict, path: str | Path) -> None:
    """Ghi kịch bản ra file vào V8 (NHÂN SỰ, CHƯƠNG TRÌNH HỌC kèm cột quy định, QUY ĐỊNH, HƯỚNG DẪN và, nếu có, sheet
    TKB đã xếp), cùng cách ghi với file mẫu."""
    staff = [_staff_row(row) for row in scenario.get("staff", [])]  # cả dòng trống: dòng i là dòng i + 2 của sheet
    grades = [int(g) for g in scenario.get("grades", [])]
    rows = []
    for subject in scenario.get("subjects", []):
        lessons, rules = subject.get("lessons") or {}, subject.get("rules") or {}
        row = [_text(subject.get("name")) or None, *[_number(lessons.get(str(g))) for g in grades],
               *[_to_cell(c, rules.get(c.key)) for c in SUBJECT_COLS]]
        if row[0] is not None or any(v is not None for v in row[1:1 + len(grades)]):
            rows.append(row)
    general = scenario.get("general") or {}
    days = scenario.get("days") or []
    periods = scenario.get("periods") or []
    tables = [([GENERAL_KEY, VALUE], [[c.header, _to_cell(c, general.get(c.key))] for c in GENERAL]),
              ([DAY_KEY, *(c.header for c in DAY_COLS)],
               [[_day_name(d), *(_to_cell(c, day.get(c.key)) for c in DAY_COLS)] for d, day in enumerate(days)]),
              ([PERIOD_KEY, *(c.header for c in PERIOD_COLS)],
               [[p, *(_to_cell(c, row.get(c.key)) for c in PERIOD_COLS)] for p, row in enumerate(periods, start=1)])]
    saved = scenario.get("saved")

    def write_saved(wb):
        ws = wb.create_sheet(config.SAVED_SHEET)
        for row in saved:
            ws.append(row)

    write_input(path, staff, (grades, [c.header for c in SUBJECT_COLS], rows), tables,
                extra=write_saved if saved else None)


# ---- kiểm tra ----

def _lines(exc: Exception, sheet: str = "") -> list[str]:
    """Các dòng lỗi của một InputError (dòng tiêu đề "... có n lỗi:" bỏ đi), thêm tên sheet nếu lỗi chưa ghi."""
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    lines = lines[1:] if len(lines) > 1 and lines[0].endswith(":") else lines
    return [line if not sheet or line.startswith(sheet) else f"{sheet}: {line}" for line in lines]


def check(scenario: dict, mode: str = config.MODE_OVERTIME, overtime_max: int = config.OVERTIME_MAX,
          student_rules: bool = True) -> dict:
    """Kiểm tra kịch bản như khi chạy: ghi ra file tạm, đọc lại bằng các hàm đọc của chương trình, đếm tìm các quy
    định mâu thuẫn (chan_doan.precheck), rồi dự toán (phân công, không xếp giờ, vài giây). Trả về {errors, warnings,
    info}: lỗi chặn việc xếp TKB; info là số liệu và dự toán. Đổi tạm config (rules.applied) nên không gọi song
    song."""
    from .allocation import build_problem
    from .chan_doan import precheck
    from .phan_cong import phan_cong
    from .solver import ShortageError, SolveError, du_toan_lines

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "kich_ban.xlsx"
        to_excel(scenario, path)
        try:
            rules = read_rules(path, warn=warnings.append)
        except InputError as exc:
            return {"errors": _lines(exc), "warnings": warnings, "info": info}
        with applied(rules):
            try:
                curriculum = read_program(path)
            except InputError as exc:
                errors += _lines(exc, config.PROGRAM_SHEET)
                curriculum = None
            try:
                subjects = [s for req in curriculum.values() for s in req] if curriculum else None
                staff = read_staff(path, subjects=subjects)
            except InputError as exc:
                errors += _lines(exc, config.STAFF_SHEET)
                staff = None
            if errors or not curriculum:
                return {"errors": errors, "warnings": warnings, "info": info}
            classes = [t for t in staff if t.class_name]
            total = sum(sum(curriculum.get(t.grade, {}).values()) for t in classes)
            quota = sum(t.max_lessons for t in staff)
            info.append(f"{len(staff)} nhân sự, {len(classes)} lớp, "
                        f"{len({s for req in curriculum.values() for s in req})} môn; cần dạy {total} tiết/tuần, "
                        f"tổng định mức {quota} tiết/tuần" + (f" (thiếu {total - quota})" if total > quota else ""))
            try:
                base = build_problem(staff, curriculum, {}, overtime_max=overtime_max)
                warnings += base.warnings
                conflicts = precheck(base, student_rules)
                if conflicts:
                    errors += [f"Quy định mâu thuẫn, không có TKB nào thỏa: {line}" for line in conflicts]
                    return {"errors": errors, "warnings": warnings, "info": info}
                plan = phan_cong(base, config.Weights())
            except (InputError, SolveError) as exc:
                errors += _lines(exc)
                return {"errors": errors, "warnings": warnings, "info": info}
            info += [line.strip() for line in du_toan_lines(base, plan)]
            if plan.missing:
                rows = ShortageError(base, plan).rows()
                head = (f"Bù tối đa +{overtime_max} tiết/người vẫn thiếu {plan.missing_total()} tiết: chế độ bù giờ sẽ "
                        f"báo lỗi; tăng số tiết bù tối đa, sửa nhân sự, hoặc chọn chế độ tuyển thêm"
                        if mode == config.MODE_OVERTIME else
                        f"Thiếu {plan.missing_total()} tiết dù đã bù tối đa +{overtime_max}: chế độ tuyển thêm sẽ thêm "
                        f"người \"{config.SUPPLEMENT_NAME}\"")
                info.append(head)
                info += [f"Lớp {cls}: {subject} thiếu {n} tiết ({reason})" for cls, subject, n, reason in rows[:30]]
                if len(rows) > 30:
                    info.append(f"... và {len(rows) - 30} dòng khác")
    return {"errors": errors, "warnings": warnings, "info": info}
