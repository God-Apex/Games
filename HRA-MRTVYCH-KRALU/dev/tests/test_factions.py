"""M3-A: factions on the server (FAC 2-5, SPEC 5.3) and the 1.0 global rules (SPEC 2.3).

Price table, HP rules, thorns, EMP, raises and OWNED_CAP, owned zombies vs their owner, noloot, every perk and command
variant, faction cards, limits, snapshot/start/end fields and the defs catalogue.
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
from hmk import defs as D  # noqa: E402
from hmk import factions as F  # noqa: E402
from hmk.defs import W, H, TICK, DEFS  # noqa: E402
from hmk.maps import bfs  # noqa: E402

DECK = ['navnada', 'kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec']
FDECK = {
    'bez': DECK,
    'prez': ['kulomet', 'plamen', 'sniper', 'hlaska', 'ostnata', 'dilna', 'pesak', 'mrchozrout'],
    'korp': ['kulomet', 'sniper', 'hlaska', 'tesla', 'hangar', 'exo', 'emp', 'dron'],
    'kult': ['kulomet', 'plamen', 'sniper', 'hlaska', 'hnizdo', 'pesak', 'nekromant', 'mor'],
}
SHARED = ['kulomet', 'plamen', 'hlaska', 'tesla', 'mina', 'rusicka', 'pesak', 'jezdec', 'obrnenec', 'strelec',
          'medik', 'saboter', 'dama']
PRICES = {   # FAC 2 price table (energy; zed = scrap)
    'bez': [50, 75, 40, 110, 40, 60, 30, 70, 110, 60, 55, 70, 200],
    'kult': [50, 75, 40, 110, 40, 60, 30, 70, 110, 60, 55, 70, 200],
    'prez': [40, 60, 30, 90, 30, 50, 35, 75, 120, 65, 60, 75, 220],
    'korp': [55, 85, 45, 120, 45, 65, 35, 75, 120, 65, 60, 75, 220],
}
SNIPER = {'bez': [100, 100, 140, 180], 'kult': [100, 100, 140, 180], 'prez': [100, 100, 140, 180], 'korp': [110, 110, 155, 200]}
ZED = {'bez': 15, 'kult': 15, 'prez': 10, 'korp': 15}


def game(facs=('bez', 'bez'), mode='strateg', compat05=False, seed=1):
    """A quiet game on an open board (no rubble), no waves/crates/Alfa, rich players."""
    g = S.Game(['A', 'B'], [list(FDECK[facs[0]]), list(FDECK[facs[1]])], mode, seed=seed, facs=facs, compat05=compat05)
    g.next_crate = g.next_alfa = g.next_wave = 1e9
    g.ter = [['.'] * W for _ in range(H)]
    g.dist = [bfs(g.ter, 0), bfs(g.ter, W - 1)]
    for sd in g.sd:
        sd.e, sd.s, sd.v = 5000.0, 500.0, 20
    return g


def run(g, secs):
    for _ in range(int(round(secs / TICK))):
        g.step(TICK)
        g.fx, g.msgs, g.evs, g.pfx = [], [[], []], [[], []], [[], []]


def zombie(g, x, y, own=-1, tgt=0, kind='chodec'):
    z = g.spawn(kind, 2, x, y)
    z.tgt = tgt
    if own >= 0:
        g.set_own(z, own)
    return z


def texts(g, s):
    return [t for t, _ in g.msgs[s]]


class TestPrices(unittest.TestCase):
    def test_price_table(self):
        for fac in F.FAC_IDS:
            g = game((fac, 'bez'))
            got = [g.price(0, k)[0] for k in SHARED]
            self.assertEqual(got, PRICES[fac], fac)
            self.assertEqual(g.price(0, 'zed'), [0, ZED[fac]], fac)
            self.assertEqual(g.price(0, 'gen')[0], 50, fac)
            sn = []
            for i in range(4):
                sn.append(g.price(0, 'sniper')[0])
                g.spawn('sniper', 0, i, 0)
            self.assertEqual(sn, SNIPER[fac], fac)

    def test_faction_cards_and_abilities(self):
        g = game(('korp', 'prez'))
        self.assertEqual(g.price(0, 'hangar'), [130, 0])
        self.assertEqual(g.price(0, 'exo'), [160, 0])
        self.assertEqual(g.price(0, 'dron'), [30, 0])
        self.assertEqual(g.price(0, 'nalet'), [120, 0])
        self.assertEqual(g.price(1, 'ostnata'), [0, 20])
        self.assertEqual(g.price(1, 'dron'), [40, 0])
        self.assertEqual(g.need_doba(0, 'tesla'), 1)
        self.assertEqual(g.need_doba(1, 'tesla'), 2)

    def test_pools_and_decks(self):
        self.assertNotIn('hangar', D.CARD_POOL)
        self.assertNotIn('emp', D.ABILITIES)
        self.assertEqual(len(F.pool_of('kult')), len(D.CARD_POOL) + 3)
        for fac in F.FAC_IDS:
            self.assertEqual(D.valid_deck(F.RECOMMENDED_F[fac], fac), F.RECOMMENDED_F[fac])
        self.assertIsNone(D.valid_deck(F.RECOMMENDED_F['kult'], 'prez'))
        self.assertIsNone(D.valid_deck(F.RECOMMENDED_F['prez'], 'bez'))
        self.assertTrue(all(DEFS[k]['up'] for k in ('dilna', 'hangar', 'hnizdo')))
        self.assertEqual(DEFS['ostnata']['up'], [[0, 25], [0, 45]])


class TestHP(unittest.TestCase):
    def test_hp_rules(self):
        g = game(('prez', 'kult'))
        self.assertAlmostEqual(g.spawn('zed', 0, 1, 1).maxhp, 350 * 1.4)
        self.assertAlmostEqual(g.spawn('ostnata', 0, 1, 2).maxhp, 450)
        self.assertAlmostEqual(g.spawn('kulomet', 0, 1, 3).maxhp, 220)
        self.assertAlmostEqual(g.spawn('kulomet', 1, 14, 3).maxhp, 220 * 0.8)
        self.assertAlmostEqual(g.spawn('hnizdo', 1, 14, 4).maxhp, 200)
        self.assertAlmostEqual(g.spawn('zed', 1, 14, 5).maxhp, 350 * 0.8)
        self.assertEqual(g.throne, [float(D.THRONE_HP)] * 2)
        w = g.spawn('ostnata', 0, 1, 6)
        g.sd[0].e = g.sd[0].s = 999
        g.upgrade(0, w, None)
        self.assertEqual((w.lvl, w.maxhp), (2, 1000.0))


class TestMechanics(unittest.TestCase):
    def test_thorns_35(self):
        g = game(('prez', 'bez'))
        w = g.spawn('ostnata', 0, 4, 4)
        u = g.spawn('obrnenec', 1, 5, 4)
        hp0 = u.hp
        g.damage(w, 40, 1, 'obrnenec', u)                 # melee: 40 x bld 2.5 = 100 dealt
        self.assertAlmostEqual(w.maxhp - w.hp, 100)
        self.assertAlmostEqual(hp0 - u.hp, 35)
        hp1 = u.hp
        g.damage(w, 40, 1, None, u, ranged=True)          # ranged: no thorns
        self.assertAlmostEqual(u.hp, hp1)

    def test_emp(self):
        g = game(('korp', 'bez'))
        t = g.spawn('kulomet', 1, 11, 4)
        u = g.spawn('pesak', 1, 12, 5)
        far = g.spawn('kulomet', 1, 13, 4)
        z = zombie(g, 10, 3)
        g.vis[0][4][11] = True
        g.act(0, {'t': 'card', 'id': 'emp', 'x': 11, 'y': 4})
        self.assertEqual((t.off, far.off), (4.0, 0.0))
        self.assertEqual((u.stun, z.stun), (1.5, 1.5))
        self.assertEqual(g.sd[0].cd['emp'], 50)
        snap = g.snapshot(1, [])
        self.assertTrue(next(e for e in snap['en'] if e[0] == t.id)[9] & 8192)
        run(g, 3.5)
        self.assertGreater(t.off, 0)
        run(g, 0.6)
        self.assertEqual(t.off, 0.0)

    def test_tower_off_does_not_fire(self):
        g = game(('korp', 'bez'))
        t = g.spawn('kulomet', 1, 11, 4)
        foe = g.spawn('pesak', 0, 9, 4)
        foe.hp = foe.maxhp = 1e6
        t.off = 2.0
        g.vis[1] = [[True] * W for _ in range(H)]
        g.tower(t, TICK)
        self.assertEqual(foe.hp, 1e6)
        t.off = 0
        t.cd = 0
        g.vis[1] = [[True] * W for _ in range(H)]
        g.tower(t, TICK)
        self.assertLess(foe.hp, 1e6)

    def test_owned_zombies_never_hit_owner(self):
        g = game(('kult', 'bez'), mode='kral')
        z = zombie(g, 3, 4, own=0, tgt=1)
        self.assertIsNone(g.target_at(z, 2, 4))
        u = g.spawn('pesak', 0, 2, 4)
        b = g.spawn('kulomet', 0, 3, 5)
        self.assertIsNone(g.target_at(z, 2, 4))
        self.assertIsNone(g.target_at(z, 3, 5))
        self.assertIsNone(g.target_at(z, -1, 4))                  # own throne
        self.assertEqual(g.target_at(z, W, 4), 1)
        self.assertIsNone(g.target_at(u, 3, 4))                   # owner's unit ignores it
        g.vis[0] = [[True] * W for _ in range(H)]
        self.assertNotIn(z, g.foes_in(b, 100))
        z2 = zombie(g, 4, 4, tgt=0)                                # an unowned zombie is fair game
        self.assertIn(z2, g.foes_in(b, 100))
        g.ents.pop(z2.id)
        g.mob[4][4] = None
        z.cx = z.cy = 0
        g.mob[4][3] = None
        z.x, z.y, z.cx, z.cy = 0.0, 4.0, 0, 4
        g.mob[4][0] = z
        hp = (u.hp, b.hp, g.throne[0], z.hp)
        run(g, 3)
        self.assertEqual((u.hp, b.hp, g.throne[0]), hp[:3])
        self.assertEqual(z.hp, hp[3])                              # throne gun and King leave it alone

    def test_tlupa_owned_and_cap(self):
        g = game()
        g.act(0, {'t': 'horde'})
        zs = [e for e in g.ents.values() if e.cat == 'z']
        self.assertEqual(len(zs), 5)
        self.assertTrue(all(z.own == 0 and z.tgt == 1 for z in zs))
        g2 = game(compat05=True)
        g2.act(0, {'t': 'horde'})
        self.assertTrue(all(z.own == -1 for z in g2.ents.values() if z.cat == 'z'))
        g3 = game(('kult', 'bez'))
        for i in range(F.OWNED_CAP):
            zombie(g3, 6 + i % 4, i // 4, own=0, tgt=1)
        self.assertEqual(g3.owned_n(0), F.OWNED_CAP)
        u = g3.spawn('pesak', 1, 10, 8)
        self.assertIsNone(g3.raise_dead(u, 0))
        self.assertEqual(g3.spawn_zombies(['chodec'], (14, 15), 1, own=0), 0)
        g3.sd[0].horde_cd = 0
        n_before = len(g3.ents)
        g3.act(0, {'t': 'horde'})
        self.assertEqual(len(g3.ents), n_before)

    def test_noloot_and_zloot(self):
        g = game(('kult', 'prez'))
        z = zombie(g, 12, 4, own=0, tgt=1)
        e0, s0 = g.sd[1].e, g.sd[1].s
        g.damage(z, 999, 1)
        self.assertEqual((g.sd[1].e, g.sd[1].s), (e0, s0))
        self.assertEqual(g.sd[1].stats['zk'], 1)
        m = g.spawn('mrchozrout', 1, 12, 5)
        z2 = zombie(g, 11, 5)
        e0, s0 = g.sd[1].e, g.sd[1].s
        g.damage(z2, 999, 1, 'mrchozrout', m)
        self.assertEqual((g.sd[1].e - e0, g.sd[1].s - s0), (6, 8))

    def test_raise_nekromant_and_mor(self):
        g = game(('kult', 'bez'))
        nk = g.spawn('nekromant', 0, 5, 4)
        u = g.spawn('pesak', 1, 7, 4)
        g.damage(u, 999, 0)
        z = g.mob[4][7]
        self.assertIsNotNone(z)
        self.assertEqual((z.kind, z.own, z.tgt), ('chodec', 0, 1))
        self.assertEqual(nk.rcd, 3.0)
        u2 = g.spawn('pesak', 1, 6, 5)
        g.damage(u2, 999, 0)
        self.assertIsNone(g.mob[5][6])                              # cooldown
        g2 = game(('kult', 'bez'))
        foe = g2.spawn('pesak', 1, 10, 4)
        foe.hp = 15
        g2.vis[0][4][10] = True
        g2.act(0, {'t': 'card', 'id': 'mor', 'x': 10, 'y': 4})
        self.assertEqual(len(g2.clouds), 1)
        run(g2, 2)
        z = g2.mob[4][10]
        self.assertTrue(z is not None and z.own == 0 and z.kind == 'chodec')
        self.assertIn([10, 4, 6.0, 0], g2.snapshot(0, [])['mc'])
        run(g2, 6.1)
        self.assertEqual(g2.clouds, [])

    def test_hnizdo(self):
        g = game(('kult', 'bez'))
        n = g.spawn('hnizdo', 0, 3, 4)
        run(g, 15.05)
        zs = [e for e in g.ents.values() if e.cat == 'z']
        self.assertEqual(len(zs), 1)
        self.assertEqual((zs[0].own, zs[0].tgt), (0, 1))
        self.assertEqual(n.hn, 1)
        n.off = 20
        run(g, 15)
        self.assertEqual(n.hn, 1)

    def test_dilna_scrap_and_limits(self):
        g = game(('prez', 'bez'))
        s0 = g.sd[0].s
        g.act(0, {'t': 'build', 'kind': 'dilna', 'x': 1, 'y': 1})
        g.act(0, {'t': 'build', 'kind': 'dilna', 'x': 1, 'y': 3})
        g.act(0, {'t': 'build', 'kind': 'dilna', 'x': 1, 'y': 5})
        self.assertEqual(g.count(0, 'dilna'), 2)
        self.assertIn('Dílna smíš mít nejvýš 2.', texts(g, 0))
        self.assertEqual(g.snapshot(0, [])['sinc'], 1.2)
        g.msgs = [[], []]
        run(g, 10)
        self.assertAlmostEqual(g.sd[0].s - s0, 12, places=4)
        self.assertNotIn('sinc', g.snapshot(1, []))

    def test_mrchozrout_crate(self):
        g = game(('prez', 'bez'))
        g.drop_crate(7, 4, 0, land=0.0)
        m = g.spawn('mrchozrout', 0, 7, 4)
        m.stun = 99

        self.assertEqual(g.at_crate(next(iter(g.crates.values()))), {0: 2.0})
        run(g, 1.55)
        self.assertEqual(g.crates, {})
        self.assertEqual(g.sd[0].stats['crates'], 1)
        self.assertEqual(m.kind, 'mrchozrout')

    def test_exo_shield_and_limit(self):
        g = game(('korp', 'bez'))
        g.sd[0].techs = {'ing1', 'arm1'}
        for y in (1, 3, 5, 7):
            g.act(0, {'t': 'unit', 'kind': 'exo', 'x': 5, 'y': y})
        self.assertEqual(g.count(0, 'exo'), 3)
        ex = next(e for e in g.ents.values() if e.kind == 'exo')
        g.damage(ex, 100, 1)
        self.assertEqual((ex.sh, ex.hp), (20, ex.maxhp))
        g.damage(ex, 50, 1)
        self.assertEqual((ex.sh, ex.hp), (0, ex.maxhp - 30))
        snap = g.snapshot(0, [])
        self.assertFalse(next(e for e in snap['en'] if e[0] == ex.id)[9] & 16)
        ex.stun = 99
        run(g, 3.0 + 2.0)
        self.assertGreater(ex.sh, 0)
        self.assertTrue(next(e for e in g.snapshot(0, [])['en'] if e[0] == ex.id)[9] & 16)

    def test_hangar(self):
        g = game(('korp', 'bez'))
        h = g.spawn('hangar', 0, 4, 4)
        foe = g.spawn('pesak', 1, 7, 4)
        foe.hp = foe.maxhp = 1e6
        h.path, h.lvl = 'B', 3
        g.vis[0] = [[True] * W for _ in range(H)]
        h.cd = 0
        fx0 = len(g.fx)
        g.tower(h, TICK)
        self.assertEqual(g.fx[fx0][0], 'H')
        self.assertEqual((foe.slow_t, foe.slowk), (1.5, 0.4))
        self.assertAlmostEqual(1e6 - foe.hp, 15 * D.LVL_MULT[2])

    def test_korp_research_and_tesla(self):
        g = game(('korp', 'bez'))
        g.sd[0].v = 1
        g.act(0, {'t': 'res', 'id': 'ing1'})
        self.assertIn('ing1', g.sd[0].techs)
        g.act(0, {'t': 'build', 'kind': 'tesla', 'x': 2, 'y': 2})
        self.assertEqual(g.count(0, 'tesla'), 1)


class TestGlobalRules(unittest.TestCase):
    def test_utok_needs_doba2(self):
        g = game()
        g.act(0, {'t': 'cmd', 'id': 'utok'})
        self.assertEqual(g.sd[0].cry_t, 0)
        self.assertIn('Útok! vyžaduje Dobu II.', texts(g, 0))
        g.sd[0].techs = {'ing1', 'arm1'}
        g.act(0, {'t': 'cmd', 'id': 'utok'})
        self.assertEqual(g.sd[0].cry_t, 6)
        g5 = game(compat05=True)
        g5.act(0, {'t': 'cmd', 'id': 'utok'})
        self.assertEqual(g5.sd[0].cry_t, 6)


class TestPerksAndCommands(unittest.TestCase):
    def test_kovar(self):
        g = game(('prez', 'bez'), mode='kral')
        k = g.sd[0].kral
        b = g.spawn('kulomet', 0, 1, 4)
        b.hp = 50
        s0 = g.sd[0].s
        g.act(0, {'t': 'in', 'r': True})
        run(g, 1.0)
        self.assertAlmostEqual(b.hp - 50, 80, delta=2)
        self.assertAlmostEqual((s0 - g.sd[0].s) * 20, b.hp - 50, places=4)
        self.assertIsNotNone(k)

    def test_tesla_glove(self):
        g = game(('korp', 'bez'), mode='kral')
        k = g.sd[0].kral
        foes = [g.spawn('pesak', 1, 3, y) for y in (4, 5, 6, 7)]
        for f in foes:
            f.hp = f.maxhp = 1e6
        g.vis[0] = [[True] * W for _ in range(H)]
        g.sd[1].kral = None
        for _ in range(3):
            k.cd = 0
            g.vis[0] = [[True] * W for _ in range(H)]
            g.kral_tick(k, TICK)
        self.assertEqual(k.shots, 3)
        zs = [f for f in g.fx if f[0] == 'z']
        self.assertEqual(len(zs), 3)
        self.assertEqual(sum(1 for f in foes if f.hp < 1e6), 4)

    def test_pan_mrtvych(self):
        g = game(('kult', 'bez'), mode='kral')
        k = g.sd[0].kral
        k.x, k.y, k.cx, k.cy = 5.0, 4.0, 5, 4
        zs = [zombie(g, 6, y, tgt=0) for y in (2, 3, 5, 6)] + [zombie(g, 6, 4, tgt=0, kind='alfa')]
        far = zombie(g, 12, 4, tgt=0)
        g.sd[0].ult = 100
        g.act(0, {'t': 'in', 'u': True})
        self.assertTrue(all(z.own == 0 and z.tgt == 1 for z in zs[:4]))
        self.assertEqual((zs[4].own, far.own), (-1, -1))
        self.assertIn(['turn', 0, 4], g.evs[0])
        self.assertEqual(sum(1 for f in g.fx if f[0] == 'W'), 4)
        z = zs[0]
        z.hp = 10
        g.damage(z, 1, 1, 'chodec', g.sd[1].kral)
        self.assertGreater(z.hp, 0)

    def test_zdmg_in(self):
        g = game(('kult', 'bez'))
        u = g.spawn('pesak', 0, 3, 3)
        u1 = g.spawn('pesak', 1, 12, 3)
        z = zombie(g, 4, 3)
        g.damage(u, 10, 2, 'chodec', z)
        g.damage(u1, 10, 2, 'chodec', z)
        self.assertAlmostEqual(u.maxhp - u.hp, 5)
        self.assertAlmostEqual(u1.maxhp - u1.hp, 10)

    def test_svepomoc(self):
        g = game(('prez', 'bez'))
        a, b, c = g.spawn('kulomet', 0, 2, 4), g.spawn('kulomet', 0, 3, 5), g.spawn('kulomet', 0, 5, 4)
        for e in (a, b, c):
            e.hp = 10
        g.act(0, {'t': 'cmd', 'id': 'oprava', 'x': 2, 'y': 4})
        self.assertAlmostEqual(a.hp, 10 + 0.4 * a.maxhp)
        self.assertAlmostEqual(b.hp, 10 + 0.2 * b.maxhp)
        self.assertEqual(c.hp, 10)

    def test_dronova_letka(self):
        g = game(('korp', 'bez'))
        g.drop_crate(7, 4, 0, land=0.0)
        g.act(0, {'t': 'cmd', 'id': 'sber', 'x': 7, 'y': 4})
        self.assertEqual(g.sd[0].cd['cmd_sber'], 15)
        d = g.drones[0]
        self.assertEqual((d['v'], d['sc']), (6.0, 2.0))
        x0 = d['x']
        g.step(TICK)
        dist = ((g.drones[0]['x'] - x0) ** 2 + (g.drones[0]['y'] - H // 2) ** 2) ** 0.5
        self.assertAlmostEqual(dist, 6.0 * TICK, places=4)
        dx, dy = int(round(g.drones[0]['x'])), int(round(g.drones[0]['y']))
        self.assertTrue(g.vis[0][dy][min(W - 1, dx + 2)] or dx + 2 >= W)

    def test_volani_mrtvych(self):
        g = game(('kult', 'bez'))
        g.sd[0].techs = {'ing1', 'arm1'}
        mist_z = [zombie(g, 7, y, tgt=0) for y in (1, 2, 3)]
        other = zombie(g, 8, 6, tgt=1)
        home = zombie(g, 2, 4, tgt=0)
        g.act(0, {'t': 'cmd', 'id': 'utok'})
        self.assertEqual(g.sd[0].cry_t, 6)
        self.assertTrue(all(z.own == 0 and z.tgt == 1 for z in mist_z))
        self.assertEqual((other.own, home.own), (-1, -1))
        self.assertIn(['turn', 0, 3], g.evs[0])


class TestMessages(unittest.TestCase):
    def test_start_end_defs(self):
        g = game(('korp', 'kult'), mode='kral')
        st = g.start_info(0)
        self.assertEqual(st['fac'], ['korp', 'kult'])
        self.assertEqual(st['costs']['kulomet'], [55, 0])
        self.assertEqual(st['costs']['hangar'], [130, 0])
        self.assertEqual(st['rcost']['ing1'], 1)
        self.assertEqual(st['cmds']['sber']['name'], 'Dronová letka')
        self.assertEqual(st['cmds']['utok']['doba'], 2)
        self.assertEqual(st['perk']['name'], 'Tesla-rukavice')
        st1 = g.start_info(1)
        self.assertEqual(st1['horde'], [80, 18.0])
        self.assertEqual(st1['perk']['name'], 'Pán mrtvých')
        self.assertIsNone(game(mode='strateg').start_info(0)['perk'])
        self.assertEqual(game(compat05=True).start_info(0)['cmds']['utok']['doba'], 1)
        g.over = {'winner': 0, 'reason': '', 'code': 'throne'}
        self.assertEqual(g.end_info()['fac'], ['korp', 'kult'])
        p = F.public()
        self.assertEqual(set(p), {'factions', 'facPool', 'facCosts', 'facRec'})
        self.assertEqual(p['factions']['kult']['cmdv']['utok']['name'], 'Volání mrtvých')
        self.assertEqual(p['facCosts']['prez']['zed'], [0, 10])
        self.assertEqual(p['facRec']['korp'], F.RECOMMENDED_F['korp'])

    def test_owned_flags(self):
        g = game(('kult', 'bez'))
        z = zombie(g, 3, 4, own=1, tgt=0)
        snap = g.snapshot(0, [])
        fl = next(e for e in snap['en'] if e[0] == z.id)[9]
        self.assertEqual(fl & (2048 | 4096), 2048 | 4096)

    def test_hangar_fx_endpoint_visible(self):
        g = game(('korp', 'bez'))
        g.vis[1] = [[False] * W for _ in range(H)]
        g.vis[1][4][10] = True
        self.assertEqual(len(g.visible_fx(1, [['H', 2, 4, 10, 4, 0]])), 1)

    def test_bez_game_runs_and_faction_game_runs(self):
        for facs in (('prez', 'korp'), ('kult', 'prez')):
            for mode in ('kral', 'strateg'):
                g = S.Game(['A', 'B'], [list(F.RECOMMENDED_F[facs[0]]), list(F.RECOMMENDED_F[facs[1]])], mode, seed=3, facs=facs)
                g.next_wave = 5.0
                for sd in g.sd:
                    sd.e = 3000.0
                    sd.v = 10
                for s in (0, 1):
                    for i, k in enumerate(g.sd[s].deck):
                        x = 4 - i % 3 if s == 0 else 11 + i % 3
                        if DEFS[k]['cat'] == 'b':
                            g.act(s, {'t': 'build', 'kind': k, 'x': x, 'y': i})
                        elif DEFS[k]['cat'] == 'u':
                            g.act(s, {'t': 'unit', 'kind': k, 'x': x, 'y': i})
                    g.act(s, {'t': 'horde'})
                for _ in range(int(30 / TICK)):
                    g.step(TICK)
                    g.snapshot(0, g.fx)
                    g.snapshot(1, g.fx)
                    g.fx = []


if __name__ == '__main__':
    unittest.main()
