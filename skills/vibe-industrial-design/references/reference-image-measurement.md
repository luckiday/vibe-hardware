# Measuring an AI look image (turn a picture into tagged numbers)

An AI render (Midjourney / Imagen / a designer's mockup) is the *look*. To drive a
parametric model from it you need numbers, and eyeballing produces arguments. Measure
with code, keep the pixel evidence in the params comments, and make the result
self-consistent.

## 0. Pick the anchor

One real dimension anchors the scale. Candidates, in order of preference:

1. **A hard constraint you already own** — the board you must wrap, a receptacle, a
   sensor window.
2. **Volume parity** with the previous version ("same size, new proportions"):
   `W = sqrt(V / (D · ratio))`.
3. The number the owner said out loud.

Everything else is `px / (px_per_mm)`; write `px_per_mm` next to the anchor.

## 1. Outer bbox and seams — brightness scans

Load as RGB, take the mean channel (`g`). Walk one row/column and print `(x, g)` across
the edge; the outer edge is where the value leaves the background band, the panel gap is
a 1–3 px dark dip, the bevel is a monotone slope between them. Do it at two rows and two
columns (away from features) and average.

```python
def scan(line, lo, hi, step=1): return [(i, int(line[i])) for i in range(lo, hi, step)]
scan(g[350], 140, 175)          # left edge at y=350
scan(g[:, 600], 148, 172)       # top edge at x=600
```

Then: outer W_px, H_px → aspect; bezel = outer edge → gap line; seam x → panel split
fraction; feature centres → offsets from the body centre in mm.

## 2. Corner radius — fit a circle to a clean corner

Use the corner *without* a perforation behind it. For rows y from the top edge down,
find the outermost non-background x. A circle of radius R centred (x_edge − R, y_top + R)
predicts offset `R − sqrt(R² − (R − dy)²)`; solve for R at two or three dy values and
take the one that satisfies all. Sanity: the arc must end (edge becomes vertical) at
`y_top + R`.

## 3. Perforation — pitch, hole, lattice

Along one row through the grille: threshold (`g < 150`), take rising edges → their
diff is the row pitch; the dark run lengths (minus ~1 px anti-alias each side) are the
hole diameter. Along one **column**: if the pitch equals the row pitch → square lattice;
if it is **0.866×** (or you hit every other row at 2× spacing with a half-pitch shift)
→ 60° honeycomb. Also record open area = π/4 · (hole/pitch)² · (1/0.866 for hex).

## 4. Dots, LEDs, small features

A row of dots: threshold along the row, list dark/bright run centres, count them, take
the mean spacing. **Count from pixels, not from looking** — 14 vs 15 dots is a real
design difference and the eye rounds. Note which are lit (bright runs) and which are
dark; a dark one at the end of an LED row may be a microphone hole — ask.

## 5. Colours — mean RGB of flat regions

Sample a flat, evenly lit patch per material (`a[y0:y1, x0:x1].mean(axis=(0,1))`);
for a perforated plate take the 90th percentile (the material between holes). Record
as the *rendered start value* in the CMF table — the real colour comes from a painted
swatch next to a Pantone/RAL chip in daylight.

## 6. Make it self-consistent, then tag

- Round to what tooling can hold (0.4 mm gap, not 0.25).
- Where the picture and a human factor disagree (a 21.5 mm button for elderly fingers),
  round the *safe* way and put the disagreement in the report's open questions.
- Anything the picture doesn't show is a decision, not a measurement — tag `[own]`/`[eye]`
  and say so.
- Save the image into `refs/NN-<version>-<view>.png`; the params comments cite it.

`scripts/measure_ref.py` does 1–5 for a front view (bbox, corner R, colours, optional
row/column pitch and dot count on a given scan line); print its output into the params
comment block.
