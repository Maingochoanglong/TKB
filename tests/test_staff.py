import openpyxl
import pytest

from tkb import config
from tkb.program import read_program
from tkb.staff import InputError, build_teacher, classes_from_staff, parse_title, read_staff, validate

from .conftest import PROGRAM_FILE


def test_parse_titles():
    assert parse_title("chủ nhiệm 1/1") == ("chủ nhiệm", None, "1/1", False)
    assert parse_title("  Chủ  nhiệm 5 / 5 ts ") == ("chủ nhiệm", None, "5/5", True)
    assert parse_title("bộ môn 5 ts") == ("bộ môn", 5, None, True)
    assert parse_title("Tiếng Anh 3") == ("tiếng anh", 3, None, False)
    assert parse_title("quản lý 1") == ("quản lý", 1, None, False)


@pytest.mark.parametrize("bad", ["hiệu trưởng 1", "bộ môn", "chủ nhiệm 1", "bộ môn 1/2", "thể dục một"])
def test_parse_title_rejects(bad):
    with pytest.raises(InputError):
        parse_title(bad)


def test_bad_lessons():
    with pytest.raises(InputError):
        build_teacher("X", "bộ môn 1", -1)
    with pytest.raises(InputError):
        build_teacher("X", "bộ môn 1", "abc")
    assert build_teacher("X", "bộ môn 1", 23.0).max_lessons == 23


def test_duplicates_rejected():
    with pytest.raises(InputError):
        validate([build_teacher("A", "chủ nhiệm 1/1", 19), build_teacher("B", "chủ nhiệm 1/1 ts", 16)])
    with pytest.raises(InputError):
        validate([build_teacher("A", "chủ nhiệm 1/1", 19), build_teacher("B", "bộ môn 2", 23),
                  build_teacher("C", "bộ môn 2 ts", 19)])


def test_read_real_staff(real_staff):
    assert len(real_staff) == 45
    classes = classes_from_staff(real_staff)
    assert len(classes) == 29
    assert classes[0] == "1/1" and classes[-1] == "5/5"
    cn55 = next(t for t in real_staff if t.class_name == "5/5")
    assert cn55.maternity and cn55.max_lessons == 16
    bm5 = next(t for t in real_staff if t.title == "bộ môn 5 ts")
    assert bm5.max_lessons == 19


def test_program_file_matches_default():
    assert read_program(PROGRAM_FILE) == config.DEFAULT_CURRICULUM


def _staff_file(path, rows, header=("Tên", "Chức vụ", "Số tiết", "Thai sản")):
    wb = openpyxl.Workbook()
    wb.active.append(list(header))
    for r in rows:
        wb.active.append(list(r))
    wb.save(path)
    return path


def test_maternity_column(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [("A", "chủ nhiệm 1/1", 16, "Có"), ("B", "bộ môn 1", 23, None),
                                             ("C", "bộ môn 2 ts", 19, None), ("D", "bộ môn 3", 23, "không")])
    a, b, c, d = read_staff(path)
    assert (a.title, a.maternity) == ("chủ nhiệm 1/1 ts", True)
    assert (b.title, b.maternity) == ("bộ môn 1", False)
    assert (c.title, c.maternity) == ("bộ môn 2 ts", True)  # file cũ ghi "ts" sau chức vụ vẫn hiểu
    assert not d.maternity


def test_maternity_column_rejects_other_values(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [("A", "chủ nhiệm 1/1", 16, "đang nghỉ")])
    with pytest.raises(InputError, match="Thai sản"):
        read_staff(path)


V7 = ("Họ và Tên", "Chức Vụ", "Lớp", "Chế độ", "Số Tiết/Tuần")


def test_v7_columns_and_auto_numbering(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [
        ("A", "Chủ Nhiệm", "1/1", None, 19), ("B", "Bộ Môn", None, None, 23),
        ("C", "Tiếng Anh", None, None, 23), ("D", "bộ môn", None, "Thai sản", 19),
        ("E", "Chủ Nhiệm", " 1 / 2 ", "Thai sản", 16), ("F", "Bộ Môn", None, None, 23)], header=V7)
    got = [(t.name, t.title, t.max_lessons, t.maternity) for t in read_staff(path)]
    assert got == [("A", "chủ nhiệm 1/1", 19, False), ("B", "bộ môn 1", 23, False),
                   ("C", "tiếng anh 1", 23, False), ("D", "bộ môn 2 ts", 19, True),
                   ("E", "chủ nhiệm 1/2 ts", 16, True), ("F", "bộ môn 3", 23, False)]


@pytest.mark.parametrize("row, message", [
    (("A", "Chủ Nhiệm", None, None, 19), "phải ghi Lớp"),
    (("A", "Bộ Môn", "1/1", None, 23), "chỉ Chủ Nhiệm mới ghi Lớp"),
    (("A", "Chủ Nhiệm", "1-1", None, 19), "khối/số thứ tự"),
    (("A", "Hiệu Trưởng", None, None, 4), "không xác định"),
    (("A", "Chủ Nhiệm", "1/1", "nghỉ ốm", 19), "Chế độ"),
])
def test_v7_errors(tmp_path, row, message):
    path = _staff_file(tmp_path / "ns.xlsx", [row], header=V7)
    with pytest.raises(InputError, match=message):
        read_staff(path)


def test_v7_class_turned_into_date(tmp_path):
    import datetime
    path = _staff_file(tmp_path / "ns.xlsx", [("A", "Chủ Nhiệm", datetime.datetime(2026, 1, 1), None, 19)],
                       header=V7)
    with pytest.raises(InputError, match="ngày tháng"):
        read_staff(path)


def test_program_sheet_aliases_and_total_row(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "NHÂN SỰ"
    ws = wb.create_sheet("CHƯƠNG TRÌNH HỌC")
    ws.append(["SST", "Môn học", "Khối 1"])
    ws.append([1, "Tự Nhiên và Xã Hội", 2])
    ws.append([2, "Lịch Sử và Địa Lý", 0])
    ws.append([3, "Hoạt Động Trải Nghiệm", 3])
    ws.append([None, "Tổng", "=SUM(C2:C4)"])
    wb.save(tmp_path / "in.xlsx")
    assert read_program(tmp_path / "in.xlsx") == {1: {config.TNXH: 2, config.LSDL: 0, config.HDTN: 3}}
    ws.append([4, "Toán Nâng Cao", 1])
    wb.save(tmp_path / "in.xlsx")
    with pytest.raises(InputError, match="không xác định"):
        read_program(tmp_path / "in.xlsx")


def test_role_alias_and_all_errors_at_once(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [
        ("A", "Chủ Nhiệm", "1/1", None, 19), ("B", "T. Anh ", None, None, 23),
        ("C", "Chủ Nhiệm", "1/1", None, 19), ("D", "Chủ Nhiệm", "2/1", None, 19),
        ("E", "Chủ Nhiệm", "2/1", None, 19), ("F", "Hiệu Trưởng", None, None, 4)], header=V7)
    with pytest.raises(InputError) as exc:
        read_staff(path)
    message = str(exc.value)
    assert "3 lỗi" in message and "Lớp 1/1 có hai Chủ Nhiệm" in message and "Lớp 2/1" in message
    assert "Hiệu Trưởng" in message and "T. Anh" not in message  # "T. Anh" được hiểu là Tiếng Anh
