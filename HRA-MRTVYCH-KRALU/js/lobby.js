'use strict';
// Lobby: layout, room and solo settings, deck, folio tabs (SPEC 3.5, META 4.1). The server messages arrive through the bus
// ('defs', 'lobby', 'm:me', 'm:lerr'), the network code itself lives in ui.js.
/* ---------------- state ---------------- */
const ROOM_TYPES = ['souboj', 'preziti'];             // played in the room seats: settings are shared and sent as `cfg`
const TYPE_ORDER = ['souboj', 'preziti', 'vycvik', 'puzzle'];
const TYPE_ICON = { souboj: 'utok', preziti: 'horde', vycvik: 'stit', puzzle: 'vzorek' };
const FALLBACK_TYPES = [
  { id: 'souboj', name: 'Souboj', desc: 'Dva hráči proti sobě v místní síti.' },
  { id: 'preziti', name: 'Přežití', desc: 'Každý hájí svůj trůn proti stejným vlnám zombie. Vydrží déle ten lepší.' },
  { id: 'vycvik', name: 'Výcvik', desc: 'Zápas proti počítači ve třech obtížnostech.' },
  { id: 'puzzle', name: 'Puzzle', desc: 'Úlohy s pevným zadáním, každou lze splnit na tři hvězdy.' },
];
const FALLBACK_DIFFS = [['lehka', 'Lehká', 'Zbloudilý mnich'], ['stredni', 'Střední', 'Kastelán'], ['tezka', 'Těžká', 'Mrtvý velmistr']];
const isRoomType = t => ROOM_TYPES.includes(t);
const LOBBY = {
  type: 'souboj',                                       // the selected game type
  room: { type: 'souboj', mode: 'kral', map: 'nahodna' }, // shared room cfg as the server sent it
  solo: { mode: 'kral', map: 'predmesti', ai: 'lehka', aip: null }, // local choices for the solo types (aip = Přežití opponent)
  puzzle: null,                                         // chosen puzzle id (modes.js sets it)
  fac: 'bez',                                           // chosen faction (M3-E1 fills the picker)
  tab: 'deck', soloRun: [0, 2], pane: '', errAt: 0,
};
function loadCfg() {
  let c = {};
  try { c = JSON.parse(load('hmk_cfg', '{}')) || {}; } catch (e) { c = {}; }
  if (TYPE_ORDER.includes(c.type)) LOBBY.type = c.type;
  if (c.mode === 'kral' || c.mode === 'strateg') LOBBY.solo.mode = c.mode;
  if (typeof c.map === 'string' && /^[a-z]{1,16}$/.test(c.map)) LOBBY.solo.map = c.map;
  if (typeof c.ai === 'string' && /^[a-z]{1,16}$/.test(c.ai)) LOBBY.solo.ai = c.ai;
  if (c.aip === null || (typeof c.aip === 'string' && /^[a-z]{1,16}$/.test(c.aip))) LOBBY.solo.aip = c.aip;
  const f = load('hmk_fac', 'bez');
  if (/^[a-z]{1,8}$/.test(f)) LOBBY.fac = f;
  LOBBY.tab = load('hmk_tab', 'deck');
}
function saveCfg() { save('hmk_cfg', JSON.stringify({ type: LOBBY.type, mode: LOBBY.solo.mode, map: LOBBY.solo.map, ai: LOBBY.solo.ai, aip: LOBBY.solo.aip })); }
loadCfg();
const queuedNow = () => !S.lobby || S.lobby.you === null || S.lobby.you === undefined;
const canCfg = () => !queuedNow() && !S.lobby.playing;   // the room cfg may change only from a seat while no room match runs
const curMode = () => (isRoomType(LOBBY.type) ? LOBBY.room.mode : LOBBY.solo.mode);
const curMap = () => (isRoomType(LOBBY.type) ? LOBBY.room.map : LOBBY.solo.map);
const typeList = () => {
  const src = S.types && S.types.length ? S.types : FALLBACK_TYPES;
  return TYPE_ORDER.map(id => src.find(t => t.id === id) || FALLBACK_TYPES.find(t => t.id === id)).filter(Boolean);
};
const diffList = () => (S.diffs && S.diffs.length ? S.diffs : FALLBACK_DIFFS);

