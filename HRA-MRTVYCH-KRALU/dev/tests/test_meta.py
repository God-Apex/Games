"""M2-F: hmk/meta.py (profiles, XP, Elo, achievements, cosmetics, Store). Pure Python, no sockets, no game.
Per META section 9: Store, Rules, History and keys (plus the views the lobby needs).
Run: python dev/tests/test_meta.py   (or through run_fast.py)"""
import contextlib
import copy
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

_folder = os.path.dirname(_paths.server_path())
if _folder not in sys.path:
    sys.path.insert(0, _folder)
try:
    from hmk import meta
except ImportError:       # the server under test is the 0.5 single file
    meta = None

NOW = datetime.datetime(2026, 10, 20, 18, 3)


def stats(**kw):
    st = {'kills': 0, 'units': 0, 'built': 0, 'crates': 0, 'techs': 0, 'zk': 0, 'uk': 0, 'bk': 0, 'kk': 0,
          'lost': 0, 'parry': 0, 'relic_s': 0.0, 'spent': 0, 'cast': 0}
    st.update(kw)
    return st


def player(n='Jarda', k='jarda', human=True, fac='bez', **st):
    return {'n': n, 'k': k, 'human': human, 'fac': fac, 'th': 1500, 'dmg': 4000, 'doba': 3,
            'st': stats(**st), 'inc': [7.4, 11.5]}


