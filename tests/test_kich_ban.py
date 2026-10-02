"""Kịch bản của giao diện (tkb/kich_ban.py): file Excel -> kịch bản -> file Excel không mất gì, và kiểm tra báo lỗi
như khi chạy."""
import datetime
import json

import openpyxl

from tkb import config, kich_ban
from tkb.program import read_program
from tkb.rules import DEFAULTS, SUBJECT_COLS, applied, code, read_rules
from tkb.staff import read_saved_timetable, read_staff
from tkb.template import write_staff_template

from .conftest import CURRICULUM, INPUT_FILE, small_staff


DEFAULT_CODE = code()


def _values(path):
    return {ws.title: [r for r in ws.iter_rows(values_only=True) if any(v is not None for v in r)]
            for ws in openpyxl.load_workbook(path).worksheets}


def _key(teachers):
    return [(t.name, t.title, t.max_lessons, t.class_name) for t in teachers]


def test_round_trip_keeps_the_file(tmp_path):
    scenario, warnings = kich_ban.from_excel(INPUT_FILE)
    assert warnings == []
    json.dumps(scenario)  # gửi được cho trang web
    assert len(scenario["staff"]) == 45 and scenario["grades"] == [1, 2, 3, 4, 5]
    assert scenario["staff"][0] == {"name": "Giáo viên CN 1", "role": "Chủ Nhiệm", "class": "1/1", "lessons": 19,
                                    "maternity": False, "contract": False, "campus2": False, "history": "", "off": ""}
    # Chức vụ trùng tên môn nhân sự đang dùng thành các dòng của sheet CHỨC VỤ (để giao diện chọn từ danh sách).
    assert [(r["name"], r["subjects"]) for r in scenario["roles"]] == [
        ("Tiếng Anh", ["Tiếng Anh"]), ("Thể Dục", ["Thể dục"]), ("Âm Nhạc", ["Âm nhạc"]), ("Mỹ Thuật", ["Mỹ thuật"]),
        ("Tin Học", ["Tin học"])]
    out = tmp_path / "ra.xlsx"
    kich_ban.to_excel(scenario, out)
    written, source = _values(out), _values(INPUT_FILE)
    assert written.pop("CHỨC VỤ")[1:] == [(r["name"], r["subjects"][0]) for r in scenario["roles"]]
    assert source.pop("CHỨC VỤ") == [("Chức vụ", "Môn được dạy")]
    assert written == source  # các sheet khác ghi lại đúng từng ô
    rules = read_rules(out)
    assert read_program(out) == CURRICULUM and {**rules, "CUSTOM_ROLES": []} == DEFAULTS
    with applied(rules):  # các dòng đó như không ghi: mã quy định không đổi
        assert code() == DEFAULT_CODE
    assert _key(read_staff(out)) == _key(read_staff(INPUT_FILE))


def test_new_scenario_is_the_blank_template(tmp_path):
    write_staff_template(tmp_path / "mau.xlsx")
    kich_ban.to_excel(kich_ban.default_scenario(), tmp_path / "moi.xlsx")
    assert _values(tmp_path / "moi.xlsx") == _values(tmp_path / "mau.xlsx")


def test_schema_follows_rules_columns():
    s = kich_ban.schema()
    assert [c["key"] for c in s["subject"]] == [c.key for c in SUBJECT_COLS]
    assert [c["header"] for c in s["staff"]][:4] == ["Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần"]
    assert s["days"][0] == "Thứ 2" and s["days"][-1] == "Thứ 7"
    keys = {c.key for c in SUBJECT_COLS}  # nhóm cột của trang chi tiết môn, cột theo chức vụ: đúng khóa của rules.py
    assert all(k in keys for g in s["subject_groups"] for k in g["keys"])
    assert set(s["role_rules"].values()) <= keys and s["sheets"]["roles"] == "CHỨC VỤ"


def test_rules_edited_in_the_scenario_reach_the_file(tmp_path):
    scenario, _ = kich_ban.from_excel(INPUT_FILE)
    scenario["general"]["SESSION_GROUP_LIMIT"] = 3
    scenario["days"][5]["morning_days"] = True  # học sáng Thứ 7
    english = next(s for s in scenario["subjects"] if s["name"] == "Tiếng Anh")
    english["rules"]["MORNING_SUBJECTS"] = True
    english["rules"]["DISPLAY_NAMES"] = "TA"
    out = tmp_path / "ra.xlsx"
    kich_ban.to_excel(scenario, out)
    rules = read_rules(out)
    assert rules["SESSION_GROUP_LIMIT"] == 3
    assert rules["DAYS"][-1] == "Thứ 7" and len(rules["DAY_SESSIONS"]) == 6
    assert config.TIENG_ANH in rules["MORNING_SUBJECTS"] and rules["DISPLAY_NAMES"][config.TIENG_ANH] == "TA"


def test_check_reads_back_like_a_run():
    scenario, _ = kich_ban.from_excel(INPUT_FILE)
    ok = kich_ban.check(scenario, config.MODE_OVERTIME, 2)
    assert ok["errors"] == [] and any(line.startswith("Dự toán:") for line in ok["info"])
    scenario["staff"][20]["class"] = "1/1"  # hai Chủ Nhiệm lớp 1/1
    scenario["subjects"][0]["lessons"]["1"] = "mười"
    res = kich_ban.check(scenario, config.MODE_OVERTIME, 2)
    assert "NHÂN SỰ: Lớp 1/1 có hai Chủ Nhiệm (dòng 2 và 22)" in res["errors"]
    assert "CHƯƠNG TRÌNH HỌC: Dòng 2, Khối 1: số tiết không hợp lệ 'mười'" in res["errors"]


