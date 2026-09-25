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
    code = main.run(in_dir / "nhan_su.xlsx", out_dir, "TKB.xlsx", thoi_gian_toi_da=20,
                    che_do="tuyen_them")
    assert code == 0
    assert (out_dir / "TKB.xlsx").is_file()
    rows = list(openpyxl.load_workbook(out_dir / "nhan_su_cap_nhat.xlsx").active.iter_rows(values_only=True))
    assert rows[-1] == ("chưa có", "bộ môn 1", 23)
    stats = list(openpyxl.load_workbook(out_dir / "Thong_Ke.xlsx").active.iter_rows(values_only=True))
    assert stats[-2][1:5] == ("tuyển thêm", "bộ môn 1", 23, 0)


def test_run_reports_missing_file(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "khac.xlsx").write_bytes(b"")
    assert main.run(tmp_path / "in" / "khong_co.xlsx", tmp_path / "out", "TKB.xlsx") == 1
    out = capsys.readouterr().out
    assert "không tìm thấy file vào" in out and "khac.xlsx" in out


def test_relative_paths_resolve_from_script_dir():
    assert main._resolve("data") == main.BASE_DIR / "data"
    assert main._resolve(main.FILE_VAO).is_file()


def test_run_rejects_bad_thread_count(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx")
    assert main.run(in_dir / "nhan_su.xlsx", tmp_path / "out", "TKB.xlsx", so_luong=0) == 1
    assert "SO_LUONG" in capsys.readouterr().out


def test_run_passes_thread_count(tmp_path, monkeypatch):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx")
    seen = {}
    import tkb.__main__ as cli
    monkeypatch.setattr(cli, "main", lambda argv: seen.setdefault("argv", argv) and 0)
    main.run(in_dir / "nhan_su.xlsx", tmp_path / "out", "TKB.xlsx", so_luong=4)
    argv = seen["argv"]
    assert argv[argv.index("--workers") + 1] == "4"


def test_run_overtime_mode_needs_no_hire(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx", general=False)
    code = main.run(in_dir / "nhan_su.xlsx", out_dir, "TKB.xlsx", thoi_gian_toi_da=20,
                    che_do="bu_gio", so_tiet_bu_toi_da=4)
    assert code == 0
    rows = list(openpyxl.load_workbook(out_dir / "nhan_su_cap_nhat.xlsx").active.iter_rows(values_only=True))
    assert all(r[0] != "chưa có" for r in rows)


def test_run_rejects_bad_mode(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _write_staff(in_dir / "nhan_su.xlsx")
    assert main.run(in_dir / "nhan_su.xlsx", tmp_path / "out", "TKB.xlsx", che_do="khac") == 1
    assert "CHE_DO" in capsys.readouterr().out
    assert main.run(in_dir / "nhan_su.xlsx", tmp_path / "out", "TKB.xlsx", so_tiet_bu_toi_da=-1) == 1
    assert "SO_TIET_BU_TOI_DA" in capsys.readouterr().out


def test_run_single_input_file_with_program_sheet(tmp_path, capsys):
    from tkb.template import write_staff_template
    src = tmp_path / "input.xlsx"
    write_staff_template(src, small_staff(general=False))  # có sheet NHÂN SỰ và CHƯƠNG TRÌNH HỌC
    code = main.run(src, tmp_path / "out", "TKB.xlsx", thoi_gian_toi_da=20, che_do="tuyen_them")
    assert code == 0
    assert "chương trình học: sheet CHƯƠNG TRÌNH HỌC của file vào" in capsys.readouterr().out
    wb = openpyxl.load_workbook(tmp_path / "out" / "input_cap_nhat.xlsx")
    assert wb.sheetnames[:2] == ["NHÂN SỰ", "CHƯƠNG TRÌNH HỌC"]  # file cập nhật vẫn là file vào đầy đủ
    rows = [r for r in wb["NHÂN SỰ"].iter_rows(values_only=True) if any(v is not None for v in r)]
    assert rows[-1] == ("=ROW()-1", "chưa có", "Bộ Môn", None, 23, None)
