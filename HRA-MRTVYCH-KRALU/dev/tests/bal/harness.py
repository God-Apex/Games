"""Headless bot-vs-bot balance harness for Hra mrtvych kralu (the server under test is imported read-only).

The server comes from _paths.load_server(): HMK_SERVER (path to a server.py or a game folder) or <game>/server.py.
Works on the frozen 0.5 server (golden/server_05.py) and on the 1.0 hmk package.
Variants are applied by monkeypatching DEFS / methods inside this process only (see variants.py).
Usage:  python run.py <variants> <scenarios> [seeds] [modes] [tag]     (experiments are defined in run.py)
Env: HMK_COMPAT05=1 plays the 0.5 rules on the 1.0 engine (default: 1.0 rules). Ignored by the 0.5 server.
"""
import copy
import importlib
import os
import math
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(HERE)
sys.dont_write_bytecode = True
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
import _paths  # noqa: E402

S = _paths.load_server()
D = _paths.defs_module(S)             # module that owns the tunables (hmk.defs on 1.0, the server itself on 0.5)
COMPAT05 = os.environ.get('HMK_COMPAT05', '0') == '1'

TUNABLES = ('THRONE_HP', 'START_RES', 'BASE_INCOME', 'HORDE_COST', 'HORDE_CD', 'SCRAP_TIME', 'SCRAP_GAIN', 'CHECK_TIME',
            'ECLIPSES', 'ECL_LEN', 'ECL_WARN', 'RELIC_FROM', 'RELIC_TIME', 'RELIC_SAMPLE', 'CONV', 'CRATE_CH')
FUNCS = ('gen_price', 'sniper_price')


def _owners(name):
    """Every loaded module that has `name` (server, hmk.defs and any module that bound it with from-import)."""
    mods = [S] + [m for k, m in list(sys.modules.items()) if (k == 'hmk' or k.startswith('hmk.')) and m is not None]
    return [m for m in mods if hasattr(m, name)]


def setc(name, value):
    """Set a tunable or price function everywhere it is visible (variants and tools use this, never S.NAME = ...)."""
    for m in _owners(name):
        setattr(m, name, value)
    if not _owners(name):
        setattr(D, name, value)


FM = importlib.import_module('hmk.factions') if _paths.is_hmk(S) else None     # factions module (1.0 only)
ORIG_FACTIONS = copy.deepcopy(FM.FACTIONS) if FM else None
ORIG_OWNED_CAP = FM.OWNED_CAP if FM else None
ORIG_DEFS = copy.deepcopy(S.DEFS)
ORIG_CMDS = copy.deepcopy(getattr(S, 'CMDS', {}))
ORIG_KRAL = copy.deepcopy(S.DEFS.get('kral', {}))
ORIG_CONST = {k: copy.deepcopy(getattr(D, k)) for k in TUNABLES if hasattr(D, k)}
ORIG_FUNCS = {k: getattr(D, k) for k in FUNCS if hasattr(D, k)}
# Every method of Game and of all its mixin bases (1.0 splits Game into mixins; variants may patch any of them)
ORIG_METHODS = {cls: {k: v for k, v in cls.__dict__.items() if callable(v) or isinstance(v, (staticmethod, classmethod))}
                for cls in S.Game.__mro__ if cls is not object}
NEW = hasattr(D, 'sniper_price')          # 0.5 rules: bots also use the new actions
BOT = NEW and os.environ.get("HMK_BOTNEW", "1") == "1"   # HMK_BOTNEW=0: bots play the 0.4 way on the 0.5 rules
SMART = os.environ.get('HMK_SMARTCMD', '0') == '1'   # reviewer: Stratég defender keeps Odstřel or Štít ready (anti šach-mat)
CONTEST = os.environ.get('HMK_CONTEST', 'all')    # default on (fix round) - reviewer: defender contests the Relikvie ('strateg' / 'all')
TICK_HOOKS = []                          # callables hook(g, n) run after every g.step in run_game (golden test, perf)

UNIT_KINDS = [k for k, d in S.DEFS.items() if d['cat'] == 'u']
ROW_ORDER = [4, 3, 5, 2, 6, 1, 7, 0, 8]
H_ROWS = ROW_ORDER
GAME_LEN = 720.0


def reset_rules():
    """Undo everything a previous game's variants and tracking did: DEFS/CMDS content, tunables, price functions and
    every method patched on Game or on any of its mixin bases."""
    if hasattr(S, 'SMOKE'):
        del S.SMOKE
    for k, d in ORIG_DEFS.items():
        S.DEFS[k].clear()
        S.DEFS[k].update(copy.deepcopy(d))
    for k in list(S.DEFS):
        if k not in ORIG_DEFS:
            del S.DEFS[k]
    for k, v in ORIG_CONST.items():
        setc(k, copy.deepcopy(v))
    for k, d in ORIG_CMDS.items():
        S.CMDS[k].clear()
        S.CMDS[k].update(copy.deepcopy(d))
    for k, v in ORIG_FUNCS.items():
        setc(k, v)
    if FM:                                    # faction mods, cards (DEFS above), OWNED_CAP (bound in facmech too)
        for k, d in ORIG_FACTIONS.items():
            FM.FACTIONS[k].clear()
            FM.FACTIONS[k].update(copy.deepcopy(d))
        setc('OWNED_CAP', ORIG_OWNED_CAP)
    for cls, orig in ORIG_METHODS.items():
        for k in list(cls.__dict__):

            if k not in orig and (callable(cls.__dict__[k]) or isinstance(cls.__dict__[k], (staticmethod, classmethod))):
                delattr(cls, k)
        for k, v in orig.items():
            if cls.__dict__.get(k) is not v:
                setattr(cls, k, v)


