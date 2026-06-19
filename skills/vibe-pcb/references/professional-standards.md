# Professional schematic & PCB standards (the conventional checklist)

What makes a schematic/board read as *professional* rather than a beginner dump. These are
industry conventions, not this repo's gotchas (those live in `design-rules.md`). Drive a
board through both. The generators (`gen_sch.py` / `gen_pcb.py`) should *encode* these so
every regen is conformant by construction.

## Power architecture (design the rails BEFORE the schematic)

A pro hardware writeup leads with a **power tree**, not a part. Do the same:

- **Draw the power tree first.** A block diagram of every *source* → *conversion* → *rail* →
  *loads*: e.g. `USB-C 5V → charger → batt → boost → 5V (auto-switch) → LDO → 3V3 → {MCU, SD,
  mic, screen}`, with `5V → {amp, LEDs}`. It catches a missing rail, an **undersized regulator**
  (sum the loads, check LDO/boost headroom — "one LDO covers 3V3 because total < 500 mA"), and
  it *is* the schematic's power blocks + the PCB's current-flow placement.
- **Set current-defining resistors from the PART's rating, not a round number.** A charger's
  PROG resistor sets charge current to the **battery's max C-rate** (a 600 mAh 0.5C cell → ≤300 mA
  → pick R per the datasheet); a boost/LDO feedback divider sets Vout. **Over-driving is a safety
  risk, not just a spec miss** ("charge current > the cell's rating can be dangerous"). Put the
  calc + the assumption in a comment.
- **Input protection is standard, not optional.** USB-C: **CC1/CC2 pulled down 5.1k** (so a
  PD/QC/AFC charger negotiates 5V), **ESD diodes on D+/D− and VBUS** (static through the connector
  shell is a top MCU-killer). Add ESD/series-R on any externally-exposed line.
- **Two sources → make-before-break.** Auto-switch (load-share **PMOS + ORing diode**, a pull-down
  biasing the gate) between USB-5V and battery-boost-5V so the rail **never browns out** on
  changeover.
- **Design for variants — DNP/NC provisioning.** Leave footprints unpopulated (an `NC` resistor,
  an alternate-regulator pad) so one board adapts to other parts/values; mark **DNP** and say why
  ("R125 NC — reserved to fit an alternate boost IC"). Same idea as DNP pull-ups.
- **Check the module's RESERVED pins before assigning any.** A WROOM/SiP ties some pins to internal
  flash/PSRAM — **ESP32-S3 R8/R16V: IO35/36/37 = octal PSRAM, unusable** — verify against the module
  datasheet, don't route them out. (A pin-planning gate that bites at layout time.)
- **Leave debug/test access** — a reset button, a few test points / a debug header — cheap insurance
  that saves bring-up.

## Schematic standards

**Sheet & title block**
- Fill the **title block**: title, rev, date, author/company, sheet *N of M*, and key notes
  (I²C addresses, default jumper states). An empty title block is the #1 "beginner" tell.
- Keep the standard **frame + zone references** (A–D × 1–6); cite parts by zone in notes.
- One **functional block per region**; multi-function designs span multiple sheets.
- **Standardized block alignment (a rule, not per-board hand-tuning).** Draw a labelled frame
  per functional block, **auto-sized from the block's content bbox** (symbol body + pins +
  power symbols + label/value text) plus a **uniform padding** — never eyeballed boxes. Then
  **align the frames on a macro grid**: a top row of blocks shares one top/bottom edge, a
  full-width block below spans their combined width. Components inside sit on the 1.27 mm grid
  with even spacing. This is what separates a tidy product sheet from "boxes drawn around a
  pile." (Implementation: a `_comp_bbox(ref)` → `_frame(members)` → align → `+PAD` pass in the
  generator, so every regen reproduces the alignment; see `gen_sch.py`.)

**Reading direction (signal flow)**
- **Inputs left → outputs right; power at top, ground at bottom.** Lay the sheet so a reader
  follows signal left-to-right. Don't scatter a net's pins randomly across the page.

**Power**
- **GND and the main supply rails use POWER SYMBOLS** (ground glyph down, VCC flag up) — each
  power pin carries its own; never a bare text label for GND/VCC.
- **Derived / intermediate rails** (e.g. `VBAT`, `USB_5V`, a jumpered `VIN`) stay **net labels**
  or a drawn rail — that's the real convention, not everything-as-a-power-symbol.
- Every rail needs a **driver for ERC**: a regulator/MCU `power_out` pin, or a **`PWR_FLAG`**
  on an externally-fed rail, or ERC reports "power input not driven."

