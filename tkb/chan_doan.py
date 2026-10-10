"""Chẩn đoán vì sao không xếp được TKB: luật bắt buộc nào mâu thuẫn, nói bằng dòng luật nhà trường đã ghi (sheet LUẬT).

1. `precheck(problem, student_rules)`: đếm trước khi xếp (vài mili giây, gọi ở solver._assignment và khi Kiểm tra
   trên giao diện). Chỉ báo khi chắc chắn không có TKB nào thỏa, vd khối 1 có 14 tiết Tiếng Việt mà "Số tiết tối đa
   một nhóm môn mỗi buổi" = 1 chỉ cho 9 buổi × 1 tiết. Các phép đếm khác nằm sẵn ở allocation.build_problem
   (tổng số tiết vượt khung giờ, GVCN không đủ tiết cho tiết Luôn do GVCN dạy) và solver.allowed_slots.
2. `diagnose(staff, curriculum, settings, log)`: khi bộ giải không tìm được TKB. Mỗi lần thử là một mô hình CP-SAT
   tìm nghiệm đầu tiên (solver.feasible) với một số dòng luật bắt buộc được bỏ (luật có sẵn: config.OFF; luật xếp
   bằng bộ ghép: bỏ khỏi config.CUSTOM_RULES), mỗi dòng bắt buộc của sheet LUẬT là một nhóm:
   - không nới gì mà vẫn xếp được, hoặc chưa biết: do thiếu thời gian, không phải mâu thuẫn;
   - nới hết các nhóm luật mà vẫn không xếp được: do nhân sự, định mức, quyền dạy;
   - còn lại: lọc bỏ dần từng nhóm luật để còn nhóm nhỏ nhất vẫn mâu thuẫn, rồi thử nới riêng từng luật trong đó.
   Xếp thật không nới gì nên mô hình và mã kết quả không đổi.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace

from . import config
from .allocation import Problem, paired_groups, subject_group
from .rules import applied
from .staff import CAMPUS1, Teacher, _fold, campus_of, grade_key, grade_of

SECONDS = 30  # thời lượng mỗi lần thử khi chẩn đoán (đơn vị như THOI_GIAN_TOI_DA)


def _q(key: str, subject: str = "") -> str:
    """Tên dòng luật có sẵn `key` (dòng của môn `subject` nếu có) như nhà trường thấy, để báo trong phép đếm."""
    from . import luat_co_san
    from .luat_rieng import label
    native = luat_co_san.BY_KEY[key]
    for r in luat_co_san.rows():
        if not r.off and luat_co_san.fits(native, r) and replace(r, group_label="") not in \
                [replace(c, group_label="") for c in config.CUSTOM_RULES] and (not subject or subject in r.subject):
            return f"'{label(r)}'"
    return f"'{key}'"


def precheck(problem: Problem, student_rules: bool = True) -> list[str]:
    """Các mâu thuẫn chắc chắn giữa chương trình học và luật bảo vệ học sinh, tìm bằng phép đếm (mỗi khối một lần)."""
    out = []
    if config.CUSTOM_RULES:  # luật riêng: môn/chức vụ không có, luật vị trí, 2 tiết liền, số lớp cùng lúc
        from .luat_rieng import precheck as precheck_custom
        out += precheck_custom(problem)
    if problem.room_fit and config.on("phong"):  # phòng học dùng chung: đủ chỗ cả tuần
        from .phong_hoc import clusters
        week = len(problem.slots)
        for kinds, rooms in clusters(problem):
            parts = [(cids, k) for k, cids in kinds.items()]
            if len(parts) > 1:
                parts.append(([cid for cids in kinds.values() for cid in cids], rooms))
            for cids, where in parts:
                need = sum(problem.courses[cid].lessons for cid in cids)
                room = sum(problem.rooms[r].capacity for r in where)
                if need > room * week:
                    subjects = ", ".join(dict.fromkeys(problem.subject_label(problem.courses[cid].subject)
                                                       for cid in cids))
                    out.append(f"{subjects} cần {need} tiết/tuần ở phòng "
                               f"{', '.join(problem.rooms[r].name for r in where)} (sheet {config.ROOMS_SHEET}) nhưng "
                               f"các phòng đó chỉ chứa {room} lớp × {week} giờ học = {room * week} tiết")
    if not student_rules:
        return out
    sessions = [s for ss in config.DAY_SESSIONS.values() for s in ss]
    pair_sessions = sum(1 for s in sessions if len(s.periods) >= 2)
    n_days = len(config.DAY_SESSIONS)
    limit = config.SESSION_GROUP_LIMIT if config.on("nhom_buoi") else 10 ** 6
    for g in sorted({grade_of(c) for c in problem.classes}, key=grade_key):
        req = problem.curriculum[g]
        groups: dict[str, dict[str, int]] = {}
        for s, n in req.items():
            if n > 0:
                groups.setdefault(subject_group(s), {})[s] = n
        pairs = paired_groups(req, g)
        for group, subjects in groups.items():
            n = sum(subjects.values())
            name = " + ".join(problem.subject_labels.get(s, s) for s in subjects)
            if n > limit * len(sessions):
                out.append(f"Khối {g}: {name} có {n} tiết/tuần nhưng luật {_q('nhom_buoi')} chỉ cho tối đa "
                           f"{limit} × {len(sessions)} buổi = {limit * len(sessions)} tiết")
                continue  # một lỗi cho mỗi nhóm môn là đủ
            if group not in pairs:
                continue
            why = f"có {n} tiết/tuần nên phải học thành cặp 2 tiết liền (luật {_q('ghep_cap')})"
            if limit < 2:
                out.append(f"Khối {g}: {name} {why} nhưng luật {_q('nhom_buoi')}")
            elif n // 2 > pair_sessions:
                out.append(f"Khối {g}: {name} {why}, cần {n // 2} buổi có từ 2 tiết nhưng khung giờ chỉ có "
                           f"{pair_sessions} buổi như vậy")
            if len(subjects) == 1:
                (s, k), = subjects.items()
                daily = config.DAILY_LIMITS.get(s)
                if daily is not None and daily < 2 and k <= n_days:
                    out.append(f"Khối {g}: {name} {why} nhưng luật {_q('toi_da_ngay', s)}")
    return out


def same_teacher(problem: Problem, lessons: dict[tuple[int, str], int]) -> list[str]:
    """Học cùng giờ (problem.links): sau phân công (course, GV) -> số tiết, hai môn của một nhóm ở một lớp không được
    giao cho cùng một người, vì người đó không dạy được hai nửa lớp cùng giờ."""
    taught: dict[tuple[str, str], set[str]] = {}
    for (cid, g), n in lessons.items():
        if n:
            c = problem.courses[cid]
            taught.setdefault((c.class_name, c.subject), set()).add(g)
    out = []
    for cls, groups in problem.links.items():
        for group in groups:
            seen: dict[str, str] = {}
            for s in group:
                for g in sorted(taught.get((cls, s), ())):
                    if seen.setdefault(g, s) != s:
                        out.append(f"Lớp {cls}: {problem.subject_label(seen[g])} và {problem.subject_label(s)} học "
                                   f"cùng giờ (luật Học cùng giờ) nhưng phân công giao cả hai cho "
                                   f"{problem.teachers[g].code}; ghi luật Chỉ giáo viên dạy để mỗi môn một người dạy")
    return out


@dataclass(frozen=True)
class _Rule:
    """Một dòng luật bắt buộc có thể bỏ khi chẩn đoán."""
    label: str  # tên như nhà trường thấy: sheet LUẬT dòng n: câu luật
    off: str = ""  # luật có sẵn: khóa bỏ (config.OFF)
    daily: str = ""  # luật có sẵn "tối đa tiết mỗi ngày" của môn này: bỏ môn khỏi config.DAILY_LIMITS
    custom: int = -1  # luật xếp bằng bộ ghép: chỉ số trong config.CUSTOM_RULES


def _matters(key: str, staff: list[Teacher]) -> bool:
    """Luật có sẵn có tác dụng với dữ liệu này không (không thì không cần thử bỏ)."""
    return {"tang_cuong": bool(config.SUBJECT_GROUPS), "gvcn_truoc": bool(config.HOMEROOM_PRIORITY),
            "tiet_gvcn": bool(config.HOMEROOM_PERIODS), "chi_gvcn": bool(config.HOMEROOM_ONLY_SUBJECTS),
            "hdtn_co_dinh": bool(config.HDTN and config.HDTN_FIXED_SLOTS),
            "hdtn_ngay": bool(config.HDTN) and set(config.HDTN_FLEX_DAYS) != set(config.DAY_SESSIONS),
            "buoi_nghi": any(t.off_sessions or t.off_any for t in staff),
            "co_so": len({_fold(campus_of(t.class_name, t.campus2)) for t in staff if t.class_name}
                         | {_fold(c.campus or CAMPUS1) for c in config.CLASSES}) > 1,  # có từ hai cơ sở
            "co_so_2": any(t.campus2_only for t in staff)}.get(key, True)


def _rules(staff: list[Teacher], settings: config.Settings) -> list[_Rule]:
    """Các dòng luật bắt buộc đang có hiệu lực, theo thứ tự dòng của sheet LUẬT."""
    from . import luat_co_san
    from .luat_rieng import label
    from .program import canonical_subject
    out = []
    plain = lambda r: replace(r, group_label="")  # noqa: E731  (cột Nhóm không đổi luật)
    custom = [plain(r) for r in config.CUSTOM_RULES]
    for r in luat_co_san.rows():
        if not r.hard or r.off:
            continue
        if plain(r) in custom:  # xếp bằng bộ ghép
            out.append(_Rule(label(r), custom=custom.index(plain(r))))
            continue
        native = luat_co_san.native_of(r)
        if native is None or not config.on(native.key) or (native.student and not settings.student_rules) \
                or not _matters(native.key, staff):
            continue
        if native.key == "toi_da_ngay":
            out.append(_Rule(label(r), daily=canonical_subject(r.subject)))
        else:
            out.append(_Rule(label(r), off=native.key))
    if config.ROOMS and config.on("phong"):  # sheet PHÒNG: sức chứa các phòng học dùng chung
        out.append(_Rule(f"sheet {config.ROOMS_SHEET}: phòng học dùng chung (mỗi giờ không quá sức chứa)",
                         off="phong"))
    return out


@contextmanager
def _relaxed(rules: list[_Rule]):
    dropped = {r.custom for r in rules if r.custom >= 0}
    daily = {r.daily for r in rules if r.daily}
    values = {"OFF": config.OFF | {r.off for r in rules if r.off},
              "DAILY_LIMITS": {s: n for s, n in config.DAILY_LIMITS.items() if s not in daily},
              "CUSTOM_RULES": [r for i, r in enumerate(config.CUSTOM_RULES) if i not in dropped]}
    with applied(values):
        yield


@dataclass
class Diagnosis:
    conflict: bool  # chắc chắn mâu thuẫn (không phải do thiếu thời gian)
    lines: list[str] = field(default_factory=list)  # lời giải thích, dòng đầu là kết luận


def diagnose(staff: list[Teacher], curriculum: dict[int, dict[str, int]], settings: config.Settings,
             log=print, seconds: float = SECONDS) -> Diagnosis:
    """Tìm luật bắt buộc nào làm không xếp được (xem đầu module)."""
    from .solver import feasible

    rules = _rules(staff, settings)

    def test(relax: list[_Rule]) -> bool | None:
        with _relaxed(relax):
            return feasible(staff, curriculum, settings, seconds)

    log(f"Chẩn đoán: tìm luật bắt buộc làm không xếp được ({len(rules)} nhóm luật, mỗi lần thử tối đa ~{seconds}s)...")
    now = test([])
    if now is not False:
        return Diagnosis(False, [
            "Không tìm được TKB trong thời gian cho phép" + (
                "; thử lại lâu hơn thì tìm được, nên các luật không mâu thuẫn" if now else
                ", và cũng chưa chứng minh được là các luật mâu thuẫn") +
            ". Tăng thời gian xếp giờ (THOI_GIAN_TOI_DA, dòng lệnh --time-limit, giao diện: Thời gian xếp giờ)."])
    if test(rules) is not True:
        return Diagnosis(True, [
            "Không có TKB nào thỏa, kể cả khi nới hết các luật về giờ học: nguyên nhân ở nhân sự, định mức hoặc quyền "
            "dạy (vd một giáo viên phải dạy nhiều tiết hơn số ô giờ còn trống của mình). Kiểm tra sheet NHÂN SỰ và "
            "CHƯƠNG TRÌNH HỌC."])
    core = list(rules)
    for rule in list(core):
        keep = [r for r in core if r is not rule]
        if test([r for r in rules if r not in keep]) is False:  # bỏ luật này mà vẫn mâu thuẫn: không cần nó
            core.remove(rule)
        log(f"  Thử nới '{rule.label}': {'cần cho mâu thuẫn' if rule in core else 'không liên quan'}")
    fixes = [r for r in core if test([r]) is True]
    lines = [("Luật bắt buộc này không thỏa được, nên không có TKB nào:" if len(core) == 1 else
              "Các luật bắt buộc sau không cùng thỏa được, nên không có TKB nào:"),
             *(f"  - {r.label}" for r in core)]
    if fixes and len(core) > 1:
        lines.append("Nới hoặc bỏ một trong các luật trên. Chỉ cần nới riêng một luật này là xếp được: "
                     + "; ".join(r.label for r in fixes) + ".")
    elif fixes:
        lines.append("Nới hoặc bỏ luật này thì xếp được.")
    else:
        lines.append("Nới riêng một luật chưa đủ: phải nới ít nhất hai luật trên.")
    return Diagnosis(True, lines)
