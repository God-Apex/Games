// Úkoly (průvodce hrou s odměnami) a příručka: odkud se která surovina bere a k čemu slouží.
'use strict';

// focus: kam „Ukaž mi“ zavede: klíč tělesa ve Sluneční soustavě, 'tab:…' nebo 'star:Jméno'
// check(G): splněno? reward: suroviny, rp (výzkum), am (antihmota v kg)
const QUESTS = [
  { id: 'mine_moon', focus: 'moon', reward: { plate: 100, circuit: 40 }, check: G => G.count('mine', 'moon') > 0,
    t: ['První důl', 'First mine'],
    d: ['Klikni na Měsíc a v panelu vlevo postav Důl. Na Měsíci je křemík, titan, železo a helium-3.', 'Click the Moon and build a Mine in the left panel. The Moon has silicon, titanium, iron and helium-3.'] },
  { id: 'plates', focus: 'earth', reward: { fe: 300 }, check: G => G.count('assembler', null, 'plate') > 0,
    t: ['Železné pláty', 'Iron plates'],
    d: ['Na Zemi postav Továrnu a v rozbalovacím seznamu vyber Železné pláty (2 železná ruda → 1 plát). Pláty potřebuje skoro každá stavba.', 'On Earth build a Factory and pick Iron plates in the list (2 iron ore → 1 plate). Almost every building needs plates.'] },
  { id: 'wire', focus: 'earth', reward: { cu: 200 }, check: G => G.count('assembler', null, 'wire') > 0,
    t: ['Měděné dráty', 'Copper wire'],
    d: ['Postav Továrnu na Měděné dráty (1 měděná ruda → 2 dráty). Dráty jsou potřeba na obvody.', 'Build a Factory making Copper wire (1 copper ore → 2 wires). Wire is needed for circuits.'] },
  { id: 'circuit', focus: 'earth', reward: { circuit: 60 }, check: G => G.count('assembler', null, 'circuit') > 0,
    t: ['Obvody', 'Circuits'],
    d: ['Obvody = 1 plát + 3 dráty + 1 křemík. Postav Továrnu na obvody. Bez nich nepostavíš doly ani laboratoře.', 'Circuits = 1 plate + 3 wire + 1 silicon. Build a Factory making circuits. Mines and labs need them.'] },
  { id: 'lab', focus: 'earth', reward: { circuit: 60 }, check: G => G.count('lab') > 0,
    t: ['Laboratoř', 'Laboratory'],
    d: ['Laboratoř mění obvody na body výzkumu (2 obvody/h → 10 bodů/h).', 'A Laboratory turns circuits into research (2 circuits/h → 10 points/h).'] },
  { id: 'research', focus: 'tab:research', reward: { rp: 30 }, check: G => !!G.s.research || G.has('fusion'),
    t: ['Začni zkoumat', 'Start research'],
    d: ['Otevři záložku Výzkum vpravo a spusť Fúzní energii.', 'Open the Research tab on the right and start Fusion power.'] },
  { id: 'solar', focus: 'mercury', reward: { plate: 150, wire: 150 }, check: G => G.count('solar') > 0,
    t: ['Sluneční energie', 'Solar power'],
    d: ['Každá stavba bere energii. Postav Solární prstenec na Merkuru: blízko Slunce je záření 6,7× silnější než u Země.', 'Every building uses power. Build a Solar ring on Mercury: sunlight there is 6.7× stronger than at Earth.'] },
  { id: 'belt', focus: 'belt', reward: { plate: 200 }, check: G => G.count('mine', 'belt') > 0,
    t: ['Pás asteroidů', 'Asteroid belt'],
    d: ['Pás asteroidů má nejvíc kovů: železo, měď, titan a led. Postav tam důl.', 'The asteroid belt is richest in metals: iron, copper, titanium and ice. Build a mine there.'] },
  { id: 'alloy', focus: 'earth', reward: { ti: 300 }, check: G => G.count('assembler', null, 'alloy') > 0,
    t: ['Titanová slitina', 'Titanium alloy'],
    d: ['Slitina = 2 titan + 1 plát. Postav Továrnu na slitinu. Titan těží doly na Měsíci a v pásu asteroidů.', 'Alloy = 2 titanium + 1 plate. Build a Factory making alloy. Titanium comes from mines on the Moon and in the belt.'] },
  { id: 'fusion_done', focus: 'tab:research', reward: { alloy: 60 }, check: G => G.has('fusion'),
    t: ['Fúze', 'Fusion'],
    d: ['Dokonči výzkum Fúzní energie. Víc laboratoří a obvodů = rychlejší výzkum.', 'Finish Fusion power research. More labs and circuits = faster research.'] },
  { id: 'europa', focus: 'europa', reward: { ice: 200 }, check: G => G.count('mine', 'europa') + G.count('mine', 'ganymede') + G.count('mine', 'ceres') > 0,
    t: ['Led', 'Ice'],
    d: ['Supravodiče se chladí ledem. Postav důl na Europě (nebo na Ganymedu či Ceres).', 'Superconductors are cooled with ice. Build a mine on Europa (or Ganymede or Ceres).'] },
  { id: 'supercond', focus: 'earth', reward: { supercond: 30 }, check: G => G.count('assembler', null, 'supercond') > 0,
    t: ['Supravodiče', 'Superconductors'],
    d: ['Supravodič = 2 dráty + 1 slitina + 1 led. Postav na ně Továrnu.', 'Superconductor = 2 wire + 1 alloy + 1 ice. Build a Factory for them.'] },
  { id: 'processor', focus: 'earth', reward: { processor: 20 }, check: G => G.count('assembler', null, 'processor') > 0,
    t: ['Procesory', 'Processors'],
    d: ['Procesor = 2 obvody + 2 křemík. Postav na ně Továrnu.', 'Processor = 2 circuits + 2 silicon. Build a Factory for them.'] },
  { id: 'gas', focus: 'jupiter', reward: { he3: 100 }, check: G => G.count('gas') > 0,
    t: ['Helium-3', 'Helium-3'],
    d: ['Palivo pro fúzi se těží z plynných obrů. Postav Plynovou těžbu na Jupiteru.', 'Fusion fuel comes from gas giants. Build a Gas harvester on Jupiter.'] },
  { id: 'fusion_plant', focus: 'moon', reward: { alloy: 100 }, check: G => G.count('fusion') > 0,
    t: ['Fúzní elektrárna', 'Fusion plant'],
    d: ['Postav Fúzní elektrárnu (100 TW, spaluje 1 helium-3 za hodinu).', 'Build a Fusion plant (100 TW, burns 1 helium-3 per hour).'] },
  { id: 'dyson_tech', focus: 'tab:research', reward: { rp: 100 }, check: G => G.has('dyson'),
    t: ['Dysonův roj', 'Dyson swarm'],
    d: ['Vyzkoumej Dysonův roj. Otevře solární plachty, katapulty a přijímače.', 'Research the Dyson swarm. It unlocks solar sails, ejectors and receivers.'] },
  { id: 'sails', focus: 'mercury', reward: { sail: 200 }, check: G => G.s.net.some(id => G.s.sys[id] && G.s.sys[id].sails >= 100),
    t: ['Roj kolem Slunce', 'Swarm around the Sun'],
    d: ['Postav Továrnu na Solární plachty a Elektromagnetický katapult (třeba na Merkuru). Vypusť 100 plachet.', 'Build a Factory making Solar sails and an EM rail ejector (e.g. on Mercury). Launch 100 sails.'] },
  { id: 'receiver', focus: 'mercury', reward: { processor: 40 }, check: G => G.count('receiver') > 0,
    t: ['Přijímač paprsku', 'Ray receiver'],
    d: ['Bez Přijímače paprsku je energie roje nevyužitá. Postav ho.', 'Without a Ray receiver the swarm energy is wasted. Build one.'] },
  { id: 'k1', focus: null, reward: { frame: 50 }, check: G => U.kardashev(G.totalPower) >= 1,
    t: ['Typ I', 'Type I'],
    d: ['Dosáhni stupně 1,0 na Kardaševově škále (10 PW).', 'Reach 1.0 on the Kardashev scale (10 PW).'] },
  { id: 'trap', focus: 'moon', reward: { supercond: 50 }, check: G => G.count('trap') > 0,
    t: ['Past na antihmotu', 'Antimatter trap'],
    d: ['Vyzkoumej Magnetické pasti a postav Penningovu past. Bez pasti se antihmota nedá skladovat.', 'Research Magnetic traps and build a Penning trap. Antimatter cannot be stored without one.'] },
  { id: 'collector', focus: 'jupiter', reward: { processor: 40 }, check: G => G.count('collector') > 0,
    t: ['Sběr antihmoty', 'Antimatter harvest'],
    d: ['Postav Magnetosférický sběrač u Jupiteru. Sbírá antiprotony zachycené v radiačních pásech.', 'Build a Magnetospheric collector at Jupiter. It harvests antiprotons trapped in the radiation belts.'] },
  { id: 'am50', focus: null, reward: { frame: 100 }, check: G => G.s.am >= 0.05,
    t: ['50 gramů', '50 grams'],
    d: ['Nasbírej 50 g antihmoty. S hmotou by anihilovala na 9·10¹⁵ J, asi 140 Hirošim.', 'Collect 50 g of antimatter. Annihilating with matter it would release 9·10¹⁵ J, about 140 Hiroshimas.'] },
  { id: 'dock', focus: 'earth', reward: { frame: 50, processor: 50 }, check: G => G.count('dock') > 0 && G.count('gate') > 0,
    t: ['Brána ke hvězdám', 'Gate to the stars'],
    d: ['Vyzkoumej Mezihvězdné lety. Postav Mezihvězdný dok a Bránu červí díry (ta se staví na Orbitální stanici).', 'Research Interstellar flight. Build an Interstellar dock and a Wormhole gate (the gate goes on the Orbital station).'] },
  { id: 'probe', focus: 'star:Proxima Centauri', reward: { rp: 300 }, check: G => G.s.probes.length > 0 || G.s.explored.length > 1,
    t: ['Sonda', 'Probe'],
    d: ['Vyber hvězdu (nejblíž je Proxima Centauri, 4,2 ly) a vyšli k ní sondu.', 'Select a star (the nearest is Proxima Centauri, 4.2 ly) and send a probe.'] },
  { id: 'wormhole', focus: 'tab:empire', reward: { am: 0.05 }, check: G => G.s.net.length > 1,
    t: ['Červí díra', 'Wormhole'],
    d: ['Až sonda doletí, vyber cílovou hvězdu a otevři červí díru antihmotou.', 'When the probe arrives, select the target star and open the wormhole with antimatter.'] },
  { id: 'shell', focus: 'tab:research', reward: { rocket: 100 }, check: G => G.s.net.some(id => G.s.sys[id] && G.s.sys[id].nodes >= 100),
    t: ['Dysonova sféra', 'Dyson sphere'],
    d: ['Vyzkoumej Dysonovu sféru, vyráběj rakety a vynes raketovým silem 100 uzlů sféry.', 'Research the Dyson sphere, build rockets and launch 100 sphere nodes with a rocket silo.'] },
  { id: 'k2', focus: null, reward: { am: 0.5 }, check: G => U.kardashev(G.totalPower) >= 2,
    t: ['Typ II', 'Type II'],
    d: ['Dosáhni stupně 2,0: ovládáš energii celé hvězdy.', 'Reach 2.0: you command the power of an entire star.'] },
  { id: 'exotic', focus: null, reward: { am: 2 }, check: G => G.s.net.some(id => { const s = Galaxy.starRec(id); return s && (s.kind === 'ns' || s.kind === 'bh'); }),
    t: ['Exotika', 'Exotica'],
    d: ['Připoj k síti neutronovou hvězdu nebo černou díru. Nejbližší je RX J1856.5−3754 (400 ly).', 'Connect a neutron star or black hole to the network. The nearest is RX J1856.5−3754 (400 ly).'] },
  { id: 'k3', focus: null, reward: {}, check: G => U.kardashev(G.totalPower) >= 3,
    t: ['Galaktická civilizace', 'Galactic civilization'],
    d: ['Typ III: energie celé galaxie. Cesta je nekonečná.', 'Type III: the energy of an entire galaxy. The road is endless.'] },
];

