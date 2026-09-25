# Xếp thời khóa biểu tự động (TKB)

Chương trình Python đọc **một file Excel** (danh sách nhân sự và chương trình học của trường) và xếp
thời khóa biểu tuần cho toàn trường bằng OR-Tools CP-SAT. Khi trường thiếu người, có hai chế độ:

- **Tuyển thêm** (`tuyen_them`): thêm giáo viên mới vào danh sách nhân sự với tên "chưa có"
  (ví dụ `chưa có | Bộ Môn | 23`, Mã GV `Bộ Môn 6`) thay vì bỏ trống tiết.
- **Bù giờ** (`bu_gio`): GVCN và bộ môn dạy bù vượt định mức, mỗi người tối đa 2 tiết/tuần
  (kể cả người hưởng thai sản). Chỉ khi bù vẫn không đủ mới thêm người "chưa có".

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
| `FILE_VAO` | **Địa chỉ file vào** (sheet `NHÂN SỰ` và `CHƯƠNG TRÌNH HỌC`) | `data/Input_TKB_V8.xlsx` |
| `THU_MUC_OUT` | Thư mục ghi kết quả; tự tạo nếu chưa có. **Để trống `""` thì ghi vào thư mục dự án** (thư mục chứa `main.py`) | `out` |
| `CHE_DO` | Khi thiếu người: `"bu_gio"` (GVCN/bộ môn dạy bù) hoặc `"tuyen_them"` (thêm GV "chưa có") | `"bu_gio"` |
| `SO_TIET_BU_TOI_DA` | Chế độ bù giờ: số tiết bù tối đa mỗi GVCN/bộ môn mỗi tuần (kể cả người hưởng thai sản) | `2` |
| `LUAT_HOC_SINH` | Áp dụng luật bảo vệ học sinh | `True` |
| `THOI_GIAN_TOI_DA` | Thời gian cho bước xếp giờ, xấp xỉ giây; tăng lên để TKB đẹp hơn. **Để trống (`None`/`""`) hoặc `0` thì không giới hạn**: chạy đến khi bộ giải chứng minh TKB tốt nhất (có thể hàng giờ); bấm Ctrl+C để dừng sớm, TKB tốt nhất đã tìm được vẫn được ghi ra | `240` (≈ 3,5 phút) |
| `CHAY_TAI_LAP_DUOC` | `True`: chạy lại bao nhiêu lần cũng ra đúng một kết quả, ở cả hai chế độ (xem điều kiện bên dưới); `False`: dừng theo giây thực, mỗi lần có thể khác | `True` |
| `FILE_TKB`, `FILE_THONG_KE` | Tên file TKB và file thống kê giáo viên xuất ra | `TKB.xlsx`, `Thong_Ke.xlsx` |
| `SO_LUONG` | Số luồng tìm kiếm song song của bộ giải; nên ≥ số nhân CPU. Đổi số này thì TKB ra khác (vẫn đúng luật) | `8` |

   - Đường dẫn tương đối được tính từ thư mục chứa `main.py`.
   - **Chạy lại, hoặc chạy ở máy khác, ra đúng TKB cũ** khi `CHAY_TAI_LAP_DUOC = True` và giữ nguyên: file vào, các hằng số trong `main.py`, phiên bản thư viện (cài bằng `pip install -r requirements.txt`). Xem mục [Chạy trên máy khác](#chạy-trên-máy-khác).
   - **Không giới hạn thời gian** (`THOI_GIAN_TOI_DA` để trống hoặc `0`): bước phân công vẫn chứng minh tối ưu số tiết thiếu/bù trong vài giây; bước xếp giờ chạy đến khi chứng minh TKB tốt nhất, với trường cỡ 29 lớp gần như không tự dừng. Bấm **Ctrl+C** để dừng, chương trình vẫn kiểm tra luật và ghi đủ các file ra. Dừng bằng tay thì mỗi lần có thể ra TKB khác nhau.
   - Trên Windows, viết đường dẫn dạng `r"C:\Users\ten\TKB\input.xlsx"` hoặc `"C:/Users/ten/TKB/input.xlsx"`.
2. Bấm **Run ▶** (VS Code, PyCharm...) hoặc chạy `python main.py`.
3. Kết quả nằm trong `THU_MUC_OUT`: `TKB.xlsx`, `Thong_Ke.xlsx` và `<tên file vào>_cap_nhat.xlsx`.

### Cách 2 — dòng lệnh

```bash
python -m tkb data/Input_TKB_V8.xlsx -o out/TKB.xlsx
```

Tuỳ chọn:

| Tham số | Ý nghĩa |
|---|---|
| `-o, --output` | File TKB xuất ra (mặc định `out/TKB.xlsx`) |
| `--staff-out` | File nhân sự cập nhật (mặc định `<thư mục output>/<tên input>_cap_nhat.xlsx`) |
| `--stats-out` | File thống kê giáo viên (mặc định `<thư mục output>/Thong_Ke.xlsx`) |
| `--program` | File chương trình học riêng; mặc định đọc sheet `CHƯƠNG TRÌNH HỌC` của file vào |
| `--time-limit` | Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 240; `0` = không giới hạn, Ctrl+C để dừng) |
| `--non-reproducible` | Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau |
| `--mode` | `tuyen_them` (mặc định) hoặc `bu_gio` |
| `--max-overtime` | Chế độ bù giờ: số tiết bù tối đa mỗi người (mặc định 2) |
| `--no-student-rules` | Tắt luật bảo vệ học sinh (dùng để tìm nguyên nhân khi không xếp được) |

