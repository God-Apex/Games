"""Tick time and snapshot size in busy bot games (harness), incl. JSON encoding of both snapshots.

usage: python perf.py [scen,scen] [seeds]                 raw numbers for the server under test (HMK_SERVER / <game>/server.py)
       python perf.py --compare [scen,scen] [seeds]       frozen 0.5 copy and the server under test one after the other
                                                          on this machine; exit 1 when the tick average is more than
                                                          10 % slower than 0.5 (M1 gate: within +-10 %, 0.5 reference
                                                          0.34-0.61 ms per tick on the dev PC)
       add --b7 to either form to also judge the absolute numbers of SPEC 7.2 B7:
                                                          tick avg <= 1.0 ms, p99 <= 3.0 ms, max <= 15 ms,
                                                          snapshot avg <= 2.5 KB, max <= 6 KB, entities <= 160
Scenarios are the ones of bal/run.py (default: mix,duel; --full: mix,spam_mixed,duel,sym; seeds default 2, 1 for --compare which plays every game 4 times).
Games run one after the other (no parallel load) so the timings are comparable.
"""
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'bal'))
import _paths  # noqa: E402

REF_05_MS = (0.34, 0.61)          # tick average of the 0.5 server on the dev PC (balance report, 2025)
B7 = {'tick_avg': 1.0, 'tick_p99': 3.0, 'tick_max': 15.0, 'snap_avg_b': 2500, 'snap_max_b': 6000, 'ents': 160}


def measure(scens, seeds):
    """-> list of per-game dicts for the server under test."""
    import harness as H
    import run as R
    S = H.S
    stats = []
    it0 = H.install_tracking

    def it():
        it0()
        step0 = S.Game.step

        def step(self, dt):
            t0 = time.perf_counter()
            step0(self, dt)
            t1 = time.perf_counter()
            b = [len(json.dumps(self.snapshot(s, self.fx), ensure_ascii=False, separators=(',', ':')).encode('utf-8')) for s in (0, 1)]
            t2 = time.perf_counter()
            st = stats[-1]
            st['tick'].append((t1 - t0) * 1000)
            st['snap'].append((t2 - t1) * 1000)
            st['bytes'].append(max(b))
            st['ents'] = max(st['ents'], len(self.ents))
        S.Game.step = step
    H.install_tracking = it
    rows = []
    for sc in scens:
        for mode in ('kral', 'strateg'):
            for seed in range(seeds):
                stats.append({'tick': [], 'snap': [], 'bytes': [], 'ents': 0})
                r = H.run_game({'variant': 'base', 'scen': dict(R.SCEN[sc], length='rand', t_end='over'), 'scen_name': sc,
                                'mode': mode, 'seed': 1000 + seed})
                st = stats[-1]
                tk = sorted(st['tick'])
                rows.append({'scen': sc, 'mode': mode, 'seed': seed, 't': r['t'], 'ticks': len(tk),
                             'tick_avg': sum(tk) / len(tk), 'tick_p99': tk[int(len(tk) * 0.99)], 'tick_max': tk[-1],
                             'snap_ms': sum(st['snap']) / len(st['snap']), 'bytes_avg': sum(st['bytes']) / len(st['bytes']),
                             'bytes_max': max(st['bytes']), 'ents': st['ents']})
    return rows


def show(rows, out=print):
    for r in rows:
        out('%-11s %-7s seed %d  t %4d  ticks %5d  tick avg %.3f ms p99 %.2f max %.2f | snap+json avg %.3f ms | '
            'bytes avg %d max %d | ents max %d' % (r['scen'], r['mode'], r['seed'], r['t'], r['ticks'], r['tick_avg'],
                                                   r['tick_p99'], r['tick_max'], r['snap_ms'], r['bytes_avg'], r['bytes_max'], r['ents']))


def total(rows):
    n = sum(r['ticks'] for r in rows)
    return {'tick_avg': sum(r['tick_avg'] * r['ticks'] for r in rows) / n, 'tick_p99': max(r['tick_p99'] for r in rows),
            'tick_max': max(r['tick_max'] for r in rows), 'bytes_avg': sum(r['bytes_avg'] * r['ticks'] for r in rows) / n,
            'bytes_max': max(r['bytes_max'] for r in rows), 'ents': max(r['ents'] for r in rows), 'ticks': n}


