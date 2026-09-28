# Tổng quan các thuật toán tối ưu xếp thời khóa biểu

Tài liệu tra cứu trên nhánh `claude/cp-sat-anlp-development-6uqx3j`: các họ thuật toán trong tài liệu khoa học về xếp
TKB trường phổ thông, và mức độ phù hợp với chương trình này. Đọc cùng `docs/Nghien_Cuu_ALNS.md` (số liệu đo LNS
hiện tại, ALNS, vùng mới, nhiễu mạnh). Chưa đổi code chạy thật.

## 1. Tóm tắt

- Bài toán của trường là dạng **lớp – giáo viên** (class-teacher timetabling): mỗi lớp có TKB riêng, giáo viên đã
  được phân công trước, không xếp phòng. Trong tài liệu nó thuộc nhóm "high school timetabling"; bộ dữ liệu chuẩn là
  XHSTT của cuộc thi ITC 2011.
- Cách hiện tại (CP-SAT khởi đầu rồi xếp lại từng vùng) thuộc họ **matheuristic / fix-and-optimize**, một trong những
  họ mạnh nhất hiện nay (mục 4.2). Các thử nghiệm trước cho thấy tối ưu cục bộ nó đạt được rất "chắc".
- **Khoảng một nửa chi phí là bắt buộc** theo luật cứng: ít nhất 8.640 điểm phạt trên 17.050 (trường mẫu) / 17.200
  (file của trường), mục 3.
- **Đo được (mục 7):** nếu xếp riêng từng lớp tới tối ưu thì chi phí chỉ còn 8.400 / 8.300. Toàn bộ phần còn lại
  (8.650 / 8.900) đến từ việc các lớp dùng chung giáo viên: nhiều TV/Toán buổi chiều hơn (+3.900), tải ngày của giáo
  viên (+2.000), môn nặng tiết 7 (+1.600), mất thưởng tiết tăng cường (+1.100–1.200). Cận dưới CP-SAT của file của
  trường là 14.210, nên mọi cải tiến chỉ có thể giảm **tối đa 2.990 (17%)**, và có thể ít hơn nhiều.
- Hướng đáng thử, theo thứ tự (mục 5, đánh giá ở mục 7):
  1. **Tính cận dưới tốt hơn trước.** Cận theo lớp đã làm nhưng quá yếu; bước tiếp là quy hoạch tuyến tính của mô
     hình "mẫu ngày", để biết còn đáng tìm thuật toán mới không.
  2. **Mô hình theo mẫu ngày + sinh cột** (column generation): đổi cách mô hình hoá chứ không chỉ đổi cách tìm; vừa
     cho cận dưới mạnh vừa cho một kiểu xếp lại mới.
  3. **Tìm kiếm cục bộ nhanh** (mô phỏng luyện kim / Late Acceptance với nước đi đổi chỗ, chuỗi Kempe) chạy sau LNS,
     để đi nhiều bước rẻ trên các vùng phẳng.
- **Nên làm ngay** (mục 7): bỏ lần xếp lại y hệt (cùng TKB, nhanh hơn), và in chi phí theo thành phần kèm phần bắt
  buộc để nhà trường thấy chất lượng thật của TKB.
- Không nên đầu tư: giải thuật di truyền, bầy đàn (PSO), siêu heuristic, học máy, MIP thuần bằng bộ giải miễn phí,
  thay CP-SAT bằng MaxSAT.

---

## 2. Bài toán của trường trong bức tranh chung

- **Khảo sát:** Pillay (2014) tổng hợp nghiên cứu xếp TKB trường phổ thông; Ceschia, Di Gaspero & Schaerf (2023)
  tổng hợp các bài toán chuẩn, bộ dữ liệu và kết quả tốt nhất (cận trên, cận dưới) của cả lĩnh vực.
- **Chuẩn XHSTT / ITC 2011:** định dạng XML chung cho TKB phổ thông của nhiều nước. Cuộc thi ITC 2011 có 17 đội; đội
  thắng (GOAL, Brazil) dùng mô phỏng luyện kim kết hợp tìm kiếm cục bộ lặp.
