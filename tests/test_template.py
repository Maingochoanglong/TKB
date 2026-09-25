import openpyxl

from tkb import config
from tkb.solver import solve
from tkb.staff import read_staff
from tkb.template import class_choices, main as template_main, role_choices, write_staff_template
from tkb.writer import write_updated_staff

from .conftest import STAFF_FILE, STAFF_FILE_V6, STAFF_FILE_V7, small_staff


def _key(teachers):
    return [(t.name, t.title, t.max_lessons, t.maternity) for t in teachers]


def test_v7_file_matches_v5(real_staff):
    assert _key(read_staff(STAFF_FILE_V7)) == _key(real_staff)
    rows = list(openpyxl.load_workbook(STAFF_FILE_V7).worksheets[0].iter_rows(values_only=True))
    assert rows[0] == ("Họ và Tên", "Chức Vụ", "Lớp", "Chế độ", "Số Tiết/Tuần")
    assert rows[1] == ("Giáo viên CN 1", "Chủ Nhiệm", "1/1", None, 19)
    assert ("Giáo viên BM 5 (Thai sản)", "Bộ Môn", None, "Thai sản", 19) in rows


def test_old_formats_still_read(real_staff):
    assert _key(read_staff(STAFF_FILE_V6)) == _key(real_staff)


def test_template_has_dropdowns(tmp_path, real_staff):
    path = tmp_path / "mau.xlsx"
    write_staff_template(path, real_staff)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["Nhân sự", "Danh mục"] and wb["Danh mục"].sheet_state == "hidden"
    ws = wb["Nhân sự"]
    dvs = {str(dv.sqref): dv for dv in ws.data_validations.dataValidation}
    assert dvs["B2:B300"].type == "list" and dvs["B2:B300"].formula1.startswith("'Danh mục'!$A")
    assert dvs["C2:C300"].type == "list" and dvs["C2:C300"].formula1.startswith("'Danh mục'!$B")
    assert dvs["D2:D300"].formula1 == '"Thai sản"' and dvs["E2:E300"].type == "whole"
    lists = wb["Danh mục"]
    assert [c.value for c in lists["A"] if c.value] == role_choices()
    assert role_choices() == ["Chủ Nhiệm", "Thể Dục", "Tiếng Anh", "Mỹ Thuật", "Bộ Môn", "Âm Nhạc", "Tin Học",
                              "Quản Lý"]
    assert [c.value for c in lists["B"] if c.value] == class_choices() and "5/10" in class_choices()
    assert ws["C2"].number_format == "@"  # Lớp là chữ để Excel không đổi thành ngày tháng
    assert len(ws.conditional_formatting) >= 1
    assert _key(read_staff(path)) == _key(real_staff)


def test_updated_staff_keeps_template(tmp_path):
    src = tmp_path / "ns.xlsx"
    write_staff_template(src, small_staff(general=False))
    sol = solve(read_staff(src), None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "ns_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    ws = openpyxl.load_workbook(dst).worksheets[0]
    assert len(ws.data_validations.dataValidation) == 4  # vẫn còn danh sách thả xuống
    rows = [r for r in ws.iter_rows(values_only=True) if any(v is not None for v in r)]
    assert rows[-1] == ("chưa có", "Bộ Môn", None, None, 23)
    assert read_staff(dst)[-1].title == "bộ môn 1"  # tự đánh số khi đọc lại


def test_cli_converts_old_file(tmp_path, real_staff):
    out = tmp_path / "moi.xlsx"
    assert template_main([str(out), "--tu", str(STAFF_FILE)]) == 0
    assert _key(read_staff(out)) == _key(real_staff)
