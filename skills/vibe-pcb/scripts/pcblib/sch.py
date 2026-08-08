"""Schematic writer — a .kicad_sch generated from parts.yaml (stdlib only).

Chips like ES8311/ES7210/NS4150 ship no KiCad library symbol, and drawing one
by hand in eeschema breaks generate-by-script. So every part gets a GENERATED
box symbol: rectangle + typed pins, pin names = the NET each pad carries
(straight from parts.yaml, the same source gen_pcb.py assigns copper nets
from — the schematic and the board cannot disagree).

Wiring scheme: every pin gets a short wire stub + a global net label; NC pads
get a no-connect cross; every power net gets one PWR_FLAG (a generated
power_out pin) so ERC's power-driven check stays meaningful. Optional
`pin_types: {pad: erc_type}` in a parts.yaml entry refines ERC further
(default: passive; power rails auto-type power_in on IC pads).

Usage (from a project's gen_sch.py):
    sheet = Sheet("myboard", title="myboard carrier")
    for spec in parts: sheet.symbol(spec, netmap)
    sheet.write("myboard.kicad_sch")
"""

from __future__ import annotations

import uuid

# ERC electrical types KiCad accepts in `pin <type> line`
PIN_TYPES = {"passive", "input", "output", "bidirectional", "power_in",
             "power_out", "no_connect", "free", "unspecified", "open_collector",
             "open_emitter", "tri_state"}

GRID = 2.54          # sch grid, mm
STUB = 3.81          # wire stub length off each pin


def _u() -> str:
    return str(uuid.uuid4())


def _esc(s: str) -> str:
    return '"' + str(s).replace('"', '\\"') + '"'


