// Uživatelské rozhraní (DOM): horní lišta, panel výběru, záložky, úkoly, příručka, vyhledávání.
'use strict';

const TABS = [['storage', 'ui.storage'], ['quests', 'ui.quests'], ['research', 'ui.research'], ['guide', 'ui.guide'], ['empire', 'ui.galaxy'], ['log', 'ui.log']];

const UI = {
  tab: 'storage', recipe: 'plate', lastInfo: '', lastTab: '', lastQuest: '', guideRes: 'circuit',

  init() {
    this.$ = id => document.getElementById(id);
    // akce na stisk tlačítka: panely se překreslují 4× za sekundu a klik (stisk + puštění) by se mohl ztratit
    document.body.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      const a = e.target.closest('[data-act]');
      if (a && !a.disabled) { e.preventDefault(); this.action(a.dataset.act, a.dataset); }
    });
    document.body.addEventListener('change', e => {
      if (e.target.id === 'recipeSel') { this.recipe = e.target.value; this.lastInfo = ''; e.target.blur(); }
    });
    this.$('speeds').innerHTML = [0, 1, 10, 100, 1000, 10000].map((s, i) =>
      `<button data-act="speed" data-v="${s}" title="${i ? s + '× (' + (i) + ')' : I18N.t('ui.pause') + ' (mezerník)'}">${i ? (s >= 1000 ? s / 1000 + 'k' : s) + '×' : '❚❚'}</button>`).join('');
    Search.init();
    // bubliny s rozpisem (⚡ energie, ✦ antihmota, ⚗ výzkum); dají se posouvat a zůstanou otevřené, když na ně přejedeš myší
    const stats = this.$('stats'), tip = this.$('powerTip');
    let hideT = null;
    const hideSoon = () => { clearTimeout(hideT); hideT = setTimeout(() => { this.tipMode = null; tip.classList.remove('show'); }, 300); };
    stats.addEventListener('mouseover', e => {
      const s = e.target.closest('[data-tip]');
      if (!s) return;
      clearTimeout(hideT);
      if (this.tipMode !== s.dataset.tip) { this.tipMode = s.dataset.tip; this.renderStatTip(true); }
    });
    stats.addEventListener('mouseout', e => { if (e.target.closest('[data-tip]')) hideSoon(); });
    tip.addEventListener('mouseenter', () => clearTimeout(hideT));
    tip.addEventListener('mouseleave', hideSoon);
    this.applyLang();
    setInterval(() => this.refresh(), 250);
  },

  applyLang() {
    document.title = I18N.t('title');
    this.$('title').textContent = I18N.t('title');
    this.$('lang').textContent = I18N.lang === 'cs' ? 'EN' : 'CZ';
    this.$('btnHelp').textContent = I18N.t('ui.help');
    this.$('btnSave').textContent = I18N.t('ui.save');
    this.$('btnNew').textContent = I18N.t('ui.new');
    this.$('search').placeholder = I18N.t('ui.search');
    document.querySelector('.tabs').innerHTML = TABS.map(([k, l]) => `<button data-act="tab" data-tab="${k}" class="${k === this.tab ? 'on' : ''}">${I18N.t(l)}</button>`).join('');
    this.$('quick').innerHTML = [['earth', 'ui.home'], ['solar', 'ui.solar'], ['local', 'ui.local'], ['galaxy', 'ui.galaxyView'], ['universe', 'ui.universe']]
      .map(([k, l]) => `<button data-act="quick" data-v="${k}">${I18N.t(l)}</button>`).join('');
    this.$('help').innerHTML = I18N.t('help') + `<button data-act="closeHelp" class="primary">OK</button>`;
    this.lastInfo = ''; this.lastTab = ''; this.lastQuest = '';
  },

  setTab(tab) {
    this.tab = tab; this.lastTab = '';
    document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  },

  action(act, d) {
    const G = Game;
    switch (act) {
      case 'speed': Main.setSpeed(+d.v); break;
      case 'tab': this.setTab(d.tab); break;
      case 'lang': I18N.set(I18N.lang === 'cs' ? 'en' : 'cs'); Galaxy.names[Galaxy.solIndex] = I18N.lang === 'cs' ? 'Slunce' : 'Sun'; this.applyLang(); break;
      case 'help': this.$('help').classList.toggle('show'); break;
      case 'closeHelp': this.$('help').classList.remove('show'); break;
      case 'save': if (G.save()) this.toast(I18N.t('ui.saved')); break;
      case 'new': this.newGameDialog(); break;
      case 'newMode': this.$('modal').classList.remove('show'); G.newGame(d.v === 'sandbox'); Main.select(null); Main.quick('solar'); this.lastQuest = ''; break;
      case 'closeModal': this.$('modal').classList.remove('show'); break;
      case 'quick': Main.quick(d.v); break;
      case 'goto': Main.flyToSel(); break;
      case 'selStar': Main.select({ type: 'star', id: d.id, key: d.id }); Main.flyToSel(); break;
      case 'selBody': { const sys = Galaxy.system(d.sys); const b = sys.bodies.find(x => x.id === d.id); Main.select({ type: 'body', body: b, key: b.id }); Main.flyToSel(); break; }
      case 'build': {
        const b = Main.sel.body, B = BUILDINGS[d.t], n = +d.n || 1;
        const miss = G.missing(B.cost);
        const done = G.build(d.t, b, d.t === 'assembler' ? this.recipe : null, n);
        if (!done) this.toast(miss.length ? I18N.t('ui.missing', miss.map(([r, v]) => U.num(Math.ceil(v)) + ' ' + I18N.t('res.' + r)).join(', ')) : '✖');
        this.lastInfo = ''; break;
      }
      case 'buildMore': {
        const e = G.s.sys[d.sys].b[+d.i];
        if (!e) break;
        const body = Galaxy.system(d.sys).bodies.find(x => x.id === e.body);
        const miss = G.missing(BUILDINGS[e.t].cost);
        if (!G.build(e.t, body, e.r || null, 1)) this.toast(miss.length ? I18N.t('ui.missing', miss.map(([r, v]) => U.num(Math.ceil(v)) + ' ' + I18N.t('res.' + r)).join(', ')) : '✖');
        this.lastInfo = ''; break;
      }
      case 'toggleDyson':
        Renderer.hideDyson = !Renderer.hideDyson;
        try { localStorage.setItem('galciv-hideDyson', Renderer.hideDyson ? '1' : '0'); } catch (e) { }
        this.toast(I18N.t(Renderer.hideDyson ? 'ui.dysonHidden' : 'ui.dysonShown')); this.lastInfo = ''; break;
      case 'quality': {
        const order = ['auto', 'high', 'mid', 'low'];
        Renderer.quality = order[(order.indexOf(Renderer.quality) + 1) % order.length];
        Renderer.autoScale = 1;
        try { localStorage.setItem('galciv-quality', Renderer.quality); } catch (e) { }
        Renderer.resize(); break;
      }
      case 'demolish': {
        const st = G.s.sys[d.sys]; const e = st.b[+d.i];
        if (e) G.demolish(d.sys, e, 1); this.lastInfo = ''; break;
      }
      case 'research': G.startResearch(d.id); this.lastTab = ''; break;
      case 'probe': G.launchProbe(d.id, G.probeSpeeds()[+d.i]); this.lastInfo = ''; break;
      case 'skip': Main.skipTo(+d.t); break;
      case 'wormhole': G.openWormhole(d.id); this.lastInfo = ''; break;
      case 'guide': this.guideRes = d.r; this.setTab('guide'); break;
      case 'guideBody': Quests.focus(d.k); break;
      case 'qfocus': Quests.focus(d.f); break;
      case 'search': Search.pick(+d.i); break;
    }
  },

  newGameDialog() {
    const t = I18N.t.bind(I18N);
    this.$('modal').innerHTML = `<h3>${t('ui.new')}</h3><p class="dim">${t('ui.newConfirm')}</p>
      <div class="modes">
        <button data-act="newMode" data-v="campaign" class="primary"><b>${t('ui.campaign')}</b><small>${t('ui.campaignD')}</small></button>
        <button data-act="newMode" data-v="sandbox"><b>${t('ui.sandbox')}</b><small>${t('ui.sandboxD')}</small></button>
      </div><button data-act="closeModal">${t('ui.cancel')}</button>`;
    this.$('modal').classList.add('show');
  },

  toast(msg) {
    const t = U.el('div', 'toast', U.esc(msg));
    this.$('toasts').prepend(t);
    setTimeout(() => t.classList.add('out'), 5000);
    setTimeout(() => t.remove(), 6000);
    while (this.$('toasts').children.length > 5) this.$('toasts').lastChild.remove();
  },

  refresh() {
    if (!Game.s) return;
    const t0 = I18N.t.bind(I18N);
    const S = Game.s;
    Quests.check();
    this.$('date').textContent = U.dateStr(S.t);
    const R = Renderer;
    this.$('btnQuality').textContent = `${t0('ui.gfx')}: ${t0('q.' + R.quality)}${R.quality === 'auto' && R.autoScale < 1 ? ' ' + Math.round(R.autoScale * 100) + ' %' : ''} · ${Math.round(Main.fps)} FPS`;
    document.querySelectorAll('#speeds button').forEach(b => b.classList.toggle('on', +b.dataset.v === Main.speed));
    const K = U.kardashev(Game.totalPower);
    this.$('stats').innerHTML = (S.sandbox ? `<div class="stat sb">SANDBOX</div>` : '') +
      `<div class="stat" title="${I18N.t('ui.kardashev')}"><span>K</span><b>${K.toFixed(2)}</b><i style="width:${U.clamp(K / 3 * 100, 0, 100)}%"></i></div>` +
      `<div data-tip="pw" class="stat pw ${this.tipMode === 'pw' ? 'open' : ''} ${Game.totalDemand > Game.totalSupply * 1.001 ? 'short' : ''}"><span>⚡</span><b>${U.si(Game.totalDemand || 0, 'W')}</b><small>/ ${U.si(Game.totalSupply || 0, 'W')}</small></div>` +
      `<div data-tip="am" class="stat am tipable ${this.tipMode === 'am' ? 'open' : ''}"><span>✦</span><b>${U.mass(S.am)}</b><small>/ ${U.mass(S.amCap || 0)}</small></div>` +
      `<div data-tip="rp" class="stat tipable ${this.tipMode === 'rp' ? 'open' : ''}"><span>⚗</span><b>${U.num(S.rp)}</b><small>+${U.num(Game.rates.rp || 0)}/h</small></div>`;
    this.renderInfo();
    this.renderTab();
    this.renderQuestCard();
    if (this.tipMode) this.renderStatTip(false);
    this.renderScale();
  },

  costHtml(cost, mult = 1) {
    return Object.entries(cost).map(([r, v]) => {
      const ok = (Game.s.store[r] || 0) >= v * mult;
      return `<a class="cost ${ok ? '' : 'miss'}" data-act="guide" data-r="${r}" title="${I18N.t('ui.howGet')}"><i style="background:${RES_COLOR[r]}"></i>${U.num(v * mult)} ${I18N.t('res.' + r)}</a>`;
    }).join(' ');
  },

  renderInfo() {
    // rozbalený seznam (recept) by překreslení zavřelo
    const ae = document.activeElement;
    if (ae && ae.tagName === 'SELECT' && this.$('info').contains(ae)) return;
    if (this.selecting('info')) return;   // označený text (kopírování) by překreslení zrušilo
    const sel = Main.sel;
    let h = '';
    if (!sel) h = `<p class="dim">${I18N.t('ui.selectHint')}</p>`;
    else if (sel.type === 'star') h = this.starInfo(sel.id);
    else if (sel.type === 'body') h = this.bodyInfo(sel.body);
    else if (sel.type === 'galaxy') h = this.galaxyInfo(sel.g);
    if (h !== this.lastInfo) { this.$('info').innerHTML = h; this.lastInfo = h; }
  },

  selecting(id) { const s = window.getSelection(); return !!(s && !s.isCollapsed && s.anchorNode && this.$(id).contains(s.anchorNode)); },

  row(k, v) { return `<div class="row"><span>${k}</span><b>${v}</b></div>`; },

  starInfo(id) {
    const s = Galaxy.starRec(id);
    if (!s) return '';
    const t = I18N.t.bind(I18N);
    const e = s.exo;
    let h = `<h2>${U.esc(s.name)}</h2>`;
    const badge = s.real ? (e ? t('ui.realExo') : t('ui.realData')) : t('ui.procData');
    h += `<div class="badge ${s.real ? 'real' : 'proc'}">${badge}</div>`;
    if (e && e.note) h += `<p class="note">${e.note[I18N.lang === 'cs' ? 0 : 1]}</p>`;
    const distLy = Math.hypot(s.x, s.y, s.z || 0) / C.KM_PER_LY;
    if (s.kind === 'bh') {
      h += this.row(t('ui.type'), t('kind.bh'));
      h += this.row(t('ui.mass'), U.num(e.M) + ' M☉');
      h += this.row(t('ui.rs'), U.dist(e.M * C.RS_KM_PER_MSUN));
    } else if (s.kind === 'ns') {
      h += this.row(t('ui.type'), e.magnetar ? t('kind.magnetar') : (e.P < 5 ? t('kind.pulsar') : t('kind.ns')));
      h += this.row(t('ui.radius'), '≈ 12 km');
      h += this.row(t('ui.spin'), e.P < 1 ? U.num(e.P * 1000) + ' ms' : U.num(e.P) + ' s');
      h += this.row(t('ui.spindown'), U.si(e.Lsd, 'W'));
    } else {
      h += this.row(t('ui.type'), s.sp || '?');
      h += this.row(t('ui.temp'), Math.round(s.T).toLocaleString(I18N.locale()) + ' K');
      h += this.row(t('ui.radius'), `${U.num(s.R)} R☉ <small>(${U.dist(s.R * C.R_SUN_KM)})</small>`);
      h += this.row(t('ui.lum'), `${U.num(s.L)} L☉ <small>(${U.si(s.L * C.L_SUN_W, 'W')})</small>`);
    }
    h += this.row(t('ui.distSol'), distLy < 1e-3 ? '0' : U.num(distLy) + ' ' + t('u.ly'));
    h += `<button data-act="goto" class="wide">${t('ui.goto')} ⟶</button>`;
    h += this.sysSection(id);
    return h;
  },

  sysSection(id) {
    const t = I18N.t.bind(I18N);
    const G = Game;
    const sys = Galaxy.system(id);
    if (!sys) return '';
    let h = '';
    const st = G.s.sys[id];
    if (!G.connected(id)) h += this.wormholeSteps(id);
    if (G.connected(id)) {
      h += `<div class="badge net">◆ ${t('ui.connected')}</div>`;
      const pw = G.power[id];
      if (pw) {
        h += `<h3>${t('ui.power')}</h3>`;
        h += this.row('⚡', `${U.si(pw.supply, 'W')} / ${U.si(pw.demand, 'W')}`);
        h += `<div class="bar"><i style="width:${pw.sat * 100}%;background:${pw.sat < 0.99 ? '#ff7b5c' : '#6fdc8c'}"></i></div>`;
        if (pw.trapSat < 0.999) h += `<p class="warn">${t('ui.trapLoss')}</p>`;
        const dy = pw.dyson;
        if (st && (st.sails > 0.5 || st.nodes > 0.5)) {
          h += `<h3>${t('ui.dyson')}</h3>`;
          h += this.row(t('ui.coverage'), (dy.cov * 100).toPrecision(3) + ' %');
          h += `<div class="bar"><i style="width:${dy.cov * 100}%;background:#ffb347"></i></div>`;
          h += this.row(t('ui.sails'), U.amount(st.sails)) + this.row(t('ui.nodes'), U.amount(st.nodes));
          h += this.row(t('ui.captured'), U.si(dy.watts, 'W')) + this.row(t('ui.used'), U.si(pw.dysonUsed, 'W'));
          h += `<button data-act="toggleDyson" class="wide">${Renderer.hideDyson ? '👁 ' + t('ui.showDyson') : '🙈 ' + t('ui.hideDyson')} <small>(D)</small></button>`;
        }
      }
    } else if (st && st.gate) {
      const c = G.wormholeCost(id);
      if (c) {
        const ok = G.s.am >= c.kg;
        h += `<button data-act="wormhole" data-id="${id}" class="wide primary" ${ok ? '' : 'disabled'}>${t('ui.openWormhole', U.mass(c.kg))}</button>`;
        if (!ok) h += `<p class="warn">${t('ui.needAm', U.mass(G.s.am), U.mass(c.kg))}</p>`;
        h += `<p class="dim">${U.num(c.ly)} ${t('u.ly')} ← ${U.esc(Galaxy.starRec(c.from).name)}</p>`;
      }
    } else {
      const pr = G.s.probes.find(p => p.to === id);
      if (pr) {
        h += `<p>${t('ui.probeOnWay', U.duration(pr.arrive - G.s.t))}</p>`;
        h += `<button data-act="skip" data-t="${pr.arrive}" class="wide">${t('ui.skip')} ⏩</button>`;
      } else if (!G.explored(id)) {
        h += `<h3>${t('ui.sendProbe')}</h3>`;
        const nd = G.nearestDock(id);
        const sp = G.probeSpeeds();
        if (!nd || !sp.length) h += `<p class="dim">${t('ui.noDock')}</p>`;
        else {
          h += `<div class="costs">${this.costHtml(ECO.PROBE_COST)}</div>`;
          sp.forEach((v, i) => {
            const years = nd.ly / v.c, gamma = 1 / Math.sqrt(1 - v.c * v.c);
            const tx = t('ui.travel', U.num(nd.ly) + ' ' + t('u.ly'), v.c, U.duration(years * C.HOURS_PER_YEAR), U.duration(years / gamma * C.HOURS_PER_YEAR));
            const ok = G.canAfford(ECO.PROBE_COST) && (!v.am || G.s.am >= v.am);
            h += `<button data-act="probe" data-id="${id}" data-i="${i}" class="wide" ${ok ? '' : 'disabled'}>🛰 ${v.c} c${v.am ? ' + ' + U.mass(v.am) : ''}</button><p class="dim small">${tx}</p>`;
          });
        }
      }
    }
    const show = G.explored(id) || !sys.procedural || G.connected(id);
    h += `<h3>${t('ui.bodies')}</h3>`;
    if (!show) h += `<p class="dim">${t('ui.unexplored')}</p>`;
    else {
      h += '<div class="bodies">';
      for (const b of sys.bodies) {
        const ents = st ? st.b.filter(e => e.body === b.id) : [];
        const ic = ents.map(e => BUILDINGS[e.t].icon).join('');
        h += `<button data-act="selBody" data-sys="${id}" data-id="${b.id}" class="${b.parent ? 'moon' : ''}">${U.esc(Galaxy.bodyName(b))} <small>${ic}</small></button>`;
      }
      h += '</div>';
    }
    return h;
  },

  depositsHtml(b) {
    const t = I18N.t.bind(I18N), G = Game;
    const deps = Object.entries(b.dep);
    if (!deps.length) return '';
    const rates = G.bodyRates[b.id] || {};
    let h = `<h3>${t('ui.deposits')}</h3>`;
    for (const [r, v] of deps) {
      const init = G.reserveInit(b, r), left = G.depLeft(b, r), rate = rates[r] || 0;
      const inf = left === Infinity;
      const pct = inf ? 100 : init ? left / init * 100 : 0;
      const eta = !inf && rate > 0 ? ' · ' + t('ui.runsOut', U.duration(left / rate)) : '';
      h += `<div class="depr"><a data-act="guide" data-r="${r}"><i style="background:${RES_COLOR[r]}"></i>${t('res.' + r)}</a>
        <span class="rich" title="${t('ui.richness')}">${'●'.repeat(Math.max(1, Math.round(v * 2)))}</span>
        <b>${inf ? '∞' : U.amount(left)}</b>
        <div class="bar"><i style="width:${pct}%;background:${RES_COLOR[r]}"></i></div>
        <small>${rate > 0 ? '+' + U.amount(rate) + '/h' : t('ui.notMined')}${eta}</small></div>`;
    }
    return h;
  },

  bodyInfo(b) {
    const t = I18N.t.bind(I18N);
    const G = Game;
    const sys = Galaxy.system(b.sys);
    let h = `<h2>${U.esc(Galaxy.bodyName(b))}</h2>`;
    h += `<div class="badge ${b.real ? 'real' : 'proc'}">${t('type.' + b.type)}</div>`;
    h += `<p class="dim">⟵ <a data-act="selStar" data-id="${sys.id}">${U.esc(sys.star.name)}</a></p>`;
    if (b.type === 'belt') h += this.row(t('ui.orbit'), U.dist(b.a0) + ' – ' + U.dist(b.a1));
    else h += this.row(t('ui.orbit'), U.dist(b.a));
    if (b.type !== 'belt') h += this.row(t('ui.period'), U.duration(Math.abs(b.P)));
    if (b.R > 10) h += this.row(t('ui.radius'), U.dist(b.R));
    h += this.row(t('ui.flux'), U.num(Galaxy.fluxAt(sys, b)) + ' W/m²');
    h += this.depositsHtml(b);
    if (!G.connected(b.sys)) { h += `<p class="dim">${t('ui.notConnected')}</p>`; return h; }
    const st = G.sysState(b.sys);
    const ents = st.b.map((e, i) => [e, i]).filter(([e]) => e.body === b.id);
    if (ents.length) {
      h += `<h3>${t('ui.buildings')}</h3>`;
      for (const [e, i] of ents) {
        h += `<div class="bld"><span>${BUILDINGS[e.t].icon} ${t('b.' + e.t)}${e.r ? ' · ' + t('res.' + e.r) : ''}</span><b>×${e.n}</b>` +
          (BUILDINGS[e.t].cost ? `<button data-act="buildMore" data-sys="${b.sys}" data-i="${i}" title="${t('ui.buildOne')}" ${BUILDINGS[e.t].unique ? 'disabled' : ''}>+</button><button data-act="demolish" data-sys="${b.sys}" data-i="${i}" title="${t('ui.demolish')}">−</button>` : '') + `</div>`;
      }
    }
    const pw = G.power[b.sys];
    if (pw && pw.sat < 0.99) h += `<p class="warn">${t('ui.satisfaction')}: ${(pw.sat * 100).toFixed(0)} % · ${t('ui.lowPower')}</p>`;
    h += `<h3>${t('ui.build')}</h3>`;
    for (const type of BUILD_ORDER) {
      if (!G.buildableOn(type, b, sys)) continue;
      const B = BUILDINGS[type];
      if (B.unique && st.b.some(e => e.t === type)) continue;
      let extra = '';
      if (type === 'assembler') {
        const opts = Object.keys(RECIPES).filter(r => !RECIPES[r].tech || G.has(RECIPES[r].tech));
        if (!opts.includes(this.recipe)) this.recipe = opts[0];
        extra = `<select id="recipeSel">${opts.map(r => `<option value="${r}" ${r === this.recipe ? 'selected' : ''}>${t('res.' + r)}</option>`).join('')}</select>`;
        const rc = RECIPES[this.recipe];
        extra += `<div class="small recipe">${Object.entries(rc.in).map(([r, v]) => Guide.chip(r, v * rc.rate)).join(' + ')} → ${Object.entries(rc.out).map(([r, v]) => Guide.chip(r, v * rc.rate)).join(', ')} ${t('ui.per_h')}</div>`;
      }
      let info = '';
      if (type === 'solar') info = '+' + U.si(Galaxy.fluxAt(sys, b) * ECO.SOLAR_AREA_M2 * ECO.SOLAR_EFF, 'W');
      else if (type === 'mine') info = Object.entries(b.dep).filter(([r]) => r !== 'h2' || b.type !== 'gas').map(([r, v]) => '+' + U.num(ECO.MINE_RATE * v * G.speedMult()) + ' ' + t('res.' + r)).join(', ') + ' /h · −' + U.si(B.pw, 'W');
      else if (B.pw > 0) info = '−' + U.si(B.pw, 'W');
      else if (B.pw < 0) info = '+' + U.si(-B.pw, 'W');
      const ok = G.canAfford(B.cost);
      h += `<div class="card ${ok ? '' : 'poor'}">
        <div class="ct"><span>${B.icon} ${t('b.' + type)}</span></div>
        <div class="dim small">${t('bd.' + type)}</div><div class="small eff">${info}</div>${extra}
        <div class="costs">${this.costHtml(B.cost)}</div>
        <div class="btns"><button data-act="build" data-t="${type}" data-n="1">+1</button><button data-act="build" data-t="${type}" data-n="5" ${B.unique ? 'disabled' : ''}>+5</button></div>
      </div>`;
    }
    return h;
  },

  // kontrolní seznam: co chybí k červí díře do této soustavy
  wormholeSteps(id) {
    const t = I18N.t.bind(I18N), G = Game, S = G.s;
    const st = S.sys[id];
    const probe = S.probes.find(p => p.to === id);
    const arrived = !!(st && st.gate);
    let c = G.wormholeCost(id);
    if (!c) { const ly = Galaxy.distLy('h' + Galaxy.solIndex, id); c = { ly, kg: ly * ECO.WORMHOLE_KG_PER_LY }; }
    const steps = [
      [G.has('magnet'), t('ws.magnet'), 'tab:research'],
      [G.has('probe'), t('ws.tech'), 'tab:research'],
      [G.count('dock') > 0, t('ws.dock'), 'earth'],
      [G.count('gate') > 0, t('ws.gate'), 'station'],
      [G.count('trap') > 0 && G.count('collector') + G.count('accelerator') + G.count('pcollector') + G.count('acollector') > 0, t('ws.am'), 'jupiter'],
      [arrived, probe ? t('ws.probeFly', U.duration(probe.arrive - S.t)) : t('ws.probe'), null],
      [arrived && S.am >= c.kg, t('ws.open', U.mass(c.kg), U.mass(S.am)), null],
    ];
    let h = `<h3>${t('ws.title')}</h3><div class="steps">`;
    let first = true;
    for (const [ok, txt, f] of steps) {
      const cur = !ok && first;
      if (!ok) first = false;
      h += `<div class="step ${ok ? 'ok' : cur ? 'cur' : ''}"><span>${ok ? '✓' : cur ? '▶' : '○'}</span><div>${txt}`;
      if (cur && f) h += ` <a data-act="qfocus" data-f="${f}">${t('ui.showMe')}</a>`;
      h += `</div></div>`;
    }
    return h + '</div>';
  },

  // bublina po najetí myší na objekt ve vesmíru
  tipHtml(h) {
    const t = I18N.t.bind(I18N), G = Game;
    const row = (k, v) => `<div class="tr"><span>${k}</span><b>${v}</b></div>`;
    if (h.type === 'galaxy') {
      const g = h.g;
      return `<b>${U.esc(g.name[I18N.lang === 'cs' ? 0 : 1])}</b>` + (g.type !== 'mw' ? row(t('ui.distSol'), U.dist(Math.hypot(g.x, g.y))) : '');
    }
    if (h.type === 'body') {
      const b = h.body, sys = Galaxy.system(b.sys);
      let s = `<b>${U.esc(Galaxy.bodyName(b))}</b><div class="dim">${t('type.' + b.type)}</div>`;
      s += row(t('ui.orbit'), b.type === 'belt' ? U.dist(b.a0) + ' – ' + U.dist(b.a1) : U.dist(b.a));
      s += row(t('ui.flux'), U.num(Galaxy.fluxAt(sys, b)) + ' W/m²');
      const deps = Object.keys(b.dep);
      if (deps.length) s += `<div class="tdeps">${deps.map(r => `<i style="background:${RES_COLOR[r]}"></i>${t('res.' + r)}`).join(' ')}</div>`;
      return s;
    }
    const st = Galaxy.starRec(h.id);
    if (!st) return '';
    const e = st.exo;
    const ly = Math.hypot(st.x, st.y, st.z || 0) / C.KM_PER_LY;
    let s = `<b>${U.esc(st.name)}</b><div class="dim">${st.kind === 'bh' ? t('kind.bh') : st.kind === 'ns' ? (e.magnetar ? t('kind.magnetar') : t('kind.pulsar')) : (st.sp || '') + ' · ' + Math.round(st.T).toLocaleString(I18N.locale()) + ' K'}</div>`;
    s += row(t('ui.distSol'), ly < 1e-3 ? '0' : U.num(ly) + ' ' + t('u.ly'));
    const near = h.id !== 'h' + Galaxy.solIndex && G.s.net.length > 1 ? G.s.net.reduce((m, id) => { const d = Galaxy.distLy(id, h.id); return d < m.d ? { id, d } : m; }, { d: Infinity }) : null;
    if (near && near.d > 1e-3) s += row(t('ui.nearestOwn'), U.num(near.d) + ' ' + t('u.ly'));
    if (st.kind === 'bh') s += row(t('ui.mass'), U.num(e.M) + ' M☉');
    else if (st.kind === 'ns') s += row(t('ui.spindown'), U.si(e.Lsd, 'W'));
    else {
      s += row(t('ui.lum'), U.num(st.L) + ' L☉ · ' + U.si(st.L * C.L_SUN_W, 'W'));
      s += row(t('ui.radius'), U.num(st.R) + ' R☉');
    }
    if (h.id !== 'h' + Galaxy.solIndex) s += row(t('ui.wormCost'), U.mass(Galaxy.distLy(G.wormholeCost(h.id) ? G.wormholeCost(h.id).from : 'h' + Galaxy.solIndex, h.id) * ECO.WORMHOLE_KG_PER_LY));
    const stt = G.connected(h.id) ? '◆ ' + t('ui.connected') : G.s.probes.some(p => p.to === h.id) ? '🛰 ' + t('ws.probeFly', U.duration(G.s.probes.find(p => p.to === h.id).arrive - G.s.t)) : G.s.sys[h.id] && G.s.sys[h.id].gate ? '◌ ' + t('ui.gateReady') : '';
    if (stt) s += `<div class="tst">${stt}</div>`;
    return s;
  },

  galaxyInfo(g) {
    const t = I18N.t.bind(I18N);
    let h = `<h2>${U.esc(g.name[I18N.lang === 'cs' ? 0 : 1])}</h2><div class="badge real">${t('ui.realExo')}</div>`;
    if (g.type !== 'mw') h += this.row(t('ui.distSol'), U.dist(Math.hypot(g.x, g.y)));
    h += this.row(t('ui.radius'), U.num(g.D / 2 * 3.2616) + ' ' + t('u.kly'));
    if (g.bh) h += this.row(t('kind.bh'), U.num(g.bh) + ' M☉');
    return h;
  },

  techUnlocks(id) {
    const t = I18N.t.bind(I18N);
    const b = BUILD_ORDER.filter(k => BUILDINGS[k].tech === id).map(k => BUILDINGS[k].icon + ' ' + t('b.' + k));
    const r = Object.keys(RECIPES).filter(k => RECIPES[k].tech === id).map(k => '⚙ ' + t('res.' + k));
    return [...b, ...r];
  },

  renderTab() {
    const t = I18N.t.bind(I18N);
    const G = Game, S = G.s;
    let h = '';
    if (this.tab === 'storage') {
      for (const r of RES) {
        const v = S.store[r] || 0, rt = G.rates[r] || 0;
        if (v < 0.05 && Math.abs(rt) < 0.01 && !RAW.includes(r)) continue;
        h += `<div class="res" data-act="guide" data-r="${r}"><i style="background:${RES_COLOR[r]}"></i><span>${t('res.' + r)}</span><b>${U.amount(v)}</b><small class="${rt < -0.01 ? 'neg' : rt > 0.01 ? 'pos' : ''}">${rt > 0 ? '+' : ''}${U.amount(rt)}/h</small></div>`;
      }
      h += `<div class="res am" data-act="guide" data-r="am"><i style="background:#d58cff"></i><span>${t('res.am')}</span><b>${U.mass(S.am)}</b><small class="pos">+${U.mass(G.rates.am || 0)}/h</small></div>`;
      h += `<div class="dim small">${t('ui.capacity')}: ${U.mass(S.amCap || 0)}${S.amCap && S.am >= S.amCap * 0.999 ? ' · ' + t('ui.capFull') : ''}</div>`;
      h += `<p class="dim small">${t('ui.storageHint')}</p>`;
    } else if (this.tab === 'quests') {
      if (S.sandbox) h += `<p class="dim">${t('ui.sandboxNoQuests')}</p>`;
      const L = I18N.lang === 'cs' ? 0 : 1;
      h += `<div class="dim small">${t('ui.questsDone', S.qDone.length, QUESTS.length)}</div>`;
      const act = Quests.active(1)[0];
      for (const q of QUESTS) {
        const done = S.qDone.includes(q.id), cur = act && act.id === q.id;
        h += `<div class="quest ${done ? 'done' : cur ? 'cur' : ''}"><div class="ct"><b>${done ? '✓ ' : ''}${q.t[L]}</b></div>
          ${!done ? `<div class="small">${q.d[L]}</div>` : ''}
          ${Object.keys(q.reward).length ? `<div class="small rw">🎁 ${Quests.rewardText(q.reward)}</div>` : ''}
          ${!done && q.focus ? `<button data-act="qfocus" data-f="${q.focus}">${t('ui.showMe')}</button>` : ''}</div>`;
      }
    } else if (this.tab === 'research') {
      const rate = G.rates.rp || 0;
      if (S.research) {
        const T = TECH[S.research];
        h += `<div class="cur">${t('ui.researching')}: <b>${t('tech.' + S.research)}</b><div class="bar"><i style="width:${Math.min(100, S.rp / T.cost * 100)}%;background:#4fd1c5"></i></div><small>${U.num(S.rp)} / ${U.num(T.cost)} RP${rate > 0 ? ' · ' + U.duration(Math.max(0, T.cost - S.rp) / rate) : ''}</small></div>`;
      } else h += `<div class="cur warn">${t('ui.idle')} · ${U.num(S.rp)} RP</div>`;
      h += `<p class="dim small">${t('ui.rpHint', U.num(rate))}</p>`;
      for (const id of TECH_ORDER) {
        const T = TECH[id], done = G.has(id), av = G.techAvailable(id);
        const unl = this.techUnlocks(id);
        h += `<div class="tech ${done ? 'done' : av ? 'av' : 'lock'} ${S.research === id ? 'cur2' : ''}">
          <div class="ct"><b>${done ? '✓ ' : ''}${t('tech.' + id)}</b><small>${done ? t('ui.done') : U.num(T.cost) + ' RP'}</small></div>
          <div class="small">${t('td.' + id)}</div>
          ${unl.length && !done ? `<div class="unl"><span class="rl">🔓 ${t('ui.unlocks')}:</span>${unl.map(u => `<span class="uq">${u}</span>`).join('')}</div>` : ''}
          ${!done && !av ? `<div class="req"><span class="rl">🔒 ${t('ui.req')}:</span>${T.req.map(r => `<span class="rq ${G.has(r) ? 'ok' : 'no'}">${G.has(r) ? '✓' : '✗'} ${t('tech.' + r)}</span>`).join('')}</div>` : ''}
          ${av && S.research !== id ? `<button data-act="research" data-id="${id}">▶ ${t('ui.startResearch')}${rate > 0 && T.cost > (S.research ? 0 : S.rp) ? ' · ' + U.duration((T.cost - (S.research ? 0 : S.rp)) / rate) : ''}</button>` : ''}
        </div>`;
      }
    } else if (this.tab === 'guide') {
      h += Guide.render(this.guideRes);
    } else if (this.tab === 'empire') {
      const K = U.kardashev(G.totalPower);
      h += this.row(t('ui.kardashev'), K.toFixed(3)) + this.row(t('ui.power'), U.si(G.totalPower, 'W'));
      h += `<h3>${t('ui.network')}</h3>`;
      for (const id of S.net) {
        const s = Galaxy.starRec(id), pw = G.power[id];
        h += `<button class="wide sys" data-act="selStar" data-id="${id}">◆ ${U.esc(s.name)} <small>${pw ? U.si(pw.supply, 'W') : ''}</small></button>`;
      }
      const pending = Object.keys(S.sys).filter(id => S.sys[id].gate && !G.connected(id));
      for (const id of pending) h += `<button class="wide sys pend" data-act="selStar" data-id="${id}">◌ ${U.esc(Galaxy.starRec(id).name)}</button>`;
      h += `<h3>${t('ui.probes')}</h3>`;
      if (!S.probes.length) h += `<p class="dim">${t('ui.none')}</p>`;
      for (const p of S.probes) h += `<button class="wide sys" data-act="selStar" data-id="${p.to}">🛰 ${U.esc(Galaxy.starRec(p.to).name)} <small>${U.duration(p.arrive - S.t)}</small></button>`;
    } else if (this.tab === 'log') {
      for (const e of S.log) h += `<div class="log"><small>${U.dateStr(e.t)}</small><div>${U.esc(I18N.t(e.k, ...e.a))}</div></div>`;
    }
    if (h !== this.lastTab && !this.selecting('tabBody')) { this.$('tabBody').innerHTML = h; this.lastTab = h; }
  },

  bname(id) { if (!id) return ''; const sys = Galaxy.system(id.split(':')[0]); const b = sys && sys.bodies.find(x => x.id === id); return b ? Galaxy.bodyName(b) : ''; },
  sysName(bodyId) { const s = Galaxy.starRec(bodyId.split(':')[0]); return s ? s.name : ''; },

  renderStatTip(place) {
    const el = this.$('powerTip');
    if (place) {
      const anchor = document.querySelector(`[data-tip="${this.tipMode}"]`);
      if (!anchor) return;
      const r = anchor.getBoundingClientRect();
      el.style.left = Math.max(8, Math.min(window.innerWidth - 400, r.left - 120)) + 'px';
      el.style.top = (r.bottom + 6) + 'px';
      el.scrollTop = 0;
    }
    const h = this.tipMode === 'am' ? this.amTip() : this.tipMode === 'rp' ? this.rpTip() : this.powerTip();
    if (h !== this._tipHtml) { const st = el.scrollTop; el.innerHTML = h; el.scrollTop = st; this._tipHtml = h; }
    el.classList.add('show');
  },

  // řádky zdrojů seskupené podle soustavy
  srcRows(list, fmt) {
    const t = I18N.t.bind(I18N);
    let h = '', last = null;
    for (const o of list) {
      const sn = o.body ? this.sysName(o.body) : '';
      if (sn !== last && Game.s.net.length > 1) { h += `<div class="pt-sub">${U.esc(sn)}</div>`; last = sn; }
      h += `<div class="pt-row"><span>${BUILDINGS[o.t].icon} ${t('b.' + o.t)}${o.t !== 'hq' ? ' ×' + o.n : ''}<small> · ${U.esc(this.bname(o.body))}</small></span><b>${fmt(o.v)}</b></div>`;
    }
    return h;
  },

  amTip() {
    const t = I18N.t.bind(I18N), G = Game, S = G.s;
    const rate = (G.amSrc || []).reduce((a, o) => a + o.v, 0);
    let h = `<div class="pt-h"><span>${t('res.am')}</span><b>${U.mass(S.am)}</b><span>${t('ui.capacity')}</span><b>${U.mass(S.amCap || 0)}</b></div>`;
    h += `<div class="bar"><i style="width:${S.amCap ? Math.min(100, S.am / S.amCap * 100) : 0}%;background:#d58cff"></i></div>`;
    h += `<div class="pt-sec pos">▲ ${t('ui.sources')} · +${U.mass(rate)}/h</div>`;
    h += (G.amSrc || []).length ? this.srcRows(G.amSrc, v => '+' + U.mass(v) + '/h') : `<div class="pt-row dim small">${t('ui.amNoSrc')}</div>`;
    if (G.amWasted) h += `<div class="pt-row warn small">${t('ui.capFull')}</div>`;
    if (!S.amCap) h += `<div class="pt-row warn small">${t('ui.amNoTrap')}</div>`;
    h += `<div class="pt-sec">⌾ ${t('b.trap')}</div>`;
    let any = false;
    for (const id of S.net) {
      const n = (S.sys[id] ? S.sys[id].b : []).filter(e => e.t === 'trap').reduce((a, e) => a + e.n, 0);
      if (!n) continue; any = true;
      const pw = G.power[id];
      h += `<div class="pt-row"><span>${U.esc(Galaxy.starRec(id).name)} ×${n}</span><b>${U.mass(n * ECO.TRAP_CAP)}${pw && pw.trapSat < 0.999 ? ' <span class="neg">⚠</span>' : ''}</b></div>`;
    }
    if (!any) h += `<div class="pt-row dim small">${t('ui.none')}</div>`;
    h += `<div class="pt-sec neg">▼ ${t('ui.amUse')}</div><div class="pt-row small dim">${t('g.amUse')}</div>`;
    return h;
  },

  rpTip() {
    const t = I18N.t.bind(I18N), G = Game, S = G.s;
    const rate = G.rates.rp || 0;
    let h = `<div class="pt-h"><span>${t('ui.research')}</span><b>${U.num(S.rp)} RP</b><span>${t('ui.speedRp')}</span><b class="pos">+${U.num(rate)}/h</b></div>`;
    if (S.research) {
      const T = TECH[S.research];
      h += `<div class="pt-sys"><b>${t('tech.' + S.research)}</b><small>${U.num(S.rp)} / ${U.num(T.cost)}${rate > 0 ? ' · ' + U.duration(Math.max(0, T.cost - S.rp) / rate) : ''}</small></div>`;
      h += `<div class="bar"><i style="width:${Math.min(100, S.rp / T.cost * 100)}%;background:#4fd1c5"></i></div>`;
    } else h += `<div class="pt-row warn small">${t('ui.idle')}</div>`;
    h += `<div class="pt-sec pos">▲ ${t('ui.sources')}</div>`;
    h += this.srcRows(G.rpSrc || [], v => '+' + U.num(v) + ' RP/h');
    const labs = (G.rpSrc || []).filter(o => o.t === 'lab').reduce((a, o) => a + o.n, 0);
    h += `<div class="pt-sec neg">▼ ${t('ui.consumers')}</div>`;
    h += labs ? `<div class="pt-row"><span>${Guide.chip('circuit')} ← ${BUILDINGS.lab.icon} ×${labs}</span><b>${U.num(labs * ECO.LAB_IN)}/h</b></div>` : `<div class="pt-row dim small">${t('ui.none')}</div>`;
    if (G.labStarved) h += `<div class="pt-row warn small">${t('ui.labStarved')}</div>`;
    return h;
  },

  powerTip() {
    const t = I18N.t.bind(I18N), G = Game;
    const bname = id => this.bname(id);
    let h = `<div class="pt-h"><span>${t('ui.consumption')}</span><b class="${G.totalDemand > G.totalSupply * 1.001 ? 'neg' : ''}">${U.si(G.totalDemand || 0, 'W')}</b>
      <span>${t('ui.generation')}</span><b class="pos">${U.si(G.totalSupply || 0, 'W')}</b></div>`;
    for (const id of G.s.net) {
      const pw = G.power[id];
      if (!pw) continue;
      const pct = pw.supply ? pw.demand / pw.supply * 100 : (pw.demand ? Infinity : 0);
      h += `<div class="pt-sys"><b>${U.esc(Galaxy.starRec(id).name)}</b><small>${U.si(pw.demand, 'W')} / ${U.si(pw.supply, 'W')}${isFinite(pct) ? ' · ' + pct.toFixed(0) + ' %' : ''}</small></div>`;
      h += `<div class="bar"><i style="width:${Math.min(100, pct)}%;background:${pct > 100 ? '#ff7b5c' : pct > 85 ? '#ffd36b' : '#6fdc8c'}"></i></div>`;
      h += `<div class="pt-sec pos">▲ ${t('ui.sources')}</div>`;
      for (const o of pw.src) {
        const nm = o.t === 'dyson' ? t('ui.dyson') + ' (' + t('b.receiver') + ' ×' + o.n + ')' : t('b.' + o.t) + (o.t !== 'hq' ? ' ×' + o.n : '');
        const where = o.t === 'dyson' || o.t === 'hq' ? '' : ' · ' + U.esc(bname(o.body));
        h += `<div class="pt-row"><span>${o.t === 'dyson' ? '◎' : BUILDINGS[o.t].icon} ${nm}<small>${where}</small></span><b>${U.si(o.w, 'W')}</b></div>`;
      }
      if (pw.noFuel) h += `<div class="pt-row warn small">${t('ui.noFuel')}</div>`;
      const unused = pw.dyson.watts - pw.dysonUsed;
      if (unused > 1) h += `<div class="pt-row dim small"><span>☀ ${t('ui.dysonUnused')}</span><b>${U.si(unused, 'W')}</b></div>`;
      h += `<div class="pt-sec neg">▼ ${t('ui.consumers')}${pw.sat < 0.99 ? ' · ' + t('ui.satisfaction') + ' ' + (pw.sat * 100).toFixed(0) + ' %' : ''}</div>`;
      if (!pw.cons.length) h += `<div class="pt-row dim small">${t('ui.none')}</div>`;
      for (const o of pw.cons) h += `<div class="pt-row"><span>${BUILDINGS[o.t].icon} ${t('b.' + o.t)} ×${o.n}</span><b>${U.si(o.w, 'W')}</b></div>`;
    }
    h += `<div class="pt-foot dim small">${t('ui.powerFoot', U.si(G.totalPower, 'W'))}</div>`;
    return h;
  },

  renderQuestCard() {
    const S = Game.s, el = this.$('questCard');
    if (S.sandbox) { el.classList.remove('show'); return; }
    const L = I18N.lang === 'cs' ? 0 : 1, t = I18N.t.bind(I18N);
    const qs = Quests.active(1);
    let h = '';
    if (qs.length) {
      h = `<div class="qh">🎯 ${t('ui.quests')} <small>${S.qDone.length}/${QUESTS.length}</small></div>`;
      for (const q of qs) h += `<div class="qi"><b>${q.t[L]}</b><div class="small">${q.d[L]}</div>
        ${Object.keys(q.reward).length ? `<div class="small rw">🎁 ${Quests.rewardText(q.reward)}</div>` : ''}
        ${q.focus ? `<button data-act="qfocus" data-f="${q.focus}">${t('ui.showMe')}</button>` : ''}</div>`;
    }
    el.classList.toggle('show', !!h);
    if (h !== this.lastQuest) { el.innerHTML = h; this.lastQuest = h; }
  },

  renderScale() {
    const z = Main.cam.z, dpr = Renderer.dpr;
    // délka měřítka ~120 CSS px, zaokrouhlená na 1-2-5
    const kmPer120 = z * 120 * dpr;
    const units = [[1e-3, 'm', 1e3], [1, 'km', 1], [C.KM_PER_AU, 'AU', 1 / C.KM_PER_AU], [C.KM_PER_LY, I18N.t('u.ly'), 1 / C.KM_PER_LY], [C.KM_PER_LY * 1e3, I18N.t('u.kly'), 1 / C.KM_PER_LY / 1e3], [C.KM_PER_LY * 1e6, I18N.t('u.mly'), 1 / C.KM_PER_LY / 1e6], [C.KM_PER_LY * 1e9, I18N.t('u.gly'), 1 / C.KM_PER_LY / 1e9]];
    let u = units[0];
    for (const uu of units) if (kmPer120 >= uu[0] * 0.5) u = uu;
    if (u[1] === 'km' && kmPer120 > 1e7) u = units[2];
    const v = kmPer120 * u[2];
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const nice = [1, 2, 5, 10].map(m => m * p).filter(m => m <= v).pop() || p;
    const px = nice / u[2] / z / dpr;
    this.$('scale').innerHTML = `<i style="width:${px}px"></i><span>${U.num(nice)} ${u[1]}</span>`;
    const empty = Main.emptiness;
    const el = this.$('empty');
    if (empty) { el.textContent = I18N.t('ui.empty', U.dist(empty)); el.classList.add('show'); }
    else el.classList.remove('show');
  },
};

