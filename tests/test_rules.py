"""Các sheet QUY ĐỊNH của file vào (tkb/rules.py): đọc, kiểm tra, dùng thay giá trị mặc định trong tkb/config.py."""
import shutil

import openpyxl
import pytest

import main
from tkb import config
from tkb.rules import ATTRS, DEFAULTS, LABELS, applied, changed, code, read_rules
from tkb.staff import InputError
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff

CHUNG, NGAY, TIET, MON = config.RULES_SHEETS


def _input(tmp_path, edits=(), name="vao.xlsx"):
    """File vào trường nhỏ (các sheet quy định ghi mặc định). `edits`: (sheet, ô cột đầu, tiêu đề cột, giá trị); ô cột
    đầu chưa có thì thêm dòng, cột chưa có thì thêm cột; sheet CHUNG ghi vào cột Giá trị."""
    path = tmp_path / name
    write_staff_template(path, small_staff(general=False), CURRICULUM)
    if edits:
        wb = openpyxl.load_workbook(path)
        for sheet, key, header, value in edits:
            ws = wb[sheet]
            heads = {c.value: c.column for c in ws[1]}
            header = "Giá trị" if sheet == CHUNG else header
            if header not in heads:  # cột mới
                heads[header] = ws.max_column + 1
                ws.cell(1, heads[header], header)
            row = next((r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == key), ws.max_row + 1)
            ws.cell(row, 1, key)
            ws.cell(row, heads[header]).value = value
        wb.save(path)
    return path


def _drop(path, sheet, header=None):
    """Xóa cả sheet, hoặc một cột của sheet."""
    wb = openpyxl.load_workbook(path)
    if header is None:
        del wb[sheet]
    else:
        ws = wb[sheet]
        ws.delete_cols(next(c.column for c in ws[1] if c.value == header))
    wb.save(path)


def test_default_sheets_equal_config(tmp_path):
    rules = read_rules(_input(tmp_path))
    assert rules == DEFAULTS and changed(rules) == []
    # Cùng thứ tự (thứ tự dựng mô hình): nhóm môn, môn GVCN, ô HĐTN.
    for attr in ("SUBJECT_GROUPS", "HOMEROOM_PRIORITY", "HOMEROOM_CUT_ORDER", "HOMEROOM_FILL_ORDER", "HDTN_FIXED_SLOTS"):
        assert list(rules[attr]) == list(DEFAULTS[attr])


def test_file_without_rule_sheets_uses_defaults(tmp_path):
    path = _input(tmp_path)
    for sheet in config.RULES_SHEETS:
        _drop(path, sheet)
    assert read_rules(path) is None


def test_missing_sheet_or_column_keeps_defaults(tmp_path):
    path = _input(tmp_path)
    _drop(path, TIET)
    _drop(path, MON, "Môn nặng")
    rules = read_rules(path)
    assert "HEAVY_SUBJECTS" not in rules and "HOMEROOM_PERIODS" not in rules and "HEAVY_LATE_PERIODS" not in rules
    assert rules["DAY_SESSIONS"] == DEFAULTS["DAY_SESSIONS"] and rules["MORNING_SUBJECTS"] == DEFAULTS["MORNING_SUBJECTS"]


def test_subject_table(tmp_path):
    """Có/Không viết kiểu nào cũng được (x, không, trống); tên môn khớp không phân biệt hoa thường, chữ "và"."""
    rules = read_rules(_input(tmp_path, [
        (MON, "Tiếng Việt", "Môn nặng", None), (MON, "Thể dục", "Môn nặng", "x"), (MON, "Toán", "Môn nặng", "có"),
        (MON, "Khoa học", "Môn nặng", "không"),
        (MON, "Lịch sử - Địa lý", "Môn học", "Lịch Sử và Địa Lý"),
        (MON, "Đạo đức", "GVCN nhận trọn", 7), (MON, "Tiếng Việt", "GVCN nhận trọn", 9),
        (MON, "Đạo đức", "Quản lý dạy khối", 5),
        (MON, "Tiếng Anh", "Tối đa tiết mỗi ngày", 2),
        (MON, "Thể dục", "Tên trong TKB", "TD"),
    ]))
    assert rules["HEAVY_SUBJECTS"] == {config.TOAN, config.TOAN_TC, config.TV_TC, config.TIENG_ANH, config.TIN_HOC,
                                       "Thể dục"}
    assert rules["HOMEROOM_PRIORITY"] == [config.TOAN, config.HDTN, config.KH, config.LSDL, config.DD, config.TV]
    assert rules["MANAGER_RULES"] == [config.ManagerRule(config.DD, 5), config.ManagerRule(config.KNS, 4)]  # thứ tự dòng
    assert rules["DAILY_LIMITS"] == {config.TOAN: 1, config.TIENG_ANH: 2}
    assert rules["DISPLAY_NAMES"]["Thể dục"] == "TD"
    assert changed(rules) == ["Tên trong TKB", "GVCN nhận trọn", "Quản lý dạy khối", "Tối đa tiết mỗi ngày",
                              "Môn nặng"]


