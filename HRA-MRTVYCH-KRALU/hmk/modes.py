"""Game-type rules. Game holds one Rules object in g.rules and calls its hooks (SPEC 3.3)."""
import math

from . import defs as D
from .defs import H, W, RARITY
from .maps import WALK


class Rules:
    play = 'souboj'
    relic = True
    checkmate = True
    night = True
    promotion = True
    eclipses = None                                  # None -> D.ECLIPSES; a tuple overrides (g.eclipse() reads it)

    def setup(self, g):                              # end of Game.__init__ (placement, resources, kings)
        pass

    def tick(self, g, dt):                           # after Game.timers
        pass

    def end_check(self, g):                          # dict {'winner', 'reason', 'code'} or None -> default throne logic
        return None

    def allow(self, g, s, m):                        # first line of Game.act; False = ignore (the rule calls g.say)
        return True

    def on_msg(self, g, s, m):                       # Game.act with an unknown 't'
        pass

    def unit_may_enter(self, g, e, x, y):            # extra test in can_enter and kral_blocked
        return True

    def horde(self, g, s):                           # True = the mode handled Tlupa
        return False

    def alfa_crate(self, g, killer, x, y):
        return (x, y)

    def start_extra(self, g, s):                     # merged into 'start'
        return {}

    def snap_extra(self, g, s):                      # merged into each snapshot
        return {}

    def end_extra(self, g):                          # merged into 'end'
        return {}


class DuelRules(Rules):
    """Souboj and Výcvik: the 0.5 world schedule (waves, crates, Alfa, eclipses, Poslední noc, Mist)."""

    def tick(self, g, dt):
        if g.t >= g.next_wave:
            g.wave()
            g.next_wave += max(22.0, 38.0 - g.wave_n)
        if g.t >= g.next_crate and not g.night:
            g.drop_crate(min_rar=0 if g.crate_n else 1)
            g.next_crate = g.t + g.R.uniform(50, 70)
        if g.t >= g.next_alfa and not g.night:
            g.next_alfa += 240.0
            cells = [(x, y) for x in g.map.mid for y in range(H) if g.ter[y][x] in WALK and not g.mob[y][x]]
            if cells:
                x, y = g.R.choice(cells)
                a = g.spawn('alfa', 2, x, y)
                a.tgt = 0 if g.throne[0] > g.throne[1] else 1 if g.throne[1] > g.throne[0] else g.R.randint(0, 1)
                g.say('V Mlze se probudila Alfa! Míří na tvůj trůn.', a.tgt, 'w')
                g.say('V Mlze se probudila Alfa! Míří na trůn hráče %s.' % g.names[a.tgt], 1 - a.tgt)
                g.event(None, 'alfa', a.tgt)
        if not g.night:
            for a in g.ecl_times():
                if g.crossed(a - D.ECL_WARN):
                    g.event(None, 'ecl_warn', D.ECL_WARN)
                elif g.crossed(a):
                    g.event(None, 'ecl', 1)
                elif g.crossed(a + D.ECL_LEN):
                    g.event(None, 'ecl', 0)
        if self.night and not g.night and g.t >= g.length:
            g.night = True
            g.say('POSLEDNÍ NOC! Padla tma a Mlha každých 20 s pohltí další sloupec. Vydrž déle než soupeř.', None, 'w')
            g.event(None, 'night', 1)
        if g.night:
            tau = g.t - g.length
            want = min(6, 4 + int(tau / 20))
            drain = (5.0 + tau * 0.2) * dt
            g.throne[0] -= drain
            g.throne[1] -= drain
        else:
            frac = g.t / g.length
            want = 3 if frac >= 0.85 else 2 if frac >= 0.7 else 1 if frac >= 0.5 else 0
        if want > g.stage:
            g.stage = want
            if want != 4:
                g.say('Mlha pohltila další sloupec v obou základnách! Stavby v ní chátrají.', None, 'w')
            g.event(None, 'mist', want)


