"""cad_contract — load cad/constraints.yaml (the cad<->pcb fit contract) as typed params.

The shell model imports its fit numbers from here instead of re-typing them —
hand-typing a contract number into the model is a bug (one number, one place):

    from cad_contract import load
    C = load("../cad/constraints.yaml")
    C.outline.l, C.outline.w          # board extents
    C.window("display")               # {'x':.., 'y':.., 'w':.., 'h':..} or {'x','y','dia'}
    C.port("usb_c")                   # edge/center/throat/mouth dict
    C.offboard["speaker"]             # off-board parts the shell must seat

Stdlib-only. PyYAML is used when importable; otherwise a small YAML-subset
parser (nested maps, lists, inline {..}/[..], comments).

NOTE: this file is a deliberate stdlib TWIN of
skills/vibe-pcb/scripts/pcblib/contract.py (its YAML parser + Constraints view)
— skills never import each other's code, so the loaders are duplicated by
design. If the constraints schema grows, update both.
"""

from __future__ import annotations

import re


# --------------------------------------------------------------------------- YAML
# (verbatim twin of pcblib/contract.py — keep in sync)

def _scalar(v: str):
    v = v.strip()
    if not v or v == "~" or v == "null":
        return None
    if (v[0] == v[-1]) and v[0] in "\"'" and len(v) >= 2:
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return int(v, 0)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _split_inline(s: str) -> list:
    """Split 'a: 1, b: [2, 3]' on top-level commas."""
    parts, depth, quote, cur = [], 0, None, []
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch in "[{":
            depth += 1
            cur.append(ch)
        elif ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _inline_value(v: str):
    v = v.strip()
    if v.startswith("{") and v.endswith("}"):
        d = {}
        for item in _split_inline(v[1:-1]):
            if ":" in item:
                k, _, rest = item.partition(":")
                d[str(_scalar(k))] = _inline_value(rest)
        return d
    if v.startswith("[") and v.endswith("]"):
        return [_inline_value(x) for x in _split_inline(v[1:-1])]
    return _scalar(v)


def _parse_block(lines: list, i: int, indent: int):
    """Parse an indentation block starting at line i. Returns (value, next_i)."""
    # decide list vs map from the first significant line
    first = lines[i][1]
    if first.lstrip().startswith("- "):
        out = []
        while i < len(lines):
            ind, text = lines[i]
            if ind < indent:
                break
            if not text.lstrip().startswith("- "):
                break
            item = text.lstrip()[2:]
            if not item:
                # nested block item
                val, i = _parse_block(lines, i + 1, ind + 1)
                out.append(val)
            else:
                out.append(_inline_value(item))
                i += 1
        return out, i
    out = {}
    while i < len(lines):
        ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ValueError(f"bad indent: {text!r}")
        m = re.match(r"([^:]+):\s*(.*)$", text.strip())
        if not m:
            raise ValueError(f"expected 'key: value': {text!r}")
        key, rest = str(_scalar(m.group(1))), m.group(2)
        if rest:
            out[key] = _inline_value(rest)
            i += 1
        else:
            # value is the following deeper block (or empty)
            if i + 1 < len(lines) and lines[i + 1][0] > ind:
                out[key], i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                out[key] = None
                i += 1
    return out, i


def load_yaml(path: str) -> dict:
    """Load a YAML file: PyYAML when available, else the subset parser."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        lines.append((len(line) - len(line.lstrip()), line))
    if not lines:
        return {}
    val, _ = _parse_block(lines, 0, lines[0][0])
    return val


# --------------------------------------------------------------------- constraints

class Outline:
    """board.outline — the board's L x W x thickness envelope (mm)."""

    def __init__(self, o: dict):
        self.l = float(o["l"])                 # board X extent
        self.w = float(o["w"])                 # board Y extent
        self.t = float(o.get("t", 1.6))        # board thickness
        self.corner_r = float(o.get("corner_r", 0))


class MountHoles:
    """board.mount_holes — dia + [(x, y), ...] in the board frame (mm)."""

    def __init__(self, mh: dict):
        self.dia = float(mh.get("dia", 0))
        self.positions = [tuple(map(float, p)) for p in (mh.get("positions") or [])]


class Contract:
    """Typed view over cad/constraints.yaml — the cad<->pcb fit contract.

    Twin of pcblib.contract.Constraints (flat attrs there, nested views here);
    same schema, keep both in sync."""

    def __init__(self, data: dict, path: str = "?"):
        self.data = data
        self.path = path
        b = data.get("board") or {}
        self.outline = Outline(b.get("outline") or {})
        self.mount_holes = MountHoles(b.get("mount_holes") or {})
        self.stack = data.get("stack") or {}          # standoff_h, total_h, ...
        self.ports = data.get("ports") or {}
        self.windows = data.get("windows") or {}
        self.keepouts = data.get("keepouts") or {}
        self.offboard = data.get("offboard") or {}    # speaker, battery, ... the shell seats
        self.tolerance_mm = float(data.get("tolerance_mm", 0.5))

    def port(self, name: str) -> dict:
        try:
            return self.ports[name]
        except KeyError:
            raise KeyError(f"{self.path}: no ports.{name} in the contract") from None

    def window(self, name: str) -> dict:
        try:
            return self.windows[name]
        except KeyError:
            raise KeyError(f"{self.path}: no windows.{name} in the contract") from None

    def keepout_boxes(self):
        """Structured keepouts -> [(name, (x0,y0,x1,y1))] in board frame (mm).

        Supported forms under `keepouts:`:
          name: {edge: "+Y", depth: 8}            strip along a board edge
          name: {x: .., y: .., w: .., h: ..}      explicit box (x,y = center)
        Free-text keepouts (a bare string) are prose for humans — skipped here.
        """
        out = []
        for name, spec in self.keepouts.items():
            if not isinstance(spec, dict):
                continue
            if "edge" in spec:
                d = float(spec.get("depth", 0))
                e = spec["edge"]
                L, W = self.outline.l, self.outline.w
                box = {"+Y": (0, W - d, L, W), "-Y": (0, 0, L, d),
                       "+X": (L - d, 0, L, W), "-X": (0, 0, d, W)}[e]
                out.append((name, box))
            elif all(k in spec for k in ("x", "y", "w", "h")):
                x, y, w, h = (float(spec[k]) for k in ("x", "y", "w", "h"))
                out.append((name, (x - w / 2, y - h / 2, x + w / 2, y + h / 2)))
        return out


def load(path: str) -> Contract:
    return Contract(load_yaml(path), path)


if __name__ == "__main__":
    import sys
    C = load(sys.argv[1] if len(sys.argv) > 1 else "cad/constraints.yaml")
    print(f"{C.path}: board {C.outline.l} x {C.outline.w} x {C.outline.t} "
          f"(r{C.outline.corner_r}), {len(C.mount_holes.positions)} holes "
          f"d{C.mount_holes.dia}, ports={list(C.ports)}, windows={list(C.windows)}, "
          f"offboard={list(C.offboard)}, tol={C.tolerance_mm}")
