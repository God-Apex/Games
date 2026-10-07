// Ekonomika: suroviny, recepty, stavby, výzkum, energie, antihmota, sondy, červí díry.
// Všechny soustavy propojené červími děrami sdílejí jeden sklad. Energie se nepřenáší, každá soustava má vlastní síť.
'use strict';

const RES = ['fe', 'cu', 'si', 'ti', 'ice', 'h2', 'he3', 'plate', 'wire', 'circuit', 'alloy', 'processor', 'supercond', 'frame', 'sail', 'rocket'];
const RAW = ['fe', 'cu', 'si', 'ti', 'ice', 'h2', 'he3'];
const RES_COLOR = { fe: '#b7a99a', cu: '#e08a4f', si: '#9fb4c9', ti: '#c9d3e0', ice: '#9fe3ff', h2: '#ff9fd0', he3: '#ffe27a',
  plate: '#d0c4b8', wire: '#f0a060', circuit: '#6fdc8c', alloy: '#a8c0ff', processor: '#4fd1c5', supercond: '#b38cff', frame: '#e6e6e6', sail: '#ffd36b', rocket: '#ff7b5c' };

// rate = výrobních cyklů za hodinu (1 továrna)
const RECIPES = {
  plate: { in: { fe: 2 }, out: { plate: 1 }, rate: 30 },
  wire: { in: { cu: 1 }, out: { wire: 2 }, rate: 30 },
  circuit: { in: { plate: 1, wire: 3, si: 1 }, out: { circuit: 1 }, rate: 15 },
  alloy: { in: { ti: 2, plate: 1 }, out: { alloy: 1 }, rate: 15 },
  processor: { in: { circuit: 2, si: 2 }, out: { processor: 1 }, rate: 6 },
  supercond: { in: { wire: 2, alloy: 1, ice: 1 }, out: { supercond: 1 }, rate: 6 },
  frame: { in: { alloy: 2, plate: 1 }, out: { frame: 1 }, rate: 6 },
  sail: { in: { alloy: 1, si: 2 }, out: { sail: 1 }, rate: 10, tech: 'dyson' },
  rocket: { in: { frame: 2, processor: 2, supercond: 1, h2: 10 }, out: { rocket: 1 }, rate: 2, tech: 'shell' },
};

