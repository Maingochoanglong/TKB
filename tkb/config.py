"""Các luật nghiệp vụ của hệ thống xếp TKB mà file vào không có.

Dữ liệu của trường (danh sách môn, số tiết từng khối, giáo viên, chức vụ, lớp, định mức) chỉ lấy từ
file vào, không ghi ở đây. Solver không hard-code số lớp, số tiết hay quyền dạy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Môn học
# --------------------------------------------------------------------------
# Danh sách môn và số tiết từng khối lấy từ sheet CHƯƠNG TRÌNH HỌC của file vào. Các tên dưới đây chỉ
# dùng để gắn luật cho môn; so khớp với tên trong file không phân biệt hoa thường, dấu câu và chữ "và"
# (vd "Lịch Sử và Địa Lý" khớp "Lịch sử - Địa lý"). Môn trong file không có ở đây vẫn được xếp bình
# thường, chỉ không có luật riêng.
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

# Tên môn hiển thị trong ô TKB (viết tắt); môn không có ở đây giữ nguyên tên.
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
# Chức vụ khác ba chức vụ trên là GV chuyên biệt: tên chức vụ trùng tên một môn trong sheet
# CHƯƠNG TRÌNH HỌC (vd "Tiếng Anh", "Thể Dục") và chỉ dạy môn đó.

# Cách ghi ba chức vụ trên trong các file xuất ra (GV chuyên biệt ghi đúng chữ trong file vào).
ROLE_LABELS: dict[str, str] = {ROLE_HOMEROOM: "Chủ Nhiệm", ROLE_GENERAL: "Bộ Môn", ROLE_MANAGER: "Quản Lý"}

# File vào gồm các sheet này (so khớp không phân biệt hoa thường); thiếu sheet nhân sự thì đọc sheet đầu.
STAFF_SHEET = "NHÂN SỰ"
PROGRAM_SHEET = "CHƯƠNG TRÌNH HỌC"

# Môn chỉ GVCN của lớp được dạy.
HOMEROOM_ONLY_SUBJECTS: set[str] = {HDTN}

# GV bộ môn dạy được mọi môn trừ các môn sau. Môn bị cấm mà trường chưa có GV chuyên biệt thì chương
# trình tự thêm chức vụ trùng tên môn để tuyển (vd "tin học 1").
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
# Các tiết luôn do GVCN của lớp dạy, ở mọi ngày (tiết 1-4 là buổi sáng, 5-7 là buổi chiều).
HOMEROOM_PERIODS: set[int] = {1}

# --------------------------------------------------------------------------
# GV bổ sung khi thiếu người
# --------------------------------------------------------------------------
# Định mức của GV bổ sung = Số tiết lớn nhất của GV cùng chức vụ (không thai sản) trong file vào;
# chức vụ chưa có ai thì lấy Số tiết lớn nhất của các GV không chủ nhiệm, không quản lý.
SUPPLEMENT_NAME = "chưa có"

# --------------------------------------------------------------------------
# Chế độ xử lý khi thiếu người
# --------------------------------------------------------------------------
MODE_HIRE = "tuyen_them"  # thêm GV bổ sung "chưa có" vào danh sách nhân sự
MODE_OVERTIME = "bu_gio"  # GVCN/bộ môn dạy bù vượt định mức; chỉ tuyển khi bù vẫn không đủ
MODES = (MODE_HIRE, MODE_OVERTIME)
# Chức vụ được dạy bù. GVCN chỉ bù ở lớp mình, không bù môn của GV chuyên biệt; GVCN bù
# trước, bộ môn chỉ bù khi GVCN đã bù hết mức. Người hưởng thai sản ("ts") không bao giờ bù.
OVERTIME_ROLES: set[str] = {ROLE_HOMEROOM, ROLE_GENERAL}
OVERTIME_MAX = 2  # số tiết bù tối đa mỗi người mỗi tuần (mức được duyệt)

# --------------------------------------------------------------------------
# Luật bảo vệ học sinh
# --------------------------------------------------------------------------
# Môn nặng: hạn chế xếp vào các tiết này (mục tiêu mềm, trọng số Weights.heavy_late).
HEAVY_SUBJECTS: set[str] = {TOAN, TOAN_TC, TV, TV_TC, TIENG_ANH, KH, TIN_HOC}
HEAVY_LATE_PERIODS: set[int] = {7}
# Nhóm môn -> số tiết tối đa mỗi buổi (môn tăng cường được đếm riêng, không gộp vào môn gốc).
SESSION_SUBJECT_LIMITS: list[tuple[frozenset[str], int]] = [
    (frozenset({TV}), 2),
    (frozenset({TOAN}), 2),
]


def rule_subjects() -> list[str]:
    """Các môn được nhắc tới trong luật ở trên (để kiểm tra tên môn trong file vào)."""
    names = [HDTN, *HOMEROOM_PRIORITY, *HOMEROOM_CUT_ORDER, *HOMEROOM_FILL_ORDER, *HOMEROOM_ONLY_SUBJECTS,
             *GENERAL_FORBIDDEN_SUBJECTS, *(r.subject for r in MANAGER_RULES), *HEAVY_SUBJECTS,
             *(s for group, _ in SESSION_SUBJECT_LIMITS for s in group), *DISPLAY_NAMES]
    return sorted(set(names))


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
    heavy_late: int = 200  # mỗi tiết môn nặng ở tiết 7
    subject_spread: int = 20  # mỗi tiết vượt mức rải đều môn/ngày
    teacher_gap: int = 10  # mỗi tiết trống giữa buổi của GV
    general_on_specialist: int = 1  # mỗi tiết bộ môn dạy thay môn chuyên biệt
    load_balance: int = 50  # mỗi tiết dư lớn nhất giữa các GV cùng chức vụ
    supplement_order: int = 1  # dồn tiết cho GV bổ sung số thứ tự nhỏ trước
    # Chế độ bù giờ (thứ tự ưu tiên: ít tiết bù của bộ môn > ít tiết bù của GVCN > chia đều >
    # GVCN bù đúng thứ tự môn > hạn chế chia môn).
    overtime_general: int = 200_000  # mỗi tiết bộ môn dạy bù (đắt hơn GVCN để GVCN bù trước)
    overtime_homeroom: int = 100_000  # mỗi tiết GVCN dạy bù
    overtime_second: int = 50_000  # mỗi tiết bù từ tiết thứ 2 của một người (ai cũng +1 rồi mới +2)
    overtime_subject_order: int = 3_000  # × hạng môn: môn ưu tiên (0) rồi HOMEROOM_FILL_ORDER (1, 2...)


@dataclass
class Settings:
    student_rules: bool = True
    mode: str = MODE_HIRE
    overtime_max: int = OVERTIME_MAX  # chỉ dùng ở chế độ bù giờ
    time_limit: float = 240.0
    # Chạy lại cùng dữ liệu luôn ra cùng một TKB (xem solver._configure).
    reproducible: bool = True
    deterministic_per_second: float = 1.0  # quy đổi time_limit sang thời gian tất định
    safety_factor: float = 20.0  # giới hạn giây thực = time_limit × hệ số này (chỉ để chặn treo)
    workers: int = 8
    seed: int = 0
    weights: Weights = field(default_factory=Weights)
