"""Bộ ghép luật (tkb/bo_ghep.py): đọc dòng Tự ghép và các mẫu mới, đếm đúng từng phép đo trên một TKB (so với
phép đếm viết tay), xếp đúng luật bắt buộc, luật ưu tiên làm giảm số lần không theo, đếm trước khi xếp."""
from collections import Counter

import pytest

from tkb import bo_ghep, bo_mau, config, luat_rieng
from tkb.allocation import build_problem
from tkb.checker import check
from tkb.config import CustomRule
from tkb.rules import applied
from tkb.solver import ConflictError, solve
from tkb.staff import InputError

from .conftest import CURRICULUM, small_staff

SETTINGS = dict(time_limit=5, workers=4, overtime_max=4)
MORNING = (1, 2, 3, 4)


def _parse(**cells):
    errors = []
    rule = luat_rieng.parse(cells, 7, errors.append)
    return rule, errors


def _solve(*rules):
    with applied({"CUSTOM_RULES": list(rules)}):
        sol = solve(small_staff(general=False), CURRICULUM, config.Settings(mode=config.MODE_OVERTIME, **SETTINGS),
                    log=lambda *_: None)
        return sol, check(sol.problem, sol.lessons)


@pytest.fixture(scope="module")
def plain():
    return _solve()[0]


def _count(sol, rule) -> int:
    """Số lần không theo luật (bắt buộc hay ưu tiên) theo bộ ghép."""
    with applied({"CUSTOM_RULES": [rule]}):
        return sum(n for _, n, _, _ in bo_ghep.violations(sol.problem, sol.lessons))


def _session(p: int) -> str:
    return "Sáng" if p in MORNING else "Chiều"


def test_parse_composed_rule():
    rule, errors = _parse(kind="Tự ghép", scope="Giáo viên, Ngày", measure="Số khác nhau", op="tối đa", number=2,
                          count_by="Lớp", role="Bộ Môn", hard="Có")
    assert errors == [] and rule == CustomRule("tu_ghep", role="bộ môn", number=2, hard=True, row=7,
                                               scope=("gv", "ngay"), measure="so_khac", op="<=", count_by="lop")
    assert luat_rieng.describe(rule) == "Mỗi GV bộ môn, mỗi ngày: dạy tối đa 2 lớp khác nhau (bắt buộc)"
    back, errors = _parse(**{k: v for k, v in luat_rieng.cells(rule).items()})
    assert errors == [] and back == rule  # ghi ra rồi đọc lại như cũ
    rule, errors = _parse(kind="Tự ghép", scope="Lớp × Buổi", subject="Tiếng Việt", group="Có", measure="Liền nhau",
                          tags="Môn nặng", when=">= 6, chẵn", level=3)
    assert errors == [] and rule.group and rule.tags == ("Môn nặng",) and rule.when == ((">=", 6), ("chan", 0))
    assert rule.scope == ("lop", "buoi")
    assert _parse(kind="Tự ghép", measure="Vị trí", op="không trong", tags="Hạn chế môn nặng",
                  subject="Toán")[1] == []


