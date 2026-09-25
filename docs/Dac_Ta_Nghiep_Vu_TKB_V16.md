# ĐẶC TẢ NGHIỆP VỤ HỆ THỐNG XẾP THỜI KHÓA BIỂU TỰ ĐỘNG (V16)

> **V16 thay thế V15.** Tài liệu này mô tả đúng hành vi của chương trình trong repo (thư mục `tkb/`, file chạy `main.py`).
>
> - Dữ liệu của trường (môn, số tiết, giáo viên, chức vụ, lớp, định mức, style) chỉ lấy từ file vào (mục 2.4).
> - Các luật nghiệp vụ mà file vào không có nằm ở `tkb/config.py`. Các tuỳ chọn chạy nằm ở `main.py` (mục 12.1).
> - Nếu chương trình và đặc tả khác nhau, coi đó là lỗi và sửa một trong hai cho khớp.
>
> Quy ước trong tài liệu:
> - **[Cứng]**: luật bắt buộc. Vi phạm thì TKB không hợp lệ, chương trình kiểm tra lại sau khi giải.
> - **[Mềm]**: mục tiêu tối ưu. Chương trình cố gắng đạt, không bắt buộc.

---

## 0. Lịch sử thay đổi V16 so với V15

| # | Nội dung | V15 | V16 |
|---|---|---|---|
| 1 | Số tiết của giáo viên | Phải dạy **đúng bằng** Số tiết | Số tiết là **mức tối đa** mỗi tuần (≤) |
| 2 | Khi thiếu người | Auto Scale chọn người bổ sung từ danh sách năng lực | Hai chế độ (mục 7). **Tuyển thêm:** thêm người `chưa có` theo định mức đầy đủ của chức vụ. **Bù giờ:** GVCN/bộ môn dạy vượt định mức |
| 3 | Ghi chỗ thiếu | Ghi "thiếu" vào ô TKB | Không bao giờ ghi "thiếu". Người bổ sung có tên `chưa có` và chức vụ `<chức vụ> n+1` |
| 4 | Quyền dạy | Theo nhóm môn | Suy ra từ **tên chức vụ** (mục 4) |
| 5 | Quản lý | – | Chỉ dạy Kỹ năng sống khối 4, đúng bằng Số tiết |
| 6 | HĐTN tiết thứ ba | FLEX_SLOT bất kỳ, ưu tiên cuối buổi | Chỉ Thứ 3–Thứ 5, ưu tiên cuối buổi |
| 7 | Tiết 1 buổi sáng | – | **[Cứng]** Luôn do GVCN của lớp dạy |
| 8 | Môn nặng ở tiết 7 | [Cứng] cấm | **[Mềm]** hạn chế |
| 9 | Tiết nặng liên tiếp | [Cứng] giới hạn | **Bỏ** |
| 10 | Tối đa 2 tiết TV, 2 tiết Toán mỗi buổi | [Cứng] | **Giữ nguyên** [Cứng]. Tiết tăng cường được đếm riêng |
| 11 | Thai sản | Chữ `ts` sau chức vụ | Cột **Chế Độ** (`Có`/trống); vẫn đọc được chữ `ts`. Người thai sản **được dạy bù** như mọi người (cùng mức tối đa) |
| 12 | Tải ngày | Buffer/overload động | [Mềm] mục tiêu tải ngày theo tỷ lệ số tiết của ngày |
| 13 | Tái lập | – | Cùng dữ liệu, cùng phiên bản OR-Tools và cùng số luồng thì luôn ra cùng một TKB |
| 14 | Nội dung ô TKB | Chức vụ (môn) | Môn, xuống dòng **tên giáo viên**. Tên trống hoặc người cần tuyển thì ghi **Mã GV** (`Bộ Môn 6`); tên trùng thì kèm Mã GV |
| 15 | File vào | Hai file: nhân sự (Tên, Chức vụ kèm số thứ tự, Số tiết) và chương trình học | **Một file duy nhất (mẫu V8):** sheet NHÂN SỰ (Họ và Tên, Chức Vụ không số thứ tự, Lớp khối/số thứ tự, Số Tiết/Tuần, Chế Độ) và sheet CHƯƠNG TRÌNH HỌC (bắt buộc) |
| 16 | Dữ liệu trong code | Chương trình học, danh sách môn, danh sách chức vụ chuyên biệt, định mức 23 nằm trong code | **Không còn trong code.** Những gì suy ra được từ file vào thì lấy từ file vào (mục 2.4) |
| 17 | Định dạng file ra | Cố định trong code | **Chép style của file vào** (phông, cỡ chữ, viền, căn lề, chiều cao dòng 25), được thêm cột (mục 11) |
| 18 | Tuỳ chọn chạy (`main.py`) | Thời gian cố định | `THU_MUC_OUT` để trống thì ghi vào thư mục dự án; `THOI_GIAN_TOI_DA` để trống thì **không giới hạn** (Ctrl+C dừng sớm). Mặc định: bù giờ, áp dụng luật học sinh, 240 giây, tái lập (mục 12.1) |

---

## 1. Phạm vi và thuật ngữ

**Phạm vi.** Xếp TKB **tuần** cho một trường tiểu học. Đầu vào là một file Excel gồm danh sách nhân sự và chương trình học. Đầu ra gồm:
- TKB từng lớp.
- Danh sách nhân sự đã cập nhật.
- Bảng thống kê: thiếu người, dạy bù, tải giáo viên.

