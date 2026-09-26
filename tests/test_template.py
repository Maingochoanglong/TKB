import openpyxl

from tkb import config
from tkb.program import read_program
from tkb.solver import solve
from tkb.staff import read_staff
from tkb.template import main as template_main, role_choices, write_staff_template
from tkb.writer import write_updated_staff

from .conftest import CURRICULUM, INPUT_FILE, small_staff

HEADER = ("Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần")


def _key(teachers):
    return [(t.name, t.title, t.max_lessons) for t in teachers]


def _rows(ws):
    return [r for r in ws.iter_rows(values_only=True) if any(v is not None for v in r)]


def test_sample_input_file(sample_staff):
    assert len(sample_staff) == 45 and sum(n for req in CURRICULUM.values() for n in req.values()) == 5 * 32
    wb = openpyxl.load_workbook(INPUT_FILE)
    rows = _rows(wb["NHÂN SỰ"])
    assert rows[0] == HEADER
    assert rows[1] == ("Giáo viên CN 1", "Chủ Nhiệm", "1/1", 19)
    assert ("Giáo viên BM 5", "Bộ Môn", None, 19) in rows


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
    assert len(dvs) == 3 and ws.max_column == 4
    program = _rows(wb["CHƯƠNG TRÌNH HỌC"])
    assert program[0] == ("Môn học", "Khối 1", "Khối 2", "Khối 3", "Khối 4", "Khối 5")
    assert len(program) == 17
    assert [c.value for c in wb["Danh mục"]["A"] if c.value] == role_choices(sample_staff)
    assert role_choices(sample_staff) == ["Chủ Nhiệm", "Bộ Môn", "Tiếng Anh", "Thể Dục", "Âm Nhạc", "Mỹ Thuật",
                                        "Tin Học", "Quản Lý"]
    assert ws["C2"].number_format == "@"  # Lớp là chữ để Excel không đổi thành ngày tháng
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
    assert len(ws.data_validations.dataValidation) == 3  # vẫn còn danh sách thả xuống
    rows = _rows(ws)
    assert rows[0] == HEADER + ("Mã GV", "Số Tiết Thực Dạy")
    assert rows[1] == ("CN A", "Chủ Nhiệm", "3/1", 19, "Chủ Nhiệm 3/1", 19)
    assert rows[-1] == ("chưa có", "Bộ Môn", None, 23, "Bộ Môn 1", 8)
    # Dòng mới và cột mới cùng style với file vào.
    last = len(rows)
    for cell in (ws.cell(last, 2), ws.cell(last, 5), ws.cell(1, 6)):
        assert cell.font.name == "Times New Roman" and cell.font.sz == 14 and cell.border.left.style == "thin"
    assert ws.cell(1, 6).font.b and ws.row_dimensions[last].height == 25
    assert _rows(wb["CHƯƠNG TRÌNH HỌC"])[1:] == _rows(openpyxl.load_workbook(src)["CHƯƠNG TRÌNH HỌC"])[1:]
    again = read_staff(dst)
    assert again[-1].title == "bộ môn 1"  # tự đánh số khi đọc lại
    # Chạy lại trên file cập nhật: không tuyển thêm nữa, các cột kết quả được ghi đè chứ không thêm mới.
    sol2 = solve(again, CURRICULUM, config.Settings(time_limit=20, workers=4), log=lambda *_: None)
    assert sol2.used_supplements() == []
    write_updated_staff(sol2, dst, tmp_path / "lan2.xlsx")
    rows2 = _rows(openpyxl.load_workbook(tmp_path / "lan2.xlsx")["NHÂN SỰ"])
    assert rows2[0] == rows[0] and len(rows2) == len(rows)


def _old_files(tmp_path, teachers):
    """File nhân sự kiểu cũ (V5/V6: chức vụ kèm số, vd "bộ môn 5") và file chương trình học riêng."""
    staff = openpyxl.Workbook()
    staff.active.append(["Tên", "Chức vụ", "Số tiết"])
    for t in teachers:
        staff.active.append([t.name, t.title, t.max_lessons])
    program = openpyxl.Workbook()
    grades = sorted(CURRICULUM)
    program.active.append(["Môn học", *(f"Khối {g}" for g in grades)])
    for subject in dict.fromkeys(s for g in grades for s in CURRICULUM[g]):
        program.active.append([subject, *(CURRICULUM[g].get(subject, 0) for g in grades)])
    paths = tmp_path / "nhan_su_cu.xlsx", tmp_path / "chuong_trinh.xlsx"
    staff.save(paths[0])
    program.save(paths[1])
    return paths


def test_cli_converts_old_file(tmp_path, sample_staff):
    out = tmp_path / "moi.xlsx"
    staff_file, program_file = _old_files(tmp_path, sample_staff)
    assert template_main([str(out), "--tu", str(staff_file), "--program", str(program_file)]) == 0
    assert _key(read_staff(out)) == _key(sample_staff)
    assert read_program(out) == CURRICULUM