@pytest.mark.parametrize("cells, error", [
    (dict(kind="Tự ghép", measure="Số tiết", number=1), "phép đo Số tiết phải ghi cột So sánh"),
    (dict(kind="Tự ghép", measure="Số tiết", op="Chỉ trong", number=1), "phép đo Số tiết so sánh Tối đa, Tối thiểu"),
    (dict(kind="Tự ghép", measure="Liền nhau", scope="Ngày"), "cột Với mỗi phải có Lớp hoặc Giáo viên"),
    (dict(kind="Tự ghép", measure="Liền nhau", scope="Lớp", number=2), "cột Số không dùng cho phép đo Liền nhau"),
    (dict(kind="Tự ghép", measure="Số khác nhau", op="<=", number=2, scope="Lớp", count_by="Lớp"),
     "Đếm theo không được trùng"),
    (dict(kind="Tự ghép", measure="Vị trí", op="Chỉ trong", subject="Toán"), "phép đo Vị trí phải ghi ít nhất"),
    (dict(kind="Tự ghép", measure="Số tiết", op="<=", number="tải ngày", scope="Lớp"), "phải có Giáo viên và Ngày"),
    (dict(kind="Tự ghép", measure="Số khác nhau", op="<=", number="tải ngày", scope="Giáo viên", count_by="Lớp"),
     "cột Số chỉ ghi"),
    (dict(kind="Tự ghép", measure="Số tiết", op="<=", number=1, points=0), "cột Điểm ghi một số nguyên dương"),
    (dict(kind="Tự ghép", measure="Người dạy", op="Do", subject="Toán"),
     "phải ghi cột Giáo viên (chức vụ, Mã GV hoặc họ tên)"),
    (dict(kind="Tự ghép", measure="Đo đạc"), "cột Phép đo ghi một trong"),
    (dict(kind="Tự ghép", measure="Số tiết", op="<=", number=1, scope="Phòng"), "cột Với mỗi ghi các chiều"),
    (dict(kind="Tự ghép", measure="Số tiết", op="<=", number=1, tags="Môn khó"), "cột Nhãn ghi tên các cột"),
    (dict(kind="Tự ghép", measure="Số tiết", op="<=", number=1, when="nhiều"), "cột Áp dụng khi ghi điều kiện"),
    (dict(kind="Không xếp vào", subject="Toán", periods="1", measure="Số tiết"),
     "cột Phép đo không dùng cho kiểu luật Không xếp vào"),
    (dict(kind="Cố định vào", subject="Thể dục"), "ít nhất một trong các cột Ngày, Tiết, Buổi"),
])
def test_parse_errors(cells, error):
    rule, errors = _parse(**cells)
    assert rule is None and any(error in e for e in errors), errors


def _tv_triples(sol, subject):
    n = 0
    for cls in sol.problem.classes:
        for d in range(5):
            for half in (True, False):
                ps = {l.period for l in sol.lessons if (l.class_name, l.day) == (cls, d)
                      and (l.period in MORNING) == half and l.subject == subject}
                n += sum(1 for i in ps for k in ps for j in range(i + 1, k) if k >= i + 2 and j not in ps)
    return n


