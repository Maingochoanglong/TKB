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
**Hướng dẫn ngắn có hình cho nhà trường:** [`docs/Huong_Dan_Su_Dung.md`](docs/Huong_Dan_Su_Dung.md).

## Cài đặt và chạy

**Không cài Python (Windows):** tải `TKB_Windows.zip` ở trang **Releases** của dự án (bản thử của từng lần sửa mã: mục
Actions → workflow **Đóng gói TKB.exe** → Artifacts), giải nén, bấm đúp `TKB.exe` (Windows báo "Windows protected your
PC" vì gói chưa ký số thì bấm More info › Run anyway): mở đúng giao diện web ở Cách 0, kết quả ghi vào thư mục `TKB` trong thư mục người dùng.
Gói dựng bằng `python tools/dong_goi.py` (PyInstaller, `pip install -r requirements-build.txt`), cùng OR-Tools ghim
nên ra cùng mã kết quả như `python -m tkb` trên Windows; gói không chứa file Excel nào của trường.

Cài thư viện (một lần):

```bash
pip install -r requirements.txt
```

### Cách 0 — giao diện web (cho nhà trường, không cần sửa code)

Mở `giao_dien.py` rồi bấm **Run ▶** (hoặc chạy `python giao_dien.py`, `python -m tkb.giao_dien`). Trình duyệt tự mở trang
`http://127.0.0.1:8765/`. Trang này **chạy ngay trên máy**: không cần Internet, không có máy chủ ngoài, tên giáo viên không
rời máy. Giữ cửa sổ chạy chương trình mở trong khi dùng trang.

1. Lần đầu mở trang (hoặc **Tệp ▾ › Bắt đầu lại…**) là **trang bắt đầu**: **Mở file Excel của trường**, **Soạn mới**
   theo một **bộ luật mẫu** (`tkb/bo_mau.py`): **Tiểu học Việt Nam** (các môn, luật và quy định mặc định) hoặc **Trống**
   (chưa có môn nào, không theo quy ước của nước nào: các luật có sẵn để Tạm tắt, bật luật cần dùng ở bước Luật), và
   **Xem thử với trường mẫu** (trường mẫu tên giả
   29 lớp, 45 giáo viên của `tkb/truong_mau.py`: bấm Kiểm tra rồi Xếp TKB để xem chương trình làm gì). Mọi việc với
   file nằm ở menu **Tệp ▾**: Mở file Excel…, Lưu ra file Excel, Tải file mẫu trống (như
   `data/Input_Template_V8.xlsx`, điền trong Excel rồi mở lại), Bắt đầu lại…. Mở được file vào V8 bất kỳ, kể cả file
   cập nhật `*_cap_nhat.xlsx` của lần chạy trước. Hộp thoại mở file cho chọn phần nào lấy từ file (Giáo viên: thay danh
   sách hoặc thêm vào cuối; Môn học; Chức vụ; Khung giờ và quy định chung; Luật: thay hoặc thêm vào cuối; TKB đã xếp),
   phần không chọn giữ như đang soạn; file đủ (có nhân sự) mặc định thay toàn bộ, file chỉ có vài sheet (vd file luật)
   chỉ chọn sẵn các phần file có. Cài đặt chạy không nằm trong file Excel: file có TKB đã xếp với số tiết bù (ô ghi
   `(bù)`) nhiều hơn số tiết bù tối đa đang đặt thì trang nâng số đó lên cho khớp và báo lại.
   - **Hoàn tác / làm lại**: nút ↶ ↷ ở đầu trang hoặc Ctrl+Z / Ctrl+Y (khi không gõ trong ô chữ), tối đa 50 bước, kể cả
     xóa và thay cả kịch bản; vì vậy xóa không hỏi lại mà hiện "Đã xóa … [Hoàn tác]". Cạnh đó ghi giờ lưu nháp.
   - **Kiểm tra tự động**: sửa xong khoảng 1,5 giây là trang đọc lại kịch bản như khi chạy (không dự toán); mỗi bước có
     dấu **✓** hoặc **⚠ n** (số lỗi), đầu bước có hộp lỗi của bước đó, bấm vào lỗi để tới đúng dòng, dòng lỗi tô đỏ nhạt.
     Đọc dừng ở lỗi đầu tiên (luật, rồi chương trình học, rồi nhân sự) nên bước chưa kiểm được hiện **?** thay cho ✓.
     Câu lỗi ghi tên giáo viên, môn, câu luật (vd `Giáo viên CN 3: Số tiết …`); vị trí trong file Excel (sheet, dòng) ở
     chú thích khi rê chuột.
2. Soạn kịch bản của trường theo từng bước (nút **Tiếp →** cuối mỗi trang):
   - **Khung giờ & quy định chung**: bảng ngày học × buổi (tên ngày, tên buổi tùy ý, mỗi ô là số tiết của buổi đó
     trong ngày; thêm/xóa/đổi thứ tự ngày, thêm/đổi tên/bỏ buổi), ai được bù, tiết HĐTN cố định, tiết luôn do GVCN dạy,
     tiết hạn chế môn nặng.
   - **Môn học**: danh sách môn với số tiết từng khối (thêm/bớt khối), cột **Ai dạy** và các quy định khác tóm tắt;
     bấm **Sửa** để mở trang chi tiết của môn, các quy định chia nhóm (hiển thị, GVCN, ai được dạy, luật bảo vệ học sinh,
     ưu tiên khi xếp), mỗi ô có giải thích. **Bảng đầy đủ** hiện mọi cột cùng lúc như sheet Excel.
   - **Lớp** (sheet `LỚP`, không bắt buộc): tên các khối (tùy ý, vd `Lá`; đổi tên thì số tiết của môn, lớp, luật đổi
     theo) và danh sách lớp: tên lớp tùy ý, khối, Cơ sở 2, Nhãn, cột Chủ Nhiệm cho thấy lớp nào chưa có GVCN. **Lấy từ các Chủ
     Nhiệm** chép các lớp đang có. Để trống thì lớp là cột Lớp của các Chủ Nhiệm như trước.
   - **Chức vụ**: ba chức vụ có sẵn và các chức vụ GV chuyên biệt của trường. Chủ Nhiệm: đánh dấu môn nhận trọn, môn chỉ
     GVCN dạy; Bộ Môn: đánh dấu môn được dạy; Quản Lý: chọn khối cạnh môn được dạy (đây là các cột quy định của môn).
     **+ Thêm chức vụ**: đặt tên (vd `GV Nghệ thuật`) và đánh dấu các môn được dạy (sheet `CHỨC VỤ`). Trang nhắc môn
     nào Bộ Môn không dạy mà chưa có chức vụ hay giáo viên nào dạy.
   - **Giáo viên**: danh sách NHÂN SỰ, chọn **Chức Vụ** trong danh sách các chức vụ ở bước trước; ô Lớp chỉ mở cho Chủ
     Nhiệm (gợi ý các lớp của bước Lớp); lọc theo chức vụ; **Dán từ Excel…** để dán cả danh sách. **Sửa** mở trang chi tiết: Thai Sản, Hợp Đồng,
     Cơ sở 2; **Lớp Đang Dạy** đánh dấu trong các lớp của trường (nút Khối k chọn cả khối); **Buổi Nghỉ** đánh dấu buổi
     cố định trên bảng ngày × buổi và ghi số buổi nghỉ thêm bất kỳ: buổi sáng, buổi chiều, hoặc sáng hay chiều đều được
     (GVCN không nghỉ buổi sáng); **Chức Vụ Thêm** đánh dấu Bộ Môn hay các chức vụ của bước Chức vụ. Trang ghi ra
     đúng chữ như ghi tay, vd `3/1, 3/2`, `Chiều T5, 2 buổi chiều` và `Bộ Môn, Tiếng Anh`.
   - **Luật** (bộ ghép luật, sheet LUẬT): mọi luật, kể cả các luật có sẵn, xếp theo nhóm, mỗi luật một câu dễ đọc
     (luật có sẵn có tên riêng, vd "Mỗi buổi, một lớp học tối đa 2 tiết của một môn…") và nhãn **Bắt buộc** hoặc
     **Ưu tiên thấp / vừa / cao / rất cao**; dòng đánh dấu **mặc định** chương trình xếp như trước. **Sửa** mở hộp thoại
     theo thứ tự câu luật: **Loại luật** (một ô chọn chia theo bốn câu hỏi **Ở đâu**, **Bao nhiêu**, **Đi cùng nhau**,
     **Ai dạy**, gồm các mẫu và "Tự ghép · <phép đo>") · **Với mỗi** · **Các tiết nào** (Môn, Khối, Lớp; các ô ít dùng
     nằm trong **Thêm điều kiện**, nhãn môn và nhãn giờ học tách riêng) · **Vào giờ nào** (họ Ở đâu) · **Thì** (Áp dụng
     khi chọn bằng ô: từ … tiết/tuần trở lên, không quá …/số ngày học, chẵn/lẻ) · **Mức** (Bắt buộc/Ưu tiên và mức;
     Điểm, Nhóm trong **Nâng cao**). Hộp thoại hiện ngay **luật đọc là** (cùng câu chương trình in ra), lỗi nếu ghép
     sai, và cảnh báo khi sửa làm luật có sẵn mất dạng gốc (mã kết quả sẽ khác), vd "Mỗi GV bộ môn, mỗi ngày: dạy tối
     đa 3 lớp khác nhau (bắt buộc)". Ô **Dùng** ở mỗi luật: bỏ dấu là **tạm tắt** (luật mờ đi, ghi `Có` ở cột Tạm tắt,
     chương trình bỏ qua; đánh dấu lại là dùng lại); **✕** xóa luật; chọn loại luật rồi **+ Thêm luật**.
     Menu **Tệp luật ▾**: **Nhập luật từ Excel…** (thay hoặc thêm vào cuối), **Xuất luật ra Excel** (file chỉ có sheet
     LUẬT, HƯỚNG DẪN: sửa trong Excel, chép sang trường khác), **Tải mẫu luật** (các luật có sẵn mặc định), **Về mặc
     định**.

   Các bước Môn học, Giáo viên, Luật có **ô tìm** (tên môn; họ tên, Mã GV, lớp; chữ trong câu luật): chỉ hiện các dòng
   khớp, bấm vào một lỗi ở dòng đang ẩn thì ô tìm tự xóa.

   Đổi tên một môn thì các chức vụ, luật ghi môn đó đổi theo; đổi tên một chức vụ thì các giáo viên giữ chức vụ
   đó và các luật ghi chức vụ đó đổi theo.
