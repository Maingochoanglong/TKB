# Xếp thời khóa biểu tự động (TKB)

Chương trình Python đọc **một file Excel** (danh sách nhân sự và chương trình học của trường) và xếp
thời khóa biểu tuần cho toàn trường bằng OR-Tools CP-SAT. Trước khi xếp, chương trình **dự toán** số tiết
thiếu, số tiết bù của từng người, số người cần tuyển và in ra màn hình. Khi trường thiếu người, có hai chế độ,
**dùng chung một TKB**:

- **Bù giờ** (`bu_gio`): GVCN và bộ môn dạy bù vượt định mức, mỗi người tối đa 2 tiết/tuần. Bù hết mức vẫn
  thiếu thì **báo lỗi**, không ra TKB, và ghi bảng tiết thiếu vào `Thong_Ke.xlsx`.
- **Tuyển thêm** (`tuyen_them`): thêm giáo viên mới tên "chưa có" (ví dụ `chưa có | Bộ Môn | 23`, Mã GV
  `Bộ Môn 6`). **Người mới dạy đúng các ô mà ở chế độ bù là tiết bù** (và các tiết còn thiếu), mọi ô khác giữ
  nguyên.

Đặc tả nghiệp vụ chi tiết: [`docs/Dac_Ta_Nghiep_Vu_TKB_V16.md`](docs/Dac_Ta_Nghiep_Vu_TKB_V16.md).

## Cài đặt và chạy

Cài thư viện (một lần):

```bash
pip install -r requirements.txt
```

### Cách 1 — bấm nút Run trong `main.py` (dễ nhất)

1. Mở `main.py` và sửa các hằng số ở đầu file:

| Hằng số | Ý nghĩa | Mặc định |
|---|---|---|
| `FILE_VAO` | **Địa chỉ file vào** (mẫu V8: sheet `NHÂN SỰ` và `CHƯƠNG TRÌNH HỌC`) | `data/INPUT_V8.xlsx` (file của trường) |
| `THU_MUC_OUT` | Thư mục ghi kết quả; tự tạo nếu chưa có. **Để trống `""` thì ghi vào thư mục dự án** (thư mục chứa `main.py`) | `""` |
| `CHE_DO` | Khi thiếu người: `"bu_gio"` (GVCN/bộ môn dạy bù; không đủ thì báo lỗi) hoặc `"tuyen_them"` (thêm GV "chưa có" dạy các ô bù) | `"bu_gio"` |
| `SO_TIET_BU_TOI_DA` | Số tiết bù tối đa mỗi GVCN/bộ môn mỗi tuần; chế độ tuyển: người mới nhận đúng các tiết bù này | `2` |
| `LUAT_HOC_SINH` | Áp dụng luật bảo vệ học sinh | `True` |
| `THOI_GIAN_TOI_DA` | Thời gian cho bước xếp giờ, xấp xỉ giây; tăng lên để TKB đẹp hơn. **Để trống (`None`/`""`) hoặc `0` thì không giới hạn**: chạy đến khi bộ giải chứng minh TKB tốt nhất (có thể hàng giờ); bấm Ctrl+C để dừng sớm, TKB tốt nhất đã tìm được vẫn được ghi ra | `480` (≈ 4–5 phút) |
| `CHAY_TAI_LAP_DUOC` | `True`: chạy lại bao nhiêu lần, trên máy nào cùng hệ điều hành cũng ra đúng một kết quả, ở cả hai chế độ (xem điều kiện bên dưới); `False`: dừng theo giây thực, mỗi lần có thể khác | `True` |
| `FILE_TKB`, `FILE_TKB_CHUC_VU`, `FILE_THONG_KE` | Tên file TKB (chỉ thời khóa biểu), TKB ghi thêm chức vụ (Mã GV) trong mỗi ô, và file thống kê số tiết từng môn của giáo viên | `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `Thong_Ke.xlsx` |
| `SO_LUONG` | Số luồng tìm kiếm song song của bộ giải; nên ≥ số nhân CPU. Đổi số này thì TKB ra khác (vẫn đúng luật) | `8` |

   - Đường dẫn tương đối được tính từ thư mục chứa `main.py`.
   - **Chạy lại, hoặc chạy ở máy khác cùng hệ điều hành, ra đúng TKB cũ** khi `CHAY_TAI_LAP_DUOC = True` và giữ nguyên: file vào, các hằng số trong `main.py`, phiên bản thư viện (cài bằng `pip install -r requirements.txt`). Xem mục [Chạy trên máy khác](#chạy-trên-máy-khác).
   - **Không giới hạn thời gian** (`THOI_GIAN_TOI_DA` để trống hoặc `0`): bước dự toán và phân công không dùng CP-SAT, xong ngay; bước xếp giờ chạy đến khi chứng minh TKB tốt nhất, với trường cỡ 29 lớp gần như không tự dừng. Bấm **Ctrl+C** để dừng, chương trình vẫn kiểm tra luật và ghi đủ các file ra. Dừng bằng tay thì mỗi lần có thể ra TKB khác nhau.
   - Trên Windows, viết đường dẫn dạng `r"C:\Users\ten\TKB\input.xlsx"` hoặc `"C:/Users/ten/TKB/input.xlsx"`.
2. Bấm **Run ▶** (VS Code, PyCharm...) hoặc chạy `python main.py`.
3. Kết quả nằm trong `THU_MUC_OUT`: `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `Thong_Ke.xlsx` và `<tên file vào>_cap_nhat.xlsx`. Khi ghi ra thư mục dự án, các file này đã được `.gitignore` bỏ qua để không lỡ đưa tên giáo viên lên git. Chế độ bù giờ mà thiếu tiết thì chỉ có `Thong_Ke.xlsx` (bảng tiết thiếu) và `main.py` trả về mã 3.

