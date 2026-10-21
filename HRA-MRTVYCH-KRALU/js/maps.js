'use strict';
// Terrain table, terrain painters and the lobby map preview (SPEC 3.5 / 5.1, MAI 3.1 and 3.3).
// Passability and buildability on the client follow the server: WALK = '.~^=', BUILD = '.^'.
// The snapshot keeps one character per cell: '.' floor, '#' rubble (scrap), 'X' pillar, 'w' water, '=' bridge, '~' canal, '^' dais.
const TERRAIN = {
  '.': { name: 'Dlažba', walk: true, build: true, tip: '' },
  '#': { name: 'Trosky', walk: false, build: false, tip: 'Trosky: neprůchozí', no: 'Na troskách' },
  'X': { name: 'Sloup', walk: false, build: false, tip: 'Sloup: neprůchozí', no: 'Na sloupu' },
  'w': { name: 'Voda', walk: false, build: false, tip: 'Voda: neprůchozí', no: 'Ve vodě' },
  '=': { name: 'Most', walk: true, build: false, tip: 'Most: dá se přejít, stavět na něm nejde.', no: 'Na mostě' },
  '~': { name: 'Kanál', walk: true, build: false, tip: 'Kanál: jednotky a zombie jsou tu rychlejší', no: 'V kanálu' },
  '^': { name: 'Vyvýšené místo', walk: true, build: true, tip: 'Vyvýšené místo: věž tu má +1 dosah a dohled' },
};
const isWalk = ch => !!(TERRAIN[ch] && TERRAIN[ch].walk);
const isBuild = ch => !!(TERRAIN[ch] && TERRAIN[ch].build);
// Czech refusal text for a cell the player cannot build on or deploy to because of its terrain ('' = terrain is fine)
function terrainRefusal(ch, unit) {
  const t = TERRAIN[ch];
  if (!t || t.build) return '';
  return `${t.no || 'Tady'} ${unit ? 'jednotku nasadit' : 'stavět'} nejde.`;
}

// Per-map look. `floor` is an optional tint over the floor tiles (terrainTheme(id).floor; render.js keeps its own mapTheme() that returns the theme id).
const THEMES = {
  ruiny: { floor: null, stone: ['#8c8576', '#5f594e', '#34302a'], water: ['#32596a', '#1c3946'], canal: ['#2f6672', '#1d4550'], rail: '#3a2b1e' },
  predmesti: { floor: 'rgba(130,140,165,0.05)', stone: ['#9b9a9c', '#6c6b70', '#3a3a41'], water: ['#36707c', '#1d4954'], canal: ['#3a8088', '#235a64'], rail: '#33291f' },
  tovarna: { floor: 'rgba(210,120,60,0.05)', stone: ['#a4a9b1', '#646b77', '#30343c'], water: ['#3a5c66', '#1f3a44'], canal: ['#3a7078', '#235058'], rail: '#2c2a2a' },
  most: { floor: 'rgba(90,125,170,0.05)', stone: ['#9a948a', '#686258', '#38342d'], water: ['#2b5a78', '#16364f'], canal: ['#2f6a80', '#1b4558'], rail: '#3b2a1b' },
  metro: { floor: 'rgba(70,165,150,0.05)', stone: ['#8f9a96', '#5e6a66', '#303836'], water: ['#2c5f62', '#173d40'], canal: ['#2f7a74', '#1b5550'], rail: '#2a2a28' },
};
const terrainTheme = id => THEMES[id] || THEMES.ruiny;

