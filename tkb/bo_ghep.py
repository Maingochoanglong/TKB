"""Bộ ghép luật: mọi luật viết theo một câu chung, mỗi phép đo viết code một lần cho mọi nơi.

    Với mỗi [phạm vi] · chỉ xét các tiết [điều kiện] · thì [phép đo] [so sánh] [ngưỡng] · khi [...] · [mức]

- Phạm vi (`SCOPES`): các chiều chia nhóm tiết, vd lớp × buổi, GV × ngày; trống là cả trường cả tuần.
- Điều kiện: môn (cả môn tăng cường cùng nhóm nếu muốn), nhãn (tiêu đề các cột Có/Không của môn, ngày, tiết, vd
  Môn nặng, Luôn do GVCN dạy), khối, lớp, ngày, tiết, buổi, chức vụ GV.
- Phép đo (`MEASURES`): số tiết, số giá trị khác nhau, vị trí, liền nhau, theo cặp, thứ tự, đi kèm, người dạy,
  khoảng cách.
- Mức: bắt buộc, hoặc ưu tiên Thấp/Vừa/Cao/Rất cao (mức 1–4, `config.Weights.custom_levels`) hoặc Điểm.

Một luật (dòng của sheet LUẬT RIÊNG, `config.CustomRule`) được chuẩn hóa thành `Luat` (`make`); các mẫu có sẵn
(luat_rieng.KINDS) chỉ là cách điền sẵn câu. Mỗi phép đo là một hàm viết trên một "ngữ cảnh": cùng hàm đó
dựng ràng buộc CP-SAT (`_Cp`) và đếm số lần không theo trên một TKB (`_Eval`, dùng cho kiểm tra độc lập, QA của
LNS, báo cáo). Phép đếm trước khi xếp (`precheck`), cắt miền ô (`banned`), ghép cặp (`forced_pairs`), giới hạn ngày
của GV (`day_cap`) và tầng phân công (`allowed`, `assign_cost`) đọc cùng luật chuẩn hóa.

Không có luật nào (config.CUSTOM_RULES rỗng) thì không hàm nào ở đây thêm gì vào mô hình: mã kết quả không đổi.
Luật có sẵn của chương trình giữ cách mã hóa riêng trong solver (để mã không đổi); `co_san()` viết chúng bằng cùng
câu để hiển thị và kiểm chéo.
"""
from __future__ import annotations

import functools
import itertools
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import config
from .config import CustomRule
from .staff import _fold, class_tags, grade_key, grade_of


# --------------------------------------------------------------------------
# Từ vựng
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Dim:
    key: str
    label: str  # chữ ghi ở cột Với mỗi, Đếm theo
    aliases: tuple[str, ...] = ()
    unit: str = ""  # chữ khi đếm, vd "lớp" trong "3 lớp khác nhau"


SCOPES = (
    Dim("lop", "Lớp", unit="lớp"),
    Dim("gv", "Giáo viên", ("gv",), unit="giáo viên"),
    Dim("mon", "Môn", unit="môn"),
    Dim("nhom_mon", "Nhóm môn", unit="nhóm môn"),
    Dim("khoi", "Khối", unit="khối"),
    Dim("ngay", "Ngày", unit="ngày"),
    Dim("buoi", "Buổi", unit="buổi"),
    Dim("o", "Giờ học", ("ô", "thời điểm", "tiết học", "giờ"), unit="giờ học"),
    Dim("co_so", "Cơ sở", unit="cơ sở"),
)
SCOPE = {d.key: d for d in SCOPES}
TIME_DIMS = ("ngay", "buoi", "o")


@dataclass(frozen=True)
class Measure:
    key: str
    label: str  # chữ ghi ở cột Phép đo
    ops: tuple[str, ...]  # các so sánh được dùng; () = không ghi cột So sánh
    number: bool  # phải ghi cột Số
    other: bool = False  # phải ghi cột Môn thứ hai
    count_by: bool = False  # phải ghi cột Đếm theo
    sequence: bool = False  # xét thứ tự các tiết trong buổi: phạm vi phải có Lớp hoặc Giáo viên
    note: str = ""
    default_op: str = ""  # so sánh khi cột So sánh để trống (thì không bắt buộc ghi)
    family: str = ""  # họ luật (FAMILIES): giao diện xếp phép đo theo câu hỏi luật trả lời


COUNT_OPS = ("<=", ">=", "=")
# Bốn họ luật: mỗi luật trả lời một câu hỏi về các tiết. Mẫu luật (luat_rieng.KINDS) và phép đo đều thuộc một họ, để
# giao diện chọn loại luật theo câu hỏi thay vì theo tên kỹ thuật.
FAMILIES = ("Ở đâu", "Bao nhiêu", "Đi cùng nhau", "Ai dạy")
MEASURES = (
    Measure("so_tiet", "Số tiết", COUNT_OPS, True, family="Bao nhiêu",
            note="Đếm số tiết trong mỗi phạm vi, vd mỗi lớp mỗi ngày học tối đa 1 tiết Toán; mỗi giờ học có tối đa "
                 "1 tiết Tin học."),
    Measure("so_khac", "Số khác nhau", COUNT_OPS, True, count_by=True, family="Bao nhiêu",
            note="Đếm số lớp, ngày, cơ sở… khác nhau (cột Đếm theo), vd mỗi giáo viên mỗi ngày dạy tối đa 3 lớp; mỗi "
                 "lớp học Tiếng Anh ít nhất 3 ngày."),
    Measure("vi_tri", "Vị trí", ("trong", "ngoai"), False, family="Ở đâu",
            note="Các tiết chỉ xếp vào, hoặc không xếp vào, các ngày, tiết, buổi (hoặc giờ có nhãn) ghi ở dòng này."),
    Measure("lien", "Liền nhau", (), False, sequence=True, family="Đi cùng nhau",
            note="Các tiết trong một buổi (của mỗi lớp hoặc giáo viên) đứng liền nhau, không có tiết khác xen giữa."),
    Measure("cap", "Theo cặp 2 tiết", (), False, sequence=True, family="Đi cùng nhau",
            note="Mỗi buổi học 0 hoặc 2 tiết, 2 tiết đó liền nhau (ưu tiên: hạn chế tiết lẻ đứng một mình)."),
    Measure("thu_tu", "Thứ tự", ("truoc", "sau"), False, other=True, sequence=True, default_op="truoc",
            family="Đi cùng nhau",
            note="Trong một buổi (hoặc ngày, nếu Với mỗi có Ngày) tiết của Môn đứng trước (hoặc sau) tiết của Môn thứ "
                 "hai. Để trống Môn thứ hai và Với mỗi có Nhóm môn: các môn khác cùng nhóm."),
    Measure("di_kem", "Đi kèm", (), False, other=True, sequence=True, family="Đi cùng nhau",
            note="Buổi (hoặc ngày) có tiết của Môn thì cũng có tiết của Môn thứ hai. Để trống Môn thứ hai và Với mỗi "
                 "có Nhóm môn: các môn khác cùng nhóm."),
    Measure("nguoi_day", "Người dạy", ("do", "cung_nguoi", "lien_cung_nguoi", "dau_tuan"), False, family="Ai dạy",
            note="Các tiết do giáo viên ghi ở cột Giáo viên (chức vụ, Mã GV hoặc họ tên) dạy; hoặc do cùng một người "
                 "dạy; hoặc hai tiết liền nhau do cùng một người; hoặc tiết đầu tuần do giáo viên đó dạy, tiết của "
                 "người khác không đứng trước."),
    Measure("khoang_cach", "Khoảng cách", ("trong_tiet", "cuoi_buoi"), True, sequence=True, family="Bao nhiêu",
            note="Số tiết trống xen giữa các tiết trong buổi (0: không có tiết trống); hoặc số tiết từ tiết đó đến "
                 "cuối buổi (0: ở tiết cuối buổi)."),
)
MEASURE = {m.key: m for m in MEASURES}
OPS = {"<=": "Tối đa", ">=": "Tối thiểu", "=": "Đúng", "trong": "Chỉ trong", "ngoai": "Không trong", "do": "Do",
       "cung_nguoi": "Cùng một người", "lien_cung_nguoi": "Liền nhau cùng người", "dau_tuan": "Tiết đầu tuần do",
       "trong_tiet": "Tiết trống tối đa", "cuoi_buoi": "Cách cuối buổi tối đa", "truoc": "Trước", "sau": "Sau"}
