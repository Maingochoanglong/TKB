"""Xếp thời khóa biểu: chỉ cần sửa các hằng số bên dưới rồi bấm nút Run (▶) để chạy.

Đường dẫn tương đối được tính từ thư mục chứa file main.py này (thư mục dự án).
Trên Windows nên viết đường dẫn dạng r"C:\\Users\\ten\\TKB\\input.xlsx" hoặc "C:/Users/ten/TKB/input.xlsx".
"""
from __future__ import annotations

import sys
from pathlib import Path

# ==========================================================================
# CẤU HÌNH — SỬA Ở ĐÂY
# ==========================================================================

# Địa chỉ file vào: sheet "NHÂN SỰ" (Họ và Tên, Chức Vụ, Lớp, Số Tiết/Tuần) và sheet
# "CHƯƠNG TRÌNH HỌC" (Môn học, Khối 1..5). Danh sách môn, số tiết, giáo viên đều lấy từ file này;
# các file ra dùng lại style (phông, cỡ chữ, viền, chiều cao dòng) của file này.
FILE_VAO = "data/INPUT_V8.xlsx"

# Thư mục ghi kết quả (tự tạo nếu chưa có). Để trống "" thì ghi ngay vào thư mục dự án
# (thư mục chứa main.py).
THU_MUC_OUT = ""

# Khi thiếu người:
#   "bu_gio"    : GVCN và bộ môn dạy bù vượt định mức (GVCN bù trước, ngay ở lớp mình,
#                 môn ưu tiên trước); chỉ khi bù vẫn không đủ mới thêm GV "chưa có".
#   "tuyen_them": thêm GV mới tên "chưa có" vào danh sách nhân sự.
CHE_DO = "bu_gio"

# Chế độ bù giờ: số tiết bù tối đa mỗi GVCN/bộ môn mỗi tuần.
SO_TIET_BU_TOI_DA = 2

# Áp dụng luật bảo vệ học sinh: tối đa 2 tiết Tiếng Việt và 2 tiết Toán mỗi buổi; môn có từ 2 tiết
# trong một buổi thì các tiết phải liền nhau (không xếp so le kiểu TV, Toán, TV).
LUAT_HOC_SINH = True

# Thời gian dành cho bước xếp giờ, đơn vị xấp xỉ giây (240 ≈ 3,5 phút trên máy thử).
# Để trống (None hoặc "") hoặc 0 thì không giới hạn: chạy bao lâu cũng được, đến khi bộ giải chứng
# minh TKB tốt nhất (có thể rất lâu, hàng giờ); muốn dừng sớm thì bấm Ctrl+C, chương trình vẫn ghi
# TKB tốt nhất đã tìm được.
THOI_GIAN_TOI_DA = 240

# True: chạy lại bao nhiêu lần, trên máy nào cùng hệ điều hành cũng ra đúng một kết quả (ở cả chế độ bu_gio lẫn
#       tuyen_them), miễn là giữ nguyên file vào, CHE_DO, SO_TIET_BU_TOI_DA, LUAT_HOC_SINH, THOI_GIAN_TOI_DA,
#       SO_LUONG và phiên bản OR-Tools (cài bằng: pip install -r requirements.txt). Máy nhanh/chậm, số nhân
#       CPU, máy bận/rảnh, phiên bản Python không ảnh hưởng; Windows và Linux ra TKB khác nhau. Mỗi lần chạy
#       in "Mã kết quả": cùng mã là cùng TKB (xem README, mục "Chạy trên máy khác").
# False: dừng đúng theo giây thực, mỗi lần chạy có thể ra TKB khác nhau.
CHAY_TAI_LAP_DUOC = True

# --- Ít khi phải sửa ---

# Tên file xuất ra trong THU_MUC_OUT: FILE_TKB chỉ gồm thời khóa biểu (các sheet Khối); FILE_THONG_KE là một bảng:
# mỗi giáo viên một dòng (tên, chức vụ), số tiết từng môn người đó dạy và tổng số tiết. Mã kết quả, kết quả kiểm
# tra luật, người cần tuyển, dạy bù chỉ in ra màn hình.
FILE_TKB = "TKB.xlsx"
FILE_THONG_KE = "Thong_Ke.xlsx"

# Số luồng tìm kiếm song song của bộ giải (mỗi luồng chạy một chiến lược khác nhau).
# Nên để >= số nhân CPU; 8 chạy tốt trên máy 4 nhân. Đổi số này thì TKB ra sẽ khác
# (vẫn đúng luật) — giữ cố định nếu muốn các lần chạy/các máy cho cùng kết quả.
SO_LUONG = 8

# ==========================================================================

BASE_DIR = Path(__file__).resolve().parent


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _resolve(path: str | Path | None) -> Path:
    """Đường dẫn tương đối tính từ thư mục dự án; để trống = chính thư mục dự án."""
    if _blank(path):
        return BASE_DIR
    p = Path(str(path).strip()).expanduser()
    return p if p.is_absolute() else BASE_DIR / p


def run(file_vao: str | Path = FILE_VAO, thu_muc_out: str | Path | None = THU_MUC_OUT,
        file_tkb: str = FILE_TKB, thoi_gian_toi_da: float | None = THOI_GIAN_TOI_DA,
        luat_hoc_sinh: bool = LUAT_HOC_SINH, chay_tai_lap_duoc: bool = CHAY_TAI_LAP_DUOC,
        so_luong: int = SO_LUONG, che_do: str = CHE_DO, so_tiet_bu_toi_da: int = SO_TIET_BU_TOI_DA,
        file_thong_ke: str = FILE_THONG_KE) -> int:
    """Chạy xếp TKB; trả về 0 nếu thành công."""
    try:
        from tkb import config
        from tkb.__main__ import main as tkb_main, use_utf8_output
    except ImportError as exc:
        print(f"LỖI: thiếu thư viện ({exc.name}). Cài bằng lệnh:  pip install -r requirements.txt")
        return 1
    use_utf8_output()

    if _blank(file_vao):
        print("LỖI: chưa điền FILE_VAO (địa chỉ file vào .xlsx)")
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
    limit = 0 if _blank(thoi_gian_toi_da) else thoi_gian_toi_da  # 0 = không giới hạn
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit < 0:
        print(f"LỖI: THOI_GIAN_TOI_DA phải là số giây >= 0, hoặc để trống để không giới hạn "
              f"(đang là {thoi_gian_toi_da!r})")
        return 1

    argv = [str(source), "-o", str(out_dir / file_tkb), "--time-limit", str(limit),
            "--workers", str(so_luong), "--mode", che_do, "--max-overtime", str(so_tiet_bu_toi_da),
            "--stats-out", str(out_dir / file_thong_ke)]
    if not luat_hoc_sinh:
        argv.append("--no-student-rules")
    if not chay_tai_lap_duoc:
        argv.append("--non-reproducible")

    print(f"File vào   : {source}")
    print(f"Thư mục ra : {out_dir}")
    print(f"Chế độ     : {che_do}" + (f" (bù tối đa {so_tiet_bu_toi_da} tiết/người)"
                                     if che_do == config.MODE_OVERTIME else ""))
    print(f"Luật HS    : {'có' if luat_hoc_sinh else 'không'} áp dụng")
    print(f"Thời gian  : {'không giới hạn (Ctrl+C để dừng sớm)' if not limit else f'~{limit} giây'}"
          f"{', kết quả tái lập' if chay_tai_lap_duoc else ''}")
    print(f"Số luồng   : {so_luong}")
    return tkb_main(argv)


if __name__ == "__main__":
    sys.exit(run())
