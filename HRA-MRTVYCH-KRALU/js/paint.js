'use strict';
// Procedural painters of the "Iluminovaná krypta" look: cached board sprites, per-frame live details and UI icons.
// Sprite space: 1 unit = 1 cell, origin in the middle of the cell, ground line at y = +0.30.

/* ---------------- path helpers ---------------- */
function rrect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function poly(g, pts) { g.beginPath(); pts.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.closePath(); }
function ellPath(g, x, y, rx, ry, rot = 0) { g.beginPath(); g.ellipse(x, y, rx, ry, rot, 0, TAU); }
function circPath(g, x, y, r) { g.beginPath(); g.arc(x, y, r, 0, TAU); }
function linGrad(g, x0, y0, x1, y1, stops) { const gr = g.createLinearGradient(x0, y0, x1, y1); stops.forEach((c, i) => gr.addColorStop(i / (stops.length - 1), c)); return gr; }

/* ---------------- materials ---------------- */
// SKIN[s]: material + enamel. 0 = bone + lapis, 1 = ebony + ember (with the mandatory ember rim), 2 = neutral icon skin (bone + gilt).
const SPR_INK = '#0b0806', GILT_INK = '#2a1d0c';
const SKIN = [0, 1].map(s => ({ ...MAT[s], t: TEAM[s].c, tHi: TEAM[s].hi, tLo: TEAM[s].lo }));
SKIN.push({ ...MAT[0], t: PAL.gilt, tHi: PAL.giltHi, tLo: PAL.giltLo });
const skinOf = s => SKIN[s] || SKIN[2];
function matFill(g, s, y0 = -0.4, y1 = 0.3) { const m = skinOf(s); g.fillStyle = linGrad(g, -0.3, y0, 0.3, y1, [m.hi, m.base, m.base, m.lo]); g.fill(); }
function outline(g, s, w = 0.03) {
  const m = skinOf(s);
  if (m.rim) { g.strokeStyle = m.ink; g.lineWidth = w * 2.2; g.stroke(); g.strokeStyle = m.rim; g.lineWidth = w; g.stroke(); }
  else { g.strokeStyle = m.ink; g.lineWidth = w * 1.3; g.stroke(); }
}
function solidFill(g, s, y0, y1, w = 0.03) { matFill(g, s, y0, y1); outline(g, s, w); }
function teamFill(g, s, y0 = -0.4, y1 = 0.3) { const m = skinOf(s); g.fillStyle = linGrad(g, 0, y0, 0, y1, [m.tHi, m.t, m.tLo]); g.fill(); g.strokeStyle = m.ink; g.lineWidth = 0.025; g.stroke(); }
function groundShadow(g, rx, y = 0.31, a = 0.45) { ellPath(g, 0, y, rx, rx * 0.28); g.fillStyle = `rgba(0,0,0,${a})`; g.fill(); }
function gemAt(g, x, y, r, col, ink = GILT_INK) { poly(g, [[x, y - r], [x + r * 0.82, y], [x, y + r], [x - r * 0.82, y]]); g.fillStyle = col; g.fill(); g.strokeStyle = ink; g.lineWidth = r * 0.34; g.stroke(); }
function paintSlit(g, x, y, h, lit) { rrect(g, x - 0.025, y, 0.05, h, 0.02); g.fillStyle = lit ? PAL.candle : '#0a0706'; g.fill(); }
const SPR_FONT = 'Cinzel, "Perpetua Titling MT", Georgia, serif';
const SPR_FONT_B = '"Alegreya Sans", Candara, "Segoe UI", sans-serif';
// Text in sprite space (size in cells), drawn in device pixels so small sizes stay crisp and never mirror.
function sprText(g, t, x, y, size, col, stroke = SPR_INK, weight = 900) {
  const m = g.getTransform(), k = Math.hypot(m.a, m.b), px = Math.max(6, Math.round(size * k));
  g.save(); g.setTransform(1, 0, 0, 1, m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f);
  g.font = `${weight} ${px}px ${SPR_FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle';
  if (stroke) { g.lineJoin = 'round'; g.lineWidth = px * 0.22; g.strokeStyle = stroke; g.strokeText(t, 0, px * 0.05); }
  g.fillStyle = col; g.fillText(t, 0, px * 0.05); g.restore();
}

/* ---------------- raster post-processing (whole canvases, device pixels) ---------------- */
function canvasCopy(src) { const c = mkCanvas(src.width, src.height); c.getContext('2d').drawImage(src, 0, 0); c.sz = src.sz; return c; }
function tintCopy(src, col) { const c = canvasCopy(src), g = c.getContext('2d'); g.globalCompositeOperation = 'source-in'; g.fillStyle = col; g.fillRect(0, 0, c.width, c.height); return c; }
function dilateCopy(src, r, col) {
  const c = mkCanvas(src.width, src.height), g = c.getContext('2d'), n = Math.max(8, Math.ceil(r * 5));
  for (let i = 0; i < n; i++) { const a = i / n * TAU; g.drawImage(src, Math.cos(a) * r, Math.sin(a) * r); }
  g.globalCompositeOperation = 'source-in'; g.fillStyle = col; g.fillRect(0, 0, c.width, c.height);
  return c;
}
function ringCopy(src, r, col) { const c = dilateCopy(src, r, col), g = c.getContext('2d'); g.globalCompositeOperation = 'destination-out'; g.drawImage(src, 0, 0); return c; }
// Draws an outline of radius r px behind everything painted so far on g.
function keyline(g, r, col) { const d = dilateCopy(g.canvas, r, col); g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'destination-over'; g.drawImage(d, 0, 0); g.restore(); }
function paintBehind(g, paint) { g.save(); g.globalCompositeOperation = 'destination-over'; paint(); g.restore(); }
function dashRim(c, n = 26) {
  const g = c.getContext('2d');
  if (typeof g.createConicGradient !== 'function') return c;
  const cg = g.createConicGradient(0, c.width / 2, c.height / 2);
  for (let i = 0; i < n; i++) { const a = i / n, b = (i + 0.6) / n; cg.addColorStop(a, '#000'); cg.addColorStop(b, '#000'); cg.addColorStop(b, 'rgba(0,0,0,0)'); cg.addColorStop((i + 1) / n, 'rgba(0,0,0,0)'); }
  g.globalCompositeOperation = 'destination-in'; g.fillStyle = cg; g.fillRect(0, 0, c.width, c.height);
  return c;
}
// 'hidden' variant: body at half alpha, a dashed side-coloured rim at full alpha (ebony must never vanish).
function hiddenize(g, s) {
  const c = g.canvas, src = canvasCopy(c), r = Math.max(1.2, c.width / c.sz * 0.03);
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height);
  g.globalAlpha = 0.5; g.drawImage(src, 0, 0); g.globalAlpha = 1;
  g.drawImage(dashRim(ringCopy(src, r, skinOf(s).rim || skinOf(s).tHi)), 0, 0); g.restore();
}
// 'ghost' variant: a sepia ink sketch of the last known look, with a small "?".
function sketchify(g) {
  const c = g.canvas, src = canvasCopy(c), w = c.width, h = c.height, u = w / c.sz;
  const flat = mkCanvas(w, h), fg = flat.getContext('2d');
  if ('filter' in fg) { fg.filter = 'grayscale(1) sepia(1) contrast(0.75) brightness(0.9)'; fg.drawImage(src, 0, 0); }
  else fg.drawImage(tintCopy(src, PAL.sepia), 0, 0);
  const ht = mkCanvas(w, h), hg = ht.getContext('2d');
  hg.strokeStyle = PAL.sepia; hg.lineWidth = Math.max(1, u * 0.012); hg.beginPath();
  for (let x = -h; x < w; x += u * 0.07) { hg.moveTo(x, h); hg.lineTo(x + h, 0); }
  hg.stroke(); hg.globalCompositeOperation = 'destination-in'; hg.drawImage(src, 0, 0);
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, w, h);
  g.globalAlpha = 0.55; g.drawImage(flat, 0, 0); g.globalAlpha = 0.6; g.drawImage(ht, 0, 0);
  g.globalAlpha = 0.9; g.drawImage(ringCopy(src, Math.max(1, u * 0.02), PAL.ink2), 0, 0); g.restore();
  sprText(g, '?', 0.3, -0.36, 0.26, PAL.sepia, SPR_INK);
}

/* ---------------- sprite cache ---------------- */
// Cached sprite drawn in cell units: 1 unit = 1 cell, origin in the middle. Cleared on resize and when web fonts arrive.
// The canvas carries sz (size in cells) and optionally box ([x0, y0, x1, y1] in cells, where the figure is; used by shardsOf).
const SPR = new Map();
function spr(key, size, paint, box) {
  let c = SPR.get(key);
  if (c) return c;
  const unit = CS * DPR;
  c = mkCanvas(size * unit, size * unit); c.sz = size; c.box = box;
  const g = c.getContext('2d');
  g.setTransform(unit, 0, 0, unit, c.width / 2, c.height / 2);
  g.lineJoin = 'round'; g.lineCap = 'round';
  paint(g);
  SPR.set(key, c);
  return c;
}
// Draws sprite c centred on board cell coords (x, y). size in cells (defaults to the sprite's own), rot in radians, sy = vertical squash after rotation.
function blit(c, x, y, size = c.sz, alpha, rot, sy = 1) {
  const s = size * CS, X = px(x), Y = py(y);
  if (alpha !== undefined) ctx.globalAlpha = alpha;
  if (rot || sy !== 1) { ctx.save(); ctx.translate(X, Y); if (sy !== 1) ctx.scale(1, sy); if (rot) ctx.rotate(rot); ctx.drawImage(c, -s / 2, -s / 2, s, s); ctx.restore(); }
  else ctx.drawImage(c, X - s / 2, Y - s / 2, s, s);
  if (alpha !== undefined) ctx.globalAlpha = 1;
}
function softSpr(col) {
  return spr('SOFT|' + col, 1, g => {
    const gr = g.createRadialGradient(0, 0, 0, 0, 0, 0.5);
    gr.addColorStop(0, rgba(col, 1)); gr.addColorStop(0.35, rgba(col, 0.45)); gr.addColorStop(1, rgba(col, 0));
    g.fillStyle = gr; g.fillRect(-0.5, -0.5, 1, 1);
  });
}
const WHITE_CACHE = new WeakMap(), SHARD_CACHE = new WeakMap();
// Cached white silhouette of a sprite (hit flash).
function whiteOf(c) { let w = WHITE_CACHE.get(c); if (!w) { w = tintCopy(c, '#ffffff'); WHITE_CACHE.set(c, w); } return w; }
// Pre-cut wedge shards of a sprite: [{ c, x, y, sz, a }] with offsets x/y in screen-oriented cell units from the sprite centre,
// sz = shard canvas size in cells (draw it like a sprite), a = outward angle.
function shardsOf(c, n = 8) {
  let byN = SHARD_CACHE.get(c);
  if (!byN) { byN = new Map(); SHARD_CACHE.set(c, byN); }
  if (byN.has(n)) return byN.get(n);
  const u = c.width / c.sz, b = c.box ? c.box.map((v, i) => v * u + (i % 2 ? c.height : c.width) / 2) : [0, 0, c.width, c.height];
  const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2, R = Math.hypot(b[2] - b[0], b[3] - b[1]);
  const cuts = Array.from({ length: n }, (_, i) => (i + 0.5 * hash(i, n, 3)) / n * TAU - Math.PI / 2);
  const out = cuts.map((a0, i) => {
    const a1 = cuts[(i + 1) % n] + (i === n - 1 ? TAU : 0), am = (a0 + a1) / 2;
    const pts = [[cx, cy]]; for (let k = 0; k <= 3; k++) { const a = a0 + (a1 - a0) * k / 3; pts.push([cx + Math.cos(a) * R, cy + Math.sin(a) * R]); }
    const xs = pts.map(p => Math.min(b[2], Math.max(b[0], p[0]))), ys = pts.map(p => Math.min(b[3], Math.max(b[1], p[1])));
    const x0 = Math.floor(Math.min(...xs)), y0 = Math.floor(Math.min(...ys)), side = Math.max(2, Math.ceil(Math.max(Math.max(...xs) - x0, Math.max(...ys) - y0)));
    const sc = mkCanvas(side, side), sg = sc.getContext('2d');
    sg.translate(-x0, -y0); poly(sg, pts); sg.clip(); sg.drawImage(c, 0, 0);
    return { c: sc, x: (x0 + side / 2 - c.width / 2) / u, y: (y0 + side / 2 - c.height / 2) / u, sz: side / u, a: am };
  });
  byN.set(n, out);
  return out;
}
// CPU-backed canvas: cheap pixel reads and toDataURL (icons only; board sprites stay GPU canvases).
function cpuCanvas(w, h) { const c = mkCanvas(w, h); return [c, c.getContext('2d', { willReadFrequently: true })]; }
// Pixel box of the opaque part of a CPU-backed canvas.
function opaqueBox(c) {
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let x0 = c.width, y0 = c.height, x1 = 0, y1 = 0;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) if (d[(y * c.width + x) * 4 + 3] > 120) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  return x1 < x0 ? [0, 0, c.width, c.height] : [x0, y0, x1 + 1, y1 + 1];
}
// Cached text label with an ink stroke (numbers, short words). px = CSS pixels. The canvas carries w/h in CSS pixels; draw it centred.
// opt: { body: true (Alegreya Sans instead of Cinzel), weight, stroke (colour or false), italic }
const TXT_KEYS = [], TXT_MEASURE = mkCanvas(1, 1).getContext('2d');
function txtSpr(text, px, col, opt = {}) {
  const key = `T|${text}|${px}|${col}|${opt.body ? 1 : 0}|${opt.weight || ''}|${opt.stroke}|${opt.italic ? 1 : 0}`;
  let c = SPR.get(key);
  if (c) return c;
  const p = px * DPR, font = `${opt.italic ? 'italic ' : ''}${opt.weight || (opt.body ? 800 : 700)} ${Math.round(p)}px ${opt.body ? SPR_FONT_B : SPR_FONT}`;
  const stroke = opt.stroke === false ? null : opt.stroke || SPR_INK, sw = stroke ? Math.max(2, p * 0.22) : 0;
  TXT_MEASURE.font = font;
  c = mkCanvas(TXT_MEASURE.measureText(text).width + sw * 2 + 4, p * 1.35 + sw * 2);
  const g = c.getContext('2d');
  g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
  if (stroke) { g.lineWidth = sw; g.strokeStyle = stroke; g.strokeText(text, c.width / 2, c.height / 2 + p * 0.04); }
  g.fillStyle = col; g.fillText(text, c.width / 2, c.height / 2 + p * 0.04);
  c.w = c.width / DPR; c.h = c.height / DPR;
  SPR.set(key, c); TXT_KEYS.push(key);
  if (TXT_KEYS.length > 256) SPR.delete(TXT_KEYS.shift());
  return c;
}

/* ---------------- buildings ---------------- */
// Shared plinth: shadow, slab in material, team band, gilt level studs.
function paintSlab(g, s, lvl) {
  const m = skinOf(s);
  groundShadow(g, 0.43, 0.33);
  rrect(g, -0.4, 0.14, 0.8, 0.2, 0.04); g.fillStyle = linGrad(g, 0, 0.14, 0, 0.34, [m.base, m.mid, m.lo]); g.fill(); outline(g, s, 0.024);
  g.fillStyle = m.t; g.fillRect(-0.38, 0.235, 0.76, 0.06); g.fillStyle = m.tHi; g.fillRect(-0.38, 0.235, 0.76, 0.012);
  for (let i = 0; i < lvl; i++) gemAt(g, (i - (lvl - 1) / 2) * 0.13, 0.265, 0.055, PAL.giltHi);
}
function pathBadge(g, p) {
  g.save(); g.translate(0.31, -0.3);
  g.beginPath(); g.moveTo(-0.1, -0.11); g.lineTo(0.1, -0.11); g.lineTo(0.1, 0); g.quadraticCurveTo(0.09, 0.08, 0, 0.13); g.quadraticCurveTo(-0.09, 0.08, -0.1, 0); g.closePath();
  g.fillStyle = linGrad(g, 0, -0.11, 0, 0.13, [PAL.giltHi, PAL.gilt]); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.02; g.stroke();
  sprText(g, p, 0, -0.005, 0.15, GILT_INK, null);
  g.restore();
}
// Candle layout of the Generátor [x, height, width]; shared by the sprite and the live flames.
function candleLayout(lvl, path) {
  const c = [[-0.16, 0.24, 0.11], [0, path === 'A' ? 0.44 : 0.36, path === 'A' ? 0.13 : 0.11], [0.16, 0.2, 0.11]];
  if (lvl >= 2) { c.unshift([-0.27, 0.13, 0.08]); c.push([0.27, 0.15, 0.08]); }
  return c;
}
function paintBell(g, path, rot = 0) {
  const big = path === 'B' ? 1.25 : 1;
  g.save(); g.translate(0, -0.2); g.rotate(rot); g.scale(big, big);
  g.beginPath(); g.moveTo(-0.1, 0.21); g.bezierCurveTo(-0.1, 0.05, -0.06, 0.01, 0, 0.01); g.bezierCurveTo(0.06, 0.01, 0.1, 0.05, 0.1, 0.21); g.closePath();
  g.fillStyle = linGrad(g, -0.1, 0, 0.1, 0, ['#e2c27a', PAL.bronze, '#5e4519']); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.02; g.stroke();
  circPath(g, 0, 0.24, 0.025); g.fillStyle = GILT_INK; g.fill();
  if (path === 'A') { g.beginPath(); g.moveTo(-0.13, 0.0); g.quadraticCurveTo(0, -0.06, 0.13, 0.0); g.lineTo(0.12, 0.25); g.lineTo(-0.12, 0.25); g.closePath(); g.fillStyle = 'rgba(185,195,190,0.45)'; g.fill(); }
  g.restore();
}
const BUILD = {
  gen(g, s, lvl, path) {
    const m = skinOf(s), cs = candleLayout(lvl, path), rx = lvl >= 2 ? 0.34 : 0.31;
    ellPath(g, 0, 0.1, rx, 0.09); solidFill(g, s, 0, 0.18);
    g.beginPath(); g.ellipse(0, 0.13, rx, 0.065, 0, Math.PI, TAU); g.strokeStyle = m.t; g.lineWidth = 0.035; g.stroke();
    for (const [x, h, w] of cs) {
      rrect(g, x - w / 2, 0.09 - h, w, h, 0.03); solidFill(g, s, 0.09 - h, 0.09, 0.02);
      ellPath(g, x, 0.09 - h, w / 2, w * 0.16); g.fillStyle = m.mid; g.fill();
      g.beginPath(); g.moveTo(x, 0.09 - h); g.lineTo(x, 0.06 - h); g.strokeStyle = SPR_INK; g.lineWidth = 0.014; g.stroke();
    }
    g.beginPath(); g.ellipse(0, 0.13, rx, 0.065, 0, 0, Math.PI); g.strokeStyle = m.t; g.lineWidth = 0.035; g.stroke();
    if (path === 'B') { g.beginPath(); g.ellipse(0, 0.12, rx + 0.06, 0.1, 0, 0, Math.PI); g.strokeStyle = PAL.giltHi; g.lineWidth = 0.015; g.setLineDash([0.03, 0.03]); g.stroke(); g.setLineDash([]); }
  },
  kulomet(g, s) {
    const m = skinOf(s);
    rrect(g, -0.29, -0.12, 0.58, 0.32, 0.03); solidFill(g, s, -0.12, 0.2);
    g.strokeStyle = rgba(m.ink, 0.35); g.lineWidth = 0.008; g.beginPath(); g.moveTo(-0.29, 0.04); g.lineTo(0.29, 0.04);
    for (const x of [-0.15, 0.0, 0.15]) { g.moveTo(x, -0.04); g.lineTo(x, 0.04); g.moveTo(x + 0.07, 0.04); g.lineTo(x + 0.07, 0.2); } g.stroke();
    ellPath(g, 0, -0.12, 0.29, 0.09); g.fillStyle = m.mid; g.fill(); outline(g, s, 0.022);
    ellPath(g, 0, -0.12, 0.2, 0.055); g.fillStyle = m.lo; g.fill();
    paintSlit(g, -0.15, -0.03, 0.12); paintSlit(g, 0.15, -0.03, 0.12);
  },
  sniper(g, s, lvl, path) {
    poly(g, [[-0.17, 0.2], [-0.13, -0.3], [0.13, -0.3], [0.17, 0.2]]); solidFill(g, s, -0.3, 0.2);
    rrect(g, -0.18, -0.34, 0.36, 0.06, 0.02); solidFill(g, s, -0.34, -0.28, 0.02);
    poly(g, [[-0.19, -0.33], [0, -0.62], [0.19, -0.33]]); teamFill(g, s, -0.62, -0.33);
    paintSlit(g, 0, -0.22, 0.14, true); paintSlit(g, 0, 0.0, 0.1);
    if (path === 'B') { ellPath(g, 0, -0.43, 0.055, 0.032); g.fillStyle = '#f3e6c8'; g.fill(); g.strokeStyle = PAL.rubric; g.lineWidth = 0.016; g.stroke(); circPath(g, 0, -0.43, 0.018); g.fillStyle = PAL.rubricD; g.fill(); }
  },
  hlaska(g, s, lvl, path, f) {
    const big = path === 'B' ? 1.22 : 1;
    poly(g, [[-0.2, 0.2], [-0.16, -0.14], [0.16, -0.14], [0.2, 0.2]]); solidFill(g, s, -0.14, 0.2);
    paintSlit(g, 0, -0.04, 0.12);
    rrect(g, -0.23, -0.2, 0.46, 0.07, 0.02); solidFill(g, s, -0.2, -0.13, 0.02);
    g.save(); g.translate(0, -0.2); g.scale(big, big);
    rrect(g, -0.09, -0.2, 0.18, 0.2, 0.03); g.fillStyle = linGrad(g, 0, -0.2, 0, 0, [PAL.flame, PAL.candle]); g.fill(); g.strokeStyle = '#1c130c'; g.lineWidth = 0.025; g.stroke();
    g.beginPath(); g.moveTo(0, -0.2); g.lineTo(0, 0); g.moveTo(-0.09, -0.1); g.lineTo(0.09, -0.1); g.strokeStyle = '#1c130c'; g.lineWidth = 0.018; g.stroke();
    poly(g, [[-0.14, -0.2], [0, -0.31], [0.14, -0.2]]); teamFill(g, s, -0.31, -0.2);
    g.restore();
    if (path === 'A') {
      g.save(); g.scale(f, 1); g.translate(0.12, -0.24); g.rotate(-0.35);
      rrect(g, 0, -0.025, 0.2, 0.05, 0.015); g.fillStyle = linGrad(g, 0, -0.03, 0, 0.03, ['#e2c27a', PAL.bronze, '#5e4519']); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.014; g.stroke();
      rrect(g, 0.17, -0.035, 0.06, 0.07, 0.015); g.fill(); g.stroke(); g.restore();
    }
  },
  plamen(g, s, lvl, path, f) {
    const m = skinOf(s);
    rrect(g, -0.25, -0.02, 0.5, 0.22, 0.03); solidFill(g, s, -0.02, 0.2);
    g.save(); g.scale(f, 1);
    g.beginPath(); g.moveTo(-0.06, -0.13); g.quadraticCurveTo(-0.16, -0.38, -0.32, -0.34); g.quadraticCurveTo(-0.27, -0.27, -0.29, -0.19); g.quadraticCurveTo(-0.24, -0.17, -0.23, -0.1); g.quadraticCurveTo(-0.17, -0.1, -0.13, -0.03); g.closePath();
    g.fillStyle = linGrad(g, 0, -0.36, 0, 0, [m.mid, m.lo]); g.fill(); outline(g, s, 0.02);
    ellPath(g, -0.04, -0.08, 0.17, 0.1, -0.15); solidFill(g, s, -0.18, 0.02);
    for (const x of [0.05, 0.12]) { poly(g, [[x, -0.05], [x + 0.05, -0.03], [x + 0.06, 0.02], [x, 0.0]]); solidFill(g, s, -0.05, 0.02, 0.015); }
    for (const [x, l] of [[0.05, 0.17], [0.12, 0.13]]) { g.beginPath(); g.moveTo(x - 0.03, -0.29); g.quadraticCurveTo(x - 0.06, -0.28 - l, x - l - 0.02, -0.33 - l * 0.8); g.quadraticCurveTo(x - 0.01, -0.34 - l * 0.3, x + 0.04, -0.28); g.closePath(); teamFill(g, s, -0.5, -0.28); }
    g.beginPath(); g.moveTo(0.0, -0.18); g.quadraticCurveTo(0.03, -0.33, 0.16, -0.32); g.lineTo(0.32, -0.23); g.lineTo(0.31, -0.165); g.lineTo(0.15, -0.16); g.lineTo(0.12, -0.11); g.quadraticCurveTo(0.03, -0.09, 0.0, -0.18); g.closePath(); solidFill(g, s, -0.33, -0.1);
    poly(g, [[0.14, -0.155], [0.31, -0.16], [0.29, -0.1], [0.14, -0.13]]); g.fillStyle = PAL.candle; g.fill();
    poly(g, [[0.12, -0.12], [0.16, -0.135], [0.3, -0.1], [0.27, -0.045], [0.12, -0.06]]); solidFill(g, s, -0.14, -0.04, 0.02);
    g.fillStyle = PAL.bone; poly(g, [[0.21, -0.162], [0.225, -0.128], [0.24, -0.162]]); g.fill(); poly(g, [[0.25, -0.108], [0.262, -0.14], [0.275, -0.105]]); g.fill();
    g.beginPath(); g.moveTo(0.1, -0.29); g.quadraticCurveTo(0.17, -0.31, 0.22, -0.27); g.strokeStyle = m.ink; g.lineWidth = 0.02; g.stroke();
    circPath(g, 0.17, -0.255, 0.024); g.fillStyle = PAL.candle; g.fill();
    g.restore();
  },
  tesla(g, s, lvl, path) {
    const m = skinOf(s), n = path === 'A' ? 5 : 3;
    poly(g, [[-0.16, 0.2], [-0.09, -0.3], [0.09, -0.3], [0.16, 0.2]]); solidFill(g, s, -0.3, 0.2);
    for (let i = 0; i < 3; i++) { g.fillStyle = m.t; g.fillRect(-0.13 + i * 0.016, 0.04 - i * 0.14, 0.26 - i * 0.032, 0.03); }
    g.beginPath(); for (let i = 0; i < n; i++) { const x = (i - (n - 1) / 2) * 0.1 / ((n - 1) / 2); g.moveTo(x * 0.8, -0.3); g.lineTo(x * 1.5, -0.45); }
    g.strokeStyle = PAL.ironL; g.lineWidth = 0.03; g.stroke();
    circPath(g, 0, -0.38, 0.065); g.fillStyle = PAL.ghost; g.fill(); g.strokeStyle = PAL.ghostD; g.lineWidth = 0.02; g.stroke();
    if (path === 'B') { ellPath(g, 0, -0.38, 0.12, 0.04); g.strokeStyle = PAL.ironL; g.lineWidth = 0.016; g.stroke(); }
  },
  rusicka(g, s, lvl, path, f, bell) {
    for (const x of [-0.2, 0.14]) { rrect(g, x, -0.24, 0.06, 0.44, 0.02); solidFill(g, s, -0.24, 0.2, 0.02); }
    rrect(g, -0.2, -0.25, 0.4, 0.04, 0.01); solidFill(g, s, -0.25, -0.21, 0.016);
    poly(g, [[-0.26, -0.22], [0, -0.42], [0.26, -0.22]]); teamFill(g, s, -0.42, -0.22);
    if (bell) paintBell(g, path);
  },
};
function paintWall(g, s, lvl) {
  const m = skinOf(s);
  groundShadow(g, 0.44, 0.33);
  if (lvl === 1) {
    for (let i = 0; i < 5; i++) {
      const x = -0.36 + i * 0.18, t = -0.28 - hash(i, 3, 1) * 0.06;
      poly(g, [[x - 0.075, 0.3], [x - 0.075, t + 0.06], [x, t], [x + 0.075, t + 0.06], [x + 0.075, 0.3]]);
      g.fillStyle = linGrad(g, x - 0.075, 0, x + 0.075, 0, ['#8a6240', PAL.woodD]); g.fill(); g.strokeStyle = '#1e140c'; g.lineWidth = 0.02; g.stroke();
    }
    for (const y of [-0.1, 0.12]) { rrect(g, -0.45, y, 0.9, 0.06, 0.015); solidFill(g, s, y, y + 0.06, 0.016); }
  } else if (lvl === 2) {
    rrect(g, -0.45, -0.3, 0.9, 0.62, 0.04); solidFill(g, s, -0.3, 0.32, 0.03);
    rrect(g, -0.39, -0.24, 0.78, 0.48, 0.02); g.fillStyle = linGrad(g, 0, -0.24, 0, 0.24, ['#80848b', '#3d4045']); g.fill(); g.strokeStyle = '#141518'; g.lineWidth = 0.02; g.stroke();
    g.strokeStyle = '#2a2c30'; g.lineWidth = 0.015; g.beginPath(); g.moveTo(0, -0.24); g.lineTo(0, 0.24); g.moveTo(-0.39, 0); g.lineTo(0.39, 0); g.stroke();
    for (const x of [-0.33, -0.06, 0.06, 0.33]) for (const y of [-0.18, -0.06, 0.06, 0.18]) { circPath(g, x, y, 0.02); g.fillStyle = '#b8bcc4'; g.fill(); }
  } else {
    poly(g, [[-0.44, 0.3], [-0.44, -0.3], [-0.3, -0.3], [-0.3, -0.22], [-0.15, -0.22], [-0.15, -0.3], [0, -0.3], [0, -0.22], [0.15, -0.22], [0.15, -0.3], [0.3, -0.3], [0.3, -0.22], [0.44, -0.22], [0.44, 0.3]]);
    solidFill(g, s, -0.3, 0.3);
    g.strokeStyle = rgba(m.ink, 0.5); g.lineWidth = 0.012; g.beginPath();
    for (let r = 0; r < 4; r++) { const y = -0.14 + r * 0.11; g.moveTo(-0.44, y); g.lineTo(0.44, y); for (let c = 0; c < 4; c++) { const x = -0.33 + c * 0.22 + (r % 2) * 0.11; g.moveTo(x, y); g.lineTo(x, y + 0.11); } }
    g.stroke();
  }
  g.fillStyle = m.t; g.fillRect(-0.43, 0.26, 0.86, 0.05);
}
function paintMine(g, s) {
  const m = skinOf(s);
  g.globalAlpha = 0.85;
  circPath(g, 0, 0.05, 0.3); g.strokeStyle = m.t; g.lineWidth = 0.03; g.setLineDash([0.05, 0.04]); g.stroke(); g.setLineDash([]);
  for (let i = 0; i < 6; i++) { const a = i / 6 * TAU; g.save(); g.translate(Math.cos(a) * 0.22, 0.05 + Math.sin(a) * 0.22); g.rotate(a); poly(g, [[-0.03, 0], [0.04, -0.03], [0.04, 0.03]]); g.fillStyle = m.t; g.fill(); g.restore(); }
  paintSkull(g, 0, 0.04, 0.1);
  g.globalAlpha = 1;
}
function paintSkull(g, x, y, r) {
  rrect(g, x - r * 0.5, y + r * 0.45, r, r * 0.45, r * 0.15); g.fillStyle = PAL.bone; g.fill(); g.strokeStyle = '#1a1210'; g.lineWidth = r * 0.14; g.stroke();
  circPath(g, x, y, r); g.fill(); g.stroke();
  g.fillStyle = '#1a1210'; for (const d of [-1, 1]) { ellPath(g, x + d * r * 0.38, y + r * 0.1, r * 0.26, r * 0.3); g.fill(); }
  poly(g, [[x, y + r * 0.42], [x + r * 0.12, y + r * 0.62], [x - r * 0.12, y + r * 0.62]]); g.fill();
}
function paintBuilding(g, kind, s, lvl, path, f, bell) {
  if (kind === 'zed') return paintWall(g, s, lvl);
  if (kind === 'mina') return paintMine(g, s);
  paintSlab(g, s, lvl);
  (BUILD[kind] || BUILD.kulomet)(g, s, lvl, path, f, bell);
  if (path) pathBadge(g, path);
}
// Screen facing of a side: own things face right (toward the enemy), enemy things face left.
const sideFace = side => side === S.side ? 1 : -1;
// variant: '' | 'ghost' (sepia sketch with "?", drawn above the fog) | 'hidden' (half alpha body, dashed full-alpha rim)
function sprBuilding(kind, side, lvl, path, variant = '', face = sideFace(side)) {
  const v = variant === true ? 'ghost' : variant || '', f = kind === 'plamen' || kind === 'hlaska' ? face : 1;
  return spr(`B|${kind}|${side}|${lvl}|${path || ''}|${v}|${f}`, 1.6, g => {
    paintBuilding(g, kind, side, lvl, path, f, v === 'ghost');
    if (v === 'ghost') sketchify(g); else if (v === 'hidden') hiddenize(g, side);
  }, [-0.46, -0.66, 0.46, 0.4]);
}
// Rotating weapon part (crossbow / arbalest), pointing to +x. Pivot = sprite centre; place it at BARREL_OY above the cell centre.
const BARREL_OY = { kulomet: -0.12, sniper: -0.18 };
function paintBarrel(g, kind, s, path) {
  const m = skinOf(s), sn = kind === 'sniper', L = sn ? 0.5 : path === 'B' ? 0.48 : 0.42, offs = !sn && path === 'A' ? [-0.06, 0.06] : [0];
  for (const o of offs) {
    rrect(g, -0.1, o - 0.035, L, 0.07, 0.02); g.fillStyle = linGrad(g, 0, o - 0.035, 0, o + 0.035, ['#8a6240', PAL.wood, PAL.woodD]); g.fill(); g.strokeStyle = '#1e140c'; g.lineWidth = 0.016; g.stroke();
    const bx = -0.1 + L * 0.72, arm = sn ? 0.24 : 0.2;
    g.beginPath(); g.moveTo(bx - 0.07, o - arm); g.quadraticCurveTo(bx + 0.08, o, bx - 0.07, o + arm);
    g.strokeStyle = m.ink; g.lineWidth = 0.075; g.stroke(); g.strokeStyle = m.t; g.lineWidth = 0.045; g.stroke();
    g.beginPath(); g.moveTo(bx - 0.07, o - arm); g.lineTo(bx - 0.17, o); g.lineTo(bx - 0.07, o + arm); g.strokeStyle = '#d8ccb0'; g.lineWidth = 0.012; g.stroke();
    for (const a of sn && path === 'A' ? [-0.2, 0, 0.2] : [0]) {
      g.save(); g.translate(bx - 0.17, o); g.rotate(a);
      g.beginPath(); g.moveTo(0, 0); g.lineTo(L * 0.62, 0); g.strokeStyle = '#3a2a1a'; g.lineWidth = 0.022; g.stroke();
      poly(g, [[L * 0.62 - 0.02, -0.035], [L * 0.62 + 0.07, 0], [L * 0.62 - 0.02, 0.035]]); g.fillStyle = path === 'B' ? '#c9ccd3' : m.tHi; g.fill(); g.strokeStyle = m.ink; g.lineWidth = 0.012; g.stroke();
      g.restore();
    }
  }
  circPath(g, 0, 0, 0.065); g.fillStyle = m.t; g.fill(); outline(g, s, 0.015);
}
function sprBarrel(kind, side, path) { return spr(`R|${kind}|${side}|${path || ''}`, 1.3, g => paintBarrel(g, kind, side, path)); }

/* ---------------- chess pieces ---------------- */
const PIECE = {
  pesak(g, s) {
    g.beginPath(); g.moveTo(-0.17, 0.2); g.bezierCurveTo(-0.15, 0.08, -0.07, 0.02, -0.06, -0.04); g.lineTo(0.06, -0.04); g.bezierCurveTo(0.07, 0.02, 0.15, 0.08, 0.17, 0.2); g.closePath(); solidFill(g, s, -0.1, 0.2);
    ellPath(g, 0, -0.05, 0.12, 0.035); solidFill(g, s, -0.08, -0.02, 0.022);
    circPath(g, 0, -0.17, 0.105); solidFill(g, s, -0.28, -0.07);
  },
  obrnenec(g, s) {
    poly(g, [[-0.19, 0.2], [-0.15, -0.12], [0.15, -0.12], [0.19, 0.2]]); solidFill(g, s, -0.12, 0.2);
    poly(g, [[-0.21, -0.12], [-0.21, -0.32], [-0.13, -0.32], [-0.13, -0.25], [-0.04, -0.25], [-0.04, -0.32], [0.04, -0.32], [0.04, -0.25], [0.13, -0.25], [0.13, -0.32], [0.21, -0.32], [0.21, -0.12]]);
    solidFill(g, s, -0.32, -0.12);
    g.fillStyle = skinOf(s).t; g.fillRect(-0.17, -0.02, 0.34, 0.05);
  },
  strelec(g, s) {
    const m = skinOf(s);
    g.beginPath(); g.moveTo(-0.16, 0.2); g.bezierCurveTo(-0.12, 0.05, -0.07, 0, -0.06, -0.06); g.lineTo(0.06, -0.06); g.bezierCurveTo(0.07, 0, 0.12, 0.05, 0.16, 0.2); g.closePath(); solidFill(g, s, -0.1, 0.2);
    ellPath(g, 0, -0.19, 0.1, 0.15); solidFill(g, s, -0.34, -0.05);
    g.beginPath(); g.moveTo(-0.02, -0.28); g.lineTo(0.08, -0.15); g.strokeStyle = m.rim || m.ink; g.lineWidth = 0.03; g.stroke();
    circPath(g, 0, -0.36, 0.035); solidFill(g, s, -0.4, -0.32, 0.02);
    ellPath(g, 0, -0.06, 0.1, 0.03); g.fillStyle = m.t; g.fill();
  },
  jezdec(g, s, f) {
    const m = skinOf(s);
    g.save(); g.scale(f, 1);
    g.beginPath(); g.moveTo(-0.18, 0.2); g.lineTo(-0.16, 0.02); g.bezierCurveTo(-0.2, -0.12, -0.12, -0.3, 0, -0.34);
    g.lineTo(0.04, -0.4); g.lineTo(0.07, -0.32); g.bezierCurveTo(0.16, -0.27, 0.22, -0.18, 0.24, -0.1);
    g.lineTo(0.22, -0.05); g.lineTo(0.1, -0.08); g.bezierCurveTo(0.06, -0.02, 0.12, 0.08, 0.18, 0.2); g.closePath(); solidFill(g, s, -0.38, 0.2);
    circPath(g, 0.08, -0.22, 0.025); g.fillStyle = m.rim || m.ink; g.fill();
    g.beginPath(); g.moveTo(-0.05, -0.32); g.quadraticCurveTo(-0.17, -0.18, -0.15, 0); g.strokeStyle = m.t; g.lineWidth = 0.05; g.stroke();
    g.restore();
  },
  dama(g, s) {
    g.beginPath(); g.moveTo(-0.18, 0.2); g.bezierCurveTo(-0.13, 0.04, -0.08, -0.06, -0.09, -0.16); g.lineTo(0.09, -0.16); g.bezierCurveTo(0.08, -0.06, 0.13, 0.04, 0.18, 0.2); g.closePath(); solidFill(g, s, -0.16, 0.2);
    poly(g, [[-0.15, -0.16], [-0.19, -0.33], [-0.09, -0.24], [0, -0.37], [0.09, -0.24], [0.19, -0.33], [0.15, -0.16]]); teamFill(g, s, -0.37, -0.16);
    for (const [x, y] of [[-0.19, -0.35], [0, -0.39], [0.19, -0.35]]) { circPath(g, x, y, 0.03); g.fillStyle = PAL.giltHi; g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.012; g.stroke(); }
  },
  medik(g, s, f) {
    const m = skinOf(s);
    g.save(); g.scale(f, 1);
    poly(g, [[-0.17, 0.2], [-0.13, -0.05], [0.13, -0.05], [0.17, 0.2]]); solidFill(g, s, -0.05, 0.2);
    circPath(g, -0.01, -0.17, 0.13); solidFill(g, s, -0.3, -0.04);
    poly(g, [[0.08, -0.22], [0.33, -0.1], [0.08, -0.1]]); g.fillStyle = m.t; g.fill(); g.strokeStyle = m.ink; g.lineWidth = 0.02; g.stroke();
    circPath(g, 0.03, -0.2, 0.035); g.fillStyle = '#d9f0e4'; g.fill(); g.strokeStyle = m.ink; g.lineWidth = 0.015; g.stroke();
    rrect(g, -0.1, -0.42, 0.18, 0.15, 0.03); g.fillStyle = linGrad(g, 0, -0.42, 0, -0.27, [m.mid, m.lo]); g.fill(); outline(g, s, 0.018);
    g.fillStyle = m.t; g.fillRect(-0.1, -0.32, 0.18, 0.03);
    ellPath(g, -0.01, -0.27, 0.21, 0.035); g.fillStyle = m.lo; g.fill(); outline(g, s, 0.018);
    g.restore();
  },
  saboter(g, s, f) {
    const m = skinOf(s);
    g.save(); g.scale(f, 1);
    poly(g, [[-0.16, 0.2], [-0.11, -0.12], [0, -0.36], [0.11, -0.12], [0.16, 0.2]]); solidFill(g, s, -0.36, 0.2);
    ellPath(g, 0, -0.13, 0.06, 0.05); g.fillStyle = '#050304'; g.fill();
    circPath(g, 0.2, 0.08, 0.08); g.fillStyle = '#1a1718'; g.fill(); g.strokeStyle = m.t; g.lineWidth = 0.025; g.stroke();
    g.beginPath(); g.moveTo(0.24, 0.02); g.quadraticCurveTo(0.3, -0.06, 0.27, -0.1); g.strokeStyle = PAL.bronze; g.lineWidth = 0.018; g.stroke();
    circPath(g, 0.27, -0.11, 0.025); g.fillStyle = PAL.flame; g.fill();
    g.restore();
  },
};
const ASYM_PIECES = new Set(['jezdec', 'medik', 'saboter']);
function pieceBase(g, s, rx) {
  groundShadow(g, rx + 0.04, 0.3);
  ellPath(g, 0, 0.25, rx, rx * 0.34); g.fillStyle = skinOf(s).tLo; g.fill();
  ellPath(g, 0, 0.215, rx, rx * 0.32); teamFill(g, s, 0.15, 0.3);
  ellPath(g, 0, 0.19, rx * 0.8, rx * 0.24); solidFill(g, s, 0.1, 0.25, 0.022);
}
// Veteran mark: a small gilt laurel wreath open at the top.
function paintLaurel(g, x, y) {
  g.save(); g.translate(x, y); g.scale(1.2, 1.2);
  for (const d of [-1, 1]) {
    g.beginPath(); g.moveTo(0, 0.07); g.quadraticCurveTo(d * 0.09, 0.04, d * 0.08, -0.07); g.strokeStyle = GILT_INK; g.lineWidth = 0.03; g.stroke(); g.strokeStyle = PAL.gilt; g.lineWidth = 0.014; g.stroke();
    for (const [lx, ly, a] of [[0.035, 0.05, 0.3], [0.072, 0.0, 1.0], [0.08, -0.06, 1.5]]) { ellPath(g, d * lx, ly, 0.036, 0.017, -d * a); g.fillStyle = PAL.giltHi; g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.01; g.stroke(); }
  }
  g.restore();
}
function paintPiece(g, kind, s, vet, f) {
  const big = kind === 'obrnenec' || kind === 'dama', rx = big ? 0.27 : 0.24;
  g.save(); g.translate(0, 0.3); g.scale(1.15, 1.15); g.translate(0, -0.3);
  pieceBase(g, s, rx);
  if (vet) { ellPath(g, 0, 0.215, rx + 0.03, (rx + 0.03) * 0.32); g.strokeStyle = PAL.giltHi; g.lineWidth = 0.018; g.stroke(); }
  (PIECE[kind] || PIECE.pesak)(g, s, f);
  if (vet) paintLaurel(g, -0.21, -0.24);
  g.restore();
}
function sprUnit(kind, side, vet, face = 1, variant = '') {
  const f = ASYM_PIECES.has(kind) ? face : 1;
  return spr(`U|${kind}|${side}|${vet ? 1 : 0}|${f}|${variant}`, 1.1, g => { paintPiece(g, kind, side, !!vet, f); if (variant === 'hidden') hiddenize(g, side); }, [-0.4, -0.52, 0.4, 0.4]);
}

/* ---------------- the King ---------------- */
function paintKing(g, s, f) {
  const m = skinOf(s);
  g.save(); g.translate(0, 0.3); g.scale(1.2, 1.2); g.translate(0, -0.3);
  pieceBase(g, s, 0.29);
  g.save(); g.scale(f, 1);
  g.beginPath(); g.moveTo(-0.24, 0.2); g.bezierCurveTo(-0.22, 0, -0.14, -0.1, -0.1, -0.16); g.lineTo(0.08, -0.16); g.bezierCurveTo(0.12, -0.1, 0.16, 0, 0.2, 0.2); g.closePath(); teamFill(g, s, -0.16, 0.2);
  g.restore();
  g.beginPath(); g.moveTo(-0.13, 0.2); g.bezierCurveTo(-0.11, 0.02, -0.07, -0.08, -0.07, -0.16); g.lineTo(0.07, -0.16); g.bezierCurveTo(0.07, -0.08, 0.11, 0.02, 0.13, 0.2); g.closePath(); solidFill(g, s, -0.16, 0.2);
  circPath(g, 0, -0.24, 0.1); solidFill(g, s, -0.34, -0.14);
  g.save(); g.scale(f, 1);
  g.beginPath(); g.moveTo(0.15, 0.16); g.lineTo(0.19, -0.2); g.strokeStyle = SPR_INK; g.lineWidth = 0.05; g.stroke(); g.strokeStyle = PAL.gilt; g.lineWidth = 0.028; g.stroke();
  circPath(g, 0.195, -0.23, 0.04); g.fillStyle = linGrad(g, 0, -0.27, 0, -0.19, ['#fff0b8', '#d8b45a', '#8a6a2a']); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.014; g.stroke();
  circPath(g, 0.155, -0.02, 0.035); solidFill(g, s, -0.06, 0.02, 0.016);
  g.restore();
  g.beginPath(); g.moveTo(-0.05 + f * 0.01, -0.25); g.lineTo(-0.02 + f * 0.01, -0.25); g.moveTo(0.02 + f * 0.01, -0.25); g.lineTo(0.05 + f * 0.01, -0.25); g.strokeStyle = m.rim || m.ink; g.lineWidth = 0.03; g.stroke();
  paintCrown(g, 0, -0.38, 1);
  g.restore();
}
// Gilt crown with fleurons (no cross), base centre at (x, y).
function paintCrown(g, x, y, k) {
  g.save(); g.translate(x, y); g.scale(k, k);
  poly(g, [[-0.12, 0.08], [-0.14, -0.06], [-0.07, 0.01], [0, -0.09], [0.07, 0.01], [0.14, -0.06], [0.12, 0.08]]);
  g.fillStyle = linGrad(g, 0, -0.09, 0, 0.08, ['#fff0b8', '#d8b45a', '#8a6a2a']); g.shadowColor = 'rgba(255,214,120,0.8)'; g.shadowBlur = 0.08 * Math.hypot(g.getTransform().a, g.getTransform().b); g.fill(); g.shadowBlur = 0;
  g.strokeStyle = GILT_INK; g.lineWidth = 0.02; g.stroke();
  for (const [cx, cy] of [[-0.14, -0.08], [0, -0.11], [0.14, -0.08]]) { circPath(g, cx, cy, 0.024); g.fillStyle = PAL.giltHi; g.fill(); g.lineWidth = 0.01; g.stroke(); }
  gemAt(g, 0, 0.035, 0.03, PAL.rubric);
  g.restore();
}
function sprKing(side, face = 1) { return spr(`K|${side}|${face}`, 1.4, g => paintKing(g, side, face), [-0.38, -0.66, 0.38, 0.42]); }

/* ---------------- zombies ---------------- */
const ZR = { chodec: 0.28, bezec: 0.22, obr: 0.38, alfa: 0.46 };
const ZSCALE = { chodec: 1.25, bezec: 1.0, obr: 1.5, alfa: 1.65 };
function zombieFrame(g, kind, frame, face, pass) {
  const big = kind === 'obr' || kind === 'alfa', s = ZSCALE[kind] || 1.25, ph = (frame & 3) / 4 * TAU, step = Math.sin(ph), bob = Math.abs(Math.cos(ph)) * 0.02;
  const lean = kind === 'bezec' ? 0.1 : 0.05, hx = lean + (big ? 0.1 : 0.08), hy = big ? -0.22 : -0.24;
  g.save(); g.translate(0, 0.3); g.scale(face * s, s); g.translate(0, -0.3 - bob);
  if (pass === 'eye') {
    circPath(g, hx + 0.035, hy - 0.01, 0.019); g.fillStyle = PAL.eye; g.shadowColor = PAL.eye; g.shadowBlur = 0.09 * Math.hypot(g.getTransform().a, g.getTransform().b); g.fill(); g.shadowBlur = 0;
    g.restore(); return;
  }
  const skinG = linGrad(g, -0.2, -0.3, 0.2, 0.3, [PAL.fleshL, PAL.flesh, PAL.fleshD]);
  g.strokeStyle = PAL.fleshD; g.lineCap = 'round'; g.lineWidth = big ? 0.075 : 0.055;
  g.beginPath(); g.moveTo(-0.05, 0.05); g.lineTo(-0.08 - step * 0.06, 0.29 + bob); g.moveTo(0.05, 0.05); g.lineTo(0.09 + step * 0.06, 0.28 + bob); g.stroke();
  if (kind === 'alfa') { poly(g, [[-0.16, -0.18], [-0.27, 0.27], [0, 0.2], [0.18, 0.26], [0.1, -0.16]]); g.fillStyle = '#3a1f33'; g.fill(); g.strokeStyle = '#120a10'; g.lineWidth = 0.02; g.stroke(); }
  ellPath(g, lean, -0.06, big ? 0.17 : 0.12, big ? 0.17 : 0.15, -0.25); g.fillStyle = skinG; g.fill(); g.strokeStyle = PAL.zInk; g.lineWidth = 0.022; g.stroke();
  poly(g, [[lean - 0.12, -0.02], [lean + 0.11, 0], [lean + 0.08, 0.1], [lean + 0.02, 0.06], [lean - 0.04, 0.12], [lean - 0.11, 0.07]]); g.fillStyle = PAL.rags; g.fill();
  const sw = Math.cos(ph) * 0.025;
  g.strokeStyle = PAL.flesh; g.lineWidth = big ? 0.07 : 0.045; g.beginPath();
  g.moveTo(lean + 0.05, -0.12); g.lineTo(lean + 0.26, -0.1 + sw); g.moveTo(lean + 0.02, -0.06); g.lineTo(lean + 0.24, -0.02 - sw); g.stroke();
  if (kind === 'obr') { for (let i = 0; i < 3; i++) { ellPath(g, lean + 0.2 + i * 0.012, 0.0 + i * 0.045 - sw, 0.018, 0.026); g.strokeStyle = PAL.ironL; g.lineWidth = 0.012; g.stroke(); } }
  circPath(g, hx, hy, big ? 0.07 : 0.075); g.fillStyle = skinG; g.fill(); g.strokeStyle = PAL.zInk; g.lineWidth = 0.02; g.stroke();
  if (big) for (let i = 0; i < 3; i++) { poly(g, [[lean - 0.12 + i * 0.07, -0.18], [lean - 0.15 + i * 0.07, -0.3], [lean - 0.07 + i * 0.07, -0.2]]); g.fillStyle = '#e6dcc4'; g.fill(); g.strokeStyle = PAL.zInk; g.lineWidth = 0.01; g.stroke(); }
  if (kind === 'alfa') {
    poly(g, [[hx - 0.07, hy - 0.05], [hx - 0.08, hy - 0.14], [hx - 0.03, hy - 0.09], [hx, hy - 0.16], [hx + 0.03, hy - 0.09], [hx + 0.08, hy - 0.13], [hx + 0.07, hy - 0.05]]);
    g.fillStyle = '#5c5f64'; g.fill(); g.strokeStyle = '#141518'; g.lineWidth = 0.012; g.stroke(); circPath(g, hx, hy - 0.08, 0.014); g.fillStyle = PAL.rubric; g.fill();
  }
  g.restore();
}
function sprZombie(kind, frame = 0, face = 1) {
  const r = ZR[kind] || 0.28, k = ZR[kind] ? kind : 'chodec', fr = frame & 3;
  return spr(`Z|${k}|${fr}|${face}`, r * 2 + 0.8, g => {
    zombieFrame(g, k, fr, face, 'body');
    keyline(g, Math.max(1.5, CS * DPR * 0.032), PAL.zInk);
    zombieFrame(g, k, fr, face, 'eye');
    paintBehind(g, () => groundShadow(g, 0.2 * ZSCALE[k], 0.3));
    if (k === 'alfa') paintBehind(g, () => { const au = g.createRadialGradient(0, -0.1, 0.05, 0, -0.1, 0.8); au.addColorStop(0, 'rgba(194,59,46,0.55)'); au.addColorStop(1, 'rgba(194,59,46,0)'); g.fillStyle = au; g.fillRect(-0.86, -0.86, 1.72, 1.72); });
  });
}

/* ---------------- crate (reliquary chest), drone (bat), throne, rubble ---------------- */
function paintCrate(g, r, open) {
  const col = RAR_COL[r] || RAR_COL[0], band = r === 4 ? PAL.giltHi : col;
  const au = g.createRadialGradient(0, 0.05, 0.05, 0, 0.05, 0.5); au.addColorStop(0, rgba(col, 0.45)); au.addColorStop(1, rgba(col, 0)); g.fillStyle = au; g.fillRect(-0.5, -0.45, 1, 1);
  groundShadow(g, 0.3, 0.3);
  const lid = () => { if (r >= 2) { g.beginPath(); g.moveTo(-0.27, -0.04); g.bezierCurveTo(-0.27, -0.25, 0.27, -0.25, 0.27, -0.04); g.closePath(); } else rrect(g, -0.27, -0.14, 0.54, 0.11, 0.02); };
  if (open) {
    g.beginPath(); g.moveTo(-0.27, -0.06); g.lineTo(-0.25, -0.34); if (r >= 2) g.quadraticCurveTo(0, -0.47, 0.25, -0.34); else g.lineTo(0.25, -0.34); g.lineTo(0.27, -0.06); g.closePath();
    g.fillStyle = linGrad(g, 0, -0.42, 0, -0.06, ['#5a3d24', '#2e1f12']); g.fill(); g.strokeStyle = '#1a100a'; g.lineWidth = 0.022; g.stroke();
    g.fillStyle = band; for (const x of [-0.19, 0.145]) g.fillRect(x, r >= 2 ? -0.39 : -0.34, 0.045, r >= 2 ? 0.33 : 0.28);
  }
  rrect(g, -0.26, -0.04, 0.52, 0.3, 0.03); g.fillStyle = linGrad(g, 0, -0.04, 0, 0.26, ['#7b5634', '#3f2a19']); g.fill(); g.strokeStyle = '#1a100a'; g.lineWidth = 0.022; g.stroke();
  if (open) {
    ellPath(g, 0, -0.04, 0.25, 0.055); g.fillStyle = rgba(PAL.flame, 0.95); g.fill();
    g.beginPath(); g.moveTo(-0.24, -0.04); g.lineTo(-0.34, -0.5); g.lineTo(0.34, -0.5); g.lineTo(0.24, -0.04); g.closePath();
    g.fillStyle = linGrad(g, 0, -0.04, 0, -0.5, [rgba(PAL.flame, 0.85), rgba(col, 0.35), rgba(col, 0)]); g.fill();
    for (let i = 0; i <= r; i++) gemAt(g, (i - r / 2) * 0.1, -0.12 - (i % 2) * 0.07, 0.045, col, '#120a06');
  } else { lid(); g.fillStyle = linGrad(g, 0, -0.24, 0, -0.04, ['#8c6440', '#4f3520']); g.fill(); g.strokeStyle = '#1a100a'; g.lineWidth = 0.022; g.stroke(); }
  g.fillStyle = band; for (const x of [-0.19, 0.145]) g.fillRect(x, open ? -0.04 : -0.18, 0.045, open ? 0.3 : 0.44);
  rrect(g, -0.06, 0, 0.12, 0.12, 0.02); g.fillStyle = col; g.fill(); g.strokeStyle = '#1a100a'; g.lineWidth = 0.015; g.stroke();
  if (!open) for (let i = 0; i <= r; i++) gemAt(g, (i - r / 2) * 0.085, r >= 2 ? -0.22 : -0.175, 0.04, col, '#120a06');
  if (r >= 3) for (const d of [-1, 1]) { poly(g, [[d * 0.26, -0.04], [d * 0.34, -0.12], [d * 0.27, 0.02]]); g.fillStyle = '#c9ccd3'; g.fill(); g.strokeStyle = '#141518'; g.lineWidth = 0.012; g.stroke(); }
  if (r === 4) { g.strokeStyle = 'rgba(255,231,160,0.75)'; g.lineWidth = 0.018; for (let i = 0; i < 9; i++) { const a = -Math.PI + i * Math.PI / 8; g.beginPath(); g.moveTo(Math.cos(a) * 0.33, -0.05 + Math.sin(a) * 0.33); g.lineTo(Math.cos(a) * 0.43, -0.05 + Math.sin(a) * 0.43); g.stroke(); } }
}
function sprCrate(rar, open = false) { return spr(`C|${rar}|${open ? 1 : 0}`, 1.2, g => paintCrate(g, rar, open)); }
// Bat seen from above, head up. flap 0..1 opens the wings; pale = light membrane for dark icon medallions.
function paintBat(g, eye, collar, flap = 1, pale = false) {
  const fl = 0.6 + 0.4 * flap, mem = pale ? '#b9ad94' : '#16131a', body = pale ? '#e2d6bc' : '#1d1a22', rib = pale ? 'rgba(43,33,24,0.55)' : 'rgba(200,190,170,0.28)', edge = pale ? SPR_INK : '#000';
  for (const d of [-1, 1]) {
    g.save(); g.scale(d, fl);
    g.beginPath(); g.moveTo(0.03, -0.06); g.quadraticCurveTo(0.14, -0.2, 0.24, -0.17); g.quadraticCurveTo(0.36, -0.15, 0.45, -0.06);
    g.quadraticCurveTo(0.39, 0.0, 0.36, 0.07); g.quadraticCurveTo(0.31, 0.02, 0.25, 0.05); g.quadraticCurveTo(0.2, 0.0, 0.14, 0.09); g.quadraticCurveTo(0.09, 0.03, 0.03, 0.08); g.closePath();
    g.fillStyle = mem; g.fill(); g.strokeStyle = edge; g.lineWidth = 0.014; g.stroke();
    g.beginPath(); g.moveTo(0.24, -0.17); g.lineTo(0.36, 0.07); g.moveTo(0.24, -0.17); g.lineTo(0.25, 0.05); g.moveTo(0.24, -0.17); g.lineTo(0.14, 0.09); g.moveTo(0.04, -0.06); g.lineTo(0.24, -0.17);
    g.strokeStyle = rib; g.lineWidth = 0.012; g.stroke();
    g.restore();
  }
  ellPath(g, 0, 0.02, 0.055, 0.11); g.fillStyle = body; g.fill(); g.strokeStyle = edge; g.lineWidth = 0.012; g.stroke();
  circPath(g, 0, -0.1, 0.05); g.fillStyle = body; g.fill(); g.stroke();
  for (const d of [-1, 1]) { poly(g, [[d * 0.015, -0.13], [d * 0.045, -0.19], [d * 0.05, -0.12]]); g.fillStyle = body; g.fill(); g.stroke(); }
  for (const d of [-1, 1]) { circPath(g, d * 0.02, -0.105, 0.012); g.fillStyle = eye; g.fill(); }
  g.beginPath(); g.arc(0, -0.08, 0.055, 0.25, Math.PI - 0.25); g.strokeStyle = collar; g.lineWidth = 0.02; g.stroke();
}
function sprDrone(side, frame = 0) {
  const fr = frame & 3;
  return spr(`D|${side}|${fr}`, 1.0, g => {
    paintBat(g, skinOf(side).tHi, skinOf(side).t, Math.abs(Math.sin(fr / 4 * Math.PI + 0.4)));
    keyline(g, Math.max(1, CS * DPR * 0.016), 'rgba(214,204,180,0.6)');
    paintBehind(g, () => { ellPath(g, 0, 0.3, 0.22, 0.06); g.fillStyle = 'rgba(0,0,0,0.35)'; g.fill(); });
  });
}
// Per-side shape emblem, the same shapes as the HUD's EMB: A heater shield with a crescent, B roundel with a flame (works without colour).
const EMB_PATH = [['M2 1.5h16v8.5c0 5.6-3.7 8.8-8 10.5-4.3-1.7-8-4.9-8-10.5z', 'M12.4 5.6A4.6 4.6 0 0 0 12.4 14.8 5.8 5.8 0 0 1 12.4 5.6z'],
  ['M18.6 11a8.6 8.6 0 1 1-17.2 0 8.6 8.6 0 1 1 17.2 0z', 'M10 4.6c.7 2.5 3.7 3.7 3.7 7.2a3.7 3.7 0 0 1-7.4 0c0-1.7.8-2.7 1.8-3.4-.1 1.3.4 2.3 1.2 2.7-.4-2.3.2-4.5.7-6.5z']];
function paintEmblem(g, s, r = 0.2) {
  const m = skinOf(s), [body, charge] = EMB_PATH[s === 1 ? 1 : 0].map(d => new Path2D(d));
  g.save(); g.scale(r / 9, r / 9); g.translate(-10, -11);
  g.fillStyle = linGrad(g, 0, 2, 0, 20, [m.tHi, m.t, m.tLo]); g.fill(body);
  g.strokeStyle = m.ink; g.lineWidth = 1.6; g.stroke(body);
  g.fillStyle = s === 1 ? PAL.flame : MAT[0].hi; g.fill(charge); g.lineWidth = 0.7; g.stroke(charge);
  g.restore();
}
// Throne tapestry hanging from a gilt rod at (x, y): A cut straight, B swallow-tailed (a side cue without colour).
function paintBanner(g, s, x, y, w, h) {
  const m = skinOf(s), l = x - w / 2, r = x + w / 2;
  g.beginPath(); g.moveTo(l, y); g.lineTo(r, y); g.lineTo(r, y + h);
  if (s === 1) g.lineTo(x, y + h - w * 0.42);
  g.lineTo(l, y + h); g.closePath();
  g.fillStyle = linGrad(g, l, 0, r, 0, [m.tLo, m.t, m.tHi, m.t, m.tLo]); g.fill(); g.strokeStyle = m.ink; g.lineWidth = 0.025; g.stroke();
  g.fillStyle = s === 1 ? MAT[1].mid : MAT[0].hi; for (const k of [0.07, h - (s === 1 ? w * 0.42 : 0) - 0.09]) g.fillRect(l + 0.03, y + k, w - 0.06, 0.03);
  g.beginPath(); g.moveTo(l - 0.05, y); g.lineTo(r + 0.05, y); g.strokeStyle = SPR_INK; g.lineWidth = 0.06; g.stroke(); g.strokeStyle = PAL.gilt; g.lineWidth = 0.03; g.stroke();
  for (const d of [l - 0.05, r + 0.05]) { circPath(g, d, y, 0.03); g.fillStyle = PAL.giltHi; g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.012; g.stroke(); }
}
function paintThrone(g, s) {
  const m = skinOf(s);
  groundShadow(g, 0.42, 0.78);
  poly(g, [[-0.32, 0.76], [-0.32, -0.45], [-0.24, -0.8], [0, -1.0], [0.24, -0.8], [0.32, -0.45], [0.32, 0.76]]); solidFill(g, s, -1.0, 0.76, 0.035);
  paintBanner(g, s, 0, -0.64, 0.42, 0.78);
  g.save(); g.translate(0, -0.3); paintEmblem(g, s, 0.14); g.restore();
  rrect(g, -0.42, 0.2, 0.84, 0.2, 0.04); solidFill(g, s, 0.2, 0.4, 0.03);
  rrect(g, -0.36, 0.4, 0.72, 0.36, 0.03); solidFill(g, s, 0.4, 0.76, 0.03);
  g.fillStyle = m.t; g.fillRect(-0.34, 0.5, 0.68, 0.05);
  for (const d of [-1, 1]) paintSkull(g, d * 0.32, -0.54, 0.075);
  paintCrown(g, 0, -0.98, 0.9);
}
function sprThrone(side) { return spr('TH|' + side, 2.4, g => paintThrone(g, side)); }
function paintRubble(g, seed) {
  groundShadow(g, 0.42, 0.3);
  for (let i = 0; i < 5; i++) {
    const bx = -0.3 + hash(seed, i, 1) * 0.42, by = -0.2 + hash(seed, i, 2) * 0.34, bw = 0.18 + hash(seed, i, 3) * 0.16, bh = 0.13 + hash(seed, i, 4) * 0.1;
    rrect(g, bx, by, bw, bh, 0.02); g.fillStyle = linGrad(g, bx, by, bx + bw, by + bh, ['#77706a', '#3a3530']); g.fill(); g.strokeStyle = '#151210'; g.lineWidth = 0.02; g.stroke();
    g.fillStyle = 'rgba(255,240,210,0.18)'; g.fillRect(bx + 0.01, by + 0.01, bw - 0.02, 0.015);
  }
  ellPath(g, 0.12, 0.12, 0.13, 0.07, 0.3); g.fillStyle = '#8a837a'; g.fill(); g.strokeStyle = '#151210'; g.lineWidth = 0.02; g.stroke();
  paintSkull(g, -0.18, 0.12, 0.065);
}
function sprRubble(seed) { return spr('RB|' + seed, 1, g => paintRubble(g, seed)); }

/* ---------------- live (per-frame) building details ---------------- */
// Draw with g already transformed to the building's cell space (origin = cell centre, 1 unit = 1 cell); the caller's alpha is respected.
function liveFlame(g, x, y, s, now, seed) {
  const f = 0.85 + 0.15 * Math.sin(now / 90 + seed) + 0.08 * Math.sin(now / 37 + seed * 3), sw = Math.sin(now / 130 + seed * 2) * s * 0.15, A = g.globalAlpha;
  g.globalAlpha = A * 0.5; g.drawImage(softSpr(PAL.candle), x - s * 3, y - s * 3.4, s * 6, s * 6); g.globalAlpha = A;
  g.beginPath(); g.moveTo(x + sw, y - s * 1.6 * f); g.quadraticCurveTo(x + s * 0.7, y - s * 0.2, x, y + s * 0.3); g.quadraticCurveTo(x - s * 0.7, y - s * 0.2, x + sw, y - s * 1.6 * f);
  g.fillStyle = '#ff9a3c'; g.fill();
  g.beginPath(); g.moveTo(x + sw * 0.6, y - s * 0.9 * f); g.quadraticCurveTo(x + s * 0.35, y - s * 0.05, x, y + s * 0.2); g.quadraticCurveTo(x - s * 0.35, y - s * 0.05, x + sw * 0.6, y - s * 0.9 * f);
  g.fillStyle = PAL.flame; g.fill();
}
function liveBuilding(g, e, now) {
  const k = e.kind, f = sideFace(e.side), seed = (e.id || 0) * 1.7, A = g.globalAlpha;
  g.save();
  if (k === 'gen') {
    g.globalCompositeOperation = 'lighter';
    for (const [x, h, w] of candleLayout(e.lvl, e.path)) liveFlame(g, x, 0.07 - h, w * 0.5, now, seed + x * 10);
  } else if (k === 'hlaska') {
    const b = e.path === 'B', r = b ? 1.7 : 1.3, w = b ? 0.45 : 0.3, a = (f > 0 ? 0 : Math.PI) + Math.sin(now / 1400 + seed) * 0.3, y = b ? -0.34 : -0.3;
    g.globalCompositeOperation = 'lighter';
    const gr = g.createRadialGradient(0, y, 0, 0, y, r); gr.addColorStop(0, 'rgba(255,200,120,0.35)'); gr.addColorStop(1, 'rgba(255,200,120,0)');
    g.fillStyle = gr; g.beginPath(); g.moveTo(0, y); g.arc(0, y, r, a - w, a + w); g.closePath(); g.fill();
    g.globalAlpha = A * (0.6 + 0.1 * Math.sin(now / 80 + seed)); g.drawImage(softSpr(PAL.candle), -0.3, y - 0.3, 0.6, 0.6);
  } else if (k === 'rusicka') {
    paintBell(g, e.path, Math.sin(now / 420 + seed) * 0.14);
    const t = (now / 1600 + seed) % 1, reach = e.path === 'B' ? 2.4 : e.lvl >= 2 ? 2.0 : 1.6;
    g.globalAlpha = A * 0.35 * (1 - t); g.strokeStyle = PAL.mist; g.lineWidth = 0.025;
    for (const d of [0, 0.12]) { g.beginPath(); g.arc(0, -0.05, 0.3 + (t * reach + d), 0, TAU); g.stroke(); }
  } else if (k === 'tesla') {
    const t = Math.floor(now / 60), y = -0.38;
    g.globalCompositeOperation = 'lighter';
    g.globalAlpha = A * (0.55 + 0.25 * hash(t, seed | 0, 1)); g.drawImage(softSpr(PAL.ghostD), -0.3, y - 0.3, 0.6, 0.6); g.globalAlpha = A;
    g.beginPath();
    for (let i = 0; i < 2; i++) {
      const a = hash(t, i, seed | 0) * TAU, L = 0.12 + hash(i, t, 5) * 0.1; let x = 0, yy = y; g.moveTo(x, yy);
      for (let j = 1; j <= 3; j++) { x = Math.cos(a) * L * j / 3 + (hash(t, i, j) - 0.5) * 0.06; yy = y + Math.sin(a) * L * j / 3 + (hash(j, t, i) - 0.5) * 0.06; g.lineTo(x, yy); }
    }
    g.strokeStyle = 'rgba(123,95,208,0.7)'; g.lineWidth = 0.05; g.stroke(); g.strokeStyle = '#f2ecff'; g.lineWidth = 0.016; g.stroke();
  } else if (k === 'plamen') {
    g.globalCompositeOperation = 'lighter'; g.scale(f, 1);
    g.globalAlpha = A * (0.45 + 0.15 * Math.sin(now / 70 + seed)); g.drawImage(softSpr('#ff9a3c'), 0.12, -0.27, 0.3, 0.3); g.globalAlpha = A;
    g.save(); g.translate(0.33, -0.13); g.rotate(Math.PI / 2); liveFlame(g, 0, 0, 0.03, now, seed); g.restore();
  }
  g.restore();
}

/* ---------------- icons ---------------- */
// Motif painters in icon space: centre (0,0), radius about 0.5. Bone and gilt matter on a dark medallion; col is the accent.
const MOTIF = {
  nalet(g) {
    for (const [x, y, r] of [[-0.02, -0.28, 0.07], [0.2, -0.04, 0.09], [-0.18, 0.2, 0.12]]) {
      g.beginPath(); g.moveTo(x - r * 0.7, y - r * 0.7); g.lineTo(x + r * 3.4, y - r * 3.4); g.lineTo(x + r * 0.7, y + r * 0.7); g.closePath();
      g.fillStyle = linGrad(g, x, y, x + r * 3, y - r * 3, ['#fff1c4', '#ff9a3c', 'rgba(194,59,46,0)']); g.fill();
      circPath(g, x, y, r); g.fillStyle = linGrad(g, x - r, y - r, x + r, y + r, ['#6a5548', '#2a201b']); g.fill(); g.strokeStyle = SPR_INK; g.lineWidth = 0.02; g.stroke();
      circPath(g, x - r * 0.25, y + r * 0.2, r * 0.3); g.fillStyle = PAL.candle; g.fill();
    }
  },
  vypadek(g) {
    rrect(g, -0.1, -0.12, 0.2, 0.46, 0.04); solidFill(g, 2, -0.12, 0.34, 0.025);
    ellPath(g, 0, -0.12, 0.1, 0.03); g.fillStyle = MAT[0].mid; g.fill();
    g.beginPath(); g.moveTo(0, -0.12); g.lineTo(0.01, -0.18); g.strokeStyle = SPR_INK; g.lineWidth = 0.025; g.stroke();
    g.beginPath(); g.moveTo(0.01, -0.19); g.bezierCurveTo(0.14, -0.26, -0.1, -0.33, 0.04, -0.4); g.bezierCurveTo(0.12, -0.44, 0.06, -0.48, 0.0, -0.47);
    g.strokeStyle = PAL.muted; g.lineWidth = 0.035; g.stroke();
    g.beginPath(); g.moveTo(-0.3, 0.38); g.lineTo(0.3, 0.38); g.strokeStyle = PAL.giltLo; g.lineWidth = 0.04; g.stroke();
  },
  karantena(g) {
    g.strokeStyle = PAL.ironL; g.lineWidth = 0.04;
    for (const x of [-0.38, -0.26, 0.26, 0.38]) { ellPath(g, x, 0.08, 0.075, 0.04); g.stroke(); }
    g.beginPath(); g.arc(0, -0.08, 0.13, Math.PI, TAU); g.lineTo(0.13, 0.02); g.moveTo(-0.13, -0.08); g.lineTo(-0.13, 0.02); g.strokeStyle = SPR_INK; g.lineWidth = 0.08; g.stroke(); g.strokeStyle = PAL.ironL; g.lineWidth = 0.05; g.stroke();
    rrect(g, -0.2, -0.02, 0.4, 0.32, 0.05); g.fillStyle = linGrad(g, 0, -0.02, 0, 0.3, [PAL.giltHi, PAL.gilt, PAL.giltLo]); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.025; g.stroke();
    circPath(g, 0, 0.1, 0.04); g.fillStyle = GILT_INK; g.fill(); poly(g, [[-0.025, 0.11], [0.025, 0.11], [0.035, 0.22], [-0.035, 0.22]]); g.fill();
  },
  navnada(g) {
    circPath(g, 0, -0.38, 0.05); g.strokeStyle = PAL.bronze; g.lineWidth = 0.03; g.stroke();
    g.beginPath(); g.moveTo(0, -0.33); g.lineTo(0, 0.12); g.arc(-0.12, 0.12, 0.12, 0, Math.PI * 0.95); g.lineTo(-0.26, 0.02);
    g.strokeStyle = SPR_INK; g.lineWidth = 0.075; g.stroke(); g.strokeStyle = linGrad(g, -0.3, 0, 0.1, 0, ['#e2c27a', PAL.bronze]); g.lineWidth = 0.045; g.stroke();
    g.beginPath(); g.moveTo(-0.05, -0.1); g.bezierCurveTo(0.12, -0.2, 0.32, -0.1, 0.3, 0.08); g.bezierCurveTo(0.28, 0.24, 0.08, 0.28, 0.02, 0.12); g.closePath();
    g.fillStyle = linGrad(g, 0, -0.2, 0.3, 0.2, ['#b5463c', '#7a1f1a']); g.fill(); g.strokeStyle = '#2a0c08'; g.lineWidth = 0.02; g.stroke();
    g.beginPath(); g.moveTo(0.06, -0.08); g.quadraticCurveTo(0.2, -0.06, 0.24, 0.08); g.strokeStyle = 'rgba(240,200,180,0.7)'; g.lineWidth = 0.025; g.stroke();
  },
  dron(g) { g.save(); g.scale(1.05, 1.05); paintBat(g, PAL.rubric, PAL.gilt, 1, true); g.restore(); },
  sber(g) {
    g.save(); g.translate(0, -0.08); paintBat(g, PAL.rubric, PAL.gilt, 1, true); g.restore();
    g.beginPath(); g.moveTo(0, 0.04); g.lineTo(0, 0.12); g.strokeStyle = PAL.giltLo; g.lineWidth = 0.02; g.stroke();
    g.beginPath(); g.moveTo(-0.06, 0.13); g.quadraticCurveTo(-0.17, 0.38, 0, 0.38); g.quadraticCurveTo(0.17, 0.38, 0.06, 0.13); g.closePath();
    g.fillStyle = linGrad(g, 0, 0.12, 0, 0.38, ['#a0764a', '#5e4126']); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.02; g.stroke();
    g.fillStyle = PAL.giltHi; g.fillRect(-0.07, 0.12, 0.14, 0.035);
  },
  mobilizace(g) {
    g.beginPath(); g.moveTo(-0.42, 0.16); g.quadraticCurveTo(-0.02, 0.5, 0.36, -0.06); g.lineTo(0.14, -0.26); g.quadraticCurveTo(-0.04, 0.24, -0.4, 0.08); g.closePath();
    solidFill(g, 2, -0.26, 0.4, 0.025);
    g.strokeStyle = PAL.gilt; g.lineWidth = 0.05;
    for (const [x0, y0, x1, y1] of [[-0.2, 0.15, -0.23, 0.29], [0.04, 0.12, 0.08, 0.27]]) { g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); }
    ellPath(g, 0.25, -0.16, 0.15, 0.06, 0.74); g.fillStyle = MAT[0].lo; g.fill(); g.strokeStyle = SPR_INK; g.lineWidth = 0.025; g.stroke();
    g.strokeStyle = PAL.giltHi; g.lineWidth = 0.035; for (const r of [0.14, 0.24]) { g.beginPath(); g.arc(0.27, -0.18, r, -2.1, -0.5); g.stroke(); }
  },
  oprava(g) {
    g.save(); g.rotate(-0.75);
    rrect(g, -0.04, -0.12, 0.08, 0.56, 0.03); g.fillStyle = linGrad(g, -0.04, 0, 0.04, 0, ['#8a6240', PAL.woodD]); g.fill(); g.strokeStyle = '#1e140c'; g.lineWidth = 0.02; g.stroke();
    rrect(g, -0.22, -0.32, 0.44, 0.18, 0.03); g.fillStyle = linGrad(g, 0, -0.32, 0, -0.14, ['#b8bcc4', '#5a5d63', '#3d4045']); g.fill(); g.strokeStyle = '#141518'; g.lineWidth = 0.025; g.stroke();
    g.fillStyle = PAL.gilt; g.fillRect(-0.05, -0.15, 0.1, 0.05);
    g.restore();
  },
  odstrel(g) {
    g.beginPath(); for (let i = 0; i < 16; i++) { const a = i / 16 * TAU, r = i % 2 ? 0.2 : 0.46; g.lineTo(Math.cos(a) * r, Math.sin(a) * r); } g.closePath();
    g.fillStyle = linGrad(g, 0, -0.46, 0, 0.46, [PAL.flame, '#ff9a3c', PAL.rubric]); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.02; g.stroke();
    circPath(g, 0, 0.02, 0.2); g.fillStyle = linGrad(g, -0.15, -0.15, 0.15, 0.2, ['#6a6d74', '#26282c', '#0e0f11']); g.fill(); g.strokeStyle = SPR_INK; g.lineWidth = 0.025; g.stroke();
    circPath(g, -0.07, -0.05, 0.045); g.fillStyle = 'rgba(255,255,255,0.35)'; g.fill();
  },
  stit(g) {
    g.beginPath(); g.moveTo(-0.32, -0.3); g.lineTo(0.32, -0.3); g.lineTo(0.32, 0.02); g.quadraticCurveTo(0.29, 0.3, 0, 0.44); g.quadraticCurveTo(-0.29, 0.3, -0.32, 0.02); g.closePath();
    g.fillStyle = linGrad(g, 0, -0.3, 0, 0.44, ['#5a4a35', '#2f231c']); g.fill(); g.strokeStyle = PAL.gilt; g.lineWidth = 0.05; g.stroke();
    paintCrown(g, 0, 0.05, 1.5);
  },
  utok(g) {
    for (const d of [-1, 1]) {
      g.save(); g.scale(d, 1); g.rotate(-Math.PI / 4);
      poly(g, [[-0.035, -0.44], [0, -0.5], [0.035, -0.44], [0.035, 0.18], [-0.035, 0.18]]); g.fillStyle = linGrad(g, -0.04, 0, 0.04, 0, ['#eef0f3', '#9a9ea6']); g.fill(); g.strokeStyle = SPR_INK; g.lineWidth = 0.02; g.stroke();
      rrect(g, -0.13, 0.17, 0.26, 0.05, 0.02); g.fillStyle = PAL.gilt; g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.015; g.stroke();
      rrect(g, -0.025, 0.22, 0.05, 0.14, 0.02); g.fillStyle = PAL.wood; g.fill(); g.stroke();
      circPath(g, 0, 0.39, 0.04); g.fillStyle = PAL.giltHi; g.fill(); g.stroke();
      g.restore();
    }
  },
  horde(g) {
    ellPath(g, 0, 0.02, 0.3, 0.36); g.fillStyle = linGrad(g, -0.3, -0.3, 0.3, 0.4, [PAL.fleshL, PAL.flesh, PAL.fleshD]); g.fill(); g.strokeStyle = PAL.zInk; g.lineWidth = 0.035; g.stroke();
    ellPath(g, -0.12, -0.04, 0.08, 0.07); g.fillStyle = PAL.zInk; g.fill();
    circPath(g, 0.12, -0.04, 0.07); g.fillStyle = PAL.zInk; g.fill(); circPath(g, 0.12, -0.04, 0.035); g.fillStyle = PAL.eye; g.fill();
    g.beginPath(); g.moveTo(-0.14, 0.2); g.lineTo(0.14, 0.18); g.strokeStyle = PAL.zInk; g.lineWidth = 0.03; g.stroke();
    g.beginPath(); for (let i = 0; i < 5; i++) { const x = -0.12 + i * 0.06; g.moveTo(x, 0.15); g.lineTo(x, 0.24); } g.lineWidth = 0.018; g.stroke();
    g.beginPath(); g.moveTo(-0.24, -0.22); g.lineTo(-0.1, -0.12); g.moveTo(0.02, -0.36); g.lineTo(0.0, -0.22); g.strokeStyle = 'rgba(29,34,22,0.6)'; g.lineWidth = 0.025; g.stroke();
  },
  kral(g) { paintCrown(g, 0, 0.1, 2.6); },
  vzorek(g, c, liquid = PAL.amethyst) {
    g.beginPath(); g.moveTo(-0.07, -0.42); g.lineTo(0.07, -0.42); g.lineTo(0.07, -0.12); g.bezierCurveTo(0.3, -0.06, 0.36, 0.36, 0, 0.4); g.bezierCurveTo(-0.36, 0.36, -0.3, -0.06, -0.07, -0.12); g.closePath();
    g.fillStyle = 'rgba(214,204,180,0.18)'; g.fill();
    g.save(); g.clip(); g.fillStyle = linGrad(g, 0, 0.05, 0, 0.4, [liquid, mix(liquid, '#000000', 0.45)]); g.fillRect(-0.4, 0.05, 0.8, 0.4); g.restore();
    g.strokeStyle = SPR_INK; g.lineWidth = 0.055; g.stroke(); g.strokeStyle = PAL.bone; g.lineWidth = 0.025; g.stroke();
    g.beginPath(); g.moveTo(-0.1, -0.42); g.lineTo(0.1, -0.42); g.strokeStyle = PAL.gilt; g.lineWidth = 0.05; g.stroke();
    ellPath(g, -0.12, 0.12, 0.04, 0.08, 0.4); g.fillStyle = 'rgba(255,255,255,0.4)'; g.fill();
  },
  conv(g) {
    g.save(); g.translate(-0.17, -0.12); g.scale(0.55, 0.55); MOTIF.e(g); g.restore();
    g.save(); g.translate(0.17, 0.17); g.scale(0.6, 0.6); MOTIF.s(g); g.restore();
    g.beginPath(); g.arc(-0.04, 0.06, 0.32, Math.PI * 0.62, Math.PI * 0.98); g.strokeStyle = PAL.giltHi; g.lineWidth = 0.04; g.stroke();
    poly(g, [[-0.25, 0.32], [-0.08, 0.36], [-0.2, 0.22]]); g.fillStyle = PAL.giltHi; g.fill();
  },
  relic(g) {
    poly(g, [[0, -0.46], [0.42, 0], [0, 0.46], [-0.42, 0]]); g.fillStyle = linGrad(g, 0, -0.46, 0, 0.46, ['#3a2c22', '#160f0b']); g.fill(); g.strokeStyle = PAL.gilt; g.lineWidth = 0.045; g.stroke();
    for (const [x, y] of [[0, -0.46], [0.42, 0], [0, 0.46], [-0.42, 0]]) gemAt(g, x, y, 0.06, PAL.giltHi);
    paintSkull(g, 0, -0.05, 0.17);
  },
  eclipse(g) {
    g.strokeStyle = PAL.giltHi; g.lineWidth = 0.035;
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU, r0 = 0.3, r1 = i % 2 ? 0.4 : 0.47; g.beginPath(); g.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); g.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); g.stroke(); }
    circPath(g, 0, 0, 0.26); g.fillStyle = linGrad(g, 0, -0.26, 0, 0.26, [PAL.flame, PAL.candle]); g.fill();
    circPath(g, 0.05, -0.03, 0.24); g.fillStyle = '#0d0a08'; g.fill(); g.strokeStyle = 'rgba(185,195,214,0.5)'; g.lineWidth = 0.015; g.stroke();
  },
  ult(g) {
    g.beginPath(); g.moveTo(-0.3, -0.44); g.lineTo(-0.3, 0.44); g.strokeStyle = SPR_INK; g.lineWidth = 0.07; g.stroke(); g.strokeStyle = PAL.giltLo; g.lineWidth = 0.04; g.stroke();
    circPath(g, -0.3, -0.45, 0.045); g.fillStyle = PAL.giltHi; g.fill();
    g.beginPath(); g.moveTo(-0.28, -0.38); g.lineTo(0.12, -0.38); g.quadraticCurveTo(0.05, -0.26, 0.12, -0.12); g.lineTo(-0.28, -0.12); g.closePath();
    g.fillStyle = linGrad(g, 0, -0.38, 0, -0.12, ['#d4473a', PAL.rubricD]); g.fill(); g.strokeStyle = SPR_INK; g.lineWidth = 0.02; g.stroke();
    g.strokeStyle = PAL.giltHi; g.lineWidth = 0.035;
    for (const r of [0.14, 0.25, 0.36]) { g.beginPath(); g.arc(-0.02, 0.12, r, -0.7, 0.7); g.stroke(); }
  },
  dash(g) {
    poly(g, [[0.44, 0], [0.12, -0.2], [0.18, -0.07], [-0.1, -0.07], [-0.1, 0.07], [0.18, 0.07], [0.12, 0.2]]);
    g.fillStyle = linGrad(g, 0, -0.2, 0, 0.2, [PAL.giltHi, PAL.gilt, PAL.giltLo]); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.025; g.stroke();
    g.strokeStyle = PAL.bone; g.lineCap = 'round';
    for (const [y, x0, w] of [[-0.24, -0.42, 0.05], [0, -0.44, 0.06], [0.24, -0.42, 0.05]]) { g.beginPath(); g.moveTo(x0, y); g.lineTo(x0 + (y ? 0.36 : 0.26), y); g.lineWidth = w; g.stroke(); }
  },
  e(g) {
    rrect(g, -0.11, 0.08, 0.22, 0.34, 0.04); solidFill(g, 2, 0.08, 0.42, 0.02);
    g.beginPath(); g.moveTo(0, -0.46); g.bezierCurveTo(0.24, -0.2, 0.2, 0.02, 0, 0.04); g.bezierCurveTo(-0.2, 0.02, -0.24, -0.2, 0, -0.46);
    g.fillStyle = '#ff9a3c'; g.fill(); g.strokeStyle = '#5a2a0c'; g.lineWidth = 0.02; g.stroke();
    g.beginPath(); g.moveTo(0, -0.22); g.bezierCurveTo(0.1, -0.1, 0.09, 0.0, 0, 0.02); g.bezierCurveTo(-0.09, 0.0, -0.1, -0.1, 0, -0.22); g.fillStyle = PAL.flame; g.fill();
  },
  s(g) {
    g.beginPath();
    for (let i = 0; i < 8; i++) { const a = i / 8 * TAU; for (const [da, r] of [[-0.2, 0.3], [-0.12, 0.44], [0.12, 0.44], [0.2, 0.3]]) g.lineTo(Math.cos(a + da) * r, Math.sin(a + da) * r); }
    g.closePath(); g.moveTo(0.13, 0); g.arc(0, 0, 0.13, 0, TAU, true);
    g.fillStyle = linGrad(g, -0.4, -0.4, 0.4, 0.4, ['#eef0f3', '#c9ccd3', '#6a6d74']); g.fill(); g.strokeStyle = '#141518'; g.lineWidth = 0.03; g.stroke();
  },
  v(g) { MOTIF.vzorek(g, null, '#b99ae6'); },
  g(g) {
    g.beginPath(); for (let i = 0; i < 24; i++) { const a = i / 24 * TAU, r = i % 2 ? 0.4 : 0.46; g.lineTo(Math.cos(a) * r, Math.sin(a) * r); } g.closePath();
    g.fillStyle = linGrad(g, 0, -0.46, 0, 0.46, ['#d4473a', PAL.rubricD]); g.fill(); g.strokeStyle = '#3d0c08'; g.lineWidth = 0.025; g.stroke();
    g.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 0.12 : 0.3; g.lineTo(Math.cos(a) * r, Math.sin(a) * r); } g.closePath();
    g.fillStyle = linGrad(g, 0, -0.3, 0, 0.3, [PAL.giltHi, PAL.gilt]); g.fill(); g.strokeStyle = GILT_INK; g.lineWidth = 0.02; g.stroke();
  },
  side0(g) { paintEmblem(g, 0, 0.36); },
  side1(g) { paintEmblem(g, 1, 0.38); },
};
// Motif for any id: card/command/resource painters, otherwise the board sprite painters in the neutral icon skin.
function paintMotif(g, id, col) {
  if (MOTIF[id]) return MOTIF[id](g, col);
  const d = S.defs && S.defs[id], cat = d ? d.cat : PIECE[id] ? 'u' : ZR[id] ? 'z' : BUILD[id] || id === 'zed' || id === 'mina' ? 'b' : '';
  if (cat === 'b') {
    paintBuilding(g, id, 2, 1, '', 1, true);
    if (BARREL_OY[id] !== undefined) { g.save(); g.translate(0, BARREL_OY[id]); g.scale(1, 0.75); g.rotate(-0.35); paintBarrel(g, id, 2, ''); g.restore(); }
  }
  else if (cat === 'u') paintPiece(g, id, 2, false, 1);
  else if (cat === 'z') { zombieFrame(g, id, 0, 1, 'body'); zombieFrame(g, id, 0, 1, 'eye'); }
  else if (cat === 'k') paintKing(g, 2, 1);
  else sprText(g, '?', 0, 0, 0.7, PAL.giltHi);
}
// Renders a motif and scales it so its opaque box fills `box` px, centred in a box x box canvas.
function motifCanvas(id, col, box, line) {
  const R = box * 2, [c, g] = cpuCanvas(R, R);
  g.setTransform(box, 0, 0, box, R / 2, R / 2); g.lineJoin = 'round'; g.lineCap = 'round';
  paintMotif(g, id, col);
  const [x0, y0, x1, y1] = opaqueBox(c), w = x1 - x0, h = y1 - y0, k = Math.min(box / Math.max(w, h, 1), box * 1.22 / Math.hypot(w, h));
  const [out, og] = cpuCanvas(box, box);
  og.imageSmoothingQuality = 'high';
  og.drawImage(c, x0, y0, w, h, (box - w * k) / 2, (box - h * k) / 2, w * k, h * k);
  if (line) keyline(og, Math.max(1, box * 0.03), line);
  return out;
}
function paintMedallion(g, col) {
  circPath(g, 0, 0, 0.49); g.fillStyle = SPR_INK; g.fill();
  circPath(g, 0, 0, 0.455); const gr = g.createRadialGradient(-0.12, -0.15, 0.02, 0, 0, 0.46); gr.addColorStop(0, '#33281f'); gr.addColorStop(1, '#100b09'); g.fillStyle = gr; g.fill();
  g.lineWidth = 0.055; g.strokeStyle = col; g.stroke();
  circPath(g, 0, 0, 0.395); g.lineWidth = 0.012; g.strokeStyle = rgba(PAL.giltHi, 0.22); g.stroke();
}
const ICON_URL = new Map();
// Icon as a data URL for the UI: a dark enamel medallion, `col` ring, motif in bone/gilt.
function iconImg(id, col) {
  const key = id + '|' + col;
  let url = ICON_URL.get(key);
  if (url) return url;
  const P = 96, [c, g] = cpuCanvas(P, P);
  g.setTransform(P, 0, 0, P, P / 2, P / 2); paintMedallion(g, col || PAL.gilt);
  const box = Math.round(P * 0.7);
  g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(motifCanvas(id, col, box), (P - box) / 2, (P - box) / 2);
  url = c.toDataURL();
  ICON_URL.set(key, url);
  return url;
}
function iconTag(id, col, cls = '') { return `<img class="ico ${cls}" src="${iconImg(id, col)}" alt="">`; }
const cardCol = k => (S.defs && S.defs[k] && CAT_COL[S.defs[k].cat]) || PAL.gilt;
// Board icon sprite: the motif with a keyline in col (or inside a medallion when medal is true).
function sprIcon(id, col, size, medal = false) {
  return spr(`I|${id}|${col}|${medal ? 1 : 0}`, size, g => {
    const c = g.canvas, P = c.width;
    if (medal) { g.save(); g.setTransform(P, 0, 0, P, P / 2, P / 2); paintMedallion(g, col); g.restore(); }
    const box = Math.round(P * (medal ? 0.7 : 0.92));
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(motifCanvas(id, col, box, medal ? null : col || SPR_INK), (P - box) / 2, (P - box) / 2); g.restore();
  });
}
