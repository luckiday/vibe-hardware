# mic-macropad — industrial design report

**Status:** v1 in progress · appearance only (`vibe-industrial-design`).
Structure, wall thickness, bosses and snap fits belong to `vibe-cad`; this
report hands it the outer envelope, the split lines and the apertures.

---

## §0 Reference basis — what already decided the form

Nothing here is an ID choice. Every number below was fixed by the board
contract [`cad/constraints.yaml`](../cad/constraints.yaml) and
[`pcb/parts.yaml`](../pcb/parts.yaml) before the first picture, and the look
images are judged against them.

### 0.1 The envelope is already set

| | value | source |
|---|---|---|
| board outline | 76 × 56 × 1.6 mm, square corners | `constraints.yaml board.outline` |
| mount holes | 4 × M2 clearance Ø2.2 at (4,4) (72,4) (4,52) (72,52) | `board.mount_holes` |
| board off floor | 5 mm standoff | `stack.standoff_h` |
| closed internal height | 24 mm | `stack.total_h` |
| fit tolerance | 0.5 mm | `tolerance_mm` |

Board frame throughout: origin **bottom-left**, +y **away from the user**, mm.

### 0.2 The top face is already allocated — and it is rear-weighted

The key row is not centred in the board. It sits at **y = 15** of 56, on
19.05 mm centres at x = 18.95 / 38.00 / 57.05, and it *is* centred left-right
(9.95 mm of board either side of the outer caps). What that leaves is a top
face split roughly:

```
y=56  ┌─────────────────────────────────────┐
      │                                     │
      │        rear plateau ~32 mm          │   ← nothing here but the WROOM underneath
      │                                     │
y=24  ├─────────────────────────────────────┤
      │   ▢ key1     ▢ key2     ▢ key3      │   ← 18 mm caps, 19.05 pitch
y=6   ├─────────────────────────────────────┤
y=0   └─────────────────────────────────────┘   ← 6 mm of board in front of the caps
```

**This proportion is the design's central question.** Three keys on the front
edge with a third of the top face left blank behind them is not a keypad
silhouette — it is closer to a desk instrument or a nameplate. The rear
plateau has to be given a job or it reads as a mistake.

### 0.3 Four things must cross the surface — check the band, not the look

| what crosses | where | what that forces |
|---|---|---|
| **2.4 GHz** | antenna keepout, box centre (38, 54.375), **48 × 3.25 mm** at the rear edge | The keepout is a *volume*, not a PCB area: **no metal and no metallised paint above or around the rear edge strip.** A full-width metal top plate blinds the radio. Any metal top must stop short of the rear edge, or the rear band must be plastic. |
| **sound in** | `mic_port` (68.5, 8.5) Ø1.5 — a hole in the **shell floor**, because the ICS-43434 is a **bottom-port** part | The device cannot sit flat on a desk. It needs feet, *and* a defined acoustic path — see R1. |
| **light out** | `led` (66.5, 2.5) Ø2, light-pipe bore | 2.5 mm from the board's front edge: the pipe exits at the **front-right**, not usefully on the top face. |
| **USB-C** | left wall, `center_y 36`, 9.5 × 3.5 | The cable leaves the **rear half of the left side**, away from the typing hand. Asymmetric by intent — do not centre it for looks. |

### 0.4 Two controls the shell has to reach

`SW4` reset (72, 24) and `SW5` boot (72, 17) are **top-actuated** TS-1187A,
4 mm bores, 4 mm from the right board edge. The board README is explicit that
side actuation was tried and lost to sourcing, and that the mechanism
therefore **moved into the shell**: either press straight down through two
top bores, or mould a flexure tab in the right wall that turns a side press
into a down press.

These are bring-up controls, not user controls. The human-machine reading:
**they must not be confusable with the three keys** — different face,
different size, no cap, recessed below the surface.

### 0.5 What is *not* decided, and is therefore mine

