from pathlib import Path

import pytest

from tkb.program import read_program
from tkb.staff import build_teacher, read_staff

DATA = Path(__file__).resolve().parent.parent / "data"
STAFF_FILE = DATA / "Input_Danh_Sach_Nhan_Su_V5.xlsx"  # định dạng cũ: "ts" sau chức vụ
INPUT_FILE = DATA / "Input_TKB_V8.xlsx"  # file vào hiện tại: sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC
PROGRAM_FILE = DATA / "Input_Chuong_Trinh_Hoc_V5.xlsx"
# Chương trình học dùng trong test: đọc từ file, không có trong code.
CURRICULUM = read_program(PROGRAM_FILE)


@pytest.fixture(scope="session")
def real_staff():
    return read_staff(STAFF_FILE)


def small_staff(general: bool = True):
    """Trường nhỏ: 2 lớp Khối 3 và đủ GV chuyên biệt."""
    rows = [
        ("CN A", "chủ nhiệm 3/1", 19),
        ("CN B", "chủ nhiệm 3/2", 19),
        ("TA", "tiếng anh 1", 23),
        ("TD", "thể dục 1", 23),
        ("AN", "âm nhạc 1", 23),
        ("MT", "mỹ thuật 1", 23),
        ("TH", "tin học 1", 23),
    ]
    if general:
        rows.append(("BM", "bộ môn 1", 23))
    return [build_teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
