# Xếp thời khóa biểu tự động (TKB)

Chương trình Python đọc **một file Excel** (danh sách nhân sự và chương trình học của trường) và xếp
thời khóa biểu tuần cho toàn trường bằng OR-Tools CP-SAT. Trước khi xếp, chương trình **dự toán** số tiết
thiếu, số tiết bù của từng người, số người cần tuyển và in ra màn hình. Khi trường thiếu người, có hai chế độ,
**dùng chung một TKB**:

- **Bù giờ** (`bu_gio`): GVCN và bộ môn dạy bù vượt định mức, mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần
  (`main.py`: 3, vì file của trường với 2 thì thiếu 17 tiết; dòng lệnh mặc định 2). Bù hết mức vẫn
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
| `SO_TIET_BU_TOI_DA` | Số tiết bù tối đa mỗi GVCN/bộ môn mỗi tuần; chế độ tuyển: người mới nhận đúng các tiết bù này. File của trường cần 3 (với 2 thì thiếu 17 tiết) | `3` |
| `LUAT_HOC_SINH` | Áp dụng luật bảo vệ học sinh | `True` |
| `THOI_GIAN_TOI_DA` | Thời gian cho bước xếp giờ, xấp xỉ giây: xếp nhanh một TKB rồi xếp lại từng vùng cho tốt dần (mục [Cách giải](#cách-giải)); tăng lên để TKB đẹp hơn. **Để trống (`None`/`""`) hoặc `0` thì không giới hạn**: xếp lại đến khi một vòng không còn cải thiện (thường 9–17 phút); bấm Ctrl+C để dừng sớm (sau vài giây), TKB tốt nhất vẫn được ghi ra. Cần nhanh thì đặt `600` (≈ 4–6 phút, TKB kém hơn một chút) | `1200` (≈ 9–13 phút) |
| `CHAY_TAI_LAP_DUOC` | `True`: chạy lại bao nhiêu lần, trên máy nào cùng hệ điều hành cũng ra đúng một kết quả, ở cả hai chế độ (xem điều kiện bên dưới); `False`: dừng theo giây thực, mỗi lần có thể khác | `True` |
| `FILE_TKB`, `FILE_TKB_CHUC_VU`, `FILE_THONG_KE` | Tên file TKB (chỉ thời khóa biểu), TKB ghi thêm chức vụ (Mã GV) trong mỗi ô, và file thống kê số tiết từng môn của giáo viên | `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `Thong_Ke.xlsx` |
| `SO_LUONG` | Số luồng tìm kiếm song song của bộ giải; nên ≥ số nhân CPU. Đổi số này thì TKB ra khác (vẫn đúng luật) | `8` |
| `GIU_TKB_DA_XEP` | `FILE_VAO` là file vào cập nhật của lần chạy trước (`<tên file vào>_cap_nhat.xlsx`, có sheet **TKB đã xếp**): `True` thì dùng lại đúng TKB đó, không xếp lại, nếu vẫn đúng mọi luật (xem [Tuyển được người](#tuyển-được-người-giữ-nguyên-tkb)); `False` thì luôn xếp lại từ đầu | `True` |

   - Đường dẫn tương đối được tính từ thư mục chứa `main.py`.
   - **Chạy lại, hoặc chạy ở máy khác cùng hệ điều hành, ra đúng TKB cũ** khi `CHAY_TAI_LAP_DUOC = True` và giữ nguyên: file vào, các hằng số trong `main.py`, phiên bản thư viện (cài bằng `pip install -r requirements.txt`). Xem mục [Chạy trên máy khác](#chạy-trên-máy-khác).
   - **Không giới hạn thời gian** (`THOI_GIAN_TOI_DA` để trống hoặc `0`): bước dự toán và phân công xong ngay; bước xếp giờ xếp lại từng vùng đến khi một vòng không còn cải thiện rồi tự dừng, vẫn tái lập được. Với file của trường bản trước (chưa có hai cơ sở), mặc định 1200 đã ra đúng TKB của chế độ không giới hạn, trên cả Linux và Windows; chế độ không giới hạn có thể lâu hơn (Windows giả lập khoảng 16 phút) vì chạy thêm các vòng cho tới khi biết chắc không còn cải thiện. Bấm **Ctrl+C** để dừng sớm: chương trình dừng sau vùng đang xếp (vài giây), vẫn kiểm tra luật và ghi đủ các file ra; dừng bằng tay thì mỗi lần có thể ra TKB khác nhau.
   - Trên Windows, viết đường dẫn dạng `r"C:\Users\ten\TKB\input.xlsx"` hoặc `"C:/Users/ten/TKB/input.xlsx"`.
2. Bấm **Run ▶** (VS Code, PyCharm...) hoặc chạy `python main.py`.
3. Kết quả nằm trong `THU_MUC_OUT`: `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `Thong_Ke.xlsx` và `<tên file vào>_cap_nhat.xlsx`. Trường có lớp ở cơ sở 2 thì mỗi file TKB tách làm hai: `TKB_diem_chinh.xlsx` / `TKB_diem_phu.xlsx` và `TKB_chuc_vu_diem_chinh.xlsx` / `TKB_chuc_vu_diem_phu.xlsx`. Khi ghi ra thư mục dự án, các file này đã được `.gitignore` bỏ qua để không lỡ đưa tên giáo viên lên git. Chế độ bù giờ mà thiếu tiết thì chỉ có `Thong_Ke.xlsx` (bảng tiết thiếu) và `main.py` trả về mã 3.

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
| `--time-limit` | Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 1200; `0` = không giới hạn: xếp lại đến khi hết cải thiện, Ctrl+C để dừng sớm) |
| `--non-reproducible` | Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau |
| `--mode` | `tuyen_them` (mặc định) hoặc `bu_gio` |
| `--max-overtime` | Số tiết bù tối đa mỗi người; chế độ tuyển: người mới nhận các tiết bù này (mặc định 2) |
| `--no-student-rules` | Tắt luật bảo vệ học sinh (dùng để tìm nguyên nhân khi không xếp được) |

Mã thoát: `0` đạt; `1` lỗi file vào hoặc không xếp được; `2` TKB sai luật bắt buộc; `3` chế độ bù giờ thiếu tiết.

Chạy test: `python -m pytest -q`

## Tuyển được người: giữ nguyên TKB

File vào cập nhật (`<tên file vào>_cap_nhat.xlsx`) lưu luôn TKB đã xếp ở sheet **TKB đã xếp** (mỗi tiết một dòng: Lớp, Thứ, Tiết, Môn, Mã GV, Tiết Bù; ô đầu cột Mã Kết Quả ghi mã kết quả, ô đầu cột Mã Quy Định ghi mã các quy định đã dùng).

1. Chạy chế độ tuyển thêm. File vào cập nhật có thêm các dòng `chưa có` (vd Bộ Môn 5–8).
2. Tuyển được người thì mở file vào cập nhật, **chỉ đổi chữ `chưa có` thành tên người mới**. Không đổi thứ tự dòng, vì giáo viên được khớp theo Mã GV (vd `Bộ Môn 5` là người thứ 5 trong chức vụ Bộ Môn).
3. Đặt `FILE_VAO` là file đó, `GIU_TKB_DA_XEP = True` (mặc định), rồi chạy. Chương trình in `Dùng lại TKB đã xếp trong file vào`, không xếp lại (chạy vài giây). TKB giữ nguyên từng ô, **mã kết quả giữ nguyên**; TKB và file thống kê ghi tên người mới.

- Chạy ở chế độ nào cũng được: người mới giờ là bộ môn thật, dạy trong định mức, nên không ai phải bù.
- Trước khi dùng lại, chương trình kiểm tra TKB đó với file vào mới theo mọi luật bắt buộc. Nếu file bị sửa làm TKB cũ sai luật (vd hạ định mức của một người xuống dưới số tiết đang dạy, thêm buổi nghỉ trùng tiết đang dạy, sửa chương trình học), chương trình in lý do rồi **xếp lại từ đầu**.
- Sửa sheet `QUY ĐỊNH` của file đó (vd thêm môn nặng) thì chương trình biết quy định đã đổi (mã quy định khác) và **xếp lại từ đầu** theo quy định mới.
- Muốn xếp lại từ đầu dù TKB cũ vẫn đúng luật: đặt `GIU_TKB_DA_XEP = False` (dòng lệnh: `--xep-lai`).
- Cũng dùng được để có lại đúng TKB của máy khác: lấy file vào cập nhật của bản chạy trên Linux, chạy trên máy Windows thì ra đúng TKB bản Linux (cùng mã kết quả), và ngược lại.

## Chạy trên máy khác

Ở chế độ tái lập (`CHAY_TAI_LAP_DUOC = True`, không bấm Ctrl+C), cùng file vào và cùng các hằng số trong `main.py` thì **chạy lại bao nhiêu lần, trên máy nào cùng hệ điều hành cũng ra cùng một TKB**, với điều kiện:

1. Cài đúng phiên bản thư viện: `pip install -r requirements.txt` (OR-Tools 9.15.6755, openpyxl 3.1.5). Nếu OR-Tools khác bản này, chương trình in cảnh báo.
2. Không sửa code trong `tkb/`.

**Không ảnh hưởng kết quả:** máy nhanh hay chậm, số nhân CPU, máy đang bận, phiên bản Python (đã thử 3.10–3.14), thư mục đặt dự án. Bộ giải dừng theo lượng tính toán chứ không theo giây thực, nên máy chậm chỉ chạy lâu hơn.

**Mã kết quả:** mỗi lần chạy in ra màn hình một mã, ví dụ `Mã kết quả: 6523-7A90-932C`. Mã này là mã băm của toàn bộ TKB. Hai máy cùng mã là cùng TKB, khỏi phải so từng ô.

**Theo hệ điều hành:** bước dự toán và phân công viết bằng Python thuần nên mọi máy ra cùng một phân công. Bước xếp giờ dùng OR-Tools: bản Windows và bản Linux ra TKB khác nhau (cùng đạt luật, cùng phân công), nên mỗi hệ điều hành có mã tham chiếu riêng. Chưa thử macOS và chip ARM (Apple M1).

**Kiểm tra một máy mới** (không cần sửa `main.py`):
- Nhanh (khoảng 20 giây): `python -m pytest tests/test_reproducible.py`. Test so mã kết quả của một trường nhỏ với mã tham chiếu của hệ điều hành đó. Qua là máy đó ra đúng kết quả như các máy khác.
- Đầy đủ (10–15 phút): `python main.py` với các hằng số mặc định (file của trường `data/INPUT_V8.xlsx`), rồi so mã kết quả với bảng. Mã trong bảng ứng với file `data/INPUT_V8.xlsx` hiện tại; trường sửa file thì mã đổi theo.

| Hệ điều hành | Mã kết quả `data/INPUT_V8.xlsx` | Đã kiểm |
|---|---|---|
| Windows x86-64 | **`08F4-E2C6-3470`** | Máy ảo GitHub Actions: Windows Server 2022 và 2025, Python 3.12 và 3.14 |
| Linux x86-64 | **`5C2B-510F-5156`** | Python 3.11 |

**Đã sửa lỗi "thỉnh thoảng ra TKB khác":** trước đây, dù đã bật chế độ tất định của OR-Tools, chạy lặp cùng một mô hình vẫn có lúc ra TKB khác (6 lần ra 3 TKB). Nguyên nhân là các luồng của bộ giải chia sẻ mệnh đề học được và cận ở mức gốc cho nhau, và phần này không tất định. Chế độ tái lập nay tắt hai loại chia sẻ đó (`tkb/solver.py`, hàm `_configure`): chạy lặp 8 lần ra 8 lần cùng mã, chất lượng không giảm. Máy ảo Windows của GitHub Actions kiểm tra việc này mỗi lần đổi code (`.github/workflows/windows.yml`): 4 máy (Windows Server 2022 và 2025, Python 3.12 và 3.14), mỗi máy chạy 2 lần, mọi mã phải trùng nhau.

## Đầu vào

**Một file Excel duy nhất theo mẫu V8** (ví dụ `data/INPUT_V8.xlsx`) gồm 2 sheet bắt buộc `NHÂN SỰ`, `CHƯƠNG TRÌNH HỌC` và sheet `QUY ĐỊNH` không bắt buộc (các luật nghiệp vụ). Chương trình tìm sheet theo tên, không phân biệt hoa thường; các sheet khác (ví dụ `HƯỚNG DẪN`) được bỏ qua. Tiêu đề cột phải đúng mẫu: `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần`, thêm 5 cột không bắt buộc `Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ`.

**Sheet `NHÂN SỰ`:**

| Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ |
|---|---|---|---|---|---|---|---|---|
| Nguyễn Văn A | Chủ Nhiệm | 1D15 | 19 | | Có | | | |
| Trần Thị B | Chủ Nhiệm | 3D23 | 15 | Có | | Có | | 2 buổi chiều |
| Lê Văn C | Bộ Môn | | 19 | Có | | | | Chiều T5, Sáng T6 |
| Phạm D | Tiếng Anh | | 23 | | | | 3D17, 3D18 | |

- **Họ và Tên** có thể để trống (vì bảo mật). Khi đó TKB ghi **Mã GV**, ví dụ `Chủ Nhiệm 1/1`, `Tiếng Anh 2`, `Bộ Môn 3`.
- **Chức Vụ**:
  - `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý`, hoặc **đúng tên một môn** trong sheet `CHƯƠNG TRÌNH HỌC`, ví dụ `Tiếng Anh`, `Thể Dục`, `Tin Học`. Chức vụ trùng tên môn là giáo viên chuyên biệt, chỉ dạy môn đó.
  - Không có danh sách chức vụ cố định trong code, nên trường có môn mới (ví dụ `Múa`) chỉ cần thêm dòng môn và giáo viên `Múa`.
  - **Không ghi số thứ tự**: chương trình tự đánh số theo thứ tự dòng (Bộ Môn thứ nhất là `Bộ Môn 1`, thứ hai là `Bộ Môn 2`…).
  - Chức vụ không khớp môn nào thì báo lỗi kèm số dòng.
- **Lớp** chỉ ghi cho Chủ Nhiệm, dạng **khối/số thứ tự** (`1/1`, `5/5`) hoặc **khối rồi tên lớp** (`1D15`, `2A`); khối là các chữ số đầu. Nên định dạng cột là chữ (Text) để Excel không đổi `1/1` thành ngày tháng.
- **Số Tiết/Tuần** là mức tối đa mỗi tuần của từng người (ai được giảm tiết thì ghi mức đã giảm).
- **Thai Sản**, **Hợp Đồng**, **Cơ sở 2**: ghi `Có` hoặc để trống.
  - Thai sản: không dạy bù, và chỉ dạy các lớp ở cơ sở 2. GVCN thai sản thì lớp phải ở cơ sở 2.
  - Hợp đồng: khi phải bù, GVCN hợp đồng bù trước GVCN khác, bộ môn hợp đồng bù trước bộ môn khác.
  - Cơ sở 2: trên dòng Chủ Nhiệm nghĩa là lớp đó học ở cơ sở 2; trên dòng khác nghĩa là GV đó chỉ dạy ở cơ sở 2.
- **Lớp Đang Dạy** (GV bộ môn, chuyên biệt): các lớp người đó dạy trong TKB cũ, cách nhau bằng dấu phẩy. TKB mới ưu tiên giữ người đó ở khối cũ, sau đó ở lớp cũ.
- **Buổi Nghỉ**: buổi cố định (`Chiều T5`, `Sáng thứ 6`) và/hoặc số buổi bất kỳ (`2 buổi chiều`, `1 buổi sáng`, `2 buổi`), cách nhau bằng dấu phẩy; không phân biệt hoa thường, có dấu hay không. Chương trình không xếp tiết vào các buổi đó; với "số buổi bất kỳ" thì chương trình tự chọn buổi. GVCN không nghỉ buổi sáng được, vì tiết 1 luôn do GVCN dạy.
- Các cột khác (ví dụ cột STT, cột ghi chú) được bỏ qua, ghi gì cũng được.
- Danh sách lớp lấy từ các dòng Chủ Nhiệm, vì mỗi lớp luôn có một GVCN. Nếu dãy lớp của một khối bị hụt (ví dụ có 1/3, 1/5 mà không có 1/4) thì chương trình cảnh báo.
- Khi file có lỗi, chương trình **liệt kê tất cả lỗi một lần** kèm số dòng (ví dụ `Lớp 1/1 có hai Chủ Nhiệm (dòng 11 và 26)`).

**Sheet `CHƯƠNG TRÌNH HỌC` (bắt buộc):** Môn học | Khối 1 … Khối n (số tiết/tuần). Dòng `Tổng` (nếu có) được bỏ qua.
- Danh sách môn và tên môn lấy nguyên từ file, TKB in đúng tên trong file. Riêng các môn ở quy định `Tên môn viết tắt trong TKB` (mặc định HĐTN, TNXH, TV tăng cường) được viết tắt trong ô TKB.
- Môn nào trùng tên một môn có trong quy định (sheet `QUY ĐỊNH`) thì nhận luật đó. So khớp không phân biệt hoa thường, dấu câu và chữ "và": `Lịch Sử và Địa Lý` khớp `Lịch sử - Địa lý`.
- Nếu quy định nhắc một môn mà chương trình học không có (thường do gõ khác tên), chương trình cảnh báo.

**Sheet `QUY ĐỊNH` (không bắt buộc):** các luật nghiệp vụ, nhà trường sửa trong Excel, không cần sửa code. Cột `Quy định | Giá trị | Ghi chú`, mỗi dòng một quy định; chương trình chỉ đọc hai cột đầu.
- Quy định nào không có dòng, hoặc file không có sheet này, thì dùng giá trị mặc định trong `tkb/config.py` (cột Mặc định dưới đây). File có sheet ghi đúng giá trị mặc định cho cùng TKB, cùng mã kết quả như file không có sheet.
- Tên môn ghi như trong sheet `CHƯƠNG TRÌNH HỌC`; nhiều môn cách nhau bằng dấu phẩy; ô để trống là "không có môn nào". Ngày ghi `Thứ 2` … `Thứ 7` (hoặc `T2`); tiết ghi số, buổi chiều đánh số nối tiếp buổi sáng; ô cố định ghi `Thứ 2 tiết 1`. Các mục dạng `A = B` cách nhau bằng dấu chấm phẩy.
- Ghi sai (tên quy định lạ, ngày/tiết không có trong khung giờ, chức vụ bù khác Chủ Nhiệm/Bộ Môn…) thì chương trình liệt kê mọi lỗi một lần kèm số dòng, không xếp.
- Màn hình in `Quy định: sheet QUY ĐỊNH, khác mặc định: …` để biết quy định nào đang khác mặc định.
- File vào cập nhật (`_cap_nhat`) luôn có sheet này: file vào chưa có thì chương trình ghi thêm các quy định đã dùng.
- Trọng số mục tiêu, tham số xếp giờ vẫn ở `tkb/config.py`; số tiết bù tối đa ở `main.py` (`SO_TIET_BU_TOI_DA`).

| Quy định | Mặc định | Ý nghĩa |
|---|---|---|
| Ngày học | Thứ 2, Thứ 3, Thứ 4, Thứ 5, Thứ 6 | Các ngày học, liền nhau từ Thứ 2 (có thể thêm Thứ 7). Ngày nào cũng học buổi sáng. |
| Ngày học buổi chiều | Thứ 2, Thứ 3, Thứ 4, Thứ 5 | Các ngày có buổi chiều; để trống là không học buổi chiều. |
| Số tiết buổi sáng | 4 | Buổi sáng là tiết 1 đến tiết này. |
| Số tiết buổi chiều | 3 | Buổi chiều là các tiết tiếp theo, vd sáng 4 tiết, chiều 3 tiết thì chiều là tiết 5, 6, 7. |
| Môn HĐTN | Hoạt động trải nghiệm | Môn chào cờ, sinh hoạt lớp: có các tiết cố định dưới đây. |
| Tiết HĐTN cố định | Thứ 2 tiết 1, Thứ 6 tiết 4 | Luật cứng: mọi lớp học môn HĐTN đúng các ô này, vd Thứ 2 tiết 1, Thứ 6 tiết 4. |
| Ngày xếp tiết HĐTN còn lại | Thứ 3, Thứ 4, Thứ 5 | Luật cứng: các tiết HĐTN còn lại chỉ xếp vào các ngày này (mục tiêu mềm: gần cuối buổi). |
| Tiết luôn do GVCN dạy | 1 | Luật cứng: tiết này ở mọi ngày do GVCN của lớp dạy; để trống là không có. |
| Môn GVCN nhận trọn | Tiếng Việt, Toán, Hoạt động trải nghiệm, Khoa học, Lịch sử - Địa lý, Đạo đức | GVCN nhận hết các môn này của lớp mình; luật cứng: môn nào phải chia cho người khác thì tiết đầu tiên trong tuần do GVCN dạy. |
| Thứ tự cắt khi GVCN vượt định mức | Tiếng Việt, Toán, Khoa học, Lịch sử - Địa lý | Các môn trên vượt định mức thì cắt bớt theo thứ tự này, mỗi môn GVCN giữ ít nhất 1 tiết. |
| Thứ tự nhận thêm khi GVCN thiếu định mức | Tiếng Việt tăng cường, Toán tăng cường, Tự nhiên xã hội, Kỹ năng sống, Công nghệ | GVCN nhận thêm các môn này theo thứ tự cho đủ định mức (không nhận môn của GV chuyên biệt). |
| Môn chỉ GVCN dạy | Hoạt động trải nghiệm | Luật cứng: chỉ GVCN của lớp được dạy. |
| Môn GV bộ môn không dạy | Tiếng Anh, Tin học, Hoạt động trải nghiệm | GV bộ môn dạy được mọi môn trừ các môn này; môn chưa có GV chuyên biệt thì chương trình tuyển thêm. |
| Quản lý dạy | Kỹ năng sống khối 4 | Môn và khối quản lý được dạy, vd Kỹ năng sống khối 4; chỉ vài lớp: Kỹ năng sống khối 4 lớp 4/1, 4/2. Nhiều mục cách nhau bằng dấu chấm phẩy. |
| Chức vụ được dạy bù | Chủ Nhiệm, Bộ Môn | Chỉ ghi Chủ Nhiệm, Bộ Môn. GVCN chỉ bù ở lớp mình và bù trước; bộ môn bù khi GVCN đã bù hết mức. |
| Môn chuyên biệt GVCN được bù | Âm nhạc, Mỹ thuật | Môn của GV chuyên biệt mà GVCN vẫn được dạy bù ở lớp mình (nhận sau cùng). |
| Môn tăng cường đi với môn chính | Tiếng Việt tăng cường = Tiếng Việt; Toán tăng cường = Toán | Mỗi mục: môn tăng cường = môn chính, cách nhau bằng dấu chấm phẩy. Hai môn tính chung một nhóm môn; luật cứng: tiết tăng cường đứng sau mọi tiết chính trong ngày và ngày đó phải có tiết chính. |
| Số tiết tối đa một nhóm môn mỗi buổi | 2 | Luật cứng; môn có từ 2 tiết trong một buổi thì các tiết đó phải liền nhau. |
| Số tiết tối đa mỗi ngày của môn | Toán = 1 | Luật cứng, vd Toán = 1; chỉ áp dụng khi số tiết/tuần của môn không quá số ngày học. |
| Ghép cặp 2 tiết liền khi nhóm môn có từ | 6 | Luật cứng: nhóm môn có từ ngần ấy tiết/tuần và tổng số tiết chẵn thì xếp thành các cặp 2 tiết liền, cùng người dạy. |
| Nhóm môn không ghép cặp | Toán, Hoạt động trải nghiệm | Các nhóm môn (ghi môn chính) không áp dụng luật ghép cặp ở trên. |
| Môn nặng | Tiếng Việt, Toán, Tiếng Việt tăng cường, Toán tăng cường, Tiếng Anh, Khoa học, Tin học | Mục tiêu mềm: hạn chế xếp các môn này vào các tiết ở dòng dưới. |
| Tiết hạn chế môn nặng | 7 | Mục tiêu mềm: mỗi tiết môn nặng ở các tiết này bị trừ điểm. |
| Môn ưu tiên buổi sáng | Tiếng Việt, Toán | Mục tiêu mềm: mỗi tiết các môn này ở buổi chiều bị trừ điểm, và các môn này được rải đều hơn. |
| Tên môn viết tắt trong TKB | Hoạt động trải nghiệm = HĐTN; Tự nhiên xã hội = TNXH; Tiếng Việt tăng cường = TV tăng cường | Mỗi mục: tên môn = chữ ghi trong ô TKB, cách nhau bằng dấu chấm phẩy; môn khác ghi đúng tên. |

Chỉ đọc mẫu V8. File mẫu cũ (V5–V7: chức vụ ghi kèm số như `bộ môn 5`, chương trình học ở file riêng) không còn đọc được: tạo file mẫu trống rồi chép dữ liệu sang, bỏ số thứ tự ở cột Chức Vụ.

File vào mẫu trống có sẵn: **`data/Input_Template_V8.xlsx`**. Tạo lại (hoặc tạo ở chỗ khác):

```bash
python -m tkb.template data/Mau_Input.xlsx
```

File mẫu đơn giản, tiếng Việt: chữ đen, không tô nền, viền mảnh, không cố định dòng/cột, không danh sách thả xuống, không ghi chú trong ô, không sheet ẩn. Gồm 4 sheet: `NHÂN SỰ`, `CHƯƠNG TRÌNH HỌC`, `QUY ĐỊNH` (điền sẵn giá trị mặc định) và `HƯỚNG DẪN` (cách ghi từng cột, từng sheet). Cột Lớp, Lớp Đang Dạy định dạng chữ để Excel không đổi `1/1` thành ngày tháng.

## Cái gì nằm trong file vào, cái gì nằm trong code

| Nằm trong file vào | Nằm trong code |
|---|---|
| Danh sách môn, tên môn, số tiết từng khối (`CHƯƠNG TRÌNH HỌC`) | Giá trị mặc định của các quy định (`tkb/config.py`), dùng khi file không ghi |
| Giáo viên, chức vụ, lớp chủ nhiệm, số tiết, thai sản, hợp đồng, cơ sở 2, lớp đang dạy, buổi nghỉ (`NHÂN SỰ`) | Trọng số mục tiêu mềm (`config.Weights`) và tham số xếp giờ (`LNS_*`) |
| Danh sách lớp (suy ra từ các dòng Chủ Nhiệm), GV chuyên biệt (chức vụ trùng tên môn) | Định mức người cần tuyển (Số tiết lớn nhất của GV cùng chức vụ), luật mỗi buổi một cơ sở, thai sản không bù |
| Khung giờ, HĐTN, tiết của GVCN, môn GVCN nhận/cắt/nhận thêm, quyền dạy, ai được bù, luật bảo vệ học sinh, môn nặng, môn buổi sáng, tên viết tắt (`QUY ĐỊNH`) | Chế độ, số tiết bù tối đa, thời gian (`main.py`) |
| Style của các file ra (phông, cỡ chữ, viền, chiều cao dòng) | |

## Đầu ra

1. **`TKB.xlsx`**: **chỉ có thời khóa biểu**, mỗi khối một sheet **Khối 1…5**.
   - **Trường có hai cơ sở** (cột `Cơ sở 2`): tách thành **`TKB_diem_chinh.xlsx`** (các lớp cơ sở 1, điểm chính) và **`TKB_diem_phu.xlsx`** (các lớp cơ sở 2, điểm phụ); `TKB_chuc_vu.xlsx` cũng tách như vậy. Cột ngày ở hai file cùng độ rộng.
   - Mẫu: `data/Output_Template_TKB_V8.xlsx` (TKB của trường mẫu tên giả). Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
   - Cột LỚP gộp 7 hàng; cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 5–7); cột TIẾT ghi số tiết trong ngày. Cột LỚP chỉ ghi tên lớp, ví dụ `3D23` (lớp cơ sở 2 nằm ở file điểm phụ).
   - Mỗi ô ghi môn và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Tên để trống hoặc người cần tuyển thì ghi Mã GV (`Bộ Môn 6`); hai người trùng tên thì kèm Mã GV. Chiều Thứ 6 ghi `Nghỉ`.
   - Các cột ngày ở mọi sheet cùng độ rộng, nới theo dòng dài nhất của cả trường (tối đa 30); tên dài hơn thì xuống dòng và hàng tự cao thêm. Khi in: khổ ngang, co vừa chiều rộng 1 trang.
   - **`TKB_chuc_vu.xlsx`**: cùng TKB, mỗi ô thêm dòng thứ 3 là chức vụ (Mã GV), ví dụ `Tiếng Việt` / tên / `Bộ Môn 4`, để theo dõi ai dạy tiết nào.
