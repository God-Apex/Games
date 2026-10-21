'use strict';
/* ---------------- geometry ---------------- */
const cv = $('#cv'), ctx = cv.getContext('2d');
// DPR is the render scale RS (device pixels per CSS pixel of the canvas), set by the quality level; the browser upscales.
let CS = 40, OX = 0, OY = 0, DPR = 1;
function resize() {
  const r = cv.getBoundingClientRect();
  DPR = renderScale(r.width, r.height);
  cv.width = Math.max(1, Math.round(r.width * DPR)); cv.height = Math.max(1, Math.round(r.height * DPR));
  const cols = S.W + 2;
  CS = Math.floor(Math.min(r.width / cols, r.height / S.H));
  OX = Math.floor((r.width - CS * cols) / 2); OY = Math.floor((r.height - CS * S.H) / 2);
  SPR.clear(); BOARD_KEY = ''; FOG_KEY = ''; VIG.clear(); THR.length = 0; FXS.scarT = 0;
}

/* ---------------- render quality: Q2 Vysoká, Q1 Střední, Q0 Nízká; hmk_opt.q = 'auto'|2|1|0 ---------------- */
// Automaticky starts a match at the level saved in hmk_qa ({q, n}), steps down when the median frame is over 18 ms and
// never steps up during a match; every 5th match starts one level higher to re-probe. ?q=0|1|2 pins a level (dev).
const QUAL = { lvl: 2, auto: true, iv: [], chk: 0, prev: 0, pin: /^[012]$/.test(new URLSearchParams(location.search).get('q') || '') ? +new URLSearchParams(location.search).get('q') : null };
const RAWOPT = { o: {}, t: -1e9 };
// an hmk_opt key: OPT/S.opt first (loadOpt in base.js), then the stored object (keys loadOpt does not validate yet)
function ropt(k, d) {
  const o = (typeof OPT !== 'undefined' && OPT) || S.opt || {};
  if (o[k] !== undefined) return o[k];
  const now = performance.now();
  if (now - RAWOPT.t > 1000) { RAWOPT.t = now; try { RAWOPT.o = JSON.parse(load('hmk_opt', '{}')) || {}; } catch (e) { RAWOPT.o = {}; } }
  return RAWOPT.o[k] !== undefined ? RAWOPT.o[k] : d;
}
function qualMode() { const q = ropt('q', 'auto'); return q === 0 || q === 1 || q === 2 ? q : /^[012]$/.test(q) ? +q : 'auto'; }
function renderScale(w, h) {
  const d = window.devicePixelRatio || 1;
  return QUAL.lvl >= 2 ? Math.min(d, 2, Math.sqrt(2.2e6 / Math.max(1, w * h))) : QUAL.lvl === 1 ? Math.min(d, 1) : 0.75;
}
function setQual(l) {
  QUAL.iv.length = 0; QUAL.chk = performance.now();
  pMax = l === 0 ? 300 : PMAX;
  if (l !== QUAL.lvl) { QUAL.lvl = l; if (S.inGame) resize(); }
}
function loadQA() { try { const v = JSON.parse(load('hmk_qa', '{}')) || {}; return { q: [0, 1, 2].includes(v.q) ? v.q : 2, n: v.n | 0 }; } catch (e) { return { q: 2, n: 0 }; } }
// first snapshot of a match
function qualityStart() {
  RAWOPT.t = -1e9;
  const q = QUAL.pin !== null ? QUAL.pin : qualMode();
  QUAL.auto = q === 'auto';
  if (!QUAL.auto) { setQual(q); return; }
  const qa = loadQA(), n = qa.n + 1;
  const lvl = n % 5 === 0 && qa.q < 2 ? qa.q + 1 : qa.q;
  save('hmk_qa', JSON.stringify({ q: lvl, n }));
  setQual(lvl);
}
// settings changed mid-match (M4-C): a fixed level applies at once, Automaticky keeps the current level
function qualityApply() {
  RAWOPT.t = -1e9;
  const q = QUAL.pin !== null ? QUAL.pin : qualMode();
  QUAL.auto = q === 'auto';
  setQual(QUAL.auto ? QUAL.lvl : q);
}
const median = a => { if (!a.length) return 0; const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; };
function qualityWatch(now) {
  const dt = now - QUAL.prev; QUAL.prev = now;
  if (dt > 0 && dt < 250) { QUAL.iv.push(dt); if (QUAL.iv.length > 120) QUAL.iv.shift(); }
  if (!QUAL.auto || now - QUAL.chk < 2000) return;
  QUAL.chk = now;
  if (document.visibilityState !== 'visible' || FXS.fin || QUAL.iv.length < 120 || QUAL.lvl === 0 || median(QUAL.iv) <= 18) return;
  const l = QUAL.lvl - 1;
  save('hmk_qa', JSON.stringify({ q: l, n: loadQA().n }));
  setQual(l);
  if (typeof toast === 'function') toast('Kvalita obrazu snížena kvůli plynulosti (Nastavení › Obraz).', 'warn');
}
window.addEventListener('resize', resize);
const vx = x => S.side === 0 ? x : S.W - 1 - x;
const px = x => OX + (vx(x) + 1.5) * CS;
const py = y => OY + (y + 0.5) * CS;
function cellAt(mx, my) {
  const col = Math.floor((mx - OX) / CS) - 1, y = Math.floor((my - OY) / CS);
  if (col < 0 || col >= S.W || y < 0 || y >= S.H) return null;
  return { x: S.side === 0 ? col : S.W - 1 - col, y };
}
const own = x => S.side === 0 ? x < S.half : x >= S.W - S.half;
const ter = (x, y) => S.snap ? S.snap.ter[y * S.W + x] : '.';
const visible = (x, y) => S.snap ? S.snap.v[y * S.W + x] === '1' : false;
function mistRange() {
  const st = S.snap ? Math.min(S.snap.st, 6) : 0;
  return [Math.max(0, S.mist[0] - st), Math.min(S.W - 1, S.mist[1] + st)];
}
const inMist = x => { const [lo, hi] = mistRange(); return x >= lo && x <= hi; };
const barrier = (x, y) => !!(S.snap && x >= S.mist[0] && x <= S.mist[1] && S.snap.qb.some(b => b[0] === y));
function entsAt(x, y) { const r = []; for (const e of S.ents.values()) if (e.cx === x && e.cy === y) r.push(e); return r; }
function crateAt(x, y) { return S.snap ? S.snap.cr.find(c => c[1] === x && c[2] === y) : null; }

// terrain classes (maps.js isWalk/isBuild when loaded; the same sets as the server's WALK/BUILD otherwise)
const terWalk = ch => typeof isWalk === 'function' ? isWalk(ch) : '.~^='.includes(ch);
const terBuild = ch => typeof isBuild === 'function' ? isBuild(ch) : ch === '.' || ch === '^';
function canPlace(k, x, y) {
  if (!own(x) || inMist(x) || !terBuild(ter(x, y)) || locked(k)) return false;
  const here = entsAt(x, y);
  if (S.defs[k].cat === 'b') return here.length === 0;
  return !here.some(e => S.defs[e.kind].cat !== 'b' || e.side !== S.side);
}
function canTarget(p, x, y) {
  if (p.kind === 'cmd') {
    const t = S.cmds[p.id].target;
    if (t === 'own') { const b = S.bmap.get(x + ',' + y); return !!(b && b.side === S.side && S.ents.has(b.id)); }
    if (t === 'crate') return !!crateAt(x, y);
    return visible(x, y);
  }
  const t = S.defs[p.id].target;
  if (t === 'vis') return visible(x, y) && (p.id !== 'navnada' || terWalk(ter(x, y)));
  if (t === 'mist') return x >= S.mist[0] && x <= S.mist[1];
  return true;
}

/* ---------------- juice state: camera trauma, hit-stop, slow motion, flash ---------------- */
const REDUCED = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
function fxOpts() {
  const o = S.opt || {}, calm = o.calm ?? REDUCED;
  return { calm, shake: calm ? 0 : o.shake ?? 1, flash: !calm && o.flash !== false, nums: o.nums !== false };
}
const FXS = {
  o: fxOpts(), vt: 0, dt: 0, rdt: 0, trauma: 0, tb: [], freeze: 0, slowUntil: 0, flash: null, flash2: 0, bolt: 0, fin: null,
  tele: -1e9, nums: [], dead: [], decals: [], scarT: 0, crates: new Map(), planes: new Map(), aura: [-1e9, -1e9],
  thHit: [-1e9, -1e9], thRow: [4, 4], band: -1e9, sweep: null, outEnd: -1e9, dark: 0, words: 0, raise: new Map(),
};
function resetFx() {
  pN = 0; S.fx = []; S.lasers = []; S.aims.clear(); FXS.crates.clear(); FXS.planes.clear(); FXS.raise.clear();
  Object.assign(FXS, { trauma: 0, tb: [], freeze: 0, slowUntil: 0, flash: null, flash2: 0, tele: -1e9, nums: [], dead: [], decals: [],
    scarT: 0, aura: [-1e9, -1e9], thHit: [-1e9, -1e9], thRow: [4, 4], promoAt: null, bolt: 0, band: -1e9, sweep: null, outEnd: -1e9, dark: 0, words: 0 });
}
function addTrauma(v, full = true) {
  if (!(v > 0)) return;
  const now = performance.now();
  if (!full) v *= 0.6;
  FXS.tb = FXS.tb.filter(b => now - b[0] < 1000);
  const used = FXS.tb.reduce((s, b) => s + b[1], 0);
  if (used + v > 0.6) v = Math.max(0, 0.6 - used) + (used + v - Math.max(0.6, used)) * 0.2;
  FXS.tb.push([now, v]);
  FXS.trauma = Math.min(1, FXS.trauma + v);
}
function hitStop(ms) { if (!FXS.o.calm) FXS.freeze = Math.max(FXS.freeze, performance.now() + ms); }
function screenFlash(a, ms, col = '#fff1c4') { if (FXS.o.flash && QUAL.lvl > 0) FXS.flash = { t0: performance.now(), a, ms, col }; }
const mineAt = (x, side) => side === S.side || (x >= 0 && x < S.W && own(Math.round(x)));

/* ---------------- small drawing helpers ---------------- */
const INK = '#0b0806', GROUND = 0.3;
const clamp01 = v => v < 0 ? 0 : v > 1 ? 1 : v;
const easeOut = t => 1 - (1 - t) ** 3;
const easeBack = t => 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2;
const since = t => FXS.vt - (t ?? -1e9);
const scrDx = dx => S.side === 0 ? dx : -dx;
// Cached sprite (cell-unit canvas from paint.js, origin in its middle) at board-space point X, Y (the camera transform is active);
// scale/rotation pivot ay px below the origin.
function putSpr(c, X, Y, a = 1, sx = 1, sy = 1, rot = 0, ay = 0) {
  const w = c.width / DPR, h = c.height / DPR;
  ctx.globalAlpha = a;
  if (sx === 1 && sy === 1 && !rot) ctx.drawImage(c, X - w / 2, Y - h / 2, w, h);
  else {   // camera * translate(X, Y + ay) * rotate * scale, set directly (no save/restore in the hot path)
    const k = CAM.k, co = Math.cos(rot) * k, si = Math.sin(rot) * k;
    ctx.setTransform(co * sx, si * sx, -si * sy, co * sy, X * k + CAM.x, (Y + ay) * k + CAM.y);
    ctx.drawImage(c, -w / 2, -h / 2 - ay, w, h);
    ctx.setTransform(k, 0, 0, k, CAM.x, CAM.y);
  }
  ctx.globalAlpha = 1;
}
const GLOW = new Map();
function glowOf(col) {
  let c = GLOW.get(col);
  if (!c) {
    c = mkCanvas(64, 64);
    const g = c.getContext('2d'), gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, rgba(col, 1)); gr.addColorStop(0.35, rgba(col, 0.45)); gr.addColorStop(1, rgba(col, 0));
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64); GLOW.set(col, c);
  }
  return c;
}
function glow(X, Y, r, col, a) { if (r > 0.5 && a > 0) { ctx.globalAlpha = Math.min(1, a); ctx.drawImage(glowOf(col), X - r, Y - r, r * 2, r * 2); } }
function ring(X, Y, r, col, w, a = 1, dash = null, off = 0, inkW = 0) {
  if (a <= 0) return;
  ctx.globalAlpha = Math.min(1, a); ctx.beginPath(); ctx.arc(X, Y, Math.max(0.5, r), 0, TAU);
  if (dash) { ctx.setLineDash(dash); ctx.lineDashOffset = off; }
  if (inkW) { ctx.strokeStyle = INK; ctx.lineWidth = w + inkW; ctx.stroke(); }
  ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke();
  if (dash) ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}
function arcP(X, Y, r, f, col, w, a = 1) {
  if (f <= 0) return;
  ctx.globalAlpha = a; ctx.beginPath(); ctx.arc(X, Y, r, -Math.PI / 2, -Math.PI / 2 + TAU * Math.min(1, f));
  ctx.strokeStyle = INK; ctx.lineWidth = w + 2.5; ctx.stroke(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke(); ctx.globalAlpha = 1;
}
function seg(x1, y1, x2, y2, col, w, a = 1) {
  ctx.globalAlpha = Math.min(1, a); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.globalAlpha = 1;
}
// Cached ink-stroked text; labels near row 0 are kept inside the board so they never clip at the canvas edge.
function ink(text, X, Y, size, col, a = 1, sc = 1, opt) {
  if (a > 0) putSpr(txtSpr(text, Math.max(8, Math.round(size)), col, opt), X, Math.max(OY + size * 0.7, Y), Math.min(1, a), sc, sc);
}
// Ornamental gilt corner brackets with diamond studs (selection, placement, check rows).
function cornerMarks(X, Y, s, col, a = 1) {
  const h = s / 2, l = s * 0.26, d = Math.max(2, s * 0.05);
  const path = () => { ctx.beginPath(); for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) { ctx.moveTo(X + sx * h, Y + sy * (h - l)); ctx.lineTo(X + sx * h, Y + sy * h); ctx.lineTo(X + sx * (h - l), Y + sy * h); } };
  ctx.globalAlpha = a; ctx.lineCap = 'butt';
  path(); ctx.strokeStyle = INK; ctx.lineWidth = 4; ctx.stroke();
  path(); ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = col;
  for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
    ctx.beginPath(); ctx.moveTo(X + sx * h, Y + sy * h - d); ctx.lineTo(X + sx * h + d, Y + sy * h); ctx.lineTo(X + sx * h, Y + sy * h + d); ctx.lineTo(X + sx * h - d, Y + sy * h); ctx.fill();
  }
  ctx.globalAlpha = 1;
}
// Marching diagonal hazard hatch: danger never relies on colour alone.
function hazard(x, y, w, h, col, a, now, step = 10) {
  ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
  ctx.globalAlpha = a; ctx.strokeStyle = col; ctx.lineWidth = step * 0.35; ctx.beginPath();
  const off = (now / 40) % step;
  for (let i = -h - step + off; i < w + step; i += step) { ctx.moveTo(x + i, y + h); ctx.lineTo(x + i + h, y); }
  ctx.stroke(); ctx.restore(); ctx.globalAlpha = 1;
}
function flameAt(X, Y, s, now, seed) {
  const f = 0.85 + 0.15 * Math.sin(now / 90 + seed) + 0.08 * Math.sin(now / 37 + seed * 3);
  glow(X, Y - s * 0.4, s * 2.6, PAL.candle, 0.35);
  ctx.globalAlpha = 1;
  ctx.beginPath(); ctx.moveTo(X, Y - s * 1.6 * f); ctx.quadraticCurveTo(X + s * 0.7, Y - s * 0.2, X, Y + s * 0.3); ctx.quadraticCurveTo(X - s * 0.7, Y - s * 0.2, X, Y - s * 1.6 * f);
  ctx.fillStyle = '#ff9a3c'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(X, Y - s * 0.9 * f); ctx.quadraticCurveTo(X + s * 0.35, Y - s * 0.05, X, Y + s * 0.2); ctx.quadraticCurveTo(X - s * 0.35, Y - s * 0.05, X, Y - s * 0.9 * f);
  ctx.fillStyle = PAL.flame; ctx.fill();
}

/* ---------------- particles: fixed pool; matter drawn normally, light additively ---------------- */
const PMAX = 700, PART = Array.from({ length: PMAX }, () => ({}));
let pN = 0, pMax = PMAX;   // pMax: the live cap (300 at Q0)
const DOT = 0, SPARK = 1, CHIP = 2, GEM = 3, IMG = 4;
function spray(x, y, n, o) {
  if (pN > pMax * 0.5) n = Math.ceil(n * (pMax - pN) / (pMax * 0.5));   // graceful thinning near the cap
  for (let i = 0; i < n && pN < pMax; i++) {
    const p = PART[pN++], v = (o.sp || 0) * (0.35 + Math.random() * 0.65), j = o.jit || 0;
    const a = o.dir === undefined ? Math.random() * TAU : o.dir + (Math.random() - 0.5) * (o.spread || 0);
    p.x = x + (Math.random() - 0.5) * j; p.y = y + (Math.random() - 0.5) * j; p.z = o.z || 0;
    p.vx = Math.cos(a) * v; p.vy = Math.sin(a) * v + (o.vy || 0); p.vz = (o.vz || 0) * (0.6 + Math.random() * 0.6); p.g = o.g || 0;
    p.drag = o.drag ?? 0.9; p.t0 = FXS.vt + (o.delay || 0); p.life = (o.life || 500) * (0.6 + Math.random() * 0.4);
    p.size = (o.size || 0.06) * (0.6 + Math.random() * 0.6); p.col = o.col; p.light = !!o.light; p.shape = o.shape || DOT;
    p.grow = o.grow || 0; p.rot = Math.random() * TAU; p.vr = (Math.random() - 0.5) * (o.spin || 0); p.img = o.img || null; p.a = o.a || 1;
  }
}
function stepParts(dt) {
  const t = FXS.vt;
  for (let i = 0; i < pN; i++) {
    const p = PART[i];
    if (t - p.t0 >= p.life) { PART[i] = PART[--pN]; PART[pN] = p; i--; continue; }
    if (t < p.t0 || !dt) continue;
    const d = p.drag ** (dt * 60);
    p.vx *= d; p.vy *= d; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.vr * dt;
    if (p.g) { p.vz -= p.g * dt; p.z += p.vz * dt; if (p.z < 0) { p.z = 0; p.vz *= -0.35; p.vx *= 0.5; p.vy *= 0.5; p.vr *= 0.5; } }
  }
}
function drawParts(light) {
  const t = FXS.vt, low = light && QUAL.lvl === 0;   // Q0: light particles without additive glows
  let fs = '';
  ctx.globalCompositeOperation = light && !low ? 'lighter' : 'source-over';
  for (let i = 0; i < pN; i++) {
    const p = PART[i];
    if (p.light !== light || t < p.t0 || (low && p.shape === DOT)) continue;
    const k = 1 - (t - p.t0) / p.life, X = px(p.x), Y = py(p.y) - p.z * CS;
    const s = p.size * CS * (p.grow ? 1 + (1 - k) * p.grow : 0.5 + k * 0.5);
    ctx.globalAlpha = p.a * Math.min(1, k * 2);
    if (p.shape === DOT) ctx.drawImage(glowOf(p.col), X - s, Y - s, s * 2, s * 2);
    else if (p.shape === SPARK) { if (fs !== p.col) ctx.fillStyle = fs = p.col; ctx.fillRect(X - s / 2, Y - s / 2, s, s); }
    else {
      const c = Math.cos(p.rot), sn = Math.sin(p.rot);
      ctx.setTransform(c * CAM.k, sn * CAM.k, -sn * CAM.k, c * CAM.k, X * CAM.k + CAM.x, Y * CAM.k + CAM.y);
      if (p.shape === IMG) { const w = p.img.width / DPR, h = p.img.height / DPR; ctx.drawImage(p.img, -w / 2, -h / 2, w, h); }
      else {
        if (fs !== p.col) ctx.fillStyle = fs = p.col;
        ctx.beginPath();
        if (p.shape === GEM) { ctx.moveTo(0, -s); ctx.lineTo(s * 0.6, 0); ctx.lineTo(0, s); ctx.lineTo(-s * 0.6, 0); }
        else { ctx.moveTo(-s, -s * 0.6); ctx.lineTo(s, -s * 0.2); ctx.lineTo(-s * 0.2, s * 0.8); }
        ctx.fill();
      }
      ctx.setTransform(CAM.k, 0, 0, CAM.k, CAM.x, CAM.y);
    }
  }
  ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
}
const dust = (x, y, n, o = {}) => spray(x, y, n, Object.assign({ col: '#3a332c', sp: 0.9, life: 650, size: 0.16, grow: 1.6, drag: 0.88, a: 0.55 }, o));

