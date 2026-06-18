# build123d patterns & the recurring gotchas

The modeling half. Distilled from real enclosure builds — see a worked model under
`examples/` (e.g. `examples/pager-buddy/cad/`) for the full, working code.

Run everything with the shared venv:
`.venv/bin/python` (build123d 0.10, py3.12;
has matplotlib + PIL too).

## File structure (one model, importable)

```python
# 1) PARAM BLOCK — every dimension named; derived values computed from them
PLATE, WALL = 1.6, 2.4
CAN_TOP  = PLATE + GAP_CAN + CAN_H        # derived — change CAN_H, this follows
CAR_BOT  = BRK_TOP + HDR_GAP             # the whole stack re-derives consistently

# 2) BUILDERS — no side effects (no file writes); return labelled parts
def build_tray():  ... ; tray.label = "..."; return tray
def build_cover(): ...
def build_fit():       return Compound(children=[build_tray(), build_carrier(), build_xiao(), build_thermal()])
def build_exploded():  ...   # parts lifted along +z to show the stack-up
```

Exports live in a **separate** `build_all.py` so `section.py` / `check_fit.py` /
the viewer can `import` the builders without writing files. Convention: `z=0` is the
reference face (e.g. the outer window), `+z` into the part.

## Placement & boolean idioms

- `Pos(x,y,z) * Box(...)` / `Rot(rx,ry,rz) * solid` — translate / rotate. `Align`
  (`MIN/CENTER/MAX` per axis) sets which face the position pins.
- `+= / -=` union / cut; `&` intersect (used by the fit-check).
- **Tapered window / cone** = `loft([Rect@z0, Rect@z1])` between two rectangles at
  different z — flare it at the sensor FOV half-angles so it never clips:
  `half(z) = tan(FOV/2)*(PUPIL_Z - z) + margin`.
- **Chamfer defensively** — one un-chamferable edge throws and kills the build.
  Wrap it:

  ```python
  def try_chamfer(part, edges, size, tag):
      if not edges: return part
      for s in (size, size*0.6, size*0.35):
          try: return chamfer(edges, s)
          except Exception: pass
      print(f"chamfer SKIP: {tag}"); return part
  ```

  Select edges by geometry (`e.center().Z`, distance from a face), not by index.

## Loading a real module STEP (fit-check)

A vendor STEP (Seeed XIAO, Melexis can) beats any EST envelope — **use the real
model when you have one.** But its coordinate frame is **arbitrary** (origin
anywhere, long axis on any axis, connector facing any way), so **discover the
frame before you place it** — dump every solid's bbox and read off where the
landmarks are:

```python
raw = import_step(str(MOD_STEP))
for i, s in enumerate(raw.solids()):              # frame is unknown — inspect, don't guess
    b = s.bounding_box()
    print(i, [round(v,1) for v in b.center], [round(v,2) for v in b.size])
# now you can SEE it: solid 18 = USB shell (8.94 long) at +x → USB exits +x;
# the can model's axis ran along z with the seating plane at z=-1.5, cap at +z.
```

Then seat off a **named** solid's bbox (not a guessed number) and pick the `Rot`
that maps the landmark into your enclosure frame (components up, USB out the +x
wall, can-down through the window):

```python
pcb  = max(raw.solids(), key=lambda s: s.volume)   # board = biggest solid
b    = pcb.bounding_box()
xiao = Pos(XL - b.min.X, ..., PAD_TOP - b.min.Y) * Rot(90,0,0) * raw
can  = Pos(WX, WY, SEAT - 1.5) * Rot(180,0,0) * raw_can   # flip can-down, seat plane on board
```

Trim leads/overhang with an intersect against a big box if a part pokes through
(`can = can & Pos(0,0,-50+CUT_Z) * Box(100,100,100)`). Off-the-shelf parts
(standoffs, servos) — pull from the **`step-parts`** catalog rather than modeling.

**A photo can correct an EST a datasheet can't.** This session a board guessed at
16×15 with the hole pair on the long edge turned out (from one clear board photo)
to be **16×12 with the castellated pads on a *short* edge** — which flips the
whole interior layout and the FOV axis mapping. When the user sends a real photo,
re-measure the outline/feature edges off it and re-derive; don't keep the EST.

## Reviewing — section over 3D-matplotlib

- **matplotlib mplot3d cannot z-sort overlapping faces** → 3D mesh previews come out
  muddy and unreadable. Use them only for a rough massing glance (`render_views.py`).
- The **dimensioned X–Z cross-section** (`section.py`, drawn to scale from the param
  block with matplotlib `Rectangle`/`Polygon` + arrow dims) is the real review view —
  it shows the stack-up, clearances, and the FOV cone unambiguously.
