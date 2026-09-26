# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Timetable (TKB) generator for a Vietnamese primary school, Python + OR-Tools CP-SAT. Input: one Excel file with
sheets `NHÂN SỰ` (staff) and `CHƯƠNG TRÌNH HỌC` (lessons per subject per grade). Output: `TKB.xlsx` (timetable
only), `Thong_Ke.xlsx` (overview, staff, statistics), `<input>_cap_nhat.xlsx` (input + hires). Code comments,
docstrings, docs and printed messages are Vietnamese; keep that style.

## Working rules
- **Talk to the user in Vietnamese.** Commit messages in English (existing style); PR titles/bodies in Vietnamese.
- Data files: `data/INPUT_V8.xlsx` (school's real file), `data/Input_TKB_V8.xlsx` (fake-name V8 sample used by
  tests/CI), `data/Output_Template_{TKB,Thong_Ke}_V8.xlsx` (output templates made from the sample). Only V8.
- **Privacy:** `data/INPUT_V8.xlsx` is the school's real file (real teacher names). Never print, quote, commit or
  upload teacher names or output files made from it (root `TKB.xlsx`, `Thong_Ke.xlsx`, `*_cap_nhat.xlsx`, `out/`
  are git-ignored). When analysing its output, read subject names only. CI uses the fake-name sample
  `data/Input_TKB_V8.xlsx`; the only exception, `file_that_windows.yml`, uploads just the result-code line.
- Never hard-code school data (classes, subjects, lesson counts, teachers) in code: it all comes from the input
  file. `tkb/config.py` holds only rules the file does not contain.
- Hard rules are the school's decisions: do not loosen or tighten one without asking.

## Commands
```bash
pip install -r requirements.txt              # pinned ortools==9.15.6755, openpyxl==3.1.5 (other versions => other results)
python -m pytest -q                          # full suite, ~1.5 min on Linux (slowest: test_real_data_* ~20 s)
python -m pytest tests/test_solver.py -k contiguous -q    # one test
python -m pytest tests/test_reproducible.py  # ~20 s: this OS's reference result codes
python tools/code_map.py [solver checker ...] # function index with file:line — use it instead of opening files
python tools/code_map.py --write             # regenerate docs/CODE_MAP.md (tests/test_code_map.py fails if stale)
python -c "import main; main.run('data/Input_TKB_V8.xlsx', 'out')"   # sample data, ~4 min, prints "Mã kết quả"
python tools/mau_dau_ra.py                   # regenerate data/Output_Template_*_V8.xlsx from the sample (~4 min)
python main.py                               # school's real file (FILE_VAO) -> project root; real names!
python -m tkb <input.xlsx> -o out/TKB.xlsx [--mode bu_gio] [--time-limit 30] [--no-student-rules]
python -m tkb.template <new.xlsx>            # blank input template
```
No linter/formatter is configured. CLI default `--mode` is `tuyen_them`; `main.py` default `CHE_DO` is `bu_gio`.

## Architecture
`main.run()` validates the constants at the top of `main.py` and calls `tkb.__main__.main(argv)`:
`program.load_curriculum` + `staff.read_staff` → `solver.solve` → `checker.check` → `writer.write_timetable`,
`write_updated_staff`, `write_statistics` (all output styles copied from the input via `style.Style.from_file`).

`solver.solve`:
1. `allocation.build_problem` → `Problem`: one `Course` per (class, subject) with lesson count, candidate
   teachers, fixed slots; homeroom share from `split_homeroom`; supplement teachers named "chưa có".
2. `assign()`: CP-SAT on teacher↔course lesson counts only (`_Allocation`), lexicographic: missing lessons /
   hires / overtime proven optimal first, then secondary goals (splits, balance) with hints.
3. `timetable(fixed=assignment)`: ONE global CP-SAT over all lessons, `x[course, (day, period)]` booleans, hard
   constraints + soft objective weighted by `config.Weights`. Not greedy per subject.
4. If infeasible: integrated model (assignment + timetable) with +1, then +3 spare supplements.

`checker.check` re-verifies every hard rule independently of the model: a new hard rule goes in both
`solver.timetable` and `checker`. Slots are `(day 0–4, period 1–7)`: 1–4 morning, 5–7 afternoon, Friday
afternoon off (`config.DAY_SESSIONS`). Subject names in config match file names loosely via
`staff.subject_key` → `program.canonical_subject`.

