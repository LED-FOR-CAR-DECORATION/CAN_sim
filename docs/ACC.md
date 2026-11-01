# Cập nhật phạm vi 30/10/2026

Bridge ACC hiện chỉ chuyển tốc độ, rẽ trái/phải, hazard và lùi. Không còn gửi
phanh; bit3 vẫn bằng 0. Tốc độ chỉ dùng cho buzzer phía LED. LED có 5 slot
Idle/Left/Right/Hazard/Reverse; xem IoT-Device/docs/VEHICLE_SLOTS.md và PINOUT.md.

# Dùng MOZA R5 + ACC làm nguồn tín hiệu

## ACC có ảnh hưởng đến Hyundai i10 không?

Xe trong ACC quyết định tốc độ, phản ứng phanh, số và đèn trong game. Bridge chỉ
chuyển những trạng thái đó thành giao thức test `0x321` của Kan_sim. Đổi xe ACC
không đổi ID hoặc định dạng frame test. Đây là cách kiểm tra đường truyền CAN
và logic LED, không xác minh bộ giải mã CAN Hyundai i10 2019.

Khi chuyển sang xe i10 thật phải có adapter giải mã riêng dựa trên bản ghi CAN
hoặc tài liệu đúng phiên bản xe. Không phát ID test vào xe thật. Tốc độ/phanh
của xe đua cũng không mô phỏng chính xác động học i10.

## Chuẩn bị

1. Kết nối MOZA và hiệu chuẩn bàn đạp trong Pit House/ACC như khi chơi bình thường.
2. Trong ACC → Options → Controls, tìm các mục indicator/turn indicator trái,
   phải và hazard nếu phiên bản game có. Gán các nút trống trên vô-lăng; tên mục
   tùy ngôn ngữ/phiên bản. Không cần cần xi-nhan. Bridge không gán nút trong game
   tự động và không suy diễn xi-nhan từ góc vô-lăng.
3. Vào Practice, chọn xe, vào cockpit và bắt đầu lái. Không chỉ ở menu/replay.
4. Chạy Python và ACC trong cùng phiên đăng nhập Windows. Không cần bật UDP
   broadcasting: công cụ dùng shared memory, chỉ mở map đã tồn tại, chỉ đọc.

## Chạy thử chỉ đọc ACC

```powershell
cd D:\SEP\Kan_sim
python tools/acc_bridge.py --dry-run
```

Quan sát `LIVE speed=... brake=... reverse=... turn=...`:

`gas` cũng hiển thị mức bàn đạp ga 0–1 để đối chiếu khi lái; giao thức CAN test
hiện chưa có trường ga riêng. Graphics có trường `Clock` trước hai xi-nhan;
bridge đọc left/right tại offset 1492/1496 (layout ACC 1.8.12).

- Phanh không được chuyển sang CAN và không điều khiển LED.
- Tốc độ dưới 0.5 km/h chuyển thành 0 (xe dừng); độc lập tín hiệu phanh.
- Gear ACC `0=R`, `1=N`, `2=số 1`; reverse chỉ bật khi R.
- `turn`: 0=tắvaihtsLeft`/`directionLightsRight` của game; không suy từ đèn mưa,
  flash đèn pha hoặc cờ vàng. Nếu xe/game không báo các trường này, turn vẫn 0;
  kiểm tra nút gán và đèn trên xe trong game trước.
- ACC có thể chạy hơn 200 km/h: bridge giới hạn tại 200 và in cảnh báo vì
  giao thức test hiện chỉ hỗ trợ 0–200. Không đổi theo model xe.

Có thể chỉnh ngưỡng:

```powershell
python tools/acc_bridge.py --dry-run --stop-speed 0.3
```

## Phát qua ESP32

Nạp **lại sender mới**, có hỗ trợ FRAME/PAUSE và watchdog:

```powershell
pio device list
pio run -e sender -t upload --upload-port COM7
python -m pip install -r requirements.txt
python tools/acc_bridge.py --port COM7
```

COM7 là ví dụ; chọn USB ESP32 thực, không chọn cổng Bluetooth. Đóng Serial
Monitor trên cùng cổng. Board thứ hai có thể dùng firmware `receiver` kiểm tra
CAN theo README. Firmware LED trong IoT-Device đã có decoder CAN; xem
`D:\SEP\IoT-Device\docs\CAN.md`, dùng TX GPIO21/RX GPIO22 ở phía LED.

Bridge gửi trạng thái nguyên khối qua Serial ở 10 Hz: `FRAME <speed_x10> <flags>`.
Sender chuyển sang chế độ streaming, phát CAN mỗi 100 ms. Khi pause/replay/menu,
map mất hoặc packet không cập nhật trong 750 ms, bridge gửi `PAUSE`, không gửi
trạng thái dừng giả. Receiver chuyển UNKNOWN sau 500 ms mất frame. Khi Python
bị tắt đột ngột, watchdog sender ngừng phát sau 1 giây thiếu FRAME; dữ liệu có thể
còn cũ tối đa khoảng 1.5 giây tính cả timeout receiver. Ctrl+C gửi PAUSE trước khi
thoát. Khi game LIVE và packet cập nhật trở lại, bridge tự tiếp tục.

Các lệnh thủ công LEFT/RIGHT/RESET... chuyển sender về chế độ thủ công và phát
liên tục như trước; STATUS không thay đổi chế độ. Không chạy bridge ACC và
simulator.py cùng cổng. Khi ACC đóng/mở lại, bridge tự thử mở lại shared memory.

## Phạm vi xác minh

Unit test dùng snapshot nhị phân giả lập kiểm tra offset, số lùi, hazard, phanh,
ngưỡng dừng, pause/replay và packet bị treo. Không thay thế kiểm tra với ACC
đang chạy và hai board thực. Bridge đọc phần đầu layout Physics và Graphics
đến directionLights; nếu phiên bản ACC thay layout cần cập nhật theo tài liệu.

Nguồn layout và tên map:
- [Physics của thư viện ACC](https://github.com/MorGuux/AssettoCorsaCompetizioneSharedMemory/blob/master/Physics.cs)
- [Graphics của thư viện ACC](https://github.com/MorGuux/AssettoCorsaCompetizioneSharedMemory/blob/master/Graphics.cs)
- [Tên map của thư viện ACC](https://github.com/MorGuux/AssettoCorsaCompetizioneSharedMemory/blob/master/AssettoCorsaCompetizione.cs)
