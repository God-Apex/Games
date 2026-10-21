"""AI ladder (MAI 5.6, SPEC 7.3): headless matches of the Výcvik AI against itself and against scripted bots.

Usage:  python dev/tests/ai_ladder.py [pairs] [--seeds N] [--maps ruiny,predmesti] [--modes kral,strateg] [--jobs J] [--seed0 S]
        pairs: comma list of A:B, each side one of lehka stredni tezka novice turtle (default: the M2 gate set
        tezka:stredni,stredni:lehka,lehka:novice). An AI side may carry a faction: tezka@kult (default bez), or
        tezka@auto = the faction Session would pick (pick_fac). Every pair plays seeds x modes x maps x 2 seatings
        (A:A plays one seating: its score is the share of side 0, the map-fairness number).
        --gate    checks the M2 gate thresholds and exits 1 when one fails.
        --gate7   SPEC 7.3 ladder on all 5 maps (default seeds 10): the six pairs + stredni:stredni lengths + map fairness
                  (tezka:tezka side 0 at 40-60 % on every map, 20 seeds x 2 modes unless --seeds is given).
        --fac     M3 gate: tezka@F vs tezka@bez on predmesti for F in prez korp kult, 35-65 % each, plus the card usage
                  (messages sent per faction card, A9: >= 80 % of the games where it is in the deck).
        --surv    Přežití: AI vs AI under SurvivalRules(2); prints the waves reached (needs M3-B1).
        --one A B mode map seed   plays one match.
        --hash A B mode map seed secs  prints the state_hash after `secs` (determinism test).
A match is played like a Session tick (ai.on_tick before g.step, fx cleared every SNAP_EVERY ticks).
Draws (code draw/both or the time cap) count 1/2.
Env HMK_AI_PATCH='{"lehka": {"cap": 3}}' overrides DIFF entries in every worker (tuning experiments, M5-B).
"""
import multiprocessing as mp
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
for p in (HERE, os.path.join(HERE, 'bal')):
    if p not in sys.path:
        sys.path.insert(0, p)
import _paths  # noqa: E402

AI_DIFFS = ('lehka', 'stredni', 'tezka')
ALL_MAPS = ['ruiny', 'predmesti', 'tovarna', 'most', 'metro']
FACS = ('prez', 'korp', 'kult')
GATE = [('tezka', 'stredni', 0.70, 1.01), ('stredni', 'lehka', 0.75, 1.01), ('lehka', 'novice', 0.40, 0.60)]
GATE7 = GATE + [('stredni', 'novice', 0.85, 1.01), ('tezka', 'turtle', 0.80, 1.01)]
FAC_GATE = (0.35, 0.65)
FAIR_GATE = (0.40, 0.60)
LEN_GATE = (480.0, 780.0)          # median Střední match, seconds (8-13 min)
T_CAP = 1500.0


def _mods():
    S = _paths.load_server()
    import harness as HB
    import novice  # noqa: F401  (registers HB.BOTS['novice'])
    from hmk import ai as A, maps, modes, defs as D, session as SS
    patch = os.environ.get('HMK_AI_PATCH')
    if patch and not getattr(A, '_patched', False):
        import json
        for diff, kv in json.loads(patch).items():
            if diff.startswith('p:'):          # 'p:tezka' patches the Přežití overlay
                A.PR.PREZITI[diff[2:]].update(kv)
                continue
            A.DIFF[diff].update({k: (tuple(v) if isinstance(v, list) and k != 'gens' and k != 'strats' else v)
                                 for k, v in kv.items()})
        A._patched = True
    return S, HB, A, maps, modes, D, SS


def parse_side(w):
    """'tezka@kult' -> ('tezka', 'kult'); a bare name -> (name, 'bez'); 'tezka@auto' -> (tezka, None = pick_fac)."""
    if '@' in w:
        d, f = w.split('@', 1)
        return d, (None if f == 'auto' else f)
    return w, 'bez'


