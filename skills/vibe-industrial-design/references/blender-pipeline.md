# GLB → Blender Cycles: a studio that outlives the model

The appearance model is regenerated many times a day. Lighting, walls, HDRI, camera and
the hand-tuned "pearl paint" materials must **not** be redone each time. Pattern:

```
three.js ──GLB──►  blender_render.py  ──► out/<name>.blend  (open, tune by hand, F12)
                       ▲                            │
                       │  studio.blend (no device)  ▼
                       └────── blender_extract_studio.py  (device deleted, materials kept,
                                                           {object → materials} table saved)
                    blender_shots.py  ── camera table ──► out/shots/{front,hero,side,back,top,bottom-*}.png
```

## Export from three.js

- **Device only** — hide meshes with `AdditiveBlending` (glow cards); fake bloom is
  wrong offline. Lights, walls, backdrop stay out.
- **Emissive strength baked**: set `emissiveIntensity` on the light bar (~8) and lit
  dots (~5) *during* export (`KHR_materials_emissive_strength`); restore after. At 1.0
  Cycles renders "white plastic", not a lamp.
- **Units**: three.js scene is in mm, glTF is metres → `device.scale = 0.001` on import.
- **Front faces −Y** after the y-up → z-up conversion. Wall on +Y, camera on −Y.
  (First attempt: camera on +Y renders the back.)
- Material **names** travel (`lightbar`, `dots`, `Material_N` for unnamed) — name what
  scripts must find.

## `blender_render.py` (import + studio + render)

- If `studio.blend` exists: `open_mainfile`, import GLB under a `device-root` empty,
  scale, re-attach overrides, render. Else: build a programmatic studio (wall, key +
  fill area lights, low warm world, camera with Track-To).
- **View transform: Khronos PBR Neutral**, exposure ~−0.15. AgX desaturates safety
  orange to salmon and lifts blacks; a product shot must match the swatch.
- `file.pack_all()` before `save_as_mainfile` — glTF textures are in memory; an
  unpacked `.blend` opens magenta.
- Samples argument `0` = save the `.blend` only (write 128 into the file so F12 isn't
  a noise field).

## `blender_extract_studio.py` (sediment the hand tuning)

- Collect the device subtree under `device-root`; for each mesh, record
  `{object.name: [material names per slot]}` where any slot carries a **non-glTF**
  material (i.e. not `Material_N`) → JSON in a text block `studio-overrides.json`;
  set `use_fake_user` on those materials so the purge keeps them.
- Delete device + root; `orphans_purge(do_recursive=True)` ×3; `pack_all()`; save
  `studio.blend` compressed. HDRIs and wall textures ride along, machine-independent.

## Re-attaching overrides (`scenelib.apply_overrides`)

Match by **object name** (stable — the three.js side sets it). Missing object or
missing material → print `[override] …` and continue; never silently drop. Renamed
parts show up in the log the first render after the rename.

## `blender_shots.py` (multi-angle set)

- Camera table: `rot` (device XYZ degrees), `cam` (m), `lens`, `res`, `lit`. The
  **camera moves, the wall doesn't**; back/top/bottom are shown by *rotating the
  device* (a wall-mounted product can't have a camera inside the wall).
- **Lit / unlit**: set Emission Strength to 0 **and** swap Base Color to opal; a
  black-based emissive at strength 0 is a black plastic bar (real unlit diffusers are
  milky).
- **Emissive detection = strength × colour.** Blender 5's Principled has Emission
  Strength **1.0 by default** (with black colour); "strength > 0.5" catches every
  material and `set_emissive` paints the whole device black-pearl.
- **Filter by material name** (`name_prefix='lightbar'`) once the front carries lit
  indicator dots — "lights off" means the bottom bar only.
- HDRI direction: check the first render — the bright side of an environment map is
  often behind the product; rotate the World `Mapping` node 180° in Z and re-shoot.

## Practicalities

- Blender CLI: `/Applications/Blender.app/Contents/MacOS/Blender --background
  --python <script> -- <args>`; parse `sys.argv` after `--`.
- Cycles 128 samples + denoise is enough for review; ~40 s per 1920×1280 frame on an
  Apple GPU; a 7-shot set is ~5 min — run it in the background and keep writing.
- Convert PNG shots to JPEG q90 for the report / repo (`renders/shots/`); keep PNGs in
  the ignored `out/`.
