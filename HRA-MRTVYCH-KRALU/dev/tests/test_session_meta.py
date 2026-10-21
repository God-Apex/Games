"""Meta server wiring (M3-F): the stats Store behind Lobby/Session, `me`, `stats_q`, `cos`, `end.me/lv/ser`, defs catalogues.

A FakeClient drives Lobby.handle without sockets (as in test_lobby). Games are fast-forwarded with Session.simulate
(headless) and then ended through the real finish path, so the sessions record into a temp Store like in the server."""
import asyncio
import json
import math
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('test_session_meta needs the 1.0 hmk package')

from hmk import lobby as L, net, meta, session as SS  # noqa: E402


class FakeWriter:
    def __init__(self, i):
        self.i = i

    def get_extra_info(self, k):
        return ('10.0.1.%d' % self.i, 1234)

    def write(self, data):
        pass

    async def drain(self):
        pass

    def close(self):
        pass


class FakeClient(net.Client):
    def __init__(self, i, name):
        super().__init__(FakeWriter(i))
        self.name = name
        self.got = []

    def send(self, obj, droppable=False):
        json.dumps(obj, ensure_ascii=False, allow_nan=False)
        self.got.append(obj)

    def drop(self):
        self.alive = False

    def of(self, t):
        return [m for m in self.got if m.get('t') == t]


def mk_lobby(store):
    lb = L.Lobby(store=store)
    lb.ai_factory = SS.IdleAI
    return lb


def connect(lb, names):
    cs = []
    for i, n in enumerate(names):
        c = FakeClient(i, n)
        assert lb.join(c)
        lb.handle(c, json.dumps({'t': 'hello', 'name': n}))
        cs.append(c)
    return cs


def send(lb, c, **m):
    lb.handle(c, json.dumps(m))


def start_room(lb, a, b, mode='kral'):
    send(lb, a, t='cfg', type='souboj', mode=mode, map='ruiny')
    send(lb, a, t='ready', v=True, deck=None, fac='bez')
    send(lb, b, t='ready', v=True, deck=None, fac='bez')
    assert lb.room is not None
    return lb.room


async def until(cond, secs=3.0):
    for _ in range(int(secs / 0.05)):
        if cond():
            return True
        await asyncio.sleep(0.05)
    return cond()


def run(coro):
    return asyncio.run(coro)


def nser(t):
    """Samples of a series at game time t: t = 0, every 5 s, plus the final one in finish (float-safe, as the engine)."""
    return int(math.floor((t + 1e-6) / 5.0)) + 2


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'stats.json')
        self.store = meta.Store(self.path)
        self.store.load()
        self._delay = L.COS_SAVE_DELAY
        L.COS_SAVE_DELAY = 0.15

    def tearDown(self):
        L.COS_SAVE_DELAY = self._delay
        self.tmp.cleanup()


class TestDefs(unittest.TestCase):
    def test_catalogues_in_defs(self):
        m = net.DEFS_MSG
        json.dumps(m, ensure_ascii=False, allow_nan=False)
        self.assertEqual(sorted(m['factions']), ['bez', 'korp', 'kult', 'prez'])
        for k in ('facPool', 'facCosts', 'facRec'):
            self.assertEqual(sorted(m[k]), ['bez', 'korp', 'kult', 'prez'], k)
        for f, d in m['factions'].items():
            for k in ('name', 'motto', 'desc', 'passives', 'cards', 'perk', 'cmdv'):
                self.assertIn(k, d, f)
        self.assertEqual(len(m['cosm']), 13)
        self.assertEqual({c['slot'] for c in m['cosm']}, {'ban', 'kor', 'zab', 'vit'})
        self.assertEqual(len(m['ach']), 12)
        self.assertEqual(len(m['lvls']), 30)
        self.assertEqual(m['titles'][0][0], 1)
        for k in ('types', 'maps', 'puzzles', 'diffs', 'squad', 'soloMax'):
            self.assertIn(k, m)

    def test_open_store_no_stats_is_memory_only(self):
        st = net.open_store(None)
        self.assertIsNone(st.path)
        st.ensure('x', 'X')
        st.dirty = True
        self.assertTrue(st.save())
        self.assertFalse(st.dirty)

    def test_open_store_reads_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'stats.json')
            st = meta.Store(p)
            st.ensure('jarda', 'Jarda')
            st.dirty = True
            self.assertTrue(st.save())
            st2 = net.open_store(p)
            self.assertIn('jarda', st2.data['players'])