| Thuật ngữ | Nghĩa |
|---|---|
| GVCN | Giáo viên chủ nhiệm, chức vụ `Chủ Nhiệm`, Mã GV `Chủ Nhiệm k/n` (lớp k/n) |
| Bộ môn (GVBM) | Chức vụ `Bộ Môn`, Mã GV `Bộ Môn n`, dạy được nhiều môn (mục 4) |
| GV chuyên biệt | Chức vụ **trùng tên một môn** trong sheet CHƯƠNG TRÌNH HỌC (ví dụ `Tiếng Anh`, `Thể Dục`, `Tin Học`); chỉ dạy đúng môn đó |
| Mã GV | Chức vụ kèm số thứ tự hoặc lớp, ví dụ `Chủ Nhiệm 1/1`, `Tiếng Anh 2`, `Bộ Môn 6`. Dùng để nhận ra giáo viên khi cột tên để trống |
| Quản lý | Chức vụ `Quản Lý`, Mã GV `Quản Lý n` |
| Thai sản | Giáo viên đang hưởng chế độ thai sản (cột Chế Độ = `Có`). Số tiết ghi mức đã giảm. Được dạy bù như mọi người |
| Số tiết (định mức) | Số tiết **tối đa** giáo viên dạy mỗi tuần |
| Tiết bù | Tiết dạy **vượt** định mức, chỉ có ở chế độ bù giờ |
| Người bổ sung | Người cần tuyển, tên `chưa có`, chức vụ `<chức vụ> n+1, n+2…` |
| Lớp–môn | Phần tiết của một môn ở một lớp giao cho một nhóm giáo viên được phép dạy |
| Slot | Một tiết cụ thể trong tuần: (ngày, tiết) |

---

## 2. Dữ liệu đầu vào

### 2.1. File vào (một file duy nhất)

Đầu vào là **một file Excel duy nhất** (`FILE_VAO` trong `main.py`, mẫu V8, ví dụ `data/Input_TKB_V8.xlsx`) gồm:

| Sheet | Bắt buộc | Nội dung |
|---|---|---|
| `NHÂN SỰ` | Có | Danh sách nhân sự (mục 2.1.1). Nếu không có sheet tên này thì đọc sheet đầu tiên |
| `CHƯƠNG TRÌNH HỌC` | Có | Chương trình học (mục 2.3). Thiếu sheet này thì báo lỗi (trừ khi chỉ định `--program`) |

Tên sheet và tên cột không phân biệt hoa thường. Dòng tiêu đề nằm trong 20 dòng đầu.

#### 2.1.1. Sheet NHÂN SỰ

| Cột | Bắt buộc | Quy tắc |
|---|---|---|
| Họ và Tên | Có (cột) | Họ tên, tự do. **Có thể để trống** (bảo mật): TKB ghi Mã GV thay tên |
| Chức Vụ | Có | `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý`, hoặc **đúng tên một môn** trong sheet CHƯƠNG TRÌNH HỌC (GV chuyên biệt). **Không ghi số thứ tự**. So khớp không phân biệt hoa thường, dấu câu, khoảng trắng thừa |
| Lớp | Với Chủ Nhiệm | Dạng **khối/số thứ tự** (`1/1`). Chỉ Chủ Nhiệm được ghi Lớp |
| Số Tiết/Tuần | Có | Số nguyên ≥ 0. Người thai sản ghi mức đã giảm |
| Chế Độ | Không | `Có` (hoặc `Thai sản`) nếu đang hưởng chế độ thai sản; để trống nếu không |
| STT, cột khác | Không | Không dùng |

- **Tự đánh số thứ tự (Mã GV):** mỗi chức vụ (trừ Chủ Nhiệm) được đánh số 1, 2, 3… theo thứ tự dòng trong file, ví dụ Bộ Môn thứ hai là `Bộ Môn 2`. Chủ Nhiệm được nhận diện theo Lớp (`Chủ Nhiệm 1/1`).
- **File cũ vẫn đọc được** (một sheet nhân sự; chương trình học lấy từ `--program`):
  - V7: `Họ và Tên | Chức Vụ | Lớp | Chế độ | Số Tiết/Tuần`.
  - V6: `Tên | Chức vụ | Số tiết | Thai sản`, chức vụ ghi kèm số (`bộ môn 5`, `chủ nhiệm 1/1`).
  - V5: 3 cột, thai sản ghi bằng chữ `ts` sau chức vụ (`bộ môn 5 ts`).

**Chương trình từ chối file và liệt kê tất cả lỗi một lần, kèm số dòng, khi:**
- Chức vụ không phải Chủ Nhiệm/Bộ Môn/Quản Lý và không trùng tên môn nào trong chương trình học, hoặc sai dạng (mẫu cũ).
- Chủ Nhiệm thiếu Lớp, Lớp sai dạng khối/số thứ tự, hoặc chức vụ khác lại ghi Lớp.
- Lớp bị Excel đổi thành ngày tháng (khi gõ tay `1/1` vào ô không định dạng chữ).
- Số tiết trống, không phải số, âm hoặc không nguyên.
- Cột Chế Độ ghi giá trị khác `Có`/`Thai sản`/`Không`/trống.
- Một lớp có hai Chủ Nhiệm, hoặc trùng chức vụ kèm số (mẫu cũ).
- Không có Chủ Nhiệm nào.

Chương trình **cảnh báo** (vẫn chạy) khi dãy lớp của một khối bị hụt, ví dụ có 1/3, 1/5 mà không có 1/4.

**File mẫu V8** (tạo bằng `python -m tkb.template`), style giống file của nhà trường (Times New Roman 14, tiêu đề in đậm không tô nền, viền mảnh, căn giữa, dòng cao 25):
- Sheet NHÂN SỰ: `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Chế Độ`. Chức Vụ có danh sách gợi ý (Chủ Nhiệm, Bộ Môn, các chức vụ chuyên biệt của file cũ, Quản Lý; vẫn gõ được tên môn khác). Lớp định dạng chữ và phải có dạng khối/số. Số Tiết/Tuần chỉ nhận số nguyên 0–40. Chế Độ chọn `Có`. Tô đỏ Lớp trùng, Chủ Nhiệm thiếu Lớp, chức vụ khác ghi Lớp.
- Sheet CHƯƠNG TRÌNH HỌC: `Môn học | Khối 1 …`. File mẫu trống không có môn nào; chuyển từ file cũ thì chép chương trình của file cũ.
- Chuyển file cũ sang file mẫu: `python -m tkb.template <mới.xlsx> --tu <cũ.xlsx> [--program <chương trình.xlsx>]`.

