# 3D fit-check + fab hand-off

The last two steps: prove the board fits its enclosure in 3D, then package the
order. Sourced from `pcb-xiao-tile/` (both a JLCPCB gerber set and an LCEDA
three-piece set exist there).

## 3D fit-check (and the bridge to `vibe-cad`)

The PCB and the enclosure are designed against the **same numbers** (stack height,
mount-hole spacing, USB exit, connector/aperture clearances — the brief §7). Catch
disagreements in 3D before either is ordered/printed.

1. **Model the real parts.** Generate `.step` for the module, the sensor breakout,
   the connector, standoffs, and a reference baseplate with **build123d**
   (`kicad/models/gen_*.py` → `*.step`). Off-the-shelf parts can come from the
   `step-parts` catalog instead of modeling them.
2. **Load into the board's 3D view** with `add_model(fp, path, offset, rot)` in
   `gen_pcb.py`, then render (`kicad-cli pcb render`, e.g. top / front / iso /
   section / stack views). The front/section views are where you confirm clearances
   (sensor can vs window gap, standoff height vs hang depth).
3. **The enclosure is the `vibe-cad` route.** The shell that holds this board is
   a separate build123d project (see `hardware/.../structure-xiao-carrier/` and the
   `vibe-cad` / `cad-viewer` skills). Feed it the brief's interlock numbers; it
   feeds back the pocket / standoff / slot geometry. Keep a single set of numbers
   across both — when the stack height changes, both move.

## ⚠️ Do NOT round-trip KiCad → EasyEDA (LCEDA)

The tempting wrong path (it cost a full debugging session): importing the KiCad
project *into* EasyEDA to "finish"/order it. Its KiCad importer is broken —

- **`component … missing "footprint" property` (fatal)** — KiCad footprint refs (`Resistor_SMD:R_0603…`,
  a project-private land) don't resolve in EasyEDA's libraries → empty footprint.
- **refdes mangled** to `$2I2…` and **schematic↔PCB netlist desync** (`netlist mismatch`)
  when sch + pcb are imported separately.

None of this is a defect in *your* board — KiCad ERC/DRC are clean. It's the importer.
**For JLC fab you don't need EasyEDA at all: upload Gerbers.** If someone insists on
editing in EasyEDA, import the **PCB only** (`.kicad_pcb` carries footprint geometry +
nets inline; no library lookup) — never the separate schematic.

## Fab hand-off — two paths (this repo uses both)

### A. KiCad → JLCPCB (gerbers + assembly) — the default
One script packages everything from the validated `.kicad_pcb`:

```bash
# run in the project kicad/ dir; extra args = refs you hand-solder (kept off the SMT CPL)
skills/vibe-pcb/scripts/fab_export.sh <proj> A1 J1
```

It writes `fab/<proj>-gerber-jlcpcb.zip` + `-CPL-jlcpcb.csv` + `-BOM-jlcpcb.csv` and
bakes in the gotchas that bit us hand-rolling it:

- **drill uses absolute origin** so it registers with the gerbers.
- **model-only / 3D-preview footprints are dropped from the CPL** — a reference
  baseplate or breakout-model footprint has no real pads (empty Package) and must not
  go to the pick-and-place. (`fab_export.sh` filters empty-Package rows automatically.)
- **CPL Mid Y is negated** (KiCad pos is Y-up; JLCPCB wants it flipped).
- **DNP/DNF parts are not placed** by default (value contains `DNP`/`DNF`);
  `INCLUDE_DNP=1` overrides if you do want the pull-ups/decoupling fitted.
- **hand-soldered parts** (the module A1, a THT header J1) are excluded via the args.
- BOM `Footprint` is mapped to JLC names (`C0805`, `R0603`); **fill the LCSC #s**
  before an SMT order (choose Basic/Preferred parts → no extended-part fee).

Then: jlcpcb.com → **Gerber upload** (the `.zip`). For bare boards that's the whole
order; for SMT also upload the CPL + BOM. (See `pcb-xiao-tile/kicad/fab/` for output.)

### B. LCEDA / LCSC three-piece (the hand-off "of record" here)
For a hand-drawn-in-EDA or fully-SMT-by-JLCPCB order, the canonical hand-off is three
files, generated one level up from `kicad/`:

- `<proj>_brief.md` — the spec (the human reads this to draw/verify)
- `<proj>_outline.dxf` — the board outline (from `<proj>_outline_gen.py`, via
  `ezdxf`; the `pcb/.venv` has ezdxf + matplotlib)
- `<proj>_bom.csv` — BOM with LCSC part numbers

The KiCad project still exists in parallel **purely to ERC/DRC/EMC-verify** the
electrical design — even when the order ships via LCEDA, KiCad is the proof the
netlist is sound.

> Pick the path per board: JLCPCB gerbers when KiCad is the master; the LCEDA
> three-piece when a person finishes layout in EasyEDA. Both are legitimate; state
> which is "of record" in `kicad/README.md`.

## Before you click "order" — physical verification

The generators are clean, but the **module reality** isn't verified by any tool.
Walk the brief's §10 EST checklist against the real hardware (photo / calipers /
multimeter):

- module already has I²C pull-ups → keep yours DNP
- VIN is direct-3V3 vs 5V+LDO
- sensor header **actual** line order vs the assumed net-map order
- module land pattern / castellation row pitch vs the official footprint (your
  `.pretty` land is EST)
- mount-hole spacing vs the enclosure standoffs
- I²C address vs firmware (a swapped sensor often shifts it)
- connector pitch / count / pin length (reaches through both boards)

A clean DRC says the copper is self-consistent; it says **nothing** about whether
the land matches the part you'll actually solder. That's what this checklist is for.
