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

// --- audio: single ES8388 duplex codec (DAC->NS4150->4ohm speaker; ADC L = mic,
//     ADC R = amp echo reference -> hardware AEC, the yunliao-s3 pattern)
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000
#define AUDIO_INPUT_REFERENCE    true   // ES8388 R-ADC carries the amp feedback -> AEC

#define AUDIO_I2S_GPIO_MCLK GPIO_NUM_17
#define AUDIO_I2S_GPIO_BCLK GPIO_NUM_18
#define AUDIO_I2S_GPIO_WS   GPIO_NUM_8
#define AUDIO_I2S_GPIO_DOUT GPIO_NUM_9   // -> ES8388 DSDIN
#define AUDIO_I2S_GPIO_DIN  GPIO_NUM_10  // <- ES8388 ASDOUT

#define AUDIO_CODEC_PA_PIN       GPIO_NUM_13  // NS4150 CTRL: low until codec is up (anti-pop)
#define AUDIO_CODEC_I2C_SDA_PIN  GPIO_NUM_11  // shared bus: ES8388 + SSD1306
#define AUDIO_CODEC_I2C_SCL_PIN  GPIO_NUM_12
#define AUDIO_CODEC_ES8388_ADDR  ES8388_CODEC_DEFAULT_ADDR  // 7-bit 0x10 (CE low)

// --- display: SSD1306 128x64 I2C module on the shared bus (addr 0x3C)
#define DISPLAY_WIDTH    128
#define DISPLAY_HEIGHT   64
#define DISPLAY_MIRROR_X true
#define DISPLAY_MIRROR_Y true

// --- inputs / led
#define BOOT_BUTTON_GPIO        GPIO_NUM_0   // strap pin IS the main button
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_47
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_21
#define BUILTIN_LED_GPIO        GPIO_NUM_38  // WS2812B data

#endif  // _BOARD_CONFIG_H_
