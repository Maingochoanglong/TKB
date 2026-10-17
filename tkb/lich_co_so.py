"""Lịch cơ sở theo ngày: giáo viên dạy ở nhiều cơ sở, mỗi ngày chỉ ở một cơ sở.

Dòng luật "Hạn chế để một giáo viên đổi cơ sở trong cùng một ngày" (Số khác nhau theo Cơ sở, mỗi GV mỗi ngày tối đa 1)
khó đạt bằng vòng xếp lại: muốn gỡ một lần đổi cơ sở của người gần kín tuần phải sắp lại cả tuần của người đó cùng lúc
(docs/Thiet_Ke_Gop_Luat.md mục 3.8). Nên trước khi xếp giờ, một bài toán nhỏ (`plan`, CP-SAT, chỉ đếm số tiết, không xếp
vào giờ cụ thể) chọn cho mỗi GV dạy ở từ hai cơ sở trở lên ngày nào ở cơ sở nào, theo:
- số tiết của người đó ở từng cơ sở (cả tiết bù mà người đó dạy thay người mới, Problem.covers);
- số giờ người đó dạy được mỗi ngày (giờ trong miền các course của người đó, trừ buổi nghỉ);
- số giờ của từng lớp mỗi ngày, số giờ của từng course mỗi ngày.

Xếp giờ (solver.build_timetable) cấm người đó dạy ở cơ sở khác trong ngày đã chọn. Kế hoạch không xếp được (bước khởi
đầu không ra nghiệm) thì solver.timetable xếp lại không theo kế hoạch, như trước khi có bước này. Trường một cơ sở, hay
sheet LUẬT không có dòng đó: không làm gì, mô hình như cũ.
"""
from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from . import config

SECONDS = 30  # thời lượng tối đa của bài toán lập lịch (đơn vị như THOI_GIAN_TOI_DA)


def applies() -> bool:
    """Sheet LUẬT có dòng "mỗi GV mỗi ngày dạy tối đa 1 cơ sở" (bắt buộc hay ưu tiên) áp cho mọi GV, mọi tiết."""
    from .bo_ghep import compiled
    return any(L.measure == "so_khac" and L.count_by == "co_so" and set(L.scope) == {"gv", "ngay"} and L.op == "<="
               and L.number == 1 and L.subjects is None and L.grades is None and L.classes is None
               and L.slots is None and L.roles is None and not L.roles_not and not L.when and not L.skip
               for L in compiled())


def away(problem, days: dict[str, dict[int, int]], cid: int, g: str, day: int) -> bool:
    """Tiết của GV g ở course cid vào ngày `day` trái kế hoạch: người dạy (hay người bù tiết đó) ngày đó ở cơ sở
    khác."""
    at = problem.campus.get(problem.courses[cid].class_name, 0)
    return any(who and days.get(who, {}).get(day, at) != at for who in (g, problem.covers.get((cid, g))))


def plan(problem, fixed: dict[tuple[int, str], int], settings: config.Settings,
         log=lambda *_: None) -> dict[str, dict[int, int]]:
    """GV -> ngày -> chỉ số cơ sở (Problem.campuses) của ngày đó, cho các GV dạy ở từ hai cơ sở trở lên; rỗng: không
    cần (một cơ sở, không có dòng luật) hay không lập được. Tìm một kế hoạch mỗi ngày một cơ sở (không có mục tiêu
    phụ: có mục tiêu thì chậm hơn trăm lần); không có thì kế hoạch ít ngày phải đổi cơ sở nhất."""
    if len(problem.campuses) < 2 or not applies():
        return {}
    from .solver import course_domains
    dom = course_domains(problem)
    courses = problem.courses
    at = {c.id: problem.campus.get(c.class_name, 0) for c in courses}
    lessons = {(cid, g): n for (cid, g), n in sorted(fixed.items()) if n > 0 and courses[cid].lead is None}
    parts: dict[str, list[tuple[int, str]]] = defaultdict(list)  # GV -> các (course, người dạy) chiếm lịch người đó
    for cid, g in lessons:
        for who in (g, problem.covers.get((cid, g))):
            if who:
                parts[who].append((cid, g))
    planned = [g for g in sorted(parts) if len({at[cid] for cid, _ in parts[g]}) > 1]
    if not planned:
        return {}
    for mixed_days in (False, True):
        found = _solve(problem, dom, at, lessons, parts, planned, settings, mixed_days)
        if found is not None:
            break
    else:
        log("  Lịch cơ sở: không lập được, xếp như thường")
        return {}
    out: dict[str, dict[int, int]] = {}
    mixed = 0
    for g in planned:
        heavy = max(sorted({at[cid] for cid, _ in parts[g]}),
                    key=lambda c: sum(lessons[p] for p in parts[g] if at[p[0]] == c))
        for d in sorted(config.DAY_SESSIONS):
            chosen = found[g, d]
            if len(chosen) > 1:  # vẫn phải dạy hai cơ sở ngày này: không giới hạn
                mixed += 1
                continue
            out.setdefault(g, {})[d] = chosen[0] if chosen else heavy
    log(f"  Lịch cơ sở: {len(planned)} GV dạy ở nhiều cơ sở, mỗi ngày một cơ sở"
        + (f" (trừ {mixed} ngày không tránh được)" if mixed else ""))
    return out


