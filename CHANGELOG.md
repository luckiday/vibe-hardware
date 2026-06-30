# Changelog

Notable changes to vibe-hardware. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions aim for
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- `vibe-cad`: `references/usb-connector-cutouts.md` — how to cut USB port openings in an
  enclosure wall. Encodes the lesson that the opening must clear the **receptacle** on the
  board (not the bare plug shell), the **conforming-funnel** pattern (snug obround throat →
  flared overmold-clearing mouth) with validated USB-C numbers + a build123d recipe, and the
  `constraints.yaml` port-contract shape. Linked from the SKILL's enclosure conventions.

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
