# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Timetable (TKB) generator for a Vietnamese primary school, Python + OR-Tools CP-SAT. Input: one Excel file with
sheets `NHÂN SỰ` (staff) and `CHƯƠNG TRÌNH HỌC` (lessons per subject per grade). Output: `TKB.xlsx` (timetable
only), `TKB_chuc_vu.xlsx` (same timetable, teacher name + role code; both split into `*_diem_chinh`/`*_diem_phu` when
the file has campus-2 classes, `writer.campus_paths`), `Thong_Ke.xlsx` (one table: lessons per subject
per teacher + total, quota, overtime, spare, and with campus 2 who moves between campuses (`campus_moves`); spare rows blue; overtime rows yellow, their overtime subject cells orange, per-subject overtime in the text column `Môn Dạy Bù` (`Lesson.overtime`); in
`bu_gio` with a shortage only the sheet `Thiếu tiết`), `<input>_cap_nhat.xlsx` (input + hires + result columns incl. `Số Tiết Dư`; rows coloured: overtime
yellow, hire green, spare blue, explained in a `Chú thích` sheet — the simple stats in input layout). Output files hold
plain values and colours only: no cell comments, formulas, frozen panes, dropdowns or conditional formats
(`writer.plain_values`). Code comments,
docstrings, docs and printed messages are Vietnamese; keep that style.

## Working rules
- **Talk to the user in Vietnamese.** Commit messages in English (existing style); PR titles/bodies in Vietnamese.
- Only the V8 input format is read (headers `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần`, titles without numbers,
  sheet `CHƯƠNG TRÌNH HỌC` required; optional `Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ`). Class names
  are `g/n` or grade + name (`1D15`): use `staff.grade_of` / `class_sort_key`, never split on "/". `data/` holds the school's real file `INPUT_V8.xlsx` and the output templates
  `Output_Template_{TKB,Thong_Ke}_V8.xlsx`. Tests use a generated fake-name school: `tests/du_lieu_mau.py`
  (`CURRICULUM`, `sample_staff()`, `write_sample_input()`); `tests/conftest.py` writes it to a temp `INPUT_FILE`
  and has `small_staff()` plus `teacher(name, "bộ môn 1", lessons)` for hand-made staff.
- **Privacy:** `data/INPUT_V8.xlsx` is the school's real file (real teacher names). Never print, quote, commit or
  upload teacher names or output files made from it (root `TKB.xlsx`, `Thong_Ke.xlsx`, `*_cap_nhat.xlsx`, `out/`
  are git-ignored). When analysing its output, read subject names only. CI runs this file but uploads only the
  result-code line, never `out/`.
- Never hard-code school data (classes, subjects, lesson counts, teachers) in code: it all comes from the input
  file. `tkb/config.py` holds only rules the file does not contain.
- Hard rules are the school's decisions: do not loosen or tighten one without asking.

## Commands
```bash
pip install -r requirements.txt              # pinned ortools==9.15.6755, openpyxl==3.1.5 (other versions => other results)
python -m pytest -q                          # full suite, ~2.5 min on Linux (slowest: tests/test_lns.py ~1 min)
python -m pytest tests/test_solver.py -k contiguous -q    # one test
python -m pytest tests/test_reproducible.py  # ~20 s: this OS's reference result codes
python tools/code_map.py [solver checker ...] # function index with file:line — use it instead of opening files
python tools/code_map.py --write             # regenerate docs/CODE_MAP.md (tests/test_code_map.py fails if stale)
python main.py                               # school's real file (FILE_VAO) -> project root; real names! ~10 min
python tools/mau_dau_ra.py                   # regenerate data/Output_Template_*_V8.xlsx from the fake school (~10 min)
python -m tkb <input.xlsx> -o out/TKB.xlsx [--mode bu_gio] [--time-limit 30] [--no-student-rules]
python -m tkb.template <new.xlsx>            # blank input template
```
No linter/formatter is configured. CLI default `--mode` is `tuyen_them`; `main.py` default `CHE_DO` is `bu_gio`.
Exit codes: 0 ok, 1 input/solve error, 2 checker found violations, 3 `bu_gio` shortage (table in the statistics file).

