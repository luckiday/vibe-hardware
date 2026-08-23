// device.js — numbers → geometry. Nothing invents a dimension; every value comes
// from params.js, or from mx.js for the two standard parts.
//
// Construction: the body is a SKIN swept from the plan outline along one side
// profile (so Rc and Rf are independent), closed by a TOP PLATE that carries the
// key tray as a real hole and a BOTTOM PLATE that carries the mic port as a real
// hole. Side apertures are recess() inserts — the skin is a continuous sweep and
// cannot take a hole; a sunk insert with a dark wall reads the same and is what
// a real recessed receptacle looks like anyway.
//
// Built in the BOARD's frame (x right, y away from the user, z up) and rotated
// once at the end into three.js's y-up world.
import * as THREE from 'three';
import { P, bx, by, boardTopZ } from './params.js';
import { rrOutline, rrPoints, circlePoints, stadiumPoints, sweep, slabProfile,
         plate, recess, mesh } from './parts.js';
import { M } from './materials.js';
import { MX, mxSwitch, keycap } from './mx.js';
import { USBC, usbcReceptacle, WALL_ROT } from './usbc.js';

export const SPLIT_Z = 9;      // [eye] the horizontal parting line. Kept BELOW
                               // the USB opening on purpose — an aperture that
                               // straddles a seam is an aperture in two parts.

const HW = () => P.W / 2, HD = () => P.D / 2;
const shape = (pts, holes = []) => {
  const s = new THREE.Shape(pts);
  for (const h of holes) s.holes.push(new THREE.Path(h));
  return s;
};

// derived — never stored.
// The key row is centred on the BOARD, not on the shell. Those were the same
// number until the board moved hard left for the USB (R5); anything that still
// says "centred on 0" is now 5.5 mm out, and in plan that reads as the tray
// having drifted off the keys.
const keyCX = () => bx(P.boardW / 2);
const keyX = i => keyCX() + (i - 1) * P.keyPitch;
const trayHalf = () => P.keyPitch + MX.capBase / 2 + P.trayMargin;
const trayX0 = () => keyCX() - trayHalf();
const trayX1 = () => keyCX() + trayHalf();
const trayY0 = () => by(P.keyY) - MX.capBase / 2 - P.trayMargin;
const trayY1 = () => by(P.keyY) + MX.capBase / 2 + P.trayMargin;
const trayPts = () => rrOutline(trayX0(), trayY0(), trayX1(), trayY1(), P.trayR, 12).pts;

function body(g) {
  const outline = rrOutline(-HW(), -HD(), HW(), HD(), P.Rc, 20);

  // the skin, footH → H, filleted at both ends
  g.add(mesh(sweep(outline, slabProfile(P.H - P.footH, P.Rf, P.footH)), M.shell, [0, 0, 0], 'shell'));

  // The parting line. It sits 0.02 mm PROUD, not inset: the skin is one closed
  // sweep with no groove cut in it, so an inset band is simply hidden behind the
  // skin — the same reason the bores had to come outward. And a groove with no AO
  // is invisible under soft light anyway, so it earns a darker material rather
  // than an occlusion pass.
  g.add(mesh(sweep(outline, [
    { r: 0.02, z: SPLIT_Z + 0.35, nr: 1, nz: 0 },
    { r: 0.02, z: SPLIT_Z - 0.35, nr: 1, nz: 0 }]),
    M.groove, [0, 0, 0], 'split-line'));

  // TOP PLATE with the key tray as a REAL hole. The plate is inset by Rf because
  // that is where the swept skin's top fillet ends.
  const topIn = rrOutline(-HW() + P.Rf, -HD() + P.Rf, HW() - P.Rf, HD() - P.Rf, Math.max(0.5, P.Rc - P.Rf), 20).pts;
  const top = plate(shape(topIn, [trayPts()]), 1.4);
  top.translate(0, 0, P.H);
  g.add(mesh(top, [M.shell, M.cavityWall], [0, 0, 0], 'top-plate'));

  // tray walls + floor, sunk from the top face
  // 0.2 mm smaller than the plate's hole so the two walls NEST instead of being
  // coplanar — coincident walls z-fight into a white hairline that reads as a
  // modelling gap around the tray.
  const tr = recess(trayX1() - trayX0() - 0.2, trayY1() - trayY0() - 0.2, P.trayR, P.H - P.trayFloorZ, 12);
  tr.translate((trayX0() + trayX1()) / 2, (trayY0() + trayY1()) / 2, P.H);
  g.add(mesh(tr, M.tray, [0, 0, 0], 'tray'));

  // BOTTOM PLATE with the mic port as a REAL hole — windows.mic_port is a hole
  // in the FLOOR, because the ICS-43434 is a bottom-port part.
  const botIn = rrOutline(-HW() + P.Rf, -HD() + P.Rf, HW() - P.Rf, HD() - P.Rf, Math.max(0.5, P.Rc - P.Rf), 20).pts;
  const bot = plate(shape(botIn, [circlePoints(bx(P.micBoardX), by(P.micBoardY), P.micPortDia / 2, 20)]), 1.4);
  bot.rotateX(Math.PI);                       // face down
  bot.translate(0, 0, P.footH);
  g.add(mesh(bot, [M.shell, M.cavityWall], [0, 0, 0], 'bottom-plate'));

  // feet — not decoration: the floor port has to stand clear of the desk (R1)
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    const f = new THREE.Mesh(new THREE.CylinderGeometry(P.footR, P.footR * 0.9, P.footH, 28), M.foot);
    f.rotation.x = Math.PI / 2;
    f.position.set(sx * (HW() - P.footInset), sy * (HD() - P.footInset), P.footH / 2);
    f.name = 'foot'; f.castShadow = true; f.receiveShadow = true; g.add(f);
  }
}

