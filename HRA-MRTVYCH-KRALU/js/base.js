'use strict';
// Shared constants, state and small helpers.
const $ = s => document.querySelector(s);
const TAU = Math.PI * 2;
const LVL = [1, 1.35, 1.7];
// "Iluminovaná krypta" palette (see DESIGN.md, Vzhled). Side A = Kostěný král (bone + lapis), B = Popelavý král (ebony + ember).
const PAL = {
  bg: '#0e0b09', bg2: '#17110e', stoneL: '#48423a', stoneD: '#3b3630', mortar: '#15110e', mistT1: '#2f3530', mistT2: '#262b27',
  blight: '#2b2a22', moss: '#5f7a52', leather1: '#1b1411', leather2: '#241a15', leather3: '#2f231c', rule: '#4a3a26',
  vellum: '#e9dcc0', vellum2: '#d8c59c', text: '#ecdfc3', muted: '#b9ad94', dim: '#857a66', ink: '#2a1d12', ink2: '#5a4a35',
  gilt: '#c9a24a', giltHi: '#ecd08a', giltLo: '#7a5e22', rubric: '#c23b2e', rubricD: '#8e2219', candle: '#ffb85a', flame: '#fff1c4',
  verdigris: '#5fb08f', verdigrisD: '#2e7a5e', amethyst: '#a77bd6', amethystD: '#6a4a9a', moon: '#b9c3d6', ghost: '#cbbcff',
  ghostD: '#7b5fd0', iron: '#5a5d63', ironL: '#8a8e96', bronze: '#b08a3e', wood: '#6e4b2e', woodD: '#4a3220', bone: '#d6ccb4',
  flesh: '#8f9c78', fleshD: '#4d5640', fleshL: '#c3cba8', zInk: '#1d2216', rags: '#3a332c', eye: '#d6ff6e', mist: '#b9cbbf',
  blood: '#9e2b30', sepia: '#a08a66', hpOk: '#9cc66a', hpMid: '#e3b04a', hpLow: '#d4473a',
};
const COL = ['#5b8fe0', '#e8833a'];                 // team enamel: A lapis, B ember (side is also carried by bone vs ebony material)
const TEAM = [{ c: '#5b8fe0', hi: '#a9c6f5', lo: '#2f5fae', ink: '#2f5fae' }, { c: '#e8833a', hi: '#ffbf7a', lo: '#a8501a', ink: '#a8501a' }];
const MAT = [{ hi: '#f6eedb', base: '#e2d6bc', mid: '#c2b498', lo: '#8f8169', ink: '#2b2118' },
  { hi: '#574e50', base: '#2e2729', mid: '#211c1e', lo: '#141112', ink: '#070506', rim: '#e8833a' }];
const RAR_COL = ['#a59d8f', '#5fb08f', '#5c8fe0', '#a868e0', '#ecc65a'];
const CAT_COL = { b: PAL.gilt, u: '#e6dcc6', a: PAL.amethyst };
const SLOT_CODES = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8', 'Digit9', 'Digit0'];
const SLOT_LABELS = '1234567890';
const ATTACK = ['kulomet', 'plamen', 'sniper', 'tesla'];
const GLYPH = { pesak: '♟', jezdec: '♞', obrnenec: '♜', strelec: '♝', dama: '♛' };
const TIPS = [
  'Odstřelovač střílí jen na to, co vidíš. Dej k němu <b>Hlásku</b>.',
  'Generátor od čtvrtého a Odstřelovač od třetího jsou <b>dražší</b>.',
  'Pěšák, který dojde k soupeřovu trůnu, se <b>promění v Dámu</b> (když žádnou nemáš).',
  'Jednotka se 3 zářezy se stane <b>veteránem</b>. Soupeřův veterán vynese 15 🔩.',
  'Jezdec přeskočí zdi. Proti němu pomůže Plamenomet nebo <b>mina</b>.',
  '🧪 Vzorky dávají Obři, Alfa, bedny a <b>Relikvie</b>. Za 2 výzkumy přijde Doba II.',
  '<b>Šach</b>: soupeřovy jednotky ve 3 řadách u tvého trůnu, když se nemůžeš bránit. Do 10 s se z toho dostaň.',
  'Minu soupeř nevidí. Odhalí ji jen Hláska s <b>Reflektorem</b>.',
  'Král: zmáčkni <b>mezerník</b>, když na tebe míří rudá nit. Odražená střela zasáhne střelce.',
  'Král: <b>Shift</b> je výpad (uhneš i střele), <b>Q</b> válečný pokřik, když je nabitý.',
  'Stratég: <b>G</b> Útok! na 6 s zesílí všechny tvé jednotky. Načasuj ho na Zatmění.',
  'Při <b>Zatmění</b> vidí věže jen 1,5 pole. Šetři jednotky na tuhle chvíli.',
  '<b>Relikvie</b> uprostřed Mlhy dává +2 ⚡/s a 🧪. Obsadíš ji jednotkou nebo Králem.',
  'Od Doby II: máš moc energie a málo šrotu? <b>Přetav</b> 30 ⚡ na 10 🔩 (klávesa C).',
  'Bednu sebereš za 3 s. Když u ní stojí i soupeř, je <b>sporná</b>, dokud ho nevyženeš.',
  'Úroveň 3: vyber stavbu, zmáčkni <b>U</b> a pak <b>A</b> nebo <b>B</b>.',
  '<b>Tlupa</b> (T) pošle soupeři vlastní zombie. Výzkum Biotech ji zlevní.',
  'Rušička s <b>Maskováním</b> schová tvé stavby před soupeřovým průzkumem.',
  'Zásobovací bedna může obsahovat i <b>kartu zdarma</b> (🎁 na liště).',
  'Klávesy <b>1–0</b> vybírají karty, pravé tlačítko myši výběr zruší. <b>M</b> ztlumí zvuk.',
  'Alfa v Mlze je silná, ale kdo ji zabije, dostane 🧪 a <b>legendární bednu</b>.',
];
const STEPS = [
  ['gen', 'Postav Generátor (klávesa 1)'],
  ['tower', 'Postav obrannou věž blízko Mlhy'],
  ['scout', 'Prozkoumej soupeře (Hláska, dron, jednotky)'],
  ['unit', 'Vyšli jednotku do útoku'],
  ['upg', 'Vylepši stavbu (klikni na ni, pak U)'],
  ['crate', 'Seber zásobovací bednu z Mlhy'],
  ['res', 'Vyzkoumej technologii (V)'],
];
// Settings (popover in the top bar). "Klidné efekty" start on when the system asks for reduced motion.
const REDUCED_MOTION = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
function loadOpt() {
  const o = { sfx: 70, mus: 40, mute: false, shake: 1, flash: true, nums: true, calm: REDUCED_MOTION };
  let v = {};
  try { v = JSON.parse(load('hmk_opt', '{}')) || {}; } catch (e) { v = {}; }
  for (const k of Object.keys(o)) if (typeof v[k] === typeof o[k]) o[k] = v[k];
  if (![0, 0.4, 1].includes(o.shake)) o.shake = 1;
  return o;
}
const S = {
  ws: null, defs: null, research: null, branches: null, cmds: null, base: [], pool: [], recommended: [], deckSize: 8,
  rarity: [], dobaAt: [2, 5], lobby: null, deck: [], tips: true, ready: false, kicked: false, oldServer: false,
  side: 0, names: ['', ''], mode: 'kral', myDeck: [], W: 16, H: 9, half: 6, mist: [6, 9], throneMax: 3000, horde: [120, 25],
  conv: [30, 10, 2], relicFrom: 120,
  snap: null, ents: new Map(), ghosts: new Map(), bmap: new Map(), fx: [], aims: new Map(), lasers: [],
  slots: [], pick: null, sel: null, hover: null, barHover: null, inGame: false, ending: false, sideHtml: '', resHtml: '', resOpen: false,
  keys: {}, inp: { mx: 0, my: 0, b: false, r: false, d: false, u: false }, kp: null, seenEnemy: false, steps: new Set(), shownTips: new Set(),
  choose: null, mouse: null, opt: null,
};
const K = () => S.defs.kral;
const roman = n => ['I', 'II', 'III'][Math.max(1, Math.min(3, n)) - 1];
// Must match VERSION in server.py. The server reads this page from disk on every load, so an updated
// page can meet a server process that was started before the update and speaks the old protocol.
const CLIENT_VER = '0.5';