3. **Kiểm tra & xếp TKB**: chọn chế độ, số tiết bù tối đa, thời gian, rồi
   - **Kiểm tra** (vài giây): đọc lại kịch bản đúng như khi chạy, báo lỗi (bấm vào lỗi để tới đúng dòng) và **dự toán**
     số tiết bù, tiết thiếu trước khi xếp.
   - **Xếp TKB**: lưu file vào `<tên>.xlsx` vào thư mục kết quả rồi chạy như `main.py`; hiện nhật ký, **Dừng sớm**
     (như Ctrl+C: vẫn ghi TKB tốt nhất), rồi **kết quả tóm tắt**: mã TKB (mã kết quả), xếp giờ bao lâu và vì sao dừng,
     dạy bù bao nhiêu tiết (bao nhiêu người +1, +2), cần tuyển mấy người, môn nặng ở tiết cuối, so với TKB trước đổi
     bao nhiêu ô, và **Chất lượng**: số lần chưa theo luật ưu tiên, điểm trừ, các luật trừ nhiều điểm nhất kèm ví dụ
     (đọc từ sheet Chất lượng); các file ra (nút Mở, Tải) gom trong mục **Các file Excel**. **Nạp vào giao diện** mở
     file cập nhật (có người cần tuyển và TKB đã xếp) để sửa tiếp, vd đổi "chưa có" thành tên người mới rồi xếp lại:
     TKB giữ nguyên.
   - **Tệp ▾ › Lưu ra file Excel**: file vào V8 đầy đủ (nhân sự, chương trình học kèm quy định, CHỨC VỤ, QUY ĐỊNH,
     LUẬT, HƯỚNG DẪN), dùng được cho `main.py` và dòng lệnh, gửi cho trường khác được.
4. **Thời khóa biểu** (bước 8): xếp xong bấm **Xem TKB trên trang** (hoặc mở file `_cap_nhat.xlsx`): TKB đã xếp hiện
   thành lưới theo khối, theo lớp hoặc theo giáo viên (ô: môn, người dạy, 🔒 ô khóa, **bù** tiết dạy bù), kiểm mọi luật
   bắt buộc như khi dùng lại TKB; tab có dấu ✓ hoặc ⚠ n.
   - **Đổi hai tiết**: bấm một ô (các ô cùng lớp đổi được mà không sai luật bắt buộc nào viền xanh), rồi bấm ô thứ hai
     cùng lớp: hai ô đổi chỗ và được khóa; trang kiểm lại ngay, ô sai luật viền đỏ, bấm vào câu lỗi để tới ô đó. Đổi
     nhầm thì Hoàn tác. Nút trong khung chọn ô để khóa / mở khóa một ô; **Mở khóa n ô** bỏ mọi khóa.
   - **Đổi người dạy** cả môn của một lớp (môn không có phần GVCN dạy): khung chọn ô có ô **Người dạy … lớp …** với
     những người được dạy môn đó; chọn người khác thì trang ghi luật "Chỉ giáo viên dạy" (Môn, Lớp, người) ở bước Luật,
     TKB đang có báo sai luật đó, bấm **Xếp lại phần còn lại** để đổi, giữ TKB cũ nhiều nhất. Muốn bỏ thì xóa hay tạm
     tắt luật đó.
   - **Xếp lại phần còn lại** (TKB còn lỗi, hoặc luật đã sửa từ lúc xếp): chạy như Xếp TKB, giữ TKB đã xếp, tối đa
     120 giây (thường dừng sớm vì đã tối ưu): ô khóa giữ nguyên, chỉ dời ít tiết nhất để đạt mọi luật; xong TKB mới tự
     vào trang, các ô đã đổi tô vàng. Ô khóa sai luật bắt buộc (vd dời HĐTN khỏi tiết cố định) không giữ được: trang
     báo rõ ô nào. TKB đúng mọi luật thì nút là **Ghi TKB này ra file Excel** (dùng lại nguyên vẹn, mã TKB mới).

- Thư mục kết quả mặc định `out/giao_dien` của dự án (đã bỏ qua trong git; bản `TKB.exe`: thư mục `TKB` trong thư mục
  người dùng); đổi ở trang Kiểm tra & xếp TKB. Kịch bản đang soạn được lưu
  tự động trong trình duyệt của máy này.
- Cài đặt chạy mặc định như `main.py`, riêng số tiết bù tối đa là mức được duyệt 2 (file của trường hiện cần 3).
  Các cài đặt này không nằm trong file Excel; cùng file vào và cùng cài đặt thì ra cùng mã kết quả như dòng lệnh.
- Mọi ô quy định sinh từ `tkb/rules.py`: thêm một quy định vào đó là giao diện tự có ô nhập.
- Tùy chọn dòng lệnh: `python -m tkb.giao_dien --cong 8765 --thu-muc <thư mục> --khong-mo-trinh-duyet`.

### Cách 1 — bấm nút Run trong `main.py` (dễ nhất cho người dùng Python)

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
| `FILE_TKB`, `FILE_TKB_CHUC_VU`, `FILE_TKB_GIAO_VIEN`, `FILE_THONG_KE` | Tên file TKB (chỉ thời khóa biểu), TKB ghi thêm chức vụ (Mã GV) trong mỗi ô, TKB của từng giáo viên, và file thống kê (số tiết từng môn của giáo viên, chất lượng TKB) | `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `TKB_giao_vien.xlsx`, `Thong_Ke.xlsx` |
| `SO_LUONG` | Số luồng tìm kiếm song song của bộ giải; nên ≥ số nhân CPU. Đổi số này thì TKB ra khác (vẫn đúng luật) | `8` |
| `GIU_TKB_DA_XEP` | `FILE_VAO` là file vào cập nhật của lần chạy trước (`<tên file vào>_cap_nhat.xlsx`, có sheet **TKB đã xếp**): `True` thì dùng lại đúng TKB đó, không xếp lại, nếu vẫn đúng mọi luật (xem [Tuyển được người](#tuyển-được-người-giữ-nguyên-tkb)); `False` thì luôn xếp lại từ đầu | `True` |

   - Đường dẫn tương đối được tính từ thư mục chứa `main.py`.
   - **Chạy lại, hoặc chạy ở máy khác cùng hệ điều hành, ra đúng TKB cũ** khi `CHAY_TAI_LAP_DUOC = True` và giữ nguyên: file vào, các hằng số trong `main.py`, phiên bản thư viện (cài bằng `pip install -r requirements.txt`). Xem mục [Chạy trên máy khác](#chạy-trên-máy-khác).
   - **Không giới hạn thời gian** (`THOI_GIAN_TOI_DA` để trống hoặc `0`): bước dự toán và phân công xong ngay; bước xếp giờ xếp lại từng vùng đến khi một vòng không còn cải thiện rồi tự dừng, vẫn tái lập được. Với file của trường bản trước (chưa có hai cơ sở), mặc định 1200 đã ra đúng TKB của chế độ không giới hạn, trên cả Linux và Windows; chế độ không giới hạn có thể lâu hơn (Windows giả lập khoảng 16 phút) vì chạy thêm các vòng cho tới khi biết chắc không còn cải thiện. Bấm **Ctrl+C** để dừng sớm: chương trình dừng sau vùng đang xếp (vài giây), vẫn kiểm tra luật và ghi đủ các file ra; dừng bằng tay thì mỗi lần có thể ra TKB khác nhau.
   - Trên Windows, viết đường dẫn dạng `r"C:\Users\ten\TKB\input.xlsx"` hoặc `"C:/Users/ten/TKB/input.xlsx"`.
2. Bấm **Run ▶** (VS Code, PyCharm...) hoặc chạy `python main.py`.
3. Kết quả nằm trong `THU_MUC_OUT`: `TKB.xlsx`, `TKB_chuc_vu.xlsx`, `TKB_giao_vien.xlsx`, `Thong_Ke.xlsx` và `<tên file vào>_cap_nhat.xlsx`. Trường có lớp ở cơ sở 2 thì mỗi file TKB tách làm hai: `TKB_diem_chinh.xlsx` / `TKB_diem_phu.xlsx` và `TKB_chuc_vu_diem_chinh.xlsx` / `TKB_chuc_vu_diem_phu.xlsx`. Khi ghi ra thư mục dự án, các file này đã được `.gitignore` bỏ qua để không lỡ đưa tên giáo viên lên git. Chế độ bù giờ mà thiếu tiết thì chỉ có `Thong_Ke.xlsx` (bảng tiết thiếu) và `main.py` trả về mã 3.

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
| `--teachers-out` | File TKB giáo viên: mỗi giáo viên một bảng, in mỗi người một trang (mặc định `<thư mục output>/TKB_giao_vien.xlsx`) |
| `--time-limit` | Lượng tính toán cho bước xếp giờ, xấp xỉ giây (mặc định 1200; `0` = không giới hạn: xếp lại đến khi hết cải thiện, Ctrl+C để dừng sớm) |
| `--non-reproducible` | Dừng theo giây thực; mỗi lần chạy có thể ra TKB khác nhau |
| `--mode` | `tuyen_them` (mặc định) hoặc `bu_gio` |
| `--max-overtime` | Số tiết bù tối đa mỗi người; chế độ tuyển: người mới nhận các tiết bù này (mặc định 2) |
| `--no-student-rules` | Tắt luật bảo vệ học sinh (dùng để tìm nguyên nhân khi không xếp được) |

Mã thoát: `0` đạt; `1` lỗi file vào hoặc không xếp được; `2` TKB sai luật bắt buộc; `3` chế độ bù giờ thiếu tiết.

**Khi các quy định mâu thuẫn** (không có TKB nào thỏa), chương trình nói rõ dòng luật nào (sheet LUẬT):
- Trước khi xếp, chương trình đếm và báo ngay (cả nút Kiểm tra của giao diện), vd `Khối 1: Tiếng Việt có 14 tiết/tuần
  nhưng luật 'LUẬT dòng 2: Mỗi buổi, một lớp học tối đa 1 tiết của một môn, tính chung môn chính với môn tăng cường
  cùng nhóm (bắt buộc)' chỉ cho tối đa 1 × 9 buổi = 9 tiết`.
