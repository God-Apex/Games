"""Rule variants, applied by monkeypatching the imported server module (never the file).
Tunables and price functions are set through H.setc (hmk.defs on 1.0), methods on S.Game (mixins included).

A variant string is names joined by '+', e.g. 'sn_cost50+obr_armor50'. Numbers inside a name are parameters.
"""
import re

import harness as H

S = H.S


def _num(name, default):
    m = re.search(r'(\d+)$', name)
    return int(m.group(1)) if m else default


# ------------------------------------------------ sniper nerfs
def sn_cost(name):
    """Every Odstřelovač after the first `free` costs `inc` more (like generators)."""
    inc = _num(name, 50)
    free = 2
    m = re.match(r'sn_cost(\d+)f(\d+)', name)
    if m:
        inc, free = int(m.group(1)), int(m.group(2))

    def price_of(self, s, kind, base):
        if kind == 'sniper':
            return base + inc * max(0, self.count(s, 'sniper') - (free - 1))
        return base
    build0 = S.Game.build

    def build(self, s, kind, x, y):
        if kind != 'sniper':
            return build0(self, s, kind, x, y)
        d = S.DEFS['sniper']
        old = d['cost'][0]
        d['cost'][0] = self.price_of(s, kind, old)
        try:
            return build0(self, s, kind, x, y)
        finally:
            d['cost'][0] = old
    S.Game.price_of = price_of
    S.Game.build = build


def sn_dmg(name):
    S.DEFS['sniper']['dmg'] = _num(name, 55)


def sn_rate(name):
    S.DEFS['sniper']['rate'] = _num(name, 35) / 10.0


def sn_aim(name):
    S.DEFS['sniper']['aim'] = _num(name, 10) / 10.0


def sn_range(name):
    S.DEFS['sniper']['range'] = _num(name, 60) / 10.0


def sn_hp(name):
    S.DEFS['sniper']['hp'] = _num(name, 110)


def sn_min(name):
    """Odstřelovač cannot target anything closer than `r` cells (it needs distance to aim)."""
    r = _num(name, 20) / 10.0
    foes0 = S.Game.foes_in

    def foes_in(self, e, r2):
        out = foes0(self, e, r2)
        if e.kind == 'sniper':
            out = [o for o in out if (o.x - e.cx) ** 2 + (o.y - e.cy) ** 2 >= r * r]
        return out
    S.Game.foes_in = foes_in


def sn_smart(name):
    """No overkill: a sniper skips targets that already have enough aimed damage incoming (makes snipers STRONGER)."""
    tower0 = S.Game.tower

    def tower(self, e, dt):
        if e.kind != 'sniper' or e.aim is not None or e.cd - dt > 0 or self.sd[e.side].outage > 0:
            return tower0(self, e, dt)
        foes0 = self.foes_in
        dmg = self.dmg_of(e)
        incoming = {}
        for o in self.ents.values():
            if o.kind == 'sniper' and o.side == e.side and o.aim is not None:
                incoming[o.aim.id] = incoming.get(o.aim.id, 0) + self.dmg_of(o)

        def foes_in(ee, r2):
            out = foes0(ee, r2)
            keep = [f for f in out if incoming.get(f.id, 0) < f.hp]
            return keep or out
        self.foes_in = foes_in
        try:
            return tower0(self, e, dt)
        finally:
            del self.foes_in
    S.Game.tower = tower


def sn_zpref(name):
    """Odstřelovač shoots zombies first when any is in range."""
    foes0 = S.Game.foes_in

    def foes_in(self, e, r2):
        out = foes0(self, e, r2)
        if e.kind == 'sniper':
            z = [o for o in out if o.cat == 'z']
            return z or out
        return out
    S.Game.foes_in = foes_in


