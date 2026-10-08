"""Quy định nghiệp vụ trong file vào: nhà trường tự sửa trong Excel, không cần sửa mã nguồn.

Một quy ước cho mọi ô: mỗi quy định là một cột (bảng quy định chung: một dòng), mỗi ô chỉ ghi Có, Không hoặc một
số nguyên dương; ô trống là Không (hoặc không áp dụng). Riêng cột Tên trong TKB ghi chữ.
- Sheet CHƯƠNG TRÌNH HỌC: sau các cột Khối là các cột quy định của môn (Tên trong TKB, Môn HĐTN, GVCN nhận trọn...),
  nên tên môn chỉ ghi một chỗ.
- Sheet QUY ĐỊNH: ba bảng xếp chồng, cách nhau một dòng trống:
  Quy định | Giá trị (số tiết mỗi buổi, giới hạn nhóm môn, ghép cặp, ai được dạy bù);
  Ngày | Học buổi sáng | Học buổi chiều | Tiết HĐTN cố định | Xếp tiết HĐTN còn lại (Thứ 2 … Thứ 7);
  Tiết | Luôn do GVCN dạy | Hạn chế môn nặng.

- Sheet CHỨC VỤ (không bắt buộc): mỗi dòng một chức vụ GV chuyên biệt nhà trường tự đặt và các môn chức vụ đó được
  dạy, vd GV Nghệ thuật: Âm nhạc, Mỹ thuật (config.CUSTOM_ROLES).
- Sheet LUẬT RIÊNG (không bắt buộc): mỗi dòng một luật riêng của trường thuộc một kiểu luật chung (tkb/luat_rieng.py),
  vd Thể dục chỉ học buổi chiều, Tiếng Anh học 2 tiết liền; các ô Khối, Ngày, Tiết, Buổi ghi danh sách.

Cột, bảng (hoặc dòng của bảng chung) nào không có thì quy định đó dùng giá trị mặc định trong tkb/config.py, nên
file vào cũ vẫn chạy như trước. Cột đã có thì là đủ: môn, ngày, tiết không có dòng tính là Không. Trọng số mục tiêu,
tham số xếp giờ và số tiết bù tối đa (main.py) vẫn ở mã nguồn.
"""
from __future__ import annotations

import copy
import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

import openpyxl

from . import bo_ghep, config, luat_rieng
from .staff import _NO, _YES, InputError, _fold, clean_name, find_sheet, normalize, subject_key

YES, NO = "Có", "Không"
MAX_DAYS = 6  # cách ghi cũ của bảng Ngày (cột Học buổi sáng/chiều): Thứ 2 – Thứ 7
SESSION_PREFIX = "Buổi"  # bảng Ngày: mỗi cột "Buổi <tên>" ghi số tiết của buổi đó trong ngày (0 hoặc trống: không học)
NOTE = "Ghi chú"  # cột ghi chú (nếu có) được bỏ qua
# Mẫu cũ không còn đọc: bốn sheet quy định riêng.
OLD_SHEETS = ("QUY ĐỊNH CHUNG", "QUY ĐỊNH NGÀY", "QUY ĐỊNH TIẾT", "QUY ĐỊNH MÔN")


@dataclass(frozen=True)
class Col:
    header: str  # tiêu đề cột (bảng chung: chữ ở cột Quy định)
    key: str  # hằng số trong tkb/config.py, hoặc phần của quy định ghép từ nhiều cột (chữ thường)
    kind: str  # "yes": Có/Không; "int": số nguyên dương; "order": số thứ tự 1, 2...; "text": chữ
    note: str


GENERAL_KEY, VALUE = "Quy định", "Giá trị"
GENERAL = (
    Col("Số tiết buổi sáng", "morning_periods", "int", "Buổi sáng là tiết 1 đến tiết này."),
    Col("Số tiết buổi chiều", "afternoon_periods", "int",
        "Buổi chiều là các tiết tiếp theo, vd sáng 4 tiết, chiều 3 tiết thì chiều là tiết 5, 6, 7."),
    Col("Số tiết tối đa một nhóm môn mỗi buổi", "SESSION_GROUP_LIMIT", "int",
        "Luật cứng; môn có từ 2 tiết trong một buổi thì các tiết đó phải liền nhau."),
    Col("Ghép cặp khi nhóm môn có từ (tiết/tuần)", "PAIR_MIN_LESSONS", "int",
        "Luật cứng: nhóm môn có từ ngần ấy tiết/tuần và tổng số tiết chẵn thì xếp thành các cặp 2 tiết liền, cùng "
        "người dạy (trừ môn ghi Có ở cột Không ghép cặp)."),
    Col("Chủ Nhiệm được dạy bù", "overtime_homeroom", "yes", "GVCN chỉ bù ở lớp mình và bù trước bộ môn."),
    Col("Bộ Môn được dạy bù", "overtime_general", "yes", "Bộ môn bù khi GVCN đã bù hết mức."),
)
DAY_KEY = "Ngày"
DAY_COLS = (
    Col("Học buổi sáng", "morning_days", "yes", "Cách ghi cũ: các ngày học, liền nhau từ Thứ 2."),
    Col("Học buổi chiều", "afternoon_days", "yes", "Cách ghi cũ: ngày có buổi chiều (phải là ngày học buổi sáng)."),
    Col("Tiết HĐTN cố định", "HDTN_FIXED_SLOTS", "int",
        "Luật cứng: tiết môn HĐTN cố định của ngày đó ở mọi lớp, vd Thứ 2: 1, Thứ 6: 4."),
    Col("Xếp tiết HĐTN còn lại", "HDTN_FLEX_DAYS", "yes",
        "Luật cứng: các tiết HĐTN còn lại chỉ xếp vào các ngày này (mục tiêu mềm: gần cuối buổi)."),
)
PERIOD_KEY = "Tiết"
PERIOD_COLS = (
    Col("Luôn do GVCN dạy", "HOMEROOM_PERIODS", "yes", "Luật cứng: tiết này ở mọi ngày do GVCN của lớp dạy."),
    Col("Hạn chế môn nặng", "HEAVY_LATE_PERIODS", "yes", "Mục tiêu mềm: mỗi tiết môn nặng ở tiết này bị trừ điểm."),
)
SUBJECT_KEY = "Môn học"
SUBJECT_COLS = (
    Col("Tên trong TKB", "DISPLAY_NAMES", "text", "Chữ ghi trong ô TKB (cột duy nhất ghi chữ); trống: ghi đúng tên môn."),
    Col("Môn HĐTN", "HDTN", "yes",
        "Có ở một môn: môn chào cờ, sinh hoạt lớp, có tiết cố định ở bảng ngày của sheet QUY ĐỊNH."),
    Col("GVCN nhận trọn", "HOMEROOM_PRIORITY", "yes",
        "GVCN nhận hết các môn này của lớp mình; luật cứng: môn nào phải chia cho người khác thì tiết đầu tiên trong "
        "tuần do GVCN dạy."),
    Col("GVCN cắt bớt", "HOMEROOM_CUT_ORDER", "order",
        "Số thứ tự 1, 2...: môn cắt trước khi các môn nhận trọn vượt định mức GVCN; mỗi môn GVCN giữ ít nhất 1 tiết."),
    Col("GVCN nhận thêm", "HOMEROOM_FILL_ORDER", "order",
        "Số thứ tự 1, 2...: môn GVCN nhận thêm trước cho đủ định mức (không nhận môn của GV chuyên biệt)."),
    Col("Chỉ GVCN dạy", "HOMEROOM_ONLY_SUBJECTS", "yes", "Luật cứng: chỉ GVCN của lớp được dạy."),
    Col("Bộ Môn không dạy", "GENERAL_FORBIDDEN_SUBJECTS", "yes",
        "GV bộ môn không dạy môn này; trường chưa có GV chuyên biệt của môn thì chương trình tuyển thêm. Ghi theo "
        "ngoại lệ để môn mới (ô trống) mặc nhiên bộ môn dạy được."),
    Col("Quản lý dạy khối", "MANAGER_RULES", "int", "Khối mà Quản Lý được dạy môn này, vd Kỹ năng sống: 4."),
    Col("GVCN bù môn chuyên biệt", "HOMEROOM_OVERTIME_SPECIALIST", "yes",
        "Môn có GV chuyên biệt mà GVCN vẫn được dạy bù ở lớp mình (nhận sau cùng)."),
    Col("Nhóm môn", "group", "int",
        "Môn chính và các môn tăng cường của nó ghi cùng một số, vd Tiếng Việt và Tiếng Việt tăng cường: 1."),
    Col("Môn tăng cường", "extra", "yes",
        "Có ở môn tăng cường của nhóm; luật cứng: tiết tăng cường đứng sau mọi tiết môn chính trong ngày và ngày đó "
        "phải có tiết môn chính; cả nhóm tính chung cho giới hạn mỗi buổi và ghép cặp."),
    Col("Tối đa tiết mỗi ngày", "DAILY_LIMITS", "int",
        "Luật cứng, vd Toán: 1; chỉ áp dụng khi số tiết/tuần của môn không quá số ngày học."),
    Col("Không ghép cặp", "PAIR_EXCLUDED", "yes",
        "Nhóm môn (ghi ở môn chính) không xếp thành cặp 2 tiết liền. Ghi theo ngoại lệ như cột Bộ Môn không dạy."),
    Col("Môn nặng", "HEAVY_SUBJECTS", "yes", "Mục tiêu mềm: hạn chế xếp vào các tiết Hạn chế môn nặng (sheet QUY ĐỊNH)."),
    Col("Ưu tiên buổi sáng", "MORNING_SUBJECTS", "yes",
        "Mục tiêu mềm: mỗi tiết ở buổi chiều bị trừ điểm, và môn được rải đều hơn trong tuần."),
)
# Sheet CHỨC VỤ: hai cột (thêm cột Ghi chú nếu cần).
ROLE_NAME, ROLE_SUBJECTS = "Chức vụ", "Môn được dạy"
# Cột của bản trước mà nay là số của một dòng luật (sheet LUẬT): vẫn đọc được ở file cũ, không ghi, không hiện.
LEGACY = frozenset({"SESSION_GROUP_LIMIT", "PAIR_MIN_LESSONS", "DAILY_LIMITS"})
# Cách ghi khung giờ của bản trước (số tiết buổi sáng/chiều chung mọi ngày, cột Có/Không học buổi sáng/chiều): vẫn
# đọc được, không ghi, không hiện; nay bảng Ngày ghi số tiết từng buổi của từng ngày (cột "Buổi <tên>").
LEGACY_FRAME = frozenset({"morning_periods", "afternoon_periods", "morning_days", "afternoon_days"})


