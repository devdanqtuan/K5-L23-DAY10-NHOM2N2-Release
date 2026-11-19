# Đề ẩn Day 10 — Nhóm HMH
Phụ trách quy trình & công cụ: Đặng Gia Tuấn (@tuandg)

Mục tiêu là tối đa F1 trên đề ẩn, hoàn thành 4 file bắt buộc và có thời gian kiểm tra commit đã push. Mốc nhóm đang nhắm là nộp trước 19:30, chừa 5 phút dự phòng. Giờ mở đề, hạn và cách tính thưởng theo thông báo giảng viên.

## Khi nhận đề

Giải nén file chính thức để có thư mục `delivery/` ở gốc repo. Chạy bằng Python 3.10 trở lên.

```bash
python3 lab_tools/de_an.py prepare
open runs/de_an/review.html
```

Validator lưu lỗi luật vào `runs/de_an/rules.json`. Danh sách review và trang HTML ở cùng thư mục. Chia ảnh cho các thành viên. Mỗi người mở ảnh, chọn đúng loại lỗi và ghi `confirmed` hoặc `rejected` kèm tên người xem và cụ thể đã thấy gì. Với bất đồng lớp, xác định nguồn sai để chọn `class_swap` hoặc `category_swap`. Giữ cả các dòng `rejected` đã review.

## Xuất và kiểm tra bài

Sau khi chốt review:

```bash
python3 lab_tools/de_an.py finish
git add -- submission/de_an/errors.json submission/de_an/candidates.json \
  submission/de_an/review_log.csv submission/de_an/trace.json
git diff --cached --stat
```

Nếu gần đến hạn mà còn dòng chưa xem, chạy `python3 lab_tools/de_an.py finish --only-reviewed` thay cho `finish`. Lệnh xuất lỗi luật và kết luận người xem đã chốt. Các dòng còn trống ở lại trong `runs/de_an/review_log.csv`. Bài xuất theo cách này có thể bỏ sót lỗi nhãn.

Kiểm nội dung staged trước khi commit và push. `delivery/`, `runs/` và ZIP ở máy. Thử mở commit trên GitHub, rồi nộp link qua kênh giảng viên chỉ định.

## Phân bổ 40 phút

| Khoảng từ lúc phát đề | Việc ưu tiên |
|---|---|
| 0–5 phút | Giải nén, chạy prepare, chia hàng đợi. |
| 5–25 phút | Cả nhóm xem ảnh, người tổng hợp ghi nhận verdict và rà truy vết. |
| 25–35 phút | Chốt các ca khó, chạy finish, đối chiếu bốn file và commit. |
| 35–40 phút | Push, mở commit để xác minh và nộp link. |

Nếu hạn đến sớm hơn, chừa thời gian cho bước kiểm tra, push và nộp link. Phần điểm dựa trên F1 có tính cả báo thừa, nên chỉ đưa vào `errors.json` các lỗi luật và lỗi nhãn đã được người xem xác nhận.
