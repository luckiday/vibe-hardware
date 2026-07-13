# voice-buddy — xiaozhi board port

A drop-in board definition for the MIT-licensed
[78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) AI-chatbot firmware.
The carrier hardware is this repo's `examples/voice-buddy` board: ESP32-S3-WROOM-1
(N16R8) + one ES8388 duplex codec (DAC → NS4150 → 4 Ω speaker; ADC L = analog
MEMS mic, ADC R = amp echo-reference for AEC) + SSD1306 OLED + 3 buttons + WS2812.

Pins live in `config.h` **only** — it mirrors `../../pcb/pinmap.yaml` and
`plm_check.py` fails the product gate if the two drift.

## Integrate into upstream (per upstream `docs/custom-board.md`)

1. Clone upstream at a **pinned tag** (record the tag you tested here — the
   board API evolves; this port was written against `main` as of 2026-07):

       git clone https://github.com/78/xiaozhi-esp32.git && cd xiaozhi-esp32

2. Copy this directory in:

       cp -r <vibe-hardware>/examples/voice-buddy/firmware/boards-port/voice-buddy main/boards/

3. Register the board type. In `main/Kconfig.projbuild`, inside
   `choice BOARD_TYPE`, add:

       config BOARD_TYPE_VOICE_BUDDY
           bool "voice-buddy (ES8388, SSD1306)"
           depends on IDF_TARGET_ESP32S3

   In `main/CMakeLists.txt`, in the board-type dispatch, add:

       elseif(CONFIG_BOARD_TYPE_VOICE_BUDDY)
           set(BOARD_TYPE "voice-buddy")

4. Build with the pinned toolchain (ESP-IDF ≥ 5.4; upstream's requirement):

       idf.py set-target esp32s3
       idf.py menuconfig        # Xiaozhi Assistant -> Board Type -> voice-buddy
       idf.py build flash monitor

   or, since `config.json` is present: `python scripts/release.py voice-buddy`.

## Status / gotchas

- **NOT yet compiled or hardware-tested** (`product.yaml` says `status: wip`);
  per the vibe-firmware rule, nothing ships until it runs on the real board.
- The OLED shares the codec I²C bus (0x3C vs 0x10). If the display is
  absent the board comes up headless instead of aborting.
- `AUDIO_INPUT_REFERENCE true`: the ES8388 right ADC carries the NS4150 output
  divider (into RIN1) — that is what gives the server usable AEC. Don't set it
  false. `Es8388AudioCodec` sets left PGA high (mic) and right PGA 0 dB (ref).
- PA_EN (GPIO13) is held low by the codec driver until the codec is configured —
  keep the NS4150 CTRL pulldown on the board so the amp stays silent at boot.
