"""M2-A: relic squad (SPEC 4.4): refusals, composition, deployment timing, cells, payment, cooldown, snapshot 'sq'.

Needs the 1.0 package (skipped on the frozen 0.5 server)."""
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('needs the 1.0 hmk package')
from hmk.defs import W, H, TICK, DEFS  # noqa: E402

DECK = ['navnada', 'kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec']
M_OFF = 'Relikvie ještě není aktivní.'
M_NOUNIT = 'V balíčku nemáš jednotky.'
M_ENERGY = 'Na člena čety nemáš energii.'


def game(deck=None, mode='strateg', relic=True, seed=1):
    g = S.Game(['A', 'B'], [list(deck or DECK), list(DECK)], mode, seed=seed)
    g.next_crate = g.next_alfa = g.next_wave = 1e9
    for sd in g.sd:
        sd.e, sd.s = 5000.0, 500.0
    g.relic['on'] = relic
    return g


def run(g, secs):
    for _ in range(int(round(secs / TICK))):
        g.step(TICK)
        g.fx, g.evs, g.pfx = [], [[], []], [[], []]


def texts(g, s):
    return [t for t, _ in g.msgs[s]]


def mine(g, s=0):
    return sorted(e.kind for e in g.ents.values() if e.side == s and e.cat == 'u')


def squad(g, s=0):
    g.act(s, {'t': 'squad', 'id': 'relic'})


class TestRefusals(unittest.TestCase):
    def test_relic_not_active(self):
        g = game(relic=False)
        squad(g)
        self.assertIn(M_OFF, texts(g, 0))
        self.assertFalse(g.pending)
        self.assertNotIn('squad', g.sd[0].cd)

    def test_no_unit_card(self):
        g = game(deck=['navnada', 'kulomet', 'plamen', 'sniper', 'hlaska', 'dron'])
        squad(g)
        self.assertIn(M_NOUNIT, texts(g, 0))
        self.assertFalse(g.pending)
        self.assertNotIn('squad', g.sd[0].cd)

    def test_only_strateg_mode(self):
        g = game(mode='kral')
        squad(g)
        self.assertFalse(g.pending)
        self.assertNotIn('squad', g.sd[0].cd)
        self.assertNotIn('sq', g.snapshot(0, []))

    def test_wrong_id_or_junk_is_ignored(self):
        g = game()
        for m in ({'t': 'squad'}, {'t': 'squad', 'id': 'x'}, {'t': 'squad', 'id': 5}, {'t': 'squad', 'id': None}):
            g.act(0, m)
        self.assertFalse(g.pending)
        self.assertEqual(texts(g, 0), [])

    def test_no_energy_for_cheapest_member(self):
        g = game()
        g.sd[0].e = 29.0                      # cheapest of the kit is Pěšák, 30
        squad(g)
        self.assertIn(M_ENERGY, texts(g, 0))
        self.assertFalse(g.pending)
        self.assertNotIn('squad', g.sd[0].cd)

    def test_refusal_does_not_touch_other_side(self):
        g = game(relic=False)
        squad(g, 0)
        self.assertEqual(texts(g, 1), [])


class TestComposition(unittest.TestCase):
    def kinds(self, deck):
        g = game(deck=deck)
        squad(g)
        return [p[2] for p in sorted(g.pending, key=lambda p: p[0])]

    def test_obrnenec_plus_two_pesak(self):
        self.assertEqual(self.kinds(DECK), ['obrnenec', 'pesak', 'pesak'])

    def test_three_cheapest_units_without_the_pair(self):
        # no Obrněnec: Pěšák 30, Střelec 60, Medik 55 -> 3 cheapest = Pěšák, Medik, Střelec? (order by price)
        g = game(deck=['pesak', 'jezdec', 'strelec', 'medik', 'kulomet'])
        squad(g)
        kinds = [p[2] for p in sorted(g.pending, key=lambda p: p[0])]
        prices = [DEFS[k]['cost'][0] for k in kinds]
        self.assertEqual(kinds, ['pesak', 'medik', 'strelec'])
        self.assertEqual(prices, sorted(prices))

    def test_obrnenec_without_pesak_uses_cheapest(self):
        self.assertEqual(self.kinds(['obrnenec', 'jezdec', 'strelec', 'kulomet']), ['strelec', 'jezdec', 'obrnenec'])

    def test_price_tie_broken_by_defs_order(self):
        # jezdec 70 and saboter 70: DEFS order decides (jezdec comes first)
        order = list(DEFS)
        self.assertLess(order.index('jezdec'), order.index('saboter'))
        self.assertEqual(self.kinds(['saboter', 'jezdec', 'strelec', 'pesak']), ['pesak', 'strelec', 'jezdec'])

    def test_fewer_than_three_cards_repeat_the_cheapest(self):
        self.assertEqual(self.kinds(['jezdec', 'kulomet']), ['jezdec', 'jezdec', 'jezdec'])
        self.assertEqual(self.kinds(['strelec', 'pesak']), ['pesak', 'strelec', 'pesak'])

    def test_unit_locked_by_doba_is_not_used(self):
        # Hlídka needs Doba II; at Doba I the squad takes the other cards
        g = game(deck=['dama', 'jezdec'])
        self.assertEqual(g.sd[0].doba, 1)
        squad(g)
        self.assertEqual([p[2] for p in g.pending], ['jezdec', 'jezdec', 'jezdec'])

    def test_only_locked_units_gives_message(self):
        g = game(deck=['dama', 'kulomet'])
        squad(g)
        self.assertFalse(g.pending)
        self.assertEqual(len(texts(g, 0)), 1)
        self.assertNotEqual(texts(g, 0)[0], M_NOUNIT)


