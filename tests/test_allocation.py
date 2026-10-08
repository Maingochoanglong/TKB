import pytest

from tkb import config
from tkb.allocation import build_problem, split_homeroom
from tkb.staff import InputError, make_teacher

from .conftest import CURRICULUM, teacher

C = config


def test_homeroom_split_sample(sample_staff):
    p = build_problem(sample_staff, CURRICULUM)
    take = p.homeroom_take
    assert take["1/1"] == {C.TV: 10, C.TOAN: 5, C.HDTN: 3, C.DD: 1}  # cắt 4 tiết TV
    assert take["2/1"] == {C.TV: 10, C.TOAN: 5, C.HDTN: 3, C.DD: 1}  # vừa đủ 19
    assert take["3/1"][C.TV_TC] == 1 and take["3/1"][C.TOAN_TC] == 2  # bù TV TC rồi Toán TC
    assert take["4/1"][C.TV] == 6  # cắt 1 tiết TV
    assert take["5/5"][C.TV] == 3 and sum(take["5/5"].values()) == 16  # GVCN 16 tiết
    for cls, t in take.items():
        quota = next(x.max_lessons for x in sample_staff if x.class_name == cls)
        assert sum(t.values()) == quota
        assert t[C.DD] == 1 and t[C.HDTN] == 3


def test_fill_order_never_takes_specialist_subjects():
    req = CURRICULUM[3]
    take = split_homeroom("3/1", req, 30, reserved=set(), specialist={C.TIENG_ANH, C.TIN_HOC, C.CONG_NGHE})
    for s in (C.TV_TC, C.TOAN_TC, C.TNXH, C.KNS):
        assert take[s] == req[s]
    for s in (C.TIENG_ANH, C.TIN_HOC, C.CONG_NGHE, "Thể dục", "Âm nhạc", "Mỹ thuật"):
        assert s not in take  # môn của GV chuyên biệt
    assert sum(take.values()) == 22


def test_fill_order_priority():
    req = CURRICULUM[3]
    take = split_homeroom("3/1", req, 17, reserved=set())  # thiếu 1 -> TV TC trước
    assert take.get(C.TV_TC) == 1 and C.TOAN_TC not in take
    take = split_homeroom("3/1", req, 18, reserved=set())  # thiếu 2 -> TV TC rồi Toán TC
    assert take.get(C.TV_TC) == 1 and take.get(C.TOAN_TC) == 1
    take = split_homeroom("3/1", req, 21, reserved={C.TNXH})  # môn dành riêng không bị lấy
    assert C.TNXH not in take and take[C.KNS] == 1 and take[C.CONG_NGHE] == 1


def test_cut_only_multi_lesson_subjects():
    req = CURRICULUM[1]
    take = split_homeroom("1/1", req, 6, reserved=set())
    assert take == {C.TV: 1, C.TOAN: 1, C.HDTN: 3, C.DD: 1}
    with pytest.raises(InputError):
        split_homeroom("1/1", req, 5, reserved=set())


def test_permissions(sample_staff):
    p = build_problem(sample_staff, CURRICULUM)
    for c in p.courses:
        roles = {p.teachers[t].role for t in c.teachers}
        if c.subject == C.HDTN:
            assert c.homeroom and p.teachers[c.teachers[0]].class_name == c.class_name
        if c.homeroom:
            continue
        if c.subject in (C.TIENG_ANH, C.TIN_HOC):
            assert roles == {r for r, s in p.specialists.items() if s == (c.subject,)}
        if c.subject in ("Thể dục", "Âm nhạc", "Mỹ thuật"):
            assert config.ROLE_GENERAL in roles and len(roles) == 2
        if config.ROLE_MANAGER in roles:
            assert c.subject == C.KNS and c.grade == 4
    manager_courses = [c for c in p.courses if "quản lý 1" in c.teachers]
    assert len(manager_courses) == 6 and p.manager_load == {"quản lý 1": 4}


def test_supplement_numbering(sample_staff):
    p = build_problem(sample_staff, CURRICULUM, supplement_counts={config.ROLE_GENERAL: 2, "tin học": 1})
    assert p.supplement_roles[config.ROLE_GENERAL] == ["bộ môn 6", "bộ môn 7"]
    assert p.supplement_roles["tin học"] == ["tin học 2"]
    t = p.teachers["bộ môn 6"]
    assert t.name == config.SUPPLEMENT_NAME and t.supplementary and t.max_lessons == 23


def test_homeroom_needs_enough_lessons_for_locked_periods(monkeypatch):
    # GVCN 8 tiết không đủ nếu khoá tiết 1 và tiết 2 mỗi ngày (10 tiết).
    monkeypatch.setattr(config, "HOMEROOM_PERIODS", {1, 2})
    staff = [teacher("CN", "chủ nhiệm 3/1", 8, row=2), teacher("BM", "bộ môn 1", 23, row=3)]
    with pytest.raises(InputError, match="tiết bắt buộc của GVCN"):
        build_problem(staff, CURRICULUM)


