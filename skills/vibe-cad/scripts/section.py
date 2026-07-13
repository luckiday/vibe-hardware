"""section — X–Z cross-section of the fit assembly, rendered to PNG for review.

    .venv/bin/python skills/vibe-cad/scripts/section.py <model.py> [--y <mm>] [--out section.png]

Slices every solid from the model's `fit_solids() -> dict` with the X–Z plane at
the given Y (default: the assembly bbox center) and draws the section outlines —
one color per solid, mm grid, equal aspect. This is the measurement view: unlike
a 3D matplotlib render (which can't z-sort) it shows stack-up and clearances
unambiguously, and it slices the REAL geometry, not a param-block cartoon.

If the model defines `DIMS: dict[str, float]` (label -> mm), they're printed as
a dimension table in the figure margin — put the numbers a reviewer needs to
check (stack heights, clearances) there.
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from check_fit import import_model   # same dir; shared by-path importer


def outline_polylines(solid, y: float):
    """Section `solid` at plane Y=y -> list of [(x, z), ...] polylines."""
    from build123d import Part, Plane, section
    if not isinstance(solid, Part):
        solid = Part() + solid                # section() wants a Part
    plane = Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    try:
        sk = section(solid, section_by=plane)
    except Exception:
        return []                             # plane misses the solid entirely
    lines = []
    for e in sk.edges():
        n = 2 if e.geom_type.name == "LINE" else 32
        pts = [e @ (i / (n - 1)) for i in range(n)]
        lines.append([(p.X, p.Z) for p in pts])
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", help="model .py exposing fit_solids() -> dict")
    ap.add_argument("--y", type=float, default=None,
                    help="section plane Y in mm (default: assembly bbox center)")
    ap.add_argument("--out", default="section.png", help="output PNG path")
    args = ap.parse_args()

    mod = import_model(args.model)
    solids = mod.fit_solids()
    if not solids:
        print("error: fit_solids() returned nothing", file=sys.stderr)
        return 1

    y = args.y
    if y is None:                             # default: cut through the middle
        los, his = [], []
        for s in solids.values():
            bb = s.bounding_box()
            los.append(bb.min.Y)
            his.append(bb.max.Y)
        y = (min(los) + max(his)) / 2
        print(f"--y not given; sectioning at bbox center Y = {y:.2f} mm")

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = plt.get_cmap("tab10").colors
    drawn = 0
    for i, (name, solid) in enumerate(solids.items()):
        lines = outline_polylines(solid, y)
        if not lines:
            print(f"note: {name} not cut by plane Y={y:g}")
            continue
        c = colors[i % len(colors)]
        for pts in lines:
            ax.plot(*zip(*pts), color=c, linewidth=1.2)
        ax.plot([], [], color=c, label=name)  # one legend entry per solid
        drawn += 1
    if not drawn:
        print(f"error: plane Y={y:g} misses every solid", file=sys.stderr)
        return 1

    ax.set_aspect("equal")
    ax.grid(True, linewidth=0.3, alpha=0.5)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Z (mm)")
    ax.set_title(f"{os.path.basename(args.model)} — X–Z section at Y = {y:g} mm")
    ax.legend(loc="upper right", fontsize=8)

    dims = getattr(mod, "DIMS", None)
    if isinstance(dims, dict) and dims:       # dimension table in the margin
        fig.subplots_adjust(right=0.74)
        rows = "\n".join(f"{k:<18} {v:>8.2f}" for k, v in dims.items())
        fig.text(0.76, 0.5, f"{'dim':<18} {'mm':>8}\n{rows}",
                 family="monospace", fontsize=8, va="center")

    fig.savefig(args.out, dpi=150)
    print(f"wrote {args.out} ({drawn}/{len(solids)} solids cut)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
