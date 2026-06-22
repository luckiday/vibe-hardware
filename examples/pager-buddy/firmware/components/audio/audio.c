#include "audio.h"

#include <math.h>
#include <stdatomic.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/i2s_std.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "nvs.h"
#include "nvs_flash.h"

#include "stick_s3_board.h"

static const char *TAG = "audio";

#define AUDIO_SAMPLE_RATE 16000
#define GEN_CHUNK         256          // samples per esp_codec_dev_write
#define QUEUE_DEPTH       4
#define NVS_NS            "audio"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ── config (shared with the BLE/main context) ────────────────────────────────────
static volatile bool s_enabled = true;   // default on
static volatile int  s_volume  = 60;     // 0..100, default 60

// ── codec / i2s resources (created on demand around each alert; silent + low-power
//    between alerts, like voicestick's per-session lifecycle) ──────────────────────
static i2s_chan_handle_t           s_tx;
static esp_codec_dev_handle_t      s_codec;
static const audio_codec_ctrl_if_t *s_ctrl_if;
static const audio_codec_data_if_t *s_data_if;
static const audio_codec_gpio_if_t *s_gpio_if;
static const audio_codec_if_t      *s_codec_if;

static QueueHandle_t      s_queue;
static esp_pm_lock_handle_t s_pm;        // held only while a tone plays (no I²S glitch)
static atomic_bool        s_abort;       // set by audio_stop() to cut playback short

// ── NVS persistence ──────────────────────────────────────────────────────────────
static void nvs_load(void) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) != ESP_OK) return;
    uint8_t v;
    if (nvs_get_u8(h, "en",  &v) == ESP_OK) s_enabled = (v != 0);
    if (nvs_get_u8(h, "vol", &v) == ESP_OK) s_volume  = (v > 100) ? 100 : v;
    nvs_close(h);
}
static void nvs_save(void) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) != ESP_OK) return;
    nvs_set_u8(h, "en",  s_enabled ? 1 : 0);
    nvs_set_u8(h, "vol", (uint8_t)s_volume);
    nvs_commit(h);
    nvs_close(h);
}