# ---------------------------------------------------------------- instrumentation
def install_tracking(use=False):
    """Wrap Game methods with read-only bookkeeping into g.stat. use=True also counts card usage per side (g.stat['used'])."""
    dmg0 = S.Game.damage
    kill0 = S.Game.kill
    horde0 = S.Game.horde

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        st = self.stat
        if isinstance(tgt, int):
            before = self.throne[tgt]
            dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
            d = before - self.throne[tgt]
            if src is not None and src.cat == 'u':
                cat = 'unit'
            elif src is not None and src.cat == 'z':
                cat = 'horde' if getattr(src, 'horde', False) else 'zombie'
            elif src_side in (0, 1):
                cat = 'charge'
            else:
                cat = 'other'
            st['throne'][tgt][cat] = st['throne'][tgt].get(cat, 0) + d
            if cat == 'unit':
                fu = st.setdefault('first_uthrone', [None, None])
                if fu[tgt] is None:
                    fu[tgt] = round(self.t)
            return
        if tgt.dead:
            return dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
        before = tgt.hp
        dmg0(self, tgt, amount, src_side, src_kind, src, ranged)
        dealt = before - tgt.hp
        eff = min(before, dealt)
        if src is not None and src.kind == 'sniper':
            key = 'u' if tgt.cat == 'u' else 'z' if tgt.cat == 'z' else 'k' if tgt.cat == 'k' else 'b'
            sn = st['sniper'][src.side]
            sn['shots'] += 1
            sn['dmg_' + key] = sn.get('dmg_' + key, 0) + eff
            sn['over'] += max(0.0, dealt - eff)
        if tgt.cat == 'u':
            st['unit_dmg_taken'][tgt.side] += eff
            k = src.kind if src is not None else ('throne' if ranged else ('mist' if src_side is None else 'other'))
            d = st['udmg_src'][tgt.side]
            d[k] = d.get(k, 0) + eff

    def kill(self, e, src_side, *rest):
        st = self.stat
        src = rest[0] if rest else None
        if src_side in (0, 1) and e.cat in 'uz' and e.side != src_side:
            sc = st.setdefault('scrap_src', [{}, {}])[src_side]
            k = 'unit' if e.cat == 'u' else 'zombie'
            if e.cat == 'u':
                v = 15 if NEW and e.vet else 6
            else:
                v = S.DEFS[e.kind]['loot'][1]
                own = getattr(e, 'own', -1)
                if own >= 0 and self.fm(own).get('noloot'):      # Kult zombies give no loot
                    v = 0
                elif src is not None and getattr(src, 'kind', '') == 'mrchozrout':
                    v *= S.DEFS['mrchozrout']['zloot']
            sc[k] = sc.get(k, 0) + v
        if e.cat == 'b' and e.side in (0, 1):
            st['bld_lost'][e.side] += e.spent[0]
            st['bld_lost_n'][e.side] += 1
            if src_side == 1 - e.side:
                st['bld_killed_by_foe'][e.side] += e.spent[0]
        elif e.cat == 'u':
            lx = local_x(1 - e.side, e.cx)
            st['udeath'][e.side][lx] = st['udeath'][e.side].get(lx, 0) + 1
            st['units_lost'][e.side] += S.DEFS[e.kind]['cost'][0]
            st['units_lost_n'][e.side] += 1
        return kill0(self, e, src_side, *rest)

    def horde(self, s):
        n0 = self.nid
        r = horde0(self, s)
        for e in self.ents.values():
            if e.id >= n0 and e.cat == 'z':
                e.horde = True
        return r

    S.Game.damage = damage
    S.Game.kill = kill
    S.Game.horde = horde
    if use:
        install_usage()

    if NEW:
        conv0 = S.Game.convert

        def convert(self, s):
            e0 = self.sd[s].e
            conv0(self, s)
            if self.sd[s].e < e0:
                c = self.stat.setdefault('conv', [0, 0])
                c[s] += 1
        S.Game.convert = convert


def install_usage():
    """Wrap Game.act: count what each side really builds, deploys or casts (g.stat['used'][side][kind or id] = n).
    reset_rules() removes the wrapper again (it is an attribute of Game that the original class dict does not have)."""
    act0 = S.Game.act

    def act(self, s, m):
        sd = self.sd[s]
        stt = sd.stats
        b0, u0, c0, h0 = stt.get('built', 0), stt.get('units', 0), stt.get('cast', 0), sd.horde_cd
        r = act0(self, s, m)
        what = None
        if stt.get('built', 0) > b0:
            what = m.get('kind')
        elif stt.get('units', 0) > u0:
            what = m.get('kind')
        elif stt.get('cast', 0) > c0:
            what = m.get('id')
        elif m.get('t') == 'horde' and sd.horde_cd > h0:
            what = 'horde'
        if what:
            d = self.stat.setdefault('used', [{}, {}])[s]
            d[what] = d.get(what, 0) + 1
        return r
    S.Game.act = act


def apply_knobs(knobs):
    """task['knobs'] = balance knobs (FAC 9) applied after reset_rules(), so they last for one game only:
    'fac.prez.zed_hp' (faction mod), 'def.emp.dur' (DEFS entry), 'cmd.utok.cd' (CMDS entry), 'const.OWNED_CAP' (tunable)."""
    for key, v in (knobs or {}).items():
        kind, _, rest = key.partition('.')
        v = copy.deepcopy(v)
        if kind == 'fac':
            f, m = rest.split('.')
            FM.FACTIONS[f]['mods'][m] = v
        elif kind == 'def':
            k, a = rest.split('.')
            S.DEFS[k][a] = v
        elif kind == 'cmd':
            c, a = rest.split('.')
            S.CMDS[c][a] = v
        elif kind == 'const':
            setc(rest, v)
        else:
            raise ValueError('unknown knob ' + key)


def new_stats():
    return {'throne': [{}, {}], 'sniper': [{'shots': 0, 'over': 0.0}, {'shots': 0, 'over': 0.0}],
            'bld_lost': [0, 0], 'bld_lost_n': [0, 0], 'bld_killed_by_foe': [0, 0],
            'units_lost': [0, 0], 'units_lost_n': [0, 0], 'unit_dmg_taken': [0.0, 0.0],
            'unit_spent': [0, 0], 'unit_n': [0, 0], 'horde_spent': [0, 0], 'abil_spent': [0, 0],
            'tower_spent': [0, 0], 'maxprog': {}, 'unit_kind': {}, 'udmg_src': [{}, {}], 'udeath': [{}, {}]}


# ---------------------------------------------------------------- bot helpers
def real_x(s, lx):
    return lx if s == 0 else S.W - 1 - lx


def local_x(s, x):
    return x if s == 0 else S.W - 1 - x


def free_cell(g, x, y):
    return (0 <= x < S.W and 0 <= y < S.H and g.ter[y][x] == '.' and g.bld[y][x] is None
            and g.mob[y][x] is None and not g.kral_near(x, y))


def gen_price(g, s):
    return D.gen_price(g.count(s, 'gen'))


def cost_of(g, s, kind):
    """Energy price of a build/deploy/cast: Game.price on 1.0 (faction mods, escalation), the DEFS cost on 0.5."""
    if hasattr(g, 'price'):
        return g.price(s, kind)[0]
    return S.DEFS[kind]['cost'][0]


def utok_ok(g, s):
    """Útok! is gated by Doba on 1.0 (cmd_of knows the faction variant and compat05); on 0.5 it never is."""
    if not hasattr(g, 'cmd_of'):
        return True
    return g.sd[s].doba >= g.cmd_of(s, 'utok').get('doba', 1)


def need_doba(g, s, kind):
    if hasattr(g, 'need_doba'):
        return g.need_doba(s, kind)
    return S.DEFS[kind].get('doba', 1)


def horde_price(g, s):
    """(cost, cooldown) of Tlupa."""
    if hasattr(g, 'horde_cost'):
        return g.horde_cost(s)
    bio = 'bio1' in g.sd[s].techs
    return round(D.HORDE_COST * (0.6 if bio else 1.0)), (15 if bio else D.HORDE_CD)


def relic_box(g):
    m = getattr(g, 'map', None)
    return tuple(m.relic) if m is not None and hasattr(m, 'relic') else tuple(S.RELIC)


