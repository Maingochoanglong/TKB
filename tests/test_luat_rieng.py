"""Luật riêng của trường (tkb/luat_rieng.py, sheet LUẬT RIÊNG): đọc, xếp đúng luật bắt buộc, ưu tiên luật mềm,
kiểm tra độc lập, đếm trước khi xếp và chẩn đoán."""
from collections import Counter

import openpyxl
import pytest

from tkb import config, luat_co_san, luat_rieng
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.config import CustomRule
from tkb.phan_cong import teacher_slots
from tkb.rules import DEFAULTS, applied, code, read_rules
from tkb.solver import ConflictError, solve
from tkb.staff import InputError
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff, plain_rules

SETTINGS = dict(time_limit=5, workers=4, overtime_max=4)
HEAD = [h for _, h in luat_rieng.COLUMNS]


def _parse(**cells):
    errors = []
    rule = luat_rieng.parse(cells, 7, errors.append)
    return rule, errors


def _solve(*rules, mode=config.MODE_OVERTIME):
    with applied({"CUSTOM_RULES": list(rules)}):
        sol = solve(small_staff(general=False), CURRICULUM, config.Settings(mode=mode, **SETTINGS),
                    log=lambda *_: None)
        return sol, check(sol.problem, sol.lessons)


def test_parse_each_kind():
    rule, errors = _parse(kind="không xếp vào", subject="Thể dục", grades="3-5", days="T2, Thứ 4", periods="1",
                          sessions="Sáng", hard="Có")
    assert errors == [] and rule == CustomRule("khong_xep", "Thể dục", grades=(3, 4, 5), days=(0, 2), periods=(1,),
                                               sessions=("Sáng",), hard=True, row=7)
    assert luat_rieng.describe(rule) == "Thể dục khối 3, 4, 5 không xếp vào buổi sáng Thứ 2, Thứ 4 tiết 1 (bắt buộc)"
    assert _parse(kind="Chỉ xếp vào", subject="Thể dục", sessions="chiều")[0].sessions == ("Chiều",)
    assert _parse(kind="Học 2 tiết liền", subject="Tiếng Anh", level=3)[0].level == 3
    assert _parse(kind="Học trước", subject="Tiếng Việt", other="Toán")[0].other == "Toán"
    rule = _parse(kind="Giáo viên tối đa tiết mỗi ngày", role="Tiếng Anh", number=5, hard="Có")[0]
    assert rule.role == "tiếng anh" and luat_rieng.describe(rule) == ("mỗi GV Tiếng Anh dạy tối đa 5 tiết mỗi ngày "
                                                                     "(bắt buộc)")
    assert _parse(kind="Số lớp học cùng lúc tối đa", subject="Tin học", number=1)[0].number == 1
    # Ô không ghi gì: không phải luật.
    assert _parse(kind=None, subject=None) == (None, [])


@pytest.mark.parametrize("cells, error", [
    (dict(kind="Xếp đẹp", subject="Toán"), "Kiểu luật 'Xếp đẹp' không có"),
    (dict(kind="Học trước", subject="Toán"), "phải ghi cột Môn thứ hai"),
    (dict(kind="Học 2 tiết liền", subject="Toán", periods="1"), "cột Tiết không dùng cho kiểu luật Học 2 tiết liền"),
    (dict(kind="Không xếp vào", subject="Toán"), "ít nhất một trong các cột Ngày, Tiết, Buổi"),
    (dict(kind="Không xếp vào", subject="Toán", days="Thứ 8"), "cột Ngày ghi Thứ 2 … Thứ 7"),
    (dict(kind="Không xếp vào", subject="Toán", sessions="tối"), "cột Buổi ghi Sáng hoặc Chiều"),
    (dict(kind="Học trước", subject="Toán", other="toán"), "Môn và Môn thứ hai phải khác nhau"),
    (dict(kind="Học 2 tiết liền", subject="Toán", level=5), "cột Mức ghi 1, 2 hoặc 3"),
    (dict(kind="Số lớp học cùng lúc tối đa", subject="Tin học", number=0), "cột Số ghi một số nguyên dương"),
])
def test_parse_errors(cells, error):
    rule, errors = _parse(**cells)
    assert rule is None and any(error in e for e in errors), errors


