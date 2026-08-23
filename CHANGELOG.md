# Changelog

Notable changes to vibe-hardware. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions aim for
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- **`examples/mic-macropad`** — a second worked example, and the first whose **board** is
  finished: three MX keys + an I2S mic on an ESP32-S3-WROOM-1, 76 x 56 mm, two layers,
  **DRC 0 error-severity / 0 unconnected**. Contracts (`constraints.yaml` / `parts.yaml` /
  `pinmap.yaml`) that the generator never re-types, a placement laid out as a *product*
  (key row as the face, USB away from the hands, ESD at the connector, pogo pads instead
  of a header), and a reproducible autoroute: a **locked skeleton** (`SetLocked` ->
  Specctra `(type fix)`) plus an **accepted `.ses`** replayed by default, because
  freerouting is nondeterministic.
- **`vibe-pcb/scripts/zone_islands.py`** — answers "why is this pour unconnected?". DRC
  reports a fenced-off pour as one cryptic `Zone <-> Zone` line pointing at the board
  corner; this prints every island with the pads and vias of that net inside it, so the
  fix is a coordinate you can read off. `--strict` exits 1 on an orphan.
- **`vibe-pcb/scripts/power_check.py`** — answers the two questions DRC never asks about a
  power net: is the **narrowest** segment wide enough for the current (IPC-2221 closed form,
  with an explicit note on why not IPC-2152), and what is the **IR drop** to each load
  (shortest-resistance path, splitting segments at T-junctions so a branch is not reported
  unreachable). Reads widths off the routed board, which is how the example found that 61 %
  of its VBUS is 0.25 mm and not the 0.5 mm its docs claimed.
- **`vibe-pcb/scripts/fab_export.sh`** — the JLCPCB BOM now carries **LCSC part numbers
  read from `parts.yaml`'s `lcsc:` field** (the schema always had it; the exporter did not
  use it), refuses to emit a BOM line whose refs disagree about their part number, and
  names the exact lines still missing one instead of a blanket "fill LCSC #s".
- **`vibe-pcb/references/design-rules.md`** — an **LED Vf vs the rail** finding: the green
  0603s JLCPCB stocks are InGaN with Vf specified as a *range* (2.6–3.6 V), so on a 3.3 V
  rail a worst-case part cannot light at any resistor value. Check the range, not the
  typical value, before colour is a design decision.
- **`examples/mic-macropad`** — a complete JLCPCB order package and
  [`pcb/ORDER.md`](examples/mic-macropad/pcb/ORDER.md): what to upload, board options, the
  hand-soldered refs, and a generated **pin-1 orientation table** to check the CPL rotations
  against in JLCPCB's preview.
- **`vibe-pcb/references/design-rules.md`** — a **mechanically special = sourcing risk**
  finding: check the assembly library BEFORE designing mechanics around a part. Five
  side-actuated switches were evaluated for the example and all five failed differently
  (not carried, obsolete, 4 in stock, no published land); the fix was to move the
  mechanism into the enclosure and keep a commodity switch on the board.
- **`vibe-pcb/references/design-rules.md`** — a **rotation is not actuation** finding: a
  side-pressed button needs a side-actuated part, not a rotated top-actuated one, and its
  shell hole belongs in a wall — so it is a `constraints.yaml` window with that stated.
  Find the actuator direction by measuring the (asymmetric) courtyard.
- **`vibe-pcb/references/design-rules.md`** — a **stitching-via drift** finding: vias added
  one at a time to chase pour islands survive a re-placement and become a constellation
  nobody can justify. Measure with leave-one-out (drop a via, refill, re-run DRC) — on the
  worked example 25 of 27 were doing nothing — then place a deliberate set: connectivity
  vias where the sweep says, plus **return-path** vias beside every signal via that changes
  layer, which DRC never asks for.
- **`vibe-pcb/references/design-rules.md`** — a **same-net pins split by a third** finding:
  two pins of one net on the same package side with a different net between them (an LDO's
  VIN + EN either side of GND) makes the router wrap the far side of the part at
  near-minimum clearance. Feed both from the near side and lock it.

