"""Kiểm tra độc lập mọi luật cứng trên TKB đã xếp (không dựa vào mô hình solver)."""
from __future__ import annotations

from collections import Counter, defaultdict

from . import config
from .allocation import Problem, all_slots, manager_allowed, specialist_subjects
from .solver import Lesson


def check(problem: Problem, lessons: list[Lesson], student_rules: bool = True) -> list[str]:
    errors: list[str] = []
    slots = set(all_slots())
    teachers = problem.teachers
    day = config.DAYS

    def where(d: int, p: int) -> str:
        return f"{day[d]} tiết {p}"

    by_class_slot: dict[tuple[str, tuple[int, int]], list[Lesson]] = defaultdict(list)
    by_teacher_slot: dict[tuple[str, tuple[int, int]], list[Lesson]] = defaultdict(list)
    for les in lessons:
        s = (les.day, les.period)
        if s not in slots:
            errors.append(f"{les.class_name}: có tiết ở slot không học {where(*s)}")
        if les.teacher not in teachers:
            errors.append(f"{les.class_name} {where(*s)}: GV không tồn tại '{les.teacher}'")
            continue
        by_class_slot[les.class_name, s].append(les)
        by_teacher_slot[les.teacher, s].append(les)

    # Lớp: mỗi slot đúng 1 tiết, đủ số tiết từng môn.
    for cls in problem.classes:
        grade = int(cls.split("/")[0])
        req = {s: n for s, n in problem.curriculum[grade].items() if n > 0}
        full = sum(req.values()) == len(slots)
        for s in slots:
            n = len(by_class_slot.get((cls, s), []))
            if n > 1 or (full and n == 0):
                errors.append(f"Lớp {cls} {where(*s)}: có {n} tiết")
        got = Counter(les.subject for les in lessons if les.class_name == cls)
        for subject in set(req) | set(got):
            if got.get(subject, 0) != req.get(subject, 0):
                errors.append(f"Lớp {cls}: môn {subject} có {got.get(subject, 0)} tiết, "
                              f"cần {req.get(subject, 0)}")

    # GV: không trùng giờ, không vượt định mức.
    for (g, s), items in by_teacher_slot.items():
        if len(items) > 1:
            errors.append(f"{g} dạy {len(items)} lớp cùng lúc {where(*s)}: "
                          f"{', '.join(i.class_name for i in items)}")
    load = Counter(les.teacher for les in lessons)
    for g, n in load.items():
        extra = problem.overtime.get(g, 0)
        if g in teachers and n > teachers[g].max_lessons + extra:
            errors.append(f"{g} dạy {n} tiết, vượt định mức {teachers[g].max_lessons}"
                          + (f" + {extra} tiết bù" if extra else ""))
    for g, need in problem.manager_load.items():
        if load.get(g, 0) != need:
            errors.append(f"{g} dạy {load.get(g, 0)} tiết, yêu cầu đúng {need} tiết")

    # Quyền dạy.
    for les in lessons:
        t = teachers.get(les.teacher)
        if t is None:
            continue
        grade = int(les.class_name.split("/")[0])
        at = f"{les.class_name} {where(les.day, les.period)}"
        if les.period in config.HOMEROOM_PERIODS and t.class_name != les.class_name:
            errors.append(f"{at}: tiết của GVCN nhưng giao cho {t.title}")
        if t.role == config.ROLE_HOMEROOM:
            if t.class_name != les.class_name:
                errors.append(f"{at}: {t.title} không phải GVCN lớp này")
        elif les.subject in config.HOMEROOM_ONLY_SUBJECTS:
            errors.append(f"{at}: {les.subject} chỉ GVCN được dạy, nhưng giao cho {t.title}")
        elif t.role == config.ROLE_GENERAL:
            if les.subject in config.GENERAL_FORBIDDEN_SUBJECTS:
                errors.append(f"{at}: bộ môn không được dạy {les.subject} ({t.title})")
        elif t.role == config.ROLE_MANAGER:
            if not any(manager_allowed(r, les.class_name, grade, les.subject) for r in config.MANAGER_RULES):
                errors.append(f"{at}: {t.title} không được dạy {les.subject}")
        elif t.role in config.SPECIALIST_ROLES:
            if les.subject != config.SPECIALIST_ROLES[t.role]:
                errors.append(f"{at}: {t.title} chỉ được dạy {config.SPECIALIST_ROLES[t.role]}")

    # GVCN dạy đủ phần đã phân; phần dạy thêm chỉ là tiết bù hợp lệ (chế độ bù giờ).
    homeroom = {t.class_name: t.title for t in teachers.values() if t.class_name}
    for cls, take in problem.homeroom_take.items():
        got = Counter(les.subject for les in lessons
                      if les.class_name == cls and teachers[les.teacher].class_name == cls)
        want = Counter({s: n for s, n in take.items() if n > 0})
        extra = got - want
        if want - got:
            errors.append(f"Lớp {cls}: GVCN dạy {dict(got)}, phân công là {take}")
        elif extra:
            allowed = problem.overtime.get(homeroom[cls], 0)
            banned = sorted(s for s in extra if s in specialist_subjects())
            if sum(extra.values()) > allowed or banned:
                errors.append(f"Lớp {cls}: GVCN dạy bù {dict(extra)} không hợp lệ (tối đa {allowed} tiết, "
                              f"không bù môn chuyên biệt)")

    # HĐTN: 2 slot cố định + phần còn lại trong các ngày linh hoạt.
    for cls in problem.classes:
        hdtn = [(les.day, les.period) for les in lessons if les.class_name == cls and les.subject == config.HDTN]
        for s in config.HDTN_FIXED_SLOTS:
            if hdtn and s not in hdtn:
                errors.append(f"Lớp {cls}: thiếu HĐTN cố định {where(*s)}")
        for s in hdtn:
            if s not in config.HDTN_FIXED_SLOTS and s[0] not in config.HDTN_FLEX_DAYS:
                errors.append(f"Lớp {cls}: HĐTN linh hoạt ở {where(*s)} ngoài các ngày cho phép")

    if student_rules:
        errors.extend(_check_student_rules(problem, lessons))
    return errors


def _check_student_rules(problem: Problem, lessons: list[Lesson]) -> list[str]:
    errors = []
    grid: dict[tuple[str, int, int], str] = {(l.class_name, l.day, l.period): l.subject for l in lessons}
    for cls in problem.classes:
        for d, sessions in config.DAY_SESSIONS.items():
            for session in sessions:
                subjects = [grid.get((cls, d, p)) for p in session.periods]
                for group, limit in config.SESSION_SUBJECT_LIMITS:
                    n = sum(1 for s in subjects if s in group)
                    if n > limit:
                        errors.append(f"Lớp {cls} {config.DAYS[d]} buổi {session.name}: "
                                      f"{n} tiết {'/'.join(sorted(group))} (tối đa {limit})")
    return errors
