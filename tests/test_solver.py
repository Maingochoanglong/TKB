import dataclasses

import pytest

from tkb import config
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.solver import assign, distance_to_session_end, solve

from .conftest import small_staff

FAST = config.Settings(time_limit=20, workers=4)


@pytest.fixture(scope="module")
def small_solution():
    return solve(small_staff(), None, FAST, log=lambda *_: None)


def test_small_school_solves_and_passes_checker(small_solution):
    sol = small_solution
    assert check(sol.problem, sol.lessons) == []
    assert len(sol.lessons) == 2 * 32
    assert sol.used_supplements() == []


def test_hdtn_fixed_and_flex(small_solution):
    for cls in ("3/1", "3/2"):
        slots = sorted((l.day, l.period) for l in small_solution.lessons
                       if l.class_name == cls and l.subject == config.HDTN)
        assert (0, 1) in slots and (4, 4) in slots and len(slots) == 3
        flex = [s for s in slots if s not in config.HDTN_FIXED_SLOTS][0]
        assert flex[0] in config.HDTN_FLEX_DAYS
        assert distance_to_session_end(flex) == 0  # cuối buổi


def test_missing_general_teacher_becomes_supplement():
    sol = solve(small_staff(general=False), None, FAST, log=lambda *_: None)
    assert check(sol.problem, sol.lessons) == []
    extra = sol.used_supplements()
    assert [t.title for t in extra] == ["bộ môn 1"]
    assert extra[0].name == config.SUPPLEMENT_NAME
    # Khối 3 mỗi lớp còn TNXH 2 + KNS 1 + Công nghệ 1 cho bộ môn.
    assert sol.teacher_load()["bộ môn 1"] == 8


def test_checker_detects_violations(small_solution):
    sol = small_solution
    lessons = list(sol.lessons)
    # GVCN lớp 3/2 dạy sang lớp 3/1.
    i = next(k for k, l in enumerate(lessons) if l.class_name == "3/1" and l.subject == config.TV)
    bad = lessons[:i] + [dataclasses.replace(lessons[i], teacher="chủ nhiệm 3/2")] + lessons[i + 1:]
    errors = check(sol.problem, bad)
    assert any("không phải GVCN" in e for e in errors)
    assert any("cùng lúc" in e or "GVCN dạy" in e for e in errors)
    # Môn nặng ở tiết 7.
    j = next(k for k, l in enumerate(lessons) if l.period == 7)
    k = next(k for k, l in enumerate(lessons) if l.class_name == lessons[j].class_name
             and l.subject == config.TOAN and l.period != 7)
    swapped = list(lessons)
    swapped[j] = dataclasses.replace(lessons[j], period=lessons[k].period, day=lessons[k].day)
    swapped[k] = dataclasses.replace(lessons[k], period=7, day=lessons[j].day)
    assert any("môn nặng" in e for e in check(sol.problem, swapped))


def test_real_data_assignment_is_optimal(real_staff):
    plan = assign(build_problem(real_staff), config.Settings(time_limit=80, workers=4))
    assert plan.optimal
    assert plan.supplement_lessons == 52
    assert {r: n for r, n in plan.counts.items() if n} == {config.ROLE_GENERAL: 3}
