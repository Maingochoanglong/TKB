import dataclasses
from collections import Counter

import pytest

from tkb import config
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.phan_cong import phan_cong, tach_tiet_bu
from tkb.solver import ShortageError, distance_to_session_end, solve

from .conftest import CURRICULUM, small_staff, teacher

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


def test_extra_lessons_after_main_lessons(small_solution):
    # Tiết tăng cường: trong ngày có tiết chính cùng nhóm đứng trước, không có tiết chính nào đứng sau.
    lessons = small_solution.lessons
    extra = [l for l in lessons if l.subject in config.SUBJECT_GROUPS]
    assert len(extra) == 2 * (2 + 1)  # khối 3: Toán TC 2 + TV TC 1 mỗi lớp
    for l in extra:
        mains = [m.period for m in lessons if m.class_name == l.class_name and m.day == l.day
                 and m.subject == config.SUBJECT_GROUPS[l.subject]]
        assert mains and max(mains) < l.period


def test_checker_flags_extra_lesson_before_main(small_solution):
    sol = small_solution
    lessons = sol.lessons
    e = next(l for l in lessons if l.subject == config.TOAN_TC)
    main = next(l for l in lessons if l.class_name == e.class_name and l.day == e.day and l.subject == config.TOAN)
    swapped = [dataclasses.replace(l, period=main.period) if l is e
               else dataclasses.replace(l, period=e.period) if l is main else l for l in lessons]
    assert any("phải sau các tiết Toán" in err for err in check(sol.problem, swapped))


def test_slot_capacity_limits_assignment():
    # 7 lớp x 4 tiết Tiếng Anh = 28 tiết, nhưng GV tiếng anh chỉ có 26 slot ngoài tiết của GVCN/HĐTN.
    rows = [(f"CN {i}", f"chủ nhiệm 3/{i}", 19) for i in range(1, 8)]
    rows += [("TA", "tiếng anh 1", 30), ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23),
             ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23), ("BM1", "bộ môn 1", 23),
             ("BM2", "bộ môn 2", 23)]
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    problem = build_problem(staff, CURRICULUM, {}, overtime_max=2)
    plan = phan_cong(problem, FAST.weights)
    assert plan.missing_total() == 28 - 26
    assert {problem.courses[cid].subject for cid in plan.missing} == {config.TIENG_ANH}
    split = tach_tiet_bu(problem, plan, staff, include_missing=True)
    assert {r: len(g) for r, g in split.items()} == {"tiếng anh": 1}


def test_sample_school_hires_take_the_overtime_lessons(sample_staff):
    problem = build_problem(sample_staff, CURRICULUM, {}, overtime_max=2)
    plan = phan_cong(problem, FAST.weights)
    split = tach_tiet_bu(problem, plan, sample_staff, include_missing=True)
    assert plan.missing_total() == 0
    assert [sum(n for _, _, n in g) for g in split[config.ROLE_GENERAL]] == [18, 18, 16]  # 52 tiết bù, 3 người mới


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


def test_overtime_mode_never_hires_and_reports_the_shortage():
    with pytest.raises(ShortageError) as err:
        solve(small_staff(general=False), CURRICULUM, OVERTIME, log=lambda *_: None)
    rows = err.value.rows()
    assert sum(n for _, _, n, _ in rows) == 4 and {r[0] for r in rows} == {"3/1", "3/2"}
    assert all("bù tối đa +2" in reason for *_, reason in rows)


def test_hire_mode_uses_the_overtime_timetable(overtime_solution):
    """Chế độ tuyển cùng TKB với chế độ bù; người mới dạy đúng các ô bù."""
    hire = solve(small_staff(general=False), CURRICULUM, dataclasses.replace(FAST, overtime_max=4),
                 log=lambda *_: None)
    assert check(hire.problem, hire.lessons) == []
    at = lambda sol: {(l.class_name, l.day, l.period): l for l in sol.lessons}  # noqa: E731
    a, b = at(overtime_solution), at(hire)
    assert {k: v.subject for k, v in a.items()} == {k: v.subject for k, v in b.items()}
    hires = {t.title for t in hire.used_supplements()}
    changed = {k for k in a if a[k].teacher != b[k].teacher}
    assert changed == {k for k in b if b[k].teacher in hires}
    assert all(not overtime_solution.problem.courses[a[k].course_id].homeroom and
               a[k].teacher == f"chủ nhiệm {k[0]}" for k in changed)
    assert len(changed) == sum(overtime_solution.overtime().values()) == 8