Chạy test: `python -m pytest -q`

## Chạy trên máy khác

Cùng file vào và cùng các hằng số trong `main.py` thì **máy nào cũng ra cùng một TKB** (khi `CHAY_TAI_LAP_DUOC = True` và `THOI_GIAN_TOI_DA` có giá trị), với điều kiện:

1. Cài đúng phiên bản thư viện: `pip install -r requirements.txt` (OR-Tools 9.15.6755, openpyxl 3.1.5). Nếu OR-Tools khác bản này, chương trình in cảnh báo.
2. Không sửa code trong `tkb/`.

**Không ảnh hưởng kết quả:** máy nhanh hay chậm, số nhân CPU, máy đang bận, phiên bản Python (đã thử 3.10–3.13), thư mục đặt dự án. Bộ giải dừng theo lượng tính toán chứ không theo giây thực, nên máy chậm chỉ chạy lâu hơn.

**Mã kết quả:** mỗi lần chạy in ra màn hình và ghi ở sheet Thống kê một mã, ví dụ `Mã kết quả: 6523-7A90-932C`. Mã này là mã băm của toàn bộ TKB. Hai máy cùng mã là cùng TKB, khỏi phải so từng ô.

**Kiểm tra một máy mới** (mất khoảng 20 giây): `python -m pytest tests/test_reproducible.py`. Test so mã kết quả của một trường nhỏ với mã tham chiếu. Qua là máy đó ra đúng kết quả như máy gốc.

**Giới hạn:** đã kiểm chứng trên Linux x86-64. OR-Tools không cam kết kết quả giống hệt giữa các hệ điều hành hoặc loại CPU khác nhau (Windows, macOS, chip ARM như Apple M1). Nếu test trên báo khác mã ở một máy, hãy xếp TKB chính thức trên một máy cố định, hoặc trên các máy cùng hệ điều hành và loại CPU.

## Đầu vào

**Một file Excel duy nhất** (mẫu V8, ví dụ `data/Input_TKB_V8.xlsx`) gồm 2 sheet. Chương trình tìm sheet theo tên, không phân biệt hoa thường.

**Sheet `NHÂN SỰ`:**

| Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Chế Độ |
|---|---|---|---|---|
| Nguyễn Văn A | Chủ Nhiệm | 1/1 | 19 | |
| Trần Thị B | Chủ Nhiệm | 5/5 | 16 | Có |
| Lê Văn C | Bộ Môn | | 19 | Có |
| Phạm D | Tiếng Anh | | 23 | |

- **Họ và Tên** có thể để trống (vì bảo mật). Khi đó TKB ghi **Mã GV**, ví dụ `Chủ Nhiệm 1/1`, `Tiếng Anh 2`, `Bộ Môn 3`.
- **Chức Vụ**:
  - `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý`, hoặc **đúng tên một môn** trong sheet `CHƯƠNG TRÌNH HỌC`, ví dụ `Tiếng Anh`, `Thể Dục`, `Tin Học`. Chức vụ trùng tên môn là giáo viên chuyên biệt, chỉ dạy môn đó.
  - Không có danh sách chức vụ cố định trong code, nên trường có môn mới (ví dụ `Múa`) chỉ cần thêm dòng môn và giáo viên `Múa`.
  - **Không ghi số thứ tự**: chương trình tự đánh số theo thứ tự dòng (Bộ Môn thứ nhất là `Bộ Môn 1`, thứ hai là `Bộ Môn 2`…).
  - Chức vụ không khớp môn nào thì báo lỗi kèm số dòng.
