# Thiết kế: ba thực thể (Chương trình học, Nhân sự, Luật) trong thư mục TKB

Tài liệu này là kế hoạch làm lại cách soạn dữ liệu theo yêu cầu của anh/chị (25/10/2026). Kế hoạch được viết trước
khi sửa code. Mục 3 so ba hướng làm và đánh giá ba vòng; mục 6 là các giai đoạn, mỗi giai đoạn một PR.

## 0. Tóm tắt

- **Yêu cầu:**
  - Mọi file chương trình đọc hay ghi đều nằm trong thư mục TKB.
  - Chỉ làm việc với ba thực thể: **Chương trình học**, **Nhân sự**, **Luật**.
  - Chương trình học là tên môn và số tiết, lấy từ file Excel hoặc gõ trên trang.
  - Mỗi người trong Nhân sự có **cùng một bộ thiết lập**, như một hồ sơ nhân viên: dạy bù, môn và lớp được dạy, buổi
    nghỉ, định mức, số tiết bù tối đa, môn ưu tiên, môn bắt buộc, tiết bắt buộc, thứ tự bù. Không còn chức vụ nào
    có mục chọn riêng (Chủ Nhiệm có "Nhận trọn", Bộ Môn có "Được dạy", Quản Lý có "khối").
  - Luật: phát triển tiếp bộ ghép luật. **Không có luật mặc định**: mọi luật do người soạn TKB tạo hoặc đưa vào
    từ Excel.
- **Hướng chọn (mục 3): làm từng bước trên lõi đang có.** Lõi xếp TKB đọc hồ sơ từng người thay cho chức vụ. Chức vụ
  chỉ còn là một **hồ sơ mẫu**, có đúng các ô như hồ sơ một người. Luật chỉ là các dòng người soạn tự thêm.
- **File cũ của trường:** chương trình tự đổi sang dạng mới. Các quy định ngầm của chức vụ và 24 luật mặc định được
  ghi thành ô hồ sơ và dòng luật thật. TKB xếp ra giống hệt hiện nay (cùng mã kết quả). Mỗi giai đoạn sửa lõi dùng
  chính điều này để chứng minh không làm sai.
- **6 giai đoạn (mục 6).** GĐ1 (thư mục TKB, ba file) và GĐ2 (luật không mặc định) làm ngay vì không phụ thuộc
  thiết kế hồ sơ. GĐ4 (hồ sơ nhân sự) là phần lớn nhất. Có 5 câu hỏi cần anh/chị quyết, kèm đề xuất (mục 7). Chưa
  trả lời thì làm theo đề xuất.

## 1. Hiện trạng

| Chỗ | Hiện nay | Vì sao chưa đạt |
|---|---|---|
| Thư mục | Kết quả ở `ket_qua/`, bản nháp ở `du_lieu/` cạnh TKB.exe. Nhưng file mở bằng hộp chọn của trình duyệt (ở đâu cũng được). Nút "Đổi" đưa kết quả ra thư mục bất kỳ. "Tải" ghi vào thư mục Tải về của máy. | File đọc và ghi nằm rải rác ngoài thư mục TKB. |
| File | Một file Excel có mọi sheet: NHÂN SỰ, CHƯƠNG TRÌNH HỌC (kèm 14 cột quy định của môn), LỚP, PHÒNG, CHỨC VỤ, QUY ĐỊNH, LUẬT. | Ba thực thể nằm chung một file. Môn học mang cả chuyện "ai dạy". |
| Chức vụ | 4 loại có cách làm viết sẵn trong code: Chủ Nhiệm (`split_homeroom`: nhận trọn, cắt bớt, nhận thêm theo thứ tự của môn; bù ở lớp mình; tiết 1), Bộ Môn (mọi môn trừ cột "Bộ Môn không dạy"), Quản Lý (môn có ghi khối, dạy đủ định mức trước), GV chuyên biệt (các môn ở sheet CHỨC VỤ). Thai Sản, Cơ sở 2, Hợp Đồng cũng có nghĩa riêng. | Mỗi chức vụ một kiểu chọn, không chỉnh riêng từng người được. Khoảng 250 chỗ trong code dựa vào chức vụ. |
| Luật | 24 dòng mặc định (`luat_co_san.NATIVES`). File không có sheet LUẬT thì tự có đủ 24 dòng. "Soạn mới" có sẵn các dòng nhưng tắt. | Có luật mặc định. |
| Bộ ghép luật | 10 phép đo, mỗi phép đo viết một lần cho cả mô hình và bộ kiểm tra. Có câu điền chỗ trống, mức ưu tiên. | Giữ và phát triển tiếp. |

