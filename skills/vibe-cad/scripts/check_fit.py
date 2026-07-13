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

Compound trap (bit the voice-buddy build): a raw import_step() Compound can
intersect (`&`) to silently-empty even when it DOES overlap — a vacuous pass.
Both sides are therefore exploded to their solids and intersected pairwise;
an input that contains no solids at all is reported loudly.
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


def explode(x, key: str) -> list:
    """A shape's constituent solids (a Compound-safe view; see header)."""
    if hasattr(x, "solids"):
        s = list(x.solids())
        if s:
            return s
        print(f"warning: fit_solids()[{key!r}] contains NO solids — "
              "it cannot clash with anything (vacuous pass?)", file=sys.stderr)
        return []
    return [x]


def intersection_mm3(a_solids, b_solids) -> float:
    """Summed volume of pairwise solid intersections (empty results -> 0.0)."""
    total = 0.0
    for sa in a_solids:
        for sb in b_solids:
            try:
                inter = sa & sb
            except Exception:
                continue                        # disjoint shapes can raise; that's a pass
            if inter is None:
                continue
            solids = list(inter.solids()) if hasattr(inter, "solids") else []
            total += sum(s.volume for s in solids)
    return float(total)


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

    exploded = {k: explode(v, k) for k, v in solids.items()}
    wid = max(len(f"{a} & {b}") for a, b in pairs)
    worst, failed = 0.0, False
    print(f"{'pair'.ljust(wid)}  intersection (mm^3)")
    for a, b in pairs:
        v = intersection_mm3(exploded[a], exploded[b])
        worst = max(worst, v)
        clash = v > args.tol_mm3
        failed |= clash
        print(f"{f'{a} & {b}'.ljust(wid)}  {v:12.6f}  {'CLASH' if clash else 'ok'}")
    print(f"\n{'FAIL' if failed else 'PASS'}: worst pair {worst:.6f} mm^3 "
          f"(tolerance {args.tol_mm3} mm^3)")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
