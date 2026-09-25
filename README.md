# Xếp thời khóa biểu tự động (TKB)

Chương trình Python đọc **danh sách nhân sự** (Excel) và xếp thời khóa biểu tuần cho toàn trường
bằng OR-Tools CP-SAT. Khi trường thiếu người, có hai chế độ:

- **Tuyển thêm** (`tuyen_them`): thêm giáo viên mới vào danh sách nhân sự với tên "chưa có"
  (ví dụ `chưa có | bộ môn 6 | 23`) thay vì bỏ trống tiết.
- **Bù giờ** (`bu_gio`): GVCN và bộ môn dạy bù vượt định mức, mỗi người tối đa 2 tiết/tuần
  (người hưởng thai sản không bù). Chỉ khi bù vẫn không đủ mới thêm người "chưa có".

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
| `THU_MUC_IN` | Thư mục chứa file đầu vào | `data` |
| `THU_MUC_OUT` | Thư mục ghi kết quả; tự tạo nếu chưa có | `out` |
| `FILE_NHAN_SU` | Tên file danh sách nhân sự trong `THU_MUC_IN` | `Input_Danh_Sach_Nhan_Su_V6.xlsx` |
| `FILE_CHUONG_TRINH` | Tên file chương trình học trong `THU_MUC_IN`; `None` = dùng chương trình mặc định | `None` |
| `FILE_TKB` | Tên file TKB xuất ra | `TKB.xlsx` |
| `THOI_GIAN_TOI_DA` | Lượng tính toán cho bước xếp giờ, xấp xỉ giây; tăng lên để TKB đẹp hơn | `240` (≈ 3,5 phút) |
| `CHAY_TAI_LAP_DUOC` | `True`: chạy lại bao nhiêu lần cũng ra đúng một TKB, ở cả hai chế độ (xem điều kiện bên dưới); `False`: dừng theo giây thực, mỗi lần có thể khác | `True` |
| `SO_LUONG` | Số luồng tìm kiếm song song của bộ giải; nên ≥ số nhân CPU. Đổi số này thì TKB ra khác (vẫn đúng luật) | `8` |
| `CHE_DO` | Khi thiếu người: `"tuyen_them"` (thêm GV "chưa có") hoặc `"bu_gio"` (GVCN/bộ môn dạy bù) | `"bu_gio"` |
| `SO_TIET_BU_TOI_DA` | Chế độ bù giờ: số tiết bù tối đa mỗi GVCN/bộ môn mỗi tuần (người hưởng thai sản không bù) | `2` |
| `LUAT_HOC_SINH` | Bật luật bảo vệ học sinh | `True` |

   - Đường dẫn tương đối được tính từ thư mục chứa `main.py`.
   - **Chạy lại ra đúng TKB cũ** khi `CHAY_TAI_LAP_DUOC = True` và giữ nguyên: file đầu vào, `CHE_DO`, `SO_TIET_BU_TOI_DA`, `THOI_GIAN_TOI_DA`, `SO_LUONG`, phiên bản OR-Tools (đã ghim trong `requirements.txt`). Máy nhanh hay chậm không ảnh hưởng kết quả, chỉ ảnh hưởng thời gian chạy.
   - Trên Windows, viết đường dẫn dạng `r"C:\Users\ten\TKB\in"` hoặc `"C:/Users/ten/TKB/in"`.
2. Bấm **Run ▶** (VS Code, PyCharm...) hoặc chạy `python main.py`.
3. Kết quả nằm trong `THU_MUC_OUT`: file `TKB.xlsx` và `<tên file nhân sự>_cap_nhat.xlsx`.

### Cách 2 — dòng lệnh

```bash
python -m tkb data/Input_Danh_Sach_Nhan_Su_V6.xlsx -o out/TKB.xlsx
```

Tuỳ chọn:

| Tham số | Ý nghĩa |
|---|---|
| `-o, --output` | File TKB xuất ra (mặc định `out/TKB.xlsx`) |
| `--staff-out` | File nhân sự cập nhật (mặc định `<thư mục output>/<tên input>_cap_nhat.xlsx`) |
| `--program` | File chương trình học (cột `Môn học`, `Khối 1..5`); mặc định dùng chương trình trong `tkb/config.py` |
| `--time-limit` | Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 240) |
| `--non-reproducible` | Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau |
| `--mode` | `tuyen_them` (mặc định) hoặc `bu_gio` |
| `--max-overtime` | Chế độ bù giờ: số tiết bù tối đa mỗi người (mặc định 2) |
| `--no-student-rules` | Tắt luật bảo vệ học sinh (dùng để tìm nguyên nhân khi không xếp được) |