class BotAdapter:
    """A harness bot driven like an AI: tick() every 5th game tick (as in harness.run_game)."""

    def __init__(self, bot):
        self.bot, self.n, self.name, self.diff = bot, 0, type(bot).__name__, None

    def on_tick(self):
        if self.n % 5 == 0:
            self.bot.tick()
        self.n += 1


def _usage_wrap(g, use):
    """Count the build / unit / card / cmd messages every side sends (per card id) in `use[side]`."""
    orig = g.act

    def act(s, m):
        try:
            t = m.get('t')
            if t in ('build', 'unit'):
                k = m.get('kind')
            elif t in ('card', 'cmd'):
                k = m.get('id')
            elif t == 'horde':
                k = 'horde'
            else:
                k = None
            if k is not None:
                use[s][k] = use[s].get(k, 0) + 1
        except Exception:
            pass
        return orig(s, m)
    g.act = act


def _build(a, b, mode, map_id, seed, rules_type='vycvik', rules_opts=None):
    """Game plus the two players for a pair of side specs. Returns (g, players, who, facs, usage)."""
    S, HB, A, maps, modes, D, SS = _mods()
    HB.reset_rules()
    R = random.Random(seed)
    md = maps.pick_map(map_id, R)
    who = [parse_side(a), parse_side(b)]
    decks, facs = [], []
    for s, (w, f) in enumerate(who):
        if w == 'none':          # Přežití for one player: side 1 is a dummy
            f, dk = 'bez', list(D.RECOMMENDED)
        elif w in AI_DIFFS:
            if f is None:
                f = A.pick_fac(w, random.Random(seed * 31 + 7 + s))
            dk = A.pick_deck(w, f, random.Random(seed * 31 + 11 + s))
        elif w == 'novice':
            import novice
            f, dk = 'bez', list(novice.NOVICE_DECK)
        else:
            f, dk = 'bez', list(HB.DEF_DECK)
        decks.append(dk)
        facs.append(f)
    ropts = dict(rules_opts or {}, mode=mode)
    rules = modes.make_rules(rules_type, ropts)
    if rules is None:
        return None
    g = S.Game(['A', 'B'], decks, mode, rules=rules, map_def=md, seed=seed, rng=R, facs=tuple(facs))
    g.stat = HB.new_stats()
    use = [{}, {}]
    _usage_wrap(g, use)
    players = []
    for s, (w, f) in enumerate(who):
        if w == 'none':
            players.append(None)
        elif w in AI_DIFFS:
            players.append(A.make_ai(g, s, w, seed, type=rules_type, fac=facs[s]))
        else:
            players.append(BotAdapter(HB.BOTS[w](g, s, {'seed': seed, 'bot': w})))
    return g, players, who, facs, use


def _run(g, players, t_end):
    S, HB, A, maps, modes, D, SS = _mods()
    think_ms = [[], []]
    n = 0
    while not g.over and g.t < t_end - 1e-9:
        n += 1
        for s, p in enumerate(players):
            if p is None:
                continue
            if isinstance(p, BotAdapter):
                p.on_tick()
            else:
                k = p.thinks
                t0 = time.perf_counter()
                p.on_tick()
                if p.thinks != k:
                    think_ms[s].append((time.perf_counter() - t0) * 1000.0)
        g.step(D.TICK)
        if n % SS.SNAP_EVERY == 0:
            g.fx = []
            for s in (0, 1):
                if players[s] is not None and not isinstance(players[s], BotAdapter):
                    continue
                g.msgs[s], g.evs[s], g.pfx[s] = [], [], []
            for s in (0, 1):
                for buf in (g.msgs, g.evs, g.pfx):
                    if len(buf[s]) > 200:
                        del buf[s][:-200]
    return think_ms


