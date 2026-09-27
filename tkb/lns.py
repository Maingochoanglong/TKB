"""Xếp giờ với phân công cố định: CP-SAT khởi đầu, rồi lặp QA -> xếp lại từng vùng (LNS) đến khi dừng.

1. Khởi đầu: CP-SAT trên toàn mô hình với LNS_START_SHARE ngân sách (không giới hạn: LNS_START_UNLIMITED).
2. Mỗi vòng:
   - QA: chi phí mềm của từng lớp-ngày theo đúng trọng số mục tiêu (config.Weights); phạt tải ngày và tiết trống
     của một GV chia đều cho các lớp GV đó dạy hôm ấy. QA chỉ dùng để xếp thứ tự các vùng, không đổi luật.
   - Xếp lại lần lượt các vùng: từng lớp -> điểm nóng (lớp-ngày xấu nhất cùng các lớp chung GV không chủ nhiệm
     hôm ấy, mở thêm ngày tốt nhất của lớp) -> nhóm lớp của một GV dùng chung -> từng khối -> từng cặp ngày.
     Mỗi vùng: giữ nguyên mọi tiết ngoài vùng, CP-SAT xếp lại trong vùng xuất phát từ nghiệm đang có, chỉ nhận
     khi chi phí giảm. Luật cứng luôn đúng vì vẫn giải trên toàn mô hình.
3. Dừng khi: hết ngân sách; một vòng giảm chưa tới LNS_MIN_GAIN chi phí (không giới hạn: vòng không giảm);
   đủ LNS_MAX_ROUNDS vòng; hoặc Ctrl+C (dừng sau lần xếp lại đang chạy, vài giây).

Tái lập: ngân sách tính theo thời gian tất định của CP-SAT (không theo giây thực) và thứ tự các vùng cố định
(hòa điểm thì theo tên lớp, số ngày), nên cùng dữ liệu, cùng hệ điều hành ra cùng TKB.
Không chứng minh tối ưu: kết quả là tối ưu cục bộ theo các vùng; cận dưới lấy từ bước khởi đầu.
"""
from __future__ import annotations

import itertools
import math
import signal
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from . import config
from .solver import TimetableModel, _configure, day_targets, distance_to_session_end


@dataclass
class LnsResult:
    values: list[int]  # giá trị mọi biến của nghiệm tốt nhất (theo chỉ số biến)
    objective: float
    bound: float  # cận dưới của bước khởi đầu
    status: str  # "OPTIMAL" nếu bước khởi đầu đã chứng minh tối ưu, không thì "FEASIBLE"
    history: list[int] = field(default_factory=list)  # chi phí xếp giờ sau khởi đầu và sau mỗi vòng
    used: float = 0.0  # ngân sách đã dùng (đơn vị như time_limit, ≈ giây)
    stop: str = ""


def _class_key(cls: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in cls.split("/"))


