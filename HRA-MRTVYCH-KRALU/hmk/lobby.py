"""Lobby: two room seats, a waiting queue, the room session and up to MAX_SOLO solo sessions (SPEC 3.4, 4)."""
import asyncio
import json
import time
import traceback

from . import VERSION
from . import defs as D
from . import maps
from . import meta
from . import factions as F
from .defs import MODES
from . import session as SS

MAX_CONN = 8          # every connection: 2 seats + queue + players in solo sessions
MAX_SOLO = 2          # solo sessions at once (so at most 3 games run)
KICK_IDLE = 30        # a waiting player may free a slot held by someone idle (and not ready) this long
ME_DEBOUNCE = 0.3     # 'me' goes out this long after the last name change
COS_SAVE_DELAY = 2.0  # stats are written this long after the last cosmetics change (debounced)
SAVE_RETRY = 30.0     # a failed stats save is retried (by the heartbeat) no sooner than this
URLS = []             # LAN addresses, filled by net.main (mutated in place)
ROOM_TYPES = ('souboj', 'preziti')
SOLO_TYPES = ('vycvik', 'preziti', 'puzzle', 'vyuka')
SOLO_TEXT = {'vycvik': 'Výcvik', 'preziti': 'Přežití', 'puzzle': 'Puzzle', 'vyuka': 'Výuka'}
T_NOT_READY = 'Tento režim zatím není hotový.'
T_SOLO_FULL = 'Server už hostí %d cvičné hry, zkus to za chvíli.'
T_DUP_NAME = 'Oba máte jméno „%s“. Jeden si ho změňte, jinak se statistiky smíchají.'


