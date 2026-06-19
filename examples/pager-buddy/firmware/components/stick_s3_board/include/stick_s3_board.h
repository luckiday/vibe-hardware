#pragma once
// Board-support layer (BSP) for the M5StickC S3 (ESP32-S3-PICO-1-N8R8).
//
// The ONE place pin numbers + low-level init live (config-as-code mirroring
// ../../../pcb/pinmap.yaml). board_init() brings up the shared I2C bus, powers the
// LCD rail via the M5PM1 PMIC (without this the screen stays dark), and configures
// the two buttons. Nothing outside this component touches a raw GPIO or the PMIC.

#include <stdbool.h>
#include "esp_err.h"

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

// Bring up I2C + PMIC (LCD power rail) + buttons. Call once, before ui_init().
esp_err_t board_init(void);

// Buttons (active-low; true = pressed).
bool board_btn_front(void);
bool board_btn_side(void);

// Battery / power via the M5PM1 PMIC (ESP_OK on success; safe to ignore for now).
esp_err_t board_battery_level(int *percent);     // 0..100
esp_err_t board_battery_charging(bool *charging);
esp_err_t board_usb_powered(bool *usb_powered);