Outer W × D × H, corner radius and edge fillet, panel split lines, the
material split, keycap profile and colour, the rear plateau's treatment, foot
height, and where the mic slot and light pipe surface. Everything in §1
onward.

### 0.6 Risks this section already creates

- **R1 — the bottom mic port has no acoustic path yet.** A Ø1.5 hole in the
  floor with the device sitting on a desk is a sealed cavity. Feet alone make
  the *desk* part of the acoustic path and turn every knock into a thump. A
  moulded channel from under U4 to a front-edge slot is the better answer and
  adds a Helmholtz resonance that has to be measured, not assumed.
- **R2 — a metal top plate and the antenna are in direct conflict.** Either
  the plate stops before y ≈ 50, or it is not metal. Decide in the ID, not on
  the bench.
- **R3 — the LED cannot be switched to the top face without moving D4.** If
  the ID wants the indicator anywhere but the front-right corner, that is a
  board change (a 0603 LED and its resistor), and cheap — but it is a board
  change, and `product.yaml revision` has to move with it.

---

## §0.7 v1 direction set — and which ones the constraints already kill

Three prompts, one per direction, sharing a literal `BASE` (every §0 feature and
its position) and `STYLE` (camera, light, exclusions), varying only the middle.
The prompts are kept beside the images in [`refs/prompts.sh`](refs/prompts.sh) —
a picture without its prompt can only be replaced, not iterated.

All three answer the same question: **what is the rear plateau?**

| | [`10-v1-instrument`](refs/10-v1-instrument.jpg) | [`11-v1-monolith`](refs/11-v1-monolith.jpg) | [`12-v1-lectern`](refs/12-v1-lectern.jpg) |
|---|---|---|---|
| rear plateau is… | a bare machined field, closed by a white band at the back | a light — it glows from within | a raised slanted panel, like a lectern |
| shell | anodised aluminium plate on a charcoal plastic base | one milky translucent PC monolith | bead-blasted aluminium wedge on a white base |
| **R2 antenna** | ✅ the white band **is** the keepout, made visible | ✅ all plastic | ❌ **fails** — aluminium covers the rear edge |
| **R1 mic** | ✅ front-edge slot + feet | ✅ front-edge slot + feet | ✅ front-edge slot + feet |
| **flat board** | ✅ | ✅ | ❌ **fails** — keys are normal to a sloped face, so the board tilts |
| board change needed | none | **yes** — a rear LED array | none (but a respin cannot save the antenna) |

Three findings that are worth more than the pictures:

- **A's white rear band is not decoration.** It is the 48 × 3.25 mm antenna
  keepout, promoted to a split line. The one place the metal is not allowed to
  go became the only graphic on the top face. This is the outcome §0 exists to
  produce, and it costs nothing to build.
- **B's headline feature does not exist on the board.** The glow implies an LED
  array under the rear plateau. What `parts.yaml` actually has is **one red
  0603** (D4) at the front-right through a 330R on `LED_DRV`. In a translucent
  shell that single red part lights the whole body *red*, which is not what the
  picture shows. B is buildable, but only as a **board change** — 4–6 side-view
  white LEDs plus a driver on the rear edge. That is a real fork, not a detail.
- **C is the prettiest and the least buildable.** MX switches stand normal to
  the PCB, so keys on a sloped face mean a **tilted board**. At the ~20° the
  image shows, a 56 mm-deep board adds ≈ 19 mm at the rear: internal height goes
  from 24 mm to ≈ 43 mm. And the all-aluminium rear sits directly over the
  antenna. C is a different product, not a finish option.

**Recommendation: A**, with B's key tray borrowed — B's single shallow recess
spanning all three keys reads better than A's three separate milled wells, and
it is one less feature to mould.

### Version log

