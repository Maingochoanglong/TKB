# Thiết kế: gộp luật có sẵn vào bộ ghép luật

Tài liệu này viết trước khi đổi code xếp TKB, để anh/chị duyệt. Nó là bước cuối của kế hoạch "tùy chỉnh tối đa" (giai
đoạn 2 ghi: "Gộp luật có sẵn về bộ ghép, chỉ còn một cách cài đặt mỗi luật, là bước riêng: đổi mã kết quả, làm sau khi
có benchmark chất lượng"). Số liệu đo ở mục 3 lấy bằng công cụ mới `tools/do_chat_luong.py`.

## 0. Tóm tắt

- **Hiện nay mỗi luật có sẵn có hai cách cài.** Sheet LUẬT có 22 dòng mặc định (`luat_co_san.NATIVES`):
  - dòng giữ đúng dạng gốc thì xếp bằng **mã hóa riêng** (khối code viết tay trong solver, checker, LNS, chẩn đoán);
  - dòng đã sửa khác dạng gốc thì xếp bằng **bộ ghép** (`bo_ghep`: mỗi phép đo viết một lần cho mô hình và cho bộ
    kiểm tra).
- **Mục tiêu:** mỗi luật chỉ một cách cài là bộ ghép. Luật có sẵn chỉ còn là dòng mẫu, có tên dễ đọc.
- **Vì sao:**
  - Hai cách cài dần lệch nhau. Đo cho bước này đã tìm ra hai chỗ lệch:
    - tắt luật ưu tiên có sẵn thì luật vẫn chạy (đã sửa ở PR #34);
    - luật theo giáo viên của bộ ghép chưa tính tiết bù cho người dạy bù như bản gốc (mục 3.2).
  - Mỗi thay đổi luật hiện phải viết hai, ba lần: solver, checker, `lns.qa`, chẩn đoán.
  - Câu dòng mẫu và cách xếp thật có thể khác nhau mà không ai thấy.
- **Đo được (mục 3):** {{TOM_TAT_SO_LIEU}}
- **Mã kết quả:** đổi với mọi file, một lần, ở PR chuyển mô hình (mục 6, PR D).
- **Đề xuất:** 5 PR theo thứ tự mục 6. PR A–C không đổi mã kết quả của file không có luật tự ghép.
- **Cần anh/chị quyết:** mục 5.

## 1. Hiện trạng

### 1.1 Mã hóa riêng nằm ở đâu

| Nhóm | Luật có sẵn (khóa) | Mô hình CP-SAT | Ngoài mô hình | Bộ kiểm tra | LNS (`qa`) |
|---|---|---|---|---|---|
| Bảo vệ học sinh | `nhom_buoi`, `toi_da_ngay`, `ghep_cap`, `lien_nhau`, `tang_cuong` | khối "Luật bảo vệ học sinh" của `build_timetable` | `allocation.paired_groups` (phân công giữ số tiết chẵn), `chan_doan.precheck` (phép đếm) | `_check_student_rules` | — |
| HĐTN và GVCN | `hdtn_co_dinh`, `hdtn_ngay`, `hdtn_cuoi_buoi`, `tiet_gvcn`, `chi_gvcn` | `allowed_slots`, mục tiêu `hdtn_flex_distance` | `build_problem` tách course HĐTN cố định/linh hoạt; GVCN giữ tiết 1 (`homeroom_slots`); `homeroom_only` (phần chủ nhiệm, quyền dạy); `staff` không cho GVCN nghỉ buổi có tiết 1 | khối HĐTN, "Quyền dạy" | khoảng cách HĐTN |
| Người dạy | `lien_tiet`, `gvcn_truoc` | "Liên tiết", "GVCN trước" | — | `_check_teacher_order` | — |
| Lịch giáo viên | `co_so`, `doi_co_so` (`buoi_nghi`, `co_so_2` chỉ có dạng gốc) | `_teacher_sessions`, `_campus_day_switch` | `phan_cong.teacher_slots` | `_check_teacher_sessions` | đổi cơ sở |
| Ưu tiên khi xếp giờ | `mon_nang`, `buoi_sang`, `tai_ngay`, `tai_ngay_1`, `rai_deu`, `rai_deu_sang`, `tiet_trong` | các khối mục tiêu cuối `build_timetable` | — | (quality sheet đã dùng bộ ghép) | môn nặng, buổi sáng, rải đều, tải ngày, tiết trống |

Thêm vào đó:
- `config.OFF` và `config.WEIGHTS` cho biết luật nào tắt và đổi điểm.
- Các tham số `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, `PAIR_MIN_LESSONS` đọc từ số của dòng.
- `chan_doan._rules` thử bỏ từng luật gốc bằng `OFF`.

### 1.2 Bộ ghép đã có những gì

- 10 phép đo, mỗi phép một hàm cho cả mô hình (`_Cp`) và bộ kiểm tra/QA (`_Eval`).
- Các đường tắt đọc câu bộ ghép:
  - cắt miền ô (`banned`);
  - nhóm ghép cặp (`forced_pairs`);
  - quyền dạy ở tầng phân công (`allowed`/`refusing`);
  - tải ngày tối đa (`day_cap`), giờ bận (`busy`), học cùng giờ (`links`), ghép lớp (`merges`).
- Test `test_generic_lowering_replaces_the_native_one` đã cho thấy 6 luật bắt buộc xếp bằng bộ ghép vẫn đúng mọi luật
  gốc.
- Mỗi dòng mặc định đã có câu bộ ghép đúng nghĩa. Sheet Chất lượng đếm vi phạm của mọi dòng bằng bộ ghép.

## 2. Công cụ đo `tools/do_chat_luong.py`

Mỗi cách xếp (biến thể) là một lần `solver.solve` trên cùng file, cùng tham số:

| Biến thể | Nghĩa |
|---|---|
| `goc` | như chương trình hiện nay |
| `ghep` | 20 luật có sẵn có câu bộ ghép: tắt mã hóa riêng (`OFF`, điểm 0) và xếp chính các dòng đó bằng bộ ghép |
| `ghep:k1,k2` | chỉ các luật có khóa k1, k2 |

- **Chấm điểm:** mọi TKB chấm cùng một cách, theo luật của file vào: bộ kiểm tra độc lập (số lỗi luật bắt buộc) và
  sheet Chất lượng (điểm trừ luật ưu tiên). In thêm số biến, số ràng buộc của mô hình và thời gian.
- **Riêng tư:** không in họ tên, không ghi file ra, nên dùng được với file thật của trường.
- **`--tung-luat`:** thêm một biến thể cho mỗi luật. Ba luật HĐTN cố định / HĐTN theo ngày đi cùng nhau (mục 3.2).

## 3. Số liệu

Các số dưới đây chạy trên máy Linux 4 lõi. Trường nhỏ: `time_limit` 10, 4 luồng. Trường mẫu và file của trường: hằng
số của `main.py` (bù giờ, bù tối đa +3, 1200 đơn vị thời gian, 8 luồng). "Điểm trừ" là tổng điểm luật ưu tiên của sheet
Chất lượng.

### 3.1 Bộ ghép như hiện nay

{{BANG_HIEN_NAY}}

### 3.2 Ba chỗ bộ ghép khác mã hóa riêng

1. **Tiết bù trong lịch của người dạy bù.**
   - Mã hóa riêng tính tiết bù (`problem.covers`: tiết người mới dạy thay phần bù của một người) vào lịch của **cả
     hai** người (`occ_terms`), ở cả hai chế độ. Nhờ vậy hai chế độ ra cùng một TKB.
   - Bộ ghép chỉ làm vậy với luật **bắt buộc**. Luật **ưu tiên** theo GV (tải ngày, tiết trống, đổi cơ sở) bỏ qua tiết
     bù.
   - Ở chế độ bù giờ, tiết bù cuối cùng thuộc người bù, nên TKB của bộ ghép kém hơn khi chấm: trường nhỏ 1100 điểm so
     với 800.
   - Ở chế độ tuyển thêm, ngược lại, bộ ghép "được lợi" vì chấm không tính tiết đó cho người bù: trường nhỏ 0 so với
     200. Đây không phải TKB tốt hơn.
   - Sửa: luật đếm theo GV dùng một nguồn tiết trong đó tiết bù thuộc cả hai người, cho cả mô hình và chấm (mục 4.2).
2. **Ba luật HĐTN gắn với cách dựng course.** Tắt riêng "HĐTN cố định" thì không xếp được, vì:
   - `build_problem` không tách course HĐTN nữa;
   - cả course chỉ được xếp vào ngày HĐTN linh hoạt (luật gốc "HĐTN theo ngày" vẫn bật);
   - mục tiêu gốc "HĐTN cuối buổi" phạt cả tiết cố định.

   Ba luật này phải chuyển cùng lúc. Đường tắt "tiết cố định" (mục 4.3) giữ nguyên cách dựng course.
3. **Ràng buộc thừa và cách hạ kém gọn.**
   - "Mỗi buổi một cơ sở" và "hạn chế đổi cơ sở" thêm khoảng 2 500 ràng buộc ở trường chỉ có một cơ sở. Mã hóa riêng
     bỏ qua trường hợp này.
   - Phép "có tiết" (`_Cp.any`) dùng k + 1 ràng buộc, trong khi một `AddMaxEquality` là đủ.

### 3.3 Bản thử nghiệm: sửa ba chỗ trên

Bản thử nghiệm sửa (1) và (3) trong `bo_ghep`. Mục (2) chưa sửa: các biến thể đo ba luật HĐTN cùng nhau.

{{BANG_THU_NGHIEM}}

### 3.4 Từng luật (trường mẫu, 120 đơn vị thời gian, bản thử nghiệm)

{{BANG_TUNG_LUAT}}

## 4. Thiết kế

### 4.1 Luật có sẵn chỉ là dòng mẫu

- `luat_co_san.NATIVES` giữ tên, dòng mẫu và tên dễ đọc (`titles`). Không còn `OFF`, `WEIGHTS` hay tham số trong
  `config`: số và điểm nằm ngay trong dòng.
- Mọi dòng của sheet LUẬT (trừ dòng Tạm tắt) vào `config.CUSTOM_RULES`. `apply` chỉ còn nhận ra dòng mẫu để đọc tên
  dễ đọc.
- `buoi_nghi`, `co_so_2` (dạng `nghi_gv`, `co_so_2`) vẫn là luật gốc. Chúng đọc cột của sheet NHÂN SỰ, không có câu
  bộ ghép. Tắt được như hiện nay.
- Còn giữ trong code vì không phải "luật về ô" mà là cơ chế phân công:
  - quyền dạy theo chức vụ (`resolve_roles`, `may_teach`);
  - phần chủ nhiệm (`split_homeroom`);
  - thứ tự bù.

### 4.2 Bộ ghép: đúng nghĩa và gọn như mã riêng

- **Tiết bù.** Luật đếm theo GV (phạm vi hay "Đếm theo" có GV, trừ phép đo Người dạy) dùng một nguồn tiết trong đó tiết
  bù (`problem.covers`) thuộc cả người mới và người bù, như `occ_terms`. Dùng ở cả `build` (thay cho lần hạ thứ hai
  hiện nay), `violations` và `qa`.
- **Nhóm không thể vi phạm.** Phép đo Số khác nhau bỏ nhóm có không quá n giá trị, ví dụ trường một cơ sở.
- **`_Cp.any`** dùng `AddMaxEquality` (một ràng buộc).
- **Hạ đặc biệt** cho các dạng mà mã riêng có cách mã hóa tốt hơn, chỉ khi số đo cho thấy cần (mục 3.4). Ví dụ:
  - "tiết trống của GV" dùng bool chiếm chỗ `v == sum(...)` vì GV không trùng giờ;
  - "các tiết liền nhau" dùng mẫu "môn – môn khác – môn".

  Hạ đặc biệt nằm trong hàm của phép đo, nên luật tự ghép cùng dạng cũng được lợi.

### 4.3 Đường tắt đọc câu bộ ghép

Các việc ngoài mô hình hiện đọc `config` sẽ đọc dòng luật qua một hàm của `bo_ghep`, như `banned` đang làm:

| Việc | Hiện nay | Sau gộp |
|---|---|---|
| Course HĐTN cố định (`build_problem`) | `HDTN_FIXED_SLOTS` khi `on("hdtn_co_dinh")` | `bo_ghep.fixed(subject)`: luật bắt buộc Số tiết "Đúng n" theo (lớp, ô) ở ô có nhãn → các ô cố định của môn |
| Ngày HĐTN linh hoạt | `HDTN_FLEX_DAYS` | `banned` (đã có): luật Vị trí bắt buộc không xét GV |
| Tiết luôn do GVCN (`allowed_slots`, `homeroom_slots`, `staff`) | `HOMEROOM_PERIODS` khi `on("tiet_gvcn")` | `bo_ghep.homeroom_slots()`: luật Người dạy "Do" Chủ Nhiệm bắt buộc có ô, không môn |
| Môn chỉ GVCN dạy (`homeroom_only`) | `HOMEROOM_ONLY_SUBJECTS` khi `on("chi_gvcn")` | `allowed` (đã có) + môn có nhãn Chỉ GVCN dạy của dòng |
| Nhóm ghép cặp (`paired_groups`) | `PAIR_MIN_LESSONS`, `PAIR_EXCLUDED` | `forced_pairs` mở rộng: phạm vi có Nhóm môn, cột Áp dụng khi, nhãn trừ |
| Phép đếm trước khi xếp (`precheck`) | `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, nhóm ghép cặp | `bo_ghep.precheck` mở rộng: Số tiết "Tối đa n" theo (lớp, đơn vị thời gian) → sức chứa cả tuần; ghép cặp cần buổi ≥ 2 tiết |

### 4.4 Bộ kiểm tra

- Phần luật của `checker.check` dùng `bo_ghep.violations(hard=True)` cho mọi dòng.
- Phần cấu trúc giữ nguyên: đủ tiết, không trùng giờ, định mức, quyền dạy, phần chủ nhiệm, bù giờ, buổi nghỉ, cơ sở 2,
  phòng.
- Các hàm kiểm tra cũ (`_check_student_rules`, `_check_teacher_order`, khối HĐTN, phần cơ sở) chuyển sang `tests/`.
  Ở đó chúng làm **phép thử độc lập**: test đổi chỗ ngẫu nhiên đối chiếu bộ ghép với chúng, như
  `test_cross_check_with_the_checker`. Bộ ghép có lỗi đếm thì test bắt được, mà chương trình không phải sửa hai nơi.

### 4.5 LNS, chẩn đoán, luật bảo vệ học sinh

- **`lns._Search.qa`:** chỉ còn phần bộ ghép (`bo_ghep.qa`) và chi phí phân công.
- **Chẩn đoán:** mỗi dòng bắt buộc là một họ luật như luật tự ghép hiện nay. `_matters` và nhánh `daily` bỏ đi.
- **`--no-student-rules` (`main.py` `LUAT_HOC_SINH`):** bỏ các dòng có cột Nhóm = "Bảo vệ học sinh" (tên nhóm của
  bộ mẫu). Sheet Chất lượng ghi "tắt" như nay.

### 4.6 File cũ, mã quy định, mã kết quả

- **File cũ** (không có sheet LUẬT; cột cũ của QUY ĐỊNH): vẫn đọc thành dòng mặc định như nay (`rules.LEGACY`).
- **Mã quy định** (`rules.code()`) tính từ các dòng luật thay cho `OFF`/`WEIGHTS`/tham số, nên đổi.
  - TKB đã lưu (`TKB đã xếp`) ghi mã cũ sẽ được xếp lại ít xáo trộn như khi đổi luật.
  - Xếp lại ít xáo trộn giữ các ô cũ, nên TKB cũ không mất.
- **Mã kết quả:** đổi ở PR D. Cập nhật `REFERENCE`, bảng README "Chạy trên máy khác", đặc tả §0 và §9, file mẫu đầu ra.

## 5. Cần anh/chị quyết

1. **Đồng ý đổi mã kết quả một lần** (PR D) để mỗi luật chỉ còn một cách cài? {{DE_XUAT_1}}
2. **Ngưỡng chất lượng cho PR D.** Đề xuất: trên trường nhỏ (hai chế độ), trường mẫu và file của trường, theo hằng số
   của `main.py`:
   - 0 lỗi luật bắt buộc;
   - điểm trừ không cao hơn cách hiện nay;
   - thời gian không quá +20 %.

   Luật nào không đạt thì thêm cách hạ đặc biệt (mục 4.2) rồi đo lại, không giữ mã riêng.
3. **Tiết bù ở chế độ tuyển thêm** vẫn tính vào lịch người bù cho mọi luật theo GV, như nay. Nhờ vậy hai chế độ cùng
   một TKB. Đề xuất: giữ.
4. **Bộ kiểm tra cũ chuyển thành phép thử trong test** (mục 4.4)? Đề xuất: có.

## 6. Kế hoạch PR

| PR | Nội dung | Mã kết quả |
|---|---|---|
| **A. Bộ ghép đúng nghĩa, gọn** | Mục 4.2: tiết bù cho luật theo GV, nhóm không thể vi phạm, `any` một ràng buộc; test | Giữ, trừ file có luật tự ghép theo GV có tiết bù, hoặc có luật Số khác nhau / Khoảng cách |
| **B. Đường tắt đọc câu bộ ghép** | Mục 4.3: `fixed`, `homeroom_slots`, `forced_pairs` mở rộng, `precheck` mở rộng; dòng có sẵn vẫn xếp bằng mã riêng | Giữ |
| **C. Bộ kiểm tra theo bộ ghép** | Mục 4.4; test đối chiếu với hàm cũ | Giữ |
| **D. Chuyển mô hình** | `luat_co_san.apply` đưa mọi dòng vào `CUSTOM_RULES`; tắt mọi khối mã riêng; `lns.qa`; chẩn đoán; `--no-student-rules`; đo đủ ngưỡng mục 5.2 | **Đổi** |
| **E. Dọn code** | Xóa khối mã riêng, `config.OFF`/`WEIGHTS`/tham số luật; tài liệu (README, đặc tả, CLAUDE.md), CODE_MAP, file mẫu | Giữ (như D) |

Công cụ đo đi cùng PR này. Mỗi PR B–E chạy lại công cụ trên ba trường và ghi số vào mô tả PR.

## 7. Rủi ro

- **Chất lượng hay thời gian kém hơn ở trường lớn.** Ngưỡng mục 5.2 và mục 3.4 cho biết luật nào cần hạ đặc biệt.
- **Bộ kiểm tra bớt độc lập:** mô hình và bộ kiểm tra dùng chung hàm phép đo. Phép thử độc lập trong test (mục 4.4)
  giữ lại một cách đếm thứ hai.
- **Đổi mã quy định:** TKB đã lưu được xếp lại ít xáo trộn một lần (mục 4.6).
- **LNS:** cách chia chi phí theo (lớp, ngày) của bộ ghép khác `qa` cũ, nên vùng được chọn khác. Đã tính trong số đo
  của PR D.
