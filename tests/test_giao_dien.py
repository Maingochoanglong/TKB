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

from tkb import config, kich_ban
from tkb.giao_dien import server as server_module
from tkb.giao_dien.server import (FILE_NAMES, InputError, TOKEN_MARK, Job, make_server, run_argv, safe_name, summary)
from tkb.template import write_staff_template

from .conftest import CURRICULUM, INPUT_FILE, small_staff
from .test_reproducible import REFERENCE


@pytest.fixture
def server(tmp_path):
    httpd, app, url = make_server(port=0, home=tmp_path / "TKB")
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
    assert schema["out_dir"] == str(app.out_dir) and schema["home"] == str(app.home)
    assert app.out_dir == app.home / "ket_qua" and all(Path(p).is_dir() for p in schema["folders"].values())


def test_import_check_save(server):
    """File lấy từ chỗ khác: đọc được thì chép bản gốc vào tep_nhap/. Tệp › Lưu: ba file cùng tên (chương trình học,
    nhân sự, luật) và file vào đủ ở ket_qua/; Mở bộ đó đọc ra đúng kịch bản đã lưu."""
    app, url = server
    body = INPUT_FILE.read_bytes()
    status, data = _call(url, "/api/import", "POST", body, app.token, {"X-File-Name": "Truong%20M%E1%BA%ABu.xlsx"})
    assert status == 200 and len(data["scenario"]["staff"]) == 45 and data["name"] == "Truong Mẫu"
    assert data["sheets"] == ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC", "LỚP", "PHÒNG", "CHỨC VỤ", "QUY ĐỊNH", "LUẬT"]
    kept = Path(data["kept"])
    assert kept == app.folders["imported"] / "Truong Mẫu.xlsx" and kept.read_bytes() == body
    assert Path(_call(url, "/api/import", "POST", body, app.token, {"X-File-Name": quote(kept.name)})[1]["kept"]) == kept
    status, res = _call(url, "/api/check", "POST", {"scenario": data["scenario"], "run": {"overtime_max": 2}}, app.token)
    assert status == 200 and res["errors"] == []
    status, saved = _call(url, "/api/save", "POST", {"scenario": data["scenario"], "name": "a/b"}, app.token)
    assert status == 200 and [Path(p) for p in saved["files"]] == [
        app.folders["program"] / "ab.xlsx", app.folders["staff"] / "ab.xlsx", app.folders["rules"] / "ab.xlsx",
        app.out_dir / "ab.xlsx"]
    status, listed = _call(url, "/api/files", token=app.token)
    assert [x["name"] for x in listed["sets"]] == ["ab"] and set(listed["sets"][0]["parts"]) == {"program", "staff", "rules"}
    kinds = {f["key"]: [(x["name"], x["kind"]) for x in f["files"]] for f in listed["folders"]}
    assert kinds == {"program": [("ab.xlsx", "program")], "staff": [("ab.xlsx", "staff")], "rules": [("ab.xlsx", "rules")],
                     "imported": [("Truong Mẫu.xlsx", "full")], "results": [("ab.xlsx", "full")]}
    status, opened = _call(url, "/api/open_set", "POST", {"name": "AB"}, app.token)
    assert status == 200 and opened["name"] == "AB"
    assert {k: v for k, v in opened["scenario"].items() if k != "saved"} == \
        {k: v for k, v in data["scenario"].items() if k != "saved"}
    assert _call(url, "/api/open_set", "POST", {"name": "khong_co"}, app.token)[0] == 400
    status, err = _call(url, "/api/import", "POST", b"khong phai excel", app.token)
    assert status == 400 and "Excel" in err["error"]
    assert len(list(app.folders["imported"].iterdir())) == 1  # file hỏng không chép vào
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
                                "native": None, "level": None, "tuned": False}  # thiếu "khi … <= số ngày": không phải dạng gốc
    assert data["rules"][1]["text"] is None and "phải có Lớp hoặc Giáo viên" in data["rules"][1]["errors"][0]
    assert data["rules"][2]["text"] == "Tiếng Việt học trước Toán trong buổi (bắt buộc)"
    status, data = _call(url, "/api/describe", "POST", {"scenario": new["scenario"]}, app.token)
    assert all(r["native"] for r in data["rules"]) and len(data["rules"]) == len(new["scenario"]["rules"])
    assert not any(r["tuned"] for r in data["rules"])  # luật có sẵn ghi bằng mức, không ghi điểm
    assert all(r["points"] is None for r in new["scenario"]["rules"])
    old = [{**r, "points": 10, "level": None} if r["level"] == "Thấp" and "trống" in t["text"] else r
           for r, t in zip(new["scenario"]["rules"], data["rules"])]  # bản nháp cũ: luật tiết trống ghi 10 điểm
    status, data = _call(url, "/api/describe", "POST", {"scenario": {**new["scenario"], "rules": old}}, app.token)
    assert [r["level"] for r in data["rules"] if r["tuned"]] == ["Thấp"]
    status, res = _call(url, "/api/rules_file", "POST", {"template": True}, app.token)
    assert status == 200 and [Path(p) for p in res["files"]] == [app.folders["rules"] / "Mau_Luat.xlsx"]
    status, imported = _call(url, "/api/import_path", "POST", {"path": res["files"][0]}, app.token)
    assert imported["sheets"] == ["LUẬT"] and imported["scenario"]["rules"] == new["scenario"]["rules"]
    status, res = _call(url, "/api/rules_file", "POST", {"scenario": new["scenario"], "name": "a"}, app.token)
    assert status == 200 and [Path(p) for p in res["files"]] == [app.folders["rules"] / "a.xlsx"]


