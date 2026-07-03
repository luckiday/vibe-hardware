# voice-buddy — enclosure (vibe-cad)

A 2-part printed shell for the 70x70 voice-buddy board: **front shell** (front
panel + 4 side walls; the board hangs vertically off the panel's standoffs) and
a **rear cover** (flat plate carrying a rear-firing 40 mm speaker behind a
computed hex grille). Every fit number is read from `constraints.yaml` (the
cad<->pcb contract) via the shipped `cad_contract` loader; the USB receptacle
face position comes from `../pcb/placement.json`; the interference check runs
against the real `../pcb/board.step`.

```
voicebuddy_case.py   the model: param block + build_*() builders + fit_solids()
build_all.py         exports models/ (STEP + STL + the viewer's GLB sidecars)
constraints.yaml     the contract (owned by vibe-plm; do not re-type its numbers)
models/              regenerated outputs — never committed
```

## Build / review / check

```bash
PY=../../../.venv/bin/python           # repo venv (build123d + matplotlib + pyyaml)
SK=../../../skills/vibe-cad/scripts    # shipped tools

$PY voicebuddy_case.py                 # self-check: asserts + volumes + grille ratio
$PY build_all.py                       # export STEP/STL/GLB into models/
$PY $SK/check_fit.py voicebuddy_case.py          # expect 0 mm^3 on all 6 pairs
$PY $SK/section.py voicebuddy_case.py --y 26.5   # X-Z stack: panel/OLED/board/cavity/speaker
$PY $SK/section.py voicebuddy_case.py --y 12     # USB funnel profile in the +X wall
../../../skills/vibe-cad/scripts/cad_viewer.sh "$PWD/models"   # interactive 3D
```

Current results: all 6 fit pairs **0.000 mm³**; grille **61 × ⌀2.5** holes,
open ratio **0.294** (contract min 0.25); rear acoustic cavity **218.9 cm³**
(≥ 100 cm³ heuristic for a small sealed-ish box — not a tuned alignment).

## Frame & stack (Z = depth)

Enclosure X/Y are the **board frame** (board bottom-left = origin, +y up).
Z: rear-cover outer face = 0 → cavity 2.4..44.4 (rear_gap 42, speaker lives
here) → board 44.4..46.0 (F side toward the panel) → front gap 46..58
(OLED + buttons + USB receptacle) → panel 58..60.4. Outer 78.4 × 83.0 × 60.4.

`board.step` is in the KiCad sheet frame (top-left at (100,100), y down;
kicad-cli negates Y): board (bx,by) → STEP (100+bx, by−170), F side facing +Z —
**verified empirically** (bbox min-corner, mic holes at y=50 not 20, USB THT
anchors at (68.55, 12±2.9)), so placement is a pure translation. Gotcha: the
imported Compound's `&` is silently empty — the model intersects the extracted
*solid* (a positive-control probe confirmed the 0.000 results are real).

## Design decisions (contract ambiguities resolved)

- **Antenna keepout vs top mount holes.** The contract bans enclosure
  bosses/metal in the +Y strip (board y 64..70) yet places two mount holes at
  y=66 inside it. Resolution: the two **bottom** holes get full M2.5 heat-set
  standoffs (⌀6.7 posts off the panel, insert bore at the board end; screws
  enter from the back); the two **top** holes get minimal **plastic-only
  locating posts** (⌀5.6) with a ⌀2.45 pin through the board hole — no metal in
  the strip, board clamped by the two bottom screws and located by the pins.
  Runtime assert: no insert/screw position falls inside the keepout box.
- **USB wall opening (+X wall).** J1 sits on the board **front** face, so the
  receptacle spans Z 46..49.4 and the opening axis is `BOARD_FRONT + h/2 =
  47.7`. The receptacle face (placement.json: 66.28 + 8.97/2 = **70.77**) is
  3.4 mm inside the outer wall face, so a plain slot would let the plug bottom
  out: the shipped `patterns.usb_funnel` (throat 9.8×4.0 hugging the contract's
  9.2×3.4 port, lead 2.2 past the inner face) is unioned with a straight
  13.4×7.6 obround **overmold pocket** whose floor sits 1.6 mm outside the
  receptacle face (seated-overmold EST ~2.0 mm — asserted ≤ 2.0). Verified in
  the y=12 section.
- **Round standoffs, not the square `heat_set_boss` body.** The square body's
  corner would come within ~0.2 mm of the USB-C (J1) and speaker-connector (J2)
  bodies at the (66,4)/(4,4) holes; bore/height still use `patterns.boss()`
  numbers. Free-standing posts print vertically (panel face down) — no overhang.
- **Cover screw posts in the shell corners.** Four full-depth ⌀6.7 posts tucked
  into the corners, centers placed (and asserted) ≥ `corner_r + 0.5 + post_r`
  from the board corner arcs so the board's straight-in insertion sweep never
  touches them; this drives `SIDE_CLEAR 1.8` / `TOP_CLEAR 4.2`. Top posts sit
  above the board edge (y≈73), outside the antenna strip.
- **OLED hover.** Module envelope (27.3×27.8×4) centered on the display window
  (35, 26.5) — placement J3 confirms the envelope center; the board's 1x4
  header holes at y≈39.1 match `header_offset_y 12.6` from the module top row.
  Glass front sits 0.5 mm behind the panel inner face (inset behind the drafted
  window), implying a ~7.5 mm header+socket stack — **EST**, check on hardware.
- **Speaker mount.** Locating ring (ID 40.6, 4 mm² wall, 6 tall) on the cover
  inner face *locates* the driver; foam tape / adhesive only *fixes* it. Grille:
  outer ⌀44×1.0 styling recess + 61 × ⌀2.5 hex-packed holes over the ⌀36 baffle
  field (`patterns.holes_in_circle` asserts the 0.25 open ratio). Speaker wire
  reaches J2 (board front, at (10,8)) around the board's bottom/side edge gaps.

## Printed parts + assembly BOM

| # | Part | Qty | Notes |
|---|------|-----|-------|
| 1 | `shell_front` | 1 | print panel face down, no supports; PETG/ABS if sunny desk |
| 2 | `cover_rear` | 1 | print outer face down (grille + counterbores down: clean bridging over ⌀2.5 holes) |
| 3 | `plunger` | 3 | button plungers, captive: drop into the panel holes before the board goes in (flange ⌀7 keeps them in; ⌀2.5 nub rests on the tact switch, 0.3 mm pretravel; tact-switch height 5.0 = **EST**) |
| 4 | M2.5 heat-set insert (⌀3.5 pilot × 5) | 6 | 2 board standoffs + 4 cover posts; press in from the bore side |
| 5 | M2.5 × 6 pan-head screw | 6 | 2 clamp the board (from the back), 4 hold the cover (heads counterbored) |
| 6 | speaker ⌀40 × 20, 4 Ω 3 W | 1 | drops into the ring, fix with foam tape / hot glue |
| 7 | light pipe: ⌀2 clear acrylic rod, ~13.5 long | 1 | glue into the panel bore from inside; ⌀3.2×1.2 shoulder stops it falling out |
| 8 | rubber feet ⌀8 | 4 | recesses on the base (−Y) wall |

Assembly: plungers into the panel → OLED onto its socket → board onto the
standoffs (top pins self-locate it), 2 screws from the back → light pipe →
speaker into the cover ring, wire to J2 → cover on (lip self-locates), 4 screws.

## ESTs to confirm on hardware

- tact-switch actuator height 5.0 (plunger nub length follows)
- OLED header+socket stack 7.5 (glass-to-panel clearance follows)
- seated USB plug overmold face ~2.0 mm behind the receptacle face
- speaker frame/magnet split (12 + ⌀22×8) of the contract's ⌀40×20 envelope
