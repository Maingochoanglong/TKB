"""Luật có sẵn của chương trình, viết bằng cùng câu của bộ ghép luật (tkb/bo_ghep.py).

Mỗi luật có sẵn vẫn mã hóa riêng trong solver/checker/lns/phan_cong như trước (đổi cách mã hóa là đổi mã kết quả),
nhưng ở đây được viết thành một câu "Với mỗi … · các tiết … · thì …" như luật nhà trường tự ghép:
- để nhà trường đọc mọi luật đang dùng theo một cách (sheet HƯỚNG DẪN của file vào cập nhật, giao diện);
- để kiểm chéo: luật nào viết được bằng bộ ghép (`CoSan.rule`) thì bộ đếm chung của bộ ghép phải thấy đúng như
  bộ kiểm tra độc lập (tests/test_luat_co_san.py), và hạ bằng bộ ghép thay cho bản gốc cũng cho TKB đúng luật.

Tham số đọc từ config lúc gọi (trong rules.applied), nên các cột quy định của file vào chỉnh luôn các câu này.
Phần thuật toán (chia phần GVCN, tách tiết cho người tuyển, LNS) và dữ liệu (khung giờ, chương trình học) không phải
luật nên không có ở đây.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from . import config
from .config import CustomRule

GROUPS = ("Cấu trúc", "Bảo vệ học sinh", "HĐTN và GVCN", "Người dạy", "Lịch giáo viên", "Phân công",
          "Ưu tiên khi xếp giờ")


@dataclass(frozen=True)
class CoSan:
    group: str
    text: str  # câu theo ngữ pháp bộ ghép (luật có `rule`: đúng câu bộ ghép nói)
    hard: bool
    source: str  # nhà trường chỉnh ở đâu
    native: str  # mã hóa ở đâu trong chương trình
    rule: CustomRule | None = None  # cùng luật viết bằng bộ ghép; None: chỉ mô tả (ngưỡng theo từng GV, lớp...)
    points: str = ""  # luật ưu tiên: điểm trừ

    def sentence(self) -> str:
        return self.text + (" (bắt buộc)" if self.hard else f" (ưu tiên: {self.points})")


def _rule(**kw) -> CustomRule:
    return CustomRule("tu_ghep", **kw)


def _say(rule: CustomRule) -> str:
    from .luat_rieng import composed
    return composed(rule)


def _labels() -> dict[str, str]:
    from .rules import LABELS
    return LABELS


def co_san(problem=None, settings: config.Settings | None = None) -> list[CoSan]:
    """Các luật có sẵn đang có hiệu lực theo config hiện tại (và nhân sự của `problem` nếu có)."""
    settings = settings or config.Settings()
    w = settings.weights
    L = _labels()
    out: list[CoSan] = []

    def add(group, hard, source, native, rule=None, text=None, points=""):
        rule = replace(rule, hard=hard) if rule is not None else None
        out.append(CoSan(group, text or _say(rule), hard, source, native, rule, points))

    # A. Cấu trúc
    add("Cấu trúc", True, "khung giờ, chương trình học", "solver.build_timetable",
        _rule(scope=("lop", "o"), measure="so_tiet", op="<=", number=1))
    add("Cấu trúc", True, "sheet CHƯƠNG TRÌNH HỌC", "solver.build_timetable", text=(
        "Với mỗi lớp, môn: số tiết đúng bằng số tiết của chương trình học"))
    add("Cấu trúc", True, "sheet NHÂN SỰ", "solver.build_timetable",
        _rule(scope=("gv", "o"), measure="so_tiet", op="<=", number=1))
    add("Cấu trúc", True, "sheet NHÂN SỰ: Số Tiết/Tuần; main.py: SO_TIET_BU_TOI_DA", "phan_cong, solver._Allocation",
        text="Với mỗi giáo viên: số tiết tối đa bằng định mức (cộng số tiết bù tối đa ở chế độ bù giờ); Quản Lý đúng "
             "định mức")

    # B. Bảo vệ học sinh
    if settings.student_rules:
        add("Bảo vệ học sinh", True, f"sheet QUY ĐỊNH: {L['SESSION_GROUP_LIMIT']}", "solver.build_timetable",
            _rule(scope=("lop", "nhom_mon", "buoi"), measure="so_tiet", op="<=", number=config.SESSION_GROUP_LIMIT))
        for subject, limit in sorted(config.DAILY_LIMITS.items()):
            add("Bảo vệ học sinh", True, f"sheet CHƯƠNG TRÌNH HỌC: {L['DAILY_LIMITS']}", "solver.build_timetable",
                _rule(subject=subject, scope=("lop", "ngay"), measure="so_tiet", op="<=", number=limit,
                      when=(("<=", -1),)))
        source = f"sheet QUY ĐỊNH: {L['PAIR_MIN_LESSONS']}; cột {L['PAIR_EXCLUDED']}"
        native = "allocation.paired_groups, solver.build_timetable"
        if problem is None:
            add("Bảo vệ học sinh", True, source, native, text=(
                f"Với mỗi lớp, nhóm môn: các tiết (cả môn tăng cường) thành cặp 2 tiết liền trong buổi, khi số "
                f"tiết/tuần >= {config.PAIR_MIN_LESSONS}, chẵn (trừ các môn ghi {L['PAIR_EXCLUDED']})"))
        else:  # mỗi nhóm môn một câu, ở các khối nhóm đó phải ghép cặp
            from .allocation import paired_groups
            grades: dict[str, list[int]] = {}
            for g, req in sorted(problem.curriculum.items()):
                for group in paired_groups(req):
                    grades.setdefault(group, []).append(g)
            for group, gs in sorted(grades.items()):
                add("Bảo vệ học sinh", True, source, native,
                    _rule(subject=group, group=True, grades=tuple(gs), scope=("lop", "buoi"), measure="cap"))
        add("Bảo vệ học sinh", True, "luật bảo vệ học sinh", "solver.build_timetable",
            _rule(scope=("lop", "mon"), measure="lien"))
        for extra, main in sorted(config.SUBJECT_GROUPS.items()):
            add("Bảo vệ học sinh", True, f"sheet CHƯƠNG TRÌNH HỌC: {L['SUBJECT_GROUPS']}", "solver.build_timetable",
                _rule(subject=main, other=extra, scope=("lop", "ngay"), measure="thu_tu"))
            add("Bảo vệ học sinh", True, f"sheet CHƯƠNG TRÌNH HỌC: {L['SUBJECT_GROUPS']}", "solver.build_timetable",
                _rule(subject=extra, other=main, scope=("lop", "ngay"), measure="di_kem"))

    # C. HĐTN và GVCN
    if config.HDTN and config.HDTN_FIXED_SLOTS:
        add("HĐTN và GVCN", True, f"sheet QUY ĐỊNH: {L['HDTN_FIXED_SLOTS']}", "allocation.build_problem",
            _rule(subject=config.HDTN, tags=("Tiết HĐTN cố định",), scope=("lop", "o"), measure="so_tiet",
                  op="=", number=1))
    if config.HDTN:
        add("HĐTN và GVCN", True, f"sheet QUY ĐỊNH: {L['HDTN_FLEX_DAYS']}", "allocation.build_problem", text=(
            f"Các tiết {config.HDTN} còn lại: chỉ trong các ngày {L['HDTN_FLEX_DAYS']}"))
        flex = tuple(sorted(config.HDTN_FLEX_DAYS))
        add("HĐTN và GVCN", False, f"sheet QUY ĐỊNH: {L['HDTN_FLEX_DAYS']}", "solver.build_timetable",
            _rule(subject=config.HDTN, days=flex, scope=("lop",), measure="khoang_cach", op="cuoi_buoi",
                  number=0), points=f"{w.hdtn_flex_distance} điểm mỗi tiết cách cuối buổi")
    if config.HOMEROOM_PERIODS:
        add("HĐTN và GVCN", True, f"sheet QUY ĐỊNH: {L['HOMEROOM_PERIODS']}", "solver.allowed_slots",
            _rule(tags=("Luôn do GVCN dạy",), role=config.ROLE_HOMEROOM, measure="nguoi_day", op="do"))
    if config.HOMEROOM_ONLY_SUBJECTS:
        add("HĐTN và GVCN", True, f"sheet CHƯƠNG TRÌNH HỌC: {L['HOMEROOM_ONLY_SUBJECTS']}",
            "allocation.build_problem", _rule(tags=("Chỉ GVCN dạy",), role=config.ROLE_HOMEROOM,
                                              measure="nguoi_day", op="do"))

    # D. Người dạy trong TKB
    add("Người dạy", True, "luật cứng", "solver.build_timetable: Liên tiết", text=(
        "Với mỗi lớp, nhóm môn, buổi: hai tiết liền nhau do cùng một người dạy"))
    if config.HOMEROOM_PRIORITY:
        add("Người dạy", True, f"sheet CHƯƠNG TRÌNH HỌC: {L['HOMEROOM_PRIORITY']}",
            "solver.build_timetable: GVCN trước",
            text=f"Với mỗi lớp, nhóm môn {L['HOMEROOM_PRIORITY'].lower()} có người khác cùng dạy: tiết đầu tuần do "
                 f"GVCN dạy, tiết của người khác không đứng trước tiết đầu tiên của GVCN")

    # E. Lịch giáo viên
    add("Lịch giáo viên", True, "sheet NHÂN SỰ: Buổi Nghỉ", "solver._teacher_sessions", text=(
        "Với mỗi giáo viên: không có tiết nào ở buổi nghỉ cố định; đủ số buổi nghỉ bất kỳ"))
    campus2 = problem is None or bool(problem.campus2)
    if campus2:
        add("Lịch giáo viên", True, "sheet NHÂN SỰ: Cơ sở 2", "solver._teacher_sessions",
            _rule(scope=("gv", "buoi"), measure="so_khac", op="<=", number=1, count_by="co_so"))
        add("Lịch giáo viên", False, "sheet NHÂN SỰ: Cơ sở 2", "solver._campus_day_switch",
            _rule(scope=("gv", "ngay"), measure="so_khac", op="<=", number=1, count_by="co_so"),
            points=f"{w.campus_day_switch} điểm mỗi giáo viên mỗi ngày")
        add("Lịch giáo viên", True, "sheet NHÂN SỰ: Cơ sở 2, Thai Sản", "allocation.build_problem", text=(
            "Các tiết của lớp cơ sở 1: không do giáo viên chỉ dạy cơ sở 2 (thai sản, hoặc ghi Cơ sở 2) dạy"))

    # F. Phân công
    add("Phân công", True, "sheet CHƯƠNG TRÌNH HỌC, CHỨC VỤ", "allocation.build_problem; checker: Quyền dạy", text=(
        "Các tiết của mỗi môn: do chức vụ được dạy môn đó dạy (Bộ Môn không dạy môn ghi Bộ Môn không dạy; GV chuyên "
        "biệt chỉ dạy các môn của chức vụ; Quản Lý chỉ các môn, khối ghi Quản lý dạy khối)"))
    add("Phân công", False, "sheet QUY ĐỊNH: Chủ Nhiệm/Bộ Môn được dạy bù; cột Hợp Đồng, Thai Sản",
        "phan_cong._flow", text="Tiết bù: GVCN hợp đồng, GVCN, bộ môn hợp đồng, rồi bộ môn; thai sản không bù; ai cũng "
                                "+1 rồi mới +2",
        points=f"{w.overtime_homeroom_contract}–{w.overtime_general} điểm mỗi tiết")
    add("Phân công", False, "sheet NHÂN SỰ: Lớp Đang Dạy", "allocation.keep_cost", text=(
        "Với mỗi giáo viên: dạy các khối, lớp đang dạy"), points=f"{w.keep_grade} điểm mỗi tiết khác khối, "
                                                                  f"{w.keep_class} mỗi tiết khác lớp")
    add("Phân công", False, "luật ưu tiên", "phan_cong._Local", text=(
        "Với mỗi giáo viên: số khối, số lớp khác nhau ít nhất; tiết của nhóm môn ghép cặp chia chẵn; tải đều giữa "
        "người cùng chức vụ"), points=f"{w.group_grade} điểm mỗi khối, {w.group_class} mỗi lớp")

    # G. Ưu tiên khi xếp giờ
    add("Ưu tiên khi xếp giờ", False, f"cột {L['HEAVY_SUBJECTS']}; sheet QUY ĐỊNH: {L['HEAVY_LATE_PERIODS']}",
        "solver.build_timetable",
        _rule(tags=("Môn nặng", "Hạn chế môn nặng"), measure="vi_tri", op="ngoai"),
        points=f"{w.heavy_late} điểm mỗi tiết")
    add("Ưu tiên khi xếp giờ", False, f"cột {L['MORNING_SUBJECTS']}", "solver.build_timetable",
        _rule(tags=("Ưu tiên buổi sáng",), sessions=(config.MORNING.name,), measure="vi_tri", op="trong"),
        points=f"{w.morning_core} điểm mỗi tiết")
    add("Ưu tiên khi xếp giờ", False, "sheet NHÂN SỰ: Số Tiết/Tuần", "solver.build_timetable", text=(
        "Với mỗi giáo viên, ngày: số tiết tối đa bằng tải ngày (định mức chia theo số tiết của ngày)"),
        points=f"{w.day_over_preferred} điểm mỗi tiết vượt, {w.day_over_buffer} từ tiết vượt thứ hai")
    add("Ưu tiên khi xếp giờ", False, "chương trình học", "solver.build_timetable", text=(
        "Với mỗi lớp, môn, ngày: số tiết tối đa bằng số tiết/tuần chia số ngày (làm tròn lên)"),
        points=f"{w.subject_spread} điểm mỗi tiết vượt ({w.core_spread} với môn ưu tiên buổi sáng)")
    if problem is not None:
        roles = sorted({t.role for t in problem.teachers.values() if t.role != config.ROLE_HOMEROOM})
        if roles:
            add("Ưu tiên khi xếp giờ", False, "luật ưu tiên", "solver.build_timetable",
                _rule(scope=("gv",), role=", ".join(roles), measure="khoang_cach", op="trong_tiet", number=0),
                points=f"{w.teacher_gap} điểm mỗi tiết trống")
    else:
        add("Ưu tiên khi xếp giờ", False, "luật ưu tiên", "solver.build_timetable", text=(
            "Với mỗi giáo viên không chủ nhiệm: mọi tiết: tối đa 0 tiết trống giữa các tiết"),
            points=f"{w.teacher_gap} điểm mỗi tiết trống")
    return out


def notes(problem=None, settings: config.Settings | None = None) -> list[tuple[str, str]]:
    """Các dòng "Luật đang dùng" (sheet HƯỚNG DẪN của file vào cập nhật): luật có sẵn rồi luật riêng của trường."""
    from .luat_rieng import SHEET, describe
    rows = [(f"Luật có sẵn: {c.group}", f"{c.sentence()}. Chỉnh ở: {c.source}.") for c in co_san(problem, settings)]
    rows += [(f"Luật riêng: {SHEET} dòng {r.row}", describe(r)) for r in config.CUSTOM_RULES]
    return rows
