<h1 align="center">⚡ vibe-hardware</h1>

<p align="center">
  <b>Vibe-code real hardware.</b> From a plain-language idea to working
  <b>firmware&nbsp;+&nbsp;PCB&nbsp;+&nbsp;enclosure</b> and a <b>fab order</b> — as a
  beginner — by driving an AI coding agent, not years of EDA/CAD muscle memory.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
  <img alt="skills: 7" src="https://img.shields.io/badge/skills-7-8a2be2">
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
| [**vibe-plm**](skills/vibe-plm/) | one manifest + interface contracts that keep the three domains in sync | `product.yaml` (identity + revision), the shared fit-number contracts, a `plm_check.py` gate, the cross-domain release checklist |
| [**vibe-firmware**](skills/vibe-firmware/) | a reproducible firmware build that flashes + runs | pinned-toolchain (Docker) builds, config-as-code, OTA, the "test on real hardware before release" rule *(framework — fill in your platform)* |
| [**vibe-uiflow**](skills/vibe-uiflow/) | a screen-and-buttons device on UIFlow2/MicroPython, in seconds per iteration | host simulator over an `M5.Lcd` stub with **device-dumped font metrics**, a bounded on-board self-test, the **ghost check**, and UIFlow2 on **non-M5 ESP32-S3 boards** |
| [**vibe-pcb**](skills/vibe-pcb/) | an ERC/DRC-clean KiCad board + a JLCPCB/LCEDA order | generate KiCad **by script** (never the GUI files), severity-aware DRC gate, module-belly keep-out, **interactive web viewer** (2D layers + 3D, one page) |
| [**vibe-cad**](skills/vibe-cad/) | a parametric build123d enclosure + STEP/STL | one parametric file, **CAD Viewer** review, board↔shell interference check (0 mm³), printability lessons |
| [**vibe-industrial-design**](skills/vibe-industrial-design/) | the product's *look*: a parametric three.js appearance model, a fixed-camera contact sheet, Blender Cycles finals, and a versioned ID/CMF report | **constraints first** — part of the form is already fixed by a spec nobody re-read, and the physics must pass through the surface you drew (ordinary plastic is opaque to LWIR); **measure the AI look image** into tagged numbers (px/mm, corner R, hole pitch, colours); **drive the image model**, don't only receive from it (`edit` refines the form, `generate` leaves it; three prompts beat three samples); one `params.js` with provenance tags, browser review + URL-driven export (raster; finals from Cycles), GLB → Blender with a **reusable hand-tuned `studio.blend`**, md-authority report + generated .docx with a change log per version |
| [**vibe-voice**](skills/vibe-voice/) | the agent *talking you through* the hands-on steps | speak the action, print the command; preflight the voice channel (a mute TTS still exits 0); poll a serial line instead of asking "did you press it?" |

`vibe-firmware` and `vibe-uiflow` are the same domain at two operating points: C/ESP-IDF
when you need determinism, power discipline and OTA; UIFlow2/MicroPython when you want the
screen to change in seconds and can trade those away. Both close the UI loop on the host.

The three domains (firmware · PCB · CAD) share **one set of fit numbers** (board outline,
stack height, mount holes, connector exits) — vibe-plm owns the contracts that hold them:
change a number once and firmware pins, board, and shell stay in sync.

**vibe-industrial-design** sits before/alongside `vibe-cad`: it decides *what the thing
looks like* (proportion, split lines, CMF, control placement) from a brief and AI look
images — which it both receives from the owner and **generates itself** from the current
render — and hands the outer numbers to the enclosure model. It starts by digging out the
constraints that already fixed part of the form, because a render that contradicts a
shipped algorithm is not a design, it's rework. `vibe-cad` decides how it holds together.

**vibe-voice** is the odd one out: not a domain, a *channel*. It turns on at the moments
the other loops hand control back to a human — flashing and probing, first power-up,
test-fitting a print — where your hands are on the hardware and nothing is left for the
keyboard.

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
                              vibe-voice speaks the steps your hands are busy for
```

Start at [**docs/getting-started.md**](docs/getting-started.md).

## Examples

Worked, end-to-end builds live in [`examples/`](examples/). Flagship:

- [**pager-buddy**](examples/pager-buddy/) — a desk "pager" that lights up and buzzes on
  **Claude Code session status / notifications** (task done, waiting on input, build
  failed) and can answer prompts from the device. The **firmware** (LVGL UI + NimBLE on an
  M5StickC S3) and the **Mac bridge** (Claude Code hooks → BLE) work today; the custom
  carrier **PCB** and 3D-printed **shell** are still stubs — the in-progress target for
  vibe-pcb / vibe-cad.

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

Early — this is the **framework**. The skills' *methods, scripts, and lessons* are real
and battle-tested. The flagship [`pager-buddy`](examples/pager-buddy/) example has working
firmware + a Mac bridge (on an M5StickC S3); its custom PCB/enclosure are still stubs.
Contributions and new examples welcome (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## License

[MIT](LICENSE).