- **Điểm riêng của trường mình:** nhiều luật trong một ngày của một lớp (môn liền nhau trong buổi, TV đi theo cặp,
  tối đa 2 tiết mỗi nhóm môn mỗi buổi, Toán 1 tiết/ngày, tiết 1 do GVCN dạy, HĐTN cố định). Ràng buộc giữa các lớp
  chỉ đến từ giáo viên dạy nhiều lớp (bộ môn, tiếng Anh, thể dục...). Cấu trúc này hợp với các cách tách theo
  lớp-ngày (mục 4.1, 5.2).

---

## 3. Phần chi phí bắt buộc

Hai bộ dữ liệu đều có 6 lớp khối 1, mỗi lớp 14 tiết Tiếng Việt/tuần, 5 buổi sáng (thứ 6 chỉ có buổi sáng) và 4 buổi
chiều. Với luật hiện tại, mỗi lớp khối 1 bắt buộc phải có:

| Nguyên nhân | Chi phí tối thiểu mỗi lớp |
|---|---:|
| Mỗi buổi tối đa 2 tiết TV → buổi sáng chứa tối đa 10 tiết TV → **ít nhất 4 tiết TV buổi chiều** × 300 (`morning_core`) | 1.200 |
| TV học theo cặp nên mỗi ngày có 0, 2 hoặc 4 tiết; thứ 6 tối đa 2 → phải có **ít nhất 2 ngày 4 tiết**, vượt ⌈14/5⌉ = 3 một tiết × 120 (`core_spread`) | 240 |
| **Cộng** | **1.440** |

6 lớp × 1.440 = **8.640** điểm phạt, tức khoảng 50% chi phí hiện tại của cả hai bộ dữ liệu. Không thuật toán nào giảm
được phần này nếu giữ nguyên luật và trọng số. Đây mới là phần dễ thấy; mục 7.1 đo thêm phần bắt buộc khi xếp riêng
từng lớp (cận theo lớp) và phần do các lớp dùng chung giáo viên.

---

## 4. Các họ thuật toán

### 4.1. Phương pháp chính xác (cho nghiệm tối ưu hoặc cận dưới)

| Phương pháp | Trong tài liệu | Với dự án này |
|---|---|---|
| **MIP** (quy hoạch nguyên) | Kristiansen, Sørensen & Stidsen (2015): phương pháp chính xác đầu tiên cho mọi bài XHSTT, dùng bộ giải MIP thương mại; tìm được tối ưu mới và cận dưới mới. Fonseca, Santos, Carrano & Stidsen (2017): thêm lát cắt, tiền xử lý, tái mô hình, nhiều cận mới | Tốt để lấy **cận dưới**. Bộ giải MIP miễn phí (HiGHS, SCIP) thường chậm hơn nhiều so với Gurobi/CPLEX; khó thay CP-SAT để tìm nghiệm |
| **Sinh cột / mô hình theo mẫu** | Papoutsis, Valouxis & Housos (2003): sinh cột cho trường trung học Hy Lạp, nghiệm tốt, không có tiết trống cho GV. Santos, Uchoa, Ochi & Maculan (2012): sinh cột + lát cắt cho **class-teacher timetabling**, cận dưới rất tốt, chứng minh tối ưu 3 bài mở. Saviniec, Santos, Costa & dos Santos (2020): hai mô hình theo mẫu, sinh cột kết hợp đội metaheuristic song song, tốt hơn các phương pháp trước | **Rất hợp** vì luật của trường chủ yếu nằm trong một lớp-ngày (mục 5.2) |
| **MaxSAT** | Demirović & Musliu (2017): mô hình MaxSAT có trọng số, dùng trong LNS; tốt hơn MaxSAT thuần khi thời gian có hạn | Tương tự LNS hiện tại với bộ giải khác; CP-SAT đã có sẵn các kỹ thuật SAT tương tự. Ít lợi |
| **CP** | Demirović & Stuckey (2018): mô hình CP kiểu lập lịch; cải thiện lớn nhờ "phase saving" theo nghiệm tốt nhất và **khởi động nóng** từ nghiệm heuristic | Chương trình đã làm đúng như vậy (gợi ý nghiệm cho CP-SAT trong mỗi vùng) |

