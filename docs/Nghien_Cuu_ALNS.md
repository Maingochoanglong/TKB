# Nghiên cứu: ALNS cho bước xếp giờ

Tài liệu nghiên cứu trên nhánh `claude/cp-sat-anlp-development-6uqx3j`. Chưa đổi code chạy thật: `tkb/lns.py`,
mã kết quả và TKB giữ nguyên. Mọi số liệu dưới đây đo trên Linux với các hằng số mặc định của `main.py` (bù giờ,
`THOI_GIAN_TOI_DA = 1200`, 8 luồng, chế độ tái lập). Với file của trường chỉ ghi chi phí và loại vùng, không ghi tên.

## 1. Tóm tắt

- **ALNS** (Adaptive Large Neighborhood Search) là LNS có nhiều cách "phá" một phần nghiệm và **học trong lúc chạy**
  nên dùng cách nào (trọng số roulette), thường kèm mô phỏng luyện kim để thoát tối ưu cục bộ (mục 2).
- `tkb/lns.py` đã là LNS kiểu fix-and-optimize với CP-SAT làm bước sửa. Nó chỉ thiếu phần "A": thứ tự vùng cố định,
  giới hạn cố định, chỉ nhận khi giảm (mục 3).
- **Đo LNS hiện tại** (1200, cả trường mẫu và file của trường): vòng 1 làm 98–99% mức giảm, sau đó chỉ vùng lớn còn
  giảm thêm được 0,3–1,8%. Trên file của trường, **17% ngân sách** xếp lại vùng bị dùng để giải lại đúng bài toán
  đã giải, chắc chắn không giảm (mục 4).
- **Ba nguyên mẫu ALNS không tốt hơn** (mục 5): ALNS thuần kém 6%; hai bản giữ vòng 1 rồi mới thích nghi (`v2`,
  `v3` có luyện kim) bằng LNS hiện tại trên file của trường, kém 1,2–1,8% trên trường mẫu. Lý do: mỗi lần sửa là
  một lần CP-SAT nên chỉ có 100–200 lần lặp, không đủ để học; thứ tự "rẻ trước, xấu trước" hiện có đã tốt; và TKB có
  nhiều vùng phẳng nên luyện kim không có tác dụng.
- **Đề xuất** (mục 7): giữ LNS theo vòng; lấy một ý của ALNS/tabu là **bỏ lần xếp lại y hệt**. Ý này ra đúng cùng
  TKB, riêng file của trường xong sớm hơn 17% (1001 thay vì 1204 đơn vị). Muốn TKB tốt hơn thì cần loại vùng mới
  hoặc nhiễu mạnh hơn, không cần cách chọn vùng mới.

---

## 2. ALNS là gì

### 2.1. LNS: phá một phần rồi xếp lại

**Large Neighborhood Search** (Shaw, 1998): từ một nghiệm đang có, **phá** (bỏ ra) một phần khá lớn các quyết định
có liên quan với nhau, giữ nguyên phần còn lại, rồi **sửa** (xếp lại) phần bị phá bằng một bộ giải. Shaw dùng lập
trình ràng buộc để xếp lại, đúng như cách `tkb/lns.py` dùng CP-SAT. Vùng càng lớn thì càng có thể thoát khỏi tối ưu
cục bộ nhưng càng khó giải.

### 2.2. ALNS: chọn cách phá theo kết quả đã thấy

**Adaptive LNS** (Ropke & Pisinger, 2006) có nhiều cách phá (toán tử phá) và nhiều cách sửa, và **học trong lúc chạy**
nên dùng cách nào:

1. **Chọn toán tử bằng bánh xe roulette:** toán tử `i` có trọng số `wᵢ`, được chọn với xác suất `wᵢ / Σw`.
2. **Chấm điểm mỗi lần dùng:** được điểm cao nếu cho nghiệm tốt nhất mới, điểm vừa nếu tốt hơn nghiệm hiện tại,
   điểm thấp nếu chỉ được chấp nhận, 0 nếu bị bỏ.
3. **Cập nhật trọng số theo đoạn** (vài chục đến vài trăm lần lặp): `wᵢ ← (1 − r)·wᵢ + r·(điểm trung bình của i
   trong đoạn)`, `r` là hệ số phản ứng (0: không học, 1: chỉ nhớ đoạn vừa rồi).
4. **Tiêu chí chấp nhận:** thường là mô phỏng luyện kim (đôi khi nhận nghiệm kém hơn để đi xa khỏi tối ưu cục bộ),
   luôn giữ riêng nghiệm tốt nhất.
