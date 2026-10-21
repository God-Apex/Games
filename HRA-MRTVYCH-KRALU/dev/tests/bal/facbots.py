"""Faction bots for the balance harness (FAC 8, SPEC 6 M3-G): decks per role, the FacMixin rules on top of the harness
bots, the faction-only strategies and the scenario builders used by facrun.py.

A faction side is a scenario side dict  {'bot': 'turtle'|'mixed'|'att', 'fac': 'prez', 'deck': <role or list>, ...}.
harness.make_bot() gives a side whose faction is not 'bez' the matching Fac* class (H.FAC_BOTS); bez sides keep the plain
harness bots, so bez-bez games play exactly as before (apart from the 1.0 global rules).
Every faction rule fires only if its card is in the deck (or is the card an ablation replaces, cfg['ablate']).
Roles in FAC_DECKS: def att mix att_sn spam (FAC 8) plus my duel (all 3 own cards, used by `matrix` and `ablate`) and
flood (kult only).

Deviations from FAC 8 (found by the first smoke runs, all so that every faction card is really played, A9):
- Tlupa (kult) is thrown only while the plan is not waiting for energy (FacMixin.plan_state) and, for attackers, with a push on
  the field (push_on); the literal "whenever off cooldown and 60 spare" starved the plan (no towers, no push).
- EMP (korp) also fires at one visible attack tower when >= 5 own units are near, and at >= 3 visible enemy units in the own half
  (attackers and defenders); two visible towers are almost never seen, the push dies at the wall.
- first_unit(): an attacker buys its tech unit (Exoskelet from Doba II, Nekromant) once as soon as it is available.
"""
import harness as H
import run as R

S, D, FM = H.S, H.D, H.FM
mine, real_x, local_x, ROW_ORDER = H.mine, H.real_x, H.local_x, H.ROW_ORDER
ATTACKS = frozenset(D.ATTACK_TOWERS)
FACS = ('bez', 'prez', 'korp', 'kult')
QT = None                                    # cfg q_timeout (s) for the Attacker queue; None = off, bez parity with run.py

FAC_DECKS = {
    'bez': {'def': H.DEF_DECK, 'att': H.ATT_DECK_D2, 'mix': H.MIX_DECK, 'att_sn': H.ATT_DECK_SN, 'spam': H.ATT_DECK,
            'duel': H.DEF_DECK},
    'prez': {'def': ['sniper', 'hlaska', 'kulomet', 'plamen', 'ostnata', 'dilna', 'pesak', 'obrnenec'],
             'att': ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'mrchozrout', 'dilna', 'nalet'],
             'mix': ['kulomet', 'plamen', 'sniper', 'hlaska', 'ostnata', 'dilna', 'obrnenec', 'mrchozrout'],
             'att_sn': ['sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'mrchozrout', 'medik', 'nalet'],
             'spam': ['kulomet', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'strelec', 'medik', 'mrchozrout'],
             'duel': ['sniper', 'hlaska', 'kulomet', 'pesak', 'obrnenec', 'ostnata', 'dilna', 'mrchozrout']},
    'korp': {'def': ['sniper', 'hlaska', 'kulomet', 'tesla', 'hangar', 'emp', 'pesak', 'obrnenec'],
             'att': ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'exo', 'emp', 'vypadek'],
             'mix': ['kulomet', 'tesla', 'sniper', 'hlaska', 'hangar', 'pesak', 'obrnenec', 'emp'],
             'att_sn': ['sniper', 'hlaska', 'pesak', 'obrnenec', 'exo', 'medik', 'emp', 'nalet'],
             'spam': ['kulomet', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'strelec', 'medik', 'exo'],
             'duel': ['sniper', 'hlaska', 'kulomet', 'pesak', 'obrnenec', 'hangar', 'exo', 'emp']},
    'kult': {'def': ['sniper', 'hlaska', 'kulomet', 'plamen', 'hnizdo', 'pesak', 'obrnenec', 'mor'],
             'att': ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'nekromant', 'hnizdo', 'mor'],
             'mix': ['kulomet', 'plamen', 'sniper', 'hlaska', 'hnizdo', 'pesak', 'obrnenec', 'mor'],
             'att_sn': ['sniper', 'hlaska', 'pesak', 'obrnenec', 'nekromant', 'medik', 'mor', 'nalet'],
             'spam': ['kulomet', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'medik', 'nekromant', 'hnizdo'],
             'duel': ['sniper', 'hlaska', 'kulomet', 'pesak', 'obrnenec', 'hnizdo', 'nekromant', 'mor'],
             'flood': ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'nekromant', 'hnizdo', 'mor']},
}
H.FAC_DECKS.update(FAC_DECKS)

