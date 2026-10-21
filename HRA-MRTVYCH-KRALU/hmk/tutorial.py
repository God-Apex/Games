"""Výuka, the 11-step tutorial (META 5, SPEC 6 M3-B1): TutorialRules.

A solo game against a fixed, preplaced enemy base (TUT_FOE) with no AI and no King. No eclipses, Relikvie, random crates,
Mist advance or Poslední noc: everything that happens is scripted by the steps. The player always plays side 0.

Protocol: snapshot `tu = [step (1-based), total, hx, hy, ui]` for side 0 (hx, hy = -1 without a cell hint; `ui` is
`slot:N | key:V | cmd:odstrel | ''` and is sent only after the step has been open for HINT_AFTER s, which is the hint pulse).
The cell hint is sent from the start of the step. `nw` is forced to 0 (there is no wave countdown). The 'start' message
carries `tsteps` = [{id, text}] of the current mode. `{t:'tut', skip:1}` skips the open step (the last one cannot be skipped).
"""
from .defs import W, H, ATTACK_TOWERS, home_col, own_half
from .maps import WALK, BUILD
from .modes import Rules

TUT_DECK = ['kulomet', 'hlaska', 'pesak', 'jezdec', 'plamen', 'sniper', 'obrnenec', 'dron']
# Enemy base in cells local to the enemy throne (x counted from it, like the player's hints): throne HP, buildings, the
# two Pěšák of the last step. No King, no AI.
TUT_FOE = {'throne': 1200.0, 'gen': [(1, 2), (1, 4), (1, 6)], 'kulomet': [(4, 3), (4, 5)], 'hlaska': [(3, 4)],
           'raid': [(5, 3), (5, 5)]}
HINT_AFTER = 20.0            # s a step stays open before its ui hint (the pulse) turns on
OBR_HP = 0.5                 # the tutorial Obr of the Stratég step has half the usual hp (kinder to a beginner's base)
REVEAL = (8.0, 3.5)          # (seconds, radius) of the foe-base reveal shown with the Hláska step


def _step(id, text, done, hint=None, ui=''):
    return {'id': id, 'text': text, 'hint': hint, 'ui': ui, 'done': done}


# Král steps; TUT_STRATEG replaces steps 1 and 5 (index 0 and 4) in Stratég. `hint` = local cell, `done` = predicate name.
TUT_STEPS = [
    _step('pohyb', 'Pohni Králem klávesami W A S D.', 'moved'),
    _step('gen', 'Postav Generátor: klávesa 1, pak klikni na zvýrazněné pole.', 'gen', hint=(1, 4), ui='slot:1'),
    _step('vez', 'Postav Kulomet blízko Mlhy (klávesa 3).', 'tower', hint=(4, 4), ui='slot:3'),
    _step('vlna', 'Z Mlhy jdou zombie! Věž a Král je zastaví.', 'wave_dead'),
    _step('blok', 'Podrž mezerník: blok sníží poškození.', 'blocked', ui='key:Space'),
    _step('bedna', 'Do Mlhy spadla bedna. Dojdi k ní a počkej 3 s.', 'crate', hint=(6, 4)),
    _step('hlaska', 'Postav Hlásku (klávesa 4). Uvidíš soupeře.', 'hlaska', ui='slot:4'),
    _step('upg', 'Klikni na Kulomet a zmáčkni U.', 'upgraded', ui='key:U'),
    _step('vyzkum', 'Za Vzorky se vyzkoumávají technologie. Zmáčkni V a jednu vyber.', 'tech', ui='key:V'),
    _step('jednotka', 'Vyšli Pěšáka (klávesa 5). Jde sám k soupeři.', 'unit', ui='slot:5'),
    _step('utok', 'Znič soupeřův trůn!', 'win'),
]
TUT_STRATEG = {
    0: _step('rozkazy', 'Tvé rozkazy jsou na liště: Q W E R G.', 'wait6'),
    4: _step('odstrel', 'Zmáčkni W a klikni na zombie.', 'odstrel', ui='cmd:odstrel'),
}