**Connections**
- **Net labels** for cross-module nets / buses (`SDA`, `LCD_D0`); **real wires** within a
  functional block. Same-name labels merge — that *is* the connection (a labelled stub is not
  "floating"; prove it with the netlist if unsure).
- **Junction dot at every T** (≥3 wires meeting); none where exactly two cross without
  connecting. Avoid 4-way junctions — offset into two 3-way Ts.
- Bus-style power across co-located pins → one **rail** (trunk + drops + one label), not a
  label per pin (that's the "label-soup / missing-wires" look).

**Components**
- **Refdes + value both visible and non-overlapping**; consistent designator scheme
  (R/C/U/J/SJ…). Mark **DNP / no-fit** clearly. Decoupling caps drawn *next to* their IC.
- **Short, functional pin names** (`SDA`, `D6`) — long `D4/SDA/GPIO5` names collide inside a
  narrow body; the full map lives in the net map. No-connect pins flagged (the ✕).

**Validation**
- **ERC to 0 errors.** Know the warning classes: *lib-not-in-cli-table* is benign;
  *power-input-not-driven* → add a `PWR_FLAG`; *unconnected-wire-endpoint* → a missing junction
  or a stub that misses a pin.

## PCB layout standards

**Stackup & net classes**
- Pick a defined **layer stack**; set **net classes** (power/ground wider than signal); note any
  **controlled-impedance** needs. Trace width follows current (width, not corner angle, sets
  ampacity).

**Placement (decides everything)**
- **Connectors and I/O at the board edge**; the enclosure/usage dictates which edge.
- **Follow current flow**: power-in → regulator → loads, laid out in that order.
- **Group by function, mirroring the schematic blocks** (MCU / power / each peripheral) — this
  is exactly the cluster floorplan (`design-rules.md` → Layered layout): arrange blocks first.
- **Decoupling caps hug their IC power pin**, same side where possible. Sensitive analog /
  crystals away from switchers and noisy digital.

**Routing**
- **Power & ground first**, then short/direct critical nets. **45° or arcs, no acute angles.**
- **Continuous return path** under signals; prefer a **ground plane / pour with via stitching**;
  no isolated copper islands, no necked-down pour.
- A through-hole / castellated pad is a **free layer change** — don't add a via where a THT pad
  already bridges F↔B.

**Clearance / DRC / DfM**
- Meet the **fab's min trace/space/drill/annular-ring**; **0 error-severity DRC + 0 unconnected**.
  Keep copper off the board edge; thermal relief on plane pads.
- **Courtyards must not overlap** (the macro placement gate). Honour any **belly keep-out** for a
  flush-mounted module (no front copper/vias under it — DRC can't see this; `belly_check.py`).

**Silkscreen / assembly**
- Refdes **readable, ≥0.8 mm, off pads and the edge, not buried under a part**; **pin-1 / polarity**
  marks; module body outline on **F.Fab**, not silk. Hide model-only / placement refs.

**Mechanical & outputs**
- Board outline on **Edge.Cuts**; mount holes + keepouts; **fiducials** for assembled boards;
  connector/tall-part keepout to the enclosure wall.
- Fab pack = **gerbers + drill + CPL + BOM**; run the **physical-verify-before-order** checklist
  (real module: pull-ups present?, VIN voltage, header order, land pattern, I²C address).

## Review the result like a reviewer
- **Schematic**: render to PDF and read it — does it flow L→R, are power symbols consistent, any
  floating labels, title block filled?
- **PCB**: read the **per-layer copper plot** (one colour per net, F.Cu | B.Cu) — the routing
  review of record (the 3D render hides copper under mask); then 3D-fit against the enclosure.
- Record dispositions (fixed / accepted-not-a-defect) in `REVIEW.md`.

## Document the decisions (the WHY per block)

A pro open-hardware writeup explains **each block's part choice and its reason** — not just a
netlist. Capture the same in the brief / `REVIEW.md` (and code comments), block by block:
*why this value* (charge R from the cell's C-rate), *why this part* (LDO headroom vs total
load), *why a part is NC* (reserved for an alternate). A good doc order to follow:
**attribution / license / disclaimer → overview → power tree → block-by-block hardware (with
rationale) → mechanical → flashing & test → schematic / PCB / BOM / 3D / downloads**. If you
reused upstream work, **credit it and state the license** up front. The decisions are the part
a reader (and future-you) actually needs; a board nobody can reason about isn't really open.