- Phép đếm không thấy mà bộ giải không xếp được thì chương trình **chẩn đoán** (thường dưới vài phút): thử bỏ từng
  dòng luật bắt buộc rồi báo các dòng ít nhất không cùng thỏa được và dòng nào bỏ riêng là đủ, vd `LUẬT dòng 2: Mỗi
  buổi, một lớp học tối đa 2 tiết của một môn…` và `LUẬT dòng 9: Tiết HĐTN chỉ xếp vào giờ có nhãn Tiết HĐTN cố định
  hoặc Xếp tiết HĐTN còn lại`. Nếu nguyên nhân chỉ là thiếu thời gian thì chương trình bảo tăng thời
  gian; nếu bỏ hết vẫn không được thì nguyên nhân ở nhân sự, định mức hoặc quyền dạy.

Chạy test: `python -m pytest -q`

## Tuyển được người, đổi giữa năm: giữ nguyên TKB

File vào cập nhật (`<tên file vào>_cap_nhat.xlsx`) lưu luôn TKB đã xếp ở sheet **TKB đã xếp**, dạng lưới như TKB: `Lớp | Tiết | Thứ 2 … Thứ 6`, mỗi ô ghi môn, xuống dòng ghi Mã GV (thêm `(bù)` ở tiết dạy bù, `(khóa)` ở ô khóa); dòng đầu ghi mã kết quả và mã các quy định đã dùng.

1. Chạy chế độ tuyển thêm. File vào cập nhật có thêm các dòng `chưa có` (vd Bộ Môn 5–8).
2. Tuyển được người thì mở file vào cập nhật, **chỉ đổi chữ `chưa có` thành tên người mới**. Không đổi thứ tự dòng, vì giáo viên được khớp theo Mã GV (vd `Bộ Môn 5` là người thứ 5 trong chức vụ Bộ Môn).
3. Đặt `FILE_VAO` là file đó, `GIU_TKB_DA_XEP = True` (mặc định), rồi chạy. Chương trình in `Dùng lại TKB đã xếp trong file vào`, không xếp lại (chạy vài giây). TKB giữ nguyên từng ô, **mã kết quả giữ nguyên**; TKB và file thống kê ghi tên người mới.

- Chạy ở chế độ nào cũng được: người mới giờ là bộ môn thật, dạy trong định mức, nên không ai phải bù.
- Trước khi dùng lại, chương trình kiểm tra TKB đó với file vào mới theo mọi luật bắt buộc. Nếu file bị sửa làm TKB cũ sai luật (vd một người xin nghỉ một buổi đang có tiết, hạ định mức, sửa chương trình học, sửa tay vài ô TKB) hoặc quy định đã đổi (mã quy định khác, vd thêm môn nặng, thêm luật), chương trình in lý do rồi **xếp lại ít xáo trộn nhất**:
  - giữ mọi ô được; mỗi ô đổi môn bị trừ điểm nặng (`keep_cell` 5.000, nặng hơn mọi mục tiêu mềm trừ đổi cơ sở trong ngày), phân công ưu tiên giữ người dạy cũ (`keep_previous`);
  - ô ghi thêm **`(khóa)`** ở dòng cuối (vd `Toán` / `Bộ Môn 2 (khóa)`, gõ tay trong sheet TKB đã xếp) giữ nguyên bắt buộc, cả môn lẫn người dạy; lần sau vẫn ghi `(khóa)`. Ô khóa không xếp được (giờ không học) bị bỏ qua; các ô khóa mâu thuẫn với luật thì chương trình bỏ khóa (in ra) và vẫn giữ TKB cũ nhiều nhất có thể;
  - màn hình in `So với TKB đã xếp trong file vào: đổi n/m ô`, file thống kê có sheet **Thay đổi** (`Lớp | Thứ | Tiết | Trước | Sau`).
  - Ví dụ trường mẫu (928 tiết): một giáo viên xin nghỉ chiều Thứ 5 → xếp lại ít xáo trộn đổi **15 ô** (chất lượng còn tốt hơn chút), xếp lại từ đầu đổi 628 ô.
- **Sửa tay vài tiết trên trang** (giao diện, bước 8 Thời khóa biểu): đổi hai tiết cùng lớp bằng hai lần bấm, trang
  kiểm luật ngay và khóa hai ô đó; **Xếp lại phần còn lại** chạy đúng cách xếp lại ít xáo trộn ở trên, rồi đưa TKB mới
  vào trang (ô đổi tô vàng). Không phải sửa sheet TKB đã xếp trong Excel.
- Muốn bỏ TKB cũ, xếp lại từ đầu: đặt `GIU_TKB_DA_XEP = False` (dòng lệnh: `--xep-lai`; giao diện: bỏ chọn "Giữ TKB đã xếp").
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
| Windows x86-64 | **`DEB9-056B-FF59`** | Máy ảo GitHub Actions: Windows Server 2022 và 2025, Python 3.12 và 3.14 |
| Linux x86-64 | **`FF2F-F451-28ED`** | Python 3.13 |

**Đã sửa lỗi "thỉnh thoảng ra TKB khác":** trước đây, dù đã bật chế độ tất định của OR-Tools, chạy lặp cùng một mô hình vẫn có lúc ra TKB khác (6 lần ra 3 TKB). Nguyên nhân là các luồng của bộ giải chia sẻ mệnh đề học được và cận ở mức gốc cho nhau, và phần này không tất định. Chế độ tái lập nay tắt hai loại chia sẻ đó (`tkb/solver.py`, hàm `_configure`): chạy lặp 8 lần ra 8 lần cùng mã, chất lượng không giảm. Máy ảo Windows của GitHub Actions kiểm tra việc này mỗi lần đổi code (`.github/workflows/windows.yml`): 4 máy (Windows Server 2022 và 2025, Python 3.12 và 3.14), mỗi máy chạy 2 lần, mọi mã phải trùng nhau. Máy ảo Linux chạy toàn bộ test, kể cả mã tham chiếu Linux và test trang web trên Chromium (`.github/workflows/linux.yml`); gói `TKB.exe` được dựng và chạy thử trên Windows (`.github/workflows/dong_goi.yml`: xếp bằng `TKB.exe --cli`, xếp và Dừng sớm qua giao diện).

## Đầu vào

**Một file Excel duy nhất theo mẫu V8** (ví dụ `data/INPUT_V8.xlsx`) gồm 2 sheet bắt buộc `NHÂN SỰ`, `CHƯƠNG TRÌNH HỌC` (kèm các cột quy định của môn) và các sheet không bắt buộc `LỚP` (danh sách lớp: tên lớp, tên khối tùy ý, lớp có thể chưa có GVCN), `CHỨC VỤ` (chức vụ GV chuyên biệt tự đặt), `QUY ĐỊNH` (khung giờ, ai được bù, nhãn của ngày và tiết), `LUẬT` (mọi luật xếp TKB, mỗi dòng một câu ghép; không có thì dùng các luật có sẵn). Chương trình tìm sheet theo tên, không phân biệt hoa thường; các sheet khác (ví dụ `HƯỚNG DẪN`) được bỏ qua. Tiêu đề cột phải đúng mẫu: `Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần`, thêm 7 cột không bắt buộc `Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ | Chức Vụ Thêm | Nhãn`.

**Sheet `NHÂN SỰ`:**

| Họ và Tên | Chức Vụ | Lớp | Số Tiết/Tuần | Thai Sản | Hợp Đồng | Cơ sở 2 | Lớp Đang Dạy | Buổi Nghỉ | Chức Vụ Thêm | Nhãn |
|---|---|---|---|---|---|---|---|---|---|---|
| Nguyễn Văn A | Chủ Nhiệm | 1D15 | 19 | | Có | | | | | |
| Trần Thị B | Chủ Nhiệm | 3D23 | 15 | Có | | Có | | 2 buổi chiều | | |
| Lê Văn C | Bộ Môn | | 19 | Có | | | | Chiều T5, Sáng T6 | | |
| Phạm D | Tiếng Anh | | 23 | | | | 3D17, 3D18 | | | Bán thời gian |
| Hoàng E | Chủ Nhiệm | 2A | 23 | | | | | | Tiếng Anh | |

- **Họ và Tên** có thể để trống (vì bảo mật). Khi đó TKB ghi **Mã GV**, ví dụ `Chủ Nhiệm 1/1`, `Tiếng Anh 2`, `Bộ Môn 3`.
- **Chức Vụ**:
  - `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý`, một chức vụ của sheet `CHỨC VỤ` (giáo viên chuyên biệt, chỉ dạy các môn ghi ở đó), hoặc **đúng tên một môn** trong sheet `CHƯƠNG TRÌNH HỌC`, ví dụ `Tiếng Anh`, `Thể Dục`, `Tin Học`. Chức vụ trùng tên môn là giáo viên chuyên biệt, chỉ dạy môn đó.
  - Không có danh sách chức vụ cố định trong code, nên trường có môn mới (ví dụ `Múa`) chỉ cần thêm dòng môn và giáo viên `Múa`.
  - **Không ghi số thứ tự**: chương trình tự đánh số theo thứ tự dòng (Bộ Môn thứ nhất là `Bộ Môn 1`, thứ hai là `Bộ Môn 2`…).
  - Chức vụ không khớp môn nào thì báo lỗi kèm số dòng.
- **Lớp** chỉ ghi cho Chủ Nhiệm: một lớp của sheet `LỚP`; file không có sheet `LỚP` (hoặc sheet trống) thì ghi dạng **khối/số thứ tự** (`1/1`, `5/5`) hoặc **khối rồi tên lớp** (`1D15`, `2A`), khối là các chữ số đầu. Nên định dạng cột là chữ (Text) để Excel không đổi `1/1` thành ngày tháng.
- **Số Tiết/Tuần** là mức tối đa mỗi tuần của từng người (ai được giảm tiết thì ghi mức đã giảm).
- **Thai Sản**, **Hợp Đồng**, **Cơ sở 2**: ghi `Có` hoặc để trống.
  - Thai sản: không dạy bù, và chỉ dạy các lớp ở cơ sở 2. GVCN thai sản thì lớp phải ở cơ sở 2.
  - Hợp đồng: khi phải bù, GVCN hợp đồng bù trước GVCN khác, bộ môn hợp đồng bù trước bộ môn khác.
  - Cơ sở 2: trên dòng Chủ Nhiệm nghĩa là lớp đó học ở cơ sở 2; trên dòng khác nghĩa là GV đó chỉ dạy ở cơ sở 2.