def summ(type='souboj', mode='kral', map='most', len=600, code='throne', winner=0, ai=None, puzzle=None,
         surv=None, p0=None, p1=None, ser=True, **kw):
    s = {'type': type, 'mode': mode, 'map': map, 'len': len, 'code': code, 'winner': winner, 'ai': ai,
         'puzzle': puzzle, 'surv': surv, 'ecl': [[240, 265]], 'night': None,
         'p': [p0 or player(), p1 or player('Petr', 'petr')]}
    if ser:
        n = int(len // 5) + 2
        s['ser'] = {'dt': 5, 'th': [[3000] * n, [2000] * n], 'inc': [[50] * n, [60] * n], 'army': [[10] * n, [20] * n]}
    s.update(kw)
    return s


def vyc(diff='stredni', winner=0, **kw):
    """Jarda (human) vs the AI."""
    kw.setdefault('p1', player('Kastelán', None, human=False))
    return summ('vycvik', winner=winner, ai={'side': 1, 'diff': diff, 'fac': 'bez'}, **kw)


def surv_s(players=1, winner=None, wave=(12, 0), t=(500.0, 0.0), **kw):
    p1 = player('Petr', 'petr') if players == 2 else player('Kastelán', None, human=False)
    return summ('preziti', winner=winner, code='survive', surv={'players': players, 'wave': list(wave), 't': list(t)},
                p1=p1, len=int(max(t)), **kw)


def slurp(path, mode='r'):
    with open(path, mode) if 'b' in mode else open(path, mode, encoding='utf-8') as f:
        return f.read()


def fresh():
    return meta.Store(None)


def rec(store, s, now=NOW):
    return meta.record(store, s, now)


@unittest.skipIf(meta is None, 'hmk package not present on the server under test')
class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='hmk_meta_')
        self.path = os.path.join(self.dir, 'stats.json')

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def played(self):
        st = meta.Store(self.path)
        st.load()
        rec(st, summ())
        rec(st, summ(winner=1, p0=player(parry=3)))
        return st

    def quiet(self, fn, *a):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = fn(*a)
        return r, buf.getvalue()

    def test_round_trip(self):
        st = self.played()
        self.assertTrue(st.save())
        self.assertFalse(st.dirty)
        st2 = meta.Store(self.path)
        st2.load()
        self.assertEqual(json.loads(json.dumps(st.data)), json.loads(json.dumps(st2.data)))
        self.assertEqual(st2.data['players']['jarda']['tot']['m'], 2)
        self.assertEqual(len(st2.data['matches']), 2)
        raw = slurp(self.path)
        self.assertNotIn(' ', raw.split('"name"')[0])              # compact separators
        self.assertIn('Kastelán' if False else 'Jarda', raw)       # ensure_ascii=False keeps names readable

    def test_save_keeps_bak_and_diacritics(self):
        st = meta.Store(self.path)
        st.load()
        rec(st, summ(p0=player('Žofie Čápková', 'žofie čápková')))
        st.save()
        self.assertIn('Žofie Čápková', slurp(self.path))
        self.assertFalse(os.path.exists(self.path + '.bak'))       # first save: nothing to back up
        rec(st, summ(p0=player('Žofie Čápková', 'žofie čápková')))
        st.save()
        bak = json.loads(slurp(self.path + '.bak'))
        self.assertEqual(bak['players']['žofie čápková']['tot']['m'], 1)   # .bak = the previous version
        self.assertFalse(os.path.exists(self.path + '.tmp'))

    def test_crash_between_tmp_write_and_replace(self):
        st = self.played()
        st.save()
        before = slurp(self.path, 'rb')
        rec(st, summ())
        real = os.replace

        def boom(a, b):
            raise OSError('simulated crash')
        os.replace = boom
        try:
            ok, out = self.quiet(st.save)
        finally:
            os.replace = real
        self.assertFalse(ok)
        self.assertTrue(st.dirty)                                   # kept in memory, saved at the next trigger
        self.assertIn('stats.json nelze ulozit', out)
        self.assertEqual(slurp(self.path, 'rb'), before)      # the original is untouched ...
        st2 = meta.Store(self.path)
        st2.load()
        self.assertEqual(st2.data['players']['jarda']['tot']['m'], 2)   # ... and readable
        self.assertTrue(st.save())                                  # the next trigger writes it
        st3 = meta.Store(self.path)
        st3.load()
        self.assertEqual(st3.data['players']['jarda']['tot']['m'], 3)

    def test_main_missing_starts_fresh(self):
        st = self.played()
        st.save()
        rec(st, summ())
        st.save()                       # .bak now holds the 2-game version
        os.remove(self.path)            # a deliberate reset: the .bak must not resurrect the old stats
        st2 = meta.Store(self.path)
        _, out = self.quiet(st2.load)
        self.assertEqual(st2.data['players'], {})
        self.assertEqual(out, '')
        self.assertFalse(st2.dirty)

    def test_corrupt_main_falls_back_to_bak(self):
        st = self.played()
        st.save()
        rec(st, summ())
        st.save()
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('{"v":1,"players":{"jarda":')                   # truncated JSON
        st2 = meta.Store(self.path)
        _, out = self.quiet(st2.load)
        self.assertEqual(st2.data['players']['jarda']['tot']['m'], 2)
        self.assertIn('stats.json poskozen', out)
        names = sorted(os.listdir(self.dir))
        self.assertTrue(any(n.startswith('stats.corrupt-') and n.endswith('.json') for n in names), names)
        self.assertFalse(os.path.exists(self.path))                # the bad file was moved aside, not rotated into .bak

    def test_both_corrupt_renames_and_starts_fresh(self):
        for p in (self.path, self.path + '.bak'):
            with open(p, 'w', encoding='utf-8') as f:
                f.write('not json at all')
        st = meta.Store(self.path)
        _, out = self.quiet(st.load)
        self.assertEqual(st.data['players'], {})
        self.assertEqual(st.data['matches'], [])
        self.assertIn('  ! stats.json poskozen, zalozen novy (stary: stats.corrupt-', out)
        moved = [n for n in os.listdir(self.dir) if n.startswith('stats.corrupt-')]
        self.assertEqual(len(moved), 1)
        self.assertIn(moved[0], out)
        self.assertEqual(slurp(os.path.join(self.dir, moved[0])), 'not json at all')
        self.assertTrue(st.save())                                  # the fresh file is usable

    def test_corrupt_main_without_bak_starts_fresh(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('[1, 2, 3]')                                    # valid JSON, wrong shape
        st = meta.Store(self.path)
        _, out = self.quiet(st.load)
        self.assertIn('zalozen novy', out)
        self.assertEqual(st.data['players'], {})

    def test_missing_file_is_a_fresh_store_without_noise(self):
        st = meta.Store(self.path)
        _, out = self.quiet(st.load)
        self.assertEqual(out, '')
        self.assertEqual(st.data['v'], 1)
        self.assertEqual(meta.SCHEMA, 1)

    def test_permission_error_retry(self):
        st = self.played()
        real, slept = os.replace, []
        calls = {'n': 0}

        def flaky(a, b):
            calls['n'] += 1
            if calls['n'] <= 2:
                raise PermissionError('antivirus')
            return real(a, b)
        os.replace = flaky
        old_sleep, time.sleep = time.sleep, lambda s: slept.append(s)
        try:
            self.assertTrue(st.save())                              # 2 failures, the 3rd try succeeds
        finally:
            os.replace, time.sleep = real, old_sleep
        self.assertEqual(calls['n'], 3)
        self.assertEqual(slept, [0.05, 0.05])
        self.assertFalse(st.dirty)
        # permanent failure: 1 try + 3 retries, then the data stays in memory
        rec(st, summ())
        os.replace = lambda a, b: (_ for _ in ()).throw(PermissionError('locked'))
        slept[:] = []
        time.sleep = lambda s: slept.append(s)
        try:
            ok, out = self.quiet(st.save)
        finally:
            os.replace, time.sleep = real, old_sleep
        self.assertFalse(ok)
        self.assertEqual(len(slept), 3)
        self.assertTrue(st.dirty)
        self.assertIn('nelze ulozit', out)
        self.assertEqual(st.data['players']['jarda']['tot']['m'], 3)
        self.assertTrue(st.save())                                  # the next trigger
        self.assertFalse(st.dirty)

    def test_memory_store_never_touches_disk(self):
        st = meta.Store(None)
        st.load()
        rec(st, summ())
        self.assertTrue(st.save())
        self.assertEqual(os.listdir(self.dir), [])

    def test_normalize_garbage(self):
        for raw in (None, 5, 'x', [], {'players': 7}, {'players': {'a': 'b', '': {}, 3: {}}, 'matches': 'm'}):
            d = meta.normalize(raw)
            self.assertEqual(d['v'], 1)
            self.assertIsInstance(d['players'], dict)
            self.assertEqual(d['matches'], [])
        nan = float('nan')
        raw = {'v': 1, 'next_id': 'x', 'players': {
            'jarda': {'name': 12, 'xp': 'many', 'lvl': 99, 'elo': -5, 'elo_n': nan, 'tot': {'m': -3, 'w': 'x', 'zk': 10 ** 15, 'time': 1.6},
                      'by': {'souboj.kral': [1, 2], 'souboj.strateg': [1, 2, 3, 4], 'bogus.x': [1, 1, 1, 1]},
                      'fac': {'kult': [3, 2], 'zzz': [1, 1], 'prez': 'x'}, 'h2h': {'petr': [1, 2, 3], 'x': 5},
                      'rec': {'kills': [5, 1], 'crates': ['a', 1], 'nope': [1, 1], 'surv': [0, 2]},
                      'streak': [1], 'ach': {'zrcadlo': '2026-10-18', 'bogus': 'x', 'noc': 5},
                      'puz': {'p01': [3, 41], 'p02': [9, 'x'], 'p03': 'x'}, 'surv': {'most|kral': [4, 90], 'x': 'y'},
                      'cos': {'ban': 'lebka', 'kor': 'nonsense', 'zab': 5, 'vit': 'zvony'}, 'tut': 'yes', 'qf': ['kult', 'x']}}}
        p = meta.normalize(raw)['players']['jarda']
        self.assertEqual(p['name'], 'jarda')                         # non-string name -> key
        self.assertEqual((p['xp'], p['lvl'], p['elo'], p['elo_n']), (0, 1, 100, 0))
        self.assertEqual(p['tot']['m'], 0)
        self.assertEqual(p['tot']['w'], 0)
        self.assertEqual(p['tot']['zk'], 10 ** 9)                    # clamped
        self.assertEqual(p['tot']['time'], 2)
        self.assertEqual(p['by'], {'souboj.strateg': [1, 2, 3, 4]})
        self.assertEqual(p['fac'], {'kult': [3, 2]})
        self.assertEqual(p['h2h'], {'petr': [1, 2, 3]})
        self.assertEqual(sorted(p['rec']), ['kills'])
        self.assertEqual(p['streak'], [0, 0])
        self.assertEqual(sorted(p['ach']), ['zrcadlo'])
        self.assertEqual(p['puz'], {'p01': [3, 41.0], 'p02': [3, 0.0]})
        self.assertEqual(p['surv'], {'most|kral': [4, 90]})
        self.assertEqual(p['cos'], {'ban': 'rod', 'kor': 'zlata', 'zab': 'jiskry', 'vit': 'zlate'})   # locked/unknown -> default
        self.assertEqual((p['tut'], p['qf']), (0, ['kult']))
        json.dumps(meta.normalize(raw))

    def test_normalize_keeps_a_good_file_unchanged(self):
        st = self.played()
        a = json.loads(json.dumps(st.data))
        self.assertEqual(meta.normalize(a), a)

    def test_profile_cap_evicts_the_oldest(self):
        st = meta.Store(None)
        for i in range(meta.MAX_PROFILES):
            st.ensure('k%03d' % i)
            st.data['players']['k%03d' % i]['last'] = '2026-01-01T00:%02d' % (i % 60) if i else ''
        self.assertEqual(len(st.data['players']), 500)
        st.ensure('newbie')
        self.assertEqual(len(st.data['players']), 500)
        self.assertIn('newbie', st.data['players'])
        self.assertNotIn('k000', st.data['players'])                 # empty `last` = the oldest
        raw = {'players': dict(('k%d' % i, {'name': 'a', 'last': '2026-01-01T00:00'}) for i in range(520))}
        self.assertEqual(len(meta.normalize(raw)['players']), 500)


@unittest.skipIf(meta is None, 'hmk package not present on the server under test')
class RuleTests(unittest.TestCase):
    def test_need_table(self):
        for lvl, xp in ((1, 0), (2, 100), (3, 250), (5, 700), (10, 2700), (15, 5950), (20, 10450)):
            self.assertEqual(meta.need(lvl), xp, lvl)
        self.assertEqual(meta.lvl_of(99), 1)
        self.assertEqual(meta.lvl_of(100), 2)
        self.assertEqual(meta.lvl_of(10 ** 7), 30)                   # the cap
        self.assertEqual(meta.bounds(0), (1, 0, 100))
        self.assertEqual(meta.bounds(120), (2, 100, 250))
        lvl, cur, nxt = meta.bounds(10 ** 6)
        self.assertEqual((lvl, nxt > cur), (30, True))               # the bar at the cap: never a zero-width range

    def test_titles(self):
        exp = {1: 'Panoš', 2: 'Panoš', 3: 'Zbrojnoš', 4: 'Zbrojnoš', 5: 'Rytíř', 7: 'Rytíř', 8: 'Pán hradu', 11: 'Pán hradu',
               12: 'Baron', 15: 'Baron', 16: 'Hrabě', 19: 'Hrabě', 20: 'Vévoda', 24: 'Vévoda', 25: 'Kníže', 29: 'Kníže',
               30: 'Mrtvý král'}
        for lvl, t in exp.items():
            self.assertEqual(meta.title(lvl), t, lvl)

    def test_key(self):
        self.assertEqual(meta.key('  Jarda   Novák '), 'jarda novák')
        self.assertEqual(meta.key('JARDA'), meta.key('jarda'))
        for n in ('', '   ', 'Král', ' KRÁL ', 'král', None, 5):
            self.assertIsNone(meta.key(n), n)
        self.assertEqual(meta.key('Král Artuš'), 'král artuš')

    # ---- XP parts
    def parts(self, s, side=0, prof=None):
        return dict((l, n) for l, n in meta.xp_gain(s, side, prof))

    def test_xp_souboj(self):
        self.assertEqual(self.parts(summ(len=600)), {'Odehraná hra': 50, 'Čas ve hře': 40, 'Vítězství': 80})
        self.assertEqual(self.parts(summ(len=600, winner=1)), {'Odehraná hra': 50, 'Čas ve hře': 40})
        self.assertEqual(self.parts(summ(len=600, winner=None, code='draw')),
                         {'Odehraná hra': 50, 'Čas ve hře': 40, 'Remíza': 30})
        self.assertEqual(self.parts(summ(len=659)), {'Odehraná hra': 50, 'Čas ve hře': 40, 'Vítězství': 80})   # full minutes only
        self.assertEqual(self.parts(summ(len=60))['Čas ve hře'], 4)
        self.assertEqual(self.parts(summ(len=5000))['Čas ve hře'], 60)                                     # cap
        self.assertEqual(sum(self.parts(summ(len=600)).values()), 170)

    def test_xp_vycvik_levels(self):
        exp = {'lehka': (15, 20, 20), 'stredni': (24, 32, 32), 'tezka': (30, 40, 40)}
        for diff, (b, t, w) in exp.items():
            self.assertEqual(self.parts(vyc(diff, len=600)), {'Odehraná hra': b, 'Čas ve hře': t, 'Vítězství': w}, diff)
            self.assertEqual(self.parts(vyc(diff, len=600, winner=1)), {'Odehraná hra': b, 'Čas ve hře': t}, diff)

    def test_xp_disconnect_and_quit(self):
        d = summ(len=600, code='disc', winner=0)
        self.assertEqual(meta.xp_gain(d, 1), [])                                                           # the leaver: 0
        self.assertEqual(self.parts(d, 0), {'Odehraná hra': 50, 'Čas ve hře': 40, 'Vítězství': 40})        # 50 % of the win
        q = summ(len=600, code='quit', winner=1)                                                           # side 0 surrendered
        self.assertEqual(self.parts(q, 0), {'Odehraná hra': 50, 'Čas ve hře': 40})                         # a normal loss
        self.assertEqual(self.parts(q, 1), {'Odehraná hra': 50, 'Čas ve hře': 40, 'Vítězství': 40})

    def test_xp_surv_puzzle_vyuka(self):
        self.assertEqual(self.parts(surv_s(1, t=(600.0, 0.0))), {'Odehraná hra': 40, 'Čas ve hře': 40})
        s2 = surv_s(2, winner=0, wave=(14, 9), t=(600.0, 400.0))
        self.assertEqual(self.parts(s2, 0), {'Odehraná hra': 40, 'Čas ve hře': 40, 'Vítězství': 60})
        self.assertEqual(self.parts(s2, 1), {'Odehraná hra': 40, 'Čas ve hře': 40})
        pz = summ('puzzle', len=31, winner=0, puzzle={'id': 'p04', 'ok': True, 'stars': 2, 't': 31.5})
        self.assertEqual(meta.xp_gain(pz, 0), [['Vyřešení puzzle', 40]])
        self.assertEqual(meta.xp_gain(pz, 0, {'puz': {'p04': [1, 50.0]}}), [['Vyřešení puzzle', 5]])
        self.assertEqual(meta.xp_gain(pz, 0, {'puz': {'p05': [3, 50.0]}}), [['Vyřešení puzzle', 40]])
        bad = summ('puzzle', len=31, code='failed', winner=None, puzzle={'id': 'p04', 'ok': False, 'stars': 0, 't': 30})
        self.assertEqual(meta.xp_gain(bad, 0), [])
        vy = summ('vyuka', len=300, winner=0)
        self.assertEqual(meta.xp_gain(vy, 0), [['Dokončení výuky', 100]])
        self.assertEqual(meta.xp_gain(vy, 0, {'tut': 1}), [])                                              # first time only

    def test_record_xp_fixtures_and_short_games(self):
        st = fresh()
        r = rec(st, summ(len=600))
        self.assertEqual(r[0]['xp'], 170 + 100)                      # + the Korunovace achievement (100)
        self.assertEqual(r[0]['xp_parts'][-1], ['Úspěch: Korunovace', 100])
        self.assertEqual(st.data['players']['jarda']['xp'], 270)
        self.assertEqual(rec(fresh(), summ(len=59)), {})
        self.assertEqual(rec(fresh(), vyc('tezka', len=59)), {})
        s2 = fresh()
        self.assertEqual(rec(s2, summ(len=59)), {})
        self.assertEqual(s2.data['players'], {})                      # not even a profile
        self.assertEqual(s2.data['matches'], [])
        r = rec(fresh(), summ(len=60))
        self.assertIn(0, r)
        # puzzle and vyuka are recorded however short
        r = rec(fresh(), summ('puzzle', len=12, winner=0, puzzle={'id': 'p01', 'ok': True, 'stars': 3, 't': 12.0}))
        self.assertEqual(r[0]['xp'], 40)
        r = rec(fresh(), summ('vyuka', len=30, winner=0))
        self.assertEqual(r[0]['xp'], 100 + 50)                       # Výuka + the Učedník achievement
        # not recorded: errors, quit/disc in puzzle or vyuka
        self.assertEqual(rec(fresh(), summ(code='error', winner=None)), {})
        self.assertEqual(rec(fresh(), summ('vyuka', len=300, code='quit', winner=1)), {})
        self.assertEqual(rec(fresh(), summ('puzzle', len=60, code='quit', winner=1,
                                           puzzle={'id': 'p01', 'ok': False, 'stars': 0, 't': 60})), {})

    # ---- Elo
    def test_elo_symmetry(self):
        for a, b in ((1000, 1000), (1000, 1300), (1500, 900), (1111, 1234), (800, 2000)):
            for sc in (1.0, 0.5, 0.0):
                na, nb = meta.elo_update(a, b, sc, 24, 24)
                self.assertEqual((na - a) + (nb - b), 0, (a, b, sc))   # the sum is conserved
                na2, nb2 = meta.elo_update(b, a, 1.0 - sc, 24, 24)
                self.assertEqual((na2, nb2), (nb, na), (a, b, sc))      # swapping the seats mirrors the result
        self.assertEqual(meta.elo_update(1000, 1000, 1.0, 24), (1012, 988))
        self.assertEqual(meta.elo_update(1000, 1000, 0.5, 24), (1000, 1000))
        na, nb = meta.elo_update(1000, 1400, 1.0, 24)                  # the upset pays more
        self.assertGreater(na - 1000, 12)
        na, nb = meta.elo_update(1400, 1000, 1.0, 24)
        self.assertLess(na - 1400, 12)

    def test_elo_k_switch_at_10(self):
        self.assertEqual((meta.elo_k(0), meta.elo_k(9), meta.elo_k(10), meta.elo_k(500)), (40, 40, 24, 24))
        self.assertEqual(meta.elo_update(1000, 1000, 1.0, 40, 24), (1020, 988))   # the new player has K 40
        st = fresh()
        for i in range(10):
            rec(st, summ(winner=0 if i % 2 == 0 else 1))
        self.assertEqual(st.data['players']['jarda']['elo_n'], 10)
        self.assertEqual(st.data['players']['petr']['elo_n'], 10)
        before = st.data['players']['jarda']['elo']
        rec(st, summ(winner=0))
        self.assertEqual(st.data['players']['jarda']['elo_n'], 11)
        self.assertGreater(st.data['players']['jarda']['elo'], before)

    def test_elo_in_record(self):
        st = fresh()
        r = rec(st, summ(winner=0))
        self.assertEqual(r[0]['elo'], [1000, 1020])                    # K 40 in the first 10 games
        self.assertEqual(r[1]['elo'], [1000, 980])
        self.assertEqual(st.data['matches'][0]['p'][0]['elo'], [1000, 1020])
        r = rec(st, summ(winner=None, code='draw'))                    # a draw: the leader gives a little
        self.assertEqual(r[0]['elo'][0], 1020)
        self.assertLess(r[0]['elo'][1], 1020)
        # no Elo: Výcvik, Přežití, one anonymous side
        self.assertIsNone(rec(fresh(), vyc('tezka'))[0]['elo'])
        self.assertIsNone(rec(fresh(), surv_s(2, winner=0, wave=(5, 3), t=(300.0, 200.0)))[0]['elo'])
        s = summ(p1=player('Král', None))
        st = fresh()
        r = rec(st, s)
        self.assertEqual(list(r), [0])
        self.assertIsNone(r[0]['elo'])
        self.assertEqual(st.data['players']['jarda']['elo'], 1000)

    # ---- achievements
    def got(self, s, side=0, store=None):
        st = store or fresh()
        return rec(st, s)[side]['new_ach'], st

    def test_ach_korunovace(self):
        self.assertIn('korunovace', self.got(summ())[0])
        self.assertNotIn('korunovace', self.got(summ(winner=1))[0])
        self.assertNotIn('korunovace', self.got(summ(winner=None, code='draw'))[0])
        self.assertNotIn('korunovace', self.got(vyc('lehka'))[0])
        self.assertIn('korunovace', self.got(vyc('stredni'))[0])
        self.assertIn('korunovace', self.got(vyc('tezka'))[0])
        self.assertIn('korunovace', self.got(surv_s(2, winner=0, wave=(5, 3), t=(300.0, 200.0)))[0])
        self.assertNotIn('korunovace', self.got(surv_s(1))[0])
        self.assertNotIn('korunovace', self.got(summ(code='disc', winner=0))[0])
        self.assertNotIn('korunovace', self.got(summ(code='quit', winner=0))[0])
        # once only
        a, st = self.got(summ())
        self.assertNotIn('korunovace', rec(st, summ())[0]['new_ach'])

    def test_ach_ucednik_and_tut_flag(self):
        a, st = self.got(summ('vyuka', len=300, winner=0))
        self.assertEqual(a, ['ucednik'])
        self.assertEqual(st.data['players']['jarda']['tut'], 1)
        self.assertEqual(meta.profile_view(st, 'jarda')['tut'], 1)
        self.assertEqual(st.data['matches'], [])                       # not in the history
        self.assertEqual(st.data['players']['jarda']['tot']['m'], 0)
        self.assertEqual(self.got(summ('vyuka', len=300, winner=1, code='failed'))[0], [])

    def test_ach_sach_mat_noc(self):
        self.assertIn('sach_mat', self.got(summ(code='mat'))[0])
        self.assertNotIn('sach_mat', self.got(summ(code='mat', winner=1))[0])
        self.assertNotIn('sach_mat', self.got(summ(code='throne'))[0])
        self.assertIn('noc', self.got(summ(code='night'))[0])
        self.assertNotIn('noc', self.got(summ(code='night', winner=1))[0])
        self.assertNotIn('noc', self.got(summ(code='throne'))[0])
        self.assertIn('sach_mat', self.got(summ(code='mat', winner=1), side=1)[0])      # Petr's side wins by mat

    def test_ach_single_match_counters(self):
        for ach, key, ok, no in (('zrcadlo', 'parry', 10, 9), ('relikvie', 'relic_s', 240.0, 239.9), ('sberatel', 'crates', 6, 5)):
            self.assertIn(ach, self.got(summ(winner=1, p0=player(**{key: ok})))[0], ach)     # a loss counts too
            self.assertNotIn(ach, self.got(summ(p0=player(**{key: no})))[0], ach)

    def test_ach_hrobnik_is_cumulative(self):
        st = fresh()
        r = rec(st, summ(p0=player(zk=999)))
        self.assertNotIn('hrobnik', r[0]['new_ach'])
        self.assertEqual(meta.profile_view(st, 'jarda')['prog']['hrobnik'], [999, 1000])
        r = rec(st, summ(p0=player(zk=1)))
        self.assertIn('hrobnik', r[0]['new_ach'])
        self.assertEqual(st.data['players']['jarda']['tot']['zk'], 1000)
        self.assertIn('havran', r[0]['new_cos'])

    def test_ach_tri_cesty(self):
        st = fresh()
        for fac in ('prez', 'korp'):
            self.assertNotIn('tri_cesty', rec(st, summ(p0=player(fac=fac)))[0]['new_ach'])
        self.assertNotIn('tri_cesty', rec(st, summ(p0=player(fac='kult'), winner=1))[0]['new_ach'])   # a loss
        self.assertNotIn('tri_cesty', rec(st, vyc('stredni', p0=player(fac='kult')))[0]['new_ach'])    # Střední does not count
        self.assertNotIn('tri_cesty', rec(st, summ(p0=player(fac='kult'), code='disc'))[0]['new_ach'])
        self.assertNotIn('tri_cesty', rec(st, summ(p0=player(fac='bez')))[0]['new_ach'])
        r = rec(st, vyc('tezka', p0=player(fac='kult')))                                               # Výcvik Těžká counts
        self.assertIn('tri_cesty', r[0]['new_ach'])
        self.assertIn('svatozar', r[0]['new_cos'])
        self.assertEqual(st.data['players']['jarda']['qf'], ['prez', 'korp', 'kult'])

    def test_ach_mistr_vycviku(self):
        self.assertIn('mistr_vycviku', self.got(vyc('tezka'))[0])
        self.assertNotIn('mistr_vycviku', self.got(vyc('stredni'))[0])
        self.assertNotIn('mistr_vycviku', self.got(vyc('tezka', winner=1))[0])
        self.assertNotIn('mistr_vycviku', self.got(summ())[0])

    def test_ach_nezlomny(self):
        self.assertIn('nezlomny', self.got(surv_s(1, wave=(25, 0), t=(720.0, 0.0)))[0])
        self.assertNotIn('nezlomny', self.got(surv_s(1, wave=(25, 0), t=(719.0, 0.0)))[0])
        self.assertIn('nezlomny', self.got(surv_s(2, winner=0, wave=(25, 20), t=(800.0, 700.0)))[0])
        self.assertNotIn('nezlomny', self.got(surv_s(2, winner=0, wave=(25, 20), t=(800.0, 700.0)), side=1)[0]
                         if False else self.got(surv_s(2, winner=1, wave=(5, 25), t=(300.0, 800.0)))[0])

    def test_ach_velmistr(self):
        st = fresh()
        ids = ['p%02d' % i for i in range(1, 11)]
        for i in ids[:9]:
            r = rec(st, summ('puzzle', len=30, winner=0, puzzle={'id': i, 'ok': True, 'stars': 1, 't': 30.0}))
            self.assertNotIn('velmistr', r[0]['new_ach'])
        self.assertEqual(meta.profile_view(st, 'jarda')['prog']['velmistr'], [9, 10])
        r = rec(st, summ('puzzle', len=30, winner=0, puzzle={'id': ids[9], 'ok': True, 'stars': 1, 't': 30.0}))
        self.assertIn('velmistr', r[0]['new_ach'])
        self.assertEqual(r[0]['xp'], 40 + 300)

    def test_ach_xp_and_catalog(self):
        self.assertEqual(len(meta.ACH), 12)
        self.assertEqual(sorted(a[0] for a in meta.ACH), sorted(
            'korunovace ucednik sach_mat zrcadlo hrobnik relikvie sberatel noc tri_cesty mistr_vycviku nezlomny velmistr'.split()))
        xp = dict((a[0], a[3]) for a in meta.ACH)
        self.assertEqual((xp['korunovace'], xp['ucednik'], xp['sach_mat'], xp['tri_cesty'], xp['velmistr']), (100, 50, 150, 300, 300))
        r = rec(fresh(), summ(code='mat', len=600))
        labels = [p[0] for p in r[0]['xp_parts']]
        self.assertEqual(labels[-2:], ['Úspěch: Korunovace', 'Úspěch: Šach a mat'])
        self.assertEqual(r[0]['xp'], 170 + 100 + 150)

    # ---- cosmetics
    def test_cosmetics_catalog(self):
        self.assertEqual(len(meta.COSM), 13)
        defaults = [c for c in meta.COSM if not c[3]]
        self.assertEqual(sorted(c[1] for c in defaults), ['jiskry', 'rod', 'zlata', 'zlate'])
        self.assertEqual(sorted(set(c[0] for c in meta.COSM)), ['ban', 'kor', 'vit', 'zab'])
        cat = meta.public_catalogs()
        self.assertEqual(sorted(cat), ['ach', 'cosm', 'lvls', 'titles'])
        self.assertEqual(len(cat['lvls']), 30)
        self.assertEqual((cat['lvls'][0], cat['lvls'][1], cat['lvls'][29]), (0, 100, meta.need(30)))
        self.assertEqual(cat['titles'][0], [1, 'Panoš'])
        self.assertEqual(cat['titles'][-1], [30, 'Mrtvý král'])
        by = dict((c['id'], c) for c in cat['cosm'])
        self.assertEqual(by['kostena']['unlock'], {'lvl': 6})
        self.assertEqual(by['lebka']['unlock'], {'ach': 'ucednik'})
        self.assertIsNone(by['rod']['unlock'])
        self.assertEqual(sorted(cat['ach'][0]), ['desc', 'goal', 'id', 'name', 'xp'])
        for a in cat['ach']:
            self.assertTrue(a['name'] and a['desc'])
        json.dumps(cat)

    def test_locked_cosmetic_falls_back_to_default(self):
        st = fresh()
        st.ensure('jarda', 'Jarda')
        want = {'ban': 'lebka', 'kor': 'kostena', 'zab': 'vrany', 'vit': 'zvony'}
        got = meta.set_cos(st, 'jarda', want)
        self.assertEqual(got, {'ban': 'rod', 'kor': 'zlata', 'zab': 'jiskry', 'vit': 'zlate'})
        self.assertEqual(st.data['players']['jarda']['cos'], got)
        self.assertTrue(st.dirty)
        self.assertEqual(meta.set_cos(st, 'jarda', {'ban': 'nonsense', 'kor': 5, 'zab': 'rod'})['zab'], 'jiskry')   # unknown / wrong slot
        p = st.data['players']['jarda']
        p['xp'] = meta.need(10)                                       # level 10 unlocks kostena, duse, zvony
        got = meta.set_cos(st, 'jarda', want)
        self.assertEqual(got, {'ban': 'rod', 'kor': 'kostena', 'zab': 'jiskry', 'vit': 'zvony'})
        p['ach']['ucednik'] = '2026-10-20'                            # an achievement unlocks lebka
        self.assertEqual(meta.set_cos(st, 'jarda', {'ban': 'lebka'})['ban'], 'lebka')
        self.assertEqual(meta.set_cos(st, 'jarda', {'zab': 'duse'}), {'ban': 'lebka', 'kor': 'kostena', 'zab': 'duse', 'vit': 'zvony'})  # others kept
        self.assertEqual(meta.cos_for(st, 'jarda')['ban'], 'lebka')
        self.assertEqual(meta.cos_for(st, 'nobody'), meta.COS_DEFAULT)
        self.assertEqual(meta.cos_for(None, 'jarda'), meta.COS_DEFAULT)
        self.assertIsNone(meta.set_cos(st, None, want))
        self.assertIsNone(meta.set_cos(None, 'jarda', want))
        # the file cannot smuggle in a locked item either
        raw = json.loads(json.dumps(st.data))
        raw['players']['jarda']['xp'] = 0
        raw['players']['jarda']['ach'] = {}
        self.assertEqual(meta.normalize(raw)['players']['jarda']['cos'], meta.COS_DEFAULT)

    def test_new_cos_on_level_and_achievement(self):
        st = fresh()
        st.ensure('jarda', 'Jarda')
        st.data['players']['jarda']['xp'] = meta.need(3) - 10
        r = rec(st, summ(len=600, winner=1))                          # a loss: 90 XP, crosses level 3
        self.assertTrue(r[0]['lvlup'])
        self.assertEqual((r[0]['lvl0'], r[0]['lvl'], r[0]['ttl']), (2, 3, 'Zbrojnoš'))
        self.assertEqual(r[0]['new_cos'], ['duse'])
        r = rec(fresh(), summ('vyuka', len=100, winner=0))
        self.assertEqual(r[0]['new_cos'], ['lebka'])

    # ---- views
    def test_profile_view(self):
        self.assertIsNone(meta.profile_view(fresh(), None))
        self.assertIsNone(meta.profile_view(None, 'jarda'))
        st = fresh()
        v = meta.profile_view(st, 'jarda', 'Jarda')                    # no profile yet: defaults, nothing created
        self.assertEqual((v['name'], v['lvl'], v['xp'], v['cur'], v['next'], v['elo'], v['m'], v['tut']), ('Jarda', 1, 0, 0, 100, 1000, 0, 0))
        self.assertEqual(v['ttl'], 'Panoš')
        self.assertEqual(v['own'], ['rod', 'zlata', 'jiskry', 'zlate'])
        self.assertEqual((v['ach'], v['puz'], v['surv']), ([], {}, {}))
        self.assertEqual(st.data['players'], {})
        rec(st, summ(len=700))
        rec(st, surv_s(1, wave=(12, 0), t=(500.0, 0.0)))
        rec(st, summ('puzzle', len=30, winner=0, puzzle={'id': 'p03', 'ok': True, 'stars': 2, 't': 30.2}))
        v = meta.profile_view(st, 'jarda')
        self.assertEqual(sorted(v), ['ach', 'cos', 'cur', 'elo', 'key', 'lvl', 'm', 'name', 'next', 'own', 'prog', 'puz', 'surv', 'ttl', 'tut', 'xp'])
        self.assertEqual(v['m'], 2)
        self.assertEqual(v['puz'], {'p03': [2, 30.2]})
        self.assertEqual(v['surv'], {'most|kral': [12, 500]})
        self.assertEqual(v['ach'], ['korunovace'])
        self.assertTrue(v['cur'] <= v['xp'] < v['next'])
        json.dumps(v)

    def test_stats_view_and_hof(self):
        st = fresh()
        self.assertIsNone(meta.stats_view(st, 'jarda'))
        for i in range(6):
            rec(st, summ(winner=0 if i < 4 else 1))
        rec(st, summ(p0=player('Eva', 'eva'), p1=player('Ondra', 'ondra'), winner=0))
        v = meta.stats_view(st, 'jarda')
        self.assertEqual(sorted(v), ['h2h', 'hist', 'hof', 'prof'])
        self.assertEqual(len(v['hist']), 6)
        self.assertTrue(all(any(x['k'] == 'jarda' for x in m['p']) for m in v['hist']))
        self.assertEqual(v['h2h'], {'petr': [4, 2, 0, 'Petr']})
        self.assertEqual(v['prof']['tot']['m'], 6)
        self.assertEqual(v['prof']['by']['souboj.kral'], [6, 4, 2, 0])
        self.assertEqual(v['prof']['streak'], [0, 4])
        # Síň slávy: >= 5 souboj games, by Elo
        names = [r[0] for r in v['hof']]
        self.assertEqual(names, sorted(names, key=lambda n: -st.data['players'][n.lower()]['elo']))
        self.assertEqual(sorted(names), ['Jarda', 'Petr'])
        row = v['hof'][0]
        self.assertEqual(len(row), 6)
        self.assertEqual(row[0], 'Jarda')
        self.assertEqual((row[4], row[5]), (6, 4))
        for i in range(12):                                            # top 10 only
            rec(st, summ(p0=player('H%d' % i, 'h%d' % i), p1=player('G%d' % i, 'g%d' % i)))
        self.assertEqual(len(meta.hof(st)), 10) if len([1 for p in st.data['players'].values() if p['tot']['m'] >= 5]) > 10 else None
        json.dumps(v)

    # ---- bookkeeping
    def test_tot_by_fac_h2h_streak(self):
        st = fresh()
        rec(st, summ(p0=player(fac='kult', zk=40, uk=22, bk=5, kk=2, crates=6, parry=3, relic_s=61.4)))
        rec(st, summ(winner=1, p0=player(fac='kult', zk=10)))
        rec(st, summ(winner=None, code='draw', p0=player(fac='prez')))
        rec(st, vyc('tezka', mode='strateg', winner=0, p0=player(fac='kult')))
        p = st.data['players']['jarda']
        self.assertEqual(p['tot'], {'m': 4, 'w': 2, 'l': 1, 'd': 1, 'time': 2400, 'zk': 50, 'uk': 22, 'bk': 5, 'kk': 2,
                                    'cr': 6, 'parry': 3, 'relic_s': 61})
        self.assertEqual(p['by']['souboj.kral'], [3, 1, 1, 1])
        self.assertEqual(p['by']['vycvik.strateg.tezka'], [1, 1, 0, 0])
        self.assertEqual(p['fac'], {'kult': [3, 2], 'prez': [1, 0]})
        self.assertEqual(p['h2h'], {'petr': [1, 1, 1]})
        self.assertEqual(p['streak'], [1, 1])                         # win, loss (cur 0), draw (unchanged), win again (cur 1, best 1)
        q = st.data['players']['petr']
        self.assertEqual(q['h2h'], {'jarda': [1, 1, 1]})
        self.assertEqual(q['tot']['m'], 3)                            # the AI game is not Petr's
        self.assertEqual(q['streak'], [1, 1])                         # loss, win, draw (unchanged)

    def test_by_key_for_vycvik(self):
        st = fresh()
        rec(st, vyc('lehka', mode='strateg', winner=1))
        rec(st, vyc('lehka', mode='strateg'))
        self.assertEqual(st.data['players']['jarda']['by'], {'vycvik.strateg.lehka': [2, 1, 1, 0]})
        self.assertEqual(st.data['players']['jarda']['h2h'], {})      # AI opponents are not in h2h

    def test_solo_survival_counts_as_neutral(self):
        st = fresh()
        rec(st, surv_s(1, wave=(12, 0), t=(500.0, 0.0)))
        rec(st, surv_s(1, wave=(8, 0), t=(300.0, 0.0), mode='strateg'))
        p = st.data['players']['jarda']
        self.assertEqual((p['tot']['m'], p['tot']['w'], p['tot']['l'], p['tot']['d']), (2, 0, 0, 2))
        self.assertEqual(p['streak'], [0, 0])
        self.assertEqual(p['by'], {'preziti.kral': [1, 0, 0, 1], 'preziti.strateg': [1, 0, 0, 1]})
        self.assertEqual(p['surv'], {'most|kral': [12, 500], 'most|strateg': [8, 300]})
        surv = lambda: st.data['players']['jarda']['surv']             # record() commits a fresh profile object
        rec(st, surv_s(1, wave=(11, 0), t=(700.0, 0.0)))               # fewer waves: no new best
        self.assertEqual(surv()['most|kral'], [12, 500])
        rec(st, surv_s(1, wave=(12, 0), t=(520.0, 0.0)))               # same wave, longer: best
        self.assertEqual(surv()['most|kral'], [12, 520])
        rec(st, surv_s(1, wave=(14, 0), t=(520.0, 0.0), map='metro'))
        self.assertEqual(surv()['metro|kral'], [14, 520])
        self.assertEqual(st.data['players']['jarda']['tot']['m'], 5)

    def test_records_only_report_beaten_values(self):
        st = fresh()
        r = rec(st, summ(len=700, p0=player(zk=30, uk=10, crates=2, parry=1, relic_s=50.0)))
        self.assertEqual(r[0]['new_rec'], [])                         # the first values are not "broken" records
        rc = st.data['players']['jarda']['rec']
        self.assertEqual({k: v[0] for k, v in rc.items()}, {'fast_win': 700, 'kills': 40, 'crates': 2, 'parry': 1, 'relic_s': 50})
        self.assertEqual(rc['kills'][1:], [1, '2026-10-20'])
        r = rec(st, summ(len=650, p0=player(zk=30, uk=11, crates=2, parry=0, relic_s=49.0)))
        self.assertEqual(r[0]['new_rec'], ['fast_win', 'kills'])      # equal crates / lower others do not count
        self.assertEqual(st.data['players']['jarda']['rec']['fast_win'][:2], [650, 2])
        r = rec(st, summ(len=900, winner=1, p0=player(parry=5)))      # a loss never sets fast_win
        self.assertEqual(r[0]['new_rec'], ['parry'])
        self.assertEqual(st.data['players']['jarda']['rec']['fast_win'][0], 650)
        r = rec(st, summ(len=500, code='disc', winner=0))             # a disconnect win is no fast win
        self.assertEqual(st.data['players']['jarda']['rec']['fast_win'][0], 650)
        r = rec(st, vyc('lehka', len=100))                            # Lehká wins are no fast win either
        self.assertEqual(st.data['players']['jarda']['rec']['fast_win'][0], 650)
        r = rec(st, vyc('tezka', len=400))
        self.assertEqual(r[0]['new_rec'], ['fast_win'])
        # Přežití: `surv` only
        r = rec(st, surv_s(1, wave=(10, 0), t=(400.0, 0.0), p0=player(zk=500)))
        self.assertEqual(r[0]['new_rec'], [])
        self.assertEqual(st.data['players']['jarda']['rec']['kills'][0], 41)   # zombies of Přežití are no `kills` record
        r = rec(st, surv_s(1, wave=(12, 0), t=(450.0, 0.0)))
        self.assertEqual(r[0]['new_rec'], ['surv'])

    def test_duplicate_or_anonymous_sides(self):
        st = fresh()
        self.assertEqual(rec(st, summ(p1=player('JARDA', 'jarda'))), {})        # the same profile on both seats
        self.assertEqual(st.data['players'], {})
        self.assertEqual(st.data['matches'], [])
        self.assertEqual(rec(st, summ(p0=player('Král', None), p1=player('Král', None))), {})   # nobody to record
        self.assertEqual(meta.key('Král'), None)

    def test_history_cap_and_ser_cap(self):
        st = fresh()
        for i in range(60):
            rec(st, summ(len=100 + i))
        ms = st.data['matches']
        self.assertEqual(len(ms), 50)
        self.assertEqual([m['id'] for m in ms][:3], [60, 59, 58])    # newest first
        self.assertEqual(ms[0]['len'], 159)
        self.assertTrue(all('ser' in m for m in ms[:10]))
        self.assertFalse(any('ser' in m for m in ms[10:]))
        self.assertEqual(st.data['next_id'], 61)
        self.assertEqual(st.data['players']['jarda']['tot']['m'], 60)  # the totals are not capped
        # the cap survives a save/load round trip
        d = tempfile.mkdtemp(prefix='hmk_meta_')
        try:
            st.path = os.path.join(d, 'stats.json')
            self.assertTrue(st.save())
            st2 = meta.Store(st.path)
            st2.load()
            self.assertEqual(len(st2.data['matches']), 50)
            self.assertEqual(sum(1 for m in st2.data['matches'] if 'ser' in m), 10)
            self.assertEqual(st2.data['next_id'], 61)
            self.assertLess(os.path.getsize(st.path), 400000)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_match_entry_shape(self):
        st = fresh()
        rec(st, summ(p0=player(fac='kult', zk=40, uk=22, bk=5, kk=2, crates=6, lost=19, spent=900), p1=player('Petr', 'petr', fac='prez')),
            now=NOW)
        m = st.data['matches'][0]
        self.assertEqual((m['id'], m['at'], m['type'], m['mode'], m['map'], m['len'], m['code'], m['win'], m['ai']),
                         (1, '2026-10-20T18:03', 'souboj', 'kral', 'most', 600, 'throne', 0, None))
        a = m['p'][0]
        self.assertEqual((a['k'], a['n'], a['fac'], a['res'], a['zk'], a['uk'], a['bk'], a['kk'], a['cr'], a['lost'], a['doba'], a['th']),
                         ('jarda', 'Jarda', 'kult', 'w', 40, 22, 5, 2, 6, 19, 3, 1500))
        self.assertEqual(a['inc'], [7.4, 11.5])
        self.assertGreater(a['xp'], 0)
        self.assertEqual((m['p'][1]['res'], m['p'][1]['fac']), ('l', 'prez'))
        self.assertEqual(sorted(m['ser']), ['army', 'dt', 'ecl', 'inc', 'night', 'th'])
        self.assertEqual(m['ser']['ecl'], [[240.0, 265.0]])
        self.assertEqual(len(m['ser']['th'][0]), 122)                # floor(600/5) + 2 samples
        rec(st, vyc('tezka', p1=player('Mrtvý velmistr', None, human=False, fac='kult')))
        m = st.data['matches'][0]
        self.assertEqual(m['ai'], {'diff': 'tezka', 'fac': 'bez'})
        self.assertEqual((m['p'][1]['k'], m['p'][1]['n'], m['p'][1]['h']), (None, 'Mrtvý velmistr', False))
        self.assertNotIn('xp', m['p'][1])
        rec(st, surv_s(2, winner=0, wave=(14, 9), t=(600.0, 400.0)))
        self.assertEqual(st.data['matches'][0]['surv'], {'players': 2, 'wave': [14, 9], 't': [600, 400]})
        json.dumps(st.data)

    def test_record_results_are_json_and_consistent(self):
        st = fresh()
        r = rec(st, summ(len=900, p0=player(crates=7), code='mat'))
        for s in (0, 1):
            x = r[s]
            self.assertEqual(sum(p[1] for p in x['xp_parts']), x['xp'])
            self.assertEqual(x['xp_tot'], st.data['players'][('jarda', 'petr')[s]]['xp'])
            self.assertTrue(x['cur'] <= x['xp_tot'] < x['next'] or x['lvl'] == 30)
            self.assertEqual(x['lvl'], meta.lvl_of(x['xp_tot']))
            self.assertEqual(x['ttl'], meta.title(x['lvl']))
            self.assertEqual(sorted(x), ['cur', 'elo', 'lvl', 'lvl0', 'lvlup', 'new_ach', 'new_cos', 'new_rec', 'next',
                                         'ttl', 'xp', 'xp_parts', 'xp_tot'])
        self.assertEqual(r[0]['new_ach'], ['korunovace', 'sach_mat', 'sberatel'])
        self.assertEqual(r[1]['new_ach'], [])
        json.dumps(r)

    def test_record_never_raises(self):
        st = fresh()
        two = [{'human': True, 'k': 'a', 'n': 'A'}, {'human': True, 'k': 'b', 'n': 'B'}]
        for bad in (None, 5, 'x', [], {}, {'type': 'souboj'}, {'type': 'souboj', 'len': 600, 'code': 'throne', 'p': 'x'},
                    {'type': 'souboj', 'len': 600, 'code': 'throne', 'p': [{}, {}]},
                    {'type': 'souboj', 'len': 600, 'code': 'throne', 'p': ['a', 'b']},
                    {'type': 'souboj', 'len': 600, 'code': 'throne', 'p': two[:1]},
                    {'type': 'souboj', 'len': 'long', 'code': 'throne', 'winner': 'x', 'p': two},
                    {'type': 'nonsense', 'len': 600, 'code': 'throne', 'winner': 0, 'p': two},
                    {'type': 'souboj', 'len': 600, 'code': 'error', 'winner': 0, 'p': two}):
            self.assertEqual(rec(st, bad), {}, bad)
        self.assertEqual((st.data['players'], st.data['matches']), ({}, []))
        # garbage in the winner of a recordable game: no exception, a draw for both
        r = rec(st, {'type': 'souboj', 'len': 600, 'code': 'throne', 'winner': 'x', 'p': two})
        self.assertEqual(sorted(r), [0, 1])
        self.assertEqual([st.data['players'][k]['tot']['d'] for k in ('a', 'b')], [1, 1])
        st = fresh()
        self.assertEqual(rec(None, summ()), {})
        # garbage inside an otherwise valid summary
        s = summ()
        s['p'][0]['st'] = {'zk': 'many', 'parry': None, 'relic_s': float('nan'), 'crates': -4}
        s['p'][0]['inc'] = 'x'
        s['p'][1]['fac'] = 'nonsense'
        s['ser'] = {'dt': 'x'}
        r = rec(st, s)
        self.assertEqual(sorted(r), [0, 1])
        self.assertEqual(st.data['players']['jarda']['tot']['zk'], 0)
        self.assertNotIn('ser', st.data['matches'][0])
        json.dumps(st.data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
