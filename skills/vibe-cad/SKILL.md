---
name: vibe-cad
description: >-
  Take a mechanical part / enclosure from a natural-language spec to a parametric
  build123d model, reviewed interactively in the latest CAD Viewer and exported as
  STEP/STL for print or tooling — written for a beginner driving CAD via Claude
  Code. Use when designing or revising an ENCLOSURE / bracket / carrier-shell,
  FITTING a board + modules into a housing, SWAPPING the module/sensor a shell
  wraps, or RESIZING to seat an off-the-shelf part. Key facts this skill encodes:
  the model is one PARAMETRIC python file (a param block = single source of truth +
  importable `build_*()` builders, no side effects); review is the **CAD Viewer**,
  which has NO CAD kernel — it renders `.step` only via a hidden GLB sidecar
  `.<name>.step.glb`, so `build_all.py` must `export_gltf` each part; the viewer is
  vendored by `npx skills install earthtojake/text-to-cad` and is launched/updated
  via `scripts/cad_viewer.sh` (which works around the fixed-port + renamed-launcher
  gotchas). Worked reference: a device shell under `examples/`.
  Upstream: https://github.com/earthtojake/text-to-cad. Sibling of `vibe-pcb`.
---

# Text → CAD (beginner + Claude Code → printable part)

Parametric mechanical CAD for the parts in this repo — mostly **enclosures** that
wrap a `vibe-pcb` board + its modules. You write the intent and the fit numbers;
Claude Code emits a single **build123d** python file, reviews it in the **CAD
Viewer**, interference-checks it against the real boards, and exports STEP/STL.

**Worked reference (copy this):** a device shell under `examples/` (e.g.
[`examples/pager-buddy/cad/`](../../examples/pager-buddy/) — *being filled in*): a
2-part stacked shell with a display/sensor window, snap detents, vents, a bracket
mount, an exploded view, and a 0 mm³ interference check. Read its `README.md` + the
model `.py`; this skill is the *method*, that dir is a *filled-in example*.

## The model is ONE parametric file

Unlike a GUI CAD, the source of truth is a python module with two halves:

1. **A param block** at the top — every dimension as a named constant, derived
   values computed from them (`CAR_TOP = CAR_BOT + CAR_T`). Change a number, the
   whole part moves consistently. This is what a beginner edits.
2. **Importable `build_*()` builders** with **no side effects** — `build_tray()`,
   `build_cover()`, `build_fit()`, `build_exploded()`. Exports live in a separate
   `build_all.py` so the model can be imported by the section / check / view tools
   without writing files.

build123d vocabulary you reuse: `Box / Cylinder / loft` primitives · `Pos / Rot /
Align` placement · `chamfer` (wrap in a `try_chamfer` that retries smaller / skips,
so one bad edge doesn't crash the build) · `import_step` to load a real module STEP
(its frame is **arbitrary** — dump each solid's bbox to discover it, then seat off a
named solid via `max(solids, key=volume)` + `bounding_box()`) · `&` for the
interference check · `Compound(children=[...])` to assemble. Two design rules worth
naming up front: **the print should self-locate each part** (a bore/stop that makes
hand-assembly foolproof — adhesive only *fixes*, never *locates*), and **add the
back plate/cover to `build_fit()`** so a boolean section can prove its bosses/ribs
clear the real parts. See `references/build123d-patterns.md`.

## The loop

```
spec + fit numbers ─► model ─► review ─► fit-check ─► export
 (from the board       *.py     CAD Viewer  check_fit.py   build_all.py
  brief §enclosure)    param    (.step+GLB) 0 mm³ overlap   STEP / STL
                       block     section.py                 (+ GLB sidecar)
```

1. **Spec** — take the fit numbers from the board's brief (`vibe-pcb`
   §enclosure-interlock): board outline, mount-hole spacing, stack height, USB
   exit, aperture/FOV clearances, antenna placement. One set of numbers shared
   across board + shell.
2. **Model** — write/edit the param block + builders. For a module swap, usually
   only the param block + the affected `build_*` change.
3. **Review** — `python build_all.py` (exports STEP + STL + the GLB sidecars),
   then open the **CAD Viewer** (`scripts/cad_viewer.sh <models-dir>`). For a
   dimensioned read, `section.py` draws a labelled X–Z cross-section — that's the
   primary review view (matplotlib 3D can't z-sort, so it's muddy; use the Viewer
   for 3D, the section for measurements).
4. **Fit-check** — `check_fit.py` boolean-intersects every real board/module
   against the shell; expect **0 mm³**. Re-run after any param change.
5. **Export** — `build_all.py` writes `models/*.step` (+ `*.stl` for printing, +
   the hidden `.<name>.step.glb` the Viewer needs). Print orientation and any
   tooling caveats (sink, draft) go in the README.

