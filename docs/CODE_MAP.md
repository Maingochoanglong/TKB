# Code map

Sinh tự động bởi `python tools/code_map.py --write`, đừng sửa tay. Bản kèm số dòng: `python tools/code_map.py`.


## main.py — Xếp thời khóa biểu: chỉ cần sửa các hằng số bên dưới rồi bấm nút Run (▶) để chạy.
Hằng số: `FILE_VAO`, `THU_MUC_OUT`, `CHE_DO`, `SO_TIET_BU_TOI_DA`, `LUAT_HOC_SINH`, `THOI_GIAN_TOI_DA`, `CHAY_TAI_LAP_DUOC`, `FILE_TKB`, `FILE_THONG_KE`, `SO_LUONG`, `BASE_DIR`
- `_blank(value)`
- `_resolve(path)` — Đường dẫn tương đối tính từ thư mục dự án; để trống = chính thư mục dự án.
- `run(file_vao, thu_muc_out, file_tkb, thoi_gian_toi_da, luat_hoc_sinh, chay_tai_lap_duoc, so_luong, che_do, so_tiet_bu_toi_da, file_thong_ke)` — Chạy xếp TKB; trả về 0 nếu thành công.

## tkb/__main__.py — Chạy: python -m tkb <file vào.xlsx> [-o TKB.xlsx] ...
- `use_utf8_output()` — In tiếng Việt không lỗi khi output bị chuyển hướng trên Windows (mặc định bảng mã cp1252).
- `main(argv)`

## tkb/allocation.py — Phân phần GVCN, sinh các "course" (lớp, môn, số tiết, GV hợp lệ) và GV bổ sung.
- `class Course`
- `class Problem`
  - `.overtime_mode()`
  - `.roles()` — Chủ Nhiệm, Bộ Môn, các GV chuyên biệt (theo thứ tự trong file), Quản Lý.
  - `.specialist_subjects()`
  - `.subject_label(subject)` — Tên môn in trong TKB: tên viết tắt trong config, không có thì tên như trong file vào.
  - `.class_courses(class_name)`
- `all_slots()`
- `roles_for_subject(subject, specialists)` — Các chức vụ (ngoài chủ nhiệm/quản lý) được dạy môn này.
- `resolve_roles(staff, subject_labels)` — Suy ra GV chuyên biệt từ tên chức vụ: (chức vụ -> môn, chức vụ -> cách ghi trong file ra).
- `manager_allowed(rule, class_name, grade, subject)`
- `split_homeroom(class_name, grade_req, quota, reserved, specialist)` — Số tiết từng môn GVCN dạy cho lớp của mình.
- `supplement_capacity(role, teachers)` — Định mức GV bổ sung: Số tiết lớn nhất của GV cùng chức vụ trong file vào;
- `make_supplements(role, count, teachers, label)`
- `overtime_allowance(t, overtime_max)` — Số tiết bù tối đa của một GV ở chế độ bù giờ.
- `build_problem(staff, curriculum, supplement_counts, overtime_max)` — Dựng bài toán.
  · Môn có luật trong config được gọi theo tên trong config; tên như trong file giữ lại để in ra.
  · Sắp môn theo tên: đổi thứ tự dòng trong file chương trình học không làm đổi TKB.
  · Môn/khối dành riêng cho quản lý thì GVCN không lấy để bù.
  · Nhu cầu tối đa theo chức vụ để dựng đủ GV bổ sung dự kiến.

## tkb/checker.py — Kiểm tra độc lập mọi luật cứng trên TKB đã xếp (không dựa vào mô hình solver).
- `check(problem, lessons, student_rules)`
  · Lớp: mỗi slot đúng 1 tiết, đủ số tiết từng môn.
  · GV: không trùng giờ, không vượt định mức.
  · Quyền dạy.
  · GVCN dạy đủ phần đã phân; phần dạy thêm chỉ là tiết bù hợp lệ (chế độ bù giờ).
  · Bù giờ: GVCN được ưu tiên bù lớp mình. Bộ môn đang dạy bù mà còn dạy ở lớp X một môn GVCN lớp X được dạy, trong khi GVCN lớp X chưa bù hết mức, thì chuyển tiết đó cho GVCN luôn làm được (GVCN chỉ dạy lớp mình nên giờ đó rảnh) và bớt tiết bù của bộ môn: phân công chưa đúng thứ tự ưu tiên.
  · HĐTN: 2 slot cố định + phần còn lại trong các ngày linh hoạt.