- **Lớp** chỉ ghi cho Chủ Nhiệm, dạng **khối/số thứ tự** (`1/1`, `5/5`). Nên định dạng cột là chữ (Text) để Excel không đổi `1/1` thành ngày tháng.
- **Số Tiết/Tuần** là mức tối đa mỗi tuần. Người hưởng thai sản ghi mức đã giảm.
- **Chế Độ**: ghi `Có` nếu đang hưởng chế độ thai sản, để trống nếu không.
- Danh sách lớp lấy từ các dòng Chủ Nhiệm, vì mỗi lớp luôn có một GVCN. Nếu dãy lớp của một khối bị hụt (ví dụ có 1/3, 1/5 mà không có 1/4) thì chương trình cảnh báo.
- Khi file có lỗi, chương trình **liệt kê tất cả lỗi một lần** kèm số dòng (ví dụ `Lớp 1/1 có hai Chủ Nhiệm (dòng 11 và 26)`).

**Sheet `CHƯƠNG TRÌNH HỌC` (bắt buộc):** Môn học | Khối 1 … Khối n (số tiết/tuần). Dòng `Tổng` (nếu có) được bỏ qua.
- Danh sách môn và tên môn lấy nguyên từ file, TKB in đúng tên trong file. Riêng HĐTN, TNXH, TV tăng cường được viết tắt trong ô TKB.
- Môn nào trùng tên một môn có luật trong `tkb/config.py` thì nhận luật đó. So khớp không phân biệt hoa thường, dấu câu và chữ "và": `Lịch Sử và Địa Lý` khớp `Lịch sử - Địa lý`.
- Nếu luật trong config nhắc một môn mà file không có (thường do gõ khác tên), chương trình cảnh báo.

File cũ vẫn đọc được: sheet nhân sự mẫu V7/V6 (chức vụ ghi kèm số như `bộ môn 5`) và V5 (3 cột, ghi `ts` sau chức vụ). Khi đó chương trình học lấy từ `--program`.

Tạo file mẫu mới, hoặc chuyển file cũ sang file mẫu:

```bash
python -m tkb.template data/Mau_Input.xlsx                                      # file vào mẫu trống
python -m tkb.template data/Input_Moi.xlsx --tu data/Input_Danh_Sach_Nhan_Su_V5.xlsx --program data/Input_Chuong_Trinh_Hoc_V5.xlsx
```

## Cái gì nằm trong file vào, cái gì nằm trong code

| Nằm trong file vào (code không ghi) | Nằm trong `tkb/config.py` (file vào không có) |
|---|---|
| Danh sách môn, tên môn, số tiết từng khối | Khung giờ: Thứ 2–5 sáng 4 + chiều 3, Thứ 6 chỉ buổi sáng |
| Giáo viên, chức vụ, lớp chủ nhiệm, số tiết, thai sản | HĐTN: Thứ 2 tiết 1, Thứ 6 tiết 4, tiết còn lại Thứ 3–5 |
| Danh sách lớp (suy ra từ các dòng Chủ Nhiệm) | Tiết 1 mỗi ngày do GVCN dạy |
| GV chuyên biệt (chức vụ trùng tên môn) | Môn ưu tiên GVCN, thứ tự cắt / nhận thêm của GVCN |
| Định mức người cần tuyển (Số tiết lớn nhất của GV cùng chức vụ) | Bộ Môn không dạy Tiếng Anh, Tin học, HĐTN; Quản Lý dạy Kỹ năng sống khối 4 |
| Style của các file ra (phông, cỡ chữ, viền, chiều cao dòng) | Luật bù giờ, môn nặng, tối đa 2 tiết TV/Toán mỗi buổi, trọng số |

## Đầu ra