### 4.2. Matheuristic (kết hợp bộ giải chính xác và tìm kiếm cục bộ)

| Phương pháp | Trong tài liệu | Với dự án này |
|---|---|---|
| **Fix-and-optimize** | Dorneles, de Araújo & Buriol (2014): cố định phần lớn, giải lại một phần bằng MIP, duyệt theo lớp, giáo viên, ngày | **Chính là cách hiện tại** (`tkb/lns.py`) |
| **VNS + vùng giải bằng MIP** | Fonseca, Santos & Carrano (2016): VNS có thêm các vùng giải bằng quy hoạch nguyên, tốt hơn VNS thuần rất nhiều | Đã có tương đương; ALNS, vùng mới, nhiễu mạnh đã thử (xem `Nghien_Cuu_ALNS.md`) |
| **ALNS** | Sørensen & Stidsen (2012): TKB trung học Đan Mạch, 300 bộ dữ liệu, cách tối ưu trung bình khoảng 5% | Đã thử, không tốt hơn |

### 4.3. Tìm kiếm cục bộ (metaheuristic một nghiệm)

| Phương pháp | Trong tài liệu | Với dự án này |
|---|---|---|
| **Mô phỏng luyện kim + tìm kiếm cục bộ lặp** | GOAL (Fonseca et al., 2016): thắng ITC 2011, nghiệm tốt nhất cho gần như mọi bài | Nước đi rẻ, hàng triệu bước: hợp để đi trên **vùng phẳng** mà LNS không vượt qua (mục 5.3) |
| **VNS** (tìm kiếm lân cận biến đổi) | Fonseca & Santos (2014): nhiều biến thể; tốt nhất là Skewed VNS (nhận nghiệm mới theo cả chi phí lẫn khoảng cách tới nghiệm tốt nhất) | Như trên |
| **Late Acceptance Hill Climbing** | Burke & Bykov (2017), ban đầu làm cho xếp lịch thi; Fonseca, Santos & Carrano (2016) dùng cho XHSTT | Đơn giản, gần như không có tham số; dễ giữ tái lập |
| **Chuỗi Kempe** (Kempe chain) | Nước đi đổi chỗ một chuỗi tiết giữa hai ô giờ mà vẫn không trùng giờ; hay dùng trong SA cho xếp lịch | Hợp với ràng buộc giáo viên không dạy hai lớp cùng lúc |

### 4.4. Tiến hoá và các hướng khác

Giải thuật di truyền, bầy đàn (PSO), siêu heuristic, thuật toán lượng tử, học máy: có nhiều bài báo, nhưng trên các
bộ dữ liệu chuẩn XHSTT, kết quả tốt nhất đến từ tìm kiếm cục bộ và matheuristic (mục 4.2, 4.3). Với một trường
khoảng 30 lớp, các hướng này khó thắng CP-SAT + LNS và khó giữ tái lập. **Không nên đầu tư.**

### 4.5. Phân rã hai giai đoạn

Sørensen & Dahms (2014) tách mô hình quy hoạch nguyên của TKB trung học Đan Mạch thành hai bài nhỏ hơn giải lần lượt,
giai đoạn 1 quyết định trước (không quay lại). Với trường mình có thể tách **ngày trước, tiết sau**: giai đoạn 1 chọn
mỗi lớp học môn gì vào ngày nào (rải đều, tải ngày của giáo viên); giai đoạn 2 xếp thứ tự trong ngày (buổi sáng cho
TV/Toán, môn liền nhau, cặp, tiết 1 GVCN, giáo viên không trùng giờ). Nhanh hơn nhưng mất tính tối ưu chung; hợp
để tạo điểm khởi đầu khác hơn là để cải thiện nghiệm hiện có.

