"""Sessions: one running game (room PvP or solo) with its clients and AIs (SPEC 3.4).

Session.run is the 0.5 match loop (moved from Lobby) that sends snapshots only to its own clients. build_game creates the
Game (and the AI) for any game type from the lobby options, so Lobby.start, Lobby.solo and Session.restart share it.
"""
import asyncio
import random
import time
import traceback

from . import defs as D
from . import maps
from . import meta
from . import modes
from . import factions as F
from .defs import TICK, SNAP_EVERY, MODES, BASE_KIT
from .game import Game

PAUSE_SNAP = 10                  # a paused session still sends a snapshot (with ps:1) every 10 ticks
SIDE_BUF = 200                   # msgs/evs/pfx kept for a side with no client (the AI reads what it needs each tick)
SOLO_FOE = 'Nemrtví'             # side-1 name when a solo game has no AI (solo Přežití, puzzle, Výuka)
DEFAULT_MAP = {'souboj': 'nahodna', 'preziti': 'nahodna', 'vycvik': 'predmesti', 'vyuka': 'predmesti'}
SOLO_DEFAULT_MAP = {'preziti': 'predmesti'}


class IdleAI:
    """Stand-in opponent that never acts (used until hmk.ai provides a real one, and by tests)."""

    def __init__(self, g, side, diff, seed, type='vycvik', fac='bez'):
        self.g, self.side, self.diff, self.seed, self.type, self.fac = g, side, diff, seed, type, fac
        try:
            from .ai.profiles import AI_NAMES
            self.name = AI_NAMES.get(diff, 'AI')
        except Exception:
            self.name = 'AI'

    def on_tick(self):
        pass


def default_ai_factory(g, side, diff, seed, type='vycvik', fac='bez'):
    try:
        from .ai import make_ai
    except Exception:
        traceback.print_exc()
        return IdleAI(g, side, diff, seed, type, fac)
    return make_ai(g, side, diff, seed, type=type, fac=fac)


def _ai_hook(name, default, *args):
    """Optional hmk.ai hooks pick_fac(diff, R) and pick_deck(diff, fac, R); missing or failing -> default."""
    try:
        from . import ai
        fn = getattr(ai, name, None)
        if fn is not None:
            v = fn(*args)
            if v is not None:
                return v
    except Exception:
        traceback.print_exc()
    return default


def ai_names():
    try:
        from .ai.profiles import AI_NAMES
        return AI_NAMES
    except Exception:
        return {}


def prof_lv(store, key):
    """[level, title] of a profile key (level 1 while it has no profile yet); None without a key or a store."""
    if store is None or not key:
        return None
    p = store.data['players'].get(key)
    lvl = meta.lvl_of(p['xp']) if p else 1
    return [lvl, meta.title(lvl)]


def clean_opts(type, m, solo):
    """Normalise lobby options (room cfg or a 'solo' message) to {type, mode, map, ai, fac, deck, puzzle}."""
    mode = m.get('mode') if m.get('mode') in MODES else 'kral'
    mp = m.get('map')
    dflt = (SOLO_DEFAULT_MAP.get(type) if solo else None) or DEFAULT_MAP.get(type, 'nahodna')
    if not isinstance(mp, str) or (mp != 'nahodna' and mp not in maps.MAPS):
        mp = dflt
    ai = m.get('ai')
    diffs = tuple(ai_names()) or ('lehka', 'stredni', 'tezka')
    if type == 'vycvik':
        ai = ai if ai in diffs else 'lehka'
    elif type == 'preziti' and solo:
        ai = ai if ai in diffs else None
    else:
        ai = None
    fac = m.get('fac') if m.get('fac') in F.FAC_IDS else 'bez'
    if type in ('puzzle', 'vyuka'):
        fac = 'bez'
    deck = D.valid_deck(m.get('deck'), fac) or list(F.RECOMMENDED_F[fac])
    pz = m.get('puzzle') if type == 'puzzle' and isinstance(m.get('puzzle'), str) else None
    return {'type': type, 'mode': mode, 'map': mp, 'ai': ai, 'fac': fac, 'deck': deck, 'puzzle': pz}


