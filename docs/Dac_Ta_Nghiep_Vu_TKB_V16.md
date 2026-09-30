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
| 11 | Thai sản | Chữ `ts` sau chức vụ | **Bỏ hẳn.** Chương trình không có chế độ thai sản: người được giảm tiết ghi Số Tiết/Tuần đã giảm, mọi luật (kể cả bù giờ, định mức tuyển) áp dụng như nhau. Cột Chế Độ của file cũ (nếu còn) bị bỏ qua; chữ `ts` sau chức vụ không còn nhận |
| 12 | Tải ngày | Buffer/overload động | [Mềm] mục tiêu tải ngày theo tỷ lệ số tiết của ngày |
| 13 | Tái lập | – | Cùng file vào, cùng hằng số `main.py` và cùng phiên bản OR-Tools thì **máy nào cũng** ra cùng một TKB; kiểm bằng **Mã kết quả** (mục 9) |
| 14 | Nội dung ô TKB | Chức vụ (môn) | Môn, xuống dòng **tên giáo viên**. Tên trống hoặc người cần tuyển thì ghi **Mã GV** (`Bộ Môn 6`); tên trùng thì kèm Mã GV |
| 15 | File vào | Hai file: nhân sự (Tên, Chức vụ kèm số thứ tự, Số tiết) và chương trình học | **Một file duy nhất (mẫu V8):** sheet NHÂN SỰ (Họ và Tên, Chức Vụ không số thứ tự, Lớp khối/số thứ tự, Số Tiết/Tuần) và sheet CHƯƠNG TRÌNH HỌC (bắt buộc) |
| 16 | Dữ liệu trong code | Chương trình học, danh sách môn, danh sách chức vụ chuyên biệt, định mức 23 nằm trong code | **Không còn trong code.** Những gì suy ra được từ file vào thì lấy từ file vào (mục 2.4) |
| 17 | Định dạng file ra | Cố định trong code | **Chép style của file vào** (phông, cỡ chữ, viền, căn lề, chiều cao dòng 25), được thêm cột (mục 11) |
| 18 | Tuỳ chọn chạy (`main.py`) | Thời gian cố định | `THU_MUC_OUT` để trống thì ghi vào thư mục dự án; `THOI_GIAN_TOI_DA` để trống thì **không giới hạn** (Ctrl+C dừng sớm). Mặc định: bù giờ, áp dụng luật học sinh, 240 giây, tái lập (mục 12.1) |
| 19 | Môn học liền trong buổi | – | **[Cứng]** Môn có từ 2 tiết trong một buổi phải học liền nhau (mục 6) |
| 20 | File ra | `TKB.xlsx` gồm TKB, danh sách nhân sự và thống kê | `TKB.xlsx` **chỉ có thời khóa biểu** (các sheet Khối). Tổng quan, danh sách nhân sự và các bảng thống kê chuyển sang `Thong_Ke.xlsx` (mục 11) |
| 21 | Tái lập | Thỉnh thoảng chạy lại vẫn ra TKB khác | Tắt phần chia sẻ không tất định giữa các luồng của OR-Tools: chạy lại luôn ra cùng TKB trên các máy cùng hệ điều hành; Actions kiểm trên 4 máy Windows (mục 9) |
| 22 | Buổi sáng cho TV, Toán | – | **[Mềm]** TV, Toán ưu tiên buổi sáng; tiết tăng cường ưu tiên buổi chiều (mục 8.2). Rút ra từ TKB của hai trường khác (`docs/Tham_Khao_TKB_Truong_Khac.md`) |
| 23 | Cột TIẾT của TKB, file mẫu | Buổi chiều ghi tiết 1–3; mẫu đầu ra V5 | Ghi **tiết trong ngày**: sáng 1–4, chiều **5–7**. Mẫu đầu ra `data/Output_Template_TKB_V8.xlsx` và `data/Output_Template_Thong_Ke_V8.xlsx` (sinh lại bằng `python tools/mau_dau_ra.py`) |
| 24 | Mẫu file vào | Đọc cả mẫu cũ V5–V7 (chức vụ kèm số, `--program`, chuyển file cũ `--tu`); có file mẫu tên giả trong `data/` | **Chỉ đọc mẫu V8** (mục 2.1). `data/` chỉ còn file của trường; test dùng trường mẫu tên giả sinh bằng code (`tests/du_lieu_mau.py`) |
| 25 | File thống kê `Thong_Ke.xlsx` | 6 sheet: Tổng quan, Danh sách nhân sự, Thống kê giáo viên, Phân công, Theo ngày, Theo chức vụ | **Một bảng:** Họ và Tên, Chức Vụ (Mã GV), số tiết từng môn, Tổng Tiết, dòng Tổng (mục 11.3). Mã kết quả, kiểm tra luật, tuyển thêm, dạy bù chỉ in ra màn hình |
| 26 | Phân công | CP-SAT (2 lần giải, ~45 giây, khác nhau giữa Windows và Linux) | **Dự toán + phân công không dùng CP-SAT** (`tkb/phan_cong.py`): luồng chi phí nhỏ nhất rồi tìm kiếm cục bộ, dưới 1 giây, mọi máy ra cùng phân công. Dự toán (tiết thiếu, bù, tuyển, biên bù) in ra trước khi xếp (mục 8.1, 9) |
| 27 | Bù giờ không đủ | Tự thêm người `chưa có` | **Báo lỗi, không tuyển, không ra TKB**: in từng tiết thiếu, ghi sheet `Thiếu tiết` vào `Thong_Ke.xlsx`, mã thoát 3 (mục 7.2) |
| 28 | Chế độ tuyển thêm | Người bổ sung nhận phần thiếu, CP-SAT chọn tiết | **Cùng TKB với chế độ bù**: người mới dạy đúng các ô mà ở chế độ bù là tiết bù, cộng các tiết còn thiếu (mục 7.1) |
| 29 | Luật người dạy | – | **[Cứng]** Hai tiết liền nhau cùng nhóm môn do 1 người dạy. **[Cứng]** GVCN trước: tiết đầu tuần của môn ưu tiên là của GVCN, người khác không dạy trước tiết đó (mục 5.7, 6) |
| 30 | Luật học sinh | Tối đa 2 TV, 2 Toán mỗi buổi | **Mỗi nhóm môn** (TV + TV tăng cường, Toán + Toán tăng cường, môn khác) tối đa 2 tiết mỗi buổi; **Toán tối đa 1 tiết mỗi ngày**; nhóm môn từ 6 tiết, tổng chẵn (TV khối 1–3) **ghép cặp 2 tiết liền** (mục 6) |
| 31 | Trọng số, thời gian | TV/Toán buổi sáng 50, môn nặng tiết 7 200, rải đều 20/60; tăng cường ưu tiên buổi chiều; 240 | 300, 400, 40/120; TV tăng cường ghép với TV (chỉ Toán tăng cường ưu tiên chiều), thưởng tiết tăng cường liền sau tiết chính cùng người; **480** (mục 8.2, 9) |
| 32 | File ra | `TKB.xlsx`, `Thong_Ke.xlsx`, file cập nhật | Thêm **`TKB_chuc_vu.xlsx`**: cùng TKB, mỗi ô thêm dòng chức vụ (Mã GV) (mục 11) |
| 33 | File thống kê | Không phân biệt người bù, người tuyển | Tô **vàng** dòng người dạy bù (chế độ bù giờ), tô **xanh lá** dòng người cần tuyển (chế độ tuyển thêm), chú thích dưới bảng (mục 11.3). Chỉ đổi cách ghi file, TKB và mã kết quả không đổi |
| 34 | Bước xếp giờ | Một lần CP-SAT trong `THOI_GIAN_TOI_DA` (480); không giới hạn = chạy đến khi chứng minh tối ưu (gần như không dừng) | **CP-SAT khởi đầu rồi các vòng QA → xếp lại từng vùng** (mục 9); mặc định **600**; không giới hạn = xếp lại đến khi một vòng không còn cải thiện, vẫn tái lập. File của trường: chi phí xếp giờ 21.590 → 17.260 trong khoảng 4–6 phút (một lần CP-SAT chạy 110 phút chỉ được 18.270) |
| 35 | Thời gian xếp giờ | Mặc định 600; khởi đầu 20% ngân sách (không giới hạn: 120) | Mặc định **1200**; khởi đầu 20% ngân sách nhưng **tối đa 120** (`LNS_START_MAX`, thay `LNS_START_UNLIMITED`), phần còn lại cho các vòng xếp lại (mục 9). Thử trên file của trường với 1200: khởi đầu 120 cho 17.200 (Linux) / 17.260 (Windows), khởi đầu 240 cho 17.580 / 17.150; khởi đầu 120 ra đúng TKB của chế độ không giới hạn. Đặt 600 thì vẫn ra đúng TKB như trước |
| 36 | Tên lớp | Chỉ dạng khối/số thứ tự (`1/1`) | Nhận thêm dạng **khối rồi tên lớp** (`1D15`); file của trường đổi sang dạng này (mục 2.1.1) |
| 37 | Hai cơ sở | Không có | Cột `Cơ sở 2`. **[Cứng] Mỗi buổi, một GV chỉ dạy ở một cơ sở** (mục 4.1). TKB cũ của trường có 1–4 buổi/tuần mỗi GV bộ môn, chuyên biệt phải chạy qua lại hai cơ sở. Cùng thai sản và buổi nghỉ, chi phí xếp giờ của file trường tăng từ 17.200 lên 22.850 (Linux; Windows 17.260 → 21.320); môn nặng tiết 7 từ 4 lên 8 tiết |
| 38 | Thai sản | Không có (đã bỏ ở bản trước) | Cột `Thai Sản`. **[Cứng]** không dạy bù, chỉ dạy các lớp ở cơ sở 2 (mục 4.1, 7.2) |
| 39 | Hợp đồng | Không có | Cột `Hợp Đồng`. Thứ tự bù: **GVCN hợp đồng → GVCN khác → bộ môn hợp đồng → bộ môn khác** (mục 7.2, 8.1) |
| 40 | Giữ phân công cũ | Không có | Cột `Lớp Đang Dạy` (các lớp dạy trong TKB cũ). GV bộ môn, chuyên biệt ưu tiên giữ **khối** cũ, rồi giữ **lớp** cũ: mục tiêu mềm, sau số tiết thiếu/bù và "không chia lớp–môn", trước gom lớp và cân bằng tải (mục 8.1) |
| 41 | Buổi nghỉ | Không có | Cột `Buổi Nghỉ`: buổi cố định (`Chiều T5`) hoặc số buổi bất kỳ (`2 buổi chiều`). **[Cứng]** không xếp tiết vào buổi nghỉ (mục 4.1) |
| 42 | File ra theo cơ sở; ô tăng tiết | Một file TKB cho cả trường; file thống kê chỉ tô cả dòng người dạy bù | Có lớp ở cơ sở 2 thì **tách TKB thành `..._diem_chinh.xlsx` (cơ sở 1) và `..._diem_phu.xlsx` (cơ sở 2)**, cả bản có chức vụ (mục 11). File thống kê tô **cam** các ô môn có tiết dạy bù, kèm ghi chú số tiết (mục 11.3). Chỉ đổi cách ghi file, mã kết quả không đổi |
| 43 | Cả ngày một cơ sở | Chỉ cấm đổi cơ sở giữa buổi; file trường còn 21 lần GV dạy sáng một cơ sở, chiều cơ sở kia | **[Mềm]** phạt `campus_day_switch` = 3000 mỗi (GV, ngày) dạy cả hai cơ sở (mục 4.1, 8.2). Đã thử: luật cứng cả ngày không ra TKB trong 1200 (UNKNOWN); phạt 300 / 1000 / 3000 còn 8 / 4 / 4 lần, chọn 3000 |
| 44 | Bỏ dòng nhân sự trùng; bù tối đa +3 | File trường có 45 dòng nhân sự, trong đó dòng 34 (bộ môn 23 tiết) trùng người với dòng 46 (bộ môn thai sản); `main.py` bù tối đa 2 | Trường xác nhận trùng: **bỏ dòng 34** (còn 44 người). Mất 23 tiết định mức nên với +2 thiếu 17 tiết (Âm Nhạc 6, Mỹ Thuật 6, Công nghệ 4, KNS 1); trường chốt **`SO_TIET_BU_TOI_DA` = 3** trong `main.py`. Dự toán: bù 79 tiết, toàn GVCN (23 người +3, 5 người +2). `config.OVERTIME_MAX` (dòng lệnh, test) vẫn 2 |
| 45 | Thống kê gọn ai dư, ai bù | File vào cập nhật có Mã GV, Số Tiết Thực Dạy, Số Tiết Bù; không thấy ai còn dư tiết | Thêm cột **Số Tiết Dư** và tô nền cả dòng: bù vàng, tuyển xanh lá, dư xanh dương (mục 11.2). Chỉ đổi file ra, mã kết quả không đổi |

