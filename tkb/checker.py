"""Kiểm tra độc lập mọi luật cứng trên TKB đã xếp (không dựa vào mô hình solver)."""
from __future__ import annotations

from collections import Counter, defaultdict

from . import config
from .allocation import Problem, all_slots, homeroom_only, manager_allowed, may_teach, paired_groups, subject_group
from .solver import Lesson
from .staff import grade_of


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
        grade = grade_of(cls)
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
        grade = grade_of(les.class_name)
        at = f"{les.class_name} {where(les.day, les.period)}"
        if les.period in config.HOMEROOM_PERIODS and t.class_name != les.class_name and config.on("tiet_gvcn") \
                and les.class_name not in problem.no_homeroom:
            errors.append(f"{at}: tiết của GVCN nhưng giao cho {t.title}")
        if t.role == config.ROLE_HOMEROOM:
            if t.class_name != les.class_name and not may_teach(t, les.subject, problem.specialists):
                errors.append(f"{at}: {t.title} không phải GVCN lớp này" + (
                    f" và chức vụ thêm ({', '.join(t.extra_roles)}) không dạy {les.subject}" if t.extra_roles else ""))
        elif les.subject in homeroom_only():
            errors.append(f"{at}: {les.subject} chỉ GVCN được dạy, nhưng giao cho {t.title}")
        elif t.extra_roles and may_teach(t, les.subject, problem.specialists):
            pass  # được dạy theo chức vụ chính hay chức vụ thêm (cột Chức Vụ Thêm)
        elif t.role == config.ROLE_GENERAL:
            if les.subject in config.GENERAL_FORBIDDEN_SUBJECTS:
                errors.append(f"{at}: bộ môn không được dạy {les.subject} ({t.title})")
        elif t.role == config.ROLE_MANAGER:
            if not any(manager_allowed(r, les.class_name, grade, les.subject) for r in config.MANAGER_RULES):
                errors.append(f"{at}: {t.title} không được dạy {les.subject}")
        elif t.role in problem.specialists:
            if les.subject not in problem.specialists[t.role]:
                errors.append(f"{at}: {t.title} chỉ được dạy {', '.join(problem.specialists[t.role])}")

    # GVCN dạy đủ phần đã phân; phần dạy thêm chỉ là tiết bù hợp lệ (chế độ bù giờ).
    homeroom = {t.class_name: t.title for t in teachers.values() if t.class_name}
    for cls, take in problem.homeroom_take.items():
        got = Counter(les.subject for les in lessons
                      if les.class_name == cls and teachers[les.teacher].class_name == cls)
        want = Counter({s: n for s, n in take.items() if n > 0})
        extra = got - want
        cn = teachers[homeroom[cls]]
        if cn.extra_roles:  # tiết theo chức vụ thêm (cột Chức Vụ Thêm) ở lớp mình không phải tiết bù của GVCN
            extra = Counter({s: n for s, n in extra.items() if not may_teach(cn, s, problem.specialists)})
        if want - got:
            errors.append(f"Lớp {cls}: GVCN dạy {dict(got)}, phân công là {take}")
        elif extra:
            allowed = problem.overtime.get(homeroom[cls], 0)
            banned = sorted(s for s in extra if s in problem.specialist_subjects()
                            and s not in config.HOMEROOM_OVERTIME_SPECIALIST)
            if sum(extra.values()) > allowed or banned:
                allowed_spec = ", ".join(problem.subject_label(s) for s in sorted(problem.specialist_subjects())
                                         if s in config.HOMEROOM_OVERTIME_SPECIALIST)
                errors.append(f"Lớp {cls}: GVCN dạy bù {dict(extra)} không hợp lệ (tối đa {allowed} tiết, "
                              f"không bù môn chuyên biệt" + (f" trừ {allowed_spec}" if allowed_spec else "") + ")")

    # Bù giờ: GVCN được ưu tiên bù lớp mình. Bộ môn đang dạy bù mà còn dạy ở lớp X một môn GVCN lớp X
    # được dạy, trong khi GVCN lớp X chưa bù hết mức, thì chuyển tiết đó cho GVCN luôn làm được (GVCN chỉ
    # dạy lớp mình nên giờ đó rảnh) và bớt tiết bù của bộ môn: phân công chưa đúng thứ tự ưu tiên.
    over = {g: n - teachers[g].max_lessons for g, n in load.items()
            if g in problem.overtime and n > teachers[g].max_lessons}
    reported = set()
    for les in lessons:
        g = les.teacher
        if g not in over or teachers[g].class_name:
            continue
        cn = homeroom.get(les.class_name)
        if cn and teachers[cn].extra_roles:  # GVCN có chức vụ thêm còn dạy lớp khác: giờ đó chưa chắc rảnh
            continue
        spare = problem.overtime.get(cn, 0) - over.get(cn, 0) if cn else 0
        key = (g, les.class_name, les.subject)
        if spare > 0 and cn in problem.courses[les.course_id].teachers and key not in reported:
            reported.add(key)
            errors.append(f"{g} dạy bù {over[g]} tiết trong khi {cn} còn được bù {spare} tiết: nên để "
                          f"GVCN dạy {les.subject} lớp {les.class_name}")

    # HĐTN: 2 slot cố định + phần còn lại trong các ngày linh hoạt.
    fixed = config.HDTN_FIXED_SLOTS if config.on("hdtn_co_dinh") else []
    for cls in problem.classes:
        hdtn = [(les.day, les.period) for les in lessons if les.class_name == cls and les.subject == config.HDTN]
        for s in fixed:
            if hdtn and s not in hdtn:
                errors.append(f"Lớp {cls}: thiếu HĐTN cố định {where(*s)}")
        for s in hdtn if config.on("hdtn_ngay") else ():
            if s not in fixed and s[0] not in config.HDTN_FLEX_DAYS:
                errors.append(f"Lớp {cls}: HĐTN linh hoạt ở {where(*s)} ngoài các ngày cho phép")

    errors.extend(_check_teacher_order(problem, lessons))
    errors.extend(_check_teacher_sessions(problem, lessons))
    if student_rules:
        errors.extend(_check_student_rules(problem, lessons))
    if config.CUSTOM_RULES:  # luật riêng bắt buộc (tkb/luat_rieng.py)
        from .luat_rieng import check as check_custom
        errors.extend(check_custom(problem, lessons))
    return errors


