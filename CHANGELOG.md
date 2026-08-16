# Changelog

Notable changes to vibe-hardware. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions aim for
[SemVer](https://semver.org/).

## [Unreleased]

### Changed
- **`vibe-industrial-design`** — light bars and finals. The in-browser path tracer is
  **retired** from the method (finals come from Blender/Cycles; the browser stays raster;
  its gotchas 22–24 are kept as generic multi-frame-renderer lessons). New in the Blender
  scripts: a **purpose-built light-bar material** (`lightbar_material` — Light Path splits
  camera-ray strength ≈7 from bounce strength ≈160, so the bar reads as a lamp *and* really
  lights the wall; milky PMMA base so unlit is `lit=0`), **compositor bloom**
  (`enable_bloom`; Blender 5.x Glare facts recorded — socket-driven params, display-name
  menu values, `NodeGroupOutput` instead of `CompositorNodeComposite`), a **studio dimmer**
  (`set_ambient`) and a **dim-room shot pair** (`hero-dim-off/on`, `front-dim-on`) — the
  honest way to show what a light bar looks like. `ID_LIGHTBAR_CAM/LIGHT` env overrides for
  tuning at low samples.

### Added
- **`vibe-industrial-design`** — a seventh skill, for the product's *appearance* (ID/CMF)
  before or beside `vibe-cad`. Encodes the loop that took a wall-mounted device through
  three ID versions with an owner iterating by AI look images: **measure the image into
  tagged numbers** (px/mm from one anchor, brightness scans for edges/seams, a circle fit
  for corner radius, run-length pitch for perforation with hex-vs-square from the row/column
  ratio, patch means for CMF start values — `scripts/measure_ref.py`); a single `params.js`
  with provenance tags (`[ref]/[std]/[eye]/[own]/[vN]`); a script-generated three.js scene
  (outline × profile body, true plates with real holes, one material per part, procedural
  textures) reviewed in the browser and exported by URL (`?sheet=1&save=1`, `&pt=1` for the
  path tracer); GLB → Blender Cycles with a **hand-tuned `studio.blend` that is extracted
  and reused** across regenerations, materials re-attached by object name
  (`scripts/blender_render.py` / `blender_extract_studio.py` / `blender_shots.py`); and a
  report method (markdown authority + generated .docx snapshot + per-version change list
  and open questions). `references/threejs-scene-gotchas.md` carries the 25 gotchas — the
  headline one: **pause the interactive rAF loop during export**, or the path tracer's
  yields let the frame loop re-sync it to another camera and tiles come out looking like
  material-index corruption (random per run, only when the tab is visible).
- **`vibe-voice`** — a fifth skill, and the first that is a *channel* rather than a domain:
  the agent **speaks** the hands-on steps (bring-up, flashing, probing a test point,
  test-fitting a print) for the moments the other loops hand control back to a human and
  the terminal is not being read. Encodes the dual-channel split (speak the action and the
  timing; print the commands, hex IDs, and expected output), a **preflight** that renders
  and *measures* a sample because a text-to-speech command that exits 0 can still be mute
  (an English voice fed Chinese text exits 0 and emits 0.4 s of noise), blocking utterances
  for pacing with an explicit-`sleep` rule for real durations, and confirmation by
  **polling a machine-observable signal** (a serial-log line) over asking "did you press
  it?" — always capped, with a turn-end fallback. Ships `scripts/speak.py` (stdlib-only,
  pluggable backends: macOS `say` verified, Linux/Windows honest skeletons) plus
  `references/confirm-channels.md` and `references/platforms.md`.
- `vibe-pcb`: **`scripts/pcblib/`** — the relational layout library ("relations in,
  coordinates out"): contract loaders (`constraints.yaml`/`pinmap.yaml`/`parts.yaml` —
  the latter is the single net source both generators derive from), `Board` drawn from
  the cad↔pcb contract, courtyard-computed relations (`beside`/`align_pads`/`row`/
  `at_edge`), `Cluster` floorplanning with real bboxes + `MOVE=` nudging, numeric
  placement gates (courtyard/cluster overlap, contract keepouts, HPWL) behind an
  honest `scorecard()`, `placement.json` evidence export, a `parts.yaml`-driven
  schematic writer, and computed copper (`wire`/`via`/`path`, decoupling fanout,
  GND pours, freerouting `.ses` replay).
- `vibe-pcb`: `scripts/drc_report.py` (pcbnew-API DRC for kicad-cli < 8) and
  `scripts/_kicad_env.sh` (tool auto-resolution + CLI feature detection — ERC skips
  loudly, DRC/render fall back, so the gates run on KiCad 7 through 10).
