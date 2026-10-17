"""Lịch cơ sở theo ngày (tkb/lich_co_so.py): GV dạy ở nhiều cơ sở, mỗi ngày chỉ ở một cơ sở theo kế hoạch lập trước khi
xếp giờ; không lập khi trường một cơ sở, sheet LUẬT không có dòng "hạn chế đổi cơ sở trong ngày", hay phép đếm cho thấy
không thể; kế hoạch không xếp được thì xếp như thường."""
from collections import defaultdict

from tkb import config, lich_co_so, luat_co_san, solver
from tkb.checker import check
from tkb.program import read_program
from tkb.rules import applied, read_rules
from tkb.staff import read_staff

from .conftest import CURRICULUM, small_staff
from .test_co_so import THREE, _file

SETTINGS = dict(time_limit=10, workers=4)
TWO = [("3/1", 3, ""), ("3/2", 3, "Điểm Hòa Bình"), ("Lá 1", "Lá", "")]  # Bộ Môn 1 dạy ở cả hai cơ sở


def _school(tmp_path, classes=TWO):
    """Trường nhỏ nhiều cơ sở (tests/test_co_so.py): quy định, nhân sự, chương trình học."""
    path = _file(tmp_path, classes)
    values = read_rules(path)
    with applied(values):
        curriculum = read_program(path)
        staff = read_staff(path, subjects=[s for req in curriculum.values() for s in req])
    return values, staff, curriculum


def _plan(staff, curriculum):
    settings = config.Settings(**SETTINGS)
    _, _, work, fixed, _, _ = solver._assignment(staff, curriculum, settings, lambda *_: None)
    return work, lich_co_so.plan(work, fixed, settings)


def test_each_teacher_is_at_one_campus_a_day(tmp_path):
    values, staff, curriculum = _school(tmp_path)
    with applied(values):
        work, days = _plan(staff, curriculum)
        assert days and all(set(d) == set(config.DAY_SESSIONS) for d in days.values())
        log = []
        sol = solver.solve(staff, curriculum, config.Settings(**SETTINGS), log=log.append)
        assert check(sol.problem, sol.lessons) == []
    assert any("Lịch cơ sở:" in line for line in log) and not any("không theo lịch" in line for line in log)
    where = defaultdict(set)
    for les in sol.problem.taught(sol.lessons):
        at = sol.problem.campus.get(les.class_name, 0)
        where[les.teacher, les.day].add(at)
        assert days.get(les.teacher, {}).get(les.day, at) == at  # đúng kế hoạch
    assert all(len(cs) == 1 for cs in where.values())


def test_no_plan_when_one_campus_a_day_is_impossible(tmp_path):
    """Ba cơ sở: Bộ Môn 1 dạy 4 tiết Toán lớp Lá 1 (tối đa 1 tiết mỗi ngày) và dạy cả hai lớp ở hai cơ sở kia, nên không
    thể mỗi ngày một cơ sở: không lập lịch, xếp như thường (mỗi buổi vẫn một cơ sở)."""
    values, staff, curriculum = _school(tmp_path, THREE)
    with applied(values):
        assert _plan(staff, curriculum)[1] == {}
        log = []
        sol = solver.solve(staff, curriculum, config.Settings(**SETTINGS), log=log.append)
        assert check(sol.problem, sol.lessons) == []
    assert any("mỗi ngày chỉ ở một cơ sở; xếp như thường" in line for line in log)


def test_no_plan_for_one_campus_or_without_the_rule(tmp_path):
    assert _plan(small_staff(), CURRICULUM)[1] == {}  # một cơ sở
    values, staff, curriculum = _school(tmp_path)
    rows = [r for r in values["CUSTOM_RULES"] if luat_co_san.native_of(r).key != "doi_co_so"]
    with applied({**values, "CUSTOM_RULES": rows}):
        assert not lich_co_so.applies() and _plan(staff, curriculum)[1] == {}
    with applied(values):
        assert lich_co_so.applies()


def test_unrealisable_plan_falls_back(tmp_path, monkeypatch):
    """Kế hoạch không xếp được thành giờ (vd mọi GV ở cơ sở đầu mọi ngày): xếp lại không theo kế hoạch."""
    values, staff, curriculum = _school(tmp_path)
    monkeypatch.setattr(lich_co_so, "plan", lambda problem, *_, **__: {
        g: {d: 0 for d in config.DAY_SESSIONS} for g in problem.teachers})
    log = []
    with applied(values):
        sol = solver.solve(staff, curriculum, config.Settings(**SETTINGS), log=log.append)
        assert check(sol.problem, sol.lessons) == []
    assert any("Không xếp được theo lịch cơ sở" in line for line in log)
