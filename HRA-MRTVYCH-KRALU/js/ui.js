'use strict';
/* ---------------- networking ---------------- */
// Reconnect only briefly and only while the tab is visible: a forgotten background tab
// must never grab a player slot when the server is started again later.
const MAX_RETRY = 10;
let retries = 0, closeWhy = '';
function connect() {
  if (location.protocol === 'file:') {
    $('#err').textContent = 'Hru spusť přes „Spustit server.bat“ a otevři adresu, kterou server vypíše.';
    $('#readyBtn').disabled = true;
    return;
  }
  if (S.ws) return;
  S.kicked = false; closeWhy = '';
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  S.ws = ws;
  ws.onopen = () => { send({ t: 'hello', name: $('#name').value }); };
  ws.onmessage = ev => { let m; try { m = JSON.parse(ev.data); } catch (e) { return; } onMsg(m); };
  ws.onclose = () => {
    if (S.ws !== ws) return;
    S.ws = null;
    if (S.inGame) { S.inGame = false; S.ending = false; showLobby(); }
    clearLobby();
    if (S.kicked) return setErr('Tvé místo uvolnil jiný hráč (nebyl jsi připraven).', true);
    if (!document.hidden && retries < MAX_RETRY) {
      retries++;
      setErr((closeWhy || 'Spojení se serverem ztraceno.') + ` Zkouším znovu… (${retries}/${MAX_RETRY})`);
      setTimeout(connect, 2000);
    } else setErr(closeWhy || 'Nejsi připojen k serveru.', true);
  };
}
function send(o) { if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(o)); }
function setErr(text, withButton) {
  $('#err').innerHTML = esc(text) + (withButton ? ' <button class="btn small" id="reconnect">Připojit znovu</button>' : '');
  const b = $('#reconnect');
  if (b) b.onclick = () => { retries = 0; connect(); };
}
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !S.ws && !S.kicked && retries < MAX_RETRY && location.protocol !== 'file:') connect();
});