/* ---------------- messages from the server ---------------- */
on('defs', m => {
  if (m.types) S.types = m.types;
  if (m.maps) S.maps = m.maps;
  if (m.diffs) S.diffs = m.diffs;
  if (m.puzzles) S.puzzles = m.puzzles;
  if (m.squad) S.squad = m.squad;
  if (m.soloMax) S.soloMax = m.soloMax;
  applyFacDefs(m);
  normFac();
  S.deck = loadDeck(LOBBY.fac);
  if (!LOBBY.puzzle && S.puzzles.length) LOBBY.puzzle = S.puzzles[0].id;
  renderDeck();
  fillMapSel();
  renderSettings(true);
  buildTabs();
});
/* ---------------- factions: catalog, picker, deck per faction ---------------- */
// defs.factions {id:{name,motto,desc,passives,cards,perk,cmdv}}, facPool {id:[cards]}, facCosts {id:{kind:[e,s]}}, facRec {id:[cards]}.
// Without them (an older server) only "Bez frakce" is offered and the picker stays hidden.
function applyFacDefs(m) {
  if (m.factions) S.fdefs = m.factions;
  if (m.facPool) S.facPool = m.facPool;
  if (m.facCosts) S.facCosts = m.facCosts;
  if (m.facRec) S.facRec = m.facRec;
}
const facList = () => FAC_IDS.filter(f => f === 'bez' || (S.fdefs && S.fdefs[f]));
const poolOf = f => (S.facPool && S.facPool[f]) || S.pool;
const recOf = f => (S.facRec && S.facRec[f]) || S.recommended;
function normFac() { if (!facList().includes(LOBBY.fac)) LOBBY.fac = 'bez'; }
const deckKey = f => 'hmk_deck_' + f;
// The deck of a faction from localStorage (hmk_deck_<fac>), cleaned against the faction's pool. The old single `hmk_deck` moves to
// hmk_deck_bez once. An empty or unusable deck becomes the recommended one.
function loadDeck(f) {
  let raw = load(deckKey(f), null);
  if (raw === null && f === 'bez') {
    const old = load('hmk_deck', null);
    if (old !== null) { raw = old; save(deckKey('bez'), old); try { localStorage.removeItem('hmk_deck'); } catch (e) {} }
  }
  let d = [];
  try { d = JSON.parse(raw || '[]'); } catch (e) { d = []; }
  const pool = poolOf(f);
  d = Array.isArray(d) ? [...new Set(d.filter(c => pool.includes(c)))].slice(0, S.deckSize) : [];
  return d.length ? d : recOf(f).slice();
}
function setFac(f) {
  if (f === LOBBY.fac || !facList().includes(f)) return;
  save(deckKey(LOBBY.fac), JSON.stringify(S.deck));
  LOBBY.fac = f; save('hmk_fac', f);
  S.deck = loadDeck(f);
  if (S.ready) send({ t: 'ready', v: false });
  uiSfx('click');
  renderDeck(); renderSettings();
  if (S.lobby) renderLobby(S.lobby);
}
function facTitle(f) {
  const i = facInfo(f);
  return i ? [i.name + ': ' + i.motto].concat((i.passives || []).map(p => '• ' + p)).join('\n') : '';
}
function facDetail(f) {
  const i = facInfo(f) || { desc: '', passives: [], cards: [], cmdv: {} }, type = LOBBY.type, kral = curMode() === 'kral';
  let h = `<p class="fdesc">${fmt(i.desc || '')}</p>`;
  if (i.passives && i.passives.length) h += '<ul class="fpass">' + i.passives.map(p => `<li>${fmt(p)}</li>`).join('') + '</ul>';
  if (f !== 'bez') {
    if (kral && i.perk) h += `<p class="fdesc"><b>Král, ${esc(i.perk.name)}:</b> ${fmt(i.perk.desc)}</p>`;
    if (!kral) for (const v of Object.values(i.cmdv || {})) h += `<p class="fdesc"><b>Stratég, ${esc(v.name)}:</b> ${fmt(v.desc)}</p>`;
    const cn = (i.cards || []).filter(c => S.defs && S.defs[c]).map(c => esc(S.defs[c].name));
    if (cn.length) h += `<p class="fdesc"><b>Frakční karty:</b> ${cn.join(', ')}. Najdeš je v balíčku nahoře.</p>`;
  }
  h += `<p class="fdesc fnote">${type === 'vycvik' ? 'Počítač hraje za Bez frakce (Lehká) nebo za náhodnou frakci (Střední, Těžká). Která to je, uvidíš až na začátku zápasu.'
    : 'Frakci soupeře uvidíš až na začátku zápasu.'}</p>`;
  return h;
}
function renderFacs() {
  const pane = $('#facPane'), list = facList();
  if (list.length < 2 || LOBBY.type === 'puzzle') return setHtmlIf(pane, '');
  const items = list.map(f => {
    const i = facInfo(f) || { name: 'Bez frakce', motto: 'Původní pravidla.' };
    return [f, `<img class="femb" src="${emblemImg(f, 2, 36)}" alt=""><span class="ftx"><b>${esc(i.name)}</b>`
      + (f === 'bez' ? '<em class="frec">Doporučeno na první hru</em>' : '') + `<span>${esc(i.motto)}</span></span>`, facTitle(f)];
  });
  setHtmlIf(pane, `<div class="fld" id="facBlock"><span class="lbl" id="facLbl">Frakce</span>`
    + `<div class="ftiles" id="facSeg" role="radiogroup" aria-labelledby="facLbl">${radioHtml(items, LOBBY.fac, 'ftile', false)}</div>`
    + `<div class="fdet" aria-live="polite">${facDetail(LOBBY.fac)}</div></div>`);
}
$('#facPane').addEventListener('click', ev => { const b = ev.target.closest('.ftile'); if (b) setFac(b.dataset.v); });
radioKeys($('#facPane'), setFac);
// emblem of the own faction in the own lobby slot (the opponent's faction stays hidden until the match starts)
const slotEmb = (i, me) => (me && LOBBY.fac !== 'bez' ? `<img class="emb femb-slot" src="${emblemImg(LOBBY.fac, i, 29)}" alt="">` : EMB[i]);
on('lobby', renderLobby);