class TestDeployment(unittest.TestCase):
    def test_pending_times_and_rows(self):
        g = game()
        t0 = g.t
        squad(g)
        self.assertEqual([round(p[0] - t0, 3) for p in g.pending], [0.0, 4.0, 5.0])
        self.assertEqual([p[3] for p in g.pending], [4, 4, 3])
        self.assertEqual([p[1] for p in g.pending], [0, 0, 0])

    def test_members_appear_at_0_4_5_seconds(self):
        g = game()
        squad(g)
        self.assertEqual(mine(g), [])
        run(g, 0.2)
        self.assertEqual(mine(g), ['obrnenec'])
        run(g, 3.5)                           # t = 3.7
        self.assertEqual(mine(g), ['obrnenec'])
        run(g, 0.5)                           # t = 4.2
        self.assertEqual(mine(g), ['obrnenec', 'pesak'])
        run(g, 1.0)                           # t = 5.2
        self.assertEqual(mine(g), ['obrnenec', 'pesak', 'pesak'])
        self.assertFalse(g.pending)

    def test_each_member_pays_at_its_own_time(self):
        g = game()
        squad(g)
        e0 = g.sd[0].e
        self.assertEqual(g.sd[0].e, e0)       # nothing is paid by the order itself
        run(g, 0.2)
        self.assertAlmostEqual(g.sd[0].e, e0 - 110 + g.income(0) * 0.2, delta=3.0)
        self.assertEqual(g.sd[0].stats['units'], 1)
        run(g, 5.0)
        self.assertEqual(g.sd[0].stats['units'], 3)
        self.assertEqual(g.sd[0].stats['spent'], 110 + 30 + 30)

    def test_unaffordable_member_is_skipped_with_message(self):
        g = game()
        g.sd[0].e = 120.0                     # affords Obrněnec (110) at once, then too little for the next Pěšák
        squad(g)
        g.sd[0].e = 120.0
        run(g, 0.2)
        g.sd[0].e = 10.0                      # the two Pěšák (30 each) cannot be paid
        run(g, 5.2)
        self.assertEqual(mine(g), ['obrnenec'])
        self.assertEqual(texts(g, 0).count(M_ENERGY), 2)
        self.assertFalse(g.pending)

    def test_one_member_skipped_the_others_go(self):
        g = game()
        squad(g)
        run(g, 0.2)
        g.sd[0].e = 10.0
        run(g, 3.9)                           # t = 4.1: first Pěšák is skipped
        self.assertEqual(mine(g), ['obrnenec'])
        g.sd[0].e = 500.0
        run(g, 1.0)                           # t = 5.1: second Pěšák goes
        self.assertEqual(mine(g), ['obrnenec', 'pesak'])
        self.assertEqual(texts(g, 0).count(M_ENERGY), 1)

    def test_cells_front_column_rows_4_4_3(self):
        g = game()
        placed = []
        orig = g.deploy
        g.deploy = lambda s, kind, x, y: (placed.append((kind, x, y)), orig(s, kind, x, y))[1]
        front = max(x for x in range(W) if g.buildable(0, x))
        squad(g)
        run(g, 5.2)
        self.assertEqual([p[0] for p in placed], ['obrnenec', 'pesak', 'pesak'])
        self.assertEqual(placed[0][1:], (front, 4))
        # units walk away after deploy, so the front cell is free again: rows 4 / 4 / 3 resolve to 4, 4 or the nearest, 3
        self.assertEqual({p[1] for p in placed}, {front})
        self.assertEqual(placed[2][2], 3)
        self.assertIn(placed[1][2], (4, 3, 5))
        self.assertEqual(len(mine(g)), 3)

    def test_cell_nearest_free_row_when_target_row_is_taken(self):
        g = game()
        front = max(x for x in range(W) if g.buildable(0, x))
        g.spawn('pesak', 0, front, 4)
        cell = g.squad_cell(0, 4)
        self.assertEqual(cell[0], front)
        self.assertIn(cell[1], (3, 5))
        g.spawn('pesak', 0, front, 3)
        g.spawn('pesak', 0, front, 5)
        cell = g.squad_cell(0, 4)
        self.assertEqual(cell[0], front)
        self.assertIn(cell[1], (2, 6))

    def test_cell_skips_a_full_front_column(self):
        g = game()
        front = max(x for x in range(W) if g.buildable(0, x))
        for y in range(H):
            g.spawn('pesak', 0, front, y)
        cell = g.squad_cell(0, 4)
        self.assertIsNotNone(cell)
        self.assertLess(cell[0], front)
        self.assertTrue(g.buildable(0, cell[0]))

    def test_cell_can_use_a_free_own_building_cell(self):
        g = game()
        front = max(x for x in range(W) if g.buildable(0, x))
        g.build(0, 'kulomet', front, 4)
        self.assertEqual(g.bld[4][front].side, 0)
        cell = g.squad_cell(0, 4)
        self.assertEqual(cell, (front, 4))   # own building cells count as free for deploy()

    def test_no_room_message(self):
        g = game()
        for x in range(W):
            if g.buildable(0, x):
                for y in range(H):
                    if g.mob[y][x] is None:
                        g.spawn('pesak', 0, x, y)
        g.squad_member(0, 'pesak', 4)
        self.assertIn('Pro člena čety není místo.', texts(g, 0))

    def test_side_one_goes_to_its_own_half(self):
        g = game()
        squad(g, 1)
        front = min(x for x in range(W) if g.buildable(1, x))
        placed = []
        orig = g.deploy
        g.deploy = lambda s, kind, x, y: (placed.append((s, x, y)), orig(s, kind, x, y))[1]
        run(g, 5.2)
        ents = [e for e in g.ents.values() if e.side == 1 and e.cat == 'u']
        self.assertEqual(len(ents), 3)
        self.assertEqual(placed[0][:2], (1, front))
        self.assertEqual(mine(g, 0), [])