def test_each_measure_counts_like_a_hand_count(plain):
    """Mỗi phép đo, trên một TKB đã xếp, đếm đúng như phép đếm viết tay."""
    les = plain.lessons
    teachers = plain.problem.teachers
    # Số tiết: mỗi lớp mỗi ngày tối đa 1 tiết Tiếng Việt.
    per = Counter((l.class_name, l.day) for l in les if l.subject == bo_mau.TV)
    rule = CustomRule("tu_ghep", "Tiếng Việt", scope=("lop", "ngay"), measure="so_tiet", op="<=", number=1)
    assert _count(plain, rule) == sum(n - 1 for n in per.values() if n > 1) > 0
    # Số tiết, tối thiểu: mỗi lớp mỗi ngày ít nhất 1 tiết Tiếng Anh (ngày không có tiết nào cũng tính).
    have = Counter((l.class_name, l.day) for l in les if l.subject == bo_mau.TIENG_ANH)
    rule = CustomRule("tu_ghep", "Tiếng Anh", scope=("lop", "ngay"), measure="so_tiet", op=">=", number=1)
    assert _count(plain, rule) == sum(1 for c in plain.problem.classes for d in range(5) if not have[c, d])
    # Số khác nhau: mỗi GV mỗi ngày dạy tối đa 1 lớp.
    classes = {}
    for l in les:
        classes.setdefault((l.teacher, l.day), set()).add(l.class_name)
    rule = CustomRule("tu_ghep", scope=("gv", "ngay"), measure="so_khac", op="<=", number=1, count_by="lop")
    assert _count(plain, rule) == sum(len(v) - 1 for v in classes.values() if len(v) > 1) > 0
    # Vị trí: Toán không trong tiết 5–7.
    rule = CustomRule("tu_ghep", "Toán", measure="vi_tri", op="ngoai", periods=(5, 6, 7))
    assert _count(plain, rule) == sum(1 for l in les if l.subject == bo_mau.TOAN and l.period >= 5)
    # Liền nhau: các tiết Tiếng Việt trong buổi.
    rule = CustomRule("tu_ghep", "Tiếng Việt", scope=("lop",), measure="lien")
    assert _count(plain, rule) == _tv_triples(plain, bo_mau.TV)
    # Thứ tự: Toán trước Tiếng Việt trong buổi.
    n = 0
    for l in les:
        if l.subject == bo_mau.TV:
            n += sum(1 for m in les if m.subject == bo_mau.TOAN and (m.class_name, m.day) == (l.class_name, l.day)
                     and _session(m.period) == _session(l.period) and m.period > l.period)
    rule = CustomRule("tu_ghep", "Toán", other="Tiếng Việt", scope=("lop",), measure="thu_tu")
    assert _count(plain, rule) == n
    # Đi kèm: ngày có Âm nhạc thì có Mỹ thuật (mỗi tiết Âm nhạc của ngày không có Mỹ thuật).
    art = {(l.class_name, l.day) for l in les if l.subject == "Mỹ thuật"}
    rule = CustomRule("tu_ghep", "Âm nhạc", other="Mỹ thuật", scope=("lop", "ngay"), measure="di_kem")
    assert _count(plain, rule) == sum(1 for l in les if l.subject == "Âm nhạc" and (l.class_name, l.day) not in art)
    # Người dạy: Tiếng Việt chỉ do Chủ Nhiệm dạy; Tiếng Anh do Bộ Môn dạy (không ai).
    rule = CustomRule("tu_ghep", "Tiếng Anh", role="bộ môn", measure="nguoi_day", op="do")
    assert _count(plain, rule) == sum(1 for l in les if l.subject == bo_mau.TIENG_ANH)
    rule = CustomRule("tu_ghep", "Tiếng Việt", role="chủ nhiệm", measure="nguoi_day", op="do")
    assert _count(plain, rule) == sum(1 for l in les if l.subject == bo_mau.TV and not teachers[l.teacher].class_name)
    # Người dạy, cùng một người: mỗi lớp mỗi ngày mọi tiết do một người (số người thừa).
    who = {}
    for l in les:
        who.setdefault((l.class_name, l.day), set()).add(l.teacher)
    rule = CustomRule("tu_ghep", scope=("lop", "ngay"), measure="nguoi_day", op="cung_nguoi")
    assert _count(plain, rule) == sum(len(v) - 1 for v in who.values() if len(v) > 1) > 0
    # Khoảng cách: tiết trống giữa buổi của mỗi GV; mỗi tiết Toán cách cuối buổi tối đa 1 tiết.
    gaps = 0
    for (g, d), _ in classes.items():
        for half in (True, False):
            ps = sorted(l.period for l in les if (l.teacher, l.day) == (g, d) and (l.period in MORNING) == half)
            gaps += (ps[-1] - ps[0] + 1 - len(ps)) if ps else 0
    rule = CustomRule("tu_ghep", scope=("gv",), measure="khoang_cach", op="trong_tiet", number=0)
    assert _count(plain, rule) == gaps
    end = lambda p: 4 if p in MORNING else 7  # noqa: E731
    rule = CustomRule("tu_ghep", "Toán", measure="khoang_cach", scope=("lop",), op="cuoi_buoi", number=1)
    assert _count(plain, rule) == sum(max(0, end(l.period) - l.period - 1) for l in les if l.subject == bo_mau.TOAN)
    # Theo cặp (ưu tiên): tiết Tiếng Anh lẻ trong buổi.
    lonely = 0
    for l in les:
        if l.subject == bo_mau.TIENG_ANH and not any(
                m.subject == bo_mau.TIENG_ANH and (m.class_name, m.day) == (l.class_name, l.day)
                and abs(m.period - l.period) == 1 and _session(m.period) == _session(l.period) for m in les):
            lonely += 1
    rule = CustomRule("tu_ghep", "Tiếng Anh", scope=("lop",), measure="cap")
    assert _count(plain, rule) == lonely