on('m:lerr', m => lobbyErr(String(m.text || '')));
on('m:me', m => { S.meProf = m.prof || null; renderBadge(); });
function lobbyErr(text) {
  LOBBY.errAt = performance.now();
  $('#err').textContent = text;
  uiSfx('deny');
  clearTimeout(lobbyErr.t); lobbyErr.t = setTimeout(() => { if (performance.now() - LOBBY.errAt > 5900) $('#err').innerHTML = ''; }, 6000);
}
function renderBadge() {
  const b = $('#lvBadge'), p = S.meProf;
  b.classList.toggle('hidden', !p);
  if (p) { b.textContent = 'Úr. ' + p.lvl; b.title = p.ttl ? `${p.ttl}, ${p.xp} XP` : ''; }
}
function clearLobby() {
  $('#slots').innerHTML = ''; $('#note').classList.add('hidden'); $('#urls').innerHTML = '';
  S.ready = false; S.lobby = null; renderSettings(); updateReady();
}

function renderLobby(m) {
  S.lobby = m;
  const queued = queuedNow();
  if (!queued) S.side = m.you;
  if (performance.now() - LOBBY.errAt > 6000) $('#err').innerHTML = '';
  S.oldServer = !!m.ver && m.ver !== CLIENT_VER;
  if (S.oldServer) {
    $('#err').textContent = `Server běží ve verzi ${m.ver}, tahle stránka je ${CLIENT_VER}. `
      + 'Zavři okno serveru, spusť „Spustit server.bat“ znovu a obnov stránku (F5).';
    if (!S.defs) $('#deck').innerHTML = '<p class="err">Karty nepřišly, protože server je v jiné verzi. Restartuj ho.</p>';
  }
  const cfg = m.cfg || { type: 'souboj', mode: m.mode || 'kral', map: LOBBY.room.map };
  LOBBY.room = { type: cfg.type || 'souboj', mode: cfg.mode || 'kral', map: cfg.map || 'nahodna' };
  if (m.solo) LOBBY.soloRun = m.solo;
  if (isRoomType(LOBBY.type)) LOBBY.type = isRoomType(LOBBY.room.type) ? LOBBY.room.type : 'souboj';
  const kickIdle = m.kickIdle || 30;
  $('#slots').innerHTML = [0, 1].map(i => {
    const p = m.players[i];
    if (!p) return `<div class="slot empty">${EMB[i]}<span class="nm">Hráč ${i + 1}: volné místo, čeká se na soupeře…</span></div>`;
    const me = i === m.you;
    const ip = p.ip ? `${esc(p.ip)}${me ? ' · tohle okno' : ''}` : '';
    const lv = p.lv ? `<span class="lv" title="${esc(p.ttl || '')}">Úr. ${+p.lv}</span>` : '';
    const canKick = !me && !p.ready && !m.playing && (!queued || p.idle >= kickIdle);
    return `<div class="slot${me ? ' me' : ''}" data-seat="${i}">${slotEmb(i, me)}<span class="nm"><span class="pn">${esc(p.name)}${me ? ' (ty)' : ''}</span>${ip ? `<small>${ip}</small>` : ''}</span>${lv}`
      + `<span class="st ${p.ready ? 'ok' : ''}">${p.ready ? '✔ připraven' : 'nepřipraven'}</span>`
      + (canKick ? `<button class="kick" data-side="${i}" title="Uvolní místo obsazené třeba zapomenutým oknem">Vyhodit</button>` : '')
      + '</div>';
  }).join('');
  let note = '';
  if (queued) {
    note = `Obě místa jsou obsazená${m.playing ? ' a právě probíhá zápas' : ''}. Jsi ${m.pos}. ve frontě, připojíš se automaticky, jakmile se místo uvolní. Zatímco čekáš, zahraj si Výcvik.`;
    if (!m.playing) note += ` Nepřipraveného hráče, který ${kickIdle} s nic nedělá, můžeš vyhodit.`;
  } else if (m.queue && m.queue.length) {
    note = 'Ve frontě čeká: ' + m.queue.map(q => `<b>${esc(q.name)}</b> (${esc(q.ip)})${q.busy ? ' – hraje Výcvik' : ''}`).join(', ') + '. Nereaguje-li tvůj soupeř, můžeš ho vyhodit.';
  }
  $('#note').innerHTML = note;
  $('#note').classList.toggle('hidden', !note);
  const me = queued ? null : m.players[m.you];
  S.ready = !!(me && me.ready);
  const others = (m.urls || []).map(u => `<code>${esc(u)}</code>`).join(' nebo ');
  $('#urls').innerHTML = others ? `Soupeř na stejné síti otevře v prohlížeči: ${others}` : '';
  renderSettings();
  updateReady();
}

