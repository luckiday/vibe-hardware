#!/usr/bin/env python3
"""plm_check.py — the vibe-plm gate: is the product manifest sane, do the
interface contracts between the three domains resolve, and does their CONTENT
still agree?

Beyond file existence it cross-checks contract *contents*:
  - pinmap <-> firmware config header (`firmware.config_header:` + `define:` keys)
  - constraints.yaml <-> placement.json (outline, mount holes, port/window centers)
  - a GPIO lint on the pinmap (duplicates, strapping/reserved pins, native USB)

Self-contained by design (the repo rule: a skill's scripts never import or call
another skill's code). This reads `product.yaml` and the contract files it
names; it NEVER runs pcb_check.sh / check_fit.py / a firmware build. Each
domain runs its own gate; this proves only the *contracts between* them are
consistent. (vibe-pcb's pcblib/contract.py carries a twin YAML-subset parser —
twins by design, never an import.)

Usage:
    python3 plm_check.py [product.yaml]      # default: ./product.yaml

Exit 0 = no errors (warnings allowed). Exit 1 = errors (or manifest not found).
Uses PyYAML if available; otherwise a vendored YAML-subset parser (nested maps,
lists, inline {..}/[..], comments) rich enough for product.yaml, pinmap.yaml
and constraints.yaml. Stdlib only.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

DOMAINS = ("firmware", "pcb", "cad")

# how a contract is classified by extension (see references/manifest-and-interfaces.md);
# a mapping-form interface (`{path: …, kind: …}`) overrides this explicitly.
SOURCE_EXTS = {".yaml", ".yml", ".json", ".md", ".toml", ".csv"}
ARTIFACT_EXTS = {".step", ".stp", ".glb", ".stl", ".gbr", ".zip", ".bin", ".elf", ".uf2"}

REV_RE = re.compile(r"^v\d{4}-\d{2}-\d{2}$")


# ── YAML loading (PyYAML if present, else a vendored subset parser) ──────────
def _scalar(v: str):
    v = v.strip()
    if not v or v in ("~", "null"):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
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
    """Drop an inline `#` comment that's not inside a quote."""
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
    first = lines[i][1]
    if first.lstrip().startswith("- "):
        out = []
        while i < len(lines):
            ind, text = lines[i]
            if ind < indent or not text.lstrip().startswith("- "):
                break
            item = text.lstrip()[2:]
            if not item:
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
            if i + 1 < len(lines) and lines[i + 1][0] > ind:
                out[key], i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                out[key] = None
                i += 1
    return out, i


def _parse_yaml_subset(text: str) -> dict:
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.strip():
            lines.append((len(line) - len(line.lstrip()), line))
    if not lines:
        return {}
    val, _ = _parse_block(lines, 0, lines[0][0])
    return val if isinstance(val, dict) else {}


def load_yaml(path: str) -> dict:
    """Load a YAML file: PyYAML when available, else the subset parser."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # noqa: PLC0415

        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_yaml_subset(text)


def parse_manifest(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(text) or {}
        engine = "PyYAML"
    except Exception:
        try:
            data = _parse_yaml_subset(text)
        except Exception:
            data = {}
        engine = "yaml-subset (PyYAML not found)"
    return {"data": data, "engine": engine}


# ── report ───────────────────────────────────────────────────────────────────
class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.oks: list[str] = []

    def ok(self, m: str) -> None:
        self.oks.append(m)
        print(f"  ✓ {m}")

    def warn(self, m: str) -> None:
        self.warns.append(m)
        print(f"  ! {m}")

    def err(self, m: str) -> None:
        self.errors.append(m)
        print(f"  ✗ {m}")


# ── GPIO lint tables ─────────────────────────────────────────────────────────
# Keyed by mcu prefix (substring-matched against a lowercased `mcu:`). Add other
# MCUs as new rows — the lint below is table-driven.
MCU_GPIO_RULES = {
    "esp32-s3": {
        "strapping": {0, 3, 45, 46},
        "reserved": [(set(range(26, 33)), "reserved for SPI flash")],
        # applies only when the mcu name marks octal PSRAM (…r8 / n16r8 / n8r8)
        "octal_psram": (set(range(33, 38)), "reserved for octal PSRAM"),
        "octal_markers": ("n16r8", "n8r8"),
        "usb": {19: "native USB D-", 20: "native USB D+"},
    },
}

_GPIO_NAME_RE = re.compile(r"(?i)^\s*(?:GPIO[_ ]?(?:NUM[_ ]?)?)?(\d+)\s*$")


def _gpio_num(v):
    """'GPIO39' / 'GPIO_NUM_39' / 39 -> 39 (int), else None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    m = _GPIO_NAME_RE.match(str(v))
    return int(m.group(1)) if m else None


