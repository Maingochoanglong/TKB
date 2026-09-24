"""Đọc và kiểm tra file Excel danh sách nhân sự (Tên / Chức vụ / Số tiết)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from . import config


class InputError(ValueError):
    """Lỗi dữ liệu đầu vào."""


@dataclass
class Teacher:
    name: str
    title: str  # chức vụ chuẩn hóa, dùng làm mã và nhãn trong TKB, vd "bộ môn 5 ts"
    role: str  # "chủ nhiệm", "bộ môn", "quản lý", hoặc một chức vụ chuyên biệt
    index: int | None  # số thứ tự trong chức vụ (không áp dụng cho chủ nhiệm)
    class_name: str | None  # lớp chủ nhiệm, vd "1/1"
    maternity: bool
    max_lessons: int
    supplementary: bool = False
    row: int | None = None  # dòng trong file Excel gốc

    @property
    def grade(self) -> int | None:
        return int(self.class_name.split("/")[0]) if self.class_name else None


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).strip().lower()
    return re.sub(r"\s+", " ", text)


_TITLE_RE = re.compile(r"^(?P<role>\D+?)\s+(?P<idx>\d+(?:\s*/\s*\d+)?)(?:\s+(?P<ts>ts))?$")


def known_roles() -> set[str]:
    return {config.ROLE_HOMEROOM, config.ROLE_GENERAL, config.ROLE_MANAGER, *config.SPECIALIST_ROLES}


def parse_title(raw: str) -> tuple[str, int | None, str | None, bool]:
    """Tách chức vụ thành (role, index, lớp chủ nhiệm, thai sản)."""
    text = normalize(raw)
    m = _TITLE_RE.match(text)
    if not m:
        raise InputError(f"Chức vụ không đúng dạng '<chức vụ> <số thứ tự>[ ts]': {raw!r}")
    role = m.group("role").strip()
    idx = re.sub(r"\s+", "", m.group("idx"))
    maternity = m.group("ts") is not None
    if role not in known_roles():
        raise InputError(f"Chức vụ không xác định: {raw!r} (hợp lệ: {', '.join(sorted(known_roles()))})")
    if role == config.ROLE_HOMEROOM:
        if "/" not in idx:
            raise InputError(f"Chủ nhiệm phải ghi lớp dạng khối/stt, vd 'chủ nhiệm 1/1': {raw!r}")
        grade, num = idx.split("/")
        return role, None, f"{int(grade)}/{int(num)}", maternity
    if "/" in idx:
        raise InputError(f"Chỉ chủ nhiệm mới ghi lớp khối/stt: {raw!r}")
    return role, int(idx), None, maternity


def canonical_title(role: str, index: int | None, class_name: str | None, maternity: bool) -> str:
    base = f"{role} {class_name}" if role == config.ROLE_HOMEROOM else f"{role} {index}"
    return f"{base} ts" if maternity else base


def _find_columns(ws) -> tuple[int, dict[str, int]]:
    wanted = {"tên": "name", "chức vụ": "title", "số tiết": "lessons"}
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 20)):
        found = {}
        for cell in row:
            if cell.value is None:
                continue
            key = normalize(cell.value)
            if key in wanted:
                found[wanted[key]] = cell.column
        if len(found) == 3:
            return row[0].row, found
    raise InputError("Không tìm thấy dòng tiêu đề có đủ các cột 'Tên', 'Chức vụ', 'Số tiết'")


def _to_lessons(value, title: str) -> int:
    if isinstance(value, bool) or value is None:
        raise InputError(f"Số tiết của '{title}' bị trống hoặc không hợp lệ")
    try:
        number = float(str(value).strip())
    except ValueError:
        raise InputError(f"Số tiết của '{title}' không phải số: {value!r}") from None
    if number != int(number) or number < 0:
        raise InputError(f"Số tiết của '{title}' phải là số nguyên không âm: {value!r}")
    return int(number)


def build_teacher(name: str, raw_title: str, lessons, row: int | None = None) -> Teacher:
    role, index, class_name, maternity = parse_title(raw_title)
    title = canonical_title(role, index, class_name, maternity)
    return Teacher(
        name=str(name).strip() if name is not None else "",
        title=title,
        role=role,
        index=index,
        class_name=class_name,
        maternity=maternity,
        max_lessons=_to_lessons(lessons, title),
        row=row,
    )


def validate(teachers: list[Teacher]) -> None:
    seen: dict[str, Teacher] = {}
    homeroom: dict[str, Teacher] = {}
    keys: dict[tuple[str, int], Teacher] = {}
    for t in teachers:
        if t.title in seen:
            raise InputError(f"Trùng chức vụ '{t.title}' (dòng {seen[t.title].row} và {t.row})")
        seen[t.title] = t
        if t.class_name:
            if t.class_name in homeroom:
                raise InputError(f"Lớp {t.class_name} có hai GV chủ nhiệm: "
                                 f"'{homeroom[t.class_name].title}' và '{t.title}'")
            homeroom[t.class_name] = t
        else:
            key = (t.role, t.index)
            if key in keys:
                raise InputError(f"Trùng chức vụ '{t.role} {t.index}' (dòng {keys[key].row} và {t.row})")
            keys[key] = t
    if not homeroom:
        raise InputError("Không có GV chủ nhiệm nào nên không xác định được danh sách lớp")


def read_staff(path: str | Path) -> list[Teacher]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    header_row, cols = _find_columns(ws)
    teachers: list[Teacher] = []
    for r in range(header_row + 1, ws.max_row + 1):
        name = ws.cell(r, cols["name"]).value
        title = ws.cell(r, cols["title"]).value
        lessons = ws.cell(r, cols["lessons"]).value
        if title is None or str(title).strip() == "":
            if name is None and lessons is None:
                continue
            raise InputError(f"Dòng {r}: thiếu chức vụ")
        try:
            teachers.append(build_teacher(name, title, lessons, row=r))
        except InputError as exc:
            raise InputError(f"Dòng {r}: {exc}") from None
    validate(teachers)
    return teachers


def class_sort_key(class_name: str) -> tuple[int, int]:
    grade, num = class_name.split("/")
    return int(grade), int(num)


def classes_from_staff(teachers: list[Teacher]) -> list[str]:
    return sorted((t.class_name for t in teachers if t.class_name), key=class_sort_key)
