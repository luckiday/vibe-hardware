---
name: vibe-firmware
description: >-
  Take embedded firmware for a small device (ESP32 / RP2040 / STM32 / nRF …) from a
  plain-language spec to a reproducible build that flashes and runs, driven by an AI
  coding agent. Use when bringing up a new board, adding a peripheral/driver, wiring a
  device to a network service, or shipping an update. Key facts this skill encodes:
  structure the firmware as LAYERED COMPONENTS, not one big main.c — a board-support
  layer (BSP) is the ONLY place pin numbers + low-level init live and exposes a typed
  API (i2c bus, PMIC/battery, buttons) so nothing else touches a raw GPIO; ONE COMPONENT
  PER DOMAIN (display/ui, audio, connectivity…) each with a single public header as its
  only surface; and a THIN main that wires them via callbacks + a FreeRTOS event queue +
  a small state machine. Build in a PINNED toolchain (a Docker image / locked SDK) so
  it's bit-for-bit reproducible; keep board/pin config as CODE (the BSP header) mirroring
  the PCB net map; ship dual-slot OTA from day one and NEVER publish an update without a
  real-hardware test first. ESP-IDF is the worked-through platform — the modular layout,
  CMake/idf_component.yml, sdkconfig/partitions, and the gotchas (native-USB console, the
  managed-dep lockfile, PM locks) are in references/esp-idf-structure.md; the worked
  example is examples/pager-buddy/firmware/. Method ports to Arduino/PlatformIO/Zephyr.
---

# Text → firmware (beginner + agent → a board that runs)

> The *method and rules* below are platform-agnostic. **ESP-IDF is the worked-through
> platform** — see [`references/esp-idf-structure.md`](references/esp-idf-structure.md)
> for the modular component layout, and
> [`examples/pager-buddy/firmware/`](../../examples/pager-buddy/firmware/) for a building
> example. Fill in the equivalent commands for Arduino-CLI / PlatformIO / Zephyr.

The firmware half of a small product. You describe what the device should do and which
pins go where (from the **same net map** the [`vibe-pcb`](../vibe-pcb/) board
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
2. **Code — as layered components, not one `main.c`.** Build a **board-support layer**
   first (the one home for pins + low-level init + a typed API), then **one component per
   domain** (display, audio, net…), then a **thin `main`** that wires them. Board
   specifics (pins, bus speeds, addresses) live in the BSP header — config-as-code that
   mirrors the net map. See *Structure* below + `references/esp-idf-structure.md`.
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

**If it has a screen, close the UI loop on the host first.** Compile the firmware's *own*
render code on your machine and screenshot each state, so you (or an agent) tune layout,
typography and animation in a sub-second loop instead of a flash cycle — and an agent can
*read* the PNGs and iterate itself. Carve the panel bring-up behind one `#ifdef` so the
screens stay shared verbatim with the device. Method + gotchas:
[`references/host-ui-simulation.md`](references/host-ui-simulation.md); worked in
`examples/pager-buddy/firmware/sim/`.

## Structure: layered components, thin main

Don't grow one `main.c`. Split the firmware into **three layers**, each touching a
peripheral in exactly one place — so a board/sensor swap is a localized edit and each
domain stands on its own:

1. **Board-support layer (BSP)** — `components/<board>_board/`. The **only** place pin
   numbers and low-level init live; exposes `*_init()` + typed accessors (the I²C bus
   handle, PMIC battery/power, button state, deep-sleep prep). Its header *is* the
   config-as-code that mirrors the PCB net map. Nothing else reads a raw GPIO.
2. **Domain components** — `components/<domain>/` (display/ui, audio, connectivity…),
   one per function. Each has a **single public header** (`include/<domain>.h`) as its
   only surface — `init` + intent verbs + callback typedefs; the `.c` stays hidden.
   Drive a domain by *what* (`ui_set_error(msg)`), not *how*.
3. **Thin `main`** — `REQUIRES` the BSP + every domain; `app_main` inits each layer then
   runs the app. **Decouple with callbacks + a FreeRTOS queue + a state machine**: ISRs/
   timers/net post a typed event; one task consumes it and drives one explicit state
   enum. `main` is the conductor, not a driver.

Dependency rule: `domains → BSP → drivers`, `main → everything`; lower layers never call
up. The full ESP-IDF mechanics (CMake `REQUIRES`, `idf_component.yml`, `sdkconfig`,
partitions, PM, and the gotchas) are in
[`references/esp-idf-structure.md`](references/esp-idf-structure.md).

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
- **One peripheral, one place (the BSP).** Pins + low-level init live only in the
  board-support component; domains ask the board, never the GPIO. A board swap is then
  one component, not a grep across drivers.
- **Reproducible deps + dual-slot from day one.** Pin managed components and **commit the
  lockfile** (`dependencies.lock`); ship the dual-slot OTA partition table even before
  OTA exists, so a field update never forces a flash re-layout that wipes user data.
- **Connectivity is a transport-agnostic data producer.** A link/network component
  exposes *what arrived* (a borrow/seq/online surface), never *how* — so swapping the
  transport (Wi-Fi↔BLE) doesn't touch `main`, and the link never calls the UI. A
  clock-less device gets its **time from the link** (epoch + monotonic timer), not an RTC.

## Run it

ESP-IDF, pinned in Docker (the authoritative build) — `examples/pager-buddy/firmware/`
ships `idf.sh` (Docker build) + `flash.sh` (host flash) wrappers:

```bash
./idf.sh build            # reproducible build in the pinned Docker image
./flash.sh [PORT]         # flash from the host straight off build/ (auto-detects the port)
./flash.sh --monitor      # …and open the serial console
```

**Build and flash are separate by design.** Docker gives a bit-for-bit artifact but can't
reach `/dev/cu.*`, and a host `idf.py flash` would re-configure and choke on the Docker
build's `/project` cmake cache. `flash.sh` flashes the built binaries directly (via
`build/flasher_args.json`) — no host re-build, and it works the same from a git worktree.
(See `references/bringup-gotchas.md` → "Docker build + host flash".)