| v | image | prompt | what it changed | verdict |
|---|---|---|---|---|
| v1 | `10-v1-instrument.jpg` | `refs/prompts.sh $A_NEW` | machined plate + white antenna band | **carried forward** |
| v1 | `11-v1-monolith.jpg` | `refs/prompts.sh $B_NEW` | translucent glowing monolith | held — needs a board change (rear LED array) |
| v1 | `12-v1-lectern.jpg` | `refs/prompts.sh $C_NEW` | rising wedge, slanted rear panel | rejected — antenna under metal, board must tilt |

Measured off `10-v1-instrument.jpg` (`measure_ref.py`), CMF start values:

| patch | rgb | reading |
|---|---|---|
| top plate | `#B0AEAC` | natural/clear anodise, bead blast |
| rear band | `#E3DDD6` | warm off-white, matte |
| base | `#252524` | near-black charcoal, matte |
| accent cap | `#FA8B3E` | safety orange |

Size is **not** taken from these pictures — they are 3/4 views and their
silhouette bbox includes the shadow. The anchor is the board: 76 × 56 mm plus
wall and `tolerance_mm`. The images set *ratios, radii and CMF*; the board sets
absolute size.

## §0.8 v2 — the owner's sheet supersedes the v1 set

The owner returned with a full ID sheet of their own ("MicroPad", Teenage
Engineering × Mondrian: milky white body, primary-colour blocks, three white
caps with a single coloured dot each, and the **clear switch housings left
exposed** in an open tray). That is the direction. The v1 set stays in `refs/`
because the version log's job is to record what was rejected and why — a
direction dropped for a reason that stops applying is the cheapest idea anyone
will ever have.

What v2 keeps from the v1 analysis, unchanged, because the constraints did not
move: the antenna band is still the one strip that may never carry metal (v2's
all-polycarbonate body satisfies R2 for free), the mic still listens through the
floor (R1), and reset/boot still must not be confusable with the three keys.

**Two things in the sheet disagree with each other, and the pixels win.**

1. **Height.** The sheet captions `90 × 60 × 22 mm`, but every picture on it
   shows the switch housings standing well clear of the top face. Measured
   against the MX stack — 2.0 foot + 2.5 floor + **5.0 standoff** + 1.6 board +
   **11.6 housing** = 22.7 mm to the crown — a 22 mm top face clears the housing
   by 0.7 mm and you would see nothing at all. At **18 mm** the housing stands
   4.7 mm proud, which is what the sheet actually draws. `H = 18`.
2. **Depth.** 60 mm is not reachable: 56 mm of board plus a 2.5 mm wall and
   `tolerance_mm` per side is 62 mm minimum. Depth therefore comes from the
   board and **width is set to hold the sheet's ratio exactly** — 93/62 =
   1.500, against the caption's 90/60 = 1.500. The proportion survives intact;
   only the absolute size moves.

Neither is a liberty taken with the design. Both are the same rule: *the picture
wins over its own caption, then the numbers are made self-consistent.*

---

## §1 Industrial design

### 1.1 Dimensions