def _solve(problem, dom, at, lessons, parts, planned, settings, mixed_days: bool):
    """(GV, ngày) -> các cơ sở người đó dạy ngày đó; None: không lập được. mixed_days False: mỗi ngày một cơ sở là
    bắt buộc, tìm nghiệm đầu tiên; True: ít ngày hai cơ sở nhất."""
    from .solver import _configure
    days = sorted(config.DAY_SESSIONS)
    m = cp_model.CpModel()
    per_day = {(cid, d): sum(1 for s in dom[cid] if s[0] == d) for cid in dom for d in days}
    n: dict[tuple[int, str, int], cp_model.IntVar] = {}
    for (cid, g), k in lessons.items():
        for d in days:
            n[cid, g, d] = m.NewIntVar(0, min(k, per_day[cid, d]), f"n_{cid}_{g}_{d}")
        m.Add(sum(n[cid, g, d] for d in days) == k)
    by_course: dict[int, list[str]] = defaultdict(list)
    for cid, g in lessons:
        by_course[cid].append(g)
    for cid, gs in by_course.items():
        for d in days:
            if len(gs) > 1:
                m.Add(sum(n[cid, g, d] for g in gs) <= per_day[cid, d])
    # Lớp: mỗi ngày không quá số giờ học của ngày đó (lớp theo của nhóm ghép lớp học cùng giờ với lớp chính).
    day_slots = {d: sum(1 for s in problem.slots if s[0] == d) for d in days}
    of_class: dict[str, list[int]] = defaultdict(list)
    for c in problem.courses:
        if (c.class_name, c.subject) not in problem.link_extra:
            of_class[c.class_name].append(c.lead if c.lead is not None else c.id)
    for cls, cids in sorted(of_class.items()):
        for d in days:
            m.Add(sum(n[cid, g, d] for cid in cids for g in by_course.get(cid, ())) <= day_slots[d])
    # GV dạy ở nhiều cơ sở: mỗi ngày không quá số giờ dạy được; mỗi ngày một cơ sở.
    leave = config.on("buoi_nghi")
    sess = {(d, p): s.name for d, ss in config.DAY_SESSIONS.items() for s in ss for p in s.periods}
    y: dict[tuple[str, int], dict[int, cp_model.IntVar]] = {}
    switches = []
    for g in planned:
        t = problem.teachers[g]
        mine = parts[g]
        for d in days:
            free = {s for cid, _ in mine for s in dom[cid] if s[0] == d}
            if leave:
                free = {s for s in free if (d, sess[s]) not in t.off_sessions}
            m.Add(sum(n[cid, h, d] for cid, h in mine) <= len(free))
            here = y[g, d] = {c: m.NewBoolVar(f"y_{g}_{d}_{c}") for c in sorted({at[cid] for cid, _ in mine})}
            for cid, h in mine:
                m.Add(n[cid, h, d] <= per_day[cid, d] * here[at[cid]])
            if mixed_days:
                switch = m.NewBoolVar(f"doi_{g}_{d}")
                m.Add(sum(here.values()) <= 1 + switch)
                switches.append(switch)
            else:
                m.AddAtMostOne(here.values())
    solver = cp_model.CpSolver()
    _configure(solver, settings, SECONDS)
    if mixed_days:
        m.Minimize(sum(switches))
    else:
        solver.parameters.stop_after_first_solution = True
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return {(g, d): [c for c, v in here.items() if solver.Value(v)] for (g, d), here in y.items()}