/* ---------------- game type, mode, map, difficulty ---------------- */
function fillMapSel() {
  const sel = $('#mapSel');
  const opts = (S.maps || []).map(mp => `<option value="${esc(mp.id)}">${esc(mp.name)}</option>`).join('') + '<option value="nahodna">Náhodná</option>';
  if (sel.dataset.h !== opts) { sel.dataset.h = opts; sel.innerHTML = opts; }
}
function mapInfo(id) { return (S.maps || []).find(mp => mp.id === id) || null; }
function updateMapPreview() {
  const id = curMap(), mp = mapInfo(id), cv = $('#mapPrev');
  if (id === 'nahodna' || !mp) drawMapPreview(cv, '?', 'ruiny');
  else drawMapPreview(cv, mp.ter || null, mp.theme, { relic: mp.relic });
  $('#mapDesc').textContent = id === 'nahodna' || !mp
    ? 'Server vybere mapu při startu zápasu. Její jméno uvidíš na úvodní obrazovce.' : mp.desc || '';
}
function radioHtml(items, cur, cls, disabled) {
  return items.map(([id, inner, title]) => `<button role="radio" class="${cls}${id === cur ? ' on' : ''}" data-v="${esc(id)}" aria-checked="${id === cur}" tabindex="${id === cur ? 0 : -1}"${disabled ? ' aria-disabled="true"' : ''}${title ? ` title="${esc(title)}"` : ''}>${inner}</button>`).join('');
}
function setHtmlIf(el, html) { if (el.dataset.h !== html) { el.dataset.h = html; el.innerHTML = html; } }
function renderSettings(force) {
  const type = LOBBY.type, room = isRoomType(type), puz = type === 'puzzle', lockRoom = room && !canCfg();
  const types = typeList();
  setHtmlIf($('#typeSeg'), radioHtml(types.map(t => [t.id, `${iconTag(TYPE_ICON[t.id] || 'kral', t.id === type ? PAL.giltHi : PAL.gilt, 'sm')}<span>${esc(t.name)}</span>`]), type, 'tseg', false));
  const ti = types.find(t => t.id === type);
  $('#typeDesc').textContent = ti ? ti.desc || '' : '';
  $('#ctlBlock').classList.toggle('hidden', puz);
  const hasMaps = !!(S.maps && S.maps.length);
  $('#mapBlock').classList.toggle('hidden', puz || !hasMaps);
  const mode = curMode();
  document.querySelectorAll('.mode').forEach(b => {
    const on_ = b.dataset.mode === mode;
    b.classList.toggle('on', on_); b.setAttribute('aria-checked', on_ ? 'true' : 'false'); b.tabIndex = on_ ? 0 : -1;
    b.disabled = lockRoom;
  });
  const sel = $('#mapSel');
  if (sel.value !== curMap()) sel.value = curMap();
  sel.disabled = lockRoom;
  updateMapPreview();
  // difficulty: Výcvik always has one, Přežití offers an optional AI opponent for "Hrát sám"
  const diffs = diffList();
  const showDiff = type === 'vycvik' || type === 'preziti';
  $('#diffBlock').classList.toggle('hidden', !showDiff);
  if (showDiff) {
    const pz = type === 'preziti', cur = pz ? (LOBBY.solo.aip || 'nikdo') : LOBBY.solo.ai;
    const items = diffs.map(([id, label, ai]) => [id, `<b>${esc(label)}</b><small>${esc(ai || '')}</small>`]);
    if (pz) items.unshift(['nikdo', '<b>Nikdo</b><small>jen zombie</small>']);
    $('#diffLbl').textContent = pz ? 'Soupeř při hře samotného hráče' : 'Obtížnost';
    setHtmlIf($('#diffSeg'), radioHtml(items, cur, 'dseg', false));
    const d = diffs.find(x => x[0] === cur);
    $('#diffDesc').textContent = pz
      ? (d ? `Hrát sám: soupeř ${d[2] || d[1]} hájí svůj trůn proti stejným vlnám. Tlačítko „Jsem připraven“ je pro hru dvou lidí.` : 'Hrát sám: bez soupeře. Tlačítko „Jsem připraven“ je pro hru dvou lidí.')
      : (d ? `Soupeř: ${d[2] || d[1]}. Počítač vidí jen to, co mu dovolí Mlha, a nemá žádné bonusy.` : '');
  }
  $('#slots').classList.toggle('hidden', !room);
  $('#readyBtn').classList.toggle('hidden', !room);
  $('#startBtn').classList.toggle('hidden', room);
  $('#soloBtn').classList.toggle('hidden', type !== 'preziti');
  renderFacs();
  if (LOBBY.pane !== type || force) { LOBBY.pane = type; const el = $('#typePane'); el.innerHTML = ''; emit('typePane', type, el); }
  updateReady();
}
function setType(t) {
  if (t === LOBBY.type) return;
  if (isRoomType(t) && LOBBY.room.type !== t) {
    if (!canCfg()) return lobbyErr('Typ souboje může měnit jen hráč na místě, když neprobíhá zápas.');
    send({ t: 'cfg', type: t });
  }
  uiSfx('click');
  LOBBY.type = t; saveCfg(); renderSettings();
}
function setMode(v) {
  if (v === curMode()) return;
  if (isRoomType(LOBBY.type)) { if (!canCfg()) return; send({ t: 'cfg', mode: v }); }
  else { LOBBY.solo.mode = v; saveCfg(); renderSettings(); }
  uiSfx('click');
}
function setMap(v) {
  if (v === curMap()) return;
  if (isRoomType(LOBBY.type)) { if (!canCfg()) { renderSettings(); return; } send({ t: 'cfg', map: v }); }
  else { LOBBY.solo.map = v; saveCfg(); renderSettings(); }
  uiSfx('click');
}
function setDiff(v) {
  if (LOBBY.type === 'preziti') LOBBY.solo.aip = v === 'nikdo' ? null : v; else LOBBY.solo.ai = v;
  saveCfg(); uiSfx('click'); renderSettings();
}
function radioKeys(box, pick) {
  box.addEventListener('keydown', ev => {
    const k = ev.key, d = k === 'ArrowRight' || k === 'ArrowDown' ? 1 : k === 'ArrowLeft' || k === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    const bs = [...box.querySelectorAll('[role=radio]:not([disabled])')], i = bs.indexOf(document.activeElement);
    if (i < 0) return;
    ev.preventDefault();
    const n = bs[(i + d + bs.length) % bs.length];
    n.focus(); pick(n.dataset.v);
    const again = box.querySelector(`[data-v="${n.dataset.v}"]`); if (again) again.focus();
  });
}
$('#typeSeg').addEventListener('click', ev => { const b = ev.target.closest('[data-v]'); if (b) setType(b.dataset.v); });
$('#diffSeg').addEventListener('click', ev => { const b = ev.target.closest('[data-v]'); if (b) setDiff(b.dataset.v); });
document.querySelectorAll('.mode').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
$('#mapSel').addEventListener('change', () => setMap($('#mapSel').value));
radioKeys($('#typeSeg'), setType); radioKeys($('#diffSeg'), setDiff);
radioKeys($('.modes'), v => setMode(v));
document.querySelectorAll('.modes .mode').forEach(b => { b.dataset.v = b.dataset.mode; });

