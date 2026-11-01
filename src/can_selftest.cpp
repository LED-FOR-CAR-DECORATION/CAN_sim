#include <Arduino.h>
#include <driver/twai.h>
#include <cstring>

// Bench diagnostic only. External transceiver required; no TX/RX jumper.
// Disconnect the other CAN node, retain suitable CAN termination.
// Build only with `pio run -e can-selftest`; normal sender excludes this file.
void setup() {
    Serial.begin(115200);
    delay(1500);
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(GPIO_NUM_18, GPIO_NUM_19, TWAI_MODE_NO_ACK);
    general.tx_queue_len = 0;
    general.alerts_enabled = TWAI_ALERT_TX_SUCCESS | TWAI_ALERT_TX_FAILED |
                             TWAI_ALERT_BUS_ERROR | TWAI_ALERT_BUS_OFF;
    twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    esp_err_t err = twai_driver_install(&general, &timing, &filter);
    if (err == ESP_OK) err = twai_start();
    Serial.printf("CAN_SELFTEST init=%s TX=18 RX=19 bitrate=500000 NO_ACK SELF_RX\n", esp_err_to_name(err));
    if (err != ESP_OK) return;
    Serial.printf("RX_IDLE=%d (normally HIGH on an idle, powered transceiver)\n", digitalRead(19));
    unsigned passed = 0;
    bool clean = true;
    for (unsigned i = 0; i < 5; ++i) {
        twai_message_t sent = {};
        sent.identifier = 0x6A5; // Separate from vehicle state ID 0x321.
        sent.data_length_code = 8;
        sent.self = 1;
        sent.ss = 1;
        for (unsigned j = 0; j < 8; ++j) sent.data[j] = uint8_t(0xA0 + i * 8 + j);
        err = twai_transmit(&sent, 0);
        bool matched = false;
        const uint32_t started = millis();
        while (err == ESP_OK && millis() - started < 500) {
            twai_message_t received = {};
            if (twai_receive(&received, pdMS_TO_TICKS(20)) == ESP_OK &&
                !received.extd && !received.rtr && received.identifier == sent.identifier &&
                received.data_length_code == 8 && memcmp(sent.data, received.data, 8) == 0) {
                matched = true;
                break;
            }
        }
        if (matched) ++passed;
        uint32_t alerts = 0;
        twai_read_alerts(&alerts, 0);
        if (alerts & (TWAI_ALERT_BUS_ERROR | TWAI_ALERT_TX_FAILED | TWAI_ALERT_BUS_OFF)) clean = false;
        twai_status_info_t status = {};
        const auto statusErr = twai_get_status_info(&status);
        Serial.printf("TEST %u enqueue=%s self_rx=%s alerts=0x%08lx RX_PIN=%d\n",
                      i + 1, esp_err_to_name(err), matched ? "MATCH" : "MISSING",
                      (unsigned long)alerts, digitalRead(19));
        if (statusErr == ESP_OK) {
            if (status.tx_error_counter || status.rx_error_counter || status.tx_failed_count ||
                status.bus_error_count || status.rx_missed_count || status.rx_overrun_count) clean = false;
            Serial.printf("BUS state=%d TEC=%lu REC=%lu failed=%lu errors=%lu pending=%lu\n",
                          int(status.state), (unsigned long)status.tx_error_counter,
                          (unsigned long)status.rx_error_counter, (unsigned long)status.tx_failed_count,
                          (unsigned long)status.bus_error_count, (unsigned long)status.msgs_to_tx);
        } else clean = false;
        delay(100);
    }
    twai_stop();
    twai_driver_uninstall();
    Serial.printf("RESULT %s %u/5 matching frames, errors=%s; this is NOT a remote-node ACK test.\n",
                  passed == 5 && clean ? "PASS" : "FAIL", passed, clean ? "NONE" : "PRESENT");
    Serial.println("DONE: controller stopped. Restore sender firmware for normal operation.");
}

void loop() { delay(1000); }
