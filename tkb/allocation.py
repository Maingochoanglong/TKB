"""Phân phần GVCN, sinh các "course" (lớp, môn, số tiết, GV hợp lệ) và GV bổ sung."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from . import config
from .program import canonical_subject, missing_rule_subjects, subjects_in_order
from .staff import (SPECIAL_ROLES, InputError, Teacher, class_sort_key, classes_from_staff, clean_name, normalize,
                    role_errors, subject_key)


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
    specialists: dict[str, str] = field(default_factory=dict)  # chức vụ chuyên biệt -> môn duy nhất được dạy
    subject_labels: dict[str, str] = field(default_factory=dict)  # môn -> tên như ghi trong file vào
    subject_order: list[str] = field(default_factory=list)  # các môn theo thứ tự dòng trong file vào

    def overtime_mode(self) -> bool:
        return self.overtime_max > 0

    def roles(self) -> list[str]:
        """Chủ Nhiệm, Bộ Môn, các GV chuyên biệt (theo thứ tự trong file), Quản Lý."""
        return [config.ROLE_HOMEROOM, config.ROLE_GENERAL, *self.specialists, config.ROLE_MANAGER]

    def specialist_subjects(self) -> set[str]:
        return set(self.specialists.values())

    def subject_label(self, subject: str) -> str:
        """Tên môn in trong TKB: tên viết tắt trong config, không có thì tên như trong file vào."""
        return config.DISPLAY_NAMES.get(subject) or self.subject_labels.get(subject, subject)

    def class_courses(self, class_name: str) -> list[Course]:
        return [c for c in self.courses if c.class_name == class_name]


def all_slots() -> list[tuple[int, int]]:
    return [(d, p) for d in sorted(config.DAY_SESSIONS)
            for s in config.DAY_SESSIONS[d] for p in s.periods]


def roles_for_subject(subject: str, specialists: dict[str, str]) -> list[str]:
    """Các chức vụ (ngoài chủ nhiệm/quản lý) được dạy môn này."""
    roles = [r for r, s in specialists.items() if s == subject]
    if subject not in config.GENERAL_FORBIDDEN_SUBJECTS:
        roles.append(config.ROLE_GENERAL)
    return roles


def resolve_roles(staff: list[Teacher], subject_labels: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Suy ra GV chuyên biệt từ tên chức vụ: (chức vụ -> môn, chức vụ -> cách ghi trong file ra).

    Chức vụ khác Chủ Nhiệm/Bộ Môn/Quản Lý phải trùng tên một môn của chương trình học. Môn bộ môn không
    được dạy mà trường chưa có GV chuyên biệt thì thêm chức vụ trùng tên môn để có thể tuyển thêm.
    """
    names = {subject_key(label): s for s, label in subject_labels.items()}
    names.update({subject_key(s): s for s in subject_labels})
    errors = role_errors(staff, names)
    if errors:
        raise InputError("\n".join(errors))
    specialists: dict[str, str] = {}
    labels = dict(config.ROLE_LABELS)
    for t in staff:
        if t.role not in SPECIAL_ROLES:
            specialists.setdefault(t.role, names[subject_key(t.role)])
            labels.setdefault(t.role, clean_name(t.label) if t.label else subject_labels[specialists[t.role]])
    for s, label in subject_labels.items():
        if (s in config.GENERAL_FORBIDDEN_SUBJECTS and s not in config.HOMEROOM_ONLY_SUBJECTS
                and s not in specialists.values()):
            specialists[normalize(label)] = s
            labels[normalize(label)] = label
    return specialists, labels


def manager_allowed(rule: config.ManagerRule, class_name: str, grade: int, subject: str) -> bool:
    if subject != rule.subject or grade != rule.grade:
        return False
    return rule.classes is None or class_name in rule.classes


def split_homeroom(class_name: str, grade_req: dict[str, int], quota: int,
                   reserved: set[str], specialist: set[str] = frozenset()) -> dict[str, int]:
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
        banned = set(specialist) | config.HOMEROOM_ONLY_SUBJECTS | reserved
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
    """Định mức GV bổ sung: Số tiết lớn nhất của GV cùng chức vụ (không thai sản) trong file vào;
    chức vụ chưa có ai thì lấy của các GV không chủ nhiệm, không quản lý."""
    real = [t for t in teachers if not t.maternity and not t.supplementary]
    loads = [t.max_lessons for t in real if t.role == role]
    loads = loads or [t.max_lessons for t in real if t.role not in (config.ROLE_HOMEROOM, config.ROLE_MANAGER)]
    if not loads:
        raise InputError(f"Không suy ra được định mức GV cần tuyển thêm cho chức vụ '{role}': file vào chưa có "
                         f"GV nào ngoài Chủ Nhiệm và Quản Lý")
    return max(loads)