- **Lớp Đang Dạy** (GV bộ môn, chuyên biệt): các lớp người đó dạy trong TKB cũ, cách nhau bằng dấu phẩy. TKB mới ưu tiên giữ người đó ở khối cũ, sau đó ở lớp cũ.
- **Buổi Nghỉ**: buổi cố định (`Chiều T5`, `Sáng thứ 6`) và/hoặc số buổi bất kỳ (`2 buổi chiều`, `1 buổi sáng`, `2 buổi`), cách nhau bằng dấu phẩy; không phân biệt hoa thường, có dấu hay không. Chương trình không xếp tiết vào các buổi đó; với "số buổi bất kỳ" thì chương trình tự chọn buổi. GVCN không nghỉ buổi sáng được, vì tiết 1 luôn do GVCN dạy.
- **Chức Vụ Thêm**: các chức vụ khác người đó cũng giữ, cách nhau bằng dấu phẩy: `Bộ Môn` hoặc một chức vụ GV chuyên biệt (của sheet `CHỨC VỤ` hay trùng tên môn), không ghi số thứ tự. Người đó dạy được cả các môn của các chức vụ này, ở mọi lớp, trong định mức của mình; Mã GV vẫn theo chức vụ chính (cột Chức Vụ).
  - Ví dụ `Hoàng E` ở bảng trên: GVCN lớp 2A, dạy thêm Tiếng Anh ở các lớp khác.
  - **Chủ Nhiệm ghi `Bộ Môn`** thì dạy được các môn của bộ môn ở cả lớp khác: đó là cách bỏ "GVCN chỉ dạy lớp mình" cho từng người.
  - Chủ Nhiệm có chức vụ thêm chỉ nhận trọn các môn GVCN nhận trọn của lớp mình (và môn cùng nhóm, vd Tiếng Việt tăng cường đi với Tiếng Việt), không nhận thêm môn cho đủ định mức: phần định mức còn lại dùng cho chức vụ thêm. Khi phải bù, người đó bù như bộ môn (bù các tiết theo chức vụ thêm); ở chế độ tuyển thêm, người mới dạy các tiết đó có chức vụ dạy được môn đó.
  - `Chủ Nhiệm`, `Quản Lý` chỉ là chức vụ chính; Quản Lý không ghi chức vụ thêm.
- **Nhãn**: các nhãn tự đặt, cách nhau bằng dấu phẩy (vd `Bán thời gian`, `Tổ Toán`). Nhãn không tự có nghĩa gì; cột
  Giáo viên của sheet `LUẬT` ghi một nhãn là mọi giáo viên có nhãn đó, vd luật `Không xếp vào`, Giáo viên
  `Bán thời gian`, Buổi `Chiều`. Thai Sản, Hợp Đồng, Cơ sở 2 ghi `Có` cũng là nhãn cùng tên (Chủ Nhiệm có lớp ở cơ sở 2
  có nhãn `Cơ sở 2`), vd luật cho mọi giáo viên `Hợp Đồng`.
- Các cột khác (ví dụ cột STT, cột ghi chú) được bỏ qua, ghi gì cũng được.
- Danh sách lớp lấy từ các dòng Chủ Nhiệm, vì mỗi lớp luôn có một GVCN. Nếu dãy lớp của một khối bị hụt (ví dụ có 1/3, 1/5 mà không có 1/4) thì chương trình cảnh báo.
- Khi file có lỗi, chương trình **liệt kê tất cả lỗi một lần** kèm số dòng (ví dụ `Lớp 1/1 có hai Chủ Nhiệm (dòng 11 và 26)`).

**Sheet `CHƯƠNG TRÌNH HỌC` (bắt buộc):** Môn học | Khối `<tên>` … (số tiết/tuần; tên khối tùy ý: `Khối 1`, `Khối Lá`, `Khối Year 7`; tên toàn chữ số là khối số) | các cột quy định của môn (không bắt buộc, xem dưới). Dòng `Tổng` (nếu có) được bỏ qua. Các khối sắp theo số rồi theo tên (thứ tự các sheet Khối của file TKB).
- Danh sách môn và tên môn lấy nguyên từ file, TKB in đúng tên trong file. Riêng các môn có ghi cột `Tên trong TKB` (mặc định HĐTN, TNXH, TV tăng cường) được viết tắt trong ô TKB.
- Sheet không có cột quy định thì môn nào trùng tên một môn có quy định mặc định trong `tkb/config.py` nhận luật đó. So khớp không phân biệt hoa thường, dấu câu và chữ "và": `Lịch Sử và Địa Lý` khớp `Lịch sử - Địa lý`. Nếu quy định mặc định nhắc một môn mà chương trình học không có (thường do gõ khác tên), chương trình cảnh báo.

**Quy định nghiệp vụ (không bắt buộc):** nhà trường sửa trong Excel, không cần sửa code. Quy định của từng môn là **các cột của sheet `CHƯƠNG TRÌNH HỌC`** (sau các cột Khối), nên tên môn chỉ ghi một chỗ; các quy định khác nằm ở **sheet `QUY ĐỊNH`**, ba bảng nhỏ xếp chồng, cách nhau một dòng trống (quy định chung, ngày, tiết).
- **Một quy ước cho mọi ô:** mỗi quy định là một cột (bảng quy định chung: một dòng); mỗi ô chỉ ghi **Có**, **Không** hoặc **một số nguyên dương**; ô trống là Không (hoặc không áp dụng). Riêng cột `Tên trong TKB` ghi chữ. Nhìn cột là biết quy định nào khác mặc định.
- Cột, bảng (hoặc dòng của bảng chung) nào không có thì quy định đó dùng giá trị mặc định trong `tkb/config.py` (cột Mặc định dưới đây), nên file chỉ có `Môn học | Khối…` vẫn chạy như trước. Cột đã có thì là đủ: môn, ngày, tiết không có dòng tính là Không. Ghi đúng giá trị mặc định thì cùng TKB, cùng mã kết quả như không ghi.
- Hai cột `Bộ Môn không dạy`, `Không ghép cặp` ghi theo ngoại lệ, để môn mới thêm vào (ô trống) mặc nhiên bộ môn dạy được và được ghép cặp như thường.
- Có/Không viết hoa hay thường, có dấu hay không đều được (`x` cũng là Có).
- Ghi sai (ô không phải Có/Không/số, số thứ tự trùng, hai môn HĐTN, ngày học không liền nhau, tiết không có trong khung giờ, cột lạ ở sheet `QUY ĐỊNH`…) thì chương trình liệt kê mọi lỗi một lần kèm sheet và số dòng, không xếp. Cột lạ ở sheet `CHƯƠNG TRÌNH HỌC` (vd gõ sai tên quy định) thì cảnh báo và bỏ qua.
- Màn hình in `Quy định: đọc từ file vào, khác mặc định: …` để biết quy định nào đang khác mặc định.
- File vào cập nhật (`_cap_nhat`) luôn ghi đủ các quy định đã dùng (thêm cột, thêm sheet `CHỨC VỤ`, `QUY ĐỊNH` nếu file vào chưa có).
- Mẫu cũ (4 sheet `QUY ĐỊNH CHUNG/NGÀY/TIẾT/MÔN`) không còn đọc: chương trình báo lỗi, nhắc tạo file mẫu mới.
- Trọng số mục tiêu, tham số xếp giờ vẫn ở `tkb/config.py`; số tiết bù tối đa ở `main.py` (`SO_TIET_BU_TOI_DA`).

**Các cột quy định của sheet `CHƯƠNG TRÌNH HỌC`** (sau các cột Khối, mỗi môn một dòng):

| Cột | Mặc định | Ý nghĩa |
|---|---|---|
| Tên trong TKB | Hoạt động trải nghiệm: HĐTN, Tự nhiên xã hội: TNXH, Tiếng Việt tăng cường: TV tăng cường | Chữ ghi trong ô TKB (cột duy nhất ghi chữ); trống: ghi đúng tên môn. |
| Môn HĐTN | Có: HĐTN | Có ở một môn: môn chào cờ, sinh hoạt lớp, có tiết cố định ở bảng ngày của sheet QUY ĐỊNH. |
| GVCN nhận trọn | Có: Tiếng Việt, Toán, HĐTN, Khoa học, Lịch sử - Địa lý, Đạo đức | GVCN nhận hết các môn này của lớp mình; luật cứng: môn nào phải chia cho người khác thì tiết đầu tiên trong tuần do GVCN dạy. |
| GVCN cắt bớt | Tiếng Việt: 1, Toán: 2, Khoa học: 3, Lịch sử - Địa lý: 4 | Số thứ tự 1, 2...: môn cắt trước khi các môn nhận trọn vượt định mức GVCN; mỗi môn GVCN giữ ít nhất 1 tiết. |
| GVCN nhận thêm | TV tăng cường: 1, Toán tăng cường: 2, TNXH: 3, Kỹ năng sống: 4, Công nghệ: 5 | Số thứ tự 1, 2...: môn GVCN nhận thêm trước cho đủ định mức (không nhận môn của GV chuyên biệt). |
| Chỉ GVCN dạy | Có: HĐTN | Luật cứng: chỉ GVCN của lớp được dạy. |
| Bộ Môn không dạy | Có: HĐTN, Tiếng Anh, Tin học | GV bộ môn không dạy môn này; trường chưa có GV chuyên biệt của môn thì chương trình tuyển thêm. Ghi theo ngoại lệ để môn mới (ô trống) mặc nhiên bộ môn dạy được. |
| Quản lý dạy khối | Kỹ năng sống: 4 | Khối mà Quản Lý được dạy môn này (tên khối như ở cột Khối `<tên>`), vd Kỹ năng sống: 4. |
| GVCN bù môn chuyên biệt | Có: Âm nhạc, Mỹ thuật | Môn có GV chuyên biệt mà GVCN vẫn được dạy bù ở lớp mình (nhận sau cùng). |
| Nhóm môn | Tiếng Việt: 1, TV tăng cường: 1, Toán: 2, Toán tăng cường: 2 | Môn chính và các môn tăng cường của nó ghi cùng một số, vd Tiếng Việt và Tiếng Việt tăng cường: 1. |
| Môn tăng cường | Có: Toán tăng cường, TV tăng cường | Có ở môn tăng cường của nhóm; luật cứng: tiết tăng cường đứng sau mọi tiết môn chính trong ngày và ngày đó phải có tiết môn chính; cả nhóm tính chung cho giới hạn mỗi buổi và ghép cặp. |
| Không ghép cặp | Có: Toán, HĐTN | Nhóm môn (ghi ở môn chính) không xếp thành cặp 2 tiết liền. Ghi theo ngoại lệ như cột Bộ Môn không dạy. |
| Môn nặng | Có: Tiếng Việt, Toán, Tiếng Anh, Khoa học, Tin học, Toán tăng cường, TV tăng cường | Mục tiêu mềm: hạn chế xếp vào các tiết Hạn chế môn nặng (sheet QUY ĐỊNH). |
| Ưu tiên buổi sáng | Có: Tiếng Việt, Toán | Mục tiêu mềm: mỗi tiết ở buổi chiều bị trừ điểm, và môn được rải đều hơn trong tuần. |

