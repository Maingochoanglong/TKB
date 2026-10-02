"""Luật riêng của trường: sheet LUẬT RIÊNG, mỗi dòng một luật thuộc một trong các kiểu luật chung (KINDS).

Nhà trường tự thêm luật mà không cần sửa mã nguồn: mỗi kiểu luật viết code một lần ở đây, cho bộ xếp
(`banned`, `forced_pairs`, `build`), cho LNS (`qa`), cho kiểm tra độc lập (`check`), cho phép đếm trước khi xếp
(`precheck`), cho phân công (`day_cap`) và cho chẩn đoán (tkb/chan_doan.py nới từng luật bắt buộc).

Mỗi luật là bắt buộc (cột Bắt buộc = Có) hoặc ưu tiên (mức 1–3 ở cột Mức, trọng số `config.Weights.custom_levels`).
Không có luật riêng nào (config.CUSTOM_RULES rỗng) thì mô hình dựng ra y như cũ: mã kết quả không đổi.

Cột của sheet: Kiểu luật | Môn | Môn thứ hai | Khối | Ngày | Tiết | Buổi | Giáo viên | Số | Bắt buộc | Mức (| Ghi chú).
Khối, Ngày, Tiết ghi danh sách cách nhau bằng dấu phẩy hoặc khoảng, vd "3, 4, 5", "3-5", "Thứ 2, Thứ 4", "T2-T4",
"5-7"; Buổi ghi Sáng/Chiều; Giáo viên ghi chức vụ (Chủ Nhiệm, Bộ Môn, Quản Lý hoặc tên môn của GV chuyên biệt).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import config
from .config import CustomRule
from .staff import _NO, _YES, _fold, clean_name, grade_of, normalize, subject_key

SHEET = "LUẬT RIÊNG"
NOTE = "Ghi chú"
# Cột của sheet: (khóa, tiêu đề).
COLUMNS = (("kind", "Kiểu luật"), ("subject", "Môn"), ("other", "Môn thứ hai"), ("grades", "Khối"), ("days", "Ngày"),
           ("periods", "Tiết"), ("sessions", "Buổi"), ("role", "Giáo viên"), ("number", "Số"), ("hard", "Bắt buộc"),
           ("level", "Mức"))
HEADERS = dict(COLUMNS)


@dataclass(frozen=True)
class Kind:
    key: str
    label: str  # chữ ở cột Kiểu luật
    needs: tuple[str, ...]  # cột phải ghi
    uses: tuple[str, ...]  # cột được ghi (ngoài Kiểu luật, Bắt buộc, Mức)
    note: str


_PLACE = ("subject", "grades", "days", "periods", "sessions")
KINDS = (
    Kind("khong_xep", "Không xếp vào", ("subject",), _PLACE,
         "Môn (của các khối ở cột Khối; trống: mọi khối) không học vào các ngày, tiết, buổi ghi ở dòng này (ghi ít "
         "nhất một trong ba cột), vd Thể dục không học tiết 1; Tin học không học Thứ 2."),
    Kind("chi_xep", "Chỉ xếp vào", ("subject",), _PLACE,
         "Môn chỉ học vào các ngày, tiết, buổi ghi ở dòng này (ghi ít nhất một trong ba cột), vd Thể dục chỉ học buổi "
         "chiều."),
    Kind("lien_2", "Học 2 tiết liền", ("subject",), ("subject", "grades"),
         "Môn học thành cặp 2 tiết liền, cùng người dạy: mỗi buổi 0 hoặc 2 tiết của môn (cả môn tăng cường cùng nhóm), "
         "vd Tiếng Anh. Bắt buộc thì số tiết/tuần phải chẵn."),
    Kind("truoc", "Học trước", ("subject", "other"), ("subject", "other", "grades"),
         "Trong một buổi có cả hai môn thì Môn học trước Môn thứ hai, vd Tiếng Việt trước Toán."),
    Kind("gv_ngay", "Giáo viên tối đa tiết mỗi ngày", ("number",), ("role", "number"),
         "Mỗi giáo viên có chức vụ ở cột Giáo viên (trống: mọi giáo viên) dạy tối đa Số tiết mỗi ngày."),
    Kind("cung_luc", "Số lớp học cùng lúc tối đa", ("subject", "number"), ("subject", "grades", "number"),
         "Môn có tối đa Số lớp học cùng một tiết (cả trường, hoặc các khối ở cột Khối), vd phòng Tin học: 1, sân Thể "
         "dục: 2."),
)
BY_KEY = {k.key: k for k in KINDS}
_BY_LABEL = {subject_key(k.label): k for k in KINDS} | {subject_key(k.key): k for k in KINDS}


def _day_label(d: int) -> str:
    return f"Thứ {d + 2}"


def _numbers(text: str) -> list[int] | None:
    """"3, 4, 5", "3-5", "3–5" -> [3, 4, 5]; None nếu có phần không phải số."""
    out = []
    for part in re.split(r"[,;]", text):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:[-–]\s*(\d+))?", part)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out += range(min(a, b), max(a, b) + 1)
    return sorted(set(out))


def _days(text: str) -> list[int] | None:
    """"Thứ 2, Thứ 4", "T2-T4", "2, 3" -> [0, 2] / [0, 1, 2] / [0, 1]."""
    folded = re.sub(r"\b(?:thu|t)\s*(?=\d)", "", _fold(text))
    days = _numbers(folded)
    if days is None or any(not 2 <= d <= 7 for d in days):
        return None
    return [d - 2 for d in days]


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def parse(values: dict, row: int, error) -> CustomRule | None:
    """Một dòng của sheet LUẬT RIÊNG ({khóa cột: ô}) -> CustomRule; lỗi gọi error(chữ). Dòng trống: None."""
    if all(_blank(v) for v in values.values()):
        return None
    raw = {k: (v if not _blank(v) else None) for k, v in values.items()}
    if raw.get("kind") is None:
        error("thiếu Kiểu luật")
        return None
    kind = _BY_LABEL.get(subject_key(raw["kind"]))
    if kind is None:
        error(f"Kiểu luật '{clean_name(raw['kind'])}' không có (các kiểu: {', '.join(k.label for k in KINDS)})")
        return None
    out: dict = {"kind": kind.key, "row": row}
    ok = True
    for key, _ in COLUMNS[1:]:
        value = raw.get(key)
        if value is None:
            if key in kind.needs:
                error(f"kiểu luật {kind.label} phải ghi cột {HEADERS[key]}")
                ok = False
            continue
        if key not in kind.uses and key not in ("hard", "level"):
            error(f"cột {HEADERS[key]} không dùng cho kiểu luật {kind.label} (để trống)")
            ok = False
            continue
        text = clean_name(value) if not isinstance(value, (int, float)) else str(int(value))
        if key in ("subject", "other"):
            out[key] = text
        elif key == "role":
            out[key] = normalize(text)
        elif key == "grades":
            grades = _numbers(text)
            if not grades or 0 in grades:
                error(f"cột Khối ghi số khối, vd '3, 4' hoặc '3-5', đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(grades)
        elif key == "days":
            days = _days(text)
            if not days:
                error(f"cột Ngày ghi Thứ 2 … Thứ 7, vd 'Thứ 2, Thứ 4' hoặc 'T2-T4', đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(days)
        elif key == "periods":
            periods = _numbers(text)
            if not periods or 0 in periods:
                error(f"cột Tiết ghi số tiết, vd '1' hoặc '5-7', đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(periods)
        elif key == "sessions":
            names = {_fold(s.name): s.name for s in (config.MORNING, config.AFTERNOON)}
            parts = [_fold(p) for p in re.split(r"[,;]", text) if p.strip()]
            if not parts or any(p.replace("buoi ", "") not in names for p in parts):
                error(f"cột Buổi ghi {config.MORNING.name} hoặc {config.AFTERNOON.name}, đang ghi {value!r}")
                ok = False
            else:
                out[key] = tuple(sorted({names[p.replace('buoi ', '')] for p in parts}))
        elif key == "number":
            if not text.isdigit() or int(text) < 1:
                error(f"cột Số ghi một số nguyên dương, đang ghi {value!r}")
                ok = False
            else:
                out[key] = int(text)
        elif key == "hard":
            folded = _fold(value) if not isinstance(value, bool) else ("co" if value else "khong")
            if folded not in _YES | _NO:
                error(f"cột Bắt buộc chỉ ghi Có hoặc Không, đang ghi {value!r}")
                ok = False
            out[key] = folded in _YES
        elif key == "level":
            if text not in ("1", "2", "3"):
                error(f"cột Mức ghi 1, 2 hoặc 3 (3 là ưu tiên nhất), đang ghi {value!r}")
                ok = False
            else:
                out[key] = int(text)
    if ok and kind.key in ("khong_xep", "chi_xep") and not any(k in out for k in ("days", "periods", "sessions")):
        error(f"kiểu luật {kind.label} phải ghi ít nhất một trong các cột Ngày, Tiết, Buổi")
        ok = False
    if ok and kind.key == "truoc" and subject_key(out["subject"]) == subject_key(out["other"]):
        error("Môn và Môn thứ hai phải khác nhau")
        ok = False
    return CustomRule(**out) if ok else None


def cells(rule: CustomRule) -> dict:
    """Các ô của luật khi ghi ra sheet LUẬT RIÊNG ({khóa cột: giá trị}), ngược với `parse`."""
    from .rules import NO, YES
    from .staff import SPECIAL_ROLES

    role = config.ROLE_LABELS.get(rule.role) if rule.role in SPECIAL_ROLES else rule.role.title()
    return {"kind": BY_KEY[rule.kind].label, "subject": rule.subject or None, "other": rule.other or None,
            "grades": ", ".join(map(str, rule.grades)) or None,
            "days": ", ".join(_day_label(d) for d in rule.days) or None,
            "periods": ", ".join(map(str, rule.periods)) or None, "sessions": ", ".join(rule.sessions) or None,
            "role": role or None, "number": rule.number, "hard": YES if rule.hard else NO,
            "level": None if rule.hard else rule.level}


def describe(rule: CustomRule) -> str:
    """Luật bằng lời, vd "Thể dục khối 3, 4 không xếp vào tiết 1 (bắt buộc)"."""
    who = rule.subject + (f" khối {', '.join(map(str, rule.grades))}" if rule.grades else "")
    where = " ".join(filter(None, [
        ", ".join(s.lower() for s in rule.sessions) and f"buổi {', '.join(s.lower() for s in rule.sessions)}",
        rule.days and ", ".join(_day_label(d) for d in rule.days),
        rule.periods and f"tiết {', '.join(map(str, rule.periods))}"]))
    text = {
        "khong_xep": f"{who} không xếp vào {where}",
        "chi_xep": f"{who} chỉ xếp vào {where}",
        "lien_2": f"{who} học 2 tiết liền",
        "truoc": f"{who} học trước {rule.other} trong buổi",
        "gv_ngay": f"{'mỗi GV ' + cells(rule)['role'] if rule.role else 'mỗi giáo viên'} dạy tối đa {rule.number} tiết "
                   f"mỗi ngày",
        "cung_luc": f"{who}: tối đa {rule.number} lớp học cùng lúc",
    }[rule.kind]
    return text + (" (bắt buộc)" if rule.hard else f" (ưu tiên mức {rule.level})")


def label(rule: CustomRule) -> str:
    return f"{SHEET} dòng {rule.row}: {describe(rule)}"


# ---- dùng khi xếp (đọc config hiện tại, gọi trong rules.applied) ----

def _subject(name: str) -> str:
    from .program import canonical_subject
    return canonical_subject(name)


def _grade_ok(rule: CustomRule, grade: int) -> bool:
    return not rule.grades or grade in rule.grades


def _slots(rule: CustomRule) -> set[tuple[int, int]]:
    """Các ô (ngày, tiết) của khung giờ khớp cột Ngày, Tiết, Buổi của luật (cột trống: mọi giá trị)."""
    out = set()
    for d, sessions in config.DAY_SESSIONS.items():
        if rule.days and d not in rule.days:
            continue
        for s in sessions:
            if rule.sessions and s.name not in rule.sessions:
                continue
            out |= {(d, p) for p in s.periods if not rule.periods or p in rule.periods}
    return out


def _all_slots() -> set[tuple[int, int]]:
    return {(d, p) for d, ss in config.DAY_SESSIONS.items() for s in ss for p in s.periods}


def _bad_slots(rule: CustomRule) -> set[tuple[int, int]]:
    """Ô mà môn của luật vị trí không được (bắt buộc) / không nên (ưu tiên) học."""
    return _slots(rule) if rule.kind == "khong_xep" else _all_slots() - _slots(rule)


def _weight(rule: CustomRule, w: config.Weights) -> int:
    return w.custom_levels[rule.level - 1]


def _rules(kind: str, hard: bool | None = None) -> list[CustomRule]:
    return [r for r in config.CUSTOM_RULES if r.kind == kind and (hard is None or r.hard == hard)]


def banned(subject: str, grade: int) -> set[tuple[int, int]]:
    """Ô mà môn của khối không được học theo các luật vị trí bắt buộc (dùng trong solver.allowed_slots)."""
    out = set()
    for r in config.CUSTOM_RULES:
        if r.hard and r.kind in ("khong_xep", "chi_xep") and _grade_ok(r, grade) and _subject(r.subject) == subject:
            out |= _bad_slots(r)
    return out


def forced_pairs(grade: int, totals: dict[str, int]) -> set[str]:
    """Nhóm môn của khối phải học 2 tiết liền theo luật bắt buộc (số tiết chẵn; lẻ thì precheck báo lỗi)."""
    from .allocation import subject_group
    out = set()
    for r in _rules("lien_2", hard=True):
        group = subject_group(_subject(r.subject))
        if _grade_ok(r, grade) and totals.get(group, 0) > 0 and totals[group] % 2 == 0:
            out.add(group)
    return out


def day_cap(teacher) -> int | None:
    """Số tiết tối đa mỗi ngày của GV theo luật bắt buộc (None: không giới hạn); dùng trong phan_cong.teacher_slots."""
    caps = [r.number for r in _rules("gv_ngay", hard=True) if not r.role or r.role == teacher.role]
    return min(caps) if caps else None


def build(m, problem, x: dict, dom: dict, occ_terms: dict, w: config.Weights) -> list:
    """Ràng buộc và mục tiêu của các luật riêng trong mô hình CP-SAT (solver.build_timetable); trả về các số hạng
    mục tiêu. Luật vị trí bắt buộc và luật 2 tiết liền bắt buộc đã nằm trong miền ô (`banned`) và nhóm ghép cặp
    (`forced_pairs`)."""
    from .allocation import paired_groups, subject_group
    if not config.CUSTOM_RULES:
        return []
    objective = []
    sessions = [(d, s) for d, ss in sorted(config.DAY_SESSIONS.items()) for s in ss]
    by_class: dict[str, dict[str, list]] = {}
    for c in problem.courses:
        by_class.setdefault(c.class_name, {}).setdefault(c.subject, []).append(c)

    def terms(cls: str, subject: str, slot) -> list:
        return [x[c.id, slot] for c in by_class.get(cls, {}).get(subject, []) if (c.id, slot) in x]

    for i, r in enumerate(config.CUSTOM_RULES):
        weight = _weight(r, w)
        subject = _subject(r.subject) if r.subject else ""
        classes = [c for c in problem.classes if _grade_ok(r, grade_of(c))]
        if r.kind in ("khong_xep", "chi_xep") and not r.hard:
            bad = _bad_slots(r)
            objective += [weight * x[c.id, s] for cls in classes for c in by_class.get(cls, {}).get(subject, [])
                          for s in dom[c.id] if s in bad]
        elif r.kind == "lien_2" and not r.hard:
            for cls in classes:
                req = problem.curriculum[grade_of(cls)]
                group = subject_group(subject)
                if group in paired_groups(req, grade_of(cls)):
                    continue  # đã bắt buộc ghép cặp
                members = [s for s in by_class.get(cls, {}) if subject_group(s) == group]
                for d, session in sessions:
                    ps = session.periods
                    for k, p in enumerate(ps):
                        here = [v for s in members for v in terms(cls, s, (d, p))]
                        if not here:
                            continue
                        near = [v for q in (ps[k - 1] if k else None, ps[k + 1] if k + 1 < len(ps) else None)
                                if q is not None for s in members for v in terms(cls, s, (d, q))]
                        lonely = m.NewBoolVar(f"le_{i}_{cls}_{d}_{p}")
                        m.Add(lonely >= sum(here) - sum(near))
                        objective.append(weight * lonely)
        elif r.kind == "truoc":
            other = _subject(r.other)
            for cls in classes:
                for d, session in sessions:
                    ps = session.periods
                    for a in range(len(ps)):
                        for b in range(a + 1, len(ps)):
                            before, after = terms(cls, other, (d, ps[a])), terms(cls, subject, (d, ps[b]))
                            if not before or not after:
                                continue
                            if r.hard:
                                m.Add(sum(before) + sum(after) <= 1)
                            else:
                                v = m.NewBoolVar(f"truoc_{i}_{cls}_{d}_{ps[a]}_{ps[b]}")
                                m.Add(v >= sum(before) + sum(after) - 1)
                                objective.append(weight * v)
        elif r.kind == "gv_ngay":
            per_day: dict[tuple[str, int], list] = defaultdict(list)
            for (g, s), vs in sorted(occ_terms.items()):
                if not r.role or problem.teachers[g].role == r.role:
                    per_day[g, s[0]].extend(vs)
            for (g, d), vs in sorted(per_day.items()):
                if len(vs) <= r.number:
                    continue
                if r.hard:
                    m.Add(sum(vs) <= r.number)
                else:
                    over = m.NewIntVar(0, len(vs), f"gv_ngay_{i}_{g}_{d}")
                    m.Add(over >= sum(vs) - r.number)
                    objective.append(weight * over)
        elif r.kind == "cung_luc":
            for slot in sorted(_all_slots()):
                vs = [v for cls in classes for v in terms(cls, subject, slot)]
                if len(vs) <= r.number:
                    continue
                if r.hard:
                    m.Add(sum(vs) <= r.number)
                else:
                    over = m.NewIntVar(0, len(vs), f"cung_luc_{i}_{slot[0]}_{slot[1]}")
                    m.Add(over >= sum(vs) - r.number)
                    objective.append(weight * over)
    return objective


def _violations(problem, lessons, hard: bool) -> list[tuple[CustomRule, int, list[tuple[str, int]], str]]:
    """Các lần không theo luật riêng (bắt buộc hoặc ưu tiên) của một TKB: (luật, số lần, các (lớp, ngày) liên quan,
    mô tả). Luật 2 tiết liền bắt buộc do checker kiểm như các nhóm ghép cặp khác."""
    from .allocation import paired_groups, subject_group
    from .solver import session_of
    out = []
    sess = session_of()
    by_cell = defaultdict(list)  # (lớp, ngày, buổi) -> các tiết
    for les in lessons:
        by_cell[les.class_name, les.day, sess[(les.day, les.period)].name].append(les)
    for r in config.CUSTOM_RULES:
        if r.hard != hard:
            continue
        subject = _subject(r.subject) if r.subject else ""
        mine = [les for les in lessons if les.subject == subject and _grade_ok(r, grade_of(les.class_name))]
        if r.kind in ("khong_xep", "chi_xep"):
            bad = _bad_slots(r)
            for les in mine:
                if (les.day, les.period) in bad:
                    out.append((r, 1, [(les.class_name, les.day)],
                                f"lớp {les.class_name} có {r.subject} {_day_label(les.day)} tiết {les.period}"))
        elif r.kind == "lien_2" and not hard:
            group = subject_group(subject)
            for (cls, d, _), items in sorted(by_cell.items()):
                if not _grade_ok(r, grade_of(cls)) or group in paired_groups(problem.curriculum[grade_of(cls)],
                                                                                  grade_of(cls)):
                    continue
                ps = {les.period for les in items if subject_group(les.subject) == group}
                lonely = sum(1 for p in ps if p - 1 not in ps and p + 1 not in ps)
                if lonely:
                    out.append((r, lonely, [(cls, d)], f"lớp {cls} {_day_label(d)} có tiết {r.subject} lẻ"))
        elif r.kind == "truoc":
            other = _subject(r.other)
            for (cls, d, name), items in sorted(by_cell.items()):
                if not _grade_ok(r, grade_of(cls)):
                    continue
                first = [les.period for les in items if les.subject == subject]
                second = [les.period for les in items if les.subject == other]
                n = sum(1 for p in first for q in second if q < p)
                if n:
                    out.append((r, n, [(cls, d)],
                                f"lớp {cls} {_day_label(d)} buổi {name.lower()}: {r.other} trước {r.subject}"))
        elif r.kind == "gv_ngay":
            per = defaultdict(list)
            for les in lessons:
                if not r.role or problem.teachers[les.teacher].role == r.role:
                    per[les.teacher, les.day].append(les)
            for (g, d), items in sorted(per.items()):
                if len(items) > r.number:
                    out.append((r, len(items) - r.number, sorted({(les.class_name, d) for les in items}),
                                f"{problem.teachers[g].code} dạy {len(items)} tiết {_day_label(d)}"))
        elif r.kind == "cung_luc":
            per = defaultdict(list)
            for les in mine:
                per[les.day, les.period].append(les)
            for (d, p), items in sorted(per.items()):
                if len(items) > r.number:
                    out.append((r, len(items) - r.number, sorted({(les.class_name, d) for les in items}),
                                f"{len(items)} lớp học {r.subject} cùng lúc {_day_label(d)} tiết {p}"))
    return out


def check(problem, lessons) -> list[str]:
    """Kiểm tra độc lập các luật riêng bắt buộc (checker.check)."""
    return [f"{label(r)}: {text}" for r, _, _, text in _violations(problem, lessons, hard=True)]


def qa(problem, lessons, w: config.Weights) -> Counter:
    """Chi phí của các luật riêng ưu tiên theo (lớp, ngày), như mục tiêu trong `build` (lns._Search.qa)."""
    cost: Counter = Counter()
    for r, n, cells_, _ in _violations(problem, lessons, hard=False):
        for key in cells_:
            cost[key] += _weight(r, w) * n / len(cells_)
    return cost


def soft_report(problem, lessons) -> list[str]:
    """Số lần không theo từng luật riêng ưu tiên (in ra màn hình sau khi xếp)."""
    count: Counter = Counter()
    for r, n, _, _ in _violations(problem, lessons, hard=False):
        count[r] += n
    return [f"{label(r)}: {count[r]} lần không theo" for r in config.CUSTOM_RULES if not r.hard] if \
        any(not r.hard for r in config.CUSTOM_RULES) else []


def validate(problem) -> list[str]:
    """Lỗi ghi của luật riêng chỉ thấy khi có chương trình học và nhân sự: môn hay chức vụ không có."""
    subjects = {s for req in problem.curriculum.values() for s, n in req.items() if n > 0}
    roles = {t.role for t in problem.teachers.values()}
    out = []
    for r in config.CUSTOM_RULES:
        for name in filter(None, (r.subject, r.other)):
            if _subject(name) not in subjects:
                out.append(f"{SHEET} dòng {r.row}: môn '{name}' không có trong chương trình học (hoặc không có tiết "
                           f"nào)")
        if r.role and r.role not in roles:
            out.append(f"{SHEET} dòng {r.row}: không có giáo viên nào có chức vụ '{cells(r)['role']}'")
    return out


def precheck(problem) -> list[str]:
    """Mâu thuẫn chắc chắn của luật riêng bắt buộc, tìm bằng phép đếm: luật vị trí để lại ít ô hơn số tiết, môn phải
    học 2 tiết liền mà số tiết lẻ, số lớp cùng lúc không đủ ô. Luật ghi sai (validate) thì bỏ qua."""
    from .allocation import subject_group
    out = []
    n_slots = len(_all_slots())
    invalid = {line.split(":")[0] for line in validate(problem)}
    for r in config.CUSTOM_RULES:
        if not r.hard or f"{SHEET} dòng {r.row}" in invalid:
            continue
        subject = _subject(r.subject) if r.subject else ""
        grades = sorted({grade_of(c) for c in problem.classes if _grade_ok(r, grade_of(c))})
        if r.kind in ("khong_xep", "chi_xep"):
            for g in grades:
                n = problem.curriculum[g].get(subject, 0)
                free = n_slots - len(banned(subject, g))
                if n > free:
                    out.append(f"{label(r)}: khối {g} có {n} tiết {r.subject} nhưng các luật vị trí bắt buộc chỉ để "
                               f"lại {free} tiết trong tuần")
        elif r.kind == "lien_2":
            group = subject_group(subject)
            for g in grades:
                n = sum(k for s, k in problem.curriculum[g].items() if subject_group(s) == group)
                if n % 2:
                    out.append(f"{label(r)}: khối {g} có {n} tiết/tuần (lẻ) nên không chia hết thành cặp 2 tiết")
        elif r.kind == "cung_luc":
            classes = [c for c in problem.classes if _grade_ok(r, grade_of(c))]
            total = sum(problem.curriculum[grade_of(c)].get(subject, 0) for c in classes)
            free = max((n_slots - len(banned(subject, g)) for g in grades), default=n_slots)
            if total > r.number * free:
                out.append(f"{label(r)}: các lớp có tổng {total} tiết {r.subject} nhưng tối đa {r.number} lớp × "
                           f"{free} tiết = {r.number * free}")
    return out