def test_overtime_homeroom_before_general():
    rows = [("CN A", "chủ nhiệm 3/1", 19), ("CN B", "chủ nhiệm 3/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23),
            ("BM", "bộ môn 1", 4)]
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
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


def test_sample_school_overtime_assignment(sample_staff):
    problem = build_problem(sample_staff, CURRICULUM, {}, overtime_max=2)
    plan = phan_cong(problem, FAST.weights)
    assert plan.missing_total() == 0
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
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
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
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
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


def test_checker_flags_new_teacher_rules(overtime_solution):
    sol = overtime_solution
    lessons = list(sol.lessons)
    grid = {(l.class_name, l.day, l.period): i for i, l in enumerate(lessons)}
    # Liên tiết do 2 người: đổi người dạy một tiết trong cặp TV liền nhau.
    i = next(i for (c, d, p), i in grid.items() if lessons[i].subject == config.TV
             and (j := grid.get((c, d, p + 1))) is not None and lessons[j].subject == config.TV and p != 4)
    bad = list(lessons)
    bad[i] = dataclasses.replace(bad[i], teacher="tiếng anh 1")
    errors = check(sol.problem, bad)
    assert any("do 2 người dạy" in e for e in errors)
    # Toán 2 tiết trong một ngày.
    t = [i for i, l in enumerate(lessons) if l.class_name == "3/1" and l.subject == config.TOAN]
    other = next(i for i, l in enumerate(lessons) if l.class_name == "3/1" and l.day == lessons[t[0]].day
                 and l.subject not in (config.TOAN, config.HDTN) and l.period != 1)
    bad = list(lessons)
    bad[t[1]], bad[other] = (dataclasses.replace(bad[t[1]], day=bad[other].day, period=bad[other].period),
                             dataclasses.replace(bad[other], day=bad[t[1]].day, period=bad[t[1]].period))
    assert any("tiết Toán (tối đa 1 mỗi ngày)" in e for e in check(sol.problem, bad))
    assert not any("mỗi ngày" in e for e in check(sol.problem, bad, student_rules=False))


def test_checker_flags_other_teacher_before_homeroom(small_solution):
    sol = small_solution
    lessons = list(sol.lessons)
    # Tiết TV đầu tuần của lớp 3/1 giao cho bộ môn: người khác dạy trước GVCN.
    i = min((i for i, l in enumerate(lessons) if l.class_name == "3/1" and l.subject == config.TV and l.period != 1),
            key=lambda i: (lessons[i].day, lessons[i].period))
    first = min((l.day, l.period) for l in lessons if l.class_name == "3/1" and l.subject == config.TV)
    bad = list(lessons)
    bad[i] = dataclasses.replace(bad[i], teacher="bộ môn 1")
    if (lessons[i].day, lessons[i].period) == first:
        assert any("trước tiết đầu tuần của GVCN" in e for e in check(sol.problem, bad))


def test_vietnamese_is_paired_in_grade_one():
    rows = [("CN A", "chủ nhiệm 1/1", 19), ("CN B", "chủ nhiệm 1/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("BM", "bộ môn 1", 23)]
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    sol = solve(staff, CURRICULUM, FAST, log=lambda *_: None)
    assert check(sol.problem, sol.lessons) == []
    per_session = Counter((l.class_name, l.day, l.period < 5) for l in sol.lessons if l.subject == config.TV)
    assert set(per_session.values()) == {2}  # 14 tiết = 7 cặp liền, mỗi cặp một người dạy
