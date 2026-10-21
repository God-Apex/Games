"""Run balance experiments in parallel.
python run.py <variants comma-separated> <scenarios comma-separated> [seeds] [modes] [tag]"""
import json
import os
import statistics as st
import sys
import time
from multiprocessing import Pool

import harness as H

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = H._paths.OUT

H.COMPS['duel'] = ['obrnenec', 'pesak', 'pesak', 'obrnenec', 'pesak', 'pesak']

TURTLE = {'bot': 'turtle', 'deck': H.DEF_DECK, 'king': 'repair'}
TURTLE_FILL = dict(TURTLE, fill='kulomet', sn_max_price=250)
MIXED = {'bot': 'mixed', 'deck': H.MIX_DECK, 'king': 'repair'}
# sensible mixed army: Obrněnec tank in front, Medik behind, Pěšáci, Hlídka once Doba II, tlupa, Výpadek + Nálet
ATT = {'bot': 'att', 'deck': H.ATT_DECK_D2, 'comp': 'mix2', 'att_def': 'light', 'king': 'idle'}
ATT_ESC = dict(ATT, king='escort')
ATT_SN = {'bot': 'att', 'deck': H.ATT_DECK_SN, 'comp': 'mix', 'att_def': 'snipers', 'king': 'idle'}
SPAM = {'bot': 'att', 'deck': H.ATT_DECK, 'comp': 'inf', 'att_def': 'light', 'spam': True, 'horde': False, 'king': 'idle'}
SCEN = {
    'mix': {'p0': ATT, 'p1': TURTLE},                 # main test: sensible army vs pure 2-row sniper turtle
    'mixeco': {'p0': ATT, 'p1': dict(TURTLE, eco=True)},   # turtle that also takes its generators to level 3 early
    'mixesc': {'p0': ATT_ESC, 'p1': TURTLE},          # same, attacking King walks behind the push (kral only)
    'mixfill': {'p0': ATT, 'p1': TURTLE_FILL},        # turtle that fills with Kulomety when snipers get too pricey
    'snatt': {'p0': ATT_SN, 'p1': TURTLE},            # attacker with own Hláska + Odstřelovači
    'spam_mixed': {'p0': SPAM, 'p1': MIXED},          # careless spam vs mixed defence: must still hold
    'mix_mixed': {'p0': ATT, 'p1': MIXED},            # sensible army vs mixed defence: should be a fight
    'spam_turtle': {'p0': SPAM, 'p1': TURTLE},
    'duel': {'p0': dict(ATT, deck=H.DEF_DECK, comp='duel', att_def='col'), 'p1': dict(ATT, deck=H.DEF_DECK, comp='duel', att_def='col'),
             'length': 'rand', 't_end': 'over'},    # both: 1 sniper column + pushes; who wins, and when?
    'sym': {'p0': TURTLE, 'p1': TURTLE, 'length': 'rand', 't_end': 'over'},           # both turtle, to the end
    'mixecl': {'p0': dict(ATT, ecl=True), 'p1': TURTLE},      # attacker saves its pushes for the Zatmění windows
    'mixeclesc': {'p0': dict(ATT_ESC, ecl=True), 'p1': TURTLE},
    'duelecl': {'p0': dict(ATT, deck=H.DEF_DECK, comp='duel', att_def='col', ecl=True),
                'p1': dict(ATT, deck=H.DEF_DECK, comp='duel', att_def='col', ecl=True), 'length': 'rand', 't_end': 'over'},
    'symfill': {'p0': TURTLE_FILL, 'p1': TURTLE_FILL, 'length': 'rand', 't_end': 'over'},
}


def cpv(r, t, s):
    cp = r['cp']
    return (cp[str(t)] if str(t) in cp else cp[t])[s]


