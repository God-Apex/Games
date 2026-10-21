"""M3-B1: Výuka (META 5): a scripted player completes all 11 steps in both modes and wins; foe base, forced deck,
tu snapshot field, skip, hints, step texts, scripted events. Needs the 1.0 package (skipped on the frozen 0.5 server)."""
import os
import random
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'bal'))
import _paths  # noqa: E402
import harness as _H  # noqa: E402  (imported at discovery: it captures the pristine rules)

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('needs the 1.0 hmk package')
from hmk import maps, modes, tutorial  # noqa: E402
from hmk import defs as D  # noqa: E402
from hmk.defs import W, H, TICK  # noqa: E402
from hmk.game import Game  # noqa: E402
from hmk.maps import BUILD  # noqa: E402


def setUpModule():
    _H.reset_rules()          # test_tools/perf leave harness patches (stat tracking) on Game
    _H.TICK_HOOKS[:] = []


REC = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'dron']
IDS_KRAL = ['pohyb', 'gen', 'vez', 'vlna', 'blok', 'bedna', 'hlaska', 'upg', 'vyzkum', 'jednotka', 'utok']
IDS_STRAT = ['rozkazy', 'gen', 'vez', 'vlna', 'odstrel', 'bedna', 'hlaska', 'upg', 'vyzkum', 'jednotka', 'utok']
TEXTS = ['Pohni Králem klávesami W A S D.',
         'Postav Generátor: klávesa 1, pak klikni na zvýrazněné pole.',
         'Postav Kulomet blízko Mlhy (klávesa 3).',
         'Z Mlhy jdou zombie! Věž a Král je zastaví.',
         'Podrž mezerník: blok sníží poškození.',
         'Do Mlhy spadla bedna. Dojdi k ní a počkej 3 s.',
         'Postav Hlásku (klávesa 4). Uvidíš soupeře.',
         'Klikni na Kulomet a zmáčkni U.',
         'Za Vzorky se vyzkoumávají technologie. Zmáčkni V a jednu vyber.',
         'Vyšli Pěšáka (klávesa 5). Jde sám k soupeři.',
         'Znič soupeřův trůn!']
TEXT_STRAT = {0: 'Tvé rozkazy jsou na liště: Q W E R G.', 4: 'Zmáčkni W a klikni na zombie.'}


def game(mode='kral', seed=1, map_id='predmesti'):
    md = maps.pick_map(map_id, random.Random(seed))
    return Game(['Jarda', 'Nemrtví'], [list(REC), list(REC)], mode, rules=modes.make_rules('vyuka', {'mode': mode}),
                map_def=md, seed=seed)


def step(g, n=1):
    for _ in range(n):
        g.step(TICK)
        g.fx, g.pfx = [], [[], []]


def run(g, secs):
    for _ in range(int(round(secs / TICK))):
        if g.over:
            break
        step(g)


def foes(g, cat=None):
    return [e for e in g.ents.values() if e.side == 1 and (cat is None or e.cat == cat)]


