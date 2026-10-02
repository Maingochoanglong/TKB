import tempfile
from pathlib import Path

import pytest

from tkb.staff import make_teacher, read_staff

from .du_lieu_mau import CURRICULUM, write_sample_input  # noqa: F401  (CURRICULUM: dùng trong các test)

# Các sheet của file vào V8 do chương trình ghi (file mẫu; file vào cập nhật thêm sheet TKB đã xếp).
INPUT_SHEETS = ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC", "CHỨC VỤ", "QUY ĐỊNH", "LUẬT RIÊNG", "HƯỚNG DẪN"]
# File vào mẫu V8 của trường mẫu tên giả (tests/du_lieu_mau.py), ghi vào thư mục tạm mỗi lần chạy test.
INPUT_FILE = write_sample_input(Path(tempfile.mkdtemp(prefix="tkb_test_")) / "Input_Mau_V8.xlsx")


@pytest.fixture(scope="session")
def sample_staff():
    """Nhân sự đủ 29 lớp của trường mẫu (tên giả), đọc từ file vào mẫu."""
    return read_staff(INPUT_FILE)


def teacher(name: str, title: str, lessons, row: int | None = None):
    """GV cho test, chức vụ viết gọn kèm số: "chủ nhiệm 3/1" (lớp chủ nhiệm), "bộ môn 1", "tiếng anh 2"."""
    role, key = title.rsplit(" ", 1)
    if "/" in key:
        return make_teacher(name, role, None, key, lessons, row)
    return make_teacher(name, role, int(key), None, lessons, row)


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
    return [teacher(n, t, s, row=i + 2) for i, (n, t, s) in enumerate(rows)]
