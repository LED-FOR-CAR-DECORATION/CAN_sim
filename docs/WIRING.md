# Sơ đồ cắm dây ESP32 ↔ module CAN

Dùng ESP32 DevKit (chip ESP32 gốc) và module **SN65HVD230, nguồn/logic 3.3 V**.
Firmware dùng bộ điều khiển TWAI có sẵn trong ESP32; sơ đồ này không áp dụng
cho module MCP2515 giao tiếp SPI. Đọc tên chân in trên module, không suy theo
vị trí hoặc màu dây vì các bản module có thể bố trí chân khác nhau.

## Cập nhật chân CAN Sim

CAN Sim chuyển từ TX GPIO5 / RX GPIO4 sang **TX GPIO18 / RX GPIO19**
để tránh dùng chân strapping GPIO5. Áp dụng cho cả `sender` và `receiver`
của Kan_sim trên board riêng; phải nạp lại firmware trước khi dùng chân mới.
ESP LED vẫn dùng TX GPIO21 / RX GPIO22. Không áp dụng GPIO18/19 cho ESP LED
vì GPIO18 dành cho buzzer và GPIO19 dành cho panel HUB75.
Đổi chân không bảo đảm sửa mọi lỗi nạp: vẫn cần kiểm tra nguồn và dây nối.

## 1. ESP32 phát Kan_sim → module SN65HVD230

```text
PC / Laptop
    │ USB (nguồn + lệnh Serial)
    ▼
ESP32 Kan_sim                         Module SN65HVD230
┌──────────────────┐                  ┌──────────────────┐
│ 3V3              ├─────────────────►│ VCC (3.3 V)      │
│ GND              ├──────────────────┤ GND              │
│ GPIO18 (CAN TX)  ├─────────────────►│ CTX / TXD        │
│ GPIO19 (CAN RX)  │◄─────────────────┤ CRX / RXD        │
└──────────────────┘                  │ CAN_H / H ───────┼──► CAN_H node nhận
                                      │ CAN_L / L ───────┼──► CAN_L node nhận
                                      │ GND ─────────────┼──► GND node nhận
                                      └──────────────────┘
```

| Dây | ESP32 Kan_sim | Module SN65HVD230 |
|---|---|---|
| Nguồn | 3V3 | VCC |
| Mass | GND | GND |
| Phát | GPIO18 | CTX / TXD |
| Nhận | GPIO19 | CRX / RXD |

TX của ESP32 nối **TXD của transceiver**, RX nối **RXD** như sơ đồ;
không đấu chéo TX/RX như hai thiết bị UART. H/L là phía bus CAN, không nối
trực tiếp H/L vào GPIO ESP32.

## 2. Toàn bộ bus thử: hai ESP32 và hai module CAN

```text
ESP32 phát       SN65HVD230 A                 SN65HVD230 B       ESP32 nhận
  3V3 ────────── VCC                         VCC ───────────── 3V3
  GND ────────── GND ──────────────────────── GND ───────────── GND
GPIO18 ─────────► CTX                         CTX ◄──────────── TX (*)
GPIO19 ◄───────── CRX                         CRX ─────────────► RX (*)
                  H ═════════════════════════ H
                  │                           │
                [120 Ω]                     [120 Ω]
                  │                           │
                  L ═════════════════════════ L
                         Cặp dây H/L xoắn đôi
```

Mỗi module lấy 3V3 từ ESP32 cùng phía. Hai ESP32 có thể cấp nguồn bằng USB
riêng; nối chung GND như sơ đồ. Không cần nối hai đường 3V3 với nhau.

**(*) Chọn chân phía nhận theo firmware nạp trên ESP32 đó:**

| Firmware phía nhận | TX → CTX | RX ← CRX |
|---|---|---|
| `Kan_sim`, environment `receiver` (kiểm tra bus) | GPIO18 | GPIO19 |
| `IoT-Device` (điều khiển LED) | GPIO21 | GPIO22 |

ESP32 LED không dùng GPIO4/5 cho CAN vì hai chân này dành cho HUB75.
Node nhận vẫn cần nối cả TX và RX để bộ điều khiển CAN ở NORMAL phát ACK.
Xem thêm [hướng dẫn phía LED](../../IoT-Device/docs/CAN.md).

## 3. Kiểm tra trước khi bật nguồn

1. Ngắt toàn bộ nguồn khi cắm dây hoặc đo điện trở.
2. Kiểm tra module đúng SN65HVD230 3.3 V; không cấp 5 V/12 V vào VCC module
   hoặc GPIO ESP32 theo sơ đồ này.
3. Kiểm tra H nối H, L nối L, GND chung; module ở chế độ hoạt động theo tài liệu
   của đúng module, không để standby.
4. Mỗi đầu vật lý bus có một điện trở 120 Ω giữa H và L. Nếu module đã tích hợp
   điện trở kết thúc thì tính cả điện trở đó, không thêm trùng. Khi tắt nguồn,
   bus có hai điện trở 120 Ω song song thường đo khoảng 60 Ω giữa H/L.
5. Nạp đúng firmware cho từng ESP32; cả hai phía dùng 500 kbit/s. Chạy sender
   cùng node nhận đã bật nguồn để có ACK; chỉ một node phát sẽ báo lỗi ACK.

Đây là bus thử độc lập. Không nối bus giả lập này vào xe thật.
Các bước nạp và chạy nằm trong [README](../README.md#phần-cứng-và-nạp-chương-trình).
