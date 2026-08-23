# Design rules, validation gates & the recurring findings

The hard-won part. These are the mistakes a module-carrier board makes every time
and the gates that catch them. Sourced from the xiao-carrier (example) review
(the per-project `kicad/REVIEW.md`).

## Validation gates (drive every board through these)

| Gate | Command | Pass = |
|---|---|---|
| ERC | `kicad-cli sch erc <proj>.kicad_sch -o <proj>-erc.rpt` | **0 errors** (lib-not-in-cli-table warnings are benign) |
| DRC | `kicad-cli pcb drc <proj>.kicad_pcb -o <proj>-drc.rpt` | **0 error-severity · 0 unconnected** (warnings reported, not failing) |
| belly keep-out | `belly_check.py <proj>.kicad_pcb x0 y0 x1 y1` | no F.Cu / vias under a flush module (DRC can't see this) |
| sch↔pcb cross | kicad-happy `cross_analysis.py` | no findings (refs / values / nets consistent) |
| EMC | kicad-happy `analyze_emc.py` | risk score noted; advisories dispositioned |

`pcb_check.sh` runs gen → ERC + DRC + render (+ the belly gate if `BELLY_BOX="x0,y0,x1,y1"`
is set). The deep review (cross/EMC) needs **kicad-happy**
(<https://github.com/aklofas/kicad-happy>): `make review KH=/path/to/kicad-happy`.

**A DRC "violation" is error- OR warning-severity — don't conflate them.** The report
line `Found N violations` is the *total*; each item ends in `; error` or `; warning`.
Gate on **error-severity + unconnected**; warnings (silk text height, edge clip,
non-mirrored back text) are cosmetic and never block a fab — clean them for tidiness,
not correctness. (Counting total violations as the fail metric false-failed a clean
board on 10 silk warnings — `pcb_check.sh` now splits the two.)

**Verify the gate parser against the actual report format before trusting a 0.**
kicad-cli ends violation lines with `; error`, but pcbnew's `WriteDRCReport` (the
KiCad-7 fallback) writes GUI-style `Severity: error` lines — a grep for the former
read **444 real violations as zero** on a real board, and two routing
sessions built copper on top of phantom-clean DRC. `drc_report.py` now normalizes
its output to match; if you ever add another report source, run one DELIBERATE
short through it first and watch the number move.

**But treat a DRC *error* as real until proven otherwise.** On xiao-carrier (example) the DRC
flagged a trace crossing another net on the same layer — a true short, not noise. Fix
by rerouting, never by waiving.

**Belly keep-out needs its own gate — DRC won't catch it.** "No front copper under the
module" is mechanical, not electrical, so it passes DRC even when violated. Run
`belly_check.py` (or `BELLY_BOX=...` in `pcb_check.sh`) after every regen.

## The recurring findings (and the fix)

| Tag | What bites | Fix |
|---|---|---|
| **Power-default-open** | a solder-jumper supply left **open** by default → board ships dead | default the supply jumper **closed (Bridged)**; it's live out of fab |
| **Belly short** | a flush-soldered module has exposed back-pads (thermal/JTAG/BAT/USB) that short to any carrier copper under its body | **no F.Cu and no vias under the module footprint**; route under-belly nets on **B.Cu**, keep front copper + vias in the margins; relocate passives out of the belly box. Put the keep-out box (x/y) in a comment in `gen_pcb.py`. |
| **Value mismatch** | schematic vs PCB component values diverge as you edit two generators | keep `gen_sch.py` and `gen_pcb.py` values in lockstep; `cross_analysis` verifies |
| **Silk DRC** | silk text too small / module ref-des & outline clipping pads or board edge | text height **≥ 0.8 mm**; module body outline on **F.Fab** (not silk); **hide model-only / placement refs**; keep silk off pads and the edge |
| **Courtyard-less land** | a hand-drawn or generated footprint with no F.CrtYd makes `courtyard_overlaps()` a **no-op** — the gate passes because there is nothing to intersect, and a part ends up under a connector or switch body | draw a courtyard in every `gen_footprints.py` land, and treat "part has no courtyard" as a gate failure, not a skip. A stock KiCad land is not automatically safe either: the Cherry MX courtyard is 13.29 mm across a **14 mm** housing, so leave margin near tall mechanical parts |
| **Wire-length ≠ routability** | optimising a placement for total wire length and watching routing get *worse* | measured on a 37-part board: 1292 mm → 591 mm of wire took unroutable traces from 14 to **22**, because packing removes the channels the router needs. Score placements on the **router's actual output**; keep `hpwl` as a regression tracker, not a target. Clearance is the lever with a real optimum (0.5/2/3.5/5/6.5 mm → 22/18/12/12/33 failures on that board) |
| **Pull-up double-fit** | fitting pull-ups the module/sensor already has → parallel value too low | **DNP** pull-ups by default; fit only for a bare sensor. Same logic for decoupling. |

## Findings that are NOT defects (accept + document, don't "fix")

Record these in `REVIEW.md` so a reviewer knows they were considered:

- **No fiducials / no test points** — fine for a hand- or JLC-assembled board this
  size.
- **Unfiltered I/O on a short internal cable** — a ~20 mm internal I²C run to a
  sensor head doesn't need series-R/ferrite/ESD; note it's optional.
- **Component intentionally over the board edge** — e.g. the module's USB-C end
  overhangs to reach the enclosure wall slot; that's by design, say so.
- **BOM 0% MPN coverage** — a prototype BOM carries LCSC/JLC placeholder part
  numbers filled at order time; the review is a *consistency* check, not a
  datasheet-verified one.
- **Carrier missing decoupling on the module's own rail** — the module carries its
  own regulator + decoupling; the carrier only decouples what it adds.
- **Acute angle in a trace** — does **not** affect power delivery (current capacity is
  set by trace *width*, not corner angle; a sensor's tens of mA on 0.3 mm has huge
  margin). The only historical worry is the etch "acid trap", a non-issue on JLC's
  modern process. Round it to two 135° bends if you want it tidy — not for function.

## Routing a module-carrier on 2 layers (the hard part)

The belly keep-out + a 2-layer board makes routing the real puzzle. Tactics that
worked on xiao-carrier (example):

- **Everything under the belly goes on B.Cu; F.Cu + vias live only in the margins**
  (the strips past the pad rows) and the left-of-connector zone. The module is on F,
  so B copper under it never touches the module — that layer is "free" under the belly.
- **A module's THT pad is a free layer change.** Castellated/through-hole module pads
  exist on both layers, so a net can switch F↔B *at the pad* with **no separate via** —
  don't add a via where a THT pad already bridges the layers. (Removing one such via
  is exactly how the carrier dropped to 2 vias, both off-body.)