# Army compositions (attackers). 'korp' and 'kult' are the FAC 8 comps; the others give the own unit card a place.
COMPS = {
    'prez': ['obrnenec', 'pesak', 'mrchozrout', 'obrnenec', 'pesak', 'mrchozrout'],
    'korp': ['obrnenec', 'pesak', 'exo', 'pesak', 'medik', 'pesak'],
    'kult': ['obrnenec', 'pesak', 'nekromant', 'pesak', 'obrnenec', 'pesak'],
    'inf_prez': ['pesak', 'pesak', 'mrchozrout', 'medik', 'pesak', 'mrchozrout', 'strelec', 'pesak'],
    'inf_korp': ['pesak', 'pesak', 'exo', 'medik', 'pesak', 'pesak', 'strelec', 'pesak'],
    'inf_kult': ['pesak', 'pesak', 'nekromant', 'medik', 'pesak', 'pesak', 'strelec', 'pesak'],
}
H.COMPS.update(COMPS)
H.COMPS.setdefault('duel', ['obrnenec', 'pesak', 'pesak', 'obrnenec', 'pesak', 'pesak'])
ATT_COMP = {'bez': 'mix2', 'prez': 'mix2', 'korp': 'korp', 'kult': 'kult'}
DUEL_COMP = {'bez': 'duel', 'prez': 'prez', 'korp': 'korp', 'kult': 'kult'}
SPAM_COMP = {'bez': 'inf', 'prez': 'inf_prez', 'korp': 'inf_korp', 'kult': 'inf_kult'}

# ablate: the faction card and the nearest shared card that replaces it (FAC 8). zed and gen are base-kit buildings,
# the others are deck cards; a replacement already in the deck is swapped for a filler card.
ABLATE = {'ostnata': 'zed', 'dilna': 'gen', 'mrchozrout': 'pesak', 'hangar': 'kulomet', 'exo': 'obrnenec', 'emp': 'vypadek',
          'hnizdo': 'rusicka', 'nekromant': 'medik', 'mor': 'nalet'}
CARD_FAC = {'ostnata': 'prez', 'dilna': 'prez', 'mrchozrout': 'prez', 'hangar': 'korp', 'exo': 'korp', 'emp': 'korp',
            'hnizdo': 'kult', 'nekromant': 'kult', 'mor': 'kult'}
FILLER = ['plamen', 'nalet', 'vypadek', 'jezdec', 'strelec', 'medik']


