"""Maps: terrain sets, BFS distance grids, MapDef, data/maps.json loader and the map pick."""
import json
import os
from collections import deque

from .defs import W, H, HALF, N4

WALK = frozenset('.~^=')
BUILD = frozenset('.^')
MAPS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'maps.json')


def bfs_from(ter, starts):
    inf = 999
    d = [[inf] * W for _ in range(H)]
    q = deque()
    for x, y in starts:
        if 0 <= x < W and 0 <= y < H and ter[y][x] in WALK:
            d[y][x] = 0
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in N4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and ter[ny][nx] in WALK and d[ny][nx] > d[y][x] + 1:
                d[ny][nx] = d[y][x] + 1
                q.append((nx, ny))
    return d


def bfs(ter, col):
    return bfs_from(ter, [(col, y) for y in range(H)])


class MapDef:
    """One board. `ter` is 9 strings of 16 chars (None for a random map until pick_map rolls it)."""

    def __init__(self, id, name, theme='', desc='', ter=None, relic=(7, 8, 3, 5), mid=(7, 8),
                 crate_rows=tuple(range(H)), spawn=((6, 7), (9, 8)), relic_fx=7.5, random=None):
        self.id = id
        self.name = name
        self.theme = theme
        self.desc = desc
        self.ter = ter
        self.relic = tuple(relic)            # (x0, x1, y0, y1)
        self.mid = tuple(mid)                # crate and Alfa columns
        self.crate_rows = tuple(crate_rows)
        self.spawn = tuple(tuple(c) for c in spawn)   # zombie spawn columns per target side
        self.relic_fx = relic_fx
        self.random = random                 # {'base': [x0, x1, n], 'mist': [x0, x1, n]} or None

    def rolled(self, ter):
        m = MapDef(self.id, self.name, self.theme, self.desc, ter, self.relic, self.mid, self.crate_rows,
                   self.spawn, self.relic_fx, self.random)
        return m


def make_random(rnd, R):
    """The 0.5 make_map with the generator R: same retry loop and draw order."""
    b0, b1, bn = rnd['base']
    m0, m1, mn = rnd['mist']
    for _ in range(200):
        ter = [['.'] * W for _ in range(H)]
        picks = R.sample([(x, y) for x in range(b0, b1 + 1) for y in range(H)], bn)
        picks += R.sample([(x, y) for x in range(m0, m1 + 1) for y in range(H)], mn)
        for x, y in picks:
            ter[y][x] = '#'
            ter[y][W - 1 - x] = '#'
        d0, d1 = bfs(ter, 0), bfs(ter, W - 1)
        if all(ter[y][x] == '#' or (d0[y][x] < 999 and d1[y][x] < 999) for y in range(H) for x in range(W)):
            return [''.join(r) for r in ter]
    return ['.' * W for _ in range(H)]


