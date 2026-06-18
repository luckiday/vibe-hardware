<h1 align="center">⚡ vibe-hardware</h1>

<p align="center">
  <b>Vibe-code real hardware.</b> From a plain-language idea to working
  <b>firmware&nbsp;+&nbsp;PCB&nbsp;+&nbsp;enclosure</b> and a <b>fab order</b> — as a
  beginner — by driving an AI coding agent, not years of EDA/CAD muscle memory.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
  <img alt="skills: 3" src="https://img.shields.io/badge/skills-3-8a2be2">
  <img alt="PCB: KiCad 10" src="https://img.shields.io/badge/PCB-KiCad%2010-2ea44f">
  <img alt="CAD: build123d" src="https://img.shields.io/badge/CAD-build123d-orange">
  <img alt="firmware: ESP32" src="https://img.shields.io/badge/firmware-ESP32-lightgrey">
  <img alt="review: in browser" src="https://img.shields.io/badge/review-in_browser-ff69b4">
</p>

<p align="center">
  <a href="docs/getting-started.md">Getting&nbsp;started</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/roadmap.md">Roadmap</a> ·
  <a href="examples/">Examples</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

Each skill encodes the *method* and the *hard-won gotchas* for one slice of a small
embedded product — plus ready-to-run scripts and an **interactive in-browser review**,
so you never open a heavyweight GUI just to look.

> Sister project to [`earthtojake/text-to-cad`](https://github.com/earthtojake/text-to-cad)
> (whose `cad` / `cad-viewer` / `step-parts` skills these build on). vibe-hardware adds
> the **firmware → PCB → fab** half and a unified, beginner-first workflow.

## Skills

| Skill | From a spec, get… | Highlights |
|---|---|---|
| [**vibe-firmware**](skills/vibe-firmware/) | a reproducible firmware build that flashes + runs | pinned-toolchain (Docker) builds, config-as-code, OTA, the "test on real hardware before release" rule *(framework — fill in your platform)* |
| [**vibe-pcb**](skills/vibe-pcb/) | an ERC/DRC-clean KiCad board + a JLCPCB/LCEDA order | generate KiCad **by script** (never the GUI files), severity-aware DRC gate, module-belly keep-out, **interactive web viewer** (2D layers + 3D, one page) |
| [**vibe-cad**](skills/vibe-cad/) | a parametric build123d enclosure + STEP/STL | one parametric file, **CAD Viewer** review, board↔shell interference check (0 mm³), printability lessons |

The three share **one set of fit numbers** (board outline, stack height, mount holes,
connector exits): change a number once and firmware pins, board, and shell stay in sync.

## Install

```bash
npx skills install luckiday/vibe-hardware
```

Installs the skills into your agent (Claude Code, Codex, …). Then just ask your agent
to design the thing; it loads the relevant skill and runs the scripts. The skills also
work standalone — the `scripts/` are plain `bash`/`python`.

> The interactive viewers pull in the upstream CAD bundle:
> `npx skills install earthtojake/text-to-cad`.

## The loop (idea → fab)

```
idea ─► spec (prose) ─►  firmware   +   PCB        +   enclosure   ─► fabricate
        one brief        vibe-        vibe-pcb         vibe-cad        order board,
        per part         firmware     (KiCad, DRC)     (build123d)     print/mould shell
                                        │                      │
                                        └─ shared fit numbers ─┘
                              interactive browser review at every step (no GUI)
```

Start at [**docs/getting-started.md**](docs/getting-started.md).

## Examples

Worked, end-to-end builds live in [`examples/`](examples/). Flagship:

- [**pager-buddy**](examples/pager-buddy/) — a tiny ESP32 desk "pager" that lights up
  and buzzes on **Claude Code session status / notifications** (task done, waiting on
  input, build failed). Exercises all three skills: firmware (status client + display),
  a carrier PCB, and a 3D-printed shell. *(brief — being filled in)*

Add your own build as `examples/<name>/` and point the skills' "worked reference" at it.

## Philosophy

- **Beginner-first.** You bring the intent and physical constraints; the agent brings
  the EDA/CAD execution. The skills exist so a newcomer can ship a board.
- **Generate by script, review in the browser.** Sources of truth are small
  parametric/generator files (diffable, reproducible), not opaque GUI binaries — and
  you review the result interactively on `localhost`, never by booting the GUI.
- **Encode the gotchas, not just the happy path.** Every skill carries the failures
  that cost a debugging session (belly shorts, power-default-open, GLB sidecars, …).
- **Living docs.** When a real build teaches you something new, fold it back into the
  skill and commit it — compound the experience.

## Status

Early — this is the **framework**. The skills' *methods, scripts, and lessons* are
real and battle-tested; the `examples/` and some platform-specific details are stubs
to fill in. Contributions and new examples welcome (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## License

[MIT](LICENSE).
