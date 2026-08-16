#!/usr/bin/env python3
"""Measure an AI look image (front view) into numbers you can put in params.js.

    python3 measure_ref.py <image> --anchor-w <mm> [--bg-tol 8] [--row Y] [--col X]
                                    [--patch x0,y0,x1,y1 --patch …]

Prints: outer bbox (px), aspect, px/mm from the anchor width, corner radius fit
(top-right corner), and — with --row / --col through a perforated area — the hole
pitch + hole diameter along that line (and hex vs square from the ratio). Each
--patch prints its mean RGB (a CMF start value). Needs Pillow + numpy.

Method notes: references/reference-image-measurement.md. This gets you the first
80 %; seams, buttons and dot rows are quicker with a few ad-hoc scans in a REPL —
print the pixel evidence into the params comments either way.
"""
import argparse
import math

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('image')
ap.add_argument('--anchor-w', type=float, required=True, help='real front width in mm')
ap.add_argument('--bg-tol', type=float, default=8.0, help='how far from the background band counts as object')
ap.add_argument('--row', type=int, help='y of a scan line through the perforation')
ap.add_argument('--col', type=int, help='x of a scan line through the perforation')
ap.add_argument('--dark', type=int, default=150, help='threshold for a hole pixel')
ap.add_argument('--patch', action='append', default=[], help='x0,y0,x1,y1 region to average (repeatable)')
a = ap.parse_args()

im = Image.open(a.image).convert('RGB')
A = np.asarray(im).astype(int)
g = A.mean(axis=2)
H, W = g.shape
bg = np.median(np.concatenate([g[:20].ravel(), g[-20:].ravel(), g[:, :20].ravel(), g[:, -20:].ravel()]))
obj = np.abs(g - bg) > a.bg_tol
rows = np.where(obj.sum(axis=1) > W * 0.05)[0]
cols = np.where(obj.sum(axis=0) > H * 0.05)[0]
x0, x1, y0, y1 = cols.min(), cols.max(), rows.min(), rows.max()
wpx, hpx = x1 - x0, y1 - y0
ppmm = wpx / a.anchor_w
print(f'image {W}x{H}, background ≈ {bg:.0f}')
print(f'outer bbox x {x0}..{x1} y {y0}..{y1}  → {wpx}×{hpx} px, aspect {wpx / hpx:.3f}')
print(f'scale {ppmm:.2f} px/mm  → W {a.anchor_w:.1f} mm, H {hpx / ppmm:.1f} mm')

# corner radius: top-right, rows from y0 down; rightmost object pixel per row
pts = []
for dy in range(2, min(200, hpx // 3), 2):
    r = obj[y0 + dy, x0:x1 + 1]
    xs = np.where(r)[0]
    if len(xs):
        pts.append((dy, x1 - (xs.max() + x0)))   # (dy, inset from the right edge)
best = None
for R in range(4, min(wpx, hpx) // 2):
    err = 0.0
    n = 0
    for dy, off in pts:
        if dy >= R:
            break
        pred = R - math.sqrt(max(0.0, R * R - (R - dy) ** 2))
        err += (pred - off) ** 2
        n += 1
    if n >= 3:
        err /= n
        if best is None or err < best[1]:
            best = (R, err)
if best:
    print(f'corner radius (top-right fit) ≈ {best[0]} px = {best[0] / ppmm:.1f} mm  (R/short side {best[0] / min(wpx, hpx):.3f})')


def runs(line):
    d = (line < a.dark).astype(int)
    edges = np.where(np.diff(d) == 1)[0]
    lens, c = [], 0
    for v in d:
        if v:
            c += 1
        elif c:
            lens.append(c)
            c = 0
    return edges, lens


rp = cp = None
if a.row is not None:
    e, l = runs(g[a.row, x0:x1])
    if len(e) > 3:
        rp = float(np.median(np.diff(e)))
        print(f'row y={a.row}: pitch {rp:.1f} px = {rp / ppmm:.2f} mm, hole {np.mean(l):.1f} px = {np.mean(l) / ppmm:.2f} mm (incl. AA), n={len(e)}')
if a.col is not None:
    e, l = runs(g[y0:y1, a.col])
    if len(e) > 3:
        cp = float(np.median(np.diff(e)))
        print(f'col x={a.col}: pitch {cp:.1f} px = {cp / ppmm:.2f} mm, n={len(e)}')
if rp and cp:
    k = cp / rp
    kind = 'square' if abs(k - 1) < 0.08 else ('60° hex (col = 0.866×row)' if abs(k - 0.866) < 0.08 else ('60° hex, every other row (col = 1.73×row)' if abs(k - 1.732) < 0.12 else '?'))
    print(f'lattice: col/row = {k:.3f} → {kind}')

for p in a.patch:
    px0, py0, px1, py1 = (int(v) for v in p.split(','))
    m = A[py0:py1, px0:px1].reshape(-1, 3).mean(axis=0)
    print(f'patch {p}: rgb ({m[0]:.0f},{m[1]:.0f},{m[2]:.0f}) = #{int(m[0]):02X}{int(m[1]):02X}{int(m[2]):02X}')
