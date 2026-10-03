"""Giao diện web (tkb/giao_dien): máy chủ trên máy, mã phiên, các lệnh /api/ và xếp TKB qua giao diện ra đúng TKB như
dòng lệnh."""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

from tkb import config
from tkb.giao_dien.server import (FILE_NAMES, InputError, TOKEN_MARK, make_server, run_argv, safe_name, summary)
from tkb.template import write_staff_template

from .conftest import CURRICULUM, INPUT_FILE, small_staff
from .test_reproducible import REFERENCE


@pytest.fixture
def server(tmp_path):
    httpd, app, url = make_server(port=0, out_dir=tmp_path / "ket_qua")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield app, url
    app.shutdown()
    httpd.shutdown()
    httpd.server_close()


def _call(url, path, method="GET", body=None, token=None, headers=None):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    req = urllib.request.Request(url + path.lstrip("/"), data=data, method=method, headers=headers or {})
    if token:
        req.add_header("X-TKB-Token", token)
    if body is not None and not isinstance(body, bytes):
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return res.status, (json.loads(raw) if res.headers.get_content_type() == "application/json" else raw)
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}") if err.headers.get_content_type() == "application/json" else None


def test_page_and_token(server):
    app, url = server
    status, page = _call(url, "/")
    assert status == 200 and app.token.encode() in page and TOKEN_MARK.encode() not in page
    assert _call(url, "/api/schema")[0] == 403  # thiếu mã phiên
    assert _call(url, "/api/schema", token="sai")[0] == 403
    assert _call(url, "/", headers={"Host": "evil.example"})[0] == 403  # chỉ nhận Host 127.0.0.1/localhost
    assert _call(url, "/../server.py")[0] == 404
    status, schema = _call(url, "/api/schema", token=app.token)
    assert status == 200 and schema["run_defaults"]["mode"] == config.MODE_OVERTIME
    assert schema["out_dir"] == str(app.out_dir)


def test_import_check_export(server):
    app, url = server
    status, data = _call(url, "/api/import", "POST", INPUT_FILE.read_bytes(), app.token,
                         {"X-File-Name": "Truong%20M%E1%BA%ABu.xlsx"})
    assert status == 200 and len(data["scenario"]["staff"]) == 45 and data["name"] == "Truong Mẫu"
    assert data["sheets"] == ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC", "CHỨC VỤ", "QUY ĐỊNH", "LUẬT RIÊNG"]
    status, res = _call(url, "/api/check", "POST", {"scenario": data["scenario"], "run": {"overtime_max": 2}}, app.token)
    assert status == 200 and res["errors"] == []
    status, xlsx = _call(url, "/api/export", "POST", {"scenario": data["scenario"], "name": "a/b"}, app.token)
    assert status == 200 and xlsx[:2] == b"PK"  # file .xlsx (zip)
    status, err = _call(url, "/api/import", "POST", b"khong phai excel", app.token)
    assert status == 400 and "Excel" in err["error"]
    status, err = _call(url, "/api/check", "POST", {"scenario": data["scenario"], "run": {"workers": 0}}, app.token)
    assert status == 400 and "luồng" in err["error"]


def test_blank_template(server, tmp_path):
    """Nút Tải file mẫu: đúng file mẫu trống của python -m tkb.template; nhập lại được."""
    import openpyxl

    app, url = server
    status, xlsx = _call(url, f"/api/template?t={app.token}")
    assert status == 200 and xlsx[:2] == b"PK"
    (tmp_path / "tai.xlsx").write_bytes(xlsx)
    write_staff_template(tmp_path / "mau.xlsx")
    values = lambda p: [list(ws.values) for ws in openpyxl.load_workbook(p).worksheets]  # noqa: E731
    assert values(tmp_path / "tai.xlsx") == values(tmp_path / "mau.xlsx")
    status, data = _call(url, "/api/import", "POST", xlsx, app.token)
    assert status == 200 and data["scenario"]["staff"] == [] and data["warnings"] == []


def test_files_only_inside_output_folder(server, tmp_path):
    app, url = server
    (tmp_path / "ngoai.xlsx").write_bytes(b"x")
    status, err = _call(url, f"/api/file?path={quote(str(tmp_path / 'ngoai.xlsx'))}&t={app.token}")
    assert status == 400 and "thư mục kết quả" in err["error"]
    status, err = _call(url, "/api/open", "POST", {"path": str(tmp_path / "ngoai.xlsx")}, app.token)
    assert status == 400


