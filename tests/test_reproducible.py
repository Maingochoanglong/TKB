"""Chạy lại (tiến trình mới, thứ tự băm khác) vẫn ra đúng một TKB, ở cả hai chế độ."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tkb import config

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = """
import json, sys
from tkb import config
from tkb.solver import solve
from tests.conftest import CURRICULUM, small_staff
settings = config.Settings(time_limit=5, workers=4, mode=sys.argv[1], overtime_max=2)
sol = solve(small_staff(general=False), CURRICULUM, settings, log=lambda *_: None)
print(json.dumps(sorted((l.class_name, l.day, l.period, l.subject, l.teacher) for l in sol.lessons)))
"""


@pytest.mark.parametrize("mode", config.MODES)
def test_same_timetable_across_runs(mode):
    outputs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        run = subprocess.run([sys.executable, "-c", SCRIPT, mode], cwd=ROOT, env=env,
                             capture_output=True, text=True, check=True)
        outputs.append(run.stdout)
    assert outputs[0] and outputs[0] == outputs[1]


# Mã kết quả tham chiếu của trường nhỏ (time_limit=5, 4 luồng), theo hệ điều hành: OR-Tools bản Windows và
# bản Linux ra TKB khác nhau, nhưng các máy cùng hệ điều hành ra cùng mã. Chạy test này trên máy khác: nếu
# khác mã thì máy đó không ra cùng TKB (thường do khác phiên bản OR-Tools). Đổi mô hình thì cập nhật lại mã.
REFERENCE = {
    "linux": {config.MODE_HIRE: "4B07-C5F1-F641", config.MODE_OVERTIME: "6523-7A90-932C"},
}


@pytest.mark.parametrize("mode", config.MODES)
def test_reference_fingerprint(mode):
    from tkb.solver import solve
    from tests.conftest import CURRICULUM, small_staff
    settings = config.Settings(time_limit=5, workers=4, mode=mode, overtime_max=2)
    code = solve(small_staff(general=False), CURRICULUM, settings, log=lambda *_: None).fingerprint()
    expected = REFERENCE.get(sys.platform, {}).get(mode)
    if expected is None:
        pytest.skip(f"chưa có mã chuẩn cho {sys.platform}; máy này ra {mode} = {code}")
    assert code == expected, f"máy này ra {code}, mã chuẩn của {sys.platform} là {expected}"


def test_ortools_version_is_pinned():
    from tkb.solver import ortools_version
    pins = (ROOT / "requirements.txt").read_text()
    assert f"ortools=={config.ORTOOLS_VERSION}" in pins
    assert ortools_version() == config.ORTOOLS_VERSION


def test_no_wall_clock_limit_in_reproducible_mode():
    from ortools.sat.python import cp_model
    from tkb.solver import _configure
    solver = cp_model.CpSolver()
    _configure(solver, config.Settings(), 240)
    p = solver.parameters
    # Chỉ dừng theo lượng tính toán: máy chậm/bận chạy lâu hơn chứ không ra kết quả khác.
    assert p.max_deterministic_time == 240 and p.max_time_in_seconds > 1e10 and p.interleave_search
