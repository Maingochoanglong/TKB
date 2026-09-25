# ĐẶC TẢ NGHIỆP VỤ HỆ THỐNG XẾP THỜI KHÓA BIỂU TỰ ĐỘNG (V16)

> **V16 thay thế V15.** Tài liệu này mô tả đúng hành vi của chương trình trong repo (thư mục `tkb/`, file chạy `main.py`).
>
> - Mọi tham số nghiệp vụ nằm ở `tkb/config.py`. Các tuỳ chọn chạy nằm ở `main.py`.
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
| 11 | Thai sản | Chữ `ts` sau chức vụ | Cột **Thai sản** (`Có`/trống); vẫn đọc được chữ `ts`. Người thai sản **không bao giờ dạy bù** |
| 12 | Tải ngày | Buffer/overload động | [Mềm] mục tiêu tải ngày theo tỷ lệ số tiết của ngày |
| 13 | Tái lập | – | Cùng dữ liệu, cùng phiên bản OR-Tools và cùng số luồng thì luôn ra cùng một TKB |
| 14 | Nội dung ô TKB | Chức vụ (môn) | Môn, xuống dòng **tên giáo viên**. Người cần tuyển và tên trùng thì kèm chức vụ |

---

## 1. Phạm vi và thuật ngữ

**Phạm vi.** Xếp TKB **tuần** cho một trường tiểu học 5 khối. Đầu vào là file danh sách nhân sự. Đầu ra gồm:
- TKB từng lớp.
- Danh sách nhân sự đã cập nhật.
- Bảng thống kê: thiếu người, dạy bù, tải giáo viên.

| Thuật ngữ | Nghĩa |
|---|---|
| GVCN | Giáo viên chủ nhiệm, chức vụ `chủ nhiệm k/n` (lớp k/n) |
| Bộ môn (GVBM) | Chức vụ `bộ môn n`, dạy được nhiều môn (mục 4) |
| GV chuyên biệt | Chức vụ `tiếng anh n`, `tin học n`, `thể dục n`, `âm nhạc n`, `mỹ thuật n`; chỉ dạy đúng môn trùng tên |
| Quản lý | Chức vụ `quản lý n` |
| Thai sản (ts) | Giáo viên đang hưởng chế độ thai sản. Số tiết ghi mức đã giảm. Ở danh sách nhân sự và thống kê, chức vụ có thêm `ts` |
| Số tiết (định mức) | Số tiết **tối đa** giáo viên dạy mỗi tuần |
| Tiết bù | Tiết dạy **vượt** định mức, chỉ có ở chế độ bù giờ |
| Người bổ sung | Người cần tuyển, tên `chưa có`, chức vụ `<chức vụ> n+1, n+2…` |
| Lớp–môn | Phần tiết của một môn ở một lớp giao cho một nhóm giáo viên được phép dạy |
| Slot | Một tiết cụ thể trong tuần: (ngày, tiết) |

---

## 2. Dữ liệu đầu vào

### 2.1. File danh sách nhân sự (bắt buộc)

Chương trình đọc sheet **đầu tiên**. Dòng tiêu đề nằm trong 20 dòng đầu và phải có các cột `Tên`, `Chức vụ`, `Số tiết`. Cột `Thai sản` không bắt buộc. Tên cột không phân biệt hoa thường.

| Cột | Bắt buộc | Quy tắc |
|---|---|---|
| Tên | Có | Họ tên, tự do |
| Chức vụ | Có | `<chức vụ> <số thứ tự>`, ví dụ `chủ nhiệm 1/1`, `bộ môn 4`, `tiếng anh 2`, `quản lý 1` |
| Số tiết | Có | Số nguyên ≥ 0. Người thai sản ghi mức đã giảm |
| Thai sản | Không | `Có` (hoặc `x`) nếu đang hưởng chế độ; để trống hoặc `Không` nếu không |

