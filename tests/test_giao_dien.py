"""Giao diện web (tkb/giao_dien): máy chủ trên máy, mã phiên, các lệnh /api/ và xếp TKB qua giao diện ra đúng TKB như
dòng lệnh."""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

from tkb import config
from tkb.giao_dien import server as server_module
from tkb.giao_dien.server import (FILE_NAMES, InputError, TOKEN_MARK, Job, make_server, run_argv, safe_name, summary)
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
    assert data["sheets"] == ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC", "LỚP", "CHỨC VỤ", "QUY ĐỊNH", "LUẬT"]
    status, res = _call(url, "/api/check", "POST", {"scenario": data["scenario"], "run": {"overtime_max": 2}}, app.token)
    assert status == 200 and res["errors"] == []
    status, xlsx = _call(url, "/api/export", "POST", {"scenario": data["scenario"], "name": "a/b"}, app.token)
    assert status == 200 and xlsx[:2] == b"PK"  # file .xlsx (zip)
    status, err = _call(url, "/api/import", "POST", b"khong phai excel", app.token)
    assert status == 400 and "Excel" in err["error"]
    status, err = _call(url, "/api/check", "POST", {"scenario": data["scenario"], "run": {"workers": 0}}, app.token)
    assert status == 400 and "luồng" in err["error"]


def test_describe_rules(server):
    """Bộ ghép luật trên trang: câu đọc lại, lỗi và dạng gốc của từng luật (cùng hàm với file Excel), từ vựng của bộ
    ghép trong schema, xuất luật và mẫu luật."""
    app, url = server
    _, schema = _call(url, "/api/schema", token=app.token)
    composer = schema["custom"]["composer"]
    assert [m["label"] for m in composer["measures"]][:3] == ["Số tiết", "Số khác nhau", "Vị trí"]
    assert "Môn nặng" in composer["tags"]["subject"] and "Luôn do GVCN dạy" in composer["tags"]["slot"]
    _, new = _call(url, "/api/new", token=app.token)
    rows = [{"kind": "Tự ghép", "scope": "Lớp, Ngày", "subject": "Toán", "measure": "Số tiết", "op": "Tối đa",
             "number": 1, "hard": True},
            {"kind": "Tự ghép", "measure": "Liền nhau", "hard": False, "level": 3},
            {"kind": "Học trước", "subject": "Tiếng Việt", "other": "Toán", "hard": True}]
    status, data = _call(url, "/api/describe", "POST", {"scenario": new["scenario"], "rows": rows}, app.token)
    assert status == 200
    assert data["rules"][0] == {"text": "Mỗi lớp, mỗi ngày: học tối đa 1 tiết Toán (bắt buộc)", "errors": [],
                                "native": None, "level": None}  # thiếu "khi … <= số ngày": không phải dạng gốc
    assert data["rules"][1]["text"] is None and "phải có Lớp hoặc Giáo viên" in data["rules"][1]["errors"][0]
    assert data["rules"][2]["text"] == "Tiếng Việt học trước Toán trong buổi (bắt buộc)"
    status, data = _call(url, "/api/describe", "POST", {"scenario": new["scenario"]}, app.token)
    assert all(r["native"] for r in data["rules"]) and len(data["rules"]) == len(new["scenario"]["rules"])
    status, xlsx = _call(url, "/api/rules_file", "POST", {"template": True}, app.token)
    assert status == 200 and xlsx[:2] == b"PK"
    status, imported = _call(url, "/api/import", "POST", xlsx, app.token)
    assert imported["sheets"] == ["LUẬT"] and imported["scenario"]["rules"] == new["scenario"]["rules"]
    status, xlsx = _call(url, "/api/rules_file", "POST", {"scenario": new["scenario"], "name": "a"}, app.token)
    assert status == 200 and xlsx[:2] == b"PK"


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


def test_sample_and_quick_check(server):
    """Trang bắt đầu: /api/sample cho trường mẫu tên giả; /api/check quick (kiểm tra tự động khi sửa) không dự toán."""
    app, url = server
    status, data = _call(url, "/api/sample", token=app.token)
    assert status == 200 and len(data["scenario"]["staff"]) == 45 and data["name"] == "truong_mau"
    status, res = _call(url, "/api/check", "POST", {"scenario": data["scenario"], "run": {"overtime_max": 3},
                                                    "quick": True}, app.token)
    assert status == 200 and res["errors"] == [] and not any(line.startswith("Dự toán") for line in res["info"])