def _lint_pinmap(r: Report, pm: dict, relpath: str) -> None:
    pins = pm.get("pins") or []
    entries = []
    for p in pins:
        if isinstance(p, dict):
            g = _gpio_num(p.get("gpio"))
            if g is not None:
                entries.append((p, g))
    if not entries:
        return
    before = len(r.errors) + len(r.warns)

    # (a) duplicate gpio assignments
    by_gpio: dict[int, list] = {}
    for p, g in entries:
        by_gpio.setdefault(g, []).append(p)
    for g in sorted(by_gpio):
        ps = by_gpio[g]
        if len(ps) > 1:
            sigs = " + ".join(str(p.get("signal", "?")) for p in ps)
            r.err(f"pinmap: GPIO{g} assigned twice: {sigs}")

    mcu = str(pm.get("mcu") or "").lower()
    rules = next((v for k, v in MCU_GPIO_RULES.items() if k in mcu), None)
    if rules:
        octal = mcu.endswith("r8") or any(mk in mcu for mk in rules["octal_markers"])
        for p, g in entries:
            sig = str(p.get("signal", "?"))
            # (b) strapping pins
            if g in rules["strapping"] and not p.get("strap_ok"):
                r.warn(f"pinmap: {sig} on GPIO{g} — strapping pin (set strap_ok: true if deliberate)")
            # (c) reserved ranges
            for pins_set, why in rules["reserved"]:
                if g in pins_set:
                    r.err(f"pinmap: {sig} on GPIO{g} — {why}")
            if octal and g in rules["octal_psram"][0]:
                r.err(f"pinmap: {sig} on GPIO{g} — {rules['octal_psram'][1]}")
            # (d) native USB pins
            if g in rules["usb"]:
                blob = f"{p.get('signal', '')} {p.get('to', '')}".lower()
                if "usb" not in blob:
                    r.warn(f"pinmap: {sig} on GPIO{g} — {rules['usb'][g]} (mention usb in signal/to if intended)")

    if len(r.errors) + len(r.warns) == before:
        r.ok(f"pinmap lint: {len(entries)} pin(s), no gpio conflicts ({relpath})")


# ── pinmap <-> firmware config header ────────────────────────────────────────
_DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+(.+?)\s*$")
_GPIO_VAL_RE = re.compile(r"^(?:GPIO_NUM_)?(\d+)$")


def _header_gpio_defines(path: str) -> dict:
    """{NAME: gpio_int} for every `#define NAME GPIO_NUM_n` / `#define NAME n`."""
    out: dict = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _DEFINE_RE.match(line)
            if not m:
                continue
            val = re.split(r"//|/\*", m.group(2))[0].strip()
            vm = _GPIO_VAL_RE.match(val)
            if vm:
                out[m.group(1)] = int(vm.group(1))
    return out


def _check_pinmap_header(r: Report, pm: dict, header_abs: str, header_rel: str) -> None:
    defines = _header_gpio_defines(header_abs)
    matched, dirty = 0, False
    for p in pm.get("pins") or []:
        if not isinstance(p, dict) or "define" not in p:
            continue
        name = str(p["define"])
        want = _gpio_num(p.get("gpio"))
        if name not in defines:
            r.warn(f"pinmap<->header: {name} not defined in {header_rel}")
            dirty = True
        elif want is None or defines[name] != want:
            r.err(
                f"pinmap<->header: {name} is GPIO{defines[name]} in {header_rel} "
                f"but GPIO{want} in the pinmap ({p.get('signal', '?')})"
            )
            dirty = True
        else:
            matched += 1
    if matched and not dirty:
        r.ok(f"pinmap<->header: {matched} define(s) agree with {header_rel}")