## 2. Đích đến

### 2.1 Thư mục TKB

```
TKB/                    thư mục chương trình (có TKB.exe; chạy từ mã nguồn: out/ của dự án)
  chuong_trinh_hoc/     file chương trình học: khối, lớp, môn, số tiết, khung giờ, phòng
  nhan_su/              file nhân sự: hồ sơ từng người, hồ sơ mẫu (chức vụ)
  luat/                 file luật (sheet LUẬT); có kèm file luật mẫu để đưa vào khi muốn
  tep_nhap/             bản gốc các file lấy từ chỗ khác vào (giữ nguyên, không sửa)
  ket_qua/              file vào của mỗi lần xếp, TKB, thống kê, file cập nhật
  du_lieu/              của riêng chương trình: bản nháp trang, file tạm, trình duyệt
```

- Trang chỉ mở và ghi file trong các thư mục này.
- File lấy từ chỗ khác (USB, email) được chép bản gốc vào `tep_nhap/` rồi mới đọc.
- "Lưu" ghi ba file, mỗi thực thể một file, cùng tên, vào ba thư mục.
- Không còn nút "Đổi" thư mục kết quả, không còn "Tải về".
- Xóa thư mục TKB là hết mọi thứ, đúng như trường đã yêu cầu.

### 2.2 Chương trình học

- **Bắt buộc:** khối, môn, số tiết từng khối (như sheet CHƯƠNG TRÌNH HỌC hiện nay), và lớp (sheet LỚP; không có thì
  lấy lớp từ cột Lớp chủ nhiệm của Nhân sự, như hiện nay).
- **Không bắt buộc:**
  - Tên trong TKB.
  - Nhóm môn: môn chính và môn tăng cường cùng nhóm. Là cấu trúc của chương trình, luật "theo nhóm môn" dùng đến.
  - **Nhãn** tự đặt, ví dụ "Môn nặng", "Ưu tiên sáng", "HĐTN", "Tăng cường". Thay cho các cột Có/Không đặt sẵn
    tên. Luật gọi môn theo nhãn, như nhãn lớp và nhãn GV hiện nay.
- **Khung giờ** (ngày, buổi, số tiết) và **Phòng** ghi cùng file chương trình học. Tiết và ngày cũng có Nhãn tự đặt
  (thay cho "Luôn do GVCN dạy", "Hạn chế môn nặng", "Tiết HĐTN cố định").
- **Bỏ khỏi môn học:** mọi cột nói "ai dạy": Chỉ GVCN dạy, Bộ Môn không dạy, GVCN nhận trọn / cắt bớt / nhận thêm,
  Quản lý dạy khối, GVCN bù môn chuyên biệt. Các ý này chuyển sang hồ sơ người dạy (2.3).

### 2.3 Hồ sơ nhân sự: mọi người cùng một bộ ô

Mỗi dòng NHÂN SỰ là một hồ sơ. **Hồ sơ mẫu** (sheet CHỨC VỤ, cùng các cột) đặt sẵn giá trị cho nhiều người. Ô để
trống ở hồ sơ một người thì lấy theo hồ sơ mẫu ở cột Chức Vụ. Chữ **"lớp CN"** trong một ô nghĩa là lớp chủ nhiệm
của chính người đó. Nhờ vậy một hồ sơ mẫu dùng chung được cho cả 29 GVCN.

