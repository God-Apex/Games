"""Faction balance suites (FAC 8-9, SPEC 7.2): bot games on the 1.0 engine with a PASS/FAIL report per criterion.

  python facrun.py <suite|all> [--quick] [--seeds N] [--modes kral,strateg] [--workers N] [--tag T]
                               [--knob key=value ...] [--rejudge]

Suites (SPEC 7.2, seeds per cell in brackets; every seed is played twice, with the sides swapped, draws count 1/2;
  a mirror pair gets seed+100 on the swapped leg, the swapped game would repeat the first):
  matrix   B1  10 faction pairs (mirrors included) x 2 modes x [20] x 2 seatings = 800, scenario `duel`; every non-mirror pair
               40-60 %, each faction pooled 45-55 %. Also A9/B5 card usage >= 80 % and the input of `fair` and `ablate`.
  crack    B2  16 ordered pairs, ATT(f) vs TURTLE(g) (prez turtles use wallturtle for half the seeds) x 2 modes x [10] x 2
               = 640: attacker wins before the night >= 85 %, median 180-420 s, Stratég/Král ratio 0.70-1.30 (bez-bez) or
               0.60-1.40.
  spam     B3  SPAM(f) vs MIXED(g) 16 pairs + flood(kult) vs MIXED(g) 4 pairs x 2 x [10] x 2 = 800: spammer wins before the
               night <= 15 %.
  ablate   B5  9 faction cards x 2 modes x [10] x 2 = 360, `duel` F (card replaced by its shared stand-in) vs bez, against the
               same matrix cell: no card more than 15 pp better than its replacement.
  perf     B7  tick and snapshot numbers of kult-kult duel, flood vs mixed and korp emprush (perf.py, 2 seeds per mode).
  b6       B6  1.0 rules vs the 0.5 rules (compat05), bez-bez `mix` Král, 20 seeds: wins within +-2.
  fair     B4  side A (side 0) 45-55 %, zombie loot B/A 0.93-1.07, pooled over the matrix games.
  selftest     checks of this tooling itself (decks, mirrored seating, knobs, usage, bez parity), about 1 minute.
  all      matrix crack spam ablate perf b6 fair.
--quick halves the seeds (b6 keeps 20) and judges `matrix` with the sanity band 30-70 % (M3 gate). Raw rows go to
dev/tests/_out/fac_<suite><tag>.json, the report to _out/report_fac<tag>.txt. --knob key=value (JSON value) sets a
balance knob in every game, e.g. --knob fac.prez.zed_hp=1.3 --knob def.emp.dur=3.5 --knob const.OWNED_CAP=25
(keys: harness.apply_knobs). --rejudge judges the cached rows without playing. Exit code 1 when a judged criterion fails.
"""
import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import harness as H
import facbots as FB
import run as R

OUT = H._paths.OUT
FACS = FB.FACS
PAIRS = [(a, b) for i, a in enumerate(FACS) for b in FACS[i:]]            # 10 pairs, mirrors included
ORDERED = [(a, b) for a in FACS for b in FACS]                              # 16 ordered pairs
SUITES = ('matrix', 'crack', 'spam', 'ablate', 'perf', 'b6', 'fair')
SEEDS = {'matrix': 20, 'crack': 10, 'spam': 10, 'ablate': 10, 'b6': 20}
BAND = {'cell': (40, 60), 'rerun': (37, 63), 'pooled': (45, 55), 'sanity': (30, 70)}


def pct(x):
    return '%5.1f%%' % (100.0 * x) if x == x else '  n/a '


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float('nan')


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return float('nan') if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0)


def T(scen, name, mode, seed, swap, **kw):
    t = {'variant': 'base', 'scen': scen, 'scen_name': name, 'mode': mode, 'seed': seed, 'swap': swap}
    t.update(kw)
    return t


