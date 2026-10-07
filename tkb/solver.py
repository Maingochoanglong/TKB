"""Xếp giờ bằng CP-SAT và toàn bộ quy trình giải.

Quy trình (`solve`):
1. Dự toán và phân công (tkb/phan_cong.py, không dùng CP-SAT): ai dạy lớp nào, môn nào, bao nhiêu tiết; mỗi
   GVCN/bộ môn bù bao nhiêu tiết; còn thiếu bao nhiêu tiết.
2. Tiết bù (và tiết thiếu ở chế độ tuyển) giao cho "người tuyển mới". Xếp giờ MỘT lần với phân công cố định
   đó (tkb/lns.py: CP-SAT khởi đầu rồi xếp lại từng vùng). Chế độ tuyển: người mới dạy các ô đó. Chế độ bù:
   trả các ô đó về đúng người bù. Hai chế độ cùng vị trí môn trong TKB.
3. Chế độ tuyển mà không xếp được với phân công cố định: mô hình tích hợp (vừa chọn GV vừa xếp giờ), có dự
   phòng thêm GV bổ sung.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, replace

from ortools.sat.python import cp_model

from . import config
from .allocation import (Course, Problem, build_problem, keep_cost, overtime_cost, paired_groups, previous_cost,
                         roles_for_subject, subject_group)
from .bo_ghep import assign_cost
from .phan_cong import PhanCong, phan_cong, tach_tiet_bu
from .staff import InputError, Teacher, grade_of, normalize


class SolveError(RuntimeError):
    pass


# Các luật bắt buộc đang được nới để chẩn đoán vì sao không xếp được (tkb/chan_doan.py). Luôn rỗng khi xếp thật:
# rỗng thì mô hình dựng ra y như cũ, không đổi mã kết quả.
# "tang_cuong": tiết tăng cường sau tiết chính; "lien_nhau": các tiết cùng môn trong buổi liền nhau; "lien_tiet":
# hai tiết liền cùng nhóm môn do một người dạy; "gvcn_truoc": tiết đầu tuần của GVCN; "co_so": mỗi buổi một cơ sở.
RELAXED: frozenset[str] = frozenset()


def on(key: str) -> bool:
    """Luật có sẵn `key` có hiệu lực: có dòng ở sheet LUẬT (config.on) và không đang nới để chẩn đoán."""
    return key not in RELAXED and config.on(key)


def ortools_version() -> str:
    import ortools
    return ortools.__version__


@dataclass
class Lesson:
    class_name: str
    day: int
    period: int
    subject: str
    teacher: str
    course_id: int
    overtime: bool = False  # tiết dạy bù (vượt định mức) của người bù, chỉ có ở chế độ bù giờ
    locked: bool = False  # ô khóa của TKB đã xếp (config.SAVED_LOCKED): xếp lại vẫn giữ nguyên; không vào mã kết quả


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

    def fingerprint(self) -> str:
        """Mã kết quả: băm toàn bộ TKB (lớp, ngày, tiết, môn, GV). Hai lần chạy cùng mã là cùng TKB."""
        rows = sorted((l.class_name, l.day, l.period, l.subject, l.teacher) for l in self.lessons)
        digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest().upper()
        return "-".join(digest[i:i + 4] for i in range(0, 12, 4))

    def overtime(self) -> dict[str, int]:
        """GV -> số tiết dạy bù (vượt định mức)."""
        load = self.teacher_load()
        teachers = self.problem.teachers
        return {g: load[g] - teachers[g].max_lessons for g in self.problem.overtime
                if load[g] > teachers[g].max_lessons}


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
        if course.subject == config.HDTN and s in config.HDTN_FIXED_SLOTS and on("hdtn_co_dinh"):
            continue
        if not course.homeroom and s[1] in config.HOMEROOM_PERIODS and on("tiet_gvcn"):
            continue
        result.append(s)
    if config.CUSTOM_RULES:  # luật riêng bắt buộc về vị trí (tkb/bo_ghep.py)
        from .luat_rieng import banned
        bad = banned(course.subject, course.grade, course.class_name, problem.curriculum)
        result = [s for s in result if s not in bad]
    if len(result) < course.lessons:
        raise SolveError(f"Lớp {course.class_name}: môn {course.subject} cần {course.lessons} tiết "
                         f"nhưng chỉ có {len(result)} slot hợp lệ")
    return result


def _configure(solver: cp_model.CpSolver, settings: config.Settings, seconds: float | None) -> None:
    """Đặt tham số CP-SAT. seconds = None: không giới hạn, chạy đến khi chứng minh tối ưu.

    Chế độ tái lập (settings.reproducible): các luồng chạy xen kẽ theo thứ tự cố định và dừng theo
    "thời gian tất định" (đếm khối lượng tính toán, không phụ thuộc máy nhanh/chậm, số nhân CPU hay máy
    đang bận), nên cùng dữ liệu + cùng phiên bản OR-Tools + cùng số luồng thì ra cùng kết quả trên các máy
    cùng hệ điều hành (Windows và Linux ra TKB khác nhau). Không đặt giới hạn giây thực: máy chậm chỉ chạy
    lâu hơn chứ không dừng sớm ra kết quả khác.

    Tắt việc các luồng chia sẻ mệnh đề học được và cận ở mức gốc: dù có interleave_search, phần chia sẻ này
    của OR-Tools 9.15 không tất định. Đo trên dữ liệu mẫu, cùng một mô hình giải 6 lần ra 3 TKB khác nhau
    (lệch từ khoảng 60–120 đơn vị tính toán trở đi); tắt đi thì 8/8 lần giống hệt, chất lượng không giảm.
    Bấm Ctrl+C khi đang giải thì bộ giải dừng và giữ nghiệm tốt nhất đã tìm được.
    """
    p = solver.parameters
    p.num_workers = settings.workers
    p.random_seed = settings.seed
    if settings.reproducible:
        p.interleave_search = True
        p.share_binary_clauses = False  # tắt luôn cả share_glue_clauses
        p.share_level_zero_bounds = False
    if seconds is None:
        return
    if settings.reproducible:
        p.max_deterministic_time = seconds * settings.deterministic_per_second
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
        self.w = w
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
            load = m.NewIntVar(0, t.max_lessons + problem.overtime.get(title, 0), f"load_{title}")
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
                if t.role in problem.specialists:
                    main.append(w.specialist_supplement * h)
        self.overtime = self._overtime(main, secondary)
        # Phá đối xứng giữa các GV bổ sung cùng chức vụ: số thứ tự nhỏ dạy nhiều hơn.
        for titles in problem.supplement_roles.values():
            for a, b in zip(titles, titles[1:]):
                m.Add(self.load[a] >= self.load[b])
                m.AddImplication(self.hired[b], self.hired[a])
            # Dồn tiết cho người bổ sung đầu trước (đủ định mức rồi mới sang người sau).
            for i, t in enumerate(titles):
                secondary.append(w.supplement_order * i * self.load[t])

        specialist = problem.specialist_subjects()
        for (cid, g), a in self.a.items():
            c = problem.courses[cid]
            if c.subject in specialist and problem.teachers[g].role not in problem.specialists:
                secondary.append(w.general_on_specialist * a)
            if not isinstance(a, int) and (keep := keep_cost(problem.teachers[g], c.class_name, w)
                                           + previous_cost(problem.teachers[g], c, w)):
                secondary.append(keep * a)  # giữ khối, lớp (và người dạy khi xếp lại ít xáo trộn) của TKB cũ
            if config.CUSTOM_RULES and not isinstance(a, int) and \
                    (cost := assign_cost(problem.teachers[g], c, problem.curriculum, w)):
                secondary.append(cost * a)  # luật riêng ưu tiên "Người dạy" (tkb/bo_ghep.py)

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

    def _overtime(self, main: list, secondary: list) -> dict[str, cp_model.IntVar]:
        """Chế độ bù giờ: số tiết bù = tải vượt định mức; GVCN bù trước bộ môn."""
        problem, m, w = self.problem, self.m, self.w
        result: dict[str, cp_model.IntVar] = {}
        for title, extra in problem.overtime.items():
            t = problem.teachers[title]
            ot = m.NewIntVar(0, extra, f"ot_{title}")
            m.Add(ot >= self.load[title] - t.max_lessons)
            result[title] = ot
            main.append(overtime_cost(t, w) * ot)
            if extra > 1:
                second = m.NewIntVar(0, extra - 1, f"ot2_{title}")
                m.Add(second >= ot - 1)
                secondary.append(w.overtime_second * second)
        # GVCN bù môn ưu tiên của lớp trước, sau đó theo thứ tự bù của GVCN.
        order = {s: 0 for s in config.HOMEROOM_PRIORITY}
        order.update({s: i + 1 for i, s in enumerate(config.HOMEROOM_FILL_ORDER)})
        for (cid, g), a in self.a.items():
            c = problem.courses[cid]
            if not c.homeroom and problem.teachers[g].class_name and not isinstance(a, int):
                rank = order.get(c.subject, len(config.HOMEROOM_FILL_ORDER) + 1)
                if rank:
                    secondary.append(w.overtime_subject_order * rank * a)
        return result

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
            # Thứ tự cố định (không theo thứ tự lặp của set, có thể khác giữa các phiên bản Python).
            for d in sorted(groups, key=lambda s: (len(s), sorted(s))):
                terms = [self.a[cid, g] for cid in cids if dom[cid] <= d]
                if any(not isinstance(t, int) for t in terms):
                    self.m.Add(sum(terms) <= len(d))

    def supplement_lessons(self):
        return sum(self.load[t] for t in self.hired)


# --------------------------------------------------------------------------
# Xếp giờ
# --------------------------------------------------------------------------
@dataclass
class TimetableModel:
    """Mô hình xếp giờ đã dựng. x[course, slot]: course có tiết ở slot; z[course, GV, slot]: GV nào dạy tiết đó
    (chỉ có khi course có nhiều hơn 1 GV). allocation_cost: phần mục tiêu của phân công (hằng số khi phân công
    cố định), để tách ra chi phí của riêng việc xếp giờ."""
    problem: Problem
    model: cp_model.CpModel
    x: dict[tuple[int, tuple[int, int]], cp_model.IntVar]
    z: dict[tuple[int, str, tuple[int, int]], cp_model.IntVar]
    dom: dict[int, list[tuple[int, int]]]
    teachers_of: dict[int, list[str]]
    allocation_cost: list

    def lessons(self, value) -> list[Lesson]:
        """Các tiết của nghiệm; value(biến) -> giá trị (vd CpSolver.Value)."""
        out: list[Lesson] = []
        for c in self.problem.courses:
            cand = self.teachers_of[c.id]
            for s in self.dom[c.id]:
                if not value(self.x[c.id, s]):
                    continue
                g = cand[0] if len(cand) == 1 else next(t for t in cand if value(self.z[c.id, t, s]))
                out.append(Lesson(c.class_name, s[0], s[1], c.subject, g, c.id))
        return out


def timetable(problem: Problem, settings: config.Settings,
              fixed: dict[tuple[int, str], int] | None = None,
              hint: dict[tuple[int, str], int] | None = None, log=lambda *_: None,
              keep: Previous | None = None) -> Solution | None:
    """Xếp giờ. Phân công cố định: CP-SAT khởi đầu rồi xếp lại từng vùng (tkb/lns.py). Mô hình tích hợp (vừa
    phân công vừa xếp giờ, chỉ dùng dự phòng): một lần CP-SAT trong time_limit. keep: TKB cũ (xếp lại ít xáo
    trộn, _keep_previous)."""
    tm = build_timetable(problem, settings, fixed, hint, keep)
    if fixed is not None:
        from .lns import improve
        start = time.time()
        res = improve(tm, settings, log)
        if res is None:
            return None
        return Solution(problem=problem, status=res.status, lessons=tm.lessons(lambda v: res.values[v.Index()]),
                        objective=res.objective, best_bound=res.bound, wall_time=time.time() - start,
                        stage="phân công cố định, xếp lại từng vùng",
                        notes=[f"Xếp giờ: chi phí {' -> '.join(map(str, res.history))}; dừng: {res.stop}"])
    solver = cp_model.CpSolver()
    _configure(solver, settings, settings.time_limit)
    start = time.time()
    status = solver.Solve(tm.model)
    wall = time.time() - start
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return Solution(problem=problem, status=solver.StatusName(status), lessons=tm.lessons(solver.Value),
                    objective=solver.ObjectiveValue(), best_bound=solver.BestObjectiveBound(),
                    wall_time=wall, stage="phân công cố định" if fixed is not None else "mô hình tích hợp")


def _teacher_sessions(m: cp_model.CpModel, problem: Problem, occ_terms: dict, occ_campus: dict) -> None:
    """Luật cứng theo buổi của từng GV: buổi nghỉ (cột Buổi Nghỉ) và mỗi buổi chỉ dạy ở một cơ sở (cột Cơ sở 2).

    occ_terms[(GV, slot)]: các literal "GV dạy ở slot"; occ_campus[(GV, slot, lớp ở cơ sở 2?)]: như trên, tách
    theo cơ sở của lớp."""
    sess = session_of()
    sessions = [(d, s) for d, ss in config.DAY_SESSIONS.items() for s in ss]
    by_teacher: dict[str, dict[tuple[int, str], list]] = {}  # GV -> buổi -> literal
    for (g, s), terms in sorted(occ_terms.items()):
        by_teacher.setdefault(g, {}).setdefault((s[0], sess[s].name), []).extend(terms)
    for g in sorted(by_teacher):
        t, busy = problem.teachers[g], by_teacher[g]
        if not on("buoi_nghi"):
            continue
        for key in sorted(t.off_sessions):  # buổi nghỉ cố định
            for v in busy.get(key, []):
                m.Add(v == 0)
        if t.off_any:  # nghỉ thêm n buổi bất kỳ (chương trình chọn buổi): off[buổi] = buổi đó trống
            free = [(d, s.name) for d, s in sessions if (d, s.name) not in t.off_sessions]
            off = {}
            for key in free:
                off[key] = m.NewBoolVar(f"off_{g}_{key[0]}_{key[1]}")
                for v in busy.get(key, []):
                    m.AddImplication(off[key], v.Not())
            for name, n in t.off_any:
                pool = [off[k] for k in free if name is None or k[1] == name]
                need = sum(k for _, k in t.off_any) if name is None else n
                m.Add(sum(pool) >= need)
    # Mỗi buổi GV chỉ dạy ở một cơ sở: o2 = 1 là buổi đó ở cơ sở 2.
    for g in sorted(by_teacher) if on("co_so") else ():
        for d, session in sessions:
            lits = {at2: [v for p in session.periods for v in occ_campus.get((g, (d, p), at2), [])]
                    for at2 in (False, True)}
            if lits[False] and lits[True]:
                o2 = m.NewBoolVar(f"cs2_{g}_{d}_{session.name}")
                for v in lits[True]:
                    m.AddImplication(v, o2)
                for v in lits[False]:
                    m.AddImplication(v, o2.Not())


def _campus_day_switch(m: cp_model.CpModel, occ_campus: dict, weight: int) -> list:
    """Mục tiêu mềm: phạt `weight` mỗi (GV, ngày) dạy ở cả hai cơ sở (sáng một nơi, chiều nơi kia)."""
    if not weight:  # luật ưu tiên bị bỏ (sheet LUẬT)
        return []
    by_day: dict[tuple[str, int, bool], list] = {}  # (GV, ngày, lớp ở cơ sở 2?) -> literal
    for (g, s, at2), lits in sorted(occ_campus.items()):
        by_day.setdefault((g, s[0], at2), []).extend(lits)
    terms = []
    for g, d in sorted({(g, d) for g, d, _ in by_day}):
        one, two = by_day.get((g, d, False)), by_day.get((g, d, True))
        if not one or not two:
            continue
        u1, u2, both = (m.NewBoolVar(f"{k}_{g}_{d}") for k in ("cs1", "cs2", "hai_cs"))
        for v in one:
            m.AddImplication(v, u1)
        for v in two:
            m.AddImplication(v, u2)
        m.Add(both >= u1 + u2 - 1)
        terms.append(weight * both)
    return terms


def build_timetable(problem: Problem, settings: config.Settings,
                    fixed: dict[tuple[int, str], int] | None = None,
                    hint: dict[tuple[int, str], int] | None = None,
                    keep: Previous | None = None) -> TimetableModel:
    """Dựng mô hình CP-SAT xếp giờ: luật cứng + mục tiêu mềm (config.Weights); keep: TKB cũ để xếp lại ít xáo trộn
    (ô khóa cứng, mỗi ô đổi môn bị trừ điểm). Không có keep thì mô hình như cũ."""
    w = config.rule_weights(settings.weights)  # điểm ghi ở các dòng luật có sẵn ưu tiên (sheet LUẬT)
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
    occ_campus: dict[tuple[str, tuple[int, int], bool], list] = {}  # (GV, slot, lớp ở cơ sở 2?) -> literal
    z: dict[tuple[int, str, tuple[int, int]], cp_model.IntVar] = {}
    for c in problem.courses:
        cand = alloc.teachers_of[c.id]
        at2 = c.class_name in problem.campus2
        if len(cand) == 1:
            for s in dom[c.id]:
                occ_terms.setdefault((cand[0], s), []).append(x[c.id, s])
                occ_campus.setdefault((cand[0], s, at2), []).append(x[c.id, s])
            continue
        for s in dom[c.id]:
            zs = []
            for g in cand:
                v = m.NewBoolVar(f"z_{c.id}_{g}_{s[0]}_{s[1]}")
                z[c.id, g, s] = v
                zs.append(v)
                occ_terms.setdefault((g, s), []).append(v)
                occ_campus.setdefault((g, s, at2), []).append(v)
            m.Add(sum(zs) == x[c.id, s])
        for g in cand:
            m.Add(sum(z[c.id, g, s] for s in dom[c.id]) == alloc.a[c.id, g])

    for terms in occ_terms.values():
        if len(terms) > 1:
            m.Add(sum(terms) <= 1)
    _teacher_sessions(m, problem, occ_terms, occ_campus)
    objective.extend(_campus_day_switch(m, occ_campus, w.campus_day_switch))

    # Biến "GV g dạy nhóm môn của lớp tại slot s" cho các luật về người dạy.
    teach: dict[tuple[str, str], dict[str, dict[tuple[int, int], list]]] = {}
    for c in problem.courses:
        cand = alloc.teachers_of[c.id]
        for s in dom[c.id]:
            for g in cand:
                v = x[c.id, s] if len(cand) == 1 else z[c.id, g, s]
                teach.setdefault((c.class_name, subject_group(c.subject)), {}).setdefault(g, {}) \
                    .setdefault(s, []).append(v)
    sessions_all = [(d, session) for d, sessions in config.DAY_SESSIONS.items() for session in sessions]

    # Liên tiết: hai tiết liền nhau cùng lớp, cùng nhóm môn (vd TV và TV tăng cường) phải cùng người dạy.
    for by_g in teach.values():
        if len(by_g) < 2 or not on("lien_tiet"):
            continue
        gs = sorted(by_g)
        for d, session in sessions_all:
            for p1, p2 in zip(session.periods, session.periods[1:]):
                for g1 in gs:
                    for g2 in gs:
                        a, b = by_g[g1].get((d, p1)), by_g[g2].get((d, p2))
                        if g1 != g2 and a and b:
                            m.Add(sum(a) + sum(b) <= 1)

    # GVCN trước: nhóm môn ưu tiên của GVCN mà có người khác cùng dạy thì tiết đầu tuần là của GVCN, tiết của
    # người khác không đứng trước tiết GVCN đầu tiên.
    homeroom_of = {t.class_name: t.title for t in problem.teachers.values() if t.class_name}
    week = sorted(slots)
    for (cls, group), by_g in teach.items():
        cn = homeroom_of.get(cls)
        if group not in config.HOMEROOM_PRIORITY or cn not in by_g or len(by_g) < 2 or not on("gvcn_truoc"):
            continue
        for g in sorted(by_g):
            if g == cn:
                continue
            for i, s in enumerate(week):
                if s not in by_g[g]:
                    continue
                before = [v for s2 in week[:i] for v in by_g[cn].get(s2, [])]
                m.Add(sum(by_g[g][s]) <= sum(before)) if before else m.Add(sum(by_g[g][s]) == 0)

    # Luật bảo vệ học sinh: mỗi nhóm môn tối đa SESSION_GROUP_LIMIT tiết mỗi buổi; Toán mỗi ngày tối đa 1 tiết
    # (DAILY_LIMITS); nhóm môn ghép cặp (allocation.paired_groups) mỗi buổi 0 hoặc 2 tiết liền nhau; môn có từ 2
    # tiết trong một buổi thì các tiết phải liền nhau (không có mẫu "môn – môn khác – môn"); tiết tăng cường
    # sau tiết chính cùng nhóm trong ngày (config.SUBJECT_GROUPS).
    if settings.student_rules:
        n_days = len(config.DAY_SESSIONS)
        for cls in problem.classes:
            courses = problem.class_courses(cls)
            req = problem.curriculum[grade_of(cls)]
            pairs = paired_groups(req, grade_of(cls))
            by_subject: dict[str, list[Course]] = {}
            by_group: dict[str, list[Course]] = {}
            for c in courses:
                by_subject.setdefault(c.subject, []).append(c)
                by_group.setdefault(subject_group(c.subject), []).append(c)
            # Tiết tăng cường là tiết luyện bài vừa học: trong ngày phải có tiết chính cùng nhóm đứng trước và
            # không có tiết chính nào đứng sau (không cần liền, không cần cùng người dạy, không cần buổi chiều).
            for extra, main in config.SUBJECT_GROUPS.items() if on("tang_cuong") else ():
                for te in by_subject.get(extra, []):
                    for mc in by_subject.get(main, []):
                        for d, p in sorted(dom[te.id]):
                            v = x[te.id, (d, p)]
                            day_main = [(q, x[mc.id, (d, q)]) for session in config.DAY_SESSIONS[d]
                                        for q in session.periods if (mc.id, (d, q)) in x]
                            before = [u for q, u in day_main if q < p]
                            m.Add(v <= sum(before)) if before else m.Add(v == 0)
                            for q, u in day_main:
                                if q > p:
                                    m.Add(v + u <= 1)
            for d, sessions in config.DAY_SESSIONS.items():
                for subject, limit in config.DAILY_LIMITS.items():
                    if req.get(subject, 0) > n_days:
                        continue
                    vs = [x[c.id, (d, p)] for c in by_subject.get(subject, []) for session in sessions
                          for p in session.periods if (c.id, (d, p)) in x]
                    if len(vs) > limit:
                        m.Add(sum(vs) <= limit)
                for session in sessions:
                    ps = session.periods
                    for group, cs in by_group.items():
                        y = {p: [x[c.id, (d, p)] for c in cs if (c.id, (d, p)) in x] for p in ps}
                        vs = [v for p in ps for v in y[p]]
                        if len(vs) > config.SESSION_GROUP_LIMIT and on("nhom_buoi"):
                            m.Add(sum(vs) <= config.SESSION_GROUP_LIMIT)
                        if group in pairs and vs:
                            pair = m.NewBoolVar(f"pair_{cls}_{d}_{ps[0]}")
                            m.Add(sum(vs) == 2 * pair)
                            for i in range(len(ps)):
                                for k in range(i + 2, len(ps)):
                                    if y[ps[i]] and y[ps[k]]:
                                        m.Add(sum(y[ps[i]]) + sum(y[ps[k]]) <= 1)
                    for subject, cs in by_subject.items():
                        if sum(c.lessons for c in cs) < 2 or not on("lien_nhau"):
                            continue
                        y = {p: [x[c.id, (d, p)] for c in cs if (c.id, (d, p)) in x] for p in ps}
                        for i in range(len(ps)):
                            for k in range(i + 2, len(ps)):
                                if not y[ps[i]] or not y[ps[k]]:
                                    continue
                                for j in range(i + 1, k):
                                    m.Add(sum(y[ps[i]]) + sum(y[ps[k]]) - sum(y[ps[j]]) <= 1)

    # HĐTN linh hoạt: càng gần cuối buổi càng tốt.
    # Điểm 0: dòng luật ưu tiên tương ứng đã bỏ khỏi sheet LUẬT (các khối dưới đây bỏ qua luôn).
    for c in problem.courses:
        if c.flex_hdtn and w.hdtn_flex_distance:
            objective.append(sum(w.hdtn_flex_distance * distance_to_session_end(s) * x[c.id, s]
                                 for s in dom[c.id] if distance_to_session_end(s) > 0))

    # Hạn chế môn nặng ở tiết cuối ngày.
    for c in problem.courses:
        if c.subject in config.HEAVY_SUBJECTS and w.heavy_late:
            objective.extend(w.heavy_late * x[c.id, s] for s in dom[c.id]
                             if s[1] in config.HEAVY_LATE_PERIODS)

    # Buổi sáng dành cho TV, Toán.
    for c in problem.courses:
        if c.subject in config.MORNING_SUBJECTS and w.morning_core:
            objective.extend(w.morning_core * x[c.id, s] for s in dom[c.id] if s[1] not in config.MORNING.periods)

    # Tải ngày của GV: phạt vượt mức mong muốn và vượt buffer (+1).
    days = sorted(config.DAY_SESSIONS)
    for title, t in problem.teachers.items() if w.day_over_preferred or w.day_over_buffer else ():
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
            if not (w.core_spread if subject in config.MORNING_SUBJECTS else w.subject_spread):
                continue
            for d in days:
                vs = [x[c.id, s] for c in courses for s in dom[c.id] if s[0] == d]
                if len(vs) <= cap:
                    continue
                ex = m.NewIntVar(0, len(vs), f"spread_{cls}_{subject}_{d}")
                m.Add(ex >= sum(vs) - cap)
                weight = w.core_spread if subject in config.MORNING_SUBJECTS else w.subject_spread
                objective.append(weight * ex)

    # Tiết trống giữa buổi của GV không chủ nhiệm.
    for title, t in problem.teachers.items():
        if t.class_name or not w.teacher_gap:
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

    # Luật riêng của trường (sheet LUẬT RIÊNG); không có luật nào thì không thêm gì.
    if config.CUSTOM_RULES:
        from .luat_rieng import build
        objective.extend(build(m, problem, x, z, dom, alloc.teachers_of, w))
    if keep is not None:  # xếp lại ít xáo trộn: giữ TKB cũ
        objective.extend(_keep_previous(m, problem, x, z, alloc.teachers_of, keep, w))

    m.Minimize(sum(objective))

    if hint and fixed is None:
        for (cid, g), a in alloc.a.items():
            if not isinstance(a, int):
                m.AddHint(a, hint.get((cid, g), 0))
                m.AddHint(alloc.used[cid, g], 1 if hint.get((cid, g), 0) > 0 else 0)
    return TimetableModel(problem, m, x, z, dom, alloc.teachers_of, list(alloc.objective))


class ShortageError(SolveError):
    """Chế độ bù giờ: GVCN và bộ môn đã bù tối đa mà vẫn thiếu tiết (không tuyển thêm)."""

    def __init__(self, problem: Problem, plan: PhanCong):
        self.problem = problem
        self.plan = plan
        super().__init__(f"Chế độ bù giờ không đủ: GVCN và bộ môn đã bù tối đa +{problem.overtime_max} tiết/người, "
                         f"còn thiếu {plan.missing_total()} tiết")

    def rows(self) -> list[tuple[str, str, int, str]]:
        """(lớp, môn, số tiết thiếu, lý do) theo thứ tự lớp."""
        from .staff import class_sort_key
        out = []
        for cid, n in self.plan.missing.items():
            c = self.problem.courses[cid]
            general = config.ROLE_GENERAL in roles_for_subject(c.subject, self.problem.specialists)
            reason = (f"GVCN và bộ môn đã bù tối đa +{self.problem.overtime_max} tiết" if general
                      else "môn chuyên biệt: không ai được dạy bù")
            out.append((c.class_name, self.problem.subject_label(c.subject), n, reason))
        return sorted(out, key=lambda r: (class_sort_key(r[0]), r[1]))


def du_toan_lines(problem: Problem, plan: PhanCong) -> list[str]:
    """Dự toán in ra trước khi xếp giờ."""
    teachers = problem.teachers
    spec = problem.specialist_subjects()
    total = sum(sum(problem.curriculum[grade_of(cls)].values()) for cls in problem.classes)
    part = {"gvcn": 0, "spec": 0, "manager": 0, "general": 0, "general_spec": 0}
    for (cid, g), n in plan.lessons.items():
        t, c = teachers[g], problem.courses[cid]
        if t.class_name:
            part["gvcn"] += n if c.homeroom else 0
        elif g in problem.manager_load:
            part["manager"] += n
        elif t.role in problem.specialists:
            part["spec"] += n
        else:
            part["general"] += n
            part["general_spec"] += n if c.subject in spec else 0
    ot = plan.overtime
    ot_h = sum(n for g, n in ot.items() if teachers[g].class_name)
    cap_h = sum(n for g, n in plan.overtime_cap.items() if teachers[g].class_name)
    cap_g = sum(n for g, n in plan.overtime_cap.items() if not teachers[g].class_name)
    used = sum(ot.values())
    lines = [f"  Dự toán: cần {total} tiết = GVCN {part['gvcn']} + GV chuyên biệt {part['spec']} + quản lý "
             f"{part['manager']} + bộ môn {part['general'] - (used - ot_h)} (trong đó {part['general_spec']} tiết môn "
             f"chuyên biệt) + bù {used} + thiếu {plan.missing_total()}"]
    if problem.overtime:
        lines.append(f"  Bù: {used}/{cap_h + cap_g} tiết (GVCN {ot_h}/{cap_h}, bộ môn {used - ot_h}/{cap_g}), "
                     f"còn dư {cap_h + cap_g - used} tiết")
    return lines


def _hire_assignment(plan: PhanCong, work: Problem, split: dict[str, list[list[tuple[int, str, int]]]]
                     ) -> tuple[dict[tuple[int, str], int], dict[tuple[int, str], list[str]]]:
    """Phân công cố định khi tiết bù/tiết thiếu do người mới dạy; (course, người mới) -> người bù từng tiết."""
    fixed = dict(plan.lessons)
    owners: dict[tuple[int, str], list[str]] = {}
    for role, groups in split.items():
        for title, parts in zip(work.supplement_roles[role], groups):
            for cid, owner, n in parts:
                if owner:
                    fixed[cid, owner] -= n
                    if not fixed[cid, owner]:
                        del fixed[cid, owner]
                fixed[cid, title] = fixed.get((cid, title), 0) + n
                owners.setdefault((cid, title), []).extend([owner] * n)
    return fixed, owners


def _to_overtime(solution: Solution, problem: Problem, owners: dict[tuple[int, str], list[str]]) -> Solution:
    """TKB chế độ bù: các ô của người mới trả về đúng người bù (cùng vị trí môn)."""
    by_key: dict[tuple[int, str], list[Lesson]] = {}
    for les in solution.lessons:
        if (les.course_id, les.teacher) in owners:
            by_key.setdefault((les.course_id, les.teacher), []).append(les)
    teacher_of: dict[int, str] = {}
    for key, lessons in by_key.items():
        for les, owner in zip(sorted(lessons, key=lambda l: (l.day, l.period)), owners[key]):
            teacher_of[id(les)] = owner
    lessons = [replace(les, teacher=teacher_of[id(les)], overtime=True) if id(les) in teacher_of else les
               for les in solution.lessons]
    return replace(solution, problem=problem, lessons=lessons)


def reuse(staff: list[Teacher], curriculum: dict[int, dict[str, int]], settings: config.Settings,
          rows: list[tuple]) -> tuple[Solution | None, list[str]]:
    """Dùng lại TKB đã xếp (sheet config.SAVED_SHEET của file vào cập nhật, staff.read_saved_timetable) thay cho
    xếp lại: (lời giải, []) nếu TKB đó khớp file vào và đúng mọi luật cứng (checker), không thì (None, các lý do).

    Giáo viên khớp theo Mã GV (vd "Bộ Môn 5"), không theo tên: đổi tên người "chưa có" thành tên người mới tuyển thì
    TKB giữ nguyên, mã kết quả cũng giữ nguyên (mã băm theo chức vụ, không theo tên)."""
    from .checker import check  # checker nhập module này: nhập muộn để tránh vòng lặp
    overtime_max = settings.overtime_max if settings.mode == config.MODE_OVERTIME else 0
    problem = build_problem(staff, curriculum, {}, overtime_max=overtime_max)
    if not rows:
        return None, [f"sheet {config.SAVED_SHEET} không có bảng TKB (dòng tiêu đề Lớp | Tiết | Thứ 2 …)"]
    parsed, errors = _parse_saved(problem, rows)
    if errors:
        return None, errors
    # Mỗi (lớp, môn) có thể có hai course: phần GVCN (homeroom) và phần còn lại; tiết của GVCN (trừ tiết bù) vào
    # phần GVCN trước.
    homeroom_of = {t.class_name: t.title for t in problem.teachers.values() if t.class_name}
    courses: dict[tuple[str, str], list[Course]] = {}
    for c in problem.courses:
        courses.setdefault((c.class_name, c.subject), []).append(c)
    groups: dict[tuple[str, str], list[tuple]] = {}
    for item in parsed:
        groups.setdefault((item[0], item[2]), []).append(item)
    lessons: list[Lesson] = []
    for key, items in sorted(groups.items()):
        options = courses.get(key)
        if not options:
            errors.append(f"Lớp {key[0]}: môn {problem.subject_label(key[1])} không có trong chương trình học")
            continue
        room = {c.id: c.lessons for c in options}
        for cls, slot, subject, teacher, overtime, locked in sorted(items, key=lambda p: (p[4], p[1])):
            own = [c for c in options if c.homeroom and room[c.id] > 0 and teacher == homeroom_of.get(cls)
                   and not overtime]
            other = [c for c in options if not c.homeroom and room[c.id] > 0]
            course = (own or other or options)[0]
            room[course.id] -= 1
            lessons.append(Lesson(cls, slot[0], slot[1], subject, teacher, course.id,
                                  overtime=overtime and teacher in problem.overtime, locked=locked))
    errors += [f"Lớp {key[0]}: môn {problem.subject_label(key[1])} có {n} tiết, chương trình học cần {need}"
               for key, need in sorted(_need(problem).items())
               if (n := sum(1 for les in lessons if (les.class_name, les.subject) == key)) != need]
    if not errors:
        errors = check(problem, lessons, settings.student_rules)
    if errors:
        return None, errors
    return Solution(problem, "Dùng lại TKB đã xếp", lessons, 0, 0, 0.0, "dùng lại TKB đã xếp"), []


def _parse_saved(problem: Problem, rows: list[tuple]) -> tuple[list[tuple], list[str]]:
    """Các ô của TKB đã xếp (staff.read_saved_timetable) theo tên trong bài toán: [(lớp, (ngày, tiết), môn, GV, tiết
    bù?, ô khóa?)] và lỗi của các ô không đọc được (lớp, môn, Mã GV không có trong file vào, thứ/tiết sai)."""
    title_of = {normalize(t.code): t.title for t in problem.teachers.values()}
    subject_of = {normalize(problem.subject_label(c.subject)): c.subject for c in problem.courses}
    day_of = {normalize(d): i for i, d in enumerate(config.DAYS)}
    classes = {normalize(c): c for c in problem.classes}
    errors: list[str] = []
    parsed = []
    for cls, day, period, subject, code, overtime, locked, at in rows:
        where = f"sheet {config.SAVED_SHEET} {at}"
        try:
            slot = (day_of[normalize(day)], int(period))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{where}: thứ/tiết không hợp lệ ({day!r}, {period!r})")
            continue
        missing = [what for what, ok in (("lớp", normalize(cls) in classes), ("môn", normalize(subject) in subject_of),
                                          ("Mã GV", normalize(code) in title_of)) if not ok]
        if missing:
            errors.append(f"{where}: {', '.join(missing)} không có trong file vào ({cls}, {subject}, {code})")
            continue
        parsed.append((classes[normalize(cls)], slot, subject_of[normalize(subject)], title_of[normalize(code)],
                       bool(overtime), bool(locked)))
    return parsed, errors


@dataclass(frozen=True)
class KeptCell:
    """Một ô của TKB cũ khi xếp lại ít xáo trộn."""
    subject: str
    teacher: str  # chức vụ chuẩn hóa (Teacher.title)
    overtime: bool
    locked: bool


@dataclass
class Previous:
    """TKB cũ để xếp lại ít xáo trộn (solve(previous=...)): (lớp, (ngày, tiết)) -> ô; các ô không đọc được bỏ qua."""
    cells: dict[tuple[str, tuple[int, int]], KeptCell]
    skipped: list[str] = field(default_factory=list)  # lý do bỏ qua (ô không đọc được, ô khóa không giữ được)

    def taught(self) -> dict[str, set[tuple[str, str]]]:
        """GV -> các (lớp, môn) GV đó dạy trong TKB cũ."""
        out: dict[str, set[tuple[str, str]]] = {}
        for (cls, _), cell in self.cells.items():
            out.setdefault(cell.teacher, set()).add((cls, cell.subject))
        return out


def previous_from(problem: Problem, rows: list[tuple]) -> Previous:
    """TKB cũ từ các dòng của sheet TKB đã xếp: chỉ các ô đọc được với file vào hiện tại (_parse_saved)."""
    parsed, errors = _parse_saved(problem, rows)
    return Previous({(cls, slot): KeptCell(subject, teacher, overtime, locked)
                     for cls, slot, subject, teacher, overtime, locked in parsed}, errors)


def _keep_previous(m, problem: Problem, x: dict, z: dict, teachers_of: dict, keep: Previous,
                   w: config.Weights) -> list:
    """Xếp lại ít xáo trộn: ô khóa của TKB cũ là ràng buộc cứng (môn, và người dạy nếu không phải tiết bù); mỗi ô cũ
    đổi môn bị trừ w.keep_cell. Không dùng TKB cũ làm nghiệm gợi ý (AddHint): OR-Tools 9.15 với interleave_search
    dừng hẳn chương trình ("heuristics.fixed_search != nullptr") khi có gợi ý mà mô hình không có nghiệm. Trả về các
    số hạng mục tiêu."""
    courses: dict[tuple[str, str], list[Course]] = {}
    for c in problem.courses:
        courses.setdefault((c.class_name, c.subject), []).append(c)
    terms = []
    for (cls, slot), cell in sorted(keep.cells.items()):
        options = courses.get((cls, cell.subject), [])
        vs = [x[c.id, slot] for c in options if (c.id, slot) in x]
        where = f"lớp {cls} {config.DAYS[slot[0]]} tiết {slot[1]}"
        if not vs:
            if cell.locked:
                keep.skipped.append(f"ô khóa {where}: môn {problem.subject_label(cell.subject)} không còn xếp được "
                                    f"vào giờ này")
            continue
        terms.append(w.keep_cell * (1 - sum(vs)))
        if not cell.locked:
            continue
        m.Add(sum(vs) == 1)
        if cell.overtime:  # tiết bù: người dạy là người tuyển thay trong bài toán xếp giờ (xem solve)
            continue
        who = [z[c.id, cell.teacher, slot] for c in options if (c.id, cell.teacher, slot) in z] + \
              [x[c.id, slot] for c in options if teachers_of[c.id] == [cell.teacher] and (c.id, slot) in x]
        if who:
            m.Add(sum(who) == 1)
        else:
            keep.skipped.append(f"ô khóa {where}: {problem.teachers[cell.teacher].code} không còn được phân công "
                                f"môn {problem.subject_label(cell.subject)} lớp {cls}, chỉ giữ môn")
    return terms


def _need(problem: Problem) -> dict[tuple[str, str], int]:
    """(lớp, môn) -> số tiết theo chương trình học."""
    need: dict[tuple[str, str], int] = {}
    for c in problem.courses:
        need[c.class_name, c.subject] = need.get((c.class_name, c.subject), 0) + c.lessons
    return need


class ConflictError(SolveError):
    """Các luật bắt buộc mâu thuẫn nhau: không có TKB nào thỏa (thấy khi đếm trước, hoặc khi chẩn đoán)."""


def _assignment(staff: list[Teacher], curriculum: dict[int, dict[str, int]], settings: config.Settings, log):
    """Bước 1 của solve: kiểm tra đếm (tkb/chan_doan.py), dự toán, phân công, chia tiết bù cho người tuyển mới.
    Trả về (bài toán chế độ bù, phân công, bài toán xếp giờ, phân công cố định, chủ của các ô bù, số người tuyển)."""
    from .chan_doan import precheck

    hire = settings.mode == config.MODE_HIRE
    base = build_problem(staff, curriculum, {}, overtime_max=settings.overtime_max)
    for msg in base.warnings:
        log(f"Cảnh báo: {msg}")
    if config.CUSTOM_RULES:
        from .luat_rieng import SHEET, validate
        wrong = validate(base)
        if wrong:
            raise InputError(f"Sheet {SHEET} có {len(wrong)} lỗi:\n  " + "\n  ".join(wrong))
    conflicts = precheck(base, settings.student_rules)
    if conflicts:
        raise ConflictError("Các quy định mâu thuẫn nhau, không có TKB nào thỏa:\n  - " + "\n  - ".join(conflicts))
    log(f"Bước 1/2: dự toán và phân công giáo viên (bù tối đa +{settings.overtime_max} tiết/người)...")
    plan = phan_cong(base, settings.weights)
    for line in du_toan_lines(base, plan):
        log(line)
    if plan.missing and not hire:
        raise ShortageError(base, plan)
    split = tach_tiet_bu(base, plan, staff, include_missing=hire)
    counts = {role: len(groups) for role, groups in split.items()}
    work = build_problem(staff, curriculum, counts, overtime_max=0)
    fixed, owners = _hire_assignment(plan, work, split)
    if hire:
        need = ", ".join(f"{work.teachers[titles[0]].label or role} x{len(titles)}"
                         for role, titles in work.supplement_roles.items() if titles)
        log(f"  Cần tuyển: {need or 'không'} (người mới dạy các tiết bù"
            f"{' và tiết thiếu' if plan.missing else ''})")
    for cls, group, g in plan.odd_pairs:
        log(f"  Cảnh báo: {work.teachers.get(g, base.teachers[g]).code} dạy số tiết lẻ nhóm {group} lớp {cls}, "
            f"khó xếp thành cặp")
    return base, plan, work, fixed, owners, counts


def feasible(staff: list[Teacher], curriculum: dict[int, dict[str, int]], settings: config.Settings,
             seconds: float) -> bool | None:
    """Có TKB nào thỏa mọi luật bắt buộc không, với phân công cố định như solve (tìm nghiệm đầu tiên, tối đa
    `seconds`): True có, False chắc chắn không, None chưa biết (hết thời gian). Dùng để chẩn đoán."""
    try:
        _, _, work, fixed, _, _ = _assignment(staff, curriculum, settings, lambda *_: None)
        tm = build_timetable(work, settings, fixed)
    except (InputError, SolveError):
        return False
    solver = cp_model.CpSolver()
    _configure(solver, settings, seconds)
    solver.parameters.stop_after_first_solution = True
    status = solver.Solve(tm.model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return True
    return False if status == cp_model.INFEASIBLE else None


def _unsolvable(staff: list[Teacher], curriculum: dict[int, dict[str, int]], settings: config.Settings,
                log) -> SolveError:
    """Lỗi khi không xếp được: chẩn đoán luật nào gây ra (tkb/chan_doan.py)."""
    from .chan_doan import diagnose

    found = diagnose(staff, curriculum, settings, log)
    return (ConflictError if found.conflict else SolveError)("\n".join(found.lines))


def solve(staff: list[Teacher], curriculum: dict[int, dict[str, int]],
          settings: config.Settings, log=print, previous: list[tuple] | None = None) -> Solution:
    """Dự toán, phân công → xếp giờ một lần → TKB chế độ bù hoặc chế độ tuyển (cùng vị trí môn). Không xếp được
    thì chẩn đoán luật bắt buộc nào gây ra (ConflictError nếu chắc chắn mâu thuẫn).

    previous: các dòng của sheet TKB đã xếp (staff.read_saved_timetable) khi TKB đó không còn dùng lại được: xếp
    lại **ít xáo trộn nhất**: phân công ưu tiên giữ người dạy cũ (Teacher.previous, allocation.previous_cost), xếp
    giờ giữ mọi ô được (Weights.keep_cell mỗi ô đổi môn), ô khóa giữ nguyên bắt buộc; ô khóa mâu thuẫn với luật
    thì bỏ khóa (in ra) rồi xếp lại."""
    if settings.mode not in config.MODES:
        raise SolveError(f"Chế độ không hợp lệ: {settings.mode!r} (chọn một trong {', '.join(config.MODES)})")
    if settings.overtime_max < 0:
        raise SolveError(f"Số tiết bù tối đa phải >= 0 (đang là {settings.overtime_max})")
    hire = settings.mode == config.MODE_HIRE
    keep = None
    if previous:
        probe = build_problem(staff, curriculum, {}, overtime_max=settings.overtime_max)
        keep = previous_from(probe, previous)
        taught = keep.taught()
        staff = [replace(t, previous=frozenset(taught.get(t.title, ()))) for t in staff]
        log(f"Xếp lại ít xáo trộn: giữ {len(keep.cells)} ô của TKB đã xếp "
            f"({sum(c.locked for c in keep.cells.values())} ô khóa) nhiều nhất có thể"
            + (f"; bỏ qua {len(keep.skipped)} ô không đọc được" if keep.skipped else ""))
    base, plan, work, fixed, owners, counts = _assignment(staff, curriculum, settings, log)

    mode = "chế độ tái lập" if settings.reproducible else "giới hạn giây thực"
    budget = ("không giới hạn thời gian, bấm Ctrl+C để dừng sớm" if settings.time_limit is None
              else f"~{settings.time_limit:.0f}s")
    log(f"Bước 2/2: xếp giờ ({budget}, {mode})...")
    solution = timetable(work, settings, fixed=fixed, log=log, keep=keep)
    if solution is None and keep is not None and any(c.locked for c in keep.cells.values()):
        log("  Các ô khóa mâu thuẫn với luật hoặc phân công mới: bỏ khóa, vẫn giữ TKB cũ nhiều nhất có thể...")
        keep = Previous({k: replace(c, locked=False) for k, c in keep.cells.items()}, keep.skipped)
        solution = timetable(work, settings, fixed=fixed, log=log, keep=keep)
    if solution is not None:
        return _mark_locked(solution if hire else _to_overtime(solution, base, owners), keep, log)
    if not hire:
        raise _unsolvable(staff, curriculum, settings, log)
    for slack in (1, 3):
        log(f"  Không xếp được với phân công cố định; thử mô hình tích hợp (dự phòng {slack} GV/chức vụ)...")
        planned = {role: counts.get(role, 0) + slack for role in work.supplement_roles}
        problem = build_problem(staff, curriculum, planned, overtime_max=0)
        solution = timetable(problem, settings, hint=fixed, keep=keep)
        if solution is not None:
            solution.notes.append(f"Mô hình tích hợp (dự phòng {slack} GV bổ sung/chức vụ)")
            return _mark_locked(solution, keep, log)
    raise _unsolvable(staff, curriculum, settings, log)


def _mark_locked(solution: Solution, keep: Previous | None, log) -> Solution:
    """Đánh dấu các tiết ở ô khóa của TKB cũ (giữ được môn) để file vào cập nhật ghi lại " (khóa)"; in các ô khóa
    không giữ được."""
    if keep is None:
        return solution
    for line in keep.skipped:
        log(f"  Bỏ qua: {line}")
    locked = {k for k, c in keep.cells.items() if c.locked}
    solution.lessons = [replace(les, locked=True)
                        if (les.class_name, (les.day, les.period)) in locked
                        and keep.cells[les.class_name, (les.day, les.period)].subject == les.subject else les
                        for les in solution.lessons]
    return solution