- For interactive 3D, use the **CAD Viewer** (`references/cad-viewer.md`), not
  matplotlib.
- **Boolean-section the `build_fit()` compound** to eyeball internal stack-ups the
  2D `section.py` schematic can't show (a cover rib landing on a real connector, a
  screw-boss stack, lead clearance under a lid). Cut every child against a
  half-space box and snapshot the cut — it slices the *real vendor geometry*, not a
  param-block cartoon:

  ```python
  sec = Compound(children=[c & Pos(0,50,0)*Box(200,100,200) for c in build_fit().children])
  export_step(sec, "/tmp/fit_section.step")     # then snapshot front + iso
  ```

  This is the fastest way to confirm "does the **back plate's** boss/rib actually
  clear the parts" — exactly the question a `build_fit` with the cover added answers.

## Interference check (don't eyeball it)

`check_fit.py` boolean-intersects every placed board/module against each shell part
and sums the volume — **expect 0 mm³**. Coincident design faces (a board resting on
a boss) intersect to zero, so a tolerance of ~1 mm³ separates "touching" from a real
clash. Re-run after every param change; it's the only certain "the board doesn't
cross the wall" answer.

```python
for sp in part.solids():
    for sh in shell.solids():
        inter = sh & sp
        if inter: v += sum(s.volume for s in inter.solids())
```

## Design-for-fabrication gotchas (caught this session)

- **Make the geometry self-locate the part (poka-yoke); let adhesive only *fix*,
  never *locate*.** A hand assembler has no jig — the print must register the part
  so it *can't* go in wrong. A bore sized to a round can (`OD_max + ~0.5` clearance)
  self-centers it on the window axis, and the part lands on the bore rim so the
  **seat height comes for free**; an *asymmetric* stop wall against one board edge
  fixes rotation (poka-yoke against a flipped sensor whose wide/tall FOV would
  transpose). Hot glue / VHB then just holds it — a glue-only mount with no locating
  feature drifts. (This replaced two flat glue rails that "made it hard to place.")
- **Connector openings: size to the max *plug overmold*, and seat the receptacle
  ~flush with the inner wall.** A hole cut snug to the receptacle won't pass a
  molded cable — size to the standard's max overmold (USB-C: **12.35 × 6.5 mm**,
  USB-IF), as a **stadium slot** (rounded ends — cleaner look, no sharp internal
  corners). And check the depth: if the receptacle face protrudes `p` past the PCB
  edge and the wall sits `m` from that edge, you need `p ≥ m` (receptacle ideally
  pokes slightly into the slot) or the plug bottoms on the wall before it seats.
  Verify it in `build_fit` with the real connector solid, not by eye.
- **Size an FOV window to the *cone*, not to the render.** In a 3D view the sensor
  *body* (e.g. a Ø9.3 can) fills the opening and looks cramped, but only the small
  Ø2.6 *aperture* needs to see out — don't enlarge the window because the render
  feels tight. Prove it numerically instead: the cone half-extent at height z is
  `tan(FOV/2)*(PUPIL_Z - z)`; assert the opening exceeds it + margin at **both**
  z=0 and the inner face. A bigger-than-needed window only weakens the thin front
  face and reads more "camera-like."
- **Pull critical dims from the datasheet figure and cite it.** Replace EST guesses
  with the drawing's numbers where one exists (90642 can: `Ø9.30±0.15, h5.70±0.30,
  aperture Ø2.60` from Fig.29) and name the source in the param comment so the next
  person can check it. Caliper-EST only for what no drawing covers.
- **Rectangular boss, round only the hole.** A free-standing cylindrical boss
  protruding into a cavity prints with a steep curved overhang and is sink-prone in
  tooling. Make the solid backing a **cuboid** merged into a wall; keep only the bore
  round.
- **Continuous chamfer across a seam.** Two-part shells look misaligned if the tray's
  outer verticals are chamfered but the cover's aren't — give **both** the same
  vertical chamfer so the closed-box silhouette is continuous.
- **Printable snap detents.** A half-round bead on a thin flexing lip + a matching
  groove, on the long walls only (corners are stiff), with small (~0.15 mm)
  interference — and keep both as horizontal half-round features on vertical walls so
  the only overhang is a tiny curve the printer bridges. State the print orientation.
- **Mind the print/tooling orientation in the geometry**, and note it + any caveat
  (sink → core out a thick block; draft) in the README.
- **EST everything you didn't measure.** Stack heights, a module's exact extents, and
  which board axis a sensor's wide-vs-tall FOV maps to are estimates until checked on
  the real assembly — flag them in the README and re-run `check_fit.py` after.
