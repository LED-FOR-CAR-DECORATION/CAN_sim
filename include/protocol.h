#pragma once
#include <stdint.h>

// Private bench protocol. NOT Hyundai CAN identifiers or encoding.
constexpr uint32_t SIGNAL_ID = 0x321;
constexpr uint32_t PERIOD_MS = 100;
constexpr uint32_t STALE_MS = 500;
constexpr uint8_t VERSION = 1;

struct VehicleState {
    uint8_t turn = 0; // 0=off, 1=left, 2=right, 3=hazard
    bool reverse = false;
    bool brake = false;
    uint16_t speed = 0; // 0.1 km/h, unsigned magnitude
};

inline void encode(const VehicleState &s, uint8_t counter, uint8_t *d) {
    d[0] = VERSION;
    d[1] = s.turn | (s.reverse ? 4 : 0) | (s.brake ? 8 : 0);
    d[2] = s.speed & 0xff;
    d[3] = s.speed >> 8;
    d[4] = counter;
    d[5] = d[6] = d[7] = 0;
}

inline bool decode(const uint8_t *d, VehicleState &s) {
    if (d[0] != VERSION || (d[1] & 0xf0) || d[5] || d[6] || d[7]) return false;
    uint16_t speed = d[2] | (uint16_t(d[3]) << 8);
    if (speed > 2000) return false;
    s.turn = d[1] & 3;
    s.reverse = d[1] & 4;
    s.brake = d[1] & 8;
    s.speed = speed;
    return true;
}