---

## 1. Phạm vi và thuật ngữ

**Phạm vi.** Xếp TKB **tuần** cho một trường tiểu học. Đầu vào là một file Excel gồm danh sách nhân sự và chương trình học. Đầu ra gồm:
- TKB từng lớp.
- Danh sách nhân sự đã cập nhật.
- Bảng thống kê: số tiết từng môn của mỗi giáo viên.

| Thuật ngữ | Nghĩa |
|---|---|
| GVCN | Giáo viên chủ nhiệm, chức vụ `Chủ Nhiệm`, Mã GV `Chủ Nhiệm k/n` (lớp k/n) |
| Bộ môn (GVBM) | Chức vụ `Bộ Môn`, Mã GV `Bộ Môn n`, dạy được nhiều môn (mục 4) |
| GV chuyên biệt | Chức vụ **trùng tên một môn** trong sheet CHƯƠNG TRÌNH HỌC (ví dụ `Tiếng Anh`, `Thể Dục`, `Tin Học`); chỉ dạy đúng môn đó |
| Mã GV | Chức vụ kèm số thứ tự hoặc lớp, ví dụ `Chủ Nhiệm 1/1`, `Tiếng Anh 2`, `Bộ Môn 6`. Dùng để nhận ra giáo viên khi cột tên để trống |
| Quản lý | Chức vụ `Quản Lý`, Mã GV `Quản Lý n` |
| Số tiết (định mức) | Số tiết **tối đa** giáo viên dạy mỗi tuần |
| Tiết bù | Tiết dạy **vượt** định mức, chỉ có ở chế độ bù giờ |
| Người bổ sung | Người cần tuyển, tên `chưa có`, chức vụ `<chức vụ> n+1, n+2…` |
| Lớp–môn | Phần tiết của một môn ở một lớp giao cho một nhóm giáo viên được phép dạy |
| Slot | Một tiết cụ thể trong tuần: (ngày, tiết) |

---

## 2. Dữ liệu đầu vào

### 2.1. File vào (một file duy nhất)

Đầu vào là **một file Excel duy nhất theo mẫu V8** (`FILE_VAO` trong `main.py`, ví dụ `data/INPUT_V8.xlsx`) gồm:

| Sheet | Bắt buộc | Nội dung |
|---|---|---|
| `NHÂN SỰ` | Có | Danh sách nhân sự (mục 2.1.1). Nếu không có sheet tên này thì đọc sheet đầu tiên |
| `CHƯƠNG TRÌNH HỌC` | Có | Chương trình học (mục 2.3). Thiếu sheet này thì báo lỗi |

Tên sheet và tên cột không phân biệt hoa thường. Dòng tiêu đề nằm trong 20 dòng đầu. Chỉ đọc mẫu V8: tiêu đề cột phải là `Họ và Tên`, `Chức Vụ`, `Lớp`, `Số Tiết/Tuần`.

#### 2.1.1. Sheet NHÂN SỰ

| Cột | Bắt buộc | Quy tắc |
|---|---|---|
| Họ và Tên | Có (cột) | Họ tên, tự do. **Có thể để trống** (bảo mật): TKB ghi Mã GV thay tên |
| Chức Vụ | Có | `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý`, hoặc **đúng tên một môn** trong sheet CHƯƠNG TRÌNH HỌC (GV chuyên biệt). **Không ghi số thứ tự**. So khớp không phân biệt hoa thường, dấu câu, khoảng trắng thừa |
| Lớp | Với Chủ Nhiệm | Dạng **khối/số thứ tự** (`1/1`) hoặc **khối rồi tên lớp** (`1D15`, `2A`); khối là các chữ số đầu. Chỉ Chủ Nhiệm được ghi Lớp |
| Số Tiết/Tuần | Có | Số nguyên ≥ 0. Người được giảm tiết (ví dụ thai sản) ghi mức đã giảm |
| Thai Sản | Không | `Có` hoặc để trống. Có: không dạy bù, chỉ dạy các lớp ở cơ sở 2 |
| Hợp Đồng | Không | `Có` hoặc để trống. Có: nhận tiết bù trước người cùng loại (mục 7.2) |
| Cơ sở 2 | Không | `Có` hoặc để trống. Dòng Chủ Nhiệm: lớp học ở cơ sở 2. Dòng khác: GV chỉ dạy ở cơ sở 2 |
| Lớp Đang Dạy | Không | Các lớp GV dạy trong TKB cũ, cách nhau bằng dấu phẩy/chấm phẩy (vd `3D17, 3D18`). Chỉ dùng cho GV không chủ nhiệm (mục 8.1) |
| Buổi Nghỉ | Không | Buổi cố định (`Chiều T5`, `Sáng thứ 6`) và/hoặc số buổi bất kỳ (`2 buổi chiều`, `1 buổi sáng`, `2 buổi`), cách nhau bằng dấu phẩy; không phân biệt hoa thường, dấu. Buổi vốn nghỉ (chiều Thứ 6) bỏ qua. Số buổi bất kỳ tính thêm ngoài buổi cố định; `n buổi` (không ghi sáng/chiều) là tổng số buổi trống tối thiểu |
| STT, cột khác | Không | Không dùng, ghi gì cũng được (ví dụ cột ghi chú) |

