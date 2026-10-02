# Code map

Sinh tự động bởi `python tools/code_map.py --write`, đừng sửa tay. Bản kèm số dòng: `python tools/code_map.py`.


## main.py — Xếp thời khóa biểu: chỉ cần sửa các hằng số bên dưới rồi bấm nút Run (▶) để chạy.
Hằng số: `FILE_VAO`, `THU_MUC_OUT`, `CHE_DO`, `SO_TIET_BU_TOI_DA`, `LUAT_HOC_SINH`, `THOI_GIAN_TOI_DA`, `CHAY_TAI_LAP_DUOC`, `GIU_TKB_DA_XEP`, `FILE_TKB`, `FILE_TKB_CHUC_VU`, `FILE_THONG_KE`, `SO_LUONG`, `BASE_DIR`
- `_blank(value)`
- `_resolve(path)` — Đường dẫn tương đối tính từ thư mục dự án; để trống = chính thư mục dự án.
- `run(file_vao, thu_muc_out, file_tkb, thoi_gian_toi_da, luat_hoc_sinh, chay_tai_lap_duoc, so_luong, che_do, so_tiet_bu_toi_da, file_thong_ke, file_tkb_chuc_vu, giu_tkb_da_xep)` — Chạy xếp TKB; trả về 0 nếu thành công, 3 nếu chế độ bù giờ thiếu tiết.

## giao_dien.py — Mở giao diện web xếp thời khóa biểu: bấm nút Run (▶) để chạy, trình duyệt tự mở trang nhập liệu.