def visible(cols) -> tuple:
    """Các cột quy định còn ghi trong file mẫu và hiện trên giao diện (bỏ các cột LEGACY, LEGACY_FRAME)."""
    return tuple(c for c in cols if c.key not in LEGACY and c.key not in LEGACY_FRAME)


FRAME_ATTRS = ("DAYS", "MORNING", "AFTERNOON", "DAY_SESSIONS")
ATTRS = (*FRAME_ATTRS, "SESSION_GROUP_LIMIT", "PAIR_MIN_LESSONS", "OVERTIME_ROLES", "HDTN_FIXED_SLOTS",
         "HDTN_FLEX_DAYS", "HOMEROOM_PERIODS", "HEAVY_LATE_PERIODS", "DISPLAY_NAMES", "HDTN", "HOMEROOM_PRIORITY",
         "HOMEROOM_CUT_ORDER", "HOMEROOM_FILL_ORDER", "HOMEROOM_ONLY_SUBJECTS", "GENERAL_FORBIDDEN_SUBJECTS",
         "MANAGER_RULES", "HOMEROOM_OVERTIME_SPECIALIST", "SUBJECT_GROUPS", "DAILY_LIMITS", "PAIR_EXCLUDED",
         "HEAVY_SUBJECTS", "MORNING_SUBJECTS", "CUSTOM_RULES", "CUSTOM_ROLES", "OFF", "WEIGHTS")
# Không ghi gì thì không tính vào mã quy định (mã cũ giữ nguyên).
OPTIONAL_ATTRS = ("CUSTOM_RULES", "CUSTOM_ROLES", "OFF", "WEIGHTS")
# Tên quy định khi in "khác mặc định".
LABELS = {**{c.key: c.header for c in (*GENERAL, *DAY_COLS, *PERIOD_COLS, *SUBJECT_COLS)},
          **{a: "Khung giờ" for a in FRAME_ATTRS}, "OVERTIME_ROLES": "Được dạy bù",
          "SUBJECT_GROUPS": "Nhóm môn, Môn tăng cường", "CUSTOM_RULES": "Luật riêng", "CUSTOM_ROLES": "Chức vụ",
          "OFF": "Luật có sẵn bị bỏ", "WEIGHTS": "Điểm của luật ưu tiên"}
DEFAULTS = {attr: copy.deepcopy(getattr(config, attr)) for attr in ATTRS}  # giá trị mặc định trong tkb/config.py
# Tên môn trong tkb/config.py (và chữ viết tắt mặc định), để khớp tên môn ghi trong sheet CHƯƠNG TRÌNH HỌC.
_KNOWN = {**{subject_key(label): s for s, label in config.DISPLAY_NAMES.items()},
          **{subject_key(s): s for s in config.rule_subjects()}}
_ROLES = {"overtime_homeroom": config.ROLE_HOMEROOM, "overtime_general": config.ROLE_GENERAL}


def _day_name(d: int) -> str:
    return f"Thứ {d + 2}"


# Khung giờ: các ngày học theo thứ tự, mỗi ngày (tên ngày, ((tên buổi, số tiết), ...)).
Layout = list[tuple[str, tuple[tuple[str, int], ...]]]


def layout_now() -> Layout:
    """Khung giờ theo config hiện tại."""
    return [(config.DAYS[d], tuple((s.name, len(s.periods)) for s in config.DAY_SESSIONS[d]))
            for d in sorted(config.DAY_SESSIONS)]


def _legacy_now() -> dict[str, object]:
    """Khung giờ hiện tại theo cách ghi cũ (giá trị ban đầu khi file ghi một phần theo cách cũ)."""
    return {"morning_days": sorted(config.DAY_SESSIONS),
            "afternoon_days": [d for d, ss in sorted(config.DAY_SESSIONS.items())
                               if any(s.name == config.AFTERNOON.name for s in ss)],
            "morning_periods": len(config.MORNING.periods),
            "afternoon_periods": len(config.AFTERNOON.periods)}


def _legacy_layout(f: dict[str, object]) -> Layout:
    morning = ((config.MORNING.name, f["morning_periods"]),)
    afternoon = ((config.AFTERNOON.name, f["afternoon_periods"]),)
    return [(_day_name(d), morning + (afternoon if d in f["afternoon_days"] else ())) for d in f["morning_days"]]