### 2.2. Danh sách lớp

Lấy từ cột Lớp của các dòng Chủ Nhiệm, vì mỗi lớp luôn có đúng một GVCN. Lớp được sắp theo khối, rồi theo số thứ tự.

### 2.3. Chương trình học

Lấy từ sheet `CHƯƠNG TRÌNH HỌC` của file vào (**bắt buộc**; code không chứa chương trình học nào). Dòng lệnh có thể chỉ định file chương trình riêng bằng `--program`.

Ví dụ (dữ liệu mẫu `data/Input_TKB_V8.xlsx`):

| Môn | Khối 1 | Khối 2 | Khối 3 | Khối 4 | Khối 5 |
|---|---:|---:|---:|---:|---:|
| Tiếng Việt | 14 | 10 | 7 | 7 | 7 |
| Toán | 5 | 5 | 5 | 5 | 5 |
| Hoạt động trải nghiệm (HĐTN) | 3 | 3 | 3 | 3 | 3 |
| Tiếng Anh | 2 | 2 | 4 | 4 | 4 |
| Tự nhiên xã hội (TNXH) | 2 | 2 | 2 | 0 | 0 |
| Khoa học | 0 | 0 | 0 | 2 | 2 |
| Lịch sử - Địa lý | 0 | 0 | 0 | 2 | 2 |
| Thể dục | 2 | 2 | 2 | 2 | 2 |
| Âm nhạc | 1 | 1 | 1 | 1 | 1 |
| Mỹ thuật | 1 | 1 | 1 | 1 | 1 |
| Đạo đức | 1 | 1 | 1 | 1 | 1 |
| Tin học | 0 | 0 | 1 | 1 | 1 |
| Công nghệ | 0 | 0 | 1 | 1 | 1 |
| Toán tăng cường | 0 | 2 | 2 | 1 | 1 |
| Tiếng Việt tăng cường | 0 | 2 | 1 | 0 | 0 |
| Kỹ năng sống | 1 | 1 | 1 | 1 | 1 |
| **Tổng** | **32** | **32** | **32** | **32** | **32** |

**Sheet chương trình học:**
- Có cột `Môn học` và các cột `Khối k`; cột STT (nếu có) không dùng. Ô trống được tính là 0. Dòng `Tổng` được bỏ qua.
- Số tiết phải là số nguyên ≥ 0.
- **Danh sách môn và tên môn lấy nguyên từ file.** Môn mới (ví dụ `Múa`) chỉ cần thêm dòng; môn đó được xếp bình thường, không có luật riêng. TKB và thống kê in đúng tên môn trong file (riêng HĐTN, TNXH, TV tăng cường được viết tắt trong ô TKB).
- Môn nào trùng tên một môn có luật trong `tkb/config.py` (mục 2.4) thì nhận luật đó. So khớp **không phân biệt hoa thường, dấu câu, khoảng trắng thừa và chữ "và"**: `Lịch Sử và Địa Lý` khớp `Lịch sử - Địa lý`, `Tự Nhiên và Xã Hội` khớp `Tự nhiên xã hội`.
- **Cảnh báo** khi luật trong config nhắc một môn mà file không có (thường do gõ khác tên).
- Một môn không được lặp lại (kể cả viết khác nhau nhưng cùng khóa so khớp).

**Kiểm tra tổng số tiết của mỗi khối:**
- Lớn hơn 32 → lỗi.
- Nhỏ hơn 32 → cảnh báo: lớp sẽ có tiết trống.

### 2.4. Cái gì nằm trong file vào, cái gì nằm trong code

**Nguyên tắc:** những gì suy ra được từ file vào thì không ghi trong code.

| Lấy từ file vào | Nằm trong `tkb/config.py` (file vào không có) |
|---|---|
| Danh sách môn, tên môn, số tiết từng khối | Khung giờ (mục 3) |
| Giáo viên, chức vụ, lớp chủ nhiệm, định mức, thai sản | HĐTN: 2 slot cố định, ngày của tiết thứ ba (mục 5.6) |
| Danh sách lớp (từ các dòng Chủ Nhiệm) | Tiết 1 do GVCN dạy (mục 5.5) |
| GV chuyên biệt: chức vụ trùng tên môn | Môn ưu tiên, thứ tự cắt / nhận thêm của GVCN (mục 5) |
| Định mức người cần tuyển: Số tiết lớn nhất của GV cùng chức vụ | Bộ Môn không dạy Tiếng Anh, Tin học, HĐTN; Quản Lý dạy KNS khối 4 (mục 4) |
| Style các file ra: phông, cỡ chữ, viền, căn lề, chiều cao dòng | Luật bù giờ, môn nặng, tối đa 2 tiết TV/Toán mỗi buổi, trọng số (mục 6–8) |

---

## 3. Khung thời gian

| Ngày | Buổi sáng | Buổi chiều |
|---|---|---|
| Thứ 2 – Thứ 5 | Tiết 1–4 | Tiết 5–7 (hiển thị Chiều 1–3) |
| Thứ 6 | Tiết 1–4 | Nghỉ |

- Mỗi tuần có **32 slot**. Mỗi lớp học đủ 32 tiết/tuần.
- Trong chương trình, tiết được đánh số 1–7. Tiết 7 là tiết cuối buổi chiều.
- **[Cứng]** Mỗi lớp, mỗi slot có đúng 1 tiết (khi tổng chương trình của khối bằng 32).
- **[Cứng]** Mỗi giáo viên dạy tối đa 1 lớp tại một slot.

---

## 4. Quyền dạy theo chức vụ

