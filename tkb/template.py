"""File vào mẫu V8: một file Excel, hai sheet, style giống file của nhà trường.

- Sheet "NHÂN SỰ": Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Chế Độ
  - Chức Vụ: Chủ Nhiệm, Bộ Môn, Quản Lý hoặc tên một môn (GV chuyên biệt, vd "Tiếng Anh"); không ghi số
    thứ tự (chương trình tự đánh số theo thứ tự dòng).
  - Lớp (khối/số thứ tự, vd 1/1) chỉ ghi cho Chủ Nhiệm.
  - Chế Độ ghi "Có" nếu đang hưởng chế độ thai sản, để trống nếu không.
- Sheet "CHƯƠNG TRÌNH HỌC": Môn học | Khối 1 ... Khối n (số tiết/tuần).

Chạy:
    python -m tkb.template <file mới.xlsx>                  tạo file mẫu trống
    python -m tkb.template <file mới.xlsx> --tu <file cũ>   chuyển file cũ sang file mẫu
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule, Rule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import config
from .program import has_program_sheet, read_program
from .staff import MATERNITY_LABEL, InputError, Teacher, read_staff

LIST_SHEET = "Danh mục"
STAFF_HEADERS = ["Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Chế Độ"]
STAFF_WIDTHS = (34, 16, 8, 17, 11)
LAST_ROW = 300  # số dòng có sẵn danh sách thả xuống
BLANK_ROWS = 10  # số dòng trống kẻ sẵn dưới danh sách
MAX_LESSONS = 40
BLANK_GRADES = (1, 2, 3, 4, 5)  # các cột Khối của file mẫu trống
# Style của file vào nhà trường: Times New Roman 14, tiêu đề in đậm không tô nền, viền mảnh, căn giữa,
# dòng cao 25. Các file ra chép lại style của file vào (tkb/style.py).
FONT = Font(name="Times New Roman", size=14)
HEADER_FONT = Font(name="Times New Roman", size=14, bold=True)
THIN = Side(style="thin")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")
NAME_ALIGN = Alignment(horizontal="left", vertical="center")
ROW_HEIGHT = 25
ERROR_STYLE = DifferentialStyle(fill=PatternFill(bgColor="FFC7CE"), font=Font(color="9C0006"))

NOTES = {
    "Chức Vụ": "Chủ Nhiệm, Bộ Môn, Quản Lý hoặc tên một môn trong sheet CHƯƠNG TRÌNH HỌC (GV chuyên biệt). "
               "Không ghi số thứ tự: chương trình tự đánh số theo thứ tự dòng.",
    "Lớp": "Chỉ ghi cho Chủ Nhiệm, dạng khối/số thứ tự, vd 1/1.",
    "Số Tiết/Tuần": "Số tiết tối đa mỗi tuần (người hưởng thai sản ghi mức đã giảm).",
    "Chế Độ": f"Ghi \"{MATERNITY_LABEL}\" nếu đang hưởng chế độ thai sản; để trống nếu không.",
}


def role_label(t: Teacher) -> str:
    return t.label or config.ROLE_LABELS.get(t.role) or t.role.title()


def role_choices(teachers: list[Teacher] = ()) -> list[str]:
    """Chủ Nhiệm, Bộ Môn, các chức vụ chuyên biệt có trong file cũ, Quản Lý (chỉ để gợi ý)."""
    labels = config.ROLE_LABELS
    specialists = [role_label(t) for t in teachers if t.role not in labels]
    return list(dict.fromkeys([labels[config.ROLE_HOMEROOM], labels[config.ROLE_GENERAL], *specialists,
                               labels[config.ROLE_MANAGER]]))


def staff_row(t: Teacher) -> list:
    return [t.name or None, role_label(t), t.class_name, t.max_lessons, MATERNITY_LABEL if t.maternity else None]


def _style_rows(ws, first: int, last: int, n_cols: int, header: bool = False, name_col: int | None = None) -> None:
    for r in range(first, last + 1):
        ws.row_dimensions[r].height = ROW_HEIGHT
        for c in range(1, n_cols + 1):
            cell = ws.cell(r, c)
            cell.font = HEADER_FONT if header else FONT
            cell.border = BORDER
            cell.alignment = NAME_ALIGN if c == name_col and not header else CENTER


def _staff_sheet(wb, teachers: list[Teacher]) -> None:
    ws = wb.active
    ws.title = config.STAFF_SHEET
    ws.append(STAFF_HEADERS)
    for t in teachers:
        ws.append(staff_row(t))
    _style_rows(ws, 1, 1, len(STAFF_HEADERS), header=True)
    _style_rows(ws, 2, len(teachers) + 1 + BLANK_ROWS, len(STAFF_HEADERS), name_col=1)
    for cell in ws[1]:
        if cell.value in NOTES:
            cell.comment = Comment(NOTES[cell.value], "TKB")
    for r in range(2, LAST_ROW + 1):
        ws.cell(r, 3).number_format = "@"  # Lớp là chữ, để Excel không đổi "1/1" thành ngày tháng
    for col, width in zip("ABCDE", STAFF_WIDTHS):
        ws.column_dimensions[col].width = width

    n_roles = len(role_choices(teachers))
    # Chức Vụ: danh sách thả xuống chỉ để gợi ý (vẫn gõ được tên môn khác cho GV chuyên biệt).
    roles = DataValidation(type="list", formula1=f"'{LIST_SHEET}'!$A$1:$A${n_roles}", allow_blank=True,
                           showErrorMessage=False, sqref=f"B2:B{LAST_ROW}")
    classes = DataValidation(type="custom", allow_blank=True, showErrorMessage=True, errorTitle="Lớp không hợp lệ",
                             error="Lớp ghi dạng khối/số thứ tự, vd 1/1.", sqref=f"C2:C{LAST_ROW}",
                             formula1='AND(ISNUMBER(FIND("/",C2)),ISNUMBER(--LEFT(C2,FIND("/",C2)-1)),'
                                      'ISNUMBER(--MID(C2,FIND("/",C2)+1,5)))')
    lessons = _whole(f"D2:D{LAST_ROW}")
    maternity = DataValidation(type="list", formula1=f'"{MATERNITY_LABEL}"', allow_blank=True, showErrorMessage=True,
                               errorTitle="Chế Độ", error=f"Ghi \"{MATERNITY_LABEL}\" hoặc để trống.",
                               sqref=f"E2:E{LAST_ROW}")
    for dv in (roles, classes, lessons, maternity):
        ws.add_data_validation(dv)

    # Tô đỏ: lớp có hai chủ nhiệm, Chủ Nhiệm thiếu Lớp, chức vụ khác lại ghi Lớp.
    homeroom = config.ROLE_LABELS[config.ROLE_HOMEROOM]
    cells = f"C2:C{LAST_ROW}"
    ws.conditional_formatting.add(cells, Rule(type="duplicateValues", dxf=ERROR_STYLE))
    ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($B2="{homeroom}",$C2="")'],
                                                     fill=ERROR_STYLE.fill))
    ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($C2<>"",$B2<>"{homeroom}")'],
                                                     fill=ERROR_STYLE.fill))


def _whole(cells: str) -> DataValidation:
    return DataValidation(type="whole", operator="between", formula1="0", formula2=str(MAX_LESSONS),
                          allow_blank=True, showErrorMessage=True, errorTitle="Số tiết không hợp lệ",
                          error=f"Số tiết là số nguyên từ 0 đến {MAX_LESSONS}.", sqref=cells)


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
    last = get_column_letter(n_cols)
    ws.add_data_validation(_whole(f"B2:{last}{max(len(subjects) + 1, 2 + BLANK_ROWS)}"))
    ws.column_dimensions["A"].width = 28
    for c in range(2, n_cols + 1):
        ws.column_dimensions[get_column_letter(c)].width = 10


def write_staff_template(path: str | Path, teachers: list[Teacher] = (),
                         curriculum: dict[int, dict[str, int]] | None = None) -> None:
    """Ghi file vào mẫu V8 (sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC)."""
    teachers = list(teachers)
    wb = openpyxl.Workbook()
    _staff_sheet(wb, teachers)
    _program_sheet(wb, curriculum, teachers)
    lists = wb.create_sheet(LIST_SHEET)
    for i, value in enumerate(role_choices(teachers), start=1):
        lists.cell(i, 1, value)
    lists.sheet_state = "hidden"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tkb.template",
                                 description="Tạo file vào mẫu (nhân sự + chương trình học)")
    ap.add_argument("output", help="File mẫu cần tạo (.xlsx)")
    ap.add_argument("--tu", help="File cũ để chép dữ liệu sang (nhân sự, và chương trình học nếu có)")
    ap.add_argument("--program", help="File chương trình học riêng để chép vào sheet CHƯƠNG TRÌNH HỌC")
    args = ap.parse_args(argv)
    try:
        teachers = read_staff(args.tu) if args.tu else []
        program = args.program or (args.tu if args.tu and has_program_sheet(args.tu) else None)
        curriculum = read_program(program) if program else None
    except InputError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    write_staff_template(args.output, teachers, curriculum)
    print(f"Đã ghi: {args.output} ({len(teachers)} nhân sự)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