const Quests = {
  L() { return I18N.lang === 'cs' ? 0 : 1; },
  active(n = 2) { return QUESTS.filter(q => !Game.s.qDone.includes(q.id)).slice(0, n); },
  check() {
    const G = Game;
    if (!G.s || G.s.sandbox) return;
    for (const q of QUESTS) {
      if (G.s.qDone.includes(q.id) || !q.check(G)) continue;
      G.s.qDone.push(q.id);
      for (const r in q.reward) {
        if (r === 'rp') G.s.rp += q.reward[r];
        else if (r === 'am') G.s.am += q.reward[r];   // bez pastí se při dalším tiku ztratí
        else G.s.store[r] = (G.s.store[r] || 0) + q.reward[r];
      }
      G.log('ev.quest', [q.t[this.L()], this.rewardText(q.reward)]);
    }
  },
  rewardText(rw) {
    return Object.entries(rw).map(([r, v]) => r === 'am' ? U.mass(v) + ' ' + I18N.t('res.am') : r === 'rp' ? v + ' RP' : v + ' ' + I18N.t('res.' + r)).join(', ');
  },
  focus(f) {
    if (!f) return;
    if (f.startsWith('tab:')) return UI.setTab(f.slice(4));
    if (f.startsWith('star:')) { const i = Galaxy.names.indexOf(f.slice(5)); if (i >= 0) { Main.select({ type: 'star', id: 'h' + i, key: 'h' + i }); Main.flyToSel(); } return; }
    const b = Main.findBody('h' + Galaxy.solIndex, f);
    if (b) { Main.select({ type: 'body', body: b, key: b.id }); Main.flyToSel(); }
  },
};

