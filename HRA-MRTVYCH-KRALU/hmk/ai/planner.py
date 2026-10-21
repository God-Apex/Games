"""Planner (MAI 5.2-5.5): economy, defence, scouting, attack, relic, upgrades and research.

Each think runs the steps in priority order and spends at most `acts` actions. A step returns 'did' (one action
queued), 'done' (nothing to do, go on), 'wait' (saving energy: stop) or 'save' (saving: skip only the upgrades).
"""
from .. import defs as D
from ..defs import W, H, DEFS, RESEARCH, ATTACK_TOWERS, BASE_KIT, local_x
from ..maps import BUILD, WALK
from . import profiles as PR
from .facplay import FacPlay

ROW_ORDER = [4, 3, 5, 2, 6, 1, 7, 0, 8]
UNIT_KINDS = [k for k, d in DEFS.items() if d['cat'] == 'u']


def squad_supported():
    try:
        from .. import actions
        return 'squad' in actions.ACT_TYPES
    except Exception:          # pragma: no cover
        return False


class Planner:
    def __init__(self, ai):
        self.ai = ai
        self.g, self.s, self.v, self.act, self.P, self.rnd = ai.g, ai.side, ai.view, ai.act, ai.P, ai.rnd
        self.foe = 1 - self.s
        self.strat = ai.strat
        self.survival = ai.type == 'preziti'
        self.fp = FacPlay(ai, self) if ai.fac in PR.FACTION_PLAN else None
        self.res_order = PR.RESEARCH[PR.STRAT_RESEARCH[self.strat]]
        self.row_w = self._row_weights()
        self.cross = self._cross_rows()
        self.rows = self._row_order()
        self.tmpl = self._template(self._base_template())
        self.extra = []
        self.surplus_cells = set()
        self.queue = []                    # [kind, due, rows] units waiting to be deployed
        self.next_push = self.P['push'][0]
        self.push_n = 0
        self.lane = 4
        self.ecl_push = False
        self.horde_pending = False
        self.rushed = not (self.P['rush'] and self.strat == 'rush')
        self.next_sq = 0.0
        self.next_drone = 60.0
        self.turtle_timing = False
        self.adapted = set()
        self.threat = [0.0] * H            # last known threat per row (for upgrades)
        self.last_relic_lehka = 0.0
        self.squad_msg = squad_supported()
        self._rc = None                    # research costs of this side (faction discounts), read once
        self.next_clear = 0.0              # Přežití: earliest time of the next Mist-clearing squad
        self.runner_for = set()            # Přežití: crates a runner unit was sent for

    # ------------------------------------------------ geometry
    def rx(self, lx):
        return lx if self.s == 0 else W - 1 - lx

    def front_lx(self):
        for lx in range(5, -1, -1):
            if self.v.buildable(self.rx(lx)):
                return lx
        return 0

    def _row_weights(self):
        v = self.v
        x6, x7 = self.rx(6), self.rx(7)
        walk = [(2 if v.walk(x6, y) else 0) + (2 if v.walk(x7, y) else 0) for y in range(H)]
        return [walk[y] * 2 + (walk[y - 1] if y > 0 else 0) + (walk[y + 1] if y < H - 1 else 0) for y in range(H)]

    def _cross_rows(self):
        """Rows a ground unit can walk straight across the Mist (columns 6-9 all walkable): water, pillars and rubble
        close the others (Most has 3 bridge rows, Továrna 5 gate rows). Pushes only use these rows."""
        v = self.v
        c = [all(v.walk(x, y) for x in range(6, 10)) for y in range(H)]
        return c if any(c) else [True] * H

    def _row_order(self):
        if self.v.map_random() or len(set(self.row_w)) == 1:
            return list(ROW_ORDER)
        return sorted(range(H), key=lambda y: (-self.row_w[y], ROW_ORDER.index(y)))

    def _base_template(self):
        items = list(PR.TEMPLATES[self.strat])
        if self.fp is not None:
            ins = self.fp.plan.get('insert', {}).get(self.strat)
            if ins:
                items = items[:5] + list(ins) + items[5:]       # after the first tower block
        return items

    def _template(self, items):
        """Remap the template rows by the map weight (gates first)."""
        out = []
        for kind, lx, y in items:
            out.append((kind, lx, self.rows[ROW_ORDER.index(y)]))
        return out if self.v.map_random() else self._fit(out)

    def _fit(self, items):
        """Fixed maps: a template cell that is not buildable (canal, rubble, pillar) moves to the nearest buildable
        cell in the same area, so Metro / Továrna / Most end up with the same number of towers as an open map."""
        v = self.v
        used = set((lx, y) for _, lx, y in items if v.ter(self.rx(lx), y) in BUILD)
        res = []
        for kind, lx, y in items:
            if v.ter(self.rx(lx), y) not in BUILD:
                for dx, dy in ((0, 1), (0, -1), (0, 2), (0, -2), (-1, 0), (1, 0), (-1, 1), (-1, -1), (1, 1), (1, -1)):
                    nx, ny = lx + dx, y + dy
                    if 0 <= nx <= 5 and 0 <= ny < H and (nx, ny) not in used and v.ter(self.rx(nx), ny) in BUILD:
                        used.add((nx, ny))
                        lx, y = nx, ny
                        break
            res.append((kind, lx, y))
        return res

    # ------------------------------------------------ resources
    def energy(self):
        return self.v.sd.e - self.act.reserved

    def has(self, kind):
        return kind in BASE_KIT or kind in self.v.deck()

    def doba_ok(self, kind):
        return self.v.sd.doba >= self.g.need_doba(self.s, kind)

    # ------------------------------------------------ primitive actions
    def try_build(self, kind, lx, y, misplace=True):
        g, v, s = self.g, self.v, self.s
        if not self.has(kind) or not self.doba_ok(kind):
            return 'skip'
        if g.mode == 'kral' and v.king() is None:
            return 'wait'
        x = self.rx(lx)
        if not (0 <= x < W and 0 <= y < H) or not v.buildable(x) or not v.free_cell(x, y):
            return 'skip'
        key = ('b', x, y)
        if self.act.busy(key) or self.act.bad(key):
            return 'skip'
        cost = g.price(s, kind)
        if self.energy() < cost[0] or v.sd.s < cost[1]:
            return 'poor'
        if misplace and self.P['misplace'] and self.rnd.random() < self.P['misplace']:
            cells = [(self.rx(a), b) for a in range(0, self.front_lx() + 1) for b in range(H)
                     if v.free_cell(self.rx(a), b)]
            if cells:
                x, y = cells[self.rnd.randrange(len(cells))]
                key = ('b', x, y)
        self.act.push({'t': 'build', 'kind': kind, 'x': x, 'y': y}, cost[0], key,
                      check=lambda: v.own_bld(x, y) is not None)
        return 'did'

    def try_upgrade(self, e, path=None):
        v = self.v
        if e.lvl >= 3 or e.dead:
            return 'skip'
        key = ('u', e.id, e.lvl)
        if self.act.busy(key) or self.act.bad(key):
            return 'skip'
        if self.g.mode == 'kral' and v.king() is None:
            return 'wait'
        ce, cs = DEFS[e.kind]['up'][e.lvl - 1]
        if self.energy() < ce:
            return 'poor'
        if v.sd.s < cs:
            return 'poor_s'
        m = {'t': 'upg', 'id': e.id}
        if e.lvl == 2 and DEFS[e.kind].get('paths'):
            m['path'] = path or PR.UP_PATH.get(e.kind, 'A')
        lv = e.lvl
        self.act.push(m, ce, key, check=lambda: e.lvl > lv)
        return 'did'

    def convert(self):
        """Přetavení for a scrap-blocked upgrade."""
        sd = self.v.sd
        if self.P['conv'] == 'never' or sd.doba < D.CONV[2] or self.energy() < D.CONV[0] + 20:
            return False
        if self.act.busy(('conv',)):
            return False
        self.act.push({'t': 'conv'}, D.CONV[0], ('conv',))
        return True

    def try_deploy(self, kind, rows):
        g, v = self.g, self.v
        if self.fp is not None:
            kind = self.fp.sub(kind)
        if kind not in v.deck() or not self.doba_ok(kind):
            return 'skip'
        cost = g.price(self.s, kind)[0]
        if self.energy() < cost:
            return 'poor'
        lx = self.front_lx()
        for dx in (0, -1, -2):
            if lx + dx < 0:
                break
            x = self.rx(lx + dx)
            if not v.buildable(x):
                continue
            for y in rows:
                if 0 <= y < H and v.deploy_cell(x, y):
                    key = ('d', x, y)
                    if self.act.busy(key) or self.act.bad(key):
                        continue
                    self.act.push({'t': 'unit', 'kind': kind, 'x': x, 'y': y}, cost, key,
                                  check=lambda xx=x, yy=y: v.own_mob(xx, yy) is not None)
                    return 'did'
        return 'skip'

    def cast(self, card, x=0, y=0):
        sd = self.v.sd
        free = sd.free.get(card, 0) > 0
        if not free:
            if card not in self.v.deck() or sd.cd.get(card, 0) > 0 or not self.doba_ok(card):
                return False
            cost = self.g.price(self.s, card)[0]
            if self.energy() < cost:
                return False
        else:
            cost = 0
        key = ('c', card)
        if self.act.busy(key):
            return False
        self.act.push({'t': 'card', 'id': card, 'x': x, 'y': y}, cost, key)
        return True

    # ------------------------------------------------ think
    def think(self):
        g = self.g
        self.left = min(self.P['acts'], max(0, 3 - self.act.pending()))
        if self.left <= 0:
            return
        self.adapt()
        self.research()
        self.flush_queue()
        if self.survival:
            steps = (self.s_emergency, self.s_economy, self.s_defence, self.s_faction, self.s_scout, self.s_surv_units,
                     self.s_upgrades)
        else:
            steps = (self.s_emergency, self.s_economy, self.s_defence, self.s_faction, self.s_scout, self.s_attack,
                     self.s_relic, self.s_upgrades)
        saving = False
        for st in steps:
            if self.left <= 0:
                break
            if saving and st == self.s_upgrades:
                break
            r = st()
            if r == 'did':
                self.left -= 1
            elif r == 'wait':
                break
            elif r == 'save':
                saving = True
        self.push_abilities()
        return g.t

    # ------------------------------------------------ 1. emergency
    def threat_rows(self):
        v, s = self.v, self.s
        th = [0.0] * H
        kinds = [None] * H
        for e in v.foes + v.zombies:
            if e.cat not in 'uz' or local_x(s, e.x) > 7:
                continue
            if e.cat == 'z' and e.tgt != s:
                continue
            y = e.cy
            th[y] += e.hp
            k = kinds[y]
            if k is None or DEFS[e.kind]['hp'] > DEFS[k]['hp']:
                kinds[y] = e.kind
        return th, kinds

    def cover_rows(self):
        cov = [0.0] * H
        for b in self.v.blds:
            if b.kind in ATTACK_TOWERS:
                reach = 3 if b.kind == 'sniper' else 1
                d = self.v.dps(b.kind, b.lvl)
                for y in range(max(0, b.cy - reach), min(H, b.cy + reach + 1)):
                    cov[y] += d
        return cov

    def s_emergency(self):
        v = self.v
        th, kinds = self.threat_rows()
        for y in range(H):
            self.threat[y] = max(th[y], self.threat[y] * 0.97)
        if self.P['emerg'] < 1.0 and self.rnd.random() > self.P['emerg']:
            return 'done'
        if v.night() and not self.P['night_build']:
            return 'done'
        cov = self.cover_rows()
        worst, wv = None, 0.0
        for y in range(H):
            need = th[y] - cov[y] * 8.0
            if th[y] >= 120 and need > wv:
                worst, wv = y, need
        if worst is None:
            return 'done'
        k = kinds[worst]
        if v.sab_seen and self.has('hlaska') and not any(b.kind == 'hlaska' and b.path == 'B' for b in v.blds):
            hl = [b for b in v.blds if b.kind == 'hlaska' and b.lvl == 2]
            if hl and self.try_upgrade(hl[0], 'B') == 'did':
                return 'did'
        if k == 'obrnenec' or k == 'dama' or k == 'obr' or k == 'alfa':
            pref = ['sniper', 'kulomet'] if (v.sd.doba >= 2 and self.energy() >= 200) else ['kulomet', 'sniper']
        elif k == 'jezdec':
            pref = ['plamen', 'mina', 'kulomet']
        else:
            pref = ['plamen', 'kulomet']
        pref += ['kulomet', 'plamen', 'tesla', 'sniper']
        kind = next((p for p in pref if self.has(p) and self.doba_ok(p)), None)
        if kind is None:
            return 'done'
        f = self.front_lx()
        for lx, y in ((f - 1, worst), (f - 2, worst), (f - 1, worst - 1), (f - 1, worst + 1), (f, worst)):
            if 0 <= lx and 0 <= y < H:
                r = self.try_build(kind, lx, y)
                if r == 'did':
                    return 'did'
                if r == 'poor':
                    return 'wait'
        return 'done'

    # ------------------------------------------------ 2. economy
    def s_economy(self):
        g, v, P = self.g, self.v, self.P
        n = 0
        for t0, k in P['gens']:
            if g.t >= t0:
                n = k
        gens = v.mine('gen')
        if len(gens) + self.act.queued('build', 'gen') < n:
            for lx in (0, 1):
                for y in self.rows:
                    r = self.try_build('gen', lx, y, misplace=False)
                    if r == 'did':
                        return 'did'
                    if r in ('poor', 'wait'):
                        return 'wait'
        if P['scrap'] and v.sd.job is None and v.sd.s < 60 and not self.act.busy(('scrap',)):
            cells = [(local_x(self.s, x), x, y) for y in range(H) for x in range(W)
                     if v.ter(x, y) == '#' and local_x(self.s, x) <= 5]
            if cells:
                _, x, y = min(cells)
                self.act.push({'t': 'scrap', 'x': x, 'y': y}, 0, ('scrap',))
                return 'did'
        towers = sum(1 for b in v.blds if b.kind in ATTACK_TOWERS)
        l2 = g.t >= P['gen_l2'] or (P['gen_l2_towers'] and towers >= P['gen_l2_towers'])
        l3 = P['gen_l3'] is not None and v.sd.doba >= 2 and g.t >= P['gen_l3']
        for gen in sorted(gens, key=lambda e: (e.lvl, e.id)):
            if (gen.lvl == 1 and l2) or (gen.lvl == 2 and l3):
                r = self.try_upgrade(gen, 'A')
                if r == 'did':
                    return 'did'
                if r == 'poor':
                    return 'wait'
                if r == 'poor_s':
                    if self.P['conv'] != 'never' and self.convert():
                        return 'did'
                    return 'done'
        return 'done'

    # ------------------------------------------------ 3. defence template
    def pace(self):
        n = 0
        for t0, k in PR.TEMPLATE_PACE:
            if self.g.t >= t0:
                n = k
        if self.survival and self.P.get('pace_free'):
            return self.P['def_max']
        return min(self.P['def_max'], int(n * self.P['def_scale'] + 0.5))

    def high_cells(self):
        v = self.v
        return [(lx, y) for lx in (1, 2, 3, 4) for y in self.rows if v.ter(self.rx(lx), y) == '^']

    def s_defence(self):
        v = self.v
        if v.night() and not self.P['night_build']:
            return 'done'
        if v.night() and self.P['night_line']:
            r = self.night_line()
            if r != 'done':
                return r
        allowed = self.pace()
        done = 0
        highs = self.high_cells()
        for kind, lx, y in self.extra + self.tmpl:
            if not self.has(kind):
                continue
            x = self.rx(lx)
            if not v.buildable(x):
                continue
            b = v.own_bld(x, y)
            if b is not None:
                done += 1
                continue
            if done >= allowed:
                return 'done'
            if kind in ('sniper', 'hlaska'):
                for hx, hy in highs:
                    if v.free_cell(self.rx(hx), hy) and v.buildable(self.rx(hx)):
                        lx, y = hx, hy
                        break
            if v.ter(self.rx(lx), y) not in BUILD:
                continue
            if kind == 'sniper' and self.g.price(self.s, 'sniper')[0] > 260:
                continue
            r = self.try_build(kind, lx, y)
            if r == 'did':
                return 'did'
            if r in ('poor', 'wait'):
                return 'wait'
        return self.s_surplus()

    def night_line(self):
        """Poslední noc: the Mist eats the board from the middle, so the last towers standing are the ones at local
        x 0-1. Fill their free cells with Kulomet/Plamenomet."""
        v = self.v
        nk, npl = v.count('kulomet'), v.count('plamen')
        kind = 'plamen' if self.has('plamen') and npl * 2 < nk else 'kulomet'
        for lx in (1, 0):
            x = self.rx(lx)
            if not v.buildable(x):
                continue
            for y in self.rows:
                if v.free_cell(x, y):
                    r = self.try_build(kind, lx, y, misplace=False)
                    if r == 'did':
                        return 'did'
                    if r in ('poor', 'wait'):
                        return 'wait'
        return 'done'

    def s_surplus(self):
        """Template complete and energy to spare: extra Kulomet/Plamenomet in the free cells of local x 1-4
        (front column first), up to P['surplus'] of them. Defence in depth for the eclipses and the night."""
        g, v, P = self.g, self.v, self.P
        if not P['surplus'] or g.t < 240 or self.energy() < 350:
            return 'done'
        extra = sum(1 for b in v.blds if b.kind in ('kulomet', 'plamen') and local_x(self.s, b.cx) == 4) +             len(self.surplus_cells)
        if extra >= P['surplus']:
            return 'done'
        nk, npl = v.count('kulomet'), v.count('plamen')
        kind = 'plamen' if self.has('plamen') and npl * 2 < nk else 'kulomet'
        for lx in (4, 3, 2, 1):
            for y in self.rows:
                x = self.rx(lx)
                if v.buildable(x) and v.free_cell(x, y) and (lx, y) not in self.surplus_cells:
                    r = self.try_build(kind, lx, y, misplace=False)
                    if r == 'did':
                        if lx != 4:
                            self.surplus_cells.add((lx, y))
                        return 'did'
                    if r in ('poor', 'wait'):
                        return 'wait'
        return 'done'

    # ------------------------------------------------ 4. scouting
    def s_scout(self):
        g, v, P = self.g, self.v, self.P
        hl = v.mine('hlaska')
        if P['scout'] >= 2 and g.t >= 120 and len(hl) < 2 and self.has('hlaska'):
            for lx, y in ((3, 2), (3, 6), (2, 2)):
                r = self.try_build('hlaska', lx, y, misplace=False)
                if r == 'did':
                    return 'did'
                if r == 'poor':
                    break
        if g.t >= 90:
            for h in hl:
                if h.lvl == 1 and self.energy() >= 80:
                    if self.try_upgrade(h) == 'did':
                        return 'did'
        want_b = v.sab_seen or (v.mine_hint > 0 and g.t - v.mine_hint < 120)
        if P['reflektor']:
            e = v.eclipse()
            want_b = want_b or (e[0] == 1 and e[1] <= 60)
        if want_b and not any(h.path == 'B' for h in hl):
            for h in hl:
                if h.lvl == 2 and self.try_upgrade(h, 'B') == 'did':
                    return 'did'
        if P['drone_every'] and 'dron' in v.deck() and g.t >= self.next_drone:
            if self.cast('dron', self.rx(12), 4):
                self.next_drone = g.t + P['drone_every']
                return 'did'
        return 'done'

    # ------------------------------------------------ 5. attack
    def lane_pick(self):
        v = self.v
        if self.P['lane'] == 'random':
            ok = [y for y in range(1, H - 1) if self.cross[y]] or list(range(1, H - 1))
            return ok[self.rnd.randrange(len(ok))]
        towers = v.foe_towers()
        power = [0.0] * H
        for kind, tx, ty, lvl, path in towers:
            r = DEFS[kind].get('range', 2) + (lvl - 1) * 0.2
            for y in range(H):
                if abs(ty - y) <= r:
                    power[y] += v.dps(kind, lvl)
        best, bv = 4, None
        for c in range(1, H - 1):
            p = power[c - 1] + power[c] + power[c + 1] - 2.0 * self.row_w[c]
            if self.v.map_random() is False and self.row_w[c] == 0:
                p += 1000
            if not self.cross[c]:
                p += 1000
            if bv is None or p < bv - 1e-9:
                best, bv = c, p
        return best

    def comp(self):
        v = self.v
        ks = {}
        for kind, *_ in v.foe_towers():
            ks[kind] = ks.get(kind, 0) + 1
        if ks.get('sniper', 0) >= 3:
            name = 'tank'
        elif ks.get('plamen', 0) >= 2:
            name = 'flank'
        elif v.mine_hint > 0 and self.g.t - v.mine_hint < 150:
            name = 'mines'
        else:
            name = 'mix'
        c = [k for k in PR.COMPS[name] if k in v.deck()]
        c = c or [k for k in PR.COMPS['mix'] if k in v.deck()]
        return self.fp.comp(name, c) if self.fp is not None else c

    def queue_units(self, comp, energy, cap=12):
        g = self.g
        q, i = [], 0
        rows = [y for y in (self.lane, self.lane - 1, self.lane + 1, self.lane - 2, self.lane + 2) if 0 <= y < H]
        rows = [y for y in rows if self.cross[y]] or rows
        while comp and len(q) < cap:
            k = comp[i % len(comp)]
            c = g.price(self.s, k)[0]
            if energy < c:
                break
            q.append([k, g.t + PR.STAGGER.get(k, 0.0), rows])
            energy -= c
            i += 1
        self.queue += q
        return len(q)

    def flush_queue(self):
        if not self.queue or self.left <= 0:
            return
        t = self.g.t
        left = []
        for it in self.queue:
            k, due, rows = it
            if due > t or self.left <= 0:
                left.append(it)
                continue
            r = self.try_deploy(k, rows)
            if r == 'did':
                self.left -= 1
            elif t - due < 8:
                left.append(it)
        self.queue = left

    def s_attack(self):
        g, v, P = self.g, self.v, self.P
        sd = v.sd
        if self.queue:
            return 'done'
        if not self.rushed and 70 <= g.t <= 95:
            if sum(1 for k in v.foe_towers() if k[0] in ATTACK_TOWERS) < 2:
                self.lane = self.lane_pick()
                self.queue_units(['pesak', 'pesak', 'pesak', 'pesak', 'obrnenec'], self.energy())
                self.rushed = True
                self.next_push = g.t + 45
                return 'did'
        if g.t >= 95:
            self.rushed = True
        if g.t < self.next_push:
            return 'done'
        t0, floor, secs = P['push']
        budget = max(floor, g.income(self.s) * secs)
        night = v.night()
        if night and P['allin']:
            budget = 60.0
        elif self.ecl_push or self.turtle_timing:
            # eclipse timing: the tanks leave at E - 18 s so the push meets the darkness at the enemy front
            e = v.eclipse()
            if e[0] == 1 and 18 < e[1] <= 30:
                return 'save'
            if self.turtle_timing and not (e[0] == 2 or (e[0] == 1 and e[1] <= 18)) \
                    and self.energy() < budget * 2:
                return 'done'
        if self.energy() < budget:
            return 'save'
        self.lane = self.lane_pick()
        e = self.energy()
        if P['spend'] and not night:
            e = min(e, budget * P['spend'])
        hc = g.horde_cost(self.s)[0]
        if P['horde'] != 'never' and sd.horde_cd < 10:
            e -= hc
        cap = P['cap'] * (2 if night and P['allin'] else 1)
        n = self.queue_units(self.comp(), e, cap=cap)
        if not n:
            return 'done'
        self.push_n += 1
        self.horde_pending = P['horde'] != 'never'
        self.ecl_push = self.rnd.random() < P['ecl_p']
        self.next_push = g.t + (min(25.0, P['regap']) if night else P['regap'])
        if sd.free.get('mobilizace', 0) > 0:
            self.cast('mobilizace')
        self.flush_queue()
        return 'did'

    def push_abilities(self):
        """During a push: Tlupa, Výpadek, Nálet (MAI 5.4)."""
        g, v, P = self.g, self.v, self.P
        sd = v.sd
        if P['horde_spare'] and sd.horde_cd <= 0 and not self.act.busy(('horde',)):
            # rich (or Poslední noc): every ready Tlupa goes out - its zombies chip the enemy throne
            hc = g.horde_cost(self.s)[0]
            if self.energy() >= hc + (0 if v.night() else P['horde_spare']):
                self.act.push({'t': 'horde'}, hc, ('horde',))
        if self.fp is not None:
            self.fp.abilities()
        if self.survival:
            self.zombie_nalet()
        units = v.units
        if not units:
            return
        foe = self.foe
        pos = [local_x(foe, e.x) for e in units]
        if self.horde_pending and sd.horde_cd <= 0:
            go = P['horde'] == 'push' or any(p <= 9 for p in pos)
            if go and self.energy() >= g.horde_cost(self.s)[0] and not self.act.busy(('horde',)):
                self.act.push({'t': 'horde'}, g.horde_cost(self.s)[0], ('horde',))
                self.horde_pending = False
        front = sum(1 for p in pos if p <= 6)
        if P['cards'] != 'nalet' and front >= 3:
            self.cast('vypadek')
        if any(p <= 8 for p in pos):
            self.nalet()

    def nalet(self):
        v = self.v
        sd = v.sd
        if not ('nalet' in v.deck() or sd.free.get('nalet', 0) > 0):
            return
        blds = [b for b in v.foe_buildings() if b.kind != 'mina']
        if not blds:
            return
        smart = self.P['cards'] == 'smart'
        best, bv = None, 0.0
        for b in blds:
            val = sum((2 if o.kind == 'hlaska' else 1) for o in blds if abs(o.cx - b.cx) <= 1 and abs(o.cy - b.cy) <= 1)
            val -= 0.5 * sum(1 for o in v.units if abs(o.x - b.cx) <= 1.5 and abs(o.y - b.cy) <= 1.5)
            if smart:
                val += 0.5 * sum(1 for o in v.foes if o.cat == 'u' and abs(o.x - b.cx) <= 1.5 and abs(o.y - b.cy) <= 1.5)
            if val > bv:
                best, bv = b, val
        if best is not None and bv >= 2:
            self.cast('nalet', best.cx, best.cy)

    # ------------------------------------------------ 6. relic
    def relic_rows(self):
        x0, x1, y0, y1 = self.v.relic_box()
        c = (y0 + y1 + 1) // 2
        return c, max(y0, c - 1)

    def s_relic(self):
        g, v, P = self.g, self.v, self.P
        rl = v.relic()
        if not rl['on']:
            return 'done'
        s, foe = self.s, self.foe
        c, c2 = self.relic_rows()
        if P['relic'] == 'lehka':
            if g.t < 300 or rl['own'] == s or g.t < self.last_relic_lehka + 60:
                return 'done'
            self.last_relic_lehka = g.t
            if g.mode == 'strateg':
                self.queue.append(['pesak', g.t, [c, c2]])
            return 'done'
        threat = rl['own'] == s and rl['by'] == foe and rl['p'] > 0
        if rl['own'] == s and not threat:
            return 'done'
        if g.t < self.next_sq or self.queue:
            return 'done'
        en_route = sum(1 for e in v.units if 3 <= local_x(s, e.x) <= 8)
        foes_mid = sum(1 for e in v.foes if e.cat == 'u' and 6 <= e.cx <= 9)
        if foes_mid > 3:
            return 'done'
        if threat:
            if en_route == 0 and self.energy() >= 30:
                self.queue.append(['pesak', g.t, [c, c2]])
                self.next_sq = g.t + 8
            return 'done'
        if en_route > 1:
            return 'done'
        if self.energy() < 170:
            return 'save'
        self.next_sq = g.t + 30
        if g.mode == 'strateg' and self.squad_msg:
            if v.sd.cd.get('squad', 0) <= 0:
                self.act.push({'t': 'squad', 'id': 'relic'}, 0, ('squad',))
                return 'did'
            return 'done'
        self.squad_queue(c, c2)
        return 'did'

    def squad_queue(self, c, c2):
        """Obrněnec + 2 Pěšák (or the 3 cheapest units of the deck), staggered 0/4/5 s (SPEC 4.4)."""
        g, v = self.g, self.v
        deck = v.deck()
        if 'obrnenec' in deck and 'pesak' in deck:
            kinds = ['obrnenec', 'pesak', 'pesak']
        else:
            units = sorted([k for k in deck if DEFS[k]['cat'] == 'u'],
                           key=lambda k: (DEFS[k]['cost'][0], UNIT_KINDS.index(k)))[:3]
            kinds = units
        if self.fp is not None:
            kinds = self.fp.squad_kinds(kinds)
        for k, dt, row in zip(kinds, (0.0, 4.0, 5.0), (c, c, c2)):
            self.queue.append([k, g.t + dt, [row, c, c2]])

    # ------------------------------------------------ 8. upgrades
    def s_upgrades(self):
        v = self.v
        if self.energy() < 120:
            return 'done'
        cand = [b for b in v.blds if (b.kind in ATTACK_TOWERS or b.kind == 'zed') and b.lvl < self.P['upg_max']
                and not (b.kind == 'zed' and b.lvl >= 2) and v.buildable(b.cx)]
        if not cand:
            return 'done'
        cand.sort(key=lambda b: (-self.threat[b.cy], b.lvl, b.id))
        nsn = v.count('sniper')
        for b in cand[:4]:
            path = ('A' if nsn >= 3 else 'B') if b.kind == 'sniper' else PR.UP_PATH.get(b.kind, 'A')
            r = self.try_upgrade(b, path)
            if r == 'did':
                return 'did'
            if r == 'poor_s' and self.P['conv'] == 'yes':
                if self.convert():
                    return 'did'
        return 'done'

    # ------------------------------------------------ faction rules (facplay.py)
    def s_faction(self):
        return self.fp.step() if self.fp is not None else 'done'

    # ------------------------------------------------ Přežití: units only for crates and the own Mist half
    def s_surv_units(self):
        g, v, P, s = self.g, self.v, self.P, self.s
        if self.queue:
            return 'done'
        # clearing the own half of the Mist: tanks first (zombies are slow, the units fight at the edge of the towers' range)
        zs = [z for z in v.zombies if z.tgt == s and 6 <= local_x(s, z.x) <= 7.6]
        if len(zs) >= P['clear_n'] and g.t >= self.next_clear and self.energy() >= P['clear_e'] and len(v.units) < 3:
            row = sorted(zs, key=lambda z: z.id)[0].cy
            rows = [y for y in (row, row - 1, row + 1) if 0 <= y < H]
            kinds = [k for k in ('obrnenec', 'pesak') if k in v.deck() and self.doba_ok(k)]
            if kinds:
                for k in (kinds[0], kinds[0], 'pesak' if 'pesak' in kinds else kinds[0]):
                    self.queue.append([k, g.t, rows])
                self.next_clear = g.t + 30.0
                return 'did'
        if not P.get('runner') or 'pesak' not in v.deck():
            return 'done'
        mid = 7 if s == 0 else 8
        k = v.king()
        for c in sorted(v.crates(), key=lambda c: c['id']):
            if c['x'] != mid or c['land'] > 8.0 or c['id'] in self.runner_for:
                continue
            if g.mode == 'kral':
                if k is not None and k.hp >= 0.6 * k.maxhp and (k.x - c['x']) ** 2 + (k.y - c['y']) ** 2 <= 36:
                    continue
            elif v.sd.cd.get('cmd_sber', 0) <= 0:
                continue
            if any(abs(u.y - c['y']) <= 1 and local_x(s, u.x) >= 3 for u in v.units):
                continue
            if self.energy() < 60:
                break
            self.runner_for.add(c['id'])
            rows = [y for y in (c['y'], c['y'] - 1, c['y'] + 1) if 0 <= y < H]
            self.queue.append(['pesak', g.t, rows])
            return 'did'
        return 'done'

    def zombie_nalet(self):
        """Nálet on a 3x3 with >= 4 zombies that march on us, still outside the walls (Střední and Těžká)."""
        v, s = self.v, self.s
        if self.P['cards'] == 'nalet' or not ('nalet' in v.deck() or v.sd.free.get('nalet', 0) > 0):
            return
        zs = [z for z in v.zombies if z.tgt == s and z.kind != 'alfa' and local_x(s, z.x) >= 4]
        if len(zs) < 4:
            return
        best, bn = None, 0
        for c in sorted(zs, key=lambda z: z.id):
            n = sum(1 for o in zs if abs(o.x - c.x) <= 1.5 and abs(o.y - c.y) <= 1.5)
            if n > bn:
                best, bn = c, n
        if best is not None and bn >= 4:
            self.cast('nalet', best.cx, best.cy)

    # ------------------------------------------------ 9. research
    def rcost(self, rid):
        """Research cost for this side (a faction may discount it); falls back to the table."""
        if self._rc is None:
            try:
                self._rc = dict(self.g.start_info(self.s).get('rcost') or {})
            except Exception:
                self._rc = {}
        return self._rc.get(rid, RESEARCH[rid]['cost'])

    def research(self):
        sd = self.v.sd
        for rid in self.res_order:
            if rid in sd.techs:
                continue
            r = RESEARCH[rid]
            if sd.v >= self.rcost(rid) and not self.act.busy(('r', rid)):
                if r['tier'] == 1 or '%s%d' % (r['branch'], r['tier'] - 1) in sd.techs:
                    self.act.push({'t': 'res', 'id': rid}, 0, ('r', rid))
                    self.left -= 1
            return

    # ------------------------------------------------ adaptation (Těžká)
    def adapt(self):
        g, v = self.g, self.v
        if not self.P['adapt']:
            return
        for at in (180, 360):
            if g.t >= at and at not in self.adapted:
                self.adapted.add(at)
                ks = v.kinds_seen
                if ks.get('sniper', 0) >= 3:
                    self.turtle_timing = True
                if sum(ks.get(k, 0) for k in UNIT_KINDS) >= 4 and at == 180:
                    f = 3
                    self.extra = [('plamen', f, self.rows[1]), ('plamen', f, self.rows[2]),
                                  ('kulomet', f, self.rows[0])]