### Cách 2 — dòng lệnh

```bash
python -m tkb data/INPUT_V8.xlsx -o out/TKB.xlsx
```

Tuỳ chọn:

| Tham số | Ý nghĩa |
|---|---|
| `-o, --output` | File TKB xuất ra, chỉ gồm các sheet Khối (mặc định `out/TKB.xlsx`) |
| `--staff-out` | File nhân sự cập nhật (mặc định `<thư mục output>/<tên input>_cap_nhat.xlsx`) |
| `--stats-out` | File thống kê số tiết từng môn của mỗi giáo viên; chế độ bù giờ mà thiếu tiết thì là bảng tiết thiếu (mặc định `<thư mục output>/Thong_Ke.xlsx`) |
| `--roles-out` | File TKB ghi thêm chức vụ (Mã GV) trong mỗi ô (mặc định `<thư mục output>/TKB_chuc_vu.xlsx`) |
| `--time-limit` | Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 480; `0` = không giới hạn, Ctrl+C để dừng) |
| `--non-reproducible` | Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau |
| `--mode` | `tuyen_them` (mặc định) hoặc `bu_gio` |
| `--max-overtime` | Số tiết bù tối đa mỗi người; chế độ tuyển: người mới nhận các tiết bù này (mặc định 2) |
| `--no-student-rules` | Tắt luật bảo vệ học sinh (dùng để tìm nguyên nhân khi không xếp được) |

Mã thoát: `0` đạt; `1` lỗi file vào hoặc không xếp được; `2` TKB sai luật bắt buộc; `3` chế độ bù giờ thiếu tiết.

Chạy test: `python -m pytest -q`

## Chạy trên máy khác

Ở chế độ tái lập (`CHAY_TAI_LAP_DUOC = True` và `THOI_GIAN_TOI_DA` có giá trị), cùng file vào và cùng các hằng số trong `main.py` thì **chạy lại bao nhiêu lần, trên máy nào cùng hệ điều hành cũng ra cùng một TKB**, với điều kiện:

1. Cài đúng phiên bản thư viện: `pip install -r requirements.txt` (OR-Tools 9.15.6755, openpyxl 3.1.5). Nếu OR-Tools khác bản này, chương trình in cảnh báo.
2. Không sửa code trong `tkb/`.

**Không ảnh hưởng kết quả:** máy nhanh hay chậm, số nhân CPU, máy đang bận, phiên bản Python (đã thử 3.10–3.14), thư mục đặt dự án. Bộ giải dừng theo lượng tính toán chứ không theo giây thực, nên máy chậm chỉ chạy lâu hơn.

**Mã kết quả:** mỗi lần chạy in ra màn hình một mã, ví dụ `Mã kết quả: 6523-7A90-932C`. Mã này là mã băm của toàn bộ TKB. Hai máy cùng mã là cùng TKB, khỏi phải so từng ô.

**Theo hệ điều hành:** bước dự toán và phân công viết bằng Python thuần nên mọi máy ra cùng một phân công. Bước xếp giờ dùng OR-Tools: bản Windows và bản Linux ra TKB khác nhau (cùng đạt luật, cùng phân công), nên mỗi hệ điều hành có mã tham chiếu riêng. Chưa thử macOS và chip ARM (Apple M1).

**Kiểm tra một máy mới** (không cần sửa `main.py`):
- Nhanh (khoảng 20 giây): `python -m pytest tests/test_reproducible.py`. Test so mã kết quả của một trường nhỏ với mã tham chiếu của hệ điều hành đó. Qua là máy đó ra đúng kết quả như các máy khác.
- Đầy đủ (vài phút): `python main.py` với các hằng số mặc định (file của trường `data/INPUT_V8.xlsx`), rồi so mã kết quả với bảng. Mã trong bảng ứng với file `data/INPUT_V8.xlsx` hiện tại; trường sửa file thì mã đổi theo.

| Hệ điều hành | Mã kết quả `data/INPUT_V8.xlsx` | Đã kiểm |
|---|---|---|
| Windows x86-64 | **`50A0-9EFB-4877`** | Máy ảo GitHub Actions: Windows Server 2022 và 2025, Python 3.12 và 3.14 |
| Linux x86-64 | **`BA73-927C-79DB`** | Python 3.11 |

**Đã sửa lỗi "thỉnh thoảng ra TKB khác":** trước đây, dù đã bật chế độ tất định của OR-Tools, chạy lặp cùng một mô hình vẫn có lúc ra TKB khác (6 lần ra 3 TKB). Nguyên nhân là các luồng của bộ giải chia sẻ mệnh đề học được và cận ở mức gốc cho nhau, và phần này không tất định. Chế độ tái lập nay tắt hai loại chia sẻ đó (`tkb/solver.py`, hàm `_configure`): chạy lặp 8 lần ra 8 lần cùng mã, chất lượng không giảm. Máy ảo Windows của GitHub Actions kiểm tra việc này mỗi lần đổi code (`.github/workflows/windows.yml`): 4 máy (Windows Server 2022 và 2025, Python 3.12 và 3.14), mỗi máy chạy 2 lần, mọi mã phải trùng nhau.

## Đầu vào

**Một file Excel duy nhất theo mẫu V8** (ví dụ `data/INPUT_V8.xlsx`) gồm 2 sheet. Chương trình tìm sheet theo tên, không phân biệt hoa thường. Tiêu đề cột phải đúng mẫu: `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần`.

**Sheet `NHÂN SỰ`:**

| Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần |
|---|---|---|---|
| Nguyễn Văn A | Chủ Nhiệm | 1/1 | 19 |
| Trần Thị B | Chủ Nhiệm | 5/5 | 16 |
| Lê Văn C | Bộ Môn | | 19 |
| Phạm D | Tiếng Anh | | 23 |