| Chức vụ | Được dạy | Không được dạy |
|---|---|---|
| Chủ nhiệm | Chỉ **lớp mình**: phần được phân (mục 5), cộng tiết bù (mục 7.2) | Lớp khác |
| Bộ môn | Mọi môn | Tiếng Anh, Tin học, HĐTN |
| GV chuyên biệt (chức vụ trùng tên một môn: Tiếng Anh, Tin Học, Thể Dục…) | Chỉ môn trùng tên chức vụ | Môn khác |
| Quản lý | Chỉ **Kỹ năng sống khối 4** | Môn/khối khác |

- **[Cứng]** HĐTN chỉ do GVCN của lớp dạy.
- Môn bộ môn không được dạy (Tiếng Anh, Tin học) mà trường chưa có GV chuyên biệt: chương trình tự thêm chức vụ trùng tên môn để tuyển (ví dụ `Tin Học 1`).
- **[Cứng]** Quản lý dạy **đúng** bằng Số tiết của mình. Nếu số tiết phù hợp ít hơn thì dạy hết số đó và có cảnh báo. Chương trình tự chọn lớp; có thể cố định lớp trong `MANAGER_RULES`. Mỗi lớp chỉ có 1 tiết KNS, nên quản lý 4 tiết sẽ dạy ở 4 lớp khối 4.
- **[Mềm]** Thể dục, Âm nhạc, Mỹ thuật ưu tiên do GV chuyên biệt dạy. Bộ môn chỉ dạy thay phần vượt năng lực của GV chuyên biệt.
- **[Mềm]** Hạn chế chia một lớp–môn cho nhiều giáo viên.

---

## 5. Phân công GVCN

### 5.1. Môn ưu tiên của GVCN

GVCN nhận trước các môn của lớp mình theo thứ tự: **Tiếng Việt, Toán, HĐTN, Khoa học, Lịch sử - Địa lý, Đạo đức** (`HOMEROOM_PRIORITY`).

### 5.2. GVCN vượt định mức: cắt bớt

- Cắt theo thứ tự **Tiếng Việt → Toán → Khoa học → Lịch sử - Địa lý** (`HOMEROOM_CUT_ORDER`).
- Chỉ cắt môn có **hơn 1 tiết** trong chương trình. GVCN luôn giữ lại **ít nhất 1 tiết** của môn bị cắt.
- Không bao giờ cắt HĐTN. Nếu định mức nhỏ hơn số tiết HĐTN thì báo lỗi.
- Cắt hết mức mà vẫn vượt thì báo lỗi.
- Phần bị cắt chuyển cho bộ môn, hoặc cho GVCN bù ở chế độ bù giờ.

### 5.3. GVCN thiếu định mức: nhận thêm

- Nhận thêm theo thứ tự **TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ** (`HOMEROOM_FILL_ORDER`).
- Không bao giờ nhận môn có GV chuyên biệt (chức vụ trùng tên môn, ví dụ Tiếng Anh, Tin học, Thể dục, Âm nhạc, Mỹ thuật).
- Nếu trường có quản lý thì không nhận môn dành cho quản lý (KNS khối 4).

### 5.4. Kết quả với dữ liệu mẫu

| Lớp (định mức GVCN) | GVCN dạy | Phần chuyển đi |
|---|---|---|
| Khối 1 (19) | TV 10, Toán 5, HĐTN 3, Đạo đức 1 | TV 4 tiết/lớp |
| Khối 2 (19) | TV 10, Toán 5, HĐTN 3, Đạo đức 1 | – |
| Khối 3 (19) | TV 7, Toán 5, HĐTN 3, Đạo đức 1, TV tăng cường 1, Toán tăng cường 2 | – |
| Khối 4, 5/1–5/4 (19) | TV 6, Toán 5, HĐTN 3, Khoa học 2, LS-ĐL 2, Đạo đức 1 | TV 1 tiết/lớp |
| 5/5 thai sản (16) | TV 3, Toán 5, HĐTN 3, Khoa học 2, LS-ĐL 2, Đạo đức 1 | TV 4 tiết (ở chế độ bù giờ, GVCN này có thể bù lại) |

### 5.5. Tiết 1 buổi sáng

- **[Cứng]** Tiết 1 buổi sáng của **mọi ngày** (Thứ 2–Thứ 6) luôn do GVCN của lớp dạy (`HOMEROOM_PERIODS = {1}`). Giáo viên khác không được xếp vào tiết này.
- GVCN phải có ít nhất 5 tiết/tuần, nếu không chương trình báo lỗi.
- Hệ quả: giáo viên không chủ nhiệm chỉ còn **26 slot/tuần** để dạy (32 − 5 tiết 1 − Thứ 6 tiết 4 của HĐTN).

### 5.6. HĐTN

- **[Cứng]** Hai tiết cố định: **Thứ 2 tiết 1** và **Thứ 6 tiết 4** (`HDTN_FIXED_SLOTS`).
- **[Cứng]** Tiết thứ ba xếp vào **Thứ 3 – Thứ 5** (`HDTN_FLEX_DAYS`).
- **[Mềm]** Tiết thứ ba ưu tiên tiết cuối buổi: mỗi tiết cách cuối buổi bị phạt 200.
- Không môn nào khác của lớp được xếp vào slot đã cố định cho HĐTN.

---

## 6. Luật bảo vệ học sinh

| Luật | Loại | Nội dung |
|---|---|---|
| Giới hạn TV/Toán | **[Cứng]** | Mỗi buổi tối đa **2 tiết Tiếng Việt** và **2 tiết Toán**. Tiết tăng cường được đếm riêng. Tắt được bằng `LUAT_HOC_SINH = False` |
| Môn nặng ở tiết 7 | **[Mềm]** | Mỗi tiết môn nặng ở tiết 7 bị phạt 200 (`heavy_late`) |
| Tiết nặng liên tiếp | Bỏ | Không còn giới hạn |

