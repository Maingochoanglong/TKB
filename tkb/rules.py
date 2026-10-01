"""Sheet QUY ĐỊNH của file vào: các luật nghiệp vụ nhà trường tự sửa được trong Excel, không cần sửa mã nguồn.

Sheet gồm các cột Quy định | Giá trị | Ghi chú, mỗi dòng một quy định (chương trình chỉ đọc hai cột đầu). Quy định
nào không có dòng (hoặc file vào không có sheet này) thì dùng giá trị mặc định trong tkb/config.py, nên file vào cũ
vẫn chạy như trước. Tên môn ghi như trong sheet CHƯƠNG TRÌNH HỌC (so khớp không phân biệt hoa thường, dấu câu và
chữ "và"); nhiều môn cách nhau bằng dấu phẩy; ô Giá trị để trống là "không có môn nào".

Trọng số mục tiêu (config.Weights), tham số xếp giờ và số tiết bù tối đa (main.py) vẫn ở trong mã nguồn.
"""
from __future__ import annotations

import copy
import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from . import config
from .staff import InputError, _fold, clean_name, find_sheet, normalize, parse_class, subject_key

HEADERS = ("Quy định", "Giá trị", "Ghi chú")
CODE_HEADER = "Mã Quy Định"  # cột của sheet TKB đã xếp (config.SAVED_SHEET) ghi mã các quy định lúc xếp


@dataclass(frozen=True)
class Rule:
    label: str  # chữ ở cột Quy định
    attr: str  # hằng số trong tkb/config.py; khung giờ: một trong FRAME (gộp thành DAYS, MORNING...)
    kind: str  # cách đọc/ghi cột Giá trị (xem _parse, _text)
    note: str  # cột Ghi chú


# Khung giờ: bốn dòng gộp thành config.DAYS, MORNING, AFTERNOON, DAY_SESSIONS.
FRAME = ("days", "afternoon_days", "morning_periods", "afternoon_periods")
FRAME_ATTRS = ("DAYS", "MORNING", "AFTERNOON", "DAY_SESSIONS")
MAX_DAYS = 6  # Thứ 2 – Thứ 7
MAX_PERIODS = 12  # số tiết tối đa mỗi ngày