5. **Ngẫu nhiên hoá** việc phá (chọn ngẫu nhiên trong các phần "liên quan") để không lặp lại cùng một vùng.

ALNS cần **nhiều lần lặp** (bài báo gốc chạy hàng chục nghìn lần) để trọng số có ý nghĩa, vì mỗi lần sửa ở đó rất
rẻ (chèn tham lam). Khi mỗi lần sửa là một lần giải CP-SAT tốn vài đến vài chục giây, số lần lặp chỉ còn vài trăm.

### 2.3. Trong bài toán xếp thời khóa biểu

- **Sørensen & Stidsen (PATAT 2012):** ALNS cho TKB trung học Đan Mạch, thử trên 300 bộ dữ liệu thật, tốt hơn
  Gurobi và heuristic đang dùng, trung bình cách tối ưu khoảng 5%; được đưa vào sản phẩm Lectio.
- **Kiefer, Hartl & Schnell (2017):** ALNS cho xếp lịch học phần đại học (curriculum-based course timetabling).
- **Dorneles, de Araújo & Buriol (2014): fix-and-optimize** cho TKB phổ thông: cố định phần lớn biến, giải lại
  một phần bằng MIP, duyệt lần lượt các cách phân rã **theo lớp, theo giáo viên, theo ngày** (VND). Đây là họ gần
  nhất với `tkb/lns.py` hiện tại.

### 2.4. CP-SAT tự chạy LNS bên trong

Trong bước khởi đầu, CP-SAT đã chạy các luồng LNS riêng với các bộ sinh vùng tổng quát và tự điều chỉnh độ khó
(kích thước vùng). Các bộ sinh này không biết cấu trúc "lớp, ngày, giáo viên dùng chung" của bài toán; `tkb/lns.py`
bổ sung đúng phần đó. Tài liệu hướng dẫn CP-SAT cũng lưu ý: khi số lần lặp ít, cách chọn chiến lược phức tạp
không có đủ dữ liệu để học.

---

## 3. `tkb/lns.py` nhìn dưới góc ALNS

| Thành phần ALNS | `tkb/lns.py` hiện tại |
|---|---|
| Toán tử phá | 5 loại vùng: lớp, điểm nóng, GV dùng chung, khối, cặp ngày |
| Toán tử sửa | CP-SAT trên toàn mô hình, cố định mọi biến ngoài vùng, xuất phát từ nghiệm đang có |
| Chọn toán tử | **Cố định**: mỗi vòng quét hết mọi vùng, theo thứ tự loại rẻ → đắt, trong loại thì vùng xấu (QA) trước |
| Thích nghi | Không có. Giới hạn thời gian mỗi loại vùng cố định (`LNS_REGION_LIMITS`) |
| Chấp nhận | Chỉ nhận khi chi phí giảm |
| Ngẫu nhiên | Không có (thứ tự tất định) |
| Dừng | Hết ngân sách; vòng giảm < 0,3%; 10 vòng; Ctrl+C |

Nói cách khác, cách hiện tại là **LNS/fix-and-optimize có hướng dẫn (QA)**, thiếu phần "A" (thích nghi).

---

## 4. Số liệu đo LNS hiện tại

Đo bằng cách bọc `_Search.region` để ghi từng lần xếp lại (loại vùng, ngân sách dùng, chi phí trước/sau, CP-SAT có
chứng minh xong vùng không). Kết quả cuối trùng với số trong spec (§9, §13): trường mẫu **17.050**, file của trường
**17.200**, nên cách đo không làm đổi đường đi của thuật toán.

### 4.1. Theo vòng

| | Khởi đầu | Vòng 1 | Vòng 2 | Vòng 3 | Vòng 4 |
|---|---:|---:|---:|---:|---:|
| Trường mẫu | 30.510 | 17.360 (−13.150) | 17.260 (−100) | 17.050 (−210) | 17.050 (0, hết ngân sách giữa vòng) |
| File của trường | 27.760 | 17.260 (−10.500) | 17.200 (−60) | 17.200 (0, hết ngân sách giữa vòng) | |

**Vòng 1 làm gần hết việc** (98–99% mức giảm). Sau vòng 1 chỉ còn giảm được 0,3–1,8%, và chỉ nhờ vùng lớn: trường mẫu
nhờ **cặp ngày** (vòng 2: 2 lần giảm, vòng 3: 4 lần), file của trường nhờ một vùng **GV dùng chung** (vòng 2).

### 4.2. Theo loại vùng (cả lần chạy)

Ngân sách = đơn vị như `THOI_GIAN_TOI_DA` (≈ giây). "Chứng minh xong": CP-SAT chứng minh không có cách xếp tốt hơn
trong vùng; còn lại là hết giờ giữa chừng.