def test_subject_groups(tmp_path):
    """Nhóm môn: môn chính và môn tăng cường cùng số; số nhỏ trước."""
    rules = read_rules(_input(tmp_path, [(MON, "Toán", "Nhóm môn", 1), (MON, "Toán tăng cường", "Nhóm môn", 1),
                                         (MON, "Tiếng Việt", "Nhóm môn", 2),
                                         (MON, "Tiếng Việt tăng cường", "Nhóm môn", 2)]))
    assert list(rules["SUBJECT_GROUPS"].items()) == [(config.TOAN_TC, config.TOAN), (config.TV_TC, config.TV)]


def test_time_frame(tmp_path):
    rules = read_rules(_input(tmp_path, [
        (NGAY, "Thứ 7", "Học buổi sáng", "Có"), (NGAY, "Thứ 4", "Học buổi chiều", "Không"),
        (CHUNG, "Số tiết buổi chiều", None, 4),
        (TIET, 7, "Hạn chế môn nặng", "Không"), (TIET, 8, "Hạn chế môn nặng", "Có"),
    ]))
    assert rules["DAYS"] == ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
    assert rules["AFTERNOON"].periods == (5, 6, 7, 8) and rules["MORNING"] == config.MORNING
    sessions = rules["DAY_SESSIONS"]
    assert [d for d, ss in sessions.items() if len(ss) == 2] == [0, 1, 3] and sessions[5] == (rules["MORNING"],)
    assert rules["HEAVY_LATE_PERIODS"] == {8}
    assert changed(rules) == ["Khung giờ", "Hạn chế môn nặng"]


def test_all_errors_at_once(tmp_path):
    with pytest.raises(InputError) as err:
        read_rules(_input(tmp_path, [
            (CHUNG, "Số tiết buổi sáng", None, 0),
            (CHUNG, "Chủ Nhiệm được dạy bù", None, "Có lẽ"),
            (NGAY, "Thứ 4", "Học buổi sáng", "Không"),  # ngày học không liền nhau
            (NGAY, "Thứ 2", "Tiết HĐTN cố định", 9),
            (TIET, 1, "Luôn do GVCN dạy", "Chắc"),
            (MON, "Toán", "GVCN nhận trọn", 1),  # trùng số với Tiếng Việt
            (MON, "Tin học", "Môn HĐTN", "Có"),  # hai môn HĐTN
            (MON, "Thể dục", "Môn tăng cường", "Có"),  # chưa có Nhóm môn
            (MON, "Tiếng Việt", "Môn khó", "Có"),  # cột lạ (thêm vào dòng tiêu đề bên dưới)
        ]))
    text = str(err.value)
    for part in ("QUY ĐỊNH CHUNG, dòng 2: cột Số tiết buổi sáng ghi một số nguyên dương, đang ghi 0",
                 "cột Chủ Nhiệm được dạy bù chỉ ghi Có hoặc Không, đang ghi 'Có lẽ'",
                 "QUY ĐỊNH NGÀY: các ngày Học buổi sáng phải liền nhau từ Thứ 2",
                 "Xếp tiết HĐTN còn lại vào Thứ 4 nhưng ngày đó không học",
                 "Tiết HĐTN cố định Thứ 2 tiết 9 không có trong khung giờ",
                 "QUY ĐỊNH TIẾT, dòng 2: cột Luôn do GVCN dạy chỉ ghi Có hoặc Không",
                 "cột GVCN nhận trọn: số thứ tự 1 bị lặp (Tiếng Việt)",
                 "cột Môn HĐTN chỉ ghi Có ở một môn (đã có Hoạt động trải nghiệm)",
                 "môn tăng cường Thể dục chưa ghi Nhóm môn",
                 "không có quy định nào tên 'Môn khó'"):
        assert part in text, part
    assert text.startswith("Các sheet quy định có 10 lỗi")


def test_old_rules_sheet_is_reported(tmp_path):
    path = _input(tmp_path)
    wb = openpyxl.load_workbook(path)
    ws = wb.create_sheet("QUY ĐỊNH")
    ws.append(["Quy định", "Giá trị", "Ghi chú"])
    ws.append(["Môn nặng", "Toán"])
    wb.save(path)
    with pytest.raises(InputError, match="mẫu cũ"):
        read_rules(path)


