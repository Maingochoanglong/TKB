"""File mẫu danh sách nhân sự V7: Họ và Tên | Chức Vụ | Lớp | Chế độ | Số Tiết/Tuần.

- Chức Vụ chọn từ danh sách, không ghi số thứ tự (chương trình tự đánh số theo thứ tự dòng).
- Lớp (khối/số thứ tự, vd 1/1) chỉ ghi cho Chủ Nhiệm.
- Chế độ ghi "Thai sản" nếu đang hưởng chế độ thai sản, để trống nếu không.

Chạy:
    python -m tkb.template <file mới.xlsx>                  tạo file mẫu trống
    python -m tkb.template <file mới.xlsx> --tu <file cũ>   chuyển file nhân sự cũ sang file mẫu
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
from openpyxl.worksheet.datavalidation import DataValidation

from . import config
from .staff import MATERNITY_LABEL, InputError, Teacher, read_staff

SHEET = "Nhân sự"
LIST_SHEET = "Danh mục"
HEADERS = ["Họ và Tên", "Chức Vụ", "Lớp", "Chế độ", "Số Tiết/Tuần"]
LAST_ROW = 300  # số dòng có sẵn danh sách thả xuống
CLASSES_PER_GRADE = 10  # lớp 1/1 ... 1/10
MAX_LESSONS = 40
FONT = "Times New Roman"
HEADER_FILL = PatternFill("solid", fgColor="F0F0F0")
ERROR_STYLE = DifferentialStyle(fill=PatternFill(bgColor="FFC7CE"), font=Font(color="9C0006"))

NOTES = {
    "Chức Vụ": "Chọn từ danh sách thả xuống. Không ghi số thứ tự: chương trình tự đánh số theo thứ tự dòng.",
    "Lớp": "Chỉ ghi cho Chủ Nhiệm, dạng khối/số thứ tự, vd 1/1. Chọn từ danh sách thả xuống.",
    "Chế độ": f"Ghi \"{MATERNITY_LABEL}\" nếu đang hưởng chế độ thai sản; để trống nếu không.",
    "Số Tiết/Tuần": "Số tiết tối đa mỗi tuần (người hưởng thai sản ghi mức đã giảm).",
}


def role_choices() -> list[str]:
    return list(config.ROLE_LABELS.values())


def class_choices() -> list[str]:
    return [f"{g}/{n}" for g in sorted(config.DEFAULT_CURRICULUM) for n in range(1, CLASSES_PER_GRADE + 1)]


def template_row(t: Teacher) -> list:
    return [t.name, config.ROLE_LABELS.get(t.role, t.role), t.class_name,
            MATERNITY_LABEL if t.maternity else None, t.max_lessons]


def write_staff_template(path: str | Path, teachers: list[Teacher] = ()) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(name=FONT, size=12, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        if cell.value in NOTES:
            cell.comment = Comment(NOTES[cell.value], "TKB")
    for t in teachers:
        ws.append(template_row(t))
    for r in range(2, LAST_ROW + 1):
        ws.cell(r, 3).number_format = "@"  # Lớp là chữ, để Excel không đổi "1/1" thành ngày tháng
        for c in range(1, len(HEADERS) + 1):
            ws.cell(r, c).font = Font(name=FONT, size=12)
    for col, width in zip("ABCDE", (34, 16, 10, 12, 14)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    lists = wb.create_sheet(LIST_SHEET)
    for col, values in enumerate((role_choices(), class_choices()), start=1):
        for i, value in enumerate(values, start=1):
            lists.cell(i, col, value).number_format = "@"
    lists.sheet_state = "hidden"

    def dv_list(source: str, title: str, error: str) -> DataValidation:
        return DataValidation(type="list", formula1=source, allow_blank=True, showErrorMessage=True,
                              errorTitle=title, error=error)

    validations = {
        "B": dv_list(f"'{LIST_SHEET}'!$A$1:$A${len(role_choices())}", "Chức Vụ không hợp lệ",
                     "Hãy chọn chức vụ từ danh sách thả xuống."),
        "C": dv_list(f"'{LIST_SHEET}'!$B$1:$B${len(class_choices())}", "Lớp không hợp lệ",
                     "Lớp ghi dạng khối/số thứ tự, hãy chọn từ danh sách thả xuống."),
        "D": dv_list(f'"{MATERNITY_LABEL}"', "Chế độ", f"Ghi \"{MATERNITY_LABEL}\" hoặc để trống."),
        "E": DataValidation(type="whole", operator="between", formula1="0", formula2=str(MAX_LESSONS),
                            allow_blank=True, showErrorMessage=True, errorTitle="Số tiết không hợp lệ",
                            error=f"Số tiết/tuần là số nguyên từ 0 đến {MAX_LESSONS}."),
    }
    for col, dv in validations.items():
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{LAST_ROW}")

    # Tô đỏ: lớp có hai chủ nhiệm, Chủ Nhiệm thiếu Lớp, chức vụ khác lại ghi Lớp.
    homeroom = config.ROLE_LABELS[config.ROLE_HOMEROOM]
    cells = f"C2:C{LAST_ROW}"
    ws.conditional_formatting.add(cells, Rule(type="duplicateValues", dxf=ERROR_STYLE))
    ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($B2="{homeroom}",$C2="")'],
                                                     fill=ERROR_STYLE.fill))
    ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($C2<>"",$B2<>"{homeroom}")'],
                                                     fill=ERROR_STYLE.fill))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tkb.template", description="Tạo file mẫu danh sách nhân sự")
    ap.add_argument("output", help="File mẫu cần tạo (.xlsx)")
    ap.add_argument("--tu", help="File nhân sự cũ để chép dữ liệu sang")
    args = ap.parse_args(argv)
    try:
        teachers = read_staff(args.tu) if args.tu else []
    except InputError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    write_staff_template(args.output, teachers)
    print(f"Đã ghi: {args.output} ({len(teachers)} nhân sự)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
