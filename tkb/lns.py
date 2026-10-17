"""Xếp giờ với phân công cố định: CP-SAT khởi đầu, rồi lặp QA -> xếp lại từng vùng (LNS) đến khi dừng.

1. Khởi đầu: CP-SAT trên toàn mô hình với LNS_START_SHARE ngân sách, tối đa LNS_START_MAX.
2. Mỗi vòng:
   - QA: chi phí mềm của từng lớp-ngày theo các dòng luật ưu tiên (bo_ghep.qa, cùng điểm với mục tiêu); luật theo
     GV (tải ngày, tiết trống, đổi cơ sở) chia đều cho các lớp GV đó dạy hôm ấy. QA chỉ dùng để xếp thứ tự các vùng,
     không đổi luật.
   - Xếp lại lần lượt các vùng: từng lớp -> điểm nóng (lớp-ngày xấu nhất cùng các lớp chung GV không chủ nhiệm
     hôm ấy, mở thêm ngày tốt nhất của lớp) -> nhóm lớp của một GV dùng chung -> từng khối -> từng cặp ngày.
     Mỗi vùng: giữ nguyên mọi tiết ngoài vùng, CP-SAT xếp lại trong vùng xuất phát từ nghiệm đang có, chỉ nhận
     khi chi phí giảm. Luật cứng luôn đúng vì vẫn giải trên toàn mô hình.
3. Dừng khi: hết ngân sách; một vòng giảm chưa tới LNS_MIN_GAIN chi phí (không giới hạn: vòng không giảm);
   đủ LNS_MAX_ROUNDS vòng; hoặc Ctrl+C / nút Dừng của giao diện (dừng sau lần xếp lại đang chạy, vài giây).

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

from . import config, khung_gio
from .solver import TimetableModel, _configure
from .staff import class_sort_key, grade_key, grade_of


@dataclass
class LnsResult:
    values: list[int] | None  # giá trị mọi biến của nghiệm tốt nhất (theo chỉ số biến); None: bỏ (improve give_up)
    objective: float
    bound: float  # cận dưới của bước khởi đầu
    status: str  # "OPTIMAL" nếu bước khởi đầu đã chứng minh tối ưu, không thì "FEASIBLE"
    history: list[int] = field(default_factory=list)  # chi phí xếp giờ sau khởi đầu và sau mỗi vòng
    used: float = 0.0  # ngân sách đã dùng (đơn vị như time_limit, ≈ giây)
    stop: str = ""


def _class_key(cls: str) -> tuple:
    return class_sort_key(cls)


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
        # Ghép lớp: các lớp của nhóm dùng chung biến nên một biến có thể ở nhiều lớp; mở vùng có một lớp của nhóm thì
        # mở cả các lớp kia (`free`).
        self.decision = sorted({i for idx in self.cells.values() for i in idx})
        self.mates: dict[str, set[str]] = defaultdict(set)
        for members in tm.problem.merge_groups().values():
            names = {courses[cid].class_name for cid in members}
            for cls in names:
                self.mates[cls] |= names

    # --- Giải -----------------------------------------------------------------
    def solve(self, model: cp_model.CpModel, seconds: float | None, hint: list[int] | None = None):
        """(status, objective, values, bound, solver); ngân sách đã dùng cộng vào self.used."""
        s = cp_model.CpSolver()
        _configure(s, self.settings, seconds)
        s.parameters.catch_sigint_signal = False  # Ctrl+C do vòng lặp xử lý (xem improve)
        if hint is not None:  # thay gợi ý của mô hình (vd TKB cũ khi xếp lại ít xáo trộn) bằng nghiệm đang có
            model.ClearHints()
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
        """Chi phí mềm theo (lớp, ngày) của các dòng luật ưu tiên (bo_ghep.qa, cùng điểm với mục tiêu), và các tiết của
        nghiệm. Mọi (lớp, ngày) có tiết đều có mặt (chi phí 0 nếu không vi phạm gì): các điểm nóng chọn theo thứ tự đó
        khi ít lớp-ngày có chi phí."""
        tm = self.tm
        lessons = tm.lessons(lambda v: values[v.Index()])
        cost: Counter = Counter({(les.class_name, les.day): 0 for les in lessons})
        if config.CUSTOM_RULES:
            from .luat_rieng import qa
            cost.update(qa(tm.problem, lessons, self.settings.weights))
        return cost, lessons

    # --- Các vùng -------------------------------------------------------------
    def free(self, classes, days) -> set[int]:
        classes = set(classes).union(*(self.mates.get(c, ()) for c in classes))
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
        # GVCN chỉ dạy lớp mình; GVCN có chức vụ thêm (cột Chức Vụ Thêm) dạy cả lớp khác nên tính như GV dạy chung
        homeroom = {g for g, t in problem.teachers.items() if t.class_name and not t.extra_roles}
        hot = sorted(cost.items(), key=lambda kv: (-round(kv[1]), _class_key(kv[0][0]), kv[0][1]))
        for (c, d), _ in hot[:config.LNS_HOTSPOTS]:
            shared = {l.teacher for l in lessons if l.class_name == c and l.day == d and l.teacher not in homeroom}
            other = min((x for x in days if x != d), key=lambda x: (round(cost[c, x]), x))
            # Mở các lớp GV dùng chung dạy ở cả hai ngày được xếp lại: tiết của một GV đổi được giữa hai ngày (vd
            # chuyển hết tiết ở một cơ sở sang ngày khác để không phải đổi cơ sở trong ngày).
            group = {c} | {l.class_name for l in lessons if l.day in (d, other) and l.teacher in shared}
            out.append(("điểm nóng", f"lớp {c} {khung_gio.day_name(d).lower()}", self.free(group, [d, other]),
                        limits["điểm nóng"]))
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
        grade = {c: grade_of(c) for c in classes}
        grades = sorted(set(grade.values()), key=lambda g: (-round(sum(by_class[c] for c in classes if grade[c] == g)),
                                                             grade_key(g)))
        out += [("khối", f"khối {g}", self.free([c for c in classes if grade[c] == g], days), limits["khối"])
                for g in grades]
        pairs = sorted(itertools.combinations(days, 2), key=lambda p: (-round(by_day[p[0]] + by_day[p[1]]), p))
        out += [("cặp ngày", f"{khung_gio.day_name(a).lower()}+{khung_gio.day_name(b).lower()}",
                 self.free(classes, [a, b]), limits["cặp ngày"])
                for a, b in pairs]
        return out


def carry(old: TimetableModel, values: list[int], new: TimetableModel) -> dict[int, int]:
    """Nghiệm của mô hình `old` thành giá trị các biến quyết định (x, z) của mô hình `new` dựng trên cùng bài toán, miền
    rộng hơn (vd bỏ lịch cơ sở): biến không có ở `old` là 0."""
    out = {}
    for name in ("x", "z"):
        before = getattr(old, name)
        for key, v in getattr(new, name).items():
            out[v.Index()] = values[before[key].Index()] if key in before else 0
    return out


def improve(tm: TimetableModel, settings: config.Settings, log=lambda *_: None,
            give_up: bool = False, initial: dict[int, int] | None = None) -> LnsResult | None:
    """Khởi đầu + các vòng QA -> LNS (xem đầu module). None nếu không tìm được TKB nào. give_up: bước khởi đầu không
    ra nghiệm thì dừng luôn, trả kết quả values None, used = ngân sách đã dùng (mô hình theo lịch cơ sở,
    solver.timetable xếp lại không theo lịch). initial (`carry`): khởi đầu từ TKB này thay cho CP-SAT khởi đầu."""
    search = _Search(tm, settings, log)
    total = settings.time_limit if settings.time_limit else math.inf
    unlimited = math.isinf(total)
    start = min(total * config.LNS_START_SHARE, config.LNS_START_MAX)

    def on_sigint(*_):
        search.interrupted = True

    # Ctrl+C; trên Windows giao diện (tkb/giao_dien) dừng sớm tiến trình xếp TKB bằng Ctrl+Break (SIGBREAK).
    signals = [signal.SIGINT, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])]
    main_thread = threading.current_thread() is threading.main_thread()
    old_handlers = {sig: signal.signal(sig, on_sigint) for sig in signals} if main_thread else {}
    try:
        if initial is not None:  # TKB có sẵn: giữ mọi biến quyết định, chỉ tính các biến của mục tiêu
            m = tm.model.clone()
            for i, v in initial.items():  # x, z là biến 0/1: miền [0, 1]
                dom = m.proto.variables[i].domain
                dom[0] = dom[1] = v
            status, best, values, bound, solver = search.solve(m, start)
            status = cp_model.FEASIBLE
        else:
            status, best, values, bound, solver = search.solve(tm.model, start)
        if values is None and give_up:
            return LnsResult(None, math.inf, math.inf, "", used=search.used, stop="khởi đầu không ra nghiệm")
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
            tried = 0
            for _, _, free, limit in search.regions(cost, lessons):
                left = total - search.used
                if left < 1:
                    result.stop = "hết thời gian"
                    break
                tried += 1
                _, val, new, _, _ = search.region(free, min(limit, left), result.values)
                if val is not None and val < result.objective - 0.5:
                    result.objective, result.values = val, new
                if search.interrupted:
                    result.stop = "Ctrl+C"
                    break
            if not tried:
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
        for sig, old in old_handlers.items():
            default = signal.default_int_handler if sig == signal.SIGINT else signal.SIG_DFL
            signal.signal(sig, old if old is not None else default)