// Message dispatch. The lobby and the catalogs are handled by lobby.js through the bus; unknown types become 'm:<t>'.
function onMsg(m) {
  if (m.t === 'defs') { onDefs(m); emit('defs', m); }
  else if (m.t === 'lobby') { retries = 0; emit('lobby', m); }
  else if (m.t === 'full') closeWhy = 'Server je plný (moc otevřených oken).';
  else if (m.t === 'kicked') S.kicked = true;
  else if (m.t === 'start') { startGame(m); emit('start', m); }
  else if (m.t === 's') { if (S.inGame && !S.ending) { const prev = S.snap; onSnap(m); emit('snap', m, prev); } }
  else if (m.t === 'end') endGame(m);
  else emit('m:' + m.t, m);
}
// sound hook: audio.js is optional, a missing module must never break the game
function uiSfx(name, x = null, opt) { if (typeof sfx === 'function') sfx(name, x, opt || {}); }
// restartable CSS animation class
function flashCls(el, cls, ms = 600) {
  if (!el) return;
  el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
  clearTimeout(el['_t' + cls]); el['_t' + cls] = setTimeout(() => el.classList.remove(cls), ms);
}
const mmss = t => { t = Math.max(0, Math.ceil(t)); return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0'); };
const dec = v => String(v).replace('.', ',');

/* ---------------- catalogs ---------------- */
// Generic part of 'defs'; the lobby (types, maps, deck) is filled in by lobby.js on the bus event.
function onDefs(m) {
  Object.assign(S, { defs: m.defs, research: m.research, branches: m.branches, cmds: m.cmds, cmds0: m.cmds, base: m.base, pool: m.pool,
    recommended: m.recommended, deckSize: m.deckSize, rarity: m.rarity, dobaAt: m.dobaAt,
    conv: m.conv && m.conv.length >= 2 ? [m.conv[0], m.conv[1], m.conv[2] || 1] : [30, 10, 2], relicFrom: m.relicFrom || 120, relicFrom0: m.relicFrom || 120, relicDef: m.relic || null, relicZone: m.relic || null });
  $('#ver').textContent = 'v' + m.ver;
  $('#convBtn').title = `Přetavit ${S.conv[0]} ⚡ na ${S.conv[1]} 🔩 (C)` + (S.conv[2] > 1 ? ` · od Doby ${roman(S.conv[2])}` : '');
}

// Procedural crown for the logo and the end screen: 'win' gilt, 'lose' cracked and tilted, 'draw' iron.
function uiCrown(c, state = 'win') {
  const dpr = Math.min(window.devicePixelRatio || 1, 2), w = c.clientWidth || c.width, h = c.clientHeight || c.height;
  c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
  const g = c.getContext('2d'), s = Math.min(w / 2.5, h / 1.75);
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  g.translate(w / 2, h * 0.6);
  g.beginPath(); g.ellipse(0, s * 0.55, s * 1.05, s * 0.12, 0, 0, TAU); g.fillStyle = 'rgba(0,0,0,.35)'; g.fill();
  if (state === 'lose') { g.translate(s * 0.12, s * 0.12); g.rotate(-0.28); }
  g.scale(s, s);
  const metal = { win: ['#fff0b8', '#d8b45a', '#8a6a2a'], lose: ['#b9a372', '#7a6232', '#3a2c12'], draw: ['#d4d8dd', '#8a8e96', '#45484d'] }[state];
  const gr = g.createLinearGradient(0, -0.8, 0, 0.5);
  gr.addColorStop(0, metal[0]); gr.addColorStop(0.55, metal[1]); gr.addColorStop(1, metal[2]);
  const tips = [[-1, -0.5], [-0.5, -0.62], [0, -0.8], [0.5, -0.62], [1, -0.5]];
  g.beginPath(); g.moveTo(-0.86, 0.22);
  [[-1, -0.5], [-0.72, -0.08], [-0.5, -0.62], [-0.25, -0.14], [0, -0.8], [0.25, -0.14], [0.5, -0.62], [0.72, -0.08], [1, -0.5]].forEach(([x, y]) => g.lineTo(x, y));
  g.lineTo(0.86, 0.22); g.closePath();
  g.fillStyle = gr; g.fill(); g.lineJoin = 'round'; g.strokeStyle = '#2a1d0c'; g.lineWidth = 0.045; g.stroke();
  g.beginPath(); g.moveTo(-0.92, 0.16); g.lineTo(0.92, 0.16); g.lineTo(0.9, 0.46); g.lineTo(-0.9, 0.46); g.closePath();
  g.fillStyle = gr; g.fill(); g.stroke();
  tips.forEach(([x, y], i) => {
    if (state === 'lose' && i === 3) return;
    g.beginPath(); g.arc(x, y - 0.06, 0.08, 0, TAU); g.fillStyle = state === 'draw' ? '#c3c7cd' : '#f3e9d2'; g.fill(); g.stroke();
  });
  [[-0.55, '#2e7a5e'], [0, '#c23b2e'], [0.55, '#2e7a5e']].forEach(([x, col]) => {
    g.beginPath(); g.ellipse(x, 0.31, 0.11, 0.09, 0, 0, TAU); g.fillStyle = state === 'draw' ? '#5a5d63' : col; g.fill(); g.lineWidth = 0.03; g.stroke();
  });
  if (state === 'lose') {
    g.beginPath(); g.moveTo(0.1, -0.6); g.lineTo(-0.05, -0.3); g.lineTo(0.12, -0.12); g.lineTo(-0.04, 0.12); g.lineTo(0.1, 0.46);
    g.strokeStyle = '#120c06'; g.lineWidth = 0.05; g.stroke();
    g.beginPath(); g.moveTo(0.5, -0.62); g.lineTo(0.62, -0.3); g.lineTo(0.42, -0.36); g.closePath(); g.fillStyle = '#120c06'; g.fill();
  }
}

/* ---------------- settings popover ---------------- */
const SPK = [
  '<svg viewBox="0 0 20 20"><path d="M3 7.5h3.2L10.5 4v12L6.2 12.5H3z"/><path d="M13 6.6a5 5 0 0 1 0 6.8M15.2 4.4a8 8 0 0 1 0 11.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  '<svg viewBox="0 0 20 20"><path d="M3 7.5h3.2L10.5 4v12L6.2 12.5H3z"/><path d="M13 7.5l5 5M18 7.5l-5 5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
];
function applyOpt() {
  save('hmk_opt', JSON.stringify(S.opt));
  document.body.classList.toggle('calm', S.opt.calm);
  for (const b of document.querySelectorAll('.optBtn')) { b.innerHTML = SPK[S.opt.mute ? 1 : 0]; b.classList.toggle('muted', S.opt.mute); }
  const pop = $('#optPop');
  for (const el of pop.querySelectorAll('[data-o]')) { if (el.type === 'checkbox') el.checked = !!S.opt[el.dataset.o]; else el.value = S.opt[el.dataset.o]; }
  for (const el of pop.querySelectorAll('[data-v]')) el.textContent = S.opt[el.dataset.v];
  for (const b of pop.querySelectorAll('[data-shake]')) b.classList.toggle('on', +b.dataset.shake === S.opt.shake);
  if (typeof audioApplyOpts === 'function') audioApplyOpts();
}
function toggleMute() {
  S.opt.mute = !S.opt.mute;
  applyOpt();
  if (S.inGame) toast(S.opt.mute ? 'Zvuk vypnut (M).' : 'Zvuk zapnut (M).');
}
function optOpen(btn) {
  const pop = $('#optPop');
  if (!pop.classList.contains('hidden') || !btn) { pop.classList.add('hidden'); return; }
  pop.classList.remove('hidden');
  const r = btn.getBoundingClientRect();
  pop.style.top = Math.round(r.bottom + 8) + 'px';
  pop.style.left = Math.round(Math.max(8, Math.min(innerWidth - pop.offsetWidth - 8, r.right - pop.offsetWidth))) + 'px';
  uiSfx('click');
}
const optShown = () => !$('#optPop').classList.contains('hidden');
$('#optPop').addEventListener('input', ev => {
  const el = ev.target, k = el.dataset.o;
  if (!k) return;
  S.opt[k] = el.type === 'checkbox' ? el.checked : +el.value;
  applyOpt();
});
$('#optPop').addEventListener('change', ev => ev.target.blur());
$('#optPop').addEventListener('pointerdown', ev => {
  const b = ev.target.closest('[data-shake]');
  if (!b) return;
  ev.preventDefault();
  S.opt.shake = +b.dataset.shake; applyOpt(); uiSfx('tick');
});
document.addEventListener('pointerdown', ev => {
  if (optShown() && !ev.target.closest('#optPop') && !ev.target.closest('.optBtn')) $('#optPop').classList.add('hidden');
}, true);
for (const b of document.querySelectorAll('.optBtn')) b.addEventListener('click', () => optOpen(b));

/* ---------------- game setup ---------------- */
function startGame(m) {
  Object.assign(S, {
    side: m.side, names: m.names, mode: m.mode, myDeck: m.deck, W: m.w, H: m.h, half: m.half, mist: m.mist,
    type: m.type || 'souboj', solo: !!m.solo, tut: !!m.tut, map: m.map || null, theme: (m.map && m.map.theme) || 'ruiny', paused: false,
    kit: Array.isArray(m.kit) ? m.kit : S.base,
    horde: m.horde, throneMax: m.throne, thMax: [m.throne, m.throne], snap: null, pick: null, sel: null, inGame: true, ending: false, sideHtml: '', resHtml: '',
    kp: null, seenEnemy: false, keys: {}, inp: { mx: 0, my: 0, b: false, r: false, d: false, u: false }, choose: null,
    zk: [], streakT: 0, readyT: 0, shineT: 0, resTw: null,
    // factions: both sides' ids (the foe's is revealed here), own prices, research costs, merged commands, King perk, Doba overrides
    facs: Array.isArray(m.fac) && m.fac.length === 2 ? m.fac : ['bez', 'bez'], costs: m.costs || null, rcost: m.rcost || null,
    cmds: m.cmds || S.cmds0 || S.cmds, perk: m.perk || null, fdoba: m.doba || null,
  });
  // per-side throne maximum (puzzles and Výuka start with other values than m.throne)
  const tmx = m.puzzle && Array.isArray(m.puzzle.throne) ? m.puzzle.throne : Array.isArray(m.thmax) ? m.thmax : null;
  if (tmx && tmx.length === 2) S.thMax = tmx.map(v => Math.max(1, +v || m.throne));
  S.throneMax = S.thMax[S.side];
  // Relikvie: per game (puzzles wake it at 0, Přežití and Výuka have none); an older server sends no relic_at
  S.noRelic = m.relic_at === null;
  S.relicFrom = typeof m.relic_at === 'number' ? m.relic_at : S.noRelic ? 1e9 : (S.relicFrom0 || 120);
  S.ents.clear(); S.ghosts.clear(); S.bmap.clear(); S.fx = []; S.aims.clear(); S.lasers = [];
  S.steps = new Set(); S.shownTips = new Set();
  // the Relikvie sits in columns 7-8 on every map, its rows come from the map (defs.maps[].relic = [y0, y1])
  const mp = (S.maps || []).find(x => m.map && x.id === m.map.id);
  S.relicZone = mp && mp.relic ? [7, 8, mp.relic[0], mp.relic[1]] : S.relicDef || [7, 8, 3, 5];
  S.slots = [...S.kit, ...m.deck].slice(0, 10).map((id, i) => ({ id, label: SLOT_LABELS[i], code: SLOT_CODES[i] }));
  $('#lobby').classList.add('hidden'); $('#endOv').classList.add('hidden'); $('#helpOv').classList.add('hidden'); $('#optPop').classList.add('hidden');
  $('#game').classList.remove('hidden');
  $('#toasts').innerHTML = ''; $('#banner').innerHTML = ''; $('#marks').innerHTML = '';
  annClear();
  $('#thMeN').innerHTML = `${facEmb(S.side)}<span>Tvůj trůn · ${esc(S.names[S.side])}</span>`;
  $('#thFoeN').innerHTML = `${facEmb(1 - S.side)}<span>Soupeř · ${esc(S.names[1 - S.side])}</span>`;
  $('#thMeN').title = facHudTip(S.side); $('#thFoeN').title = facHudTip(1 - S.side);
  $('#thMeBar').className = 'bar s' + 'ab'[S.side];
  $('#thFoeBar').className = 'bar s' + 'ab'[1 - S.side];
  buildBar();
  resize();
  if (S.type !== 'puzzle' && S.type !== 'vyuka') {
    const nm = { souboj: 'Zápas', preziti: 'Přežití', vycvik: 'Výcvik' }[S.type] || 'Zápas';
    toast(nm + ' začíná (' + (S.mode === 'kral' ? 'režim Král' : 'režim Stratég') + '). Braň svůj trůn vlevo!');
    const ff = S.facs[1 - S.side];
    if (ff && ff !== 'bez' && facInfo(ff)) toast(`Soupeř hraje za frakci ${facInfo(ff).name}. ${facInfo(ff).motto}`);
  }
}
// Faction emblem for the top bar (image with the faction's charge inside the side's shield or roundel) and its passives tooltip
function facEmb(side) {
  const f = S.facs[side] || 'bez';
  return typeof emblemImg === 'function' ? `<img class="emb femb-hud" src="${emblemImg(f, side, 20)}" alt="">` : EMB[side];
}
function facHudTip(side) {
  const f = S.facs[side] || 'bez', i = facInfo(f);
  if (!i) return f === 'bez' ? 'Bez frakce: původní pravidla.' : facName(f);
  const t = [`${i.name}: ${i.motto}`].concat((i.passives || []).map(p => '• ' + p));
  if (side === S.side) {
    if (S.perk) t.push(`Král, ${S.perk.name}: ${S.perk.desc}`);
    else if (S.mode === 'strateg') for (const v of Object.values(i.cmdv || {})) t.push(`Stratég, ${v.name}: ${v.desc}`);
  }
  return t.join('\n');
}

function barBtn(attrs, col, icon, seal, name, cost) {
  return `<button class="bb" tabindex="-1" ${attrs} style="--c:${col}"><span class="medal">${iconTag(icon, col)}<span class="cdt"></span></span>`
    + `<span class="bt"><b>${esc(name)}</b><span class="c" data-cost>${cost}</span></span>`
    + (seal ? `<span class="seal">${seal}</span>` : '') + '<span class="badge"></span><i class="cdv"></i></button>';
}
function buildBar() {
  let h = '';
  S.slots.forEach((s, i) => {
    if (i === S.kit.length) h += '<div class="sep"></div>';
    h += barBtn(`data-slot="${i}"`, cardCol(s.id), s.id, s.label, S.defs[s.id].name, '');
  });
  h += '<div class="sep"></div>' + barBtn('data-horde="1"', PAL.flesh, 'horde', 'T', 'Tlupa', '');
  if (S.mode === 'strateg') {
    h += '<div class="sep"></div>';
    for (const [id, c] of Object.entries(S.cmds)) h += barBtn(`data-cmd="${id}"`, PAL.moon, id, c.key, c.name, `obnova ${c.cd} s`);
    h += barBtn('data-squad="1"', PAL.moon, 'relic', 'H', 'Četa na Relikvii', 'obnova ' + (S.squad[0] || 20) + ' s');
  }
  h += '<span id="freeBar" style="display:contents"></span>';
  $('#bar').innerHTML = h;
}
// Pointerdown, not click: the bar is patched at 20 Hz and a click whose target was replaced is lost.
$('#bar').addEventListener('pointerdown', ev => {
  if (ev.button !== 0 || S.ending) return;
  const b = ev.target.closest('.bb');
  if (!b) return;
  ev.preventDefault();
  flashCls(b, 'press', 150);
  if (b.dataset.slot !== undefined) pickCard(S.slots[+b.dataset.slot].id);
  else if (b.dataset.horde) useHorde();
  else if (b.dataset.cmd) pickCmd(b.dataset.cmd);
  else if (b.dataset.squad) useSquad();
  else if (b.dataset.free) pickCard(b.dataset.free);
});
$('#bar').addEventListener('mouseover', ev => {
  const b = ev.target.closest('.bb');
  const k = !b ? null : b.dataset.slot !== undefined ? S.slots[+b.dataset.slot].id : b.dataset.horde ? 'horde' : b.dataset.cmd ? 'cmd:' + b.dataset.cmd : b.dataset.squad ? 'squad' : b.dataset.free || null;
  if (k !== S.barHover) { S.barHover = k; renderSide(); }
});
$('#bar').addEventListener('mouseleave', () => { S.barHover = null; renderSide(); });

function costOf(k) {
  const c = ((S.costs && S.costs[k]) || S.defs[k].cost || [0, 0]).slice();      // S.costs: the own faction's prices from 'start'
  if (S.snap && k === 'gen') c[0] = S.snap.gp;
  if (S.snap && k === 'sniper' && S.snap.sp !== undefined) c[0] = S.snap.sp;
  return c;
}
function costHtml(c) {
  const p = [];
  if (c[0]) p.push(`<span class="e">${c[0]} ${SVG.e}</span>`);
  if (c[1]) p.push(`<span class="s">${c[1]} ${SVG.s}</span>`);
  return p.join(' ') || 'zdarma';
}
function afford(c) { return !!S.snap && S.snap.r[0] >= c[0] && S.snap.r[1] >= c[1]; }
function locked(k) { const db = dobaOf(k); return !!(S.snap && db && S.snap.doba < db); }
// a command (Útok! needs Doba II) is locked while the Doba is lower
function cmdLocked(c) { return !!(S.snap && cmdDoba(c) && S.snap.doba < cmdDoba(c)); }
function freeOf(k) { return (S.snap && S.snap.free[k]) || 0; }
const kingDead = () => S.mode === 'kral' && !!(S.snap && S.snap.kr && S.snap.kr.dead > 0);

/* ---------------- actions with client-side checks (deny feedback instead of server spam) ---------------- */
let curMsgT = 0;
function refuse(text) {
  const el = $('#curMsg');
  let [x, y] = S.mouse || [0, 0];
  if (!S.mouse) { const r = ($('#board').offsetParent ? $('#board') : document.body).getBoundingClientRect(); x = r.left + r.width / 2; y = r.top + r.height / 2; }
  el.innerHTML = fmt(text);
  el.classList.remove('hidden');
  const w = el.offsetWidth, h = el.offsetHeight;
  el.style.left = Math.round(Math.max(w / 2 + 6, Math.min(innerWidth - w / 2 - 6, x))) + 'px';
  el.style.top = Math.round(Math.max(h + 6, y - 16)) + 'px';
  clearTimeout(curMsgT); curMsgT = setTimeout(() => el.classList.add('hidden'), 1200);
  uiSfx('deny');
}
function missOf(c) { const r = S.snap ? S.snap.r : [0, 0, 0]; const p = []; if (r[0] < c[0]) p.push(c[0] - r[0] + ' ⚡'); if (r[1] < c[1]) p.push(c[1] - r[1] + ' 🔩'); return p.join(' a '); }
function pulseMissing(c) { const r = S.snap ? S.snap.r : [0, 0]; if (r[0] < c[0]) flashCls($('#resE'), 'miss', 460); if (r[1] < c[1]) flashCls($('#resS'), 'miss', 460); }
function denyBtn(el, text, cost) { if (el) flashCls(el, 'deny', 260); if (cost) pulseMissing(cost); refuse(text); }
function denyKing() { flashCls($('#banner [data-k="kdead"]'), 'ping', 620); refuse(`Tvůj Král je mrtvý, stavět můžeš za ${Math.ceil(S.snap.kr.dead)} s.`); }
function cardEl(k) { const i = S.slots.findIndex(s => s.id === k); return $(i >= 0 ? `#bar .bb[data-slot="${i}"]` : `#bar .bb[data-free="${k}"]`); }
function denyCard(k, why, cost) { if (why === 'kingdead') return denyKing(); denyBtn(cardEl(k), why, cost); }
// Why a card cannot be used right now ('' = it can). Returns 'kingdead' for the dead-King case so callers can pulse that banner.
function useBlock(k) {
  const d = S.defs[k], m = S.snap;
  if (!m) return 'Zápas ještě nezačal.';
  const fr = freeOf(k);
  if (locked(k) && !fr) return `${d.name} vyžaduje Dobu ${roman(dobaOf(k))}.`;
  if (d.cat === 'b' && kingDead()) return 'kingdead';
  if (fr) return '';
  if ((m.cd[k] || 0) > 0) return `${d.name} se nabíjí, ještě ${Math.ceil(m.cd[k])} s.`;
  if (k === 'dama' && [...S.ents.values()].some(e => e.side === S.side && e.kind === 'dama')) return 'Hlídku smíš mít jen jednu.';
  const c = costOf(k);
  if (!afford(c)) return `Na ${d.name} chybí ${missOf(c)}.`;
  return '';
}
function cellBlock(k, x, y) {
  const unit = S.defs[k].cat === 'u';
  if (!own(x) || inMist(x)) return unit ? 'Jednotky nasazuješ jen na své polovině mimo Mlhu.' : 'Stavět můžeš jen na své polovině mimo Mlhu.';
  if (ter(x, y) === '#') return 'Na troskách stavět nejde. Klikni na ně bez karty a rozeber je.';
  const tr = terrainRefusal(ter(x, y), unit);
  if (tr) return tr;
  if (!canPlace(k, x, y)) return unit ? 'Sem jednotku nepostavíš.' : 'Tady stavět nejde.';
  return '';
}
function targetBlock(p, x, y) {
  if (canTarget(p, x, y)) return '';
  const t = p.kind === 'cmd' ? S.cmds[p.id].target : S.defs[p.id].target;
  if (t === 'own') return 'Klikni na svou stavbu.';
  if (t === 'crate') return 'Klikni na zásobovací bednu.';
  if (t === 'mist') return 'Karanténu jde použít jen v Mlze.';
  if (p.id === 'navnada' && visible(x, y)) return 'Návnadu polož na volné průchozí pole.';
  return 'Cíl musíš vidět.';
}
// red X stamp over a refused cell
function stampCell(x, y) {
  const el = document.createElement('i');
  el.className = 'mk';
  el.style.left = px(x) + 'px'; el.style.top = py(y) + 'px'; el.style.setProperty('--s', Math.round(CS * 0.7) + 'px');
  $('#marks').appendChild(el);
  setTimeout(() => el.remove(), 700);
}
function denyCell(x, y, text) { stampCell(x, y); refuse(text); }
// a click on the board with a card or command in hand (called from input.js)
function useAt(p, x, y) {
  if (p.kind === 'cmd') {
    const c = S.cmds[p.id], cd = S.snap.cd['cmd_' + p.id] || 0;
    if (cmdLocked(c)) return denyBtn($(`#bar .bb[data-cmd="${p.id}"]`), `${c.name} vyžaduje Dobu ${roman(cmdDoba(c))}.`);
    if (cd > 0) return denyBtn($(`#bar .bb[data-cmd="${p.id}"]`), `${c.name} se nabíjí, ještě ${Math.ceil(cd)} s.`);
    const why = targetBlock(p, x, y);
    if (why) return denyCell(x, y, why);
    send({ t: 'cmd', id: p.id, x, y });
  } else {
    const k = p.id, why = useBlock(k);
    if (why) return denyCard(k, why, costOf(k));
    if (p.kind === 'place') {
      const w = cellBlock(k, x, y);
      if (w) return denyCell(x, y, w);
      send({ t: S.defs[k].cat === 'b' ? 'build' : 'unit', kind: k, x, y });
      return;
    }
    const w = targetBlock(p, x, y);
    if (w) return denyCell(x, y, w);
    send({ t: 'card', id: k, x, y });
  }
  S.pick = null; updateBar(); renderSide();
}

function pickCard(id) {
  const d = S.defs[id];
  if (!d || S.ending) return;
  if (locked(id) && !freeOf(id)) return denyCard(id, `${d.name} vyžaduje Dobu ${roman(dobaOf(id))}.`);

  S.choose = null;
  if (d.cat === 'a' && !d.target) {
    const why = useBlock(id);
    if (why) return denyCard(id, why, costOf(id));
    send({ t: 'card', id, x: -1, y: -1 });
    uiSfx('tick');
    return;
  }
  const kind = d.cat === 'a' ? 'card' : 'place';
  S.pick = S.pick && S.pick.kind === kind && S.pick.id === id ? null : { kind, id };
  S.sel = null;
  uiSfx('tick');
  updateBar(); renderSide();
}
function pickCmd(id) {
  const c = S.cmds[id];
  if (!c || S.mode !== 'strateg' || S.ending) return;
  S.choose = null;
  const cd = (S.snap && S.snap.cd['cmd_' + id]) || 0;
  if (cmdLocked(c)) return denyBtn($(`#bar .bb[data-cmd="${id}"]`), `${c.name} vyžaduje Dobu ${roman(cmdDoba(c))}.`);
  if (!c.target) {
    if (cd > 0) return denyBtn($(`#bar .bb[data-cmd="${id}"]`), `${c.name} se nabíjí, ještě ${Math.ceil(cd)} s.`);
    send({ t: 'cmd', id, x: -1, y: -1 });
    uiSfx('tick');
    return;
  }
  S.pick = S.pick && S.pick.kind === 'cmd' && S.pick.id === id ? null : { kind: 'cmd', id };
  S.sel = null;
  uiSfx('tick');
  updateBar(); renderSide();
}
function cancelPick() { S.pick = null; S.sel = null; S.choose = null; updateBar(); renderSide(); }
function useHorde() {
  const m = S.snap, b = $('#bar .bb[data-horde]');
  if (!m) return;
  if (m.hcd > 0) return denyBtn(b, `Tlupa se nabíjí, ještě ${Math.ceil(m.hcd)} s.`);
  if (m.r[0] < m.hc) return denyBtn(b, `Na Tlupu chybí ${m.hc - m.r[0]} ⚡.`, [m.hc, 0]);
  send({ t: 'horde' });
  uiSfx('tick');
}
// Četa na Relikvii (H, Stratég): the server checks the deck, energy and cooldown too and answers with a message
function useSquad() {
  const m = S.snap, b = $('#bar .bb[data-squad]');
  if (!m || S.mode !== 'strateg' || S.ending) return;
  if (!m.sq) return denyBtn(b, 'Relikvie ještě není aktivní.');
  if (m.sq[1] > 0) return denyBtn(b, `Četa se nabíjí, ještě ${Math.ceil(m.sq[1])} s.`);
  send({ t: 'squad', id: 'relic' });
  if (b) flashCls(b, 'press', 150);
  uiSfx('tick');
}
const convOpen = m => !!m && m.doba >= (S.conv[2] || 1);
function convert() {
  const m = S.snap, b = $('#convBtn');
  if (!m || S.ending) return;
  if (!convOpen(m)) return denyBtn(b, `Přetavení vyžaduje Dobu ${roman(S.conv[2])}.`);
  if (m.r[0] < S.conv[0]) return denyBtn(b, `Přetavení stojí ${S.conv[0]} ⚡.`, [S.conv[0], 0]);
  send({ t: 'conv' });
  flashCls(b, 'press', 150);
  uiSfx('tick');
}
$('#convBtn').addEventListener('pointerdown', ev => { if (ev.button !== 0) return; ev.preventDefault(); convert(); });
function selectBuilding(id) {
  if (S.sel !== id) S.choose = null;
  S.sel = id; S.pick = null;
  uiSfx('select');
  updateBar(); renderSide();
}
function upMsg(c) {
  const short = S.snap.r[1] < c[1];
  return `Na vylepšení chybí ${missOf(c)}${short ? (S.mode === 'kral' ? ' (oprava F stojí šrot)' : convOpen(S.snap) ? ' (C přetaví energii na šrot)' : '') : ''}.`;
}
function doUpgrade(e, path, btn) {
  S.choose = null;
  const d = S.defs[e.kind];
  if (e.lvl >= 3) refuse('Stavba už má maximální úroveň.');
  else if (kingDead()) denyKing();
  else if (e.lvl === 2 && !isWallKind(e.kind) && !path) refuse('Na úroveň 3 vyber cestu A nebo B.');
  else if (!afford(d.up[e.lvl - 1])) denyBtn(btn, upMsg(d.up[e.lvl - 1]), d.up[e.lvl - 1]);
  else { send({ t: 'upg', id: e.id, path }); if (btn) flashCls(btn, 'press', 150); uiSfx('tick'); }
  renderSide();
}
function doSell(e) {
  if (kingDead()) return denyKing();
  send({ t: 'sell', id: e.id });
  uiSfx('sell');
  S.sel = null; S.choose = null;
  renderSide();
}
// U on the selected building: level 1 (or a wall) upgrades, level 2 opens the A/B chooser, level 3 is refused.
function keyUpgrade() {
  const e = S.sel && S.ents.get(S.sel);
  if (!e) return refuse('Nejdřív klikni na svou stavbu.');
  if (e.lvl === 2 && !isWallKind(e.kind)) {
    if (S.choose) { S.choose = null; return renderSide(); }
    if (kingDead()) return denyKing();
    S.choose = { id: e.id, until: performance.now() + 4000 };
    setTimeout(() => { if (S.choose && performance.now() >= S.choose.until) { S.choose = null; renderSide(); hud(S.snap); } }, 4050);
    uiSfx('chooser');
    renderSide(); hud(S.snap);
    return;
  }
  doUpgrade(e, '', $('#sideMain [data-a="upg"]'));
}
function choosePath(p) {
  const e = S.ents.get(S.choose.id);
  S.choose = null;
  if (e && e.lvl === 2 && S.sel === e.id) doUpgrade(e, p, $(`#sideMain [data-a="upg"][data-p="${p}"]`));
  else renderSide();
  hud(S.snap);
}

function updateBar() {
  if (!S.snap) return;
  const m = S.snap, now = performance.now();
  document.querySelectorAll('#bar .bb').forEach(b => {
    let cd = 0, cdMax = 0, unaff = false, lk = false, fr = 0, cost = '';
    if (b.dataset.slot !== undefined) {
      const id = S.slots[+b.dataset.slot].id, d = S.defs[id], c = costOf(id);
      cd = m.cd[id] || 0; cdMax = d.cd || 0; fr = freeOf(id);
      lk = locked(id) && !fr;
      unaff = !fr && !afford(c);
      b.classList.toggle('on', !!(S.pick && S.pick.id === id && S.pick.kind !== 'cmd'));
      b.classList.toggle('free', fr > 0);
      cost = lk ? `<span class="doba">zámek · Doba ${roman(dobaOf(id))}</span>` : fr ? `${SVG.g} zdarma` : costHtml(c);
      setHtml(b.querySelector('.badge'), fr ? 'dar ×' + fr : '');
      if (fr > (b._fr || 0)) flashCls(b.querySelector('.badge'), 'pop', 1000);
      b._fr = fr;
    } else if (b.dataset.horde) {
      cd = m.hcd; cdMax = S.horde[1]; unaff = m.r[0] < m.hc;
      cost = `<span class="e">${m.hc} ${SVG.e}</span> → soupeři`;
    } else if (b.dataset.cmd) {
      const id = b.dataset.cmd;
      cd = m.cd['cmd_' + id] || 0; cdMax = S.cmds[id].cd;
      lk = cmdLocked(S.cmds[id]);                       // Útok! (G) waits for Doba II
      b.classList.toggle('on', !lk && !!(S.pick && S.pick.kind === 'cmd' && S.pick.id === id));
      cost = lk ? `<span class="doba">zámek · Doba ${roman(cmdDoba(S.cmds[id]))}</span>` : cd > 0 ? `připraveno za ${Math.ceil(cd)} s` : `obnova ${cdMax} s`;
    } else if (b.dataset.squad) {
      const sq = m.sq;
      cd = sq ? sq[1] : 0; cdMax = S.squad[0] || 20; lk = !sq; unaff = !!sq && m.r[0] < sq[0];
      cost = lk ? 'Relikvie ještě spí' : cd > 0 ? `připraveno za ${Math.ceil(cd)} s` : `<span class="e">${sq[0]} ${SVG.e}</span> · obnova ${cdMax} s`;
    } else return;
    b.classList.toggle('lock', lk);
    b.classList.toggle('poor', !lk && (unaff || cd > 0));
    setHtml(b.querySelector('[data-cost]'), cost);
    const cdv = b.querySelector('.cdv');
    cdv.style.height = (cd > 0 && cdMax ? Math.min(100, cd / cdMax * 100) : 0) + '%';
    cdv.style.display = cd > 0 ? '' : 'none';
    setHtml(b.querySelector('.cdt'), cd > 0 ? String(Math.ceil(cd)) : '');
    if (b._cd > 0 && cd <= 0 && cdMax >= 10 && now - S.readyT > 400) { S.readyT = now; flashCls(b, 'ready', 520); uiSfx('ready'); }
    else if (b._unaff && !unaff && cd <= 0 && !lk) {
      flashCls(b, 'shine', 360);
      const c0 = b.dataset.slot !== undefined ? costOf(S.slots[+b.dataset.slot].id)[0] : m.hc;
      if (c0 >= 100 && now - S.shineT > 1500) { S.shineT = now; uiSfx('tick'); }
    }
    b._cd = cd; b._unaff = unaff;
  });
  // free charges for abilities that are not in the deck
  const extra = Object.entries(m.free).filter(([k]) => !S.slots.some(s => s.id === k));
  const fh = extra.map(([k, n]) => barBtn(`data-free="${k}"`, PAL.verdigris, k, '', S.defs[k].name, `${SVG.g} zdarma ×${n}`)).join('');
  const fb = $('#freeBar');
  if (fb && fb.dataset.h !== fh) {
    const had = fb.dataset.h || '';
    fb.dataset.h = fh; fb.innerHTML = fh;
    if (fh.length > had.length) fb.querySelectorAll('.bb').forEach(b => flashCls(b, 'ready', 520));
  }
}
// compare with the last string we set (innerHTML re-serializes '<path/>' as '<path></path>', so a direct compare never matched SVG);
// _s catches anyone else writing innerHTML in between
function setHtml(el, html) {
  if (!el || (el._h === html && el.innerHTML === el._s)) return;
  el.innerHTML = html; el._h = html; el._s = el.innerHTML;
}

/* ---------------- snapshots ---------------- */
function onSnap(m) {
  const prev = S.snap;
  S.snap = m;
  const seen = new Set(), now = performance.now();
  let built = false, deployed = false, upLvl = 0;
  const promo = m.fx.some(f => f[0] === 'P' && f[5] === S.side);   // a promoted Dáma is not a deployment
  for (const a of m.en) {
    const [id, kind, side, x, y, hp, maxhp, lvl, path, flags, kills] = a;
    seen.add(id);
    let e = S.ents.get(id);
    if (!e) {
      e = { id, kind, side, dx: x, dy: y, born: now };
      S.ents.set(id, e);
      if (prev && side === S.side) { const c = S.defs[kind].cat; if (c === 'b') built = true; else if (c === 'u' && !(promo && kind === 'dama')) deployed = true; }
    } else if (side === S.side && lvl > e.lvl) upLvl = lvl;
    Object.assign(e, { kind, side, x, y, hp, maxhp, lvl, path, flags, kills: kills || 0, cx: Math.round(x), cy: Math.round(y) });
    if (side === 1 - S.side) S.seenEnemy = true;
  }
  const gone = new Map();
  for (const [id, e] of S.ents) if (!seen.has(id)) { gone.set(id, e); S.ents.delete(id); }
  // ghosts: last known enemy buildings
  const vis = m.v;
  for (const [id, g] of S.ghosts) if (vis[g.cy * S.W + g.cx] === '1') S.ghosts.delete(id);
  S.bmap.clear();
  for (const e of S.ents.values()) {
    if (S.defs[e.kind].cat !== 'b') continue;
    S.bmap.set(e.cx + ',' + e.cy, e);
    if (e.side !== S.side) S.ghosts.set(e.id, { kind: e.kind, side: e.side, cx: e.cx, cy: e.cy, lvl: e.lvl, path: e.path });
  }
  for (const g of S.ghosts.values()) if (!S.bmap.has(g.cx + ',' + g.cy)) S.bmap.set(g.cx + ',' + g.cy, g);
  if (S.sel && !S.ents.has(S.sel)) S.sel = null;
  if (S.choose) { const c = S.ents.get(S.choose.id); if (now > S.choose.until || S.choose.id !== S.sel || !c || c.lvl !== 2) S.choose = null; }
  // own King: client-side prediction, reconciled with the server position; a dash snaps to the server
  const kr = m.kr;
  const me = kr && kr.id ? S.ents.get(kr.id) : null;
  const dashed = m.fx.some(f => f[0] === 'D' && f[5] === S.side);
  if (!me) S.kp = null;
  else if (!S.kp || S.kp.id !== me.id || dashed) S.kp = { id: me.id, x: me.x, y: me.y };
  else {
    const ex = me.x - S.kp.x, ey = me.y - S.kp.y;
    if (ex * ex + ey * ey > 1) { S.kp.x = me.x; S.kp.y = me.y; } else { S.kp.x += ex * 0.08; S.kp.y += ey * 0.08; }
  }
  if (typeof renderOnSnap === 'function') renderOnSnap(m, prev, gone);
  if (typeof audioOnSnap === 'function') audioOnSnap(m, prev, gone);
  if (built) uiSfx('build'); else if (deployed) uiSfx('deploy');
  if (upLvl) uiSfx('upgrade', null, { lvl: upLvl });
  (m.msg || []).forEach((t, i) => { const k = m.mk ? m.mk[i] : 'i'; if (k === 'e') refuse(t); else toast(t, k === 'w' ? 'warn' : ''); });
  annEvents(m, prev);
  annDiff(m, prev);
  hud(m, prev);
  updateBar(); renderSide(); renderResearch();
  advisor(m, prev);
}

/* ---------------- top bar ---------------- */
function hud(m, prev) {
  if (!m) return;
  resCount(m.r, prev && prev.r);
  $('#rInc').textContent = '+' + dec(m.inc) + '/s';
  $('#rDoba').textContent = 'Doba ' + roman(m.doba);
  const cb = $('#convBtn'), co = convOpen(m);
  cb.classList.toggle('lock', !co);
  cb.classList.toggle('poor', co && m.r[0] < S.conv[0]);
  const canRes = Object.entries(S.research).some(([id, r]) => !m.tech.includes(id) && m.r[2] >= rcostOf(id) && (r.tier === 1 || m.tech.includes(r.branch + (r.tier - 1))));
  $('#resBtn').classList.toggle('ping', canRes);
  throneBar('Me', S.side, m, prev);
  throneBar('Foe', 1 - S.side, m, prev);
  const tm = Math.floor(m.tm), ck = $('#clock'), ph = $('#phase');
  ck.textContent = m.ni ? 'Poslední noc' : String(Math.floor(tm / 60)).padStart(2, '0') + ':' + String(tm % 60).padStart(2, '0');
  ck.classList.toggle('night', !!m.ni);
  const dl = m.dl ? ` · škoda ${m.dl[S.side]} : ${m.dl[1 - S.side]}` : '';
  ph.textContent = m.ni ? `Mlha ${m.st}/6${dl || ' · trůny ztrácejí životy'}` : `vlna za ${m.nw} s` + (m.st ? ` · Mlha ${m.st}/3` : '');
  ph.classList.toggle('soon', !m.ni && m.nw > 0 && m.nw <= 3);
  const ec = $('#eclChip'), e = m.ec;
  ec.classList.toggle('hidden', !e || !e[0] || !!m.ni);
  if (e && e[0]) {
    setHtml(ec, e[0] === 2 ? `<small>Zatmění</small>věže slepé · ${Math.ceil(e[1])} s` : `<small>Zatmění</small>za ${mmss(e[1])}`);
    ec.classList.toggle('ecl1', e[0] === 1 && e[1] <= 15);
    ec.classList.toggle('ecl2', e[0] === 2);
  }
  const rc = $('#relicChip'), rl = m.rl;
  rc.classList.toggle('hidden', !rl || !!S.noRelic);
  if (rl && !S.noRelic) {
    const [own, cap, p, smp] = rl;
    let t, cls = '';
    if (m.tm < S.relicFrom) t = `probudí se za ${mmss(S.relicFrom - m.tm)}`;
    else if (cap >= 0 && cap !== own && p > 0) { t = `${cap === S.side ? 'obsazuješ' : 'soupeř obsazuje'} · ${Math.round(p * 100)} %`; cls = 'cap ' + (cap === S.side ? 'mine' : 'foe'); }
    else if (own === S.side) { t = `tvoje · +2 ${SVG.e}/s · ${SVG.v} za ${Math.max(0, Math.ceil(smp))} s`; cls = 'mine'; }
    else if (own === 1 - S.side) { t = 'soupeřova · +2 ' + SVG.e + '/s pro soupeře'; cls = 'foe'; }
    else t = 'volná · obsaď ji jednotkou';
    setHtml(rc, `<small>Relikvie</small>${t}`);
    rc.className = 'chip ' + cls;
  }
  const ban = [];
  if (m.ck[S.side] > 0) ban.push(['bad', '', GLY.bell + `Šach! Mat za ${Math.max(0, Math.ceil(10 - m.ck[S.side]))} s · ubraň řadu`]);
  if (m.ck[1 - S.side] > 0) ban.push(['good', '', GLY.crown + `Dáváš šach! Mat za ${Math.max(0, Math.ceil(10 - m.ck[1 - S.side]))} s`]);
  if (m.kr && m.kr.dead > 0) ban.push(['bad', 'kdead', GLY.crack + `Král padl · návrat za ${Math.ceil(m.kr.dead)} s`]);
  if (S.choose) ban.push(['lea', '', 'Zvol cestu: <kbd>A</kbd> nebo <kbd>B</kbd> · Esc zruší']);
  if (m.out[S.side] > 0) ban.push(['lea', '', `Výpadek proudu · věže nestřílí ${Math.ceil(m.out[S.side])} s`]);
  if (m.mob > 0) ban.push(['info', '', `Mobilizace · další ${m.mob} jednotky rychlejší`]);
  setHtml($('#banner'), ban.map(([c, k, t]) => `<div class="ban ${c}"${k ? ` data-k="${k}"` : ''}>${t}</div>`).join(''));
}
function throneBar(id, side, m, prev) {
  const mx = S.thMax[side] || S.throneMax, hp = Math.max(0, m.th[side]), f = Math.min(100, 100 * hp / mx), bar = $('#th' + id + 'Bar');
  $('#th' + id + 'V').textContent = hp + ' / ' + mx + (m.sh[side] > 0 ? ' · štít' : '');
  $('#th' + id).style.width = f + '%';
  const tr = $('#th' + id + 'T');
  if (!prev || hp >= prev.th[side]) { tr.style.transition = 'none'; tr.style.width = f + '%'; void tr.offsetWidth; tr.style.transition = ''; }
  else { tr.style.width = f + '%'; if (side === S.side && prev.th[side] - hp >= 20 && !S.opt.calm) flashCls(bar.parentNode, 'hit', 200); }
  bar.classList.toggle('low', f < 25);
  bar.classList.toggle('shield', m.sh[side] > 0);
}
// resource counters roll to the new value; big gains and spends float a number
function resCount(r, pr) {
  const els = [$('#rE'), $('#rS'), $('#rV')], boxes = [$('#resE'), $('#resS'), $('#resV')];
  if (!S.resTw) { S.resTw = { from: r.slice(), to: r.slice(), cur: r.slice(), t0: 0, raf: 0 }; els.forEach((el, i) => { el.textContent = r[i]; }); return; }
  const tw = S.resTw;
  if (!pr) return;
  if (r.every((v, i) => v === tw.to[i])) return;
  r.forEach((v, i) => {
    const d = v - pr[i];
    if (d >= 10 || d <= -5) floatAt(boxes[i], (d > 0 ? '+' : '−') + Math.abs(d), d > 0 ? 'up' : 'dn');
    if (d >= 10) flashCls(boxes[i], 'gain', 420);
  });
  tw.from = tw.cur.slice(); tw.to = r.slice(); tw.t0 = performance.now();
  if (tw.raf) return;
  const step = now => {
    const k = Math.min(1, (now - tw.t0) / 250), q = 1 - (1 - k) * (1 - k);
    tw.cur = tw.to.map((v, i) => Math.round(tw.from[i] + (v - tw.from[i]) * q));
    els.forEach((el, i) => { const t = String(tw.cur[i]); if (el.textContent !== t) el.textContent = t; });
    tw.raf = k < 1 ? requestAnimationFrame(step) : 0;
  };
  tw.raf = requestAnimationFrame(step);
}
function floatAt(el, text, cls) {
  const r = el.getBoundingClientRect(), f = document.createElement('span');
  f.className = 'flt ' + cls; f.textContent = text;
  f.style.left = Math.round(r.left + r.width * 0.62) + 'px'; f.style.top = Math.round(r.bottom - 6) + 'px';
  $('#floats').appendChild(f);
  setTimeout(() => f.remove(), 950);
}

/* ---------------- announcer: big banners in the reserved strip ---------------- */
const GLY = {
  bell: '<svg viewBox="0 0 16 16"><path d="M8 1.2c.6 0 1 .4 1 1v.5a4.6 4.6 0 0 1 3.6 4.5v3l1.4 1.9v.8H2v-.8l1.4-1.9v-3A4.6 4.6 0 0 1 7 2.7v-.5c0-.6.4-1 1-1zM6.3 13.6h3.4a1.7 1.7 0 0 1-3.4 0z"/></svg>',
  crown: '<svg viewBox="0 0 16 16"><path d="M1.5 4.5l3.2 3 3.3-5 3.3 5 3.2-3-1.2 8H2.7zM2.8 13.2h10.4v1.8H2.8z"/></svg>',
  crack: '<svg viewBox="0 0 16 16"><path d="M1.5 4.5l3.2 3 3.3-5 .7 1.1-1.2 2.9 1.5 1.4-1 4.6H2.7zM9.3 4.1l1.9 3.4 3.3-3-1.2 8H9l1-4.1-1.6-1.6zM2.8 13.2h4.5V15H2.8zM8.8 13.2h4.4V15H8.8z"/></svg>',
  moon: '<svg viewBox="0 0 16 16"><path d="M10.5 1.5a6.5 6.5 0 1 0 4 11.6A5.6 5.6 0 0 1 10.5 1.5z"/></svg>',
};
const ANN = { q: [], cur: null, state: 'idle', t: 0, seen: new Map() };
function announce(title, sub = '', prio = 3, kind = 'info') {
  if (!S.inGame || S.ending) return;
  const now = performance.now();
  if (now - (ANN.seen.get(title) || -1e9) < 3000) return;
  ANN.seen.set(title, now);
  const it = { title, sub, prio, kind };
  const i = ANN.q.findIndex(q => q.prio > prio);
  ANN.q.splice(i < 0 ? ANN.q.length : i, 0, it);
  if (ANN.q.length > 3) ANN.q.length = 3;
  if (ANN.state === 'idle' || (ANN.state === 'show' && prio === 1 && ANN.cur.prio > 1 && ANN.q[0] === it)) annNext();
}
function annNext() {
  clearTimeout(ANN.t);
  const box = $('#ann'), it = ANN.q.shift();
  ANN.cur = it || null;
  if (!it) { box.innerHTML = ''; ANN.state = 'idle'; return; }
  ANN.state = 'show';
  const g = { bad: GLY.bell, good: GLY.crown, dark: GLY.moon }[it.kind] || '';
  box.innerHTML = `<div class="annc ${it.kind}${it.prio >= 3 ? ' p3' : ''}"><div class="t">${g}<span>${esc(it.title)}</span>${g}</div>${it.sub ? `<div class="s">${fmt(it.sub)}</div>` : ''}</div>`;
  const el = box.firstChild;
  if (S.opt.calm) el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200 });
  else {
    el.animate([{ opacity: 0, transform: 'scale(1.5)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 140, easing: 'ease-out' });
    el.firstChild.animate([{ letterSpacing: '.32em' }, { letterSpacing: '.08em' }], { duration: 180, easing: 'ease-out' });
  }
  uiSfx('banner' + it.prio);
  ANN.t = setTimeout(() => {
    el.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-12px)' }], { duration: 260, fill: 'forwards' });
    ANN.t = setTimeout(() => {
      box.innerHTML = ''; ANN.cur = null; ANN.state = 'gap';
      ANN.t = setTimeout(annNext, 300);
    }, 260);
  }, 140 + 1100 + (it.prio === 1 ? 400 : 0));
}
function annClear() { clearTimeout(ANN.t); ANN.q = []; ANN.cur = null; ANN.state = 'idle'; ANN.seen.clear(); const b = $('#ann'); if (b) b.innerHTML = ''; }
// announcements derived from state changes (work with any server that sends the field)
function annDiff(m, p) {
  if (!p) return;
  const me = S.side, foe = 1 - me, tmx = S.thMax[me] || S.throneMax, fmx = S.thMax[foe] || S.throneMax;
  if (m.ck[me] > 0 && !(p.ck[me] > 0)) announce('Šach!', 'Ubraň řadu u trůnu, jinak za 10 s prohraješ', 1, 'bad');
  if (m.ck[foe] > 0 && !(p.ck[foe] > 0)) announce('Dáváš šach!', 'Udrž jednotky u trůnu 10 s', 1, 'good');
  for (const f of [0.5, 0.25, 0.1]) {
    if (m.th[me] <= tmx * f && p.th[me] > tmx * f) announce('Trůn v ohrožení', `zbývá ${f * 100} %`, 1, 'bad');
    if (f > 0.1 && m.th[foe] <= fmx * f && p.th[foe] > fmx * f) announce('Soupeřův trůn slábne', `zbývá ${f * 100} %`, 3, 'good');
  }
  const kd = !!(m.kr && m.kr.dead > 0), pkd = !!(p.kr && p.kr.dead > 0);
  if (kd && !pkd) announce('Král padl', `návrat za ${Math.ceil(m.kr.dead)} s · do té doby nestavíš`, 1, 'bad');
  if (!kd && pkd && m.kr) announce('Král povstal', 'můžeš zase stavět', 2, 'good');
  if (m.ni && !p.ni) ANN_EV.night();
  else if (m.st > p.st) ANN_EV.mist(m.st, m.ni);
  if (m.doba > p.doba) { announce('Doba ' + roman(m.doba), m.doba === 2 ? 'odemkly se silnější karty' : '+2 ⚡/s', 2, 'good'); uiSfx('doba'); unlockAnim(m.doba); }
  if (m.out[me] > 0 && !(p.out[me] > 0)) announce('Výpadek proudu', 'tvoje věže 5 s nestřílí', 2, 'bad');
  if (m.out[foe] > 0 && !(p.out[foe] > 0)) announce('Soupeř bez proudu', 'jeho věže 5 s nestřílí', 3, 'good');
  for (const id of m.tech) if (!p.tech.includes(id) && S.research[id]) { announce('Výzkum', S.research[id].name, 3, 'info'); uiSfx('research'); }
  for (const c of m.cr) if (c[3] === 4 && !p.cr.some(q => q[0] === c[0])) ANN_EV.legend(c[4] > 0);
  const e = m.ec, pe = p.ec;
  if (e && pe && !m.ni) {
    if (e[0] === 1 && e[1] <= 15 && !(pe[0] === 1 && pe[1] <= 15)) ANN_EV.eclWarn(e[1]);
    if (e[0] === 2 && pe[0] !== 2) ANN_EV.ecl(1);
    if (e[0] !== 2 && pe[0] === 2) ANN_EV.ecl(0);
  }
  if (m.rl && p.rl) {
    if (m.tm >= S.relicFrom && p.tm < S.relicFrom) ANN_EV.relicOn();
    if (m.rl[0] !== p.rl[0] && m.rl[0] >= 0) ANN_EV.relic(m.rl[0]);
  }
  if (m.kr && p.kr && m.kr.ult >= 100 && !(p.kr.ult >= 100)) uiSfx('ready');
}
// Announcements that come both from server events and from state diffs share one title, so the 3 s duplicate filter keeps one.
const ANN_EV = {
  night: () => announce('Poslední noc', 'tma, Mlha pohlcuje základny, trůny ztrácejí životy', 2, 'dark'),
  mist: (st, night) => announce('Mlha postupuje', night ? `pohltila další sloupec · ${st}/6` : 'stavby v ní chátrají', 2, 'dark'),
  legend: falling => announce('Legendární bedna', falling ? 'padá do Mlhy' : 'leží v Mlze', 3, 'good'),
  eclWarn: secs => announce('Zatmění se blíží', `za ${Math.ceil(secs)} s · věže pak uvidí jen 1,5 pole`, 2, 'dark'),
  ecl: on => on ? announce('Zatmění!', 'věže vidí jen 1,5 pole · tvoje polovina je ve tmě', 2, 'dark') : announce('Světlo se vrací', 'věže zase vidí daleko', 3, 'info'),
  relicOn: () => announce('Relikvie se probudila', 'obsaď střed Mlhy: +2 ⚡/s a 🧪', 2, 'info'),
  relic: side => side === S.side ? announce('Relikvie je tvoje', '+2 ⚡/s a 🧪 každých 40 s', 2, 'good') : announce('Soupeř vzal Relikvii', 'vezmi mu ji zpátky', 2, 'bad'),
};
// announcements from server events (m.ev)
function annEvents(m, p) {
  const now = performance.now(), me = S.side;
  const myKingFell = !!(m.kr && m.kr.dead > 0 && !(p && p.kr && p.kr.dead > 0));
  for (const f of m.fx) if (f[0] === 'x' && f[5] === 'z' && f[9] === me) S.zk.push(now);
  S.zk = S.zk.filter(t => now - t < 6000);
  if (S.zk.length >= 10) { S.zk = []; announce('Čistka', '10 zombie za 6 s', 3, 'good'); }
  for (const [code, a, b] of m.ev || []) {
    const mine = a === me;
    if (code === 'wave') announce('Vlna ' + a, 'zombie lezou z Mlhy', 3, 'info');
    else if (code === 'alfa') announce('Alfa se probudila', mine ? 'míří na tvůj trůn' : 'míří na soupeře', 2, mine ? 'bad' : 'info');
    else if (code === 'alfa_dead') announce('Alfa padla', mine ? 'tvoje kořist: legendární bedna' : a === 1 - me ? 'zabil ji soupeř' : 'v Mlze leží legendární bedna', 2, mine ? 'good' : 'info');
    else if (code === 'horde') announce('Tlupa!', 'soupeř na tebe poslal zombie', 3, 'bad');
    else if (code === 'fb') announce('První krev', mine ? 'tvoje' : 'pro soupeře', 3, mine ? 'good' : 'info');
    else if (code === 'streak' && now - S.streakT > 5000) { S.streakT = now; announce(a >= 5 ? 'Řežba' : a >= 3 ? 'Trojitý úder' : 'Dvojitý úder', '', 3, 'good'); }
    else if (code === 'kk') { if (mine) announce('Zabil jsi krále', 'soupeř 15 s nestaví', 1, 'good'); else if (a !== 1 - me && !myKingFell) announce('Soupeřův král padl', '', 2, 'good'); }
    else if (code === 'kr' && a !== me) announce('Soupeřův král povstal', '', 3, 'info');
    else if (code === 'ult') announce(mine ? 'Válečný pokřik!' : 'Soupeřův pokřik', mine ? 'jednotky kolem Krále jsou 8 s odolnější' : 'jeho jednotky u Krále jsou 8 s odolnější', 2, mine ? 'good' : 'bad');
    else if (code === 'utok') announce(mine ? 'Útok!' : 'Soupeř velí k útoku', mine ? 'tvé jednotky jsou 6 s odolnější a rychlejší' : 'jeho jednotky jsou 6 s odolnější a rychlejší', 2, mine ? 'good' : 'bad');
    else if (code === 'turn') announce('Mrtví poslechli!', mine ? `${b} zombie se obrátilo proti soupeři` : `${b} zombie se obrátilo proti tobě`, 2, mine ? 'good' : 'bad');
    else if (code === 'promo') announce('Proměna!', mine ? 'tvůj Pěšák povýšil u soupeřova trůnu' : 'soupeřův Pěšák povýšil u tvého trůnu', 2, mine ? 'good' : 'bad');
    else if (code === 'contest') {
      announce('Sporná bedna', S.mode === 'strateg' ? 'Odstřel (W) sestřelí soupeřův dron' : 'u bedny stojí oba, vyžeň soupeře', 3, 'info');
      if (S.mode === 'strateg' && !S.shownTips.has('contestW')) { S.shownTips.add('contestW'); toast('Sporná bedna! Odstřel (W) sestřelí soupeřův dron.', 'warn'); }
    }
    else if (code === 'ecl_warn') ANN_EV.eclWarn(a);
    else if (code === 'ecl') ANN_EV.ecl(a);
    else if (code === 'night') ANN_EV.night();
    else if (code === 'mist') ANN_EV.mist(a, m.ni);
    else if (code === 'relic_on') ANN_EV.relicOn();
    else if (code === 'relic') ANN_EV.relic(a);
    else if (code === 'crate' && b === 4) ANN_EV.legend(true);
  }
}
function unlockAnim(doba) {
  let n = 0;
  S.slots.forEach((s, i) => { if (dobaOf(s.id) === doba) { const b = $(`#bar .bb[data-slot="${i}"]`); setTimeout(() => flashCls(b, 'unlock', 600), 80 * n++); } });
  for (const id of Object.keys(S.cmds || {})) if (cmdDoba(S.cmds[id]) === doba) { const b = $(`#bar .bb[data-cmd="${id}"]`); setTimeout(() => flashCls(b, 'unlock', 600), 80 * n++); }
}

/* ---------------- toasts (chronicle under the side panel) ---------------- */
function toast(text, kind) {
  const box = $('#toasts');
  const el = document.createElement('div');
  el.className = 'toast' + (kind ? ' ' + kind : ''); el.innerHTML = fmt(text);
  box.appendChild(el);
  while (box.children.length > 4) box.firstChild.remove();
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 600); }, kind === 'tip' ? 9000 : 4500);
  if (S.inGame) uiSfx('toast');
}

