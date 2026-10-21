"""M2-A: engine counters, eclipse log, Poslední noc time and the 5 s time series (SPEC 3.6).

Needs the 1.0 package (skipped on the frozen 0.5 server)."""
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
from hmk import defs as D  # noqa: E402
from hmk.defs import W, H, TICK, DEFS, KRAL, ATTACK_TOWERS, LVL_MULT  # noqa: E402

DECK = ['navnada', 'kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec']
KEYS = ('kills', 'units', 'built', 'crates', 'techs', 'zk', 'uk', 'bk', 'kk', 'lost', 'parry', 'relic_s', 'spent', 'cast')


def game(mode='strateg', seed=1, waves=False):
    """A quiet game: no waves, crates or Alfa (unless asked), rich players."""
    g = S.Game(['A', 'B'], [list(DECK), list(DECK)], mode, seed=seed)
    g.next_crate = g.next_alfa = 1e9
    if not waves:
        g.next_wave = 1e9
    for sd in g.sd:
        sd.e, sd.s = 5000.0, 500.0
    return g


def run(g, secs):
    for _ in range(int(round(secs / TICK))):
        g.step(TICK)
        g.fx, g.msgs, g.evs, g.pfx = [], [[], []], [[], []], [[], []]


def texts(g, s):
    return [t for t, _ in g.msgs[s]]