RULES: tuple[Rule, ...] = (
    Rule("Ngày học", "days", "frame_days",
         "Các ngày học, liền nhau từ Thứ 2 (có thể thêm Thứ 7). Ngày nào cũng học buổi sáng."),
    Rule("Ngày học buổi chiều", "afternoon_days", "days",
         "Các ngày có buổi chiều; để trống là không học buổi chiều."),
    Rule("Số tiết buổi sáng", "morning_periods", "count",
         "Buổi sáng là tiết 1 đến tiết này."),
    Rule("Số tiết buổi chiều", "afternoon_periods", "count0",
         "Buổi chiều là các tiết tiếp theo, vd sáng 4 tiết, chiều 3 tiết thì chiều là tiết 5, 6, 7."),
    Rule("Môn HĐTN", "HDTN", "subject",
         "Môn chào cờ, sinh hoạt lớp: có các tiết cố định dưới đây."),
    Rule("Tiết HĐTN cố định", "HDTN_FIXED_SLOTS", "slots",
         "Luật cứng: mọi lớp học môn HĐTN đúng các ô này, vd Thứ 2 tiết 1, Thứ 6 tiết 4."),
    Rule("Ngày xếp tiết HĐTN còn lại", "HDTN_FLEX_DAYS", "days",
         "Luật cứng: các tiết HĐTN còn lại chỉ xếp vào các ngày này (mục tiêu mềm: gần cuối buổi)."),
    Rule("Tiết luôn do GVCN dạy", "HOMEROOM_PERIODS", "periods",
         "Luật cứng: tiết này ở mọi ngày do GVCN của lớp dạy; để trống là không có."),
    Rule("Môn GVCN nhận trọn", "HOMEROOM_PRIORITY", "subject_list",
         "GVCN nhận hết các môn này của lớp mình; luật cứng: môn nào phải chia cho người khác thì tiết đầu tiên "
         "trong tuần do GVCN dạy."),
    Rule("Thứ tự cắt khi GVCN vượt định mức", "HOMEROOM_CUT_ORDER", "subject_list",
         "Các môn trên vượt định mức thì cắt bớt theo thứ tự này, mỗi môn GVCN giữ ít nhất 1 tiết."),
    Rule("Thứ tự nhận thêm khi GVCN thiếu định mức", "HOMEROOM_FILL_ORDER", "subject_list",
         "GVCN nhận thêm các môn này theo thứ tự cho đủ định mức (không nhận môn của GV chuyên biệt)."),
    Rule("Môn chỉ GVCN dạy", "HOMEROOM_ONLY_SUBJECTS", "subject_set",
         "Luật cứng: chỉ GVCN của lớp được dạy."),
    Rule("Môn GV bộ môn không dạy", "GENERAL_FORBIDDEN_SUBJECTS", "subject_set",
         "GV bộ môn dạy được mọi môn trừ các môn này; môn chưa có GV chuyên biệt thì chương trình tuyển thêm."),
    Rule("Quản lý dạy", "MANAGER_RULES", "managers",
         "Môn và khối quản lý được dạy, vd Kỹ năng sống khối 4; chỉ vài lớp: Kỹ năng sống khối 4 lớp 4/1, 4/2. "
         "Nhiều mục cách nhau bằng dấu chấm phẩy."),
    Rule("Chức vụ được dạy bù", "OVERTIME_ROLES", "roles",
         "Chỉ ghi Chủ Nhiệm, Bộ Môn. GVCN chỉ bù ở lớp mình và bù trước; bộ môn bù khi GVCN đã bù hết mức."),
    Rule("Môn chuyên biệt GVCN được bù", "HOMEROOM_OVERTIME_SPECIALIST", "subject_set",
         "Môn của GV chuyên biệt mà GVCN vẫn được dạy bù ở lớp mình (nhận sau cùng)."),
    Rule("Môn tăng cường đi với môn chính", "SUBJECT_GROUPS", "pairs",
         "Mỗi mục: môn tăng cường = môn chính, cách nhau bằng dấu chấm phẩy. Hai môn tính chung một nhóm môn; "
         "luật cứng: tiết tăng cường đứng sau mọi tiết chính trong ngày và ngày đó phải có tiết chính."),
    Rule("Số tiết tối đa một nhóm môn mỗi buổi", "SESSION_GROUP_LIMIT", "count",
         "Luật cứng; môn có từ 2 tiết trong một buổi thì các tiết đó phải liền nhau."),
    Rule("Số tiết tối đa mỗi ngày của môn", "DAILY_LIMITS", "limits",
         "Luật cứng, vd Toán = 1; chỉ áp dụng khi số tiết/tuần của môn không quá số ngày học."),
    Rule("Ghép cặp 2 tiết liền khi nhóm môn có từ", "PAIR_MIN_LESSONS", "count",
         "Luật cứng: nhóm môn có từ ngần ấy tiết/tuần và tổng số tiết chẵn thì xếp thành các cặp 2 tiết liền, "
         "cùng người dạy."),
    Rule("Nhóm môn không ghép cặp", "PAIR_EXCLUDED", "subject_set",
         "Các nhóm môn (ghi môn chính) không áp dụng luật ghép cặp ở trên."),
    Rule("Môn nặng", "HEAVY_SUBJECTS", "subject_set",
         "Mục tiêu mềm: hạn chế xếp các môn này vào các tiết ở dòng dưới."),
    Rule("Tiết hạn chế môn nặng", "HEAVY_LATE_PERIODS", "periods",
         "Mục tiêu mềm: mỗi tiết môn nặng ở các tiết này bị trừ điểm."),
    Rule("Môn ưu tiên buổi sáng", "MORNING_SUBJECTS", "subject_set",
         "Mục tiêu mềm: mỗi tiết các môn này ở buổi chiều bị trừ điểm, và các môn này được rải đều hơn."),
    Rule("Tên môn viết tắt trong TKB", "DISPLAY_NAMES", "names",
         "Mỗi mục: tên môn = chữ ghi trong ô TKB, cách nhau bằng dấu chấm phẩy; môn khác ghi đúng tên."),
)
BY_KEY = {subject_key(r.label): r for r in RULES}
# Thứ tự đọc: khung giờ trước (để kiểm tra ngày, tiết), rồi tên viết tắt và môn HĐTN (để hiểu tên môn).
_FIRST = (*FRAME, "DISPLAY_NAMES", "HDTN")
_ORDER = sorted(RULES, key=lambda r: _FIRST.index(r.attr) if r.attr in _FIRST else len(_FIRST))
ATTRS = (*FRAME_ATTRS, *(r.attr for r in RULES if r.attr not in FRAME))
DEFAULTS = {attr: copy.deepcopy(getattr(config, attr)) for attr in ATTRS}  # giá trị mặc định trong tkb/config.py
DEFAULT_SUBJECTS = tuple(config.rule_subjects())  # tên môn trong tkb/config.py (để khớp tên môn ghi trong sheet)