## Run it

```bash
PY=.venv/bin/python   # build123d 0.10, py3.12
$PY build_all.py            # export STEP + STL + GLB sidecars  (run in the model dir)
$PY section.py              # dimensioned X–Z cross-section PNG
$PY check_fit.py            # board↔shell interference (expect 0 mm³)

# review in the latest CAD Viewer (handles install/update + the launch gotchas):
skills/vibe-cad/scripts/cad_viewer.sh <abs-models-dir>   # prints the URL
```

> **cwd resets between shell calls.** Each tool invocation may start in the repo
> root, so a relative `$PY build_all.py` or `../structure/.venv/bin/python` fails
> with *"no such file or directory"* on the next call. Always `cd <model-dir> && …`
> in the **same** compound command (or use absolute paths). Bit us twice this session.

## The CAD Viewer — update + use (read `references/cad-viewer.md`)

The Viewer is **vendored**, not in-repo: `npx skills install earthtojake/text-to-cad`
drops the bundle (`cad`, `cad-viewer`, `implicit-cad`, `sdf`, `step-parts`, …) into
the gitignored `.agents/skills/` (symlinked for Claude Code). Three things bite
every time — `cad_viewer.sh` and the reference handle them:

- **STEP needs a GLB sidecar.** The Viewer has no CAD kernel; it renders `.step`
  via a hidden `.<name>.step.glb` in the same dir. `build_all.py` must
  `export_gltf(part, ".{name}.step.glb", binary=True)` for every exported part, or
  the Viewer shows "Generated GLB is missing". STL renders natively.
- **Fixed port + lingering server.** It binds a fixed port (4178) and dies with
  `EADDRINUSE` if a prior `--shutdown-after` server is still up — `cad_viewer.sh`
  finds and kills the stale PID first.
- **Launcher renamed.** Newer bundles renamed the npm script `agent:start` → `start`
  (`node backend/server.mjs`); the SKILL.md may still say `agent:start`. The script
  detects which exists.

## Scaffolding a new part

```
hardware/<line>/structure-<name>/
  <name>.py            # the model: param block + build_*() builders (edit this)
  build_all.py         # export STEP + STL + GLB sidecars → models/
  section.py           # dimensioned X–Z cross-section (the measurement view)
  check_fit.py         # board/module ↔ shell interference check
  render_views.py      # rough matplotlib previews (use the Viewer for real review)
  README.md            # decisions, stack-up/assembly, print orientation, EST flags
  models/              # *.step (tracked) + *.stl/.glb (gitignored, regenerated)
  .gitignore           # .venv/ __pycache__/ models/*.stl models/.*.glb
```

Off-the-shelf parts (servos, standoffs, the module itself) come from the
**`step-parts`** catalog instead of being modeled.

## Enclosure conventions (DfM, learned from shipped products)

Patterns a polished consumer enclosure uses — bake these into the param block / builders:

- **Indicator LEDs reach the user through a light pipe, not a hole.** A clear acrylic rod
  (e.g. ⌀2 mm solid round) carries an on-board LED to the shell surface — model the bore + a
  retaining shoulder; the LED never pokes out.
- **Inset the screen/glass behind the front face** so it doesn't scratch when the device is set
  face-down; the bezel overlaps the panel edge.
- **Threaded brass heat-set inserts for screws, not screwing into plastic** — model the insert
  boss (bore + melt relief); **hide the screws** (back-cover screws that also capture the shell,
  not exposed on a show face).
- **Anti-slip: textured surface + rubber feet** on the base (model recesses for the feet).
- **Self-locating assembly + an exploded view.** Every part should drop into one position
  (bore/stop/keyed); ship an `build_exploded()` view **and a numbered mechanical BOM** (screws
  `M1.4×N`, gaskets, light pipe, inserts, battery + carrier) so a builder can assemble it.
- **State print-relevant specs**: material, wall, the light-pipe rod stock, insert size, feet.

## When to reach for this vs others

- Enclosure / bracket / mechanical fit → **here**.
- The **board** inside it → `vibe-pcb` (the two share one set of fit numbers).
- Just *viewing* an existing `.step`/`.stl`/`.gcode` → the `cad-viewer` skill
  directly (this skill wraps it for the design loop).
- Slicing a mesh to G-code / printing → `gcode` / `bambu-labs`.

## Keeping this current (living doc)

This skill exists to **compound** hard-won CAD experience so the next part is
easier. When a new enclosure/part surfaces a new gotcha (a viewer quirk, a
build123d idiom, a DfM lesson), a fix, or a better practice, **fold it back in**
(SKILL.md / `references/` / `scripts/`) and commit it with the work — don't let a
lesson live only in a chat. Same for `vibe-pcb`.
