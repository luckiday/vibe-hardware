#include "stick_s3_board.h"

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

static const char *TAG = "board";

static i2c_master_bus_handle_t s_bus;
static i2c_master_dev_handle_t s_pmic;

// --- M5PM1 PMIC register map (hardware interface for the StickC S3) ---
#define PMIC_ADDR        0x6e
#define R_DEVID          0x00
#define R_PWR_CFG        0x06
#define R_HOLD_CFG       0x07
#define R_I2C_CFG        0x09
#define R_GPIO_MODE      0x10
#define R_GPIO_OUT       0x11
#define R_GPIO_IN        0x12
#define R_GPIO_DRV       0x13
#define R_GPIO_FUNC0     0x16
#define R_BAT_L          0x22
#define R_VIN_L          0x24
#define PWR_LDO_EN       (1 << 2)
#define PWR_LED_CTRL     (1 << 4)
#define HOLD_LDO         (1 << 5)
#define LCD_RAIL_GPIO    (1 << 2)   // M5PM1 GPIO2 gates the LCD (L3B) rail
#define CHG_SENSE_GPIO   (1 << 0)   // M5PM1 GPIO0 = charge sense input
#define PA_EN_GPIO       (1 << 3)   // M5PM1 GPIO3 enables the AW8737 speaker amp (PA)

static esp_err_t reg_rd(uint8_t reg, uint8_t *v) {
    return i2c_master_transmit_receive(s_pmic, &reg, 1, v, 1, 100);
}
static esp_err_t reg_rd16(uint8_t reg, uint8_t *v /* [2] */) {
    return i2c_master_transmit_receive(s_pmic, &reg, 1, v, 2, 100);
}
static esp_err_t reg_wr(uint8_t reg, uint8_t v) {
    const uint8_t d[2] = {reg, v};
    return i2c_master_transmit(s_pmic, d, sizeof(d), 100);
}
static esp_err_t reg_upd(uint8_t reg, uint8_t clear, uint8_t set) {
    uint8_t v = 0;
    esp_err_t e = reg_rd(reg, &v);
    if (e != ESP_OK) return e;
    v = (v & ~clear) | set;
    return reg_wr(reg, v);
}

static esp_err_t init_i2c(void) {
    const i2c_master_bus_config_t bus = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = BOARD_PIN_I2C_SDA,
        .scl_io_num = BOARD_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    esp_err_t e = i2c_new_master_bus(&bus, &s_bus);
    if (e != ESP_OK) return e;

    const i2c_device_config_t dev = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = PMIC_ADDR,
        .scl_speed_hz = 100000,
    };
    return i2c_master_bus_add_device(s_bus, &dev, &s_pmic);
}

// Enable the LDO and drive M5PM1 GPIO2 high to power the LCD rail. Without this the
// panel never lights. Also set GPIO0 as an input for charge sensing.
static void power_on_lcd_rail(void) {
    uint8_t id = 0;
    if (reg_rd(R_DEVID, &id) != ESP_OK) {
        ESP_LOGW(TAG, "M5PM1 not found at 0x%02x", PMIC_ADDR);
        return;
    }
    reg_upd(R_PWR_CFG, PWR_LED_CTRL, PWR_LDO_EN);  // LDO on
    reg_upd(R_HOLD_CFG, 0, HOLD_LDO);              // hold across resets
    reg_upd(R_GPIO_FUNC0, LCD_RAIL_GPIO, 0);       // GPIO2 = plain GPIO
    reg_upd(R_GPIO_MODE, 0, LCD_RAIL_GPIO);        // GPIO2 = output
    reg_upd(R_GPIO_DRV, LCD_RAIL_GPIO, 0);         // push-pull
    reg_upd(R_GPIO_OUT, 0, LCD_RAIL_GPIO);         // drive high → rail on
    reg_wr(R_I2C_CFG, 0x00);
    reg_upd(R_GPIO_FUNC0, CHG_SENSE_GPIO, 0);      // GPIO0 = plain GPIO
    reg_upd(R_GPIO_MODE, CHG_SENSE_GPIO, 0);       // GPIO0 = input
    ESP_LOGI(TAG, "M5PM1 id=0x%02x — LCD rail on", id);
}