def sn_near(name):
    """Odstřelovač shoots the nearest target instead of the healthiest one."""
    tower0 = S.Game.tower

    def tower(self, e, dt):
        if e.kind != 'sniper':
            return tower0(self, e, dt)
        foes0 = self.foes_in

        def foes_in(ee, r2):
            out = foes0(ee, r2)
            if out and ee.aim is None:
                o = min(out, key=lambda f: (f.x - ee.cx) ** 2 + (f.y - ee.cy) ** 2)
                o_hp = o.hp
                return [o] + [f for f in out if f is not o and f.hp < o_hp]  # max(hp) picks o
            return out
        self.foes_in = foes_in
        try:
            return tower0(self, e, dt)
        finally:
            del self.foes_in
    S.Game.tower = tower


# ------------------------------------------------ unit buffs
def obr_armor(name):
    """Obrněnec takes `p` % less damage from Odstřelovač (or from all ranged fire with obr_rarmor)."""
    p = _num(name, 50) / 100.0
    all_ranged = name.startswith('obr_rarmor')
    dmg0 = S.Game.damage

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if not isinstance(tgt, int) and tgt.kind == 'obrnenec' and src is not None:
            if (src.kind == 'sniper') or (all_ranged and ranged):
                amount *= 1.0 - p
        return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
    S.Game.damage = damage


def u_armor(name):
    """All units take `p` % less damage from Odstřelovač."""
    p = _num(name, 30) / 100.0
    dmg0 = S.Game.damage

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if not isinstance(tgt, int) and tgt.cat == 'u' and src is not None and src.kind == 'sniper':
            amount *= 1.0 - p
        return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
    S.Game.damage = damage


def u_hp(name):
    p = _num(name, 30) / 100.0
    for k in H.UNIT_KINDS:
        S.DEFS[k]['hp'] = round(S.DEFS[k]['hp'] * (1 + p))


def obr_hp(name):
    S.DEFS['obrnenec']['hp'] = _num(name, 600)


def u_speed(name):
    p = _num(name, 20) / 100.0
    for k in H.UNIT_KINDS:
        S.DEFS[k]['step'] = S.DEFS[k]['step'] * (1 - p)


def throne(name):
    """Units deal `m`x damage to the throne."""
    m = _num(name, 3)
    dmg0 = S.Game.damage

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if isinstance(tgt, int) and src is not None and src.cat == 'u':
            amount *= m
        return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
    S.Game.damage = damage


def z_bld(name):
    """Zombies deal `m`x damage to buildings (turtles suffer more)."""
    m = _num(name, 2)
    for k in ('chodec', 'bezec'):
        S.DEFS[k]['bld'] = float(m)
    S.DEFS['obr']['bld'] = 3.0 * m / 2


def obr_bld(name):
    S.DEFS['obrnenec']['bld'] = _num(name, 40) / 10.0


def sn_pierce(name):
    """Path A (Průstřel) hits n targets instead of 3."""
    n = _num(name, 2)
    foes0 = S.Game.foes_in
    tower0 = S.Game.tower

    def tower(self, e, dt):
        if e.kind != 'sniper' or e.path != 'A' or e.aim is None:
            return tower0(self, e, dt)

        def foes_in(ee, r2):
            out = foes0(self, ee, r2)
            aim = ee.aim
            rest = sorted((f for f in out if f is not aim), key=lambda f: -f.hp)[:n - 1]
            return rest
        self.foes_in = foes_in
        try:
            return tower0(self, e, dt)
        finally:
            del self.foes_in
    S.Game.tower = tower


def hl_vis(name):
    """Hláska vision: lvl3 path A (Dalekohled) = v/10 instead of 7."""
    v = _num(name, 55) / 10.0
    vis0 = S.Game.vision

    def vision(self, e):
        if e.kind == 'hlaska' and e.path == 'A':
            r = v
            if 'ing3' in self.techs(e.side):
                r += 0.5
            return r
        return vis0(self, e)
    S.Game.vision = vision


