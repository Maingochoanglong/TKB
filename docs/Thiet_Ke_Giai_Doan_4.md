# Thiết kế giai đoạn 4: phòng học, học cùng giờ, đa ngôn ngữ

Tài liệu này viết trước khi làm code, để nhà trường duyệt. Nó tiếp nối kế hoạch "tùy chỉnh tối đa": code chỉ chứa cơ
chế, còn quy định là dữ liệu trường tự ghi. Giai đoạn 0–3 đã xong (PR #24 → #29).

## 0. Tóm tắt

| Phần | Nội dung | Cỡ việc | Mã kết quả |
|---|---|---|---|
| **4A. Phòng học dùng chung** | Sheet `PHÒNG` không bắt buộc. Mỗi tiết của môn cần phòng có một phòng; tên phòng in trong TKB; thêm file TKB phòng | 1 PR, cỡ 3B | Giữ nguyên nếu không có sheet |
| **4B-1. Chia nhóm, dạy kèm** | Một lớp học hai môn cùng giờ, mỗi môn một người dạy (nửa lớp Tin, nửa lớp Tiếng Anh; GV chính + trợ giảng) | 1 PR | Giữ nguyên nếu không có dòng luật |
| **4B-2. Ghép lớp** | Nhiều lớp học chung một tiết với một người dạy; người dạy chỉ tính một tiết | 1 PR, lớn nhất | Giữ nguyên nếu không có dòng luật |
| **4C. Đa ngôn ngữ** | Giao diện và tiêu đề cột file bằng tiếng Anh | Lớn, chủ yếu việc chép chữ | Không đổi |

**Đề xuất:** làm 4A → 4B-1 → 4B-2. Hoãn 4C cho đến khi có trường không dùng tiếng Việt.

**Khác kế hoạch ban đầu:** kế hoạch ghi giai đoạn 4 đổi mã kết quả. Thiết kế dưới đây thêm tính năng bên cạnh mô hình cũ,
không viết lại. Vì vậy file không dùng tính năng mới cho đúng mã cũ, như các giai đoạn 1–3.

Các điểm cần anh/chị quyết nằm ở mục 5.

## 1. Hiện trạng

- **Phòng.** Kiểu luật "Số lớp học cùng lúc tối đa" giới hạn được số lớp học một môn cùng giờ, vd phòng Tin: 1. Nhưng:
  - không có tên phòng, nên TKB không ghi lớp học phòng nào;
  - không ghi được phòng dùng cho nhiều môn (phòng đa năng cho Âm nhạc và Mỹ thuật);
  - trường nhiều cơ sở phải tự ghép phạm vi "Giờ học, Cơ sở".
- **Một tiết.** Mỗi tiết đúng một lớp, một môn, một người dạy (`allocation.Course`, `solver.Lesson`). Không ghi được:
  - chia nhóm (nửa lớp học môn này, nửa lớp học môn kia cùng giờ);
  - dạy kèm (GV nước ngoài cùng trợ giảng);
  - ghép lớp (hai lớp ít học sinh học chung giờ Thể dục).
- **Ngôn ngữ.** Mọi chữ đều là tiếng Việt:
  - giao diện: khoảng 360 chuỗi trong `app.js` và 160 dòng trong `index.html`;
  - Python (tiêu đề cột, báo lỗi, hướng dẫn): khoảng 1.600 chuỗi.

## 2. Giai đoạn 4A: phòng học dùng chung

### 2.1 Cách ghi
Sheet mới, không bắt buộc, `PHÒNG`, mỗi dòng một phòng:

| Phòng | Cơ sở | Môn | Khối | Sức chứa |
|---|---|---|---|---|
| Phòng Tin 1 | | Tin học | | 1 |
| Phòng Tin 2 | | Tin học | 4, 5 | 1 |
| Phòng đa năng | | Âm nhạc, Mỹ thuật | | 1 |
| Sân trường | | Thể dục | | 3 |
| Phòng Tin | Điểm Tân Phú | Tin học | | 1 |

- **Phòng:** tên tùy ý, không trùng trong một cơ sở.
- **Cơ sở:** tên như cột Cơ sở của sheet LỚP. Trống là Cơ sở 1; trường một cơ sở để trống.
- **Môn:** các môn học ở phòng này. Ghi được nhãn môn (tiêu đề một cột Có/Không của CHƯƠNG TRÌNH HỌC), như cột Môn của
  sheet LUẬT.
- **Khối:** chỉ các khối này dùng phòng; trống là mọi khối.
- **Sức chứa:** số lớp học cùng lúc trong phòng; trống là 1. Sân rộng ghi 3.

### 2.2 Nghĩa
- Một tiết thuộc môn, khối và cơ sở mà có ít nhất một phòng ghi, thì phải học ở một phòng phù hợp. Đây là luật cứng.
- Tiết của môn không có phòng nào ghi thì học ở lớp, như hiện nay.
- Mỗi giờ học, số lớp trong một phòng không vượt sức chứa.
- Không có sheet `PHÒNG` thì không có ràng buộc mới; luật "Số lớp học cùng lúc tối đa" vẫn dùng như cũ.

### 2.3 Mô hình (`solver.build_timetable`)
- Gom tiết theo **loại**: (môn, khối, cơ sở). Mỗi loại có các phòng phù hợp. Các loại dùng chung phòng nối thành một **cụm**.
- **Cụm mà mọi phòng dùng cho đúng cùng các loại** (trường hợp thường gặp: các phòng Tin giống nhau, sân trường):
  - ràng buộc: mỗi giờ học, tổng số tiết của cụm ≤ tổng sức chứa;
  - cùng dạng ràng buộc mà luật "Số lớp học cùng lúc tối đa" đang dùng, nên không thêm biến.
- **Cụm có phòng dùng chung một phần** (phòng Tin 2 chỉ khối 4, 5; phòng đa năng dùng cho hai môn):
  - thêm biến nguyên `y[loại, phòng, giờ]` = số tiết của loại học ở phòng đó;
  - ràng buộc: tổng `y` theo phòng bằng số tiết của loại; tổng `y` trong một phòng ≤ sức chứa;
  - đây là bài toán luồng nên chính xác: có `y` thỏa thì xếp được phòng cho mọi tiết.
  - Cỡ biến: vd 20 loại × 3 phòng × 35 giờ ≈ 2.100 biến. Chỉ có ở trường ghi phòng kiểu này.
- **Xếp phòng cho từng tiết** làm sau khi xếp giờ, bằng Python thuần (`phan_cong.MinCostFlow`, cố định thứ tự nên mọi máy
  ra như nhau):
  - mỗi giờ học là một bài toán luồng nhỏ;
  - ưu tiên một lớp học cùng một phòng cho cùng môn cả tuần.
- **Phòng không vào mã kết quả.** Mã vẫn băm (lớp, ngày, tiết, môn, GV). Ràng buộc phòng chỉ đổi mã khi trường ghi phòng.
- **Vòng xếp lại (LNS):** không đổi cách chọn vùng. Biến `y` không bị cố định, luôn giải lại cùng các tiết của vùng.

### 2.4 Kiểm tra và chẩn đoán
- **`checker`:** mỗi giờ học, mỗi cụm phải xếp được phòng (giải lại luồng nhỏ). Báo vd "Thứ 3 tiết 2: 3 lớp cần phòng
  Tin học (3/1, 4/2, 5/1) mà chỉ có 2 chỗ".
- **`chan_doan.precheck`** (phép đếm chắc chắn): tổng số tiết của một cụm ≤ tổng sức chứa × số giờ học của tuần.
- **`chan_doan._rules`:** thêm họ luật "Phòng". Khi không xếp được TKB, chẩn đoán thử bỏ ràng buộc phòng để biết phòng có
  phải nguyên nhân không.

### 2.5 File ra
- **TKB lớp:** ô có phòng thêm dòng thứ ba ghi tên phòng, vd "Tin học / TH1 / Phòng Tin 2". Ô khác giữ nguyên.
- **TKB giáo viên:** ô ghi thêm phòng, vd "3/1 Tin học · Phòng Tin 2".
- **File mới `TKB_phong.xlsx`:** mỗi phòng một bảng ngày × tiết, ô ghi lớp và môn; ngắt trang sau mỗi phòng như TKB giáo
  viên. Chỉ ghi khi có sheet `PHÒNG`.
- **File vào cập nhật:** giữ sheet `PHÒNG`. Sheet `TKB đã xếp` không lưu phòng: nạp lại thì xếp phòng lại theo cùng cách,
  nên ra cùng kết quả.

### 2.6 Giao diện
- **Bước Lớp** thêm bảng "Phòng học dùng chung", cùng cột như sheet. Ô Cơ sở gợi ý tên cơ sở; ô Môn gợi ý môn và nhãn môn.
- **Kịch bản:** thêm `scenario["rooms"]`. Mở file, ghi file và kiểm tra nhanh đi qua đúng các hàm đọc như dòng lệnh.
- **Bước Thời khóa biểu:** ô ghi phòng. Có bộ lọc "theo phòng" bên cạnh theo lớp, khối, giáo viên.

### 2.7 Mã quy định, tương thích, test
- **`rules.code()`:** thêm sheet `PHÒNG` dạng chuẩn hóa, chỉ khi có. File cũ ra cùng mã quy định, cùng mã kết quả.
- **Test:**
  - Phòng Tin 1 chỗ: không giờ nào có hai lớp học Tin, mỗi tiết Tin ghi đúng phòng.
  - Phòng dùng chung một phần (phòng Tin 2 chỉ khối 4, 5): xếp đạt, mọi tiết có phòng.
  - Ba cơ sở, mỗi cơ sở một phòng Tin.
  - `checker` báo khi đổi tay hai tiết làm thiếu phòng.
  - `precheck` báo khi phòng không đủ chỗ cả tuần.
  - Không có sheet: mã tham chiếu không đổi.
  - Trang web: thêm phòng ở bước Lớp, dấu ✓, xem TKB theo phòng.

### 2.8 Chưa làm ở 4A
- **Phòng riêng của từng lớp** (trường cấp 2, 3 học theo phòng bộ môn mọi môn): có thể ghi bằng phòng có Môn là mọi môn của
  lớp, nhưng không tối ưu cho cách học đó.
- **Đi lại giữa các phòng xa nhau trong một buổi:** không phạt.

## 3. Giai đoạn 4B: học cùng giờ

### 3.1 Ba trường hợp và một khái niệm
| Trường hợp | Ví dụ | Lớp | Người dạy |
|---|---|---|---|
| Chia nhóm | Lớp 4/1: nửa lớp học Tin học, nửa lớp học Tiếng Anh cùng giờ, rồi đổi | một lớp, hai môn | mỗi môn một người |
| Dạy kèm | Tiếng Anh bản ngữ có trợ giảng: môn riêng "Trợ giảng Tiếng Anh", cùng số tiết | một lớp, hai môn | mỗi môn một người |
| Ghép lớp | Thể dục lớp 3/1 và 3/2 học chung một sân, một GV | nhiều lớp, một môn | một người cho cả nhóm |

Cả ba là một **nhóm học cùng giờ**: một tập (lớp, môn) mà mọi tiết luôn xếp cùng giờ, cùng số tiết mỗi tuần.
- Chia nhóm và dạy kèm: các (lớp, môn) cùng lớp. Lớp tính là một tiết ở giờ đó. Mỗi môn có người dạy riêng, mỗi người
  tính tiết của mình.
- Ghép lớp: các (lớp, môn) khác lớp, chung một người dạy. Người đó tính một tiết cho cả nhóm.

Dạy kèm dùng một môn riêng ghi ở CHƯƠNG TRÌNH HỌC, vd "Trợ giảng Tiếng Anh" cùng số tiết với Tiếng Anh, chức vụ Trợ
Giảng dạy môn đó. Nhờ vậy không cần cơ chế thứ tư. Thống kê ghi đúng tiết của trợ giảng. Luật theo môn Tiếng Anh không
đếm nhầm tiết của trợ giảng.

### 3.2 Cách ghi: hai kiểu luật mới ở sheet LUẬT
Dùng sheet LUẬT vì nó đã có sẵn: bộ lọc lớp/khối/nhãn, câu đọc lại, nút "Dùng", chẩn đoán luật mâu thuẫn và hộp thoại
soạn luật trên giao diện.

| Kiểu luật | Cột ghi | Nghĩa (câu đọc lại) |
|---|---|---|
| **Học cùng giờ** (chia nhóm, dạy kèm) | Môn, Môn thứ hai; Khối, Lớp hoặc nhãn lớp | "Mỗi lớp khối 4: Tin học và Tiếng Anh học cùng giờ (chia nhóm), mỗi môn một người dạy" |
| **Ghép lớp** | Môn; Lớp hoặc nhãn lớp; Với mỗi: trống hoặc Khối | "Thể dục lớp 3/1, 3/2 học chung, một người dạy, tính một tiết" |

- **Bộ ghép (`bo_ghep`):** thêm phép đo "Cùng giờ" (họ "Đi cùng nhau"). So sánh "Cùng người" là ghép lớp, để trống là chia
  nhóm. Hai kiểu luật trên chỉ là cách điền sẵn, như các kiểu có sẵn.
- **Ràng buộc khi ghi:**
  - chỉ ghi Bắt buộc = Có;
  - không ghi Ngày, Tiết, Buổi, Áp dụng khi (luôn là mọi tiết của môn);
  - Với mỗi chỉ là Lớp, Khối, Cơ sở hoặc trống.
- **Báo lỗi** (`validate`, `chan_doan.precheck`):
  - các (lớp, môn) trong nhóm khác số tiết/tuần;
  - ghép lớp không còn ai được dạy môn đó ở mọi lớp trong nhóm;
  - chia nhóm mà chỉ một người dạy được cả hai môn (người đó không thể ở hai nơi);
  - một (lớp, môn) thuộc hai nhóm mâu thuẫn (một nhóm ghép lớp, một nhóm chia nhóm).
- Hai dòng nhóm chồng nhau (3/1+3/2 và 3/2+3/3) thì gộp thành một nhóm.

### 3.3 Thay đổi mô hình
**`allocation.build_problem`**
- `Problem.links`: các nhóm, mỗi nhóm là các (lớp, môn) và cờ cùng người dạy.
- `Course.link`: số nhóm. Lớp đầu của nhóm ghép lớp là lớp chính, các lớp còn lại theo nó.
- **Ghép lớp:**
  - môn được ghép không vào phần GVCN (`split_homeroom` để dành, như môn của quản lý);
  - người được dạy là người được dạy môn đó ở mọi lớp trong nhóm;
  - GVCN có chức vụ thêm Bộ Môn vẫn dạy được.

**`phan_cong`** (dự toán, phân công)
- **Ghép lớp:** cả nhóm là một nhu cầu. Phân công cho tiết chính rồi chép sang các lớp theo, nên định mức và tiết bù tính
  một lần. Chế độ tuyển thêm: người mới dạy cả nhóm.
- **Chia nhóm:** mỗi môn phân công riêng như nay, thêm một điều: không giao hai môn cùng nhóm của một lớp cho cùng một
  người (người đó không thể dạy hai nửa lớp cùng giờ). Kiểm tra sau phân công, sửa bằng tìm kiếm cục bộ (`_Local`).

**`solver.build_timetable`**
- Các (lớp, môn) cùng nhóm có tiết ở đúng các giờ như nhau: miền giờ là giao các miền, ràng buộc bằng nhau theo từng giờ.
- **"Mỗi lớp mỗi giờ một tiết":** các môn cùng nhóm trong một lớp tính một. Lớp "đủ tiết" thì tổng tiết trừ phần trùng
  bằng số giờ học.
- **Lịch GV:** tiết của lớp theo trong nhóm ghép lớp không chiếm thêm giờ của người dạy. Không trùng giờ, buổi nghỉ, cơ sở,
  tải ngày, tiết trống đều tính một lần.
- **Luật học sinh** (nhóm môn mỗi buổi, liền tiết, cặp 2 tiết, TC sau tiết chính) vẫn tính theo từng (lớp, môn): không đổi.
- **Luật tự ghép:**
  - đếm theo giáo viên thì tiết ghép lớp tính một lần;
  - đếm theo lớp thì mỗi môn trong nhóm chia nhóm là một tiết riêng: luật theo một môn (vd Tin học tối đa 2 tiết mỗi
    ngày) đếm đúng; luật đếm mọi môn của lớp thì giờ chia nhóm tính hai tiết.

**`lns`**
- Vùng xếp lại có một lớp trong nhóm ghép lớp thì gồm cả các lớp kia.
- Phần chấm điểm (`qa`) tính tải GV theo số giờ dạy, không theo số dòng tiết.

**`checker`** (kiểm tra độc lập)
- Các (lớp, môn) cùng nhóm có tiết ở cùng các giờ.
- Ghép lớp: cùng một người dạy ở mỗi giờ.
- Lớp có hai tiết cùng giờ chỉ đúng khi hai tiết đó cùng nhóm.
- GV dạy hai lớp cùng giờ chỉ đúng khi cùng nhóm ghép lớp.
- Định mức đếm theo số giờ dạy.

**Tải GV** (`Solution.teacher_load`, thống kê, `checker`): đếm số giờ khác nhau GV có dạy. File không có nhóm cho đúng số
cũ.

### 3.4 File ra và TKB đã xếp
- **TKB lớp:**
  - ô chia nhóm ghi hai môn, vd "Tin học / Tiếng Anh" và dòng dưới "TH1 / TA1";
  - ô ghép lớp ghi như thường; có thể thêm "(ghép 3/2)" (xem mục 5).
- **TKB giáo viên:** ô ghép lớp ghi "3/1, 3/2 Thể dục".
- **Thống kê:** số tiết từng môn của GV đếm theo giờ dạy.
- **Sheet `TKB đã xếp`:**
  - ô chia nhóm ghi từng cặp "môn / Mã GV" nối tiếp, vd "Tin học\nTH1\nTiếng Anh\nTA1"; dấu (bù), (khóa) ghi sau Mã GV
    như nay;
  - `staff.parse_saved_grid` đọc ô có hơn hai dòng thành nhiều tiết; ô hai dòng đọc như cũ;
  - ô ghép lớp ghi bình thường ở từng lớp.
- **Mã kết quả:** vẫn băm mọi dòng tiết (lớp, ngày, tiết, môn, GV). File không có nhóm thì các dòng như cũ, mã như cũ.

### 3.5 Giao diện
- **Bước Luật:** hai kiểu luật mới tự hiện trong hộp thoại soạn luật (danh sách kiểu luật lấy từ `luat_rieng.KINDS`).
- **Bước Thời khóa biểu:** đổi chỗ hai ô mà một ô thuộc nhóm thì lớp đó và các lớp cùng nhóm phải đổi cùng lúc. Bản đầu:
  - chặn đổi tay ô thuộc nhóm ghép lớp, ghi lý do và gợi ý "Xếp lại phần còn lại";
  - ô chia nhóm cùng lớp đổi được, vì cả ô (hai môn) đi cùng nhau.
- **Ô Người dạy:** với ô ghép lớp thì đổi cho cả nhóm.

### 3.6 Test
- **Chia nhóm:**
  - Tin học và Tiếng Anh khối 4 cùng giờ: mọi giờ có Tin của 4/1 cũng có Tiếng Anh của 4/1, hai người khác nhau;
  - lớp vẫn đủ tiết; GV Tin và GV Tiếng Anh không trùng giờ.
- **Dạy kèm:** môn "Trợ giảng Tiếng Anh", chức vụ Trợ Giảng: trợ giảng có đúng số tiết, ở đúng giờ Tiếng Anh.
- **Ghép lớp:**
  - Thể dục 3/1 + 3/2: cùng giờ, cùng người;
  - người dạy tính 2 tiết/tuần chứ không phải 4;
  - dự toán cần ít hơn 2 tiết;
  - cả hai chế độ (bù giờ, tuyển thêm) đều đạt.
- **Kiểm tra độc lập:** sửa tay một lớp lệch giờ khỏi nhóm thì bị báo.
- **Báo lỗi:** khác số tiết; không ai dạy được; ghép môn chỉ GVCN dạy.
- **Đọc lại:** sheet `TKB đã xếp` có ô hai môn đọc lại đúng, nạp lại giữ TKB.
- **Không có dòng luật:** mã tham chiếu không đổi.

### 3.7 Rủi ro, chưa làm
- **Rủi ro lớn nhất:** sót một chỗ đếm "một dòng tiết = một tiết của GV" (thống kê, dự toán, LNS, luật tự ghép). Cách
  giảm rủi ro:
  - tách 4B-1 (chia nhóm, không đổi phân công) trước 4B-2;
  - một hàm đếm chung "giờ dạy của GV" cho mọi nơi;
  - test đối chiếu `checker` với mô hình.
- **Chỉ ghép một phần số tiết** (vd 1 trong 2 tiết Thể dục học chung): chưa làm. Bản đầu ghép trọn môn.
- **Lớp ghép nhiều khối ở vùng khó khăn** (một GV dạy hai khối trong một phòng cả ngày): ghi được từng cặp môn cùng số
  tiết bằng "Ghép lớp" khác môn. Ghi cả ngày thì cần cách ghi riêng; chưa làm.
- **Tiết ghép lớp tính cho GV một tiết:** nếu trường tính khác (vd 1,5 tiết), cần thêm một cột; xem mục 5.

## 4. Giai đoạn 4C: đa ngôn ngữ (đề xuất hoãn)
- **Phạm vi tối thiểu có ích:**
  1. **Giao diện tiếng Anh:** gom chữ của `app.js`, `index.html` vào `static/lang/vi.js`, `en.js`; chọn ngôn ngữ ở góc
     trang.
  2. **Đọc file có tiêu đề tiếng Anh:** mỗi `Col` (`tkb/rules.py`), mỗi cột NHÂN SỰ, mỗi tên sheet có thêm tên tiếng Anh.
     Đọc nhận cả hai; ghi theo ngôn ngữ chọn khi chạy.
  3. **File ra tiếng Anh:** tiêu đề TKB, thống kê, hướng dẫn.
  4. **Báo lỗi, câu đọc lại luật bằng tiếng Anh:** khoảng 1.600 chuỗi Python, phần lớn việc. Có thể bỏ, giữ tiếng Việt.
- **Mã kết quả không đổi:** tên trong file chỉ là nhãn, bên trong vẫn dùng khóa như nay.
- **Vì sao đề xuất hoãn:**
  - trường hiện tại dùng tiếng Việt;
  - phần 4 là nhiều việc nhất mà không đổi gì về xếp lịch;
  - hai phần lõi (luật và khung giờ) đã không gắn với nước nào sau giai đoạn 1–3.

## 5. Cần anh/chị quyết

**Đã duyệt ngày 10/10/2026: theo mọi đề xuất dưới đây.**

1. **Thứ tự và phạm vi:** 4A → 4B-1 → 4B-2, hoãn 4C? (đề xuất: có)
2. **Ghép lớp tính cho người dạy bao nhiêu tiết:** một tiết mỗi giờ (đề xuất), hay số lớp × tiết?
3. **Ghép lớp ở phòng:** cả nhóm chiếm một chỗ trong phòng (đề xuất), hay mỗi lớp một chỗ?
4. **Dạy kèm:** ghi bằng môn riêng như "Trợ giảng Tiếng Anh" (đề xuất, không thêm cơ chế), hay một cột "Người dạy kèm" ở
   CHƯƠNG TRÌNH HỌC?
5. **Ô ghép lớp trong TKB lớp:** ghi thêm "(ghép 3/2)" hay để như ô thường?
6. **TKB phòng:** file riêng `TKB_phong.xlsx` (đề xuất), hay thêm sheet vào file TKB giáo viên?

## 6. Kế hoạch PR
Mỗi phần một PR nháp, xếp chồng trên #29, theo quy trình như các giai đoạn trước:
- đủ test;
- `python main.py` cho đúng mã cũ;
- cập nhật README, đặc tả (§0 thêm dòng), CLAUDE.md, CODE_MAP, file mẫu.

| PR | Nội dung | Phụ thuộc |
|---|---|---|
| 4A | Sheet PHÒNG, ràng buộc phòng, xếp phòng, TKB phòng, giao diện bước Lớp | #29 |
| 4B-1 | Nhóm học cùng giờ (phần chung) + chia nhóm, dạy kèm; ô nhiều môn ở TKB đã xếp | 4A (chỉ để tránh xung đột code) |
| 4B-2 | Ghép lớp: phân công một lần, tải GV theo giờ dạy, LNS theo nhóm, TKB giáo viên | 4B-1 |
| 4C | (nếu duyệt) giao diện và tiêu đề tiếng Anh | sau cùng |
