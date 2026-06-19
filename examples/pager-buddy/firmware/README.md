# pager-buddy — firmware (ESP-IDF · M5StickC S3)

Bring-up firmware for the pager, built on the **M5StickC S3** (ESP32-S3-PICO-1-N8R8 —
8 MB flash, 8 MB octal PSRAM, dual LX7 @240 MHz). Reference:
<https://docs.m5stack.com/en/core/StickS3>.

Built with **ESP-IDF v5.5** in a **pinned Docker toolchain** so the build is
reproducible regardless of the host SDK (per [`vibe-firmware`](../../../skills/vibe-firmware/)).

## What it does today (display UI, stub data)

Renders the pager UI on the LCD — the screens from
[`../design/`](../design/) (the web mock), driven by the two buttons. **No network
yet**: the sessions are stubbed in [`main/main.c`](main/main.c).

- **SIDE** (KEY2) = scroll/cycle the highlight (wraps) · **FRONT** (KEY1) = OK ·
  **hold FRONT** = back.
- Screens: idle (clock + battery) → Monitor list → Approve / Ask / Done / Working.
- Battery indicator reads the real **M5PM1** PMIC (falls back to a stub value).

### Structure — layered per [`vibe-firmware`](../../../skills/vibe-firmware/)

```
components/stick_s3_board/   BSP — the only home for pins; brings up I²C, powers the
                             LCD rail via the M5PM1 PMIC, owns buttons + battery
components/ui/               ST7789 + LVGL bring-up and the screen renderers
main/main.c                  thin: stub model + state machine + button poll + render loop
```

Pins live in [`components/stick_s3_board/include/stick_s3_board.h`](components/stick_s3_board/include/stick_s3_board.h)
(config-as-code), mirroring the [`../pcb/pinmap.yaml`](../pcb/pinmap.yaml) contract.
The LCD only lights because the BSP enables its rail through the PMIC — driving the
backlight GPIO alone is not enough on this hardware.

> **Status:** *builds clean* in the pinned toolchain (LVGL + ST7789, verified). Flash it
> and drive the screens with the two buttons to verify on real hardware.

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

- [x] **PMIC** — M5PM1 powers the LCD rail + battery reads (`stick_s3_board`).
- [x] **LCD** — ST7789P3 over SPI via `esp_lcd` + LVGL; the design screens (`ui`).
- [ ] **Wi-Fi/BLE status client** — replace the stub with the Claude Code hook bridge
      ([`../bridge/`](../bridge/)); KEY1 acks, screen flashes on a new "needs you".
- [ ] **Audio "buzz"** — ES8311 + AW8737 over I²S → a short tone on a page.
- [ ] **OTA** — only after a real-hardware soak test (heap/reboots, failure paths).
