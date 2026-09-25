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