**Chức vụ hợp lệ:** `chủ nhiệm`, `bộ môn`, `tiếng anh`, `tin học`, `thể dục`, `âm nhạc`, `mỹ thuật`, `quản lý`.
- Chủ nhiệm ghi lớp dạng `khối/stt` (`chủ nhiệm 3/2`).
- Chức vụ khác ghi số thứ tự (`bộ môn 5`).
- File cũ ghi thai sản bằng chữ `ts` sau chức vụ (`bộ môn 5 ts`) vẫn đọc được.

**Chương trình từ chối file và báo rõ dòng lỗi khi:**
- Chức vụ sai dạng hoặc không thuộc danh sách trên.
- Chủ nhiệm không ghi lớp `khối/stt`, hoặc chức vụ khác lại ghi `khối/stt`.
- Số tiết trống, không phải số, âm hoặc không nguyên.
- Cột Thai sản ghi giá trị khác `Có`/`x`/`Không`/trống.
- Trùng chức vụ (kể cả `bộ môn 2` và `bộ môn 2 ts`).
- Một lớp có hai GVCN.
- Không có GVCN nào.

**File mẫu** (`data/Input_Danh_Sach_Nhan_Su_V6.xlsx`, tạo bằng `python -m tkb.template`):
- Chức vụ chọn từ danh sách thả xuống: `chủ nhiệm 1/1 … 5/10` và các chức vụ khác từ 1 đến 20. Danh sách nằm ở sheet ẩn `Danh mục`.
- Số tiết chỉ nhận số nguyên từ 0 đến 40.
- Thai sản chỉ nhận `Có`.
- Chức vụ bị trùng được tô đỏ.
- Chuyển file cũ sang file mẫu: `python -m tkb.template <mới.xlsx> --tu <cũ.xlsx>`.

### 2.2. Danh sách lớp

Lấy từ các dòng `chủ nhiệm k/n`, vì mỗi lớp luôn có đúng một GVCN. Lớp được sắp theo khối, rồi theo số thứ tự.

### 2.3. Chương trình học

Mặc định lấy trong `tkb/config.py` (`DEFAULT_CURRICULUM`). Nếu có file chương trình học (`FILE_CHUONG_TRINH` trong `main.py` hoặc `--program`) thì dùng file đó.

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

**File chương trình học:**
- Có cột `Môn học` và các cột `Khối k`. Ô trống được tính là 0.
- Số tiết phải là số nguyên ≥ 0.
- Tên môn được so khớp không phân biệt hoa thường.
- Một môn không được lặp lại.

**Kiểm tra tổng số tiết của mỗi khối:**
- Lớn hơn 32 → lỗi.
- Nhỏ hơn 32 → cảnh báo: lớp sẽ có tiết trống.

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
| Tiếng anh / Tin học / Thể dục / Âm nhạc / Mỹ thuật | Chỉ môn trùng tên chức vụ | Môn khác |
| Quản lý | Chỉ **Kỹ năng sống khối 4** | Môn/khối khác |

- **[Cứng]** HĐTN chỉ do GVCN của lớp dạy.
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
- Không bao giờ nhận môn của GV chuyên biệt (Tiếng Anh, Tin học, Thể dục, Âm nhạc, Mỹ thuật).
- Nếu trường có quản lý thì không nhận môn dành cho quản lý (KNS khối 4).

### 5.4. Kết quả với dữ liệu hiện tại

| Lớp (định mức GVCN) | GVCN dạy | Phần chuyển đi |
|---|---|---|
| Khối 1 (19) | TV 10, Toán 5, HĐTN 3, Đạo đức 1 | TV 4 tiết/lớp |
| Khối 2 (19) | TV 10, Toán 5, HĐTN 3, Đạo đức 1 | – |
| Khối 3 (19) | TV 7, Toán 5, HĐTN 3, Đạo đức 1, TV tăng cường 1, Toán tăng cường 2 | – |
| Khối 4, 5/1–5/4 (19) | TV 6, Toán 5, HĐTN 3, Khoa học 2, LS-ĐL 2, Đạo đức 1 | TV 1 tiết/lớp |
| 5/5 thai sản (16) | TV 3, Toán 5, HĐTN 3, Khoa học 2, LS-ĐL 2, Đạo đức 1 | TV 4 tiết |

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