- **Họ và Tên** có thể để trống (vì bảo mật). Khi đó TKB ghi **Mã GV**, ví dụ `Chủ Nhiệm 1/1`, `Tiếng Anh 2`, `Bộ Môn 3`.
- **Chức Vụ**:
  - `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý`, hoặc **đúng tên một môn** trong sheet `CHƯƠNG TRÌNH HỌC`, ví dụ `Tiếng Anh`, `Thể Dục`, `Tin Học`. Chức vụ trùng tên môn là giáo viên chuyên biệt, chỉ dạy môn đó.
  - Không có danh sách chức vụ cố định trong code, nên trường có môn mới (ví dụ `Múa`) chỉ cần thêm dòng môn và giáo viên `Múa`.
  - **Không ghi số thứ tự**: chương trình tự đánh số theo thứ tự dòng (Bộ Môn thứ nhất là `Bộ Môn 1`, thứ hai là `Bộ Môn 2`…).
  - Chức vụ không khớp môn nào thì báo lỗi kèm số dòng.
- **Lớp** chỉ ghi cho Chủ Nhiệm, dạng **khối/số thứ tự** (`1/1`, `5/5`). Nên định dạng cột là chữ (Text) để Excel không đổi `1/1` thành ngày tháng.
- **Số Tiết/Tuần** là mức tối đa mỗi tuần của từng người (ai được giảm tiết thì ghi mức đã giảm).
- Các cột khác (ví dụ cột STT, cột ghi chú) được bỏ qua, ghi gì cũng được.
- Danh sách lớp lấy từ các dòng Chủ Nhiệm, vì mỗi lớp luôn có một GVCN. Nếu dãy lớp của một khối bị hụt (ví dụ có 1/3, 1/5 mà không có 1/4) thì chương trình cảnh báo.
- Khi file có lỗi, chương trình **liệt kê tất cả lỗi một lần** kèm số dòng (ví dụ `Lớp 1/1 có hai Chủ Nhiệm (dòng 11 và 26)`).

**Sheet `CHƯƠNG TRÌNH HỌC` (bắt buộc):** Môn học | Khối 1 … Khối n (số tiết/tuần). Dòng `Tổng` (nếu có) được bỏ qua.
- Danh sách môn và tên môn lấy nguyên từ file, TKB in đúng tên trong file. Riêng HĐTN, TNXH, TV tăng cường được viết tắt trong ô TKB.
- Môn nào trùng tên một môn có luật trong `tkb/config.py` thì nhận luật đó. So khớp không phân biệt hoa thường, dấu câu và chữ "và": `Lịch Sử và Địa Lý` khớp `Lịch sử - Địa lý`.
- Nếu luật trong config nhắc một môn mà file không có (thường do gõ khác tên), chương trình cảnh báo.

Chỉ đọc mẫu V8. File mẫu cũ (V5–V7: chức vụ ghi kèm số như `bộ môn 5`, chương trình học ở file riêng) không còn đọc được: tạo file mẫu trống rồi chép dữ liệu sang, bỏ số thứ tự ở cột Chức Vụ.

Tạo file vào mẫu V8 trống:

```bash
python -m tkb.template data/Mau_Input.xlsx
```

## Cái gì nằm trong file vào, cái gì nằm trong code

| Nằm trong file vào (code không ghi) | Nằm trong `tkb/config.py` (file vào không có) |
|---|---|
| Danh sách môn, tên môn, số tiết từng khối | Khung giờ: Thứ 2–5 sáng 4 + chiều 3, Thứ 6 chỉ buổi sáng |
| Giáo viên, chức vụ, lớp chủ nhiệm, số tiết | HĐTN: Thứ 2 tiết 1, Thứ 6 tiết 4, tiết còn lại Thứ 3–5 |
| Danh sách lớp (suy ra từ các dòng Chủ Nhiệm) | Tiết 1 mỗi ngày do GVCN dạy |
| GV chuyên biệt (chức vụ trùng tên môn) | Môn ưu tiên GVCN, thứ tự cắt / nhận thêm của GVCN |
| Định mức người cần tuyển (Số tiết lớn nhất của GV cùng chức vụ) | Bộ Môn không dạy Tiếng Anh, Tin học, HĐTN; Quản Lý dạy Kỹ năng sống khối 4 |
| Style của các file ra (phông, cỡ chữ, viền, chiều cao dòng) | Luật bù giờ, môn nặng, tối đa 2 tiết TV/Toán mỗi buổi, trọng số |

