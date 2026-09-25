"""Xếp thời khóa biểu: chỉ cần sửa các hằng số bên dưới rồi bấm nút Run (▶) để chạy.

Đường dẫn tương đối được tính từ thư mục chứa file main.py này.
Trên Windows nên viết đường dẫn dạng r"C:\\Users\\ten\\TKB\\input.xlsx" hoặc "C:/Users/ten/TKB/input.xlsx".
"""
from __future__ import annotations

import sys
from pathlib import Path

# ==========================================================================
# CẤU HÌNH — SỬA Ở ĐÂY
# ==========================================================================

# File vào duy nhất: sheet "NHÂN SỰ" (Họ và Tên, Chức Vụ, Lớp, Số Tiết/Tuần, Chế độ) và sheet
# "CHƯƠNG TRÌNH HỌC" (Môn học, Khối 1..5). Thiếu sheet chương trình học thì dùng chương trình mặc định.
FILE_VAO = "data/Input_TKB_V8.xlsx"

# Thư mục ghi kết quả (tự tạo nếu chưa có).
THU_MUC_OUT = "out"

# Tên file TKB xuất ra trong THU_MUC_OUT.
FILE_TKB = "TKB.xlsx"

# Tên file thống kê giáo viên (tên, chức vụ, số tiết quy định, số tiết bù) trong THU_MUC_OUT.
FILE_THONG_KE = "Thong_Ke.xlsx"

# Lượng tính toán dành cho bước xếp giờ, đơn vị xấp xỉ giây (240 ≈ 3,5 phút trên máy thử).
# Tăng lên nếu muốn TKB đẹp hơn. Khi CHAY_TAI_LAP_DUOC = True, máy chậm sẽ chạy lâu hơn
# nhưng kết quả không đổi.
THOI_GIAN_TOI_DA = 240

# True: chạy lại bao nhiêu lần cũng ra đúng một TKB (ở cả chế độ tuyen_them lẫn bu_gio), miễn là
#       giữ nguyên file đầu vào, CHE_DO, SO_TIET_BU_TOI_DA, THOI_GIAN_TOI_DA, SO_LUONG và phiên bản
#       OR-Tools (đã ghim trong requirements.txt).
# False: dừng đúng theo giây thực, mỗi lần chạy có thể ra TKB khác nhau.
CHAY_TAI_LAP_DUOC = True

# Số luồng tìm kiếm song song của bộ giải (mỗi luồng chạy một chiến lược khác nhau).
# Nên để >= số nhân CPU; 8 chạy tốt trên máy 4 nhân. Đổi số này thì TKB ra sẽ khác
# (vẫn đúng luật) — giữ cố định nếu muốn các lần chạy/các máy cho cùng kết quả.
SO_LUONG = 8

# Khi thiếu người:
#   "tuyen_them": thêm GV mới tên "chưa có" vào danh sách nhân sự.
#   "bu_gio"    : GVCN và bộ môn dạy bù vượt định mức (GVCN bù trước, ngay ở lớp mình,
#                 môn ưu tiên trước); chỉ khi bù vẫn không đủ mới thêm GV "chưa có".
CHE_DO = "bu_gio"

# Chế độ bù giờ: số tiết bù tối đa mỗi GVCN/bộ môn mỗi tuần.
# Người hưởng thai sản không bao giờ phải bù.
SO_TIET_BU_TOI_DA = 2

# Bật luật bảo vệ học sinh (tối đa 2 tiết Tiếng Việt và 2 tiết Toán mỗi buổi).
LUAT_HOC_SINH = True

# ==========================================================================

BASE_DIR = Path(__file__).resolve().parent


def _resolve(path: str | Path) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else BASE_DIR / p


def run(file_vao: str | Path = FILE_VAO, thu_muc_out: str | Path = THU_MUC_OUT,
        file_tkb: str = FILE_TKB, thoi_gian_toi_da: float = THOI_GIAN_TOI_DA,
        luat_hoc_sinh: bool = LUAT_HOC_SINH, chay_tai_lap_duoc: bool = CHAY_TAI_LAP_DUOC,
        so_luong: int = SO_LUONG, che_do: str = CHE_DO, so_tiet_bu_toi_da: int = SO_TIET_BU_TOI_DA,
        file_thong_ke: str = FILE_THONG_KE) -> int:
    """Chạy xếp TKB; trả về 0 nếu thành công."""
    try:
        from tkb import config
        from tkb.__main__ import main as tkb_main
    except ImportError as exc:
        print(f"LỖI: thiếu thư viện ({exc.name}). Cài bằng lệnh:  pip install -r requirements.txt")
        return 1

    source = _resolve(file_vao)
    out_dir = _resolve(thu_muc_out)
    if not source.is_file():
        folder = source.parent
        found = sorted(p.name for p in folder.glob("*.xlsx")) if folder.is_dir() else []
        print(f"LỖI: không tìm thấy file vào: {source}")
        if not folder.is_dir():
            print(f"  Thư mục không tồn tại: {folder}")
        elif found:
            print(f"  Các file .xlsx có trong {folder}: " + ", ".join(found))
        return 1

    if not isinstance(so_luong, int) or so_luong < 1:
        print(f"LỖI: SO_LUONG phải là số nguyên >= 1 (đang là {so_luong!r})")
        return 1

    if che_do not in config.MODES:
        print(f"LỖI: CHE_DO phải là một trong {', '.join(repr(m) for m in config.MODES)} (đang là {che_do!r})")
        return 1
    if not isinstance(so_tiet_bu_toi_da, int) or so_tiet_bu_toi_da < 0:
        print(f"LỖI: SO_TIET_BU_TOI_DA phải là số nguyên >= 0 (đang là {so_tiet_bu_toi_da!r})")
        return 1

    argv = [str(source), "-o", str(out_dir / file_tkb), "--time-limit", str(thoi_gian_toi_da),
            "--workers", str(so_luong), "--mode", che_do, "--max-overtime", str(so_tiet_bu_toi_da),
            "--stats-out", str(out_dir / file_thong_ke)]
    if not luat_hoc_sinh:
        argv.append("--no-student-rules")
    if not chay_tai_lap_duoc:
        argv.append("--non-reproducible")

    print(f"File vào   : {source}")
    print(f"Thư mục ra : {out_dir}")
    print(f"Số luồng   : {so_luong}")
    print(f"Chế độ     : {che_do}" + (f" (bù tối đa {so_tiet_bu_toi_da} tiết/người)"
                                     if che_do == config.MODE_OVERTIME else ""))
    return tkb_main(argv)


if __name__ == "__main__":
    sys.exit(run())