| Ô của hồ sơ | Nghĩa | Ví dụ | Thay cho (hiện nay) |
|---|---|---|---|
| Họ và Tên, Mã GV, Tên Viết Tắt, Nhãn | Như hiện nay; Mã GV trống thì tự đặt theo Chức Vụ và số thứ tự | | |
| Chức Vụ | Hồ sơ mẫu của người này (không bắt buộc), chỉ là tên, không có cách làm riêng | Chủ nhiệm | 4 loại chức vụ viết sẵn |
| Lớp Chủ Nhiệm | Lớp người này chủ nhiệm (không bắt buộc), in ở đầu TKB lớp | 1D15 | cột Lớp của dòng Chủ Nhiệm |
| Định Mức | Số tiết/tuần đúng luật | 19 | Số Tiết/Tuần |
| Dạy Được | Môn và lớp được dạy: một danh sách môn với lớp, khối, cơ sở hoặc nhãn lớp; hoặc từng môn với lớp riêng | `lớp CN: Tiếng Việt, Toán, HĐTN…` · `Tin học: khối 3, 4, 5` · `Thể dục: Cơ sở 2` | quyền theo chức vụ, Bộ Môn không dạy, Chỉ GVCN dạy, Quản lý dạy khối, Cơ sở 2 / Thai Sản chỉ dạy cơ sở 2 |
| Dạy Khi Thiếu Người | Môn và lớp chỉ giao khi không còn ai | `Thể dục, Âm nhạc` | giá "bộ môn dạy môn chuyên biệt" |
| Nhận Trọn | Môn và lớp phải dạy hết; thiếu định mức thì bớt theo thứ tự ghi (mỗi môn giữ ít nhất 1 tiết) | `lớp CN: Tiếng Việt, Toán, Khoa học, LS&ĐL, HĐTN, Đạo đức` | GVCN nhận trọn + thứ tự cắt bớt |
| Nhận Thêm | Môn ưu tiên dạy cho đủ định mức, theo thứ tự | `lớp CN: TV tăng cường, Toán tăng cường, TNXH…` | GVCN nhận thêm |
| Tiết Bắt Buộc | Giờ người này phải dạy, ở lớp nào | `tiết 1 các ngày, lớp CN` | Luôn do GVCN dạy + luật "Ở giờ … lớp học với GV chủ nhiệm" |
| Giao Trước | Có: được giao đủ định mức trước người khác | Có | quản lý dạy đủ định mức (`MANAGER_BONUS`) |
| Dạy Bù | Số tiết bù tối đa; 0 là không dạy bù; trống thì theo cài đặt khi xếp | 3 | chức vụ được bù, Thai Sản không bù |
| Bù Được | Môn và lớp được dạy bù (trống thì như Dạy Được) | `lớp CN` | GVCN chỉ bù lớp mình, trừ môn chuyên biệt (trừ Âm nhạc, Mỹ thuật) |
| Thứ Tự Bù | Ai bù trước (1 là trước nhất) | 1 | Thứ Tự Bù; trống thì theo chức vụ và Hợp Đồng |
| Buổi Nghỉ | Buổi cố định hoặc n buổi sáng, chiều, bất kỳ | `Chiều T5, Sáng T6` · `2 buổi chiều` | như hiện nay (luật `buoi_nghi` thành dữ liệu hồ sơ) |
| Lớp Năm Trước | Lớp người này đang dạy, để TKB mới giữ khối, giữ lớp | | Lớp Đang Dạy |

Những điều luôn đúng, không phải luật:
- mỗi lớp mỗi giờ một tiết;
- đủ số tiết của chương trình học;
- một người không dạy hai nơi cùng lúc;
- dạy trong định mức cộng số tiết bù được phép;
- đúng các ô Dạy Được, Nhận Trọn, Tiết Bắt Buộc, Buổi Nghỉ của hồ sơ.