def test_overtime_allowances_and_eligibility(sample_staff):
    p = build_problem(sample_staff, CURRICULUM, overtime_max=2)
    assert p.overtime["chủ nhiệm 1/1"] == 2 and p.overtime["bộ môn 1"] == 2
    assert p.overtime["chủ nhiệm 5/5"] == 2 and p.overtime["bộ môn 5"] == 2  # định mức thấp cũng được bù
    assert all(p.teachers[g].role in C.OVERTIME_ROLES for g in p.overtime)
    pool = {(c.class_name, c.subject): c for c in p.courses if not c.homeroom}
    assert "chủ nhiệm 1/1" in pool["1/1", C.TV].teachers
    assert "chủ nhiệm 1/1" in pool["1/1", C.TNXH].teachers
    assert "chủ nhiệm 1/1" not in pool["1/1", C.TIENG_ANH].teachers  # không bù môn chuyên biệt
    assert "chủ nhiệm 1/1" not in pool["1/1", "Thể dục"].teachers
    assert "chủ nhiệm 1/1" in pool["1/1", C.AM_NHAC].teachers  # trừ Âm nhạc, Mỹ thuật
    assert "chủ nhiệm 1/1" in pool["1/1", C.MY_THUAT].teachers
    assert "chủ nhiệm 3/1" not in pool["3/1", C.TIN_HOC].teachers
    assert "chủ nhiệm 1/2" not in pool["1/1", C.TV].teachers  # chỉ bù lớp mình
    hire = build_problem(sample_staff, CURRICULUM)
    assert hire.overtime == {} and not hire.overtime_mode()
    assert all(not hire.teachers[g].class_name for c in hire.courses if not c.homeroom for g in c.teachers)


def test_class_gaps_are_warned():
    staff = [teacher("A", "chủ nhiệm 1/1", 19), teacher("B", "chủ nhiệm 1/3", 19),
             teacher("C", "bộ môn 1", 23)]
    warnings = build_problem(staff, CURRICULUM).warnings
    assert any("Khối 1 không có lớp 1/2" in w for w in warnings)


def test_curriculum_row_order_does_not_change_problem(sample_staff):
    shuffled = {g: dict(reversed(list(req.items()))) for g, req in CURRICULUM.items()}
    key = lambda p: [(c.class_name, c.subject, c.lessons, tuple(c.teachers)) for c in p.courses]
    assert key(build_problem(sample_staff, shuffled)) == key(build_problem(sample_staff, CURRICULUM))


def _v8(name, label, lessons, cls=None, index=None, row=None):
    """GV đọc từ file mẫu V8: chức vụ ghi như trong file, không kèm số."""
    from tkb.staff import normalize
    role = normalize(label)
    return make_teacher(name, role, index, cls, lessons, row=row, label=label)


SCHOOL = {3: {"Tiếng Việt": 7, "Toán": 5, "Hoạt Động Trải Nghiệm": 3, "Tiếng Anh": 4, "Tin Học": 1,
              "Thể Dục": 2, "Âm Nhạc": 1, "Mỹ Thuật": 1, "Lịch Sử và Địa Lý": 2, "Múa": 1}}


def test_specialists_come_from_subject_names():
    staff = [_v8("A", "Chủ Nhiệm", 19, cls="3/1", row=2), _v8("B", "Tiếng Anh ", 23, index=1, row=3),
             _v8("C", "Thể Dục", 23, index=1, row=4), _v8("D", "Múa", 4, index=1, row=5),
             _v8("E", "Bộ Môn", 20, index=1, row=6)]
    p = build_problem(staff, SCHOOL)
    # Chức vụ trùng tên môn là GV chuyên biệt; môn lạ ("Múa") vẫn được xếp.
    assert p.specialists["tiếng anh"] == (C.TIENG_ANH,) and p.specialists["thể dục"] == ("Thể Dục",)
    assert p.specialists["múa"] == ("Múa",)
    # Tin học: bộ môn không được dạy, trường chưa có GV -> tự thêm chức vụ trùng tên môn để tuyển.
    assert p.specialists["tin học"] == (C.TIN_HOC,) and p.supplement_roles["tin học"] == ["tin học 1"]
    assert p.teachers["tin học 1"].label == "Tin Học" and p.teachers["tin học 1"].code == "Tin Học 1"
    # Định mức người tuyển thêm: lấy Số tiết lớn nhất của GV không chủ nhiệm, không quản lý trong file.
    assert p.teachers["tin học 1"].max_lessons == 23
    assert p.teachers["tiếng anh 1"].code == "Tiếng Anh 1"
    # Tên môn trong file được giữ để in ra, tên viết tắt theo config.
    assert p.subject_label(C.LSDL) == "Lịch Sử và Địa Lý" and p.subject_label(C.HDTN) == "HĐTN"
    assert p.subject_order[:3] == [C.TV, C.TOAN, C.HDTN]


def test_unknown_role_is_rejected():
    staff = [_v8("A", "Chủ Nhiệm", 19, cls="3/1", row=2), _v8("B", "Hiệu Trưởng", 4, index=1, row=3),
             _v8("C", "Hiệu Trưởng", 4, index=2, row=7)]
    with pytest.raises(InputError, match="Dòng 3, 7: chức vụ 'Hiệu Trưởng' không xác định"):
        build_problem(staff, SCHOOL)


def test_rule_subjects_missing_from_file_are_warned():
    staff = [_v8("A", "Chủ Nhiệm", 19, cls="3/1", row=2), _v8("E", "Bộ Môn", 23, index=1, row=3),
             _v8("B", "Tiếng Anh", 23, index=1, row=4)]
    warnings = build_problem(staff, SCHOOL).warnings
    assert any("không có trong chương trình học" in w and C.KH in w and C.LSDL not in w for w in warnings)