// ── codec bring-up (DAC/output) — mirrors voicestick init but tx + WORK_MODE_DAC ──
static esp_err_t prepare(void) {
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    chan_cfg.auto_clear = true;          // feed zeros when idle → no DMA underrun noise
    ESP_RETURN_ON_ERROR(i2s_new_channel(&chan_cfg, &s_tx, NULL), TAG, "i2s channel");

    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,
                                                        I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = BOARD_PIN_ES8311_MCLK,
            .bclk = BOARD_PIN_ES8311_BCLK,
            .ws   = BOARD_PIN_ES8311_LRCK,
            .dout = BOARD_PIN_ES8311_DIN,   // MCU → codec (speaker path)
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = {0},
        },
    };
    std_cfg.clk_cfg.mclk_multiple = I2S_MCLK_MULTIPLE_256;
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(s_tx, &std_cfg), TAG, "i2s std");
    ESP_RETURN_ON_ERROR(i2s_channel_enable(s_tx), TAG, "i2s enable");

    i2c_master_bus_handle_t bus = board_i2c_bus();
    ESP_RETURN_ON_FALSE(bus, ESP_ERR_INVALID_STATE, TAG, "i2c bus unavailable");
    audio_codec_i2c_cfg_t i2c_cfg = {
        .port = I2C_NUM_0,                       // the board's shared bus
        .addr = ES8311_CODEC_DEFAULT_ADDR,       // 0x18 << 1
        .bus_handle = bus,
    };
    s_ctrl_if = audio_codec_new_i2c_ctrl(&i2c_cfg);
    ESP_RETURN_ON_FALSE(s_ctrl_if, ESP_ERR_NO_MEM, TAG, "codec i2c ctrl");

    audio_codec_i2s_cfg_t i2s_data = { .port = I2S_NUM_1, .tx_handle = s_tx, .rx_handle = NULL };
    s_data_if = audio_codec_new_i2s_data(&i2s_data);
    ESP_RETURN_ON_FALSE(s_data_if, ESP_ERR_NO_MEM, TAG, "codec i2s data");

    s_gpio_if = audio_codec_new_gpio();
    ESP_RETURN_ON_FALSE(s_gpio_if, ESP_ERR_NO_MEM, TAG, "codec gpio");

    es8311_codec_cfg_t es_cfg = {
        .ctrl_if     = s_ctrl_if,
        .gpio_if     = s_gpio_if,
        .codec_mode  = ESP_CODEC_DEV_WORK_MODE_DAC,
        .pa_pin      = -1,                 // AW8737 enable is a PMIC pin (M5PM1 G3), not a
                                           // GPIO → board_audio_amp() drives it, not the codec
        .pa_reverted = false,
        .master_mode = false,
        .use_mclk    = true,
        .digital_mic = false,
        .invert_mclk = false,
        .invert_sclk = false,
        .hw_gain = { .pa_voltage = 5.0, .codec_dac_voltage = 3.3 },
    };
    s_codec_if = es8311_codec_new(&es_cfg);
    ESP_RETURN_ON_FALSE(s_codec_if, ESP_ERR_NO_MEM, TAG, "es8311");

    esp_codec_dev_cfg_t dev_cfg = {
        .dev_type = ESP_CODEC_DEV_TYPE_OUT,
        .codec_if = s_codec_if,
        .data_if  = s_data_if,
    };
    s_codec = esp_codec_dev_new(&dev_cfg);
    ESP_RETURN_ON_FALSE(s_codec, ESP_ERR_NO_MEM, TAG, "codec dev");

    esp_codec_dev_sample_info_t sample = {
        .bits_per_sample = 16,
        .channel = 1,
        .channel_mask = I2S_STD_SLOT_LEFT,   // mono on the left slot (matches voicestick)
        .sample_rate = AUDIO_SAMPLE_RATE,
        .mclk_multiple = 0,
    };
    ESP_RETURN_ON_FALSE(esp_codec_dev_open(s_codec, &sample) == ESP_CODEC_DEV_OK,
                        ESP_FAIL, TAG, "codec open");
    esp_codec_dev_set_out_vol(s_codec, s_volume);   // 0..100

    // Power the speaker amp LAST — only now is the I²S line driving silence (auto_clear),
    // so enabling the AW8737 here (via M5PM1 G3) doesn't latch onto a floating input.
    // Short settle so the amp is up before the first sample (mirrors xiaozhi's delay).
    board_audio_amp(true);
    vTaskDelay(pdMS_TO_TICKS(30));
    return ESP_OK;
}

static void release(void) {
    board_audio_amp(false);     // mute the amp BEFORE tearing down I²S (avoids a pop)
    if (s_codec)    { esp_codec_dev_close(s_codec); esp_codec_dev_delete(s_codec); s_codec = NULL; }
    if (s_codec_if) { audio_codec_delete_codec_if(s_codec_if); s_codec_if = NULL; }
    if (s_data_if)  { audio_codec_delete_data_if(s_data_if);   s_data_if = NULL; }
    if (s_gpio_if)  { audio_codec_delete_gpio_if(s_gpio_if);   s_gpio_if = NULL; }
    if (s_ctrl_if)  { audio_codec_delete_ctrl_if(s_ctrl_if);   s_ctrl_if = NULL; }
    if (s_tx)       { i2s_channel_disable(s_tx); i2s_del_channel(s_tx); s_tx = NULL; }
}

// Generate a frequency glide f0→f1 (f0==f1 ⇒ steady tone) for `ms`.
// Synthesis: fundamental + 2× harmonic (0.72·sin(f) + 0.22·sin(2f)) for warmth.
// Envelope: 8ms attack, 40ms decay tail, for natural chime-like release.
// Bails early on audio_stop().
static void gen(double f0, double f1, int ms) {
    if (!s_codec) return;
    const int total  = AUDIO_SAMPLE_RATE * ms / 1000;
    const int attack = AUDIO_SAMPLE_RATE * 8  / 1000;
    const int decay  = AUDIO_SAMPLE_RATE * 40 / 1000;
    static int16_t buf[GEN_CHUNK];
    double phase1 = 0, phase2 = 0;
    int done = 0;
    while (done < total && !atomic_load(&s_abort)) {
        int n = total - done; if (n > GEN_CHUNK) n = GEN_CHUNK;
        for (int i = 0; i < n; i++) {
            int pos = done + i;
            double frac = (double)pos / total;
            double f = f0 + (f1 - f0) * frac;
            phase1 += 2.0 * M_PI * f       / AUDIO_SAMPLE_RATE;
            phase2 += 2.0 * M_PI * (f*2.0) / AUDIO_SAMPLE_RATE;
            if (phase1 > 2.0*M_PI) phase1 -= 2.0*M_PI;
            if (phase2 > 2.0*M_PI) phase2 -= 2.0*M_PI;
            double env;
            if      (pos < attack)           env = (double)pos / attack;
            else if (pos > total - decay)    env = (double)(total - pos) / decay;
            else                             env = 1.0;
            buf[i] = (int16_t)(0.62 * 32767.0 * env *
                               (0.72*sin(phase1) + 0.22*sin(phase2)));
        }
        esp_codec_dev_write(s_codec, buf, n * sizeof(int16_t));
        done += n;
    }
}