def sn_lvl(name):
    """Sniper damage per level: x1.0 / x(1+a) / x(1+2a) with a = n/100 instead of 1.35 / 1.7."""
    a = _num(name, 15) / 100.0
    dmg0 = S.Game.dmg_of

    def dmg_of(self, e):
        if e.kind == 'sniper':
            return S.DEFS['sniper']['dmg'] * (1 + a * (e.lvl - 1))
        return dmg0(self, e)
    S.Game.dmg_of = dmg_of


def sn_cap(name):
    """At most n Odstřelovač per player (like Hlídka)."""
    n = _num(name, 4)
    build0 = S.Game.build

    def build(self, s, kind, x, y):
        if kind == 'sniper' and self.count(s, 'sniper') >= n:
            return self.say('Odstřelovačů smíš mít nejvýš %d.' % n, s)
        return build0(self, s, kind, x, y)
    S.Game.build = build


# ------------------------------------------------ economy / misc
def up_s(name):
    """Level 2->3 (path) upgrade costs n scrap instead of 35 (all buildings except Zeď)."""
    n = _num(name, 25)
    for k, d in S.DEFS.items():
        if d['cat'] == 'b' and k != 'zed' and 'up' in d:
            d['up'][1][1] = n


def ecap(name):
    """Energy storage capped at n."""
    cap = _num(name, 2000)
    t0 = S.Game.timers

    def timers(self, dt):
        t0(self, dt)
        for sd in self.sd:
            if sd.e > cap:
                sd.e = cap
    S.Game.timers = timers


def sn_mist(name):
    """Odstřelovač cannot target anything standing in the Mist farther than r/10 cells (the Mist hides it)."""
    r = _num(name, 0) / 10.0
    foes0 = S.Game.foes_in

    def foes_in(self, e, r2):
        out = foes0(self, e, r2)
        if e.kind == 'sniper':
            out = [o for o in out if not self.in_mist(o.cx) or (o.x - e.cx) ** 2 + (o.y - e.cy) ** 2 <= r * r]
        return out
    S.Game.foes_in = foes_in


def tw_value(g, s):
    return sum(e.spent[0] for e in g.ents.values() if e.side == s and e.kind in S.ATTACK_TOWERS)


