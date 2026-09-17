// main.js — renderer, the interactive loop, and the export loop.
//
// Automation entry points (all of them trigger from setTimeout, never rAF: a
// background tab suspends rAF and the image simply never appears, with no error):
//   ?sheet=1&save=1&scale=2   contact sheet   → out/sheet.png
//   ?shot=1&view=hero&save=1  one camera      → out/shot-<view>.png
//   ?glb=1                    GLB for Blender → out/mic-macropad.glb
//   ?fresh=1                  ignore stored slider deltas
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { GLTFExporter } from './vendor/GLTFExporter.js';
import { P } from './params.js';
import { buildDevice, capTopY } from './device.js';
import { buildStudio } from './studio.js';
import { applyView, VIEWS } from './views.js';
import { renderSheet, saveCanvas } from './sheet.js';

const q = new URLSearchParams(location.search);
const canvas = document.getElementById('c');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;   // Khronos PBR Neutral, matching
renderer.toneMappingExposure = 1.0;                // the Blender side. NOT AgX.
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
buildStudio(scene, renderer);

const device = buildDevice();
scene.add(device);

const cam = new THREE.PerspectiveCamera(30, 1, 1, 2000);
const controls = new OrbitControls(cam, canvas);
controls.target.set(0, capTopY() / 2, 0);
controls.enableDamping = true;

let exporting = false;   // any multi-frame render sets this; the rAF loop then
                         // returns early instead of re-applying its own camera

function resize() {
  const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
  renderer.setSize(w, h, false);
  cam.aspect = w / h; cam.updateProjectionMatrix();
}
addEventListener('resize', resize);

function loop() {
  requestAnimationFrame(loop);
  if (exporting) return;
  controls.update();
  renderer.render(scene, cam);
}

async function exportGLB() {
  // three.js is mm, glTF is m → the Blender side imports at 0.001. Front ends
  // up facing -Y there.
  const ex = new GLTFExporter();
  const buf = await ex.parseAsync(device, { binary: true });
  await fetch('/save?name=mic-macropad.glb', { method: 'POST', body: new Blob([buf]) });
  return 'out/mic-macropad.glb';
}
window.ID = { P, exportGLB, scene, device, renderer, cam };

resize();
applyView(cam, 'hero', (canvas.clientWidth || 1) / (canvas.clientHeight || 1));
controls.target.set(0, capTopY() / 2, 0);
loop();

// ---- export loop -----------------------------------------------------------
setTimeout(async () => {
  const scale = Number(q.get('scale') || 2);
  if (q.get('sheet')) {
    exporting = true;
    const c = renderSheet({ renderer, scene, cam, scale });
    if (q.get('save')) await saveCanvas(c, 'sheet.png');
    document.body.appendChild(Object.assign(c, { className: 'result' }));
    exporting = false; resize();
    document.title = 'sheet ready';
  } else if (q.get('shot')) {
    exporting = true;
    const view = q.get('view') || 'hero';
    renderer.setSize(1400 * scale / 2, 1000 * scale / 2, false);
    applyView(cam, view, 1.4);
    renderer.render(scene, cam);
    if (q.get('save')) await saveCanvas(renderer.domElement, `shot-${view}.png`);
    exporting = false; resize();
    document.title = `shot ${view} ready`;
  } else if (q.get('glb')) {
    document.title = await exportGLB();
  }
}, 400);

// ---- a small readout so the review is against numbers, not vibes ------------
document.getElementById('hud').textContent =
  [`${P.W} × ${P.D} × ${P.H} mm   (aspect ${(P.W / P.D).toFixed(3)})`,
   `board 76 × 56 · bezel ${(P.W - 76) / 2} / ${(P.D - 56) / 2} mm`,
   `caps top out at ${capTopY().toFixed(1)} mm`,
   `views: ${Object.keys(VIEWS).join(' · ')}`].join('\n');