**Môn nặng** (`HEAVY_SUBJECTS`): Toán, Toán tăng cường, Tiếng Việt, Tiếng Việt tăng cường, Tiếng Anh, Khoa học, Tin học.

Với dữ liệu mẫu, còn đúng **4 tiết Tiếng Anh ở tiết 7**, mỗi GV tiếng anh 1 tiết. Đây là mức tối thiểu:
- Mỗi GV tiếng anh dạy 23 tiết.
- Ngoài tiết 1, Thứ 6 tiết 4 và tiết 7, họ chỉ còn 22 slot.

---

## 7. Xử lý khi thiếu người

Chọn chế độ bằng `CHE_DO` trong `main.py` hoặc `--mode` khi chạy dòng lệnh.

### 7.1. Chế độ tuyển thêm (`tuyen_them`)

- Phần không ai dạy được giao cho **người bổ sung**:
  - Tên `chưa có`.
  - Mã GV `<chức vụ> n+1, n+2…` (ví dụ `Bộ Môn 6`), với n là số thứ tự lớn nhất hiện có của chức vụ đó.
- **Định mức tuyển** của người bổ sung = Số tiết lớn nhất của các giáo viên cùng chức vụ trong file vào, không tính người thai sản. Nếu chức vụ đó chưa có ai thì lấy Số tiết lớn nhất của các giáo viên không chủ nhiệm, không quản lý.
- Người bổ sung là một người thật sẽ tuyển: không dạy 2 lớp cùng lúc, và không dạy quá định mức tuyển.
- Thứ tự ưu tiên:
  1. Ít tiết giao cho người bổ sung nhất (dùng hết người hiện có trước).
  2. Ít người bổ sung nhất.
  3. Ưu tiên tuyển bộ môn hơn GV chuyên biệt.
- Tiết được dồn cho người bổ sung đầu trước. Người cuối có thể dạy chưa đủ định mức, ví dụ 23 + 23 + 6.
- Trong danh sách nhân sự, người bổ sung ghi **định mức tuyển đầy đủ** (ví dụ 23), kèm số tiết thực dạy.

### 7.2. Chế độ bù giờ (`bu_gio`)

- **Người được bù:** chỉ **GVCN** và **bộ môn**. Mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần (mặc định 2).
- Người hưởng thai sản **cũng được bù** như mọi người, cùng mức tối đa `SO_TIET_BU_TOI_DA`.
- **[Cứng]** GVCN chỉ bù ở **lớp mình**, và không bù môn của GV chuyên biệt.
- **Thứ tự môn GVCN bù:**
  1. Môn ưu tiên (lấy lại tiết đã bị cắt ở mục 5.2).
  2. TV tăng cường.
  3. Toán tăng cường.
  4. TNXH.
  5. Kỹ năng sống.
  6. Công nghệ.
- **Thứ tự ưu tiên khi quyết định:**
  1. Ít tiết không ai dạy nhất, ít người phải tuyển nhất.
  2. Ít tiết bù của **bộ môn** nhất: **GVCN bù trước**, bộ môn chỉ bù khi GVCN đã bù hết mức.
  3. Ít tiết bù của GVCN nhất. Không trả bù thừa khi còn người dạy trong định mức.
  4. **Chia đều:** mọi người bù +1 rồi mới có người bù +2.
  5. Đúng thứ tự môn ở trên.
  6. Hạn chế chia một lớp–môn cho nhiều người.
- Bù hết mức mà vẫn thiếu thì phần còn lại mới thêm người `chưa có` như mục 7.1.

---

## 8. Mục tiêu tối ưu

### 8.1. Bước phân công: tối ưu theo thứ tự

Chương trình giải hai lần:
- **Lần 1** tối ưu nhóm chính:
  - Tiết giao cho người bổ sung: ×1.000.000.
  - Người bổ sung: ×100.000, cộng thêm ×1.000 nếu là GV chuyên biệt.
  - Tiết bù của bộ môn: ×200.000.
  - Tiết bù của GVCN: ×100.000.
- **Lần 2** giữ nguyên kết quả lần 1 và tối ưu nhóm phụ:
  - Tiết bù thứ 2 của một người: ×50.000.
  - Thứ tự môn GVCN bù: ×3.000 × hạng môn.
  - Chia lớp–môn: ×5.000 cho mỗi người thêm.
  - Cân bằng phần định mức chưa dùng giữa người cùng chức vụ: ×50.
  - Bộ môn dạy thay môn chuyên biệt: ×1.
  - Dồn tiết cho người bổ sung đầu: ×1.

### 8.2. Bước xếp giờ: mục tiêu mềm

| Mục tiêu | Trọng số |
|---|---:|
| Tải ngày của giáo viên vượt mục tiêu. Mục tiêu ngày chia định mức theo tỷ lệ số slot của ngày | 100 / tiết vượt; thêm 300 nếu vượt quá mục tiêu + 1 |
| HĐTN tiết thứ ba cách cuối buổi | 200 / tiết cách |
| Môn nặng ở tiết 7 | 200 / tiết |
| Rải đều môn (trừ HĐTN): số tiết một môn trong ngày vượt ⌈số tiết/tuần ÷ 5⌉ | 20 / tiết vượt |
| Tiết trống giữa buổi của giáo viên không chủ nhiệm | 10 / tiết trống |

---

## 9. Quy trình giải

1. **Đọc và kiểm tra** đầu vào (mục 2).
2. **Phân GVCN** (mục 5) và tạo các lớp–môn còn lại, mỗi lớp–môn kèm danh sách giáo viên được dạy (mục 4).
3. **Bước 1 – Phân công** (chưa xếp giờ):
   - Tìm số tiết mỗi giáo viên dạy ở từng lớp–môn, theo thứ tự ưu tiên ở mục 8.1.
   - Mỗi giáo viên không được nhận quá số slot họ thực sự xếp được, ví dụ 26 slot với giáo viên không chủ nhiệm.
   - Kết quả thường được **chứng minh tối ưu**. Đây là cận dưới của số tiết thiếu và số tiết bù.
