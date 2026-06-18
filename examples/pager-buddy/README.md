# pager-buddy — a Claude Code "pager"

> **Status: brief / stub.** The concept and the per-skill breakdown are here; the
> sources (`firmware/`, `pcb/`, `cad/`) are to be filled in. This is the flagship
> example that exercises all three [skills](../../skills/).

A tiny desk device that gives your coding agent a **physical presence**: it lights up,
shows a glyph, and buzzes when a **Claude Code session changes state** — task done,
**waiting on your input**, build/test failed, or a long job finished — so you can look
away from the terminal and still get paged, like an old **pager**.

## How it talks to Claude Code

Claude Code emits lifecycle events via **hooks** (e.g. `Notification`, `Stop`). A small
hook command turns each event into a status ping the device can read:

```
Claude Code hook ──► tiny bridge (local HTTP / MQTT / WebSocket) ──► ESP32 ──► display + buzzer
 (settings.json)      "status: waiting_input"                       polls/subs   pages you
```

The bridge can be one shell line in `~/.claude/settings.json` hooks that POSTs the event
to the device's endpoint (LAN), or publishes to MQTT the device subscribes to. *(Pick
one when filling this in.)*

## Bill of the build (the shared fit numbers live here)

- **MCU:** XIAO ESP32-S3 (Wi-Fi, USB-C) or any ESP32.
- **Out:** a small OLED/e-ink display + a buzzer or vibration motor + a status LED.
- **In:** one button (ack / silence).
- **Power:** USB-C (optionally a LiPo).

## Per-skill breakdown

| Skill | This example's slice |
|---|---|
| [**vibe-firmware**](../../skills/vibe-firmware/) | Wi-Fi status client (HTTP poll / WS / MQTT fed by the hook bridge) → render state on the display, buzz/flash on transitions, button to ack. Config-as-code: display + buzzer + button pins, endpoint URL; Wi-Fi creds as a secret. |
| [**vibe-pcb**](../../skills/vibe-pcb/) | Carrier for the MCU + display connector + buzzer + button. **Net map:** display (I²C/SPI), buzzer GPIO, button GPIO. Belly keep-out under the flush MCU; USB-C out one edge. |
| [**vibe-cad**](../../skills/vibe-cad/) | A small desk shell exposing the **display window**, USB-C, and the button; holds the PCB on standoffs. Same board outline / display cutout / mount holes as the PCB. |

## To build it out

1. Write the spec/net map (start from [`vibe-pcb` spec template](../../skills/vibe-pcb/references/spec-template.md)).
2. `pcb/` — generate the carrier, DRC-clean, review with `pcb_view.sh`.
3. `cad/` — model the shell to the shared fit numbers, check the board fits (0 mm³).
4. `firmware/` — the status client + the Claude Code hook bridge.
5. Fabricate (JLCPCB gerbers + print the shell), flash, page yourself. 🎉
