"""Xếp thời khóa biểu: chỉ cần sửa các hằng số bên dưới rồi bấm nút Run (▶) để chạy.

Đường dẫn tương đối được tính từ thư mục chứa file main.py này.
Trên Windows nên viết đường dẫn dạng r"C:\\Users\\ten\\TKB\\in" hoặc "C:/Users/ten/TKB/in".
"""
from __future__ import annotations

import sys
from pathlib import Path

# ==========================================================================
# CẤU HÌNH — SỬA Ở ĐÂY
# ==========================================================================

# Thư mục chứa file đầu vào.
THU_MUC_IN = "data"

# Thư mục ghi kết quả (tự tạo nếu chưa có).
THU_MUC_OUT = "out"

# Tên file danh sách nhân sự (cột Tên, Chức vụ, Số tiết) nằm trong THU_MUC_IN.
FILE_NHAN_SU = "Input_Danh_Sach_Nhan_Su_V5.xlsx"

# Tên file chương trình học trong THU_MUC_IN (cột Môn học, Khối 1..5).
# Để None thì dùng chương trình mặc định trong tkb/config.py.
FILE_CHUONG_TRINH = None

# Tên file TKB xuất ra trong THU_MUC_OUT.
FILE_TKB = "TKB.xlsx"

# Lượng tính toán dành cho bước xếp giờ, đơn vị xấp xỉ giây (240 ≈ 3,5 phút trên máy thử).
# Tăng lên nếu muốn TKB đẹp hơn. Khi CHAY_TAI_LAP_DUOC = True, máy chậm sẽ chạy lâu hơn
# nhưng kết quả không đổi.
THOI_GIAN_TOI_DA = 240

# True: cùng dữ liệu thì lần chạy nào cũng ra đúng một TKB.
# False: dừng đúng theo giây thực, mỗi lần chạy có thể ra TKB khác nhau.
CHAY_TAI_LAP_DUOC = True

# Bật luật bảo vệ học sinh (không môn nặng tiết 7, tối đa 2 tiết TV/Toán mỗi buổi...).
LUAT_HOC_SINH = True

# Dừng lại chờ nhấn Enter khi chạy xong (hữu ích khi mở bằng cách nhấp đúp file).
CHO_NHAN_ENTER_KHI_XONG = False

# ==========================================================================

BASE_DIR = Path(__file__).resolve().parent


def _resolve(path: str | Path) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else BASE_DIR / p


def run(thu_muc_in: str | Path = THU_MUC_IN, thu_muc_out: str | Path = THU_MUC_OUT,
        file_nhan_su: str = FILE_NHAN_SU, file_chuong_trinh: str | None = FILE_CHUONG_TRINH,
        file_tkb: str = FILE_TKB, thoi_gian_toi_da: float = THOI_GIAN_TOI_DA,
        luat_hoc_sinh: bool = LUAT_HOC_SINH, chay_tai_lap_duoc: bool = CHAY_TAI_LAP_DUOC) -> int:
    """Chạy xếp TKB; trả về 0 nếu thành công."""
    try:
        from tkb.__main__ import main as tkb_main
    except ImportError as exc:
        print(f"LỖI: thiếu thư viện ({exc.name}). Cài bằng lệnh:  pip install -r requirements.txt")
        return 1

    in_dir = _resolve(thu_muc_in)
    out_dir = _resolve(thu_muc_out)
    staff = in_dir / file_nhan_su
    if not staff.is_file():
        found = sorted(p.name for p in in_dir.glob("*.xlsx")) if in_dir.is_dir() else []
        print(f"LỖI: không tìm thấy file nhân sự: {staff}")
        if not in_dir.is_dir():
            print(f"  Thư mục THU_MUC_IN không tồn tại: {in_dir}")
        elif found:
            print("  Các file .xlsx có trong THU_MUC_IN: " + ", ".join(found))
        return 1

    argv = [str(staff), "-o", str(out_dir / file_tkb), "--time-limit", str(thoi_gian_toi_da)]
    if file_chuong_trinh:
        program = in_dir / file_chuong_trinh
        if not program.is_file():
            print(f"LỖI: không tìm thấy file chương trình học: {program}")
            return 1
        argv += ["--program", str(program)]
    if not luat_hoc_sinh:
        argv.append("--no-student-rules")
    if not chay_tai_lap_duoc:
        argv.append("--non-reproducible")

    print(f"Thư mục vào: {in_dir}")
    print(f"Thư mục ra : {out_dir}")
    return tkb_main(argv)


if __name__ == "__main__":
    code = run()
    if CHO_NHAN_ENTER_KHI_XONG:
        input("Nhấn Enter để thoát...")
    sys.exit(code)
