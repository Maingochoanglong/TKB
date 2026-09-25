"""File mẫu danh sách nhân sự: 4 cột Tên / Chức vụ / Số tiết / Thai sản, chức vụ chọn từ danh sách.

Chạy:
    python -m tkb.template <file mới.xlsx>                  tạo file mẫu trống
    python -m tkb.template <file mới.xlsx> --tu <file cũ>   chuyển file cũ (chữ "ts" sau chức vụ)
                                                            sang file mẫu, giữ nguyên dữ liệu
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.formatting.rule import Rule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.worksheet.datavalidation import DataValidation

from . import config
from .staff import InputError, Teacher, canonical_title, read_staff

SHEET = "Nhân sự"
LIST_SHEET = "Danh mục"
HEADERS = ["Tên", "Chức vụ", "Số tiết", "Thai sản"]
YES = "Có"
LAST_ROW = 300  # số dòng có sẵn danh sách thả xuống
CLASSES_PER_GRADE = 10  # chủ nhiệm 1/1 ... 1/10
MAX_INDEX = 20  # bộ môn 1 ... bộ môn 20
MAX_LESSONS = 40
FONT = "Times New Roman"
HEADER_FILL = PatternFill("solid", fgColor="F0F0F0")

NOTES = {
    "Chức vụ": "Chọn từ danh sách thả xuống, không gõ tay.",
    "Số tiết": "Số tiết tối đa mỗi tuần (người hưởng thai sản ghi mức đã giảm).",
    "Thai sản": "Ghi \"Có\" nếu đang hưởng chế độ thai sản; để trống nếu không.",
}


def title_choices() -> list[str]:
    """Mọi chức vụ hợp lệ cho danh sách thả xuống."""
    titles = [f"{config.ROLE_HOMEROOM} {g}/{n}" for g in sorted(config.DEFAULT_CURRICULUM)
              for n in range(1, CLASSES_PER_GRADE + 1)]
    for role in [config.ROLE_GENERAL, *config.SPECIALIST_ROLES, config.ROLE_MANAGER]:
        titles += [f"{role} {i}" for i in range(1, MAX_INDEX + 1)]
    return titles


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
        ws.append([t.name, canonical_title(t.role, t.index, t.class_name, False), t.max_lessons,
                   YES if t.maternity else None])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name=FONT, size=12)
    for col, width in zip("ABCD", (34, 22, 10, 10)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    lists = wb.create_sheet(LIST_SHEET)
    choices = title_choices()
    for i, title in enumerate(choices, start=1):
        lists.cell(i, 1, title)
    lists.sheet_state = "hidden"

    rows = f"2:{LAST_ROW}"
    title_dv = DataValidation(type="list", formula1=f"'{LIST_SHEET}'!$A$1:$A${len(choices)}", allow_blank=True,
                              showErrorMessage=True, errorTitle="Chức vụ không hợp lệ",
                              error="Hãy chọn chức vụ từ danh sách thả xuống.")
    lessons_dv = DataValidation(type="whole", operator="between", formula1="0", formula2=str(MAX_LESSONS),
                                allow_blank=True, showErrorMessage=True, errorTitle="Số tiết không hợp lệ",
                                error=f"Số tiết là số nguyên từ 0 đến {MAX_LESSONS}.")
    ts_dv = DataValidation(type="list", formula1=f'"{YES}"', allow_blank=True, showErrorMessage=True,
                           errorTitle="Thai sản", error=f"Ghi \"{YES}\" hoặc để trống.")
    for dv, col in ((title_dv, "B"), (lessons_dv, "C"), (ts_dv, "D")):
        ws.add_data_validation(dv)
        dv.add(f"{col}{rows.replace(':', f':{col}')}")
    # Tô đỏ chức vụ bị trùng.
    ws.conditional_formatting.add(f"B2:B{LAST_ROW}", Rule(
        type="duplicateValues", dxf=DifferentialStyle(fill=PatternFill(bgColor="FFC7CE"),
                                                      font=Font(color="9C0006"))))
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
