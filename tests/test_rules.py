"""Sheet QUY ĐỊNH của file vào (tkb/rules.py): đọc, kiểm tra, dùng thay giá trị mặc định trong tkb/config.py."""
import shutil

import openpyxl
import pytest

import main
from tkb import config
from tkb.rules import DEFAULTS, RULES, applied, changed, read_rules
from tkb.staff import InputError
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff


def _input(tmp_path, values=None, name="vao.xlsx"):
    """File vào trường nhỏ; `values`: {Quy định: Giá trị} ghi đè các dòng của sheet QUY ĐỊNH (None: xóa dòng)."""
    path = tmp_path / name
    write_staff_template(path, small_staff(general=False), CURRICULUM)
    if values:
        wb = openpyxl.load_workbook(path)
        ws = wb["QUY ĐỊNH"]
        rows = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1)}
        for label, value in values.items():
            r = rows.get(label) or ws.max_row + 1
            if value is None:
                ws.delete_rows(r)
                rows = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1)}
            else:
                ws.cell(r, 1, label)
                ws.cell(r, 2, value)
        wb.save(path)
    return path


def test_default_sheet_equals_config(tmp_path):
    assert read_rules(_input(tmp_path)) == DEFAULTS
    assert changed(DEFAULTS) == []


def test_file_without_sheet_uses_defaults(tmp_path):
    path = _input(tmp_path)
    wb = openpyxl.load_workbook(path)
    del wb["QUY ĐỊNH"]
    wb.save(path)
    assert read_rules(path) is None


def test_missing_rows_keep_defaults(tmp_path):
    rules = read_rules(_input(tmp_path, {"Môn nặng": None, "Ngày học": None}))
    assert "HEAVY_SUBJECTS" not in rules and "DAYS" in rules  # khung giờ ghép từ các dòng còn lại
    assert rules["DAY_SESSIONS"] == DEFAULTS["DAY_SESSIONS"]


def test_subject_names_written_like_the_program(tmp_path):
    """Tên môn khớp không phân biệt hoa thường, dấu câu, chữ "và"; chữ viết tắt (HĐTN) cũng được."""
    rules = read_rules(_input(tmp_path, {
        "Môn nặng": "toán, TIẾNG VIỆT, Thể Dục",
        "Môn chỉ GVCN dạy": "HĐTN",
        "Môn GVCN nhận trọn": "Tiếng Việt, Lịch Sử và Địa Lý",
        "Quản lý dạy": "Kỹ năng sống khối 4 lớp 4/1, 4/2; Đạo đức khối 5, Khoa học khối 3",
        "Số tiết tối đa mỗi ngày của môn": "Toán = 1; Tiếng Anh = 2",
        "Tiết hạn chế môn nặng": "6, 7",
        "Môn ưu tiên buổi sáng": "Tiếng Việt\nToán",  # xuống dòng trong ô cũng tách mục
    }))
    assert rules["HEAVY_SUBJECTS"] == {config.TOAN, config.TV, "Thể Dục"}
    assert rules["HOMEROOM_ONLY_SUBJECTS"] == {config.HDTN}
    assert rules["HOMEROOM_PRIORITY"] == [config.TV, config.LSDL]
    assert rules["MANAGER_RULES"] == [config.ManagerRule(config.KNS, 4, ("4/1", "4/2")),
                                      config.ManagerRule(config.DD, 5), config.ManagerRule(config.KH, 3)]
    assert rules["DAILY_LIMITS"] == {config.TOAN: 1, config.TIENG_ANH: 2}
    assert rules["HEAVY_LATE_PERIODS"] == {6, 7}
    assert rules["MORNING_SUBJECTS"] == {config.TV, config.TOAN}
    assert changed(rules) == ["Môn GVCN nhận trọn", "Quản lý dạy", "Số tiết tối đa mỗi ngày của môn", "Môn nặng",
                              "Tiết hạn chế môn nặng"]


def test_time_frame(tmp_path):
    rules = read_rules(_input(tmp_path, {"Ngày học": "Thứ 2, Thứ 3, Thứ 4, Thứ 5, Thứ 6, Thứ 7",
                                         "Ngày học buổi chiều": "T2, T3, T5", "Số tiết buổi chiều": 4,
                                         "Tiết hạn chế môn nặng": 8}))
    assert rules["DAYS"] == ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
    assert rules["AFTERNOON"].periods == (5, 6, 7, 8) and rules["MORNING"] == config.MORNING
    sessions = rules["DAY_SESSIONS"]
    assert [d for d, ss in sessions.items() if len(ss) == 2] == [0, 1, 3] and sessions[5] == (rules["MORNING"],)
    assert changed(rules) == ["Khung giờ", "Tiết hạn chế môn nặng"]