// ---------- příručka: generuje se z dat ekonomiky ----------
const Guide = {
  // tělesa Sluneční soustavy s ložiskem suroviny, setříděná podle bohatosti
  sources(r) {
    const sys = Galaxy.system('h' + Galaxy.solIndex);
    return sys.bodies.filter(b => b.dep[r]).sort((a, b) => b.dep[r] - a.dep[r]);
  },
  resource(r) {
    const t = I18N.t.bind(I18N), L = I18N.lang === 'cs' ? 0 : 1;
    let h = `<h3><i class="dot" style="background:${RES_COLOR[r] || '#d58cff'}"></i>${t('res.' + r)}</h3>`;
    h += `<div class="gsec">${t('g.get')}</div>`;
    if (r === 'am') {
      h += `<p class="small">${t('g.am')}</p>`;
    } else if (RAW.includes(r)) {
      const how = r === 'h2' || r === 'he3' ? t('g.gas') : t('g.mine');
      h += `<p class="small">${how}</p><div class="bodies">` + this.sources(r).map(b =>
        `<button data-act="guideBody" data-k="${b.id.split(':').pop()}">${U.esc(Galaxy.bodyName(b))} <small>${'●'.repeat(Math.max(1, Math.round(b.dep[r] * 2)))}</small></button>`).join('') + '</div>';
    } else if (RECIPES[r]) {
      const rc = RECIPES[r];
      h += `<p class="small">${t('g.factory')}${rc.tech ? ' · ' + t('ui.req') + ': ' + t('tech.' + rc.tech) : ''}</p>`;
      h += `<div class="recipe">${Object.entries(rc.in).map(([x, v]) => this.chip(x, v)).join(' + ')} → ${Object.entries(rc.out).map(([x, v]) => this.chip(x, v)).join('')}</div>`;
      h += `<p class="dim small">${t('g.rate', rc.rate)}</p>`;
    }
    const usedR = Object.entries(RECIPES).filter(([k, rc]) => rc.in[r]).map(([k]) => this.chip(k));
    const usedB = BUILD_ORDER.filter(k => BUILDINGS[k].cost[r]).map(k => `<span class="bchip" title="${U.esc(t('bd.' + k))}">${BUILDINGS[k].icon} ${t('b.' + k)}</span>`);
    if (usedR.length || usedB.length || r === 'am') {
      h += `<div class="gsec">${t('g.use')}</div>`;
      if (usedR.length) h += `<p class="small">${t('g.inRecipes')}: ${usedR.join(' ')}</p>`;
      if (usedB.length) h += `<p class="small">${t('g.inBuildings')}: ${usedB.join(' ')}</p>`;
      if (ECO.PROBE_COST[r]) h += `<p class="small">🛰 ${t('g.probe')}</p>`;
      if (r === 'am') h += `<p class="small">${t('g.amUse')}</p>`;
    }
    return h;
  },
  chip(r, v) { return `<a class="rchip" data-act="guide" data-r="${r}"><i style="background:${RES_COLOR[r]}"></i>${v != null ? v + '× ' : ''}${I18N.t('res.' + r)}</a>`; },
  render(sel) {
    const t = I18N.t.bind(I18N);
    let h = `<p class="dim small">${t('g.intro')}</p><div class="gl">`;
    for (const r of [...RES, 'am']) h += `<a class="rchip ${r === sel ? 'on' : ''}" data-act="guide" data-r="${r}"><i style="background:${RES_COLOR[r] || '#d58cff'}"></i>${t('res.' + r)}</a>`;
    h += '</div>';
    if (sel) h += this.resource(sel);
    h += `<div class="gsec">${t('g.chain')}</div><p class="small chain">${t('g.chainText')}</p>`;
    return h;
  },
};
