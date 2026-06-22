# codesign-viewer

One browser page for a whole **vibe-plm product** — the PCB and the CAD enclosure side
by side, so you can see the board *in its actual shell* without opening KiCad or a CAD
GUI. The integration-layer counterpart to `vibe-pcb`'s `pcb_view.sh` (board only) and
`vibe-cad`'s `cad_viewer.sh` (shell only).

```
tools/codesign-viewer/codesign-viewer.sh <product-dir> [port]    # dir holds product.yaml
```

## What you get

A single page with a header (`product · revision · contract chips`) and five tabs:

| Tab | Pane | Source |
|---|---|---|
| **PCB 2D** | KiCanvas, live `.kicad_pcb` | `pcb/kicad/*.kicad_pcb` (layers · objects · schematic) |
| **PCB 3D** | `<model-viewer>` | `view/pcb.glb` — kicad-cli export (board + parts + the real enclosure tray model) |
| **Enclosure** | `<model-viewer>` | `cad/models/.*assembly*.step.glb` (or tray) |
| **Fit** | `<model-viewer>` | `cad/models/.*fit*.step.glb` — board placed in the shell |
| **Exploded** | `<model-viewer>` | `cad/models/.*exploded*.step.glb` |

Keys **1–5** switch tabs. A 3D tab whose GLB is missing is greyed out.

## How it works (and why it's self-contained)

- **No bespoke server, no CAD kernel in the browser.** Both domains render as **GLB** in
  Google `<model-viewer>`; the 2D board is the live `.kicad_pcb` in **KiCanvas**. The CAD
  GLBs are the hidden `.<name>.step.glb` sidecars that `vibe-cad`'s `build_all.py` already
  writes (`export_gltf`) next to each STEP; the PCB GLB comes from `kicad-cli pcb export
  glb`. Everything is served by `python3 -m http.server` from the product root, so
  `/pcb/...`, `/cad/...`, `/view/...` all resolve.
- The page is written to `<product>/view/` (regenerated — add `view/` to the product
  `.gitignore`).

## Prereqs

- `kicad-cli` (PCB 3D pane) — set `KICAD_CLI` if not at the macOS default path.
- The CAD GLBs built: `(cd <product>/cad && ../../structure/.venv/bin/python build_all.py)`.
- `python3` + a browser. KiCanvas / model-viewer load from CDN (vendor for offline later).

## Example

```bash
tools/codesign-viewer/codesign-viewer.sh \
  ../nursing-home-thermal-solution/hardware/v2.0-multi-thermal/tc5-1-xiao &
open http://127.0.0.1:8099/view/
```

## Roadmap (iterate)

- Vendor `kicanvas.js` + `model-viewer.min.js` for fully-offline use.
- A **Split** layout (2D ∥ 3D) and cross-probing PCB selection → 3D highlight.
- Read per-domain gate status (ERC/DRC, fit-check mm³) into the header chips.
- One combined scene placing `view/pcb.glb` into the CAD frame via `constraints.yaml`
  `frame_mapping` (a true single codesign scene rather than separate tabs).
