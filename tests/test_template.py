import openpyxl

from tkb import config
from tkb.program import read_program
from tkb.solver import solve
from tkb.staff import read_staff
from tkb.template import main as template_main, role_choices, write_staff_template
from tkb.writer import write_updated_staff

from .conftest import CURRICULUM, small_staff

HEADER = ("Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Thai Sản", "Hợp Đồng", "Cơ sở 2", "Lớp Đang Dạy", "Buổi Nghỉ")
NONE5 = (None,) * 5  # 5 cột không bắt buộc để trống


def _key(teachers):
    return [(t.name, t.title, t.max_lessons) for t in teachers]


def _rows(ws):
    return [r for r in ws.iter_rows(values_only=True) if any(v is not None for v in r)]


def test_template_style_and_dropdowns(tmp_path, sample_staff):
    path = tmp_path / "mau.xlsx"
    write_staff_template(path, sample_staff, CURRICULUM)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC", "Danh mục"]
    assert wb["Danh mục"].sheet_state == "hidden"
    ws = wb["NHÂN SỰ"]
    # Style như file của nhà trường: Times New Roman 14, tiêu đề đậm không tô nền, viền mảnh, dòng cao 25.
    assert ws["A1"].font.name == "Times New Roman" and ws["A1"].font.sz == 14 and ws["A1"].font.b
    assert ws["A1"].fill.fill_type is None
    assert ws["B2"].font.sz == 14 and not ws["B2"].font.b and ws["B2"].border.left.style == "thin"
    assert ws["B2"].alignment.horizontal == "center" and ws.row_dimensions[2].height == 25
    dvs = {str(dv.sqref): dv for dv in ws.data_validations.dataValidation}
    assert dvs["B2:B300"].type == "list" and not dvs["B2:B300"].showErrorMessage  # chỉ gợi ý
    assert dvs["C2:C300"].type == "custom" and dvs["D2:D300"].type == "whole"
    assert dvs["E2:G300"].type == "list" and dvs["E2:G300"].formula1 == '"Có"'
    assert len(dvs) == 4 and ws.max_column == 9
    program = _rows(wb["CHƯƠNG TRÌNH HỌC"])
    assert program[0] == ("Môn học", "Khối 1", "Khối 2", "Khối 3", "Khối 4", "Khối 5")
    assert len(program) == 17
    assert [c.value for c in wb["Danh mục"]["A"] if c.value] == role_choices(sample_staff)
    assert role_choices(sample_staff) == ["Chủ Nhiệm", "Bộ Môn", "Tiếng Anh", "Thể Dục", "Âm Nhạc", "Mỹ Thuật",
                                        "Tin Học", "Quản Lý"]
    assert ws["C2"].number_format == ws["H2"].number_format == "@"  # chữ để Excel không đổi thành ngày tháng
    assert len(ws.conditional_formatting) >= 1
    assert _key(read_staff(path)) == _key(sample_staff)
    assert read_program(path) == CURRICULUM


def test_blank_template_has_only_headers(tmp_path):
    path = tmp_path / "trong.xlsx"
    write_staff_template(path)
    wb = openpyxl.load_workbook(path)
    assert _rows(wb["NHÂN SỰ"]) == [HEADER]
    assert _rows(wb["CHƯƠNG TRÌNH HỌC"]) == [("Môn học", "Khối 1", "Khối 2", "Khối 3", "Khối 4", "Khối 5")]
    assert [c.value for c in wb["Danh mục"]["A"]] == ["Chủ Nhiệm", "Bộ Môn", "Quản Lý"]