/* ---------------- small helpers ---------------- */
function load(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
function save(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function rgba(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
function mix(h1, h2, t) {
  const a = parseInt(h1.slice(1), 16), b = parseInt(h2.slice(1), 16);
  const c = s => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t);
  return '#' + ((1 << 24) | (c(16) << 16) | (c(8) << 8) | c(0)).toString(16).slice(1);
}
function hash(x, y, n) { let h = (x * 374761393 + y * 668265263 + n * 2147483647) | 0; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function mkCanvas(w, h) { const c = document.createElement('canvas'); c.width = Math.max(1, Math.ceil(w)); c.height = Math.max(1, Math.ceil(h)); return c; }
S.opt = loadOpt();

// resource icons as inline SVG, so currency looks the same in every text
const SVG = {
  e: '<svg class="ic ic-e" viewBox="0 0 10 10"><path d="M6.2 0 1.4 5.7h3.2L3.7 10l4.9-6.1H5.4z"/></svg>',
  s: '<svg class="ic ic-s" viewBox="0 0 10 10"><path fill-rule="evenodd" d="M5 .4 9 2.7v4.6L5 9.6 1 7.3V2.7zM5 3.4a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 1 0 0-3.2z"/></svg>',
  v: '<svg class="ic ic-v" viewBox="0 0 10 10"><path d="M3.4.4h3.2v.9h-.6v2.4l3.2 5.3c.3.5-.1 1-.6 1H1.4c-.5 0-.9-.5-.6-1L4 3.7V1.3h-.6z"/></svg>',
  g: '<svg class="ic ic-g" viewBox="0 0 10 10"><path d="M5 0l1.3 3.7L10 5 6.3 6.3 5 10 3.7 6.3 0 5l3.7-1.3z"/></svg>',
};
// Per-side heraldic emblem, a shape cue that survives greyscale: A = heater shield with a crescent, B = roundel with a flame.
const EMB = [
  '<svg class="emb emb-a" viewBox="0 0 20 22" aria-hidden="true"><path d="M2 1.5h16v8.5c0 5.6-3.7 8.8-8 10.5-4.3-1.7-8-4.9-8-10.5z"/><path class="ch" d="M12.4 5.6A4.6 4.6 0 0 0 12.4 14.8 5.8 5.8 0 0 1 12.4 5.6z"/></svg>',
  '<svg class="emb emb-b" viewBox="0 0 20 22" aria-hidden="true"><circle cx="10" cy="11" r="8.6"/><path class="ch" d="M10 4.6c.7 2.5 3.7 3.7 3.7 7.2a3.7 3.7 0 0 1-7.4 0c0-1.7.8-2.7 1.8-3.4-.1 1.3.4 2.3 1.2 2.7-.4-2.3.2-4.5.7-6.5z"/></svg>',
];
function iconize(html) { return html.replace(/⚡/g, SVG.e).replace(/🔩/g, SVG.s).replace(/🧪/g, SVG.v).replace(/🎁/g, SVG.g); }
function fmt(text) { return iconize(esc(text)); }