function keys(g) {
  const z0 = boardTopZ();
  for (let i = 0; i < 3; i++) {
    const x = keyX(i), y = by(P.keyY);
    const sw = mxSwitch(M.swBase, M.sw, M.swStem);
    sw.position.set(x, y, z0); g.add(sw);

    const cap = keycap(M.cap);
    cap.position.set(x, y, z0 + MX.height + P.capLift); g.add(cap);

    // one dot per cap — the entire legend. The three keys' functions are not
    // decided (firmware is a stub), and a dot commits to nothing (report Q2).
    const d = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.6, 0.3, 32), [M.blue, M.red, M.black][i]);
    d.rotation.x = Math.PI / 2;
    d.position.set(x, y, z0 + MX.height + P.capLift + MX.capH - MX.capDish + 0.05);
    d.name = 'cap-dot'; g.add(d);
  }
}

// A Mondrian block: a thin inlay just proud of the face. Every block names what
// is underneath it — that is the whole scheme, and why none of them is decoration.
// The inset is Rf, the SAME number the top plate uses, because that is where the
// swept skin's top fillet ends and the flat top face begins. Any smaller and the
// block overhangs the fillet — in plan it reads as a sticker peeling off the edge.
function blockTop(g, x0, x1, y0, y1, mat, r, name) {
  const i = P.Rf, cl = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const pts = rrOutline(cl(x0, -HW() + i, HW() - i), cl(y0, -HD() + i, HD() - i),
                        cl(x1, -HW() + i, HW() - i), cl(y1, -HD() + i, HD() - i), r, 14).pts;
  const p = plate(shape(pts), 0.45); p.translate(0, 0, P.H + 0.05);
  g.add(mesh(p, [mat, mat], [0, 0, 0], name));
}
function blockSide(g, mat, w, d, h, pos, name) {
  const b = new THREE.BoxGeometry(w, d, h);
  g.add(mesh(b, mat, pos, name));
}

function mondrian(g) {
  const blueX1 = -HW() + P.blockBlueW;
  // NOTE: the owner's sheet wraps its colour blocks over the edges. A flat plate
  // cannot follow an edge fillet, and a "wrap" built from a top plate plus a side
  // plate leaves a 1.6 mm band of bare fillet between them that reads as a
  // misprint. These are flat top-face fields instead; a true wrap wants a partial
  // sweep along the outline, which is a v3 job. (report §1.3)

  // BLUE — the rear band. Its near edge is board y 52.75: the leading edge of
  // Espressif's antenna keepout. The one strip that may never carry metal is the
  // one strip that carries the colour. (report R2)
  blockTop(g, -HW(), blueX1, P.rearBandY, HD(), M.blue, [0, P.Rc - P.Rf, 0, 0], 'block-blue-top');

  // RED — the right service strip: reset (y -4) and boot (y -11) live under it.
  blockTop(g, P.stripX, HW(), P.blockRedY0, P.blockRedY1, M.red, 0, 'block-red-top');

  // YELLOW — the front band. The mic slot and the indicator are under it, and
  // its rear edge IS the tray's front wall: the Mondrian line and the tray edge
  // are the same line, not two lines 1 mm apart.
  blockTop(g, P.blockYellowX, P.stripX, -HD(), trayY0(), M.yellow, 0, 'block-yellow-top');

  // BLUE again, low on the front-left: the front elevation needs weight on the
  // left or the whole face leans right.
  blockSide(g, M.blue, 16, 0.5, 4.0, [-HW() + P.Rc + 8, -HD() + 0.19, 5.0], 'block-blue-front');
}