Với dữ liệu hiện tại, còn đúng **4 tiết Tiếng Anh ở tiết 7**, mỗi GV tiếng anh 1 tiết. Đây là mức tối thiểu:
- Mỗi GV tiếng anh dạy 23 tiết.
- Ngoài tiết 1, Thứ 6 tiết 4 và tiết 7, họ chỉ còn 22 slot.

---

## 7. Xử lý khi thiếu người

Chọn chế độ bằng `CHE_DO` trong `main.py` hoặc `--mode` khi chạy dòng lệnh.

### 7.1. Chế độ tuyển thêm (`tuyen_them`)

- Phần không ai dạy được giao cho **người bổ sung**:
  - Tên `chưa có`.
  - Chức vụ `<chức vụ> n+1, n+2…`, với n là số thứ tự lớn nhất hiện có của chức vụ đó.
- **Định mức tuyển** của người bổ sung = Số tiết lớn nhất của các giáo viên cùng chức vụ, không tính người thai sản. Nếu chức vụ đó chưa có ai thì lấy 23 (`FALLBACK_SUPPLEMENT_LOAD`).
- Người bổ sung là một người thật sẽ tuyển: không dạy 2 lớp cùng lúc, và không dạy quá định mức tuyển.
- Thứ tự ưu tiên:
  1. Ít tiết giao cho người bổ sung nhất (dùng hết người hiện có trước).
  2. Ít người bổ sung nhất.
  3. Ưu tiên tuyển bộ môn hơn GV chuyên biệt.
- Tiết được dồn cho người bổ sung đầu trước. Người cuối có thể dạy chưa đủ định mức, ví dụ 23 + 23 + 6.
- Trong danh sách nhân sự, người bổ sung ghi **định mức tuyển đầy đủ** (ví dụ 23), kèm số tiết thực dạy.

### 7.2. Chế độ bù giờ (`bu_gio`)

- **Người được bù:** chỉ **GVCN** và **bộ môn**. Mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần (mặc định 2).
- **[Cứng]** Người hưởng thai sản **không bao giờ** dạy bù.
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
- `THOI_GIAN_TOI_DA` (mặc định 240) là lượng tính toán dành cho bước xếp giờ, tính xấp xỉ bằng giây.
- **[Cứng] Tái lập:** khi `CHAY_TAI_LAP_DUOC = True`, chạy lại bao nhiêu lần cũng ra **đúng một TKB**, ở **cả chế độ tuyển thêm lẫn bù giờ**, miễn là giữ nguyên:
  - file nhân sự (và file chương trình học nếu có);
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
  - Người cần tuyển ghi tên kèm chức vụ: `chưa có (bộ môn 6)`.
  - Hai giáo viên trùng tên thì kèm chức vụ, ví dụ `Lan (bộ môn 1)`. Tên để trống thì ghi chức vụ.
  - Cột ngày tự nới theo dòng dài nhất, từ 24 đến 30 (đơn vị cột Excel). Tên dài hơn thì xuống dòng và hàng tự cao thêm.
- Tên viết tắt: `HĐTN`, `TNXH`, `TV tăng cường`.
- Định dạng: font Times New Roman cỡ 14, dòng tiêu đề nền xám nhạt, viền mảnh. Khi in: khổ ngang, co vừa chiều rộng 1 trang.

**Sheet `Danh sách nhân sự`:**
- Cột: Tên, Chức vụ, Số tiết, Số tiết thực dạy, Ghi chú. Chế độ bù giờ có thêm cột **Số tiết bù**.
- Thứ tự: giáo viên theo thứ tự file gốc, sau đó đến người bổ sung.