def summarize(rows):
    n = len(rows)
    m = lambda k: st.mean(r[k] for r in rows)
    spent = sum(r['u0_spent'] + r['h0_spent'] + r['a0_spent'] for r in rows)
    un = sum(r['u0_n'] for r in rows) or 1
    w0 = [r for r in rows if r['winner'] == 0]
    w1 = [r for r in rows if r['winner'] == 1]
    dr = [r for r in rows if r['winner'] == -1]
    casts = lambda c: round(st.mean(r['casts'].get(c, [0, 0])[0] for r in rows), 1)
    return {
        'n': n, 'W0': len(w0), 'W1': len(w1), 'D': len(dr),
        'W0pre': sum(1 for r in w0 if not r['night']), 'W1pre': sum(1 for r in w1 if not r['night']),
        'tW0pre': round(st.mean(r['t'] for r in w0 if not r['night'])) if any(not r['night'] for r in w0) else '-',
        'tW0min': min((r['t'] for r in w0 if not r['night']), default='-'),
        'tW0max': max((r['t'] for r in w0 if not r['night']), default='-'),
        'tW0': round(st.mean(r['t'] for r in w0)) if w0 else '-',
        'tEnd': round(m('t')),
        'th1@6': round(st.mean(cpv(r, 360, 1) for r in rows)),
        'th1@10': round(st.mean(cpv(r, 600, 1) for r in rows)),
        'th1': round(st.mean(r['throne'][1] for r in rows)), 'th0': round(st.mean(r['throne'][0] for r in rows)),
        'units': round(m('u0_n')), 'half%': round(100 * sum(r['u0_half'] for r in rows) / un),
        'past%': round(100 * sum(r['u0_past'] for r in rows) / un),
        'thr%': round(100 * sum(r['u0_throne'] for r in rows) / un),
        'spent0': round(spent / n), 'bld1': round(m('bld1_lost_n'), 1), 'bld0': round(m('bld0_lost_n'), 1),
        'sn1': round(m('snipers1'), 1), 'sn0': round(m('snipers0'), 1),
        'over%': round(100 * sum(r['sn1_over'] for r in rows) / max(1, sum(r['sn1_dmg_u'] + r['sn1_dmg_z'] + r['sn1_over'] for r in rows))),
        'tw1': round(m('tw1_spent')), 'e1': round(m('e1')), 'e0': round(m('e0')),
        'vyp': casts('vypadek'), 'nal': casts('nalet'),
    }


COLS = ['n', 'W0', 'W1', 'D', 'tW0', 'tEnd', 'th1@6', 'th1@10', 'th1', 'th0', 'units', 'half%', 'past%', 'thr%',
        'spent0', 'bld1', 'bld0', 'sn1', 'sn0', 'tw1', 'e1', 'e0', 'over%', 'vyp', 'nal']


def table(res, variants, scens, modes, out=sys.stdout):
    print('%-34s %-11s %-7s ' % ('variant', 'scen', 'mode') + ' '.join('%6s' % c for c in COLS), file=out)
    for v in variants:
        for sc in scens:
            for mode in modes + ['ALL']:
                rows = [r for r in res if r['variant'] == v and r['scen'] == sc and (mode == 'ALL' or r['mode'] == mode)]
                if not rows or (mode == 'ALL' and len(modes) == 1):
                    continue
                s = summarize(rows)
                print('%-34s %-11s %-7s ' % (v[:34], sc, mode) + ' '.join('%6s' % s[c] for c in COLS), file=out)


def ev(r, k):
    return r.get('ev', {}).get(k, 0)


