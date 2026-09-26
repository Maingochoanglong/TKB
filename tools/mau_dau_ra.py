"""Sinh lại các file mẫu đầu ra từ trường mẫu tên giả (tests/du_lieu_mau.py), với các hằng số mặc định
của main.py: data/Output_Template_TKB_V8.xlsx (TKB) và data/Output_Template_Thong_Ke_V8.xlsx (thống kê).

Chạy lại sau khi đổi cách ghi file ra (tkb/writer.py) hoặc đổi luật làm TKB khác đi (vài phút):
  python tools/mau_dau_ra.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from tests.du_lieu_mau import write_sample_input  # noqa: E402

TEMPLATES = {main.FILE_TKB: "Output_Template_TKB_V8.xlsx", main.FILE_THONG_KE: "Output_Template_Thong_Ke_V8.xlsx"}


def run() -> int:
    out = ROOT / "out" / "mau_dau_ra"
    status = main.run(write_sample_input(out / "Input_Mau_V8.xlsx"), out)
    if status != 0:
        return status
    for produced, template in TEMPLATES.items():
        shutil.copyfile(out / produced, ROOT / "data" / template)
        print(f"Đã ghi: data/{template}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