class _Search:
    def __init__(self, tm: TimetableModel, settings: config.Settings, log):
        self.tm, self.settings, self.log = tm, settings, log
        self.n = len(tm.model.proto.variables)
        self.used = 0.0
        self.interrupted = False
        courses = tm.problem.courses
        # Biến quyết định (x, z) theo lớp-ngày: vùng xếp lại = các ô lớp-ngày được mở.
        self.cells: dict[tuple[str, int], list[int]] = defaultdict(list)
        for (cid, s), v in tm.x.items():
            self.cells[courses[cid].class_name, s[0]].append(v.Index())
        for (cid, g, s), v in tm.z.items():
            self.cells[courses[cid].class_name, s[0]].append(v.Index())
        self.decision = sorted(i for idx in self.cells.values() for i in idx)

    # --- Giải -----------------------------------------------------------------
    def solve(self, model: cp_model.CpModel, seconds: float | None, hint: list[int] | None = None):
        """(status, objective, values, bound, solver); ngân sách đã dùng cộng vào self.used."""
        s = cp_model.CpSolver()
        _configure(s, self.settings, seconds)
        s.parameters.catch_sigint_signal = False  # Ctrl+C do vòng lặp xử lý (xem improve)
        if hint is not None:
            model.proto.solution_hint.vars.extend(range(self.n))
            model.proto.solution_hint.values.extend(hint)
        status = s.Solve(model)
        r = s.response_proto
        self.used += (r.deterministic_time / self.settings.deterministic_per_second if self.settings.reproducible
                      else r.wall_time)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return status, None, None, None, s
        return status, s.ObjectiveValue(), list(r.solution), s.BestObjectiveBound(), s

    def region(self, free: set[int], seconds: float, best: list[int]):
        """Xếp lại một vùng: mọi biến quyết định ngoài `free` giữ giá trị của `best`."""
        m = self.tm.model.clone()
        variables = m.proto.variables
        for i in self.decision:
            if i not in free:
                dom = variables[i].domain
                dom[0] = best[i]
                dom[1] = best[i]
        return self.solve(m, seconds, hint=best)

    # --- QA -------------------------------------------------------------------
    def qa(self, values: list[int]):
        """Chi phí mềm theo (lớp, ngày), theo trọng số mục tiêu; và các tiết của nghiệm."""
        tm, w = self.tm, self.settings.weights
        problem = tm.problem
        lessons = tm.lessons(lambda v: values[v.Index()])
        cost: Counter = Counter()
        for les in lessons:
            key = les.class_name, les.day
            if les.subject in config.HEAVY_SUBJECTS and les.period in config.HEAVY_LATE_PERIODS:
                cost[key] += w.heavy_late
            if les.subject in config.MORNING_SUBJECTS and les.period not in config.MORNING.periods:
                cost[key] += w.morning_core
            elif les.subject in config.AFTERNOON_SUBJECTS and les.period in config.MORNING.periods:
                cost[key] += w.extra_morning
            if problem.courses[les.course_id].flex_hdtn:
                cost[key] += w.hdtn_flex_distance * distance_to_session_end((les.day, les.period))
        days = len(config.DAY_SESSIONS)
        per_day = Counter((l.class_name, l.subject, l.day) for l in lessons if l.subject != config.HDTN)
        total = Counter((l.class_name, l.subject) for l in lessons if l.subject != config.HDTN)
        for (cls, subject, d), k in per_day.items():
            over = max(0, k - math.ceil(total[cls, subject] / days))
            cost[cls, d] += over * (w.core_spread if subject in config.MORNING_SUBJECTS else w.subject_spread)
        by_teacher_day = defaultdict(list)
        for les in lessons:
            by_teacher_day[les.teacher, les.day].append(les)
        for (g, d), items in sorted(by_teacher_day.items()):
            t = problem.teachers[g]
            over = len(items) - day_targets(t.max_lessons, problem.slots)[d]
            pen = w.day_over_preferred * max(0, over) + w.day_over_buffer * max(0, over - 1)
            if not t.class_name:
                for morning in (True, False):
                    ps = [l.period for l in items if (l.period in config.MORNING.periods) == morning]
                    if ps:
                        pen += w.teacher_gap * ((max(ps) - min(ps) + 1) - len(ps))
            classes = sorted({l.class_name for l in items})
            for cls in classes:
                cost[cls, d] += pen / len(classes)
        return cost, lessons

    # --- Các vùng -------------------------------------------------------------
    def free(self, classes, days) -> set[int]:
        return {i for c in classes for d in days for i in self.cells.get((c, d), ())}

    def regions(self, cost: Counter, lessons) -> list[tuple[str, str, set[int], float]]:
        """(loại, tên, biến được mở, giới hạn) theo thứ tự thử của một vòng."""
        tm = self.tm
        problem = tm.problem
        limits = config.LNS_REGION_LIMITS
        days = sorted(config.DAY_SESSIONS)
        by_class, by_day = Counter(), Counter()
        for (c, d), v in cost.items():
            by_class[c] += v
            by_day[d] += v
        classes = sorted(problem.classes, key=_class_key)
        out = [("lớp", f"lớp {c}", self.free([c], days), limits["lớp"])
               for c in sorted(classes, key=lambda c: (-round(by_class[c]), _class_key(c))) if by_class[c] > 0]
        homeroom = {g for g, t in problem.teachers.items() if t.class_name}
        hot = sorted(cost.items(), key=lambda kv: (-round(kv[1]), _class_key(kv[0][0]), kv[0][1]))
        for (c, d), _ in hot[:config.LNS_HOTSPOTS]:
            shared = {l.teacher for l in lessons if l.class_name == c and l.day == d and l.teacher not in homeroom}
            group = {c} | {l.class_name for l in lessons if l.day == d and l.teacher in shared}
            other = min((x for x in days if x != d), key=lambda x: (round(cost[c, x]), x))
            out.append(("điểm nóng", f"lớp {c} thứ {d + 2}", self.free(group, [d, other]), limits["điểm nóng"]))
        teacher_classes = defaultdict(set)
        for cid, cand in tm.teachers_of.items():
            for g in cand:
                if g not in homeroom:
                    teacher_classes[g].add(problem.courses[cid].class_name)
        lo, hi = config.LNS_SHARED_CLASSES
        groups = list(dict.fromkeys(frozenset(v) for g, v in sorted(teacher_classes.items()) if lo <= len(v) <= hi))
        groups.sort(key=lambda s: (-round(sum(by_class[c] for c in s)), sorted(s, key=_class_key)))
        out += [("GV dùng chung", "lớp " + ",".join(sorted(s, key=_class_key)), self.free(s, days),
                 limits["GV dùng chung"]) for s in groups]
        grade = {c: c.split("/")[0] for c in classes}
        grades = sorted(set(grade.values()), key=lambda g: (-round(sum(by_class[c] for c in classes if grade[c] == g)),
                                                             _class_key(g)))
        out += [("khối", f"khối {g}", self.free([c for c in classes if grade[c] == g], days), limits["khối"])
                for g in grades]
        pairs = sorted(itertools.combinations(days, 2), key=lambda p: (-round(by_day[p[0]] + by_day[p[1]]), p))
        out += [("cặp ngày", f"thứ {a + 2}+{b + 2}", self.free(classes, [a, b]), limits["cặp ngày"])
                for a, b in pairs]
        return out