/* ---------------- ready, solo start ---------------- */
function updateReady() {
  const type = LOBBY.type, room = isRoomType(type), full = S.deck.length === S.deckSize;
  const rb = $('#readyBtn'), sb = $('#startBtn'), ob = $('#soloBtn');
  rb.disabled = queuedNow() || S.oldServer || (!full && !S.ready);
  rb.textContent = S.oldServer ? 'Nejdřív restartuj server' : S.ready ? '✔ Připraven (zrušit)' : full ? 'Jsem připraven' : `Doplň balíček (${S.deck.length}/${S.deckSize})`;
  rb.classList.toggle('on', S.ready);
  const full_ = full || type === 'puzzle';                  // a puzzle brings its own cards
  const full2 = LOBBY.soloRun[0] >= LOBBY.soloRun[1];
  const noPuz = type === 'puzzle' && !LOBBY.puzzle;
  sb.disabled = !S.ws || S.oldServer || !full_ || noPuz;
  sb.textContent = S.oldServer ? 'Nejdřív restartuj server' : noPuz ? 'Vyber puzzle' : !full_ ? `Doplň balíček (${S.deck.length}/${S.deckSize})` : 'Začít';
  sb.title = full2 && !room ? `Server právě hostí ${LOBBY.soloRun[0]} cvičné hry, nová se nemusí spustit.` : '';
  ob.disabled = !S.ws || S.oldServer || !full;
  ob.textContent = 'Hrát sám';
}
// Start a solo session. `o` overrides the defaults taken from the lobby (type, mode, map, ai, puzzle, ...).
function soloStart(o) {
  o = o || {};
  const type = o.type || (LOBBY.type === 'souboj' ? 'vycvik' : LOBBY.type);
  const m = { t: 'solo', type, mode: curMode(), map: curMap(), ai: null, fac: LOBBY.fac || 'bez', deck: S.deck, puzzle: null };
  if (type === 'puzzle' || type === 'vyuka') m.fac = 'bez';      // the server forces it too; a puzzle or the tutorial brings its own kit
  if (type === 'vycvik') m.ai = LOBBY.solo.ai;
  else if (type === 'preziti') m.ai = LOBBY.solo.aip;
  else if (type === 'puzzle') { m.puzzle = LOBBY.puzzle; m.map = null; }
  else if (type === 'vyuka') m.map = 'predmesti';
  Object.assign(m, o);
  m.t = 'solo';
  send(m);
}
$('#readyBtn').onclick = () => { uiSfx('click'); send({ t: 'ready', v: !S.ready, deck: S.deck, fac: LOBBY.fac || 'bez' }); };
$('#startBtn').onclick = () => { uiSfx('click'); soloStart(); };
$('#soloBtn').onclick = () => { uiSfx('click'); soloStart({ type: 'preziti' }); };
$('#tutBtn').onclick = () => { uiSfx('click'); soloStart({ type: 'vyuka', mode: LOBBY.solo.mode, map: 'predmesti', ai: null }); };
$('#slots').addEventListener('click', ev => {
  const b = ev.target.closest('.kick');
  if (b) send({ t: 'kick', side: +b.dataset.side });
});
$('#helpBtn').onclick = () => { uiSfx('click'); toggleHelp(true); };