- **Tự đánh số thứ tự (Mã GV):** mỗi chức vụ (trừ Chủ Nhiệm) được đánh số 1, 2, 3… theo thứ tự dòng trong file, ví dụ Bộ Môn thứ hai là `Bộ Môn 2`. Chủ Nhiệm được nhận diện theo Lớp (`Chủ Nhiệm 1/1`).
- **Không đọc mẫu cũ** (V5–V7: chức vụ ghi kèm số như `bộ môn 5`, chương trình học ở file riêng): Chức Vụ có chữ số thì báo lỗi. Muốn dùng dữ liệu cũ thì tạo file mẫu V8 trống rồi chép sang, bỏ số thứ tự.

**Chương trình từ chối file và liệt kê tất cả lỗi một lần, kèm số dòng, khi:**
- Chức vụ không phải Chủ Nhiệm/Bộ Môn/Quản Lý và không trùng tên môn nào trong chương trình học, hoặc có ghi số thứ tự (mẫu cũ).
- Chủ Nhiệm thiếu Lớp, Lớp sai dạng khối/số thứ tự, hoặc chức vụ khác lại ghi Lớp.
- Lớp bị Excel đổi thành ngày tháng (khi gõ tay `1/1` vào ô không định dạng chữ).
- Số tiết trống, không phải số, âm hoặc không nguyên.
- Một lớp có hai Chủ Nhiệm.
- Không có Chủ Nhiệm nào.
- Cột Thai Sản/Hợp Đồng/Cơ sở 2 ghi khác `Có`/`Không`/trống; Lớp Đang Dạy có lớp không có Chủ Nhiệm nào.
- Buổi Nghỉ ghi sai dạng, xin nhiều buổi hơn số buổi trong tuần, hoặc GVCN xin nghỉ buổi sáng (tiết 1 luôn do GVCN dạy).
- GVCN thai sản mà lớp không đánh dấu Cơ sở 2.

Chương trình **cảnh báo** (vẫn chạy) khi dãy lớp của một khối bị hụt, ví dụ có 1/3, 1/5 mà không có 1/4.

**File mẫu V8** (tạo bằng `python -m tkb.template`), style giống file của nhà trường (Times New Roman 14, tiêu đề in đậm không tô nền, viền mảnh, căn giữa, dòng cao 25):
- Sheet NHÂN SỰ: `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ`, mỗi cột có chú thích. Chức Vụ có danh sách gợi ý (Chủ Nhiệm, Bộ Môn, Quản Lý; vẫn gõ được tên môn cho GV chuyên biệt). Lớp định dạng chữ và phải bắt đầu bằng số khối. Ba cột Có/Không có danh sách `Có`. Số Tiết/Tuần chỉ nhận số nguyên 0–40. Tô đỏ Lớp trùng, Chủ Nhiệm thiếu Lớp, chức vụ khác ghi Lớp.
- Sheet CHƯƠNG TRÌNH HỌC: `Môn học | Khối 1 …`. File mẫu trống không có môn nào.

### 2.2. Danh sách lớp

Lấy từ cột Lớp của các dòng Chủ Nhiệm, vì mỗi lớp luôn có đúng một GVCN. Lớp được sắp theo khối, rồi theo phần chữ, rồi theo số (`1D9` trước `1D15`). Lớp ở cơ sở 2 là các lớp có `Cơ sở 2 = Có` trên dòng Chủ Nhiệm.

### 2.3. Chương trình học

Lấy từ sheet `CHƯƠNG TRÌNH HỌC` của file vào (**bắt buộc**; code không chứa chương trình học nào).

Ví dụ (trường mẫu tên giả của test, `tests/du_lieu_mau.py`):

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
| Giáo viên, chức vụ, lớp chủ nhiệm, định mức | HĐTN: 2 slot cố định, ngày của tiết thứ ba (mục 5.6) |
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
- Thể dục, Âm nhạc, Mỹ thuật do GV chuyên biệt dạy trước. Bộ môn chỉ dạy thay phần vượt năng lực của GV chuyên biệt; dự toán in số tiết này.
- **[Mềm]** Hạn chế chia một lớp–môn cho nhiều giáo viên.

### 4.1. Hai cơ sở, thai sản, buổi nghỉ

Theo các cột không bắt buộc của sheet NHÂN SỰ (mục 2.1.1). File không có các cột này thì không có luật nào dưới đây.

- **[Cứng] Mỗi buổi, một giáo viên chỉ dạy ở một cơ sở.**
  - Buổi là sáng hoặc chiều của một ngày. Ví dụ sáng Thứ 2 có tiết ở cơ sở 2 thì cả buổi sáng đó người ấy chỉ dạy các lớp cơ sở 2. Giữa buổi sáng và buổi chiều thì đổi cơ sở được.
  - Áp dụng cho mọi người, kể cả người cần tuyển, để chế độ tuyển thêm vẫn dùng đúng TKB của chế độ bù. GVCN chỉ dạy lớp mình nên luôn thỏa.
  - Cài đặt (`solver._teacher_sessions`): mỗi GV có tiết ở cả hai cơ sở, mỗi buổi có một biến "buổi này ở cơ sở 2"; mỗi tiết của người đó kéo theo biến này đúng hoặc sai tùy cơ sở của lớp.
- **[Mềm] Cả ngày ở một cơ sở:** mỗi (GV, ngày) sáng dạy cơ sở này, chiều cơ sở kia bị phạt `campus_day_switch` (3000, mục 8.2).
  - Không để cứng: với file của trường, luật cứng cả ngày không tìm được TKB trong 1200 (trạng thái UNKNOWN).
  - Thử mức phạt trên file của trường (chế độ bù, 1200, Linux): không phạt 21 lần; 300: 8 lần; 1000: 4 lần; 3000: 4 lần, chi phí các mục tiêu khác gần như bằng khi không phạt. Chọn 3000. Bản chính thức (QA của các vòng xếp lại cũng tính phạt này) còn **1 lần** trên cả Linux và Windows (mục 9).
  - Cài đặt (`solver._campus_day_switch`): mỗi (GV, ngày) có thể dạy cả hai cơ sở có hai biến "có dạy cơ sở 1", "có dạy cơ sở 2" và biến "cả hai" ≥ tổng − 1, phạt biến "cả hai". QA của các vòng xếp lại tính cùng mức phạt (mục 9). Màn hình in số lần còn lại.
- **[Cứng] Thai sản:** không dạy bù (mục 7.2); chỉ dạy các lớp ở cơ sở 2. GV có `Cơ sở 2 = Có` trên dòng không phải Chủ Nhiệm cũng chỉ dạy các lớp ở cơ sở 2.
- **[Cứng] Buổi nghỉ:**
  - buổi nghỉ cố định không có tiết nào của người đó;
  - "n buổi chiều/sáng bất kỳ": chương trình tự chọn, người đó có ít nhất n buổi loại đó trống (ngoài các buổi nghỉ cố định);
  - khi phân công, số ô giờ một người dạy được trừ đi các buổi nghỉ (buổi cố định bỏ hẳn; n buổi bất kỳ bỏ n buổi có ít ô nhất).

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
| 5/5 (16) | TV 3, Toán 5, HĐTN 3, Khoa học 2, LS-ĐL 2, Đạo đức 1 | TV 4 tiết (ở chế độ bù giờ, GVCN này có thể bù lại) |

### 5.5. Tiết 1 buổi sáng

- **[Cứng]** Tiết 1 buổi sáng của **mọi ngày** (Thứ 2–Thứ 6) luôn do GVCN của lớp dạy (`HOMEROOM_PERIODS = {1}`). Giáo viên khác không được xếp vào tiết này.
- GVCN phải có ít nhất 5 tiết/tuần, nếu không chương trình báo lỗi.
- Hệ quả: giáo viên không chủ nhiệm chỉ còn **26 slot/tuần** để dạy (32 − 5 tiết 1 − Thứ 6 tiết 4 của HĐTN).

### 5.6. HĐTN

- **[Cứng]** Hai tiết cố định: **Thứ 2 tiết 1** và **Thứ 6 tiết 4** (`HDTN_FIXED_SLOTS`).
- **[Cứng]** Tiết thứ ba xếp vào **Thứ 3 – Thứ 5** (`HDTN_FLEX_DAYS`).
- **[Mềm]** Tiết thứ ba ưu tiên tiết cuối buổi: mỗi tiết cách cuối buổi bị phạt 200.
- Không môn nào khác của lớp được xếp vào slot đã cố định cho HĐTN.