def test_timetable_view_and_swaps(server, small_updated):
    """Bước 7: /api/timetable vẽ TKB đã xếp kèm lỗi luật; /api/swaps thử đổi một ô với các ô cùng lớp. Đổi ô (chỉ
    phần TKB của kịch bản đổi) thì dùng lại bài toán đã dựng; file cập nhật x_cap_nhat.xlsx nhập vào có tên x."""
    app, url = server
    status, data = _call(url, "/api/import", "POST", small_updated.read_bytes(), app.token,
                         {"X-File-Name": quote(small_updated.name)})
    assert status == 200 and data["name"] == "nho"
    body = {"scenario": data["scenario"], "run": {"overtime_max": 4}}
    status, view = _call(url, "/api/timetable", "POST", body, app.token)
    assert status == 200 and view["ok"] and view["classes"] == ["3/1", "3/2"]
    grid = app.grid[1]
    status, res = _call(url, "/api/swaps", "POST", {**body, "cls": "3/1", "d": 1, "p": 3}, app.token)
    assert status == 200 and res["swaps"] and {"d", "p", "new", "fixed"} <= set(res["swaps"][0])
    moved = {**data["scenario"], "saved": [*data["scenario"]["saved"][:-1], []]}
    assert _call(url, "/api/timetable", "POST", {**body, "scenario": moved}, app.token)[0] == 200
    assert app.grid[1] is grid
    _call(url, "/api/timetable", "POST", {**body, "run": {"overtime_max": 3}}, app.token)
    assert app.grid[1] is not grid  # cài đặt chạy đổi: dựng lại


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
    got = summary(lines)
    assert {k: got[k] for k in ("code", "passed", "files", "error")} == {
        "code": "1234-5678-9ABC", "passed": True, "files": ["/x/TKB.xlsx", "/x/Thong_Ke.xlsx"], "error": None}
    # Các số của trang kết quả tóm tắt, đúng như tkb/__main__.py in ra.
    full = summary(["  Dừng xếp giờ: đã tối ưu", "Kết quả: OPTIMAL, kiểm tra luật bắt buộc: ĐẠT",
                    "Mã kết quả: 1234-5678-9ABC (cùng mã là cùng TKB; xếp giờ mất 12 giây)",
                    "So với TKB đã xếp trong file vào: đổi 11/928 ô (danh sách ở sheet Thay đổi của file thống kê)",
                    "Không cần bổ sung giáo viên.", "Dạy bù 52 tiết: GVCN 52 tiết (29 người), bộ môn 0 tiết (0 người)",
                    "  23 người bù +2, 6 người bù +1", "Môn nặng ở tiết 7: 6 tiết (mục tiêu mềm, càng ít càng tốt)",
                    "LUẬT dòng 30: Toán không xếp vào tiết 5: 2 lần không theo (ưu tiên, càng ít càng tốt)"])
    assert (full["stop"], full["seconds"], full["changes"], full["hires"]) == ("đã tối ưu", 12, [11, 928], [0, 0])
    assert full["overtime"] == {"total": 52, "homeroom": [52, 29], "general": [0, 0],
                                "levels": "23 người bù +2, 6 người bù +1"}
    assert full["soft"] == ["Môn nặng ở tiết 7: 6 tiết", "LUẬT dòng 30: Toán không xếp vào tiết 5: 2 lần không theo"]
    assert summary(["Dùng lại TKB đã xếp trong file vào (sheet TKB đã xếp), không xếp lại."])["reused"]
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
    assert result["overtime"] or result["hires"]  # trang kết quả tóm tắt: số liệu và chất lượng của lần xếp
    q = result["quality"]  # sheet Chất lượng: tổng và tối đa 5 luật trừ nhiều điểm nhất
    assert q is not None and len(q["top"]) <= 5 and q["count"] >= sum(t["count"] for t in q["top"])
    assert {Path(p).name for p in result["files"]} == {*FILE_NAMES.values(), "nho_cap_nhat.xlsx"}
    expected = REFERENCE.get(sys.platform, {}).get(mode)
    if expected is not None:
        assert result["code"] == expected
    status, body = _call(url, f"/api/file?path={quote(result['files'][0])}&t={app.token}")
    assert status == 200 and body[:2] == b"PK"


def test_open_only_files_inside_output_folder(server, monkeypatch):
    """Nút Mở file: mở đúng file trong thư mục kết quả bằng ứng dụng mặc định (Windows: os.startfile; máy khác:
    xdg-open / open), giả lập để không mở Excel thật; file ngoài thư mục hay không có thì báo lỗi."""
    app, url = server
    app.out_dir.mkdir(parents=True, exist_ok=True)
    target = app.out_dir / FILE_NAMES["tkb"]
    target.write_bytes(b"PK")
    opened = []
    if os.name == "nt":
        monkeypatch.setattr(server_module.os, "startfile", lambda path: opened.append(Path(path)))
    else:
        monkeypatch.setattr(server_module.subprocess, "Popen", lambda args, **_: opened.append(Path(args[-1])))
    assert _call(url, "/api/open", "POST", {"path": str(target)}, app.token) == (200, {"ok": True})
    assert _call(url, "/api/open", "POST", {"path": FILE_NAMES["tkb"]}, app.token)[0] == 200  # tên trong thư mục
    assert opened == [target.resolve()] * 2
    status, err = _call(url, "/api/open", "POST", {"path": str(app.out_dir / "khong_co.xlsx")}, app.token)
    assert status == 400 and "Không có" in err["error"] and len(opened) == 2


def test_stop_ends_early_and_keeps_the_timetable(tmp_path):
    """Nút Dừng (Linux: Ctrl+C, Windows: Ctrl+Break tới nhóm tiến trình con): chương trình xếp xong vùng đang xếp rồi
    ghi TKB tốt nhất, không đợi hết thời gian. Chạy ở cả 4 máy Windows của CI."""
    job = Job(run_argv(INPUT_FILE, tmp_path, "mau", {"time_limit": 100, "workers": 4}), tmp_path)
    try:
        deadline = time.time() + 300
        while job.running and not any("Khởi đầu:" in line for line in job.lines):
            assert time.time() < deadline, "\n".join(job.lines[-20:])
            time.sleep(0.2)
        assert job.running, "\n".join(job.lines[-20:])
        job.stop()
        stopped = time.time()
        while job.running:
            assert time.time() - stopped < 90, "\n".join(job.lines[-20:])
            time.sleep(0.2)
    finally:
        job.kill()
    state = job.state()
    assert state["exit"] == 0 and state["stopping"], "\n".join(state["lines"][-20:])
    assert any("Dừng xếp giờ: Ctrl+C" in line for line in state["lines"])
    assert state["summary"]["passed"] is True and (tmp_path / FILE_NAMES["teachers"]).is_file()