def test_composed_hard_rules_hold():
    """Luật tự ghép bắt buộc của nhiều phép đo cùng lúc: TKB xếp ra đúng luật, bộ kiểm tra độc lập không thấy lỗi."""
    rules = [
        CustomRule("tu_ghep", scope=("gv", "ngay"), measure="so_khac", op="<=", number=2, count_by="lop",
                   role="tiếng anh", hard=True, row=2),
        CustomRule("tu_ghep", "Tiếng Anh", scope=("lop", "ngay"), measure="so_tiet", op="<=", number=1, hard=True,
                   row=3),
        CustomRule("tu_ghep", "Toán", other="Tiếng Việt", scope=("lop",), measure="thu_tu", hard=True, row=4),
        CustomRule("tu_ghep", "Tin học", measure="vi_tri", op="trong", sessions=("Chiều",), hard=True, row=5),
        CustomRule("tu_ghep", "Thể dục", scope=("lop",), measure="khoang_cach", op="cuoi_buoi", number=1,
                   hard=True, row=6),
        CustomRule("tu_ghep", "Âm nhạc", other="Mỹ thuật", scope=("lop", "ngay"), measure="di_kem", hard=True,
                   row=7),
    ]
    sol, errors = _solve(*rules)
    assert errors == []
    les = sol.lessons
    for g in {l.teacher for l in les if l.subject == bo_mau.TIENG_ANH}:
        assert max(Counter(d for d in {(l.day, l.class_name) for l in les if l.teacher == g}).values()) <= 2
    assert max(Counter((l.class_name, l.day) for l in les if l.subject == bo_mau.TIENG_ANH).values()) == 1
    assert all(l.period >= 5 for l in les if l.subject == bo_mau.TIN_HOC)
    art = {(l.class_name, l.day) for l in les if l.subject == "Mỹ thuật"}
    assert all((l.class_name, l.day) in art for l in les if l.subject == "Âm nhạc")
    with applied({"CUSTOM_RULES": rules}):
        assert bo_ghep.violations(sol.problem, sol.lessons) == []


def test_soft_composed_rule_is_preferred(plain):
    """Luật ưu tiên làm giảm số lần không theo so với TKB không có luật."""
    rule = CustomRule("tu_ghep", scope=("gv",), measure="khoang_cach", op="trong_tiet", number=0, level=3, row=3)
    before = _count(plain, rule)
    sol, errors = _solve(rule)
    assert errors == [] and _count(sol, rule) < before
    with applied({"CUSTOM_RULES": [rule]}):
        assert luat_rieng.soft_report(sol.problem, sol.lessons)[0].endswith(f": {_count(sol, rule)} lần không theo")


def test_new_presets():
    """Mẫu mới: Cố định vào, Giáo viên tối đa lớp mỗi ngày, Học ít nhất số ngày, Chỉ giáo viên dạy."""
    rules = [CustomRule("co_dinh", "Thể dục", classes=("3/1",), days=(1,), periods=(3,), hard=True, row=2),
             CustomRule("gv_lop_ngay", role="âm nhạc", number=1, hard=True, row=3),
             CustomRule("rai_ngay", "Tiếng Anh", number=4, hard=True, row=4),
             CustomRule("chi_gv", "Tiếng Anh", role="tiếng anh", hard=True, row=5)]
    sol, errors = _solve(*rules)
    assert errors == []
    les = sol.lessons
    assert [l.subject for l in les if (l.class_name, l.day, l.period) == ("3/1", 1, 3)] == ["Thể dục"]
    for cls in sol.problem.classes:
        assert len({l.day for l in les if l.class_name == cls and l.subject == bo_mau.TIENG_ANH}) >= 4
    assert max(Counter(l.day for l in les if l.subject == "Âm nhạc").values()) == 1  # 2 lớp, 1 GV, 1 lớp/ngày
    assert {sol.problem.teachers[l.teacher].role for l in les if l.subject == bo_mau.TIENG_ANH} == {"tiếng anh"}
    assert luat_rieng.describe(rules[0]) == "Thể dục lớp 3/1 cố định vào Thứ 3 tiết 3 (bắt buộc)"
    assert luat_rieng.describe(rules[3]) == "Tiếng Anh chỉ do GV Tiếng Anh dạy (bắt buộc)"
    with applied({"CUSTOM_RULES": [CustomRule("chi_gv", "Kỹ năng sống", role="tiếng anh", hard=True, row=6)]}):
        with pytest.raises(InputError, match="Lớp 3/1: không GV nào được dạy Kỹ năng sống theo LUẬT RIÊNG dòng 6"):
            build_problem(small_staff(), CURRICULUM, {}, overtime_max=0)