### 5.7. GVCN dạy trước

- **[Cứng]** Nhóm môn ưu tiên của GVCN (mục 5.1; TV tăng cường tính chung với TV, Toán tăng cường với Toán) mà có người khác cùng dạy ở lớp đó (bộ môn, người tuyển mới): **tiết đầu tuần của nhóm môn là của GVCN**, và mọi tiết của người khác không đứng trước tiết GVCN đầu tiên đó.
- Lý do: GVCN mở bài của tuần trước. Không bắt mọi tiết của người khác phải sau mọi tiết của GVCN (thử nghiệm cho thấy cách đó làm TKB kém rõ: rải đều từ 17 lên 20–23).
- Luôn áp dụng, không tắt cùng luật học sinh.

---

## 6. Luật bảo vệ học sinh

| Luật | Loại | Nội dung |
|---|---|---|
| Giới hạn mỗi buổi | **[Cứng]** | Mỗi **nhóm môn** tối đa **2 tiết** mỗi buổi (`SESSION_GROUP_LIMIT`). Nhóm môn: TV cùng TV tăng cường, Toán cùng Toán tăng cường (`SUBJECT_GROUPS`), môn khác là nhóm riêng. Tắt được bằng `LUAT_HOC_SINH = False` |
| Toán mỗi ngày | **[Cứng]** | **Toán tối đa 1 tiết mỗi ngày** khi số tiết Toán/tuần không quá số ngày học (`DAILY_LIMITS`). Tắt cùng `LUAT_HOC_SINH` |
| Ghép cặp | **[Cứng]** | Nhóm môn có **từ 6 tiết/tuần và tổng chẵn** (`PAIR_MIN_LESSONS`; trừ Toán và HĐTN, `PAIR_EXCLUDED`) học thành **cặp 2 tiết liền nhau**: mỗi buổi 0 hoặc 2 tiết của nhóm. Với chương trình hiện tại: TV + TV tăng cường khối 1 (14, 7 cặp), khối 2 (12, 6 cặp), khối 3 (8, 4 cặp). Phân công luôn chia chẵn phần của mỗi người trong nhóm. Tắt cùng `LUAT_HOC_SINH` |
| Môn học liền trong buổi | **[Cứng]** | Môn nào có từ 2 tiết trong cùng một buổi thì các tiết đó phải **liền nhau**. Áp dụng cho mọi môn, không phân biệt giáo viên. Chỉ xét trong từng buổi (tiết 4 sáng và tiết 5 không tính là liền). Tắt cùng `LUAT_HOC_SINH = False` |
| Liên tiết do 1 người | **[Cứng]** | Hai tiết liền nhau trong một buổi, cùng lớp, **cùng nhóm môn** phải do **cùng một người** dạy. Luôn áp dụng |
| Môn nặng ở tiết 7 | **[Mềm]** | Mỗi tiết môn nặng ở tiết 7 bị phạt 400 (`heavy_late`) |
| Tiết nặng liên tiếp | Bỏ | Không còn giới hạn |

Ví dụ luật học liền, buổi sáng tiết 1–4:
- Sai: `Tiếng Việt, Toán, Tiếng Việt, Tiếng Anh` (Tiếng Việt ở tiết 1 và 3, bị Toán chen giữa).
- Đúng: `Toán, Tiếng Việt, Tiếng Việt, Tiếng Anh` hoặc `Tiếng Việt, Tiếng Việt, Toán, Tiếng Anh`.

**Môn nặng** (`HEAVY_SUBJECTS`): Toán, Toán tăng cường, Tiếng Việt, Tiếng Việt tăng cường, Tiếng Anh, Khoa học, Tin học.

Mỗi GV tiếng anh dạy 23 tiết; ngoài tiết 1, Thứ 6 tiết 4 và tiết 7, họ chỉ còn 22 slot, nên luôn còn ít nhất 1 tiết Tiếng Anh ở tiết 7 mỗi người.

---

## 7. Xử lý khi thiếu người

Chọn chế độ bằng `CHE_DO` trong `main.py` hoặc `--mode` khi chạy dòng lệnh.

Cả hai chế độ **dùng chung một TKB** (cùng vị trí môn ở mọi ô). Trước khi xếp, chương trình **dự toán** (mục 8.1) và in ra: tổng tiết cần dạy chia theo GVCN, GV chuyên biệt, quản lý, bộ môn, tiết bù và tiết thiếu; biên bù (đã bù / tối đa có thể bù, theo GVCN và bộ môn).

### 7.1. Chế độ tuyển thêm (`tuyen_them`)

- **Người mới nhận đúng các tiết bù** của chế độ bù giờ (mục 7.2), cộng các tiết không ai dạy được. Các ô khác của TKB giống hệt chế độ bù giờ; các ô bù đổi người dạy từ GVCN/bộ môn sang người mới.
- Người mới:
  - Tên `chưa có`, Mã GV `<chức vụ> n+1, n+2…` (ví dụ `Bộ Môn 6`), với n là số thứ tự lớn nhất hiện có của chức vụ đó.
  - Chức vụ: bộ môn nếu bộ môn được dạy các tiết đó; tiết thiếu của môn bộ môn không được dạy (Tiếng Anh, Tin học) thì tuyển GV chuyên biệt của môn.
  - **Định mức tuyển** = Số tiết lớn nhất của các giáo viên cùng chức vụ trong file vào. Chức vụ chưa có ai thì lấy Số tiết lớn nhất của các giáo viên không chủ nhiệm, không quản lý.
  - Là một người thật sẽ tuyển: không dạy 2 lớp cùng lúc, không dạy tiết 1 (của GVCN), không quá định mức tuyển.
- Chia tiết cho người mới (`tach_tiet_bu`):
  - tiết bù của một người ở một lớp giao trọn cho một người mới;
  - mỗi người mới tối đa **một cặp tiết mỗi buổi** (9 cặp/tuần), vì các tiết ghép cặp (mục 6) phải liền nhau;
  - số người = ít nhất có thể theo định mức và giới hạn cặp; người số nhỏ nhận nhiều tiết hơn.
- Trong danh sách nhân sự, người mới ghi **định mức tuyển đầy đủ** (ví dụ 23), kèm số tiết thực dạy.
- Dự phòng: nếu không xếp được TKB với phân công cố định, chương trình giải mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ) với thêm người dự phòng (mục 9). Khi đó TKB không còn khớp chế độ bù.

### 7.2. Chế độ bù giờ (`bu_gio`)

- **Người được bù:** chỉ **GVCN** và **bộ môn**. Mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần (`main.py` mặc định 3 cho file của trường; dòng lệnh và `config.OVERTIME_MAX`: 2). **[Cứng]** GV đang hưởng thai sản không bù.
- **[Cứng]** GVCN chỉ bù ở **lớp mình**, và không bù môn của GV chuyên biệt.
- **[Cứng]** GVCN được **ưu tiên bù lớp mình**: không được để bộ môn dạy bù ở lớp X một môn mà GVCN lớp X dạy được, trong khi GVCN lớp X chưa bù hết mức. Bộ kiểm tra báo lỗi.
- **Thứ tự môn GVCN bù:**
  1. Môn ưu tiên (lấy lại tiết đã bị cắt ở mục 5.2), theo nhóm môn; nhóm ghép cặp giữ phần của GVCN chẵn.
  2. Các môn còn lại theo thứ tự TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ, **ưu tiên nhận trọn môn** cho vừa số tiết bù (không chia đôi môn nếu tránh được).
- **Thứ tự ưu tiên khi quyết định ai bù:**
  1. Ít tiết không ai dạy nhất.
  2. Ít tiết bù của **bộ môn** nhất: **GVCN bù trước**, bộ môn chỉ bù khi GVCN đã bù hết mức.
  3. Ít tiết bù của GVCN nhất.
  4. **Hợp đồng trước:** GVCN hợp đồng bù trước GVCN khác; bộ môn hợp đồng bù trước bộ môn khác. Thứ tự đầy đủ: GVCN hợp đồng → GVCN khác → bộ môn hợp đồng → bộ môn khác.
  5. **Chia đều** trong từng nhóm trên: mọi người bù +1 rồi mới có người bù +2.
  6. Đúng thứ tự môn ở trên. GVCN phải nhường môn ưu tiên vì chia chẵn thì đổi mức bù với một GVCN khác (tổng không đổi).
- **Bù hết mức mà vẫn thiếu: báo lỗi, không tuyển, không ra TKB.** Màn hình in từng lớp, môn, số tiết thiếu, lý do và cách sửa (tăng mức bù, sửa định mức/nhân sự, hoặc chạy chế độ tuyển thêm); `Thong_Ke.xlsx` chỉ có sheet `Thiếu tiết` (mục 11.3); mã thoát 3.