static void play_pattern(audio_alert_t kind) {
    switch (kind) {
    case AUDIO_ALERT_WAITING:                 // urgent ascending ding-ding (A5→E6 perfect fifth)
        gen(880, 880, 90);
        if (!atomic_load(&s_abort)) { vTaskDelay(pdMS_TO_TICKS(55)); gen(1320, 1320, 125); }
        break;
    case AUDIO_ALERT_ASKING:                  // rising question glide (A5→D6)
        gen(880, 1175, 310);
        break;
    case AUDIO_ALERT_DONE:                    // satisfying major-chord build (C5→E5→A5)
        gen(523, 523, 75);
        if (!atomic_load(&s_abort)) { vTaskDelay(pdMS_TO_TICKS(25)); gen(659, 659, 75); }
        if (!atomic_load(&s_abort)) { vTaskDelay(pdMS_TO_TICKS(25)); gen(880, 880, 130); }
        break;
    }
}

static void audio_task(void *arg) {
    (void)arg;
    audio_alert_t kind;
    for (;;) {
        if (xQueueReceive(s_queue, &kind, portMAX_DELAY) != pdTRUE) continue;
        if (!s_enabled) continue;
        atomic_store(&s_abort, false);
        if (s_pm) esp_pm_lock_acquire(s_pm);
        if (prepare() == ESP_OK) {
            play_pattern(kind);
        } else {
            ESP_LOGW(TAG, "codec prepare failed — no sound");
        }
        release();
        if (s_pm) esp_pm_lock_release(s_pm);
    }
}

// ── public API ───────────────────────────────────────────────────────────────────
esp_err_t audio_init(void) {
    esp_err_t err = nvs_flash_init();        // idempotent: bridge_start may have run it
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        err = nvs_flash_init();
    }
    nvs_load();

    s_queue = xQueueCreate(QUEUE_DEPTH, sizeof(audio_alert_t));
    if (!s_queue) return ESP_ERR_NO_MEM;
    // Best-effort PM lock so light sleep can't glitch I²S mid-tone (like the screen lock).
    esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "audio", &s_pm);

    BaseType_t ok = xTaskCreate(audio_task, "audio", 4096, NULL, 5, NULL);
    if (ok != pdPASS) { vQueueDelete(s_queue); s_queue = NULL; return ESP_ERR_NO_MEM; }

    ESP_LOGI(TAG, "ready — audio %s, volume %d", s_enabled ? "on" : "off", s_volume);
    return ESP_OK;
}

void audio_alert(audio_alert_t kind) {
    if (!s_enabled || !s_queue) return;
    xQueueSend(s_queue, &kind, 0);   // drop if full — a missed beep is fine
}

void audio_stop(void) {
    atomic_store(&s_abort, true);
    if (s_queue) xQueueReset(s_queue);
}

void audio_set_enabled(bool on) {
    if (on == s_enabled) return;
    s_enabled = on;
    if (!on) audio_stop();
    nvs_save();
    ESP_LOGI(TAG, "audio %s", on ? "enabled" : "disabled");
}

void audio_set_volume(int vol) {
    if (vol < 0) vol = 0; else if (vol > 100) vol = 100;
    if (vol == s_volume) return;
    s_volume = vol;
    if (s_codec) esp_codec_dev_set_out_vol(s_codec, s_volume);   // live if mid-tone
    nvs_save();
    ESP_LOGI(TAG, "volume %d", vol);
}

bool audio_enabled(void) { return s_enabled; }
int  audio_volume(void)  { return s_volume; }
