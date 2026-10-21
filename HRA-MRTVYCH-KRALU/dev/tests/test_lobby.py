"""Lobby + Session protocol (SPEC 3.4, 4.1-4.3; M2 gate list). A FakeClient drives Lobby.handle without sockets; the
sessions run their real asyncio loops (a few hundred ms each). The AI is session.IdleAI so the test does not depend on
hmk/ai."""
import asyncio
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
if not _paths.is_hmk(S):
    raise unittest.SkipTest('test_lobby needs the 1.0 hmk package')

from hmk import lobby as L, net, session as SS, modes, puzzle  # noqa: E402


class FakeWriter:
    def __init__(self, i):
        self.i = i

    def get_extra_info(self, k):
        return ('10.0.0.%d' % self.i, 1234)

    def write(self, data):
        pass

    async def drain(self):
        pass

    def close(self):
        pass


class FakeClient(net.Client):
    """A net.Client whose sends are recorded (strict JSON, as the socket would get them)."""

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


def mk_lobby():
    lb = L.Lobby()
    lb.ai_factory = SS.IdleAI
    return lb


def connect(lb, n):
    cs = []
    for i in range(n):
        c = FakeClient(i, 'Hrac%d' % i)
        assert lb.join(c)
        lb.handle(c, json.dumps({'t': 'hello', 'name': c.name}))
        cs.append(c)
    return cs


def send(lb, c, **m):
    lb.handle(c, json.dumps(m))


def ter_of(g):
    return ''.join(''.join(r) for r in g.ter)


def start_room(lb, a, b, mode='kral'):
    send(lb, a, t='cfg', type='souboj', mode=mode)
    send(lb, a, t='ready', v=True, deck=None, fac='bez')
    send(lb, b, t='ready', v=True, deck=None, fac='xx')
    return lb.room


def run(coro):
    return asyncio.run(coro)