---

## 8. Mục tiêu tối ưu

### 8.1. Dự toán và phân công (`tkb/phan_cong.py`, không dùng CP-SAT)

Viết bằng Python thuần, số nguyên, duyệt theo thứ tự cố định: mọi máy (Windows, Linux) ra cùng một phân công, dưới 1 giây.

1. **Dự toán:** luồng chi phí nhỏ nhất từ các lớp–môn ngoài phần GVCN sang các giáo viên được dạy. Mỗi giáo viên không nhận quá định mức (cộng mức bù) và không quá số ô giờ có thể dạy (ví dụ 26 với giáo viên không chủ nhiệm). Giá mỗi tiết:
   - không ai dạy: 1.000.000;
   - tiết bù: GVCN hợp đồng 100.000, GVCN khác 300.000, bộ môn hợp đồng 500.000, bộ môn khác 700.000; mỗi tiết bù sau của một người thêm 50.000 (các mức cách nhau 200.000 nên thứ tự đúng đến +4);
   - GV có `Lớp Đang Dạy` dạy khối không nằm trong các khối cũ: 60; đúng khối nhưng khác lớp cũ: 10 (`keep_grade`, `keep_class`);
   - GVCN bù: 3.000 × hạng môn (môn ưu tiên 0, rồi theo `HOMEROOM_FILL_ORDER`);
   - bộ môn dạy môn chuyên biệt: 1.000;
   - quản lý: dạy đúng số tiết.
   Luồng chi phí nhỏ nhất cho kết quả **tối ưu chính xác** với các giá trên.
2. **GVCN nhận tiết bù** ở lớp mình theo mục 7.2.
3. **Phần còn lại:** luồng lần 2 cho bộ môn, GV chuyên biệt, quản lý; rồi **tìm kiếm cục bộ** (chuyển, đổi chéo, gộp phần bị chia) giảm tổng:
   - chia một lớp–môn cho nhiều người: 5.000 mỗi người thêm;
   - bộ môn dạy môn chuyên biệt: 1.000 mỗi tiết;
   - giữ phân công cũ: 60 mỗi tiết khác khối cũ, 10 mỗi tiết đúng khối nhưng khác lớp cũ (lớn hơn mọi mục bên dưới);
   - chênh lệch phần định mức chưa dùng giữa người cùng chức vụ: 50;
   - gom lớp: 20 mỗi khối, 5 mỗi lớp một giáo viên dạy (`group_grade`, `group_class`);
   - phần lẻ của một người trong nhóm môn ghép cặp: 100.000 (`odd_pair_share`).

### 8.2. Bước xếp giờ: mục tiêu mềm

| Mục tiêu | Trọng số |
|---|---:|
| Tải ngày của giáo viên vượt mục tiêu. Mục tiêu ngày chia định mức theo tỷ lệ số slot của ngày | 100 / tiết vượt; thêm 300 nếu vượt quá mục tiêu + 1 |
| HĐTN tiết thứ ba cách cuối buổi | 200 / tiết cách |
| Môn nặng ở tiết 7 | 400 / tiết (`heavy_late`) |
| **Buổi sáng dành cho TV, Toán** (`MORNING_SUBJECTS`): mỗi tiết TV, Toán xếp vào buổi chiều | 300 / tiết (`morning_core`) |
| Toán tăng cường (`AFTERNOON_SUBJECTS`) xếp vào buổi sáng | 10 / tiết (`extra_morning`). TV tăng cường không có ở đây: nó ghép cặp với TV |
| Tiết tăng cường liền sau tiết chính cùng nhóm, cùng người dạy | thưởng 100 / tiết (`extra_after_main`) |
| Rải đều môn (trừ HĐTN): số tiết một môn trong ngày vượt ⌈số tiết/tuần ÷ 5⌉ | 40 / tiết vượt; **TV, Toán 120** (`core_spread`). Khối 1 có 7 cặp TV trong 5 ngày nên luôn có 2 ngày vượt |
| Tiết trống giữa buổi của giáo viên không chủ nhiệm | 10 / tiết trống |
| Giáo viên dạy sáng ở cơ sở này, chiều ở cơ sở kia (mục 4.1) | 3000 / (GV, ngày) (`campus_day_switch`) |

Các trọng số chọn qua thử nghiệm trên file của trường (lượng tính toán 480): với mọi luật cứng mới, TV/Toán buổi chiều 39 tiết (như trước khi có luật mới), môn nặng ở tiết 7: 7 tiết, vượt rải đều 19, tiết trống 1.

---

## 9. Quy trình giải

1. **Đọc và kiểm tra** đầu vào (mục 2).
2. **Phân GVCN** (mục 5) và tạo các lớp–môn còn lại, mỗi lớp–môn kèm danh sách giáo viên được dạy (mục 4).
3. **Bước 1 – Dự toán và phân công** (mục 8.1): in dự toán; chế độ bù giờ mà còn thiếu thì dừng, báo lỗi (mục 7.2).
4. **Tiết bù → người mới:** các tiết bù (và ở chế độ tuyển, tiết thiếu) giao cho người tuyển mới (mục 7.1).
5. **Bước 2 – Xếp giờ** với phân công cố định đó, tối ưu mục tiêu mềm ở mục 8.2 (`tkb/lns.py`):
   - **Khởi đầu:** CP-SAT trên toàn mô hình với 20% `THOI_GIAN_TOI_DA` nhưng không quá 120 (không giới hạn: 120). Nếu đã chứng minh tối ưu thì dừng (trường nhỏ của test).
   - **Mỗi vòng:** QA chấm chi phí mềm của từng lớp-ngày theo đúng trọng số mục 8.2 (phạt tải ngày, tiết trống, dạy cả hai cơ sở trong ngày của một giáo viên chia đều cho các lớp người đó dạy hôm ấy). Rồi xếp lại lần lượt các vùng, vùng xấu trước: từng lớp (tối đa 5) → 5 "điểm nóng" (lớp-ngày xấu nhất cùng các lớp chung giáo viên không chủ nhiệm hôm ấy, mở thêm ngày tốt nhất của lớp; 10) → nhóm lớp của một giáo viên dùng chung 2–8 lớp (15) → từng khối (20) → từng cặp ngày (30). Mỗi vùng: giữ nguyên mọi biến ngoài vùng, CP-SAT giải lại xuất phát từ nghiệm đang có, **chỉ nhận khi chi phí giảm**. Luật cứng luôn đúng vì vẫn giải trên toàn mô hình.
   - **Dừng:** hết `THOI_GIAN_TOI_DA`; một vòng giảm chưa tới 0,3% chi phí (không giới hạn: vòng không giảm); đủ 10 vòng; hoặc Ctrl+C (dừng sau vùng đang xếp).
   - Tham số trong `config.py`: `LNS_START_SHARE`, `LNS_START_MAX`, `LNS_REGION_LIMITS`, `LNS_HOTSPOTS`, `LNS_SHARED_CLASSES`, `LNS_MIN_GAIN`, `LNS_MAX_ROUNDS`.
   - Màn hình in "chi phí xếp giờ" (mục tiêu trừ phần của phân công, là hằng số) sau khởi đầu và sau mỗi vòng. Trạng thái là FEASIBLE: kết quả là tốt nhất tìm được (tối ưu cục bộ theo các vùng), không chứng minh tối ưu.

   Chế độ tuyển: giữ người mới. Chế độ bù giờ: trả các ô của người mới về đúng người bù. Hai chế độ cùng vị trí môn; mã kết quả khác nhau vì người dạy các ô bù khác nhau.
6. **Dự phòng** (chỉ chế độ tuyển): nếu bước 2 không xếp được, giải một lần CP-SAT mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ), cho phép thêm 1 người dự phòng mỗi chức vụ, rồi 3 người. Chế độ bù giờ thì báo lỗi.
7. **Kiểm tra độc lập** (mục 10) và xuất file (mục 11).