def _check_teacher_order(problem: Problem, lessons: list[Lesson]) -> list[str]:
    """Liên tiết do 1 người dạy; nhóm môn ưu tiên của GVCN: tiết của người khác không trước tiết GVCN đầu tuần."""
    errors = []
    session_of = {(d, p): s for d, sessions in config.DAY_SESSIONS.items() for s in sessions for p in s.periods}
    grid = {(l.class_name, l.day, l.period): l for l in lessons}
    for les in sorted(lessons, key=lambda l: (l.class_name, l.day, l.period)):
        nxt = grid.get((les.class_name, les.day, les.period + 1))
        same = session_of.get((les.day, les.period + 1)) is session_of[les.day, les.period]
        if nxt and config.on("lien_tiet") and same \
                and subject_group(nxt.subject) == subject_group(les.subject) and nxt.teacher != les.teacher:
            errors.append(f"Lớp {les.class_name} {config.DAYS[les.day]} tiết {les.period}–{les.period + 1}: "
                          f"hai tiết liền {les.subject}/{nxt.subject} do 2 người dạy ({les.teacher}, {nxt.teacher})")
    homeroom = {t.class_name: t.title for t in problem.teachers.values() if t.class_name}
    by: dict[tuple[str, str], dict[str, list[tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))
    for les in lessons:
        by[les.class_name, subject_group(les.subject)][les.teacher].append((les.day, les.period))
    for (cls, group), per_teacher in sorted(by.items()):
        cn = homeroom.get(cls)
        if group not in config.HOMEROOM_PRIORITY or cn not in per_teacher or not config.on("gvcn_truoc"):
            continue
        first = min(per_teacher[cn])
        for g, slots in sorted(per_teacher.items()):
            early = sorted(s for s in slots if g != cn and s < first)
            if early:
                errors.append(f"Lớp {cls} môn {group}: {g} dạy {config.DAYS[early[0][0]]} tiết {early[0][1]}, "
                              f"trước tiết đầu tuần của GVCN")
    return errors


def _check_teacher_sessions(problem: Problem, lessons: list[Lesson]) -> list[str]:
    """Cơ sở và buổi nghỉ: GV chỉ-cơ-sở-2 (cột Cơ sở 2, thai sản) không dạy lớp cơ sở 1; mỗi buổi một GV chỉ dạy ở
    một cơ sở; buổi nghỉ cố định không có tiết; đủ số buổi nghỉ bất kỳ đã xin."""
    errors = []
    teachers = problem.teachers
    sess = {(d, p): s.name for d, ss in config.DAY_SESSIONS.items() for s in ss for p in s.periods}
    campuses: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    busy: dict[str, set[tuple[int, str]]] = defaultdict(set)
    for les in lessons:
        t = teachers.get(les.teacher)
        if t is None:
            continue
        key = (les.day, sess.get((les.day, les.period), ""))
        at2 = les.class_name in problem.campus2
        if t.campus2_only and not at2 and config.on("co_so_2"):
            errors.append(f"{les.class_name} {config.DAYS[les.day]} tiết {les.period}: {t.title} chỉ dạy ở cơ sở 2 "
                          f"nhưng lớp ở cơ sở 1")
        campuses[les.teacher, *key].add(2 if at2 else 1)
        busy[les.teacher].add(key)
        if key in t.off_sessions and config.on("buoi_nghi"):
            errors.append(f"{t.title} có tiết buổi nghỉ {key[1].lower()} {config.DAYS[key[0]]} ({les.class_name} "
                          f"tiết {les.period})")
    for (g, d, name), cs in sorted(campuses.items()):
        if len(cs) > 1 and config.on("co_so"):
            errors.append(f"{g} dạy cả hai cơ sở trong buổi {name.lower()} {config.DAYS[d]}")
    sessions = [(d, s.name) for d, ss in config.DAY_SESSIONS.items() for s in ss]
    for g, t in teachers.items() if config.on("buoi_nghi") else ():
        free = [k for k in sessions if k not in t.off_sessions and k not in busy.get(g, set())]
        for name, n in t.off_any:
            need = sum(k for _, k in t.off_any) if name is None else n
            got = sum(1 for k in free if name is None or k[1] == name)
            if got < need:
                kind = f"buổi {name.lower()}" if name else "buổi"
                errors.append(f"{g} xin nghỉ {need} {kind} nhưng chỉ trống {got} {kind}")
    return errors


def _check_student_rules(problem: Problem, lessons: list[Lesson]) -> list[str]:
    errors = []
    grid: dict[tuple[str, int, int], str] = {(l.class_name, l.day, l.period): l.subject for l in lessons}
    n_days = len(config.DAY_SESSIONS)
    for cls in problem.classes:
        req = problem.curriculum[grade_of(cls)]
        pairs = paired_groups(req, grade_of(cls))
        for d, sessions in config.DAY_SESSIONS.items():
            day_subjects = [grid.get((cls, d, p)) for s in sessions for p in s.periods]
            for subject, limit in config.DAILY_LIMITS.items():
                n = day_subjects.count(subject)
                if req.get(subject, 0) <= n_days and n > limit:
                    errors.append(f"Lớp {cls} {config.DAYS[d]}: {n} tiết {subject} (tối đa {limit} mỗi ngày)")
            # Tiết tăng cường sau tiết chính: trong ngày có tiết chính cùng nhóm đứng trước, không có tiết chính
            # nào đứng sau (khối không học môn chính thì không xét).
            day_at = [(p, grid.get((cls, d, p))) for s in sessions for p in s.periods]
            for extra, main in config.SUBJECT_GROUPS.items() if config.on("tang_cuong") else ():
                if not req.get(main, 0):
                    continue
                mains = [p for p, s in day_at if s == main]
                for p in (p for p, s in day_at if s == extra):
                    if not mains or max(mains) > p:
                        where = f"tiết {', '.join(map(str, mains))}" if mains else "không có trong ngày"
                        errors.append(f"Lớp {cls} {config.DAYS[d]}: {extra} ở tiết {p} phải sau các tiết {main} "
                                      f"({where})")
            for session in sessions:
                subjects = [grid.get((cls, d, p)) for p in session.periods]
                groups = Counter(subject_group(s) for s in subjects if s)
                for group, n in sorted(groups.items()):
                    if n > config.SESSION_GROUP_LIMIT and config.on("nhom_buoi"):
                        errors.append(f"Lớp {cls} {config.DAYS[d]} buổi {session.name}: {n} tiết nhóm {group} "
                                      f"(tối đa {config.SESSION_GROUP_LIMIT})")
                    at = [p for p, s in zip(session.periods, subjects) if s and subject_group(s) == group]
                    if group in pairs and (n % 2 or (n and at[-1] - at[0] + 1 != n)):
                        errors.append(f"Lớp {cls} {config.DAYS[d]} buổi {session.name}: nhóm {group} phải thành "
                                      f"cặp 2 tiết liền (tiết {', '.join(map(str, at))})")
                # Môn có từ 2 tiết trong buổi phải học liền nhau.
                for subject in dict.fromkeys(s for s in subjects if s) if config.on("lien_nhau") else ():
                    at = [p for p, s in zip(session.periods, subjects) if s == subject]
                    if len(at) > 1 and at[-1] - at[0] + 1 != len(at):
                        errors.append(f"Lớp {cls} {config.DAYS[d]} buổi {session.name}: môn {subject} không học "
                                      f"liền (tiết {', '.join(map(str, at))})")
    return errors
