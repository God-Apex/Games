"""Scripted headless match on the server under test; dumps real snapshots (both sides) for windows with relic capture,
contested crate, promotion, war cry, dash, King kill, eclipse and Poslední noc, plus the end payload.
usage: python replay.py [out.js]   (default dev/tests/_out/_test_replay.js, the replay page of the client tests)"""
import json
import os
import random
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
OUT_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_paths.OUT, '_test_replay.js')

deck = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'dron']
g = _paths.new_game(S, ['Kostěný', 'Popelavý'], [deck, deck], 'kral', seed=7)
g.ter = [['.'] * S.W for _ in range(S.H)]
g.dist = [S.bfs(g.ter, 0), S.bfs(g.ter, S.W - 1)]
g.length = 292.0
WIN = [(110, 145), (236, 248), (290, 400)]
out = {0: [], 1: []}
end = None
stunned = []

def L(s, x):
    return x if s == 0 else S.W - 1 - x

def unit(kind, s, x, y, stun=False):
    e = g.spawn(kind, s, x, y)
    if stun:
        e.stun = 1e9
        stunned.append(e)
    return e

tick = 0
cr = None
while not g.over and g.t < 400:
    t = g.t
    for s in (0, 1):
        sd = g.sd[s]
        if tick == 1:
            sd.e, sd.s = 2000, 300
            for kind, x, y in [('gen', 0, 1), ('gen', 0, 7), ('kulomet', 4, 2), ('kulomet', 4, 6), ('sniper', 2, 4), ('hlaska', 3, 4), ('plamen', 5, 4), ('zed', 5, 2)]:
                g.act(s, {'t': 'build', 'kind': kind, 'x': L(s, x), 'y': y})
            for e in list(g.ents.values()):
                if e.side == s and e.kind in ('kulomet', 'sniper'):
                    g.act(s, {'t': 'upg', 'id': e.id})
                    g.act(s, {'t': 'upg', 'id': e.id, 'path': 'A' if s == 0 else 'B'})
        if tick % 300 == 150 + s * 40:
            sd.e += 200
            g.act(s, {'t': 'unit', 'kind': random.choice(['pesak', 'jezdec', 'obrnenec']), 'x': L(s, 5), 'y': random.randrange(S.H)})
    if tick == 110 * 20:
        unit('obrnenec', 0, 7, 4, True)                      # takes the relic at about 125 s
    if tick == 124 * 20:
        g.drop_crate(8, 6, 3, land=0.0)
        cr = max(g.crates)
        unit('jezdec', 0, 8, 6, True)                        # side 0 channels the crate
    if 124 * 20 <= tick < 132 * 20 and g.sd[1].kral:         # side 1's King stands next to it: contested
        k = g.sd[1].kral
        k.x, k.y, k.cx, k.cy = 8.3, 6.0, 8, 6
    if tick == 127 * 20:
        unit('pesak', 0, 14, 3)                              # walks onto the enemy throne column: promotion
    if tick == 129 * 20:
        g.sd[1].ult = 100.0
        g.act(1, {'t': 'in', 'mx': 0, 'my': 0, 'b': False, 'r': False, 'd': False, 'u': True})
    if tick == 129 * 20 + 2:
        g.act(1, {'t': 'in', 'mx': 0, 'my': 0, 'b': False, 'r': False, 'd': False, 'u': False})
    if tick == 133 * 20:
        g.act(0, {'t': 'in', 'mx': 1, 'my': 0, 'b': False, 'r': False, 'd': True, 'u': False})
    if tick == 133 * 20 + 2:
        g.act(0, {'t': 'in', 'mx': 0, 'my': 0, 'b': False, 'r': False, 'd': False, 'u': False})
    if tick == 140 * 20 and g.sd[1].kral:
        g.damage(g.sd[1].kral, 5000, 0)
    if tick == 305 * 20:
        g.throne[1] = 1.0
    g.step(S.TICK)
    tick += 1
    fx = g.fx
    g.fx = []
    snaps = [g.snapshot(0, fx), g.snapshot(1, fx)]
    if any(a <= g.t < b for a, b in WIN) or g.over:
        for s in (0, 1):
            out[s].append(snaps[s])
if g.over:
    end = {'t': 'end', 'winner': g.over['winner'], 'reason': g.over['reason'], 'tm': round(g.t),
           'stats': [g.sd[0].stats, g.sd[1].stats], 'names': g.names, 'th': [int(g.throne[0]), int(g.throne[1])],
           'dl': [int(g.dealt[0]), int(g.dealt[1])]}
seen = {}
for s in (0, 1):
    evs, fxs = set(), set()
    for m in out[s]:
        evs.update(e[0] for e in m.get('ev', []))
        fxs.update(f[0] for f in m['fx'])
    seen[s] = (sorted(evs), sorted(fxs))
start = {'t': 'start', 'names': g.names, 'w': S.W, 'h': S.H, 'half': S.HALF, 'mist': S.MIST, 'mode': 'kral', 'deck': deck,
         'throne': S.THRONE_HP, 'horde': [S.HORDE_COST, S.HORDE_CD]}
js = 'window.REPLAY = ' + json.dumps({'start': start, 's0': out[0], 's1': out[1], 'end': end}, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + ';\n'
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write(js)
print('snaps', len(out[0]), 'bytes', len(js), 'end', end and end['reason'], 'tm', g.t)
print('side0', seen[0])
print('side1', seen[1])
crs = [(m['tm'], m['cr']) for m in out[0] if m['cr']][:1] + [(m['tm'], m['cr']) for m in out[0] if any(c[8] for c in m['cr'])][:1]
print('crates', crs)
print('rl samples', [(m['tm'], m['rl']) for m in out[0][::100]])
print('ec samples', [(m['tm'], m['ec'], m['st'], m['ni']) for m in out[0][::150]])
