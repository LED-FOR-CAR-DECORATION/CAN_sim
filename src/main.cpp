#include <Arduino.h>
#include <driver/twai.h>
#include "protocol.h"

static VehicleState state;
static bool ready = false;
static uint32_t lastSend = 0, lastReceive = 0;
static uint8_t counter = 0;
static String input;
static bool overflow = false, fresh = false;
static bool transmitting = true, streaming = false;
static uint32_t lastStream = 0;
// Dedicated CAN simulator board: avoid boot strapping pins for the transceiver.
static constexpr gpio_num_t CAN_TX_PIN = GPIO_NUM_18;
static constexpr gpio_num_t CAN_RX_PIN = GPIO_NUM_19;

void printState(const VehicleState &s) {
    Serial.printf("STATE turn=%u reverse=%u brake=%u speed=%.1f stopped=%u\n",
                  s.turn, s.reverse, s.brake, s.speed / 10.0, s.speed == 0);
}

void command(String line) {
    line.trim(); line.toUpperCase();
    if (line == "STATUS") { printState(state); return; }
    if (line == "PAUSE") {
        transmitting = false; streaming = false;
        twai_clear_transmit_queue();
        Serial.println("STREAM paused; CAN state becomes UNKNOWN at receiver");
        return;
    }
    if (line.startsWith("FRAME ")) {
        unsigned speed, flags;
        char extra;
        if (sscanf(line.c_str(), "FRAME %u %u %c", &speed, &flags, &extra) != 2 ||
            speed > 2000 || flags > 15) {
            Serial.println("ERR FRAME expects speed 0..2000 and flags 0..15"); return;
        }
        state.speed = speed; state.turn = flags & 3;
        state.reverse = flags & 4; state.brake = flags & 8;
        lastStream = millis(); transmitting = true; streaming = true;
        return;
    }
    if (line == "RESET") state = VehicleState{};
    else if (line == "LEFT") state.turn = 1;
    else if (line == "RIGHT") state.turn = 2;
    else if (line == "HAZARD") state.turn = 3;
    else if (line == "OFF") state.turn = 0;
    else if (line == "STOP") state.speed = 0;
    else if (line == "REVERSE ON") state.reverse = true;
    else if (line == "REVERSE OFF") state.reverse = false;
    else if (line == "BRAKE ON") state.brake = true;
    else if (line == "BRAKE OFF") state.brake = false;
    else if (line.startsWith("SPEED ")) {
        const char *start = line.c_str() + 6;
        char *end;
        double value = strtod(start, &end);
        if (end == start || *end || !isfinite(value) || value < 0 || value > 200) {
            Serial.println("ERR speed must be 0..200 km/h"); return;
        }
        state.speed = uint16_t(lround(value * 10));
    } else { Serial.println("ERR unknown command"); return; }
    transmitting = true; streaming = false;
    printState(state);
}

void setup() {
    Serial.begin(115200);
    input.reserve(80);
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_NORMAL);
    general.alerts_enabled = TWAI_ALERT_BUS_OFF | TWAI_ALERT_BUS_RECOVERED |
                            TWAI_ALERT_TX_FAILED | TWAI_ALERT_TX_SUCCESS;
    twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    esp_err_t err = twai_driver_install(&general, &timing, &filter);
    if (err == ESP_OK) err = twai_start();
    ready = err == ESP_OK;
    Serial.printf("KAN_SIM %s init=%s, 500 kbit/s TX=%d RX=%d\n",
#ifdef KAN_RECEIVER
                  "receiver",
#else
                  "sender",
#endif
                  esp_err_to_name(err), int(CAN_TX_PIN), int(CAN_RX_PIN));
#ifdef KAN_RECEIVER
    Serial.println("UNKNOWN: waiting for first valid vehicle frame");
#endif
}

void loop() {
    if (!ready) { delay(100); return; }
    uint32_t alerts = 0;
    twai_read_alerts(&alerts, 0);
    if (alerts & TWAI_ALERT_BUS_OFF) {
        Serial.println("ERR BUS_OFF: check wiring, bitrate and ACK peer; recovering");
        twai_initiate_recovery();
    }
    if (alerts & TWAI_ALERT_BUS_RECOVERED) {
        Serial.printf("BUS restart=%s\n", esp_err_to_name(twai_start()));
    }
    if (alerts & TWAI_ALERT_TX_FAILED) Serial.println("ERR TX_FAILED");
#ifndef KAN_RECEIVER
    // Bounded input and work per loop keep frame scheduling responsive.
    for (int n = 0; n < 80 && Serial.available(); ++n) {
        char c = Serial.read();
        if (c == '\n') {
            if (overflow) Serial.println("ERR command too long"); else command(input);
            input = ""; overflow = false;
        } else if (c != '\r') {
            if (input.length() < 79) input += c; else overflow = true;
        }
    }
    if (alerts & TWAI_ALERT_TX_SUCCESS) Serial.println("TX_ACK");
    if (streaming && millis() - lastStream > 1000) {
        transmitting = false; streaming = false;
        twai_clear_transmit_queue();
        Serial.println("STREAM timeout; CAN paused (UNKNOWN)");
    }
    if (transmitting && millis() - lastSend >= PERIOD_MS) {
        lastSend = millis();
        twai_message_t frame = {};
        frame.identifier = SIGNAL_ID; frame.data_length_code = 8;
        frame.ss = 1; // Single shot avoids indefinite retries when no ACK peer exists.
        encode(state, counter++, frame.data);
        esp_err_t err = twai_transmit(&frame, 0);
        if (err != ESP_OK) Serial.printf("ERR enqueue=%s\n", esp_err_to_name(err));
    }
#endif
    twai_message_t frame;
    for (int n = 0; n < 16 && twai_receive(&frame, 0) == ESP_OK; ++n) {
#ifdef KAN_RECEIVER
        if (!frame.extd && !frame.rtr && frame.identifier == SIGNAL_ID &&
            frame.data_length_code == 8 && decode(frame.data, state)) {
            lastReceive = millis(); fresh = true;
            Serial.printf("RX counter=%u ", frame.data[4]); printState(state);
        }
#endif
    }
#ifdef KAN_RECEIVER
    if (fresh && millis() - lastReceive > STALE_MS) {
        fresh = false;
        Serial.println("STALE: vehicle state UNKNOWN (not stopped); no valid frame for 500ms");
    }
#endif
    delay(1);
}
