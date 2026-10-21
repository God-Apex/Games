"""Puzzles (MAI 7, SPEC 5.2): PuzzleRules, the puzzle data loader, star evaluation and the foe scripts."""
import json
import os

from . import defs as D
from .defs import W, H, DEFS, BASE_KIT
from .maps import WALK
from .modes import Rules

PUZZLES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'puzzles.json')

GOALS = ('survive', 'destroy', 'mate', 'collect', 'relic', 'promote', 'win')
STAR_KEYS = ('win', 'throne_min', 'time_max', 'spent_max', 'lost_max', 'king_hp_min', 'parries_min', 'left_min',
             'cards_max', 'units_max', 'alive_min', 'relic_kept')
OPS = ('zombies', 'unit', 'crate', 'say', 'eclipse', 'reveal')
NO_TOWERS = ('zed', 'mina', 'gen')     # foe buildings that do not count for goal destroy/what=towers
NOHORDE = 'V této hádance Tlupu poslat nemůžeš.'
NOKIT = 'Tuhle stavbu v této hádance nemáš.'


# ------------------------------------------------------------------ data
def _check(p):
    """None when puzzle p is usable, else the reason (ASCII, for the console)."""
    for k in ('id', 'name', 'mode', 'map', 'seed', 'time', 'goal', 'you', 'foe', 'stars'):
        if k not in p:
            return 'chybi ' + k
    if p['mode'] not in ('kral', 'strateg'):
        return 'mode'
    if p['goal'].get('type') not in GOALS:
        return 'goal'
    if not isinstance(p['stars'], list) or len(p['stars']) != 3 or p['stars'][0].get('k') != 'win':
        return 'stars'
    if any(s.get('k') not in STAR_KEYS for s in p['stars']):
        return 'star key'
    for k in p['you'].get('deck', []):
        if k not in DEFS or DEFS[k]['cat'] not in 'bua':
            return 'deck ' + str(k)
    for e in p.get('place', []):
        if e.get('k') not in DEFS or not (0 <= e.get('x', -1) < W and 0 <= e.get('y', -1) < H):
            return 'place ' + str(e.get('k'))
    for op in p.get('script', []):
        if op.get('do') not in OPS:
            return 'op ' + str(op.get('do'))
    ai = p['foe'].get('ai')
    if ai is not None and ai not in FOE_SCRIPTS:
        return 'foe.ai ' + str(ai)
    return None