def play(a, b, mode, map_id, seed, t_end=T_CAP):
    """One match, `a` on side 0 and `b` on side 1. Returns a result dict."""
    g, players, who, facs, use = _build(a, b, mode, map_id, seed)
    think_ms = _run(g, players, t_end)
    o = g.over or {'winner': -1, 'code': 'cap'}
    strat = [getattr(p, 'strat', None) for p in players]
    return {'a': a, 'b': b, 'mode': mode, 'map': map_id, 'seed': seed, 'winner': o.get('winner', -1),
            'code': o.get('code'), 't': round(g.t, 1), 'strat': strat, 'hash': g.state_hash(), 'facs': facs,
            'use': use, 'decks': [list(sd.deck) for sd in g.sd],
            'think': [(max(x) if x else 0.0, sum(x) / len(x) if x else 0.0) for x in think_ms]}


def play_surv(a, b, mode, map_id, seed, t_end=1500.0):
    """Přežití between two AIs (players=2): the last wave each side cleared and who lasted longer."""
    built = _build(a, b, mode, map_id, seed, 'preziti', {'players': 1 if b == 'none' else 2})
    if built is None:
        return {'a': a, 'b': b, 'mode': mode, 'map': map_id, 'seed': seed, 'na': True}
    g, players, who, facs, use = built
    _run(g, players, t_end)
    o = g.over or {'winner': -1, 'code': 'cap'}
    info = g.end_info()
    sv = info.get('surv') or {}
    return {'a': a, 'b': b, 'mode': mode, 'map': map_id, 'seed': seed, 'winner': o.get('winner', -1),
            'code': o.get('code'), 't': round(g.t, 1), 'wave': sv.get('wave'), 'use': use}


def _task(t):
    try:
        return play(*t)
    except Exception:          # report, do not kill the pool
        import traceback
        return {'error': traceback.format_exc(), 'task': t}


def _stask(t):
    try:
        return play_surv(*t)
    except Exception:
        import traceback
        return {'error': traceback.format_exc(), 'task': t}


def score(results, x, y):
    """Share of points of `x` against `y` over results that contain the pair (either seating; x:x = side 0)."""
    pts, n = 0.0, 0
    for r in results:
        if 'error' in r:
            continue
        if (r['a'], r['b']) == (x, y):
            side = 0
        elif (r['a'], r['b']) == (y, x):
            side = 1
        else:
            continue
        n += 1
        pts += 0.5 if r['winner'] not in (0, 1) else (1.0 if r['winner'] == side else 0.0)
    return (pts / n if n else 0.0), n


def _tasks(pairs, maps_, modes_, seeds, seed0):
    tasks = []
    for a, b in pairs:
        for mp_ in maps_:
            for mode in modes_:
                for seed in range(seed0, seed0 + seeds):
                    tasks.append((a, b, mode, mp_, seed))
                    if a != b and 'none' not in (a, b):
                        tasks.append((b, a, mode, mp_, seed))
    return tasks


def _pool(fn, tasks, jobs):
    t0 = time.time()
    with mp.Pool(jobs) as pool:
        res = pool.map(fn, tasks, chunksize=1)
    errs = [r for r in res if 'error' in r]
    for r in errs[:3]:
        print('ERROR', r['task'], r['error'])
    print('%d matches, %d errors, %.0f s wall' % (len(res), len(errs), time.time() - t0))
    return res, errs


def _usage_report(res, facs_of_interest=FACS):
    """A9: per faction card, the share of games (of those where the faction AI has it in the deck) in which it was used."""
    F = _mods()[2].F
    ok = True
    for f in facs_of_interest:
        cards = F.FACTIONS[f]['cards']
        line = '  usage %-5s' % f
        for c in cards:
            games = used = 0
            for r in res:
                if 'error' in r:
                    continue
                for s in (0, 1):
                    if r['facs'][s] == f and c in r['decks'][s]:
                        games += 1
                        used += 1 if r['use'][s].get(c, 0) > 0 else 0
            share = used / games if games else None
            line += '  %s %s' % (c, 'n/a' if share is None else '%.0f %% (%d/%d)' % (share * 100, used, games))
            if share is not None and share < 0.8:
                ok = False
        print(line)
    return ok


