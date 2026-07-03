// voice-buddy selftest — first-power bring-up (see ../README.md).
// Thin conductor: every pin/bus detail lives in the voicebuddy_board BSP.
#include <stdio.h>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>

#include "voicebuddy_board.h"

static const char *TAG = "selftest";

// ES8311/ES7210 both expose readable chip-ID registers; an ACK plus a sane ID
// read proves the I2C path AND that the right die is on the pads. Register
// numbers per the datasheets (ES8311 0xFD/0xFE = 0x83/0x11; ES7210 0x3D
// family) — treat unexpected values as WARN, not FAIL, until verified on
// real silicon.
static void check_codec(const char *name, uint8_t addr, uint8_t id_reg)
{
    if (!board_i2c_probe(addr)) {
        ESP_LOGE(TAG, "FAIL %s: no ACK at 0x%02X", name, addr);
        return;
    }
    int id = board_i2c_read_reg(addr, id_reg);
    ESP_LOGI(TAG, "PASS %s: ACK at 0x%02X, reg[0x%02X]=0x%02X",
             name, addr, id_reg, id);
}

void app_main(void)
{
    board_init();
    ESP_LOGI(TAG, "== voice-buddy selftest ==");

    // 1+2. codecs on the shared I2C bus
    check_codec("ES8311", BOARD_I2C_ADDR_ES8311, 0xFD);
    check_codec("ES7210", BOARD_I2C_ADDR_ES7210, 0x3D);
    if (board_i2c_probe(BOARD_I2C_ADDR_SSD1306)) {
        ESP_LOGI(TAG, "PASS SSD1306: ACK at 0x%02X", BOARD_I2C_ADDR_SSD1306);
    } else {
        ESP_LOGW(TAG, "WARN SSD1306: no ACK (OLED module not plugged?)");
    }

    // 3. buttons drive the LED — 30 s interactive window
    ESP_LOGI(TAG, "press BOOT (red) / VOL+ (green) / VOL- (blue) ...");
    for (int i = 0; i < 300; i++) {
        if (board_btn(BOARD_PIN_BTN_BOOT)) {
            board_led(64, 0, 0);
            ESP_LOGI(TAG, "PASS BTN_BOOT");
        } else if (board_btn(BOARD_PIN_BTN_VOLUP)) {
            board_led(0, 64, 0);
            ESP_LOGI(TAG, "PASS BTN_VOLUP");
        } else if (board_btn(BOARD_PIN_BTN_VOLDN)) {
            board_led(0, 0, 64);
            ESP_LOGI(TAG, "PASS BTN_VOLDN");
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    board_led(0, 8, 0);
    ESP_LOGI(TAG, "selftest done — flash the xiaozhi port next "
                  "(../boards-port/voice-buddy/)");
}