def test_updated_staff_keeps_template_and_style(tmp_path):
    src = tmp_path / "ns.xlsx"
    write_staff_template(src, small_staff(general=False), CURRICULUM)
    sol = solve(read_staff(src), CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "ns_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    wb = openpyxl.load_workbook(dst)
    ws = wb["NHÂN SỰ"]
    # File mẫu có danh sách thả xuống, định dạng theo điều kiện, sheet danh mục ẩn và ghi chú hướng dẫn ở tiêu đề
    # cột; file cập nhật (file kết quả) chỉ còn chữ, số và màu.
    assert len(openpyxl.load_workbook(src)["NHÂN SỰ"].data_validations.dataValidation) == 4
    assert not ws.data_validations.dataValidation and not len(ws.conditional_formatting)
    assert "Danh mục" not in wb.sheetnames
    assert any(c.comment for c in openpyxl.load_workbook(src)["NHÂN SỰ"][1])
    assert not any(c.comment for sheet in wb.worksheets for row in sheet.iter_rows() for c in row)
    rows = _rows(ws)
    assert rows[0] == HEADER + ("Mã GV", "Số Tiết Thực Dạy", "Số Tiết Dư")
    assert rows[1] == ("CN A", "Chủ Nhiệm", "3/1", 19, *NONE5, "Chủ Nhiệm 3/1", 19, None)
    assert rows[-1] == ("chưa có", "Bộ Môn", None, 23, *NONE5, "Bộ Môn 1", 8, 15)
    # Dòng mới và cột mới cùng style với file vào.
    last = len(rows)
    for cell in (ws.cell(last, 2), ws.cell(last, 10), ws.cell(1, 11)):
        assert cell.font.name == "Times New Roman" and cell.font.sz == 14 and cell.border.left.style == "thin"
    assert ws.cell(1, 11).font.b and ws.row_dimensions[last].height == 25
    assert _rows(wb["CHƯƠNG TRÌNH HỌC"])[1:] == _rows(openpyxl.load_workbook(src)["CHƯƠNG TRÌNH HỌC"])[1:]
    again = read_staff(dst)
    assert again[-1].title == "bộ môn 1"  # tự đánh số khi đọc lại
    # Chạy lại trên file cập nhật: không tuyển thêm nữa, các cột kết quả được ghi đè chứ không thêm mới.
    sol2 = solve(again, CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    assert sol2.used_supplements() == []
    write_updated_staff(sol2, dst, tmp_path / "lan2.xlsx")
    rows2 = _rows(openpyxl.load_workbook(tmp_path / "lan2.xlsx")["NHÂN SỰ"])
    assert rows2[0] == rows[0] and len(rows2) == len(rows)


def test_cli_writes_blank_template(tmp_path):
    out = tmp_path / "moi.xlsx"
    assert template_main([str(out)]) == 0
    assert _rows(openpyxl.load_workbook(out)["NHÂN SỰ"]) == [HEADER]


def test_optional_columns_round_trip(tmp_path):
    """Các cột Thai Sản, Hợp Đồng, Cơ sở 2, Lớp Đang Dạy, Buổi Nghỉ ghi ra file mẫu rồi đọc lại đúng."""
    from dataclasses import replace
    staff = small_staff()
    staff = [replace(t, campus2=True, maternity=True, off_any=(("Chiều", 2),)) if t.class_name == "3/1" else
             replace(t, contract=True, history=frozenset({"3/1"}), off_sessions=frozenset({(3, "Chiều"), (4, "Sáng")}))
             if not t.class_name else t for t in staff]
    path = tmp_path / "mau.xlsx"
    write_staff_template(path, staff, CURRICULUM)
    ws = openpyxl.load_workbook(path)["NHÂN SỰ"]
    assert [c.value for c in ws[4]][4:] == [None, "Có", None, "3/1", "Chiều T5, Sáng T6"]  # dòng TA
    fields = lambda ts: [(t.maternity, t.contract, t.campus2, t.history, t.off_sessions, t.off_any) for t in ts]
    assert fields(read_staff(path)) == fields(staff)


def test_updated_staff_turns_formulas_into_values(tmp_path):
    """Cột STT ghi công thức =ROW()-1: file cập nhật ghi số, người cần tuyển nhận số tiếp theo."""
    src = tmp_path / "stt.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NHÂN SỰ"
    ws.append(["STT", *HEADER[:4]])
    for t in small_staff(general=False):
        ws.append(["=ROW()-1", t.name, t.role.title(), t.class_name, t.max_lessons])
    prog = wb.create_sheet("CHƯƠNG TRÌNH HỌC")
    prog.append(["Môn học", "Khối 3"])
    for subject, n in CURRICULUM[3].items():
        prog.append([subject, n])
    wb.save(src)
    sol = solve(read_staff(src), CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    dst = tmp_path / "stt_cap_nhat.xlsx"
    write_updated_staff(sol, src, dst)
    out = openpyxl.load_workbook(dst)["NHÂN SỰ"]
    stt = [out.cell(r, 1).value for r in range(2, out.max_row + 1) if out.cell(r, 2).value]
    assert stt == list(range(1, len(stt) + 1)) and len(stt) == len(small_staff(general=False)) + 1
    assert not any(c.data_type == "f" for row in out.iter_rows() for c in row)