def test_run_argv_like_main():
    argv = run_argv(Path("/d/vao.xlsx"), Path("/d"), "vao", {"mode": config.MODE_HIRE, "overtime_max": 3,
                                                               "time_limit": "", "workers": 8, "student_rules": False,
                                                               "reproducible": True, "keep_saved": False})
    assert argv[0] == str(Path("/d/vao.xlsx"))
    assert argv[argv.index("--time-limit") + 1] == "0"  # trống = không giới hạn
    assert argv[argv.index("--staff-out") + 1] == str(Path("/d/vao_cap_nhat.xlsx"))
    assert argv[argv.index("-o") + 1] == str(Path("/d") / FILE_NAMES["tkb"])
    assert "--no-student-rules" in argv and "--xep-lai" in argv and "--non-reproducible" not in argv
    for bad in ({"mode": "x"}, {"overtime_max": -1}, {"overtime_max": 1.5}, {"time_limit": "abc"}, {"workers": 0}):
        with pytest.raises(InputError):
            run_argv(Path("v.xlsx"), Path("."), "v", bad)
    assert safe_name('  a<b>:c.xlsx ') == "abc" and safe_name("") == "kich_ban"


def test_summary_reads_printed_result():
    lines = ["Kết quả: FEASIBLE, kiểm tra luật bắt buộc: ĐẠT", "Mã kết quả: 1234-5678-9ABC (cùng mã là cùng TKB)",
             "Đã ghi: /x/TKB.xlsx", "Đã ghi: /x/Thong_Ke.xlsx"]
    assert summary(lines) == {"code": "1234-5678-9ABC", "passed": True, "files": ["/x/TKB.xlsx", "/x/Thong_Ke.xlsx"],
                              "error": None}
    assert summary(["Kết quả: FEASIBLE, kiểm tra luật bắt buộc: KHÔNG ĐẠT"])["passed"] is False
    assert summary(lines)["error"] is None
    failed = summary(["Bước 2/2: xếp giờ", "LỖI: Các luật bắt buộc sau không cùng thỏa được:", "  - A", "Đã ghi: /x/a"])
    assert failed["error"] == "LỖI: Các luật bắt buộc sau không cùng thỏa được:\n  - A"


@pytest.mark.parametrize("mode", config.MODES)
def test_run_from_the_ui_gives_the_reference_timetable(server, tmp_path, mode):
    """Xếp qua giao diện (kịch bản -> file vào -> python -m tkb ở tiến trình con) ra đúng mã tham chiếu của dòng
    lệnh (tests/test_reproducible.py: trường nhỏ, time_limit=5, 4 luồng, bù tối đa +4)."""
    app, url = server
    write_staff_template(tmp_path / "nho.xlsx", small_staff(general=False), CURRICULUM)
    _, data = _call(url, "/api/import", "POST", (tmp_path / "nho.xlsx").read_bytes(), app.token)
    run = {"name": "nho", "mode": mode, "overtime_max": 4, "time_limit": 5, "workers": 4}
    status, started = _call(url, "/api/run", "POST", {"scenario": data["scenario"], "run": run}, app.token)
    assert status == 200 and Path(started["input"]) == app.out_dir / "nho.xlsx"
    assert _call(url, "/api/run", "POST", {"scenario": data["scenario"], "run": run}, app.token)[0] == 400  # đang chạy
    deadline = time.time() + 300
    while True:
        _, state = _call(url, "/api/status?since=0", token=app.token)
        if not state["running"] or time.time() > deadline:
            break
        time.sleep(0.5)
    assert state["exit"] == 0, "\n".join(state["lines"])
    result = state["summary"]
    assert result["passed"] is True
    assert {Path(p).name for p in result["files"]} == {*FILE_NAMES.values(), "nho_cap_nhat.xlsx"}
    expected = REFERENCE.get(sys.platform, {}).get(mode)
    if expected is not None:
        assert result["code"] == expected
    status, body = _call(url, f"/api/file?path={quote(result['files'][0])}&t={app.token}")
    assert status == 200 and body[:2] == b"PK"
