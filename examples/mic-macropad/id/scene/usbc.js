// usbc.js — a reusable USB Type-C receptacle. Standard part, so it lives with
// its datasheet numbers, exactly like mx.js. Nothing in here is specific to this
// product; drop the file into another scene and it still works.
//
// The board fits Korean Hroparts TYPE-C-31-M-12 (LCSC C165948), whose KiCad land
// is `Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12`. The outer body numbers
// below are MEASURED off that footprint's F.Fab outline rather than remembered:
//
//   $ python3 - <<'EOF'   # over Connector_USB.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12.kicad_mod
//   F.Fab   x -4.47..4.47 (w 8.94)   y -3.65..3.65 (d 7.30)
//   EOF
//
// The interface numbers (cavity, tongue) come from the USB Type-C spec: the plug
// shell is 8.34 × 2.56 with a full 1.28 radius, so the receptacle cavity is a
// stadium a hair larger. A Type-C opening is never a rectangle — every corner is
// a full half-height radius, and drawing it square is the single most obvious
// tell in a render.
//
// Authored with the OPENING at z = 0 facing +z and the body running toward -z,
// which is the same convention plate()/recess() use — so the same wall rotation
// table places all three.
import * as THREE from 'three';
import { rrOutline, sweep, mergeGeometries } from './parts.js';

// Orientation helper. The part is authored with its WIDTH along x and its
// opening along +z; a side wall wants the width along the body's depth instead.
// Getting this wrong renders a portrait Type-C port, which is unmistakable and
// still easy to produce by rotating about one axis and calling it done.
export const WALL_ROT = {
  left:  [Math.PI / 2, -Math.PI / 2, 0],   // opening faces -x, width along -y
  right: [Math.PI / 2, Math.PI / 2, 0],    // opening faces +x
  front: [Math.PI / 2, 0, 0],              // opening faces -y
};

export const USBC = {
  shellW: 8.94,        // [kicad] F.Fab of the HRO land
  shellH: 3.16,        // [std]   Type-C receptacle shell height
  bodyD: 7.30,         // [kicad] F.Fab, along the insertion axis
  cavityW: 8.44,       // [std]   plug shell 8.34 + fit
  cavityH: 2.66,       // [std]   plug shell 2.56 + fit
  mateD: 6.5,          // [std]   mating depth
  tongueW: 6.80,       // [std]
  tongueT: 0.66,       // [std]
  tongueSetback: 1.10, // [std]   opening face → front of the tongue
  cutoutClear: 0.28,   // [eye]   per side, panel aperture → shell
};

const stadium = (w, h, seg = 12) => rrOutline(-w / 2, -h / 2, w / 2, h / 2, h / 2, seg);

/** Panel aperture outline for this receptacle — feed it to plate()/Shape. */
export const usbcCutout = (clear = USBC.cutoutClear) =>
  stadium(USBC.shellW + 2 * clear, USBC.shellH + 2 * clear).pts;

/**
 * The receptacle: metal shell, darkened cavity, tongue.
 * Returns a Group whose origin is the centre of the opening, opening toward +z.
 *
 * `depthScale` compresses everything along the insertion axis. Default 1 = the
 * true part. Pass a small value when the host body is a continuous swept skin
 * with no hole cut in it: everything behind the skin is hidden, so the cavity
 * and tongue have to be squeezed into the fraction of a millimetre that sits
 * OUTSIDE it. The shapes and materials stay correct — only the depth is a lie,
 * and it is a lie no camera can see at product scale. Cut a real hole (rebuild
 * that straight run as a flat plate) and this drops back to 1.
 */
export function usbcReceptacle(matShell, matCavity, matTongue, { depthScale = 1 } = {}) {
  const g = new THREE.Group(); g.name = 'usb-c';
  const k = depthScale;
  const U = { ...USBC, bodyD: USBC.bodyD * k, mateD: USBC.mateD * k, tongueSetback: USBC.tongueSetback * k };

  // outer shell — a stadium tube running back from the opening
  const shell = sweep(stadium(U.shellW, U.shellH), [
    { r: 0, z: 0, nr: 1, nz: 0 }, { r: 0, z: -U.bodyD, nr: 1, nz: 0 }]);
  // the front face: the ring between shell and cavity, at z = 0
  const ring = new THREE.Shape(stadium(U.shellW, U.shellH).pts);
  ring.holes.push(new THREE.Path(stadium(U.cavityW, U.cavityH).pts));
  const face = new THREE.ShapeGeometry(ring);
  const m = new THREE.Mesh(mergeGeometries([shell, face]), matShell);
  m.name = 'usb-shell'; m.castShadow = false; g.add(m);

  // cavity — walls facing INWARD, plus an unlit back. Both matter: off-axis you
  // see the wall of the opening, not the space behind it, and a lit back fills
  // the port with a pale blob instead of reading as a hole.
  const cav = sweep(stadium(U.cavityW, U.cavityH), [
    { r: 0, z: 0, nr: -1, nz: 0 }, { r: 0, z: -U.mateD, nr: -1, nz: 0 }]);
  const back = new THREE.ShapeGeometry(new THREE.Shape(stadium(U.cavityW, U.cavityH).pts));
  back.translate(0, 0, -U.mateD);
  const c = new THREE.Mesh(mergeGeometries([cav, back]), matCavity);
  c.name = 'usb-cavity'; c.castShadow = false; g.add(c);

  // tongue, floating on the centreline — the part that makes a Type-C port
  // recognisable at a glance
  const t = new THREE.Mesh(
    new THREE.BoxGeometry(U.tongueW, U.tongueT, Math.max(0.004, U.mateD - U.tongueSetback)), matTongue);
  t.position.z = -(U.mateD + U.tongueSetback) / 2;
  t.name = 'usb-tongue'; t.castShadow = false; g.add(t);

  return g;
}
