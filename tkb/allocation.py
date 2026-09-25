"""Phân phần GVCN, sinh các "course" (lớp, môn, số tiết, GV hợp lệ) và GV bổ sung."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import config
from .staff import InputError, Teacher, class_sort_key, classes_from_staff


@dataclass
class Course:
    id: int
    class_name: str
    grade: int
    subject: str
    lessons: int
    teachers: list[str]  # chức vụ các GV được phép dạy; 1 phần tử = đã cố định
    homeroom: bool = False  # phần do GVCN dạy
    fixed_slots: tuple[tuple[int, int], ...] = ()  # (ngày, tiết) bắt buộc
    allowed_days: tuple[int, ...] | None = None
    flex_hdtn: bool = False  # tiết HĐTN linh hoạt (ưu tiên cuối buổi)


@dataclass
class Problem:
    teachers: dict[str, Teacher]  # theo chức vụ, gồm cả GV bổ sung dự kiến
    classes: list[str]
    curriculum: dict[int, dict[str, int]]
    courses: list[Course]
    homeroom_take: dict[str, dict[str, int]]  # lớp -> môn -> số tiết GVCN dạy
    supplement_roles: dict[str, list[str]]  # chức vụ -> các GV bổ sung dự kiến (theo thứ tự)
    manager_load: dict[str, int]  # quản lý -> số tiết bắt buộc dạy
    slots: list[tuple[int, int]]
    warnings: list[str] = field(default_factory=list)
    overtime: dict[str, int] = field(default_factory=dict)  # GV -> số tiết được dạy bù tối đa
    overtime_max: int = 0  # > 0: chế độ bù giờ

    def overtime_mode(self) -> bool:
        return self.overtime_max > 0

    def class_courses(self, class_name: str) -> list[Course]:
        return [c for c in self.courses if c.class_name == class_name]


def all_slots() -> list[tuple[int, int]]:
    return [(d, p) for d in sorted(config.DAY_SESSIONS)
            for s in config.DAY_SESSIONS[d] for p in s.periods]


def specialist_subjects() -> set[str]:
    return set(config.SPECIALIST_ROLES.values())


def roles_for_subject(subject: str) -> list[str]:
    """Các chức vụ (ngoài chủ nhiệm/quản lý) được dạy môn này."""
    roles = [r for r, s in config.SPECIALIST_ROLES.items() if s == subject]
    if subject not in config.GENERAL_FORBIDDEN_SUBJECTS:
        roles.append(config.ROLE_GENERAL)
    return roles


def manager_allowed(rule: config.ManagerRule, class_name: str, grade: int, subject: str) -> bool:
    if subject != rule.subject or grade != rule.grade:
        return False
    return rule.classes is None or class_name in rule.classes


def split_homeroom(class_name: str, grade_req: dict[str, int], quota: int,
                   reserved: set[str]) -> dict[str, int]:
    """Số tiết từng môn GVCN dạy cho lớp của mình."""
    take = {s: grade_req[s] for s in config.HOMEROOM_PRIORITY if grade_req.get(s, 0) > 0}
    only = sum(n for s, n in take.items() if s in config.HOMEROOM_ONLY_SUBJECTS)
    if only > quota:
        raise InputError(f"Lớp {class_name}: GVCN chỉ có {quota} tiết, không đủ dạy {only} tiết "
                         f"môn bắt buộc của GVCN")
    load = sum(take.values())
    if load > quota:
        for s in config.HOMEROOM_CUT_ORDER:
            if load <= quota:
                break
            if s in config.HOMEROOM_ONLY_SUBJECTS or grade_req.get(s, 0) <= 1:
                continue  # chỉ cắt môn có hơn 1 tiết
            cut = min(take.get(s, 0) - 1, load - quota)  # GVCN giữ lại ít nhất 1 tiết
            if cut > 0:
                take[s] -= cut
                load -= cut
        if load > quota:
            raise InputError(f"Lớp {class_name}: GVCN vượt định mức {load - quota} tiết mà không "
                             f"còn môn nhiều hơn 1 tiết để cắt")
    else:
        banned = specialist_subjects() | config.HOMEROOM_ONLY_SUBJECTS | reserved
        for s in config.HOMEROOM_FILL_ORDER:
            if load >= quota:
                break
            if s in banned:
                continue
            add = min(grade_req.get(s, 0) - take.get(s, 0), quota - load)
            if add > 0:
                take[s] = take.get(s, 0) + add
                load += add
    return take


def supplement_capacity(role: str, teachers: list[Teacher]) -> int:
    loads = [t.max_lessons for t in teachers if t.role == role and not t.maternity and not t.supplementary]
    return max(loads) if loads else config.FALLBACK_SUPPLEMENT_LOAD


def make_supplements(role: str, count: int, teachers: list[Teacher]) -> list[Teacher]:
    start = max((t.index or 0 for t in teachers if t.role == role and not t.supplementary), default=0)
    cap = supplement_capacity(role, teachers)
    return [Teacher(name=config.SUPPLEMENT_NAME, title=f"{role} {start + i}", role=role,
                    index=start + i, class_name=None, maternity=False, max_lessons=cap,
                    supplementary=True)
            for i in range(1, count + 1)]


def overtime_allowance(t: Teacher, overtime_max: int) -> int:
    """Số tiết bù tối đa của một GV ở chế độ bù giờ."""
    if overtime_max <= 0 or t.supplementary or t.role not in config.OVERTIME_ROLES:
        return 0
    return min(overtime_max, config.MATERNITY_OVERTIME_MAX) if t.maternity else overtime_max


def build_problem(staff: list[Teacher], curriculum: dict[int, dict[str, int]] | None = None,
                  supplement_counts: dict[str, int] | None = None, overtime_max: int = 0) -> Problem:
    """Dựng bài toán.

    supplement_counts: số GV bổ sung dự kiến cho từng chức vụ; None = đủ lớn để luôn có nghiệm.
    overtime_max: > 0 là chế độ bù giờ: GVCN và bộ môn được dạy vượt định mức tối đa ngần ấy tiết
    (người hưởng thai sản tối đa MATERNITY_OVERTIME_MAX); GVCN bù các môn không thuộc GV chuyên
    biệt của lớp mình.
    """
    curriculum = curriculum or config.DEFAULT_CURRICULUM
    slots = all_slots()
    warnings: list[str] = []
    classes = classes_from_staff(staff)
    homeroom = {t.class_name: t for t in staff if t.class_name}
    managers = [t for t in staff if t.role == config.ROLE_MANAGER]

    for g in sorted({int(c.split("/")[0]) for c in classes}):
        if g not in curriculum:
            raise InputError(f"Không có chương trình học cho Khối {g}")
        total = sum(curriculum[g].values())
        if total > len(slots):
            raise InputError(f"Khối {g} có {total} tiết/tuần, vượt {len(slots)} tiết của khung giờ")
        if total < len(slots):
            warnings.append(f"Khối {g} chỉ có {total}/{len(slots)} tiết, lớp sẽ có tiết trống")

    # Môn/khối dành riêng cho quản lý thì GVCN không lấy để bù.
    reserved_by_grade: dict[int, set[str]] = {}
    if managers:
        for rule in config.MANAGER_RULES:
            reserved_by_grade.setdefault(rule.grade, set()).add(rule.subject)

    courses: list[Course] = []
    homeroom_take: dict[str, dict[str, int]] = {}
    pool: list[tuple[str, int, str, int]] = []
    fixed_hdtn = tuple(config.HDTN_FIXED_SLOTS)
    homeroom_slots = [s for s in slots if s[1] in config.HOMEROOM_PERIODS]

    for cls in classes:
        grade = int(cls.split("/")[0])
        req = curriculum[grade]
        cn = homeroom[cls]
        take = split_homeroom(cls, req, cn.max_lessons, reserved_by_grade.get(grade, set()))
        homeroom_take[cls] = take
        if sum(take.values()) < len(homeroom_slots):
            raise InputError(f"Lớp {cls}: GVCN chỉ dạy {sum(take.values())} tiết, không đủ "
                             f"{len(homeroom_slots)} tiết bắt buộc của GVCN "
                             f"(tiết {', '.join(map(str, sorted(config.HOMEROOM_PERIODS)))} mỗi ngày)")
        for subject, n in take.items():
            if subject == config.HDTN:
                n_fixed = min(n, len(fixed_hdtn))
                courses.append(Course(len(courses), cls, grade, subject, n_fixed, [cn.title],
                                      homeroom=True, fixed_slots=fixed_hdtn[:n_fixed]))
                if n > n_fixed:
                    if not config.HDTN_FLEX_DAYS:
                        raise InputError("Chưa cấu hình ngày cho tiết HĐTN linh hoạt")
                    courses.append(Course(len(courses), cls, grade, subject, n - n_fixed, [cn.title],
                                          homeroom=True, allowed_days=tuple(config.HDTN_FLEX_DAYS),
                                          flex_hdtn=True))
            else:
                courses.append(Course(len(courses), cls, grade, subject, n, [cn.title], homeroom=True))
        for subject, n in req.items():
            rest = n - take.get(subject, 0)
            if rest <= 0:
                continue
            if subject in config.HOMEROOM_ONLY_SUBJECTS:
                raise InputError(f"Lớp {cls}: môn {subject} chỉ GVCN được dạy nhưng GVCN không đủ tiết")
            pool.append((cls, grade, subject, rest))

    # Nhu cầu tối đa theo chức vụ để dựng đủ GV bổ sung dự kiến.
    role_demand: dict[str, int] = {}
    for _, _, subject, n in pool:
        roles = roles_for_subject(subject)
        if not roles:
            raise InputError(f"Không có chức vụ nào được phép dạy môn {subject}")
        for r in roles:
            role_demand[r] = role_demand.get(r, 0) + n

    all_teachers = list(staff)
    supplement_roles: dict[str, list[str]] = {}
    for role, demand in role_demand.items():
        cap = supplement_capacity(role, staff)
        if supplement_counts is None:
            count = math.ceil(demand / cap) if cap > 0 else 0
        else:
            count = supplement_counts.get(role, 0)
        extra = make_supplements(role, count, staff)
        supplement_roles[role] = [t.title for t in extra]
        all_teachers.extend(extra)

    by_role: dict[str, list[Teacher]] = {}
    for t in all_teachers:
        by_role.setdefault(t.role, []).append(t)

    overtime = {t.title: n for t in staff if (n := overtime_allowance(t, overtime_max)) > 0}
    manager_pool_lessons: dict[str, int] = {m.title: 0 for m in managers}
    for cls, grade, subject, n in pool:
        eligible = [t.title for r in roles_for_subject(subject) for t in by_role.get(r, [])]
        if homeroom[cls].title in overtime and subject not in specialist_subjects():
            eligible.append(homeroom[cls].title)
        for m in managers:
            if any(manager_allowed(rule, cls, grade, subject) for rule in config.MANAGER_RULES):
                eligible.append(m.title)
                manager_pool_lessons[m.title] += n
        if not eligible:
            raise InputError(f"Lớp {cls}: không có GV nào được phép dạy môn {subject}")
        courses.append(Course(len(courses), cls, grade, subject, n, eligible))

    manager_load: dict[str, int] = {}
    for m in managers:
        manager_load[m.title] = min(m.max_lessons, manager_pool_lessons[m.title])
        if manager_load[m.title] < m.max_lessons:
            warnings.append(f"{m.title}: chỉ có {manager_pool_lessons[m.title]} tiết phù hợp "
                            f"để dạy (định mức {m.max_lessons})")

    return Problem(
        teachers={t.title: t for t in all_teachers},
        classes=sorted(classes, key=class_sort_key),
        curriculum=curriculum,
        courses=courses,
        homeroom_take=homeroom_take,
        supplement_roles=supplement_roles,
        manager_load=manager_load,
        slots=slots,
        warnings=warnings,
        overtime=overtime,
        overtime_max=max(overtime_max, 0),
    )