### 2.4 Luật

- Không có luật mặc định. Mẫu file trống có sheet LUẬT trống. "Soạn mới" không có luật nào.
- Thêm luật bằng câu điền chỗ trống (đã có) hoặc Tự ghép. 24 luật hiện nay thành **câu mẫu** trong hộp "Thêm luật".
  Câu mẫu chỉ thành luật khi người soạn bấm thêm.
- File luật mẫu (chính 24 luật đang dùng) nằm sẵn ở `luat/Mau_Luat.xlsx`. Đưa vào được bằng "Nhập luật từ Excel"
  khi muốn, không tự nạp.
- Luật nói về người theo **Chức Vụ** (tên hồ sơ mẫu), **Nhãn**, Mã GV hay họ tên. Luật nói về "GV chủ nhiệm của
  lớp" theo ô Lớp Chủ Nhiệm.
- Bộ ghép phát triển tiếp: thêm phép đo khi trường cần, theo cách đã có (một `Measure` cộng một hàm).

## 3. Ba hướng và ba vòng đánh giá

### 3.1 Ba hướng

- **A. Viết lại từ đầu:** dữ liệu mới và lõi xếp mới, xây quanh hồ sơ. File cũ chỉ đọc qua một bộ đổi.
- **B. Thay lớp ngoài, giữ nguyên lõi:** trang và file chỉ có ba thực thể và hồ sơ đồng nhất. Một bộ dịch đổi hồ sơ
  sang các thứ lõi đang hiểu: mỗi người một chức vụ ẩn, các dòng luật "Người dạy" ẩn cho quyền dạy và phân công
  riêng. Lõi không đổi.
- **C. Làm từng bước trên lõi đang có:** lõi hiểu hồ sơ thay cho chức vụ. Mỗi giai đoạn thay một cách làm viết sẵn
  theo chức vụ bằng một ô hồ sơ. File cũ đổi tự động sang hồ sơ và dòng luật thật, kết quả không đổi.

### 3.2 Vòng 1: so theo năm tiêu chí

| Tiêu chí | A | B | C |
|---|---|---|---|
| Đúng ý anh/chị (đồng nhất, tùy chỉnh tối đa) | Đủ | Chỉ ở bề mặt: có ô không dịch được (số tiết bù riêng từng người, tiết bắt buộc của người không chủ nhiệm, thứ tự nhận thêm riêng từng người); lỗi báo theo chức vụ ẩn mà người dùng không hề tạo | Đủ |
| Rủi ro xếp sai | Cao: mất các cách làm đã chỉnh qua nhiều đợt (LNS, lịch cơ sở, chẩn đoán, bộ kiểm tra) | Thấp | Vừa, kiểm được: file cũ phải ra đúng mã kết quả cũ |
| Giữ TKB và mã kết quả của trường | Mất | Giữ | Giữ (bằng cách đổi file cũ) |
| Công sức | Rất lớn (nhiều tháng) | Nhỏ đến vừa | Lớn, chia 6 PR |
| Dễ sửa về sau | Tốt | Kém: hai mô hình song song, bộ dịch phải theo mọi thay đổi | Tốt khi xong: một mô hình |

**Kết quả:** bỏ A vì rủi ro và công sức quá lớn so với lợi. B nhanh nhưng chỉ đổi bề ngoài; anh/chị muốn toàn quyền
chỉnh từng người nên B sớm chạm giới hạn. **Chọn C.** Lấy của B một ý: giai đoạn đầu không đụng lõi (GĐ1–3).

### 3.3 Vòng 2: thử hướng C với các trường hợp thật

