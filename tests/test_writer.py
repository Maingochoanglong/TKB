import openpyxl

from tkb import config
from tkb.checker import check
from tkb.solver import solve
from tkb.staff import build_teacher, read_staff
from tkb import writer
from tkb.style import Style
from tkb.writer import write_timetable, write_updated_staff

from .conftest import CURRICULUM, INPUT_FILE, small_staff

STYLE = Style.from_file(INPUT_FILE)  # style của file vào: Times New Roman 14, viền mảnh, dòng cao 25
STAFF_HEADER = ("Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Chế Độ", "Mã GV", "Số Tiết Thực Dạy")


def _solve_small(general):
    return solve(small_staff(general), CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)


def test_style_is_read_from_input_file():
    assert STYLE.header.font.name == "Times New Roman" and STYLE.header.font.sz == 14 and STYLE.header.font.b
    assert STYLE.header.fill is None and STYLE.body.border.left.style == "thin"
    assert STYLE.row_height == 25 and STYLE.line_height == 21


def test_timetable_layout(tmp_path):
    sol = _solve_small(general=True)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, check(sol.problem, sol.lessons), [], STYLE)
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
    assert ws["D2"].value == "HĐTN\nCN A"  # môn, xuống dòng tên giáo viên
    assert ws["H5"].value == "HĐTN\nCN A"
    assert [ws.cell(r, 8).value for r in (6, 7, 8)] == ["Nghỉ"] * 3
    cells = [ws.cell(r, c).value for r in range(2, 9) for c in range(4, 9)]
    assert all(v for v in cells) and not any("thiếu" in v for v in cells)
    # Style chép từ file vào.
    for cell in (ws["A1"], ws["A2"], ws["C2"], ws["D2"]):
        assert cell.font.name == "Times New Roman" and cell.font.sz == 14
    assert ws["A1"].font.b and ws["A1"].fill.fill_type is None and not ws["D2"].font.b
    assert ws.row_dimensions[1].height == 25
    assert ws.row_dimensions[2].height == 2 * STYLE.line_height  # môn + tên giáo viên
    assert ws["A5"].border.left.style == "thin"  # viền cả ô nằm trong vùng gộp
    assert ws.column_dimensions["D"].width >= STYLE.text_width("TV tăng cường")
    stats = [v for row in wb["Thống kê"].iter_rows(values_only=True) for v in row if v is not None]
    assert "ĐẠT" in stats


def test_supplement_added_to_staff_list(tmp_path):
    sol = _solve_small(general=False)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, [], [], STYLE)
    ws = openpyxl.load_workbook(out)["Danh sách nhân sự"]
    rows = list(ws.iter_rows(values_only=True))
    # Cột như sheet NHÂN SỰ của file vào, thêm các cột kết quả.
    assert rows[0] == STAFF_HEADER + ("Ghi Chú",)
    assert rows[1][:7] == ("CN A", "Chủ Nhiệm", "3/1", 19, None, "Chủ Nhiệm 3/1", 19)
    # Tuyển theo định mức đầy đủ 23 tiết, thực dạy 8 tiết.
    assert rows[-1][:7] == ("chưa có", "Bộ Môn", None, 23, None, "Bộ Môn 1", 8)
    assert ws["A1"].font.b and ws["A2"].font.sz == 14 and ws.row_dimensions[2].height == 25
    grid = [v for row in openpyxl.load_workbook(out)["Khối 3"].iter_rows(values_only=True) for v in row if v]
    assert any(isinstance(v, str) and v.endswith("\nBộ Môn 1") for v in grid)


