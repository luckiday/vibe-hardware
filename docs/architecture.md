# Architecture

How vibe-hardware is put together, and *why* it's shaped this way. Read this once to
get the mental model; the day-to-day method lives in each skill's `SKILL.md`.

## The mental model

A small embedded product is three things that must agree:

```
            ┌──────────────┐
   spec  ─► │  fit numbers │ ◄─ one source of truth: board outline, stack height,
   (prose)  │  + net map   │     mount holes, connector/USB exits, sensor/display
            └──────┬───────┘     window; and the pin↔signal net map
                   │
      ┌────────────┼────────────┐
      ▼            ▼            ▼
  firmware       PCB        enclosure
 (vibe-firmware)(vibe-pcb)  (vibe-cad)
   pins +        the board   the shell that
   behavior      that wires  holds the board
                 it           + exposes ports
```

The **net map** is shared by firmware ↔ PCB (same pins, same I²C address). The **fit
numbers** are shared by PCB ↔ enclosure (the board outline and connector positions are
the shell's pockets and cutouts). Change a number once in the spec and all three move —
that's the whole point of keeping sources as small parametric files.

## Two principles

1. **Generate by script, not by GUI.** The sources of truth are generators /
   parametric files — `gen_sch.py` + `gen_pcb.py` (KiCad via `pcbnew`), one build123d
   `.py` (the enclosure), config-as-code (firmware). The `.kicad_*` / STEP / build
   artifacts are *outputs*: diffable inputs in, reproducible outputs out. You never
   hand-place a track or push a vertex.
2. **Review in the browser, not the heavyweight app.** Every step has an interactive
   `localhost` review (`pcb_view.sh` → 2D layers + 3D board; `cad_viewer.sh` → the
   enclosure) so you never boot KiCad/FreeCAD just to look. If a task *needs* the GUI
   to do, the skill isn't finished.

## Repo layout

```
skills/<name>/        one skill = one half of the build
  SKILL.md            frontmatter (name + "use when…") + the method (the loop)
  references/*.md     the gotchas / deep lessons, loaded on demand (progressive disclosure)
  scripts/*           portable bash/python tools (the loop, automated)
examples/<name>/      worked end-to-end builds (the filled-in templates)
docs/                 this folder — the map, getting-started, roadmap
assets/               images/GIFs for the docs
```

### Anatomy of a skill (progressive disclosure)

- **frontmatter `description`** — when to load the skill + the key facts/gotchas in one
  paragraph (so an agent picks it up at the right moment).
- **body** — the loop: spec → generate → validate → review → output, with the hard
  rules inline.
- **`references/`** — pulled in only when needed (design rules, fab hand-off, viewer
  gotchas, build123d patterns). Keeps the body short.
- **`scripts/`** — the loop as commands. Self-contained: a skill's scripts never import
  another skill's code (cross-skill links are prose hand-offs only).

## The data flow (PCB example)

```
spec/net map ─► gen_sch.py + gen_pcb.py ─► *.kicad_sch / *.kicad_pcb
                                              │
                          pcb_check.sh ──►  ERC + DRC (0 errors / 0 unconnected)
                          belly_check.py ─► no copper under a flush module
                          pcb_view.sh ────► browser: 2D layers | 3D board
                          fab_export.sh ──► gerbers + BOM + CPL → JLCPCB
```

`vibe-cad` is the same shape (param file → `build_all.py` → STEP/STL + `check_fit.py`
→ `cad_viewer.sh`), and `vibe-firmware` too (config + code → pinned build → flash +
monitor → OTA).

## Dependencies

- **KiCad 10** — `kicad-cli` + its bundled python (`pcbnew`). Not pip-installable.
- **build123d** — a venv (`requirements.txt`).
- **Firmware toolchain** — pinned per platform (ESP-IDF/PlatformIO/Arduino-CLI).
- **Interactive 3D / CAD Viewer** — vendored from
  [`earthtojake/text-to-cad`](https://github.com/earthtojake/text-to-cad)
  (`npx skills install …`); the PCB 2D viewer uses [KiCanvas](https://kicanvas.org) and
  the 3D pane uses [`<model-viewer>`](https://modelviewer.dev), both loaded in-page.

See the [roadmap](roadmap.md) for where this is headed.
