import openpyxl

from tkb import config
from tkb.checker import check
from tkb.solver import solve
from tkb.staff import read_staff
from tkb import writer
from tkb.writer import write_timetable, write_updated_staff

from .conftest import small_staff


def _solve_small(general):
    return solve(small_staff(general), None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)


def test_timetable_layout(tmp_path):
    sol = _solve_small(general=True)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, check(sol.problem, sol.lessons), [])
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Khối 3", "Danh sách nhân sự", "Thống kê"]
    ws = wb["Khối 3"]
    # Bố cục theo Output_Template_TKB_V5_Formatted.xlsx: mỗi lớp 1 dòng tiêu đề + 7 tiết + 2 dòng trống.
    assert [ws.cell(1, c).value for c in range(1, 9)] == [
        "LỚP", "BUỔI", "TIẾT", "THỨ 2", "THỨ 3", "THỨ 4", "THỨ 5", "THỨ 6"]
    assert {str(r) for r in ws.merged_cells.ranges} == {
        "A2:A8", "B2:B5", "B6:B8", "A12:A18", "B12:B15", "B16:B18"}
    assert ws["A2"].value == "LỚP 3/1" and ws["A12"].value == "LỚP 3/2"
    assert ws["A11"].value == "LỚP"
    assert ws["B2"].value == "SÁNG" and ws["B6"].value == "CHIỀU"
    assert [ws.cell(r, 3).value for r in range(2, 9)] == [1, 2, 3, 4, 1, 2, 3]
    assert ws["D2"].value == "HĐTN\nchủ nhiệm 3/1"
    assert ws["H5"].value == "HĐTN\nchủ nhiệm 3/1"
    assert [ws.cell(r, 8).value for r in (6, 7, 8)] == ["Nghỉ"] * 3
    cells = [ws.cell(r, c).value for r in range(2, 9) for c in range(4, 9)]
    assert all(v for v in cells) and not any("thiếu" in v for v in cells)
    assert ws["D2"].font.name == "Times New Roman" and ws["D2"].font.sz == writer.FONT_SIZE == 14
    assert ws["A1"].font.sz == 14 and ws["A2"].font.sz == 14 and ws["C2"].font.sz == 14
    assert ws["A1"].fill.fgColor.rgb.endswith("F0F0F0") and ws["A1"].font.b
    assert ws.column_dimensions["A"].width == writer.COLUMN_WIDTHS["class"]
    assert ws.column_dimensions["D"].width == writer.COLUMN_WIDTHS["day"]
    assert ws.row_dimensions[2].height == writer.LESSON_ROW_HEIGHT
    assert ws["A5"].border.left.style == "thin"  # viền cả ô nằm trong vùng gộp
    stats = [v for row in wb["Thống kê"].iter_rows(values_only=True) for v in row if v is not None]
    assert "ĐẠT" in stats


def test_supplement_added_to_staff_list(tmp_path):
    sol = _solve_small(general=False)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, [], [])
    rows = list(openpyxl.load_workbook(out)["Danh sách nhân sự"].iter_rows(min_row=3, values_only=True))
    # Tuyển theo định mức đầy đủ 23 tiết, thực dạy 8 tiết.
    assert rows[-1][:4] == ("chưa có", "bộ môn 1", 23, 8)
    grid = [v for row in openpyxl.load_workbook(out)["Khối 3"].iter_rows(values_only=True) for v in row if v]
    assert any(isinstance(v, str) and v.endswith("\nbộ môn 1") for v in grid)


def test_updated_staff_file_is_reusable(tmp_path):
    src = tmp_path / "staff.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tên", "Chức vụ", "Số tiết"])
    for t in small_staff(general=False):
        ws.append([t.name, t.title, t.max_lessons])
    wb.save(src)
    sol = solve(read_staff(src), None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "staff_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    again = read_staff(dst)
    assert again[-1].name == "chưa có" and again[-1].title == "bộ môn 1"
    assert again[-1].max_lessons == 23
    sol2 = solve(again, None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    assert sol2.used_supplements() == []
    assert check(sol2.problem, sol2.lessons) == []


def test_overtime_columns(tmp_path):
    settings = config.Settings(time_limit=20, workers=4, mode=config.MODE_OVERTIME, overtime_max=4)
    sol = solve(small_staff(general=False), None, settings, log=lambda *_: None)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, check(sol.problem, sol.lessons), [])
    wb = openpyxl.load_workbook(out)
    staff = list(wb["Danh sách nhân sự"].iter_rows(min_row=2, values_only=True))
    assert staff[0] == ("Tên", "Chức vụ", "Số tiết", "Số tiết thực dạy", "Số tiết bù", "Ghi chú")
    assert staff[1][:5] == ("CN A", "chủ nhiệm 3/1", 19, 23, 4)
    stats = [v for row in wb["Thống kê"].iter_rows(values_only=True) for v in row if v is not None]
    assert "2. DẠY BÙ (vượt định mức)" in stats
    assert any(isinstance(v, str) and v.startswith("Bù giờ") for v in stats)
    assert any(isinstance(v, str) and "TNXH ×2" in v for v in stats)
