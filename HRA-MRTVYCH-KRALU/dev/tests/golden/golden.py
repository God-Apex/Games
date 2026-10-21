"""Golden regression (SPEC 7.1): the 1.0 engine, run with compat05, must stay bit-identical to the frozen 0.5 server.

Both sides play the same harness match (Mixed vs Attacker, the bots in bal/harness.py) for N seeds x modes with
random.seed(seed); the state hash (golden/statehash.py) is taken every 60 s of game time (1200 ticks). A run is
identical when every checkpoint hash, the end reason and the winner match.

  old side = golden/server_05.py (never edited)       new side = <game>/server.py  (or HMK_SERVER / --new)
  Game(..., rng=random, compat05=True) is used on the new side by _paths.new_game.

usage: python golden.py [--seeds 1-10] [--modes kral,strateg] [--secs 600] [--every 1200] [--procs N]
                        [--old PATH] [--new PATH]
  tip: after a mismatch, find the first diverging tick with  --seeds 3 --modes kral --every 20
Exit code 0 only when every run is identical (20/20 for the full gate).
"""
import json
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.dirname(HERE)
for _p in (TESTS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _paths  # noqa: E402

TICKS_60S = 1200


def parse_seeds(txt):
    out = []
    for part in txt.split(','):
        if '-' in part:
            a, b = part.split('-')
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


# ---------------------------------------------------------------- worker side (one process per server under test)
def run_one(task):
    seed, mode, secs, every = task
    sys.path.insert(0, os.path.join(TESTS, 'bal'))
    import harness as H
    import run as R
    import statehash
    S = H.S
    hashes = []
    check = {'method': 'missing' if not hasattr(S.Game, 'state_hash') else 'ok'}

    def hook(g, n):
        if n % every == 0:
            h = statehash.state_hash(g)
            hashes.append([n, round(g.t, 6), h])
            if check['method'] == 'ok' and g.state_hash() != h:
                check['method'] = 'Game.state_hash() differs from golden/statehash.py at tick %d' % n

    H.TICK_HOOKS[:] = [hook]
    scen = {'p0': R.MIXED, 'p1': R.ATT, 'length': 720, 't_end': secs}
    t0 = time.time()
    r = H.run_game({'variant': 'base', 'scen': scen, 'scen_name': 'golden', 'mode': mode, 'seed': seed, 'compat05': True})
    H.TICK_HOOKS[:] = []
    return {'seed': seed, 'mode': mode, 'hashes': hashes, 'over': r['over'], 'winner': r['winner'], 't': r['t'],
            'throne': r['throne'], 'state_hash_method': check['method'], 'wall': round(time.time() - t0, 1)}


def worker_main(args):
    from multiprocessing import Pool
    tasks = [(s, m, args.secs, args.every) for s in parse_seeds(args.seeds) for m in args.modes.split(',')]
    procs = max(1, min(args.procs, len(tasks)))
    if procs == 1:
        res = [run_one(t) for t in tasks]
    else:
        with Pool(procs) as p:
            res = p.map(run_one, tasks, chunksize=1)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(res, f)


# ---------------------------------------------------------------- orchestrator
def _launch(label, server, args, procs):
    out = os.path.join(_paths.OUT, 'golden_%s_%d.json' % (label, os.getpid()))
    env = dict(os.environ, HMK_SERVER=server, PYTHONDONTWRITEBYTECODE='1')
    cmd = [sys.executable, os.path.abspath(__file__), '--worker', '--seeds', args['seeds'], '--modes', args['modes'],
           '--secs', str(args['secs']), '--every', str(args['every']), '--procs', str(procs), '--out', out]
    return subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT), out


def _short(path):
    rel = os.path.relpath(path, _paths.GAME)
    return path if rel.startswith('..') else rel


def compare(old, new):
    """-> list of (seed, mode, ok, message)"""
    rows = []
    key = lambda r: (r['seed'], r['mode'])
    nm = {key(r): r for r in new}
    for o in old:
        n = nm.get(key(o))
        if n is None:
            rows.append((o['seed'], o['mode'], False, 'missing on the new side'))
            continue
        msg = ''
        ok = True
        for a, b in zip(o['hashes'], n['hashes']):
            if a != b:
                ok = False
                msg = 'first difference at tick %d (t=%.2f): old %s.. new %s..' % (b[0], b[1], a[2][:10], b[2][:10])
                break
        if ok and len(o['hashes']) != len(n['hashes']):
            ok, msg = False, 'checkpoint count %d vs %d' % (len(o['hashes']), len(n['hashes']))
        if ok and (o['over'], o['winner']) != (n['over'], n['winner']):
            ok, msg = False, 'end differs: %r/%r vs %r/%r' % (o['over'], o['winner'], n['over'], n['winner'])
        if ok:
            msg = '%d checkpoints, t=%s, over=%r' % (len(o['hashes']), o['t'], o['over'] or '-')
        rows.append((o['seed'], o['mode'], ok, msg))
    return rows


def run_golden(seeds='1-10', modes='kral,strateg', secs=600, every=TICKS_60S, procs=None, old=None, new=None, log=print):
    """Returns (ok, rows, notes). `rows` as in compare(); `notes` = warnings such as a missing Game.state_hash."""
    os.makedirs(_paths.OUT, exist_ok=True)
    old = old or _paths.SERVER_05
    new = _paths.server_path(new)
    procs = procs or max(2, (os.cpu_count() or 4))
    per = max(1, procs // 2)
    a = {'seeds': seeds, 'modes': modes, 'secs': secs, 'every': every}
    t0 = time.time()
    p_old, f_old = _launch('old', old, a, per)
    p_new, f_new = _launch('new', new, a, per)
    outs = {}
    for label, p in (('old', p_old), ('new', p_new)):
        txt = p.communicate()[0].decode('utf-8', 'replace')
        if p.returncode != 0:
            raise RuntimeError('%s worker failed (exit %s):\n%s' % (label, p.returncode, txt[-3000:]))
    with open(f_old, encoding='utf-8') as f:
        old_res = json.load(f)
    with open(f_new, encoding='utf-8') as f:
        new_res = json.load(f)
    for f in (f_old, f_new):
        try:
            os.remove(f)
        except OSError:
            pass
    rows = compare(old_res, new_res)
    notes = sorted({r['state_hash_method'] for r in new_res if r['state_hash_method'] != 'ok'})
    log('golden: old=%s new=%s  (%.0f s)' % (_short(old), _short(new), time.time() - t0))
    return all(r[2] for r in rows), rows, notes


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--seeds', default='1-10')
    ap.add_argument('--modes', default='kral,strateg')
    ap.add_argument('--secs', type=int, default=600)
    ap.add_argument('--every', type=int, default=TICKS_60S, help='ticks between hashes (1200 = 60 s)')
    ap.add_argument('--procs', type=int, default=0)
    ap.add_argument('--old', default=None)
    ap.add_argument('--new', default=None)
    ap.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--out', default='', help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        return worker_main(args)
    ok, rows, notes = run_golden(args.seeds, args.modes, args.secs, args.every, args.procs or None, args.old, args.new)
    for seed, mode, good, msg in rows:
        print('%-4s seed %-3d %-8s %s' % ('ok' if good else 'DIFF', seed, mode, msg))
    for n in notes:
        print('NOTE: ' + n)
    n_ok = sum(1 for r in rows if r[2])
    print('%d/%d runs identical' % (n_ok, len(rows)))
    return 0 if ok and n_ok == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
