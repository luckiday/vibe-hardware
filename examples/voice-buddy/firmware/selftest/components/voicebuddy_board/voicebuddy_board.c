// voicebuddy_board — selftest BSP implementation (ESP-IDF v5.4 APIs).
#include "voicebuddy_board.h"

#include <driver/i2c_master.h>
#include <esp_log.h>
#include <led_strip.h>

static const char *TAG = "vb_board";
static i2c_master_bus_handle_t s_bus;
static led_strip_handle_t s_led;

void board_init(void)
{
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = 0,
        .sda_io_num = BOARD_PIN_I2C_SDA,
        .scl_io_num = BOARD_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags = { .enable_internal_pullup = 1 },   // board has 4.7k externals
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &s_bus));

    // amp OFF for the whole selftest (pop-free bring-up)
    gpio_config_t pa = { .pin_bit_mask = 1ULL << BOARD_PIN_PA_EN,
                         .mode = GPIO_MODE_OUTPUT };
    gpio_config(&pa);
    gpio_set_level(BOARD_PIN_PA_EN, 0);

    gpio_config_t btn = {
        .pin_bit_mask = (1ULL << BOARD_PIN_BTN_BOOT) |
                        (1ULL << BOARD_PIN_BTN_VOLUP) |
                        (1ULL << BOARD_PIN_BTN_VOLDN),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    gpio_config(&btn);

    led_strip_config_t strip_cfg = {
        .strip_gpio_num = BOARD_PIN_LED,
        .max_leds = 1,
    };
    led_strip_rmt_config_t rmt_cfg = { .resolution_hz = 10 * 1000 * 1000 };
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &s_led));
    board_led(0, 0, 0);
    ESP_LOGI(TAG, "board init done (PA muted)");
}

bool board_i2c_probe(uint8_t addr)
{
    return i2c_master_probe(s_bus, addr, 50) == ESP_OK;
}

int board_i2c_read_reg(uint8_t addr, uint8_t reg)
{
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = addr,
        .scl_speed_hz = 100000,
    };
    i2c_master_dev_handle_t dev;
    if (i2c_master_bus_add_device(s_bus, &dev_cfg, &dev) != ESP_OK) {
        return -1;
    }
    uint8_t val = 0;
    esp_err_t err = i2c_master_transmit_receive(dev, &reg, 1, &val, 1, 100);
    i2c_master_bus_rm_device(dev);
    return err == ESP_OK ? val : -1;
}

bool board_btn(gpio_num_t pin)
{
    return gpio_get_level(pin) == 0;
}

void board_led(uint8_t r, uint8_t g, uint8_t b)
{
    led_strip_set_pixel(s_led, 0, r, g, b);
    led_strip_refresh(s_led);
}

void *board_i2c_bus(void)
{
    return s_bus;
}