// ---------- vyhledávání hvězd, planet a galaxií ----------
const SEARCH_ALIASES = {
  'Alfa Centauri': 'Rigil Kentaurus', 'Alpha Centauri': 'Rigil Kentaurus', 'Polárka': 'Polaris', 'Barnardova šipka': "Barnard's Star",
  'Epsilon Eridani': 'Ran', 'Tau Ceti': 'Tau Cet', 'Sluneční soustava': 'Slunce', 'Sun': 'Slunce', 'Sol': 'Slunce',
};
const Search = {
  idx: [], hits: [], sel: 0,
  norm(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); },
  init() {
    const G = Galaxy, idx = this.idx;
    const add = (label, kind, ref) => idx.push({ label, n: this.norm(label), kind, ref });
    for (let i = 0; i < G.n; i++) {
      const nm = G.names[i];
      if (!nm || (G.primary[i] >= 0 && !G.extra[i])) continue;
      if (/^Gl |^GJ |^NN |^Wo /.test(nm)) continue;
      add(nm, G.extra[i] ? G.extra[i].kind : 'star', { type: 'star', id: 'h' + i, key: 'h' + i });
    }
    for (const [a, target] of Object.entries(SEARCH_ALIASES)) {
      const i = target === 'Slunce' ? G.solIndex : G.names.indexOf(target);
      if (i >= 0) add(a, 'star', { type: 'star', id: 'h' + i, key: 'h' + i });
    }
    for (const g of G.galaxies) for (const nm of new Set(g.name)) add(nm, 'galaxy', { type: 'galaxy', g, key: 'g' + g.name[1] });
    const sol = G.system('h' + G.solIndex);
    for (const b of sol.bodies) for (const nm of new Set(Array.isArray(b.name) ? b.name : [b.name])) add(nm, 'body', { type: 'body', body: b, key: b.id });
    for (const [star, list] of Object.entries(KNOWN_EXOPLANETS)) {
      const i = G.names.indexOf(star);
      if (i >= 0) for (const p of list) add(p.n, 'planet', { type: 'star', id: 'h' + i, key: 'h' + i });
    }
    const inp = document.getElementById('search'), box = document.getElementById('searchRes');
    inp.addEventListener('input', () => this.find(inp.value));
    inp.addEventListener('focus', () => this.find(inp.value));
    inp.addEventListener('blur', () => setTimeout(() => box.classList.remove('show'), 150));
    inp.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { this.sel = Math.min(this.sel + 1, this.hits.length - 1); this.draw(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { this.sel = Math.max(this.sel - 1, 0); this.draw(); e.preventDefault(); }
      else if (e.key === 'Enter') this.pick(this.sel);
      else if (e.key === 'Escape') inp.blur();
    });
    window.addEventListener('keydown', e => {
      if ((e.key === '/' || (e.ctrlKey && e.key === 'f')) && document.activeElement !== inp) { e.preventDefault(); inp.focus(); inp.select(); }
    });
  },
  find(q) {
    const n = this.norm(q.trim());
    this.sel = 0;
    if (!n) { this.hits = []; this.draw(); return; }
    const pre = [], mid = [];
    for (const e of this.idx) {
      if (e.n.startsWith(n)) pre.push(e); else if (e.n.includes(n)) mid.push(e);
      if (pre.length > 40) break;
    }
    const rank = e => (e.kind === 'body' ? 0 : e.kind === 'star' ? 2 : 1) + e.label.length / 100;
    pre.sort((a, b) => rank(a) - rank(b)); mid.sort((a, b) => rank(a) - rank(b));
    this.hits = [...pre, ...mid].slice(0, 12);
    this.draw();
  },
  draw() {
    const box = document.getElementById('searchRes');
    const icon = { star: '✦', ns: '✺', bh: '●', galaxy: '🌀', body: '◍', planet: '◍' };
    box.innerHTML = this.hits.map((e, i) => `<div class="sr ${i === this.sel ? 'on' : ''}" data-act="search" data-i="${i}"><span>${icon[e.kind] || '·'}</span>${U.esc(e.label)}<small>${I18N.t('sk.' + e.kind)}</small></div>`).join('')
      || (document.getElementById('search').value ? `<div class="sr dim">${I18N.t('ui.noResults')}</div>` : '');
    box.classList.toggle('show', !!box.innerHTML);
  },
  pick(i) {
    const e = this.hits[i];
    if (!e) return;
    Main.select(e.ref); Main.flyToSel();
    const inp = document.getElementById('search');
    inp.value = ''; inp.blur();
    this.hits = []; this.draw();
  },
};
