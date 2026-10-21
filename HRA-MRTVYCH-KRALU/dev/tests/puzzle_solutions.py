"""Scripted 3-star solutions of the ten puzzles (MAI 7.2). A designer who changes a puzzle must update its solution.

SOLUTIONS[id] = [[t, msg], ...]: messages side 0 sends at game time t (sent before the step that passes t).
King input ('in') holds until the next 'in'. run(id) plays one puzzle headless and returns (result, game).

  python dev/tests/puzzle_solutions.py [id ...] [--idle] [--trace]   prints result and metrics
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()


def K(mx=0, my=0, b=False, d=False, u=False, r=False):
    """King input message."""
    return {'t': 'in', 'mx': mx, 'my': my, 'b': b, 'd': d, 'u': u, 'r': r}


def U(kind, x, y):
    return {'t': 'unit', 'kind': kind, 'x': x, 'y': y}


def B(kind, x, y):
    return {'t': 'build', 'kind': kind, 'x': x, 'y': y}


def C(card, x=-1, y=-1):
    return {'t': 'card', 'id': card, 'x': x, 'y': y}


def CMD(cid, x=-1, y=-1):
    return {'t': 'cmd', 'id': cid, 'x': x, 'y': y}


SOLUTIONS = {
    # two Kulomets cover rows 1-7, the Plamenomet in front of the throne burns what slips through
    'p01': [[0, B('kulomet', 2, 3)], [0, B('kulomet', 2, 5)], [0, B('plamen', 1, 4)]],
    # Kulomets out of the lanes, three mines on the approach, the King steps out and repairs (R) with scrap
    'p02': [[0, B('kulomet', 2, 3)], [0, B('kulomet', 2, 5)], [0, B('mina', 5, 3)], [0, B('mina', 5, 5)], [0, B('mina', 4, 4)],
            [0.05, K(1)], [0.45, K(r=True)]],
    # run to the crate, stop on it and block just before both snipers fire (two parries)
    'p03': [[0, K(1)], [3.0, K(0)], [3.1, K(b=True)], [3.6, K()]],
    # the Obrněnec breaks the wall in the Hláska's row, two cheap Pěšáci soak up the Kulomets
    'p04': [[0, U('obrnenec', 5, 4)], [0, U('pesak', 4, 4)], [0, U('pesak', 5, 3)]],
    # two Obrněnci take the sniper shots (armour vs ranged), two Pěšáci follow and finish the towers
    'p05': [[0, U('obrnenec', 5, 4)], [0, U('obrnenec', 5, 3)], [0, U('pesak', 4, 4)], [0, U('pesak', 4, 3)]],
    # Obrněnci soak the Kulomet and the Plamenomet on the edge rows, four Pěšáci fill rows 0, 2, 6, 8 beside the throne
    'p06': [[0, U('obrnenec', 5, 1)], [0, U('obrnenec', 5, 7)], [0, U('pesak', 5, 0)], [0, U('pesak', 5, 8)],
            [0, U('pesak', 5, 2)], [0, U('pesak', 5, 6)]],
    # wait, then send the whole army so it reaches the towers in the dark (eclipse at t 8)
    'p07': [[4, U('obrnenec', 5, 4)], [4, U('jezdec', 5, 1)], [4, U('jezdec', 5, 7)], [4, U('pesak', 4, 4)],
            [4, U('pesak', 5, 3)], [4, U('pesak', 5, 5)]],
    # three Kulomets cover the Relikvie from the edge of the base, a Pěšák every 2.5 s keeps someone standing on it
    'p08': [[0, B('kulomet', 5, 3)], [0, B('kulomet', 5, 5)], [0, B('kulomet', 4, 4)]] +
           [[t * 2.5, U('pesak', 5, 4)] for t in range(25)],
    # a Návnada between the two generators (lit by the opening reveal) pulls the whole horde onto them, renewed at once
    'p09': [[0.1, C('navnada', 13, 4)], [20.2, C('navnada', 13, 4)]],
    # the King walks up to row 1 and shoots the upper Plamenomet out of the Hláska's sight, the Obrněnec opens row 2
    # and takes the sniper shots, the Pěšák follows it and slips past onto the throne column
    'p10': [[0, K(0, -1)], [0.77, K(1, 0)], [4.62, K(0, -1)], [5.0, K()],
            [0, U('obrnenec', 5, 2)], [3, U('pesak', 5, 2)]],
}


def build(pid):
    from hmk import puzzle, session
    p = puzzle.PUZZLES[pid]
    g, _ = session.build_game('puzzle', {'mode': p['mode'], 'map': p['map'], 'puzzle': pid},
                              [('Tester', [], 'bez'), None])
    return g


def run(pid, sol=None, limit=None, trace=None):
    """Play puzzle pid with solution `sol` (default SOLUTIONS[pid]; [] = idle). Returns (result dict, game)."""
    from hmk.defs import TICK
    g = build(pid)
    sol = sorted(SOLUTIONS[pid] if sol is None else sol, key=lambda m: m[0])
    i = 0
    limit = limit or g.rules.p['time'] + 5
    while not g.over and g.t < limit:
        while i < len(sol) and sol[i][0] <= g.t + 1e-9:
            g.act(0, dict(sol[i][1]))
            i += 1
        g.step(TICK)
        g.fx = []
        if trace:
            trace(g)
    g.msgs = [[], []]
    return g.rules.result, g


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    idle = '--idle' in sys.argv
    from hmk import puzzle
    for pid in args or list(puzzle.PUZZLES):
        res, g = run(pid, [] if idle else None)
        print(pid, g.over and g.over.get('code'), res and res['stars'], res and res['metrics'])
