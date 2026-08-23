// materials.js — ONE material per part. This ledger IS the CMF spec: every
// entry names its real-world counterpart, and the report's CMF table is
// generated from the same list. Split parts = split materials.
import * as THREE from 'three';
import { P } from './params.js';

const std = (o) => new THREE.MeshStandardMaterial(o);

export const M = {
  // shell — warm off-white PC with a soft-touch feel: mid roughness, no clearcoat
  shell: std({ name: 'shell', color: P.colShell, roughness: P.roughShell, metalness: 0 }),
  // the split-line groove floor. A groove with no AO is invisible under soft
  // light, so it gets a darker material instead of an occlusion pass.
  groove: std({ name: 'groove', color: '#B9B6AE', roughness: 0.8, metalness: 0 }),
  // key tray floor. Dark on purpose: a recess whose floor catches the key light
  // stops reading as a recess, and the switches lose their silhouette.
  tray: std({ name: 'tray', color: P.colTray, roughness: 0.85, metalness: 0 }),
  cap: std({ name: 'cap', color: P.colCap, roughness: P.roughCap, metalness: 0 }),
  // A real MX is two parts and it matters here: a single pale housing against a
  // white shell has no silhouette at all, and the exposed-switch look — the whole
  // point of the sheet — disappears. Dark lower housing, clear upper.
  swBase: std({ name: 'switch-base', color: '#26272A', roughness: 0.55, metalness: 0 }),
  sw: std({ name: 'switch', color: P.colSwitch, roughness: 0.28, metalness: 0,
            transparent: true, opacity: 0.85 }),
  swStem: std({ name: 'switch-stem', color: '#8B8F94', roughness: 0.4 }),

  // Mondrian primaries. Smoother than the shell so they catch a different
  // highlight — that is what stops them reading as printed-on graphics.
  blue: std({ name: 'block-blue', color: P.colBlue, roughness: P.roughBlock, metalness: 0 }),
  red: std({ name: 'block-red', color: P.colRed, roughness: P.roughBlock, metalness: 0 }),
  yellow: std({ name: 'block-yellow', color: P.colYellow, roughness: P.roughBlock, metalness: 0 }),
  black: std({ name: 'block-black', color: P.colBlack, roughness: 0.5, metalness: 0 }),

  // Every aperture gets a dark cavity AND a dark side wall. Off-axis you mostly
  // see the wall of the hole, not the space behind it: a body-coloured wall
  // catches the key light and reads as a raised white square.
  cavity: new THREE.MeshBasicMaterial({ name: 'cavity', color: '#0B0B0B' }),
  cavityWall: std({ name: 'cavity-wall', color: '#1A1A18', roughness: 0.9 }),
  usbShell: std({ name: 'usb-shell', color: '#9DA3A8', roughness: 0.35, metalness: 0.9 }),
  foot: std({ name: 'foot', color: P.colFoot, roughness: 0.95 }),

  // Light-emitting parts: black base + emissive, toneMapped false, and NAMED —
  // the name travels through the GLB so a Blender script can toggle this one
  // without touching anything else that happens to glow.
  led: (() => {
    const m = std({ name: 'led', color: '#0A0A0A', roughness: 0.3 });
    m.emissive = new THREE.Color('#FF6A44'); m.emissiveIntensity = 2.4; m.toneMapped = false;
    return m;
  })(),
};

export const setLed = (on) => { M.led.emissiveIntensity = on ? 2.4 : 0; M.led.color.set(on ? '#0A0A0A' : '#E9E6DF'); };