// where: kde se dá stavět. pw: spotřeba [W] (záporná = výroba). unique: max 1 na soustavu
const SOLID = b => b.type !== 'gas' && b.type !== 'station';
const ANY = b => true;
const BUILDINGS = {
  hq: { cost: null, pw: -2e13, where: () => false, icon: '★' },
  mine: { cost: { plate: 10, circuit: 3 }, pw: 2e12, where: b => SOLID(b) && ['fe', 'cu', 'si', 'ti', 'ice', 'he3'].some(r => b.dep[r]), icon: '⛏' },
  gas: { cost: { plate: 20, circuit: 5, alloy: 5 }, pw: 3e12, where: b => b.type === 'gas', icon: '◍' },
  solar: { cost: { plate: 8, wire: 10, si: 15 }, pw: 0, where: ANY, icon: '☀' },
  assembler: { cost: { plate: 15, circuit: 6 }, pw: 1e12, where: b => b.type !== 'gas', icon: '⚙', recipe: true },
  lab: { cost: { plate: 20, circuit: 10, wire: 10 }, pw: 2e12, where: b => b.type !== 'gas', icon: '⚗' },
  fusion: { cost: { alloy: 25, supercond: 10, processor: 4 }, pw: -1e14, where: b => b.type !== 'gas', icon: '⚛', tech: 'fusion' },
  ejector: { cost: { alloy: 30, supercond: 10, processor: 6 }, pw: 5e13, where: SOLID, icon: '➶', tech: 'dyson' },
  receiver: { cost: { alloy: 30, supercond: 20, processor: 10 }, pw: 0, where: SOLID, icon: '◎', tech: 'dyson' },
  silo: { cost: { frame: 40, processor: 20, supercond: 20 }, pw: 1e14, where: SOLID, icon: '🚀', tech: 'shell' },
  collector: { cost: { alloy: 40, supercond: 30, processor: 10 }, pw: 1e13, where: b => b.mag > 0, icon: '∿', tech: 'magnet' },
  trap: { cost: { alloy: 15, supercond: 20, processor: 5 }, pw: 1e12, where: b => b.type !== 'gas', icon: '⌾', tech: 'magnet' },
  accelerator: { cost: { frame: 60, supercond: 100, processor: 40 }, pw: 1e20, where: b => b.type !== 'gas', icon: '◉', tech: 'accel' },
  dock: { cost: { frame: 50, processor: 30, supercond: 30 }, pw: 5e13, where: b => b.type !== 'gas', icon: '⚓', tech: 'probe' },
  gate: { cost: { frame: 150, processor: 60, supercond: 120, alloy: 100 }, pw: 2e14, where: b => b.type === 'station', icon: '◌', tech: 'probe', unique: true },
  pcollector: { cost: { frame: 80, alloy: 120, supercond: 100, processor: 50 }, pw: 1e15, where: (b, sys) => !!sys.ns, icon: '✺', tech: 'shield' },
  acollector: { cost: { frame: 200, supercond: 200, processor: 100 }, pw: 1e15, where: (b, sys) => !!(sys.bh && sys.bh.disk), icon: '⊛', tech: 'horizon' },
  penrose: { cost: { frame: 300, supercond: 300, processor: 150 }, pw: -5e22, where: (b, sys) => !!sys.bh && b.type === 'station', icon: '◐', tech: 'horizon' },
};
const BUILD_ORDER = ['mine', 'gas', 'solar', 'assembler', 'lab', 'fusion', 'ejector', 'receiver', 'silo', 'collector', 'trap', 'accelerator', 'dock', 'gate', 'pcollector', 'acollector', 'penrose'];

const TECH = {
  fusion: { cost: 60, req: [] },
  automation: { cost: 150, req: [] },
  dyson: { cost: 250, req: ['fusion'] },
  magnet: { cost: 400, req: ['fusion'] },
  probe: { cost: 600, req: ['magnet'] },
  accel: { cost: 900, req: ['dyson', 'magnet'] },
  shell: { cost: 1500, req: ['dyson', 'automation'] },
  automation2: { cost: 2000, req: ['automation'] },
  sail_drive: { cost: 2000, req: ['probe', 'dyson'] },
  accel2: { cost: 3000, req: ['accel'] },
  shield: { cost: 3500, req: ['probe'] },
  am_drive: { cost: 5000, req: ['sail_drive', 'accel'] },
  horizon: { cost: 8000, req: ['shield'] },
  accel3: { cost: 12000, req: ['accel2'] },
};
const TECH_ORDER = Object.keys(TECH);

const ECO = {
  SAIL_SHARE: 1e-5,          // jedna plachta zachytí 1/100 000 svítivosti Slunce
  NODE_SHARE: 1e-4,          // jeden uzel sféry 1/10 000
  DYSON_EFF: 0.5,
  SAIL_HALFLIFE_H: 20 * C.HOURS_PER_YEAR,
  RECEIVER_CAP: 2e22,
  SOLAR_AREA_M2: 1e11,       // solární prstenec 100 000 km²
  SOLAR_EFF: 0.25,
  FUSION_HE3: 1,             // t/h
  MINE_RATE: 20, GAS_RATE: 30,
  LAB_IN: 2, LAB_RP: 10,
  EJECT_RATE: 20, SILO_RATE: 3,
  TRAP_CAP: 1,               // kg antihmoty na past
  COLLECTOR_KG: 5e-4,        // kg/h při síle pole jako Jupiter
  ACCEL_EFF: 1e-9,
  WORMHOLE_KG_PER_LY: 0.01,
  PROBE_COST: { frame: 20, processor: 20, supercond: 20, alloy: 40, he3: 50 },
};

