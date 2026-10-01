"""Các sheet QUY ĐỊNH của file vào: luật nghiệp vụ nhà trường tự sửa trong Excel, không cần sửa mã nguồn.

Bốn sheet, mỗi quy định là một cột (sheet chung: một dòng); mỗi ô chỉ ghi Có, Không hoặc một số nguyên dương, ô
trống là Không (hoặc không áp dụng). Riêng cột Tên trong TKB ghi chữ.
- QUY ĐỊNH CHUNG: Quy định | Giá trị | Ghi chú (số tiết mỗi buổi, giới hạn nhóm môn, ghép cặp, ai được dạy bù).
- QUY ĐỊNH NGÀY: Ngày | Học buổi sáng | Học buổi chiều | Tiết HĐTN cố định | Xếp tiết HĐTN còn lại.
- QUY ĐỊNH TIẾT: Tiết | Luôn do GVCN dạy | Hạn chế môn nặng.
- QUY ĐỊNH MÔN: Môn học | Tên trong TKB | Môn HĐTN | GVCN nhận trọn | ... (mỗi môn một dòng, tên như trong sheet
  CHƯƠNG TRÌNH HỌC).

Sheet, cột (hoặc dòng của sheet chung) nào không có thì quy định đó dùng giá trị mặc định trong tkb/config.py, nên
file vào cũ vẫn chạy như trước. Cột đã có thì là đủ: môn, ngày, tiết không có dòng tính là Không. Trọng số mục tiêu,
tham số xếp giờ và số tiết bù tối đa (main.py) vẫn ở mã nguồn.
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
from .staff import _NO, _YES, InputError, _fold, clean_name, find_sheet, normalize, subject_key

GENERAL_SHEET, DAY_SHEET, PERIOD_SHEET, SUBJECT_SHEET = config.RULES_SHEETS
OLD_SHEET = "QUY ĐỊNH"  # mẫu cũ (Quy định | Giá trị, giá trị ghi chữ), không còn đọc
YES, NO = "Có", "Không"
CODE_HEADER = "Mã Quy Định"  # cột của sheet TKB đã xếp (config.SAVED_SHEET) ghi mã các quy định lúc xếp
MAX_DAYS = 6  # Thứ 2 – Thứ 7
NOTE = "Ghi chú"


@dataclass(frozen=True)
class Col:
    header: str  # tiêu đề cột (sheet chung: chữ ở cột Quy định)
    key: str  # hằng số trong tkb/config.py, hoặc phần của quy định ghép từ nhiều cột (chữ thường)
    kind: str  # "yes": Có/Không; "int": số nguyên dương; "order": số thứ tự 1, 2...; "text": chữ
    note: str


GENERAL = (
    Col("Số tiết buổi sáng", "morning_periods", "int", "Buổi sáng là tiết 1 đến tiết này."),
    Col("Số tiết buổi chiều", "afternoon_periods", "int",
        "Buổi chiều là các tiết tiếp theo, vd sáng 4 tiết, chiều 3 tiết thì chiều là tiết 5, 6, 7."),
    Col("Số tiết tối đa một nhóm môn mỗi buổi", "SESSION_GROUP_LIMIT", "int",
        "Luật cứng; môn có từ 2 tiết trong một buổi thì các tiết đó phải liền nhau."),
    Col("Ghép cặp khi nhóm môn có từ (tiết/tuần)", "PAIR_MIN_LESSONS", "int",
        "Luật cứng: nhóm môn có từ ngần ấy tiết/tuần và tổng số tiết chẵn thì xếp thành các cặp 2 tiết liền, cùng "
        "người dạy (trừ nhóm ghi Có ở cột Không ghép cặp, sheet QUY ĐỊNH MÔN)."),
    Col("Chủ Nhiệm được dạy bù", "overtime_homeroom", "yes", "GVCN chỉ bù ở lớp mình và bù trước bộ môn."),
    Col("Bộ Môn được dạy bù", "overtime_general", "yes", "Bộ môn bù khi GVCN đã bù hết mức."),
)
DAY_KEY = "Ngày"
DAY_COLS = (
    Col("Học buổi sáng", "morning_days", "yes", "Các ngày học, liền nhau từ Thứ 2 (có thể thêm Thứ 7)."),
    Col("Học buổi chiều", "afternoon_days", "yes", "Ngày có buổi chiều (phải là ngày học buổi sáng)."),
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
        "Có ở một môn: môn chào cờ, sinh hoạt lớp, có tiết cố định ở sheet QUY ĐỊNH NGÀY."),
    Col("GVCN nhận trọn", "HOMEROOM_PRIORITY", "order",
        "Số thứ tự 1, 2...: GVCN nhận hết các môn này của lớp mình; luật cứng: môn nào phải chia cho người khác thì "
        "tiết đầu tiên trong tuần do GVCN dạy."),
    Col("GVCN cắt bớt", "HOMEROOM_CUT_ORDER", "order",
        "Số thứ tự cắt khi các môn nhận trọn vượt định mức GVCN; mỗi môn GVCN giữ ít nhất 1 tiết."),
    Col("GVCN nhận thêm", "HOMEROOM_FILL_ORDER", "order",
        "Số thứ tự nhận thêm cho đủ định mức GVCN (không nhận môn của GV chuyên biệt)."),
    Col("Chỉ GVCN dạy", "HOMEROOM_ONLY_SUBJECTS", "yes", "Luật cứng: chỉ GVCN của lớp được dạy."),
    Col("Bộ Môn không dạy", "GENERAL_FORBIDDEN_SUBJECTS", "yes",
        "GV bộ môn không dạy môn này; trường chưa có GV chuyên biệt của môn thì chương trình tuyển thêm."),
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
    Col("Không ghép cặp", "PAIR_EXCLUDED", "yes", "Nhóm môn (ghi ở môn chính) không xếp thành cặp 2 tiết liền."),
    Col("Môn nặng", "HEAVY_SUBJECTS", "yes", "Mục tiêu mềm: hạn chế xếp vào các tiết Hạn chế môn nặng (QUY ĐỊNH TIẾT)."),
    Col("Ưu tiên buổi sáng", "MORNING_SUBJECTS", "yes",
        "Mục tiêu mềm: mỗi tiết ở buổi chiều bị trừ điểm, và môn được rải đều hơn trong tuần."),
)
FRAME_ATTRS = ("DAYS", "MORNING", "AFTERNOON", "DAY_SESSIONS")
ATTRS = (*FRAME_ATTRS, "SESSION_GROUP_LIMIT", "PAIR_MIN_LESSONS", "OVERTIME_ROLES", "HDTN_FIXED_SLOTS",
         "HDTN_FLEX_DAYS", "HOMEROOM_PERIODS", "HEAVY_LATE_PERIODS", "DISPLAY_NAMES", "HDTN", "HOMEROOM_PRIORITY",
         "HOMEROOM_CUT_ORDER", "HOMEROOM_FILL_ORDER", "HOMEROOM_ONLY_SUBJECTS", "GENERAL_FORBIDDEN_SUBJECTS",
         "MANAGER_RULES", "HOMEROOM_OVERTIME_SPECIALIST", "SUBJECT_GROUPS", "DAILY_LIMITS", "PAIR_EXCLUDED",
         "HEAVY_SUBJECTS", "MORNING_SUBJECTS")
# Tên quy định khi in "khác mặc định".
LABELS = {**{c.key: c.header for c in (*GENERAL, *DAY_COLS, *PERIOD_COLS, *SUBJECT_COLS)},
          **{a: "Khung giờ" for a in FRAME_ATTRS}, "OVERTIME_ROLES": "Được dạy bù",
          "SUBJECT_GROUPS": "Nhóm môn, Môn tăng cường"}
DEFAULTS = {attr: copy.deepcopy(getattr(config, attr)) for attr in ATTRS}  # giá trị mặc định trong tkb/config.py
# Tên môn trong tkb/config.py (và chữ viết tắt mặc định), để khớp tên môn ghi trong sheet QUY ĐỊNH MÔN.
_KNOWN = {**{subject_key(label): s for s, label in config.DISPLAY_NAMES.items()},
          **{subject_key(s): s for s in config.rule_subjects()}}
_ROLES = {"overtime_homeroom": config.ROLE_HOMEROOM, "overtime_general": config.ROLE_GENERAL}


def _day_name(d: int) -> str:
    return f"Thứ {d + 2}"


def _frame_now() -> dict[str, object]:
    """Khung giờ theo config hiện tại: ngày học buổi sáng, buổi chiều, số tiết mỗi buổi."""
    return {"morning_days": sorted(config.DAY_SESSIONS),
            "afternoon_days": [d for d, ss in sorted(config.DAY_SESSIONS.items())
                               if any(s.name == config.AFTERNOON.name for s in ss)],
            "morning_periods": len(config.MORNING.periods),
            "afternoon_periods": len(config.AFTERNOON.periods)}


def _build_frame(f: dict[str, object]) -> dict[str, object]:
    """Khung giờ -> config.DAYS, MORNING, AFTERNOON, DAY_SESSIONS."""
    m, a = f["morning_periods"], f["afternoon_periods"]
    morning = config.Session(config.MORNING.name, tuple(range(1, m + 1)))
    afternoon = config.Session(config.AFTERNOON.name, tuple(range(m + 1, m + a + 1)))
    days = f["morning_days"]
    sessions = {d: (morning, afternoon) if d in f["afternoon_days"] else (morning,) for d in days}
    return {"DAYS": [_day_name(d) for d in days], "MORNING": morning, "AFTERNOON": afternoon, "DAY_SESSIONS": sessions}


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


class _Reader:
    """Đọc bốn sheet QUY ĐỊNH; gom mọi lỗi (sheet, dòng, lỗi) để báo cùng lúc."""

    def __init__(self):
        self.frame = _frame_now()
        self.frame_given = False
        self.values: dict[str, object] = {}
        self.errors: list[tuple[int, int, str]] = []

    def error(self, sheet: str, row: int | None, text: str) -> None:
        where = f"{sheet}, dòng {row}" if row else sheet
        self.errors.append((config.RULES_SHEETS.index(sheet), row or 10 ** 6, f"{where}: {text}"))

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
        return None if _blank(value) else clean_name(value)

    def header(self, ws, *names: str) -> tuple[int, dict[str, int]] | None:
        """Dòng tiêu đề (trong 20 dòng đầu) có đủ các cột `names`: (dòng, {tiêu đề chuẩn hóa: cột})."""
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 20)):
            heads = {normalize(c.value): c.column for c in row if not _blank(c.value)}
            if all(normalize(n) in heads for n in names):
                return row[0].row, heads
        self.error(ws.title, None, f"không có dòng tiêu đề có cột {', '.join(names)}")
        return None

    def table(self, ws, key_header: str, cols: tuple[Col, ...]):
        """Bảng có cột khóa `key_header`: ({khóa của cột: số cột}, [(dòng, ô khóa, {khóa của cột: giá trị})])."""
        sheet = ws.title
        found_header = self.header(ws, key_header)
        if found_header is None:
            return {}, []
        header_row, heads = found_header
        key_col = heads[normalize(key_header)]
        wanted = {normalize(c.header): c for c in cols}
        found: dict[str, int] = {}
        for head, c in heads.items():
            if c == key_col or head == normalize(NOTE):
                continue
            col = wanted.get(head)
            if col is None:
                self.error(sheet, header_row, f"không có quy định nào tên '{ws.cell(header_row, c).value}' "
                                              f"(các cột: {', '.join(x.header for x in cols)})")
            else:
                found[col.key] = c
        by_key = {c.key: c for c in cols}
        rows = []
        for r in range(header_row + 1, ws.max_row + 1):
            key = ws.cell(r, key_col).value
            values = {k: ws.cell(r, c).value for k, c in found.items()}
            if _blank(key):
                if any(not _blank(v) for v in values.values()):
                    self.error(sheet, r, f"thiếu {key_header}")
                continue
            rows.append((r, key, {k: self.cell(sheet, r, by_key[k], v) for k, v in values.items()}))
        return found, rows

    def general(self, ws) -> None:
        sheet = ws.title
        found_header = self.header(ws, "Quy định", "Giá trị")
        if found_header is None:
            return
        header_row, heads = found_header
        label_col, value_col = heads[normalize("Quy định")], heads[normalize("Giá trị")]
        by_label = {subject_key(c.header): c for c in GENERAL}
        seen: dict[str, int] = {}
        roles = set(config.OVERTIME_ROLES)
        for r in range(header_row + 1, ws.max_row + 1):
            label = ws.cell(r, label_col).value
            if _blank(label):
                continue
            col = by_label.get(subject_key(label))
            if col is None:
                self.error(sheet, r, f"không có quy định '{clean_name(label)}'")
                continue
            if col.key in seen:
                self.error(sheet, r, f"quy định '{col.header}' bị lặp với dòng {seen[col.key]}")
                continue
            seen[col.key] = r
            raw = ws.cell(r, value_col).value
            value = self.cell(sheet, r, col, raw)
            if col.kind == "int" and value is None:
                if _blank(raw):
                    self.error(sheet, r, f"chưa ghi số ở cột Giá trị ({col.header})")
                continue
            if col.key in _ROLES:
                roles = roles | {_ROLES[col.key]} if value else roles - {_ROLES[col.key]}
                self.values["OVERTIME_ROLES"] = roles
            elif col.key in ("morning_periods", "afternoon_periods"):
                self.frame[col.key] = value
                self.frame_given = True
            else:
                self.values[col.key] = value

    def days(self, ws) -> None:
        sheet = ws.title
        found, rows = self.table(ws, DAY_KEY, DAY_COLS)
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
                self.frame[key] = [d for d in days if by_day[d][key]]
                self.frame_given = True
        if "HDTN_FIXED_SLOTS" in found:
            self.values["HDTN_FIXED_SLOTS"] = [(d, by_day[d]["HDTN_FIXED_SLOTS"]) for d in days
                                               if by_day[d]["HDTN_FIXED_SLOTS"] is not None]
        if "HDTN_FLEX_DAYS" in found:
            self.values["HDTN_FLEX_DAYS"] = [d for d in days if by_day[d]["HDTN_FLEX_DAYS"]]

    def periods(self, ws) -> None:
        sheet = ws.title
        found, rows = self.table(ws, PERIOD_KEY, PERIOD_COLS)
        seen: dict[int, dict] = {}
        for r, key, values in rows:
            p = self.number(sheet, r, PERIOD_KEY, key)
            if p is not None and p in seen:
                self.error(sheet, r, f"tiết {p} bị lặp")
            elif p is not None:
                seen[p] = values
        for key in found:
            self.values[key] = {p for p, values in seen.items() if values[key]}

    def subjects(self, ws) -> None:
        sheet = ws.title
        found, rows = self.table(ws, SUBJECT_KEY, SUBJECT_COLS)
        labels = {subject_key(v["DISPLAY_NAMES"]): clean_name(k) for _, k, v in rows if v.get("DISPLAY_NAMES")}
        names: list[tuple[int, str, dict]] = []
        seen: dict[str, int] = {}
        for r, key, values in rows:
            k = subject_key(key)
            name = _KNOWN.get(k) or _KNOWN.get(subject_key(labels.get(k, ""))) or clean_name(key)
            if name in seen:
                self.error(sheet, r, f"môn {clean_name(key)} bị lặp với dòng {seen[name]}")
                continue
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
            self.error(sheet, None, "cột Nhóm môn và cột Môn tăng cường phải có cùng nhau")
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

    def finish(self) -> dict[str, object]:
        f = self.frame
        morning = f["morning_days"]
        if not morning or morning != list(range(len(morning))):
            self.error(DAY_SHEET, None, "các ngày Học buổi sáng phải liền nhau từ Thứ 2")
        elif any(d not in morning for d in f["afternoon_days"]):
            self.error(DAY_SHEET, None, "ngày Học buổi chiều phải là ngày Học buổi sáng")
        if self.frame_given:
            self.values.update(_build_frame(f))
        # Ngày, tiết các quy định nhắc tới (kể cả giá trị mặc định) phải có trong khung giờ.
        get = lambda attr: self.values.get(attr, getattr(config, attr))  # noqa: E731
        afternoon = set(f["afternoon_days"])
        n_periods = lambda d: f["morning_periods"] + (f["afternoon_periods"] if d in afternoon else 0)  # noqa: E731
        for d, p in get("HDTN_FIXED_SLOTS"):
            if d not in morning or p > n_periods(d):
                self.error(DAY_SHEET, None, f"Tiết HĐTN cố định {_day_name(d)} tiết {p} không có trong khung giờ")
        for d in get("HDTN_FLEX_DAYS"):
            if d not in morning:
                self.error(DAY_SHEET, None, f"Xếp tiết HĐTN còn lại vào {_day_name(d)} nhưng ngày đó không học")
        total = f["morning_periods"] + f["afternoon_periods"]
        for attr in ("HOMEROOM_PERIODS", "HEAVY_LATE_PERIODS"):
            for p in sorted(get(attr)):
                if p > total:
                    self.error(PERIOD_SHEET, None, f"{LABELS[attr]}: không có tiết {p} trong khung giờ (mỗi ngày tối "
                                                   f"đa {total} tiết)")
        return self.values


def read_rules(path: str | Path) -> dict[str, object] | None:
    """Đọc các sheet QUY ĐỊNH của file vào. Trả về {hằng số trong config: giá trị} của các quy định có trong file
    (khung giờ gộp thành DAYS, MORNING, AFTERNOON, DAY_SESSIONS); None nếu file không có sheet quy định nào. Báo mọi
    lỗi cùng lúc (InputError)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    if find_sheet(wb, OLD_SHEET) is not None:
        raise InputError(f"Sheet {OLD_SHEET} theo mẫu cũ (Quy định | Giá trị) không còn đọc: nay quy định nằm ở các "
                         f"sheet {', '.join(config.RULES_SHEETS)}, mỗi ô ghi Có, Không hoặc số. Tạo file mẫu mới "
                         f"(python -m tkb.template) rồi chép các quy định sang, hoặc xóa sheet {OLD_SHEET} để dùng "
                         f"giá trị mặc định")
    sheets = [find_sheet(wb, name) for name in config.RULES_SHEETS]
    if all(ws is None for ws in sheets):
        return None
    reader = _Reader()
    for ws, read in zip(sheets, (reader.general, reader.days, reader.periods, reader.subjects)):
        if ws is not None:
            read(ws)
    values = reader.finish()
    if reader.errors:
        lines = list(dict.fromkeys(text for *_, text in sorted(reader.errors)))
        raise InputError(f"Các sheet quy định có {len(lines)} lỗi:\n  " + "\n  ".join(lines))
    return values


