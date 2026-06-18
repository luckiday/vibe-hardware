# Interactive PCB review in the browser (no KiCad GUI)

One command, **one page**, no KiCad GUI — a unified viewer with a header switch
**[2D layers | 3D board | Split]** (keys 1/2/3). It combines the two things you
actually want, in a single dark "EDA tool" UI so it doesn't read as two bolted-on
projects:

- **2D** — [KiCanvas](https://kicanvas.org) reading the live `.kicad_pcb`:
  layer-visibility panel, object toggles, pan/zoom, select/cross-probe, and the
  schematic in tabs (the per-layer copper inspection a baked mesh can't give).
- **3D** — the `kicad-cli` GLB (copper + silk + components) in Google's
  [`<model-viewer>`](https://modelviewer.dev): orbit / zoom of the real board.

```bash
# run in the project kicad/ dir; launch in the background, then open the URL
skills/text-to-pcb/scripts/pcb_view.sh <proj> &
#   -> http://127.0.0.1:8088/view/pcb.html       (switch: 2D layers · 3D board · Split)
```

## What `pcb_view.sh` does

1. Exports the routed board to a GLB (`kicad-cli pcb export glb --include-tracks
   --include-pads --include-silkscreen --subst-models`) into `kicad/view/`.
2. Writes `kicad/view/pcb.html` — KiCanvas (2D) + model-viewer (3D) sharing one
   dark theme, framed as matching panels, with the view switch.
3. Serves the `kicad/` dir over **localhost** so the `.kicad_pcb` / `.kicad_sch` /
   GLB are fetchable same-origin — **files never leave the machine**.

`.glb` needs no GLB sidecar (model-viewer tessellates it); contrast the `.step`
sidecar rule the enclosure CAD Viewer needs.

## Which pane for what

| Checking… | Pane |
|---|---|
| copper routing **layer-by-layer**, objects, nets, the **schematic** | **2D** (KiCanvas) |
| physical look, component overhang, **board ↔ enclosure fit** | **3D** (model-viewer GLB) |

For board+shell together, drop the enclosure's GLB into the same `kicad/view/` and
load it in the 3D pane.

## Notes

- **Gitignore** `kicad/view/` — regenerated (the GLB + the HTML).
- **No kicad-cli?** The page degrades to **2D only** (set `KICAD_CLI=` for the 3D
  pane). The 2D side needs only `python3` + the `.kicad_pcb`.
- **Offline:** drop a `kicanvas.js` next to the script (or `KICANVAS_SRC=/abs`) — it's
  copied beside the page and used instead of the CDN; likewise `MODELVIEWER_SRC=/abs`
  for the 3D component.
- **Tweak the 3D export** (edit the `kicad-cli pcb export glb` flags in the script):
  `--board-only`, `--no-components`, `--include-soldermask`, `--include-zones`,
  `--component-filter A1,U*`, `--net-filter GND`.
- **Privacy:** the hosted kicanvas.org / modelviewer pages would **upload** a
  drag-dropped file; this script's local serve keeps private boards on your machine.
- Only have gerbers (post `fab_export.sh`)? A gerber viewer like
  [tracespace](https://github.com/tracespace/tracespace) renders them in-browser —
  usually unnecessary, review the `.kicad_pcb` / GLB first.

The static `pcb render` PNG (`pcb_check.sh`) is still fine for a committed
thumbnail; this is for when you need to **interact** with the board.