# Ngưỡng theo dữ liệu, ghi ở cột Số thay cho một số (phép đo Số tiết).
DERIVED = {"tai_ngay": "tải ngày", "tai_ngay_1": "tải ngày + 1", "tran_ngay": "số tiết/tuần chia số ngày"}
NOT = "trừ "  # cột Giáo viên: "trừ Chủ Nhiệm" là mọi GV trừ chức vụ đó (hay trừ người đó)
OP_ALIASES = {"<=": ("≤", "tối đa", "nhiều nhất"), ">=": ("≥", "tối thiểu", "ít nhất"), "=": ("đúng", "bằng")}
NUMBER_DAYS = -1  # cột Áp dụng khi: "≤ số ngày" (số ngày học trong tuần)


def subject_tags() -> dict[str, set[str]]:
    """Nhãn môn: tiêu đề cột Có/Không (và cột số thứ tự) của sheet CHƯƠNG TRÌNH HỌC -> các môn ghi Có (config hiện
    tại). Thêm một cột Có/Không vào rules.SUBJECT_COLS là có thêm một nhãn."""
    from .rules import SUBJECT_COLS
    out = {}
    for col in SUBJECT_COLS:
        if col.kind not in ("yes", "order"):
            continue
        if col.key == "extra":
            value = set(config.SUBJECT_GROUPS)
        elif col.key == "HDTN":
            value = {config.HDTN} if config.HDTN else set()
        else:
            value = getattr(config, col.key, None)
            if value is None:
                continue
        out[col.header] = set(value)
    return out


def slot_tags() -> dict[str, set[tuple[int, int]]]:
    """Nhãn ô: tiêu đề cột Có/Không của bảng Ngày, bảng Tiết (sheet QUY ĐỊNH) -> các ô (ngày, tiết) ghi Có."""
    from .rules import DAY_COLS, PERIOD_COLS
    slots = _all_slots()
    out = {}
    for col in PERIOD_COLS:
        periods = getattr(config, col.key, None)
        if col.kind == "yes" and periods is not None:
            out[col.header] = {s for s in slots if s[1] in periods}
    for col in DAY_COLS:
        if col.key == "HDTN_FLEX_DAYS":
            out[col.header] = {s for s in slots if s[0] in config.HDTN_FLEX_DAYS}
        elif col.key == "HDTN_FIXED_SLOTS":
            out[col.header] = set(config.HDTN_FIXED_SLOTS)
    return out


def tag_names() -> list[str]:
    """Mọi nhãn ghi được ở cột Nhãn (không phụ thuộc file vào)."""
    from .rules import DAY_COLS, PERIOD_COLS, SUBJECT_COLS
    return [*(c.header for c in SUBJECT_COLS if c.kind in ("yes", "order")),
            *(c.header for c in PERIOD_COLS if c.kind == "yes"),
            *(c.header for c in DAY_COLS if c.key in ("HDTN_FLEX_DAYS", "HDTN_FIXED_SLOTS"))]


# --------------------------------------------------------------------------
# Luật chuẩn hóa
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Luat:
    rule: CustomRule
    scope: tuple[str, ...]
    measure: str
    op: str
    number: int
    subjects: frozenset[str] | None  # môn (tên trong config); None = mọi môn
    grades: frozenset[int] | None
    classes: frozenset[str] | None
    slots: frozenset[tuple[int, int]] | None  # ô được xét; None = mọi ô
    roles: frozenset[str] | None  # GV được xét (chức vụ, Mã GV, họ tên; xem `picks`); None = mọi GV
    place: frozenset[tuple[int, int]] = frozenset()  # phép đo Vị trí: các ô ghi ở dòng
    other: frozenset[str] | None = None  # Môn thứ hai
    who: frozenset[str] = frozenset()  # phép đo Người dạy "Do": các GV được dạy (chức vụ, Mã GV, họ tên)
    count_by: str = ""
    when: tuple[tuple[str, int], ...] = ()
    skip: frozenset[str] = frozenset()  # môn bị trừ (cột Trừ nhãn)
    roles_not: frozenset[str] = frozenset()  # GV bị trừ (cột Giáo viên "trừ ...")
    derived: str = ""

    @property
    def hard(self) -> bool:
        return self.rule.hard

    @property
    def lesson_only(self) -> bool:
        """Chỉ xét môn, khối, lớp (không ô, không GV): áp dụng được ở tầng phân công."""
        return self.slots is None and self.roles is None

    def teacher(self) -> bool:
        """Cần biết GV dạy từng tiết."""
        return ("gv" in self.scope or self.count_by == "gv" or self.roles is not None or bool(self.roles_not)
                or self.measure == "nguoi_day")


def _subject(name: str) -> str:
    from .program import canonical_subject
    return canonical_subject(name)


def names(text: str) -> list[str]:
    """"Toán, Tiếng Việt; Tin học" -> các tên (bỏ ô trống)."""
    import re
    return [p.strip() for p in re.split(r"[,;]", text or "") if p.strip()]


def _all_slots() -> set[tuple[int, int]]:
    return {(d, p) for d, ss in config.DAY_SESSIONS.items() for s in ss for p in s.periods}


def rule_slots(rule: CustomRule) -> set[tuple[int, int]] | None:
    """Các ô khớp cột Ngày, Tiết, Buổi và nhãn ô của luật; None nếu luật không ghi cột nào trong số đó."""
    tags = slot_tags()
    slot_tag = [t for t in rule.tags if t in tags]
    skip = [t for t in rule.exclude if t in tags]
    if not (rule.days or rule.periods or rule.sessions or slot_tag or skip):
        return None
    out = set()
    for d, sessions in config.DAY_SESSIONS.items():
        if rule.days and d not in rule.days:
            continue
        for s in sessions:
            if rule.sessions and s.name not in rule.sessions:
                continue
            out |= {(d, p) for p in s.periods if not rule.periods or p in rule.periods}
    if slot_tag:  # nhiều nhãn ô: ô có một trong các nhãn
        out &= set().union(*(tags[t] for t in slot_tag))
    for t in skip:
        out -= tags[t]
    return out


def _subjects(rule: CustomRule, text: str, group: bool) -> frozenset[str] | None:
    from .allocation import subject_group
    tags = subject_tags()
    chosen = {_subject(n) for n in names(text)}
    for t in rule.tags:
        chosen |= tags.get(t, set())
    if not chosen and not any(t in tags for t in rule.tags):
        return None
    if group:  # cả các môn cùng nhóm (môn chính và các môn tăng cường của nó)
        groups = {subject_group(s) for s in chosen}
        chosen |= {s for s, main in config.SUBJECT_GROUPS.items() if main in groups} | groups
    return frozenset(chosen)