def load_puzzles(path):
    """{id: puzzle dict} in file order. A bad entry is skipped with a console line."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as ex:
        print('  ! puzzles.json nenacten: %s' % ex)
        return {}
    out = {}
    for p in data.get('puzzles', []) if isinstance(data, dict) else []:
        try:
            why = _check(p)
        except (AttributeError, TypeError, KeyError) as ex:
            why = 'format (%s)' % ex
        if why:
            print('  ! puzzle %s preskocen: %s' % (p.get('id') if isinstance(p, dict) else '?', why))
            continue
        out[p['id']] = p
    return out


def _n(v):
    return ('%g' % v).replace('.', ',')


def goal_text(p):
    if p.get('goal_text'):
        return p['goal_text']
    g, t = p['goal'], _n(p['time'])
    typ = g['type']
    if typ == 'survive':
        return 'Vydrž %s s, trůn nesmí padnout.' % t
    if typ == 'destroy':
        what = g.get('what')
        if what == 'towers':
            return 'Znič všechny soupeřovy věže do %s s.' % t
        if what == 'throne':
            return 'Znič soupeřův trůn do %s s.' % t
        return 'Znič označené cíle do %s s.' % t
    if typ == 'mate':
        return 'Dej soupeři šach-mat do %s s.' % t
    if typ == 'collect':
        return 'Seber %d %s do %s s.' % (g.get('n', 1), 'bednu' if g.get('n', 1) == 1 else 'bedny', t)
    if typ == 'relic':
        return 'Drž Relikvii celkem %s s (limit %s s).' % (_n(g.get('hold', 20)), t)
    if typ == 'promote':
        return 'Proměň Pěšáka v Hlídku do %s s.' % t
    return 'Znič soupeřův trůn do %s s.' % t


def _pl(n, one, few, many):
    return one if n == 1 else few if 2 <= n <= 4 else many


def star_text(p, s):
    if s.get('text'):
        return s['text']
    k, v = s['k'], s.get('v', 0)
    n = int(v) if isinstance(v, (int, float)) else 0
    if k == 'win':
        return 'Splň úkol.'
    if k == 'lost_max':
        return ('Ztrať nejvýš %d %s.' % (n, _pl(n, 'jednotku nebo stavbu', 'jednotky nebo stavby', 'jednotek nebo staveb'))
                if n else 'Neztrať žádnou jednotku ani stavbu.')
    if k == 'relic_kept':
        return 'Po prvním obsazení o Relikvii nepřijdeš.'
    return {
        'throne_min': 'Trůn má na konci aspoň %s životů.' % _n(v),
        'time_max': 'Hotovo do %s s.' % _n(v),
        'spent_max': 'Utrať nejvýš %s ⚡.' % _n(v),
        'king_hp_min': 'Král má na konci aspoň %s %% životů.' % _n(round(v * 100)),
        'parries_min': 'Odraz aspoň %d %s.' % (n, _pl(n, 'střelu', 'střely', 'střel')),
        'left_min': 'Na konci ti zbude aspoň %s ⚡.' % _n(v),
        'cards_max': 'Použij nejvýš %d %s.' % (n, _pl(n, 'kartu', 'karty', 'karet')),
        'units_max': 'Nasaď nejvýš %d %s.' % (n, _pl(n, 'jednotku', 'jednotky', 'jednotek')),
        'alive_min': 'Na konci ti %s aspoň %d %s.' % (_pl(n, 'přežije', 'přežijí', 'přežije'), n,
                                                    _pl(n, 'jednotka', 'jednotky', 'jednotek')),
    }[k]


def public(p):
    """The client view of one puzzle (defs.puzzles and start.puzzle)."""
    return {'id': p['id'], 'name': p['name'], 'desc': p.get('desc', ''), 'mode': p['mode'], 'map': p['map'],
            'time': p['time'], 'goal': p['goal']['type'], 'goal_text': goal_text(p),
            'stars_text': [star_text(p, s) for s in p['stars']]}


PUZZLES = {}


def public_puzzles():
    return [public(p) for p in PUZZLES.values()]


# ------------------------------------------------------------------ stars
STAR_METRIC = {'throne_min': ('throne', 'min'), 'time_max': ('t', 'max'), 'spent_max': ('spent', 'max'),
               'lost_max': ('lost', 'max'), 'king_hp_min': ('king_hp', 'min'), 'parries_min': ('parries', 'min'),
               'left_min': ('left', 'min'), 'cards_max': ('cards', 'max'), 'units_max': ('units', 'max'),
               'alive_min': ('alive', 'min')}


def star_hits(puzzle, metrics):
    """Per-star flags [b, b, b] (sent as end.puzzle.hit); all False when the puzzle failed."""
    if not metrics.get('ok'):
        return [False] * len(puzzle['stars'])
    out = []
    for s in puzzle['stars']:
        k, v = s['k'], s.get('v', 0)
        if k == 'win':
            hit = True
        elif k == 'relic_kept':
            hit = bool(metrics.get('relic_kept'))
        else:
            name, op = STAR_METRIC[k]
            hit = metrics[name] >= v if op == 'min' else metrics[name] <= v
        out.append(bool(hit))
    return out


def eval_stars(puzzle, g, metrics):
    """Stars 0-3: 0 when the puzzle failed, else 1 + each further star whose condition holds (each on its own)."""
    return sum(1 for h in star_hits(puzzle, metrics) if h)


# ------------------------------------------------------------------ foe scripts
def relic_squads(rules, g, dt):
    """Side 1 sends a Četa na Relikvii every 20 s (SPEC 5.2). Never uses hmk/ai."""
    if g.t >= rules.foe_next:
        rules.foe_next += 20.0
        g.act(1, {'t': 'squad', 'id': 'relic'})


FOE_SCRIPTS = {'relic_squads': relic_squads}

PUZZLES.update(load_puzzles(PUZZLES_PATH))


# ------------------------------------------------------------------ rules
class PuzzleRules(Rules):
    play = 'puzzle'
    relic = False                 # PuzzleRules runs the Relikvie itself when world.relic is on
    checkmate = False             # run by end_check for goal 'mate' only
    night = False
    eclipses = ()

    def __init__(self, puzzle):
        if not isinstance(puzzle, dict):
            raise KeyError('puzzle')
        self.p = puzzle
        self.goal = puzzle['goal']
        self.you, self.foe = puzzle['you'], puzzle['foe']
        w = puzzle.get('world') or {}
        self.world = w
        self.eclipses = tuple(w.get('eclipses') or ())
        self.use_relic = bool(w.get('relic'))
        self.inc = [float(self.you.get('income', 0)), float(self.foe.get('income', 0))]
        self.kit = list(BASE_KIT) if self.you.get('kit') else []
        self.cds = dict(self.you.get('cds') or {})
        self.script = sorted(puzzle.get('script', []), key=lambda o: o.get('t', 0))
        self.si = 0
        self.foe_ai = FOE_SCRIPTS.get(self.foe.get('ai')) if self.foe.get('ai') else None
        self.foe_next = 1.0
        self.tags = {}            # tag -> entity
        self.towers = []          # foe tower ids for destroy/what=towers
        self.had_king = False
        self.promoted = False
        self.relic_got = False
        self.relic_lost = False
        self.result = None        # {id, ok, stars, t, metrics}
        self.last_metrics = None

    # ---------------------------------------------------- setup
    def setup(self, g):
        p = self.p
        for s, cfg in ((0, self.you), (1, self.foe)):
            sd = g.sd[s]
            res = list(cfg.get('res', [0, 0, 0])) + [0, 0, 0]
            sd.e, sd.s, sd.v = float(res[0]), float(res[1]), int(res[2])
            g.throne[s] = float(cfg.get('throne', D.THRONE_HP))
            sd.techs = set(cfg.get('techs', []))
            if 'deck' in cfg:
                sd.deck = list(cfg['deck'])
            if g.mode == 'kral':
                if not cfg.get('king', s == 0):
                    if sd.kral is not None:
                        g.remove(sd.kral)
                    sd.kral = None
                    sd.respawn_len = None
                else:
                    r = cfg.get('respawn', D.KRAL['respawn'])
                    sd.respawn_len = float(r) if isinstance(r, (int, float)) and not isinstance(r, bool) and r > 0 else None
            if cfg.get('helpless'):
                sd.cd['cmd_odstrel'] = sd.cd['cmd_stit'] = 1e9
        self.had_king = g.sd[0].kral is not None
        g.next_wave = g.next_crate = g.next_alfa = 1e9
        for e in p.get('place', []):
            self.place(g, e)
        if self.goal['type'] == 'destroy' and self.goal.get('what') == 'towers':
            self.towers = sorted(e.id for e in g.ents.values() if e.side == 1 and e.cat == 'b' and e.kind not in NO_TOWERS)
        if self.use_relic:
            self.relic_on(g)

    def place(self, g, o):
        kind, s, x, y = o['k'], int(o.get('s', 1)), int(o['x']), int(o['y'])
        cat = DEFS[kind]['cat']
        grid = g.bld if cat == 'b' else g.mob
        if grid[y][x] is not None or (cat != 'b' and g.ter[y][x] not in WALK):
            return None
        e = g.spawn(kind, s, x, y)
        if cat == 'z':
            e.tgt = int(o.get('tgt', 0))
        if 'lvl' in o:
            e.lvl = int(o['lvl'])
        if 'path' in o:
            e.path = o['path']
        if o.get('vet'):
            e.vet = True
        if cat in 'bu':
            g.refresh_hp(e, full=True)
        if 'hp' in o:
            e.hp = max(1.0, e.maxhp * float(o['hp']))
        if 'stun' in o:
            e.stun = float(o['stun'])
        if 'tag' in o:
            e.tag = o['tag']
            self.tags[o['tag']] = e
        return e

    def relic_on(self, g):
        if not g.relic['on']:
            g.relic['on'] = True
            g.event(None, 'relic_on', 1)
            g.say('Relikvie je aktivní! Obsaď ji jednotkou.' if g.mode == 'strateg' else 'Relikvie je aktivní! Obsaď ji jednotkou nebo Králem.')

    # ---------------------------------------------------- hooks
    def allow(self, g, s, m):
        if s != 0:
            return True
        t = m.get('t')
        if t == 'horde' and not self.you.get('horde'):
            g.say(NOHORDE, 0, 'e')
            return False
        if t == 'build':
            k = m.get('kind')
            if isinstance(k, str) and k in BASE_KIT and k not in self.kit and k not in g.sd[0].deck:
                g.say(NOKIT, 0, 'e')
                return False
        return True

    def tick(self, g, dt):
        for s in (0, 1):                              # puzzle income replaces BASE_INCOME
            sd = g.sd[s]
            sd.e -= (D.BASE_INCOME - self.inc[s]) * dt
            if sd.e < 0:
                sd.e = 0.0
        sd = g.sd[0]
        for c, v in self.cds.items():
            if sd.cd.get(c, 0) > v:
                sd.cd[c] = float(v)
        while self.si < len(self.script) and self.script[self.si].get('t', 0) <= g.t + 1e-9:
            self.run_op(g, self.script[self.si])
            self.si += 1
        if self.foe_ai:
            self.foe_ai(self, g, dt)
        for a in self.eclipses:
            if g.crossed(a):
                g.event(None, 'ecl', 1)
            elif g.crossed(a + D.ECL_LEN):
                g.event(None, 'ecl', 0)

    def run_op(self, g, o):
        do = o['do']
        if do == 'zombies':
            kinds = o.get('kinds', [])
            rows = o.get('rows') or [H // 2]
            x = int(o.get('x', 7))
            for i, k in enumerate(kinds):
                y = rows[i % len(rows)]
                cells = sorted(((abs(cx - x) + abs(cy - y), cx, cy) for cx in range(max(0, x - 2), min(W, x + 3))
                                for cy in range(H) if g.ter[cy][cx] in WALK and not g.mob[cy][cx] and not g.bld[cy][cx]))
                if cells:
                    g.spawn(k, 2, cells[0][1], cells[0][2]).tgt = int(o.get('tgt', 0))
        elif do == 'unit':
            self.place(g, o)
        elif do == 'crate':
            g.drop_crate(int(o['x']), int(o['y']), int(o.get('r', 0)), land=float(o.get('land', 0.0)))
        elif do == 'say':
            g.say(o.get('text', ''), 0, o.get('kind', 'i'))
        elif do == 'eclipse':
            self.eclipses = self.eclipses + (g.t,)
            g.event(None, 'ecl', 1)
        elif do == 'reveal':
            g.sd[0].reveals.append([int(o['x']), int(o['y']), float(o.get('secs', 5)), float(o.get('r', 2))])

    # ---------------------------------------------------- goal
    def metrics(self, g):
        sd = g.sd[0]
        k = sd.kral
        return {'ok': False, 't': round(g.t, 1), 'throne': int(g.throne[0]), 'spent': int(sd.stats['spent']),
                'lost': sd.stats['lost'], 'king_hp': round(k.hp / k.maxhp, 3) if k else 0.0,
                'parries': sd.stats['parry'], 'left': int(sd.e), 'cards': sd.stats['cast'], 'units': sd.stats['units'],
                'alive': sum(1 for e in g.ents.values() if e.side == 0 and e.cat == 'u'),
                'crates': sd.stats['crates'], 'relic': round(sd.stats['relic_s'], 1),
                'relic_kept': self.relic_got and not self.relic_lost}

    def progress(self, g):
        """(progress, target) for the pz snapshot field."""
        typ, gl = self.goal['type'], self.goal
        if typ == 'survive':
            return int(min(g.t, self.p['time'])), int(self.p['time'])
        if typ == 'destroy':
            ids = self.target_ids()
            return sum(1 for i in ids if i not in g.ents), len(ids)
        if typ == 'mate':
            return round(g.sd[1].check, 1), D.CHECK_TIME
        if typ == 'collect':
            return g.sd[0].stats['crates'], int(gl.get('n', 1))
        if typ == 'relic':
            return int(g.sd[0].stats['relic_s']), int(gl.get('hold', 20))
        if typ == 'promote':
            return 1 if self.promoted else 0, 1
        return 0, 1

    def target_ids(self):
        gl = self.goal
        if gl.get('what') == 'towers':
            return self.towers
        if gl.get('tags'):
            return sorted(self.tags[t].id for t in gl['tags'] if t in self.tags)
        return []

    def done(self, g):
        typ, gl = self.goal['type'], self.goal
        if typ == 'destroy':
            if gl.get('what') == 'throne':
                return g.throne[1] <= 0
            return all(i not in g.ents for i in self.target_ids())
        if typ == 'collect':
            return g.sd[0].stats['crates'] >= int(gl.get('n', 1))
        if typ == 'relic':
            return g.sd[0].stats['relic_s'] >= float(gl.get('hold', 20)) - 1e-6
        if typ == 'promote':
            return self.promoted
        if typ == 'win':
            return g.throne[1] <= 0
        return False

    def finish(self, g, ok, reason):
        m = self.metrics(g)
        m['ok'] = ok
        stars = eval_stars(self.p, g, m)
        self.result = {'id': self.p['id'], 'ok': ok, 'stars': stars, 't': m['t'], 'metrics': m,
                       'hit': star_hits(self.p, m)}
        g.throne[0] = max(0.0, g.throne[0])
        return {'winner': 0 if ok else 1, 'reason': reason, 'code': 'solved' if ok else 'failed'}

    def end_check(self, g):
        dt = g.t - g.prev_t
        sd = g.sd[0]
        if self.use_relic:
            saved = D.RELIC_FROM
            D.RELIC_FROM = 0.0
            try:
                g.relic_tick(dt)
            finally:
                D.RELIC_FROM = saved
            own = g.relic['own']
            if own == 0:
                self.relic_got = True
            elif self.relic_got:
                self.relic_lost = True
        if not self.promoted and any(e.kind == 'dama' and e.side == 0 for e in g.ents.values()):
            self.promoted = True
        typ = self.goal['type']
        if typ == 'mate':
            g.checkmate(dt)
            o, g.over = g.over, None
            if o and o.get('winner') == 0:
                return self.finish(g, True, 'Šach-mat! Hádanka vyřešena.')
            if o:
                return self.finish(g, False, 'Dostal jsi šach-mat.')
        if g.throne[0] <= 0:
            return self.finish(g, False, 'Tvůj trůn padl.')
        if self.you.get('king_must_live') and self.had_king and sd.kral is None:
            return self.finish(g, False, 'Tvůj Král padl.')
        if g.throne[1] <= 0 and not (typ == 'win' or (typ == 'destroy' and self.goal.get('what') == 'throne')):
            g.throne[1] = 1.0                         # the foe throne only falls when that is the goal
        if typ == 'survive':
            for t in self.goal.get('keep', []):
                e = self.tags.get(t)
                if e is not None and e.dead:
                    return self.finish(g, False, 'Nepodařilo se ubránit, co bylo potřeba.')
            if g.t >= self.p['time'] - 1e-9:
                return self.finish(g, True, 'Vydržel jsi! Hádanka vyřešena.')
            return None
        if self.done(g):
            return self.finish(g, True, 'Hádanka vyřešena!')
        if g.t >= self.p['time'] - 1e-9:
            return self.finish(g, False, 'Čas vypršel.')
        return None

    # ---------------------------------------------------- messages
    def start_extra(self, g, s):
        info = public(self.p)
        info['throne'] = [int(self.you.get('throne', D.THRONE_HP)), int(self.foe.get('throne', D.THRONE_HP))]
        return {'kit': list(self.kit), 'deck': list(g.sd[s].deck), 'puzzle': info}

    def snap_extra(self, g, s):
        if s != 0:
            return {}
        prog, tgt = self.progress(g)
        return {'pz': [int(max(0, self.p['time'] - g.t) + 0.999), prog, tgt],
                'inc': round(g.income(0) - D.BASE_INCOME + self.inc[0], 1)}

    def end_extra(self, g):
        if self.result is None:                       # quit / disconnect / error: not solved
            m = self.metrics(g)
            self.result = {'id': self.p['id'], 'ok': False, 'stars': 0, 't': m['t'], 'metrics': m,
                           'hit': [False] * len(self.p['stars'])}
        return {'puzzle': self.result}