/* ---------------- advisor: tips for new players ---------------- */
function tip(key, text) {
  if (!S.tips || S.shownTips.has(key)) return;
  S.shownTips.add(key);
  toast('Rada: ' + text, 'tip');
}
function advisor(m) {
  const mine = [...S.ents.values()].filter(e => e.side === S.side);
  const cat = e => S.defs[e.kind].cat;
  // checklist progress
  if (mine.some(e => e.kind === 'gen')) S.steps.add('gen');
  if (mine.some(e => ATTACK.includes(e.kind) || e.kind === 'hangar')) S.steps.add('tower');
  if (S.seenEnemy || mine.some(e => e.kind === 'hlaska') || m.rv.length) S.steps.add('scout');
  if (mine.some(e => cat(e) === 'u')) S.steps.add('unit');
  if (mine.some(e => cat(e) === 'b' && e.lvl >= 2)) S.steps.add('upg');
  if (m.stc > 0) S.steps.add('crate');
  if (m.tech.length) S.steps.add('res');
  if (!S.tips) return;
  const t = m.tm, kral = S.mode === 'kral';
  tip('start', 'Tvůj trůn je vlevo, soupeř vpravo. Zombie lezou z Mlhy uprostřed. Začni Generátorem (1) a obrannou věží.');
  if (t > 6) tip('mode', kral
    ? 'Krále ovládáš klávesami W A S D, střílí sám. Mezerník = blok (včas zmáčknutý odrazí střelu), F = oprava stavby, Shift = výpad.'
    : 'Velitelské schopnosti: Q oprava, W odstřel, E sběrný dron pro bedny, R štít trůnu, G Útok!');
  if (t > 12 && m.nw <= 12 && t < 45) tip('wave1', 'Za pár sekund dorazí první vlna zombie. Měj u Mlhy aspoň jednu věž.');
  if (m.cr.some(c => c[4] > 0)) tip('crate', kral
    ? 'Do Mlhy padá zásobovací bedna (měsíční paprsek s odpočtem). Doběhni k ní Králem nebo tam pošli jednotku. Sebrat ji trvá 3 s.'
    : 'Do Mlhy padá zásobovací bedna. Pošli pro ni sběrný dron (E) nebo jednotku. Sebrat ji trvá 3 s.');
  if (m.cr.some(c => c[8] || (c[6] > 0 && c[7] > 0))) tip('contest', 'Sporná bedna: stojí u ní oba hráči. Vyžeň soupeře, jinak ji nesebere nikdo.');
  if (m.r[2] >= 2 && !m.tech.length) tip('res', 'Máš 🧪 Vzorky. Otevři Výzkum klávesou V a vyber technologii.');
  if (mine.some(e => e.kind === 'sniper')) tip('sniper', 'Odstřelovač střílí jen tam, kam vidíš. Postav k němu Hlásku nebo pošli dopředu jednotky.');
  if (t > 150 && !S.seenEnemy) tip('scout', 'Soupeře zatím nevidíš. Hláska, Průzkumný dron nebo jednotky ho odhalí.');
  if (m.th[S.side] < S.throneMax * 0.75) tip('throne', 'Trůn dostává zásahy. Postav věže do řad, kudy nepřítel chodí, a před ně zdi.');
  if (m.kr && m.kr.dead > 0) tip('kraldead', 'Král padl. Za 15 s se vrátí, do té doby nemůžeš stavět ani vylepšovat. Příště ustup dřív.');
  if (m.ck[S.side] > 0) tip('check', 'ŠACH! Zab nepřátele aspoň v jedné řadě u trůnu' + (kral ? ' nebo počkej na Krále' : ' nebo použij Odstřel či Štít') + ', jinak za 10 s prohraješ.');
  if (m.ck[1 - S.side] > 0) tip('checkfoe', 'Dáváš šach! Udrž jednotky ve 3 řadách u soupeřova trůnu 10 s a vyhraješ.');
  if (m.st >= 1 && !m.ni) tip('mist', 'Mlha postoupila. Stavby v zamořených sloupcích chátrají a nedá se tam stavět.');
  if (m.r[0] >= 350) tip('rich', 'Hromadí se ti energie. Utrať ji za stavby, jednotky nebo Tlupu (T).');
  if (convOpen(m) && m.r[0] >= 150 && m.r[1] < 15) tip('conv', 'Máš energii, ale málo šrotu. Přetav 30 ⚡ na 10 🔩 klávesou C nebo tlačítkem u šrotu.');
  if (mine.filter(e => cat(e) === 'b').length >= 3 && !mine.some(e => cat(e) === 'b' && e.lvl >= 2) && m.r[1] >= 15) tip('upg', 'Klikni na svou věž a vylepši ji (U). Na úrovni 2 zmáčkni U a pak A nebo B (nebo klikni na cestu).');
  if (m.doba >= 2) {
    const n2 = S.slots.filter(s => dobaOf(s.id) === 2).map(s => S.defs[s.id].name).slice(0, 4);
    tip('doba2', 'Doba II! Odemkly se silnější karty' + (n2.length ? ' (' + n2.join(', ') + ')' : '') + (!kral && S.cmds.utok ? ' a velení ' + S.cmds.utok.name + ' (G)' : '') + '.');
  }
  if ((m.ev || []).some(v => v[0] === 'alfa') || (m.msg || []).some(x => x.includes('Alfa'))) tip('alfa', 'V Mlze je Alfa. Je silná, ale kdo ji zabije, získá 🧪 a legendární bednu.');
  if (Object.keys(m.free).length) tip('free', 'Z bedny máš kartu zdarma (🎁 na liště). Použij ji, až se bude hodit.');
  if (m.ec && m.ec[0] === 1 && m.ec[1] <= 15) tip('ecl', 'Blíží se Zatmění: věže uvidí jen 1,5 pole. Šetři jednotky na útok ve tmě a hlídej svou polovinu.');
  if (kral && m.rl && t >= S.relicFrom) tip('relic', 'Uprostřed Mlhy se probudila Relikvie. Postav tam jednotku nebo Krále na 5 s a dostaneš +2 ⚡/s a 🧪.');
  // Stratég: the relic is not ours, so point at the squad button (H)
  if (!kral && m.rl && t >= S.relicFrom && m.rl[0] !== S.side && m.sq && m.sq[1] <= 0) tip('relicsq', 'Relikvie ještě není tvoje. Zmáčkni H a vyšli na ni četu (Obrněnec a 2 Pěšáci' + (m.sq[0] ? `, asi ${m.sq[0]} ⚡` : '') + '). Obsadí ji za 5 s.');
  if (!kral && m.rl && m.rl[0] === 1 - S.side && m.rl[3] <= 5) tip('relic2', 'Soupeř drží Relikvii a bohatne. Vyšli na ni četu (H) a Odstřelem (W) sestřel toho, kdo ji obsazuje.');
  if (kral && m.kr && m.kr.ult >= 100) tip('ult', 'Válečný pokřik je nabitý! Zmáčkni Q u svých jednotek: 8 s budou odolnější a rychlejší.');
  if (!kral && t > 200 && S.cmds.utok && !cmdLocked(S.cmds.utok)) {
    tip('utok', S.cmds.utok.turn ? 'G = Volání mrtvých: jako Útok! a navíc se zombie v Mlze, které jdou na tebe, obrátí na soupeře. Pošli vlnu a pak ho zmáčkni.'
      : 'G = Útok!: tvé jednotky 6 s dostávají od věží o polovinu méně. Pošli vlnu a pak ho zmáčkni.');
  }
  // own faction: its 2 tips (the same texts as in the lobby, without the markup)
  const ft = FAC_TIPS[S.facs[S.side]] || [];
  if (ft[0] && t > 25) tip('fac1', ft[0].replace(/<\/?b>/g, ''));
  if (ft[1] && t > 100) tip('fac2', ft[1].replace(/<\/?b>/g, ''));
  if (m.ni) tip('night', 'Poslední noc: tma, Mlha každých 20 s pohltí další sloupec a trůny ztrácejí životy. Padnou-li oba naráz, vyhraje ten, kdo nadělal víc škody.');
  if (kral && m.kr && m.fx.some(f => f[0] === 'a' && f[6] === m.kr.id)) tip('parry', 'Na tvého Krále míří rudá nit! Zmáčkni mezerník těsně před výstřelem a střelu odrazíš. Nebo uskoč výpadem (Shift).');
}