class TestCooldown(unittest.TestCase):
    def test_cooldown_20s_and_message(self):
        g = game()
        squad(g)
        self.assertAlmostEqual(g.sd[0].cd['squad'], 20.0)
        run(g, 6.0)
        n = len(g.ents)
        g.msgs = [[], []]
        squad(g)
        self.assertEqual(len(g.pending), 0)
        self.assertEqual(len(g.ents), n)
        self.assertEqual(len(texts(g, 0)), 1)
        self.assertIn('s', texts(g, 0)[0])

    def test_second_squad_after_cooldown(self):
        g = game()
        squad(g)
        run(g, 20.5)
        self.assertNotIn('squad', g.sd[0].cd)
        g.msgs = [[], []]
        squad(g)
        self.assertEqual(len(g.pending), 3)
        run(g, 5.2)
        self.assertEqual(g.sd[0].stats['units'], 6)

    def test_cooldown_is_per_side(self):
        g = game()
        squad(g, 0)
        squad(g, 1)
        self.assertEqual(len(g.pending), 6)
        self.assertIn('squad', g.sd[0].cd)
        self.assertIn('squad', g.sd[1].cd)


class TestSnapshot(unittest.TestCase):
    def test_sq_field(self):
        g = game()
        sq = g.snapshot(0, [])['sq']
        self.assertEqual(sq, [110 + 30 + 30, 0.0])
        squad(g)
        sq = g.snapshot(0, [])['sq']
        self.assertEqual(sq[0], 170)
        self.assertEqual(sq[1], 20.0)
        run(g, 3.0)
        self.assertAlmostEqual(g.snapshot(0, [])['sq'][1], 17.0, delta=0.15)

    def test_sq_absent_when_relic_off_or_no_kit(self):
        self.assertNotIn('sq', game(relic=False).snapshot(0, []))
        self.assertNotIn('sq', game(deck=['kulomet', 'plamen']).snapshot(0, []))

    def test_sq_is_json_serialisable(self):
        import json
        g = game()
        squad(g)
        json.dumps(g.snapshot(0, []))


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_hash(self):
        hs = []
        for _ in range(2):
            g = game(seed=7)
            squad(g)
            run(g, 12.0)
            squad(g, 1)
            run(g, 12.0)
            hs.append(g.state_hash())
        self.assertEqual(hs[0], hs[1])


if __name__ == '__main__':
    unittest.main()
