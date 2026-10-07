#!/usr/bin/env python3
"""Neon Roj LAN server: serves the game and relays co-op messages over WebSocket.

Usage:  python server.py [port]        (default port 8090)
Needs only the Python 3.8+ standard library.
"""
import asyncio
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
ROOT = os.path.dirname(os.path.abspath(__file__))
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_PLAYERS = 4


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
    ips = [ip for ip in ips if not ip.startswith('127.')]
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


class Client:
    def __init__(self, cid, writer):
        self.id = cid
        self.writer = writer
        self.name = 'Pilot'
        self.ship = 'jiskra'
        self.meta = {}
        self.view = 900
        self.ready = False
        self.in_game = False
        self.queue = asyncio.Queue(maxsize=64)
        self.alive = True

    def send_raw(self, data, droppable=False):
        if not self.alive:
            return
        if self.queue.full():
            if droppable:
                return
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(frame(data))

    def send(self, obj):
        self.send_raw(json.dumps(obj, separators=(',', ':')).encode('utf-8'))

    async def pump(self):
        try:
            while self.alive:
                data = await self.queue.get()
                self.writer.write(data)
                await self.writer.drain()
        except (ConnectionError, OSError):
            self.alive = False


class Lobby:
    def __init__(self):
        self.clients = {}
        self.order = []
        self.next_id = 1
        self.host_id = None
        self.started = False
        self.cfg = {'sector': 's1', 'diff': 'normal'}

    def public(self):
        return [{'id': c.id, 'name': c.name, 'ship': c.ship, 'ready': c.ready} for c in (self.clients[i] for i in self.order)]

    def broadcast(self, obj, skip=None):
        data = json.dumps(obj, separators=(',', ':')).encode('utf-8')
        for c in self.clients.values():
            if c.id != skip:
                c.send_raw(data)

    def lobby_update(self):
        self.broadcast({'t': 'lobby', 'players': self.public(), 'hostId': self.host_id, 'started': self.started, 'cfg': self.cfg})

    def join(self, writer):
        c = Client(self.next_id, writer)
        self.next_id += 1
        self.clients[c.id] = c
        self.order.append(c.id)
        if self.host_id is None:
            self.host_id = c.id
        return c

    def leave(self, c):
        if c.id not in self.clients:
            return
        del self.clients[c.id]
        self.order.remove(c.id)
        was_host = c.id == self.host_id
        if was_host:
            self.host_id = self.order[0] if self.order else None
            if self.started:
                self.started = False
                for o in self.clients.values():
                    o.in_game = False
                    o.ready = False
                self.broadcast({'t': 'hostleft'})
        elif self.started and c.in_game and self.host_id in self.clients:
            self.clients[self.host_id].send({'t': 'left', 'id': c.id})
        if not self.order:
            self.started = False
        self.lobby_update()

    def handle(self, c, text):
        if text.startswith('{"t":"snap"'):
            if c.id == self.host_id:
                data = text.encode('utf-8')
                for o in self.clients.values():
                    if o.id != c.id and o.in_game:
                        o.send_raw(data, droppable=True)
            return
        try:
            m = json.loads(text)
        except ValueError:
            return
        t = m.get('t')
        if t == 'hello':
            c.name = str(m.get('name') or 'Pilot')[:16]
            c.ship = str(m.get('ship') or 'jiskra')[:16]
            c.meta = m.get('meta') if isinstance(m.get('meta'), dict) else {}
            c.view = m.get('view') or 900
            c.send({'t': 'welcome', 'id': c.id, 'hostId': self.host_id, 'started': self.started})
            self.lobby_update()
        elif t == 'set':
            if 'name' in m:
                c.name = str(m['name'] or 'Pilot')[:16]
            if 'ship' in m:
                c.ship = str(m['ship'])[:16]
            if 'ready' in m:
                c.ready = bool(m['ready'])
            if 'meta' in m and isinstance(m['meta'], dict):
                c.meta = m['meta']
            if 'view' in m:
                c.view = m['view']
            self.lobby_update()
        elif t == 'cfg' and c.id == self.host_id:
            cfg = m.get('cfg') or {}
            self.cfg = {'sector': str(cfg.get('sector', 's1')), 'diff': str(cfg.get('diff', 'normal'))}
            self.lobby_update()
        elif t == 'start' and c.id == self.host_id and not self.started:
            self.started = True
            roster = []
            for o in (self.clients[i] for i in self.order):
                o.in_game = True
                roster.append({'id': o.id, 'name': o.name, 'ship': o.ship, 'meta': o.meta, 'view': o.view})
            self.broadcast({'t': 'start', 'host': self.host_id, 'sector': self.cfg['sector'], 'diff': self.cfg['diff'], 'roster': roster})
            self.lobby_update()
        elif t == 'end' and c.id == self.host_id:
            self.started = False
            for o in self.clients.values():
                o.in_game = False
                o.ready = False
            self.lobby_update()
        elif t == 'to' and c.id == self.host_id:
            target = self.clients.get(m.get('id'))
            if target:
                target.send({'t': 'ev', 'm': m.get('m')})
        elif t == 'leavegame':
            if self.started and c.in_game and c.id != self.host_id:
                c.in_game = False
                c.ready = False
                if self.host_id in self.clients:
                    self.clients[self.host_id].send({'t': 'left', 'id': c.id})
                self.lobby_update()
        elif t in ('in', 'lvact', 'chestok'):
            if self.started and c.in_game and self.host_id in self.clients and c.id != self.host_id:
                m['from'] = c.id
                self.clients[self.host_id].send(m)