def seeds_of(suite, args):
    n = args.seeds or SEEDS[suite]
    if args.quick and not args.seeds and suite != 'b6':
        n = max(1, n // 2)
    return list(range(1000, 1000 + n))


# ---------------------------------------------------------------- task lists
def tasks_matrix(args):
    out = []
    for a, b in PAIRS:
        sc = FB.duel_scen(a, b)
        for mode in args.modes:
            for seed in seeds_of('matrix', args):
                for swap in (False, True):
                    # a mirror pair played with the sides swapped is the very same game: its second leg gets another seed
                    out.append(T(sc, 'matrix:%s-%s' % (a, b), mode, seed + 100 if (a == b and swap) else seed, swap))
    return out


def tasks_crack(args):
    out = []
    for fa, ft in ORDERED:
        for mode in args.modes:
            for i, seed in enumerate(seeds_of('crack', args)):
                sc = FB.crack_scen(fa, ft, wall=(ft == 'prez' and i % 2 == 1))       # prez turtles: wallturtle for half the seeds
                for swap in (False, True):
                    out.append(T(sc, 'crack:%s-%s' % (fa, ft), mode, seed, swap))
    return out


def tasks_spam(args):
    out = []
    cells = [('spam', fs, fm) for fs, fm in ORDERED] + [('flood', 'kult', fm) for fm in FACS]
    for kind, fs, fm in cells:
        sc = FB.spam_scen(fs, fm) if kind == 'spam' else FB.flood_scen(fm)
        name = 'spam:%s-%s' % (fs, fm) if kind == 'spam' else 'spam:flood-%s' % fm
        for mode in args.modes:
            for seed in seeds_of('spam', args):
                for swap in (False, True):
                    out.append(T(sc, name, mode, seed, swap))
    return out


def tasks_ablate(args, have_matrix):
    out = []
    for card, fac in FB.CARD_FAC.items():
        sc = FB.duel_scen(fac, 'bez', ablate0=card)
        for mode in args.modes:
            for seed in seeds_of('ablate', args):
                for swap in (False, True):
                    out.append(T(sc, 'ablate:%s' % card, mode, seed, swap))
    if not have_matrix:                      # the reference cells (F vs bez), same seeds as the ablation
        for fac in FACS[1:]:
            sc = FB.duel_scen('bez', fac)
            for mode in args.modes:
                for seed in seeds_of('ablate', args):
                    for swap in (False, True):
                        out.append(T(sc, 'matrix:bez-%s' % fac, mode, seed, swap))
    return out


def tasks_b6(args):
    out = []
    sc = FB.crack_scen('bez', 'bez')
    for seed in seeds_of('b6', args):
        out.append(T(sc, 'b6:rules10', 'kral', seed, False, compat05=False))
        out.append(T(sc, 'b6:rules05', 'kral', seed, False, compat05=True))
    return out


# ---------------------------------------------------------------- running
def _perf_job(seeds):
    import perf as P
    rows = P.measure(['f_kk', 'f_flood', 'f_emprush'], seeds)
    return rows, P.total(rows), P.b7_verdict(P.total(rows))


def play(tasks, workers, label, knobs):
    for t in tasks:
        if knobs:
            t['knobs'] = knobs
    t0 = time.time()
    res = []
    with Pool(workers) as p:
        for i, r in enumerate(p.imap_unordered(H.run_game, tasks, chunksize=1), 1):
            res.append(r)
            if i % 100 == 0 or i == len(tasks):
                print('  %s: %d/%d games, %.0f s' % (label, i, len(tasks), time.time() - t0), flush=True)
    res.sort(key=lambda r: (r['scen'], r['mode'], r['seed'], r['swap']))
    return res


def cache_path(suite, tag):
    return os.path.join(OUT, 'fac_%s%s.json' % (suite, tag))


def load_rows(suite, tag):
    p = cache_path(suite, tag)
    if not os.path.isfile(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)['rows']


def save_rows(suite, tag, rows, args):
    os.makedirs(OUT, exist_ok=True)
    with open(cache_path(suite, tag), 'w', encoding='utf-8') as f:
        json.dump({'quick': args.quick, 'knobs': args.knobs, 'rows': rows}, f, ensure_ascii=False)


# ---------------------------------------------------------------- judging (each returns (lines, checks); check = (id, ok, text))
def split_name(r):
    kind, rest = r['scen'].split(':', 1)
    return kind, rest


def band_ok(v, lo, hi):
    return lo <= 100.0 * v <= hi


def judge_matrix(rows, quick):
    lines = ['MATRIX  win rate of the first faction of the pair (draws 1/2), n games per cell = seeds x 2 seatings']
    cells = {}
    for r in rows:
        _, pair = split_name(r)
        a, b = pair.split('-')
        cells.setdefault((a, b, r['mode']), []).append(r)
    modes = sorted({k[2] for k in cells}, key=lambda m: ('kral', 'strateg').index(m))
    lo, hi = BAND['sanity'] if quick else BAND['cell']
    bad, rerun = [], []
    lines.append('%-12s ' % 'pair' + ' '.join('%-17s' % m for m in modes) + ('  (band %d-%d)' % (lo, hi)))
    for a, b in PAIRS:
        cols = []
        for m in modes:
            rs = cells.get((a, b, m), [])
            if a == b:
                v = mean((1.0 if r['winner'] == 0 else 0.5 if r['winner'] not in (0, 1) else 0.0) for r in rs)
                cols.append('%s n=%-3d side0' % (pct(v), len(rs)))
                continue
            v = mean(r['wa'] for r in rs)
            flag = ' '
            if rs and not band_ok(v, lo, hi):
                flag = '!'
                bad.append('%s-%s %s %.0f%%' % (a, b, m, 100 * v))
            elif rs and not quick and not band_ok(v, *BAND['cell']):
                flag = '?'
            if rs and not band_ok(v, *BAND['cell']) and band_ok(v, *BAND['rerun']):
                rerun.append('%s-%s %s' % (a, b, m))
            cols.append('%s n=%-3d%s     ' % (pct(v), len(rs), flag))
        lines.append('%-12s ' % ('%s-%s' % (a, b)) + ' '.join('%-17s' % c for c in cols))
    pooled = {}
    for f in FACS:
        sc = []
        for (a, b, m), rs in cells.items():
            if a == b or f not in (a, b):
                continue
            sc += [r['wa'] if f == a else 1.0 - r['wa'] for r in rs]
        pooled[f] = mean(sc)
    lines.append('pooled (3 opponents, both modes): ' + '  '.join('%s %s' % (f, pct(v)) for f, v in pooled.items()))
    if rerun:
        lines.append('cells in 37-63 %% but outside 40-60 %%: re-run with 80 games before tuning: ' + '; '.join(rerun))
    checks = [('B1' if not quick else 'B1-quick', not bad,
               'every non-mirror pair per mode in %d-%d %%' % (lo, hi) + ('' if not bad else ' (outside: ' + '; '.join(bad) + ')'))]
    if not quick:
        pbad = [f for f, v in pooled.items() if not band_ok(v, *BAND['pooled'])]
        checks.append(('B1-pooled', not pbad, 'each faction pooled in 45-55 %' + ('' if not pbad else ' (outside: ' + ', '.join(pbad) + ')')))
    else:
        lines.append('(quick: pooled 45-55 %% not judged)')
    l2, c2 = judge_usage(rows)
    return lines + l2, checks + c2


def usage_of(rows):
    out = {}
    for r in rows:
        for side in (0, 1):
            for card, fac in FB.CARD_FAC.items():
                if r['fac'][side] == fac and card in r['decks'][side]:
                    n, u = out.get(card, (0, 0))
                    out[card] = (n + 1, u + (1 if r['used'][side].get(card, 0) > 0 else 0))
    return out


def judge_usage(rows):
    use = usage_of(rows)
    lines = ['CARD USAGE (built, deployed or cast at least once, games where the card is in the deck; A9 >= 80 %)']
    low = []
    for card in FB.CARD_FAC:
        n, u = use.get(card, (0, 0))
        v = u / n if n else float('nan')
        lines.append('  %-11s %s  (%d of %d games)' % (card, pct(v), u, n))
        if n and v < 0.8:
            low.append('%s %.0f%%' % (card, 100 * v))
    return lines, [('A9', not low and bool(use), 'each faction card used in >= 80 %% of games' + ('' if not low else ' (low: ' + ', '.join(low) + ')'))]


def judge_fair(rows):
    n = len(rows)
    a = mean((1.0 if r['winner'] == 0 else 0.5 if r['winner'] not in (0, 1) else 0.0) for r in rows)
    z0 = sum(r['scrap_src'][0].get('zombie', 0) for r in rows)
    z1 = sum(r['scrap_src'][1].get('zombie', 0) for r in rows)
    ratio = z1 / z0 if z0 else float('nan')
    lines = ['FAIR  %d matrix games: side A (side 0) wins %s, zombie loot B/A %.3f (%.0f / %.0f scrap)' % (n, pct(a), ratio, z1, z0)]
    ok = n > 0 and 45 <= 100 * a <= 55 and 0.93 <= ratio <= 1.07
    return lines, [('B4', ok, 'side A 45-55 %, zombie loot B/A 0.93-1.07')]


def crack_cells(rows):
    cells = {}
    for r in rows:
        _, pair = split_name(r)
        fa, ft = pair.split('-')
        cells.setdefault((fa, ft, r['mode']), []).append(r)
    return cells


def judge_crack(rows, quick):
    cells = crack_cells(rows)
    lines = ['CRACK  attacker (first faction) vs turtle (second): wins before the night, median time of those wins',
             '%-12s %-18s %-18s %s' % ('att-turtle', 'kral win/med', 'strateg win/med', 'S/K ratio')]
    bad_win, bad_med, bad_ratio = [], [], []
    for fa, ft in ORDERED:
        col, meds = [], {}
        for m in ('kral', 'strateg'):
            rs = cells.get((fa, ft, m), [])
            if not rs:
                col.append('-')
                continue
            wins = [r for r in rs if r['ws'] == 0 and not r['night']]
            w = len(wins) / len(rs)
            med = median([r['t'] for r in wins]) if wins else float('nan')
            meds[m] = med
            col.append('%s %4.0fs' % (pct(w), med))
            if w < 0.85:
                bad_win.append('%s-%s %s %.0f%%' % (fa, ft, m, 100 * w))
            if wins and not 180 <= med <= 420:
                bad_med.append('%s-%s %s %.0fs' % (fa, ft, m, med))
        ratio = meds['strateg'] / meds['kral'] if len(meds) == 2 and meds['kral'] == meds['kral'] and meds['kral'] else float('nan')
        lo, hi = (0.70, 1.30) if (fa, ft) == ('bez', 'bez') else (0.60, 1.40)
        rflag = ''
        if ratio == ratio and not lo <= ratio <= hi:
            rflag = ' !'
            bad_ratio.append('%s-%s %.2f' % (fa, ft, ratio))
        lines.append('%-12s %-18s %-18s %s%s' % ('%s-%s' % (fa, ft), col[0] if col else '-', col[1] if len(col) > 1 else '-',
                                                 '%.2f' % ratio if ratio == ratio else ' n/a', rflag))
    return lines, [('B2-win', not bad_win, 'attacker wins before the night in >= 85 %' + ('' if not bad_win else ' (low: ' + '; '.join(bad_win) + ')')),
                   ('B2-median', not bad_med, 'median crack time 180-420 s' + ('' if not bad_med else ' (outside: ' + '; '.join(bad_med) + ')')),
                   ('B2-ratio', not bad_ratio, 'Strateg/Kral median ratio 0.70-1.30 (bez-bez) / 0.60-1.40' + ('' if not bad_ratio else ' (outside: ' + '; '.join(bad_ratio) + ')'))]


def judge_spam(rows, quick):
    cells = {}
    for r in rows:
        _, pair = split_name(r)
        cells.setdefault((pair, r['mode']), []).append(r)
    lines = ['SPAM  spammer (first) vs mixed defender (second): spammer wins before the night (B3 <= 15 %)']
    bad = []
    names = ['%s-%s' % p for p in ORDERED] + ['flood-%s' % f for f in FACS]
    for nm in names:
        col = []
        for m in ('kral', 'strateg'):
            rs = cells.get((nm, m), [])
            if not rs:
                col.append('-')
                continue
            w = mean(1.0 if (r['ws'] == 0 and not r['night']) else 0.0 for r in rs)
            col.append('%s n=%d%s' % (pct(w), len(rs), ' !' if w > 0.15 else ''))
            if w > 0.15:
                bad.append('%s %s %.0f%%' % (nm, m, 100 * w))
        lines.append('%-14s %-20s %-20s' % (nm, col[0], col[1] if len(col) > 1 else '-'))
    return lines, [('B3', not bad, 'spammer (and flood) wins before the night in <= 15 %' + ('' if not bad else ' (over: ' + '; '.join(bad) + ')'))]


def judge_ablate(rows, quick):
    lines = ['ABLATE  win rate of faction F: with the card (matrix cell F vs bez) minus with its shared stand-in (B5 <= +15 pp)',
             '%-11s %-5s %-24s %-24s %s' % ('card', 'fac', 'kral with/without/delta', 'strateg with/without/delta', 'pooled delta')]
    bad = []
    for card, fac in FB.CARD_FAC.items():
        col, d_all = [], []
        for m in ('kral', 'strateg'):
            ref = [1.0 - r['wa'] for r in rows if r['scen'] == 'matrix:bez-%s' % fac and r['mode'] == m]
            abl = [r['wa'] for r in rows if r['scen'] == 'ablate:%s' % card and r['mode'] == m]
            if not ref or not abl:
                col.append('-')
                continue
            d = 100 * (mean(ref) - mean(abl))
            d_all.append((ref, abl))
            col.append('%s %s %+5.1f%s' % (pct(mean(ref)), pct(mean(abl)), d, '!' if d > 15 else ' '))
        if d_all:
            ref = sum((x[0] for x in d_all), [])
            abl = sum((x[1] for x in d_all), [])
            dp = 100 * (mean(ref) - mean(abl))
            if dp > 15:
                bad.append('%s %+.1f pp' % (card, dp))
            lines.append('%-11s %-5s %-24s %-24s %+5.1f pp (n %d vs %d)' % (card, fac, col[0], col[1] if len(col) > 1 else '-', dp, len(ref), len(abl)))
        else:
            lines.append('%-11s %-5s no data' % (card, fac))
    use_lines, use_checks = judge_usage([r for r in rows if r['scen'].startswith('matrix:')])
    ok = not bad
    return lines, [('B5', ok, 'no faction card more than 15 pp better than its replacement' + ('' if ok else ' (over: ' + ', '.join(bad) + ')'))]


def judge_b6(rows, quick):
    w = {}
    for r in rows:
        w.setdefault(r['scen'], []).append(1 if (r['ws'] == 0 and not r['night']) else 0)
    w10, w05 = sum(w.get('b6:rules10', [])), sum(w.get('b6:rules05', []))
    n = len(w.get('b6:rules10', []))
    lines = ['B6  bez-bez mix Kral, attacker wins before the night: 1.0 rules %d/%d, 0.5 rules (compat05) %d/%d' % (w10, n, w05, len(w.get('b6:rules05', [])))]
    return lines, [('B6', n > 0 and abs(w10 - w05) <= 2, '1.0 rules within +-2 wins/20 of the 0.5 rules')]


# ---------------------------------------------------------------- selftest
def selftest(args):
    import copy
    lines, checks = [], []

    def chk(name, ok, text=''):
        checks.append((name, bool(ok), text))
        lines.append('  %-4s %s %s' % ('ok' if ok else 'FAIL', name, text))

    D, S, FM = H.D, H.S, H.FM
    # decks: 8 distinct cards of the faction pool, every role
    for f, roles in FB.FAC_DECKS.items():
        for role, deck in roles.items():
            chk('deck %s/%s' % (f, role), D.valid_deck(list(deck), f) is not None, str(deck) if D.valid_deck(list(deck), f) is None else '')
    # every faction card is in the duel deck of its faction
    chk('duel decks hold the 3 own cards', all(c in FB.FAC_DECKS[f]['duel'] for c, f in FB.CARD_FAC.items()))
    # ablation decks stay valid
    for card, f in FB.CARD_FAC.items():
        sc = FB.duel_scen(f, 'bez', ablate0=card)
        d = list(FB.FAC_DECKS[f]['duel']) if isinstance(sc['p0']['deck'], str) else sc['p0']['deck']
        chk('ablate %s deck' % card, D.valid_deck(list(d), f) is not None and card not in d)
    # one short mirrored pair: swap exchanges the sides, wa follows the scenario slot, same seed gives the same game
    scen = dict(FB.duel_scen('prez', 'korp'), length=300, t_end=240)
    a = H.run_game(T(scen, 'st', 'kral', 5, False))
    b = H.run_game(T(scen, 'st', 'kral', 5, True))
    a2 = H.run_game(T(scen, 'st', 'kral', 5, False))
    chk('fac per side', a['fac'] == ['prez', 'korp'] and b['fac'] == ['korp', 'prez'], '%s %s' % (a['fac'], b['fac']))
    chk('same seed, same game', a == a2)
    chk('wa follows the slot', all(r['wa'] == (0.5 if r['winner'] not in (0, 1) else float((r['winner'] == 0) != r['swap'])) for r in (a, b)))
    chk('mirrored games differ in seating only', a['length'] == b['length'] and a['night'] == b['night'])
    # usage and faction rules in a longer game (kult builds nests, throws hordes, raises)
    sk = dict(FB.duel_scen('kult', 'kult'), length=600, t_end=330)
    k = H.run_game(T(sk, 'st', 'kral', 3, False))
    chk('usage counts', all(k['used'][s].get('gen', 0) >= 3 for s in (0, 1)), str(k['used'][0]))
    chk('kult builds hnizdo, uses Mor and Tlupa', all(k['used'][s].get('hnizdo', 0) >= 1 for s in (0, 1)) and any(
        k['used'][s].get('horde', 0) >= 1 and k['used'][s].get('mor', 0) >= 1 for s in (0, 1)), str(k['used']))
    fl = H.run_game(T(dict(FB.flood_scen('bez'), t_end=300), 'st', 'kral', 3, False))
    chk('flood: Tlupa spam, no units', fl['used'][0].get('horde', 0) >= 5 and fl['u0_n'] == 0 and fl['used'][0].get('hnizdo', 0) == 2, str(fl['used'][0]))
    ke = H.run_game(T(dict(FB.duel_scen('korp', 'bez'), length=700, t_end=520), 'st', 'kral', 4, False))
    chk('korp uses exo and emp', ke['used'][0].get('exo', 0) >= 1 and ke['used'][0].get('emp', 0) >= 1, str(ke['used'][0]))
    # knobs apply for one game only
    z0 = FM.FACTIONS['prez']['mods']['zed_hp']
    kn = H.run_game(T(scen, 'st', 'kral', 5, False, knobs={'fac.prez.ucost': 1.6, 'def.emp.dur': 2.5, 'const.OWNED_CAP': 7}))
    chk('knobs reach the game', kn != a)
    chk('knobs are undone by the next game', H.run_game(T(scen, 'st', 'kral', 5, False)) == a)

    H.reset_rules()
    chk('reset_rules restores faction data', FM.FACTIONS['prez']['mods']['zed_hp'] == z0 and S.DEFS['emp']['dur'] == 4.0
        and FM.OWNED_CAP == H.ORIG_OWNED_CAP)
    # bez parity: a facrun crack scenario with bez on both sides plays like the plain run.py scenario
    for mode in ('kral', 'strateg'):
        p = H.run_game({'variant': 'base', 'scen': dict(R.SCEN['mix'], t_end=200), 'scen_name': 'mix', 'mode': mode, 'seed': 7})
        q = H.run_game(T(dict(FB.crack_scen('bez', 'bez'), t_end=200), 'mix', mode, 7, False))
        same = all(p[x] == q[x] for x in ('t', 'throne', 'winner', 'dealt', 'kills', 'casts', 'scrap'))
        chk('bez parity %s' % mode, same, '' if same else '%s %s' % (p['throne'], q['throne']))
    return lines, checks


# ---------------------------------------------------------------- driver
def report(lines_by_suite, checks, started, args):
    out = ['FACTION BALANCE REPORT  %s  %s%s' % (time.strftime('%Y-%m-%d %H:%M'), 'quick ' if args.quick else 'full ',
                                                 ('knobs ' + json.dumps(args.knobs)) if args.knobs else ''), '']
    for suite, lines in lines_by_suite:
        out += ['== %s' % suite] + lines + ['']
    out.append('== VERDICT (%.0f s)' % (time.time() - started))
    for cid, ok, text in checks:
        out.append('%-4s %-10s %s' % ('PASS' if ok else 'FAIL', cid, text))
    bad = [c for c in checks if not c[1]]
    out.append('RESULT: %s' % ('PASS' if not bad else 'FAIL (%s)' % ', '.join(c[0] for c in bad)))
    return '\n'.join(out), not bad


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('suite')
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--seeds', type=int)
    ap.add_argument('--modes', default='kral,strateg')
    ap.add_argument('--workers', type=int, default=int(os.environ.get('WORKERS', max(1, (os.cpu_count() or 4) - 1))))
    ap.add_argument('--tag', default='')
    ap.add_argument('--knob', action='append', default=[])
    ap.add_argument('--rejudge', action='store_true')
    args = ap.parse_args(argv)
    args.modes = args.modes.split(',')
    args.knobs = {}
    for kv in args.knob:
        k, _, v = kv.partition('=')
        args.knobs[k] = json.loads(v)
    tag = ('_' + args.tag) if args.tag else ''
    started = time.time()
    names = list(SUITES) if args.suite == 'all' else [args.suite]
    if names == ['selftest']:
        lines, checks = selftest(args)
        text, ok = report([('selftest', lines)], checks, started, args)
        print(text)
        return 0 if ok else 1
    for n in names:
        if n not in SUITES:
            ap.error('unknown suite %r (%s, all, selftest)' % (n, ', '.join(SUITES)))
    rows, lines_by_suite, checks = {}, [], []
    need_matrix = 'matrix' in names or 'fair' in names
    plan = [n for n in names if n not in ('fair',)]
    if 'fair' in names and 'matrix' not in names:
        plan = ['matrix'] + plan
    for n in plan:
        if n == 'perf':
            continue
        cached = load_rows(n, tag) if args.rejudge else None
        if args.rejudge and cached is None:
            print('no cached rows for %s%s, skipped' % (n, tag))
            continue
        if cached is not None:
            rows[n] = cached
            continue
        if n == 'matrix':
            tasks = tasks_matrix(args)
        elif n == 'crack':
            tasks = tasks_crack(args)
        elif n == 'spam':
            tasks = tasks_spam(args)
        elif n == 'ablate':
            have = 'matrix' in rows or bool(load_rows('matrix', tag))
            if 'matrix' not in rows and have:
                rows['matrix'] = load_rows('matrix', tag)
            tasks = tasks_ablate(args, have)
        elif n == 'b6':
            tasks = tasks_b6(args)
        print('%s: %d games, %d workers' % (n, len(tasks), args.workers), flush=True)
        rows[n] = play(tasks, args.workers, n, args.knobs)
        save_rows(n, tag, rows[n], args)
    for n in names:
        if n == 'matrix' and 'matrix' in rows:
            l, c = judge_matrix(rows['matrix'], args.quick)
        elif n == 'fair':
            if 'matrix' not in rows:
                continue
            l, c = judge_fair(rows['matrix'])
        elif n == 'crack' and 'crack' in rows:
            l, c = judge_crack(rows['crack'], args.quick)
        elif n == 'spam' and 'spam' in rows:
            l, c = judge_spam(rows['spam'], args.quick)
        elif n == 'ablate' and 'ablate' in rows:
            ref = rows['ablate'] + [r for r in rows.get('matrix', []) if r['scen'].startswith('matrix:bez-')]
            l, c = judge_ablate(ref, args.quick)
        elif n == 'b6' and 'b6' in rows:
            l, c = judge_b6(rows['b6'], args.quick)
        elif n == 'perf':
            if args.rejudge:
                continue
            print('perf: kult-kult duel, flood vs mixed, korp emprush (2 seeds per mode, one game at a time)', flush=True)
            with Pool(1) as p:
                prow, tot, bad = p.apply(_perf_job, (1 if args.quick else 2,))
            l = ['PERF  %d games: tick avg %.3f ms, worst p99 %.2f, max %.2f | snapshot avg %d B, max %d B | entities max %d' % (
                len(prow), tot['tick_avg'], tot['tick_p99'], tot['tick_max'], tot['bytes_avg'], tot['bytes_max'], tot['ents'])]
            l += ['  %-10s %-7s seed %d t %4d tick avg %.3f p99 %.2f max %.2f bytes max %5d ents %d' % (
                r['scen'], r['mode'], r['seed'], r['t'], r['tick_avg'], r['tick_p99'], r['tick_max'], r['bytes_max'], r['ents']) for r in prow]
            c = [('B7', not bad, 'tick avg <= 1.0 ms, p99 <= 3.0, max <= 15; snapshot avg <= 2.5 KB, max <= 6 KB; entities <= 160'
                  + ('' if not bad else ' (' + '; '.join(bad) + ')'))]
        else:
            continue
        lines_by_suite.append((n, l))
        checks += c
    text, ok = report(lines_by_suite, checks, started, args)
    print(text)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'report_fac%s%s.txt' % (tag, '' if args.suite == 'all' else '_' + args.suite)), 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
