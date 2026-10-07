// Vykreslování: WebGL2 (HDR scéna + bloom) a 2D překryv (dráhy, popisky, značky).
'use strict';

const FLOATS = 13;

class Batch {
  constructor() { this.data = new Float32Array(FLOATS * 4096); this.n = 0; }
  reset() { this.n = 0; }
  push(x, y, size, r, cr, cg, cb, a, kind, p1 = 0, p2 = 0, p3 = 0, p4 = 0) {
    if ((this.n + 1) * FLOATS > this.data.length) { const d = new Float32Array(this.data.length * 2); d.set(this.data); this.data = d; }
    const o = this.n * FLOATS, D = this.data;
    D[o] = x; D[o + 1] = y; D[o + 2] = size; D[o + 3] = r;
    D[o + 4] = cr; D[o + 5] = cg; D[o + 6] = cb; D[o + 7] = a;
    D[o + 8] = kind; D[o + 9] = p1; D[o + 10] = p2; D[o + 11] = p3; D[o + 12] = p4;
    this.n++;
  }
}

const lin = c => [Math.pow(c[0], 2.2), Math.pow(c[1], 2.2), Math.pow(c[2], 2.2)];
// barvy hvězd o něco sytější, ať jsou rudí obři opravdu oranžoví a horké hvězdy modré
const starLin = c => [Math.pow(c[0], 3.0), Math.pow(c[1], 3.0), Math.pow(c[2], 3.0)];

