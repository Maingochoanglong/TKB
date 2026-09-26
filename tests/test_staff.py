import openpyxl
import pytest

from tkb import config
from tkb.program import canonical_subject, load_curriculum, read_program, subject_key
from tkb.staff import InputError, build_teacher, classes_from_staff, parse_title, read_staff, validate

from .conftest import CURRICULUM


def test_parse_titles():
    assert parse_title("chủ nhiệm 1/1") == ("chủ nhiệm", None, "1/1")
    assert parse_title("  Chủ  nhiệm 5 / 5 ") == ("chủ nhiệm", None, "5/5")
    assert parse_title("bộ môn 5") == ("bộ môn", 5, None)
    assert parse_title("Tiếng Anh 3") == ("tiếng anh", 3, None)
    assert parse_title("quản lý 1") == ("quản lý", 1, None)


@pytest.mark.parametrize("bad", ["bộ môn", "chủ nhiệm 1", "bộ môn 1/2", "thể dục một", "bộ môn 5 ts"])
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
        validate([build_teacher("A", "chủ nhiệm 1/1", 19), build_teacher("B", "Chủ nhiệm 1 / 1", 16)])
    with pytest.raises(InputError):
        validate([build_teacher("A", "chủ nhiệm 1/1", 19), build_teacher("B", "bộ môn 2", 23),
                  build_teacher("C", "Bộ Môn 2", 19)])


def test_read_sample_staff(sample_staff):
    assert len(sample_staff) == 45
    classes = classes_from_staff(sample_staff)
    assert len(classes) == 29
    assert classes[0] == "1/1" and classes[-1] == "5/5"
    cn55 = next(t for t in sample_staff if t.class_name == "5/5")
    assert cn55.title == "chủ nhiệm 5/5" and cn55.max_lessons == 16
    bm5 = next(t for t in sample_staff if t.title == "bộ môn 5")
    assert bm5.max_lessons == 19


def test_program_file_is_read_as_written():
    assert list(CURRICULUM) == [1, 2, 3, 4, 5]
    assert CURRICULUM[1]["Tiếng Việt"] == 14 and CURRICULUM[3]["Tin học"] == 1
    assert all(sum(req.values()) == 32 for req in CURRICULUM.values())


def test_subject_names_match_rules_loosely():
    assert subject_key("Lịch Sử và Địa Lý") == subject_key("Lịch sử - Địa lý") == "lịch sử địa lý"
    assert canonical_subject(" Tự Nhiên và Xã Hội ") == config.TNXH
    assert canonical_subject("HĐTN") == config.HDTN
    assert canonical_subject("Toán  Tăng Cường") == config.TOAN_TC
    assert canonical_subject("Múa  dân gian") == "Múa dân gian"  # môn không có luật: giữ tên trong file


def _staff_file(path, rows, header=("Tên", "Chức vụ", "Số tiết", "Chế Độ")):
    wb = openpyxl.Workbook()
    wb.active.append(list(header))
    for r in rows:
        wb.active.append(list(r))
    wb.save(path)
    return path


def test_extra_columns_are_ignored(tmp_path):
    # File cũ còn cột Chế Độ (thai sản) hay cột ghi chú: chương trình bỏ qua, ghi gì cũng được.
    path = _staff_file(tmp_path / "ns.xlsx", [("A", "chủ nhiệm 1/1", 16, "Có"), ("B", "bộ môn 1", 23, None),
                                             ("C", "bộ môn 2", 19, "đang nghỉ")])
    got = [(t.name, t.title, t.max_lessons) for t in read_staff(path)]
    assert got == [("A", "chủ nhiệm 1/1", 16), ("B", "bộ môn 1", 23), ("C", "bộ môn 2", 19)]


V7 = ("Họ và Tên", "Chức Vụ", "Lớp", "Chế độ", "Số Tiết/Tuần")


def test_v7_columns_and_auto_numbering(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [
        ("A", "Chủ Nhiệm", "1/1", None, 19), ("B", "Bộ Môn", None, None, 23),
        ("C", "Tiếng Anh", None, None, 23), ("D", "bộ môn", None, "Thai sản", 19),
        ("E", "Chủ Nhiệm", " 1 / 2 ", "Thai sản", 16), ("F", "Bộ Môn", None, None, 23)], header=V7)
    got = [(t.name, t.title, t.max_lessons) for t in read_staff(path)]
    assert got == [("A", "chủ nhiệm 1/1", 19), ("B", "bộ môn 1", 23), ("C", "tiếng anh 1", 23),
                   ("D", "bộ môn 2", 19), ("E", "chủ nhiệm 1/2", 16), ("F", "bộ môn 3", 23)]


@pytest.mark.parametrize("row, message", [
    (("A", "Chủ Nhiệm", None, None, 19), "phải ghi Lớp"),
    (("A", "Bộ Môn", "1/1", None, 23), "chỉ Chủ Nhiệm mới ghi Lớp"),
    (("A", "Chủ Nhiệm", "1-1", None, 19), "khối/số thứ tự"),
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
    ws.append([4, "Toán Nâng Cao", 1])  # môn lạ vẫn nhận
    wb.save(tmp_path / "in.xlsx")
    assert read_program(tmp_path / "in.xlsx") == {
        1: {"Tự Nhiên và Xã Hội": 2, "Lịch Sử và Địa Lý": 0, "Hoạt Động Trải Nghiệm": 3, "Toán Nâng Cao": 1}}
    ws.append([5, "Lịch sử - Địa lý", 1])  # cùng môn, khác cách viết
    wb.save(tmp_path / "in.xlsx")
    with pytest.raises(InputError, match="bị lặp với dòng 3"):
        read_program(tmp_path / "in.xlsx")


def test_missing_program_sheet_is_an_error(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [("A", "chủ nhiệm 1/1", 19, None)])
    with pytest.raises(InputError, match="thiếu sheet CHƯƠNG TRÌNH HỌC"):
        load_curriculum(path)


def test_all_errors_at_once(tmp_path):
    path = _staff_file(tmp_path / "ns.xlsx", [
        ("A", "Chủ Nhiệm", "1/1", None, 19), ("B", "T. Anh ", None, None, 23),
        ("C", "Chủ Nhiệm", "1/1", None, 19), ("D", "Chủ Nhiệm", "2/1", None, 19),
        ("E", "Chủ Nhiệm", "2/1", None, 19), ("F", "Hiệu Trưởng", None, None, 4)], header=V7)
    with pytest.raises(InputError) as exc:
        read_staff(path, subjects=["Tiếng Việt", "Tiếng Anh"])
    message = str(exc.value)
    assert "4 lỗi" in message and "Lớp 1/1 có hai Chủ Nhiệm" in message and "Lớp 2/1" in message
    # Chức vụ phải là Chủ Nhiệm/Bộ Môn/Quản Lý hoặc đúng tên một môn trong chương trình học.
    assert "Dòng 3: chức vụ 'T. Anh' không xác định" in message and "'Hiệu Trưởng'" in message
    ok = _staff_file(tmp_path / "ok.xlsx", [("A", "Chủ Nhiệm", "1/1", None, 19),
                                            ("B", "Tiếng Anh ", None, None, 23)], header=V7)
    b = read_staff(ok, subjects=["Tiếng Việt", "Tiếng Anh"])[1]
    assert (b.title, b.label) == ("tiếng anh 1", "Tiếng Anh")
