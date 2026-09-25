"""Đọc và kiểm tra file Excel danh sách nhân sự.

Mẫu V8: Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Chế Độ (chức vụ không ghi số, chương trình tự đánh
số theo thứ tự dòng). Vẫn đọc được mẫu cũ: Tên | Chức vụ ("bộ môn 5 ts") | Số tiết [| Thai sản].

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
    title: str  # chức vụ chuẩn hóa, dùng làm mã giáo viên, vd "bộ môn 5 ts"
    role: str  # "chủ nhiệm", "bộ môn", "quản lý", hoặc một chức vụ chuyên biệt
    index: int | None  # số thứ tự trong chức vụ (không áp dụng cho chủ nhiệm)
    class_name: str | None  # lớp chủ nhiệm, vd "1/1"
    maternity: bool
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


_TITLE_RE = re.compile(r"^(?P<role>\D+?)\s+(?P<idx>\d+(?:\s*/\s*\d+)?)(?:\s+(?P<ts>ts))?$")


def parse_title(raw: str) -> tuple[str, int | None, str | None, bool]:
    """Tách chức vụ kiểu cũ ("bộ môn 5 ts", "chủ nhiệm 1/1") thành (role, index, lớp chủ nhiệm, thai sản)."""
    text = normalize(raw)
    m = _TITLE_RE.match(text)
    if not m:
        raise InputError(f"Chức vụ không đúng dạng '<chức vụ> <số thứ tự>[ ts]': {raw!r}")
    role = m.group("role").strip()
    idx = re.sub(r"\s+", "", m.group("idx"))
    maternity = m.group("ts") is not None
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


def find_sheet(wb, name: str):
    """Sheet có tên `name` (không phân biệt hoa thường), hoặc None."""
    return next((ws for ws in wb.worksheets if normalize(ws.title) == normalize(name)), None)


def staff_sheet(wb):
    """Sheet nhân sự: sheet tên "NHÂN SỰ" nếu có, không thì sheet đầu tiên."""
    return find_sheet(wb, config.STAFF_SHEET) or wb.worksheets[0]


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _find_columns(ws) -> tuple[int, dict[str, int]]:
    """Dòng tiêu đề và vị trí các cột. Bắt buộc: tên, chức vụ, số tiết; không bắt buộc: lớp, chế độ."""
    wanted = {"tên": "name", "họ và tên": "name", "họ tên": "name", "chức vụ": "title",
              "số tiết": "lessons", "số tiết/tuần": "lessons", "số tiết / tuần": "lessons",
              "thai sản": "maternity", "chế độ": "maternity", "lớp": "class", "stt": "stt"}
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


MATERNITY_LABEL = "Có"  # giá trị cột Chế Độ của người hưởng chế độ thai sản
_YES = {"thai sản", "thai san", "ts", "có", "co", "x"}
_NO = {"", "không", "khong", "bình thường", "binh thuong"}


def to_maternity(value) -> bool:
    """Cột Chế Độ (hoặc Thai sản ở mẫu cũ): "Có"/"Thai sản" là đang hưởng chế độ thai sản."""
    if value is None:
        return False
    text = normalize(value)
    if text in _YES:
        return True
    if text in _NO:
        return False
    raise InputError(f"cột Chế Độ chỉ ghi '{MATERNITY_LABEL}' (thai sản) hoặc để trống, đang ghi {value!r}")


def build_teacher(name: str, raw_title: str, lessons, row: int | None = None,
                  maternity: bool = False) -> Teacher:
    """Chức vụ kèm số thứ tự (mẫu cũ); chữ "ts" sau chức vụ cũng được hiểu là thai sản."""
    role, index, class_name, ts = parse_title(raw_title)
    return make_teacher(name, role, index, class_name, maternity or ts, lessons, row)


def make_teacher(name, role: str, index: int | None, class_name: str | None, maternity: bool, lessons,
                 row: int | None = None, label: str = "") -> Teacher:
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

    rows: list[list] = []  # [dòng, tên, chức vụ, stt, lớp, thai sản, số tiết, chữ chức vụ trong file]
    errors: list[str] = []
    for r in range(header_row + 1, ws.max_row + 1):
        name, title, lessons, cls = cell(r, "name"), cell(r, "title"), cell(r, "lessons"), cell(r, "class")
        if _blank(title):
            if not all(_blank(v) for v in (name, lessons, cls)):
                errors.append(f"Dòng {r}: thiếu chức vụ")
            continue
        try:
            maternity = to_maternity(cell(r, "maternity"))
            label = ""
            if not re.search(r"\d", str(title)):  # mẫu V8: chỉ ghi tên chức vụ, số thứ tự tự đánh
                role, label = normalize(title), clean_name(title)
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
            rows.append([r, name, role, index, class_name, maternity, lessons, label])
        except InputError as exc:
            errors.append(f"Dòng {r}: {exc}")

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
    for r, name, role, index, class_name, maternity, lessons, label in rows:
        try:
            teachers.append(make_teacher(name, role, index, class_name, maternity, lessons, row=r, label=label))
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
