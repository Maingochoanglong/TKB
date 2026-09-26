import dataclasses
from collections import Counter

import pytest

from tkb import config
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.solver import assign, distance_to_session_end, solve
from tkb.staff import build_teacher

from .conftest import CURRICULUM, small_staff

FAST = config.Settings(time_limit=20, workers=4)
OVERTIME = dataclasses.replace(FAST, mode=config.MODE_OVERTIME)


@pytest.fixture(scope="module")
def small_solution():
    return solve(small_staff(), CURRICULUM, FAST, log=lambda *_: None)


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
    sol = solve(small_staff(general=False), CURRICULUM, FAST, log=lambda *_: None)
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
    # Tiết 1 giao cho GV khác GVCN.
    j = next(k for k, l in enumerate(lessons) if l.class_name == "3/1" and l.day == 1 and l.period == 1)
    moved = lessons[:j] + [dataclasses.replace(lessons[j], teacher="bộ môn 1")] + lessons[j + 1:]
    assert any("tiết của GVCN" in e for e in check(sol.problem, moved))


def test_homeroom_teaches_first_period(small_solution):
    first = [l for l in small_solution.lessons if l.period in config.HOMEROOM_PERIODS]
    assert len(first) == 2 * len(config.DAYS)
    for les in first:
        assert les.teacher == f"chủ nhiệm {les.class_name}"


def test_heavy_subjects_avoid_last_period(small_solution):
    late = [l for l in small_solution.lessons
            if l.subject in config.HEAVY_SUBJECTS and l.period in config.HEAVY_LATE_PERIODS]
    assert late == []


def test_core_subjects_in_the_morning(small_solution):
    # Khối 3 mỗi lớp TV 7 + Toán 5 = 12 tiết; buổi sáng còn 18 chỗ (trừ 2 tiết HĐTN cố định) nên xếp hết được.
    core = [l for l in small_solution.lessons if l.subject in config.MORNING_SUBJECTS]
    assert len(core) == 2 * 12 and all(l.period in config.MORNING.periods for l in core)
    # Tiết tăng cường nhường buổi sáng cho tiết chính.
    extra = [l for l in small_solution.lessons if l.subject in config.AFTERNOON_SUBJECTS]
    assert extra and all(l.period not in config.MORNING.periods for l in extra)


def test_slot_capacity_limits_assignment():
    # 7 lớp x 4 tiết Tiếng Anh = 28 tiết, nhưng GV tiếng anh chỉ có 26 slot ngoài tiết của GVCN/HĐTN.
    rows = [(f"CN {i}", f"chủ nhiệm 3/{i}", 19) for i in range(1, 8)]
    rows += [("TA", "tiếng anh 1", 30), ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23),
             ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23), ("BM1", "bộ môn 1", 23),
             ("BM2", "bộ môn 2", 23)]
    staff = [build_teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    plan = assign(build_problem(staff, CURRICULUM), FAST)
    assert plan.optimal
    assert {r: n for r, n in plan.counts.items() if n} == {"tiếng anh": 1}
    assert plan.supplement_lessons == 28 - 26


def test_real_data_assignment_is_optimal(real_staff):
    plan = assign(build_problem(real_staff, CURRICULUM), config.Settings(time_limit=80, workers=4))
    assert plan.optimal
    assert plan.supplement_lessons == 52
    assert {r: n for r, n in plan.counts.items() if n} == {config.ROLE_GENERAL: 3}


def test_reproducible_mode_gives_identical_timetables():
    settings = config.Settings(time_limit=10, workers=4, reproducible=True)
    runs = [solve(small_staff(general=False), CURRICULUM, settings, log=lambda *_: None) for _ in range(2)]
    key = [sorted((l.class_name, l.day, l.period, l.subject, l.teacher) for l in r.lessons) for r in runs]
    assert key[0] == key[1]


@pytest.fixture(scope="module")
def overtime_solution():
    settings = dataclasses.replace(OVERTIME, overtime_max=4)
    return solve(small_staff(general=False), CURRICULUM, settings, log=lambda *_: None)


def test_overtime_mode_covers_shortage_without_hiring(overtime_solution):
    sol = overtime_solution
    assert check(sol.problem, sol.lessons) == []
    assert sol.used_supplements() == []
    # Khối 3 mỗi lớp còn TNXH 2 + KNS 1 + Công nghệ 1: GVCN bù hết ở lớp mình.
    assert sol.overtime() == {"chủ nhiệm 3/1": 4, "chủ nhiệm 3/2": 4}


def test_overtime_mode_hires_only_the_remainder():
    sol = solve(small_staff(general=False), CURRICULUM, OVERTIME, log=lambda *_: None)
    assert check(sol.problem, sol.lessons) == []
    assert sol.overtime() == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2}
    assert [t.title for t in sol.used_supplements()] == ["bộ môn 1"]
    assert sol.teacher_load()["bộ môn 1"] == 4