| Loại vùng | Lần xếp lại | Lần giảm | Tổng giảm | Ngân sách | Giảm / đơn vị | Chứng minh xong |
|---|---:|---:|---:|---:|---:|---:|
| **Trường mẫu** | | | | | | |
| lớp | 116 | 19 | 4.280 | 23 (2%) | 185 | 116/116 |
| điểm nóng | 20 | 4 | 1.200 | 23 (2%) | 52 | 20/20 |
| GV dùng chung | 23 | 7 | 5.460 | 273 (25%) | 20 | 13/23 |
| khối | 15 | 5 | 760 | 166 (15%) | 4,6 | 9/15 |
| cặp ngày | 30 | 15 | 1.760 | 594 (55%) | 3,0 | 17/30 |
| **File của trường** | | | | | | |
| lớp | 87 | 15 | 3.300 | 14 (1%) | 235 | 87/87 |
| điểm nóng | 15 | 2 | 1.150 | 7 (1%) | 175 | 15/15 |
| GV dùng chung | 24 | 9 | 4.610 | 335 (31%) | 14 | 12/24 |
| khối | 15 | 2 | 350 | 230 (21%) | 1,5 | 9/15 |
| cặp ngày | 25 | 6 | 1.150 | 496 (46%) | 2,3 | 16/25 |

Nhận xét:
- **Lớp, điểm nóng:** rất rẻ (trung bình 0,2–1 đơn vị mỗi lần), luôn chứng minh xong, chỉ có ích ở vòng 1.
- **GV dùng chung:** tổng giảm lớn nhất; ở vòng 1 gần như lần nào cũng giảm. Một nửa số lần hết giờ.
- **Cặp ngày:** tốn một nửa ngân sách, hiệu quả thấp nhất tính theo đơn vị, nhưng là nguồn giảm chính sau vòng 1
  (trường mẫu).
- **Khối:** kém hiệu quả nhất trên cả hai bộ dữ liệu.

### 4.3. Giải lại y hệt

CP-SAT ở chế độ tái lập là tất định: đã thử giải cùng một vùng, cùng nghiệm đầu vào, cùng giới hạn 3 lần liền trong
một tiến trình, cả 3 lần ra đúng cùng chi phí và cùng lượng tính toán. Vì vậy giải lại một vùng khi nghiệm đầu vào
chưa đổi **chắc chắn không giảm được gì**.

| | Lần giải lại y hệt | Ngân sách phí | Loại vùng |
|---|---:|---:|---|
| Trường mẫu | 1 | 1 đơn vị (0%) | cặp ngày |
| File của trường | 11 | 184 đơn vị (**17%**) | cặp ngày 100, khối 74, GV dùng chung 11 |

Với file của trường, vòng 2 chỉ giảm một lần (ở giữa vòng), nên vòng 3 giải lại y hệt mọi vùng đứng sau vùng đó ở
vòng 2, rồi hết ngân sách.

## 5. Nguyên mẫu ALNS

Các biến thể nằm trong `tools/thu_alns.py` (không đổi `tkb/`). Chạy lại: `python tools/thu_alns.py <mau|truong>
<biến thể> [ngân sách]`, rồi `python tools/thu_alns.py --tom-tat out/thu_alns/*.json` để in bảng theo loại vùng.
Mọi biến thể dùng chung bước khởi đầu, cách xếp lại một vùng, QA và danh sách vùng của `tkb/lns.py`, cùng ngân sách
1200.

| Biến thể | Cách làm |
|---|---|
| `lns` | LNS hiện tại (`lns.improve`) |
| `bo_trung` | LNS hiện tại, **bỏ lần xếp lại y hệt**: cùng vùng, cùng giới hạn, cùng nghiệm đầu vào thì không giải lại (mục 4.3) |
| `v1` | ALNS "sách giáo khoa" ngay sau khởi đầu: roulette chọn loại vùng, trọng số = hiệu quả (giảm / ngân sách) của 8 lần gần nhất, trong loại lấy vùng xấu nhất (QA) chưa tabu; vùng không giảm thành tabu tới khi nghiệm đổi ở lớp liên quan; hết vùng thì gấp đôi giới hạn các vùng hết giờ |
| `v2` | Vòng 1 như hiện tại, rồi roulette chọn loại vùng, **vùng ngẫu nhiên** trong loại, bỏ vùng đã chứng minh tối ưu trên nghiệm hiện tại, vùng hết giờ mà không giảm thì lần sau gấp đôi giới hạn (tối đa ×4) |
| `v3` | Vòng 1 như hiện tại, rồi ALNS có **mô phỏng luyện kim**: vùng ngẫu nhiên, **buộc đổi** ít nhất một tiết trong vùng, CP-SAT tìm cách đổi tốt nhất; nhận nếu không tệ hơn, tệ hơn Δ thì nhận với xác suất e^(−Δ/T); điểm σ = 33/9/13 như Ropke & Pisinger |

