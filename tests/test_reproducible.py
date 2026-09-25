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
from tests.conftest import small_staff
settings = config.Settings(time_limit=5, workers=4, mode=sys.argv[1], overtime_max=2)
sol = solve(small_staff(general=False), None, settings, log=lambda *_: None)
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
