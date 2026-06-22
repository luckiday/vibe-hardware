# espressif/esp-iot-solution — study note

**Repo:** https://github.com/espressif/esp-iot-solution · **Framework:** ESP-IDF ≥ 5.3 ·
**License:** Apache-2.0 · **Local clone:** `_clones/esp-iot-solution/` (run [`clone.sh`](clone.sh))

Espressif's 150+-component grab-bag of drivers and frameworks: sensors, LCD / touch
panels, USB device classes, buttons / knobs / LED indicators, BLE services, motor /
power. The first place to look before writing a peripheral driver from scratch.

## What to read, and why

| Need | Where (roughly) |
|---|---|
| A sensor / display / input driver | `components/<category>/` |
| Button / knob / long-press handling | `components/button`, `components/knob` |
| USB device classes (CDC, MSC, …) | `components/usb/` |
| Reference apps wiring components together | `examples/` |

## Caveats

- Quality varies across components — check each one's own README + maturity note.
- Consume via the Component Manager; clone only to read.
- Has submodules; the depth-1 clone doesn't fetch them.