// Apertures.
//
// The body is a continuous swept skin, and a sweep cannot take a hole — so an
// opening is MODELLED rather than cut: an unlit dark face sitting 0.06 mm proud
// of the skin, with the plate's own extruded wall (material slot 1) behind it.
// Two rules make that read as an opening rather than as a printed dot:
//   - the face must be UNLIT (MeshBasicMaterial). With a lit material the fill
//     light reaches it and every hole fills with a pale disc — a vent field that
//     renders as white tiles printed on the shell.
//   - the WALL gets its own dark material, because off-axis you mostly see the
//     wall of an opening, not the space behind it.
// vibe-cad cuts the real hole from the same params; this is appearance only.
// (A true cut wants the outline's straight runs rebuilt as flat plates — the
// contrispeaker scene does that with runPanel(); it is a v3 job here.)
function bore(g, pts, mat, pos, rot, name, depth = 1.2) {
  const p = plate(shape(pts), depth);
  const m = mesh(p, [mat, M.cavityWall], pos, name);
  if (rot) m.rotation.set(...rot);
  m.castShadow = false;
  g.add(m); return m;
}

function apertures(g) {
  const z0 = boardTopZ(), out = 0.06;
  // the receptacle sits ON the board, so its centreline is half a shell height
  // above the board's top face — not an eyeballed height up the wall
  const usbZ = z0 + USBC.shellH / 2;
  // plate() extrudes toward -z, so each face is turned to look OUT of its wall.
  const R = { left: [0, -Math.PI / 2, 0], right: [0, Math.PI / 2, 0], front: [Math.PI / 2, 0, 0] };

  // USB-C, LEFT wall, board y 36 — rear of centre so the cable leaves away from
  // the typing hand. Not centred, and not to be centred for looks.
  // The real receptacle, from usbc.js: its face has to reach the OUTER surface
  // or no plug bottoms out, which is exactly why the board sits hard left (R5).
  // depthScale: the skin has no hole, so only what sits OUTSIDE it is visible.
  // 0.004 squeezes the 6.5 mm cavity into 26 µm, which keeps the shapes and the
  // dark mouth while leaving nothing buried. See the note in usbc.js.
  const usb = usbcReceptacle(M.usbShell, M.cavity, M.usbTongue, { depthScale: 0.004 });
  usb.position.set(-HW() - 0.03, by(P.usbBoardY), usbZ);
  usb.rotation.set(...WALL_ROT.left);
  g.add(usb);

  // reset + boot, RIGHT wall. Small, round, sunk: they must never be confusable
  // with the three keys, so a different face, a different shape, and a bore you
  // press with a fingernail rather than with a finger.
  for (const [b, nm] of [[P.btnResetY, 'reset'], [P.btnBootY, 'boot']])
    bore(g, circlePoints(0, 0, P.btnDia / 2, 28), M.cavity,
      [HW() + out, by(b), P.btnSinkZ], R.right, nm, 1.6);

  // indicator. D4 sits at board x 66.5; the ID wants the dot at the front-right,
  // inside the service strip. 4.5 mm of lateral run in a moulded light pipe buys
  // that without a board respin (report R3).
  const pipe = new THREE.Mesh(new THREE.CylinderGeometry(P.ledDia / 2, P.ledDia / 2, 0.9, 32), M.led);
  pipe.rotation.x = Math.PI / 2;
  pipe.position.set(bx(P.ledExitX), -HD() - 0.1, P.ledZ);
  pipe.name = 'led-pipe'; pipe.castShadow = false; g.add(pipe);

  // mic. The Ø1.5 floor port is vented to this slot on the front edge, so the
  // device does not have to listen through the desk (report R1). The slot does
  // NOT sit under the port: at board x 68.5 it would land 2.5 mm from the
  // indicator and the two would read as one smudge. The channel runs sideways
  // under the floor — it has to be a channel either way, and its length is not
  // what decides the acoustics.
  bore(g, stadiumPoints(0, 0, P.micSlotW, P.micSlotH), M.cavity,
    [bx(P.micSlotX), -HD() - out, P.micSlotZ], R.front, 'mic-slot', 1.2);
}

export function buildDevice() {
  const g = new THREE.Group(); g.name = 'device';
  body(g); keys(g); mondrian(g); apertures(g);
  // The ONE frame conversion: board frame (z up, +y away from user) → three.js
  // world (y up, -z away from user).
  const root = new THREE.Group(); root.name = 'device-root';
  g.rotation.x = -Math.PI / 2;
  root.add(g);
  return root;
}

export const capTopY = () => boardTopZ() + MX.height + P.capLift + MX.capH;
