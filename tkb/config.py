"""Toàn bộ tham số nghiệp vụ của hệ thống xếp TKB.

Mọi giá trị có thể thay đổi theo trường/năm học đều nằm ở đây, solver không
hard-code số lớp, số tiết hay quyền dạy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Môn học
# --------------------------------------------------------------------------
TV = "Tiếng Việt"
TOAN = "Toán"
HDTN = "Hoạt động trải nghiệm"
KH = "Khoa học"
LSDL = "Lịch sử - Địa lý"
DD = "Đạo đức"
TNXH = "Tự nhiên xã hội"
KNS = "Kỹ năng sống"
CONG_NGHE = "Công nghệ"
TOAN_TC = "Toán tăng cường"
TV_TC = "Tiếng Việt tăng cường"
TIENG_ANH = "Tiếng Anh"
TIN_HOC = "Tin học"
THE_DUC = "Thể dục"
AM_NHAC = "Âm nhạc"
MY_THUAT = "Mỹ thuật"

SUBJECTS: list[str] = [TV, TOAN, HDTN, KH, LSDL, DD, TNXH, KNS, CONG_NGHE, TOAN_TC, TV_TC,
                       TIENG_ANH, TIN_HOC, THE_DUC, AM_NHAC, MY_THUAT]

# Chương trình mặc định (số tiết/tuần theo khối) - đúng số liệu doanh nghiệp.
# Có thể thay bằng file Input_Chuong_Trinh_Hoc qua tham số --program.
DEFAULT_CURRICULUM: dict[int, dict[str, int]] = {
    1: {TV: 14, TOAN: 5, HDTN: 3, TIENG_ANH: 2, TNXH: 2, KH: 0, LSDL: 0, THE_DUC: 2,
        AM_NHAC: 1, MY_THUAT: 1, DD: 1, TIN_HOC: 0, CONG_NGHE: 0, TOAN_TC: 0, TV_TC: 0, KNS: 1},
    2: {TV: 10, TOAN: 5, HDTN: 3, TIENG_ANH: 2, TNXH: 2, KH: 0, LSDL: 0, THE_DUC: 2,
        AM_NHAC: 1, MY_THUAT: 1, DD: 1, TIN_HOC: 0, CONG_NGHE: 0, TOAN_TC: 2, TV_TC: 2, KNS: 1},
    3: {TV: 7, TOAN: 5, HDTN: 3, TIENG_ANH: 4, TNXH: 2, KH: 0, LSDL: 0, THE_DUC: 2,
        AM_NHAC: 1, MY_THUAT: 1, DD: 1, TIN_HOC: 1, CONG_NGHE: 1, TOAN_TC: 2, TV_TC: 1, KNS: 1},
    4: {TV: 7, TOAN: 5, HDTN: 3, TIENG_ANH: 4, TNXH: 0, KH: 2, LSDL: 2, THE_DUC: 2,
        AM_NHAC: 1, MY_THUAT: 1, DD: 1, TIN_HOC: 1, CONG_NGHE: 1, TOAN_TC: 1, TV_TC: 0, KNS: 1},
    5: {TV: 7, TOAN: 5, HDTN: 3, TIENG_ANH: 4, TNXH: 0, KH: 2, LSDL: 2, THE_DUC: 2,
        AM_NHAC: 1, MY_THUAT: 1, DD: 1, TIN_HOC: 1, CONG_NGHE: 1, TOAN_TC: 1, TV_TC: 0, KNS: 1},
}

# Tên môn hiển thị trong ô TKB (giống template); môn không có ở đây giữ nguyên tên.
DISPLAY_NAMES: dict[str, str] = {
    HDTN: "HĐTN",
    TNXH: "TNXH",
    TV_TC: "TV tăng cường",
}

# --------------------------------------------------------------------------
# Khung thời gian
# --------------------------------------------------------------------------
DAYS: list[str] = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"]


@dataclass(frozen=True)
class Session:
    name: str
    periods: tuple[int, ...]


MORNING = Session("Sáng", (1, 2, 3, 4))
AFTERNOON = Session("Chiều", (5, 6, 7))

# Buổi học của từng ngày (theo chỉ số trong DAYS). Thứ 6 chỉ học buổi sáng.
DAY_SESSIONS: dict[int, tuple[Session, ...]] = {
    0: (MORNING, AFTERNOON),
    1: (MORNING, AFTERNOON),
    2: (MORNING, AFTERNOON),
    3: (MORNING, AFTERNOON),
    4: (MORNING,),
}

# Nhãn cho slot không học (chiều Thứ 6).
OFF_LABEL = "Nghỉ"

# --------------------------------------------------------------------------
# HĐTN: 2 tiết cố định + tiết còn lại xếp giữa tuần, ưu tiên cuối buổi
# --------------------------------------------------------------------------
HDTN_FIXED_SLOTS: list[tuple[int, int]] = [(0, 1), (4, 4)]  # (ngày, tiết): T2 tiết 1, T6 tiết 4
HDTN_FLEX_DAYS: list[int] = [1, 2, 3]  # Thứ 3 - Thứ 5

# --------------------------------------------------------------------------
# Chức vụ và quyền dạy
# --------------------------------------------------------------------------
ROLE_HOMEROOM = "chủ nhiệm"
ROLE_GENERAL = "bộ môn"
ROLE_MANAGER = "quản lý"

# Chức vụ chuyên biệt -> môn duy nhất được dạy (tên chức vụ trùng tên môn).
SPECIALIST_ROLES: dict[str, str] = {
    "tiếng anh": TIENG_ANH,
    "tin học": TIN_HOC,
    "thể dục": THE_DUC,
    "âm nhạc": AM_NHAC,
    "mỹ thuật": MY_THUAT,
}

# Môn chỉ GVCN của lớp được dạy.
HOMEROOM_ONLY_SUBJECTS: set[str] = {HDTN}

# GV bộ môn dạy được mọi môn trừ các môn sau.
GENERAL_FORBIDDEN_SUBJECTS: set[str] = {TIENG_ANH, TIN_HOC, HDTN}


@dataclass(frozen=True)
class ManagerRule:
    """Quản lý chỉ dạy môn `subject` của khối `grade`.

    `classes`: nếu khác None thì chỉ các lớp này (vd ("4/1", "4/2")); None = solver tự chọn.
    Số tiết dạy đúng bằng cột Số tiết của quản lý (giới hạn bởi số tiết khả dụng).
    """
    subject: str
    grade: int
    classes: tuple[str, ...] | None = None


MANAGER_RULES: list[ManagerRule] = [ManagerRule(subject=KNS, grade=4)]

# --------------------------------------------------------------------------
# Phân công GVCN
# --------------------------------------------------------------------------
# GVCN nhận trọn các môn này của lớp mình (HĐTN luôn là GVCN).
HOMEROOM_PRIORITY: list[str] = [TV, TOAN, HDTN, KH, LSDL, DD]
# Vượt định mức: cắt theo thứ tự này, chỉ môn có hơn 1 tiết; GVCN giữ lại ít nhất 1 tiết.
HOMEROOM_CUT_ORDER: list[str] = [TV, TOAN, KH, LSDL]
# Thiếu định mức: nhận thêm theo thứ tự này (không bao giờ nhận môn của GV chuyên biệt).
HOMEROOM_FILL_ORDER: list[str] = [TV_TC, TOAN_TC, TNXH, KNS, CONG_NGHE]

# --------------------------------------------------------------------------
# GV bổ sung khi thiếu người
# --------------------------------------------------------------------------
SUPPLEMENT_NAME = "chưa có"
# Chỉ dùng khi chức vụ chưa có GV nào (không "ts") để suy ra định mức.
FALLBACK_SUPPLEMENT_LOAD = 23

# --------------------------------------------------------------------------
# Luật bảo vệ học sinh (V15)
# --------------------------------------------------------------------------
HEAVY_SUBJECTS: set[str] = {TOAN, TOAN_TC, TV, TV_TC, TIENG_ANH, KH, TIN_HOC}
HEAVY_FORBIDDEN_PERIODS: set[int] = {7}
# Số tiết nặng liên tiếp tối đa trong một buổi.
MAX_CONSECUTIVE_HEAVY: dict[str, int] = {"Sáng": 3, "Chiều": 2}
# Nhóm môn -> số tiết tối đa mỗi buổi.
SESSION_SUBJECT_LIMITS: list[tuple[frozenset[str], int]] = [
    (frozenset({TV}), 2),
    (frozenset({TOAN}), 2),
]
# Gộp môn tăng cường vào giới hạn mỗi buổi của môn gốc.
SESSION_SUBJECT_LIMITS_MERGED: list[tuple[frozenset[str], int]] = [
    (frozenset({TV, TV_TC}), 2),
    (frozenset({TOAN, TOAN_TC}), 2),
]


# --------------------------------------------------------------------------
# Trọng số mục tiêu (phân tầng)
# --------------------------------------------------------------------------
@dataclass
class Weights:
    supplement_lesson: int = 1_000_000  # mỗi tiết giao cho GV bổ sung
    supplement_teacher: int = 100_000  # mỗi GV bổ sung được dùng
    course_split: int = 5_000  # mỗi GV thêm vào cùng một lớp-môn (chia môn cho 2 GV)
    specialist_supplement: int = 1_000  # GV bổ sung là chuyên biệt (ưu tiên tuyển bộ môn đa năng)
    day_over_preferred: int = 100  # mỗi tiết vượt tải ngày mong muốn
    day_over_buffer: int = 300  # mỗi tiết vượt tải ngày mong muốn + 1
    hdtn_flex_distance: int = 200  # mỗi tiết cách cuối buổi của HĐTN flex
    subject_spread: int = 20  # mỗi tiết vượt mức rải đều môn/ngày
    teacher_gap: int = 10  # mỗi tiết trống giữa buổi của GV
    general_on_specialist: int = 1  # mỗi tiết bộ môn dạy thay môn chuyên biệt
    load_balance: int = 50  # mỗi tiết dư lớn nhất giữa các GV cùng chức vụ


@dataclass
class Settings:
    student_rules: bool = True
    merge_enhanced_limits: bool = False
    time_limit: float = 120.0
    workers: int = 8
    seed: int = 0
    weights: Weights = field(default_factory=Weights)