def build_game(type, opts, humans, seed=None, ai_factory=None):
    """(game, ais) for one session, or None when the type cannot run yet (make_rules gave None).

    humans: [(name, deck, fac) | None] * 2. A None side is the AI (opts['ai']) or the passive solo foe.
    seed: None -> new random seed (a puzzle uses its own fixed seed). The game always gets a seed (g.seed is set)."""
    mode, map_id = opts['mode'], opts['map']
    ropts = {'mode': mode}
    if type == 'puzzle':
        from . import puzzle
        p = puzzle.PUZZLES.get(opts.get('puzzle'))
        if not isinstance(p, dict):
            return None
        mode = p.get('mode') if p.get('mode') in MODES else mode
        map_id = p.get('map') or 'ruiny'
        ropts = {'mode': mode, 'puzzle': opts['puzzle']}
        if seed is None and isinstance(p.get('seed'), int):
            seed = p['seed']
    if type == 'preziti':
        ropts['players'] = 2 if humans[1] is not None or opts.get('ai') else 1
    rules = modes.make_rules(type, ropts)
    if rules is None:
        return None
    if seed is None:
        seed = random.randrange(2 ** 31)
    R = random.Random(seed)
    map_def = maps.pick_map(map_id, R)
    names, decks, facs = [], [], []
    diff = opts.get('ai')
    for s in (0, 1):
        h = humans[s]
        if h is not None:
            n, dk, fc = h
        elif diff:
            fc = _ai_hook('pick_fac', 'bez', diff, random.Random(seed * 31 + 7))
            fc = fc if fc in F.FAC_IDS else 'bez'
            dk = _ai_hook('pick_deck', None, diff, fc, random.Random(seed * 31 + 11))
            dk = D.valid_deck(dk, fc) or list(F.RECOMMENDED_F[fc])
            n = ai_names().get(diff, 'AI')
        else:
            n, dk, fc = SOLO_FOE, list(F.RECOMMENDED_F['bez']), 'bez'
        names.append(n)
        decks.append(list(dk))
        facs.append(fc)
    g = Game(names, decks, mode, rules=rules, map_def=map_def, seed=seed, rng=R, facs=tuple(facs))
    ais = [None, None]
    if diff:
        for s in (0, 1):
            if humans[s] is None:
                ais[s] = (ai_factory or default_ai_factory)(g, s, diff, seed, type=type, fac=facs[s])
                names[s] = getattr(ais[s], 'name', names[s]) or names[s]
    return g, ais


