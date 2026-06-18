#!/usr/bin/env bash
# Package a *validated* KiCad PCB into a JLCPCB fab order: gerber+drill zip, a JLCPCB
# CPL (pick-and-place), and a starter BOM. Run from the project kicad/ dir.
#
#   tools/skills/text-to-pcb/scripts/fab_export.sh <proj-basename> [hand-soldered-ref ...]
#
# Extra args = refs you will hand-solder (the module, a THT header) — kept OUT of the
# SMT CPL/BOM. Env: KICAD_CLI=... (non-mac); INCLUDE_DNP=1 to also place DNP parts.
#
# WHY THIS SCRIPT EXISTS — the gotchas it bakes in (each one bit us once):
#   * Upload the resulting .zip at jlcpcb.com (Gerber upload). DO NOT import the KiCad
#     project into 立创EDA / EasyEDA — its KiCad importer drops footprints ("缺少封装"),
#     mangles refdes ($2I2...), and desyncs the netlist. Gerbers carry geometry, so
#     the upload path is clean. (See references/fab-and-3d.md.)
#   * drill uses ABSOLUTE origin so it lines up with the gerbers.
#   * model-only / 3D-preview footprints (empty Package, e.g. a reference baseplate)
#     are auto-dropped from the CPL — they aren't real placements.
#   * KiCad pos Y is +up; JLCPCB wants it flipped → we negate Mid Y.
#   * DNP / DNF parts (value contains "DNP"/"DNF") are not placed (INCLUDE_DNP=1 keeps).
#   * common R/C packages are mapped to JLC names (C0805, R0603, ...).
set -eu

PROJ="${1:?usage: fab_export.sh <proj-basename> [hand-soldered-ref ...]   (run in kicad/ dir)}"; shift || true
EXCLUDE="$*"

KC="/Applications/KiCad/KiCad.app/Contents"
CLI="${KICAD_CLI:-$KC/MacOS/kicad-cli}"
[ -x "$CLI" ] || { echo "kicad-cli not found: $CLI   (set KICAD_CLI)"; exit 1; }
[ -f "$PROJ.kicad_pcb" ] || { echo "no $PROJ.kicad_pcb here — run me in the project kicad/ dir"; exit 1; }

OUT=fab; G="$OUT/gerber"; rm -rf "$OUT"; mkdir -p "$G"

echo "-> gerbers"; "$CLI" pcb export gerbers "$PROJ.kicad_pcb" -o "$G/" \
  --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --no-x2 --subtract-soldermask >/dev/null
echo "-> drill";   "$CLI" pcb export drill "$PROJ.kicad_pcb" -o "$G/" \
  --format excellon --drill-origin absolute --excellon-units mm --excellon-separate-th >/dev/null
echo "-> pos";     "$CLI" pcb export pos "$PROJ.kicad_pcb" -o "$OUT/_pos.csv" --format csv --units mm >/dev/null

echo "-> CPL + starter BOM"
EXCLUDE="$EXCLUDE" PROJ="$PROJ" INCLUDE_DNP="${INCLUDE_DNP:-}" python3 - "$OUT" <<'PY'
import csv, os, sys, collections, re
out=sys.argv[1]; proj=os.environ["PROJ"]
excl=set(os.environ.get("EXCLUDE","").split())
keep_dnp=bool(os.environ.get("INCLUDE_DNP"))
rows=list(csv.DictReader(open(f"{out}/_pos.csv")))

def jlc_fp(pkg):  # map common KiCad land names -> JLCPCB footprint names
    m=re.search(r'^([RC])_(\d{4})_', pkg) or re.search(r'^([RC])_(\d{4})', pkg)
    return f"{m.group(1)}{m.group(2)}" if m else pkg

cpl, placed = [], []
for r in rows:
    if not r["Package"].strip():          continue   # model-only / 3D-preview helper
    if r["Ref"] in excl:                  continue   # hand-soldered (module / THT header)
    if not keep_dnp and re.search(r'DN[PF]', r["Val"], re.I): continue   # DNP/DNF: not placed
    placed.append(r)
    cpl.append([r["Ref"], f'{float(r["PosX"]):.3f}', f'{-float(r["PosY"]):.3f}',
                "Top" if r["Side"]=="top" else "Bottom", r["Rot"]])

with open(f"{out}/{proj}-CPL-jlcpcb.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["Designator","Mid X","Mid Y","Layer","Rotation"]); w.writerows(cpl)

grp=collections.OrderedDict()
for r in placed: grp.setdefault((r["Val"], jlc_fp(r["Package"])), []).append(r["Ref"])
with open(f"{out}/{proj}-BOM-jlcpcb.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["Comment","Designator","Footprint","LCSC Part #"])
    for (val,fp),refs in grp.items(): w.writerow([val, ",".join(sorted(refs)), fp, ""])

print(f"   CPL: {len(cpl)} SMT placement(s) · BOM: {len(grp)} line(s)  (fill LCSC #s before an SMT order)")
if excl:        print(f"   hand-soldered (excluded): {', '.join(sorted(excl))}")
PY
rm -f "$OUT/_pos.csv"

( cd "$G" && zip -q -j "../$PROJ-gerber-jlcpcb.zip" ./* )
echo
echo "wrote $OUT/$PROJ-gerber-jlcpcb.zip  +  $PROJ-CPL-jlcpcb.csv  +  $PROJ-BOM-jlcpcb.csv"
echo "→ jlcpcb.com → Gerber upload (the .zip).  Do NOT import the KiCad project into 立创EDA."
