'use strict';
/* ---------------- audio: procedural Web Audio, no files ----------------
   A candlelit crypt: bells, gongs, stone, bone, wooden chess pieces, low choir drones.
   Everything lives in this closure so helper names never collide with the other scripts;
   the only globals are sfx, audioOnSnap, audioApplyOpts, audioEnd and audioStop. */
(() => {
const MAXV = 24, MUS_GAIN = 1.4;
let C = null, M = null;                   // AudioContext (made on the first gesture) and the running music
const A = {
  voices: [], last: {}, nx: {}, ids: new Set(), alfa: new Map(), crates: new Map(), whist: new Set(),
  I: 0.15, iT: 0, thT: -99, waveT: -99, hb: 0, crit: false, ck: false, gck: 0, geiger: 0, gx: null, alt: 0,
  muf: false, ended: false, lastSnap: 0, timer: 0, optKey: '', warned: false,
};

/* ---------------- context, buses, options ---------------- */
function init() {
  if (C) { if (C.state === 'suspended' && !document.hidden) C.resume().catch(() => {}); return; }
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;
  const c = new AC({ latencyHint: 'interactive' });
  const gain = (v, out) => { const g = c.createGain(); g.gain.value = v; if (out) g.connect(out); return g; };
  const comp = (thr, knee, ratio, att, rel) => {
    const k = c.createDynamicsCompressor();
    k.threshold.value = thr; k.knee.value = knee; k.ratio.value = ratio; k.attack.value = att; k.release.value = rel;
    return k;
  };
  const lowpass = out => { const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 20000; f.connect(out); return f; };
  A.master = gain(1);
  A.master.connect(comp(-14, 8, 4, 0.004, 0.25)).connect(comp(-2, 0, 20, 0.001, 0.08)).connect(c.destination);
  A.rev = c.createConvolver(); A.rev.buffer = impulse(c, 2.2); A.rev.connect(A.master);
  A.sfx = gain(1, A.master); A.sfx.connect(gain(0.16, A.rev));
  A.xw = gain(1, A.rev);                  // extra reverb for bells, follows the effects volume
  A.wf = lowpass(A.sfx);                  // muffles the world while my King is dead
  A.world = gain(1, A.wf); A.ui = gain(1, A.sfx);
  A.mus = gain(1, A.master); A.mus.connect(gain(0.3, A.rev));
  A.mf = lowpass(A.mus); A.duck = gain(1, A.mf);
  A.noise = c.createBuffer(1, c.sampleRate * 2, c.sampleRate);
  const d = A.noise.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  A.curve = new Float32Array(1024);
  for (let i = 0; i < 1024; i++) A.curve[i] = Math.tanh(2.2 * (i / 511.5 - 1)) / Math.tanh(2.2);
  C = c;
  apply();
  if (!document.hidden) A.timer = setInterval(tick, 25);
}
// stone crypt reverb: decaying noise that darkens over time, plus a few early wall reflections
function impulse(c, sec) {
  const n = Math.floor(c.sampleRate * sec), b = c.createBuffer(2, n, c.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = b.getChannelData(ch);
    let lp = 0;
    for (let i = Math.floor(c.sampleRate * 0.012); i < n; i++) {
      const k = i / n;
      lp += (Math.random() * 2 - 1 - lp) * (0.6 - 0.5 * k);
      d[i] = lp * Math.exp(-3.2 * k * sec);
    }
    for (const [ms, a] of [[19, 0.5], [31, 0.35], [47, 0.3], [63, 0.2]]) d[Math.floor(c.sampleRate * (ms + ch * 4) / 1000)] += a;
  }
  return b;
}
const optKey = () => { const o = S.opt || {}; return `${o.sfx}|${o.mus}|${o.mute}`; };
function apply() {
  if (!C) return;
  const o = S.opt || {}, t = C.currentTime;
  const lvl = (v, d) => ((Math.max(0, Math.min(100, Number(v ?? d))) || 0) / 100) ** 1.6;
  const sv = lvl(o.sfx, 70);
  A.sfx.gain.setTargetAtTime(sv, t, 0.03);
  A.xw.gain.setTargetAtTime(sv, t, 0.03);
  A.mus.gain.setTargetAtTime(lvl(o.mus, 40) * MUS_GAIN, t, 0.03);
  A.master.gain.setTargetAtTime(o.mute ? 0 : 1, t, 0.015);
  A.optKey = optKey();
}
for (const ev of ['pointerdown', 'keydown']) window.addEventListener(ev, () => { try { init(); } catch (e) { warn(e); } }, true);
document.addEventListener('visibilitychange', () => {
  try {
    if (!C) return;
    if (document.hidden) { clearInterval(A.timer); A.timer = 0; C.suspend().catch(() => {}); }
    else { C.resume().catch(() => {}); if (!A.timer) A.timer = setInterval(tick, 25); }
  } catch (e) { warn(e); }
});
function warn(e) { if (!A.warned) { A.warned = true; console.warn('audio:', e); } }

/* ---------------- voices ---------------- */
function play(name, x, op) {
  const d = SND[name];
  if (!d || !C || C.state !== 'running') return;
  op = op || {};
  const now = C.currentTime, t = now + 0.01 + (op.delay || 0), key = op.foe ? name + '~' : name;
  if (Math.abs(t - (A.last[key] ?? -99)) < d.rl) return;
  prune(now);
  const pri = d.pri ?? 2, live = A.voices.filter(v => !v.cut);
  if (live.length >= MAXV) {          // steal the oldest voice of the lowest priority, or drop this sound
    const v = live.reduce((a, b) => (b.pri < a.pri ? b : a));
    if (v.pri >= pri) return;
    v.g.gain.setTargetAtTime(0, now, 0.015); v.cut = true; v.end = now + 0.1;
  }
  A.last[key] = t;
  const g = C.createGain(), pan = C.createStereoPanner ? C.createStereoPanner() : C.createGain();
  g.gain.value = (op.vol ?? 1) * (op.foe ? 0.55 : 1) * (0.9 + Math.random() * 0.2);
  if (pan.pan) pan.pan.value = panOf(x);
  g.connect(pan).connect(d.bus === 'ui' ? A.ui : d.bus === 'mus' ? A.duck : A.world);
  if (d.wet) { const w = C.createGain(); w.gain.value = d.wet; pan.connect(w).connect(A.xw); }
  if (d.duck && !op.foe) duck(d.duck[0], d.duck[1]);
  const j = d.jit ?? 0.06, p = (1 + (Math.random() * 2 - 1) * j) * 2 ** ((op.st || 0) / 12);
  A.voices.push({ g, pan, pri, cut: false, end: t + d.fn(g, t, p, op) + 0.05 });
}
function prune(now) {
  if (!A.voices.length) return;
  A.voices = A.voices.filter(v => { if (v.end > now) return true; v.pan.disconnect(); return false; });
}
// board column → stereo position (own side always on the left)
function panOf(x) {
  if (x == null || !isFinite(x)) return 0;
  const c = typeof vx === 'function' ? vx(x) : x;
  return Math.max(-0.7, Math.min(0.7, (c / ((S.W || 16) - 1) * 2 - 1) * 0.7));
}
function duck(db, sec) {
  const p = A.duck.gain, t = C.currentTime;
  if (p.cancelAndHoldAtTime) p.cancelAndHoldAtTime(t); else p.cancelScheduledValues(t);
  p.setTargetAtTime(10 ** (-db / 20), t, 0.03);
  p.setTargetAtTime(1, t + sec, 0.25);
}
function muffle(on) {
  if (A.muf === on || !C) return;
  A.muf = on;
  const t = C.currentTime;
  A.mf.frequency.setTargetAtTime(on ? 400 : 20000, t, on ? 0.15 : 0.5);
  A.wf.frequency.setTargetAtTime(on ? 1800 : 20000, t, on ? 0.15 : 0.5);
}

/* ---------------- synthesis primitives (o = destination node, t = start time) ---------------- */
function env(p, t, a, v, dur, hold = 0) {
  p.setValueAtTime(0.0001, t);
  p.linearRampToValueAtTime(v, t + a);
  if (hold > 0) p.setValueAtTime(v, t + a + hold);
  p.exponentialRampToValueAtTime(0.0001, t + dur);
}
function run(s, g, t, dur, off = 0) { s.start(t, off); s.stop(t + dur + 0.03); s.onended = () => g.disconnect(); }
function tone(o, t, type, f0, f1, dur, vol, a = 0.004, glide = dur) {
  const s = C.createOscillator(), g = C.createGain();
  s.type = type;
  s.frequency.setValueAtTime(f0, t);
  if (f1 !== f0) s.frequency.exponentialRampToValueAtTime(f1, t + glide);
  env(g.gain, t, a, vol, dur);
  s.connect(g).connect(o);
  run(s, g, t, dur);
  return s;
}
function nz(o, t, dur, type, f0, f1, q, vol, a = 0.003) {
  const s = C.createBufferSource(), f = C.createBiquadFilter(), g = C.createGain();
  s.buffer = A.noise; s.loop = true;
  f.type = type; f.Q.value = q;
  f.frequency.setValueAtTime(f0, t);
  if (f1 !== f0) f.frequency.exponentialRampToValueAtTime(f1, t + dur);
  env(g.gain, t, a, vol, dur);
  s.connect(f).connect(g).connect(o);
  run(s, g, t, dur, Math.random() * 1.5);
}
function vib(o, t, f0, f1, dur, vol, rate, depth, a) {
  const l = C.createOscillator(), lg = C.createGain();
  l.frequency.value = rate; lg.gain.value = depth;
  l.connect(lg).connect(tone(o, t, 'sine', f0, f1, dur, vol, a).frequency);
  run(l, lg, t, dur);
}
// struck bells: [ratio, level, decay share]; lower partials ring longest
const BELL = [[0.5, 0.4, 1], [1, 1, 0.7], [1.19, 0.5, 0.5], [1.5, 0.3, 0.42], [2, 0.45, 0.34], [2.51, 0.24, 0.26], [2.66, 0.2, 0.22], [3.01, 0.15, 0.18]];
const GONG = [[1, 1, 1], [1.505, 0.75, 0.8], [2.378, 0.5, 0.6], [3.173, 0.35, 0.45]];
const CHIME = [[1, 1, 1], [2.76, 0.3, 0.45], [5.4, 0.12, 0.25]];
const METAL = [[1, 1, 1], [1.48, 0.7, 0.8], [2.11, 0.5, 0.6], [2.73, 0.4, 0.5], [3.6, 0.3, 0.4]];
function bell(o, t, f, dur, vol, parts = BELL) {
  for (const [r, a, d] of parts) if (f * r < 15000) tone(o, t, 'sine', f * r, f * r, dur * d, vol * a, 0.002);
  const s = Math.min(9000, f * 5);
  nz(o, t, 0.025, 'bandpass', s, s, 1.5, vol * 0.35);
}
function brass(o, t, f, dur, vol, a = 0.05) {
  const lp = C.createBiquadFilter(), g = C.createGain();
  lp.type = 'lowpass'; lp.Q.value = 3;
  lp.frequency.setValueAtTime(f * 1.5, t);
  lp.frequency.linearRampToValueAtTime(f * 7, t + a);
  lp.frequency.setTargetAtTime(f * 3.5, t + a, 0.2);
  env(g.gain, t, a, vol, dur, dur * 0.6 - a);
  lp.connect(g).connect(o);
  for (const det of [-7, 7]) {
    const s = C.createOscillator();
    s.type = 'sawtooth'; s.frequency.value = f; s.detune.value = det;
    s.connect(lp); run(s, g, t, dur);
  }
}
// sung "ah" (or "oo" with vow = [400, 800]): detuned saws through two formant band-passes
function choir(o, t, freqs, dur, vol, a = 0.4, vow = [700, 1150]) {
  const g = C.createGain(), l = C.createOscillator(), lg = C.createGain();
  env(g.gain, t, a, vol, dur, dur * 0.55 - a);
  g.connect(o);
  l.frequency.value = 4.8; lg.gain.value = 9; l.connect(lg); run(l, lg, t, dur);
  const fs = vow.map((fq, i) => {
    const b = C.createBiquadFilter();
    b.type = 'bandpass'; b.frequency.value = fq; b.Q.value = 4 + 3 * i; b.connect(g);
    return b;
  });
  for (const f of freqs) for (const det of [-10, 0, 10]) {
    const s = C.createOscillator();
    s.type = 'sawtooth'; s.frequency.value = f; s.detune.value = det;
    lg.connect(s.detune); fs.forEach(b => s.connect(b)); run(s, g, t, dur);
  }
}
// growling beast: two saws through a sweeping formant with a fast amplitude flutter
function roar(o, t, f0, f1, dur, vol) {
  const b = C.createBiquadFilter(), am = C.createGain(), g = C.createGain(), l = C.createOscillator(), lg = C.createGain();
  b.type = 'bandpass'; b.Q.value = 3;
  b.frequency.setValueAtTime(300, t);
  b.frequency.exponentialRampToValueAtTime(900, t + dur * 0.4);
  b.frequency.exponentialRampToValueAtTime(400, t + dur);
  am.gain.value = 0.7; l.frequency.value = 23; lg.gain.value = 0.3; l.connect(lg).connect(am.gain); run(l, lg, t, dur);
  env(g.gain, t, dur * 0.25, vol, dur);
  b.connect(am).connect(g).connect(o);
  for (const det of [-12, 12]) {
    const s = C.createOscillator();
    s.type = 'sawtooth'; s.detune.value = det;
    s.frequency.setValueAtTime(f0, t); s.frequency.exponentialRampToValueAtTime(f1, t + dur);
    s.connect(b); run(s, g, t, dur);
  }
}
function drum(o, t, f, dur, vol) { tone(o, t, 'sine', f * 2.2, f, dur, vol, 0.002, 0.05); nz(o, t, 0.08, 'lowpass', 700, 200, 1, vol * 0.4); }
function wood(o, t, f, vol) { nz(o, t, 0.035, 'bandpass', f, f, 6, vol); tone(o, t, 'triangle', f * 0.37, f * 0.19, 0.06, vol * 0.25, 0.001); }
function crackle(o, t, n, span, vol) { for (let i = 0; i < n; i++) nz(o, t + Math.random() * span, 0.004, 'highpass', 3000, 3000, 1, vol, 0.0005); }
function pluck(o, t, f, vol) {
  const lp = C.createBiquadFilter();
  lp.type = 'lowpass'; lp.Q.value = 4;
  lp.frequency.setValueAtTime(600, t); lp.frequency.exponentialRampToValueAtTime(160, t + 0.25);
  lp.connect(o);
  tone(lp, t, 'sawtooth', f, f, 0.32, vol, 0.006);
}
function boom(o, t, p, r) {
  const k = Math.min(1, 0.45 + 0.35 * r), d = 0.4 + 0.3 * Math.min(1.6, r), sh = C.createWaveShaper();
  sh.curve = A.curve; sh.connect(o);
  nz(sh, t, d, 'lowpass', 3000 * p, 150, 1, 0.75 * k, 0.004);
  tone(sh, t, 'sine', 70 * p, 28, d + 0.25, 0.8 * k);
  nz(o, t, 0.02, 'highpass', 1500, 1500, 1, 0.25 * k);
  return d + 0.3;
}

/* ---------------- sound table ----------------
   rl = rate limit (s, per name and side), pri = voice priority 0-3, bus = 'ui' | 'mus' (default: world),
   jit = pitch jitter, wet = extra reverb, duck = [dB, s] on the music; fn returns the duration. */
const SND = {
  // interface (called by the UI)
  tick: { rl: 0.03, pri: 3, bus: 'ui', fn: (o, t, p) => { wood(o, t, 2100 * p, 0.5); return 0.08; } },
  click: { rl: 0.03, pri: 3, bus: 'ui', fn: (o, t, p) => { wood(o, t, 1500 * p, 0.45); tone(o, t, 'sine', 520 * p, 470 * p, 0.06, 0.06); return 0.08; } },
  select: { rl: 0.05, pri: 3, bus: 'ui', fn: (o, t, p) => { wood(o, t, 2600 * p, 0.3); bell(o, t + 0.01, 1175 * p, 0.25, 0.05, CHIME); return 0.3; } },
  deny: { rl: 0.12, pri: 3, bus: 'ui', fn: (o, t, p) => {
    for (const [d, v] of [[0, 1], [0.09, 0.8]]) {
      tone(o, t + d, 'triangle', 150 * p, 132 * p, 0.12, 0.3 * v);
      tone(o, t + d, 'sawtooth', 159 * p, 140 * p, 0.1, 0.05 * v);
      nz(o, t + d, 0.05, 'lowpass', 500, 300, 1, 0.3 * v);
    }
    return 0.25;
  } },
  ready: { rl: 0.4, pri: 3, bus: 'ui', jit: 0.005, fn: (o, t, p) => { bell(o, t, 880 * p, 0.5, 0.1, CHIME); bell(o, t + 0.07, 1318.5 * p, 0.6, 0.1, CHIME); return 0.7; } },
  afford: { rl: 1.5, pri: 2, bus: 'ui', jit: 0.005, fn: (o, t, p) => { bell(o, t, 1760 * p, 0.35, 0.04, CHIME); return 0.4; } },
  chooser: { rl: 0.2, pri: 3, bus: 'ui', jit: 0.005, fn: (o, t, p) => { bell(o, t, 587 * p, 0.5, 0.1, CHIME); bell(o, t + 0.1, 784 * p, 0.7, 0.1, CHIME); return 0.8; } },
  toast: { rl: 0.3, pri: 2, bus: 'ui', fn: (o, t, p) => { nz(o, t, 0.09, 'bandpass', 2800 * p, 1800 * p, 0.8, 0.1, 0.02); wood(o, t + 0.02, 2500 * p, 0.12); return 0.12; } },
  banner1: { rl: 0.3, pri: 3, bus: 'ui', jit: 0.01, wet: 0.4, duck: [4, 0.7], fn: (o, t, p) => {
    drum(o, t, 55, 1.0, 0.6); brass(o, t, 110 * p, 0.7, 0.1); brass(o, t, 116.5 * p, 0.7, 0.08); bell(o, t, 220 * p, 1.6, 0.12);
    return 1.6;
  } },
  banner2: { rl: 0.3, pri: 3, bus: 'ui', jit: 0.01, wet: 0.5, duck: [4, 0.7], fn: (o, t, p) => { bell(o, t, 164.8 * p, 2.2, 0.2); drum(o, t, 49, 0.8, 0.35); return 2.2; } },
  banner3: { rl: 0.3, pri: 3, bus: 'ui', jit: 0.01, wet: 0.3, duck: [3, 0.5], fn: (o, t, p) => {
    wood(o, t, 1300 * p, 0.25); bell(o, t + 0.02, 659 * p, 0.5, 0.08, CHIME); bell(o, t + 0.1, 988 * p, 0.6, 0.08, CHIME);
    return 0.7;
  } },
  research: { rl: 0.5, pri: 3, bus: 'ui', jit: 0.005, wet: 0.4, fn: (o, t, p) => {
    [659, 784, 988].forEach((f, i) => bell(o, t + i * 0.1, f * p, 1.0, 0.08, CHIME));
    choir(o, t, [164.8, 246.9], 1.6, 0.12, 0.3);
    return 1.7;
  } },
  doba: { rl: 1, pri: 3, bus: 'ui', jit: 0, wet: 0.4, duck: [5, 1.5], fn: (o, t) => {
    drum(o, t, 55, 1.2, 0.5);
    for (const f of [110, 164.8, 220, 277.2]) brass(o, t + 0.05, f, 2.0, 0.06, 0.25);
    bell(o, t + 0.05, 220, 2.5, 0.12);
    return 2.6;
  } },
  win: { rl: 1, pri: 3, bus: 'ui', jit: 0, wet: 0.4, fn: (o, t) => {
    [440, 554.4, 659.3, 880].forEach((f, i) => bell(o, t + i * 0.09, f, 1.6, 0.1, CHIME));
    nz(o, t + 0.27, 1.6, 'highpass', 7000, 5000, 1, 0.06, 0.01);
    return 2;
  } },
  lose: { rl: 1, pri: 3, bus: 'ui', jit: 0, wet: 0.4, fn: (o, t) => {
    bell(o, t, 110, 3, 0.25);
    [329.6, 261.6, 220].forEach((f, i) => bell(o, t + 0.15 + i * 0.22, f, 1.2, 0.07, CHIME));
    return 3;
  } },
  draw: { rl: 1, pri: 3, bus: 'ui', jit: 0, wet: 0.4, fn: (o, t) => { bell(o, t, 220, 2.4, 0.13); bell(o, t, 329.6, 2.4, 0.1); return 2.5; } },
  // placement (UI on a confirmed action and the server fx; the rate limit merges the two)
  build: { rl: 0.25, fn: (o, t, p) => {
    nz(o, t, 0.2, 'lowpass', 900 * p, 180 * p, 1, 0.5); tone(o, t, 'sine', 130 * p, 55 * p, 0.22, 0.5); wood(o, t + 0.005, 700 * p, 0.25);
    return 0.25;
  } },
  deploy: { rl: 0.25, jit: 0.02, fn: (o, t, p) => {
    tone(o, t, 'sine', 170 * p, 70 * p, 0.12, 0.45); wood(o, t, 1100 * p, 0.35);
    bell(o, t + 0.07, 523 * p, 0.3, 0.06, CHIME); bell(o, t + 0.14, 784 * p, 0.35, 0.06, CHIME);
    return 0.5;
  } },
  upgrade: { rl: 0.25, jit: 0.01, wet: 0.2, fn: (o, t, p, op) => {
    for (let i = 0; i < 5; i++) wood(o, t + i * 0.025, (1500 + i * 220) * p, 0.2);
    const top = op.lvl >= 3;
    (top ? [523, 659, 784] : [523, 659]).forEach((f, i) => bell(o, t + 0.14 + i * 0.08, f * p, 0.8, 0.09, CHIME));
    if (top) { bell(o, t + 0.4, 2093 * p, 0.9, 0.04, CHIME); bell(o, t + 0.46, 2637 * p, 0.9, 0.035, CHIME); }
    return top ? 1.3 : 1;
  } },
  conv: { rl: 0.3, bus: 'ui', jit: 0.02, fn: (o, t, p) => {   // Přetavení: hammer on the anvil, a coin, the quench hiss
    bell(o, t, 1250 * p, 0.5, 0.07, METAL); nz(o, t, 0.02, 'highpass', 3000, 3000, 1, 0.2);
    bell(o, t + 0.09, 2093 * p, 0.4, 0.04, CHIME); nz(o, t + 0.05, 0.3, 'highpass', 4000, 6000, 1, 0.03, 0.05);
    return 0.5;
  } },
  sell: { rl: 0.25, jit: 0.01, fn: (o, t, p) => {
    bell(o, t, 659 * p, 0.35, 0.08, CHIME); bell(o, t + 0.11, 494 * p, 0.45, 0.08, CHIME);
    for (let i = 0; i < 3; i++) tone(o, t + 0.05 + i * 0.06, 'sine', (3200 + i * 500) * p, (3200 + i * 500) * p, 0.08, 0.03);
    return 0.6;
  } },
  // weapons and hits
  gun: { rl: 0.055, pri: 1, fn: (o, t, p) => { nz(o, t, 0.035, 'bandpass', 2200 * p, 1800 * p, 1.5, 0.45); tone(o, t, 'square', 180 * p, 90 * p, 0.025, 0.05); return 0.05; } },
  tgun: { rl: 0.09, pri: 1, fn: (o, t, p) => {
    nz(o, t, 0.06, 'bandpass', 1200 * p, 900 * p, 1.5, 0.45); tone(o, t, 'square', 110 * p, 55 * p, 0.06, 0.06); tone(o, t, 'sine', 110 * p, 50 * p, 0.08, 0.3);
    return 0.09;
  } },
  kshot: { rl: 0.06, pri: 1, fn: (o, t, p) => { tone(o, t, 'triangle', 1320 * p, 660 * p, 0.07, 0.12); nz(o, t, 0.015, 'highpass', 4000, 4000, 1, 0.15); return 0.08; } },
  snipe: { rl: 0.08, wet: 0.2, fn: (o, t, p) => {
    nz(o, t, 0.025, 'highpass', 2500, 2500, 1, 0.5); tone(o, t, 'sine', 120 * p, 40 * p, 0.22, 0.5);
    nz(o, t + 0.01, 0.45, 'lowpass', 900 * p, 200 * p, 1, 0.22, 0.02);
    return 0.47;
  } },
  flame: { rl: 0.15, pri: 1, fn: (o, t, p) => { nz(o, t, 0.28, 'lowpass', 900 * p, 700 * p, 1, 0.35, 0.03); crackle(o, t + 0.03, 3, 0.2, 0.2); return 0.3; } },
  tesla: { rl: 0.12, pri: 1, fn: (o, t, p, op) => {
    const q = p * (1 + 0.08 * Math.min(5, (op.n || 1) - 1)), b = C.createBiquadFilter(), am = C.createGain(), m = C.createOscillator(), mg = C.createGain();
    b.type = 'bandpass'; b.Q.value = 2;
    b.frequency.setValueAtTime(3000 * q, t); b.frequency.exponentialRampToValueAtTime(800 * q, t + 0.18);
    am.gain.value = 0.5; m.type = 'square'; m.frequency.value = 37; mg.gain.value = 0.5; m.connect(mg).connect(am.gain); run(m, mg, t, 0.18);
    b.connect(am).connect(o);
    tone(b, t, 'sawtooth', 60 * q, 60 * q, 0.18, 0.9, 0.002);
    crackle(o, t, 2, 0.12, 0.12);
    return 0.2;
  } },
  bite: { rl: 0.05, pri: 1, fn: (o, t, p) => { nz(o, t, 0.09, 'bandpass', 350 * p, 300 * p, 3, 0.6); tone(o, t, 'sine', 160 * p, 70 * p, 0.1, 0.3); return 0.1; } },
  clack: { rl: 0.05, pri: 1, fn: (o, t, p) => { wood(o, t, 1600 * p, 0.45); tone(o, t, 'triangle', 600 * p, 300 * p, 0.06, 0.08); return 0.08; } },
  bash: { rl: 0.12, fn: (o, t, p) => {
    tone(o, t, 'sine', 90 * p, 45 * p, 0.2, 0.5); nz(o, t, 0.12, 'lowpass', 700, 200, 1, 0.35);
    tone(o, t, 'sine', 420 * p, 420 * p, 0.4, 0.07, 0.002); tone(o, t, 'sine', 613 * p, 613 * p, 0.32, 0.05, 0.002);
    return 0.4;
  } },
  boom: { rl: 0.05, wet: 0.25, fn: (o, t, p, op) => boom(o, t, p, op.r || 1) },
  whistle: { rl: 0.3, fn: (o, t, p, op) => {
    const d = Math.max(0.3, Math.min(1.2, op.dur || 1));
    vib(o, t, 2200 * p, 500 * p, d, 0.12, 9, 25, d - 0.03);
    nz(o, t, d, 'bandpass', 2000 * p, 600 * p, 4, 0.05, d - 0.03);
    return d;
  } },
  parry: { rl: 0.1, pri: 3, jit: 0.01, wet: 0.35, duck: [6, 0.4], fn: (o, t, p) => {
    for (const [f, v, d] of [[1568, 0.16, 0.6], [2349, 0.1, 0.5], [3136, 0.07, 0.4]]) tone(o, t, 'sine', f * p, f * p, d, v, 0.001);
    nz(o, t, 0.26, 'highpass', 1500, 6000, 1, 0.16, 0.24);
    return 0.62;
  } },
  guard: { rl: 0.08, fn: (o, t, p) => { tone(o, t, 'sine', 190 * p, 90 * p, 0.06, 0.45); nz(o, t, 0.05, 'lowpass', 700, 300, 1, 0.35); return 0.07; } },
  heal: { rl: 0.4, pri: 1, jit: 0.01, fn: (o, t, p) => { [659, 831, 988].forEach((f, i) => tone(o, t + i * 0.08, 'sine', f * p, f * p, 0.4, 0.05, 0.01)); return 0.6; } },
  vet: { rl: 0.2, jit: 0.01, fn: (o, t, p) => { brass(o, t, 392 * p, 0.16, 0.07, 0.02); brass(o, t + 0.14, 523 * p, 0.4, 0.08, 0.02); return 0.55; } },
  fuse: { rl: 0.3, fn: (o, t, p) => {
    nz(o, t, 2, 'highpass', 5000, 3000, 1, 0.05, 0.05);
    for (let d = 0, iv = 0.22; d < 1.95; d += iv, iv = Math.max(0.09, iv * 0.88)) wood(o, t + d, 2000 * p, 0.2);
    return 2;
  } },
  // deaths
  zdie: { rl: 0.06, pri: 1, fn: (o, t, p) => { nz(o, t, 0.25, 'bandpass', 500 * p, 150 * p, 5, 0.7); vib(o, t, 180 * p, 90 * p, 0.2, 0.12, 14, 12, 0.01); return 0.26; } },
  zbig: { rl: 0.2, fn: (o, t, p) => {
    nz(o, t, 0.45, 'bandpass', 380 * p, 90 * p, 4, 0.8); vib(o, t, 110 * p, 50 * p, 0.4, 0.2, 9, 10, 0.02); tone(o, t, 'sine', 80 * p, 35 * p, 0.35, 0.45);
    return 0.46;
  } },
  alfaDie: { rl: 2, pri: 3, wet: 0.3, fn: (o, t, p) => {
    nz(o, t, 0.7, 'bandpass', 300 * p, 70 * p, 4, 0.8); roar(o, t, 50 * p, 30 * p, 0.9, 0.35); tone(o, t, 'sine', 70 * p, 30, 0.6, 0.45);
    [523, 659, 784, 1047].forEach((f, i) => bell(o, t + 0.5 + i * 0.08, f, 1.2, 0.07, CHIME));
    return 1.8;
  } },
  udie: { rl: 0.08, fn: (o, t, p) => {
    [0, 0.045, 0.11].forEach((d, i) => wood(o, t + d, (1500 - i * 250) * p, 0.45 - i * 0.08));
    tone(o, t, 'triangle', 500 * p, 180 * p, 0.3, 0.08);
    return 0.32;
  } },
  bdie: { rl: 0.15, wet: 0.25, fn: (o, t, p) => {
    nz(o, t, 0.9, 'lowpass', 1200 * p, 100, 1, 0.55, 0.01); tone(o, t, 'sine', 60 * p, 32, 0.5, 0.45);
    for (let i = 0; i < 5; i++) wood(o, t + 0.05 + Math.random() * 0.55, (700 + Math.random() * 1300) * p, 0.2);
    return 0.92;
  } },
  kral: { rl: 1, pri: 3, jit: 0.02, wet: 0.5, fn: (o, t, p) => { bell(o, t, 98 * p, 2.5, 0.3, GONG); boom(o, t, p, 1.2); return 2.5; } },
  // crates
  loot: { rl: 0.15, jit: 0.005, wet: 0.3, fn: (o, t, p, op) => {
    const r = Math.max(0, Math.min(4, op.rar | 0));
    [523, 587, 659, 784, 880, 1047].slice(0, r + 2).forEach((f, i) => bell(o, t + i * 0.07, f * p, 0.6, 0.08, CHIME));
    if (r < 4) return 0.6 + r * 0.07;
    choir(o, t + 0.3, [261.6, 329.6, 392], 1.2, 0.14, 0.2); bell(o, t + 0.35, 1047 * p, 1.2, 0.06, CHIME);
    return 1.6;
  } },
  drop: { rl: 1, fn: (o, t, p) => { vib(o, t, 1800 * p, 700 * p, 1.4, 0.05, 6, 15, 0.5); nz(o, t, 1.4, 'bandpass', 900, 400, 1, 0.06, 0.6); return 1.45; } },
  ping: { rl: 0.5, jit: 0, wet: 0.3, fn: (o, t, p) => { bell(o, t, 1568 * p, 0.6, 0.07, CHIME); return 0.6; } },
  land: { rl: 0.3, wet: 0.3, fn: (o, t, p, op) => {
    const r = Math.max(0, Math.min(4, op.rar | 0));
    tone(o, t, 'sine', 95 * p, 38, 0.3, 0.6); nz(o, t, 0.35, 'lowpass', 900, 100, 1, 0.45);
    bell(o, t + 0.02, 520 * p, 0.7, 0.07, METAL); bell(o, t + 0.14, 660 * 2 ** (r / 6), 0.9, 0.06 + r * 0.01, CHIME);
    return 1;
  } },
  pop: { rl: 0.2, fn: (o, t, p) => { tone(o, t, 'sine', 300 * p, 900 * p, 0.08, 0.15); bell(o, t + 0.04, 1047 * p, 0.5, 0.06, CHIME); return 0.55; } },
  chan: { rl: 0.35, pri: 1, jit: 0.01, fn: (o, t, p) => { tone(o, t, 'triangle', 420 * p, 400 * p, 0.06, 0.09); wood(o, t, 1800 * p, 0.16); return 0.08; } },
  contest: { rl: 3, wet: 0.2, fn: (o, t, p) => {
    nz(o, t, 0.45, 'bandpass', 2600 * p, 1100 * p, 9, 0.35, 0.05); nz(o, t + 0.07, 0.45, 'bandpass', 2750 * p, 1180 * p, 9, 0.3, 0.05);
    brass(o, t, 73.4 * p, 0.8, 0.07); brass(o, t, 77.8 * p, 0.8, 0.06);
    return 0.85;
  } },
  // King and war cries
  dash: { rl: 0.2, fn: (o, t, p) => { nz(o, t, 0.28, 'bandpass', 400 * p, 2400 * p, 1.2, 0.35, 0.09); nz(o, t + 0.05, 0.2, 'lowpass', 600, 250, 1, 0.15, 0.02); return 0.3; } },
  horn: { rl: 1, pri: 3, jit: 0.01, wet: 0.4, fn: (o, t, p) => {
    brass(o, t, 146.8 * p, 1.3, 0.14, 0.12); brass(o, t + 0.35, 220 * p, 1.1, 0.13, 0.1);
    drum(o, t, 65, 0.6, 0.35); drum(o, t + 0.35, 65, 0.6, 0.3);
    return 1.5;
  } },
  utok: { rl: 1, pri: 3, jit: 0.01, wet: 0.3, fn: (o, t, p) => {
    [0, 0.16, 0.32].forEach(d => drum(o, t + d, 73, 0.5, 0.35));
    brass(o, t + 0.32, 164.8 * p, 0.5, 0.1, 0.04); brass(o, t + 0.5, 246.9 * p, 0.7, 0.11, 0.04);
    return 1.25;
  } },
  promo: { rl: 0.5, pri: 3, jit: 0.005, wet: 0.3, fn: (o, t, p) => {
    [261.6, 329.6, 392, 523.3].forEach((f, i) => brass(o, t + i * 0.11, f * p, i === 3 ? 0.7 : 0.14, 0.09, 0.02));
    bell(o, t + 0.33, 1047 * p, 0.9, 0.05, CHIME);
    return 1.1;
  } },
  rise: { rl: 1, pri: 3, jit: 0, wet: 0.5, fn: (o, t) => {
    choir(o, t, [220, 329.6, 440], 1.8, 0.14, 0.7); bell(o, t + 0.6, 440, 1.6, 0.1); nz(o, t, 1.2, 'highpass', 6000, 8000, 1, 0.03, 0.9);
    return 1.8;
  } },
  bready: { rl: 0.5, jit: 0, fn: (o, t) => { bell(o, t, 2093, 0.25, 0.08, CHIME); return 0.25; } },
  whine: { rl: 0.3, pri: 3, jit: 0, fn: (o, t) => { vib(o, t, 1800, 2600, 0.45, 0.07, 18, 25, 0.35); return 0.47; } },
  aim: { rl: 0.4, jit: 0, fn: (o, t) => { vib(o, t, 1500, 2000, 0.45, 0.035, 18, 20, 0.35); return 0.47; } },
  charge: { rl: 0.25, pri: 1, fn: (o, t, p) => { tone(o, t, 'sine', 600 * p, 1200 * p, 0.3, 0.035, 0.2); return 0.32; } },
  // relic
  relic: { rl: 1, pri: 3, jit: 0, wet: 0.5, fn: (o, t, p, op) => {
    choir(o, t, op.foe ? [220, 261.6, 329.6] : [220, 277.2, 329.6], 1.8, 0.2, 0.25); bell(o, t, op.foe ? 220 : 440, 2.0, 0.14);
    return 2;
  } },
  relicOn: { rl: 3, pri: 3, jit: 0, wet: 0.5, fn: (o, t) => { choir(o, t, [110, 164.8], 2.6, 0.2, 0.8, [400, 800]); bell(o, t + 0.3, 110, 3, 0.2); return 3.3; } },
  // the dead and the Mist
  wtick: { rl: 0.5, jit: 0, fn: (o, t, p) => { wood(o, t, 1250 * p, 0.5); bell(o, t, 880 * p, 0.3, 0.08, CHIME); return 0.35; } },
  wave: { rl: 5, pri: 3, jit: 0.01, wet: 0.5, fn: (o, t, p) => {
    bell(o, t, 82.4 * p, 2.6, 0.25); choir(o, t + 0.1, [98, 146.8], 2.0, 0.16, 0.5, [400, 800]); drum(o, t, 49, 0.9, 0.4);
    return 2.6;
  } },
  groan: { rl: 0.3, pri: 1, fn: (o, t, p) => { const f = (85 + Math.random() * 50) * p; roar(o, t, f, f * 0.8, 0.7, 0.12); return 0.72; } },
  alfa: { rl: 3, pri: 3, wet: 0.4, fn: (o, t, p) => {
    roar(o, t, 55 * p, 42 * p, 1.6, 0.45); nz(o, t, 1.4, 'lowpass', 500, 150, 1, 0.2, 0.25); tone(o, t, 'sine', 45, 30, 1.2, 0.3, 0.1);
    return 1.6;
  } },
  astep: { rl: 0.25, pri: 1, fn: (o, t, p) => { tone(o, t, 'sine', 70 * p, 38, 0.25, 0.4); nz(o, t, 0.1, 'lowpass', 300, 150, 1, 0.25); return 0.26; } },
  horde: { rl: 3, pri: 3, fn: (o, t, p) => {
    for (const d of [0, 0.15, 0.32, 0.5]) { const f = (80 + Math.random() * 60) * p; roar(o, t + d, f, f * 0.75, 0.8, 0.1); }
    drum(o, t, 55, 0.7, 0.3);
    return 1.3;
  } },
  night: { rl: 10, pri: 3, jit: 0, wet: 0.6, fn: (o, t) => { for (let i = 0; i < 3; i++) bell(o, t + i * 2.2, 98, 4, 0.28); return 8.4; } },
  mist: { rl: 3, pri: 3, jit: 0.01, wet: 0.4, fn: (o, t, p) => {
    choir(o, t, [110 * p, 103.8 * p], 1.8, 0.14, 0.4, [400, 800]); vib(o, t, 196 * p, 147 * p, 1.6, 0.06, 0.8, 8, 0.5);
    nz(o, t, 1.5, 'highpass', 2500, 5000, 1, 0.07, 0.6); crackle(o, t + 0.3, 8, 1.1, 0.12);
    return 1.8;
  } },
  pdown: { rl: 1, pri: 3, fn: (o, t, p) => {
    tone(o, t, 'sine', 300 * p, 30, 0.8, 0.3); nz(o, t, 0.4, 'bandpass', 1500, 300, 1, 0.25, 0.02); crackle(o, t, 6, 0.6, 0.15);
    return 0.82;
  } },
  pup: { rl: 1, pri: 3, fn: (o, t, p) => {
    tone(o, t, 'sine', 40, 300 * p, 0.6, 0.22, 0.4); nz(o, t, 0.5, 'bandpass', 300, 1800, 1, 0.15, 0.45); crackle(o, t + 0.2, 4, 0.35, 0.12);
    return 0.62;
  } },
  // factions (FAC §6)
  emp: { rl: 0.3, pri: 3, wet: 0.3, fn: (o, t, p) => {
    tone(o, t, 'sawtooth', 1600 * p, 90 * p, 0.4, 0.1, 0.003); nz(o, t, 0.3, 'bandpass', 3000 * p, 600 * p, 2, 0.35);
    tone(o, t, 'sine', 85 * p, 40, 0.35, 0.45); crackle(o, t + 0.05, 10, 0.45, 0.25); return 0.55;
  } },
  mor: { rl: 0.3, pri: 2, wet: 0.35, fn: (o, t, p) => { nz(o, t, 1.2, 'lowpass', 1300 * p, 300 * p, 1, 0.3, 0.25); roar(o, t + 0.1, 70 * p, 55 * p, 1.0, 0.08); return 1.3; } },
  raise: { rl: 0.2, pri: 2, fn: (o, t, p) => { nz(o, t, 0.3, 'lowpass', 500 * p, 150, 1, 0.4, 0.01); vib(o, t + 0.15, 90 * p, 160 * p, 0.5, 0.1, 9, 10, 0.1); return 0.7; } },
  turn: { rl: 0.3, pri: 2, wet: 0.4, fn: (o, t, p) => { bell(o, t, 330 * p, 0.8, 0.06, CHIME); vib(o, t, 220 * p, 180 * p, 0.5, 0.06, 5, 8, 0.05); return 0.9; } },
  hangar: { rl: 0.08, pri: 1, fn: (o, t, p) => { tone(o, t, 'sine', 4200 * p, 2600 * p, 0.05, 0.05, 0.002); nz(o, t, 0.12, 'bandpass', 1500 * p, 3000 * p, 2, 0.2, 0.01); return 0.13; } },
  thorns: { rl: 0.15, pri: 1, fn: (o, t, p) => { nz(o, t, 0.08, 'highpass', 2500 * p, 2500 * p, 1, 0.3); bell(o, t, 1900 * p, 0.2, 0.04, METAL); return 0.22; } },
  thit: { rl: 0.25, fn: (o, t, p) => {
    tone(o, t, 'sine', 85 * p, 48, 0.25, 0.5); nz(o, t, 0.12, 'lowpass', 600, 200, 1, 0.35); bell(o, t, 190 * p, 0.45, 0.06, METAL);
    return 0.45;
  } },
  tding: { rl: 0.3, jit: 0.01, wet: 0.3, fn: (o, t, p) => { bell(o, t, 1318.5 * p, 0.9, 0.09, CHIME); bell(o, t, 1975.5 * p, 0.7, 0.05, CHIME); return 0.9; } },
  // danger loops (scheduled by tick)
  heart: { rl: 0.25, pri: 3, bus: 'mus', jit: 0.01, fn: (o, t) => { tone(o, t, 'sine', 62, 40, 0.13, 0.7, 0.008); tone(o, t + 0.14, 'sine', 58, 38, 0.13, 0.5, 0.008); return 0.3; } },
  alarm: { rl: 0.2, jit: 0, fn: (o, t, p, op) => { bell(o, t, op.n ? 784 : 988, 0.2, 0.07, CHIME); return 0.22; } },
  roll: { rl: 0.04, pri: 1, fn: (o, t, p) => { nz(o, t, 0.06, 'bandpass', 1600 * p, 1600 * p, 1, 0.25); tone(o, t, 'sine', 210 * p, 150 * p, 0.05, 0.12); return 0.07; } },
  geiger: { rl: 0.015, pri: 0, jit: 0.2, fn: (o, t, p) => { nz(o, t, 0.002, 'highpass', 3000 * p, 3000 * p, 1, 0.3, 0.0005); return 0.01; } },
  // weather and darkness
  thunder: { rl: 1.5, wet: 0.5, fn: (o, t, p, op) => {
    if (!op.far) nz(o, t, 0.25, 'highpass', 1200, 400, 1, 0.25, 0.005);
    nz(o, t + 0.05, 1.8, 'lowpass', 200 * p, 90, 1, op.far ? 0.3 : 0.6, 0.6); tone(o, t, 'sine', 45, 32, 1.6, op.far ? 0.12 : 0.22, 0.5);
    return 1.9;
  } },
  eclWarn: { rl: 5, pri: 3, jit: 0, wet: 0.5, fn: (o, t) => { bell(o, t, 146.8, 3, 0.25); brass(o, t + 0.2, 55, 3, 0.12, 1.2); return 3.2; } },
  ecl: { rl: 5, pri: 3, jit: 0, wet: 0.5, fn: (o, t) => { nz(o, t, 1.6, 'lowpass', 2200, 70, 1, 0.5, 0.15); bell(o, t + 0.1, 73.4, 4, 0.32, GONG); return 4.1; } },
  eclEnd: { rl: 5, pri: 3, jit: 0, wet: 0.5, fn: (o, t) => {
    [440, 554.4, 659.3, 880].forEach((f, i) => bell(o, t + i * 0.12, f, 1.4, 0.07, CHIME)); choir(o, t, [220, 277.2, 329.6], 2.2, 0.14, 0.6);
    return 2.3;
  } },
  // end-of-match music stingers (audioEnd)
  finWin: { rl: 1, pri: 3, bus: 'mus', jit: 0, fn: (o, t) => {
    drum(o, t, 55, 1.4, 0.6);
    [220, 277.2, 329.6, 440, 554.4, 659.3].forEach((f, i) => brass(o, t + i * 0.12, f, 1.8 - i * 0.12, 0.07, 0.03));
    for (const f of [110, 164.8, 220]) brass(o, t + 0.72, f, 2.2, 0.08, 0.2);
    nz(o, t + 0.72, 2.2, 'highpass', 6000, 4000, 1, 0.08, 0.01); bell(o, t + 0.72, 440, 2.5, 0.12);
    return 3.2;
  } },
  finLose: { rl: 1, pri: 3, bus: 'mus', jit: 0, fn: (o, t) => {
    [329.6, 293.7, 261.6, 220].forEach((f, i) => brass(o, t + i * 0.35, f, 0.6, 0.08, 0.04));
    bell(o, t + 1.4, 73.4, 3.5, 0.35, GONG); choir(o, t + 1.4, [110, 130.8], 2.5, 0.16, 0.5);
    return 4;
  } },
  finDraw: { rl: 1, pri: 3, bus: 'mus', jit: 0, fn: (o, t) => {
    brass(o, t, 110, 2.5, 0.06, 0.4); brass(o, t, 164.8, 2.5, 0.05, 0.4); bell(o, t + 0.2, 220, 2.5, 0.14); bell(o, t + 0.9, 329.6, 2.2, 0.1);
    return 3.1;
  } },
};

/* ---------------- music: drone + intensity layers on a lookahead scheduler ---------------- */
const BASS = [0, 0, 7, 10, 12, 10, 7, 5, 0, 0, 3, 5, 7, 5, 3, -2];   // A minor pentatonic, eighths over 2 bars
function musStart() {
  const t = C.currentTime, keep = [], tuned = [];
  const L = [0, 1, 2, 3].map(() => { const g = C.createGain(); g.gain.value = 0; g.connect(A.duck); return g; });
  const mod = (f, depth, param) => {
    const s = C.createOscillator(), g = C.createGain();
    s.frequency.value = f; g.gain.value = depth; s.connect(g); keep.push(s);
    if (param) g.connect(param);
    return g;
  };
  const osc = (type, f, det, out) => {
    const s = C.createOscillator();
    s.type = type; s.frequency.value = f; s.detune.value = det; s.connect(out);
    keep.push(s); tuned.push([s, f]);
    return s;
  };
  const filt = (type, f, q, out) => { const b = C.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; b.connect(out); return b; };
  const gain = (v, out) => { const g = C.createGain(); g.gain.value = v; g.connect(out); return g; };
  // L0: detuned triangles on A1 and E2 under a slowly breathing low-pass, a sung open fifth, and wind
  const lp = filt('lowpass', 400, 1, gain(0.025, L[0]));
  mod(0.07, 150, lp.frequency);
  for (const f of [55, 82.41]) for (const d of [-3, 3]) osc('triangle', f, d, lp);
  const cg = gain(0.05, L[0]), fa = filt('bandpass', 700, 5, cg), fb = filt('bandpass', 1150, 8, cg), vb = mod(4.6, 7);
  mod(0.045, 0.025, cg.gain);
  for (const f of [110, 164.81]) for (const d of [-9, 0, 9]) { const s = osc('sawtooth', f, d, fa); s.connect(fb); vb.connect(s.detune); }
  const n = C.createBufferSource(), wind = gain(0.05, L[0]), wb = filt('bandpass', 500, 0.8, wind);
  n.buffer = A.noise; n.loop = true; n.connect(wb); keep.push(n);
  mod(0.11, 0.025, wind.gain); mod(0.05, 250, wb.frequency);
  keep.forEach(s => s.start(t));
  keep[0].onended = () => L.forEach(g => g.disconnect());
  L[0].gain.setTargetAtTime(1, t, 1);
  M = { L, keep, tuned, wind, on: [true, false, false, false], step: 0, bar: 0, next: t + 0.1, bpm: 84, night: false, dark: false };
}
function musStop(fade) {
  if (!M) return;
  const t = C.currentTime;
  for (const g of M.L) g.gain.setTargetAtTime(0, t, fade / 4);
  for (const s of M.keep) s.stop(t + fade + 0.1);
  M = null;
}
// L1 tom on beats 1 and 3, L2 plucked bass ostinato + bone shaker, L3 tritone stab every 2 bars (100 BPM); night tolls every 4 bars
function musTick(now) {
  if (M.next < now) M.next = now + 0.03;
  const live = i => M.on[i] || M.L[i].gain.value > 0.003;
  while (M.next < now + 0.12) {
    const s = M.step, t = M.next, r = M.night ? 2 ** (-1 / 12) : 1;
    if (s === 0) M.bpm = M.on[3] ? 100 : 84;
    if (live(1) && s % 8 === 0) drum(M.L[1], t, 55 * r, 0.8, s ? 0.3 : 0.42);
    if (live(2)) {
      if (s % 2 === 0) pluck(M.L[2], t, 55 * r * 2 ** (BASS[(M.bar % 2) * 8 + s / 2] / 12), 0.12);
      nz(M.L[2], t, 0.03, 'highpass', 7000, 7000, 1, s % 4 === 2 ? 0.035 : 0.014);
    }
    if (live(3) && s === 0 && M.bar % 2 === 0) {
      for (const f of [220, 311.13]) brass(M.L[3], t, f * r, 0.7, 0.045, 0.01);
      tone(M.L[3], t, 'sine', 110 * r, 110 * r, 0.9, 0.08);
    }
    if (M.night && s === 0 && M.bar % 4 === 0) bell(M.L[0], t, 220 * r, 4, 0.05);
    M.next += 15 / M.bpm;
    if ((M.step = (s + 1) % 16) === 0) M.bar++;
  }
}
function musLayers(hot, night, dark, now) {
  const th = [0, 0.3, 0.55, 0.8];
  for (let i = 1; i < 4; i++) {
    const on = (i === 3 && hot) || (M.on[i] ? A.I > th[i] - 0.07 : A.I > th[i]);
    if (on !== M.on[i]) { M.on[i] = on; M.L[i].gain.setTargetAtTime(on ? 1 : 0, now, 0.7); }
  }
  if (night !== M.night) {
    M.night = night;
    for (const [s, f] of M.tuned) s.frequency.setTargetAtTime(night ? f * 2 ** (-1 / 12) : f, now, 1.5);
  }
  if (dark !== M.dark) { M.dark = dark; M.wind.gain.setTargetAtTime(dark ? 0.11 : 0.05, now, 1.5); }
}

/* ---------------- 25 ms clock: music lookahead and the danger loops ---------------- */
function tick() {
  try {
    if (!C || C.state !== 'running') return;
    const now = C.currentTime, ahead = now + 0.12;
    prune(now);
    if (performance.now() - A.lastSnap > 3000) { musStop(1.5); calm(); }   // left the match without audioStop
    if (M) musTick(now);
    every('hb', A.hb > 0, ahead, t => { play('heart', null, { delay: t - now, vol: A.crit ? 1.3 : 1 }); return 60 / A.hb; });
    every('ck', A.ck, ahead, t => { play('alarm', null, { delay: t - now, n: A.alt ^= 1 }); return 0.25; });
    every('roll', A.gck > 0, ahead, t => { play('roll', null, { delay: t - now, vol: 0.4 + 0.06 * A.gck }); return Math.max(0.06, 0.2 - 0.014 * A.gck); });
    every('geiger', A.geiger > 0, ahead, t => { play('geiger', A.gx, { delay: t - now }); return -Math.log(1 - Math.random()) / A.geiger; });
    every('rumble', !!(M && M.night), ahead, t => {
      if (t > A.nx.rumble0) play('thunder', 2 + Math.random() * 12, { delay: t - now, far: true });
      return 14 + Math.random() * 10;
    });
  } catch (e) { warn(e); }
}
// fn(t) plays one event at time t and returns the gap to the next one
function every(key, on, ahead, fn) {
  if (!on) { A.nx[key] = 0; return; }
  let t = A.nx[key];
  if (!t || t < C.currentTime) { t = C.currentTime + 0.02; if (key === 'rumble') A.nx.rumble0 = t; }
  while (t < ahead) t += fn(t);
  A.nx[key] = t;
}
function calm() { A.hb = 0; A.ck = false; A.gck = 0; A.geiger = 0; muffle(false); }

/* ---------------- snapshot → sounds ---------------- */
const FX_ANY = { k: 'gun', t: 'tgun', s: 'snipe', f: 'flame', h: 'heal', c: 'fuse', b: 'boom', H: 'hangar' };
const FX_SIDE = { p: 'parry', g: 'guard', v: 'vet', r: 'sell', D: 'dash', U: 'horn', R: 'relic', P: 'promo', E: 'emp', M: 'mor', Z: 'raise', W: 'turn' };
const mine = x => (S.side === 0 ? x < S.half : x >= S.W - S.half);
const inMistX = x => (typeof inMist === 'function' ? inMist(x) : x >= S.mist[0] && x <= S.mist[1]);
const thX = s => (s === 0 ? -0.5 : S.W - 0.5);
const homeX = s => (s === 0 ? 2.5 : S.W - 3.5);
const catOf = e => (S.defs && S.defs[e.kind] ? S.defs[e.kind].cat : '');
function reset() {
  A.ended = false; A.ids = new Set(); A.alfa.clear(); A.crates.clear(); A.whist.clear();
  A.I = 0.15; A.thT = A.waveT = -99;
  calm();
}
function onSnap(m, prev, gone) {
  if (!C || !m) return;
  const now = C.currentTime, me = S.side, foe = 1 - me, kr = m.kr, pk = prev && prev.kr;
  A.lastSnap = performance.now();
  if (!prev || m.tm < prev.tm) reset();
  if (optKey() !== A.optKey) apply();
  if (!M && !A.ended) musStart();
  const kingDied = !!(kr && pk && kr.dead > 0 && !(pk.dead > 0));
  let zc = 0, zx = null, bashed = false;
  for (const f of m.fx || []) {
    const ty = f[0], x = f[1], fo = f[5] !== me;
    if (FX_ANY[ty]) play(FX_ANY[ty], x, { r: f[3] });
    else if (FX_SIDE[ty]) play(FX_SIDE[ty], x, { foe: fo });
    else if (ty === 'q') play('kshot', x, { foe: fo, st: fo ? -3 : 2 });
    else if (ty === 'z') { zc++; if (zx === null) zx = x; }
    else if (ty === 'm') {
      if (f[3] < 0 || f[3] > S.W - 1) { play('bash', f[3]); bashed = true; }
      else {
        play(f[5] === 2 ? 'bite' : 'clack', x);
        const tb = S.bmap && S.bmap.get(Math.round(f[3]) + ',' + Math.round(f[4]));   // melee into an Ostnatá zeď: thorns bite back
        if (tb && tb.kind === 'ostnata' && tb.side !== f[5]) play('thorns', f[3], { foe: tb.side !== me });
      }
    } else if (ty === 'a') {
      const tg = S.ents.get(f[6]);
      if (kr && f[6] === kr.id) play('whine', f[3]);
      else if (!fo) play('charge', x);
      else if (tg && tg.side === me) play('aim', f[3]);
    } else if (ty === 'x') {
      if (f[5] === 'k') play('kral', x, { foe: f.length > 8 ? f[8] !== me : !kingDied });
      else if (f[5] === 'z') play(f[7] === 'alfa' ? 'alfaDie' : f[7] === 'obr' ? 'zbig' : 'zdie', x);
      else play(f[5] === 'b' ? 'bdie' : 'udie', x);
    }
    else if (ty === 'n') play(f[3] ? 'deploy' : 'build', x, { foe: fo, st: fo ? -4 : 0 });
    else if (ty === 'u') play('upgrade', x, { foe: fo, lvl: f[3] });
    else if (ty === 'o') play('loot', x, { foe: fo, rar: f[3] });
  }
  if (zc) play('tesla', zx, { n: zc });
  for (const [code, a] of m.ev || []) {
    if (code === 'wave') { play('wave'); A.waveT = now; }
    else if (code === 'alfa') play('alfa', 7.5);
    else if (code === 'alfa_dead') play('alfaDie', 7.5);
    else if (code === 'horde') play('horde');
    else if (code === 'kk' && !kingDied) play('kral', null, { foe: true });
    else if (code === 'kr' && a !== me) play('rise', null, { foe: true });
    else if (code === 'ecl_warn') play('eclWarn');
    else if (code === 'ecl') play(a ? 'ecl' : 'eclEnd');
    else if (code === 'night') play('night');
    else if (code === 'mist') play('mist');
    else if (code === 'ult') play('horn', null, { foe: a !== me });
    else if (code === 'utok') play('utok', null, { foe: a !== me });
    else if (code === 'relic_on') play('relicOn', 7.5);
    else if (code === 'relic') play('relic', 7.5, { foe: a !== me });
    else if (code === 'promo') play('promo', null, { foe: a !== me });
    else if (code === 'contest') { const c = (m.cr || []).find(r => r[0] === a); play('contest', c ? c[1] : null); }
  }
  const dark = !!(m.ni || (m.ec && m.ec[0] === 2));
  if (prev) {
    if (!m.ni && m.nw !== prev.nw && m.nw >= 1 && m.nw <= 3) play('wtick', null, { st: m.nw === 1 ? 5 : 0 });
    if (m.nw > prev.nw + 3) { play('wave'); A.waveT = now; }
    if (m.ni && !prev.ni) play('night');
    if (m.st > prev.st) play('mist');
    // ec phase 1 is the whole countdown to the next eclipse; the warning is its last 15 s
    const e0 = prev.ec ? prev.ec[0] : 0, e1 = m.ec ? m.ec[0] : 0, ecW = e => !!e && e[0] === 1 && e[1] <= 15;
    if (e1 === 2 && e0 !== 2) play('ecl');
    else if (e0 === 2 && e1 !== 2) play('eclEnd');
    else if (ecW(m.ec) && !ecW(prev.ec)) play('eclWarn');
    for (const s of [me, foe]) {
      if (!(prev.out[s] > 0) && m.out[s] > 0) play('pdown', homeX(s), { foe: s !== me });
      if (prev.out[s] > 0 && !(m.out[s] > 0) && s === me) play('pup', homeX(s));
    }
    const lost = prev.th[me] - m.th[me];
    if (lost > 0) A.thT = now;
    if (lost >= 5 && !bashed) play('thit', thX(me));
    if (prev.th[foe] - m.th[foe] >= 50) play('tding', thX(foe));
    const cv = S.conv || [30, 10];
    if (m.r && prev.r && m.r[1] - prev.r[1] >= cv[1] && prev.r[0] - m.r[0] >= cv[0] - 5) play('conv');
    if (kingDied) { const g = gone && gone.get(pk.id); play('kral', g ? g.x : thX(me)); }
    if (kr && pk && pk.dead > 0 && !(kr.dead > 0)) play('rise', thX(me));
    if (kr && pk && kr.id && pk.bcd > 0 && !(kr.bcd > 0)) { const k = S.ents.get(kr.id); play('bready', k ? k.x : null); }
  }
  // crates: announcement, last-3-s beacon, landing, own channel progress
  const cseen = new Set();
  for (const c of m.cr || []) {
    const [id, x, , r, land] = c, pc = A.crates.get(id), ch = c[6 + me] || 0;
    cseen.add(id);
    if (!pc) { if (prev) play(land > 0 ? 'drop' : 'pop', x, { rar: r }); }
    else {
      if (land > 0 && Math.ceil(land) <= 3 && Math.ceil(land) < Math.ceil(pc.land)) play('ping', x, { st: (3 - Math.ceil(land)) * 2 });
      if (pc.land > 0 && land <= 0) play('land', x, { rar: r });
      if (ch > pc.ch + 0.001 && ch < 1) play('chan', x, { st: ch * 12 });
    }
    A.crates.set(id, { land, ch });
  }
  for (const id of A.crates.keys()) if (!cseen.has(id)) A.crates.delete(id);
  // Nálet: falling whistle during the last second
  const sseen = new Set();
  for (const [x, y, tl, s] of m.ns || []) {
    const k = x + ',' + y + ',' + s;
    sseen.add(k);
    if (tl <= 1.05 && !A.whist.has(k)) { A.whist.add(k); play('whistle', x, { dur: tl }); }
  }
  for (const k of A.whist) if (!sseen.has(k)) A.whist.delete(k);
  // entities: Alfa roar and steps, zombies rising from the Mist
  const ids = new Set();
  for (const e of S.ents.values()) {
    ids.add(e.id);
    if (e.kind === 'alfa') {
      const cell = e.cx * 100 + e.cy, pc = A.alfa.get(e.id);
      if (pc === undefined) { if (prev) play('alfa', e.cx); } else if (pc !== cell) play('astep', e.cx);
      A.alfa.set(e.id, cell);
    } else if (prev && !A.ids.has(e.id) && catOf(e) === 'z' && inMistX(e.cx) && m.v && m.v[e.cy * S.W + e.cx] === '1') play('groan', e.cx);
  }
  A.ids = ids;
  for (const id of A.alfa.keys()) if (!ids.has(id)) A.alfa.delete(id);
  // danger loops read by tick()
  const k = kr && kr.id ? S.ents.get(kr.id) : null, th = m.th[me] / (S.throneMax || 3000);
  A.geiger = k && !A.ended && inMistX(k.cx) ? 6 + 6 * (1 - k.hp / Math.max(1, k.maxhp)) : 0;
  A.gx = k ? k.x : null;
  A.hb = !A.ended && th > 0 && th < 0.35 ? 60 + 50 * (1 - th / 0.35) : 0;
  A.crit = th < 0.15;
  A.ck = !A.ended && m.ck[me] > 0;
  A.gck = !A.ended && m.ck[foe] > 0 ? m.ck[foe] : 0;
  muffle(!A.ended && !!(kr && kr.dead > 0));
  if (now - A.iT >= 0.25) intensity(m, now, dark);
  if (M) musLayers(m.ck[0] > 0 || m.ck[1] > 0 || !!m.ni, !!m.ni, dark, now);
}
function intensity(m, now, dark) {
  let near = 0, units = 0, alfa = false;
  for (const e of S.ents.values()) {
    const cat = catOf(e);
    if (e.side === S.side || (cat !== 'u' && cat !== 'z')) continue;
    if (e.kind === 'alfa') alfa = true;
    if (cat === 'u') units++;
    if (mine(e.cx)) near++;
  }
  const want = Math.min(1, 0.15 + 0.06 * Math.min(near, 8) + (now - A.thT < 4 ? 0.25 : 0) + (units >= 3 ? 0.2 : 0)
    + (m.ck[0] > 0 || m.ck[1] > 0 ? 0.3 : 0) + (m.ni ? 0.25 : 0) + (dark ? 0.2 : 0) + (alfa ? 0.2 : 0) + (now - A.waveT < 5 ? 0.15 : 0));
  const dt = Math.min(1, now - A.iT);
  A.iT = now;
  A.I = want > A.I ? Math.min(want, A.I + 0.5 * dt) : Math.max(want, A.I - 0.1 * dt);
}
function end(result) {
  if (!C) return;
  A.ended = true;
  calm();
  musStop(0.4);
  play(result === 'win' ? 'finWin' : result === 'lose' ? 'finLose' : 'finDraw');
}
function stop() { if (!C) return; A.ended = true; calm(); musStop(1); }

const safe = fn => (...a) => { try { fn(...a); } catch (e) { warn(e); } };
Object.assign(window, { sfx: safe((name, x = null, opt = {}) => play(name, x, opt)), audioOnSnap: safe(onSnap),
  audioApplyOpts: safe(apply), audioEnd: safe(end), audioStop: safe(stop) });
})();
