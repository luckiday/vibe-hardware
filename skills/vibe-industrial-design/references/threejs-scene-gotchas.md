# three.js appearance scene — the gotchas that cost a session each

Structure that works: `params.js` (numbers) · `parts.js` (primitives: rounded-rect
outline with explicit points, `sweep(outline, profile)`, `plate(shape, t, bevel)`,
`lathe` about +Z with explicit normals, `recess`) · `device.js` (numbers → geometry)
· `materials.js` (one material per part, the CMF ledger) · `textures.js` (procedural)
· `views.js` (fixed cameras) · `sheet.js` (contact sheet) · `studio.js` (env +
light rig + backdrop) · `pathtrace.js` (final quality) · `main.js` (UI, export loop).

## Geometry

1. **Two independent radii.** Front corner radius comes from the outline, edge fillet
   from the side profile. A single-radius rounded box cannot make "round front, thin
   soft edge".
2. **Panel corner = shell radius − fillet − inset.** Never a free parameter: a second
   radius makes the gap pinch at 45° and leak a black notch at the corner tip.
3. **Straight runs are true planes → real holes.** Split each run's profile into
   `front fillet / flat / split groove / flat / back fillet`. A hole must lie **entirely
   inside one flat**: cross the groove, or extend into the corner arc, and
   `ShapeGeometry`/`ExtrudeGeometry` triangulation **silently drops the hole** (and
   sprinkles shards). Auto-assign holes to a flat by z and warn loudly when none fits;
   clamp slot lengths to `±(W/2 − Rc)`.
4. **Open the shell face behind every panel hole, bigger than the part.** Otherwise the
   shell face hides the button/window from behind — the part is *there*, positioned
   correctly, and looks like a white disc / a faint print. Smaller-than-part holes let
   the shell poke through the part's side wall.
5. **Lathe about +Z with explicit normals.** `THREE.LatheGeometry` turns about Y and
   flips visibility with point order — a reversed cap *disappears* silently. Give
   normals from the profile tangent; a narrow ring's profile must be monotone.
6. **Inner light-blocker must fit the outline.** A rectangular core pokes out of large
   corner arcs by 0.3 mm — four black "T"s in side views. Use a cross-shaped pair of
   boxes.
7. **Explicit points for rounded outlines, no `absarc`.** Curves subdivide by
   `curveSegments`; a plate with 600 rounded holes becomes tens of thousands of 0.03 mm
   points and earcut fails silently.
8. **A groove floor with no AO is invisible.** Give it a slightly darker material
   instead of adding AO — otherwise gap and seam vanish under soft light.

## Texturing / materials

9. **Perforation ≠ alpha holes.** `alphaMap + alphaTest` at 2–3 px per hole hard-cuts
   at 0.5 on the mipmap → a swimming mottled mess that looks like "holes too dense".
   Use color / bump / roughness maps (mipmaps average correctly).
10. **UVs in millimetres, not normalised.** Every part shares one grain scale;
    normalised UVs stretch the grain into a weave on long thin faces.
11. **`shadowSide = DoubleSide` on a skin.** Shadow maps default to back faces only;
    a one-layer shell seen from above writes depth only from its bottom → its bottom
    holes become light leaks on the wall. Also blank a dark plate behind any through
    hole.
12. **Light-emitting parts: black base + emissive, `toneMapped = false`.** Basic
    materials look unlit to a path tracer; tone-mapped emissive never reads as light.
13. **Name emissive materials** (`lightbar`, `dots`) — the name travels through GLB and
    lets Blender scripts toggle *one* of them.
14. **Several decals, one canvas.** Label + icon share a texture via UV sub-rects; a
    decal on a domed cap must follow the dome (build a polar-grid disc with `z(r)`) or
    it floats/clips.

## Cameras / sheet

15. **Frame by fit, not fov.** `fitW/fitH` → fov from aspect; the sheet survives size
    changes.
16. **`updateMatrixWorld` before panning; guard aspect.** `lookAt` sets quaternion
    only; and a 0-height canvas gives aspect ∞ → `0·∞ = NaN` → the camera never
    recovers (all tiles blank, console clean).
17. **Strip views: drop grain maps + steepen the key light** (raster only). Grazing
    light + 10× minification aliases noise into diagonal stripes; shadow acne adds
    another set. Under the path tracer keep the maps.
18. **Third-angle projection for top/bottom strips.** Bottom: front edge up, left/right
    as the front. A tilt of 1° pulls the mirrored back silk into the frame.
19. **Elevation 0.3° for front/back once the top carries a lamp** — 1.2° pokes a red
    dot over the top edge.

## Export loop

20. **Trigger auto-export from `setTimeout`, not rAF or `load`.** Background tabs
    suspend rAF (image never appears, no error); module scripts can evaluate after
    `load`.
21. **`serve.py` sends `Cache-Control: no-store`.** Otherwise Chrome caches modules
    and you edit the wrong file for an hour.
22. **Pause the interactive rAF loop during export.** The path tracer yields to the
    event loop every N samples; the frame loop sees `needsRender`, re-applies the
    *interactive* camera and re-syncs the tracer; the rest of the samples accumulate
    onto another view/material set. Random per run: a face goes dark grey, the light
    bar shows the perforation texture, the back plate shows the front label, a bottom
    tile contains a whole front. Everything *looks like* a material-index bug (new
    tracer per tile, merged textures, no-map-swaps — none fix it). Only bites with the
    tab visible, so it "worked" for two versions.
23. **Path tracer + emissive geometry: small emitters don't light the wall.** No
    importance sampling for arbitrary emissive triangles; a 4 cm² bar at 22× stays at
    zero on the wall. Add a same-size `RectAreaLight` *inside* the slot (two-sided,
    outside the slot it throws ghost shadows back). Environment maps must be
    `DataTexture` (canvas textures have no `.image.data` → black scene).
24. **Pin the canvas CSS size to the buffer while path-tracing an export** — the
    engine sizes its target from `clientWidth`; otherwise the front squashes to a band.
25. **`?fresh=1` for automation.** localStorage deltas from a slider session
    otherwise leak into "reference" renders.