### 5.1. Kết quả (chi phí xếp giờ, càng thấp càng tốt)

| Biến thể | Trường mẫu | File của trường | Ngân sách dùng (mẫu / trường) |
|---|---:|---:|---:|
| `lns` (hiện tại) | **17.050** | **17.200** | 1200 / 1204 |
| `bo_trung` | **17.050**, cùng TKB | **17.200**, cùng TKB | 1204 / **1001** |
| `v1` | 18.030 (+5,7%) | 18.240 (+6,0%) | 1199 / 1207 |
| `v2` | 17.360 (+1,8%) | 17.200 (bằng) | 1200 / 1205 |
| `v3` | 17.260 (+1,2%) | 17.200 (bằng) | 1200 / 1202 |

"Cùng TKB": danh sách các lần xếp lại của `bo_trung` trùng từng lần (vùng, chi phí, lượng tính toán) với của `lns`
sau khi bỏ các lần y hệt; trên file của trường, vòng 3 bỏ hết các lần y hệt nên không giảm, dừng vì "vòng sau cùng
không còn cải thiện đáng kể" ở 1001 thay vì hết ngân sách giữa vòng.

### 5.2. Vì sao ALNS không thắng

- **`v1` mất độ phủ.** Luôn lấy vùng xấu nhất của loại được chọn nên lặp lại đúng một vùng nhiều lần (file của
  trường: "thứ 2+4" 10 lần, "khối 1" 8 lần trong 81 lần xếp lại; trường mẫu: "thứ 2+5" 8 lần). Tabu bị xoá gần như
  sau mỗi lần giảm vì GV dùng chung (tiếng Anh, thể dục...) nối hầu hết các lớp với nhau. Chọn loại vùng ngay từ đầu
  nên cặp ngày (30 đơn vị mỗi lần) chiếm 70–77% ngân sách, trong khi LNS hiện tại quét hết 29 lớp với giá gần 0 rồi
  mới tới vùng lớn.
- **`v2`: vòng 1 đã lấy gần hết phần có thể giảm.** Phần ALNS sau đó không tìm thêm được gì trên trường mẫu (LNS
  hiện tại còn giảm 310 ở vòng 2–3 nhờ quét lần lượt đủ 10 cặp ngày trên nghiệm mới). Gấp đôi thời gian cho cùng
  một vùng hết giờ không giúp: vùng GV dùng chung khối 1 chạy ở 30 rồi 60 đơn vị vẫn không giảm.
- **`v3`: TKB có rất nhiều "vùng phẳng".** Buộc đổi một tiết gần như luôn tìm được cách xếp **cùng chi phí**
  (trường mẫu 49/55 lần, file của trường 61/62 lần), phần còn lại tốt hơn, **không lần nào tệ hơn**: luôn có hai
  tiết đổi chỗ cho nhau mà chi phí không đổi. Vì vậy tiêu chí luyện kim không bao giờ phải nhận nghiệm kém hơn và
  tìm kiếm chỉ đi loanh quanh trên vùng phẳng. Trường mẫu giảm thêm được 100 sau vòng 1, ít hơn LNS hiện tại (310).
- **Quá ít lần lặp để học.** Một lần chạy 1200 chỉ có 100–200 lần xếp lại, và sau vòng 1 chỉ còn vài chục lần tốn
  kém. ALNS gốc học trọng số qua hàng chục nghìn lần sửa rẻ. Thứ tự cố định "rẻ trước, đắt sau, xấu trước" của LNS
  hiện tại đã là điều mà trọng số thích nghi sẽ học ra.

## 6. Giữ tái lập khi có ngẫu nhiên

Nguyên mẫu vẫn tái lập (cùng dữ liệu, cùng hệ điều hành thì cùng kết quả) nhờ:
- **Bộ sinh số splitmix64 viết bằng số nguyên** (`tools/thu_alns.py`, `Rng`), hạt giống từ `Settings.seed`.
  Không dùng module `random`: cách `choice`, `shuffle`, `randrange` sinh số có thể đổi giữa các bản Python.
- **Roulette trên trọng số nguyên:** trọng số làm tròn thành số nguyên sau mỗi lần cập nhật, chọn bằng phép chia
  lấy dư.