def test_all_errors_at_once(tmp_path):
    with pytest.raises(InputError) as err:
        read_rules(_input(tmp_path, {
            "Ngày học": "Thứ 2, Thứ 4",  # không liền nhau
            "Tiết HĐTN cố định": "Thứ 2 tiết 9",
            "Tiết luôn do GVCN dạy": "một",
            "Chức vụ được dạy bù": "Chủ Nhiệm, Quản Lý",
            "Môn tăng cường đi với môn chính": "Toán = Toán",
            "Số tiết tối đa một nhóm môn mỗi buổi": "",
            "Môn khó": "Toán",
        }))
    text = str(err.value)
    assert text.startswith("Sheet QUY ĐỊNH có 7 lỗi")
    for part in ("(Ngày học): ghi các ngày liền nhau", "Thứ 2 tiết 9: không có tiết này", "tiết phải là số",
                 "chỉ ghi Chủ Nhiệm, Bộ Môn", "môn chính không được là môn tăng cường", "ghi một số nguyên",
                 "không có quy định 'Môn khó'"):
        assert part in text


def test_applied_restores_config():
    before = config.HEAVY_LATE_PERIODS
    with applied({"HEAVY_LATE_PERIODS": {6}}):
        assert config.HEAVY_LATE_PERIODS == {6}
    assert config.HEAVY_LATE_PERIODS is before
    with applied(None):
        assert config.HEAVY_LATE_PERIODS is before


def _code(text):
    return next(line.split()[3] for line in text.splitlines() if line.startswith("Mã kết quả"))


def test_default_sheet_gives_the_same_timetable(tmp_path, capsys):
    """Có sheet QUY ĐỊNH (giá trị mặc định) hay không có sheet thì TKB như nhau."""
    with_sheet = _input(tmp_path)
    without = tmp_path / "khong_quy_dinh.xlsx"
    shutil.copy(with_sheet, without)
    wb = openpyxl.load_workbook(without)
    del wb["QUY ĐỊNH"]
    wb.save(without)
    codes = []
    for path, note in ((with_sheet, "giống mặc định"), (without, "mặc định của chương trình")):
        assert main.run(path, tmp_path / path.stem, thoi_gian_toi_da=10, che_do="tuyen_them") == 0
        out = capsys.readouterr().out
        assert note in out
        codes.append(_code(out))
    assert codes[0] == codes[1]
    # File cập nhật của file vào không có sheet QUY ĐỊNH thì có thêm sheet đó (các quy định đã dùng).
    assert read_rules(tmp_path / without.stem / "khong_quy_dinh_cap_nhat.xlsx") == DEFAULTS


def test_rules_from_the_sheet_are_used(tmp_path, capsys):
    """Thêm sáng Thứ 7, chiều 4 tiết: TKB có cột Thứ 7, kiểm tra luật đạt; chạy xong config trở lại mặc định."""
    path = _input(tmp_path, {"Ngày học": "Thứ 2, Thứ 3, Thứ 4, Thứ 5, Thứ 6, Thứ 7", "Số tiết buổi chiều": 4,
                             "Tiết hạn chế môn nặng": "8", "Môn nặng": "Toán"})
    assert main.run(path, tmp_path / "out", thoi_gian_toi_da=10, che_do="tuyen_them") == 0
    out = capsys.readouterr().out
    assert "khác mặc định: Khung giờ, Môn nặng, Tiết hạn chế môn nặng" in out
    assert "kiểm tra luật bắt buộc: ĐẠT" in out and "Môn nặng ở tiết 8:" in out
    ws = openpyxl.load_workbook(tmp_path / "out" / "TKB.xlsx")["Khối 3"]
    assert [c.value for c in ws[1]][3:] == ["THỨ 2", "THỨ 3", "THỨ 4", "THỨ 5", "THỨ 6", "THỨ 7"]
    assert [ws.cell(r, 3).value for r in range(2, 10)] == list(range(1, 9))  # sáng 1–4, chiều 5–8
    for attr, value in DEFAULTS.items():
        assert getattr(config, attr) == value


def test_every_rule_has_a_config_default():
    assert all(r.attr in DEFAULTS or r.attr in ("days", "afternoon_days", "morning_periods", "afternoon_periods")
               for r in RULES)


def test_changed_rules_in_updated_file_solve_again(tmp_path, capsys):
    """File vào cập nhật lưu mã quy định cùng TKB đã xếp: sửa sheet QUY ĐỊNH rồi nạp lại thì xếp lại theo quy định
    mới, không dùng lại TKB cũ."""
    from tkb.rules import code
    path = _input(tmp_path)
    assert main.run(path, tmp_path / "lan1", thoi_gian_toi_da=10, che_do="tuyen_them") == 0
    updated = tmp_path / "lan1" / "vao_cap_nhat.xlsx"
    ws = openpyxl.load_workbook(updated)["TKB đã xếp"]
    assert (ws["G1"].value, ws["H1"].value, ws["H2"].value) == ("Mã Kết Quả", "Mã Quy Định", code())
    wb = openpyxl.load_workbook(updated)
    rules = wb["QUY ĐỊNH"]
    row = next(r for r in range(2, rules.max_row + 1) if rules.cell(r, 1).value == "Môn nặng")
    rules.cell(row, 2, "Toán")
    wb.save(updated)
    capsys.readouterr()
    assert main.run(updated, tmp_path / "lan2", thoi_gian_toi_da=10, che_do="tuyen_them") == 0
    out = capsys.readouterr().out
    assert "khác mặc định: Môn nặng" in out and "xếp lại từ đầu theo quy định mới" in out
    assert "Dùng lại TKB đã xếp" not in out
