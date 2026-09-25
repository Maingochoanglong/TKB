import openpyxl

from tkb import config
from tkb.solver import solve
from tkb.staff import canonical_title, read_staff
from tkb.template import main as template_main, title_choices, write_staff_template
from tkb.writer import write_updated_staff

from .conftest import STAFF_FILE, STAFF_FILE_V6, small_staff


def _key(teachers):
    return [(t.name, t.title, t.max_lessons, t.maternity) for t in teachers]


def test_v6_file_matches_v5(real_staff):
    assert _key(read_staff(STAFF_FILE_V6)) == _key(real_staff)
    rows = list(openpyxl.load_workbook(STAFF_FILE_V6).worksheets[0].iter_rows(values_only=True))
    assert rows[0] == ("Tên", "Chức vụ", "Số tiết", "Thai sản")
    assert not any(str(r[1]).endswith(" ts") for r in rows[1:])  # thai sản ở cột riêng


def test_template_has_dropdowns(tmp_path, real_staff):
    path = tmp_path / "mau.xlsx"
    write_staff_template(path, real_staff)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["Nhân sự", "Danh mục"] and wb["Danh mục"].sheet_state == "hidden"
    dvs = {str(dv.sqref): dv for dv in wb["Nhân sự"].data_validations.dataValidation}
    assert dvs["B2:B300"].type == "list" and dvs["B2:B300"].formula1.startswith("'Danh mục'!")
    assert dvs["C2:C300"].type == "whole" and dvs["D2:D300"].formula1 == '"Có"'
    choices = [c.value for c in wb["Danh mục"]["A"]]
    assert choices == title_choices()
    assert all(canonical_title(t.role, t.index, t.class_name, False) in choices for t in real_staff)
    assert _key(read_staff(path)) == _key(real_staff)


def test_updated_staff_keeps_template(tmp_path):
    src = tmp_path / "ns.xlsx"
    write_staff_template(src, small_staff(general=False))
    sol = solve(read_staff(src), None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "ns_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    ws = openpyxl.load_workbook(dst).worksheets[0]
    assert len(ws.data_validations.dataValidation) == 3  # vẫn còn danh sách thả xuống
    assert list(ws.iter_rows(values_only=True))[-1] == ("chưa có", "bộ môn 1", 23, None)
    assert read_staff(dst)[-1].title == "bộ môn 1"


def test_cli_converts_old_file(tmp_path, real_staff):
    out = tmp_path / "moi.xlsx"
    assert template_main([str(out), "--tu", str(STAFF_FILE)]) == 0
    assert _key(read_staff(out)) == _key(real_staff)
