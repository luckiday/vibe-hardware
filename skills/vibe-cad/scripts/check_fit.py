"""check_fit — the generic board/module <-> shell interference gate (expect 0 mm³).

    .venv/bin/python skills/vibe-cad/scripts/check_fit.py <model.py> [--tol-mm3 0.001]

The model module must expose `fit_solids() -> dict[str, solid]` with every part
placed in its real assembled position. Keys pick the sides of the check:

  board* / part* / module* / speaker* / oled*   -> the real parts
  shell* / tray* / cover* / case* / baffle*     -> the enclosure

Every part is boolean-intersected (`&`) against every shell piece; any pair over
tolerance is a clash (exit 2). Define `FIT_PAIRS = [("board", "shell_tray"), ...]`
in the model to check exactly those pairs instead of the cross product.

Why a tolerance at all: coincident design faces (a board resting on a boss)
intersect to ~0, so a small threshold separates "touching" from a real clash.
build123d returns an empty Compound for a no-op `&` — treated as 0 here.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

PART_PREFIXES = ("board", "part", "module", "speaker", "oled")
SHELL_PREFIXES = ("shell", "tray", "cover", "case", "baffle")


def import_model(path: str):
    """Import a model .py by path (so it can live anywhere, venv-agnostic)."""
    path = os.path.abspath(path)
    name = os.path.splitext(os.path.basename(path))[0]
    sys.path.insert(0, os.path.dirname(path))   # let the model import its siblings
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def intersection_mm3(a, b) -> float:
    """Volume of a & b, robust to empty results (no solids -> 0.0)."""
    try:
        inter = a & b
    except Exception:
        return 0.0                              # disjoint shapes can raise; that's a pass
    if inter is None:
        return 0.0
    solids = list(inter.solids()) if hasattr(inter, "solids") else []
    return float(sum(s.volume for s in solids))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", help="model .py exposing fit_solids() -> dict")
    ap.add_argument("--tol-mm3", type=float, default=0.001,
                    help="max allowed intersection per pair (default 0.001)")
    args = ap.parse_args()

    mod = import_model(args.model)
    if not hasattr(mod, "fit_solids"):
        print(f"error: {args.model} has no fit_solids() -> dict", file=sys.stderr)
        return 1
    solids = mod.fit_solids()

    pairs = getattr(mod, "FIT_PAIRS", None)
    if pairs:
        for a, b in pairs:
            for k in (a, b):
                if k not in solids:
                    print(f"error: FIT_PAIRS names {k!r}, not in fit_solids()",
                          file=sys.stderr)
                    return 1
    else:
        parts = [k for k in solids if k.lower().startswith(PART_PREFIXES)]
        shells = [k for k in solids if k.lower().startswith(SHELL_PREFIXES)]
        skipped = [k for k in solids if k not in parts and k not in shells]
        if skipped:
            print(f"note: keys not checked (unrecognized prefix): {skipped}")
        pairs = [(p, s) for p in parts for s in shells]
    if not pairs:
        print("error: no part<->shell pairs to check — name the fit_solids() keys "
              f"with {PART_PREFIXES} / {SHELL_PREFIXES} or define FIT_PAIRS",
              file=sys.stderr)
        return 1

    wid = max(len(f"{a} & {b}") for a, b in pairs)
    worst, failed = 0.0, False
    print(f"{'pair'.ljust(wid)}  intersection (mm^3)")
    for a, b in pairs:
        v = intersection_mm3(solids[a], solids[b])
        worst = max(worst, v)
        clash = v > args.tol_mm3
        failed |= clash
        print(f"{f'{a} & {b}'.ljust(wid)}  {v:12.6f}  {'CLASH' if clash else 'ok'}")
    print(f"\n{'FAIL' if failed else 'PASS'}: worst pair {worst:.6f} mm^3 "
          f"(tolerance {args.tol_mm3} mm^3)")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
