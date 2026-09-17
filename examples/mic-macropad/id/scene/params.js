// params.js — EVERY dimension of the mic-macropad shell, once, with provenance.
// Nobody types a number anywhere else. Derived quantities are computed in the
// builder, never stored (a stored derivative is how a second radius sneaks in).
//
// Tags:  [pcb] the board contract (../../cad/constraints.yaml, ../../pcb/parts.yaml)
//        [std] a real part or standard        [v2] the owner's MicroPad sheet
//        [eye] tuned by looking               [ask] wants a board change, see report R3
//
// FRAMES.  The board contract uses origin bottom-left, +y away from the user.
// The scene uses three.js: +x right, +y UP, +z toward the viewer. `bx()`/`bz()`
// at the bottom convert board → scene, and are the ONLY place the two meet.

export const P = {
  // ---- outer envelope -----------------------------------------------------
  // The owner's sheet captions "90 x 60 x 22 MM" on a 1.50 aspect. 60 mm deep
  // is not reachable: a 56 mm board + 2.5 mm wall + 0.5 mm tolerance per side
  // is 62 mm minimum. So DEPTH is taken from the board and WIDTH is set to hold
  // the sheet's ratio exactly — 93/62 = 1.500. The picture wins on proportion,
  // the board wins on size. (report §1.1)
  W: 93,            // [v2] 62 x 1.50, the sheet's aspect held exactly
  D: 62,            // [pcb] 56 board + 2·(2.5 wall + 0.5 tolerance_mm)
  H: 18,            // [v2] and this one is worth reading. The sheet CAPTIONS
                    //      22 mm, but its pictures show the clear switch
                    //      housings standing well proud of the top face — that
                    //      is the whole exposed-switch idea. Measure it against
                    //      the MX stack: 2.0 foot + 2.5 floor + 5 standoff (both
                    //      [pcb]) + 1.6 board + 11.6 housing = 22.7 mm to the top
                    //      of the housing. At a 22 mm face the housing clears it
                    //      by 0.7 mm and you see nothing. At 18 it stands 4.7 mm
                    //      proud, which is what the picture actually shows.
                    //      The picture wins over its own caption. (report §1.2)

  bezelL: 3.0,      // [pcb] wall + tolerance_mm. The board is NOT centred in the
                    //       shell, and this is the number that decides it — see
                    //       the note on bx() at the bottom. Everything left of
                    //       the board is one wall thickness; everything spare
                    //       goes to the right, where the service strip needs it.
  Rc: 6.0,          // [v2] plan-view corner radius — soft, TE-ish, ~6.5% of W
  Rf: 1.6,          // [v2] edge fillet on the side profile. Independent of Rc:
                    //      "round in plan, thin soft edge" needs two radii.
  wall: 2.5,        // [std] injection-moulded PC wall
  footH: 2.0,       // [eye] lifts the floor clear of the desk — the mic port is
                    //       in the FLOOR (report R1), so this is not decoration
  footR: 4.0,       // [eye]
  footInset: 9.0,   // [eye] from each corner

  // ---- the board underneath ----------------------------------------------
  boardW: 76,       // [pcb] board.outline.l
  boardD: 56,       // [pcb] board.outline.w
  boardT: 1.6,      // [pcb] board.outline.t
  standoff: 5,      // [pcb] stack.standoff_h
  floorT: 2.5,      // [std] = wall

  // ---- keys ---------------------------------------------------------------
  keyPitch: 19.05,  // [pcb] SW1..SW3 centres, and [std] MX spacing
  keyY: 15,         // [pcb] board y of the key row
  // Keycap and MX switch dimensions are NOT here — they are datasheet numbers
  // and they live with the part, in mx.js. One number, one place.
  capLift: 0.4,     // [eye] visible gap, housing crown → cap underside

  // ---- the key tray (one recess spanning all three, from the sheet) -------
  trayFloorZ: 13.0, // [eye] 1.9 above the board's top face: enough to show the
                    //       switch housings, which is the sheet's whole point
  trayMargin: 2.5,  // [eye] cap edge → tray wall. The gap BETWEEN caps is not a
                    //       choice: 19.05 mm pitch minus an 18.0 mm 1u base is
                    //       1.05 mm. What makes a real board look generously
                    //       spaced is the cap TAPER — 18.0 at the base, 13.6 at
                    //       the crown, so the eye reads 5.5 mm up top. Shrinking
                    //       the cap to fake that was the wrong fix.
  trayR: 2.5,       // [v2]

  // ---- the Mondrian grid --------------------------------------------------
  // Not decoration: every line is a constraint and every block names what is
  // under it. (report §1.3, face→element allocation)
  stripX: 28,       // [eye] local x of the vertical split = board x 71.5. Right of
                    //       it: reset, boot, the four test pads. "Service."
  // frontBandZ is NOT stored: the horizontal split IS the tray's front wall.
  // Storing it separately is how a second edge appears 1 mm from the first.
  rearBandY: 24.75,// [pcb] board y 52.75 = the leading edge of Espressif's antenna
                    //       keepout (centre y 54.375, h 3.25). Behind it: radio
                    //       only. NO metal may ever go here — see report R2.
  blockBlueW: 26,   // [v2] blue runs from the left edge along the rear band
  blockRedY0: -14.0,  // [v2] red block on the right strip, over reset/boot…
  blockRedY1: -1.0, // [v2]  …(reset sits at local y -4, boot at local y -11)
  blockYellowX: 4,  // [v2] yellow on the front band, right end, over the mic
  wrap: 4.0,        // [v2] how far a block wraps over the edge onto the side face

  // ---- apertures (all straight from the board contract) -------------------
  usbW: 9.5,        // [pcb] ports.usb_c.w
  usbH: 3.5,        // [pcb] ports.usb_c.h
  usbR: 1.75,       // [std] = usbH/2, a real receptacle is a stadium
  usbBoardY: 36,    // [pcb] ports.usb_c.center_y — REAR of centre, on purpose:
                    //       the cable leaves away from the typing hand
  btnDia: 4.0,      // [pcb] windows.btn_reset/btn_boot.dia
  btnResetY: 24,    // [pcb] board y
  btnBootY: 17,     // [pcb] board y
  btnSinkZ: 11.5,   // [eye] height up the right wall — pressed with a fingernail,
                    //       not a finger: these must never be confusable with keys
  ledDia: 2.0,      // [pcb] windows.led.dia (light-pipe bore)
  ledZ: 4.4,        // [eye] shares micSlotZ: two features on one baseline
                    //       reads as a considered front elevation, not as scatter
  micSlotZ: 4.4,    // [eye] height of the mic slot up the front face
  micSlotX: 52,     // [eye] board x where the front-edge slot sits. Deliberately
                    //       NOT micBoardX: 13 mm of separation from the indicator,
                    //       so the two features read as two features.
  ledBoardX: 66.5,  // [pcb] windows.led.x — where D4 actually is
  ledExitX: 66.5,   // [pcb] = windows.led.x. R3 is CLOSED: once the board moved
                    //       left in the shell, D4's own position already lands in
                    //       the front band where the ID wants it. No light-pipe
                    //       run, no board change.
  micSlotW: 9.0,    // [eye] the front-edge slot the floor port vents through
  micSlotH: 1.2,    // [eye]
  micBoardX: 68.5,  // [pcb] windows.mic_port.x
  micBoardY: 8.5,   // [pcb] windows.mic_port.y
  micPortDia: 1.5,  // [pcb] windows.mic_port.dia — a hole in the FLOOR

  // ---- CMF (measured off refs/10-v1-instrument.png, restated to the sheet) -
  colShell:  '#F2F0EB',  // [v2] warm off-white PC, soft-touch
  colTray:   '#222321',  // [v2] near-black tray floor. Dark on purpose: a recess
                         //      with a light floor stops reading as a recess.
  colCap:    '#F7F6F2',  // [v2] caps a touch brighter than the shell
  colBlue:   '#1F5FA9',  // [v2] Mondrian primary
  colRed:    '#D3372B',  // [v2]
  colYellow: '#F0C22E',  // [v2]
  colBlack:  '#141414',  // [v2]
  colSwitch: '#C9CDD2',  // [std] clear MX housing, reading as pale grey
  colFoot:   '#2A2A28',  // [eye]
  roughShell: 0.62,      // [eye] soft-touch, not gloss
  roughCap:   0.55,      // [eye]
  roughBlock: 0.45,      // [eye] the colour blocks are smoother than the shell

  wordmark: 'mic-macropad',  // [ask] the sheet says "MicroPad"; the repo says
                             //       mic-macropad. Naming is open — report Q1.
};

// ---- frames -----------------------------------------------------------------
// The device is built in the BOARD's own frame — x right, y away from the user,
// z up — and the whole group is rotated once, in device.js, into three.js's
// y-up world. So a board coordinate needs nothing but centring, and there is
// exactly one place where the two conventions meet instead of one per part.
// The board sits HARD LEFT in the shell, one wall thickness from the left face,
// not centred. Two reasons, and the first one is not negotiable:
//   1. USB-C has to be reachable. A Type-C plug shell is 6.5 mm long. Centre the
//      board and its left edge is 8.5 mm behind the outer face — the receptacle
//      ends up down a tunnel no plug can bottom out in. Hard left puts it at the
//      wall. (report R5)
//   2. It is what the owner's sheet draws: keys left of centre, a wide service
//      strip on the right. The constraint and the picture wanted the same thing.
// Consequence: the key row is NOT centred in the shell (it is still centred on
// the board). Left bezel 3.0, right bezel 14.0.
export const bx = b => b + P.bezelL - P.W / 2;   // board x → local x: 0→-43.5, 76→+32.5
export const by = b => b - P.boardD / 2;    // board y → local y:  0→-28, 56→+28
export const boardTopZ = () => P.footH + P.floorT + P.standoff + P.boardT;