def test_blank_template(server, tmp_path):
    """Nút Ghi file mẫu trống: file mẫu trống của python -m tkb.template (chưa có môn, chưa có luật) chia thành ba
    file (chương trình học, nhân sự, luật) ở ba thư mục; mỗi file có đúng các sheet của thực thể đó (và HƯỚNG DẪN),
    nhập lại được."""
    import openpyxl

    app, url = server
    status, res = _call(url, "/api/template", "POST", {}, app.token)
    assert status == 200 and [Path(p) for p in res["files"]] == [
        app.folders["program"] / "Mau_Chuong_Trinh_Hoc.xlsx", app.folders["staff"] / "Mau_Nhan_Su.xlsx",
        app.folders["rules"] / "Mau_Luat.xlsx"]
    write_staff_template(tmp_path / "mau.xlsx", mau="trong")  # mẫu trống: chưa có môn, chưa có luật
    full = {ws.title: list(ws.values) for ws in openpyxl.load_workbook(tmp_path / "mau.xlsx").worksheets}
    for path, key in zip(res["files"], ("program", "staff", "rules")):
        sheets = {ws.title: list(ws.values) for ws in openpyxl.load_workbook(path).worksheets}
        assert set(sheets) == {*kich_ban.ENTITIES[key], "HƯỚNG DẪN"} - {"LUẬT RIÊNG"}
        assert all(sheets[name] == full[name] for name in sheets)
    status, data = _call(url, "/api/import_path", "POST", {"path": res["files"][1]}, app.token)
    assert status == 200 and data["scenario"]["staff"] == [] and data["sheets"] == ["NHÂN SỰ", "CHỨC VỤ"]


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


