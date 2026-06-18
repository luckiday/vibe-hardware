# Changelog

Notable changes to vibe-hardware. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions aim for
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Skills**: `vibe-firmware` (framework stub), `vibe-pcb`, `vibe-cad` — method,
  references (gotchas), and portable `bash`/`python` scripts.
- **vibe-pcb**: generate-by-script KiCad flow with a severity-aware ERC/DRC gate
  (`pcb_check.sh`), module-belly keep-out check (`belly_check.py`), JLCPCB packaging
  (`fab_export.sh`), and a one-page **interactive web viewer** — 2D KiCanvas layers +
  3D `model-viewer`, switchable (`pcb_view.sh`).
- **vibe-cad**: parametric build123d workflow + CAD-Viewer launcher (`cad_viewer.sh`)
  and the board↔shell interference check pattern.
- **Examples**: `pager-buddy` brief (a Claude Code session-status pager).
- **Docs**: getting-started, architecture, roadmap.
- **Project**: `AGENTS.md` + `CLAUDE.md`, CI + issue/PR templates, `requirements.txt`,
  `.editorconfig`, `CODE_OF_CONDUCT.md`, MIT `LICENSE`.

[Unreleased]: https://github.com/luckiday/vibe-hardware
