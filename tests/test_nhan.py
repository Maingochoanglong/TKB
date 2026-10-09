"""Cột Nhãn (không bắt buộc) của sheet NHÂN SỰ và sheet LỚP: nhãn tự đặt; cột Giáo viên, cột Lớp của sheet LUẬT ghi một
nhãn là mọi GV (lớp) có nhãn đó (staff.parse_tags, Teacher.tag_keys, staff.class_tags, bo_ghep.picks, bo_ghep._classes).
Các cột Thai Sản, Hợp Đồng, Cơ sở 2 ghi Có cũng là nhãn cùng tên. Không ghi nhãn: như trước (cùng mã quy định, cùng mã
kết quả)."""
import dataclasses

import pytest

from tkb import bo_mau, config, kich_ban
from tkb.__main__ import main
from tkb.rules import applied, code, read_rules
from tkb.staff import InputError, class_tags, parse_tags, read_saved_timetable, read_staff
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff

BLANK = {k: "" for k in kich_ban.RULE_KEYS}


def _file(tmp_path, staff=None, classes=(), rules=(), name="vao"):
    """Trường nhỏ (sửa nhân sự bằng `staff`: Mã GV -> các trường của Teacher), sheet LỚP ghi `classes` [(lớp, khối,
    cơ sở 2, nhãn)], thêm các dòng luật `rules`. Ghi qua kịch bản như giao diện."""
    people = [dataclasses.replace(t, **(staff or {}).get(t.title, {})) for t in small_staff()]
    path = tmp_path / f"{name}.xlsx"
    write_staff_template(path, people, CURRICULUM)
    sc, _ = kich_ban.from_excel(path)
    sc["classes"] = [{"name": n, "grade": g, "campus2": c, "tags": t} for n, g, c, t in classes]
    sc["rules"] += [{**BLANK, "hard": True, **r} for r in rules]
    kich_ban.to_excel(sc, path)
    return path


def test_parse_tags_and_tag_keys():
    assert parse_tags(None) == () and parse_tags(" Tổ  Toán; bán thời gian, tổ toán,") == ("Tổ Toán", "bán thời gian")
    t = next(t for t in small_staff() if t.title == "bộ môn 1")
    assert dataclasses.replace(t, tags=("Tổ Toán",), contract=True).tag_keys == {"tổ toán", "hợp đồng"}
    cn = next(t for t in small_staff() if t.class_name == "3/1")
    with applied({"CLASSES": (config.SchoolClass("3/1", 3, True, 2, ("Song ngữ",)), config.SchoolClass("3/2", 3))}):
        assert cn.tag_keys == {"cơ sở 2"}  # lớp ở cơ sở 2 theo sheet LỚP
        assert class_tags() == {"song ngu": ("3/1",), "co so 2": ("3/1",)}


def test_rules_by_staff_and_class_tags(tmp_path, capsys):
    """GV Tiếng Anh có nhãn Bán thời gian: luật "Bán thời gian không dạy buổi chiều"; GV bộ môn Hợp Đồng: luật "Hợp Đồng
    không dạy Thứ 2"; lớp 3/1 có nhãn Song ngữ: luật "Tiếng Anh lớp Song ngữ không xếp Thứ 6". Xếp đạt mọi luật."""
    path = _file(tmp_path, staff={"tiếng anh 1": {"tags": ("Bán thời gian",)}, "bộ môn 1": {"contract": True}},
                 classes=[("3/1", 3, False, "Song ngữ"), ("3/2", 3, False, "")],
                 rules=[{"kind": "Không xếp vào", "role": "Bán Thời Gian", "sessions": "Chiều"},
                        {"kind": "Không xếp vào", "role": "Hợp Đồng", "days": "Thứ 2"},
                        {"kind": "Không xếp vào", "subject": bo_mau.TIENG_ANH, "classes": "song ngữ",
                         "days": "Thứ 6"}])
    argv = [str(path), "-o", str(tmp_path / "TKB.xlsx"), "--time-limit", "10", "--workers", "4"]
    assert main(argv) == 0
    assert "kiểm tra luật bắt buộc: ĐẠT" in capsys.readouterr().out
    with applied(read_rules(path)):
        rows = read_saved_timetable(tmp_path / "vao_cap_nhat.xlsx").rows
    english = [r for r in rows if r[4] == "Tiếng Anh 1"]
    assert english and not [r for r in english if r[2] >= 5]  # tiết 5–7 là buổi chiều
    general = [r for r in rows if r[4] == "Bộ Môn 1"]
    assert general and not [r for r in general if r[1] == "Thứ 2"]
    assert not [r for r in rows if r[0] == "3/1" and r[3] == bo_mau.TIENG_ANH and r[1] == "Thứ 6"]
    # Câu đọc lại ghi nhãn như tên chức vụ.
    sc, _ = kich_ban.from_excel(path)
    said = kich_ban.describe(sc, [sc["rules"][-3]])["rules"][0]["text"]
    assert said.startswith("GV Bán Thời Gian không dạy") and "buổi chiều" in said


def test_tag_errors(tmp_path):
    path = _file(tmp_path, rules=[{"kind": "Không xếp vào", "role": "Bán thời gian", "sessions": "Chiều"},
                                  {"kind": "Không xếp vào", "subject": bo_mau.TOAN, "classes": "Song ngữ",
                                   "days": "Thứ 2"}],
                 classes=[("3/1", 3, False, ""), ("3/2", 3, False, "3/1, Song")])
    with pytest.raises(InputError, match="LỚP, dòng 3: nhãn '3/1' trùng tên lớp ở dòng 2"):
        read_rules(path)
    path = _file(tmp_path, rules=[{"kind": "Không xếp vào", "role": "Bán thời gian", "sessions": "Chiều"},
                                  {"kind": "Không xếp vào", "subject": bo_mau.TOAN, "classes": "Song ngữ",
                                   "days": "Thứ 2"}],
                 classes=[("3/1", 3, False, ""), ("3/2", 3, False, "Song")], name="lai")
    sc, _ = kich_ban.from_excel(path)
    errors = kich_ban.check(sc, quick=True)["errors"]
    assert any("không có giáo viên nào có chức vụ, nhãn, Mã GV hay họ tên 'Bán Thời Gian'" in e for e in errors), errors
    assert any("không có lớp 'Song ngữ' (cũng không có nhãn lớp nào tên đó ở sheet LỚP)" in e for e in errors), errors


def test_class_tags_in_rules_code(tmp_path):
    """Nhãn lớp vào mã quy định (luật dùng chúng); sheet LỚP không ghi nhãn: mã như trước."""
    plain = _file(tmp_path, classes=[("3/1", 3, False, ""), ("3/2", 3, False, "")])
    tagged = _file(tmp_path, classes=[("3/1", 3, False, "Song ngữ"), ("3/2", 3, False, "")], name="nhan")
    codes = []
    for path in (plain, tagged):
        with applied(read_rules(path)):
            codes.append(code())
            staff = read_staff(path)
    assert codes[0] != codes[1]
    with applied(None):
        default = code()
    with applied({"CLASSES": (config.SchoolClass("3/1", 3), config.SchoolClass("3/2", 3))}):
        with_sheet = code()
    with applied(read_rules(plain)):
        assert code() == with_sheet != default
    assert [t.tags for t in staff] == [()] * len(staff)
