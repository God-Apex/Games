"""M3-B2: puzzles (SPEC 5.2, MAI 7). Every scripted solution earns 3 stars twice with identical metrics, idle play never
earns 3 stars, plus the loader, the rules hooks, the messages and the relic_squads foe script.

Needs the 1.0 package (skipped on the frozen 0.5 server)."""
import json
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('needs the 1.0 hmk package')
import puzzle_solutions as PS  # noqa: E402
from hmk import puzzle, modes  # noqa: E402
from hmk.defs import TICK  # noqa: E402

IDS = ['p%02d' % i for i in range(1, 11)]


class Solutions(unittest.TestCase):
    def test_solutions_three_stars_deterministic(self):
        for pid in IDS:
            with self.subTest(pid=pid):
                a, g = PS.run(pid)
                b, _ = PS.run(pid)
                self.assertEqual(g.over['code'], 'solved', a)
                self.assertTrue(a['ok'])
                self.assertEqual(a['stars'], 3, a)
                self.assertEqual(a['hit'], [True, True, True])            # end.puzzle.hit (client star list)
                self.assertEqual(a['metrics'], b['metrics'])
                self.assertEqual(a['t'], b['t'])

    def test_idle_never_three_stars(self):
        for pid in IDS:
            with self.subTest(pid=pid):
                res, g = PS.run(pid, [])
                self.assertIn(g.over['code'], ('solved', 'failed'))
                self.assertLess(res['stars'], 3, res)
                self.assertEqual(len(res['hit']), 3)
                self.assertEqual(res['stars'], sum(res['hit']), res)


class Data(unittest.TestCase):
    def test_ten_puzzles_public(self):
        self.assertEqual(list(puzzle.PUZZLES), IDS)
        pub = puzzle.public_puzzles()
        self.assertEqual([p['id'] for p in pub], IDS)
        for p in pub:
            for k in ('id', 'name', 'desc', 'mode', 'time', 'goal_text', 'stars_text'):
                self.assertIn(k, p)
            self.assertEqual(len(p['stars_text']), 3)
            self.assertTrue(all(isinstance(t, str) and t for t in p['stars_text']))
            self.assertTrue(p['goal_text'])
        for p in puzzle.PUZZLES.values():
            self.assertEqual(p['fac'], 'bez')
            self.assertTrue(set(SOLUTIONS_KEYS) >= {p['id']})

    def test_bad_entry_skipped(self):
        good = dict(puzzle.PUZZLES['p02'])
        bad = dict(good, id='zz', goal={'type': 'night'})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'p.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'puzzles': [good, bad, {'id': 'yy'}]}, f)
            got = puzzle.load_puzzles(path)
        self.assertEqual(list(got), ['p02'])
        self.assertEqual(puzzle.load_puzzles(os.path.join(HERE, 'missing.json')), {})

    def test_make_rules(self):
        r = modes.make_rules('puzzle', {'puzzle': 'p05', 'mode': 'strateg'})
        self.assertIsInstance(r, puzzle.PuzzleRules)
        self.assertEqual(r.play, 'puzzle')
        self.assertIsNone(modes.make_rules('puzzle', {'puzzle': 'nope'}))

    def test_eval_stars(self):
        p = puzzle.PUZZLES['p04']            # win, time_max 30, spent_max 170
        m = {'ok': True, 't': 25.0, 'spent': 200}
        self.assertEqual(puzzle.eval_stars(p, None, m), 2)
        m.update(spent=170)
        self.assertEqual(puzzle.eval_stars(p, None, m), 3)
        m.update(ok=False)
        self.assertEqual(puzzle.eval_stars(p, None, m), 0)


SOLUTIONS_KEYS = list(PS.SOLUTIONS)