def build_cost(g, s, kind):
    d = S.DEFS[kind]
    c = list(d['cost'])
    if hasattr(g, 'price'):
        c = list(g.price(s, kind))
    elif kind == 'gen':
        c[0] = gen_price(g, s)
    elif kind == 'sniper' and NEW:
        c[0] = D.sniper_price(g.count(s, 'sniper'))
    if hasattr(g, 'price_of'):
        c[0] = g.price_of(s, kind, c[0])
    return c


def try_build(g, s, kind, lx, y):
    x = real_x(s, lx)
    if not free_cell(g, x, y) or not g.buildable(s, x):
        return 'blocked'
    c = build_cost(g, s, kind)
    sd = g.sd[s]
    if sd.e < c[0] or sd.s < c[1]:
        return 'poor'
    if g.mode == 'kral' and sd.kral is None:
        return 'poor'
    g.act(s, {'t': 'build', 'kind': kind, 'x': x, 'y': y})
    b = g.bld[y][x]
    if b is not None and b.side == s and b.kind == kind:
        if kind not in ('gen', 'zed', 'hlaska'):
            g.stat['tower_spent'][s] += c[0]
        return 'ok'
    return 'blocked'


def try_upgrade(g, s, e, path='A'):
    if e.lvl >= 3:
        return 'max'
    ce, cs = S.DEFS[e.kind]['up'][e.lvl - 1]
    sd = g.sd[s]
    if sd.e < ce or sd.s < cs:
        return 'poor'
    lv = e.lvl
    g.act(s, {'t': 'upg', 'id': e.id, 'path': path})
    if lv == 2 and e.lvl == 3:
        f = g.stat.setdefault('first_l3', [None, None])
        if f[s] is None:
            f[s] = round(g.t)
    if e.kind != 'gen' and e.kind != 'hlaska':
        g.stat['tower_spent'][s] += ce
    return 'ok'


def deploy(g, s, kind, lx, y):
    x = real_x(s, lx)
    d = S.DEFS[kind]
    sd = g.sd[s]
    cost = cost_of(g, s, kind)
    if sd.e < cost or sd.doba < need_doba(g, s, kind):
        return 'poor'
    if not (0 <= x < S.W) or not g.buildable(s, x) or g.ter[y][x] != '.' or g.mob[y][x] is not None:
        return 'blocked'
    b = g.bld[y][x]
    if b is not None and b.side != s:
        return 'blocked'
    if kind == 'dama' and g.count(s, 'dama'):
        return 'blocked'
    n0 = g.nid
    g.act(s, {'t': 'unit', 'kind': kind, 'x': x, 'y': y})
    if g.nid > n0:
        g.stat['unit_spent'][s] += cost
        g.stat['unit_n'][s] += 1
        u = g.mob[y][x]
        if u is not None:
            g.stat['unit_kind'][u.id] = (s, kind)
        return 'ok'
    return 'blocked'


def front_lx(g, s):
    """Front-most buildable local column (5 at start, shrinks when the Mist advances)."""
    for lx in range(5, -1, -1):
        if g.buildable(s, real_x(s, lx)):
            return lx
    return 0


def mine(g, s, kind=None):
    return [e for e in g.ents.values() if e.side == s and (kind is None or e.kind == kind)]