Chạy test: `python -m pytest -q`

## Đầu vào

File Excel 1 sheet, 4 cột, ví dụ `data/Input_Danh_Sach_Nhan_Su_V6.xlsx`:

| Tên | Chức vụ | Số tiết | Thai sản |
|---|---|---|---|
| Nguyễn Văn A | chủ nhiệm 1/1 | 19 | |
| Trần Thị B | chủ nhiệm 5/5 | 16 | Có |
| Lê Văn C | bộ môn 5 | 19 | Có |

- **Chức vụ** chọn từ danh sách thả xuống: tên chức vụ + số thứ tự, ví dụ `chủ nhiệm 1/1`, `bộ môn 4`, `tiếng anh 2`, `quản lý 1`. Chức vụ bị trùng tự tô đỏ.
- **Số tiết** là mức tối đa mỗi tuần (số nguyên 0–40). Người hưởng thai sản ghi mức đã giảm.
- **Thai sản**: ghi `Có` nếu đang hưởng chế độ thai sản, để trống nếu không. Ở sheet Danh sách nhân sự và Thống kê, chức vụ của người này có thêm `ts`, ví dụ `chủ nhiệm 5/5 ts`.
- Danh sách lớp lấy từ các dòng `chủ nhiệm khối/stt`, vì mỗi lớp luôn có một GVCN.
- File cũ 3 cột (ghi chữ `ts` sau chức vụ, ví dụ `bộ môn 5 ts`) vẫn đọc được.

Tạo file mẫu mới, hoặc chuyển file cũ sang file mẫu:

```bash
python -m tkb.template data/Mau_Nhan_Su.xlsx                                    # file mẫu trống
python -m tkb.template data/Nhan_Su_Moi.xlsx --tu data/Input_Danh_Sach_Nhan_Su_V5.xlsx   # chép dữ liệu file cũ
```

## Đầu ra

1. **`TKB.xlsx`**
   - Sheet **Khối 1…5**: định dạng theo `data/Output_Template_TKB_V5_Formatted.xlsx`.
     - Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
     - Cột LỚP gộp 7 hàng; cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 1–3).
     - Mỗi ô ghi môn và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Người cần tuyển ghi `chưa có (bộ môn 6)`; hai người trùng tên thì kèm chức vụ để phân biệt. Chiều Thứ 6 ghi `Nghỉ`.
     - Cột ngày tự nới theo tên dài nhất (24–30); tên dài hơn thì xuống dòng và hàng tự cao thêm.
     - Font Times New Roman cỡ 14 (phóng to so với template cỡ 10 cho dễ đọc; đổi ở `FONT_SIZE` trong `tkb/writer.py`), dòng tiêu đề nền xám nhạt, viền mảnh. Khi in: khổ ngang, co vừa chiều rộng 1 trang.
   - Sheet **Danh sách nhân sự**: danh sách đã cập nhật, kèm số tiết thực dạy (chế độ bù giờ có thêm cột **Số tiết bù**). Người bổ sung có tên `chưa có`, Số tiết ghi theo **định mức tuyển đầy đủ** của chức vụ (bộ môn: 23), dù thực dạy có thể ít hơn.
   - Sheet **Thống kê**:
     - Các chức vụ thiếu và số tiết thiếu, kèm chi tiết lớp/môn.
     - Chế độ bù giờ: ai dạy bù, bao nhiêu tiết, GVCN bù môn gì.
     - Tổng hợp theo nhóm chức vụ: định mức, đã dạy, dư, thiếu.
     - Tải từng giáo viên theo từng ngày.
     - Kết quả kiểm tra luật bắt buộc.
2. **`<tên input>_cap_nhat.xlsx`**: file nhân sự gốc, có thêm các dòng `chưa có` ở cuối, Số tiết = định mức tuyển (vd 23). File này dùng làm đầu vào cho lần chạy sau được. File gốc không bị sửa.

## Quy tắc nghiệp vụ

Mọi quy tắc đều cấu hình được trong `tkb/config.py`.

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
- **Giáo viên chuyên biệt** (tiếng anh, tin học, thể dục, âm nhạc, mỹ thuật): chỉ dạy đúng môn trùng tên chức vụ.
- **Bộ môn:** dạy mọi môn trừ Tiếng Anh, Tin học và HĐTN. Nghĩa là bộ môn vẫn dạy thay được Thể dục, Âm nhạc, Mỹ thuật, nhưng giáo viên chuyên biệt được ưu tiên dạy trước.
- **Quản lý:** chỉ dạy Kỹ năng sống Khối 4, đúng bằng số tiết của mình. Chương trình tự chọn lớp.

