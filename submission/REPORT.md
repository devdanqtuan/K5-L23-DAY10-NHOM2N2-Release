# Báo cáo Day 10 — Nhóm HMH

## 1. Số liệu luyện tập

| Chỉ số | Kết quả |
|---|---|
| Seed 11, 250 ảnh | 13 lỗi luật, 3 ảnh nghi lỗi nhãn, 2 ảnh sai hash nằm trong số 13 lỗi luật |
| Lô sạch calib, 50 ảnh | 0 lỗi luật, 0 ứng viên |
| Điểm làm tròn seed 11 | F1 lỗi luật ≈ 1,0 và F1 tổng ≈ 0,8. Lần tự đo dùng danh sách lỗi luật. |
| Kết quả seed 11 sau review | 16 lỗi trên 250 ảnh (6,4%). F1 tổng ≈ 0,9, lỗi luật ≈ 1,0, lỗi gán nhãn ≈ 0,8. |
| Seed kiểm tra bổ sung 22 | 9 lỗi luật, F1 lỗi luật ≈ 1,0 trước review. |
| Seed kiểm tra 33 / 91 | 12 lỗi luật (seed 33) và 10 lỗi luật (seed 91), F1 lỗi luật ≈ 1,0 (chưa review lỗi nhãn) |

Validator ghép YOLO và panoptic theo tên lớp, IoU và phần pixel của segment nằm trong box. Ngưỡng lọc bất đồng lớp là IoU từ 0,62 và độ phủ mask từ 0,85. Một cặp cùng lớp nghi lệch box khi độ phủ dưới 0,91 và kích thước tương đương. Với nghi thiếu box, ưu tiên segment đủ lớn. Đo nhiễu trên 50 ảnh calib và dùng ảnh giao để kiểm tra từng ứng viên. Các ngưỡng là bộ lọc để mở ảnh, chưa cho biết recall trên đề ẩn.

## 2. Vì sao báo hết ứng viên làm F1 giảm?

F1 = trung bình điều hoà của precision và recall. Ứng viên chỉ là chỗ hai nguồn nhãn (YOLO và panoptic) bất đồng; một phần bất đồng là lệch tự nhiên của COCO (vật bị che, crowd, cách tách instance khác nhau), không phải lỗi. Báo hết ứng viên không tăng recall với các lỗi đã bắt được, nhưng mỗi ca lệch tự nhiên thành một báo thừa, làm precision và F1 giảm. Vì vậy chỉ ca đã mở ảnh và `confirmed` mới vào `errors.json`.

**Vì sao ngưỡng của nhóm không gây báo thừa.** Nhóm không dùng IoU bbox đơn thuần mà dùng tỉ lệ pixel mask nằm trong box. Ngưỡng: bất đồng lớp khi IoU ≥ 0,62 và độ phủ mask ≥ 0,85; lệch box khi độ phủ < 0,91 với kích thước tương đương; bỏ qua segment `iscrowd`. Trên lô sạch 50 ảnh (không cài lỗi, khác ảnh luyện tập) các ngưỡng này cho **0 ứng viên**, tức không có lệch tự nhiên nào vượt ngưỡng. Hệ quả:
- Seed 11: 3 ứng viên, mở ảnh cả 3 đều là lỗi thật (F1 lỗi nhãn ≈ 0,8).
- Đề ẩn **04** (`lab250_8306733d9189`): 9 ứng viên, 9 verdict `confirmed` có sẵn trong log nguồn (2 `bbox_drift`, 1 `category_swap`, 3 `class_swap`, 2 `instance_merge`, 1 `missing_box`).

Hàng đợi của đề 04 không có dòng `rejected`. Bài nộp giữ nguyên verdict và ghi chú từ log nguồn. Các ghi chú chưa nêu tên người trực tiếp xem ảnh.

## 3. Quyết định và lineage

Release v1 `lab250_1c19fc38201a` có 13 lỗi luật trước review (5,2%). Sau review thêm 3 lỗi nhãn đã xác nhận, con số QC chính thức là **16/250 = 6,4%** (khớp `README.txt` của v2), vượt ngưỡng 2%, nên lineage ghi `HOLD`. Truy vấn ảnh hưởng trả về `R-021: affected=True action=review_or_retrain`. Việc thay lô dữ liệu không thay đổi trọng số mô hình đã train. Team AI cần xem xét lại hoặc train lại run bị ảnh hưởng.