def z_turtle(name):
    """Mist zombies go for noise: every wave sends +1 extra zombie per n energy of attack towers the bigger
    builder has over the other player, and the Alfa hunts the bigger builder."""
    n = _num(name, 400)
    wave0 = S.Game.wave

    def wave(self):
        wave0(self)
        v = [tw_value(self, 0), tw_value(self, 1)]
        big = 0 if v[0] > v[1] else 1
        extra = int((v[big] - v[1 - big]) // n)
        if extra > 0:
            self.spawn_zombies(['chodec'] * extra, (6, 7) if big == 0 else (9, 8), big)
    S.Game.wave = wave


def unit_bld(name):
    """All units deal m/10 x damage to buildings (on top of their own multiplier)."""
    m = _num(name, 15) / 10.0
    dmg0 = S.Game.damage

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if not isinstance(tgt, int) and tgt.cat == 'b' and src is not None and src.cat == 'u':
            amount *= m
        return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
    S.Game.damage = damage


def night(name):
    """Poslední noc: thrones lose n/10 x more for every 500 energy of attack towers the player owns."""
    k = _num(name, 10) / 10.0
    t0 = S.Game.timers

    def timers(self, dt):
        before = list(self.throne)
        t0(self, dt)
        if self.night:
            for s in (0, 1):
                d = before[s] - self.throne[s]
                if d > 0:
                    self.throne[s] -= d * k * tw_value(self, s) / 500.0
    S.Game.timers = timers


def smoke(name):
    """Dýmovnice (bot-only ability, no card slot): 40 energy, cooldown 15 s. A 3x3 cloud for 6 s:
    the enemy cannot see into it, so his towers cannot shoot there."""
    S.SMOKE = {'cost': 40, 'cd': 15.0, 'dur': 6.0}
    cv0 = S.Game.compute_vis
    t0 = S.Game.timers

    def compute_vis(self, side, ents):
        vis = cv0(self, side, ents)
        for s2, x, y, t in getattr(self, 'smokes', []):
            if s2 == side:
                continue
            for yy in range(max(0, y - 1), min(S.H, y + 2)):
                for xx in range(max(0, x - 1), min(S.W, x + 2)):
                    vis[yy][xx] = False
        return vis

    def timers(self, dt):
        t0(self, dt)
        self.smokes = [[s2, x, y, t - dt] for s2, x, y, t in getattr(self, 'smokes', []) if t - dt > 0]
    S.Game.compute_vis = compute_vis
    S.Game.timers = timers


def medshield(name):
    """Medik also shields: own units within 1.5 cells of a Medik take p % less damage from towers / ranged fire."""
    p = _num(name, 30) / 100.0
    dmg0 = S.Game.damage

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if not isinstance(tgt, int) and tgt.cat == 'u' and ranged:
            if any(o.kind == 'medik' and o.side == tgt.side and o is not tgt and (o.x - tgt.x) ** 2 + (o.y - tgt.y) ** 2 <= 2.25
                   for o in self.ents.values()):
                amount *= 1.0 - p
        return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
    S.Game.damage = damage


def night2(name):
    """Poslední noc: drain 5 + 0.2/s (thrones fall ~150 s after nightfall instead of ~217 s) and a tie-break:
    if both thrones fall in the same tick, the player with more kills (zombies + units) wins."""
    t0 = S.Game.timers
    step0 = S.Game.step

    def timers(self, dt):
        before = list(self.throne)
        was = self.night
        t0(self, dt)
        if self.night:
            el = self.t - self.length
            extra = ((5.0 + el * 0.2) - (3.0 + el * 0.1)) * dt
            for s in (0, 1):
                self.throne[s] -= extra

    def step(self, dt):
        step0(self, dt)
        if self.over and self.over.get('winner') == -1:
            k = [self.sd[0].stats['kills'], self.sd[1].stats['kills']]
            if k[0] != k[1]:
                w = 0 if k[0] > k[1] else 1
                self.over = {'winner': w, 'reason': 'Poslední noc: oba trůny padly, víc zabil hráč %s.' % self.names[w]}
    S.Game.timers = timers
    S.Game.step = step


def night3(name):
    """Poslední noc: drain 5 + 0.2/s (~150 s instead of ~217 s) and, if both thrones fall in the same tick,
    the player who dealt more damage to the opponent's throne and buildings during the game wins."""
    t0 = S.Game.timers
    step0 = S.Game.step
    dmg0 = S.Game.damage

    def timers(self, dt):
        t0(self, dt)
        if self.night:
            el = self.t - self.length
            extra = ((5.0 + el * 0.2) - (3.0 + el * 0.1)) * dt
            for s in (0, 1):
                self.throne[s] -= extra

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if src_side in (0, 1):
            if isinstance(tgt, int):
                if tgt != src_side:
                    before = self.throne[tgt]
                    dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
                    self.dealt = getattr(self, 'dealt', [0.0, 0.0])
                    self.dealt[src_side] += before - self.throne[tgt]
                    return
            elif tgt.cat == 'b' and tgt.side == 1 - src_side and not tgt.dead:
                before = tgt.hp
                dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
                self.dealt = getattr(self, 'dealt', [0.0, 0.0])
                self.dealt[src_side] += min(before, before - tgt.hp)
                return
        return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)

    def step(self, dt):
        step0(self, dt)
        if self.over and self.over.get('winner') == -1:
            d = getattr(self, 'dealt', [0.0, 0.0])
            if abs(d[0] - d[1]) >= 1:
                w = 0 if d[0] > d[1] else 1
                self.over = {'winner': w, 'reason': 'Poslední noc: oba trůny padly, víc škody nadělal hráč %s.' % self.names[w]}
    S.Game.timers = timers
    S.Game.step = step
    S.Game.damage = damage