def _frame_now() -> dict[str, object]:
    """Bốn dòng khung giờ theo config hiện tại."""
    return {"days": list(range(len(config.DAYS))),
            "afternoon_days": [d for d, ss in sorted(config.DAY_SESSIONS.items())
                               if any(s.name == config.AFTERNOON.name for s in ss)],
            "morning_periods": len(config.MORNING.periods),
            "afternoon_periods": len(config.AFTERNOON.periods)}


def _build_frame(f: dict[str, object]) -> dict[str, object]:
    """Bốn dòng khung giờ -> config.DAYS, MORNING, AFTERNOON, DAY_SESSIONS."""
    m, a = f["morning_periods"], f["afternoon_periods"]
    morning = config.Session(config.MORNING.name, tuple(range(1, m + 1)))
    afternoon = config.Session(config.AFTERNOON.name, tuple(range(m + 1, m + a + 1)))
    days = [f"Thứ {d + 2}" for d in f["days"]]
    sessions = {d: (morning, afternoon) if d in f["afternoon_days"] and a else (morning,) for d in f["days"]}
    return {"DAYS": days, "MORNING": morning, "AFTERNOON": afternoon, "DAY_SESSIONS": sessions}


def _text(value) -> str:
    """Chữ trong ô Giá trị, giữ chỗ xuống dòng (xuống dòng trong ô cũng tách mục như dấu phẩy); số nguyên Excel lưu
    dạng 7.0 thì đọc là 7."""
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        value = int(value)
    return "\n".join(clean_name(line) for line in str(value).splitlines() if line.strip())


def _items(text: str, separators: str = ",;\n") -> list[str]:
    return [part.strip() for part in re.split(f"[{re.escape(separators)}]", text) if part.strip()]


