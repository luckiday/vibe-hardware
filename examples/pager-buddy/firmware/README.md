# pager-buddy — firmware (ESP-IDF · M5StickC S3)

Bring-up firmware for the pager, built on the **M5StickC S3** (ESP32-S3-PICO-1-N8R8 —
8 MB flash, 8 MB octal PSRAM, dual LX7 @240 MHz). Reference:
<https://docs.m5stack.com/en/core/StickS3>.

Built with **ESP-IDF v5.5** in a **pinned Docker toolchain** so the build is
reproducible regardless of the host SDK (per [`vibe-firmware`](../../../skills/vibe-firmware/)).

## What it does today (display UI + BLE status link)

Renders the pager UI on the LCD — the screens from
[`../design/`](../design/) (the web mock), driven by the two buttons, **fed live
over BLE** by the Mac bridge ([`../bridge/`](../bridge/)). Until the first snapshot
arrives it shows stub sessions from [`main/main.c`](main/main.c).

- **SIDE** (KEY2) = scroll/cycle the highlight (wraps) · **FRONT** (KEY1) = OK ·
  **hold FRONT** = back.
- Screens: idle (clock + battery) → Monitor list → Approve / Ask / Done / Working.
- Battery indicator reads the real **M5PM1** PMIC (battery is device-owned, never on
  the wire); clock/date come from the snapshot (the Mac is the time source).
- **BLE**: the device is a NimBLE **peripheral** advertising as `pg-XXXX`; the Mac
  connects and writes status snapshots. Modeled on
  [`voicestick`](../../../docs/references/_clones/voicestick/firmware/components/voice_ble/).

### Structure — layered per [`vibe-firmware`](../../../skills/vibe-firmware/)

```
components/stick_s3_board/   BSP — the only home for pins; brings up I²C, powers the
                             LCD rail via the M5PM1 PMIC, owns buttons + battery
components/ui/               ST7789 + LVGL bring-up and the screen renderers
components/bridge/           BLE (NimBLE) peripheral; reassembles + parses snapshot
                             JSON into the shared app model (a pure data producer)
main/main.c                  thin: state machine + button poll + binds live/stub + render
```

Pins live in [`components/stick_s3_board/include/stick_s3_board.h`](components/stick_s3_board/include/stick_s3_board.h)
(config-as-code), mirroring the [`../pcb/pinmap.yaml`](../pcb/pinmap.yaml) contract.
The LCD only lights because the BSP enables its rail through the PMIC — driving the
backlight GPIO alone is not enough on this hardware.

> **Status:** *builds clean* in the pinned toolchain (LVGL + ST7789 + NimBLE). Flash it,
> drive the screens with the two buttons, and feed it live status from the Mac bridge.

### Live status from the Mac

On the Mac (see [`../bridge/`](../bridge/)):

```bash
pip install bleak
python3 ../bridge/pager_stub.py        # the hub (Claude hooks POST here; --ui for the web mock)
python3 ../bridge/ble_push.py          # scans for "pg-XXXX", connects, writes snapshots over BLE
python3 ../bridge/install_hooks.py install   # register the Claude Code hooks (then restart Claude)
```

The device shows stub sessions until the first snapshot lands, then switches to live
data. The wire format is [`../bridge/protocol.yaml`](../bridge/protocol.yaml).

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

The BLE link needs no credentials (open connection, like voicestick), so nothing is
required here today. `main/secrets.h` (**gitignored**) is reserved for later stages
(a Wi-Fi fallback / OTA); copy the example if/when those land:

```bash
cp main/secrets.example.h main/secrets.h   # then fill it in — never commit secrets.h
```

## Next stages (incremental bring-up — one peripheral at a time)

- [x] **PMIC** — M5PM1 powers the LCD rail + battery reads (`stick_s3_board`).
- [x] **LCD** — ST7789P3 over SPI via `esp_lcd` + LVGL; the design screens (`ui`).
- [x] **BLE status client** — NimBLE peripheral receives Claude Code snapshots from
      the Mac bridge ([`../bridge/`](../bridge/)) into the live model (`bridge`).
- [ ] **Two-way + page** — device → Mac approve/answer over the resolution
      characteristic; screen flashes / wakes on a new "needs you".
- [ ] **Audio "buzz"** — ES8311 + AW8737 over I²S → a short tone on a page.
- [ ] **OTA** — only after a real-hardware soak test (heap/reboots, failure paths).