class Lobby:
    """Two room seats plus a waiting queue, so an extra or forgotten browser tab never locks anyone out.
    Players not in a session may start a solo session; that frees their seat or queue place."""

    def __init__(self, store=None):
        self.slots = [None, None]       # room seats
        self.waiting = []               # queue (never holds a client that is in a session)
        self.conns = []                 # every connected client
        self.room = None                # Session of the room match
        self.solos = []                 # solo Sessions
        self.cfg = {'type': 'souboj', 'mode': 'kral', 'map': 'nahodna'}
        self.store = store
        self.ai_factory = None          # None -> hmk.ai.make_ai (tests set session.IdleAI)
        self.last_log = ''
        self.save_timer = None          # pending debounced stats save (cosmetics)
        self.save_failed_at = None      # monotonic time of the last failed save, None = the last save worked

    def clients(self):
        return list(self.conns)

    # ------------------------------------------------------------ lobby state
    def info(self, c, now):
        return {'name': c.name, 'ip': c.ip, 'ready': c.ready, 'idle': int(now - c.acted)}

    def player_info(self, c, now, i):
        d = dict(self.info(c, now), side=i)
        lt = SS.prof_lv(self.store, c.key)
        cs = meta.cos_for(self.store, c.key)
        d.update(lv=lt[0] if lt else None, ttl=lt[1] if lt else None, cos={'ban': cs['ban'], 'kor': cs['kor']})
        return d

    def update(self):
        now = time.monotonic()
        players = [self.player_info(c, now, i) if c else None for i, c in enumerate(self.slots)]
        queue = [dict(self.info(c, now), busy=False) for c in self.waiting]
        queue += [dict(self.info(c, now), busy=True) for ses in self.solos for c in ses.clients if c is not None]
        for c in self.conns:
            c.send({'t': 'lobby', 'players': players, 'queue': queue, 'you': c.seat, 'cfg': dict(self.cfg),
                    'solo': [len(self.solos), MAX_SOLO],
                    'pos': self.waiting.index(c) + 1 if c in self.waiting else 0, 'kickIdle': KICK_IDLE,
                    'playing': self.room is not None, 'urls': URLS, 'ver': VERSION})
        self.log()

    def log(self):
        parts = ['%d) %s [%s]%s' % (i + 1, c.name, c.ip, ' - pripraven' if c.ready else '') if c else '%d) volno' % (i + 1)
                 for i, c in enumerate(self.slots)]
        if self.waiting:
            parts.append('fronta: ' + ', '.join('%s [%s]' % (c.name, c.ip) for c in self.waiting))
        if self.solos:
            parts.append('sami: %d' % len(self.solos))
        line = '  Lobby (%s/%s/%s): ' % (self.cfg['type'], self.cfg['mode'], self.cfg['map']) + ' | '.join(parts)
        if line != self.last_log:
            self.last_log = line
            print(line)

    def lerr(self, c, text):
        c.send({'t': 'lerr', 'text': text})

    def unready(self):
        for o in self.slots:
            if o:
                o.ready = False

    # ------------------------------------------------------------ seats
    def join(self, c):
        if len(self.conns) >= MAX_CONN:
            return False
        self.conns.append(c)
        self.place(c)
        return True

    def place(self, c):
        """Seat c in a free seat (no room match running), else queue it."""
        for i in (0, 1):
            if self.slots[i] is None and self.room is None:
                self.slots[i] = c
                c.seat = i
                c.ready = False
                return
        if c not in self.waiting:
            self.waiting.append(c)

    def seat(self, side, c=None):
        """Give a free slot to c, or to whoever waits longest."""
        if self.slots[side] is not None or self.room is not None:
            return
        if c is None:
            if not self.waiting:
                return
            c = self.waiting[0]
        if c in self.waiting:
            self.waiting.remove(c)
        self.slots[side] = c
        c.seat = side
        c.ready = False

    def unseat(self, c):
        """Take c out of its seat or the queue (the freed seat goes to the queue head)."""
        if c in self.waiting:
            self.waiting.remove(c)
        if c.seat is not None and self.slots[c.seat] is c:
            side = c.seat
            self.slots[side] = None
            c.seat = None
            self.unready()
            self.seat(side)
        c.seat = None
        c.ready = False

    def leave(self, c):
        """A connection closed (also used by the heartbeat). Inside a session this is a 'quit' with code 'disc'."""
        if c not in self.conns:
            return
        self.conns.remove(c)
        ses = c.session
        if ses is not None and not ses.done:
            ses.quit(c, code='disc')
        c.session = None
        self.unseat(c)
        self.update()

    def kick(self, c, side):
        """A player may remove an opponent who is not ready; a waiting player only one idle for KICK_IDLE s."""
        if self.room or c.session or type(side) is not int or side not in (0, 1):
            return
        t = self.slots[side]
        if t is None or t is c or t.ready:
            return
        if c.seat is None and time.monotonic() - t.acted < KICK_IDLE:
            return
        print('  %s [%s] uvolnil misto hrace %s [%s]' % (c.name, c.ip, t.name, t.ip))
        self.slots[side] = None
        t.seat = None
        t.send({'t': 'kicked', 'by': c.name})
        try:
            asyncio.get_running_loop().call_later(0.5, t.drop)
        except RuntimeError:
            t.drop()
        self.seat(side, c if c in self.waiting else None)
        self.update()

    # ------------------------------------------------------------ messages
    def handle(self, c, text):
        try:
            m = json.loads(text)
        except (ValueError, RecursionError):
            return
        if not isinstance(m, dict):
            return
        c.acted = time.monotonic()
        t = m.get('t')
        if not isinstance(t, str):
            t = None
        if t == 'hello':
            self.hello(c, m)
        elif t == 'stats_q':
            self.stats_q(c, m)
        elif t == 'cos':
            self.set_cos(c, m)
        elif c.session is not None:
            self.in_session(c, m, t)
        elif t == 'ready':
            self.ready(c, m)
        elif t == 'cfg':
            self.set_cfg(c, m)
        elif t == 'solo':
            self.solo(c, m)
        elif t == 'kick':
            self.kick(c, m.get('side'))

    def hello(self, c, m):
        name = m.get('name')
        new = ((name if isinstance(name, str) else '').strip() or 'Král')[:16]
        changed = new != c.name or not getattr(c, 'me_sent', False)
        c.name = new
        c.key = meta.key(new)
        if changed:
            self.schedule_me(c)
        self.update()

    def schedule_me(self, c):
        h = getattr(c, 'me_timer', None)
        if h is not None:
            h.cancel()
        try:
            c.me_timer = asyncio.get_running_loop().call_later(ME_DEBOUNCE, self.send_me, c)
        except RuntimeError:
            c.me_timer = None
            self.send_me(c)

    def send_me(self, c):
        h = c.me_timer
        c.me_timer = None
        if h is not None:
            h.cancel()
        c.me_sent = True
        prof = None
        if self.store is not None and c.key:
            try:
                prof = meta.profile_view(self.store, c.key, name=c.name)
            except Exception:
                traceback.print_exc()
        c.send({'t': 'me', 'prof': prof})

    def set_cos(self, c, m):
        """{t:'cos', v:{ban,kor,zab,vit}}: a locked or unknown id falls back to the slot default. Needs a profile key."""
        v = m.get('v')
        if not isinstance(v, dict) or not c.key:
            return
        if meta.set_cos(self.store, c.key, v, name=c.name) is None:
            return
        self.schedule_save()
        self.send_me(c)
        self.update()

    def stats_q(self, c, m):
        """{t:'stats_q', who: key | null (= self)} -> {t:'stats', who, prof, hist, hof, h2h}. Unknown profile: prof null."""
        who = m.get('who')
        k = c.key if who is None else (meta.key(who[:64]) if isinstance(who, str) else None)
        sv = None
        if self.store is not None and k:
            try:
                sv = meta.stats_view(self.store, k)
            except Exception:
                traceback.print_exc()
        if sv is None:
            sv = {'prof': None, 'hist': [], 'hof': meta.hof(self.store) if self.store is not None else [], 'h2h': {}}
        c.send(dict(sv, t='stats', who=k))

    # ------------------------------------------------------------ stats file
    def save_store(self):
        """Write the stats now (when there is anything to write). Returns False when the save failed."""
        h = self.save_timer
        self.save_timer = None
        if h is not None:
            h.cancel()
        st = self.store
        if st is None or not st.dirty:
            return True
        ok = bool(st.save())
        self.save_failed_at = None if ok else time.monotonic()
        return ok

    def schedule_save(self):
        """Debounced save (cosmetics): COS_SAVE_DELAY after the last change; at once when no event loop runs."""
        h = self.save_timer
        if h is not None:
            h.cancel()
        try:
            self.save_timer = asyncio.get_running_loop().call_later(COS_SAVE_DELAY, self.save_store)
        except RuntimeError:
            self.save_timer = None
            self.save_store()

    def store_tick(self):
        """Heartbeat: retry a failed save, or save what was left unsaved (e.g. a profile restored from .bak)."""
        st = self.store
        if st is None or not st.dirty or self.save_timer is not None:
            return
        if self.save_failed_at is not None and time.monotonic() - self.save_failed_at < SAVE_RETRY:
            return
        self.save_store()

    def in_session(self, c, m, t):
        ses = c.session
        if t == 'quit':
            ses.quit(c)
        elif t == 'pause':
            ses.set_pause(m.get('v'))
        elif t == 'restart':
            ses.restart()
        elif ses.done or ses.game.over:
            return
        else:
            try:
                ses.game.act(c.gside, m)
            except Exception:
                traceback.print_exc()

    def ready(self, c, m):
        if self.room or c.seat is None:
            return
        v = bool(m.get('v'))
        if v:
            fac = m.get('fac') if m.get('fac') in F.FAC_IDS else 'bez'
            o = self.slots[1 - c.seat]
            if c.key and o is not None and o.key == c.key:
                self.lerr(c, T_DUP_NAME % c.name)
                v = False
            else:
                c.fac = fac
                c.deck = D.valid_deck(m.get('deck'), fac) or list(F.RECOMMENDED_F[fac])
        c.ready = v
        self.update()
        if all(s and s.ready for s in self.slots):
            self.start_room()

    def set_cfg(self, c, m):
        if self.room or c.seat is None:
            return
        new = dict(self.cfg)
        if m.get('type') in ROOM_TYPES:
            new['type'] = m['type']
        if m.get('mode') in MODES:
            new['mode'] = m['mode']
        mp = m.get('map')
        if isinstance(mp, str) and (mp == 'nahodna' or mp in maps.MAPS):
            new['map'] = mp
        if new != self.cfg:
            self.cfg = new
            self.unready()
            self.update()

    # ------------------------------------------------------------ sessions
    def start_room(self):
        cs = list(self.slots)
        typ = self.cfg['type']
        opts = SS.clean_opts(typ, self.cfg, solo=False)
        humans = [(c.name, c.deck or list(F.RECOMMENDED_F[c.fac]), c.fac) for c in cs]
        built = SS.build_game(typ, opts, humans, ai_factory=self.ai_factory)
        self.unready()
        if built is None:
            for c in cs:
                self.lerr(c, T_NOT_READY)
            self.update()
            return
        g, ais = built
        ses = SS.Session(self, 'room', typ, g, cs, ais, opts, store=self.store)
        self.room = ses
        ses.send_start()
        ses.task = asyncio.ensure_future(ses.run())
        print('  Zapas zacal (%s/%s, %s): %s vs %s (delka %.0f s)' % (typ, g.mode, g.map.id, g.names[0], g.names[1],
                                                                    g.length))
        self.update()

    def solo(self, c, m):
        typ = m.get('type')
        if typ not in SOLO_TYPES:
            return
        if len(self.solos) >= MAX_SOLO:
            self.lerr(c, T_SOLO_FULL % MAX_SOLO)
            return
        opts = SS.clean_opts(typ, m, solo=True)
        built = SS.build_game(typ, opts, [(c.name, opts['deck'], opts['fac']), None], ai_factory=self.ai_factory)
        if built is None:
            self.lerr(c, T_NOT_READY)
            return
        g, ais = built
        self.unseat(c)
        ses = SS.Session(self, 'solo', typ, g, [c, None], ais, opts, store=self.store)
        self.solos.append(ses)
        ses.send_start()
        ses.task = asyncio.ensure_future(ses.run())
        print('  %s [%s] hraje sam: %s (%s, %s%s)' % (c.name, c.ip, SOLO_TEXT.get(typ, typ), g.mode, g.map.id,
                                                    ', ' + opts['ai'] if opts['ai'] else ''))
        self.update()

    def session_done(self, ses):
        """Called by Session.finish: room players stay seated; solo players are seated again or queued."""
        if ses is self.room:
            self.room = None
            for c in ses.clients:
                if c is not None:
                    c.session = None
                    c.ready = False
                    self.fresh_me(ses, c)
            for i in (0, 1):
                self.seat(i)
        elif ses in self.solos:
            self.solos.remove(ses)
            for c in ses.clients:
                if c is not None:
                    c.session = None
                    self.fresh_me(ses, c)
                    if c in self.conns:
                        self.place(c)
        self.update()

    def fresh_me(self, ses, c):
        """After a recorded game the player's profile (XP, unlocks, puzzle stars) changed: send 'me' again."""
        if ses.clients.index(c) in ses.rec_sides:
            self.send_me(c)
