# codesign-viewer

One browser page for a whole **vibe-plm product** — the PCB and the CAD enclosure side
by side, so you can see the board *in its actual shell* without opening KiCad or a CAD
GUI. The integration-layer counterpart to `vibe-pcb`'s `pcb_view.sh` (board only) and
`vibe-cad`'s `cad_viewer.sh` (shell only).

```
tools/codesign-viewer/codesign-viewer.sh <product-dir> [port]    # dir holds product.yaml
```

## What you get

A single page with a header (`product · revision · contract chips`) and up to six tabs:

| Tab | Pane | Source |
|---|---|---|
| **PCB 2D** | KiCanvas, live `.kicad_pcb` | `pcb/kicad/*.kicad_pcb` (layers · objects) |
| **Schematic** | KiCanvas, live `.kicad_sch` | `pcb/kicad/*.kicad_sch` — the design's schematic sheet (tab shown only when one exists) |
| **PCB 3D** | three.js | `view/pcb.glb` — kicad-cli export (board + parts + the real enclosure tray model) |
| **Enclosure** | three.js | `cad/models/.*assembly*.step.glb` (or tray) |
| **Fit** | three.js | `cad/models/.*fit*.step.glb` — board placed in the shell |
| **Exploded** | three.js | `cad/models/.*exploded*.step.glb` |

**Number keys** switch tabs (left→right). A tab whose source is missing — the schematic, a 3D GLB — is greyed out or omitted.

## How it works (and why it's self-contained)

- **No bespoke server, no CAD kernel in the browser.** Both domains render as **GLB** in
  a small inline **three.js** scene (GLTFLoader); the 2D board is the live `.kicad_pcb` in
  **KiCanvas**. The CAD GLBs are the hidden `.<name>.step.glb` sidecars that `vibe-cad`'s
  `build_all.py` already writes (`export_gltf`) next to each STEP; the PCB GLB comes from
  `kicad-cli pcb export glb`. Everything is served by `python3 -m http.server` from the
  product root, so `/pcb/...`, `/cad/...`, `/view/...` all resolve.
- **Shading follows the text-to-cad CAD Viewer** (ACES tone-map, Z-up 3-point light rig,
  `MeshPhysicalMaterial` surface, `EdgesGeometry` feature-edge overlay) — which is why it's
  three.js and not `<model-viewer>` (that can't do the dark feature-edge overlay). The PCB
  GLB keeps its real copper/soldermask colors; only the untinted CAD STEP gets the surface
  tint. Each model auto-recenters + auto-fits the camera until you first orbit.
- The page is written to `<product>/view/` (regenerated — add `view/` to the product
  `.gitignore`).

## Prereqs

- `kicad-cli` (PCB 3D pane) — set `KICAD_CLI` if not at the macOS default path.
- The CAD GLBs built: `(cd <product>/cad && ../../structure/.venv/bin/python build_all.py)`.
- `python3` + a browser. KiCanvas + three.js load from CDN (three via an importmap; vendor for offline later).

## Example

```bash
tools/codesign-viewer/codesign-viewer.sh examples/pager-buddy &
open http://127.0.0.1:8099/view/
```

## Roadmap (iterate)

- Vendor `kicanvas.js` + the `three` modules for fully-offline use.
- A **Split** layout (2D ∥ 3D) and cross-probing PCB selection → 3D highlight.
- Read per-domain gate status (ERC/DRC, fit-check mm³) into the header chips.
- One combined scene placing `view/pcb.glb` into the CAD frame via `constraints.yaml`
  `frame_mapping` (a true single codesign scene rather than separate tabs).
