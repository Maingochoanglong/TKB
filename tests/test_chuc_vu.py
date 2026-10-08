"""Chức vụ GV chuyên biệt nhà trường tự đặt (sheet CHỨC VỤ, config.CUSTOM_ROLES): một chức vụ dạy nhiều môn; đọc,
báo lỗi, phân công, xếp đúng quyền dạy, tuyển thêm, và kịch bản của giao diện."""
from collections import Counter

import openpyxl
import pytest

from tkb import config, kich_ban, luat_rieng
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.config import CustomRule, Role
from tkb.rules import DEFAULTS, applied, code, read_rules
from tkb.solver import solve
from tkb.staff import InputError
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff, teacher, plain_rules

ARTS = Role("GV Năng khiếu", ("Thể dục", "Âm nhạc", "Mỹ thuật"), row=2)
SETTINGS = dict(time_limit=5, workers=4, overtime_max=4)


def _arts_staff():
    """Trường nhỏ: một GV Năng khiếu dạy Thể dục, Âm nhạc, Mỹ thuật thay cho ba GV chuyên biệt."""
    staff = [t for t in small_staff() if t.role not in ("thể dục", "âm nhạc", "mỹ thuật")]
    return [*staff, teacher("NK", "gv năng khiếu 1", 23, row=10)]


def _sheet(path, rows):
    wb = openpyxl.load_workbook(path)
    ws = wb[config.ROLES_SHEET]
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            ws.cell(r, c, value)
    wb.save(path)


def test_read_sheet_and_rules_code(tmp_path):
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    assert plain_rules(read_rules(path)) == DEFAULTS  # sheet CHỨC VỤ trống của file mẫu: như không có
    with applied(DEFAULTS):
        empty = code()
    _sheet(path, [["GV Năng khiếu", "Thể dục, Âm nhạc; Mỹ thuật, thể dục"], ["Tiếng Anh", "Tiếng Anh"]])
    rules = read_rules(path)
    assert rules["CUSTOM_ROLES"] == [ARTS, Role("Tiếng Anh", ("Tiếng Anh",), row=3)]
    with applied(rules):
        assert code() != empty
    # Dòng chức vụ trùng tên môn, dạy đúng môn đó: như không ghi.
    with applied({"CUSTOM_ROLES": [Role("Tiếng Anh", ("tiếng anh",), row=3)]}):
        assert code() == empty


def test_sheet_errors_all_at_once(tmp_path):
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    _sheet(path, [["Bộ Môn", "Toán"], ["GV Năng khiếu 2", "Âm nhạc"], ["GV Năng khiếu", None],
                  ["Tin", "Tin học"], ["tin", "Tin học"], [None, "Toán"]])
    with pytest.raises(InputError) as exc:
        read_rules(path)
    text = str(exc.value)
    assert "có 5 lỗi" in text
    assert "CHỨC VỤ, dòng 2: Bộ Môn là chức vụ có sẵn" in text
    assert "CHỨC VỤ, dòng 3: tên chức vụ không ghi số" in text
    assert "CHỨC VỤ, dòng 4: chức vụ 'GV Năng khiếu' chưa ghi môn ở cột Môn được dạy" in text
    assert "CHỨC VỤ, dòng 6: chức vụ 'tin' đã ghi ở dòng 5" in text
    assert "CHỨC VỤ, dòng 7: thiếu tên ở cột Chức vụ" in text


def test_role_with_many_subjects():
    with applied({"CUSTOM_ROLES": [ARTS]}):
        p = build_problem(_arts_staff(), CURRICULUM)
    assert p.specialists["gv năng khiếu"] == ("Thể dục", "Âm nhạc", "Mỹ thuật")
    assert p.teachers["gv năng khiếu 1"].code == "GV Năng khiếu 1"  # tên như ghi ở sheet CHỨC VỤ
    for c in p.courses:
        if c.subject in ARTS.subjects and not c.homeroom:
            assert "gv năng khiếu 1" in c.teachers and "bộ môn 1" in c.teachers
        if c.subject in (config.TIENG_ANH, config.TIN_HOC):
            assert "gv năng khiếu 1" not in c.teachers
    # GVCN không nhận thêm môn của GV chuyên biệt.
    assert all(s not in ARTS.subjects for take in p.homeroom_take.values() for s in take)


@pytest.mark.parametrize("subjects, error", [
    (("Âm nhạc", "Múa"), "CHỨC VỤ, dòng 2: không có môn 'Múa' trong sheet CHƯƠNG TRÌNH HỌC"),
    (("Hoạt động trải nghiệm",), "CHỨC VỤ, dòng 2: môn 'Hoạt động trải nghiệm' chỉ GVCN được dạy"),
])
def test_role_subject_errors(subjects, error):
    with applied({"CUSTOM_ROLES": [Role("GV Năng khiếu", subjects, row=2)]}):
        with pytest.raises(InputError, match=error):
            build_problem(_arts_staff(), CURRICULUM)


def test_unknown_role_is_still_an_error():
    staff = [*small_staff(), teacher("X", "gv múa 1", 10, row=11)]
    with pytest.raises(InputError, match="chức vụ 'gv múa' không xác định .*sheet CHỨC VỤ"):
        build_problem(staff, CURRICULUM)