def _build_frame(layout: Layout, legacy: dict[str, object] | None = None) -> dict[str, object]:
    """Khung giờ -> config.DAYS, DAY_SESSIONS (tiết đánh số liên tục trong ngày; buổi giống nhau dùng chung một
    Session). MORNING, AFTERNOON chỉ để mã quy định (code) của khung giờ ghi theo cách cũ không đổi: buổi đầu và buổi
    kế tiếp của ngày đầu (cách cũ: đúng như bản trước)."""
    made: dict[tuple, config.Session] = {}
    day_sessions: dict[int, tuple[config.Session, ...]] = {}
    for d, (_, parts) in enumerate(layout):
        p, out = 1, []
        for name, n in parts:
            if n > 0:
                key = (name, tuple(range(p, p + n)))
                out.append(made.setdefault(key, config.Session(*key)))
                p += n
        day_sessions[d] = tuple(out)
    if legacy is not None:
        m, a = legacy["morning_periods"], legacy["afternoon_periods"]
        morning = config.Session(config.MORNING.name, tuple(range(1, m + 1)))
        afternoon = config.Session(config.AFTERNOON.name, tuple(range(m + 1, m + a + 1)))
    else:
        first = day_sessions.get(0, ())
        morning = first[0] if first else config.Session("", ())
        afternoon = first[1] if len(first) > 1 else config.Session("", ())
    return {"DAYS": [name for name, _ in layout], "MORNING": morning, "AFTERNOON": afternoon,
            "DAY_SESSIONS": day_sessions}


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _row(ws, r: int) -> dict[int, object]:
    """Các ô có chữ của dòng r: {cột: giá trị}."""
    return {c: ws.cell(r, c).value for c in range(1, ws.max_column + 1) if not _blank(ws.cell(r, c).value)}


def _is_grade(head: str) -> bool:
    return re.fullmatch(r"khối \d+", head) is not None