# ---------------------------------------------------------------- the mixin
class FacMixin:
    """Faction rules on top of a harness bot: extra plan steps built into self.steps (plan_<fac>) and the per-tick rules
    of fac_tick(), called at the start of every tick. Rules fire only if the card is in the deck."""

    def __init__(self, g, s, cfg):
        super().__init__(g, s, cfg)
        self.fac = cfg.get('fac', 'bez')
        self.abl = cfg.get('ablate')
        self.deckset = set(g.sd[s].deck)
        self.attacker = isinstance(self, H.Attacker)
        self.n_gen = cfg.get('n_gen', 5)
        self.plan_state = 'wait'                     # result of the last run_steps: 'wait' = saving for the next item
        # cells the plan already uses (the faction wall must not take them); the Zeď wall is replaced by the faction wall
        self.reserved = set((lx, y) for st in self.steps for (k, lx, y) in getattr(st, 'items', ()) if k != 'zed')
        if self.fac == 'prez':
            self.kmode = 'repair'                    # Kovář: the King always repairs
        plan = getattr(self, 'plan_' + self.fac, None)
        if plan:
            plan()

    # ------------------------------------------------ plan helpers
    def has(self, card):
        return card in self.deckset or self.abl == card

    def kind(self, card):
        return ABLATE[card] if self.abl == card else card

    def _at(self, pred):
        for i, st in enumerate(self.steps):
            if pred(getattr(st, 'tag', None)):
                return i
        return None

    def after_gens(self, n, *steps):
        i = self._at(lambda t: t == ('gens', n))
        i = len(self.steps) if i is None else i + 1
        self.steps[i:i] = steps

    def before_gens(self, n, *steps):
        i = self._at(lambda t: t == ('gens', n))
        i = len(self.steps) if i is None else i
        self.steps[i:i] = steps

    def after_block(self, *steps):
        """Defenders: after the first tower block. Attackers (whose block is the whole sniper column): after the economy."""
        if self.attacker:
            return self.after_gens(self.n_gen, *steps)
        i = self._at(lambda t: t and t[0] == 'layout' and t[1] & ATTACKS)
        i = len(self.steps) if i is None else i + 1
        self.steps[i:i] = steps

    def s_when_gens(self, n, inner):
        def f():
            return inner() if len(mine(self.g, self.s, 'gen')) >= n else 'done'
        return f

    def s_build(self, card, cells, n=None, wait=True, conv=False):
        """Build `card` on the first free of `cells` ((local x, y) pairs). n = how many may stand on the cells (rebuilt when
        lost), wait = save energy when too poor ('wait'), conv = pay a missing scrap with Přetavení when energy is spare."""
        def f():
            g, s = self.g, self.s
            if not self.has(card):
                return 'done'
            kind = self.kind(card)
            if n is not None:
                have = 0
                for lx, y in cells:
                    b = g.bld[y][real_x(s, lx)]
                    if b is not None and b.side == s and b.kind == kind:
                        have += 1
                if have >= n:
                    return 'done'
            for lx, y in cells:
                x = real_x(s, lx)
                if g.ter[y][x] != '.' or not g.buildable(s, x) or g.bld[y][x] is not None:
                    continue
                r = H.try_build(g, s, kind, lx, y)
                if r == 'ok':
                    return 'did'
                if r == 'poor':
                    if conv:
                        self.convert_for(kind)
                    return 'wait' if wait else 'done'
            return 'done'
        return f

    def convert_for(self, kind):
        g, s = self.g, self.s
        sd = g.sd[s]
        c = H.build_cost(g, s, kind)
        if c[1] > sd.s and sd.doba >= D.CONV[2] and sd.e >= c[0] + D.CONV[0] + 20:
            g.act(s, {'t': 'conv'})

    def s_wallup(self):
        """Ostnatá zeď to level 3 whenever 60 or more scrap are in stock."""
        def f():
            g, s = self.g, self.s
            if g.sd[s].s < 60:
                return 'done'
            ws = sorted((e for e in mine(g, s, 'ostnata') if e.lvl < 3), key=lambda e: e.lvl)
            if ws:
                H.try_upgrade(g, s, ws[0])
                return 'did'
            return 'done'
        return f

    # ------------------------------------------------ plans (built into self.steps)
    def plan_prez(self):
        wc = self.cfg.get('wall_cols', (3,))
        wr = self.cfg.get('wall_rows', (4, 3, 5, 2, 6))
        cells = [(c, y) for c in wc for y in wr if (c, y) not in self.reserved]
        if self.has('ostnata'):
            self.after_block(self.s_build('ostnata', cells, wait=False, conv=True), self.s_wallup())
        if self.has('dilna'):
            self.after_gens(3, self.s_build('dilna', [(0, 1)], n=1))
            self.after_gens(self.n_gen, self.s_when_gens(5, self.s_build('dilna', [(0, 7)], n=1)))
            if self.abl != 'dilna':
                self.steps.append(self.s_upg(('dilna',), 3, 'A', block=False))

    def plan_korp(self):
        blk = []
        if self.has('tesla'):
            blk.append(self.s_build('tesla', [(3, 3), (3, 5)], n=2))
        if self.has('hangar'):
            blk.append(self.s_build('hangar', [(3, 6), (3, 4), (3, 3), (3, 5)], n=1))
        if blk:
            self.after_block(*blk)
        if 'tesla' in self.deckset:
            self.steps.append(self.s_upg(('tesla',), 3, 'A', block=False))
        if 'hangar' in self.deckset:
            self.steps.append(self.s_upg(('hangar',), 3, 'B', block=False))

    def plan_kult(self):
        if self.has('hnizdo'):
            path = self.cfg.get('nest_path', 'A')
            self.before_gens(self.n_gen, self.s_when_gens(4, self.s_build('hnizdo', [(0, 1), (0, 7)], n=2)))
            if self.abl != 'hnizdo':
                self.steps.append(self.s_upg(('hnizdo',), 3, path, block=False))

    # ------------------------------------------------ per tick
    def run_steps(self, steps):
        r = super().run_steps(steps)
        self.plan_state = r
        return r

    def tick(self):
        self.fac_tick()
        super().tick()

    def fac_tick(self):
        if self.attacker:
            self.first_unit()
        if self.fac == 'korp':
            self.korp_emp()
        elif self.fac == 'kult':
            self.kult_tick()

    def first_unit(self):
        """An attacker buys the faction's tech unit (Exoskelet from Doba II, Nekromant) once as soon as it is available and
        affordable, ahead of the push: an attacker that is held back by rebuilding its defence (or loses early) would never
        push and so never try its card. Later copies come with the pushes (comp)."""
        g, s = self.g, self.s
        sd = g.sd[s]
        if g.t < 120 or self.cfg.get('no_units'):
            return
        for card in ('exo', 'nekromant'):
            if card not in self.deckset or g.stat.get('used', [{}, {}])[s].get(card, 0) or any(it[0] == card for it in self.queue):
                continue
            if sd.doba < need_doba(g, s, card) or sd.e < cost_of(g, s, card) + 30 or g.count(s, card) >= S.DEFS[card].get('max', 99):
                continue
            if getattr(self, 'cur_lane', None) is None:
                self.cur_lane = self.lane if self.lane is not None else 4
            self.queue.append([card, g.t])
            return

    def best_center(self, items, weight, r):
        """(score, x, y) of the visible cell whose (2r+1)-wide square holds the most weight; (0, 0, 0) if nothing."""
        g, s = self.g, self.s
        cand = set()
        for o in items:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    x, y = o.cx + dx, o.cy + dy
                    if 0 <= x < S.W and 0 <= y < S.H and g.vis[s][y][x]:
                        cand.add((x, y))
        best = (0, 0, 0)
        for x, y in sorted(cand):
            sc = sum(weight(o) for o in items if abs(o.x - x) <= r and abs(o.y - y) <= r)
            if sc > best[0]:
                best = (sc, x, y)
        return best

    def ready_card(self, card):
        g, s = self.g, self.s
        sd = g.sd[s]
        return (card in self.deckset and sd.cd.get(card, 0) <= 0 and sd.doba >= need_doba(g, s, card)
                and sd.e >= cost_of(g, s, card))

    def cast(self, card, x, y):
        g, s = self.g, self.s
        sd = g.sd[s]
        cost = cost_of(g, s, card)
        g.act(s, {'t': 'card', 'id': card, 'x': x, 'y': y})
        if sd.cd.get(card, 0) > 0:
            g.stat['abil_spent'][s] += cost
            g.stat.setdefault('casts', {}).setdefault(card, [0, 0])[s] += 1
            return True
        return False

    def korp_emp(self):
        """EMP: an attacker fires it on the 3x3 holding the most enemy attack towers (>= 2) when >= 3 own units are within
        3 columns of it; a defender on the 3x3 with >= 3 visible enemy units that is in its own half."""
        g, s = self.g, self.s
        if not self.ready_card('emp'):
            return
        foe = 1 - s
        if self.attacker:
            towers = [b for b in mine(g, foe) if b.cat == 'b' and b.kind in ATTACKS and b.off <= 0 and g.vis[s][b.cy][b.cx]]
            if towers:
                sc, x, y = self.best_center(towers, lambda b: 1, 1)
                near = sum(1 for u in mine(g, s) if u.cat == 'u' and abs(u.cx - x) <= 3)
                # FAC 8: >= 2 attack towers in the 3x3 and >= 3 own units near. Towers are rarely seen in numbers (the push
                # dies at the wall), so one tower is enough once a real push (>= 5 units) is there.
                if (sc >= 2 and near >= 3) or (sc >= 1 and near >= 5):
                    return self.cast('emp', x, y)
        # a defender (and an attacker whose push is not at the wall): the 3x3 with >= 3 visible enemy units in its own half
        units = [e for e in mine(g, foe) if e.cat == 'u' and g.vis[s][e.cy][e.cx] and S.own_half(s, e.cx)]
        if len(units) >= 3:
            sc, x, y = self.best_center(units, lambda e: 1, 1)
            if sc >= 3:
                self.cast('emp', x, y)

    def push_on(self):
        """May Tlupa be thrown now? flood: always; other attackers: queued units or >= 3 units in the Mist; defenders: after 60 s."""
        g, s = self.g, self.s
        if not self.attacker:
            return g.t >= 60
        if self.cfg.get('no_units'):
            return True
        if getattr(self, 'queue', None):
            return True
        foe = 1 - s
        return sum(1 for e in mine(g, s) if e.cat == 'u' and local_x(foe, e.cx) <= 10) >= 3

    def kult_tick(self):
        g, s = self.g, self.s
        sd = g.sd[s]
        foe = 1 - s
        # Tlupa whenever it is off cooldown and 60 energy are spare, but never at the cost of the plan: not while the plan
        # waits for energy (the first version of this rule starved the plan: no towers, no push), defenders not in the first
        # minute, attackers only with a push on the field (the harness also throws one when a push enters the Mist)
        if self.cfg.get('horde', True) and self.plan_state != 'wait' and self.push_on():
            hc = H.horde_price(g, s)[0]
            if sd.horde_cd <= 0 and sd.e >= hc + 60:
                cd0 = sd.horde_cd
                g.act(s, {'t': 'horde'})
                if sd.horde_cd > cd0:
                    g.stat['horde_spent'][s] += hc
                    if self.attacker:
                        self.horde_pending = False
        # Mor on the visible square holding the most enemy units (the King counts double), >= 2
        if self.ready_card('mor'):
            foes = [e for e in mine(g, foe) if e.cat in 'uk' and not e.dead and g.vis[s][e.cy][e.cx]]
            if foes:
                sc, x, y = self.best_center(foes, lambda e: 2 if e.cat == 'k' else 1, 1.5)
                if sc >= 2:
                    self.cast('mor', x, y)
        # Stratég: Volání mrtvých when >= 4 zombies on their way to us stand in the Mist, or the push has >= 3 units
        if g.mode == 'strateg' and sd.cd.get('cmd_utok', 0) <= 0 and H.utok_ok(g, s):
            lo, hi = g.mist()
            zs = sum(1 for z in g.ents.values() if z.cat == 'z' and z.kind != 'alfa' and z.tgt == s and lo <= z.cx <= hi)
            push = sum(1 for e in mine(g, s) if e.cat == 'u' and local_x(foe, e.cx) <= 8)
            if zs >= 4 or push >= 3:
                g.act(s, {'t': 'cmd', 'id': 'utok', 'x': 0, 'y': 0})

    def king_tweak(self, m, k):
        """Kult King: war cry (Pán mrtvých) when >= 4 zombies (not Alfa, not already ours) are within 3."""
        if self.fac != 'kult':
            return
        g, s = self.g, self.s
        if g.sd[s].ult >= 100 and not getattr(self, 'last_u', False):
            near = sum(1 for z in g.ents.values() if z.cat == 'z' and z.kind != 'alfa' and z.own != s
                       and (z.x - k.x) ** 2 + (z.y - k.y) ** 2 <= 9)
            if near >= 4:
                m['u'] = True
                self.last_u = True


