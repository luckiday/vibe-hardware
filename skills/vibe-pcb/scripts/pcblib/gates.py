"""Numeric placement gates — cheap, code-computed checks that catch a bad
floorplan BEFORE any render or DRC run. The model still reviews the staged
renders, but the honest scorecard comes from geometry, not eyeballing:

  courtyard_overlaps   two parts on the same face may never overlap (hard fail)
  cluster_overlaps     functional groups may not collide (hard fail)
  keepout_violations   parts/copper inside a contract keepout (hard fail)
  hpwl                 half-perimeter wirelength per net — a routability PROXY,
                       tracked and budgeted (warn), never a hard gate
  scorecard            prints the table, returns the hard-fail count
  export_placement     writes placement.json — the pcb->cad/plm EVIDENCE of
                       where user-visible items actually landed

Needs pcbnew. All coordinates reported in board frame (mm, +y up).
"""

from __future__ import annotations

import json

import pcbnew
from pcbnew import ToMM

__all__ = [
    "courtyard_overlaps", "cluster_overlaps", "keepout_violations", "hpwl",
    "scorecard", "export_placement", "draw_cluster_boxes",
]


def _isect(a, b) -> float:
    """Overlap area of two (x0,y0,x1,y1) boxes, mm^2 (0 when disjoint)."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if (w > 0 and h > 0) else 0.0


def courtyard_overlaps(board, tol: float = 1e-3) -> list:
    """[(refA, refB, mm^2)] for same-face courtyard collisions."""
    parts = list(board.parts.values())
    bad = []
    for i, a in enumerate(parts):
        ca, sa = a.courtyard(), a.side()
        for b in parts[i + 1:]:
            if b.side() != sa:
                continue
            v = _isect(ca, b.courtyard())
            if v > tol:
                bad.append((a.ref, b.ref, round(v, 2)))
    return bad


def cluster_overlaps(clusters=None, tol: float = 1e-3) -> list:
    """[(nameA, nameB, mm^2)] for colliding cluster bboxes."""
    from .layout import Cluster
    cl = list((clusters or Cluster.all).values())
    bad = []
    for i, a in enumerate(cl):
        ba = a.bbox()
        for b in cl[i + 1:]:
            v = _isect(ba, b.bbox())
            if v > tol:
                bad.append((a.name, b.name, round(v, 2)))
    return bad


def keepout_violations(board, boxes=None, allow=()) -> list:
    """Anything inside a keepout box: part courtyards, track points, via
    barrels. `boxes` defaults to the contract's structured keepouts; pass
    extra [(name, (x0,y0,x1,y1))] to add module belly boxes etc. `allow` lists
    refs that legitimately live in a keepout (e.g. the RF module whose antenna
    section IS the antenna keepout) — copper is still checked."""
    boxes = list(boxes if boxes is not None else board.c.keepout_boxes())
    bad = []

    def inbox(box, x, y):
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    for name, box in boxes:
        for part in board.parts.values():
            if part.ref.startswith("H") or part.ref in allow:
                continue                        # mount holes are contract-placed
            if _isect(box, part.courtyard()) > 1e-3:
                bad.append((name, f"part {part.ref}"))
        for t in board.pcb.GetTracks():
            if t.GetClass() == "PCB_VIA":
                x, y = board.from_kicad(t.GetPosition())
                if inbox(box, x, y):
                    bad.append((name, f"via {t.GetNetname()} @({x:.1f},{y:.1f})"))
            else:
                sx, sy = board.from_kicad(t.GetStart())
                ex, ey = board.from_kicad(t.GetEnd())
                if (inbox(box, sx, sy) or inbox(box, ex, ey)
                        or inbox(box, (sx + ex) / 2, (sy + ey) / 2)):
                    bad.append((name, f"track {t.GetNetname()} "
                                      f"({sx:.1f},{sy:.1f})->({ex:.1f},{ey:.1f})"))
    return bad


def hpwl(board) -> dict:
    """{net: half-perimeter wirelength mm} over pad positions (+ 'TOTAL').
    A routability proxy: compare between floorplan candidates, budget it,
    never hard-gate on it."""
    boxes = {}
    for fp in board.pcb.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if not n:
                continue
            x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
            b = boxes.get(n)
            boxes[n] = (min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)) \
                if b else (x, y, x, y)
    out = {n: round((b[2] - b[0]) + (b[3] - b[1]), 1) for n, b in boxes.items()}
    out["TOTAL"] = round(sum(out.values()), 1)
    return out


def scorecard(board, budgets=None, extra_keepouts=None, keepout_allow=(),
              top: int = 8) -> int:
    """Print the honest gate table; return the number of HARD fails.
    budgets: {"hpwl_mm": float} -> over-budget prints a warning (not a fail)."""
    budgets = budgets or {}
    co = courtyard_overlaps(board)
    cl = cluster_overlaps()
    ko = keepout_violations(board, boxes=None if extra_keepouts is None
                            else list(board.c.keepout_boxes()) + list(extra_keepouts),
                            allow=keepout_allow)
    wl = hpwl(board)
    fails = 0

    def line(label, bad, detail):
        nonlocal fails
        mark = "PASS" if not bad else "FAIL"
        if bad:
            fails += 1
        print(f"  {mark}  {label:24}: {detail}")

    print("==== placement scorecard (board frame mm) ====")
    line("courtyard overlaps", co,
         "0" if not co else f"{len(co)} -> " + "; ".join(
             f"{a}+{b} {v}mm^2" for a, b, v in co[:top]))
    line("cluster overlaps", cl,
         "0" if not cl else f"{len(cl)} -> " + "; ".join(
             f"{a}+{b} {v}mm^2" for a, b, v in cl[:top]))
    line("keepout violations", ko,
         "0" if not ko else f"{len(ko)} -> " + "; ".join(
             f"[{n}] {w}" for n, w in ko[:top]))
    total = wl.get("TOTAL", 0.0)
    budget = budgets.get("hpwl_mm")
    worst = sorted(((v, k) for k, v in wl.items() if k != "TOTAL"), reverse=True)[:5]
    note = f" (budget {budget}mm{' EXCEEDED' if budget and total > budget else ''})" \
        if budget else ""
    print(f"  INFO  HPWL total            : {total} mm{note}; worst: "
          + ", ".join(f"{k}={v}" for v, k in worst))
    print(f"==== hard fails: {fails} ====")
    return fails


def export_placement(board, path: str, kinds: dict, extras=None,
                     product: str = "", revision: str = ""):
    """Write placement.json — the evidence contract. kinds: {ref: kind} for the
    user-visible items (usb_c, button, led, mic_port, speaker_conn, ...); size
    is the courtyard extent. extras: pre-computed items (e.g. a display window
    derived from header position + module geometry) appended verbatim."""
    items = []
    for ref, kind in kinds.items():
        part = board.parts[ref]
        x, y = part.pos
        c = part.courtyard()
        item = {"ref": ref, "kind": kind,
                "center": [round(x, 2), round(y, 2)],
                "w": round(c[2] - c[0], 2), "h": round(c[3] - c[1], 2)}
        items.append(item)
    items += list(extras or [])
    doc = {
        "product": product, "revision": revision,
        "frame": "board mm, origin bottom-left viewed from front, +y up",
        "outline": {"l": board.L, "w": board.W, "t": board.c.outline_t,
                    "corner_r": board.c.corner_r},
        "mount_holes": {"dia": board.c.hole_dia,
                        "positions": [list(p) for p in board.c.hole_positions]},
        "items": items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print(f"wrote {path} ({len(items)} items)")


def draw_cluster_boxes(board, clusters=None):
    """Label each cluster's REAL bbox on Dwgs.User — read at STAGE=floorplan."""
    from .layout import Cluster
    from pcbnew import FromMM as MM
    for name, cl in (clusters or Cluster.all).items():
        x0, y0, x1, y1 = cl.bbox()
        s = pcbnew.PCB_SHAPE(board.pcb)
        s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetStart(board.xy(x0, y1))     # top-left in KiCad frame
        s.SetEnd(board.xy(x1, y0))
        s.SetLayer(pcbnew.Dwgs_User)
        s.SetWidth(MM(0.15))
        board.pcb.Add(s)
        t = pcbnew.PCB_TEXT(board.pcb)
        t.SetText(name)
        t.SetPosition(board.xy((x0 + x1) / 2, y1 + 1.2))
        t.SetLayer(pcbnew.Dwgs_User)
        t.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2)))
        board.pcb.Add(t)
