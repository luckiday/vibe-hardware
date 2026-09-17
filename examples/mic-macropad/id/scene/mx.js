// mx.js — the two standard parts, built from published dimensions rather than
// eyeballed boxes. KiCad ships no 3D model for Button_Switch_Keyboard (the
// keyboard lands are copper-only), so there is nothing authoritative to import;
// these are generated from the datasheet numbers instead, which is also what the
// repo asks for — sources are generators, not binaries.
//
// Cherry MX (MX1A), PCB-mount:
//   bottom housing 14.0 sq, top housing 15.6 sq tapering to ~12.4 at the crown
//   crown 11.6 mm above the PCB · stem cross 4.1 × 1.17 mm, 3.6 mm above the crown
//   plate cut-out 14.0 sq  ← which is exactly windows.key*.dia in the board contract
//
// Keycap: XDA/MA-family uniform profile — 18.0 mm square base, 15.4 mm top,
// 8.6 mm tall, spherical top dish. (DSA's 12.7 mm top was tried first and reads
// as a lampshade in the side elevation; XDA is the near-vertical wall the
// owner's sheet shows.) The TAPER is still the point: adjacent 1u caps on
// 19.05 mm centres are 1.05 mm apart at the base but 3.7 mm apart at the top,
// which is where the eye reads the gap. That is how a real board gets its
// spacing, and why shrinking the cap to fake it was the wrong fix.
import * as THREE from 'three';
import { rrPoints } from './parts.js';

// Loft between two rounded-rect rings, then close the top with a spherical dish.
function loft(baseW, topW, h, rBase, rTop, dish, seg = 10) {
  const ring = (w, r) => rrPoints(0, 0, w, w, r, seg);
  const a = ring(baseW, rBase), b = ring(topW, rTop);
  const n = Math.min(a.length, b.length);
  const pos = [], idx = [];
  const push = (x, y, z) => (pos.push(x, y, z), pos.length / 3 - 1);

  const lo = [], hi = [];
  for (let i = 0; i < n; i++) {
    lo.push(push(a[i].x, a[i].y, 0));        // local frame: x, y plan · z up
    hi.push(push(b[i].x, b[i].y, h));
  }
  // Winding matters and fails silently: with the ring CCW in xy and z up, the
  // outward face is (lo[i], lo[j], hi[i]). Reverse it and three.js culls the
  // OUTSIDE of the cap, so you see straight through to its far inner wall — it
  // reads as a splayed tent, not as an inverted normal.
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    idx.push(lo[i], lo[j], hi[i], lo[j], hi[j], hi[i]);
  }
  // dish: one intermediate ring + a centre, so the crown is spherical rather
  // than a cone. z(r) = dish * r^2 keeps it smooth at the centre.
  const mid = [], k = 0.55;
  for (let i = 0; i < n; i++)
    mid.push(push(b[i].x * k, b[i].y * k, h - dish * (1 - k * k)));
  const c = push(0, 0, h - dish);
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    idx.push(hi[i], hi[j], mid[i], hi[j], mid[j], mid[i]);
    idx.push(mid[i], mid[j], c);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

export const MX = {
  bodyLower: 14.0, bodyUpper: 15.6, crownW: 12.4,
  lowerH: 5.0, upperH: 6.6, height: 11.6,      // 5.0 + 6.6 = 11.6 above the PCB
  stemArm: 4.1, stemThk: 1.17, stemH: 3.6,
  capBase: 18.0, capTop: 15.4, capH: 8.6, capDish: 0.8, capRb: 1.2, capRt: 2.4,
};

// bottom housing (dark) + tapered top housing (clear) + the cross stem
export function mxSwitch(matBase, matTop, matStem) {
  const g = new THREE.Group(); g.name = 'mx-switch';
  const lower = new THREE.Mesh(loft(MX.bodyLower, MX.bodyLower, MX.lowerH, 0.6, 0.6, 0), matBase);
  lower.name = 'switch-base'; g.add(lower);
  const upper = new THREE.Mesh(loft(MX.bodyUpper, MX.crownW, MX.upperH, 0.8, 1.2, 0), matTop);
  upper.name = 'switch-housing'; upper.position.z = MX.lowerH; g.add(upper);
  for (const [w, d] of [[MX.stemArm, MX.stemThk], [MX.stemThk, MX.stemArm]]) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(w, d, MX.stemH), matStem);
    s.name = 'switch-stem'; s.position.z = MX.height + MX.stemH / 2; g.add(s);
  }
  g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return g;
}

export function keycap(mat) {
  const m = new THREE.Mesh(
    loft(MX.capBase, MX.capTop, MX.capH, MX.capRb, MX.capRt, MX.capDish), mat);
  m.name = 'keycap'; m.castShadow = true; m.receiveShadow = true;
  return m;
}