/* ---------------- board layer (static, cached) ---------------- */
// BOARD (= BASE): floor, terrain, rubble, fences, Mist tint and the base vignette, rebuilt only when BOARD_KEY changes.
// LAYER: BOARD plus the live decals; it is the one opaque blit per frame.
let BOARD = null, BOARD_KEY = '', BOARD_N = 0, LAYER = null, LAYER_N = -1, FOG = null, FOG_KEY = '', FOGPAT = null, FOGPAT_K = -1, DARK = null;
const boardTheme = () => S.theme || (S.map && S.map.theme) || 'ruiny';   // theme id (maps.js THEMES)
function boardCanvas() {
  const m = S.snap, [lo, hi] = mistRange(), theme = boardTheme();
  const key = [m.ter, lo, hi, m.ni ? 1 : 0, S.side, CS, OX, OY, cv.width, cv.height, theme].join('|');
  if (key === BOARD_KEY && BOARD) return BOARD;
  BOARD_KEY = key; BOARD_N++;
  if (!BOARD || BOARD.width !== cv.width || BOARD.height !== cv.height) BOARD = mkCanvas(cv.width, cv.height);
  const g = BOARD.getContext('2d'), W = S.W, H = S.H, b = Math.max(1, CS / 40);
  g.setTransform(DPR, 0, 0, DPR, 0, 0);
  g.fillStyle = PAL.bg; g.fillRect(0, 0, cv.width / DPR, cv.height / DPR);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const X = px(x) - CS / 2, Y = py(y) - CS / 2, mist = x >= lo && x <= hi, blight = mist && (x < S.mist[0] || x > S.mist[1]);
    const light = (x + y) % 2 === 0, j = (hash(x, y, 7) - 0.5) * 0.08, ix = X + b, iy = Y + b, iw = CS - 2 * b;
    g.fillStyle = PAL.mortar; g.fillRect(X, Y, CS, CS);
    g.fillStyle = blight ? PAL.blight : mist ? (light ? PAL.mistT1 : PAL.mistT2) : (light ? PAL.stoneL : PAL.stoneD); g.fillRect(ix, iy, iw, iw);
    g.fillStyle = j > 0 ? `rgba(255,240,210,${j})` : `rgba(0,0,0,${-j * 1.5})`; g.fillRect(ix, iy, iw, iw);
    if (!mist) {
      const side = x < S.half ? 0 : x >= W - S.half ? 1 : -1;
      if (side >= 0) { const d = side === 0 ? x : W - 1 - x; g.fillStyle = rgba(COL[side], 0.06 * (1 - d / S.half)); g.fillRect(ix, iy, iw, iw); }
    }
    g.fillStyle = 'rgba(255,240,210,0.07)'; g.fillRect(ix, iy, iw, 1); g.fillRect(ix, iy, 1, iw);
    g.fillStyle = 'rgba(0,0,0,0.35)'; g.fillRect(ix, iy + iw - 1, iw, 1); g.fillRect(ix + iw - 1, iy, 1, iw);
    const cracks = blight ? 2 : hash(x, y, 2) < (mist ? 0.7 : 0.3) ? 1 : 0;
    g.strokeStyle = 'rgba(0,0,0,0.45)'; g.lineWidth = 1;
    for (let k = 0; k < cracks; k++) {
      let cx = X + CS * 0.1 + hash(x, y, 3 + k * 7) * CS * 0.8, cy = Y + CS * 0.06;
      g.beginPath(); g.moveTo(cx, cy);
      for (let i = 0; i < 4; i++) { cx += (hash(x, y, 10 + i + k * 5) - 0.5) * CS * 0.25; cy += CS / 5; g.lineTo(cx, cy); }
      g.stroke();
    }
    if (mist && hash(x, y, 5) < 0.6) for (let i = 0; i < 5; i++) {
      g.fillStyle = rgba(PAL.moss, 0.35); g.beginPath();
      g.arc(X + CS * 0.08 + hash(x, i, y) * CS * 0.84, Y + CS * 0.92 - hash(i, y, x) * CS * 0.4, CS * (0.024 + hash(y, i, 4) * 0.04), 0, TAU); g.fill();
    }
    if (blight) {
      g.save(); g.beginPath(); g.rect(X, Y, CS, CS); g.clip();
      g.strokeStyle = 'rgba(185,203,191,0.10)'; g.lineWidth = 5;
      for (const o of [0.25, 0.7]) { g.beginPath(); g.moveTo(X + CS * o - CS * 0.4, Y + CS); g.lineTo(X + CS * o + CS * 0.4, Y); g.stroke(); }
      g.restore();
    }
  }
  // per-map floor tint (maps.js THEMES[theme].floor; Ruiny has none)
  const tint = typeof mapTheme === 'function' && mapTheme(theme).floor;
  if (tint) { g.fillStyle = tint; g.fillRect(OX + CS, OY, W * CS, H * CS); }
  // warm candle pools in front of both thrones, so the floor is never murky
  for (const tx of [-1, W]) {
    const X = px(tx), gr = g.createRadialGradient(X, OY + H * CS / 2, 0, X, OY + H * CS / 2, CS * 4);
    gr.addColorStop(0, 'rgba(255,184,90,0.07)'); gr.addColorStop(1, 'rgba(255,184,90,0)');
    g.fillStyle = gr; g.fillRect(X - CS * 4, OY, CS * 8, H * CS);
  }
  // 1.0 terrain (X w = ~ ^) from maps.js, painted over the floor tile; X, Y = the cell's top-left corner
  if (typeof paintTerrain === 'function') for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const ch = ter(x, y);
    if (ch !== '.' && ch !== '#') paintTerrain(g, ch, px(x) - CS / 2, py(y) - CS / 2, CS, x, y, theme);
  }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (ter(x, y) !== '#') continue;
    const c = sprRubble(x * 31 + y * 7 + 1), w = c.width / DPR, h = c.height / DPR;
    g.drawImage(c, px(x) - w / 2, py(y) - h / 2, w, h);
  }
  // iron cemetery fence along both Mist edges
  const pw = Math.max(2, CS * 0.05), ph = CS * 0.19;
  for (const bx of [lo - 0.5, hi + 0.5]) {
    if (bx < 0 || bx > W - 1) continue;
    const X = (px(bx - 0.5) + px(bx + 0.5)) / 2;
    g.strokeStyle = rgba(PAL.mist, 0.35); g.lineWidth = 1.5; g.setLineDash([3, 5]);
    g.beginPath(); g.moveTo(X, OY); g.lineTo(X, OY + H * CS); g.stroke(); g.setLineDash([]);
    g.fillStyle = '#1b1816';
    for (let i = 0; i < H * 2; i++) {
      const Y = OY + (i + 0.5) * CS / 2;
      g.fillRect(X - pw / 2, Y - ph / 2, pw, ph);
      g.beginPath(); g.moveTo(X - pw, Y - ph / 2); g.lineTo(X, Y - ph / 2 - pw * 1.6); g.lineTo(X + pw, Y - ph / 2); g.fill();
    }
  }
  if (m.ni) { g.fillStyle = 'rgba(110,10,20,0.12)'; g.fillRect(OX, OY, (W + 2) * CS, H * CS); }
  g.strokeStyle = PAL.giltLo; g.lineWidth = 3; g.strokeRect(OX + CS - 1.5, OY + 1.5, W * CS + 3, H * CS - 3);
  g.strokeStyle = rgba(PAL.giltHi, 0.4); g.lineWidth = 1; g.strokeRect(OX + CS + 2.5, OY + 4.5, W * CS - 5, H * CS - 9);
  // Mist tint (night: blood red), then the base vignette at a fixed alpha (under the units, no pulse)
  g.fillStyle = m.ni ? 'rgba(120,20,24,0.16)' : 'rgba(185,203,191,0.06)';
  g.fillRect(Math.min(px(lo), px(hi)) - CS / 2, OY, (hi - lo + 1) * CS, H * CS);
  g.setTransform(1, 0, 0, 1, 0, 0);
  const vw = BOARD.width, vh = BOARD.height, vg = g.createRadialGradient(vw / 2, vh / 2, Math.min(vw, vh) * 0.35, vw / 2, vh / 2, Math.hypot(vw, vh) * 0.6);
  vg.addColorStop(0, 'rgba(8,4,2,0)'); vg.addColorStop(1, 'rgba(8,4,2,1)');
  g.globalAlpha = 0.58; g.fillStyle = vg; g.fillRect(0, 0, vw, vh); g.globalAlpha = 1;
  return BOARD;
}
// BOARD + decals; the 1 s sweep rebuilds it only when a decal changed its alpha step or expired
function layerCanvas(now) {
  const b = boardCanvas();
  if (!LAYER || LAYER.width !== b.width || LAYER.height !== b.height) { LAYER = mkCanvas(b.width, b.height); LAYER_N = -1; }
  let dirty = LAYER_N !== BOARD_N || !FXS.scarT;
  if (!FXS.scarT || now - FXS.scarT > 1000) {
    FXS.scarT = now || 1;
    const keep = [];
    for (const d of FXS.decals) { const q = decalStep(d); if (q !== d.q) dirty = true; if (q > 0) keep.push(d); }
    FXS.decals = keep;
  }
  if (dirty) {
    const g = LAYER.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
    g.drawImage(b, 0, 0);
    g.setTransform(DPR, 0, 0, DPR, 0, 0);
    for (const d of FXS.decals) { d.q = decalStep(d); paintDecal(g, d); }
    LAYER_N = BOARD_N;
  }
  return LAYER;
}
function fogPaths() {
  const key = [S.snap.v, S.side, CS, OX, OY].join('|');
  if (key === FOG_KEY && FOG) return FOG;
  FOG_KEY = key;
  const cells = new Path2D(), edges = new Path2D();
  let n = 0;
  for (let y = 0; y < S.H; y++) for (let x = 0; x < S.W; x++) {
    if (visible(x, y)) continue;
    const X = px(x) - CS / 2, Y = py(y) - CS / 2;
    n++;
    cells.rect(X, Y, CS, CS);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= S.W || ny >= S.H || !visible(nx, ny)) continue;
      if (dy === 0) { const ex = vx(nx) > vx(x) ? X + CS : X; edges.moveTo(ex, Y); edges.lineTo(ex, Y + CS); }
      else { const ey = dy > 0 ? Y + CS : Y; edges.moveTo(X, ey); edges.lineTo(X + CS, ey); }
    }
  }
  cells.area = n * CS * CS;   // CSS px², read by ?perf
  FOG = { cells, edges };
  return FOG;
}
// fog fill and hatch pre-blended into one 8x8 pattern (per-pixel alpha), so the fog cells are filled once
function fogPat(strong) {
  const k = strong ? 1 : 0;
  if (FOGPAT && FOGPAT_K === k) return FOGPAT;
  const c = mkCanvas(8, 8), g = c.getContext('2d');
  g.fillStyle = `rgba(9,7,6,${strong ? 0.9 : 0.8})`; g.fillRect(0, 0, 8, 8);
  g.strokeStyle = 'rgba(214,190,140,0.09)'; g.lineWidth = 1; g.beginPath();
  g.moveTo(0, 8); g.lineTo(8, 0); g.moveTo(-2, 2); g.lineTo(2, -2); g.moveTo(6, 10); g.lineTo(10, 6); g.stroke();
  FOGPAT = ctx.createPattern(c, 'repeat'); FOGPAT_K = k;
  return FOGPAT;
}
// red (low throne) and dark (eclipse warning) vignettes: 4 edge strips 0.2·min(w,h) thick, cached per size at quarter
// resolution; the radial curve of 0.5 fades out over the inner half of each strip
const VIG = new Map();
function vigStrips(kind) {
  const W = cv.width, H = cv.height, key = kind + '|' + W + '|' + H;
  let v = VIG.get(key);
  if (v) return v;
  const q = 4, t = Math.max(q, Math.round(0.2 * Math.min(W, H) / q) * q), w = Math.ceil(W / q), h = Math.ceil(H / q);
  const [r0, rgb] = kind === 'red' ? [0.3, [150, 24, 18]] : [0.18, [0, 0, 0]];
  const R0 = Math.min(W, H) * r0, R1 = Math.hypot(W, H) * 0.6;
  const c = mkCanvas(w, h), g = c.getContext('2d'), img = g.createImageData(w, h), D = img.data;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const X = (x + 0.5) * q, Y = (y + 0.5) * q, s = Math.min(X, W - X, Y, H - Y);
    if (s >= t) continue;
    const a = clamp01((Math.hypot(X - W / 2, Y - H / 2) - R0) / (R1 - R0)), f = clamp01((t - s) / (0.5 * t)), i = (y * w + x) * 4;
    D[i] = rgb[0]; D[i + 1] = rgb[1]; D[i + 2] = rgb[2]; D[i + 3] = Math.round(255 * a * f * f * (3 - 2 * f));
  }
  g.putImageData(img, 0, 0);
  v = { c, t, q };
  VIG.set(key, v);
  return v;
}
function drawVig(kind, a) {   // screen space (identity transform)
  const { c, t, q } = vigStrips(kind), W = cv.width, H = cv.height, tq = t / q, mid = H - 2 * t;
  ctx.globalAlpha = a;
  ctx.drawImage(c, 0, 0, W / q, tq, 0, 0, W, t);
  ctx.drawImage(c, 0, (H - t) / q, W / q, tq, 0, H - t, W, t);
  if (mid > 0) {
    ctx.drawImage(c, 0, tq, tq, mid / q, 0, t, t, mid);
    ctx.drawImage(c, (W - t) / q, tq, tq, mid / q, W - t, t, t, mid);
  }
  ctx.globalAlpha = 1;
}

/* ---------------- decals: painted into LAYER; alpha in 4 steps (1, .75, .5, .25 of the linear curve) ---------------- */
function decalStep(d) {
  const age = FXS.vt - d.t0, a = d.type === 'rubble' ? clamp01((d.life - age) / (d.life * 0.2)) : 1 - age / d.life;
  return a <= 0 ? 0 : Math.ceil(a * 4 - 1e-9) / 4;
}
function addDecal(type, x, y, life, s = 1) {
  const d = { type, x, y, t0: FXS.vt, life, s, seed: Math.random() * 1e6 | 0, q: 1 };
  FXS.decals.push(d);
  if (FXS.decals.length > 60) { FXS.decals.shift(); FXS.scarT = 0; }
  else if (LAYER && FXS.scarT && LAYER_N === BOARD_N) { const g = LAYER.getContext('2d'); g.setTransform(DPR, 0, 0, DPR, 0, 0); paintDecal(g, d); }
}
function paintDecal(g, d) {
  const a = d.q;
  if (!(a > 0)) return;
  const X = px(d.x), Y = py(d.y), r = CS * d.s;
  if (d.type === 'scorch') {
    const gr = g.createRadialGradient(X, Y, 0, X, Y, r * 0.55);
    gr.addColorStop(0, `rgba(0,0,0,${0.38 * a})`); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.fillRect(X - r, Y - r, r * 2, r * 2);
  } else if (d.type === 'splat') {
    g.fillStyle = `rgba(52,64,36,${0.38 * a})`;
    for (let i = 0; i < 3; i++) {
      g.beginPath(); g.ellipse(X + (hash(d.seed, i, 1) - 0.5) * r * 0.5, Y + r * 0.2 + (hash(d.seed, i, 2) - 0.5) * r * 0.25, r * (0.12 + hash(d.seed, i, 3) * 0.14), r * (0.06 + hash(d.seed, i, 4) * 0.06), hash(d.seed, i, 5) * 3, 0, TAU); g.fill();
    }
  } else if (d.type === 'rubble') {
    g.fillStyle = `rgba(0,0,0,${0.3 * a})`; g.beginPath(); g.ellipse(X, Y + r * 0.22, r * 0.42, r * 0.14, 0, 0, TAU); g.fill();
    for (let i = 0; i < 6; i++) {
      const bx = X + (hash(d.seed, i, 6) - 0.5) * r * 0.7, by = Y + r * 0.05 + (hash(d.seed, i, 7) - 0.5) * r * 0.35, s = r * (0.07 + hash(d.seed, i, 8) * 0.08);
      g.fillStyle = i % 2 ? `rgba(92,85,77,${a})` : `rgba(68,62,56,${a})`; g.fillRect(bx - s / 2, by - s / 2, s, s * 0.7);
      g.fillStyle = `rgba(255,240,210,${0.12 * a})`; g.fillRect(bx - s / 2, by - s / 2, s, 1);
    }
  } else {
    g.fillStyle = `rgba(70,64,56,${0.3 * a})`;
    for (let i = 0; i < 4; i++) { g.beginPath(); g.arc(X + (hash(d.seed, i, 9) - 0.5) * r * 0.5, Y + r * 0.2 + (hash(d.seed, i, 10) - 0.5) * r * 0.2, r * (0.04 + hash(d.seed, i, 11) * 0.06), 0, TAU); g.fill(); }
  }
}

/* ---------------- snapshot -> presentation (fx, hit reactions, deaths, numbers, transitions) ---------------- */
const FX_LIFE = { k: 260, q: 220, t: 240, s: 760, z: 240, f: 360, m: 300, b: 720, p: 950, g: 450, h: 800, c: 2000, o: 320,
  v: 900, u: 900, r: 520, D: 340, U: 650, P: 1100, R: 1300, L: 1500, K: 450, w: 750, H: 260, E: 800, M: 700, Z: 700, W: 500 };