---

## 5. Đề xuất theo thứ tự

### 5.1. Đo khoảng cách thật trước (công sức nhỏ, nên làm đầu tiên; đã làm, xem mục 7.1)

- **Cận theo lớp:** bỏ ràng buộc "giáo viên không dạy hai lớp cùng lúc", mỗi lớp giải riêng bằng CP-SAT cho tối ưu
  (bài nhỏ, vài giây). Tổng các tối ưu theo lớp là một cận dưới hợp lệ, vì các thành phần theo giáo viên (tải ngày,
  tiết trống) đều không âm. Cận này có thể mạnh hơn 14.210 vì mỗi bài nhỏ được giải tới tối ưu.
- Nếu cận gần 17.000 thì nghiệm hiện tại gần tối ưu: **dừng tìm thuật toán mới**, chỉ nên tối ưu thời gian chạy (bỏ
  lần xếp lại y hệt).

### 5.2. Mô hình theo mẫu ngày + sinh cột (công sức lớn, tiềm năng cao nhất)

- **Mẫu ngày** của một lớp: dãy môn cho các tiết trong ngày thỏa mọi luật học sinh (liền nhau trong buổi, cặp TV,
  ≤ 2 tiết mỗi nhóm môn mỗi buổi, Toán ≤ 1, tiết 1 GVCN, HĐTN) kèm chi phí trong ngày (buổi sáng TV/Toán, môn nặng
  tiết 7...). Luật trong ngày trở thành ngầm định trong mẫu.
- **Bài chính:** mỗi lớp-ngày chọn một mẫu; ràng buộc giữa các ngày là số tiết mỗi môn trong tuần, rải đều, GVCN dạy
  trước; ràng buộc giữa các lớp là giáo viên không trùng giờ, tải ngày.
- Nới lỏng tuyến tính cho **cận dưới mạnh** (như Santos et al. 2012 cho class-teacher). Bài chính giải nguyên bằng
  CP-SAT cho **một kiểu xếp lại mới**: xếp lại nhiều lớp-ngày một lúc bằng cách chọn lại mẫu.
- Rủi ro: số mẫu mỗi lớp-ngày có thể lớn, cần sinh dần (pricing) hoặc liệt kê có cắt tỉa; công sức vài tuần.

### 5.3. Tìm kiếm cục bộ nhanh sau LNS (công sức vừa, tiềm năng vừa)

- Mô phỏng luyện kim hoặc Late Acceptance trên các nước đi rẻ: đổi chỗ hai tiết của một lớp, chuỗi Kempe giữa hai ô
  giờ. Tính chênh lệch chi phí và kiểm tra luật **tăng dần** (chỉ phần bị ảnh hưởng), để đạt hàng nghìn bước mỗi giây
  kể cả bằng Python thuần (mỗi lần xếp lại vùng của LNS mất từ vài phần trăm giây đến vài chục giây).
- Hợp với phát hiện "vùng phẳng rộng": nhiều bước ngang giá rẻ có thể dẫn tới chỗ giảm mà LNS không thấy. Thử
  nghiệm nhiễu mạnh (B) đã giảm 17.200 → 17.160 theo cách tương tự nhưng mỗi bước rất đắt.
- Giữ tái lập: bộ sinh số splitmix64 và số bước cố định (không dùng giây thực).
- Rủi ro: phải viết lại việc kiểm tra các luật cứng theo kiểu tăng dần (có sẵn `checker.check` để kiểm lại cuối).

### 5.4. Không nên đầu tư

- Giải thuật di truyền, PSO, siêu heuristic, lượng tử, học máy (mục 4.4).
- MIP thuần bằng bộ giải miễn phí để tìm nghiệm; chỉ nên dùng MIP / nới lỏng tuyến tính để lấy cận dưới.
- Thay CP-SAT bằng MaxSAT: cùng bản chất với LNS hiện tại.

