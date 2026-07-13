# Changelog

Notable changes to vibe-hardware. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions aim for
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- **`examples/voice-buddy`** — the first end-to-end worked example across all four
  skills: a xiaozhi-style AI speaker (ESP32-S3-WROOM-1 + ES8311/ES7210 duplex audio +
  NS4150B + SSD1306 + rear-firing 4 Ω speaker). Generated 2-layer KiCad board
  (placement gates green; scripted routing in progress), contract-driven printed
  enclosure with a 0 mm³ fit-check, a drop-in board port for the MIT-licensed `78/xiaozhi-esp32`
  firmware plus a minimal selftest app, and a `product.yaml` whose contracts are
  content-verified.
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
- `vibe-pcb` docs rewritten library-first: the `Cluster`/gates prose sketches are now
  shipped code, the raw-coordinate `place(x,y)`/`trk([…])` vocabulary is retired, and
  the worked reference is `examples/voice-buddy/pcb/`.
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
