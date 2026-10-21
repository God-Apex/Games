"""M3-B1: Přežití (MAI 6): wave table, spawn queue, quarantine wall, crates, Tlupa, solo isolation, end codes, eclipse/Mist.

Needs the 1.0 package (skipped on the frozen 0.5 server)."""
import math
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
from hmk import defs as D  # noqa: E402
from hmk import maps, modes  # noqa: E402
from hmk.defs import W, H, TICK, DEFS  # noqa: E402
from hmk.game import Game  # noqa: E402


def setUpModule():
    _H.reset_rules()          # test_tools/perf leave harness patches (stat tracking) on Game
    _H.TICK_HOOKS[:] = []


DECK = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'dron']

# MAI 6 table: wave -> (time s, Chodec, Běžec, Obr, Alfa, hp x)
TABLE = {1: (30, 4, 0, 0, 0, 1.0), 5: (152, 9, 3, 0, 0, 1.0), 10: (291, 14, 11, 0, 1, 1.0), 15: (415, 19, 15, 1, 0, 1.2),
         20: (524, 20, 16, 4, 2, 1.45), 25: (618, 20, 16, 7, 0, 1.7), 30: (708, 20, 16, 10, 3, 1.95)}


def game(players=1, mode='kral', seed=1, map_id='predmesti', rich=False):
    md = maps.pick_map(map_id, random.Random(seed))
    g = Game(['A', 'B'], [list(DECK), list(DECK)], mode, rules=modes.SurvivalRules(players), map_def=md, seed=seed)
    if rich:
        for sd in g.sd:
            sd.e, sd.s = 5000.0, 500.0
    return g


def step(g, n=1):
    for _ in range(n):
        g.step(TICK)
        g.fx, g.evs, g.pfx = [], [[], []], [[], []]


def run(g, secs, each=None):
    for _ in range(int(round(secs / TICK))):
        if g.over:
            break
        step(g)
        if each:
            each(g)


def texts(g, s):
    return [t for t, _ in g.msgs[s]]


def zombies(g, tgt=None):
    return [e for e in g.ents.values() if e.cat == 'z' and (tgt is None or e.tgt == tgt)]


class TestWaveTable(unittest.TestCase):
    def test_time_budget_composition(self):
        for k, (t, walk, run_, obr, alfa, hp) in sorted(TABLE.items()):
            self.assertEqual(int(round(modes.wave_time(k))), t, 'time of wave %d' % k)
            self.assertEqual(modes.wave_comp(k), (walk, run_, obr, alfa), 'composition of wave %d' % k)
            self.assertAlmostEqual(modes.wave_mult(k)[0], hp, 6, 'hp x of wave %d' % k)

    def test_budget_formula_and_knob(self):
        self.assertEqual(modes.wave_budget(1), 4)
        self.assertEqual(modes.wave_budget(10), 25)
        old = modes.SURV_C
        try:
            modes.SURV_C = 0.0
            self.assertEqual(modes.wave_budget(10), 18)          # 2 + 16
        finally:
            modes.SURV_C = old
        self.assertEqual(modes.wave_budget(10), 25)

    def test_multipliers_start_at_wave_12(self):
        self.assertEqual(modes.wave_mult(11), (1.0, 1.0))
        hp, dm = modes.wave_mult(12)
        self.assertAlmostEqual(hp, 1.05, 6)
        self.assertAlmostEqual(dm, 1.03, 6)
        self.assertAlmostEqual(modes.wave_mult(30)[1], 1.57, 6)

    def test_entity_cap(self):
        for k in range(1, 80):
            walk, run_, obr, alfa = modes.wave_comp(k)
            self.assertLessEqual(walk + run_, 36)
            self.assertGreaterEqual(walk, 0)

    def test_spawned_counts_match_table(self):
        """The real spawn queue produces the table counts and the stat multipliers (the zombies are removed each tick so
        the 18 spawn cells never block the queue)."""
        g = game(1, rich=True)
        seen = {}                                                 # wave -> {kind: n}
        hpseen = {}

        def sweep(g):
            g.throne[0] = 1e9
            for z in zombies(g):
                if getattr(z, 'wv', 0) not in hpseen:
                    hpseen[z.wv] = (z.maxhp / DEFS[z.kind]['hp'], g.dmg_of(z) / DEFS[z.kind]['dmg'])
                d = seen.setdefault(z.wv, {})
                d[z.kind] = d.get(z.kind, 0) + 1
                g.remove(z)
        run(g, modes.wave_time(30) + 15, sweep)
        for k, (t, walk, run_, obr, alfa, hp) in TABLE.items():
            d = seen.get(k, {})
            self.assertEqual((d.get('chodec', 0), d.get('bezec', 0), d.get('obr', 0), d.get('alfa', 0)),
                             (walk, run_, obr, alfa), 'wave %d' % k)
            self.assertAlmostEqual(hpseen[k][0], hp, 5, 'hp x wave %d' % k)
            self.assertAlmostEqual(hpseen[k][1], modes.wave_mult(k)[1], 5, 'dmg x wave %d' % k)
        self.assertEqual(g.rules.k, 30)

    def test_spawn_rate_limit(self):
        g = game(1, rich=True)
        g.rules.k = 19
        g.rules.t_next = 0.0
        peaks = []
        for _ in range(int(12 / TICK)):
            before = len(zombies(g))
            step(g)
            peaks.append(len(zombies(g)) - before)
        # at most 6 per flush and a flush every 0.5 s (10 ticks), so no 10-tick window holds more than 6 new zombies
        self.assertGreater(sum(peaks), 12, 'the wave is big enough to need several flushes')
        for i in range(0, len(peaks) - 10):
            self.assertLessEqual(sum(peaks[i:i + 10]), 6)