class TestSideStats(unittest.TestCase):
    def test_all_keys_start_at_zero(self):
        g = game()
        for sd in g.sd:
            for k in KEYS:
                self.assertIn(k, sd.stats)
                self.assertEqual(sd.stats[k], 0, k)
        self.assertIsInstance(g.sd[0].stats['relic_s'], float)

    def test_zombie_kill_credits_zk_and_kills(self):
        g = game()
        z = g.spawn('chodec', 2, 7, 4)
        g.kill(z, 0)
        st = g.sd[0].stats
        self.assertEqual((st['zk'], st['uk'], st['bk'], st['kk'], st['kills'], st['lost']), (1, 0, 0, 0, 1, 0))
        self.assertEqual(g.sd[1].stats['zk'], 0)
        self.assertEqual(g.sd[1].stats['lost'], 0, 'a dead zombie is nobody\'s loss')

    def test_enemy_unit_kill_credits_uk_and_victim_lost(self):
        g = game()
        u = g.spawn('pesak', 1, 9, 4)
        g.kill(u, 0)
        a, b = g.sd[0].stats, g.sd[1].stats
        self.assertEqual((a['uk'], a['zk'], a['kills']), (1, 0, 1))
        self.assertEqual(b['lost'], 1)
        self.assertEqual(a['lost'], 0)

    def test_enemy_building_kill_credits_bk_not_kills(self):
        g = game()
        b = g.spawn('kulomet', 1, 13, 4)
        g.kill(b, 0)
        a, v = g.sd[0].stats, g.sd[1].stats
        self.assertEqual((a['bk'], a['kills'], a['uk'], a['zk']), (1, 0, 0, 0))
        self.assertEqual(v['lost'], 1)

    def test_king_kill_credits_kk_and_is_not_a_loss(self):
        g = game('kral')
        k = g.sd[1].kral
        g.kill(k, 0)
        a, v = g.sd[0].stats, g.sd[1].stats
        self.assertEqual((a['kk'], a['kills'], a['uk']), (1, 0, 0))
        self.assertEqual(v['lost'], 0, 'lost counts units and buildings only')

    def test_own_unit_killed_by_zombie_is_lost_but_nobody_scores(self):
        g = game()
        u = g.spawn('pesak', 0, 3, 4)
        g.kill(u, 2)
        self.assertEqual(g.sd[0].stats['lost'], 1)
        for k in ('zk', 'uk', 'bk', 'kk', 'kills'):
            self.assertEqual(g.sd[0].stats[k] + g.sd[1].stats[k], 0, k)

    def test_selling_is_not_a_loss(self):
        g = game()
        g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 2, 'y': 4})
        (b,) = [e for e in g.ents.values() if e.cat == 'b' and e.side == 0]
        g.act(0, {'t': 'sell', 'id': b.id})
        self.assertEqual(g.sd[0].stats['lost'], 0)
        self.assertEqual(g.sd[1].stats['bk'], 0)

    def test_kills_always_equals_zk_plus_uk_in_a_real_match(self):
        g = game(waves=True)
        g.next_wave = 5.0
        for x, y in ((3, 2), (3, 6), (4, 4)):
            g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': x, 'y': y})
        run(g, 120)
        for sd in g.sd:
            st = sd.stats
            self.assertEqual(st['kills'], st['zk'] + st['uk'])
        self.assertGreater(g.sd[0].stats['zk'], 0, 'the towers should have killed a zombie')

    def test_tower_kills_a_zombie_in_the_field(self):
        g = game()
        g.spawn('kulomet', 0, 4, 4)
        z = g.spawn('chodec', 2, 6, 4)
        z.tgt = 0
        g.sd[0].reveals.append([6, 4, 60.0, 3.0])
        run(g, 10)
        self.assertTrue(z.dead)
        self.assertEqual(g.sd[0].stats['zk'], 1)

    def test_parry_counts_successful_parries_only(self):
        g = game('kral')
        k = g.sd[0].kral
        g.act(0, {'t': 'in', 'b': True})
        self.assertGreaterEqual(g.sd[0].block_t, 0)
        shooter = g.spawn('strelec', 1, 8, 4)
        g.damage(k, 10.0, 1, None, shooter, True)          # inside the parry window
        self.assertEqual(g.sd[0].stats['parry'], 1)
        g.t += KRAL['parry'] + 0.5                           # the window has closed: a block, not a parry
        g.damage(k, 10.0, 1, None, shooter, True)
        self.assertEqual(g.sd[0].stats['parry'], 1)
        self.assertEqual(g.sd[1].stats['parry'], 0)

    def test_relic_s_grows_only_while_holding(self):
        g = game()
        g.t = g.prev_t = D.RELIC_FROM + 0.1
        p = g.spawn('pesak', 0, 7, 4)
        p.stun = 1e9
        run(g, D.RELIC_TIME + 0.5)
        self.assertEqual(g.relic['own'], 0)
        before = g.sd[0].stats['relic_s']
        self.assertLess(before, 1.0, 'only the time after the capture counts')
        run(g, 10.0)
        self.assertAlmostEqual(g.sd[0].stats['relic_s'] - before, 10.0, delta=0.1)
        self.assertEqual(g.sd[1].stats['relic_s'], 0.0)


