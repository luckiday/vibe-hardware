# pager-buddy — firmware (ESP-IDF · M5StickC S3)

Bring-up firmware for the pager, built on the **M5StickC S3** (ESP32-S3-PICO-1-N8R8 —
8 MB flash, 8 MB octal PSRAM, dual LX7 @240 MHz). Reference:
<https://docs.m5stack.com/en/core/StickS3>.

Built with **ESP-IDF v5.5** in a **pinned Docker toolchain** so the build is
reproducible regardless of the host SDK (per [`vibe-firmware`](../../../skills/vibe-firmware/)).

## What it does today (stage-1 bring-up)

[`main/main.c`](main/main.c) proves the board is alive *without* guessing at the
PMIC/LCD init sequence:

- logs chip info (cores, flash, PSRAM, heap);
- turns the LCD backlight on (G38);
- configures both buttons (KEY1/KEY2, active-low) and reports them each heartbeat;
- inits the shared I²C bus (SDA G47 / SCL G48) and **scans** it — expect
  **BMI270 @0x68**, **M5PM1 @0x6e**, **ES8311 @0x18**.

Pins live in [`main/board_pins.h`](main/board_pins.h) (config-as-code), which mirrors
the [`../pcb/pinmap.yaml`](../pcb/pinmap.yaml) contract — keep them in sync.

> **Status:** *builds clean* in the pinned toolchain (verified). **Not yet flashed to
> hardware** — a clean compile is not a bring-up. Flash + watch the serial log next.

## Build — reproducible (Docker, authoritative)

```bash
./idf.sh build                  # idf.py inside espressif/idf:v5.5 (override IDF_DOCKER_TAG)
```

## Flash + monitor — host (Docker can't reach USB on macOS)

```bash
# with a host ESP-IDF (e.g. ~/esp/v5.5.1/esp-idf, source its export.sh first):
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

- No serial? The S3 may enumerate as **native USB Serial/JTAG** — try the other
  `/dev/cu.*`, or set `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`.
- Flashing won't start? Long-press the power button to enter **download mode**.

## Secrets

Wi-Fi creds + the hook-bridge endpoint live in `main/secrets.h` (**gitignored**):

```bash
cp main/secrets.example.h main/secrets.h   # then fill it in — never commit secrets.h
```

## Next stages (incremental bring-up — one peripheral at a time)

- [ ] **LCD** — ST7789P3 over SPI via `esp_lcd` (`esp_lcd_panel_st7789`) → status glyphs.
- [ ] **PMIC** — M5PM1 init over I²C (battery, rail enables); needs the register map.
- [ ] **Audio "buzz"** — ES8311 + AW8737 over I²S → a short tone on a page.
- [ ] **Wi-Fi status client** — poll/subscribe the Claude Code hook bridge; KEY1 acks.
- [ ] **OTA** — only after a real-hardware soak test (heap/reboots, failure paths).
