"""Phân phần GVCN, sinh các "course" (lớp, môn, số tiết, GV hợp lệ) và GV bổ sung."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from . import config
from .program import canonical_subject, missing_rule_subjects, subjects_in_order
from .staff import (_CLASS_RE, CAMPUS1, CAMPUS2, SPECIAL_ROLES, InputError, Teacher, _fold, campus_of, class_list,
                    class_sort_key, clean_name, grade_key, grade_of, normalize, role_errors, subject_key)


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
    overtime_order: dict[str, int] = field(default_factory=dict)  # GV được bù -> thứ tự dạy bù (overtime_rank)
    overtime_max: int = 0  # > 0: chế độ bù giờ
    specialists: dict[str, tuple[str, ...]] = field(default_factory=dict)  # chức vụ chuyên biệt -> các môn được dạy
    subject_labels: dict[str, str] = field(default_factory=dict)  # môn -> tên như ghi trong file vào
    subject_order: list[str] = field(default_factory=list)  # các môn theo thứ tự dòng trong file vào
    campus2: frozenset[str] = frozenset()  # các lớp ở Cơ sở 2 (cột Cơ sở của sheet LỚP hay cột Cơ sở 2 của Chủ Nhiệm)
    # Lớp -> chỉ số cơ sở trong `campuses` (tên các cơ sở: Cơ sở 1 trước, rồi theo thứ tự lớp); một cơ sở: trống.
    campus: dict[str, int] = field(default_factory=dict)
    campuses: tuple[str, ...] = ()
    # Các lớp không có GVCN (sheet LỚP): mọi môn chia cho GV khác; tiết luôn do GVCN dạy, GVCN trước không áp dụng.
    no_homeroom: frozenset[str] = frozenset()
    # (course, người tuyển mới) -> người bù: các tiết đó là tiết bù của người bù (chế độ bù giờ dạy đúng các ô này),
    # nên khi xếp giờ cũng chiếm lịch của người bù (solver.build_timetable). Chỉ có ở bài toán xếp giờ (solver.solve).
    covers: dict[tuple[int, str], str] = field(default_factory=dict)
    # Phòng học dùng chung (sheet PHÒNG, tkb/phong_hoc.py): các phòng, course -> chỉ số các phòng hợp (course không có
    # ở đây thì học ở lớp). Không có sheet PHÒNG: trống.
    rooms: tuple[config.Room, ...] = ()
    room_fit: dict[int, tuple[int, ...]] = field(default_factory=dict)

    def overtime_mode(self) -> bool:
        return self.overtime_max > 0

    def roles(self) -> list[str]:
        """Chủ Nhiệm, Bộ Môn, các GV chuyên biệt (theo thứ tự trong file), Quản Lý."""
        return [config.ROLE_HOMEROOM, config.ROLE_GENERAL, *self.specialists, config.ROLE_MANAGER]

    def specialist_subjects(self) -> set[str]:
        return {s for subjects in self.specialists.values() for s in subjects}

    def subject_label(self, subject: str) -> str:
        """Tên môn in trong TKB: tên viết tắt trong config, không có thì tên như trong file vào."""
        return config.DISPLAY_NAMES.get(subject) or self.subject_labels.get(subject, subject)

    def class_courses(self, class_name: str) -> list[Course]:
        return [c for c in self.courses if c.class_name == class_name]

    def campus_name(self, class_name: str) -> str:
        """Tên cơ sở của lớp (trường một cơ sở: Cơ sở 1)."""
        return self.campuses[self.campus[class_name]] if self.campuses else CAMPUS1

    def campus_label(self, class_name: str) -> str:
        """Tên cơ sở của lớp trong câu: "cơ sở 1", "cơ sở 2" viết thường; tên khác giữ như ghi."""
        return campus_label(self.campus_name(class_name))


def campus_label(name: str) -> str:
    """Tên cơ sở trong câu: tên bắt đầu bằng "Cơ sở" viết thường chữ đầu (vd "cơ sở 2"), tên khác giữ như ghi."""
    return name[0].lower() + name[1:] if _fold(name).startswith("co so") else name


def all_slots() -> list[tuple[int, int]]:
    return [(d, p) for d in sorted(config.DAY_SESSIONS)
            for s in config.DAY_SESSIONS[d] for p in s.periods]


def subject_group(subject: str) -> str:
    """Nhóm môn: môn tăng cường đi cùng môn chính (config.SUBJECT_GROUPS), môn khác là nhóm riêng."""
    return config.SUBJECT_GROUPS.get(subject, subject)


def paired_groups(grade_req: dict[str, int], grade: int | None = None) -> set[str]:
    """Các nhóm môn của một khối phải xếp thành cặp 2 tiết liền nhau (config.PAIR_MIN_LESSONS, và luật riêng "Học 2
    tiết liền" bắt buộc của khối `grade`)."""
    totals: dict[str, int] = {}
    for s, n in grade_req.items():
        totals[subject_group(s)] = totals.get(subject_group(s), 0) + n
    out = {g for g, n in totals.items()
           if n >= config.PAIR_MIN_LESSONS and n % 2 == 0 and g not in config.PAIR_EXCLUDED} if config.on("ghep_cap") \
        else set()
    if grade is not None and config.CUSTOM_RULES:
        from .luat_rieng import forced_pairs
        out |= forced_pairs(grade, totals)
    return out


def homeroom_only() -> set[str]:
    """Các môn chỉ GVCN dạy (cột Chỉ GVCN dạy), khi luật "Chỉ GVCN dạy" có trong sheet LUẬT."""
    return set(config.HOMEROOM_ONLY_SUBJECTS) if config.on("chi_gvcn") else set()


def sessions_per_week() -> int:
    return sum(len(s) for s in config.DAY_SESSIONS.values())


def roles_for_subject(subject: str, specialists: dict[str, tuple[str, ...]]) -> list[str]:
    """Các chức vụ (ngoài chủ nhiệm/quản lý) được dạy môn này."""
    roles = [r for r, subjects in specialists.items() if subject in subjects]
    if subject not in config.GENERAL_FORBIDDEN_SUBJECTS:
        roles.append(config.ROLE_GENERAL)
    return roles


def may_teach(t: Teacher, subject: str, specialists: dict[str, tuple[str, ...]]) -> bool:
    """t được dạy môn này theo chức vụ chính (Bộ Môn, GV chuyên biệt) hay một chức vụ ở cột Chức Vụ Thêm."""
    roles = roles_for_subject(subject, specialists)
    return any(r in roles for r in (t.role, *t.extra_roles))


def as_specialist(t: Teacher, subject: str, specialists: dict[str, tuple[str, ...]]) -> bool:
    """t dạy môn này với tư cách GV chuyên biệt (không bị tính "bộ môn dạy môn chuyên biệt"): chức vụ chính là GV
    chuyên biệt; người có chức vụ thêm: một chức vụ GV chuyên biệt của người đó dạy môn này."""
    if not t.extra_roles:
        return t.role in specialists
    return any(subject in specialists.get(r, ()) for r in (t.role, *t.extra_roles))


def resolve_roles(staff: list[Teacher], subject_labels: dict[str, str]
                  ) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    """Các GV chuyên biệt: (chức vụ -> các môn được dạy, chức vụ -> cách ghi trong file ra).

    Chức vụ khác Chủ Nhiệm/Bộ Môn/Quản Lý là một chức vụ của sheet CHỨC VỤ (config.CUSTOM_ROLES, dạy các môn ghi
    ở đó), hoặc trùng tên một môn của chương trình học (chỉ dạy môn đó). Môn bộ môn không được dạy mà trường chưa
    có GV dạy được thì thêm một chức vụ để có thể tuyển thêm: chức vụ đầu tiên của sheet CHỨC VỤ dạy môn đó, không
    có thì chức vụ trùng tên môn. Chức vụ của sheet CHỨC VỤ không ai giữ và không cần tuyển thì không dùng.
    """
    names = {subject_key(label): s for s, label in subject_labels.items()}
    names.update({subject_key(s): s for s in subject_labels})
    errors = role_errors(staff, names)
    custom: dict[str, tuple[str, tuple[str, ...]]] = {}  # khóa tên chức vụ -> (tên, các môn), theo thứ tự dòng
    for r in config.CUSTOM_ROLES:
        subjects = []
        for s in r.subjects:
            where = f"{config.ROLES_SHEET}, dòng {r.row}" if r.row else f"Chức vụ {r.name}"
            if subject_key(s) not in names:
                errors.append(f"{where}: không có môn '{s}' trong sheet {config.PROGRAM_SHEET}")
            elif names[subject_key(s)] in homeroom_only():
                errors.append(f"{where}: môn '{s}' chỉ GVCN được dạy (cột Chỉ GVCN dạy)")
            else:
                subjects.append(names[subject_key(s)])
        custom[subject_key(r.name)] = (clean_name(r.name), tuple(dict.fromkeys(subjects)))
    if errors:
        raise InputError("\n".join(errors))
    specialists: dict[str, tuple[str, ...]] = {}
    labels = dict(config.ROLE_LABELS)
    for t in staff:
        for role, label in ((t.role, t.label), *((r, "") for r in t.extra_roles)):  # cả chức vụ ở cột Chức Vụ Thêm
            if role not in SPECIAL_ROLES and role not in specialists:
                name, subjects = custom.get(subject_key(role)) or (None, (names[subject_key(role)],))
                specialists[role] = subjects
                labels[role] = clean_name(label) if label else name or subject_labels[subjects[0]]
    covered = {s for subjects in specialists.values() for s in subjects}
    for s, label in subject_labels.items():
        if (s in config.GENERAL_FORBIDDEN_SUBJECTS and s not in homeroom_only()
                and s not in covered):
            name, subjects = next(((n, subs) for n, subs in custom.values() if s in subs), (label, (s,)))
            specialists[normalize(name)] = subjects
            labels[normalize(name)] = name
            covered.update(subjects)
    return specialists, labels


def manager_allowed(rule: config.ManagerRule, class_name: str, grade: int, subject: str) -> bool:
    if subject != rule.subject or grade != rule.grade:
        return False
    return rule.classes is None or class_name in rule.classes


def split_homeroom(class_name: str, grade_req: dict[str, int], quota: int,
                   reserved: set[str], specialist: set[str] = frozenset(), fill: bool = True) -> dict[str, int]:
    """Số tiết từng môn GVCN dạy cho lớp của mình. `fill` = False (GVCN có chức vụ thêm, dùng phần định mức còn lại
    cho chức vụ đó): chỉ nhận thêm các môn cùng nhóm với môn đã nhận trọn (vd Tiếng Việt tăng cường đi cùng Tiếng
    Việt), để nhóm môn không chia cho hai người."""
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
        held = {subject_group(s) for s in take}
        for s in config.HOMEROOM_FILL_ORDER:
            if load >= quota:
                break
            if s in banned or (not fill and subject_group(s) not in held):
                continue
            add = min(grade_req.get(s, 0) - take.get(s, 0), quota - load)
            if add > 0:
                take[s] = take.get(s, 0) + add
                load += add
    return take


def supplement_capacity(role: str, teachers: list[Teacher]) -> int:
    """Định mức GV bổ sung: Số tiết lớn nhất của GV cùng chức vụ trong file vào;
    chức vụ chưa có ai thì lấy của các GV không chủ nhiệm, không quản lý."""
    real = [t for t in teachers if not t.supplementary]
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
                    index=start + i, class_name=None, max_lessons=cap,
                    supplementary=True, label=label)
            for i in range(1, count + 1)]