## Đầu ra

1. **`TKB.xlsx`**: **chỉ có thời khóa biểu**, mỗi khối một sheet **Khối 1…5**.
   - Mẫu: `data/Output_Template_TKB_V8.xlsx` (TKB của trường mẫu tên giả). Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
   - Cột LỚP gộp 7 hàng; cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 5–7); cột TIẾT ghi số tiết trong ngày.
   - Mỗi ô ghi môn và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Tên để trống hoặc người cần tuyển thì ghi Mã GV (`Bộ Môn 6`); hai người trùng tên thì kèm Mã GV. Chiều Thứ 6 ghi `Nghỉ`.
   - Các cột ngày ở mọi sheet cùng độ rộng, nới theo dòng dài nhất của cả trường (tối đa 30); tên dài hơn thì xuống dòng và hàng tự cao thêm. Khi in: khổ ngang, co vừa chiều rộng 1 trang.
   - **`TKB_chuc_vu.xlsx`**: cùng TKB, mỗi ô thêm dòng thứ 3 là chức vụ (Mã GV), ví dụ `Tiếng Việt` / tên / `Bộ Môn 4`, để theo dõi ai dạy tiết nào.
2. **`Thong_Ke.xlsx`**: **một bảng** (sheet `Thống kê`), mẫu: `data/Output_Template_Thong_Ke_V8.xlsx`.
   - Mỗi giáo viên một dòng, theo thứ tự file nhân sự, rồi đến người cần tuyển (tên `tuyển thêm`).
   - Cột: **Họ và Tên | Chức Vụ** (Mã GV, ví dụ `Chủ Nhiệm 1/1`, `Bộ Môn 2`) **| số tiết từng môn người đó dạy | Tổng Tiết**. Chỉ có cột cho các môn có người dạy, theo thứ tự trong chương trình học; ô trống là không dạy môn đó. Cuối bảng có dòng **Tổng**.
   - **Tô màu cả dòng** để biết ai bù, ai thêm: chế độ bù giờ tô **vàng** dòng người dạy bù (vượt định mức); chế độ tuyển thêm tô **xanh lá** dòng người cần tuyển. Dưới bảng có chú thích màu kèm số người, số tiết, ví dụ `Dạy bù (vượt định mức): 29 người, 56 tiết` hoặc `Cần tuyển thêm: 3 người, 56 tiết`.
   - Chế độ, dự toán, mã kết quả, kết quả kiểm tra luật, người cần tuyển và dạy bù chỉ in ra màn hình.
   - **Chế độ bù giờ mà thiếu tiết:** không ra TKB; file này chỉ có sheet `Thiếu tiết`: **Lớp | Môn | Số Tiết Thiếu | Lý Do** và dòng Tổng.
3. **`<tên file vào>_cap_nhat.xlsx`**: bản chép của file vào (đủ cả 2 sheet). Sheet NHÂN SỰ có thêm các dòng `chưa có` ở cuối (chép style của dòng trên), Số tiết = định mức tuyển; bên phải thêm cột **Mã GV**, **Số Tiết Thực Dạy** (và **Số Tiết Bù**). File này dùng làm đầu vào cho lần chạy sau được (các cột thêm được bỏ qua khi đọc, chạy lại thì ghi đè). File gốc không bị sửa.

**Style:** mọi file ra chép style của sheet NHÂN SỰ trong file vào: phông, cỡ chữ, tiêu đề in đậm, viền, căn lề và chiều cao dòng (làm tròn, ví dụ 24,95 → 25). Bảng ghi tiêu đề cột ở dòng 1 như file vào. Riêng hàng tiết trong TKB cao đủ 2 dòng chữ (môn và giáo viên).

## Quy tắc nghiệp vụ

Các quy tắc không có trong file vào nằm trong `tkb/config.py`.