def test_overtime_homeroom_before_general():
    rows = [("CN A", "chủ nhiệm 3/1", 19), ("CN B", "chủ nhiệm 3/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23),
            ("BM", "bộ môn 1", 4)]
    staff = [build_teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    sol = solve(staff, CURRICULUM, OVERTIME, log=lambda *_: None)
    assert check(sol.problem, sol.lessons) == []
    assert sol.used_supplements() == []
    # Thiếu 8 - 4 = 4 tiết: GVCN bù trước, bộ môn không phải bù.
    assert sol.overtime() == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2}


def test_checker_flags_invalid_overtime(overtime_solution):
    sol = overtime_solution
    lessons = list(sol.lessons)
    i = next(k for k, l in enumerate(lessons) if l.class_name == "3/1" and l.subject == config.TIENG_ANH)
    bad = lessons[:i] + [dataclasses.replace(lessons[i], teacher="chủ nhiệm 3/1")] + lessons[i + 1:]
    errors = check(sol.problem, bad)
    assert any("dạy bù" in e for e in errors)
    assert any("vượt định mức 19 + 4 tiết bù" in e for e in errors)


def test_real_data_overtime_assignment(real_staff):
    problem = build_problem(real_staff, CURRICULUM, overtime_max=2)
    plan = assign(problem, config.Settings(time_limit=80, workers=4))
    assert plan.supplement_lessons == 0
    assert sum(plan.overtime.values()) == 52
    # Chỉ GVCN bù (kể cả GVCN 5/5 chỉ có 16 tiết), không ai quá 2 tiết.
    assert all(problem.teachers[g].class_name for g in plan.overtime)
    assert max(plan.overtime.values()) == 2


def split_subjects(lessons):
    """Các buổi có một môn học từ 2 tiết mà không liền nhau: (lớp, ngày, môn, các tiết)."""
    at: dict = {}
    for l in lessons:
        session = next(s.name for s in config.DAY_SESSIONS[l.day] if l.period in s.periods)
        at.setdefault((l.class_name, l.day, session, l.subject), []).append(l.period)
    return [(k, sorted(ps)) for k, ps in at.items() if max(ps) - min(ps) + 1 != len(ps)]


def test_same_subject_lessons_are_contiguous(small_solution, overtime_solution):
    for sol in (small_solution, overtime_solution):
        assert split_subjects(sol.lessons) == []


def test_contiguous_when_a_subject_must_repeat_in_a_session():
    # Khối 1 học 14 tiết Tiếng Việt trong 9 buổi: buộc phải có buổi học 2 tiết TV, và 2 tiết đó phải liền.
    rows = [("CN A", "chủ nhiệm 1/1", 19), ("CN B", "chủ nhiệm 1/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("BM", "bộ môn 1", 23)]
    staff = [build_teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    sol = solve(staff, CURRICULUM, FAST, log=lambda *_: None)
    assert check(sol.problem, sol.lessons) == []
    pairs = Counter((l.class_name, l.day, l.period < 5, l.subject) for l in sol.lessons if l.subject == config.TV)
    assert sum(1 for n in pairs.values() if n == 2) >= 2 * 5
    assert split_subjects(sol.lessons) == []


def test_checker_detects_split_subject(small_solution):
    lessons = list(small_solution.lessons)
    grid = {(l.class_name, l.day, l.period): i for i, l in enumerate(lessons)}
    # Tìm môn học 2 tiết liền (p, p+1) rồi tráo một tiết với tiết kề bên cùng buổi để tạo mẫu so le.
    found = None
    for (cls, d, p), i in grid.items():
        j = grid.get((cls, d, p + 1))
        if j is None or lessons[i].subject != lessons[j].subject:
            continue
        periods = next(s.periods for s in config.DAY_SESSIONS[d] if p in s.periods)
        if p + 1 not in periods:
            continue
        for other, moved, keep in ((p + 2, j, p), (p - 1, i, p + 1)):
            k = grid.get((cls, d, other))
            if other in periods and k is not None and lessons[k].subject != lessons[i].subject:
                found = (moved, k, sorted([keep, other]))
                break
        if found:
            break
    assert found, "TKB phải có ít nhất một môn học 2 tiết liền"
    moved, k, periods = found
    subject = lessons[moved].subject
    a, b = lessons[moved], lessons[k]
    lessons[moved] = dataclasses.replace(a, period=b.period)
    lessons[k] = dataclasses.replace(b, period=a.period)
    errors = check(small_solution.problem, lessons)
    assert any(f"môn {subject} không học liền (tiết {periods[0]}, {periods[1]})" in e for e in errors)
    assert not any("không học liền" in e for e in check(small_solution.problem, lessons, student_rules=False))


def test_checker_requires_homeroom_to_cover_own_class_first():
    rows = [("CN A", "chủ nhiệm 3/1", 19), ("CN B", "chủ nhiệm 3/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23),
            ("BM", "bộ môn 1", 4)]
    staff = [build_teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    sol = solve(staff, CURRICULUM, OVERTIME, log=lambda *_: None)
    assert check(sol.problem, sol.lessons) == []
    assert sol.overtime() == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2}
    # Chuyển một tiết bù của GVCN 3/1 sang bộ môn: bộ môn phải bù trong khi GVCN 3/1 còn quyền bù.
    lessons = list(sol.lessons)
    i = next(k for k, l in enumerate(lessons)
             if l.teacher == "chủ nhiệm 3/1" and not sol.problem.courses[l.course_id].homeroom)
    lessons[i] = dataclasses.replace(lessons[i], teacher="bộ môn 1")
    errors = check(sol.problem, lessons)
    assert any("bộ môn 1 dạy bù 1 tiết trong khi chủ nhiệm 3/1 còn được bù 1 tiết" in e for e in errors)
