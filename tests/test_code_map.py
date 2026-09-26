"""docs/CODE_MAP.md phải khớp code hiện tại (sinh lại bằng: python tools/code_map.py --write)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _code_map():
    spec = importlib.util.spec_from_file_location("code_map", ROOT / "tools" / "code_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_code_map_is_up_to_date():
    code_map = _code_map()
    assert code_map.OUT.read_text(encoding="utf-8") == code_map.render(), \
        "docs/CODE_MAP.md đã cũ: chạy  python tools/code_map.py --write"
