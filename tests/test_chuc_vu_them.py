"""Cột Chức Vụ Thêm (không bắt buộc): một người giữ nhiều chức vụ, quyền dạy là hợp các chức vụ (staff.parse_extra_roles,
allocation.may_teach, phan_cong._homeroom_only, checker). Chủ Nhiệm ghi Bộ Môn ở cột này thì dạy được cả lớp khác:
đó là cách bỏ "GVCN chỉ dạy lớp mình" cho từng người. Không ghi cột này: như trước (cùng mã kết quả,
tests/test_reproducible.py)."""
import dataclasses

import pytest

from tkb import bo_mau, config, kich_ban
from tkb.__main__ import main
from tkb.allocation import build_problem, subject_group
from tkb.checker import check
from tkb.program import read_program
from tkb.rules import applied, read_rules
from tkb.solver import saved_lessons
from tkb.staff import InputError, parse_extra_roles, read_saved_timetable, read_staff
from tkb.template import write_staff_template

from .conftest import CURRICULUM, small_staff

CLASSES = ("3/1", "3/2")
CN = tuple(f"{config.ROLE_HOMEROOM} {c}" for c in CLASSES)


def _school(tmp_path, extra, quota, drop=(), name="vao", only=None):
    """Trường nhỏ, Chủ Nhiệm (cả hai, hay chỉ lớp `only`) có chức vụ thêm `extra` và định mức `quota`; bỏ các GV có
    chức vụ trong `drop`."""
    staff = [dataclasses.replace(t, extra_roles=extra, max_lessons=quota) if t.class_name in (only or CLASSES) else t
             for t in small_staff() if t.role not in drop]
    path = tmp_path / f"{name}.xlsx"
    write_staff_template(path, staff, CURRICULUM)
    return path


def _run(path, capsys, mode, out="out"):
    argv = [str(path), "-o", str(path.parent / out / "TKB.xlsx"), "--time-limit", "10", "--workers", "4",
            "--mode", mode, "--max-overtime", "4"]
    code = main(argv)
    return code, capsys.readouterr().out


def test_parse_extra_roles():
    assert parse_extra_roles(None, config.ROLE_HOMEROOM) == ()
    assert parse_extra_roles(" Tiếng  Anh; Bộ Môn, tiếng anh,", config.ROLE_HOMEROOM) == ("tiếng anh", "bộ môn")
    assert parse_extra_roles("Tin học + Tiếng Anh", "tiếng anh") == ("tin học",)  # bỏ chức vụ chính
    for bad, msg in (("Chủ Nhiệm", "chỉ là chức vụ chính"), ("Tiếng Anh 2", "không ghi số thứ tự")):
        with pytest.raises(InputError, match=msg):
            parse_extra_roles(bad, config.ROLE_GENERAL)
    with pytest.raises(InputError, match="Quản Lý dạy đúng số tiết"):
        parse_extra_roles("Bộ Môn", config.ROLE_MANAGER)


def test_unknown_extra_role(tmp_path):
    path = _school(tmp_path, ("hóa học",), 19)
    with applied(read_rules(path)), pytest.raises(InputError, match="chức vụ 'hóa học' không xác định"):
        read_staff(path, subjects=read_program(path)[3])


def test_homeroom_with_general_role_teaches_other_classes(tmp_path):
    """Không có GV bộ môn; hai Chủ Nhiệm ghi Bộ Môn: dạy được các môn bộ môn được dạy ở cả lớp kia. GVCN có chức vụ
    thêm chỉ nhận trọn các môn ưu tiên (và môn cùng nhóm), không nhận thêm cho đủ định mức."""
    path = _school(tmp_path, (config.ROLE_GENERAL,), 23, drop=(config.ROLE_GENERAL,))
    with applied(read_rules(path)):
        problem = build_problem(read_staff(path), read_program(path))
        for c in problem.courses:
            if c.homeroom:
                continue
            if c.subject in config.GENERAL_FORBIDDEN_SUBJECTS:
                assert not set(CN) & set(c.teachers), c
            else:
                assert set(CN) <= set(c.teachers), c
        held = {subject_group(s) for s in config.HOMEROOM_PRIORITY}
        for take in problem.homeroom_take.values():
            assert {subject_group(s) for s in take} <= held and bo_mau.TNXH not in take