def test_teacher_rule_filters_the_assignment():
    """Người dạy "Do" không xét ô: lọc GV được dạy ngay khi phân công (bộ môn không nhận Tin học)."""
    rule = CustomRule("chi_gv", "Tin học", role="tin học", hard=True, row=2)
    with applied({"CUSTOM_RULES": [rule]}):
        p = build_problem(small_staff(), CURRICULUM, {}, overtime_max=0)
    for c in p.courses:
        if c.subject == bo_mau.TIN_HOC:
            assert {p.teachers[g].role for g in c.teachers} == {"tin học"}


def test_precheck_finds_impossible_counts():
    def run(*rules):
        with applied({"CUSTOM_RULES": list(rules)}):
            problem = build_problem(small_staff(), CURRICULUM, {}, overtime_max=0)
            return luat_rieng.precheck(problem)

    # Tiết 1 luôn do GVCN: Tiếng Anh (GV chuyên biệt) không thể cố định vào tiết 1.
    found = run(CustomRule("co_dinh", "Tiếng Anh", days=(0,), periods=(1,), hard=True, row=4))
    assert found and found[0].startswith("LUẬT RIÊNG dòng 4: Tiếng Anh cố định vào Thứ 2 tiết 1 (bắt buộc): lớp 3/1 "
                                         "Thứ 2 tiết 1 chỉ có thể có 0, cần 1")
    # Cố định nhiều tiết hơn chương trình học.
    found = run(CustomRule("co_dinh", "Tin học", days=(1, 2), periods=(5,), hard=True, row=5))
    assert found == ["LUẬT RIÊNG dòng 5: Tin học cố định vào Thứ 3, Thứ 4 tiết 5 (bắt buộc): lớp 3/1 cần ít nhất 2 "
                     "tiết Tin học nhưng chương trình chỉ có 1"]
    with pytest.raises(ConflictError, match="LUẬT RIÊNG dòng 5"):
        _solve(CustomRule("co_dinh", "Tin học", days=(1, 2), periods=(5,), hard=True, row=5))


def test_extensions_count_like_a_hand_count(plain):
    """Trừ nhãn, ngưỡng theo dữ liệu (tải ngày, số tiết/tuần chia số ngày), "trừ Chủ Nhiệm", Thứ tự "sau" với Môn
    thứ hai để trống (các môn khác cùng nhóm), Điểm."""
    import math

    from tkb.solver import day_targets
    les, p = plain.lessons, plain.problem
    # Rải đều: mỗi lớp, môn, ngày tối đa ⌈tiết/tuần / số ngày⌉, trừ HĐTN và các môn ưu tiên buổi sáng.
    per = Counter((l.class_name, l.subject, l.day) for l in les)
    skip = {config.HDTN} | set(config.MORNING_SUBJECTS)
    want = sum(max(0, n - math.ceil(p.curriculum[3][s] / 5)) for (c, s, d), n in per.items() if s not in skip)
    rule = CustomRule("tu_ghep", scope=("lop", "mon", "ngay"), measure="so_tiet", op="<=", derived="tran_ngay",
                      exclude=("Môn HĐTN", "Ưu tiên buổi sáng"))
    assert _count(plain, rule) == want
    # Tải ngày của GV không chủ nhiệm.
    load = Counter((l.teacher, l.day) for l in les if not p.teachers[l.teacher].class_name)
    want = sum(max(0, n - day_targets(p.teachers[g].max_lessons, p.slots)[d]) for (g, d), n in load.items())
    rule = CustomRule("tu_ghep", scope=("gv", "ngay"), measure="so_tiet", op="<=", derived="tai_ngay",
                      role="trừ chủ nhiệm")
    assert _count(plain, rule) == want
    # Tiết tăng cường đứng sau các tiết môn chính cùng nhóm trong ngày (luật có sẵn đúng thì 0; đổi chỗ thì thấy).
    rule = CustomRule("tu_ghep", tags=("Môn tăng cường",), scope=("lop", "nhom_mon", "ngay"), measure="thu_tu",
                      op="sau", hard=True)
    assert _count(plain, rule) == 0
    tc = next(l for l in les if l.subject == bo_mau.TOAN_TC)
    main = next(l for l in les if (l.class_name, l.day, l.subject) == (tc.class_name, tc.day, bo_mau.TOAN))
    swapped = [l if l not in (tc, main) else type(l)(**{**l.__dict__, "period": (main if l is tc else tc).period})
               for l in les]
    assert _count(type(plain)(**{**plain.__dict__, "lessons": swapped}), rule) == 1
    # Điểm thay cho Mức.
    rule = CustomRule("tu_ghep", "Toán", measure="vi_tri", op="ngoai", periods=(5, 6, 7), points=50, row=4)
    assert bo_ghep.weight(bo_ghep.make(rule), config.Weights()) == 50
    assert luat_rieng.describe(rule) == "Các tiết Toán không xếp vào tiết 5, 6, 7 (ưu tiên thấp)"  # 50 điểm: gần Thấp


