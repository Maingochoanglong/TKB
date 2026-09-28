# Nghiên cứu: ALNS và hai hướng khác cho bước xếp giờ

Tài liệu nghiên cứu trên nhánh `claude/cp-sat-anlp-development-6uqx3j`. Chưa đổi code chạy thật: `tkb/lns.py`,
mã kết quả và TKB giữ nguyên. Mọi số liệu dưới đây đo trên Linux với các hằng số mặc định của `main.py` (bù giờ,
`THOI_GIAN_TOI_DA = 1200`, 8 luồng, chế độ tái lập; mục 8 có thêm 2400). Với file của trường chỉ ghi chi phí và loại
vùng, không ghi tên.

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
- **Hai hướng khác** (mục 8), so với cách cũ ở 1200 và 2400:
  - **Vùng mới** cắt ngang loại cũ (một khối, hoặc các lớp của một GV dùng chung, trong 2 ngày) không giúp gì. Đặt
    cuối vòng thì ra đúng cùng TKB; đặt trước vùng lớn thì kém hơn 0,06–0,6%.
  - **Nhiễu mạnh rồi LNS lại** (buộc đổi 20% số tiết của một vùng lớn) là hướng duy nhất dùng được thêm thời gian.
    Nhưng mức lợi nhỏ: với 2400, file của trường tốt hơn 0,23% (17.200 → 17.160), trường mẫu bằng; với 1200 thì bằng.
  - Mọi lần buộc đổi 20% số tiết đều **không làm tăng chi phí**: TKB có những vùng phẳng rất rộng.
- **Đề xuất** (mục 7): giữ LNS theo vòng; lấy một ý của ALNS/tabu là **bỏ lần xếp lại y hệt**. Ý này ra đúng cùng
  TKB, riêng file của trường xong sớm hơn 17% (1001 thay vì 1204 đơn vị). Vùng mới và nhiễu mạnh không đáng đưa
  vào mặc định; nhiễu mạnh chỉ có thể cân nhắc cho chế độ không giới hạn thời gian.

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
3. **Vùng mới và nhiễu mạnh (mục 8) cũng không đáng đưa vào mặc định 1200.** File của trường còn cách cận dưới
   14.210 khoảng 17%, nhưng phần lớn là bắt buộc theo luật cứng (spec §14.4), và tối ưu cục bộ mà LNS hiện tại đạt
   được rất "chắc":
   - vùng mới cắt ngang không phá được nó (đặt cuối vòng: cùng TKB), đặt trước còn làm kết quả kém đi;
   - nhiễu mạnh rồi LNS lại đôi khi tìm được nghiệm tốt hơn, nhưng ít (0,23% trên file của trường sau gấp đôi thời
     gian). Có thể cân nhắc cho **chế độ không giới hạn**: thay vì tự dừng khi một vòng không còn giảm (file của
     trường dừng ở khoảng 1000 đơn vị), tiếp tục nhiễu + LNS lại tới khi bấm Ctrl+C. Trước khi quyết cần thử thêm
     nhiều hạt giống và mức nhiễu khác, vì mỗi bộ dữ liệu mới chạy một lần.

## 8. Hai hướng khác so với cách cũ

Sau ALNS (mục 5), thử tiếp hai hướng của mục 7.3 bằng `tools/thu_alns.py`. Hai hướng dùng chung bước khởi đầu và
cách xếp lại một vùng với cách cũ, và cũng bỏ lần xếp lại y hệt (không làm đổi TKB, mục 7.2). Mỗi hướng chạy với
1200 (mặc định) và 2400, để xem hướng đó có biến thêm thời gian thành TKB tốt hơn không. Cách cũ thì không: nó tự
dừng khi một vòng không còn giảm (bỏ lần trùng: trường mẫu ở 1439 đơn vị, file của trường ở 1001), và mọi ngân sách
từ 1200 trở lên đều ra cùng TKB (spec §9: 1200 đã bằng chế độ không giới hạn).

### 8.1. Hướng A: vùng mới (`vung_moi`, `vung_moi_sau`)

Mỗi vòng thêm hai loại vùng cắt ngang các loại cũ, giới hạn 10 mỗi vùng:
- **khối × 2 ngày:** một khối trong cặp ngày có tổng chi phí QA lớn nhất của khối đó (5 vùng mỗi vòng);
- **GV × 2 ngày:** các lớp của một GV dùng chung (như vùng GV dùng chung) trong cặp ngày xấu nhất của các lớp đó
  (7–8 vùng mỗi vòng).

Mỗi vùng mới có 700–1.400 biến (vùng cặp ngày khoảng 5.000). Đây là phần giao của các vùng lớn hay hết giờ (khối, GV
dùng chung, cặp ngày): nếu vùng lớn hết giờ mà bỏ sót một cách giảm nằm trong phần giao thì vùng mới sẽ tìm ra.
Thử hai cách đặt: trước vùng GV dùng chung (`vung_moi`, "vùng nhỏ trước" như cách cũ) và cuối mỗi vòng
(`vung_moi_sau`).

| | Trường mẫu 1200 | Trường mẫu 2400 | File của trường 1200 | File của trường 2400 |
|---|---:|---:|---:|---:|
| Cách cũ | 17.050 | 17.050 | 17.200 | 17.200 |
| Vùng mới đặt trước | 17.150 (+100) | 17.060 (+10), tự dừng ở 1550 | 17.260 (+60) | 17.260 (+60), tự dừng ở 1262 |
| Vùng mới đặt cuối | 17.050, cùng TKB | 17.050, cùng TKB, tự dừng ở 1442 | 17.200, cùng TKB, tự dừng ở 1003 | 17.200, cùng TKB |

