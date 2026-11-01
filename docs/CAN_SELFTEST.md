# Kiểm tra riêng ESP32 + transceiver CAN

Environment `can-selftest` chỉ dành cho board phát riêng, TX GPIO18, RX GPIO19,
500 kbit/s. Dùng NO_ACK và Self Reception Request theo ví dụ Espressif:
https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32/api-reference/peripherals/twai.html

Ngắt nguồn khi thay dây. Giữ transceiver nối 3V3/GND/CTX/CRX đúng chân.
Tách CANH/CANL khỏi node khác, giữ termination phù hợp. Không nối tắt TX với RX:
bài này kiểm tra phản hồi qua transceiver bên ngoài, không phải vòng lặp dây.

```powershell
pio run -e can-selftest -t upload --upload-port COM10
pio device monitor --port COM10 --baud 115200
```

COM10 là ví dụ; chọn cổng ESP phát thực tế. Nếu bỏ lỡ log, nhấn EN để chạy lại.
Firmware thử 5 frame ID 0x6A5, so sánh đủ ID, DLC và 8 byte dữ liệu, mỗi lần
chờ tối đa 500 ms. Sau bài test driver dừng, không tiếp tục phát.

- `PASS 5/5`: tự nhận đúng cả 5 frame và không có lỗi báo về; chưa chứng minh node khác nhận/ACK được.
- `FAIL`: kiểm tra nguồn, tiếp xúc, mode và module; không đủ để kết luận chip hỏng.
- `RX_IDLE=0`: RX đang LOW lúc đo; bus idle bình thường phải recessive/HIGH.
  Đây là mức logic tại GPIO19, không phải phép đo điện áp CANH/CANL.
- `TEC`, `REC`, `failed`, `errors`, `pending`: bộ đếm lỗi và hàng đợi của TWAI.
- `enqueue=ESP_OK` chỉ là nhận vào bộ điều khiển, không phải phát thành công.

Đóng monitor và nạp lại firmware bình thường sau test:

```powershell
pio run -e sender -t upload --upload-port COM10
```

Firmware sender/receiver loại file chẩn đoán khỏi build; bài test không thay đổi
giao thức xe 0x321 và không ghi cấu hình vào NVS.

## Đối chiếu ngày 01/11/2026

- Module ban đầu: 3/5 và 4/5 frame khớp, có lỗi bus.
- Module thay thế trên cùng ESP: 5/5 và 1/5 frame khớp, có lỗi bus ở cả hai lần.
- Log gốc: `can-selftest-result.txt`, `can-selftest-module2-result.txt`.
  Bản test ban đầu in PASS khi đủ 5 frame dù có lỗi bus; dòng PASS đó chỉ
  phản ánh số frame khớp, không chứng minh phần cứng ổn định. Đã sửa tiêu chí
  để yêu cầu cả 5 frame và bộ đếm/alert không lỗi.
- Chưa đủ bằng chứng kết luận riêng module hỏng; cần đối chiếu dây, nguồn,
  termination, chế độ transceiver và ESP dùng chung.
