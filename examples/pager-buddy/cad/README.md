# pager-buddy — cad

> **Stub.** Sources to be filled in via [`vibe-cad`](../../../skills/vibe-cad/)
> (one parametric build123d `.py` + `build_all.py`).

A desk shell exposing the display window, USB-C, and the button; holds the PCB on
standoffs.

## Interface contracts

- **Owns** [`constraints.yaml`](constraints.yaml) — the shared fit numbers (board
  outline, mount holes, stack height, port/window cutouts). `pcb/` reads these too,
  so a number lives here once and both the board and the shell move with it.
- **Consumes** `../pcb/board.step` — the real board for the 0 mm³ interference check.

## Check *(fill in)*

`python check_fit.py` → board ↔ shell interference must be **0 mm³**.