4. **Bước 2 – Xếp giờ** với phân công cố định từ bước 1, tối ưu mục tiêu mềm ở mục 8.2. Nếu xếp được thì kết quả đạt đúng cận dưới của bước 1.
5. **Dự phòng:** nếu bước 2 không xếp được, chương trình giải mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ), cho phép thêm 1 người bổ sung dự phòng mỗi chức vụ, rồi 3 người.
6. **Kiểm tra độc lập** (mục 10) và xuất file (mục 11).

**Thời gian và tái lập:**
- `THOI_GIAN_TOI_DA` (mặc định 240) là lượng tính toán dành cho bước xếp giờ, tính xấp xỉ bằng giây. Bước phân công dùng 1/8 lượng này (tối thiểu 10).
- **Không giới hạn** (`THOI_GIAN_TOI_DA` để trống hoặc 0, dòng lệnh `--time-limit 0`):
  - Bước phân công: nhóm chính (tiết thiếu, người tuyển, tiết bù) giải đến khi **chứng minh tối ưu** (vài giây). Nhóm phụ (chia đều, thứ tự môn…) gần như không bao giờ chứng minh được nên vẫn giới hạn (`Settings.unlimited_polish_time`, 30).
  - Bước xếp giờ: chạy đến khi chứng minh TKB tốt nhất. Với trường cỡ 29 lớp, việc này gần như không kết thúc.
  - Bấm **Ctrl+C** thì bộ giải dừng, giữ TKB tốt nhất đã tìm được, kiểm tra luật và ghi đủ các file ra như bình thường. Kết quả khi dừng bằng tay phụ thuộc thời điểm dừng nên không tái lập.
- **[Cứng] Tái lập:** khi `CHAY_TAI_LAP_DUOC = True` và có giới hạn thời gian, chạy lại bao nhiêu lần cũng ra **đúng một TKB**, ở **cả chế độ tuyển thêm lẫn bù giờ**, miễn là giữ nguyên:
  - file vào (và file chương trình học riêng nếu có);
  - `CHE_DO`, `SO_TIET_BU_TOI_DA`, `THOI_GIAN_TOI_DA`, `SO_LUONG`, `LUAT_HOC_SINH`;
  - phiên bản OR-Tools (ghim trong `requirements.txt`).
- Máy nhanh hay chậm, máy đang bận hay rảnh không ảnh hưởng kết quả, vì bộ giải dừng theo **lượng tính toán**, không theo giây thực.
- Đổi một trong các điều kiện trên thì TKB ra khác, nhưng vẫn đúng luật.
- `tests/test_reproducible.py` kiểm tra điều này ở cả hai chế độ: chạy trong hai tiến trình Python riêng, thứ tự băm khác nhau, và so sánh kết quả.

---

## 10. Kiểm tra độc lập (sau khi giải)

`tkb/checker.py` kiểm tra lại TKB mà không dựa vào mô hình giải:

1. Mỗi lớp, mỗi slot có đúng 1 tiết. Mỗi lớp đủ số tiết từng môn.
2. Không giáo viên nào dạy 2 lớp cùng lúc.
3. Không ai vượt định mức, cộng mức bù được phép. Quản lý dạy đúng số tiết.
4. Quyền dạy đúng mục 4.
5. Tiết 1 buổi sáng do đúng GVCN của lớp dạy.
6. GVCN dạy đủ phần được phân. Phần dạy thêm chỉ là tiết bù hợp lệ: đúng lớp mình, không phải môn chuyên biệt, không quá mức bù.
7. HĐTN đúng 2 slot cố định; tiết thứ ba nằm trong Thứ 3–Thứ 5.
8. Mỗi buổi tối đa 2 tiết TV và 2 tiết Toán (nếu bật luật học sinh).

Kết quả ghi vào sheet Thống kê (**ĐẠT** / **KHÔNG ĐẠT** kèm danh sách lỗi) và in ra màn hình.

---

## 11. Đầu ra

### 11.1. `TKB.xlsx`

**Sheet `Khối 1` … `Khối 5`**, bố cục theo `data/Output_Template_TKB_V5_Formatted.xlsx`:
- Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
  - Cột LỚP gộp 7 hàng (`LỚP 1/1`).
  - Cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 1–3).
  - Giữa hai lớp có 2 dòng trống.
- Mỗi ô ghi **môn** và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Chiều Thứ 6 ghi `Nghỉ`.
  - Tên để trống hoặc người cần tuyển: ghi **Mã GV**, ví dụ `Chủ Nhiệm 1/1`, `Bộ Môn 6`.
  - Hai giáo viên trùng tên thì kèm Mã GV, ví dụ `Lan (Bộ Môn 1)`.
  - Cột ngày tự nới theo dòng dài nhất, tối đa 30 (đơn vị cột Excel). Tên dài hơn thì xuống dòng và hàng tự cao thêm.
- Tên môn in như trong file vào; viết tắt: `HĐTN`, `TNXH`, `TV tăng cường`.
- Khi in: khổ ngang, co vừa chiều rộng 1 trang.

**Style của mọi file ra** (`TKB.xlsx`, `Thong_Ke.xlsx`, file vào cập nhật): chép từ sheet NHÂN SỰ của file vào, không cố định trong code:
- Ô tiêu đề (dòng tiêu đề, cột Chức Vụ): phông, cỡ chữ, in đậm, viền, căn lề, nền.
- Ô dữ liệu (dòng đầu tiên, cột Chức Vụ): phông, cỡ chữ, viền, căn lề.
- Chiều cao dòng: của dòng dữ liệu đầu tiên, làm tròn (24,95 → **25**); file vào không đặt thì 25.
- Bảng ghi tiêu đề cột ở dòng 1 như file vào. Riêng hàng tiết trong TKB cao đủ 2 dòng chữ (môn và giáo viên), theo cỡ chữ của file vào.

