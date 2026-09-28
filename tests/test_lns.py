"""Xếp giờ: CP-SAT khởi đầu rồi xếp lại từng vùng (tkb/lns.py). Dùng trường mẫu tên giả: trường nhỏ giải tối ưu
ngay ở bước khởi đầu nên không qua vòng xếp lại."""
import os
import subprocess
import sys
from pathlib import Path

from tkb import config, lns
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.phan_cong import phan_cong, tach_tiet_bu
from ortools.sat.python import cp_model

from tkb.solver import _hire_assignment, build_timetable, cost_breakdown

from .conftest import CURRICULUM, small_staff

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = config.Settings(time_limit=15, workers=4, mode=config.MODE_OVERTIME, overtime_max=2)


def _model(staff, settings=SETTINGS):
    """Mô hình xếp giờ với phân công cố định, như solver.solve dựng."""
    base = build_problem(staff, CURRICULUM, {}, overtime_max=settings.overtime_max)
    plan = phan_cong(base, settings.weights)
    split = tach_tiet_bu(base, plan, staff, include_missing=False)
    work = build_problem(staff, CURRICULUM, {role: len(g) for role, g in split.items()}, overtime_max=0)
    fixed, _ = _hire_assignment(plan, work, split)
    return build_timetable(work, settings, fixed=fixed)


def test_rounds_never_worsen_and_respect_the_budget(sample_staff):
    tm = _model(sample_staff)
    res = lns.improve(tm, SETTINGS)
    assert res.status == "FEASIBLE" and len(res.history) >= 2  # có ít nhất một vòng xếp lại
    assert res.history == sorted(res.history, reverse=True) and res.history[-1] < res.history[0]
    assert res.used <= SETTINGS.time_limit + 1
    assert res.stop in ("hết thời gian", "vòng sau cùng không còn cải thiện đáng kể")
    assert check(tm.problem, tm.lessons(lambda v: res.values[v.Index()])) == []


def test_region_moves_only_the_open_cells(sample_staff):
    tm = _model(sample_staff)
    search = lns._Search(tm, SETTINGS, lambda *_: None)
    _, start, values, _, _ = search.solve(tm.model, 3)
    free = search.free(["1/1"], sorted(config.DAY_SESSIONS))
    _, val, new, _, _ = search.region(free, 5, values)
    assert val <= start  # xuất phát từ nghiệm đang có nên không tệ hơn
    assert all(new[i] == values[i] for i in search.decision if i not in free)
    assert any(new[i] != values[i] for i in free) or val == start


def test_ctrl_c_stops_after_the_current_region(sample_staff, monkeypatch):
    region = lns._Search.region

    def interrupted(self, *a, **k):
        out = region(self, *a, **k)
        self.interrupted = True  # như bấm Ctrl+C trong lúc xếp lại vùng này
        return out

    monkeypatch.setattr(lns._Search, "region", interrupted)
    tm = _model(sample_staff)
    res = lns.improve(tm, SETTINGS)
    assert res.stop == "Ctrl+C" and len(res.history) == 2
    assert check(tm.problem, tm.lessons(lambda v: res.values[v.Index()])) == []


def test_same_timetable_in_new_processes():
    """Thứ tự vùng và ngân sách tất định: tiến trình mới, thứ tự băm khác vẫn ra cùng TKB."""
    script = ("from tkb import config; from tkb.solver import solve; "
              "from tests.du_lieu_mau import CURRICULUM, sample_staff; "
              "s = config.Settings(time_limit=12, workers=4, mode=config.MODE_OVERTIME, overtime_max=2); "
              "print(solve(sample_staff(), CURRICULUM, s, log=lambda *_: None).fingerprint())")
    codes = {subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED=seed),
                            capture_output=True, text=True, check=True).stdout for seed in ("1", "2")}
    assert len(codes) == 1 and next(iter(codes)).strip()



def test_unchanged_regions_are_not_solved_again(sample_staff, monkeypatch):
    """Vùng đã xếp lại trên đúng nghiệm hiện tại thì vòng sau bỏ qua (CP-SAT tất định: giải lại ra y hệt)."""
    names, calls = [], []
    regions, region = lns._Search.regions, lns._Search.region

    def recorded_regions(self, cost, lessons):
        out = regions(self, cost, lessons)
        names.append([name for _, name, _, _ in out])
        self.name_of = {id(free): name for _, name, free, _ in out}
        return out

    def fake_region(self, free, seconds, best):
        calls.append(self.name_of[id(free)])
        if len(calls) == 1:  # vùng đầu tiên giảm rất mạnh, các vùng khác không giảm
            return cp_model.FEASIBLE, -1e12, list(best), None, None
        return cp_model.FEASIBLE, None, None, None, None

    monkeypatch.setattr(lns._Search, "regions", recorded_regions)
    monkeypatch.setattr(lns._Search, "region", fake_region)
    res = lns.improve(_model(sample_staff), SETTINGS)
    assert len(names) == 2 and names[0] == names[1]
    # Vòng 1 giải mọi vùng; vòng 2 chỉ giải lại vùng đầu (lần trước nó được giải trên nghiệm cũ), rồi dừng.
    assert calls == names[0] + names[0][:1]
    assert res.stop == "vòng sau cùng không còn cải thiện đáng kể"


def test_cost_breakdown_adds_up_to_the_timetabling_cost():
    """Chi phí theo thành phần (solver.cost_breakdown) cộng lại đúng bằng chi phí xếp giờ của nghiệm tối ưu."""
    settings = config.Settings(time_limit=5, workers=4, mode=config.MODE_OVERTIME, overtime_max=4)
    tm = _model(small_staff(general=False), settings)
    res = lns.improve(tm, settings)
    assert res.status == "OPTIMAL"
    costs = cost_breakdown(tm.problem, tm.lessons(lambda v: res.values[v.Index()]), settings.weights)
    assert [c[0] for c in costs] == ["morning_core", "heavy_late", "extra_morning", "hdtn_flex", "spread",
                                     "day_load", "teacher_gap", "extra_after_main"]
    assert sum(c[-1] for c in costs) == res.history[-1]