class Session:
    def __init__(self, lobby, kind, type, game, clients, ais, opts, store=None):
        self.lobby = lobby
        self.kind = kind                  # 'room' | 'solo'
        self.type = type
        self.game = game
        self.clients = list(clients)      # [Client|None] * 2, index = game side
        self.ais = list(ais)
        self.opts = opts
        self.store = store
        self.paused = False
        self.done = False
        self.task = None
        self.started = time.monotonic()
        self.end_base = None
        # who played, fixed at the start: a client that disconnects is dropped from `clients` but still gets its result
        self.who = [{'k': getattr(c, 'key', None), 'human': c is not None} for c in self.clients]
        self.rec_sides = []               # sides whose result was recorded (they get a fresh 'me' afterwards)
        for s, c in enumerate(self.clients):
            if c is not None:
                c.session = self
                c.gside = s

    # ------------------------------------------------------------ messages
    def start_msg(self, s):
        g = self.game
        diff = self.opts.get('ai')
        ai = None
        for a in self.ais:
            if a is not None:
                ai = {'diff': getattr(a, 'diff', diff), 'name': getattr(a, 'name', '')}
        msg = {'type': self.type, 'map': {'id': g.map.id, 'name': g.map.name, 'theme': g.map.theme},
               'seed': g.seed, 'ai': ai, 'kit': list(BASE_KIT), 'puzzle': None,
               'surv': {'players': getattr(g.rules, 'players', 1)} if self.type == 'preziti' else None,
               'fac': list(g.facs), 'cos': [meta.cos_for(self.store, w['k']) for w in self.who],
               'lv': [prof_lv(self.store, w['k']) for w in self.who],
               'tut': self.type == 'vyuka', 'solo': self.kind == 'solo'}
        msg.update(g.start_info(s))
        return msg

    def end_msg(self):
        """The shared part of 'end' (per-client fields are added in finish)."""
        g = self.game
        msg = {'type': self.type, 'seed': g.seed, 'map': g.map.id, 'fac': list(g.facs), 'puzzle': None, 'surv': None,
               'ser': getattr(g, 'ser', None), 'lv': [None, None]}
        msg.update(g.end_info())
        return msg

    def send_start(self):
        for s, c in enumerate(self.clients):
            if c is not None:
                c.send(self.start_msg(s))

    # ------------------------------------------------------------ loop
    def _trim(self, g):
        for s in (0, 1):
            if self.clients[s] is None:
                for buf in (g.msgs, g.evs, g.pfx):
                    if len(buf[s]) > SIDE_BUF:
                        del buf[s][:-SIDE_BUF]

    def tick(self, n, send=True):
        """One server tick (run and simulate share it). Returns False when the game hit an error."""
        g = self.game
        if self.paused:
            if send and n % PAUSE_SNAP == 0:
                for c in self.clients:
                    if c is not None:
                        m = g.snapshot(c.gside, [])
                        m['ps'] = 1
                        c.send(m, droppable=True)
            return True
        for i, a in enumerate(self.ais):
            if a is not None:
                try:
                    a.on_tick()
                except Exception:
                    traceback.print_exc()
                    print('  ! AI strany %d selhala, dal nehraje' % (i + 1))
                    self.ais[i] = None
        try:
            g.step(TICK)
        except Exception:
            traceback.print_exc()
            return False
        if n % SNAP_EVERY == 0 or g.over:
            fx = g.fx
            g.fx = []
            if send:
                for c in self.clients:
                    if c is not None:
                        c.send(g.snapshot(c.gside, fx), droppable=True)
            self._trim(g)
        return True

    async def run(self):
        n = 0
        nxt = time.perf_counter()
        while not self.done:
            g = self.game
            if g.over:
                self.finish(g.over)
                break
            n += 1
            if not self.tick(n):
                self.finish({'winner': -1, 'reason': 'Chyba serveru, zápas byl ukončen.', 'code': 'error'})
                break
            if g.over and self.game is g:
                self.finish(g.over)
                break
            nxt += TICK
            delay = nxt - time.perf_counter()
            if delay < -0.5:
                nxt = time.perf_counter()
                delay = 0
            await asyncio.sleep(max(0.0, delay))

    def simulate(self, seconds):
        """Headless: no sleep, no sends. Returns g.over (None when the time ran out first)."""
        g = self.game
        end = g.t + seconds
        n = 0
        while not g.over and g.t < end - 1e-9:
            n += 1
            if not self.tick(n, send=False):
                g.over = {'winner': -1, 'reason': 'Chyba serveru, zápas byl ukončen.', 'code': 'error'}
            if self.paused:
                break
        return g.over

    # ------------------------------------------------------------ control
    def set_pause(self, v):
        if self.kind == 'solo' and not self.done:
            self.paused = bool(v)

    def restart(self):
        """Solo only: a new game with the same options (puzzle: same seed). Not recorded."""
        if self.kind != 'solo' or self.done:
            return False
        g = self.game
        seed = g.seed if self.type == 'puzzle' else None
        humans = [(c.name, self.opts['deck'], self.opts['fac']) if c is not None else None for c in self.clients]
        built = build_game(self.type, self.opts, humans, seed=seed, ai_factory=getattr(self.lobby, 'ai_factory', None))
        if built is None:
            return False
        self.game, self.ais = built
        self.paused = False
        self.started = time.monotonic()
        self.send_start()
        return True

    def quit(self, c, code='quit'):
        """A human leaves: PvP -> the opponent wins; solo -> the game ends (the AI or nobody wins)."""
        if self.done or c not in self.clients:
            return
        g = self.game
        s = self.clients.index(c)
        if code == 'disc':
            self.clients[s] = None                     # gone: no 'end' for it
        if self.kind == 'room':
            reason = ('Soupeř se odpojil.' if code == 'disc' else 'Hráč %s se vzdal.' % g.names[s])
            res = {'winner': 1 - s, 'reason': reason, 'code': code}
        else:
            reason = 'Hráč se odpojil.' if code == 'disc' else 'Hra ukončena.'
            res = {'winner': 1 - s, 'reason': reason, 'code': code}
        self.finish(res)

    def finish(self, result):
        if self.done:
            return
        self.done = True
        g = self.game
        g.over = result
        if hasattr(g, 'sample'):
            try:
                g.sample()
            except Exception:
                traceback.print_exc()
        base = self.end_msg()
        self.end_base = base
        res = {}
        if self.store is not None:
            try:
                res = meta.record(self.store, summary(self)) or {}
            except Exception:
                traceback.print_exc()
                res = {}
        self.rec_sides = sorted(res)
        base['lv'] = [prof_lv(self.store, w['k']) for w in self.who]
        for s, c in enumerate(self.clients):
            if c is not None:
                r = res.get(s) or {}
                msg = dict(base)
                msg['me'] = {k: r[k] for k in ('xp_parts', 'xp', 'lvl', 'cur', 'next', 'lvlup', 'new_ach', 'new_cos',
                                               'elo') if k in r} or None
                msg['rec_new'] = list(r.get('new_rec', []))
                c.send(msg)
        self._save_store()
        print('  Zapas skoncil (%s/%s): %s' % (self.kind, self.type, result.get('reason', '')))
        if self.lobby is not None:
            self.lobby.session_done(self)

    def _save_store(self):
        """Right after the 'end' broadcast (META 1.1): write the stats now. A failure keeps the data and is retried."""
        st = self.store
        if st is None or not st.dirty:
            return
        try:
            lb = self.lobby
            if lb is not None and getattr(lb, 'store', None) is st:
                lb.save_store()
            else:
                st.save()
        except Exception:
            traceback.print_exc()