@contextmanager
def applied(values: dict[str, object] | None):
    """Dùng các quy định đọc từ file vào trong khối `with`; ra khỏi khối thì trả lại giá trị cũ."""
    old = {attr: getattr(config, attr) for attr in (values or {})}
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
    return list(dict.fromkeys(LABELS[a] for a in ATTRS if a in values and values[a] != DEFAULTS[a]))


def _canonical(attr: str, value):
    """Giá trị viết theo một cách duy nhất (tập hợp sắp xếp; tên viết tắt không phụ thuộc thứ tự dòng)."""
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if attr == "DISPLAY_NAMES":
        return sorted(value.items())
    return value


def code() -> str:
    """Mã của các quy định đang dùng (12 chữ số hex): quy định khác nhau thì mã khác nhau, mọi máy cùng mã."""
    text = "\n".join(f"{attr}={_canonical(attr, getattr(config, attr))!r}" for attr in ATTRS)
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


def tables(subjects=()) -> list[tuple[str, list[str], list[list]]]:
    """Bốn bảng quy định theo config hiện tại: [(tên sheet, tiêu đề, các dòng)], để ghi file mẫu và file vào cập
    nhật. `subjects`: các môn của chương trình học, tên như trong file vào (dòng sheet QUY ĐỊNH MÔN theo thứ tự này,
    rồi đến các môn có quy định mà chương trình học không có)."""
    from .program import canonical_subject

    yn = lambda on: YES if on else NO  # noqa: E731
    f = _frame_now()
    general = {"morning_periods": f["morning_periods"], "afternoon_periods": f["afternoon_periods"],
               "SESSION_GROUP_LIMIT": config.SESSION_GROUP_LIMIT, "PAIR_MIN_LESSONS": config.PAIR_MIN_LESSONS,
               **{k: yn(role in config.OVERTIME_ROLES) for k, role in _ROLES.items()}}
    out = [(GENERAL_SHEET, ["Quy định", "Giá trị", NOTE], [[c.header, general[c.key], c.note] for c in GENERAL])]

    fixed = dict(config.HDTN_FIXED_SLOTS)
    flex = set(config.HDTN_FLEX_DAYS)
    days = [[_day_name(d), yn(d in f["morning_days"]), yn(d in f["afternoon_days"]), fixed.get(d), yn(d in flex)]
            for d in range(MAX_DAYS)]
    out.append((DAY_SHEET, [DAY_KEY, *(c.header for c in DAY_COLS)], days))

    total = f["morning_periods"] + f["afternoon_periods"]
    periods = [[p, yn(p in config.HOMEROOM_PERIODS), yn(p in config.HEAVY_LATE_PERIODS)] for p in range(1, total + 1)]
    out.append((PERIOD_SHEET, [PERIOD_KEY, *(c.header for c in PERIOD_COLS)], periods))

    names = {canonical_subject(s): clean_name(s) for s in subjects}
    rest = sorted((s for s in config.rule_subjects() if s not in names), key=subject_key)
    groups: dict[str, int] = {}
    for extra, main in config.SUBJECT_GROUPS.items():
        groups.setdefault(main, len(set(groups.values())) + 1)
        groups[extra] = groups[main]
    rank = lambda attr, s: (getattr(config, attr).index(s) + 1 if s in getattr(config, attr) else None)  # noqa: E731
    managers = {r.subject: r.grade for r in config.MANAGER_RULES}
    rows = []
    for s in [*names, *rest]:
        rows.append([names.get(s, s), config.DISPLAY_NAMES.get(s), yn(s == config.HDTN),
                     rank("HOMEROOM_PRIORITY", s), rank("HOMEROOM_CUT_ORDER", s), rank("HOMEROOM_FILL_ORDER", s),
                     yn(s in config.HOMEROOM_ONLY_SUBJECTS), yn(s in config.GENERAL_FORBIDDEN_SUBJECTS),
                     managers.get(s), yn(s in config.HOMEROOM_OVERTIME_SPECIALIST), groups.get(s),
                     yn(s in config.SUBJECT_GROUPS), config.DAILY_LIMITS.get(s), yn(s in config.PAIR_EXCLUDED),
                     yn(s in config.HEAVY_SUBJECTS), yn(s in config.MORNING_SUBJECTS)])
    out.append((SUBJECT_SHEET, [SUBJECT_KEY, *(c.header for c in SUBJECT_COLS)], rows))
    return out


def notes() -> list[tuple[str, str]]:
    """Giải thích từng cột của các sheet quy định (cho sheet HƯỚNG DẪN): [(sheet: cột, cách ghi)]."""
    return [(f"{sheet}: {c.header}", c.note)
            for sheet, cols in ((DAY_SHEET, DAY_COLS), (PERIOD_SHEET, PERIOD_COLS), (SUBJECT_SHEET, SUBJECT_COLS))
            for c in cols]
