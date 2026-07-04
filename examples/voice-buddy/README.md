# voice-buddy — a xiaozhi-style AI speaker, end to end

The first worked example that exercises **all four skills**: one natural-language
spec became a manifest + contracts (vibe-plm), a generated 2-layer KiCad board
(vibe-pcb; placement gated, routing in progress), a printed 2-part enclosure (vibe-cad), and a firmware port
(vibe-firmware) for the MIT-licensed
[78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) AI chatbot.

Hardware: ESP32-S3-WROOM-1-N16R8 · ES8311 codec DAC → NS4150B → rear-firing
4 Ω/3 W speaker · ES7210 4-ch ADC with 2 analog MEMS mics + amp echo-reference
(server-side AEC) · SSD1306 OLED on a socket · BOOT/VOL± buttons · WS2812 ·
USB-C 5 V. The audio architecture follows xiaozhi's `lichuang-dev`
(立创实战派) reference; pins are cross-checked between `pcb/pinmap.yaml` and
the firmware header by `plm_check.py`.

```
product.yaml          the manifest + interface contracts (validate: plm_check.py)
pcb/                  brief, pinmap.yaml, parts.yaml (single net source),
                      kicad/gen_sch.py + gen_pcb.py + routing.py  → generated board
cad/                  constraints.yaml (the shared fit numbers), voicebuddy_case.py
firmware/
  boards-port/…       drop-in board dir for upstream xiaozhi (config.h/json + class)
  selftest/           minimal ESP-IDF bring-up app (I2C scan, OLED, buttons, LED)
```

## How the language→geometry bridge works here

No coordinate in this design is hand-invented twice:

- `cad/constraints.yaml` holds every cross-domain number ONCE (outline, mount
  holes, USB-C port, panel windows, speaker). `gen_pcb.py` **reads** it — the
  board outline and connector positions are lookups, not literals.
- `pcb/parts.yaml` holds every net ONCE; the schematic and the copper both
  derive from it, so they cannot disagree.
- Placement is **relations** (`beside`, `align_pads`, `at_edge`, clusters), and
  numeric gates (courtyard/cluster overlap, keepouts, HPWL) fail the build
  before a bad floorplan reaches copper.
- Routing is **computed** (pad-anchored `wire()/via()` — freerouting is the
  preferred alternative when available).
- `gen_pcb.py` exports `placement.json`; `plm_check.py` compares contract vs
  evidence, and `check_fit.py` proves board↔shell interference = 0 mm³.

## Rebuild / verify

```bash
python3 ../../skills/vibe-plm/scripts/plm_check.py product.yaml     # manifest + cross-checks
cd pcb/kicad && ../../../../skills/vibe-pcb/scripts/pcb_check.sh voicebuddy   # ERC/DRC gates
cd ../../cad && ../../../.venv/bin/python build_all.py                        # enclosure
../../../.venv/bin/python ../../../skills/vibe-cad/scripts/check_fit.py voicebuddy_case.py
```

## Status — read before building one

`status: wip` on every domain. Placement gates are green and the enclosure fit-check is 0 mm³, but **routing is still in progress — DRC is NOT yet clean** (ERC additionally needs a ≥8 host);
the firmware has **not** been compiled or run on hardware; and
`pcb/voicebuddy_brief.md` §10 lists datasheet values that are UNVERIFIED
(ES7210 supply-pin names, NS4150B pin-1 orientation, MEMS mic port variant,
AEC divider values). Close that checklist before ordering anything.