## Architecture
`main.run()` validates the constants at the top of `main.py` and calls `tkb.__main__.main(argv)`:
`program.read_program` + `staff.read_staff` → `solver.solve` → `checker.check` → `writer.write_timetable`,
`write_timetable(with_codes=True)`, `write_updated_staff`, `write_statistics` (all output styles copied from the input via
`style.Style.from_file`, which skips the program's own row colours `style.MARK_FILLS`); `solver.ShortageError` →
`writer.write_shortage`. The updated input stores the timetable in sheet `TKB đã xếp` (`config.SAVED_SHEET`); reloading
it (`staff.read_saved_timetable` → `solver.reuse`, teachers matched by Mã GV, `checker.check` must pass) skips
solving, so renaming "chưa có" hires keeps the timetable and the code; `main.py` `GIU_TKB_DA_XEP = False` /
`--xep-lai` forces a re-solve.

`solver.solve` (both modes share one timetable; only who teaches the overtime cells differs):
1. `allocation.build_problem` → `Problem`: one `Course` per (class, subject) with lesson count, candidate
   teachers, fixed slots; homeroom share from `split_homeroom`; supplement teachers named "chưa có".
2. `phan_cong.phan_cong` (pure Python, no CP-SAT, integer and fixed order ⇒ same on every OS): min-cost flow for
   the estimate (missing lessons, overtime per teacher, homeroom first, +1 before +2), then local search for
   class grouping → `PhanCong`. Printed as "Dự toán"/"Bù:". `bu_gio` with missing lessons → `ShortageError`.
3. `tach_tiet_bu`: overtime lessons (+ missing ones in `tuyen_them`) go to hired "bộ môn n+1…" supplements,
   heaviest first (the `_Allocation` symmetry rule), ≤ one pair per session each.
4. `timetable(fixed=...)`: `build_timetable` makes ONE global CP-SAT model over all lessons (`x[course, (day,
   period)]`, `z[course, teacher, slot]` booleans, hard constraints + soft objective weighted by `config.Weights`),
   then `lns.improve`: CP-SAT start with 20% of the budget (≤ 120), then rounds of QA (cost per class-day) and re-solving
   regions (class, hot spot, shared-teacher classes, grade, day pair) with everything else fixed; stops on budget,
   a round gaining < 0.3%, 10 rounds, or Ctrl+C. Budget is deterministic time ⇒ reproducible. `bu_gio` then
   relabels hire lessons back to their owners (`_to_overtime`), so both modes place every lesson in the same cell.
5. If infeasible (`tuyen_them` only): integrated model (`_Allocation` + timetable, single CP-SAT solve) with +1, then
   +3 spare supplements.

`checker.check` re-verifies every hard rule independently of the model: a new hard rule goes in both
`solver.timetable` and `checker`. Slots are `(day 0–4, period 1–7)`: 1–4 morning, 5–7 afternoon, Friday
afternoon off (`config.DAY_SESSIONS`). Subject names in config match file names loosely via
`staff.subject_key` → `program.canonical_subject`.

| Rule | `tkb/config.py` | Implemented in |
|---|---|---|
| Subject group (TV+TV TC, Toán+Toán TC) ≤ 2 per session; Toán ≤ 1 per day; groups ≥ 6 lessons with even total in consecutive pairs; same subject contiguous in a session; TC lesson after every main lesson of its group that day, and the day has one (hard) | `SUBJECT_GROUPS`, `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, `PAIR_MIN_LESSONS`, `PAIR_EXCLUDED` | `solver.timetable` "Luật bảo vệ học sinh" block; `checker._check_student_rules`; `allocation.paired_groups` |
| Consecutive lessons of a group by one teacher; homeroom priority group: GVCN's lesson first in the week (hard, always) | `SUBJECT_GROUPS`, `HOMEROOM_PRIORITY` | `solver.timetable` "Liên tiết", "GVCN trước"; `checker._check_teacher_order` |
| HĐTN Mon p1 + Fri p4 fixed, rest Tue–Thu near session end | `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS` | `allocation.build_problem`, `solver.allowed_slots`, objective `hdtn_flex_distance` |
| Period 1 always the homeroom teacher | `HOMEROOM_PERIODS` | `solver.allowed_slots` |
| Who may teach what | `HOMEROOM_ONLY_SUBJECTS`, `GENERAL_FORBIDDEN_SUBJECTS`, `MANAGER_RULES` | `allocation.roles_for_subject`, `manager_allowed` |
| Homeroom share: keep / cut / fill order | `HOMEROOM_PRIORITY`, `HOMEROOM_CUT_ORDER`, `HOMEROOM_FILL_ORDER` | `allocation.split_homeroom` |
| Estimate + assignment, overtime homeroom first, max +2 (`main.py` `SO_TIET_BU_TOI_DA` = 3 for the school file); GVCN overtime never in specialist subjects except Âm nhạc/Mỹ thuật, capped by the flow estimate | `OVERTIME_ROLES`, `OVERTIME_MAX`, `HOMEROOM_OVERTIME_SPECIALIST`, `Weights.overtime_*`, `Weights.group_*` | `phan_cong.phan_cong` (`_flow`, `_homeroom_extra`, `_Local`); `solver._Allocation._overtime` in the fallback |
| Soft: heavy subjects at p7, TV/Toán mornings, spread, day load, teacher gaps | `HEAVY_*`, `MORNING_SUBJECTS`, `Weights` | `solver.build_timetable` objective blocks; `lns._Search.qa` mirrors them to rank regions (keep in sync) |
| Campuses: a teacher teaches at one campus per session (hard), soft penalty per teacher-day at both campuses (whole-day hard was infeasible); maternity/`Cơ sở 2` non-homeroom teach only campus-2 classes; `Buổi Nghỉ` fixed and "n buổi" leave (hard) | columns → `Teacher.campus2/maternity/off_sessions/off_any`, `Problem.campus2`; `Weights.campus_day_switch` | `allocation.build_problem` (eligibility), `phan_cong.teacher_slots`, `solver._teacher_sessions`, `solver._campus_day_switch` (+ `lns._Search.qa`); `checker._check_teacher_sessions` |
| Overtime order: homeroom contract → homeroom → general contract → general; maternity no overtime; keep old grade then class (`Lớp Đang Dạy`) | `Weights.overtime_*`, `keep_grade`, `keep_class` | `allocation.overtime_cost`, `keep_cost`, `overtime_allowance`; used in `phan_cong._flow`, `_Local._part`, `solver._Allocation` |
| Timetabling loop: start share (≤ `LNS_START_MAX`), region limits, stop rules | `LNS_*`, `Settings.time_limit` (1200) | `lns.improve`, `lns._Search.regions` |

Glossary: GVCN/chủ nhiệm = homeroom teacher; bộ môn = general subject teacher; GV chuyên biệt = specialist (role
name = subject name); quản lý = manager; tuyển thêm = hire "chưa có"; bù giờ = overtime; tiết = period; buổi =
session; khối = grade; TC/tăng cường = extra lessons (separate subjects); HĐTN, TNXH, TV = subject abbreviations;
cơ sở = campus; thai sản = maternity; hợp đồng = contract teacher; buổi nghỉ = requested day-part off.

## Reproducibility (read before changing the solver)
- Default reproducible mode (`solver._configure`): deterministic time budget, `interleave_search`, clause and
  level-zero-bound sharing off. Same input + `main.py` constants + pinned libs ⇒ same timetable on the same OS.
  Windows and Linux give different (equally valid) timetables.
- `Solution.fingerprint()` is the "Mã kết quả"; it is only printed (`chay_mau.py` reads it from stdout).
- Any change to constraints, objective, weights, solver params or model-building order changes the codes. Update:
  `tests/test_reproducible.py` `REFERENCE` (Linux: run the test, the failure message shows the new code;
  `win32`: from the Windows workflow logs; an OS without a reference is skipped and prints its code), README table
  "Chạy trên máy khác" (codes of `python main.py`), the spec (§0 history row, §9), and the output templates
  (`python tools/mau_dau_ra.py`).
- Current codes: small school (`tuyen_them`/`bu_gio`) Linux `4CCD-C868-AF11`/`51DE-A8CB-6CB7`, Windows the same
  (the small school is proven optimal at the LNS start, so these did not change with LNS);
  `python main.py` (school file as of now) Linux `5C2B-510F-5156`, Windows `08F4-E2C6-3470`; fake school of
  `tests/du_lieu_mau.py` with main.py constants Linux `72C2-3315-CE24`. Editing `INPUT_V8.xlsx` changes the main.py codes.

## CI (`.github/workflows/`, repo is public so minutes are free)
- `windows.yml`: on PRs and pushes to main; 4 VMs (windows-2022/2025 × Python 3.12/3.14) run pytest and
  `.github/scripts/chay_mau.py` (`FILE_VAO` twice, uploads only the code); a Linux job fails if any VM's code
  differs (~35 min).
- `file_that_windows.yml`: manual (or when the file itself changes); same run once on 2 VMs with Python 3.14.

## Docs (open only the section you need)
- `docs/CODE_MAP.md`: generated function index (prefer `python tools/code_map.py <filter>`).
- `README.md`: user guide — `main.py` constants, input format, outputs, business rules.
- `docs/Dac_Ta_Nghiep_Vu_TKB_V16.md`: full spec. §0 change history (add a row per rule change), §5 homeroom,
  §6 student rules, §7 shortage modes, §8 objectives and weights, §9 solve process and reproducibility,
  §11 outputs, §13 reference results.
- `docs/Tham_Khao_TKB_Truong_Khac.md`: how other schools arrange subjects; §5 proposals (5.1 done, 5.2 dropped); §6 not adopted (incl. the homeroom-gap trial).
