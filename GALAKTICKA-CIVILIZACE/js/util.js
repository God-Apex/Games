// Pomocné funkce, fyzikální konstanty, náhoda se seedem, barvy hvězd, formátování.
'use strict';

const C = {
  KM_PER_AU: 1.495978707e8,
  KM_PER_LY: 9.4607304725808e12,
  KM_PER_PC: 3.0856775814914e13,
  R_SUN_KM: 695700,
  L_SUN_W: 3.828e26,
  C_MS: 299792458,
  C2: 299792458 * 299792458,
  HOURS_PER_YEAR: 8766,
  RS_KM_PER_MSUN: 2.953,      // Schwarzschildův poloměr na 1 hmotnost Slunce
  START_YEAR: 2100,
};

const U = {
  clamp: (v, a, b) => (v < a ? a : v > b ? b : v),
  lerp: (a, b, t) => a + (b - a) * t,
  smooth: t => t * t * (3 - 2 * t),
  log10: Math.log10,

  // deterministický hash -> [0,1)
  hash(a, b = 0, c = 0) {
    let h = (a | 0) * 374761393 + (b | 0) * 668265263 + (c | 0) * 2147483647;
    h = (h ^ (h >>> 13)) * 1274126177;
    h = h ^ (h >>> 16);
    return (h >>> 0) / 4294967296;
  },
  hashStr(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  },
  // mulberry32
  rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  },

  // barva černého tělesa (Tanner Helland, upraveno), vrací [r,g,b] 0..1
  tempRGB(T) {
    const t = U.clamp(T, 1000, 40000) / 100;
    let r, g, b;
    if (t <= 66) { r = 255; g = 99.4708025861 * Math.log(t) - 161.1195681661; }
    else { r = 329.698727446 * Math.pow(t - 60, -0.1332047592); g = 288.1221695283 * Math.pow(t - 60, -0.0755148492); }
    if (t >= 66) b = 255; else if (t <= 19) b = 0; else b = 138.5177312231 * Math.log(t - 10) - 305.0447927307;
    return [U.clamp(r, 0, 255) / 255, U.clamp(g, 0, 255) / 255, U.clamp(b, 0, 255) / 255];
  },
  rgbCss(c, a = 1) { return `rgba(${(c[0] * 255) | 0},${(c[1] * 255) | 0},${(c[2] * 255) | 0},${a})`; },

  // SI předpony
  si(v, unit = '', digits = 3) {
    if (!isFinite(v)) return '∞ ' + unit;
    if (v === 0) return '0 ' + unit;
    const pre = [['Q', 1e30], ['R', 1e27], ['Y', 1e24], ['Z', 1e21], ['E', 1e18], ['P', 1e15], ['T', 1e12], ['G', 1e9], ['M', 1e6], ['k', 1e3], ['', 1], ['m', 1e-3], ['µ', 1e-6], ['n', 1e-9], ['p', 1e-12]];
    const a = Math.abs(v);
    for (const [p, f] of pre) if (a >= f * 0.9995) return U.num(v / f, digits) + ' ' + p + unit;
    return v.toExponential(2) + ' ' + unit;
  },
  num(v, digits = 3) {
    const a = Math.abs(v);
    if (a >= 1e6) return v.toExponential(2).replace('e+', '·10^');
    if (a >= 100) return Math.round(v).toLocaleString(I18N.locale());
    return (+v.toPrecision(digits)).toLocaleString(I18N.locale());
  },
  amount(v) { // tuny / kusy
    const a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(2) + ' G';
    if (a >= 1e6) return (v / 1e6).toFixed(2) + ' M';
    if (a >= 1e4) return (v / 1e3).toFixed(1) + ' k';
    if (a >= 100) return Math.floor(v).toString();
    return (Math.floor(v * 10) / 10).toString();
  },
  mass(kg) { // antihmota
    if (kg >= 1000) return U.num(kg / 1000) + ' t';
    if (kg >= 1) return U.num(kg) + ' kg';
    if (kg >= 1e-3) return U.num(kg * 1e3) + ' g';
    if (kg >= 1e-6) return U.num(kg * 1e6) + ' mg';
    return U.num(kg * 1e9) + ' µg';
  },
  // vzdálenost v km -> čitelná jednotka
  dist(km) {
    const a = Math.abs(km);
    if (a < 1) return U.num(km * 1000) + ' m';
    if (a < 1e7) return U.num(km) + ' km';
    if (a < 0.05 * C.KM_PER_LY) return U.num(km / C.KM_PER_AU) + ' AU';
    if (a < 1e3 * C.KM_PER_LY) return U.num(km / C.KM_PER_LY) + ' ' + I18N.t('u.ly');
    if (a < 1e6 * C.KM_PER_LY) return U.num(km / C.KM_PER_LY / 1e3) + ' ' + I18N.t('u.kly');
    if (a < 1e9 * C.KM_PER_LY) return U.num(km / C.KM_PER_LY / 1e6) + ' ' + I18N.t('u.mly');
    return U.num(km / C.KM_PER_LY / 1e9) + ' ' + I18N.t('u.gly');
  },
  duration(hours) {
    const y = hours / C.HOURS_PER_YEAR;
    if (y >= 1e6) return U.num(y / 1e6) + ' ' + I18N.t('u.myr');
    if (y >= 1) return U.num(y) + ' ' + U.plural(+y.toPrecision(3), 'yr');
    const d = hours / 24;
    if (d >= 1) return U.num(d) + ' ' + U.plural(+d.toPrecision(3), 'day');
    return U.num(hours) + ' ' + I18N.t('u.hr');
  },
  // české tvary: 1 rok, 2–4 roky, 5+ / desetinná let
  plural(v, unit) {
    if (I18N.lang !== 'cs') return I18N.t('u.' + unit);
    const forms = { yr: ['rok', 'roky', 'let', 'roku'], day: ['den', 'dny', 'dní', 'dne'] }[unit];
    if (!Number.isInteger(v)) return forms[3];   // 1,5 roku
    if (v === 1) return forms[0];
    if (v >= 2 && v <= 4) return forms[1];
    return forms[2];
  },
  dateStr(hours) {
    const y = C.START_YEAR + hours / C.HOURS_PER_YEAR;
    const yi = Math.floor(y);
    const day = Math.floor((y - yi) * 365.25) + 1;
    return `${yi.toLocaleString(I18N.locale())}, ${I18N.t('u.dayN')} ${day}`;
  },
  // Kardaševova škála (Sagan): K = (log10 P[W] - 6) / 10
  kardashev(watts) { return watts > 0 ? (Math.log10(watts) - 6) / 10 : 0; },

  // hodnotový šum (pro procedurální věci na CPU)
  noise2(x, y, seed = 0) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = U.hash(xi, yi, seed), b = U.hash(xi + 1, yi, seed);
    const c = U.hash(xi, yi + 1, seed), d = U.hash(xi + 1, yi + 1, seed);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  },
  el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  },
  esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); },
};