/* ---------------- side panel ---------------- */
function statRows(k, lvl, path) {
  const d = S.defs[k];
  const r = [];
  if (d.cat === 'u') {
    r.push(['Životy', d.hp], ['Poškození', d.dmg + ' / ' + dec(d.rate) + ' s'], ['Krok', 'každých ' + dec(d.step) + ' s']);
    if (d.sh) r.push(['Štít', d.sh]);
    if (d.max) r.push(['Nejvýš', d.max + ' ks']);

  } else if (d.cat === 'a') {
    r.push(['Cena', costHtml(costOf(k))], ['Cooldown', d.cd + ' s']);

  } else if (k === 'gen') {
    r.push(['Výnos', '+' + ([2, 3, 3][lvl - 1] + (path === 'A' ? 3 : 0)) + ' ' + SVG.e + '/s']);
  } else if (k === 'hlaska') {
    r.push(['Dohled', dec(path === 'A' ? 7 : lvl < 3 ? 4.5 + (lvl - 1) * 0.75 : 6) + ' polí']);
  } else if (isWallKind(k)) {
    r.push(['Materiál', d.levels[lvl - 1]], ['Odolnost', d.hps[lvl - 1]]);
  } else if (k === 'dilna') {
    r.push(['Výnos', dec(((d.scrap || [0.6])[lvl - 1] + (path === 'A' ? 0.6 : 0)).toFixed(1)) + ' ' + SVG.s + '/s'], ['Nejvýš', d.max + ' ks']);
    if (path === 'B') r.push(['Oprava', '5 životů/s okolo']);
  } else if (k === 'hnizdo') {
    r.push(['Vypouští', 'každých ' + (d.every || [15])[lvl - 1] + ' s'], ['Nejvýš', d.max + ' ks']);
  } else if (k === 'mina') {

    r.push(['Výbuch', Math.round(d.dmg * LVL[lvl - 1]) + ' v okruhu 1,2']);
  } else if (k === 'rusicka') {
    const [rr, f] = path === 'B' ? [2.4, 45] : lvl >= 2 ? [2.0, 30] : [1.6, 25];
    r.push(['Zpomalení', f + ' %'], ['Okruh', dec(rr) + ' pole']);
  } else {
    let dmg = d.dmg * LVL[lvl - 1], rate = d.rate, range = d.range + (lvl - 1) * 0.2;
    if (k === 'kulomet' && path === 'A') rate /= 2;
    if (k === 'kulomet' && path === 'B') dmg *= 1.5;
    if (k === 'plamen' && path === 'B') range = 2.6;
    r.push(['Poškození', Math.round(dmg)], ['Kadence', dec(rate.toFixed(2).replace(/0$/, '')) + ' s'], ['Dosah', dec(range.toFixed(1)) + ' pole']);
    if (k === 'tesla') r.push(['Cíle', path === 'A' ? 5 : 3]);
  }
  return r.map(([a, b]) => `<span>${a}</span><span>${b}</span>`).join('');
}
// The panel is rebuilt only when its structure changes. Live values (hp, cooldowns, affordability) are
// patched into [data-live] / [data-w] / [data-tg] / [data-need] so buttons survive the 20 Hz snapshots.
function kingBox(m, live) {
  if (S.mode !== 'kral' || !m || !m.kr) return '';
  const kr = m.kr, me = S.ents.get(kr.id), dead = kr.dead > 0;
  live.kdead = dead;
  live.khp = me ? `${me.hp} / ${me.maxhp}` : 'Král';
  live.kst = dead ? `padl · návrat za ${Math.ceil(kr.dead)} s` : kr.blk ? 'blokuje' : kr.bcd > 0 ? `blok za ${dec(kr.bcd.toFixed(1))} s` : 'blok připraven';
  let h = `<div class="kbox" data-tg="kdead dead"><div class="kh">${iconTag('kral', PAL.gilt, 'sm')}<b data-live="khp"></b><span data-live="kst"></span></div>`;
  if (kr.ult !== undefined) {
    const u = Math.max(0, Math.min(100, Math.round(kr.ult))), aura = kr.ua > 0;
    live.ultw = (aura ? Math.min(100, kr.ua / 8 * 100) : u) + '%';
    live.ultv = aura ? `působí ${Math.ceil(kr.ua)} s` : u >= 100 ? '<kbd>Q</kbd> připraveno' : u + ' %';
    live.ultr = !dead && (aura || u >= 100);
    h += '<div class="meter" data-tg="ultr ready"><i data-w="ultw"></i><span><span>Válečný pokřik</span><span data-live="ultv"></span></span></div>';
  }
  if (kr.dcd !== undefined) {
    live.dcd = kr.dcd > 0;
    live.dash = kr.dcd > 0 ? `za ${Math.ceil(kr.dcd)} s` : 'připraven';
    h += '<div class="kpips"><span class="pip" data-tg="dcd cd">Výpad <kbd>Shift</kbd> <span data-live="dash"></span></span></div>';
  }
  return h + '</div>';
}
function renderSide() {
  if (!S.defs || !S.inGame) return;
  const m = S.snap, live = {};
  let h = kingBox(m, live);
  const e = S.sel ? S.ents.get(S.sel) : null;
  const hov = S.barHover;
  if (e) {
    const d = S.defs[e.kind];
    const lvlName = isWallKind(e.kind) ? d.levels[e.lvl - 1] : 'Úroveň ' + e.lvl + (e.path ? ' · cesta ' + e.path + ': ' + d.paths[e.path][0] : '');
    live.hp = `${e.hp} / ${e.maxhp}`;
    h += `<h3>${iconTag(e.kind, COL[S.side])}${esc(d.name)}</h3><div class="lvl">${esc(lvlName)}${e.flags & 128 ? ' · skrytá před soupeřem' : ''}</div><p>${fmt(d.desc)}</p>`;
    h += `<div class="stats"><span>Stav</span><span data-live="hp"></span>${statRows(e.kind, e.lvl, e.path)}</div>`;
    if (e.lvl < 3) {
      const c = d.up[e.lvl - 1], need = JSON.stringify(c);
      if (e.lvl === 2 && !isWallKind(e.kind)) {
        const open = !!(S.choose && S.choose.id === e.id);
        h += `<p class="${open ? 'hint' : ''}">Úroveň 3: vyber cestu. Klikni na ni, nebo <kbd>U</kbd> a pak <kbd>A</kbd> / <kbd>B</kbd>.</p>`;
        for (const p of ['A', 'B']) {
          h += `<button class="act up${open ? ' pick' : ''}" tabindex="-1" data-a="upg" data-p="${p}" data-need="${need}"><b><span class="sh">${p}</span>${esc(d.paths[p][0])}${open ? `<kbd>${p}</kbd>` : ''}</b>`
            + `<span>${fmt(d.paths[p][1])}</span><br>${costHtml(c)}</button>`;
        }
      } else {
        const nm = isWallKind(e.kind) ? 'Zesílit na ' + d.levels[e.lvl].toLowerCase() : 'Vylepšit na úroveň 2';
        h += `<button class="act up" tabindex="-1" data-a="upg" data-need="${need}"><b>${nm}<kbd>U</kbd></b>${costHtml(c)}</button>`;
      }
    } else h += '<p>Maximální úroveň.</p>';
    h += '<button class="act sell" tabindex="-1" data-a="sell"><b>Prodat<kbd>X</kbd></b><span>Vrátí 50 % ceny podle stavu.</span></button>';
  } else if (hov === 'horde') {
    h += `<h3>${iconTag('horde', PAL.flesh)}Tlupa</h3><div class="lvl">${costHtml([m ? m.hc : S.horde[0], 0])} · obnova ${S.horde[1]} s</div><p>Vypustí 5 zombie (po 6. minutě i Obra) z Mlhy přímo na soupeře.</p>`;
  } else if (hov === 'squad') {
    h += `<h3>${iconTag('relic', PAL.moon)}Četa na Relikvii</h3><div class="lvl">Klávesa H · obnova ${S.squad[0] || 20} s${m && m.sq ? ` · ${costHtml([m.sq[0], 0])}` : ''}</div><p>Vyšle na Relikvii Obrněnce a 2 Pěšáky, jinak 3 nejlevnější jednotky z balíčku. Vyrazí postupně a každý zaplatí svou cenu. Jen pro Stratéga.</p>`;
  } else if (hov && hov.startsWith('cmd:')) {
    const id = hov.slice(4), c = S.cmds[id];
    h += `<h3>${iconTag(id, PAL.moon)}${esc(c.name)}</h3><div class="lvl">Klávesa ${c.key} · obnova ${c.cd} s${cmdDoba(c) ? ` · <span class="doba">Doba ${roman(cmdDoba(c))}</span>` : ''}</div><p>${fmt(c.desc)}</p>`;
  } else if (hov || (S.pick && S.pick.kind !== 'cmd')) {
    const k = hov || S.pick.id;
    const d = S.defs[k];
    h += `<h3>${iconTag(k, cardCol(k))}${esc(d.name)}</h3><div class="lvl">${d.cat === 'a' ? cardCostHtml(k) : costHtml(costOf(k)) + (dobaOf(k) ? ` · <span class="doba">Doba ${roman(dobaOf(k))}</span>` : '')}${d.max ? ` · nejvýš ${d.max}` : ''}</div><p>${fmt(d.desc)}</p>`;
    if (d.cat !== 'a') h += `<div class="stats">${statRows(k, 1, '')}</div>`;
    if (d.paths) h += `<p>Úroveň 3: <b>A</b> ${esc(d.paths.A[0])} · <b>B</b> ${esc(d.paths.B[0])}</p>`;
    if (freeOf(k)) h += `<p class="hint">${SVG.g} Máš ${freeOf(k)}× zdarma z bedny.</p>`;
    if (S.pick && S.pick.id === k) h += `<p class="hint">${d.cat === 'a' ? 'Klikni na cíl na poli.' : 'Klikni na pole na své polovině.'} Pravé tlačítko ruší.</p>`;
  } else if (S.pick && S.pick.kind === 'cmd') {
    const c = S.cmds[S.pick.id];
    h += `<h3>${iconTag(S.pick.id, PAL.moon)}${esc(c.name)}</h3><p>${fmt(c.desc)}</p><p class="hint">${c.target === 'own' ? 'Klikni na svou stavbu.' : c.target === 'crate' ? 'Klikni na bednu v Mlze.' : 'Klikni na viditelné pole.'} Pravé tlačítko ruší.</p>`;
  } else {
    h += '<h3>Velení</h3>';
    if (m && S.mode === 'kral' && m.kr) {
      h += '<p><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> pohyb · <kbd>Mezerník</kbd> blok · <kbd>F</kbd> oprava · <kbd>Shift</kbd> výpad · <kbd>Q</kbd> pokřik</p>';
    } else if (m && S.mode === 'strateg') {
      for (const [id, c] of Object.entries(S.cmds)) {
        const cd = m.cd['cmd_' + id] || 0, lk = cmdLocked(c);
        live['cp' + id] = cd > 0 || lk;
        live['ct' + id] = lk ? `zámek · odemkne se v Době ${roman(cmdDoba(c))}` : cd > 0 ? 'připraveno za ' + Math.ceil(cd) + ' s' : fmt(c.desc);
        live['cw' + id] = (cd > 0 ? cd / c.cd * 100 : 0) + '%';
        h += `<button class="act cmd" tabindex="-1" data-a="cmd" data-id="${id}" data-tg="cp${id} poor"><b>${iconTag(id, PAL.moon, 'sm')} ${esc(c.name)}<kbd>${c.key}</kbd></b><span data-live="ct${id}"></span><i class="cdl" data-w="cw${id}"></i></button>`;
      }
      const sq = m.sq;
      live.cpsq = !sq || sq[1] > 0;
      live.ctsq = !sq ? 'Odemkne se, až se probudí Relikvie.' : sq[1] > 0 ? 'připraveno za ' + Math.ceil(sq[1]) + ' s' : `Obrněnec a 2 Pěšáci na Relikvii (${sq[0]} ${SVG.e})`;
      live.cwsq = (sq && sq[1] > 0 ? sq[1] / (S.squad[0] || 20) * 100 : 0) + '%';
      h += `<button class="act cmd" tabindex="-1" data-a="squad" data-tg="cpsq poor"><b>${iconTag('relic', PAL.moon, 'sm')} Četa na Relikvii<kbd>H</kbd></b><span data-live="ctsq"></span><i class="cdl" data-w="cwsq"></i></button>`;
    }
    if (m) {
      live.vz = String(m.r[2]);
      h += `<p>${SVG.v} Vzorky: <b data-live="vz"></b> · Doba ${roman(m.doba)} · výzkumů ${m.tech.length} <button class="linkb" tabindex="-1" data-a="res">otevřít výzkum (V)</button></p>`;
    }
    if (S.tips && STEPS.some(([id]) => !S.steps.has(id))) {
      h += '<h4>První kroky</h4><ul class="steps">' + STEPS.map(([id, t]) => `<li class="${S.steps.has(id) ? 'done' : ''}">${t}</li>`).join('') + '</ul>';
    } else h += '<p>Vyber kartu dole nebo klikni na svou stavbu. Klikni na trosky na své polovině pro šrot.</p>';
    if (m && m.job) { live.job = Math.round(m.job[2] * 100) + ' %'; h += '<p class="hint">Čety rozebírají trosky: <b data-live="job"></b></p>'; }
  }
  const helpKey = S.mode === 'strateg' ? '<kbd>H</kbd> četa na Relikvii · <button class="linkb" tabindex="-1" data-a="help">nápověda <kbd>F1</kbd></button>' : '<kbd>H</kbd> nápověda';
  h += `<div class="keys">${helpKey} · <kbd>M</kbd> zvuk · <kbd>Esc</kbd> ${S.solo ? 'zrušit, pauza' : 'zrušit'} · <button class="linkb" tabindex="-1" data-a="tips">rady ${S.tips ? 'vypnout' : 'zapnout'}</button></div>`;
  const box = $('#sideMain');
  if (h !== S.sideHtml) { S.sideHtml = h; box.innerHTML = h; }
  for (const el of box.querySelectorAll('[data-live]')) setHtml(el, live[el.dataset.live] === undefined ? '' : String(live[el.dataset.live]));
  for (const el of box.querySelectorAll('[data-w]')) el.style.width = live[el.dataset.w] || '0%';
  for (const el of box.querySelectorAll('[data-tg]')) { const [k, c] = el.dataset.tg.split(' '); el.classList.toggle(c, !!live[k]); }
  for (const el of box.querySelectorAll('[data-need]')) el.classList.toggle('poor', !afford(JSON.parse(el.dataset.need)));
}
// pointerdown (button 0): a click is lost when the button is replaced between mousedown and mouseup
$('#side').addEventListener('pointerdown', ev => {
  if (ev.button !== 0 || S.ending) return;
  const b = ev.target.closest('[data-a]');
  if (!b) return;
  ev.preventDefault();
  const a = b.dataset.a;
  if (a === 'res') return toggleResearch();
  if (a === 'tips') { S.tips = !S.tips; save('hmk_tips', S.tips ? '1' : '0'); $('#tipsChk').checked = S.tips; S.sideHtml = ''; return renderSide(); }
  if (a === 'cmd') { flashCls(b, 'press', 150); return pickCmd(b.dataset.id); }
  if (a === 'squad') { flashCls(b, 'press', 150); return useSquad(); }
  if (a === 'help') return toggleHelp(true);
  const e = S.sel && S.ents.get(S.sel);
  if (!e) return;
  if (a === 'upg') doUpgrade(e, b.dataset.p || '', b);
  else if (a === 'sell') doSell(e);
});