def sn_rtie(name):
    """Odstřelovač breaks ties between equally healthy targets at random (instead of lowest entity id)."""
    import random as _r
    foes0 = S.Game.foes_in

    def foes_in(self, e, r2):
        out = foes0(self, e, r2)
        if e.kind == 'sniper':
            _r.shuffle(out)
        return out
    S.Game.foes_in = foes_in




# ------------------------------------------------ 0.5 ablations: switch one new rule back off
def x05(name):
    if name == 'xpromo':
        S.Game.promote = lambda self, e: None
    elif name == 'xrelic':
        S.Game.relic_tick = lambda self, dt: None
    elif name == 'xcrate':
        def post_init(self):
            self.next_crate, self.crate_n = 75.0, 1
        S.Game.post_init = post_init
    elif name == 'xcry':
        S.Game.cry = lambda self, e: 1.0
    elif name == 'xconv':
        S.Game.convert = lambda self, s: None
    elif name == 'xsnp':
        H.setc('sniper_price', lambda n: 100)
    elif name == 'xtgt':                  # old target tie-break: lowest entity id
        S.Game.near_key = lambda self, side, x, y: (lambda o: (o.id,))
    elif name == 'xarm':                  # Pancíř not against the throne gun (study version)
        dmg0 = S.Game.damage

        def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
            if not isinstance(tgt, int) and tgt.kind == 'obrnenec' and ranged and src is None:
                amount /= 0.6
            return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
        S.Game.damage = damage
    elif name == 'xconvbot':              # nobody can afford Přetavení (bots never use it)
        H.setc('CONV', (10 ** 9, 10))
    elif name == 'xutok':                 # Útok! without effect (war cry unchanged)
        def cry(self, e):
            if e.cat != 'u':
                return 1.0
            sd = self.sd[e.side]
            k = sd.kral
            return 0.4 if sd.ult_t > 0 and k and (k.x - e.x) ** 2 + (k.y - e.y) ** 2 <= 9 else 1.0
        S.Game.cry = cry
    elif name == 'xchan':                 # crates picked up at once (no 3 s channel)
        H.setc('CRATE_CH', 0.001)
    elif name == 'xecl':
        S.Game.dark = lambda self: self.night
    elif name.startswith('xvet'):          # xvet: no veterans from kills; xvetz: zombies do not count; xvet5: need 5 kills
        need = _num(name, 3) if name[-1].isdigit() else (10 ** 9 if name == 'xvet' else 3)
        kill0 = S.Game.kill

        def kill(self, e, src_side, src=None):
            if src is not None and getattr(src, 'cat', '') == 'u' and src.side != e.side and not src.dead:
                k = src.kills
                if name == 'xvetz' and e.cat == 'z':
                    k -= 1
                src.kills = -10 ** 9
                kill0(self, e, src_side, src)
                src.kills = k + 1
                if src.kills >= need and not src.vet:
                    self.make_vet(src)
                return
            return kill0(self, e, src_side, src)
        S.Game.kill = kill
    else:
        raise ValueError(name)



