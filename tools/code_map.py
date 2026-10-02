"""Bản đồ code: mỗi module một dòng mô tả, rồi các hàm/lớp kèm tham số và dòng đầu docstring.

Dùng để tìm hàm mà không phải mở từng file (ít tốn token cho các phiên Claude Code sau).

  python tools/code_map.py          in bản đồ kèm số dòng (file:dòng), luôn đúng với code hiện tại
  python tools/code_map.py solver   chỉ in các file có "solver" trong đường dẫn (lọc được nhiều từ)
  python tools/code_map.py --write  ghi docs/CODE_MAP.md (không có số dòng); chạy lại sau khi thêm/đổi tên hàm
  python tools/code_map.py --check  mã thoát 1 nếu docs/CODE_MAP.md đã cũ (tests/test_code_map.py dùng)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "CODE_MAP.md"
SOURCES = ["main.py", "giao_dien.py", "tkb/*.py", "tkb/giao_dien/*.py", ".github/scripts/*.py", "tools/*.py"]
TESTS = "tests/test_*.py"
LONG_FUNCTION = 60  # hàm dài từ chừng này dòng thì liệt kê các khối chú thích "# ..." ở thân hàm
HEADER = ("# Code map\n\n"
          "Sinh tự động bởi `python tools/code_map.py --write`, đừng sửa tay. Bản kèm số dòng: "
          "`python tools/code_map.py`.\n")


def _files(pattern: str) -> list[Path]:
    return sorted(ROOT.glob(pattern), key=lambda p: p.relative_to(ROOT).as_posix())


def _first_line(node) -> str:
    doc = ast.get_docstring(node)
    return doc.strip().splitlines()[0] if doc and doc.strip() else ""


def _signature(fn: ast.FunctionDef) -> str:
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args if x.arg not in ("self", "cls")]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    return f"{fn.name}({', '.join(names)})"


def _item(text: str, doc: str, line: int | None, indent: str = "") -> str:
    where = f" :{line}" if line else ""
    return f"{indent}- `{text}`{where}" + (f" — {doc}" if doc else "")


def _blocks(fn: ast.FunctionDef, source: list[str], lines: bool, indent: str) -> list[str]:
    """Các dòng chú thích ngay ở thân hàm (cùng lề với các câu lệnh của thân) của một hàm dài."""
    if fn.end_lineno - fn.lineno < LONG_FUNCTION:
        return []
    margin = fn.body[0].col_offset
    blocks: list[tuple[int, str]] = []  # (dòng đầu, chú thích); chú thích nhiều dòng liền nhau gộp làm một
    for no in range(fn.body[0].lineno, fn.end_lineno + 1):
        text = source[no - 1]
        if text[:margin].strip() == "" and text[margin:margin + 2] == "# ":
            comment = text[margin + 2:].strip()
            if blocks and source[no - 2][margin:margin + 2] == "# ":
                blocks[-1] = (blocks[-1][0], f"{blocks[-1][1]} {comment}")
            else:
                blocks.append((no, comment))
    return [f"{indent}  · {comment}" + (f" :{no}" if lines else "") for no, comment in blocks]


def _constants(tree: ast.Module) -> list[str]:
    names = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        names += [t.id for t in targets if isinstance(t, ast.Name) and t.id.isupper()]
    return names


def _module(path: Path, lines: bool) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    source = text.splitlines()
    rel = path.relative_to(ROOT).as_posix()
    doc = _first_line(tree)
    out = [f"\n## {rel}" + (f" — {doc}" if doc else "")]
    consts = _constants(tree)
    if consts:
        out.append("Hằng số: " + ", ".join(f"`{c}`" for c in consts))
    for node in tree.body:
        line = node.lineno if lines else None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(_item(_signature(node), _first_line(node), line))
            out += _blocks(node, source, lines, "")
        elif isinstance(node, ast.ClassDef):
            out.append(_item(f"class {node.name}", _first_line(node), line))
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name != "__init__":
                    out.append(_item("." + _signature(m), _first_line(m), m.lineno if lines else None, "  "))
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out += _blocks(m, source, lines, "  ")
    return out


def _tests(lines: bool) -> list[str]:
    out = ["\n## tests"]
    for path in _files(TESTS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        tests = [(n.name, n.lineno) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        names = ", ".join(f"{name}:{no}" if lines else name for name, no in tests)
        out.append(f"- `{path.relative_to(ROOT).as_posix()}`: {names}")
    return out


def render(lines: bool = False, only: list[str] | None = None) -> str:
    keep = lambda rel: not only or any(word in rel for word in only)
    parts = [HEADER]
    for pattern in SOURCES:
        for path in _files(pattern):
            if path.name != "__init__.py" and keep(path.relative_to(ROOT).as_posix()):
                parts += _module(path, lines)
    if keep("tests"):
        parts += _tests(lines)
    return "\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    if "--write" in argv:
        OUT.write_text(render(), encoding="utf-8", newline="\n")
        print(f"Đã ghi {OUT.relative_to(ROOT).as_posix()}")
        return 0
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != render():
            print("docs/CODE_MAP.md đã cũ: chạy  python tools/code_map.py --write")
            return 1
        return 0
    sys.stdout.reconfigure(encoding="utf-8")
    print(render(lines=True, only=[a for a in argv if not a.startswith("-")]), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
