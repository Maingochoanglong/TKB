# Xếp thời khóa biểu tự động (TKB)

Chương trình Python đọc **danh sách nhân sự** (Excel) và xếp thời khóa biểu tuần cho toàn trường
bằng OR-Tools CP-SAT. Khi trường thiếu người, chương trình **thêm giáo viên mới vào danh sách nhân sự
với tên "chưa có"** (ví dụ `chưa có | bộ môn 6 | 23`) thay vì bỏ trống tiết.

## Cài đặt và chạy

```bash
pip install -r requirements.txt
python -m tkb data/Input_Danh_Sach_Nhan_Su_V5.xlsx -o out/TKB.xlsx
```

Tuỳ chọn:

| Tham số | Ý nghĩa |
|---|---|
| `-o, --output` | File TKB xuất ra (mặc định `out/TKB.xlsx`) |
| `--staff-out` | File nhân sự cập nhật (mặc định `<thư mục output>/<tên input>_cap_nhat.xlsx`) |
| `--program` | File chương trình học (cột `Môn học`, `Khối 1..5`); mặc định dùng chương trình trong `tkb/config.py` |
| `--time-limit` | Giới hạn thời gian bước xếp giờ, giây (mặc định 120) |
| `--no-student-rules` | Tắt luật bảo vệ học sinh (dùng để tìm nguyên nhân khi không xếp được) |
| `--merge-enhanced` | Tính TV/Toán tăng cường chung với TV/Toán trong giới hạn 2 tiết/buổi |

Chạy test: `python -m pytest -q`

## Đầu vào

File Excel có 3 cột **Tên**, **Chức vụ**, **Số tiết**.

- Chức vụ = tên chức vụ + số thứ tự: `chủ nhiệm 1/1`, `bộ môn 4`, `tiếng anh 2`, `quản lý 1`...
- Thêm chữ `ts` nếu giáo viên hưởng chế độ thai sản: `bộ môn 5 ts`, `chủ nhiệm 5/5 ts`.
- Danh sách lớp lấy từ các dòng `chủ nhiệm khối/stt`, vì mỗi lớp luôn có một GVCN.
- Số tiết là **mức tối đa** mỗi tuần của giáo viên.

## Đầu ra

1. **`TKB.xlsx`**
   - Sheet **Khối 1…5**: định dạng theo `data/Output_Template_TKB_V5_Formatted.xlsx`.
     - Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
     - Cột LỚP gộp 7 hàng; cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 1–3).
     - Mỗi ô ghi môn và chức vụ trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `chủ nhiệm 1/1`. Chiều Thứ 6 ghi `Nghỉ`.
     - Font Times New Roman 10, dòng tiêu đề nền xám nhạt, viền mảnh.
   - Sheet **Danh sách nhân sự**: danh sách đã cập nhật, kèm số tiết thực dạy. Người bổ sung có tên `chưa có`, Số tiết ghi theo **định mức tuyển đầy đủ** của chức vụ (bộ môn: 23), dù thực dạy có thể ít hơn.
   - Sheet **Thống kê**:
     - Các chức vụ thiếu và số tiết thiếu, kèm chi tiết lớp/môn.
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

**Luật bảo vệ học sinh** (đặc tả V15)
- Không xếp môn nặng vào tiết 7.
- Buổi sáng không quá 3 tiết nặng liên tiếp; buổi chiều không quá 2.
- Mỗi buổi tối đa 2 tiết Tiếng Việt và 2 tiết Toán.

**Mục tiêu mềm**
- Cân bằng số tiết mỗi ngày của giáo viên.
- Ít tiết trống giữa buổi.
- Rải đều các môn trong tuần.
- Hạn chế chia một lớp-môn cho hai giáo viên.

## Cách giải

1. **Phân công** (chưa xếp giờ): CP-SAT tìm số tiết mỗi giáo viên dạy cho từng lớp-môn. Mục tiêu đầu tiên là ít tiết thiếu nhất, rồi ít người bổ sung nhất; sau đó mới đến hạn chế chia môn và cân bằng tải. Kết quả này là cận dưới của bài toán.
2. **Xếp giờ** với phân công cố định. Nếu xếp được thì nghiệm đạt đúng cận dưới ở bước 1.
3. **Dự phòng:** nếu bước 2 không xếp được, chương trình giải mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ) với thêm giáo viên bổ sung dự phòng.

Sau khi giải, `tkb/checker.py` kiểm tra lại mọi luật bắt buộc trên TKB, độc lập với solver.

## Cấu trúc mã nguồn

| File | Nội dung |
|---|---|
| `tkb/config.py` | Toàn bộ tham số nghiệp vụ: chương trình, khung giờ, quyền dạy, thứ tự cắt/bù, trọng số |
| `tkb/staff.py` | Đọc và kiểm tra file nhân sự |
| `tkb/program.py` | Đọc file chương trình học (tuỳ chọn) |
| `tkb/allocation.py` | Phân phần GVCN, sinh lớp-môn và danh sách giáo viên được dạy, sinh giáo viên bổ sung |
| `tkb/solver.py` | Mô hình CP-SAT |
| `tkb/checker.py` | Kiểm tra độc lập các luật bắt buộc |
| `tkb/writer.py` | Xuất Excel |
