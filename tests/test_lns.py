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
from tkb.solver import _hire_assignment, build_timetable

from .conftest import CURRICULUM

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

