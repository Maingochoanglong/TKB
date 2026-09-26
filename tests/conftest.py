from pathlib import Path

import pytest

from tkb.program import read_program
from tkb.staff import build_teacher, read_staff

DATA = Path(__file__).resolve().parent.parent / "data"
INPUT_FILE = DATA / "Input_TKB_V8.xlsx"  # file vào mẫu V8, tên giả: sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC
# Chương trình học dùng trong test: đọc từ file, không có trong code.
CURRICULUM = read_program(INPUT_FILE)


@pytest.fixture(scope="session")
def sample_staff():
    """Nhân sự đủ 29 lớp của file mẫu (tên giả)."""
    return read_staff(INPUT_FILE)


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
