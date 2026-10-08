"""Đóng gói giao diện xếp TKB thành bản chạy không cần cài Python (PyInstaller, bản thư mục), rồi nén zip.

    pip install -r requirements-build.txt
    python tools/dong_goi.py        # -> dist/TKB/TKB.exe (Linux: dist/TKB/TKB) và dist/TKB_<hệ điều hành>.zip

Người dùng giải nén zip rồi bấm đúp TKB.exe: cửa sổ dòng lệnh mở máy chủ, trình duyệt mở trang nhập liệu, kết quả ghi
vào thư mục TKB trong thư mục người dùng (tkb/giao_dien/server.default_out_dir). Việc xếp TKB chạy lại chính TKB.exe
với --cli (server.cli_command), cùng OR-Tools ghim trong requirements.txt nên ra cùng mã kết quả như `python -m tkb`
trên cùng hệ điều hành. Dùng bản thư mục (không phải một file .exe): OR-Tools có nhiều thư viện động, bản một file
mỗi lần mở phải giải nén ra thư mục tạm, chậm. Gói không được chứa file Excel nào (file của trường có tên giáo viên):
kiểm sau khi dựng. Workflow .github/workflows/dong_goi.yml dựng bản Windows và chạy thử (.github/scripts/thu_goi.py).
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "TKB"
README = """Xếp thời khóa biểu (TKB)

1. Bấm đúp {exe}. Một cửa sổ dòng lệnh mở ra (giữ cửa sổ này mở trong khi dùng), trình duyệt mở trang nhập liệu.
   Trình duyệt không tự mở thì chép đường dẫn in trong cửa sổ (http://127.0.0.1:...) vào trình duyệt.
2. Trên trang: Nhập từ Excel (hoặc Tải file mẫu rồi điền), đi lần lượt các bước, bấm Kiểm tra rồi Xếp TKB.
3. Kết quả ghi vào thư mục TKB trong thư mục người dùng (vd C:\\Users\\<tên>\\TKB); đổi được ở bước cuối.
4. Tắt: đóng cửa sổ dòng lệnh.

Mọi thứ chạy trên máy này, không gửi dữ liệu đi đâu. Hướng dẫn đầy đủ: docs/Huong_Dan_Su_Dung.md của dự án.
"""


def build() -> Path:
    """Dựng dist/TKB bằng PyInstaller; trả về thư mục gói."""
    sep = ";" if os.name == "nt" else ":"
    static = ROOT / "tkb" / "giao_dien" / "static"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
                    "--name", NAME, "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
                    "--specpath", str(ROOT / "build"), "--paths", str(ROOT),
                    "--add-data", f"{static}{sep}tkb/giao_dien/static",
                    "--collect-submodules", "tkb", "--collect-all", "ortools",
                    str(ROOT / "giao_dien.py")], check=True, cwd=ROOT)
    folder = ROOT / "dist" / NAME
    exe = f"{NAME}.exe" if os.name == "nt" else NAME
    (folder / "DOC_TRUOC.txt").write_text(README.format(exe=exe), encoding="utf-8-sig")
    return folder


def check(folder: Path) -> None:
    """Gói đủ trang giao diện, không có file Excel nào (file của trường có tên giáo viên)."""
    excel = [p.relative_to(folder) for p in folder.rglob("*") if p.suffix.lower() in (".xlsx", ".xlsm", ".xls")]
    if excel:
        raise SystemExit(f"LỖI: gói có file Excel, không được phát hành: {', '.join(map(str, excel))}")
    pages = list(folder.rglob("index.html"))
    if not any(p.parent.name == "static" and (p.parent / "app.js").is_file() for p in pages):
        raise SystemExit("LỖI: gói thiếu trang giao diện (tkb/giao_dien/static)")


def pack(folder: Path) -> Path:
    """Nén thư mục gói thành dist/TKB_<hệ điều hành>.zip (trong zip là thư mục TKB/)."""
    out = folder.parent / f"{NAME}_{platform.system()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            z.write(p, Path(NAME) / p.relative_to(folder))
    return out


def main() -> int:
    if not _has_pyinstaller():
        print("LỖI: chưa có PyInstaller. Cài bằng lệnh:  pip install -r requirements-build.txt")
        return 1
    folder = build()
    check(folder)
    out = pack(folder)
    print(f"Đã dựng: {folder}")
    print(f"Đã nén : {out} ({out.stat().st_size / 1e6:.0f} MB)")
    return 0


def _has_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
