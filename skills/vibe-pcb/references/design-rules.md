# Design rules, validation gates & the recurring findings

The hard-won part. These are the mistakes a module-carrier board makes every time
and the gates that catch them. Sourced from the xiao-carrier (example) review
(`pcb-xiao-tile/kicad/REVIEW.md`).

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
(`github.com/aklofas/kicad-happy`): `make review KH=/path/to/kicad-happy`.

**A DRC "violation" is error- OR warning-severity — don't conflate them.** The report
line `Found N violations` is the *total*; each item ends in `; error` or `; warning`.
Gate on **error-severity + unconnected**; warnings (silk text height, edge clip,
non-mirrored back text) are cosmetic and never block a fab — clean them for tidiness,
not correctness. (Counting total violations as the fail metric false-failed a clean
board on 10 silk warnings — `pcb_check.sh` now splits the two.)

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
| **Pull-up double-fit** | fitting pull-ups the module/sensor already has → parallel value too low | **DNP** pull-ups by default; fit only for a bare sensor. Same logic for decoupling. |

## Findings that are NOT defects (accept + document, don't "fix")

Record these in `REVIEW.md` so a reviewer knows they were considered:

- **No fiducials / no test points** — fine for a hand- or JLC-assembled board this
  size.
- **Unfiltered I/O on a short internal cable** — a ~20 mm internal I²C run to a
  sensor head doesn't need series-R/ferrite/ESD; note it's optional.
- **Component intentionally over the board edge** — e.g. the module's USB-C end
  overhangs to reach the enclosure wall slot; that's by design, say so.
- **BOM 0% MPN coverage** — a prototype BOM carries 立创/JLC placeholder part
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

## Generator conventions (so regen stays clean)

- **Edit `gen_*.py`, never the `.kicad_*`.** The GUI files are outputs; hand-edits
  are lost on the next `make check`. (If you *must* inspect a manual KiCad tweak,
  dump it semantically and fold the intent back into the generator — don't let the
  two diverge.)
- Coordinates are **absolute mm** from a pad dump; the `gen_pcb.py` helpers
  (`place / mhole / trk / via / silk / add_model`) are the whole vocabulary.
- Register project libs via `sym-lib-table` / `fp-lib-table` (emitted by
  `gen_sch.py`) so there's no GUI "rescue" prompt.
- A custom module land (e.g. a 2×7 castellated XIAO footprint) lives in
  `<proj>.pretty/` and is **EST until checked against the official footprint** —
  put it on the brief's verify list.
