#!/usr/bin/env python3
"""power_check.py — is this power net wide enough, and how much does it drop?

Two questions DRC never asks, both of which decide whether a board works:

  1. THERMAL — will the narrowest segment carrying the full current overheat?
  2. IR DROP — how much of the rail is lost in the copper between the source
     and each load?

Neither is a width you can eyeball, and the trap is that a power net is rarely
one width: a run that is 0.5 mm across the board can neck to 0.25 mm escaping a
connector, and it is the neck that decides the answer.

Usage:
    power_check.py <board.kicad_pcb> --net VBUS --from J1 --amps 0.5 \\
                   [--rise 10] [--oz 1] [--loads U3,C3]

  --from   REF or REF.PAD of the source (where current enters the net)
  --loads  refs to report drop to (default: every other ref on the net)
  --rise   allowed temperature rise, °C (default 10)
  --oz     outer-layer copper weight (default 1 oz = 34.8 um)

Run with KiCad's BUNDLED python (the one with pcbnew).

ON THE STANDARD: the width check uses the IPC-2221 closed form,

    I = k · dT^0.44 · A^0.725      (k = 0.048 external, 0.024 internal)

because IPC-2152 is a set of CHARTS, not an equation — there is no honest way
to evaluate it in a script. For external traces IPC-2152 is generally more
permissive than IPC-2221 (2221 came from 1950s data and is conservative in
still air), so a trace that passes here passes IPC-2152 with margin. If a
result lands close to the limit, read the real IPC-2152 charts rather than
trusting either number.

Resistance uses rho_Cu = 1.72e-8 ohm*m at 20 C; copper is +0.39 %/K, so a warm
board reads slightly higher than this prints.
"""
import heapq
import math
import sys

import pcbnew

RHO_CU = 1.72e-8          # ohm*m at 20 C
OZ_UM = 34.8              # 1 oz copper thickness, um