class _Reader:
    """Đọc giá trị từng quy định; tên môn được đổi về tên dùng trong tkb/config.py nếu khớp."""

    def __init__(self):
        self.frame = _frame_now()
        self.labels: dict[str, str] = {}  # khóa chữ viết tắt -> môn
        self.hdtn = config.HDTN

    def subject(self, name: str) -> str:
        key = subject_key(name)
        if key in self.labels:
            return self.labels[key]
        known = {subject_key(s): s for s in [self.hdtn, *DEFAULT_SUBJECTS]}
        return known.get(key, clean_name(name))

    def day(self, item: str, frame: bool = True) -> int:
        """Ngày ghi dạng Thứ 2, T2 hoặc 2 -> chỉ số 0, 1...; `frame`: phải là ngày học."""
        m = re.fullmatch(r"(?:thu|t)?\s*(\d)", _fold(item))
        day = int(m.group(1)) - 2 if m else -1
        if not 0 <= day < MAX_DAYS:
            raise InputError(f"ngày phải ghi dạng Thứ 2 … Thứ 7, đang ghi {item!r}")
        if frame and day not in self.frame["days"]:
            raise InputError(f"{item} không phải ngày học (dòng Ngày học)")
        return day

    def slots(self) -> set[tuple[int, int]]:
        f = self.frame
        m, a = f["morning_periods"], f["afternoon_periods"]
        return {(d, p) for d in f["days"]
                for p in range(1, m + (a if d in f["afternoon_days"] else 0) + 1)}

    def period(self, item: str) -> int:
        if not re.fullmatch(r"\d+", item):
            raise InputError(f"tiết phải là số, đang ghi {item!r}")
        p = int(item)
        if not any(p == q for _, q in self.slots()):
            raise InputError(f"không có tiết {p} trong khung giờ")
        return p

    def parse(self, rule: Rule, text: str):
        kind = rule.kind
        if kind in ("count", "count0"):
            if not re.fullmatch(r"\d+", text):
                raise InputError(f"ghi một số nguyên, đang ghi {text!r}")
            n = int(text)
            low = 0 if kind == "count0" else 1
            high = MAX_PERIODS if rule.attr in FRAME else 99
            if not low <= n <= high:
                raise InputError(f"ghi số từ {low} đến {high}")
            return n
        if kind == "subject":
            if not text:
                raise InputError("chưa ghi tên môn")
            return self.subject(text)
        if kind in ("subject_list", "subject_set"):
            names = list(dict.fromkeys(self.subject(s) for s in _items(text)))
            return names if kind == "subject_list" else set(names)
        if kind == "frame_days":
            days = [self.day(s, frame=False) for s in _items(text)]
            if not days or sorted(set(days)) != list(range(max(days) + 1)):
                raise InputError("ghi các ngày liền nhau từ Thứ 2, vd Thứ 2, Thứ 3, Thứ 4, Thứ 5, Thứ 6")
            return sorted(set(days))
        if kind == "days":
            return sorted({self.day(s) for s in _items(text)})
        if kind == "periods":
            return {self.period(s) for s in _items(text)}
        if kind == "slots":
            out = []
            for item in _items(text):
                m = re.fullmatch(r"(?:thu|t)?\s*(\d)\s*[-,]?\s*tiet\s*(\d+)", _fold(item))
                if not m:
                    raise InputError(f"ghi dạng Thứ 2 tiết 1, đang ghi {item!r}")
                slot = (self.day(f"Thứ {m.group(1)}"), int(m.group(2)))
                if slot not in self.slots():
                    raise InputError(f"{item}: không có tiết này trong khung giờ")
                if slot not in out:
                    out.append(slot)
            return out
        if kind in ("pairs", "limits", "names"):
            out = {}
            for item in _items(text, ";,\n"):
                left, sep, right = item.partition("=")
                if not sep or not left.strip() or not right.strip():
                    raise InputError(f"mỗi mục ghi dạng A = B, đang ghi {item!r}")
                key = self.subject(left)
                if kind == "names":
                    out[key] = clean_name(right)
                elif kind == "limits":
                    if not re.fullmatch(r"\s*\d+\s*", right) or int(right) < 1:
                        raise InputError(f"{item}: số tiết phải là số nguyên dương")
                    out[key] = int(right)
                else:
                    out[key] = self.subject(right)
            if kind == "pairs":
                for extra, main in out.items():
                    if extra == main or main in out:
                        raise InputError(f"{extra} = {main}: môn chính không được là môn tăng cường")
            return out
        if kind == "roles":
            allowed = {normalize(config.ROLE_LABELS[r]): r for r in (config.ROLE_HOMEROOM, config.ROLE_GENERAL)}
            roles = set()
            for item in _items(text):
                if normalize(item) not in allowed:
                    raise InputError(f"chỉ ghi Chủ Nhiệm, Bộ Môn, đang ghi {item!r}")
                roles.add(allowed[normalize(item)])
            return roles
        if kind == "managers":
            out = []
            for part in _items(text, ";\n"):
                pieces = [part] if re.search(r"\b(lớp|lop)\b", part, re.I) else _items(part, ",")
                for item in pieces:
                    m = re.fullmatch(r"(.+?)\s+(?:khối|khoi)\s*(\d+)(?:\s*,?\s*\(?\s*(?:lớp|lop)\s+(.+?)\)?)?",
                                     clean_name(item), re.I)
                    if not m:
                        raise InputError(f"ghi dạng Kỹ năng sống khối 4, đang ghi {item!r}")
                    classes = tuple(parse_class(c) for c in _items(m.group(3))) if m.group(3) else None
                    out.append(config.ManagerRule(subject=self.subject(m.group(1)), grade=int(m.group(2)),
                                                  classes=classes))
            return out
        raise AssertionError(kind)