PRESETS = {  # mẫu -> (phạm vi, phép đo, so sánh, đếm theo)
    "khong_xep": ((), "vi_tri", "ngoai", ""),
    "chi_xep": ((), "vi_tri", "trong", ""),
    "lien_2": (("lop", "buoi"), "cap", "", ""),
    "truoc": (("lop", "buoi"), "thu_tu", "", ""),
    "gv_ngay": (("gv", "ngay"), "so_tiet", "<=", ""),
    "cung_luc": (("o",), "so_tiet", "<=", ""),
    "co_dinh": (("lop", "o"), "so_tiet", "=", ""),
    "gv_lop_ngay": (("gv", "ngay"), "so_khac", "<=", "lop"),
    "rai_ngay": (("lop",), "so_khac", ">=", "ngay"),
    "chi_gv": ((), "nguoi_day", "do", ""),
}


def role_names(text: str) -> tuple[list[str], list[str]]:
    """Cột Giáo viên -> (GV được xét, GV bị trừ), vd "trừ Chủ Nhiệm"; mỗi tên là chức vụ, Mã GV hoặc họ tên."""
    from .staff import normalize
    keep, drop = [], []
    for name in names(text):
        name = normalize(name)
        (drop if name.startswith(NOT) else keep).append(name[len(NOT):].strip() if name.startswith(NOT) else name)
    return keep, drop


def person_keys(t) -> frozenset[str]:
    """Các cách ghi riêng một GV ở cột Giáo viên (chuẩn hóa): Mã GV (vd "bộ môn 3", "chủ nhiệm 1/1") và họ tên (trừ
    tên "chưa có" của người tuyển thêm)."""
    return _person_keys(t.title, t.code, t.name)


@functools.lru_cache(maxsize=None)
def _person_keys(title: str, code: str, name: str) -> frozenset[str]:
    from .staff import normalize
    name = normalize(name)
    named = {name} if name and name != normalize(config.SUPPLEMENT_NAME) else set()
    return frozenset({title, normalize(code)} | named)


def picks(names: frozenset[str], t) -> bool:
    """GV t khớp một tên ở cột Giáo viên: chức vụ của t (cả chức vụ ở cột Chức Vụ Thêm), nhãn (Teacher.tag_keys), Mã GV
    hoặc họ tên của t."""
    return (t.role in names or not names.isdisjoint(t.extra_roles) or not names.isdisjoint(t.tag_keys)
            or not names.isdisjoint(person_keys(t)))


def know_staff(teachers) -> None:
    """Ghi config.PEOPLE (người -> Mã GV) để câu đọc lại ghi Mã GV thay cho họ tên; tên trùng nhau thì bỏ (validate
    báo). Gọi trong rules.applied, sau khi đọc nhân sự."""
    from .staff import normalize
    count = Counter(normalize(t.name) for t in teachers)
    people = {}
    for t in teachers:
        for k in person_keys(t):
            if k != normalize(t.name) or count[k] == 1:
                people[k] = t.code
    config.PEOPLE = people


def person(name: str) -> str | None:
    """Mã GV nếu tên ở cột Giáo viên (chuẩn hóa) là một người: Mã GV, hoặc họ tên có trong config.PEOPLE; None: chức
    vụ. Chức vụ không có chữ số (staff.read_staff) nên tên có chữ số là Mã GV."""
    if name in config.PEOPLE:
        return config.PEOPLE[name]
    return name.title() if any(ch.isdigit() for ch in name) else None


def make(rule: CustomRule) -> Luat:
    """Một luật (mẫu hoặc tự ghép) -> luật chuẩn hóa theo config hiện tại."""
    scope, measure, op, count_by = PRESETS.get(rule.kind, (rule.scope, rule.measure, rule.op, rule.count_by))
    if not op and measure in MEASURE:
        op = MEASURE[measure].default_op
    group = rule.group or rule.kind == "lien_2"
    slots = rule_slots(rule)
    keep, drop = role_names(rule.role)
    roles = frozenset(keep) or None
    who: frozenset[str] = frozenset()
    if measure == "nguoi_day" and op in ("do", "dau_tuan"):
        who, roles = roles or frozenset(), None
    place: frozenset = frozenset()
    if measure == "vi_tri":
        place, slots = frozenset(slots or ()), None
    in_session = measure in MEASURE and MEASURE[measure].sequence or (measure, op) == ("nguoi_day", "lien_cung_nguoi")
    if in_session and not any(d in scope for d in ("ngay", "buoi")):
        scope = (*scope, "buoi")
    if (measure in ("lien", "cap", "khoang_cach") or op == "lien_cung_nguoi") and "ngay" in scope:
        scope = tuple("buoi" if d == "ngay" else d for d in scope)
    number = rule.number if rule.number is not None else (1 if rule.kind == "co_dinh" else 0)
    tags = subject_tags()
    skip = frozenset(s for t in rule.exclude for s in tags.get(t, ()))
    return Luat(rule=rule, scope=tuple(scope), measure=measure, op=op, number=number,
                subjects=_subjects(rule, rule.subject, group), grades=frozenset(rule.grades) or None,
                classes=_classes(rule.classes), slots=frozenset(slots) if slots is not None else None,
                roles=roles, place=place,
                other=frozenset(_subject(n) for n in names(rule.other)) or None, who=who, count_by=count_by,
                when=rule.when, skip=skip, roles_not=frozenset(drop), derived=rule.derived)


def _classes(written: tuple[str, ...]) -> frozenset[str] | None:
    """Cột Lớp -> các lớp: tên lớp, hoặc nhãn lớp của sheet LỚP (mọi lớp có nhãn đó, staff.class_tags); trống: None."""
    tags = class_tags()
    return frozenset(c for name in written for c in tags.get(_fold(name), (name,))) or None


def compiled() -> list[Luat]:
    return [make(r) for r in config.CUSTOM_RULES]


def weight(L: Luat, w: config.Weights) -> int:
    """Điểm trừ mỗi lần không theo luật ưu tiên: cột Điểm, không ghi thì theo Mức."""
    return L.rule.points if L.rule.points is not None else w.custom_levels[L.rule.level - 1]


def _when_ok(L: Luat, curriculum: dict[int, dict[str, int]], grade: int, subject: str | None = None) -> bool:
    """Cột Áp dụng khi: điều kiện trên số tiết/tuần của các môn của luật ở khối này; phạm vi có Môn (Nhóm môn) thì
    chỉ tính môn (nhóm môn) của tiết đang xét."""
    if not L.when:
        return True
    from .allocation import subject_group
    req = curriculum.get(grade, {})
    same = (lambda s: s == subject) if subject is not None and "mon" in L.scope else \
        (lambda s: subject_group(s) == subject_group(subject)) if subject is not None and "nhom_mon" in L.scope else \
        (lambda s: True)
    n = sum(k for s, k in req.items() if (L.subjects is None or s in L.subjects) and s not in L.skip and same(s))
    days = len(config.DAY_SESSIONS)
    for op, value in L.when:
        value = days if value == NUMBER_DAYS else value
        if not {"<=": n <= value, ">=": n >= value, "=": n == value, "chan": n % 2 == 0,
                "le": n % 2 == 1}[op]:
            return False
    return True


def _class_ok(L: Luat, cls: str, grade: int, curriculum) -> bool:
    return ((L.grades is None or grade in L.grades) and (L.classes is None or cls in L.classes)
            and _when_ok(L, curriculum, grade))


_ALL = object()  # mọi môn của luật (L.subjects)