**Khung giờ**
- Thứ 2–Thứ 5: sáng 4 tiết, chiều 3 tiết.
- Thứ 6: chỉ học buổi sáng, 4 tiết.
- Mỗi lớp học 32 tiết/tuần.

**HĐTN**
- Chỉ GVCN của lớp được dạy.
- Hai tiết cố định: Thứ 2 tiết 1 và Thứ 6 tiết 4.
- Tiết còn lại xếp vào Thứ 3–Thứ 5, ưu tiên tiết cuối buổi.

**Giáo viên chủ nhiệm**
- Chỉ dạy lớp mình, nhận trước các môn Tiếng Việt, Toán, HĐTN, Khoa học, Lịch sử - Địa lý, Đạo đức.
- **Tiết 1 buổi sáng của mọi ngày luôn do GVCN của lớp dạy** (đổi ở `HOMEROOM_PERIODS`). Giáo viên khác không được xếp vào các tiết này.
- **Vượt định mức:** cắt theo thứ tự Tiếng Việt → Toán → Khoa học → Lịch sử - Địa lý. Chỉ cắt môn có hơn 1 tiết, và GVCN luôn giữ lại ít nhất 1 tiết của môn bị cắt.
- **Thiếu định mức:** nhận thêm theo thứ tự TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ. Không bao giờ nhận môn của giáo viên chuyên biệt.
- **GVCN trước:** môn ưu tiên mà có người khác cùng dạy (bộ môn, người mới) thì tiết đầu tuần là của GVCN, tiết của người khác không đứng trước tiết GVCN đầu tiên.

**Các chức vụ khác**
- **Giáo viên chuyên biệt** (chức vụ trùng tên một môn, ví dụ Tiếng Anh, Tin Học, Thể Dục): chỉ dạy đúng môn đó. Môn bộ môn không được dạy (Tiếng Anh, Tin học) mà trường chưa có ai thì chương trình tự thêm chức vụ trùng tên môn để tuyển (ví dụ `Tin Học 1`).
- **Bộ môn:** dạy mọi môn trừ Tiếng Anh, Tin học và HĐTN. Nghĩa là bộ môn vẫn dạy thay được Thể dục, Âm nhạc, Mỹ thuật, nhưng chỉ phần vượt định mức của giáo viên chuyên biệt (dự toán in số tiết này).
- **Quản lý:** chỉ dạy Kỹ năng sống Khối 4, đúng bằng số tiết của mình. Chương trình tự chọn lớp.

**Dự toán** (in ra màn hình trước khi xếp, cả hai chế độ)
- Tổng tiết cần dạy = phần GVCN + GV chuyên biệt + quản lý + bộ môn + tiết bù + tiết thiếu.
- Biên bù: đã dùng bao nhiêu trên tối đa có thể bù, ví dụ `Bù: 56/68 tiết (GVCN 56/58, bộ môn 0/10), còn dư 12 tiết`. Còn dư ít nghĩa là chỉ cần bớt một người là chế độ bù không đủ.

**Chế độ bù giờ** (`CHE_DO = "bu_gio"`)
- Chỉ GVCN và bộ môn được dạy bù (vượt Số tiết định mức), mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần.
- GVCN chỉ bù ở lớp mình, không bù môn của giáo viên chuyên biệt. Thứ tự môn: môn ưu tiên của GVCN (lấy lại tiết đã bị cắt) → TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ; ưu tiên nhận trọn một môn thay vì chia đôi.
- GVCN bù trước; bộ môn chỉ bù khi GVCN đã bù hết mức. Bộ kiểm tra báo lỗi nếu bộ môn dạy bù ở một lớp mà GVCN lớp đó còn được bù và dạy được môn đó.
- Chia đều: mọi người bù +1 rồi mới có người bù +2.
- **Bù hết mức vẫn thiếu thì báo lỗi, không tuyển thêm, không ra TKB**: màn hình in từng lớp, môn, số tiết thiếu và cách sửa; `Thong_Ke.xlsx` có sheet `Thiếu tiết`; mã thoát 3.