class TestLobby(unittest.TestCase):
    def test_concurrent_sessions_and_own_snapshots(self):
        async def body():
            lb = mk_lobby()
            a, b, c, d, e = connect(lb, 5)
            self.assertEqual((a.seat, b.seat, c.seat), (0, 1, None))
            self.assertEqual(lb.waiting, [c, d, e])
            room = start_room(lb, a, b)
            self.assertIsNotNone(room)
            self.assertEqual(a.of('start')[-1]['fac'], ['bez', 'bez'])
            send(lb, c, t='solo', type='vycvik', mode='strateg', map='ruiny', ai='tezka')
            send(lb, d, t='solo', type='vycvik', mode='kral', map='ruiny', ai='lehka')
            self.assertEqual(len(lb.solos), 2)
            self.assertEqual(lb.waiting, [e])
            for cl in (c, d):
                st = cl.of('start')[-1]
                self.assertTrue(st['solo'])
                self.assertEqual(st['type'], 'vycvik')
                self.assertIsInstance(st['seed'], int)
                self.assertEqual(st['side'], 0)
                self.assertEqual(st['ai']['diff'], cl.session.opts['ai'])
            # the 3rd solo is refused
            send(lb, e, t='solo', type='vycvik', ai='lehka')
            self.assertEqual(len(lb.solos), 2)
            self.assertIn('2 cvičné hry', e.of('lerr')[-1]['text'])
            self.assertIs(e.session, None)
            self.assertEqual(e.of('lobby')[-1]['solo'], [2, 2])
            await asyncio.sleep(0.4)
            games = {id(x.session.game) for x in (a, c, d)}
            self.assertEqual(len(games), 3)
            for cl in (a, b, c, d):
                snaps = cl.of('s')
                self.assertGreater(len(snaps), 3, cl.name)
                want = ter_of(cl.session.game)
                self.assertTrue(all(s['ter'] == want for s in snaps), '%s got a foreign snapshot' % cl.name)
                self.assertEqual(all('kr' in s for s in snaps), cl.session.game.mode == 'kral')
            self.assertEqual(e.of('s'), [])
            self.assertTrue(all(g.t > 0.1 for g in (a.session.game, c.session.game, d.session.game)))
            for cl in (a, c, d):
                send(lb, cl, t='quit')
            self.assertEqual((lb.room, lb.solos), (None, []))
        run(body())

    def test_seated_player_solo_frees_seat(self):
        async def body():
            lb = mk_lobby()
            a, b, c = connect(lb, 3)
            send(lb, b, t='ready', v=True)
            self.assertTrue(b.ready)
            send(lb, a, t='solo', type='vycvik', ai='lehka')
            self.assertIs(a.session, lb.solos[0])
            self.assertEqual(a.seat, None)
            self.assertIs(lb.slots[0], c)             # the queue head took the seat
            self.assertEqual((c.seat, lb.waiting), (0, []))
            self.assertFalse(b.ready)                 # a new opponent: ready again
            send(lb, a, t='quit')
            self.assertEqual(lb.waiting, [a])         # seats full -> back to the queue
            end = a.of('end')[-1]
            self.assertEqual((end['code'], end['winner'], end['type']), ('quit', 1, 'vycvik'))
            self.assertIn('me', end)
            self.assertIn('rec_new', end)
        run(body())

    def test_queued_player_solo_and_return(self):
        async def body():
            lb = mk_lobby()
            a, b, c, d = connect(lb, 4)
            send(lb, d, t='solo', type='vycvik', ai='lehka')
            self.assertEqual(lb.waiting, [c])         # d left the queue
            send(lb, d, t='quit')
            self.assertEqual(lb.waiting, [c, d])      # no seat free -> appended
            # a free seat when the solo ends -> seated
            lb2 = mk_lobby()
            x, y = connect(lb2, 2)
            send(lb2, x, t='solo', type='vycvik', ai='lehka')
            self.assertEqual(lb2.slots, [None, y])
            send(lb2, x, t='quit')
            self.assertEqual((lb2.slots[0], x.seat), (x, 0))
        run(body())

    def test_pause_stops_time(self):
        async def body():
            lb = mk_lobby()
            a, b = connect(lb, 2)
            send(lb, a, t='pause', v=True)            # not in a session: ignored
            room = start_room(lb, a, b)
            send(lb, a, t='pause', v=True)            # PvP: no pause
            self.assertFalse(room.paused)
            send(lb, a, t='quit')
            send(lb, a, t='solo', type='vycvik', ai='lehka')
            ses = a.session
            await asyncio.sleep(0.2)
            send(lb, a, t='pause', v=True)
            t0 = ses.game.t
            self.assertGreater(t0, 0)
            await asyncio.sleep(0.8)
            self.assertEqual(ses.game.t, t0)
            ps = [s for s in a.of('s') if s.get('ps') == 1]
            self.assertGreaterEqual(len(ps), 1)
            send(lb, a, t='pause', v=False)
            await asyncio.sleep(0.2)
            self.assertGreater(ses.game.t, t0)
            send(lb, a, t='quit')
        run(body())

    def test_restart_puzzle_keeps_seed(self):
        class FakePuzzleRules(modes.DuelRules):
            play = 'puzzle'

        old_rules, old_pz = modes.make_rules, dict(puzzle.PUZZLES)

        def fake_make_rules(type, opts):
            if type == 'puzzle':
                return FakePuzzleRules() if opts.get('puzzle') in puzzle.PUZZLES else None
            return old_rules(type, opts)

        async def body():
            lb = mk_lobby()
            a, = connect(lb, 1)
            send(lb, a, t='solo', type='puzzle', puzzle='p99')
            self.assertEqual(a.of('start'), [])       # unknown puzzle -> lerr
            self.assertTrue(a.of('lerr'))
            send(lb, a, t='solo', type='puzzle', puzzle='pT')
            ses = a.session
            g1 = ses.game
            self.assertEqual((g1.seed, g1.mode, a.of('start')[-1]['seed']), (4321, 'strateg', 4321))
            await asyncio.sleep(0.15)
            send(lb, a, t='restart')
            self.assertIsNot(ses.game, g1)
            self.assertEqual((ses.game.seed, a.of('start')[-1]['seed']), (4321, 4321))
            self.assertEqual(ter_of(ses.game), ter_of(g1))
            self.assertEqual(a.of('end'), [])         # restart is not an end
            await asyncio.sleep(0.15)
            self.assertGreater(ses.game.t, 0)
            send(lb, a, t='quit')
            # other solo types: a new seed
            send(lb, a, t='solo', type='vycvik', ai='lehka')
            s1 = a.session.game.seed
            send(lb, a, t='restart')
            self.assertNotEqual(a.session.game.seed, s1)
            send(lb, a, t='quit')

        modes.make_rules = fake_make_rules
        puzzle.PUZZLES['pT'] = {'id': 'pT', 'mode': 'strateg', 'map': 'ruiny', 'seed': 4321}
        try:
            run(body())
        finally:
            modes.make_rules = old_rules
            puzzle.PUZZLES.clear()
            puzzle.PUZZLES.update(old_pz)

    def test_quit_pvp(self):
        async def body():
            lb = mk_lobby()
            a, b = connect(lb, 2)
            start_room(lb, a, b)
            await asyncio.sleep(0.1)
            send(lb, b, t='quit')
            for cl in (a, b):
                end = cl.of('end')[-1]
                self.assertEqual((end['code'], end['winner'], end['type']), ('quit', 0, 'souboj'))
            self.assertIsNone(lb.room)
            self.assertEqual((a.seat, b.seat, a.session, b.session), (0, 1, None, None))
        run(body())

    def test_disconnect(self):
        async def body():
            lb = mk_lobby()
            a, b, c = connect(lb, 3)
            start_room(lb, a, b)
            await asyncio.sleep(0.1)
            lb.leave(a)
            end = b.of('end')[-1]
            self.assertEqual((end['code'], end['winner']), ('disc', 1))
            self.assertEqual(a.of('end'), [])
            self.assertEqual(lb.slots, [c, b])        # the queue head takes the freed seat
            send(lb, b, t='solo', type='vycvik', ai='lehka')
            ses = b.session
            lb.leave(b)
            self.assertTrue(ses.done)
            self.assertEqual(ses.game.over['code'], 'disc')
            self.assertEqual(lb.solos, [])
            self.assertNotIn(b, lb.waiting)
        run(body())

    def test_cfg_ready_and_lobby_fields(self):
        async def body():
            lb = mk_lobby()
            a, b, c = connect(lb, 3)
            send(lb, a, t='ready', v=True, fac='kult', deck=['x'])
            self.assertEqual((a.fac, len(a.deck)), ('kult', 8))
            send(lb, b, t='cfg', type='souboj', mode='strateg', map='nahodna')
            self.assertFalse(a.ready)                 # cfg unreadies both
            send(lb, c, t='cfg', mode='kral')         # queued: ignored
            send(lb, a, t='mode', v='kral')           # 'mode' is gone
            send(lb, a, t='cfg', type='vycvik', map='nowhere', mode=5)
            self.assertEqual(lb.cfg, {'type': 'souboj', 'mode': 'strateg', 'map': 'nahodna'})
            m = c.of('lobby')[-1]
            self.assertEqual((m['cfg'], m['solo'], m['you'], m['pos']), (lb.cfg, [0, L.MAX_SOLO], None, 1))
            self.assertNotIn('mode', m)
            self.assertTrue(all(k in m['players'][0] for k in ('lv', 'ttl', 'cos')))
            self.assertEqual(a.of('me'), [])             # debounced
            await asyncio.sleep(L.ME_DEBOUNCE + 0.1)
            self.assertEqual(a.of('me'), [{'t': 'me', 'prof': None}])
            # same profile name in both seats
            send(lb, b, t='hello', name='hrac0 ')
            send(lb, b, t='hello', name='Hrac0')
            send(lb, b, t='ready', v=True)
            self.assertFalse(b.ready)
            self.assertIn('Hrac0', b.of('lerr')[-1]['text'])
            # defs additions
            d = net.DEFS_MSG
            self.assertEqual(d['soloMax'], L.MAX_SOLO)
            self.assertTrue({'types', 'maps', 'puzzles', 'diffs', 'squad'} <= set(d))
        run(body())


if __name__ == '__main__':
    unittest.main()