class Bot:
    """A scripted beginner: does what the open step asks, then spams Obrněnci at the enemy throne."""

    def __init__(self, g):
        self.g = g
        self.last_in = None
        self.n = 0

    def free(self, x0, y0, kral_off=True):
        g = self.g
        return g.rules._nearest(g, x0, y0, lambda x, y: g.ter[y][x] in BUILD and g.buildable(0, x) and g.bld[y][x] is None
                                and g.mob[y][x] is None and not g.kral_near(x, y))

    def send_in(self, mx, my, b=False):
        key = (mx, my, b)
        if key != self.last_in:
            self.last_in = key
            self.g.act(0, {'t': 'in', 'mx': mx, 'my': my, 'b': b})

    def tick(self):
        g, r, sd = self.g, self.g.rules, self.g.sd[0]
        sid = r.steps[r.i]['id']
        self.n += 1
        k = sd.kral
        mx = my = 0
        b = False
        if sid == 'pohyb':
            mx = 1
        elif sid == 'blok':
            b = True
        elif sid == 'bedna' and k is not None and g.crates:
            c = next(iter(g.crates.values()))
            dx, dy = c['x'] - k.x, c['y'] - k.y
            mx, my = (dx > 0.15) - (dx < -0.15), (dy > 0.15) - (dy < -0.15)
        elif k is not None and sid not in ('pohyb', 'blok', 'bedna') and k.x > 2.0:
            mx = -1
        if g.mode == 'kral':
            self.send_in(mx, my, b)
        if self.n % 5:
            return
        if sid == 'gen':
            x, y = r.hint
            g.act(0, {'t': 'build', 'kind': 'gen', 'x': x, 'y': y})
        elif sid == 'vez':
            x, y = r.hint
            g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': x, 'y': y})
        elif sid == 'odstrel':
            z = next((e for e in g.ents.values() if e.cat == 'z'), None)
            x, y = (z.cx, z.cy) if z is not None and g.vis[0][z.cy][z.cx] else (3, 4)
            g.act(0, {'t': 'cmd', 'id': 'odstrel', 'x': x, 'y': y})
        elif sid == 'bedna' and g.mode == 'strateg' and g.crates:
            c = next(iter(g.crates.values()))
            if c['land'] <= 0 and not g.drones:
                g.act(0, {'t': 'cmd', 'id': 'sber', 'x': c['x'], 'y': c['y']})
        elif sid == 'hlaska' and not g.count(0, 'hlaska'):
            cell = self.free(3, 6)
            g.act(0, {'t': 'build', 'kind': 'hlaska', 'x': cell[0], 'y': cell[1]})
        elif sid == 'upg':
            kul = next((e for e in g.ents.values() if e.side == 0 and e.kind == 'kulomet'), None)
            if kul is not None:
                g.act(0, {'t': 'upg', 'id': kul.id})
        elif sid == 'vyzkum':
            g.act(0, {'t': 'res', 'id': 'ing1'})
        elif sid == 'jednotka':
            g.act(0, {'t': 'unit', 'kind': 'pesak', 'x': 5, 'y': 4})
        elif sid == 'utok':
            if g.count(0, 'gen') < 4 and sd.e >= 60:
                cell = self.free(2, 1 + 2 * g.count(0, 'gen'))
                if cell:
                    g.act(0, {'t': 'build', 'kind': 'gen', 'x': cell[0], 'y': cell[1]})
            elif sd.e >= 110:
                row = (4, 3, 5, 2, 6, 1, 7)[(self.n // 5) % 7]
                g.act(0, {'t': 'unit', 'kind': 'obrnenec', 'x': 5, 'y': row})


def play(mode, seed=1, map_id='predmesti', limit=600.0):
    g = game(mode, seed, map_id)
    bot = Bot(g)
    visited = [g.rules.steps[g.rules.i]['id']]
    while not g.over and g.t < limit:
        bot.tick()
        step(g)
        sid = g.rules.steps[g.rules.i]['id']
        if sid != visited[-1]:
            visited.append(sid)
    return g, visited


class TestFullRun(unittest.TestCase):
    def check(self, mode, ids):
        g, visited = play(mode)
        self.assertIsNotNone(g.over, '%s: not finished in 600 s (step %s, t=%.0f)' % (mode, visited[-1], g.t))
        self.assertEqual(visited, ids, 'every step in order, none skipped')
        self.assertEqual((g.over['winner'], g.over['code']), (0, 'throne'))
        self.assertLessEqual(g.t, 600.0)
        info = g.end_info()
        self.assertEqual((info['code'], info['winner']), ('throne', 0))
        return g

    def test_kral_completes_all_steps(self):
        self.check('kral', IDS_KRAL)

    def test_strateg_completes_all_steps(self):
        self.check('strateg', IDS_STRAT)

    def test_ruiny_map_is_playable_too(self):
        g, visited = play('strateg', seed=3, map_id='ruiny')
        self.assertIsNotNone(g.over, 'ruiny: stuck at step %s' % visited[-1])
        self.assertEqual(g.over['winner'], 0)


class TestSetup(unittest.TestCase):
    def test_enemy_base_on_predmesti(self):
        g = game('kral')
        want = {('gen', 1, 2), ('gen', 1, 4), ('gen', 1, 6), ('kulomet', 4, 3), ('kulomet', 4, 5), ('hlaska', 3, 4)}
        got = {(e.kind, W - 1 - e.cx, e.cy) for e in foes(g, 'b')}
        self.assertEqual(got, want)
        self.assertEqual(g.throne[1], 1200.0)
        self.assertEqual(g.throne[0], float(D.THRONE_HP))
        self.assertEqual([e for e in foes(g) if e.cat != 'b'], [], 'no foe King or units at the start')
        self.assertIsNone(g.sd[1].kral)
        self.assertIsNone(g.sd[1].respawn_len)

    def test_enemy_base_on_every_map(self):
        for map_id in maps.MAPS:
            for seed in (1, 2, 3):
                g = game('strateg', seed, map_id)
                kinds = sorted(e.kind for e in foes(g, 'b'))
                self.assertEqual(kinds, ['gen'] * 3 + ['hlaska'] + ['kulomet'] * 2, '%s seed %d' % (map_id, seed))
                for e in foes(g, 'b'):
                    self.assertIn(g.ter[e.cy][e.cx], BUILD)
                    self.assertGreaterEqual(e.cx, 10)

    def test_rules_flags_and_no_world_events(self):
        g = game('kral')
        r = g.rules
        self.assertEqual((r.play, r.relic, r.checkmate, r.night), ('vyuka', False, False, False))
        self.assertEqual(g.length, float('inf'))
        self.assertEqual(g.eclipse(), [0, 0])
        run(g, 140)
        self.assertEqual(g.stage, 0, 'the Mist never advances')
        self.assertFalse(g.relic['on'])
        self.assertEqual(g.crates, {})
        self.assertFalse(g.night)
        self.assertEqual(g.wave_n, 0)
        self.assertEqual([e for e in g.ents.values() if e.cat == 'z'], [])
        self.assertIsNone(g.over)

    def test_forced_deck(self):
        g = game('kral')
        self.assertEqual(g.sd[0].deck, tutorial.TUT_DECK)
        self.assertEqual(g.start_info(0)['deck'], tutorial.TUT_DECK)
        self.assertEqual(tutorial.TUT_DECK[:3], ['kulomet', 'hlaska', 'pesak'], 'keys 3, 4 and 5')
        self.assertIsNotNone(D.valid_deck(list(tutorial.TUT_DECK)))
        self.assertEqual(tutorial.TUT_FOE['throne'], 1200)

    def test_step_texts_verbatim(self):
        self.assertEqual([s['text'] for s in tutorial.TUT_STEPS], TEXTS)
        k, st = tutorial.steps_for('kral'), tutorial.steps_for('strateg')
        self.assertEqual([s['id'] for s in k], IDS_KRAL)
        self.assertEqual([s['id'] for s in st], IDS_STRAT)
        for i in range(11):
            self.assertEqual(st[i]['text'], TEXT_STRAT.get(i, TEXTS[i]))
        ex = game('strateg').start_info(0)['tsteps']
        self.assertEqual([t['text'] for t in ex], [st[i]['text'] for i in range(11)])

    def test_make_rules_dispatch(self):
        r = modes.make_rules('vyuka', {'mode': 'strateg'})
        self.assertIsInstance(r, tutorial.TutorialRules)
        self.assertEqual(r.mode, 'strateg')
        self.assertEqual(modes.make_rules('vyuka', {}).mode, 'kral')

    def test_build_game_integration(self):
        from hmk import session
        opts = {'type': 'vyuka', 'mode': 'kral', 'map': 'predmesti', 'ai': None, 'fac': 'bez', 'deck': list(REC), 'puzzle': None}
        g, ais = session.build_game('vyuka', opts, [('A', list(REC), 'bez'), None], seed=2)
        self.assertEqual((g.play, ais), ('vyuka', [None, None]))
        self.assertEqual(g.sd[0].deck, tutorial.TUT_DECK)
        self.assertEqual(g.snapshot(0, [])['tu'][:2], [1, 11])


class TestSteps(unittest.TestCase):
    def test_tu_field_hint_and_pulse(self):
        g = game('strateg')
        run(g, 6.2)
        tu = g.snapshot(0, [])['tu']
        self.assertEqual(tu[:2], [2, 11], 'rozkazy done after 6 s')
        self.assertEqual((tu[2], tu[3]), g.rules.hint)
        self.assertEqual((tu[2], tu[3]), (1, 4), 'local (1,4) on Předměstí')
        self.assertEqual(tu[4], '', 'no ui hint before 20 s')
        run(g, 19)
        self.assertEqual(g.snapshot(0, [])['tu'][4], '')
        run(g, 1.5)
        tu = g.snapshot(0, [])['tu']
        self.assertEqual(tu[4], 'slot:1', 'the pulse turns on after 20 s')
        self.assertEqual(tu[:2], [2, 11])
        self.assertNotIn('tu', g.snapshot(1, []))

    def test_no_hint_is_minus_one(self):
        g = game('kral')
        tu = g.snapshot(0, [])['tu']
        self.assertEqual(tu, [1, 11, -1, -1, ''])

    def test_move_step_needs_two_cells(self):
        g = game('kral')
        g.act(0, {'t': 'in', 'mx': 1, 'my': 0})
        run(g, 0.5)
        self.assertEqual(g.rules.i, 0)
        run(g, 1.5)
        self.assertEqual(g.rules.i, 1)

    def test_done_steps_are_skipped(self):
        g = game('strateg')
        g.act(0, {'t': 'build', 'kind': 'gen', 'x': 1, 'y': 4})
        g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 4, 'y': 4})
        run(g, 5.5)
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'rozkazy')
        run(g, 1.0)
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'vlna', 'gen and vez were already done')
        self.assertEqual(len([e for e in g.ents.values() if e.cat == 'z']), 3, 'step 4 spawned 3 chodci')

    def test_wave_step_needs_the_three_chodci_dead(self):
        g = game('strateg')
        for _ in range(3):
            g.rules.on_msg(g, 0, {'t': 'tut', 'skip': 1})
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'vlna')
        zs = [e for e in g.ents.values() if e.cat == 'z']
        self.assertEqual(len(zs), 3)
        self.assertTrue(all(z.kind == 'chodec' and z.tgt == 0 and z.cx in g.map.spawn[0] for z in zs))
        step(g)
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'vlna')
        for z in zs[:2]:
            g.remove(z)
        step(g)
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'vlna')
        g.remove(zs[2])
        step(g)
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'odstrel')
        obr = [e for e in g.ents.values() if e.cat == 'z']
        self.assertEqual([e.kind for e in obr], ['obr'], 'Stratég: step 5 spawns 1 Obr')

    def test_block_step_counts_a_short_tap(self):
        g = game('kral')
        for _ in range(4):
            g.act(0, {'t': 'tut', 'skip': 1})
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'blok')
        g.act(0, {'t': 'in', 'b': True})
        g.act(0, {'t': 'in', 'b': False})          # released before any tick
        step(g)
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'bedna')

    def test_crate_step_drops_and_redrops(self):
        g = game('strateg')
        for _ in range(5):
            g.act(0, {'t': 'tut', 'skip': 1})
        r = g.rules
        self.assertEqual(r.steps[r.i]['id'], 'bedna')
        cr = list(g.crates.values())
        self.assertEqual(len(cr), 1)
        self.assertEqual((cr[0]['x'], cr[0]['y'], cr[0]['r']), (6, 4, 2))
        self.assertAlmostEqual(cr[0]['land'], 2.0, 1)
        g.crates.clear()                           # expired unopened
        step(g)
        self.assertEqual(len(g.crates), 1, 'a new crate is dropped')
        self.assertEqual(g.sd[0].stats['crates'], 0)

    def test_hlaska_step_shows_the_enemy_base(self):
        g = game('strateg')
        for _ in range(6):
            g.act(0, {'t': 'tut', 'skip': 1})
        r = g.rules
        self.assertEqual(r.steps[r.i]['id'], 'hlaska')
        g.sd[0].e = 500.0
        g.act(0, {'t': 'build', 'kind': 'hlaska', 'x': 3, 'y': 6})
        step(g, 3)
        self.assertEqual(r.steps[r.i]['id'], 'upg', 'a visible enemy building completes the step')
        self.assertTrue(g.sd[0].reveals)

    def test_entry_grants(self):
        g = game('strateg')
        for _ in range(7):
            g.act(0, {'t': 'tut', 'skip': 1})
        self.assertEqual(g.rules.steps[g.rules.i]['id'], 'upg')
        self.assertEqual(g.sd[0].s, D.START_RES[1] + 40)
        v0 = g.sd[0].v
        g.act(0, {'t': 'tut', 'skip': 1})
        self.assertEqual(g.sd[0].v, v0 + 2)

    def test_last_step_spawns_two_pesaks_once_and_cannot_be_skipped(self):
        g = game('kral')
        for _ in range(10):
            g.act(0, {'t': 'tut', 'skip': 1})
        r = g.rules
        self.assertEqual(r.steps[r.i]['id'], 'utok')
        pes = [e for e in foes(g) if e.kind == 'pesak']
        self.assertEqual(len(pes), 2)
        self.assertTrue(all(e.cat == 'u' and e.cx >= 10 for e in pes))
        for _ in range(5):
            g.act(0, {'t': 'tut', 'skip': 1})
        self.assertEqual(r.i, 10)
        run(g, 5)
        self.assertLessEqual(len([e for e in foes(g) if e.kind == 'pesak']), 2)
        self.assertEqual(g.snapshot(0, [])['tu'][:2], [11, 11])
        self.assertIsNone(g.over)

    def test_skip_and_garbage_messages(self):
        g = game('kral')
        for m in ({'t': 'tut'}, {'t': 'tut', 'skip': 0}, {'t': 'tut', 'skip': None}, {'t': 'tut', 'skip': 'x'},
                  {'t': 'tut', 'skip': [1]}, {'t': 'zzz'}, {}):
            g.act(0, m)
        self.assertEqual(g.rules.i, 0)
        g.act(1, {'t': 'tut', 'skip': 1})           # only the player's own skip counts
        self.assertEqual(g.rules.i, 0)
        g.act(0, {'t': 'tut', 'skip': 1})
        self.assertEqual(g.rules.i, 1)

    def test_deterministic(self):
        def hashes():
            g = game('kral', seed=4)
            bot = Bot(g)
            out = []
            for _ in range(3):
                for _ in range(int(40 / TICK)):
                    bot.tick()
                    step(g)
                out.append(g.state_hash())
            return out
        self.assertEqual(hashes(), hashes())


if __name__ == '__main__':
    unittest.main()