const Game = {
  s: null,          // uložitelný stav
  rates: {},        // změna skladu za hodinu (poslední tik)
  bodyRates: {},    // bodyId -> {surovina: vytěženo za hodinu}
  power: {},        // sysId -> {supply, demand, sat, dyson}
  totalPower: 0,

  newGame(sandbox) {
    const home = 'h' + Galaxy.solIndex;
    this.s = {
      v: 1, t: 0, speed: 1, sandbox: !!sandbox, dep: {}, qDone: [],
      store: { fe: 200, cu: 120, si: 150, ti: 60, ice: 40, h2: 0, he3: 0, plate: 300, wire: 200, circuit: 80, alloy: 40, processor: 0, supercond: 0, frame: 0, sail: 0, rocket: 0 },
      am: 0, rp: 0, tech: {}, research: null,
      sys: {}, net: [home], probes: [], log: [], explored: [home],
      stats: { maxK: 0.7 },
    };
    const st = this.sysState(home);
    st.b.push({ t: 'hq', body: home + ':earth', n: 1 });
    if (sandbox) for (const t of TECH_ORDER) this.s.tech[t] = true;
    this.log(sandbox ? 'ev.sandbox' : 'ev.start');
  },

  sysState(id) {
    if (!this.s.sys[id]) this.s.sys[id] = { b: [], sails: 0, nodes: 0, gate: false };
    return this.s.sys[id];
  },
  log(key, args) {
    this.s.log.unshift({ t: this.s.t, k: key, a: args || [] });
    if (this.s.log.length > 80) this.s.log.length = 80;
    if (typeof UI !== 'undefined' && UI.$) UI.toast(I18N.t(key, ...(args || [])));
  },
  has(tech) { return !!this.s.tech[tech]; },
  connected(id) { return this.s.net.includes(id); },
  explored(id) { return this.s.explored.includes(id); },

  // ---------- ložiska ----------
  // zásoba podle bohatosti a velikosti tělesa; plynní obři jsou prakticky nevyčerpatelní
  reserveInit(b, r) {
    const v = b.dep[r] || 0;
    if (b.type === 'gas' && (r === 'h2' || r === 'he3')) return Infinity;
    if (b.type === 'belt') return v * 2e7;
    return v * 3e5 * Math.pow(Math.max(0.3, b.R / 1000), 1.5);
  },
  depLeft(b, r) {
    const d = this.s.dep[b.id];
    return d && d[r] != null ? d[r] : this.reserveInit(b, r);
  },
  extract(b, r, want) {
    const left = this.depLeft(b, r);
    if (left === Infinity) return want;
    const got = Math.min(want, left);
    (this.s.dep[b.id] = this.s.dep[b.id] || {})[r] = left - got;
    if (left > 0 && left - got <= 0) this.log('ev.depleted', ['res.' + r, Galaxy.bodyName(b)]);
    return got;
  },
  // počet staveb v síti (volitelně jen na tělese s klíčem, např. 'moon', a s receptem)
  count(type, bodyKey, recipe) {
    let n = 0;
    for (const id of this.s.net) for (const e of (this.s.sys[id] || { b: [] }).b)
      if (e.t === type && (!bodyKey || e.body.endsWith(':' + bodyKey)) && (!recipe || e.r === recipe)) n += e.n;
    return n;
  },
  missing(cost, mult = 1) {
    return Object.entries(cost).filter(([r, v]) => (this.s.store[r] || 0) < v * mult - 1e-9).map(([r, v]) => [r, v * mult - (this.s.store[r] || 0)]);
  },

  canAfford(cost, mult = 1) {
    for (const r in cost) if ((this.s.store[r] || 0) < cost[r] * mult - 1e-9) return false;
    return true;
  },
  pay(cost, mult = 1) { for (const r in cost) this.s.store[r] -= cost[r] * mult; },

  buildableOn(type, body, sys) {
    const B = BUILDINGS[type];
    if (!B.cost) return false;
    if (B.tech && !this.has(B.tech)) return false;
    if (!B.where(body, sys)) return false;
    return true;
  },
  build(type, body, recipe, count = 1) {
    const sys = Galaxy.system(body.sys);
    const B = BUILDINGS[type];
    if (!this.connected(body.sys) || !this.buildableOn(type, body, sys)) return false;
    const st = this.sysState(body.sys);
    if (B.unique) {
      if (st.b.some(x => x.t === type)) return false;
      count = 1;
    }
    let n = 0;
    while (n < count && this.canAfford(B.cost)) { this.pay(B.cost); n++; }
    if (!n) return false;
    let e = st.b.find(x => x.t === type && x.body === body.id && (x.r || null) === (recipe || null));
    if (!e) { e = { t: type, body: body.id, n: 0 }; if (recipe) e.r = recipe; st.b.push(e); }
    e.n += n;
    if (type === 'gate') st.gate = true;
    return n;
  },
  demolish(sysId, entry, count = 1) {
    const B = BUILDINGS[entry.t];
    if (!B.cost) return;
    const k = Math.min(count, entry.n);
    for (const r in B.cost) this.s.store[r] += B.cost[r] * k * 0.5; // polovina materiálu zpět
    entry.n -= k;
    const st = this.sysState(sysId);
    if (entry.n <= 0) st.b.splice(st.b.indexOf(entry), 1);
    if (entry.t === 'gate' && entry.n <= 0) st.gate = false;
  },

  // ---------- výzkum ----------
  techAvailable(id) { return !this.has(id) && TECH[id].req.every(r => this.has(r)); },
  startResearch(id) { if (this.techAvailable(id)) this.s.research = id; },

  // ---------- energie ----------
  bodyById(sys, id) { return sys.bodies.find(b => b.id === id); },
  dysonPower(sys, st) {
    const share = st.sails * ECO.SAIL_SHARE + st.nodes * ECO.NODE_SHARE;
    const cov = Math.min(1, share / Math.max(sys.Ltot, 1e-9));
    return { cov, watts: cov * sys.Ltot * C.L_SUN_W * ECO.DYSON_EFF, sailCov: Math.min(1, st.sails * ECO.SAIL_SHARE / Math.max(sys.Ltot, 1e-9)) };
  },
  accelEff() { return ECO.ACCEL_EFF * (this.has('accel2') ? 10 : 1) * (this.has('accel3') ? 10 : 1); },
  speedMult() { return (this.has('automation') ? 1.5 : 1) * (this.has('automation2') ? 2 : 1); },

  // ---------- simulace ----------
  tick(dt) {
    const S = this.s, store = S.store;
    const delta = {}; RES.forEach(r => delta[r] = 0);
    let amDelta = 0, rpDelta = 0, total = 0, totSupply = 0, totDemand = 0;
    const amSrc = {}, rpSrc = {};
    let labStarved = false;
    const acc = (map, t, body, n, perH) => { const k = t + '|' + body; const o = map[k] || (map[k] = { t, body, n: 0, v: 0 }); o.n += n; o.v += perH; };
    const take = (r, want) => { const got = Math.min(want, Math.max(0, store[r])); store[r] -= got; delta[r] -= got; return got; };
    const give = (r, v) => { store[r] += v; delta[r] += v; };
    let trapCap = 0;
    this.power = {};
    if (S.sandbox) for (const r of RES) store[r] = 1e9;
    const br = this.bodyRates = {};
    const mined = (b, r, v) => { const got = this.extract(b, r, v); give(r, got); (br[b.id] = br[b.id] || {})[r] = ((br[b.id] || {})[r] || 0) + got / dt; };
    const decay = Math.pow(0.5, dt / ECO.SAIL_HALFLIFE_H);
    const autom = this.speedMult();

    for (const id of S.net) {
      const st = S.sys[id];
      if (!st) continue;
      const sys = Galaxy.system(id);
      st.sails *= decay;
      const dy = this.dysonPower(sys, st);
      // --- nabídka energie ---
      let supply = 0, recvCap = 0, demand = 0, trapDemand = 0;
      // rozpis pro bublinu u ukazatele energie: zdroje (typ + těleso) a spotřebitelé (typ)
      const src = {}, cons = {};
      let noFuel = false;
      const addSrc = (t, body, n, w) => { if (w <= 0) return; const key = t + '|' + body; const o = src[key] || (src[key] = { t, body, n: 0, w: 0 }); o.n += n; o.w += w; };
      const addCons = (t, n, w) => { const o = cons[t] || (cons[t] = { t, n: 0, w: 0 }); o.n += n; o.w += w; };
      for (const e of st.b) {
        const B = BUILDINGS[e.t];
        if (e.t === 'solar') { const w = e.n * Galaxy.fluxAt(sys, this.bodyById(sys, e.body)) * ECO.SOLAR_AREA_M2 * ECO.SOLAR_EFF; supply += w; addSrc('solar', e.body, e.n, w); }
        else if (e.t === 'fusion') { const need = e.n * ECO.FUSION_HE3 * dt; const got = take('he3', need); const w = -B.pw * e.n * (need ? got / need : 0); supply += w; addSrc('fusion', e.body, e.n, w); if (w < -B.pw * e.n * 0.99) noFuel = true; }
        else if (e.t === 'receiver') recvCap += e.n * ECO.RECEIVER_CAP;
        else if (B.pw < 0) { supply += -B.pw * e.n; addSrc(e.t, e.body, e.n, -B.pw * e.n); }
        else if (e.t === 'trap') { trapDemand += B.pw * e.n; trapCap += e.n * ECO.TRAP_CAP; addCons('trap', e.n, B.pw * e.n); }
        else if (B.pw > 0) { demand += B.pw * e.n; addCons(e.t, e.n, B.pw * e.n); }
      }
      const dysonUsed = Math.min(dy.watts, recvCap);
      supply += dysonUsed;
      if (dysonUsed > 0) addSrc('dyson', '', st.b.filter(e => e.t === 'receiver').reduce((a, e) => a + e.n, 0), dysonUsed);
      // pasti mají přednost; když nestačí ani na ně, antihmota uniká
      const trapSat = trapDemand ? Math.min(1, supply / trapDemand) : 1;
      const rest = Math.max(0, supply - trapDemand);
      const sat = demand ? Math.min(1, rest / demand) : 1;
      this.power[id] = { supply, demand: demand + trapDemand, sat, trapSat, dyson: dy, dysonUsed, recvCap,
        src: Object.values(src).sort((a, b) => b.w - a.w), cons: Object.values(cons).sort((a, b) => b.w - a.w), noFuel };
      total += supply + (dy.watts - dysonUsed);
      totSupply += supply; totDemand += demand + trapDemand;
      if (trapSat < 0.999 && S.am > 0) this.trapFailure(id, st, 1 - trapSat, dt);

      // --- výroba ---
      const order = ['hq', 'mine', 'gas', 'assembler', 'lab', 'ejector', 'silo', 'collector', 'accelerator', 'pcollector', 'acollector'];
      const entries = st.b.slice().sort((a, b) => order.indexOf(a.t) - order.indexOf(b.t));
      for (const e of entries) {
        const body = this.bodyById(sys, e.body);
        const k = e.n * sat * dt;
        switch (e.t) {
          case 'hq': for (const r of ['fe', 'cu', 'si']) give(r, 10 * dt); rpDelta += 3 * dt; acc(rpSrc, 'hq', e.body, 1, 3); break;
          case 'mine': for (const r in body.dep) if (r !== 'h2' || body.type !== 'gas') mined(body, r, ECO.MINE_RATE * body.dep[r] * k * autom); break;
          case 'gas': for (const r in body.dep) if (r === 'h2' || r === 'he3') mined(body, r, ECO.GAS_RATE * body.dep[r] * k * autom); break;
          case 'assembler': this.craft(RECIPES[e.r], k * autom, take, give); break;
          case 'lab': { const need = ECO.LAB_IN * k; const got = take('circuit', need); const v = ECO.LAB_RP * (need ? got / need : 0) * e.n * sat * dt; rpDelta += v; acc(rpSrc, 'lab', e.body, e.n, v / dt); if (need && got < need * 0.99) labStarved = true; break; }
          case 'ejector': { const got = take('sail', ECO.EJECT_RATE * k); st.sails += got; break; }
          case 'silo': { const got = take('rocket', ECO.SILO_RATE * k); st.nodes += got; break; }
          case 'collector': { const v = ECO.COLLECTOR_KG * body.mag * k; amDelta += v; acc(amSrc, e.t, e.body, e.n, v / dt); break; }
          case 'accelerator': { const v = BUILDINGS.accelerator.pw * this.accelEff() / C.C2 * 3600 * k; amDelta += v; acc(amSrc, e.t, e.body, e.n, v / dt); break; }
          case 'pcollector': { const v = 0.05 * Math.pow(sys.ns.Lsd / 1e27, 0.25) * k; amDelta += v; acc(amSrc, e.t, e.body, e.n, v / dt); break; }
          case 'acollector': { const v = 0.5 * sys.bh.disk * k; amDelta += v; acc(amSrc, e.t, e.body, e.n, v / dt); break; }
        }
      }
      // limit plných obalů: víc než 100 % pokrytí nemá smysl
      const maxShare = sys.Ltot;
      if (st.nodes * ECO.NODE_SHARE > maxShare) st.nodes = maxShare / ECO.NODE_SHARE;
      if (st.nodes * ECO.NODE_SHARE + st.sails * ECO.SAIL_SHARE > maxShare) st.sails = Math.max(0, (maxShare - st.nodes * ECO.NODE_SHARE) / ECO.SAIL_SHARE);
    }
    // antihmota: bez pastí se nedá skladovat
    S.amCap = trapCap;
    S.am = Math.min(trapCap, S.am + amDelta);
    if (S.sandbox) { S.amCap = Math.max(trapCap, 1e4); S.am = S.amCap; }
    // výzkum
    if (S.research) {
      S.rp += rpDelta;
      const T = TECH[S.research];
      if (S.rp >= T.cost) { S.rp -= T.cost; S.tech[S.research] = true; this.log('ev.tech', ['tech.' + S.research]); S.research = null; }
    } else S.rp += rpDelta;
    // sondy
    for (const p of S.probes.slice()) if (S.t + dt >= p.arrive) this.probeArrived(p);
    S.t += dt;
    this.totalPower = total;
    this.totalSupply = totSupply; this.totalDemand = totDemand;
    this.amSrc = Object.values(amSrc).sort((a, b) => b.v - a.v);
    this.rpSrc = Object.values(rpSrc).sort((a, b) => b.v - a.v);
    this.labStarved = labStarved;
    this.amWasted = S.am >= trapCap - 1e-12 && amDelta > 0;
    const K = U.kardashev(total);
    if (K > S.stats.maxK + 0.1 - 1e-9 && S.t > 1) { S.stats.maxK = Math.floor(K * 10) / 10; this.log('ev.kardashev', [S.stats.maxK.toFixed(1)]); }
    for (const r of RES) this.rates[r] = U.lerp(this.rates[r] || 0, delta[r] / dt, Math.min(1, dt / 2));
    this.rates.am = U.lerp(this.rates.am || 0, amDelta / dt, Math.min(1, dt / 2));
    this.rates.rp = rpDelta / dt;
  },
  craft(rc, cycles, take, give) {
    if (!rc || cycles <= 0) return;
    let f = 1;
    const want = rc.rate * cycles;
    for (const r in rc.in) f = Math.min(f, (this.s.store[r] || 0) / (rc.in[r] * want));
    f = U.clamp(f, 0, 1);
    if (f <= 0) return;
    for (const r in rc.in) take(r, rc.in[r] * want * f);
    for (const r in rc.out) give(r, rc.out[r] * want * f);
  },
  trapFailure(id, st, frac, dt) {
    const lost = this.s.am * Math.min(1, frac * dt * 0.5);
    this.s.am -= lost;
    if (lost > 1e-4 && (!this._lastBoom || this.s.t - this._lastBoom > 24)) {
      this._lastBoom = this.s.t;
      // anihilace 1 g = 1,8·10^14 J (hmota + antihmota) ~ 43 kilotun TNT
      const victim = st.b.filter(e => BUILDINGS[e.t].cost && e.t !== 'trap');
      if (victim.length) { const v = victim[Math.floor(Math.random() * victim.length)]; v.n -= 1; if (v.n <= 0) st.b.splice(st.b.indexOf(v), 1); }
      this.log('ev.boom', [U.mass(lost), U.si(lost * 2 * C.C2, 'J')]);
    }
  },

  // ---------- sondy a červí díry ----------
  probeSpeeds() {
    const v = [];
    if (this.has('probe')) v.push({ id: 'fusion', c: 0.1 });
    if (this.has('sail_drive')) v.push({ id: 'sail', c: 0.2 });
    if (this.has('am_drive')) v.push({ id: 'am', c: 0.5, am: 0.02 });
    return v;
  },
  docks() { return this.s.net.filter(id => this.s.sys[id] && this.s.sys[id].b.some(e => e.t === 'dock')); },
  nearestDock(targetId) {
    let best = null, bd = Infinity;
    for (const d of this.docks()) { const ly = Galaxy.distLy(d, targetId); if (ly < bd) { bd = ly; best = d; } }
    return best ? { from: best, ly: bd } : null;
  },
  launchProbe(targetId, speed) {
    const nd = this.nearestDock(targetId);
    if (!nd || this.s.probes.some(p => p.to === targetId) || this.explored(targetId)) return false;
    if (!this.canAfford(ECO.PROBE_COST)) return false;
    if (speed.am && this.s.am < speed.am) return false;
    this.pay(ECO.PROBE_COST);
    if (speed.am) this.s.am -= speed.am;
    const hours = this.s.sandbox ? 1 : nd.ly / speed.c * C.HOURS_PER_YEAR;
    this.s.probes.push({ from: nd.from, to: targetId, c: speed.c, depart: this.s.t, arrive: this.s.t + hours, ly: nd.ly });
    this.log('ev.probe', [Galaxy.starRec(targetId).name, U.duration(hours)]);
    return true;
  },
  probeArrived(p) {
    this.s.probes.splice(this.s.probes.indexOf(p), 1);
    if (!this.s.explored.includes(p.to)) this.s.explored.push(p.to);
    const st = this.sysState(p.to);
    st.gate = true; // sonda nese soupravu protější brány
    const sys = Galaxy.system(p.to);
    st.b = st.b.filter(e => e.t !== 'gate');
    st.b.push({ t: 'gate', body: sys.bodies.find(b => b.type === 'station').id, n: 1 });
    this.log('ev.arrive', [sys.star.name]);
  },
  wormholeCost(targetId) {
    let best = Infinity, from = null;
    for (const id of this.s.net) if (this.s.sys[id] && this.s.sys[id].gate) {
      const ly = Galaxy.distLy(id, targetId);
      if (ly < best) { best = ly; from = id; }
    }
    return from ? { from, ly: best, kg: best * ECO.WORMHOLE_KG_PER_LY } : null;
  },
  openWormhole(targetId) {
    const st = this.s.sys[targetId];
    if (!st || !st.gate || this.connected(targetId)) return false;
    const c = this.wormholeCost(targetId);
    if (!c || this.s.am < c.kg) return false;
    this.s.am -= c.kg;
    this.s.net.push(targetId);
    (this.s.links = this.s.links || []).push([c.from, targetId]);
    this.log('ev.wormhole', [Galaxy.starRec(targetId).name, U.mass(c.kg)]);
    return true;
  },

  // ---------- uložení ----------
  save() { try { localStorage.setItem('galciv-save-v1', JSON.stringify(this.s)); return true; } catch (e) { return false; } },
  load() {
    try {
      const j = localStorage.getItem('galciv-save-v1');
      if (!j) return false;
      this.s = JSON.parse(j);
      this.s.dep = this.s.dep || {}; this.s.qDone = this.s.qDone || [];   // starší uložené hry
      return true;
    } catch (e) { return false; }
  },
};