---

## 7. Đánh giá các đề xuất bằng số liệu

### 7.1. Chi phí nằm ở đâu

Đo bằng `tools/thu_alns.py` (Linux, hằng số mặc định của `main.py`, 1200):
- `--can-duoi <mau|truong>`: **cận theo lớp** (mục 5.1). Mỗi lớp một bài riêng: chỉ các môn của lớp, phân công giữ
  nguyên, bỏ ràng buộc giáo viên không dạy hai lớp cùng lúc, bỏ phần tiết trống của giáo viên, tải ngày tính riêng
  trong lớp. Cả 29 lớp đều được CP-SAT chứng minh tối ưu. Tổng các tối ưu là cận dưới hợp lệ: các phần bị bỏ không
  âm, và phạt tải ngày là hàm lồi bằng 0 tại 0 nên tổng theo lớp không vượt phạt thật.
- `--thanh-phan <file kết quả>`: tách chi phí của nghiệm cuối (LNS hiện tại, cùng TKB với cách cũ) theo thành phần,
  đúng công thức mục tiêu của mô hình. Tổng khớp đúng chi phí xếp giờ (17.050 / 17.200).

| Thành phần | Trường mẫu: nghiệm | Cận theo lớp | Chênh | File của trường: nghiệm | Cận theo lớp | Chênh |
|---|---:|---:|---:|---:|---:|---:|
| TV/Toán buổi chiều | 11.100 | 7.200 | +3.900 | 11.100 | 7.200 | +3.900 |
| Tải ngày giáo viên | 3.200 | 1.200 | +2.000 | 3.200 | 1.200 | +2.000 |
| Môn nặng tiết 7 | 1.600 | 0 | +1.600 | 1.600 | 0 | +1.600 |
| Thưởng tiết tăng cường liền sau | −700 | −1.800 | +1.100 | −700 | −1.900 | +1.200 |
| Rải đều | 1.840 | 1.680 | +160 | 2.000 | 1.680 | +320 |
| Toán tăng cường buổi sáng | 10 | 120 | −110 | 0 | 120 | −120 |
| HĐTN xa cuối buổi, tiết trống GV | 0 | 0 | 0 | 0 | 0 | 0 |
| **Cộng** | **17.050** | **8.400** | **+8.650** | **17.200** | **8.300** | **+8.900** |

- Nếu mỗi lớp được xếp riêng thì chi phí chỉ còn 8.300–8.400; **toàn bộ phần chênh đến từ việc các lớp dùng chung
  giáo viên**. Riêng TV/Toán, nghiệm có 37 tiết buổi chiều so với 24 tiết bắt buộc. Giải thích có khả năng nhất
  (chưa đo riêng): giáo viên dạy nhiều lớp (tiếng Anh, thể dục, tin học, bộ môn...) cũng cần tiết buổi sáng, nên
  một số lớp phải đẩy TV/Toán sang buổi chiều.
- Cận theo lớp (8.300) **yếu hơn nhiều** so với cận CP-SAT toàn cục (14.210, file của trường, lần chạy 110 phút ở spec
  §9). Vậy ít nhất 5.910 trong 8.900 điểm chênh là không tránh được, và mọi cải tiến chỉ có thể giảm **tối đa 2.990
  (17%)** chi phí của file của trường. Muốn biết con số thật cần một cận có tính tới giáo viên dùng chung (mục 5.2).

### 7.2. Đánh giá từng đề xuất

