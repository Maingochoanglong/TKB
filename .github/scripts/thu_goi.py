"""Chạy thử gói dựng bằng tools/dong_goi.py, như người dùng bấm đúp TKB.exe, với trường mẫu tên giả.

1. `TKB.exe --cli <file vào> ...` (đúng lệnh giao diện gọi khi xếp TKB), 30 giây: mã thoát 0, đủ các file ra.
2. Mở giao diện (máy chủ của gói), lấy mã phiên trong trang, rồi qua /api/: nhập file, Kiểm tra, xếp 20 giây (giao diện
   gọi lại chính TKB.exe --cli), xem TKB vừa xếp (bước 7: kiểm luật, thử đổi ô), xếp lần nữa rồi bấm Dừng sau khi đã
   có TKB khởi đầu: dừng sớm mà vẫn ghi TKB.
Gói chạy với môi trường không có PYTHONPATH/PYTHONHOME, thư mục làm việc ngoài dự án: không dùng Python của máy.

Chạy: python .github/scripts/thu_goi.py dist/TKB/TKB.exe
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tkb.truong_mau import write_sample_input  # noqa: E402

FILES = ("TKB.xlsx", "TKB_chuc_vu.xlsx", "TKB_giao_vien.xlsx", "Thong_Ke.xlsx", "mau_cap_nhat.xlsx")


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    return env | {"PYTHONIOENCODING": "utf-8"}


def _fail(text: str) -> None:
    print(f"LỖI: {text}")
    sys.exit(1)


def cli(exe: Path, work: Path) -> None:
    out = work / "cli"
    argv = [str(exe), "--cli", str(work / "mau.xlsx"), "-o", str(out / "TKB.xlsx"), "--time-limit", "30",
            "--mode", "bu_gio", "--max-overtime", "3", "--staff-out", str(out / "mau_cap_nhat.xlsx")]
    res = subprocess.run(argv, cwd=work, env=_env(), capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=900)
    print(res.stdout[-3000:])
    if res.returncode != 0:
        _fail(f"TKB --cli thoát mã {res.returncode}")
    missing = [name for name in FILES if not (out / name).is_file()]
    if missing:
        _fail(f"TKB --cli không ghi: {', '.join(missing)}")
    print("1. TKB --cli: đạt")


def _call(url: str, token: str, path: str, body=None, raw: bytes | None = None, timeout: int = 300):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url + path, data=data, method="POST" if data is not None else "GET",
                                 headers={"X-TKB-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read())


def _wait(url: str, token: str, until, limit: int) -> dict:
    deadline = time.time() + limit
    while True:
        state = _call(url, token, "api/status?since=0")
        if until(state):
            return state
        if time.time() > deadline:
            print("\n".join(state["lines"][-30:]))
            _fail(f"quá {limit} giây")
        time.sleep(1)


def ui(exe: Path, work: Path) -> None:
    server = subprocess.Popen([str(exe), "--khong-mo-trinh-duyet", "--cong", "8799", "--thu-muc", str(work / "ui")],
                              cwd=work, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace")
    try:
        line, deadline = "", time.time() + 120
        while "http://" not in line:
            line = server.stdout.readline()
            if not line and (server.poll() is not None or time.time() > deadline):
                _fail("giao diện không mở được máy chủ")
        url = re.search(r"http://\S+/", line).group(0)
        with urllib.request.urlopen(url, timeout=60) as res:
            page = res.read().decode("utf-8")
        token = re.search(r'window\.TKB_TOKEN = "([^"]+)"', page).group(1)
        scenario = _call(url, token, "api/import", raw=(work / "mau.xlsx").read_bytes())["scenario"]
        errors = _call(url, token, "api/check", {"scenario": scenario, "run": {"overtime_max": 3}})["errors"]
        if errors:
            _fail(f"Kiểm tra báo lỗi: {errors[:3]}")
        run = {"name": "mau", "time_limit": 20, "workers": 4, "overtime_max": 3}
        _call(url, token, "api/run", {"scenario": scenario, "run": run})
        state = _wait(url, token, lambda s: not s["running"], 600)
        if state["exit"] != 0 or not state["summary"]["passed"]:
            print("\n".join(state["lines"][-30:]))
            _fail(f"xếp qua giao diện thoát mã {state['exit']}")
        print(f"2. Giao diện, xếp TKB: đạt ({state['summary']['code']})")
        updated = next(p for p in state["summary"]["files"] if p.endswith("_cap_nhat.xlsx"))  # bước 7: xem TKB
        saved = _call(url, token, "api/import_path", {"path": updated})["scenario"]
        view = _call(url, token, "api/timetable", {"scenario": saved, "run": run})
        if not view["ok"] or len(view["classes"]) != 29:
            _fail(f"Xem TKB trên trang: {view['errors'][:3] or view['input_errors'][:3]}")
        cell = next(c for c in view["cells"] if c["subject"])
        swaps = _call(url, token, "api/swaps", {"scenario": saved, "run": run, "cls": cell["cls"], "d": cell["d"],
                                                "p": cell["p"]})["swaps"]
        print(f"   Xem TKB trên trang: đạt ({len(view['cells'])} ô, thử đổi một ô với {len(swaps)} ô)")
        _call(url, token, "api/run", {"scenario": scenario, "run": {**run, "time_limit": 300}})
        _wait(url, token, lambda s: any("Khởi đầu:" in x for x in s["lines"]) or not s["running"], 600)
        _call(url, token, "api/stop", {})
        stopped = time.time()
        state = _wait(url, token, lambda s: not s["running"], 120)
        if state["exit"] != 0 or not any("Dừng xếp giờ: Ctrl+C" in x for x in state["lines"]):
            print("\n".join(state["lines"][-30:]))
            _fail(f"Dừng sớm không đúng (mã thoát {state['exit']})")
        print(f"3. Giao diện, Dừng sớm: đạt (dừng sau {time.time() - stopped:.0f} giây, vẫn ghi TKB)")
    finally:
        server.kill()


def main() -> int:
    exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        write_sample_input(work / "mau.xlsx")
        cli(exe, work)
        ui(exe, work)
    print("Gói chạy đúng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
