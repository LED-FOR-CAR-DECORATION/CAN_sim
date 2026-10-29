# Kan_sim — bộ giả lập CAN ô tô trên bàn

Mô phỏng rẽ trái/phải, hazard, xe dừng, số lùi và phanh bằng ESP32.
Có công cụ Python điều khiển qua USB và preview không cần phần cứng.
Đây là giao thức test tự định nghĩa, **không phải ID/dữ liệu Hyundai i10 2019**.
Chỉ kết nối bus thử độc lập; không phát các frame này vào xe thật.

## Lấy tín hiệu từ ACC + MOZA R5

Đã có `tools/acc_bridge.py` đọc shared memory ACC trên Windows: tốc độ, phanh,
số lùi và hai trạng thái xi-nhan (hai phía bật = hazard). Xem
[hướng dẫn ACC](docs/ACC.md) để gán nút MOZA trong game, chạy preview và phát qua USB.

```powershell
python tools/acc_bridge.py --dry-run
# Sau khi nạp lại firmware sender mới và chọn đúng COM:
python tools/acc_bridge.py --port COM7
```

Bridge ngừng CAN khi dữ liệu ACC không hợp lệ/pause hoặc mất kết nối. Trong chế
độ ACC, sender có watchdog 1 giây; không giữ/phát trạng thái cũ vô hạn.

## Chạy ngay không cần phần cứng

```powershell
cd D:\SEP\Kan_sim
python tools/simulator.py --dry-run
python tools/simulator.py --dry-run --demo
python -m unittest discover -s tests -v
```

Preview in một frame sau mỗi lệnh; không tạo tín hiệu điện CAN.
Firmware ESP32 mới phát CAN thực liên tục mỗi 100 ms.

## Phần cứng và nạp chương trình

- Hai ESP32 DevKit dùng chip ESP32 gốc (board `esp32dev`).
- Hai transceiver SN65HVD230 tương thích logic 3.3 V, dây xoắn đôi.
- USB cho từng board; không cấp 12 V ô tô vào ESP32.

Đấu giống nhau trên cả hai board:

| ESP32 | Transceiver |
|---|---|
| 3V3 | VCC 3.3 V |
| GND | GND |
| GPIO5 (TX) | TXD / CTX |
| GPIO4 (RX) | RXD / CRX |

Nối CAN_H ↔ CAN_H, CAN_L ↔ CAN_L và chung GND giữa hai node.
Mỗi đầu vật lý của bus có một điện trở 120 Ω giữa H/L. Kiểm tra điện trở
có sẵn trên module trước khi thêm; bus tắt nguồn thường đo khoảng 60 Ω giữa H/L
khi có đúng hai điện trở 120 Ω song song. Đặt transceiver ở chế độ hoạt động
theo tài liệu module; không để standby.

Cài PlatformIO CLI, sau đó:

```powershell
pio run -e sender
pio run -e receiver
pio run -e sender -t upload --upload-port COM5
pio run -e receiver -t upload --upload-port COM6
python -m pip install -r requirements.txt
python tools/simulator.py --port COM5
```

Thay COM5/COM6 theo cổng thực tế. Mở terminal khác xem node nhận:

```powershell
pio device monitor --port COM6 --baud 115200
```

Không mở Serial Monitor và Python trên cùng COM. Có thể dùng Serial Monitor
thay Python để nhập lệnh, đặt kết thúc dòng newline. Hai node chạy 500 kbit/s,
CAN chuẩn 11 bit, DLC 8. Node nhận dùng NORMAL để ACK; LISTEN_ONLY không ACK.
`TX_ACK` xác nhận truyền ở tầng CAN, không chứng minh ứng dụng nhận đã xử lý.
`STATE` là trạng thái được đặt; không phải báo truyền thành công. Lỗi enqueue,
TX_FAILED và BUS_OFF được in riêng; firmware tự bắt đầu phục hồi bus-off.

## Điều khiển