## tkb/__main__.py — Chạy: python -m tkb <file vào.xlsx> [-o TKB.xlsx] ...
- `use_utf8_output()` — In tiếng Việt không lỗi khi output bị chuyển hướng trên Windows (mặc định bảng mã cp1252).
- `main(argv)`
- `_run(args, settings)`
- `print_teacher_rules(solution)` — In số liệu các luật về GV: hai cơ sở, thai sản, buổi nghỉ, giữ phân công của TKB cũ (chỉ in khi file vào

## tkb/allocation.py — Phân phần GVCN, sinh các "course" (lớp, môn, số tiết, GV hợp lệ) và GV bổ sung.
- `class Course`
- `class Problem`
  - `.overtime_mode()`
  - `.roles()` — Chủ Nhiệm, Bộ Môn, các GV chuyên biệt (theo thứ tự trong file), Quản Lý.
  - `.specialist_subjects()`
  - `.subject_label(subject)` — Tên môn in trong TKB: tên viết tắt trong config, không có thì tên như trong file vào.
  - `.class_courses(class_name)`
- `all_slots()`
- `subject_group(subject)` — Nhóm môn: môn tăng cường đi cùng môn chính (config.SUBJECT_GROUPS), môn khác là nhóm riêng.
- `paired_groups(grade_req)` — Các nhóm môn của một khối phải xếp thành cặp 2 tiết liền nhau (config.PAIR_MIN_LESSONS).
- `sessions_per_week()`
- `roles_for_subject(subject, specialists)` — Các chức vụ (ngoài chủ nhiệm/quản lý) được dạy môn này.
- `resolve_roles(staff, subject_labels)` — Suy ra GV chuyên biệt từ tên chức vụ: (chức vụ -> môn, chức vụ -> cách ghi trong file ra).
- `manager_allowed(rule, class_name, grade, subject)`
- `split_homeroom(class_name, grade_req, quota, reserved, specialist)` — Số tiết từng môn GVCN dạy cho lớp của mình.
- `supplement_capacity(role, teachers)` — Định mức GV bổ sung: Số tiết lớn nhất của GV cùng chức vụ trong file vào;
- `make_supplements(role, count, teachers, label)`
- `overtime_allowance(t, overtime_max)` — Số tiết bù tối đa của một GV ở chế độ bù giờ. GV đang hưởng thai sản không dạy bù.
- `overtime_cost(t, w)` — Giá tiết bù thứ nhất của t (mỗi tiết sau đắt thêm w.overtime_second). Ai bù trước: GVCN hợp đồng, GVCN
- `keep_cost(t, class_name, w)` — Giá mỗi tiết GV không chủ nhiệm t dạy lớp `class_name` khi lệch TKB cũ (cột Lớp Đang Dạy): khác mọi khối
- `build_problem(staff, curriculum, supplement_counts, overtime_max)` — Dựng bài toán.
  · Môn có luật trong config được gọi theo tên trong config; tên như trong file giữ lại để in ra.
  · Sắp môn theo tên: đổi thứ tự dòng trong file chương trình học không làm đổi TKB.
  · Môn/khối dành riêng cho quản lý thì GVCN không lấy để bù.
  · Nhu cầu tối đa theo chức vụ để dựng đủ GV bổ sung dự kiến.

## tkb/chan_doan.py — Chẩn đoán vì sao không xếp được TKB: luật bắt buộc nào mâu thuẫn, nói bằng tên quy định nhà trường đã ghi.
Hằng số: `SECONDS`, `ALL`
- `_q(attr)`
- `precheck(problem, student_rules)` — Các mâu thuẫn chắc chắn giữa chương trình học và luật bảo vệ học sinh, tìm bằng phép đếm (mỗi khối một lần).
- `class _Rule` — Một nhóm luật bắt buộc có thể nới khi chẩn đoán.
- `_rules(staff, settings)` — Các nhóm luật bắt buộc đang có hiệu lực, theo thứ tự thử.
- `_relaxed(rules)`
- `class Diagnosis`
- `diagnose(staff, curriculum, settings, log, seconds)` — Tìm luật bắt buộc nào làm không xếp được (xem đầu module).

## tkb/checker.py — Kiểm tra độc lập mọi luật cứng trên TKB đã xếp (không dựa vào mô hình solver).
- `check(problem, lessons, student_rules)`
  · Lớp: mỗi slot đúng 1 tiết, đủ số tiết từng môn.
  · GV: không trùng giờ, không vượt định mức.
  · Quyền dạy.
  · GVCN dạy đủ phần đã phân; phần dạy thêm chỉ là tiết bù hợp lệ (chế độ bù giờ).
  · Bù giờ: GVCN được ưu tiên bù lớp mình. Bộ môn đang dạy bù mà còn dạy ở lớp X một môn GVCN lớp X được dạy, trong khi GVCN lớp X chưa bù hết mức, thì chuyển tiết đó cho GVCN luôn làm được (GVCN chỉ dạy lớp mình nên giờ đó rảnh) và bớt tiết bù của bộ môn: phân công chưa đúng thứ tự ưu tiên.
  · HĐTN: 2 slot cố định + phần còn lại trong các ngày linh hoạt.
- `_check_teacher_order(problem, lessons)` — Liên tiết do 1 người dạy; nhóm môn ưu tiên của GVCN: tiết của người khác không trước tiết GVCN đầu tuần.
- `_check_teacher_sessions(problem, lessons)` — Cơ sở và buổi nghỉ: GV chỉ-cơ-sở-2 (cột Cơ sở 2, thai sản) không dạy lớp cơ sở 1; mỗi buổi một GV chỉ dạy ở
- `_check_student_rules(problem, lessons)`

## tkb/config.py — Giá trị mặc định của các luật nghiệp vụ, trọng số mục tiêu và tham số xếp giờ.
Hằng số: `TV`, `TOAN`, `HDTN`, `KH`, `LSDL`, `DD`, `TNXH`, `KNS`, `CONG_NGHE`, `TOAN_TC`, `TV_TC`, `TIENG_ANH`, `TIN_HOC`, `AM_NHAC`, `MY_THUAT`, `DISPLAY_NAMES`, `DAYS`, `MORNING`, `AFTERNOON`, `DAY_SESSIONS`, `OFF_LABEL`, `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS`, `ROLE_HOMEROOM`, `ROLE_GENERAL`, `ROLE_MANAGER`, `ROLE_LABELS`, `STAFF_SHEET`, `PROGRAM_SHEET`, `RULES_SHEET`, `SAVED_SHEET`, `SAVED_OVERTIME`, `SAVED_CODES`, `HOMEROOM_ONLY_SUBJECTS`, `GENERAL_FORBIDDEN_SUBJECTS`, `MANAGER_RULES`, `HOMEROOM_PRIORITY`, `HOMEROOM_CUT_ORDER`, `HOMEROOM_FILL_ORDER`, `HOMEROOM_PERIODS`, `SUPPLEMENT_NAME`, `MODE_HIRE`, `MODE_OVERTIME`, `MODES`, `OVERTIME_ROLES`, `HOMEROOM_OVERTIME_SPECIALIST`, `OVERTIME_MAX`, `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, `MORNING_SUBJECTS`, `SUBJECT_GROUPS`, `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, `PAIR_MIN_LESSONS`, `PAIR_EXCLUDED`, `LNS_START_SHARE`, `LNS_START_MAX`, `LNS_REGION_LIMITS`, `LNS_HOTSPOTS`, `LNS_SHARED_CLASSES`, `LNS_MIN_GAIN`, `LNS_MAX_ROUNDS`, `ORTOOLS_VERSION`
- `class Session`
- `class ManagerRule` — Quản lý chỉ dạy môn `subject` của khối `grade`.
- `rule_subjects()` — Các môn được nhắc tới trong luật ở trên (để kiểm tra tên môn trong file vào).
- `class Weights`
- `class Settings`

## tkb/kich_ban.py — Kịch bản của một trường cho giao diện (tkb/giao_dien): toàn bộ nội dung file vào V8 dưới dạng dữ liệu JSON.
Hằng số: `VERSION`, `STAFF_COLS`, `_HEADERS`, `ROLES`
- `_col(c)`
- `schema()` — Mô tả các bảng, cột cho giao diện (sinh ô nhập theo đây).
- `_blank(value)`
- `_number(value)` — Số nguyên nếu ô là số nguyên, ô trống là None, còn lại giữ chữ (kiểm tra sẽ báo lỗi).
- `_text(value)`
- `_read_staff_rows(wb, warnings)` — Các dòng của sheet nhân sự đúng như chữ trong file (không kiểm tra; dòng trống bỏ qua).
- `_read_program_rows(wb)` — Các khối và các dòng (môn, {khối: số tiết}) của sheet CHƯƠNG TRÌNH HỌC đúng như trong file.
- `_from_cell(col, value)`
- `_json_value(value)`
- `_read_saved(wb)`
- `_rules_part(subject_names)` — Các quy định đang dùng (config) theo dạng kịch bản: (chung, ngày, tiết, {môn: quy định}, các môn có quy
- `from_excel(path)` — Đọc file vào V8 (cả file vào cập nhật *_cap_nhat.xlsx) thành kịch bản: (kịch bản, các cảnh báo). Nhân sự và số
- `default_scenario()` — Kịch bản trống như file mẫu (python -m tkb.template): chưa có nhân sự, các môn có quy định mặc định với số tiết
- `_to_cell(col, value)`
- `_staff_row(row)`
- `to_excel(scenario, path)` — Ghi kịch bản ra file vào V8 (NHÂN SỰ, CHƯƠNG TRÌNH HỌC kèm cột quy định, QUY ĐỊNH, HƯỚNG DẪN và, nếu có, sheet
- `_lines(exc, sheet)` — Các dòng lỗi của một InputError (dòng tiêu đề "... có n lỗi:" bỏ đi), thêm tên sheet nếu lỗi chưa ghi.
- `check(scenario, mode, overtime_max, student_rules)` — Kiểm tra kịch bản như khi chạy: ghi ra file tạm, đọc lại bằng các hàm đọc của chương trình, đếm tìm các quy

## tkb/lns.py — Xếp giờ với phân công cố định: CP-SAT khởi đầu, rồi lặp QA -> xếp lại từng vùng (LNS) đến khi dừng.
- `class LnsResult`
- `_class_key()`
- `class _Search`
  - `.solve(model, seconds, hint)` — (status, objective, values, bound, solver); ngân sách đã dùng cộng vào self.used.
  - `.region(free, seconds, best)` — Xếp lại một vùng: mọi biến quyết định ngoài `free` giữ giá trị của `best`.
  - `.qa(values)` — Chi phí mềm theo (lớp, ngày), theo trọng số mục tiêu; và các tiết của nghiệm.
  - `.free(classes, days)`
  - `.regions(cost, lessons)` — (loại, tên, biến được mở, giới hạn) theo thứ tự thử của một vòng.
- `improve(tm, settings, log)` — Khởi đầu + các vòng QA -> LNS (xem đầu module). None nếu không tìm được TKB nào.
  · Ctrl+C; trên Windows giao diện (tkb/giao_dien) dừng sớm tiến trình xếp TKB bằng Ctrl+Break (SIGBREAK).

## tkb/phan_cong.py — Dự toán và phân công giáo viên, không dùng CP-SAT: Python thuần, số nguyên, duyệt theo thứ tự cố định nên
Hằng số: `MANAGER_BONUS`
- `class MinCostFlow`
  - `.add(u, v, cap, cost)`
  - `.run(s, t)`
  - `.used(ref)`
- `subject_rank(subject)` — Hạng môn khi GVCN bù: môn ưu tiên 0, rồi theo HOMEROOM_FILL_ORDER 1, 2..., môn khác sau cùng.
- `_real_teachers(problem)`
- `teacher_slots(problem)` — GV -> số ô giờ có thể dạy (hợp các ô được phép của những course người đó được dạy, trừ buổi nghỉ). Vd GV
- `_flow(problem, w, demand, base_load, homeroom_arcs)` — Giao `demand` (course -> số tiết) cho GV thật; trả về (phân công, tiết thiếu theo course).
- `_homeroom_extra(problem, g, x, rem, order, spec_cap)` — Chọn x tiết bù cho GVCN g: (course -> số tiết, số tiết môn ưu tiên phải nhường vì chia chẵn).
  · 1. Môn ưu tiên trước, theo nhóm môn; nhóm ghép cặp giữ phần của GVCN chẵn.
  · 2. Còn lại: các môn trọn vẹn, tổng vừa khít, ít hạng nhất (không chia môn nếu tránh được).
- `_balance_parity(problem, totals, rem, order, spec_cap)` — GVCN phải nhường môn ưu tiên vì chia chẵn (vd bù +1 vào nhóm TV ghép cặp) thì đổi mức bù với một GVCN
- `class _Local`
  - `._count(cid, g, n)`
  - `._shift(cid, g, n)`
  - `._part(cids, gs)`
  - `._try(ops, cids, gs)`
  - `.run(max_rounds)`
  - `.lessons()`
- `class PhanCong`
  - `.missing_total()`
- `phan_cong(problem, w)` — Dự toán + phân công (xem đầu module). `problem` là bài toán chế độ bù (GVCN được nhận tiết ở lớp mình).
  · 1. Dự toán: mỗi GVCN bù bao nhiêu tiết.
  · 2. GVCN nhận tiết bù ở lớp mình.
  · 3. Phần còn lại cho bộ môn, GV chuyên biệt, quản lý; rồi tìm kiếm cục bộ.
- `_hire_role(problem, course)` — Chức vụ tuyển cho tiết thiếu: bộ môn nếu được dạy môn này, không thì GV chuyên biệt của môn.
- `tach_tiet_bu(problem, plan, staff, include_missing)` — Chức vụ -> người tuyển mới (số nhỏ nhận nhiều tiết hơn), mỗi người là các (course, người bù, số tiết);

## tkb/program.py — Đọc chương trình học: cột 'Môn học' và các cột 'Khối k'.
- `_rule_names()`
- `canonical_subject(name)` — Tên môn dùng khi dựng bài toán: tên trong config nếu khớp một môn có luật, không thì giữ tên trong file.
- `read_program(path)` — Đọc sheet "CHƯƠNG TRÌNH HỌC" của file vào.
- `subjects_in_order(curriculum)` — Các môn theo thứ tự xuất hiện trong file.
- `missing_rule_subjects(curriculum)` — Môn có luật (sheet QUY ĐỊNH hoặc config) nhưng không có trong chương trình học (thường do gõ khác tên).

## tkb/rules.py — Quy định nghiệp vụ trong file vào: nhà trường tự sửa trong Excel, không cần sửa mã nguồn.
Hằng số: `MAX_DAYS`, `NOTE`, `OLD_SHEETS`, `GENERAL`, `DAY_KEY`, `DAY_COLS`, `PERIOD_KEY`, `PERIOD_COLS`, `SUBJECT_KEY`, `SUBJECT_COLS`, `FRAME_ATTRS`, `ATTRS`, `LABELS`, `DEFAULTS`, `_KNOWN`, `_ROLES`
- `class Col`
- `_day_name(d)`
- `_frame_now()` — Khung giờ theo config hiện tại: ngày học buổi sáng, buổi chiều, số tiết mỗi buổi.
- `_build_frame(f)` — Khung giờ -> config.DAYS, MORNING, AFTERNOON, DAY_SESSIONS.
- `_blank(value)`
- `_row(ws, r)` — Các ô có chữ của dòng r: {cột: giá trị}.
- `_is_grade(head)`
- `class _Reader` — Đọc các cột quy định của sheet CHƯƠNG TRÌNH HỌC và ba bảng của sheet QUY ĐỊNH; gom mọi lỗi để báo cùng
  - `.error(sheet, row, text)`
  - `.yes(sheet, row, header, value)`
  - `.number(sheet, row, header, value)`
  - `.cell(sheet, row, col, value)`
  - `.table(ws, header_row, end_row, key_col, cols, strict)` — Bảng có dòng tiêu đề `header_row`, khóa ở cột `key_col`, các dòng đến `end_row`: ({khóa của cột: số
  - `.rules_sheet(ws)` — Tìm các bảng theo ô tiêu đề đầu bảng (Quy định, Ngày, Tiết); mỗi bảng đến dòng trống kế tiếp.
  - `.general(ws, header_row, end_row, label_col)`
  - `.days(ws, header_row, end_row, key_col)`
  - `.periods(ws, header_row, end_row, key_col)`
  - `.subjects(ws)` — Đọc các cột quy định sau các cột Khối; trả về True nếu sheet có ít nhất một cột quy định.
  - `.finish()`
- `read_rules(path, warn)` — Đọc quy định của file vào: các cột quy định của sheet CHƯƠNG TRÌNH HỌC và sheet QUY ĐỊNH. Trả về {hằng số
- `applied(values)` — Dùng các quy định đọc từ file vào trong khối `with`; ra khỏi khối thì trả lại giá trị cũ.
- `changed(values)` — Tên các quy định trong file khác giá trị mặc định trong tkb/config.py.
- `_canonical(attr, value)` — Giá trị viết theo một cách duy nhất (tập hợp sắp xếp; tên viết tắt không phụ thuộc thứ tự dòng).
- `code()` — Mã của các quy định đang dùng (12 chữ số hex): quy định khác nhau thì mã khác nhau, mọi máy cùng mã.
- `_yn(on)`
- `rule_tables()` — Ba bảng của sheet QUY ĐỊNH theo config hiện tại: [(tiêu đề, các dòng)].
- `default_subjects()` — Các môn có quy định, theo thứ tự tự nhiên (môn GVCN nhận trọn, môn nhận thêm, rồi các môn khác).
- `subject_columns(subjects)` — Các cột quy định của sheet CHƯƠNG TRÌNH HỌC theo config hiện tại: (tiêu đề, {môn: giá trị các cột}, các môn có
- `notes()` — Giải thích từng quy định (cho sheet HƯỚNG DẪN): [(sheet: cột/quy định, cách ghi)].

## tkb/solver.py — Xếp giờ bằng CP-SAT và toàn bộ quy trình giải.
Hằng số: `RELAXED`
- `class SolveError`
- `ortools_version()`
- `class Lesson`
- `class Solution`
  - `.teacher_load()`
  - `.used_supplements()`
  - `.fingerprint()` — Mã kết quả: băm toàn bộ TKB (lớp, ngày, tiết, môn, GV). Hai lần chạy cùng mã là cùng TKB.
  - `.overtime()` — GV -> số tiết dạy bù (vượt định mức).
- `session_of()`
- `distance_to_session_end(slot)`
- `day_targets(total, slots)` — Chia `total` tiết cho các ngày theo tỷ lệ số slot (phương pháp phần dư lớn nhất).
- `allowed_slots(course, problem)`
- `_configure(solver, settings, seconds)` — Đặt tham số CP-SAT. seconds = None: không giới hạn, chạy đến khi chứng minh tối ưu.
- `class _Allocation` — a[k,g] = số tiết GV g dạy course k; used[k,g] = GV g có dạy course k.
    · Phá đối xứng giữa các GV bổ sung cùng chức vụ: số thứ tự nhỏ dạy nhiều hơn.
    · Cân bằng phần định mức chưa dùng giữa các GV cùng chức vụ.
  - `._overtime(main, secondary)` — Chế độ bù giờ: số tiết bù = tải vượt định mức; GVCN bù trước bộ môn.
  - `._slot_capacity()` — GV không dạy 2 lớp cùng lúc: các tiết có miền slot nằm trong D chiếm tối đa |D| slot.
  - `.supplement_lessons()`
- `class TimetableModel` — Mô hình xếp giờ đã dựng. x[course, slot]: course có tiết ở slot; z[course, GV, slot]: GV nào dạy tiết đó
  - `.lessons(value)` — Các tiết của nghiệm; value(biến) -> giá trị (vd CpSolver.Value).
- `timetable(problem, settings, fixed, hint, log)` — Xếp giờ. Phân công cố định: CP-SAT khởi đầu rồi xếp lại từng vùng (tkb/lns.py). Mô hình tích hợp (vừa
- `_teacher_sessions(m, problem, occ_terms, occ_campus)` — Luật cứng theo buổi của từng GV: buổi nghỉ (cột Buổi Nghỉ) và mỗi buổi chỉ dạy ở một cơ sở (cột Cơ sở 2).
- `_campus_day_switch(m, occ_campus, weight)` — Mục tiêu mềm: phạt `weight` mỗi (GV, ngày) dạy ở cả hai cơ sở (sáng một nơi, chiều nơi kia).
- `build_timetable(problem, settings, fixed, hint)` — Dựng mô hình CP-SAT xếp giờ: luật cứng + mục tiêu mềm (config.Weights).
  · Mỗi lớp mỗi slot đúng 1 tiết (hoặc tối đa 1 nếu chương trình ít hơn số slot).
  · GV dạy course tại slot nào.
  · Biến "GV g dạy nhóm môn của lớp tại slot s" cho các luật về người dạy.
  · Liên tiết: hai tiết liền nhau cùng lớp, cùng nhóm môn (vd TV và TV tăng cường) phải cùng người dạy.
  · GVCN trước: nhóm môn ưu tiên của GVCN mà có người khác cùng dạy thì tiết đầu tuần là của GVCN, tiết của người khác không đứng trước tiết GVCN đầu tiên.
  · Luật bảo vệ học sinh: mỗi nhóm môn tối đa SESSION_GROUP_LIMIT tiết mỗi buổi; Toán mỗi ngày tối đa 1 tiết (DAILY_LIMITS); nhóm môn ghép cặp (allocation.paired_groups) mỗi buổi 0 hoặc 2 tiết liền nhau; môn có từ 2 tiết trong một buổi thì các tiết phải liền nhau (không có mẫu "môn – môn khác – môn"); tiết tăng cường sau tiết chính cùng nhóm trong ngày (config.SUBJECT_GROUPS).
  · HĐTN linh hoạt: càng gần cuối buổi càng tốt.
  · Hạn chế môn nặng ở tiết cuối ngày.
  · Buổi sáng dành cho TV, Toán.
  · Tải ngày của GV: phạt vượt mức mong muốn và vượt buffer (+1).
  · Rải đều môn trong tuần theo từng lớp.
  · Tiết trống giữa buổi của GV không chủ nhiệm.
- `class ShortageError` — Chế độ bù giờ: GVCN và bộ môn đã bù tối đa mà vẫn thiếu tiết (không tuyển thêm).
  - `.rows()` — (lớp, môn, số tiết thiếu, lý do) theo thứ tự lớp.
- `du_toan_lines(problem, plan)` — Dự toán in ra trước khi xếp giờ.
- `_hire_assignment(plan, work, split)` — Phân công cố định khi tiết bù/tiết thiếu do người mới dạy; (course, người mới) -> người bù từng tiết.
- `_to_overtime(solution, problem, owners)` — TKB chế độ bù: các ô của người mới trả về đúng người bù (cùng vị trí môn).
- `reuse(staff, curriculum, settings, rows)` — Dùng lại TKB đã xếp (sheet config.SAVED_SHEET của file vào cập nhật, staff.read_saved_timetable) thay cho
  · Mỗi (lớp, môn) có thể có hai course: phần GVCN (homeroom) và phần còn lại; tiết của GVCN (trừ tiết bù) vào phần GVCN trước.
- `_need(problem)` — (lớp, môn) -> số tiết theo chương trình học.
- `class ConflictError` — Các luật bắt buộc mâu thuẫn nhau: không có TKB nào thỏa (thấy khi đếm trước, hoặc khi chẩn đoán).
- `_assignment(staff, curriculum, settings, log)` — Bước 1 của solve: kiểm tra đếm (tkb/chan_doan.py), dự toán, phân công, chia tiết bù cho người tuyển mới.
- `feasible(staff, curriculum, settings, seconds)` — Có TKB nào thỏa mọi luật bắt buộc không, với phân công cố định như solve (tìm nghiệm đầu tiên, tối đa
- `_unsolvable(staff, curriculum, settings, log)` — Lỗi khi không xếp được: chẩn đoán luật nào gây ra (tkb/chan_doan.py).
- `solve(staff, curriculum, settings, log)` — Dự toán, phân công → xếp giờ một lần → TKB chế độ bù hoặc chế độ tuyển (cùng vị trí môn). Không xếp được

## tkb/staff.py — Đọc và kiểm tra file Excel danh sách nhân sự.
Hằng số: `SPECIAL_ROLES`, `_CLASS_RE`, `_CLASS_NAMED_RE`, `_YES`, `_NO`, `_SESSIONS`, `_FIXED_OFF_RE`, `_ANY_OFF_RE`, `OPTIONAL_COLUMNS`
- `class InputError` — Lỗi dữ liệu đầu vào.
- `class Teacher`
  - `.grade()`
  - `.campus2_only()` — GV không chủ nhiệm chỉ dạy các lớp ở cơ sở 2 (đánh dấu Cơ sở 2, hoặc đang hưởng thai sản).
  - `.code()` — Mã GV hiển thị trong các file ra, vd "Bộ Môn 5", "Chủ Nhiệm 1/1".
- `normalize(text)`
- `clean_name(text)` — Chữ trong file, bỏ khoảng trắng thừa (giữ hoa thường).
- `subject_key(name)` — Khóa so khớp tên môn/chức vụ: không phân biệt hoa thường, dấu câu và chữ "và".
- `role_errors(teachers, subjects)` — Chức vụ không phải Chủ Nhiệm/Bộ Môn/Quản Lý và không trùng tên môn nào của chương trình học.
- `canonical_title(role, index, class_name)`
- `parse_class(value)` — Cột Lớp: khối/số thứ tự, vd "1/1", hoặc khối + tên lớp, vd "1D15" (khối là các chữ số đầu).
- `grade_of(class_name)` — Khối của một lớp: các chữ số đầu tên lớp, vd "1/2" và "1D15" đều là khối 1.
- `class_sort_key(class_name)` — Sắp lớp theo khối, rồi phần chữ, rồi số: "1/2" trước "1/10", "1D9" trước "1D15".
- `_fold(text)` — Chữ thường, bỏ dấu tiếng Việt (so khớp "Chiều T5" với "chieu thu 5").
- `parse_yes(value, column)` — Cột Có/Không: trống hoặc "Không" là không; "Có", "x", "1" là có.
- `parse_classes(value)` — Cột Lớp Đang Dạy: các lớp cách nhau bằng dấu phẩy hoặc chấm phẩy.
- `off_text(t)` — Cột Buổi Nghỉ viết lại từ dữ liệu đã đọc, vd "Chiều T5, Sáng T6, 2 buổi chiều".
- `parse_off(value)` — Cột Buổi Nghỉ: các mục cách nhau bằng dấu phẩy/chấm phẩy. Mỗi mục là buổi cố định ("Chiều T5",
- `find_sheet(wb, name)` — Sheet có tên `name` (không phân biệt hoa thường), hoặc None.
- `staff_sheet(wb)` — Sheet nhân sự: sheet tên "NHÂN SỰ" nếu có, không thì sheet đầu tiên.
- `class SavedTimetable` — TKB đã xếp đọc từ file vào cập nhật (sheet config.SAVED_SHEET).
- `read_saved_timetable(path)` — Sheet config.SAVED_SHEET của file vào (TKB đã xếp dạng lưới Lớp | Tiết | Thứ 2 …, mỗi ô "môn" xuống dòng
- `_blank(value)`
- `_find_columns(ws)` — Dòng tiêu đề và vị trí các cột (mẫu V8). Bắt buộc: Họ và Tên, Chức Vụ, Số Tiết/Tuần; không bắt buộc: Lớp,
- `_to_lessons(value, title)`
- `make_teacher(name, role, index, class_name, lessons, row, label, **extra)` — `extra`: các trường không bắt buộc của Teacher (maternity, contract, campus2, history, off_sessions, off_any).
- `_check_extras(teachers)` — Lỗi của các cột không bắt buộc cần cả danh sách mới kiểm được (lớp trong Lớp Đang Dạy, thai sản, buổi nghỉ).
- `validate(teachers)` — Báo mọi lỗi trùng lặp cùng lúc (mỗi lỗi một dòng).
- `read_staff(path, subjects)` — Đọc sheet nhân sự; `subjects`: các môn của chương trình học để kiểm tra chức vụ (None = không kiểm).
- `classes_from_staff(teachers)`

## tkb/style.py — Style của các file ra, chép từ sheet NHÂN SỰ của file vào (font, viền, căn lề, nền, chiều cao dòng).
Hằng số: `DEFAULT_ROW_HEIGHT`, `MAX_COLUMN_WIDTH`, `STAFF_HEADERS`, `MARK_FILLS`
- `with_bold(font, bold)`
- `class CellStyle`
  - `.of(cell)`
  - `.apply(cell, bold, horizontal, wrap)`
- `class Style`
  - `.from_file(path)` — Style của ô tiêu đề và ô dữ liệu đầu tiên ở cột Chức Vụ của sheet nhân sự (bỏ màu nền MARK_FILLS).
  - `.font_size()`
  - `.line_height()` — Chiều cao một dòng chữ (point).
  - `.text_width(text)` — Độ rộng ước lượng (đơn vị cột Excel) của một dòng chữ.
  - `.lines(text, width)`
  - `.header_cell(ws, row, col, value)`
  - `.body_cell(ws, row, col, value, bold, horizontal)`
  - `.table(ws, header, rows, top, bold_last)` — Bảng như sheet nhân sự của file vào: dòng tiêu đề rồi các dòng dữ liệu. Trả về dòng cuối.
  - `.fit_columns(ws, first_row, minimum, skip_rows)` — Nới độ rộng cột vừa chữ dài nhất (tối đa MAX_COLUMN_WIDTH, dài hơn thì xuống dòng).

## tkb/template.py — File vào mẫu V8: một file Excel đơn giản, tiếng Việt, style giống file của nhà trường (chữ đen, không tô nền,
Hằng số: `STAFF_HEADERS`, `STAFF_WIDTHS`, `RULES_WIDTHS`, `GUIDE_SHEET`, `GUIDE_HEADERS`, `GUIDE_WIDTHS`, `YES`, `LAST_ROW`, `BLANK_ROWS`, `BLANK_GRADES`, `BLACK`, `FONT`, `HEADER_FONT`, `THIN`, `BORDER`, `CENTER`, `LEFT`, `ROW_HEIGHT`, `NOTES`, `GUIDE`
- `role_label(t)`
- `staff_row(t)`
- `_style_rows(ws, first, last, n_cols, header, left)` — Kẻ bảng: chữ đen Times New Roman 14 (tiêu đề in đậm), viền mảnh, không tô nền; cột trong `left` căn trái.
- `_widths(ws, widths)`
- `_staff_sheet(wb, rows)` — Sheet NHÂN SỰ: mỗi dòng các giá trị theo STAFF_HEADERS (vd `staff_row`).
- `program_rows(curriculum, teachers)` — Bảng CHƯƠNG TRÌNH HỌC: các môn của `curriculum` (không có thì các môn có quy định mặc định, số tiết để trống)
- `_program_sheet(wb, grades, heads, rows)` — Sheet CHƯƠNG TRÌNH HỌC: Môn học | Khối ... | các cột quy định `heads`; mỗi dòng một môn.
- `write_rules_sheet(wb, index, tables)` — Sheet QUY ĐỊNH ở vị trí `index`: ba bảng (quy định chung, ngày, tiết), cách nhau một dòng trống. `tables`:
- `write_guide(wb, extra, index)` — Sheet HƯỚNG DẪN: cách ghi từng sheet, từng cột, rồi các dòng `extra` (vd giải thích kết quả).
- `write_input(path, staff, program, tables, extra)` — Ghi file vào V8 từ các dòng có sẵn: NHÂN SỰ (`staff`: các dòng theo STAFF_HEADERS), CHƯƠNG TRÌNH HỌC
- `write_staff_template(path, teachers, curriculum)` — Ghi file vào mẫu V8: sheet NHÂN SỰ, CHƯƠNG TRÌNH HỌC (kèm các cột quy định của môn), QUY ĐỊNH (các luật đang
- `main(argv)`

## tkb/writer.py — Xuất ra Excel: TKB (chỉ các sheet Khối); file thống kê (số tiết từng môn của mỗi giáo viên); file vào
Hằng số: `MAX_DAY_WIDTH`, `BLOCK_GAP`, `LABEL_PAD`, `HIRE_LABEL`, `CODE_HEADER`, `LOAD_HEADER`, `OVERTIME_HEADER`, `OVERTIME_DETAIL_HEADER`, `SPARE_HEADER`, `STATS_SHEET`, `SHORTAGE_SHEET`, `TOTAL_HEADER`, `MOVE_HEADERS`, `OVERTIME_FILL`, `HIRE_FILL`, `OVERTIME_LEGEND`, `HIRE_LEGEND`, `SPARE_FILL`, `SPARE_LEGEND`, `OVERTIME_CELL_FILL`, `OVERTIME_CELL_LEGEND`, `CAMPUS_FILES`, `OLD_NOTES_SHEET`, `LIST_SHEET`, `_ROW_FORMULA`
- `teacher_labels(teachers, with_codes)` — Chức vụ -> tên hiển thị dưới tên môn trong TKB.
- `session_rows()` — Các hàng của bảng TKB: (buổi, tiết trong ngày). Cột TIẾT ghi tiết trong ngày: sáng 1–4, chiều 5–7.
- `_merge(ws, style, r1, c1, r2, c2, value)`
- `_grade_sheets(wb, solution, style, with_codes, classes)`
- `staff_rows(solution)` — GV thật theo thứ tự file gốc, sau đó GV bổ sung được dùng.
- `campus_paths(path, problem)` — Các file TKB cần ghi: (đường dẫn, các lớp; None = cả trường). Trường có lớp ở cơ sở 2 thì tách thành
- `write_timetable(solution, path, style, with_codes, classes)` — File TKB: chỉ các sheet Khối. Nhân sự và thống kê ghi ở file thống kê (write_statistics).
- `_stats_name(t)`
- `campus_moves(solution)` — GV dạy ở cả hai cơ sở -> (các buổi ở cơ sở 2, vd "Sáng T3"; các ngày sáng một cơ sở, chiều cơ sở kia,
- `subject_table(solution, style)` — Họ và Tên | Chức Vụ (Mã GV) | số tiết từng môn | Tổng Tiết | Số Tiết/Tuần | Số Tiết Bù | (Môn Dạy Bù) |
- `_fill(color)`
- `row_marks(solution, spare)` — GV -> (màu nền, số tiết): người dạy bù (số tiết bù) và người cần tuyển thêm (số tiết thực dạy); spare: thêm
- `overtime_cells(solution)` — (GV, môn) -> số tiết dạy bù (vượt định mức) của GV đó trong môn đó (chế độ bù giờ).
- `_mark_rows(ws, solution, header, top, style)` — Tô nền dòng người dạy bù, người cần tuyển và người còn dư tiết (bảng bắt đầu ở dòng 1); trong dòng người
- `write_statistics(solution, path, style)` — File thống kê: một bảng số tiết từng môn của mỗi giáo viên, kèm định mức, số tiết bù, số tiết dư (xem
- `write_shortage(rows, path, style)` — File thống kê khi chế độ bù giờ không đủ: sheet SHORTAGE_SHEET liệt kê các tiết không ai dạy được.
- `_copy_style(src, dst)`
- `plain_values(wb, cached)` — Chỉ giữ chữ, số và màu: bỏ mọi ghi chú (comment), cố định dòng/cột, lọc, danh sách thả xuống, định dạng theo
- `_result_notes(overtime_mode)` — Các dòng sheet HƯỚNG DẪN giải thích phần kết quả của file vào cập nhật.
- `_add_subject_rules(wb)` — Sheet CHƯƠNG TRÌNH HỌC của file vào cập nhật ghi đủ các quy định của môn đã dùng: thêm các cột quy định còn
- `_write_saved(wb, solution, style)` — Sheet config.SAVED_SHEET: TKB đã xếp dạng lưới như TKB (Lớp | Tiết | Thứ 2 …), mỗi ô ghi môn, xuống dòng ghi Mã
- `write_updated_staff(solution, source, path)` — Chép file vào, thêm người cần tuyển vào cuối danh sách nhân sự và các cột Mã GV, số tiết thực dạy
  · Cột kết quả: ghi đè nếu file đã có (chạy lại trên file cập nhật), không thì thêm vào bên phải.
  · Tô nền cả dòng (đến cột tiêu đề cuối); chạy lại trên file cập nhật thì bỏ màu cũ của chương trình.
  · Ghi đủ các quy định đã dùng: cột quy định của môn, sheet QUY ĐỊNH (nếu file vào chưa có, sau sheet chương trình học); sheet HƯỚNG DẪN viết lại, kèm giải thích phần kết quả; cuối cùng là TKB đã xếp.

## tkb/giao_dien/__main__.py — Chạy: python -m tkb.giao_dien [--cong 8765] [--thu-muc <thư mục kết quả>] [--khong-mo-trinh-duyet]
- `main(argv)`

## tkb/giao_dien/server.py — Máy chủ HTTP của giao diện (chỉ thư viện chuẩn) và việc xếp TKB ở tiến trình con.
Hằng số: `STATIC`, `PROJECT`, `PORT`, `TOKEN_MARK`, `MAX_BODY`, `TYPES`, `XLSX`, `MODES`, `RUN_DEFAULTS`, `FILE_NAMES`
- `default_out_dir()` — Chạy từ mã nguồn: out/giao_dien của dự án (out/ đã bỏ qua trong git vì có tên giáo viên); bản đóng gói: thư
- `cli_command(argv)` — Lệnh chạy `python -m tkb`; bản đóng gói (PyInstaller) gọi lại chính nó với --cli (xem __main__.py).
- `safe_name(name)` — Tên file vào: bỏ ký tự Windows không cho phép, bỏ đuôi .xlsx.
- `run_argv(source, out, name, run)` — Tham số dòng lệnh `python -m tkb` theo cài đặt chạy (như main.run); báo lỗi nếu cài đặt sai.
- `summary(lines)` — Kết quả đọc từ các dòng in ra: mã kết quả, đạt luật bắt buộc hay không, các file đã ghi, lỗi (từ dòng "LỖI:"
- `class Job` — Một lần xếp TKB: tiến trình con, đọc từng dòng in ra.
  - `._read()`
  - `.running()`
  - `.stop()` — Dừng sớm như bấm Ctrl+C: chương trình xếp xong vùng đang xếp rồi ghi TKB tốt nhất.
  - `.kill()`
  - `.state(since)`
- `class App` — Trạng thái của giao diện: thư mục kết quả, mã phiên, việc xếp TKB đang chạy.
  - `.inside(path)` — Đường dẫn trong thư mục kết quả, không thì báo lỗi.
  - `.schema(_)`
  - `.new(_)`
  - `._import(path, name)`
  - `.import_file(body, name)`
  - `.import_path(data)`
  - `.check(data)`
  - `.export(data)`
  - `.run(data)`
  - `.status(query)`
  - `.stop(_)`
  - `.kill(_)`
  - `.open(data)`
  - `.settings(data)`
  - `.shutdown()`
- `class Handler`
  - `.log_message(fmt, *args)`
  - `._send(status, body, ctype, headers)`
  - `._json(status, payload)`
  - `._host_ok()`
  - `._token_ok(query)`
  - `._body()`
  - `.do_GET()`
  - `.do_POST()`
  - `._static(path)`
  - `._api(method, url)`
- `make_server(port, out_dir)` — Máy chủ trên 127.0.0.1 (cổng bận thì lấy cổng khác): (máy chủ, trạng thái, đường dẫn trang).
- `serve(port, open_browser, out_dir)`

## .github/scripts/chay_mau.py — Chạy xếp TKB file FILE_VAO với các hằng số mặc định của main.py (mặc định 2 lần); các lần phải ra cùng mã.
Hằng số: `ROOT`
- `class _Tee` — Vừa in ra màn hình vừa giữ lại chữ đã in.
  - `.write(text)`
  - `.flush()`
- `run_once(source, out)` — Chạy main.run; trả về (mã thoát, mã kết quả đọc từ dòng "Mã kết quả: ..." in ra màn hình).
- `run(argv)`

## tools/code_map.py — Bản đồ code: mỗi module một dòng mô tả, rồi các hàm/lớp kèm tham số và dòng đầu docstring.
Hằng số: `ROOT`, `OUT`, `SOURCES`, `TESTS`, `LONG_FUNCTION`, `HEADER`
- `_files(pattern)`
- `_first_line(node)`
- `_signature(fn)`
- `_item(text, doc, line, indent)`
- `_blocks(fn, source, lines, indent)` — Các dòng chú thích ngay ở thân hàm (cùng lề với các câu lệnh của thân) của một hàm dài.
- `_constants(tree)`
- `_module(path, lines)`
- `_tests(lines)`
- `render(lines, only)`
- `main(argv)`

## tools/mau_dau_ra.py — Sinh lại các file mẫu đầu ra từ trường mẫu tên giả (tests/du_lieu_mau.py), với các hằng số mặc định
Hằng số: `ROOT`, `TEMPLATES`
- `run()`

## tests
- `tests/test_allocation.py`: test_homeroom_split_sample, test_fill_order_never_takes_specialist_subjects, test_fill_order_priority, test_cut_only_multi_lesson_subjects, test_permissions, test_supplement_numbering, test_homeroom_needs_enough_lessons_for_locked_periods, test_overtime_allowances_and_eligibility, test_class_gaps_are_warned, test_curriculum_row_order_does_not_change_problem, test_specialists_come_from_subject_names, test_unknown_role_is_rejected, test_rule_subjects_missing_from_file_are_warned
- `tests/test_chan_doan.py`: test_no_conflict_with_default_rules, test_session_limit_too_small_for_the_lessons, test_pairs_against_daily_limit, test_student_rules_off_skips_the_count, test_solve_stops_before_solving_on_a_counted_conflict, test_diagnosis_names_the_rules_in_conflict, test_diagnosis_of_a_solvable_school_blames_the_time, test_relaxing_rules_changes_nothing_by_default
- `tests/test_code_map.py`: test_code_map_is_up_to_date
- `tests/test_giao_dien.py`: test_page_and_token, test_import_check_export, test_files_only_inside_output_folder, test_run_argv_like_main, test_summary_reads_printed_result, test_run_from_the_ui_gives_the_reference_timetable
- `tests/test_kich_ban.py`: test_round_trip_keeps_the_file, test_new_scenario_is_the_blank_template, test_schema_follows_rules_columns, test_rules_edited_in_the_scenario_reach_the_file, test_check_reads_back_like_a_run, test_check_estimates_shortage, test_blank_staff_rows_keep_row_numbers, test_excel_date_in_class_column_is_read_back_with_a_warning, test_saved_timetable_sheet_is_kept, test_check_finds_rules_in_conflict
- `tests/test_lns.py`: test_rounds_never_worsen_and_respect_the_budget, test_region_moves_only_the_open_cells, test_ctrl_c_stops_after_the_current_region, test_same_timetable_in_new_processes
- `tests/test_main.py`: test_run_writes_outputs, test_overtime_shortage_is_an_error_with_a_table, test_run_reports_missing_file, test_relative_paths_resolve_from_script_dir, test_run_rejects_bad_thread_count, test_run_passes_thread_count, test_run_overtime_mode_needs_no_hire, test_run_rejects_bad_mode, test_run_single_input_file_with_program_sheet, test_run_without_program_sheet_fails, test_defaults_are_overtime_student_rules_1200s_reproducible, test_blank_output_folder_means_project_folder, test_blank_time_limit_means_unlimited, test_bad_time_limit_and_blank_input_are_rejected, test_cli_time_limit_zero_is_unlimited, test_reloading_updated_file_keeps_timetable, test_reloading_falls_back_when_saved_timetable_breaks_rules, test_reloading_overtime_result_rewrites_the_same_files
- `tests/test_phan_cong.py`: test_min_cost_flow_prefers_cheap_paths, test_estimate_overtime_then_missing, test_homeroom_overtime_before_general, test_homeroom_overtime_takes_whole_subjects, test_homeroom_overtime_takes_music_and_art, test_assignment_is_deterministic, test_hires_take_overtime_and_missing_lessons, test_hire_split_limits_pairs_and_orders_by_load
- `tests/test_reproducible.py`: test_same_timetable_across_runs, test_reference_fingerprint, test_ortools_version_is_pinned, test_no_wall_clock_limit_in_reproducible_mode
- `tests/test_rules.py`: test_default_rules_equal_config, test_file_without_rules_uses_defaults, test_missing_sheet_or_column_keeps_defaults, test_subject_columns, test_subject_groups, test_time_frame, test_all_errors_at_once, test_old_rule_sheets_are_reported, test_applied_restores_config, test_every_rule_has_a_label, test_default_rules_give_the_same_timetable, test_rules_from_the_file_are_used, test_changed_rules_in_updated_file_solve_again
- `tests/test_solver.py`: test_small_school_solves_and_passes_checker, test_hdtn_fixed_and_flex, test_missing_general_teacher_becomes_supplement, test_checker_detects_violations, test_homeroom_teaches_first_period, test_heavy_subjects_avoid_last_period, test_core_subjects_in_the_morning, test_extra_lessons_after_main_lessons, test_checker_flags_extra_lesson_before_main, test_slot_capacity_limits_assignment, test_sample_school_hires_take_the_overtime_lessons, test_reproducible_mode_gives_identical_timetables, test_overtime_mode_covers_shortage_without_hiring, test_overtime_mode_never_hires_and_reports_the_shortage, test_hire_mode_uses_the_overtime_timetable, test_overtime_homeroom_before_general, test_checker_flags_invalid_overtime, test_sample_school_overtime_assignment, test_same_subject_lessons_are_contiguous, test_contiguous_when_a_subject_must_repeat_in_a_session, test_checker_detects_split_subject, test_checker_requires_homeroom_to_cover_own_class_first, test_checker_flags_new_teacher_rules, test_checker_flags_other_teacher_before_homeroom, test_vietnamese_is_paired_in_grade_one
- `tests/test_staff.py`: test_bad_lessons, test_duplicates_rejected, test_read_sample_staff, test_program_file_is_read_as_written, test_subject_names_match_rules_loosely, test_columns_and_auto_numbering, test_numbered_titles_are_rejected, test_old_headers_are_rejected, test_class_errors, test_class_turned_into_date, test_program_sheet_aliases_and_total_row, test_missing_program_sheet_is_an_error, test_all_errors_at_once, test_named_classes_and_optional_columns, test_optional_column_errors
- `tests/test_teacher_rules.py`: test_maternity_homeroom_takes_no_overtime, test_maternity_general_teaches_only_campus_two, test_contract_homeroom_takes_overtime_first, test_contract_general_takes_overtime_first, test_general_teachers_keep_their_old_grade, test_general_teachers_keep_their_old_class, test_one_campus_per_session_and_leave_are_kept, test_whole_day_at_one_campus_is_preferred, test_checker_flags_campus_and_leave_violations, test_timetable_class_column_is_plain_name, test_statistics_show_campus_moves, test_cli_splits_timetables_by_campus
- `tests/test_template.py`: test_template_is_plain, test_saved_input_template_is_up_to_date, test_blank_template, test_updated_staff_keeps_template_and_style, test_cli_writes_blank_template, test_optional_columns_round_trip, test_updated_staff_turns_formulas_into_values
- `tests/test_writer.py`: test_style_is_read_from_input_file, test_timetable_layout, test_statistics_file_is_one_table, test_supplement_in_statistics, test_updated_staff_file_is_reusable, test_teacher_labels, test_blank_names_show_teacher_code, test_timetable_with_codes, test_shortage_file, test_long_names_widen_columns_and_rows, test_statistics_file, test_statistics_file_overtime, test_mark_colours_are_not_copied_as_input_style
