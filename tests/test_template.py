import openpyxl

from tkb import config
from tkb.solver import solve
from tkb.program import read_program
from tkb.staff import read_staff
from tkb.template import class_choices, main as template_main, role_choices, write_staff_template
from tkb.writer import write_updated_staff

from .conftest import INPUT_FILE, STAFF_FILE, small_staff


def _key(teachers):
    return [(t.name, t.title, t.max_lessons, t.maternity) for t in teachers]


def test_input_file_matches_v5(real_staff):
    assert _key(read_staff(INPUT_FILE)) == _key(real_staff)
    assert read_program(INPUT_FILE) == config.DEFAULT_CURRICULUM
    wb = openpyxl.load_workbook(INPUT_FILE)
    rows = list(wb["NHÂN SỰ"].iter_rows(values_only=True))
    assert rows[0] == ("STT", "Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Chế độ")
    assert rows[1] == ("=ROW()-1", "Giáo viên CN 1", "Chủ Nhiệm", "1/1", 19, None)
    assert ("=ROW()-1", "Giáo viên BM 5 (Thai sản)", "Bộ Môn", None, 19, "Có") in rows


def test_template_has_dropdowns(tmp_path, real_staff):
    path = tmp_path / "mau.xlsx"
    write_staff_template(path, real_staff)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC", "Danh mục"]
    assert wb["Danh mục"].sheet_state == "hidden"
    ws = wb["NHÂN SỰ"]
    dvs = {str(dv.sqref): dv for dv in ws.data_validations.dataValidation}
    assert dvs["C2:C300"].type == "list" and dvs["C2:C300"].formula1.startswith("'Danh mục'!$A")
    assert dvs["D2:D300"].type == "list" and dvs["D2:D300"].formula1.startswith("'Danh mục'!$B")
    assert dvs["E2:E300"].type == "whole" and dvs["F2:F300"].formula1 == '"Có"'
    program = list(wb["CHƯƠNG TRÌNH HỌC"].iter_rows(values_only=True))
    assert program[0] == ("STT", "Môn học", "Khối 1", "Khối 2", "Khối 3", "Khối 4", "Khối 5")
    assert program[-1][1] == "Tổng" and program[-1][2] == "=SUM(C2:C17)"
    lists = wb["Danh mục"]
    assert [c.value for c in lists["A"] if c.value] == role_choices()
    assert role_choices() == ["Chủ Nhiệm", "Thể Dục", "Tiếng Anh", "Mỹ Thuật", "Bộ Môn", "Âm Nhạc", "Tin Học",
                              "Quản Lý"]
    assert [c.value for c in lists["B"] if c.value] == class_choices() and "5/10" in class_choices()
    assert ws["D2"].number_format == "@"  # Lớp là chữ để Excel không đổi thành ngày tháng
    assert len(ws.conditional_formatting) >= 1
    assert _key(read_staff(path)) == _key(real_staff)
    assert read_program(path) == config.DEFAULT_CURRICULUM


def test_updated_staff_keeps_template(tmp_path):
    src = tmp_path / "ns.xlsx"
    write_staff_template(src, small_staff(general=False))
    sol = solve(read_staff(src), None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "ns_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    ws = openpyxl.load_workbook(dst)["NHÂN SỰ"]
    assert len(ws.data_validations.dataValidation) == 4  # vẫn còn danh sách thả xuống
    rows = [r for r in ws.iter_rows(values_only=True) if any(v is not None for v in r)]
    assert rows[-1] == ("=ROW()-1", "chưa có", "Bộ Môn", None, 23, None)
    assert read_staff(dst)[-1].title == "bộ môn 1"  # tự đánh số khi đọc lại


def test_cli_converts_old_file(tmp_path, real_staff):
    out = tmp_path / "moi.xlsx"
    assert template_main([str(out), "--tu", str(STAFF_FILE)]) == 0
    assert _key(read_staff(out)) == _key(real_staff)