**Sheet `Thống kê`:**
- **Thông tin chung:** chế độ, kết quả kiểm tra luật, trạng thái bộ giải, thời gian, số lớp, tổng tiết, tổng tiết thiếu, số người bổ sung, tổng tiết dạy bù, ghi chú và cảnh báo.
- **Chức vụ thiếu và số tiết thiếu:** người bổ sung và chi tiết lớp, môn.
- **Dạy bù** (chế độ bù giờ): ai bù, bao nhiêu tiết, GVCN bù môn gì.
- **Theo nhóm chức vụ:** số người, tổng định mức, đã dạy, dư, dạy bù, tiết thiếu, số người bổ sung.
- **Tải từng giáo viên:** định mức, thực dạy, dư, bù, số tiết từng ngày, số lớp dạy.
- **Lỗi kiểm tra** (nếu có).

### 11.2. File nhân sự cập nhật `<tên file nhân sự>_cap_nhat.xlsx`

- Là bản chép của file nhân sự gốc, thêm các dòng người bổ sung `chưa có` ở cuối với **định mức tuyển đầy đủ**.
- Giữ nguyên danh sách thả xuống của file mẫu.
- Dùng làm đầu vào cho lần chạy sau được. File gốc không bị sửa.

### 11.3. File thống kê giáo viên `Thong_Ke.xlsx`

Một sheet, mỗi giáo viên một dòng, theo thứ tự file nhân sự rồi đến người cần tuyển:

| STT | Tên giáo viên | Chức vụ | Số tiết quy định | Số tiết bù |
|---|---|---|---|---|

- Người cần tuyển có tên **`tuyển thêm`**. Số tiết quy định là định mức tuyển đầy đủ (ví dụ 23).
- Số tiết bù là số tiết dạy vượt định mức (chế độ bù giờ); các trường hợp khác ghi 0.
- Cuối bảng có dòng **Tổng**.

### 11.4. Màn hình và mã thoát

- Màn hình in: các bước giải, người cần bổ sung, tiết dạy bù (tổng, theo GVCN/bộ môn, số người +2/+1), số tiết môn nặng ở tiết 7, lỗi kiểm tra.
- Mã thoát:
  - `0`: thành công.
  - `1`: lỗi đầu vào, hoặc không xếp được.
  - `2`: đã xuất file nhưng kiểm tra luật **không đạt**.

---

## 12. Cấu hình

### 12.1. `main.py` (sửa rồi bấm Run)

| Hằng số | Ý nghĩa | Mặc định |
|---|---|---|
| `THU_MUC_IN`, `THU_MUC_OUT` | Thư mục vào/ra (tương đối theo `main.py`) | `data`, `out` |
| `FILE_NHAN_SU` | File nhân sự | `Input_Danh_Sach_Nhan_Su_V6.xlsx` |
| `FILE_CHUONG_TRINH` | File chương trình học; `None` = dùng mặc định | `None` |
| `FILE_TKB` | Tên file TKB | `TKB.xlsx` |
| `FILE_THONG_KE` | Tên file thống kê giáo viên | `Thong_Ke.xlsx` |
| `THOI_GIAN_TOI_DA` | Lượng tính toán cho bước xếp giờ (≈ giây) | `240` |
| `CHAY_TAI_LAP_DUOC` | Cùng dữ liệu luôn ra cùng một TKB | `True` |
| `SO_LUONG` | Số luồng tìm kiếm song song | `8` |
| `CHE_DO` | `tuyen_them` hoặc `bu_gio` | `bu_gio` |
| `SO_TIET_BU_TOI_DA` | Mức bù tối đa mỗi người (chế độ bù giờ) | `2` |
| `LUAT_HOC_SINH` | Bật luật tối đa 2 TV/2 Toán mỗi buổi | `True` |

### 12.2. `tkb/config.py` (tham số nghiệp vụ)

