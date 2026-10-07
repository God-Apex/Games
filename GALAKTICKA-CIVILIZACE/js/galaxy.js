// Model vesmíru: reálné hvězdy (HYG), exotické objekty, procedurální hvězdy za hranicí katalogu,
// planetární soustavy, Mléčná dráha a nekonečné pole galaxií.
// Souřadnice: galaktická rovina, km, Slunce v počátku, osa +x míří ke středu Galaxie.
'use strict';

const GAL = {
  GC_PC: 8178,                // vzdálenost Slunce od Sgr A*
  PITCH: 0.2126,              // tan(12°), sklon spirálních ramen
  ARM_R0: 4.0,                // kpc, začátek ramen (konce příčky)
  BAR_ANGLE: 27 * Math.PI / 180,
  CATALOG_PC: 900,            // poloměr bubliny s reálnými daty
  PROC_CELL_PC: 6,            // buňka procedurálních hvězd
};
GAL.ARM_PHI0 = (Math.PI - Math.log(GAL.GC_PC / 1000 / GAL.ARM_R0) / GAL.PITCH) - Math.PI / 2;

const EQ2GAL = [[-0.0548755604, -0.8734370902, -0.4838350155],
  [0.4941094279, -0.4448296300, 0.7469822445],
  [-0.8676661490, -0.1980763734, 0.4559837762]];

function galFromRaDec(raDeg, decDeg, distPc) {
  const ra = raDeg * Math.PI / 180, dec = decDeg * Math.PI / 180;
  const x = distPc * Math.cos(dec) * Math.cos(ra), y = distPc * Math.cos(dec) * Math.sin(ra), z = distPc * Math.sin(dec);
  return EQ2GAL.map(r => r[0] * x + r[1] * y + r[2] * z);
}
function galFromLB(lDeg, bDeg, distPc) {
  const l = lDeg * Math.PI / 180, b = bDeg * Math.PI / 180;
  return [distPc * Math.cos(b) * Math.cos(l), distPc * Math.cos(b) * Math.sin(l), distPc * Math.sin(b)];
}

// Hustota hvězd v Galaxii (relativní, 1 ~ okolí Slunce). Stejný model kreslí shader Mléčné dráhy.
function galaxyDensity(xPc, yPc) {
  const X = (xPc - GAL.GC_PC) / 1000, Y = yPc / 1000;
  const R = Math.hypot(X, Y) + 1e-6;
  const phi = Math.atan2(Y, X);
  const disc = Math.exp(-(R - 8.178) / 3.0) * (R > 15 ? Math.exp(-(R - 15) * 1.5) : 1);
  const psi = phi - Math.log(R / GAL.ARM_R0) / GAL.PITCH - GAL.ARM_PHI0;
  const main = Math.pow(0.5 + 0.5 * Math.cos(2 * psi), 5);
  const minor = Math.pow(0.5 + 0.5 * Math.cos(4 * psi), 8) * 0.5;
  const arms = R > GAL.ARM_R0 * 0.8 ? 0.35 + 1.4 * (main + minor) : 0.6;
  const ux = -Math.cos(GAL.BAR_ANGLE), uy = Math.sin(GAL.BAR_ANGLE);
  const along = X * ux + Y * uy, across = -X * uy + Y * ux;
  const bar = 25 * Math.exp(-(along * along) / (2 * 2.2 * 2.2) - (across * across) / (2 * 0.7 * 0.7));
  const bulge = 120 * Math.exp(-(R * R) / (2 * 0.6 * 0.6));
  return disc * arms + bar + bulge;
}

