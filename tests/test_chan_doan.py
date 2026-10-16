"""Chẩn đoán quy định mâu thuẫn (tkb/chan_doan.py): đếm trước khi xếp, và khi không xếp được thì chỉ ra luật nào."""
import pytest

from tkb import bo_mau, config, luat_co_san
from tkb.allocation import build_problem
from tkb.chan_doan import diagnose, precheck
from tkb.rules import applied
from tkb.solver import ConflictError, solve

from .conftest import CURRICULUM, small_staff

SETTINGS = dict(time_limit=5, workers=4, overtime_max=4)
GROUP_LIMIT = ("'Luật có sẵn: Mỗi buổi, một lớp học tối đa {} tiết của một môn, tính chung môn chính với môn tăng "
               "cường cùng nhóm (bắt buộc)'")
PAIRS = ("'Luật có sẵn: Môn có từ {} tiết/tuần trở lên và số tiết chẵn, tính chung môn tăng cường cùng nhóm, học "
         "thành cặp 2 tiết liền trong buổi; trừ môn có nhãn Không ghép cặp (bắt buộc)'")


def _rules(**params) -> dict:
    """Các dòng luật mặc định viết với các số khác (vd SESSION_GROUP_LIMIT=1: dòng "tối đa 1 tiết mỗi buổi")."""
    with applied(params):
        return {**params, **luat_co_san.apply(luat_co_san.default_rows())}


def _precheck(staff, **params):
    with applied(_rules(**params)):
        return precheck(build_problem(staff, CURRICULUM, {}, overtime_max=2))


def test_no_conflict_with_default_rules(sample_staff):
    assert _precheck(sample_staff) == []


def test_session_limit_too_small_for_the_lessons(sample_staff):
    found = _precheck(sample_staff, SESSION_GROUP_LIMIT=1)
    assert found[0] == (f"{GROUP_LIMIT.format(1)[1:-1]}: lớp 1/1 có 14 tiết Tiếng Việt/tuần nhưng tối đa 1 × 9 buổi "
                        f"= 9 tiết")
    # Khối 3: 8 tiết Tiếng Việt vừa 9 buổi, nhưng phải học thành cặp mà mỗi buổi chỉ được 1 tiết.
    assert (f"Khối 3: Tiếng Việt + Tiếng Việt tăng cường có 8 tiết/tuần nên phải học thành cặp 2 tiết liền (luật "
            f"{PAIRS.format(6)}) nhưng luật {GROUP_LIMIT.format(1)}") in found
    assert len(found) == 3  # mỗi nhóm môn của mỗi khối một lỗi: khối 1, 2 (đếm), khối 3 (ghép cặp)
    assert "lớp 2/1 có 12 tiết" in _precheck(sample_staff, SESSION_GROUP_LIMIT=1, PAIR_MIN_LESSONS=100)[-1]


def test_pairs_against_daily_limit(sample_staff):
    found = _precheck(sample_staff, PAIR_MIN_LESSONS=4, DAILY_LIMITS={bo_mau.TIENG_ANH: 1, bo_mau.TOAN: 1})
    daily = ("'Luật có sẵn: Mỗi ngày, một lớp học tối đa 1 tiết Tiếng Anh, khi số tiết/tuần của môn không quá số "
             "ngày học (bắt buộc)'")
    assert found == [f"Khối {g}: Tiếng Anh có 4 tiết/tuần nên phải học thành cặp 2 tiết liền (luật {PAIRS.format(4)}) "
                     f"nhưng luật {daily}" for g in (3, 4, 5)]


def test_student_rules_off_skips_the_count():
    with applied(_rules(SESSION_GROUP_LIMIT=1)):
        assert precheck(build_problem(small_staff(), CURRICULUM, {}, overtime_max=2), student_rules=False) == []


def test_solve_stops_before_solving_on_a_counted_conflict():
    with applied(_rules(SESSION_GROUP_LIMIT=1)), pytest.raises(ConflictError, match="Khối 3: Tiếng Việt"):
        solve(small_staff(), CURRICULUM, config.Settings(**SETTINGS), log=lambda *_: None)


def test_diagnosis_names_the_rules_in_conflict():
    """HĐTN: chỉ còn tiết cố định Thứ 6 tiết 4 và 2 tiết còn lại cũng chỉ được xếp Thứ 6 (chỉ có buổi sáng) mà mỗi
    buổi một nhóm môn tối đa 2 tiết: phép đếm không thấy, bộ giải thấy, chẩn đoán chỉ ra đúng 2 luật."""
    log, before = [], (config.OFF, config.CUSTOM_RULES)
    with applied({"HDTN_FIXED_SLOTS": [(4, 4)], "HDTN_FLEX_DAYS": [4]}), pytest.raises(ConflictError) as err:
        solve(small_staff(), CURRICULUM, config.Settings(mode=config.MODE_OVERTIME, **SETTINGS), log=log.append)
    limit = GROUP_LIMIT.format(2)[1:-1]
    flex = ("Luật có sẵn: Tiết HĐTN chỉ xếp vào giờ có nhãn Tiết HĐTN cố định hoặc Xếp tiết HĐTN còn lại (bắt "
            "buộc)")
    assert str(err.value).splitlines() == [
        "Các luật bắt buộc sau không cùng thỏa được, nên không có TKB nào:", f"  - {limit}", f"  - {flex}",
        f"Nới hoặc bỏ một trong các luật trên. Chỉ cần nới riêng một luật này là xếp được: {limit}; {flex}."]
    assert any(line.startswith("Chẩn đoán:") for line in log)
    assert (config.OFF, config.CUSTOM_RULES) == before  # chẩn đoán xong trả lại như cũ


def test_diagnosis_of_a_solvable_school_blames_the_time():
    found = diagnose(small_staff(), CURRICULUM, config.Settings(**SETTINGS), log=lambda *_: None, seconds=5)
    assert not found.conflict and "Tăng thời gian xếp giờ" in found.lines[0]