const TERRAIN_INK = '#150f0a';
function tGrad(g, x0, y0, x1, y1, cols) {
  const gr = g.createLinearGradient(x0, y0, x1, y1);
  cols.forEach((c, i) => gr.addColorStop(cols.length === 1 ? 0 : i / (cols.length - 1), c));
  return gr;
}
function tEll(g, cx, cy, rx, ry) { g.beginPath(); g.ellipse(cx, cy, rx, ry, 0, 0, TAU); }
// Painters work in cell-local pixels: (0,0) is the top-left corner of the cell, `cs` its size.
const TERRAIN_PAINT = {
  X(g, cs, x, y, th, id) {
    g.fillStyle = 'rgba(0,0,0,0.34)'; tEll(g, cs * 0.54, cs * 0.82, cs * 0.34, cs * 0.1); g.fill();
    g.lineJoin = 'round'; g.lineWidth = Math.max(1, cs * 0.04); g.strokeStyle = TERRAIN_INK;
    if (id === 'tovarna') {                       // riveted steel block with a hazard stripe
      g.beginPath(); g.rect(cs * 0.16, cs * 0.12, cs * 0.68, cs * 0.7);
      g.fillStyle = tGrad(g, cs * 0.16, 0, cs * 0.84, 0, [th.stone[0], th.stone[1], th.stone[2]]); g.fill(); g.stroke();
      g.fillStyle = '#e0b030'; g.fillRect(cs * 0.17, cs * 0.7, cs * 0.66, cs * 0.1);
      g.fillStyle = '#26282c';
      for (let i = 0; i < 6; i++) { g.beginPath(); g.moveTo(cs * (0.17 + i * 0.11), cs * 0.8); g.lineTo(cs * (0.23 + i * 0.11), cs * 0.7); g.lineTo(cs * (0.28 + i * 0.11), cs * 0.7); g.lineTo(cs * (0.22 + i * 0.11), cs * 0.8); g.fill(); }
      g.fillStyle = th.stone[2];
      for (const [rx, ry] of [[0.24, 0.2], [0.76, 0.2], [0.24, 0.58], [0.76, 0.58]]) { g.beginPath(); g.arc(cs * rx, cs * ry, cs * 0.03, 0, TAU); g.fill(); }
      g.strokeStyle = 'rgba(255,255,255,0.18)'; g.beginPath(); g.moveTo(cs * 0.2, cs * 0.16); g.lineTo(cs * 0.8, cs * 0.16); g.stroke();
    } else if (id === 'metro') {                  // tiled concrete pier with a safety stripe
      g.beginPath(); g.rect(cs * 0.2, cs * 0.1, cs * 0.6, cs * 0.72);
      g.fillStyle = tGrad(g, cs * 0.2, 0, cs * 0.8, 0, [th.stone[0], th.stone[1], th.stone[2]]); g.fill(); g.stroke();
      g.strokeStyle = 'rgba(0,0,0,0.3)'; g.lineWidth = 1;
      g.beginPath(); for (let i = 1; i < 4; i++) { g.moveTo(cs * 0.2, cs * (0.1 + i * 0.16)); g.lineTo(cs * 0.8, cs * (0.1 + i * 0.16)); } g.moveTo(cs * 0.5, cs * 0.1); g.lineTo(cs * 0.5, cs * 0.82); g.stroke();
      g.fillStyle = '#d9b43a'; g.fillRect(cs * 0.2, cs * 0.66, cs * 0.6, cs * 0.07);
    } else {                                      // fluted stone column with capital and plinth
      g.beginPath(); g.rect(cs * 0.28, cs * 0.2, cs * 0.44, cs * 0.58);
      g.fillStyle = tGrad(g, cs * 0.28, 0, cs * 0.72, 0, [th.stone[0], th.stone[1], th.stone[2]]); g.fill(); g.stroke();
      g.strokeStyle = 'rgba(0,0,0,0.28)'; g.lineWidth = 1; g.beginPath();
      for (const fx of [0.4, 0.5, 0.6]) { g.moveTo(cs * fx, cs * 0.24); g.lineTo(cs * fx, cs * 0.76); }
      g.stroke();
      g.lineWidth = Math.max(1, cs * 0.04); g.strokeStyle = TERRAIN_INK;
      for (const [ry, rh, rw] of [[0.1, 0.11, 0.62], [0.76, 0.1, 0.62]]) {
        g.beginPath(); g.rect(cs * (0.5 - rw / 2), cs * ry, cs * rw, cs * rh);
        g.fillStyle = tGrad(g, 0, cs * ry, 0, cs * (ry + rh), [th.stone[0], th.stone[1]]); g.fill(); g.stroke();
      }
    }
    if (hash(x, y, 41) < 0.5) { g.strokeStyle = 'rgba(0,0,0,0.4)'; g.lineWidth = 1; g.beginPath(); g.moveTo(cs * 0.55, cs * 0.3); g.lineTo(cs * 0.5, cs * 0.45); g.lineTo(cs * 0.58, cs * 0.6); g.stroke(); }
  },
  w(g, cs, x, y, th) {
    g.fillStyle = tGrad(g, 0, 0, 0, cs, th.water); g.fillRect(0, 0, cs, cs);
    g.strokeStyle = 'rgba(190,225,235,0.34)'; g.lineWidth = Math.max(1, cs * 0.04); g.lineCap = 'round';
    for (let i = 0; i < 3; i++) {
      const cx = cs * (0.2 + hash(x, y, 50 + i) * 0.5), cy = cs * (0.2 + i * 0.3), w = cs * (0.16 + hash(x, y, 60 + i) * 0.16);
      g.beginPath(); g.moveTo(cx - w, cy); g.quadraticCurveTo(cx - w / 2, cy - cs * 0.06, cx, cy); g.quadraticCurveTo(cx + w / 2, cy + cs * 0.06, cx + w, cy); g.stroke();
    }
    g.fillStyle = 'rgba(235,248,250,0.4)';
    for (let i = 0; i < 2; i++) g.fillRect(cs * (0.15 + hash(x, y, 70 + i) * 0.7), cs * (0.12 + hash(x, y, 80 + i) * 0.76), Math.max(1.5, cs * 0.04), Math.max(1.5, cs * 0.04));
    g.strokeStyle = 'rgba(0,0,0,0.45)'; g.lineWidth = 1; g.strokeRect(0.5, 0.5, cs - 1, cs - 1);
  },
  '='(g, cs, x, y, th) {
    g.fillStyle = '#4a3220'; g.fillRect(0, 0, cs, cs);
    const n = 4, pw = cs / n;
    for (let i = 0; i < n; i++) {
      const j = (hash(x, y, 90 + i) - 0.5) * 0.12;
      g.fillStyle = tGrad(g, 0, 0, 0, cs, [mix('#8a6140', '#ffffff', 0.04 + j), mix('#6e4b2e', '#000000', 0.05 - j)]);
      g.fillRect(i * pw + 1, 0, pw - 2, cs);
      g.fillStyle = 'rgba(0,0,0,0.22)'; g.fillRect(i * pw + pw * 0.4, cs * (0.2 + hash(x, y, 95 + i) * 0.5), 1, cs * 0.14);
    }
    const rh = Math.max(3, cs * 0.14);
    for (const ry of [0, cs - rh]) {
      g.fillStyle = tGrad(g, 0, ry, 0, ry + rh, ['#5a3f28', '#2e1f13']); g.fillRect(0, ry, cs, rh);
      g.fillStyle = 'rgba(255,230,190,0.18)'; g.fillRect(0, ry, cs, 1);
      g.fillStyle = '#b8b2a4';
      for (let i = 0; i < n; i++) g.fillRect(i * pw + pw / 2 - 1, ry + rh / 2 - 1, 2, 2);
    }
  },
  '~'(g, cs, x, y, th) {
    g.fillStyle = tGrad(g, 0, 0, 0, cs, th.canal); g.fillRect(0, 0, cs, cs);
    const rh = Math.max(3, cs * 0.12);
    for (const ry of [0, cs - rh]) {                    // stone curbs along the lane
      g.fillStyle = tGrad(g, 0, ry, 0, ry + rh, [th.stone[1], th.stone[2]]); g.fillRect(0, ry, cs, rh);
      g.fillStyle = 'rgba(255,240,210,0.14)'; g.fillRect(0, ry, cs, 1);
    }
    // flow chevrons point from the board edge towards its centre
    const sc = g.getTransform ? g.getTransform().a || 1 : 1;
    const gx = g.getTransform ? g.getTransform().e / sc : 0;
    const mid = g.canvas.width / sc / 2, dir = (gx + cs / 2) < mid ? 1 : -1;
    g.strokeStyle = 'rgba(215,245,240,0.5)'; g.lineWidth = Math.max(1, cs * 0.05); g.lineCap = 'round'; g.lineJoin = 'round';
    for (const [cx, cy] of [[0.32, 0.38], [0.7, 0.62]]) {
      const px0 = cs * cx, py0 = cs * cy, a = cs * 0.1;
      g.beginPath(); g.moveTo(px0 - dir * a, py0 - a); g.lineTo(px0 + dir * a, py0); g.lineTo(px0 - dir * a, py0 + a); g.stroke();
    }
  },
  '^'(g, cs, x, y, th) {
    g.fillStyle = TERRAIN_INK; g.fillRect(0, 0, cs, cs);
    const b = Math.max(1, cs * 0.04), s = cs * 0.1;
    g.fillStyle = tGrad(g, 0, 0, cs, cs, [th.stone[0], th.stone[1]]); g.fillRect(b, b, cs - 2 * b, cs - 2 * b);
    g.fillStyle = 'rgba(255,245,220,0.3)'; g.fillRect(b, b, cs - 2 * b, s * 0.5); g.fillRect(b, b, s * 0.5, cs - 2 * b);   // lit edges
    g.fillStyle = 'rgba(0,0,0,0.38)'; g.fillRect(b, cs - b - s, cs - 2 * b, s); g.fillRect(cs - b - s, b, s, cs - 2 * b);   // shaded step
    g.fillStyle = tGrad(g, 0, 0, cs, cs, [mix(th.stone[0], '#ffffff', 0.1), th.stone[1]]);
    g.fillRect(cs * 0.2, cs * 0.2, cs * 0.52, cs * 0.52);
    g.strokeStyle = 'rgba(201,162,74,0.65)'; g.lineWidth = Math.max(1, cs * 0.035); g.strokeRect(cs * 0.28, cs * 0.28, cs * 0.36, cs * 0.36);
    g.fillStyle = 'rgba(236,208,138,0.7)'; g.beginPath(); g.arc(cs * 0.46, cs * 0.46, cs * 0.045, 0, TAU); g.fill();
  },
};
// Paint terrain character `ch` into the cell whose top-left corner is (X, Y) on context g (already scaled to CSS px).
// Called by render.js boardCanvas on top of the floor tile for ch not in {'.', '#'}.
function paintTerrain(g, ch, X, Y, cs, x, y, theme) {
  const f = TERRAIN_PAINT[ch];
  if (!f) return;
  g.save();
  g.beginPath(); g.rect(X, Y, cs, cs); g.clip();
  g.translate(X, Y);
  f(g, cs, x, y, terrainTheme(theme), theme);
  g.restore();
}

