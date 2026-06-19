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

## Layered layout & the feedback loop (beating "③ place & route")

The model is weak at one-shot absolute-coordinate geometry — it thinks in **relations**,
but `place(x,y)` / `trk([…])` throw the relations away and keep only the numbers, so layouts
are brittle and look amateur. Don't auto-solve ③; **change the representation + close a
visual loop** (full rationale in SKILL.md → *Layered layout*). Three moves:

**1 — Clusters as first-class objects: a TWO-LEVEL floorplan.** Split layout into a
**macro** level (where each block sits) and a **micro** level (parts within a block):

- **MACRO** — each cluster has an *origin*; you arrange the coarse layout by moving whole
  blocks. Move a cluster as a **unit** by editing ONE origin line — every member part *and*
  the cluster's box follow together. This is the coarse step you do first.
- **MICRO** — a part's home is `cluster.at(dx,dy)`: a slot *relative to the origin*.
- **The box is AUTO-derived from the members' real geometry** (pad extents), not guessed —
  so the coarse stage shows true block sizes to pack against. Origins can be chosen to
  reproduce an already-routed board's coords exactly → adopting this **moves nothing**
  (DRC stays 0/0/0); the win is the relations live in the source and blocks move as one.

```python
class Cluster:
    all = {}
    def __init__(self, name, ox, oy): self.name,self.ox,self.oy,self.members = name,ox,oy,[]; Cluster.all[name]=self
    def at(self, dx, dy): return (self.ox+dx, self.oy+dy)      # MICRO slot, relative to origin
    def add(self, fp): self.members.append(fp); return fp      # register part -> auto box + face
    def box(self, pad=0.3): ...                                # real bbox from member pad extents
PWR = Cluster("PWR", CX, CY)                                   # MACRO origin (move this -> all follow)
PWR.add(place(..., *PWR.at(-7,+3), 90, {...}, flip=True))     # C1 = origin + slot
```

The coarse→fine loop is then: in `STAGE=floorplan` read the **box sizes** printed per
cluster (`box PWR[B] 9.5 x 9.6 mm @ origin (100,100)`) and the rendered boxes, **nudge
origins to pack the blocks** (whole clusters move), watch the macro gate, then place + route.
`MOVE="NAME:dx,dy"` (coarse stages only — never the routed full board) A/Bs a macro move
without editing code, so you can feel the HPWL change before committing.

**2 — Stage the generator; render the skeleton; read it back.** Gate `gen_pcb.py` on a
`STAGE` env so it can stop early and emit a *skeleton* image for the model to read before any
copper is committed:

```python
STAGE = os.environ.get("STAGE", "full")     # floorplan | place | full
… place footprints …
if STAGE == "floorplan": draw_cluster_boxes(); board.Save(out); sys.exit()   # boxes+labels only
… (ratsnest is automatic from net assignment) …
if STAGE == "place":     board.Save(out); sys.exit()                          # parts+courtyards+ratsnest, NO trk/via
… trk()/via() copper …                                                       # full
```

Render each stage headless and **look at it**: `kicad-cli pcb render … --side top` (or the
2D plot for ratsnest/courtyards), then read the PNG. `scripts/pcb_skeleton.sh <proj> <stage>`
wraps this. The loop is: render floorplan → read → fix placement → render place → read →
route → render full → read. Perception-in-the-loop, not one blind shot.

**3 — Cheap numeric gates, MACRO + micro (no render needed).** Fail fast on bad placement,
in `pcbnew`, in milliseconds — print on every regen:
- **MACRO: same-face cluster-box overlap** — do any two clusters' auto-boxes intersect on
  the same face? The coarse-floorplan check; arrange origins until it's empty before you even
  place parts. (Face-aware: passives on B *under* the MCU on F don't count.)
- **micro: pad-extent overlap** (two same-face footprints' pads intersect → parts collide)
  and **HPWL** (half-perimeter wirelength — sum each net's pad-bbox half-perimeter; the
  classic placement-quality proxy; minimise before routing — watch it rise when a `MOVE`
  worsens the layout). (`ratsnest total length` from `board.GetConnectivity()` is an
  equivalent proxy if you prefer the air-wire sum.)

**Routing half — freerouting is a real CLI.** Placement has no auto tool (→ the loop above),
but routing does: `kicad-cli pcb export specctra <proj>.kicad_pcb -o b.dsn` →
`freerouting -de b.dsn -do b.ses` → `kicad-cli pcb import specctra … b.ses`. Quality needs a
cleanup pass and a JRE must be installed; for a trivial board keep scripted `trk`. Either
way the model's job is to **read the routed render and accept/reject**, not to place copper blind.

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
  put it on the brief's verify list.
