// parts.js — geometry primitives. No CSG: the body is a SKIN swept from one
// closed plan outline along one side profile, plus flat plates that can carry
// real holes. That is what lets the plan corner radius (Rc) and the edge fillet
// (Rf) be two INDEPENDENT numbers — "round in plan, thin soft edge" is exactly
// what a single-radius rounded box cannot do.
//
// Ported from the contrispeaker ID scene (src/parts.js), which is where the
// sweep/plate/lathe trio and the notes below were worked out. Algorithms
// unchanged; comments translated. Nothing product-specific came across.
//
// LOCAL FRAME (the whole device is built in it, and rotated ONCE in device.js):
//   x = board +x   ·   y = board +y (away from the user)   ·   z = height up
// which is the board contract's own frame, so a board coordinate needs no
// conversion beyond centring.
import * as THREE from 'three';

/**
 * Sample points + outward normals of a rounded rectangle (CCW, first point not
 * repeated). Radii may differ per corner, for a panel that is round on one side
 * and square on the other.
 *
 * Outlines are ALWAYS built from explicit points — never quadraticCurveTo /
 * absarc. Those subdivide by curveSegments, so a plate with a thousand rounded
 * holes becomes tens of thousands of points 0.03 mm apart, and earcut fails
 * SILENTLY at that density: holes vanish and stair-stepped shards appear.
 */
export function rrOutline(x0, y0, x1, y1, radii, seg = 14) {
  const [rTR, rTL, rBL, rBR] = normRadii(radii, x1 - x0, y1 - y0);
  const pts = [], nrm = [];
  const corner = (cx, cy, r, a0, a1) => {
    if (r <= 1e-6) {
      pts.push(new THREE.Vector2(cx, cy));
      const a = (a0 + a1) / 2;
      nrm.push(new THREE.Vector2(Math.cos(a), Math.sin(a)));
      return;
    }
    for (let i = 0; i <= seg; i++) {
      const a = a0 + ((a1 - a0) * i) / seg;
      const nx = Math.cos(a), ny = Math.sin(a);
      pts.push(new THREE.Vector2(cx + r * nx, cy + r * ny));
      nrm.push(new THREE.Vector2(nx, ny));
    }
  };
  corner(x1 - rBR, y0 + rBR, rBR, -Math.PI / 2, 0);          // CCW from bottom-right
  corner(x1 - rTR, y1 - rTR, rTR, 0, Math.PI / 2);
  corner(x0 + rTL, y1 - rTL, rTL, Math.PI / 2, Math.PI);
  corner(x0 + rBL, y0 + rBL, rBL, Math.PI, (Math.PI * 3) / 2);
  return { pts, nrm };
}

function normRadii(radii, w, h) {
  const r = Array.isArray(radii) ? radii.slice() : [radii, radii, radii, radii];
  const lim = Math.min(w, h) / 2;
  return r.map(v => Math.max(0, Math.min(v, lim)));
}

export const rrPoints = (cx, cy, w, h, r, seg = 10) =>
  rrOutline(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, r, seg).pts;

export function circlePoints(cx, cy, r, seg = 48) {
  const pts = [];
  for (let i = 0; i < seg; i++) {
    const a = (i / seg) * Math.PI * 2;
    pts.push(new THREE.Vector2(cx + r * Math.cos(a), cy + r * Math.sin(a)));
  }
  return pts;
}

export function stadiumPoints(cx, cy, w, h, seg = 14) {
  const r = h / 2, sx = w / 2 - r, pts = [];
  for (let i = 0; i <= seg; i++) { const a = -Math.PI / 2 + Math.PI * i / seg; pts.push(new THREE.Vector2(cx + sx + r * Math.cos(a), cy + r * Math.sin(a))); }
  for (let i = 0; i <= seg; i++) { const a = Math.PI / 2 + Math.PI * i / seg; pts.push(new THREE.Vector2(cx - sx + r * Math.cos(a), cy + r * Math.sin(a))); }
  return pts;
}