esp_err_t board_init(void) {
    esp_err_t e = init_i2c();
    if (e == ESP_OK) {
        power_on_lcd_rail();
    } else {
        ESP_LOGW(TAG, "I2C init failed: %s (LCD may stay dark)", esp_err_to_name(e));
    }

    const gpio_config_t btn = {
        .pin_bit_mask = (1ULL << BOARD_PIN_BTN_FRONT) | (1ULL << BOARD_PIN_BTN_SIDE),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    return gpio_config(&btn);
}

bool board_btn_front(void) { return gpio_get_level(BOARD_PIN_BTN_FRONT) == 0; }
bool board_btn_side(void) { return gpio_get_level(BOARD_PIN_BTN_SIDE) == 0; }

i2c_master_bus_handle_t board_i2c_bus(void) { return s_bus; }

// Enable/disable the AW8737 speaker amp via M5PM1 GPIO3 (push-pull, high = on). Same
// register dance as the LCD rail on GPIO2; the codec's pa_pin stays -1 because the PA
// is a PMIC pin, not an ESP32 GPIO (per xiaozhi-esp32 m5stack-stick-s3). Best-effort.
void board_audio_amp(bool on) {
    if (!s_pmic) return;
    reg_upd(R_GPIO_FUNC0, PA_EN_GPIO, 0);   // GPIO3 = plain GPIO
    reg_upd(R_GPIO_MODE, 0, PA_EN_GPIO);    // output
    reg_upd(R_GPIO_DRV, PA_EN_GPIO, 0);     // push-pull
    reg_upd(R_GPIO_OUT, on ? 0 : PA_EN_GPIO, on ? PA_EN_GPIO : 0);  // high → amp on
}

static esp_err_t read_mv(uint8_t reg, int *mv) {
    if (!s_pmic) return ESP_ERR_INVALID_STATE;
    uint8_t d[2] = {0};
    esp_err_t e = reg_rd16(reg, d);
    if (e != ESP_OK) return e;
    *mv = (d[1] << 8) | d[0];
    return ESP_OK;
}

esp_err_t board_battery_level(int *percent) {
    if (!percent) return ESP_ERR_INVALID_ARG;
    int mv = 0;
    esp_err_t e = read_mv(R_BAT_L, &mv);
    if (e != ESP_OK) return e;
    int level = (mv - 3300) * 100 / (4150 - 3350);
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    *percent = level;
    return mv > 0 ? ESP_OK : ESP_FAIL;
}

esp_err_t board_battery_charging(bool *charging) {
    if (!charging) return ESP_ERR_INVALID_ARG;
    if (!s_pmic) return ESP_ERR_INVALID_STATE;
    uint8_t gpio_in = 0;
    esp_err_t e = reg_rd(R_GPIO_IN, &gpio_in);
    if (e != ESP_OK) return e;
    *charging = (gpio_in & CHG_SENSE_GPIO) == 0;
    return ESP_OK;
}

esp_err_t board_usb_powered(bool *usb_powered) {
    if (!usb_powered) return ESP_ERR_INVALID_ARG;
    int mv = 0;
    esp_err_t e = read_mv(R_VIN_L, &mv);
    if (e != ESP_OK) return e;
    *usb_powered = mv > 4500;
    return ESP_OK;
}

// Drive M5PM1 GPIO2 low to power down the LCD rail (the inverse of power_on_lcd_rail).
// Called right before esp_deep_sleep_start() so the panel + backlight rail draws
// nothing while the chip sleeps. Best-effort: if the PMIC is absent, do nothing.
void board_prepare_deep_sleep(void) {
    if (!s_pmic) return;
    reg_upd(R_GPIO_OUT, PA_EN_GPIO, 0);      // GPIO3 low → speaker amp off
    reg_upd(R_GPIO_OUT, LCD_RAIL_GPIO, 0);   // GPIO2 low → rail off
    reg_upd(R_GPIO_DRV, LCD_RAIL_GPIO, 0);   // release the push-pull driver too
}