def overtime_allowance(t: Teacher, overtime_max: int) -> int:
    """Số tiết bù tối đa của một GV ở chế độ bù giờ. GV đang hưởng thai sản không dạy bù."""
    if overtime_max <= 0 or t.supplementary or t.maternity or t.role not in config.OVERTIME_ROLES:
        return 0
    return overtime_max


def overtime_rank(t: Teacher) -> int:
    """Thứ tự dạy bù của t (1 = trước nhất): cột Thứ Tự Bù; không ghi thì GVCN hợp đồng 1, GVCN khác 2, bộ môn hợp đồng
    3, bộ môn khác 4."""
    if t.overtime_order is not None:
        return t.overtime_order
    return (1 if t.contract else 2) if t.class_name else (3 if t.contract else 4)


def overtime_cost(t: Teacher, w: config.Weights, ranks: dict[str, int] | None = None) -> int:
    """Giá tiết bù thứ nhất của t (mỗi tiết sau đắt thêm w.overtime_second) theo thứ tự dạy bù (overtime_rank; `ranks`:
    thứ tự của mọi người được bù, Problem.overtime_order). Thứ tự 1–4 là bốn mức w.overtime_* (GVCN hợp đồng, GVCN,
    bộ môn hợp đồng, bộ môn), cách nhau đủ xa để thứ tự này không đổi; ghi số khác thì các thứ tự đang dùng chia đều
    khoảng giá đó (mức đắt nhất vẫn rẻ hơn một tiết thiếu)."""
    tiers = (w.overtime_homeroom_contract, w.overtime_homeroom, w.overtime_general_contract, w.overtime_general)
    rank = (ranks or {}).get(t.title) or overtime_rank(t)
    used = sorted(set((ranks or {}).values()) | {rank})
    if used[-1] <= len(tiers):
        return tiers[rank - 1]
    return tiers[0] + used.index(rank) * (tiers[-1] - tiers[0]) // (len(used) - 1)