def improve(tm: TimetableModel, settings: config.Settings, log=lambda *_: None) -> LnsResult | None:
    """Khởi đầu + các vòng QA -> LNS (xem đầu module). None nếu không tìm được TKB nào."""
    search = _Search(tm, settings, log)
    total = settings.time_limit if settings.time_limit else math.inf
    unlimited = math.isinf(total)
    start = config.LNS_START_UNLIMITED if unlimited else total * config.LNS_START_SHARE

    def on_sigint(*_):
        search.interrupted = True

    main_thread = threading.current_thread() is threading.main_thread()
    old_handler = signal.signal(signal.SIGINT, on_sigint) if main_thread else None
    try:
        status, best, values, bound, solver = search.solve(tm.model, start)
        if values is None:
            # Khởi đầu chưa ra nghiệm: giải tiếp toàn mô hình với phần ngân sách còn lại, như cách cũ.
            status, best, values, bound, solver = search.solve(tm.model, None if unlimited else total - search.used)
            if values is None:
                return None
        allocation = sum(tm.allocation_cost)
        offset = allocation if isinstance(allocation, (int, float)) else solver.Value(allocation)
        result = LnsResult(values, best, bound, "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                           [round(best - offset)])
        log(f"  Khởi đầu: chi phí xếp giờ {result.history[-1]}")
        if status == cp_model.OPTIMAL:
            result.stop = "đã tối ưu"
        rnd = 0
        while not result.stop:
            if search.interrupted:
                result.stop = "Ctrl+C"
                break
            if rnd == config.LNS_MAX_ROUNDS:
                result.stop = f"đủ {rnd} vòng"
                break
            rnd += 1
            before = result.objective
            cost, lessons = search.qa(result.values)
            gains: Counter = Counter()
            for kind, _, free, limit in search.regions(cost, lessons):
                left = total - search.used
                if left < 1:
                    result.stop = "hết thời gian"
                    break
                _, val, new, _, _ = search.region(free, min(limit, left), result.values)
                if val is not None and val < result.objective - 0.5:
                    gains[kind] += round(result.objective - val)
                    result.objective, result.values = val, new
                if search.interrupted:
                    result.stop = "Ctrl+C"
                    break
            result.history.append(round(result.objective - offset))
            log(f"  Vòng {rnd}: chi phí xếp giờ {result.history[-1]} (−{round(before - result.objective)})")
            gain = before - result.objective
            if not result.stop and (gain < 0.5 or (not unlimited and gain < config.LNS_MIN_GAIN * result.history[-2])):
                result.stop = "vòng sau cùng không còn cải thiện đáng kể"
        result.used = search.used
        log(f"  Dừng xếp giờ: {result.stop}")
        return result
    finally:
        if main_thread:
            signal.signal(signal.SIGINT, old_handler if old_handler is not None else signal.default_int_handler)
