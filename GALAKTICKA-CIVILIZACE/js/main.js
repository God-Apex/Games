// Hlavní smyčka, kamera (plynulý zoom přes ~25 řádů), ovládání, lety mezi objekty.
'use strict';

const Main = {
  cam: { x: 0, y: 0, z: 30, d: 0 },
  zoomTarget: null, zoomAnchor: null,
  sel: null, hover: null, follow: null,
  fly: null, speed: 1, prevSpeed: 1, depthTarget: null,
  realT: 0, emptiness: 0, fps: 60, frameMs: 16.7, _qT: 0, _goodT: 0,
  Z_MIN: 0.02, Z_MAX: 3e24,

  start() {
    Galaxy.init();
    Renderer.init(document.getElementById('gl'), document.getElementById('ov'));
    const fresh = !Game.load();
    if (fresh) Game.newGame();
    UI.init();
    if (fresh) setTimeout(() => document.getElementById('help').classList.add('show'), 9000);
    this.bindInput();
    // úvodní záběr: od Země ven do Sluneční soustavy
    const earth = this.findBody('h' + Galaxy.solIndex, 'earth');
    const p = Galaxy.bodyPos(Galaxy.system(earth.sys), earth, Game.s.t);
    this.cam = { x: p[0], y: p[1], z: 25, d: 0 };
    this.select({ type: 'body', body: earth, key: earth.id });
    this.follow = this.sel;
    setTimeout(() => this.flyTo(() => [0, 0, 0], 2.2e7 / Renderer.dpr, 7), 1200);
    setInterval(() => Game.save(), 60000);
    setInterval(() => this.computeEmptiness(), 500);
    window.addEventListener('beforeunload', () => Game.save());
    let last = performance.now();
    const loop = now => {
      const raw = (now - last) / 1000; last = now;
      const dt = Math.min(0.1, raw);
      if (raw < 0.5) this.measure(raw);
      this.realT += dt;
      this.update(dt);
      Renderer.frame(this.cam, this.realT, Game.s.t, this.sel, this.hover);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  },

  // plynulost: klouzavý průměr délky snímku; v režimu auto se podle něj mění rozlišení
  measure(raw) {
    this.frameMs = U.lerp(this.frameMs, raw * 1000, 0.05);
    this.fps = 1000 / this.frameMs;
    if (Renderer.quality !== 'auto') return;
    this._qT += raw;
    if (this._qT < 2) return;
    this._qT = 0;
    const R = Renderer;
    if (this.frameMs > 30 && R.autoScale > 0.5) { R.autoScale -= 0.25; this._goodT = 0; R.resize(); }
    else if (this.frameMs < 18) { this._goodT += 2; if (this._goodT >= 8 && R.autoScale < 1) { R.autoScale += 0.25; this._goodT = 0; R.resize(); } }
    else this._goodT = 0;
  },

  findBody(sysId, key) { return Galaxy.system(sysId).bodies.find(b => b.id.endsWith(':' + key)); },

  // hledání objektu pod kurzorem prochází všechny hvězdy, proto nejvýš 20× za sekundu
  updateHover() {
    const ev = this._hoverEv, now = performance.now();
    if (!ev || now - (this._hoverT || 0) < 50) return;
    this._hoverT = now; this._hoverEv = null;
    const h = Renderer.pick(ev.p[0], ev.p[1], this.cam, Game.s.t);
    this.hover = h;
    document.getElementById('ov').style.cursor = h ? 'pointer' : 'default';
    const tip = document.getElementById('tip');
    if (h) {
      tip.innerHTML = UI.tipHtml(h);
      tip.style.left = (ev.cx + 14) + 'px'; tip.style.top = (ev.cy + 10) + 'px'; tip.classList.add('show');
    } else tip.classList.remove('show');
  },

  update(dt) {
    this.updateHover();
    // simulace
    const hours = dt * this.speed;
    if (hours > 0) {
      const steps = Math.min(60, Math.ceil(hours / 2));
      for (let i = 0; i < steps; i++) Game.tick(hours / steps);
    }
    // let kamery
    const cam = this.cam;
    if (this.fly) {
      const f = this.fly;
      f.t += dt;
      const e = U.clamp(f.t / f.dur, 0, 1);
      const to = f.target();
      const k = Math.floor(e * 64), fr = e * 64 - k;
      const u = k >= 64 ? 1 : U.lerp(f.u[k], f.u[k + 1], fr);
      const lz = U.lerp(f.lz0, f.lz1, e) + f.bump * Math.sin(Math.PI * e);
      cam.z = Math.exp(lz);
      cam.x = U.lerp(f.x0, to[0], u); cam.y = U.lerp(f.y0, to[1], u);
      if (to[2] != null) cam.d = U.lerp(f.d0, to[2], u);
      if (e >= 1) { this.fly = null; this.zoomTarget = null; }
    } else {
      if (this.follow) {
        const p = this.objPos(this.follow);
        if (p) { cam.x = p[0]; cam.y = p[1]; if (p[2] != null) cam.d = p[2]; }
      }
      if (this.depthTarget != null && !this.follow) {
        cam.d = U.lerp(cam.d || 0, this.depthTarget, Math.min(1, dt * 5));
        if (Math.abs(cam.d - this.depthTarget) < 1) this.depthTarget = null;
      }
      if (this.zoomTarget) {
        const lz = Math.log(cam.z), lt = Math.log(this.zoomTarget);
        const nz = Math.exp(U.lerp(lz, lt, Math.min(1, dt * 12)));
        if (this.zoomAnchor && !this.follow) {
          const [ax, ay] = this.zoomAnchor;
          const [wx, wy] = Renderer.toWorld(ax, ay, cam);
          cam.z = nz;
          const [wx2, wy2] = Renderer.toWorld(ax, ay, cam);
          cam.x += wx - wx2; cam.y += wy - wy2;
        } else cam.z = nz;
        if (Math.abs(lz - lt) < 0.002) this.zoomTarget = null;
      }
    }
  },

  objPos(o) {
    if (!o) return null;
    if (o.type === 'star') { const s = Galaxy.starRec(o.id); return s && [s.x, s.y, s.z || 0]; }
    if (o.type === 'body') { const sys = Galaxy.system(o.body.sys); const sz = sys.star.z || 0; if (o.body.type === 'belt') return [sys.x, sys.y, sz]; const p = Galaxy.bodyPos(sys, o.body, Game.s.t); return [p[0], p[1], sz]; }
    if (o.type === 'galaxy') return [o.g.x, o.g.y, 0];
    return null;
  },
  objZoom(o) {
    const dpr = Renderer.dpr, H = Renderer.H;
    if (o.type === 'body') {
      const b = o.body;
      if (b.type === 'belt') return b.a1 * 2.4 / H;
      if (b.type === 'station') return Math.max(b.a * 0.3, 2e5) / H * 4;
      return Math.max(b.R * 7 / H, 0.05);
    }
    if (o.type === 'star') {
      const s = Galaxy.starRec(o.id);
      const sys = Galaxy.system(o.id);
      if (Game.explored(o.id) || !sys.procedural) {
        const far = sys.bodies.filter(b => !b.parent && b.type !== 'station').reduce((m, b) => Math.max(m, b.type === 'belt' ? b.a1 : b.a), 0);
        if (far) return Math.min(far * 2.4 / H, 3e10);
      }
      if (s.kind === 'bh') return Math.max(s.R * C.R_SUN_KM * 120 / H, 0.5);
      if (s.kind === 'ns') return 2e7 / dpr;
      return Math.max(s.R * C.R_SUN_KM * 14 / H, 2);
    }
    if (o.type === 'galaxy') return (o.g.type === 'mw' ? 36000 : o.g.D * 1000 * 1.6) * C.KM_PER_PC / H;
    return this.cam.z;
  },

  select(o) { this.sel = o; UI.lastInfo = ''; },
  flyToSel() { if (this.sel) { const o = this.sel; this.flyTo(() => this.objPos(o), this.objZoom(o)); this.follow = o.type === 'body' ? o : null; } },

  // plynulý let: oddálí se, aby byly vidět oba konce, posun hlavně v oddálení
  flyTo(target, z1, dur) {
    const cam = this.cam;
    const to = target();
    const d = Math.hypot(to[0] - cam.x, to[1] - cam.y);
    const lz0 = Math.log(cam.z), lz1 = Math.log(U.clamp(z1, this.Z_MIN, this.Z_MAX));
    const zMid = d / (Renderer.W * 0.5);
    const bump = Math.max(0, Math.log(Math.max(zMid, 1e-9)) - Math.max(lz0, lz1));
    const u = [0]; let acc = 0;
    for (let k = 1; k <= 64; k++) { const e = (k - 0.5) / 64; acc += Math.exp(U.lerp(lz0, lz1, e) + bump * Math.sin(Math.PI * e)); u.push(acc); }
    for (let k = 1; k <= 64; k++) u[k] /= acc || 1;
    const span = Math.abs(lz1 - lz0) / Math.LN10 + bump * 2 / Math.LN10;
    this.depthTarget = null;
    this.fly = { t: 0, dur: dur || U.clamp(0.9 + span * 0.22, 0.8, 6), x0: cam.x, y0: cam.y, d0: cam.d || 0, lz0, lz1, bump, u, target };
    this.follow = null;
  },

  quick(k) {
    const sol = 'h' + Galaxy.solIndex, H = Renderer.H;
    if (k === 'earth') { const e = this.findBody(sol, 'earth'); this.select({ type: 'body', body: e, key: e.id }); this.flyToSel(); }
    else if (k === 'solar') { this.select({ type: 'star', id: sol, key: sol }); this.flyTo(() => [0, 0, 0], 70 * C.KM_PER_AU / H); }
    else if (k === 'local') this.flyTo(() => [0, 0, 0], 40 * C.KM_PER_LY / H);
    else if (k === 'galaxy') this.flyTo(() => [GAL.GC_PC * C.KM_PER_PC * 0.5, 0, 0], 120000 * C.KM_PER_LY / H);
    else if (k === 'universe') this.flyTo(() => [0, 0, 0], 1.2e11 * C.KM_PER_LY / H, 7);
  },

  setSpeed(s) { if (s === 0 && this.speed === 0) s = this.prevSpeed || 1; if (s) this.prevSpeed = s; this.speed = s; },

  skipTo(tEnd) {
    const total = tEnd - Game.s.t + 0.01;
    if (total <= 0) return;
    const steps = Math.min(4000, Math.ceil(total / 1));
    for (let i = 0; i < steps; i++) Game.tick(total / steps);
    UI.toast(I18N.t('ui.skipDone', U.duration(total)));
    UI.lastInfo = '';
  },

  // při přibližování kamera sjede do hloubky hvězdy pod kurzorem, aby z vrstvy nevypadla
  focusDepth(px, py) {
    const G = Galaxy, cam = this.cam, z = cam.z, W = Renderer.W, H = Renderer.H, R = Renderer;
    const zl = R.slab(cam), lim = 90 * R.dpr;
    let best = -1, bs = Infinity;
    for (let i = 0; i < G.n; i++) {
      const sx = (G.X[i] - cam.x) / z + W / 2, dx = sx - px;
      if (dx > lim || dx < -lim) continue;
      const dy = H / 2 - (G.Y[i] - cam.y) / z - py;
      if (dy > lim || dy < -lim) continue;
      const f = R.slabFade(G.Z[i], cam, zl);
      if (f < 0.05) continue;
      const sc = Math.hypot(dx, dy) - Math.log10(G.L[i] + 1e-3) * 4 * R.dpr - f * 20 * R.dpr;
      if (sc < bs) { bs = sc; best = i; }
    }
    if (best >= 0) this.depthTarget = G.Z[best];
  },

  computeEmptiness() {
    const cam = this.cam, z = cam.z;
    this.emptiness = 0;
    if (z < 2e5 || z > 2e12 || this.fly) return;
    const G = Galaxy;
    let best = Infinity;
    for (let i = 0; i < G.n; i++) { const d = Math.hypot(G.X[i] - cam.x, G.Y[i] - cam.y, G.Z[i] - (cam.d || 0)); if (d < best) best = d; }
    for (const v of Renderer.visSystems) if (v.bodies) for (const r of v.bodies) {
      if (r.x > 0 && r.x < Renderer.W && r.y > 0 && r.y < Renderer.H && r.orbitPx > 5) return;
    }
    if (best / z > Math.max(Renderer.W, Renderer.H) * 0.7) this.emptiness = best;
  },

  bindInput() {
    const cv = document.getElementById('ov');
    let drag = null, moved = false;
    const pt = e => [e.clientX * Renderer.dpr, e.clientY * Renderer.dpr];
    cv.addEventListener('wheel', e => {
      e.preventDefault();
      const dy = e.deltaMode === 1 ? e.deltaY * 30 : e.deltaY;
      const base = this.zoomTarget || this.cam.z;
      this.zoomTarget = U.clamp(base * Math.exp(dy * 0.0022), this.Z_MIN, this.Z_MAX);
      this.zoomAnchor = pt(e);
      if (this.fly) { this.fly = null; }
      if (dy < 0 && this.cam.z < 3e14 && !this.follow) this.focusDepth(...this.zoomAnchor);
    }, { passive: false });
    cv.addEventListener('mousedown', e => { drag = pt(e); moved = false; });
    window.addEventListener('mousemove', e => {
      const p = pt(e);
      if (drag) {
        const dx = p[0] - drag[0], dy = p[1] - drag[1];
        if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
        if (moved) {
          this.cam.x -= dx * this.cam.z; this.cam.y += dy * this.cam.z;
          Renderer.bgOff[0] -= dx * 0.04; Renderer.bgOff[1] += dy * 0.04;
          this.follow = null; this.fly = null;
        }
        drag = p;
      } else if (e.target === cv) {
        this._hoverEv = { p, cx: e.clientX, cy: e.clientY };
      } else { this._hoverEv = null; document.getElementById('tip').classList.remove('show'); }
    });
    window.addEventListener('mouseup', e => {
      if (drag && !moved && e.target === cv) {
        const h = Renderer.pick(...pt(e), this.cam, Game.s.t);
        this.select(h);
        if (h && h.type === 'star') { const s = Galaxy.starRec(h.id); if (s) this.depthTarget = s.z || 0; }
      }
      drag = null;
    });
    cv.addEventListener('dblclick', e => {
      const h = Renderer.pick(...pt(e), this.cam, Game.s.t);
      if (h) { this.select(h); this.flyToSel(); }
    });
    // dotyk: jeden prst posun, dva prsty zoom
    let touches = null;
    cv.addEventListener('touchstart', e => { touches = [...e.touches].map(t => [t.clientX * Renderer.dpr, t.clientY * Renderer.dpr]); moved = false; }, { passive: true });
    cv.addEventListener('touchmove', e => {
      e.preventDefault();
      const ts = [...e.touches].map(t => [t.clientX * Renderer.dpr, t.clientY * Renderer.dpr]);
      if (ts.length === 1 && touches && touches.length === 1) {
        const dx = ts[0][0] - touches[0][0], dy = ts[0][1] - touches[0][1];
        this.cam.x -= dx * this.cam.z; this.cam.y += dy * this.cam.z; moved = true; this.follow = null;
      } else if (ts.length === 2 && touches && touches.length === 2) {
        const d0 = Math.hypot(touches[0][0] - touches[1][0], touches[0][1] - touches[1][1]);
        const d1 = Math.hypot(ts[0][0] - ts[1][0], ts[0][1] - ts[1][1]);
        this.cam.z = U.clamp(this.cam.z * d0 / d1, this.Z_MIN, this.Z_MAX); moved = true;
      }
      touches = ts;
    }, { passive: false });
    cv.addEventListener('touchend', e => {
      if (!moved && touches && touches.length === 1) this.select(Renderer.pick(touches[0][0], touches[0][1], this.cam, Game.s.t));
      touches = null;
    });
    window.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.code === 'Space') { e.preventDefault(); this.setSpeed(this.speed ? 0 : this.prevSpeed); }
      else if (e.key >= '1' && e.key <= '5') this.setSpeed([1, 10, 100, 1000, 10000][+e.key - 1]);
      else if (e.key === 'h' || e.key === 'H') this.quick('earth');
      else if (e.key === 'Escape') { this.select(null); this.follow = null; }
      else if (e.key === 'f' || e.key === 'F') this.flyToSel();
      else if (e.key === 'd' || e.key === 'D') UI.action('toggleDyson', {});
      else if (e.key === '+' || e.key === '=') { this.zoomTarget = this.cam.z / 2; this.zoomAnchor = null; }
      else if (e.key === '-') { this.zoomTarget = this.cam.z * 2; this.zoomAnchor = null; }
    });
    window.addEventListener('resize', () => Renderer.resize());
  },
};

window.addEventListener('load', () => {
  try { Main.start(); }
  catch (err) {
    console.error(err);
    document.getElementById('err').textContent = 'Chyba / Error: ' + err.message;
    document.getElementById('err').style.display = 'block';
  }
});