**Sheet `Danh sách nhân sự`:**
- Cột như sheet NHÂN SỰ của file vào: Họ và Tên, Chức Vụ, Lớp, Số Tiết/Tuần, Chế Độ. Thêm **Mã GV**, **Số Tiết Thực Dạy**, **Số Tiết Bù** (chế độ bù giờ) và Ghi Chú.
- Thứ tự: giáo viên theo thứ tự file gốc, sau đó đến người bổ sung.

**Sheet `Thống kê`:**
- **Thông tin chung:** chế độ, kết quả kiểm tra luật, trạng thái bộ giải, thời gian, số lớp, tổng tiết, tổng tiết thiếu, số người bổ sung, tổng tiết dạy bù, ghi chú và cảnh báo.
- **Chức vụ thiếu và số tiết thiếu:** người bổ sung và chi tiết lớp, môn.
- **Dạy bù** (chế độ bù giờ): ai bù, bao nhiêu tiết, GVCN bù môn gì.
- **Theo nhóm chức vụ:** số người, tổng định mức, đã dạy, dư, dạy bù, tiết thiếu, số người bổ sung.
- **Tải từng giáo viên:** định mức, thực dạy, dư, bù, số tiết từng ngày, số lớp dạy.
- **Lỗi kiểm tra** (nếu có).

### 11.2. File vào cập nhật `<tên file vào>_cap_nhat.xlsx`

- Là bản chép của file vào (đủ các sheet), sheet NHÂN SỰ có thêm các dòng người bổ sung `chưa có` ở cuối với **định mức tuyển đầy đủ** (Chức Vụ ghi không kèm số, ví dụ `Bộ Môn`; STT điền tiếp nếu có). Dòng mới **chép style của dòng trên**.
- Bên phải thêm các cột **Mã GV**, **Số Tiết Thực Dạy** và (chế độ bù giờ) **Số Tiết Bù**, cùng style với file. Chạy lại trên file này thì các cột được ghi đè, không thêm mới.
- Giữ nguyên danh sách thả xuống của file mẫu.
- Dùng làm đầu vào cho lần chạy sau được (các cột thêm được bỏ qua khi đọc). File gốc không bị sửa.

### 11.3. File thống kê giáo viên `Thong_Ke.xlsx`

Giáo viên được liệt kê theo thứ tự file nhân sự, rồi đến người cần tuyển. Người cần tuyển có tên **`tuyển thêm`**. Mọi bảng có tiêu đề cột ở dòng 1 (cố định khi cuộn), style theo file vào.

| Sheet | Cột | Ghi chú |
|---|---|---|
| **Thống kê giáo viên** | STT, Họ và Tên, Chức Vụ, Mã GV, Số tiết quy định, Số tiết bù, Số tiết thực dạy, Số tiết còn dư | Có dòng **Tổng**. Số tiết quy định của người cần tuyển là định mức tuyển đầy đủ (ví dụ 23). Số tiết bù chỉ khác 0 ở chế độ bù giờ |
| **Phân công** | STT, Họ và Tên, Mã GV, Lớp, Môn, Số tiết | Bảng phân công chuyên môn; mỗi dòng là một (giáo viên, lớp, môn) |
| **Theo ngày** | STT, Họ và Tên, Mã GV, Thứ 2 … Thứ 6, Tổng | Có dòng **Tổng** |
| **Theo chức vụ** | STT, Chức vụ, Số người, Số tiết quy định, Số tiết thực dạy, Số tiết bù, Số tiết còn dư, Số người tuyển thêm, Số tiết tuyển thêm | Có dòng **Tổng** |

### 11.4. Màn hình và mã thoát

- Màn hình in: các bước giải, người cần bổ sung, tiết dạy bù (tổng, theo GVCN/bộ môn, số người +2/+1), số tiết môn nặng ở tiết 7, lỗi kiểm tra.
- Mã thoát:
  - `0`: thành công (kể cả khi dừng sớm bằng Ctrl+C ở chế độ không giới hạn thời gian).
  - `1`: lỗi đầu vào, hoặc không xếp được.
  - `2`: đã xuất file nhưng kiểm tra luật **không đạt**.

---

## 12. Cấu hình

### 12.1. `main.py` (sửa rồi bấm Run)

| Hằng số | Ý nghĩa | Mặc định |
|---|---|---|
| `FILE_VAO` | **Địa chỉ file vào** (sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC), tương đối theo `main.py`. Để trống thì báo lỗi | `data/Input_TKB_V8.xlsx` |
| `THU_MUC_OUT` | Thư mục ra. **Để trống thì ghi vào thư mục dự án** (thư mục chứa `main.py`) | `out` |
| `CHE_DO` | `bu_gio` hoặc `tuyen_them` | `bu_gio` |
| `SO_TIET_BU_TOI_DA` | Mức bù tối đa mỗi người (chế độ bù giờ) | `2` |
| `LUAT_HOC_SINH` | Áp dụng luật tối đa 2 TV/2 Toán mỗi buổi | `True` |
| `THOI_GIAN_TOI_DA` | Lượng tính toán cho bước xếp giờ (≈ giây). **Để trống hoặc 0 thì không giới hạn**: chạy đến khi chứng minh tối ưu; Ctrl+C dừng sớm và vẫn ghi TKB tốt nhất đã tìm được | `240` |
| `CHAY_TAI_LAP_DUOC` | Cùng dữ liệu luôn ra cùng một kết quả | `True` |
| `FILE_TKB`, `FILE_THONG_KE` | Tên file TKB, file thống kê giáo viên | `TKB.xlsx`, `Thong_Ke.xlsx` |
| `SO_LUONG` | Số luồng tìm kiếm song song | `8` |

### 12.2. `tkb/config.py` (tham số nghiệp vụ)

