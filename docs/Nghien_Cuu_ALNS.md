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

(điền sau)

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