**Thời gian và tái lập:**
- `THOI_GIAN_TOI_DA` (mặc định 1200) là tổng lượng tính toán dành cho bước xếp giờ (khởi đầu và các vòng), tính xấp xỉ bằng giây; đếm theo thời gian tất định của CP-SAT. Các vùng nhỏ giải xong sớm nên 1200 đơn vị chạy khoảng 9 phút trên Linux, 11–13 phút trên Windows (Wine; máy ảo CI 2 nhân: 13 phút); 600: khoảng 4–6 phút. Bước dự toán và phân công không dùng CP-SAT, xong ngay.
- **So sánh trên file của trường bản trước, chưa có hai cơ sở (Linux, chi phí xếp giờ, càng thấp càng tốt):** một lần CP-SAT 480: 21.590 (8 phút); một lần CP-SAT không giới hạn dừng sau 110 phút: 18.270 (cận dưới 14.210); khởi đầu + xếp lại 600: 17.260 (khoảng 4,5 phút); **1200: 17.200** (khoảng 9 phút), bằng chế độ không giới hạn. Windows: cách cũ 20.850; 600: 18.030 (khoảng 4 phút trên máy ảo CI); **1200: 17.260** (3 vòng, khoảng 11,5 phút trên Wine, 13 phút trên máy ảo CI; 4 máy cùng mã `6D35-AD5A-3ABA`), bằng chế độ không giới hạn (4 vòng, khoảng 16 phút trên Wine). Trường mẫu tên giả: cách cũ 20.550, 600: 17.360, **1200: 17.050**, bằng chế độ không giới hạn.
- **File hiện tại (hai cơ sở, thai sản, buổi nghỉ, phạt dạy cả hai cơ sở trong ngày; mục 4.1; 44 nhân sự, bù tối đa +3), 1200:** Linux khởi đầu 91.120, các vòng 32.300 → 24.680 → 24.320 (khoảng 10–11 phút); Windows 92.540 → 32.780 → 24.140 (khoảng 13 phút trên máy ảo CI). Cả hai còn 1 lần giáo viên dạy sáng một cơ sở, chiều cơ sở kia (3.000 trong chi phí). Không tính phần phạt đó: 21.320 / 21.140, so với 17.200 / 17.260 khi chưa có các luật của mục 4.1. Môn nặng ở tiết 7: 6 tiết (Linux), 7 tiết (Windows); TV/Toán buổi chiều: 38/408 (Linux), 36/408 (Windows).
- **Vì sao khởi đầu tối đa 120:** khởi đầu dài hơn cho điểm xuất phát tốt hơn (file của trường, khởi đầu 240: khoảng 23.000 thay vì 28.000–30.000) nhưng các vòng xếp lại kéo về gần như cùng mức. Với 1200, khởi đầu 120 cho 17.200 / 17.260 (Linux / Windows), khởi đầu 240 cho 17.580 / 17.150: khởi đầu 120 có trường hợp xấu nhất tốt hơn và có TKB tốt sớm hơn (khi bấm Ctrl+C giữa chừng).
- **Không giới hạn** (`THOI_GIAN_TOI_DA` để trống hoặc 0, dòng lệnh `--time-limit 0`): khởi đầu 120, rồi xếp lại đến khi một vòng không còn giảm; tự dừng và vẫn tái lập. Bấm **Ctrl+C** thì dừng sau vùng đang xếp (vài giây), giữ TKB tốt nhất, kiểm tra luật và ghi đủ các file ra như bình thường; dừng bằng tay thì không tái lập.
- **[Cứng] Tái lập giữa các lần chạy và giữa các máy cùng hệ điều hành:** khi `CHAY_TAI_LAP_DUOC = True` và không bấm Ctrl+C, chạy lại bao nhiêu lần, trên máy nào cùng hệ điều hành cũng ra **cùng một TKB**, ở **cả chế độ tuyển thêm lẫn bù giờ**, miễn là giữ nguyên:
  - file vào (và file chương trình học riêng nếu có);
  - các hằng số trong `main.py`: `CHE_DO`, `SO_TIET_BU_TOI_DA`, `LUAT_HOC_SINH`, `THOI_GIAN_TOI_DA`, `CHAY_TAI_LAP_DUOC`, `SO_LUONG`;
  - phiên bản thư viện đã ghim trong `requirements.txt` (OR-Tools 9.15.6755, openpyxl 3.1.5). Nếu OR-Tools khác bản đã ghim, chương trình in cảnh báo.
- **Không ảnh hưởng kết quả:**
  - Máy nhanh hay chậm, số nhân CPU, máy đang bận hay rảnh: bộ giải dừng theo **lượng tính toán**, không theo giây thực. Chế độ tái lập **không có giới hạn giây thực**, nên máy chậm chỉ chạy lâu hơn chứ không dừng sớm.
  - Phiên bản Python (đã thử 3.10 đến 3.14), thư mục chạy, thứ tự băm của Python.
  - Thứ tự dựng mô hình cố định, không phụ thuộc thứ tự lặp của `set`. Thứ tự các vùng xếp lại cố định (điểm QA, hòa thì theo tên lớp, số ngày); ngân sách của mỗi lần xếp lại cũng tính theo thời gian tất định.
- **Tham số bộ giải ở chế độ tái lập** (`_configure` trong `tkb/solver.py`): `interleave_search` (các luồng chạy xen kẽ theo thứ tự cố định), dừng theo `max_deterministic_time`, và **tắt chia sẻ giữa các luồng** (`share_binary_clauses`, kéo theo `share_glue_clauses`, và `share_level_zero_bounds`). Phần chia sẻ này của OR-Tools 9.15 không tất định: đo trên dữ liệu mẫu, cùng một mô hình giải 6 lần ra 3 TKB khác nhau, lệch từ khoảng 60–120 đơn vị tính toán trở đi. Tắt đi thì chạy lặp 8 lần (có lúc 2 tiến trình song song) ra 8 lần cùng mã, chất lượng không giảm.
- **Mã kết quả:** mã băm của toàn bộ TKB (lớp, ngày, tiết, môn, giáo viên), in ra màn hình. Cùng mã là cùng TKB. Với các hằng số mặc định của `main.py` (file của trường `data/INPUT_V8.xlsx` hiện tại), mã trên Linux là **`3D43-752C-E1B3`**, trên Windows là **`801B-0289-6F38`** (máy ảo Windows Server 2022/2025, Python 3.12/3.14). Trường mẫu tên giả của test (`tests/du_lieu_mau.py`) cho `428A-3655-C110` trên Linux.
- **Theo hệ điều hành:** phân công (mục 8.1) giống nhau trên mọi máy. Bước xếp giờ: OR-Tools bản Windows và bản Linux ra TKB khác nhau (cùng đạt luật, cùng phân công), vì bản dựng khác trình biên dịch và phép tính số thực. `.github/workflows/windows.yml` kiểm mỗi lần đổi code: 4 máy ảo Windows (Windows Server 2022 và 2025, Python 3.12 và 3.14) chạy `main.py` với các hằng số mặc định, mỗi máy 2 lần, mọi mã phải trùng nhau; chỉ mã kết quả được tải lên, không tải file ra. Chưa thử macOS, chip ARM.
- Đổi một trong các điều kiện trên thì TKB ra khác, nhưng vẫn đúng luật.
- `tests/test_reproducible.py` kiểm tra:
  - chạy trong hai tiến trình Python riêng, thứ tự băm khác nhau, và so sánh kết quả (`tests/test_lns.py` làm tương tự với trường mẫu, có qua các vòng xếp lại);
  - mã kết quả tham chiếu của trường nhỏ ở cả hai chế độ (chạy test này trên máy khác để kiểm máy đó);
  - OR-Tools đúng bản đã ghim;
  - không có giới hạn giây thực.

---

## 10. Kiểm tra độc lập (sau khi giải)

`tkb/checker.py` kiểm tra lại TKB mà không dựa vào mô hình giải:

1. Mỗi lớp, mỗi slot có đúng 1 tiết. Mỗi lớp đủ số tiết từng môn.
2. Không giáo viên nào dạy 2 lớp cùng lúc.
3. Không ai vượt định mức, cộng mức bù được phép. Quản lý dạy đúng số tiết.
4. Quyền dạy đúng mục 4.
5. Tiết 1 buổi sáng do đúng GVCN của lớp dạy.
6. GVCN dạy đủ phần được phân. Phần dạy thêm chỉ là tiết bù hợp lệ: đúng lớp mình, không phải môn chuyên biệt, không quá mức bù.
7. GVCN được ưu tiên bù lớp mình: bộ môn không dạy bù ở lớp mà GVCN còn được bù và dạy được môn đó.
8. HĐTN đúng 2 slot cố định; tiết thứ ba nằm trong Thứ 3–Thứ 5.
9. Hai tiết liền nhau cùng nhóm môn do 1 người dạy; nhóm môn ưu tiên: người khác không dạy trước tiết GVCN đầu tuần (mục 5.7).
10. Nếu bật luật học sinh: mỗi nhóm môn tối đa 2 tiết mỗi buổi; Toán tối đa 1 tiết mỗi ngày; nhóm ghép cặp mỗi buổi 0 hoặc 2 tiết liền; môn có từ 2 tiết trong buổi học liền nhau.
11. Mục 4.1: mỗi GV mỗi buổi chỉ một cơ sở; GV thai sản hoặc chỉ-cơ-sở-2 không dạy lớp cơ sở 1 (và thai sản không bù, qua mục 3); buổi nghỉ cố định không có tiết; đủ số buổi trống đã xin.

Kết quả (**ĐẠT** / **KHÔNG ĐẠT** kèm danh sách lỗi) in ra màn hình.

---

## 11. Đầu ra