# ---------------------------------------------------------------- generic per-side helpers shared by bots
class Bot:
    def __init__(self, g, s, cfg):
        self.g, self.s, self.cfg = g, s, cfg
        self.rnd = random.Random(cfg.get('seed', 0) * 31 + s)
        self.last_throne = g.throne[s]

    # economy shared by every bot: N generators then generator upgrades
    def eco(self, n_gen, upg=True):
        g, s = self.g, self.s
        gens = mine(g, s, 'gen')
        if len(gens) < n_gen:
            for y in ROW_ORDER:
                r = try_build(g, s, 'gen', 0, y)
                if r != 'blocked':
                    return r == 'ok' or 'wait'
            return False
        if upg:
            for gen in sorted(gens, key=lambda e: e.lvl):
                if gen.lvl < 3:
                    r = try_upgrade(g, s, gen, 'A')
                    return 'wait' if r == 'poor' else True
        return False

    def research(self, order):
        g, s = self.g, self.s
        sd = g.sd[s]
        for rid in order:
            if rid not in sd.techs:
                r = S.RESEARCH[rid]
                if sd.v >= r['cost']:
                    g.act(s, {'t': 'res', 'id': rid})
                return

    def commands(self, attacker):
        g, s = self.g, self.s
        if g.mode != 'strateg':
            return
        sd = g.sd[s]
        rdy = lambda c: sd.cd.get('cmd_' + c, 0) <= 0
        if rdy('sber') and g.crates:
            c = min(g.crates.values(), key=lambda c: c['land'])
            g.act(s, {'t': 'cmd', 'id': 'sber', 'x': c['x'], 'y': c['y']})
        if rdy('oprava'):
            hurt = [b for b in mine(g, s) if b.cat == 'b' and b.hp < 0.6 * b.maxhp]
            if hurt:
                b = min(hurt, key=lambda b: b.hp / b.maxhp)
                g.act(s, {'t': 'cmd', 'id': 'oprava', 'x': b.cx, 'y': b.cy})
        if BOT and rdy('odstrel') and os.environ.get('HMK_CRATESHOT', '1') == '1':
            for d in g.drones:        # SPORNÁ BEDNA: shoot the enemy drone hovering over a contested crate
                if d['s'] != s and d['h'] and g.vis[s][round(d['y'])][round(d['x'])]:
                    g.act(s, {'t': 'cmd', 'id': 'odstrel', 'x': round(d['x']), 'y': round(d['y'])})
                    break
        smart = SMART and not attacker
        keep = lambda other: not smart or rdy(other) or sd.check > 0 or sd.shield > 0   # never be 'helpless' by choice
        if rdy('odstrel') and keep('stit'):
            foes = [e for e in g.ents.values() if e.side not in (s,) and not e.dead and e.kind != 'mina'
                    and g.vis[s][e.cy][e.cx] and g.can_see(s, e)]
            if attacker:   # attacker: hit the defending building its units are fighting, else a unit
                tg = [e for e in foes if e.cat == 'b' and e.side == 1 - s]
                tg = sorted(tg, key=lambda e: e.hp)[:1] or [e for e in foes if e.cat in 'uz']
            else:
                tg = sorted([e for e in foes if e.cat == 'u' and e.side == 1 - s and own_half_x(s, e.cx)],
                            key=lambda e: -e.hp)
            if tg:
                e = tg[0]
                g.act(s, {'t': 'cmd', 'id': 'odstrel', 'x': e.cx, 'y': e.cy})
        if BOT and attacker and rdy('utok') and utok_ok(g, s):
            if sum(1 for e in mine(g, s) if e.cat == 'u' and local_x(1 - s, e.cx) <= 8) >= 3:
                g.act(s, {'t': 'cmd', 'id': 'utok', 'x': 0, 'y': 0})
        if rdy('stit') and (g.throne[s] < self.last_throne - 15 and keep('odstrel') or (smart and sd.check > 0)):
            g.act(s, {'t': 'cmd', 'id': 'stit', 'x': 0, 'y': 0})
        self.last_throne = g.throne[s]

    def king_tweak(self, m, k):
        """Hook: faction bots adjust the King's input message before it is sent (Kult war cry)."""

    def contest(self):
        """Reviewer addition (HMK_CONTEST=strateg|all): a defender that, like a human, contests the Relikvie.
        Relic not ours -> send a small squad (Obrněnec, then 2 Pěšáci in the same lanes) when no big enemy push is
        crossing the middle; enemy is capturing our relic -> one Pěšák to stall it and Odstřel the capturer."""
        g, s = self.g, self.s
        if not BOT or CONTEST == '0' or (CONTEST == 'strateg' and g.mode != 'strateg'):
            return
        sd = g.sd[s]
        foe = 1 - s
        q = getattr(self, 'cq', [])
        left = []
        for kind, y, when in q:
            if when > g.t:
                left.append([kind, y, when])
                continue
            ok = False
            for yy in (y, 4, 3, 5):
                if deploy(g, s, kind, front_lx(g, s), yy) == 'ok':
                    g.stat['contest_spent'] = g.stat.get('contest_spent', 0) + cost_of(g, s, kind)
                    ok = True
                    break
            if not ok and g.t - when < 6:
                left.append([kind, y, when])
        self.cq = left
        rl = g.relic
        if not rl['on'] or self.cq:
            return
        x0, x1, y0, y1 = relic_box(g)
        threat = rl['own'] == s and rl['by'] == foe and rl['p'] > 0
        if threat and sd.cd.get('cmd_odstrel', 0) <= 0 and g.mode == 'strateg':
            for e in g.ents.values():
                if e.side == foe and e.cat == 'u' and x0 <= e.cx <= x1 and y0 <= e.cy <= y1 and g.vis[s][e.cy][e.cx]:
                    g.act(s, {'t': 'cmd', 'id': 'odstrel', 'x': e.cx, 'y': e.cy})
                    break
        if rl['own'] == s and not threat:
            return
        if g.t < getattr(self, 'next_sq', 0):
            return
        en_route = sum(1 for e in g.ents.values() if e.side == s and e.cat == 'u' and 3 <= local_x(s, e.cx) <= 8)
        foes_mid = sum(1 for e in g.ents.values() if e.side == foe and e.cat == 'u' and 6 <= e.cx <= 9)
        if foes_mid > 3:
            return
        if threat:
            if en_route == 0 and sd.e >= 30:
                self.cq = [[self.cfg.get('contest_inf', 'pesak'), 4, g.t]]
                self.next_sq = g.t + 8
            return
        if en_route >= 2:
            return
        if sd.e < 170:
            return 'save'          # a human saves for the squad instead of the next tower
        inf = self.cfg.get('contest_inf', 'pesak')
        self.cq = [['obrnenec', 4, g.t], [inf, 4, g.t + 4], [inf, 3, g.t + 5]]
        self.next_sq = g.t + 30

    def king(self, mode):
        """'idle' = stand at home; 'repair' = walk to the most damaged own building and hold F; 'escort' = behind the push.
        With the 0.5 rules the King also takes the Relikvie when idle, dashes towards far targets, parries sniper
        lasers aimed at him and uses the war cry when he is out with own units."""
        g, s = self.g, self.s
        k = g.sd[s].kral
        if g.mode != 'kral' or k is None:
            return
        sd = g.sd[s]
        tx, ty, rep = S.home_col(s), S.H // 2, False
        # walk out for a supply crate that landed on our side of the middle (both sides do this)
        crate = None
        if self.cfg.get('crates', True) and k.hp > 0.6 * k.maxhp:
            skip = getattr(self, 'crate_skip', set())
            mine_c = [c for c in g.crates.values() if c['land'] <= 0 and c['id'] not in skip
                      and (c['x'] <= 7 if s == 0 else c['x'] >= 8)]
            if mine_c:
                crate = min(mine_c, key=lambda c: (c['x'] - k.x) ** 2 + (c['y'] - k.y) ** 2)
                if getattr(self, 'crate_id', None) != crate['id']:
                    self.crate_id, self.crate_t = crate['id'], g.t
                elif g.t - self.crate_t > 20:          # stuck behind debris: give up on this one
                    skip.add(crate['id'])
                    self.crate_skip = skip
                    crate = None
        escorting = False
        if crate is not None:
            tx, ty = crate['x'], crate['y']
            mode = 'crate'
        elif mode == 'escort':
            # walk 1.5 cells behind the most advanced own unit once the push is in the Mist; retreat when hurt
            us = [e for e in mine(g, s) if e.cat == 'u' and local_x(1 - s, e.cx) <= 9]
            if us and k.hp > 0.45 * k.maxhp:
                lead = min(us, key=lambda e: local_x(1 - s, e.cx))
                tx = lead.x - (1.5 if s == 0 else -1.5)
                ty = lead.y
                escorting = True
        if mode == 'repair':
            hurt = [b for b in mine(g, s) if b.cat == 'b' and b.hp < 0.85 * b.maxhp and g.buildable(s, b.cx)]
            if hurt and (sd.s > 2 or (BOT and sd.e > 200)):
                b = min(hurt, key=lambda b: b.hp / b.maxhp)
                tx, ty = b.cx + (1 if s == 1 else -1) * 0.75, b.cy
                tx = max(0, min(S.W - 1, tx))
                rep = True
                if BOT and sd.s < 5:
                    g.act(s, {'t': 'conv'})
        rl = getattr(g, 'relic', None)
        if (BOT and self.cfg.get('relic', True) and crate is None and not rep and not escorting and rl and rl['on']
                and rl['own'] != s and k.hp > 0.6 * k.maxhp):
            tx, ty = (7 if s == 0 else 8), 4
        if BOT and k.hp < 0.4 * k.maxhp:
            tx, ty, rep = S.home_col(s), S.H // 2, False
        dx, dy = tx - k.x, ty - k.y
        mx = 0 if abs(dx) < 0.15 else (1 if dx > 0 else -1)
        my = 0 if abs(dy) < 0.15 else (1 if dy > 0 else -1)
        near = dx * dx + dy * dy < 1.4
        m = {'t': 'in', 'mx': mx, 'my': my, 'b': False, 'r': rep and near}
        if BOT:
            aimed = any(e.kind == 'sniper' and e.aim is k and e.aim_t <= 0.3 for e in g.ents.values() if e.side != s)
            m['b'] = aimed and not getattr(self, 'last_b', False)
            self.last_b = m['b']
            far = dx * dx + dy * dy > 9 or (k.hp < 0.4 * k.maxhp and not S.own_half(s, k.cx))
            m['d'] = bool(far and sd.dash_cd <= 0 and (mx or my) and not getattr(self, 'last_d', False))
            self.last_d = m['d']
            pals = sum(1 for e in mine(g, s) if e.cat == 'u' and (e.x - k.x) ** 2 + (e.y - k.y) ** 2 <= 9)
            m['u'] = sd.ult >= 100 and not S.own_half(s, k.cx) and pals >= 2 and not getattr(self, 'last_u', False)
            self.last_u = m['u']
        self.king_tweak(m, k)
        g.act(s, m)


