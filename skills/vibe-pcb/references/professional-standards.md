# Professional schematic & PCB standards (the conventional checklist)

What makes a schematic/board read as *professional* rather than a beginner dump. These are
industry conventions, not this repo's gotchas (those live in `design-rules.md`). Drive a
board through both. The generators (`gen_sch.py` / `gen_pcb.py`) should *encode* these so
every regen is conformant by construction.

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
