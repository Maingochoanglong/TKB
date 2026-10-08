"""Sheet LỚP (không bắt buộc): tên lớp, tên khối tùy ý, lớp không có GVCN (rules._Reader.classes, staff.grade_of,
staff.class_sort_key, allocation.build_problem). Không có sheet hoặc sheet trống: như trước (lớp của các dòng Chủ
Nhiệm)."""
import openpyxl
import pytest

from tkb import config, kich_ban
from tkb.__main__ import main
from tkb.allocation import build_problem
from tkb.program import read_program
from tkb.rules import applied, code, read_rules
from tkb.staff import (InputError, class_list, class_sort_key, grade_key, grade_of, parse_class, parse_grade,
                       read_saved_timetable, read_staff)
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff

# Khối Lá: ít tiết, không có HĐTN (môn chỉ GVCN dạy) vì lớp của khối này không có Chủ Nhiệm.
LA = {**{s: 0 for s in CURRICULUM[3]},
      "Tiếng Việt": 6, "Toán": 4, "Tiếng Anh": 2, "Thể dục": 2, "Âm nhạc": 2, "Mỹ thuật": 2}
BLANK = {k: "" for k in kich_ban.RULE_KEYS}


def _file(tmp_path, classes, la=LA, rules=()):
    """Trường nhỏ (2 lớp Khối 3 có Chủ Nhiệm) thêm khối Lá; sheet LỚP ghi `classes` [(lớp, khối, cơ sở 2)], thêm các
    dòng luật `rules`. Ghi qua kịch bản như giao diện."""
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), {3: CURRICULUM[3], "Lá": la})
    sc, _ = kich_ban.from_excel(path)
    sc["classes"] = [{"name": n, "grade": g, "campus2": c} for n, g, c in classes]
    sc["rules"] += [{**BLANK, **r} for r in rules]
    kich_ban.to_excel(sc, path)
    return path


def test_grade_names_and_order():
    assert [parse_grade(v) for v in (1, 2.0, "03", " Lá ", "Year 7")] == [1, 2, 3, "Lá", "Year 7"]
    grades = ["Lá", 10, "Year 10", 2, "Chồi", "Year 7", 1]
    assert sorted(grades, key=grade_key) == [1, 2, 10, "Chồi", "Lá", "Year 7", "Year 10"]
    # Không có sheet LỚP: thứ tự cũ (khối, phần chữ, số).
    old = ["2/1", "1D15", "1/10", "1D9", "1/2"]
    assert sorted(old, key=class_sort_key) == ["1/2", "1/10", "1D9", "1D15", "2/1"]
    school = (config.SchoolClass("Lá 10", "Lá"), config.SchoolClass("Chồi 1", "Chồi"), config.SchoolClass("Lá 2", "Lá"),
              config.SchoolClass("1A", 1))
    with applied({"CLASSES": school}):
        assert sorted(c.name for c in school) != sorted((c.name for c in school), key=class_sort_key)
        assert sorted((c.name for c in school), key=class_sort_key) == ["1A", "Chồi 1", "Lá 2", "Lá 10"]
        assert grade_of("Lá 10") == "Lá" and parse_class("lá  10") == "Lá 10"
        with pytest.raises(InputError, match="không có trong sheet LỚP"):
            parse_class("Lá 3")


def test_class_sheet_is_read(tmp_path):
    path = _file(tmp_path, [("3/1", 3, False), ("3 / 2", None, False), ("lá 1", "lá", True)])
    rules = read_rules(path)
    assert [(c.name, c.grade, c.campus2) for c in rules["CLASSES"]] == [("3/1", 3, False), ("3/2", 3, False),
                                                                         ("lá 1", "Lá", True)]
    with applied(rules):
        staff = read_staff(path)
        assert class_list(staff) == ["3/1", "3/2", "lá 1"] and grade_of("lá 1") == "Lá"
        problem = build_problem(staff, read_program(path))
        assert problem.no_homeroom == {"lá 1"} and problem.campus2 == {"lá 1"}
        assert not problem.homeroom_take.get("lá 1")
        assert {c.subject for c in problem.class_courses("lá 1")} == {s for s, n in LA.items() if n}


def test_class_sheet_errors(tmp_path):
    path = _file(tmp_path, [("3/1", 3, False), ("3/1", 3, False), ("Lá 1", None, False), ("Lá 2", "Mầm", False),
                            ("3/2", 3, False)])
    with pytest.raises(InputError) as err:
        read_rules(path)
    text = str(err.value)
    assert "LỚP, dòng 3: lớp '3/1' đã ghi ở dòng 2" in text
    assert "LỚP, dòng 4: lớp 'Lá 1' chưa ghi Khối" in text
    assert "LỚP, dòng 5: lớp 'Lá 2': không có cột Khối Mầm ở sheet CHƯƠNG TRÌNH HỌC" in text
    # Chủ Nhiệm ghi lớp không có trong sheet LỚP.
    path = _file(tmp_path, [("3/1", 3, False), ("Lá 1", "Lá", False)])
    with applied(read_rules(path)), pytest.raises(InputError, match="lớp '3/2' không có trong sheet LỚP"):
        read_staff(path)


