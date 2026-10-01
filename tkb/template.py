"""File vào mẫu V8: một file Excel đơn giản, tiếng Việt, style giống file của nhà trường (chữ đen, không tô nền,
viền mảnh). Không cố định dòng/cột, không danh sách thả xuống, không ghi chú trong ô, không sheet ẩn: cách ghi từng
cột nằm ở sheet HƯỚNG DẪN.

- Sheet "NHÂN SỰ": Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy |
  Buổi Nghỉ (5 cột sau không bắt buộc)
  - Chức Vụ: Chủ Nhiệm, Bộ Môn, Quản Lý hoặc tên một môn (GV chuyên biệt, vd "Tiếng Anh"); không ghi số
    thứ tự (chương trình tự đánh số theo thứ tự dòng).
  - Lớp (khối/số thứ tự, vd 1/1, hoặc khối rồi tên lớp, vd 1D15) chỉ ghi cho Chủ Nhiệm.
- Sheet "CHƯƠNG TRÌNH HỌC": Môn học | Khối 1 ... Khối n (số tiết/tuần).
- Sheet "QUY ĐỊNH": Quy định | Giá trị | Ghi chú, điền sẵn các luật đang dùng (tkb/rules.py).
- Sheet "HƯỚNG DẪN": cách ghi từng sheet, từng cột.

Chạy:
    python -m tkb.template <file mới.xlsx>    tạo file mẫu trống (sheet QUY ĐỊNH điền sẵn giá trị mặc định)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from . import config
from .program import canonical_subject
from .rules import HEADERS as RULE_HEADERS, rule_rows
from .staff import Teacher, class_sort_key, off_text

STAFF_HEADERS = ["Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Thai Sản", "Hợp Đồng", "Cơ sở 2", "Lớp Đang Dạy",
                 "Buổi Nghỉ"]
STAFF_WIDTHS = (34, 16, 8, 17, 12, 12, 11, 26, 24)
RULE_WIDTHS = (44, 60, 100)
GUIDE_SHEET = "HƯỚNG DẪN"
GUIDE_HEADERS = ("Mục", "Cách ghi")
GUIDE_WIDTHS = (36, 160)
YES = "Có"
LAST_ROW = 300  # các ô Lớp, Lớp Đang Dạy đến dòng này để dạng chữ (Excel không đổi "1/1" thành ngày tháng)
BLANK_ROWS = 10  # số dòng trống kẻ sẵn dưới danh sách
BLANK_GRADES = (1, 2, 3, 4, 5)  # các cột Khối của file mẫu trống
# Style của file vào nhà trường: Times New Roman 14 chữ đen, tiêu đề in đậm, không tô nền, viền mảnh, căn giữa,
# dòng cao 25. Các file ra chép lại style của file vào (tkb/style.py).
BLACK = "FF000000"
FONT = Font(name="Times New Roman", size=14, color=BLACK)
HEADER_FONT = Font(name="Times New Roman", size=14, bold=True, color=BLACK)
THIN = Side(style="thin")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")
ROW_HEIGHT = 25

NOTES = {
    "Họ và Tên": "Tên giáo viên; người chưa tuyển được ghi \"chưa có\".",
    "Chức Vụ": "Chủ Nhiệm, Bộ Môn, Quản Lý hoặc tên một môn trong sheet CHƯƠNG TRÌNH HỌC (GV chuyên biệt). "
               "Không ghi số thứ tự: chương trình tự đánh số theo thứ tự dòng.",
    "Lớp": "Chỉ ghi cho Chủ Nhiệm, dạng khối/số thứ tự (vd 1/1) hoặc khối rồi tên lớp (vd 1D15). Mỗi lớp một "
           "Chủ Nhiệm.",
    "Số Tiết/Tuần": "Số tiết tối đa mỗi tuần (số nguyên).",
    "Thai Sản": "Ghi Có nếu đang hưởng chế độ thai sản: không dạy bù, chỉ dạy các lớp ở cơ sở 2.",
    "Hợp Đồng": "Ghi Có nếu là GV hợp đồng: khi phải bù, GVCN hợp đồng bù trước GVCN khác, bộ môn hợp đồng "
                "bù trước bộ môn khác.",
    "Cơ sở 2": "Dòng Chủ Nhiệm: ghi Có nếu lớp học ở cơ sở 2. Dòng khác: ghi Có nếu GV chỉ dạy ở cơ sở 2. "
               "Mỗi buổi, một GV chỉ dạy ở một cơ sở.",
    "Lớp Đang Dạy": "GV bộ môn, chuyên biệt: các lớp đang dạy trong TKB cũ, cách nhau bằng dấu phẩy (vd 3D17, "
                    "3D18). TKB mới ưu tiên giữ khối, rồi giữ lớp.",
    "Buổi Nghỉ": "Buổi không xếp tiết: buổi cố định (vd Chiều T5, Sáng T6) hoặc số buổi bất kỳ (vd 2 buổi chiều), "
                 "cách nhau bằng dấu phẩy. GVCN không nghỉ buổi sáng được (tiết luôn do GVCN dạy ở sheet QUY ĐỊNH).",
}
GUIDE = [
    (config.STAFF_SHEET, "Mỗi giáo viên một dòng. Năm cột Thai Sản, Hợp Đồng, Cơ sở 2, Lớp Đang Dạy, Buổi Nghỉ "
                         "không bắt buộc (để trống hoặc xóa cột)."),
    *((f"{config.STAFF_SHEET}: {head}", note) for head, note in NOTES.items()),
    (config.PROGRAM_SHEET, "Mỗi môn một dòng: cột Môn học ghi tên môn, cột Khối k ghi số tiết/tuần của môn ở khối k "
                           "(0 hoặc để trống: khối đó không học). Dùng lại đúng tên môn này ở cột Chức Vụ và sheet "
                           f"{config.RULES_SHEET}."),
    (config.RULES_SHEET, "Các luật nghiệp vụ, mỗi dòng một quy định: chỉ sửa cột Giá trị, cột Ghi chú giải thích. "
                         "Xóa một dòng thì chương trình dùng giá trị mặc định của quy định đó; không có sheet này "
                         "thì mọi quy định dùng giá trị mặc định."),
    (f"{config.RULES_SHEET}: tên môn", "Ghi như trong sheet CHƯƠNG TRÌNH HỌC (không phân biệt hoa thường); nhiều "
                                       "môn cách nhau bằng dấu phẩy; để trống là không có môn nào."),
    (f"{config.RULES_SHEET}: ngày, tiết", "Ngày ghi Thứ 2 … Thứ 7. Tiết ghi số: buổi sáng từ tiết 1, buổi chiều nối "
                                          "tiếp buổi sáng (sáng 4 tiết thì chiều từ tiết 5). Ô cố định ghi dạng "
                                          "Thứ 2 tiết 1."),
    ("Kiểu chữ", "Các file kết quả chép kiểu chữ, cỡ chữ, viền của sheet NHÂN SỰ. Chỉ cần chữ và số: không cần "
                 "công thức, màu nền, ghi chú trong ô hay danh sách thả xuống."),
]


def role_label(t: Teacher) -> str:
    return t.label or config.ROLE_LABELS.get(t.role) or t.role.title()


def staff_row(t: Teacher) -> list:
    flag = lambda on: YES if on else None
    history = ", ".join(sorted(t.history, key=class_sort_key)) or None
    return [t.name or None, role_label(t), t.class_name, t.max_lessons, flag(t.maternity), flag(t.contract),
            flag(t.campus2), history, off_text(t) or None]


def _style_rows(ws, first: int, last: int, n_cols: int, header: bool = False, left: tuple[int, ...] = ()) -> None:
    """Kẻ bảng: chữ đen Times New Roman 14 (tiêu đề in đậm), viền mảnh, không tô nền; cột trong `left` căn trái."""
    for r in range(first, last + 1):
        ws.row_dimensions[r].height = ROW_HEIGHT
        for c in range(1, n_cols + 1):
            cell = ws.cell(r, c)
            cell.font = HEADER_FONT if header else FONT
            cell.border = BORDER
            cell.alignment = LEFT if c in left and not header else CENTER


def _widths(ws, widths) -> None:
    for c, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = width


def _staff_sheet(wb, teachers: list[Teacher]) -> None:
    ws = wb.active
    ws.title = config.STAFF_SHEET
    ws.append(STAFF_HEADERS)
    for t in teachers:
        ws.append(staff_row(t))
    _style_rows(ws, 1, 1, len(STAFF_HEADERS), header=True)
    _style_rows(ws, 2, len(teachers) + 1 + BLANK_ROWS, len(STAFF_HEADERS), left=(1,))
    for r in range(2, LAST_ROW + 1):
        for c in (3, 8):  # Lớp, Lớp Đang Dạy là chữ, để Excel không đổi "1/1" thành ngày tháng
            ws.cell(r, c).number_format = "@"
    _widths(ws, STAFF_WIDTHS)


def _program_sheet(wb, curriculum: dict[int, dict[str, int]] | None, teachers: list[Teacher]) -> None:
    ws = wb.create_sheet(config.PROGRAM_SHEET)
    grades = (sorted(curriculum) if curriculum
              else sorted({t.grade for t in teachers if t.grade}) or list(BLANK_GRADES))
    ws.append(["Môn học", *[f"Khối {g}" for g in grades]])
    subjects = list(dict.fromkeys(s for g in grades for s in (curriculum or {}).get(g, {})))
    for s in subjects:
        ws.append([s, *[curriculum[g].get(s, 0) for g in grades]])
    n_cols = 1 + len(grades)
    _style_rows(ws, 1, 1, n_cols, header=True)
    _style_rows(ws, 2, len(subjects) + 1 + (0 if subjects else BLANK_ROWS), n_cols)
    _widths(ws, (28, *[10] * len(grades)))


def write_rules_sheet(wb, subjects=(), index: int | None = None) -> None:
    """Sheet QUY ĐỊNH (Quy định | Giá trị | Ghi chú) ghi các luật đang dùng (tkb/rules.py) ở vị trí `index`; tên và
    thứ tự môn như `subjects` (các môn của chương trình học, tên như trong file vào)."""
    names = {canonical_subject(s): s for s in subjects}
    rows = rule_rows(label=lambda s: names.get(s, s), order=list(names))
    ws = wb.create_sheet(config.RULES_SHEET, index)
    ws.append(list(RULE_HEADERS))
    for row in rows:
        ws.append(list(row))
    _style_rows(ws, 1, 1, len(RULE_HEADERS), header=True)
    _style_rows(ws, 2, len(rows) + 1, len(RULE_HEADERS), left=(1, 2, 3))
    _widths(ws, RULE_WIDTHS)


def _guide_sheet(wb) -> None:
    ws = wb.create_sheet(GUIDE_SHEET)
    ws.append(list(GUIDE_HEADERS))
    for row in GUIDE:
        ws.append(list(row))
    _style_rows(ws, 1, 1, len(GUIDE_HEADERS), header=True)
    _style_rows(ws, 2, len(GUIDE) + 1, len(GUIDE_HEADERS), left=(1, 2))
    _widths(ws, GUIDE_WIDTHS)


def write_staff_template(path: str | Path, teachers: list[Teacher] = (),
                         curriculum: dict[int, dict[str, int]] | None = None) -> None:
    """Ghi file vào mẫu V8: sheet NHÂN SỰ, CHƯƠNG TRÌNH HỌC, QUY ĐỊNH (các luật đang dùng) và HƯỚNG DẪN."""
    teachers = list(teachers)
    wb = openpyxl.Workbook()
    _staff_sheet(wb, teachers)
    _program_sheet(wb, curriculum, teachers)
    write_rules_sheet(wb, [s for g in sorted(curriculum or {}) for s in curriculum[g]])
    _guide_sheet(wb)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tkb.template",
                                 description="Tạo file vào mẫu V8 trống (nhân sự, chương trình học, quy định)")
    ap.add_argument("output", help="File mẫu cần tạo (.xlsx)")
    args = ap.parse_args(argv)
    write_staff_template(args.output)
    print(f"Đã ghi: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
