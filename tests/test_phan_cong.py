from collections import Counter

from tkb import bo_mau, config
from tkb.allocation import build_problem
from tkb.phan_cong import MinCostFlow, phan_cong, tach_tiet_bu

from .conftest import CURRICULUM, small_staff, teacher

W = config.Weights()


def _problem(staff, overtime_max=2):
    return build_problem(staff, CURRICULUM, {}, overtime_max=overtime_max)


def test_min_cost_flow_prefers_cheap_paths():
    # Nguồn 4 cấp 3 đơn vị cho 0; 0 -> 1 -> 3 giá 1 (chứa 2), 0 -> 2 -> 3 giá 5: 2 đơn vị đi đường rẻ.
    f = MinCostFlow(5)
    s0 = f.add(4, 0, 3, 0)
    a = f.add(0, 1, 2, 1)
    b = f.add(0, 2, 5, 5)
    f.add(1, 3, 2, 0)
    f.add(2, 3, 5, 0)
    f.run(4, 3)
    assert (f.used(s0), f.used(a), f.used(b)) == (3, 2, 1)


def test_estimate_overtime_then_missing():
    # Trường nhỏ không có bộ môn: mỗi lớp khối 3 còn TNXH 2 + KNS 1 + Công nghệ 1 ngoài phần GVCN.
    plan = phan_cong(_problem(small_staff(general=False), 2), W)
    assert plan.overtime == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2}
    assert plan.missing_total() == 4 and plan.overtime_cap == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2}
    plan = phan_cong(_problem(small_staff(general=False), 4), W)
    assert plan.overtime == {"chủ nhiệm 3/1": 4, "chủ nhiệm 3/2": 4} and plan.missing_total() == 0


def test_homeroom_overtime_before_general():
    rows = [("CN A", "chủ nhiệm 3/1", 19), ("CN B", "chủ nhiệm 3/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23),
            ("BM", "bộ môn 1", 4)]
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    plan = phan_cong(_problem(staff), W)
    assert plan.overtime == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2} and plan.missing_total() == 0


def test_homeroom_overtime_takes_whole_subjects():
    # Bù +1: GVCN nhận trọn một môn 1 tiết (KNS hoặc Công nghệ) thay vì chia đôi TNXH 2 tiết.
    rows = [("CN A", "chủ nhiệm 3/1", 19), ("CN B", "chủ nhiệm 3/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23),
            ("BM", "bộ môn 1", 6)]
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    problem = _problem(staff)
    plan = phan_cong(problem, W)
    assert plan.overtime == {"chủ nhiệm 3/1": 1, "chủ nhiệm 3/2": 1}
    for (cid, g), n in plan.extra.items():
        assert n == problem.courses[cid].lessons  # không chia môn


def test_homeroom_overtime_takes_music_and_art():
    # Không có bộ môn; GV Âm nhạc, Mỹ thuật mỗi người chỉ 1 tiết cho 2 lớp: tiết còn lại do GVCN dạy bù.
    staff = [t for t in small_staff(general=False) if t.role not in ("âm nhạc", "mỹ thuật")]
    staff += [teacher("AN", "âm nhạc 1", 1, row=20), teacher("MT", "mỹ thuật 1", 1, row=21)]
    problem = _problem(staff, 5)
    plan = phan_cong(problem, W)
    assert plan.missing_total() == 0
    extra = Counter(problem.courses[cid].subject for (cid, g) in plan.extra if problem.teachers[g].class_name)
    assert extra[bo_mau.AM_NHAC] == 1 and extra[bo_mau.MY_THUAT] == 1
    assert not {bo_mau.TIENG_ANH, bo_mau.TIN_HOC, "Thể dục"} & set(extra)


def test_assignment_is_deterministic():
    a = phan_cong(_problem(small_staff()), W)
    b = phan_cong(_problem(small_staff()), W)
    assert a.lessons == b.lessons and list(a.lessons) == list(b.lessons)


def test_hires_take_overtime_and_missing_lessons():
    staff = small_staff(general=False)
    problem = _problem(staff)
    plan = phan_cong(problem, W)
    split = tach_tiet_bu(problem, plan, staff, include_missing=True)
    [hire] = split[config.ROLE_GENERAL]
    owners = Counter(owner for _, owner, n in hire for _ in range(n))
    assert owners == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2, "": 4}  # 4 tiết bù + 4 tiết thiếu
    assert tach_tiet_bu(problem, plan, staff, include_missing=False)[config.ROLE_GENERAL][0] == \
        [p for p in hire if p[1]]


def test_hire_split_limits_pairs_and_orders_by_load(sample_staff):
    problem = build_problem(sample_staff, CURRICULUM, {}, overtime_max=2)
    plan = phan_cong(problem, W)
    groups = tach_tiet_bu(problem, plan, sample_staff, include_missing=True)[config.ROLE_GENERAL]
    loads = [sum(n for _, _, n in g) for g in groups]
    assert loads == sorted(loads, reverse=True) and sum(loads) == sum(plan.overtime.values())
    for g in groups:  # mỗi người mới tối đa một cặp mỗi buổi
        tv = sum(n for cid, _, n in g if problem.courses[cid].grade == 1 and problem.courses[cid].subject == bo_mau.TV)
        assert tv // 2 <= 9 and sum(n for _, _, n in g) <= 23
