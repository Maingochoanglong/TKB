"""Mọi luật là dòng của sheet LUẬT (tkb/luat_co_san.py): dòng mặc định cho đúng mô hình cũ (mã không đổi); sửa số,
điểm, xóa dòng, đổi Bắt buộc có tác dụng; bộ ghép kiểm chéo với bộ kiểm tra độc lập và hạ thay được luật gốc."""
import random
from dataclasses import replace

import openpyxl
import pytest

from tkb import bo_ghep, checker, config, luat_co_san, luat_rieng, solver
from tkb.rules import DEFAULTS, applied, code, read_rules
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff

SETTINGS = dict(time_limit=5, workers=4, overtime_max=4)
NO_FILE_CODE = code()  # mã quy định khi file không ghi gì


def _solve(**values):
    with applied(values):
        sol = solver.solve(small_staff(general=False), CURRICULUM,
                           config.Settings(mode=config.MODE_OVERTIME, **SETTINGS), log=lambda *_: None)
        return sol, checker.check(sol.problem, sol.lessons)


@pytest.fixture(scope="module")
def plain():
    return _solve()[0]


def _hard_rows():
    return [r for r in luat_co_san.default_rows() if r.hard and r.kind == "tu_ghep"]


def test_default_rows_change_nothing():
    rows = luat_co_san.default_rows()
    assert {r.group_label for r in rows} == set(luat_co_san.GROUPS)
    assert all(luat_co_san.native_of(r) is not None for r in rows)
    values = luat_co_san.apply(rows)
    assert values["OFF"] == frozenset() and values["WEIGHTS"] == {} and values["CUSTOM_RULES"] == []
    assert values["DAILY_LIMITS"] == config.DAILY_LIMITS
    assert values["SESSION_GROUP_LIMIT"] == config.SESSION_GROUP_LIMIT
    assert values["PAIR_MIN_LESSONS"] == config.PAIR_MIN_LESSONS
    with applied(values):
        assert code() == NO_FILE_CODE


def test_template_sheet_reads_back_to_defaults(tmp_path):
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    wb = openpyxl.load_workbook(path)
    assert luat_rieng.SHEET not in wb.sheetnames and luat_rieng.RULES_SHEET in wb.sheetnames
    ws = wb[luat_rieng.RULES_SHEET]
    head = [c.value for c in ws[1]]
    assert head[0] == "Nhóm" and head[-1] == "Luật đọc là"
    assert ws.cell(2, len(head)).value.startswith("Mỗi buổi, một lớp học tối đa 2 tiết của một môn")
    rules = read_rules(path)
    assert len(rules.pop("RULES")) == len(luat_co_san.default_rows())
    assert rules == DEFAULTS
    with applied(read_rules(path)):
        assert code() == NO_FILE_CODE


def _edit(tmp_path, change):
    """File mẫu với sheet LUẬT sửa theo change(ws, dòng tiêu đề) rồi đọc lại."""
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    wb = openpyxl.load_workbook(path)
    ws = wb[luat_rieng.RULES_SHEET]
    change(ws, [c.value for c in ws[1]])
    wb.save(path)
    return read_rules(path)


def _row_of(ws, head, text):
    say = head.index("Luật đọc là") + 1
    return next(r for r in range(2, ws.max_row + 1) if (ws.cell(r, say).value or "").startswith(text))


def test_edit_number_points_delete_and_soften(tmp_path):
    def change(ws, head):
        col = {h: i + 1 for i, h in enumerate(head)}
        ws.cell(_row_of(ws, head, "Mỗi buổi, một lớp học tối đa"), col["Số"], 3)
        ws.cell(_row_of(ws, head, "Tránh xếp môn có nhãn Môn nặng"), col["Điểm"], 2000)
        ws.delete_rows(_row_of(ws, head, "Ở giờ có nhãn Luôn do GVCN dạy"))
        r = _row_of(ws, head, "Các tiết của một môn trong cùng buổi")
        ws.cell(r, col["Bắt buộc"], "Không")
        ws.cell(r, col["Mức"], 3)

    rules = _edit(tmp_path, change)
    assert rules["SESSION_GROUP_LIMIT"] == 3
    assert rules["WEIGHTS"] == {"heavy_late": 2000}
    assert rules["OFF"] == frozenset({"tiet_gvcn", "lien_nhau"})
    (soft,) = rules["CUSTOM_RULES"]  # luật có sẵn đổi thành ưu tiên: xếp bằng bộ ghép
    assert soft.measure == "lien" and not soft.hard and soft.level == 3
    with applied(rules):
        assert code() != NO_FILE_CODE
        assert luat_rieng.label(soft) == (f"LUẬT dòng {soft.row}: Mỗi lớp, mỗi môn: các tiết trong một buổi đứng "
                                          f"liền nhau (ưu tiên cao)")  # khác dạng gốc: câu của bộ ghép