| Trường hợp | C làm thế nào | Phải thêm vào thiết kế |
|---|---|---|
| File của trường: 29 GVCN nhận trọn TV, Toán…; GVCN thai sản 15 tiết phải bớt 1 tiết | Hồ sơ mẫu "Chủ nhiệm": Nhận Trọn `lớp CN: …` theo đúng thứ tự cắt hiện nay; Nhận Thêm theo thứ tự nhận thêm hiện nay | Nhận Trọn có thứ tự (bớt theo thứ tự, giữ ít nhất 1 tiết), giống `split_homeroom` |
| GVCN chỉ bù ở lớp mình, không bù môn chuyên biệt trừ Âm nhạc, Mỹ thuật | Bù Được `lớp CN: …các môn được bù` | Ô **Bù Được** riêng với Dạy Được |
| Bộ Môn dạy được Thể dục nhưng chỉ khi thiếu GV Thể dục (giá `general_on_specialist`) | Dạy Khi Thiếu Người: Thể dục, Âm nhạc, Mỹ thuật | Ô **Dạy Khi Thiếu Người** (cùng giá cũ) |
| Quản lý dạy 4 trong 5 lớp KNS khối 4, phải dạy đủ trước | Dạy Được `Kỹ năng sống: khối 4`, Giao Trước = Có | Ô **Giao Trước** (không dùng Nhận Trọn vì phải để phân công chọn 4 lớp nào) |
| GV thai sản / Cơ sở 2: chỉ dạy cơ sở 2, không bù | Dạy Được `…: Cơ sở 2`, Dạy Bù = 0; Thai Sản chỉ còn là nhãn | Dạy Được nhận tên cơ sở, nhãn lớp |
| Trường cấp 2, không có GVCN dạy nhiều môn | Mỗi người Dạy Được vài môn, vài khối; không ai có Lớp Chủ Nhiệm | Không thêm gì: hiện nay làm khó (phải có sheet LỚP, lớp không có GVCN) |
| Tuyển thêm "chưa có" | Người mới chép hồ sơ mẫu đầu tiên dạy được môn thiếu và không gắn "lớp CN"; tên `<Chức vụ> n (chưa có)` như hiện nay | Quy tắc chọn hồ sơ mẫu cho người tuyển |
| Trường mới, chưa có luật nào | Xếp được ngay (chỉ cấu trúc); hộp Thêm luật gợi các câu mẫu; nhập `luat/Mau_Luat.xlsx` một lần là có đủ 24 luật | Thông báo "chưa có luật nào" ở bước Luật và bước Xếp |

Sau vòng 2, hồ sơ có thêm ba ô (Bù Được, Dạy Khi Thiếu Người, Giao Trước) và quy tắc chọn hồ sơ cho người tuyển.
Có các ô này thì mọi cách làm theo chức vụ hiện nay đều ghi được thành dữ liệu hồ sơ. Đó là điều kiện để file cũ ra
đúng mã cũ.

### 3.4 Vòng 3: đối chiếu với các quy ước của dự án

| Quy ước | Cách giữ |
|---|---|
| Tái lập: cùng dữ liệu thì cùng TKB, mã kết quả ghi trong test và README | GĐ1–3 không đổi mã. GĐ4 có test so **bài toán dựng theo đường cũ và đường hồ sơ**: cùng các course, cùng người được dạy, cùng giá. Phải giống nhau trước khi chuyển lõi. Sau đó mã của trường nhỏ, trường mẫu, file của trường (chạy trên máy, không in tên) phải giữ nguyên. |
| Thứ tự dựng mô hình đổi là mã đổi | Hồ sơ dựng course theo đúng thứ tự cũ (lớp theo thứ tự, phần nhận trọn trước). Test so ở trên bắt mọi lệch. |
| Riêng tư: file của trường có tên thật | Chỉ đổi và chạy trên máy, chỉ in mã kết quả và số đếm. Test dùng trường mẫu tên giả. |
| Không ghi cứng dữ liệu trường, không gắn với nước nào | Đúng hướng: tên môn, chức vụ, nhãn đều là dữ liệu. Bộ đổi file cũ đọc giá trị cũ từ chính file. |
| Luật bắt buộc là quyết định của trường | Bỏ luật mặc định là quyết định của anh/chị (ghi vào §0 của đặc tả). File cũ giữ đủ luật đang dùng bằng dòng thật. |
| Trang không thư viện ngoài | Ô hồ sơ là ô chữ có gợi ý, hộp chọn môn × lớp, như các hộp đang có. |