Other platforms — same shape, different command: `pio run` (PlatformIO pins the platform
in `platformio.ini`) · `arduino-cli compile --fqbn <board>`.

## TODO (fill in)

- [x] ESP-IDF modular structure → `references/esp-idf-structure.md`; pinned Docker build
      + config-as-code BSP demoed in `examples/pager-buddy/firmware/`.
- [x] pager-buddy bring-up so far: display (ST7789 + LVGL) and the **BLE status link**
      (NimBLE peripheral, hardware-tested) — see `references/esp-idf-structure.md`
      (connectivity) + the hard-won `references/bringup-gotchas.md`.
- [x] **Low-power auto sleep** (tiered light + deep, `ext1` button wake) — builds clean,
      needs a hardware test. Method + the BLE-can't-wake-from-deep-sleep fact in
      `references/esp-idf-structure.md` (Power management); the `ext1` self-wake traps in
      `references/bringup-gotchas.md`.
- [ ] Remaining pager-buddy bring-up: audio → OTA — one peripheral at a time.
- [x] **Host UI simulator + agent render-loop** — design/tune the screen on the host (render
      the real `ui.c` to PNGs and iterate) before flashing; method in
      `references/host-ui-simulation.md`, worked in `examples/pager-buddy/firmware/sim/`.
- [x] Standard build/flash wrappers: `idf.sh` (pinned Docker build) + `flash.sh` (host flash
      off `build/`, worktree-safe). The Docker↔host cmake-cache trap + the one-command cycle
      are in `references/bringup-gotchas.md`.
- [ ] Driver-pattern references for non-ESP platforms (Arduino / PlatformIO / Zephyr).

## Keeping this current (living doc)

When a bring-up teaches you a gotcha (a heap overflow only on real hardware, a toolchain
pin that mattered), fold it back here and commit it. The modular structure above was
distilled from a studied reference design (`78/voicestick` — ESP-IDF for the M5StickC S3)
plus the pager-buddy bring-up; when a new reference or build teaches a better pattern,
fold it in. See the other skills' "Keeping this current" notes.
