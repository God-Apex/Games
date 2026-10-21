"""Fast regression run: unittest discovery over dev/tests/test_*.py on the server under test. Target: <= 3 minutes.

usage: python dev/tests/run_fast.py [-v] [-k SUBSTRING] [--slowest N]
  -v           one line per test        -k  only tests whose id contains SUBSTRING        --slowest  list the N slowest
The server is <game>/server.py unless HMK_SERVER says otherwise (see _paths.py). Python 3.8+ is enough to run it.

What runs (all short forms; the long gates are separate commands, run them before a milestone gate):
  test_features   the 0.5 feature tests (compat05)           test_golden    golden hashes vs the frozen 0.5 server (short)
  test_py38       Python 3.8 + stdlib-only guard             test_hashorder set-order guard + PYTHONHASHSEED check
  test_harness    bot harness smoke / reset                  test_tools     fuzz, lobby fuzz, replay and perf smoke
Long gates:
  python dev/tests/golden/golden.py                  full golden: seeds 1-10 x {kral, strateg}, 600 s -> 20/20 identical
  python dev/tests/fuzz.py                           4 seeds x 2 modes x 400 s of random actions + lobby fuzz, 0 exceptions
  python dev/tests/perf.py --compare [--b7]          tick average vs the frozen 0.5 server (within +-10 %)
"""
import os
import sys
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

BUDGET_S = 180


class TimedResult(unittest.TextTestResult):
    def startTest(self, test):
        self._t0 = time.time()
        super().startTest(test)

    def stopTest(self, test):
        self.times = getattr(self, 'times', [])
        self.times.append((time.time() - self._t0, test.id()))
        super().stopTest(test)


def collect(substring=None):
    suite = unittest.TestLoader().discover(HERE, pattern='test_*.py', top_level_dir=HERE)

    def flat(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                yield from flat(t)
            else:
                yield t
    tests = [t for t in flat(suite) if not substring or substring in t.id()]
    return unittest.TestSuite(tests), len(tests)


def main(argv):
    verbose = '-v' in argv
    sub = argv[argv.index('-k') + 1] if '-k' in argv else None
    slowest = int(argv[argv.index('--slowest') + 1]) if '--slowest' in argv else 5
    print('server under test: %s   python %s' % (_paths.server_path(), sys.version.split()[0]))
    suite, n = collect(sub)
    t0 = time.time()
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1, resultclass=TimedResult, buffer=True)
    res = runner.run(suite)
    total = time.time() - t0
    print('\n%d tests in %.1f s (budget %d s)%s' % (res.testsRun, total, BUDGET_S, '' if total <= BUDGET_S else '  ** OVER BUDGET **'))
    for dt, tid in sorted(getattr(res, 'times', []), reverse=True)[:slowest]:
        print('  %6.1f s  %s' % (dt, tid))
    skipped = len(res.skipped)
    if skipped:
        print('%d skipped: %s' % (skipped, '; '.join('%s (%s)' % (t.id().split('.')[-1], r) for t, r in res.skipped)))
    ok = res.wasSuccessful()
    print('RESULT: ' + ('GREEN' if ok else 'RED'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
