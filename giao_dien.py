"""Mở giao diện web xếp thời khóa biểu: bấm nút Run (▶) để chạy, trình duyệt tự mở trang nhập liệu.

Trên trang: nhập hoặc mở file Excel (nhân sự, chương trình học, quy định), bấm Kiểm tra, rồi Xếp TKB. Giữ cửa sổ
chạy chương trình mở trong khi dùng trang; tắt bằng Ctrl+C hoặc đóng cửa sổ. Dòng lệnh: python -m tkb.giao_dien
(xem README, mục "Cách 0 — giao diện web").
"""
import sys

if __name__ == "__main__":
    try:
        from tkb.giao_dien.__main__ import main
    except ImportError as exc:
        print(f"LỖI: thiếu thư viện ({exc.name}). Cài bằng lệnh:  pip install -r requirements.txt")
        sys.exit(1)
    sys.exit(main())