Ba quy định của bản trước nay là **số của một dòng luật** ở sheet LUẬT: `Tối đa tiết mỗi ngày` (cột của sheet CHƯƠNG
TRÌNH HỌC; dòng "Mỗi ngày, một lớp học tối đa 1 tiết Toán, khi số tiết/tuần của môn không quá số ngày học"), `Số tiết tối đa
một nhóm môn mỗi buổi` và `Ghép cặp khi nhóm môn có từ (tiết/tuần)` (sheet QUY ĐỊNH). File cũ ghi các cột đó vẫn đọc
được (khi không có sheet LUẬT); file mẫu không còn các cột đó. Các cột Có/Không còn lại là dữ liệu và **nhãn** để các
dòng luật dùng (vd luật "Tránh xếp môn có nhãn Môn nặng vào giờ có nhãn Hạn chế môn nặng").

**Sheet `QUY ĐỊNH`**, bảng 1 (`Quy định | Giá trị`):

| Quy định | Mặc định | Ý nghĩa |
|---|---|---|
| Chủ Nhiệm được dạy bù | Có | GVCN chỉ bù ở lớp mình và bù trước bộ môn. |
| Bộ Môn được dạy bù | Có | Bộ môn bù khi GVCN đã bù hết mức. |

**Sheet `QUY ĐỊNH`**, bảng 2 (`Ngày`: mỗi ngày học một dòng) và bảng 3 (`Tiết`: mỗi tiết một dòng):

| Cột | Mặc định | Ý nghĩa |
|---|---|---|
| Ngày | Thứ 2 … Thứ 6 | Tên ngày học, tùy ý (vd Thứ 7, Chủ nhật, Mon), theo thứ tự trong tuần; thêm ngày thì thêm dòng. |
| Buổi `<tên>` (vd `Buổi Sáng`, `Buổi Chiều`) | Sáng 4 tiết mọi ngày; Chiều 3 tiết Thứ 2 – Thứ 5 | Số tiết của buổi đó trong ngày; ô trống: ngày đó không học buổi đó. Số buổi, tên buổi tùy ý (thêm cột `Buổi Tối`…); mỗi ngày một số tiết riêng (vd chiều Thứ 5 có 4 tiết). Tiết đánh số liên tục trong ngày theo thứ tự cột: sáng 4 tiết thì chiều từ tiết 5. Ngày không có tiết nào không phải ngày học. |
| Tiết HĐTN cố định | Thứ 2: 1, Thứ 6: 4 | Luật cứng: tiết môn HĐTN cố định của ngày đó ở mọi lớp, vd Thứ 2: 1, Thứ 6: 4. |
| Xếp tiết HĐTN còn lại | Có: Thứ 3, Thứ 4, Thứ 5 | Luật cứng: các tiết HĐTN còn lại chỉ xếp vào các ngày này (mục tiêu mềm: gần cuối buổi). |
| Luôn do GVCN dạy | Có: tiết 1 | Luật cứng: tiết này ở mọi ngày do GVCN của lớp dạy. |
| Hạn chế môn nặng | Có: tiết 7 | Mục tiêu mềm: mỗi tiết môn nặng ở tiết này bị trừ điểm. |

**Sheet `LỚP`** (không bắt buộc): danh sách lớp, **mỗi dòng một lớp**: `Lớp | Khối | Cơ sở 2 | Nhãn` (thêm cột `Ghi chú`
tùy ý), vd `Lá 1 | Lá | Có | Song ngữ`.
- **Lớp**: tên tùy ý, không trùng nhau (không phân biệt hoa thường). **Khối**: tên khối như ở các cột `Khối <tên>` của
  sheet `CHƯƠNG TRÌNH HỌC`; để trống thì là các chữ số đầu tên lớp (`3/1` là khối 3). **Cơ sở 2**: `Có` nếu lớp học ở cơ
  sở 2 (hoặc đánh dấu ở dòng Chủ Nhiệm như trước). **Nhãn**: các nhãn tự đặt, cách nhau bằng dấu phẩy, không trùng tên
  lớp; cột Lớp của sheet `LUẬT` ghi một nhãn là mọi lớp có nhãn đó (lớp ghi Cơ sở 2 = `Có` có nhãn `Cơ sở 2`), vd luật
  `Không xếp vào`, Môn `Tiếng Anh`, Lớp `Song ngữ`, Ngày `Thứ 6`.
- Có sheet này thì Chủ Nhiệm ghi Lớp là một lớp của sheet, cột Lớp Đang Dạy và cột Lớp của sheet `LUẬT` cũng theo tên
  này. **Lớp chưa có Chủ Nhiệm** vẫn được xếp: mọi môn của lớp chia cho giáo viên khác; tiết **Luôn do GVCN dạy**, luật
  "GVCN dạy tiết đầu tuần" không áp dụng cho lớp đó; tiết HĐTN vẫn cố định như các lớp khác; môn **Chỉ GVCN dạy** thì
  lớp phải có Chủ Nhiệm (chương trình báo lỗi ghi rõ lớp, môn).
- Không có sheet, hoặc sheet chỉ có dòng tiêu đề: lớp là lớp của các dòng Chủ Nhiệm, cùng mã quy định, cùng mã kết quả
  như trước. Ghi đúng các lớp của Chủ Nhiệm thì TKB như không có sheet (mã quy định có thêm danh sách lớp).

**Sheet `CHỨC VỤ`** (không bắt buộc): các chức vụ giáo viên chuyên biệt do trường đặt tên, **mỗi dòng một chức vụ**:
`Chức vụ | Môn được dạy` (thêm cột `Ghi chú` tùy ý), vd `GV Nghệ thuật | Âm nhạc, Mỹ thuật`. Giáo viên có Chức Vụ
`GV Nghệ thuật` chỉ dạy Âm nhạc và Mỹ thuật; hai môn đó là môn chuyên biệt (GVCN không nhận thêm, bộ môn chỉ dạy phần
GV chuyên biệt không dạy hết).
- Tên không ghi số, không trùng `Chủ Nhiệm`, `Bộ Môn`, `Quản Lý` (quyền dạy của ba chức vụ này là các cột Chỉ GVCN dạy,
  Bộ Môn không dạy, Quản lý dạy khối của sheet `CHƯƠNG TRÌNH HỌC`). Các môn cách nhau bằng dấu phẩy, đúng tên trong
  sheet `CHƯƠNG TRÌNH HỌC`. Ghi sai thì chương trình báo kèm số dòng.
- Chức vụ trùng tên một môn không cần ghi ở đây (vẫn chỉ dạy môn đó); ghi `Tiếng Anh | Tiếng Anh` cũng như không ghi.
- Môn Bộ Môn không dạy mà chưa có ai dạy được: chương trình tuyển chức vụ đầu tiên ở đây dạy môn đó (không có thì chức
  vụ trùng tên môn), vd một `GV Ngoại ngữ Tin học` thay vì một người Tiếng Anh và một người Tin học.
- File vào cập nhật ghi thêm sheet này nếu chưa có (các chức vụ GV chuyên biệt đang có), để thấy mỗi chức vụ dạy môn
  nào. Không có sheet, hoặc chỉ có các dòng trùng tên môn, thì cùng mã kết quả, cùng mã quy định như trước.

**Sheet `LUẬT`**: **mọi luật xếp TKB**, mỗi dòng một luật, không cần sửa code. File mẫu ghi sẵn **các luật có sẵn**
của chương trình (23 luật, nhóm Bảo vệ học sinh, HĐTN và GVCN, Người dạy, Lịch giáo viên, Ưu tiên khi xếp giờ): sửa số
hoặc Điểm để chỉnh, đổi Bắt buộc/Ưu tiên, xóa dòng để bỏ luật, thêm dòng để có luật mới. Muốn **tạm tắt** một luật mà
vẫn giữ dòng thì ghi `Có` ở cột **Tạm tắt** (cột cuối): chương trình bỏ qua dòng đó như khi xóa (cùng mã quy định), cột
Luật đọc là ghi `(Tạm tắt) …`, sheet Chất lượng ghi "tắt"; xóa chữ `Có` là dùng lại. Dòng luật có sẵn chưa sửa dạng
(chỉ khác số, điểm) thì chương trình xếp như trước, nên để mặc định thì cùng mã kết quả. Không có sheet này (file của
bản trước) thì dùng các luật có sẵn, cộng các luật của sheet `LUẬT RIÊNG` cũ. Phần không phải luật vẫn ở chương trình:
mỗi lớp mỗi giờ học một tiết, đủ số tiết của chương trình học, giáo viên không dạy hai nơi cùng lúc và không quá định
mức, chỉ dạy các môn chức vụ được dạy. Mỗi luật là một câu của **bộ ghép luật** (`tkb/bo_ghep.py`):