**Chế độ tuyển thêm** (`CHE_DO = "tuyen_them"`)
- **Cùng TKB với chế độ bù**: các tiết bù chuyển cho người mới, người mới dạy đúng các ô đó; cộng thêm các tiết còn thiếu (nếu có).
- Người mới có chức vụ `<chức vụ> n+1, n+2…`, tên `chưa có`, định mức bằng Số tiết lớn nhất của giáo viên cùng chức vụ trong file vào (chức vụ chưa có ai thì lấy của các giáo viên không chủ nhiệm, không quản lý).
- Tiết bù của một người ở một lớp giao trọn cho một người mới; mỗi người mới tối đa một cặp tiết mỗi buổi; người số nhỏ nhận nhiều tiết hơn.
- Không dạy hai lớp cùng lúc, không dạy tiết 1.

**Liên tiết** (luôn áp dụng)
- Hai tiết liền nhau trong một buổi, cùng lớp, cùng nhóm môn (Tiếng Việt với TV tăng cường, Toán với Toán tăng cường, môn khác là nhóm riêng) phải do **cùng một người** dạy. Tiết 4 sáng và tiết 5 chiều không tính là liền.

**Luật bảo vệ học sinh** (bật/tắt bằng `LUAT_HOC_SINH`)
- **Mỗi nhóm môn tối đa 2 tiết mỗi buổi** (TV + TV tăng cường tính chung; đổi ở `SESSION_GROUP_LIMIT`).
- **Toán mỗi ngày tối đa 1 tiết** (khi số tiết Toán/tuần không quá số ngày học; `DAILY_LIMITS`).
- **Ghép cặp:** nhóm môn có từ 6 tiết/tuần và tổng chẵn (TV + TV tăng cường khối 1–3) học thành các **cặp 2 tiết liền nhau**, mỗi buổi 0 hoặc 2 tiết của nhóm (`PAIR_MIN_LESSONS`; trừ Toán và HĐTN: `PAIR_EXCLUDED`). Phần của mỗi người trong nhóm ghép cặp luôn chẵn.
- **Môn có từ 2 tiết trong một buổi thì các tiết phải liền nhau**, không xếp so le. Ví dụ buổi sáng `TV, Toán, TV, Tiếng Anh` là sai, phải là `Toán, TV, TV, Tiếng Anh`. Áp dụng cho mọi môn, trong từng buổi (tiết 4 sáng và tiết 1 chiều không tính là liền).
- Môn nặng ở tiết 7 không bị cấm, chỉ hạn chế bằng mục tiêu mềm (xem dưới).

**Mục tiêu mềm**
- **Buổi sáng dành cho Tiếng Việt và Toán**, như TKB của các trường khác (xem [`docs/Tham_Khao_TKB_Truong_Khac.md`](docs/Tham_Khao_TKB_Truong_Khac.md)):
  - mỗi tiết TV, Toán xếp vào buổi chiều bị phạt;
  - Toán tăng cường ưu tiên buổi chiều; TV tăng cường thì ghép cặp với tiết TV nên không đẩy sang chiều;
  - tiết tăng cường liền sau tiết chính cùng nhóm, cùng người dạy được thưởng (`extra_after_main`);
  - đổi ở `MORNING_SUBJECTS`, `AFTERNOON_SUBJECTS`, trọng số `morning_core` (300), `extra_morning`, `core_spread`.

  Khối có nhiều tiết TV (vd khối 1: 14 tiết, mỗi buổi tối đa 2) vẫn phải có vài tiết TV buổi chiều. Mỗi lần chạy in ra số tiết TV, Toán còn ở buổi chiều.
