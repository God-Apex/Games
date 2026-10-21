"""Random-input fuzz: garbage and semi-valid actions in both modes, every snapshot JSON-encoded strictly (no
NaN/Infinity), plus raw text through Lobby.handle (the real network entry point). Must give 0 exceptions.

usage: python fuzz.py [--games N] [--secs S] [--actions A] [--modes kral,strateg] [--lobby N] [--seed0 100]
                     [--content N] [--csecs 300]
  --content seeds per 1.0 content config: Souboj/Výcvik/Přežití with every faction, all puzzles, Výuka (default 0)
  --games   games per mode (default 4: seeds seed0..seed0+3)      --secs     game time limit (default 400 s)
  --actions stop a game after A random actions (default: none)     --lobby    lobby fuzz seeds (default 3)
Env FULL=1 keeps the thrones at 3000 HP (default: 30000, so long games reach eclipses, relic, night stages).
Works on the 0.5 server and the 1.0 hmk package (HMK_SERVER, see _paths.py).
"""
import asyncio
import json
import os
import random
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()

KINDS = list(S.DEFS) + list(S.CMDS) + list(S.RESEARCH) + ['', 'x' * 300, 'ŽŽ']
# 'in'..'mode' = 0.5 protocol; the rest are 1.0 lobby/session messages, which must be harmless when unknown or malformed
TYPES = ['in', 'res', 'horde', 'conv', 'upg', 'sell', 'build', 'unit', 'card', 'cmd', 'scrap', 'hello', 'ready', 'mode',
         'kick', 'squad', 'cfg', 'solo', 'pause', 'restart', 'quit', 'tut', 'cos', 'stats_q',
         None, 5, 'zz', ['in']]


def junk(r):
    return r.choice([None, True, False, r.randint(-3, 20), r.randint(-3, 20), 10 ** 30, -10 ** 30, r.uniform(-5, 20),
                     float('inf'), float('-inf'), float('nan'), r.choice(KINDS), 'A', 'B', [], [1, 2], {}, {'a': 1},
                     '1', '-1', '1e999'])


def message(r, g, s):
    """Half semi-valid (so the game state gets rich), half garbage."""
    t = r.choice(TYPES)
    m = {'t': t}
    if r.random() < 0.5:
        x, y = r.randrange(-1, S.W + 1), r.randrange(-1, S.H + 1)
        if t in ('build', 'unit'):
            m.update(kind=r.choice(list(S.DEFS)), x=x, y=y)
        elif t in ('card', 'cmd'):
            m.update(id=r.choice(list(S.DEFS) + list(S.CMDS)), x=x, y=y)
        elif t in ('upg', 'sell'):
            own = [e.id for e in g.ents.values() if e.side == s and e.cat == 'b']
            m.update(id=r.choice(own) if own and r.random() < 0.8 else junk(r), path=r.choice(['A', 'B', '', None, 1]))
        elif t == 'in':
            m.update(mx=r.choice([-1, 0, 1]), my=r.choice([-1, 0, 1]), b=r.random() < 0.3, r=r.random() < 0.3,
                     d=r.random() < 0.2, u=r.random() < 0.2)
        elif t == 'res':
            m.update(id=r.choice(list(S.RESEARCH)))
        elif t == 'scrap':
            m.update(x=x, y=y)
        elif t == 'squad':
            m.update(id=r.choice(['relic', 'x', None, 3]))
    else:
        for k in r.sample(['x', 'y', 'id', 'kind', 'path', 'mx', 'my', 'b', 'r', 'd', 'u', 'v', 'deck', 'side', 'name'], r.randint(0, 6)):
            m[k] = junk(r)
    return m