def keep_cost(t: Teacher, class_name: str, w: config.Weights) -> int:
    """Giá mỗi tiết GV không chủ nhiệm t dạy lớp `class_name` khi lệch TKB cũ (cột Lớp Đang Dạy): khác mọi khối
    đang dạy thì w.keep_grade, đúng khối nhưng khác lớp thì w.keep_class. GV không ghi Lớp Đang Dạy: 0."""
    if not t.history or t.class_name:
        return 0
    if grade_of(class_name) not in {grade_of(c) for c in t.history}:
        return w.keep_grade
    return 0 if class_name in t.history else w.keep_class


def previous_cost(t: Teacher, course: Course, w: config.Weights) -> int:
    """Xếp lại ít xáo trộn: giá mỗi tiết t dạy (lớp, môn) của course mà TKB cũ không giao cho t (Teacher.previous).
    GV không có trong TKB cũ (vd người mới): 0."""
    if not t.previous:
        return 0
    return 0 if (course.class_name, course.subject) in t.previous else w.keep_previous


def build_problem(staff: list[Teacher], curriculum: dict[int, dict[str, int]],
                  supplement_counts: dict[str, int] | None = None, overtime_max: int = 0) -> Problem:
    """Dựng bài toán.

    curriculum: chương trình học đọc từ file vào ({khối: {môn: số tiết}}).
    supplement_counts: số GV bổ sung dự kiến cho từng chức vụ; None = đủ lớn để luôn có nghiệm.
    overtime_max: > 0 là chế độ bù giờ: GVCN và bộ môn được dạy vượt
    định mức tối đa ngần ấy tiết; GVCN bù các môn không thuộc GV chuyên biệt của lớp mình (và các môn
    config.HOMEROOM_OVERTIME_SPECIALIST).
    """
    # Môn có luật trong config được gọi theo tên trong config; tên như trong file giữ lại để in ra.
    subject_labels = {canonical_subject(s): clean_name(s) for s in subjects_in_order(curriculum)}
    subject_order = list(subject_labels)
    warnings: list[str] = []
    missing = missing_rule_subjects(curriculum)
    if missing:
        warnings.append(f"Các môn có quy định mặc định trong tkb/config.py nhưng không có trong chương trình học: "
                        f"{', '.join(missing)} (nếu trường có dạy, kiểm tra lại tên môn)")
    # Sắp môn theo tên: đổi thứ tự dòng trong file chương trình học không làm đổi TKB.
    curriculum = {g: dict(sorted(((canonical_subject(s), n) for s, n in req.items()),
                                 key=lambda kv: subject_key(kv[0])))
                  for g, req in curriculum.items()}
    specialists, role_labels = resolve_roles(staff, subject_labels)
    staff = [replace(t, label=role_labels[t.role]) for t in staff]
    specialist = {s for subjects in specialists.values() for s in subjects}
    slots = all_slots()
    classes = class_list(staff)
    homeroom = {t.class_name: t for t in staff if t.class_name}
    managers = [t for t in staff if t.role == config.ROLE_MANAGER]
    # Cơ sở của từng lớp (cột Cơ sở của sheet LỚP, cột Cơ sở 2 của dòng Chủ Nhiệm); cùng tên khác hoa thường là một.
    names: dict[str, str] = {}
    where = {c: names.setdefault(_fold(n), n)
             for c in classes for n in (campus_of(c, c in homeroom and homeroom[c].campus2),)}
    order = list(dict.fromkeys(where[c] for c in classes))
    order.sort(key=lambda n: _fold(n) != _fold(CAMPUS1))  # Cơ sở 1 trước, các cơ sở khác theo thứ tự lớp
    campuses = tuple(order) if len(order) > 1 else ()
    campus = {c: order.index(n) for c, n in where.items()} if campuses else {}
    campus2 = frozenset(c for c, n in where.items() if _fold(n) == _fold(CAMPUS2))
    no_homeroom = frozenset(c for c in classes if c not in homeroom)

    for g in sorted({grade_of(c) for c in classes}, key=grade_key):
        # Lớp ghi dạng khối/số thứ tự: báo số thứ tự bị bỏ trống.
        numbers = {int(m.group(2)) for c in classes if (m := _CLASS_RE.match(c)) and grade_of(c) == g}
        missing = [f"{g}/{n}" for n in range(1, max(numbers, default=0)) if n not in numbers]
        if missing:
            warnings.append(f"Khối {g} không có lớp {', '.join(missing)} (không có Chủ Nhiệm nào ghi lớp này)"
                            if not config.CLASSES else f"Khối {g} không có lớp {', '.join(missing)} (sheet "
                            f"{config.CLASSES_SHEET} không ghi lớp này)")
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
    fixed_hdtn = tuple(config.HDTN_FIXED_SLOTS) if config.on("hdtn_co_dinh") else ()
    homeroom_slots = [s for s in slots if s[1] in config.HOMEROOM_PERIODS] if config.on("tiet_gvcn") else []

    for cls in classes:
        grade = grade_of(cls)
        req = curriculum[grade]
        if cls in no_homeroom:  # lớp không có GVCN: mọi môn chia cho GV khác
            for subject, n in req.items():
                if n <= 0:
                    continue
                if subject in homeroom_only():
                    raise InputError(f"Lớp {cls} không có Chủ Nhiệm nên không ai dạy được môn {subject} (môn chỉ GVCN "
                                     f"được dạy: bỏ Có ở cột Chỉ GVCN dạy của môn này hoặc thêm Chủ Nhiệm cho lớp)")
                pool.append((cls, grade, subject, n))
            continue
        cn = homeroom[cls]
        take = split_homeroom(cls, req, cn.max_lessons, reserved_by_grade.get(grade, set()), specialist,
                              fill=not cn.extra_roles)
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
                    flex = config.on("hdtn_ngay")
                    if flex and not config.HDTN_FLEX_DAYS:
                        raise InputError("Chưa cấu hình ngày cho tiết HĐTN linh hoạt")
                    courses.append(Course(len(courses), cls, grade, subject, n - n_fixed, [cn.title],
                                          homeroom=True, allowed_days=tuple(config.HDTN_FLEX_DAYS) if flex else None,
                                          flex_hdtn=True))
            else:
                courses.append(Course(len(courses), cls, grade, subject, n, [cn.title], homeroom=True))
        for subject, n in req.items():
            rest = n - take.get(subject, 0)
            if rest <= 0:
                continue
            if subject in homeroom_only():
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

    teacher_of = {t.title: t for t in all_teachers}
    by_role: dict[str, list[Teacher]] = {}
    for t in all_teachers:
        for role in (t.role, *t.extra_roles):  # chức vụ ở cột Chức Vụ Thêm cũng được dạy các môn của chức vụ đó
            by_role.setdefault(role, []).append(t)

    overtime = {t.title: n for t in staff if (n := overtime_allowance(t, overtime_max)) > 0}
    overtime_order = {g: overtime_rank(teacher_of[g]) for g in overtime}
    for t in staff:  # cột Thứ Tự Bù của người không được dạy bù thì không có tác dụng
        if t.overtime_order is not None and overtime_allowance(t, 1) == 0:
            warnings.append(f"{t.code}: không được dạy bù (chức vụ, thai sản) nên cột Thứ Tự Bù không có tác dụng")
    manager_pool_lessons: dict[str, int] = {m.title: 0 for m in managers}
    for cls, grade, subject, n in pool:
        # GV chỉ dạy cơ sở 2 (đánh dấu Cơ sở 2, hoặc thai sản) không dạy lớp ở cơ sở 1.
        eligible = list(dict.fromkeys(t.title for r in roles_for_subject(subject, specialists)
                                      for t in by_role.get(r, [])
                                      if cls in campus2 or not t.campus2_only or not config.on("co_so_2")))
        # GVCN bù ở lớp mình: không bù môn của GV chuyên biệt, trừ HOMEROOM_OVERTIME_SPECIALIST.
        if cls in homeroom and homeroom[cls].title in overtime and (subject not in specialist
                                                                    or subject in config.HOMEROOM_OVERTIME_SPECIALIST) \
                and homeroom[cls].title not in eligible:
            eligible.append(homeroom[cls].title)
        for m in managers:
            if (cls in campus2 or not m.campus2_only or not config.on("co_so_2")) and \
                    any(manager_allowed(rule, cls, grade, subject) for rule in config.MANAGER_RULES):
                eligible.append(m.title)
                manager_pool_lessons[m.title] += n
        if config.CUSTOM_RULES:  # luật bắt buộc "Người dạy" không xét ô (vd Chỉ giáo viên dạy): lọc khi phân công
            from .bo_ghep import refusing
            from .luat_rieng import label
            refused = {g: refusing(teacher_of[g], cls, grade, subject, curriculum) for g in eligible}
            kept = [g for g in eligible if not refused[g]]
            if eligible and not kept:
                rules = dict.fromkeys(label(L.rule) for g in eligible for L in refused[g])
                raise InputError(f"Lớp {cls}: không GV nào được dạy {subject_labels.get(subject, subject)} theo "
                                 f"{'; '.join(rules)} (tên ở cột Giáo viên phải là chức vụ, Mã GV hay họ tên của người "
                                 f"được dạy môn này)")
            eligible = kept
        if not eligible:
            raise InputError(f"Lớp {cls}: không có GV nào được phép dạy môn {subject}")
        if subject == config.HDTN and cls in no_homeroom:  # lớp không có GVCN: tiết HĐTN như các lớp khác
            n_fixed = min(n, len(fixed_hdtn))
            if n_fixed:
                courses.append(Course(len(courses), cls, grade, subject, n_fixed, eligible,
                                      fixed_slots=fixed_hdtn[:n_fixed]))
            if n > n_fixed:
                flex = config.on("hdtn_ngay")
                courses.append(Course(len(courses), cls, grade, subject, n - n_fixed, eligible,
                                      allowed_days=tuple(config.HDTN_FLEX_DAYS) if flex else None, flex_hdtn=True))
            continue
        courses.append(Course(len(courses), cls, grade, subject, n, eligible))

    manager_load: dict[str, int] = {}
    for m in managers:
        manager_load[m.title] = min(m.max_lessons, manager_pool_lessons[m.title])
        if manager_load[m.title] < m.max_lessons:
            warnings.append(f"{m.title}: chỉ có {manager_pool_lessons[m.title]} tiết phù hợp "
                            f"để dạy (định mức {m.max_lessons})")

    from .phong_hoc import fit  # phong_hoc dùng phan_cong, phan_cong nhập module này: nhập muộn
    room_fit = fit(courses, where, subject_labels)

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
        overtime_order=overtime_order,
        overtime_max=max(overtime_max, 0),
        specialists=specialists,
        subject_labels=subject_labels,
        subject_order=subject_order,
        campus2=campus2,
        campus=campus,
        campuses=campuses,
        no_homeroom=no_homeroom,
        rooms=tuple(config.ROOMS) if room_fit else (),
        room_fit=room_fit,
    )
