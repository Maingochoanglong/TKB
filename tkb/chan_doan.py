"""Chẩn đoán vì sao không xếp được TKB: luật bắt buộc nào mâu thuẫn, nói bằng tên quy định nhà trường đã ghi.

1. `precheck(problem, student_rules)`: đếm trước khi xếp (vài mili giây, gọi ở solver._assignment và khi Kiểm tra
   trên giao diện). Chỉ báo khi chắc chắn không có TKB nào thỏa, vd khối 1 có 14 tiết Tiếng Việt mà "Số tiết tối đa
   một nhóm môn mỗi buổi" = 1 chỉ cho 9 buổi × 1 tiết. Các phép đếm khác nằm sẵn ở allocation.build_problem
   (tổng số tiết vượt khung giờ, GVCN không đủ tiết cho tiết Luôn do GVCN dạy) và solver.allowed_slots.
2. `diagnose(staff, curriculum, settings, log)`: khi bộ giải không tìm được TKB. Mỗi lần thử là một mô hình CP-SAT
   tìm nghiệm đầu tiên (solver.feasible) với một số nhóm luật bắt buộc được nới (config hoặc solver.RELAXED):
   - không nới gì mà vẫn xếp được, hoặc chưa biết: do thiếu thời gian, không phải mâu thuẫn;
   - nới hết các nhóm luật mà vẫn không xếp được: do nhân sự, định mức, quyền dạy;
   - còn lại: lọc bỏ dần từng nhóm luật để còn nhóm nhỏ nhất vẫn mâu thuẫn, rồi thử nới riêng từng luật trong đó.
   Xếp thật không nới gì (solver.RELAXED rỗng) nên mô hình và mã kết quả không đổi.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace

from . import config
from .allocation import Problem, paired_groups, subject_group
from .rules import LABELS, applied
from .staff import Teacher, grade_of

SECONDS = 30  # thời lượng mỗi lần thử khi chẩn đoán (đơn vị như THOI_GIAN_TOI_DA)
ALL = 10 ** 6  # giá trị "không giới hạn" khi nới luật


def _q(attr: str) -> str:
    return f"'{LABELS[attr]}'"


def precheck(problem: Problem, student_rules: bool = True) -> list[str]:
    """Các mâu thuẫn chắc chắn giữa chương trình học và luật bảo vệ học sinh, tìm bằng phép đếm (mỗi khối một lần)."""
    if not student_rules:
        return []
    sessions = [s for ss in config.DAY_SESSIONS.values() for s in ss]
    pair_sessions = sum(1 for s in sessions if len(s.periods) >= 2)
    n_days = len(config.DAY_SESSIONS)
    limit = config.SESSION_GROUP_LIMIT
    out = []
    for g in sorted({grade_of(c) for c in problem.classes}):
        req = problem.curriculum[g]
        groups: dict[str, dict[str, int]] = {}
        for s, n in req.items():
            if n > 0:
                groups.setdefault(subject_group(s), {})[s] = n
        pairs = paired_groups(req)
        for group, subjects in groups.items():
            n = sum(subjects.values())
            name = " + ".join(problem.subject_labels.get(s, s) for s in subjects)
            if n > limit * len(sessions):
                out.append(f"Khối {g}: {name} có {n} tiết/tuần nhưng {_q('SESSION_GROUP_LIMIT')} = {limit} chỉ cho "
                           f"tối đa {limit} × {len(sessions)} buổi = {limit * len(sessions)} tiết")
                continue  # một lỗi cho mỗi nhóm môn là đủ
            if group not in pairs:
                continue
            why = f"có {n} tiết/tuần nên phải học thành cặp 2 tiết liền ({_q('PAIR_MIN_LESSONS')} = " \
                  f"{config.PAIR_MIN_LESSONS})"
            if limit < 2:
                out.append(f"Khối {g}: {name} {why} nhưng {_q('SESSION_GROUP_LIMIT')} = {limit}")
            elif n // 2 > pair_sessions:
                out.append(f"Khối {g}: {name} {why}, cần {n // 2} buổi có từ 2 tiết nhưng khung giờ chỉ có "
                           f"{pair_sessions} buổi như vậy")
            if len(subjects) == 1:
                (s, k), = subjects.items()
                daily = config.DAILY_LIMITS.get(s)
                if daily is not None and daily < 2 and k <= n_days:
                    out.append(f"Khối {g}: {name} {why} nhưng {_q('DAILY_LIMITS')} của môn này = {daily}")
    return out


@dataclass(frozen=True)
class _Rule:
    """Một nhóm luật bắt buộc có thể nới khi chẩn đoán."""
    label: str  # tên như nhà trường thấy (cột, dòng quy định trong file vào / giao diện)
    values: tuple = ()  # (hằng số config, giá trị khi nới)
    flag: str = ""  # cờ solver.RELAXED
    leave: bool = False  # bỏ cột Buổi Nghỉ của mọi GV


def _rules(staff: list[Teacher], settings: config.Settings) -> list[_Rule]:
    """Các nhóm luật bắt buộc đang có hiệu lực, theo thứ tự thử."""
    out = []
    if settings.student_rules:
        out.append(_Rule(f"{LABELS['SESSION_GROUP_LIMIT']} (sheet QUY ĐỊNH)", (("SESSION_GROUP_LIMIT", ALL),)))
        out.append(_Rule(f"{LABELS['PAIR_MIN_LESSONS']} (sheet QUY ĐỊNH; cột Không ghép cặp)",
                         (("PAIR_MIN_LESSONS", ALL),)))
        if config.DAILY_LIMITS:
            out.append(_Rule(f"{LABELS['DAILY_LIMITS']} (cột của sheet CHƯƠNG TRÌNH HỌC)", (("DAILY_LIMITS", {}),)))
        if config.SUBJECT_GROUPS:
            out.append(_Rule("Tiết tăng cường đứng sau tiết môn chính trong ngày (cột Môn tăng cường)",
                             flag="tang_cuong"))
        out.append(_Rule("Các tiết cùng môn trong một buổi phải liền nhau (luật bảo vệ học sinh)", flag="lien_nhau"))
    out.append(_Rule("Hai tiết liền nhau cùng nhóm môn của một lớp do một người dạy", flag="lien_tiet"))
    if config.HOMEROOM_PRIORITY:
        out.append(_Rule(f"Tiết đầu tuần của môn {LABELS['HOMEROOM_PRIORITY']} do GVCN dạy", flag="gvcn_truoc"))
    if config.HOMEROOM_PERIODS:
        out.append(_Rule(f"{LABELS['HOMEROOM_PERIODS']}: tiết "
                         f"{', '.join(map(str, sorted(config.HOMEROOM_PERIODS)))} (sheet QUY ĐỊNH, bảng Tiết)",
                         (("HOMEROOM_PERIODS", set()),)))
    if config.HDTN and (config.HDTN_FIXED_SLOTS or set(config.HDTN_FLEX_DAYS) != set(config.DAY_SESSIONS)):
        out.append(_Rule(f"{LABELS['HDTN_FIXED_SLOTS']}, {LABELS['HDTN_FLEX_DAYS']} (sheet QUY ĐỊNH, bảng Ngày)",
                         (("HDTN_FIXED_SLOTS", []), ("HDTN_FLEX_DAYS", sorted(config.DAY_SESSIONS)))))
    if any(t.off_sessions or t.off_any for t in staff):
        out.append(_Rule("Buổi Nghỉ của giáo viên (sheet NHÂN SỰ)", leave=True))
    if any(t.campus2 for t in staff if t.class_name):
        out.append(_Rule("Mỗi buổi một giáo viên chỉ dạy ở một cơ sở (cột Cơ sở 2)", flag="co_so"))
    return out


@contextmanager
def _relaxed(rules: list[_Rule]):
    from . import solver

    old = solver.RELAXED
    with applied({attr: value for r in rules for attr, value in r.values}):
        solver.RELAXED = frozenset(r.flag for r in rules if r.flag)
        try:
            yield
        finally:
            solver.RELAXED = old


@dataclass
class Diagnosis:
    conflict: bool  # chắc chắn mâu thuẫn (không phải do thiếu thời gian)
    lines: list[str] = field(default_factory=list)  # lời giải thích, dòng đầu là kết luận


def diagnose(staff: list[Teacher], curriculum: dict[int, dict[str, int]], settings: config.Settings,
             log=print, seconds: float = SECONDS) -> Diagnosis:
    """Tìm luật bắt buộc nào làm không xếp được (xem đầu module)."""
    from .solver import feasible

    rules = _rules(staff, settings)
    free = [replace(t, off_sessions=frozenset(), off_any=()) for t in staff]

    def test(relax: list[_Rule]) -> bool | None:
        with _relaxed(relax):
            return feasible(free if any(r.leave for r in relax) else staff, curriculum, settings, seconds)

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