def own_half_x(s, x):
    return S.own_half(s, x)


# ---------------------------------------------------------------- plan steps (shared)
def up_res(g, s, e):
    if e.lvl >= 3:
        return 'max'
    ce, cs = S.DEFS[e.kind]['up'][e.lvl - 1]
    sd = g.sd[s]
    if sd.s < cs:
        return 'poor_s'
    if sd.e < ce:
        return 'poor_e'
    return 'ok'


class Planner(Bot):
    """Runs an ordered list of steps; a step returns 'done' (go on), 'wait' (saving energy, stop) or 'did'."""

    def run_steps(self, steps):
        for st in steps:
            r = st()
            if r != 'done':
                return r
        return 'done'

    def s_gens(self, n):
        def f():
            g, s = self.g, self.s
            if len(mine(g, s, 'gen')) >= n:
                return 'done'
            for y in ROW_ORDER:
                r = try_build(g, s, 'gen', 0, y)
                if r == 'ok':
                    return 'did'
                if r == 'poor':
                    return 'wait'
            return 'done'
        f.tag = ('gens', n)
        return f

    def s_upg(self, kinds, lvl, path='A', block=True):
        """Upgrade every own building of `kinds` to level `lvl`. Scrap shortage never blocks."""
        def f():
            g, s = self.g, self.s
            for e in sorted([e for e in mine(g, s) if e.kind in kinds and e.lvl < lvl], key=lambda e: e.lvl):
                r = up_res(g, s, e)
                if r == 'poor_s':
                    if BOT and g.sd[s].e >= S.DEFS[e.kind]['up'][e.lvl - 1][0] + D.CONV[0]:
                        before = g.sd[s].s
                        g.act(s, {'t': 'conv'})         # Přetavení: surplus energy pays the scrap
                        return 'wait' if g.sd[s].s > before else 'done'
                    return 'done'
                if r == 'poor_e':
                    return 'wait' if block else 'done'
                if r == 'ok':
                    try_upgrade(g, s, e, path)
                    return 'did'
            return 'done'
        f.tag = ('upg', tuple(kinds), lvl)
        return f

    def s_layout(self, items, limit=None):
        """Build missing items of a layout (kind, local x, y); `limit` = only the first n entries."""
        def f():
            g, s = self.g, self.s
            for kind, lx, y in items[:limit]:
                x = real_x(s, lx)
                if g.ter[y][x] != '.' or not g.buildable(s, x):
                    continue
                b = g.bld[y][x]
                if b is not None:
                    continue
                if kind == 'sniper' and build_cost(g, s, 'sniper')[0] > self.cfg.get('sn_max_price', 1e9):
                    continue          # a sensible player stops buying snipers once they get too expensive
                r = try_build(g, s, kind, lx, y)
                if r == 'ok':
                    return 'did'
                if r == 'poor':
                    return 'wait'
            return 'done'
        f.tag = ('layout', frozenset(k for k, _, _ in items[:limit]))
        f.items = list(items[:limit])
        return f


# ---------------------------------------------------------------- the turtle

class Turtle(Planner):
    """Generators, Hláska(s) for vision, then two full columns of Odstřelovač, upgrades, rebuilds."""

    def __init__(self, g, s, cfg):
        super().__init__(g, s, cfg)
        cols = cfg.get('sniper_cols', (1, 2))          # local columns (1,2) = real 13,14 for side 1
        hl = cfg.get('hlaska_spots', [(3, 2), (3, 6)])
        n_gen = cfg.get('n_gen', 5)
        path = cfg.get('sniper_path', 'A')
        fill = cfg.get('fill')                          # tower used where a sniper cannot be built (cap)
        sn = [('sniper', lx, y) for lx in cols for y in ROW_ORDER]
        self.kmode = cfg.get('king', 'repair')
        steps = [self.s_gens(3), self.s_layout([('hlaska',) + hl[0]]), self.s_layout(sn, 4), self.s_gens(n_gen),
                 self.s_upg(('gen',), 2), self.s_layout(sn, 9), self.s_upg(("gen",), 3)]
        if cfg.get('eco'):        # 0.5-aware turtle: generators to level 3 (via Přetavení) before the second sniper row
            steps[5], steps[6] = steps[6], steps[5]
        steps += [self.s_layout([('hlaska',) + p for p in hl]), self.s_layout(sn)]
        if fill:
            steps.append(self.s_layout([(fill, lx, y) for _, lx, y in sn]))
        steps += [self.s_upg(('hlaska',), 3), self.s_upg(('sniper',), 2, path), self.s_upg(('sniper',), 3, path)]
        if fill:
            steps.append(self.s_upg((fill,), 3, 'A'))
        self.steps = steps

    def tick(self):
        self.king(self.kmode)
        c = self.contest()
        self.commands(False)
        self.research(['ing1', 'arm1', 'ing2', 'ing3'])
        if c != 'save':
            self.run_steps(self.steps)


# ---------------------------------------------------------------- the mixed defender
class Mixed(Planner):
    def __init__(self, g, s, cfg):
        super().__init__(g, s, cfg)
        n_gen = cfg.get('n_gen', 5)
        L1 = [('kulomet', 2, 4), ('hlaska', 3, 4), ('plamen', 2, 3), ('plamen', 2, 5), ('sniper', 1, 4)]
        L2 = [('kulomet', 2, 2), ('kulomet', 2, 6), ('plamen', 2, 1), ('plamen', 2, 7), ('kulomet', 2, 0), ('kulomet', 2, 8),
              ('sniper', 1, 2), ('sniper', 1, 6)]
        W = [('zed', 3, y) for y in (3, 5, 2, 6, 1, 7, 0, 8)]
        self.kmode = cfg.get('king', 'repair')
        self.steps = [self.s_gens(3), self.s_layout(L1), self.s_gens(n_gen), self.s_upg(('gen',), 2),
                      self.s_layout(L2), self.s_upg(('gen',), 3), self.s_layout(W),
                      self.s_upg(('kulomet', 'plamen', 'sniper', 'hlaska', 'zed'), 2),
                      self.s_upg(('kulomet', 'plamen', 'sniper', 'hlaska', 'zed'), 3)]

    def tick(self):
        self.king(self.kmode)
        c = self.contest()
        self.commands(False)
        self.research(['ing1', 'arm1', 'ing2', 'ing3'])
        if c != 'save':
            self.run_steps(self.steps)