def test_board_import(server, small_updated):
    """Tệp › Nhập TKB đang dùng: /api/board đọc file TKB toàn trường theo kịch bản đang soạn, trả lưới TKB đã xếp
    (đúng mọi luật như lúc xếp) và báo cáo; file hỏng hay kịch bản còn lỗi thì báo rõ."""
    import base64
    app, url = server
    status, data = _call(url, "/api/import", "POST", small_updated.read_bytes(), app.token,
                         {"X-File-Name": quote(small_updated.name)})
    scenario = {**data["scenario"], "saved": None}
    board = base64.b64encode((small_updated.parent / "TKB_toan_truong.xlsx").read_bytes()).decode()
    body = {"scenario": scenario, "run": {"overtime_max": 4}, "file": board, "name": "tkb.xlsx"}
    status, res = _call(url, "/api/board", "POST", body, app.token)
    assert status == 200 and res["report"]["cells"] > 0 and not res["report"]["unknown_subjects"]
    assert res["lines"][0].startswith("Đọc ") and res["subjects"] and res["teachers"]
    status, view = _call(url, "/api/timetable", "POST", {**body, "scenario": {**scenario, "saved": res["grid"]}},
                         app.token)
    assert status == 200 and view["ok"]
    status, err = _call(url, "/api/board", "POST", {**body, "file": base64.b64encode(b"abc").decode()}, app.token)
    assert status == 400 and "xlsx" in err["error"]
    broken = {**scenario, "staff": []}
    status, err = _call(url, "/api/board", "POST", {**body, "scenario": broken}, app.token)
    assert status == 400 and "còn lỗi" in err["error"]


def test_files_only_inside_the_tkb_folder(server, tmp_path):
    """Trang chỉ đọc, mở file trong thư mục TKB (không đọc du_lieu/ của chương trình); không còn lệnh tải file ra
    ngoài hay đổi thư mục kết quả."""
    app, url = server
    (tmp_path / "ngoai.xlsx").write_bytes(b"x")
    status, err = _call(url, "/api/import_path", "POST", {"path": str(tmp_path / "ngoai.xlsx")}, app.token)
    assert status == 400 and "thư mục TKB" in err["error"]
    assert _call(url, "/api/open", "POST", {"path": str(tmp_path / "ngoai.xlsx")}, app.token)[0] == 400
    assert _call(url, "/api/import_path", "POST", {"path": str(app.data / "trang.json")}, app.token)[0] == 400
    assert _call(url, f"/api/file?path=x&t={app.token}")[0] == 404
    assert _call(url, "/api/settings", "POST", {"out_dir": str(tmp_path)}, app.token)[0] == 404


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
    assert all(Path(p).parent == app.out_dir and Path(p).is_file() for p in result["files"])


