# Validator của nhóm

`validate.py` kiểm lô được giao và tạo danh sách ứng viên để người xem ảnh xác nhận.

```
python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
```

Validator đọc dữ liệu từ thư mục delivery được truyền vào, dùng thư viện chuẩn Python và ghi kết quả ra ngoài delivery. File `--out` chứa lỗi luật. File tùy chọn `--candidates` chứa bằng chứng đối chiếu để xem ảnh. Xem [GUIDE.md](../GUIDE.md) Pha 1–2 và [RULES.md](../RULES.md).