def summary(session):
    """The SPEC 5.4 dict for meta.record."""
    g = session.game
    o = g.over or {}
    base = session.end_base or {}
    ser = getattr(g, 'ser', None)
    ai = None
    for s, a in enumerate(session.ais):
        if a is not None or (session.opts.get('ai') and not session.who[s]['human']):
            ai = {'side': s, 'diff': session.opts.get('ai'), 'fac': g.facs[s]}
    pz = base.get('puzzle')
    sv = base.get('surv')
    p = []
    for s in (0, 1):
        sd = g.sd[s]
        w = session.who[s]
        inc = (ser or {}).get('inc', [[], []])[s] if ser else []
        p.append({'n': g.names[s], 'k': w['k'], 'human': w['human'],
                  'fac': g.facs[s], 'th': int(g.throne[s]), 'dmg': int(g.dealt[s]), 'doba': sd.doba,
                  'st': dict(sd.stats),
                  'inc': [round(sum(inc) / len(inc) / 10.0, 1), round(max(inc) / 10.0, 1)] if inc else [0.0, 0.0]})
    return {'type': session.type, 'mode': g.mode, 'map': g.map.id, 'len': int(g.t), 'code': o.get('code', 'error'),
            'winner': o.get('winner', -1), 'ai': ai,
            'puzzle': {k: pz.get(k) for k in ('id', 'ok', 'stars', 't')} if isinstance(pz, dict) else None,
            'surv': dict(sv, players=getattr(g.rules, 'players', 1)) if isinstance(sv, dict) else None,
            'ecl': list(getattr(g, 'ecl_log', [])), 'night': getattr(g, 'night_t', None), 'ser': ser, 'p': p}