// side factions (FAC §6): every faction-aware sprite reads them through facOf()
on('start', m => setSideFacs(m && m.fac));
const HOP = { jezdec: 2.236, strelec: 1.414 };
function renderOnSnap(m, prev, gone) {
  if (!prev) { resetFx(); qualityStart(); }
  // no frame drawn for a while (background tab): drop the backlog so returning does not replay it all at once
  else if (performance.now() - lastT > 500) { pN = 0; S.fx.length = 0; S.lasers.length = 0; FXS.nums.length = 0; FXS.dead.length = 0; }
  FXS.o = fxOpts();
  const kid = m.kr && m.kr.id;
  for (const f of m.fx) onFx(f, gone, kid);
  if (S.fx.length > 400) S.fx.splice(0, S.fx.length - 400);
  for (const e of S.ents.values()) onEnt(e, prev);
  for (const ev of m.ev || []) if (ev[0] === 'contest') { const r = FXS.crates.get(ev[1]); if (r) r.cont = FXS.vt + 1000; }
  onDiff(m, prev);
}
function nearest(x, y, r, test) {
  let best = null, bd = r;
  for (const e of S.ents.values()) { const d = Math.hypot(e.x - x, e.y - y); if (d < bd && test(e)) { bd = d; best = e; } }
  return best;
}
const catOf = e => S.defs[e.kind] ? S.defs[e.kind].cat : 'z';
function onFx(f, gone, kid) {
  const [type, a, b, c, d, side] = f, vt = FXS.vt, now = performance.now();
  if (type === 'a') {
    S.lasers.push({ x: a, y: b, tx: c, ty: d, id: f[6], side, t0: now });
    if (kid && f[6] === kid) FXS.tele = now;
    const tw = S.bmap.get(a + ',' + b); if (tw) tw.aimT = now;
    return;
  }
  if (type === 'x') return onDeath(f, gone);
  if (type === 'n') return onPlaced(f);
  const rec = { type, a, b, c, d, side, f, t0: vt, life: FX_LIFE[type] || 300, seed: Math.random() * 1e4 | 0 };
  S.fx.push(rec);
  if ('ksmqtzH'.includes(type)) {
    const t = nearest(c, d, 0.35, e => true);
    if (t) { const l = Math.hypot(c - a, d - b) || 1; t.hitDir = [(c - a) / l, (d - b) / l]; t.hitDirT = vt; }
  }
  switch (type) {
    case 'k': case 's': {
      const tw = S.bmap.get(a + ',' + b); if (tw) tw.recoilT = vt;
      S.aims.set(a + ',' + b, [c, d]);
      if (type === 'k') { spray(c, d, 3, { col: PAL.wood, sp: 1.6, life: 380, size: 0.05, shape: CHIP, vz: 2, g: 9, spin: 12, delay: 110 }); break; }
      dust(c, d, 6, { delay: 40 });
      spray(c, d, 8, { col: PAL.flame, sp: 3, life: 300, size: 0.05, shape: SPARK, light: true, delay: 40 });
      const t = nearest(c, d, 0.4, () => true);
      addTrauma(t && t.side === S.side && 'bk'.includes(catOf(t)) ? 0.12 : 0.03);
      break;
    }
    case 'q': case 't': spray(c, d, 4, { col: TEAM[side] ? TEAM[side].hi : PAL.giltHi, sp: 2, life: 260, size: 0.05, shape: SPARK, light: true, delay: 90 }); break;
    case 'z': spray(c, d, 4, { col: PAL.ghost, sp: 2, life: 240, size: 0.05, shape: SPARK, light: true }); break;
    case 'f':
      for (let i = 0; i < 10; i++) {
        const ang = Math.random() * TAU, r = Math.sqrt(Math.random()) * c;
        spray(a + Math.cos(ang) * r, b + Math.sin(ang) * r, 1, { col: i % 3 ? '#ff9a3c' : PAL.flame, vy: -0.9, sp: 0.3, life: 420, size: 0.13, light: true, drag: 0.95 });
      }
      dust(a, b, 3, { col: '#28201c', vy: -0.5, sp: 0.6, life: 900, size: 0.14, jit: c });
      break;
    case 'm':
      if (c === -0.5 || c === S.W - 0.5) FXS.thRow[c < 0 ? 0 : 1] = d;
      { const at = nearest(a, b, 0.35, e => 'uzk'.includes(catOf(e))); if (at) { const l = Math.hypot(c - a, d - b) || 1; at.lungeT = vt; at.lungeDir = [(c - a) / l, (d - b) / l]; } }
      if (side !== 2) spray(c, d, 3, { col: PAL.giltHi, sp: 2, life: 200, size: 0.04, shape: SPARK, light: true });
      break;
    case 'b': explode(a, b, c, side); break;
    case 'p': {
      const mine = side === S.side;
      if (mine && S.mode === 'kral') { hitStop(90); FXS.slowUntil = now + 310; screenFlash(0.22, 50); addTrauma(0.15); }
      spray(a, b, mine ? 14 : 7, { col: PAL.giltHi, sp: 3.2, life: 360, size: 0.05, shape: SPARK, light: true });
      if (c >= 0) spray(c, d, 10, { col: PAL.flame, sp: 2.4, life: 320, size: 0.05, shape: SPARK, light: true, delay: 120 });
      break;
    }
    case 'g': spray(a, b, 5, { col: PAL.muted, sp: 1.6, life: 260, size: 0.05, shape: SPARK, light: true }); break;
    case 'h': spray(a, b, 3, { col: PAL.giltHi, vy: -0.8, sp: 0.3, life: 700, size: 0.07, light: true, jit: 0.5 }); break;
    case 'o': {
      const col = RAR_COL[c] || PAL.gilt, r = [...FXS.crates.values()].find(q => q.c[1] === a && q.c[2] === b);
      spray(a, b, 16, { col, sp: 2.2, vz: 3, g: 8, life: 900, size: 0.09, shape: GEM, light: true, spin: 10 });
      spray(a, b, 10, { col: PAL.giltHi, vy: -0.9, sp: 0.4, life: 900, size: 0.06, light: true, jit: 0.6 });
      FXS.dead.push({ corpse: 'crate', x: a, y: b, rar: c, t0: vt, life: 650, mine: side === S.side, cy: b });
      if (r) FXS.crates.delete(r.id);
      break;
    }
    case 'v': {
      spray(a, b, 12, { col: PAL.gilt, sp: 2, life: 500, size: 0.05, shape: SPARK, light: true });
      const u = nearest(a, b, 0.6, e => catOf(e) === 'u'); if (u) u.spinT = vt;
      break;
    }
    case 'u': {
      const e = S.bmap.get(a + ',' + b); if (e) e.lvlT = vt;
      if (c >= 3) { spray(a, b, 16, { col: PAL.giltHi, sp: 1.6, vy: -0.5, life: 700, size: 0.05, shape: SPARK, light: true }); addTrauma(0.05, mineAt(a, side)); }
      break;
    }
    case 'r':
      for (let i = 0; i < 10; i++) { const ang = i / 10 * TAU; spray(a + Math.cos(ang) * 0.6, b + Math.sin(ang) * 0.6, 1, { col: PAL.giltHi, dir: ang + Math.PI, sp: 2.4, life: 260, size: 0.05, light: true, drag: 1 }); }
      if (side === S.side) spray(a, b, 6, { col: PAL.giltHi, dir: S.side === 0 ? -2.4 : -0.75, spread: 0.6, sp: 7, life: 700, size: 0.06, shape: SPARK, light: true, drag: 1, delay: 220 });
      break;
    case 'D': dust(a, b, 6, { sp: 0.6 }); if (side === S.side) addTrauma(0.05); break;
    case 'U':
      FXS.aura[side] = vt + 8000;
      spray(a, b, 24, { col: TEAM[side].hi, sp: 3, life: 600, size: 0.06, light: true });
      addTrauma(0.12, side === S.side);
      break;
    case 'P': FXS.promoAt = a + ',' + b; spray(a, b, 16, { col: PAL.giltHi, sp: 1.8, vy: -0.6, life: 800, size: 0.05, shape: SPARK, light: true }); break;
    case 'H': spray(c, d, 4, { col: '#e9f2ff', sp: 1.8, life: 240, size: 0.04, shape: SPARK, light: true, delay: 200 }); break;
    case 'E':
      spray(a, b, 18, { col: '#e9f2ff', sp: 3, life: 420, size: 0.05, shape: SPARK, light: true });
      spray(a, b, 8, { col: PAL.ghost, sp: 1.5, life: 600, size: 0.06, shape: SPARK, light: true, jit: 1.2 });
      addTrauma(0.1, side === S.side || mineAt(a, -1));
      break;
    case 'M': dust(a, b, 12, { col: '#6c7a5a', sp: 1.3, life: 1000, size: 0.24, grow: 2.2, drag: 0.9, a: 0.5, jit: 1 }); break;
    case 'Z':
      FXS.raise.set(Math.round(a) + ',' + Math.round(b), vt);
      spray(a, b + 0.25, 8, { col: '#4a3f33', sp: 1.2, vz: 2, g: 8, life: 600, size: 0.05, shape: CHIP, delay: 100 });
      break;
    case 'W': { const z = nearest(a, b, 0.7, e => catOf(e) === 'z'); if (z) z.turnT = vt; break; }
    case 'R':
      spray(a, b, 24, { col: TEAM[side].hi, sp: 2.6, life: 900, size: 0.07, light: true });
      spray(a, b, 12, { col: PAL.giltHi, vy: -1.2, sp: 0.5, life: 1100, size: 0.06, light: true, jit: 1.5 });
      addTrauma(0.1, side === S.side);
      break;
  }
}
// Explosion: smoke annulus, additive fireball, embers, shockwave, scorch, shake (also used by the finale).
function explode(x, y, r, side, delay = 0) {
  dust(x, y, 10, { col: '#1e1814', sp: r * 1.6, life: 900, size: 0.2 * r + 0.1, grow: 2, drag: 0.86, a: 0.7, delay });
  spray(x, y, 14, { col: PAL.candle, sp: 2.6 * r + 1, vz: 2.5, g: 7, life: 700, size: 0.045, shape: SPARK, light: true, delay });
  spray(x, y, 6, { col: PAL.flame, sp: 1.5 * r, life: 360, size: 0.18 * r, light: true, delay });
  addDecal('scorch', x, y, 4000, r * 1.6);
  if (!delay) {
    const th = x < 0 ? 0 : x > S.W - 1 ? 1 : -1;
    addTrauma(th < 0 ? 0.18 * r : th === S.side ? 0.35 : 0.1, th === S.side || mineAt(x, -1));
    if (r >= 1.2 && FXS.words < 3) S.fx.push({ type: 'w', a: x, b: y, t0: FXS.vt, life: FX_LIFE.w, rot: (Math.random() - 0.5) * 0.3 });
  }
  if (r >= 1.5 && !delay) {
    hitStop(70);
    for (const dl of [70, 140]) {
      const ex = x + (Math.random() - 0.5) * 2, ey = y + (Math.random() - 0.5) * 2;
      S.fx.push({ type: 'b', a: ex, b: ey, c: 0.6, side, t0: FXS.vt + dl, life: FX_LIFE.b });
      explode(ex, ey, 0.6, side, dl);
    }
  }
}
function onPlaced(f) {
  const [, x, y, isUnit, , side, kind] = f;
  FXS.decals = FXS.decals.filter(d => !(d.type === 'rubble' && Math.abs(d.x - x) < 0.5 && Math.abs(d.y - y) < 0.5));
  FXS.scarT = 0;
  const e = isUnit ? nearest(x, y, 0.6, q => q.kind === kind && q.side === side) : S.bmap.get(x + ',' + y);
  if (e && S.ents.has(e.id) && since(e.spawnT) > 150) placed(e, !isUnit);
}
function placed(e, building) {
  e.spawnT = FXS.vt;
  if (!building) return;
  dust(e.cx, e.cy + 0.25, 8, { sp: 1.4, delay: 180, life: 500 });
  addTrauma(0.04, e.side === S.side);
}
function onDeath(f, gone) {
  const [, x, y, , , cat, id, kind, side, killer] = f, vt = FXS.vt;
  let e = id !== undefined && gone ? gone.get(id) : null;
  if (!e && gone) for (const g of gone.values()) if (catOf(g) === cat && Math.hypot(g.dx - x, g.dy - y) < 0.6) { e = g; break; }
  if (!e && kind) e = { id, kind, side, x, y, dx: x, dy: y, cx: Math.round(x), cy: Math.round(y), lvl: 1, path: '', flags: 0 };
  if (!e) { spray(x, y, 10, { col: PAL.muted, sp: 1.5, life: 500, size: 0.05, shape: SPARK }); return; }
  const mine = e.side === S.side, X = e.dx ?? x, Y = e.dy ?? y;
  if (cat === 'z') {
    const big = e.kind === 'obr' || e.kind === 'alfa';
    FXS.dead.push({ corpse: 'z', c: sprZombie(e.kind, 0, 1, ownOf(e)), x: X, y: Y, cy: Y, t0: vt, life: 450, face: e.face || 1, e });
    spray(X, Y, big ? 16 : 8, { col: PAL.fleshD, sp: big ? 2.2 : 1.4, vz: 2, g: 9, life: 650, size: big ? 0.09 : 0.06, shape: CHIP, spin: 8 });
    addDecal('splat', X, Y, 20000, big ? 1.6 : 1);
    if (big) addDecal('splat', X + 0.3, Y + 0.1, 20000, 1.2);
    if (e.kind === 'obr') addTrauma(0.1, mineAt(X, -1));
    if (e.kind === 'alfa') { addTrauma(0.4); hitStop(120); }
  } else if (cat === 'u') {
    const h = e.hitDir && since(e.hitDirT) < 400 ? scrDx(e.hitDir[0]) : (mine ? -1 : 1);
    const c = sprUnit(e.kind, e.side, !!(e.flags & 1), mine ? 1 : -1);
    FXS.dead.push({ corpse: 'u', c, x: X, y: Y, cy: Y, t0: vt, life: 620, dir: h >= 0 ? 1 : -1, side: e.side });
    addDecal('ash', X, Y, 10000, 0.9);
  } else if (cat === 'b') {
    FXS.dead.push({ corpse: 'b', c: sprBuilding(e.kind, e.side, e.lvl, e.path), x: e.cx, y: e.cy, cy: e.cy, t0: vt, life: 520 });
    dust(e.cx, e.cy + 0.1, 14, { col: '#463e36', sp: 0.7, life: 1500, size: 0.22, grow: 2.2, drag: 0.93 });
    spray(e.cx, e.cy, 6, { col: '#6b645b', sp: 1.8, vz: 3, g: 9, life: 900, size: 0.09, shape: CHIP, spin: 10 });
    addDecal('rubble', e.cx, e.cy, 45000);
    addTrauma(mine ? 0.25 : 0.15); hitStop(50);
  } else if (cat === 'k') {
    const c = sprKing(e.side, e.face || 1);
    hitStop(mine ? 140 : 90); screenFlash(0.2, 60); addTrauma(mine ? 0.55 : 0.35);
    for (const s of shardsOf(c, 12)) {
      const dir = Math.atan2(Math.sin(s.a), scrDx(Math.cos(s.a)));
      spray(X + scrDx(s.x), Y + s.y, 1, { img: s.c, shape: IMG, dir, sp: 2.4, vz: 2.5, g: 8, life: 900, spin: 9, drag: 0.93 });
    }
    spray(X, Y, 20, { col: PAL.giltHi, sp: 3, life: 600, size: 0.05, shape: SPARK, light: true });
    FXS.dead.push({ corpse: 'crown', x: X, y: Y, cy: Y + 0.3, t0: vt, life: 1400, dir: Math.random() < 0.5 ? -1 : 1 });
    S.fx.push({ type: 'K', a: X, b: Y, side: e.side, t0: vt, life: FX_LIFE.K });
  }
  if (FXS.dead.length > 40) FXS.dead.splice(0, FXS.dead.length - 40);
}
function onEnt(e, prev) {
  const cat = catOf(e), vt = FXS.vt;
  if (e.rhp === undefined) {
    e.rhp = e.hp; e.rmax = e.maxhp; e.trav = 0; e.rest = 0; e.ang = e.side === S.side ? 0 : Math.PI; e.face = e.side === S.side ? 1 : -1;
    if (!prev) return;
    const rz = cat === 'z' ? FXS.raise.get(e.cx + ',' + e.cy) : undefined;
    if (rz !== undefined && vt - rz < 1000) { FXS.raise.delete(e.cx + ',' + e.cy); e.emergeT = rz + 300; }
    else if (cat === 'z' && inMist(e.cx) && visible(e.cx, e.cy)) { e.emergeT = vt; spray(e.x, e.y + 0.25, 6, { col: '#4a3f33', sp: 1.2, vz: 2, g: 8, life: 600, size: 0.05, shape: CHIP }); }
    else if (cat === 'k') { if (e.side === S.side || Math.abs(e.x - (e.side === 0 ? 0 : S.W - 1)) < 1.5) e.spawnT = vt; }
    else if (e.side === S.side && cat !== 'z' && since(e.spawnT) > 150 && !(e.kind === 'dama' && FXS.promoAt === e.cx + ',' + e.cy)) placed(e, cat === 'b');   // a promoted Dáma gets the crown burst, not a drop-in
    return;
  }
  const dmg = e.rhp - e.hp;
  if (dmg && e.maxhp === e.rmax && (e.side === S.side || visible(e.cx, e.cy))) {
    const dot = Math.abs(dmg) < 3 && ((e.flags & 2) || (cat !== 'z' && cat !== 'b' && inMist(e.cx)) || dmg < 0);
    if (dmg >= 2 && !dot) hitReact(e, dmg);
    if (FXS.o.nums) addNum(e, dmg, dot);
  }
  e.rhp = e.hp; e.rmax = e.maxhp;
}
function hitReact(e, dmg) {
  // under sustained fire the flash/pop/sparks repeat at most every 250 ms, so a mobbed target never turns solid white
  const big = dmg > e.maxhp * 0.3, dir = e.hitDir && since(e.hitDirT) < 300 ? e.hitDir : null;
  if (!big && since(e.hitT) < 250) return;
  e.hitT = FXS.vt; e.nudge = dir;
  spray(e.x, e.y - 0.1, big ? 10 : 5, { col: '#ffd9a0', sp: 2.6, life: 220, size: 0.045, shape: SPARK, light: true, dir: dir ? Math.atan2(-dir[1], -dir[0]) : undefined, spread: 1.4 });
  if (big && e.side === S.side) addTrauma(0.04);
}
function addNum(e, dmg, dot) {
  const vt = FXS.vt, heal = dmg < 0, kind = heal ? 'h' : e.flags & 256 ? 'b' : dot ? 't' : 'd';
  const n = FXS.nums.find(q => q.key === e.id && q.kind === kind && vt - q.t0 < (dot || heal ? 600 : 300));
  if (n) { n.val += Math.abs(dmg); n.pop = vt; n.x = e.x; n.y = e.y; return; }
  const col = heal ? PAL.hpOk : kind === 'b' ? PAL.muted : e.side === S.side ? '#e46a5a' : e.flags & 12 ? PAL.giltHi : PAL.text;
  FXS.nums.push({ key: e.id, kind, x: e.x, y: e.y, jx: (Math.random() - 0.5) * 0.3, val: Math.abs(dmg), col, t0: vt, pop: vt, th: false });
  trimNums();
}
function trimNums() {
  while (FXS.nums.length > 48) { let k = 0; FXS.nums.forEach((q, i) => { if (q.val < FXS.nums[k].val) k = i; }); FXS.nums.splice(k, 1); }
}
function onDiff(m, prev) {
  const vt = FXS.vt;
  if (prev) {
    for (const s of [0, 1]) {
      const drop = prev.th[s] - m.th[s];
      if (drop >= 5) {
        FXS.thHit[s] = vt;
        const x = s === 0 ? -0.6 : S.W - 0.4;
        spray(x, FXS.thRow[s], 4, { col: '#6b645b', sp: 1.6, vz: 2, g: 9, life: 700, size: 0.07, shape: CHIP, spin: 10, dir: s === 0 ? 0 : Math.PI, spread: 1.6 });
        if (s === S.side) addTrauma(Math.min(0.12, 0.04 + drop / 2000));
      }
      if (drop > 0 && FXS.o.nums) {
        const n = FXS.nums.find(q => q.key === 'th' + s && vt - q.t0 < 400);
        if (n) { n.val += drop; n.pop = vt; }
        else { FXS.nums.push({ key: 'th' + s, kind: 'd', x: s === 0 ? -1 : S.W, y: FXS.thRow[s], jx: 0, val: drop, col: s === S.side ? '#e46a5a' : PAL.text, t0: vt, pop: vt, th: true }); trimNums(); }
      }
    }
    if (m.st > prev.st) {
      const st = Math.min(prev.st, 6);
      FXS.sweep = { t0: vt, lo: Math.max(0, S.mist[0] - st), hi: Math.min(S.W - 1, S.mist[1] + st) };
    }
    if (prev.out[S.side] > 0 && m.out[S.side] <= 0) FXS.outEnd = vt;
    if (m.tech.length > prev.tech.length) FXS.band = vt;
    if (m.kr && prev.kr && prev.kr.bcd > 0 && m.kr.bcd <= 0) { const k = S.ents.get(m.kr.id); if (k) k.shimT = vt; }
  }
  const seen = new Set();
  for (const c of m.cr) {
    const [id, x, y, rar, land] = c;
    seen.add(id);
    let r = FXS.crates.get(id);
    const at = vt + Math.max(0, land) * 1000;
    if (!r) { r = { crate: true, id, c, land: at, pop: prev && land <= 0 ? vt : -1e9, ch: [c[6] || 0, c[7] || 0], cont: -1e9 }; FXS.crates.set(id, r); }
    else {
      if (r.c[4] > 0 && land <= 0) landed(c);
      if (Math.abs(at - r.land) > 150 || land <= 0) r.land = at;
      const ch0 = c[6] || 0, ch1 = c[7] || 0;
      if (c[8] || (ch0 > 0 && ch1 > 0 && ch0 >= r.ch[0] && ch1 >= r.ch[1])) r.cont = Math.max(r.cont, vt + 400);   // c[8]: contested right now
      r.ch = [ch0, ch1]; r.c = c;
    }
    r.cy = y;
  }
  for (const id of [...FXS.crates.keys()]) if (!seen.has(id)) FXS.crates.delete(id);
}
function landed(c) {
  const [, x, y, rar] = c;
  S.fx.push({ type: 'L', a: x, b: y, c: rar, t0: FXS.vt, life: rar >= 3 ? FX_LIFE.L : 400 });
  dust(x, y + 0.2, 14, { sp: 1.8, life: 700 });
  spray(x, y, 8, { col: RAR_COL[rar] || PAL.gilt, sp: 2, vy: -0.4, life: 700, size: 0.06, shape: GEM, light: true, spin: 8 });
  addDecal('scorch', x, y, 6000, 1);
  addTrauma(0.08 + 0.04 * rar, mineAt(x, -1));
}

/* ---------------- frame loop ---------------- */
let lastT = performance.now();
const CAM = { k: 1, x: 0, y: 0 };
function frame(now) {
  requestAnimationFrame(frame);
  const rdt = Math.min(0.1, (now - lastT) / 1000); lastT = now;
  if (!S.snap || !(S.inGame || FXS.fin) || !CS) { QUAL.prev = 0; return; }
  qualityWatch(now);
  FXS.o = fxOpts();
  if (FXS.fin) runFinale(now);
  const scale = FXS.fin && !FXS.o.calm ? 0.3 : now < FXS.slowUntil && now >= FXS.freeze ? 0.35 : 1;
  const dt = now < FXS.freeze ? 0 : rdt * scale;
  FXS.vt += dt * 1000; FXS.dt = dt; FXS.rdt = rdt;
  FXS.trauma = Math.max(0, FXS.trauma - 1.4 * rdt);
  const k = 1 - Math.exp(-dt * 16), kid = S.kp && S.kp.id;
  if (dt) for (const e of S.ents.values()) {
    if (e.id === kid) continue;
    const ox = e.dx, oy = e.dy;
    e.dx += (e.x - e.dx) * k; e.dy += (e.y - e.dy) * k;
    track(e, e.dx - ox, e.dy - oy);
  }
  predictKing(rdt);
  if (S.kp) { const me = S.ents.get(S.kp.id); if (me) { track(me, S.kp.x - me.dx, S.kp.y - me.dy); me.dx = S.kp.x; me.dy = S.kp.y; } }
  stepParts(dt);
  if (DEMO) { DEMO.fps.push(rdt * 1000); if (DEMO.fps.length > 120) DEMO.fps.shift(); }
  if (PERF) PERF.begin();
  draw(now);
  if (PERF) PERF.end();
  if (DEMO) DEMO.hud();
  if (PERF) PERF.hud();
  if (ropt('fps', false)) fpsCorner();
}
// "Ukazovat FPS": a small corner counter with the quality level (screen space, top right)
function fpsCorner() {
  const md = median(QUAL.iv), text = `${md ? Math.round(1000 / md) : '–'} fps · Q${QUAL.lvl}${QUAL.auto ? ' auto' : ''}`;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  ctx.font = '700 14px "Alegreya Sans", Candara, sans-serif'; ctx.textBaseline = 'middle';
  const w = ctx.measureText(text).width + 14, X = cv.width / DPR - w - 6;
  ctx.fillStyle = 'rgba(11,8,6,0.75)'; ctx.fillRect(X, 6, w, 24);
  ctx.fillStyle = PAL.giltHi; ctx.fillText(text, X + 7, 18.5);
}
requestAnimationFrame(frame);
function track(e, mx, my) {
  const d = Math.hypot(mx, my);
  if (Math.abs(mx) > 0.002) e.face = scrDx(mx) > 0 ? 1 : -1;
  if (d > 0.002) {
    e.trav += d; e.rest = 0;
    if (e.flags & 512 && Math.random() < 0.2) dust(e.dx - scrDx(e.face) * 0.25, e.dy + 0.28, 1, { sp: 0.3, life: 400, size: 0.08 });
  } else if (e.trav && ++e.rest >= 2) {
    if (catOf(e) === 'u') { e.landT = FXS.vt; dust(e.dx, e.dy + 0.28, 3, { sp: 0.7, life: 380, size: 0.08 }); }
    e.trav = 0;
  }
}

/* ---------------- finale ---------------- */
function startFinale(m, done) {
  let fired = false;
  const fin = () => { if (fired) return; fired = true; FXS.fin = null; done(); };
  if (!S.snap || !CS || !m || /Chyba serveru/.test(m.reason || '')) { fin(); return; }
  FXS.o = fxOpts();
  const dur = FXS.o.calm ? 1000 : 2200;
  FXS.fin = { t0: performance.now(), dur, n: 0, losers: m.winner === -1 ? [0, 1] : [1 - m.winner], mate: /mat/i.test(m.reason || ''), lead: 0 };
  FXS.fin.lead = FXS.fin.mate ? 350 : 0;
  setTimeout(fin, dur);
}
function runFinale(now) {
  const F = FXS.fin, el = now - F.t0 - F.lead, total = FXS.o.calm ? 4 : 9;
  const n = el < 0 ? 0 : Math.min(total, Math.floor(el / 110) + 1);
  while (F.n < n) {
    const i = F.n++, y = i / (total - 1) * (S.H - 1);
    for (const s of F.losers) {
      const x = s === 0 ? -1 : S.W;
      S.fx.push({ type: 'b', a: x, b: y, c: 0.9, side: s, t0: FXS.vt, life: FX_LIFE.b });
      dust(x, y, 6, { col: '#1e1814', sp: 1.4, life: 900, size: 0.25, grow: 2, a: 0.7 });
      spray(x, y, 10, { col: PAL.candle, sp: 3, vz: 2.5, g: 7, life: 700, size: 0.05, shape: SPARK, light: true });
      spray(x, y, 3, { col: '#6b645b', sp: 2, vz: 3, g: 9, life: 900, size: 0.1, shape: CHIP, spin: 10 });
    }
    if (FXS.o.calm) continue;
    addTrauma(0.25);
    if (i === total - 1) { addTrauma(1); FXS.trauma = 1; hitStop(250); screenFlash(0.22, 60); }
  }
}