def test_read_sheet_and_rules_code(tmp_path):
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    assert plain_rules(read_rules(path)) == DEFAULTS  # sheet LUẬT của file mẫu: chỉ có các luật có sẵn
    with applied(DEFAULTS):
        empty = code()
    wb = openpyxl.load_workbook(path)
    ws = wb[luat_rieng.RULES_SHEET]
    head = [c.value for c in ws[1]]
    assert head[1:-1] == HEAD  # Nhóm | các cột câu luật | Luật đọc là
    n = len(luat_co_san.default_rows()) + 2  # dòng trống đầu tiên sau các luật có sẵn
    for r, row in ((n, {"Kiểu luật": "Không xếp vào", "Môn": "Thể dục", "Tiết": "1", "Bắt buộc": "Có"}),
                   (n + 1, {"Kiểu luật": "Học trước", "Môn": "Toán"})):
        for h, value in row.items():
            ws.cell(r, head.index(h) + 1, value)
    wb.save(path)
    with pytest.raises(InputError, match=f"LUẬT, dòng {n + 1}: kiểu luật Học trước phải ghi cột Môn thứ hai"):
        read_rules(path)
    ws.delete_rows(n + 1)
    wb.save(path)
    rules = read_rules(path)
    assert rules["CUSTOM_RULES"] == [CustomRule("khong_xep", "Thể dục", periods=(1,), hard=True, row=n)]
    with applied(rules):
        assert code() != empty  # có luật riêng thì mã quy định khác (TKB đã lưu không dùng lại được)
        moved = code()
    with applied({"CUSTOM_RULES": [CustomRule("khong_xep", "Thể dục", periods=(1,), hard=True, row=40)]}):
        assert code() == moved  # dời dòng thì mã không đổi


def test_no_custom_rules_change_nothing():
    plain, _ = _solve()
    assert plain.fingerprint() == "51DE-A8CB-6CB7"  # mã tham chiếu của trường nhỏ (tests/test_reproducible.py)


def test_hard_rules_hold_and_are_checked():
    rules = [CustomRule("khong_xep", "Thể dục", periods=(2, 3, 4), hard=True),
             CustomRule("chi_xep", "Tin học", days=(1, 2), hard=True),
             CustomRule("truoc", "Tiếng Việt", other="Toán", hard=True),
             CustomRule("cung_luc", "Tiếng Anh", number=1, hard=True),
             CustomRule("gv_ngay", role="tiếng anh", number=2, hard=True),
             CustomRule("lien_2", "Tiếng Anh", hard=True)]
    sol, errors = _solve(*rules)
    assert errors == []
    les = sol.lessons
    assert not [l for l in les if l.subject == "Thể dục" and l.period in (2, 3, 4)]
    assert {l.day for l in les if l.subject == config.TIN_HOC} <= {1, 2}
    assert max(Counter((l.day, l.period) for l in les if l.subject == config.TIENG_ANH).values()) == 1
    assert max(Counter((l.teacher, l.day) for l in les if l.subject == config.TIENG_ANH).values()) <= 2
    session = lambda p: p <= 4  # noqa: E731
    for cls in sol.problem.classes:
        for d in range(5):
            for morning in (True, False):
                tv = [l.period for l in les if (l.class_name, l.day) == (cls, d) and session(l.period) == morning
                      and l.subject == config.TV]
                toan = [l.period for l in les if (l.class_name, l.day) == (cls, d) and session(l.period) == morning
                        and l.subject == config.TOAN]
                assert not tv or not toan or max(tv) < min(toan)
                ta = sorted(l.period for l in les if (l.class_name, l.day) == (cls, d) and session(l.period) == morning
                            and l.subject == config.TIENG_ANH)
                assert len(ta) in (0, 2) and (not ta or ta[1] == ta[0] + 1)
    # Bộ kiểm tra độc lập bắt được TKB sai luật: TKB xếp không có luật, kiểm với luật.
    plain, _ = _solve()
    gym = next(l for l in plain.lessons if l.subject == "Thể dục")
    with applied({"CUSTOM_RULES": [CustomRule("khong_xep", "Thể dục", days=(gym.day,), periods=(gym.period,),
                                              hard=True, row=9)]}):
        found = check(plain.problem, plain.lessons)
    assert any(e.startswith(f"LUẬT RIÊNG dòng 9: Thể dục không xếp vào Thứ {gym.day + 2} tiết {gym.period} "
                            f"(bắt buộc): lớp {gym.class_name}") for e in found), found


