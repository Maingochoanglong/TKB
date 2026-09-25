"""File vào mẫu V8: một file Excel, hai sheet.

- Sheet "NHÂN SỰ": STT | Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Chế độ
  - Chức Vụ chọn từ danh sách, không ghi số thứ tự (chương trình tự đánh số theo thứ tự dòng).
  - Lớp (khối/số thứ tự, vd 1/1) chỉ ghi cho Chủ Nhiệm.
  - Chế độ ghi "Có" nếu đang hưởng chế độ thai sản, để trống nếu không.
- Sheet "CHƯƠNG TRÌNH HỌC": STT | Môn học | Khối 1 ... Khối 5 (số tiết/tuần), có dòng Tổng.

Chạy:
    python -m tkb.template <file mới.xlsx>                  tạo file mẫu (chương trình học mặc định)
    python -m tkb.template <file mới.xlsx> --tu <file cũ>   chuyển file cũ sang file mẫu
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule, Rule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import config
from .program import has_program_sheet, read_program
from .staff import InputError, Teacher, read_staff

LIST_SHEET = "Danh mục"
STAFF_HEADERS = ["STT", "Họ và Tên", "Chức Vụ", "Lớp", "Số Tiết/Tuần", "Chế độ"]
MATERNITY_VALUE = "Có"  # giá trị cột Chế độ của người hưởng chế độ thai sản
LAST_ROW = 300  # số dòng có sẵn danh sách thả xuống
CLASSES_PER_GRADE = 10  # lớp 1/1 ... 1/10
MAX_LESSONS = 40
FONT = "Times New Roman"
HEADER_FILL = PatternFill("solid", fgColor="F0F0F0")
ERROR_STYLE = DifferentialStyle(fill=PatternFill(bgColor="FFC7CE"), font=Font(color="9C0006"))

NOTES = {
    "Chức Vụ": "Chọn từ danh sách thả xuống. Không ghi số thứ tự: chương trình tự đánh số theo thứ tự dòng.",
    "Lớp": "Chỉ ghi cho Chủ Nhiệm, dạng khối/số thứ tự, vd 1/1. Chọn từ danh sách thả xuống.",
    "Số Tiết/Tuần": "Số tiết tối đa mỗi tuần (người hưởng thai sản ghi mức đã giảm).",
    "Chế độ": f"Ghi \"{MATERNITY_VALUE}\" nếu đang hưởng chế độ thai sản; để trống nếu không.",
}


def role_choices() -> list[str]:
    return list(config.ROLE_LABELS.values())


def class_choices() -> list[str]:
    return [f"{g}/{n}" for g in sorted(config.DEFAULT_CURRICULUM) for n in range(1, CLASSES_PER_GRADE + 1)]


def staff_row(t: Teacher) -> list:
    return ["=ROW()-1", t.name, config.ROLE_LABELS.get(t.role, t.role), t.class_name, t.max_lessons,
            MATERNITY_VALUE if t.maternity else None]


def _header(ws, headers: list[str]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(name=FONT, size=12, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        if cell.value in NOTES:
            cell.comment = Comment(NOTES[cell.value], "TKB")
    ws.freeze_panes = "A2"


def _body_font(ws, last_row: int, n_cols: int) -> None:
    for r in range(2, last_row + 1):
        for c in range(1, n_cols + 1):
            ws.cell(r, c).font = Font(name=FONT, size=12)


def _whole(cells: str) -> DataValidation:
    return DataValidation(type="whole", operator="between", formula1="0", formula2=str(MAX_LESSONS),
                          allow_blank=True, showErrorMessage=True, errorTitle="Số tiết không hợp lệ",
                          error=f"Số tiết là số nguyên từ 0 đến {MAX_LESSONS}.", sqref=cells)


def _staff_sheet(wb, teachers: list[Teacher]) -> None:
    ws = wb.active
    ws.title = config.STAFF_SHEET
    _header(ws, STAFF_HEADERS)
    for t in teachers:
        ws.append(staff_row(t))
    for r in range(2, LAST_ROW + 1):
        ws.cell(r, 4).number_format = "@"  # Lớp là chữ, để Excel không đổi "1/1" thành ngày tháng
    _body_font(ws, LAST_ROW, len(STAFF_HEADERS))
    for col, width in zip("ABCDEF", (7, 34, 16, 10, 16, 10)):
        ws.column_dimensions[col].width = width

    def dv_list(source: str, col: str, title: str, error: str) -> DataValidation:
        return DataValidation(type="list", formula1=source, allow_blank=True, showErrorMessage=True,
                              errorTitle=title, error=error, sqref=f"{col}2:{col}{LAST_ROW}")

    for dv in (dv_list(f"'{LIST_SHEET}'!$A$1:$A${len(role_choices())}", "C", "Chức Vụ không hợp lệ",
                       "Hãy chọn chức vụ từ danh sách thả xuống."),
               dv_list(f"'{LIST_SHEET}'!$B$1:$B${len(class_choices())}", "D", "Lớp không hợp lệ",
                       "Lớp ghi dạng khối/số thứ tự, hãy chọn từ danh sách thả xuống."),
               _whole(f"E2:E{LAST_ROW}"),
               dv_list(f'"{MATERNITY_VALUE}"', "F", "Chế độ", f"Ghi \"{MATERNITY_VALUE}\" hoặc để trống.")):
        ws.add_data_validation(dv)

    # Tô đỏ: lớp có hai chủ nhiệm, Chủ Nhiệm thiếu Lớp, chức vụ khác lại ghi Lớp.
    homeroom = config.ROLE_LABELS[config.ROLE_HOMEROOM]
    cells = f"D2:D{LAST_ROW}"
    ws.conditional_formatting.add(cells, Rule(type="duplicateValues", dxf=ERROR_STYLE))
    ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($C2="{homeroom}",$D2="")'],
                                                     fill=ERROR_STYLE.fill))
    ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($D2<>"",$C2<>"{homeroom}")'],
                                                     fill=ERROR_STYLE.fill))


def _program_sheet(wb, curriculum: dict[int, dict[str, int]]) -> None:
    ws = wb.create_sheet(config.PROGRAM_SHEET)
    grades = sorted(curriculum)
    _header(ws, ["STT", "Môn học", *[f"Khối {g}" for g in grades]])
    subjects = [s for s in config.SUBJECT_ORDER if any(s in curriculum[g] for g in grades)]
    subjects += sorted({s for g in grades for s in curriculum[g]} - set(subjects))
    for i, s in enumerate(subjects, start=1):
        ws.append([i, s, *[curriculum[g].get(s, 0) for g in grades]])
    last = len(subjects) + 1
    ws.append([None, "Tổng", *[f"=SUM({get_column_letter(c)}2:{get_column_letter(c)}{last})"
                                for c in range(3, 3 + len(grades))]])
    _body_font(ws, last + 1, 2 + len(grades))
    for cell in ws[last + 1]:
        cell.font = Font(name=FONT, size=12, bold=True)
    ws.add_data_validation(_whole(f"C2:{get_column_letter(2 + len(grades))}{last}"))
    for col, width in zip("ABCDEFG", (7, 28, 10, 10, 10, 10, 10)):
        ws.column_dimensions[col].width = width


def write_staff_template(path: str | Path, teachers: list[Teacher] = (),
                         curriculum: dict[int, dict[str, int]] | None = None) -> None:
    """Ghi file vào mẫu V8 (sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC)."""
    wb = openpyxl.Workbook()
    _staff_sheet(wb, teachers)
    _program_sheet(wb, curriculum or config.DEFAULT_CURRICULUM)
    lists = wb.create_sheet(LIST_SHEET)
    for col, values in enumerate((role_choices(), class_choices()), start=1):
        for i, value in enumerate(values, start=1):
            lists.cell(i, col, value).number_format = "@"
    lists.sheet_state = "hidden"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tkb.template",
                                 description="Tạo file vào mẫu (nhân sự + chương trình học)")
    ap.add_argument("output", help="File mẫu cần tạo (.xlsx)")
    ap.add_argument("--tu", help="File cũ để chép dữ liệu sang (nhân sự, và chương trình học nếu có)")
    args = ap.parse_args(argv)
    try:
        teachers = read_staff(args.tu) if args.tu else []
        curriculum = read_program(args.tu) if args.tu and has_program_sheet(args.tu) else None
    except InputError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    write_staff_template(args.output, teachers, curriculum)
    print(f"Đã ghi: {args.output} ({len(teachers)} nhân sự)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