def need_doba(g, s, kind):
    return H.need_doba(g, s, kind)


def cost_of(g, s, kind):
    return H.cost_of(g, s, kind)


class FacTurtle(FacMixin, H.Turtle):
    pass


class FacMixed(FacMixin, H.Mixed):
    pass


class FacAttacker(FacMixin, H.Attacker):
    pass


H.FAC_BOTS.update({'turtle': FacTurtle, 'mixed': FacMixed, 'att': FacAttacker})


# ---------------------------------------------------------------- scenario builders (plain dicts: they travel to the workers)
def _fin(f, c, kw):
    c.update(kw)
    c['fac'] = f
    if QT:
        c['q_timeout'] = QT

    if f == 'korp':
        c.setdefault('fallback', {'exo': 'obrnenec'})        # Exoskelet needs Doba II and is limited to 3: Obrněnec instead
    if f == 'prez':
        c.setdefault('contest_inf', 'mrchozrout')            # the relic squad takes Mrchožrout instead of Pěšák
    return c


def _king(f, default='idle'):
    return 'escort' if f == 'kult' else 'repair' if f == 'prez' else default


def turtle(f, wall=False, **kw):
    """Two sniper columns (FAC 8 Turtle). wall=True: wallturtle, two Ostnatá zeď columns in front of the snipers."""
    c = {'bot': 'turtle', 'deck': 'def', 'king': 'repair'}
    if wall:
        c.update(wall_cols=(4, 3), wall_rows=tuple(ROW_ORDER))
    return _fin(f, c, kw)


