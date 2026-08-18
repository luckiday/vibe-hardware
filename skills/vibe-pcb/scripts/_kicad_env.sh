# shellcheck shell=bash
# Shared KiCad tool resolution for the vibe-pcb scripts (sourced, not run).
#
# Resolves, in order: env override -> mac app bundle -> PATH:
#   CLI  kicad-cli            (KICAD_CLI=... to override)
#   PY   a python with pcbnew (KICAD_PY=...  to override; mac = the BUNDLED
#        python, linux distro packages put pcbnew in the system python3)
# and exports PYTHONPATH so `import pcblib` works in gen_*.py.
#
# Feature detection: kicad-cli grew `sch erc` / `pcb drc` / `pcb render` in v8.
# On older CLIs the callers fall back (drc -> drc_report.py via pcbnew, render
# -> export svg [+ rsvg-convert when present], erc -> SKIP with a loud note).
#   cli_has pcb drc   -> 0 when the subcommand exists

_VS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$_VS${PYTHONPATH:+:$PYTHONPATH}"

_KC="/Applications/KiCad/KiCad.app/Contents"

if [ -n "${KICAD_CLI:-}" ]; then CLI="$KICAD_CLI"
elif [ -x "$_KC/MacOS/kicad-cli" ]; then CLI="$_KC/MacOS/kicad-cli"
else CLI="$(command -v kicad-cli || true)"; fi
[ -n "$CLI" ] && [ -x "$CLI" ] || {
  echo "kicad-cli not found (set KICAD_CLI or install KiCad)"; exit 1; }

if [ -n "${KICAD_PY:-}" ]; then PY="$KICAD_PY"
elif [ -x "$_KC/Frameworks/Python.framework/Versions/Current/bin/python3" ]; then
  PY="$_KC/Frameworks/Python.framework/Versions/Current/bin/python3"
elif python3 -c "import pcbnew" >/dev/null 2>&1; then PY="$(command -v python3)"
else
  echo "no python with pcbnew found (set KICAD_PY)"; exit 1
fi

export CLI PY

cli_has() {  # cli_has pcb drc  -> subcommand exists on this kicad-cli
  "$CLI" "$1" "$2" --help >/dev/null 2>&1
}

# BELLY_BOX="x0,y0,x1,y1" → belly_check.py (no unquoted $(tr) split).
belly_check_box() {
  local pcb="$1" x0 y0 x1 y1 extra
  IFS=',' read -r x0 y0 x1 y1 extra <<EOF
${BELLY_BOX-}
EOF
  if [ -z "$x0" ] || [ -z "$y0" ] || [ -z "$x1" ] || [ -z "$y1" ] || [ -n "${extra:-}" ]; then
    echo "BELLY_BOX must be x0,y0,x1,y1 (got: ${BELLY_BOX:-empty})" >&2
    return 1
  fi
  "$PY" "$_VS/belly_check.py" "$pcb" "$x0" "$y0" "$x1" "$y1"
}

# render_top <board> <out.png> — 3D render on v8+; 2D svg fallback on v7
render_top() {
  if cli_has pcb render; then
    "$CLI" pcb render "$1" -o "$2" --side top --background opaque \
      -w 950 --height 600 >/dev/null
  else
    local svg="${2%.png}.svg"
    "$CLI" pcb export svg "$1" -o "$svg" --page-size-mode 2 \
      --layers "Edge.Cuts,Dwgs.User,F.Cu,F.SilkS,F.Fab,F.CrtYd" >/dev/null
    if command -v rsvg-convert >/dev/null 2>&1; then
      rsvg-convert -w 950 "$svg" -o "$2" && rm -f "$svg"
    else
      echo "   (no pcb render on kicad-cli $("$CLI" version); wrote $svg)"
    fi
  fi
}
