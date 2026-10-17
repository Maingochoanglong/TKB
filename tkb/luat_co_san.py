"""Luật có sẵn của chương trình là các dòng của sheet LUẬT, viết bằng câu của bộ ghép luật (tkb/bo_ghep.py).

Mọi luật nằm trong file Excel: file mẫu ghi sẵn mỗi luật có sẵn thành một dòng (`default_rows`); nhà trường sửa số,
điểm, đổi Bắt buộc/Ưu tiên, xóa dòng (hoặc ghi Tạm tắt = Có) để tắt luật, thêm dòng để có luật mới. Khi đọc
(`apply`, chỉ các dòng không tạm tắt) mọi dòng xếp bằng bộ ghép (config.CUSTOM_RULES), cả dòng ở **dạng gốc** của một
luật có sẵn (`NATIVES`, chỉ khác số hay điểm): mỗi luật chỉ có một cách cài (docs/Thiet_Ke_Gop_Luat.md). Riêng hai
luật chỉ có dạng gốc vì đọc cột của sheet NHÂN SỰ (`NATIVE_ONLY`: Buổi nghỉ, Cơ sở 2) có mã riêng, bật khi có dòng
(config.OFF). Dạng gốc còn dùng để đọc tên dễ đọc của dòng (`title`) và nhận ra luật bảo vệ học sinh (`student`, tắt
bằng --no-student-rules).

File không có sheet LUẬT (file cũ) dùng các dòng mặc định, lấy số từ các cột quy định cũ (Số tiết tối đa một nhóm môn
mỗi buổi, Ghép cặp khi nhóm môn có từ, Tối đa tiết mỗi ngày), cộng các dòng của sheet LUẬT RIÊNG.

Phần không phải luật vẫn ở chương trình (`STRUCTURE`): cấu trúc TKB, các thuật toán (chia phần GVCN, tách tiết cho
người tuyển, LNS) và dữ liệu (khung giờ, chương trình học, nhân sự).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from . import config, khung_gio
from .config import CustomRule

GROUPS = ("Bảo vệ học sinh", "HĐTN và GVCN", "Người dạy", "Lịch giáo viên", "Ưu tiên khi xếp giờ")
CUSTOM_GROUP = "Luật riêng"
STRUCTURE = ("Cấu trúc của TKB (không phải luật, luôn có): mỗi lớp mỗi giờ học một tiết; mỗi lớp học đủ số tiết của "
             "chương trình học; giáo viên không dạy hai nơi cùng lúc, dạy không quá định mức (cộng số tiết bù tối đa ở "
             "chế độ bù giờ), Quản Lý dạy đúng định mức; giáo viên chỉ dạy các môn chức vụ được dạy (sheet CHƯƠNG "
             "TRÌNH HỌC, CHỨC VỤ).")


def _r(**kw) -> CustomRule:
    return CustomRule("tu_ghep", **kw)


@dataclass(frozen=True)
class Native:
    """Một luật có sẵn: các dòng ở dạng gốc (tham số theo config hiện tại) và cột nào là tham số."""
    key: str
    group: str
    rows: object  # () -> list[CustomRule]
    free: tuple[str, ...] = ()  # cột tham số: khác giá trị vẫn là dạng gốc
    student: bool = False  # luật bảo vệ học sinh (tắt cả nhóm bằng --no-student-rules)
    # Tên dễ đọc của từng dòng (theo thứ tự `rows`), điền {number}, {subject}, {min} (số ở cột Áp dụng khi) của dòng;
    # dòng đúng dạng gốc đọc bằng tên này (`title`), dòng đã sửa khác dạng gốc đọc bằng câu của bộ ghép.
    titles: tuple[str, ...] = ()


def _daily(subject: str, n: int) -> CustomRule:
    return _r(subject=subject, scope=("lop", "ngay"), measure="so_tiet", op="<=", number=n, when=(("<=", -1),),
              hard=True)


NATIVES = (
    Native("nhom_buoi", "Bảo vệ học sinh", lambda: [_r(
        scope=("lop", "nhom_mon", "buoi"), measure="so_tiet", op="<=", number=config.SESSION_GROUP_LIMIT,
        hard=True)], free=("number",), student=True,
        titles=("Mỗi buổi, một lớp học tối đa {number} tiết của một môn, tính chung môn chính với môn tăng cường cùng "
                "nhóm",)),
    Native("toi_da_ngay", "Bảo vệ học sinh", lambda: [_daily(s, n) for s, n in sorted(config.DAILY_LIMITS.items())],
           free=("subject", "number"), student=True,
           titles=("Mỗi ngày, một lớp học tối đa {number} tiết {subject}, khi số tiết/tuần của môn không quá số "
                   "ngày học",)),
    Native("ghep_cap", "Bảo vệ học sinh", lambda: [_r(
        scope=("lop", "nhom_mon", "buoi"), measure="cap", exclude=("Không ghép cặp",),
        when=((">=", config.PAIR_MIN_LESSONS), ("chan", 0)), hard=True)], free=("when",), student=True,
        titles=("Môn có từ {min} tiết/tuần trở lên và số tiết chẵn, tính chung môn tăng cường cùng nhóm, học thành "
                "cặp 2 tiết liền trong buổi; trừ môn có nhãn Không ghép cặp",)),
    Native("lien_nhau", "Bảo vệ học sinh", lambda: [_r(scope=("lop", "mon"), measure="lien", hard=True)],
           student=True, titles=("Các tiết của một môn trong cùng buổi phải đứng liền nhau",)),
    Native("tang_cuong", "Bảo vệ học sinh", lambda: [
        _r(tags=("Môn tăng cường",), scope=("lop", "nhom_mon", "ngay"), measure="thu_tu", op="sau", hard=True),
        _r(tags=("Môn tăng cường",), scope=("lop", "nhom_mon", "ngay"), measure="di_kem", hard=True)], student=True,
        titles=("Trong một ngày, tiết môn tăng cường đứng sau các tiết môn chính cùng nhóm",
                "Ngày có tiết môn tăng cường thì cũng có tiết môn chính cùng nhóm")),
    Native("hdtn_co_dinh", "HĐTN và GVCN", lambda: [_r(
        tags=("Môn HĐTN", "Tiết HĐTN cố định"), scope=("lop", "o"), measure="so_tiet", op="=", number=1,
        hard=True)],
        titles=("Ở mỗi giờ có nhãn Tiết HĐTN cố định, mỗi lớp học đúng 1 tiết HĐTN",)),
    Native("hdtn_ngay", "HĐTN và GVCN", lambda: [_r(
        tags=("Môn HĐTN", "Xếp tiết HĐTN còn lại", "Tiết HĐTN cố định"), measure="vi_tri", op="trong", hard=True)],
        titles=("Tiết HĐTN chỉ xếp vào giờ có nhãn Tiết HĐTN cố định hoặc Xếp tiết HĐTN còn lại",)),
    Native("hdtn_cuoi_buoi", "HĐTN và GVCN", lambda: [_r(
        tags=("Môn HĐTN", "Xếp tiết HĐTN còn lại"), exclude=("Tiết HĐTN cố định",), scope=("lop",),
        measure="khoang_cach", op="cuoi_buoi", number=0, points=200)],  # mỗi tiết cách cuối buổi
        free=("points",),
        titles=("Tiết HĐTN còn lại, ngoài giờ cố định, xếp ở tiết cuối buổi",)),
    Native("tiet_gvcn", "HĐTN và GVCN", lambda: [_r(
        tags=("Luôn do GVCN dạy",), measure="nguoi_day", op="do", role=config.ROLE_HOMEROOM, hard=True)],
        titles=("Ở giờ có nhãn Luôn do GVCN dạy, lớp học với GV chủ nhiệm",)),
    Native("chi_gvcn", "HĐTN và GVCN", lambda: [_r(
        tags=("Chỉ GVCN dạy",), measure="nguoi_day", op="do", role=config.ROLE_HOMEROOM, hard=True)],
        titles=("Môn có nhãn Chỉ GVCN dạy thì chỉ GV chủ nhiệm dạy",)),
    Native("lien_tiet", "Người dạy", lambda: [_r(
        scope=("lop", "nhom_mon", "buoi"), measure="nguoi_day", op="lien_cung_nguoi", hard=True)],
        titles=("Hai tiết liền nhau của một môn (cùng nhóm) trong buổi do cùng một giáo viên dạy",)),
    Native("gvcn_truoc", "Người dạy", lambda: [_r(
        tags=("GVCN nhận trọn",), scope=("lop", "nhom_mon"), measure="nguoi_day", op="dau_tuan",
        role=config.ROLE_HOMEROOM, hard=True)],
        titles=("Môn có nhãn GVCN nhận trọn: tiết đầu tuần của lớp do GV chủ nhiệm dạy, tiết của giáo viên khác "
                "không đứng trước",)),
    Native("buoi_nghi", "Lịch giáo viên", lambda: [CustomRule("nghi_gv", hard=True)],
        titles=("Giáo viên không dạy vào buổi nghỉ ghi ở cột Buổi Nghỉ và nghỉ đủ số buổi ghi ở đó",)),
    Native("co_so", "Lịch giáo viên", lambda: [_r(
        scope=("gv", "buoi"), measure="so_khac", op="<=", number=1, count_by="co_so", hard=True)],
        titles=("Mỗi buổi, một giáo viên chỉ dạy ở một cơ sở",)),
    # Ưu tiên, không bắt buộc: bắt buộc cả ngày một cơ sở thì file của trường không xếp được.
    Native("doi_co_so", "Lịch giáo viên", lambda: [_r(
        scope=("gv", "ngay"), measure="so_khac", op="<=", number=1, count_by="co_so",
        points=10_000)], free=("points",),
        titles=("Hạn chế để một giáo viên đổi cơ sở trong cùng một ngày (dạy ở hai cơ sở trở lên)",)),
    Native("co_so_2", "Lịch giáo viên", lambda: [CustomRule("co_so_2", hard=True)],
        titles=("Giáo viên không chủ nhiệm ghi Cơ sở 2 hoặc Thai Sản chỉ dạy các lớp ở cơ sở 2",)),
    # Điểm 1200: 400 thì file của trường còn 8 tiết môn nặng ở tiết 7 (Windows); 1200: 6; 3000 cũng 6 mà tiết
    # TV/Toán buổi chiều tăng.
    Native("mon_nang", "Ưu tiên khi xếp giờ", lambda: [_r(
        tags=("Môn nặng", "Hạn chế môn nặng"), measure="vi_tri", op="ngoai", points=1_200)],
        free=("points",),
        titles=("Tránh xếp môn có nhãn Môn nặng vào giờ có nhãn Hạn chế môn nặng",)),
    Native("buoi_sang", "Ưu tiên khi xếp giờ", lambda: [_r(
        tags=("Ưu tiên buổi sáng",), sessions=(khung_gio.first_session_name(),), measure="vi_tri", op="trong",
        points=300)], free=("points",),
        titles=("Môn có nhãn Ưu tiên buổi sáng xếp vào buổi sáng",)),
    Native("tai_ngay", "Ưu tiên khi xếp giờ", lambda: [_r(
        scope=("gv", "ngay"), measure="so_tiet", op="<=", derived="tai_ngay", points=100)],
        free=("points",),
        titles=("Số tiết mỗi ngày của giáo viên không quá tải ngày, tức số tiết/tuần chia đều cho các ngày",)),
    Native("tai_ngay_1", "Ưu tiên khi xếp giờ", lambda: [_r(
        scope=("gv", "ngay"), measure="so_tiet", op="<=", derived="tai_ngay_1", points=300)],
        free=("points",),
        titles=("Số tiết mỗi ngày của giáo viên không quá tải ngày + 1 tiết",)),
    Native("rai_deu", "Ưu tiên khi xếp giờ", lambda: [_r(
        exclude=("Môn HĐTN", "Ưu tiên buổi sáng"), scope=("lop", "mon", "ngay"), measure="so_tiet", op="<=",
        derived="tran_ngay", points=40)], free=("points",),
        titles=("Mỗi môn, trừ HĐTN và môn ưu tiên buổi sáng, rải đều trong tuần: một ngày không quá số tiết/tuần "
                "chia số ngày",)),
    Native("rai_deu_sang", "Ưu tiên khi xếp giờ", lambda: [_r(
        tags=("Ưu tiên buổi sáng",), exclude=("Môn HĐTN",), scope=("lop", "mon", "ngay"), measure="so_tiet",
        op="<=", derived="tran_ngay", points=120)], free=("points",),
        titles=("Môn ưu tiên buổi sáng rải đều trong tuần: một ngày không quá số tiết/tuần chia số ngày",)),
    Native("tiet_trong", "Ưu tiên khi xếp giờ", lambda: [_r(
        scope=("gv", "buoi"), role="trừ " + config.ROLE_HOMEROOM, measure="khoang_cach", op="trong_tiet", number=0,
        points=10)], free=("points",),
        titles=("Giáo viên, trừ GV chủ nhiệm, không có tiết trống xen giữa các tiết trong buổi",)),
)
BY_KEY = {n.key: n for n in NATIVES}
# Luật chỉ có dạng gốc (đọc cột của sheet NHÂN SỰ, không có câu bộ ghép): solver, checker, phân công dùng mã riêng,
# bật khi có dòng (config.OFF).
NATIVE_ONLY = ("buoi_nghi", "co_so_2")
STUDENT = frozenset(n.key for n in NATIVES if n.student)


def default_rows() -> list[CustomRule]:
    """Các dòng mặc định của sheet LUẬT: mỗi luật có sẵn ở dạng gốc, số và điểm theo config hiện tại."""
    return [replace(r, group_label=n.group) for n in NATIVES for r in n.rows()]


def rows() -> list[CustomRule]:
    """Các dòng luật đang dùng: sheet LUẬT của file vào; không có sheet thì các dòng mặc định (trừ dòng đã có trong
    config.CUSTOM_RULES) và luật riêng, theo thứ tự các luật có sẵn rồi luật riêng."""
    if config.RULES is not None:
        return list(config.RULES)
    have = {replace(r, row=0, group_label="") for r in config.CUSTOM_RULES}
    out = [r for r in default_rows() if replace(r, group_label="") not in have]
    out += [replace(r, group_label=r.group_label or CUSTOM_GROUP) for r in config.CUSTOM_RULES]
    order = {n.key: i for i, n in enumerate(NATIVES)}
    return sorted(out, key=lambda r: order[n.key] if (n := native_of(r)) is not None else len(NATIVES))


def student(r: CustomRule) -> bool:
    """Dòng ở dạng gốc của một luật bảo vệ học sinh (tắt cả nhóm bằng --no-student-rules, main.py LUAT_HOC_SINH)."""
    return (n := native_of(r)) is not None and n.student


def without_student(rules: list[CustomRule]) -> list[CustomRule]:
    """Các dòng trừ dòng luật bảo vệ học sinh (Settings.student_rules False: solver.solve, chan_doan.precheck)."""
    return [r for r in rules if not student(r)]


def hard_rows(student_rules: bool = True) -> list[CustomRule]:
    """Các dòng bắt buộc đang có hiệu lực (config.CUSTOM_RULES), cho bộ kiểm tra (checker.check kiểm bằng bộ ghép);
    trừ luật bảo vệ học sinh khi student_rules False, như mô hình."""
    return [r for r in config.CUSTOM_RULES if r.hard and (student_rules or not student(r))]


def title(r: CustomRule) -> str | None:
    """Tên dễ đọc của dòng ở dạng gốc một luật có sẵn, vd "Mỗi ngày, một lớp học tối đa 1 tiết Toán (…)"; None: dòng
    không ở dạng gốc (đọc bằng câu của bộ ghép, luat_rieng.composed)."""
    native = native_of(r)
    if native is None or not native.titles:
        return None
    shape = _shape(r, native.free)
    i = next((k for k, p in enumerate(native.rows()) if _shape(p, native.free) == shape), 0)
    least = r.when[0][1] if r.when and r.when[0][0] == ">=" else ""
    return native.titles[min(i, len(native.titles) - 1)].format(number=r.number, subject=r.subject, min=least)


def _names(text: str) -> list[str]:
    from .bo_ghep import names
    return names(text)


def _shape(r: CustomRule, free: tuple[str, ...]) -> CustomRule:
    """Dòng bỏ đi các phần không làm đổi dạng: số dòng, nhóm, mức và điểm, các cột tham số."""
    from .program import canonical_subject
    blank = {k: getattr(CustomRule(""), k) for k in free if k != "when"}
    if "when" in free:  # Ghép cặp khi nhóm môn có từ n tiết, chẵn
        blank["when"] = tuple((op, 0 if op == ">=" else v) for op, v in r.when)
    out = replace(r, **{"row": 0, "group_label": "", "level": 2, "points": None, **blank})
    if out.subject:
        out = replace(out, subject=", ".join(canonical_subject(s) for s in _names(out.subject)))
    return out


def fits(native: Native, r: CustomRule) -> bool:
    """Dòng r là dạng gốc của luật có sẵn (chỉ khác số, điểm)."""
    if native.key == "toi_da_ngay":  # mọi dòng "mỗi lớp mỗi ngày tối đa n tiết môn X, khi tiết/tuần <= số ngày"
        patterns = [_daily("x", 1)]
        if len(_names(r.subject)) != 1:
            return False
    else:
        patterns = native.rows()
    if "when" in native.free and not (len(r.when) == 2 and r.when[0][0] == ">=" and r.when[0][1] > 0):
        return False
    return any(r.hard == p.hard and _shape(r, native.free) == _shape(p, native.free) for p in patterns)


def native_of(r: CustomRule) -> Native | None:
    """Luật có sẵn mà dòng r là dạng gốc (None: dòng xếp bằng bộ ghép)."""
    return next((n for n in NATIVES if fits(n, r)), None)


def apply(all_rows: list[CustomRule]) -> dict:
    """Các dòng luật -> giá trị config: mọi dòng xếp bằng bộ ghép (CUSTOM_RULES), trừ dòng của luật chỉ có dạng gốc
    (NATIVE_ONLY: bật khi có dòng, không thì vào OFF). Gọi trong rules.applied của các quy định khác."""
    present, custom = set(), []
    for r in all_rows:
        native = native_of(r)
        if native is not None and native.key in NATIVE_ONLY:
            present.add(native.key)
        else:
            custom.append(r)
    return {"OFF": frozenset(k for k in NATIVE_ONLY if k not in present), "CUSTOM_RULES": custom}


def numbers(all_rows: list[CustomRule]) -> dict:
    """Số ở các dòng dạng gốc "tối đa n tiết một nhóm môn mỗi buổi", "ghép cặp khi nhóm môn có từ n tiết", "tối đa n
    tiết môn X mỗi ngày", theo tên cột cũ (config.SESSION_GROUP_LIMIT, PAIR_MIN_LESSONS, DAILY_LIMITS): để báo khi
    file có cả sheet LUẬT lẫn cột cũ ghi số khác (rules._rules_rows)."""
    from .program import canonical_subject
    out: dict = {"DAILY_LIMITS": {}}
    for r in all_rows:
        native = native_of(r)
        if native is None:
            continue
        if native.key == "toi_da_ngay":
            out["DAILY_LIMITS"][canonical_subject(_names(r.subject)[0])] = r.number
        elif native.key == "nhom_buoi":
            out.setdefault("SESSION_GROUP_LIMIT", r.number)
        elif native.key == "ghep_cap":
            out.setdefault("PAIR_MIN_LESSONS", r.when[0][1])
    return out


def notes() -> list[tuple[str, str]]:
    """Dòng của sheet HƯỚNG DẪN về phần không phải luật."""
    return [("LUẬT: cấu trúc của TKB", STRUCTURE)]