def test_check_estimates_shortage(tmp_path):
    """Trường nhỏ không có bộ môn: bù +1 vẫn thiếu tiết (như khi chạy, chế độ bù giờ sẽ báo lỗi mã 3); không ai
    được bù thì có môn không ai dạy được (chạy cũng báo lỗi đó)."""
    write_staff_template(tmp_path / "vao.xlsx", small_staff(general=False), CURRICULUM)
    scenario, _ = kich_ban.from_excel(tmp_path / "vao.xlsx")
    res = kich_ban.check(scenario, config.MODE_OVERTIME, 1)
    assert res["errors"] == []
    assert any("chế độ bù giờ sẽ báo lỗi" in line for line in res["info"])
    assert any(line.startswith("Lớp 3/1: TNXH thiếu 2 tiết") for line in res["info"])
    res = kich_ban.check(scenario, config.MODE_HIRE, 1)
    assert any("chế độ tuyển thêm sẽ thêm người" in line for line in res["info"])
    assert kich_ban.check(scenario, config.MODE_OVERTIME, 0)["errors"] == [
        "Lớp 3/1: không có GV nào được phép dạy môn Công nghệ"]


def test_blank_staff_rows_keep_row_numbers(tmp_path):
    scenario, _ = kich_ban.from_excel(INPUT_FILE)
    scenario["staff"].insert(0, {"name": "", "role": "", "class": "", "lessons": None})
    kich_ban.to_excel(scenario, tmp_path / "ra.xlsx")
    assert [t.row for t in read_staff(tmp_path / "ra.xlsx")][:2] == [3, 4]  # dòng i của bảng là dòng i + 2


def test_excel_date_in_class_column_is_read_back_with_a_warning(tmp_path):
    path = tmp_path / "vao.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    wb = openpyxl.load_workbook(path)
    wb["NHÂN SỰ"]["C2"] = datetime.datetime(2025, 1, 3)  # Excel đổi "3/1" thành ngày 3 tháng 1
    wb.save(path)
    scenario, warnings = kich_ban.from_excel(path)
    assert scenario["staff"][0]["class"] == "3/1" and "ngày tháng" in warnings[0]


def test_saved_timetable_sheet_is_kept(tmp_path):
    path = tmp_path / "vao_cap_nhat.xlsx"
    write_staff_template(path, small_staff(), CURRICULUM)
    wb = openpyxl.load_workbook(path)
    ws = wb.create_sheet(config.SAVED_SHEET)
    ws.append(["Mã kết quả", "AAAA-BBBB-CCCC", "Mã quy định", "123456789ABC"])
    ws.append([])
    ws.append(["Lớp", "Tiết", "Thứ 2"])
    ws.append(["3/1", 1, "HĐTN\nChủ Nhiệm 3/1"])
    ws.append([None, 2, "Tiếng Việt\nBộ Môn 1 (bù)"])
    wb.save(path)
    scenario, _ = kich_ban.from_excel(path)
    assert scenario["saved"][0] == ["Mã kết quả", "AAAA-BBBB-CCCC", "Mã quy định", "123456789ABC"]
    kich_ban.to_excel(scenario, tmp_path / "ra.xlsx")
    assert read_saved_timetable(tmp_path / "ra.xlsx") == read_saved_timetable(path)


def test_check_finds_rules_in_conflict():
    scenario, _ = kich_ban.from_excel(INPUT_FILE)
    scenario["general"]["SESSION_GROUP_LIMIT"] = 1
    res = kich_ban.check(scenario, config.MODE_OVERTIME, 2)
    assert res["errors"][0].startswith("Quy định mâu thuẫn, không có TKB nào thỏa: Khối 1: Tiếng Việt có 14 tiết/tuần")
    assert res["info"] == [] or not any(line.startswith("Dự toán:") for line in res["info"])
    assert kich_ban.check(scenario, config.MODE_OVERTIME, 2, student_rules=False)["errors"] == []


def test_custom_rules_round_trip(tmp_path):
    from tkb.config import CustomRule

    scenario, _ = kich_ban.from_excel(INPUT_FILE)
    assert scenario["custom"] == [] and len(kich_ban.schema()["custom"]["kinds"]) == 6
    scenario["custom"] = [{"kind": "Chỉ xếp vào", "subject": "Thể dục", "sessions": "Chiều", "hard": False, "level": 3},
                          {"kind": "Học trước", "subject": "Tiếng Việt", "other": "Toán", "hard": True}]
    out = tmp_path / "ra.xlsx"
    kich_ban.to_excel(scenario, out)
    assert read_rules(out)["CUSTOM_RULES"] == [
        CustomRule("chi_xep", "Thể dục", sessions=("Chiều",), level=3, row=2),
        CustomRule("truoc", "Tiếng Việt", other="Toán", hard=True, row=3)]
    back, _ = kich_ban.from_excel(out)
    assert back["custom"][0]["sessions"] == "Chiều" and back["custom"][0]["level"] == 3
    assert back["custom"][1] | {} == {"kind": "Học trước", "subject": "Tiếng Việt", "other": "Toán", "grades": "",
                                      "days": "", "periods": "", "sessions": "", "role": "", "number": None,
                                      "hard": True, "level": None}
    assert kich_ban.check(back, config.MODE_OVERTIME, 2)["errors"] == []
    back["custom"].append({"kind": "Học trước", "subject": "Toán"})
    assert "LUẬT RIÊNG, dòng 4: kiểu luật Học trước phải ghi cột Môn thứ hai" in \
        kich_ban.check(back, config.MODE_OVERTIME, 2)["errors"]
