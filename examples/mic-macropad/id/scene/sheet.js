// sheet.js — the contact sheet: six fixed views into one image, each labelled.
// Rendered off the same scene, one tile at a time, into an offscreen target.
import { VIEWS, VIEW_ORDER, applyView } from './views.js';

const COLS = 3, TW = 720, TH = 520, PAD = 18, LABEL = 26;

export function renderSheet({ renderer, scene, cam, scale = 2 }) {
  const rows = Math.ceil(VIEW_ORDER.length / COLS);
  const cw = COLS * TW + (COLS + 1) * PAD;
  const ch = rows * (TH + LABEL) + (rows + 1) * PAD;
  const out = document.createElement('canvas');
  out.width = cw * scale; out.height = ch * scale;
  const ctx = out.getContext('2d');
  ctx.scale(scale, scale);
  ctx.fillStyle = '#F4F2ED'; ctx.fillRect(0, 0, cw, ch);

  renderer.setSize(TW, TH, false);

  VIEW_ORDER.forEach((name, i) => {
    applyView(cam, name, TW / TH);
    renderer.render(scene, cam);
    const col = i % COLS, row = Math.floor(i / COLS);
    const x = PAD + col * (TW + PAD), y = PAD + row * (TH + LABEL + PAD);
    // Third-angle already falls out of views.js: projecting the corners shows
    // BOTTOM puts the front edge up (+0.83) and +x on the right (+0.89), exactly
    // like FRONT. No mirror — adding one flips the underside away from the board
    // it is meant to be held against. (Checked by projecting, not by reasoning
    // about up vectors; that is what got it wrong the first time.)
    ctx.drawImage(renderer.domElement, x, y, TW, TH);
    ctx.strokeStyle = '#D6D2CA'; ctx.lineWidth = 1;
    ctx.strokeRect(x + .5, y + .5, TW - 1, TH - 1);
    ctx.fillStyle = '#4A4640';
    ctx.font = '500 15px ui-monospace, SFMono-Regular, Menlo, monospace';
    ctx.fillText(`${name.toUpperCase()}  ·  ${VIEWS[name].desc}`, x + 2, y + TH + 17);
  });

  return out;
}

export function saveCanvas(canvas, name) {
  return new Promise(res => canvas.toBlob(b =>
    fetch(`/save?name=${name}`, { method: 'POST', body: b }).then(res).catch(res), 'image/png'));
}
