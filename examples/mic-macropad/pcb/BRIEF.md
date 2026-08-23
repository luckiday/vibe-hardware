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

E4–E6 are the pre-order checklist. Nothing here has been fabricated.
