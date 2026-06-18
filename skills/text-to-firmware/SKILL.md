---
name: text-to-firmware
description: >-
  Take embedded firmware for a small device (ESP32 / RP2040 / STM32 / nRF …) from a
  plain-language spec to a reproducible build that flashes and runs, driven by an AI
  coding agent. Use when bringing up a new board, adding a peripheral/driver, wiring a
  device to a network service, or shipping an update. Key facts this skill encodes:
  build in a PINNED toolchain (a Docker image / locked SDK version) so it's bit-for-bit
  reproducible and "works on my machine" version drift can't bite; keep board/pin
  config as CODE (one header / Kconfig, not scattered magic numbers) so it tracks the
  PCB's net map; never ship an OTA/fleet update without a real-hardware test first.
  FRAMEWORK — fill in your platform's commands (this stub is platform-agnostic; the
  worked example is examples/pager-buddy/).
---

# Text → firmware (beginner + agent → a board that runs)

> ⚠️ **Framework stub.** The *method and rules* below are real and platform-agnostic;
> the exact toolchain commands are yours to fill in for ESP-IDF / Arduino-CLI /
> PlatformIO / Zephyr. See `examples/pager-buddy/` for a worked target.

The firmware half of a small product. You describe what the device should do and which
pins go where (from the **same net map** the [`text-to-pcb`](../text-to-pcb/) board
uses); the agent writes the drivers + app, builds them reproducibly, and you flash and
watch the serial log.

## The loop

```
spec + pin map ─► code ─► build (pinned) ─► flash + monitor ─► (OTA when fielded)
 (shared with        drivers   reproducible     real hardware      test-before-release
  the PCB net map)   + app     container        serial log
```

1. **Spec** — what it does + the **pin/peripheral map**. Reuse the board's net map so
   firmware pins and the PCB agree (a swapped sensor → a one-line pin + address change).
2. **Code** — drivers + app for your platform. Keep board specifics (pins, bus speeds,
   addresses, feature flags) in **one config-as-code** place that mirrors the net map.
3. **Build — reproducibly.** Build inside a **pinned toolchain** (a Docker image at a
   fixed SDK version, or a locked PlatformIO/SDK pin), *not* whatever is on your host.
   Version drift between a local SDK and CI is the #1 source of "works on my machine"
   bugs and silent ABI/heap differences. Make the pinned build the standard; a local
   build is a personal convenience only.
4. **Flash + monitor** — flash over USB and read the serial log. Bring up one
   peripheral at a time; confirm on the bench before adding the next.
5. **OTA (fielded devices)** — ship updates over the air with **rollback protection**,
   and **never publish to real/fleet devices without a real-hardware test first** —
   a clean compile is not enough (a code-clean path can still exhaust RAM or crashloop
   only on hardware with a live peripheral). Gate the publish behind a deliberate,
   post-test trigger.

## Rules this skill encodes (platform-agnostic)

- **Pinned, reproducible builds.** One image/lock = identical artifacts everywhere.
  Document the exact `build` command; treat host-toolchain builds as non-authoritative.
- **Config as code, mirroring the PCB.** Pins/buses/addresses/flags live in one file
  that tracks the board's net map — not magic numbers sprinkled across drivers.
- **Secrets never in the repo.** Wi-Fi creds / API keys / tokens load from a gitignored
  file or are flashed separately. Commit a `.example`.
- **Bring up incrementally, log everything.** One peripheral at a time; the serial log
  is your oscilloscope.
- **Hardware test before any release.** Especially before an OTA that touches fielded
  devices. Watch heap/reboots for a sustained run, exercise failure paths (peripheral
  unplugged, network loss).

## Run it  *(fill in for your platform)*

```bash
# examples — replace with your toolchain:
#   ESP-IDF (pinned):   docker run --rm -v "$PWD":/work -w /work espressif/idf:vX.Y idf.py build
#   PlatformIO:         pio run                 # platformio.ini pins the platform version
#   Arduino-CLI:        arduino-cli compile --fqbn <board>
# flash + monitor over USB (local toolchain, needs the cable):
#   idf.py flash monitor   /   pio run -t upload -t monitor   /   arduino-cli upload && monitor
```

## TODO (fill in)

- [ ] Pick the platform + pin the toolchain (image tag / `platformio.ini` / SDK rev).
- [ ] `references/` — your driver patterns, the config-as-code layout, the OTA + safety
      model, the build/flash/monitor commands.
- [ ] A `scripts/` build wrapper (mirrors `text-to-pcb`'s `pcb_check.sh` idea: one
      command → reproducible build + size report).

## Keeping this current (living doc)

When a bring-up teaches you a gotcha (a heap overflow only on real hardware, a toolchain
pin that mattered), fold it back here and commit it. See the other skills' "Keeping this
current" notes.