def mixed(f, **kw):
    return _fin(f, {'bot': 'mixed', 'deck': 'mix', 'king': 'repair'}, kw)


def att(f, **kw):
    """The sensible attacker (R.ATT): light defence, pushes with ATT_COMP."""
    return _fin(f, {'bot': 'att', 'deck': 'att', 'comp': ATT_COMP[f], 'att_def': 'light', 'king': _king(f)}, kw)


def emprush(f='korp', **kw):
    """Korporace attacker that saves its EMP for every push."""
    return att(f, emprush=True, **kw)


def spam(f, **kw):
    """Careless unit spam (R.SPAM) with the faction's units; no Tlupa."""
    return _fin(f, {'bot': 'att', 'deck': 'spam', 'comp': SPAM_COMP[f], 'att_def': 'light', 'spam': True, 'horde': False,
                    'king': 'idle'}, kw)


def flood(f='kult', **kw):
    """Kult flood: no units at all, Tlupa whenever possible, 2 Hnízda path B, Mor."""
    return _fin(f, {'bot': 'att', 'deck': 'flood', 'comp': ['pesak'], 'att_def': 'light', 'spam': True, 'no_units': True,
                    'horde': True, 'nest_path': 'B', 'king': 'idle'}, kw)


def duel(f, ablate=None, **kw):
    """The matrix side: one sniper column, Hlásky, pushes with the faction's comp and all 3 own cards in the deck.
    ablate=<card>: that faction card is replaced by its nearest shared card (deck, comp and plan)."""
    c = {'bot': 'att', 'deck': 'duel', 'comp': DUEL_COMP[f], 'att_def': 'col', 'king': _king(f)}
    if ablate:
        deck = list(FAC_DECKS[f]['duel'])
        repl = ABLATE[ablate]
        if repl in D.BASE_KIT:
            deck[deck.index(ablate)] = next(k for k in FILLER if k not in deck)
        elif repl in deck:
            deck[deck.index(ablate)] = next(k for k in FILLER if k not in deck)
        else:
            deck[deck.index(ablate)] = repl
        comp = H.COMPS[c['comp']] if isinstance(c['comp'], str) else c['comp']
        c['comp'] = [repl if k == ablate else k for k in comp]
        c['deck'] = deck
        c['ablate'] = ablate
    return _fin(f, c, kw)


def duel_scen(f0, f1, ablate0=None):
    return {'p0': duel(f0, ablate0), 'p1': duel(f1), 'length': 'rand', 't_end': 'over'}


def crack_scen(fa, ft, wall=False):
    """Attacker faction fa (p0) against the turtle of faction ft (p1); 720 s, no night."""
    return {'p0': att(fa), 'p1': turtle(ft, wall=wall)}


def spam_scen(fs, fm):
    return {'p0': spam(fs), 'p1': mixed(fm)}


def flood_scen(fm):
    return {'p0': flood(), 'p1': mixed(fm)}


# named scenarios for run.py / perf.py (perf.measure reads run.SCEN)
R.SCEN['f_kk'] = duel_scen('kult', 'kult')
R.SCEN['f_flood'] = flood_scen('bez')
R.SCEN['f_emprush'] = {'p0': emprush('korp'), 'p1': turtle('bez')}
