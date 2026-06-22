# 78/voicestick — study note

**Repo:** https://github.com/78/voicestick · **Framework:** ESP-IDF 5.5 ·
**License:** unspecified (no `LICENSE` file — read-only reference) ·
**Local clone:** `_clones/voicestick/` (run [`clone.sh`](clone.sh))

ESP-IDF firmware that turns an **M5StickC S3 — the exact board pager-buddy uses** —
into a BLE push-to-talk dictation device for macOS. Because the hardware is identical,
this is our highest-fidelity bring-up reference: a confirmed pinout, real driver init
sequences, and the power model.

## What to read, and why

| Area | Maps to in this repo |
|---|---|
| ST7789P3 1.14" LCD init + G38 PWM backlight | `examples/pager-buddy/firmware/components/stick_s3_board/` |
| ES8311 audio over I2S (16 kHz mono → Opus) | pager-buddy audio bring-up (next peripheral) |
| Shared I2C bus (`stick_s3_board_i2c_bus`) | our `stick_s3_board` BSP (mirrors it) |
| NimBLE peripheral / open link + MTU sizing | `examples/pager-buddy/firmware/components/bridge/` (modeled on its `voice_ble`) |
| Tiered deep-sleep + button wake (`prepare_deep_sleep`) | `examples/pager-buddy/firmware/main/main.c` low-power auto-sleep |
| Battery awareness (`ui_status_set_battery`) | `design/` battery indicator + UI status |

These mappings are already cited inline across the pager-buddy firmware — this note is
the index to them.

## Caveats

- **No license** in the repo: study the patterns and confirm pinouts, but don't vendor
  code wholesale. Our implementations are re-written, not copied.
- Pin to the commit you studied; upstream may change without notice.