/* ---------------- deck ---------------- */
function cardCostHtml(k) {
  const d = S.defs[k];
  const fc = (S.inGame && S.costs) || (S.facCosts && S.facCosts[LOBBY.fac]), c = (fc && fc[k]) || d.cost || [0, 0];     // faction price (base, without escalation)
  const p = [];
  if (c[0]) p.push(`<span class="e">${c[0]} ${SVG.e}</span>`);
  if (c[1]) p.push(`<span class="s">${c[1]} ${SVG.s}</span>`);
  if (d.cd) p.push(`<span>obnova ${d.cd} s</span>`);
  const db = S.inGame ? dobaOf(k) : dobaOf(k, LOBBY.fac);

  if (db) p.push(`<span class="doba">Doba ${roman(db)}</span>`);
  return p.join(' · ');
}
function renderDeck() {
  if (!S.defs) return;
  // "Frakční karty" first (the faction's own cards), then the shared cards by category
  const own = (facInfo(LOBBY.fac) && facInfo(LOBBY.fac).cards || []).filter(k => S.defs[k] && poolOf(LOBBY.fac).includes(k));
  const shared = poolOf(LOBBY.fac).filter(k => S.defs[k] && !own.includes(k));
  const groups = [['f', 'Frakční karty · ' + facName(LOBBY.fac)], ['b', 'Stavby'], ['u', 'Jednotky · šachové pohyby'], ['a', 'Schopnosti']];
  $('#deck').innerHTML = groups.map(([cat, title]) => {
    const ks = cat === 'f' ? own : shared.filter(k => S.defs[k].cat === cat);
    if (!ks.length) return '';
    return `<h4>${esc(title)}</h4><div class="cards">` + ks.map(k => {
      const d = S.defs[k], col = CAT_COL[d.cat];
      return `<button class="dc ${cat === 'f' ? 'fc ' : ''}${S.deck.includes(k) ? 'on' : ''}" data-card="${k}">${iconTag(k, col)}<span class="dt"><b>${esc(d.name)}</b>`
        + `<span class="c">${cardCostHtml(k)}</span><span class="d">${fmt(d.desc)}</span></span></button>`;
    }).join('') + '</div>';
  }).join('');
  const cnt = $('#deckCount'), n = S.deck.length;
  cnt.innerHTML = Array.from({ length: S.deckSize }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('') + `<span>${n}/${S.deckSize}</span>`;
  cnt.classList.toggle('full', n === S.deckSize);
  updateReady();
}
function deckChanged() {
  save(deckKey(LOBBY.fac), JSON.stringify(S.deck));
  if (S.ready) send({ t: 'ready', v: false });
  renderDeck();
}
$('#deck').addEventListener('click', ev => {
  const b = ev.target.closest('.dc');
  if (!b) return;
  const k = b.dataset.card;
  if (S.deck.includes(k)) S.deck = S.deck.filter(c => c !== k);
  else if (S.deck.length < S.deckSize) S.deck.push(k);
  else { flashCls($('#deckCount'), 'bump', 320); uiSfx('deny'); return; }
  uiSfx('tick');
  deckChanged();
});
$('#deckRec').onclick = () => { uiSfx('click'); S.deck = recOf(LOBBY.fac).slice(); deckChanged(); };
$('#deckClear').onclick = () => { uiSfx('click'); S.deck = []; deckChanged(); };
let tipIdx = Math.floor(Math.random() * TIPS.length);
// the shared tips plus the 2 tips of the chosen faction
function rotateTip() { const all = TIPS.concat(FAC_TIPS[LOBBY.fac] || []); $('#tipday').innerHTML = '<span class="rada">Rada</span> · ' + iconize(all[tipIdx % all.length]); tipIdx++; }

rotateTip(); setInterval(rotateTip, 9000);

/* ---------------- right folio tabs ---------------- */
// lobbyTab(id, label, render): registers a tab of the right folio. The panel #tab_<id> is created when missing, and
// render(panelEl) runs every time the tab is shown. The last tab is remembered in localStorage hmk_tab.
const TABS = [];
function lobbyTab(id, label, render) {
  const t = TABS.find(x => x.id === id);
  if (t) { t.label = label; if (render) t.render = render; } else TABS.push({ id, label, render: render || null });
  if (!$('#tab_' + id)) {
    const el = document.createElement('div');
    el.id = 'tab_' + id; el.className = 'tabpane hidden'; el.setAttribute('role', 'tabpanel'); el.setAttribute('aria-labelledby', 'tabbtn_' + id);
    $('#folioPane').appendChild(el);
  }
  buildTabs();
}
function tabCur() { return TABS.some(t => t.id === LOBBY.tab) ? LOBBY.tab : TABS.length ? TABS[0].id : ''; }
function buildTabs() {
  const cur = tabCur();
  $('#folioTabs').innerHTML = TABS.map(t => `<button role="tab" class="ftab${t.id === cur ? ' on' : ''}" id="tabbtn_${t.id}" data-tab="${t.id}" aria-selected="${t.id === cur}" aria-controls="tab_${t.id}" tabindex="${t.id === cur ? 0 : -1}">${esc(t.label)}</button>`).join('');
  for (const t of TABS) { const el = $('#tab_' + t.id); if (el) el.classList.toggle('hidden', t.id !== cur); }
  const t = TABS.find(x => x.id === cur);
  if (t && t.render) { try { t.render($('#tab_' + t.id)); } catch (e) { console.error('tab', t.id, e); } }
}
function selectTab(id) {
  if (!TABS.some(t => t.id === id)) return;
  LOBBY.tab = id; save('hmk_tab', id);
  buildTabs();
  const b = $('#tabbtn_' + id); if (b) b.focus();
}
$('#folioTabs').addEventListener('click', ev => { const b = ev.target.closest('[data-tab]'); if (b) { uiSfx('click'); selectTab(b.dataset.tab); } });
$('#folioTabs').addEventListener('keydown', ev => {
  const d = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0;
  if (!d || TABS.length < 2) return;
  ev.preventDefault();
  const i = TABS.findIndex(t => t.id === tabCur());
  selectTab(TABS[(i + d + TABS.length) % TABS.length].id);
});
lobbyTab('deck', 'Balíček');

/* ---------------- lobby show and backdrop ---------------- */
function showLobby() {
  $('#game').classList.add('hidden');
  $('#resOv').classList.add('hidden'); S.resOpen = false;
  $('#lobby').classList.remove('hidden');
  annClear();
  if (typeof audioStop === 'function') audioStop();
  drawLobbyBg();
  renderSettings();
}

// Lobby backdrop: night sky with a moon, a ruined skyline, and the crypt's ashlar wall in front.
function drawLobbyBg() {
  const c = $('#lobbyBg');
  if (!c || $('#lobby').classList.contains('hidden')) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2), W = innerWidth, H = innerHeight;
  c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
  const g = c.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const sky = g.createLinearGradient(0, 0, 0, H * 0.5);
  sky.addColorStop(0, '#060509'); sky.addColorStop(1, '#17121a');
  g.fillStyle = sky; g.fillRect(0, 0, W, H);
  for (let i = 0; i < 110; i++) { g.fillStyle = `rgba(226,219,204,${0.12 + hash(i, 3, 7) * 0.4})`; g.fillRect(hash(i, 1, 7) * W, hash(i, 2, 7) * H * 0.42, 1.3, 1.3); }
  const mr = Math.max(24, Math.min(W, H) * 0.05), mx = W * 0.8, my = H * 0.14;
  let gr = g.createRadialGradient(mx, my, mr * 0.8, mx, my, mr * 4.5);
  gr.addColorStop(0, 'rgba(185,195,214,.18)'); gr.addColorStop(1, 'rgba(185,195,214,0)');
  g.fillStyle = gr; g.fillRect(mx - mr * 5, my - mr * 5, mr * 10, mr * 10);
  gr = g.createRadialGradient(mx - mr * 0.3, my - mr * 0.3, mr * 0.1, mx, my, mr);
  gr.addColorStop(0, '#f1f3f7'); gr.addColorStop(0.7, '#b9c3d6'); gr.addColorStop(1, '#8a94a8');
  g.beginPath(); g.arc(mx, my, mr, 0, TAU); g.fillStyle = gr; g.fill();
  g.fillStyle = 'rgba(70,80,100,.18)';
  for (const [dx, dy, r] of [[-0.3, -0.2, 0.22], [0.25, 0.15, 0.16], [-0.05, 0.4, 0.12], [0.35, -0.35, 0.09]]) { g.beginPath(); g.arc(mx + dx * mr, my + dy * mr, r * mr, 0, TAU); g.fill(); }
  // ruined skyline: towers with broken tops and a few candle-lit windows
  const base = H * 0.44;
  g.fillStyle = '#0c0a0d';
  g.beginPath(); g.moveTo(0, H);
  let x = 0, i = 0;
  const lit = [];
  while (x < W) {
    const w = 34 + hash(i, 5, 3) * 70, h = 40 + hash(i, 6, 3) * H * 0.2, top = base - h, k = hash(i, 7, 3);
    g.lineTo(x, base - h * 0.35);
    g.lineTo(x, top);
    if (k < 0.3) { g.lineTo(x + w * 0.5, top - w * 0.9); g.lineTo(x + w, top); }
    else if (k < 0.6) { g.lineTo(x + w * 0.3, top + 8); g.lineTo(x + w * 0.45, top - 6); g.lineTo(x + w * 0.7, top + 12); g.lineTo(x + w, top + 4); }
    else { for (let j = 0; j < 4; j++) { const cx = x + (w / 4) * j; g.lineTo(cx, top - 7); g.lineTo(cx + w / 8, top - 7); g.lineTo(cx + w / 8, top); g.lineTo(cx + w / 4, top); } }
    g.lineTo(x + w, base - h * 0.3);
    if (hash(i, 8, 3) < 0.55) lit.push([x + w * (0.3 + hash(i, 9, 3) * 0.4), top + 14 + hash(i, 10, 3) * h * 0.4]);
    x += w + hash(i, 11, 3) * 22; i++;
  }
  g.lineTo(W, H); g.closePath(); g.fill();
  for (const [lx, ly] of lit) { g.fillStyle = 'rgba(255,184,90,.55)'; g.fillRect(lx, ly, 3, 5); }
  // ashlar wall with a broken upper edge
  const bw = 112, bh = 56, top = H * 0.5;
  g.fillStyle = '#0b0907'; g.fillRect(0, top + bh * 0.5, W, H);
  for (let r = 0; r * bh + top < H; r++) {
    const off = (r % 2) * bw / 2;
    for (let cx = -off; cx < W; cx += bw) {
      const col = Math.round((cx + off) / bw);
      if (r === 0 && hash(col, r, 21) < 0.45) continue;
      if (r === 1 && hash(col, r, 21) < 0.12) continue;
      g.fillStyle = mix('#1d1814', hash(col, r, 22) < 0.5 ? '#2a231d' : '#141110', hash(col, r, 23) * 0.6);
      g.fillRect(cx + 2, top + r * bh + 2, bw - 4, bh - 4);
      g.fillStyle = 'rgba(255,230,190,.035)'; g.fillRect(cx + 2, top + r * bh + 2, bw - 4, 3);
    }
  }
  gr = g.createLinearGradient(0, top, 0, H);
  gr.addColorStop(0, 'rgba(14,11,9,0)'); gr.addColorStop(1, 'rgba(14,11,9,.75)');
  g.fillStyle = gr; g.fillRect(0, top, W, H - top);
}
let lobbyBgRaf = 0;
window.addEventListener('resize', () => { cancelAnimationFrame(lobbyBgRaf); lobbyBgRaf = requestAnimationFrame(drawLobbyBg); });