def b7_verdict(tot):
    bad = []
    if tot['tick_avg'] > B7['tick_avg']:
        bad.append('tick avg %.3f > %.1f ms' % (tot['tick_avg'], B7['tick_avg']))
    if tot['tick_p99'] > B7['tick_p99']:
        bad.append('tick p99 %.2f > %.1f ms' % (tot['tick_p99'], B7['tick_p99']))
    if tot['tick_max'] > B7['tick_max']:
        bad.append('tick max %.2f > %.0f ms' % (tot['tick_max'], B7['tick_max']))
    if tot['bytes_avg'] > B7['snap_avg_b']:
        bad.append('snapshot avg %d > %d B' % (tot['bytes_avg'], B7['snap_avg_b']))
    if tot['bytes_max'] > B7['snap_max_b']:
        bad.append('snapshot max %d > %d B' % (tot['bytes_max'], B7['snap_max_b']))
    if tot['ents'] > B7['ents']:
        bad.append('entities %d > %d' % (tot['ents'], B7['ents']))
    return bad


def _child(server, scens, seeds):
    """Run measure() for one server in a fresh process (so the module state of the two servers never mixes)."""
    out = os.path.join(_paths.OUT, 'perf_%d_%s.json' % (os.getpid(), 'old' if server == _paths.SERVER_05 else 'new'))
    os.makedirs(_paths.OUT, exist_ok=True)
    env = dict(os.environ, HMK_SERVER=server, PYTHONDONTWRITEBYTECODE='1')
    p = subprocess.run([sys.executable, os.path.abspath(__file__), '--child', out, ','.join(scens), str(seeds)], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise RuntimeError('perf child failed:\n' + p.stdout.decode('utf-8', 'replace')[-3000:])
    with open(out, encoding='utf-8') as f:
        rows = json.load(f)
    os.remove(out)
    return rows


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    flags = [a for a in argv if a.startswith('--')]
    if flags and flags[0] == '--child':          # internal: --child OUT scens seeds
        out, scens, seeds = argv[1], argv[2].split(','), int(argv[3])
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(measure(scens, seeds), f)
        return 0
    compare = '--compare' in flags
    full = '--full' in flags
    default = 'mix,spam_mixed,duel,sym' if full else 'mix,duel'
    scens = (args[0] if args else default).split(',')
    seeds = int(args[1]) if len(args) > 1 else (1 if compare else 2)
    rc = 0
    if not compare:
        rows = measure(scens, seeds)
        show(rows)
        tot = total(rows)
        print('TOTAL tick avg %.3f ms, worst p99 %.2f, max %.2f | snapshot avg %d B, max %d B | entities max %d' % (
            tot['tick_avg'], tot['tick_p99'], tot['tick_max'], tot['bytes_avg'], tot['bytes_max'], tot['ents']))
        if '--b7' in flags:
            bad = b7_verdict(tot)
            print('B7:', 'OK' if not bad else 'FAIL ' + '; '.join(bad))
            rc = 1 if bad else 0
        return rc
    new_path = _paths.server_path()
    print('perf compare: scenarios %s x 2 modes x %d seeds (one game at a time)' % (','.join(scens), seeds))
    old_rows = _child(_paths.SERVER_05, scens, seeds)
    new_rows = _child(new_path, scens, seeds)
    # second pass in the opposite order damps drift (thermal / background load); the lower tick average per side counts
    new_rows2 = _child(new_path, scens, seeds)
    old_rows2 = _child(_paths.SERVER_05, scens, seeds)
    o1, o2, n1, n2 = total(old_rows), total(old_rows2), total(new_rows), total(new_rows2)
    old_t, new_t = min(o1['tick_avg'], o2['tick_avg']), min(n1['tick_avg'], n2['tick_avg'])
    ratio = new_t / old_t
    print('0.5 copy      : tick avg %.3f ms (runs %.3f, %.3f)  (reference range %.2f-%.2f ms)' % (old_t, o1['tick_avg'], o2['tick_avg'], *REF_05_MS))
    print('server (new)  : tick avg %.3f ms (runs %.3f, %.3f)' % (new_t, n1['tick_avg'], n2['tick_avg']))
    print('ratio new/old : %.3f  -> %s' % (ratio, 'OK (within +-10 %)' if 0.9 <= ratio <= 1.1 else
                                           'faster than 0.5 (OK)' if ratio < 0.9 else 'FAIL: more than 10 % slower'))
    tot = n1 if n1['tick_avg'] <= n2['tick_avg'] else n2
    print('new: tick p99 %.2f ms, max %.2f ms | snapshot avg %d B, max %d B | entities max %d' % (
        tot['tick_p99'], tot['tick_max'], tot['bytes_avg'], tot['bytes_max'], tot['ents']))
    if ratio > 1.1:
        rc = 1
    if '--b7' in flags:
        bad = b7_verdict(tot)
        print('B7:', 'OK' if not bad else 'FAIL ' + '; '.join(bad))
        rc = rc or (1 if bad else 0)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