def test_open_only_files_inside_the_tkb_folder(server, monkeypatch):
    """Nút Mở file: mở đúng file trong thư mục TKB bằng ứng dụng mặc định (Windows: os.startfile; máy khác:
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
    assert _call(url, "/api/open", "POST", {"path": f"ket_qua/{FILE_NAMES['tkb']}"}, app.token)[0] == 200  # trong thư mục TKB
    assert opened == [target.resolve()] * 2
    status, err = _call(url, "/api/open", "POST", {"path": str(app.out_dir / "khong_co.xlsx")}, app.token)
    assert status == 400 and "Không có" in err["error"] and len(opened) == 2


def test_forget_drops_what_the_server_holds(server):
    """Tệp › Xóa dữ liệu trên máy này: máy chủ bỏ TKB đang xem và nhật ký lần chạy; đang xếp thì từ chối, giữ nguyên;
    file trong thư mục kết quả để nguyên."""
    app, url = server
    app.out_dir.mkdir(parents=True, exist_ok=True)
    kept = app.out_dir / FILE_NAMES["tkb"]
    kept.write_bytes(b"PK")
    running = type("Running", (), {"running": True, "kill": lambda self: None})()
    app.job, app.grid = running, ("khoa", None)
    status, err = _call(url, "/api/forget", "POST", {}, app.token)
    assert status == 400 and "Dừng" in err["error"] and app.job is running and app.grid is not None
    running.running = False
    assert _call(url, "/api/forget", "POST", {}, app.token) == (200, {"ok": True})
    assert app.job is None and app.grid is None and kept.is_file()
    assert _call(url, "/api/status", token=app.token)[1]["lines"] == []


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


def test_page_store_lives_in_the_program_folder(server):
    """Bản nháp và lựa chọn của trang ghi ở file trang.json trong thư mục dữ liệu của chương trình (không ở bộ nhớ
    trình duyệt); Tệp › Xóa dữ liệu trên máy này xóa file đó."""
    app, url = server
    assert _call(url, "/api/store", token=app.token) == (200, {})
    assert _call(url, "/api/store", "POST", {"items": {"tkb-luoi": "1", "tkb-tab": "xep"}}, app.token)[0] == 200
    path = app.data / server_module.STORE_NAME
    assert app.home in path.parents and json.loads(path.read_text(encoding="utf-8"))["tkb-tab"] == "xep"
    assert _call(url, "/api/store", token=app.token)[1] == {"tkb-luoi": "1", "tkb-tab": "xep"}
    # Đóng trang gửi bằng sendBeacon: mã phiên ở địa chỉ (?t=) thay cho tiêu đề.
    assert _call(url, f"/api/store?t={quote(app.token)}", "POST", {"items": {"tkb-luoi": "0"}})[0] == 200
    assert _call(url, "/api/store", "POST", {"items": {}})[0] == 403  # không có mã phiên
    assert json.loads(path.read_text(encoding="utf-8")) == {"tkb-luoi": "0"}
    assert _call(url, "/api/forget", "POST", {}, app.token)[0] == 200
    assert not path.exists() and _call(url, "/api/store", token=app.token)[1] == {}


def test_packaged_app_keeps_everything_in_its_folder(tmp_path, monkeypatch):
    """Bản đóng gói (TKB.exe): kết quả ở ket_qua/, dữ liệu trang ở du_lieu/ cạnh TKB.exe, không ở thư mục người dùng;
    trang mở bằng trình duyệt họ Chromium với hồ sơ riêng trong du_lieu/trinh_duyet, file tải về vào ket_qua/."""
    exe = tmp_path / "TKB" / "TKB.exe"
    monkeypatch.setattr(server_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(server_module.sys, "executable", str(exe))
    assert server_module.default_out_dir() == exe.parent / "ket_qua"
    assert server_module.data_dir() == exe.parent / "du_lieu"
    httpd, app, url = make_server(port=0)
    try:
        assert app.out_dir == (exe.parent / "ket_qua").resolve() and app.data == (exe.parent / "du_lieu").resolve()
        assert {p.name for p in exe.parent.iterdir()} == {"chuong_trinh_hoc", "nhan_su", "luat", "tep_nhap", "ket_qua"}
        started = []
        monkeypatch.setattr(server_module, "find_browser", lambda: "msedge")
        monkeypatch.setattr(server_module.subprocess, "Popen", lambda args, **_: started.append(args))
        server_module.open_page(url, app)
        profile = app.data / "trinh_duyet"
        assert started == [["msedge", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                             f"--app={url}"]]
        prefs = json.loads((profile / "Default" / "Preferences").read_text(encoding="utf-8"))
        assert prefs["download"]["default_directory"] == str(app.out_dir)
    finally:
        httpd.server_close()


def test_page_icons_are_embedded_svg():
    """Biểu tượng của trang là SVG của Bootstrap Icons nhúng trong index.html (tools/bieu_tuong.py): mọi tên trang dùng
    (icon("…") trong app.js, #i-… trong index.html) đều có <symbol>; không dùng ký tự đặc biệt thay biểu tượng."""
    import re
    static = Path(server_module.STATIC)
    page = (static / "index.html").read_text(encoding="utf-8")
    script = (static / "app.js").read_text(encoding="utf-8")
    symbols = set(re.findall(r'<symbol id="i-([a-z0-9-]+)"', page))
    used = set(re.findall(r'icon\("([a-z0-9-]+)"\)', script)) | set(re.findall(r'href="#i-([a-z0-9-]+)"', page))
    used |= {m for pair in re.findall(r'icon\((\w+) \? "([a-z-]+)" : "([a-z-]+)"\)', script) for m in pair[1:]}
    assert used and used <= symbols, used - symbols
    body = re.sub(r"<!-- BIEU_TUONG -->.*?<!-- /BIEU_TUONG -->", "", page, flags=re.S)
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
    for text in (body, code):
        assert not set(text) & set("✓✕⚠↶↷▾▸↑↓←→🔒›"), set(text) & set("✓✕⚠↶↷▾▸↑↓←→🔒›")