| Rule | `tkb/config.py` | Implemented in |
|---|---|---|
| Max TV/Toán per session; same subject contiguous in a session (hard) | `SESSION_SUBJECT_LIMITS` | `solver.timetable` "Luật bảo vệ học sinh" block; `checker._check_student_rules` |
| HĐTN Mon p1 + Fri p4 fixed, rest Tue–Thu near session end | `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS` | `allocation.build_problem`, `solver.allowed_slots`, objective `hdtn_flex_distance` |
| Period 1 always the homeroom teacher | `HOMEROOM_PERIODS` | `solver.allowed_slots` |
| Who may teach what | `HOMEROOM_ONLY_SUBJECTS`, `GENERAL_FORBIDDEN_SUBJECTS`, `MANAGER_RULES` | `allocation.roles_for_subject`, `manager_allowed` |
| Homeroom share: keep / cut / fill order | `HOMEROOM_PRIORITY`, `HOMEROOM_CUT_ORDER`, `HOMEROOM_FILL_ORDER` | `allocation.split_homeroom` |
| Overtime mode (`bu_gio`), homeroom first | `OVERTIME_ROLES`, `OVERTIME_MAX`, `Weights.overtime_*` | `solver._Allocation._overtime` |
| Soft: heavy subjects at p7, TV/Toán mornings, spread, day load, teacher gaps | `HEAVY_*`, `MORNING_SUBJECTS`, `AFTERNOON_SUBJECTS`, `Weights` | `solver.timetable` objective blocks |

Glossary: GVCN/chủ nhiệm = homeroom teacher; bộ môn = general subject teacher; GV chuyên biệt = specialist (role
name = subject name); quản lý = manager; tuyển thêm = hire "chưa có"; bù giờ = overtime; tiết = period; buổi =
session; khối = grade; TC/tăng cường = extra lessons (separate subjects); HĐTN, TNXH, TV = subject abbreviations.

## Reproducibility (read before changing the solver)
- Default reproducible mode (`solver._configure`): deterministic time budget, `interleave_search`, clause and
  level-zero-bound sharing off. Same input + `main.py` constants + pinned libs ⇒ same timetable on the same OS.
  Windows and Linux give different (equally valid) timetables.
- `Solution.fingerprint()` is the "Mã kết quả" printed and written to `Thong_Ke.xlsx` › Tổng quan.
- Any change to constraints, objective, weights, solver params or model-building order changes the codes. Update:
  `tests/test_reproducible.py` `REFERENCE` (Linux: run the test, the failure message shows the new code;
  `win32`: from the Windows workflow logs; an OS without a reference is skipped and prints its code), README table "Chạy trên máy khác" (sample-data
  codes), the spec (§0 history row, §9), and the output templates (`python tools/mau_dau_ra.py`).
- Current codes: small school Linux `60A5-5219-142F`/`F08D-1913-F355`, Windows `BAB3-230A-56C1`/`8D95-DAE4-E979`;
  sample data Linux `A77F-F330-8C78`, Windows `CAAD-454D-9F0F`.

## CI (`.github/workflows/`, repo is public so minutes are free)
- `windows.yml`: on PRs and pushes to main; 4 VMs (windows-2022/2025 × Python 3.12/3.14) run pytest and
  `.github/scripts/chay_mau.py` (sample data twice); a Linux job fails if any VM's code differs (~25 min).
- `file_that_windows.yml`: manual (or when the file itself changes); runs `FILE_VAO` on 2 VMs, compares codes.

## Docs (open only the section you need)
- `docs/CODE_MAP.md`: generated function index (prefer `python tools/code_map.py <filter>`).
- `README.md`: user guide — `main.py` constants, input format, outputs, business rules.
- `docs/Dac_Ta_Nghiep_Vu_TKB_V16.md`: full spec. §0 change history (add a row per rule change), §5 homeroom,
  §6 student rules, §7 shortage modes, §8 objectives and weights, §9 solve process and reproducibility,
  §11 outputs, §13 reference results.
- `docs/Tham_Khao_TKB_Truong_Khac.md`: how other schools arrange subjects; §5 proposals (5.1 done).