| Lệnh | Ý nghĩa |
|---|---|
| `LEFT`, `RIGHT` | Chọn rẽ trái hoặc phải |
| `HAZARD` | Bật cảnh báo hai phía |
| `OFF` | Tắt xi-nhan/hazard, giữ tốc độ/số lùi/phanh |
| `SPEED 25.5` | Tốc độ 0–200 km/h, độ phân giải 0.1 |
| `STOP` | Tốc độ bằng 0, giữ các trạng thái khác |
| `REVERSE ON`, `REVERSE OFF` | Bật/tắt số lùi, độc lập tốc độ |
| `BRAKE ON`, `BRAKE OFF` | Bật/tắt phanh, độc lập trạng thái dừng |
| `RESET` | Tắt mọi tín hiệu và tốc độ về 0 |
| `STATUS` | In trạng thái hiện tại |
| `DEMO` | Kịch bản trong Python; Serial firmware không có lệnh này |
| `QUIT` | Thoát Python, gửi RESET nếu đang nối USB |

Hazard là chế độ yêu cầu bật; bộ hiển thị phía nhận tự tạo nhịp nhấp nháy.
Chuyển LEFT/RIGHT sẽ thay thế hazard. Xe dừng là `speed == 0`, không đồng nghĩa
đạp phanh. Reverse ON với speed bằng 0 biểu diễn đang vào số lùi nhưng chưa chạy.
Firmware tiếp tục giữ/phát trạng thái cuối nếu mất kết nối USB đột ngột; khi thoát
Python bình thường công cụ gửi RESET. RESET vẫn phát trạng thái đứng yên mỗi 100 ms.

## Giao thức tích hợp

ID `0x321`, CAN classic, standard data frame, 8 byte, chu kỳ 100 ms:

| Byte | Nội dung |
|---|---|
| 0 | Phiên bản = 1 |
| 1 bit 0–1 | 0=off, 1=left, 2=right, 3=hazard |
| 1 bit 2 | Reverse |
| 1 bit 3 | Brake |
| 1 bit 4–7 | Reserved = 0 |
| 2–3 | Tốc độ ×10, uint16 little endian, 0–2000 |
| 4 | Counter tăng mỗi lần thử gửi, quay vòng 255 → 0 |
| 5–7 | Reserved = 0 |

Ví dụ hazard + lùi + phanh, 5.5 km/h, counter 0:
`321#010F370000000000`. CAN cung cấp CRC tầng đường truyền; giao thức test
không thêm checksum ứng dụng. Counter phục vụ quan sát, chưa chống replay.

`include/protocol.h` chứa encode/decode dùng chung cho firmware phát/nhận.
`protocol/kan_sim.dbc` mô tả tín hiệu để nhập vào công cụ phân tích CAN hỗ trợ DBC.
Bên nhận chỉ chấp nhận đúng ID, standard frame, không RTR, DLC/version/reserved
và miền tốc độ hợp lệ. Nếu quá 500 ms không có frame hợp lệ sau khi đã nhận,
in `STALE` và đánh dấu UNKNOWN; không suy diễn mất tín hiệu là xe dừng.
Lúc mới bật chưa có frame cũng là UNKNOWN.

Repo `D:\SEP\IoT-Device` đã có CAN receiver trong `src/core/CarSignalService.cpp`
và hiệu ứng trái/phải/hazard/phanh/lùi/dừng. Phía LED dùng TX GPIO21, RX GPIO22;
phía sender vẫn TX GPIO5, RX GPIO4. Xem `IoT-Device/docs/CAN.md` để đấu nối và nạp
firmware LED. Environment receiver ở repo này chỉ kiểm tra bus, không điều khiển LED.

## Xác minh

Unit test Python kiểm tra tổ hợp trạng thái, dừng/phanh độc lập, byte order,
counter và đầu vào sai. Build cả hai environment để kiểm tra API TWAI.
Test vật lý: chạy DEMO trên sender, đối chiếu STATE/RX ở receiver; tháo sender
để kiểm tra STALE, tháo receiver để kiểm tra lỗi ACK. Không thể xác nhận dây,
transceiver hoặc LED thực nếu chưa có phần cứng.

Tham khảo API chính thức:
[Espressif TWAI](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/api-reference/peripherals/twai.html).