| Đề xuất | Lợi ích (đo được hoặc ước lượng) | Công sức | Rủi ro | Đánh giá |
|---|---|---|---|---|
| Bỏ lần xếp lại y hệt | **Đã đo:** cùng TKB (so từng lần giải); file của trường xong ở 1001 thay vì 1204 đơn vị (−17%, khoảng 1,5–2 phút); trường mẫu gần như không đổi | Khoảng 10 dòng trong `lns.improve` + 1 test | Rất thấp. Mã kết quả Linux không đổi; Windows cần CI xác nhận | **Làm ngay** |
| In chi phí theo thành phần và phần bắt buộc | Không đổi TKB. Nhà trường thấy 17.200 gồm những gì, phần nào không tránh được (bảng mục 7.1) | Khoảng 30 dòng (có sẵn hàm tách thành phần) | Không (chỉ in thêm ra màn hình hoặc file thống kê) | **Nên làm** |
| Nhiễu mạnh cho chế độ không giới hạn | **Đã đo:** −40 (−0,23%) trên file của trường khi gấp đôi thời gian; 0 trên trường mẫu; mỗi bộ một lần chạy | Khoảng 60 dòng | Chế độ không giới hạn mất "tự dừng"; lợi ích chưa chắc | Tùy chọn, cần đo thêm nhiều hạt giống |
| Cận theo lớp | **Đã làm:** 8.400 / 8.300, yếu hơn cận CP-SAT | Xong | Không | Giữ làm công cụ phân tích; không đủ để biết còn giảm được bao nhiêu |
| Mô hình mẫu ngày + sinh cột | **Ước lượng:** tối đa 2.990 (17%) trên file của trường. Riêng phần nới lỏng tuyến tính (cận dưới) sẽ cho biết con số thật | Phần cận: khoảng 1 tuần. Cả bộ giải: vài tuần | Cao | Chỉ làm nếu nhà trường cần TKB tốt hơn nữa; làm phần cận trước |
| Tìm kiếm cục bộ nhanh sau LNS | **Ước lượng:** nhỏ, cỡ vài chục đến vài trăm điểm (hướng B chỉ được −40); tối đa 2.990 | 1–2 tuần | Vừa: phải viết kiểm tra luật cứng kiểu tăng dần | Sau khi có cận tốt hơn |
| Phân công có xét xếp giờ | **Giả thuyết, chưa đo:** các khoản chênh lớn nhất (TV/Toán chiều, tải ngày) gắn với giáo viên dùng chung, nên có thể phụ thuộc ai dạy lớp nào | Lớn | Cao: phân công hiện tại là quy tắc nhà trường đã chốt (spec §8.1), đổi nó là đổi bảng thống kê | Hỏi nhà trường trước |
| Giải thuật di truyền, PSO, học máy, MaxSAT, MIP thuần | Không có lý do để kỳ vọng tốt hơn (mục 4) | – | – | Không làm |

### 7.3. Kết luận

- Kiến trúc hiện tại (phân công bằng Python thuần, rồi CP-SAT + LNS với phân công cố định) **phù hợp** với bài toán.
  Phần chi phí còn có thể giảm nằm hoàn toàn ở chỗ các lớp dùng chung giáo viên, và tối đa chỉ 17% (file của
  trường), có thể ít hơn nhiều.
- Hai việc nên làm ngay đều **không đổi TKB**: bỏ lần xếp lại y hệt (nhanh hơn) và in chi phí theo thành phần (minh
  bạch hơn).
- Mọi thay đổi thuật toán lớn nên chờ một cận dưới có tính tới giáo viên dùng chung (phần nới lỏng của mô hình mẫu
  ngày). Nếu cận đó gần 17.000 thì dừng.

## 8. Tài liệu tham khảo

- N. Pillay (2014). *A survey of school timetabling research.* Annals of Operations Research 218, 261–293.
  <https://link.springer.com/article/10.1007/s10479-013-1321-8>
- S. Ceschia, L. Di Gaspero, A. Schaerf (2023). *Educational timetabling: Problems, benchmarks, and state-of-the-art
  results.* European Journal of Operational Research 308(1), 1–18.
  <https://www.sciencedirect.com/science/article/pii/S0377221722005641>
- ITC 2011, High School Timetabling Project (Đại học Twente). <https://www.utwente.nl/en/eemcs/dmmp/hstt/itc2011/>
- G. H. G. Fonseca, H. G. Santos, T. A. M. Toffolo, S. S. Brito, M. J. F. Souza (2016). *GOAL solver: a hybrid local
  search based solver for high school timetabling.* Annals of Operations Research.
  <https://link.springer.com/article/10.1007/s10479-014-1685-4>
