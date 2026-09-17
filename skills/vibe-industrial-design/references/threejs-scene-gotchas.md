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
    materials look unlit to any physically based renderer; tone-mapped emissive never reads as light.
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
    another set. (A path tracer would keep the maps — it doesn't alias that way.)
18. **Third-angle projection for top/bottom strips.** Bottom: front edge up, left/right
    as the front. A tilt of 1° pulls the mirrored back silk into the frame.
    **Verify by projecting a known corner, not by reasoning about up vectors** —
    `new Vector3(0, y, ±z).project(cam)` on the front and bottom cameras settles it
    in seconds. Reasoning it out got it backwards once, and "fixing" that with a
    `ctx.scale(-1, 1)` in the sheet flipped the one strip that exists to be held
    against the board.
19. **Elevation 0.3° for front/back once the top carries a lamp** — 1.2° pokes a red
    dot over the top edge.

## Export loop

20. **Trigger auto-export from `setTimeout`, not rAF or `load`.** Background tabs
    suspend rAF (image never appears, no error); module scripts can evaluate after
    `load`.
21. **`serve.py` sends `Cache-Control: no-store`.** Otherwise Chrome caches modules
    and you edit the wrong file for an hour.
*(22–24 come from the in-browser path tracer, since retired in favour of Blender;
they hold for any multi-frame renderer you put in the page.)*

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

## Reading depth (holes, recesses, vents)

A perforated panel only reads as *holes* if what shows through is darker than the panel at
every angle. Two ways it silently stops being darker:

26. **The blanking part behind a hole must be unlit** (`MeshBasicMaterial`, or basic +
    a fixed dark colour). With a lit material, the fill or rim light reaches it from the
    far side and each hole fills with a pale square — a vent field that renders as *white
    tiles printed on the shell*. It looks like the holes were never cut, so the instinct
    is to go check the geometry, which is fine.
27. **Darken the hole's side wall, not just the cavity.** Off-axis you mostly see the
    wall of the hole, not the space behind it: at 45° a 3 mm-thick wall covers a 3 mm-wide
    hole completely. A body-coloured wall catches the key light and reads as a raised
    white square. Give the wall its own darker material (`ExtrudeGeometry` puts caps in
    material slot 0 and walls in slot 1, so this is free) — which is also what the real
    part does, with a dark liner behind the panel.
28. **A sub-assembly must follow the opening it sits in.** When the aperture is a
    parameter (`driverX/Y`), the parts behind it — basket, cone, light guide, gasket —
    have to move with it. Miss it and the assembly stays at the origin while the hole
    moves: you get a crescent of bare cavity on one side of the opening that looks like a
    lighting bug, not a positioning one. Position the *group*, never the members.

## Openings on a swept body, and other silent failures

29. **A swept skin cannot take a hole — so every aperture has to come OUTWARD.**
    The body sweep is one closed surface. Anything placed *behind* it (a recessed
    bore, an inset parting groove, a cavity disc) is simply hidden: the wall is
    opaque and continuous. Symptoms are two, and they look like different bugs —
    a bore that renders as nothing at all, and a bore that renders as an unlit
    *crescent* (the recess opening the wrong way, so you catch one edge of it).
    Either model the opening as an **unlit dark face 0.05–0.1 mm proud** of the
    skin (identical read at review distance), or rebuild that straight run as a
    flat plate and cut a real hole in it. Same for a parting line: proud thin
    band, not an inset groove.
30. **`recess()`/`plate()` open toward +z, so check which way you rotated them.**
    `Ry(+90°)` sends +z to **+x**, `Ry(−90°)` sends it to **−x**. Getting the two
    walls' rotations swapped opens every bore *into* the body — see the crescent
    in 29. Write the rotation table once (`{left, right, front}`) rather than per
    call site.
31. **Loft/ring winding fails silently and does not look like a normals bug.**
    With the ring CCW in xy and z up, the outward face is `(lo[i], lo[j], hi[i])`.
    Reverse it and three.js culls the *outside* of the part, so you see straight
    through to its far inner wall: a keycap reads as a splayed tent, not as an
    inverted normal, and the instinct is to go check the profile maths.
32. **`Object3D.add()` returns the PARENT, not the child.** `g.add(mesh(…)).rotation.x = …`
    rotates the whole group. The tell is that *everything* is 90° out — the
    bounding box reports height in z and depth in y — while each individual
    part's own numbers check out. Assign the mesh to a variable first.
33. **Two coincident walls z-fight into a white hairline** that reads as a
    modelling gap. A recess nested inside a plate's hole must be ~0.2 mm smaller,
    not exactly the same footprint.
34. **A flat inlay must be inset by the same Rf the top plate uses.** Inset it
    less and it overhangs the edge fillet: in plan the block reads as a sticker
    peeling off the rim. And a colour block "wrapping" an edge cannot be a top
    plate plus a side plate — the bare fillet between them reads as a misprint;
    it wants a partial sweep along the outline.