| | mm | provenance |
|---|---|---|
| W × D × H | **93 × 62 × 18** | ratio [v2], depth [pcb], height [v2] pixels |
| bezel, left / right | **3.0 / 14.0** | [pcb] — the board sits hard left, see §1.5 |
| key row centre | 5.5 mm left of the shell centre | derived — the row is centred on the *board* |
| plan corner radius `Rc` | 6.0 | [v2] |
| edge fillet `Rf` | 1.6 | [v2] — independent of `Rc`; that is the whole reason the body is a swept skin and not a rounded box |
| wall | 2.5 | [std] |
| parting line height | 9.0 | [eye] — deliberately **below** the USB opening (10.9–14.4) |
| foot | Ø8 × 2.0, 9 mm in from each corner | [eye] |
| key tray | 61.1 × 23.0, R2.5, floor at z 13.0 | derived from cap + `trayMargin` |
| service strip line | local x 33 (= board x 71) | [eye] |
| front band | local y −31 … −24.5 (the tray's own front wall) | derived |
| rear band | local y 24.75 … 31 | [pcb] antenna keepout |
| caps top out at | 31.7 above the desk | derived |

Every one of these lives once, in [`scene/params.js`](scene/params.js), tagged.
A value with no tag is a bug.

### 1.2 Why the switches are exposed, and why it only works at 18 mm

The sheet's signature is the open tray with the clear MX housings showing. That
is not a finish choice — it is a height budget, and the board already spent most
of it:

```
  2.0  feet          (R1: the mic port is a hole in the floor)
  2.5  shell floor
  5.0  standoff      [pcb] stack.standoff_h
  1.6  board         [pcb]
 11.6  MX housing    [std]
─────
 22.7  crown of the switch
 18.0  top face      →  4.7 mm of switch stands proud
```

Raise the face to the captioned 22 mm and the design's whole idea vanishes into
a 0.7 mm sliver. This is the number to defend in review.

The **gaps between the caps are not a choice either.** 19.05 mm pitch minus an
18.0 mm 1u base leaves 1.05 mm. An early pass "fixed" that by shrinking the cap
to 16.5 mm, which is a custom part solving a problem that does not exist: what
makes a real keyboard look generously spaced is the cap **taper**. An XDA/MA
profile goes 18.0 at the base to 15.4 at the crown, so the eye reads 3.7 mm at
the top while the bases stay standard. Stock caps, stock pitch, correct look.
(DSA's 12.7 mm crown was tried and reads as a lampshade in side elevation.)

### 1.3 The Mondrian grid is the constraint map

Every line is a constraint and every block names what is under it. This is the
section to read if the scheme ever looks arbitrary:

| block | where | what is underneath | why that colour is there |
|---|---|---|---|
| **blue** | rear band, left 26 mm | the WROOM and its antenna | its front edge **is** board y 52.75, the leading edge of Espressif's keepout. The one strip that may never carry metal is the one strip that carries colour. |
| **red** | right strip, local y −14…−1 | reset (y −4), boot (y −11) | "service — don't touch unless you mean it" |
| **yellow** | front band, local x 4…28 | the mic slot and the indicator | "it listens here". Its rear edge **is** the tray's front wall — one line, not two lines 1 mm apart. |
| **black** | the tray floor | the three switches | a recess with a light floor stops reading as a recess |
| **blue** (low) | front-left of the lower shell | nothing | the front elevation needs weight on the left or the whole face leans right. The one purely compositional block, and it says so. |

Two deviations from the sheet, both recorded rather than quietly taken:

- **The colour blocks do not wrap over the edges.** The sheet wraps them. A flat
  plate cannot follow an edge fillet, and a "wrap" built from a top plate plus a
  side plate leaves a 1.6 mm band of bare fillet between them that reads as a
  misprint. Flat top-face fields instead. A true wrap wants a partial sweep
  along the outline — a v3 job, and cheap when it comes.
- **No wordmark.** The sheet laser-etches "MicroPad"; the repo calls this
  `mic-macropad`. Naming is Q1, not a decision to make inside a render.

### 1.4 Face → element allocation

| face | carries |
|---|---|
| top | key tray (3 × MX, exposed) · blue rear band · red service strip · yellow front band |
| front | mic slot (board x 52) · indicator (board x 66.5, D4's own position) · low blue block — mic and LED share one baseline at z 4.4 |
| left | USB-C, **rear of centre** at board y 36, so the cable leaves away from the typing hand |
| right | reset (board y 24) and boot (board y 17), Ø4 bores at z 11.5 |
| bottom | four feet · the Ø1.5 mic floor port · four M2 bosses (vibe-cad) |

---

### 1.5 The board is not centred, and USB-C is why

A USB Type-C plug's metal shell is 6.5 mm long. Centre a 76 mm board in a 93 mm
shell and its left edge sits **8.5 mm** behind the outer face — the receptacle
ends up down a tunnel no plug can bottom out in. The port would have looked
perfect in every render and failed on the first cable.

So the board sits **hard left**, one wall thickness (3.0 mm = wall + 
`tolerance_mm`) from the left face, and all 14 mm of slack goes to the right,
where the service strip wants it anyway. Two things fall out for free:

- The **key row is 5.5 mm left of the shell centre** — which is what the owner's
  sheet draws: keys left, wide strip right. The constraint and the picture
  wanted the same layout.
- **R3 closes.** D4 at board x 66.5 now lands inside the front band on its own.
  No light-pipe run, no board change; `ledExitX` is just `windows.led.x`.

The receptacle itself is a reusable part — [`scene/usbc.js`](scene/usbc.js),
built from the KiCad land the board actually specifies (`F.Fab` of
`USB_C_Receptacle_HRO_TYPE-C-31-M-12` measures **8.94 × 7.30 mm**) plus the
Type-C spec's cavity and tongue. A Type-C opening is never a rectangle: every
corner is a full half-height radius, and drawing it square is the most obvious
tell in a render.

![USB-C detail](renders/detail-usbc.jpg)

## §2 CMF

| part | material | finish | rendered | real-world start point |
|---|---|---|---|---|
| shell (upper + lower) | PC, milky warm white | soft-touch, matte | `#F2F0EB` | roughness 0.62 |
| key tray floor | PC, black | matte | `#222321` | roughness 0.85 |
| keycaps | PBT, XDA/MA profile | matte | `#F7F6F2` | roughness 0.55 |
| switch lower housing | nylon, black | — | `#26272A` | stock MX |
| switch upper housing | PC, clear | gloss | `#C9CDD2` @ 0.85 α | stock MX |
| blue block | 2-shot or IMD | semi-matte | `#1F5FA9` | roughness 0.45 |
| red block | ″ | ″ | `#D3372B` | ″ |
| yellow block | ″ | ″ | `#F0C22E` | ″ |
| cap dots | pad print or 2-shot | ″ | blue / red / `#141414` | ″ |
| indicator | PMMA light pipe | polished | emissive `#FF6A44` @ 2.4 | red 0603, worst-case Vf 2.6 V |
| feet | TPE | matte | `#2A2A28` | roughness 0.95 |
| aperture cavities | — | — | unlit `#0B0B0B` | see note |

**The cavity material is not styling.** It is `MeshBasicMaterial` — *unlit*.
With a lit material the fill light reaches into every opening and each one fills
with a pale disc, so a bore renders as a white dot printed on the shell. The
opening walls get their own darker material for the same reason: off-axis you
mostly see the wall of an opening, not the space behind it.

---

## §3 Small-batch manufacturing

**A / B / C tiers.** A = the three caps and the shell halves (SLA or CNC,
in-house). B = the colour blocks (pad print at this volume; 2-shot or IMD only
past a few hundred). C = bought parts — MX switches, keycaps if not printed,
TPE feet, PMMA rod for the light pipe.

Notes that matter at low volume:

- **The tray is the plate.** Its floor carries three 14 × 14 mm cutouts so the
  switches clip in — which is exactly `windows.key1/2/3` in the board contract,
  Ø14. That number did not have to change.
- **The light pipe runs 4.5 mm sideways** (board x 66.5 → 71). A straight
  polished rod with one bend; at this volume, cut from 2 mm PMMA rod.
- **The mic channel** runs from the floor port at board (68.5, 8.5) to the front
  slot at board x 58 — see R1.

### Risks

- **R1 — the mic's acoustic path is still unproven.** A Ø1.5 floor port vented
  sideways to a front slot is a duct, and a duct is a Helmholtz resonator. The
  2 mm feet stop the desk sealing the port; they do not make the response flat.
  This needs measuring on the first shell, not assuming. *If it misbehaves, the
  cheap fix is board-side — move U4 toward the front edge and shorten the duct.*
- **R2 — closed by the material choice.** An all-PC body puts no metal over the
  antenna. It reopens the moment anyone proposes a metal top plate or a
  metallised paint; §1.3 is why the rear band is blue.
- **R3 — CLOSED.** The indicator wanted to be 4.5 mm right of D4 while the board
  was centred. Moving the board hard left (§1.5) put D4 where the ID wanted it.
  No light pipe run, no board change.
- **R5 — the receptacle still has to reach the outer face.** §1.5 buys the
  reach; it does not guarantee the last millimetre. The HRO part is 7.30 mm deep
  and overhangs the board edge by ~0.65 mm, so with a 2.5 mm wall the plug
  enters ~2.4 mm of tunnel before it meets the shell. Check J1's overhang
  against the Hroparts drawing before the wall thickness is frozen; if it is
  short, thin the wall locally at the port rather than moving the board again.
- **R4 — the model's apertures are modelled, not cut.** The body is a continuous
  swept skin, so each opening is an unlit dark face at the surface rather than a
  hole. The read is identical at review distance and every number comes from
  `params.js`, but nobody should take the GLB as a manufacturing solid.

### What this ID asks of the board contract

One line, and it is a real cross-domain change:

> `cad/constraints.yaml` → `stack.total_h: 24` is no longer true. It described a
> shell that **encloses** switch and cap. This design deliberately does not: the
> internal height is **13.5 mm** (floor top to the underside of the top face),
> and the switches and caps live outside the shell. Changing it bumps
> `product.yaml revision`.

Everything else in the contract survives untouched — outline, mount holes, the
USB port, the three Ø14 key windows, the mic floor port, the LED bore, the two
button bores, and the antenna keepout.

---

## §4 Open questions

- **Q1 — the name.** The sheet says "MicroPad"; the repo says `mic-macropad`.
  No wordmark is modelled until this is settled.
- **Q2 — what are the three keys?** Firmware is a stub, so each cap carries a
  single coloured dot and nothing else. A dot commits to nothing; an icon
  freezes an undecided function into a mould.
- **Q3 — dot colours or cap colours?** The sheet uses white caps with coloured
  dots. One coloured cap (the v1 "instrument" direction's orange key) reads
  faster across a desk. Cheap either way at this volume.
- **Q4 — hot-swap?** The sheet's spec strip says "hot swap, 3-pin compatible".
  The board solders MX lands directly. Kailh sockets are a board change and add
  1.8 mm under each switch, which the 5 mm standoff can absorb — but it is a
  respin, so it needs to be wanted before it is drawn.

## §5 Next steps

1. Settle Q1–Q5.
2. Decide the `stack.total_h` contract change and bump `product.yaml revision`.
3. Blender/Cycles finals from `scene/out/mic-macropad.glb` (mm→m at 0.001,
   front faces −Y), with a `studio.blend` extracted and reused.
4. Hand `params.js` to `vibe-cad`: W/D/H, `Rc`/`Rf`, wall, the tray footprint
   and floor height, and the five apertures. Structure — bosses, snap fits,
   draft, the mic duct — is that skill's job, not this one's.

### Version log

| v | image / model | what changed | verdict |
|---|---|---|---|
| v1 | `refs/10-v1-instrument.jpg` | machined plate + white antenna band | superseded by v2; its §0 analysis carried forward |
| v1 | `refs/11-v1-monolith.jpg` | translucent glowing monolith | rejected — the glow needs a rear LED array the board does not have |
| v1 | `refs/12-v1-lectern.jpg` | rising wedge, slanted rear panel | rejected — antenna under metal, and MX keys normal to a slope force a tilted board |
| **v2** | owner's MicroPad sheet → [`scene/`](scene/), [`renders/sheet.jpg`](renders/sheet.jpg) | TE × Mondrian, exposed switches, H 18 not 22, 93 × 62, flat colour fields | **current** |

Prompts for the v1 images are in [`refs/prompts.sh`](refs/prompts.sh). The v2
sheet came from the owner and should be saved to `refs/20-v2-mondrian-sheet.png`
— a picture without its source cannot be iterated, only replaced.
