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
    code = main.run(in_dir, out_dir, "nhan_su.xlsx", None, "TKB.xlsx", thoi_gian_toi_da=20)
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