/* ---------------- research ---------------- */
function toggleResearch(force) {
  S.resOpen = force === undefined ? !S.resOpen : force;
  $('#resOv').classList.toggle('hidden', !S.resOpen);
  if (S.resOpen) releaseKeys();
  S.resHtml = '';
  renderResearch();
}
function resState(id, m) {
  const r = S.research[id], done = m.tech.includes(id), open = r.tier === 1 || m.tech.includes(r.branch + (r.tier - 1));
  const cost = rcostOf(id);          // faction price (Korporace: tier 1 costs 1 🧪)
  return { r, done, open, cost, can: !done && open && m.r[2] >= cost };
}
function renderResearch() {
  if (!S.resOpen || !S.snap) return;
  const m = S.snap;
  const next = m.doba >= 3 ? 'Doba III je nejvyšší.' : `Doba ${roman(m.doba + 1)} po ${S.dobaAt[m.doba - 1]} výzkumech.`;
  setHtml($('#resInfo'), `${SVG.v} Vzorky: <b>${m.r[2]}</b> · Doba ${roman(m.doba)} · ${next}`);
  let h = '';
  for (const [br, name] of Object.entries(S.branches)) {
    h += `<div><h3>${esc(name)}</h3>`;
    for (let tier = 1; tier <= 3; tier++) {
      const id = br + tier, { r, done, open } = resState(id, m);
      const state = done ? 'vyzkoumáno' : !open ? 'zámek · nejdřív předchozí stupeň' : `${rcostOf(id)} ${SVG.v}`;
      h += `<button class="rb ${done ? 'done' : ''} ${!open ? 'locked' : ''}" tabindex="-1" data-res="${id}"><b>${roman(tier)}. ${esc(r.name)}</b><span>${fmt(r.desc)}</span><span class="st">${state}</span></button>`;
    }
    h += '</div>';
  }
  const tree = $('#resTree');
  if (h !== S.resHtml) { S.resHtml = h; tree.innerHTML = h; }
  for (const b of tree.querySelectorAll('[data-res]')) {
    const st = resState(b.dataset.res, m);
    b.classList.toggle('can', st.can);
    b.classList.toggle('poor', !st.can && !st.done && st.open);
  }
}
$('#resTree').addEventListener('pointerdown', ev => {
  if (ev.button !== 0 || !S.snap) return;
  const b = ev.target.closest('[data-res]');
  if (!b) return;
  ev.preventDefault();
  const st = resState(b.dataset.res, S.snap);
  if (st.done) return;
  if (!st.open) return denyBtn(b, 'Nejdřív vyzkoumej předchozí stupeň.');
  if (!st.can) return denyBtn(b, `Na výzkum chybí ${st.cost - S.snap.r[2]} 🧪.`);
  send({ t: 'res', id: b.dataset.res });
  flashCls(b, 'press', 150);
  uiSfx('tick');
});
$('#resBtn').onclick = () => toggleResearch();
$('#resClose').onclick = () => toggleResearch(false);
$('#resOv').addEventListener('click', ev => { if (ev.target.id === 'resOv') toggleResearch(false); });