@pytest.mark.parametrize("mode", ["tuyen_them", "bu_gio"])
def test_homeroom_teacher_also_teaches_english(tmp_path, capsys, mode):
    """Không có GV Tiếng Anh; Chủ Nhiệm 3/1 ghi Tiếng Anh ở cột Chức Vụ Thêm, định mức 27 (phần GVCN 19 + 8): dạy Tiếng
    Anh cả hai lớp trong định mức, không bù, không tuyển; nạp lại file cập nhật thì giữ TKB. Bỏ chức vụ thêm thì
    checker báo GVCN dạy lớp khác."""
    path = _school(tmp_path, ("tiếng anh",), 27, drop=("tiếng anh",), only=("3/1",))
    code, out = _run(path, capsys, mode)
    assert code == 0 and "kiểm tra luật bắt buộc: ĐẠT" in out and "Bù: 0/" in out
    assert "Cần bổ sung" not in out
    updated = tmp_path / "out" / "vao_cap_nhat.xlsx"
    with applied(read_rules(updated)):
        rows = read_saved_timetable(updated).rows
        english = [r for r in rows if r[3] == bo_mau.TIENG_ANH]
        assert {(r[0], r[4]) for r in english} == {("3/1", "Chủ Nhiệm 3/1"), ("3/2", "Chủ Nhiệm 3/1")}
        for extra, ok in ((("tiếng anh",), True), ((), False)):
            staff = [dataclasses.replace(t, extra_roles=extra) if t.class_name == "3/1" else t
                     for t in read_staff(updated)]
            problem = build_problem(staff, read_program(updated), overtime_max=4 if mode == "bu_gio" else 0)
            lessons, errors = saved_lessons(problem, rows)
            errors += check(problem, lessons)
            assert not errors if ok else any("không phải GVCN lớp này" in e for e in errors), errors
    code, out = _run(updated, capsys, mode, out="lai")
    assert code == 0 and "Dùng lại TKB đã xếp" in out


@pytest.mark.parametrize("mode, want", [("bu_gio", "Bù: 8/12 tiết (GVCN 8/8"),
                                        ("tuyen_them", "Cần tuyển: Tiếng Anh x2")])
def test_extra_role_beyond_quota(tmp_path, capsys, mode, want):
    """Định mức 19 đã hết cho phần GVCN: Tiếng Anh là tiết bù của Chủ Nhiệm (bù giờ), hay người mới dạy Tiếng Anh
    (tuyển thêm)."""
    path = _school(tmp_path, ("tiếng anh",), 19, drop=("tiếng anh",))
    code, out = _run(path, capsys, mode)
    assert code == 0 and "kiểm tra luật bắt buộc: ĐẠT" in out and want in out
    assert "Dự toán: cần 64 tiết = GVCN 38 + GV chuyên biệt 10 + quản lý 0 + bộ môn 8" in out


def test_scenario_keeps_extra_roles(tmp_path):
    """Kịch bản giao diện: cột Chức Vụ Thêm đọc đúng chữ, chức vụ trùng tên môn chỉ có ở cột này vẫn thành chức vụ
    của bước Chức vụ; ghi lại ra Excel giữ nguyên, kiểm tra nhanh không lỗi."""
    path = _school(tmp_path, ("tiếng anh",), 23, drop=("tiếng anh",))
    sc, _ = kich_ban.from_excel(path)
    assert [t["extra_roles"] for t in sc["staff"][:2]] == ["Tiếng Anh", "Tiếng Anh"]
    assert {"name": "Tiếng Anh", "subjects": [bo_mau.TIENG_ANH]} in sc["roles"]
    again = tmp_path / "lai.xlsx"
    kich_ban.to_excel(sc, again)
    assert kich_ban.from_excel(again)[0] == sc
    assert not kich_ban.check(sc, quick=True)["errors"]
