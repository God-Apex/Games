"""M2-A: terrain rules of the new map characters (SPEC 5.1, MAI 3.1): WALK/BUILD checks, canal `~`, raised ground `^`,
crates/zombies/Navnada on the new boards. Needs the 1.0 package (skipped on the frozen 0.5 server)."""
import os
import random
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('needs the 1.0 hmk package')
from hmk import maps  # noqa: E402
from hmk import defs as D  # noqa: E402
from hmk.defs import W, H, TICK, DEFS, KRAL  # noqa: E402

DECK = ['navnada', 'kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec']
FLAT = ['.' * W] * H


def game(mode='strateg', rows=None, map_id=None, seed=1, deck=DECK):
    """A quiet game: no waves, crates or Alfa unless the test asks for them, rich players."""
    R = random.Random(seed)
    md = maps.pick_map(map_id, R) if map_id else None
    g = S.Game(['A', 'B'], [list(deck), list(deck)], mode, map_def=md, seed=seed)
    if rows is not None:
        g.ter = [list(r) for r in rows]
        g.dist = [maps.bfs(g.ter, 0), maps.bfs(g.ter, W - 1)]
    g.next_wave = g.next_crate = g.next_alfa = 1e9
    g.length = 1e9
    for sd in g.sd:
        sd.e, sd.s = 5000.0, 500.0
    return g


def row4(chars, fill='.'):
    """FLAT with row 4 starting with `chars`."""
    rows = list(FLAT)
    rows[4] = (chars + fill * W)[:W]
    return rows


def run(g, secs):
    for _ in range(int(round(secs / TICK))):
        g.step(TICK)
        g.fx, g.msgs, g.evs, g.pfx = [], [[], []], [[], []], [[], []]


class TestPlacement(unittest.TestCase):
    CHARS = '.^~=XW#'        # W is replaced by the water char 'w' below (kept upper case in the label only)

    def board(self):
        return game(rows=row4('.^~=Xw#'))

    def test_build_only_on_dlazba_and_vyvyseni(self):
        g = self.board()
        for x in range(7):
            g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': x, 'y': 4})
        built = sorted(e.cx for e in g.ents.values() if e.cat == 'b')
        self.assertEqual(built, [0, 1], 'only "." and "^" can be built on: %s' % built)
        self.assertIn('Tady stavět nejde.', [t for t, _ in g.msgs[0]])

    def test_deploy_only_on_dlazba_and_vyvyseni(self):
        g = self.board()
        for x in range(7):
            g.act(0, {'t': 'unit', 'kind': 'pesak', 'x': x, 'y': 4})
        placed = sorted(e.cx for e in g.ents.values() if e.cat == 'u')
        self.assertEqual(placed, [0, 1], placed)

    def test_navnada_needs_a_walk_cell(self):
        g = game(rows=row4('.~X=w#'))
        ok = {}
        for x in range(6):
            sd = g.sd[0]
            sd.cd.clear()
            g.lure = None
            g.act(0, {'t': 'card', 'id': 'navnada', 'x': x, 'y': 4})
            ok[x] = g.lure is not None
        self.assertEqual(ok, {0: True, 1: True, 2: False, 3: True, 4: False, 5: False})

    def test_scrap_still_only_on_rubble(self):
        g = game(rows=row4('..#X'))
        s0 = g.sd[0].s
        self.assertEqual(g.dist[1][4][2], 999, 'rubble is not walkable before it is cleared')
        g.act(0, {'t': 'scrap', 'x': 3, 'y': 4})       # a pillar is not rubble
        self.assertIsNone(g.sd[0].job)
        g.act(0, {'t': 'scrap', 'x': 2, 'y': 4})
        run(g, D.SCRAP_TIME + 0.5)
        self.assertEqual(g.ter[4][2], '.')
        self.assertEqual(g.ter[4][3], 'X')
        self.assertEqual(g.sd[0].s, s0 + D.SCRAP_GAIN)
        self.assertEqual(g.dist[1][4][2], maps.bfs(g.ter, W - 1)[4][2], 'dist is rebuilt after the scrap job')
        self.assertLess(g.dist[1][4][2], 999)