class TestWall(unittest.TestCase):
    def test_units_and_kings_blocked_zombies_not(self):
        g = game(2, 'kral')
        self.assertIsNotNone(g.may_enter)
        p0 = g.spawn('pesak', 0, 7, 0)
        p1 = g.spawn('pesak', 1, 8, 8)
        self.assertFalse(g.can_enter(p0, 8, 0), 'side 0 unit must not cross to x=8')
        self.assertTrue(g.can_enter(p0, 6, 0))
        self.assertFalse(g.can_enter(p1, 7, 8), 'side 1 unit must not cross to x=7')
        self.assertTrue(g.can_enter(p1, 9, 8))
        z = g.spawn('chodec', 2, 7, 2)
        z.tgt = 1
        self.assertTrue(g.can_enter(z, 8, 2), 'zombies cross the wall')
        z2 = g.spawn('chodec', 2, 8, 4)
        self.assertTrue(g.can_enter(z2, 7, 4))
        k0, k1 = g.sd[0].kral, g.sd[1].kral
        self.assertTrue(g.kral_blocked(k0, 8, 4))
        self.assertFalse(g.kral_blocked(k0, 7, 4))
        self.assertTrue(g.kral_blocked(k1, 7, 4))
        self.assertFalse(g.kral_blocked(k1, 8, 4))

    def test_walking_unit_stops_at_the_wall(self):
        g = game(2, 'strateg', rich=True)
        y = 4
        g.act(0, {'t': 'unit', 'kind': 'pesak', 'x': 5, 'y': y})
        g.act(1, {'t': 'unit', 'kind': 'pesak', 'x': 10, 'y': y})
        mine = [e for e in g.ents.values() if e.cat == 'u' and e.side == 0][0]
        foe = [e for e in g.ents.values() if e.cat == 'u' and e.side == 1][0]
        hi, lo = [0], [W]

        def watch(g):
            g.sd[0].e = g.sd[1].e = 5000.0
            g.throne[0] = g.throne[1] = 1e9
            for z in zombies(g):
                g.remove(z)
            hi[0] = max(hi[0], mine.cx if not mine.dead else 0)
            lo[0] = min(lo[0], foe.cx if not foe.dead else W)
        # the units (side 0 and side 1) also shoot at each other across the wall, so only the x range is asserted
        run(g, 25, watch)
        self.assertEqual(hi[0], 7)
        self.assertEqual(lo[0], 8)

    def test_no_promotion(self):
        g = game(1, 'strateg')
        self.assertFalse(g.rules.promotion)