- `vibe-cad`: shipped the computational-geometry scripts the docs only described —
  `cad_contract.py` (stdlib constraints loader), `check_fit.py` (generic
  `fit_solids()` interference gate), `section.py` (dimensioned cross-section PNG),
  `patterns.py` (hex-packed speaker grille with asserted open-area ratio, heat-set
  bosses, USB-C funnel).
- `vibe-plm`: `plm_check.py` now verifies contract **contents**, not just existence —
  pinmap ↔ firmware header `#define`s, constraints ↔ `placement.json` drift within
  `tolerance_mm`, GPIO lint (duplicates, ESP32-S3 strapping pins unless `strap_ok`,
  flash/octal-PSRAM reserved pins, native-USB pins), and `{path, kind}` mapping-form
  interfaces for generated evidence artifacts.
- `vibe-cad`: `references/usb-connector-cutouts.md` — how to cut USB port openings in an
  enclosure wall. Encodes the lesson that the opening must clear the **receptacle** on the
  board (not the bare plug shell), the **conforming-funnel** pattern (snug obround throat →
  flared overmold-clearing mouth) with validated USB-C numbers + a build123d recipe, and the
  `constraints.yaml` port-contract shape. Linked from the SKILL's enclosure conventions.

### Changed
- **Language policy: English-only → global-developer.** CI no longer fails on non-English
  text anywhere in the repo — language fixtures in code (vibe-voice's zh/ja/ko preflight
  samples), quoted strings, and log excerpts are all legitimate. What remains is a shared
  entry point: English is the lingua franca of the top-level docs, and a translation lives
  *beside* its English original as `*.<lang>.md`. The gate now hard-fails only on a
  translation whose original is missing, and merely warns when a normal doc reads as
  mostly non-English. Also rewritten in `python3` so it no longer depends on GNU
  `grep -P`. `CONTRIBUTING.md`, `AGENTS.md`, and the PR template updated to match.
- `vibe-pcb` docs rewritten library-first: the `Cluster`/gates prose sketches are now
  shipped code and the raw-coordinate `place(x,y)`/`trk([…])` vocabulary is retired.
- `autoroute.sh` documents the accept-by-committing-`routing.ses` flow;
  `export_dsn.py` derives net classes from `parts.yaml`; `import_ses.py` shares one
  pour/rule-area implementation with `pcblib.route`.

## [0.1.0] — Initial public release

### Added
- **Skills** (the method, references/gotchas, and portable `bash`/`python` scripts):
  - `vibe-plm` — the integration layer: a `product.yaml` manifest + the interface
    contracts (`pinmap.yaml`, `constraints.yaml`) that keep firmware/PCB/CAD in sync,
    a `plm_check.py` gate, and the cross-domain release checklist.
  - `vibe-firmware` — reproducible, pinned-toolchain (Docker) firmware builds,
    config-as-code, a host UI simulator, and the "test on real hardware before release"
    rule *(framework — fill in your platform)*.
  - `vibe-pcb` — generate-by-script KiCad flow with a severity-aware ERC/DRC gate
    (`pcb_check.sh`), staged layout rendering (`pcb_skeleton.sh`), module-belly keep-out
    check (`belly_check.py`), JLCPCB packaging (`fab_export.sh`), and a one-page
    **interactive web viewer** — 2D KiCanvas layers + 3D `model-viewer` (`pcb_view.sh`).
  - `vibe-cad` — parametric build123d workflow + CAD-Viewer launcher (`cad_viewer.sh`)
    and the board↔shell interference check (0 mm³) pattern.
- **Examples**: `pager-buddy` — a Claude Code session-status pager. Working **firmware**
  (LVGL UI + NimBLE on an M5StickC S3) and a **Mac bridge** (Claude Code hooks → local hub
  → BLE relay, with the `pager` CLI and usage analytics); the custom carrier **PCB** and
  3D-printed **shell** are stubs (the in-progress target for vibe-pcb / vibe-cad).
- **Tools**: `codesign-viewer` — a one-page PCB (2D+3D) + CAD viewer for a vibe-plm product.
- **Docs**: getting-started, architecture, roadmap, and a curated firmware-reference index.
- **Project**: `AGENTS.md` + `CLAUDE.md`, CI + issue/PR templates, `SECURITY.md`,
  `requirements.txt`, `.editorconfig`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, MIT `LICENSE`.

[0.1.0]: https://github.com/luckiday/vibe-hardware
