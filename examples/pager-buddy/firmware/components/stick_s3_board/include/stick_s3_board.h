#pragma once
// Board-support layer (BSP) for the M5StickC S3 (ESP32-S3-PICO-1-N8R8).
//
// The ONE place pin numbers + low-level init live (config-as-code mirroring
// ../../../pcb/pinmap.yaml). board_init() brings up the shared I2C bus, powers the
// LCD rail via the M5PM1 PMIC (without this the screen stays dark), and configures
// the two buttons. Nothing outside this component touches a raw GPIO or the PMIC.

#include <stdbool.h>
#include "esp_err.h"
#include "driver/i2c_master.h"

// --- pins (mirror pcb/pinmap.yaml) ---
#define BOARD_PIN_BTN_FRONT 11   // KEY1 (blue, front) — OK / hold = back
#define BOARD_PIN_BTN_SIDE  12   // KEY2 (side)        — scroll / cycle
#define BOARD_PIN_I2C_SDA   47
#define BOARD_PIN_I2C_SCL   48
#define BOARD_PIN_LCD_MOSI  39
#define BOARD_PIN_LCD_SCLK  40
#define BOARD_PIN_LCD_DC    45   // RS
#define BOARD_PIN_LCD_CS    41
#define BOARD_PIN_LCD_RST   21
#define BOARD_PIN_LCD_BL    38   // backlight

// --- audio (ES8311 codec + AW8737 amp over I²S; mirror pcb/pinmap.yaml) ---
// Pin names follow the codec's perspective:
//   ES8311_DIN  = codec serial data input  (DSDIN, MCU → codec, speaker path) = GPIO14
//   ES8311_DOUT = codec serial data output (ASDOUT, codec → MCU, mic path)    = GPIO16
#define BOARD_PIN_ES8311_MCLK 18
#define BOARD_PIN_ES8311_BCLK 17
#define BOARD_PIN_ES8311_LRCK 15
#define BOARD_PIN_ES8311_DIN  14
#define BOARD_PIN_ES8311_DOUT 16
#define BOARD_ES8311_I2C_ADDR 0x18

// Bring up I2C + PMIC (LCD power rail) + buttons. Call once, before ui_init().
esp_err_t board_init(void);

// The shared I2C master bus (IMU + PMIC + ES8311 codec live on it). Valid after
// board_init(); NULL if I2C init failed. The audio component needs it for ES8311
// codec control. (Mirrors voicestick's stick_s3_board_i2c_bus.)
i2c_master_bus_handle_t board_i2c_bus(void);

// Enable/disable the speaker power amp (AW8737). On the StickC S3 the PA enable is
// NOT an ESP32 GPIO — it's M5PM1 PMIC GPIO3 (per the xiaozhi-esp32 m5stack-stick-s3
// board). The audio component gates it to the playback window so the amp isn't
// powered into a floating I²S line (which hisses) between tones. No-op if the PMIC
// is absent. Best-effort; the codec's own pa_pin stays -1.
void board_audio_amp(bool on);

// Buttons (active-low; true = pressed).
bool board_btn_front(void);
bool board_btn_side(void);

// Battery / power via the M5PM1 PMIC (ESP_OK on success; safe to ignore for now).
esp_err_t board_battery_level(int *percent);     // 0..100
esp_err_t board_battery_charging(bool *charging);
esp_err_t board_usb_powered(bool *usb_powered);