/* ---------------- draw ---------------- */
const ZLIST = [];
function draw(now) {
  const m = S.snap, o = FXS.o, W = S.W, H = S.H;
  const [lo, hi] = mistRange();
  const amp = Math.min(7, 0.22 * CS * FXS.trauma ** 2) * o.shake, t = now / 1000;
  const sx = amp * (Math.sin(t * 86) * 0.6 + Math.sin(t * 145 + 1.3) * 0.4), sy = amp * (Math.sin(t * 97 + 2.1) * 0.6 + Math.sin(t * 131 + 0.4) * 0.4);
  let z = 1, fx0 = 0, fy0 = 0;
  if (FXS.fin && !o.calm) {
    const F = FXS.fin, p = easeOut(clamp01((now - F.t0) / 600));
    z = 1 + 0.06 * p; fx0 = F.losers.length === 2 ? OX + (W + 2) * CS / 2 : px(F.losers[0] === 0 ? -1 : W); fy0 = OY + H * CS / 2;
  }
  CAM.k = DPR * z; CAM.x = (sx + fx0 * (1 - z)) * DPR; CAM.y = (sy + fy0 * (1 - z)) * DPR;
  if (z === 1) { CAM.x = Math.round(CAM.x); CAM.y = Math.round(CAM.y); }   // whole device pixels keep the blit on the copy path
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  // the opaque board layer covers the whole canvas unless the camera shakes or zooms: skip the redundant clear (raster cost)
  // (shake: only the edge strips the shifted layer leaves bare; finale zoom: the whole canvas)
  ctx.fillStyle = PAL.bg;
  if (CAM.k !== DPR) ctx.fillRect(0, 0, cv.width, cv.height);
  else {
    if (CAM.x) ctx.fillRect(CAM.x > 0 ? 0 : cv.width + CAM.x, 0, Math.abs(CAM.x), cv.height);
    if (CAM.y) ctx.fillRect(0, CAM.y > 0 ? 0 : cv.height + CAM.y, cv.width, Math.abs(CAM.y));
  }
  const layer = layerCanvas(now);
  if (z === 1) { ctx.setTransform(1, 0, 0, 1, CAM.x, CAM.y); ctx.drawImage(layer, 0, 0); }   // one opaque, unscaled blit
  else { ctx.setTransform(CAM.k, 0, 0, CAM.k, CAM.x, CAM.y); ctx.drawImage(layer, 0, 0, cv.width / DPR, cv.height / DPR); }
  ctx.setTransform(CAM.k, 0, 0, CAM.k, CAM.x, CAM.y);
  showMist(now, lo, hi, m.ni);
  relicZone(m, now, false);
  showThrone(0, now); showThrone(1, now);
  for (const q of m.qb) showBarrier(q, now);
  if (m.job) jobArc(m.job, now);
  auraRings(m, now);
  // bodies in depth order (lower rows overlap upper ones)
  ZLIST.length = 0;
  for (const e of S.ents.values()) { e.sy = catOf(e) === 'b' ? e.cy - 0.01 : e.dy; ZLIST.push(e); }
  FXS.dead = FXS.dead.filter(d => since(d.t0) < d.life);
  for (const d of FXS.dead) { d.sy = d.cy; ZLIST.push(d); }
  for (const r of FXS.crates.values()) if (r.c[4] <= 0) { r.sy = r.cy; ZLIST.push(r); }
  ZLIST.sort((a, b) => a.sy - b.sy);
  for (const it of ZLIST) {
    if (it.corpse) showCorpse(it, now);
    else if (it.crate) showCrate(it, now);
    else { const c = catOf(it); if (c === 'b') showBuilding(it, now); else if (c === 'u') showUnit(it, now); else if (c === 'z') showZombie(it, now); else showKing(it, now); }
  }
  for (const e of S.ents.values()) overlay(e, now);
  for (const d of m.dr) showDrone(d, now);
  for (const c of m.mc || []) showCloud(c, now);
  drawParts(false);
  shade(m, now);
  drawFx(now);
  drawParts(true);
  showNums();
  const fog = fogPaths(), fogc = !!ropt('fogc', false);
  ctx.fillStyle = fogPat(fogc); ctx.fill(fog.cells);
  ctx.strokeStyle = 'rgba(0,0,0,0.6)'; ctx.lineWidth = 4; ctx.stroke(fog.edges);
  ctx.strokeStyle = rgba(PAL.gilt, 0.55); ctx.lineWidth = fogc ? 2 : 1.2; ctx.setLineDash([2, 4]); ctx.stroke(fog.edges); ctx.setLineDash([]);
  for (const g of S.ghosts.values()) {
    if (visible(g.cx, g.cy)) continue;
    const X = px(g.cx), Y = py(g.cy);
    putSpr(sprBuilding(g.kind, g.side, g.lvl, g.path, 'ghost'), X, Y, 0.9);
    ink('?', X + CS * 0.32, Y - CS * 0.42, CS * 0.3, PAL.sepia);
  }
  relicZone(m, now, true);
  for (const r of FXS.crates.values()) if (r.c[4] > 0) crateDrop(r, now);
  for (const st of m.ns) showStrike(st, now);
  if (m.lu) showLure(m.lu, now);
  for (const r of m.rv) ring(px(r[0]), py(r[1]), (r[3] || 2.5) * CS, PAL.giltHi, 1.5, 0.7, [6, 6], -now / 40, 2);
  const bt = since(FXS.band);
  if (bt < 600) {
    ctx.globalCompositeOperation = 'lighter';
    const X = S.side === 0 ? px(-1 + bt / 600 * (S.half + 1)) : px(W - bt / 600 * (S.half + 1));
    ctx.globalAlpha = 0.4 * (1 - bt / 600); ctx.drawImage(glowOf(PAL.giltHi), X - CS * 0.7, OY - CS, CS * 1.4, (H + 2) * CS);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  }
  showPreview(now);
  showSelection(now);
  if (m.kr && m.kr.dead > 0) {   // the 0.2 dim is part of shade()
    const X = px(S.side === 0 ? -1 : W), Y = py((H - 1) / 2), rs = (S.defs.kral && S.defs.kral.respawn) || 15;
    arcP(X, Y, CS * 0.75, 1 - m.kr.dead / rs, PAL.giltHi, 3);
    ink(String(Math.ceil(m.kr.dead)), X, Y - CS * 1.05, CS * 0.36, PAL.giltHi);
  }
  // screen space: no shake from here on
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const hp = m.th[S.side] / S.throneMax;
  if (hp < 0.5) {
    let a = 0.06;
    if (hp < 0.35) {
      const per = 60 / (60 + 50 * (1 - hp / 0.35)), ph = (now / 1000) % per;
      a = (hp < 0.15 ? 0.35 : 0.22) * (Math.exp(-((ph / 0.06) ** 2)) + 0.7 * Math.exp(-(((ph - 0.14) / 0.06) ** 2)));
      if (o.calm) a *= 0.5;
      a = Math.max(0.06, a);
    }
    drawVig('red', a);
  }
  if (m.ec && m.ec[0] === 1 && m.ec[1] <= 15) drawVig('dark', 0.45 * (1 - m.ec[1] / 15) * (0.85 + 0.15 * Math.sin(now / 160)));
  ctx.globalAlpha = 1;
  lightning(m, now);
  const fl = FXS.flash;
  if (fl && now - fl.t0 < fl.ms) {
    ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = fl.a * (1 - (now - fl.t0) / fl.ms);
    ctx.fillStyle = fl.col; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  }
}
function lightning(m, now) {
  if (!m.ni || !FXS.o.flash) { FXS.bolt = 0; return; }
  if (!FXS.bolt) FXS.bolt = now + 9000 + Math.random() * 7000;
  if (now >= FXS.bolt) { screenFlash(0.15, 60, PAL.ghost); FXS.flash2 = now + 150; FXS.bolt = now + 9000 + Math.random() * 7000; }
  if (FXS.flash2 && now >= FXS.flash2) { screenFlash(0.15, 60, PAL.ghost); FXS.flash2 = 0; }
}

/* ---------------- Mist, thrones, barriers ---------------- */
const WISP = new Map();
function wispsOf(col) {
  let w = WISP.get(col);
  if (w) return w;
  w = [1, 2, 3].map(seed => {
    const c = mkCanvas(256, 96), g = c.getContext('2d');
    for (let i = 0; i < 9; i++) {
      const x = 40 + hash(i, seed, 1) * 176, y = 30 + hash(i, seed, 2) * 36, r = 18 + hash(i, seed, 3) * 30;
      const gr = g.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, 'rgba(255,255,255,0.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.beginPath(); g.ellipse(x, y, r * 1.6, r * 0.7, 0, 0, TAU); g.fill();
    }
    g.globalCompositeOperation = 'source-in'; g.fillStyle = col; g.fillRect(0, 0, 256, 96);
    return c;
  });
  WISP.set(col, w);
  return w;
}
function showMist(now, lo, hi, night) {
  const sw = FXS.sweep, sp = sw ? since(sw.t0) / 1200 : 1;
  if (sw && sp < 1) {
    const e = easeOut(sp);
    lo = Math.round(sw.lo + (lo - sw.lo) * e); hi = Math.round(sw.hi + (hi - sw.hi) * e);
    for (const x of [lo - 0.5, hi + 0.5]) if (Math.random() < 0.5) dust(x, Math.random() * S.H - 0.5, 1, { col: PAL.mist, sp: 0.4, life: 900, size: 0.3, grow: 1.5, a: 0.25 });
  }
  const x0 = Math.min(px(lo), px(hi)) - CS / 2, w = (hi - lo + 1) * CS, h = S.H * CS, wisps = wispsOf(night ? PAL.blood : PAL.mist);
  ctx.save(); ctx.beginPath(); ctx.rect(x0 - CS * 0.3, OY, w + CS * 0.6, h); ctx.clip();
  // (the Mist tint itself is baked into BOARD)
  const n = Math.round(14 * (hi - lo + 1) / 4 * (QUAL.lvl === 0 ? 0.5 : 1)), face = Math.floor(now / 6000) % Math.max(1, n);
  for (let i = 0; i < n; i++) {
    const tt = now / 1000 * (0.015 + hash(i, 1, 2) * 0.02);
    const cx = x0 - CS + ((hash(i, 5, 6) + tt) % 1) * (w + CS * 2), cy = OY + ((hash(i, 7, 8) + Math.sin(tt * 3 + i) * 0.03 + 1) % 1) * h;
    const ww = CS * (2.2 + hash(i, 9, 1) * 1.8), wh = ww * 0.38;
    ctx.globalAlpha = 0.16 + hash(i, 2, 2) * 0.12;
    ctx.drawImage(wisps[i % 3], cx - ww / 2, cy - wh / 2, ww, wh);
    if (i === face) {
      ctx.globalAlpha = 0.08 * Math.sin(Math.PI * ((now % 6000) / 6000)); ctx.fillStyle = '#0b0a09';
      for (const s of [-1, 1]) { ctx.beginPath(); ctx.ellipse(cx + s * ww * 0.07, cy - wh * 0.08, ww * 0.035, wh * 0.12, 0, 0, TAU); ctx.fill(); }
      ctx.beginPath(); ctx.ellipse(cx, cy + wh * 0.18, ww * 0.03, wh * 0.14, 0, 0, TAU); ctx.fill();
    }
  }
  ctx.restore(); ctx.globalAlpha = 1;
  if (night && Math.random() < FXS.dt * 6) spray(Math.random() * S.W - 0.5, -0.5, 1, { col: '#8a8580', vy: 0.6, sp: 0.15, life: 6000, size: 0.03, shape: SPARK, drag: 1 });
}
const THR = [];
function throneCol(side, hp) {
  const h = S.H * CS, key = `${Math.round(hp * 200)}|${CS}|${h}|${DPR}`, t = THR[side];
  if (t && t.key === key) return t.c;
  const c = t && t.c.width === Math.ceil(CS * DPR) && t.c.height === Math.ceil(h * DPR) ? t.c : mkCanvas(CS * DPR, h * DPR);
  THR[side] = { key, c };
  const g = c.getContext('2d'), tm = TEAM[side], mt = MAT[side], bx = CS * 0.18, bw = CS * 0.64, top = h * (1 - hp);
  g.setTransform(DPR, 0, 0, DPR, 0, 0); g.clearRect(0, 0, CS, h);
  g.fillStyle = '#100c0a'; g.fillRect(0, 0, CS, h);
  if (hp > 0) {
    const jag = i => top + (i % 2 ? CS * 0.11 : 0) + hash(i, side, 4) * CS * 0.09, tail = h - CS * 0.1;
    g.save(); g.beginPath(); g.moveTo(bx, tail);
    for (let i = 0; i <= 8; i++) g.lineTo(bx + bw * i / 8, jag(i));
    g.lineTo(bx + bw, tail);
    if (side === 1) g.lineTo(bx + bw / 2, tail - CS * 0.45);           // B: swallow-tail banner
    g.closePath();
    const tg = g.createLinearGradient(bx, 0, bx + bw, 0);
    tg.addColorStop(0, tm.lo); tg.addColorStop(0.5, tm.c); tg.addColorStop(1, tm.lo);
    g.fillStyle = tg; g.fill(); g.clip();
    g.strokeStyle = 'rgba(0,0,0,0.25)'; g.lineWidth = 1;
    for (let yy = 0; yy < h; yy += CS * 0.5) { g.beginPath(); g.moveTo(bx + bw / 2, yy); g.lineTo(bx + bw, yy + CS * 0.25); g.lineTo(bx + bw / 2, yy + CS * 0.5); g.lineTo(bx, yy + CS * 0.25); g.closePath(); g.stroke(); }
    const ex = CS / 2, ey = h - CS * (side === 1 ? 1.25 : 0.95);
    g.beginPath();
    if (side === 0) { g.moveTo(ex - CS * 0.17, ey - CS * 0.18); g.lineTo(ex + CS * 0.17, ey - CS * 0.18); g.lineTo(ex + CS * 0.17, ey); g.quadraticCurveTo(ex + CS * 0.15, ey + CS * 0.16, ex, ey + CS * 0.22); g.quadraticCurveTo(ex - CS * 0.15, ey + CS * 0.16, ex - CS * 0.17, ey); g.closePath(); }
    else g.arc(ex, ey, CS * 0.17, 0, TAU);
    g.fillStyle = mt.base; g.fill(); g.strokeStyle = mt.ink; g.lineWidth = 2.2; g.stroke();
    if (mt.rim) { g.strokeStyle = mt.rim; g.lineWidth = 1; g.stroke(); }
    g.restore();
    if (hp < 1) {
      g.beginPath(); for (let i = 0; i <= 8; i++) g.lineTo(bx + bw * i / 8, jag(i));
      g.strokeStyle = 'rgba(255,138,42,0.35)'; g.lineWidth = 6; g.stroke();
      g.strokeStyle = '#ffb46a'; g.lineWidth = 2; g.stroke();
    }
  }
  const pw = Math.max(4, CS * 0.11);
  for (const x of [0, CS - pw]) { const pg = g.createLinearGradient(x, 0, x + pw, 0); pg.addColorStop(0, '#6b645b'); pg.addColorStop(1, '#2c2824'); g.fillStyle = pg; g.fillRect(x, 0, pw, h); }
  return c;
}
function showThrone(side, now) {
  const m = S.snap, x = side === 0 ? -1 : S.W, X = px(x), h = S.H * CS, F = FXS.fin;
  let hp = Math.max(0, Math.min(1, m.th[side] / ((S.thMax && S.thMax[side]) || S.throneMax)));
  if (F && F.losers.includes(side)) hp *= clamp01(1 - (now - F.t0 - F.lead) / 1100);
  ctx.drawImage(throneCol(side, hp), X - CS / 2, OY, CS, h);
  const check = m.ck[side] > 0, danger = hp < 0.3 || check, blink = danger && Math.floor(now / 250) % 2, pw = Math.max(4, CS * 0.11);
  if (blink) { ctx.fillStyle = rgba(PAL.rubric, 0.7); ctx.fillRect(X - CS / 2, OY, pw, h); ctx.fillRect(X + CS / 2 - pw, OY, pw, h); }
  const Y = py((S.H - 1) / 2), jit = danger && !FXS.o.calm ? (Math.random() - 0.5) * 2 : 0;
  putSpr(sprThrone(side), X + jit, Y);
  if (danger) bell(X, Y - CS * 1.35, now);
  if (hp > 0 && hp < 1 && Math.random() < FXS.dt * 3.3) spray(x + (Math.random() - 0.5) * 0.55, (1 - hp) * S.H - 0.5, 1, { col: '#ffb46a', vy: -0.5, sp: 0.15, life: 1300, size: 0.045, light: true, drag: 0.99 });
  const ht = since(FXS.thHit[side]);
  if (ht < 120) { ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = `rgba(255,255,255,${0.35 * (1 - ht / 120)})`; ctx.fillRect(X - CS / 2, OY, CS, h); ctx.globalCompositeOperation = 'source-over'; }
  if (m.sh[side] > 0) {
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.5; ctx.drawImage(glowOf(PAL.giltHi), X - CS * 1.2, OY - CS * 0.5, CS * 2.4, h + CS);
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU + now / 3000; seg(X + Math.cos(a) * CS * 0.5, Y + Math.sin(a) * CS * 0.5, X + Math.cos(a) * CS * 1.3, Y + Math.sin(a) * CS * 1.3, PAL.giltHi, 1, 0.35); }
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = 'rgba(236,208,138,0.6)'; ctx.lineWidth = 1; ctx.beginPath();
    for (let yy = OY; yy < OY + h; yy += CS * 0.5) { ctx.moveTo(X, yy); ctx.lineTo(X + CS / 2, yy + CS / 4); ctx.lineTo(X, yy + CS / 2); ctx.lineTo(X - CS / 2, yy + CS / 4); ctx.closePath(); }
    ctx.stroke();
  }
  if (check) {
    const home = side === 0 ? 0 : S.W - 1, rows = new Set(), mine = side === S.side, pulse = 0.6 + 0.4 * Math.sin(now / 120);
    for (const e of S.ents.values()) if (catOf(e) === 'u' && e.side !== side && e.cx === home) rows.add(e.cy);
    for (const r of rows) {
      if (mine) hazard(X - CS / 2, py(r) - CS / 2, CS, CS, PAL.rubric, 0.35, now);
      cornerMarks(X, py(r), CS * 0.92, mine ? PAL.rubric : PAL.giltHi, pulse);
    }
  }
}
function bell(X, Y, now) {
  const s = CS * 0.16, r = Math.sin(now / 140) * 0.45;
  ctx.save(); ctx.translate(X, Y - s); ctx.rotate(r);
  ctx.beginPath(); ctx.moveTo(-s * 0.15, 0); ctx.quadraticCurveTo(-s * 0.9, s * 0.2, -s * 0.85, s * 1.4); ctx.lineTo(s * 0.85, s * 1.4); ctx.quadraticCurveTo(s * 0.9, s * 0.2, s * 0.15, 0); ctx.closePath();
  ctx.fillStyle = PAL.gilt; ctx.fill(); ctx.strokeStyle = INK; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.beginPath(); ctx.arc(Math.sin(now / 140) * s * 0.3, s * 1.55, s * 0.22, 0, TAU); ctx.fillStyle = PAL.rubric; ctx.fill();
  ctx.restore();
}
function showBarrier(q, now) {
  const [y, t] = q, x1 = Math.min(px(S.mist[0]), px(S.mist[1])) - CS / 2, x2 = x1 + (S.mist[1] - S.mist[0] + 1) * CS, Y = py(y);
  const lw = CS * 0.11, lh = CS * 0.056;
  for (const o of [-0.16, 0.16]) {
    ctx.beginPath();
    for (let x = x1; x < x2 - lw; x += lw * 2) { const yy = Y + o * CS + Math.sin(now / 300 + x / 30) * 1; ctx.moveTo(x + lw * 2, yy); ctx.ellipse(x + lw, yy, lw, lh, 0, 0, TAU); }
    ctx.strokeStyle = '#141210'; ctx.lineWidth = 4; ctx.stroke();
    ctx.strokeStyle = PAL.ironL; ctx.lineWidth = 2; ctx.stroke();
  }
  const sx = (x1 + x2) / 2, r = CS * 0.19;
  ctx.beginPath(); ctx.arc(sx, Y, r, 0, TAU); ctx.fillStyle = '#9e2219'; ctx.fill(); ctx.strokeStyle = '#4a0d08'; ctx.lineWidth = 2; ctx.stroke();
  ink(String(Math.ceil(t)), sx, Y + 1, CS * 0.2, '#f0c9b8');
}
function jobArc(j, now) {
  const X = px(j[0]), Y = py(j[1]);
  arcP(X, Y, CS * 0.38, j[2], PAL.giltHi, 3);
  ctx.save(); ctx.translate(X, Y - CS * 0.05); ctx.rotate(Math.sin(now / 120) * 0.5 - 0.4);
  seg(0, CS * 0.16, 0, -CS * 0.12, PAL.wood, 3);
  ctx.beginPath(); ctx.moveTo(-CS * 0.15, -CS * 0.08); ctx.quadraticCurveTo(0, -CS * 0.2, CS * 0.15, -CS * 0.08); ctx.strokeStyle = PAL.ironL; ctx.lineWidth = 2.5; ctx.stroke();
  ctx.restore();
}

