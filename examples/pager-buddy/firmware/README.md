# pager-buddy — firmware

> **Stub.** Sources to be filled in via [`vibe-firmware`](../../../skills/vibe-firmware/).

The status client: poll/subscribe the Claude Code hook bridge, render state on the
OLED, buzz/flash on transitions, button to ack.

## Interface contract

- **Consumes** [`../pcb/pinmap.yaml`](../pcb/pinmap.yaml) — pins / bus speeds /
  addresses must match the board. Keep the firmware config-as-code in sync with it,
  and bump `revision` in [`../product.yaml`](../product.yaml) on any change.

## Build *(fill in)*

Pin the toolchain (ESP-IDF image tag / `platformio.ini`). Wi-Fi creds load from a
gitignored file — commit a `.example`. See the skill for the loop.