def test_built_in_rules_read_as_plain_sentences():
    """Mỗi luật có sẵn có tên viết tay; tên theo số của dòng; câu không có ký hiệu hay chữ kỹ thuật."""
    rows = luat_co_san.default_rows()
    titles = [luat_co_san.title(r) for r in rows]
    assert all(titles) and len(set(titles)) == len(titles)
    assert all(len(n.titles) == len(n.rows()) or n.key == "toi_da_ngay" for n in luat_co_san.NATIVES)
    first = replace(rows[0], number=3)
    assert luat_co_san.title(first).startswith("Mỗi buổi, một lớp học tối đa 3 tiết")
    assert luat_co_san.title(replace(rows[0], hard=False)) is None  # khác dạng gốc: đọc bằng câu của bộ ghép
    for r in rows:
        for rule in (r, replace(r, hard=not r.hard) if r.kind == "tu_ghep" else r):
            text = luat_rieng.describe(rule)
            assert not any(s in text for s in ("<=", ">=", " ô ", "Với mỗi", "mức ")), text
            assert text.count(":") <= 1, text
    levels = [luat_rieng.level_label(r) for r in rows if not r.hard]
    assert levels[:2] == ["Thấp", "Rất cao"]  # 200 điểm: gần Thấp; 10000 điểm: Rất cao


def test_deleted_rule_is_off_when_solving():
    rows = [r for r in luat_co_san.default_rows() if luat_co_san.native_of(r).key != "tiet_gvcn"]
    sol, errors = _solve(**luat_co_san.apply(rows))
    assert errors == []
    with applied({}):  # luật gốc đầy đủ: tiết 1 có thể không do GVCN dạy
        found = checker.check(sol.problem, sol.lessons)
    assert all("tiết của GVCN" in e for e in found)


def test_legacy_file_rows(tmp_path):
    """File bản trước: số ở các cột cũ, luật ở sheet LUẬT RIÊNG -> các dòng mặc định với số đó, cộng luật riêng."""
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    wb = openpyxl.load_workbook(path)
    del wb[luat_rieng.RULES_SHEET]
    ws = wb.create_sheet(luat_rieng.SHEET)
    ws.append(["Kiểu luật", "Môn", "Tiết", "Bắt buộc"])
    ws.append(["Không xếp vào", "Thể dục", "1", "Có"])
    rules_ws = wb[config.RULES_SHEET]
    rules_ws.insert_rows(2)
    rules_ws.cell(2, 1, "Số tiết tối đa một nhóm môn mỗi buổi")
    rules_ws.cell(2, 2, 3)
    program = wb[config.PROGRAM_SHEET]
    col = program.max_column + 1
    program.cell(1, col, "Tối đa tiết mỗi ngày")
    row = next(r for r in range(2, program.max_row + 1) if program.cell(r, 1).value == "Tiếng Anh")
    program.cell(row, col, 2)
    wb.save(path)
    rules = read_rules(path)
    assert "RULES" not in rules and rules["SESSION_GROUP_LIMIT"] == 3 and rules["OFF"] == frozenset()
    assert rules["DAILY_LIMITS"] == {config.TIENG_ANH: 2}  # cột cũ có thì là đủ (Toán để trống: không giới hạn)
    assert [r.kind for r in rules["CUSTOM_RULES"]] == ["khong_xep"]
    with applied(rules):
        assert luat_co_san.rows()[0].number == 3  # dòng mặc định lấy số từ cột cũ
        assert luat_rieng.label(rules["CUSTOM_RULES"][0]).startswith("LUẬT RIÊNG dòng 2")


def test_solved_timetable_keeps_every_hard_row(plain):
    assert checker.check(plain.problem, plain.lessons) == []
    found = bo_ghep.violations(plain.problem, plain.lessons, rules=_hard_rows(), skip_forced=False)
    assert found == [], [luat_rieng.describe(L.rule) + ": " + t for L, _, _, t in found]


def test_cross_check_with_the_checker(plain):
    """Đổi chỗ hai tiết của một lớp: dòng bắt buộc nào bộ ghép thấy bị vi phạm thì bộ kiểm tra độc lập cũng báo lỗi;
    bộ kiểm tra thấy lỗi luật bảo vệ học sinh thì bộ ghép cũng thấy ở các dòng Bảo vệ học sinh."""
    rnd = random.Random(0)
    rows = _hard_rows()
    student = [r for r in rows if r.group_label == "Bảo vệ học sinh"]
    hits = 0
    for _ in range(40):
        les = list(plain.lessons)
        cls = rnd.choice(plain.problem.classes)
        i, j = rnd.sample([k for k, l in enumerate(les) if l.class_name == cls], 2)
        a, b = les[i], les[j]
        les[i] = replace(a, day=b.day, period=b.period)
        les[j] = replace(b, day=a.day, period=a.period)
        found = bo_ghep.violations(plain.problem, les, rules=rows, skip_forced=False)
        assert not found or checker.check(plain.problem, les)
        if checker._check_student_rules(plain.problem, les):
            assert bo_ghep.violations(plain.problem, les, rules=student, skip_forced=False)
            hits += 1
    assert hits >= 5


@pytest.mark.parametrize("keys", [("lien_nhau", "tang_cuong", "lien_tiet", "gvcn_truoc"), ("nhom_buoi", "tiet_gvcn")])
def test_generic_lowering_replaces_the_native_one(keys):
    """Tắt luật gốc và xếp chính các dòng đó bằng bộ ghép: TKB vẫn đúng mọi luật gốc."""
    rows = [replace(r, row=i + 2) for i, r in enumerate(luat_co_san.default_rows())
            if luat_co_san.native_of(r).key in keys]
    sol, errors = _solve(OFF=frozenset(keys), CUSTOM_RULES=rows)
    assert errors == []
    with applied({"OFF": frozenset(), "CUSTOM_RULES": []}):
        assert checker.check(sol.problem, sol.lessons) == []