/* ---------------- relic zone, war-cry aura, darkness ---------------- */
function relicZone(m, now, top) {
  if (!m.rl || S.noRelic) return;
  const [x0, x1, y0, y1] = S.relicZone || [7, 8, 3, 5], [holder, cap, prog, secs] = m.rl;
  const L = Math.min(px(x0), px(x1)) - CS / 2, T = py(y0) - CS / 2, w = (Math.abs(x1 - x0) + 1) * CS, h = (y1 - y0 + 1) * CS;
  const cx = L + w / 2, cy = T + h / 2, awake = m.tm >= (S.relicFrom ?? 120);
  if (!top) {
    if (holder >= 0) { ctx.fillStyle = rgba(COL[holder], 0.14); ctx.fillRect(L, T, w, h); }
    ring(cx, cy, CS * 0.8, PAL.gilt, 1, awake ? 0.3 : 0.15);
    return;
  }
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.globalAlpha = awake ? 0.8 : 0.3; ctx.strokeRect(L + 2, T + 2, w - 4, h - 4);
  ctx.strokeStyle = holder >= 0 ? TEAM[holder].hi : PAL.gilt; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]); ctx.lineDashOffset = awake ? -now / 50 : 0;
  ctx.strokeRect(L + 2, T + 2, w - 4, h - 4); ctx.setLineDash([]); ctx.globalAlpha = 1;
  const bob = Math.sin(now / 500) * CS * 0.04;
  if (awake) { ctx.globalCompositeOperation = 'lighter'; glow(cx, cy, CS * 0.7, holder >= 0 ? COL[holder] : PAL.gilt, 0.35 + 0.1 * Math.sin(now / 300)); ctx.globalCompositeOperation = 'source-over'; }
  putSpr(sprIcon('relic', holder >= 0 ? TEAM[holder].hi : PAL.giltHi, 0.8), cx, cy + bob, awake ? 1 : 0.4);
  if (cap >= 0 && prog > 0) arcP(cx, cy, CS * 0.62, prog, TEAM[cap].hi, 3.5);
  if (holder >= 0 && secs > 0) arcP(cx, cy, CS * 0.46, 1 - secs / 40, PAL.giltHi, 1.5, 0.8);
}
function auraRings(m, now) {
  for (const e of S.ents.values()) {
    if (catOf(e) !== 'k') continue;
    const on = (e.flags & 1024) || (e.side === S.side ? m.kr && m.kr.ua > 0 : FXS.vt < FXS.aura[e.side]);
    if (!on) continue;
    const X = px(e.dx), Y = py(e.dy), R = 3 * CS, col = TEAM[e.side].hi, pulse = 0.6 + 0.2 * Math.sin(now / 200);
    ctx.globalCompositeOperation = 'lighter'; glow(X, Y, R, COL[e.side], 0.18); ctx.globalCompositeOperation = 'source-over';
    ring(X, Y, R, col, 2, pulse, [10, 8], -now / 30, 2);
  }
}
// one quarter-resolution shade blit: darkness (eclipse, night) with light holes, the outage dim (0.18, own half) and the
// dim while the own King is dead (0.2); drawn only when one of them is active
function shade(m, now) {
  const want = m.ni ? 0.6 : m.ec && m.ec[0] === 2 ? 0.55 : 0;
  FXS.dark += (want - FXS.dark) * Math.min(1, FXS.rdt * (want > FXS.dark ? (m.ni ? 0.6 : 1.4) : 1.5));
  const dark = FXS.dark >= 0.01, out = m.out[S.side] > 0, kd = !!(m.kr && m.kr.dead > 0);
  if (!dark && !out && !kd) return;
  const oX = (S.side === 0 ? OX : px(S.W - S.half) - CS / 2), oW = (S.half + 1) * CS;
  if (!dark) {   // flat dims only: fill them straight (the outage covers half the board, no full-board blit)
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.fillStyle = 'rgba(0,0,0,0.18)';
    if (out) ctx.fillRect(oX, OY, oW, S.H * CS);
    if (kd) { ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.fillRect(OX, OY, (S.W + 2) * CS, S.H * CS); }
    return;
  }
  const q = 4, w = Math.ceil((S.W + 2) * CS / q), h = Math.ceil(S.H * CS / q);
  if (!DARK || DARK.width !== w || DARK.height !== h) DARK = mkCanvas(w, h);
  const g = DARK.getContext('2d');
  g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1; g.clearRect(0, 0, w, h);
  if (dark) darkHoles(g, m, now, q, w, h);
  if (out) { g.fillStyle = 'rgba(0,0,0,0.18)'; g.fillRect((oX - OX) / q, 0, oW / q, h); }
  if (kd) { g.fillStyle = 'rgba(0,0,0,0.2)'; g.fillRect(0, 0, w, h); }
  ctx.drawImage(DARK, OX, OY, w * q, h * q);
}
function darkHoles(g, m, now, q, w, h) {
  const hole = glowOf('#ffffff');
  g.fillStyle = `rgba(4,3,10,${FXS.dark})`; g.fillRect(0, 0, w, h);
  g.globalCompositeOperation = 'destination-out';
  const L = (x, y, r, a) => { const R = r * CS / q; g.globalAlpha = a; g.drawImage(hole, (px(x) - OX) / q - R, (py(y) - OY) / q - R, R * 2, R * 2); };
  const home = S.side === 0 ? -0.5 : S.W - 0.5;
  for (let y = 0; y < S.H; y++) L(home, y, 2, 0.9);
  for (const e of S.ents.values()) {
    if (e.side !== S.side) continue;
    const c = catOf(e);
    if (c === 'k') L(e.dx, e.dy, 3 * (1 + 0.03 * Math.sin(now / 90)), 1);
    else if (c === 'b') L(e.cx, e.cy, e.kind === 'hlaska' && e.path === 'B' ? 3 : 1.2, 0.5);
  }
  for (const r of m.rv) L(r[0], r[1], r[3] || 2.5, 0.7);
  g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
}

/* ---------------- bodies ---------------- */
function showBuilding(e, now) {
  // hidden (mine, masked): ART's 'hidden' variant already has a half-alpha body and a full-alpha dashed side rim
  const hidden = e.flags & 128, off = e.flags & 8192, m = S.snap, vt = FXS.vt, X = px(e.cx), Y = py(e.cy), ay = GROUND * CS;
  const c = sprBuilding(e.kind, e.side, e.lvl, e.path, hidden ? 'hidden' : off ? 'off' : '');
  let sx = 1, sy = 1, ox = 0, oy = 0, a = 1;
  const sp = since(e.spawnT);
  if (sp < 480) {
    const p = clamp01(sp / 180), s = 1.35 - 0.35 * easeBack(p);
    sx = sy = s; oy = -0.25 * CS * (1 - p); a *= clamp01(sp / 120);
    if (sp > 180) ring(X, Y + ay * 0.8, CS * (0.3 + 0.5 * (sp - 180) / 300), '#8a7f70', 2, 0.6 * (1 - (sp - 180) / 300));
  }
  const up = since(e.lvlT);
  if (up < 300) { const s = 1 + 0.22 * Math.sin(up / 300 * Math.PI * 2.2) * (1 - up / 300); sx *= s; sy *= s; }
  const ht = since(e.hitT);
  if (ht < 150) ox = Math.sin(ht * 0.25) * 0.04 * CS * (1 - ht / 150);
  const atk = ATTACK.includes(e.kind) && e.side === S.side, dark = atk && (m.out[S.side] > 0 || since(FXS.outEnd) < vx(e.cx) * 40 + 40);
  if (dark) a *= Math.random() < 0.06 ? 0.35 : 0.6;
  const rk = since(e.recoilT), kick = rk < 120 ? (1 - rk / 120) : 0;
  if (kick) { sx *= 1 - 0.04 * kick; sy *= 1 - 0.04 * kick; }
  putSpr(c, X + ox, Y + oy, a, sx, sy, 0, ay);
  if (ht < 90) putSpr(whiteOf(c), X + ox, Y + oy, 0.85 * (1 - ht / 90), sx, sy, 0, ay);
  const lit = since(FXS.outEnd) - vx(e.cx) * 40;
  if (atk && lit > 0 && lit < 90 && m.out[S.side] <= 0) putSpr(whiteOf(c), X, Y, 0.5 * (1 - lit / 90));
  if (e.kind === 'kulomet' || e.kind === 'sniper') {
    const aim = S.aims.get(e.cx + ',' + e.cy), by = Y + oy - (e.kind === 'sniper' ? 0.18 : 0.12) * CS * sy;
    const want = aim ? Math.atan2(py(aim[1]) - by, px(aim[0]) - X) : (e.side === S.side ? 0 : Math.PI);
    let dA = want - e.ang; dA = Math.atan2(Math.sin(dA), Math.cos(dA));
    e.ang += dA * Math.min(1, FXS.rdt * 14);
    const back = kick * (e.kind === 'sniper' ? 0.12 : 0.07) * CS, ca = Math.cos(e.ang), sa = Math.sin(e.ang);
    putSpr(sprBarrel(e.kind, e.side, e.path), X + ox - ca * back, by - sa * back, hidden ? a * 0.5 : a, 1, 1, e.ang);
    const tipX = X + ox + ca * CS * 0.42, tipY = by + sa * CS * 0.42;
    ctx.globalCompositeOperation = 'lighter';
    if (rk < 60) { const s = CS * (e.kind === 'sniper' ? 0.6 : 0.35) * (1 - rk / 60); glow(tipX, tipY, s, PAL.candle, 1); glow(tipX, tipY, s * 0.45, PAL.flame, 1); }
    const aimT = now - (e.aimT || -1e9);
    if (aimT < 500) glow(tipX, tipY, CS * (0.08 + 0.22 * aimT / 500), PAL.rubric, 0.5 + 0.5 * aimT / 500);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  }
  ctx.save(); ctx.translate(X + ox, Y + oy + ay); ctx.scale(sx * CS, sy * CS); ctx.translate(0, -GROUND);
  if (!dark && !off) liveBuilding(ctx, e, now);
  ctx.restore(); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  if (off) crackle(X, Y, e.id, now);
  if (dark && Math.floor(now / 200) % 2) {
    const s = CS * 0.16;
    for (const [w, col] of [[5, INK], [2.5, PAL.rubric]]) { seg(X - s, Y - s, X + s, Y + s, col, w); seg(X + s, Y - s, X - s, Y + s, col, w); }
  }
}
function floorShadow(X, Y, rx, a) {
  ctx.globalAlpha = a; ctx.fillStyle = '#000'; ctx.beginPath(); ctx.ellipse(X, Y, rx, rx * 0.3, 0, 0, TAU); ctx.fill(); ctx.globalAlpha = 1;
}
// Shared motion for pieces, zombies and Kings: hit pop + nudge, melee lunge. Returns [dx, dy, scale].
function motion(e) {
  const ht = since(e.hitT), lt = since(e.lungeT);
  let ox = 0, oy = 0, s = 1;
  if (ht < 120) {
    const k = 1 - ht / 120; s = 1 + 0.12 * k;
    if (e.nudge) { ox += scrDx(e.nudge[0]) * 0.06 * CS * k; oy += e.nudge[1] * 0.06 * CS * k; }
  }
  if (lt < 180 && e.lungeDir) {
    const k = lt < 60 ? lt / 60 : 1 - (lt - 60) / 120;
    ox += scrDx(e.lungeDir[0]) * 0.18 * CS * k; oy += e.lungeDir[1] * 0.18 * CS * k;
  }
  return [ox, oy, s];
}
function showUnit(e, now) {
  const ay = GROUND * CS, face = e.side === S.side ? 1 : -1, X = px(e.dx), Y = py(e.dy);
  const lift = e.trav > 0 ? (e.kind === 'jezdec' ? 0.35 : 0.12) * Math.sin(Math.PI * Math.min(1, e.trav / (HOP[e.kind] || 1))) * CS : 0;
  e.lift = lift;
  let [ox, oy, s] = motion(e), sx = s, sy = s, rot = 0;
  const hidden = e.flags & 128;
  const lt = since(e.landT);
  if (lt < 80) { const k = 1 - lt / 80; sx *= 1 + 0.12 * k; sy *= 1 - 0.12 * k; }
  const sp = since(e.spawnT);
  if (sp < 330) {
    if (sp < 150) { ring(X, Y + ay * 0.6, CS * (0.8 - 0.5 * sp / 150), COL[e.side], 2, 0.9, null, 0, 2); return; }
    const p = (sp - 150) / 180, k = p < 0.6 ? 1.15 * p / 0.6 : 1.15 - 0.15 * (p - 0.6) / 0.4; sx *= k; sy *= k;
  }
  const vs = since(e.spinT);
  if (vs < 300) sx *= Math.cos(vs / 300 * TAU);
  if (e.flags & 32) rot = Math.sin(now / 1000 * 6 * TAU) * 0.17;
  floorShadow(X, Y + ay, CS * 0.22 * (1 - lift / CS * 0.8), 0.35);
  if (e.flags & 1024) auraRim(X, Y + ay, e.side, now);
  const c = sprUnit(e.kind, e.side, !!(e.flags & 1), face, hidden ? 'hidden' : '');
  putSpr(c, X + ox, Y - lift + oy, 1, sx, sy, rot, ay);
  const ht = since(e.hitT);
  if (ht < 90) putSpr(whiteOf(c), X + ox, Y - lift + oy, 0.85 * (1 - ht / 90), sx, sy, rot, ay);
}
function auraRim(X, Y, side, now) {
  const p = 0.5 + 0.5 * Math.sin(now / 150);
  ctx.globalCompositeOperation = 'lighter'; glow(X, Y, CS * 0.4, COL[side], 0.35 + 0.3 * p); ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = 0.6 + 0.4 * p; ctx.strokeStyle = TEAM[side].hi; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(X, Y, CS * 0.3, CS * 0.1, 0, 0, TAU); ctx.stroke(); ctx.globalAlpha = 1;
}
function showZombie(e, now) {
  const ay = GROUND * CS, X = px(e.dx), Y = py(e.dy), moving = e.trav > 0;
  const [ox, oy, s] = motion(e), f = e.face || 1;
  const rot = (moving ? Math.sin(now / 1000 * 2 * TAU + e.id) * 0.1 : Math.sin(now / 700 + e.id) * 0.03) + 0.06 * f;
  const bob = moving ? -Math.abs(Math.sin(now / 1000 * 2 * Math.PI + e.id)) * 0.03 * CS : 0;
  const big = e.kind === 'obr' || e.kind === 'alfa', c = sprZombie(e.kind, moving ? Math.floor(e.trav * 3 + e.id) % 4 : 0, 1, ownOf(e));
  floorShadow(X, Y + ay, CS * (big ? 0.38 : 0.22), 0.4);
  const em = since(e.emergeT);
  if (em < 0) return;   // a raised zombie waits for the hand (fx Z)
  if (em < 400) {
    const p = easeOut(em / 400), hgt = c.height / DPR;
    ctx.save(); ctx.beginPath(); ctx.rect(X - CS * 2, Y + ay - hgt, CS * 4, hgt); ctx.clip();
    putSpr(c, X, Y + (1 - p) * hgt * 0.7, 1, f, 1, 0, ay);
    ctx.restore();
    return;
  }
  const tt = since(e.turnT), flip = tt < 450 ? Math.cos(tt / 450 * TAU) : 1;   // fx W: the zombie turns (eyes flip)
  putSpr(c, X + ox, Y + oy + bob, 1, f * s * flip, s, rot, ay);
  const ht = since(e.hitT);
  if (ht < 90) putSpr(whiteOf(c), X + ox, Y + oy + bob, 0.85 * (1 - ht / 90), f * s * flip, s, rot, ay);
}
// owner side of an owned zombie (flag 2048, 4096 = side 1), else -1
const ownOf = e => e.flags & 2048 ? (e.flags & 4096 ? 1 : 0) : -1;
// EMP-off building: blue-white crackle lines (shape, not colour only), re-rolled every 90 ms
function crackle(X, Y, id, now) {
  const t = Math.floor(now / 90), r = CS * 0.42;
  ctx.beginPath();
  for (let i = 0; i < 3; i++) {
    if (hash(t, i, id) < 0.25) continue;
    let a = hash(i, t, id) * TAU, x = X + Math.cos(a) * r * 0.2, y = Y - CS * 0.15 + Math.sin(a) * r * 0.2;
    ctx.moveTo(x, y);
    for (let j = 1; j <= 4; j++) { a += (hash(t, j, i + id) - 0.5) * 1.6; x += Math.cos(a) * r * 0.22; y += Math.sin(a) * r * 0.22; ctx.lineTo(x, y); }
  }
  ctx.lineJoin = 'round'; ctx.strokeStyle = 'rgba(11,8,6,0.8)'; ctx.lineWidth = 3.5; ctx.stroke();
  ctx.strokeStyle = '#e9f2ff'; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.globalCompositeOperation = 'lighter'; glow(X, Y - CS * 0.15, CS * 0.35, '#9fb8ff', 0.25 + 0.15 * hash(t, 7, id)); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
}
// Mor cloud [x, y, t, s]: a grey-green hatched 3x3 that thins as t (s left of 8) drops; dashed rim in the caster's enamel.
function showCloud(c, now) {
  const [x, y, t, s] = c, k = clamp01(t / 8), X = px(x), Y = py(y), h = CS * 1.5, step = CS * (0.16 + 0.22 * (1 - k));
  ctx.save(); ctx.beginPath(); ctx.rect(X - h, Y - h, h * 2, h * 2); ctx.clip();
  ctx.globalAlpha = 0.1 + 0.18 * k; ctx.fillStyle = '#6c7a5a'; ctx.fillRect(X - h, Y - h, h * 2, h * 2);
  const off = (now / 60) % step;
  ctx.beginPath();
  for (let d = -h * 2 - step + off; d < h * 2; d += step) { ctx.moveTo(X - h + d, Y + h); ctx.lineTo(X + h + d, Y - h); }
  ctx.globalAlpha = 0.3 + 0.45 * k; ctx.strokeStyle = '#a8b896'; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.restore();
  ctx.globalAlpha = 0.5 + 0.4 * k; ctx.setLineDash([5, 4]); ctx.lineDashOffset = -now / 50;
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.strokeRect(X - h, Y - h, h * 2, h * 2);
  ctx.strokeStyle = TEAM[s] ? TEAM[s].hi : '#a8b896'; ctx.lineWidth = 1.5; ctx.strokeRect(X - h, Y - h, h * 2, h * 2);
  ctx.setLineDash([]); ctx.lineDashOffset = 0; ctx.globalAlpha = 1;
}
function showKing(e, now) {
  const ay = GROUND * CS, X = px(e.dx), Y = py(e.dy), mine = e.side === S.side;
  const [ox, oy, s] = motion(e), sp = since(e.spawnT), c = sprKing(e.side, e.face || 1);
  floorShadow(X, Y + ay, CS * 0.26, 0.4);
  if (mine) {
    ctx.globalAlpha = 0.8; ctx.strokeStyle = PAL.giltHi; ctx.lineWidth = 1.5; ctx.setLineDash([3, 4]); ctx.lineDashOffset = -now / 60;
    ctx.beginPath(); ctx.ellipse(X, Y + ay, CS * 0.34, CS * 0.12, 0, 0, TAU); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
  }
  if (sp < 700) {
    const p = sp / 700;
    ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 1 - p;
    ctx.drawImage(glowOf(PAL.giltHi), X - CS * 0.5, Y - CS * 3, CS, CS * 3.4); ctx.globalCompositeOperation = 'source-over';
    putSpr(c, X, Y + (1 - easeOut(p)) * CS * -0.4, clamp01(p * 2), s, s, 0, ay);
    return;
  }
  putSpr(c, X + ox, Y + oy, 1, s, s, 0, ay);
  const ht = since(e.hitT);
  if (ht < 90) putSpr(whiteOf(c), X + ox, Y + oy, 0.85 * (1 - ht / 90), s, s, 0, ay);
  const sh = since(e.shimT);
  if (sh < 350) { ctx.globalCompositeOperation = 'lighter'; ring(X, Y, CS * (0.35 + 0.25 * sh / 350), PAL.giltHi, 2, 1 - sh / 350); ctx.globalCompositeOperation = 'source-over'; }
}
function showDrone(d, now) {
  const [x, y, side] = d, X = px(x), Y = py(y), hover = d[3] || S.snap.cr.some(c => Math.hypot(c[1] - x, c[2] - y) < 0.3);
  const bob = Math.sin(now / (hover ? 120 : 220) + x * 3) * CS * (hover ? 0.06 : 0.03);
  floorShadow(X, Y + CS * 0.35, CS * 0.18, 0.3);
  putSpr(sprDrone(side, Math.floor(now / 110) % 2), X, Y - CS * 0.15 + bob);
}
function showCrate(r, now) {
  const [, x, y, rar, , ttl] = r.c, X = px(x), Y = py(y), bob = Math.sin(now / 350 + x) * CS * 0.03;
  const pp = since(r.pop), k = pp < 300 ? easeBack(pp / 300) : 1;
  ctx.globalCompositeOperation = 'lighter'; glow(X, Y, CS * 0.55, RAR_COL[rar] || PAL.gilt, 0.25); ctx.globalCompositeOperation = 'source-over';
  floorShadow(X, Y + CS * GROUND, CS * 0.3, 0.4);
  putSpr(sprCrate(rar), X, Y + bob, ttl <= 5 && Math.floor(now / 125) % 2 ? 0.35 : 1, k, k, 0, GROUND * CS);
  const [c0, c1] = r.ch, rr = CS * 0.44;
  if (FXS.vt < r.cont) {
    const spin = now / 900;
    for (const s of [0, 1]) {
      ctx.beginPath(); ctx.arc(X, Y, rr, spin + s * Math.PI, spin + s * Math.PI + Math.PI * 0.92);
      ctx.strokeStyle = INK; ctx.lineWidth = 5.5; ctx.stroke(); ctx.strokeStyle = TEAM[s].hi; ctx.lineWidth = 3; ctx.stroke();
    }
    ink('SPORNÁ', X, Y - CS * 0.72, CS * 0.24, PAL.giltHi);
  } else {
    if (c0 > 0) arcP(X, Y, rr, c0, TEAM[0].hi, 3);
    if (c1 > 0) arcP(X, Y, rr + 4, c1, TEAM[1].hi, 3);
  }
}
function showCorpse(d, now) {
  const age = since(d.t0), ay = GROUND * CS, X = px(d.x), Y = py(d.y);
  if (d.corpse === 'z') {
    if (age < 120) { putSpr(d.c, X, Y, 1, d.face, 1, 0, ay); putSpr(whiteOf(d.c), X, Y, 1 - age / 120, d.face, 1, 0, ay); return; }
    const p = (age - 120) / 330;
    putSpr(d.c, X, Y + p * 0.1 * CS, 1 - p, d.face * (1 + 0.35 * p), 1 - 0.75 * p, 0, ay);
  } else if (d.corpse === 'u') {
    const tp = clamp01(age / 280), rot = d.dir * (Math.PI / 2) * tp * tp + (age > 280 && age < 360 ? -d.dir * 0.12 * Math.sin((age - 280) / 80 * Math.PI) : 0);
    if (age < 580) putSpr(d.c, X + d.dir * 0.2 * CS * tp, Y, 1, 1, 1, rot, ay);
    if (age >= 580 && !d.shattered) {
      d.shattered = true;
      shardsOf(d.c, 6).forEach((s, i) => spray(d.x + d.dir * 0.35, d.y + 0.15, 1, { img: s.c, shape: IMG, dir: -Math.PI / 2 + (i - 2.5) * 0.5, sp: 1.6, vz: 2, g: 9, life: 600, spin: 8 }));
      dust(d.x + d.dir * 0.3, d.y + 0.2, 5, { sp: 0.8, life: 600 });
    }
  } else if (d.corpse === 'b') {
    if (age < 80) { putSpr(d.c, X, Y); putSpr(whiteOf(d.c), X, Y, 0.85); return; }
    const p = easeOut((age - 80) / 440);
    putSpr(d.c, X, Y, 1 - p * 0.7, 1 + 0.1 * p, 1 - 0.7 * p, 0, ay);
  } else if (d.corpse === 'crown') {
    const t = age / 1000, h = Math.max(0, 2.6 * t - 4.5 * t * t), bounce = t > 0.58 ? Math.abs(Math.sin((t - 0.58) * 9)) * 0.12 * Math.max(0, 1 - (t - 0.58) * 2) : 0;
    putSpr(sprIcon('kral', PAL.giltHi, 0.8), X + d.dir * Math.min(t, 0.6) * 0.5 * CS, Y - (h + bounce) * CS - CS * 0.25, age > 1100 ? 1 - (age - 1100) / 300 : 1, 0.55, 0.55, d.dir * t * 3);
  } else if (d.corpse === 'crate') {
    const p = age / d.life;
    putSpr(sprCrate(d.rar, true), X, Y, 1 - p, 1, 1, 0, ay);
    ctx.save(); ctx.translate(X + p * CS * 0.6, Y - CS * 0.3 - Math.sin(p * Math.PI) * CS * 0.6); ctx.rotate(p * 4);
    ctx.globalAlpha = 1 - p; ctx.fillStyle = PAL.wood; ctx.fillRect(-CS * 0.2, -CS * 0.05, CS * 0.4, CS * 0.1); ctx.strokeStyle = INK; ctx.lineWidth = 1.5; ctx.strokeRect(-CS * 0.2, -CS * 0.05, CS * 0.4, CS * 0.1);
    ctx.restore(); ctx.globalAlpha = 1;
  }
}