# ---------------------------------------------------------------- the attacker
COMPS = {
    'mix': ['obrnenec', 'pesak', 'obrnenec', 'pesak', 'medik', 'strelec', 'pesak', 'jezdec'],
    'tank': ['obrnenec', 'obrnenec', 'medik', 'obrnenec', 'medik'],
    'inf': ['pesak', 'pesak', 'pesak', 'medik', 'pesak', 'pesak', 'strelec', 'pesak'],
    'mix2': ['obrnenec', 'pesak', 'medik', 'pesak', 'obrnenec', 'pesak', 'pesak', 'medik'],
    'duel': ['obrnenec', 'pesak', 'pesak', 'obrnenec', 'pesak', 'pesak'],
}


class Attacker(Planner):
    """Same economy, light anti-zombie defence, then grouped unit pushes on 3 adjacent lanes + tlupa + abilities."""

    def __init__(self, g, s, cfg):
        super().__init__(g, s, cfg)
        n_gen = cfg.get('n_gen', 5)
        comp = cfg.get('comp', 'mix')
        self.comp = COMPS[comp] if isinstance(comp, str) else list(comp)     # a name in COMPS or the unit list itself

        self.push_every = cfg.get('push_every', 40.0)     # seconds of income saved per push
        d = cfg.get('att_def', 'light')
        if d == 'light':
            L = [('kulomet', 3, 4), ('hlaska', 4, 4), ('kulomet', 3, 2), ('kulomet', 3, 6)]
        elif d == 'snipers':
            L = [('hlaska', 5, 4), ('sniper', 4, 4), ('sniper', 4, 2), ('sniper', 4, 6), ('hlaska', 5, 1),
                 ('hlaska', 5, 7), ('sniper', 4, 3), ('sniper', 4, 5)]
        elif d == 'col':      # one full column of Odstřelovač + 2 Hlásky, then attack with everything else
            L = [('hlaska', 3, 2)] + [('sniper', 2, y) for y in H_ROWS] + [('hlaska', 3, 6)]
        else:
            L = []
        self.pushes = 0
        self.queue = []
        self.lane = self.rnd.choice([2, 3, 4, 5, 6]) if cfg.get('focus', True) else None
        self.next_push_ok = cfg.get('first_push', 60.0)
        self.kmode = cfg.get('king', 'idle')
        self.spam = cfg.get('spam', False)
        self.use_horde = cfg.get('horde', True)
        self.stagger = cfg.get('stagger', True)
        self.horde_pending = False
        steps = [self.s_gens(3), self.s_layout(L[:1]), self.s_gens(n_gen), self.s_layout(L),
                 self.s_upg(('gen',), 2), self.s_upg(('gen',), 3)]
        if cfg.get('upg_def', True) and d in ('snipers', 'col'):
            steps += [self.s_upg(('hlaska', 'sniper'), 2, block=False), self.s_upg(('hlaska', 'sniper'), 3, block=False)]
        self.steps = steps

    def tick(self):
        g, s = self.g, self.s
        self.king(self.kmode)
        self.commands(True)
        self.research(self.cfg.get('att_research', ['arm1', 'ing1', 'arm2', 'arm3']))
        if self.queue:
            self.flush_queue()
        self.timing()
        if self.run_steps(self.steps) == 'wait':
            return
        if self.spam:
            return self.spam_tick()
        self.push_tick()

    def spam_tick(self):
        g, s = self.g, self.s
        if self.cfg.get('no_units'):          # flood: no army at all (Tlupa, Hnízda and Mor only)
            return
        comp = [k for k in self.comp if k in g.sd[s].deck] or self.comp
        kind = self.pick(self.rnd.choice(comp), [])
        if kind is not None and g.sd[s].e >= cost_of(g, s, kind):
            deploy(g, s, kind, front_lx(g, s), self.rnd.randrange(S.H))

    def pick(self, k, queued):
        """Faction decks: a unit that is not available yet (Doba) or is at its card limit is replaced by
        cfg['fallback'][k] (None = skip). Without cfg['fallback'] nothing changes (0.5 / bez behaviour)."""
        fb = self.cfg.get('fallback')
        if not fb or k not in fb:
            return k
        g, s = self.g, self.s
        d = S.DEFS[k]
        n = sum(1 for it in queued if it[0] == k)
        if need_doba(g, s, k) > g.sd[s].doba or ('max' in d and g.count(s, k) + n >= d['max']):
            return fb[k]
        return k

    def push_tick(self):
        g, s = self.g, self.s
        sd = g.sd[s]
        if self.queue or g.t < self.next_push_ok:
            return
        if self.cfg.get('emprush') and 'emp' in sd.deck and (sd.cd.get('emp', 0) > 0 or sd.doba < need_doba(g, s, 'emp')):
            return                          # emprush: a push only starts while the EMP is ready
        budget = max(300.0, g.income(s) * self.push_every)
        if self.cfg.get('emprush') and 'emp' in sd.deck:
            budget += cost_of(g, s, 'emp')
        if BOT and self.cfg.get('ecl'):         # save everything for the Zatmění windows and the night
            if not (g.night or any(a - 2 <= g.t < a + 10 for a in D.ECLIPSES)):
                return
            budget = 150.0
        if sd.e < budget:
            return
        self.pushes += 1
        lane = self.lane if self.lane is not None else self.rnd.choice([1, 2, 3, 4, 5, 6, 7])
        self.cur_lane = lane
        q = []
        e = sd.e - (horde_price(g, s)[0] if self.use_horde and sd.horde_cd < 15 else 0)
        if self.cfg.get('use_dama', True) and sd.doba >= 2 and 'dama' in sd.deck and not g.count(s, 'dama') and e >= 200:
            q.append(['dama', 0.0])
            e -= 200
        comp = [k for k in self.comp if k in sd.deck]
        i = 0
        while comp:
            k = self.pick(comp[i % len(comp)], q)
            if k is None:
                i += 1
                if i > 3 * len(comp):
                    break
                continue
            c = cost_of(g, s, k)
            if e < c:
                break
            # stagger: slow tanks go first, faster units later so the group arrives together
            delay = {'obrnenec': 0.0, 'dama': 0.0, 'pesak': 4.0, 'medik': 4.0, 'strelec': 5.0, 'jezdec': 8.0}.get(k, 0) if self.stagger else 0.0
            q.append([k, g.t + delay])
            e -= c
            i += 1
        self.queue = q
        self.horde_pending = self.use_horde
        self.flush_queue()

    def flush_queue(self):
        g, s = self.g, self.s
        lx = front_lx(g, s)
        lane = self.cur_lane
        rows = [y for y in (lane, lane - 1, lane + 1, lane - 2, lane + 2) if 0 <= y < S.H]
        left = []
        qt = self.cfg.get('q_timeout')
        for item in self.queue:
            k, when = item
            if when > g.t:
                left.append(item)
                continue
            if qt and g.t - when > qt:        # faction bots: a unit that cannot be placed for qt seconds is dropped
                continue
            done = False
            for dx in (0, -1, -2):
                for y in rows:
                    if deploy(g, s, k, lx + dx, y) == 'ok':
                        done = True
                        break
                if done:
                    break
            if not done:
                left.append(item)
        self.queue = left

    def timing(self):
        """Release the tlupa when the push enters the Mist so zombies arrive with it; abilities at the wall."""
        g, s = self.g, self.s
        sd = g.sd[s]
        foe = 1 - s
        units = [e for e in mine(g, s) if e.cat == 'u']
        if self.horde_pending and sd.horde_cd <= 0:
            if any(local_x(foe, e.cx) <= 9 for e in units) or not units and not self.queue:
                hc = horde_price(g, s)[0]
                if sd.e >= hc:
                    g.act(s, {'t': 'horde'})
                    g.stat['horde_spent'][s] += hc
                    self.horde_pending = False
        self.abilities()

    def abilities(self):
        g, s = self.g, self.s
        sd = g.sd[s]
        foe = 1 - s
        units = [e for e in mine(g, s) if e.cat == 'u']
        sm = getattr(S, 'SMOKE', None)
        if sm and sd.cd.get('smoke', 0) <= 0 and sd.e >= sm['cost']:
            push = [e for e in units if local_x(foe, e.cx) <= 10]
            if len(push) >= 3:
                lead = min(push, key=lambda e: local_x(foe, e.cx))
                f = 1 if s == 0 else -1
                g.smokes = getattr(g, 'smokes', []) + [[s, lead.cx, lead.cy, sm['dur']]]
                sd.e -= sm['cost']
                sd.cd['smoke'] = sm['cd']
                g.stat['abil_spent'][s] += sm['cost']
                g.stat.setdefault('casts', {}).setdefault('smoke', [0, 0])[s] += 1
        # push inside the defender's killing zone (last Mist column onwards)
        front = [e for e in units if local_x(foe, e.cx) <= self.cfg.get('vyp_at', 6)]
        for card in ('vypadek', 'nalet'):
            if card not in sd.deck and not sd.free.get(card):
                continue
            d = S.DEFS[card]
            free = sd.free.get(card, 0) > 0
            if not free and (sd.cd.get(card, 0) > 0 or sd.doba < need_doba(g, s, card) or sd.e < cost_of(g, s, card)):
                continue
            if card == 'vypadek':
                if len(front) >= 3:
                    g.act(s, {'t': 'card', 'id': card, 'x': 0, 'y': 0})
                    g.stat['abil_spent'][s] += 0 if free else cost_of(g, s, card)
                    g.stat.setdefault('casts', {}).setdefault(card, [0, 0])[s] += 1
            else:
                blds = [b for b in mine(g, foe) if b.cat == 'b' and g.vis[s][b.cy][b.cx] and b.kind != 'mina']
                if not blds:
                    continue
                best, bv = None, 0
                for b in blds:
                    v = sum((2 if o.kind == 'hlaska' else 1) for o in blds if abs(o.cx - b.cx) <= 1 and abs(o.cy - b.cy) <= 1)
                    v -= sum(1 for o in units if abs(o.x - b.cx) <= 1.5 and abs(o.y - b.cy) <= 1.5) * 0.5
                    if v > bv:
                        best, bv = b, v
                if best and bv >= 2:
                    g.act(s, {'t': 'card', 'id': card, 'x': best.cx, 'y': best.cy})
                    g.stat['abil_spent'][s] += 0 if free else cost_of(g, s, card)
                    g.stat.setdefault('casts', {}).setdefault(card, [0, 0])[s] += 1


