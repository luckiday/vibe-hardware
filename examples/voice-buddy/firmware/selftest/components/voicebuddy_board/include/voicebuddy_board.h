// voicebuddy_board — the selftest BSP. The ONE place pin numbers + low-level
// init live (config-as-code mirroring ../../../../pcb/pinmap.yaml; the xiaozhi
// port's config.h mirrors the same file and plm_check cross-checks it).
#pragma once

#include <stdbool.h>
#include <driver/gpio.h>

#define BOARD_PIN_I2C_SDA      GPIO_NUM_1
#define BOARD_PIN_I2C_SCL      GPIO_NUM_2
#define BOARD_PIN_I2S_MCLK     GPIO_NUM_38
#define BOARD_PIN_I2S_BCLK     GPIO_NUM_14
#define BOARD_PIN_I2S_WS       GPIO_NUM_13
#define BOARD_PIN_I2S_DOUT     GPIO_NUM_45
#define BOARD_PIN_I2S_DIN      GPIO_NUM_12
#define BOARD_PIN_PA_EN        GPIO_NUM_10
#define BOARD_PIN_BTN_BOOT     GPIO_NUM_0
#define BOARD_PIN_BTN_VOLUP    GPIO_NUM_40
#define BOARD_PIN_BTN_VOLDN    GPIO_NUM_39
#define BOARD_PIN_LED          GPIO_NUM_48

#define BOARD_I2C_ADDR_ES8311  0x18
#define BOARD_I2C_ADDR_ES7210  0x41
#define BOARD_I2C_ADDR_SSD1306 0x3C

// init I2C bus + button/PA/LED GPIO; PA_EN driven LOW (amp muted)
void board_init(void);

// true if the 7-bit address ACKs
bool board_i2c_probe(uint8_t addr);

// read one 8-bit register (returns -1 on error)
int board_i2c_read_reg(uint8_t addr, uint8_t reg);

// buttons are active-low
bool board_btn(gpio_num_t pin);

// WS2812 status led
void board_led(uint8_t r, uint8_t g, uint8_t b);

// the shared bus handle (for the OLED test)
void *board_i2c_bus(void);