| Tham số | Nội dung |
|---|---|
| `DEFAULT_CURRICULUM` | Chương trình học mặc định (mục 2.3) |
| `DAYS`, `DAY_SESSIONS` | Khung thời gian (mục 3) |
| `HDTN_FIXED_SLOTS`, `HDTN_FLEX_DAYS` | HĐTN (mục 5.6) |
| `SPECIALIST_ROLES`, `GENERAL_FORBIDDEN_SUBJECTS`, `MANAGER_RULES` | Quyền dạy (mục 4) |
| `HOMEROOM_PRIORITY`, `HOMEROOM_CUT_ORDER`, `HOMEROOM_FILL_ORDER` | Phân GVCN (mục 5) |
| `HOMEROOM_PERIODS` | Tiết luôn do GVCN dạy (mục 5.5) |
| `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, `SESSION_SUBJECT_LIMITS` | Luật học sinh (mục 6) |
| `SUPPLEMENT_NAME`, `FALLBACK_SUPPLEMENT_LOAD` | Người bổ sung (mục 7.1) |
| `OVERTIME_ROLES`, `OVERTIME_MAX` | Bù giờ (mục 7.2) |
| `Weights` | Trọng số mục tiêu (mục 8) |

---

## 13. Kết quả tham chiếu với dữ liệu hiện tại

**Nhân sự** (`Input_Danh_Sach_Nhan_Su_V6.xlsx`): 45 người, gồm:
- 29 GVCN, ứng với 29 lớp: khối 1–4 mỗi khối 6 lớp, khối 5 có 5 lớp.
- 5 bộ môn, 4 tiếng anh, 3 thể dục, 1 âm nhạc, 1 mỹ thuật, 1 tin học, 1 quản lý.
- 2 người thai sản: chủ nhiệm 5/5 (16 tiết) và bộ môn 5 (19 tiết).

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
| Tuyển thêm | Thiếu **52** tiết. Tuyển `bộ môn 6`, `bộ môn 7`, `bộ môn 8` (định mức 23; thực dạy 23/23/6) |
| Bù giờ (+2) | **Không phải tuyển.** Bù 52 tiết, toàn bộ do GVCN (24 người +2, 4 người +1). Người thai sản và bộ môn không bù |
| Cả hai | 145/145 ô tiết 1 buổi sáng là GVCN của lớp. Môn nặng ở tiết 7: 4 tiết (Tiếng Anh, mức tối thiểu) |

Cả hai chế độ đều đã **chứng minh tối ưu** ở bước phân công: số tiết thiếu, số người tuyển và số tiết bù là nhỏ nhất.

---

## 14. Giả định và hạn chế đã biết

1. **Tiết 1 buổi sáng thuộc GVCN** làm giáo viên không chủ nhiệm chỉ còn 26 slot/tuần. Giáo viên có định mức trên 26 sẽ bị phát hiện ngay ở bước phân công và cần người bổ sung hoặc bù.
2. **Thai sản** không có ngày bắt đầu/kết thúc. Khi chế độ thay đổi, sửa cột Thai sản và Số tiết rồi chạy lại.
3. **Người được bù +1 thay vì +2**, lớp nào quản lý dạy KNS, và cách chia các tiết cùng chi phí là do chương trình chọn. Các phương án này tương đương nhau theo mục tiêu. Đổi dữ liệu hoặc `SO_LUONG` có thể làm đổi lựa chọn.
4. **Bước xếp giờ** chỉ bảo đảm TKB hợp lệ và tốt trong thời gian cho phép (trạng thái FEASIBLE). Mục tiêu mềm không được chứng minh là tốt nhất.
5. **Người bổ sung** được ghi theo định mức tuyển đầy đủ, dù có thể dạy ít hơn (ví dụ `bộ môn 8` ghi 23, thực dạy 6).
6. **"Kỹ năng số"** trong yêu cầu ban đầu được hiểu là **Kỹ năng sống**, vì chương trình không có môn Kỹ năng số.
7. **Danh sách thả xuống** của file mẫu hỗ trợ tối đa 10 lớp mỗi khối và số thứ tự 1–20 cho mỗi chức vụ khác. Muốn mở rộng thì tạo lại file mẫu (`CLASSES_PER_GRADE`, `MAX_INDEX` trong `tkb/template.py`).
