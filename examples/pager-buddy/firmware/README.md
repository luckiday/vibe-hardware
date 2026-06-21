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
                             JSON into the shared app model (a pure data producer);
                             also receives audio settings on the control characteristic
components/audio/            ES8311 (DAC) + AW8737 over I²S; alert tones + NVS-backed
                             enable/volume (a self-contained FreeRTOS task)
main/main.c                  thin: state machine + button poll + binds live/stub + render;
                             fires alert tones + applies pushed audio settings
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
./flash.sh                      # flash the Docker-built build/ from the host (auto-detects port)
./flash.sh /dev/cu.usbmodemXXXX # …or name the port explicitly
./flash.sh --monitor            # …then open the serial console
```

`flash.sh` flashes the **already-built** binaries with esptool (via
`build/flasher_args.json`) — it does **not** re-run CMake, so it sidesteps the Docker→host
`/project` cmake-cache conflict and works unchanged **from a git worktree**. It needs
esptool on the host (`pip install esptool`, or `source $IDF_PATH/export.sh`). The standard
cycle is just **`./idf.sh build && ./flash.sh`**.

- No serial? The S3 may enumerate as **native USB Serial/JTAG** — try the other
  `/dev/cu.*` (pass it to `flash.sh`), or set `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`.
- Flashing won't start? Long-press the power button to enter **download mode**.
- A raw host `idf.py flash` on a Docker-built `build/` aborts with "CMakeCache.txt directory
  is different" — that's expected; use `flash.sh`, or `rm -rf build` for a host rebuild.

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
- [x] **Audio "buzz"** — ES8311 (DAC) + AW8737 over I²S → a distinct alert tone when a
      session newly enters waiting/asking/done (`audio` component). Enable/volume are
      Mac-controlled via the bridge `control` characteristic (`../bridge/pager_settings.py`)
      and persisted in NVS; FRONT = ACK/silence. The speaker amp enable is **M5PM1 PMIC
      GPIO3** (not an ESP32 GPIO — confirmed against xiaozhi-esp32's `m5stack-stick-s3`),
      driven by `board_audio_amp()` and gated to the playback window. Builds + boots on
      the device (`audio: ready`); confirm the tone is audible on your unit.
- [ ] **OTA** — only after a real-hardware soak test (heap/reboots, failure paths).
