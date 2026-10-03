"""Giao diện web chạy trên máy của trường: nhập kịch bản (nhân sự, chương trình học, quy định), xuất file Excel V8
đầy đủ rồi xếp TKB.

Chạy:  python -m tkb.giao_dien     (hoặc bấm Run ở file giao_dien.py của thư mục dự án)
Trình duyệt tự mở trang http://127.0.0.1:<cổng>/. Máy chủ chỉ nghe trên máy này (127.0.0.1), không cần mạng, tên
giáo viên không rời máy. Trang web (static/) không dùng thư viện ngoài nên chạy được khi không có Internet.

- tkb/kich_ban.py: kịch bản <-> file Excel, kiểm tra và dự toán.
- server.py: máy chủ HTTP (thư viện chuẩn) và việc xếp TKB chạy ở tiến trình con `python -m tkb` (như main.py).
"""