class Rules(unittest.TestCase):
    def test_setup_and_messages(self):
        g = PS.build('p02')
        sd = g.sd[0]
        self.assertEqual(g.mode, 'kral')
        self.assertEqual(g.map.id, 'predmesti')
        self.assertEqual(g.seed, 2)
        self.assertEqual(sd.deck, ['kulomet', 'plamen', 'mina', 'zed'])
        self.assertEqual((int(sd.e), int(sd.s)), (250, 40))
        self.assertEqual(g.throne, [1200.0, 3000.0])
        self.assertIsNotNone(sd.kral)
        self.assertIsNone(g.sd[1].kral)
        self.assertEqual(sum(1 for e in g.ents.values() if e.side == 1), 5)
        st = g.start_info(0)
        self.assertEqual(st['kit'], [])
        self.assertEqual(st['deck'], sd.deck)
        self.assertEqual(st['puzzle']['id'], 'p02')
        self.assertEqual(st['puzzle']['throne'], [1200, 3000])
        self.assertEqual(st['thmax'], [1200, 3000])                   # per-side throne maximum for the HUD
        self.assertIsNone(st['relic_at'])                              # p02 has no Relikvie
        self.assertEqual(PS.build('p08').start_info(0)['relic_at'], 0)
        g.step(TICK)
        snap = g.snapshot(0, [])
        self.assertEqual(snap['pz'], [30, 0, 30])
        self.assertEqual(snap['inc'], 0.0)
        self.assertNotIn('pz', g.snapshot(1, []))
        e0 = sd.e
        for _ in range(40):
            g.step(TICK)
        self.assertAlmostEqual(sd.e, e0, places=6)          # income 0 replaces BASE_INCOME

    def test_kit_and_horde_refused(self):
        g = PS.build('p02')
        g.act(0, {'t': 'build', 'kind': 'gen', 'x': 2, 'y': 0})
        self.assertFalse(any(e.kind == 'gen' for e in g.ents.values()))
        self.assertIn((puzzle.NOKIT, 'e'), g.msgs[0])
        g.act(0, {'t': 'build', 'kind': 'zed', 'x': 2, 'y': 0})       # zed is in this deck
        self.assertTrue(any(e.kind == 'zed' and e.side == 0 for e in g.ents.values()))
        g.act(0, {'t': 'horde'})
        self.assertIn((puzzle.NOHORDE, 'e'), g.msgs[0])
        g1 = PS.build('p01')                                          # kit: true
        g1.act(0, {'t': 'build', 'kind': 'gen', 'x': 2, 'y': 0})
        self.assertTrue(any(e.kind == 'gen' for e in g1.ents.values()))
        self.assertEqual(g1.start_info(0)['kit'], ['gen', 'zed'])

    def test_end_info_and_failure(self):
        res, g = PS.run('p03', [])
        end = g.end_info()
        self.assertEqual(end['code'], 'failed')
        self.assertEqual(end['winner'], 1)
        self.assertEqual(end['puzzle']['id'], 'p03')
        self.assertFalse(end['puzzle']['ok'])
        self.assertEqual(end['puzzle']['stars'], 0)
        self.assertEqual(end['puzzle']['hit'], [False, False, False])
        for k in ('t', 'throne', 'spent', 'lost', 'king_hp', 'parries', 'left', 'cards', 'units', 'alive'):
            self.assertIn(k, end['puzzle']['metrics'])
        g2 = PS.build('p04')                                          # quit before the end: not solved
        self.assertFalse(g2.end_info()['puzzle']['ok'])

    def test_king_must_live(self):
        g = PS.build('p03')
        g.kill(g.sd[0].kral, 1)
        g.step(TICK)
        self.assertEqual(g.over['code'], 'failed')

    def test_relic_squads_and_eclipse(self):
        res, g = PS.run('p08', [], limit=25)
        self.assertTrue(g.relic['on'])
        self.assertGreaterEqual(g.sd[1].stats['units'], 3)          # squads at t 1 and t 21
        g7 = PS.build('p07')
        while g7.t < 9:
            g7.step(TICK)
        self.assertEqual(g7.eclipse()[0], 2)


if __name__ == '__main__':
    unittest.main()