def test_soft_rules_are_preferred():
    monday_it = lambda sol: sum(1 for l in sol.lessons if l.subject == config.TIN_HOC and l.day == 0)  # noqa: E731
    plain, _ = _solve()
    prefer, errors = _solve(CustomRule("khong_xep", "Tin học", days=(0, 1, 2, 3), level=3))
    assert errors == []  # luật ưu tiên không phải lỗi
    assert monday_it(prefer) == 0 and {l.day for l in prefer.lessons if l.subject == config.TIN_HOC} == {4}
    with applied({"CUSTOM_RULES": [CustomRule("khong_xep", "Tin học", days=(0, 1, 2, 3), level=3, row=4)]}):
        assert luat_rieng.soft_report(prefer.problem, prefer.lessons) == [
            "LUẬT RIÊNG dòng 4: Tin học không xếp vào Thứ 2, Thứ 3, Thứ 4, Thứ 5 (ưu tiên mức 3): 0 lần không theo"]
        before = sum(1 for l in plain.lessons if l.subject == config.TIN_HOC and l.day < 4)
        assert before > 0 and luat_rieng.soft_report(plain.problem, plain.lessons)[0].endswith(
            f": {before} lần không theo")


def test_teacher_day_cap_limits_the_assignment():
    with applied({"CUSTOM_RULES": [CustomRule("gv_ngay", role="tiếng anh", number=1, hard=True)]}):
        problem = build_problem(small_staff(), CURRICULUM, {}, overtime_max=0)
        assert teacher_slots(problem)["tiếng anh 1"] == 5  # 1 tiết mỗi ngày × 5 ngày


def test_precheck_and_validate():
    def run(*rules):
        with applied({"CUSTOM_RULES": list(rules)}):
            problem = build_problem(small_staff(), CURRICULUM, {}, overtime_max=0)
            return luat_rieng.validate(problem), luat_rieng.precheck(problem)

    assert run(CustomRule("truoc", "Bơi lội", other="Toán", row=3))[0] == [
        "LUẬT RIÊNG dòng 3: môn 'Bơi lội' không có trong chương trình học (hoặc không có tiết nào)"]
    assert run(CustomRule("gv_ngay", role="bảo vệ", number=3, row=4))[0] == [
        "LUẬT RIÊNG dòng 4: không có giáo viên nào có chức vụ 'Bảo Vệ'"]
    _, found = run(CustomRule("chi_xep", "Toán", days=(0,), sessions=("Chiều",), hard=True, row=5))
    assert found == ["LUẬT RIÊNG dòng 5: Toán chỉ xếp vào buổi chiều Thứ 2 (bắt buộc): khối 3 có 5 tiết Toán nhưng "
                     "các luật vị trí bắt buộc chỉ để lại 3 tiết trong tuần"]
    _, found = run(CustomRule("lien_2", "Toán", hard=True, row=6))
    assert found == ["LUẬT RIÊNG dòng 6: Toán học 2 tiết liền (bắt buộc): khối 3 có 7 tiết/tuần (lẻ) nên không chia "
                     "hết thành cặp 2 tiết"]
    _, found = run(CustomRule("cung_luc", "Tiếng Anh", number=1, hard=True, row=7),
                   CustomRule("chi_xep", "Tiếng Anh", days=(0,), hard=True, row=8))
    assert found == ["LUẬT RIÊNG dòng 7: Tiếng Anh: tối đa 1 lớp học cùng lúc (bắt buộc): các lớp có tổng 8 tiết "
                     "Tiếng Anh nhưng tối đa 1 lớp × 7 tiết = 7"]
    assert run(CustomRule("lien_2", "Toán", row=6)) == ([], [])  # ưu tiên: không đếm


def test_diagnosis_names_the_custom_rule():
    """Toán chỉ học buổi chiều (4 buổi) mà Toán mỗi ngày tối đa 1 tiết và có 5 tiết/tuần: phép đếm không thấy, bộ
    giải thấy; chẩn đoán chỉ ra dòng luật riêng và quy định Tối đa tiết mỗi ngày."""
    rule = CustomRule("chi_xep", "Toán", sessions=("Chiều",), hard=True, row=12)
    with pytest.raises(ConflictError) as err:
        _solve(rule)
    lines = str(err.value).splitlines()
    assert "  - LUẬT RIÊNG dòng 12: Toán chỉ xếp vào buổi chiều (bắt buộc)" in lines
    assert ("  - Luật có sẵn: Với mỗi lớp, ngày: các tiết Toán: số tiết tối đa 1, khi số tiết/tuần <= số ngày (bắt "
            "buộc)") in lines
    assert config.CUSTOM_RULES == []  # chẩn đoán xong trả lại như cũ
