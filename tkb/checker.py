"""Kiểm tra độc lập mọi luật cứng trên TKB đã xếp (không dựa vào mô hình solver): phần cấu trúc (đủ tiết, không trùng
giờ, định mức, quyền dạy theo chức vụ, phần chủ nhiệm, bù giờ, buổi nghỉ, cơ sở 2, phòng) ở đây; mọi dòng bắt buộc của
sheet LUẬT, luật có sẵn và luật tự ghép, kiểm bằng bộ ghép (bo_ghep.violations), cùng phép đo với mô hình. Phép thử
độc lập thứ hai cho các luật có sẵn nằm trong tests/kiem_tra_cu.py."""
from __future__ import annotations

from collections import Counter, defaultdict

from . import config
from .allocation import Problem, all_slots, manager_allowed, may_teach, overtime_rank
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

    # Lớp: mỗi slot đúng 1 tiết, đủ số tiết từng môn. Môn học cùng giờ với môn chính (luật Học cùng giờ) không tính
    # thêm giờ của lớp; dòng của luật đó (bộ ghép, cuối hàm) kiểm các môn có cùng giờ.
    extra = problem.link_extra
    for cls in problem.classes:
        grade = grade_of(cls)
        req = {s: n for s, n in problem.curriculum[grade].items() if n > 0}
        full = problem.class_load(cls) == len(slots)
        for s in slots:
            n = sum(1 for les in by_class_slot.get((cls, s), []) if (cls, les.subject) not in extra)
            if n > 1 or (full and n == 0):
                errors.append(f"Lớp {cls} {where(*s)}: có {n} tiết")
        got = Counter(les.subject for les in lessons if les.class_name == cls)
        for subject in set(req) | set(got):
            if got.get(subject, 0) != req.get(subject, 0):
                errors.append(f"Lớp {cls}: môn {subject} có {got.get(subject, 0)} tiết, "
                              f"cần {req.get(subject, 0)}")

    # GV: không trùng giờ (trừ các lớp của một nhóm ghép lớp: một giờ dạy), không vượt định mức (đếm giờ dạy).
    lead = {c.id: c.lead for c in problem.courses if c.lead is not None}
    for (g, s), items in by_teacher_slot.items():
        if len({lead.get(i.course_id, i.course_id) for i in items}) > 1 or \
                len({i.class_name for i in items}) < len(items):
            errors.append(f"{g} dạy {len(items)} lớp cùng lúc {where(*s)}: "
                          f"{', '.join(i.class_name for i in items)}")
    load = Counter(les.teacher for les in problem.taught(lessons))
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
        if t.role == config.ROLE_HOMEROOM:
            if t.class_name != les.class_name and not may_teach(t, les.subject, problem.specialists):
                errors.append(f"{at}: {t.title} không phải GVCN lớp này" + (
                    f" và chức vụ thêm ({', '.join(t.extra_roles)}) không dạy {les.subject}" if t.extra_roles else ""))
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
    # được dạy, trong khi GVCN lớp X chưa bù hết mức và đứng trước bộ môn đó trong thứ tự dạy bù (cột Thứ Tự Bù;
    # mặc định GVCN luôn trước), thì chuyển tiết đó cho GVCN luôn làm được (GVCN chỉ dạy lớp mình nên giờ đó rảnh)
    # và bớt tiết bù của bộ môn: phân công chưa đúng thứ tự ưu tiên.
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
        first = cn and overtime_rank(teachers[cn]) < overtime_rank(teachers[g])
        if spare > 0 and first and cn in problem.courses[les.course_id].teachers and key not in reported:
            reported.add(key)
            errors.append(f"{g} dạy bù {over[g]} tiết trong khi {cn} còn được bù {spare} tiết: nên để "
                          f"GVCN dạy {les.subject} lớp {les.class_name}")

    errors.extend(_check_teacher_sessions(problem, lessons))
    # Mọi dòng bắt buộc của sheet LUẬT (luật có sẵn ở dạng gốc và luật tự ghép) bằng bộ ghép. Luật theo cặp của cả
    # lớp chỉ xếp cùng luật bảo vệ học sinh (allocation.paired_groups) nên tắt theo các luật đó.
    from .bo_ghep import violations
    from .luat_co_san import hard_rows
    from .luat_rieng import label
    errors.extend(f"{label(L.rule)}: {text}" for L, _, _, text in
                  violations(problem, lessons, rules=hard_rows(student_rules), skip_forced=not student_rules))
    if problem.room_fit and config.on("phong"):  # phòng học dùng chung (sheet PHÒNG): xếp được phòng mỗi giờ
        from .phong_hoc import errors as room_errors
        errors.extend(room_errors(problem, lessons))
    return errors


def _check_teacher_sessions(problem: Problem, lessons: list[Lesson]) -> list[str]:
    """Hai luật chỉ có dạng gốc (luat_co_san.NATIVE_ONLY): GV chỉ-cơ-sở-2 (cột Cơ sở 2, thai sản) không dạy lớp cơ sở
    1; buổi nghỉ cố định không có tiết, đủ số buổi nghỉ bất kỳ đã xin."""
    errors = []
    teachers = problem.teachers
    sess = {(d, p): s.name for d, ss in config.DAY_SESSIONS.items() for s in ss for p in s.periods}
    busy: dict[str, set[tuple[int, str]]] = defaultdict(set)
    for les in lessons:
        t = teachers.get(les.teacher)
        if t is None:
            continue
        key = (les.day, sess.get((les.day, les.period), ""))
        if t.campus2_only and les.class_name not in problem.campus2 and config.on("co_so_2"):
            errors.append(f"{les.class_name} {config.DAYS[les.day]} tiết {les.period}: {t.title} chỉ dạy ở cơ sở 2 "
                          f"nhưng lớp ở {problem.campus_label(les.class_name)}")
        busy[les.teacher].add(key)
        if key in t.off_sessions and config.on("buoi_nghi"):
            errors.append(f"{t.title} có tiết buổi nghỉ {key[1].lower()} {config.DAYS[key[0]]} ({les.class_name} "
                          f"tiết {les.period})")
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