1. **`TKB.xlsx`**
   - Sheet **Khối 1…5**: định dạng theo `data/Output_Template_TKB_V5_Formatted.xlsx`.
     - Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
     - Cột LỚP gộp 7 hàng; cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 1–3).
     - Mỗi ô ghi môn và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Tên để trống hoặc người cần tuyển thì ghi Mã GV (`Bộ Môn 6`); hai người trùng tên thì kèm Mã GV. Chiều Thứ 6 ghi `Nghỉ`.
     - Cột ngày tự nới theo tên dài nhất (tối đa 30); tên dài hơn thì xuống dòng và hàng tự cao thêm. Khi in: khổ ngang, co vừa chiều rộng 1 trang.
   - Sheet **Danh sách nhân sự**: các cột như sheet NHÂN SỰ của file vào (Họ và Tên, Chức Vụ, Lớp, Số Tiết/Tuần, Chế Độ), thêm **Mã GV**, **Số Tiết Thực Dạy**, **Số Tiết Bù** (chế độ bù giờ) và Ghi Chú. Người cần tuyển có tên `chưa có`, Số tiết ghi theo **định mức tuyển đầy đủ** của chức vụ, dù thực dạy có thể ít hơn.
   - Sheet **Thống kê**:
     - Các chức vụ thiếu và số tiết thiếu, kèm chi tiết lớp/môn.
     - Chế độ bù giờ: ai dạy bù, bao nhiêu tiết, GVCN bù môn gì.
     - Tổng hợp theo nhóm chức vụ: định mức, đã dạy, dư, thiếu.
     - Tải từng giáo viên theo từng ngày.
     - Kết quả kiểm tra luật bắt buộc.
2. **`<tên file vào>_cap_nhat.xlsx`**: bản chép của file vào (đủ cả 2 sheet). Sheet NHÂN SỰ có thêm các dòng `chưa có` ở cuối (chép style của dòng trên), Số tiết = định mức tuyển; bên phải thêm cột **Mã GV**, **Số Tiết Thực Dạy** (và **Số Tiết Bù**). File này dùng làm đầu vào cho lần chạy sau được (các cột thêm được bỏ qua khi đọc, chạy lại thì ghi đè). File gốc không bị sửa.
3. **`Thong_Ke.xlsx`**: file thống kê riêng. Người cần tuyển có tên `tuyển thêm`.
   - **Thống kê giáo viên**: Họ và Tên | Chức Vụ | Mã GV | Số tiết quy định | Số tiết bù | Số tiết thực dạy | Số tiết còn dư, cuối bảng có dòng Tổng.
   - **Phân công**: giáo viên dạy môn gì, lớp nào, bao nhiêu tiết (bảng phân công chuyên môn).
   - **Theo ngày**: số tiết từng ngày Thứ 2 → Thứ 6 của mỗi giáo viên.
   - **Theo chức vụ**: số người, tiết quy định, thực dạy, bù, còn dư, số người và số tiết tuyển thêm của từng chức vụ.

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

**Các chức vụ khác**
- **Giáo viên chuyên biệt** (chức vụ trùng tên một môn, ví dụ Tiếng Anh, Tin Học, Thể Dục): chỉ dạy đúng môn đó. Môn bộ môn không được dạy (Tiếng Anh, Tin học) mà trường chưa có ai thì chương trình tự thêm chức vụ trùng tên môn để tuyển (ví dụ `Tin Học 1`).
- **Bộ môn:** dạy mọi môn trừ Tiếng Anh, Tin học và HĐTN. Nghĩa là bộ môn vẫn dạy thay được Thể dục, Âm nhạc, Mỹ thuật, nhưng giáo viên chuyên biệt được ưu tiên dạy trước.
- **Quản lý:** chỉ dạy Kỹ năng sống Khối 4, đúng bằng số tiết của mình. Chương trình tự chọn lớp.

**Giáo viên bổ sung** (khi thiếu người)
- Chức vụ là `<chức vụ> n+1, n+2…`, tên `chưa có`.
- Được tuyển với định mức đầy đủ bằng Số tiết lớn nhất của giáo viên cùng chức vụ trong file vào (không tính người thai sản; chức vụ chưa có ai thì lấy của các giáo viên không chủ nhiệm, không quản lý).
- Không dạy hai lớp cùng lúc.
- Chương trình ưu tiên (1) ít tiết thiếu nhất, rồi (2) ít người bổ sung nhất.
- Tiết được dồn cho người bổ sung đầu trước; người cuối có thể dạy chưa đủ định mức, ví dụ 23 + 23 + 6.

