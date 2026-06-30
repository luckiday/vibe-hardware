# USB connector cutouts (enclosure wall openings)

How to cut a USB port opening in an enclosure wall so the **cable plug** seats fully
and the **cable boot/overmold** doesn't foul the shell. Centered on **USB-C** (the one
we've validated on hardware); the method generalizes to micro-B / USB-A.

> One-line rule: **size the opening to clear the RECEPTACLE on your board, then flare
> it to clear the cable overmold.** Do NOT size it to the bare plug shell — the
> board's receptacle is bigger and usually pokes into the wall.

---

## The two objects you're clearing (don't confuse them)

| Object | What it is | USB-C size (W × H) |
|---|---|---|
| **Plug metal shell** | the male shell on the *cable* (USB-IF hard spec) | **8.34 × 2.56 mm**, obround, R = 1.28 (= H/2) |
| **Receptacle shell** | the female connector *on your PCB* the plug inserts into | **≈ 8.94 × 3.26 mm** (typical 16-pin SMD) |
| **Cable overmold** | the bulky strain-relief boot behind the plug | varies wildly; USB-IF max envelope is large, cheap cables larger |

The classic "USB-C cutout = 9.0–9.5 × 3.2–3.5 mm" rule of thumb is derived from the
**plug shell + 0.3–0.6 mm/side**, and it assumes the receptacle is recessed *behind*
the wall so only the slim plug passes through. **That assumption is often false.** On
edge-mounted boards (XIAO, many dev boards) the receptacle overhangs the board edge by
~0.7–0.9 mm and ends up *at or inside* the wall — so the opening has to clear the
**receptacle** (8.94 × 3.26), not the plug. Sizing to the plug-based 3.2–3.5 mm height
leaves ~0–0.12 mm/side over the receptacle and **pinches it once you add print
tolerance**. Measure where your receptacle face lands relative to the wall before
picking numbers.

## Shape: obround, full radius

The USB-C connector is **obround** (stadium / capsule — two full semicircle ends), not
a rounded-square. Corner radius = H/2. Cut the wall opening as an obround too (or a
generous round-cornered rect, R ≥ 1.6 mm) so it conforms to the plug and demolds clean.
In build123d that's `RectangleRounded(w, h, h/2 * 0.999)` (the `*0.999` avoids a
degenerate full-radius edge case).

## Clearances (per side)

| Gap | Value | Notes |
|---|---|---|
| Opening vs **receptacle** | **0.3–0.6 mm/side** | the gap that actually matters when the receptacle is at the wall |
| Opening vs **plug shell** | 0.5–0.8 mm/side falls out of the above | don't design to this directly |
| Print tolerance to absorb | budget ~0.1–0.2 mm | FDM; eats into the gap, so don't run tight |

---

## Preferred pattern: a conforming FUNNEL (not a straight slot)

A straight slot sized for the overmold is a big ugly hole; a slot sized for the plug
won't let a fat cable boot approach the receptacle. Resolve both with a **funnel**: a
snug obround **throat** at the inner face that hugs the receptacle, flaring through the
wall to a wider **mouth** that clears the overmold. The taper is the cable's lead-in.

```
   outer mouth            inner throat
  (clears overmold)      (hugs receptacle)
   ┌───────────┐          ┌─────┐
   │  13 × 7   │ ───────► │9.8×4.2│ ──► receptacle (8.94×3.26) ──► plug seats
   └───────────┘  taper   └─────┘
   outside                inside the box
```

Validated numbers (TC5.1-Xiao, XIAO ESP32-S3 edge receptacle, ~2.4 mm wall):

| Feature | W × H | Radius | Clears |
|---|---|---|---|
| **Throat** (inner) | 9.8 × 4.2 | 2.1 | receptacle 8.94 × 3.26 → 0.43 / 0.47 mm per side |
| **Mouth** (outer) | 13.0 × 7.0 | 3.5 | cable overmold (USB-IF max envelope) |

Overmold recess, if you want the boot to sit flush/semi-flush: open the mouth to
**⌀12–14 mm** equivalent; depth = how far you want it sunk. There is **no standard
overmold size** — cheap cables are fat and long — so size to the cable your user will
actually plug in and accept that some boots won't fully sink.

### build123d recipe

```python
# Funnel axis along +X through the wall; opening centered on the receptacle axis (USB_AX in Z).
USB_IN_W, USB_IN_H  = 9.8, 4.2     # throat — hugs the receptacle shell (~8.94×3.26)
USB_OUT_W, USB_OUT_H = 13.0, 7.0   # mouth  — clears the cable overmold
USB_LEAD = 0.6                      # throat runs this far past the inner face (clears receptacle)

def _usb_sk(x, w, h):               # obround cross-section in the wall plane at X = x
    return Plane(origin=(x, 0, USB_AX), x_dir=(0, 1, 0), z_dir=(1, 0, 0)) \
        * RectangleRounded(w, h, h/2 * 0.999)

xi, xo = X_INNER_WALL, X_OUTER_WALL
usb  = extrude(_usb_sk(xi, USB_IN_W, USB_IN_H), amount=-(USB_LEAD + 1.0))   # snug throat, inward
usb += loft([_usb_sk(xi, USB_IN_W, USB_IN_H),
             _usb_sk(xo + 0.3, USB_OUT_W, USB_OUT_H)])                      # flared mouth
shell -= usb
```

Centering the opening in Z: put the axis on the **receptacle** center, e.g.
`USB_AX = CARRIER_TOP + pcb_to_conn_z + receptacle_H/2`. Sanity-check it against the
imported board STEP, not just the number.

---

## Other USB families (same method, different numbers)

| Connector | Plug shell W × H | Cut opening (rect, R ≥ 1) | Overmold mouth |
|---|---|---|---|
| **USB-C** | 8.34 × 2.56 (obround) | clear receptacle 8.94 × 3.26 → ~9.8 × 4.2 | ⌀12–14 |
| **micro-B** | 6.85 × 1.8 | ~8 × 3 | ~10–11 |
| **USB-A (host)** | 12.0 × 4.5 | ~13 × 5.5 | rarely overmolded |

Always confirm against the *receptacle on your board* and the cable you'll use — the
plug-shell column is only the USB-IF anchor.

## Verify before printing

- [ ] Opening is **obround / R ≥ 1.6**, not a sharp-cornered rect.
- [ ] Throat clears the **receptacle** (not just the plug) by 0.3–0.6 mm/side — check
      against the board STEP, not the datasheet plug number.
- [ ] Axis centered on the receptacle in Z (eyeball it in the CAD Viewer fit view).
- [ ] Mouth clears the overmold of the **cable you'll actually use**; recess depth set.
- [ ] `check_fit.py` shows the connector STEP passing through with **0 mm³** wall overlap.
- [ ] Print tolerance (~0.1–0.2 mm) won't pinch the tightest gap.

## Record it in the interface contract

The port belongs in the pcb↔cad `constraints.yaml` (vibe-plm). Record **both** the
throat and the mouth, and the receptacle-vs-plug rationale, so nobody "corrects" a
funnel back into a pinching plug-based slot:

```yaml
ports:
  usb_c:
    wall: "+X"
    axis_z: 18.13
    throat: { w: 9.8, h: 4.2, radius: 2.1 }   # inner aperture (obround), hugs receptacle
    mouth:  { w: 13.0, h: 7.0, radius: 3.5 }   # outer mouth (obround), clears overmold
```