- **Relocate DNP parts to open a route.** Pull-ups/decoupling that are DNP have no
  fixed home — moving one (e.g. R1 out of a crowded pad column) can make a signal reach
  it without crossing the power cluster. Cheaper than re-placing real parts.
- **Drop unused features to simplify.** Question every net/jumper: an unused supply
  option (a 5V alt the breakout never needs) is dead copper that also fought the
  routing. Deleting it shrank the net count and freed the belly. Confirm with the user,
  then remove from *both* generators (and re-mark the module pin no-connect).
- **Route, regen, DRC, repeat** — and check the belly gate each loop. A reroute that
  looks fine often crosses a cluster trace; let DRC find it rather than eyeballing.

## Place for the product, then for the router

A layout that passes every gate can still read as an engineering board. The
recurring shape of the mistake: the parts a USER touches get placed wherever
routing was convenient, and the board's "face" ends up being whatever was left
over. Worked before/after: [`examples/mic-macropad`](../../../examples/mic-macropad).

Ask these before the placement gates, because none of them is a DRC question:

- **What is the face?** Whatever the user looks at or touches (a key row, a
  display, a knob) is the composition; centre it and give it an even bezel.
  Everything else serves it.
- **Which way does the cable leave?** A connector on the edge facing the user
  is a cable across the desk. Ports belong on the edge away from the hands —
  and the port position is a `constraints.yaml` number, so the shell agrees.
- **Is this control for the user or for me?** Reset and boot buttons are
  bring-up hardware; tuck them beside the module. A debug header is *never*
  product hardware — four pogo pads cost nothing and leave a flat surface.