> **Với mỗi** [phạm vi] · **các tiết** [Môn, Nhãn, Khối, Lớp, Ngày, Tiết, Buổi, Giáo viên] · **thì** [Phép đo] [So sánh]
> [Số] · **khi** [Áp dụng khi] · [Bắt buộc / Mức / Điểm]

Mỗi luật trả lời một trong **bốn câu hỏi** về các tiết, và các mẫu, phép đo xếp theo đó (cột `Kiểu luật`, `Phép đo`
ghi như cũ; giao diện và sheet HƯỚNG DẪN chia theo bốn câu hỏi):

| Câu hỏi | Mẫu | Phép đo (Tự ghép) |
|---|---|---|
| **Ở đâu** | Không xếp vào, Chỉ xếp vào, Cố định vào | Vị trí |
| **Bao nhiêu** | Giáo viên tối đa tiết mỗi ngày, Giáo viên tối đa lớp mỗi ngày, Số lớp học cùng lúc tối đa, Học ít nhất số ngày | Số tiết, Số khác nhau, Khoảng cách |
| **Đi cùng nhau** | Học 2 tiết liền, Học trước | Liền nhau, Theo cặp 2 tiết, Thứ tự, Đi kèm |
| **Ai dạy** | Chỉ giáo viên dạy, Buổi nghỉ của giáo viên, Giáo viên chỉ dạy cơ sở 2 | Người dạy |

Cột: `Nhóm | Kiểu luật | Với mỗi | Môn | Gồm môn tăng cường | Nhãn | Trừ nhãn | Khối | Lớp | Ngày | Tiết | Buổi |
Giáo viên | Phép đo | So sánh | Số | Đếm theo | Môn thứ hai | Áp dụng khi | Bắt buộc | Mức | Điểm | Luật đọc là` (cột Nhóm
và Luật đọc là chỉ để đọc, chương trình ghi lại; thêm cột `Ghi chú` tùy ý; chương trình tìm cột theo tiêu đề). `Kiểu luật` là một **mẫu** (điền sẵn phạm vi, phép đo) hoặc
**Tự ghép** (ghi đủ Với mỗi, Phép đo, So sánh). Cột không dùng để trống.

| Mẫu | Cột dùng | Ví dụ |
|---|---|---|
| Không xếp vào | Môn, Khối, Lớp, Nhãn, Ngày / Tiết / Buổi (ít nhất một), Giáo viên | Thể dục không học tiết 1; Tin học không học Thứ 2; **giờ bận**: Giáo viên `Bộ Môn 3`, Thứ 2, tiết 1, để trống Môn |
| Chỉ xếp vào | như trên | Thể dục chỉ học buổi chiều; Giáo viên `Bộ Môn 3` chỉ dạy buổi sáng |
| Học 2 tiết liền | Môn, Khối, Lớp | Tiếng Anh khối 3–5 học thành cặp 2 tiết liền, cùng người dạy |
| Học trước | Môn, Môn thứ hai, Khối, Lớp | Tiếng Việt học trước Toán khi cùng buổi |
| Giáo viên tối đa tiết mỗi ngày | Giáo viên (chức vụ hoặc một người; trống: mọi GV), Số | Mỗi GV Tiếng Anh dạy tối đa 5 tiết mỗi ngày |
| Số lớp học cùng lúc tối đa | Môn, Khối, Số | Phòng Tin học: tối đa 1 lớp mỗi tiết |
| Cố định vào | Môn, Khối, Lớp, Ngày / Tiết / Buổi | Thể dục lớp 1/1 cố định Thứ 3 tiết 3 |
| Giáo viên tối đa lớp mỗi ngày | Giáo viên, Số | Mỗi GV Bộ Môn dạy tối đa 3 lớp mỗi ngày |
| Học ít nhất số ngày | Môn, Khối, Lớp, Số | Tiếng Anh học ít nhất 3 ngày mỗi tuần |
| Chỉ giáo viên dạy | Môn, Khối, Lớp, Ngày / Tiết / Buổi, Giáo viên | Tin học khối 3 chỉ GV Tin học dạy; **ép phân công**: Tiếng Anh lớp 3/1 chỉ `Tiếng Anh 2` dạy |
| Buổi nghỉ của giáo viên | (chỉ Bắt buộc) | Theo cột Buổi Nghỉ của sheet NHÂN SỰ |
| Giáo viên chỉ dạy cơ sở 2 | (chỉ Bắt buộc) | Theo cột Cơ sở 2, Thai Sản của sheet NHÂN SỰ |

**Tự ghép**: `Với mỗi` ghi các chiều `Lớp, Giáo viên, Môn, Nhóm môn, Khối, Ngày, Buổi, Giờ học, Cơ sở` (trống: cả
trường cả tuần); các cột điều kiện chọn tiết nào được xét; `Phép đo` là một trong 9 phép đo:

| Phép đo | So sánh | Ví dụ |
|---|---|---|
| Số tiết | Tối đa / Tối thiểu / Đúng + Số (hoặc `tải ngày`, `tải ngày + 1`, `số tiết/tuần chia số ngày`) | Mỗi lớp, mỗi ngày: học tối đa 1 tiết Toán |
| Số khác nhau | như trên + `Đếm theo` | Mỗi giáo viên, mỗi ngày: dạy tối đa 3 lớp khác nhau |
| Vị trí | Chỉ trong / Không trong (Ngày, Tiết, Buổi, nhãn giờ học) | Các tiết môn có nhãn Môn nặng không xếp vào tiết 7 |
| Liền nhau | — | Mỗi lớp, mỗi môn: các tiết trong một buổi đứng liền nhau |
| Theo cặp 2 tiết | — | Mỗi lớp: các tiết Tiếng Anh xếp thành cặp 2 tiết liền trong buổi |
| Thứ tự | Trước / Sau + `Môn thứ hai` (trống: các môn khác cùng nhóm) | Mỗi lớp, mỗi nhóm môn, mỗi ngày: các tiết môn có nhãn Môn tăng cường đứng sau các tiết môn khác cùng nhóm |
| Đi kèm | — + `Môn thứ hai` | Mỗi lớp, mỗi ngày: có tiết Toán tăng cường thì cũng có tiết Toán |
| Người dạy | Do (+ Giáo viên) / Cùng một người / Liền nhau cùng người / Tiết đầu tuần do | Các tiết ở giờ có nhãn Luôn do GVCN dạy do GV chủ nhiệm dạy |
| Khoảng cách | Tiết trống tối đa / Cách cuối buổi tối đa + Số | Mỗi giáo viên, mỗi buổi: các tiết không có tiết trống xen giữa |

