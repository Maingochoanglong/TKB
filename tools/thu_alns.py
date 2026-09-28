"""Thử nghiệm ALNS (docs/Nghien_Cuu_ALNS.md): đo LNS hiện tại theo loại vùng, so với các nguyên mẫu ALNS.

Không đổi tkb/: mọi biến thể dùng lại lns._Search (khởi đầu, xếp lại một vùng, QA, danh sách vùng).

  python tools/thu_alns.py mau lns             trường mẫu tên giả (tests/du_lieu_mau.py), LNS hiện tại, 1200
  python tools/thu_alns.py truong v2 600       FILE_VAO của main.py (chỉ in chi phí và loại vùng, không in tên)
  python tools/thu_alns.py --tom-tat out/thu_alns/*.json      bảng theo loại vùng

Biến thể:
  lns       LNS hiện tại (lns.improve).
  bo_trung  LNS hiện tại, bỏ lần xếp lại y hệt (cùng vùng, cùng giới hạn, cùng nghiệm đầu vào): CP-SAT tất định
            nên lần đó chắc chắn không giảm; ra cùng TKB, chỉ bớt ngân sách.
  v1        ALNS từ đầu: roulette theo loại vùng, vùng xấu nhất (QA) chưa tabu của loại đó.
  v2        Vòng 1 như LNS hiện tại, rồi roulette theo loại vùng, vùng ngẫu nhiên, vùng hết giờ thì gấp đôi giới hạn.
  v3        Vòng 1 như LNS hiện tại, rồi ALNS có mô phỏng luyện kim: buộc đổi ít nhất một tiết trong vùng.
Hằng số lấy từ main.py (SO_LUONG, SO_TIET_BU_TOI_DA, LUAT_HOC_SINH), chế độ tái lập. Kết quả ghi
out/thu_alns/<dữ liệu>_<biến thể>_<ngân sách>.json; bước khởi đầu (tất định, như nhau ở mọi biến thể) lưu ở
out/thu_alns/khoi_dau_<dữ liệu>_<ngân sách>.json để lần sau khỏi giải lại (xóa file này khi đổi mô hình).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ortools.sat.python import cp_model  # noqa: E402

import main  # noqa: E402
from tkb import config, lns  # noqa: E402
from tkb.allocation import build_problem  # noqa: E402
from tkb.phan_cong import phan_cong, tach_tiet_bu  # noqa: E402
from tkb.solver import _hire_assignment, build_timetable  # noqa: E402

OUT = ROOT / "out" / "thu_alns"
KINDS = ["lớp", "điểm nóng", "GV dùng chung", "khối", "cặp ngày"]
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
    return build_timetable(work, settings, fixed=fixed)


def measuring_search(cache: Path, records: list, skip_repeats: bool = False):
    """Lớp con của lns._Search ghi từng lần xếp lại vào `records` và lưu/đọc lại bước khởi đầu từ `cache`."""

    class _Fake:  # thay CpSolver khi đọc khởi đầu từ cache: chỉ cần Value(phần chi phí phân công)
        def __init__(self, offset):
            self.offset = offset

        def Value(self, _):
            return self.offset

    class Search(lns._Search):
        started = False

        def regions(self, cost, lessons):
            out = super().regions(cost, lessons)
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

    Search = measuring_search(OUT / f"khoi_dau_{data}_{limit:g}.json", records, skip_repeats=variant == "bo_trung")
    start = time.time()
    if variant in ("lns", "bo_trung"):
        original, lns._Search = lns._Search, Search
        try:
            res = lns.improve(tm, settings, log)
        finally:
            lns._Search = original
    else:
        res = {"v1": v1, "v2": v2, "v3": v3}[variant](tm, settings, log, Search)
    out = OUT / f"{data}_{variant}_{limit:g}.json"
    out.write_text(json.dumps(dict(
        data=data, variant=variant, limit=limit, history=res.history, used=res.used, stop=res.stop,
        wall=time.time() - start, logs=logs, records=records,
        values=hashlib.sha1(repr(res.values).encode()).hexdigest()), ensure_ascii=False, indent=0))
    print(f"{data} {variant} {limit:g}: chi phí {' -> '.join(map(str, res.history))}, dùng {res.used:.0f}, "
          f"{time.time() - start:.0f} giây. Ghi {out.relative_to(ROOT)}")
    return out


def summary(paths: list[str]) -> None:
    """Bảng theo loại vùng: số lần, số lần giảm, tổng giảm, ngân sách, giảm/đơn vị, số vùng chứng minh xong."""
    for p in paths:
        d = json.loads(Path(p).read_text())
        start = json.loads((OUT / f"khoi_dau_{d['data']}_{d['limit']:g}.json").read_text())
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
        for k in KINDS:
            if k in agg:
                n, imp, gain, dt, opt, skip = agg[k]
                print(f"  {k:14} {n:4} {imp:4} {gain:9.0f} {dt:9.1f} {100 * dt / total:4.0f} "
                      f"{gain / max(dt, 1e-9):8.1f} {opt:10} {skip:8}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("data", nargs="?", choices=["mau", "truong"])
    ap.add_argument("variant", nargs="?", choices=["lns", "bo_trung", "v1", "v2", "v3"])
    ap.add_argument("limit", nargs="?", type=float, default=1200.0)
    ap.add_argument("--tom-tat", nargs="+", metavar="JSON", help="in bảng theo loại vùng rồi thoát")
    args = ap.parse_args()
    if args.tom_tat:
        summary(args.tom_tat)
    elif args.data and args.variant:
        run(args.data, args.variant, args.limit)
    else:
        ap.error("cần <dữ liệu> <biến thể> hoặc --tom-tat")