def _two_english():
    """Trường nhỏ có hai GV Tiếng Anh: "TA" (Tiếng Anh 1) và "Cô Lan" (Tiếng Anh 2)."""
    from .conftest import teacher
    return [*small_staff(general=False), teacher("Cô Lan", "tiếng anh 2", 23, row=10)]


def test_parse_busy_and_teacher_names():
    """Không xếp vào / Chỉ xếp vào ghi Giáo viên thì bỏ trống Môn được (giờ bận); cột Giáo viên ghi Mã GV hay họ tên."""
    rule, errors = _parse(kind="Không xếp vào", role="Bộ Môn 3", days="Thứ 2", periods="1", hard="Có")
    assert errors == [] and rule == CustomRule("khong_xep", role="bộ môn 3", days=(0,), periods=(1,), hard=True, row=7)
    assert luat_rieng.describe(rule) == "Bộ Môn 3 không dạy vào Thứ 2 tiết 1 (bắt buộc)"
    assert luat_rieng.cells(rule)["role"] == "Bộ Môn 3"
    back, errors = _parse(**luat_rieng.cells(rule))
    assert errors == [] and back == rule
    _, errors = _parse(kind="Không xếp vào", days="Thứ 2", hard="Có")
    assert any("phải ghi cột Môn" in e for e in errors)
    rule, _ = _parse(kind="Chỉ xếp vào", subject="Toán", role="Chủ Nhiệm", sessions="Sáng")
    assert luat_rieng.describe(rule) == "GV chủ nhiệm chỉ dạy Toán vào buổi sáng (ưu tiên vừa)"
    rule, _ = _parse(kind="Giáo viên tối đa tiết mỗi ngày", role="Tiếng Anh 2", number=3, hard="Có")
    assert luat_rieng.describe(rule) == "Tiếng Anh 2 dạy tối đa 3 tiết mỗi ngày (bắt buộc)"


