"""File vào mẫu V8: một file Excel đơn giản, tiếng Việt, style giống file của nhà trường (chữ đen, không tô nền,
viền mảnh). Không cố định dòng/cột, không danh sách thả xuống, không ghi chú trong ô, không sheet ẩn: cách ghi từng
cột nằm ở sheet HƯỚNG DẪN.

- Sheet "NHÂN SỰ": Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy |
  Buổi Nghỉ (5 cột sau không bắt buộc)
  - Chức Vụ: Chủ Nhiệm, Bộ Môn, Quản Lý hoặc tên một môn (GV chuyên biệt, vd "Tiếng Anh"); không ghi số
    thứ tự (chương trình tự đánh số theo thứ tự dòng).
  - Lớp (khối/số thứ tự, vd 1/1, hoặc khối rồi tên lớp, vd 1D15) chỉ ghi cho Chủ Nhiệm.
- Sheet "CHƯƠNG TRÌNH HỌC": Môn học | Khối 1 ... Khối n (số tiết/tuần).
- Các sheet "QUY ĐỊNH CHUNG", "QUY ĐỊNH NGÀY", "QUY ĐỊNH TIẾT", "QUY ĐỊNH MÔN": các luật đang dùng, mỗi quy định
  một cột, mỗi ô ghi Có, Không hoặc số (tkb/rules.py).
- Sheet "HƯỚNG DẪN": cách ghi từng sheet, từng cột.

Chạy:
    python -m tkb.template <file mới.xlsx>    tạo file mẫu trống (các sheet QUY ĐỊNH điền sẵn giá trị mặc định)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from . import config
from .rules import notes as rule_notes, tables as rule_tables
from .staff import Teacher, class_sort_key, normalize, off_text

STAFF_HEADERS = ["Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Thai Sản", "Hợp Đồng", "Cơ sở 2", "Lớp Đang Dạy",
                 "Buổi Nghỉ"]
STAFF_WIDTHS = (34, 16, 8, 17, 12, 12, 11, 26, 24)
RULE_KEY_WIDTHS = (44, 10, 10, 28)  # cột đầu của các sheet quy định: Quy định, Ngày, Tiết, Môn học
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
                 "cách nhau bằng dấu phẩy. GVCN không nghỉ buổi sáng được (tiết Luôn do GVCN dạy ở sheet QUY ĐỊNH "
                 "TIẾT).",
}
GUIDE = [
    (config.STAFF_SHEET, "Mỗi giáo viên một dòng. Năm cột Thai Sản, Hợp Đồng, Cơ sở 2, Lớp Đang Dạy, Buổi Nghỉ "
                         "không bắt buộc (để trống hoặc xóa cột)."),
    *((f"{config.STAFF_SHEET}: {head}", note) for head, note in NOTES.items()),
    (config.PROGRAM_SHEET, "Mỗi môn một dòng: cột Môn học ghi tên môn, cột Khối k ghi số tiết/tuần của môn ở khối k "
                           "(0 hoặc để trống: khối đó không học). Dùng lại đúng tên môn này ở cột Chức Vụ và sheet "
                           f"{config.RULES_SHEETS[3]}."),
    ("Các sheet QUY ĐỊNH", "Các luật nghiệp vụ, mỗi quy định một cột (sheet QUY ĐỊNH CHUNG: một dòng). Mỗi ô chỉ ghi "
                           "Có, Không hoặc một số nguyên dương; ô trống là Không. Riêng cột Tên trong TKB ghi chữ. Xóa "
                           "một cột (một dòng của sheet chung, hoặc cả sheet) thì quy định đó dùng giá trị mặc định "
                           "của chương trình."),
    (config.RULES_SHEETS[0], "Mỗi dòng một quy định, ghi ở cột Giá trị; cột Ghi chú giải thích."),
    (config.RULES_SHEETS[1], "Mỗi ngày Thứ 2 … Thứ 7 một dòng."),
    (config.RULES_SHEETS[2], "Mỗi tiết một dòng; buổi chiều đánh số nối tiếp buổi sáng (sáng 4 tiết thì chiều từ tiết "
                             "5). Thêm tiết thì thêm dòng."),
    (config.RULES_SHEETS[3], "Mỗi môn một dòng, tên như trong sheet CHƯƠNG TRÌNH HỌC (không phân biệt hoa thường). "
                             "Môn không có dòng thì mọi cột là Không."),
    *rule_notes(),
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


def write_rules_sheets(wb, subjects=(), index: int | None = None) -> None:
    """Các sheet quy định (tkb/rules.py) ghi các luật đang dùng, từ vị trí `index`; sheet nào file đã có thì giữ
    nguyên. `subjects`: các môn của chương trình học, tên như trong file vào (dòng của sheet QUY ĐỊNH MÔN)."""
    for (name, headers, rows), key_width in zip(rule_tables(subjects), RULE_KEY_WIDTHS):
        if any(normalize(ws.title) == normalize(name) for ws in wb.worksheets):
            continue
        ws = wb.create_sheet(name, index)
        index = None if index is None else index + 1
        ws.append(headers)
        for row in rows:
            ws.append(row)
        general = name == config.RULES_SHEETS[0]
        _style_rows(ws, 1, 1, len(headers), header=True)
        _style_rows(ws, 2, len(rows) + 1, len(headers), left=(1, 3) if general else (1,))
        widths = (key_width, 10, 110) if general else (key_width, *(max(10, len(h) + 4) for h in headers[1:]))
        _widths(ws, widths)


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
    """Ghi file vào mẫu V8: sheet NHÂN SỰ, CHƯƠNG TRÌNH HỌC, các sheet QUY ĐỊNH (các luật đang dùng) và HƯỚNG
    DẪN."""
    teachers = list(teachers)
    wb = openpyxl.Workbook()
    _staff_sheet(wb, teachers)
    _program_sheet(wb, curriculum, teachers)
    write_rules_sheets(wb, list(dict.fromkeys(s for g in sorted(curriculum or {}) for s in curriculum[g])))
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
