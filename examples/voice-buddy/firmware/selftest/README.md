# voice-buddy selftest — first-power bring-up firmware

A minimal ESP-IDF app (no xiaozhi, no Wi-Fi) that proves the carrier board is
alive before the real firmware goes on. Per the vibe-firmware layering, the
BSP component (`components/voicebuddy_board/`) is the ONLY place pins live —
it mirrors `../../pcb/pinmap.yaml` the same way the xiaozhi port's `config.h`
does.

What it checks, in order, printing PASS/FAIL per step on the console:

1. **I²C scan** — expects ES8388 @0x10, SSD1306 @0x3C. A missing codec = the
   audio cluster didn't solder; a missing 0x3C just means no OLED plugged
   (warn, not fail).
2. **Control-register read** — reads a known ES8388 control register over I²C
   (a readable register proves more than a bare ACK).
3. **OLED test pattern** — checkerboard + text via `esp_lcd` SSD1306 (skipped
   if absent).
4. **Buttons + LED** — 10 s interactive loop: each press of BOOT/VOL+/VOL-
   changes the WS2812 color and logs the GPIO. PA_EN is toggled LOW the whole
   time (amp silent).

The full audio path (ES8388 playback → NS4150 → speaker, ES8388 capture +
AEC reference) is exercised by the xiaozhi firmware itself — see
`../boards-port/voice-buddy/`.

## Build (pinned toolchain — the vibe-firmware rule)

    docker run --rm -it -v $PWD:/project -w /project espressif/idf:v5.4 \
        idf.py set-target esp32s3 build
    # host-side flash (adjust port):
    idf.py -p /dev/tty.usbmodem* flash monitor

Status: written against ESP-IDF v5.4 APIs but **not yet compiled or run on
hardware** (this workspace has no toolchain). Treat every step as unverified
until the release checklist says otherwise.