def test_rules_for_one_teacher(plain):
    """Cột Giáo viên ghi một người (Mã GV hoặc họ tên): đếm như đếm tay, xếp thật đạt, phân công chỉ cho người đó,
    câu đọc lại ghi Mã GV thay cho họ tên."""
    # Giờ bận theo tiết (không ghi Môn): đếm các tiết của đúng người đó ở các ô đó.
    gym = next(les for les in plain.lessons if les.teacher == "thể dục 1")
    busy = CustomRule("khong_xep", role="td", days=(gym.day,), sessions=(_session(gym.period),), hard=True, row=2)
    by_hand = sum(1 for les in plain.lessons if les.teacher == "thể dục 1" and les.day == gym.day
                  and _session(les.period) == _session(gym.period))
    assert _count(plain, busy) == by_hand > 0
    assert _count(plain, CustomRule("khong_xep", role="an", days=(gym.day,), hard=True)) == sum(
        1 for les in plain.lessons if les.teacher == "âm nhạc 1" and les.day == gym.day)
    with applied({"CUSTOM_RULES": [busy]}):
        from tkb.phan_cong import teacher_slots
        p = build_problem(small_staff(general=False), CURRICULUM, {}, overtime_max=4)
        bad = {(gym.day, q) for q in (MORNING if _session(gym.period) == "Sáng" else (5, 6, 7))}
        assert bo_ghep.busy(p.teachers["thể dục 1"]) == bad and bo_ghep.busy(p.teachers["âm nhạc 1"]) == set()
    with applied({}):
        p0 = build_problem(small_staff(general=False), CURRICULUM, {}, overtime_max=4)
        before = teacher_slots(p0)["thể dục 1"]
    with applied({"CUSTOM_RULES": [busy]}):
        assert teacher_slots(p)["thể dục 1"] == before - len(bad)

    # Ép phân công: Tiếng Anh lớp 3/1 chỉ Tiếng Anh 2 dạy (Mã GV), lớp 3/2 chỉ người tên "TA" dạy (họ tên).
    rules = [busy, CustomRule("chi_gv", "Tiếng Anh", classes=("3/1",), role="tiếng anh 2", hard=True, row=3),
             CustomRule("chi_gv", "Tiếng Anh", classes=("3/2",), role="ta", hard=True, row=4)]
    with applied({"CUSTOM_RULES": rules}):
        p = build_problem(_two_english(), CURRICULUM, {}, overtime_max=4)
        english = {c.class_name: c.teachers for c in p.courses if c.subject == bo_mau.TIENG_ANH}
        assert english == {"3/1": ["tiếng anh 2"], "3/2": ["tiếng anh 1"]}
        sol = solve(_two_english(), CURRICULUM, config.Settings(mode=config.MODE_OVERTIME, **SETTINGS),
                    log=lambda *_: None)
        assert check(sol.problem, sol.lessons) == []
        les = sol.lessons
        assert {l.teacher for l in les if l.subject == bo_mau.TIENG_ANH and l.class_name == "3/1"} == {"tiếng anh 2"}
        assert {l.teacher for l in les if l.subject == bo_mau.TIENG_ANH and l.class_name == "3/2"} == {"tiếng anh 1"}
        assert not [l for l in les if l.teacher == "thể dục 1" and (l.day, l.period) in bad]
        assert [n for _, n, _, _ in bo_ghep.violations(sol.problem, sol.lessons, hard=True)] == []
        # Câu đọc lại ghi Mã GV (config.PEOPLE), không ghi họ tên.
        bo_ghep.know_staff(_two_english())
        text = luat_rieng.describe(rules[2])
        assert text == "Tiếng Anh lớp 3/2 chỉ do tiếng anh 1 dạy (bắt buộc)"  # luật ghi họ tên "TA"
        assert luat_rieng.describe(CustomRule("chi_xep", role="cô lan", sessions=("Sáng",), hard=True)) == \
            "tiếng anh 2 chỉ dạy vào buổi sáng (bắt buộc)"
    assert config.PEOPLE == {}  # ra khỏi rules.applied thì trả lại như cũ


def test_teacher_names_are_checked():
    """Tên ở cột Giáo viên không phải chức vụ, Mã GV hay họ tên của ai, hoặc là họ tên của hai người: báo lỗi rõ
    dòng; ép phân công cho người không được dạy môn đó: lỗi ghi dòng luật."""
    from .conftest import teacher
    staff = [*small_staff(general=False), teacher("TA", "tiếng anh 2", 23, row=10)]  # hai người tên "TA"
    rules = [CustomRule("khong_xep", role="cô hoa", days=(0,), hard=True, row=5),
             CustomRule("gv_ngay", role="ta", number=3, hard=True, row=6),
             CustomRule("gv_ngay", role="tiếng anh 9", number=3, hard=True, row=7),
             CustomRule("gv_ngay", role="tiếng anh 2, chủ nhiệm 3/1, trừ td", number=5, hard=True, row=8)]
    with applied({"CUSTOM_RULES": rules}):
        p = build_problem(staff, CURRICULUM, {}, overtime_max=4)
        assert luat_rieng.validate(p) == [
            "LUẬT RIÊNG dòng 5: không có giáo viên nào có chức vụ, Mã GV hay họ tên 'Cô Hoa'",
            "LUẬT RIÊNG dòng 6: có 2 giáo viên tên 'Ta', ghi Mã GV để chỉ rõ người",
            "LUẬT RIÊNG dòng 7: không có giáo viên nào có chức vụ, Mã GV hay họ tên 'Tiếng Anh 9'"]
    rule = CustomRule("chi_gv", "Tin học", classes=("3/1",), role="tiếng anh 2", hard=True, row=9)
    with applied({"CUSTOM_RULES": [rule]}):
        with pytest.raises(InputError, match="Lớp 3/1: không GV nào được dạy Tin học theo LUẬT RIÊNG dòng 9: Tin học "
                                             "lớp 3/1 chỉ do Tiếng Anh 2 dạy"):
            build_problem(staff, CURRICULUM, {}, overtime_max=4)