def test_homeroom_only_subject_needs_a_homeroom_teacher(tmp_path):
    path = _file(tmp_path, [("3/1", 3, False), ("3/2", 3, False), ("Lá 1", "Lá", False)],
                 la={**LA, config.HDTN: 1})
    with applied(read_rules(path)), pytest.raises(InputError, match="Lớp Lá 1 không có Chủ Nhiệm nên không ai dạy được "
                                                                     "môn Hoạt động trải nghiệm"):
        build_problem(read_staff(path), read_program(path))


def test_empty_or_same_class_sheet_keeps_the_timetable(tmp_path, capsys):
    """Sheet LỚP trống: như không có (cùng mã quy định); ghi đúng các lớp của Chủ Nhiệm: cùng TKB."""
    path = tmp_path / "trong.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    with applied(None):
        default = code()
    with applied(read_rules(path)):
        assert config.CLASSES == () and code() == default
    same = tmp_path / "cung.xlsx"
    sc, _ = kich_ban.from_excel(path)
    sc["classes"] = [{"name": "3/2", "grade": 3, "campus2": False}, {"name": "3/1", "grade": None, "campus2": False}]
    kich_ban.to_excel(sc, same)
    codes = []
    for p in (path, same):
        assert main([str(p), "-o", str(tmp_path / p.stem / "TKB.xlsx"), "--time-limit", "10", "--workers", "4"]) == 0
        codes.append(next(line.split()[3] for line in capsys.readouterr().out.splitlines()
                          if line.startswith("Mã kết quả")))
    assert codes[0] == codes[1]


def test_class_without_homeroom_end_to_end(tmp_path, capsys):
    """Lớp "lá 1" khối Lá không có Chủ Nhiệm, ở cơ sở 2: mọi môn do GV khác dạy (cả tiết 1), luật theo tên khối và tên
    lớp (ghi khác hoa thường) vẫn áp dụng; nạp lại file cập nhật thì giữ TKB."""
    path = _file(tmp_path, [("3/1", 3, False), ("3/2", 3, False), ("lá 1", "lá", True)],
                 rules=[{"kind": "Không xếp vào", "subject": "Toán", "grades": "LÁ", "days": "Thứ 2", "hard": True},
                        {"kind": "Không xếp vào", "subject": "Tiếng Anh", "classes": "Lá 1", "days": "Thứ 6",
                         "hard": True}])
    argv = [str(path), "-o", str(tmp_path / "TKB.xlsx"), "--time-limit", "10", "--workers", "4"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "kiểm tra luật bắt buộc: ĐẠT" in out and "Đọc 8 nhân sự, 3 lớp" in out
    with applied(read_rules(path)):
        saved = read_saved_timetable(tmp_path / "vao_cap_nhat.xlsx")
    la = [row for row in saved.rows if row[0] == "lá 1"]
    assert len(la) == sum(LA.values()) and not [r for r in la if r[4].startswith("Chủ Nhiệm")]
    assert not [r for r in la if r[3] == "Toán" and r[1] == "Thứ 2"]
    assert not [r for r in la if r[3] == "Tiếng Anh" and r[1] == "Thứ 6"]
    assert openpyxl.load_workbook(tmp_path / "TKB_diem_phu.xlsx").sheetnames == ["Khối Lá"]
    argv[0] = str(tmp_path / "vao_cap_nhat.xlsx")
    assert main(argv) == 0
    assert "Dùng lại TKB đã xếp" in capsys.readouterr().out


def test_scenario_keeps_classes_and_grade_names(tmp_path):
    path = _file(tmp_path, [("3/1", 3, False), ("", None, False), ("lá 1", "Lá", True)])
    sc, _ = kich_ban.from_excel(path)
    assert sc["grades"] == [3, "Lá"] and sc["subjects"][0]["lessons"] == {"3": 7, "Lá": 6}
    assert sc["classes"] == [{"name": "3/1", "grade": 3, "campus2": False}, {"name": "", "grade": None, "campus2": False},
                             {"name": "lá 1", "grade": "Lá", "campus2": True}]
    again = tmp_path / "lai.xlsx"
    kich_ban.to_excel(sc, again)
    assert kich_ban.from_excel(again)[0] == sc
    # Lỗi của sheet LỚP chỉ đúng dòng (dòng trống giữa bảng giữ chỗ): lớp 3/2 của Chủ Nhiệm chưa có trong sheet.
    res = kich_ban.check(sc, quick=True)
    assert any(text.startswith("NHÂN SỰ") and "lớp '3/2' không có trong sheet LỚP" in text for text in res["errors"])