/* ---------------- overlays: hp bars, status flags, King marks ---------------- */
const BAR = { b: [0.8, 0.7], u: [0.62, 0.5], k: [0.78, 0.7], z: [0.55, 0.45], obr: [0.85, 0.7], alfa: [1.0, 0.9] };
function overlay(e, now) {
  const cat = catOf(e), b = cat === 'b', [top, bw] = BAR[e.kind] || BAR[cat];
  const X = b ? px(e.cx) : px(e.dx), Y = (b ? py(e.cy) : py(e.dy)) - (e.lift || 0), r = CS * (b ? 0.4 : 0.3);
  if (since(e.emergeT) < 400 || since(e.spawnT) < 150) return;
  flagFx(e, X, Y, r, now);
  if (cat === 'k') kingMarks(e, X, Y, now);
  lifeBar(X, Y - top * CS, e.hp, e.maxhp, bw * CS);
}
function lifeBar(X, top, hp, max, w) {
  if (hp >= max) return;
  const f = Math.max(0, hp / max), h = Math.max(3, Math.round(CS * 0.06)), x0 = Math.round(X - w / 2);
  ctx.fillStyle = INK; ctx.fillRect(x0 - 1, top - 1, w + 2, h + 2);
  ctx.fillStyle = f > 0.5 ? PAL.hpOk : f > 0.25 ? PAL.hpMid : PAL.hpLow; ctx.fillRect(x0, top, w * f, h);
  ctx.fillStyle = 'rgba(11,8,6,0.6)';
  if (f <= 0.25) for (let x = 2; x < w * f; x += 4) ctx.fillRect(x0 + x, top, 1.5, h);
  for (const q of [0.25, 0.5, 0.75]) ctx.fillRect(x0 + Math.round(w * q), top, 1, h);
}
function flagFx(e, X, Y, r, now) {
  const f = e.flags;
  ctx.globalCompositeOperation = 'lighter';
  if (f & 8) glow(X, Y, r * 1.8, PAL.giltHi, 0.22);
  if (f & 2) for (const i of [0, 1]) flameAt(X + (i - 0.5) * r * 0.8 + Math.sin(now / 130 + i) * 2, Y - r * 0.4 - i * r * 0.2, CS * 0.05, now, e.id + i * 7);
  if (f & 32) for (let i = 0; i < 3; i++) { const a = now / 250 + i * TAU / 3; glow(X + Math.cos(a) * r * 0.7, Y - r * 1.2 + Math.sin(a) * r * 0.25, CS * 0.08, PAL.amethyst, 1); }
  ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  if (f & 4) {
    cornerMarks(X, Y, r * 2.7, PAL.rubric, 0.9);
    ctx.beginPath(); ctx.ellipse(X, Y - r * 1.55, r * 0.28, r * 0.15, 0, 0, TAU); ctx.fillStyle = INK; ctx.fill(); ctx.strokeStyle = PAL.rubric; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.beginPath(); ctx.arc(X, Y - r * 1.55, r * 0.08, 0, TAU); ctx.fillStyle = PAL.rubric; ctx.fill();
  }
  if (f & 16 && e.kind === 'exo') ring(X, Y - r * 0.2, r + 6, '#e9f2ff', 1.5, 0.85, [5, 4], -now / 60, 1.5);   // Exo shield: a dashed bubble
  else if (f & 16) {
    ring(X, Y, r + 5, PAL.giltHi, 1.5, 0.8, null, 0, 1.5);
    for (let i = 0; i < 6; i++) { const a = i / 6 * TAU + now / 2000; seg(X + Math.cos(a) * (r + 2), Y + Math.sin(a) * (r + 2), X + Math.cos(a) * (r + 8), Y + Math.sin(a) * (r + 8), PAL.giltHi, 1.5, 0.8); }
  }
  if (f & 64) {
    ctx.setLineDash([3, 3]); ctx.strokeStyle = '#8f86a8'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.ellipse(X, Y + GROUND * CS, r * 0.95, r * 0.32, 0, 0.1, Math.PI - 0.1); ctx.stroke(); ctx.setLineDash([]);
  }
}
function kingMarks(e, X, Y, now) {
  const m = S.snap, mine = e.side === S.side;
  if (e.flags & 256) {
    const perfect = mine && m.kr && m.kr.blk === 2, a = (e.face || 1) > 0 ? 0 : Math.PI, r = CS * 0.48;
    ctx.beginPath(); ctx.arc(X, Y, r, a - 1.1, a + 1.1);
    ctx.strokeStyle = INK; ctx.lineWidth = perfect ? 8 : 6; ctx.stroke();
    ctx.strokeStyle = perfect ? '#ffffff' : PAL.giltHi; ctx.lineWidth = perfect ? 4.5 : 2.5; ctx.stroke();
    for (const k of [-0.6, 0, 0.6]) seg(X + Math.cos(a + k) * (r - 4), Y + Math.sin(a + k) * (r - 4), X + Math.cos(a + k) * (r + 4), Y + Math.sin(a + k) * (r + 4), perfect ? '#ffffff' : PAL.gilt, 2);
  }
  const tl = performance.now() - FXS.tele;
  if (mine && tl < 520) {
    const p = clamp01(tl / 450), r = CS * (1.2 - 0.85 * p), band = tl > 150;
    ring(X, Y, r, band ? PAL.flame : PAL.rubric, band ? 3.5 : 2, band ? 1 : 0.7, band ? null : [5, 4], -now / 30, 2.5);
  }
}

/* ---------------- fx (shots, blasts, bursts) ---------------- */
function drawFx(now) {
  const vt = FXS.vt;
  S.fx = S.fx.filter(f => vt - f.t0 < f.life);
  S.lasers = S.lasers.filter(l => now - l.t0 < 500);
  FXS.words = 0;
  for (const l of S.lasers) {
    const t = S.ents.get(l.id), X = px(l.x), Y = py(l.y) - 0.18 * CS, p = (now - l.t0) / 500;
    const tx = t ? px(t.dx) : px(l.tx), ty = t ? py(t.dy) - (t.lift || 0) : py(l.ty);
    seg(X, Y, tx, ty, INK, 3, 0.8);
    ctx.setLineDash([6, 4]); ctx.lineDashOffset = -now / 25; seg(X, Y, tx, ty, PAL.rubric, 1.5); ctx.setLineDash([]);
    const r = CS * (0.42 - 0.14 * p);
    for (const [col, w] of [[INK, 4], [PAL.rubric, 2]]) {
      ring(tx, ty, r, col, w);
      for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; seg(tx + Math.cos(a) * r * 0.55, ty + Math.sin(a) * r * 0.55, tx + Math.cos(a) * r * 1.35, ty + Math.sin(a) * r * 1.35, col, w); }
    }
  }
  for (const f of S.fx) {
    const age = vt - f.t0;
    if (age < 0) continue;
    const p = age / f.life, X1 = px(f.a), Y1 = py(f.b);
    ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 1;
    switch (f.type) {
      case 'k': case 'q': case 't': {
        const T = f.type === 'k' ? 110 : f.type === 'q' ? 90 : 100;
        if (age > T) break;
        const X2 = px(f.c), Y2 = py(f.d), h = age / T, ang = Math.atan2(Y2 - Y1, X2 - X1), len = Math.hypot(X2 - X1, Y2 - Y1);
        const hx = X1 + (X2 - X1) * h, hy = Y1 + (Y2 - Y1) * h, tl = Math.min(len * h, CS * 0.9), tx = hx - Math.cos(ang) * tl, ty = hy - Math.sin(ang) * tl;
        const tm = TEAM[f.side] || TEAM[0];
        if (f.type === 'k') {
          seg(tx, ty, hx, hy, 'rgba(255,220,160,0.6)', 2);
          ctx.globalCompositeOperation = 'source-over';
          ctx.save(); ctx.translate(hx, hy); ctx.rotate(ang);
          ctx.fillStyle = '#3a2a1a'; ctx.fillRect(-0.22 * CS, -0.025 * CS, 0.22 * CS, 0.05 * CS);
          ctx.fillStyle = '#e6e2d8'; ctx.beginPath(); ctx.moveTo(0, -0.055 * CS); ctx.lineTo(0.11 * CS, 0); ctx.lineTo(0, 0.055 * CS); ctx.fill();
          ctx.restore();
        } else {
          seg(tx, ty, hx, hy, tm.c, f.type === 't' ? 4 : 2.5, 0.8);
          glow(hx, hy, CS * (f.type === 't' ? 0.22 : 0.16), tm.hi, 1);
        }
        break;
      }
      case 's': {
        const X2 = px(f.c), Y2 = py(f.d), ang = Math.atan2(Y2 - Y1, X2 - X1), nx = -Math.sin(ang), ny = Math.cos(ang);
        if (age < 60) seg(X1, Y1, X2, Y2, PAL.flame, 4 * (1 - age / 60) + 1);
        const dr = p * 0.18 * CS;
        seg(X1 + nx * dr, Y1 + ny * dr, X2 + nx * dr, Y2 + ny * dr, PAL.flame, 1, 0.6 * (1 - p));
        break;
      }
      case 'z': {
        const X2 = px(f.c), Y2 = py(f.d), seed = Math.floor(age / 60) + f.seed, pts = [[X1, Y1]];
        for (let i = 1; i < 7; i++) pts.push([X1 + (X2 - X1) * i / 7 + (hash(i, seed, 1) - 0.5) * CS * 0.32, Y1 + (Y2 - Y1) * i / 7 + (hash(i, seed, 2) - 0.5) * CS * 0.32]);
        pts.push([X2, Y2]);
        ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
        for (const i of [2, 5]) { if (hash(i, seed, 3) < 0.5) continue; const [x, y] = pts[i], a = hash(i, seed, 4) * TAU; ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * CS * 0.2, y + Math.sin(a) * CS * 0.2); ctx.lineTo(x + Math.cos(a + 0.6) * CS * 0.35, y + Math.sin(a + 0.6) * CS * 0.35); }
        ctx.globalAlpha = 1 - p; ctx.lineJoin = 'round';
        ctx.strokeStyle = 'rgba(123,95,208,0.6)'; ctx.lineWidth = 7; ctx.stroke();
        ctx.strokeStyle = '#f2ecff'; ctx.lineWidth = 1.8; ctx.stroke();
        break;
      }
      case 'f': glow(X1, Y1, f.c * CS * (0.6 + p * 0.4), '#ff9a3c', 0.3 * (1 - p)); break;
      case 'm': {
        const X2 = px(f.c), Y2 = py(f.d), ang = Math.atan2(Y2 - Y1, X2 - X1), a = 1 - p;
        ctx.globalCompositeOperation = 'source-over';
        if (f.side === 2) {
          const nx = -Math.sin(ang), ny = Math.cos(ang), l = CS * 0.2 * Math.min(1, age / 80);
          for (const k of [-1, 0, 1]) {
            const cx = X2 + nx * k * CS * 0.08, cy = Y2 + ny * k * CS * 0.08, dx = Math.cos(ang + 0.8) * l, dy = Math.sin(ang + 0.8) * l;
            seg(cx - dx, cy - dy, cx + dx, cy + dy, INK, 3.5, a); seg(cx - dx, cy - dy, cx + dx, cy + dy, PAL.fleshL, 1.6, a);
          }
        } else {
          const r = CS * 0.32, a0 = ang - Math.PI * 0.75, sweep = Math.PI / 2 * Math.min(1, age / 90);
          ctx.globalAlpha = a; ctx.beginPath(); ctx.arc(X2 - Math.cos(ang) * r * 0.6, Y2 - Math.sin(ang) * r * 0.6, r, a0 + Math.PI / 2, a0 + Math.PI / 2 + sweep);
          ctx.strokeStyle = INK; ctx.lineWidth = 5; ctx.stroke(); ctx.strokeStyle = (TEAM[f.side] || TEAM[0]).hi; ctx.lineWidth = 2.5; ctx.stroke();
        }
        break;
      }
      case 'b': {
        const r = f.c * CS, R = r * (0.35 + 0.65 * easeOut(p));
        glow(X1, Y1, R * 1.15, '#ff9a3c', (1 - p) * 0.9);
        glow(X1, Y1, R * 0.6, PAL.flame, (1 - p) ** 2);
        ctx.globalCompositeOperation = 'source-over';
        ring(X1, Y1, r * 1.05 * easeOut(clamp01(p * 1.6)), 'rgba(255,220,170,0.6)', 2, 1 - p);
        break;
      }
      case 'p': {
        const k = f.side === S.side ? 1 : 0.5, sp = clamp01(age / 350);
        ring(X1, Y1, CS * (0.3 + p * 0.5) * k, PAL.giltHi, 2.5 * k, 1 - p);
        for (let i = 0; i < 8; i++) { const a = i / 8 * TAU, r0 = CS * (0.25 + 0.3 * sp) * k; seg(X1 + Math.cos(a) * r0, Y1 + Math.sin(a) * r0, X1 + Math.cos(a) * (r0 + CS * 0.25 * k), Y1 + Math.sin(a) * (r0 + CS * 0.25 * k), '#ffffff', 2 * k, 1 - sp); }
        if (sp < 1) { ring(X1, Y1, CS * 1.4 * k * easeOut(sp), '#ffffff', 3 * k, 1 - sp); ring(X1, Y1, CS * 1.55 * k * easeOut(sp), COL[f.side] || PAL.gilt, 3 * k, 1 - sp); }
        if (f.c >= 0) {
          const X2 = px(f.c), Y2 = py(f.d) - 0.18 * CS, h = clamp01(age / 120), hx = X1 + (X2 - X1) * h, hy = Y1 + (Y2 - Y1) * h;
          seg(X1, Y1, hx, hy, PAL.giltHi, 4 * k, 1 - p);
          glow(hx, hy, CS * 0.25 * k, PAL.flame, 1 - p);
        }
        ctx.globalCompositeOperation = 'source-over';
        ink('ODRAŽENO!', X1, Y1 - CS * (0.85 + 0.3 * easeOut(clamp01(age / 900))), CS * 0.45 * k, PAL.giltHi, age > 650 ? 1 - (age - 650) / 300 : 1, 1 + 0.35 * clamp01(1 - age / 90));
        break;
      }
      case 'g':
        ctx.globalCompositeOperation = 'source-over';
        ring(X1, Y1, CS * 0.45, PAL.muted, 3, 1 - p, null, 0, 2);
        ink('BLOK', X1, Y1 - CS * (0.75 + 0.25 * p), CS * 0.26, PAL.muted, 1 - p);
        break;
      case 'h':
        ctx.globalCompositeOperation = 'source-over';
        ink('+', X1, Y1 - CS * (0.3 + 0.6 * p), CS * 0.42, PAL.giltHi, 1 - p);
        break;
      case 'c': {
        const pulse = 0.5 + 0.5 * Math.sin(age / 1000 * TAU * (2 + p * 6)), s = CS * 0.12;
        ctx.globalCompositeOperation = 'source-over';
        ring(X1, Y1, CS * (0.36 + 0.06 * pulse), PAL.rubric, 2, 0.5 + 0.5 * pulse, [5, 4], now / 40, 2);
        ctx.beginPath(); ctx.arc(X1, Y1 + s * 0.3, s, 0, TAU); ctx.fillStyle = '#1a1412'; ctx.fill(); ctx.strokeStyle = PAL.ironL; ctx.lineWidth = 1.2; ctx.stroke();
        seg(X1 + s * 0.5, Y1 - s * 0.5, X1 + s, Y1 - s * 1.2, PAL.wood, 2);
        ctx.globalCompositeOperation = 'lighter';
        glow(X1 + s, Y1 - s * 1.25, CS * (0.08 + Math.random() * 0.06), PAL.candle, 1);
        break;
      }
      case 'o': if (f.c >= 3) { ctx.globalAlpha = 1 - p; ctx.drawImage(glowOf(RAR_COL[f.c]), X1 - CS * 0.5, Y1 - CS * 4, CS, CS * 4.4); } break;
      case 'v': {
        ring(X1, Y1, CS * (0.2 + 0.6 * p), PAL.gilt, 2.5, 1 - p);
        ctx.globalCompositeOperation = 'source-over';
        const ly = Y1 - CS * (0.55 + 0.5 * p), a = p < 0.7 ? 1 : 1 - (p - 0.7) / 0.3;
        for (const s of [-1, 1]) {
          ctx.globalAlpha = a; ctx.beginPath(); ctx.arc(X1, ly, CS * 0.18, Math.PI / 2 + s * 0.3, Math.PI / 2 + s * 2.2, s < 0);
          ctx.strokeStyle = INK; ctx.lineWidth = 4; ctx.stroke(); ctx.strokeStyle = PAL.giltHi; ctx.lineWidth = 2; ctx.stroke();
          for (let i = 1; i <= 3; i++) { const an = Math.PI / 2 + s * (0.3 + i * 0.55); ctx.beginPath(); ctx.ellipse(X1 + Math.cos(an) * CS * 0.2, ly + Math.sin(an) * CS * 0.2, CS * 0.045, CS * 0.02, an, 0, TAU); ctx.fillStyle = PAL.giltHi; ctx.fill(); }
        }
        break;
      }
      case 'u': {
        const col = (TEAM[f.side] || TEAM[0]).hi;
        ring(X1, Y1, CS * 0.7 * easeOut(clamp01(age / 300)), PAL.giltHi, 2, 1 - clamp01(age / 300));
        ctx.globalCompositeOperation = 'source-over';
        const rp = clamp01(age / 500), ca = age < 500 ? 1 : 0;
        for (let i = 0; i < 3; i++) {
          const yy = Y1 - CS * (0.1 + 0.6 * easeOut(rp) + i * 0.13), w = CS * 0.16;
          for (const [c, lw] of [[INK, 4.5], [col, 2.5]]) { ctx.globalAlpha = ca * (1 - rp * 0.6); ctx.strokeStyle = c; ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(X1 - w, yy + w * 0.5); ctx.lineTo(X1, yy); ctx.lineTo(X1 + w, yy + w * 0.5); ctx.stroke(); }
        }
        ctx.globalAlpha = 1;
        ink(`ÚROVEŇ ${f.c}${f.f[6] ? ' · ' + f.f[6] : ''}`, X1, Y1 - CS * 1.05, CS * 0.3, PAL.giltHi, p > 0.75 ? (1 - p) / 0.25 : 1, 1 + 0.3 * clamp01(1 - age / 100));
        break;
      }
      case 'r': ring(X1, Y1, CS * 0.7 * (1 - easeOut(p)), PAL.giltHi, 2, 1 - p, [4, 4]); break;
      case 'D': {
        const X2 = px(f.c), Y2 = py(f.d), c = sprKing(f.side, X2 >= X1 ? 1 : -1);
        seg(X1, Y1, X2, Y2, COL[f.side], CS * 0.22, 0.35 * (1 - p));
        ctx.globalCompositeOperation = 'source-over';
        for (let i = 1; i <= 4; i++) putSpr(c, X1 + (X2 - X1) * i / 5, Y1 + (Y2 - Y1) * i / 5, 0.32 * (1 - p) * i / 4);
        break;
      }
      case 'U': {
        const e = easeOut(clamp01(age / 400));
        glow(X1, Y1, CS * 1.4, COL[f.side], 0.6 * (1 - p));
        ctx.globalCompositeOperation = 'source-over';
        ring(X1, Y1, CS * 3 * e, TEAM[f.side].hi, 4 * (1 - p) + 1, 1 - p, null, 0, 2);
        break;
      }
      case 'P': {
        ring(X1, Y1, CS * (0.3 + 0.9 * easeOut(p)), PAL.giltHi, 3, 1 - p);
        glow(X1, Y1, CS * 0.9, PAL.gilt, 0.6 * (1 - p));
        ctx.globalCompositeOperation = 'source-over';
        const s = age < 160 ? 0.5 + 0.7 * age / 160 : Math.max(1, 1.2 - (age - 160) / 400);
        putSpr(sprIcon('kral', PAL.giltHi, 0.8), X1, Y1 - CS * (0.6 + 0.6 * easeOut(clamp01(age / 600))), p > 0.75 ? (1 - p) / 0.25 : 1, s * 0.7, s * 0.7);
        break;
      }
      case 'R': {
        const e = easeOut(clamp01(p * 1.5));
        ctx.globalAlpha = 0.8 * (1 - p); ctx.drawImage(glowOf(COL[f.side]), X1 - CS * 0.8, Y1 - CS * 5, CS * 1.6, CS * 6);
        ctx.globalCompositeOperation = 'source-over';
        ring(X1, Y1, CS * 2 * e, TEAM[f.side].hi, 3, 1 - p, null, 0, 2);
        break;
      }
      case 'L':
        if (age < 350) { ctx.globalCompositeOperation = 'source-over'; ring(X1, Y1 + CS * 0.2, CS * 1.3 * easeOut(age / 350), 'rgba(220,200,160,0.7)', 3, 1 - age / 350); ctx.globalCompositeOperation = 'lighter'; }
        if (f.c >= 3) { ctx.globalAlpha = 0.9 * (1 - p); ctx.drawImage(glowOf(RAR_COL[f.c]), X1 - CS * 0.6, Y1 - CS * 5, CS * 1.2, CS * 5.4); }
        break;
      case 'K': glow(X1, Y1, CS * 1.2, PAL.gilt, 1 - p); ring(X1, Y1, CS * 1.4 * easeOut(p), PAL.giltHi, 3, 1 - p); break;
      case 'H': {   // hangar: a small bat dart along the shot line
        const X2 = px(f.c), Y2 = py(f.d), h = clamp01(age / 200), ang = Math.atan2(Y2 - Y1, X2 - X1), hx = X1 + (X2 - X1) * h, hy = Y1 + (Y2 - Y1) * h;
        if (h < 1) {
          seg(X1 + (hx - X1) * 0.6, Y1 + (hy - Y1) * 0.6, hx, hy, 'rgba(233,242,255,0.5)', 1.5);
          glow(hx, hy, CS * 0.3, '#e9f2ff', 0.7);
          ctx.globalCompositeOperation = 'source-over';
          putSpr(sprDrone(f.side, Math.floor(age / 50) % 2), hx, hy, 1, 0.45, 0.45, ang + Math.PI / 2);
        } else glow(X2, Y2, CS * 0.2, '#e9f2ff', 1 - (age - 200) / 60);
        break;
      }
      case 'E': {   // EMP: a 3x3 square outline flash, a white-violet ring and spark glyphs
        const h = f.c * CS, e = easeOut(clamp01(age / 300));
        glow(X1, Y1, CS * 1.6, PAL.ghostD, 0.5 * (1 - p));
        ctx.globalCompositeOperation = 'source-over';
        ctx.globalAlpha = 1 - p; ctx.strokeStyle = INK; ctx.lineWidth = 5; ctx.strokeRect(X1 - h, Y1 - h, h * 2, h * 2);
        ctx.strokeStyle = '#e9f2ff'; ctx.lineWidth = 2.5; ctx.strokeRect(X1 - h, Y1 - h, h * 2, h * 2); ctx.globalAlpha = 1;
        ring(X1, Y1, CS * 1.7 * e, PAL.ghost, 3, 1 - p, null, 0, 2);
        ring(X1, Y1, CS * 1.45 * e, '#ffffff', 1.5, 1 - p);
        if (p < 0.7) for (let i = 0; i < 6; i++) {
          const a = i / 6 * TAU + f.seed, rr = h * (0.4 + 0.5 * hash(i, f.seed, 1)), x = X1 + Math.cos(a) * rr, y = Y1 + Math.sin(a) * rr, s = CS * 0.09;
          ctx.beginPath(); ctx.moveTo(x - s, y - s); ctx.lineTo(x + s * 0.2, y - s * 0.1); ctx.lineTo(x - s * 0.2, y + s * 0.1); ctx.lineTo(x + s, y + s);
          ctx.globalAlpha = 1 - p / 0.7; ctx.strokeStyle = INK; ctx.lineWidth = 3.5; ctx.stroke(); ctx.strokeStyle = '#e9f2ff'; ctx.lineWidth = 1.5; ctx.stroke(); ctx.globalAlpha = 1;
        }
        break;
      }
      case 'M': {   // Mor cast: a grey-green swell (the cloud itself comes from snapshot mc)
        glow(X1, Y1, CS * (0.8 + 1.2 * easeOut(p)), '#6c7a5a', 0.5 * (1 - p));
        ctx.globalCompositeOperation = 'source-over';
        ring(X1, Y1, CS * 1.5 * easeOut(clamp01(age / 400)), '#a8b896', 2, 1 - p, [3, 4]);
        break;
      }
      case 'Z': {   // raise: a hand rises from the ground, then the zombie
        ctx.globalCompositeOperation = 'source-over';
        const up = age < 350 ? easeOut(age / 350) : age < 500 ? 1 : Math.max(0, 1 - (age - 500) / 200), gy = Y1 + CS * 0.28, hh = CS * 0.36 * up;
        ctx.save(); ctx.beginPath(); ctx.rect(X1 - CS * 0.5, gy - CS, CS, CS); ctx.clip();
        ctx.translate(X1, gy - hh); ctx.rotate(Math.sin(age / 90) * 0.12);
        ctx.fillStyle = PAL.flesh; ctx.strokeStyle = PAL.zInk; ctx.lineWidth = 1.5;
        ctx.fillRect(-CS * 0.04, 0, CS * 0.08, hh + 2); ctx.strokeRect(-CS * 0.04, 0, CS * 0.08, hh + 2);
        ctx.beginPath(); for (const a of [-0.6, -0.2, 0.2, 0.6]) { ctx.moveTo(Math.sin(a) * CS * 0.03, 0); ctx.lineTo(Math.sin(a) * CS * 0.1, -CS * 0.1); }
        ctx.lineWidth = 4; ctx.strokeStyle = PAL.zInk; ctx.stroke(); ctx.lineWidth = 2; ctx.strokeStyle = PAL.flesh; ctx.stroke();
        ctx.restore();
        ctx.globalAlpha = 1 - p; ctx.fillStyle = '#2a221b'; ctx.beginPath(); ctx.ellipse(X1, gy, CS * 0.2, CS * 0.06, 0, 0, TAU); ctx.fill(); ctx.globalAlpha = 1;
        break;
      }
      case 'W': ctx.globalCompositeOperation = 'source-over'; ring(X1, Y1, CS * (0.3 + 0.35 * easeOut(p)), (TEAM[f.side] || TEAM[0]).hi, 2.5, 1 - p, null, 0, 2); break;
      case 'w': {
        FXS.words++;
        ctx.globalCompositeOperation = 'source-over';
        putSpr(txtSpr('PRÁSK!', Math.round(CS * 0.5), PAL.giltHi), X1, Math.max(OY + CS * 0.4, Y1 - CS * (0.9 + 0.2 * p)), p > 0.7 ? (1 - p) / 0.3 : 1, 1 + 0.6 * clamp01(1 - age / 120), 1 + 0.6 * clamp01(1 - age / 120), f.rot);
        break;
      }
    }
  }
  ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
}
const NUM_OPT = { body: true };
function showNums() {
  const vt = FXS.vt;
  FXS.nums = FXS.nums.filter(n => vt - n.t0 < 900);
  for (const n of FXS.nums) {
    if (n.kind === 'h' && n.val < 3) continue;
    const age = vt - n.t0, rise = 0.55 * easeOut(Math.min(1, age / 750)), pop = 1 + 0.35 * clamp01(1 - (vt - n.pop) / 90);
    const big = n.val >= 50, size = CS * (n.th ? 0.42 : n.kind === 't' ? 0.24 : big ? 0.4 : 0.3);
    const text = n.kind === 'h' ? '+' + n.val : n.kind === 'b' ? 'BLOK −' + n.val : big ? n.val + '!' : String(n.val);
    ink(text, px(n.x) + n.jx * CS, py(n.y) - CS * (0.5 + rise), size, n.col, (age > 600 ? 1 - (age - 600) / 300 : 1) * (n.kind === 't' ? 0.75 : 1), pop, NUM_OPT);
  }
}

