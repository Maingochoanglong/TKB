"""Đọc và kiểm tra file Excel danh sách nhân sự.

Chỉ đọc mẫu V8: Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần (chức vụ không ghi số, chương trình tự đánh số
theo thứ tự dòng). Các cột khác bị bỏ qua.

Chức vụ hợp lệ: Chủ Nhiệm, Bộ Môn, Quản Lý, hoặc tên một môn trong sheet CHƯƠNG TRÌNH HỌC (GV chuyên
biệt của môn đó). Danh sách môn lấy từ file vào nên không có danh sách chức vụ cố định trong code.
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
    title: str  # chức vụ chuẩn hóa, dùng làm mã giáo viên, vd "bộ môn 5"
    role: str  # "chủ nhiệm", "bộ môn", "quản lý", hoặc một chức vụ chuyên biệt
    index: int | None  # số thứ tự trong chức vụ (không áp dụng cho chủ nhiệm)
    class_name: str | None  # lớp chủ nhiệm, vd "1/1"
    max_lessons: int
    supplementary: bool = False
    row: int | None = None  # dòng trong file Excel gốc
    label: str = ""  # chức vụ như ghi trong file, vd "Tiếng Anh"; trống = dùng `role`

    @property
    def grade(self) -> int | None:
        return int(self.class_name.split("/")[0]) if self.class_name else None

    @property
    def code(self) -> str:
        """Mã GV hiển thị trong các file ra, vd "Bộ Môn 5", "Chủ Nhiệm 1/1"."""
        return f"{self.label or self.role} {self.class_name or self.index}"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).strip().lower()
    return re.sub(r"\s+", " ", text)


def clean_name(text) -> str:
    """Chữ trong file, bỏ khoảng trắng thừa (giữ hoa thường)."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text)).strip())


def subject_key(name) -> str:
    """Khóa so khớp tên môn/chức vụ: không phân biệt hoa thường, dấu câu và chữ "và"."""
    words = re.sub(r"[^\w\s]", " ", normalize(name)).split()
    return " ".join(w for w in words if w != "và")


SPECIAL_ROLES = (config.ROLE_HOMEROOM, config.ROLE_GENERAL, config.ROLE_MANAGER)


def role_errors(teachers: list[Teacher], subjects) -> list[str]:
    """Chức vụ không phải Chủ Nhiệm/Bộ Môn/Quản Lý và không trùng tên môn nào của chương trình học."""
    keys = {subject_key(s) for s in subjects}
    bad: dict[str, list[str]] = {}
    for t in teachers:
        if t.role not in SPECIAL_ROLES and subject_key(t.role) not in keys:
            bad.setdefault(t.label or t.role, []).append(str(t.row) if t.row else "?")
    valid = ", ".join(config.ROLE_LABELS[r] for r in SPECIAL_ROLES)
    return [f"Dòng {', '.join(rows)}: chức vụ '{label}' không xác định (hợp lệ: {valid} hoặc đúng tên một môn "
            f"trong sheet {config.PROGRAM_SHEET})" for label, rows in bad.items()]


def canonical_title(role: str, index: int | None, class_name: str | None) -> str:
    return f"{role} {class_name}" if role == config.ROLE_HOMEROOM else f"{role} {index}"


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


def find_sheet(wb, name: str):
    """Sheet có tên `name` (không phân biệt hoa thường), hoặc None."""
    return next((ws for ws in wb.worksheets if normalize(ws.title) == normalize(name)), None)


def staff_sheet(wb):
    """Sheet nhân sự: sheet tên "NHÂN SỰ" nếu có, không thì sheet đầu tiên."""
    return find_sheet(wb, config.STAFF_SHEET) or wb.worksheets[0]


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _find_columns(ws) -> tuple[int, dict[str, int]]:
    """Dòng tiêu đề và vị trí các cột (mẫu V8). Bắt buộc: Họ và Tên, Chức Vụ, Số Tiết/Tuần; không bắt buộc: Lớp, STT."""
    wanted = {"họ và tên": "name", "chức vụ": "title", "số tiết/tuần": "lessons", "số tiết / tuần": "lessons",
              "lớp": "class", "stt": "stt"}
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
    raise InputError("Không tìm thấy dòng tiêu đề có đủ các cột 'Họ và Tên', 'Chức Vụ', 'Số Tiết/Tuần' (mẫu V8)")


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


