# pager-buddy — a Claude Code "pager"

> **Status: scaffolded / stub.** The structure is initialized — a
> [`product.yaml`](product.yaml) manifest + the three domain dirs (`firmware/`, `pcb/`,
> `cad/`) with their interface-contract stubs. The *sources* inside each are still to be
> filled in. This is the flagship example that exercises all four
> [skills](../../skills/) (vibe-plm ties the three domains together).

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

## Structure (the vibe-plm manifest ties it together)

```
pager-buddy/
  product.yaml          # the manifest: identity + revision + interface contracts (vibe-plm)
  firmware/             # vibe-firmware  — consumes pcb/pinmap.yaml
  pcb/                  # vibe-pcb       — produces pinmap.yaml + board.step
    pinmap.yaml         #   contract: pcb -> firmware (the net map)
  cad/                  # vibe-cad       — produces constraints.yaml
    constraints.yaml    #   contract: cad <-> pcb (the shared fit numbers)
```

The three domains agree **only through those contract files** — change a shared number
once and both sides move; bump `revision` in `product.yaml` and re-run the gate:

```bash
python3 ../../skills/vibe-plm/scripts/plm_check.py product.yaml
```

## Per-skill breakdown

| Skill | This example's slice |
|---|---|
| [**vibe-firmware**](../../skills/vibe-firmware/) | Wi-Fi status client (HTTP poll / WS / MQTT fed by the hook bridge) → render state on the display, buzz/flash on transitions, button to ack. Config-as-code: display + buzzer + button pins, endpoint URL; Wi-Fi creds as a secret. |
| [**vibe-pcb**](../../skills/vibe-pcb/) | Carrier for the MCU + display connector + buzzer + button. **Net map:** display (I²C/SPI), buzzer GPIO, button GPIO. Belly keep-out under the flush MCU; USB-C out one edge. |
| [**vibe-cad**](../../skills/vibe-cad/) | A small desk shell exposing the **display window**, USB-C, and the button; holds the PCB on standoffs. Same board outline / display cutout / mount holes as the PCB. |

## To build it out

0. Fill in the contracts: the net map ([`pcb/pinmap.yaml`](pcb/pinmap.yaml)) and the
   shared fit numbers ([`cad/constraints.yaml`](cad/constraints.yaml)); keep
   [`product.yaml`](product.yaml) current and run `plm_check.py` (above).
1. Write the spec/net map (start from [`vibe-pcb` spec template](../../skills/vibe-pcb/references/spec-template.md)).
2. `pcb/` — generate the carrier, DRC-clean, review with `pcb_view.sh`; export `board.step`.
3. `cad/` — model the shell to the shared fit numbers, check the board fits (0 mm³).
4. `firmware/` — the status client + the Claude Code hook bridge.
5. Walk the [release gate](../../skills/vibe-plm/references/release-checklist.md) — all
   three domains green at one revision — then fabricate (JLCPCB gerbers + print the
   shell), flash, page yourself. 🎉