- G. H. G. Fonseca, H. G. Santos (2014). *Variable Neighborhood Search based algorithms for high school timetabling.*
  Computers & Operations Research. <https://www.sciencedirect.com/science/article/abs/pii/S0305054813003328>
- G. H. G. Fonseca, H. G. Santos, E. G. Carrano (2016). *Integrating matheuristics and metaheuristics for
  timetabling.* Computers & Operations Research 74, 108–117.
  <https://www.sciencedirect.com/science/article/abs/pii/S0305054816300879>
- G. H. G. Fonseca, H. G. Santos, E. G. Carrano (2016). *Late acceptance hill-climbing for high school timetabling.*
  Journal of Scheduling 19, 453–465. <https://link.springer.com/article/10.1007/s10951-015-0458-5>
- G. H. G. Fonseca, H. G. Santos, E. G. Carrano, T. J. R. Stidsen (2017). *Integer programming techniques for
  educational timetabling.* European Journal of Operational Research 262(1), 28–39.
  <https://www.sciencedirect.com/science/article/abs/pii/S0377221717302242>
- S. Kristiansen, M. Sørensen, T. R. Stidsen (2015). *Integer programming for the generalized high school
  timetabling problem.* Journal of Scheduling 18(4), 377–392. <https://link.springer.com/article/10.1007/s10951-014-0405-x>
- N. Papoutsis, C. Valouxis, E. Housos (2003). *A column generation approach for the timetabling problem of Greek
  high schools.* Journal of the Operational Research Society 54(3), 230–238.
  <https://link.springer.com/article/10.1057/palgrave.jors.2601495>
- H. G. Santos, E. Uchoa, L. S. Ochi, N. Maculan (2012). *Strong bounds with cut and column generation for
  class-teacher timetabling.* Annals of Operations Research 194(1), 399–412.
  <https://link.springer.com/article/10.1007/s10479-010-0709-y>
- L. Saviniec, M. O. Santos, A. M. Costa, L. M. R. dos Santos (2020). *Pattern-based models and a cooperative
  parallel metaheuristic for high school timetabling problems.* European Journal of Operational Research 280(3),
  1064–1081. <https://www.sciencedirect.com/science/article/abs/pii/S0377221719306538>
- E. Demirović, N. Musliu (2017). *MaxSAT-based large neighborhood search for high school timetabling.* Computers &
  Operations Research 78, 172–180. <https://www.sciencedirect.com/science/article/abs/pii/S0305054816301927>
- E. Demirović, P. J. Stuckey (2018). *Constraint programming for high school timetabling: a scheduling-based model
  with hot starts.* CPAIOR 2018, LNCS, 135–152. <https://link.springer.com/chapter/10.1007/978-3-319-93031-2_10>
- Á. P. Dorneles, O. C. B. de Araújo, L. S. Buriol (2014). *A fix-and-optimize heuristic for the high school
  timetabling problem.* Computers & Operations Research 52, 29–38.
  <https://www.sciencedirect.com/science/article/pii/S0305054814001816>
- M. Sørensen, T. R. Stidsen (2012). *High School Timetabling: Modeling and solving a large number of cases in
  Denmark.* PATAT 2012. <https://orbit.dtu.dk/en/publications/high-school-timetabling-modeling-and-solving-a-large-number-of-ca/>
- M. Sørensen, F. Dahms (2014). *A two-stage decomposition of high school timetabling applied to cases in
  Denmark.* Computers & Operations Research. <https://www.sciencedirect.com/science/article/abs/pii/S0305054813002451>
- E. K. Burke, Y. Bykov (2017). *The late acceptance hill-climbing heuristic.* European Journal of Operational
  Research 258(1), 70–78. <https://www.sciencedirect.com/science/article/abs/pii/S0377221716305495>
