"""Đọc và kiểm tra file Excel danh sách nhân sự.

Mẫu V7: Họ và Tên | Chức Vụ | Lớp | Chế độ | Số Tiết/Tuần (chức vụ không ghi số, chương trình tự đánh
số theo thứ tự dòng). Vẫn đọc được mẫu cũ: Tên | Chức vụ ("bộ môn 5 ts") | Số tiết [| Thai sản].
"""
from __future__ import annotations

import datetime
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from . import config


class InputError(ValueError):
    """Lỗi dữ liệu đầu vào."""


@dataclass
class Teacher:
    name: str
    title: str  # chức vụ chuẩn hóa, dùng làm mã giáo viên, vd "bộ môn 5 ts"
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


def role_names() -> str:
    return ", ".join(config.ROLE_LABELS.get(r, r) for r in config.ROLE_LABELS)


def parse_title(raw: str) -> tuple[str, int | None, str | None, bool]:
    """Tách chức vụ thành (role, index, lớp chủ nhiệm, thai sản)."""
    text = normalize(raw)
    if not re.search(r"\d", text):
        raise InputError(f"Chức vụ không xác định: {raw!r} (hợp lệ: {role_names()})")
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


_CLASS_RE = re.compile(r"^(\d+)\s*/\s*(\d+)$")


def parse_class(value) -> str:
    """Cột Lớp: khối/số thứ tự, vd "1/1"."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        raise InputError(f"cột Lớp bị Excel đổi thành ngày tháng ({value:%d/%m}); hãy chọn lớp từ danh sách "
                         f"thả xuống hoặc định dạng cột Lớp là Text")
    m = _CLASS_RE.match(normalize(value))
    if not m:
        raise InputError(f"cột Lớp phải ghi dạng khối/số thứ tự, vd '1/1', đang ghi {value!r}")
    return f"{int(m.group(1))}/{int(m.group(2))}"


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _find_columns(ws) -> tuple[int, dict[str, int]]:
    """Dòng tiêu đề và vị trí các cột. Bắt buộc: tên, chức vụ, số tiết; không bắt buộc: lớp, chế độ."""
    wanted = {"tên": "name", "họ và tên": "name", "họ tên": "name", "chức vụ": "title",
              "số tiết": "lessons", "số tiết/tuần": "lessons", "số tiết / tuần": "lessons",
              "thai sản": "maternity", "chế độ": "maternity", "lớp": "class"}
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 20)):
        found = {}
        for cell in row:
            if cell.value is None:
                continue
            key = normalize(cell.value)
            if key in wanted:
                found[wanted[key]] = cell.column
        if {"name", "title", "lessons"} <= found.keys():
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


MATERNITY_LABEL = "Thai sản"  # giá trị cột Chế độ
_YES = {"thai sản", "thai san", "ts", "có", "co", "x"}
_NO = {"", "không", "khong", "bình thường", "binh thuong"}


def to_maternity(value) -> bool:
    """Cột Chế độ (mẫu V7) hoặc Thai sản (mẫu V6): "Thai sản"/"Có" là đang hưởng chế độ thai sản."""
    if value is None:
        return False
    text = normalize(value)
    if text in _YES:
        return True
    if text in _NO:
        return False
    raise InputError(f"cột Chế độ chỉ ghi '{MATERNITY_LABEL}' hoặc để trống, đang ghi {value!r}")


def build_teacher(name: str, raw_title: str, lessons, row: int | None = None,
                  maternity: bool = False) -> Teacher:
    """Chức vụ kèm số thứ tự (mẫu cũ); chữ "ts" sau chức vụ cũng được hiểu là thai sản."""
    role, index, class_name, ts = parse_title(raw_title)
    return make_teacher(name, role, index, class_name, maternity or ts, lessons, row)


def make_teacher(name, role: str, index: int | None, class_name: str | None, maternity: bool, lessons,
                 row: int | None = None) -> Teacher:
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

    def cell(r: int, key: str):
        return ws.cell(r, cols[key]).value if key in cols else None

    rows: list[list] = []  # [dòng, tên, chức vụ, stt, lớp, thai sản, số tiết]
    for r in range(header_row + 1, ws.max_row + 1):
        name, title, lessons, cls = cell(r, "name"), cell(r, "title"), cell(r, "lessons"), cell(r, "class")
        if _blank(title):
            if all(_blank(v) for v in (name, lessons, cls)):
                continue
            raise InputError(f"Dòng {r}: thiếu chức vụ")
        try:
            maternity = to_maternity(cell(r, "maternity"))
            role = normalize(title)
            if role in known_roles():  # mẫu V7: chỉ ghi tên chức vụ, số thứ tự tự đánh
                index = class_name = None
                if role == config.ROLE_HOMEROOM:
                    if _blank(cls):
                        raise InputError("Chủ Nhiệm phải ghi Lớp dạng khối/số thứ tự, vd '1/1'")
                    class_name = parse_class(cls)
                elif not _blank(cls):
                    raise InputError(f"chỉ Chủ Nhiệm mới ghi Lớp (chức vụ đang là {title!r})")
            else:
                role, index, class_name, ts = parse_title(title)
                maternity = maternity or ts
                if not _blank(cls) and parse_class(cls) != class_name:
                    raise InputError(f"chức vụ {title!r} không khớp cột Lớp {cls!r}")
            rows.append([r, name, role, index, class_name, maternity, lessons])
        except InputError as exc:
            raise InputError(f"Dòng {r}: {exc}") from None

    # Đánh số thứ tự cho các dòng chỉ ghi tên chức vụ, theo thứ tự dòng, bỏ qua số đã dùng.
    used: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if row[3] is not None:
            used[row[2]].add(row[3])
    for row in rows:
        if row[2] != config.ROLE_HOMEROOM and row[3] is None:
            n = 1
            while n in used[row[2]]:
                n += 1
            used[row[2]].add(n)
            row[3] = n

    teachers: list[Teacher] = []
    for r, name, role, index, class_name, maternity, lessons in rows:
        try:
            teachers.append(make_teacher(name, role, index, class_name, maternity, lessons, row=r))
        except InputError as exc:
            raise InputError(f"Dòng {r}: {exc}") from None
    validate(teachers)
    return teachers


def class_sort_key(class_name: str) -> tuple[int, int]:
    grade, num = class_name.split("/")
    return int(grade), int(num)


def classes_from_staff(teachers: list[Teacher]) -> list[str]:
    return sorted((t.class_name for t in teachers if t.class_name), key=class_sort_key)
