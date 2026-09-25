"""Đọc chương trình học: cột 'Môn học' và các cột 'Khối k'.

Chương trình học nằm ở sheet "CHƯƠNG TRÌNH HỌC" của file vào, hoặc ở sheet đầu của một file riêng.
Danh sách môn và tên môn lấy nguyên từ file. Khi dựng bài toán, môn nào trùng tên một môn có luật trong
tkb/config.py (xem `canonical_subject`) thì nhận luật đó, môn khác vẫn được xếp bình thường.
"""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl

from . import config
from .staff import InputError, clean_name, find_sheet, normalize, subject_key


def _rule_names() -> dict[str, str]:
    names = {subject_key(label): s for s, label in config.DISPLAY_NAMES.items()}
    names.update({subject_key(s): s for s in config.rule_subjects()})
    return names


def canonical_subject(name) -> str:
    """Tên môn dùng khi dựng bài toán: tên trong config nếu khớp một môn có luật, không thì giữ tên trong file."""
    return _rule_names().get(subject_key(name), clean_name(name))


def has_program_sheet(path: str | Path) -> bool:
    return find_sheet(openpyxl.load_workbook(path, read_only=True), config.PROGRAM_SHEET) is not None


def read_program(path: str | Path) -> dict[int, dict[str, int]]:
    """Đọc sheet "CHƯƠNG TRÌNH HỌC" nếu có, không thì sheet đầu tiên.

    Trả về {khối: {tên môn như trong file: số tiết}}, giữ thứ tự dòng của file.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = find_sheet(wb, config.PROGRAM_SHEET) or wb.worksheets[0]
    header_row = subject_col = None
    grade_cols: dict[int, int] = {}
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 20)):
        cols = {}
        subj = None
        for cell in row:
            if cell.value is None:
                continue
            key = normalize(cell.value)
            if key == "môn học":
                subj = cell.column
            m = re.fullmatch(r"khối (\d+)", key)
            if m:
                cols[int(m.group(1))] = cell.column
        if subj and cols:
            header_row, subject_col, grade_cols = row[0].row, subj, cols
            break
    if header_row is None:
        raise InputError(f"Sheet {config.PROGRAM_SHEET} phải có cột 'Môn học' và các cột 'Khối k'")

    curriculum: dict[int, dict[str, int]] = {g: {} for g in grade_cols}
    seen: dict[str, int] = {}
    for r in range(header_row + 1, ws.max_row + 1):
        subject = ws.cell(r, subject_col).value
        if subject is None or str(subject).strip() == "" or normalize(subject) in ("tổng", "tổng cộng"):
            continue
        name = clean_name(subject)
        key = canonical_subject(subject)
        if key in seen:
            raise InputError(f"Dòng {r}: môn '{name}' bị lặp với dòng {seen[key]} trong chương trình học")
        seen[key] = r
        for grade, col in grade_cols.items():
            value = ws.cell(r, col).value
            value = 0 if value is None or str(value).strip() == "" else value
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise InputError(f"Dòng {r}, Khối {grade}: số tiết không hợp lệ {value!r}") from None
            if number != int(number) or number < 0:
                raise InputError(f"Dòng {r}, Khối {grade}: số tiết phải là số nguyên không âm")
            curriculum[grade][name] = int(number)
    if not any(curriculum.values()):
        raise InputError(f"Sheet {config.PROGRAM_SHEET} chưa có môn nào")
    return curriculum


def load_curriculum(input_path: str | Path, program_path: str | Path | None = None
                    ) -> tuple[dict[int, dict[str, int]], str]:
    """Chương trình học của file vào (hoặc file riêng `program_path`) và mô tả nguồn."""
    if program_path:
        return read_program(program_path), str(program_path)
    if not has_program_sheet(input_path):
        raise InputError(f"File vào thiếu sheet {config.PROGRAM_SHEET} (Môn học, Khối 1, Khối 2...)")
    return read_program(input_path), f"sheet {config.PROGRAM_SHEET} của file vào"


def subjects_in_order(curriculum: dict[int, dict[str, int]]) -> list[str]:
    """Các môn theo thứ tự xuất hiện trong file."""
    return list(dict.fromkeys(s for g in sorted(curriculum) for s in curriculum[g]))


def missing_rule_subjects(curriculum: dict[int, dict[str, int]]) -> list[str]:
    """Môn có luật trong config nhưng không có trong chương trình học (thường do gõ khác tên)."""
    present = {canonical_subject(s) for req in curriculum.values() for s in req}
    return [s for s in config.rule_subjects() if s not in present]