def validate_map(m):
    """None when the raw map entry (dict with 'half') is valid, otherwise the reason (str)."""
    half = m.get('half')
    if not (isinstance(half, list) and len(half) == H and all(isinstance(r, str) and len(r) == W // 2 for r in half)):
        return 'half musi mit 9 radku po 8 znacich'
    if any(c not in WALK and c not in '#Xw' for r in half for c in r):
        return 'neznamy znak terenu'
    if any(r[0] != '.' for r in half):
        return 'sloupec 0 musi byt volny'
    ter = [r + r[::-1] for r in half]
    relic = m.get('relic') or [3, 5]
    crates = m.get('crates') or list(range(H))
    if not (isinstance(relic, list) and len(relic) == 2 and all(isinstance(v, int) and 0 <= v < H for v in relic)
            and relic[0] <= relic[1]):
        return 'spatne radky relikvie'
    if not (isinstance(crates, list) and crates and all(isinstance(v, int) and 0 <= v < H for v in crates)):
        return 'spatne radky beden'
    if m.get('random'):
        return None                          # rubble is rolled per game; pick_map retries until it is connected
    walk = [[c in WALK for c in r] for r in ter]

    def reach(col):
        seen = [[False] * W for _ in range(H)]
        q = deque((col, y) for y in range(H) if walk[y][col])
        for x, y in q:
            seen[y][x] = True
        while q:
            x, y = q.popleft()
            for dx, dy in N4:
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and walk[ny][nx] and not seen[ny][nx]:
                    seen[ny][nx] = True
                    q.append((nx, ny))
        return seen
    r0, r1 = reach(0), reach(W - 1)
    if any(walk[y][x] and not (r0[y][x] and r1[y][x]) for y in range(H) for x in range(W)):
        return 'nektera pole nejsou dosazitelna z obou trunu'
    if sum(1 for y in range(H) for x in range(HALF) if ter[y][x] in BUILD) < 36:
        return 'malo stavebnich poli (sloupce 0-5)'
    if sum(1 for y in range(H) if ter[y][5] in BUILD) < 7:
        return 'malo stavebnich poli ve sloupci 5'
    if any(ter[y][x] not in WALK for y in range(relic[0], relic[1] + 1) for x in (7, 8)):
        return 'relikvie lezi na neprochozim poli'
    if any(ter[y][7] not in WALK for y in crates):
        return 'bedna by padla na neprochozi pole'
    if sum(1 for y in range(H) for x in (6, 7) if ter[y][x] in WALK) < 8:
        return 'malo poli pro zombie ve sloupcich 6-7'
    return None


def _mapdef(m):
    relic = m.get('relic') or [3, 5]
    half = m['half']
    ter = None if m.get('random') else [r + r[::-1] for r in half]
    return MapDef(m['id'], m.get('name', m['id']), m.get('theme', m['id']), m.get('desc', ''), ter,
                  relic=(7, 8, relic[0], relic[1]), crate_rows=tuple(m.get('crates') or range(H)),
                  random=m.get('random'))


RUINY = {'id': 'ruiny', 'name': 'Ruiny', 'theme': 'ruiny',
         'desc': 'Klasická mapa z 0.5: trosky se rozhodí pokaždé jinak.',
         'half': ['.' * 8] * H, 'relic': [3, 5], 'crates': list(range(H)),
         'random': {'base': [1, 4, 4], 'mist': [6, 7, 3]}}


def load_maps(path):
    """{id: MapDef} in file order. A bad entry is skipped with a console line; Ruiny is always present."""
    out = {}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        entries = raw.get('maps', []) if isinstance(raw, dict) else []
    except (OSError, ValueError) as e:
        print('  ! mapy nenacteny (%s): %s' % (path, e))
        entries = []
    for m in entries:
        mid = m.get('id') if isinstance(m, dict) else None
        if not isinstance(mid, str) or not mid or mid == 'nahodna' or mid in out:
            print('  ! mapa %s preskocena: chybne id' % mid)
            continue
        why = validate_map(m)
        if why:
            print('  ! mapa %s preskocena: %s' % (mid, why))
            continue
        out[mid] = _mapdef(m)
    if 'ruiny' not in out:
        out['ruiny'] = _mapdef(RUINY)
    return out


MAPS = load_maps(MAPS_PATH)


def pick_map(id, R):
    """MapDef with its terrain for one game. 'nahodna' picks uniformly with R; random rubble is rolled with R."""
    if id == 'nahodna':
        id = R.choice(list(MAPS))
    m = MAPS.get(id) or MAPS['ruiny']
    if m.random:
        return m.rolled(make_random(m.random, R))
    return m


def public_maps():
    return [{'id': m.id, 'name': m.name, 'desc': m.desc, 'theme': m.theme,
             'ter': ''.join(m.ter) if m.ter else None, 'relic': [m.relic[2], m.relic[3]],
             'crates': list(m.crate_rows)} for m in MAPS.values()]
