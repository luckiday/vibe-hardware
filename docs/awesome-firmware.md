# Awesome firmware references

Curated firmware projects we study when building **vibe-hardware** devices — the
real, shipping ESP-IDF codebases that taught us the patterns in
[`skills/vibe-firmware`](../skills/vibe-firmware/SKILL.md). Each entry is the
*upstream link plus why it's worth reading*; the bulky third-party code itself is
**not** committed here.

## How to use these

The link is versioned (this file); the code is not. Every reference clones into the
**one** gitignored home — `references/_clones/` — and is read locally:

```bash
docs/references/clone.sh          # fetch every project below (depth-1) into _clones/
# …or one at a time:
git clone --depth 1 https://github.com/78/voicestick docs/references/_clones/voicestick
```

Everything under `_clones/` is gitignored — only the links + notes here are committed.

## The list

| Project | Board / scope | Framework | License | Why it's a reference |
|---|---|---|---|---|
| [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) · [notes](references/xiaozhi-esp32.md) | 70+ ESP32-C3 / S3 / P4 boards | ESP-IDF ≥ 5.4 | MIT | Production-grade, layered AI-voice firmware: WebSocket / MQTT+UDP protocols, OPUS audio, ESP-SR wake-word, LVGL UI, dual-slot OTA, battery / PM, MCP device control. The reference for *how a big ESP-IDF app stays modular*. |
| [espressif/esp-box](https://github.com/espressif/esp-box) · [notes](references/esp-box.md) | ESP32-S3-BOX / -BOX-3 / -Lite | ESP-IDF ≥ 5.1 | Apache-2.0 | Espressif's *official* AIoT firmware: 2.4" LVGL touchscreen + dual-mic far-field offline wake-word / 200+ commands, Matter / Home-Assistant. A clean, maintained counterpart to xiaozhi for display + audio + voice. |
| [espressif/esp-bsp](https://github.com/espressif/esp-bsp) · [notes](references/esp-bsp.md) | 25+ Espressif / M5Stack boards | ESP-IDF 5.2–6.0 | Apache-2.0 | The canonical **BSP pattern**: one board API over display (ST7789 / ILI9341 / GC9A01 …), touch, audio codecs, SD, camera + the `esp_lvgl_port`. Maps directly to our `<board>_board` layer. |
| [espressif/esp-iot-solution](https://github.com/espressif/esp-iot-solution) · [notes](references/esp-iot-solution.md) | component library | ESP-IDF ≥ 5.3 | Apache-2.0 | 150+ drivers / components via the Component Manager: sensors, LCD / touch panels, USB device classes, buttons / knobs / LEDs, BLE services, power. The grab-bag to check before writing a driver. |
| [78/voicestick](https://github.com/78/voicestick) · [notes](references/voicestick.md) | M5StickC S3 (ESP32-S3) | ESP-IDF 5.5 | unspecified ¹ | The **same exact board pager-buddy uses**. Reference for ST7789P3 display, ES8311 audio (16 kHz mono I2S → Opus), G38 PWM backlight, NimBLE / button bring-up, deep-sleep + battery. |

¹ No `LICENSE` file in the repo as of last clone — treat as **read-only**: study the
patterns, confirm pinouts, don't copy code wholesale. Confirm licensing before
vendoring anything.

## Adding a reference

1. Add a row to the table above (+ a `references/<name>.md` study note if it earns one).
2. Add a `name|url` line to the `refs=(…)` list in [`clone.sh`](references/clone.sh) so
   `clone.sh` fetches it into `_clones/`.

Keep this **firmware-focused**. Mechanical / PCB references belong with their parts.