class _Reader:
    """Đọc các cột quy định của sheet CHƯƠNG TRÌNH HỌC và ba bảng của sheet QUY ĐỊNH; gom mọi lỗi để báo cùng
    lúc, sắp theo sheet rồi theo dòng."""

    def __init__(self, warn):
        self.legacy = _legacy_now()  # khung giờ ghi theo cách cũ (số tiết sáng/chiều, cột Học buổi sáng/chiều)
        self.legacy_given = False
        self.layout: Layout | None = None  # khung giờ ghi theo cách mới (cột Buổi <tên> của bảng Ngày)
        self.values: dict[str, object] = {}
        self.errors: list[tuple[int, int, str]] = []
        self.warn = warn

    def error(self, sheet: str, row: int | None, text: str) -> None:
        where = f"{sheet}, dòng {row}" if row else sheet
        order = 0 if normalize(sheet) == normalize(config.PROGRAM_SHEET) else 1
        self.errors.append((order, row or 10 ** 6, f"{where}: {text}"))

    def yes(self, sheet: str, row: int, header: str, value) -> bool:
        if isinstance(value, bool):
            return value
        if _blank(value):
            return False
        key = _fold(value)
        if key in _YES:
            return True
        if key not in _NO:
            self.error(sheet, row, f"cột {header} chỉ ghi {YES} hoặc {NO}, đang ghi {value!r}")
        return False

    def number(self, sheet: str, row: int, header: str, value) -> int | None:
        if _blank(value):
            return None
        if isinstance(value, float) and value == int(value):
            value = int(value)
        text = str(value).strip()
        if isinstance(value, bool) or not re.fullmatch(r"\d+", text) or int(text) < 1:
            self.error(sheet, row, f"cột {header} ghi một số nguyên dương, đang ghi {value!r}")
            return None
        return int(text)

    def cell(self, sheet: str, row: int, col: Col, value):
        if col.kind == "yes":
            return self.yes(sheet, row, col.header, value)
        if col.kind in ("int", "order"):
            return self.number(sheet, row, col.header, value)
        if col.kind == "count":  # số tiết của một buổi: 0 hoặc trống là không học buổi đó
            if not _blank(value) and str(value).strip() in ("0", "0.0"):
                return 0
            return self.number(sheet, row, col.header, value) or 0
        return None if _blank(value) else clean_name(value)

    def table(self, ws, header_row: int, end_row: int, key_col: int, cols: tuple[Col, ...], strict: bool):
        """Bảng có dòng tiêu đề `header_row`, khóa ở cột `key_col`, các dòng đến `end_row`: ({khóa của cột: số
        cột}, [(dòng, ô khóa, {khóa của cột: giá trị})]). `strict`: cột lạ là lỗi; không thì chỉ cảnh báo."""
        sheet = ws.title
        wanted = {normalize(c.header): c for c in cols}
        found: dict[str, int] = {}
        for c, value in _row(ws, header_row).items():
            head = normalize(value)
            if c == key_col or head == normalize(NOTE):
                continue
            col = wanted.get(head)
            if col is not None:
                found[col.key] = c
            elif strict:
                self.error(sheet, header_row, f"không có quy định nào tên '{value}' (các cột: "
                                              f"{', '.join(x.header for x in cols)})")
            elif not _is_grade(head) and head not in ("stt", "tổng"):
                self.warn(f"Sheet {sheet}: cột '{clean_name(value)}' không phải quy định nào, bỏ qua (các cột "
                          f"quy định: {', '.join(x.header for x in cols)})")
        by_key = {c.key: c for c in cols}
        rows = []
        for r in range(header_row + 1, end_row + 1):
            key = ws.cell(r, key_col).value
            values = {k: ws.cell(r, c).value for k, c in found.items()}
            if _blank(key):
                if any(not _blank(v) for v in values.values()):
                    self.error(sheet, r, "dòng có quy định nhưng thiếu ô đầu dòng")
                continue
            rows.append((r, key, {k: self.cell(sheet, r, by_key[k], v) for k, v in values.items()}))
        return found, rows

    # ---- sheet QUY ĐỊNH: ba bảng ----
    def rules_sheet(self, ws) -> None:
        """Tìm các bảng theo ô tiêu đề đầu bảng (Quy định, Ngày, Tiết); mỗi bảng đến dòng trống kế tiếp."""
        kinds = {normalize(GENERAL_KEY): (self.general, GENERAL), normalize(DAY_KEY): (self.days, DAY_COLS),
                 normalize(PERIOD_KEY): (self.periods, PERIOD_COLS)}
        seen: dict[str, int] = {}
        r = 1
        while r <= ws.max_row:
            cells = _row(ws, r)
            first = next(iter(cells.items()), None)
            kind = kinds.get(normalize(first[1])) if first else None
            others = {normalize(v) for c, v in cells.items() if c != (first[0] if first else None)}
            if kind is None or not others & ({normalize(c.header) for c in kind[1]} | {normalize(VALUE)}):
                r += 1
                continue
            end = r
            while end + 1 <= ws.max_row and _row(ws, end + 1) and \
                    normalize(next(iter(_row(ws, end + 1).values()))) not in kinds:
                end += 1
            name = normalize(first[1])
            if name in seen:
                self.error(ws.title, r, f"bảng {first[1]} bị lặp với dòng {seen[name]}")
            else:
                seen[name] = r
                kind[0](ws, r, end, first[0])
            r = end + 1
        if not seen:
            self.error(ws.title, None, f"không có bảng nào (dòng tiêu đề bắt đầu bằng {GENERAL_KEY}, {DAY_KEY} "
                                       f"hoặc {PERIOD_KEY})")

    def general(self, ws, header_row: int, end_row: int, label_col: int) -> None:
        sheet = ws.title
        heads = {normalize(v): c for c, v in _row(ws, header_row).items()}
        if normalize(VALUE) not in heads:
            self.error(sheet, header_row, f"bảng {GENERAL_KEY} phải có cột {VALUE}")
            return
        value_col = heads[normalize(VALUE)]
        by_label = {subject_key(c.header): c for c in GENERAL}
        seen: dict[str, int] = {}
        roles = set(config.OVERTIME_ROLES)
        for r in range(header_row + 1, end_row + 1):
            label = ws.cell(r, label_col).value
            if _blank(label):
                continue
            col = by_label.get(subject_key(label))
            if col is None:
                self.error(sheet, r, f"không có quy định '{clean_name(label)}' (các quy định: "
                                     f"{', '.join(c.header for c in GENERAL)})")
                continue
            if col.key in seen:
                self.error(sheet, r, f"quy định '{col.header}' bị lặp với dòng {seen[col.key]}")
                continue
            seen[col.key] = r
            raw = ws.cell(r, value_col).value
            value = self.cell(sheet, r, col, raw)
            if col.kind == "int" and value is None:
                if _blank(raw):
                    self.error(sheet, r, f"chưa ghi số ở cột {VALUE} ({col.header})")
                continue
            if col.key in _ROLES:
                roles = roles | {_ROLES[col.key]} if value else roles - {_ROLES[col.key]}
                self.values["OVERTIME_ROLES"] = roles
            elif col.key in ("morning_periods", "afternoon_periods"):
                self.legacy[col.key] = value
                self.legacy_given = True
            else:
                self.values[col.key] = value

    def days(self, ws, header_row: int, end_row: int, key_col: int) -> None:
        sheet = ws.title
        known = {normalize(c.header) for c in DAY_COLS}
        sessions = [clean_name(str(value).strip()[len(SESSION_PREFIX):]) for c, value in _row(ws, header_row).items()
                    if c != key_col and normalize(value) not in known
                    and normalize(value).startswith(normalize(SESSION_PREFIX) + " ")]
        if sessions:
            return self.day_layout(ws, header_row, end_row, key_col, sessions)
        found, rows = self.table(ws, header_row, end_row, key_col, DAY_COLS, strict=True)
        by_day: dict[int, dict] = {}
        for r, key, values in rows:
            m = re.fullmatch(r"(?:thu|t)?\s*(\d)", _fold(key))
            day = int(m.group(1)) - 2 if m else -1
            if not 0 <= day < MAX_DAYS:
                self.error(sheet, r, f"ngày ghi Thứ 2 … Thứ 7, đang ghi {key!r}")
            elif day in by_day:
                self.error(sheet, r, f"{_day_name(day)} bị lặp")
            else:
                by_day[day] = values
        days = sorted(by_day)
        for key in ("morning_days", "afternoon_days"):
            if key in found:
                self.legacy[key] = [d for d in days if by_day[d][key]]
                self.legacy_given = True
        if "HDTN_FIXED_SLOTS" in found:
            self.values["HDTN_FIXED_SLOTS"] = [(d, by_day[d]["HDTN_FIXED_SLOTS"]) for d in days
                                               if by_day[d]["HDTN_FIXED_SLOTS"] is not None]
        if "HDTN_FLEX_DAYS" in found:
            self.values["HDTN_FLEX_DAYS"] = [d for d in days if by_day[d]["HDTN_FLEX_DAYS"]]

    def day_layout(self, ws, header_row: int, end_row: int, key_col: int, sessions: list[str]) -> None:
        """Bảng Ngày ghi theo cách mới: Ngày (tên tùy ý, thứ tự theo dòng) | Buổi <tên> (số tiết, 0 hoặc trống: không
        học buổi đó) | các cột HĐTN. Ngày không có tiết nào không phải ngày học."""
        sheet = ws.title
        if len({normalize(n) for n in sessions}) < len(sessions):
            self.error(sheet, header_row, "bảng Ngày có hai cột Buổi trùng tên")
            return
        cols = tuple(Col(f"{SESSION_PREFIX} {n}", f"buoi:{n}", "count", "") for n in sessions)
        found, rows = self.table(ws, header_row, end_row, key_col, DAY_COLS + cols, strict=True)
        old = [c.header for c in DAY_COLS if c.key in found and c.key in LEGACY_FRAME]
        if old:
            self.error(sheet, header_row, f"bảng Ngày ghi số tiết ở các cột {SESSION_PREFIX} <tên> thì bỏ cột "
                                          f"{', '.join(old)} (cách ghi cũ)")
            return
        layout: Layout = []
        fixed, flex, seen = [], [], {}
        for r, key, values in rows:
            name = clean_name(key)
            if normalize(name) in seen:
                self.error(sheet, r, f"ngày '{name}' bị lặp với dòng {seen[normalize(name)]}")
                continue
            seen[normalize(name)] = r
            parts = tuple((n, values.get(f"buoi:{n}") or 0) for n in sessions)
            if not any(k for _, k in parts):
                if values.get("HDTN_FIXED_SLOTS") is not None or values.get("HDTN_FLEX_DAYS"):
                    self.error(sheet, r, f"ngày '{name}' không có tiết nào (cột {SESSION_PREFIX} <tên>) nhưng có ghi "
                                         f"tiết HĐTN")
                continue
            d = len(layout)
            layout.append((name, parts))
            if values.get("HDTN_FIXED_SLOTS") is not None:
                fixed.append((d, values["HDTN_FIXED_SLOTS"]))
            if values.get("HDTN_FLEX_DAYS"):
                flex.append(d)
        self.layout = layout
        if "HDTN_FIXED_SLOTS" in found:
            self.values["HDTN_FIXED_SLOTS"] = fixed
        if "HDTN_FLEX_DAYS" in found:
            self.values["HDTN_FLEX_DAYS"] = flex

    def periods(self, ws, header_row: int, end_row: int, key_col: int) -> None:
        sheet = ws.title
        found, rows = self.table(ws, header_row, end_row, key_col, PERIOD_COLS, strict=True)
        seen: dict[int, dict] = {}
        for r, key, values in rows:
            p = self.number(sheet, r, PERIOD_KEY, key)
            if p is not None and p in seen:
                self.error(sheet, r, f"tiết {p} bị lặp")
            elif p is not None:
                seen[p] = values
        for key in found:
            self.values[key] = {p for p, values in seen.items() if values[key]}

    # ---- sheet CHƯƠNG TRÌNH HỌC: các cột quy định của môn ----
    def subjects(self, ws) -> bool:
        """Đọc các cột quy định sau các cột Khối; trả về True nếu sheet có ít nhất một cột quy định."""
        sheet = ws.title
        header_row = key_col = None
        for r in range(1, min(ws.max_row, 20) + 1):
            for c, value in _row(ws, r).items():
                if normalize(value) == normalize(SUBJECT_KEY):
                    header_row, key_col = r, c
                    break
            if header_row:
                break
        if header_row is None:
            return False  # read_program báo lỗi thiếu cột Môn học
        found, rows = self.table(ws, header_row, ws.max_row, key_col, SUBJECT_COLS, strict=False)
        if not found:
            return False
        rows = [(r, k, v) for r, k, v in rows if normalize(k) not in ("tổng", "tổng cộng")]
        labels = {subject_key(v["DISPLAY_NAMES"]): clean_name(k) for _, k, v in rows if v.get("DISPLAY_NAMES")}
        names: list[tuple[int, str, dict]] = []
        seen: dict[str, int] = {}
        for r, key, values in rows:
            k = subject_key(key)
            name = _KNOWN.get(k) or _KNOWN.get(subject_key(labels.get(k, ""))) or clean_name(key)
            if name in seen:
                continue  # read_program báo lỗi môn lặp
            seen[name] = r
            names.append((r, name, values))
        v = self.values
        for col in SUBJECT_COLS:
            if col.key not in found or col.key in ("group", "extra"):
                continue
            cells = [(r, s, values[col.key]) for r, s, values in names]
            if col.key == "DISPLAY_NAMES":
                v[col.key] = {s: x for _, s, x in cells if x}
            elif col.key == "HDTN":
                chosen = [(r, s) for r, s, x in cells if x]
                for r, s in chosen[1:]:
                    self.error(sheet, r, f"cột {col.header} chỉ ghi {YES} ở một môn (đã có {chosen[0][1]})")
                v[col.key] = chosen[0][1] if chosen else ""
            elif col.key == "HOMEROOM_PRIORITY":
                v[col.key] = [s for _, s, x in cells if x]  # theo thứ tự dòng
            elif col.kind == "order":
                order: dict[int, str] = {}
                for r, s, x in cells:
                    if x is not None and x in order:
                        self.error(sheet, r, f"cột {col.header}: số thứ tự {x} bị lặp ({order[x]})")
                    elif x is not None:
                        order[x] = s
                v[col.key] = [order[n] for n in sorted(order)]
            elif col.key == "MANAGER_RULES":
                v[col.key] = [config.ManagerRule(subject=s, grade=x) for _, s, x in cells if x is not None]
            elif col.key == "DAILY_LIMITS":
                v[col.key] = {s: x for _, s, x in cells if x is not None}
            else:
                v[col.key] = {s for _, s, x in cells if x}
        if ("group" in found) != ("extra" in found):
            self.error(sheet, header_row, "cột Nhóm môn và cột Môn tăng cường phải có cùng nhau")
        elif "group" in found:
            groups: dict[int, list[tuple[int, str, bool]]] = {}
            for r, s, values in names:
                if values["group"] is not None:
                    groups.setdefault(values["group"], []).append((r, s, values["extra"]))
                elif values["extra"]:
                    self.error(sheet, r, f"môn tăng cường {s} chưa ghi Nhóm môn")
            pairs: dict[str, str] = {}
            for n in sorted(groups):
                mains = [s for _, s, extra in groups[n] if not extra]
                if len(mains) != 1:
                    self.error(sheet, groups[n][0][0], f"nhóm môn {n} phải có đúng một môn chính (Môn tăng cường để "
                                                       f"trống hoặc Không), đang có {len(mains)}")
                    continue
                pairs.update({s: mains[0] for _, s, extra in groups[n] if extra})
            v["SUBJECT_GROUPS"] = pairs
        return True

    # ---- sheet LUẬT RIÊNG: mỗi dòng một luật riêng ----
    def custom(self, ws, attr: str = "CUSTOM_RULES") -> None:
        """Bảng có dòng tiêu đề chứa cột Kiểu luật; mỗi dòng sau đó là một luật (dòng trống bỏ qua). Sheet LUẬT
        (attr RULES) có thêm cột Nhóm; cột Ghi chú, Luật đọc là bỏ qua."""
        sheet = ws.title
        heads = {normalize(h): k for k, h in (luat_rieng.GROUP, *luat_rieng.COLUMNS)}
        header_row = next((r for r in range(1, min(ws.max_row, 20) + 1)
                           if any(normalize(v) == normalize(luat_rieng.HEADERS["kind"]) for v in _row(ws, r).values())),
                          None)
        if header_row is None:
            if ws.max_row > 1 or _row(ws, 1):
                self.error(sheet, None, f"không có dòng tiêu đề có cột {luat_rieng.HEADERS['kind']}")
            self.values[attr] = []
            return
        cols: dict[str, int] = {}
        for c, value in _row(ws, header_row).items():
            key = heads.get(normalize(value))
            if key is not None:
                cols[key] = c
            elif normalize(value) not in (normalize(luat_rieng.NOTE), normalize(luat_rieng.SAY)):
                self.error(sheet, header_row, f"không có cột nào tên '{clean_name(value)}' (các cột: "
                                              f"{', '.join(luat_rieng.HEADERS.values())}, {luat_rieng.NOTE})")
        rules = []
        for r in range(header_row + 1, ws.max_row + 1):
            values = {k: ws.cell(r, c).value for k, c in cols.items()}
            rule = luat_rieng.parse(values, r, lambda text, r=r: self.error(sheet, r, text))
            if rule is not None:
                rules.append(rule)
        self.values[attr] = rules

    # ---- sheet CHỨC VỤ: mỗi dòng một chức vụ GV chuyên biệt và các môn được dạy ----
    def roles(self, ws) -> None:
        """Bảng có dòng tiêu đề chứa cột Chức vụ; các dòng sau là các chức vụ (dòng trống bỏ qua). Tên môn kiểm
        tra khi dựng bài toán (allocation.resolve_roles), vì cần chương trình học."""
        sheet = ws.title
        heads = {normalize(ROLE_NAME): "name", normalize(ROLE_SUBJECTS): "subjects"}
        header_row = next((r for r in range(1, min(ws.max_row, 20) + 1)
                           if normalize(ROLE_NAME) in {normalize(v) for v in _row(ws, r).values()}), None)
        self.values["CUSTOM_ROLES"] = roles = []
        if header_row is None:
            if ws.max_row > 1 or _row(ws, 1):
                self.error(sheet, None, f"không có dòng tiêu đề có cột {ROLE_NAME}")
            return
        cols: dict[str, int] = {}
        for c, value in _row(ws, header_row).items():
            key = heads.get(normalize(value))
            if key is not None:
                cols[key] = c
            elif normalize(value) != normalize(NOTE):
                self.error(sheet, header_row, f"không có cột nào tên '{clean_name(value)}' (các cột: {ROLE_NAME}, "
                                              f"{ROLE_SUBJECTS}, {NOTE})")
        if "subjects" not in cols:
            self.error(sheet, header_row, f"thiếu cột {ROLE_SUBJECTS}")
            return
        builtin = {subject_key(label): label for label in config.ROLE_LABELS.values()}
        seen: dict[str, int] = {}
        for r in range(header_row + 1, ws.max_row + 1):
            name, subjects = (ws.cell(r, cols[k]).value for k in ("name", "subjects"))
            if _blank(name):
                if not _blank(subjects):
                    self.error(sheet, r, f"thiếu tên ở cột {ROLE_NAME}")
                continue
            label, key = clean_name(name), subject_key(name)
            if key in builtin:
                self.error(sheet, r, f"{builtin[key]} là chức vụ có sẵn, không ghi ở sheet này (môn được dạy của "
                                     f"Chủ Nhiệm, Bộ Môn, Quản Lý ghi ở các cột của sheet {config.PROGRAM_SHEET})")
            elif re.search(r"\d", label):
                self.error(sheet, r, f"tên chức vụ không ghi số (chương trình tự đánh số GV theo thứ tự dòng): "
                                     f"{label!r}")
            elif key in seen:
                self.error(sheet, r, f"chức vụ '{label}' đã ghi ở dòng {seen[key]}")
            else:
                seen[key] = r
                names: dict[str, str] = {}  # môn ghi trùng chỉ tính một lần
                for x in re.split(r"[,;\n]", "" if _blank(subjects) else str(subjects)):
                    if x.strip():
                        names.setdefault(subject_key(x), clean_name(x))
                if not names:
                    self.error(sheet, r, f"chức vụ '{label}' chưa ghi môn ở cột {ROLE_SUBJECTS}")
                else:
                    roles.append(config.Role(label, tuple(names.values()), r))

    def frame(self) -> dict[str, object]:
        """Khung giờ của file (DAYS, DAY_SESSIONS, MORNING, AFTERNOON; {} nếu file không ghi): đọc xong sheet QUY ĐỊNH
        thì tính ngay, để cột Ngày, Buổi của sheet LUẬT đọc theo tên ngày, tên buổi của chính file."""
        sheet = config.RULES_SHEET
        self.frame_layout = layout = layout_now()
        if self.layout is not None and self.legacy_given:
            self.error(sheet, None, f"khung giờ ghi theo hai cách: bảng Ngày đã có các cột {SESSION_PREFIX} <tên> thì bỏ "
                                    f"các quy định Số tiết buổi sáng, Số tiết buổi chiều (cách ghi cũ)")
        elif self.layout is not None:
            if not self.layout:
                self.error(sheet, None, f"chưa có ngày học nào (bảng Ngày, cột {SESSION_PREFIX} <tên> ghi số tiết)")
            else:
                layout = self.layout
                self.values.update(_build_frame(layout))
        elif self.legacy_given:
            f = self.legacy
            morning = f["morning_days"]
            if not morning or morning != list(range(len(morning))):
                self.error(sheet, None, "các ngày Học buổi sáng phải liền nhau từ Thứ 2")
            elif any(d not in morning for d in f["afternoon_days"]):
                self.error(sheet, None, "ngày Học buổi chiều phải là ngày Học buổi sáng")
            else:
                layout = _legacy_layout(f)
                self.values.update(_build_frame(layout, legacy=f))
        self.frame_layout = layout
        return {a: self.values[a] for a in FRAME_ATTRS if a in self.values}

    def finish(self) -> dict[str, object]:
        sheet = config.RULES_SHEET
        layout = self.frame_layout
        # Ngày, tiết các quy định nhắc tới (kể cả giá trị mặc định) phải có trong khung giờ.
        get = lambda attr: self.values.get(attr, getattr(config, attr))  # noqa: E731
        counts = [sum(n for _, n in parts) for _, parts in layout]
        name = lambda d: layout[d][0] if 0 <= d < len(layout) else _day_name(d)  # noqa: E731
        for d, p in get("HDTN_FIXED_SLOTS"):
            if not 0 <= d < len(layout) or p > counts[d]:
                self.error(sheet, None, f"Tiết HĐTN cố định {name(d)} tiết {p} không có trong khung giờ")
        for d in get("HDTN_FLEX_DAYS"):
            if not 0 <= d < len(layout):
                self.error(sheet, None, f"Xếp tiết HĐTN còn lại vào {name(d)} nhưng ngày đó không học")
        total = max(counts, default=0)
        for attr in ("HOMEROOM_PERIODS", "HEAVY_LATE_PERIODS"):
            for p in sorted(get(attr)):
                if p > total:
                    self.error(sheet, None, f"{LABELS[attr]}: không có tiết {p} trong khung giờ (mỗi ngày tối đa "
                                            f"{total} tiết)")
        return self.values