# ---------------------------------------------------------------- one game
DEF_DECK = ['sniper', 'hlaska', 'kulomet', 'plamen', 'pesak', 'obrnenec', 'nalet', 'vypadek']
ATT_DECK = ['kulomet', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'strelec', 'medik', 'vypadek']
ATT_DECK_SN = ['sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'strelec', 'medik', 'nalet']
ATT_DECK_D2 = ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'dama', 'nalet', 'vypadek']
MIX_DECK = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'obrnenec', 'medik', 'nalet']

BOTS = {'turtle': Turtle, 'att': Attacker, 'mixed': Mixed}
FAC_BOTS = {}       # bot name -> class played by a side whose faction is not 'bez' (filled by facbots.py)
FAC_DECKS = {}      # faction -> {role: deck} (filled by facbots.py)
_FAC_LOADED = []


def load_fac():
    """Import facbots on demand: it fills FAC_BOTS, FAC_DECKS and COMPS. Safe in pool workers (the task carries plain data)."""
    if not _FAC_LOADED:
        _FAC_LOADED.append(1)
        import facbots  # noqa: F401


def side_cfg(c, seed):
    """Copy of a scenario side: a deck given as a role name ('def', 'att', 'mix', 'att_sn', 'spam', 'duel') is
    resolved through FAC_DECKS[side's faction], the seed is added."""
    c = dict(c)
    if isinstance(c.get('deck'), str):
        load_fac()
        c['deck'] = list(FAC_DECKS[c.get('fac', 'bez')][c['deck']])
    c['seed'] = seed
    return c


def make_bot(g, s, cfg):
    cls = BOTS.get(cfg['bot'])
    if cfg.get('fac', 'bez') != 'bez' or cls is None:
        load_fac()
        cls = FAC_BOTS.get(cfg['bot'], cls)
    return cls(g, s, cfg)


