# Getting started

You don't need to be a hardware engineer. You need an idea, the physical constraints,
and an AI coding agent (Claude Code). The skills do the EDA/CAD execution; you steer.

## 0. Install

```bash
npx skills install luckiday/vibe-hardware        # these skills
npx skills install earthtojake/text-to-cad      # the CAD/3D viewer bundle they reuse
```

Local tools the scripts call:
- **KiCad 10** (`kicad-cli` + its bundled python with `pcbnew`) — for `vibe-pcb`.
- A **build123d** venv (`python3 -m venv .venv && .venv/bin/pip install build123d`) — for `vibe-cad`.
- Your firmware toolchain (ESP-IDF / PlatformIO / Arduino-CLI) — for `vibe-firmware`.

## 1. One spec, shared numbers

Write a short brief per part, but keep **one set of fit numbers** across all three —
board outline, stack height, mount-hole spacing, connector/USB exits, any display/sensor
window. Change a number once; firmware pins, the board, and the shell follow. The
[`vibe-pcb` spec template](../skills/vibe-pcb/references/spec-template.md) is the
place to start (its **net map** is the single source of truth firmware also reads).

## 2. Run each loop (ask your agent, or run the scripts)

| Part | Do | Review (no GUI) |
|---|---|---|
| **PCB** | generate KiCad by script → `pcb_check.sh` to 0 errors / 0 unconnected | `pcb_view.sh` — one page, **2D layers \| 3D board \| Split** |
| **Enclosure** | one parametric build123d file → `build_all.py` → `check_fit.py` (0 mm³ vs the board) | the **CAD Viewer** (`cad_viewer.sh`) |
| **Firmware** | code → **reproducible** (pinned) build → flash + monitor | the serial log; bring up one peripheral at a time |

Each skill's `SKILL.md` has the exact loop; its `references/` carry the gotchas that
cost a debugging session. **Read the gotchas before you trust the happy path.**

## 3. Fabricate

- **Board:** `fab_export.sh` → upload the gerber `.zip` to JLCPCB (or the LCEDA
  three-piece). **Photo/caliper-verify the real module** against your footprint first.
- **Shell:** export STL, print (or core-out for moulding).
- **Firmware:** flash over USB; OTA later — but **test on real hardware before any
  fielded release**.

## 4. Learn forward

When a build teaches you something the skill didn't warn you about, **edit the skill and
commit it**. That's the point — each project makes the next one easier.

See [`examples/pager-buddy`](../examples/pager-buddy/) for a worked target.