def read_rules(path: str | Path, warn=lambda text: None) -> dict[str, object] | None:
    """Đọc quy định của file vào: các cột quy định của sheet CHƯƠNG TRÌNH HỌC và sheet QUY ĐỊNH. Trả về {hằng số
    trong config: giá trị} của các quy định có trong file (khung giờ gộp thành DAYS, MORNING, AFTERNOON,
    DAY_SESSIONS); None nếu file không ghi quy định nào. Báo mọi lỗi cùng lúc (InputError); `warn` nhận các cảnh báo
    (vd cột lạ ở sheet chương trình học)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    old = [name for name in OLD_SHEETS if find_sheet(wb, name) is not None]
    if old:
        raise InputError(f"File vào theo mẫu cũ (sheet {', '.join(old)}): nay quy định của môn là các cột của sheet "
                         f"{config.PROGRAM_SHEET}, các quy định khác ở sheet {config.RULES_SHEET}. Tạo file mẫu mới "
                         f"(python -m tkb.template) rồi chép sang, hoặc xóa các sheet đó để dùng giá trị mặc định")
    reader = _Reader(warn)
    found = False
    program = find_sheet(wb, config.PROGRAM_SHEET)
    if program is not None:
        found = reader.subjects(program)
    ws = find_sheet(wb, config.RULES_SHEET)
    if ws is not None:
        reader.rules_sheet(ws)
        found = True
    ws = find_sheet(wb, config.ROLES_SHEET)
    if ws is not None:
        reader.roles(ws)
        found = True
    with applied(reader.frame()):  # cột Ngày, Buổi của các dòng luật theo khung giờ của file
        ws = find_sheet(wb, luat_rieng.SHEET)
        if ws is not None:
            reader.custom(ws)
            found = True
        ws = find_sheet(wb, luat_rieng.RULES_SHEET)
        if ws is not None:
            reader.custom(ws, "RULES")
            found = True
    if not found:
        return None
    values = reader.finish()
    if reader.errors:
        lines = list(dict.fromkeys(text for *_, text in sorted(reader.errors)))
        raise InputError(f"Quy định trong file vào có {len(lines)} lỗi:\n  " + "\n  ".join(lines))
    return _rules_rows(values, warn)


def _rules_rows(values: dict, warn) -> dict:
    """Các dòng luật (sheet LUẬT; không có thì dòng mặc định theo các cột cũ, cộng sheet LUẬT RIÊNG) -> tham số luật
    có sẵn, luật bị tắt, luật xếp bằng bộ ghép (luat_co_san.apply)."""
    from . import luat_co_san
    custom = values.pop("CUSTOM_RULES", [])
    with applied(values):
        if "RULES" in values:
            rows = [*values["RULES"], *(replace(r, group_label=r.group_label or luat_co_san.CUSTOM_GROUP)
                                        for r in custom)]
            legacy = {a: getattr(config, a) for a in LEGACY if a in values}
            values["RULES"] = rows
        else:
            rows = [*luat_co_san.default_rows(), *custom]
            legacy = {}
        out = {**values, **luat_co_san.apply([r for r in rows if not r.off])}  # dòng Tạm tắt: như không có
    for attr, value in legacy.items():
        if attr in out and _canonical(attr, out[attr]) != _canonical(attr, value):
            warn(f"Cột {LABELS[attr]} không còn dùng khi có sheet {luat_rieng.RULES_SHEET}: số của luật ghi ở "
                 f"dòng luật (sheet {luat_rieng.RULES_SHEET})")
    if custom and "RULES" in values:
        warn(f"Các luật ở sheet {luat_rieng.SHEET} được thêm vào cuối sheet {luat_rieng.RULES_SHEET}")
    return out


@contextmanager
def applied(values: dict[str, object] | None):
    """Dùng các quy định đọc từ file vào trong khối `with`; ra khỏi khối thì trả lại giá trị cũ (cả config.PEOPLE,
    đặt sau khi đọc nhân sự)."""
    old = {attr: getattr(config, attr) for attr in (*(values or {}), "PEOPLE")}
    try:
        for attr, value in (values or {}).items():
            setattr(config, attr, value)
        yield
    finally:
        for attr, value in old.items():
            setattr(config, attr, value)


def changed(values: dict[str, object] | None) -> list[str]:
    """Tên các quy định trong file khác giá trị mặc định trong tkb/config.py."""
    values = values or {}
    return list(dict.fromkeys(LABELS[a] for a in ATTRS
                              if a in values and _canonical(a, values[a]) != _canonical(a, DEFAULTS[a])))


def _canonical(attr: str, value):
    """Giá trị viết theo một cách duy nhất (tập hợp sắp xếp; tên viết tắt không phụ thuộc thứ tự dòng)."""
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if attr == "DISPLAY_NAMES":
        return sorted(value.items())
    if attr == "CUSTOM_RULES":  # số dòng, cột Nhóm không phải là luật: dời dòng không đổi mã
        return [replace(r, row=0, group_label="") for r in value]
    if attr == "WEIGHTS":
        return sorted(value.items())
    if attr == "CUSTOM_ROLES":  # dòng một môn trùng tên chức vụ là như không ghi (chức vụ trùng tên môn có sẵn)
        from .program import canonical_subject
        key = lambda name: subject_key(canonical_subject(name))  # noqa: E731
        roles = [(subject_key(r.name), sorted({key(s) for s in r.subjects})) for r in value]
        return [(name, subjects) for name, subjects in roles if subjects != [key(name)]]
    return value


def code() -> str:
    """Mã của các quy định đang dùng (12 chữ số hex): quy định khác nhau thì mã khác nhau, mọi máy cùng mã."""
    values = ((attr, _canonical(attr, getattr(config, attr))) for attr in ATTRS)
    text = "\n".join(f"{attr}={value!r}" for attr, value in values if value or attr not in OPTIONAL_ATTRS)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12].upper()


def _yn(on: bool) -> str:
    return YES if on else NO


def rule_tables() -> list[tuple[list[str], list[list]]]:
    """Ba bảng của sheet QUY ĐỊNH theo config hiện tại: [(tiêu đề, các dòng)]."""
    general = {"SESSION_GROUP_LIMIT": config.SESSION_GROUP_LIMIT, "PAIR_MIN_LESSONS": config.PAIR_MIN_LESSONS,
               **{k: _yn(role in config.OVERTIME_ROLES) for k, role in _ROLES.items()}}
    fixed = dict(config.HDTN_FIXED_SLOTS)
    flex = set(config.HDTN_FLEX_DAYS)
    layout = layout_now()
    names = list(dict.fromkeys(n for _, parts in layout for n, _ in parts))
    day_cols = visible(DAY_COLS)
    hdtn = {"HDTN_FIXED_SLOTS": lambda d: fixed.get(d), "HDTN_FLEX_DAYS": lambda d: _yn(d in flex)}
    days = [[name, *(dict(parts).get(n) or None for n in names), *(hdtn[c.key](d) for c in day_cols)]
            for d, (name, parts) in enumerate(layout)]
    total = max((sum(n for _, n in parts) for _, parts in layout), default=0)
    periods = [[p, _yn(p in config.HOMEROOM_PERIODS), _yn(p in config.HEAVY_LATE_PERIODS)]
               for p in range(1, total + 1)]
    return [([GENERAL_KEY, VALUE], [[c.header, general[c.key]] for c in visible(GENERAL)]),
            ([DAY_KEY, *(f"{SESSION_PREFIX} {n}" for n in names), *(c.header for c in day_cols)], days),
            ([PERIOD_KEY, *(c.header for c in PERIOD_COLS)], periods)]


def role_rows() -> list[list]:
    """Các dòng của sheet CHỨC VỤ theo config hiện tại: [tên chức vụ, các môn cách nhau bằng dấu phẩy]."""
    return [[r.name, ", ".join(r.subjects)] for r in config.CUSTOM_ROLES]


def luat_headers() -> list[str]:
    """Tiêu đề sheet LUẬT: Nhóm, các cột câu luật, Luật đọc là (chương trình ghi, khi đọc bỏ qua)."""
    return [luat_rieng.GROUP[1], *(h for _, h in luat_rieng.COLUMNS), luat_rieng.SAY]


def luat_row(rule) -> list:
    """Một dòng của sheet LUẬT (cùng thứ tự cột với luat_headers)."""
    cells = luat_rieng.cells(rule)
    say = luat_rieng.describe(rule)
    return [rule.group_label or None, *(cells[k] for k, _ in luat_rieng.COLUMNS),
            f"(Tạm tắt) {say}" if rule.off else say]


def luat_rows() -> list[list]:
    """Các dòng của sheet LUẬT theo config hiện tại: mọi luật, kể cả luật có sẵn (luat_co_san.rows)."""
    from . import luat_co_san
    return [luat_row(r) for r in luat_co_san.rows()]


def default_subjects() -> list[str]:
    """Các môn có quy định, theo thứ tự tự nhiên (môn GVCN nhận trọn, môn nhận thêm, rồi các môn khác)."""
    order = [*config.HOMEROOM_PRIORITY, *config.HOMEROOM_FILL_ORDER,
             *sorted(config.rule_subjects(), key=subject_key)]
    return list(dict.fromkeys(s for s in order if s))


def subject_columns(subjects=()) -> tuple[list[str], dict[str, list], list[str]]:
    """Các cột quy định của sheet CHƯƠNG TRÌNH HỌC theo config hiện tại: (tiêu đề, {môn: giá trị các cột}, các môn có
    quy định mà `subjects` không có). `subjects`: tên môn như trong file vào; khóa của kết quả là tên đó."""
    from .program import canonical_subject

    names = {canonical_subject(s): clean_name(s) for s in subjects}
    rest = [s for s in default_subjects() if s not in names]
    groups: dict[str, int] = {}
    for extra, main in config.SUBJECT_GROUPS.items():
        groups.setdefault(main, len(set(groups.values())) + 1)
        groups[extra] = groups[main]
    rank = lambda attr, s: (getattr(config, attr).index(s) + 1 if s in getattr(config, attr) else None)  # noqa: E731
    managers = {r.subject: r.grade for r in config.MANAGER_RULES}
    values = {}
    for s in [*names, *rest]:
        values[names.get(s, s)] = [
            config.DISPLAY_NAMES.get(s), _yn(s == config.HDTN), _yn(s in config.HOMEROOM_PRIORITY),
            rank("HOMEROOM_CUT_ORDER", s), rank("HOMEROOM_FILL_ORDER", s),
            _yn(s in config.HOMEROOM_ONLY_SUBJECTS), _yn(s in config.GENERAL_FORBIDDEN_SUBJECTS),
            managers.get(s), _yn(s in config.HOMEROOM_OVERTIME_SPECIALIST), groups.get(s),
            _yn(s in config.SUBJECT_GROUPS), config.DAILY_LIMITS.get(s), _yn(s in config.PAIR_EXCLUDED),
            _yn(s in config.HEAVY_SUBJECTS), _yn(s in config.MORNING_SUBJECTS)]
    keep = [i for i, c in enumerate(SUBJECT_COLS) if c.key not in LEGACY]
    values = {s: [v[i] for i in keep] for s, v in values.items()}
    return [SUBJECT_COLS[i].header for i in keep], values, rest


def notes() -> list[tuple[str, str]]:
    """Giải thích từng quy định (cho sheet HƯỚNG DẪN): [(sheet: cột/quy định, cách ghi)]."""
    return [*((f"{config.PROGRAM_SHEET}: {c.header}", c.note) for c in visible(SUBJECT_COLS)),
            *((f"{config.RULES_SHEET}: {c.header}", c.note) for c in visible(GENERAL)),
            (f"{config.RULES_SHEET}: {DAY_KEY}, {SESSION_PREFIX} <tên buổi>",
             f"Bảng {DAY_KEY}: mỗi dòng một ngày học, tên tùy ý (vd Thứ 2, Thứ 7, Chủ nhật), theo thứ tự trong tuần. Mỗi "
             f"cột {SESSION_PREFIX} <tên buổi> (vd {SESSION_PREFIX} Sáng, {SESSION_PREFIX} Chiều, {SESSION_PREFIX} Tối) ghi "
             f"số tiết của buổi đó trong ngày; ô trống là ngày đó không học buổi đó. Mỗi ngày một số tiết riêng được "
             f"(vd chiều Thứ 5 có 4 tiết). Thêm buổi thì thêm cột, thêm ngày học thì thêm dòng; ngày không có tiết nào "
             f"không phải ngày học. Tiết đánh số liên tục trong ngày theo thứ tự các cột buổi: sáng 4 tiết thì chiều "
             f"bắt đầu từ tiết 5."),
            *((f"{config.RULES_SHEET}: {c.header}", c.note) for c in visible((*DAY_COLS, *PERIOD_COLS))),
            (config.ROLES_SHEET,
             f"Không bắt buộc. Mỗi dòng một chức vụ GV chuyên biệt nhà trường tự đặt: cột {ROLE_NAME} ghi tên (không "
             f"ghi số, không trùng Chủ Nhiệm, Bộ Môn, Quản Lý), cột {ROLE_SUBJECTS} ghi các môn chức vụ đó dạy, cách "
             f"nhau bằng dấu phẩy, đúng tên trong sheet {config.PROGRAM_SHEET}, vd GV Nghệ thuật: Âm nhạc, Mỹ thuật. Ở "
             f"sheet {config.STAFF_SHEET}, GV có Chức Vụ là tên đó chỉ dạy các môn này. Chức vụ không ghi ở đây mà "
             f"trùng tên một môn (vd Tiếng Anh) thì chỉ dạy môn đó. Môn Bộ Môn không dạy mà chưa có GV nào dạy được "
             f"thì chương trình tuyển thêm chức vụ đầu tiên ở đây dạy môn đó (không có thì chức vụ trùng tên môn)."),
            (luat_rieng.RULES_SHEET,
             "Mọi luật xếp TKB, mỗi dòng một luật, đọc như một câu: Với mỗi [cột Với mỗi] · các tiết [Môn, Nhãn, Khối, "
             "Lớp, Ngày, Tiết, Buổi, Giáo viên] · thì [Phép đo] [So sánh] [Số] · khi [Áp dụng khi]. Mỗi luật trả lời "
             f"một trong bốn câu hỏi: {', '.join(bo_ghep.FAMILIES)} (các kiểu luật và phép đo xếp theo câu hỏi ở "
             "dưới). File mẫu ghi sẵn các luật có sẵn của chương trình: sửa số hoặc Điểm để chỉnh, đổi Bắt buộc, xóa "
             "dòng để bỏ luật (hoặc ghi Có ở cột Tạm tắt: chương trình bỏ qua dòng đó mà vẫn giữ lại, xóa chữ Có là "
             "dùng lại), thêm dòng để có luật mới. Cột Nhóm và Luật đọc là chỉ để đọc (chương trình ghi lại mỗi "
             "lần). Kiểu luật: một mẫu hoặc Tự ghép; cột kiểu luật không dùng để trống. Bắt buộc: Có (luật cứng) hoặc "
             f"Không (ưu tiên); luật ưu tiên ghi Mức {', '.join(luat_rieng.LEVELS)} (100, 400, 1500, 5000 điểm) hoặc "
             "ghi thẳng Điểm (điểm trừ mỗi lần không theo). Môn, Lớp, Khối, Ngày, Tiết ghi danh sách cách nhau bằng "
             "dấu phẩy hoặc khoảng, vd 3, 4 hoặc 3-5; Thứ 2, Thứ 4 hoặc T2-T4; 5-7. Buổi: Sáng hoặc Chiều. Giáo viên: "
             "chức vụ (Chủ Nhiệm, Bộ Môn, Quản Lý hoặc chức vụ GV chuyên biệt), 'trừ Chủ Nhiệm' là mọi giáo viên trừ "
             "chức vụ đó; hoặc một người: Mã GV (vd Bộ Môn 3, Chủ Nhiệm 1/1, đánh số theo thứ tự dòng của sheet "
             f"{config.STAFF_SHEET}) hay họ tên (hai người trùng tên thì ghi Mã GV), vd giờ bận: Không xếp vào, "
             "Giáo viên Bộ Môn 3, Thứ 2, tiết 1 (để trống Môn); ép phân công: Chỉ giáo viên dạy, Môn Tiếng Anh, Lớp "
             "3/1, Giáo viên Tiếng Anh 2. Câu đọc lại ghi Mã GV, không ghi họ tên. Nhãn, Trừ nhãn: tên các cột "
             "Có/Không của môn (vd Môn nặng) hoặc của giờ học (ngày, tiết, vd "
             "Luôn do GVCN dạy); nhiều nhãn giờ học là giờ có một trong các nhãn. Gồm môn tăng cường: Có thì Môn tính "
             "cả các môn tăng cường cùng nhóm. Không có sheet này thì chương trình dùng các luật có sẵn và sheet "
             f"{luat_rieng.SHEET} (file của bản trước)."),
            *((f"{luat_rieng.RULES_SHEET}: {k.family + ' · ' if k.family else ''}{k.label}", k.note)
              for f in (*bo_ghep.FAMILIES, "") for k in luat_rieng.KINDS if k.family == f),
            (f"{luat_rieng.RULES_SHEET}: Tự ghép, cột Với mỗi",
             "Chia các tiết thành từng nhóm theo các chiều, vd 'Lớp, Ngày': luật áp dụng cho mỗi lớp mỗi ngày. Các "
             f"chiều: {', '.join(d.label for d in bo_ghep.SCOPES)}. Trống: cả trường cả tuần."),
            *((f"{luat_rieng.RULES_SHEET}: {m.family} · Tự ghép, Phép đo {m.label}",
               m.note + (f" So sánh: {', '.join(bo_ghep.OPS[o] for o in m.ops)}." if m.ops else "")
               + (" Ghi cột Số." if m.number else "") + (" Ghi cột Đếm theo." if m.count_by else ""))
              for f in bo_ghep.FAMILIES for m in bo_ghep.MEASURES if m.family == f),
            (f"{luat_rieng.RULES_SHEET}: Tự ghép, cột Số",
             "Một số nguyên, hoặc (phép đo Số tiết) một ngưỡng theo dữ liệu: "
             f"{', '.join(bo_ghep.DERIVED.values())} (tải ngày: định mức của giáo viên chia theo số tiết của ngày)."),
            (f"{luat_rieng.RULES_SHEET}: Tự ghép, cột Áp dụng khi",
             "Chỉ áp dụng khi số tiết/tuần của các môn ở cột Môn (phạm vi có Môn, Nhóm môn: của từng môn, nhóm môn) ở "
             "khối đó thỏa điều kiện, vd '>= 6, chẵn' (từ 6 tiết trở lên và chẵn) hoặc '<= số ngày' (không quá số "
             "ngày học)."),
            ("LUẬT: cấu trúc của TKB", luat_co_san_structure())]


def luat_co_san_structure() -> str:
    from .luat_co_san import STRUCTURE
    return STRUCTURE
