"""File vào mẫu V8: một file Excel đơn giản, tiếng Việt, style giống file của nhà trường (chữ đen, không tô nền,
viền mảnh). Không cố định dòng/cột, không danh sách thả xuống, không ghi chú trong ô, không sheet ẩn: cách ghi từng
cột nằm ở sheet HƯỚNG DẪN.

- Sheet "NHÂN SỰ": Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy |
  Buổi Nghỉ (5 cột sau không bắt buộc)
  - Chức Vụ: Chủ Nhiệm, Bộ Môn, Quản Lý, một chức vụ của sheet CHỨC VỤ hoặc tên một môn (GV chuyên biệt, vd
    "Tiếng Anh"); không ghi số thứ tự (chương trình tự đánh số theo thứ tự dòng).
  - Lớp (khối/số thứ tự, vd 1/1, hoặc khối rồi tên lớp, vd 1D15) chỉ ghi cho Chủ Nhiệm.
- Sheet "CHƯƠNG TRÌNH HỌC": Môn học | Khối 1 ... Khối n (số tiết/tuần) | các cột quy định của môn (Có, Không
  hoặc số; tkb/rules.py).
- Sheet "CHỨC VỤ": Chức vụ | Môn được dạy: các chức vụ GV chuyên biệt nhà trường tự đặt (không bắt buộc).
- Sheet "QUY ĐỊNH": ba bảng (quy định chung, ngày, tiết), mỗi ô ghi Có, Không hoặc số.
- Sheet "LUẬT": mọi luật xếp TKB, mỗi dòng một câu của bộ ghép luật; ghi sẵn các luật có sẵn (tkb/luat_co_san.py).
- Sheet "HƯỚNG DẪN": cách ghi từng sheet, từng cột.

Chạy:
    python -m tkb.template <file mới.xlsx>    tạo file mẫu trống (các môn và quy định điền sẵn giá trị mặc định,
                                              số tiết để trống)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from . import config
from . import luat_rieng
from .rules import (ROLE_NAME, ROLE_SUBJECTS, default_subjects, luat_headers, luat_rows,
                    notes as rule_notes, role_rows,
                    rule_tables, subject_columns)
from .staff import Teacher, class_sort_key, off_text

STAFF_HEADERS = ["Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Thai Sản", "Hợp Đồng", "Cơ sở 2", "Lớp Đang Dạy",
                 "Buổi Nghỉ"]
STAFF_WIDTHS = (34, 16, 8, 17, 12, 12, 11, 26, 24)
RULES_WIDTHS = (40, 16, 16, 20, 24)  # sheet QUY ĐỊNH: cột đầu (Quy định, Ngày, Tiết) và các cột giá trị
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
    "Chức Vụ": "Chủ Nhiệm, Bộ Môn, Quản Lý, một chức vụ của sheet CHỨC VỤ hoặc tên một môn trong sheet CHƯƠNG "
               "TRÌNH HỌC (GV chuyên biệt). Không ghi số thứ tự: chương trình tự đánh số theo thứ tự dòng.",
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
                 "cách nhau bằng dấu phẩy. GVCN không nghỉ được buổi có tiết Luôn do GVCN dạy (sheet QUY ĐỊNH).",
}
GUIDE = [
    (config.STAFF_SHEET, "Mỗi giáo viên một dòng. Năm cột Thai Sản, Hợp Đồng, Cơ sở 2, Lớp Đang Dạy, Buổi Nghỉ "
                         "không bắt buộc (để trống hoặc xóa cột)."),
    *((f"{config.STAFF_SHEET}: {head}", note) for head, note in NOTES.items()),
    (config.PROGRAM_SHEET, "Mỗi môn một dòng: cột Môn học ghi tên môn (dùng đúng tên này ở sheet CHỨC VỤ, hoặc ở cột "
                           "Chức Vụ của GV chuyên biệt chỉ dạy môn này), cột Khối k ghi số tiết/tuần của môn ở khối k "
                           "(0 hoặc để trống: khối đó không học), các cột sau là quy định của môn."),
    ("Quy ước các ô quy định", "Mỗi quy định là một cột (bảng Quy định chung: một dòng). Mỗi ô chỉ ghi Có, Không hoặc "
                               "một số nguyên dương; ô trống là Không. Riêng cột Tên trong TKB ghi chữ. Xóa một cột "
                               "(một dòng của bảng chung, một bảng, hoặc cả sheet QUY ĐỊNH) thì quy định đó dùng giá "
                               "trị mặc định của chương trình."),
    (config.RULES_SHEET, "Ba bảng cách nhau một dòng trống: Quy định | Giá trị; Ngày (mỗi dòng một ngày học, mỗi cột "
                         "Buổi <tên> ghi số tiết của buổi đó); Tiết (đánh số liên tục trong ngày: sáng 4 tiết thì chiều "
                         "từ tiết 5; ngày dài nhất có bao nhiêu tiết thì bấy nhiêu dòng)."),
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


def _staff_sheet(wb, rows: list[list]) -> None:
    """Sheet NHÂN SỰ: mỗi dòng các giá trị theo STAFF_HEADERS (vd `staff_row`)."""
    ws = wb.active
    ws.title = config.STAFF_SHEET
    ws.append(STAFF_HEADERS)
    for row in rows:
        ws.append(row)
    _style_rows(ws, 1, 1, len(STAFF_HEADERS), header=True)
    _style_rows(ws, 2, len(rows) + 1 + BLANK_ROWS, len(STAFF_HEADERS), left=(1,))
    for r in range(2, LAST_ROW + 1):
        for c in (3, 8):  # Lớp, Lớp Đang Dạy là chữ, để Excel không đổi "1/1" thành ngày tháng
            ws.cell(r, c).number_format = "@"
    _widths(ws, STAFF_WIDTHS)


def program_rows(curriculum: dict[int, dict[str, int]] | None, teachers: list[Teacher] = ()):
    """Bảng CHƯƠNG TRÌNH HỌC: các môn của `curriculum` (không có thì các môn có quy định mặc định, số tiết để trống)
    với số tiết từng khối và các cột quy định của môn theo các luật đang dùng: (các khối, tiêu đề cột quy định, các
    dòng)."""
    grades = (sorted(curriculum) if curriculum
              else sorted({t.grade for t in teachers if t.grade}) or list(BLANK_GRADES))
    subjects = list(dict.fromkeys(s for g in grades for s in (curriculum or {}).get(g, {})))
    heads, rules, _ = subject_columns(subjects or default_subjects())
    rows = [[s, *([curriculum[g].get(s, 0) for g in grades] if s in subjects else [None] * len(grades)), *values]
            for s, values in rules.items()]
    return grades, heads, rows


def _program_sheet(wb, grades, heads, rows: list[list]) -> None:
    """Sheet CHƯƠNG TRÌNH HỌC: Môn học | Khối ... | các cột quy định `heads`; mỗi dòng một môn."""
    ws = wb.create_sheet(config.PROGRAM_SHEET)
    ws.append(["Môn học", *[f"Khối {g}" for g in grades], *heads])
    for row in rows:
        ws.append(row)
    n_cols = 1 + len(grades) + len(heads)
    _style_rows(ws, 1, 1, n_cols, header=True)
    _style_rows(ws, 2, len(rows) + 1 + BLANK_ROWS, n_cols, left=(1,))
    _widths(ws, (28, *[10] * len(grades), *(max(10, len(h) + 4) for h in heads)))


def write_rules_sheet(wb, index: int | None = None, tables=None) -> None:
    """Sheet QUY ĐỊNH ở vị trí `index`: ba bảng (quy định chung, ngày, tiết), cách nhau một dòng trống. `tables`:
    [(tiêu đề, các dòng)] như `rules.rule_tables`; không có thì lấy theo các luật đang dùng."""
    ws = wb.create_sheet(config.RULES_SHEET, index)
    r = 1
    for headers, rows in tables or rule_tables():
        for c, value in enumerate(headers, start=1):
            ws.cell(r, c, value)
        for i, row in enumerate(rows, start=1):
            for c, value in enumerate(row, start=1):
                ws.cell(r + i, c, value)
        _style_rows(ws, r, r, len(headers), header=True)
        _style_rows(ws, r + 1, r + len(rows), len(headers), left=(1,))
        r += len(rows) + 2
    _widths(ws, RULES_WIDTHS)


def write_roles_sheet(wb, rows: list[list] | None = None, index: int | None = None) -> None:
    """Sheet CHỨC VỤ ở vị trí `index`: Chức vụ | Môn được dạy, các dòng `rows` (không có thì theo các chức vụ đang
    dùng), kẻ sẵn vài dòng trống để nhà trường điền."""
    rows = role_rows() if rows is None else rows
    ws = wb.create_sheet(config.ROLES_SHEET, index)
    ws.append([ROLE_NAME, ROLE_SUBJECTS])
    for row in rows:
        ws.append(row)
    _style_rows(ws, 1, 1, 2, header=True)
    _style_rows(ws, 2, len(rows) + 1 + BLANK_ROWS, 2, left=(1, 2))
    _widths(ws, (30, 60))


def write_luat_sheet(wb, rows: list[list] | None = None, index: int | None = None) -> None:
    """Sheet LUẬT ở vị trí `index`: tiêu đề và các dòng luật (không có thì theo các luật đang dùng, kể cả luật có
    sẵn), kẻ sẵn vài dòng trống để nhà trường thêm luật."""
    rows = luat_rows() if rows is None else rows
    ws = wb.create_sheet(luat_rieng.RULES_SHEET, index)
    headers = luat_headers()
    ws.append(headers)
    for row in rows:
        ws.append(row)
    _style_rows(ws, 1, 1, len(headers), header=True)
    _style_rows(ws, 2, len(rows) + 1 + BLANK_ROWS, len(headers), left=(1, 2, 3, len(headers)))
    _widths(ws, (18, 22, 16, 18, 10, 22, 16, 8, 10, 12, 8, 8, 16, 12, 14, 10, 10, 14, 12, 9, 6, 8, 70))


def write_guide(wb, extra=(), index: int | None = None) -> None:
    """Sheet HƯỚNG DẪN: cách ghi từng sheet, từng cột, rồi các dòng `extra` (vd giải thích kết quả)."""
    rows = [*GUIDE, *extra]
    ws = wb.create_sheet(GUIDE_SHEET, index)
    ws.append(list(GUIDE_HEADERS))
    for row in rows:
        ws.append(list(row))
    _style_rows(ws, 1, 1, len(GUIDE_HEADERS), header=True)
    _style_rows(ws, 2, len(rows) + 1, len(GUIDE_HEADERS), left=(1, 2))
    _widths(ws, GUIDE_WIDTHS)


def write_input(path: str | Path, staff: list[list], program: tuple, tables=None, extra=None,
                rules: list[list] | None = None, roles: list[list] | None = None) -> None:
    """Ghi file vào V8 từ các dòng có sẵn: NHÂN SỰ (`staff`: các dòng theo STAFF_HEADERS), CHƯƠNG TRÌNH HỌC
    (`program`: (các khối, tiêu đề cột quy định, các dòng) như `program_rows`), CHỨC VỤ (`roles`: các dòng), QUY ĐỊNH
    (`tables` như `rules.rule_tables`), LUẬT (`rules`: các dòng như `rules.luat_rows`), HƯỚNG DẪN; phần nào không có
    thì theo các quy định đang dùng. `extra(wb)` ghi thêm sheet nếu cần."""
    wb = openpyxl.Workbook()
    _staff_sheet(wb, staff)
    _program_sheet(wb, *program)
    write_roles_sheet(wb, roles)
    write_rules_sheet(wb, tables=tables)
    write_luat_sheet(wb, rules)
    write_guide(wb)
    if extra is not None:
        extra(wb)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_staff_template(path: str | Path, teachers: list[Teacher] = (),
                         curriculum: dict[int, dict[str, int]] | None = None) -> None:
    """Ghi file vào mẫu V8: sheet NHÂN SỰ, CHƯƠNG TRÌNH HỌC (kèm các cột quy định của môn), CHỨC VỤ, QUY ĐỊNH, LUẬT
    (mọi luật, kể cả luật có sẵn) và HƯỚNG DẪN."""
    teachers = list(teachers)
    write_input(path, [staff_row(t) for t in teachers], program_rows(curriculum, teachers))


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
