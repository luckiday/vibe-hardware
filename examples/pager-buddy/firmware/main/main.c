// pager-buddy — stage-1 bring-up for the M5StickC S3 (ESP32-S3-PICO-1-N8R8).
//
// Proves the board is alive WITHOUT guessing at the PMIC/LCD init sequence:
//   - logs chip info (cores, flash, PSRAM, heap)
//   - turns the LCD backlight on (G38)
//   - configures the two buttons and reports them each heartbeat
//   - inits the shared I2C bus (SDA G47 / SCL G48) and scans it
//       -> expect BMI270 @0x68, M5PM1 @0x6e, ES8311 @0x18
//
// Pins come from board_pins.h (config-as-code, mirrors ../../pcb/pinmap.yaml).
// Next stages (see README): ST7789 display, ES8311 audio, Wi-Fi status client, OTA.

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "board_pins.h"

static const char *TAG = "pager-buddy";

static void log_chip_info(void)
{
    esp_chip_info_t info;
    esp_chip_info(&info);
    uint32_t flash_sz = 0;
    esp_flash_get_size(NULL, &flash_sz);
    size_t psram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);

    ESP_LOGI(TAG, "ESP32-S3 rev v%d.%d, %d core(s)",
             info.revision / 100, info.revision % 100, info.cores);
    ESP_LOGI(TAG, "flash: %lu MB   PSRAM: %u KB",
             (unsigned long)(flash_sz / (1024 * 1024)), (unsigned)(psram / 1024));
    ESP_LOGI(TAG, "free heap: %lu B", (unsigned long)esp_get_free_heap_size());
}

static void init_io(void)
{
    gpio_config_t btn = {
        .pin_bit_mask = (1ULL << PIN_BTN_A) | (1ULL << PIN_BTN_B),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&btn));

    gpio_config_t bl = {
        .pin_bit_mask = 1ULL << PIN_LCD_BL,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&bl));
    gpio_set_level(PIN_LCD_BL, 1);   // backlight on — visible proof of life
}

static i2c_master_bus_handle_t init_i2c(void)
{
    i2c_master_bus_config_t cfg = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .i2c_port = I2C_NUM_0,
        .sda_io_num = PIN_I2C_SDA,
        .scl_io_num = PIN_I2C_SCL,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    i2c_master_bus_handle_t bus = NULL;
    ESP_ERROR_CHECK(i2c_new_master_bus(&cfg, &bus));
    return bus;
}

static void i2c_scan(i2c_master_bus_handle_t bus)
{
    ESP_LOGI(TAG, "I2C scan on SDA=%d SCL=%d:", PIN_I2C_SDA, PIN_I2C_SCL);
    int found = 0;
    for (uint8_t addr = 1; addr < 0x7F; addr++) {
        if (i2c_master_probe(bus, addr, 50) == ESP_OK) {
            const char *name = addr == I2C_ADDR_IMU   ? "BMI270 (IMU)"
                             : addr == I2C_ADDR_PMIC  ? "M5PM1 (PMIC)"
                             : addr == I2C_ADDR_CODEC ? "ES8311 (audio)"
                             : "?";
            ESP_LOGI(TAG, "  0x%02X  %s", addr, name);
            found++;
        }
    }
    ESP_LOGI(TAG, "I2C scan done: %d device(s)", found);
}

void app_main(void)
{
    esp_err_t nvs = nvs_flash_init();
    if (nvs == ESP_ERR_NVS_NO_FREE_PAGES || nvs == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    ESP_LOGI(TAG, "=== pager-buddy bring-up (M5StickC S3) ===");
    log_chip_info();
    init_io();
    i2c_master_bus_handle_t bus = init_i2c();
    i2c_scan(bus);

    ESP_LOGI(TAG, "ready — heartbeat + button watch. Next: LCD + Wi-Fi status client.");
    while (1) {
        ESP_LOGI(TAG, "heap=%lu  KEY1=%d KEY2=%d",
                 (unsigned long)esp_get_free_heap_size(),
                 gpio_get_level(PIN_BTN_A) == 0,
                 gpio_get_level(PIN_BTN_B) == 0);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}