class TestSpentAndCast(unittest.TestCase):
    def spent(self, g, s=0):
        return g.sd[s].stats['spent']

    def test_build_deploy_upgrade_cast_horde_squad_all_count_energy(self):
        g = game()
        sd = g.sd[0]
        g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 2, 'y': 4})
        self.assertEqual(self.spent(g), DEFS['kulomet']['cost'][0])
        s1 = self.spent(g)
        g.act(0, {'t': 'unit', 'kind': 'pesak', 'x': 1, 'y': 2})
        self.assertEqual(self.spent(g) - s1, DEFS['pesak']['cost'][0])
        s2 = self.spent(g)
        (b,) = [e for e in g.ents.values() if e.kind == 'kulomet']
        g.act(0, {'t': 'upg', 'id': b.id})
        self.assertEqual(self.spent(g) - s2, DEFS['kulomet']['up'][0][0])
        s3 = self.spent(g)
        g.act(0, {'t': 'card', 'id': 'navnada', 'x': 3, 'y': 6})
        self.assertEqual(self.spent(g) - s3, DEFS['navnada']['cost'][0])
        s4 = self.spent(g)
        cost, _ = g.horde_cost(0)
        g.act(0, {'t': 'horde'})
        self.assertEqual(self.spent(g) - s4, cost)
        s5 = self.spent(g)
        g.relic['on'] = True
        g.act(0, {'t': 'squad', 'id': 'relic'})
        self.assertEqual(self.spent(g), s5, 'a squad member pays at its deploy time, not when ordered')
        run(g, 6.0)
        paid = DEFS['obrnenec']['cost'][0] + 2 * DEFS['pesak']['cost'][0]
        self.assertEqual(self.spent(g) - s5, paid)
        self.assertEqual(sd.stats['units'], 1 + 3)

    def test_refused_actions_are_not_counted(self):
        g = game()
        g.sd[0].e = 1.0
        g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 2, 'y': 4})
        g.act(0, {'t': 'unit', 'kind': 'pesak', 'x': 1, 'y': 2})
        g.act(0, {'t': 'horde'})
        g.act(0, {'t': 'card', 'id': 'navnada', 'x': 3, 'y': 6})
        self.assertEqual(g.sd[0].stats['spent'], 0)
        self.assertEqual(g.sd[0].stats['cast'], 0)

    def test_cast_counts_abilities_and_commands_but_commands_cost_no_energy(self):
        g = game()
        sd = g.sd[0]
        g.act(0, {'t': 'card', 'id': 'navnada', 'x': 3, 'y': 6})
        self.assertEqual(sd.stats['cast'], 1)
        g.act(0, {'t': 'card', 'id': 'navnada', 'x': 3, 'y': 6})      # on cooldown: ignored
        self.assertEqual(sd.stats['cast'], 1)
        e0, spent0 = sd.e, sd.stats['spent']
        g.act(0, {'t': 'cmd', 'id': 'stit'})
        self.assertEqual(sd.stats['cast'], 2)
        self.assertEqual((sd.e, sd.stats['spent']), (e0, spent0))
        g.act(0, {'t': 'cmd', 'id': 'stit'})                            # cooldown
        self.assertEqual(sd.stats['cast'], 2)
        self.assertEqual(g.sd[1].stats['cast'], 0)

    def test_research_and_conversion_are_not_spending(self):
        g = game()
        g.sd[0].v = 10
        g.act(0, {'t': 'res', 'id': 'ing1'})
        self.assertEqual(g.sd[0].stats['spent'], 0)
        self.assertEqual(g.sd[0].stats['techs'], 1)


class TestEclipseLog(unittest.TestCase):
    def test_every_eclipse_is_logged_with_its_window(self):
        g = game()
        g.length = 1e9
        self.assertEqual(g.ecl_log, [])
        run(g, 245)
        self.assertEqual(g.ecl_log, [[240, 240 + D.ECL_LEN]], 'logged when it starts')
        run(g, 200)
        self.assertEqual(g.ecl_log, [[240, 265], [420, 445]])
        self.assertIsNone(g.night_t)

    def test_night_cuts_the_running_eclipse_short_and_sets_night_t(self):
        g = game()
        g.length = 250.0
        run(g, 245)
        self.assertIsNone(g.night_t)
        self.assertEqual(len(g.ecl_log), 1)
        run(g, 15)
        self.assertTrue(g.night)
        self.assertAlmostEqual(g.night_t, 250.0, delta=2 * TICK)
        self.assertEqual(len(g.ecl_log), 1, 'no eclipse is skipped in or after the night')
        a, b = g.ecl_log[0]
        self.assertEqual(a, 240)
        self.assertAlmostEqual(b, g.night_t, delta=2 * TICK)
        self.assertLess(b, 240 + D.ECL_LEN)

    def test_game_over_closes_the_running_eclipse(self):
        g = game()
        g.length = 1e9
        run(g, 250)
        g.throne[1] = 0.0
        run(g, 0.2)
        self.assertTrue(g.over)
        self.assertLess(g.ecl_log[0][1], 240 + D.ECL_LEN)
        self.assertAlmostEqual(g.ecl_log[0][1], g.t, delta=2 * TICK)
        self.assertEqual(g.over['code'], 'throne')

    def test_night_t_is_set_once(self):
        g = game()
        g.length = 30.0
        run(g, 40)
        t = g.night_t
        self.assertIsNotNone(t)
        run(g, 5)
        self.assertEqual(g.night_t, t)


