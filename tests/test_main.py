import openpyxl

import main

from .conftest import small_staff


def _write_staff(path, general=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tên", "Chức vụ", "Số tiết"])
    for t in small_staff(general):
        ws.append([t.name, t.title, t.max_lessons])
    wb.save(path)


def test_run_writes_outputs(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx", general=False)
    code = main.run(in_dir, out_dir, "nhan_su.xlsx", None, "TKB.xlsx", thoi_gian_toi_da=20,
                    che_do="tuyen_them")
    assert code == 0
    assert (out_dir / "TKB.xlsx").is_file()
    rows = list(openpyxl.load_workbook(out_dir / "nhan_su_cap_nhat.xlsx").active.iter_rows(values_only=True))
    assert rows[-1] == ("chưa có", "bộ môn 1", 23)


def test_run_reports_missing_file(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "khac.xlsx").write_bytes(b"")
    assert main.run(tmp_path / "in", tmp_path / "out", "khong_co.xlsx", None, "TKB.xlsx") == 1
    out = capsys.readouterr().out
    assert "không tìm thấy file nhân sự" in out and "khac.xlsx" in out


def test_relative_paths_resolve_from_script_dir():
    assert main._resolve("data") == main.BASE_DIR / "data"
    assert (main.BASE_DIR / main.THU_MUC_IN / main.FILE_NHAN_SU).is_file()


def test_run_rejects_bad_thread_count(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx")
    assert main.run(in_dir, tmp_path / "out", "nhan_su.xlsx", None, "TKB.xlsx", so_luong=0) == 1
    assert "SO_LUONG" in capsys.readouterr().out


def test_run_passes_thread_count(tmp_path, monkeypatch):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx")
    seen = {}
    import tkb.__main__ as cli
    monkeypatch.setattr(cli, "main", lambda argv: seen.setdefault("argv", argv) and 0)
    main.run(in_dir, tmp_path / "out", "nhan_su.xlsx", None, "TKB.xlsx", so_luong=4)
    argv = seen["argv"]
    assert argv[argv.index("--workers") + 1] == "4"


def test_run_overtime_mode_needs_no_hire(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx", general=False)
    code = main.run(in_dir, out_dir, "nhan_su.xlsx", None, "TKB.xlsx", thoi_gian_toi_da=20,
                    che_do="bu_gio", so_tiet_bu_toi_da=4)
    assert code == 0
    rows = list(openpyxl.load_workbook(out_dir / "nhan_su_cap_nhat.xlsx").active.iter_rows(values_only=True))
    assert all(r[0] != "chưa có" for r in rows)


def test_run_rejects_bad_mode(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx")
    assert main.run(in_dir, tmp_path / "out", "nhan_su.xlsx", None, "TKB.xlsx", che_do="khac") == 1
    assert "CHE_DO" in capsys.readouterr().out
    assert main.run(in_dir, tmp_path / "out", "nhan_su.xlsx", None, "TKB.xlsx", so_tiet_bu_toi_da=-1) == 1
    assert "SO_TIET_BU_TOI_DA" in capsys.readouterr().out