- **Đặt cuối vòng:** vùng mới được giải 40 lần (trường mẫu) và 28 lần (file của trường; không kể các lần bỏ vì
  trùng), **không lần nào giảm**, và lần nào CP-SAT cũng chứng minh xong ngay (tổng cộng 2–3 đơn vị). Nghiệm của cách
  cũ đã tối ưu sẵn trong mọi vùng mới; TKB y hệt (mã băm nghiệm trùng với cách cũ).
- **Đặt trước:** vùng mới giảm nhiều ở vòng 1 (file của trường: khối × 2 ngày 790, GV × 2 ngày 1.710), nhưng sau đó
  vùng GV dùng chung chỉ còn giảm 2.470 thay vì 4.610, và LNS dừng ở một tối ưu cục bộ xấu hơn. Đi bước nhỏ trước
  thì mất những thay đổi lớn mà chỉ vùng cả tuần mới làm được. Có thêm thời gian (2400) cũng không bù lại.
- **Kết luận:** vùng mới không có ích. Chỗ kẹt của tối ưu cục bộ hiện tại không phải là "vùng lớn hết giờ nên bỏ
  sót phần giao".

### 8.2. Hướng B: nhiễu mạnh rồi LNS lại (`nhieu`)

Kiểu tìm kiếm cục bộ lặp (iterated local search): chạy LNS như cũ tới khi dừng, rồi lặp tới khi hết ngân sách:
1. chọn ngẫu nhiên (bộ sinh số tất định, mục 6) một vùng lớn của nghiệm tốt nhất: GV dùng chung, khối hoặc cặp ngày;
2. **buộc đổi chỗ ít nhất 20% số tiết** trong vùng; CP-SAT tìm cách đổi rẻ nhất, có thể tệ hơn (giới hạn 30);
3. chạy các vòng LNS như cũ từ nghiệm đó tới khi dừng; tốt hơn nghiệm tốt nhất thì giữ.

| | Trường mẫu | File của trường |
|---|---:|---:|
| 1200 | 17.050, bằng: LNS dùng hết ngân sách, không còn chỗ để nhiễu (không chạy riêng, kết quả chắc chắn trùng cách cũ) | 17.200, bằng: 1 lần nhiễu, hết ngân sách giữa lúc LNS lại |
| 2400 | 17.050, bằng: 3 lần nhiễu, không lần nào tốt hơn | **17.160 (−40, −0,23%)**: 4 lần nhiễu, 1 lần tốt hơn |

Các lần nhiễu ở 2400 (chi phí: trước nhiễu → sau nhiễu → sau LNS lại):

| Lần | Trường mẫu | File của trường |
|---|---|---|
| 1 | khối 5, đổi ≥ 32/160 tiết: 17.050 → 17.050 → 17.050 | khối 5, đổi ≥ 32/160 tiết: 17.200 → 17.200 → **17.160** |
| 2 | GV dùng chung (khối 1), ≥ 32/160: 17.050 → 17.050 → 17.050 | GV dùng chung (4 lớp khối 4), ≥ 26/128: 17.160 → 17.160 → 17.160 |
| 3 | GV dùng chung (khối 2–3), ≥ 38/192: 17.050 → 17.050 → 17.050 | GV dùng chung (khối 5), ≥ 32/160: 17.160 → 17.160 → 17.160 |
| 4 | | GV dùng chung (khối 2–3), ≥ 45/224: 17.160 → 17.160 → 17.160 |

- **Không lần nhiễu nào làm tăng chi phí.** Đổi chỗ 20% số tiết của một khối hay một nhóm lớp mà chi phí vẫn y
  nguyên: TKB có những vùng phẳng rất rộng (mục 5.2 đã thấy điều này khi đổi 1 tiết). Vì vậy nhiễu thực chất là một
  bước nhảy xa trên vùng phẳng, không phải một bước lùi.
- **Chỉ hướng này biến thêm thời gian thành TKB tốt hơn**, nhưng ít: −40 (0,23%) trên file của trường, 0 trên
  trường mẫu, khi gấp đôi thời gian. Mỗi bộ dữ liệu mới chạy một lần với một hạt giống, nên chưa nói được mức lợi
  trung bình.
- Mỗi lần nhiễu + LNS lại tốn 300–400 đơn vị (một vòng đầy đủ và một vòng không giảm), nên với 1200 gần như không
  còn chỗ cho nó.

### 8.3. So sánh chung

| Hướng | So với cách cũ | Tốn thêm |
|---|---|---|
| ALNS (mục 5) | kém hơn 1,2–6% hoặc bằng | không |
| A: vùng mới | đặt cuối vòng: bằng, cùng TKB; đặt trước: kém hơn 0,06–0,6% | đặt cuối: gần 0 |
| B: nhiễu mạnh + LNS lại | 1200: bằng; 2400: file của trường tốt hơn 0,23%, trường mẫu bằng | gấp đôi thời gian |

Tối ưu cục bộ mà LNS hiện tại đạt được rất "chắc": vùng mới không phá được, chỉ nhảy xa trên vùng phẳng rồi tối ưu
lại mới đôi khi thấy nghiệm tốt hơn, và lợi ích nhỏ. Với mặc định 1200, cách cũ vẫn là lựa chọn tốt nhất.

## 9. Tài liệu tham khảo

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
