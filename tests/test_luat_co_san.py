"""Luật có sẵn viết bằng bộ ghép (tkb/luat_co_san.py): kiểm chéo với bộ kiểm tra độc lập, và hạ bằng bộ ghép thay
cho bản gốc vẫn cho TKB đúng luật."""
import random
from dataclasses import replace

import pytest

from tkb import bo_ghep, checker, config, solver
from tkb.luat_co_san import GROUPS, co_san
from tkb.rules import applied

from .conftest import CURRICULUM, small_staff

SETTINGS = dict(time_limit=5, workers=4, overtime_max=4)


@pytest.fixture(scope="module")
def plain():
    return solver.solve(small_staff(general=False), CURRICULUM,
                        config.Settings(mode=config.MODE_OVERTIME, **SETTINGS), log=lambda *_: None)


def _hard(problem):
    return [c for c in co_san(problem) if c.hard and c.rule is not None]


def _found(problem, lessons, items) -> list:
    return bo_ghep.violations(problem, lessons, rules=[c.rule for c in items], skip_forced=False)


def test_every_rule_has_a_sentence_and_a_group(plain):
    items = co_san(plain.problem)
    assert {c.group for c in items} <= set(GROUPS) and all(c.sentence() and c.source for c in items)
    assert sum(1 for c in items if c.rule is not None) >= 12  # phần lớn viết được bằng bộ ghép
    # Không có lớp cơ sở 2 thì không có luật cơ sở; tắt luật bảo vệ học sinh thì không có nhóm đó.
    assert not any("cơ sở" in c.text for c in items)
    assert not any(c.group == "Bảo vệ học sinh" for c in co_san(plain.problem, config.Settings(student_rules=False)))
    # Quy định của file chỉnh luôn câu luật.
    with applied({"SESSION_GROUP_LIMIT": 3}):
        assert any(c.text.endswith("số tiết tối đa 3") for c in co_san(plain.problem))


def test_solved_timetable_keeps_every_built_in_rule(plain):
    assert checker.check(plain.problem, plain.lessons) == []
    assert _found(plain.problem, plain.lessons, _hard(plain.problem)) == []


def test_cross_check_with_the_checker(plain):
    """Đổi chỗ hai tiết của một lớp: luật có sẵn nào bộ ghép thấy bị vi phạm thì bộ kiểm tra độc lập cũng báo lỗi;
    bộ kiểm tra thấy lỗi luật bảo vệ học sinh thì bộ ghép cũng thấy ở nhóm Bảo vệ học sinh."""
    rnd = random.Random(0)
    items = _hard(plain.problem)
    student = [c for c in items if c.group == "Bảo vệ học sinh"]
    hits = 0
    for _ in range(40):
        les = list(plain.lessons)
        cls = rnd.choice(plain.problem.classes)
        i, j = rnd.sample([k for k, l in enumerate(les) if l.class_name == cls], 2)
        a, b = les[i], les[j]
        les[i] = replace(a, day=b.day, period=b.period)
        les[j] = replace(b, day=a.day, period=a.period)
        found = _found(plain.problem, les, items)
        errors = checker.check(plain.problem, les)
        assert not found or errors
        if checker._check_student_rules(plain.problem, les):
            assert _found(plain.problem, les, student)
            hits += 1
    assert hits >= 5  # phép thử có làm hỏng luật bảo vệ học sinh


def test_generic_lowering_replaces_the_native_one():
    """Tắt bản gốc của "các tiết cùng môn liền nhau" và "tiết tăng cường sau tiết chính" (cờ solver.RELAXED), thay
    bằng chính các câu đó hạ qua bộ ghép: TKB vẫn qua bộ kiểm tra độc lập (kiểm theo bản gốc)."""
    staff = small_staff(general=False)
    problem = solver.build_problem(staff, CURRICULUM)
    rules = [c.rule for c in co_san(problem) if c.rule is not None and c.rule.measure in ("lien", "thu_tu", "di_kem")]
    assert len(rules) == 5
    old = solver.RELAXED
    solver.RELAXED = frozenset({"lien_nhau", "tang_cuong"})
    try:
        with applied({"CUSTOM_RULES": [replace(r, row=i + 2) for i, r in enumerate(rules)]}):
            sol = solver.solve(staff, CURRICULUM, config.Settings(mode=config.MODE_OVERTIME, **SETTINGS),
                               log=lambda *_: None)
    finally:
        solver.RELAXED = old
    assert checker.check(sol.problem, sol.lessons) == []