def _lesson_ok(L: Luat, cls: str, grade: int, subject: str, curriculum, subjects=_ALL, skip=None) -> bool:
    subjects, skip = (L.subjects, L.skip) if subjects is _ALL else (subjects, skip or frozenset())
    return ((subjects is None or subject in subjects) and subject not in skip
            and (L.grades is None or grade in L.grades) and (L.classes is None or cls in L.classes)
            and _when_ok(L, curriculum, grade, subject))


# --------------------------------------------------------------------------
# Tiết (nguyên tử): một biến "course có tiết ở ô" (hoặc "GV dạy tiết đó") khi dựng mô hình, 0/1 khi đánh giá
# --------------------------------------------------------------------------
@dataclass
class Atom:
    lit: object
    cls: str | None = None
    grade: int = 0
    subject: str = ""
    day: int = -1
    period: int = 0
    session: str = ""
    teacher: str | None = None
    cells: tuple = ()  # (lớp, ngày) liên quan, cho số hạng dẫn xuất

    def where(self) -> list[tuple[str, int]]:
        if self.cls is not None:
            return [(self.cls, self.day)] if self.lit else []
        return list(self.cells)


def _key(dim: str, a: Atom, problem):
    from .allocation import subject_group
    return {"lop": lambda: a.cls, "gv": lambda: a.teacher, "mon": lambda: a.subject,
            "nhom_mon": lambda: subject_group(a.subject), "khoi": lambda: a.grade, "ngay": lambda: a.day,
            "buoi": lambda: (a.day, a.session), "o": lambda: (a.day, a.period),
            "co_so": lambda: a.cls in problem.campus2}[dim]()


class _Source:
    """Các tiết có thể có (mỗi course × ô trong miền × GV): từ biến của mô hình, hoặc từ một TKB."""

    def __init__(self, problem, dom: dict[int, list], lit, teachers_of, extra=(), relabel=None):
        from .solver import session_of
        self.problem, self.dom, self.lit, self.teachers_of, self.extra = problem, dom, lit, teachers_of, extra
        self.relabel = relabel or {}  # (course, GV trong mô hình) -> GV tính cho luật (người bù, Problem.covers)
        self.sess = session_of()

    def atoms(self, L: Luat, subjects=_ALL, skip=None) -> list[Atom]:
        """Các tiết của luật; subjects/skip: thay bộ lọc môn của luật (Môn thứ hai)."""
        p, out = self.problem, []
        need_teacher = L.teacher()
        ok = {g: (L.roles is None or picks(L.roles, t)) and not picks(L.roles_not, t)
              for g, t in p.teachers.items()} if need_teacher else {}
        for c in p.courses:
            if not _lesson_ok(L, c.class_name, c.grade, c.subject, p.curriculum, subjects, skip):
                continue
            slots = list(self.dom.get(c.id, ())) + [s for cid, s in self.extra if cid == c.id]
            for s in slots:
                if L.slots is not None and s not in L.slots:
                    continue
                name = self.sess[s].name if s in self.sess else ""
                if not need_teacher:
                    out.append(Atom(self.lit(c.id, None, s), c.class_name, c.grade, c.subject, s[0], s[1], name))
                    continue
                for g in self.teachers_of(c.id):
                    t = self.relabel.get((c.id, g), g)
                    if not ok[t]:
                        continue
                    out.append(Atom(self.lit(c.id, g, s), c.class_name, c.grade, c.subject, s[0], s[1], name, t))
        return out


def _cp_source(problem, x, z, dom, teachers_of, relabel=None) -> _Source:
    def lit(cid, g, s):
        if g is None or len(teachers_of[cid]) == 1:
            return x[cid, s]
        return z[cid, g, s]
    return _Source(problem, dom, lit, lambda cid: teachers_of[cid], relabel=relabel)


def _domains(problem) -> dict[int, list]:
    from .solver import SolveError, allowed_slots
    out = {}
    for c in problem.courses:
        try:
            out[c.id] = allowed_slots(c, problem)
        except SolveError:
            out[c.id] = list(problem.slots)
    return out


def _eval_source(problem, lessons, dom=None) -> _Source:
    dom = _domains(problem) if dom is None else dom
    placed = {(les.course_id, (les.day, les.period)) for les in lessons}
    taught = {(les.course_id, (les.day, les.period), les.teacher) for les in lessons}
    by_course: dict[int, list[str]] = defaultdict(list)
    for les in lessons:
        if les.teacher not in by_course[les.course_id]:
            by_course[les.course_id].append(les.teacher)
    extra = sorted({(cid, s) for cid, s in placed if s not in set(dom.get(cid, ()))})

    def lit(cid, g, s):
        return int((cid, s) in placed) if g is None else int((cid, s, g) in taught)
    return _Source(problem, dom, lit, lambda cid: sorted(by_course.get(cid, ())), extra)


def _groups(L: Luat, atoms: list[Atom], problem, all_keys: bool) -> list[tuple[tuple, list[Atom]]]:
    """Chia các tiết theo phạm vi. all_keys: có cả nhóm không có tiết nào (cho so sánh Tối thiểu, Đúng)."""
    groups: dict[tuple, list[Atom]] = {}
    if all_keys:
        for key in _universe(L, problem):
            groups[key] = []
    for a in atoms:
        groups.setdefault(tuple(_key(d, a, problem) for d in L.scope), []).append(a)
    return sorted(groups.items(), key=lambda kv: repr(kv[0]))


def _universe(L: Luat, problem) -> list[tuple]:
    """Mọi nhóm của phạm vi (chiều GV, môn, nhóm môn, cơ sở: chỉ các giá trị có tiết)."""
    from .solver import session_of
    classes = [c for c in problem.classes if _class_ok(L, c, grade_of(c), problem.curriculum)
               and (L.subjects is None or any(problem.curriculum[grade_of(c)].get(s, 0) for s in L.subjects))]
    slots = sorted(s for s in _all_slots() if L.slots is None or s in L.slots)
    sess = session_of()
    values = {"lop": classes, "khoi": sorted({grade_of(c) for c in classes}, key=grade_key), "ngay": sorted({d for d, _ in slots}),
              "buoi": sorted({(d, sess[(d, p)].name) for d, p in slots}), "o": slots}
    if any(d not in values for d in L.scope):
        return []
    return list(itertools.product(*(values[d] for d in L.scope)))


def _periods(a: Atom) -> tuple[int, ...]:
    from .solver import session_of
    return session_of()[(a.day, a.period)].periods


# --------------------------------------------------------------------------
# Ngữ cảnh: dựng ràng buộc CP-SAT, hoặc đếm số lần không theo trên một TKB
# --------------------------------------------------------------------------
def _const(v) -> bool:
    return isinstance(v, int)