- **What does this part need to be near, physically?** A MEMS mic wants the
  user and the enclosure port, and wants distance from the USB switching edge;
  an ESD array wants to be at the connector, before the protected line goes
  anywhere. If a part sits somewhere odd, the reason is usually a routing
  workaround that a ground pour has since made unnecessary.

The test that catches most of it costs one command: render the board in 3D
(`kicad-cli pcb render --perspective`) and ask whether it looks like a product
someone would pick up. Copper-level gates cannot answer that, and a courtyard
gate cannot see a part tucked under a 14 mm switch housing.

## Layered layout & the feedback loop (beating "③ place & route")

The model is weak at one-shot absolute-coordinate geometry — it thinks in **relations**,
but raw `place(x,y)` / point lists throw the relations away and keep only the numbers, so
layouts are brittle and look amateur. Don't auto-solve ③; **change the representation +
close a visual loop**. All of this is SHIPPED CODE now — `scripts/pcblib/` — proven on a
four-layer ESP32-S3 build. Three moves:

**1 — Clusters as first-class objects: a TWO-LEVEL floorplan** (`pcblib.Cluster`).
- **MACRO** — `Cluster(brd, "AUDIO", (16, 30))`: the origin is the ONLY tuned number;
  move it (or `MOVE="AUDIO:-2,3"` env, coarse stages only) and every member follows.
- **MICRO** — members placed by `cl.place(..., at=(dx,dy))` slots or, better, by
  relations off real courtyards: `beside(u5, c4, side="right", gap=0.7)`,
  `align_pads(ic, "8", cap, "1")`, `row([...])`, `at_edge(brd, j1, "usb_c")` (the
  port x/y comes from `constraints.yaml`, never a literal).
- `cluster.bbox()` derives from member courtyards — true block sizes to pack against.
- `Cluster(..., pinned=True)` for groups whose members sit at CONTRACT positions
  (panel buttons, edge connectors): they aren't free-floating blocks, so they skip the
  cluster-overlap gate; the courtyard gate still covers their real collisions.

**2 — Stage the generator; render the skeleton; read it back.** `gen_pcb.py` honors
`STAGE=floorplan|place|full` and
`scripts/pcb_skeleton.sh <proj> <stage>` renders each stage to a PDF+PNG you READ.
The loop: floorplan → read → nudge origins → place → read → route → full → read.
Perception-in-the-loop, not one blind shot.

**3 — Numeric gates (`pcblib.gates.scorecard`), printed on every regen.** Hard fails:
**courtyard overlaps** (same-face body boxes intersect), **cluster overlaps** (MACRO
boxes collide), **keepout violations** (parts/copper inside a contract keepout —
generalizes the belly check; `keepout_allow=("U1",)` exempts the RF module from its
own antenna strip). Tracked, not gated: **HPWL** (half-perimeter wirelength, the
placement-quality proxy — watch it move when you `MOVE=` a cluster). A generator that
fails its own scorecard exits nonzero, so `pcb_check.sh` stops before copper.
Two implementation gotchas encoded in `pcblib.layout.Part.courtyard()`: antenna
modules draw their far-field clearance on F.CrtYd (the WROOM's spans ±24 mm — gate on
the body box, keep the antenna rule as a contract keepout), and KiCad 7's
`GetCourtyard()` is empty off-board (`BuildCourtyardCaches()` segfaults there).

**4 — Placement serves routing: reserve channels.** Before routing, name the bus
channels in comments and keep support passives OUT of them (one board kept
x≈9.5–13.5 clear for the I²S/I²C trunks down both codecs' left flanks; ref/bias caps
live in one row above the codec instead of scattered around it). A route that fights
means a part should move — placement is cheaper than copper. QFN 0.4 mm pitch: 0.2 mm
stubs, straight out of the pad row, bend ≥0.5 mm away.