- Hạn chế môn nặng ở tiết 7 (Toán, Tiếng Việt, tiết tăng cường, Tiếng Anh, Khoa học, Tin học; đổi ở `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, trọng số `heavy_late` (400)).
- Cân bằng số tiết mỗi ngày của giáo viên.
- Ít tiết trống giữa buổi.
- Rải đều các môn trong tuần (`subject_spread` 40, TV/Toán `core_spread` 120). Khối 1 có 7 cặp TV trong 5 ngày nên luôn có 2 ngày học 4 tiết TV.
- Phân công: hạn chế chia một lớp-môn cho hai giáo viên, gom lớp của một giáo viên vào ít khối, cân bằng tải.

## Cách giải

1. **Dự toán và phân công** (`tkb/phan_cong.py`, Python thuần, dưới 1 giây, mọi máy như nhau):
   - luồng chi phí nhỏ nhất từ các lớp-môn sang giáo viên được dạy, không vượt định mức và số ô giờ giáo viên đó dạy được; ưu tiên ít tiết thiếu nhất, rồi ít tiết bù của bộ môn, rồi ít tiết bù của GVCN, mọi người +1 rồi mới +2;
   - GVCN nhận tiết bù ở lớp mình (môn ưu tiên trước, môn trọn vẹn, chia chẵn nhóm ghép cặp); phần còn lại chia cho bộ môn, GV chuyên biệt, quản lý, rồi tìm kiếm cục bộ bớt chia môn, gom lớp, cân bằng tải.
2. **Tiết bù → người mới:** các tiết bù (và, ở chế độ tuyển, tiết thiếu) giao cho người tuyển mới.
3. **Xếp giờ một lần** (CP-SAT) với phân công cố định đó, trong `THOI_GIAN_TOI_DA`. Chế độ tuyển: giữ người mới. Chế độ bù: trả các ô đó về đúng người bù. Hai chế độ cùng vị trí môn.
4. **Dự phòng** (chỉ chế độ tuyển): nếu bước 3 không xếp được, giải mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ) với thêm giáo viên bổ sung dự phòng.

Sau khi giải, `tkb/checker.py` kiểm tra lại mọi luật bắt buộc trên TKB, độc lập với solver.

## Cấu trúc mã nguồn

| File | Nội dung |
|---|---|
| `main.py` | File chạy nhanh: sửa hằng số (file vào, thư mục ra, chế độ, luật học sinh, thời gian, tái lập) rồi bấm Run |
| `tkb/config.py` | Luật nghiệp vụ không có trong file vào: khung giờ, quyền dạy, thứ tự cắt/bù, luật học sinh, trọng số |
| `tkb/staff.py` | Đọc và kiểm tra file nhân sự |
| `tkb/template.py` | Tạo file vào mẫu V8 trống (NHÂN SỰ + CHƯƠNG TRÌNH HỌC) |
| `tkb/program.py` | Đọc sheet chương trình học, so khớp tên môn với luật trong config |
| `tkb/style.py` | Chép style của file vào cho các file ra |
| `tkb/allocation.py` | Phân phần GVCN, sinh lớp-môn và danh sách giáo viên được dạy, sinh giáo viên bổ sung, nhóm môn ghép cặp |
| `tkb/phan_cong.py` | Dự toán và phân công giáo viên (luồng chi phí nhỏ nhất, tìm kiếm cục bộ), chia tiết bù cho người mới |
| `tkb/solver.py` | Quy trình giải và mô hình xếp giờ CP-SAT |
| `tkb/checker.py` | Kiểm tra độc lập các luật bắt buộc |
| `tkb/writer.py` | Xuất Excel |
| `tools/code_map.py` | In bản đồ code (hàm, lớp, `file:dòng`); `--write` sinh lại `docs/CODE_MAP.md` |
| `tools/mau_dau_ra.py` | Sinh lại các file mẫu đầu ra `data/Output_Template_TKB_V8.xlsx`, `data/Output_Template_Thong_Ke_V8.xlsx` từ trường mẫu tên giả (`tests/du_lieu_mau.py`) |

Hướng dẫn cho Claude Code (lệnh, kiến trúc, luật bảo mật, mã tham chiếu): [`CLAUDE.md`](CLAUDE.md).