2. **`Thong_Ke.xlsx`**: **một bảng** (sheet `Thống kê`), mẫu: `data/Output_Template_Thong_Ke_V8.xlsx`.
   - Mỗi giáo viên một dòng, theo thứ tự file nhân sự, rồi đến người cần tuyển (tên `tuyển thêm`).
   - Cột: **Họ và Tên | Chức Vụ** (Mã GV, ví dụ `Chủ Nhiệm 1/1`, `Bộ Môn 2`) **| số tiết từng môn người đó dạy | Tổng Tiết | Số Tiết/Tuần** (định mức) **| Số Tiết Bù | Số Tiết Dư**. Tiết bù: dạy vượt định mức (chế độ bù giờ); tiết dư: định mức − Tổng Tiết khi dạy ít hơn định mức. Trường có lớp ở cơ sở 2 thì thêm 2 cột cho người **di chuyển giữa hai cơ sở**: **Buổi Ở Cơ Sở 2** (vd `Sáng T3, Chiều T5`) và **Đổi Cơ Sở Trong Ngày** (vd `T5: sáng cơ sở 1, chiều cơ sở 2`); dòng Tổng ghi số người, số lần, dưới bảng có chú thích. Chỉ có cột cho các môn có người dạy, theo thứ tự trong chương trình học; ô trống là không dạy môn đó. Cuối bảng có dòng **Tổng**.
   - **Tô màu cả dòng** để biết ai bù, ai thêm: chế độ bù giờ tô **vàng** dòng người dạy bù (vượt định mức); chế độ tuyển thêm tô **xanh lá** dòng người cần tuyển; người còn dư tiết tô **xanh dương**. Trong dòng người dạy bù, **ô môn có tiết bù tô cam**; số tiết bù từng môn ghi bằng chữ ở cột **Môn Dạy Bù**, ví dụ `TV tăng cường 2, TNXH 1`. Dưới bảng có chú thích màu kèm số người, số tiết, ví dụ `Dạy bù (vượt định mức): 28 người, 56 tiết`, `Môn có tiết dạy bù: 40 ô, 56 tiết (số tiết từng môn ở cột Môn Dạy Bù)`, `Cần tuyển thêm: 3 người, 56 tiết`, `Dạy ít hơn định mức (còn dư tiết): 4 người, 17 tiết`.
   - Chế độ, dự toán, mã kết quả, kết quả kiểm tra luật, người cần tuyển, dạy bù và số liệu cơ sở, thai sản, buổi nghỉ, giữ phân công cũ chỉ in ra màn hình.
   - **Chế độ bù giờ mà thiếu tiết:** không ra TKB; file này chỉ có sheet `Thiếu tiết`: **Lớp | Môn | Số Tiết Thiếu | Lý Do** và dòng Tổng.