class TestMovementCells(unittest.TestCase):
    def test_can_enter_by_terrain(self):
        g = game(rows=row4('.~^=Xw#'))
        p = g.spawn('pesak', 1, 9, 2)
        z = g.spawn('chodec', 2, 9, 6)
        for x, ch in enumerate('.~^=Xw#'):
            want = ch in '.~^='
            self.assertEqual(g.can_enter(p, x, 4), want, 'pesak into %r' % ch)
            self.assertEqual(g.can_enter(z, x, 4), want, 'zombie into %r' % ch)

    def test_king_walks_on_bridge_and_canal_not_through_walls(self):
        g = game('kral', rows=row4('.~^=Xw#'))
        k = g.sd[0].kral
        for x, ch in enumerate('.~^=Xw#'):
            self.assertEqual(g.kral_blocked(k, float(x), 4.0), ch not in '.~^=', 'King on %r' % ch)

    def test_jezdec_still_jumps_over_pillars_water_and_rubble(self):
        rows = [r[:4] + 'X' + r[5:] for r in FLAT]            # a pillar wall across column 4
        g = game(rows=rows)
        j = g.spawn('jezdec', 0, 3, 4)
        run(g, 6.0)
        self.assertGreaterEqual(j.cx, 5, 'the Jezdec should have jumped the wall (cx=%d)' % j.cx)

    def test_units_path_around_pillars_on_every_map(self):
        for mid in ('tovarna', 'most', 'metro', 'predmesti'):
            g = game(map_id=mid)
            for s in (0, 1):
                grid = g.dist[s]
                for y in range(H):
                    for x in range(W):
                        self.assertEqual(grid[y][x] < 999, g.ter[y][x] in maps.WALK, '%s dist[%d] at %d,%d' % (mid, s, x, y))


class TestCanal(unittest.TestCase):
    def crossing(self, rows):
        """Ticks a Pěšák needs from arriving on x=4 to arriving on x=8 (four cells x=4..7 between)."""
        g = game(rows=rows)
        p = g.spawn('pesak', 0, 3, 4)
        t4 = t8 = None
        for n in range(1, 2000):
            g.step(TICK)
            if t4 is None and p.cx == 4:
                t4 = n
            if p.cx >= 8:
                t8 = n
                break
        self.assertIsNotNone(t8, 'the Pěšák never crossed')
        return t8 - t4

    def test_four_canal_cells_take_075_of_the_time(self):
        base = self.crossing(FLAT)
        canal = self.crossing(row4('....~~~~'))
        self.assertAlmostEqual(canal / base, 0.75, delta=0.02 * 0.75, msg='canal %d ticks vs %d on dlazba' % (canal, base))

    def test_step_of_on_canal_for_units_and_zombies_only(self):
        g = game(rows=row4('~.'))
        p = g.spawn('pesak', 0, 0, 4)
        q = g.spawn('pesak', 0, 1, 4)
        z = g.spawn('chodec', 2, 1, 5)
        self.assertAlmostEqual(g.step_of(p), 0.75 * g.step_of(q))
        self.assertAlmostEqual(g.step_of(z), DEFS['chodec']['step'])
        g2 = game(rows=row4('~.'))
        z1 = g2.spawn('chodec', 2, 0, 4)
        z2 = g2.spawn('chodec', 2, 1, 4)
        self.assertAlmostEqual(g2.step_of(z1), 0.75 * g2.step_of(z2))

    def test_king_runs_125_on_canal(self):
        def dist(rows):
            g = game('kral', rows=rows)
            k = g.sd[0].kral
            k.x, k.y, k.cx, k.cy = 1.0, 4.0, 1, 4
            g.act(0, {'t': 'in', 'mx': 1, 'my': 0})
            run(g, 1.0)
            return k.x - 1.0
        ratio = dist(row4('~~~~~~~~')) / dist(FLAT)
        self.assertAlmostEqual(ratio, 1.25, delta=0.02)
        self.assertGreater(KRAL['speed'], 0)