const Galaxy = {
  n: 0,
  X: null, Y: null, Z: null,     // km (Float64Array)
  T: null, R: null, L: null,     // K, R_sun, L_sun
  kind: null,                    // 0 hvězda, 1 neutronová hvězda, 2 černá díra
  names: [], spect: [], extra: [], primary: null,
  brightOrder: null,             // indexy setříděné podle svítivosti (pro popisky)
  galaxies: [],
  systems: new Map(),
  solIndex: 0,

  init() {
    const D = window.STAR_DATA;
    const nCat = D.x.length, nExo = EXOTIC.length;
    const n = nCat + nExo;
    this.n = n;
    this.X = new Float64Array(n); this.Y = new Float64Array(n); this.Z = new Float64Array(n);
    this.T = new Float32Array(n); this.R = new Float32Array(n); this.L = new Float32Array(n);
    this.kind = new Uint8Array(n);
    this.names = new Array(n); this.spect = new Array(n); this.extra = new Array(n);
    for (let i = 0; i < nCat; i++) {
      this.X[i] = D.x[i] * C.KM_PER_PC; this.Y[i] = D.y[i] * C.KM_PER_PC; this.Z[i] = D.z[i] * C.KM_PER_PC;
      this.T[i] = D.t[i]; this.R[i] = D.r[i]; this.L[i] = D.l[i];
      this.spect[i] = D.s[i];
    }
    for (const k in D.n) this.names[+k] = D.n[k];
    this.solIndex = this.names.indexOf('Sol');
    this.names[this.solIndex] = I18N.lang === 'cs' ? 'Slunce' : 'Sun';
    EXOTIC.forEach((e, j) => {
      const i = nCat + j;
      const g = e.ra != null ? galFromRaDec(e.ra, e.dec, e.d) : galFromLB(e.l, e.b, e.d);
      this.X[i] = g[0] * C.KM_PER_PC; this.Y[i] = g[1] * C.KM_PER_PC; this.Z[i] = g[2] * C.KM_PER_PC;
      this.names[i] = e.name; this.extra[i] = e;
      if (e.kind === 'star') { this.T[i] = e.T; this.R[i] = e.R; this.L[i] = e.L; this.spect[i] = 'M'; }
      else if (e.kind === 'ns') {
        this.kind[i] = 1; this.T[i] = e.T || 600000; this.R[i] = 12 / C.R_SUN_KM;
        this.L[i] = Math.max(e.Lsd / C.L_SUN_W, 1e-3); this.spect[i] = 'NS';
      } else {
        this.kind[i] = 2; this.T[i] = 1e4; this.R[i] = e.M * C.RS_KM_PER_MSUN / C.R_SUN_KM;
        this.L[i] = e.disk ? 1e4 * e.disk : 0; this.spect[i] = 'BH';
      }
    });
    this.findCompanions();
    // hvězda z katalogu, která je průvodcem exotického objektu (např. HDE 226868 u Cygnus X-1), se skryje do jeho soustavy
    EXOTIC.forEach((e, j) => {
      const k = this.names.indexOf(e.name);
      if (k >= 0 && k < nCat) { this.names[k] = e.name === 'Cygnus X-1' ? 'HDE 226868' : e.name + ' (opt.)'; this.primary[k] = nCat + j; }
    });
    this.brightOrder = Array.from({ length: n }, (_, i) => i)
      .sort((a, b) => this.labelRank(b) - this.labelRank(a));
    this.galaxies = GALAXIES.map(g => {
      const p = galFromLB(g.l, g.b, g.d * 1000);
      return Object.assign({}, g, { x: p[0] * C.KM_PER_PC, y: p[1] * C.KM_PER_PC, real: true });
    });
    this.galaxies.push({ name: ['Mléčná dráha', 'Milky Way'], x: GAL.GC_PC * C.KM_PER_PC, y: 0, D: 30, type: 'mw', real: true, incl: 0, rot: 0 });
  },

  labelRank(i) {
    let r = Math.log10(this.L[i] + 1e-6);
    if (this.extra[i]) r += 6;
    if (this.names[i] && !/^\d|^Gl |^GJ |^NN /.test(this.names[i])) r += 3;
    if (i === this.solIndex) r += 20;
    return r;
  },

  // dvojhvězdy: hvězdy blíž než ~600 AU sloučíme do jedné soustavy
  findCompanions() {
    const n = this.n, cell = 0.01 * C.KM_PER_PC, lim = 600 * C.KM_PER_AU;
    this.primary = new Int32Array(n).fill(-1);
    const grid = new Map();
    for (let i = 0; i < n; i++) {
      const k = Math.floor(this.X[i] / cell) + ',' + Math.floor(this.Y[i] / cell);
      if (!grid.has(k)) grid.set(k, []);
      grid.get(k).push(i);
    }
    for (const list of grid.values()) {
      if (list.length < 2) continue;
      for (let a = 0; a < list.length; a++) for (let b = a + 1; b < list.length; b++) {
        const i = list[a], j = list[b];
        if (this.primary[i] >= 0 || this.primary[j] >= 0) continue;
        if (this.kind[i] || this.kind[j]) continue;
        const d = Math.hypot(this.X[i] - this.X[j], this.Y[i] - this.Y[j], this.Z[i] - this.Z[j]);
        if (d < lim) { if (this.L[i] >= this.L[j]) this.primary[j] = i; else this.primary[i] = j; }
      }
    }
  },

  starName(i) { return this.names[i] || ('HYG ' + i); },

  // ---------- procedurální hvězdy za hranicí katalogu ----------
  procCell(cx, cy) {
    const cs = GAL.PROC_CELL_PC;
    const xc = (cx + 0.5) * cs, yc = (cy + 0.5) * cs;
    const dSun = Math.hypot(xc, yc);
    if (dSun < GAL.CATALOG_PC * 0.85) return null;
    let rho = galaxyDensity(xc, yc);
    rho *= U.clamp((dSun - GAL.CATALOG_PC * 0.85) / (GAL.CATALOG_PC * 0.3), 0, 1);
    const expected = Math.min(rho * 0.9, 12);
    const r = U.rng(U.hash(cx, cy, 77) * 4294967296);
    let count = Math.floor(expected) + (r() < expected % 1 ? 1 : 0);
    if (!count) return null;
    const out = [];
    for (let k = 0; k < count; k++) {
      const s = this.randomStar(r);
      s.id = `p${cx}_${cy}_${k}`;
      s.x = (cx + r()) * cs * C.KM_PER_PC; s.y = (cy + r()) * cs * C.KM_PER_PC;
      s.name = this.procName(cx, cy, k);
      out.push(s);
    }
    return out;
  },
  randomStar(r) {
    // zhruba počáteční funkce hmotnosti: hlavně červení trpaslíci, sem tam obr
    const u = r();
    let T, R, L, sp;
    if (u < 0.73) { T = 2600 + r() * 1300; R = 0.1 + r() * 0.5; sp = 'M'; }
    else if (u < 0.85) { T = 3900 + r() * 1300; R = 0.65 + r() * 0.3; sp = 'K'; }
    else if (u < 0.93) { T = 5200 + r() * 800; R = 0.9 + r() * 0.3; sp = 'G'; }
    else if (u < 0.97) { T = 6000 + r() * 1500; R = 1.15 + r() * 0.5; sp = 'F'; }
    else if (u < 0.99) { T = 7500 + r() * 2500; R = 1.6 + r() * 1; sp = 'A'; }
    else if (u < 0.996) { T = 10000 + r() * 20000; R = 2.5 + r() * 5; sp = 'B'; }
    else { T = 3400 + r() * 1500; R = 10 + Math.pow(r(), 3) * 600; sp = 'K/M III'; }
    L = R * R * Math.pow(T / 5772, 4);
    return { T, R, L, sp, proc: true };
  },
  procName(cx, cy, k) {
    const syl = ['ka', 'ro', 'vel', 'an', 'tis', 'mor', 'el', 'ux', 'sa', 'dri', 'on', 'quo', 'ny', 'ze', 'lar', 'thi'];
    const h = U.hash(cx, cy, k + 900) * 4294967296 >>> 0;
    const a = syl[h & 15], b = syl[(h >> 4) & 15], c = (h >> 8) & 1 ? syl[(h >> 12) & 15] : '';
    const nm = (a + b + c);
    return nm[0].toUpperCase() + nm.slice(1) + '-' + ((h >> 16) % 9000 + 1000);
  },

  // ---------- hvězdný záznam (pro výběr / UI) ----------
  starRec(id) {
    if (id[0] === 'h') {
      const i = +id.slice(1);
      const e = this.extra[i];
      return { id, idx: i, name: this.starName(i), x: this.X[i], y: this.Y[i], z: this.Z[i], T: this.T[i], R: this.R[i], L: this.L[i],
        kind: ['star', 'ns', 'bh'][this.kind[i]], sp: this.spect[i], real: true, exo: e };
    }
    const m = id.slice(1).split('_').map(Number);
    const list = this.procCell(m[0], m[1]);
    const s = list && list[m[2]];
    if (!s) return null;
    return Object.assign({ kind: 'star', real: false }, s);
  },

  // ---------- planetární soustavy ----------
  system(id) {
    if (this.systems.has(id)) return this.systems.get(id);
    const st = this.starRec(id);
    if (!st) return null;
    const sys = { id, star: st, bodies: [], companions: [], x: st.x, y: st.y };
    const exo = st.exo;
    if (st.idx === this.solIndex) this.buildSol(sys);
    else if (exo && exo.kind === 'bh') this.buildBH(sys, exo);
    else if (exo && exo.kind === 'ns') this.buildNS(sys, exo);
    else this.buildProcedural(sys);
    if (st.idx != null && !(exo && exo.comp)) { // průvodci z katalogu (dvojhvězdy)
      for (let j = 0; j < this.n; j++) if (this.primary[j] === st.idx) {
        const sep = (st.name === 'Rigil Kentaurus') ? 23.4 : 20 + U.hash(j) * 300;
        sys.companions.push({ name: this.starName(j), T: this.T[j], R: this.R[j], L: this.L[j], a: sep * C.KM_PER_AU, P: this.period(sep, st.L + this.L[j]), phase: U.hash(j, 3) * 6.28 });
      }
    }
    sys.Ltot = st.L + sys.companions.reduce((s, c) => s + c.L, 0);
    // orbitální stanice: místo pro stavby v každé soustavě (i u černé díry bez planet)
    const rs = st.kind === 'bh' ? st.R * C.R_SUN_KM : 0;
    const aSt = st.kind === 'bh' ? Math.max(rs * 200, 0.05 * C.KM_PER_AU) / C.KM_PER_AU : Math.max(0.6 * Math.sqrt(Math.max(sys.Ltot, 1e-4)), st.R * C.R_SUN_KM * 3 / C.KM_PER_AU);
    this.mkBody(sys, { id: 'station', n: [I18N.lang === 'cs' ? 'Orbitální stanice' : 'Orbital station', 'Orbital station'], type: 'station', a: aSt, R: 2, P: this.period(aSt, 0, st.kind === 'bh' ? sys.bh.M : st.kind === 'ns' ? 1.4 : U.clamp(Math.pow(Math.max(st.L, 1e-4), 0.25), 0.08, 60)), col: [0.8, 0.9, 1], dep: {} });
    this.systems.set(id, sys);
    return sys;
  },
  period(aAU, L, M) { // dny, M odhadem z L u hlavní posloupnosti
    const mass = M || U.clamp(Math.pow(Math.max(L, 1e-4), 0.25), 0.08, 60);
    return 365.25 * Math.sqrt(aAU * aAU * aAU / mass);
  },
  mkBody(sys, o, parent) {
    const b = {
      id: sys.id + ':' + o.id, sys: sys.id, name: o.n, type: o.type || 'moon', parent: parent || null,
      a: parent ? o.a : o.a * C.KM_PER_AU, R: o.R, P: o.P * 24, phase: o.phase != null ? o.phase : U.hash(U.hashStr(sys.id + o.id)) * Math.PI * 2,
      col: o.col, atm: o.atm, bands: o.bands, rings: o.rings, dep: o.dep || {}, mag: o.mag || 0, home: o.home,
      a0: o.a0 ? o.a0 * C.KM_PER_AU : 0, a1: o.a1 ? o.a1 * C.KM_PER_AU : 0, moons: [], real: o.real !== false,
    };
    sys.bodies.push(b);
    if (o.moons) for (const m of o.moons) b.moons.push(this.mkBody(sys, m, b));
    return b;
  },
  buildSol(sys) {
    for (const p of SOLAR_SYSTEM) this.mkBody(sys, p);
    sys.explored = true;
  },
  buildNS(sys, e) {
    sys.ns = e;
    if (e.planets) e.planets.forEach((p, k) => this.mkBody(sys, { id: 'p' + k, n: p.n, type: p.type, a: p.a, R: p.Rp * 6371, P: p.P, col: [0.55, 0.5, 0.6], dep: { fe: 1.5, ti: 1.2, cu: 1, si: 1 } }));
    if (e.comp) sys.companions.push({ name: e.comp.wd ? (I18N.lang === 'cs' ? 'bílý trpaslík' : 'white dwarf') : 'B', T: e.comp.T, R: e.comp.R, L: e.comp.R * e.comp.R * Math.pow(e.comp.T / 5772, 4), a: e.comp.a * C.KM_PER_AU, P: this.period(e.comp.a, 0, 1.6), phase: 1 });
    // trosky po supernově: pás kovů bohatý na těžké prvky
    this.mkBody(sys, { id: 'debris', n: [I18N.lang === 'cs' ? 'Disk trosek' : 'Debris disk', 'Debris disk'], type: 'belt', a: 1.2, a0: 0.8, a1: 1.8, R: 0, P: this.period(1.2, 0, 1.4), col: [0.6, 0.55, 0.7], dep: { fe: 2.5, ti: 2.0, cu: 2.0 } });
  },
  buildBH(sys, e) {
    sys.bh = e;
    if (e.comp) sys.companions.push({ name: (I18N.lang === 'cs' ? 'průvodce' : 'companion'), T: e.comp.T, R: e.comp.R, L: e.comp.R * e.comp.R * Math.pow(e.comp.T / 5772, 4), a: e.comp.a * C.KM_PER_AU, P: this.period(e.comp.a, 0, e.M + 1), phase: 2 });
    if (e.core) { // hvězdy S obíhající Sgr A*
      sys.sStars = [
        { name: 'S2 (S0-2)', a: 1031 * C.KM_PER_AU, e: 0.884, P: 16.05 * C.HOURS_PER_YEAR, T: 28000, R: 6.0, w: 1.2 },
        { name: 'S62', a: 740 * C.KM_PER_AU, e: 0.976, P: 9.9 * C.HOURS_PER_YEAR, T: 20000, R: 2, w: 3.9 },
        { name: 'S4711', a: 600 * C.KM_PER_AU, e: 0.768, P: 7.6 * C.HOURS_PER_YEAR, T: 18000, R: 2, w: 5.2 },
      ];
    }
  },
  buildProcedural(sys) {
    const st = sys.star;
    const known = KNOWN_EXOPLANETS[st.name];
    const r = U.rng(U.hashStr(sys.id) ^ 0x9e3779b9);
    const rStarAU = st.R * C.R_SUN_KM / C.KM_PER_AU;
    const sq = Math.sqrt(Math.max(st.L, 1e-5));
    const mass = U.clamp(Math.pow(Math.max(st.L, 1e-4), 0.25), 0.08, 60);
    const mk = (k, a, type, R, extra) => this.mkBody(sys, Object.assign({ id: 'b' + k, n: null, type, a, R, P: this.period(a, st.L, mass) }, extra));
    if (known) {
      known.forEach((p, k) => mk(k, p.a, p.type, p.Rp * 6371, { n: p.n, col: p.type === 'gas' ? [0.8, 0.65, 0.5] : [0.6, 0.45, 0.4], bands: p.type === 'gas', dep: p.type === 'gas' ? { h2: 1.5, he3: 0.6 } : { fe: 1.2, si: 1, ti: 0.6 }, mag: p.type === 'gas' ? 0.8 : 0 }));
    } else {
      const count = st.R > 20 ? Math.floor(r() * 3) : Math.floor(r() * 8);
      let a = Math.max(rStarAU * 4, 0.03 * sq) * (1 + r());
      const snow = 2.7 * sq;
      let beltDone = false;
      for (let k = 0; k < count; k++) {
        const teq = 278 * Math.pow(st.L, 0.25) / Math.sqrt(a);
        let type = 'rocky', R, col, dep, mag = 0, extra = {};
        if (a > snow && r() < 0.6) {
          type = 'gas'; R = 20000 + r() * 55000; mag = 0.1 + r() * 1.4;
          const hue = r(); col = hue < 0.5 ? [0.85, 0.72 + hue * 0.2, 0.55] : [0.45, 0.65 + hue * 0.2, 0.9];
          dep = { h2: 1 + r(), he3: 0.3 + r() * 0.8 }; extra.bands = true;
          if (r() < 0.3) extra.rings = [R * 1.3, R * (2 + r())];
        } else if (teq < 150) {
          type = 'ice'; R = 800 + r() * 4000; col = [0.75, 0.8, 0.85]; dep = { ice: 1 + r(), cu: r() * 0.6 };
        } else {
          R = 1500 + r() * 8000; const g = 0.35 + r() * 0.4; col = [g + r() * 0.3, g, g - r() * 0.15];
          dep = { fe: 0.3 + r() * 1.5, si: 0.3 + r() * 1.2, ti: r() * 1.2, cu: r() * 1 };
          if (teq < 400 && teq > 200 && r() < 0.5) extra.atm = [0.5, 0.7, 1];
        }
        const moons = [];
        if (type === 'gas') for (let m = 0, nm = Math.floor(r() * 4); m < nm; m++)
          moons.push({ id: 'm' + m, n: null, a: R * (4 + m * 4 + r() * 3), R: 400 + r() * 2200, P: 1.5 + m * 3 + r() * 4, col: [0.6 + r() * 0.3, 0.6, 0.55], dep: r() < 0.5 ? { ice: 0.5 + r() } : { fe: 0.5 + r(), si: 0.5 } });
        const b = mk(k, a, type, R, Object.assign({ col, dep, mag, moons }, extra));
        if (!beltDone && k > 0 && r() < 0.35) {
          beltDone = true;
          const ab = a * 1.35;
          this.mkBody(sys, { id: 'belt', n: null, type: 'belt', a: ab, a0: ab * 0.85, a1: ab * 1.15, R: 0, P: this.period(ab, st.L, mass), col: [0.55, 0.5, 0.45], dep: { fe: 1 + r(), cu: 0.5 + r(), ti: 0.5 + r() } });
          a = ab * 1.2;
        }
        a *= 1.5 + r() * 0.9;
      }
    }
    // pojmenování: jméno hvězdy + b, c, d...
    let li = 0;
    for (const b of sys.bodies) {
      if (b.name) continue;
      if (b.parent) { b.name = b.parent.name + ' ' + 'I II III IV V'.split(' ')[b.parent.moons.indexOf(b)]; continue; }
      b.name = b.type === 'belt' ? (I18N.lang === 'cs' ? 'Pás asteroidů ' : 'Asteroid belt ') + st.name : st.name + ' ' + 'bcdefghijk'[li++];
    }
    sys.procedural = !known;
  },

  bodyName(b) { return Array.isArray(b.name) ? b.name[I18N.lang === 'cs' ? 0 : 1] : b.name; },

  // poloha tělesa v čase (km, absolutně)
  bodyPos(sys, b, t) {
    if (b.parent) {
      const p = this.bodyPos(sys, b.parent, t);
      const ang = b.phase + 2 * Math.PI * t / b.P;
      return [p[0] + b.a * Math.cos(ang), p[1] + b.a * Math.sin(ang)];
    }
    if (b.type === 'belt') return [sys.x, sys.y];
    const ang = b.phase + 2 * Math.PI * t / b.P;
    return [sys.x + b.a * Math.cos(ang), sys.y + b.a * Math.sin(ang)];
  },
  // tok záření [W/m²] u tělesa
  fluxAt(sys, b) {
    const d = (b.parent ? b.parent.a : b.a) || 1;
    return sys.Ltot * C.L_SUN_W / (4 * Math.PI * Math.pow(d * 1000, 2));
  },

  distLy(idA, idB) {
    const a = this.starRec(idA), b = this.starRec(idB);
    return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0)) / C.KM_PER_LY;
  },
};