Bốn file, ghi vào `THU_MUC_OUT` (chế độ bù giờ mà thiếu tiết: chỉ `Thong_Ke.xlsx` với sheet `Thiếu tiết`):

| File | Nội dung |
|---|---|
| `TKB.xlsx` | **Chỉ thời khóa biểu**: các sheet Khối (mục 11.1). Trường có lớp ở cơ sở 2: tách thành `TKB_diem_chinh.xlsx` (lớp cơ sở 1) và `TKB_diem_phu.xlsx` (lớp cơ sở 2) |
| `TKB_chuc_vu.xlsx` | Cùng TKB, mỗi ô thêm dòng thứ 3 là chức vụ (Mã GV), để theo dõi ai dạy tiết nào. Hai cơ sở: tách như `TKB.xlsx` |
| `Thong_Ke.xlsx` | Một bảng: số tiết từng môn của mỗi giáo viên (mục 11.3) |
| `<tên file vào>_cap_nhat.xlsx` | File vào cập nhật, dùng lại làm file vào lần sau (mục 11.2) |

### 11.1. `TKB.xlsx`

Chỉ gồm **các sheet `Khối 1` … `Khối 5`**, bố cục như mẫu `data/Output_Template_TKB_V8.xlsx`:
- Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
  - Cột LỚP gộp 7 hàng (`LỚP 1/1`). Lớp ở cơ sở 2 ghi thêm `(CƠ SỞ 2)`, ví dụ `LỚP 3D23 (CƠ SỞ 2)`.
  - Cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 5–7); cột TIẾT ghi số tiết trong ngày.
  - Giữa hai lớp có 2 dòng trống.
- Mỗi ô ghi **môn** và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Chiều Thứ 6 ghi `Nghỉ`.
  - Tên để trống hoặc người cần tuyển: ghi **Mã GV**, ví dụ `Chủ Nhiệm 1/1`, `Bộ Môn 6`.
  - Hai giáo viên trùng tên thì kèm Mã GV, ví dụ `Lan (Bộ Môn 1)`.
  - Các cột ngày ở mọi sheet cùng độ rộng, nới theo dòng dài nhất của cả trường, tối đa 30 (đơn vị cột Excel). Tên dài hơn thì xuống dòng và hàng tự cao thêm.
- Tên môn in như trong file vào; viết tắt: `HĐTN`, `TNXH`, `TV tăng cường`.
- Khi in: khổ ngang, co vừa chiều rộng 1 trang.

**Style của mọi file ra** (`TKB.xlsx`, `Thong_Ke.xlsx`, file vào cập nhật): chép từ sheet NHÂN SỰ của file vào, không cố định trong code:
- Ô tiêu đề (dòng tiêu đề, cột Chức Vụ): phông, cỡ chữ, in đậm, viền, căn lề, nền.
- Ô dữ liệu (dòng đầu tiên, cột Chức Vụ): phông, cỡ chữ, viền, căn lề.
- Chiều cao dòng: của dòng dữ liệu đầu tiên, làm tròn (24,95 → **25**); file vào không đặt thì 25.
- Bảng ghi tiêu đề cột ở dòng 1 như file vào. Riêng hàng tiết trong TKB cao đủ 2 dòng chữ (môn và giáo viên), theo cỡ chữ của file vào.

### 11.2. File vào cập nhật `<tên file vào>_cap_nhat.xlsx`

- Là bản chép của file vào (đủ các sheet), sheet NHÂN SỰ có thêm các dòng người bổ sung `chưa có` ở cuối với **định mức tuyển đầy đủ** (Chức Vụ ghi không kèm số, ví dụ `Bộ Môn`; STT điền tiếp nếu có). Dòng mới **chép style của dòng trên**.
- Bên phải thêm các cột **Mã GV**, **Số Tiết Thực Dạy**, (chế độ bù giờ) **Số Tiết Bù** và **Số Tiết Dư** (định mức − thực dạy, để trống khi dạy đủ), cùng style với file. Chạy lại trên file này thì các cột được ghi đè, không thêm mới.
- **Thống kê gọn theo mẫu file vào:** tô nền cả dòng (đến cột tiêu đề cuối) người dạy bù (vàng, như file thống kê), người cần tuyển (xanh lá), người còn dư tiết (xanh dương); ô tiêu đề Số Tiết Dư có ghi chú giải thích các màu. Không ghi chú thích dưới bảng, để file vẫn đọc lại được. Chạy lại trên file này thì màu cũ của chương trình được bỏ trước khi tô.
- Giữ nguyên danh sách thả xuống của file mẫu.
- Dùng làm đầu vào cho lần chạy sau được (các cột thêm được bỏ qua khi đọc). File gốc không bị sửa.

### 11.3. File thống kê `Thong_Ke.xlsx`

Chỉ một sheet **`Thống kê`** (mẫu `data/Output_Template_Thong_Ke_V8.xlsx`), style theo file vào, tiêu đề cột ở dòng 1; cột tên, chức vụ và dòng tiêu đề cố định khi cuộn:

| Cột | Nội dung |
|---|---|
| Họ và Tên | Tên như file nhân sự; người cần tuyển ghi **`tuyển thêm`** |
| Chức Vụ | Mã GV, ví dụ `Chủ Nhiệm 1/1`, `Bộ Môn 2`, `Tiếng Anh 1` |
| Một cột mỗi môn | Số tiết môn đó người này dạy trong tuần; ô trống là không dạy. Chỉ có cột cho các môn có người dạy, theo thứ tự trong chương trình học, tên môn như trong TKB |
| Tổng Tiết | Tổng số tiết người này dạy (kể cả tiết bù ở chế độ bù giờ) |

- Mỗi giáo viên một dòng, theo thứ tự file nhân sự, rồi đến người cần tuyển. Cuối bảng có dòng **Tổng** (tổng từng môn và tổng tiết toàn trường).
- **Tô nền cả dòng:** chế độ bù giờ tô **vàng** (`FFEB9C`) dòng người dạy bù (tổng tiết vượt định mức); chế độ tuyển thêm tô **xanh lá** (`C6EFCE`) dòng người cần tuyển. Trong dòng người dạy bù, **ô môn có tiết bù tô cam** (`F4B183`), kèm ghi chú (comment) `Dạy bù <n> tiết <môn>`: đó đúng là các tiết mà chế độ tuyển thêm giao cho người mới. Dưới bảng, cách một dòng, có chú thích: ô màu và dòng chữ `Dạy bù (vượt định mức): <số người> người, <số tiết bù> tiết`, `Môn có tiết dạy bù: <số ô> ô, <số tiết> tiết` hoặc `Cần tuyển thêm: <số người> người, <số tiết> tiết`. Không ai bù, không ai tuyển thì không tô, không chú thích.
- Chế độ, dự toán, mã kết quả, kết quả kiểm tra luật, người cần tuyển (số tiết thiếu), dạy bù và cảnh báo **chỉ in ra màn hình** (mục 11.4).
- **Chế độ bù giờ mà thiếu tiết** (mục 7.2): file chỉ có sheet **`Thiếu tiết`**: **Lớp | Môn | Số Tiết Thiếu | Lý Do**, cuối bảng dòng Tổng.

### 11.4. Màn hình và mã thoát

- Màn hình in: các bước giải, **dự toán và biên bù**, cảnh báo, kết quả kiểm tra luật, **mã kết quả**, người cần bổ sung, tiết dạy bù (tổng, theo GVCN/bộ môn, số người +2/+1), số tiết môn nặng ở tiết 7, số tiết TV/Toán buổi chiều, lỗi kiểm tra.
- Khi file vào có dùng các cột mục 4.1, 8.1 thì in thêm: số lớp ở cơ sở 2 và số GV dạy ở cả hai cơ sở; người thai sản và số tiết; người có buổi nghỉ; số tiết đúng khối cũ, đúng lớp cũ của các GV có `Lớp Đang Dạy`.
- Mã thoát:
  - `0`: thành công (kể cả khi dừng sớm bằng Ctrl+C ở chế độ không giới hạn thời gian).
  - `1`: lỗi đầu vào, hoặc không xếp được.
  - `2`: đã xuất file nhưng kiểm tra luật **không đạt**.
  - `3`: chế độ bù giờ thiếu tiết (không ra TKB, chỉ có bảng tiết thiếu).

---

## 12. Cấu hình

### 12.1. `main.py` (sửa rồi bấm Run)