# ------------------------------------------------ 0.5 candidate fixes
def fix05(name):
    if name == 'fpromo':                  # promotion keeps the hp fraction; only into a Dáma (none if the side has one)
        def promote(self, e):
            if self.count(e.side, 'dama'):
                return
            frac = e.hp / e.maxhp
            self.remove(e)
            n = self.spawn('dama', e.side, e.cx, e.cy)
            n.hp = max(1.0, n.maxhp * frac)
            n.kills, n.fast = e.kills, e.fast
            n.x, n.y, n.ax, n.ay, n.at, n.adur = e.x, e.y, e.ax, e.ay, e.at, e.adur
            self.fx.append(['P', e.cx, e.cy, 0, 0, e.side])
            self.event(None, 'promo', e.side)
        S.Game.promote = promote
    elif name == 'fhp':                   # promotion keeps the hp fraction (Obrněnec fallback kept)
        p0 = S.Game.promote

        def promote(self, e):
            frac = e.hp / e.maxhp
            p0(self, e)
            n = self.mob[e.cy][e.cx]
            if n is not None and n.side == e.side:
                n.hp = max(1.0, n.maxhp * frac)
        S.Game.promote = promote
    elif name == 'fcrr':                  # first crate at 40 s, normal rarity roll
        dc = S.Game.drop_crate

        def drop_crate(self, x=None, y=None, rarity=None, land=10.0, min_rar=0):
            return dc(self, x, y, rarity, land, 0)
        S.Game.drop_crate = drop_crate
    elif name.startswith('fcd'):          # Přetavení cooldown fcd4 = once per 4 s
        cd = float(_num(name, 1))
        c0 = S.Game.convert

        def convert(self, s):
            before = self.sd[s].conv_t
            c0(self, s)
            if self.sd[s].conv_t != before:
                self.sd[s].conv_t = self.t + cd
        S.Game.convert = convert
    elif name == 'frel1':                 # Relikvie pays +1 energy/s instead of +2
        inc0 = S.Game.income
        S.Game.income = lambda self, side: inc0(self, side) - (1.0 if self.relic['own'] == side else 0.0)
    elif name.startswith('frs'):          # Relikvie sample every N s (frs80); frs0 = no samples
        n = _num(name, 40)
        H.setc('RELIC_SAMPLE', float(n) if n else 1e9)
    elif name.startswith('fdoba'):        # Přetavení only from Doba N (fdoba2)
        need = _num(name, 2)
        c0 = S.Game.convert

        def convert(self, s):
            if self.sd[s].doba >= need:
                c0(self, s)
        S.Game.convert = convert
    elif name.startswith('fat'):          # Přetavení only after N seconds (fat180)
        at = _num(name, 180)
        c0 = S.Game.convert

        def convert(self, s):
            if self.t >= at:
                c0(self, s)
        S.Game.convert = convert
    elif name.startswith('fcv'):          # Přetavení price fcv40 = 40 energy -> 10 scrap
        H.setc('CONV', (_num(name, 30), 10))
    elif name.startswith('fut'):          # Útok! tower damage multiplier fut7 = 0.7
        m = _num(name, 5) / 10.0

        def cry(self, e):
            if e.cat != 'u':
                return 1.0
            sd = self.sd[e.side]
            k = sd.kral
            if sd.ult_t > 0 and k and (k.x - e.x) ** 2 + (k.y - e.y) ** 2 <= 9:
                return 0.4
            return m if sd.cry_t > 0 else 1.0
        S.Game.cry = cry
    else:
        raise ValueError(name)

REG = [('x', x05), ('f', fix05), ('sn_cap', sn_cap), ('sn_cost', sn_cost), ('sn_pierce', sn_pierce), ('hl_vis', hl_vis), ('sn_lvl', sn_lvl), ('sn_dmg', sn_dmg), ('sn_rate', sn_rate), ('sn_aim', sn_aim), ('sn_range', sn_range),
       ('sn_hp', sn_hp), ('sn_min', sn_min), ('sn_smart', sn_smart), ('sn_zpref', sn_zpref), ('sn_near', sn_near),
       ('obr_rarmor', obr_armor), ('obr_armor', obr_armor), ('u_armor', u_armor), ('u_hp', u_hp), ('obr_hp', obr_hp),
       ('u_speed', u_speed), ('throne', throne), ('z_bld', z_bld), ('obr_bld', obr_bld),
       ('up_s', up_s), ('ecap', ecap), ('sn_mist', sn_mist), ('z_turtle', z_turtle), ('unit_bld', unit_bld), ('night2', night2), ('night3', night3), ('night', night), ('smoke', smoke), ('medshield', medshield), ('sn_rtie', sn_rtie)]


def apply(variant):
    if not variant or variant == 'base':
        return
    for name in variant.split('+'):
        for pre, fn in REG:
            if name.startswith(pre):
                fn(name)
                break
        else:
            raise ValueError('unknown variant ' + name)
