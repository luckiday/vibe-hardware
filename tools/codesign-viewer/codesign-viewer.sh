#!/usr/bin/env bash
# codesign-viewer.sh — ONE browser page for a whole vibe-plm product: the PCB (2D
# KiCanvas + 3D board) AND the CAD enclosure (tray / fit / exploded), side by side,
# with the product.yaml manifest + contract status across the top.
#
#   codesign-viewer.sh <product-dir> [port]      (the dir with product.yaml)
#
# What it does (all local, files never leave the machine):
#   • reads product.yaml for identity + revision + which interface contracts resolve,
#   • exports the PCB GLB from pcb/kicad/*.kicad_pcb via kicad-cli (the board now carries
#     the real enclosure tray model, so the 3D pane shows the board IN its shell),
#   • finds the CAD GLB sidecars build_all.py emits in cad/models/ (.<name>.step.glb),
#   • writes view/index.html and serves it with python3 -m http.server.
#
# Learns from vibe-pcb/scripts/pcb_view.sh (KiCanvas + <model-viewer> + http.server) and
# vibe-cad/scripts/cad_viewer.sh (STEP renders via a GLB sidecar). No bespoke server, no
# CAD kernel in the browser — both domains are just GLB in <model-viewer> + the live
# .kicad_pcb in KiCanvas. CDN for KiCanvas / model-viewer (vendor offline later).
set -eu

PROD_IN="${1:?usage: codesign-viewer.sh <product-dir> [port]   (dir holding product.yaml)}"
PORT="${2:-8099}"
PROD="$(cd "$PROD_IN" 2>/dev/null && pwd || true)"
[ -n "$PROD" ] && [ -f "$PROD/product.yaml" ] || { echo "no product.yaml in '$PROD_IN'"; exit 1; }

CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
VIEW="$PROD/view"; mkdir -p "$VIEW"   # regenerated — add view/ to the product .gitignore

# ── manifest identity + contract resolution ─────────────────────────────────────────
val(){ grep -E "^$1:" "$PROD/product.yaml" | head -1 \
  | sed -E "s/^$1:[[:space:]]*//; s/[[:space:]]*#.*$//; s/^\"(.*)\"$/\1/; s/^'(.*)'\$/\1/"; }
NAME="$(val product)"; REV="$(val revision)"; SUMMARY="$(val summary)"
ctract(){ # name path -> chip html
  local n="$1" p="$2"
  if [ -f "$PROD/$p" ]; then echo "<span class=chip ok>$n ✓</span>"
  else echo "<span class=chip no>$n ✗</span>"; fi
}
PINMAP=$(ctract pinmap "pcb/pinmap.yaml")
BOARDSTEP=$(ctract board.step "pcb/board.step")
CONSTR=$(ctract constraints "cad/constraints.yaml")

# ── PCB: live .kicad_pcb for KiCanvas + a GLB for the 3D pane ─────────────────────────
KPCB="$(ls "$PROD"/pcb/kicad/*.kicad_pcb 2>/dev/null | head -1 || true)"
KSRC=""; SCHSRC=""; PCB_GLB=""
if [ -n "$KPCB" ]; then
  PROJ="$(basename "${KPCB%.kicad_pcb}")"
  REL_PCB="pcb/kicad/$(basename "$KPCB")"
  KSRC="      <kicanvas-source src='/$REL_PCB'></kicanvas-source>"
  [ -f "${KPCB%.kicad_pcb}.kicad_sch" ] && \
    SCHSRC="      <kicanvas-source src='/pcb/kicad/$PROJ.kicad_sch'></kicanvas-source>"
  if [ -x "$CLI" ]; then
    echo "-> export PCB GLB (board + components + the enclosure tray model)"
    "$CLI" pcb export glb --include-tracks --include-pads --include-silkscreen \
        --subst-models --force -o "$VIEW/pcb.glb" "$KPCB" >/dev/null 2>&1 \
      && PCB_GLB="/view/pcb.glb" || echo "   (GLB export failed — PCB 3D pane disabled)"
  else echo "-> no kicad-cli ($CLI) — PCB 3D pane disabled"; fi
fi

