import openpyxl

from tkb import config
from tkb.checker import check
from tkb.solver import solve
from tkb.staff import read_staff
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
    assert {str(r) for r in ws.merged_cells.ranges} == {"A1:F1", "A12:F12"}
    assert ws["A1"].value == "THỜI KHÓA BIỂU LỚP 3/1"
    assert ws["A12"].value == "THỜI KHÓA BIỂU LỚP 3/2"
    assert [ws.cell(2, c).value for c in range(1, 7)] == ["Tiết / Ngày", *config.DAYS]
    assert ws["A3"].value == "Tiết 1 (Sáng)" and ws["A9"].value == "Tiết 7 (Chiều)"
    assert ws["B3"].value == "chủ nhiệm 3/1 (HĐTN)"
    assert ws["F6"].value == "chủ nhiệm 3/1 (HĐTN)"
    assert [ws.cell(r, 6).value for r in (7, 8, 9)] == ["Nghỉ"] * 3
    cells = [ws.cell(r, c).value for r in range(3, 10) for c in range(2, 7)]
    assert all(v for v in cells) and not any("thiếu" in v for v in cells)
    stats = [v for row in wb["Thống kê"].iter_rows(values_only=True) for v in row if v is not None]
    assert "ĐẠT" in stats


def test_supplement_added_to_staff_list(tmp_path):
    sol = _solve_small(general=False)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, [], [])
    rows = list(openpyxl.load_workbook(out)["Danh sách nhân sự"].iter_rows(min_row=3, values_only=True))
    assert rows[-1][:4] == ("chưa có", "bộ môn 1", 8, 8)
    grid = [v for row in openpyxl.load_workbook(out)["Khối 3"].iter_rows(values_only=True) for v in row if v]
    assert any(v.startswith("bộ môn 1 (") for v in grid)


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
    sol2 = solve(again, None, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    assert sol2.used_supplements() == []
    assert check(sol2.problem, sol2.lessons) == []
