"""The authoritative 1v1 simulation: Game = core (init, helpers, timers, step, views) + the rule mixins."""
import hashlib
import json
import math
import random

from . import defs as D
from . import maps
from . import modes
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401
from .entity import Ent, Side
from . import factions  # noqa: F401  (merges faction cards into D.DEFS at import)
from .vision import VisionMixin
from .actions import ActionsMixin
from .combat import CombatMixin
from .movement import MoveMixin
from .king import KingMixin
from .world import WorldMixin
from .facmech import FactionMixin


class Game(ActionsMixin, CombatMixin, MoveMixin, KingMixin, WorldMixin, VisionMixin, FactionMixin):
    def __init__(self, names, decks, mode, *, rules=None, map_def=None, seed=None, rng=None, facs=('bez', 'bez'),
                 compat05=False):
        if seed is None and rng is None:
            seed = random.randrange(2 ** 31)      # harness random.seed() still gives repeatable games
        self.seed = seed                          # None only when the caller passes its own rng without a seed
        self.R = rng if rng is not None else random.Random(seed)
        self.rules = rules or modes.DuelRules()
        self.play = self.rules.play
        # rules.unit_may_enter is called from hot loops; None when the mode keeps the base rule (always True)
        m = self.rules.unit_may_enter
        self.may_enter = None if getattr(m, '__func__', None) is modes.Rules.unit_may_enter else m
        self.facs = tuple(f if f in factions.FACTIONS else 'bez' for f in facs)
        self.compat05 = compat05
        self.facon = any(f != 'bez' for f in self.facs)    # faction hooks run only then (bez-bez = 0.5 + global rules)
        self.clouds = []          # Mor: [side, x, y, seconds]
        self.names = names
        self.mode = mode
        self.sd = [Side(0, names[0], decks[0], self.facs[0]), Side(1, names[1], decks[1], self.facs[1])]
        self.ents = {}
        self.nid = 1
        self.map = map_def or maps.pick_map('ruiny', self.R)     # draw order as 0.5: map first, then the length
        self.ter = [list(r) for r in self.map.ter]
        self.dist = [bfs(self.ter, 0), bfs(self.ter, W - 1)]
        self.bld = [[None] * W for _ in range(H)]
        self.mob = [[None] * W for _ in range(H)]
        self.throne = [float(D.THRONE_HP), float(D.THRONE_HP)]
        self.throne_cd = [0.0, 0.0]
        self.t = self.prev_t = 0.0
        self.length = self.R.uniform(600, 900)
        self.stage = 0            # how far the Mist has advanced (0-3 by day, 4-6 in Poslední noc)
        self.night = False
        self.over = None
        self.fx = []
        self.pfx = [[], []]       # fx only the owner may see (hidden things)
        self.msgs = [[], []]      # (text, kind) per side
        self.evs = [[], []]       # events per side since the last snapshot
        self.dealt = [0.0, 0.0]   # damage to the enemy throne and buildings (Poslední noc tie-break)
        self.first_blood = False
        self.next_wave = 40.0
        self.wave_n = 0
        self.next_crate = 40.0
        self.crate_n = 0
        self.next_alfa = 300.0
        self.relic = {'on': False, 'own': -1, 'by': -1, 'p': 0.0, 'vt': 0.0}
        self.crates = {}
        self.strikes = []         # Nálet: [side, x, y, seconds]
        self.charges = []         # sabotage: [side, ('e', id) or ('t', side), seconds, x, y]
        self.barriers = []        # Karanténa: [row, seconds]
        self.drones = []          # Sběrný dron
        self.lure = None          # Návnada: [x, y, seconds, dist grid]
        self.masked = set()
        self.reflectors = [[], []]
        self.pending = []         # delayed deployments [t_due, side, kind, row] (relic squad)
        self.ecl_log = []         # [[start, end], ...] of every eclipse that ran
        self.ecl_open = False
        self.night_t = None       # game time Poslední noc began
        self.ser = {'dt': D.SAMPLE_DT, 'th': [[], []], 'inc': [[], []], 'army': [[], []]}
        self.next_sample = D.SAMPLE_DT
        self.vis = [self.base_vis(0), self.base_vis(1)]
        if mode == 'kral':
            for s in (0, 1):
                self.spawn_kral(s)
        self.rules.setup(self)
        self.sample()

    def say(self, text, side=None, kind='i'):
        """kind: 'e' refusal, 'w' warning, 'i' info."""
        for s in ((0, 1) if side is None else (side,)):
            self.msgs[s].append((text, kind))

    def event(self, side, *ev):
        for s in ((0, 1) if side is None else (side,)):
            self.evs[s].append(list(ev))

    def crossed(self, at):
        return self.prev_t < at <= self.t

    def ecl_times(self):
        e = self.rules.eclipses
        return D.ECLIPSES if e is None else e

    def in_mist(self, x):
        lo, hi = self.mist()
        return lo <= x <= hi

    def buildable(self, side, x):
        return own_half(side, x) and not self.in_mist(x)

    def count(self, side, kind):
        return sum(1 for e in self.ents.values() if e.kind == kind and e.side == side)

    def income(self, side):
        inc = D.BASE_INCOME + (2.0 if self.sd[side].doba >= 3 else 0.0) + (2.0 if self.relic['own'] == side else 0.0)
        for e in self.ents.values():
            if e.kind == 'gen' and e.side == side and e.off <= 0:
                inc += (2, 3, 3)[e.lvl - 1] + (3 if e.path == 'A' else 0)
        return inc

    def techs(self, side):
        return self.sd[side].techs if side in (0, 1) else ()

    def spawn(self, kind, side, x, y):
        e = Ent(self.nid, kind, side, x, y, self.R)
        self.nid += 1
        self.ents[e.id] = e
        if e.cat == 'b':
            self.bld[y][x] = e
        elif e.cat in 'uz':
            self.mob[y][x] = e
        if e.cat in 'bu':
            self.refresh_hp(e, full=True)
        return e

    def spawn_kral(self, s):
        k = Ent(self.nid, 'kral', s, home_col(s), H // 2, self.R)
        self.nid += 1
        self.ents[k.id] = k
        self.sd[s].kral = k
        return k

    def remove(self, e):
        e.dead = True
        self.ents.pop(e.id, None)
        if e.cat == 'b':
            if self.bld[e.cy][e.cx] is e:
                self.bld[e.cy][e.cx] = None
        elif e.cat in 'uz':
            if self.mob[e.cy][e.cx] is e:
                self.mob[e.cy][e.cx] = None

    def max_hp(self, e):
        d = DEFS[e.kind]
        techs = self.techs(e.side)
        if e.cat == 'b':
            hp = d['hps'][e.lvl - 1] if 'hps' in d else d['hp'] * LVL_MULT[e.lvl - 1]
            if self.facon and e.side in (0, 1):
                fm = self.fm(e.side)
                if e.kind == 'zed' and 'zed_hp' in fm:
                    hp *= fm['zed_hp']
                if 'bhp' in fm:
                    hp *= fm['bhp']
            if 'ing1' in techs:
                hp *= 1.25
        elif e.cat == 'u':
            hp = d['hp'] * (1.5 if e.vet else 1.0)
            if 'arm2' in techs:
                hp *= 1.3
        else:
            hp = d['hp']
        return float(hp)

    def refresh_hp(self, e, full=False):
        new = self.max_hp(e)
        e.hp = new if full else max(1.0, e.hp + new - e.maxhp)
        e.maxhp = new

    def dmg_of(self, e):
        v = DEFS[e.kind].get('dmg', 0)
        if e.cat == 'b':
            v *= LVL_MULT[e.lvl - 1]
        elif e.cat == 'u':
            if e.vet:
                v *= 1.5
            if 'arm1' in self.techs(e.side):
                v *= 1.2
        return v

    def step_of(self, e):
        st = DEFS[e.kind]['step']
        if e.cat == 'u':
            if e.fast:
                st *= 0.67
            if 'arm3' in self.techs(e.side):
                st *= 0.8
            if self.cry(e) < 1.0:
                st *= 0.7
        if e.cat in 'uz' and self.ter[e.cy][e.cx] == '~':
            st *= 0.75                            # canal
        return st * e.slowf

    def cry(self, e):
        """Tower damage multiplier for unit e: King's war cry aura 0.4, Stratég's Útok! 0.5, otherwise 1."""
        if e.cat != 'u':
            return 1.0
        sd = self.sd[e.side]
        k = sd.kral
        if sd.ult_t > 0 and k and (k.x - e.x) ** 2 + (k.y - e.y) ** 2 <= KRAL['cry_r'] ** 2:
            return 0.4
        return 0.5 if sd.cry_t > 0 else 1.0

    def rng(self, e):
        r = DEFS[e.kind].get('range', 0)
        if e.kind == 'plamen' and e.path == 'B':
            r = 2.6
        else:
            r += (e.lvl - 1) * 0.2
        if 'ing3' in self.techs(e.side):
            r += 0.6
        if e.cat == 'b' and self.ter[e.cy][e.cx] == '^':
            r += 1.0                              # raised ground
        return r

    def vision(self, e):
        d = DEFS[e.kind]
        v = d.get('vision', 1.5)
        if e.kind == 'hlaska':
            v = 7.0 if e.path == 'A' else (4.5 + (e.lvl - 1) * 0.75 if e.lvl < 3 else 6.0)
        elif e.cat == 'b' and e.kind not in ('zed', 'mina', 'ostnata'):

            v += (e.lvl - 1) * 0.25
        if e.cat == 'b':
            if 'ing3' in self.techs(e.side):
                v += 0.5
            if self.ter[e.cy][e.cx] == '^':
                v += 1.0                          # raised ground
        return v

    def timers(self, dt):
        for s in (0, 1):
            sd = self.sd[s]
            sd.e += self.income(s) * dt
            if self.facon:
                sd.s += self.scrap_income(s) * dt
            sd.horde_cd = max(0.0, sd.horde_cd - dt)
            sd.outage = max(0.0, sd.outage - dt)
            sd.shield = max(0.0, sd.shield - dt)
            sd.block_cd = max(0.0, sd.block_cd - dt)
            sd.dash_cd = max(0.0, sd.dash_cd - dt)
            sd.dash_t = max(0.0, sd.dash_t - dt)
            sd.ult_t = max(0.0, sd.ult_t - dt)
            sd.cry_t = max(0.0, sd.cry_t - dt)
            if sd.kral and not own_half(s, sd.kral.cx):
                sd.ult = min(100.0, sd.ult + dt)
            for k in list(sd.cd):
                sd.cd[k] -= dt
                if sd.cd[k] <= 0:
                    del sd.cd[k]
            sd.reveals = [[x, y, t - dt, r] for x, y, t, r in sd.reveals if t - dt > 0]
            j = sd.job
            if j:
                j[2] += dt
                if self.ter[j[1]][j[0]] != '#':
                    sd.job = None
                elif j[2] >= D.SCRAP_TIME:
                    self.ter[j[1]][j[0]] = '.'
                    sd.s += D.SCRAP_GAIN
                    sd.job = None
                    self.dist = [bfs(self.ter, 0), bfs(self.ter, W - 1)]
                    self.say('Trosky rozebrány: +%d šrotu.' % D.SCRAP_GAIN, s)
            if self.mode == 'kral' and sd.kral is None and sd.respawn_len is not None:
                sd.respawn -= dt
                if sd.respawn <= 0:
                    self.spawn_kral(s)
                    self.say('Tvůj Král znovu povstal.', s)
                    self.event(None, 'kr', s)
            if sd.block_t >= 0 and self.t - sd.block_t > KRAL['block']:
                sd.block_t = -1.0
                sd.block_cd = KRAL['block_cd']
        self.barriers = [[y, t - dt] for y, t in self.barriers if t - dt > 0]
        if self.lure:
            self.lure[2] -= dt
            if self.lure[2] <= 0:
                self.lure = None
        if self.pending:
            now = self.t + 1e-9
            due = [p for p in self.pending if p[0] <= now]
            if due:
                self.pending = [p for p in self.pending if p[0] > now]
                for _, s, kind, row in due:
                    self.squad_member(s, kind, row)

    def track_world(self):
        """night_t and ecl_log (end-screen bands). Called each step after rules.tick."""
        if self.night and self.night_t is None:
            self.night_t = round(self.t, 2)
        act = self.eclipse()[0] == 2
        if act and not self.ecl_open:
            a = next((a for a in self.ecl_times() if a <= self.t < a + D.ECL_LEN), self.t)
            self.ecl_log.append([a, a + D.ECL_LEN])
            self.ecl_open = True
        elif not act and self.ecl_open:
            self.close_eclipse()

    def close_eclipse(self):
        self.ecl_open = False
        if self.ecl_log and self.ecl_log[-1][1] > self.t:      # cut short by Poslední noc or the end of the game
            self.ecl_log[-1][1] = round(self.t, 2)

    def army_value(self, s):
        """Army value of side s for the graphs: base cost (energy + 3 x scrap) of live units, attack towers x level."""
        v = 0.0
        for e in self.ents.values():
            if e.side != s:
                continue
            if e.cat == 'u':
                c = DEFS[e.kind]['cost']
                v += c[0] + 3 * c[1]
            elif e.kind in ATTACK_TOWERS:
                c = DEFS[e.kind]['cost']
                v += (c[0] + 3 * c[1]) * LVL_MULT[e.lvl - 1]
        return int(round(v))

    def sample(self):
        """One point of the time series g.ser: throne, income x 10 and army value per side."""
        for s in (0, 1):
            self.ser['th'][s].append(int(self.throne[s]))
            self.ser['inc'][s].append(int(round(self.income(s) * 10)))
            self.ser['army'][s].append(self.army_value(s))

    def step(self, dt):
        if self.over:
            return
        self.prev_t = self.t
        self.t += dt
        self.timers(dt)
        self.rules.tick(self, dt)
        self.track_world()
        ents = list(self.ents.values())
        self.passives(ents, dt)
        self.vis = [self.compute_vis(0, ents), self.compute_vis(1, ents)]
        for e in ents:
            if e.dead:
                continue
            if e.cat == 'b':
                self.tower(e, dt)
            elif e.cat == 'k':
                self.kral_tick(e, dt)
            else:
                self.mobile(e, dt)
        for s in (0, 1):
            self.throne_gun(s, dt)
        self.mines()
        self.strikes_tick(dt)
        if self.clouds:
            self.clouds_tick(dt)
        self.charges_tick(dt)
        self.crates_tick(dt)
        self.drones_tick(dt)
        if self.rules.relic:
            self.relic_tick(dt)
        if self.rules.checkmate:
            self.checkmate(dt)
        for s in (0, 1):
            self.throne[s] = max(0.0, self.throne[s])
        if not self.over:
            res = self.rules.end_check(self)
            if res:
                self.over = res
        if not self.over and (self.throne[0] <= 0 or self.throne[1] <= 0):
            if self.throne[0] <= 0 and self.throne[1] <= 0:
                d = self.dealt
                if abs(d[0] - d[1]) < 1:
                    self.over = {'winner': -1, 'reason': 'Oba trůny padly současně. Remíza.', 'code': 'draw'}
                else:
                    w = 0 if d[0] > d[1] else 1
                    self.over = {'winner': w, 'reason': 'Oba trůny padly naráz, víc škody nadělal hráč %s.' % self.names[w],
                                 'code': 'both'}
            else:
                w = 0 if self.throne[1] <= 0 else 1
                self.over = {'winner': w, 'reason': 'Trůn hráče %s padl.' % self.names[1 - w],
                             'code': 'night' if self.night else 'throne'}
        if self.over:
            if self.ecl_open:
                self.close_eclipse()
        else:
            while self.t >= self.next_sample - 1e-6:
                self.next_sample += D.SAMPLE_DT
                self.sample()

    def snapshot(self, side, fx):
        vis = self.vis[side]
        sd = self.sd[side]
        facon = self.facon
        out = []

        for e in self.ents.values():
            if e.side == side or self.can_see(side, e):
                flags = ((1 if e.vet else 0) | (2 if e.burn > 0 else 0) | (4 if e.mark > 0 else 0) | (8 if e.lit else 0)
                         | (16 if e.shield else 0) | (32 if e.stun > 0 else 0) | (64 if e.slowf > 1.0 else 0)
                         | (128 if e.side == side and self.hidden_kind(e) else 0) | (512 if e.fast else 0))
                if e.cat == 'k':
                    ks = self.sd[e.side]
                    flags |= (256 if ks.block_t >= 0 else 0) | (1024 if ks.ult_t > 0 else 0)
                elif e.cat == 'u' and self.cry(e) < 1.0:
                    flags |= 1024
                if e.own >= 0:
                    flags |= 2048 | (4096 if e.own == 1 else 0)     # owned zombie, owner side 1
                elif facon:
                    if e.off > 0:
                        flags |= 8192                               # building off (EMP)
                    elif e.sh > 0:
                        flags |= 16                                 # Exoskelet shield
                out.append([e.id, e.kind, e.side, round(e.x, 2), round(e.y, 2), int(math.ceil(e.hp)), int(e.maxhp), e.lvl, e.path,
                            flags, e.kills if e.side == side else 0])

        my_fx = self.visible_fx(side, fx)
        j = sd.job
        k = sd.kral
        rl = self.relic
        msg = {
            't': 's', 'tm': round(self.t, 1), 'ni': self.night, 'st': self.stage, 'nw': int(max(0, self.next_wave - self.t)),
            'r': [int(sd.e), int(sd.s), int(sd.v)], 'inc': round(self.income(side), 1), 'gp': self.price(side, 'gen')[0],
            'sp': self.price(side, 'sniper')[0], 'ec': self.eclipse(), 'dl': [int(self.dealt[0]), int(self.dealt[1])],
            'rl': [rl['own'], rl['by'], round(rl['p'] / D.RELIC_TIME, 2), int(math.ceil(D.RELIC_SAMPLE - rl['vt'])) if rl['own'] >= 0 else 0],
            'doba': sd.doba, 'tech': sorted(sd.techs), 'cd': {c: round(v, 1) for c, v in sd.cd.items()},
            'free': dict(sd.free), 'mob': sd.mobil, 'stc': sd.stats['crates'],
            'th': [int(math.ceil(self.throne[0])), int(math.ceil(self.throne[1]))],
            'sh': [round(self.sd[0].shield, 1), round(self.sd[1].shield, 1)],
            'ck': [round(self.sd[0].check, 1), round(self.sd[1].check, 1)],
            'out': [round(self.sd[0].outage, 1), round(self.sd[1].outage, 1)],
            'v': ''.join('1' if vis[y][x] else '0' for y in range(H) for x in range(W)),
            'ter': ''.join(''.join(row) for row in self.ter),
            'en': out, 'fx': my_fx,
            'cr': [[c['id'], c['x'], c['y'], c['r'], round(c['land'], 1), int(c['ttl']),
                    round(c['ch'][0] / D.CRATE_CH, 2), round(c['ch'][1] / D.CRATE_CH, 2), 1 if c['now'] else 0] for c in self.crates.values()],
            'dr': [[round(d['x'], 2), round(d['y'], 2), d['s'], 1 if d['h'] else 0] for d in self.drones],
            'ns': [[x, y, round(t, 1), s] for s, x, y, t in self.strikes],
            'qb': [[y, round(t, 1)] for y, t in self.barriers],
            'lu': [self.lure[0], self.lure[1], round(self.lure[2], 1)] if self.lure else None,
            'rv': [[x, y, round(t, 1), r] for x, y, t, r in sd.reveals],
            'job': [j[0], j[1], round(j[2] / D.SCRAP_TIME, 2)] if j else None,
            'hcd': round(sd.horde_cd, 1), 'hc': self.horde_cost(side)[0],
        }
        if self.mode == 'strateg' and rl['on']:
            kit = self.squad_kit(side)[1]
            if kit:
                msg['sq'] = [sum(self.price(side, k)[0] for k in kit), round(sd.cd.get('squad', 0.0), 1)]
        if self.facon:
            si = self.scrap_income(side)
            if si > 0:
                msg['sinc'] = round(si, 1)
            if self.clouds:
                mc = [[x, y, round(t, 1), cs] for cs, x, y, t in self.clouds if cs == side or vis[y][x]]
                if mc:
                    msg['mc'] = mc
        if self.mode == 'kral':
            msg['kr'] = {'id': k.id if k else 0, 'dead': round(sd.respawn, 1) if k is None else 0,
                         'blk': (2 if self.t - sd.block_t <= KRAL['parry'] else 1) if sd.block_t >= 0 else 0,
                         'bcd': round(sd.block_cd, 1), 'ult': int(sd.ult), 'ua': round(sd.ult_t, 1), 'dcd': round(sd.dash_cd, 1),
                         'sf': round(k.slowf, 3) if k else 1}
        if self.msgs[side]:
            msg['msg'] = [t for t, _ in self.msgs[side]]
            msg['mk'] = [kind for _, kind in self.msgs[side]]
            self.msgs[side] = []
        if self.evs[side]:
            msg['ev'] = self.evs[side]
            self.evs[side] = []
        msg.update(self.rules.snap_extra(self, side))
        return msg

    def visible_fx(self, side, fx):
        """The fx of this tick that `side` may see (plus its private fx, which are consumed)."""
        vis = self.vis[side]

        def seen(x, y):
            xi, yi = int(round(x)), int(round(y))
            return 0 <= yi < H and 0 <= xi < W and vis[yi][xi]
        my_fx = [f for f in fx if f[5] == side or f[0] in 'oR' or seen(f[1], f[2]) or (f[0] in 'ksmtqazDH' and seen(f[3], f[4]))]
        my_fx += self.pfx[side]
        self.pfx[side] = []
        return my_fx

    # ------------------------------------------------ seams (filled by factions and modes later)
    def fm(self, s):
        """The faction mods of side s (FAC 2)."""
        return factions.FACTIONS[self.sd[s].fac]['mods']

    def price(self, s, kind):
        """[energy, scrap] the side pays now for building/deploying/casting `kind` (count escalation, then the faction rule)."""
        cost = list(DEFS[kind].get('cost', [0, 0]))
        if kind == 'gen':
            cost[0] = D.gen_price(self.count(s, 'gen'))
        elif kind == 'sniper':
            cost[0] = D.sniper_price(self.count(s, 'sniper'))
        if self.sd[s].fac != 'bez':
            cost = factions.fac_price(self.sd[s].fac, kind, cost)
        return cost

    def need_doba(self, s, kind):
        d = self.fm(s).get('doba')
        if d and kind in d:
            return d[kind]
        return DEFS[kind].get('doba', 1)

    def cmd_of(self, s, cid):
        """CMDS[cid] merged with the side's faction variant (FAC 4); compat05: Útok! is not gated."""
        c = CMDS.get(cid)
        if c is None:
            return None
        v = factions.FACTIONS[self.sd[s].fac]['cmd'].get(cid)
        if v is None and not (cid == 'utok' and self.compat05):
            return c
        c = dict(c)
        if v:
            c.update(v)
        if cid == 'utok' and self.compat05:
            c['doba'] = 1
        return c

    def card_cd(self, s, card):
        """Cooldown of an ability card (Korporace: Průzkumný dron 15 s)."""
        if card == 'dron':
            m = self.fm(s).get('dron')
            if m:
                return m[1]
        return DEFS[card]['cd']

    def horde_cost(self, s):
        """(energy cost, cooldown) of Tlupa (Kult: 80 / 18 s; Levná tlupa x0.6 and 15 s, Kult 12 s)."""
        cheap = 'bio1' in self.sd[s].techs
        h = self.fm(s).get('horde')
        if h:
            return round(h[0] * (0.6 if cheap else 1.0)), (12.0 if cheap else h[1])
        return round(D.HORDE_COST * (0.6 if cheap else 1.0)), (15.0 if cheap else D.HORDE_CD)

    def state_hash(self):
        """Regression fingerprint (same algorithm as dev/tests/golden/statehash.py)."""
        ents = sorted([e.id, e.kind, e.side, round(e.x, 6), round(e.y, 6), round(e.hp, 6), e.lvl, e.path]
                      for e in self.ents.values())
        data = [round(self.t, 6), [[sd.e, sd.s, sd.v] for sd in self.sd], self.throne, ents]
        return hashlib.sha1(json.dumps(data).encode('utf-8')).hexdigest()

    def start_info(self, s):
        """The game part of the 'start' message for side s."""
        msg = {'t': 'start', 'side': s, 'names': self.names, 'w': W, 'h': H, 'half': HALF, 'mist': MIST,
               'mode': self.mode, 'deck': self.sd[s].deck, 'throne': D.THRONE_HP, 'horde': [D.HORDE_COST, D.HORDE_CD]}
        fac = self.sd[s].fac
        F = factions.FACTIONS[fac]
        msg.update({'fac': list(self.facs), 'costs': factions.base_costs(fac), 'rcost': factions.research_costs(fac),
                    'cmds': factions.merged_cmds(fac, self.compat05),
                    'perk': dict(F['perk']) if F['perk'] and self.mode == 'kral' else None})
        if F['mods'].get('horde'):
            msg['horde'] = list(F['mods']['horde'])
        msg.update(self.rules.start_extra(self, s))
        return msg

    def end_info(self):
        """The 'end' message (g.over must be set)."""
        o = self.over or {'winner': -1, 'reason': '', 'code': 'error'}
        msg = {'t': 'end', 'winner': o['winner'], 'reason': o['reason'], 'tm': round(self.t),
               'stats': [dict(sd.stats, relic_s=round(sd.stats['relic_s'], 1)) for sd in self.sd], 'names': self.names,
               'th': [int(self.throne[0]), int(self.throne[1])], 'dl': [int(self.dealt[0]), int(self.dealt[1])],
               'code': o.get('code', 'error'), 'fac': list(self.facs)}
        msg.update(self.rules.end_extra(self))
        return msg