# ── constraints.yaml <-> placement.json ──────────────────────────────────────
def _feq(a, b, eps: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return a == b


def _port_center(spec: dict, length: float, width: float):
    """A port's contract center: edge ±X -> (edge_x, center_y); ±Y -> (center_x, edge_y)."""
    edge = str(spec.get("edge", ""))
    try:
        if edge in ("+X", "-X") and spec.get("center_y") is not None:
            return (length if edge == "+X" else 0.0, float(spec["center_y"]))
        if edge in ("+Y", "-Y") and spec.get("center_x") is not None:
            return (float(spec["center_x"]), width if edge == "+Y" else 0.0)
    except (TypeError, ValueError):
        pass
    return None


def _check_constraints_placement(r: Report, cons: dict, plc: dict, plc_rel: str) -> None:
    try:
        tol = float(cons.get("tolerance_mm", 0.5))
    except (TypeError, ValueError):
        tol = 0.5
    board = cons.get("board") if isinstance(cons.get("board"), dict) else {}
    o = board.get("outline") if isinstance(board.get("outline"), dict) else {}
    po = plc.get("outline") if isinstance(plc.get("outline"), dict) else {}

    # (a) outline: exact match
    bad = [k for k in ("l", "w", "t", "corner_r") if not _feq(o.get(k), po.get(k))]
    if bad:
        detail = ", ".join(f"{k}: {o.get(k)} vs {po.get(k)}" for k in bad)
        r.err(f"constraints<->placement: outline mismatch ({detail})")
    else:
        r.ok("constraints<->placement: outline agrees (l/w/t/corner_r)")

    # (b) mount holes: dia + positions as an exact set
    mh = board.get("mount_holes") if isinstance(board.get("mount_holes"), dict) else {}
    pmh = plc.get("mount_holes") if isinstance(plc.get("mount_holes"), dict) else {}

    def posset(d):
        try:
            return {(round(float(p[0]), 3), round(float(p[1]), 3)) for p in (d.get("positions") or [])}
        except (TypeError, ValueError, IndexError):
            return None

    a, b = posset(mh), posset(pmh)
    if not _feq(mh.get("dia"), pmh.get("dia")) or a is None or b is None or a != b:
        r.err(
            f"constraints<->placement: mount_holes mismatch "
            f"(dia {mh.get('dia')} vs {pmh.get('dia')}; positions {sorted(a or [])} vs {sorted(b or [])})"
        )
    else:
        r.ok(f"constraints<->placement: mount_holes agree (dia {mh.get('dia')}, {len(a)} position(s))")

    # (c) port/window centers vs placement items (match by kind, then by ref)
    items = [it for it in (plc.get("items") or []) if isinstance(it, dict)]

    def find_item(name: str):
        for it in items:
            if it.get("kind") == name:
                return it
        for it in items:
            if it.get("ref") == name:
                return it
        return None

    try:
        length, width = float(o.get("l")), float(o.get("w"))
    except (TypeError, ValueError):
        length = width = 0.0
    matched, max_drift, dirty = 0, 0.0, False
    for section in ("ports", "windows"):
        block = cons.get(section) if isinstance(cons.get(section), dict) else {}
        for name, spec in block.items():
            if not isinstance(spec, dict):
                continue
            if section == "ports":
                exp = _port_center(spec, length, width)
            elif spec.get("x") is not None and spec.get("y") is not None:
                exp = (float(spec["x"]), float(spec["y"]))  # window x,y IS the center
            else:
                exp = None
            if exp is None:
                continue
            it = find_item(str(name))
            if it is None:
                r.warn(f"constraints<->placement: {section}.{name} not evidenced in {plc_rel}")
                continue
            c = it.get("center") or []
            try:
                cx, cy = float(c[0]), float(c[1])
            except (TypeError, ValueError, IndexError):
                r.err(f"constraints<->placement: {section}.{name} item {it.get('ref', '?')} has no usable center")
                dirty = True
                continue
            drift = math.hypot(cx - exp[0], cy - exp[1])
            matched += 1
            if drift > tol:
                dirty = True
                r.err(
                    f"constraints<->placement: {section}.{name} drifted {drift:.2f} mm > {tol:g} mm "
                    f"(contract ({exp[0]:g}, {exp[1]:g}) vs {it.get('ref', '?')} ({cx:g}, {cy:g}))"
                )
            else:
                max_drift = max(max_drift, drift)
    if matched and not dirty:
        r.ok(f"constraints<->placement: {matched} port/window(s) within {tol:g} mm (max drift {max_drift:.2f} mm)")


# ── cross-check driver ───────────────────────────────────────────────────────
def _load_contract_yaml(r: Report, root: str, relpath: str, label: str):
    try:
        data = load_yaml(os.path.join(root, relpath))
    except Exception as e:  # malformed contract: report, skip content checks
        r.warn(f"{label}: could not parse {relpath} ({e}) — content checks skipped")
        return None
    return data if isinstance(data, dict) else None


def _cross_checks(r: Report, root: str, data: dict, contracts: dict) -> None:
    pin_rel, pin_ok = contracts.get("pinmap", (None, False))
    cons_rel, cons_ok = contracts.get("enclosure_constraints", (None, False))
    plc_rel, plc_ok = contracts.get("placement", (None, False))
    fw = data.get("firmware")
    header_rel = fw.get("config_header") if isinstance(fw, dict) else None

    if not (pin_ok or (cons_ok and plc_ok)):
        return
    print("\n cross-checks:")

    if pin_ok:
        pm = _load_contract_yaml(r, root, pin_rel, "pinmap")
        if pm is not None:
            _lint_pinmap(r, pm, pin_rel)
            if header_rel:
                header_rel = str(header_rel)
                habs = os.path.join(root, header_rel)
                if os.path.isfile(habs):
                    _check_pinmap_header(r, pm, habs, header_rel)
                else:
                    r.warn(f"firmware.config_header: {header_rel} not found — pinmap<->header check skipped")

    if cons_ok and plc_ok:
        cons = _load_contract_yaml(r, root, cons_rel, "enclosure_constraints")
        try:
            with open(os.path.join(root, plc_rel), encoding="utf-8") as fh:
                plc = json.load(fh)
        except Exception as e:
            r.warn(f"placement: could not parse {plc_rel} ({e}) — content checks skipped")
            plc = None
        if cons is not None and isinstance(plc, dict):
            _check_constraints_placement(r, cons, plc, plc_rel)


# ── checks ───────────────────────────────────────────────────────────────────
def check(manifest_path: str) -> int:
    manifest_path = os.path.abspath(manifest_path)
    root = os.path.dirname(manifest_path)
    if not os.path.isfile(manifest_path):
        print(f"✗ manifest not found: {manifest_path}")
        return 1

    parsed = parse_manifest(manifest_path)
    data, engine = parsed["data"], parsed["engine"]
    rel = os.path.relpath(manifest_path)
    print(f"vibe-plm check · {rel}  [{engine}]\n")

    r = Report()

    # identity
    product = data.get("product")
    if product:
        r.ok(f"product: {product}")
    else:
        r.err("missing required key: product")

    rev = data.get("revision")
    if not rev:
        r.err("missing required key: revision")
    elif REV_RE.match(str(rev)):
        r.ok(f"revision: {rev}")
    else:
        r.warn(f"revision '{rev}' is not vYYYY-MM-DD")

    # domains
    print("\n domains:")
    for d in DOMAINS:
        block = data.get(d)
        if not isinstance(block, dict):
            r.err(f"{d}: missing domain block")
            continue
        ddir = block.get("dir")
        if not ddir:
            r.err(f"{d}: no 'dir:'")
        elif os.path.isdir(os.path.join(root, ddir)):
            r.ok(f"{d}: {ddir} (status: {block.get('status', '?')})")
        else:
            r.err(f"{d}: dir '{ddir}' does not exist")

    # interface contracts
    print("\n interfaces:")
    contracts: dict = {}  # name -> (relpath, exists) for the content cross-checks
    interfaces = data.get("interfaces")
    if not isinstance(interfaces, dict) or not interfaces:
        r.err("no 'interfaces:' contracts declared")
    else:
        for name, spec in interfaces.items():
            kind_override = None
            if isinstance(spec, dict):  # mapping form: {path: …, kind: source|artifact}
                p = str(spec.get("path") or "")
                if not p:
                    r.err(f"{name}: mapping form needs a 'path:'")
                    continue
                kind_override = spec.get("kind")
                if kind_override not in (None, "source", "artifact"):
                    r.warn(f"{name}: unknown kind '{kind_override}' — classifying by extension")
                    kind_override = None
            else:
                p = str(spec)
            ext = os.path.splitext(p)[1].lower()
            kind = kind_override or ("artifact" if ext in ARTIFACT_EXTS else "source")
            exists = os.path.isfile(os.path.join(root, p))
            contracts[name] = (p, exists)
            if exists:
                r.ok(f"{name}: {p} [{kind}]")
            elif kind == "artifact":
                r.warn(f"{name}: {p} [artifact] not generated yet")
            else:
                r.err(f"{name}: {p} [source] missing")

    # content-level cross-checks (pinmap lint, pinmap<->header, constraints<->placement)
    _cross_checks(r, root, data, contracts)

    # gate
    print("\n" + "-" * 56)
    if r.errors:
        print(f"GATE: FAIL — {len(r.errors)} error(s), {len(r.warns)} warning(s)")
        return 1
    print(f"GATE: PASS — 0 errors, {len(r.warns)} warning(s)")
    return 0


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "product.yaml"
    return check(path)


if __name__ == "__main__":
    raise SystemExit(main())