def steps_for(mode):
    return [TUT_STRATEG.get(i, st) if mode == 'strateg' else st for i, st in enumerate(TUT_STEPS)]


class TutorialRules(Rules):
    play = 'vyuka'
    relic = False
    checkmate = False
    night = False
    eclipses = ()

    def __init__(self, mode='kral'):
        self.mode = 'strateg' if mode == 'strateg' else 'kral'
        self.steps = steps_for(self.mode)
        self.n = len(self.steps)
        self.i = 0                        # index of the open step
        self.t0 = 0.0                     # game time it opened
        self.hint = (-1, -1)
        self.wave_ids = []                # the 3 chodci of step 4
        self.blk = False                  # a block (space) was sent during the block step
        self.shown = False                # the foe-base reveal of the Hláska step was started
        self.foe_pos = (W - 4, H // 2)    # where the foe Hláska stands (set in setup)

    # ------------------------------------------------------------ setup: forced deck and the enemy base
    def setup(self, g):
        g.sd[0].deck = list(TUT_DECK)
        g.length = float('inf')
        g.next_wave = g.next_crate = g.next_alfa = 1e9
        g.throne[1] = float(TUT_FOE['throne'])
        k = g.sd[1].kral
        if k is not None:
            g.remove(k)
            g.sd[1].kral = None
        g.sd[1].respawn_len = None
        for kind in ('gen', 'kulomet', 'hlaska'):
            for lx, ly in TUT_FOE[kind]:
                cell = self._nearest(g, W - 1 - lx, ly, lambda x, y: g.ter[y][x] in BUILD and own_half(1, x)
                                     and g.bld[y][x] is None and g.mob[y][x] is None)
                if cell is not None:
                    g.spawn(kind, 1, cell[0], cell[1])
                    if kind == 'hlaska':
                        self.foe_pos = cell
        self._enter(g, 0)

    @staticmethod
    def _nearest(g, x0, y0, ok):
        """The cell nearest to (x0, y0) for which ok(x, y) holds (ties: lower row, then lower column), or None."""
        best = None
        for y in range(H):
            for x in range(W):
                if ok(x, y):
                    key = ((x - x0) ** 2 + (y - y0) ** 2, y, x)
                    if best is None or key < best[0]:
                        best = (key, x, y)
        return (best[1], best[2]) if best else None

    # ------------------------------------------------------------ steps
    def _enter(self, g, i):
        self.i = min(i, self.n - 1)
        self.t0 = g.t
        st = self.steps[self.i]
        self.hint = (-1, -1)
        if st['hint'] is not None:
            lx, ly = st['hint']
            if st['id'] == 'bedna':
                ok = lambda x, y: g.ter[y][x] in WALK and not any(c['x'] == x and c['y'] == y for c in g.crates.values())
            else:
                ok = lambda x, y: (g.ter[y][x] in BUILD and own_half(0, x) and not g.in_mist(x)
                                   and g.bld[y][x] is None and g.mob[y][x] is None)
            cell = self._nearest(g, lx, ly, ok)
            if cell is not None:
                self.hint = cell
        fn = getattr(self, 'e_' + st['id'], None)
        if fn is not None:
            fn(g)

    def _zombie(self, g, kind):
        cells = [(x, y) for x in g.map.spawn[0] for y in range(H)
                 if g.ter[y][x] in WALK and g.mob[y][x] is None and g.bld[y][x] is None]
        if not cells:
            return None
        x, y = g.R.choice(cells)
        z = g.spawn(kind, 2, x, y)
        z.tgt = 0
        return z

    def e_vlna(self, g):
        self.wave_ids = []
        for _ in range(3):
            z = self._zombie(g, 'chodec')
            if z is not None:
                self.wave_ids.append(z.id)
        g.say('Z Mlhy se valí vlna 1!', 0)
        g.event(0, 'wave', 1)

    def e_odstrel(self, g):
        z = self._zombie(g, 'obr')
        if z is not None:
            z.maxhp = z.hp = z.maxhp * OBR_HP
            g.say('Z Mlhy se valí Obr!', 0, 'w')
            g.event(0, 'wave', 1)

    def e_bedna(self, g):
        x, y = self.hint if self.hint[0] >= 0 else (6, H // 2)
        g.drop_crate(x, y, 2, land=2.0)

    def e_upg(self, g):
        g.sd[0].s += 40

    def e_vyzkum(self, g):
        g.sd[0].v += 2

    def e_utok(self, g):
        for lx, ly in TUT_FOE['raid']:
            cell = self._nearest(g, W - 1 - lx, ly, lambda x, y: g.ter[y][x] in WALK and g.mob[y][x] is None
                                 and g.bld[y][x] is None)
            if cell is not None:
                e = g.spawn('pesak', 1, cell[0], cell[1])
                g.fx_of(e, ['n', cell[0], cell[1], 1, 0, 1, 'pesak'])
        g.say('Soupeř posílá dva Pěšáky. Ubraň se a pak znič jeho trůn!', 0, 'w')

    # ------------------------------------------------------------ predicates ("done when")
    def d_moved(self, g):
        k = g.sd[0].kral
        return k is not None and (k.x - home_col(0)) ** 2 + (k.y - H // 2) ** 2 >= 4.0

    def d_wait6(self, g):
        return g.t - self.t0 >= 6.0

    def d_gen(self, g):
        return g.count(0, 'gen') >= 1

    def d_tower(self, g):
        return any(e.side == 0 and e.kind in ATTACK_TOWERS for e in g.ents.values())

    def d_wave_dead(self, g):
        return not any(i in g.ents for i in self.wave_ids)

    def d_blocked(self, g):
        return self.blk or g.sd[0].block_t >= 0

    def d_odstrel(self, g):
        return 'cmd_odstrel' in g.sd[0].cd

    def d_crate(self, g):
        return g.sd[0].stats['crates'] >= 1

    def d_hlaska(self, g):
        return g.count(0, 'hlaska') >= 1 and any(
            e.side == 1 and e.cat == 'b' and g.vis[0][e.cy][e.cx] for e in g.ents.values())

    def d_upgraded(self, g):
        return any(e.side == 0 and e.cat == 'b' and e.lvl >= 2 for e in g.ents.values())

    def d_tech(self, g):
        return len(g.sd[0].techs) >= 1

    def d_unit(self, g):
        return g.sd[0].stats['units'] >= 1

    # ------------------------------------------------------------ hooks
    def tick(self, g, dt):
        sid = self.steps[self.i]['id']
        if sid == 'bedna' and not g.crates and g.sd[0].stats['crates'] < 1:
            self.e_bedna(g)                                  # the crate expired unopened: drop a new one
        elif sid == 'hlaska' and not self.shown and g.count(0, 'hlaska') >= 1:
            self.shown = True                                # a Hláska at lvl 1 cannot see the enemy base: show it
            g.sd[0].reveals.append([self.foe_pos[0], self.foe_pos[1], REVEAL[0], REVEAL[1]])
            g.say('Hláska vidí daleko do Mlhy. Pro ukázku ti na chvíli odhalíme soupeřovu základnu.', 0)
        for _ in range(self.n):                              # a step that is already done is skipped
            st = self.steps[self.i]
            if st['done'] == 'win' or not getattr(self, 'd_' + st['done'])(g):
                break
            self._enter(g, self.i + 1)

    def allow(self, g, s, m):
        if s == 0 and m.get('t') == 'in' and m.get('b') and self.steps[self.i]['done'] == 'blocked':
            self.blk = True                                  # a tap shorter than a tick still counts
        return True

    def on_msg(self, g, s, m):
        if s == 0 and m.get('t') == 'tut' and m.get('skip') in (1, True) and self.i < self.n - 1:
            self._enter(g, self.i + 1)

    def start_extra(self, g, s):
        return {'tsteps': [{'id': st['id'], 'text': st['text']} for st in self.steps]}

    def snap_extra(self, g, s):
        if s != 0:
            return {}
        st = self.steps[self.i]
        ui = st['ui'] if g.t - self.t0 >= HINT_AFTER else ''
        return {'tu': [self.i + 1, self.n, self.hint[0], self.hint[1], ui], 'nw': 0}
