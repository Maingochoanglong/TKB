"""Phép thử độc lập cho các luật có sẵn: bộ kiểm tra viết tay trước khi checker kiểm mọi dòng luật bằng bộ ghép
(docs/Thiet_Ke_Gop_Luat.md mục 4.4). Mỗi luật một cách đếm riêng, không dùng phép đo của bộ ghép, để test đổi chỗ ngẫu
nhiên đối chiếu hai cách (tests/test_luat_co_san.py): bộ ghép đếm sai thì test bắt được. Không xét cờ bật/tắt của luật:
test chọn luật."""
from __future__ import annotations

from collections import Counter, defaultdict

from tkb import config
from tkb.allocation import subject_group
from tkb.staff import grade_of


def _pairs(req: dict[str, int]) -> set[str]:
    """Nhóm môn phải ghép cặp theo tham số của luật có sẵn (không gồm luật tự ghép)."""
    totals = Counter()
    for s, n in req.items():
        totals[subject_group(s)] += n
    return {g for g, n in totals.items()
            if n >= config.PAIR_MIN_LESSONS and n % 2 == 0 and g not in config.PAIR_EXCLUDED}


def errors(problem, lessons) -> dict[str, list[str]]:
    """Khóa luật có sẵn (luat_co_san.NATIVES) -> các lỗi của TKB theo luật đó."""
    out: dict[str, list[str]] = defaultdict(list)
    teachers = problem.teachers
    day = config.DAYS
    session_of = {(d, p): s for d, sessions in config.DAY_SESSIONS.items() for s in sessions for p in s.periods}
    homeroom = {t.class_name: g for g, t in teachers.items() if t.class_name}

    for les in lessons:  # tiết GVCN, môn chỉ GVCN dạy
        t = teachers[les.teacher]
        mine = t.role == config.ROLE_HOMEROOM and t.class_name == les.class_name
        if les.period in config.HOMEROOM_PERIODS and not mine and les.class_name not in problem.no_homeroom:
            out["tiet_gvcn"].append(f"{les.class_name} {day[les.day]} tiết {les.period}: {les.teacher}")
        if les.subject in config.HOMEROOM_ONLY_SUBJECTS and not mine:
            out["chi_gvcn"].append(f"{les.class_name} {day[les.day]} tiết {les.period}: {les.teacher}")

    for cls in problem.classes:  # HĐTN cố định, HĐTN theo ngày
        hdtn = [(les.day, les.period) for les in lessons if les.class_name == cls and les.subject == config.HDTN]
        for s in config.HDTN_FIXED_SLOTS:
            if hdtn and s not in hdtn:
                out["hdtn_co_dinh"].append(f"Lớp {cls}: thiếu HĐTN cố định {day[s[0]]} tiết {s[1]}")
        for s in hdtn:
            if s not in config.HDTN_FIXED_SLOTS and s[0] not in config.HDTN_FLEX_DAYS:
                out["hdtn_ngay"].append(f"Lớp {cls}: HĐTN ở {day[s[0]]} tiết {s[1]}")

    grid: dict[tuple[str, int, int], list] = defaultdict(list)  # liên tiết, GVCN trước
    for les in lessons:
        grid[les.class_name, les.day, les.period].append(les)
    for les in sorted(lessons, key=lambda l: (l.class_name, l.day, l.period, l.subject)):
        same = session_of.get((les.day, les.period + 1)) is session_of[les.day, les.period]
        for nxt in grid.get((les.class_name, les.day, les.period + 1), []):
            if same and subject_group(nxt.subject) == subject_group(les.subject) and nxt.teacher != les.teacher:
                out["lien_tiet"].append(f"Lớp {les.class_name} {day[les.day]} tiết {les.period}")
    by: dict = defaultdict(lambda: defaultdict(list))
    for les in lessons:
        by[les.class_name, subject_group(les.subject)][les.teacher].append((les.day, les.period))
    for (cls, group), per_teacher in sorted(by.items()):
        cn = homeroom.get(cls)
        if group not in config.HOMEROOM_PRIORITY or cn not in per_teacher:
            continue
        first = min(per_teacher[cn])
        if any(g != cn and s < first for g, slots in per_teacher.items() for s in slots):
            out["gvcn_truoc"].append(f"Lớp {cls} môn {group}")

    campuses: dict = defaultdict(set)  # mỗi buổi một cơ sở
    for les in lessons:
        campuses[les.teacher, les.day, session_of[les.day, les.period].name].add(problem.campus.get(les.class_name, 0))
    out["co_so"] += [f"{g} {day[d]} buổi {name}" for (g, d, name), cs in sorted(campuses.items()) if len(cs) > 1]

    names = defaultdict(list)  # luật bảo vệ học sinh
    for les in sorted(lessons, key=lambda l: l.subject):
        names[les.class_name, les.day, les.period].append(les.subject)
    n_days = len(config.DAY_SESSIONS)
    for cls in problem.classes:
        req = problem.curriculum[grade_of(cls)]
        pairs = _pairs(req)
        for d, sessions in config.DAY_SESSIONS.items():
            day_subjects = [x for s in sessions for p in s.periods for x in names.get((cls, d, p), [])]
            for subject, limit in config.DAILY_LIMITS.items():
                if req.get(subject, 0) <= n_days and day_subjects.count(subject) > limit:
                    out["toi_da_ngay"].append(f"Lớp {cls} {day[d]}: {subject}")
            day_at = [(p, x) for s in sessions for p in s.periods for x in names.get((cls, d, p), [])]
            for extra, main in config.SUBJECT_GROUPS.items():
                if not req.get(main, 0):
                    continue
                mains = [p for p, s in day_at if s == main]
                if any(not mains or max(mains) > p for p in (p for p, s in day_at if s == extra)):
                    out["tang_cuong"].append(f"Lớp {cls} {day[d]}: {extra}")
            for session in sessions:
                subjects = [(p, x) for p in session.periods for x in names.get((cls, d, p), [])]
                groups = Counter(subject_group(s) for _, s in subjects)
                for group, n in sorted(groups.items()):
                    if n > config.SESSION_GROUP_LIMIT:
                        out["nhom_buoi"].append(f"Lớp {cls} {day[d]} buổi {session.name}: nhóm {group}")
                    at = [p for p, s in subjects if subject_group(s) == group]
                    if group in pairs and (n % 2 or (n and at[-1] - at[0] + 1 != n)):
                        out["ghep_cap"].append(f"Lớp {cls} {day[d]} buổi {session.name}: nhóm {group}")
                for subject in dict.fromkeys(s for _, s in subjects):
                    at = [p for p, s in subjects if s == subject]
                    if len(at) > 1 and at[-1] - at[0] + 1 != len(at):
                        out["lien_nhau"].append(f"Lớp {cls} {day[d]} buổi {session.name}: môn {subject}")
    return out