# ---------------------------------------------------------------- Přežití (MAI 6)
SURV_C = 0.07                  # the single tuning knob (M5-B): budget(k) = round(2 + 1.6 k + SURV_C k^2); read at the use site
SURV = {
    'first': 30.0, 'gap': 32.0, 'gap_dec': 0.6, 'gap_min': 18.0,     # wave times: t1, t(k+1) = t(k) + max(gap_min, gap - gap_dec k)
    'base': 2.0, 'lin': 1.6,                                         # budget(k) = base + lin k + SURV_C k^2
    'obr_from': 8, 'obr_share': 0.25, 'obr_pts': 8, 'small_cap': 36,  # Obr: 8 points each, from wave 8, 25 % of the budget
    'run_from': 4, 'run_step': 0.05, 'run_max': 0.45,                # share of Běžci among the small zombies
    'boss_every': 10,                                                # Alfa (k // 10 of them) on waves 10, 20, 30...
    'buff_from': 12, 'hp_step': 0.05, 'dmg_step': 0.03,              # zombie hp and damage multipliers from wave 12
    'flush': 0.5, 'per_flush': 6,                                    # spawn queue: at most 6 zombies per side every 0.5 s
    'crate_first': 40.0, 'crate_gap': (45.0, 60.0),                  # crate pairs
    'eclipse_every': 5, 'mist_every': 10, 'mist_max': 3,             # eclipse on waves 5, 10, ...; Mist +1 column on 10, 20, 30
    'push': 0.35,                                                    # Tlupa: share of the current wave budget
}
_WT = [0.0, SURV['first']]     # _WT[k] = start of wave k (cache)


def wave_time(k):
    while len(_WT) <= k:
        n = len(_WT) - 1
        _WT.append(_WT[-1] + max(SURV['gap_min'], SURV['gap'] - SURV['gap_dec'] * n))
    return _WT[k]


def wave_budget(k):
    return int(round(SURV['base'] + SURV['lin'] * k + SURV_C * k * k))