class TestSeries(unittest.TestCase):
    def test_sample_at_start_then_every_5_s(self):
        g = game()
        self.assertEqual(g.ser['dt'], 5)
        self.assertEqual(sorted(g.ser), ['army', 'dt', 'inc', 'th'])
        for k in ('th', 'inc', 'army'):
            self.assertEqual([len(g.ser[k][0]), len(g.ser[k][1])], [1, 1], k)
        run(g, 12.0)
        self.assertEqual(len(g.ser['th'][0]), 3, 't = 0, 5, 10')
        run(g, 88.0)
        for k in ('th', 'inc', 'army'):
            self.assertEqual([len(g.ser[k][0]), len(g.ser[k][1])], [21, 21], k)

    def test_values_follow_the_spec_formulas(self):
        g = game()
        self.assertEqual(g.ser['th'][0][0], int(D.THRONE_HP))
        self.assertEqual(g.ser['inc'][0][0], int(round(D.BASE_INCOME * 10)))
        self.assertEqual(g.ser['army'][0][0], 0)
        g.spawn('pesak', 0, 3, 4)
        g.spawn('obrnenec', 0, 3, 5)
        g.spawn('kulomet', 0, 2, 4)
        g.throne[1] -= 123.7
        g.sample()
        pe, ob, ku = DEFS['pesak']['cost'], DEFS['obrnenec']['cost'], DEFS['kulomet']['cost']
        want = pe[0] + 3 * pe[1] + ob[0] + 3 * ob[1] + (ku[0] + 3 * ku[1]) * LVL_MULT[0]
        self.assertEqual(g.ser['army'][0][-1], int(round(want)))
        self.assertEqual(g.ser['army'][1][-1], 0)
        self.assertEqual(g.ser['th'][1][-1], int(D.THRONE_HP - 123.7))
        self.assertEqual(g.ser['inc'][0][-1], int(round(g.income(0) * 10)))

    def test_army_counts_attack_towers_by_level_and_ignores_walls_and_foes(self):
        g = game()
        t = g.spawn('kulomet', 0, 2, 4)
        t.lvl = 3
        z = g.spawn('zed', 0, 2, 5)
        g.spawn('chodec', 2, 7, 4)
        ku = DEFS['kulomet']['cost']
        self.assertEqual(g.army_value(0), int(round((ku[0] + 3 * ku[1]) * LVL_MULT[2])))
        self.assertNotIn(z.kind, ATTACK_TOWERS)

    def test_series_never_travel_in_snapshots(self):
        g = game()
        run(g, 6.0)
        for s in (0, 1):
            snap = g.snapshot(s, [])
            self.assertNotIn('ser', snap)
            self.assertNotIn('ecl', snap)

    def test_summary_fields_exist_for_the_session(self):
        """Session.finish reads these attributes; they must exist from the first tick."""
        g = game()
        for name in ('ecl_log', 'night_t', 'ser', 'pending'):
            self.assertTrue(hasattr(g, name), name)


class TestDeterminism(unittest.TestCase):
    def test_counters_do_not_depend_on_the_rng_stream(self):
        """Two games with the same seed produce the same counters and series."""
        def play():
            g = game(waves=True, seed=7)
            g.next_wave = 5.0
            for x, y in ((3, 2), (3, 6)):
                g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': x, 'y': y})
            run(g, 60)
            return [dict(sd.stats) for sd in g.sd], g.ser
        self.assertEqual(play(), play())


if __name__ == '__main__':
    unittest.main()
