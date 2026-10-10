"""Cột Thứ Tự Bù (không bắt buộc) của sheet NHÂN SỰ: ai dạy bù trước (1 = trước nhất; staff.parse_order,
allocation.overtime_rank, allocation.overtime_cost). Không ghi: GVCN hợp đồng 1, GVCN 2, bộ môn hợp đồng 3, bộ môn 4
như trước (cùng giá, cùng mã kết quả)."""
import dataclasses

import pytest

from tkb import config
from tkb.allocation import build_problem, overtime_cost, overtime_rank
from tkb.checker import check
from tkb.phan_cong import phan_cong
from tkb.solver import solve
from tkb.staff import InputError, parse_order

from .conftest import CURRICULUM, teacher

W = config.Weights()


def _staff(bm_lessons, **orders):
    """GVCN 3/1, 3/2, đủ GV chuyên biệt và các bộ môn; `orders`: Mã GV (dấu cách, "/" thành _) -> Thứ Tự Bù."""
    rows = [("CN 3/1", "chủ nhiệm 3/1", 19), ("CN 3/2", "chủ nhiệm 3/2", 19), ("TA", "tiếng anh 1", 23),
            ("TD", "thể dục 1", 23), ("AN", "âm nhạc 1", 23), ("MT", "mỹ thuật 1", 23), ("TH", "tin học 1", 23)]
    rows += [(f"BM{i}", f"bộ môn {i}", n) for i, n in enumerate(bm_lessons, start=1)]
    staff = [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
    key = lambda title: title.replace(" ", "_").replace("/", "_")  # noqa: E731
    return [dataclasses.replace(t, overtime_order=orders.get(key(t.title))) for t in staff]


def test_parse_order():
    assert parse_order(None) is None and parse_order(" ") is None
    assert parse_order(2) == 2 and parse_order("3") == 3 and parse_order(4.0) == 4
    for bad in (0, -1, 1.5, "một", True):
        with pytest.raises(InputError, match="Thứ Tự Bù ghi số nguyên dương"):
            parse_order(bad)


def test_default_order_keeps_the_old_prices():
    cn, bm = _staff([4])[0], _staff([4])[-1]
    contract = lambda t: dataclasses.replace(t, contract=True)  # noqa: E731
    assert [overtime_rank(t) for t in (contract(cn), cn, contract(bm), bm)] == [1, 2, 3, 4]
    assert [overtime_cost(t, W) for t in (contract(cn), cn, contract(bm), bm)] == [
        W.overtime_homeroom_contract, W.overtime_homeroom, W.overtime_general_contract, W.overtime_general]
    # Số khác 1–4: các thứ tự đang dùng chia đều khoảng giá, mức đắt nhất vẫn rẻ hơn một tiết thiếu.
    ranks = {"a": 1, "b": 5, "c": 10}
    prices = [overtime_cost(dataclasses.replace(cn, title=g), W, ranks) for g in ranks]
    assert prices == [W.overtime_homeroom_contract, 400_000, W.overtime_general] and prices[-1] < W.supplement_lesson


def test_general_teacher_first():
    """Bộ môn chỉ 4 tiết, còn thiếu 4 tiết (bù tối đa +4): mặc định hai GVCN bù; bộ môn ghi Thứ Tự Bù 1 thì bộ môn bù
    hết trước; bộ môn và GVCN cùng số thì bù ngang nhau (+1 trước +2)."""
    def overtime(staff):
        return phan_cong(build_problem(staff, CURRICULUM, {}, overtime_max=4), W).overtime

    assert overtime(_staff([4])) == {"chủ nhiệm 3/1": 2, "chủ nhiệm 3/2": 2}
    assert overtime(_staff([4], bộ_môn_1=1)) == {"bộ môn 1": 4}
    assert overtime(_staff([4], bộ_môn_1=2)) == {"chủ nhiệm 3/1": 1, "chủ nhiệm 3/2": 1, "bộ môn 1": 2}
    # GVCN 3/2 ghi 1: bù hết trước GVCN 3/1.
    assert overtime(_staff([4], chủ_nhiệm_3_2=1)) == {"chủ nhiệm 3/2": 4}


def test_general_teacher_first_end_to_end():
    """Xếp đủ TKB chế độ bù giờ: bộ môn bù trước GVCN, bộ kiểm tra độc lập không báo "nên để GVCN dạy" (luật GVCN ưu
    tiên bù lớp mình chỉ áp khi GVCN đứng trước trong thứ tự dạy bù)."""
    settings = config.Settings(mode=config.MODE_OVERTIME, time_limit=10, workers=4, overtime_max=4)
    sol = solve(_staff([4], bộ_môn_1=1), CURRICULUM, settings, log=lambda *_: None)
    assert sol.overtime() == {"bộ môn 1": 4} and check(sol.problem, sol.lessons) == []


def test_order_only_matters_for_overtime(tmp_path):
    """Người không được dạy bù (GV chuyên biệt) ghi Thứ Tự Bù: cảnh báo, không có tác dụng."""
    problem = build_problem(_staff([4], tiếng_anh_1=1), CURRICULUM, {}, overtime_max=4)
    assert "tiếng anh 1" not in problem.overtime_order and problem.overtime_order["bộ môn 1"] == 4
    assert any("Thứ Tự Bù không có tác dụng" in w for w in problem.warnings)