class TestMe(Base):
    def test_me_after_hello_and_on_name_change(self):
        async def body():
            lb = mk_lobby(self.store)
            c, = connect(lb, ['Jarda'])
            self.assertEqual(c.of('me'), [])                 # debounced
            self.assertTrue(await until(lambda: c.of('me')))
            prof = c.of('me')[-1]['prof']
            self.assertEqual((prof['key'], prof['name'], prof['lvl'], prof['xp']), ('jarda', 'Jarda', 1, 0))
            self.assertEqual(prof['cos'], meta.COS_DEFAULT)
            n = len(c.of('me'))
            send(lb, c, t='hello', name='Petr')
            self.assertTrue(await until(lambda: len(c.of('me')) > n))
            self.assertEqual(c.of('me')[-1]['prof']['key'], 'petr')
            # the placeholder name and an empty name have no profile
            send(lb, c, t='hello', name='')
            n = len(c.of('me'))
            self.assertTrue(await until(lambda: len(c.of('me')) > n))
            self.assertIsNone(c.of('me')[-1]['prof'])
        run(body())

    def test_no_store_no_profile(self):
        async def body():
            lb = mk_lobby(None)
            c, = connect(lb, ['Jarda'])
            self.assertTrue(await until(lambda: c.of('me')))
            self.assertIsNone(c.of('me')[-1]['prof'])
            send(lb, c, t='stats_q', who=None)
            st = c.of('stats')[-1]
            self.assertEqual((st['prof'], st['hist'], st['hof'], st['h2h']), (None, [], [], {}))
        run(body())

    def test_lobby_players_carry_level_title_cos(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Jarda', 'Král'])
            pl = a.of('lobby')[-1]['players']
            self.assertEqual((pl[0]['lv'], pl[0]['ttl']), (1, meta.title(1)))
            self.assertEqual(pl[0]['cos'], {'ban': 'rod', 'kor': 'zlata'})
            self.assertEqual((pl[1]['lv'], pl[1]['ttl']), (None, None))       # no profile
            self.assertEqual(pl[1]['cos'], {'ban': 'rod', 'kor': 'zlata'})
            p = self.store.ensure('jarda', 'Jarda')
            p['xp'] = meta.need(7)
            lb.update()
            pl = a.of('lobby')[-1]['players']
            self.assertEqual(pl[0]['lv'], 7)
            self.assertEqual(pl[0]['ttl'], meta.title(7))
        run(body())


class TestDuplicateName(Base):
    def test_same_key_cannot_ready(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Jarda', '  jarda '])
            send(lb, a, t='ready', v=True, deck=None, fac='bez')
            send(lb, b, t='ready', v=True, deck=None, fac='bez')
            err = b.of('lerr')
            self.assertEqual(len(err), 1)
            self.assertIn('Oba máte jméno', err[0]['text'])
            self.assertEqual(len(a.of('lerr')), 1)           # both seats hold the same key, so neither can be ready
            self.assertFalse(a.ready or b.ready)
            self.assertIsNone(lb.room)
            send(lb, b, t='hello', name='Petr')
            send(lb, a, t='ready', v=True, deck=None, fac='bez')
            send(lb, b, t='ready', v=True, deck=None, fac='bez')
            self.assertIsNotNone(lb.room)
            lb.room.finish({'winner': -1, 'reason': 'test', 'code': 'error'})
        run(body())

    def test_two_placeholder_names_are_fine(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Král', ''])
            send(lb, a, t='ready', v=True, deck=None, fac='bez')
            send(lb, b, t='ready', v=True, deck=None, fac='bez')
            self.assertEqual(b.of('lerr'), [])
            self.assertIsNotNone(lb.room)
            lb.room.finish({'winner': -1, 'reason': 'test', 'code': 'error'})
        run(body())


class TestRecording(Base):
    def _end(self, c):
        e = c.of('end')
        self.assertTrue(e, 'no end message for %s' % c.name)
        return e[-1]

    def test_two_room_matches_and_one_vycvik_recorded(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b, c = connect(lb, ['Hrac0', 'Hrac1', 'Hrac2'])
            await until(lambda: all(x.of('me') for x in (a, b, c)))

            # match 1: b gives up after 70 s of game time
            r1 = start_room(lb, a, b)
            st = a.of('start')[-1]
            self.assertEqual(st['lv'], [[1, meta.title(1)]] * 2)
            self.assertEqual(st['cos'], [meta.COS_DEFAULT, meta.COS_DEFAULT])
            r1.simulate(70)
            t1 = r1.game.t
            send(lb, b, t='quit')
            self.assertTrue(r1.done)
            e = self._end(a)
            self.assertEqual(e['code'], 'quit')
            self.assertEqual(len(e['ser']['th'][0]), nser(t1))
            self.assertEqual(len(e['ser']['th'][1]), len(e['ser']['th'][0]))
            self.assertEqual(e['lv'], [[1, meta.title(1)], [1, meta.title(1)]])
            self.assertEqual(self._end(b)['ser'], e['ser'])
            self.assertGreater(e['me']['xp'], 0)
            self.assertEqual(sorted(e['me']), sorted(['xp_parts', 'xp', 'lvl', 'cur', 'next', 'lvlup', 'new_ach',
                                                      'new_cos', 'elo']))
            self.assertIsInstance(e['rec_new'], list)
            self.assertEqual(len(self.store.data['matches']), 1)
            self.assertTrue(os.path.exists(self.path), 'stats are written right after the end broadcast')

            # match 2: a destroys b's throne
            r2 = start_room(lb, a, b, mode='strateg')
            r2.simulate(70)
            t2 = r2.game.t
            r2.game.throne[1] = 0.0
            await until(lambda: r2.done)
            e2 = self._end(a)
            self.assertEqual((e2['code'], e2['winner']), ('throne', 0))
            self.assertEqual(len(e2['ser']['th'][0]), nser(r2.game.t))
            self.assertGreaterEqual(r2.game.t, t2)
            self.assertEqual(len(self.store.data['matches']), 2)

            # match 3: a Výcvik of c (queued while the room was running) is recorded too
            send(lb, c, t='solo', type='vycvik', mode='kral', map='ruiny', ai='lehka')
            self.assertEqual(len(lb.solos), 1)
            r3 = lb.solos[0]
            r3.simulate(70)
            send(lb, c, t='quit')
            e3 = self._end(c)
            self.assertEqual(e3['code'], 'quit')
            self.assertEqual(e3['type'], 'vycvik')
            self.assertEqual(len(e3['ser']['th'][0]), nser(r3.game.t))
            self.assertIsNotNone(e3['me'])
            self.assertEqual(e3['lv'][1], None)                 # the AI has no level
            self.assertEqual(len(self.store.data['matches']), 3)

            pl = self.store.data['players']
            self.assertEqual(sorted(pl), ['hrac0', 'hrac1', 'hrac2'])
            self.assertEqual((pl['hrac0']['tot']['m'], pl['hrac0']['tot']['w']), (2, 2))
            self.assertEqual((pl['hrac1']['tot']['m'], pl['hrac1']['tot']['l']), (2, 2))
            self.assertEqual((pl['hrac2']['tot']['m'], pl['hrac2']['tot']['l']), (1, 1))
            self.assertIn('vycvik.kral.lehka', pl['hrac2']['by'])
            # the file on disk holds all three and reloads
            st2 = meta.Store(self.path)
            st2.load()
            self.assertEqual(len(st2.data['matches']), 3)
            self.assertEqual(sorted(st2.data['players']), ['hrac0', 'hrac1', 'hrac2'])
            # a fresh 'me' follows a recorded game (XP and level changed)
            self.assertGreater(a.of('me')[-1]['prof']['xp'], 0)
        run(body())

    def test_short_game_is_not_recorded(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Hrac0', 'Hrac1'])
            r = start_room(lb, a, b)
            r.simulate(10)
            send(lb, b, t='quit')
            e = self._end(a)
            self.assertIsNone(e['me'])
            self.assertEqual(e['rec_new'], [])
            self.assertEqual(self.store.data['matches'], [])
        run(body())

    def test_disconnect_records_a_loss_for_the_leaver(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Hrac0', 'Hrac1'])
            r = start_room(lb, a, b)
            r.simulate(70)
            lb.leave(b)
            e = self._end(a)
            self.assertEqual((e['code'], e['winner']), ('disc', 0))
            pl = self.store.data['players']
            self.assertEqual((pl['hrac0']['tot']['m'], pl['hrac0']['tot']['w']), (1, 1))
            self.assertEqual((pl['hrac1']['tot']['m'], pl['hrac1']['tot']['l']), (1, 1))
            m = self.store.data['matches'][0]
            self.assertTrue(all(p['k'] in ('hrac0', 'hrac1') for p in m['p']))
        run(body())

    def test_no_store_still_ends_cleanly(self):
        async def body():
            lb = mk_lobby(None)
            a, b = connect(lb, ['Hrac0', 'Hrac1'])
            r = start_room(lb, a, b)
            r.simulate(70)
            send(lb, b, t='quit')
            e = self._end(a)
            self.assertIsNone(e['me'])
            self.assertEqual(e['lv'], [None, None])
            self.assertEqual(len(e['ser']['th'][0]), nser(r.game.t))
        run(body())


class TestCosmetics(Base):
    def test_locked_cosmetic_falls_back_and_unlocked_is_kept(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Hrac0', 'Hrac1'])
            send(lb, a, t='cos', v={'ban': 'lebka', 'kor': 'neexistuje', 'zab': 5, 'vit': 'zvony'})
            prof = a.of('me')[-1]['prof']
            self.assertEqual(prof['cos'], meta.COS_DEFAULT)                  # all locked / unknown -> defaults
            p = self.store.data['players']['hrac0']
            p['ach']['ucednik'] = '2026-10-19'                               # unlocks the Lebka banner
            p['xp'] = meta.need(6)                                           # level 6: Kostěná koruna
            send(lb, a, t='cos', v={'ban': 'lebka', 'kor': 'kostena', 'vit': 'zvony'})
            prof = a.of('me')[-1]['prof']
            self.assertEqual(prof['cos'], {'ban': 'lebka', 'kor': 'kostena', 'zab': 'jiskry', 'vit': 'zlate'})
            self.assertIn('lebka', prof['own'])
            pl = b.of('lobby')[-1]['players']
            self.assertEqual(pl[0]['cos'], {'ban': 'lebka', 'kor': 'kostena'})   # the opponent sees the slot preview
            for bad in (None, 7, 'x', [1], {}):
                send(lb, a, t='cos', v=bad)
            self.assertEqual(a.of('me')[-1]['prof']['cos']['ban'], 'lebka')
            # saved 2 s (here 0.15 s) after the last change, not before
            self.assertFalse(os.path.exists(self.path))
            self.assertTrue(await until(lambda: os.path.exists(self.path), 2.0))
            st2 = meta.Store(self.path)
            st2.load()
            self.assertEqual(st2.data['players']['hrac0']['cos']['ban'], 'lebka')
            # the opponent gets my cosmetics in 'start'
            r = start_room(lb, a, b)
            st = b.of('start')[-1]
            self.assertEqual(st['cos'][0]['ban'], 'lebka')
            self.assertEqual(st['cos'][1], meta.COS_DEFAULT)
            r.finish({'winner': -1, 'reason': 'test', 'code': 'error'})
        run(body())

    def test_cos_without_profile_key_is_ignored(self):
        async def body():
            lb = mk_lobby(self.store)
            c, = connect(lb, ['Král'])
            send(lb, c, t='cos', v={'ban': 'rod'})
            self.assertEqual(self.store.data['players'], {})
            self.assertFalse(self.store.dirty)
        run(body())


class TestStatsQuery(Base):
    def test_stats_q_self_other_and_unknown(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Hrac0', 'Hrac1'])
            r = start_room(lb, a, b)
            r.simulate(70)
            send(lb, b, t='quit')
            send(lb, a, t='stats_q', who=None)
            st = a.of('stats')[-1]
            self.assertEqual(st['prof']['key'], 'hrac0')
            self.assertEqual(st['prof']['tot']['m'], 1)
            self.assertEqual(len(st['hist']), 1)
            self.assertIn('ser', st['hist'][0])
            self.assertEqual(st['hof'], [])                      # nobody has 5 souboj games yet
            self.assertEqual(st['h2h']['hrac1'][:3], [1, 0, 0])
            send(lb, a, t='stats_q', who='hrac1')
            st = a.of('stats')[-1]
            self.assertEqual((st['who'], st['prof']['key']), ('hrac1', 'hrac1'))
            self.assertEqual(st['h2h']['hrac0'][:3], [0, 1, 0])
            send(lb, a, t='stats_q', who='  HRAC1 ')
            self.assertEqual(a.of('stats')[-1]['prof']['key'], 'hrac1')
            for who in ('nikdo', 5, [1], {'a': 1}, ''):
                send(lb, a, t='stats_q', who=who)
                st = a.of('stats')[-1]
                self.assertIsNone(st['prof'], who)
                self.assertEqual((st['hist'], st['h2h']), ([], {}))
            c, = connect(lb, ['Král'])
            send(lb, c, t='stats_q', who=None)
            self.assertIsNone(c.of('stats')[-1]['prof'])
        run(body())

    def test_hof_lists_players_with_five_games(self):
        async def body():
            lb = mk_lobby(self.store)
            a, b = connect(lb, ['Hrac0', 'Hrac1'])
            for i in range(5):
                r = start_room(lb, a, b)
                r.simulate(62)
                send(lb, b, t='quit')
            send(lb, a, t='stats_q', who=None)
            hof = a.of('stats')[-1]['hof']
            self.assertEqual([h[0] for h in hof][:1], ['Hrac0'])
            self.assertEqual(len(hof), 2)
            self.assertEqual(hof[0][4:], [5, 5])
        run(body())


class TestSaving(Base):
    def test_failed_save_is_retried_by_the_heartbeat(self):
        lb = mk_lobby(self.store)
        calls = []
        ok = [False]

        def fake_save():
            calls.append(1)
            if ok[0]:
                self.store.dirty = False
            return ok[0]
        self.store.save = fake_save
        self.store.dirty = True
        self.assertFalse(lb.save_store())
        self.assertEqual(len(calls), 1)
        lb.store_tick()                                          # too soon: no retry
        self.assertEqual(len(calls), 1)
        lb.save_failed_at -= L.SAVE_RETRY + 1
        lb.store_tick()
        self.assertEqual(len(calls), 2)
        ok[0] = True
        lb.save_failed_at -= L.SAVE_RETRY + 1
        lb.store_tick()
        self.assertEqual(len(calls), 3)
        self.assertIsNone(lb.save_failed_at)
        lb.store_tick()                                          # clean: nothing to do
        self.assertEqual(len(calls), 3)


if __name__ == '__main__':
    unittest.main(verbosity=1)
