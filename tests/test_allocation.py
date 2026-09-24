import pytest

from tkb import config
from tkb.allocation import build_problem, split_homeroom
from tkb.staff import InputError

C = config


def test_homeroom_split_real(real_staff):
    p = build_problem(real_staff)
    take = p.homeroom_take
    assert take["1/1"] == {C.TV: 10, C.TOAN: 5, C.HDTN: 3, C.DD: 1}  # cắt 4 tiết TV
    assert take["2/1"] == {C.TV: 10, C.TOAN: 5, C.HDTN: 3, C.DD: 1}  # vừa đủ 19
    assert take["3/1"][C.TV_TC] == 1 and take["3/1"][C.TOAN_TC] == 2  # bù TV TC rồi Toán TC
    assert take["4/1"][C.TV] == 6  # cắt 1 tiết TV
    assert take["5/5"][C.TV] == 3 and sum(take["5/5"].values()) == 16  # GVCN thai sản 16 tiết
    for cls, t in take.items():
        quota = next(x.max_lessons for x in real_staff if x.class_name == cls)
        assert sum(t.values()) == quota
        assert t[C.DD] == 1 and t[C.HDTN] == 3


def test_fill_order_never_takes_specialist_subjects():
    req = config.DEFAULT_CURRICULUM[3]
    take = split_homeroom("3/1", req, 30, reserved=set())
    for s in (C.TV_TC, C.TOAN_TC, C.TNXH, C.KNS, C.CONG_NGHE):
        assert take[s] == req[s]
    for s in (C.TIENG_ANH, C.TIN_HOC, C.THE_DUC, C.AM_NHAC, C.MY_THUAT):
        assert s not in take
    assert sum(take.values()) == 23


def test_fill_order_priority():
    req = config.DEFAULT_CURRICULUM[3]
    take = split_homeroom("3/1", req, 17, reserved=set())  # thiếu 1 -> TV TC trước
    assert take.get(C.TV_TC) == 1 and C.TOAN_TC not in take
    take = split_homeroom("3/1", req, 18, reserved=set())  # thiếu 2 -> TV TC rồi Toán TC
    assert take.get(C.TV_TC) == 1 and take.get(C.TOAN_TC) == 1
    take = split_homeroom("3/1", req, 21, reserved={C.TNXH})  # môn dành riêng không bị lấy
    assert C.TNXH not in take and take[C.KNS] == 1 and take[C.CONG_NGHE] == 1


def test_cut_only_multi_lesson_subjects():
    req = config.DEFAULT_CURRICULUM[1]
    take = split_homeroom("1/1", req, 6, reserved=set())
    assert take == {C.TV: 1, C.TOAN: 1, C.HDTN: 3, C.DD: 1}
    with pytest.raises(InputError):
        split_homeroom("1/1", req, 5, reserved=set())


def test_permissions(real_staff):
    p = build_problem(real_staff)
    for c in p.courses:
        roles = {p.teachers[t].role for t in c.teachers}
        if c.subject == C.HDTN:
            assert c.homeroom and p.teachers[c.teachers[0]].class_name == c.class_name
        if c.homeroom:
            continue
        if c.subject in (C.TIENG_ANH, C.TIN_HOC):
            assert roles == {r for r, s in config.SPECIALIST_ROLES.items() if s == c.subject}
        if c.subject in (C.THE_DUC, C.AM_NHAC, C.MY_THUAT):
            assert config.ROLE_GENERAL in roles
        if config.ROLE_MANAGER in roles:
            assert c.subject == C.KNS and c.grade == 4
    manager_courses = [c for c in p.courses if "quản lý 1" in c.teachers]
    assert len(manager_courses) == 6 and p.manager_load == {"quản lý 1": 4}


def test_supplement_numbering(real_staff):
    p = build_problem(real_staff, supplement_counts={config.ROLE_GENERAL: 2, "tin học": 1})
    assert p.supplement_roles[config.ROLE_GENERAL] == ["bộ môn 6", "bộ môn 7"]
    assert p.supplement_roles["tin học"] == ["tin học 2"]
    t = p.teachers["bộ môn 6"]
    assert t.name == config.SUPPLEMENT_NAME and t.supplementary and t.max_lessons == 23