LOBBY = Lobby()
URLS = []


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


def http_response(writer, code, ctype, body, extra=''):
    reason = {200: 'OK', 404: 'Not Found', 405: 'Method Not Allowed'}.get(code, 'OK')
    head = ('HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nCache-Control: no-store\r\nConnection: close\r\n%s\r\n'
            % (code, reason, ctype, len(body), extra)).encode('latin-1')
    writer.write(head + body)


def game_page():
    with open(os.path.join(ROOT, 'index.html'), 'rb') as f:
        html = f.read().decode('utf-8')
    flag = '<script>window.NEONROJ_LAN=' + json.dumps({'urls': URLS}) + ';</script>'
    return html.replace('<!--LAN-->', flag, 1).encode('utf-8')


async def websocket(reader, writer, headers):
    key = headers.get('sec-websocket-key', '')
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode('latin-1')).digest()).decode('latin-1')
    writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n' % accept).encode('latin-1'))
    await writer.drain()
    if len(LOBBY.clients) >= MAX_PLAYERS or LOBBY.started:
        busy = Client(0, writer)
        writer.write(frame(json.dumps({'t': 'full' if not LOBBY.started else 'lobby', 'players': LOBBY.public(), 'hostId': LOBBY.host_id, 'started': LOBBY.started}).encode('utf-8')))
        await writer.drain()
        writer.close()
        return
    c = LOBBY.join(writer)
    pump = asyncio.ensure_future(c.pump())
    print('  + %s pripojen (%d/%d)' % (writer.get_extra_info('peername')[0], len(LOBBY.clients), MAX_PLAYERS))
    parts = []
    try:
        while True:
            b1, b2 = await reader.readexactly(2)
            op = b1 & 0x0F
            fin = b1 & 0x80
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack('!H', await reader.readexactly(2))[0]
            elif n == 127:
                n = struct.unpack('!Q', await reader.readexactly(8))[0]
            mask = await reader.readexactly(4) if b2 & 0x80 else b''
            data = await reader.readexactly(n) if n else b''
            if mask:
                data = unmask(data, mask)
            if op == 8:
                break
            if op == 9:
                c.writer.write(frame(data, 10))
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
        print('  - %s odpojen (%d/%d)' % (c.name, len(LOBBY.clients), MAX_PLAYERS))
        try:
            writer.close()
        except OSError:
            pass


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
        elif path.split('?')[0] in ('/', '/index.html'):
            http_response(writer, 200, 'text/html; charset=utf-8', game_page())
        else:
            http_response(writer, 404, 'text/plain; charset=utf-8', b'Nenalezeno')
        await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except OSError:
            pass


async def main():
    global URLS
    server = await asyncio.start_server(handle, '0.0.0.0', PORT)
    URLS = ['http://%s:%d' % (ip, PORT) for ip in lan_ips()]
    print('')
    print('  NEON ROJ - co-op server bezi.')
    print('  Ty:       http://localhost:%d' % PORT)
    for u in URLS:
        print('  Ostatni:  %s' % u)
    print('')
    print('  Server ukoncis klavesami Ctrl+C.')
    print('')
    if '--no-browser' not in sys.argv:
        try:
            webbrowser.open('http://localhost:%d' % PORT)
        except Exception:
            pass
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Server ukoncen.')
    except OSError as e:
        print('Server se nepodarilo spustit: %s' % e)
        print('Port %d je mozna obsazeny. Zkus: python server.py 8091' % PORT)