/* ---------------- markers above the fog ---------------- */
function crateDrop(r, now) {
  const [, x, y, rar] = r.c, col = RAR_COL[rar] || PAL.gilt, X = px(x), Y = py(y), left = Math.max(0, (r.land - FXS.vt) / 1000);
  ctx.globalCompositeOperation = 'lighter';
  const gr = ctx.createLinearGradient(0, OY, 0, Y);
  gr.addColorStop(0, rgba(col, 0)); gr.addColorStop(1, rgba(col, 0.28));
  ctx.fillStyle = gr; ctx.beginPath(); ctx.moveTo(X - CS * 0.1, OY); ctx.lineTo(X + CS * 0.1, OY); ctx.lineTo(X + CS * 0.35, Y); ctx.lineTo(X - CS * 0.35, Y); ctx.fill();
  ctx.globalCompositeOperation = 'source-over';
  if (Math.random() < FXS.dt * 8) spray(x + (Math.random() - 0.5) * 0.3, y - 1 - Math.random() * 3, 1, { col, vy: 0.8, sp: 0.05, life: 1200, size: 0.04, light: true, drag: 1 });
  ctx.setLineDash([4, 4]); ctx.strokeStyle = col; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(X, Y + CS * 0.2, CS * 0.36, CS * 0.13, 0, 0, TAU); ctx.stroke(); ctx.setLineDash([]);
  if (left < 1.2) {
    const p = 1 - left / 1.2, cy = OY - CS + (Y - OY + CS) * p * p;
    floorShadow(X, Y + CS * 0.25, CS * (0.2 + 0.4 * p), 0.2 + 0.35 * p);
    putSpr(sprCrate(rar), X, cy);
  } else ink(String(Math.ceil(left)), X, Y - CS * 0.55, CS * 0.4, col);
}
function showStrike(st, now) {
  const [x, y, t, side] = st, X = px(x), Y = py(y), s = 3 * CS, hz = 2 + 8 * (1 - clamp01(t / 1.5)), pulse = 0.5 + 0.5 * Math.sin(now / 1000 * TAU * hz);
  ctx.fillStyle = `rgba(194,59,46,${0.1 + 0.1 * pulse})`; ctx.fillRect(X - s / 2, Y - s / 2, s, s);
  hazard(X - s / 2, Y - s / 2, s, s, PAL.rubric, 0.25, now, 14);
  ctx.lineWidth = 4; ctx.strokeStyle = INK; ctx.strokeRect(X - s / 2, Y - s / 2, s, s);
  ctx.lineWidth = 2; ctx.strokeStyle = PAL.rubric; ctx.setLineDash([8, 5]); ctx.lineDashOffset = -now / 30; ctx.strokeRect(X - s / 2, Y - s / 2, s, s); ctx.setLineDash([]);
  ctx.beginPath(); ctx.arc(X, Y, CS * 0.55, 0, TAU); ctx.moveTo(X - CS * 0.8, Y); ctx.lineTo(X + CS * 0.8, Y); ctx.moveTo(X, Y - CS * 0.8); ctx.lineTo(X, Y + CS * 0.8); ctx.stroke();
  ink(t.toFixed(1).replace('.', ','), X, Y - CS * 1.05, CS * 0.36, '#ff9a8a');
  if (t < 0.5) {
    const p = 1 - t / 0.5, hx = X + CS * 0.8 * (1 - p), hy = OY + (Y - OY) * p;
    ctx.globalCompositeOperation = 'lighter';
    seg(X + CS * 0.8, OY, hx, hy, '#ff9a3c', 3, 0.6); glow(hx, hy, CS * 0.3, PAL.flame, 1);
    ctx.globalCompositeOperation = 'source-over';
  }
  const key = x + ',' + y + ',' + side;
  if (t <= 0.4 && !FXS.planes.has(key)) FXS.planes.set(key, FXS.vt);
  const pt = since(FXS.planes.get(key));
  if (pt < 600) {
    const PX = OX + (S.W + 2) * CS * (pt / 600) * 1.2 - CS, w = CS * 1.6;
    ctx.globalAlpha = 0.35; ctx.fillStyle = '#000';
    ctx.beginPath(); ctx.ellipse(PX, Y, w * 0.5, w * 0.08, 0, 0, TAU); ctx.fill();
    ctx.beginPath(); ctx.moveTo(PX + w * 0.05, Y); ctx.lineTo(PX - w * 0.15, Y - w * 0.5); ctx.lineTo(PX - w * 0.3, Y - w * 0.5); ctx.lineTo(PX - w * 0.15, Y); ctx.lineTo(PX - w * 0.3, Y + w * 0.5); ctx.lineTo(PX - w * 0.15, Y + w * 0.5); ctx.closePath(); ctx.fill();
    ctx.globalAlpha = 1;
  }
}
function showLure(lu, now) {
  const X = px(lu[0]), Y = py(lu[1]);
  for (let i = 0; i < 3; i++) {
    const p = ((now / 1600) + i / 3) % 1, a = i * TAU / 3 + p * 4, r = CS * (1.1 - p);
    ctx.globalAlpha = 0.25 * Math.sin(p * Math.PI); ctx.drawImage(glowOf(PAL.mist), X + Math.cos(a) * r - CS * 0.3, Y + Math.sin(a) * r - CS * 0.3, CS * 0.6, CS * 0.6);
  }
  ring(X, Y, CS * (0.45 + 0.08 * Math.sin(now / 200)), PAL.bronze, 2, 0.8, [4, 5], now / 40, 2);
  putSpr(sprIcon('navnada', PAL.bronze, 0.8), X, Y);
}
function showSelection(now) {
  const se = S.sel && S.ents.get(S.sel);
  if (!se) return;
  const X = px(se.cx), Y = py(se.cy), pulse = 0.5 + 0.5 * Math.sin(now / 180);
  cornerMarks(X, Y, CS * (0.98 + pulse * 0.05), PAL.giltHi);
  const d = S.defs[se.kind];
  let r = d.range ? d.range + (se.lvl - 1) * 0.2 : 0;
  if (se.kind === 'plamen' && se.path === 'B') r = 2.6;
  if (S.snap.tech.includes('ing3') && r) r += 0.6;
  if (r && d.cat === 'b' && ter(se.cx, se.cy) === '^') r += 1;   // raised ground: +1 range
  if (r) ring(X, Y, r * CS, PAL.giltHi, 1.5, 0.6, [2, 5], -now / 60);
}
function showPreview(now) {
  const c = S.hover;
  if (!c) return;
  const X = px(c.x), Y = py(c.y), p = S.pick;
  let ok = true;
  if (p && p.kind === 'place') {
    ok = canPlace(p.id, c.x, c.y) && (afford(costOf(p.id)) || freeOf(p.id));
    if (ok) {
      putSpr(S.defs[p.id].cat === 'b' ? sprBuilding(p.id, S.side, 1, '') : sprUnit(p.id, S.side, false, 1), X, Y, 0.55);
      let r = p.id === 'hlaska' ? 4.5 : p.id === 'rusicka' ? 1.6 : S.defs[p.id].range;
      if (r && S.defs[p.id].cat === 'b' && ter(c.x, c.y) === '^') r += 1;
      if (r) ring(X, Y, r * CS, PAL.giltHi, 1.5, 0.6, [2, 5], -now / 60);
    }
  } else if (p) {
    ok = canTarget(p, c.x, c.y);
    if (ok && (p.id === 'nalet' || p.id === 'odstrel')) {
      const s = 3 * CS, col = p.id === 'nalet' ? PAL.rubric : PAL.giltHi;
      if (p.id === 'nalet') hazard(X - s / 2, Y - s / 2, s, s, col, 0.25, now, 14);
      ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.setLineDash([6, 5]); ctx.lineDashOffset = -now / 30; ctx.strokeRect(X - s / 2, Y - s / 2, s, s); ctx.setLineDash([]);
    }
    if (ok && p.id === 'dron') ring(X, Y, 2.5 * CS, PAL.giltHi, 1.5, 0.8, [6, 5], -now / 40, 2);
    if (ok && p.id === 'karantena') { ctx.fillStyle = 'rgba(138,142,150,0.18)'; for (let x = S.mist[0]; x <= S.mist[1]; x++) ctx.fillRect(px(x) - CS / 2, Y - CS / 2, CS, CS); }
  }
  if (!ok) hazard(X - CS / 2, Y - CS / 2, CS, CS, PAL.rubric, 0.4, 0, 8);
  cornerMarks(X, Y, CS * 0.94, ok ? (p ? PAL.giltHi : rgba(PAL.muted, 0.7)) : PAL.rubric);
}

/* ---------------- ?perf: raster accounting of the main canvas (works with ?demo) ---------------- */
// Wraps drawImage, fillRect, fill and stroke on ctx. Dest area is counted in device pixels, clipped to the canvas for
// axis-aligned transforms; fill(path) counts the area a path carries in .area (the fog cells), stroke counts calls only.
// The HUD shows dest Mpx per frame, overdraw ×, the 'lighter' share, the draw JS ms, RS and Q (averages of 60 frames).
// PERF.bench(n) draws n frames synchronously (for a hidden tab) and returns the same averages.
const PERF = /[?&]perf\b/.test(location.search) ? (() => {
  const P = { on: false, px: 0, lp: 0, calls: 0, t0: 0, hist: [] };
  const dI = ctx.drawImage, fR = ctx.fillRect, fl = ctx.fill, st = ctx.stroke;
  function add(c, x, y, w, h) {
    if (!P.on) return;
    P.calls++;
    const t = c.getTransform();
    let a;
    if (!t.b && !t.c) {
      const x0 = Math.max(0, Math.min(t.a * x, t.a * (x + w)) + t.e), x1 = Math.min(cv.width, Math.max(t.a * x, t.a * (x + w)) + t.e);
      const y0 = Math.max(0, Math.min(t.d * y, t.d * (y + h)) + t.f), y1 = Math.min(cv.height, Math.max(t.d * y, t.d * (y + h)) + t.f);
      a = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
    } else a = Math.abs(w * h * (t.a * t.d - t.b * t.c));
    P.px += a;
    if (c.globalCompositeOperation === 'lighter') P.lp += a;
  }
  ctx.drawImage = function (img, ...a) {
    if (a.length === 2) add(this, a[0], a[1], img.width, img.height);
    else if (a.length === 4) add(this, a[0], a[1], a[2], a[3]);
    else add(this, a[4], a[5], a[6], a[7]);
    return dI.call(this, img, ...a);
  };
  ctx.fillRect = function (x, y, w, h) { add(this, x, y, w, h); return fR.call(this, x, y, w, h); };
  ctx.fill = function (p, ...r) {
    if (P.on) { P.calls++; if (p && p.area) { const t = this.getTransform(); P.px += p.area * Math.abs(t.a * t.d - t.b * t.c); } }
    return fl.call(this, p, ...r);
  };
  ctx.stroke = function (...a) { if (P.on) P.calls++; return st.apply(this, a); };
  P.begin = () => { P.px = P.lp = P.calls = 0; P.on = true; P.t0 = performance.now(); };
  P.end = () => { P.on = false; P.hist.push([P.px, P.lp, performance.now() - P.t0, P.calls]); if (P.hist.length > 60) P.hist.shift(); };
  P.avg = () => {
    const n = P.hist.length || 1, s = [0, 0, 0, 0];
    for (const h of P.hist) for (let i = 0; i < 4; i++) s[i] += h[i];
    const area = cv.width * cv.height;
    return { mpx: +(s[0] / n / 1e6).toFixed(2), over: +(s[0] / n / area).toFixed(2), lighter: +(s[1] / n / 1e6).toFixed(2),
      ms: +(s[2] / n).toFixed(2), calls: Math.round(s[3] / n), rs: +DPR.toFixed(2), q: QUAL.lvl, cw: cv.width, ch: cv.height };
  };
  P.bench = (n = 60) => {
    P.hist.length = 0;
    for (let i = 0; i < n; i++) { FXS.vt += 16; FXS.dt = FXS.rdt = 0.016; stepParts(0.016); P.begin(); draw(performance.now()); P.end(); }
    return P.avg();
  };
  P.hud = () => {
    const a = P.avg(), text = `PERF · ${a.mpx} Mpx · ${a.over}× · lighter ${a.lighter} Mpx · kresba ${a.ms} ms · ${a.calls} volání · RS ${a.rs} · Q${a.q}`;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    ctx.font = '700 14px "Alegreya Sans", Candara, sans-serif'; ctx.textBaseline = 'middle';
    const y = DEMO ? 34 : 6;
    ctx.fillStyle = 'rgba(11,8,6,0.75)'; fR.call(ctx, 6, y, ctx.measureText(text).width + 16, 24);
    ctx.fillStyle = PAL.giltHi; ctx.fillText(text, 14, y + 12.5);
  };
  return P;
})() : null;