def make_teacher(name, role: str, index: int | None, class_name: str | None, lessons,
                 row: int | None = None, label: str = "") -> Teacher:
    title = canonical_title(role, index, class_name)
    return Teacher(
        name=str(name).strip() if name is not None else "",
        title=title,
        role=role,
        index=index,
        class_name=class_name,
        max_lessons=_to_lessons(lessons, title),
        row=row,
        label=label,
    )


def validate(teachers: list[Teacher]) -> None:
    """Báo mọi lỗi trùng lặp cùng lúc (mỗi lỗi một dòng)."""
    errors: list[str] = []
    homeroom: dict[str, Teacher] = {}
    keys: dict[tuple[str, int], Teacher] = {}
    for t in teachers:
        if t.class_name:
            if t.class_name in homeroom:
                errors.append(f"Lớp {t.class_name} có hai Chủ Nhiệm (dòng {homeroom[t.class_name].row} "
                              f"và {t.row})")
            else:
                homeroom[t.class_name] = t
        else:
            key = (t.role, t.index)
            if key in keys:
                errors.append(f"Trùng chức vụ '{t.role} {t.index}' (dòng {keys[key].row} và {t.row})")
            else:
                keys[key] = t
    if not homeroom:
        errors.append("Không có Chủ Nhiệm nào nên không xác định được danh sách lớp")
    if errors:
        raise InputError("\n".join(errors))


def read_staff(path: str | Path, subjects=None) -> list[Teacher]:
    """Đọc sheet nhân sự; `subjects`: các môn của chương trình học để kiểm tra chức vụ (None = không kiểm)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = staff_sheet(wb)
    header_row, cols = _find_columns(ws)

    def cell(r: int, key: str):
        return ws.cell(r, cols[key]).value if key in cols else None

    rows: list[list] = []  # [dòng, tên, chức vụ, stt, lớp, số tiết, chữ chức vụ trong file]
    errors: list[str] = []
    for r in range(header_row + 1, ws.max_row + 1):
        name, title, lessons, cls = cell(r, "name"), cell(r, "title"), cell(r, "lessons"), cell(r, "class")
        if _blank(title):
            if not all(_blank(v) for v in (name, lessons, cls)):
                errors.append(f"Dòng {r}: thiếu chức vụ")
            continue
        try:
            if re.search(r"\d", str(title)):
                raise InputError(f"Chức Vụ không ghi số thứ tự (chương trình tự đánh số theo thứ tự dòng): {title!r}")
            role, label = normalize(title), clean_name(title)
            index = class_name = None
            if role == config.ROLE_HOMEROOM:
                if _blank(cls):
                    raise InputError("Chủ Nhiệm phải ghi Lớp dạng khối/số thứ tự, vd '1/1'")
                class_name = parse_class(cls)
            elif not _blank(cls):
                raise InputError(f"chỉ Chủ Nhiệm mới ghi Lớp (chức vụ đang là {title!r})")
            rows.append([r, name, role, index, class_name, lessons, label])
        except InputError as exc:
            errors.append(f"Dòng {r}: {exc}")

    # Đánh số thứ tự trong từng chức vụ theo thứ tự dòng (Chủ Nhiệm dùng lớp thay cho số).
    count: dict[str, int] = defaultdict(int)
    for row in rows:
        if row[2] != config.ROLE_HOMEROOM:
            count[row[2]] += 1
            row[3] = count[row[2]]

    teachers: list[Teacher] = []
    for r, name, role, index, class_name, lessons, label in rows:
        try:
            teachers.append(make_teacher(name, role, index, class_name, lessons, row=r, label=label))
        except InputError as exc:
            errors.append(f"Dòng {r}: {exc}")
    try:
        validate(teachers)
    except InputError as exc:
        errors.append(str(exc))
    if subjects is not None:
        errors += role_errors(teachers, subjects)
    errors = [line for err in errors for line in err.split("\n")]
    if errors:
        raise InputError(f"File nhân sự có {len(errors)} lỗi:\n  " + "\n  ".join(errors))
    return teachers


def class_sort_key(class_name: str) -> tuple[int, int]:
    grade, num = class_name.split("/")
    return int(grade), int(num)


def classes_from_staff(teachers: list[Teacher]) -> list[str]:
    return sorted((t.class_name for t in teachers if t.class_name), key=class_sort_key)