class _Sym:
    """One generated box symbol + its placed instance."""

    def __init__(self, ref: str, value: str, footprint: str, pins: dict,
                 pin_types: dict, power_nets: set, dnp: bool):
        self.ref, self.value, self.footprint, self.dnp = ref, value, footprint, dnp
        self.lib_id = f"vb:{ref}"
        # pins: {pad: net} INCLUDING NC pads (net None) so nothing dangles
        items = sorted(pins.items(), key=_pad_key)
        half = (len(items) + 1) // 2
        self.left = items[:half]
        self.right = items[half:]
        self.types = {}
        for pad, net in items:
            t = pin_types.get(pad)
            if t is None:
                t = "power_in" if (net in power_nets and ref.startswith("U")) \
                    else "passive"
            if t not in PIN_TYPES:
                raise ValueError(f"{ref} pad {pad}: bad pin type {t!r}")
            self.types[pad] = t
        rows = max(len(self.left), len(self.right), 2)
        self.w = 30.48                              # box width, mm
        self.h = (rows + 2) * GRID                  # box height
        self.at = (0.0, 0.0)                        # sheet position, set by Sheet

    def pin_rows(self):
        """[(pad, net, side, index)] with geometric rows."""
        out = []
        for i, (pad, net) in enumerate(self.left):
            out.append((pad, net, "L", i))
        for i, (pad, net) in enumerate(self.right):
            out.append((pad, net, "R", i))
        return out

    def pin_xy(self, side: str, i: int, at=None):
        """Sheet position of a pin's connection point."""
        x0, y0 = at or self.at
        y = y0 - self.h / 2 + GRID * (i + 1)
        x = x0 - self.w / 2 - STUB if side == "L" else x0 + self.w / 2 + STUB
        return (x, y)

    def lib_symbol(self) -> str:
        s = [f'    (symbol {_esc(self.lib_id)} (pin_names (offset 1.016)) '
             f'(in_bom yes) (on_board yes)']
        s.append(f'      (property "Reference" {_esc(_ref_prefix(self.ref))} '
                 f'(at 0 {self.h / 2 + 1.27:.2f} 0) '
                 f'(effects (font (size 1.27 1.27))))')
        s.append(f'      (property "Value" {_esc(self.value)} '
                 f'(at 0 {-(self.h / 2 + 1.27):.2f} 0) '
                 f'(effects (font (size 1.27 1.27))))')
        s.append(f'      (property "Footprint" {_esc(self.footprint)} (at 0 0 0) '
                 f'(effects (font (size 1.27 1.27)) hide))')
        body = self.lib_id.split(":")[1]
        s.append(f'      (symbol "{body}_0_1"')
        s.append(f'        (rectangle (start {-self.w / 2:.2f} {self.h / 2:.2f}) '
                 f'(end {self.w / 2:.2f} {-self.h / 2:.2f}) '
                 f'(stroke (width 0.254) (type default)) (fill (type background))))')
        s.append(f'      (symbol "{body}_1_1"')
        for pad, net, side, i in self.pin_rows():
            # pin origin is the CONNECTION point, pointing INTO the box
            px = -self.w / 2 - STUB if side == "L" else self.w / 2 + STUB
            py = self.h / 2 - GRID * (i + 1)
            rot = 0 if side == "L" else 180
            name = net if net else "NC"
            t = self.types[pad]
            s.append(f'        (pin {t} line (at {px:.2f} {py:.2f} {rot}) '
                     f'(length {STUB:.2f})')
            s.append(f'          (name {_esc(name)} (effects (font (size 1.0 1.0))))')
            s.append(f'          (number {_esc(pad)} (effects (font (size 1.0 1.0)))))')
        s.append('      ))')
        return "\n".join(s)

    def instance(self, project: str, root_uuid: str) -> str:
        x, y = self.at
        s = [f'  (symbol (lib_id {_esc(self.lib_id)}) (at {x:.2f} {y:.2f} 0) '
             f'(unit 1) (in_bom yes) (on_board yes) '
             f'(dnp {"yes" if self.dnp else "no"})']
        s.append(f'    (uuid {_u()})')
        s.append(f'    (property "Reference" {_esc(self.ref)} '
                 f'(at {x:.2f} {y - self.h / 2 - 2.54:.2f} 0) '
                 f'(effects (font (size 1.27 1.27))))')
        s.append(f'    (property "Value" {_esc(self.value)} '
                 f'(at {x:.2f} {y + self.h / 2 + 2.54:.2f} 0) '
                 f'(effects (font (size 1.27 1.27))))')
        s.append(f'    (property "Footprint" {_esc(self.footprint)} (at {x:.2f} '
                 f'{y:.2f} 0) (effects (font (size 1.27 1.27)) hide))')
        for pad, _, _, _ in self.pin_rows():
            s.append(f'    (pin {_esc(pad)} (uuid {_u()}))')
        s.append(f'    (instances (project {_esc(project)} '
                 f'(path "/{root_uuid}" (reference {_esc(self.ref)}) (unit 1)))))')
        return "\n".join(s)


def _pad_key(item):
    pad = item[0]
    return (0, int(pad)) if pad.isdigit() else (1, pad)


def _ref_prefix(ref: str) -> str:
    return ref.rstrip("0123456789") or ref