class TestSolo(unittest.TestCase):
    def test_side_one_is_a_dummy(self):
        g = game(1, 'kral')
        self.assertIsNone(g.sd[1].kral, 'no King on side 1')
        self.assertIsNotNone(g.sd[0].kral)
        self.assertIsNone(g.sd[1].respawn_len)
        g.throne[1] -= 1500
        g.rules.next_crate = 10.0
        seen_tgt1, crate_x = [], set()

        def watch(g):
            seen_tgt1.extend(zombies(g, 1))
            crate_x.update(c['x'] for c in g.crates.values())
            g.throne[0] = 1e9
        run(g, 130, watch)
        self.assertEqual(g.throne[1], float(D.THRONE_HP), 'side 1 throne is untouchable')
        self.assertEqual(seen_tgt1, [], 'no zombie ever targets side 1')
        self.assertTrue(crate_x and crate_x <= {7}, 'only side 0 gets crates: %s' % sorted(crate_x))
        self.assertIsNone(g.sd[1].kral)

    def test_no_king_in_strateg_either(self):
        g = game(1, 'strateg')
        self.assertIsNone(g.sd[1].kral)

    def test_horde_and_outage_refused(self):
        g = game(1, 'strateg', rich=True)
        e0 = g.sd[0].e
        g.act(0, {'t': 'horde'})
        self.assertEqual(g.sd[0].e, e0)
        self.assertTrue(texts(g, 0))
        self.assertEqual(g.sd[0].horde_cd, 0)
        g.msgs = [[], []]
        g.sd[0].free['vypadek'] = 1
        g.act(0, {'t': 'card', 'id': 'vypadek'})
        self.assertEqual(g.sd[1].outage, 0.0)
        self.assertEqual(g.sd[0].free.get('vypadek'), 1, 'the refused card is not consumed')
        self.assertTrue(texts(g, 0))

    def test_ends_with_survive_when_the_throne_falls(self):
        g = game(1, 'strateg', rich=True)
        g.throne[0] = 60.0
        run(g, 400)
        self.assertIsNotNone(g.over, 'zombies must finish a 60 HP throne')
        self.assertEqual(g.over['code'], 'survive')
        self.assertEqual(g.over['winner'], -1)
        info = g.end_info()
        self.assertEqual(info['code'], 'survive')
        sv = info['surv']
        self.assertEqual(sv['wave'][1], 0)
        self.assertEqual(sv['t'][1], 0.0)
        self.assertGreaterEqual(sv['wave'][0], 0)
        self.assertLessEqual(sv['wave'][0], g.rules.k)
        self.assertAlmostEqual(sv['t'][0], g.t, 1)
        self.assertEqual(g.throne[1], float(D.THRONE_HP))

    def test_cleared_wave_counts_only_dead_waves(self):
        g = game(1, 'strateg')
        r = g.rules
        r.k = 3
        r.left = {1: 0, 2: 0, 3: 2}
        r._clear_update(g)
        self.assertEqual(r.cleared[0], 2)
        z = g.spawn('chodec', 2, 7, 4)
        z.wv, z.tgt = 1, 0
        r.cleared[0] = 0
        r._clear_update(g)
        self.assertEqual(r.cleared[0], 0, 'a live zombie of wave 1 keeps it open')
        g.remove(z)
        r._clear_update(g)
        self.assertEqual(r.cleared[0], 2)

    def test_snapshot_and_start_fields(self):
        g = game(1, 'kral')
        run(g, 31)
        m = g.snapshot(0, [])
        sv = m['sv']
        self.assertEqual(len(sv), 4)
        self.assertEqual(sv[0], 1)
        self.assertEqual(sv[1], int(math.ceil(modes.wave_time(2) - g.t)))
        self.assertEqual(m['nw'], int(max(0, g.next_wave - g.t)))
        self.assertGreater(sv[2], 0, 'wave 1 zombies march at my throne')
        self.assertEqual(sv[3], 0)
        self.assertEqual(g.start_info(0)['t'], 'start')


