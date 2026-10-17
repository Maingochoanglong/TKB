"""Bộ luật mẫu: giá trị ban đầu của các quy định gắn với tên môn và với cách tổ chức của một loại trường.

Code chỉ chứa cơ chế; tên môn, môn nào GVCN nhận trọn, môn nặng, tiết HĐTN cố định… là dữ liệu. Mỗi bộ mẫu là một
cách khởi đầu, nhà trường sửa tùy ý trong file vào (cột quy định của sheet CHƯƠNG TRÌNH HỌC, sheet QUY ĐỊNH, sheet
LUẬT) hay trên giao diện:

- `TIEU_HOC_VN` (Tiểu học Việt Nam): giá trị mặc định của chương trình (tkb/config.py lấy từ đây), dùng cho mọi quy
  định file vào không ghi, nên file cũ chạy y như trước.
- `TRONG` (Trống): không môn nào có quy định riêng, không có HĐTN, tiết luôn do GVCN dạy hay tiết hạn chế môn nặng;
  mọi ngày học hai buổi; các luật có sẵn theo quy ước của một nước (ghép cặp, mỗi buổi tối đa 2 tiết một nhóm môn,
  HĐTN, GVCN…) vẫn ghi ở sheet LUẬT nhưng ở trạng thái Tạm tắt (bật lại bằng ô Dùng), chỉ bật các luật theo dữ liệu
  trường ghi (buổi nghỉ, cơ sở) và các ưu tiên chung (tải ngày, rải đều, tiết trống, liên tiết cùng người dạy).

Module này không import module nào khác của tkb (tkb/config.py đọc nó lúc khởi tạo); rules.mau() đổi một bộ mẫu ra
giá trị config.
"""
from __future__ import annotations

# Tên môn của bộ mẫu Tiểu học Việt Nam. So khớp với tên trong file không phân biệt hoa thường, dấu câu và chữ "và"
# (vd "Lịch Sử và Địa Lý" khớp "Lịch sử - Địa lý"); môn trong file không có ở đây vẫn xếp bình thường.
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

TIEU_HOC_VN: dict[str, object] = {
    # Tên môn hiển thị trong ô TKB (viết tắt); môn không có ở đây giữ nguyên tên.
    "DISPLAY_NAMES": {HDTN: "HĐTN", TNXH: "TNXH", TV_TC: "TV tăng cường"},
    # Môn chào cờ, sinh hoạt lớp: 2 tiết cố định (Thứ 2 tiết 1, Thứ 6 tiết 4), tiết còn lại Thứ 3 – Thứ 5.
    "HDTN": HDTN,
    "HDTN_FIXED_SLOTS": [(0, 1), (4, 4)],
    "HDTN_FLEX_DAYS": [1, 2, 3],
    # Môn chỉ GVCN của lớp được dạy.
    "HOMEROOM_ONLY_SUBJECTS": {HDTN},
    # GV bộ môn dạy được mọi môn trừ các môn sau; trường chưa có GV chuyên biệt dạy được thì tuyển thêm.
    "GENERAL_FORBIDDEN_SUBJECTS": {TIENG_ANH, TIN_HOC, HDTN},
    # Quản lý dạy (môn, khối).
    "MANAGER_RULES": [(KNS, 4)],
    # GVCN nhận trọn các môn này của lớp mình; vượt định mức thì cắt theo thứ tự CUT (chỉ môn hơn 1 tiết, giữ ít nhất
    # 1 tiết); thiếu định mức thì nhận thêm theo thứ tự FILL (không nhận môn của GV chuyên biệt).
    "HOMEROOM_PRIORITY": [TV, TOAN, HDTN, KH, LSDL, DD],
    "HOMEROOM_CUT_ORDER": [TV, TOAN, KH, LSDL],
    "HOMEROOM_FILL_ORDER": [TV_TC, TOAN_TC, TNXH, KNS, CONG_NGHE],
    # Các tiết luôn do GVCN của lớp dạy, ở mọi ngày.
    "HOMEROOM_PERIODS": {1},
    # Môn của GV chuyên biệt mà GVCN vẫn được dạy bù ở lớp mình.
    "HOMEROOM_OVERTIME_SPECIALIST": {AM_NHAC, MY_THUAT},
    # Môn nặng hạn chế xếp vào các tiết HEAVY_LATE_PERIODS (mục tiêu mềm).
    "HEAVY_SUBJECTS": {TOAN, TOAN_TC, TV, TV_TC, TIENG_ANH, KH, TIN_HOC},
    "HEAVY_LATE_PERIODS": {7},
    # Buổi sáng dành cho môn chính (mục tiêu mềm).
    "MORNING_SUBJECTS": {TV, TOAN},
    # Môn tăng cường (khóa) tính chung với môn chính (giá trị): liên tiết, số tiết mỗi buổi, ghép cặp, tiết tăng
    # cường đứng sau tiết chính trong ngày.
    "SUBJECT_GROUPS": {TV_TC: TV, TOAN_TC: TOAN},
    # Môn -> số tiết tối đa mỗi ngày (khi số tiết/tuần không quá số ngày học).
    "DAILY_LIMITS": {TOAN: 1},
    # Nhóm môn không xếp thành cặp 2 tiết liền.
    "PAIR_EXCLUDED": {TOAN, HDTN},
}

