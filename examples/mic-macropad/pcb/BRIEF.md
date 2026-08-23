# mic-macropad — board brief

## 1. What it is

A three-key macropad that listens: three MX-style mechanical switches, an I2S
MEMS microphone, and an ESP32-S3-WROOM-1, powered and flashed over USB-C.
76 × 56 mm, two layers, 30 parts, 19 nets.

## 2. Power

```
USB-C ─┬─ 5.1k ×2 on CC1/CC2         (this is what asks a C-to-C cable for 5 V)
       ├─ USBLC6-2SC6 ── D+/D- ───── GPIO20 / GPIO19  (native USB, no bridge)
       └─ VBUS ── AP2112K-3.3 ── 3V3 ── module, mic
```

USB-only by design. An earlier revision carried a LiPo subsystem (charger,
P-FET load-share, cell connector, sense divider) and those were exactly the
nets that would not route; deleting them was the single biggest routing win.

Peak draw is 355 mA (802.11b TX at 20.5 dBm) against a 600 mA LDO, so the
margin lives in the bulk caps rather than the regulator.

## 3. Pin map

The contract is [`pinmap.yaml`](pinmap.yaml); the reasoning is one line long:
**every signal leaves the module on the side facing its destination.** Keys on
the bottom pad row in key order, the mic bus on the right column opposite the
mic, USB fixed by silicon on the left, UART and LED on the right.

## 4. Mechanical

All shared numbers are in [`../cad/constraints.yaml`](../cad/constraints.yaml).
The ones that decide things: MX switches are **PCB-mount (5-pin)** so the two
locating posts are used; the mic is a **bottom-port** part and needs a hole in
the shell floor plus a gasket if the case is sealed; the antenna keepout is
Espressif's own (x ±24 mm above the module), and no shell wall or metal may sit
over it either.

## 5. Validation

```bash
cd kicad && ./route_fr.sh          # DRC 0 error-severity / 0 unconnected
python3 ../../../skills/vibe-pcb/scripts/zone_islands.py \
        kicad/macropad-fr.kicad_pcb --net GND --strict     # no orphan pour islands
python3 ../../../skills/vibe-plm/scripts/plm_check.py ../product.yaml
```

## 6. EST register — every estimated number, tracked until closed

| # | item | status |
|---|---|---|
| E1 | USB-C, mic and WROOM land patterns | **closed** — official KiCad lands (the hand-drawn mic land was miswired; see ../README.md) |
| E2 | antenna keepout extent | **closed** — Espressif's own rule area, x ±24 mm |
| E3 | LED polarity | **closed** — KiCad `LED_0603` pad 1 is the cathode |
| E4 | trace widths: 0.5 mm power / 0.25 mm signal | **EST** — sized by rule of thumb, not by a thermal calculation. VBUS carries ≤ 500 mA over ~25 mm; check against IPC-2152 before ordering |
| E5 | MX switch part number | **EST** — footprint is generic Cherry MX PCB-mount; confirm the actual switch's pin positions |
| E6 | USB-C receptacle part | **EST** — land is HRO TYPE-C-31-M-12; confirm the ordered part matches that land |
| E7 | button access through the shell | **EST** — the TS-1187A is top-actuated, so the shell either bores straight down onto it (`windows.btn_*`) or reaches over it with a flexure tab from the right wall. Which one, and whether the tab has room, is settled with the real shell |

E4–E7 are the pre-order checklist. Nothing here has been fabricated.

## 7. Sourcing — can JLCPCB assemble this?

Partly. The BOM line for every part is emitted by
`skills/vibe-pcb/scripts/fab_export.sh`, which reads `lcsc:` out of
`parts.yaml`, and it prints exactly which lines still have no part number.

**Verified available** (looked up, not remembered):

| ref | part | LCSC | note |
|---|---|---|---|
| J1 | TYPE-C-31-M-12 | `C165948` | SMD receptacle — machine-placeable, and KiCad's land is named for this exact part |
| U1 | ESP32-S3-WROOM-1-N8R8 | `C2913201` | **Standard PCBA only**, not the Economic service |
| U3 | AP2112K-3.3TRG1 | `C51118` | |
| U4 | ICS-43434 | `C5656610` | |
| D1 | USBLC6-2SC6 | `C7519` | |

**Cannot be machine-assembled as drawn:**

- **SW1–SW3, the MX key switches.** They are through-hole, and a Cherry-MX-style
  switch is not in JLCPCB's assembly library. Hand-solder them — three joints,
  and `fab_export.sh macropad-fr SW1 SW2 SW3` already keeps them out of the CPL.
### Why reset/boot are not side-actuated

They were, for one revision. Sourcing killed it. Every side-actuated candidate
failed a different way:

| part | why not |
|---|---|
| Panasonic EVQ-P7C | not carried by LCSC/JLCPCB at all |
| Alps SKRKAEE010 | obsolete lifecycle |
| ROCPU TP40521116 (`C5289939`) | in JLCPCB's library, Economic+Standard — but **4 units** in stock, and no published land pattern |
| JLCPCB JC-K1 (`C9900014703`) | in the library, but no datasheet and no dimensions published — nothing to draw a land from |
| YIZHI YZA-022 (`C49108618`) | 360 in stock, assembly availability not stated, no land pattern |

So SW4/SW5 are **XKB TS-1187A (`C318884`)**: top-actuated, in JLCPCB's library
for **both Economic and Standard** PCBA, in stock at about $0.01, and with a
stock KiCad land (`SW_Push_1P1T_XKB_TS-1187A`) so the footprint is not a
guess. They sit by the right edge, and a side press — if the enclosure wants
one — comes from a flexure tab in the right wall pressing down on the button.
The mechanism moved from the board into the shell, which is where it is cheap.

**Still to fill:** the passives (0402 R/C, the 0805 bulk cap, the 0603 LED)
have no `lcsc:` yet. They are all commodity JLCPCB *Basic* parts — pick them
from the Basic Parts filter so the order carries no per-part setup fee, and
add the numbers to `parts.yaml`. `fab_export.sh` names the exact lines.

So an SMT order today assembles everything except the three MX keys, which are
through-hole and hand-soldered by design. Filling the passives' `lcsc:` fields
is the only step left before the BOM is orderable.