def summarize2(rows):
    n = len(rows)
    m = lambda f: round(st.mean(f(r) for r in rows), 1)
    night = [r['t'] - r['length'] for r in rows if r['night']]
    return {
        'n': n, 'night%': round(100 * len(night) / n), 'nightLen': round(st.mean(night)) if night else '-',
        'nightMax': max(night) if night else '-', 'tbreak': sum(1 for r in rows if 'víc škody' in r['over']),
        'draw': sum(1 for r in rows if r['winner'] == -1),
        'relicFl': m(lambda r: ev(r, 'relic0') + ev(r, 'relic1')), 'held0': m(lambda r: r['relic_held'][0]),
        'held1': m(lambda r: r['relic_held'][1]), 'cr0': m(lambda r: r['crates'][0]), 'cr1': m(lambda r: r['crates'][1]),
        'contest': m(lambda r: ev(r, 'contest')), 'promo': m(lambda r: ev(r, 'promo0') + ev(r, 'promo1')),
        'ult': m(lambda r: ev(r, 'ult0') + ev(r, 'ult1')), 'utok': m(lambda r: ev(r, 'utok0') + ev(r, 'utok1')),
        'dash': m(lambda r: sum(v for k, v in r.get('fxn', {}).items() if k[0] == 'D')),
        'parry': m(lambda r: sum(v for k, v in r.get('fxn', {}).items() if k[0] == 'p')),
        'conv0': m(lambda r: r['conv'][0]), 'conv1': m(lambda r: r['conv'][1]),
        'dl0': m(lambda r: r['dealt'][0]), 'dl1': m(lambda r: r['dealt'][1]),
        'k0': m(lambda r: r['kills'][0]), 'k1': m(lambda r: r['kills'][1]),
        'v0': m(lambda r: r['v'][0]), 'v1': m(lambda r: r['v'][1]),
        'uthr': round(st.mean(min(x for x in r['first_uthrone'] if x is not None) for r in rows
                              if any(x is not None for x in r['first_uthrone']))) if any(
            any(x is not None for x in r['first_uthrone']) for r in rows) else '-',
    }


COLS2 = ['n', 'draw', 'night%', 'nightLen', 'nightMax', 'tbreak', 'uthr', 'relicFl', 'held0', 'held1', 'cr0', 'cr1', 'contest',
         'promo', 'ult', 'utok', 'dash', 'parry', 'conv0', 'conv1', 'dl0', 'dl1', 'k0', 'k1', 'v0', 'v1']


def table2(res, variants, scens, modes, out=sys.stdout):
    if not any('ev' in r for r in res):
        return
    print('%-34s %-11s %-7s ' % ('variant (0.5 metrics)', 'scen', 'mode') + ' '.join('%7s' % c for c in COLS2), file=out)
    for v in variants:
        for sc in scens:
            for mode in modes + ['ALL']:
                rows = [r for r in res if r['variant'] == v and r['scen'] == sc and (mode == 'ALL' or r['mode'] == mode)]
                if not rows or (mode == 'ALL' and len(modes) == 1):
                    continue
                s2 = summarize2(rows)
                print('%-34s %-11s %-7s ' % (v[:34], sc, mode) + ' '.join('%7s' % s2[c] for c in COLS2), file=out)


def main():
    variants = sys.argv[1].split(',')
    scens = sys.argv[2].split(',')
    seeds = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    modes = sys.argv[4].split(',') if len(sys.argv) > 4 else ['kral', 'strateg']
    tag = sys.argv[5] if len(sys.argv) > 5 else 'run'
    tasks = []
    for v in variants:
        for sc in scens:
            for mode in modes:
                if sc in ('mixesc', 'mixeclesc') and mode != 'kral':
                    continue
                for seed in range(seeds):
                    scen = SCEN[sc]
                    if os.environ.get('FULL'):          # random 10-15 min length, play on through Poslední noc
                        scen = dict(scen, length='rand', t_end='over')
                    tasks.append({'variant': v, 'scen': scen, 'scen_name': sc, 'mode': mode, 'seed': 1000 + seed})
    t0 = time.time()
    with Pool(int(os.environ.get('WORKERS', max(1, (os.cpu_count() or 4) - 1)))) as p:
        res = p.map(H.run_game, tasks, chunksize=1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'out_%s.json' % tag), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False)
    print('%d games in %.0f s' % (len(res), time.time() - t0))
    table(res, variants, scens, modes)
    table2(res, variants, scens, modes)


if __name__ == '__main__':
    main()