/**
 * Sweep a side profile along a closed plan outline to make the body skin.
 * Each profile entry is { r, z, nr, nz }: r is the offset along the outline's
 * outward normal (negative = inward), z the height, and (nr, nz) the normal
 * split between "outward" and "up". So "top fillet → side wall → bottom fillet"
 * is ONE continuous profile and the seams do not exist mathematically.
 *
 * UVs are in MILLIMETRES of arc length, never normalised: every part shares one
 * grain scale, and normalised UVs stretch that grain into a weave on long thin
 * faces.
 */
export function sweep(outline, profile, closed = true) {
  const { pts, nrm } = outline;
  const n = pts.length, m = profile.length;
  const pos = new Float32Array(n * m * 3), nor = new Float32Array(n * m * 3), uv = new Float32Array(n * m * 2);
  const s = [0];
  for (let i = 1; i < n; i++) s.push(s[i - 1] + pts[i].distanceTo(pts[i - 1]));
  const pz = [0];
  for (let j = 1; j < m; j++)
    pz.push(pz[j - 1] + Math.hypot(profile[j].r - profile[j - 1].r, profile[j].z - profile[j - 1].z));

  for (let i = 0; i < n; i++) {
    const p = pts[i], nv = nrm[i];
    for (let j = 0; j < m; j++) {
      const pr = profile[j], k = (i * m + j) * 3;
      pos[k] = p.x + nv.x * pr.r; pos[k + 1] = p.y + nv.y * pr.r; pos[k + 2] = pr.z;
      const len = Math.hypot(pr.nr, pr.nz) || 1;
      nor[k] = (nv.x * pr.nr) / len; nor[k + 1] = (nv.y * pr.nr) / len; nor[k + 2] = pr.nz / len;
      const t = (i * m + j) * 2; uv[t] = s[i]; uv[t + 1] = pz[j];
    }
  }
  const idx = [], last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) {
    const i2 = (i + 1) % n;
    for (let j = 0; j < m - 1; j++) {
      const a = i * m + j, b = a + 1, c = i2 * m + j, d = c + 1;
      idx.push(a, b, c, c, b, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/**
 * The body skin's side profile: top flat → top fillet → side wall → bottom
 * fillet → bottom flat, for a slab of height H sitting with its base at z = z0.
 * The middle entry gives the parting line somewhere to be shaded.
 */
export function slabProfile(H, Rf, z0 = 0, seg = 12) {
  const prof = [], top = z0 + H - Rf, bot = z0 + Rf;
  for (let i = 0; i <= seg; i++) {
    const phi = (Math.PI / 2) * (1 - i / seg);
    prof.push({ r: -Rf * (1 - Math.cos(phi)), z: top + Rf * Math.sin(phi), nr: Math.cos(phi), nz: Math.sin(phi) });
  }
  prof.push({ r: 0, z: z0 + H / 2, nr: 1, nz: 0 });
  for (let i = 0; i <= seg; i++) {
    const phi = (Math.PI / 2) * (i / seg);
    prof.push({ r: -Rf * (1 - Math.cos(phi)), z: bot - Rf * Math.sin(phi), nr: Math.cos(phi), nz: -Math.sin(phi) });
  }
  return prof;
}

/**
 * Extrude a 2D shape into a plate of `thickness`. Caps land in material slot 0,
 * side walls in slot 1 — which is free and is exactly what a hole needs: give
 * the wall its own darker material, because off-axis you mostly see the WALL of
 * an opening, not the space behind it, and a body-coloured wall catches the key
 * light and reads as a raised white square.
 * Outer face at z = 0, thickness toward -z.
 */
export function plate(shape, thickness, bevel = 0) {
  const opt = { depth: thickness, bevelEnabled: false, curveSegments: 6 };
  if (bevel > 0) Object.assign(opt, { bevelEnabled: true, bevelSize: bevel, bevelThickness: bevel * 0.8, bevelSegments: 5 });
  const g = new THREE.ExtrudeGeometry(shape, opt);
  g.translate(0, 0, -thickness);
  return g;
}

/**
 * A solid of revolution about +Z. profile is a list of [r, z].
 *
 * NOT THREE.LatheGeometry: that turns about Y, and which side the normals face
 * is decided implicitly by point order — reverse the order and the part simply
 * DISAPPEARS (back-face culled) with no error. Normals are explicit here:
 * tangent (dr, dz) → normal (-dz, dr), so writing the profile "outward from the
 * axis, then downward" gives outward/upward faces.
 */
export function lathe(profile, seg = 96) {
  const n = profile.length;
  const pos = new Float32Array(n * (seg + 1) * 3), nor = new Float32Array(n * (seg + 1) * 3), uv = new Float32Array(n * (seg + 1) * 2);
  const nr = [], nz = [];
  for (let i = 0; i < n; i++) {
    const a = profile[Math.max(0, i - 1)], b = profile[Math.min(n - 1, i + 1)];
    const dr = b[0] - a[0], dz = b[1] - a[1], L = Math.hypot(dr, dz) || 1;
    nr.push(-dz / L); nz.push(dr / L);
  }
  const arc = [0];
  for (let i = 1; i < n; i++) arc.push(arc[i - 1] + Math.hypot(profile[i][0] - profile[i - 1][0], profile[i][1] - profile[i - 1][1]));
  for (let i = 0; i < n; i++) {
    const [r, z] = profile[i];
    for (let j = 0; j <= seg; j++) {
      const th = (j / seg) * Math.PI * 2, c = Math.cos(th), s = Math.sin(th);
      const k = (i * (seg + 1) + j) * 3;
      pos[k] = r * c; pos[k + 1] = r * s; pos[k + 2] = z;
      nor[k] = nr[i] * c; nor[k + 1] = nr[i] * s; nor[k + 2] = nz[i];
      const t = (i * (seg + 1) + j) * 2; uv[t] = th * Math.max(r, 0.5); uv[t + 1] = arc[i];
    }
  }
  const idx = [];
  for (let i = 0; i < n - 1; i++) for (let j = 0; j < seg; j++) {
    const a = i * (seg + 1) + j, b = (i + 1) * (seg + 1) + j;
    idx.push(a, b, a + 1, a + 1, b, b + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/** A rounded-rect sink: floor + walls, opening toward +z. */
export function recess(w, h, r, depth, seg = 10) {
  const outline = rrOutline(-w / 2, -h / 2, w / 2, h / 2, r, seg);
  const wall = sweep(outline, [{ r: 0, z: 0, nr: -1, nz: 0 }, { r: 0, z: -depth, nr: -1, nz: 0 }]);
  const floor = new THREE.ShapeGeometry(new THREE.Shape(outline.pts));
  floor.translate(0, 0, -depth);
  return mergeGeometries([wall, floor]);
}

/** Minimal merge (position / normal / uv + index). */
export function mergeGeometries(geos) {
  let vCount = 0, iCount = 0;
  for (const g of geos) { vCount += g.attributes.position.count; iCount += g.index ? g.index.count : g.attributes.position.count; }
  const pos = new Float32Array(vCount * 3), nor = new Float32Array(vCount * 3), uv = new Float32Array(vCount * 2), idx = new Uint32Array(iCount);
  let vo = 0, io = 0;
  for (const g of geos) {
    const c = g.attributes.position.count;
    pos.set(g.attributes.position.array, vo * 3);
    if (g.attributes.normal) nor.set(g.attributes.normal.array, vo * 3);
    if (g.attributes.uv) uv.set(g.attributes.uv.array, vo * 2);
    if (g.index) { const gi = g.index.array; for (let k = 0; k < gi.length; k++) idx[io + k] = gi[k] + vo; io += gi.length; }
    else { for (let k = 0; k < c; k++) idx[io + k] = k + vo; io += c; }
    vo += c;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  out.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  out.setIndex(new THREE.BufferAttribute(idx, 1));
  // Deliberately NOT computeVertexNormals: each piece computed its own (fillet
  // and flat agree exactly at the tangent, the parting groove is a hard edge).
  // Recomputing destroys both at once.
  return out;
}

export function mesh(geo, mat, pos = [0, 0, 0], name = '') {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(...pos); m.name = name;
  m.castShadow = true; m.receiveShadow = true;
  return m;
}