**Routing half — freerouting is a real CLI, but the naive `kicad-cli … specctra` form is a
hallucination.** Placement has no auto tool (→ the loop above); routing you hand to freerouting.
The validated headless recipe + every gotcha that bit lives in **`references/autorouting.md`**,
driven by `scripts/autoroute.sh` — **read that, don't reconstruct the pipeline from memory.** The
ones that cost real time: `kicad-cli` has **no** Specctra subcommand (go through pcbnew
`ExportSpecctraDSN`/`ImportSpecctraSES`); the freerouting version ↔ JRE ↔ display pick is a trap
(1.9.0 plain on a workstation vs 2.x + JDK 25 for headless CI); the belly keep-out must block
**tracks**, not just zone fills, or the router lays F.Cu under the module; and the `.ses` saves
~10 s *after* "completed". **Accept a route by committing the `.ses` as `routing.ses`** —
`pcblib.route.apply_ses` replays it in the full stage, so the routed board regenerates from
committed sources. When no JRE/jar is available, route by script with the pad-anchored
vocabulary (`wire(brd, net, [a.pad(3), b.pad(1)], bend="x")` / `via` / `path` — endpoints are
pad lookups, waypoints relative; GND via `gnd_pours()` + stitching, never point-to-point) in a
scripted `routing.py`. Either way the model's job is to **read the routed render and
DRC report and accept/reject**, not to place copper blind.

**Read routing per layer — the copper plot is the review of record.** The 3D render hides
copper under soldermask, so a 2D **per-net, per-layer** plot (one colour per net, F.Cu | B.Cu
split) is how you actually check the route — *nothing of a different net crosses on the same
layer* (the same short DRC flags). Regenerate it whenever the board changes (it goes stale
silently): `kicad-cli pcb export pdf <proj>.kicad_pcb --mode-multipage --layers F.Cu,B.Cu,Edge.Cuts`,
or a matplotlib per-net plot for colour-by-net.

## Schematic standardization — the same idea on the sheet

The sheet reads amateur for the same reason: scattered parts + a net **label stuck on every
pin** (label-soup that looks like "missing wires"). Standardize with a small fixed vocabulary
so it reads as blocks with real connections — and keep it ERC-clean *by construction*:

- **Module = a grid cell.** Group each module's symbols in its own region (MCU | CONN row,
  POWER cluster below); a module/sensor swap moves one block.
- **Short pin display names.** Long `D4/SDA/GPIO5`-style names collide inside a narrow body —
  show the silk alias (`SDA`, `D6`); the full GPIO map lives in the net map, not the symbol.
  (ERC keys off pin number + type, never the display name — renaming is free.)
- **Shared cluster power net → a real RAIL, ONE label.** A net on ≥2 co-located pins
  (the passives' `VIN`, the caps' `GND`) is drawn as an actual wire — a trunk + a drop to each
  pin — with a *single* net label, the standard "power distribution" look, instead of a label
  per pin. **Add a `(junction)` where a drop T's the trunk** (≥3 wires meeting need one, or the
  pin reads "not connected"); two end pins land on the trunk's endpoints and need none.
- **Signals / cross-module nets stay net labels** (`SDA`/`SCL` between MCU and connector) —
  conventional, and cheaper than routing a wire across the sheet.

## Generator conventions (so regen stays clean)

- **Edit `gen_*.py`, never the `.kicad_*`.** The GUI files are outputs; hand-edits
  are lost on the next `make check`. (If you *must* inspect a manual KiCad tweak,
  dump it semantically and fold the intent back into the generator — don't let the
  two diverge.)
- Coordinates are **absolute mm** from a pad dump; the `gen_pcb.py` helpers
  (`place / mhole / trk / via / silk / add_model`) are the whole vocabulary. Prefer
  expressing placement through **clusters** (above) so the source carries the *relations*,
  not bare numbers — anchors can reproduce the same mm, so it's a zero-risk refactor.
- Register project libs via `sym-lib-table` / `fp-lib-table` (emitted by
  `gen_sch.py`) so there's no GUI "rescue" prompt.
- A custom module land (e.g. a 2×7 castellated XIAO footprint) lives in
  `<proj>.pretty/` and is **EST until checked against the official footprint** —
  put it on the brief's verify list. **Verify the pad-NUMBER → physical-position map,
  not just the outline/pitch.** A reversed bottom row (pad 9/10 vs 12/13) is geometrically
  perfect and **passes ERC/DRC** — the net is electrically valid, it just lands on the wrong
  pin. On a real carrier this silently routed `+3V3`/`GND` onto two GPIO pads; the sensor
  enumerated on I²C but its measurement core never ran (powered through a GPIO). ERC/DRC
  can't catch it — only a pinmap-vs-datasheet cross-check can.
