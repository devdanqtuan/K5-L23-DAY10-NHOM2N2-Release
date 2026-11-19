# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | @haihm | Codex | Đọc đề, hướng dẫn và chuẩn bị lab trong repo HMH | Ngưỡng IoU ban đầu (0.5) báo thừa 6 ứng viên trên lô sạch 50 ảnh do không xét tỉ lệ phủ pixel mask và chưa lọc bỏ iscrowd | Chạy lô sạch 50 ảnh, tái chạy seed 11, kiểm tra handover trên dữ liệu giả lập |
| 2 | @haihm | Codex | Hỗ trợ xem ảnh và điền ghi chú review | Codex tự phán đoán loại lỗi mà không xem ảnh thật nên dễ nhầm khi vật che khuất; gợi ý ghi chú review ban đầu thiếu tên người xem và không phân định bên nào sai | Hoàng Minh Hải (@haihm) mở và xác nhận 3 ảnh nghi lỗi nhãn, 2 ảnh sai hash và ảnh minh họa bảo mật |

## Phiên hỗ trợ Codex

- Yêu cầu người dùng là đọc repo Day 10, hướng dẫn và bắt đầu triển khai bài lab.
- Codex viết validator, công cụ dựng hàng đợi ảnh, truy vết ticket và tạo lô v2, đồng thời soạn hướng dẫn chạy.
- Đã kiểm thử bằng bộ dữ liệu giả lập riêng của Codex, gồm cả tình huống lệch lớp, lệch box, thiếu box và hai vật dùng chung segment. Bộ kiểm handover đạt 17/17 trên bộ kiểm thử giả lập.
- Codex ghi kết luận theo xác nhận của Hoàng Minh Hải, chạy kiểm định dạng trên lô chính thức (17 PASS, 0 FAIL), tự chấm và export seed 11.
- @haihm yêu cầu tối ưu điểm bắt lỗi tự động và chuẩn bị thao tác cho đề ẩn. Codex nhận thấy cặp khớp mạnh có thể che lệch khung nhỏ, một box đã ghép với vật kế bên có thể che ca thiếu box, và hai box giao nhau vừa phải có thể giải thích một segment bị gộp. Kiểm bằng mask giả lập, lô sạch và các lô luyện tập. Rehearsal chuẩn bị rồi xuất bốn file cho kết quả trùng hồ sơ seed 11 đã chốt.
- Codex bổ sung ca khung lệch mạnh với IoU thấp và kiểm tra trên mask giả lập. Thử lại lô sạch và bốn seed luyện tập để kiểm số lỗi luật và hàng đợi. Rà thao tác trong tình huống gần hết giờ: chế độ xuất theo các ca đã review bỏ dòng trống, giữ kết luận có người xem và ngăn trộn review từ hai lô.
- @haihm yêu cầu đóng gói riêng repo cho đề ẩn 04. Codex dùng các verdict có sẵn trong log nguồn, đối chiếu JSON với merge_review.py và kiểm cấu trúc ZIP.
