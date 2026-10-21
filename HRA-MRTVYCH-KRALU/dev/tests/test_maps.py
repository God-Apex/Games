"""M2-A: the five maps (data/maps.json), validate_map, load_maps, pick_map and the WALK/BUILD sets (SPEC 5.1, MAI 3).

Needs the 1.0 package (skipped on the frozen 0.5 server).
"""
import importlib.util
import json
import os
import random
import sys
import tempfile
import unittest
from collections import deque

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('needs the 1.0 hmk package')
from hmk import maps  # noqa: E402
from hmk.defs import W, H, N4  # noqa: E402

IDS = ['ruiny', 'predmesti', 'tovarna', 'most', 'metro']


def raw_entries():
    with open(maps.MAPS_PATH, encoding='utf-8') as fh:
        return json.load(fh)['maps']


def reach(ter, col):
    """Independent flood fill over WALK cells from every WALK cell of column `col`."""
    walk = set('.~^=')
    seen = {(col, y) for y in range(H) if ter[y][col] in walk}
    q = deque(seen)
    while q:
        x, y = q.popleft()
        for dx, dy in N4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and ter[ny][nx] in walk and (nx, ny) not in seen:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


class TestMapData(unittest.TestCase):
    def test_five_maps_in_file_order(self):
        self.assertEqual(list(maps.MAPS), IDS)
        self.assertEqual([m['id'] for m in raw_entries()], IDS)

    def test_validate_map_passes_for_all_five(self):
        for m in raw_entries():
            self.assertIsNone(maps.validate_map(m), m['id'])

    def test_walk_build_sets(self):
        self.assertEqual(maps.WALK, frozenset('.~^='))
        self.assertEqual(maps.BUILD, frozenset('.^'))

    def test_boards_are_mirrored_9x16_and_use_known_terrain(self):
        for mid, m in maps.MAPS.items():
            if m.ter is None:
                self.assertEqual(mid, 'ruiny')
                continue
            self.assertEqual(len(m.ter), H, mid)
            for y, row in enumerate(m.ter):
                self.assertEqual(len(row), W, mid)
                self.assertEqual(row, row[::-1], '%s row %d is not mirror symmetric' % (mid, y))
                self.assertTrue(set(row) <= set('.#Xw=~^'), mid)
                self.assertEqual(row[0], '.', '%s throne column must be free' % mid)

    def test_every_walk_cell_reachable_from_both_throne_columns(self):
        for mid, m in maps.MAPS.items():
            if m.ter is None:
                continue
            walk = {(x, y) for y in range(H) for x in range(W) if m.ter[y][x] in '.~^='}
            self.assertEqual(reach(m.ter, 0), walk, mid + ' from the left throne')
            self.assertEqual(reach(m.ter, W - 1), walk, mid + ' from the right throne')

    def test_map_fields(self):
        most, metro, tov = maps.MAPS['most'], maps.MAPS['metro'], maps.MAPS['tovarna']
        self.assertEqual(maps.MAPS['ruiny'].relic, (7, 8, 3, 5))
        self.assertEqual(most.relic, (7, 8, 4, 4))
        self.assertEqual(most.crate_rows, (1, 7))
        self.assertEqual(metro.crate_rows, (0, 1, 3, 4, 5, 7, 8))
        self.assertEqual(tov.crate_rows, (2, 3, 4, 5, 6))
        for m in maps.MAPS.values():
            self.assertEqual(m.mid, (7, 8))
            self.assertEqual(m.spawn, ((6, 7), (9, 8)))
            self.assertEqual(m.relic_fx, 7.5)

    def test_relic_cells_walkable_and_crate_cells_walkable(self):
        for mid, m in maps.MAPS.items():
            if m.ter is None:
                continue
            x0, x1, y0, y1 = m.relic
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    self.assertIn(m.ter[y][x], maps.WALK, '%s relic cell %d,%d' % (mid, x, y))
            for y in m.crate_rows:
                for x in m.mid:
                    self.assertIn(m.ter[y][x], maps.WALK, '%s crate cell %d,%d' % (mid, x, y))

    def test_public_maps_payload(self):
        pub = {m['id']: m for m in maps.public_maps()}
        self.assertEqual(list(pub), IDS)
        self.assertIsNone(pub['ruiny']['ter'])
        for mid in IDS[1:]:
            self.assertEqual(len(pub[mid]['ter']), W * H)
        self.assertEqual(pub['most']['relic'], [4, 4])
        self.assertEqual(pub['most']['crates'], [1, 7])
        json.dumps(pub)