- `_check_student_rules(problem, lessons)`

## tkb/config.py — Các luật nghiệp vụ của hệ thống xếp TKB mà file vào không có.
Hằng số: `TV`, `TOAN`, `HDTN`, `KH`, `LSDL`, `DD`, `TNXH`, `KNS`, `CONG_NGHE`, `TOAN_TC`, `TV_TC`, `TIENG_ANH`, `TIN_HOC`, `DISPLAY_NAMES`, `DAYS`, `MORNING`, `AFTERNOON`, `DAY_SESSIONS`, `OFF_LABEL`, `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS`, `ROLE_HOMEROOM`, `ROLE_GENERAL`, `ROLE_MANAGER`, `ROLE_LABELS`, `STAFF_SHEET`, `PROGRAM_SHEET`, `HOMEROOM_ONLY_SUBJECTS`, `GENERAL_FORBIDDEN_SUBJECTS`, `MANAGER_RULES`, `HOMEROOM_PRIORITY`, `HOMEROOM_CUT_ORDER`, `HOMEROOM_FILL_ORDER`, `HOMEROOM_PERIODS`, `SUPPLEMENT_NAME`, `MODE_HIRE`, `MODE_OVERTIME`, `MODES`, `OVERTIME_ROLES`, `OVERTIME_MAX`, `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, `MORNING_SUBJECTS`, `AFTERNOON_SUBJECTS`, `SESSION_SUBJECT_LIMITS`, `ORTOOLS_VERSION`
- `class Session`
- `class ManagerRule` — Quản lý chỉ dạy môn `subject` của khối `grade`.
- `rule_subjects()` — Các môn được nhắc tới trong luật ở trên (để kiểm tra tên môn trong file vào).
- `class Weights`
- `class Settings`

## tkb/program.py — Đọc chương trình học: cột 'Môn học' và các cột 'Khối k'.
- `_rule_names()`
- `canonical_subject(name)` — Tên môn dùng khi dựng bài toán: tên trong config nếu khớp một môn có luật, không thì giữ tên trong file.
- `read_program(path)` — Đọc sheet "CHƯƠNG TRÌNH HỌC" của file vào.
- `subjects_in_order(curriculum)` — Các môn theo thứ tự xuất hiện trong file.
- `missing_rule_subjects(curriculum)` — Môn có luật trong config nhưng không có trong chương trình học (thường do gõ khác tên).

## tkb/solver.py — Mô hình CP-SAT: phân tiết cho GV và xếp tiết vào khung giờ.
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
- `class Assignment`
- `assign(problem, settings)` — Tối ưu theo thứ tự: (1) tiết/GV bổ sung, rồi (2) chia môn, dạy thay, cân bằng tải.
- `timetable(problem, settings, fixed, hint)`
  · Mỗi lớp mỗi slot đúng 1 tiết (hoặc tối đa 1 nếu chương trình ít hơn số slot).
  · GV dạy course tại slot nào.
  · Luật bảo vệ học sinh: số tiết tối đa của một số môn trong mỗi buổi; môn có từ 2 tiết trong một buổi thì các tiết phải liền nhau (không có mẫu "môn – môn khác – môn").
  · HĐTN linh hoạt: càng gần cuối buổi càng tốt.
  · Hạn chế môn nặng ở tiết cuối ngày.
  · Buổi sáng dành cho TV, Toán; tiết tăng cường ưu tiên buổi chiều để nhường buổi sáng cho tiết chính.
  · Tải ngày của GV: phạt vượt mức mong muốn và vượt buffer (+1).
  · Rải đều môn trong tuần theo từng lớp.
  · Tiết trống giữa buổi của GV không chủ nhiệm.
- `solve(staff, curriculum, settings, log)` — Toàn bộ quy trình: phân công → xếp giờ với phân công cố định → (dự phòng) mô hình tích hợp.

## tkb/staff.py — Đọc và kiểm tra file Excel danh sách nhân sự.
Hằng số: `SPECIAL_ROLES`, `_CLASS_RE`
- `class InputError` — Lỗi dữ liệu đầu vào.
- `class Teacher`
  - `.grade()`
  - `.code()` — Mã GV hiển thị trong các file ra, vd "Bộ Môn 5", "Chủ Nhiệm 1/1".
- `normalize(text)`
- `clean_name(text)` — Chữ trong file, bỏ khoảng trắng thừa (giữ hoa thường).
- `subject_key(name)` — Khóa so khớp tên môn/chức vụ: không phân biệt hoa thường, dấu câu và chữ "và".
- `role_errors(teachers, subjects)` — Chức vụ không phải Chủ Nhiệm/Bộ Môn/Quản Lý và không trùng tên môn nào của chương trình học.
- `canonical_title(role, index, class_name)`
- `parse_class(value)` — Cột Lớp: khối/số thứ tự, vd "1/1".
- `find_sheet(wb, name)` — Sheet có tên `name` (không phân biệt hoa thường), hoặc None.
- `staff_sheet(wb)` — Sheet nhân sự: sheet tên "NHÂN SỰ" nếu có, không thì sheet đầu tiên.
- `_blank(value)`
- `_find_columns(ws)` — Dòng tiêu đề và vị trí các cột (mẫu V8). Bắt buộc: Họ và Tên, Chức Vụ, Số Tiết/Tuần; không bắt buộc: Lớp, STT.
- `_to_lessons(value, title)`
- `make_teacher(name, role, index, class_name, lessons, row, label)`
- `validate(teachers)` — Báo mọi lỗi trùng lặp cùng lúc (mỗi lỗi một dòng).
- `read_staff(path, subjects)` — Đọc sheet nhân sự; `subjects`: các môn của chương trình học để kiểm tra chức vụ (None = không kiểm).
- `class_sort_key(class_name)`
- `classes_from_staff(teachers)`

## tkb/style.py — Style của các file ra, chép từ sheet NHÂN SỰ của file vào (font, viền, căn lề, nền, chiều cao dòng).
Hằng số: `DEFAULT_ROW_HEIGHT`, `MAX_COLUMN_WIDTH`, `STAFF_HEADERS`
- `with_bold(font, bold)`
- `class CellStyle`
  - `.of(cell)`
  - `.apply(cell, bold, horizontal, wrap)`
- `class Style`
  - `.from_file(path)` — Style của ô tiêu đề và ô dữ liệu đầu tiên ở cột Chức Vụ của sheet nhân sự.
  - `.font_size()`
  - `.line_height()` — Chiều cao một dòng chữ (point).
  - `.text_width(text)` — Độ rộng ước lượng (đơn vị cột Excel) của một dòng chữ.
  - `.lines(text, width)`
  - `.header_cell(ws, row, col, value)`
  - `.body_cell(ws, row, col, value, bold, horizontal)`
  - `.table(ws, header, rows, top, bold_last)` — Bảng như sheet nhân sự của file vào: dòng tiêu đề rồi các dòng dữ liệu. Trả về dòng cuối.
  - `.fit_columns(ws, first_row, minimum, skip_rows)` — Nới độ rộng cột vừa chữ dài nhất (tối đa MAX_COLUMN_WIDTH, dài hơn thì xuống dòng).

## tkb/template.py — File vào mẫu V8: một file Excel, hai sheet, style giống file của nhà trường.
Hằng số: `LIST_SHEET`, `STAFF_HEADERS`, `STAFF_WIDTHS`, `LAST_ROW`, `BLANK_ROWS`, `MAX_LESSONS`, `BLANK_GRADES`, `FONT`, `HEADER_FONT`, `THIN`, `BORDER`, `CENTER`, `NAME_ALIGN`, `ROW_HEIGHT`, `ERROR_STYLE`, `NOTES`
- `role_label(t)`
- `role_choices(teachers)` — Chủ Nhiệm, Bộ Môn, các chức vụ chuyên biệt có trong danh sách, Quản Lý (chỉ để gợi ý).
- `staff_row(t)`
- `_style_rows(ws, first, last, n_cols, header, name_col)`
- `_staff_sheet(wb, teachers)`
- `_whole(cells)`
- `_program_sheet(wb, curriculum, teachers)`
- `write_staff_template(path, teachers, curriculum)` — Ghi file vào mẫu V8 (sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC).
- `main(argv)`

## tkb/writer.py — Xuất ra Excel: TKB (chỉ các sheet Khối); file thống kê (số tiết từng môn của mỗi giáo viên); file vào
Hằng số: `MAX_DAY_WIDTH`, `BLOCK_GAP`, `LABEL_PAD`, `HIRE_LABEL`, `CODE_HEADER`, `LOAD_HEADER`, `OVERTIME_HEADER`, `STATS_SHEET`, `TOTAL_HEADER`
- `teacher_labels(teachers)` — Chức vụ -> tên hiển thị dưới tên môn trong TKB.
- `session_rows()` — Các hàng của bảng TKB: (buổi, tiết trong ngày). Cột TIẾT ghi tiết trong ngày: sáng 1–4, chiều 5–7.
- `_merge(ws, style, r1, c1, r2, c2, value)`
- `_grade_sheets(wb, solution, style)`
- `staff_rows(solution)` — GV thật theo thứ tự file gốc, sau đó GV bổ sung được dùng.
- `write_timetable(solution, path, style)` — File TKB: chỉ các sheet Khối. Nhân sự và thống kê ghi ở file thống kê (write_statistics).
- `_stats_name(t)`
- `subject_table(solution, style)` — Họ và Tên | Chức Vụ (Mã GV) | số tiết từng môn | Tổng Tiết, mỗi giáo viên một dòng; cuối bảng có dòng Tổng.
- `write_statistics(solution, path, style)` — File thống kê: một bảng số tiết từng môn của mỗi giáo viên (xem subject_table).
- `_copy_style(src, dst)`
- `write_updated_staff(solution, source, path)` — Chép file vào, thêm người cần tuyển vào cuối danh sách nhân sự và các cột Mã GV, số tiết thực dạy

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
- `tests/test_code_map.py`: test_code_map_is_up_to_date
- `tests/test_main.py`: test_run_writes_outputs, test_run_reports_missing_file, test_relative_paths_resolve_from_script_dir, test_run_rejects_bad_thread_count, test_run_passes_thread_count, test_run_overtime_mode_needs_no_hire, test_run_rejects_bad_mode, test_run_single_input_file_with_program_sheet, test_run_without_program_sheet_fails, test_defaults_are_overtime_student_rules_240s_reproducible, test_blank_output_folder_means_project_folder, test_blank_time_limit_means_unlimited, test_bad_time_limit_and_blank_input_are_rejected, test_cli_time_limit_zero_is_unlimited
- `tests/test_reproducible.py`: test_same_timetable_across_runs, test_reference_fingerprint, test_ortools_version_is_pinned, test_no_wall_clock_limit_in_reproducible_mode
- `tests/test_solver.py`: test_small_school_solves_and_passes_checker, test_hdtn_fixed_and_flex, test_missing_general_teacher_becomes_supplement, test_checker_detects_violations, test_homeroom_teaches_first_period, test_heavy_subjects_avoid_last_period, test_core_subjects_in_the_morning, test_slot_capacity_limits_assignment, test_sample_school_assignment_is_optimal, test_reproducible_mode_gives_identical_timetables, test_overtime_mode_covers_shortage_without_hiring, test_overtime_mode_hires_only_the_remainder, test_overtime_homeroom_before_general, test_checker_flags_invalid_overtime, test_sample_school_overtime_assignment, test_same_subject_lessons_are_contiguous, test_contiguous_when_a_subject_must_repeat_in_a_session, test_checker_detects_split_subject, test_checker_requires_homeroom_to_cover_own_class_first
- `tests/test_staff.py`: test_bad_lessons, test_duplicates_rejected, test_read_sample_staff, test_program_file_is_read_as_written, test_subject_names_match_rules_loosely, test_columns_and_auto_numbering, test_numbered_titles_are_rejected, test_old_headers_are_rejected, test_class_errors, test_class_turned_into_date, test_program_sheet_aliases_and_total_row, test_missing_program_sheet_is_an_error, test_all_errors_at_once
- `tests/test_template.py`: test_template_style_and_dropdowns, test_blank_template_has_only_headers, test_updated_staff_keeps_template_and_style, test_cli_writes_blank_template
- `tests/test_writer.py`: test_style_is_read_from_input_file, test_timetable_layout, test_statistics_file_is_one_table, test_supplement_in_statistics, test_updated_staff_file_is_reusable, test_teacher_labels, test_blank_names_show_teacher_code, test_long_names_widen_columns_and_rows, test_statistics_file, test_statistics_file_overtime
