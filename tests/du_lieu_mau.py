"""Trường mẫu tên giả dùng cho test, CI và file mẫu đầu ra (thay cho file vào mẫu trước đây).

29 lớp (khối 1–4 mỗi khối 6 lớp, khối 5 có 5 lớp), 45 nhân sự và chương trình học chuẩn 32 tiết/tuần.
Không phải dữ liệu của trường: file vào thật của trường là data/INPUT_V8.xlsx.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from tkb.staff import Teacher, clean_name, make_teacher, normalize
from tkb.template import write_staff_template

_SUBJECTS = ["Tiếng Việt", "Toán", "Hoạt động trải nghiệm", "Khoa học", "Lịch sử - Địa lý", "Đạo đức",
             "Tự nhiên xã hội", "Kỹ năng sống", "Công nghệ", "Toán tăng cường", "Tiếng Việt tăng cường",
             "Tiếng Anh", "Tin học", "Thể dục", "Âm nhạc", "Mỹ thuật"]
_LESSONS = {  # số tiết từng môn theo thứ tự _SUBJECTS
    1: [14, 5, 3, 0, 0, 1, 2, 1, 0, 0, 0, 2, 0, 2, 1, 1],
    2: [10, 5, 3, 0, 0, 1, 2, 1, 0, 2, 2, 2, 0, 2, 1, 1],
    3: [7, 5, 3, 0, 0, 1, 2, 1, 1, 2, 1, 4, 1, 2, 1, 1],
    4: [7, 5, 3, 2, 2, 1, 0, 1, 1, 1, 0, 4, 1, 2, 1, 1],
    5: [7, 5, 3, 2, 2, 1, 0, 1, 1, 1, 0, 4, 1, 2, 1, 1],
}
# {khối: {môn: số tiết}}, như đọc từ sheet CHƯƠNG TRÌNH HỌC.
CURRICULUM: dict[int, dict[str, int]] = {g: dict(zip(_SUBJECTS, n)) for g, n in _LESSONS.items()}

_CLASSES = [f"{g}/{n}" for g in range(1, 6) for n in range(1, 7 if g < 5 else 6)]
# (Họ và Tên, Chức Vụ, Lớp, Số Tiết/Tuần) như sheet NHÂN SỰ; GVCN 5/5 và Bộ Môn 5 có định mức thấp hơn.
STAFF_ROWS: list[tuple[str, str, str | None, int]] = [
    *((f"Giáo viên CN {i}", "Chủ Nhiệm", c, 16 if c == "5/5" else 19) for i, c in enumerate(_CLASSES, start=1)),
    *((f"Giáo viên BM {i}", "Bộ Môn", None, 19 if i == 5 else 23) for i in range(1, 6)),
    *((f"Giáo viên TA {i}", "Tiếng Anh", None, 23) for i in range(1, 5)),
    *((f"Giáo viên TD {i}", "Thể Dục", None, 23) for i in range(1, 4)),
    ("Giáo viên ÂN 1", "Âm Nhạc", None, 23),
    ("Giáo viên MT 1", "Mỹ Thuật", None, 23),
    ("Giáo viên TH 1", "Tin Học", None, 23),
    ("Giáo viên QL 1", "Quản Lý", None, 4),
]


def sample_staff() -> list[Teacher]:
    """Nhân sự của trường mẫu, đánh số trong từng chức vụ theo thứ tự dòng như khi đọc file vào."""
    count: dict[str, int] = defaultdict(int)
    teachers = []
    for row, (name, title, class_name, lessons) in enumerate(STAFF_ROWS, start=2):
        role = normalize(title)
        index = None
        if class_name is None:
            count[role] += 1
            index = count[role]
        teachers.append(make_teacher(name, role, index, class_name, lessons, row=row, label=clean_name(title)))
    return teachers


def write_sample_input(path: str | Path) -> Path:
    """Ghi file vào mẫu V8 của trường mẫu (sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC)."""
    write_staff_template(path, sample_staff(), CURRICULUM)
    return Path(path)