def run_game(task):
    variant, scen, mode, seed = task['variant'], task['scen'], task['mode'], task['seed']
    import variants
    reset_rules()
    variants.apply(variant)
    apply_knobs(task.get('knobs'))
    install_tracking()
    install_usage()
    swap = bool(task.get('swap'))        # mirrored seating: the scenario's p1 sits on side 0 and p0 on side 1
    c0, c1 = (scen['p1'], scen['p0']) if swap else (scen['p0'], scen['p1'])
    c0, c1 = side_cfg(c0, seed), side_cfg(c1, seed)
    facs = (c0.get('fac', 'bez'), c1.get('fac', 'bez'))
    kw = {'facs': facs} if 'facs' in _paths.game_params(S) else {}      # the frozen 0.5 server has no factions
    g = _paths.new_game(S, ['A', 'B'], [list(c0['deck']), list(c1['deck'])], mode, seed=seed,
                        compat05=task.get('compat05', COMPAT05), **kw)
    g.length = scen.get('length', GAME_LEN)
    if g.length == 'rand':
        g.length = random.Random(seed).uniform(600, 900)
    g.stat = new_stats()
    if hasattr(g, 'post_init'):
        g.post_init()
    bots = [make_bot(g, 0, c0), make_bot(g, 1, c1)]
    bonus = scen.get('samples', [])     # [(time, n)] samples given to both sides (simulates crates/kills)
    bi = 0
    n = 0
    prog = g.stat['maxprog']
    reach = {}
    t_end = scen.get('t_end', GAME_LEN)
    if t_end == 'over':
        t_end = g.length + 600
    cps = [360, 480, 600, 720]
    cp = {}
    while not g.over and g.t < t_end:
        if cps and g.t >= cps[0]:
            cp[cps.pop(0)] = [round(g.throne[0]), round(g.throne[1])]
        if bi < len(bonus) and g.t >= bonus[bi][0]:
            for sd in g.sd:
                sd.v += bonus[bi][1]
            bi += 1
        if n % 5 == 0:
            for b in (bots if n % 10 == 0 else bots[::-1]):
                b.tick()
        g.step(S.TICK)
        for h in TICK_HOOKS:
            h(g, n + 1)
        for f in g.fx:
            if f[0] in 'DUPpg':
                cnt = g.stat.setdefault('fx', {})
                cnt[f[0] + str(f[5])] = cnt.get(f[0] + str(f[5]), 0) + 1
        g.fx = []
        g.msgs = [[], []]
        if NEW:
            cnt = g.stat.setdefault('ev', {})
            for e in g.evs[0]:
                key = e[0] + (str(e[1]) if e[0] in ('ult', 'utok', 'relic', 'promo', 'fb') else '')
                cnt[key] = cnt.get(key, 0) + 1
                if e[0] in ('promo', 'relic'):
                    g.stat.setdefault(e[0] + '_t', []).append([round(g.t), e[1]])
            for s_ in (0, 1):
                if g.sd[s_].doba >= 2 and g.stat.setdefault('doba2_t', [None, None])[s_] is None:
                    g.stat['doba2_t'][s_] = round(g.t)
                if g.stat.get('conv', [0, 0])[s_] and g.stat.setdefault('conv_t', [None, None])[s_] is None:
                    g.stat['conv_t'][s_] = round(g.t)
            ecl = any(a <= g.t < a + D.ECL_LEN for a in D.ECLIPSES) and not g.night
            pt = g.stat.setdefault('_pth', list(g.throne))
            et = g.stat.setdefault('ecl_dmg', [[0.0, 0.0], [0.0, 0.0]])   # [side][0=outside eclipse,1=inside]
            for s_ in (0, 1):
                et[s_][1 if ecl else 0] += max(0.0, pt[s_] - g.throne[s_])
                pt[s_] = g.throne[s_]
            for e in g.evs[1]:
                if e[0] == 'streak':
                    cnt['streak1'] = cnt.get('streak1', 0) + 1
            g.evs = [[], []]
            g.pfx = [[], []]
            own = g.relic['own']
            if own >= 0:
                held = g.stat.setdefault('relic_held', [0.0, 0.0])
                held[own] += S.TICK
        n += 1
        if n % 4 == 0:
            for e in g.ents.values():
                if e.cat == 'u':
                    p = local_x(1 - e.side, e.cx)      # distance (columns) to the enemy throne
                    if p < prog.get(e.id, 99):
                        prog[e.id] = p
    st = g.stat
    out = {'variant': variant, 'scen': task['scen_name'], 'mode': mode, 'seed': seed,
           't': round(g.t), 'over': (g.over or {}).get('reason', ''), 'winner': (g.over or {}).get('winner', None),
           'throne': [round(g.throne[0]), round(g.throne[1])], 'cp': cp, 'length': round(g.length),
           'casts': g.stat.get('casts', {}), 'night': g.night,
           'first_l3': g.stat.get('first_l3', [None, None]), 'scrap_src': g.stat.get('scrap_src', [{}, {}]),
           'scrap': [round(g.sd[0].s), round(g.sd[1].s)], 'v': [g.sd[0].v, g.sd[1].v],
           'ev': g.stat.get('ev', {}), 'fxn': g.stat.get('fx', {}), 'relic_held': [round(h) for h in g.stat.get('relic_held', [0, 0])],
           'dealt': [round(d) for d in getattr(g, 'dealt', [0, 0])], 'crates': [g.sd[0].stats['crates'], g.sd[1].stats['crates']],
           'kills': [g.sd[0].stats['kills'], g.sd[1].stats['kills']], 'conv': g.stat.get('conv', [0, 0]),
           'first_uthrone': g.stat.get('first_uthrone', [None, None]), 'techs': [len(g.sd[0].techs), len(g.sd[1].techs)],
           'cspent': g.stat.get('contest_spent', 0), 'promo_t': g.stat.get('promo_t', []), 'relic_t': g.stat.get('relic_t', []),
           'ecl_dmg': [[round(a), round(b)] for a, b in g.stat.get('ecl_dmg', [[0, 0], [0, 0]])],
           'conv_t': g.stat.get('conv_t', [None, None]), 'doba2_t': g.stat.get('doba2_t', [None, None])}
    for c in cps:
        cp[c] = [round(g.throne[0]), round(g.throne[1])]
    w = out['winner']
    ws = -1 if w not in (0, 1) else (1 - w if swap else w)      # winner as scenario slot: 0 = p0's owner, 1 = p1's, -1 draw
    out.update({'fac': list(facs), 'swap': swap, 'ws': ws, 'wa': 0.5 if ws < 0 else (1.0 if ws == 0 else 0.0),
                'used': g.stat.get('used', [{}, {}]), 'decks': [list(c0['deck']), list(c1['deck'])]})

    for s in (0, 1):

        ids = [i for i, (side, k) in st['unit_kind'].items() if side == s]
        out['u%d_n' % s] = len(ids)
        out['u%d_half' % s] = sum(1 for i in ids if prog.get(i, 99) <= 5)        # entered enemy half
        out['u%d_wall' % s] = sum(1 for i in ids if prog.get(i, 99) <= 3)        # reached sniper wall front (local 3)
        out['u%d_past' % s] = sum(1 for i in ids if prog.get(i, 99) <= 1)        # past first wall column (local 1)
        out['u%d_throne' % s] = sum(1 for i in ids if prog.get(i, 99) <= 0)      # at the throne column
        out['u%d_spent' % s] = st['unit_spent'][s]
        out['h%d_spent' % s] = st['horde_spent'][s]
        out['a%d_spent' % s] = st['abil_spent'][s]
        out['tw%d_spent' % s] = st['tower_spent'][s]
        out['bld%d_lost' % s] = st['bld_lost'][s]
        out['bld%d_lost_foe' % s] = st['bld_killed_by_foe'][s]
        out['bld%d_lost_n' % s] = st['bld_lost_n'][s]
        out['ul%d' % s] = st['units_lost'][s]
        th = st['throne'][s]
        out['th%d_unit' % s] = round(th.get('unit', 0))
        out['th%d_zomb' % s] = round(th.get('zombie', 0))
        out['th%d_horde' % s] = round(th.get('horde', 0))
        out['th%d_charge' % s] = round(th.get('charge', 0))
        sn = st['sniper'][s]
        out['sn%d_shots' % s] = sn['shots']
        out['sn%d_dmg_u' % s] = round(sn.get('dmg_u', 0))
        out['sn%d_dmg_z' % s] = round(sn.get('dmg_z', 0))
        out['sn%d_over' % s] = round(sn['over'])
        out['snipers%d' % s] = g.count(s, 'sniper')
        out['gens%d' % s] = g.count(s, 'gen')
        out['e%d' % s] = round(g.sd[s].e)
        out['doba%d' % s] = g.sd[s].doba
        out['udmg%d' % s] = {k: round(v) for k, v in st['udmg_src'][s].items()}
        out['udeath%d' % s] = st['udeath'][s]
    return out