def test_applied_restores_config():
    before = config.HEAVY_LATE_PERIODS
    with applied({"HEAVY_LATE_PERIODS": {6}}):
        assert config.HEAVY_LATE_PERIODS == {6}
    assert config.HEAVY_LATE_PERIODS is before
    with applied(None):
        assert config.HEAVY_LATE_PERIODS is before


def test_every_rule_has_a_label():
    assert all(attr in LABELS for attr in ATTRS)


def _code(text):
    return next(line.split()[3] for line in text.splitlines() if line.startswith("Mã kết quả"))


def test_default_sheets_give_the_same_timetable(tmp_path, capsys):
    """Có các sheet quy định (giá trị mặc định) hay không có thì TKB như nhau."""
    with_sheets = _input(tmp_path)
    without = tmp_path / "khong_quy_dinh.xlsx"
    shutil.copy(with_sheets, without)
    for sheet in config.RULES_SHEETS:
        _drop(without, sheet)
    codes = []
    for path, note in ((with_sheets, "giống mặc định"), (without, "mặc định của chương trình")):
        assert main.run(path, tmp_path / path.stem, thoi_gian_toi_da=10, che_do="tuyen_them") == 0
        out = capsys.readouterr().out
        assert note in out
        codes.append(_code(out))
    assert codes[0] == codes[1]
    # File cập nhật của file vào không có các sheet quy định thì có thêm các sheet đó (các quy định đã dùng).
    assert read_rules(tmp_path / without.stem / "khong_quy_dinh_cap_nhat.xlsx") == DEFAULTS


def test_rules_from_the_sheets_are_used(tmp_path, capsys):
    """Thêm sáng Thứ 7, chiều 4 tiết: TKB có cột Thứ 7, kiểm tra luật đạt; chạy xong config trở lại mặc định."""
    path = _input(tmp_path, [(NGAY, "Thứ 7", "Học buổi sáng", "Có"), (CHUNG, "Số tiết buổi chiều", None, 4),
                             (TIET, 7, "Hạn chế môn nặng", "Không"), (TIET, 8, "Hạn chế môn nặng", "Có")])
    assert main.run(path, tmp_path / "out", thoi_gian_toi_da=10, che_do="tuyen_them") == 0
    out = capsys.readouterr().out
    assert "khác mặc định: Khung giờ, Hạn chế môn nặng" in out
    assert "kiểm tra luật bắt buộc: ĐẠT" in out and "Môn nặng ở tiết 8:" in out
    ws = openpyxl.load_workbook(tmp_path / "out" / "TKB.xlsx")["Khối 3"]
    assert [c.value for c in ws[1]][3:] == ["THỨ 2", "THỨ 3", "THỨ 4", "THỨ 5", "THỨ 6", "THỨ 7"]
    assert [ws.cell(r, 3).value for r in range(2, 10)] == list(range(1, 9))  # sáng 1–4, chiều 5–8
    for attr, value in DEFAULTS.items():
        assert getattr(config, attr) == value


def test_changed_rules_in_updated_file_solve_again(tmp_path, capsys):
    """File vào cập nhật lưu mã quy định cùng TKB đã xếp: sửa quy định rồi nạp lại thì xếp lại theo quy định mới,
    không dùng lại TKB cũ."""
    path = _input(tmp_path)
    assert main.run(path, tmp_path / "lan1", thoi_gian_toi_da=10, che_do="tuyen_them") == 0
    updated = tmp_path / "lan1" / "vao_cap_nhat.xlsx"
    ws = openpyxl.load_workbook(updated)["TKB đã xếp"]
    assert (ws["G1"].value, ws["H1"].value, ws["H2"].value) == ("Mã Kết Quả", "Mã Quy Định", code())
    wb = openpyxl.load_workbook(updated)
    rules = wb[MON]
    row = next(r for r in range(2, rules.max_row + 1) if rules.cell(r, 1).value == "Tiếng Việt")
    col = next(c.column for c in rules[1] if c.value == "Môn nặng")
    rules.cell(row, col, "Không")
    wb.save(updated)
    capsys.readouterr()
    assert main.run(updated, tmp_path / "lan2", thoi_gian_toi_da=10, che_do="tuyen_them") == 0
    out = capsys.readouterr().out
    assert "khác mặc định: Môn nặng" in out and "xếp lại từ đầu theo quy định mới" in out
    assert "Dùng lại TKB đã xếp" not in out