| Hằng số | Ý nghĩa | Mặc định |
|---|---|---|
| `FILE_VAO` | **Địa chỉ file vào** (sheet NHÂN SỰ + CHƯƠNG TRÌNH HỌC), tương đối theo `main.py`. Để trống thì báo lỗi | `data/INPUT_V8.xlsx` (file của trường) |
| `THU_MUC_OUT` | Thư mục ra. **Để trống thì ghi vào thư mục dự án** (thư mục chứa `main.py`); các file ra ở đó được `.gitignore` bỏ qua | `""` |
| `CHE_DO` | `bu_gio` hoặc `tuyen_them` (cùng TKB, mục 7) | `bu_gio` |
| `SO_TIET_BU_TOI_DA` | Mức bù tối đa mỗi người; chế độ tuyển: người mới nhận các tiết bù này | `3` (file của trường với 2 thì thiếu 17 tiết) |
| `LUAT_HOC_SINH` | Áp dụng luật học sinh (mục 6) | `True` |
| `THOI_GIAN_TOI_DA` | Tổng lượng tính toán cho bước xếp giờ (≈ giây): khởi đầu và các vòng xếp lại (mục 9). **Để trống hoặc 0 thì không giới hạn**: xếp lại đến khi một vòng không còn cải thiện; Ctrl+C dừng sớm và vẫn ghi TKB tốt nhất | `1200` |
| `CHAY_TAI_LAP_DUOC` | Cùng dữ liệu luôn ra cùng một kết quả | `True` |
| `FILE_TKB`, `FILE_TKB_CHUC_VU`, `FILE_THONG_KE` | Tên file TKB, TKB có chức vụ, file thống kê số tiết từng môn của giáo viên | `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `Thong_Ke.xlsx` |
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
| `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, `SUBJECT_GROUPS`, `SESSION_GROUP_LIMIT`, `DAILY_LIMITS`, `PAIR_MIN_LESSONS`, `PAIR_EXCLUDED` | Luật học sinh, nhóm môn, ghép cặp (mục 6) |
| `MORNING_SUBJECTS`, `AFTERNOON_SUBJECTS` | Môn ưu tiên buổi sáng (TV, Toán) và môn tăng cường ưu tiên buổi chiều (Toán tăng cường) (mục 8.2) |
| `SUPPLEMENT_NAME` | Tên người bổ sung (mục 7.1) |
| `ROLE_LABELS` | Cách ghi ba chức vụ Chủ Nhiệm, Bộ Môn, Quản Lý trong file ra |
| `OVERTIME_ROLES`, `OVERTIME_MAX` | Bù giờ (mục 7.2); thứ tự bù có hợp đồng trong `Weights.overtime_*` |
| `Weights` | Trọng số mục tiêu (mục 8), gồm `keep_grade`, `keep_class` (giữ phân công cũ) |
| `LNS_START_SHARE`, `LNS_START_MAX`, `LNS_REGION_LIMITS`, `LNS_HOTSPOTS`, `LNS_SHARED_CLASSES`, `LNS_MIN_GAIN`, `LNS_MAX_ROUNDS` | Bước xếp giờ: phần khởi đầu, giới hạn mỗi loại vùng, điều kiện dừng (mục 9) |
| `Settings` | Tham số chạy mặc định (thời gian 1200, tái lập, số luồng, mức bù) |

---

## 13. Kết quả tham chiếu với dữ liệu mẫu

**Nhân sự** (trường mẫu tên giả của test, `tests/du_lieu_mau.py`): 45 người, gồm:
- 29 GVCN, ứng với 29 lớp: khối 1–4 mỗi khối 6 lớp, khối 5 có 5 lớp.
- 5 bộ môn, 4 tiếng anh, 3 thể dục, 1 âm nhạc, 1 mỹ thuật, 1 tin học, 1 quản lý.
- 2 người có định mức thấp hơn người cùng chức vụ: `Chủ Nhiệm 5/5` (16 tiết) và `Bộ Môn 5` (19 tiết).

**Nhu cầu so với năng lực** (ngoài phần GVCN):

| Nhóm | Nhu cầu | Năng lực | Ghi chú |
|---|---:|---:|---|
| Tiếng Anh | 92 | 92 | Đủ |
| Thể dục | 58 | 69 | Dư 11 |
| Tin học | 17 | 23 | Dư 6 |
| Âm nhạc / Mỹ thuật | 29 / 29 | 23 / 23 | Mỗi môn 6 tiết chuyển cho bộ môn |
| Bộ môn | 163 | 111 | **Thiếu 52**. Nhu cầu gồm TV 38, TNXH 36, KNS 25 (29 trừ 4 của quản lý), Toán TC 23, Công nghệ 17, TV TC 12, cộng 12 tiết Âm nhạc/Mỹ thuật |

**Kết quả** (hằng số mặc định của `main.py`: chế độ tái lập, 1200, 8 luồng; kiểm tra luật **ĐẠT**):

| Chế độ | Kết quả |
|---|---|
| Dự toán | `Bù: 52/68 tiết (GVCN 52/58, bộ môn 0/10), còn dư 16 tiết`, không thiếu tiết |
| Bù giờ (+2) | **Không phải tuyển.** Bù 52 tiết, toàn bộ do GVCN, kể cả GVCN 5/5 chỉ có 16 tiết (29 người: 23 người +2, 6 người +1). Bộ môn không phải bù. Mã Linux `428A-3655-C110` |
| Tuyển thêm | Tuyển `Bộ Môn 6`, `Bộ Môn 7`, `Bộ Môn 8` (định mức 23; thực dạy 18/18/16 = 52 tiết bù). Cùng TKB với chế độ bù, người mới đứng đúng các ô bù |
| Cả hai | 145/145 ô tiết 1 buổi sáng là GVCN của lớp. Môn nặng ở tiết 7: 4 tiết. TV/Toán buổi chiều: 37/408 tiết. Chi phí xếp giờ: khởi đầu 30.510, các vòng 17.360 → 17.260 → 17.050, khoảng 9 phút (một lần CP-SAT 480 trước đây: 20.550; 600: 17.360) |

Số tiết thiếu và số tiết bù do luồng chi phí nhỏ nhất tính, nên là **nhỏ nhất**. Phần gom lớp (mục 8.1) dùng tìm kiếm cục bộ nên chỉ là tốt, không chứng minh tối ưu.

Với file của trường (`data/INPUT_V8.xlsx` hiện tại, 44 nhân sự, `main.py` bù tối đa +3, Linux): bù 79 tiết (23 GVCN +3, 5 GVCN +2), hoặc tuyển 4 bộ môn (thực dạy 21/20/19/19; mã chế độ tuyển `341B-5182-8FB9`). Hai TKB giống nhau từng ô, trừ đúng 79 ô bù. File vào cập nhật: 4 người còn dư tiết (Thể dục 1–3, Tin học 1: tổng 17 tiết; GV chuyên biệt chỉ dạy môn mình nên không đỡ được phần bù).

---

## 14. Giả định và hạn chế đã biết

1. **Tiết 1 buổi sáng thuộc GVCN** làm giáo viên không chủ nhiệm chỉ còn 26 slot/tuần. Giáo viên có định mức trên 26 sẽ bị phát hiện ngay ở bước phân công và cần người bổ sung hoặc bù.
2. **Không có chế độ thai sản hay giảm tiết riêng.** Người được giảm tiết ghi Số Tiết/Tuần đã giảm; khi thay đổi thì sửa Số Tiết/Tuần rồi chạy lại.
3. **Người được bù +1 thay vì +2**, lớp nào quản lý dạy KNS, và cách chia các tiết cùng chi phí là do chương trình chọn. Các phương án này tương đương nhau theo mục tiêu. Đổi dữ liệu hoặc `SO_LUONG` có thể làm đổi lựa chọn.
4. **Bước xếp giờ** chỉ bảo đảm TKB hợp lệ và tốt trong thời gian cho phép (trạng thái FEASIBLE). Kết quả là tốt nhất tìm được: không vùng nào xếp lại được tốt hơn (tối ưu cục bộ), không chứng minh là tốt nhất, kể cả ở chế độ không giới hạn. Với file của trường bản trước (chưa có hai cơ sở), chi phí xếp giờ 17.260 so với cận dưới 14.210 mà CP-SAT chứng minh được: còn cách tối ưu nhiều nhất khoảng 18%, trong đó phần lớn TV/Toán buổi chiều của khối 1 là bắt buộc theo luật cứng (mục 6).
5. **Người bổ sung** được ghi theo định mức tuyển đầy đủ, dù có thể dạy ít hơn (ví dụ `Bộ Môn 8` của trường mẫu ghi 23, thực dạy 16).
6. **"Kỹ năng số"** trong yêu cầu ban đầu được hiểu là **Kỹ năng sống**, vì chương trình không có môn Kỹ năng số.
7. **Số thứ tự tự đánh theo thứ tự dòng:** đổi thứ tự các dòng cùng chức vụ thì Mã GV (ví dụ `Bộ Môn 2`) đổi theo. Khi cột tên để trống, hãy dùng cột Mã GV trong file cập nhật để biết ai là ai.
8. **Tên môn phải khớp luật:** môn viết khác hẳn tên trong config (ví dụ `TV` thay cho `Tiếng Việt`) sẽ không nhận luật của môn đó; chương trình cảnh báo khi luật nhắc môn không có trong file.