def make_supplements(role: str, count: int, teachers: list[Teacher], label: str = "") -> list[Teacher]:
    start = max((t.index or 0 for t in teachers if t.role == role and not t.supplementary), default=0)
    cap = supplement_capacity(role, teachers) if count else 0
    return [Teacher(name=config.SUPPLEMENT_NAME, title=f"{role} {start + i}", role=role,
                    index=start + i, class_name=None, maternity=False, max_lessons=cap,
                    supplementary=True, label=label)
            for i in range(1, count + 1)]


def overtime_allowance(t: Teacher, overtime_max: int) -> int:
    """Số tiết bù tối đa của một GV ở chế độ bù giờ (người hưởng thai sản cũng được bù)."""
    if overtime_max <= 0 or t.supplementary or t.role not in config.OVERTIME_ROLES:
        return 0
    return overtime_max


def build_problem(staff: list[Teacher], curriculum: dict[int, dict[str, int]],
                  supplement_counts: dict[str, int] | None = None, overtime_max: int = 0) -> Problem:
    """Dựng bài toán.

    curriculum: chương trình học đọc từ file vào ({khối: {môn: số tiết}}).
    supplement_counts: số GV bổ sung dự kiến cho từng chức vụ; None = đủ lớn để luôn có nghiệm.
    overtime_max: > 0 là chế độ bù giờ: GVCN và bộ môn (kể cả người hưởng thai sản) được dạy vượt
    định mức tối đa ngần ấy tiết; GVCN bù các môn không thuộc GV chuyên biệt của lớp mình.
    """
    # Môn có luật trong config được gọi theo tên trong config; tên như trong file giữ lại để in ra.
    subject_labels = {canonical_subject(s): clean_name(s) for s in subjects_in_order(curriculum)}
    subject_order = list(subject_labels)
    warnings: list[str] = []
    missing = missing_rule_subjects(curriculum)
    if missing:
        warnings.append(f"Các môn có luật trong tkb/config.py nhưng không có trong chương trình học: "
                        f"{', '.join(missing)} (nếu trường có dạy, kiểm tra lại tên môn)")
    # Sắp môn theo tên: đổi thứ tự dòng trong file chương trình học không làm đổi TKB.
    curriculum = {g: dict(sorted(((canonical_subject(s), n) for s, n in req.items()),
                                 key=lambda kv: subject_key(kv[0])))
                  for g, req in curriculum.items()}
    specialists, role_labels = resolve_roles(staff, subject_labels)
    staff = [replace(t, label=role_labels[t.role]) for t in staff]
    specialist = set(specialists.values())
    slots = all_slots()
    classes = classes_from_staff(staff)
    homeroom = {t.class_name: t for t in staff if t.class_name}
    managers = [t for t in staff if t.role == config.ROLE_MANAGER]

    for g in sorted({int(c.split("/")[0]) for c in classes}):
        numbers = {int(c.split("/")[1]) for c in classes if int(c.split("/")[0]) == g}
        missing = [f"{g}/{n}" for n in range(1, max(numbers)) if n not in numbers]
        if missing:
            warnings.append(f"Khối {g} không có lớp {', '.join(missing)} (không có Chủ Nhiệm nào ghi lớp này)")
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
        take = split_homeroom(cls, req, cn.max_lessons, reserved_by_grade.get(grade, set()), specialist)
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
        roles = roles_for_subject(subject, specialists)
        if not roles:
            raise InputError(f"Không có chức vụ nào được phép dạy môn {subject}")
        for r in roles:
            role_demand[r] = role_demand.get(r, 0) + n

    all_teachers = list(staff)
    supplement_roles: dict[str, list[str]] = {}
    for role, demand in role_demand.items():
        if supplement_counts is None:
            cap = supplement_capacity(role, staff)
            count = math.ceil(demand / cap) if cap > 0 else 0
        else:
            count = supplement_counts.get(role, 0)
        extra = make_supplements(role, count, staff, role_labels[role])
        supplement_roles[role] = [t.title for t in extra]
        all_teachers.extend(extra)

    by_role: dict[str, list[Teacher]] = {}
    for t in all_teachers:
        by_role.setdefault(t.role, []).append(t)

    overtime = {t.title: n for t in staff if (n := overtime_allowance(t, overtime_max)) > 0}
    manager_pool_lessons: dict[str, int] = {m.title: 0 for m in managers}
    for cls, grade, subject, n in pool:
        eligible = [t.title for r in roles_for_subject(subject, specialists) for t in by_role.get(r, [])]
        if homeroom[cls].title in overtime and subject not in specialist:
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
        specialists=specialists,
        subject_labels=subject_labels,
        subject_order=subject_order,
    )
