# AGENTS.md

Guidance for AI agents working **in this repo**. Keep this short — the detailed
method and gotchas for any task live in the relevant skill's `SKILL.md` +
`references/`. Read those before acting; this file is the map and the rules.

## Repo map

```
skills/          the agent skills (one per dir):
  vibe-plm              the integration layer: product manifest + interface contracts
  vibe-firmware · vibe-pcb · vibe-cad   the three domains (each a self-contained loop)
  <skill>/SKILL.md      frontmatter (name + "use when…") + the method
  <skill>/references/   deep lessons / gotchas, loaded on demand
  <skill>/scripts/      portable bash/python tools (plm_check, pcb_check, pcb_view, cad_viewer, …)
examples/        worked end-to-end builds (pager-buddy, …); product.yaml + the three dirs
docs/            getting-started and friends
```

The three domains are coupled **only through data** — the contract files named in a
product's `product.yaml` (vibe-plm owns it), never by one skill calling another's code.

## Repo rules

- **Keep root guidance short.** Put domain detail in the skill it belongs to, not here.
- **Skills are self-contained.** A skill's *code* (its `scripts/`) must not import or
  call another skill's code. Prose "hand off to the sibling skill" pointers are fine;
  a runtime dependency between skills is not. (`vibe-pcb`'s viewer renders in-page; it
  does not shell out to `vibe-cad`.)
- **Generate by script, review in the browser.** Sources of truth are small
  generator/parametric files (KiCad via `gen_*.py`; build123d `.py`) — never
  hand-edited GUI binaries. Review interactively on `localhost`, never by booting a
  heavyweight GUI. If a change needs the GUI to use, it isn't done.
- **Keep it general; no proprietary designs.** Skills teach a reusable method,
  illustrated with generic parts. Worked product designs go in `examples/` (only what
  you choose to publish) — never bake a private design into a skill.
- **Living docs.** When a real build teaches a new gotcha/fix/better-practice, fold it
  back into the skill and commit it *with* the work. Compounding the experience is the
  point.

## Environments

- **PCB** — KiCad 10: `kicad-cli` + its **bundled** python (the one with `pcbnew`),
  not system python. Override paths via `KICAD_CLI` / `KICAD_PY` on non-mac.
- **CAD** — a build123d venv: `python3 -m venv .venv && .venv/bin/pip install build123d`.
  Run model/check/export scripts with `.venv/bin/python`.
- **Firmware** — a **pinned** toolchain (Docker image at a fixed SDK tag / locked
  PlatformIO). A host-toolchain build is a personal convenience, never authoritative.
- **Viewers** — the interactive CAD Viewer is vendored:
  `npx skills install earthtojake/text-to-cad` (lands in the gitignored
  `.agents/`/`.claude/`).

## Checks (run the skill's own scripts; smallest first)

- PLM: `python3 skills/vibe-plm/scripts/plm_check.py <product>/product.yaml` → manifest
  sane + every interface contract resolves (source missing = error, artifact = warn).
- PCB: `scripts/pcb_check.sh <proj>` → ERC + DRC to 0 errors / 0 unconnected
  (+ `BELLY_BOX=…` for the module belly keep-out).
- CAD: `python check_fit.py` → board↔shell interference must be **0 mm³**.
- Review with the launchers (`scripts/pcb_view.sh`, `scripts/cad_viewer.sh`) — let them
  pick the port and serve locally; don't hand-pick ports or serve files publicly.

## Git

- Work on a branch; PR to `main`. Keep commits scoped to one skill/area.
- **Never commit** regenerated artifacts (`view/`, `*.glb`, `models/*.stl`), `.venv/`,
  `node_modules/`, the vendored `.agents/`/`.claude/`, or secrets (Wi-Fi creds / API
  keys / tokens — load from a gitignored file, commit a `.example`). See `.gitignore`.

## Always / Never

| | Rule |
|---|---|
| Skills | **Never** import another skill's code at runtime; cross-references are prose only |
| Sources | **Never** hand-edit the `.kicad_*` / generated CAD; edit the `gen_*.py` / model `.py` and regenerate |
| Designs | **Never** commit a proprietary design into a skill; generic examples only |
| Builds | **Never** treat a host firmware build as authoritative; use the pinned toolchain |
| Release | **Never** ship an OTA / fielded firmware update without a real-hardware test first |
| Secrets | **Never** commit credentials; gitignore + a `.example` |
| Artifacts | **Never** commit regenerated outputs; they rebuild from source |
