"""Networking: HTTP static files, the WebSocket framing, client queues, heartbeat and the command-line entry."""
import asyncio
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import time
import webbrowser

from . import VERSION
from . import defs as D
from .defs import (DEFS, RESEARCH, BRANCHES, CMDS, BASE_KIT, CARD_POOL, RECOMMENDED, DECK_SIZE, RARITY, MODES,
                   DOBA_AT, RELIC)
from . import factions as FA
from . import lobby as L
from . import maps as M
from . import meta
from . import puzzle as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the game folder
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
PING_EVERY = 5.0
DEAD_AFTER = 20.0
PORT = 8095


def lan_ips():
    ips = set()
    primary = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        primary = s.getsockname()[0]
        ips.add(primary)
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips = [ip for ip in sorted(ips) if not ip.startswith('127.')]
    first = [primary] if primary in ips else []
    return first + sorted(ip for ip in ips if ip not in first) or ['127.0.0.1']


def unmask(data, mask):
    n = len(data)
    if not n:
        return data
    m = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, 'little') ^ int.from_bytes(m, 'little')).to_bytes(n, 'little')


def frame(payload, opcode=1):
    n = len(payload)
    if n < 126:
        head = struct.pack('!BB', 0x80 | opcode, n)
    elif n < 65536:
        head = struct.pack('!BBH', 0x80 | opcode, 126, n)
    else:
        head = struct.pack('!BBQ', 0x80 | opcode, 127, n)
    return head + payload


DEFS_MSG = {'t': 'defs', 'ver': VERSION, 'defs': DEFS, 'research': RESEARCH, 'branches': BRANCHES, 'cmds': CMDS,
            'base': BASE_KIT, 'pool': CARD_POOL, 'recommended': RECOMMENDED, 'deckSize': DECK_SIZE,
            'rarity': [r[0] for r in RARITY], 'modes': MODES, 'dobaAt': DOBA_AT,
            'relic': RELIC, 'relicFrom': D.RELIC_FROM, 'eclipses': D.ECLIPSES, 'eclLen': D.ECL_LEN, 'conv': D.CONV}


def _diffs():
    try:
        from .ai.profiles import DIFFS
        return [list(d) for d in DIFFS]
    except Exception:
        return []


# SPEC 4.2 additions: types maps puzzles diffs squad soloMax, the faction catalogue (factions facPool facCosts facRec)
# and the meta catalogue (cosm ach lvls titles)
DEFS_MSG.update({'types': D.TYPES, 'maps': M.public_maps(), 'puzzles': P.public_puzzles(), 'diffs': _diffs(),
                 'squad': [getattr(D, 'SQUAD_CD', 20)], 'soloMax': L.MAX_SOLO})
DEFS_MSG.update(FA.public())
DEFS_MSG.update(meta.public_catalogs())


class Client:
    def __init__(self, writer):
        self.writer = writer
        peer = writer.get_extra_info('peername')
        self.ip = str(peer[0]) if peer else '?'
        if self.ip.startswith('::ffff:'):
            self.ip = self.ip[7:]
        self.name = 'Král'
        self.key = None           # meta.key(name), None = no profile
        self.seat = None          # room seat 0/1 or None
        self.session = None       # the Session this client plays in
        self.gside = None         # side in that session's game
        self.fac = 'bez'
        self.ready = False
        self.deck = None
        self.me_timer = None
        self.queue = asyncio.Queue(maxsize=64)
        self.alive = True
        self.last = time.monotonic()      # last frame received from the browser (pongs included)
        self.acted = time.monotonic()     # last message the player actually sent

    def push(self, data, droppable=False):
        if not self.alive:
            return
        if self.queue.full():
            if droppable:
                return
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(data)

    def send_raw(self, data, droppable=False):
        self.push(frame(data), droppable)

    def send(self, obj, droppable=False):
        self.send_raw(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), droppable)

    def drop(self):
        # abort(), not close(): close() waits to flush the send buffer, which a frozen peer never lets happen
        self.alive = False
        try:
            self.writer.transport.abort()
        except (OSError, AttributeError):
            pass

    async def pump(self):
        try:
            while self.alive:
                data = await self.queue.get()
                self.writer.write(data)
                await self.writer.drain()
        except (ConnectionError, OSError):
            self.alive = False



LOBBY = L.Lobby()


async def read_headers(reader):
    raw = await reader.readuntil(b'\r\n\r\n')
    lines = raw.decode('latin-1').split('\r\n')
    method, path, _ = (lines[0].split(' ') + ['', '', ''])[:3]
    headers = {}
    for line in lines[1:]:
        if ':' in line:
            k, v = line.split(':', 1)
            headers[k.strip().lower()] = v.strip()
    return method, path, headers


def http_response(writer, code, ctype, body):
    reason = {200: 'OK', 404: 'Not Found', 405: 'Method Not Allowed'}.get(code, 'OK')
    head = ('HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n'
            % (code, reason, ctype, len(body))).encode('latin-1')
    writer.write(head + body)


STATIC_TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8'}


def static_file(path):
    """Map a URL path to (file, content type) inside the game folder; None when not allowed."""
    rel = path.split('?')[0].split('#')[0].lstrip('/') or 'index.html'
    if '..' in rel or '\\' in rel or ':' in rel:
        return None
    ctype = STATIC_TYPES.get(os.path.splitext(rel)[1].lower())
    f = os.path.normpath(os.path.join(ROOT, rel))
    if not ctype or not f.startswith(ROOT + os.sep) or not os.path.isfile(f):
        return None
    return f, ctype