TRONG: dict[str, object] = {
    "DISPLAY_NAMES": {}, "HDTN": "", "HDTN_FIXED_SLOTS": [], "HDTN_FLEX_DAYS": [], "HOMEROOM_ONLY_SUBJECTS": set(),
    "GENERAL_FORBIDDEN_SUBJECTS": set(), "MANAGER_RULES": [], "HOMEROOM_PRIORITY": [], "HOMEROOM_CUT_ORDER": [],
    "HOMEROOM_FILL_ORDER": [], "HOMEROOM_PERIODS": set(), "HOMEROOM_OVERTIME_SPECIALIST": set(),
    "HEAVY_SUBJECTS": set(), "HEAVY_LATE_PERIODS": set(), "MORNING_SUBJECTS": set(), "SUBJECT_GROUPS": {},
    "DAILY_LIMITS": {}, "PAIR_EXCLUDED": set(),
}
# Khung giờ của bộ Trống: 5 ngày, mỗi ngày buổi Sáng 4 tiết và buổi Chiều 3 tiết (sửa ở bước Khung giờ).
TRONG_FRAME: list[tuple[str, list[tuple[str, int]]]] = [
    (day, [("Sáng", 4), ("Chiều", 3)]) for day in ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6")]
# Các luật có sẵn bộ Trống để bật (khóa trong tkb/luat_co_san.py): theo dữ liệu trường ghi và các ưu tiên chung.
# Các luật có sẵn khác ghi ở sheet LUẬT ở trạng thái Tạm tắt.
TRONG_ON: frozenset[str] = frozenset({"lien_tiet", "buoi_nghi", "co_so", "doi_co_so", "co_so_2", "tai_ngay",
                                      "tai_ngay_1", "rai_deu", "tiet_trong"})

# Các bộ mẫu: khóa -> (tên hiện trên giao diện, giải thích).
PRESETS: dict[str, tuple[str, str]] = {
    "tieu_hoc_vn": ("Tiểu học Việt Nam",
                    "Các môn và quy định của trường tiểu học Việt Nam: GVCN nhận trọn Tiếng Việt, Toán…, HĐTN cố định "
                    "Thứ 2 tiết 1 và Thứ 6 tiết 4, tiết 1 luôn do GVCN dạy, ghép cặp Tiếng Việt, Toán mỗi ngày 1 "
                    "tiết…"),
    "trong": ("Trống",
              "Chưa có môn nào, không theo quy ước của nước nào: các luật có sẵn như ghép cặp, HĐTN, tiết của GVCN "
              "đều Tạm tắt (bật lại ở bước Luật); chỉ bật luật theo buổi nghỉ, cơ sở và các ưu tiên chung."),
}
DEFAULT = "tieu_hoc_vn"