3. **`<tên file vào>_cap_nhat.xlsx`**: bản chép của file vào (đủ các sheet; file vào chưa có sheet `QUY ĐỊNH` thì thêm sheet này với các quy định đã dùng). Sheet NHÂN SỰ có thêm các dòng `chưa có` ở cuối (chép style của dòng trên), Số tiết = định mức tuyển; bên phải thêm cột **Mã GV**, **Số Tiết Thực Dạy** (chế độ bù: **Số Tiết Bù**) và **Số Tiết Dư** (định mức − thực dạy, khi dạy ít hơn định mức). Đây cũng là **bản thống kê gọn theo mẫu file vào**: tô nền cả dòng người dạy bù (vàng), người cần tuyển (xanh lá), người còn dư tiết (xanh dương); sheet **Chú thích** giải thích các cột và màu bằng chữ thường. File này dùng làm đầu vào cho lần chạy sau được (các cột thêm được bỏ qua khi đọc, chạy lại thì ghi đè). File còn có sheet **TKB đã xếp**: nạp lại file này thì TKB được giữ nguyên nếu vẫn đúng luật (mục [Tuyển được người](#tuyển-được-người-giữ-nguyên-tkb)). File gốc không bị sửa.
4. **Mọi file kết quả chỉ có chữ, số và màu:** không có ghi chú (comment) trong ô, không có công thức, không cố định dòng/cột, không danh sách thả xuống hay định dạng theo điều kiện. Công thức trong file vào (ví dụ STT `=ROW()-1`) được chép sang file cập nhật dưới dạng giá trị.

**Style:** mọi file ra chép style của sheet NHÂN SỰ trong file vào: phông, cỡ chữ, tiêu đề in đậm, viền, căn lề và chiều cao dòng (làm tròn, ví dụ 24,95 → 25). Bảng ghi tiêu đề cột ở dòng 1 như file vào. Riêng hàng tiết trong TKB cao đủ 2 dòng chữ (môn và giáo viên).

## Quy tắc nghiệp vụ

Dưới đây là các quy tắc với giá trị mặc định. Phần lớn sửa được ở sheet `QUY ĐỊNH` của file vào (mục [Đầu vào](#đầu-vào)); giá trị mặc định nằm trong `tkb/config.py`.

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

**Hai cơ sở, thai sản, buổi nghỉ** (theo các cột không bắt buộc của file vào; luật cứng, bộ kiểm tra kiểm lại)
- **Mỗi buổi, một giáo viên chỉ dạy ở một cơ sở.** Ví dụ sáng Thứ 2 có tiết ở cơ sở 2 thì cả buổi sáng đó người ấy chỉ dạy các lớp cơ sở 2. Giữa buổi sáng và buổi chiều thì đổi cơ sở được, nhưng bị hạn chế bằng mục tiêu mềm (xem dưới). Áp dụng cho mọi người, kể cả người cần tuyển (để hai chế độ vẫn chung một TKB).
- **Thai sản:** không dạy bù; chỉ dạy các lớp ở cơ sở 2.
- **Buổi nghỉ:** không có tiết nào trong buổi nghỉ cố định; đủ số buổi trống đã xin.
- Lớp ở cơ sở 2 nằm ở file TKB điểm phụ (`..._diem_phu.xlsx`); cột LỚP chỉ ghi tên lớp.

**Các chức vụ khác**
- **Giáo viên chuyên biệt** (chức vụ trùng tên một môn, ví dụ Tiếng Anh, Tin Học, Thể Dục): chỉ dạy đúng môn đó. Môn bộ môn không được dạy (Tiếng Anh, Tin học) mà trường chưa có ai thì chương trình tự thêm chức vụ trùng tên môn để tuyển (ví dụ `Tin Học 1`).
- **Bộ môn:** dạy mọi môn trừ Tiếng Anh, Tin học và HĐTN. Nghĩa là bộ môn vẫn dạy thay được Thể dục, Âm nhạc, Mỹ thuật, nhưng chỉ phần vượt định mức của giáo viên chuyên biệt (dự toán in số tiết này).
- **Quản lý:** chỉ dạy Kỹ năng sống Khối 4, đúng bằng số tiết của mình. Chương trình tự chọn lớp.

**Dự toán** (in ra màn hình trước khi xếp, cả hai chế độ)
- Tổng tiết cần dạy = phần GVCN + GV chuyên biệt + quản lý + bộ môn + tiết bù + tiết thiếu.
- Biên bù: đã dùng bao nhiêu trên tối đa có thể bù, ví dụ `Bù: 56/68 tiết (GVCN 56/58, bộ môn 0/10), còn dư 12 tiết`. Còn dư ít nghĩa là chỉ cần bớt một người là chế độ bù không đủ.

**Chế độ bù giờ** (`CHE_DO = "bu_gio"`)
- Chỉ GVCN và bộ môn được dạy bù (vượt Số tiết định mức), mỗi người tối đa `SO_TIET_BU_TOI_DA` tiết/tuần.
- GVCN chỉ bù ở lớp mình, không bù môn của giáo viên chuyên biệt, **trừ Âm nhạc và Mỹ thuật** (`HOMEROOM_OVERTIME_SPECIALIST`; Tin học, Tiếng Anh, Thể dục thì không). Thứ tự môn: môn ưu tiên của GVCN (lấy lại tiết đã bị cắt) → TV tăng cường → Toán tăng cường → TNXH → Kỹ năng sống → Công nghệ → Âm nhạc, Mỹ thuật; ưu tiên nhận trọn một môn thay vì chia đôi. Âm nhạc, Mỹ thuật GVCN chỉ nhận phần giáo viên chuyên biệt và bộ môn không dạy hết (theo dự toán).
- GVCN bù trước; bộ môn chỉ bù khi GVCN đã bù hết mức. Bộ kiểm tra báo lỗi nếu bộ môn dạy bù ở một lớp mà GVCN lớp đó còn được bù và dạy được môn đó.
- Có cột `Hợp Đồng` thì thứ tự bù là: **GVCN hợp đồng → GVCN khác → bộ môn hợp đồng → bộ môn khác** (`overtime_homeroom_contract`, `overtime_homeroom`, `overtime_general_contract`, `overtime_general`).
- Chia đều trong từng nhóm trên: mọi người bù +1 rồi mới có người bù +2.
- GV đang hưởng thai sản không dạy bù.
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
- **Tiết tăng cường sau tiết chính:** tiết tăng cường là tiết luyện bài vừa học, nên trong một ngày phải có tiết chính cùng môn đứng trước nó và không có tiết chính nào đứng sau nó (Toán tăng cường sau Toán, TV tăng cường sau TV; `SUBJECT_GROUPS`). Không cần liền, không cần cùng người dạy, không cần buổi chiều. Với TV ghép cặp thì cặp có tiết tăng cường là "TV rồi TV tăng cường".
- Môn nặng ở tiết 7 không bị cấm, chỉ hạn chế bằng mục tiêu mềm (xem dưới).

**Mục tiêu mềm**
- **Buổi sáng dành cho Tiếng Việt và Toán**, như TKB của các trường khác (xem [`docs/Tham_Khao_TKB_Truong_Khac.md`](docs/Tham_Khao_TKB_Truong_Khac.md)):
  - mỗi tiết TV, Toán xếp vào buổi chiều bị phạt;
  - tiết tăng cường không có mục tiêu riêng: luật cứng "sau tiết chính" (xem trên) đã đặt nó sau TV, Toán;
  - đổi ở `MORNING_SUBJECTS`, trọng số `morning_core` (300), `core_spread`.

  Khối có nhiều tiết TV (vd khối 1: 14 tiết, mỗi buổi tối đa 2) vẫn phải có vài tiết TV buổi chiều. Mỗi lần chạy in ra số tiết TV, Toán còn ở buổi chiều.
- Hạn chế môn nặng ở tiết 7 (Toán, Tiếng Việt, tiết tăng cường, Tiếng Anh, Khoa học, Tin học; đổi ở `HEAVY_SUBJECTS`, `HEAVY_LATE_PERIODS`, trọng số `heavy_late` (1200)). Mỗi GV Tiếng Anh dạy 23 tiết trong 26 ô được dạy (4 ô là tiết 7), nên mỗi người còn ít nhất 1 tiết Tiếng Anh ở tiết 7.
- Cân bằng số tiết mỗi ngày của giáo viên.
- Ít tiết trống giữa buổi.
- **Cả ngày ở một cơ sở:** mỗi lần một giáo viên dạy sáng ở cơ sở này, chiều ở cơ sở kia bị phạt `campus_day_switch` (10000, gấp hơn 30 lần một tiết TV/Toán buổi chiều). Không để luật cứng vì với file của trường, luật cứng cả ngày không ra được TKB trong 1200. Màn hình in số lần còn phải đổi.
- Rải đều các môn trong tuần (`subject_spread` 40, TV/Toán `core_spread` 120). Khối 1 có 7 cặp TV trong 5 ngày nên luôn có 2 ngày học 4 tiết TV.
- Phân công: hạn chế chia một lớp-môn cho hai giáo viên; **giữ phân công của TKB cũ** (cột `Lớp Đang Dạy`: mỗi tiết dạy khác khối cũ phạt `keep_grade` 60, đúng khối nhưng khác lớp cũ phạt `keep_class` 10); gom lớp của một giáo viên vào ít khối; cân bằng tải. Giữ phân công cũ đứng sau số tiết thiếu, số tiết bù và "không chia lớp-môn", nhưng trước gom lớp và cân bằng tải. Màn hình in số tiết đúng khối cũ, đúng lớp cũ.

## Cách giải

1. **Dự toán và phân công** (`tkb/phan_cong.py`, Python thuần, dưới 1 giây, mọi máy như nhau):
   - luồng chi phí nhỏ nhất từ các lớp-môn sang giáo viên được dạy, không vượt định mức và số ô giờ giáo viên đó dạy được; ưu tiên ít tiết thiếu nhất, rồi ít tiết bù của bộ môn, rồi ít tiết bù của GVCN, mọi người +1 rồi mới +2;
   - GVCN nhận tiết bù ở lớp mình (môn ưu tiên trước, môn trọn vẹn, chia chẵn nhóm ghép cặp); phần còn lại chia cho bộ môn, GV chuyên biệt, quản lý, rồi tìm kiếm cục bộ bớt chia môn, gom lớp, cân bằng tải.
2. **Tiết bù → người mới:** các tiết bù (và, ở chế độ tuyển, tiết thiếu) giao cho người tuyển mới.
3. **Xếp giờ** với phân công cố định đó (`tkb/lns.py`), trong `THOI_GIAN_TOI_DA`:
   - **khởi đầu:** CP-SAT xếp toàn trường với 20% thời gian nhưng không quá 120 (không giới hạn: 120), được một TKB đúng luật;
   - **các vòng xếp lại:** mỗi vòng chấm điểm từng lớp-ngày theo các mục tiêu mềm (QA), rồi lần lượt xếp lại từng vùng, vùng xấu trước: từng lớp, các "điểm nóng" (lớp-ngày xấu nhất cùng các lớp chung giáo viên hôm đó), nhóm lớp của một giáo viên dùng chung, từng khối, từng cặp ngày. Mỗi vùng: giữ nguyên mọi tiết ngoài vùng, CP-SAT tìm cách xếp tốt hơn trong vùng, chỉ nhận khi tốt hơn. Luật bắt buộc luôn đúng;
   - **dừng** khi hết thời gian, khi một vòng tốt lên chưa tới 0,3% (không giới hạn: khi vòng không tốt lên), sau 10 vòng, hoặc khi bấm Ctrl+C. Màn hình in chi phí xếp giờ (tổng điểm phạt mềm) sau mỗi vòng.
   - Với file của trường bản trước (chưa có hai cơ sở), cách này cho TKB tốt hơn cả khi để một lần CP-SAT chạy 110 phút, ngay với 600 (khoảng 4–6 phút), và mặc định 1200 ra đúng TKB của chế độ không giới hạn. Kết quả là tốt nhất tìm được, không chứng minh là tối ưu.
   - File hiện tại có thêm hai cơ sở, thai sản, buổi nghỉ (44 nhân sự, bù tối đa +3), luật tiết tăng cường sau tiết chính và trọng số mới (môn nặng tiết 7: 1200, đổi cơ sở trong ngày: 10000): chi phí xếp giờ 28.220 (Linux) / 37.340 (Windows). Giáo viên dạy sáng một cơ sở, chiều cơ sở kia: 0 lần (Linux), 1 lần (Windows); trước khi có mục tiêu này: 21 lần. Môn nặng ở tiết 7: 6 tiết (đều là Tiếng Anh, thấp nhất có thể là 4); TV/Toán buổi chiều 38/408.

   Chế độ tuyển: giữ người mới. Chế độ bù: trả các ô đó về đúng người bù. Hai chế độ cùng vị trí môn.
4. **Dự phòng** (chỉ chế độ tuyển): nếu bước 3 không xếp được, giải một lần CP-SAT mô hình tích hợp (vừa chọn giáo viên vừa xếp giờ) với thêm giáo viên bổ sung dự phòng.

Sau khi giải, `tkb/checker.py` kiểm tra lại mọi luật bắt buộc trên TKB, độc lập với solver.

## Cấu trúc mã nguồn

| File | Nội dung |
|---|---|
| `main.py` | File chạy nhanh: sửa hằng số (file vào, thư mục ra, chế độ, luật học sinh, thời gian, tái lập) rồi bấm Run |
| `tkb/config.py` | Giá trị mặc định của các quy định (khi file vào không ghi), trọng số mục tiêu, tham số xếp giờ |
| `tkb/rules.py` | Đọc và kiểm tra sheet QUY ĐỊNH, dùng thay giá trị mặc định trong lúc chạy |
| `tkb/staff.py` | Đọc và kiểm tra file nhân sự |
| `tkb/template.py` | Tạo file vào mẫu V8 trống, đơn giản (NHÂN SỰ, CHƯƠNG TRÌNH HỌC, QUY ĐỊNH, HƯỚNG DẪN) |
| `tkb/program.py` | Đọc sheet chương trình học, so khớp tên môn với các quy định |
| `tkb/style.py` | Chép style của file vào cho các file ra |
| `tkb/allocation.py` | Phân phần GVCN, sinh lớp-môn và danh sách giáo viên được dạy, sinh giáo viên bổ sung, nhóm môn ghép cặp |
| `tkb/phan_cong.py` | Dự toán và phân công giáo viên (luồng chi phí nhỏ nhất, tìm kiếm cục bộ), chia tiết bù cho người mới |
| `tkb/solver.py` | Quy trình giải và mô hình xếp giờ CP-SAT |
| `tkb/lns.py` | Xếp giờ: CP-SAT khởi đầu rồi các vòng QA → xếp lại từng vùng |
| `tkb/checker.py` | Kiểm tra độc lập các luật bắt buộc |
| `tkb/writer.py` | Xuất Excel |
| `tools/code_map.py` | In bản đồ code (hàm, lớp, `file:dòng`); `--write` sinh lại `docs/CODE_MAP.md` |
| `tools/mau_dau_ra.py` | Sinh lại các file mẫu đầu ra `data/Output_Template_TKB_V8.xlsx`, `data/Output_Template_Thong_Ke_V8.xlsx` từ trường mẫu tên giả (`tests/du_lieu_mau.py`) |

Hướng dẫn cho Claude Code (lệnh, kiến trúc, luật bảo mật, mã tham chiếu): [`CLAUDE.md`](CLAUDE.md).
