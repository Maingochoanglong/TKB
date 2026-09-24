"""Đọc (tùy chọn) file chương trình học: cột 'Môn học' và các cột 'Khối k'."""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl

from . import config
from .staff import InputError, normalize


def _canonical_subjects() -> dict[str, str]:
    return {normalize(n): n for n in config.SUBJECTS}


def read_program(path: str | Path) -> dict[int, dict[str, int]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
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
        raise InputError("File chương trình học phải có cột 'Môn học' và các cột 'Khối k'")

    canonical = _canonical_subjects()
    curriculum: dict[int, dict[str, int]] = {g: {} for g in grade_cols}
    for r in range(header_row + 1, ws.max_row + 1):
        subject = ws.cell(r, subject_col).value
        if subject is None or str(subject).strip() == "":
            continue
        subject = canonical.get(normalize(subject), " ".join(str(subject).split()))
        for grade, col in grade_cols.items():
            value = ws.cell(r, col).value
            value = 0 if value is None or str(value).strip() == "" else value
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise InputError(f"Dòng {r}, Khối {grade}: số tiết không hợp lệ {value!r}") from None
            if number != int(number) or number < 0:
                raise InputError(f"Dòng {r}, Khối {grade}: số tiết phải là số nguyên không âm")
            if subject in curriculum[grade]:
                raise InputError(f"Môn '{subject}' bị lặp trong file chương trình học")
            curriculum[grade][subject] = int(number)
    return curriculum