def test_role_without_teacher_is_hired_for_forbidden_subjects():
    """Môn bộ môn không dạy mà chưa ai dạy được: chức vụ để tuyển là chức vụ đầu tiên của sheet CHỨC VỤ dạy môn đó
    (một người dạy cả Tiếng Anh và Tin học), không phải hai chức vụ trùng tên môn. Chức vụ không ai giữ, không cần
    tuyển: bỏ qua."""
    staff = [t for t in small_staff() if t.role not in ("tiếng anh", "tin học")]
    roles = [Role("GV Ngoại ngữ Tin học", ("Tiếng Anh", "Tin học"), row=2), Role("GV Múa", ("Âm nhạc",), row=3)]
    with applied({"CUSTOM_ROLES": roles}):
        p = build_problem(staff, CURRICULUM)  # đủ người tuyển dự kiến (như mô hình tích hợp của solver)
    assert list(p.specialists)[-1] == "gv ngoại ngữ tin học" and "gv múa" not in p.specialists
    assert "tiếng anh" not in p.specialists and "tin học" not in p.specialists
    assert p.supplement_roles["gv ngoại ngữ tin học"] == ["gv ngoại ngữ tin học 1"]
    assert p.teachers["gv ngoại ngữ tin học 1"].code == "GV Ngoại ngữ Tin học 1"
    for c in p.courses:
        if c.subject in (config.TIENG_ANH, config.TIN_HOC):
            assert c.teachers == ["gv ngoại ngữ tin học 1"]


@pytest.mark.parametrize("mode", [config.MODE_OVERTIME, config.MODE_HIRE])
def test_solve_with_a_role_of_many_subjects(mode):
    with applied({"CUSTOM_ROLES": [ARTS]}):
        sol = solve(_arts_staff(), CURRICULUM, config.Settings(mode=mode, **SETTINGS), log=lambda *_: None)
        assert check(sol.problem, sol.lessons) == []
    taught = Counter(les.subject for les in sol.lessons if les.teacher == "gv năng khiếu 1")
    assert set(taught) <= set(ARTS.subjects) and sum(taught.values()) > 0
    # Bộ môn chỉ dạy thay môn chuyên biệt khi GV Năng khiếu đã đủ tiết.
    assert sum(taught.values()) == min(23, sum(n for s, n in CURRICULUM[3].items() if s in ARTS.subjects) * 2)


def test_custom_rule_for_a_role_of_many_subjects():
    """Luật riêng "Giáo viên tối đa tiết mỗi ngày" cho chức vụ tự đặt: ghi đúng tên chức vụ, xếp đúng luật."""
    rule = CustomRule("gv_ngay", role="gv năng khiếu", number=3, hard=True, row=2)
    with applied({"CUSTOM_ROLES": [ARTS], "CUSTOM_RULES": [rule]}):
        assert luat_rieng.cells(rule)["role"] == "GV Năng khiếu"
        sol = solve(_arts_staff(), CURRICULUM, config.Settings(mode=config.MODE_OVERTIME, **SETTINGS),
                    log=lambda *_: None)
        assert check(sol.problem, sol.lessons) == []
    per_day = Counter(les.day for les in sol.lessons if les.teacher == "gv năng khiếu 1")
    assert per_day and max(per_day.values()) <= 3


def test_checker_finds_a_subject_outside_the_role():
    with applied({"CUSTOM_ROLES": [ARTS]}):
        sol = solve(_arts_staff(), CURRICULUM, config.Settings(mode=config.MODE_OVERTIME, **SETTINGS),
                    log=lambda *_: None)
        les = next(les for les in sol.lessons if les.subject == config.TIENG_ANH)
        lessons = [l if l is not les else type(les)(**{**les.__dict__, "teacher": "gv năng khiếu 1"})
                   for l in sol.lessons]
        errors = check(sol.problem, lessons)
    assert any("gv năng khiếu 1 chỉ được dạy Thể dục, Âm nhạc, Mỹ thuật" in e for e in errors)


def test_scenario_roles_round_trip(tmp_path):
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    scenario, _ = kich_ban.from_excel(path)
    scenario["roles"].append({"name": "GV Năng khiếu", "subjects": ["Thể dục", "Âm nhạc", "Mỹ thuật"]})
    for row in scenario["staff"]:
        if row["role"] in ("Thể Dục", "Âm Nhạc", "Mỹ Thuật"):
            row["role"] = "GV Năng khiếu"
    kich_ban.to_excel(scenario, tmp_path / "ra.xlsx")
    rules = read_rules(tmp_path / "ra.xlsx")
    assert rules["CUSTOM_ROLES"][-1] == Role("GV Năng khiếu", ("Thể dục", "Âm nhạc", "Mỹ thuật"),
                                             row=len(scenario["roles"]) + 1)
    back, _ = kich_ban.from_excel(tmp_path / "ra.xlsx")
    assert back["roles"] == scenario["roles"]
    assert kich_ban.check(back, config.MODE_OVERTIME, 2)["errors"] == []
    back["roles"][-1]["subjects"].append("Múa")
    back["roles"].append({"name": "Chủ nhiệm", "subjects": ["Toán"]})
    errors = kich_ban.check(back, config.MODE_OVERTIME, 2)["errors"]
    assert errors == [f"CHỨC VỤ, dòng {len(back['roles']) + 1}: Chủ Nhiệm là chức vụ có sẵn, không ghi ở sheet này "
                      f"(môn được dạy của Chủ Nhiệm, Bộ Môn, Quản Lý ghi ở các cột của sheet CHƯƠNG TRÌNH HỌC)"]
    back["roles"].pop()
    assert kich_ban.check(back, config.MODE_OVERTIME, 2)["errors"] == [
        f"CHỨC VỤ, dòng {len(back['roles']) + 1}: không có môn 'Múa' trong sheet CHƯƠNG TRÌNH HỌC"]