class TestValidateRejects(unittest.TestCase):
    def base(self):
        return {'id': 'x', 'half': ['........'] * H, 'relic': [3, 5], 'crates': list(range(H))}

    def test_bad_shapes_and_characters(self):
        m = self.base()
        m['half'] = ['........'] * 8
        self.assertIsNotNone(maps.validate_map(m))
        m = self.base()
        m['half'][2] = '.......'
        self.assertIsNotNone(maps.validate_map(m))
        m = self.base()
        m['half'][2] = '...Q....'
        self.assertIn('znak', maps.validate_map(m))

    def test_throne_column_must_be_free(self):
        m = self.base()
        m['half'][4] = '#.......'
        self.assertIn('sloupec 0', maps.validate_map(m))

    def test_unreachable_pocket(self):
        m = self.base()
        m['half'][0] = '.XXXXXXX'
        m['half'][1] = '.X.....X'      # 6 free cells walled in by pillars; (x=2..6,y=1) cannot be reached
        m['half'][2] = '.XXXXXXX'
        self.assertIn('dosa', maps.validate_map(m))

    def test_relic_on_a_wall(self):
        m = self.base()
        m['half'][4] = '.......X'
        self.assertIn('relikv', maps.validate_map(m))

    def test_crate_row_on_a_wall(self):
        m = self.base()
        m['half'][0] = '.......w'
        m['crates'] = [0]
        self.assertIn('bedna', maps.validate_map(m))

    def test_too_few_build_cells(self):
        m = self.base()
        for y in range(H):
            m['half'][y] = '.~~~~~~~'
        self.assertIn('stavebn', maps.validate_map(m))

    def test_too_few_zombie_cells(self):
        m = self.base()
        m['half'] = ['......XX'] * H
        m['half'][4] = '........'          # one lane only: 2 walkable cells in columns 6-7
        m['relic'] = [4, 4]
        m['crates'] = [4]
        self.assertIn('zombie', maps.validate_map(m))

    def test_bad_relic_and_crate_rows(self):
        m = self.base()
        m['relic'] = [5, 3]
        self.assertIn('relikvie', maps.validate_map(m))
        m = self.base()
        m['crates'] = [99]
        self.assertIn('beden', maps.validate_map(m))


class TestLoadMaps(unittest.TestCase):
    def test_bad_entries_are_skipped_with_a_console_line(self):
        good = raw_entries()[1]
        bad_shape = {'id': 'zle', 'half': ['..']}
        dup = dict(good)
        entries = [good, bad_shape, dup, {'id': 'nahodna', 'half': good['half']}, 'junk']
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'maps.json')
            with open(p, 'w', encoding='utf-8') as fh:
                json.dump({'v': 1, 'maps': entries}, fh)
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                out = maps.load_maps(p)
        self.assertEqual(list(out), ['predmesti', 'ruiny'], 'bad entries dropped, Ruiny always present')
        text = buf.getvalue()
        self.assertIn('  ! mapa zle preskocena: ', text)
        self.assertIn('  ! mapa predmesti preskocena: chybne id', text)   # the duplicate
        self.assertIn('  ! mapa nahodna preskocena', text)

    def test_missing_file_falls_back_to_ruiny(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            out = maps.load_maps(os.path.join(tempfile.gettempdir(), 'hmk-no-such-maps.json'))
        self.assertEqual(list(out), ['ruiny'])


class TestPickMap(unittest.TestCase):
    def test_nahodna_is_uniform_over_500_seeds(self):
        n = {mid: 0 for mid in IDS}
        for seed in range(500):
            n[maps.pick_map('nahodna', random.Random(seed)).id] += 1
        for mid, c in n.items():
            self.assertTrue(80 <= c <= 120, '%s picked %d of 500 (want 20 +- 4 %%): %s' % (mid, c, n))

    def test_pick_is_deterministic_per_seed(self):
        for seed in (1, 7, 42):
            a = maps.pick_map('nahodna', random.Random(seed))
            b = maps.pick_map('nahodna', random.Random(seed))
            self.assertEqual((a.id, a.ter), (b.id, b.ter))

    def test_unknown_id_falls_back_to_ruiny(self):
        self.assertEqual(maps.pick_map('nic', random.Random(1)).id, 'ruiny')

    def test_fixed_maps_do_not_consume_random_numbers(self):
        for mid in IDS[1:]:
            R = random.Random(9)
            before = R.getstate()
            m = maps.pick_map(mid, R)
            self.assertEqual(R.getstate(), before, mid)
            self.assertIs(m, maps.MAPS[mid])

    def test_ruiny_rolls_rubble_and_leaves_the_definition_untouched(self):
        a = maps.pick_map('ruiny', random.Random(3))
        b = maps.pick_map('ruiny', random.Random(4))
        self.assertIsNotNone(a.ter)
        self.assertIsNone(maps.MAPS['ruiny'].ter)
        self.assertNotEqual(a.ter, b.ter)
        for m in (a, b):
            self.assertEqual(sum(r.count('#') for r in m.ter), 14)
            for row in m.ter:
                self.assertEqual(row, row[::-1])

    def test_ruiny_reproduces_the_05_make_map_exactly(self):
        spec = importlib.util.spec_from_file_location('server05_for_maps', _paths.SERVER_05)
        old = importlib.util.module_from_spec(spec)
        argv, sys.argv = sys.argv, [sys.argv[0]]
        try:
            spec.loader.exec_module(old)
        finally:
            sys.argv = argv
        for seed in range(1, 41):
            random.seed(seed)
            a = [''.join(r) for r in old.make_map()]
            after_old = random.random()
            random.seed(seed)
            m = maps.pick_map('ruiny', random)
            after_new = random.random()
            self.assertEqual(m.ter, a, 'seed %d: other rubble' % seed)
            self.assertEqual(after_old, after_new, 'seed %d: different number of random draws' % seed)

    def test_bfs_uses_walk_cells(self):
        ter = [list(r) for r in maps.MAPS['tovarna'].ter]
        d = maps.bfs(ter, 0)
        for y in range(H):
            for x in range(W):
                if ter[y][x] in 'X#':
                    self.assertEqual(d[y][x], 999)
                else:
                    self.assertLess(d[y][x], 999)
        d = maps.bfs([list(r) for r in maps.MAPS['most'].ter], 0)
        self.assertLess(d[4][8], 999, 'bridge cell is reachable')
        self.assertEqual(d[0][7], 999, 'water is never entered')


if __name__ == '__main__':
    unittest.main()