# ── CAD: the GLB sidecars build_all.py wrote next to the STEPs (hidden .<name>.step.glb)
glb(){ # keyword -> root-absolute url of the matching cad GLB (or empty)
  local f; f="$(ls "$PROD"/cad/models/.*"$1"*.step.glb 2>/dev/null | head -1 || true)"
  [ -n "$f" ] && echo "/cad/models/$(basename "$f")" || echo ""
}
G_ENCL="$(glb assembly)"; [ -z "$G_ENCL" ] && G_ENCL="$(glb tray)"
G_FIT="$(glb fit)"; G_EXPL="$(glb exploded)"
[ -z "$G_FIT$G_ENCL$G_EXPL" ] && echo "-> no CAD GLBs in cad/models/ — run: (cd cad && ../../structure/.venv/bin/python build_all.py)"

# ── schematic tab + pane — only injected when a .kicad_sch resolved ───────────────────
SCH_BTN=""; SCH_PANE=""
if [ -n "$SCHSRC" ]; then
  SCH_BTN="    <button data-v=sch>Schematic</button>"
  SCH_PANE="  <div id=psch class=hide><kicanvas-embed controls=full controlslist=nodownload theme=kicad>
$SCHSRC
  </kicanvas-embed></div>"
fi

# ── one page ─────────────────────────────────────────────────────────────────────────
KICANVAS="https://kicanvas.org/kicanvas/kicanvas.js"
THREE_VER="0.169.0"   # 3D panes use a small inline three.js renderer (shading per text-to-cad)

