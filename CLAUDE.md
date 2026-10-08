# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Timetable (TKB) generator for a Vietnamese primary school, Python + OR-Tools CP-SAT. Input: one Excel file with
sheets `NHÂN SỰ` (staff) and `CHƯƠNG TRÌNH HỌC` (lessons per subject per grade). Output: `TKB.xlsx` (timetable
only), `TKB_chuc_vu.xlsx` (same timetable, teacher name + role code; both split into `*_diem_chinh`/`*_diem_phu` when
the file has campus-2 classes, `writer.campus_paths`), `TKB_giao_vien.xlsx` (`writer.write_teacher_timetable`: one
block per teacher, a page break after each, plus sheet `Tổng hợp` one row per teacher), `Thong_Ke.xlsx` (sheet
`Chất lượng` = `writer.quality_rows`: violations/points per row of sheet LUẬT counted with `bo_ghep.violations`; sheet
`Thống kê`, one table: lessons per subject
per teacher + total, quota, overtime, spare, and with campus 2 who moves between campuses (`campus_moves`); spare rows blue; overtime rows yellow, their overtime subject cells orange, per-subject overtime in the text column `Môn Dạy Bù` (`Lesson.overtime`); in
`bu_gio` with a shortage only the sheet `Thiếu tiết`), `<input>_cap_nhat.xlsx` (input + hires + result columns incl. `Số Tiết Dư`; rows coloured: overtime
yellow, hire green, spare blue, explained in the rewritten `HƯỚNG DẪN` sheet — the simple stats in input layout;
it also writes all rules used and the saved timetable grid `TKB đã xếp`). Output files hold
plain values and colours only: no cell comments, formulas, frozen panes, dropdowns or conditional formats
(`writer.plain_values`); print setup (landscape, fit to width, page breaks) is allowed. Code comments,
docstrings, docs and printed messages are Vietnamese; keep that style.

