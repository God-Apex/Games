"""Smoke tests of the dev tools themselves: fuzz.py (game fuzz + lobby fuzz), replay.py and perf.py run on the server
under test and finish without an exception. The long runs are done by hand / by the M1 gate (see run_fast.py doc)."""
import asyncio
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'bal'))
import _paths  # noqa: E402
import fuzz  # noqa: E402


class TestTools(unittest.TestCase):
    def test_fuzz_games_have_no_exception(self):
        for mode in fuzz.S.MODES:
            res = fuzz.fuzz_game(mode, 101, 90, max_actions=1500)
            self.assertGreaterEqual(res['acts'], 1500)
            self.assertLess(res['snap_max_bytes'], 20000)

    def test_lobby_fuzz_has_no_exception(self):
        with contextlib.redirect_stdout(io.StringIO()):          # the lobby prints its console log
            sent, t = asyncio.run(fuzz.lobby_fuzz(0))
        self.assertGreater(sent, 1000)

    def test_replay_writes_snapshots(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'r.js')
            p = subprocess.run([sys.executable, os.path.join(HERE, 'replay.py'), out], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(p.returncode, 0, p.stdout.decode('utf-8', 'replace')[-1500:])
            with open(out, encoding='utf-8') as f:
                txt = f.read()
            self.assertTrue(txt.startswith('window.REPLAY = '))
            data = json.loads(txt[len('window.REPLAY = '):].rstrip(';\n'))
            self.assertGreater(len(data['s0']), 500)
            self.assertIsNotNone(data['end'])

    def test_perf_measure(self):
        import perf
        rows = perf.measure(['mix'], 1)
        self.assertEqual(len(rows), 2)
        tot = perf.total(rows)
        self.assertGreater(tot['tick_avg'], 0)
        self.assertEqual(perf.b7_verdict(tot), [], 'B7 numbers violated on a plain mix game')


if __name__ == '__main__':
    unittest.main()