class TestRaisedGround(unittest.TestCase):
    def test_range_and_vision_plus_one_on_raised_ground_only(self):
        g = game(rows=row4('.^'))
        a = g.spawn('kulomet', 0, 0, 4)
        b = g.spawn('kulomet', 0, 1, 4)
        self.assertAlmostEqual(g.rng(b), g.rng(a) + 1.0)
        self.assertAlmostEqual(g.rng(b), DEFS['kulomet']['range'] + 1.0)
        self.assertAlmostEqual(g.vision(b), g.vision(a) + 1.0)
        w = g.spawn('zed', 0, 1, 5)
        self.assertAlmostEqual(g.vision(w), DEFS['zed']['vision'], msg='row 5 is plain dlazba')
        pe = g.spawn('pesak', 0, 1, 6)
        self.assertAlmostEqual(g.vision(pe), DEFS['pesak']['vision'])
        for e in (a, b):
            e.lvl = 3
        self.assertAlmostEqual(g.rng(b), g.rng(a) + 1.0, msg='bonus stacks with level range')

    def test_kulomet_on_raised_ground_hits_at_range_plus_one(self):
        """Foe 4.0 cells away: out of reach of a Kulomet on dlazba (3.2), inside on `^` (4.2)."""
        def hp_after(ch):
            g = game(rows=row4('...' + ch))                 # tower at (3,4)
            tw = g.spawn('kulomet', 0, 3, 4)
            foe = g.spawn('pesak', 1, 7, 4)
            foe.stun = 1e9
            foe.hp = foe.maxhp = 100000.0
            g.sd[0].reveals.append([7, 4, 1e9, 3.0])        # the foe stands in Mist, light it so the tower may shoot
            run(g, 3.0)
            return foe.hp, tw
        hp_dl, _ = hp_after('.')
        hp_up, tw = hp_after('^')
        mist_only = 100000.0 - 1.5 * 3.0
        self.assertAlmostEqual(hp_dl, mist_only, delta=0.5, msg='on dlazba only the Mist hurts the foe')
        self.assertLess(hp_up, mist_only - 20, 'on ^ the Kulomet reaches 4 cells: hp %s' % hp_up)


class TestWorldOnNewMaps(unittest.TestCase):
    def test_crates_land_on_walk_cells_of_the_crate_rows(self):
        for mid in ('most', 'metro', 'tovarna', 'predmesti'):
            g = game(map_id=mid)
            seen = set()
            for _ in range(60):
                g.crates.clear()
                g.drop_crate(land=0.0)
                (c,) = g.crates.values()
                seen.add((c['x'], c['y']))
                self.assertIn(c['x'], g.map.mid, mid)
                self.assertIn(c['y'], g.map.crate_rows, mid)
                self.assertIn(g.ter[c['y']][c['x']], maps.WALK, mid)
            self.assertGreaterEqual(len(seen), 3, '%s: crates should vary' % mid)
        g = game(map_id='most')
        g.crates.clear()
        for _ in range(10):
            g.crates.clear()
            g.drop_crate(land=0.0)
            (c,) = g.crates.values()
            self.assertIn(c['y'], (1, 7))
            self.assertEqual(g.ter[c['y']][c['x']], '=')

    def test_zombies_spawn_on_walk_cells_only(self):
        for mid in ('most', 'tovarna', 'metro', 'predmesti'):
            g = game(map_id=mid)
            for cols, tgt in (((6, 7), 0), ((9, 8), 1)):
                n = g.spawn_zombies(['chodec'] * 40, cols, tgt)
                want = sum(1 for x in cols for y in range(H) if g.map.ter[y][x] in maps.WALK)
                self.assertEqual(n, want, '%s cols %s: all free walkable cells used, nothing else' % (mid, cols))
            for e in g.ents.values():
                self.assertIn(g.ter[e.cy][e.cx], maps.WALK, mid)
            g2 = game(map_id=mid)
            for _ in range(8):
                g2.wave()
            for e in g2.ents.values():
                self.assertIn(g2.ter[e.cy][e.cx], maps.WALK, mid)

    def test_idle_match_on_every_map_zombies_reach_a_throne(self):
        for mid in maps.MAPS:
            g = game(map_id=mid, seed=3)
            g.next_wave = 5.0
            run(g, 110)
            self.assertLess(min(g.throne), D.THRONE_HP, '%s: waves never reached a throne' % mid)

    def test_relic_zone_of_most_is_one_bridge_row(self):
        self.assertEqual(maps.MAPS['most'].relic, (7, 8, 4, 4))

        def holder(x, y):
            g = game(map_id='most')
            g.t = g.prev_t = D.RELIC_FROM + 0.1
            p = g.spawn('pesak', 0, x, y)
            p.stun = 1e9
            run(g, D.RELIC_TIME + 1.5)
            return g.relic['own']
        self.assertEqual(holder(7, 4), 0, 'a unit on the bridge row takes the relic')
        self.assertEqual(holder(7, 7), -1, 'a unit on another bridge row does not')


if __name__ == '__main__':
    unittest.main()
