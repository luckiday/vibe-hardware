// views.js — six FIXED cameras, framed by "how much must fit" (fitW/fitH) rather
// than by fov, so changing a dimension never re-frames the sheet. Top and bottom
// follow third-angle projection, so left/right in those strips match the front —
// those are the strips people hold against the board.
import * as THREE from 'three';
import { P } from './params.js';
import { capTopY } from './device.js';

const CY = () => capTopY() / 2;          // vertical centre of the whole device

export const VIEWS = {
  front:  { fitW: 108, fitH: 46, pos: [0, 0.3, 220],   look: [0, 0, 0], desc: 'front elevation' },
  side:   { fitW: 78,  fitH: 46, pos: [220, 0.3, 0],   look: [0, 0, 0], desc: 'right elevation' },
  back:   { fitW: 108, fitH: 46, pos: [0, 0.3, -220],  look: [0, 0, 0], desc: 'rear elevation' },
  top:    { fitW: 108, fitH: 78, pos: [0, 240, 0.001], look: [0, 0, 0], desc: 'plan (third-angle)' },
  hero:   { fitW: 124, fitH: 92, pos: [118, 96, 150],  look: [0, -2, 0], desc: 'three-quarter' },
  bottom: { fitW: 108, fitH: 78, pos: [0, -240, 0.001], look: [0, 0, 0], desc: 'underside (third-angle)' },
  // not in VIEW_ORDER — a detail camera for ?shot=1&view=left, because the one
  // aperture that has to be judged as a real part is on the left wall
  // USB-C sits at board y 36 and half a shell-height above the board: local
  // (-46.5, 8, 12.68) → world (-46.5, 12.68, -8). pos[1]/look[1] are relative to
  // the device's vertical centre, which applyView adds back.
  left:   { fitW: 34,  fitH: 22, pos: [-170, -3.2, -8], look: [-46.5, -3.2, -8], desc: 'USB-C detail' },
};

// fov from fit + aspect. Guard the aspect: a 0-height canvas gives Infinity,
// 0 * Infinity = NaN, the camera quaternion goes NaN and NEVER recovers — every
// tile blank with a clean console.
export function applyView(cam, name, aspect) {
  const v = VIEWS[name];
  const a = (Number.isFinite(aspect) && aspect > 0.01) ? aspect : 1;
  // distance from the camera to what it is LOOKING AT, not from the origin.
  // They are the same for the six product views (look = origin) and badly
  // different for any detail camera, which then frames ~20% too tight.
  const dist = Math.hypot(v.pos[0] - v.look[0], v.pos[1] - v.look[1], v.pos[2] - v.look[2]);
  const needH = Math.max(v.fitH, v.fitW / a);
  cam.fov = 2 * THREE.MathUtils.radToDeg(Math.atan((needH / 2) / dist));
  cam.aspect = a;
  cam.position.set(v.pos[0], v.pos[1] + CY(), v.pos[2]);
  cam.up.set(0, 1, 0);
  if (name === 'top') cam.up.set(0, 0, -1);        // third-angle: rear is up
  if (name === 'bottom') cam.up.set(0, 0, 1);      // third-angle: front edge up
  cam.lookAt(v.look[0], v.look[1] + CY(), v.look[2]);
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);                     // lookAt sets the quaternion only
  return cam;
}

export const VIEW_ORDER = ['hero', 'front', 'side', 'top', 'back', 'bottom'];