async def websocket(reader, writer, headers):
    key = headers.get('sec-websocket-key', '')
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode('latin-1')).digest()).decode('latin-1')
    writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n' % accept).encode('latin-1'))
    await writer.drain()
    c = Client(writer)
    if not LOBBY.join(c):
        print('  ! %s odmitnut: prilis mnoho pripojeni' % c.ip)
        writer.write(frame(json.dumps({'t': 'full'}).encode('utf-8')))
        await writer.drain()
        writer.close()
        return
    pump = asyncio.ensure_future(c.pump())
    print('  + %s pripojen %s' % (c.ip, 'jako hrac %d' % (c.seat + 1) if c.seat is not None else 'do fronty'))
    c.send(DEFS_MSG)
    LOBBY.update()
    parts = []
    try:
        while True:
            b1, b2 = await reader.readexactly(2)
            c.last = time.monotonic()
            op = b1 & 0x0F
            fin = b1 & 0x80
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack('!H', await reader.readexactly(2))[0]
            elif n == 127:
                n = struct.unpack('!Q', await reader.readexactly(8))[0]
            if n > 65536:
                break
            mask = await reader.readexactly(4) if b2 & 0x80 else b''
            data = await reader.readexactly(n) if n else b''
            if mask:
                data = unmask(data, mask)
            if op == 8:
                break
            if op == 9:
                c.push(frame(data, 10))
                continue
            if op == 10:
                continue
            if op in (0, 1, 2):
                parts.append(data)
                if fin:
                    text = b''.join(parts).decode('utf-8', 'replace')
                    parts = []
                    LOBBY.handle(c, text)
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
        pass
    finally:
        c.alive = False
        pump.cancel()
        LOBBY.leave(c)
        print('  - %s [%s] odpojen' % (c.name, c.ip))
        try:
            writer.close()
        except OSError:
            pass


async def heartbeat():
    """Ping every browser; drop connections that stopped answering (sleeping PC, pulled cable)."""
    ping = frame(b'', 9)
    while True:
        await asyncio.sleep(PING_EVERY)
        now = time.monotonic()
        for c in LOBBY.clients():
            if now - c.last > DEAD_AFTER:
                print('  ! %s [%s] neodpovida, odpojuji' % (c.name, c.ip))
                c.drop()
                LOBBY.leave(c)
            else:
                c.push(ping, droppable=True)
        if LOBBY.waiting and LOBBY.room is None:
            LOBBY.update()
        LOBBY.store_tick()


async def handle(reader, writer):
    try:
        method, path, headers = await read_headers(reader)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, OSError):
        writer.close()
        return
    try:
        if path.startswith('/ws') and headers.get('upgrade', '').lower() == 'websocket':
            await websocket(reader, writer, headers)
            return
        if method != 'GET':
            http_response(writer, 405, 'text/plain', b'')
        else:
            f = static_file(path)
            if f:
                with open(f[0], 'rb') as fh:
                    http_response(writer, 200, f[1], fh.read())
            else:
                http_response(writer, 404, 'text/plain; charset=utf-8', 'Nenalezeno'.encode('utf-8'))
        await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except OSError:
            pass


async def main(argv=()):
    server = await asyncio.start_server(handle, '0.0.0.0', PORT)
    L.URLS[:] = ['http://%s:%d' % (ip, PORT) for ip in lan_ips()]
    print('')
    print('  HRA MRTVYCH KRALU %s - server bezi.' % VERSION)
    print('  Ty:       http://localhost:%d' % PORT)
    for u in L.URLS:
        print('  Souper:   %s' % u)
    print('')
    print('  Server ukoncis klavesami Ctrl+C.')
    print('')
    if '--no-browser' not in argv:
        try:
            webbrowser.open('http://localhost:%d' % PORT)
        except Exception:
            pass
    asyncio.ensure_future(heartbeat())
    async with server:
        await server.serve_forever()


STATS_PATH = None        # set by main_cli (None = --no-stats = a Store that lives in memory only)


def open_store(path):
    """The stats Store for the server (loaded from `path`; None = memory only, nothing is ever written)."""
    st = meta.Store(path)
    st.load()
    n = len(st.data['players'])
    if path:
        print('  Statistiky: %s (%d %s)' % (path, n, 'profil' if n == 1 else 'profilu'))
    else:
        print('  Statistiky: vypnuto (--no-stats), profily jen v pameti')
    return st


def parse_args(argv):
    """server.py [port] [--no-browser] [--stats PATH] [--no-stats] -> (port, stats path or None, open browser).
    The env var HMK_STATS works like --stats; the default stats file is <game dir>/stats.json."""
    args = list(argv[1:])
    port = 8095
    stats = os.environ.get('HMK_STATS') or os.path.join(ROOT, 'stats.json')
    browser = True
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--no-browser':
            browser = False
        elif a == '--no-stats':
            stats = None
        elif a == '--stats' and i + 1 < len(args):
            i += 1
            stats = args[i]
        elif a.startswith('--stats='):
            stats = a.split('=', 1)[1] or stats
        elif a.isdigit():
            port = int(a)
        i += 1
    if '--no-stats' in args:
        stats = None
    return port, stats, browser


def main_cli(argv):
    """server.py [port] [--no-browser] [--stats PATH] [--no-stats]"""
    global PORT, STATS_PATH
    try:                  # player names may contain characters the console cannot print
        sys.stdout.reconfigure(errors='replace', line_buffering=True)
    except (AttributeError, ValueError):
        pass
    PORT, STATS_PATH, _ = parse_args(argv)
    LOBBY.store = open_store(STATS_PATH)
    try:
        asyncio.run(main(argv))
    except KeyboardInterrupt:
        print('Server ukoncen.')
    except OSError as e:
        print('Server se nepodarilo spustit: %s' % e)
        print('Port %d je mozna obsazeny. Zkus: python server.py 8096' % PORT)
    finally:
        LOBBY.save_store()