**Điều chỉnh sau vòng 3:**
1. Tách GĐ4 làm ba PR:
   - 4a: đọc và ghi hồ sơ, đổi file cũ, test so bài toán; lõi cũ vẫn chạy.
   - 4b: lõi dùng hồ sơ.
   - 4c: bỏ code theo chức vụ.
2. GĐ1 làm cả ba file: hộp nhập file đã chọn được từng phần, nên chia file gần như chỉ là đổi chỗ ghi.
3. Hồ sơ mẫu phải sửa được cho nhiều người cùng lúc. Nếu không, 29 GVCN là 29 lần sửa. Đây là lý do hồ sơ mẫu và
   chữ "lớp CN" nằm trong thiết kế, không để sau.

### 3.5 Kết luận

Chọn **C**: 6 giai đoạn, mỗi giai đoạn một PR (GĐ4 ba PR). Mỗi PR chạy được và có đủ test.
- Mã kết quả không đổi ở mọi giai đoạn với file cũ.
- Với dữ liệu mới, kết quả theo đúng những gì người soạn ghi.

## 4. File cũ và mã kết quả

- **File V8 một tệp** (file của trường, các file `*_cap_nhat.xlsx`) vẫn mở được.
  - Chương trình chia file thành ba thực thể.
  - Mỗi quy định ngầm được ghi ra thành dữ liệu:
    - chức vụ thành hồ sơ mẫu;
    - cột quy định của môn thành ô hồ sơ và nhãn môn;
    - file không có sheet LUẬT thì có đủ 24 dòng luật thật.
- **Dòng lệnh** (`python -m tkb`, `main.py`) vẫn nhận một file V8. Sau GĐ6 nhận thêm ba file hoặc một thư mục.
- **Mã kết quả:** file cũ giữ nguyên mã. Lý do: dữ liệu đổi ra có đúng nghĩa của file cũ, lõi xếp đúng cách cũ. Nếu
  một giai đoạn buộc phải đổi mã, PR đó nói rõ lý do và cập nhật mã tham chiếu như quy ước.

## 5. Giao diện sau cùng

Các bước của trang:
1. **Khung giờ**
2. **Chương trình học:** khối, lớp, môn, số tiết, nhóm, nhãn, phòng.
3. **Nhân sự:**
   - bảng người;
   - hồ sơ một người là một mẫu điền, giống nhau cho mọi người;
   - hồ sơ mẫu (chức vụ) ở cùng bước, cùng mẫu điền;
   - chọn nhiều người rồi sửa một ô cho tất cả.
4. **Luật**
5. **Kiểm tra & xếp**
6. **TKB**

Bước "Chức vụ" riêng và ba thẻ Chủ Nhiệm / Bộ Môn / Quản Lý không còn. Mỗi bước có "Mở…" và "Lưu" file của thực thể
đó, trong thư mục của nó.

## 6. Các giai đoạn

