'use strict';
// Mouse/keyboard input and King movement prediction.
/* ---------------- input ---------------- */
for (const t of ['pointermove', 'pointerdown']) document.addEventListener(t, ev => { S.mouse = [ev.clientX, ev.clientY]; }, { passive: true, capture: true });
cv.addEventListener('mousemove', ev => { const r = cv.getBoundingClientRect(); S.hover = cellAt(ev.clientX - r.left, ev.clientY - r.top); updateTip(); });
cv.addEventListener('mouseleave', () => { S.hover = null; updateTip(); });
cv.addEventListener('contextmenu', ev => { ev.preventDefault(); if (!S.ending) cancelPick(); });
cv.addEventListener('mousedown', ev => {
  if (ev.button !== 0 || !S.snap || S.ending) return;
  const r = cv.getBoundingClientRect();
  const c = cellAt(ev.clientX - r.left, ev.clientY - r.top);
  if (!c) return;
  if (S.pick) return useAt(S.pick, c.x, c.y);
  const mine = entsAt(c.x, c.y).find(e => e.side === S.side && S.defs[e.kind].cat === 'b');
  if (mine) return selectBuilding(mine.id);
  if (own(c.x) && ter(c.x, c.y) === '#') {
    if (S.snap.job) return refuse('Čety už rozebírají jiné trosky.');
    send({ t: 'scrap', x: c.x, y: c.y });
    return;
  }
  S.sel = null; S.choose = null; renderSide();
});

const KING_KEYS = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'Space', 'KeyF', 'ShiftLeft', 'ShiftRight', 'KeyQ'];
function updateInput() {
  const k = S.keys;
  const dx = (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0), dy = (k.KeyS ? 1 : 0) - (k.KeyW ? 1 : 0);
  const inp = { mx: S.side === 0 ? dx : -dx, my: dy, b: !!k.Space, r: !!k.KeyF, d: !!(k.ShiftLeft || k.ShiftRight), u: !!k.KeyQ };
  if (Object.keys(inp).some(n => inp[n] !== S.inp[n])) {
    S.inp = inp;
    send(Object.assign({ t: 'in' }, inp));
  }
}
function releaseKeys() { S.keys = {}; if (S.inGame && S.mode === 'kral') updateInput(); }
const helpShown = () => !$('#helpOv').classList.contains('hidden');
// modal dialogs of the solo/meta modules (pause menu, welcome card, settings): while one is open the board gets no keys
const MODAL_IDS = ['#pauseOv', '#setOv', '#welcomeOv'];
const modalOpen = () => MODAL_IDS.some(s => { const el = $(s); return !!el && !el.classList.contains('hidden'); });
function toggleHelp(force) {
  const open = force === undefined ? !helpShown() : force;
  $('#helpOv').classList.toggle('hidden', !open);
  if (open) releaseKeys();
}
// Dash and war cry say why they do nothing instead of failing silently.
function kingKeyBlock(code) {
  const kr = S.snap && S.snap.kr;
  if (!kr || (code !== 'KeyQ' && code !== 'ShiftLeft' && code !== 'ShiftRight')) return '';
  if (kr.dead > 0) return `Král padl, vrátí se za ${Math.ceil(kr.dead)} s.`;
  if (code === 'KeyQ' && kr.ua > 0) return 'Válečný pokřik už působí.';
  if (code === 'KeyQ' && kr.ult !== undefined && kr.ult < 100) return `Válečný pokřik ještě není nabitý (${Math.round(kr.ult)} %).`;
  if (code !== 'KeyQ' && kr.dcd > 0) return `Výpad bude připraven za ${Math.ceil(kr.dcd)} s.`;
  return '';
}
window.addEventListener('keydown', ev => {
  const code = ev.code, tag = ev.target.tagName;
  if ((tag === 'INPUT' && ev.target.type === 'text') || tag === 'SELECT') return;
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  if (code === 'F1') { ev.preventDefault(); if (!ev.repeat && !modalOpen()) toggleHelp(); return; }
  if (code === 'Escape' && optShown()) { $('#optPop').classList.add('hidden'); return; }
  if (code === 'KeyM') { if (!ev.repeat) toggleMute(); return; }
  // a modal dialog owns the keyboard: Esc is handed to its module through the bus ('esc', 'modal'), nothing reaches the board
  if (modalOpen()) {
    if (code === 'Escape' && !ev.repeat) emit('esc', 'modal');
    if (Object.keys(S.keys).some(k => S.keys[k])) releaseKeys();
    return;
  }
  // H: relic squad for the Strateg in a match, help everywhere else (the Strateg opens help with F1)
  if (code === 'KeyH') {
    if (ev.repeat) return;
    if (S.inGame && !S.ending && S.mode === 'strateg' && !helpShown() && !S.resOpen) useSquad(); else toggleHelp();
    return;
  }
  if (!S.inGame || S.ending) { if (code === 'Escape') toggleHelp(false); return; }
  if (code === 'Space') ev.preventDefault();
  // modal overlays (Help, Research): only Esc, H, M and V work, nothing reaches the board behind them
  if (helpShown() || S.resOpen) {
    if (ev.repeat) return;
    if (code === 'Escape') { if (helpShown()) toggleHelp(false); else toggleResearch(false); }
    else if (code === 'KeyV' && !helpShown()) toggleResearch();
    return;
  }
  if (optShown() && /^(Key|Digit|Space)/.test(code)) $('#optPop').classList.add('hidden');   // a game key closes the settings popover
  // open path chooser: the next fresh A/B picks the path and never reaches the King keys
  if (S.choose && !ev.repeat && (code === 'KeyA' || code === 'KeyB')) return choosePath(code === 'KeyA' ? 'A' : 'B');
  if (S.mode === 'kral' && KING_KEYS.includes(code)) {
    if (ev.repeat || S.resOpen || helpShown()) return;
    const why = kingKeyBlock(code);
    if (why) return refuse(why);
    S.keys[code] = true; updateInput();
    return;
  }
  if (ev.repeat) return;
  if (code === 'Escape') {
    if (helpShown()) toggleHelp(false);
    else if (S.choose) { S.choose = null; renderSide(); hud(S.snap); }
    else if (S.resOpen) toggleResearch(false);
    else if (S.pick || S.sel) cancelPick();
    else if (S.solo) emit('esc', 'idle');          // nothing to cancel: modes.js opens the pause menu
    return;
  }
  if (code === 'KeyV') return toggleResearch();
  const si = SLOT_CODES.indexOf(code);
  if (si >= 0) {
    if (S.slots[si]) { flashCls($(`#bar .bb[data-slot="${si}"]`), 'press', 150); pickCard(S.slots[si].id); }
    return;
  }
  if (code === 'KeyT') { flashCls($('#bar .bb[data-horde]'), 'press', 150); return useHorde(); }
  if (code === 'KeyC') return convert();
  if (S.mode === 'strateg') {
    const cmd = Object.entries(S.cmds).find(([, c]) => 'Key' + c.key === code);
    if (cmd) { flashCls($(`#bar .bb[data-cmd="${cmd[0]}"]`), 'press', 150); return pickCmd(cmd[0]); }
  }
  if (code === 'KeyU') return keyUpgrade();
  const e = S.sel && S.ents.get(S.sel);
  if (code === 'KeyX' || code === 'Delete') return e ? doSell(e) : refuse('Nejdřív klikni na svou stavbu.');
  if ((code === 'KeyA' || code === 'KeyB') && e && e.lvl === 2 && !isWallKind(e.kind)) refuse('Cestu vybereš takto: U a pak A nebo B.');
});
window.addEventListener('keyup', ev => {
  if (KING_KEYS.includes(ev.code) && S.keys[ev.code]) { S.keys[ev.code] = false; if (S.inGame && S.mode === 'kral') updateInput(); }
});
window.addEventListener('blur', releaseKeys);