**Giáo viên bổ sung** (khi thiếu người)
- Chức vụ là `<chức vụ> n+1, n+2…`, tên `chưa có`.
- Được tuyển với định mức đầy đủ bằng mức của giáo viên cùng chức vụ (bộ môn: 23), và ghi 23 trong danh sách nhân sự.
- Không dạy hai lớp cùng lúc.
- Chương trình ưu tiên (1) ít tiết thiếu nhất, rồi (2) ít người bổ sung nhất.
- Tiết được dồn cho người bổ sung đầu trước; người cuối có thể dạy chưa đủ định mức, ví dụ 23 + 23 + 6.

**Chế độ bù giờ** (`CHE_DO = "bu_gio"`)
- Chỉ GVCN và bộ môn được dạy bù (vượt Số tiết định mức), mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần.
- **Người hưởng thai sản (`ts`) không bao giờ phải bù** (luật cứng).
- GVCN chỉ bù ở lớp mình, không bù môn của giáo viên chuyên biệt. Thứ tự môn: môn ưu tiên của GVCN (lấy lại tiết đã bị cắt) → TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ.
- GVCN bù trước; bộ môn chỉ bù khi GVCN đã bù hết mức.
- Chia đều: mọi người bù +1 rồi mới có người bù +2.
- Nếu bù hết mức vẫn thiếu thì phần còn lại mới thêm GV "chưa có" như chế độ tuyển thêm.

**Luật bảo vệ học sinh**
- Mỗi buổi tối đa 2 tiết Tiếng Việt và 2 tiết Toán (tiết tăng cường được đếm riêng).
- Môn nặng ở tiết 7 không bị cấm nữa, chỉ hạn chế bằng mục tiêu mềm (xem dưới). Không giới hạn số tiết nặng liên tiếp.

**Mục tiêu mềm**
- Hạn chế môn nặng ở tiết 7 (Toán, Tiếng Việt, tiết tăng cường, Tiếng Anh, Khoa học, Tin học; đổi ở `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, trọng số `heavy_late`).
- Cân bằng số tiết mỗi ngày của giáo viên.
- Ít tiết trống giữa buổi.
- Rải đều các môn trong tuần.
- Hạn chế chia một lớp-môn cho hai giáo viên.

## Cách giải

1. **Phân công** (chưa xếp giờ): CP-SAT tìm số tiết mỗi giáo viên dạy cho từng lớp-môn, không vượt định mức và số tiết trống giáo viên đó có thể xếp. Mục tiêu đầu tiên là ít tiết thiếu nhất, rồi ít người bổ sung nhất (chế độ bù giờ: rồi ít tiết bù của bộ môn, ít tiết bù của GVCN); sau đó mới đến chia đều tiết bù, hạn chế chia môn và cân bằng tải. Kết quả này là cận dưới của bài toán.
2. **Xếp giờ** với phân công cố định. Nếu xếp được thì nghiệm đạt đúng cận dưới ở bước 1.
3. **Dự phòng:** nếu bước 2 không xếp được, chương trình giải mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ) với thêm giáo viên bổ sung dự phòng.

Sau khi giải, `tkb/checker.py` kiểm tra lại mọi luật bắt buộc trên TKB, độc lập với solver.

## Cấu trúc mã nguồn

| File | Nội dung |
|---|---|
| `main.py` | File chạy nhanh: sửa hằng số thư mục vào/ra rồi bấm Run |
| `tkb/config.py` | Toàn bộ tham số nghiệp vụ: chương trình, khung giờ, quyền dạy, thứ tự cắt/bù, trọng số |
| `tkb/staff.py` | Đọc và kiểm tra file nhân sự |
| `tkb/template.py` | Tạo file mẫu nhân sự (danh sách thả xuống), chuyển file cũ sang file mẫu |
| `tkb/program.py` | Đọc file chương trình học (tuỳ chọn) |
| `tkb/allocation.py` | Phân phần GVCN, sinh lớp-môn và danh sách giáo viên được dạy, sinh giáo viên bổ sung |
| `tkb/solver.py` | Mô hình CP-SAT |
| `tkb/checker.py` | Kiểm tra độc lập các luật bắt buộc |
| `tkb/writer.py` | Xuất Excel |