`Nhãn`, `Trừ nhãn` là tên các cột Có/Không của môn (vd `Môn nặng`, `Ưu tiên buổi sáng`) hoặc của ngày, tiết (vd `Luôn
do GVCN dạy`, `Hạn chế môn nặng`): thêm một cột Có/Không là có thêm một nhãn; nhiều nhãn giờ học là giờ có một trong
các nhãn.
`Giáo viên` ghi chức vụ, hoặc `trừ Chủ Nhiệm` (mọi giáo viên trừ chức vụ đó), hoặc **một người**: Mã GV (`Bộ Môn 3`,
`Chủ Nhiệm 1/1`, như ở các file ra) hay họ tên. `Gồm môn tăng cường` = Có thì Môn tính cả các môn tăng
cường cùng nhóm. `Áp dụng khi` đặt điều kiện trên số tiết/tuần của các môn của luật ở từng khối, vd `>= 6, chẵn` hay
`<= số ngày` (phạm vi có Môn, Nhóm môn thì xét từng môn, nhóm môn). Câu đọc lại của mỗi luật có ở giao diện, ở thông
báo lỗi và ở cột Luật đọc là; dòng ở dạng gốc của một luật có sẵn đọc bằng tên riêng của luật đó (vd "Tránh xếp môn
có nhãn Môn nặng vào giờ có nhãn Hạn chế môn nặng"), dòng khác đọc bằng câu ghép, không dùng ký hiệu (`>=` đọc là "từ …
trở lên").

- **Bắt buộc** `Có`: TKB phải theo đúng (luật cứng, bộ kiểm tra độc lập kiểm lại). `Không` hoặc trống: **ưu tiên**
  (mục tiêu mềm): **Điểm** là điểm trừ mỗi lần không theo (các luật có sẵn ghi sẵn điểm, vd môn nặng ở tiết hạn chế
  1.200), hoặc **Mức** `Thấp`, `Vừa`, `Cao`, `Rất cao` (hoặc `1`–`4`; trống là Vừa): 100, 400, 1.500, 5.000 điểm.
  Câu đọc lại ghi mức bằng chữ, dòng ghi Điểm đọc theo mức gần nhất (vd 1.200 điểm là "ưu tiên cao"). Sau khi xếp,
  màn hình in số lần không theo từng luật ưu tiên của luật thêm vào.
- Môn, Lớp, Khối, Ngày, Tiết ghi danh sách: `3, 4`, `3-5`; `Thứ 2, Thứ 4`, `T2-T4`; `1`, `5-7`. Buổi: `Sáng` hoặc
  `Chiều`.
  Lớp: tên lớp, hoặc một nhãn lớp của sheet `LỚP` (mọi lớp có nhãn đó).
  Giáo viên: chức vụ như cột Chức Vụ (`Chủ Nhiệm`, `Bộ Môn`, `Quản Lý` hoặc chức vụ GV chuyên biệt, vd `Tiếng Anh`;
  khớp cả người ghi chức vụ đó ở cột Chức Vụ Thêm), một nhãn ở cột Nhãn của sheet NHÂN SỰ (mọi giáo viên có nhãn đó; khác
  cột Nhãn của sheet `LUẬT` là nhãn của môn, của giờ), hoặc một người: Mã GV (`Bộ Môn 3`: người thứ 3 có chức vụ Bộ Môn theo thứ tự dòng của sheet NHÂN SỰ; `Chủ Nhiệm 1/1`)
  hay họ tên (hai người trùng tên thì phải ghi Mã GV). Câu đọc lại, thông báo lỗi và file ra luôn ghi **Mã GV**, không
  ghi họ tên. Thêm hay xóa một dòng nhân sự làm đổi số thứ tự trong Mã GV của những người sau đó. **Trên giao diện**,
  luật tự đi theo đúng người: xóa, dời, đổi chức vụ, đổi lớp hay đổi tên một người thì cột Giáo viên của các luật đổi
  theo; người bị xóa thì luật ghi họ tên của họ (không có tên: `<Mã GV> (đã xóa)`) để Kiểm tra báo luật đó, không âm
  thầm áp cho người khác. Sửa tay trong Excel thì luật dùng lâu dài nên ghi họ tên.
  - **Giờ bận theo tiết**: `Không xếp vào`, Giáo viên `Bộ Môn 3`, Ngày `Thứ 2`, Tiết `1`, để trống Môn: người đó không
    dạy giờ đó (bắt buộc), phân công cũng tính bớt giờ đó. Khác cột Buổi Nghỉ của sheet NHÂN SỰ (nghỉ cả buổi).
  - **Ép phân công**: `Chỉ giáo viên dạy`, Môn `Tiếng Anh`, Lớp `3/1`, Giáo viên `Tiếng Anh 2`: chỉ người đó nhận các
    tiết đó (người đó phải được dạy môn này theo chức vụ). Không ai nhận được thì chương trình báo lỗi kèm dòng luật.
- Ghi sai (kiểu luật lạ, thiếu cột cần, ghi cột không dùng, môn, chức vụ hay người không có, họ tên trùng nhau…) thì
  chương trình báo kèm số dòng.
  Luật bắt buộc mâu thuẫn (với nhau hoặc với các quy định khác) thì chương trình đếm trước hoặc chẩn đoán và chỉ ra
  đúng dòng luật, vd `LUẬT dòng 27: Tiếng Anh khối 3, 4, 5 học 2 tiết liền (bắt buộc)`.
- "Học 2 tiết liền" bắt buộc: số tiết/tuần phải chẵn, mỗi người dạy số tiết chẵn ở lớp đó (phân công tự đổi chéo để
  chẵn); dùng chung cơ chế ghép cặp của luật bảo vệ học sinh (tắt luật học sinh thì luật này cũng tắt). Giáo viên dạy
  nhiều lớp phải ghép cặp mà tiết 1 luôn do GVCN dạy thì mỗi buổi sáng chỉ ghép được một cặp: khi đó nên để ưu tiên.
- Các luật để mặc định (hoặc không có sheet LUẬT) thì mọi thứ như trước (cùng mã kết quả, cùng mã quy định).

Chỉ đọc mẫu V8. File mẫu cũ (V5–V7: chức vụ ghi kèm số như `bộ môn 5`, chương trình học ở file riêng) không còn đọc được: tạo file mẫu trống rồi chép dữ liệu sang, bỏ số thứ tự ở cột Chức Vụ.

File vào mẫu trống có sẵn: **`data/Input_Template_V8.xlsx`**. Tạo lại (hoặc tạo ở chỗ khác):

```bash
python -m tkb.template data/Mau_Input.xlsx               # bộ luật mẫu Tiểu học Việt Nam
python -m tkb.template data/Mau_Trong.xlsx --mau trong   # bộ Trống: chưa có môn, luật theo quy ước để Tạm tắt
```

File mẫu đơn giản, tiếng Việt: chữ đen, không tô nền, viền mảnh, không cố định dòng/cột, không danh sách thả xuống, không ghi chú trong ô, không sheet ẩn. Gồm 7 sheet: `NHÂN SỰ`, `CHƯƠNG TRÌNH HỌC` (điền sẵn các môn có quy định mặc định và các cột quy định, số tiết để trống), `LỚP` (chỉ có dòng tiêu đề), `CHỨC VỤ` (chỉ có dòng tiêu đề), `QUY ĐỊNH` (điền sẵn giá trị mặc định), `LUẬT` (các luật có sẵn) và `HƯỚNG DẪN` (cách ghi từng cột, từng sheet, từng mẫu luật và phép đo). Cột Lớp, Lớp Đang Dạy định dạng chữ để Excel không đổi `1/1` thành ngày tháng.

## Cái gì nằm trong file vào, cái gì nằm trong code

| Nằm trong file vào | Nằm trong code |
|---|---|
| Danh sách môn, tên môn, số tiết từng khối (`CHƯƠNG TRÌNH HỌC`) | Giá trị mặc định của các quy định (`tkb/config.py`), dùng khi file không ghi; các giá trị gắn tên môn (môn GVCN nhận trọn, môn nặng, HĐTN…) là dữ liệu của bộ luật mẫu Tiểu học Việt Nam (`tkb/bo_mau.py`), code không chứa tên môn nào |
| Giáo viên, chức vụ, lớp chủ nhiệm, số tiết, thai sản, hợp đồng, cơ sở 2, lớp đang dạy, buổi nghỉ (`NHÂN SỰ`) | Trọng số mục tiêu mềm (`config.Weights`) và tham số xếp giờ (`LNS_*`) |
| Danh sách lớp (sheet `LỚP`, không có thì suy ra từ các dòng Chủ Nhiệm), tên khối, GV chuyên biệt (sheet `CHỨC VỤ`, hoặc chức vụ trùng tên môn) | Định mức người cần tuyển (Số tiết lớn nhất của GV cùng chức vụ), luật mỗi buổi một cơ sở, thai sản không bù |
| Khung giờ, HĐTN, tiết của GVCN, môn GVCN nhận/cắt/nhận thêm, quyền dạy, ai được bù, luật bảo vệ học sinh, môn nặng, môn buổi sáng, tên viết tắt (cột quy định của `CHƯƠNG TRÌNH HỌC`, sheet `QUY ĐỊNH`); mọi luật xếp TKB, cả số và điểm (sheet `LUẬT`) | Chế độ, số tiết bù tối đa, thời gian (`main.py`) |
| Style của các file ra (phông, cỡ chữ, viền, chiều cao dòng) | |

## Đầu ra

1. **`TKB.xlsx`**: **chỉ có thời khóa biểu**, mỗi khối một sheet **Khối 1…5** (tên khối như ở sheet `CHƯƠNG TRÌNH HỌC`).
   - **Trường có hai cơ sở** (cột `Cơ sở 2`): tách thành **`TKB_diem_chinh.xlsx`** (các lớp cơ sở 1, điểm chính) và **`TKB_diem_phu.xlsx`** (các lớp cơ sở 2, điểm phụ); `TKB_chuc_vu.xlsx` cũng tách như vậy. Cột ngày ở hai file cùng độ rộng.
   - Mẫu: `data/Output_Template_TKB_V8.xlsx` (TKB của trường mẫu tên giả). Mỗi lớp là một bảng có các cột `LỚP | BUỔI | TIẾT | THỨ 2 … THỨ 6`.
   - Cột LỚP gộp 7 hàng; cột BUỔI gộp thành SÁNG (tiết 1–4) và CHIỀU (tiết 5–7); cột TIẾT ghi số tiết trong ngày. Cột LỚP chỉ ghi tên lớp, ví dụ `3D23` (lớp cơ sở 2 nằm ở file điểm phụ).
   - Mỗi ô ghi môn và **tên giáo viên** trên 2 dòng, ví dụ `HĐTN` rồi xuống dòng `Nguyễn Văn A`. Tên để trống hoặc người cần tuyển thì ghi Mã GV (`Bộ Môn 6`); hai người trùng tên thì kèm Mã GV. Chiều Thứ 6 ghi `Nghỉ`.
   - Các cột ngày ở mọi sheet cùng độ rộng, nới theo dòng dài nhất của cả trường (tối đa 30); tên dài hơn thì xuống dòng và hàng tự cao thêm. Khi in: khổ ngang, co vừa chiều rộng 1 trang.
   - **`TKB_chuc_vu.xlsx`**: cùng TKB, mỗi ô thêm dòng thứ 3 là chức vụ (Mã GV), ví dụ `Tiếng Việt` / tên / `Bộ Môn 4`, để theo dõi ai dạy tiết nào.
2. **`TKB_giao_vien.xlsx`**: **TKB của từng giáo viên**, mẫu: `data/Output_Template_TKB_Giao_Vien_V8.xlsx`.
   - Sheet **`Giáo viên`**: mỗi giáo viên (có tiết dạy, theo thứ tự file nhân sự) một bảng `BUỔI | TIẾT | THỨ 2 … THỨ 6`, dòng tựa ghi tên, Mã GV và số tiết, ví dụ `Nguyễn Văn A (Bộ Môn 2): 23 tiết`. Mỗi ô ghi **lớp** rồi xuống dòng **môn**, ví dụ `3/1` / `Tiếng Anh`; tiết dạy bù thêm `(bù)`, lớp ở cơ sở 2 thêm `(CS2)`. Ngắt trang sau mỗi bảng: **in ra mỗi người một trang** (khổ ngang).
   - Sheet **`Tổng hợp`**: mỗi giáo viên một dòng, mỗi cột một tiết của tuần (`THỨ 2` tiết 1 … ), ô ghi lớp dạy giờ đó: nhìn một bảng thấy cả trường ai dạy lúc nào.
3. **`Thong_Ke.xlsx`**: sheet `Thống kê` và sheet `Chất lượng`, mẫu: `data/Output_Template_Thong_Ke_V8.xlsx`.
   - Mỗi giáo viên một dòng, theo thứ tự file nhân sự, rồi đến người cần tuyển (tên `tuyển thêm`).
   - Cột: **Họ và Tên | Chức Vụ** (Mã GV, ví dụ `Chủ Nhiệm 1/1`, `Bộ Môn 2`) **| số tiết từng môn người đó dạy | Tổng Tiết | Số Tiết/Tuần** (định mức) **| Số Tiết Bù | Số Tiết Dư**. Tiết bù: dạy vượt định mức (chế độ bù giờ); tiết dư: định mức − Tổng Tiết khi dạy ít hơn định mức. Trường có lớp ở cơ sở 2 thì thêm 2 cột cho người **di chuyển giữa hai cơ sở**: **Buổi Ở Cơ Sở 2** (vd `Sáng T3, Chiều T5`) và **Đổi Cơ Sở Trong Ngày** (vd `T5: sáng cơ sở 1, chiều cơ sở 2`); dòng Tổng ghi số người, số lần, dưới bảng có chú thích. Chỉ có cột cho các môn có người dạy, theo thứ tự trong chương trình học; ô trống là không dạy môn đó. Cuối bảng có dòng **Tổng**.
   - **Tô màu cả dòng** để biết ai bù, ai thêm: chế độ bù giờ tô **vàng** dòng người dạy bù (vượt định mức); chế độ tuyển thêm tô **xanh lá** dòng người cần tuyển; người còn dư tiết tô **xanh dương**. Trong dòng người dạy bù, **ô môn có tiết bù tô cam**; số tiết bù từng môn ghi bằng chữ ở cột **Môn Dạy Bù**, ví dụ `TV tăng cường 2, TNXH 1`. Dưới bảng có chú thích màu kèm số người, số tiết, ví dụ `Dạy bù (vượt định mức): 28 người, 56 tiết`, `Môn có tiết dạy bù: 40 ô, 56 tiết (số tiết từng môn ở cột Môn Dạy Bù)`, `Cần tuyển thêm: 3 người, 56 tiết`, `Dạy ít hơn định mức (còn dư tiết): 4 người, 17 tiết`.
   - Chế độ, dự toán, mã kết quả, kết quả kiểm tra luật, người cần tuyển, dạy bù và số liệu cơ sở, thai sản, buổi nghỉ, giữ phân công cũ chỉ in ra màn hình.
   - Sheet **`Chất lượng`**: TKB đã xếp tốt tới đâu, theo **từng dòng luật** của sheet LUẬT: **Nhóm | Luật** (câu đọc lại) **| Mức | Số Lần Không Theo | Điểm Trừ | Ví Dụ** (3 chỗ không theo đầu tiên, vd `lớp 1/5 có Tiếng Anh Thứ 3 tiết 7`), cuối bảng dòng Tổng. Luật bắt buộc luôn 0 (bộ kiểm tra độc lập đã đạt); luật ưu tiên cho biết còn bao nhiêu chỗ chưa theo được và mất bao nhiêu điểm, để so hai lần xếp hay xem sửa luật có tác dụng không. Đếm bằng chính bộ ghép luật (cùng cách đếm khi xếp). Hai luật chỉ có dạng gốc (buổi nghỉ, chỉ dạy cơ sở 2) ghi "kiểm bằng bộ kiểm tra độc lập".
   - **Chế độ bù giờ mà thiếu tiết:** không ra TKB; file này chỉ có sheet `Thiếu tiết`: **Lớp | Môn | Số Tiết Thiếu | Lý Do** và dòng Tổng.
4. **`<tên file vào>_cap_nhat.xlsx`**: bản chép của file vào (đủ các sheet; ghi đủ các quy định đã dùng: thêm cột quy định vào `CHƯƠNG TRÌNH HỌC`, thêm sheet `LỚP` (trống), `CHỨC VỤ`, `QUY ĐỊNH`, `LUẬT` nếu file vào chưa có; sheet `LUẬT RIÊNG` cũ gộp vào `LUẬT`). Sheet NHÂN SỰ có thêm các dòng `chưa có` ở cuối (chép style của dòng trên), Số tiết = định mức tuyển; bên phải thêm cột **Mã GV**, **Số Tiết Thực Dạy** (chế độ bù: **Số Tiết Bù**) và **Số Tiết Dư** (định mức − thực dạy, khi dạy ít hơn định mức). Đây cũng là **bản thống kê gọn theo mẫu file vào**: tô nền cả dòng người dạy bù (vàng), người cần tuyển (xanh lá), người còn dư tiết (xanh dương); sheet **HƯỚNG DẪN** (viết lại mỗi lần) giải thích cách ghi từng cột, cả các cột kết quả và màu, bằng chữ thường. File này dùng làm đầu vào cho lần chạy sau được (các cột thêm được bỏ qua khi đọc, chạy lại thì ghi đè). File còn có sheet **TKB đã xếp** (dạng lưới như TKB, mỗi ô môn + Mã GV): nạp lại file này thì TKB được giữ nguyên nếu vẫn đúng luật (mục [Tuyển được người](#tuyển-được-người-giữ-nguyên-tkb)). File gốc không bị sửa.
5. **Mọi file kết quả chỉ có chữ, số và màu** (cộng thiết lập trang in: khổ ngang, vừa chiều rộng, ngắt trang ở TKB giáo viên): không có ghi chú (comment) trong ô, không có công thức, không cố định dòng/cột, không danh sách thả xuống hay định dạng theo điều kiện. Công thức trong file vào (ví dụ STT `=ROW()-1`) được chép sang file cập nhật dưới dạng giá trị.

**Style:** mọi file ra chép style của sheet NHÂN SỰ trong file vào: phông, cỡ chữ, tiêu đề in đậm, viền, căn lề và chiều cao dòng (làm tròn, ví dụ 24,95 → 25). Bảng ghi tiêu đề cột ở dòng 1 như file vào. Riêng hàng tiết trong TKB cao đủ 2 dòng chữ (môn và giáo viên).

## Quy tắc nghiệp vụ

Dưới đây là các quy tắc với giá trị mặc định. Phần lớn sửa được trong file vào (cột quy định của `CHƯƠNG TRÌNH HỌC`, sheet `QUY ĐỊNH`) (mục [Đầu vào](#đầu-vào)); giá trị mặc định nằm trong `tkb/config.py`.

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
- **Giáo viên chuyên biệt** (chức vụ của sheet `CHỨC VỤ`, ví dụ `GV Nghệ thuật`: chỉ dạy các môn ghi ở đó; hoặc chức vụ trùng tên một môn, ví dụ Tiếng Anh, Tin Học, Thể Dục: chỉ dạy đúng môn đó). Môn bộ môn không được dạy (Tiếng Anh, Tin học) mà trường chưa có ai thì chương trình tự thêm chức vụ để tuyển: chức vụ đầu tiên của sheet `CHỨC VỤ` dạy môn đó, không có thì chức vụ trùng tên môn (ví dụ `Tin Học 1`).
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
- **Cùng TKB với chế độ bù**: các tiết bù chuyển cho người mới, người mới dạy đúng các ô đó; cộng thêm các tiết còn thiếu (nếu có). Khi xếp, mỗi ô bù giữ luật của cả hai người: người bù cũng không dạy hai lớp cùng lúc, không có tiết trong buổi nghỉ, mỗi buổi một cơ sở; tải ngày và tiết trống của người bù tính cả tiết bù.
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
| `giao_dien.py`, `tkb/giao_dien/` | Giao diện web chạy trên máy: máy chủ HTTP thư viện chuẩn (`server.py`), trang HTML/JS không cần Internet (`static/`), xếp TKB ở tiến trình con `python -m tkb` |
| `tkb/kich_ban.py` | Kịch bản của giao diện: file vào V8 ↔ dữ liệu JSON, kiểm tra (đọc lại bằng các hàm đọc của chương trình) và dự toán |
| `tkb/config.py` | Giá trị mặc định của các quy định (khi file vào không ghi), trọng số mục tiêu, tham số xếp giờ |
| `tkb/bo_mau.py` | Các bộ luật mẫu: Tiểu học Việt Nam (giá trị mặc định: tên môn, môn GVCN nhận trọn, môn nặng, HĐTN…) và Trống; `rules.mau` đổi một bộ ra quy định |
| `tkb/rules.py` | Đọc, kiểm tra, ghi các quy định (cột của CHƯƠNG TRÌNH HỌC, sheet LỚP, CHỨC VỤ, QUY ĐỊNH, LUẬT; Có/Không/số); dùng thay giá trị mặc định trong lúc chạy |
| `tkb/staff.py` | Đọc và kiểm tra file nhân sự |
| `tkb/template.py` | Tạo file vào mẫu V8 trống, đơn giản (NHÂN SỰ, CHƯƠNG TRÌNH HỌC kèm quy định môn, LỚP, CHỨC VỤ, QUY ĐỊNH, LUẬT, HƯỚNG DẪN) |
| `tkb/program.py` | Đọc sheet chương trình học, so khớp tên môn với các quy định |
| `tkb/style.py` | Chép style của file vào cho các file ra |
| `tkb/allocation.py` | Chức vụ GV chuyên biệt và các môn được dạy, phân phần GVCN, sinh lớp-môn và danh sách giáo viên được dạy, sinh giáo viên bổ sung, nhóm môn ghép cặp |
| `tkb/phan_cong.py` | Dự toán và phân công giáo viên (luồng chi phí nhỏ nhất, tìm kiếm cục bộ), chia tiết bù cho người mới |
| `tkb/solver.py` | Quy trình giải và mô hình xếp giờ CP-SAT |
| `tkb/lns.py` | Xếp giờ: CP-SAT khởi đầu rồi các vòng QA → xếp lại từng vùng |
| `tkb/checker.py` | Kiểm tra độc lập các luật bắt buộc |
| `tkb/luat_rieng.py` | Dòng luật (sheet LUẬT, LUẬT RIÊNG cũ): đọc/ghi các ô, các mẫu luật, câu đọc lại |
| `tkb/bo_ghep.py` | Bộ ghép luật: phạm vi, điều kiện, 9 phép đo; mỗi phép đo viết một lần cho mô hình CP-SAT, kiểm tra độc lập, QA của LNS, đếm trước, phân công |
| `tkb/luat_co_san.py` | Luật có sẵn là các dòng mặc định của sheet LUẬT; dòng ở dạng gốc xếp như trước (số, điểm lấy từ dòng), luật không còn dòng thì tắt |
| `tkb/chan_doan.py` | Quy định mâu thuẫn: đếm trước khi xếp; khi không xếp được thì thử nới từng nhóm luật để chỉ ra luật nào gây ra |
| `tkb/writer.py` | Xuất Excel |
| `tools/code_map.py` | In bản đồ code (hàm, lớp, `file:dòng`); `--write` sinh lại `docs/CODE_MAP.md` |
| `tools/mau_dau_ra.py` | Sinh lại các file mẫu đầu ra `data/Output_Template_TKB_V8.xlsx`, `data/Output_Template_TKB_Giao_Vien_V8.xlsx`, `data/Output_Template_Thong_Ke_V8.xlsx` từ trường mẫu tên giả (`tkb/truong_mau.py`) |

Hướng dẫn cho Claude Code (lệnh, kiến trúc, luật bảo mật, mã tham chiếu): [`CLAUDE.md`](CLAUDE.md).