| GĐ | Nội dung | Đổi mã kết quả? |
|---|---|---|
| **1. Thư mục TKB và ba file** | Các thư mục của 2.1. "Mở file" là danh sách file trong thư mục TKB, kèm "Lấy file từ chỗ khác" (chép bản gốc vào `tep_nhap/`). "Lưu" ghi ba file: chương trình học, nhân sự, luật. Mẫu trống là ba file. Bỏ nút Đổi thư mục, bỏ "Tải". | Không |
| **2. Luật không mặc định** | Mẫu trống và "Soạn mới" không có luật. 24 luật thành câu mẫu trong "Thêm luật" và file `luat/Mau_Luat.xlsx`. Bỏ "Về mặc định". Có thông báo khi chưa có luật. File cũ không có sheet LUẬT được ghi đủ 24 dòng thật. | Không |
| **3. Chương trình học gọn** | Cột Có/Không của môn (HĐTN, Môn nặng, Ưu tiên buổi sáng, Không ghép cặp, Môn tăng cường) và của tiết, ngày thành **Nhãn** tự đặt. Luật gọi theo nhãn. File cũ đổi tự động. Các cột "ai dạy" tạm giữ đến GĐ4. | Không |
| **4a. Hồ sơ: dữ liệu** | Đọc, ghi các ô hồ sơ và hồ sơ mẫu; chữ "lớp CN". Đổi file cũ: chức vụ thành hồ sơ mẫu. Test: bài toán dựng từ hồ sơ giống hệt bài toán dựng theo chức vụ (trường nhỏ, trường mẫu, các test chức vụ). Lõi chưa đổi. | Không |
| **4b. Hồ sơ: lõi** | Dựng bài toán, phân công, tuyển thêm, bộ kiểm tra, thống kê theo hồ sơ. | Không (test của 4a bảo đảm) |
| **4c. Dọn code** | Bỏ code theo chức vụ, cột "ai dạy" của môn (chỉ còn đọc ở bộ đổi file cũ). Cập nhật đặc tả, README, hướng dẫn. | Không |
| **5. Trang ba thực thể** | Các bước của mục 5; mẫu điền hồ sơ; sửa nhiều người một lúc. | Không |
| **6. Hoàn thiện** | Dòng lệnh nhận ba file hoặc thư mục; mẫu trống ba file; bản đóng gói; tài liệu. | Không |

Thứ tự này đặt các việc ít rủi ro, không phụ thuộc thiết kế hồ sơ lên trước. Trong lúc làm, anh/chị có thời gian
xem lại bảng hồ sơ ở 2.3 trước khi lõi đổi (GĐ4).

## 7. Cần anh/chị quyết

| # | Câu hỏi | Đề xuất |
|---|---|---|
| 1 | Giữ **Chức vụ như hồ sơ mẫu** (cùng các ô như một người, ô trống của người lấy theo mẫu), hay bỏ hẳn chức vụ và mỗi người tự điền đủ? | Giữ hồ sơ mẫu: không có thì 29 GVCN phải điền 29 lần. Mẫu chỉ là cách điền nhanh, không có cách làm riêng. |
| 2 | Giữ ô **Lớp Chủ Nhiệm** trong hồ sơ? | Giữ: TKB lớp in GVCN ở đầu, các ô khác dùng chữ "lớp CN". Người không chủ nhiệm để trống. |
| 3 | File cũ của trường tự đổi sang dạng mới và giữ đúng TKB? | Có. |
| 4 | Ba file riêng (chương trình học, nhân sự, luật), vẫn mở được file một tệp cũ? | Có. |
| 5 | Kèm sẵn `luat/Mau_Luat.xlsx` (24 luật đang dùng) để đưa vào khi muốn? | Có, không tự nạp. |

## 8. Rủi ro

- **Lệch phân công khi chuyển lõi (GĐ4b).** Cách phòng: test so bài toán ở 4a; mã của trường nhỏ, trường mẫu, file
  trường phải giữ nguyên; CI Windows so mã của 4 máy.
- **Hồ sơ nhiều ô, khó điền.** Cách phòng: hồ sơ mẫu, chữ "lớp CN", sửa nhiều người một lúc, giải thích từng ô ngay
  dưới ô. Đồng thời mọi ô đều không bắt buộc, trừ tên và định mức.
- **Luật không mặc định thì trường mới dễ xếp ra TKB kém cho học sinh.** Cách phòng: bước Luật và bước Xếp báo "chưa
  có luật bảo vệ học sinh nào". Câu mẫu và file luật mẫu ở ngay đó.
- **Bản đóng gói cũ** (`TKB_Windows.zip` trên main) không có các thư mục mới. Đóng gói lại khi anh/chị bảo.