/* ---------------- ?demo: showcase scene fed with synthetic snapshots (screenshots, fps check) ---------------- */
// index.html?demo[=noc,strateg,konec,<entity count>] is opt-in only. The page still needs the game server for the card
// definitions; once they arrive the socket is dropped (no lobby slot taken) and a scripted 32 s scene runs through onSnap.
const DEMO = /[?&]demo\b/.test(location.search) ? (() => {
  const arg = (new URLSearchParams(location.search).get('demo') || '').split(',');
  const night = arg.includes('noc'), mode = arg.includes('strateg') ? 'strateg' : 'kral', crowd = +arg.find(a => /^\d+$/.test(a)) || 0;
  const D = { fps: [], hud: null, stats: null, ult: 40, ua: 0 }, L = 32, LANES = [1, 3, 5, 7, 2, 6, 0, 8, 4];
  const BLD = [['gen', 0, 0, 1, ''], ['gen', 0, 8, 3, 'A'], ['hlaska', 1, 2, 3, 'B'], ['sniper', 1, 4, 3, 'A'], ['rusicka', 1, 6, 2, ''],
    ['kulomet', 4, 1, 1, ''], ['kulomet', 4, 7, 3, 'B'], ['plamen', 5, 3, 2, 'A'], ['tesla', 5, 5, 2, ''], ['zed', 5, 0, 1, ''],
    ['zed', 5, 8, 2, ''], ['zed', 2, 8, 3, ''], ['mina', 3, 6, 1, '']];
  const FIRE = { kulomet: ['k', 0.45], sniper: ['s', 2.6], plamen: ['f', 0.35], tesla: ['z', 1.1] };
  // status flags shown on a few units: [side, index, flags] (fast, marked+lit, burning, shield, stun, slow)
  const STAT = [[0, 0, 512], [1, 1, 12], [0, 2, 2], [0, 3, 16], [1, 4, 32], [1, 5, 64]];
  let T = 0, T0 = 0, t0 = 0, id = 1, ents = [], fx = [], ev = [], later = [], cr = [], kdead = 0, ended = false;
  const def = k => S.defs[k] || {}, mir = (s, x) => s === 0 ? x : 15 - x, live = e => ents.includes(e);
  const at = t => { const c = T % L, p = T0 % L; return p < c ? p < t && t <= c : t <= c || p < t; };
  const sm = f => { f = clamp01(f); return f * f * (3 - 2 * f); };
  function add(kind, side, x, y, o = {}) {
    const d = def(kind), lvl = o.lvl || 1, hp = Math.round(d.hps ? d.hps[lvl - 1] : (d.hp || 100) * (d.cat === 'b' ? LVL[lvl - 1] : 1));
    const e = Object.assign({ id: id++, kind, side, x, y, hp, max: hp, lvl, path: '', flags: 0, kills: 0, cat: d.cat || 'z', t: T, cd: Math.random() }, o);
    ents.push(e);
    if (T > 0.1 && e.cat !== 'z' && e.cat !== 'k') fx.push(['n', Math.round(x), Math.round(y), e.cat === 'u' ? 1 : 0, 0, side, kind]);
    return e;
  }
  const lane = (side, i) => LANES[(i + side * 4) % LANES.length];
  const unit = (kind, side, i) => add(kind, side, mir(side, 2), lane(side, i), { i, lane: lane(side, i) });
  const zombie = (kind, i) => add(kind, 2, 6.3 + (i * 1.7) % 2.4, (i * 2.3) % 8.5, { i, hx: 6.3 + (i * 1.7) % 2.4, hy: (i * 2.3) % 8.5 });
  const king = side => add('kral', side, mir(side, 3), 4, { hp: 960, max: 960 });
  function setup() {
    for (const s of [0, 1]) for (const [k, x, y, lvl, path] of BLD) if (S.defs[k] && !(s && k === 'mina')) add(k, s, mir(s, x), y, { lvl, path, flags: k === 'mina' ? 128 : 0, spec: [k, x, y, lvl, path] });
    Object.keys(S.defs).filter(k => S.defs[k].cat === 'u').forEach((k, i) => { unit(k, 0, i).t = -i * 1.3; unit(k, 1, i).t = -i * 1.3 - 0.6; });
    Object.keys(S.defs).filter(k => S.defs[k].cat === 'z').forEach(zombie);
    for (let i = 0; ents.length < crowd; i++) zombie('chodec', 5 + i);
    if (mode === 'kral') { king(0); king(1); }
  }
  function die(e, killer, silent) {
    ents = ents.filter(q => q !== e);
    if (!silent) fx.push(['x', e.x, e.y, 0, 0, e.cat, e.id, e.kind, e.side, killer]);
    if (killer >= 0) {
      const k = ents.find(q => q.side === killer && q.cat === 'u' && Math.hypot(q.x - e.x, q.y - e.y) < 3);
      if (k && ++k.kills === 3) { k.flags |= 1; fx.push(['v', Math.round(k.x), Math.round(k.y), 0, 0, k.side]); }
    }
    const back = e.cat === 'b' ? 3 : e.cat === 'k' ? 4 : 1.5;
    if (e.cat === 'k' && e.side === 0) kdead = T + back;
    later.push([T + back, () => e.cat === 'u' ? unit(e.promo ? 'pesak' : e.kind, e.side, e.i) : e.cat === 'z' ? zombie(e.kind, e.i)
      : e.cat === 'k' ? king(e.side) : add(e.kind, e.side, e.x, e.y, { lvl: e.spec[3], path: e.spec[4], flags: e.flags & 128, spec: e.spec })]);
  }
  function hurt(e, dmg, src) {
    if (!live(e) || dmg <= 0) return;
    e.hp = Math.max(0, e.hp - dmg);
    if (!e.hp) die(e, src && src.side !== 2 ? src.side : -1);
  }
  function foe(e, r) {
    let best = null, bd = r;
    for (const q of ents) {
      if (q.side === e.side || q.flags & 128 || (q.cat === 'b' && (e.side === 2 || e.cat === 'b'))) continue;
      const d = Math.hypot(q.x - e.x, q.y - e.y);
      if (d < bd) { bd = d; best = q; }
    }
    return best;
  }
  function move(e) {
    if (e.cat === 'u') {
      const P = (def(e.kind).step || 1.6) * 0.75, a = Math.max(0, T - e.t), n = Math.floor(a / P), f = sm((a - n * P) / 0.3);
      const hop = e.kind === 'jezdec' ? 2 : 1, zig = e.kind === 'jezdec' || e.kind === 'strelec', up = e.lane < 8 ? 1 : -1;
      const pos = k => [2 + hop * k, e.lane + (zig && k % 2 ? up : 0)], [x0, y0] = pos(n), [x1, y1] = pos(n + 1), gx = x0 + (x1 - x0) * f;
      e.x = mir(e.side, Math.min(13, gx)); e.y = y0 + (y1 - y0) * f;
      if (gx < 13) return;
      if (e.kind === 'pesak') {
        ents = ents.filter(q => q !== e);
        fx.push(['P', Math.round(e.x), Math.round(e.y), 0, 0, e.side]);
        add('dama', e.side, e.x, e.y, { i: e.i, lane: e.lane, t: T - 99, promo: true });
        return;
      }
      if ((e.hit = (e.hit || 0) + 1) % 16 === 0) fx.push(['m', e.x, e.y, e.side ? -0.5 : 15.5, e.y, e.side]);
      if (e.hit > 50) die(e, 1 - e.side);
    } else if (e.cat === 'z') {
      const w = e.kind === 'bezec' ? 0.9 : 0.35;
      e.x = e.hx + 0.9 * Math.sin(T * w + e.i); e.y = Math.max(0, Math.min(8, e.hy + 0.4 * Math.sin(T * w * 0.7 + e.i * 2)));
    } else if (e.cat === 'k') {
      const c = T % L, dash = c >= 2 && c < 4 ? 2.5 * (1 - sm((c - 2) / 2)) : 0;
      if (e.side === 0) { e.x = 3 + Math.cos(T * 0.45) + dash; e.y = 4 + 1.6 * Math.sin(T * 0.6); }
      else { e.x = 12.2 + 0.7 * Math.sin(T * 0.6); e.y = 4 + 2 * Math.sin(T * 0.4); }
    }
  }
  function fight(e, dt) {
    if ((e.cd -= dt) > 0) return;
    const d = def(e.kind), dmg = (d.dmg || 8) * (e.cat === 'b' ? LVL[e.lvl - 1] : 1) * 0.5;
    if (e.cat === 'b') {
      const f = FIRE[e.kind], r = (d.range || 0) + (e.lvl - 1) * 0.2, o = f && foe(e, r);
      if (!o) return;
      e.cd = f[1];
      const near = () => ents.filter(q => q.side !== e.side && q.cat !== 'b' && Math.hypot(q.x - e.x, q.y - e.y) < r);
      if (f[0] === 's') {
        fx.push(['a', e.x, e.y, o.x, o.y, e.side, o.id]);
        later.push([T + 0.5, () => { if (live(o) && live(e)) { fx.push(['s', e.x, e.y, o.x, o.y, e.side]); hurt(o, dmg, e); } }]);
      } else if (f[0] === 'f') { fx.push(['f', e.x, e.y, r, 0, e.side]); near().forEach(q => hurt(q, dmg, e)); }
      else if (f[0] === 'z') { let p = e; for (const q of near().slice(0, 3)) { fx.push(['z', p.x, p.y, q.x, q.y, e.side]); p = q; hurt(q, dmg, e); } }
      else { fx.push(['k', e.x, e.y, o.x, o.y, e.side]); hurt(o, dmg, e); }
    } else if (e.cat === 'k') {
      const o = foe(e, 3.2);
      e.cd = e.side === 0 && D.ua > 0 ? 0.35 : 0.7;
      if (o) { fx.push(['q', e.x, e.y, o.x, o.y, e.side]); hurt(o, 9, e); }
    } else {
      e.cd = d.rate || 1;
      if (e.kind === 'medik') {
        const h = ents.find(q => q.side === e.side && q.cat === 'u' && q.hp < q.max && Math.hypot(q.x - e.x, q.y - e.y) < 1.5);
        if (h) { h.hp = Math.min(h.max, h.hp + 12); fx.push(['h', Math.round(h.x), Math.round(h.y), 0, 0, e.side]); }
      }
      const o = foe(e, 1.25);
      if (o && d.dmg !== 0) { fx.push(['m', e.x, e.y, o.x, o.y, e.side]); hurt(o, (d.dmg || 6) * (e.cat === 'z' ? 0.6 : 1.2), e); }
    }
  }
  function script() {
    const c = T % L, me = ents.find(e => e.cat === 'k' && e.side === 0), foeK = ents.find(e => e.cat === 'k' && e.side === 1);
    const find = (k, s, y) => ents.find(e => e.kind === k && e.side === s && (y === undefined || e.spec[2] === y));
    const sn = find('sniper', 1), kul = find('kulomet', 0, 1), rus = find('rusicka', 0), pl = find('plamen', 1), gun = find('kulomet', 0, 7);
    if (me) {
      if (at(2)) fx.push(['D', 3 + Math.cos(T * 0.45), me.y, me.x, me.y, 0]);
      if (sn && (at(5.5) || at(11.5))) fx.push(['a', sn.x, sn.y, me.x, me.y, 1, me.id]);
      if (at(6)) { fx.push(['p', me.x, me.y, sn ? sn.x : -1, sn ? sn.y : -1, 0]); if (sn) hurt(sn, 40, me); D.ult = Math.min(100, D.ult + 20); }
      if (at(12)) { fx.push(['g', me.x, me.y, 0, 0, 0]); hurt(me, 12); }
      me.flags = (c > 5.6 && c < 6.3) || (c > 11.6 && c < 12.3) ? me.flags | 256 : me.flags & ~256;
      if (at(10)) { fx.push(['U', me.x, me.y, 3, 0, 0]); ev.push(['ult', 0]); D.ua = 8; D.ult = 0; }
      for (const q of ents) if (q.side === 0 && q.cat === 'u') q.flags = D.ua > 0 && Math.hypot(q.x - me.x, q.y - me.y) <= 3 ? q.flags | 1024 : q.flags & ~1024;
    }
    if (foeK && at(18)) { die(foeK, 0); ev.push(['kk', 0]); }
    if (kul && (at(5) || at(9))) { kul.lvl++; kul.path = kul.lvl === 3 ? 'A' : ''; kul.max = kul.hp = Math.round(220 * LVL[kul.lvl - 1]); fx.push(['u', 4, 1, kul.lvl, 0, 0, kul.path]); }
    if (kul && at(0.2)) { kul.lvl = 1; kul.path = ''; kul.max = kul.hp = 220; }
    if (rus && at(20)) { die(rus, -1, true); fx.push(['r', rus.x, rus.y, 0, 0, 0]); }
    if (pl && at(15)) die(pl, 0);
    if (at(13)) fx.push(['c', 4, 7, 0, 0, 1]);
    if (at(15)) { fx.push(['b', 4, 7, 1.2, 0, 1]); if (gun) hurt(gun, 260); }
    if (at(27)) { fx.push(['b', 12, 6, 1.6, 0, 0]); for (const q of [...ents]) if (q.side !== 0 && Math.abs(q.x - 12) <= 1.5 && Math.abs(q.y - 6) <= 1.5) hurt(q, 180, { side: 0 }); }
    if (!night && at(14)) ev.push(['ecl_warn', 15]);
    if (!night && at(20)) ev.push(['ecl', 1]);
    if (!night && at(30)) ev.push(['ecl', 0]);
    // crate A lands, gets contested and opened twice per loop; crate B is a legendary drop that blinks out and the foe opens
    const cA = c % 16;
    cr = [];
    if (cA > 0.5 && cA < 13) {
      const ch0 = cA < 4 ? 0 : Math.min(0.55, (cA - 4) / 5) + (cA > 10 ? (cA - 10) / 3 * 0.45 : 0), ch1 = cA > 6 && cA < 10 ? Math.min(0.5, (cA - 6) / 4) : 0;
      cr.push([9001, 7, 1, 2, Math.max(0, +(3.5 - cA).toFixed(1)), 40, +ch0.toFixed(2), +ch1.toFixed(2)]);
    }
    if (at(6.1) || at(22.1)) ev.push(['contest', 9001]);
    if (at(13) || at(29)) fx.push(['o', 7, 1, 2, 0, 0]);
    if (c > 1 && c < 24) cr.push([9002, 8, 7, 4, Math.max(0, +(7 - c).toFixed(1)), Math.ceil(24 - c), 0, c > 18 ? +((c - 18) / 6).toFixed(2) : 0]);
    if (at(1.1)) ev.push(['crate', 9002, 4]);
    if (at(24)) fx.push(['o', 8, 7, 4, 0, 1]);
  }
  function relic(c) {
    const k = c % 16;
    if (at(5) || at(21)) { fx.push(['R', 7.5, 4, 0, 0, 0]); ev.push(['relic', 0]); }
    return k < 5 ? [-1, 0, +(k / 5).toFixed(2), 0] : k < 11 ? [0, -1, 0, Math.ceil(40 - (k - 5) * 5)]
      : [0, 1, +((k - 11) / 5).toFixed(2), Math.max(1, Math.ceil(10 - (k - 11) * 2))];
  }
  function snap() {
    const c = T % L, W = 16, ter = Array(W * 9).fill('.'), r2 = q => Math.round(q * 100) / 100, me = ents.find(e => e.cat === 'k' && e.side === 0);
    for (const [x, y] of [[6, 7], [9, 1], [2, 3]]) ter[y * W + x] = '#';
    const v = Array.from({ length: W * 9 }, (_, i) => T > 1 && i % W >= 13 && i < 3 * W ? '0' : '1').join('');
    const flags = e => STAT.reduce((f, [s, i, b]) => f | (e.cat === 'u' && e.side === s && e.i === i ? b : 0), e.flags);
    const ec = night ? [0, 0] : c >= 14 && c < 20 ? [1, Math.ceil(20 - c)] : c >= 20 && c < 30 ? [2, Math.ceil(30 - c)] : [0, 0];
    const m = {
      t: 's', tm: +(130 + T).toFixed(1), ni: night ? 1 : 0, st: night ? 4 + Math.floor(c / 11) : c >= 26 ? 1 : 0, nw: Math.ceil(20 - T % 20),
      r: [420, 85, 3], inc: 6.5, gp: 50, sp: 140, ec, dl: [Math.round(T * 40), Math.round(T * 31)], rl: relic(c), doba: 2,
      tech: c >= 4 ? ['ing1'] : [], cd: {}, free: {}, mob: 0, stc: 1,
      th: [Math.round(3000 - Math.floor(c * 2) / (L * 2) * 2400), Math.round(3000 - Math.floor(c * 2) / (L * 2) * 1100)],
      sh: [0, c >= 22 && c < 28 ? +(28 - c).toFixed(1) : 0], ck: [c >= 24 && c < 30 ? +(30 - c).toFixed(1) : 0, 0],
      out: [c >= 8 && c < 12 ? +(12 - c).toFixed(1) : 0, 0], v, ter: ter.join(''), fx, cr,
      en: ents.filter(e => e.side === 0 || v[Math.round(e.y) * W + Math.round(e.x)] === '1')
        .map(e => [e.id, e.kind, e.side, r2(e.x), r2(e.y), Math.ceil(e.hp), e.max, e.lvl, e.path, flags(e), e.side === 0 ? e.kills : 0]),
      dr: [[7, 1, 0, c % 16 > 4 && c % 16 < 13 ? 1 : 0], [r2(10.5 + Math.sin(T * 0.7)), r2(3 + Math.cos(T * 0.5)), 1, 0]],
      ns: c >= 24 && c < 27 ? [[12, 6, +(27 - c).toFixed(1), 0]] : [], qb: c % 25 < 8 ? [[7, +(8 - c % 25).toFixed(1)]] : [],
      lu: c % 20 < 10 ? [7, 6, +(10 - c % 20).toFixed(1)] : null, rv: [[13, 2, 4, 1.5]],
      job: mode === 'strateg' ? [6, 7, +((T % 5) / 5).toFixed(2)] : null, hcd: 0, hc: 120,
    };
    if (mode === 'kral') m.kr = { id: me ? me.id : 0, dead: me ? 0 : Math.max(0, +(kdead - T).toFixed(1)), blk: me && me.flags & 256 ? (c < 7 ? 2 : 1) : 0,
      bcd: 0, ult: Math.round(D.ult), ua: +D.ua.toFixed(1), dcd: c >= 2 && c < 9 ? +(9 - c).toFixed(1) : 0 };
    if (ev.length) m.ev = ev;
    return m;
  }
  function tick() {
    if (!S.inGame || S.ending) return;
    T0 = T; T = (performance.now() - t0) / 1000;
    const dt = T - T0, due = later.filter(l => T >= l[0]);
    fx = []; ev = [];
    D.ua = Math.max(0, D.ua - dt); D.ult = Math.min(100, D.ult + dt * 2);
    later = later.filter(l => T < l[0]);
    due.forEach(l => l[1]());
    for (const e of [...ents]) if (live(e)) { move(e); if (live(e)) fight(e, dt); }
    script();
    onSnap(snap());
    if (arg.includes('konec') && T > 12 && !ended) {
      ended = true;
      const st = { kills: 14, units: 9, built: 15, crates: 2, techs: 3 };
      endGame({ t: 'end', winner: 0, reason: 'Soupeřův trůn padl.', tm: 312, th: [1640, 0], names: S.names, stats: [st, { ...st, kills: 9 }], dl: [5200, 3100] });
    }
  }
  function start() {
    const ws = S.ws;
    if (ws) { S.ws = null; S.kicked = true; ws.close(); }
    S.tips = false;
    startGame({ side: 0, names: ['Kostěný', 'Popelavý'], mode, deck: (S.recommended || []).slice(0, S.deckSize), w: 16, h: 9, half: 6, mist: [6, 9], horde: [120, 25], throne: 3000 });
    t0 = performance.now();
    setup();
    setInterval(tick, 50);
    setInterval(() => { const s = D.stats(); console.info(`[demo] ${s.fps} fps, p95 ${s.p95} ms, částice ${s.parts}, entity ${s.ents}`); }, 5000);
  }
  D.stats = () => {
    const f = D.fps, s = [...f].sort((a, b) => a - b), avg = f.reduce((a, b) => a + b, 0) / (f.length || 1);
    return { fps: Math.round(1000 / (avg || 16.7)), p95: +(s[Math.floor(s.length * 0.95)] || 0).toFixed(1), parts: pN, ents: S.ents.size,
      nums: FXS.nums.length, dead: FXS.dead.length, decals: FXS.decals.length };
  };
  D.hud = () => {
    const s = D.stats(), text = `UKÁZKA · ${s.fps} fps · p95 ${s.p95} ms · částice ${s.parts}/${PMAX} · entity ${s.ents} · čísla ${s.nums}`;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.font = '700 12px "Alegreya Sans", Candara, sans-serif'; ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(11,8,6,0.75)'; ctx.fillRect(6, 6, ctx.measureText(text).width + 16, 22);
    ctx.fillStyle = PAL.giltHi; ctx.fillText(text, 14, 17.5);
  };
  const boot = setInterval(() => { if (S.defs) { clearInterval(boot); start(); } }, 100);
  return D;
})() : null;
