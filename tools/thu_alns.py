"""Thử nghiệm bước xếp giờ (docs/Nghien_Cuu_ALNS.md): đo LNS hiện tại, so với ALNS, vùng mới, nhiễu mạnh.

Không đổi tkb/: mọi biến thể dùng lại lns._Search (khởi đầu, xếp lại một vùng, QA, danh sách vùng).

  python tools/thu_alns.py mau lns             trường mẫu tên giả (tests/du_lieu_mau.py), LNS hiện tại, 1200
  python tools/thu_alns.py truong v2 600       FILE_VAO của main.py (chỉ in chi phí và loại vùng, không in tên)
  python tools/thu_alns.py --tom-tat out/thu_alns/*.json      bảng theo loại vùng
  python tools/thu_alns.py --can-duoi truong   cận dưới theo lớp (mỗi lớp giải riêng tới tối ưu)
  python tools/thu_alns.py --thanh-phan out/thu_alns/truong_bo_trung_1200.json   chi phí theo thành phần

Biến thể:
  lns       LNS hiện tại (lns.improve).
  bo_trung  LNS hiện tại, bỏ lần xếp lại y hệt (cùng vùng, cùng giới hạn, cùng nghiệm đầu vào): CP-SAT tất định
            nên lần đó chắc chắn không giảm; ra cùng TKB, chỉ bớt ngân sách.
  v1        ALNS từ đầu: roulette theo loại vùng, vùng xấu nhất (QA) chưa tabu của loại đó.
  v2        Vòng 1 như LNS hiện tại, rồi roulette theo loại vùng, vùng ngẫu nhiên, vùng hết giờ thì gấp đôi giới hạn.
  v3        Vòng 1 như LNS hiện tại, rồi ALNS có mô phỏng luyện kim: buộc đổi ít nhất một tiết trong vùng.
  vung_moi  Hướng A: LNS hiện tại (bỏ lần trùng) thêm hai loại vùng "khối × 2 ngày", "GV × 2 ngày", đặt trước
            vùng GV dùng chung (vùng nhỏ trước). vung_moi_sau: cùng các vùng đó nhưng đặt cuối mỗi vòng.
  nhieu     Hướng B: LNS hiện tại (bỏ lần trùng) tới khi dừng, rồi lặp: nhiễu mạnh (buộc đổi 20% số tiết của một
            vùng lớn) -> LNS lại; giữ nghiệm tốt nhất.
Hằng số lấy từ main.py (SO_LUONG, SO_TIET_BU_TOI_DA, LUAT_HOC_SINH), chế độ tái lập. Kết quả ghi
out/thu_alns/<dữ liệu>_<biến thể>_<ngân sách>.json; bước khởi đầu (tất định, như nhau ở mọi biến thể) lưu ở
out/thu_alns/khoi_dau_<dữ liệu>_<ngân sách khởi đầu>.json để lần sau khỏi giải lại (xóa file này khi đổi mô hình).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ortools.sat.python import cp_model  # noqa: E402

import main  # noqa: E402
from tkb import config, lns  # noqa: E402
from tkb.allocation import build_problem  # noqa: E402
from tkb.phan_cong import phan_cong, tach_tiet_bu  # noqa: E402
from tkb.solver import (_configure, _hire_assignment, build_timetable, day_targets,  # noqa: E402
                        distance_to_session_end, session_of)

OUT = ROOT / "out" / "thu_alns"
KINDS = ["lớp", "điểm nóng", "GV dùng chung", "khối", "cặp ngày"]
EXTRA_KINDS = {"khối × 2 ngày": 10, "GV × 2 ngày": 10}  # hướng A: loại vùng mới -> giới hạn mỗi lần xếp lại
ALL_KINDS = KINDS[:2] + list(EXTRA_KINDS) + KINDS[2:]
MASK = (1 << 64) - 1


class Rng:
    """splitmix64 bằng số nguyên thuần: như nhau trên mọi máy, mọi bản Python (không dùng module random)."""

    def __init__(self, seed: int):
        self.state = seed & MASK

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def pick(self, weights: list[int]) -> int:
        """Bánh xe roulette với trọng số nguyên > 0."""
        r = self.next() % sum(weights)
        for i, w in enumerate(weights):
            if r < w:
                return i
            r -= w
        return len(weights) - 1


def build_model(data: str, settings: config.Settings):
    """Mô hình xếp giờ với phân công cố định, như solver.solve dựng (chế độ bù giờ)."""
    work, fixed = _work(data, settings)
    return build_timetable(work, settings, fixed=fixed)


def _work(data: str, settings: config.Settings):
    """(bài toán xếp giờ, phân công cố định) như solver.solve dựng ở chế độ bù giờ."""
    if data == "mau":
        from tests.du_lieu_mau import CURRICULUM, sample_staff
        curriculum, staff = CURRICULUM, sample_staff()
    else:
        from tkb.program import read_program
        from tkb.staff import read_staff
        path = ROOT / main.FILE_VAO
        curriculum = read_program(path)
        staff = read_staff(path, subjects=[s for req in curriculum.values() for s in req])
    base = build_problem(staff, curriculum, {}, overtime_max=settings.overtime_max)
    plan = phan_cong(base, settings.weights)
    split = tach_tiet_bu(base, plan, staff, include_missing=False)
    work = build_problem(staff, curriculum, {r: len(g) for r, g in split.items()}, overtime_max=0)
    fixed, _ = _hire_assignment(plan, work, split)
    return work, fixed


def measuring_search(cache: Path, records: list, skip_repeats: bool = False, extra_regions: str = ""):
    """Lớp con của lns._Search ghi từng lần xếp lại vào `records` và lưu/đọc lại bước khởi đầu từ `cache`.

    skip_repeats: bỏ lần xếp lại y hệt (biến thể bo_trung). extra_regions: thêm vùng của hướng A, "truoc" (trước
    vùng GV dùng chung) hoặc "sau" (cuối vòng).
    """

    class _Fake:  # thay CpSolver khi đọc khởi đầu từ cache: chỉ cần Value(phần chi phí phân công)
        def __init__(self, offset):
            self.offset = offset

        def Value(self, _):
            return self.offset

    class Search(lns._Search):
        started = False

        def regions(self, cost, lessons):
            out = super().regions(cost, lessons)
            if extra_regions:
                out = _with_extra_regions(self, out, cost, extra_regions)
            self.kind_of = {id(free): (kind, name) for kind, name, free, _ in out}
            return out

        def solve(self, model, seconds, hint=None):
            if hint is not None or self.started:
                return super().solve(model, seconds, hint)
            self.started = True
            if cache.exists():
                c = json.loads(cache.read_text())
                self.used += c["used"]
                return c["status"], c["objective"], c["values"], c["bound"], _Fake(c["offset"])
            used = self.used
            status, obj, values, bound, solver = super().solve(model, seconds, hint)
            if values is not None:
                alloc = sum(self.tm.allocation_cost)
                offset = alloc if isinstance(alloc, (int, float)) else solver.Value(alloc)
                cache.write_text(json.dumps(dict(status=int(status), objective=obj, values=values, bound=bound,
                                                 used=self.used - used, offset=offset)))
            return status, obj, values, bound, solver

        def region(self, free, seconds, best):
            kind, name = getattr(self, "current", None) or self.kind_of.get(id(free), ("?", "?"))
            self.current = None
            key = (hashlib.sha1(repr(sorted(free)).encode()).hexdigest(), seconds,
                   hashlib.sha1(repr(best).encode()).hexdigest())
            seen = self.__dict__.setdefault("seen", set())
            if skip_repeats and key in seen:
                records.append(dict(kind=kind, name=name, limit=seconds, dt=0.0, val=None, status="SKIPPED"))
                return cp_model.UNKNOWN, None, None, None, None
            seen.add(key)
            used = self.used
            status, val, new, bound, solver = super().region(free, seconds, best)
            records.append(dict(kind=kind, name=name, limit=seconds, dt=self.used - used, val=val,
                                status=getattr(status, "name", str(status))))
            return status, val, new, bound, solver

    return Search


def _with_extra_regions(search, out, cost, where="truoc"):
    """Hướng A: thêm vùng "khối × 2 ngày" và "GV × 2 ngày", trước các vùng GV dùng chung hoặc cuối vòng.

    Mỗi khối, và mỗi nhóm lớp của một GV dùng chung (như vùng GV dùng chung), được mở trong cặp ngày có tổng chi
    phí QA lớn nhất của nó. Đây là phần giao của các vùng lớn hay hết giờ (khối, GV dùng chung, cặp ngày), nhỏ hơn
    nhiều nên CP-SAT dễ giải xong. Trong mỗi loại, vùng xấu trước; bỏ vùng có chi phí 0.
    """
    tm = search.tm
    problem = tm.problem
    pairs = list(itertools.combinations(sorted(config.DAY_SESSIONS), 2))

    def worst_pair(cs):
        score = {p: sum(cost[c, d] for c in cs for d in p) for p in pairs}
        pair = min(pairs, key=lambda p: (-round(score[p]), p))
        return pair, round(score[pair])

    grades = defaultdict(list)
    for c in sorted(problem.classes, key=lns._class_key):
        grades[c.split("/")[0]].append(c)
    homeroom = {g for g, t in problem.teachers.items() if t.class_name}
    teacher_classes = defaultdict(set)
    for cid, cand in tm.teachers_of.items():
        for g in cand:
            if g not in homeroom:
                teacher_classes[g].add(problem.courses[cid].class_name)
    lo, hi = config.LNS_SHARED_CLASSES
    groups = list(dict.fromkeys(frozenset(v) for g, v in sorted(teacher_classes.items()) if lo <= len(v) <= hi))
    sets = {"khối × 2 ngày": [(f"khối {g}", cs) for g, cs in grades.items()],
            "GV × 2 ngày": [("lớp " + ",".join(cs), cs) for cs in (sorted(s, key=lns._class_key) for s in groups)]}
    extra = []
    for kind, items in sets.items():
        found = []
        for label, cs in items:
            (a, b), score = worst_pair(cs)
            if score > 0:
                found.append((-score, label, cs, a, b))
        extra += [(kind, f"{label} thứ {a + 2}+{b + 2}", search.free(cs, [a, b]), EXTRA_KINDS[kind])
                  for _, label, cs, a, b in sorted(found, key=lambda f: f[:2])]
    if where == "sau":
        return out + extra
    at = next((i for i, r in enumerate(out) if r[0] not in ("lớp", "điểm nóng")), len(out))
    return out[:at] + extra + out[at:]


def _start(search, tm, settings, log):
    """Khởi đầu như lns.improve: (LnsResult, phần chi phí phân công) hoặc None."""
    total = settings.time_limit
    status, best, values, bound, solver = search.solve(tm.model, min(total * config.LNS_START_SHARE,
                                                                     config.LNS_START_MAX))
    if values is None:
        return None
    allocation = sum(tm.allocation_cost)
    offset = allocation if isinstance(allocation, (int, float)) else solver.Value(allocation)
    res = lns.LnsResult(values, best, bound, "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                        [round(best - offset)])
    log(f"  Khởi đầu: chi phí xếp giờ {res.history[-1]}")
    return res, offset


def _first_round(search, res, total, offset, log):
    """Vòng 1 đúng như lns.improve."""
    cost, lessons = search.qa(res.values)
    for kind, name, free, limit in search.regions(cost, lessons):
        left = total - search.used
        if left < 1:
            break
        _, val, new, _, _ = search.region(free, min(limit, left), res.values)
        if val is not None and val < res.objective - 0.5:
            res.objective, res.values = val, new
    res.history.append(round(res.objective - offset))
    log(f"  Vòng 1: chi phí xếp giờ {res.history[-1]}")


def _descent(search, res, total, offset, log, label="Vòng"):
    """Các vòng QA -> xếp lại từng vùng từ nghiệm `res`, đúng như vòng lặp của lns.improve; trả về lý do dừng."""
    history = [round(res.objective - offset)]
    rnd = 0
    while True:
        if rnd == config.LNS_MAX_ROUNDS:
            return f"đủ {rnd} vòng"
        rnd += 1
        before = res.objective
        cost, lessons = search.qa(res.values)
        tried, stop = 0, ""
        for _, _, free, limit in search.regions(cost, lessons):
            left = total - search.used
            if left < 1:
                stop = "hết thời gian"
                break
            tried += 1
            _, val, new, _, _ = search.region(free, min(limit, left), res.values)
            if val is not None and val < res.objective - 0.5:
                res.objective, res.values = val, new
        if not tried:
            return stop or "hết thời gian"
        history.append(round(res.objective - offset))
        log(f"  {label} {rnd}: chi phí xếp giờ {history[-1]} (−{round(before - res.objective)})")
        if stop:
            return stop
        gain = before - res.objective
        if gain < 0.5 or gain < config.LNS_MIN_GAIN * history[-2]:
            return "vòng sau cùng không còn cải thiện đáng kể"


def _finish(search, res, offset, log, note=""):
    """Ghi lý do dừng, chi phí cuối và ngân sách đã dùng."""
    res.stop = res.stop or "hết thời gian"
    res.history.append(round(res.objective - offset))
    res.used = search.used
    log(f"  Dừng xếp giờ: {res.stop}{note}")
    return res


def v1(tm, settings, log, Search, segment=8, reaction=0.3, w_min=50):
    """ALNS từ đầu: roulette theo loại vùng, vùng xấu nhất chưa tabu.

    Mỗi bước: chọn loại vùng theo trọng số (roulette), lấy vùng xấu nhất (QA) chưa tabu của loại đó. Vùng xếp lại
    mà không giảm thành tabu tới khi nghiệm đổi ở lớp liên quan (cùng lớp hoặc chung GV không chủ nhiệm). Trọng số =
    hiệu quả (giảm / ngân sách) của đoạn vừa qua, trộn với cũ theo hệ số r. Hết vùng thì gấp đôi giới hạn các vùng
    đã hết giờ (tối đa 8 lần), không còn thì dừng."""
    search = Search(tm, settings, log)
    started = _start(search, tm, settings, log)
    if started is None:
        return None
    res, offset = started
    total = settings.time_limit
    courses = tm.problem.courses
    var_class = {i: c for (c, _), idx in search.cells.items() for i in idx}
    homeroom = {g for g, t in tm.problem.teachers.items() if t.class_name}
    teacher_classes = defaultdict(set)
    for cid, cand in tm.teachers_of.items():
        for g in cand:
            if g not in homeroom:
                teacher_classes[g].add(courses[cid].class_name)
    neighbors = defaultdict(set)
    for cs in teacher_classes.values():
        for c in cs:
            neighbors[c] |= cs
    rng = Rng(settings.seed * 1_000_003 + 17)
    weight = {k: 1000 for k in KINDS}
    seg_gain, seg_used = defaultdict(float), defaultdict(float)
    tabu, timed_out, extra = set(), set(), {}
    it, regs = 0, None
    while total - search.used >= 1:
        if regs is None:
            regs = search.regions(*search.qa(res.values))
            region_classes = {name: {var_class[i] for i in free} for _, name, free, _ in regs}
        cands = [r for r in regs if r[1] not in tabu]
        if not cands:
            again = [n for n in sorted(timed_out) if extra.get(n, 1) < 8]
            if not again:
                res.stop = "mọi vùng đã thử, không vùng nào giảm"
                break
            for n in again:
                extra[n] = extra.get(n, 1) * 2
                tabu.discard(n)
            timed_out.clear()
            continue
        kinds = [k for k in KINDS if any(r[0] == k for r in cands)]
        kind = kinds[rng.pick([weight[k] for k in kinds])]
        _, name, free, limit = next(r for r in cands if r[0] == kind)
        used = search.used
        search.current = kind, name
        st, val, new, _, _ = search.region(free, min(limit * extra.get(name, 1), total - search.used), res.values)
        it += 1
        seg_used[kind] += search.used - used
        if val is not None and val < res.objective - 0.5:
            seg_gain[kind] += res.objective - val
            changed = {var_class[i] for i in search.decision if new[i] != res.values[i]}
            affected = set(changed).union(*(neighbors[c] for c in changed))
            res.objective, res.values = val, new
            tabu = {n for n in tabu if not region_classes[n] & affected}
            timed_out = {n for n in timed_out if not region_classes[n] & affected}
            regs = None
        else:
            tabu.add(name)
            if st != cp_model.OPTIMAL:
                timed_out.add(name)
        if it % segment == 0:
            eff = {k: seg_gain[k] / seg_used[k] for k in KINDS if seg_used[k] > 0}
            if eff:
                mean = sum(eff.values()) / len(eff) or 1
                for k, e in eff.items():
                    weight[k] = max(w_min, round((1 - reaction) * weight[k] + reaction * 1000 * e / mean))
            seg_gain.clear(), seg_used.clear()
            res.history.append(round(res.objective - offset))
            log(f"  Bước {it}: chi phí xếp giờ {res.history[-1]}, trọng số "
                + ", ".join(f"{k} {weight[k]}" for k in KINDS))
    return _finish(search, res, offset, log, f" (sau {it} lần xếp lại)")


def v2(tm, settings, log, Search, segment=5, reaction=0.3, w_floor=100, max_mult=4):
    """Vòng 1 như LNS hiện tại, rồi roulette theo loại vùng, vùng ngẫu nhiên, vùng hết giờ thì gấp đôi giới hạn.

    Sau vòng 1, mỗi bước chọn loại vùng theo trọng số (roulette), vùng ngẫu nhiên trong loại, bỏ vùng đã chứng minh
    tối ưu trên đúng nghiệm hiện tại; vùng hết giờ mà không giảm thì lần sau gấp đôi giới hạn (tối đa max_mult lần).
    Vòng 1 cũng ghi sổ như vậy."""
    search = Search(tm, settings, log)
    started = _start(search, tm, settings, log)
    if started is None:
        return None
    res, offset = started
    total = settings.time_limit
    version, proven, mult = 0, {}, {}

    def attempt(kind, name, free, limit):
        """Xếp lại một vùng; (giảm, ngân sách dùng). Ghi sổ: chứng minh xong, gấp đôi giới hạn, phiên bản nghiệm."""
        nonlocal version
        used = search.used
        search.current = kind, name
        st, val, new, _, _ = search.region(free, min(limit * mult.get(name, 1), total - search.used), res.values)
        gain = res.objective - val if val is not None else 0
        if gain > 0.5:
            res.objective, res.values = val, new
            version += 1
            mult.pop(name, None)
        elif st == cp_model.OPTIMAL:
            proven[name] = version
        else:
            mult[name] = min(max_mult, mult.get(name, 1) * 2)
        return max(gain, 0), search.used - used

    for region in search.regions(*search.qa(res.values)):
        if total - search.used < 1:
            break
        attempt(*region)
    res.history.append(round(res.objective - offset))
    log(f"  Vòng 1: chi phí xếp giờ {res.history[-1]}")
    rng = Rng(settings.seed * 1_000_003 + 17)
    weight = {k: 1000 for k in KINDS}
    seg_gain, seg_used = defaultdict(float), defaultdict(float)
    it, seen = 0, -1
    while total - search.used >= 1:
        if seen != version:
            by_kind = defaultdict(list)
            for r in search.regions(*search.qa(res.values)):
                by_kind[r[0]].append(r)
            seen = version
        cands = {k: [r for r in by_kind[k] if proven.get(r[1]) != version] for k in KINDS}
        avail = [k for k in KINDS if cands[k]]
        if not avail:
            res.stop = "mọi vùng đã chứng minh tối ưu"
            break
        kind = avail[rng.pick([weight[k] for k in avail])]
        gain, used = attempt(*cands[kind][rng.next() % len(cands[kind])])
        it += 1
        seg_gain[kind] += gain
        seg_used[kind] += used
        if it % segment == 0:
            eff = {k: seg_gain[k] / max(seg_used[k], 0.01) for k in seg_used}
            mean = sum(eff.values()) / len(eff)
            for k, e in eff.items():
                target = 1000 * e / mean if mean > 0 else weight[k]
                weight[k] = max(w_floor, round((1 - reaction) * weight[k] + reaction * target))
            seg_gain.clear(), seg_used.clear()
            res.history.append(round(res.objective - offset))
            log(f"  Bước {it}: chi phí xếp giờ {res.history[-1]}, trọng số "
                + ", ".join(f"{k} {weight[k]}" for k in KINDS))
    return _finish(search, res, offset, log, f" (sau vòng 1: {it} lần xếp lại)")


def v3(tm, settings, log, Search, segment=5, reaction=0.3, w_floor=100, t_start=0.004, t_end=0.0003,
       sigma=(33, 9, 13)):
    """Vòng 1 như LNS hiện tại, rồi ALNS có mô phỏng luyện kim và buộc đổi.

    Mỗi bước: chọn loại vùng (roulette, điểm σ của Ropke & Pisinger: nghiệm tốt nhất mới / tốt hơn nghiệm hiện
    tại / nhận nghiệm tệ hơn), vùng ngẫu nhiên, BUỘC ĐỔI ít nhất một tiết trong vùng, CP-SAT tìm cách đổi tốt nhất.
    Nhận nếu không tệ hơn; tệ hơn Δ thì nhận với xác suất exp(-Δ/T), T giảm dần từ t_start đến t_end × chi phí
    xếp giờ. Giữ riêng nghiệm tốt nhất. Các lần buộc đổi không vào bảng --tom-tat (chỉ có vòng 1); số lần tốt hơn /
    bằng / tệ hơn in ở dòng "Kết quả buộc đổi"."""
    search = Search(tm, settings, log)
    started = _start(search, tm, settings, log)
    if started is None:
        return None
    res, offset = started
    total = settings.time_limit
    _first_round(search, res, total, offset, log)
    xs = {v.Index() for v in tm.x.values()}

    def forced(free, seconds, values):
        m = tm.model.clone()
        variables = m.proto.variables
        for i in search.decision:
            if i not in free:
                variables[i].domain[0] = variables[i].domain[1] = values[i]
        ones = [i for i in sorted(free) if i in xs and values[i] == 1]
        m.add(sum(m.get_bool_var_from_proto_index(i) for i in ones) <= len(ones) - 1)
        return search.solve(m, seconds, hint=values)

    cur_obj, cur_vals = res.objective, res.values
    tried, version = set(), 0
    rng = Rng(settings.seed * 1_000_003 + 29)
    weight = {k: 1000 for k in KINDS}
    seg_score, seg_uses = defaultdict(float), defaultdict(int)
    outcome = defaultdict(int)
    phase = search.used
    it, seen, worse = 0, -1, 0
    while total - search.used >= 1:
        if seen != version:
            by_kind = defaultdict(list)
            for r in search.regions(*search.qa(cur_vals)):
                by_kind[r[0]].append(r)
            seen = version
        cands = {k: [r for r in by_kind[k] if (r[1], version) not in tried] for k in KINDS}
        avail = [k for k in KINDS if cands[k]]
        if not avail:
            res.stop = "mọi vùng đã thử"
            break
        kind = avail[rng.pick([weight[k] for k in avail])]
        _, name, free, limit = cands[kind][rng.next() % len(cands[kind])]
        _, val, new, _, _ = forced(free, min(limit, total - search.used), cur_vals)
        it += 1
        outcome[kind, "không có nghiệm" if val is None else "tốt hơn" if val < cur_obj - 0.5
                else "bằng" if val <= cur_obj + 0.5 else "tệ hơn"] += 1
        frac = min(1.0, (search.used - phase) / max(total - phase, 1))
        temp = (cur_obj - offset) * t_start * (t_end / t_start) ** frac
        score = 0
        if val is not None:
            delta = val - cur_obj
            if val < res.objective - 0.5:
                score = sigma[0]
            elif delta < -0.5:
                score = sigma[1]
            if delta <= 0.5 or rng.next() / 2 ** 64 < math.exp(-delta / temp):
                if delta > 0.5:
                    worse += 1
                    score = max(score, sigma[2])
                cur_obj, cur_vals = val, new
                version += 1
                if val < res.objective - 0.5:
                    res.objective, res.values = val, new
            else:
                tried.add((name, version))
        else:
            tried.add((name, version))
        seg_score[kind] += score
        seg_uses[kind] += 1
        if it % segment == 0:
            for k, n in seg_uses.items():
                weight[k] = max(w_floor, round((1 - reaction) * weight[k] + reaction * 1000 * (seg_score[k] / n)
                                               / sigma[1]))
            seg_score.clear(), seg_uses.clear()
            res.history.append(round(res.objective - offset))
            log(f"  Bước {it}: tốt nhất {res.history[-1]}, hiện tại {round(cur_obj - offset)}, T {temp:.0f}")
    log("  Kết quả buộc đổi: " + "; ".join(f"{k} {o} {n}" for (k, o), n in sorted(outcome.items())))
    return _finish(search, res, offset, log, f" (sau vòng 1: {it} lần, nhận tệ hơn {worse} lần)")


def nhieu(tm, settings, log, Search, share=0.2, kick_limit=30, kick_min=60):
    """Hướng B: LNS như hiện tại tới khi dừng, rồi lặp nhiễu mạnh -> LNS lại, giữ nghiệm tốt nhất.

    Nhiễu: chọn ngẫu nhiên một vùng lớn (GV dùng chung, khối hoặc cặp ngày) của nghiệm tốt nhất, BUỘC ĐỔI CHỖ ít nhất
    `share` số tiết trong vùng; CP-SAT tìm cách đổi rẻ nhất (có thể tệ hơn), giới hạn kick_limit. Rồi các vòng LNS
    như cũ từ nghiệm đó tới khi dừng; tốt hơn thì giữ. Dừng khi ngân sách còn dưới kick_min.
    """
    search = Search(tm, settings, log)
    started = _start(search, tm, settings, log)
    if started is None:
        return None
    res, offset = started
    total = settings.time_limit
    stop = _descent(search, res, total, offset, log)
    res.history.append(round(res.objective - offset))
    log(f"  LNS dừng ({stop}): chi phí xếp giờ {res.history[-1]}, đã dùng {search.used:.0f}")
    xs = {v.Index() for v in tm.x.values()}
    big = ("GV dùng chung", "khối", "cặp ngày")
    rng = Rng(settings.seed * 1_000_003 + 43)
    kicks = better = 0
    while total - search.used >= kick_min:
        by_kind = defaultdict(list)
        for r in search.regions(*search.qa(res.values)):
            if r[0] in big:
                by_kind[r[0]].append(r)
        kinds = [k for k in big if by_kind[k]]
        kind = kinds[rng.next() % len(kinds)]
        _, name, free, _ = by_kind[kind][rng.next() % len(by_kind[kind])]
        ones = [i for i in sorted(free) if i in xs and res.values[i] == 1]
        k = max(1, round(share * len(ones)))
        m = tm.model.clone()
        variables = m.proto.variables
        for i in search.decision:
            if i not in free:
                variables[i].domain[0] = variables[i].domain[1] = res.values[i]
        m.add(sum(m.get_bool_var_from_proto_index(i) for i in ones) <= len(ones) - k)
        _, val, new, _, _ = search.solve(m, min(kick_limit, total - search.used), hint=res.values)
        kicks += 1
        if val is None:
            log(f"  Nhiễu {kicks}: {kind} {name}, đổi ≥ {k}/{len(ones)} tiết: không tìm được cách đổi")
            continue
        cur = lns.LnsResult(new, val, res.bound, res.status)
        stop = _descent(search, cur, total, offset, log, label=f"  Nhiễu {kicks}, vòng")
        log(f"  Nhiễu {kicks}: {kind} {name}, đổi ≥ {k}/{len(ones)} tiết: {round(res.objective - offset)} -> "
            f"{round(val - offset)} -> LNS lại {round(cur.objective - offset)} ({stop}), đã dùng {search.used:.0f}")
        if cur.objective < res.objective - 0.5:
            res.objective, res.values = cur.objective, cur.values
            better += 1
        res.history.append(round(res.objective - offset))
    res.stop = "hết thời gian"
    return _finish(search, res, offset, log, f" (sau {kicks} lần nhiễu, {better} lần tốt hơn)")


def run(data: str, variant: str, limit: float) -> Path:
    """Chạy một biến thể, ghi out/thu_alns/<dữ liệu>_<biến thể>_<ngân sách>.json."""
    settings = config.Settings(time_limit=limit, workers=main.SO_LUONG, mode=config.MODE_OVERTIME,
                               overtime_max=main.SO_TIET_BU_TOI_DA, student_rules=main.LUAT_HOC_SINH)
    OUT.mkdir(parents=True, exist_ok=True)
    tm = build_model(data, settings)
    records, logs = [], []

    def log(msg):
        logs.append(msg)
        print(msg, flush=True)

    Search = measuring_search(_start_cache(data, limit), records,
                              skip_repeats=variant in ("bo_trung", "vung_moi", "vung_moi_sau", "nhieu"),
                              extra_regions={"vung_moi": "truoc", "vung_moi_sau": "sau"}.get(variant, ""))
    start = time.time()
    if variant in ("lns", "bo_trung", "vung_moi", "vung_moi_sau"):
        original, lns._Search = lns._Search, Search
        try:
            res = lns.improve(tm, settings, log)
        finally:
            lns._Search = original
    else:
        res = {"v1": v1, "v2": v2, "v3": v3, "nhieu": nhieu}[variant](tm, settings, log, Search)
    out = OUT / f"{data}_{variant}_{limit:g}.json"
    out.write_text(json.dumps(dict(
        data=data, variant=variant, limit=limit, history=res.history, used=res.used, stop=res.stop,
        wall=time.time() - start, logs=logs, records=records,
        values=hashlib.sha1(repr(res.values).encode()).hexdigest(), solution=res.values),
        ensure_ascii=False, indent=0))
    print(f"{data} {variant} {limit:g}: chi phí {' -> '.join(map(str, res.history))}, dùng {res.used:.0f}, "
          f"{time.time() - start:.0f} giây. Ghi {out.relative_to(ROOT)}")
    return out


COMPONENTS = ["TV/Toán buổi chiều", "môn nặng tiết 7", "Toán TC buổi sáng", "HĐTN xa cuối buổi", "rải đều",
              "thưởng tiết TC liền sau", "tải ngày GV", "tiết trống GV"]


def components(tm, values, w: config.Weights) -> Counter:
    """Chi phí xếp giờ của một nghiệm theo từng thành phần, đúng công thức mục tiêu của solver.build_timetable."""
    problem = tm.problem
    lessons = tm.lessons(lambda v: values[v.Index()])
    out = Counter({k: 0 for k in COMPONENTS})
    at = {(les.class_name, les.day, les.period): les for les in lessons}
    session = session_of()
    for les in lessons:
        slot = les.day, les.period
        if les.subject in config.MORNING_SUBJECTS and les.period not in config.MORNING.periods:
            out["TV/Toán buổi chiều"] += w.morning_core
        elif les.subject in config.AFTERNOON_SUBJECTS and les.period in config.MORNING.periods:
            out["Toán TC buổi sáng"] += w.extra_morning
        if les.subject in config.HEAVY_SUBJECTS and les.period in config.HEAVY_LATE_PERIODS:
            out["môn nặng tiết 7"] += w.heavy_late
        if problem.courses[les.course_id].flex_hdtn:
            out["HĐTN xa cuối buổi"] += w.hdtn_flex_distance * distance_to_session_end(slot)
        main_subject = config.SUBJECT_GROUPS.get(les.subject)
        prev = at.get((les.class_name, les.day, les.period - 1))
        if (main_subject and prev and prev.subject == main_subject and prev.teacher == les.teacher
                and session.get((les.day, les.period - 1)) is session[slot]):
            out["thưởng tiết TC liền sau"] -= w.extra_after_main
    days = sorted(config.DAY_SESSIONS)
    total = Counter((c.class_name, c.subject) for c in problem.courses for _ in range(c.lessons)
                    if c.subject != config.HDTN)
    per_day = Counter((les.class_name, les.subject, les.day) for les in lessons if les.subject != config.HDTN)
    for (cls, subject, d), k in per_day.items():
        over = max(0, k - math.ceil(total[cls, subject] / len(days)))
        out["rải đều"] += over * (w.core_spread if subject in config.MORNING_SUBJECTS else w.subject_spread)
    by_teacher_day = defaultdict(list)
    for les in lessons:
        by_teacher_day[les.teacher, les.day].append(les.period)
    for (g, d), periods in by_teacher_day.items():
        t = problem.teachers[g]
        over = len(periods) - day_targets(t.max_lessons, problem.slots)[d]
        out["tải ngày GV"] += w.day_over_preferred * max(0, over) + w.day_over_buffer * max(0, over - 1)
        if not t.class_name:
            for sess in config.DAY_SESSIONS[d]:
                ps = [p for p in periods if p in sess.periods]
                if len(sess.periods) >= 3 and ps:
                    out["tiết trống GV"] += w.teacher_gap * ((max(ps) - min(ps) + 1) - len(ps))
    return out


def _settings(limit: float | None = 1200.0) -> config.Settings:
    return config.Settings(time_limit=limit, workers=main.SO_LUONG, mode=config.MODE_OVERTIME,
                           overtime_max=main.SO_TIET_BU_TOI_DA, student_rules=main.LUAT_HOC_SINH)


def lower_bound(data: str, seconds: float = 60) -> Path:
    """Cận dưới theo lớp: mỗi lớp một bài riêng (chỉ các môn của lớp, phân công giữ nguyên), giải tới tối ưu.

    Bỏ ràng buộc giữa các lớp (GV không dạy 2 lớp cùng lúc) và phần tiết trống của GV (trọng số 0); giữ tải ngày
    của GV tính riêng trong lớp đó (hàm phạt lồi, bằng 0 tại 0 nên tổng theo lớp không vượt phạt thật). Mọi
    thành phần khác chỉ phụ thuộc một lớp. Vì vậy tổng tối ưu các lớp là cận dưới của chi phí xếp giờ.
    """
    settings = _settings(seconds)
    settings.weights = replace(settings.weights, teacher_gap=0)
    work, fixed = _work(data, settings)
    rows, comp = [], Counter()
    for cls in work.classes:
        courses = [c for c in work.courses if c.class_name == cls]
        ids = {c.id: i for i, c in enumerate(courses)}
        sub = replace(work, classes=[cls], courses=[replace(c, id=ids[c.id]) for c in courses], manager_load={},
                      supplement_roles={})
        tm = build_timetable(sub, settings, fixed={(ids[cid], g): n for (cid, g), n in fixed.items() if cid in ids})
        solver = cp_model.CpSolver()
        _configure(solver, settings, seconds)
        status = solver.Solve(tm.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise SystemExit(f"lớp {cls}: không giải được ({solver.StatusName(status)})")
        alloc = sum(tm.allocation_cost)
        offset = alloc if isinstance(alloc, (int, float)) else solver.Value(alloc)
        values = list(solver.ResponseProto().solution)
        c = components(tm, values, settings.weights)
        comp.update(c)  # không dùng +=: Counter bỏ giá trị âm (thưởng)
        rows.append(dict(cls=cls, status=solver.StatusName(status), bound=round(solver.BestObjectiveBound() - offset),
                         value=round(solver.ObjectiveValue() - offset), components=dict(c)))
        print(f"  lớp {cls}: {rows[-1]['status']}, cận {rows[-1]['bound']}, tối ưu lớp {rows[-1]['value']}", flush=True)
    bound = sum(r["bound"] for r in rows)
    print(f"{data}: cận dưới theo lớp {bound} ({sum(r['status'] == 'OPTIMAL' for r in rows)}/{len(rows)} lớp chứng "
          f"minh tối ưu)")
    for k in COMPONENTS:
        print(f"  {k:24} {comp[k]:7}")
    out = OUT / f"can_duoi_{data}.json"
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(data=data, bound=bound, components=dict(comp), classes=rows), ensure_ascii=False,
                              indent=0))
    return out


def breakdown(path: str) -> None:
    """Chi phí xếp giờ của nghiệm trong file kết quả theo thành phần; so với cận dưới theo lớp nếu đã tính."""
    d = json.loads(Path(path).read_text())
    settings = _settings(d["limit"])
    tm = build_model(d["data"], settings)
    comp = components(tm, d["solution"], settings.weights)
    lb_path = OUT / f"can_duoi_{d['data']}.json"
    lb = json.loads(lb_path.read_text()) if lb_path.exists() else None
    print(f"{path}: chi phí xếp giờ {d['history'][-1]}, tổng theo thành phần {sum(comp.values())}")
    print(f"  {'thành phần':24} {'nghiệm':>7}" + (f" {'cận theo lớp':>13} {'chênh':>6}" if lb else ""))
    for k in COMPONENTS:
        extra = f" {lb['components'].get(k, 0):13} {comp[k] - lb['components'].get(k, 0):6}" if lb else ""
        print(f"  {k:24} {comp[k]:7}{extra}")
    if lb:
        print(f"  {'cộng':24} {sum(comp.values()):7} {lb['bound']:13} {sum(comp.values()) - lb['bound']:6}")


def _start_cache(data: str, limit: float) -> Path:
    """File lưu bước khởi đầu: theo ngân sách khởi đầu (1200 và 2400 cùng khởi đầu 120)."""
    return OUT / f"khoi_dau_{data}_{min(limit * config.LNS_START_SHARE, config.LNS_START_MAX):g}.json"


def summary(paths: list[str]) -> None:
    """Bảng theo loại vùng: số lần, số lần giảm, tổng giảm, ngân sách, giảm/đơn vị, số vùng chứng minh xong."""
    for p in paths:
        d = json.loads(Path(p).read_text())
        start = json.loads(_start_cache(d["data"], d["limit"]).read_text())
        cur = start["objective"]
        agg = defaultdict(lambda: [0, 0, 0.0, 0.0, 0, 0])
        for r in d["records"]:
            a = agg[r["kind"]]
            a[0] += 1
            a[3] += r["dt"]
            a[4] += r["status"] == "OPTIMAL"
            a[5] += r["status"] == "SKIPPED"
            if r["val"] is not None and r["val"] < cur - 0.5:
                a[1] += 1
                a[2] += cur - r["val"]
                cur = r["val"]
        total = sum(a[3] for a in agg.values()) or 1
        print(f"{p}: chi phí {' -> '.join(map(str, d['history']))}, dùng {d['used']:.0f}, dừng: {d['stop']}")
        print(f"  {'loại':14} {'lần':>4} {'giảm':>4} {'tổng giảm':>9} {'ngân sách':>9} {'%':>4} {'giảm/đv':>8} "
              f"{'chứng minh':>10} {'bỏ trùng':>8}")
        for k in ALL_KINDS:
            if k in agg:
                n, imp, gain, dt, opt, skip = agg[k]
                print(f"  {k:14} {n:4} {imp:4} {gain:9.0f} {dt:9.1f} {100 * dt / total:4.0f} "
                      f"{gain / max(dt, 1e-9):8.1f} {opt:10} {skip:8}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("data", nargs="?", choices=["mau", "truong"])
    ap.add_argument("variant", nargs="?", choices=["lns", "bo_trung", "v1", "v2", "v3", "vung_moi",
                                                         "vung_moi_sau", "nhieu"])
    ap.add_argument("limit", nargs="?", type=float, default=1200.0)
    ap.add_argument("--tom-tat", nargs="+", metavar="JSON", help="in bảng theo loại vùng rồi thoát")
    ap.add_argument("--can-duoi", choices=["mau", "truong"], help="cận dưới theo lớp rồi thoát")
    ap.add_argument("--thanh-phan", metavar="JSON", help="chi phí của nghiệm trong file kết quả theo thành phần")
    args = ap.parse_args()
    if args.can_duoi:
        lower_bound(args.can_duoi)
    elif args.thanh_phan:
        breakdown(args.thanh_phan)
    elif args.tom_tat:
        summary(args.tom_tat)
    elif args.data and args.variant:
        run(args.data, args.variant, args.limit)
    else:
        ap.error("cần <dữ liệu> <biến thể> hoặc --tom-tat")