def main(argv):
    args = list(argv)
    if '--hash' in args:          # used by test_ai_determinism: A B mode map seed seconds -> state_hash
        i = args.index('--hash')
        a, b, mode, mp_, seed, secs = args[i + 1:i + 7]
        r = play(a, b, mode, mp_, int(seed), float(secs))
        print('HASH', r['hash'], 'T', r['t'], 'THINK', '%.3f %.3f' % tuple(r['think'][0]))
        return 0
    if '--one' in args:
        i = args.index('--one')
        a, b, mode, mp_, seed = args[i + 1:i + 6]
        r = play(a, b, mode, mp_, int(seed))
        print(r)
        return 0

    def opt(name, default):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return v
        return default

    def flag(name):
        if name in args:
            args.remove(name)
            return True
        return False
    given_seeds = '--seeds' in args
    seeds = int(opt('--seeds', '10'))
    seed0 = int(opt('--seed0', '1'))
    maps_ = opt('--maps', 'ruiny,predmesti').split(',')
    modes_ = opt('--modes', 'kral,strateg').split(',')
    jobs = int(opt('--jobs', str(max(1, (os.cpu_count() or 2) - 2))))
    gate = flag('--gate')
    gate7 = flag('--gate7')
    fac = flag('--fac')
    surv = flag('--surv')
    args = [x for x in args if not x.startswith('--')]

    if surv:
        pairs = [tuple(p.split(':')) for p in (args[0] if args else 'tezka:tezka,stredni:stredni').split(',')]
        # A:none = one player (SurvivalRules(1), side 1 is a dummy): the waves the AI lasts alone
        tasks = _tasks(pairs, maps_, modes_, seeds, seed0)
        res, errs = _pool(_stask, tasks, jobs)
        if res and res[0].get('na'):
            print('SurvivalRules is not available yet (make_rules(preziti) gave None).')
            return 1
        for a, b in pairs:
            sub = [r for r in res if 'error' not in r and (r['a'], r['b']) in ((a, b), (b, a))]
            waves = [max(w) for w in (r.get('wave') for r in sub) if w]
            print('%-8s vs %-8s n=%d  median best wave %s  median t %.0f s  codes %s' % (
                a, b, len(sub), statistics.median(waves) if waves else '?',
                statistics.median([r['t'] for r in sub]) if sub else 0,
                sorted(set(r['code'] for r in sub))))
        return 0 if not errs else 1

    if fac:
        maps_ = ['predmesti'] if '--maps' not in argv else maps_
        pairs = [('tezka@%s' % f, 'tezka@bez') for f in FACS]
        res, errs = _pool(_task, _tasks(pairs, maps_, modes_, seeds, seed0), jobs)
        ok_all = not errs
        for a, b in pairs:
            sc, n = score(res, a, b)
            good = FAC_GATE[0] <= sc <= FAC_GATE[1]
            ok_all = ok_all and good
            line = '%-12s vs %-12s %5.1f %% (n=%d) [%s %d-%d %%]' % (a, b, sc * 100, n, 'OK' if good else 'FAIL',
                                                                   FAC_GATE[0] * 100, FAC_GATE[1] * 100)
            for mode in modes_:
                sub = [r for r in res if 'error' not in r and r['mode'] == mode]
                line += '  %s %.0f' % (mode[0], score(sub, a, b)[0] * 100)
            print(line)
        ok_all = _usage_report(res) and ok_all
        return 0 if ok_all else 1

    if gate7:
        maps_ = ALL_MAPS if '--maps' not in argv else maps_
        pairs = [(a, b) for a, b, _, _ in GATE7] + [('stredni', 'stredni')]
        fair_pairs = [('tezka', 'tezka')]
        tasks = _tasks(pairs, maps_, modes_, seeds, seed0)
        tasks += _tasks(fair_pairs, maps_, modes_, seeds if given_seeds else 20, seed0)
        res, errs = _pool(_task, tasks, jobs)
        ok_all = not errs
        for a, b, lo, hi in GATE7:
            sc, n = score(res, a, b)
            good = lo <= sc <= hi
            ok_all = ok_all and good
            line = '%-8s vs %-8s %5.1f %% (n=%d) [%s %d-%d %%]' % (a, b, sc * 100, n, 'OK' if good else 'FAIL', lo * 100,
                                                                 min(100, hi * 100))
            for mp_ in maps_:
                sub = [r for r in res if 'error' not in r and r['map'] == mp_]
                line += '  %s %.0f' % (mp_[:4], score(sub, a, b)[0] * 100)
            print(line)
        lens = [r['t'] for r in res if 'error' not in r and (r['a'], r['b']) == ('stredni', 'stredni')]
        med = statistics.median(lens) if lens else 0
        good = LEN_GATE[0] <= med <= LEN_GATE[1]
        ok_all = ok_all and good
        print('median stredni:stredni match %.0f s [%s %d-%d s]' % (med, 'OK' if good else 'FAIL', *LEN_GATE))
        line = 'map fairness tezka:tezka, side 0:'
        for mp_ in maps_:
            sub = [r for r in res if 'error' not in r and r['map'] == mp_ and (r['a'], r['b']) == ('tezka', 'tezka')]
            sc, n = score(sub, 'tezka', 'tezka')
            good = FAIR_GATE[0] <= sc <= FAIR_GATE[1]
            ok_all = ok_all and good
            line += '  %s %.0f %% (n=%d) %s' % (mp_, sc * 100, n, 'OK' if good else 'FAIL')
        print(line)
        tk = [r['think'][s] for r in res if 'error' not in r for s in (0, 1) if (r['a'], r['b'])[s] == 'tezka']
        if tk:
            print('tezka think: avg %.2f ms, max %.2f ms' % (sum(t[1] for t in tk) / len(tk), max(t[0] for t in tk)))
        return 0 if ok_all else 1

    if args:
        pairs = [tuple(p.split(':')) for p in args[0].split(',')]
    else:
        pairs = [(a, b) for a, b, _, _ in GATE]
    res, errs = _pool(_task, _tasks(pairs, maps_, modes_, seeds, seed0), jobs)
    ok_all = not errs
    for a, b in pairs:
        sc, n = score(res, a, b)
        line = '%-8s vs %-8s %5.1f %% (n=%d)' % (a, b, sc * 100, n)
        for mode in modes_:
            for mp_ in maps_:
                sub = [r for r in res if 'error' not in r and r['mode'] == mode and r['map'] == mp_]
                line += '  %s/%s %.0f' % (mode[0], mp_[:4], score(sub, a, b)[0] * 100)
        lens = [r['t'] for r in res if 'error' not in r and {r['a'], r['b']} == {a, b}]
        line += '  median %.0f s' % (statistics.median(lens) if lens else 0)
        codes = {}
        for r in res:
            if 'error' not in r and {r['a'], r['b']} == {a, b}:
                codes[r['code']] = codes.get(r['code'], 0) + 1
        line += '  ' + ' '.join('%s:%d' % kv for kv in sorted(codes.items()))
        for ga, gb, lo, hi in GATE:
            if (ga, gb) == (a, b):
                good = lo <= sc <= hi
                ok_all = ok_all and good
                line += '  [%s %d-%d %%]' % ('OK' if good else 'FAIL', lo * 100, min(100, hi * 100))
        print(line)
    tk = [r['think'][s] for r in res if 'error' not in r for s in (0, 1) if parse_side((r['a'], r['b'])[s])[0] == 'tezka']
    if tk:
        print('tezka think: avg %.2f ms, max %.2f ms' % (sum(t[1] for t in tk) / len(tk), max(t[0] for t in tk)))
    if any('@' in x for pr in pairs for x in pr):
        _usage_report(res)
    return 0 if (ok_all or not gate) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