def test_updated_staff_file_is_reusable(tmp_path):
    src = tmp_path / "staff.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tên", "Chức vụ", "Số tiết"])
    for t in small_staff(general=False):
        ws.append([t.name, t.title, t.max_lessons])
    wb.save(src)
    sol = solve(read_staff(src), CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "staff_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    rows = list(openpyxl.load_workbook(dst).active.iter_rows(values_only=True))
    assert rows[0] == ("Tên", "Chức vụ", "Số tiết", "Mã GV", "Số Tiết Thực Dạy")
    assert rows[-1] == ("chưa có", "bộ môn 1", 23, "Bộ Môn 1", 8)
    again = read_staff(dst)
    assert again[-1].name == "chưa có" and again[-1].title == "bộ môn 1"
    assert again[-1].max_lessons == 23
    sol2 = solve(again, CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    assert sol2.used_supplements() == []
    assert check(sol2.problem, sol2.lessons) == []


def test_overtime_columns(tmp_path):
    settings = config.Settings(time_limit=20, workers=4, mode=config.MODE_OVERTIME, overtime_max=4)
    sol = solve(small_staff(general=False), CURRICULUM, settings, log=lambda *_: None)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, check(sol.problem, sol.lessons), [], STYLE)
    wb = openpyxl.load_workbook(out)
    staff = list(wb["Danh sách nhân sự"].iter_rows(values_only=True))
    assert staff[0] == STAFF_HEADER + ("Số Tiết Bù", "Ghi Chú")
    assert staff[1][:8] == ("CN A", "Chủ Nhiệm", "3/1", 19, None, "Chủ Nhiệm 3/1", 23, 4)
    stats = [v for row in wb["Thống kê"].iter_rows(values_only=True) for v in row if v is not None]
    assert "2. DẠY BÙ (vượt định mức)" in stats
    assert any(isinstance(v, str) and v.startswith("Bù giờ") for v in stats)
    assert any(isinstance(v, str) and "TNXH ×2" in v for v in stats)


def test_teacher_labels():
    teachers = {t.title: t for t in [build_teacher("Lan", "chủ nhiệm 1/1", 19), build_teacher("Lan", "bộ môn 1", 23),
                                     build_teacher("", "bộ môn 2", 23), build_teacher("Hoa", "bộ môn 3", 23)]}
    teachers["bộ môn 2"].label = "Bộ Môn"
    labels = writer.teacher_labels(teachers)
    assert labels == {"chủ nhiệm 1/1": "Lan (chủ nhiệm 1/1)", "bộ môn 1": "Lan (bộ môn 1)",
                      "bộ môn 2": "Bộ Môn 2", "bộ môn 3": "Hoa"}


def test_blank_names_show_teacher_code(tmp_path):
    staff = small_staff()
    for t in staff:
        t.name = ""  # file vào để trống tên (bảo mật)
    sol = solve(staff, CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, [], [], STYLE)
    ws = openpyxl.load_workbook(out)["Khối 3"]
    assert ws["D2"].value == "HĐTN\nChủ Nhiệm 3/1"
    grid = {v.split("\n")[1] for row in ws.iter_rows(min_row=2, max_row=8, min_col=4, values_only=True)
            for v in row if v and "\n" in v}
    assert {"Tiếng Anh 1", "Thể dục 1"} <= grid  # chức vụ chuyên biệt ghi theo tên môn


def test_long_names_widen_columns_and_rows(tmp_path):
    staff = small_staff()
    staff[0].name = "Nguyễn Thị Thanh Hương Giang Mai"  # GVCN 3/1, tên rất dài
    sol = solve(staff, CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    out = tmp_path / "TKB.xlsx"
    write_timetable(sol, out, [], [], STYLE)
    ws = openpyxl.load_workbook(out)["Khối 3"]
    assert ws["D2"].value == "HĐTN\nNguyễn Thị Thanh Hương Giang Mai"
    assert ws.column_dimensions["D"].width == writer.MAX_DAY_WIDTH  # nới hết mức
    assert ws.row_dimensions[2].height > 2 * STYLE.line_height  # tên xuống dòng, hàng cao thêm


def test_statistics_file(tmp_path):
    out = tmp_path / "Thong_Ke.xlsx"
    writer.write_statistics(_solve_small(general=False), out, STYLE)
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Thống kê giáo viên", "Phân công", "Theo ngày", "Theo chức vụ"]
    ws = wb["Thống kê giáo viên"]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("STT", "Họ và Tên", "Chức Vụ", "Mã GV", "Số Tiết Quy Định", "Số Tiết Bù",
                       "Số Tiết Thực Dạy", "Số Tiết Còn Dư")
    assert rows[1] == (1, "CN A", "Chủ Nhiệm", "Chủ Nhiệm 3/1", 19, 0, 19, 0)
    assert rows[-2] == (8, "tuyển thêm", "Bộ Môn", "Bộ Môn 1", 23, 0, 8, 15)  # người cần tuyển
    assert rows[-1] == (None, "Tổng", None, None, 19 * 2 + 23 * 6, 0, 64, 19 * 2 + 23 * 6 - 64)
    assert ws["A1"].font.b and ws["B2"].font.name == "Times New Roman" and ws["B2"].border.left.style == "thin"
    assert ws.cell(len(rows), 2).font.b and ws.row_dimensions[2].height == 25

    assign = list(wb["Phân công"].iter_rows(min_row=2, values_only=True))
    assert any(r[1:] == ("CN A", "Chủ Nhiệm 3/1", "3/1", "HĐTN", 3) for r in assign)
    assert sum(r[5] for r in assign) == 64
    assert any(r[1:4] == ("tuyển thêm", "Bộ Môn 1", "3/2") for r in assign)

    daily = list(wb["Theo ngày"].iter_rows(values_only=True))
    assert daily[0][3:8] == ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6")
    assert all(sum(r[3:8]) == r[8] for r in daily[1:])
    assert daily[-1][8] == 64

    roles = {r[1]: r[2:] for r in wb["Theo chức vụ"].iter_rows(min_row=2, values_only=True)}
    assert roles["Chủ Nhiệm"] == (2, 38, 38, 0, 0, 0, 0)
    assert roles["Bộ Môn"] == (0, 0, 0, 0, 0, 1, 8)
    assert roles["Tổng"][5:] == (1, 8)


def test_statistics_file_overtime(tmp_path):
    settings = config.Settings(time_limit=20, workers=4, mode=config.MODE_OVERTIME, overtime_max=4)
    sol = solve(small_staff(general=False), CURRICULUM, settings, log=lambda *_: None)
    out = tmp_path / "Thong_Ke.xlsx"
    writer.write_statistics(sol, out, STYLE)
    wb = openpyxl.load_workbook(out)
    rows = list(wb["Thống kê giáo viên"].iter_rows(min_row=2, values_only=True))
    assert rows[0] == (1, "CN A", "Chủ Nhiệm", "Chủ Nhiệm 3/1", 19, 4, 23, 0) and rows[1][5] == 4
    assert all(r[1] != "tuyển thêm" for r in rows)
    assert rows[-1][1] == "Tổng" and rows[-1][5] == 8
    roles = {r[1]: r[2:] for r in wb["Theo chức vụ"].iter_rows(min_row=2, values_only=True)}
    assert roles["Chủ Nhiệm"][3] == 8  # cột Số tiết bù