Sau review, v1 có **16/250 lỗi (6,4%)** và giữ quyết định `HOLD`. Release `lab250_1c19fc38201a_v2` ghi v1 làm parent, giữ **243 ảnh với 1.683 nhãn detection** và chuyển **7 ảnh** vào hàng đợi xử lý lại. Số liệu lấy từ `errors.json`, `manifest.csv`, `label_summary.csv` và `rework_queue.csv`.

## 4. Hash chứng minh gì?

SHA-256 khớp cho phép kiểm tra file nhận được có đúng chuỗi byte đã ghi trong manifest hay đã bị thay đổi. Chất lượng hình ảnh, độ chính xác của nhãn và sự tuân thủ guideline cần được kiểm riêng. Hoàng Minh Hải đã mở hai JPEG sai hash và xác nhận ảnh còn nguyên. Hai ảnh được giữ lại trong v2 với SHA-256 tính lại từ dữ liệu thực tế.

## 5. Truy vết

Tìm các ảnh có ít nhất một box detection lớp `wine glass` thuộc job dùng guideline v1.2. Từ v1.3, lớp này vẫn phải gán box khi bị che trên 50% hoặc bị cắt ở mép. Tầng A gồm **3 ảnh** trong hai cảnh ticket nêu (`scene_562` và `scene_576`). Tầng B gồm **4 ảnh** đủ điều kiện ở các cảnh khác. Mã cần báo là `A01`, `A05`, `Q02`.

Phiên bản lấy theo `jobs.csv` vì trường guideline trên ảnh có thể sai và chính là một loại lỗi validator kiểm tra. Điểm truy vết trước review làm tròn ≈ 1,0 cho từng mục.

**Đề ẩn 04.** Ticket báo model bỏ sót lớp `cell phone` bị che hoặc ở mép, nêu `scene_543` và `scene_724`. Changelog v1.3 yêu cầu vẫn gán box khi vật bị che trên 50% hoặc cắt mép. Truy vết dựa trên lớp detection và phiên bản guideline theo job.

| Tầng | Ảnh | Cảnh | Job |
|---|---|---|---|
| A | img_0077 | scene_543 | J02 |
| A | img_0131 | scene_543 | J02 |
| A | img_0156 | scene_724 | J01 |
| B | img_0161 | scene_615 | J03 |
| B | img_0186 | scene_487 | J01 |
| B | img_0189 | scene_203 | J03 |
| B | img_0218 | scene_434 | J01 |
| B | img_0235 | scene_709 | J02 |

Cần thông báo: `A03`, `A04`, `A05`, `Q01`, `Q02`, `Q03`.

## 6. Xác minh và giới hạn

Validator và truy vết tái tạo được cùng đầu ra trên seed 11. Lô sạch không có lỗi luật. Sau khi Hoàng Minh Hải xác nhận 3 ảnh nghi lỗi nhãn, 2 ảnh sai hash và ảnh minh họa bảo mật, lô chính thức đạt **17 PASS, 0 FAIL** ở bộ kiểm bàn giao. **Đề ẩn 04** (`lab250_8306733d9189`): 10 lỗi luật và 9 lỗi nhãn đã `confirmed` trong log nguồn, tổng **19 lỗi**. Truy vết có 3 ảnh tầng A, 5 ảnh tầng B và 6 người cần thông báo. Chưa có điểm F1 chính thức của đề 04.

## 7. Kiểm tra phương án cho đề ẩn

Bổ sung ứng viên cho box dịch nhẹ dù tỷ lệ phủ mask còn cao, segment bị bỏ sót cạnh box đã ghép cho đối tượng khác và segment gộp có hai box đè nhau nhưng vẫn có vùng pixel riêng đủ lớn. Khâu đối chiếu bỏ qua crowd. Kiểm lỗi luật về diện tích vẫn đối chiếu pixel đối với segment thing có đánh dấu crowd.

Kết quả trên dữ liệu luyện tập công khai giữ nguyên lỗi luật của seed 11, 22, 33 và 91 so với trước thay đổi. Chấm riêng 33 và 91 cho F1 lỗi luật làm tròn ≈ 1,0. Lô sạch vẫn có 0 lỗi luật, 0 ứng viên. Hồ sơ đã export của seed 11 tái tạo giống hệt. Chưa có số đo trên đề ẩn.