| Tham số | Nội dung |
|---|---|
| `DAYS`, `DAY_SESSIONS` | Khung thời gian (mục 3) |
| `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS` | HĐTN (mục 5.6) |
| `GENERAL_FORBIDDEN_SUBJECTS`, `HOMEROOM_ONLY_SUBJECTS`, `MANAGER_RULES` | Quyền dạy (mục 4); GV chuyên biệt suy ra từ tên chức vụ, không cấu hình |
| `TV`, `TOAN`, `HDTN`…, `DISPLAY_NAMES` | Tên các môn có luật (so khớp với file vào, mục 2.3) và tên viết tắt |
| `HOMEROOM_PRIORITY`, `HOMEROOM_CUT_ORDER`, `HOMEROOM_FILL_ORDER` | Phân GVCN (mục 5) |
| `HOMEROOM_PERIODS` | Tiết luôn do GVCN dạy (mục 5.5) |
| `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, `SESSION_SUBJECT_LIMITS` | Luật học sinh (mục 6) |
| `SUPPLEMENT_NAME` | Tên người bổ sung (mục 7.1) |
| `ROLE_LABELS` | Cách ghi ba chức vụ Chủ Nhiệm, Bộ Môn, Quản Lý trong file ra |
| `OVERTIME_ROLES`, `OVERTIME_MAX` | Bù giờ (mục 7.2) |
| `Weights` | Trọng số mục tiêu (mục 8) |
| `Settings` | Tham số chạy mặc định (thời gian, tái lập, số luồng; `unlimited_polish_time` ở mục 9) |

---

## 13. Kết quả tham chiếu với dữ liệu mẫu

**Nhân sự** (`data/Input_TKB_V8.xlsx`, tên giả): 45 người, gồm:
- 29 GVCN, ứng với 29 lớp: khối 1–4 mỗi khối 6 lớp, khối 5 có 5 lớp.
- 5 bộ môn, 4 tiếng anh, 3 thể dục, 1 âm nhạc, 1 mỹ thuật, 1 tin học, 1 quản lý.
- 2 người thai sản: `Chủ Nhiệm 5/5` (16 tiết) và `Bộ Môn 5` (19 tiết).

**Nhu cầu so với năng lực** (ngoài phần GVCN):

| Nhóm | Nhu cầu | Năng lực | Ghi chú |
|---|---:|---:|---|
| Tiếng Anh | 92 | 92 | Đủ |
| Thể dục | 58 | 69 | Dư 11 |
| Tin học | 17 | 23 | Dư 6 |
| Âm nhạc / Mỹ thuật | 29 / 29 | 23 / 23 | Mỗi môn 6 tiết chuyển cho bộ môn |
| Bộ môn | 163 | 111 | **Thiếu 52**. Nhu cầu gồm TV 38, TNXH 36, KNS 25 (29 trừ 4 của quản lý), Toán TC 23, Công nghệ 17, TV TC 12, cộng 12 tiết Âm nhạc/Mỹ thuật |

**Kết quả** (chế độ tái lập, 240, 8 luồng; kiểm tra luật **ĐẠT**):

| Chế độ | Kết quả |
|---|---|
| Tuyển thêm | Thiếu **52** tiết. Tuyển `Bộ Môn 6`, `Bộ Môn 7`, `Bộ Môn 8` (định mức 23; thực dạy 23/23/6) |
| Bù giờ (+2) | **Không phải tuyển.** Bù 52 tiết, toàn bộ do GVCN, kể cả GVCN thai sản 5/5 (29 người: 23 người +2, 6 người +1). Bộ môn không phải bù |
| Cả hai | 145/145 ô tiết 1 buổi sáng là GVCN của lớp. Môn nặng ở tiết 7: 4 tiết (Tiếng Anh, mức tối thiểu) |

Cả hai chế độ đều đã **chứng minh tối ưu** ở bước phân công: số tiết thiếu, số người tuyển và số tiết bù là nhỏ nhất.

---

## 14. Giả định và hạn chế đã biết

1. **Tiết 1 buổi sáng thuộc GVCN** làm giáo viên không chủ nhiệm chỉ còn 26 slot/tuần. Giáo viên có định mức trên 26 sẽ bị phát hiện ngay ở bước phân công và cần người bổ sung hoặc bù.
2. **Thai sản** không có ngày bắt đầu/kết thúc. Khi chế độ thay đổi, sửa cột Chế Độ và Số Tiết/Tuần rồi chạy lại.
3. **Người được bù +1 thay vì +2**, lớp nào quản lý dạy KNS, và cách chia các tiết cùng chi phí là do chương trình chọn. Các phương án này tương đương nhau theo mục tiêu. Đổi dữ liệu hoặc `SO_LUONG` có thể làm đổi lựa chọn.
4. **Bước xếp giờ** chỉ bảo đảm TKB hợp lệ và tốt trong thời gian cho phép (trạng thái FEASIBLE). Mục tiêu mềm không được chứng minh là tốt nhất, kể cả khi để không giới hạn thời gian rồi dừng bằng Ctrl+C.
5. **Người bổ sung** được ghi theo định mức tuyển đầy đủ, dù có thể dạy ít hơn (ví dụ `Bộ Môn 8` ghi 23, thực dạy 6).
6. **"Kỹ năng số"** trong yêu cầu ban đầu được hiểu là **Kỹ năng sống**, vì chương trình không có môn Kỹ năng số.
7. **Số thứ tự tự đánh theo thứ tự dòng:** đổi thứ tự các dòng cùng chức vụ thì Mã GV (ví dụ `Bộ Môn 2`) đổi theo. Khi cột tên để trống, hãy dùng cột Mã GV trong file cập nhật để biết ai là ai.
8. **Tên môn phải khớp luật:** môn viết khác hẳn tên trong config (ví dụ `TV` thay cho `Tiếng Việt`) sẽ không nhận luật của môn đó; chương trình cảnh báo khi luật nhắc môn không có trong file.