cat > "$VIEW/index.html" <<HTML
<!doctype html><html lang=en><head><meta charset=utf-8>
<title>$NAME — codesign</title>
<script type=module src="$KICANVAS"></script>
<script type=importmap>
{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@$THREE_VER/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@$THREE_VER/examples/jsm/"
}}
</script>
<style>
  :root{--bg:#0d1117;--panel:#0b0e16;--line:#222c3d;--txt:#c9d4e3;--muted:#5b6b82;--accent:#36d399}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px system-ui,-apple-system,sans-serif}
  #bar{display:flex;align-items:center;gap:12px;padding:8px 14px;background:var(--bg);border-bottom:1px solid var(--line);flex-wrap:wrap}
  #bar b{color:#fff;font-weight:650;letter-spacing:.2px;font-size:14px}
  .rev{color:var(--muted);font-variant-numeric:tabular-nums}
  .sum{color:var(--muted);flex-basis:100%;font-size:12px;margin-top:-2px}
  .chips{display:flex;gap:6px}
  .chip{font-size:11px;padding:2px 7px;border-radius:20px;border:1px solid var(--line)}
  .chip.ok{color:#9ff0d4;border-color:#1f6f57}.chip.no{color:#f0a39f;border-color:#7a2f2c}
  .seg{display:flex;background:var(--panel);border:1px solid var(--line);border-radius:7px;overflow:hidden}
  .seg button{background:transparent;color:var(--txt);border:0;border-right:1px solid var(--line);padding:5px 12px;cursor:pointer;font:inherit}
  .seg button:last-child{border-right:0}
  .seg button.on{background:var(--accent);color:#04231a;font-weight:600}
  .seg button:disabled{color:var(--muted);cursor:not-allowed}
  .hint{margin-left:auto;color:var(--muted)}
  #stage{height:calc(100% - 86px);padding:10px;box-sizing:border-box}
  #p2d,#psch,#p3d{position:relative;width:100%;height:100%;background:var(--panel);border:1px solid var(--line);border-radius:9px;overflow:hidden}
  #p3d{background:#eaeef4}
  #p3d canvas{display:block;width:100%;height:100%}
  kicanvas-embed{display:block;height:100%}
  #p3d .note{position:absolute;left:14px;bottom:12px;color:#5b6b82;font-size:11px;pointer-events:none}
  #parts{position:absolute;left:10px;top:10px;background:rgba(255,255,255,.82);border:1px solid #d3dae6;border-radius:8px;padding:6px 9px;font-size:11px;color:#1f2933;max-height:calc(100% - 24px);overflow:auto;min-width:104px;-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
  #parts .ptitle{display:flex;justify-content:space-between;gap:10px;font-weight:600;color:#5b6b82;margin:0 0 4px;text-transform:uppercase;letter-spacing:.4px;font-size:10px}
  #parts .ptitle a{color:#3076d1;text-decoration:none;cursor:pointer;text-transform:none;letter-spacing:0;font-weight:500}
  #parts .prow{display:flex;align-items:center;gap:6px;padding:2px 0;cursor:pointer;white-space:nowrap}
  #parts .prow input{margin:0;cursor:pointer;accent-color:#36a37a}
  .hide{display:none!important}
  .empty{display:grid;place-items:center;height:100%;color:var(--muted);font-size:13px}
</style></head><body>
<div id=bar>
  <b>$NAME</b><span class=rev>$REV</span>
  <span class=chips>$PINMAP $BOARDSTEP $CONSTR</span>
  <div class=seg id=tabs>
    <button data-v=2d>PCB 2D</button>
$SCH_BTN
    <button data-v=3d data-mode=pcb data-src="$PCB_GLB">PCB 3D</button>
    <button data-v=encl data-mode=cad data-src="$G_ENCL">Enclosure</button>
    <button data-v=fit data-mode=cad data-src="$G_FIT">Fit</button>
    <button data-v=expl data-mode=cad data-src="$G_EXPL">Exploded</button>
  </div>
  <span class=hint>PCB 2D / Schematic = KiCanvas · 3D = orbit/zoom · number keys switch tabs</span>
  <div class=sum>$SUMMARY</div>
</div>
<div id=stage>
  <div id=p2d><kicanvas-embed controls=full controlslist=nodownload theme=kicad>
$KSRC
  </kicanvas-embed></div>
$SCH_PANE
  <div id=p3d class=hide><div id=parts class=hide></div><div class=note>orbit · scroll-zoom · right-drag pan · toggle parts ↖</div></div>
</div>
<script type=module>
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// ── renderer / scene / camera — shading recipe borrowed from text-to-cad's CAD Viewer:
//    ACES tone-map + sRGB, a 3-point directional rig over a hemisphere, MeshPhysicalMaterial
//    (surface #f4f4f5, roughness .92, metalness .03) and an EdgesGeometry(16 deg) overlay in
//    #18181b @ .84 — the dark feature-edge overlay is what makes parts read as parts.
var host=document.getElementById('p3d');
var renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.16;
renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
host.appendChild(renderer.domElement);

var scene=new THREE.Scene();
scene.background=new THREE.Color('#eaeef4');
var pmrem=new THREE.PMREMGenerator(renderer);
scene.environment=pmrem.fromScene(new RoomEnvironment(),0.04).texture;

var camera=new THREE.PerspectiveCamera(48,1,0.1,50000);
camera.up.set(0,0,1); camera.position.set(180,-180,120);
var controls=new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true; controls.dampingFactor=0.08;

scene.add(new THREE.HemisphereLight('#ffffff','#b7c0cd',0.55));
var key=new THREE.DirectionalLight('#ffffff',1.1); key.position.set(240,-150,340);
key.castShadow=true; key.shadow.mapSize.set(2048,2048); key.shadow.bias=-0.00025; key.shadow.normalBias=0.024;
scene.add(key);
var fill=new THREE.DirectionalLight('#ffffff',0.42); fill.position.set(120,80,210); scene.add(fill);
var rim=new THREE.DirectionalLight('#ffffff',0.35); rim.position.set(-260,240,180); scene.add(rim);

var loader=new GLTFLoader(), current=null, ground=null;
function disposeObj(o){ o.traverse(function(n){ if(n.geometry)n.geometry.dispose(); if(n.material){ [].concat(n.material).forEach(function(m){m.dispose&&m.dispose();}); } }); }
function clear(){ if(current){ scene.remove(current); disposeObj(current); current=null; } if(ground){ scene.remove(ground); ground.geometry.dispose(); ground.material.dispose(); ground=null; } var pp=document.getElementById('parts'); if(pp){ pp.classList.add('hide'); pp.innerHTML=''; } }

// ── per-part show/hide (like the text-to-cad CAD Viewer) ──────────────────────────────
// Group meshes by their nearest *named* ancestor and map that to a friendly module: the
// PCB GLB names nodes by kicad refdes (A1/MLX1/J1/H1/ENCLOSURE_REF…), the CAD GLBs name
// their top-level parts (tray/carrier/xiao/thermal/cover — set by build_all.py).
function moduleOf(nm){
  if(!nm) return null; var n=nm.toUpperCase();
  if(n==='TRAY'||n.indexOf('ENCLOSURE')>=0) return 'Enclosure';
  if(n==='COVER') return 'Cover';
  if(n==='CARRIER') return 'Carrier';
  if(n==='XIAO'||n.indexOf('XIAO')>=0||n.indexOf('A1')===0||n.indexOf('USB TYPE')>=0) return 'XIAO';
  if(n==='THERMAL'||n.indexOf('MLX')>=0||n.indexOf('90642')>=0||n.indexOf('90640')>=0) return 'Thermal sensor';
  if(n.indexOf('J1')===0||n.indexOf('HEADER')>=0||n.indexOf('CONNECTOR_1X4')>=0) return 'Header';
  if(n.indexOf('SUP')===0||n.indexOf('SPACER')>=0) return 'Spacer';
  if(/^H\d/.test(nm)||n.indexOf('STANDOFF')>=0) return 'Standoffs';
  return null;
}
function classify(obj,groups){
  var mod=moduleOf(obj.name);
  if(mod){ (groups[mod]=groups[mod]||[]).push(obj); return; }  // anchor: whole subtree is this module
  if(obj.isMesh){ (groups['Board']=groups['Board']||[]).push(obj); }
  for(var i=0;i<obj.children.length;i++) classify(obj.children[i],groups);
}
var PART_ORDER=['Board','Carrier','XIAO','Thermal sensor','Header','Spacer','Standoffs','Enclosure','Cover'];
function buildParts(root){
  var groups={}; classify(root,groups);
  var panel=document.getElementById('parts'); panel.innerHTML='';
  var keys=Object.keys(groups);
  if(keys.length<2){ panel.classList.add('hide'); return; }   // nothing meaningful to toggle
  keys.sort(function(a,b){ var ia=PART_ORDER.indexOf(a),ib=PART_ORDER.indexOf(b); return (ia<0?99:ia)-(ib<0?99:ib); });
  var head=document.createElement('div'); head.className='ptitle';
  var t=document.createElement('span'); t.textContent='Parts';
  var all=document.createElement('a'); all.textContent='all'; head.appendChild(t); head.appendChild(all);
  panel.appendChild(head);
  var boxes=[];
  keys.forEach(function(k){
    var row=document.createElement('label'); row.className='prow';
    var cb=document.createElement('input'); cb.type='checkbox'; cb.checked=true; boxes.push(cb);
    cb.addEventListener('change',function(){ groups[k].forEach(function(o){ o.visible=cb.checked; }); });
    var sp=document.createElement('span'); sp.textContent=k;
    row.appendChild(cb); row.appendChild(sp); panel.appendChild(row);
  });
  all.addEventListener('click',function(){
    var any=boxes.some(function(b){ return !b.checked; }); // if any hidden -> show all, else hide all
    boxes.forEach(function(b,i){ b.checked=any; b.dispatchEvent(new Event('change')); });
    all.textContent=any?'none':'all';
  });
  panel.classList.remove('hide');
}

function shade(root,mode){
  root.traverse(function(o){
    if(!o.isMesh) return;
    o.castShadow=true; o.receiveShadow=true;
    if(mode==='cad'){   // untinted CAD STEP -> the matte light-grey CAD surface
      o.material=new THREE.MeshPhysicalMaterial({color:'#f4f4f5',roughness:0.92,metalness:0.03,clearcoat:0,envMapIntensity:0.6});
    }
    var pos=o.geometry&&o.geometry.attributes&&o.geometry.attributes.position;
    if(pos&&pos.count<160000){   // crisp feature-edge overlay (skip very dense meshes e.g. fine copper)
      var eg=new THREE.EdgesGeometry(o.geometry,16);
      var ls=new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:'#18181b',transparent:true,opacity:0.84}));
      ls.renderOrder=2; o.add(ls);
    }
  });
}
var userMoved=false;
controls.addEventListener('start',function(){ userMoved=true; });
function frame(obj){
  // recenter the model to the world origin first — GLBs arrive at wildly different
  // offsets (the PCB export sits at its KiCad board coordinates, ~0.1 m off origin),
  // which would otherwise leave it tiny/off-screen.
  var box=new THREE.Box3().setFromObject(obj);
  var c=box.getCenter(new THREE.Vector3());
  obj.position.sub(c); box.setFromObject(obj);
  var size=box.getSize(new THREE.Vector3());
  var r=Math.max(size.length()*0.5,1e-4);
  controls.target.set(0,0,0);
  camera.position.set(0,0,0).add(new THREE.Vector3(1,-1,0.75).normalize().multiplyScalar(r*2.4));
  camera.near=r/100; camera.far=r*100; camera.updateProjectionMatrix(); controls.update();
  if(ground){ scene.remove(ground); ground.geometry.dispose(); ground.material.dispose(); }
  var g=new THREE.Mesh(new THREE.PlaneGeometry(r*8,r*8),new THREE.ShadowMaterial({opacity:0.18}));
  g.position.set(0,0,box.min.z-r*0.002); g.receiveShadow=true; scene.add(g); ground=g;
}
var token=0, lastFitW=0;
function load(url,mode){
  clear(); if(!url) return; var my=++token; userMoved=false; lastFitW=0;
  loader.load(url,function(g){ if(my!==token) return; shade(g.scene,mode); scene.add(g.scene); current=g.scene; buildParts(g.scene); },null,
    function(){ if(my===token) host.querySelector('.note').textContent='failed to load model'; });
}
function resize(){ var w=host.clientWidth||1,h=host.clientHeight||1; renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(host); resize();
renderer.setAnimationLoop(function(){
  // auto-fit every frame until the user first orbits — bulletproof against panes that
  // start at 0×0 (hidden tabs / offscreen render) and only get a real size later.
  if(current && !userMoved){ var w=host.clientWidth; if(w>0 && w!==lastFitW){ lastFitW=w; resize(); frame(current); } }
  controls.update(); renderer.render(scene,camera);
});

// ── tabs: PCB 2D = KiCanvas · the four 3D tabs = this renderer (mode pcb|cad) ──────────
var tabs=document.getElementById('tabs'), p2d=document.getElementById('p2d'), p3d=document.getElementById('p3d'), psch=document.getElementById('psch');
[].forEach.call(tabs.querySelectorAll('button[data-src]'),function(b){ if(!b.dataset.src) b.disabled=true; });
var curSrc=null;
function setv(v){
  var btn=tabs.querySelector('button[data-v="'+v+'"]'); if(!btn||btn.disabled) return;
  [].forEach.call(tabs.children,function(b){ b.classList.toggle('on',b===btn); });
  var isSch=(v==='sch'), is2d=(v==='2d'), is3d=!isSch&&!is2d;
  if(psch) psch.classList.toggle('hide',!isSch);
  p2d.classList.toggle('hide',!is2d); p3d.classList.toggle('hide',!is3d);
  if(is3d){ resize(); if(btn.dataset.src!==curSrc){ curSrc=btn.dataset.src; load(curSrc,btn.dataset.mode); } }
}
[].forEach.call(tabs.children,function(b){ b.addEventListener('click',function(){ setv(b.dataset.v); }); });
addEventListener('keydown',function(e){ var bs=tabs.querySelectorAll('button'), i=parseInt(e.key,10)-1; if(i>=0&&i<bs.length&&!bs[i].disabled) setv(bs[i].dataset.v); });
setv('2d');
</script></body></html>
HTML

# ── serve from the PRODUCT ROOT so /pcb/... /cad/... /view/... all resolve ────────────
old=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
[ -n "$old" ] && { echo "freeing port $PORT (pid $old)"; kill $old 2>/dev/null || true; sleep 1; }
SCHLBL=""; [ -n "$SCH_BTN" ] && SCHLBL=" | Schematic"
echo "codesign view ($NAME $REV) -> http://127.0.0.1:$PORT/view/   [PCB 2D$SCHLBL | PCB 3D | Enclosure | Fit | Exploded]"
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$PROD"
