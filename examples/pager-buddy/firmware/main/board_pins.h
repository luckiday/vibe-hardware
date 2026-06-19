#pragma once
// board_pins.h — pager-buddy config-as-code for M5StickC S3 (ESP32-S3-PICO-1-N8R8).
// Mirrors ../../pcb/pinmap.yaml (the pcb->firmware contract). Source: M5Stack StickS3
// docs https://docs.m5stack.com/en/core/StickS3. Keep both in sync; bump `revision`
// in ../../product.yaml on any change. Pins are plain GPIO numbers.

// --- Display: ST7789P3, 135x240, SPI ---
#define PIN_LCD_MOSI   39
#define PIN_LCD_SCLK   40
#define PIN_LCD_DC     45   // RS
#define PIN_LCD_CS     41
#define PIN_LCD_RST    21
#define PIN_LCD_BL     38   // backlight
#define LCD_H_RES      135
#define LCD_V_RES      240

// --- Buttons (active-low: pressed == 0) ---
#define PIN_BTN_A      11   // KEY1 (front) — pager ACK / silence
#define PIN_BTN_B      12   // KEY2 (side)

// --- I2C bus (IMU + PMIC + audio codec share it) ---
#define PIN_I2C_SDA    47
#define PIN_I2C_SCL    48
#define I2C_ADDR_IMU   0x68 // BMI270
#define I2C_ADDR_PMIC  0x6e // M5PM1
#define I2C_ADDR_CODEC 0x18 // ES8311

// --- Audio: ES8311 codec + AW8737 amp, I2S (the pager "buzz") ---
#define PIN_I2S_MCLK   18
#define PIN_I2S_BCLK   17
#define PIN_I2S_LRCK   15
#define PIN_I2S_DOUT   14   // to codec (speaker)
#define PIN_I2S_DIN    16   // from codec (mic)

// --- IR (RMT peripheral) ---
#define PIN_IR_TX      46
#define PIN_IR_RX      42

// --- Grove HY2.0-4P ---
#define PIN_GROVE_A    9    // yellow
#define PIN_GROVE_B    10   // white

// --- Battery monitor ---
#define PIN_BAT_ADC    44