const Renderer = {
  gl: null, ov: null, ctx: null, W: 0, H: 0, dpr: 1,
  add: new Batch(), alpha: new Batch(), top: new Batch(),
  visSystems: [], labels: [], procCache: new Map(),
  starCol: null, starA: null, starG: null,
  bgOff: [0, 0], _tw: new Map(),

  init(glCanvas, ovCanvas) {
    const gl = glCanvas.getContext('webgl2', { antialias: false, alpha: false, premultipliedAlpha: false });
    if (!gl) throw new Error('WebGL2 není k dispozici');
    this.gl = gl; this.ov = ovCanvas; this.ctx = ovCanvas.getContext('2d');
    this.glCanvas = glCanvas;
    this.hdr = !!gl.getExtension('EXT_color_buffer_float');
    gl.getExtension('OES_texture_float_linear');
    const mk = (vs, fs) => {
      const p = gl.createProgram();
      for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
        const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
        gl.attachShader(p, s);
      }
      gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
      const u = {}; const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
      for (let i = 0; i < n; i++) { const info = gl.getActiveUniform(p, i); u[info.name] = gl.getUniformLocation(p, info.name); }
      return { p, u };
    };
    this.pBg = mk(SH.quadVS, SH.bgFS);
    this.pSprite = mk(SH.spriteVS, SH.spriteFS);
    this.pDown = mk(SH.quadVS, SH.downFS);
    this.pUp = mk(SH.quadVS, SH.upFS);
    this.pComp = mk(SH.quadVS, SH.compFS);
    this.pTex = mk(SH.texVS, SH.texFS);

    this.quadVao = gl.createVertexArray(); gl.bindVertexArray(this.quadVao);
    const qb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, qb);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    this.spriteVao = gl.createVertexArray(); gl.bindVertexArray(this.spriteVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, qb);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    this.instBuf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, this.instBuf);
    const st = FLOATS * 4;
    [[1, 4, 0], [2, 4, 16], [3, 4, 32], [4, 1, 48]].forEach(([loc, n, off]) => {
      gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, st, off); gl.vertexAttribDivisor(loc, 1);
    });
    gl.bindVertexArray(null);

    // předpočítané vlastnosti hvězd
    const G = Galaxy, n = G.n;
    this.starCol = new Float32Array(n * 3); this.starA = new Float32Array(n); this.starG = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const c = starLin(U.tempRGB(G.T[i]));
      const s = 0.35 + 0.65 * Math.max(c[0], c[1], c[2]);
      this.starCol[i * 3] = c[0] / s; this.starCol[i * 3 + 1] = c[1] / s; this.starCol[i * 3 + 2] = c[2] / s;
      const lg = Math.log10(Math.max(G.L[i], 1e-5));
      this.starA[i] = U.clamp(0.55 + 0.28 * lg, 0.12, 2.6);
      this.starG[i] = U.clamp(1.1 + 0.75 * (lg + 2), 0.8, 7);
    }
    this.resize();
    this.bakeMilkyWay();
  },

  // Mléčná dráha je statická: její drahý shader se spočítá jednou do textury 2048² a pak se jen kreslí
  bakeMilkyWay() {
    const gl = this.gl, S = 2048;
    this.mwTex = this.makeTarget(S, S);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.mwTex.fb);
    gl.viewport(0, 0, S, S);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(this.pSprite.p);
    gl.uniform2f(this.pSprite.u.uRes, S, S);
    gl.uniform1f(this.pSprite.u.uTime, 0);
    gl.uniform4f(this.pSprite.u.uMW, GAL.ARM_PHI0, GAL.PITCH, GAL.ARM_R0, GAL.BAR_ANGLE);
    const b = new Batch();
    b.push(S / 2, S / 2, S / 2, S / 2 / 1.3, 1, 1, 1, 1, 4, 3, 0, 1, 0);
    gl.bindVertexArray(this.spriteVao);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instBuf);
    gl.bufferData(gl.ARRAY_BUFFER, b.data.subarray(0, FLOATS), gl.STREAM_DRAW);
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, 1);
    gl.disable(gl.BLEND);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  },

  makeTarget(w, h) {
    const gl = this.gl;
    const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
    if (this.hdr) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
    else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    return { tex, fb, w, h };
  },

  // kvalita: 'auto' upravuje rozlišení podle plynulosti, jinak pevné měřítko rozlišení
  quality: (() => { try { return localStorage.getItem('galciv-quality') || 'auto'; } catch (e) { return 'auto'; } })(),
  autoScale: 1,
  hideDyson: (() => { try { return localStorage.getItem('galciv-hideDyson') === '1'; } catch (e) { return false; } })(),
  renderScale() { return { high: 1, mid: 0.75, low: 0.5 }[this.quality] || this.autoScale; },

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2) * this.renderScale();
    const W = Math.max(64, Math.floor((window.innerWidth || 1280) * dpr)), H = Math.max(64, Math.floor((window.innerHeight || 720) * dpr));
    if (W === this.W && H === this.H && this.scene) return;
    this.W = W; this.H = H; this.dpr = dpr;
    this.glCanvas.width = W; this.glCanvas.height = H;
    this.ov.width = W; this.ov.height = H;
    const gl = this.gl;
    if (this.targets) for (const t of this.targets) { gl.deleteTexture(t.tex); gl.deleteFramebuffer(t.fb); }
    this.scene = this.makeTarget(W, H);
    this.bgTex = this.makeTarget(W, H);
    this.bgKey = '';
    this.levels = [];
    let w = W, h = H;
    for (let i = 0; i < 6; i++) { w = Math.max(1, w >> 1); h = Math.max(1, h >> 1); this.levels.push(this.makeTarget(w, h)); }
    this.targets = [this.scene, this.bgTex, ...this.levels];
  },

  // vrstva prostoru kolem kamery: pohled shora ukazuje jen hvězdy do hloubky ~ šířky záběru
  slab(cam) { const hw = Math.max(this.W, this.H) / 2 * cam.z; return Math.max(hw * 1.2, 0.4 * C.KM_PER_LY); },
  // měkký okraj vrstvy: hvězdy v jiné hloubce pozvolna slábnou (do 3× tloušťky vrstvy), nezmizí naráz
  slabFade(zk, cam, zl) { const az = Math.abs(zk - (cam.d || 0)); if (az < zl) return 1; const f = 1 - (az - zl) / (2 * zl); return f > 0 ? f * Math.sqrt(f) : 0; },

  // ---------- souřadnice ----------
  sx(x, cam) { return (x - cam.x) / cam.z + this.W / 2; },
  sy(y, cam) { return this.H / 2 - (y - cam.y) / cam.z; },
  toWorld(px, py, cam) { return [(px - this.W / 2) * cam.z + cam.x, (this.H / 2 - py) * cam.z + cam.y]; },

  // ---------- snímek ----------
  frame(cam, realT, gameT, sel, hover) {
    this.resize();
    this.add.reset(); this.alpha.reset(); this.top.reset();
    this.visSystems = [];
    this.collectCosmos(cam, realT);
    this.collectStars(cam, realT);
    if (cam.z < 3e12) this.collectProc(cam, realT);
    for (const v of this.visSystems) this.collectSystem(v, cam, realT, gameT);
    this.drawGL(cam, realT);
    this.drawOverlay(cam, realT, gameT, sel, hover);
  },

  collectCosmos(cam, realT) {
    const z = cam.z, W = this.W, H = this.H;
    // Mléčná dráha
    const mwFade = U.clamp(Math.log10(z / 1e12) / 2, 0, 1);
    this.mwDraw = null;
    for (const g of Galaxy.galaxies) {
      const x = this.sx(g.x, cam), y = this.sy(g.y, cam);
      const r = (g.D / 2) * 1000 * C.KM_PER_PC / z;
      if (g.type === 'mw') {
        const rr = 16000 * C.KM_PER_PC / z;
        if (x + rr * 1.3 < 0 || x - rr * 1.3 > W || y + rr * 1.3 < 0 || y - rr * 1.3 > H) continue;
        if (rr < 10) this.add.push(x, y, 8 * this.dpr, 0, 1, 0.9, 0.8, U.clamp(0.3 + rr * 0.08, 0.3, 1), 0, Math.max(1, rr * 0.3) * this.dpr, 0);
        if (rr < 1) continue;
        if (mwFade > 0.01) this.mwDraw = { x, y, half: rr * 1.3, a: mwFade };
        continue;
      }
      this.pushGalaxy(g, x, y, r, 1);
    }
    if (z > 2e15) this.collectProcGalaxies(cam);
  },
  pushGalaxy(g, x, y, r, a) {
    const W = this.W, H = this.H;
    if (x + r * 1.3 < -2 || x - r * 1.3 > W + 2 || y + r * 1.3 < -2 || y - r * 1.3 > H + 2) return;
    const type = { spiral: 0, ell: 1, irr: 2 }[g.type] || 0;
    if (r > 1.2 && r < 10) { const c = type === 1 ? [1, 0.8, 0.6] : [0.85, 0.88, 1]; this.add.push(x, y, 8 * this.dpr, 0, c[0], c[1], c[2], a * 0.35, 0, Math.max(0.8, r * 0.25) * this.dpr, 0); }
    if (r > 1.2) {
      const seed = g.seed != null ? g.seed : U.hashStr(g.name[0]) % 100;
      this.add.push(x, y, r * 1.3, r, 1, 1, 1, a * (type === 1 ? 0.9 : 1.2), 4, type, (g.rot || 0) * Math.PI / 180, Math.cos((g.incl || 0) * Math.PI / 180), seed);
    } else {
      const c = type === 1 ? [1, 0.8, 0.6] : [0.8, 0.85, 1];
      this.add.push(x, y, 6 * this.dpr, 0, c[0], c[1], c[2], a * U.clamp(0.06 + r * 0.5, 0.04, 0.9), 0, 0.7 * this.dpr, 0);
    }
  },
  // nekonečné pole galaxií: úrovně buněk, každá 6× větší
  collectProcGalaxies(cam) {
    const z = cam.z, W = this.W, H = this.H;
    const G0 = 3e3 * 1000 * C.KM_PER_PC; // 3 Mpc
    for (let lvl = 0; lvl < 12; lvl++) {
      const cs = G0 * Math.pow(6, lvl);
      const cpx = cs / z;
      if (cpx < 12) continue;
      if (cpx > 6000) break;
      const fade = U.clamp((cpx - 12) / 30, 0, 1) * (lvl === 0 ? 1 : U.clamp((3000 - cpx) / 2000, 0, 1) + 0);
      const [x0, y0] = this.toWorld(0, H, cam), [x1, y1] = this.toWorld(W, 0, cam);
      const cx0 = Math.floor(x0 / cs), cx1 = Math.floor(x1 / cs), cy0 = Math.floor(y0 / cs), cy1 = Math.floor(y1 / cs);
      if ((cx1 - cx0 + 1) * (cy1 - cy0 + 1) > 2500) continue;
      for (let cx = cx0; cx <= cx1; cx++) for (let cy = cy0; cy <= cy1; cy++) {
        const web = Math.pow(U.noise2(cx * 0.35, cy * 0.35, lvl + 5) * 0.6 + U.noise2(cx * 0.9, cy * 0.9, lvl + 9) * 0.4, 2.2);
        const r = U.rng((U.hash(cx, cy, lvl * 31 + 7) * 4294967296) >>> 0);
        if (lvl === 0) {
          if (Math.abs(cx) <= 1 && Math.abs(cy) <= 1) continue; // Místní skupina je reálná
          const count = Math.floor(web * 14 + r() * 0.6);
          for (let k = 0; k < count; k++) {
            const gx = (cx + r()) * cs, gy = (cy + r()) * cs;
            const ell = r() < 0.3;
            const g = { name: ['', ''], type: ell ? 'ell' : (r() < 0.15 ? 'irr' : 'spiral'), D: 8 + Math.pow(r(), 2) * 60, incl: r() * 80, rot: r() * 360, seed: r() * 100 };
            this.pushGalaxy(g, this.sx(gx, cam), this.sy(gy, cam), g.D / 2 * 1000 * C.KM_PER_PC / z, fade);
          }
        } else {
          const count = Math.floor(web * 40);
          for (let k = 0; k < count; k++) {
            const gx = (cx + r()) * cs, gy = (cy + r()) * cs;
            const x = this.sx(gx, cam), y = this.sy(gy, cam);
            if (x < -4 || x > W + 4 || y < -4 || y > H + 4) continue;
            const warm = r();
            this.add.push(x, y, 5 * this.dpr, 0, 0.85 + warm * 0.15, 0.85, 1 - warm * 0.2, fade * (0.05 + r() * 0.2), 0, 0.65 * this.dpr, 0);
          }
        }
      }
    }
  },

  collectStars(cam, realT) {
    const G = Galaxy, z = cam.z, W = this.W, H = this.H;
    const n = G.n, X = G.X, Y = G.Y, R = G.R;
    const cx = cam.x, cy = cam.y;
    // při oddálení se hvězdy slévají: intenzita klesá s hustotou, ať bublina katalogu nepřezáří galaxii
    const far = (z > 2e12 ? Math.pow(2e12 / z, 1.3) : 1) * (z > 1e14 ? U.clamp(1 - Math.log10(z / 1e14) / 0.6, 0, 1) : 1);
    if (far <= 0.002) return;
    const near = U.clamp(Math.log10(1e12 / z), 0, 7);
    const gMul = (1 + near * 0.22) * (z > 1e12 ? Math.pow(1e12 / z, 0.4) : 1);
    const aMul = (1 + near * 0.06) * far;
    const sysZoom = z < 6e9;
    const dpr = this.dpr;
    const Z = G.Z, zl = this.slab(cam), cd = cam.d || 0;
    for (let i = 0; i < n; i++) {
      const az = Math.abs(Z[i] - cd);
      if (az > zl * 3) continue;
      let sf = 1;
      if (az > zl) { const f = 1 - (az - zl) / (2 * zl); sf = f * Math.sqrt(f); }
      const x = (X[i] - cx) / z + W / 2;
      const y = H / 2 - (Y[i] - cy) / z;
      if (sysZoom && G.primary[i] < 0) {
        const ext = 80 * C.KM_PER_AU * Math.max(1, Math.sqrt(G.L[i])) / z;
        if (x > -ext && x < W + ext && y > -ext && y < H + ext && this.visSystems.length < 8) this.visSystems.push({ id: 'h' + i, x, y });
      }
      const rpx = R[i] * C.R_SUN_KM / z;
      const m = 40 * dpr + rpx * 4;
      if (x < -m || x > W + m || y < -m || y > H + m) continue;
      const k = G.kind[i];
      if (k === 0) {
        const a = this.starA[i] * aMul * sf;
        if (a < 0.015 && rpx < 0.5) continue;   // neviditelně slabá hvězda: nekreslit
        this.pushStar(x, y, rpx, this.starCol[i * 3], this.starCol[i * 3 + 1], this.starCol[i * 3 + 2], a, this.starG[i] * gMul * dpr, i, realT);
      }
      else if (k === 1) this.pushNS(G.extra[i], x, y, rpx, aMul * sf, realT, z);
      else this.pushBH(G.extra[i], x, y, rpx, aMul * sf, realT, z);
    }
  },
  dimFor(id) {
    const st = Game.s && Game.s.sys[id];
    if (!st || !st.nodes || this.hideDyson) return 1;
    const sys = Galaxy.system(id);
    return 1 - 0.85 * Math.min(1, st.nodes * ECO.NODE_SHARE / sys.Ltot);
  },
  pushStar(x, y, rpx, r, g, b, a, glow, i, realT) {
    if (i != null && Game.s && Game.s.sys['h' + i]) a *= this.dimFor('h' + i);
    const gl = rpx > 0.5 ? Math.min(glow, Math.max(rpx * 0.6, 0.6)) + Math.min(rpx, 3) * 0.3 : glow;
    // halo jen tak velké, jak je hvězda jasná: slabé hvězdy (většina) kreslí malý čtverec, šetří to grafickou kartu
    const halo = a < 0.25 ? 2.6 : 2.6 + 4.4 * Math.min(1, (a - 0.25) / 0.9);
    const size = Math.min(Math.max(gl * halo, rpx > 0.5 ? rpx * 3.5 + 12 : 0, 2), 6000);
    const spikes = a > 1.1 && rpx < 2 ? Math.min(1, (a - 1.1)) : 0;
    this.add.push(x, y, size, rpx, r, g, b, a, 0, gl, spikes, 0, (i || 0) % 97);
  },
  pushNS(e, x, y, rpx, aMul, realT, z) {
    const vis = U.clamp(e.P * 25, 0.8, 6);
    const ang = (realT / vis) * Math.PI * 2;
    const size = U.clamp(20 + Math.log10(e.Lsd) - 20, 18, 60) * this.dpr * (1 + U.clamp(Math.log10(1e11 / z), 0, 6) * 0.5);
    this.add.push(x, y, size, rpx, 0.75, 0.85, 1, 1.2 * aMul, 2, ang, e.magnetar ? 1 : 0, 0, 0);
    if (e.nebula) {
      const rr = (e.name.startsWith('Vela') ? 60 : 5.5) / 2 * C.KM_PER_LY / z;
      if (rr > 3) this.add.push(x, y, rr * 1.3, rr, e.nebula[0], e.nebula[1], e.nebula[2], 0.9 * aMul, 9, e.name.length, 0, 0, 0);
    }
  },
  pushBH(e, x, y, rpx, aMul, realT, z) {
    const disk = e.disk || 0;
    if (disk) { // světlo akrečního disku z dálky
      const g = 2.5 * this.dpr * (1 + U.clamp(Math.log10(1e11 / z), 0, 6) * 0.4);
      if (rpx * 22 < g * 2) this.add.push(x, y, g * 6, 0, 1, 0.65, 0.35, (0.8 * disk + 0.3) * aMul, 0, g, 0, 0, 0);
    }
    if (rpx * 2.6 > 0.35) {
      const size = Math.max(rpx * (disk ? 26 : 5), 6);
      this.alpha.push(x, y, size, rpx, 1, 1, 1, 1, 3, disk, e.name.length, 0, 0);
    }
  },

  collectProc(cam, realT) {
    const z = cam.z, W = this.W, H = this.H;
    const cs = GAL.PROC_CELL_PC * C.KM_PER_PC;
    const [x0, y0] = this.toWorld(0, H, cam), [x1, y1] = this.toWorld(W, 0, cam);
    const cx0 = Math.floor(x0 / cs) - 1, cx1 = Math.floor(x1 / cs) + 1, cy0 = Math.floor(y0 / cs) - 1, cy1 = Math.floor(y1 / cs) + 1;
    if ((cx1 - cx0 + 1) * (cy1 - cy0 + 1) > 3000) return;
    // celý výřez uvnitř bubliny katalogu: procedurální hvězdy tu nejsou
    const farX = Math.max(Math.abs(x0), Math.abs(x1)), farY = Math.max(Math.abs(y0), Math.abs(y1));
    if (Math.hypot(farX, farY) / C.KM_PER_PC < GAL.CATALOG_PC * 0.85) return;
    const near = U.clamp(Math.log10(1e12 / z), 0, 7);
    const gMul = (1 + near * 0.22) * this.dpr, aMul = 1 + near * 0.06;
    for (let cx = cx0; cx <= cx1; cx++) for (let cy = cy0; cy <= cy1; cy++) {
      const key = cx + ',' + cy;
      let list = this.procCache.get(key);
      if (list === undefined) {
        list = Galaxy.procCell(cx, cy);
        if (list) for (const s of list) { s.col = starLin(U.tempRGB(s.T)); const lg = Math.log10(s.L); s.a = U.clamp(0.55 + 0.28 * lg, 0.12, 2.6); s.g = U.clamp(1.1 + 0.75 * (lg + 2), 0.8, 7); }
        this.procCache.set(key, list);
        if (this.procCache.size > 40000) this.procCache.clear();
      }
      if (!list) continue;
      for (const s of list) {
        const x = this.sx(s.x, cam), y = this.sy(s.y, cam);
        if (z < 6e9) {
          const ext = 80 * C.KM_PER_AU * Math.max(1, Math.sqrt(s.L)) / z;
          if (x > -ext && x < W + ext && y > -ext && y < H + ext && this.visSystems.length < 8) this.visSystems.push({ id: s.id, x, y });
        }
        if (x < -60 || x > W + 60 || y < -60 || y > H + 60) continue;
        const rpx = s.R * C.R_SUN_KM / z;
        let a = s.a * aMul;
        if (Game.s && Game.s.sys[s.id]) a *= this.dimFor(s.id);
        this.pushStar(x, y, rpx, s.col[0], s.col[1], s.col[2], a, s.g * gMul, null, realT);
      }
    }
  },

  collectSystem(v, cam, realT, gameT) {
    const sys = Galaxy.system(v.id);
    if (!sys) return;
    v.sys = sys;
    const z = cam.z;
    const st = Game.s.sys[v.id];
    const showBodies = Game.explored(v.id) || !sys.procedural || Game.connected(v.id);
    v.showBodies = showBodies;
    v.bodies = [];
    // průvodci (dvojhvězdy, průvodci černých děr)
    for (const c of sys.companions) {
      const ang = c.phase + 2 * Math.PI * gameT / (c.P * 24);
      const wx = sys.x + c.a * Math.cos(ang), wy = sys.y + c.a * Math.sin(ang);
      c.wx = wx; c.wy = wy;
      const x = this.sx(wx, cam), y = this.sy(wy, cam);
      const rpx = c.R * C.R_SUN_KM / z;
      const col = starLin(U.tempRGB(c.T)); const s = 0.35 + 0.65 * Math.max(...col);
      const lg = Math.log10(Math.max(c.L, 1e-5));
      const near = U.clamp(Math.log10(1e12 / z), 0, 7);
      this.pushStar(x, y, rpx, col[0] / s, col[1] / s, col[2] / s, U.clamp(0.55 + 0.28 * lg, 0.12, 2.6) * (1 + near * 0.06), U.clamp(1.1 + 0.75 * (lg + 2), 0.8, 7) * (1 + near * 0.22) * this.dpr, null, realT);
    }
    // hvězdy S kolem Sgr A*
    if (sys.sStars) for (const s of sys.sStars) {
      const p = this.keplerPos(s, gameT);
      const wx = sys.x + p[0], wy = sys.y + p[1];
      s.wx = wx; s.wy = wy;
      const col = starLin(U.tempRGB(s.T));
      this.pushStar(this.sx(wx, cam), this.sy(wy, cam), s.R * C.R_SUN_KM / z, col[0], col[1], col[2], 1.2, 3 * this.dpr * (1 + U.clamp(Math.log10(1e12 / z), 0, 7) * 0.4), null, realT);
    }
    if (!showBodies) return;
    const W = this.W, H = this.H;
    const Lsq = Math.sqrt(Math.max(sys.Ltot, 1e-4));
    for (const b of sys.bodies) {
      const orbitPx = (b.parent ? b.a : (b.type === 'belt' ? b.a1 : b.a)) / z;
      if (b.parent && orbitPx < 5) continue;
      const p = Galaxy.bodyPos(sys, b, gameT);
      const x = this.sx(p[0], cam), y = this.sy(p[1], cam);
      const rec = { b, x, y, wx: p[0], wy: p[1], orbitPx, rpx: b.R / z };
      v.bodies.push(rec);
      if (b.type === 'belt') { this.pushBelt(sys, b, cam, realT); continue; }
      if (b.type === 'station') {
        if (orbitPx > 4) this.top.push(x, y, 8 * this.dpr, 1.2 * this.dpr, 0.5, 0.85, 1, 0.9, 7);
        continue;
      }
      const rpx = rec.rpx;
      if (x < -rpx - 50 || x > W + rpx + 50 || y < -rpx - 50 || y > H + rpx + 50) continue;
      // směr ke hvězdě (svět, y nahoru)
      let lx = sys.x - p[0], ly = sys.y - p[1];
      const ll = Math.hypot(lx, ly) || 1; lx /= ll; ly /= ll;
      if (rpx >= 0.6) {
        const style = b.id.endsWith(':earth') ? 2 : b.type === 'gas' ? 1 : b.type === 'ice' ? 3 : 0;
        const c = lin(b.col);
        const atm = b.atm ? 0.8 : 0;
        this.alpha.push(x, y, rpx * 1.2 + 3, rpx, c[0], c[1], c[2], (U.hashStr(b.id) % 100) / 10, 1, lx, ly, style, atm);
        if (b.rings && b.rings[1] / z > 1.5) {
          const rc = lin([0.85, 0.78, 0.62]);
          this.alpha.push(x, y, b.rings[1] / z + 2, b.rings[0] / z, rc[0], rc[1], rc[2], 1, 6, b.rings[1] / z, lx, -ly, rpx);
        }
      } else if (orbitPx > 3) {
        const c = lin(b.col);
        this.top.push(x, y, 5 * this.dpr, 0.9 * this.dpr, c[0] * 1.5 + 0.2, c[1] * 1.5 + 0.2, c[2] * 1.5 + 0.2, 0.8, 7);
      }
    }
    // Dysonova stavba
    if (st && (st.sails > 0.5 || st.nodes > 0.5) && !this.hideDyson) {
      const x = this.sx(sys.x, cam), y = this.sy(sys.y, cam);
      const rOpt = Math.max(0.6 * Lsq * C.KM_PER_AU, sys.star.R * C.R_SUN_KM * 4) / z;
      if (st.nodes > 0.5 && rOpt > 2) {
        const cov = Math.min(1, st.nodes * ECO.NODE_SHARE / sys.Ltot);
        this.add.push(x, y, rOpt * 1.05, rOpt * 0.92, 1, 1, 1, cov, 5);
      }
      if (st.sails > 0.5 && rOpt > 2) {
        const N = Math.min(this.renderScale() < 0.8 ? 1200 : 2400, Math.floor(20 + Math.sqrt(st.sails) * 8));
        const tt = realT * 0.05, Wm = this.W + 4, Hm = this.H + 4;
        for (let k = 0; k < N; k++) {
          const h1 = U.hash(k, 1), h2 = U.hash(k, 2), h3 = U.hash(k, 3), h4 = U.hash(k, 4);
          const inc = (h1 - 0.5) * 3.0, node = h2 * 6.283, rr = rOpt * (0.85 + h4 * 0.35);
          const th = h3 * 6.283 + tt * (1.2 / Math.pow(rr / rOpt, 1.5));
          const ox = Math.cos(th), oy = Math.sin(th) * Math.cos(inc);
          const px = ox * Math.cos(node) - oy * Math.sin(node), py = ox * Math.sin(node) + oy * Math.cos(node);
          const qx = x + px * rr, qy = y + py * rr;
          if (qx < -4 || qx > Wm || qy < -4 || qy > Hm) continue;
          this.top.push(qx, qy, 3 * this.dpr, 0.55 * this.dpr, 1, 0.78, 0.4, 0.55, 7);
        }
      }
    }
  },
  pushBelt(sys, b, cam, realT) {
    const z = cam.z;
    const w = (b.a1 - b.a0) / z;
    if (b.a1 / z < 15) return;
    const N = Math.min(this.renderScale() < 0.8 ? 1200 : 2000, Math.floor(b.a1 / z * 2));
    const cx = this.sx(sys.x, cam), cy = this.sy(sys.y, cam);
    const seed = U.hashStr(b.id) % 1000;
    const c = lin(b.col);
    for (let k = 0; k < N; k++) {
      const h1 = U.hash(k, seed), h2 = U.hash(k, seed + 1), h3 = U.hash(k, seed + 2);
      const r = (b.a0 + (b.a1 - b.a0) * (0.5 + (h1 + h2 - 1) * 0.5)) / z;
      const th = h3 * 6.283 + realT * 0.01 / Math.pow(r * z / C.KM_PER_AU, 1.5);
      const x = cx + Math.cos(th) * r, y = cy - Math.sin(th) * r;
      if (x < -5 || x > this.W + 5 || y < -5 || y > this.H + 5) continue;
      this.top.push(x, y, 3 * this.dpr, 0.5 * this.dpr, c[0] * 1.6, c[1] * 1.6, c[2] * 1.6, 0.25 + h2 * 0.35, 7);
    }
  },
  keplerPos(s, t) {
    const M = 2 * Math.PI * ((t / s.P) % 1);
    let E = M;
    for (let i = 0; i < 12; i++) E = E - (E - s.e * Math.sin(E) - M) / (1 - s.e * Math.cos(E));
    const xo = s.a * (Math.cos(E) - s.e), yo = s.a * Math.sqrt(1 - s.e * s.e) * Math.sin(E);
    return [xo * Math.cos(s.w) - yo * Math.sin(s.w), xo * Math.sin(s.w) + yo * Math.cos(s.w)];
  },

  drawGL(cam, realT) {
    const gl = this.gl, W = this.W, H = this.H;
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.BLEND);
    // pozadí je drahé (šum na každém pixelu) a mění se jen při posunu: počítá se do textury, jen když je potřeba
    const z = cam.z;
    const neb = z > 1e16 ? U.clamp(1 - Math.log10(z / 1e16) / 2, 0.15, 1) : 1;
    const key = Math.round(this.bgOff[0]) + ',' + Math.round(this.bgOff[1]) + ',' + neb.toFixed(2);
    gl.bindVertexArray(this.quadVao);
    if (key !== this.bgKey) {
      this.bgKey = key;
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.bgTex.fb);
      gl.viewport(0, 0, W, H);
      gl.useProgram(this.pBg.p);
      gl.uniform2f(this.pBg.u.uRes, W, H);
      gl.uniform2f(this.pBg.u.uOff, Math.round(this.bgOff[0]), Math.round(this.bgOff[1]));
      gl.uniform1f(this.pBg.u.uTime, 0);
      gl.uniform1f(this.pBg.u.uNeb, neb);
      gl.uniform1f(this.pBg.u.uStars, neb);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.scene.fb);
    gl.viewport(0, 0, W, H);
    gl.useProgram(this.pTex.p);
    gl.uniform2f(this.pTex.u.uRes, W, H);
    gl.uniform2f(this.pTex.u.uCenter, W / 2, H / 2);
    gl.uniform2f(this.pTex.u.uHalf, W / 2, H / 2);
    gl.uniform1f(this.pTex.u.uA, 1);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.bgTex.tex);
    gl.uniform1i(this.pTex.u.uTex, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    // Mléčná dráha z předpočítané textury
    if (this.mwDraw) {
      const m = this.mwDraw;
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
      gl.useProgram(this.pTex.p);
      gl.uniform2f(this.pTex.u.uRes, W, H);
      gl.uniform2f(this.pTex.u.uCenter, m.x, m.y);
      gl.uniform2f(this.pTex.u.uHalf, m.half, m.half);
      gl.uniform1f(this.pTex.u.uA, m.a);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.mwTex.tex);
      gl.uniform1i(this.pTex.u.uTex, 0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.disable(gl.BLEND);
    }
    // sprity
    gl.useProgram(this.pSprite.p);
    gl.uniform2f(this.pSprite.u.uRes, W, H);
    gl.uniform1f(this.pSprite.u.uTime, realT);
    gl.uniform4f(this.pSprite.u.uMW, GAL.ARM_PHI0, GAL.PITCH, GAL.ARM_R0, GAL.BAR_ANGLE);
    gl.bindVertexArray(this.spriteVao);
    gl.enable(gl.BLEND);
    const draw = (batch, additive) => {
      if (!batch.n) return;
      if (additive) gl.blendFunc(gl.ONE, gl.ONE); else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.instBuf);
      gl.bufferData(gl.ARRAY_BUFFER, batch.data.subarray(0, batch.n * FLOATS), gl.STREAM_DRAW);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, batch.n);
    };
    draw(this.add, true);
    draw(this.alpha, false);
    draw(this.top, true);
    gl.disable(gl.BLEND);
    // bloom
    gl.bindVertexArray(this.quadVao);
    let src = this.scene;
    gl.useProgram(this.pDown.p);
    for (const t of this.levels) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, t.fb); gl.viewport(0, 0, t.w, t.h);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, src.tex);
      gl.uniform1i(this.pDown.u.uTex, 0);
      gl.uniform2f(this.pDown.u.uTexel, 1 / src.w, 1 / src.h);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      src = t;
    }
    gl.useProgram(this.pUp.p);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
    for (let i = this.levels.length - 2; i >= 0; i--) {
      const t = this.levels[i], s = this.levels[i + 1];
      gl.bindFramebuffer(gl.FRAMEBUFFER, t.fb); gl.viewport(0, 0, t.w, t.h);
      gl.bindTexture(gl.TEXTURE_2D, s.tex);
      gl.uniform1i(this.pUp.u.uTex, 0);
      gl.uniform2f(this.pUp.u.uTexel, 1 / s.w, 1 / s.h);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    gl.disable(gl.BLEND);
    // složení na obrazovku
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, W, H);
    gl.useProgram(this.pComp.p);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.scene.tex);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.levels[0].tex);
    gl.uniform1i(this.pComp.u.uScene, 0); gl.uniform1i(this.pComp.u.uBloom, 1);
    gl.uniform1f(this.pComp.u.uExposure, 1.15);
    gl.uniform1f(this.pComp.u.uBloomK, 0.1);
    gl.uniform1f(this.pComp.u.uTime, realT % 100);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.activeTexture(gl.TEXTURE0);
  },

  // ---------- 2D překryv ----------
  drawOverlay(cam, realT, gameT, sel, hover) {
    const ctx = this.ctx, W = this.W, H = this.H, dpr = this.dpr, z = cam.z;
    ctx.clearRect(0, 0, W, H);
    ctx.textBaseline = 'middle';
    const occ = new Set();
    const place = (x, y, w, h) => {
      const gx0 = Math.floor((x) / 60), gx1 = Math.floor((x + w) / 60), gy0 = Math.floor((y - h / 2) / 18), gy1 = Math.floor((y + h / 2) / 18);
      for (let a = gx0; a <= gx1; a++) for (let b = gy0; b <= gy1; b++) if (occ.has(a + ':' + b)) return false;
      for (let a = gx0; a <= gx1; a++) for (let b = gy0; b <= gy1; b++) occ.add(a + ':' + b);
      return true;
    };
    const label = (text, x, y, color, size = 12, force = false, weight = '') => {
      ctx.font = `${weight} ${size * dpr}px "Exo 2", system-ui, sans-serif`;
      const fk = size * dpr + weight + text;
      let w = this._tw.get(fk);
      if (w === undefined) { w = ctx.measureText(text).width; if (this._tw.size > 5000) this._tw.clear(); this._tw.set(fk, w); }
      if (!force && !place(x, y, w, size * dpr * 1.3)) return false;
      if (force) place(x, y, w, size * dpr * 1.3);
      ctx.fillStyle = 'rgba(0,0,0,0.55)'; ctx.fillText(text, x + dpr, y + dpr);
      ctx.fillStyle = color; ctx.fillText(text, x, y);
      return true;
    };
    const selId = sel && (sel.type === 'star' ? sel.id : sel.type === 'body' ? sel.body.id : null);

    // výběr
    const selPos = sel ? this.objScreen(sel, cam, gameT) : null;
    if (selPos) this.bracket(selPos[0], selPos[1], Math.max(selPos[2] * 1.15, 12 * dpr), realT, 'rgba(120,220,255,0.9)');
    const hovPos = hover && (!sel || hover.key !== sel.key) ? this.objScreen(hover, cam, gameT) : null;
    if (hovPos) this.bracket(hovPos[0], hovPos[1], Math.max(hovPos[2] * 1.15, 10 * dpr), 0, 'rgba(255,255,255,0.35)');

    // soustavy: dráhy a tělesa
    for (const v of this.visSystems) {
      if (!v.sys) continue;
      const sys = v.sys, cx = this.sx(sys.x, cam), cy = this.sy(sys.y, cam);
      for (const c of sys.companions) {
        const r = c.a / z;
        if (r > 6 && r < 2e5) { ctx.strokeStyle = 'rgba(255,220,180,0.10)'; ctx.lineWidth = dpr; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.stroke(); }
        if (r > 10) label(c.name, this.sx(c.wx, cam) + 8 * dpr, this.sy(c.wy, cam), 'rgba(255,225,190,0.75)', 11);
      }
      if (sys.sStars) for (const s of sys.sStars) {
        ctx.strokeStyle = 'rgba(180,200,255,0.18)'; ctx.lineWidth = dpr; ctx.beginPath();
        for (let k = 0; k <= 120; k++) { const p = this.keplerPos({ a: s.a, e: s.e, w: s.w, P: 1 }, k / 120); const X = this.sx(sys.x + p[0], cam), Y = this.sy(sys.y + p[1], cam); k ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); }
        ctx.stroke();
        if (s.a / z > 20) label(s.name, this.sx(s.wx, cam) + 8 * dpr, this.sy(s.wy, cam), 'rgba(200,215,255,0.8)', 11);
      }
      if (sys.bh && sys.bh.disk && sys.companions[0]) { // proud hmoty z průvodce do disku
        const c = sys.companions[0], x1 = this.sx(c.wx, cam), y1 = this.sy(c.wy, cam);
        if (Math.hypot(x1 - cx, y1 - cy) > 20) {
          const g = ctx.createLinearGradient(x1, y1, cx, cy);
          g.addColorStop(0, 'rgba(255,200,150,0.0)'); g.addColorStop(0.3, 'rgba(255,170,110,0.35)'); g.addColorStop(1, 'rgba(255,140,80,0.05)');
          ctx.strokeStyle = g; ctx.lineWidth = 3 * dpr; ctx.beginPath(); ctx.moveTo(x1, y1);
          const mx = (x1 + cx) / 2 - (cy - y1) * 0.25, my = (y1 + cy) / 2 + (cx - x1) * 0.25;
          ctx.quadraticCurveTo(mx, my, cx, cy); ctx.stroke();
        }
      }
      if (!v.showBodies) {
        const r = 30 * C.KM_PER_AU * Math.sqrt(Math.max(sys.Ltot, 0.01)) / z;
        if (r > 40 && r < 3000) {
          ctx.setLineDash([4 * dpr, 8 * dpr]); ctx.strokeStyle = 'rgba(150,170,200,0.15)'; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.stroke(); ctx.setLineDash([]);
          label(I18N.t('ui.unexplored'), cx + r * 0.72, cy - r * 0.72, 'rgba(160,180,210,0.55)', 11);
        }
        continue;
      }
      const st = Game.s.sys[sys.id];
      if (st && this.hideDyson && (st.sails > 0.5 || st.nodes > 0.5)) {
        const rO = Math.max(0.6 * Math.sqrt(Math.max(sys.Ltot, 1e-4)) * C.KM_PER_AU, sys.star.R * C.R_SUN_KM * 4) / z;
        if (rO > 8 && rO < 3e5) { ctx.setLineDash([3 * dpr, 7 * dpr]); ctx.strokeStyle = 'rgba(255,190,110,0.35)'; ctx.lineWidth = dpr; ctx.beginPath(); ctx.arc(cx, cy, rO, 0, 6.283); ctx.stroke(); ctx.setLineDash([]); }
      }
      const ordered = v.bodies.slice().sort((a, b) => (b.b.parent ? 0 : b.b.R + 1e5) - (a.b.parent ? 0 : a.b.R + 1e5));
      for (const rec of ordered) {
        const b = rec.b;
        const isSel = selId === b.id;
        if (b.type === 'belt') {
          const r0 = b.a0 / z, r1 = b.a1 / z;
          if (r1 > 8 && r0 < 1e5) {
            ctx.strokeStyle = isSel ? 'rgba(120,220,255,0.18)' : 'rgba(200,190,170,0.025)'; ctx.lineWidth = Math.max(1, r1 - r0);
            ctx.beginPath(); ctx.arc(cx, cy, (r0 + r1) / 2, 0, 6.283); ctx.stroke();
            if (r1 > 40) label(Galaxy.bodyName(b), cx, cy - (r0 + r1) / 2, 'rgba(210,200,180,0.55)', 11);
          }
          continue;
        }
        const ocx = b.parent ? this.sx(Galaxy.bodyPos(sys, b.parent, gameT)[0], cam) : cx;
        const ocy = b.parent ? this.sy(Galaxy.bodyPos(sys, b.parent, gameT)[1], cam) : cy;
        const r = rec.orbitPx;
        if (r > 4 && r < 3e5) {
          ctx.strokeStyle = isSel ? 'rgba(120,220,255,0.45)' : b.type === 'station' ? 'rgba(120,200,255,0.08)' : 'rgba(170,190,230,0.13)';
          ctx.lineWidth = dpr; ctx.beginPath(); ctx.arc(ocx, ocy, r, 0, 6.283); ctx.stroke();
        }
        if (r < 8 && !isSel) continue;
        const ents = st ? st.b.filter(e => e.body === b.id) : [];
        if (rec.rpx < 5) {
          ctx.strokeStyle = b.type === 'station' ? 'rgba(120,210,255,0.7)' : 'rgba(220,230,255,0.5)';
          ctx.lineWidth = dpr; ctx.beginPath();
          if (b.type === 'station') { const s = 5 * dpr; ctx.moveTo(rec.x, rec.y - s); ctx.lineTo(rec.x + s, rec.y); ctx.lineTo(rec.x, rec.y + s); ctx.lineTo(rec.x - s, rec.y); ctx.closePath(); }
          else ctx.arc(rec.x, rec.y, 5 * dpr, 0, 6.283);
          ctx.stroke();
        }
        const off = Math.max(rec.rpx, 5 * dpr) + 6 * dpr;
        const name = Galaxy.bodyName(b);
        if (r > 14 || isSel) label(name, rec.x + off, rec.y, ents.length ? 'rgba(140,230,255,0.95)' : 'rgba(225,232,245,0.8)', 12, isSel);
        if (ents.length && (r > 30 || isSel)) {
          const txt = ents.map(e => BUILDINGS[e.t].icon + (e.n > 1 ? e.n : '')).join(' ');
          label(txt, rec.x + off, rec.y + 14 * dpr, 'rgba(255,215,140,0.85)', 11, true);
        }
        if (st && st.gate && b.type === 'station') this.gateFx(rec.x, rec.y, realT, Game.connected(sys.id));
      }
    }

    // propojení červích děr a sondy
    if (Game.s) {
      const links = Game.s.links || [];
      ctx.lineWidth = 1.5 * dpr;
      for (const [a, b] of links) {
        const A = Galaxy.starRec(a), B = Galaxy.starRec(b);
        const x1 = this.sx(A.x, cam), y1 = this.sy(A.y, cam), x2 = this.sx(B.x, cam), y2 = this.sy(B.y, cam);
        if (Math.hypot(x2 - x1, y2 - y1) < 30) continue;
        const g = ctx.createLinearGradient(x1, y1, x2, y2);
        g.addColorStop(0, 'rgba(140,110,255,0.6)'); g.addColorStop(0.5, 'rgba(90,220,255,0.35)'); g.addColorStop(1, 'rgba(140,110,255,0.6)');
        ctx.strokeStyle = g; ctx.setLineDash([6 * dpr, 6 * dpr]); ctx.lineDashOffset = -realT * 20 * dpr;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]);
      }
      for (const p of Game.s.probes) {
        const A = Galaxy.starRec(p.from), B = Galaxy.starRec(p.to);
        const f = U.clamp((gameT - p.depart) / (p.arrive - p.depart), 0, 1);
        const x1 = this.sx(A.x, cam), y1 = this.sy(A.y, cam), x2 = this.sx(B.x, cam), y2 = this.sy(B.y, cam);
        if (Math.hypot(x2 - x1, y2 - y1) < 20) continue;
        ctx.strokeStyle = 'rgba(255,220,140,0.18)'; ctx.setLineDash([2 * dpr, 6 * dpr]); ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]);
        const px = U.lerp(x1, x2, f), py = U.lerp(y1, y2, f);
        const g = ctx.createRadialGradient(px, py, 0, px, py, 8 * dpr);
        g.addColorStop(0, 'rgba(255,240,200,1)'); g.addColorStop(1, 'rgba(255,180,80,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, 8 * dpr, 0, 6.283); ctx.fill();
        label(U.duration(p.arrive - gameT), px + 10 * dpr, py, 'rgba(255,220,150,0.8)', 10, true);
      }
      // soustavy říše
      if (z > 1e9) for (const id of Game.s.net) {
        const s = Galaxy.starRec(id);
        const x = this.sx(s.x, cam), y = this.sy(s.y, cam);
        if (x < -20 || x > W + 20 || y < -20 || y > H + 20) continue;
        ctx.strokeStyle = 'rgba(90,220,255,0.75)'; ctx.lineWidth = 1.2 * dpr;
        const r = 9 * dpr; ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath(); ctx.stroke();
      }
    }

    // popisky hvězd
    if (z > 2e9 && z < 4e15) {
      const G = Galaxy, ord = G.brightOrder;
      const near = U.clamp(Math.log10(1e12 / z), 0, 7);
      let shown = 0;
      const lim = z < 1e12 ? 9000 : 2500;
      const zl = this.slab(cam);
      for (let k = 0; k < lim && shown < 70; k++) {
        const i = ord[k];
        if (!G.names[i] || G.primary[i] >= 0) continue;
        if (this.slabFade(G.Z[i], cam, zl) < 0.5) continue;
        const x = this.sx(G.X[i], cam), y = this.sy(G.Y[i], cam);
        if (x < 0 || x > W || y < 0 || y > H) continue;
        const ex = G.extra[i];
        if (ex && z > 3e14 && !ex.core) continue;
        if (!ex && z > 2e14) continue;
        if (i === G.solIndex && z > 4e13) continue;
        const bright = this.starA[i] * (1 + near * 0.12);
        if (!ex && z > 5e13 && bright < 1.2 && i !== G.solIndex) continue;
        const c = ex ? (ex.kind === 'bh' ? 'rgba(255,170,120,0.9)' : ex.kind === 'ns' ? 'rgba(170,200,255,0.9)' : 'rgba(255,200,170,0.85)')
          : U.rgbCss(U.tempRGB(G.T[i]).map(v => 0.55 + v * 0.45), 0.8);
        const isSel = selId === 'h' + i;
        if (label(G.starName(i), x + 9 * dpr, y - 6 * dpr, c, i === G.solIndex ? 13 : 11.5, isSel || i === G.solIndex, i === G.solIndex ? '600' : '')) shown++;
        if (ex && ex.kind === 'bh' && !ex.disk) { ctx.strokeStyle = 'rgba(255,170,120,0.45)'; ctx.lineWidth = dpr; ctx.beginPath(); ctx.arc(x, y, 4 * dpr, 0, 6.283); ctx.stroke(); }
      }
      if (z < 2e11) for (const [key, list] of this.procCache) {
        if (!list) continue;
        for (const s of list) {
          if (s.L < 0.3 && z > 3e10) continue;
          const x = this.sx(s.x, cam), y = this.sy(s.y, cam);
          if (x < 0 || x > W || y < 0 || y > H) continue;
          if (label(s.name, x + 9 * dpr, y - 6 * dpr, 'rgba(190,200,220,0.6)', 11)) if (++shown > 90) break;
        }
      }
    }
    // galaxie
    if (z > 3e14) for (const g of Galaxy.galaxies) {
      const x = this.sx(g.x, cam), y = this.sy(g.y, cam);
      if (x < 0 || x > W || y < 0 || y > H) continue;
      const r = (g.type === 'mw' ? 16000 : g.D / 2 * 1000) * C.KM_PER_PC / z;
      const nm = g.name[I18N.lang === 'cs' ? 0 : 1];
      if (g.type === 'mw') { if (r < 400) label(nm, x - 20 * dpr, y + r * 0.9 + 14 * dpr, 'rgba(230,220,255,0.75)', 13, true); }
      else if (r > 0.3 || z < 3e18) label(nm, x + r + 8 * dpr, y, 'rgba(220,215,255,0.7)', 11);
    }
    // Slunce = „jsi tady“ při velkém oddálení
    if (z > 4e13) {
      const x = this.sx(0, cam), y = this.sy(0, cam);
      if (x > 0 && x < W && y > 0 && y < H) {
        ctx.strokeStyle = 'rgba(255,230,150,0.8)'; ctx.lineWidth = dpr;
        ctx.beginPath(); ctx.arc(x, y, 5 * dpr, 0, 6.283); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x, y - 9 * dpr); ctx.lineTo(x, y - 18 * dpr); ctx.stroke();
        if (z < 3e18) label(I18N.lang === 'cs' ? 'Slunce' : 'Sun', x + 8 * dpr, y - 14 * dpr, 'rgba(255,230,150,0.9)', 11, true);
      }
    }
    // hranice pozorovatelného vesmíru
    const OBS = 46.5e9 * C.KM_PER_LY;
    if (OBS / z < 5e4 && OBS / z > 30) {
      const x = this.sx(0, cam), y = this.sy(0, cam), r = OBS / z;
      ctx.strokeStyle = 'rgba(150,170,255,0.35)'; ctx.lineWidth = 1.5 * dpr; ctx.setLineDash([10 * dpr, 10 * dpr]);
      ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.stroke(); ctx.setLineDash([]);
      label(I18N.t('ui.observable'), x - r * 0.7, y - r * 0.72, 'rgba(170,185,255,0.7)', 12, true);
    }
  },

  gateFx(x, y, t, open) {
    const ctx = this.ctx, dpr = this.dpr;
    const r = 11 * dpr;
    for (let k = 0; k < 3; k++) {
      ctx.strokeStyle = open ? `rgba(${120 + k * 40},${140 + k * 30},255,${0.55 - k * 0.12})` : `rgba(160,160,180,${0.4 - k * 0.1})`;
      ctx.lineWidth = 1.5 * dpr;
      ctx.beginPath(); ctx.arc(x, y, r + k * 3 * dpr, t * (1 + k * 0.5), t * (1 + k * 0.5) + 4.2); ctx.stroke();
    }
  },
  bracket(x, y, r, t, color) {
    const ctx = this.ctx, dpr = this.dpr;
    const R = r + Math.sin(t * 3) * 1.5 * dpr, L = Math.max(5 * dpr, R * 0.35);
    ctx.strokeStyle = color; ctx.lineWidth = 1.4 * dpr;
    ctx.beginPath();
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      ctx.moveTo(x + sx * R, y + sy * (R - L)); ctx.lineTo(x + sx * R, y + sy * R); ctx.lineTo(x + sx * (R - L), y + sy * R);
    }
    ctx.stroke();
  },

  objScreen(o, cam, gameT) {
    if (o.type === 'star') {
      const s = Galaxy.starRec(o.id); if (!s) return null;
      return [this.sx(s.x, cam), this.sy(s.y, cam), Math.max(s.R * C.R_SUN_KM / cam.z * (s.kind === 'bh' ? 2.6 : 1), 6 * this.dpr)];
    }
    if (o.type === 'body') {
      const sys = Galaxy.system(o.body.sys);
      if (o.body.type === 'belt') return null;
      const p = Galaxy.bodyPos(sys, o.body, gameT);
      return [this.sx(p[0], cam), this.sy(p[1], cam), Math.max(o.body.R / cam.z, 6 * this.dpr)];
    }
    if (o.type === 'galaxy') {
      const g = o.g; const r = (g.type === 'mw' ? 16000 : g.D / 2 * 1000) * C.KM_PER_PC / cam.z;
      return [this.sx(g.x, cam), this.sy(g.y, cam), Math.max(r, 6 * this.dpr)];
    }
    return null;
  },

  // ---------- výběr myší ----------
  pick(px, py, cam, gameT) {
    const dpr = this.dpr, z = cam.z;
    let best = null, bd = 14 * dpr;
    for (const v of this.visSystems) {
      if (!v.sys || !v.showBodies) continue;
      for (const rec of v.bodies) {
        const b = rec.b;
        if (b.type === 'belt') {
          const r = Math.hypot(px - this.sx(v.sys.x, cam), py - this.sy(v.sys.y, cam));
          if (r > b.a0 / z && r < b.a1 / z && b.a1 / z > 15) { if (!best) best = { type: 'body', body: b, key: b.id, d: bd }; }
          continue;
        }
        if (rec.orbitPx < 6) continue;
        const d = Math.hypot(px - rec.x, py - rec.y) - Math.max(rec.rpx, 0);
        if (d < bd) { bd = d; best = { type: 'body', body: b, key: b.id }; }
      }
    }
    if (best) return best;
    const G = Galaxy, W = this.W, H = this.H;
    bd = 12 * dpr; let bi = -1, bscore = 1e9;
    const zl = this.slab(cam);
    if (z < 3e15) for (let i = 0; i < G.n; i++) {
      if (G.primary[i] >= 0) continue;
      if (this.slabFade(G.Z[i], cam, zl) < 0.3) continue;
      const x = (G.X[i] - cam.x) / z + W / 2, y = H / 2 - (G.Y[i] - cam.y) / z;
      const rp = G.R[i] * C.R_SUN_KM / z * (G.kind[i] === 2 ? 2.6 : 1);
      const d = Math.hypot(px - x, py - y) - rp;
      if (d < bd) { const sc = d - Math.log10(G.L[i] + 1e-3) * 2 * dpr - (G.extra[i] ? 6 * dpr : 0); if (sc < bscore) { bscore = sc; bi = i; } }
    }
    if (bi >= 0) return { type: 'star', id: 'h' + bi, key: 'h' + bi };
    if (z < 3e12) {
      for (const [k, list] of this.procCache) if (list) for (const s of list) {
        const d = Math.hypot(px - this.sx(s.x, cam), py - this.sy(s.y, cam));
        if (d < bd) { bd = d; best = { type: 'star', id: s.id, key: s.id }; }
      }
      if (best) return best;
    }
    for (const g of Galaxy.galaxies) {
      const r = (g.type === 'mw' ? 16000 : g.D / 2 * 1000) * C.KM_PER_PC / z;
      const d = Math.hypot(px - this.sx(g.x, cam), py - this.sy(g.y, cam));
      if (d < Math.max(r * (g.type === 'mw' ? 0.9 : 1), 10 * dpr) && (g.type !== 'mw' || z > 1e14)) return { type: 'galaxy', g, key: 'g' + g.name[1] };
    }
    return null;
  },
};