class TestCrates(unittest.TestCase):
    def test_first_crate_at_40_and_gaps(self):
        g = game(2, 'strateg')
        log = {}

        def watch(g):
            g.throne[0] = g.throne[1] = 1e9
            for z in zombies(g):
                g.remove(z)
            for c in g.crates.values():
                log.setdefault(c['id'], (round(g.t, 2), c['x'], c['y'], c['r']))
        run(g, 360, watch)
        drops = sorted(log.values())
        self.assertGreaterEqual(len(drops), 6)
        pairs = {}
        for t, x, y, r in drops:
            pairs.setdefault(t, []).append((x, y, r))
        times = sorted(pairs)
        self.assertAlmostEqual(times[0], 40.0, 1)
        for t in times:
            (xa, ya, ra), (xb, yb, rb) = sorted(pairs[t])
            self.assertEqual((xa, xb), (7, 8))
            self.assertEqual((ya, ra), (yb, rb), 'mirrored pair: same row and rarity')
        self.assertGreaterEqual(pairs[times[0]][0][2], 1, 'first crate at least neobvyklá')
        for a, b in zip(times, times[1:]):
            self.assertTrue(45 - 0.2 <= b - a <= 60 + 0.2, 'gap %.2f' % (b - a))

    def test_crate_rows_follow_the_map(self):
        g = game(2, 'strateg', map_id='most')
        g.rules.next_crate = 1.0
        rows = set()

        def watch(g):
            g.throne[0] = g.throne[1] = 1e9
            for z in zombies(g):
                g.remove(z)
            rows.update(c['y'] for c in g.crates.values())
        run(g, 200, watch)
        self.assertTrue(rows and rows <= set(g.map.crate_rows), rows)

    def test_alfa_crate_lands_in_the_killers_column(self):
        for players, killer, col in ((2, 0, 7), (2, 1, 8), (1, 0, 7)):
            g = game(players, 'strateg')
            a = g.spawn('alfa', 2, 11, 5)
            g.damage(a, 1e9, killer)
            cr = list(g.crates.values())
            self.assertEqual(len(cr), 1)
            self.assertEqual((cr[0]['x'], cr[0]['y'], cr[0]['r']), (col, 5, len(D.RARITY) - 1))

    def test_sber_on_the_other_half_is_refused(self):
        g = game(2, 'strateg', rich=True)
        g.drop_crate(8, 4, 0, land=0.0)               # side 1's crate
        g.drop_crate(7, 5, 0, land=0.0)               # side 0's crate
        g.msgs = [[], []]
        g.act(0, {'t': 'cmd', 'id': 'sber', 'x': 8, 'y': 4})
        self.assertIn('Tahle bedna patří soupeři.', texts(g, 0))
        self.assertEqual(g.drones, [])
        g.act(0, {'t': 'cmd', 'id': 'sber', 'x': 7, 'y': 5})
        self.assertEqual(len(g.drones), 1)
        g.act(1, {'t': 'cmd', 'id': 'sber', 'x': 7, 'y': 5})
        self.assertIn('Tahle bedna patří soupeři.', texts(g, 1))
        self.assertEqual(len(g.drones), 1)
        g.act(0, {'t': 'cmd', 'id': 'sber', 'x': 'x', 'y': None})      # malformed: ignored, no exception


class TestTwoPlayers(unittest.TestCase):
    def test_waves_are_mirrored_pairs(self):
        g = game(2, 'strateg')
        first = []

        def watch(g):
            g.throne[0] = g.throne[1] = 1e9
            if not first and zombies(g):
                first.extend((z.tgt, z.kind, z.cx, z.cy) for z in zombies(g))
        run(g, 31, watch)
        self.assertTrue(first)
        mine = sorted((k, x, y) for t, k, x, y in first if t == 0)
        foe = sorted((k, W - 1 - x, y) for t, k, x, y in first if t == 1)
        self.assertEqual(mine, foe, 'same kinds, mirrored cells')
        self.assertEqual(len(mine), 4)

    def test_tlupa_points_cost_and_cooldown(self):
        g = game(2, 'strateg', rich=True)
        g.rules.k = 10
        e0 = g.sd[0].e
        g.act(0, {'t': 'horde'})
        self.assertAlmostEqual(g.sd[0].e, e0 - D.HORDE_COST, 5)
        self.assertEqual(g.sd[0].horde_cd, D.HORDE_CD)
        pts = int(round(0.35 * modes.wave_budget(10)))
        walk, run_, obr, _ = modes.wave_comp(10, pts, boss=False)
        self.assertEqual(sorted(k for k, _, _ in g.rules.pq[1]), sorted(['chodec'] * walk + ['bezec'] * run_ + ['obr'] * obr))
        self.assertEqual(len(g.rules.pq[1]), pts)
        self.assertEqual(g.rules.pq[0], [])
        e1 = g.sd[0].e
        g.act(0, {'t': 'horde'})
        self.assertEqual(g.sd[0].e, e1, 'cooldown')
        step(g, 12)
        self.assertGreater(len(zombies(g, 1)), 0)
        self.assertEqual(zombies(g, 0), [])
        self.assertTrue(any(('tlupu' in t) for t in texts(g, 0)))
        self.assertTrue(any(('tlupu' in t) for t in texts(g, 1)))

    def test_tlupa_costs_less_with_bio1_and_needs_energy(self):
        g = game(2, 'strateg')
        g.sd[0].techs.add('bio1')
        g.sd[0].e = 100.0
        g.act(0, {'t': 'horde'})
        self.assertAlmostEqual(g.sd[0].e, 100.0 - round(D.HORDE_COST * 0.6), 5)
        self.assertEqual(g.sd[0].horde_cd, 15.0)
        g2 = game(2, 'strateg')
        g2.sd[0].e = 50.0
        g2.act(0, {'t': 'horde'})
        self.assertEqual(g2.sd[0].e, 50.0)
        self.assertEqual(g2.rules.pq[1], [])
        self.assertTrue(texts(g2, 0))

    def test_outage_works_on_the_opponent(self):
        g = game(2, 'strateg', rich=True)
        g.sd[0].free['vypadek'] = 1
        g.act(0, {'t': 'card', 'id': 'vypadek'})
        self.assertGreater(g.sd[1].outage, 0)

    def test_end_rules(self):
        g = game(2, 'strateg')
        g.throne[0] = 0.0
        step(g)
        self.assertEqual((g.over['winner'], g.over['code']), (1, 'survive'))
        self.assertIn('vydržel déle', g.over['reason'])
        self.assertIn('B', g.over['reason'])
        g = game(2, 'strateg')
        g.throne[1] = 0.0
        step(g)
        self.assertEqual(g.over['winner'], 0)
        g = game(2, 'strateg')
        g.throne[0] = g.throne[1] = 0.0
        g.sd[1].stats['zk'] = 5
        step(g)
        self.assertEqual((g.over['winner'], g.over['code']), (1, 'survive'))
        g = game(2, 'strateg')
        g.throne[0] = g.throne[1] = 0.0
        step(g)
        self.assertEqual((g.over['winner'], g.over['code']), (-1, 'survive'))
        sv = g.end_info()['surv']
        self.assertEqual(sv['t'][0], sv['t'][1])

    def test_both_sides_get_snapshots(self):
        g = game(2, 'kral')
        run(g, 32)
        a, b = g.snapshot(0, [])['sv'], g.snapshot(1, [])['sv']
        self.assertEqual((a[0], a[1]), (b[0], b[1]))
        self.assertEqual((a[2], a[3]), (b[3], b[2]))