## Working rules
- **Talk to the user in Vietnamese.** Commit messages in English (existing style); PR titles/bodies in Vietnamese.
- Only the V8 input format is read (headers `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần`, titles without numbers,
  sheet `CHƯƠNG TRÌNH HỌC` required; optional `Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ`; optional
  business rules, one rule per column, every cell Có/Không/positive integer except `Tên trong TKB`: per-subject rules
  are extra columns of `CHƯƠNG TRÌNH HỌC`, the rest is sheet `QUY ĐỊNH` with three stacked tables (general | days |
  periods); school-defined specialist roles teaching several subjects are rows of sheet `CHỨC VỤ`; **every scheduling
  rule, built-in ones included, is a row of sheet `LUẬT`** (old files: sheet `LUẬT RIÊNG`; see Architecture).
  `python -m tkb.template` writes a plain template (black text, no fill/freeze/dropdowns/comments/hidden sheets) with
  NHÂN SỰ, CHƯƠNG TRÌNH HỌC (+ rule columns), CHỨC VỤ, QUY ĐỊNH, LUẬT (the built-in rule rows), HƯỚNG DẪN. Class names
  are `g/n` or grade + name (`1D15`): use `staff.grade_of` / `class_sort_key`, never split on "/". `data/` holds the school's real file `INPUT_V8.xlsx`, the blank input template
  `Input_Template_V8.xlsx` (`python -m tkb.template`, a test checks it is current) and the output templates
  `Output_Template_{TKB,Thong_Ke}_V8.xlsx`. Tests use a generated fake-name school: `tkb/truong_mau.py`
  (`CURRICULUM`, `sample_staff()`, `write_sample_input()`; demo data, also the UI's "Xem thử với trường mẫu" via
  `kich_ban.sample_scenario`, never read by the solver); `tests/conftest.py` writes it to a temp `INPUT_FILE`
  and has `small_staff()` plus `teacher(name, "bộ môn 1", lessons)` for hand-made staff.
- **Privacy:** `data/INPUT_V8.xlsx` is the school's real file (real teacher names). Never print, quote, commit or
  upload teacher names or output files made from it (root `TKB.xlsx`, `Thong_Ke.xlsx`, `*_cap_nhat.xlsx`, `out/`
  are git-ignored). When analysing its output, read subject names only. CI runs this file but uploads only the
  result-code line, never `out/`.
- Never hard-code school data (classes, subjects, lesson counts, teachers) in code: it all comes from the input
  file. `tkb/config.py` holds the defaults of the rules (overridden by the file's rules), weights and LNS
  params. A new business rule the school may want to change gets a `Col` in `tkb/rules.py` (read in `_Reader`,
  written in `rule_tables`/`subject_columns`, listed in `ATTRS`), keeping the Có/Không/number convention.
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
python -m tkb.giao_dien [--khong-mo-trinh-duyet] [--thu-muc DIR] [--cong 8765]  # local web UI (or giao_dien.py)
```
No linter/formatter is configured. CLI default `--mode` is `tuyen_them`; `main.py` default `CHE_DO` is `bu_gio`.
Exit codes: 0 ok, 1 input/solve error, 2 checker found violations, 3 `bu_gio` shortage (table in the statistics file).

## Architecture
`main.run()` validates the constants at the top of `main.py` and calls `tkb.__main__.main(argv)`:
`rules.read_rules` (rule columns of `CHƯƠNG TRÌNH HỌC` + sheet `QUY ĐỊNH` → config attribute values; missing
sheet/table/column = default; all errors at once; unknown program columns only warn; the old 4-sheet format is an
error) then everything runs
inside `with rules.applied(values)`, which sets those `config.*` module attributes and restores them afterwards (code
reads `config.X` at call time, never copies it at import). A sheet with the defaults gives the same codes as no
sheet. `program.read_program` + `staff.read_staff` → `solver.solve` → `checker.check` → `writer.write_timetable`,
`write_timetable(with_codes=True)`, `write_updated_staff` (adds the missing rule columns/rows and sheet `QUY ĐỊNH`,
rewrites `HƯỚNG DẪN` with the result notes, writes the saved timetable grid), `write_statistics` (all output styles copied from the input via
`style.Style.from_file`, which skips the program's own row colours `style.MARK_FILLS`); `solver.ShortageError` →
`writer.write_shortage`. The updated input stores the timetable in sheet `TKB đã xếp` (`config.SAVED_SHEET`), a grid like the TKB
(`Lớp | Tiết | Thứ 2…`, cell "subject\nMã GV", " (bù)" for overtime, row 1 = result code + rules code); reloading
it (`staff.read_saved_timetable` → `solver.reuse`, teachers matched by Mã GV, `checker.check` must pass, and the
saved rules code must equal `rules.code()`) skips
solving, so renaming "chưa có" hires keeps the timetable and the code. Otherwise (checker fails, rules changed) it
re-solves with **minimal change**: `solver.solve(previous=rows)` → `previous_from` (cells readable with the new
file) → `Teacher.previous` + `allocation.previous_cost` (`Weights.keep_previous`) in assignment, `_keep_previous` in
`build_timetable` (`Weights.keep_cell` per moved cell, cells marked " (khóa)" = `config.SAVED_LOCKED` are hard,
infeasible locks are released and retried; no `AddHint`: OR-Tools 9.15 + interleave_search aborts on hints of an
infeasible model), `Lesson.locked` writes the mark back, `writer.change_rows` → sheet `Thay đổi`. `main.py`
`GIU_TKB_DA_XEP = False` / `--xep-lai` re-solves from scratch.

Web UI (`giao_dien.py` → `tkb.giao_dien`): a stdlib `ThreadingHTTPServer` on 127.0.0.1 (Host check + per-start token
`X-TKB-Token`, injected into `static/index.html`; files opened/served only inside the output folder, default
`out/giao_dien`) serving a no-dependency HTML/JS page. The page edits a "kịch bản" (`tkb/kich_ban.py`): the V8 input as
JSON whose columns come from `rules.py` `Col`s (`kich_ban.schema`), so a new rule column appears in the UI by itself
(subject detail groups `kich_ban.SUBJECT_GROUPS`, ungrouped columns go to "Khác"). Steps: Khung giờ → Môn học (list +
detail dialog) → Chức vụ (built-in role cards edit the subject columns named in `kich_ban.ROLE_RULES`; custom roles =
`scenario["roles"]`, imported files also list subject-named roles teachers use) → Giáo viên (role select; the detail
dialog picks `Lớp Đang Dạy` from the homeroom classes and `Buổi Nghỉ` as day × session boxes plus "n buổi"
counts, written as the same text `staff.parse_classes`/`parse_off` read) → Luật (all rules grouped, read-back
sentences, composer dialog) →
Kiểm tra & xếp; renaming a subject/role updates roles, custom rules and staff in the page. First visit (no draft, or
Tệp › Bắt đầu lại) shows a start screen (open file / new / fake sample `/api/sample`); all file actions are in the
`Tệp ▾` menu. Every edit goes through `changed()` in app.js: draft save, an undo snapshot 0.6 s after the last edit
(`snap`/`travel`, 50 steps, Ctrl+Z/Y outside text fields; deletes show "Đã xóa … [Hoàn tác]" instead of confirm), and
a quick check 1.5 s later (`/api/check` with `quick`: `kich_ban.check(quick=True)` stops before `phan_cong`) whose
errors are split per step by the sheet named in the message (`sheetOf`/`sheetTab`) into tab marks ✓/⚠ n, a per-step
error box and red rows (`markRows`, `data-row` = Excel row).
Import (`/api/import` → `kich_ban.from_excel` + `sheets_in`) opens a dialog to take only some parts (staff replace/append,
subjects+grades, roles, frame, custom rules, saved grid) into the current scenario; `/api/template` gives the blank template.
`kich_ban.to_excel` writes it with `template.write_input` (same layout as the template); `from_excel` reads staff/program
cells as written and rules via `read_rules` + `rule_tables`/`subject_columns` (missing ones = defaults), keeping sheet
`TKB đã xếp`; `check` writes a temp file and reads it back with the real readers, then runs the estimate
(`build_problem` + `phan_cong`, no CP-SAT). Runs are `python -m tkb` subprocesses (`server.Job`, argv like `main.run`),
so UI results equal CLI codes; Stop sends SIGINT (Windows: CTRL_BREAK → SIGBREAK, also handled in `lns.improve`). The
check/import path changes `config` via `rules.applied`, so `App.lock` serialises it. Run settings (mode, max overtime,
time) live in the UI, not in the Excel file.

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

Conflicting rules (`tkb/chan_doan.py`): `precheck` (sound counting checks only, called in `solver._assignment` and by the
UI check) raises `solver.ConflictError` before solving; when no timetable is found, `solver._unsolvable` →
`chan_doan.diagnose` re-runs `solver.feasible` (fixed assignment, first solution, 30 units) with rule families relaxed via
`rules.applied` or the diagnosis-only flags `solver.RELAXED` (always empty in a real solve, so the model and codes are
unchanged): not proven → "add time"; all relaxed still infeasible → staff/quota; else a deletion filter gives the
minimal conflicting families and which single relaxation fixes it. A new hard rule should get a family in
`chan_doan._rules` (and a count in `precheck` if one is sound).

Specialist roles (sheet `CHỨC VỤ`, `config.CUSTOM_ROLES` of `config.Role(name, subjects)`, read in `rules._Reader.roles`):
`Problem.specialists` is role → tuple of subjects (`allocation.resolve_roles`: a sheet role, else a role named like a
subject teaches that one subject; an uncovered `GENERAL_FORBIDDEN_SUBJECTS` subject gets the first sheet role teaching it,
else a subject-named role; sheet roles nobody holds and nobody needs are dropped). `specialist_subjects()` is the union.
`rules.code()` leaves out an empty list and rows that only restate a subject-named role, so the codes are unchanged;
the updated input adds the sheet with the held specialist roles (`writer.role_rows`).

Rules = rows of sheet `LUẬT` (`config.RULES_SHEET_ROWS`), each one sentence of the rule composer (`tkb/bo_ghep.py`;
cells read/written and described in `tkb/luat_rieng.py` as `config.CustomRule`): "for each [scope dims `SCOPES`] ·
lessons [subject(+group), tags, excluded tags, grades, classes, days, periods, sessions, teacher: role, Mã GV or name,
or 'trừ <…>'; matched by `bo_ghep.picks`] ·
then [measure `MEASURES`] [op] [number or `DERIVED` threshold] · when [curriculum condition, per subject/group if the
scope has one]", hard or soft (Điểm points, else Mức Thấp/Vừa/Cao/Rất cao = level 1–4 `Weights.custom_levels`,
`luat_rieng.LEVELS`; written as words, read as words or 1–4). `Kiểu luật` is a preset
(`luat_rieng.KINDS`, expanded by `bo_ghep.PRESETS`; `nghi_gv`, `co_so_2` exist only in native form) or "Tự ghép".
**Built-in rules** are the default rows of `tkb/luat_co_san.py` (`NATIVES`, `default_rows`, written by the template):
`rules.read_rules` → `luat_co_san.apply(rows)`: a row in a native's exact shape (only number/points differ, `fits`)
keeps the native encoding (params into `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, `PAIR_MIN_LESSONS`, `config.WEIGHTS` via
`config.rule_weights`), a native with no row is off (`config.OFF`; code checks `config.on(key)`, the solver
`solver.on(key)` which also honours `RELAXED`), every other row goes to `config.CUSTOM_RULES` (composer). No sheet
`LUẬT` (old file): default rows from the old columns (`rules.LEGACY`: still read, never written or shown) plus sheet
`LUẬT RIÊNG` rows; so defaults give the same model and codes (`OFF`/`WEIGHTS` are optional attrs of `rules.code()`).
`config.RULES` holds the sheet rows (None: no sheet, `luat_co_san.rows()` rebuilds them). Read-back sentences (`luat_rieng.describe`, used by the UI, diagnosis, the
"Luật đọc là" column): a row in a native's shape reads as that native's hand-written title (`Native.titles`,
`luat_co_san.title`, filled with the row's number/subject), any other row as a plain composed sentence (no `>=`/`<=`,
one colon, "giờ học" not "ô"). Every preset (`Kind.family`) and measure (`Measure.family`) belongs to one of the four
`bo_ghep.FAMILIES` (Ở đâu, Bao nhiêu, Đi cùng nhau, Ai dạy): the UI's single "Loại luật" select and the guide are grouped
by them; the Excel columns are unchanged. Each of the 9 measures is ONE
function against a context: `_Cp` lowers it into CP-SAT (`build`, end of `build_timetable`), `_Eval` counts violations
(`violations` → `check`, `qa`, `soft_report`), both over the same atoms (`_Source`: course × allowed slot [× teacher]).
Shortcuts read the same `Luat`: `banned` (domain cut in `solver.allowed_slots`), `forced_pairs` (in
`allocation.paired_groups(req, grade)` — always pass the grade), `day_cap` and `busy` (a teacher's busy slots: hard
"Không xếp vào" with a teacher and no subject; both in `phan_cong.teacher_slots`), `allowed`/`refusing` (hard
"Người dạy: Do" without slots filters eligible teachers in `allocation.build_problem`; one Mã GV + class = forced
assignment), `assign_cost` (soft one:
`phan_cong._flow`, `_Local._part`, `solver._Allocation`), `validate`/`precheck`. Diagnosis (`chan_doan._rules`) tries
dropping each hard row (native: `OFF`; daily: drop the subject; composer: drop from `CUSTOM_RULES`) and names rows as
`LUẬT dòng n: <sentence>` (`luat_rieng.label`). Sentences show Mã GV, never names: `bo_ghep.know_staff(staff)` fills
`config.PEOPLE` (name/code → Mã GV; not a rule, restored by `rules.applied`) after the staff is read in `__main__._run`
and `kich_ban.check`/`describe`; `bo_ghep.person` treats any name with a digit as a Mã GV. A new measure = one `Measure` + one function in `LOWER`; a new tag = a
new Có/Không `Col`; a new built-in rule = a `Native` + its encoding guarded by `on(key)` (plus `checker`). Everything
composer-side is skipped when `CUSTOM_RULES` is empty. `tests/test_luat_co_san.py` checks default rows change nothing,
edits work, the composer cross-checks the checker and its lowering can replace natives. The UI rules step edits
`scenario["rules"]` (all rows) in a composer dialog driven by `kich_ban.composer()`, asks `/api/describe`
(`kich_ban.describe`: sentence, errors, native key), and imports/exports rules-only files (`kich_ban.rules_to_excel`,
`/api/rules_file`).

`checker.check` re-verifies every hard rule independently of the model: a new hard rule goes in both
`solver.timetable` and `checker`. Slots are `(day 0–4, period 1–7)`: 1–4 morning, 5–7 afternoon, Friday
afternoon off (`config.DAY_SESSIONS`). Subject names in config match file names loosely via
`staff.subject_key` → `program.canonical_subject`.

Each rule below (except who-may-teach and the assignment/LNS rows) is a default row of sheet `LUẬT` (`luat_co_san.NATIVES`; deleting the row turns it off, its number/points come from the row).

| Rule | `tkb/config.py` default (the file's rules override) | Implemented in |
|---|---|---|
| Subject group (TV+TV TC, Toán+Toán TC) ≤ 2 per session; Toán ≤ 1 per day; groups ≥ 6 lessons with even total in consecutive pairs; same subject contiguous in a session; TC lesson after every main lesson of its group that day, and the day has one (hard) | `SUBJECT_GROUPS`, `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, `PAIR_MIN_LESSONS`, `PAIR_EXCLUDED` | `solver.timetable` "Luật bảo vệ học sinh" block; `checker._check_student_rules`; `allocation.paired_groups` |
| Consecutive lessons of a group by one teacher; homeroom priority group: GVCN's lesson first in the week (hard, always) | `SUBJECT_GROUPS`, `HOMEROOM_PRIORITY` | `solver.timetable` "Liên tiết", "GVCN trước"; `checker._check_teacher_order` |
| HĐTN Mon p1 + Fri p4 fixed, rest Tue–Thu near session end | `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS` | `allocation.build_problem`, `solver.allowed_slots`, objective `hdtn_flex_distance` |
| Period 1 always the homeroom teacher | `HOMEROOM_PERIODS` | `solver.allowed_slots` |
| Who may teach what | `HOMEROOM_ONLY_SUBJECTS`, `GENERAL_FORBIDDEN_SUBJECTS`, `MANAGER_RULES`, `CUSTOM_ROLES` (sheet CHỨC VỤ) | `allocation.resolve_roles`, `roles_for_subject`, `manager_allowed`; `checker.check` "Quyền dạy" |
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
  `tkb/truong_mau.py` with main.py constants Linux `72C2-3315-CE24`. Editing `INPUT_V8.xlsx` changes the main.py codes.

## CI (`.github/workflows/`, repo is public so minutes are free)
- `windows.yml`: on PRs and pushes to main; 4 VMs (windows-2022/2025 × Python 3.12/3.14) run pytest and
  `.github/scripts/chay_mau.py` (`FILE_VAO` twice, uploads only the code); a Linux job fails if any VM's code
  differs (~35 min).
- `linux.yml`: on PRs and pushes to main; pytest on ubuntu-24.04 / Python 3.12 (incl. the Linux reference codes).
- `file_that_windows.yml`: manual (or when the file itself changes); same run once on 2 VMs with Python 3.14.
- `dong_goi.yml` (manual, tags `v*`, PRs touching packaging/UI entry): `tools/dong_goi.py` builds `dist/TKB/TKB.exe`
  (PyInstaller onedir, `requirements-build.txt` pins it; static pages as data, `--collect-all ortools`; refuses any
  `.xlsx` in the package) → `.github/scripts/thu_goi.py` runs it on the fake school (`--cli`, then the UI: import,
  check, run, Stop) → artifact `TKB_Windows.zip`. The frozen exe re-runs itself with `--cli` for each solve
  (`server.cli_command`) and ignores `PYTHONUNBUFFERED`, so `__main__.use_utf8_output` line-buffers stdout (the UI log
  and Stop depend on it).

## Docs (open only the section you need)
- `docs/CODE_MAP.md`: generated function index (prefer `python tools/code_map.py <filter>`).
- `README.md`: user guide — `main.py` constants, input format, outputs, business rules.
- `docs/Dac_Ta_Nghiep_Vu_TKB_V16.md`: full spec. §0 change history (add a row per rule change), §5 homeroom,
  §6 student rules, §7 shortage modes, §8 objectives and weights, §9 solve process and reproducibility,
  §11 outputs, §13 reference results.
- `docs/Tham_Khao_TKB_Truong_Khac.md`: how other schools arrange subjects; §5 proposals (5.1 done, 5.2 dropped); §6 not adopted (incl. the homeroom-gap trial).
