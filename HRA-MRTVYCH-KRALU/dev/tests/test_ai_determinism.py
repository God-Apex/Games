"""AI determinism and think cost (MAI 5.6, SPEC M2 gate): Těžká vs Střední, 300 s, seed 5, run in two subprocesses
with PYTHONHASHSEED 1 and 2 -> equal state_hash. The Těžká think must average <= 2 ms."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LADDER = os.path.join(HERE, 'ai_ladder.py')


def run(hashseed, mode):
    env = dict(os.environ, PYTHONHASHSEED=str(hashseed))
    env.pop('HMK_AI_PATCH', None)
    out = subprocess.run([sys.executable, LADDER, '--hash', 'tezka', 'stredni', mode, 'ruiny', '5', '300'],
                         env=env, capture_output=True, text=True, timeout=600, cwd=HERE)
    line = [x for x in out.stdout.splitlines() if x.startswith('HASH')]
    if not line:
        raise AssertionError('no HASH line:\n' + out.stdout + out.stderr)
    p = line[0].split()
    return p[1], float(p[3]), float(p[6])


class TestAIDeterminism(unittest.TestCase):
    def test_hashseed_independent(self):
        for mode in ('kral', 'strateg'):
            h1, t1, avg1 = run(1, mode)
            h2, t2, avg2 = run(2, mode)
            self.assertEqual(h1, h2, 'state_hash differs between PYTHONHASHSEED 1 and 2 (%s)' % mode)
            self.assertGreater(t1, 299.0)
            self.assertLessEqual(max(avg1, avg2), 2.0, 'Těžká think average > 2 ms (%s)' % mode)


if __name__ == '__main__':
    unittest.main()
