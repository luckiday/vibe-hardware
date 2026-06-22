#!/usr/bin/env python3
"""plm_check.py — the vibe-plm gate: is the product manifest sane and do the
interface contracts between the three domains resolve?

Self-contained by design (the repo rule: a skill's scripts never import or call
another skill's code). This reads `product.yaml` and stats the contract files; it
NEVER runs pcb_check.sh / check_fit.py / a firmware build. Each domain runs its own
gate; this proves only the *contracts between* them are consistent.

Usage:
    python3 plm_check.py [product.yaml]      # default: ./product.yaml

Exit 0 = no errors (warnings allowed). Exit 1 = errors (or manifest not found).
Uses PyYAML if available; otherwise falls back to a targeted line-scan that
understands the small, fixed manifest schema. Stdlib only.
"""
from __future__ import annotations

import os
import re
import sys

DOMAINS = ("firmware", "pcb", "cad")

# how a contract is classified by extension (see references/manifest-and-interfaces.md)
SOURCE_EXTS = {".yaml", ".yml", ".json", ".md", ".toml", ".csv"}
ARTIFACT_EXTS = {".step", ".stp", ".glb", ".stl", ".gbr", ".zip", ".bin", ".elf", ".uf2"}

REV_RE = re.compile(r"^v\d{4}-\d{2}-\d{2}$")


# ── manifest parsing ─────────────────────────────────────────────────────────
def _strip_comment(line: str) -> str:
    """Drop an inline `#` comment that's not inside a quote."""
    q = None
    out = []
    for c in line:
        if q:
            out.append(c)
            if c == q:
                q = None
        elif c in ('"', "'"):
            q = c
            out.append(c)
        elif c == "#":
            break
        else:
            out.append(c)
    return "".join(out).rstrip()


def _scalar(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1]
    return v


def _parse_with_yaml(text: str) -> dict:
    import yaml  # noqa: PLC0415

    return yaml.safe_load(text) or {}


def _parse_lines(text: str) -> dict:
    """Targeted fallback parser for the fixed manifest schema (no PyYAML).

    Understands: top-level `key:` / `key: value`; inline-map values
    `key: { dir: x, ... }`; one level of nesting under a top-level key; the
    `interfaces:` block of `name: path` pairs. Enough for product.yaml.
    """
    data: dict = {}
    top = None  # current top-level key whose nested block we're reading
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if ":" not in body:
            continue
        key, _, val = body.partition(":")
        key, val = key.strip(), val.strip()
        if indent == 0:
            top = key
            if val.startswith("{") and val.endswith("}"):  # inline map
                data[key] = _inline_map(val)
                top = None
            elif val:
                data[key] = _scalar(val)
            else:
                data[key] = {}
        elif indent >= 2 and top is not None:
            block = data.get(top)
            if not isinstance(block, dict):
                block = data[top] = {}
            block[key] = _scalar(val) if val else {}
    return data


def _inline_map(s: str) -> dict:
    inner = s.strip()[1:-1]
    out: dict = {}
    for part in inner.split(","):
        if ":" in part:
            k, _, v = part.partition(":")
            out[k.strip()] = _scalar(v)
    return out


def parse_manifest(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        data = _parse_with_yaml(text)
        engine = "PyYAML"
    except Exception:
        data = _parse_lines(text)
        engine = "line-scan (PyYAML not found)"
    return {"data": data, "engine": engine}


# ── checks ───────────────────────────────────────────────────────────────────
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
    interfaces = data.get("interfaces")
    if not isinstance(interfaces, dict) or not interfaces:
        r.err("no 'interfaces:' contracts declared")
    else:
        for name, p in interfaces.items():
            p = str(p)
            ext = os.path.splitext(p)[1].lower()
            kind = "artifact" if ext in ARTIFACT_EXTS else "source"
            exists = os.path.isfile(os.path.join(root, p))
            if exists:
                r.ok(f"{name}: {p} [{kind}]")
            elif kind == "artifact":
                r.warn(f"{name}: {p} [artifact] not generated yet")
            else:
                r.err(f"{name}: {p} [source] missing")

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
