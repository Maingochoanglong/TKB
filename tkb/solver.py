"""Mô hình CP-SAT: phân tiết cho GV và xếp tiết vào khung giờ.

Quy trình:
1. Phân công (chưa xếp giờ): tìm số tiết mỗi GV dạy cho từng lớp-môn sao cho số tiết giao
   cho GV bổ sung ít nhất, rồi số GV bổ sung ít nhất. Đây là cận dưới của bài toán đầy đủ.
2. Xếp giờ với phân công cố định ở bước 1 (nhanh). Nếu xếp được thì nghiệm đạt đúng cận dưới.
3. Nếu bước 2 không xếp được: giải mô hình tích hợp (vừa chọn GV vừa xếp giờ), có dự phòng
   thêm GV bổ sung.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from . import config
from .allocation import Course, Problem, build_problem
from .staff import Teacher


class SolveError(RuntimeError):
    pass


@dataclass
class Lesson:
    class_name: str
    day: int
    period: int
    subject: str
    teacher: str
    course_id: int


@dataclass
class Solution:
    problem: Problem
    status: str
    lessons: list[Lesson]
    objective: float
    best_bound: float
    wall_time: float
    stage: str
    notes: list[str] = field(default_factory=list)

    def teacher_load(self) -> dict[str, int]:
        load = {t: 0 for t in self.problem.teachers}
        for les in self.lessons:
            load[les.teacher] += 1
        return load

    def used_supplements(self) -> list[Teacher]:
        load = self.teacher_load()
        return [t for t in self.problem.teachers.values() if t.supplementary and load[t.title] > 0]


# --------------------------------------------------------------------------
# Tiện ích khung giờ
# --------------------------------------------------------------------------
def session_of() -> dict[tuple[int, int], config.Session]:
    return {(d, p): s for d, sessions in config.DAY_SESSIONS.items() for s in sessions for p in s.periods}


def distance_to_session_end(slot: tuple[int, int]) -> int:
    return session_of()[slot].periods[-1] - slot[1]


def day_targets(total: int, slots: list[tuple[int, int]]) -> dict[int, int]:
    """Chia `total` tiết cho các ngày theo tỷ lệ số slot (phương pháp phần dư lớn nhất)."""
    per_day: dict[int, int] = {}
    for d, _ in slots:
        per_day[d] = per_day.get(d, 0) + 1
    quotas = {d: total * c / len(slots) for d, c in per_day.items()}
    target = {d: math.floor(q) for d, q in quotas.items()}
    rest = total - sum(target.values())
    for d in sorted(quotas, key=lambda d: (-(quotas[d] - target[d]), d))[:rest]:
        target[d] += 1
    return target


def allowed_slots(course: Course, problem: Problem) -> list[tuple[int, int]]:
    if course.fixed_slots:
        missing = [s for s in course.fixed_slots if s not in problem.slots]
        if missing:
            raise SolveError(f"Slot cố định {missing} của {course.subject} không có trong khung giờ")
        return list(course.fixed_slots)
    # Slot đã cố định cho môn khác của lớp (HĐTN) thì không xếp môn này.
    taken = {s for c in problem.class_courses(course.class_name) if c.id != course.id for s in c.fixed_slots}
    result = []
    for s in problem.slots:
        if s in taken:
            continue
        if course.allowed_days is not None and s[0] not in course.allowed_days:
            continue
        if course.subject == config.HDTN and s in config.HDTN_FIXED_SLOTS:
            continue
        if not course.homeroom and s[1] in config.HOMEROOM_PERIODS:
            continue
        result.append(s)
    if len(result) < course.lessons:
        raise SolveError(f"Lớp {course.class_name}: môn {course.subject} cần {course.lessons} tiết "
                         f"nhưng chỉ có {len(result)} slot hợp lệ")
    return result


def _configure(solver: cp_model.CpSolver, settings: config.Settings, seconds: float) -> None:
    """Đặt tham số CP-SAT.

    Chế độ tái lập (settings.reproducible): các luồng chạy xen kẽ theo thứ tự cố định và dừng theo
    "thời gian tất định" (đếm khối lượng tính toán, không phụ thuộc máy nhanh/chậm), nên cùng dữ
    liệu + cùng phiên bản OR-Tools + cùng số luồng thì lần nào cũng ra đúng một kết quả.
    """
    p = solver.parameters
    p.num_workers = settings.workers
    p.random_seed = settings.seed
    if settings.reproducible:
        p.interleave_search = True
        p.max_deterministic_time = seconds * settings.deterministic_per_second
        p.max_time_in_seconds = seconds * settings.safety_factor  # chỉ để chặn treo
    else:
        p.max_time_in_seconds = seconds


# --------------------------------------------------------------------------
# Phần chung: số tiết mỗi GV dạy cho mỗi course, tải tuần, GV bổ sung
# --------------------------------------------------------------------------
class _Allocation:
    """a[k,g] = số tiết GV g dạy course k; used[k,g] = GV g có dạy course k."""

    def __init__(self, m: cp_model.CpModel, problem: Problem, w: config.Weights,
                 fixed: dict[tuple[int, str], int] | None = None):
        self.m = m
        self.problem = problem
        self.a: dict[tuple[int, str], cp_model.LinearExprT] = {}
        self.used: dict[tuple[int, str], cp_model.LinearExprT] = {}
        self.teachers_of: dict[int, list[str]] = {}
        main: list = []  # số tiết/GV bổ sung
        secondary: list = []  # chia môn, bộ môn dạy thay, cân bằng tải
        load_terms: dict[str, list] = {t: [] for t in problem.teachers}
        for c in problem.courses:
            if fixed is not None:
                cand = [g for g in c.teachers if fixed.get((c.id, g), 0) > 0]
                if sum(fixed.get((c.id, g), 0) for g in cand) != c.lessons:
                    raise SolveError(f"Phân công không khớp số tiết: lớp {c.class_name} môn {c.subject}")
            else:
                cand = list(c.teachers)
            self.teachers_of[c.id] = cand
            if len(cand) == 1 or fixed is not None:
                for g in cand:
                    n = c.lessons if len(cand) == 1 else fixed[c.id, g]
                    self.a[c.id, g] = n
                    self.used[c.id, g] = 1
                    load_terms[g].append(n)
                continue
            us = []
            for g in cand:
                a = m.NewIntVar(0, c.lessons, f"a_{c.id}_{g}")
                u = m.NewBoolVar(f"u_{c.id}_{g}")
                m.Add(a <= c.lessons * u)
                m.Add(a >= u)
                self.a[c.id, g] = a
                self.used[c.id, g] = u
                us.append(u)
                load_terms[g].append(a)
            m.Add(sum(self.a[c.id, g] for g in cand) == c.lessons)
            secondary.append(w.course_split * (sum(us) - 1))

        self.load: dict[str, cp_model.IntVar] = {}
        self.hired: dict[str, cp_model.IntVar] = {}
        for title, t in problem.teachers.items():
            load = m.NewIntVar(0, t.max_lessons, f"load_{title}")
            m.Add(load == sum(load_terms[title]))
            self.load[title] = load
            if title in problem.manager_load:
                m.Add(load == problem.manager_load[title])
            if t.supplementary:
                h = m.NewBoolVar(f"hired_{title}")
                m.Add(load <= t.max_lessons * h)
                m.Add(load >= h)
                self.hired[title] = h
                main.append(w.supplement_lesson * load + w.supplement_teacher * h)
                if t.role in config.SPECIALIST_ROLES:
                    main.append(w.specialist_supplement * h)
        # Phá đối xứng giữa các GV bổ sung cùng chức vụ: số thứ tự nhỏ dạy nhiều hơn.
        for titles in problem.supplement_roles.values():
            for a, b in zip(titles, titles[1:]):
                m.Add(self.load[a] >= self.load[b])
                m.AddImplication(self.hired[b], self.hired[a])
            # Dồn tiết cho người bổ sung đầu trước (đủ định mức rồi mới sang người sau).
            for i, t in enumerate(titles):
                secondary.append(w.supplement_order * i * self.load[t])

        specialist = set(config.SPECIALIST_ROLES.values())
        for (cid, g), a in self.a.items():
            c = problem.courses[cid]
            if c.subject in specialist and problem.teachers[g].role not in config.SPECIALIST_ROLES:
                secondary.append(w.general_on_specialist * a)

        # Cân bằng phần định mức chưa dùng giữa các GV cùng chức vụ.
        by_role: dict[str, list[Teacher]] = {}
        for t in problem.teachers.values():
            if not t.supplementary and not t.class_name and t.title not in problem.manager_load:
                by_role.setdefault(t.role, []).append(t)
        for role, members in by_role.items():
            if len(members) < 2:
                continue
            worst = m.NewIntVar(0, max(t.max_lessons for t in members), f"spare_{role}")
            for t in members:
                m.Add(worst >= t.max_lessons - self.load[t.title])
            secondary.append(w.load_balance * worst)
        if fixed is None:
            self._slot_capacity()
        self.main = main
        self.secondary = secondary
        self.objective = main + secondary

    def _slot_capacity(self) -> None:
        """GV không dạy 2 lớp cùng lúc: các tiết có miền slot nằm trong D chiếm tối đa |D| slot.

        Giúp bước phân công biết trước GV nào không đủ slot trống (vd tiết 1 đã dành cho GVCN).
        """
        problem = self.problem
        dom = {c.id: frozenset(allowed_slots(c, problem)) for c in problem.courses}
        by_teacher: dict[str, list[int]] = {}
        for cid, g in self.a:
            by_teacher.setdefault(g, []).append(cid)
        for g, cids in by_teacher.items():
            groups = {dom[cid] for cid in cids}
            groups.add(frozenset().union(*groups))
            for d in groups:
                terms = [self.a[cid, g] for cid in cids if dom[cid] <= d]
                if any(not isinstance(t, int) for t in terms):
                    self.m.Add(sum(terms) <= len(d))

    def supplement_lessons(self):
        return sum(self.load[t] for t in self.hired)


# --------------------------------------------------------------------------
# Bước 1: phân công (chưa xếp giờ)
# --------------------------------------------------------------------------
@dataclass
class Assignment:
    lessons: dict[tuple[int, str], int]  # (course, GV) -> số tiết
    counts: dict[str, int]  # chức vụ -> số GV bổ sung cần
    supplement_lessons: int
    optimal: bool


def assign(problem: Problem, settings: config.Settings) -> Assignment:
    """Tối ưu theo thứ tự: (1) tiết/GV bổ sung, rồi (2) chia môn, dạy thay, cân bằng tải."""
    m = cp_model.CpModel()
    alloc = _Allocation(m, problem, settings.weights)
    solver = cp_model.CpSolver()
    _configure(solver, settings, max(10.0, settings.time_limit / 8))

    main = sum(alloc.main)
    m.Minimize(main)
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SolveError("Không phân công được GV ngay cả khi chưa xếp giờ (kiểm tra quyền dạy/định mức)")
    optimal = status == cp_model.OPTIMAL
    best_main = int(solver.ObjectiveValue())

    all_vars = [v for v in list(alloc.a.values()) + list(alloc.used.values()) + list(alloc.load.values())
                if not isinstance(v, int)]
    first = {v.Index(): solver.Value(v) for v in all_vars}
    m.Add(main <= best_main)
    m.Minimize(sum(alloc.secondary))
    m.ClearHints()
    for v in all_vars:
        m.AddHint(v, first[v.Index()])
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SolveError("Lỗi nội bộ khi tối ưu phân công bước 2")

    lessons = {key: int(solver.Value(v)) for key, v in alloc.a.items()}
    counts = {role: sum(1 for t in titles if solver.Value(alloc.hired[t]))
              for role, titles in problem.supplement_roles.items()}
    return Assignment(lessons={k: v for k, v in lessons.items() if v > 0}, counts=counts,
                      supplement_lessons=int(solver.Value(alloc.supplement_lessons())),
                      optimal=optimal)


# --------------------------------------------------------------------------
# Bước 2/3: xếp giờ
# --------------------------------------------------------------------------
def timetable(problem: Problem, settings: config.Settings,
              fixed: dict[tuple[int, str], int] | None = None,
              hint: dict[tuple[int, str], int] | None = None) -> Solution | None:
    w = settings.weights
    m = cp_model.CpModel()
    slots = problem.slots
    alloc = _Allocation(m, problem, w, fixed)
    objective = list(alloc.objective)

    x: dict[tuple[int, tuple[int, int]], cp_model.IntVar] = {}
    dom: dict[int, list[tuple[int, int]]] = {}
    for c in problem.courses:
        dom[c.id] = allowed_slots(c, problem)
        vs = []
        for s in dom[c.id]:
            v = m.NewBoolVar(f"x_{c.id}_{s[0]}_{s[1]}")
            x[c.id, s] = v
            vs.append(v)
        if c.fixed_slots:
            for v in vs:
                m.Add(v == 1)
        else:
            m.Add(sum(vs) == c.lessons)

    # Mỗi lớp mỗi slot đúng 1 tiết (hoặc tối đa 1 nếu chương trình ít hơn số slot).
    for cls in problem.classes:
        courses = problem.class_courses(cls)
        full = sum(c.lessons for c in courses) == len(slots)
        for s in slots:
            vs = [x[c.id, s] for c in courses if (c.id, s) in x]
            m.Add(sum(vs) == 1) if full else m.Add(sum(vs) <= 1)

    # GV dạy course tại slot nào.
    occ_terms: dict[tuple[str, tuple[int, int]], list] = {}
    z: dict[tuple[int, str, tuple[int, int]], cp_model.IntVar] = {}
    for c in problem.courses:
        cand = alloc.teachers_of[c.id]
        if len(cand) == 1:
            for s in dom[c.id]:
                occ_terms.setdefault((cand[0], s), []).append(x[c.id, s])
            continue
        for s in dom[c.id]:
            zs = []
            for g in cand:
                v = m.NewBoolVar(f"z_{c.id}_{g}_{s[0]}_{s[1]}")
                z[c.id, g, s] = v
                zs.append(v)
                occ_terms.setdefault((g, s), []).append(v)
            m.Add(sum(zs) == x[c.id, s])
        for g in cand:
            m.Add(sum(z[c.id, g, s] for s in dom[c.id]) == alloc.a[c.id, g])

    for terms in occ_terms.values():
        if len(terms) > 1:
            m.Add(sum(terms) <= 1)

    # Luật bảo vệ học sinh: số tiết tối đa của một số môn trong mỗi buổi.
    if settings.student_rules:
        for cls in problem.classes:
            courses = problem.class_courses(cls)
            for d, sessions in config.DAY_SESSIONS.items():
                for session in sessions:
                    for group, limit in config.SESSION_SUBJECT_LIMITS:
                        vs = [x[c.id, (d, p)] for c in courses if c.subject in group
                              for p in session.periods if (c.id, (d, p)) in x]
                        if len(vs) > limit:
                            m.Add(sum(vs) <= limit)

    # HĐTN linh hoạt: càng gần cuối buổi càng tốt.
    for c in problem.courses:
        if c.flex_hdtn:
            objective.append(sum(w.hdtn_flex_distance * distance_to_session_end(s) * x[c.id, s]
                                 for s in dom[c.id] if distance_to_session_end(s) > 0))

    # Hạn chế môn nặng ở tiết cuối ngày.
    for c in problem.courses:
        if c.subject in config.HEAVY_SUBJECTS:
            objective.extend(w.heavy_late * x[c.id, s] for s in dom[c.id]
                             if s[1] in config.HEAVY_LATE_PERIODS)

    # Tải ngày của GV: phạt vượt mức mong muốn và vượt buffer (+1).
    days = sorted(config.DAY_SESSIONS)
    for title, t in problem.teachers.items():
        target = day_targets(t.max_lessons, slots)
        for d in days:
            terms = [v for s in slots if s[0] == d for v in occ_terms.get((title, s), [])]
            if len(terms) <= target[d]:
                continue
            day_load = sum(terms)
            over1 = m.NewIntVar(0, len(terms), f"over1_{title}_{d}")
            over2 = m.NewIntVar(0, len(terms), f"over2_{title}_{d}")
            m.Add(over1 >= day_load - target[d])
            m.Add(over2 >= day_load - target[d] - 1)
            objective.append(w.day_over_preferred * over1 + w.day_over_buffer * over2)

    # Rải đều môn trong tuần theo từng lớp.
    for cls in problem.classes:
        by_subject: dict[str, list[Course]] = {}
        for c in problem.class_courses(cls):
            if c.subject != config.HDTN:
                by_subject.setdefault(c.subject, []).append(c)
        for subject, courses in by_subject.items():
            cap = math.ceil(sum(c.lessons for c in courses) / len(days))
            for d in days:
                vs = [x[c.id, s] for c in courses for s in dom[c.id] if s[0] == d]
                if len(vs) <= cap:
                    continue
                ex = m.NewIntVar(0, len(vs), f"spread_{cls}_{subject}_{d}")
                m.Add(ex >= sum(vs) - cap)
                objective.append(w.subject_spread * ex)

    # Tiết trống giữa buổi của GV không chủ nhiệm.
    for title, t in problem.teachers.items():
        if t.class_name:
            continue
        for d, sessions in config.DAY_SESSIONS.items():
            for session in sessions:
                ps = session.periods
                if len(ps) < 3 or not any((title, (d, p)) in occ_terms for p in ps):
                    continue
                o = []
                for p in ps:
                    terms = occ_terms.get((title, (d, p)), [])
                    v = m.NewBoolVar(f"occ_{title}_{d}_{p}")
                    m.Add(v == sum(terms)) if terms else m.Add(v == 0)
                    o.append(v)
                started = [o[0]]
                for i in range(1, len(ps)):
                    a = m.NewBoolVar("")
                    m.AddMaxEquality(a, [started[-1], o[i]])
                    started.append(a)
                later = [None] * len(ps)
                later[-1] = o[-1]
                for i in range(len(ps) - 2, -1, -1):
                    b = m.NewBoolVar("")
                    m.AddMaxEquality(b, [later[i + 1], o[i]])
                    later[i] = b
                for i in range(1, len(ps) - 1):
                    gap = m.NewBoolVar(f"gap_{title}_{d}_{ps[i]}")
                    m.Add(gap >= started[i - 1] + later[i + 1] - o[i] - 1)
                    objective.append(w.teacher_gap * gap)

    m.Minimize(sum(objective))

    if hint and fixed is None:
        for (cid, g), a in alloc.a.items():
            if not isinstance(a, int):
                m.AddHint(a, hint.get((cid, g), 0))
                m.AddHint(alloc.used[cid, g], 1 if hint.get((cid, g), 0) > 0 else 0)

    solver = cp_model.CpSolver()
    _configure(solver, settings, settings.time_limit)
    start = time.time()
    status = solver.Solve(m)
    wall = time.time() - start
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    lessons: list[Lesson] = []
    for c in problem.courses:
        cand = alloc.teachers_of[c.id]
        for s in dom[c.id]:
            if not solver.Value(x[c.id, s]):
                continue
            if len(cand) == 1:
                g = cand[0]
            else:
                g = next(t for t in cand if solver.Value(z[c.id, t, s]))
            lessons.append(Lesson(c.class_name, s[0], s[1], c.subject, g, c.id))
    return Solution(problem=problem, status=solver.StatusName(status), lessons=lessons,
                    objective=solver.ObjectiveValue(), best_bound=solver.BestObjectiveBound(),
                    wall_time=wall, stage="phân công cố định" if fixed is not None else "mô hình tích hợp")


def solve(staff: list[Teacher], curriculum: dict[int, dict[str, int]] | None,
          settings: config.Settings, log=print) -> Solution:
    """Toàn bộ quy trình: phân công → xếp giờ với phân công cố định → (dự phòng) mô hình tích hợp."""
    base = build_problem(staff, curriculum)
    for msg in base.warnings:
        log(f"Cảnh báo: {msg}")
    log("Bước 1/2: phân công giáo viên...")
    plan = assign(base, settings)
    need = {r: c for r, c in plan.counts.items() if c}
    log(f"  Cần bổ sung: {need or 'không'}; {plan.supplement_lessons} tiết cho GV bổ sung"
        f"{' (tối ưu)' if plan.optimal else ' (chưa chứng minh tối ưu)'}")

    problem = build_problem(staff, curriculum, plan.counts)
    fixed = {k: v for k, v in plan.lessons.items() if k[1] in problem.teachers}
    mode = "chế độ tái lập" if settings.reproducible else "giới hạn giây thực"
    log(f"Bước 2/2: xếp giờ (~{settings.time_limit:.0f}s, {mode})...")
    solution = timetable(problem, settings, fixed=fixed)
    if solution is not None:
        solution.notes.append("Số tiết thiếu và số GV bổ sung là nhỏ nhất (đã chứng minh tối ưu)"
                              if plan.optimal else
                              "Số tiết thiếu/số GV bổ sung chưa được chứng minh là nhỏ nhất")
        return solution

    for slack in (1, 3):
        log(f"  Không xếp được với phân công cố định; thử mô hình tích hợp (dự phòng {slack} GV/chức vụ)...")
        planned = {role: plan.counts.get(role, 0) + slack for role in base.supplement_roles}
        problem = build_problem(staff, curriculum, planned)
        solution = timetable(problem, settings, hint=plan.lessons)
        if solution is not None:
            solution.notes.append(f"Mô hình tích hợp (dự phòng {slack} GV bổ sung/chức vụ)")
            return solution
    raise SolveError("Không tìm được TKB hợp lệ. Thử tăng --time-limit hoặc tắt luật học sinh "
                     "(--no-student-rules) để kiểm tra nguyên nhân.")