- **Mọi quyết định chỉ dựa trên đại lượng tất định:** chi phí (số nguyên) và thời gian tất định của CP-SAT, không
  bao giờ dùng giây thực.
- **Cẩn thận với hàm số thực của thư viện C:** `math.exp` trong tiêu chí luyện kim của `v3` đi qua thư viện C của
  hệ điều hành, có thể lệch bit cuối giữa hai máy. Nếu đưa vào code thật thì nên so sánh bằng số nguyên (ví dụ
  bảng tra hoặc so `u · 2⁶⁴ < ngưỡng` với ngưỡng tính sẵn).

## 7. Đề xuất

1. **Giữ LNS theo vòng, không thay bằng ALNS.** Ba nguyên mẫu ALNS không tốt hơn trên cả hai bộ dữ liệu; bản
   thuần ALNS kém hơn 6%. Với CP-SAT làm bước sửa, mỗi lần lặp đắt nên không đủ số lần để phần "thích nghi" có ích.
2. **Lấy một ý của ALNS/tabu: nhớ vùng đã thử trên nghiệm hiện tại** (biến thể `bo_trung`). Chắc chắn không làm TKB
   kém đi, vì lần bị bỏ là lần chắc chắn không giảm:
   - Trên Linux, cả hai bộ dữ liệu ra **đúng cùng TKB**. File của trường xong ở **1001 thay vì 1204 đơn vị (−17%)**;
     trường mẫu không đổi (chỉ có 1 lần trùng).
   - Sửa khoảng 10 dòng trong `lns.improve`: tập các khoá (vùng, giới hạn, phiên bản nghiệm), phiên bản tăng mỗi
     khi nhận nghiệm mới; khoá đã có thì bỏ qua, không tốn ngân sách.
   - Mã kết quả trên Linux không đổi. Windows chạy đường đi khác nên cần xem log của `windows.yml`: nếu một vòng
     dang dở vì hết ngân sách mà nay chạy được thêm vùng và giảm thêm, TKB Windows sẽ khác (tốt hơn hoặc bằng).
     Khi đó phải cập nhật mã Windows trong README, spec §0/§9 và `CLAUDE.md`.
3. **Muốn TKB tốt hơn thì cần vùng mới, không phải cách chọn vùng mới.** File của trường còn cách cận dưới
   14.210 khoảng 17%, nhưng phần lớn là bắt buộc theo luật cứng (spec §14.4). Hướng đáng thử tiếp:
   - vùng cắt ngang các loại hiện có: các lớp của một GV dùng chung trong 2–3 ngày; một khối trong một cặp ngày;
   - nhiễu mạnh hơn khi LNS đã dừng: buộc đổi nhiều tiết một lúc, hoặc không cho đổi sang cách cùng chi phí, để
     thật sự rời vùng phẳng (`v3` cho thấy buộc đổi một tiết là quá yếu). Chỉ đáng thử ở chế độ không giới hạn thời
     gian, vì với 1200 thì vòng 1–2 đã dùng gần hết ngân sách.

## 8. Tài liệu tham khảo

- P. Shaw (1998). *Using Constraint Programming and Local Search Methods to Solve Vehicle Routing Problems.* CP-98,
  LNCS 1520. <https://link.springer.com/chapter/10.1007/3-540-49481-2_30>
- S. Ropke, D. Pisinger (2006). *An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem
  with Time Windows.* Transportation Science 40(4), 455–472. <https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135>
- D. Pisinger, S. Ropke (2019). *Large Neighborhood Search.* Handbook of Metaheuristics, 3rd ed.
  <https://link.springer.com/chapter/10.1007/978-3-319-91086-4_4>
- M. Sørensen, T. R. Stidsen (2012). *High School Timetabling: Modeling and solving a large number of cases in
  Denmark.* PATAT 2012. <https://orbit.dtu.dk/en/publications/high-school-timetabling-modeling-and-solving-a-large-number-of-ca/>
- A. Kiefer, R. F. Hartl, A. Schnell (2017). *Adaptive large neighborhood search for the curriculum-based course
  timetabling problem.* Annals of Operations Research 252, 255–282. <https://link.springer.com/article/10.1007/s10479-016-2151-2>
- Á. P. Dorneles, O. C. B. de Araújo, L. S. Buriol (2014). *A fix-and-optimize heuristic for the high school
  timetabling problem.* Computers & Operations Research 52, 29–38.
  <https://www.sciencedirect.com/science/article/pii/S0305054814001816>
- D. Krupke. *The CP-SAT Primer*, chương Large Neighborhood Search. <https://d-krupke.github.io/cpsat-primer/09_lns.html>
