# Nghiên cứu: ALNS cho bước xếp giờ

Tài liệu nghiên cứu trên nhánh `claude/cp-sat-anlp-development-6uqx3j`. Chưa đổi code chạy thật: `tkb/lns.py`,
mã kết quả và TKB giữ nguyên. Mọi số liệu dưới đây đo trên Linux với các hằng số mặc định của `main.py` (bù giờ,
`THOI_GIAN_TOI_DA = 1200`, 8 luồng, chế độ tái lập). Với file của trường chỉ ghi chi phí và loại vùng, không ghi tên.

## 1. Tóm tắt

(điền sau khi có kết quả)

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

(điền sau)

## 6. Giữ tái lập khi có ngẫu nhiên

(điền sau)

## 7. Đề xuất

(điền sau)

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
