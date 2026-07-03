"""Contract loaders — the bridge from the product's shared data files into layout code.

Three files feed a board generator, and NONE of their numbers may be re-typed
into gen_pcb.py (one number, one place):

  ../cad/constraints.yaml   cad<->pcb fit contract: outline, mount holes, ports,
                            windows, keepouts (vibe-plm names it `enclosure_constraints`)
  pinmap.yaml               pcb->firmware net map: buses + signal<->GPIO pins
  parts.yaml                THIS project's part list: ref -> footprint / value /
                            pad->net map / cluster / DNP. Both gen_sch.py and
                            gen_pcb.py derive their netlists from it, so the
                            schematic and the layout cannot drift apart.

Stdlib-only. PyYAML is used when importable; otherwise a small YAML-subset
parser (nested maps, lists, inline {..}/[..], comments) — same spirit as
vibe-plm's plm_check.py, which must stay import-free of this file (skills never
import each other's code; the parsers are twins by design). Subset means
subset: NO multi-line/folded scalars — keep contract strings on one line.

NOTE: skills/vibe-cad/scripts/cad_contract.py mirrors the constraints loader for
the CAD side. If the constraints schema grows, update both.
"""

from __future__ import annotations

import os
import re


# --------------------------------------------------------------------------- YAML

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

class Constraints:
    """Typed view over cad/constraints.yaml — the cad<->pcb fit contract."""

    def __init__(self, data: dict, path: str = "?"):
        self.data = data
        self.path = path
        b = data.get("board") or {}
        o = b.get("outline") or {}
        self.outline_l = float(o["l"])          # board X extent, mm
        self.outline_w = float(o["w"])          # board Y extent, mm
        self.outline_t = float(o.get("t", 1.6))
        self.corner_r = float(o.get("corner_r", 0))
        mh = b.get("mount_holes") or {}
        self.hole_dia = float(mh.get("dia", 0))
        self.hole_positions = [tuple(map(float, p)) for p in (mh.get("positions") or [])]
        self.stack = data.get("stack") or {}
        self.ports = data.get("ports") or {}
        self.windows = data.get("windows") or {}
        self.keepouts = data.get("keepouts") or {}
        self.offboard = data.get("offboard") or {}
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
                L, W = self.outline_l, self.outline_w
                box = {"+Y": (0, W - d, L, W), "-Y": (0, 0, L, d),
                       "+X": (L - d, 0, L, W), "-X": (0, 0, d, W)}[e]
                out.append((name, box))
            elif all(k in spec for k in ("x", "y", "w", "h")):
                x, y, w, h = (float(spec[k]) for k in ("x", "y", "w", "h"))
                out.append((name, (x - w / 2, y - h / 2, x + w / 2, y + h / 2)))
        return out


def load_constraints(path: str) -> Constraints:
    return Constraints(load_yaml(path), path)


# -------------------------------------------------------------------------- pinmap

class Pinmap:
    """Typed view over pinmap.yaml — the pcb->firmware net map."""

    def __init__(self, data: dict, path: str = "?"):
        self.data = data
        self.path = path
        self.mcu = data.get("mcu", "")
        self.buses = data.get("bus") or {}
        self.pins = data.get("pins") or []

    def bus(self, name: str) -> dict:
        try:
            return self.buses[name]
        except KeyError:
            raise KeyError(f"{self.path}: no bus.{name}") from None

    def gpio(self, signal: str) -> int:
        """'I2S_MCLK' -> 38 (int). Raises if the signal isn't in the pinmap."""
        for p in self.pins:
            if p.get("signal") == signal:
                return int(str(p["gpio"]).replace("GPIO", ""))
        raise KeyError(f"{self.path}: no pin with signal={signal!r}")

    def signals(self) -> list:
        return [p["signal"] for p in self.pins]


def load_pinmap(path: str) -> Pinmap:
    return Pinmap(load_yaml(path), path)


# --------------------------------------------------------------------------- parts

class PartSpec:
    __slots__ = ("ref", "footprint", "value", "pins", "pin_types", "cluster",
                 "dnp", "lcsc", "notes")

    def __init__(self, ref: str, d: dict):
        self.ref = ref
        self.footprint = d["footprint"]          # "Lib:Name" or "./local.pretty:Name"
        self.value = str(d.get("value", ""))
        self.pins = {str(k): ("" if v is None else str(v))
                     for k, v in (d.get("pins") or {}).items()}
        self.pin_types = {str(k): str(v)
                          for k, v in (d.get("pin_types") or {}).items()}
        self.cluster = d.get("cluster", "")
        self.dnp = bool(d.get("dnp", False))
        self.lcsc = d.get("lcsc", "")
        self.notes = d.get("notes", "")


class Parts:
    """Typed view over parts.yaml — ref -> footprint/value/pad->net. The ONE
    net source both gen_sch.py and gen_pcb.py derive from."""

    NC = ("", "NC", "nc", None)

    def __init__(self, data: dict, path: str = "?"):
        self.data = data
        self.path = path
        self.parts = {ref: PartSpec(ref, d) for ref, d in (data.get("parts") or {}).items()}
        self.power_nets = [str(n) for n in (data.get("power_nets") or [])]

    def __getitem__(self, ref: str) -> PartSpec:
        try:
            return self.parts[ref]
        except KeyError:
            raise KeyError(f"{self.path}: no part {ref!r}") from None

    def __iter__(self):
        return iter(self.parts.values())

    def netmap(self, ref: str) -> dict:
        """{pad_name: net_name} for one ref, NC pads dropped."""
        return {pad: net for pad, net in self[ref].pins.items() if net not in self.NC}

    def nets(self) -> set:
        s = set()
        for p in self.parts.values():
            s.update(n for n in p.pins.values() if n not in self.NC)
        return s

    def signal_nets(self) -> list:
        return sorted(self.nets() - set(self.power_nets))


def load_parts(path: str) -> Parts:
    return Parts(load_yaml(path), path)