class TestWorld(unittest.TestCase):
    def test_eclipse_and_mist_schedule(self):
        g = game(1, 'strateg')
        r = g.rules
        self.assertEqual(r.eclipses[0], modes.wave_time(5))
        self.assertEqual(g.eclipse()[0], 1)

        def keep(g):
            g.throne[0] = 1e9
            for z in zombies(g):
                g.remove(z)
        run(g, modes.wave_time(5) + 5, keep)
        self.assertEqual(g.eclipse()[0], 2, 'darkness at once with wave 5')
        self.assertEqual(g.stage, 0)
        run(g, 30, keep)
        self.assertEqual(g.eclipse()[0], 1)
        run(g, modes.wave_time(10) + 1 - g.t, keep)
        self.assertEqual(g.stage, 1)
        run(g, modes.wave_time(20) + 1 - g.t, keep)
        self.assertEqual(g.stage, 2)
        run(g, modes.wave_time(30) + 1 - g.t, keep)
        self.assertEqual(g.stage, 3)
        run(g, modes.wave_time(40) + 1 - g.t, keep)
        self.assertEqual(g.stage, 3, 'the Mist stops at 3 columns')
        self.assertFalse(g.night, 'no Věčná noc')
        self.assertIsNone(g.over)

    def test_no_relic_no_alfa_timer(self):
        g = game(1, 'strateg')
        bad = []

        def keep(g):
            g.throne[0] = 1e9
            for z in zombies(g):
                if z.kind == 'alfa' and not getattr(z, 'wv', 0):
                    bad.append(z)                     # the Duel Alfa timer (300 s) must not run
                g.remove(z)
        run(g, 310, keep)
        self.assertFalse(g.relic['on'])
        self.assertEqual(bad, [])

    def test_deterministic(self):
        def hashes():
            g = game(2, 'kral', seed=7)
            out = []
            for i in range(3):
                run(g, 60)
                out.append(g.state_hash())
            return out
        self.assertEqual(hashes(), hashes())

    def test_make_rules_dispatch(self):
        r = modes.make_rules('preziti', {'players': 2})
        self.assertIsInstance(r, modes.SurvivalRules)
        self.assertEqual((r.players, r.play, r.relic, r.checkmate, r.night), (2, 'preziti', False, False, False))
        self.assertEqual(modes.make_rules('preziti', {}).players, 1)

    def test_build_game_solo_and_vs_ai(self):
        from hmk import session
        opts = {'type': 'preziti', 'mode': 'kral', 'map': 'predmesti', 'ai': None, 'fac': 'bez', 'deck': list(DECK), 'puzzle': None}
        g, ais = session.build_game('preziti', opts, [('A', list(DECK), 'bez'), None], seed=5)
        self.assertEqual((g.play, g.rules.players), ('preziti', 1))
        self.assertEqual(ais, [None, None])
        g2, _ = session.build_game('preziti', dict(opts, ai='lehka'), [('A', list(DECK), 'bez'), None], seed=5)
        self.assertEqual(g2.rules.players, 2)


if __name__ == '__main__':
    unittest.main()