**Chế độ bù giờ** (`CHE_DO = "bu_gio"`)
- Chỉ GVCN và bộ môn được dạy bù (vượt Số tiết định mức), mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần.
- **Người hưởng thai sản cũng được bù** như mọi người, cùng mức tối đa.
- GVCN chỉ bù ở lớp mình, không bù môn của giáo viên chuyên biệt. Thứ tự môn: môn ưu tiên của GVCN (lấy lại tiết đã bị cắt) → TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ.
- GVCN bù trước; bộ môn chỉ bù khi GVCN đã bù hết mức. Bộ kiểm tra báo lỗi nếu bộ môn dạy bù ở một lớp mà GVCN lớp đó còn được bù và dạy được môn đó.
- Chia đều: mọi người bù +1 rồi mới có người bù +2.
- Nếu bù hết mức vẫn thiếu thì phần còn lại mới thêm GV "chưa có" như chế độ tuyển thêm.

**Luật bảo vệ học sinh** (bật/tắt bằng `LUAT_HOC_SINH`)
- Mỗi buổi tối đa 2 tiết Tiếng Việt và 2 tiết Toán (tiết tăng cường được đếm riêng).
- **Môn có từ 2 tiết trong một buổi thì các tiết phải liền nhau**, không xếp so le. Ví dụ buổi sáng `TV, Toán, TV, Tiếng Anh` là sai, phải là `Toán, TV, TV, Tiếng Anh`. Áp dụng cho mọi môn, trong từng buổi (tiết 4 sáng và tiết 1 chiều không tính là liền).
- Môn nặng ở tiết 7 không bị cấm nữa, chỉ hạn chế bằng mục tiêu mềm (xem dưới). Không giới hạn số tiết nặng liên tiếp.

**Mục tiêu mềm**
- Hạn chế môn nặng ở tiết 7 (Toán, Tiếng Việt, tiết tăng cường, Tiếng Anh, Khoa học, Tin học; đổi ở `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, trọng số `heavy_late`).
- Cân bằng số tiết mỗi ngày của giáo viên.
- Ít tiết trống giữa buổi.
- Rải đều các môn trong tuần.
- Hạn chế chia một lớp-môn cho hai giáo viên.

## Cách giải

1. **Phân công** (chưa xếp giờ): CP-SAT tìm số tiết mỗi giáo viên dạy cho từng lớp-môn, không vượt định mức và số tiết trống giáo viên đó có thể xếp. Mục tiêu đầu tiên là ít tiết thiếu nhất, rồi ít người bổ sung nhất (chế độ bù giờ: rồi ít tiết bù của bộ môn, ít tiết bù của GVCN); sau đó mới đến chia đều tiết bù, hạn chế chia môn và cân bằng tải. Kết quả này là cận dưới của bài toán.
2. **Xếp giờ** với phân công cố định, trong `THOI_GIAN_TOI_DA` (để trống thì đến khi chứng minh tối ưu hoặc bấm Ctrl+C). Nếu xếp được thì nghiệm đạt đúng cận dưới ở bước 1.
3. **Dự phòng:** nếu bước 2 không xếp được, chương trình giải mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ) với thêm giáo viên bổ sung dự phòng.

Sau khi giải, `tkb/checker.py` kiểm tra lại mọi luật bắt buộc trên TKB, độc lập với solver.

## Cấu trúc mã nguồn

| File | Nội dung |
|---|---|
| `main.py` | File chạy nhanh: sửa hằng số (file vào, thư mục ra, chế độ, luật học sinh, thời gian, tái lập) rồi bấm Run |
| `tkb/config.py` | Luật nghiệp vụ không có trong file vào: khung giờ, quyền dạy, thứ tự cắt/bù, luật học sinh, trọng số |
| `tkb/staff.py` | Đọc và kiểm tra file nhân sự |
| `tkb/template.py` | Tạo file vào mẫu V8 (NHÂN SỰ + CHƯƠNG TRÌNH HỌC), chuyển file cũ sang file mẫu |
| `tkb/program.py` | Đọc sheet chương trình học, so khớp tên môn với luật trong config |
| `tkb/style.py` | Chép style của file vào cho các file ra |
| `tkb/allocation.py` | Phân phần GVCN, sinh lớp-môn và danh sách giáo viên được dạy, sinh giáo viên bổ sung |
| `tkb/solver.py` | Mô hình CP-SAT |
| `tkb/checker.py` | Kiểm tra độc lập các luật bắt buộc |
| `tkb/writer.py` | Xuất Excel |