def _args(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    o = {"board": argv[1], "net": None, "src": None, "amps": None,
         "rise": 10.0, "oz": 1.0, "loads": None}
    i = 2
    while i < len(argv):
        a = argv[i]
        key = {"--net": "net", "--from": "src", "--amps": "amps",
               "--rise": "rise", "--oz": "oz", "--loads": "loads"}.get(a)
        if not key:
            sys.exit(f"unknown argument {a!r}\n\n{__doc__}")
        i += 1
        v = argv[i]
        o[key] = float(v) if key in ("amps", "rise", "oz") else v
        i += 1
    for req in ("net", "src", "amps"):
        if o[req] is None:
            sys.exit(f"--{'from' if req == 'src' else req} is required\n\n{__doc__}")
    return o


def ipc2221_width_mm(amps, rise_c, thick_um, internal=False):
    """Width needed for `amps` at `rise_c` on a trace of that copper thickness."""
    k = 0.024 if internal else 0.048
    area_mils2 = (amps / (k * rise_c ** 0.44)) ** (1 / 0.725)
    thick_mils = thick_um / 25.4
    return area_mils2 / thick_mils * 0.0254        # mils -> mm


def ipc2221_amps(width_mm, rise_c, thick_um, internal=False):
    """The inverse: what that width is rated for."""
    k = 0.024 if internal else 0.048
    area_mils2 = (width_mm / 0.0254) * (thick_um / 25.4)
    return k * rise_c ** 0.44 * area_mils2 ** 0.725


def main(argv):
    o = _args(argv)
    board = pcbnew.LoadBoard(o["board"])
    thick_um = OZ_UM * o["oz"]
    r_sq = RHO_CU / (thick_um * 1e-6)             # ohm per square

    # --- graph: nodes are track endpoints and via positions, snapped to 1 um
    def key(pt):
        return (round(pt.x / 1000), round(pt.y / 1000))

    raw = []                                      # (ax, ay, bx, by, width_mm)
    nodes = set()
    for t in board.GetTracks():
        if t.GetNetname() != o["net"]:
            continue
        if t.GetClass() == "PCB_VIA":
            nodes.add(key(t.GetPosition()))       # a via is a node, not a length
            continue
        a, b = key(t.GetStart()), key(t.GetEnd())
        if a == b:
            continue
        raw.append((a, b, t.GetWidth() / 1e6))
        nodes.update((a, b))
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            if pd.GetNetname() == o["net"]:
                nodes.add(key(pd.GetPosition()))
    if not raw:
        sys.exit(f"no {o['net']} track segments in {o['board']}")

    # A trace that Ts onto the MIDDLE of another shares no endpoint with it, so
    # a naive endpoint graph reports half the net as unreachable. Split every
    # segment at any node that lies on it.
    def on_segment(a, b, p, tol=2.0):             # tol in um-keys (~2 um)
        (ax, ay), (bx, by), (px, py) = a, b, p
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return None
        t = ((px - ax) * dx + (py - ay) * dy) / L2
        if not (0 < t < 1):
            return None
        cx, cy = ax + t * dx, ay + t * dy
        return t if (cx - px) ** 2 + (cy - py) ** 2 <= tol * tol else None

    adj = {}
    segs = []
    for a, b, w_mm in raw:
        cuts = [(0.0, a), (1.0, b)]
        for n in nodes:
            if n in (a, b):
                continue
            t = on_segment(a, b, n)
            if t is not None:
                cuts.append((t, n))
        cuts.sort()
        full = math.dist(a, b) / 1000.0           # um-keys -> mm
        for (t0, n0), (t1, n1) in zip(cuts, cuts[1:]):
            L_mm = full * (t1 - t0)
            if L_mm <= 0:
                continue
            r = r_sq * (L_mm / w_mm)              # squares * ohm/square
            segs.append((w_mm, L_mm))
            adj.setdefault(n0, []).append((n1, r))
            adj.setdefault(n1, []).append((n0, r))

    # pads join whatever touches them (a pad is a low-resistance node)
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != o["net"]:
                continue
            k = key(p.GetPosition())
            pads.setdefault(fp.GetReference(), []).append(k)
            adj.setdefault(k, [])
            for other in pads[fp.GetReference()]:  # pads of one part are the part
                if other != k:
                    adj[k].append((other, 0.0))
                    adj[other].append((k, 0.0))

    src_ref = o["src"].split(".")[0]
    if src_ref not in pads:
        sys.exit(f"{src_ref} has no {o['net']} pad")

    # --- thermal: the narrowest segment has to carry the whole current
    widths = sorted({w for w, _ in segs})
    narrow = widths[0]
    need = ipc2221_width_mm(o["amps"], o["rise"], thick_um)
    rated = ipc2221_amps(narrow, o["rise"], thick_um)
    len_at_narrow = sum(L for w, L in segs if abs(w - narrow) < 1e-9)

    print(f"net {o['net']}  ·  {o['amps']:.3f} A  ·  {o['oz']:.0f} oz "
          f"({thick_um:.1f} um)  ·  {o['rise']:.0f} C rise  ·  external layer")
    print(f"  widths present : {', '.join(f'{w:.2f}' for w in widths)} mm")
    print(f"  narrowest      : {narrow:.2f} mm over {len_at_narrow:.1f} mm of run")
    print(f"  IPC-2221 needs : {need:.3f} mm   -> narrowest is rated {rated:.3f} A "
          f"({rated / o['amps']:.1f}x the load)")
    verdict = "PASS" if narrow >= need else "FAIL"
    print(f"  thermal        : {verdict}")

    # --- IR drop: shortest-resistance path from the source to each load
    start = pads[src_ref][0]
    dist = {start: 0.0}
    pq = [(0.0, start)]
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist.get(n, math.inf):
            continue
        for m, r in adj.get(n, []):
            nd = d + r
            if nd < dist.get(m, math.inf):
                dist[m] = nd
                heapq.heappush(pq, (nd, m))

    loads = o["loads"].split(",") if o["loads"] else [r for r in pads if r != src_ref]
    print(f"  IR drop from {src_ref} at {o['amps']:.3f} A "
          f"(worst case: the full current down each path):")
    unreached = []
    for ref in sorted(loads):
        ks = [k for k in pads.get(ref, []) if k in dist]
        if not ks:
            unreached.append(ref)
            continue
        r = min(dist[k] for k in ks)
        print(f"    -> {ref:5} {r * 1000:6.1f} mOhm   {r * o['amps'] * 1000:6.1f} mV")
    if unreached:
        print(f"    (not reached through copper -- pour or a via chain: "
              f"{', '.join(unreached)})")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