/* ---------------- lobby map preview ---------------- */
const PREV = { cell: 8, W: 16, H: 9 };
// Draw a 16x9 preview of `ter` (144 chars) into `canvas`. ter === null: Ruiny with random rubble; ter === '?': the "Náhodná" card.
// `meta` ({relic: [y0, y1]}) marks the Relikvie. A flat rendering, so the picture is quick to read, not the in-game sprites.
function drawMapPreview(canvas, ter, theme, meta) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2), c = PREV.cell, w = PREV.W * c, h = PREV.H * c;
  if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  const g = canvas.getContext('2d'), th = terrainTheme(theme);
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  const cell = (x, y) => (typeof ter === 'string' && ter.length >= PREV.W * PREV.H ? ter[y * PREV.W + x] : '.');
  for (let y = 0; y < PREV.H; y++) for (let x = 0; x < PREV.W; x++) {
    const ch = cell(x, y), X = x * c, Y = y * c, mist = x >= 6 && x <= 9;
    g.fillStyle = mist ? ((x + y) % 2 ? PAL.mistT1 : PAL.mistT2) : ((x + y) % 2 ? PAL.stoneL : PAL.stoneD);
    g.fillRect(X, Y, c, c);
    if (ch === 'X') { g.fillStyle = th.stone[2]; g.fillRect(X + 1, Y + 1, c - 2, c - 2); g.fillStyle = th.stone[0]; g.fillRect(X + 2, Y + 1, c - 4, 2); }
    else if (ch === 'w') { g.fillStyle = th.water[0]; g.fillRect(X, Y, c, c); g.fillStyle = 'rgba(200,230,240,0.35)'; g.fillRect(X + 1 + (x * 3 + y) % 4, Y + 3, 3, 1); }
    else if (ch === '=') { g.fillStyle = '#7a5434'; g.fillRect(X, Y, c, c); g.fillStyle = 'rgba(0,0,0,0.3)'; g.fillRect(X + 2, Y, 1, c); g.fillRect(X + 5, Y, 1, c); g.fillStyle = '#3a2819'; g.fillRect(X, Y, c, 1); g.fillRect(X, Y + c - 1, c, 1); }
    else if (ch === '~') { g.fillStyle = th.canal[0]; g.fillRect(X, Y + 1, c, c - 2); g.fillStyle = 'rgba(215,245,240,0.5)'; g.fillRect(X + 2, Y + 3, 3, 1); }
    else if (ch === '^') { g.fillStyle = th.stone[0]; g.fillRect(X + 1, Y + 1, c - 2, c - 2); g.fillStyle = 'rgba(255,255,255,0.25)'; g.fillRect(X + 1, Y + 1, c - 2, 1); g.fillStyle = 'rgba(201,162,74,0.8)'; g.fillRect(X + 3, Y + 3, 2, 2); }
    else if (ch === '#') { g.fillStyle = '#6a5f50'; g.fillRect(X + 1, Y + 2, c - 2, c - 3); g.fillStyle = '#8a7e6a'; g.fillRect(X + 2, Y + 2, 3, 2); }
  }
  if (ter === null) {                                // Ruiny: rubble lands elsewhere in every game, show a few at fixed spots
    g.fillStyle = '#6a5f50';
    for (const [x, y] of [[2, 1], [4, 5], [1, 7], [3, 3], [6, 2], [7, 6]]) for (const xx of [x, 15 - x]) { g.fillRect(xx * c + 1, y * c + 2, c - 2, c - 3); }
    g.fillStyle = '#8a7e6a';
    for (const [x, y] of [[2, 1], [4, 5], [1, 7], [3, 3], [6, 2], [7, 6]]) for (const xx of [x, 15 - x]) g.fillRect(xx * c + 2, y * c + 2, 3, 2);
  }
  // thrones at both edges and the Relikvie in the centre
  g.fillStyle = 'rgba(201,162,74,0.9)';
  for (const tx of [0, 15]) g.fillRect(tx * c + (tx ? c - 2 : 0), 3 * c, 2, 3 * c);
  if (meta && meta.relic) {
    const cy = (meta.relic[0] + meta.relic[1] + 1) / 2 * c, cx = 8 * c;
    g.fillStyle = 'rgba(14,11,9,0.8)'; g.beginPath(); g.moveTo(cx, cy - 6); g.lineTo(cx + 6, cy); g.lineTo(cx, cy + 6); g.lineTo(cx - 6, cy); g.closePath(); g.fill();
    g.strokeStyle = PAL.gilt; g.lineWidth = 1.2; g.stroke();
  }
  if (ter === '?') {
    g.fillStyle = 'rgba(14,11,9,0.55)'; g.fillRect(0, 0, w, h);
    g.fillStyle = PAL.giltHi; g.font = `800 ${Math.round(h * 0.78)}px "Grenze Gotisch", "Cinzel", Georgia, serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('?', w / 2, h * 0.54);
  }
  g.strokeStyle = PAL.giltLo; g.lineWidth = 1; g.strokeRect(0.5, 0.5, w - 1, h - 1);
}
