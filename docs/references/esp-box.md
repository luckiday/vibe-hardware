# espressif/esp-box — study note

**Repo:** https://github.com/espressif/esp-box · **Framework:** ESP-IDF ≥ 5.1 ·
**License:** Apache-2.0 · **Local clone:** `_clones/esp-box/` (run [`clone.sh`](clone.sh))

Espressif's *official* AIoT dev-kit firmware for the ESP32-S3-BOX / -BOX-3 / -BOX-Lite:
a 2.4" LVGL touchscreen, dual-microphone far-field audio, offline wake-word + 200+
offline commands, with Matter / Home-Assistant / RainMaker integrations. The
best-maintained official counterpart to xiaozhi when you want display + audio + voice
done "the Espressif way."

## What to read, and why

| Area | Maps to in this repo |
|---|---|
| LVGL UI over `esp_lvgl_port` | our `ui` component pattern |
| Dual-mic audio front-end + offline speech (ESP-SR) | pager-buddy audio bring-up (next peripheral) |
| Board init / BSP (via esp-bsp) | our `<board>_board` BSP layer |
| Factory + OTA app structure | dual-slot OTA in [`esp-idf-structure.md`](../../skills/vibe-firmware/references/esp-idf-structure.md) |

## Caveats

- Built for BOX hardware (2.4" cap-touch, dual mic) — adapt pin / peripheral
  assumptions to your board; read it for *structure*, not pinout.
- Apache-2.0 — patterns and snippets reusable with attribution.
- Has submodules; the depth-1 clone doesn't fetch them (fine for studying structure).
