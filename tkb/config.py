"""Giá trị mặc định của các luật nghiệp vụ, trọng số mục tiêu và tham số xếp giờ.

Dữ liệu của trường (danh sách môn, số tiết từng khối, giáo viên, chức vụ, lớp, định mức) chỉ lấy từ
file vào, không ghi ở đây. Solver không hard-code số lớp, số tiết hay quyền dạy.
Các luật nghiệp vụ (khung giờ, HĐTN, GVCN, quyền dạy, bù giờ, luật bảo vệ học sinh, môn nặng, tên viết tắt) nhà
trường sửa trong file vào (các cột quy định của sheet CHƯƠNG TRÌNH HỌC và sheet QUY ĐỊNH, tkb/rules.py); giá trị
dưới đây chỉ dùng cho quy định file vào không ghi.
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
AM_NHAC = "Âm nhạc"
MY_THUAT = "Mỹ thuật"

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
# Không bắt buộc: các luật nghiệp vụ, mỗi ô ghi Có, Không hoặc số (tkb/rules.py): quy định của môn là các cột của
# sheet CHƯƠNG TRÌNH HỌC, các quy định khác ở sheet này (ba bảng: chung, ngày, tiết); thiếu thì dùng giá trị dưới đây.
RULES_SHEET = "QUY ĐỊNH"
# File vào cập nhật (<file vào>_cap_nhat.xlsx) lưu TKB đã xếp ở sheet này, dạng lưới như TKB: dòng đầu ghi mã kết
# quả và mã quy định; bảng Lớp | Tiết | Thứ 2 …, mỗi ô ghi môn, xuống dòng ghi Mã GV (thêm " (bù)" ở tiết dạy bù).
# Nạp lại file đó làm file vào thì chương trình dùng lại TKB này nếu vẫn đúng mọi luật (vd chỉ đổi tên người
# "chưa có" thành tên người mới tuyển); main.py GIU_TKB_DA_XEP = False (dòng lệnh --xep-lai) thì xếp lại từ đầu.
SAVED_SHEET = "TKB đã xếp"
SAVED_OVERTIME = "(bù)"
SAVED_CODES = ("Mã kết quả", "Mã quy định")

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
# Định mức của GV bổ sung = Số tiết lớn nhất của GV cùng chức vụ trong file vào;
# chức vụ chưa có ai thì lấy Số tiết lớn nhất của các GV không chủ nhiệm, không quản lý.
SUPPLEMENT_NAME = "chưa có"

# --------------------------------------------------------------------------
# Chế độ xử lý khi thiếu người
# --------------------------------------------------------------------------
# Cả hai chế độ dùng chung một TKB: người tuyển mới dạy đúng các ô mà ở chế độ bù giờ là tiết bù.
MODE_HIRE = "tuyen_them"  # thêm GV bổ sung "chưa có": nhận các tiết bù và phần còn thiếu
MODE_OVERTIME = "bu_gio"  # GVCN/bộ môn dạy bù vượt định mức; bù vẫn không đủ thì báo lỗi, không tuyển
MODES = (MODE_HIRE, MODE_OVERTIME)
# Chức vụ được dạy bù. GVCN chỉ bù ở lớp mình, không bù môn của GV chuyên biệt (trừ
# HOMEROOM_OVERTIME_SPECIALIST); GVCN bù trước, bộ môn chỉ bù khi GVCN đã bù hết mức.
OVERTIME_ROLES: set[str] = {ROLE_HOMEROOM, ROLE_GENERAL}
# Môn của GV chuyên biệt mà GVCN vẫn được dạy bù ở lớp mình (nhận sau cùng, sau các môn trong
# HOMEROOM_FILL_ORDER). Tin học, Tiếng Anh, Thể dục thì không.
HOMEROOM_OVERTIME_SPECIALIST: set[str] = {AM_NHAC, MY_THUAT}
OVERTIME_MAX = 2  # số tiết bù tối đa mỗi người mỗi tuần (mức được duyệt)

# --------------------------------------------------------------------------
# Luật bảo vệ học sinh
# --------------------------------------------------------------------------
# Môn nặng: hạn chế xếp vào các tiết này (mục tiêu mềm, trọng số Weights.heavy_late).
HEAVY_SUBJECTS: set[str] = {TOAN, TOAN_TC, TV, TV_TC, TIENG_ANH, KH, TIN_HOC}
HEAVY_LATE_PERIODS: set[int] = {7}
# Buổi sáng dành cho môn chính (mục tiêu mềm, như TKB các trường khác: docs/Tham_Khao_TKB_Truong_Khac.md):
# mỗi tiết TV, Toán xếp vào buổi chiều bị phạt (Weights.morning_core).
MORNING_SUBJECTS: set[str] = {TV, TOAN}
# Nhóm môn: môn tăng cường (khóa) tính chung với môn chính (giá trị) cho các luật liên tiết, số tiết mỗi buổi
# và ghép cặp. Luật cứng đi kèm (luật bảo vệ học sinh): tiết tăng cường là tiết luyện bài vừa học nên trong một
# ngày phải có tiết chính cùng nhóm đứng trước nó và không có tiết chính nào đứng sau nó (không cần liền, không
# cần cùng người dạy, không cần buổi chiều).
SUBJECT_GROUPS: dict[str, str] = {TV_TC: TV, TOAN_TC: TOAN}
# Mỗi nhóm môn tối đa ngần ấy tiết mỗi buổi. Luật cứng đi kèm: môn nào có từ 2 tiết trong một buổi thì
# các tiết đó phải liền nhau, vd sáng "TV, Toán, TV, Anh" là sai, phải là "Toán, TV, TV, Anh".
SESSION_GROUP_LIMIT = 2
# Môn -> số tiết tối đa mỗi ngày, chỉ áp dụng khi số tiết/tuần không quá số ngày học (Toán mỗi ngày 1 tiết).
DAILY_LIMITS: dict[str, int] = {TOAN: 1}
# Nhóm môn có từ ngần ấy tiết/tuần và tổng số tiết chẵn thì xếp thành các cặp 2 tiết liền nhau, cùng người
# dạy (mỗi buổi 0 hoặc 2 tiết của nhóm), vd TV + TV tăng cường khối 1–3. Trừ các nhóm trong PAIR_EXCLUDED.
PAIR_MIN_LESSONS = 6
PAIR_EXCLUDED: set[str] = {TOAN, HDTN}  # Toán: mỗi ngày 1 tiết (DAILY_LIMITS); HĐTN: có ô cố định


# --------------------------------------------------------------------------
# Luật riêng của trường (sheet LUẬT RIÊNG, tkb/luat_rieng.py): mỗi dòng một luật thuộc một kiểu luật chung, bắt
# buộc hoặc ưu tiên (mức 1–3). Mặc định không có luật riêng nào.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CustomRule:
    kind: str  # khóa kiểu luật trong luat_rieng.KINDS, vd "khong_xep"
    subject: str = ""  # môn (tên như trong file vào)
    other: str = ""  # môn thứ hai (luật "Học trước": subject học trước other)
    grades: tuple[int, ...] = ()  # các khối; trống = mọi khối
    days: tuple[int, ...] = ()  # các ngày (0 = Thứ 2); trống = mọi ngày
    periods: tuple[int, ...] = ()  # các tiết; trống = mọi tiết
    sessions: tuple[str, ...] = ()  # các buổi (tên buổi, vd "Sáng"); trống = mọi buổi
    role: str = ""  # chức vụ của GV (chữ thường); trống = mọi GV
    number: int | None = None  # số trong luật (tối đa tiết mỗi ngày, số lớp cùng lúc)
    hard: bool = False  # bắt buộc; không thì là ưu tiên
    level: int = 2  # mức ưu tiên 1–3 (Weights.custom_levels)
    row: int = 0  # dòng trong sheet LUẬT RIÊNG (để báo lỗi)


CUSTOM_RULES: list[CustomRule] = []


def rule_subjects() -> list[str]:
    """Các môn được nhắc tới trong luật ở trên (để kiểm tra tên môn trong file vào)."""
    names = [HDTN, *HOMEROOM_PRIORITY, *HOMEROOM_CUT_ORDER, *HOMEROOM_FILL_ORDER, *HOMEROOM_ONLY_SUBJECTS,
             *GENERAL_FORBIDDEN_SUBJECTS, *(r.subject for r in MANAGER_RULES), *HEAVY_SUBJECTS,
             *MORNING_SUBJECTS, *SUBJECT_GROUPS, *SUBJECT_GROUPS.values(),
             *DAILY_LIMITS, *DISPLAY_NAMES, *HOMEROOM_OVERTIME_SPECIALIST]
    return sorted({n for n in names if n})  # HDTN = "": trường không có môn HĐTN (cột Môn HĐTN để trống)


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
    heavy_late: int = 1_200  # mỗi tiết môn nặng ở tiết 7 (400 thì file của trường còn 8 tiết trên Windows; 1200: 6;
                             # 3000 cũng 6 mà TV/Toán buổi chiều tăng)
    morning_core: int = 300  # mỗi tiết TV, Toán (MORNING_SUBJECTS) xếp vào buổi chiều
    core_spread: int = 120  # như subject_spread nhưng cho MORNING_SUBJECTS
    subject_spread: int = 40  # mỗi tiết vượt mức rải đều môn/ngày
    teacher_gap: int = 10  # mỗi tiết trống giữa buổi của GV
    campus_day_switch: int = 10_000  # mỗi (GV, ngày) sáng dạy cơ sở này, chiều cơ sở kia (luật cứng mỗi buổi
                                     # một cơ sở vẫn giữ; cứng cả ngày thì file của trường không ra TKB)
    general_on_specialist: int = 1_000  # mỗi tiết bộ môn dạy thay môn chuyên biệt (chỉ khi GV chuyên biệt đã
                                       # hết định mức; lớn hơn điểm gom lớp để không bị đổi chỉ vì gom lớp)
    load_balance: int = 50  # mỗi tiết dư lớn nhất giữa các GV cùng chức vụ
    supplement_order: int = 1  # dồn tiết cho GV bổ sung số thứ tự nhỏ trước
    # Chế độ bù giờ (thứ tự ưu tiên: ít tiết bù của bộ môn > ít tiết bù của GVCN > chia đều >
    # GVCN bù đúng thứ tự môn > hạn chế chia môn).
    # Ai bù trước: GVCN hợp đồng, GVCN khác, bộ môn hợp đồng, bộ môn khác (cột Hợp Đồng). Các mức cách nhau
    # 200.000 > 3 × overtime_second: tiết bù thứ 4 của mức trước vẫn rẻ hơn tiết thứ nhất của mức sau (đúng khi
    # bù tối đa đến +4); mức đắt nhất vẫn rẻ hơn một tiết thiếu (supplement_lesson).
    overtime_general: int = 700_000  # mỗi tiết bộ môn dạy bù (đắt hơn GVCN để GVCN bù trước)
    overtime_general_contract: int = 500_000  # mỗi tiết bộ môn hợp đồng dạy bù
    overtime_homeroom: int = 300_000  # mỗi tiết GVCN dạy bù
    overtime_homeroom_contract: int = 100_000  # mỗi tiết GVCN hợp đồng dạy bù
    overtime_second: int = 50_000  # mỗi tiết bù từ tiết thứ 2 của một người (ai cũng +1 rồi mới +2)
    overtime_subject_order: int = 3_000  # × hạng môn: môn ưu tiên (0) rồi HOMEROOM_FILL_ORDER (1, 2...)
    # Phân công (tkb/phan_cong.py, tìm kiếm cục bộ): gom lớp của một GV vào ít khối, ít lớp; môn ghép cặp
    # (PAIR_MIN_LESSONS) phải chia chẵn cho mỗi người.
    # Giữ phân công của TKB cũ (cột Lớp Đang Dạy): sau số tiết thiếu/tiết bù và sau "không chia lớp-môn", nhưng
    # trước gom lớp và cân bằng tải.
    keep_grade: int = 60  # mỗi tiết GV dạy khối không nằm trong các khối đang dạy
    keep_class: int = 10  # mỗi tiết GV dạy đúng khối cũ nhưng khác lớp cũ
    group_grade: int = 20  # mỗi khối một GV không chủ nhiệm dạy
    group_class: int = 5  # mỗi lớp một GV không chủ nhiệm dạy
    odd_pair_share: int = 100_000  # mỗi phần lẻ của một người trong nhóm môn ghép cặp
    # Luật riêng không bắt buộc (sheet LUẬT RIÊNG), theo mức 1, 2, 3: mỗi lần không theo luật bị trừ ngần ấy điểm
    # (mức 3 nặng hơn một tiết môn nặng ở tiết 7, mức 1 cỡ một tiết TV/Toán buổi chiều).
    custom_levels: tuple[int, int, int] = (100, 400, 1_500)


# --------------------------------------------------------------------------
# Xếp giờ: CP-SAT khởi đầu rồi xếp lại từng vùng (tkb/lns.py). Thời lượng tính như time_limit (≈ giây).
# --------------------------------------------------------------------------
# Khởi đầu: CP-SAT trên toàn mô hình với LNS_START_SHARE time_limit nhưng không quá LNS_START_MAX (không giới
# hạn thời gian: LNS_START_MAX). Khởi đầu dài hơn cho điểm xuất phát tốt hơn nhưng các vòng xếp lại kéo về gần
# như cùng mức, nên phần ngân sách còn lại dành cho các vòng.
LNS_START_SHARE: float = 0.2
LNS_START_MAX: float = 120
# Thời lượng tối đa mỗi lần xếp lại một vùng, theo loại vùng (vùng nhỏ thường giải xong sớm hơn).
LNS_REGION_LIMITS: dict[str, float] = {"lớp": 5, "điểm nóng": 10, "GV dùng chung": 15, "khối": 20, "cặp ngày": 30}
LNS_HOTSPOTS: int = 5  # số lớp-ngày xấu nhất (theo QA) được mở thành vùng "điểm nóng" mỗi vòng
LNS_SHARED_CLASSES: tuple[int, int] = (2, 8)  # vùng "GV dùng chung": GV dạy từ 2 đến 8 lớp
LNS_MIN_GAIN: float = 0.003  # dừng khi một vòng giảm chưa tới 0,3% chi phí (không giới hạn: khi vòng không giảm)
LNS_MAX_ROUNDS: int = 10

# Phiên bản OR-Tools đã ghim trong requirements.txt. Máy khác phiên bản thì TKB có thể khác.
ORTOOLS_VERSION = "9.15.6755"


@dataclass
class Settings:
    student_rules: bool = True
    mode: str = MODE_HIRE
    overtime_max: int = OVERTIME_MAX  # bù tối đa mỗi người; chế độ tuyển: người mới nhận đúng các tiết bù này
    time_limit: float | None = 1200.0  # tổng cho bước xếp giờ (tkb/lns.py); None: không giới hạn
    # Chạy lại cùng dữ liệu luôn ra cùng một TKB (xem solver._configure).
    reproducible: bool = True
    deterministic_per_second: float = 1.0  # quy đổi time_limit sang thời gian tất định
    workers: int = 8
    seed: int = 0
    weights: Weights = field(default_factory=Weights)