// "Kanál: jednotky a zombie jsou tu rychlejší" -> bold name plus the rest; '' for plain floor and rubble (handled apart)
function terrainTip(ch) {
  const t = typeof TERRAIN !== 'undefined' ? TERRAIN[ch] : null;
  if (!t || !t.tip || ch === '#') return '';
  const i = t.tip.indexOf(': ');
  return i < 0 ? esc(t.tip) : `<b>${esc(t.tip.slice(0, i))}</b>${esc(t.tip.slice(i))}`;
}
function updateTip() {
  const tipEl = $('#tip');
  const c = S.hover;
  if (!c || !S.snap) { tipEl.classList.add('hidden'); return; }
  let t = '';
  const here = visible(c.x, c.y) ? entsAt(c.x, c.y) : entsAt(c.x, c.y).filter(e => e.side === S.side);
  const crate = crateAt(c.x, c.y), z = S.relicZone;
  if (here.length) {
    t = here.map(e => {
      const d = S.defs[e.kind];
      const who = e.side === 2 ? 'zombie' : e.side === S.side ? 'tvůj' : 'nepřítel';
      const rank = d.cat !== 'u' ? '' : e.flags & 1 ? ' · veterán' : e.side === S.side ? ` · zářezy ${e.kills || 0}/3` : '';
      return `<b>${esc(d.name)}</b> (${who}) ${e.hp}/${e.maxhp}${rank}`;
    }).join(' · ');
  } else if (crate) {
    const rar = esc(S.rarity[crate[3]]), ch = [crate[6] || 0, crate[7] || 0];
    t = crate[4] > 0 ? `<b>Bedna (${rar})</b> dopadne za ${Math.ceil(crate[4])} s`
      : `<b>Zásobovací bedna (${rar})</b>, zmizí za ${crate[5]} s` + (crate[8] ? ' · <b>sporná</b>, vyžeň soupeře' : '')
        + (ch[0] || ch[1] ? ` · sbíráš ${Math.round(ch[S.side] * 100)} %, soupeř ${Math.round(ch[1 - S.side] * 100)} %` : '');
  } else if (ter(c.x, c.y) === '#') t = own(c.x) ? `<b>Trosky</b>: klikni pro rozebrání (+25 ${SVG.s}, 4 s)` : '<b>Trosky</b>: neprůchozí';
  else if (z && S.snap.rl && c.x >= z[0] && c.x <= z[1] && c.y >= z[2] && c.y <= z[3]) t = `<b>Relikvie</b>: obsaď ji na 5 s jen svými jednotkami nebo Králem. Dává +2 ${SVG.e}/s a každých 40 s ${SVG.v}.`;
  else if (terrainTip(ter(c.x, c.y))) t = terrainTip(ter(c.x, c.y)) + (inMist(c.x) ? ' · <b>Mlha</b>: odtud lezou zombie' : '');
  else if (!visible(c.x, c.y)) {
    const g = [...S.ghosts.values()].find(g => g.cx === c.x && g.cy === c.y);
    t = g ? `<b>${esc(S.defs[g.kind].name)}</b> (naposledy viděno)` : 'Neprozkoumáno: postav Hlásku, pošli dron nebo jednotky';
  } else if (inMist(c.x)) t = '<b>Mlha</b>: odtud lezou zombie, jednotkám a Králi pomalu ubírá životy';
  if (!t) { tipEl.classList.add('hidden'); return; }
  tipEl.innerHTML = t; tipEl.classList.remove('hidden');
}

