"""Short form of the golden regression (the full gate is golden/golden.py: seeds 1-10, 600 s, 20/20).
Here: seeds 1-2 x {kral, strateg}, 180 s, a hash every 60 s, 0.5 copy vs the server under test."""
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'golden'))
import _paths  # noqa: E402
import golden  # noqa: E402
import statehash  # noqa: E402


class TestGolden(unittest.TestCase):
    def test_short_golden_identical(self):
        ok, rows, notes = golden.run_golden(seeds='1-2', modes='kral,strateg', secs=180, log=lambda *a: None)
        bad = ['seed %s %s: %s' % (s, m, msg) for s, m, good, msg in rows if not good]
        self.assertTrue(ok and len(rows) == 4, 'not identical to 0.5: ' + '; '.join(bad))
        self.assertNotIn('differs', ' '.join(notes), ' '.join(notes))

    def test_golden_detects_a_difference(self):
        """Self-test: a copy of the 0.5 server with BASE_INCOME 1.5 -> 1.6 must be reported as different."""
        src = open(_paths.SERVER_05, encoding='utf-8').read()
        self.assertIn('\nBASE_INCOME = 1.5', src)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'server.py')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(src.replace('\nBASE_INCOME = 1.5', '\nBASE_INCOME = 1.6'))
            ok, rows, _ = golden.run_golden(seeds='1', modes='kral', secs=60, every=200, new=p, log=lambda *a: None)
        self.assertFalse(ok)
        self.assertIn('first difference', rows[0][3])

    def test_state_hash_reference(self):
        S = _paths.load_server()
        g = _paths.new_game(S, ['A', 'B'], [list(S.RECOMMENDED)] * 2, 'kral', seed=3)
        h0 = statehash.state_hash(g)
        self.assertEqual(h0, statehash.state_hash(g))
        for _ in range(40):
            g.step(S.TICK)
        h1 = statehash.state_hash(g)
        self.assertNotEqual(h0, h1)
        self.assertEqual(len(h1), 40)
        if hasattr(g, 'state_hash'):
            self.assertEqual(g.state_hash(), h1, 'Game.state_hash() must equal golden/statehash.state_hash()')
        g.sd[0].e += 0.001
        self.assertNotEqual(h1, statehash.state_hash(g))


if __name__ == '__main__':
    unittest.main()