/* ---------------- end ---------------- */
// The finale plays on the board first (render.js), then the overlay. Input is ignored while S.ending.
function endGame(m) {
  if (S.ending) return;
  if (!S.inGame) return showEndOverlay(m);
  S.ending = true;
  releaseKeys();
  S.pick = null; S.sel = null; S.choose = null;
  toggleResearch(false);
  $('#helpOv').classList.add('hidden');
  annClear();
  updateBar(); renderSide(); if (S.snap) hud(S.snap);
  if (typeof audioEnd === 'function') audioEnd(m.winner === -1 ? 'draw' : m.winner === S.side ? 'win' : 'lose');
  let fin = false;
  const done = () => { if (fin) return; fin = true; S.ending = false; S.inGame = false; showEndOverlay(m); };
  if (typeof startFinale === 'function' && S.snap) {
    setTimeout(done, 6000);
    try { startFinale(m, done); } catch (err) { console.error(err); done(); }
  } else done();
}
function showEndOverlay(m) {
  const res = m.winner === -1 ? 'draw' : m.winner === S.side ? 'win' : 'lose';
  const t = $('#endT');
  const typ = m.type || S.type;
  let title = { draw: 'Remíza', win: 'Vítězství', lose: 'Porážka' }[res];
  if (typ === 'puzzle') title = m.puzzle && m.puzzle.ok ? 'Hádanka vyřešena' : 'Hádanka nevyřešena';
  else if (typ === 'vyuka') title = res === 'win' ? 'Výuka dokončena' : 'Výuka ukončena';
  else if (typ === 'preziti') title = m.winner === -1 ? 'Konec přežití' : res === 'win' ? 'Vydržel jsi déle' : 'Soupeř vydržel déle';
  t.textContent = title;
  t.className = res;
  const tm = Math.floor(m.tm || 0);
  $('#endR').textContent = m.reason + ' Délka zápasu ' + Math.floor(tm / 60) + ' min ' + (tm % 60) + ' s.';
  const dl = m.dl || (S.snap && S.snap.dl);
  const rows = [['Trůn', i => m.th[i]]];
  if (dl) rows.push(['Škoda na trůnu a stavbách', i => dl[i]]);
  rows.push(['Zabito', i => m.stats[i].kills], ['Jednotek', i => m.stats[i].units], ['Staveb', i => m.stats[i].built],
    ['Bedny', i => m.stats[i].crates], ['Výzkumy', i => m.stats[i].techs]);
  const w = i => (m.winner === i ? ' w' : '');
  $('#endS').innerHTML = `<thead><tr><th></th><th class="ca${w(0)}">${EMB[0]}${esc(m.names[0])}</th><th class="cb${w(1)}">${EMB[1]}${esc(m.names[1])}</th></tr></thead><tbody>`
    + rows.map(([lbl, f]) => `<tr><th>${lbl}</th><td class="${w(0)}" data-n="${+f(0) || 0}">0</td><td class="${w(1)}" data-n="${+f(1) || 0}">0</td></tr>`).join('') + '</tbody>';
  $('#endMeta').innerHTML = '';
  $('#endOv').classList.remove('hidden');
  uiCrown($('#endCrown'), res);
  uiSfx(res);
  // stat rows count up one after another, with a tick per row
  [...$('#endS').querySelectorAll('tbody tr')].forEach((tr, ri) => setTimeout(() => {
    uiSfx('tick');
    const cells = [...tr.querySelectorAll('td')], t0 = performance.now();
    if (document.hidden) { cells.forEach(td => { td.textContent = td.dataset.n; }); return; }
    const step = now => {
      const k = Math.min(1, (now - t0) / 380);
      cells.forEach(td => { td.textContent = Math.round(+td.dataset.n * (1 - (1 - k) * (1 - k))); });
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, 250 + ri * 110));
  emit('end', m, $('#endMeta'));
}
$('#endBtn').onclick = () => { uiSfx('click'); $('#endOv').classList.add('hidden'); showLobby(); };