def wave_comp(k, budget=None, boss=True):
    """(chodci, běžci, obři, alfy) of wave k; `budget` overrides the wave budget (Tlupa push, boss=False)."""
    b = wave_budget(k) if budget is None else budget
    obr = int(b * SURV['obr_share'] // SURV['obr_pts']) if k >= SURV['obr_from'] else 0
    n = b - SURV['obr_pts'] * obr
    if n > SURV['small_cap']:
        obr += int(math.ceil((n - SURV['small_cap']) / float(SURV['obr_pts'])))
        n = SURV['small_cap']
    run = int(round(n * min(SURV['run_max'], SURV['run_step'] * k))) if k >= SURV['run_from'] else 0
    alfa = k // SURV['boss_every'] if boss and k % SURV['boss_every'] == 0 else 0
    return n - run, run, obr, alfa


def wave_mult(k):
    """(hp multiplier, damage multiplier) of the zombies of wave k."""
    d = k - (SURV['buff_from'] - 1)
    return (1.0 + SURV['hp_step'] * d, 1.0 + SURV['dmg_step'] * d) if d > 0 else (1.0, 1.0)


def _fmt_time(t):
    t = int(round(t))                  # same rounding as end.tm and the client (fmtT)
    return '%d:%02d' % (t // 60, t % 60)


class SurvivalRules(Rules):
    """Přežití: waves of zombies for one player (solo) or two players on a shared board with a quarantine wall."""
    play = 'preziti'
    relic = False
    checkmate = False
    night = False
    promotion = False

    def __init__(self, players=1):
        self.players = 2 if players == 2 else 1
        self.eclipses = tuple(wave_time(k) for k in range(SURV['eclipse_every'], 121, SURV['eclipse_every']))
        self.k = 0                                   # waves started
        self.t_next = wave_time(1)
        self.wq = []                                 # wave queue [(kind, hp mult, dmg mult, wave)], spawned as mirrored pairs
        self.left = {}                               # wave -> entries still in wq
        self.pq = [[], []]                           # Tlupa queue per target side [(kind, hp mult, dmg mult)]
        self.next_flush = 0.0
        self.next_crate = SURV['crate_first']
        self.crate_n = 0
        self.cleared = [0, 0]                        # last wave fully cleared per side (consecutive from wave 1)

    # ------------------------------------------------------------ setup and hooks
    def setup(self, g):
        if self.players == 1:                        # side 1 is only a dummy: no King, never touched
            k = g.sd[1].kral
            if k is not None:
                g.remove(k)
                g.sd[1].kral = None
            g.sd[1].respawn_len = None
        g.next_wave = self.t_next
        orig = g.dmg_of

        def dmg_of(e, _orig=orig):                   # zombie damage multiplier of the late waves (loot unchanged)
            v = _orig(e)
            m = getattr(e, 'dmul', None)
            return v * m if m else v
        g.dmg_of = dmg_of

    def unit_may_enter(self, g, e, x, y):            # the quarantine wall: Mist and zombies stay open for everyone
        if e.cat == 'z':
            return True
        return x < W // 2 if e.side == 0 else x >= W // 2

    def allow(self, g, s, m):
        t = m.get('t')
        if t == 'cmd' and m.get('id') == 'sber':
            try:
                x, y = int(m.get('x', -1)), int(m.get('y', -1))
            except (TypeError, ValueError, OverflowError):
                return True
            if any(c['x'] == x and c['y'] == y for c in g.crates.values()) and (x >= W // 2) != (s == 1):
                g.say('Tahle bedna patří soupeři.', s, 'e')
                return False
        elif t == 'card' and self.players == 1 and m.get('id') == 'vypadek':
            g.say('Výpadek proudu má smysl jen proti soupeři.', s, 'e')
            return False
        return True

    def horde(self, g, s):
        """Tlupa: 2 players only; sends round(0.35 x the current wave budget) points of zombies into the foe's Mist half."""
        if self.players == 1:
            g.say('Tlupu můžeš poslat jen na soupeře.', s, 'e')
            return True
        sd = g.sd[s]
        cost, cd = g.horde_cost(s)
        if sd.horde_cd > 0:
            return True
        if sd.e < cost:
            g.say('Tlupa stojí %d energie.' % cost, s, 'e')
            return True
        sd.e -= cost
        sd.stats['spent'] += cost
        sd.horde_cd = cd
        foe = 1 - s
        k = max(1, self.k)
        walk, run, obr, _ = wave_comp(k, int(round(SURV['push'] * wave_budget(k))), boss=False)
        kinds = ['chodec'] * walk + ['bezec'] * run
        g.R.shuffle(kinds)
        kinds += ['obr'] * obr
        hm, dm = wave_mult(k)
        self.pq[foe].extend((kind, hm, dm) for kind in kinds)
        g.say('Vypustil jsi tlupu (%d zombie).' % len(kinds), s)
        g.say('Soupeř na tebe poslal tlupu zombie!', foe, 'w')
        g.event(foe, 'horde', s)
        return True

    def alfa_crate(self, g, killer, x, y):
        """The Alfa reward crate lands in the killer's own crate column, in the row nearest to the Alfa."""
        s = killer if killer in (0, 1) else (0 if x < W // 2 else 1)
        col = g.map.mid[0 if self.players == 1 else s]
        for r in sorted(g.map.crate_rows, key=lambda r: (abs(r - y), r)):
            if g.ter[r][col] in WALK:
                return col, r
        return x, y

    # ------------------------------------------------------------ the world schedule
    def tick(self, g, dt):
        if self.players == 1:
            g.throne[1] = float(D.THRONE_HP)
        while g.t >= self.t_next:
            self._start_wave(g)
        g.next_wave = self.t_next
        if g.t >= self.next_crate:
            self._crates(g)
        if g.t >= self.next_flush:
            self.next_flush = g.t + SURV['flush']
            self._flush(g)
        for a in self.eclipses:
            if g.crossed(a - D.ECL_WARN):
                g.event(None, 'ecl_warn', D.ECL_WARN)
            elif g.crossed(a):
                g.event(None, 'ecl', 1)
            elif g.crossed(a + D.ECL_LEN):
                g.event(None, 'ecl', 0)

    def _start_wave(self, g):
        self.k = k = self.k + 1
        self.t_next = wave_time(k + 1)
        walk, run, obr, alfa = wave_comp(k)
        hm, dm = wave_mult(k)
        small = ['chodec'] * walk + ['bezec'] * run
        g.R.shuffle(small)
        kinds = small + ['obr'] * obr + ['alfa'] * alfa
        self.wq.extend((kind, hm, dm, k) for kind in kinds)
        self.left[k] = len(kinds)
        if alfa:
            g.say('Z Mlhy se valí vlna %d a s ní Alfa!' % k, None, 'w')
        else:
            g.say('Z Mlhy se valí vlna %d!' % k)
        g.event(None, 'wave', k)
        if k % SURV['mist_every'] == 0 and g.stage < SURV['mist_max']:
            g.stage = min(SURV['mist_max'], k // SURV['mist_every'])
            g.say('Mlha pohltila další sloupec v obou základnách! Stavby v ní chátrají.', None, 'w')
            g.event(None, 'mist', g.stage)

    @staticmethod
    def _free(g, x, y):
        return g.ter[y][x] in WALK and g.mob[y][x] is None and g.bld[y][x] is None

    def _spawn(self, g, kind, tgt, x, y, hm, dm, wave):
        z = g.spawn(kind, 2, x, y)
        z.tgt = tgt
        z.wv = wave
        if hm != 1.0:
            z.maxhp = z.hp = z.maxhp * hm
        if dm != 1.0:
            z.dmul = dm
        return z

    def _flush(self, g):
        """At most per_flush zombies per side: first the wave queue (mirrored pairs as in 0.5 wave()), then Tlupa pushes."""
        cap = SURV['per_flush']
        n = 0
        two = self.players == 2
        free = self._free
        cols = g.map.spawn[0]
        while self.wq and n < cap:
            kind, hm, dm, wv = self.wq[0]
            cells = [(x, y) for x in cols for y in range(H) if free(g, x, y) and (not two or free(g, W - 1 - x, y))]
            if not cells:
                break
            x, y = g.R.choice(cells)
            if two:
                first = g.R.randint(0, 1)            # neither side may always get the older (lower id) zombie
                for tgt in (first, 1 - first):
                    self._spawn(g, kind, tgt, x if tgt == 0 else W - 1 - x, y, hm, dm, wv)
            else:
                self._spawn(g, kind, 0, x, y, hm, dm, wv)
            self.wq.pop(0)
            self.left[wv] -= 1
            n += 1
        for tgt in (0, 1):
            q = self.pq[tgt]
            m = n
            while q and m < cap:
                kind, hm, dm = q[0]
                cells = [(x, y) for x in g.map.spawn[tgt] for y in range(H) if free(g, x, y)]
                if not cells:
                    break
                x, y = g.R.choice(cells)
                self._spawn(g, kind, tgt, x, y, hm, dm, 0)
                q.pop(0)
                m += 1
        self._clear_update(g)

    def _clear_update(self, g):
        """Advance cleared[s]: wave j is cleared for side s once fully spawned and no zombie of it targets s any more."""
        alive = {}
        for e in g.ents.values():
            if e.cat == 'z':
                wv = getattr(e, 'wv', 0)
                if wv:
                    alive[(wv, e.tgt)] = 1
        for s in ((0, 1) if self.players == 2 else (0,)):
            j = self.cleared[s] + 1
            while j <= self.k and not self.left.get(j) and (j, s) not in alive:
                self.cleared[s] = j
                j += 1

    def _crates(self, g):
        """A mirrored pair: one crate in column mid[0] for side 0 and one in mid[1] for side 1 (solo: side 0 only)."""
        first = self.crate_n == 0
        self.crate_n += 1
        lo, hi = SURV['crate_gap']
        self.next_crate = g.t + g.R.uniform(lo, hi)
        sides = (0, 1) if self.players == 2 else (0,)
        taken = [(c['x'], c['y']) for c in g.crates.values()]
        rows = [y for y in g.map.crate_rows
                if all(g.ter[y][g.map.mid[s]] in WALK and (g.map.mid[s], y) not in taken for s in sides)]
        if not rows:
            return
        y = g.R.choice(rows)
        roll = g.R.uniform(0, sum(r[1] for r in RARITY))
        rarity = 0
        for i, r in enumerate(RARITY):
            roll -= r[1]
            if roll <= 0:
                rarity = i
                break
        rarity = max(1 if first else 0, rarity)      # the first crate is at least neobvyklá
        for i, s in enumerate(sides):
            keep = (len(g.msgs[0]), len(g.msgs[1]), len(g.evs[0]), len(g.evs[1]))
            g.drop_crate(g.map.mid[s], y, rarity, land=10.0)
            if i:                                    # one announcement per pair
                del g.msgs[0][keep[0]:], g.msgs[1][keep[1]:], g.evs[0][keep[2]:], g.evs[1][keep[3]:]

    # ------------------------------------------------------------ end and messages
    def end_check(self, g):
        d0 = g.throne[0] <= 0
        d1 = self.players == 2 and g.throne[1] <= 0
        if not (d0 or d1):
            return None
        self._clear_update(g)
        if self.players == 1:
            return {'winner': -1, 'code': 'survive',
                    'reason': 'Trůn padl. Zvládnuté vlny: %d, čas %s.' % (self.cleared[0], _fmt_time(g.t))}
        if d0 and d1:
            z0, z1 = g.sd[0].stats['zk'], g.sd[1].stats['zk']
            if z0 == z1:
                return {'winner': -1, 'code': 'survive', 'reason': 'Oba trůny padly naráz. Remíza.'}
            w = 0 if z0 > z1 else 1
            return {'winner': w, 'code': 'survive',
                    'reason': 'Oba trůny padly naráz, víc zombie zabil hráč %s.' % g.names[w]}
        w = 1 if d0 else 0
        return {'winner': w, 'code': 'survive', 'reason': 'Hráč %s vydržel déle.' % g.names[w]}

    def snap_extra(self, g, s):
        mine = foe = 0
        for e in g.ents.values():
            if e.cat == 'z':
                if e.tgt == s:
                    mine += 1
                else:
                    foe += 1
        return {'sv': [self.k, int(math.ceil(max(0.0, self.t_next - g.t))), mine, foe]}

    def end_extra(self, g):
        self._clear_update(g)
        t = round(g.t, 1)
        two = self.players == 2
        return {'surv': {'wave': [self.cleared[0], self.cleared[1] if two else 0], 't': [t, t if two else 0.0]}}


def make_rules(type, opts):
    """Rules for a game type, or None when that mode is not built yet (the lobby then refuses it)."""
    opts = opts or {}
    try:
        if type in ('souboj', 'vycvik'):
            r = DuelRules()
            r.play = type
            return r
        if type == 'preziti':
            return SurvivalRules(opts.get('players', 1))
        if type == 'puzzle':
            from . import puzzle
            return puzzle.PuzzleRules(puzzle.PUZZLES[opts['puzzle']])
        if type == 'vyuka':
            from . import tutorial
            return tutorial.TutorialRules(opts.get('mode', 'kral'))
    except (NotImplementedError, KeyError):
        return None
    return None