### Changed
- **`vibe-pcb`** — `autoroute.sh` now passes `-mt 1` (freerouting's own log: the
  multi-threaded optimizer "is known to generate clearance violations"; a 27-part board
  saw its optimization stage go 16 -> 17 violations). `references/autorouting.md` gains a
  **"Freerouting at scale"** section: the locked-skeleton pattern, the accepted-session
  convention, why a *dense* board must export a **GND-less** DSN (and how that squares
  with gotcha 5, which is now cross-referenced rather than contradicted), netless vias
  vanishing from the export, and netclasses as a simpler alternative to `export_dsn.py`'s
  regex class rewrite. `references/design-rules.md` gains a **"place for the product,
  then for the router"** section plus two findings: a footprint with **no courtyard**
  makes `courtyard_overlaps()` a silent no-op (and a stock land is not automatically
  safe — the Cherry MX courtyard is 13.29 mm across a 14 mm housing), and **wire length
  does not predict routability** (1292 -> 591 mm of wire took unroutable traces from 14
  to 22 on a measured board), which argues against treating the `hpwl` budget as a target.

### Fixed
- **CI** — the `checks` job was a lint-only scaffold that did not run the gates the
  docs tell you to run. It now compiles Python under `examples/` and `tools/` as well
  as `skills/`, runs `plm_check.py` on every `examples/*/product.yaml`, and runs the
  pager-buddy `bridge/smoke.sh`. Shellcheck is a real gate (it used to `continue-on-error`
  while failing every run on `_kicad_env.sh` SC2148). Firmware builds can be triggered
  with **Run workflow** so the Docker job is exercisable without cutting a tag; the
  container flags now match `idf.sh` (`-u` / `HOME=/tmp`). Actions get `permissions:` /
  `concurrency:` and Dependabot for `github-actions`.

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
- `vibe-industrial-design`: **the outbound leg of the look loop, and the constraints that
  outrank the picture.** Two new references plus a new `SKILL.md` §0.
  `references/ai-image-iteration.md` — driving an image model instead of only receiving
  from one: get the current render to disk without a human (`POST /save`; two nested rAFs
  after moving the camera or you capture the previous view; always send **two** angles or
  the model guesses the depth generously); **`edit` refines within the form, `generate`
  leaves it** — reaching for `edit` after the brief moved returns the same box with a
  different button and the review calls it exploration; **three prompts beat `-n 3`**
  (three samples of one prompt are lighting accidents, not directions) sharing a literal
  `BASE`/`STYLE` so the comparison is controlled; enumerate every feature that must
  survive *and where it sits*, because the model simplifies silently; and always exclude
  text, or you get invented brand marks and a screen on a device with no display.
  `references/appearance-vs-physics.md` — requirement archaeology before the first image
  (an algorithm spec's mounting assumption, an antenna keep-out, a power LED the MCU
  cannot switch off), then the physics that overrides appearance: ordinary plastic and
  glass are **opaque to LWIR**, so a handsome dark "filter" panel is a blind sensor; a
  window sunk `t` mm needs `2·t·tan(FOV/2)` of extra clear width per edge or the shell
  clips the field and only the far corners of the room quietly stop being detected; a
  self-heating die reads 36.7 °C in a 28 °C room; an attenuating window is a
  **calibration item**, not a user-removable cover. Worked failure: a desktop form that
  silently invalidated a regression-tested detector whose thresholds all came from
  "wall-mounted at 1.5 m".
  `references/threejs-scene-gotchas.md` gains a *reading depth* section (26–28): the
  blanking part behind a hole must be **unlit** or fill light turns a vent field into
  white tiles printed on the shell; darken the hole's **side wall**, which is what you
  actually see off-axis; and position the *group* of a sub-assembly so it follows its
  aperture instead of leaving a crescent of bare cavity that reads as a lighting bug.
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
