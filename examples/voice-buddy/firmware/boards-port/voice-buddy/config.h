// voice-buddy — xiaozhi board port: hardware config (config-as-code).
//
// THE one place pin numbers live on the firmware side. Mirrors
// ../../..../pcb/pinmap.yaml — every macro here is named by a pinmap entry's
// `define:` key, and vibe-plm's plm_check.py cross-checks the two. Change a
// pin on the board -> change pinmap.yaml -> change here -> bump product
// revision. Never edit just one side.

#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

// --- audio: ES8311 (DAC->NS4150->4ohm speaker) + ES7210 (2 mics + echo ref)
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000
#define AUDIO_INPUT_REFERENCE    true   // ES7210 ch3 carries the amp feedback -> server AEC

#define AUDIO_I2S_GPIO_MCLK GPIO_NUM_38
#define AUDIO_I2S_GPIO_WS   GPIO_NUM_13
#define AUDIO_I2S_GPIO_BCLK GPIO_NUM_14
#define AUDIO_I2S_GPIO_DIN  GPIO_NUM_12  // <- ES7210 SDOUT
#define AUDIO_I2S_GPIO_DOUT GPIO_NUM_45  // -> ES8311 DSDIN (strap pin, see pinmap note)

#define AUDIO_CODEC_PA_PIN       GPIO_NUM_10  // NS4150 CTRL: low until codec is up (anti-pop)
#define AUDIO_CODEC_I2C_SDA_PIN  GPIO_NUM_1   // shared bus: ES8311 + ES7210 + SSD1306
#define AUDIO_CODEC_I2C_SCL_PIN  GPIO_NUM_2
#define AUDIO_CODEC_ES8311_ADDR  ES8311_CODEC_DEFAULT_ADDR  // 7-bit 0x18
#define AUDIO_CODEC_ES7210_ADDR  ES7210_CODEC_DEFAULT_ADDR  // 7-bit 0x41

// --- display: SSD1306 128x64 I2C module on the shared bus (addr 0x3C)
#define DISPLAY_WIDTH    128
#define DISPLAY_HEIGHT   64
#define DISPLAY_MIRROR_X true
#define DISPLAY_MIRROR_Y true

// --- inputs / led
#define BOOT_BUTTON_GPIO        GPIO_NUM_0   // strap pin IS the main button
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_40
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_39
#define BUILTIN_LED_GPIO        GPIO_NUM_48  // WS2812B data

#endif  // _BOARD_CONFIG_H_