/* ---------------- King prediction ---------------- */
function kralBlocked(x, y) {
  const r = K().radius;
  if (x < -0.5 + r || x > S.W - 0.5 - r || y < -0.5 + r || y > S.H - 0.5 - r) return true;
  for (let cy = Math.floor(y - r + 0.5); cy <= Math.floor(y + r + 0.5); cy++) {
    for (let cx = Math.floor(x - r + 0.5); cx <= Math.floor(x + r + 0.5); cx++) {
      if (cx < 0 || cy < 0 || cx >= S.W || cy >= S.H) continue;
      if (!terWalk(ter(cx, cy)) || barrier(cx, cy)) return true;
      const b = S.bmap.get(cx + ',' + cy);
      if (b && b.side !== S.side && b.kind !== 'mina') return true;
    }
  }
  return false;
}
// Blocked head-on: drift towards the centre of a neighbouring free lane (same rule as the server).
function kralSlide(v, step, aheadBlocked, hereBlocked, prefer) {
  const r = Math.round(v);
  const cands = [...new Set([Math.floor(v), Math.ceil(v), r - 1, r + 1])].filter(c => Math.abs(c - v) <= 1)
    .sort((a, b) => (Math.abs(a - v) - Math.abs(b - v)) || (Math.abs(a - prefer) - Math.abs(b - prefer)));
  for (const c of cands) {
    if (!aheadBlocked(c)) {
      const nv = v + Math.max(-step, Math.min(step, c - v));
      return hereBlocked(nv) ? v : nv;
    }
  }
  return v;
}
function predictKing(dt) {
  if (S.mode !== 'kral' || !S.kp || !S.snap) return;
  const me = S.ents.get(S.kp.id);
  if (!me || (me.flags & 32)) return;
  const { mx, my } = S.inp;
  if (!mx && !my) return;
  const kr = S.snap.kr || {};
  let sp = K().speed * (kr.blk ? 0.4 : 1) / (kr.sf || (me.flags & 64 ? 1.4 : 1));
  if (mx && my) sp *= 0.7071;
  const p = S.kp;
  if (ter(Math.max(0, Math.min(S.W - 1, Math.round(p.x))), Math.max(0, Math.min(S.H - 1, Math.round(p.y)))) === '~') sp *= 1.25;   // canal: the King runs faster (as on the server)
  const step = sp * dt;
  const stuck = kralBlocked(p.x, p.y);
  const nx = p.x + mx * step;
  if (stuck || !kralBlocked(nx, p.y)) p.x = nx;
  else if (!my) p.y = kralSlide(p.y, step, c => kralBlocked(nx, c), c => kralBlocked(p.x, c), 0);
  const ny = p.y + my * step;
  if (stuck || !kralBlocked(p.x, ny)) p.y = ny;
  else if (!mx) p.x = kralSlide(p.x, step, c => kralBlocked(c, ny), c => kralBlocked(c, p.y), S.side === 0 ? 0 : S.W - 1);
  const r = K().radius;
  p.x = Math.min(S.W - 0.5 - r, Math.max(-0.5 + r, p.x));
  p.y = Math.min(S.H - 0.5 - r, Math.max(-0.5 + r, p.y));
}
