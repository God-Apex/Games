'use strict';
/* Modes UI (M3-E2, SPEC 3.5 and 6): the puzzle grid and the Přežití records in the lobby type pane, the pinned HUD box of Přežití and
   puzzles (#modeBox in the side panel), the Výuka card (#tutCard) with its hints, the pause menu (#pauseOv), the first-visit modal
   (#welcomeOv) and the result block of the end overlay. Everything arrives through the event bus of base.js; the mount points
   are in index.html. Progress is kept in localStorage (hmk_puzzle, hmk_surv) next to the profile of the server, the UI shows the better one. */
(() => {
  const MD = {
    pane: $('#typePane'), picked: false,       // the player chose a puzzle by hand (no more automatic "next puzzle")
    type: '', puz: null, sv: null, k: 0,       // running game: type, start.puzzle, start.surv, last announced wave
    tsteps: [], tuStep: 0, tuUi: '', quitT: 0, tipsHeld: false, before: null,
    welcomed: false,
  };
  const LS_PUZ = 'hmk_puzzle', LS_SURV = 'hmk_surv', LS_SEEN = 'hmk_seen';

  /* ---------------- small helpers ---------------- */
  const vln = n => (n === 1 ? 'vlna' : n >= 2 && n <= 4 ? 'vlny' : 'vln');
  const fmtT = t => { t = Math.max(0, Math.round(+t || 0)); return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0'); };
  const clockT = t => { t = Math.max(0, Math.ceil(+t || 0)); return String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(t % 60).padStart(2, '0'); };
  const sec1 = t => String(Math.round((+t || 0) * 10) / 10).replace('.', ',');
  const starStr = n => '★'.repeat(n) + '☆'.repeat(3 - n);
  const starLbl = n => (n <= 0 ? 'bez hvězdy' : n === 1 ? '1 hvězda ze 3' : n + ' hvězdy ze 3');
  const starsHtml = n => `<span class="stars" role="img" aria-label="${starLbl(n)}">${starStr(n)}</span>`;
  const readObj = key => { try { const o = JSON.parse(load(key, 'null')); return o && typeof o === 'object' ? o : null; } catch (e) { return null; } };
  const modeName = m => (m === 'strateg' ? 'Stratég' : 'Král');
  const mapName = id => { const mp = (S.maps || []).find(x => x.id === id); return mp ? mp.name : id; };
  const puzNum = (p, i) => String(p.id).replace(/^\D+/, '') || String(i + 1).padStart(2, '0');
  const SAFE_ID = /^[a-z0-9_]{1,16}$/;

  /* ---------------- progress: localStorage next to the profile (the better one wins) ---------------- */
  const locPuz = () => { const o = readObj(LS_PUZ); return o && o.v === 1 && o.p && typeof o.p === 'object' ? o.p : {}; };
  const betterPuz = (a, b) => a.s > b.s || (a.s === b.s && a.s > 0 && a.t > 0 && (b.t <= 0 || a.t < b.t));
  function puzBest(id) {
    let b = { s: 0, t: 0 };
    const l = locPuz()[id];
    if (l && typeof l === 'object' && l.s > 0) b = { s: Math.min(3, l.s | 0), t: +l.t || 0 };
    const p = S.meProf && S.meProf.puz && S.meProf.puz[id];
    if (Array.isArray(p) && p[0] > 0) { const c = { s: Math.min(3, p[0] | 0), t: +p[1] || 0 }; if (betterPuz(c, b)) b = c; }
    return b;
  }
  function savePuz(id, stars, t) {
    if (!SAFE_ID.test(id)) return;
    const p = locPuz(), old = p[id], cur = { s: stars, t: Math.round(t * 10) / 10 };
    if (!old || typeof old !== 'object' || betterPuz(cur, { s: old.s | 0, t: +old.t || 0 })) p[id] = cur;
    save(LS_PUZ, JSON.stringify({ v: 1, p }));
  }
  const locSurv = () => readObj(LS_SURV) || {};
  const betterSurv = (a, b) => a.w > b.w || (a.w === b.w && a.t > b.t);
  const survKey = (map, mode) => map + '|' + mode;
  function survBest(map, mode) {
    const key = survKey(map, mode);
    let b = { w: 0, t: 0 };
    const l = locSurv()[key];
    if (l && typeof l === 'object' && l.w > 0) b = { w: l.w | 0, t: +l.t || 0 };
    const p = S.meProf && S.meProf.surv && S.meProf.surv[key];
    if (Array.isArray(p) && p[0] > 0) { const c = { w: p[0] | 0, t: +p[1] || 0 }; if (betterSurv(c, b)) b = c; }
    return b;
  }
  function saveSurv(map, mode, w, t) {
    if (!SAFE_ID.test(map) || (mode !== 'kral' && mode !== 'strateg') || w < 1) return;
    const all = locSurv(), key = survKey(map, mode), old = all[key];
    const cur = { w, t: Math.round(t) };
    if (!old || typeof old !== 'object' || betterSurv(cur, { w: old.w | 0, t: +old.t || 0 })) all[key] = cur;
    save(LS_SURV, JSON.stringify(all));
  }
  const survText = b => (b.w > 0 ? `${b.w} ${vln(b.w)} (${fmtT(b.t)})` : 'zatím žádný');

  // puzzles p01-p03 are always open, p(n) opens when p(n-1) has at least one star (enforced here only)
  const puzList = () => S.puzzles || [];
  const puzOpen = i => i < 3 || (puzList()[i - 1] ? puzBest(puzList()[i - 1].id).s >= 1 : true);
  function nextPuzzle() {
    const l = puzList(), open = l.filter((p, i) => puzOpen(i));
    const p = open.find(x => puzBest(x.id).s === 0) || open.find(x => puzBest(x.id).s < 3) || open[0] || l[0];
    return p ? p.id : null;
  }
  function autoSel() { if (!MD.picked && puzList().length) LOBBY.puzzle = nextPuzzle(); }

  /* ---------------- lobby: puzzle grid and Přežití records in the type pane ---------------- */
  function puzDetail(p, i) {
    const b = puzBest(p.id), mp = p.map ? mapName(p.map) : '';
    const st = (p.stars_text || []).map(t => `<li>${esc(t)}</li>`).join('');
    return `<div class="puzdet" aria-live="polite"><p class="fdesc"><b>Puzzle ${esc(puzNum(p, i))} · ${esc(p.name)}</b> · ${modeName(p.mode)}`
      + `${mp ? ' · mapa ' + esc(mp) : ''}${p.time ? ' · limit ' + p.time + ' s' : ''}</p>`
      + (p.desc ? `<p class="fdesc">${esc(p.desc)}</p>` : '')
      + (p.goal_text ? `<p class="fdesc"><b>Cíl:</b> ${esc(p.goal_text)}</p>` : '')
      + (st ? `<ul class="puzstars" aria-label="Hvězdy">${st}</ul>` : '')
      + `<p class="fdesc">Nejlepší výsledek: ${b.s ? starsHtml(b.s) + (b.t ? ' za ' + sec1(b.t) + ' s' : '') : 'zatím žádný'}</p></div>`;
  }
  function renderPuzzlePane() {
    const el = MD.pane, list = puzList();
    if (!el || LOBBY.type !== 'puzzle') return;
    if (!list.length) { el.innerHTML = '<p class="fdesc">Server zatím neposlal žádná puzzle.</p>'; return; }
    let si = list.findIndex(p => p.id === LOBBY.puzzle);
    if (si < 0 || !puzOpen(si)) { LOBBY.puzzle = nextPuzzle(); si = list.findIndex(p => p.id === LOBBY.puzzle); }
    const total = list.reduce((a, p) => a + puzBest(p.id).s, 0);
    const cards = list.map((p, i) => {
      const open = puzOpen(i), on = i === si;
      const meta = open ? `${modeName(p.mode)} · ${starsHtml(puzBest(p.id).s)}`
        : `Zamčeno: nejdřív puzzle ${esc(puzNum(list[i - 1], i - 1))}`;
      return `<button type="button" role="radio" class="pzc${on ? ' on' : ''}${open ? '' : ' lock'}" data-v="${esc(p.id)}" aria-checked="${on}" tabindex="${on ? 0 : -1}"${open ? '' : ' disabled'}>`
        + `<span class="pn">${esc(puzNum(p, i))}</span><span class="pt"><b>${esc(p.name)}</b><span class="pm">${meta}</span></span></button>`;
    }).join('');
    el.innerHTML = `<div class="fld"><div class="puzhead"><span class="lbl" id="puzLbl">Puzzle</span><span class="puzsum">Hvězdy ${total} / ${list.length * 3}</span></div>`
      + `<div class="puzgrid" id="puzGrid" role="radiogroup" aria-labelledby="puzLbl">${cards}</div>${puzDetail(list[si], si)}</div>`;
  }
  function pickPuzzle(id) {
    const i = puzList().findIndex(p => p.id === id);
    if (i < 0 || !puzOpen(i) || id === LOBBY.puzzle) return;
    LOBBY.puzzle = id; MD.picked = true;
    uiSfx('click');
    renderPuzzlePane(); updateReady();
  }
  function renderSurvPane() {
    const el = MD.pane;
    if (!el || LOBBY.type !== 'preziti') return;
    const rows = (S.maps || []).map(mp => [mp.name, survBest(mp.id, 'kral'), survBest(mp.id, 'strateg')]).filter(r => r[1].w || r[2].w);
    const cell = b => (b.w ? `${b.w} ${vln(b.w)} · ${fmtT(b.t)}` : '–');
    el.innerHTML = '<div class="fld"><span class="lbl">Rekordy v Přežití</span>' + (rows.length
      ? '<table class="rectab"><thead><tr><th scope="col">Mapa</th><th scope="col">Král</th><th scope="col">Stratég</th></tr></thead><tbody>'
        + rows.map(r => `<tr><th scope="row">${esc(r[0])}</th><td>${cell(r[1])}</td><td>${cell(r[2])}</td></tr>`).join('') + '</tbody></table>'
      : '<p class="fdesc">Zatím žádný rekord. Vydrž co nejvíc vln a výsledek se zapíše sem.</p>') + '</div>';
  }
  function refreshPane() { if (LOBBY.type === 'puzzle') renderPuzzlePane(); else if (LOBBY.type === 'preziti') renderSurvPane(); }

  on('typePane', (type, el) => {
    MD.pane = el;
    if (type === 'puzzle') renderPuzzlePane(); else if (type === 'preziti') renderSurvPane();
  });
  MD.pane.addEventListener('click', ev => { const b = ev.target.closest('.pzc'); if (b && !b.disabled) pickPuzzle(b.dataset.v); });
  radioKeys(MD.pane, pickPuzzle);
  on('defs', () => { autoSel(); refreshPane(); updateReady(); });
  on('m:me', () => { autoSel(); refreshPane(); updateReady(); welcomeCheck(); });

  /* ---------------- pinned HUD box in the side panel (Přežití and puzzles) ---------------- */
  function boxEl() {
    let b = $('#modeBox');
    if (!b) {
      b = document.createElement('div'); b.id = 'modeBox'; b.className = 'mbox';
      $('#side').insertBefore(b, $('#toasts'));
    }
    return b;
  }
  function setBox(html) { const b = boxEl(); if (b._h !== html) { b._h = html; b.innerHTML = html; } }
  const row = (a, b) => `<span>${a}</span><span>${b}</span>`;
  const mapId = () => (S.map && S.map.id) || '';

  function survUpdate(m) {
    const [k, secs, zm, zf] = m.sv, two = !!(MD.sv && MD.sv.players === 2), best = survBest(mapId(), S.mode);
    const ph = $('#phase');
    ph.textContent = k > 0 ? `Vlna ${k} · další za ${secs} s` : `První vlna za ${secs} s`;
    ph.classList.toggle('soon', secs > 0 && secs <= 3);
    if (k > MD.k) {
      MD.k = k;
      const boss = k % 10 === 0;
      announce('Vlna ' + k, boss ? 'Přichází Alfa. Drž se.' : '', boss ? 2 : 3, boss ? 'bad' : 'info');
    }
    setBox(`<h4>Přežití${two ? ' · dva hráči' : ''}</h4><div class="stats">`
      + row('Vlna', k > 0 ? k : '–') + row('Další vlna za', secs + ' s') + row(two ? 'Zombie na tobě' : 'Zombie živých', zm)
      + (two ? row('Zombie u soupeře', zf) : '') + row('Rekord', survText(best)) + '</div>'
      + (best.w > 0 && k - 1 > best.w ? '<p class="mnote">Překonáváš svůj rekord.</p>' : '')
      + `<p class="mnote">Mapa ${esc(mapName(mapId()))}, ${modeName(S.mode)}.</p>`);
  }

  const GOAL = {
    survive: p => ['Vydrženo', `${p[1]} / ${p[2]} s`], destroy: p => ['Zničeno cílů', `${p[1]} / ${p[2]}`],
    mate: p => ['Šach trvá', `${sec1(p[1])} / ${sec1(p[2])} s`], collect: p => ['Sebráno beden', `${p[1]} / ${p[2]}`],
    relic: p => ['Relikvii držíš', `${p[1]} / ${p[2]} s`], promote: p => ['Proměna v Dámu', p[1] ? 'ano' : 'ne'],
  };
  function puzUpdate(m) {
    const pz = m.pz, p = MD.puz;
    if (!p) return;
    const pl = puzList(), i = pl.findIndex(x => x.id === p.id), num = puzNum(p, i < 0 ? 0 : i);
    const ck = $('#clock'), ph = $('#phase');
    ck.textContent = clockT(pz[0]);
    ck.classList.toggle('pzlow', pz[0] <= 10);
    $('#clockBox').title = 'Zbývající čas puzzle';
    ph.textContent = `Puzzle ${num} · zbývá čas`;
    ph.classList.toggle('soon', pz[0] <= 10);
    const g = GOAL[p.goal] ? GOAL[p.goal](pz) : null, best = puzBest(p.id);
    setBox(`<h4>Puzzle ${esc(num)} · ${esc(p.name)}</h4><p class="mgoal"><b>Cíl:</b> ${esc(p.goal_text || '')}</p><div class="stats">`
      + row('Zbývá', fmtT(pz[0])) + (g ? row(g[0], g[1]) : '') + '</div>'
      + '<ul class="mstars" aria-label="Hvězdy">' + (p.stars_text || []).map(t => `<li>${esc(t)}</li>`).join('') + '</ul>'
      + `<p class="mnote">Nejlepší: ${best.s ? starsHtml(best.s) : 'zatím žádný'}</p>`);
  }

  /* ---------------- Výuka: #tutCard, the cell hint and the pulse of the hinted control ---------------- */
  const KEYRUN = '((?:[A-Z0-9](?![A-Za-zÀ-ž])\\s*)+)';
  const KEYRE = [new RegExp('(kláves(?:a|ami|u)\\s+|[Zz]máčkni\\s+|[Ss]tiskni\\s+|liště:\\s+)' + KEYRUN, 'g')];
  // step text from the server -> HTML with <kbd> keys ("klávesa 1", "W A S D", "mezerník", "Zmáčkni U")
  function tutHtml(text) {
    let h = esc(text);
    for (const re of KEYRE) {
      h = h.replace(re, (all, kw, keys) => kw + keys.trim().split(/\s+/).map(k => `<kbd>${k}</kbd>`).join(' ') + (keys.match(/\s*$/)[0] || ''));
    }
    return h.replace(/\bmezerník\b/gi, w => `<kbd>${w}</kbd>`);
  }
  function tutBuild() {
    const c = $('#tutCard');
    c.className = 'folio orn hidden';
    c.innerHTML = '<div class="tuth"><span class="tuks"></span><span class="tuok" aria-hidden="true">✔</span></div><p class="tutx"></p>'
      + '<div class="tutb"><button type="button" class="btn small dark" data-a="skip">Přeskočit krok</button>'
      + '<button type="button" class="btn small dark" data-a="quit">Ukončit výuku</button></div>';
    MD.tuStep = 0; MD.tuUi = '';
  }
  $('#tutCard').addEventListener('click', ev => {
    const b = ev.target.closest('button[data-a]');
    if (!b || !S.inGame || S.ending) return;
    if (b.dataset.a === 'skip') { uiSfx('click'); send({ t: 'tut', skip: 1 }); return; }
    const now = performance.now();
    if (now - MD.quitT < 3000) { MD.quitT = 0; send({ t: 'quit' }); return; }
    MD.quitT = now; b.textContent = 'Opravdu ukončit?'; uiSfx('click');
    setTimeout(() => { if (MD.quitT === now) { MD.quitT = 0; b.textContent = 'Ukončit výuku'; } }, 3000);
  });
  function tutCell(hx, hy) {
    let c = $('#tutCell');
    if (hx < 0 || hy < 0 || typeof px !== 'function') { if (c) c.classList.add('hidden'); return; }
    if (!c) { c = document.createElement('i'); c.id = 'tutCell'; c.setAttribute('aria-hidden', 'true'); $('#marks').appendChild(c); }
    c.classList.remove('hidden');
    c.style.width = c.style.height = CS + 'px';
    c.style.left = Math.round(px(hx) - CS / 2) + 'px'; c.style.top = Math.round(py(hy) - CS / 2) + 'px';
  }
  function tutUi(ui) {
    if (ui === MD.tuUi) return;
    MD.tuUi = ui;
    document.querySelectorAll('.tut').forEach(e => e.classList.remove('tut'));
    const [kind, v] = (ui || '').split(':');
    let el = null;
    if (kind === 'slot') el = $(`#bar .bb[data-slot="${(+v || 1) - 1}"]`);
    else if (kind === 'cmd') el = $(`#bar .bb[data-cmd="${v}"]`);
    else if (kind === 'key' && v === 'V') el = $('#resBtn');
    if (el) el.classList.add('tut');
    if (ui) document.body.dataset.tut = ui; else delete document.body.dataset.tut;
    $('#tutCard').classList.toggle('hot', !!ui);
  }
  function tutUpdate(m) {
    const [step, total, hx, hy, ui] = m.tu, c = $('#tutCard');
    if (step !== MD.tuStep) {
      const first = MD.tuStep === 0, st = MD.tsteps[step - 1];
      MD.tuStep = step;
      c.querySelector('.tuks').innerHTML = `Krok <b>${step}</b>/${total}`;
      c.querySelector('.tutx').innerHTML = st ? tutHtml(st.text) : '';
      c.querySelector('[data-a="skip"]').classList.toggle('hidden', step >= total);
      c.classList.remove('hidden');
      if (!first) {
        uiSfx('select');
        const ok = c.querySelector('.tuok');
        if (ok && !S.opt.calm) flashCls(ok, 'go', 900);
      }
      MD.tuUi = '?';                 // force tutUi to re-apply
    }
    tutCell(hx, hy);
    tutUi(ui || '');
  }

  // the tips toasts and the first-steps checklist would talk over the tutorial: switch them off in memory while it runs (the saved choice stays)
  function holdTips(on_) {
    if (on_) { if (!MD.tipsHeld) { MD.tipsHeld = true; S.tips = false; } }
    else if (MD.tipsHeld) { MD.tipsHeld = false; S.tips = load('hmk_tips', '1') === '1'; }
  }

  /* ---------------- pause menu ---------------- */
  const pauseOpen = () => !$('#pauseOv').classList.contains('hidden');
  const PAUSE_NOTE = {
    vycvik: 'Ukončení po první minutě se počítá jako prohra.', preziti: 'Dosažená vlna se započítá do rekordu.',
    puzzle: 'Puzzle se do statistik nezapisuje, zkusit ho můžeš znovu.', vyuka: 'Výuku můžeš kdykoli začít znovu z lobby.',
  };
  function openPause() {
    if (!S.inGame || !S.solo || S.ending || pauseOpen()) return;
    if (typeof releaseKeys === 'function') releaseKeys();
    send({ t: 'pause', v: true });
    S.paused = true;
    const ov = $('#pauseOv');
    ov.innerHTML = '<div class="card folio orn pausec"><h2>Pozastaveno</h2><p class="sub">Hra stojí, nic se neděje.</p>'
      + '<div class="pbtns"><button type="button" class="btn big" data-p="go">Pokračovat</button>'
      + '<button type="button" class="btn" data-p="re">Začít znovu</button><button type="button" class="btn dark" data-p="quit">Ukončit</button></div>'
      + `<p class="muted">Esc také pokračuje. ${PAUSE_NOTE[S.type] || ''}</p></div>`;
    ov.classList.remove('hidden');
    uiSfx('click');
    ov.querySelector('[data-p="go"]').focus();
  }
  function closePause(silent) {
    const was = pauseOpen();
    $('#pauseOv').classList.add('hidden');
    S.paused = false;
    if (was && !silent) send({ t: 'pause', v: false });
  }
  $('#pauseOv').addEventListener('click', ev => {
    const b = ev.target.closest('button[data-p]');
    if (!b) return;
    uiSfx('click');
    if (b.dataset.p === 'go') closePause();
    else if (b.dataset.p === 're') { closePause(true); send({ t: 'restart' }); }
    else { closePause(true); send({ t: 'quit' }); }
  });
  function trapTab(ev, root) {
    if (ev.key !== 'Tab') return;
    const f = [...root.querySelectorAll('button:not([disabled])')];
    if (!f.length) return;
    const i = f.indexOf(document.activeElement);
    ev.preventDefault();
    f[ev.shiftKey ? (i <= 0 ? f.length - 1 : i - 1) : (i >= f.length - 1 ? 0 : i + 1)].focus();
  }
  $('#pauseOv').addEventListener('keydown', ev => trapTab(ev, $('#pauseOv')));
  // a solo game that disappears behind the menu (lost connection) must not leave the menu over the lobby
  setInterval(() => { if (pauseOpen() && !S.inGame) closePause(true); }, 500);

  /* ---------------- first visit ---------------- */
  const welcomeOpen = () => !$('#welcomeOv').classList.contains('hidden');
  function welcomeShow() {
    const ov = $('#welcomeOv');
    ov.innerHTML = '<div class="card folio orn welc"><h2>Vítej v Hře mrtvých králů</h2>'
      + '<p>Dva mrtví králové, jedno město a Mlha mezi nimi. Nejrychleji se to naučíš hrou.</p>'
      + '<div class="pbtns"><button type="button" class="btn big" data-w="tut">Výuka (asi 8 min)</button>'
      + '<button type="button" class="btn" data-w="train">Výcvik proti AI</button><button type="button" class="btn dark" data-w="play">Rovnou hrát</button></div>'
      + '<p class="muted">Výuku najdeš kdykoli v lobby pod tlačítkem „Výuka“.</p></div>';
    ov.classList.remove('hidden');
    ov.querySelector('[data-w="tut"]').focus();
  }
  function welcomeClose(choice) {
    save(LS_SEEN, '1');
    $('#welcomeOv').classList.add('hidden');
    uiSfx('click');
    if (choice === 'tut') soloStart({ type: 'vyuka', mode: LOBBY.solo.mode, map: 'predmesti', ai: null });
    else if (choice === 'train') setType('vycvik');
  }
  function welcomeCheck() {
    if (MD.welcomed) return;
    MD.welcomed = true;
    if (load(LS_SEEN, '') || S.inGame || (S.meProf && S.meProf.m > 0)) return;
    welcomeShow();
  }
  $('#welcomeOv').addEventListener('click', ev => { const b = ev.target.closest('button[data-w]'); if (b) welcomeClose(b.dataset.w); });
  $('#welcomeOv').addEventListener('keydown', ev => trapTab(ev, $('#welcomeOv')));
  // a profile-less visit gets no 'me' with data: decide shortly after the first lobby message when 'me' has not come
  on('lobby', () => {
    if (!MD.welcomed && !MD.wt) MD.wt = setTimeout(welcomeCheck, 1500);
    if (!S.inGame) { closePause(true); clearGameUi(); }
  });

  /* ---------------- bus: esc, start, snap, end ---------------- */
  on('esc', why => {
    if (why === 'idle') openPause();
    else if (why === 'modal') { if (pauseOpen()) closePause(); else if (welcomeOpen()) welcomeClose('play'); }
  });

  function clearGameUi() {
    const b = $('#modeBox'); if (b) b.remove();
    const c = $('#tutCard'); c.classList.add('hidden'); c.innerHTML = ''; c.classList.remove('hot');
    const cell = $('#tutCell'); if (cell) cell.remove();
    document.querySelectorAll('.tut').forEach(e => e.classList.remove('tut'));
    delete document.body.dataset.tut;
    $('#clock').classList.remove('pzlow'); $('#clockBox').removeAttribute('title');
    MD.tuStep = 0; MD.tuUi = ''; MD.puz = null; MD.sv = null; MD.k = 0;
    holdTips(false);
  }

  on('start', m => {
    closePause(true);
    clearGameUi();
    const r = $('#modeRes'); if (r) r.remove();
    MD.type = m.type || 'souboj'; MD.puz = m.puzzle || null; MD.sv = m.surv || null; MD.k = 0;
    // the best result before this game (the profile may already hold the new one when the end overlay shows)
    MD.before = MD.type === 'puzzle' && MD.puz ? puzBest(MD.puz.id) : MD.type === 'preziti' ? survBest(mapId(), S.mode) : null;
    if (m.tut) { holdTips(true); MD.tsteps = Array.isArray(m.tsteps) ? m.tsteps : []; tutBuild(); }
    else if (MD.type === 'puzzle' && MD.puz) { holdTips(true); puzUpdate({ pz: [MD.puz.time || 0, 0, 0] }); }   // a puzzle has its own texts: no general tips
  });

  on('snap', m => {
    if (!S.inGame) return;
    if (m.sv) survUpdate(m);
    if (m.pz) puzUpdate(m);
    if (m.tu && S.tut) tutUpdate(m);
  });

  /* ---------------- end: save the progress and add the result block ---------------- */
  function resBlock(endMetaEl, html) {
    const old = $('#modeRes'); if (old) old.remove();
    if (!html || !endMetaEl || !endMetaEl.parentNode) return null;
    const d = document.createElement('div');
    d.id = 'modeRes'; d.className = 'mres'; d.innerHTML = html;
    endMetaEl.parentNode.insertBefore(d, endMetaEl);
    return d;
  }
  function puzResult(m, endMetaEl) {
    const r = m.puzzle, list = puzList(), i = list.findIndex(p => p.id === r.id), p = list[i] || MD.puz || { id: r.id, name: r.id, stars_text: [] };
    const before = MD.before && MD.puz && MD.puz.id === r.id ? MD.before : puzBest(r.id), quit = m.code === 'quit' || m.code === 'disc';
    if (r.ok && r.stars >= 1) savePuz(r.id, Math.min(3, r.stars | 0), +r.t || 0);
    const after = puzBest(r.id), isNew = r.ok && (after.s > before.s || (after.s === before.s && after.t < before.t && before.s > 0));
    const hit = Array.isArray(r.hit) ? r.hit : null, n = Math.min(3, r.stars | 0);
    const lines = (p.stars_text || []).map((t, k) => {
      let st = 'n';
      if (r.ok) st = hit ? (hit[k] ? 'y' : 'n') : n >= 3 || (k === 0 && n >= 1) ? 'y' : n === 1 ? 'n' : '?';
      const g = { y: ['✔', 'splněno'], n: ['✖', 'nesplněno'], '?': ['◇', 'nejisté'] }[st];
      return `<li class="${st}"><span class="mk2" aria-hidden="true">${g[0]}</span><span class="vh">${g[1]}: </span>${esc(t)}</li>`;
    }).join('');
    const unsure = r.ok && !hit && n === 2;
    const next = r.ok && i >= 0 && i + 1 < list.length && puzOpen(i + 1) ? list[i + 1] : null;
    if (r.ok) { MD.picked = true; LOBBY.puzzle = next ? next.id : r.id; }
    const head = quit ? 'Puzzle přerušeno' : r.ok ? 'Puzzle splněno' : 'Puzzle se nepovedlo';
    const sub = r.ok ? `${starsHtml(n)} za ${sec1(r.t)} s${isNew ? ' · <b>nový nejlepší výsledek</b>' : ''}`
      : quit ? 'Do postupu se nic nezapsalo.' : 'Zkus to znovu, ostatní puzzle zůstávají otevřená.';
    const html = `<h3>${esc(head)} · ${esc(p.name)}</h3><p class="mrs">${sub}</p>` + (lines ? `<ul class="mrstars">${lines}</ul>` : '')
      + (unsure ? '<p class="fdesc">Splněna je jedna z posledních dvou podmínek.</p>' : '')
      + `<div class="mrb"><button type="button" class="btn small" data-r="again">Zkusit znovu</button>`
      + (next ? `<button type="button" class="btn small" data-r="next">Další: ${esc(next.name)}</button>` : '') + '</div>';
    const d = resBlock(endMetaEl, html);
    if (d) d.addEventListener('click', ev => {
      const b = ev.target.closest('button[data-r]');
      if (!b) return;
      uiSfx('click');
      soloStart({ type: 'puzzle', puzzle: b.dataset.r === 'next' && next ? next.id : r.id, map: null, ai: null });
    });
  }
  function survResult(m, endMetaEl) {
    const sv = m.surv, mp = m.map || mapId(), two = !!(sv.players === 2 || (MD.sv && MD.sv.players === 2));
    const w = (sv.wave || [0, 0]).map(x => x | 0), t = (sv.t || [0, 0]).map(x => +x || 0), me = S.side === 1 ? 1 : 0;
    const before = MD.before || survBest(mp, S.mode);
    if (m.code !== 'error' && m.code !== 'disc') saveSurv(mp, S.mode, w[me], t[me]);
    const after = survBest(mp, S.mode), isNew = w[me] > 0 && betterSurv({ w: w[me], t: t[me] }, before);
    let h = `<h3>Přežití · ${esc(mapName(mp))}, ${modeName(S.mode)}</h3>`;
    h += two ? `<p class="mrs">Ty: ${w[me]} ${vln(w[me])} (${fmtT(t[me])}) · soupeř: ${w[1 - me]} ${vln(w[1 - me])} (${fmtT(t[1 - me])})</p>`
      : `<p class="mrs">Vyčištěno ${w[me]} ${vln(w[me])}, vydržel jsi ${fmtT(t[me])}.</p>`;
    h += isNew ? '<p class="mrs"><b>Nový rekord.</b></p>' : `<p class="mrs">Rekord: ${survText(after)}</p>`;
    resBlock(endMetaEl, h);
  }
  function tutResult(m, endMetaEl) {
    if (m.code !== 'throne' || m.winner !== S.side) return resBlock(endMetaEl, '');
    const d = resBlock(endMetaEl, '<h3>Výuka dokončena</h3><p class="mrs">Teď zkus Výcvik proti AI, nebo hru s kamarádem.</p>'
      + '<div class="mrb"><button type="button" class="btn small" data-r="train">Výcvik proti AI</button></div>');
    if (d) d.addEventListener('click', ev => {
      if (!ev.target.closest('button[data-r]')) return;
      $('#endOv').classList.add('hidden'); showLobby(); setType('vycvik');
    });
  }
  on('end', (m, endMetaEl) => {
    const type = m.type || MD.type;
    try {
      if (type === 'puzzle' && m.puzzle) puzResult(m, endMetaEl);
      else if (type === 'preziti' && m.surv) survResult(m, endMetaEl);
      else if (type === 'vyuka') tutResult(m, endMetaEl);
      else resBlock(endMetaEl, '');
    } finally {
      closePause(true); clearGameUi();
      refreshPane(); updateReady();
    }
  });

  // for tests and later modules
  window.MODES = { puzBest, survBest, puzOpen, nextPuzzle, openPause, closePause, tutHtml, state: MD };
})();
