# pager-buddy — a Claude Code "pager"

> **Status: partially built.** The **firmware**, the **Mac bridge**, and the **web design
> mock** are working today — realized on an off-the-shelf **M5StickC S3** dev board (it
> already has the LCD, buttons, PMIC and speaker). The custom **carrier PCB** (`pcb/`) and
> the **3D-printed shell** (`cad/`) are still stubs — they're the from-scratch hardware the
> [`vibe-pcb`](../../skills/vibe-pcb/) and [`vibe-cad`](../../skills/vibe-cad/) skills would
> produce. So this example fully exercises **vibe-firmware** + **vibe-plm** now, and is the
> in-progress target for the other two.

A tiny desk device that gives your coding agent a **physical presence**: it lights up,
shows the session, and buzzes when a **Claude Code session changes state** — task done,
**waiting on your input**, build/test failed, or a long job finished — so you can look
away from the terminal and still get paged, like an old **pager**. It can also **answer
Claude's permission / question prompts from the device** (a two-way gate).

## How it talks to Claude Code

Claude Code emits lifecycle events via **hooks** (e.g. `Notification`, `Stop`,
`PermissionRequest`). A small hook command turns each event into a status snapshot, and a
Mac-side relay pushes it to the device over BLE:

```
Claude Code hook ──► Mac bridge (hook → local hub → BLE relay) ──► M5StickC S3 ──► display + buzzer
 (settings.json)      claude_pager_hook.py + the `pager` CLI       NimBLE peer    pages you
```

See [`bridge/`](bridge/) for the working bridge (the `pager` CLI, the hook, analytics)
and [`firmware/`](firmware/) for the ESP-IDF device firmware. The [`design/`](design/)
dir is a browser mock of the device screens used to iterate the UI.

## Structure (the vibe-plm manifest ties it together)

```
pager-buddy/
  product.yaml          # the manifest: identity + revision + interface contracts (vibe-plm)
  firmware/   [built]    # vibe-firmware  — ESP-IDF on the M5StickC S3 (LVGL UI + NimBLE)
  bridge/     [built]    # the Mac side   — Claude Code hook → hub → BLE relay (`pager` CLI)
  design/     [built]    # browser mock of the device screens (UI iteration)
  pcb/        [stub]     # vibe-pcb       — would produce pinmap.yaml + board.step
    pinmap.yaml          #   contract: pcb -> firmware (the net map)
  cad/        [stub]     # vibe-cad       — would produce constraints.yaml + the shell
    constraints.yaml     #   contract: cad <-> pcb (the shared fit numbers)
```

The domains agree **only through those contract files** — change a shared number once and
both sides move; bump `revision` in `product.yaml` and re-run the gate:

```bash
python3 ../../skills/vibe-plm/scripts/plm_check.py product.yaml
```

## Run it today (firmware + bridge)

The device firmware runs on a stock **M5StickC S3**, and the Mac bridge feeds it live
Claude Code status:

```bash
# device: build (pinned Docker toolchain) then flash from the host
cd firmware && ./idf.sh build && ./flash.sh        # see firmware/README.md
# mac: install the bridge + register the Claude Code hooks, then bring it up
cd ../bridge && ./pager install && ./pager up      # see bridge/README.md
```

## Per-skill breakdown

| Skill | This example's slice | State |
|---|---|---|
| [**vibe-firmware**](../../skills/vibe-firmware/) | LVGL status UI on the LCD; NimBLE peripheral that receives status snapshots; alert tones; buttons to ack / answer prompts. Config-as-code pins; Wi-Fi creds as a secret. | **built** |
| [**vibe-plm**](../../skills/vibe-plm/) | `product.yaml` manifest + the `pinmap.yaml` / `constraints.yaml` interface contracts that tie the domains together; the `plm_check.py` gate. | **built** |
| [**vibe-pcb**](../../skills/vibe-pcb/) | A custom carrier for the MCU + display + buzzer + buttons (replacing the StickC dev board). Belly keep-out under a flush module; USB-C out one edge. | *stub* |
| [**vibe-cad**](../../skills/vibe-cad/) | A desk shell exposing the display window, USB-C, and buttons; holds the carrier on standoffs. Same outline / cutout / mount holes as the PCB. | *stub* |

## What's left to build (the custom hardware)

The firmware + bridge are done on the StickC dev board; the remaining work is the
from-scratch carrier + enclosure so it's a standalone device:

1. Write the spec/net map (start from the [`vibe-pcb` spec template](../../skills/vibe-pcb/references/spec-template.md)),
   keeping [`pcb/pinmap.yaml`](pcb/pinmap.yaml) as the pcb→firmware contract.
2. `pcb/` — generate the carrier, DRC-clean, review with `pcb_view.sh`; export `board.step`.
3. `cad/` — model the shell to the shared fit numbers ([`cad/constraints.yaml`](cad/constraints.yaml)),
   check the board fits (0 mm³).
4. Walk the [release gate](../../skills/vibe-plm/references/release-checklist.md) — all
   domains green at one revision — then fabricate (JLCPCB gerbers + print the shell),
   flash, page yourself. 🎉