def read_rules(path: str | Path) -> dict[str, object] | None:
    """Đọc sheet QUY ĐỊNH của file vào. Trả về {hằng số trong config: giá trị} của các quy định có trong sheet
    (khung giờ gộp thành DAYS, MORNING, AFTERNOON, DAY_SESSIONS); None nếu file không có sheet này. Báo mọi lỗi
    cùng lúc (InputError)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = find_sheet(wb, config.RULES_SHEET)
    if ws is None:
        return None
    header_row = label_col = value_col = None
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 20)):
        cols = {normalize(c.value): c.column for c in row if c.value is not None}
        if normalize(HEADERS[0]) in cols and normalize(HEADERS[1]) in cols:
            header_row, label_col, value_col = row[0].row, cols[normalize(HEADERS[0])], cols[normalize(HEADERS[1])]
            break
    if header_row is None:
        raise InputError(f"Sheet {config.RULES_SHEET} phải có dòng tiêu đề '{HEADERS[0]}', '{HEADERS[1]}'")
    raw: dict[str, tuple[int, str]] = {}
    errors: list[tuple[int, str]] = []  # (dòng, lỗi)
    for r in range(header_row + 1, ws.max_row + 1):
        label = ws.cell(r, label_col).value
        if label is None or str(label).strip() == "":
            continue
        rule = BY_KEY.get(subject_key(label))
        if rule is None:
            errors.append((r, f"dòng {r}: không có quy định '{clean_name(label)}'"))
        elif rule.attr in raw:
            errors.append((r, f"dòng {r}: quy định '{rule.label}' bị lặp với dòng {raw[rule.attr][0]}"))
        else:
            raw[rule.attr] = (r, _text(ws.cell(r, value_col).value))
    reader = _Reader()
    values: dict[str, object] = {}
    for rule in _ORDER:
        if rule.attr not in raw:
            continue
        r, text = raw[rule.attr]
        try:
            value = reader.parse(rule, text)
        except InputError as exc:
            errors.append((r, f"dòng {r} ({rule.label}): {exc}"))
            continue
        if rule.attr in FRAME:
            reader.frame[rule.attr] = value
        else:
            values[rule.attr] = value
            if rule.attr == "DISPLAY_NAMES":
                reader.labels = {subject_key(label): s for s, label in value.items()}
            elif rule.attr == "HDTN":
                reader.hdtn = value
    frame = reader.frame
    last = ws.max_row + 1  # lỗi chung của khung giờ ghi sau cùng
    if frame["afternoon_days"] and not frame["afternoon_periods"]:
        errors.append((last, "Ngày học buổi chiều có ngày nhưng Số tiết buổi chiều là 0"))
    if any(d not in frame["days"] for d in frame["afternoon_days"]):
        errors.append((last, "Ngày học buổi chiều phải là ngày học"))
    if errors:
        lines = [text for _, text in sorted(errors, key=lambda e: e[0])]
        raise InputError(f"Sheet {config.RULES_SHEET} có {len(lines)} lỗi:\n  " + "\n  ".join(lines))
    if any(f in raw for f in FRAME):
        values.update(_build_frame(frame))
    return values


@contextmanager
def applied(values: dict[str, object] | None):
    """Dùng các quy định đọc từ sheet QUY ĐỊNH trong khối `with`; ra khỏi khối thì trả lại giá trị cũ."""
    old = {attr: getattr(config, attr) for attr in (values or {})}
    try:
        for attr, value in (values or {}).items():
            setattr(config, attr, value)
        yield
    finally:
        for attr, value in old.items():
            setattr(config, attr, value)


def changed(values: dict[str, object] | None) -> list[str]:
    """Các quy định trong sheet khác giá trị mặc định trong tkb/config.py (tên ở cột Quy định)."""
    values = values or {}
    out = []
    frame = [a for a in FRAME_ATTRS if a in values and values[a] != DEFAULTS[a]]
    if frame:
        out.append("Khung giờ")
    out += [r.label for r in RULES if r.attr in values and values[r.attr] != DEFAULTS[r.attr]]
    return out


def rule_rows(label=None, order=()) -> list[tuple[str, str, str]]:
    """Các dòng (Quy định, Giá trị, Ghi chú) theo config hiện tại, để ghi sheet QUY ĐỊNH. `label`: tên môn ghi ra
    (mặc định tên trong config), `order`: thứ tự môn (vd thứ tự trong chương trình học) cho các tập môn."""
    label = label or (lambda s: s)
    rank = {s: i for i, s in enumerate(order)}
    sort = lambda subjects: sorted(subjects, key=lambda s: (rank.get(s, len(rank)), subject_key(s)))  # noqa: E731
    frame = _frame_now()
    day = lambda d: config.DAYS[d] if d < len(config.DAYS) else f"Thứ {d + 2}"  # noqa: E731
    rows = []
    for rule in RULES:
        value = frame[rule.attr] if rule.attr in FRAME else getattr(config, rule.attr)
        kind = rule.kind
        if kind in ("count", "count0"):
            text = str(value)
        elif kind == "subject":
            text = label(value)
        elif kind == "subject_list":
            text = ", ".join(label(s) for s in value)
        elif kind == "subject_set":
            text = ", ".join(label(s) for s in sort(value))
        elif kind in ("frame_days", "days"):
            text = ", ".join(day(d) for d in value)
        elif kind == "periods":
            text = ", ".join(map(str, sorted(value)))
        elif kind == "slots":
            text = ", ".join(f"{day(d)} tiết {p}" for d, p in value)
        elif kind == "pairs":
            text = "; ".join(f"{label(a)} = {label(b)}" for a, b in value.items())
        elif kind == "limits":
            text = "; ".join(f"{label(s)} = {n}" for s, n in value.items())
        elif kind == "names":
            text = "; ".join(f"{label(s)} = {n}" for s, n in value.items())
        elif kind == "roles":
            text = ", ".join(config.ROLE_LABELS[r] for r in (config.ROLE_HOMEROOM, config.ROLE_GENERAL)
                             if r in value)
        elif kind == "managers":
            text = "; ".join(f"{label(r.subject)} khối {r.grade}"
                             + (f" lớp {', '.join(r.classes)}" if r.classes else "") for r in value)
        else:
            raise AssertionError(kind)
        rows.append((rule.label, text, rule.note))
    return rows


def code() -> str:
    """Mã của các quy định đang dùng (12 chữ số hex): quy định khác nhau thì mã khác nhau, mọi máy cùng mã."""
    text = "\n".join(f"{label}={value}" for label, value, _ in rule_rows())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12].upper()


def saved_code(path: str | Path) -> str | None:
    """Mã quy định lưu cùng TKB đã xếp (sheet config.SAVED_SHEET, cột CODE_HEADER) của file vào cập nhật; None nếu
    không có (file của bản trước chưa lưu mã này)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = find_sheet(wb, config.SAVED_SHEET)
    if ws is None:
        return None
    for c in range(1, ws.max_column + 1):
        if ws.cell(1, c).value is not None and normalize(ws.cell(1, c).value) == normalize(CODE_HEADER):
            value = ws.cell(2, c).value
            return str(value).strip() if value is not None else None
    return None
