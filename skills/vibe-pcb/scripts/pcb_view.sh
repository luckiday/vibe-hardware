#!/usr/bin/env bash
# Interactive PCB review in ONE browser page — no KiCad GUI. Two linked panes with a
# header switch [2D | 3D | Split] (keys 1/2/3):
#   • 2D — KiCanvas reading the live .kicad_pcb: layer-visibility panel, object toggles,
#          pan/zoom, select/cross-probe, and the schematic in tabs.
#   • 3D — the kicad-cli GLB (copper + silk + components) in <model-viewer>: orbit/zoom.
# One local server (files never leave the machine), one URL.
#
#   pcb_view.sh <proj-basename> [port]      (run in the project kicad/ dir)
#
# Foreground (server stays up) — launch in the background, then open the URL.
# Offline: vendor kicanvas.js next to this script (or KICANVAS_SRC=/abs); the 3D pane's
# model-viewer is a CDN module (or set MODELVIEWER_SRC=/abs). No kicad-cli → 2D only.
set -eu

PROJ="${1:?usage: pcb_view.sh <proj-basename> [port]   (run in the project kicad/ dir)}"
PORT="${2:-8088}"
KC="/Applications/KiCad/KiCad.app/Contents"
CLI="${KICAD_CLI:-$KC/MacOS/kicad-cli}"
[ -f "$PROJ.kicad_pcb" ] || { echo "no $PROJ.kicad_pcb here — run in the project kicad/ dir"; exit 1; }

VIEW="$PWD/view"; mkdir -p "$VIEW"     # add kicad/view/ to .gitignore (regenerated)

# 3D: export the GLB if kicad-cli is present (else the page degrades to 2D only)
GLB=""
if [ -x "$CLI" ]; then
  echo "-> export 3D GLB (tracks + pads + silk + components)"
  if "$CLI" pcb export glb --include-tracks --include-pads --include-silkscreen \
        --subst-models --force -o "$VIEW/$PROJ-pcb.glb" "$PROJ.kicad_pcb" >/dev/null 2>&1; then
    GLB="$PROJ-pcb.glb"; echo "   $VIEW/$GLB"
  else echo "   (GLB export failed — 2D only)"; fi
else
  echo "-> no kicad-cli at $CLI — 2D only (set KICAD_CLI for the 3D pane)"
fi

# bundles: vendored KiCanvas wins (offline); model-viewer from CDN (or MODELVIEWER_SRC)
KICANVAS="https://kicanvas.org/kicanvas/kicanvas.js"
VEND="${KICANVAS_SRC:-$(dirname "$0")/kicanvas.js}"
[ -f "$VEND" ] && { cp "$VEND" "$VIEW/kicanvas.js"; KICANVAS="kicanvas.js"; }
MV="${MODELVIEWER_SRC:-https://cdn.jsdelivr.net/npm/@google/model-viewer/dist/model-viewer.min.js}"

KSRC="      <kicanvas-source src='../$PROJ.kicad_pcb'></kicanvas-source>"
[ -f "$PROJ.kicad_sch" ] && KSRC="$KSRC
      <kicanvas-source src='../$PROJ.kicad_sch'></kicanvas-source>"

if [ -n "$GLB" ]; then
  MVTAG="<script type='module' src='$MV'></script>"
  P3D="<model-viewer id='mv' src='$GLB' camera-controls touch-action='pan-y' exposure='1.05' shadow-intensity='0.35' environment-image='neutral' style='width:100%;height:100%;background:transparent;--poster-color:transparent'></model-viewer>"
else
  MVTAG=""
  P3D="<div style='display:grid;place-items:center;height:100%;color:#999;font:14px sans-serif'>no GLB — set KICAD_CLI to enable the 3D board pane</div>"
fi

cat > "$VIEW/pcb.html" <<HTML
<!doctype html><html lang=en><head><meta charset=utf-8>
<title>$PROJ — PCB review</title>
<script type=module src="$KICANVAS"></script>$MVTAG
<style>
  :root{--bg:#0d1117;--panel:#0b0e16;--line:#222c3d;--txt:#c9d4e3;--muted:#5b6b82;--accent:#36d399}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px system-ui,-apple-system,sans-serif}
  #bar{height:42px;display:flex;align-items:center;gap:10px;padding:0 14px;background:var(--bg);border-bottom:1px solid var(--line)}
  #bar b{color:#fff;font-weight:600;letter-spacing:.2px}
  .seg{display:flex;background:var(--panel);border:1px solid var(--line);border-radius:7px;overflow:hidden}
  .seg button{background:transparent;color:var(--txt);border:0;border-right:1px solid var(--line);padding:5px 13px;cursor:pointer;font:inherit}
  .seg button:last-child{border-right:0}
  .seg button.on{background:var(--accent);color:#04231a;font-weight:600}
  .hint{margin-left:auto;color:var(--muted)}
  #wrap{display:flex;gap:10px;height:calc(100% - 42px);padding:10px;box-sizing:border-box}
  #p2d,#p3d{flex:1;min-width:0;height:100%;background:var(--panel);border:1px solid var(--line);border-radius:9px;overflow:hidden}
  kicanvas-embed{display:block;height:100%}
  .hide{display:none!important}
</style></head><body>
<div id=bar><b>$PROJ</b>
  <div class=seg>
    <button id=b2d onclick="setv('2d')">2D layers</button>
    <button id=b3d onclick="setv('3d')">3D board</button>
    <button id=bsp onclick="setv('split')">Split</button>
  </div>
  <span class=hint>2D = KiCanvas (layers · objects · schematic)   ·   3D = orbit / zoom   ·   keys 1 / 2 / 3</span>
</div>
<div id=wrap>
  <div id=p2d><kicanvas-embed controls=full controlslist=nodownload theme=kicad>
$KSRC
  </kicanvas-embed></div>
  <div id=p3d>$P3D</div>
</div>
<script>
function setv(v){
  document.getElementById('p2d').classList.toggle('hide', v==='3d');
  document.getElementById('p3d').classList.toggle('hide', v==='2d');
  for (const [id,k] of [['b2d','2d'],['b3d','3d'],['bsp','split']])
    document.getElementById(id).classList.toggle('on', k===v);
}
addEventListener('keydown', e => { const m={1:'2d',2:'3d',3:'split'}; if(m[e.key]) setv(m[e.key]); });
setv('$([ -n "$GLB" ] && echo split || echo 2d)');
</script></body></html>
HTML

old=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
[ -n "$old" ] && { echo "freeing port $PORT (pid $old)"; kill $old 2>/dev/null || true; sleep 1; }
echo "PCB review -> http://127.0.0.1:$PORT/view/pcb.html   [2D layers | 3D board | Split]"
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$PWD"