class _Cp:
    """Bắt buộc: ràng buộc; ưu tiên: biến phần vượt × điểm vào mục tiêu."""

    def __init__(self, m, w: config.Weights):
        self.m, self.w = m, w
        self.objective: list = []
        self.i = 0

    def use(self, L: Luat, i: int) -> None:
        self.L, self.i, self.hard, self.weight = L, i, L.hard, weight(L, self.w)

    def _false(self) -> None:
        self.m.AddBoolOr([])

    def at_most(self, pos: list[Atom], n: int, neg: list[Atom] = (), text=None) -> None:
        p, q = [a.lit for a in pos], [a.lit for a in neg]
        if len(p) <= n:
            return
        if all(_const(v) for v in p + q):
            if sum(p) - sum(q) > n and self.hard:
                self._false()
            return
        if self.hard:
            self.m.Add(sum(p) - sum(q) <= n)
        elif n == 0 and not q:
            self.objective += [self.weight * v for v in p]
        else:
            over = self.m.NewIntVar(0, len(p), f"luat{self.i}_vuot")
            self.m.Add(over >= sum(p) - sum(q) - n)
            self.objective.append(self.weight * over)

    def at_least(self, pos: list[Atom], n: int, text=None) -> None:
        p = [a.lit for a in pos]
        if n <= 0:
            return
        if all(_const(v) for v in p):
            if sum(p) < n and self.hard:
                self._false()
            return
        if self.hard:
            self.m.Add(sum(p) >= n)
        else:
            short = self.m.NewIntVar(0, n, f"luat{self.i}_thieu")
            self.m.Add(short >= n - sum(p))
            self.objective.append(self.weight * short)

    def pairs(self, pos: list[Atom], text=None) -> None:
        """Bắt buộc: tổng 0 hoặc 2."""
        p = [a.lit for a in pos if not _const(a.lit)]
        if p:
            b = self.m.NewBoolVar(f"luat{self.i}_cap")
            self.m.Add(sum(p) == 2 * b)

    def any(self, atoms: list[Atom]) -> Atom:
        lits = [a.lit for a in atoms if not _const(a.lit)]
        if any(_const(a.lit) and a.lit for a in atoms):
            return Atom(1)
        if not lits:
            return Atom(0)
        if len(lits) == 1:
            return Atom(lits[0])
        b = self.m.NewBoolVar(f"luat{self.i}_co")
        for v in lits:
            self.m.AddImplication(v, b)
        self.m.Add(b <= sum(lits))
        return Atom(b)

    def excess(self, pos: list[Atom], n: int, neg: list[Atom] = ()) -> Atom:
        """Số hạng ≥ max(0, tổng pos - tổng neg - n) (đủ cho ràng buộc tối đa và cho mục tiêu cực tiểu)."""
        p, q = [a.lit for a in pos], [a.lit for a in neg]
        if all(_const(v) for v in p + q):
            return Atom(max(0, sum(p) - sum(q) - n))
        v = self.m.NewIntVar(0, len(p), f"luat{self.i}_du")
        self.m.Add(v >= sum(p) - sum(q) - n)
        return Atom(v)


class _Eval:
    """Đếm số lần không theo: (luật, số lần, các (lớp, ngày) liên quan, mô tả)."""

    def __init__(self):
        self.found: list[tuple[Luat, int, list[tuple[str, int]], str]] = []

    def use(self, L: Luat, i: int) -> None:
        self.L = L

    def _add(self, n: int, atoms, text, value) -> None:
        cells = sorted({c for a in atoms for c in a.where()})
        self.found.append((self.L, n, cells, text(value) if text else ""))

    def at_most(self, pos, n, neg=(), text=None) -> None:
        value = sum(a.lit for a in pos) - sum(a.lit for a in neg)
        if value > n:
            self._add(value - n, pos, text, value)

    def at_least(self, pos, n, text=None) -> None:
        value = sum(a.lit for a in pos)
        if value < n:
            self._add(n - value, pos, text, value)

    def pairs(self, pos, text=None) -> None:
        value = sum(a.lit for a in pos)
        if value not in (0, 2):
            self._add(1, pos, text, value)

    def any(self, atoms) -> Atom:
        on = [a for a in atoms if a.lit]
        return Atom(int(bool(on)), cells=tuple(c for a in on for c in a.where()))

    def excess(self, pos, n, neg=()) -> Atom:
        value = sum(a.lit for a in pos) - sum(a.lit for a in neg) - n
        return Atom(max(0, value), cells=tuple(c for a in pos for c in a.where()))


# --------------------------------------------------------------------------
# Phép đo: mỗi phép đo một hàm, dùng cho cả dựng mô hình và đánh giá
# --------------------------------------------------------------------------
def _day(d: int) -> str:
    from .khung_gio import day_name
    return day_name(d)


def _label(problem, subject: str) -> str:
    return problem.subject_labels.get(subject, subject)


def _where(L: Luat, key: tuple, problem) -> str:
    parts = []
    for d, v in zip(L.scope, key):
        parts.append({"lop": lambda: f"lớp {v}", "gv": lambda: problem.teachers[v].code if v in problem.teachers else v,
                      "mon": lambda: _label(problem, v), "nhom_mon": lambda: f"nhóm {_label(problem, v)}",
                      "khoi": lambda: f"khối {v}", "ngay": lambda: _day(v),
                      "buoi": lambda: f"{_day(v[0])} buổi {v[1].lower()}",
                      "o": lambda: f"{_day(v[0])} tiết {v[1]}",
                      "co_so": lambda: "cơ sở 2" if v else "cơ sở 1"}[d]())
    return " ".join(parts) or "cả trường"


def _by_period(atoms: list[Atom]) -> dict[int, list[Atom]]:
    out: dict[int, list[Atom]] = defaultdict(list)
    for a in atoms:
        out[a.period].append(a)
    return out


