# Roadmap

A living plan — tick items as they land, add new ones as the project teaches you what's
missing. Not a schedule; a direction. (Phases overlap; pull anything forward.)

## Phase 0 — Framework  ·  *now*

The method, scripts, and hard-won lessons are real; examples and some platform detail
are stubs.

- [x] `vibe-pcb` — generate-by-script KiCad, severity-aware ERC/DRC gate, belly keep-out,
      JLCPCB packaging, one-page 2D+3D web viewer.
- [x] `vibe-cad` — parametric build123d, CAD-Viewer review, interference check.
- [x] `vibe-firmware` — framework stub (pinned builds, config-as-code, OTA + test-first).
- [x] `vibe-plm` — the integration layer: a `product.yaml` manifest + the three interface
      contracts (pinmap / board.step / constraints) + a self-contained `plm_check.py` gate
      + the cross-domain release checklist.
- [x] Repo scaffold — README, AGENTS/CLAUDE, docs, CI, templates, license.

## Phase 1 — One end-to-end example

Prove the whole loop on a real, public build.

- [ ] `examples/pager-buddy` filled in: structure + `product.yaml` manifest scaffolded ✔
      — now the `pcb/`, `cad/`, `firmware/` sources + the Claude Code hook→bridge→device glue.
- [ ] `vibe-firmware` made concrete for **ESP-IDF** (or Arduino) — the status client,
      config-as-code layout, a one-command pinned build wrapper (`scripts/`).
- [ ] Demo GIFs in `assets/` (the 2D/3D viewer; the device paging) wired into the README.
- [ ] A "first board in an afternoon" tutorial in `docs/`.

## Phase 2 — Breadth & polish

- [ ] More examples (a sensor logger, a desk widget) — each a filled-in template.
- [ ] `vibe-pcb`: kicad-happy cross/EMC pass wired into `pcb_check.sh`; KiCanvas viewer
      polish (net highlight presets); panelization notes.
- [ ] `vibe-cad`: a small parts library / `step-parts` recipes; print-profile presets.
- [ ] A `vibe-glue` (or `vibe-hooks`) skill: the agent-status bridge (hooks → MQTT/HTTP →
      device) generalized, since several examples want it.
- [ ] `references/` for `vibe-firmware` (driver patterns, OTA safety model).

## Phase 3 — Distribution

- [ ] Plugin packaging — `.claude-plugin/` + Codex plugin manifests so
      `claude plugin install` / `codex plugin add` work, like the reference repo.
- [ ] Versioning + releases (CHANGELOG → tags); a `Release` workflow.
- [ ] Benchmarks — a handful of "design X from this brief" cases to test the skills.

## Phase 4 — Reach

- [ ] More MCU platforms (RP2040, STM32, nRF; Zephyr/PlatformIO).
- [ ] Other fab routes (PCBWay, OSH Park) + assembly/BOM sourcing helpers.
- [ ] A project template / cookiecutter (`new-project <name>` scaffolds the three dirs).
- [ ] Community: a registry of user examples; contribution guides per skill.

## Guiding constraints (don't drift from these)

- **Beginner-first** — if a step needs EDA/CAD expertise to do, automate or document it.
- **Generate by script, review in the browser** — never require the heavyweight GUI.
- **Encode the gotchas** — every skill carries the failures, not just the happy path.
- **Living docs** — fold each new lesson back into the skill (see each `SKILL.md`).
- **Generic & English-only** — skills teach the method; designs stay in `examples/`.