class Sheet:
    """Collects generated symbols on a grid, then writes the .kicad_sch."""

    def __init__(self, project: str, title: str = "", paper: str = "A3",
                 cols: int = 4, cell=(65.0, 0.0), origin=(40.0, 40.0)):
        self.project = project
        self.title = title or project
        self.paper = paper
        self.cols = cols
        self.cell_w, _ = cell
        self.ox, self.oy = origin
        self.root_uuid = _u()
        self.syms: list = []
        self.power_nets: set = set()

    def symbol(self, spec, power_nets=()) -> _Sym:
        """Add one part. spec is a contract.PartSpec (or any object with
        ref/value/footprint/pins/dnp and optional pin_types)."""
        self.power_nets.update(power_nets)
        pins = {str(k): (v if v not in ("", "NC", "nc", None) else None)
                for k, v in spec.pins.items()}
        sym = _Sym(spec.ref, spec.value, spec.footprint, pins,
                   getattr(spec, "pin_types", None) or {},
                   set(power_nets), spec.dnp)
        self.syms.append(sym)
        return sym

    def _layout(self):
        """Grid placement: column x fixed, y flows down per column height."""
        col_y = [self.oy] * self.cols
        for i, sym in enumerate(self.syms):
            col = i % self.cols
            x = self.ox + col * self.cell_w
            y = col_y[col] + sym.h / 2
            sym.at = (x, y)
            col_y[col] = y + sym.h / 2 + 15.0

    def write(self, path: str):
        self._layout()
        out = [f'(kicad_sch (version 20230121) (generator "pcblib")',
               f'  (uuid {self.root_uuid})',
               f'  (paper {_esc(self.paper)})',
               f'  (title_block (title {_esc(self.title)}))']
        # ---- embedded library symbols (incl. one PWR_FLAG) ----
        out.append('  (lib_symbols')
        for sym in self.syms:
            out.append(sym.lib_symbol())
        out.append(_PWR_FLAG_LIB)
        out.append('  )')
        # ---- instances + per-pin stubs/labels/no-connects ----
        for sym in self.syms:
            out.append(sym.instance(self.project, self.root_uuid))
            for pad, net, side, i in sym.pin_rows():
                px, py = sym.pin_xy(side, i)
                if net is None:
                    out.append(f'  (no_connect (at {px:.2f} {py:.2f}) (uuid {_u()}))')
                    continue
                qx = px - STUB if side == "L" else px + STUB
                out.append(f'  (wire (pts (xy {px:.2f} {py:.2f}) '
                           f'(xy {qx:.2f} {py:.2f})) '
                           f'(stroke (width 0)) (uuid {_u()}))')
                rot = 180 if side == "L" else 0
                out.append(f'  (global_label {_esc(net)} (shape passive) '
                           f'(at {qx:.2f} {py:.2f} {rot}) '
                           f'(effects (font (size 1.27 1.27)) '
                           f'(justify {"right" if side == "L" else "left"})) '
                           f'(uuid {_u()}))')
        # ---- one PWR_FLAG per power net actually used ----
        used = set()
        for sym in self.syms:
            used.update(n for _, n in sym.left + sym.right if n)
        fx = self.ox
        for net in sorted(self.power_nets & used):
            out.append(_pwr_flag_instance(self.project, self.root_uuid, net,
                                          fx, 15.0))
            fx += 25.0
        out.append(')')
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        print(f"wrote {path} ({len(self.syms)} symbols)")


_PWR_FLAG_LIB = '''    (symbol "vb:PWR_FLAG" (power) (pin_names (offset 0)) (in_bom no) (on_board yes)
      (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.0 1.0))))
      (symbol "PWR_FLAG_0_1"
        (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27))
          (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "PWR_FLAG_1_1"
        (pin power_out line (at 0 0 90) (length 0)
          (name "pwr" (effects (font (size 1.0 1.0))))
          (number "1" (effects (font (size 1.0 1.0)))))))'''

_FLG_N = [0]


def _pwr_flag_instance(project: str, root_uuid: str, net: str,
                       x: float, y: float) -> str:
    _FLG_N[0] += 1
    ref = f"#FLG{_FLG_N[0]:02d}"
    s = [f'  (symbol (lib_id "vb:PWR_FLAG") (at {x:.2f} {y:.2f} 0) (unit 1) '
         f'(in_bom no) (on_board yes) (dnp no)',
         f'    (uuid {_u()})',
         f'    (property "Reference" {_esc(ref)} (at {x:.2f} {y - 2.54:.2f} 0) '
         f'(effects (font (size 1.27 1.27)) hide))',
         f'    (property "Value" "PWR_FLAG" (at {x:.2f} {y + 5.08:.2f} 0) '
         f'(effects (font (size 1.0 1.0))))',
         f'    (pin "1" (uuid {_u()}))',
         f'    (instances (project {_esc(project)} (path "/{root_uuid}" '
         f'(reference {_esc(ref)}) (unit 1)))))',
         f'  (wire (pts (xy {x:.2f} {y:.2f}) (xy {x:.2f} {y + 2.54 + 2.54:.2f})) '
         f'(stroke (width 0)) (uuid {_u()})']
    # the wire goes UP from the flag pin; label at its far end
    s[-1] = s[-1] + ')'
    s.append(f'  (global_label {_esc(net)} (shape passive) '
             f'(at {x:.2f} {y + 5.08:.2f} 90) '
             f'(effects (font (size 1.27 1.27)) (justify left)) (uuid {_u()}))')
    return "\n".join(s)