def fuzz_game(mode, seed, secs, max_actions=None):
    r = random.Random(seed)
    g = _paths.new_game(S, ['A', 'B'], [list(S.RECOMMENDED), r.sample(S.CARD_POOL, S.DECK_SIZE)], mode, seed=seed)
    g.length = r.uniform(250, 620) if seed % 2 else g.length       # half the games reach Poslední noc
    if not os.environ.get('FULL'):
        g.throne = [30000.0, 30000.0]                              # long games: eclipses, relic, night stages
    evs = set()
    worst, total, n, maxbytes = 0.0, 0.0, 0, 0
    acts = 0
    while not g.over and g.t < secs and (max_actions is None or acts < max_actions):
        for s in (0, 1):
            if r.random() < 0.02:
                g.sd[s].e += r.choice([100, 400])
                g.sd[s].s += r.choice([20, 60])
                g.sd[s].v += r.choice([0, 1, 3])
            for _ in range(r.choice([0, 0, 1, 2, 5])):
                g.act(s, message(r, g, s))
                acts += 1
            if r.random() < 0.01 and mode == 'kral':
                g.sd[s].ult = 100.0
        t0 = time.perf_counter()
        g.step(S.TICK)
        dt = time.perf_counter() - t0
        fx = g.fx
        g.fx = []
        for s in (0, 1):
            m = g.snapshot(s, fx)
            evs.update(e[0] for e in m.get('ev', []))
            evs.update('fx:' + f[0] for f in m['fx'])
            txt = json.dumps(m, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            maxbytes = max(maxbytes, len(txt.encode('utf-8')))
        worst = max(worst, dt)
        total += dt
        n += 1
    return {'mode': mode, 'seed': seed, 't': round(g.t), 'over': (g.over or {}).get('reason'), 'acts': acts,
            'ents': len(g.ents), 'tick_avg_ms': round(total / max(1, n) * 1000, 3), 'tick_max_ms': round(worst * 1000, 2),
            'snap_max_bytes': maxbytes, 'night': g.night, 'stage': g.stage, 'seen': ' '.join(sorted(evs))}


def content_configs():
    """1.0 content (M3): every game type x factions, built the way the lobby builds them (hmk.session.build_game)."""
    from hmk import puzzle as PZ
    facs = ['bez', 'prez', 'korp', 'kult']
    out = []
    for i, f in enumerate(facs):
        out.append(('souboj', {'mode': 'kral' if i % 2 else 'strateg', 'map': 'nahodna'}, (f, facs[(i + 1) % 4])))
        out.append(('vycvik', {'mode': 'strateg' if i % 2 else 'kral', 'map': 'nahodna', 'ai': 'tezka' if i % 2 else 'stredni'}, (f, None)))
        out.append(('preziti', {'mode': 'kral' if i % 2 else 'strateg', 'map': 'nahodna'}, (f, None)))
    out.append(('preziti', {'mode': 'kral', 'map': 'nahodna', 'ai': 'stredni'}, ('kult', None)))
    out.append(('preziti', {'mode': 'strateg', 'map': 'most'}, ('prez', 'korp')))
    for pid in sorted(PZ.PUZZLES):
        out.append(('puzzle', {'mode': 'kral', 'map': 'ruiny', 'puzzle': pid}, ('bez', None)))
    for md in ('kral', 'strateg'):
        out.append(('vyuka', {'mode': md, 'map': 'ruiny'}, ('bez', None)))
    return out


def fuzz_content(cfg, seed, secs):
    """One 1.0 game of any type with random input on the human sides, real AI on AI sides; start/snap/end JSON strict."""
    import importlib
    SS = importlib.import_module('hmk.session')
    F = importlib.import_module('hmk.factions')
    typ, opts, (f0, f1) = cfg
    r = random.Random(seed)
    kinds = KINDS + list(F.FAC_DEFS)
    humans = []
    for s, f in enumerate((f0, f1)):
        if f is None:
            humans.append(None)
        else:
            humans.append(('Fuzz%d' % s, list(F.RECOMMENDED_F[f]), f))
    built = SS.build_game(typ, dict(opts), humans, seed=seed)
    assert built is not None, 'build_game refused %r' % (cfg,)
    g, ais = built
    for s in (0, 1):
        json.dumps(g.start_info(s), ensure_ascii=False, allow_nan=False)
    acts, maxbytes, evs = 0, 0, set()
    while not g.over and g.t < secs:
        for a in ais:
            if a is not None:
                a.on_tick()
        for s in (0, 1):
            if humans[s] is None:
                continue
            if r.random() < 0.02:
                g.sd[s].e += r.choice([100, 400])
                g.sd[s].s += r.choice([20, 60])
                g.sd[s].v += r.choice([0, 1, 3])
            for _ in range(r.choice([0, 0, 1, 2, 5])):
                m = message(r, g, s)
                if m.get('t') in ('build', 'unit', 'card', 'cmd') and r.random() < 0.5:
                    m['kind' if m['t'] in ('build', 'unit') else 'id'] = r.choice(kinds)
                if r.random() < 0.01:
                    m = {'t': 'tut', 'skip': r.choice([1, True, 0, None, 'x'])}
                g.act(s, m)
                acts += 1
        g.step(S.TICK)
        fx = g.fx
        g.fx = []
        for s in (0, 1):
            m = g.snapshot(s, fx)
            evs.update(e[0] for e in m.get('ev', []))
            txt = json.dumps(m, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            maxbytes = max(maxbytes, len(txt.encode('utf-8')))
    if g.over:
        json.dumps(g.end_info(), ensure_ascii=False, allow_nan=False)
    return {'type': typ, 'opts': opts.get('puzzle') or opts.get('mode'), 'facs': list(g.facs), 'seed': seed, 't': round(g.t),
            'over': (g.over or {}).get('code'), 'acts': acts, 'ents': len(g.ents), 'snap_max_bytes': maxbytes}


class FakeWriter:
    def __init__(self, i):
        self.i = i

    def get_extra_info(self, k):
        return ('10.0.0.%d' % self.i, 1234)

    def write(self, data):
        pass

    async def drain(self):
        pass

    def close(self):
        pass


def raw_texts(r):
    vals = ['null', 'true', '1e999', '-1e999', 'NaN', 'Infinity', '-Infinity', '"x"', '[]', '{}', '[1,{"a":[]}]',
            '99999999999999999999999999', '"A"', '"kulomet"', '0', '-1', '3', '7.5']
    out = []
    for _ in range(40):
        keys = r.sample(['t', 'x', 'y', 'id', 'kind', 'path', 'mx', 'my', 'b', 'd', 'u', 'v', 'deck', 'side', 'name'], r.randint(0, 6))
        body = ','.join('"%s":%s' % (k, r.choice(vals) if k != 't' else '"%s"' % r.choice(
            ['in', 'build', 'unit', 'upg', 'sell', 'cmd', 'card', 'conv', 'res', 'scrap', 'horde', 'hello', 'ready', 'mode',
             'kick', 'q', 'squad', 'cfg', 'solo', 'pause', 'restart', 'quit', 'tut', 'cos', 'stats_q']))
                        for k in keys)
        out.append('{%s}' % body)
    out += ['', 'garbage', '[1,2]', '"str"', '{"t":', '{"t":"in","mx":Infinity}', '{"t":"build","x":Infinity,"y":1,"kind":"gen"}',
            '{"t":"ready","v":true,"deck":["kulomet"]}', '{"t":"mode","v":["kral"]}', '{"t":"kick","side":[0]}',
            '{"t":"hello","name":{"a":1}}', '{"t":"in","mx":1e999,"my":-1e999,"d":1,"u":"x"}']
    return out


def _find(name):
    """Look a name up in the server module, then in hmk.lobby / hmk.net (the 1.0 package)."""
    import importlib
    for mod in (S, 'hmk.lobby', 'hmk.net'):
        try:
            m = importlib.import_module(mod) if isinstance(mod, str) else mod
        except ImportError:
            continue
        if hasattr(m, name):
            return getattr(m, name)
    return None


def _running_game(lobby):
    """The game the lobby runs now (0.5: lobby.game; 1.0: the room session's game, else the first solo's game)."""
    g = getattr(lobby, 'game', None)
    if g is not None:
        return g
    ses = getattr(lobby, 'room', None)
    if ses is not None and getattr(ses, 'game', None) is not None:
        return ses.game
    for ses in getattr(lobby, 'solos', None) or []:
        if getattr(ses, 'game', None) is not None:
            return ses.game
    return None


def session_texts(r):
    """Semi-valid and malformed 1.0 lobby/session messages (SPEC 4.1)."""
    def j(*opts):
        return r.choice(list(opts) + [junk(r)])
    deck = j(r.sample(S.CARD_POOL, 8), list(S.RECOMMENDED), ['kulomet'] * 8, [1] * 8, 'kulomet')
    ms = [{'t': 'solo', 'type': j('vycvik', 'preziti', 'puzzle', 'vyuka', 'souboj'), 'mode': j('kral', 'strateg'),
           'map': j('ruiny', 'predmesti', 'tovarna', 'most', 'metro', 'nahodna'), 'ai': j('lehka', 'stredni', 'tezka', None),
           'fac': j('bez', 'prez', 'korp', 'kult'), 'deck': deck, 'puzzle': j('p01', 'p05', 'p10')},
          {'t': 'cfg', 'type': j('souboj', 'preziti'), 'mode': j('kral', 'strateg'), 'map': j('most', 'nahodna', 'ruiny')},
          {'t': 'ready', 'v': j(True, False), 'deck': deck, 'fac': j('bez', 'kult', 'prez', 'korp')},
          {'t': 'pause', 'v': j(True, False)}, {'t': 'squad', 'id': j('relic')},
          {'t': 'tut', 'skip': j(1)}, {'t': 'cos', 'v': j({'ban': 'lebka', 'kor': 'x'}, {})},
          {'t': 'stats_q', 'who': j(None, 'fuzz0')}, {'t': 'hello', 'name': j('Fuzz', 'král', '', ' ' * 20, 'Ž' * 40)},
          {'t': 'kick', 'side': j(0, 1, 0.0, True)}]
    out = [json.dumps(m, ensure_ascii=False) for m in r.sample(ms, 4)]
    if r.random() < 0.03:
        out.append('{"t":"restart"}')
    if r.random() < 0.02:
        out.append('{"t":"quit"}')
    return out


def _count_tracebacks():
    """Swap traceback.print_exc for a counting one: the server logs errors and survives, the fuzz must still see them."""
    import traceback as tb
    box = {'n': 0, 'orig': tb.print_exc}

    def counting(*a, **k):
        box['n'] += 1
        box['orig'](*a, **k)
    tb.print_exc = counting
    return box


async def _lobby_fuzz_05(r, Lobby):
    lobby = _find('LOBBY') or Lobby()
    Client = _find('Client')
    cs = [Client(FakeWriter(i)) for i in range(3)]
    for c in cs:
        lobby.join(c)
    for c in cs[:2]:
        lobby.handle(c, json.dumps({'t': 'hello', 'name': 'Fuzz%s' % getattr(c, 'side', 0)}))
        lobby.handle(c, json.dumps({'t': 'ready', 'v': True, 'deck': r.sample(S.CARD_POOL, 8)}))
    assert _running_game(lobby) is not None, 'game did not start'
    sent = 0
    for _ in range(60):
        for c in cs:
            for txt in r.sample(raw_texts(r), 10):
                lobby.handle(c, txt)
                sent += 1
        await asyncio.sleep(0.05)          # lets Lobby.run step the game and build snapshots
    g = _running_game(lobby)
    t = g.t if g else None
    for c in cs:
        lobby.leave(c)
    await asyncio.sleep(0.1)
    return sent, t


async def lobby_fuzz(seed):
    """0.5: one room match. 1.0: a room match plus 2 solo sessions (refilled when quit), every SPEC 4.1 type with
    malformed values from 6 clients; any server traceback counts as a failure. FUZZ_AI=1 uses the real hmk.ai."""
    r = random.Random(seed)
    Lobby = _find('Lobby')
    if Lobby is None or not hasattr(Lobby(), 'solos'):
        return await _lobby_fuzz_05(r, Lobby)
    import importlib
    SS = importlib.import_module('hmk.session')
    Client = _find('Client')
    lobby = Lobby()
    if not os.environ.get('FUZZ_AI'):
        lobby.ai_factory = SS.IdleAI
    box = _count_tracebacks()
    try:
        cs = [Client(FakeWriter(i)) for i in range(6)]
        for c in cs:
            assert lobby.join(c)
            lobby.handle(c, json.dumps({'t': 'hello', 'name': 'Fuzz%d' % c.writer.i}))

        def refill():
            if lobby.room is None:
                for c in lobby.slots:
                    if c is not None and c.session is None:
                        lobby.handle(c, json.dumps({'t': 'ready', 'v': True, 'deck': r.sample(S.CARD_POOL, 8),
                                                    'fac': r.choice(['bez', 'kult', 'zz'])}))
            free = [c for c in lobby.waiting if c.session is None]
            if free and len(lobby.solos) < 2:
                lobby.handle(r.choice(free), json.dumps({'t': 'solo', 'type': 'vycvik', 'mode': r.choice(['kral', 'strateg']),
                                                         'map': 'nahodna', 'ai': r.choice(['lehka', 'stredni', 'tezka'])}))
        for _ in range(3):
            refill()
        assert lobby.room is not None and len(lobby.solos) == 2, 'sessions did not start'
        sent, tmax = 0, 0.0
        for _ in range(60):
            for c in cs:
                for txt in r.sample(raw_texts(r), 6) + session_texts(r):
                    lobby.handle(c, txt)
                    sent += 1
            refill()
            assert len(lobby.solos) <= 2, 'solo cap broken'
            for ses in ([lobby.room] if lobby.room else []) + list(lobby.solos):
                tmax = max(tmax, ses.game.t)
            await asyncio.sleep(0.05)      # lets the sessions step their games and build snapshots
        for c in cs:
            lobby.leave(c)
        await asyncio.sleep(0.1)
        assert lobby.room is None and not lobby.solos and not lobby.conns, 'sessions left after every client left'
        assert box['n'] == 0, '%d server tracebacks during lobby fuzz' % box['n']
        return sent, tmax
    finally:
        import traceback as tb
        tb.print_exc = box['orig']


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--games', type=int, default=4)
    ap.add_argument('--secs', type=float, default=400)
    ap.add_argument('--actions', type=int, default=None)
    ap.add_argument('--modes', default=','.join(S.MODES))
    ap.add_argument('--lobby', type=int, default=3)
    ap.add_argument('--seed0', type=int, default=100)
    ap.add_argument('--content', type=int, default=0, help='1.0: seeds per content config (all types x factions)')
    ap.add_argument('--csecs', type=float, default=300, help='game time limit of a content game')
    a = ap.parse_args(argv)
    t0 = time.time()
    fails = 0
    total_acts = 0
    for mode in a.modes.split(','):
        for i in range(a.games):
            try:
                res = fuzz_game(mode, a.seed0 + i, a.secs, a.actions)
                total_acts += res['acts']
                print(res)
            except Exception:
                fails += 1
                print('EXCEPTION in', mode, a.seed0 + i)
                traceback.print_exc()
    if a.content and not hasattr(S, 'Game') or a.content and not os.path.isdir(os.path.join(os.path.dirname(S.__file__), 'hmk')):
        a.content = 0
    for cfg in (content_configs() if a.content else []):
        for i in range(a.content):
            try:
                res = fuzz_content(cfg, a.seed0 + i, a.csecs)
                total_acts += res['acts']
                print(res)
            except Exception:
                fails += 1
                print('EXCEPTION in content', cfg, a.seed0 + i)
                traceback.print_exc()
    for seed in range(a.lobby):
        try:
            sent, t = asyncio.run(lobby_fuzz(seed))
            print('lobby fuzz seed %d: %d raw messages, game time %.1f s, no exception' % (seed, sent, t or -1))
        except Exception:
            fails += 1
            print('EXCEPTION in lobby fuzz', seed)
            traceback.print_exc()
    print('fuzz done in %.0f s, %d random actions, %d failures' % (time.time() - t0, total_acts, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