def threshold(L: Luat, key: tuple, problem) -> int:
    """Ngưỡng của một nhóm: cột Số, hoặc ngưỡng theo dữ liệu (DERIVED) tính cho nhóm đó."""
    if not L.derived:
        return L.number
    at = dict(zip(L.scope, key))
    if L.derived in ("tai_ngay", "tai_ngay_1"):  # tải ngày mong muốn của GV (solver.day_targets)
        from .solver import day_targets
        t = problem.teachers[at["gv"]]
        return day_targets(t.max_lessons, problem.slots)[at["ngay"]] + (L.derived == "tai_ngay_1")
    # tran_ngay: số tiết/tuần của môn ở lớp chia số ngày học, làm tròn lên
    req = problem.curriculum[grade_of(at["lop"])]
    return -(-req.get(at["mon"], 0) // len(config.DAY_SESSIONS))


def _limit_text(L: Luat, n: int) -> str:
    return f"{OPS[L.op].lower()} {n}" + (f" = {DERIVED[L.derived]}" if L.derived else "")


def _so_tiet(ctx, L, problem, src):
    atoms = src.atoms(L)
    for key, group in _groups(L, atoms, problem, all_keys=L.op in (">=", "=")):
        n = threshold(L, key, problem)
        text = (lambda v, key=key, n=n: f"{_where(L, key, problem)}: {v} tiết ({_limit_text(L, n)})")
        if L.op in ("<=", "="):
            ctx.at_most(group, n, text=text)
        if L.op in (">=", "="):
            ctx.at_least(group, n, text=text)


def _so_khac(ctx, L, problem, src):
    unit = SCOPE[L.count_by].unit
    for key, group in _groups(L, src.atoms(L), problem, all_keys=L.op in (">=", "=")):
        by: dict = defaultdict(list)
        for a in group:
            by[_key(L.count_by, a, problem)].append(a)
        terms = [ctx.any(by[v]) for v in sorted(by, key=repr)]
        text = (lambda v, key=key: f"{_where(L, key, problem)}: {v} {unit} khác nhau ({OPS[L.op].lower()} "
                                   f"{L.number})")
        if L.op in ("<=", "="):
            ctx.at_most(terms, L.number, text=text)
        if L.op in (">=", "="):
            ctx.at_least(terms, L.number, text=text)


def bad_slots(L: Luat) -> set[tuple[int, int]]:
    """Phép đo Vị trí: các ô mà tiết của luật không được (bắt buộc) / không nên (ưu tiên) nằm."""
    return set(L.place) if L.op == "ngoai" else _all_slots() - set(L.place)


def _vi_tri(ctx, L, problem, src):
    bad = bad_slots(L)
    for a in src.atoms(L):
        if (a.day, a.period) in bad:
            who = f"{problem.teachers[a.teacher].code} dạy " if a.teacher is not None and L.roles is not None else ""
            ctx.at_most([a], 0, text=lambda v, a=a, who=who: f"{who}lớp {a.cls} có {_label(problem, a.subject)} "
                                                             f"{_day(a.day)} tiết {a.period}")


def _lien(ctx, L, problem, src):
    for key, group in _groups(L, src.atoms(L), problem, all_keys=False):
        y = _by_period(group)
        ps = _periods(group[0])
        for i in range(len(ps)):
            for k in range(i + 2, len(ps)):
                if not y.get(ps[i]) or not y.get(ps[k]):
                    continue
                for j in range(i + 1, k):
                    ctx.at_most(y[ps[i]] + y[ps[k]], 1, neg=y.get(ps[j], []),
                                text=lambda v, key=key, a=ps[i], b=ps[k], c=ps[j]:
                                f"{_where(L, key, problem)}: tiết {a} và tiết {b} không liền (tiết {c} xen giữa)")


def forced(L: Luat) -> bool:
    """Luật theo cặp bắt buộc của các nhóm môn cả lớp: xếp như nhóm ghép cặp có sẵn (allocation.paired_groups)."""
    return (L.measure == "cap" and L.hard and L.scope == ("lop", "buoi") and L.subjects is not None
            and L.classes is None and L.slots is None and L.roles is None)


def _cap(ctx, L, problem, src):
    from .allocation import paired_groups, subject_group
    for key, group in _groups(L, src.atoms(L), problem, all_keys=False):
        y = _by_period(group)
        ps = _periods(group[0])
        if L.hard:
            ctx.pairs(group, text=lambda v, key=key: f"{_where(L, key, problem)}: {v} tiết (phải 0 hoặc 2)")
            for i in range(len(ps)):
                for k in range(i + 2, len(ps)):
                    if y.get(ps[i]) and y.get(ps[k]):
                        ctx.at_most(y[ps[i]] + y[ps[k]], 1, text=lambda v, key=key, a=ps[i], b=ps[k]:
                                    f"{_where(L, key, problem)}: tiết {a} và tiết {b} không liền")
            continue
        if "lop" in L.scope and L.subjects is not None:
            cls = key[L.scope.index("lop")]
            pairs = paired_groups(problem.curriculum[grade_of(cls)], grade_of(cls))
            if {subject_group(s) for s in L.subjects} <= pairs:
                continue  # đã bắt buộc ghép cặp
        for k, p in enumerate(ps):
            if not y.get(p):
                continue
            near = [a for q in (ps[k - 1] if k else None, ps[k + 1] if k + 1 < len(ps) else None)
                    if q is not None for a in y.get(q, [])]
            ctx.at_most(y[p], 0, neg=near, text=lambda v, key=key, p=p: f"{_where(L, key, problem)}: tiết {p} lẻ")


def _second(L: Luat, src) -> list[Atom]:
    """Các tiết Môn thứ hai; để trống thì là các môn khác của nhóm (phạm vi có Nhóm môn): mọi môn trừ các môn của
    cột Môn, Nhãn."""
    if L.other is not None:
        return src.atoms(L, subjects=L.other)
    return src.atoms(L, subjects=None, skip=(L.subjects or frozenset()) | L.skip)


def _other_names(problem, L: Luat) -> str:
    return _names(problem, L.other) if L.other is not None else "môn khác cùng nhóm"


def _thu_tu(ctx, L, problem, src):
    first, second = src.atoms(L), _second(L, src)
    if L.op == "sau":  # các tiết cột Môn đứng sau: các tiết Môn thứ hai đứng trước
        first, second = second, first
    groups = dict(_groups(L, first, problem, False))
    others = dict(_groups(L, second, problem, False))
    for key in sorted(set(groups) & set(others), key=repr):
        a_at, b_at = _by_period(groups[key]), _by_period(others[key])
        for pb in sorted(b_at):
            for pa in sorted(a_at):
                if pb < pa:
                    ctx.at_most(b_at[pb] + a_at[pa], 1, text=lambda v, key=key, pa=pa, pb=pb:
                                f"{_where(L, key, problem)}: tiết {pb} đứng trước tiết {pa} (sai thứ tự "
                                f"{_names(problem, L.subjects)} {OPS[L.op].lower()} {_other_names(problem, L)})")


def _names(problem, subjects) -> str:
    return ", ".join(_label(problem, s) for s in sorted(subjects or ())) or "mọi môn"


def _di_kem(ctx, L, problem, src):
    groups = _groups(L, src.atoms(L), problem, False)
    others = dict(_groups(L, _second(L, src), problem, False))
    for key, group in groups:
        for a in group:
            ctx.at_most([a], 0, neg=others.get(key, []),
                        text=lambda v, key=key: f"{_where(L, key, problem)}: có {_names(problem, L.subjects)} mà "
                                                f"không có {_other_names(problem, L)}")


def teacher_ok(L: Luat, t, class_name: str) -> bool:
    """Phép đo Người dạy "Do": GV t được dạy tiết của lớp class_name: t có tên (Mã GV, họ tên) ở cột Giáo viên, hoặc
    có chức vụ ở đó (chủ nhiệm: GVCN của chính lớp đó; cả chức vụ ở cột Chức Vụ Thêm), hoặc có nhãn ở đó."""
    if not L.who.isdisjoint(person_keys(t)) or not L.who.isdisjoint(t.extra_roles) or not L.who.isdisjoint(t.tag_keys):
        return True
    if t.role == config.ROLE_HOMEROOM:
        return config.ROLE_HOMEROOM in L.who and t.class_name == class_name
    return t.role in L.who


def _nguoi_day(ctx, L, problem, src):
    atoms = src.atoms(L)
    if L.op == "do":
        for a in atoms:
            t = problem.teachers[a.teacher]
            if not teacher_ok(L, t, a.cls):
                ctx.at_most([a], 0, text=lambda v, a=a, t=t: f"{t.code} dạy {_label(problem, a.subject)} lớp {a.cls} "
                                                             f"{_day(a.day)} tiết {a.period}")
        return
    for key, group in _groups(L, atoms, problem, False):
        by: dict = defaultdict(list)
        for a in group:
            by[a.teacher].append(a)
        if len(by) < 2:
            continue
        if L.op == "cung_nguoi":
            ctx.at_most([ctx.any(by[g]) for g in sorted(by)], 1,
                        text=lambda v, key=key: f"{_where(L, key, problem)}: {v} người dạy")
        elif L.op == "lien_cung_nguoi":  # hai tiết liền nhau trong buổi do cùng một người
            at = {g: _by_period(items) for g, items in by.items()}
            ps = _periods(group[0])
            for p1, p2 in zip(ps, ps[1:]):
                for g1 in sorted(by):
                    for g2 in sorted(by):
                        if g1 != g2 and at[g1].get(p1) and at[g2].get(p2):
                            ctx.at_most(at[g1][p1] + at[g2][p2], 1, text=lambda v, key=key, p1=p1:
                                        f"{_where(L, key, problem)}: tiết {p1} và tiết {p1 + 1} khác người dạy")
        else:  # dau_tuan: tiết đầu tuần do người có chức vụ ở cột Giáo viên, người khác không dạy trước tiết đó
            first = [g for g in sorted(by) if teacher_ok(L, problem.teachers[g], group[0].cls)]
            if not first:
                continue
            mine = [a for g in first for a in by[g]]
            for g in sorted(by):
                if g in first:
                    continue
                for a in sorted(by[g], key=lambda a: (a.day, a.period)):
                    before = [b for b in mine if (b.day, b.period) < (a.day, a.period)]
                    ctx.at_most([a], 0, neg=before, text=lambda v, key=key, a=a:
                                f"{_where(L, key, problem)}: {problem.teachers[a.teacher].code} dạy "
                                f"{_day(a.day)} tiết {a.period} trước tiết đầu tuần của "
                                f"{', '.join(problem.teachers[g].code for g in first)}")


def _khoang_cach(ctx, L, problem, src):
    atoms = src.atoms(L)
    if L.op == "cuoi_buoi":
        for a in atoms:
            far = _periods(a)[-1] - a.period - L.number
            if far > 0:
                ctx.at_most([a] * far, 0, text=lambda v, a=a, far=far: f"lớp {a.cls} {_day(a.day)} tiết {a.period}: "
                                                                       f"cách cuối buổi {far + L.number} tiết")
        return
    for key, group in _groups(L, atoms, problem, False):
        y = _by_period(group)
        ps = _periods(group[0])
        if len(ps) < 3:
            continue
        o = [ctx.any(y.get(p, [])) for p in ps]
        started, later = [o[0]], [None] * len(ps)
        for i in range(1, len(ps)):
            started.append(ctx.any([started[-1], o[i]]))
        later[-1] = o[-1]
        for i in range(len(ps) - 2, -1, -1):
            later[i] = ctx.any([later[i + 1], o[i]])
        holes = [ctx.excess([started[i - 1], later[i + 1]], 1, neg=[o[i]]) for i in range(1, len(ps) - 1)]
        ctx.at_most(holes, L.number, text=lambda v, key=key: f"{_where(L, key, problem)}: {v} tiết trống (tối đa "
                                                             f"{L.number})")


LOWER = {"so_tiet": _so_tiet, "so_khac": _so_khac, "vi_tri": _vi_tri, "lien": _lien, "cap": _cap,
         "thu_tu": _thu_tu, "di_kem": _di_kem, "nguoi_day": _nguoi_day, "khoang_cach": _khoang_cach}


# --------------------------------------------------------------------------
# Dùng khi xếp (đọc config hiện tại, gọi trong rules.applied)
# --------------------------------------------------------------------------
def _ban(L: Luat) -> set[tuple[int, int]] | None:
    """Ô bị cắt khỏi miền bởi luật bắt buộc chỉ xét môn, khối, lớp và ô (không xét GV); None nếu không phải."""
    if not L.hard or L.roles is not None:
        return None
    if L.measure == "vi_tri":
        return bad_slots(L)
    if L.measure == "so_tiet" and L.op in ("<=", "=") and L.number == 0:
        return set(L.slots) if L.slots is not None else _all_slots()
    return None


def banned(subject: str, grade: int, class_name: str | None = None, curriculum=None) -> set[tuple[int, int]]:
    """Ô mà môn của khối (lớp) không được học theo các luật bắt buộc (dùng trong solver.allowed_slots)."""
    out = set()
    for L in compiled():
        bad = _ban(L)
        if bad is None or (L.subjects is not None and subject not in L.subjects):
            continue
        if (L.grades is not None and grade not in L.grades) or \
                (L.classes is not None and class_name is not None and class_name not in L.classes):
            continue
        if L.when and curriculum is not None and not _when_ok(L, curriculum, grade):
            continue
        out |= bad
    return out


def forced_pairs(grade: int, totals: dict[str, int]) -> set[str]:
    """Nhóm môn của khối phải học thành cặp 2 tiết liền theo luật bắt buộc (số tiết chẵn; lẻ thì precheck báo)."""
    from .allocation import subject_group
    out = set()
    for L in compiled():
        if not forced(L) or (L.grades is not None and grade not in L.grades):
            continue
        for s in sorted(L.subjects):
            group = subject_group(s)
            if totals.get(group, 0) > 0 and totals[group] % 2 == 0:
                out.add(group)
    return out


def day_cap(teacher) -> int | None:
    """Số tiết tối đa mỗi ngày của GV theo luật bắt buộc "mỗi GV mỗi ngày tối đa n tiết" (mọi môn, mọi ô); dùng
    trong phan_cong.teacher_slots. None: không giới hạn."""
    caps = [L.number for L in compiled()
            if L.hard and L.measure == "so_tiet" and L.op in ("<=", "=") and L.scope == ("gv", "ngay")
            and L.subjects is None and L.grades is None and L.classes is None and L.slots is None
            and (L.roles is None or picks(L.roles, teacher)) and not picks(L.roles_not, teacher)]
    return min(caps) if caps else None


def busy(teacher) -> set[tuple[int, int]]:
    """Giờ bận của GV: các ô luật bắt buộc Vị trí chỉ xét người dạy (mọi môn, mọi lớp) không cho GV dạy, vd "Bộ Môn 3
    không dạy Thứ 2 tiết 1"; dùng trong phan_cong.teacher_slots."""
    out: set[tuple[int, int]] = set()
    for L in compiled():
        if L.hard and L.measure == "vi_tri" and L.roles is not None and L.subjects is None and not L.skip \
                and L.grades is None and L.classes is None and not L.when \
                and picks(L.roles, teacher) and not picks(L.roles_not, teacher):
            out |= bad_slots(L)
    return out


def _who_rules(hard: bool) -> list[Luat]:
    return [L for L in compiled() if L.hard == hard and L.measure == "nguoi_day" and L.op == "do"
            and L.slots is None]


def refusing(t, class_name: str, grade: int, subject: str, curriculum) -> list[Luat]:
    """Tầng phân công: các luật bắt buộc "Người dạy: Do" không xét ô không cho GV t nhận tiết môn này của lớp."""
    return [L for L in _who_rules(True)
            if _lesson_ok(L, class_name, grade, subject, curriculum) and not teacher_ok(L, t, class_name)]


def allowed(t, class_name: str, grade: int, subject: str, curriculum) -> bool:
    """Tầng phân công: GV t được nhận tiết môn này của lớp theo các luật bắt buộc "Người dạy: Do" không xét ô."""
    return not refusing(t, class_name, grade, subject, curriculum)


def assign_cost(t, course, curriculum, w: config.Weights) -> int:
    """Tầng phân công: giá mỗi tiết GV t dạy course khi trái luật ưu tiên "Người dạy: Do" không xét ô."""
    return sum(weight(L, w) for L in _who_rules(False)
               if _lesson_ok(L, course.class_name, course.grade, course.subject, curriculum)
               and not teacher_ok(L, t, course.class_name))


def build(m, problem, x: dict, z: dict, dom: dict, teachers_of: dict, w: config.Weights) -> list:
    """Ràng buộc và mục tiêu của các luật trong mô hình CP-SAT (solver.build_timetable); trả về các số hạng mục tiêu.
    Luật đã nằm trong miền ô (`banned`) hay trong nhóm ghép cặp (`forced_pairs`) không thêm gì."""
    rules = compiled()
    if not rules:
        return []
    ctx, src = _Cp(m, w), _cp_source(problem, x, z, dom, teachers_of)
    # Tiết bù do người mới dạy (Problem.covers) ở chế độ bù giờ là tiết của người bù, cùng ô: luật bắt buộc theo GV
    # phải đúng cả khi tính các tiết đó cho người bù.
    covered = _cp_source(problem, x, z, dom, teachers_of, relabel=problem.covers) if problem.covers else None
    for i, L in enumerate(rules):
        if forced(L) or (_ban(L) is not None and L.measure == "vi_tri"):
            continue
        ctx.use(L, i)
        LOWER[L.measure](ctx, L, problem, src)
        if covered is not None and L.hard and L.teacher() and L.measure != "nguoi_day":
            LOWER[L.measure](ctx, L, problem, covered)
    return ctx.objective


def violations(problem, lessons, hard: bool | None = None, dom=None, rules: list[CustomRule] | None = None,
               skip_forced: bool = True) -> list[tuple[Luat, int, list, str]]:
    """Các lần không theo luật (mặc định: config.CUSTOM_RULES) của một TKB: (luật, số lần, các (lớp, ngày) liên
    quan, mô tả). Luật theo cặp bắt buộc của cả lớp do checker kiểm như các nhóm ghép cặp khác (skip_forced)."""
    luats = [make(r) for r in (config.CUSTOM_RULES if rules is None else rules)]
    luats = [L for L in luats if hard is None or L.hard == hard]
    if not luats:
        return []
    ctx, src = _Eval(), _eval_source(problem, lessons, dom)
    for i, L in enumerate(luats):
        if skip_forced and forced(L):
            continue
        ctx.use(L, i)
        LOWER[L.measure](ctx, L, problem, src)
    return ctx.found


def qa(problem, lessons, w: config.Weights) -> Counter:
    """Chi phí của các luật ưu tiên theo (lớp, ngày), như mục tiêu trong `build` (lns._Search.qa)."""
    cost: Counter = Counter()
    for L, n, cells, _ in violations(problem, lessons, hard=False):
        for key in cells:
            cost[key] += weight(L, w) * n / len(cells)
    return cost


def soft_counts(problem, lessons) -> Counter:
    """Luật ưu tiên -> số lần không theo."""
    count: Counter = Counter()
    for L, n, _, _ in violations(problem, lessons, hard=False):
        count[L.rule] += n
    return count


# --------------------------------------------------------------------------
# Đếm trước khi xếp
# --------------------------------------------------------------------------
def precheck(problem, label, skip: set[int] = frozenset()) -> list[str]:
    """Mâu thuẫn chắc chắn của luật bắt buộc, tìm bằng phép đếm; label(luật) là tên luật khi báo; bỏ qua các luật ở
    dòng `skip` (ghi sai)."""
    from .allocation import subject_group
    out = []
    n_slots = len(_all_slots())
    for L in compiled():
        if not L.hard or L.rule.row in skip:
            continue
        r = L.rule
        classes = [c for c in problem.classes if _class_ok(L, c, grade_of(c), problem.curriculum)]
        grades = sorted({grade_of(c) for c in classes}, key=grade_key)
        subjects = sorted(L.subjects or ())
        if _ban(L) is not None:
            for g in grades:
                for s in subjects:
                    n = problem.curriculum[g].get(s, 0)
                    free = n_slots - len(banned(s, g, curriculum=problem.curriculum))
                    if n > free:
                        out.append(f"{label(r)}: khối {g} có {n} tiết {_label(problem, s)} nhưng các luật vị trí "
                                   f"bắt buộc chỉ để lại {free} tiết trong tuần")
        elif L.measure == "cap" and "lop" in L.scope and L.subjects is not None:
            groups = {subject_group(s) for s in L.subjects}
            for g in grades:
                n = sum(k for s, k in problem.curriculum[g].items() if subject_group(s) in groups)
                if n % 2:
                    out.append(f"{label(r)}: khối {g} có {n} tiết/tuần (lẻ) nên không chia hết thành cặp 2 tiết")
        elif L.measure == "so_tiet" and L.scope == ("o",) and L.op in ("<=", "=") and L.slots is None and subjects:
            total = sum(problem.curriculum[grade_of(c)].get(s, 0) for c in classes for s in subjects)
            free = max((n_slots - len(banned(s, g, curriculum=problem.curriculum)) for g in grades for s in subjects),
                       default=n_slots)
            if total > L.number * free:
                out.append(f"{label(r)}: các lớp có tổng {total} tiết {_names(problem, L.subjects)} nhưng tối đa "
                           f"{L.number} lớp × {free} tiết = {L.number * free}")
        if L.measure in ("so_tiet", "so_khac") and L.op in (">=", "=") and L.number > 0:
            out += _precheck_at_least(L, problem, label)
    return out


def _precheck_at_least(L: Luat, problem, label) -> list[str]:
    """So sánh Tối thiểu, Đúng: nhóm không đủ tiết có thể có (vd ô cố định mà môn không được xếp vào ô đó), hoặc
    luật cần nhiều tiết hơn chương trình học của lớp."""
    out, seen = [], set()
    src = _eval_source(problem, [])
    groups = _groups(L, src.atoms(L), problem, all_keys=True)
    need: Counter = Counter()
    for key, group in groups:
        if L.measure == "so_tiet":
            possible = len(group)
        else:
            possible = len({_key(L.count_by, a, problem) for a in group})
        if "lop" in L.scope and L.measure == "so_tiet":
            need[key[L.scope.index("lop")]] += L.number
        if possible < L.number:
            text = f"{label(L.rule)}: {_where(L, key, problem)} chỉ có thể có {possible}, cần {L.number}"
            grade = key[L.scope.index("lop")] if "lop" in L.scope else key
            if (grade, possible) not in seen and len(out) < 10:
                seen.add((grade, possible))
                out.append(text)
    if L.measure == "so_tiet" and set(L.scope) - {"lop"} <= set(TIME_DIMS) and "lop" in L.scope and L.subjects:
        for cls in sorted(need, key=repr):
            have = sum(problem.curriculum[grade_of(cls)].get(s, 0) for s in L.subjects)
            if need[cls] > have:
                out.append(f"{label(L.rule)}: lớp {cls} cần ít nhất {need[cls]} tiết "
                           f"{_names(problem, L.subjects)} nhưng chương trình chỉ có {have}")
                break
    return out


def validate(problem, sheet: str, role_label) -> list[str]:
    """Lỗi ghi chỉ thấy khi có chương trình học và nhân sự: môn, lớp (hay nhãn lớp) không có; tên ở cột Giáo viên không
    phải chức vụ, nhãn, Mã GV hay họ tên của ai, hoặc là họ tên của nhiều người."""
    subjects = {s for req in problem.curriculum.values() for s, n in req.items() if n > 0}
    roles = {r for t in problem.teachers.values() for r in (t.role, *t.extra_roles, *t.tag_keys)}
    found = Counter(k for t in problem.teachers.values() for k in person_keys(t))
    out = []
    for r in config.CUSTOM_RULES:
        for name in [*names(r.subject), *names(r.other)]:
            if _subject(name) not in subjects:
                out.append(f"{sheet} dòng {r.row}: môn '{name}' không có trong chương trình học (hoặc không có tiết "
                           f"nào)")
        keep, drop = role_names(r.role)
        for role in [*keep, *drop]:
            if found[role] > 1 and role not in roles:
                out.append(f"{sheet} dòng {r.row}: có {found[role]} giáo viên tên '{role_label(role)}', ghi Mã GV để "
                           f"chỉ rõ người")
            elif not found[role] and role not in roles:
                out.append(f"{sheet} dòng {r.row}: không có giáo viên nào có chức vụ, nhãn, Mã GV hay họ tên "
                           f"'{role_label(role)}'")
        for c in r.classes:
            if c not in problem.classes and _fold(c) not in class_tags():
                out.append(f"{sheet} dòng {r.row}: không có lớp '{c}'" +
                           (f" (cũng không có nhãn lớp nào tên đó ở sheet {config.CLASSES_SHEET})" if config.CLASSES
                            else ""))
        for g in r.grades:
            if isinstance(g, str) and g not in problem.curriculum:
                out.append(f"{sheet} dòng {r.row}: không có khối '{g}' (các khối: "
                           f"{', '.join(map(str, sorted(problem.curriculum, key=grade_key)))})")
    return out
