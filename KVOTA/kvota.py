#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KVÓTA — dystopický padající-blokový puzzle
Ministerstvo stavebních bloků · Sektor 7

Spuštění:   python kvota.py        (vyžaduje pygame nebo pygame-ce)

Ovládání:   ← →  pohyb            ↑ / X  rotace po směru
            ↓    zrychlený pád     Z / Ctrl  rotace proti směru
            MEZERNÍK  okamžitý shoz
            C / Shift  zadržet blok
            ENTER  (LAN) spustit CENZURU
            P pauza · M hudba · F11 celá obrazovka · Esc zpět

Highscore:  highscores.csv (vedle skriptu, oddělovač ';', UTF-8)
Zvuky:      složka sounds/ — při prvním spuštění se syntetizují jako WAV.
            Libovolný soubor můžeš nahradit vlastním (stejné jméno,
            .wav / .ogg / .mp3).
LAN režim:  SABOTÁŽ — TCP port 50505, hledání hostitelů UDP port 50506.
"""
import os
import sys
import csv
import json
import math
import time
import array
import wave
import queue
import random
import socket
import getpass
import datetime
import threading

try:
    import pygame
except ImportError:
    print("Chybí knihovna pygame. Nainstaluj ji příkazem:\n    python -m pip install pygame-ce")
    sys.exit(1)

# ---------------------------------------------------------------- konstanty
BASE = os.path.dirname(os.path.abspath(__file__))
HS_FILE = os.path.join(BASE, "highscores.csv")
SND_DIR = os.path.join(BASE, "sounds")

W, H = 1120, 720
CELL = 30
COLS, ROWS, HIDDEN = 10, 20, 2
TR = ROWS + HIDDEN
FPS = 60
PORT = 50505
DISC_PORT = 50506
PROTO = 1
DAS_T, ARR_T = 0.16, 0.045
LOCK_DELAY = 0.5

BG = (9, 10, 12)
PANEL = (18, 20, 22)
EDGE = (58, 62, 56)
GRIDC = (26, 29, 31)
TEXT = (204, 210, 192)
DIM = (112, 118, 104)
ACID = (164, 255, 64)
WARN = (255, 58, 48)
AMBER = (255, 176, 0)
AMBER_D = (120, 84, 0)
CYAN = (0, 230, 210)

PIECE_COL = {
    'I': (40, 224, 200),   # toxický tyrkys
    'O': (232, 197, 71),   # výstražná žlutá
    'T': (190, 80, 255),   # propagandistická fialová
    'S': (143, 224, 61),   # kyselinová zelená
    'Z': (255, 59, 59),    # poplachová červená
    'J': (74, 125, 255),   # policejní modrá
    'L': (255, 138, 42),   # rez
    'G': (78, 80, 76),     # beton (garbage)
}

SLOGANY = [
    "POSLUŠNOST JE PRODUKTIVITA", "KAŽDÝ BLOK SE POČÍTÁ",
    "MEZERA V ŘADĚ JE MEZERA V LOAJALITĚ", "SEKTOR 7 TĚ SLEDUJE",
    "SPLNĚNÁ KVÓTA = TEPLÁ POLÉVKA", "NEPLÁNOVANÉ PŘESTÁVKY JSOU HLÁŠENY",
    "ŘÁD · PŘÍDĚL · PRÁCE", "OBČANE, SKLÁDEJ",
    "POCHYBNOSTI HLAS SVÉMU DOZORČÍMU", "DNEŠNÍ PŘÍDĚL KYSLÍKU: 94 %",
    "SMÍCH BEZ POVOLENÍ JE PŘESTUPEK", "BETON NELŽE",
]

# ---------------------------------------------------------------- tvary + SRS
SHAPES = {
    'I': (4, [(0, 1), (1, 1), (2, 1), (3, 1)]),
    'O': (2, [(0, 0), (1, 0), (0, 1), (1, 1)]),
    'T': (3, [(1, 0), (0, 1), (1, 1), (2, 1)]),
    'S': (3, [(1, 0), (2, 0), (0, 1), (1, 1)]),
    'Z': (3, [(0, 0), (1, 0), (1, 1), (2, 1)]),
    'J': (3, [(0, 0), (0, 1), (1, 1), (2, 1)]),
    'L': (3, [(2, 0), (0, 1), (1, 1), (2, 1)]),
}
ROTS = {}
for _k, (_n, _c) in SHAPES.items():
    _r = [_c]
    for _ in range(3):
        _r.append([(_n - 1 - y, x) for x, y in _r[-1]])
    ROTS[_k] = _r

# SRS kick tabulky (y nahoru, při použití se převrací)
KICKS = {
    (0, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (1, 0): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (2, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (2, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (3, 2): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (3, 0): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (0, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
}
KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
}


# ================================================================ HERNÍ LOGIKA
class Game:
    """Jedna hrací plocha. Bez grafiky, bez vstupu — čistá logika."""

    def __init__(self, seed=None, versus=False):
        self.rng = random.Random(seed)
        self.board = [[None] * COLS for _ in range(TR)]
        self.bag = []
        self.nexts = [self._draw() for _ in range(5)]
        self.hold = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.combo = -1
        self.b2b = False
        self.over = False
        self.events = []
        self.versus = versus
        self.pending = []      # příchozí beton [(počet, díra)]
        self.outgoing = 0      # odchozí útok
        self.hack = 0          # měřič cenzury 0..100
        self.time = 0.0
        self.grav_t = 0.0
        self.lock_t = 0.0
        self.lock_moves = 0
        self.spawn()

    # --- generátor 7-bag
    def _draw(self):
        if not self.bag:
            self.bag = list("IOTSZJL")
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self, kind=None):
        if kind is None:
            kind = self.nexts.pop(0)
            self.nexts.append(self._draw())
        self.kind, self.rot = kind, 0
        self.x = 4 if kind == 'O' else 3
        self.y = HIDDEN - 2 if kind == 'I' else HIDDEN - 1
        self.grav_t = self.lock_t = 0.0
        self.lock_moves = 0
        self.lowest = self.y
        if self.collides(self.x, self.y, self.rot):
            self.over = True
            self.events.append(('gameover',))
            return
        if not self.collides(self.x, self.y + 1, self.rot):
            self.y += 1

    def cells(self, x=None, y=None, rot=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        rot = self.rot if rot is None else rot
        return [(x + cx, y + cy) for cx, cy in ROTS[self.kind][rot]]

    def collides(self, x, y, rot):
        for cx, cy in ROTS[self.kind][rot]:
            X, Y = x + cx, y + cy
            if X < 0 or X >= COLS or Y >= TR:
                return True
            if Y >= 0 and self.board[Y][X]:
                return True
        return False

    def grounded(self):
        return self.collides(self.x, self.y + 1, self.rot)

    def _after_move(self):
        if self.grounded() and self.lock_moves < 15:
            self.lock_t = 0.0
            self.lock_moves += 1

    def move(self, dx):
        if self.over or self.collides(self.x + dx, self.y, self.rot):
            return False
        self.x += dx
        self._after_move()
        self.events.append(('move',))
        return True

    def rotate(self, d):
        if self.over:
            return False
        if self.kind == 'O':
            self.events.append(('rotate',))
            return True
        new = (self.rot + d) % 4
        table = KICKS_I if self.kind == 'I' else KICKS
        for dx, dy in table[(self.rot, new)]:
            if not self.collides(self.x + dx, self.y - dy, new):
                self.x += dx
                self.y -= dy
                self.rot = new
                self._after_move()
                self.events.append(('rotate',))
                return True
        return False

    def ghost_y(self):
        y = self.y
        while not self.collides(self.x, y + 1, self.rot):
            y += 1
        return y

    def hard_drop(self):
        if self.over:
            return
        d = self.ghost_y() - self.y
        self.y += d
        self.score += 2 * d
        self.events.append(('drop', d))
        self.lock()

    def do_hold(self):
        if self.over or self.hold_used:
            return
        k = self.kind
        if self.hold is None:
            self.hold = k
            self.spawn()
        else:
            k2, self.hold = self.hold, k
            self.spawn(k2)
        self.hold_used = True
        self.events.append(('hold',))

    def gravity(self):
        lv = min(self.level, 20)
        return (0.8 - (lv - 1) * 0.007) ** (lv - 1)

    def update(self, dt, soft=False):
        if self.over:
            return
        self.time += dt
        interval = self.gravity()
        if soft:
            interval = min(interval, 0.035)
        if self.grounded():
            self.grav_t = 0.0
            self.lock_t += dt
            if self.lock_t >= LOCK_DELAY:
                self.lock()
            return
        self.grav_t += dt
        while self.grav_t >= interval and not self.over:
            self.grav_t -= interval
            if self.grounded():
                break
            self.y += 1
            self.lock_t = 0.0
            if soft:
                self.score += 1
            if self.y > self.lowest:
                self.lowest = self.y
                self.lock_moves = 0

    def lock(self):
        above = True
        for X, Y in self.cells():
            if 0 <= Y < TR:
                self.board[Y][X] = self.kind
            if Y >= HIDDEN:
                above = False
        full = [r for r in range(TR) if all(self.board[r])]
        n = len(full)
        if n:
            rows = [(r - HIDDEN, list(self.board[r])) for r in full]
            for r in sorted(full, reverse=True):
                del self.board[r]
            for _ in range(n):
                self.board.insert(0, [None] * COLS)
            b2b_bonus = (n == 4 and self.b2b)
            base = [0, 100, 300, 500, 800][n] * self.level
            if b2b_bonus:
                base = base * 3 // 2
            self.b2b = (n == 4)
            self.combo += 1
            if self.combo > 0:
                base += 50 * self.combo * self.level
            self.score += base
            self.lines += n
            nl = self.lines // 10 + 1
            if nl > self.level:
                self.level = nl
                self.events.append(('levelup',))
            self.events.append(('clear', n, rows, self.combo, b2b_bonus))
            if self.versus:
                atk = [0, 0, 1, 2, 4][n] + (1 if b2b_bonus else 0)
                atk += (1 if self.combo >= 2 else 0) + (1 if self.combo >= 4 else 0)
                while atk > 0 and self.pending:
                    c, g = self.pending[0]
                    if c <= atk:
                        atk -= c
                        self.pending.pop(0)
                    else:
                        self.pending[0] = (c - atk, g)
                        atk = 0
                self.outgoing += atk
                self.hack = min(100, self.hack + [0, 10, 20, 35, 50][n])
        else:
            self.combo = -1
            self.events.append(('lock',))
            if above:
                self.over = True
                self.events.append(('gameover',))
                return
            if self.pending:
                self._apply_garbage()
        self.hold_used = False
        if not self.over:
            self.spawn()

    def _apply_garbage(self):
        total = 0
        for c, g in self.pending:
            for _ in range(c):
                top = self.board.pop(0)
                if any(top):
                    self.over = True
                row = ['G'] * COLS
                row[g % COLS] = None
                self.board.append(row)
                total += 1
        self.pending = []
        self.events.append(('garbage', total))
        if self.over:
            self.events.append(('gameover',))

    def pending_total(self):
        return sum(c for c, _ in self.pending)

    # --- export pro vykreslení / síť
    def visible_rows(self):
        return self.board[HIDDEN:]

    def piece_visible(self):
        if self.over:
            return []
        return [(x, y - HIDDEN) for x, y in self.cells() if y >= HIDDEN]

    def ghost_visible(self):
        if self.over:
            return []
        gy = self.ghost_y()
        return [(x, y - HIDDEN) for x, y in self.cells(y=gy) if y >= HIDDEN]

    def board_string(self):
        return "".join((c or '.') for row in self.visible_rows() for c in row)


# ================================================================ HIGHSCORE (CSV)
HS_FIELDS = ["jmeno", "skore", "radky", "smena", "cas_s", "datum"]


def load_scores():
    rows = []
    if not os.path.exists(HS_FILE):
        return rows
    try:
        with open(HS_FILE, newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f, delimiter=';'):
                try:
                    rows.append({
                        "jmeno": r.get("jmeno", "?"),
                        "skore": int(r.get("skore", 0)),
                        "radky": int(r.get("radky", 0)),
                        "smena": int(r.get("smena", 1)),
                        "cas_s": int(float(r.get("cas_s", 0) or 0)),
                        "datum": r.get("datum", ""),
                    })
                except (ValueError, TypeError):
                    pass
    except OSError:
        pass
    rows.sort(key=lambda r: r["skore"], reverse=True)
    return rows


def save_score(name, score, lines, level, secs):
    rows = load_scores()
    entry = {"jmeno": name, "skore": score, "radky": lines, "smena": level,
             "cas_s": int(secs), "datum": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    rows.append(entry)
    rows.sort(key=lambda r: r["skore"], reverse=True)
    rows = rows[:100]
    try:
        with open(HS_FILE, "w", newline='', encoding='utf-8-sig') as f:
            wr = csv.DictWriter(f, fieldnames=HS_FIELDS, delimiter=';')
            wr.writeheader()
            wr.writerows(rows)
    except OSError as e:
        print("Nelze uložit highscore:", e)
    return rows.index(entry) + 1 if entry in rows else None


def qualifies(score):
    if score <= 0:
        return False
    rows = load_scores()
    return len(rows) < 10 or score > rows[9]["skore"]


# ================================================================ SYNTÉZA ZVUKU
SR = 22050
NOTE_IDX = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6,
            'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}


def nf(n):
    midi = 12 * (int(n[-1]) + 1) + NOTE_IDX[n[:-1]]
    return 440.0 * 2 ** ((midi - 69) / 12)


def newbuf(sec):
    return array.array('d', [0.0]) * int(sec * SR)


def tone(buf, start, dur, f0, f1=None, kind='sq', vol=0.3, duty=0.5,
         attack=0.004, curve=1.0, vib=0.0, lp=None, rel=0.01):
    f1 = f0 if f1 is None else f1
    n = int(dur * SR)
    s0 = int(start * SR)
    a = max(1, int(attack * SR))
    r = max(1, int(rel * SR))
    ph = 0.0
    y = 0.0
    L = len(buf)
    two_pi = 2 * math.pi
    rnd = random.random
    for i in range(n):
        j = s0 + i
        if j >= L:
            break
        t = i / n
        f = f0 + (f1 - f0) * t
        if vib:
            f *= 1 + vib * math.sin(two_pi * 5.5 * i / SR)
        ph += f / SR
        p = ph - int(ph)
        if kind == 'sq':
            v = 1.0 if p < duty else -1.0
        elif kind == 'tri':
            v = 4 * abs(p - 0.5) - 1
        elif kind == 'saw':
            v = 2 * p - 1
        elif kind == 'sin':
            v = math.sin(two_pi * p)
        else:
            v = rnd() * 2 - 1
        if lp is not None:
            y += lp * (v - y)
            v = y
        env = (i / a if i < a else 1.0) * ((n - i) / r if n - i < r else 1.0)
        if curve:
            env *= (1 - t) ** curve
        buf[j] += v * vol * env


def write_wav(path, buf):
    data = array.array('h', (int(max(-1.0, min(1.0, x)) * 32000) for x in buf))
    if sys.byteorder == 'big':
        data.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def _arp(freqs, step, dur, kind='sq', vol=0.18, total=None, duty=0.25):
    b = newbuf(total or (step * len(freqs) + dur + 0.05))
    for i, f in enumerate(freqs):
        tone(b, i * step, dur, f, kind=kind, vol=vol, duty=duty, curve=1.2)
    return b


def sfx_move():
    b = newbuf(0.04)
    tone(b, 0, 0.03, 300, 240, 'sq', 0.10, curve=2)
    return b


def sfx_rotate():
    b = newbuf(0.07)
    tone(b, 0, 0.06, 480, 880, 'sq', 0.11, duty=0.25, curve=1)
    return b


def sfx_lock():
    b = newbuf(0.14)
    tone(b, 0, 0.12, 150, 55, 'tri', 0.55, curve=2)
    tone(b, 0, 0.05, 0, kind='noise', vol=0.25, curve=3, lp=0.35)
    return b


def sfx_drop():
    b = newbuf(0.24)
    tone(b, 0, 0.2, 260, 40, 'sq', 0.22, curve=1.6, duty=0.4)
    tone(b, 0, 0.18, 0, kind='noise', vol=0.35, curve=2, lp=0.25)
    return b


def sfx_hold():
    b = newbuf(0.12)
    tone(b, 0, 0.045, 520, kind='sq', vol=0.14, duty=0.25, curve=0.5)
    tone(b, 0.05, 0.06, 780, kind='sq', vol=0.14, duty=0.25, curve=1)
    return b


def sfx_clear():
    b = _arp([nf('A4'), nf('C5'), nf('E5')], 0.055, 0.14)
    tone(b, 0, 0.3, 0, kind='noise', vol=0.12, curve=1.5, lp=0.7)
    return b


def sfx_quad():
    b = newbuf(0.9)
    for i, n in enumerate(['A4', 'C5', 'E5', 'A5', 'C6', 'E6']):
        tone(b, i * 0.06, 0.25, nf(n), kind='sq', vol=0.15, duty=0.25, curve=1, vib=0.01)
    tone(b, 0, 0.8, 110, 880, 'saw', 0.10, curve=1.2)
    tone(b, 0.35, 0.5, 0, kind='noise', vol=0.2, curve=1.5, lp=0.5)
    return b


def sfx_levelup():
    return _arp([nf(n) for n in ['E4', 'A4', 'C5', 'E5', 'A5']], 0.07, 0.16, kind='tri', vol=0.35)


def sfx_gameover():
    b = newbuf(1.9)
    tone(b, 0, 1.7, 440, 40, 'saw', 0.25, curve=0.7, vib=0.03)
    tone(b, 0, 1.7, 443, 38, 'sq', 0.12, curve=0.7, duty=0.3)
    tone(b, 1.0, 0.8, 0, kind='noise', vol=0.2, curve=1, lp=0.15)
    return b


def sfx_garbage():
    b = newbuf(0.35)
    tone(b, 0, 0.3, 90, 55, 'saw', 0.35, curve=1)
    tone(b, 0, 0.25, 0, kind='noise', vol=0.25, curve=1.5, lp=0.2)
    return b


def sfx_hack():
    b = newbuf(0.7)
    r = random.Random(7)
    for i in range(18):
        f = r.uniform(150, 2400)
        tone(b, i * 0.035, 0.035, f, f * r.uniform(0.5, 1.5), 'sq', 0.13, duty=r.choice([0.125, 0.25, 0.5]), curve=0)
    tone(b, 0, 0.65, 0, kind='noise', vol=0.12, curve=1, lp=0.9)
    return b


def sfx_select():
    b = newbuf(0.13)
    tone(b, 0, 0.05, 660, kind='sq', vol=0.14, duty=0.25, curve=0.5)
    tone(b, 0.05, 0.07, 990, kind='sq', vol=0.14, duty=0.25, curve=1)
    return b


def sfx_tick():
    b = newbuf(0.03)
    tone(b, 0, 0.02, 900, kind='sq', vol=0.08, curve=1)
    return b


def sfx_count():
    b = newbuf(0.2)
    tone(b, 0, 0.15, 440, kind='sq', vol=0.18, duty=0.5, curve=0.8)
    return b


def sfx_go():
    b = newbuf(0.45)
    tone(b, 0, 0.4, 880, kind='sq', vol=0.18, duty=0.5, curve=1)
    tone(b, 0, 0.4, 440, kind='saw', vol=0.1, curve=1)
    return b


def sfx_win():
    return _arp([nf(n) for n in ['C5', 'E5', 'G5', 'C6', 'G5', 'C6']], 0.09, 0.2, vol=0.16)


def sfx_lose():
    return _arp([nf(n) for n in ['E4', 'D#4', 'D4', 'C#4']], 0.18, 0.3, kind='saw', vol=0.2)


def sfx_alarm():
    b = newbuf(0.6)
    tone(b, 0, 0.28, 660, 520, 'sq', 0.1, curve=0.3, duty=0.5)
    tone(b, 0.3, 0.28, 660, 520, 'sq', 0.1, curve=0.3, duty=0.5)
    return b


SFX = {
    "move": sfx_move, "rotate": sfx_rotate, "lock": sfx_lock, "drop": sfx_drop,
    "hold": sfx_hold, "clear": sfx_clear, "quad": sfx_quad, "levelup": sfx_levelup,
    "gameover": sfx_gameover, "garbage": sfx_garbage, "hack": sfx_hack,
    "select": sfx_select, "tick": sfx_tick, "count": sfx_count, "go": sfx_go,
    "win": sfx_win, "lose": sfx_lose, "alarm": sfx_alarm,
}


def gen_music():
    """Vlastní temná aranžmá lidové písně Korobejniki (volné dílo) + vlastní mezihra."""
    bpm = 150
    bt = 60 / bpm
    A = [('E5', 1), ('B4', .5), ('C5', .5), ('D5', 1), ('C5', .5), ('B4', .5),
         ('A4', 1), ('A4', .5), ('C5', .5), ('E5', 1), ('D5', .5), ('C5', .5),
         ('B4', 1.5), ('C5', .5), ('D5', 1), ('E5', 1),
         ('C5', 1), ('A4', 1), ('A4', 2),
         (None, .5), ('D5', 1), ('F5', .5), ('A5', 1), ('G5', .5), ('F5', .5),
         ('E5', 1.5), ('C5', .5), ('E5', 1), ('D5', .5), ('C5', .5),
         ('B4', 1), ('B4', .5), ('C5', .5), ('D5', 1), ('E5', 1),
         ('C5', 1), ('A4', 1), ('A4', 1), (None, 1)]
    Bm = [('A4', 2), ('E4', 2), ('F4', 2), ('E4', 2), ('D4', 2), ('C4', 2), ('B3', 2), ('E4', 2),
          ('A4', 1), ('B4', 1), ('C5', 2), ('B4', 1), ('A4', 1), ('G#4', 2),
          ('A4', 2), ('E4', 2), ('A3', 4)]
    bassA = ['E2', 'A2', 'E2', 'A2', 'D2', 'C2', 'E2', 'A2']
    bassB = ['A1', 'F1', 'D2', 'E1', 'A1', 'E1', 'A1', 'A1']
    total_beats = 96
    buf = newbuf(total_beats * bt + 0.1)
    lead = newbuf(total_beats * bt + 0.1)

    def melody(seq, start_beat, kind, vol, duty, oct_shift=1.0):
        b = start_beat
        for n, d in seq:
            if n:
                tone(lead, b * bt, d * bt * 0.92, nf(n) * oct_shift, kind=kind, vol=vol,
                     duty=duty, curve=0.6, vib=0.005)
            b += d

    melody(A, 0, 'sq', 0.16, 0.25)
    melody(A, 32, 'sq', 0.16, 0.125)
    melody(Bm, 64, 'tri', 0.30, 0.5)
    # ozvěna (betonová hala)
    dl = int(0.75 * bt * SR)
    for i in range(len(lead) - 1, dl - 1, -1):
        lead[i] += lead[i - dl] * 0.28
    for i in range(len(buf)):
        buf[i] += lead[i]
    # basa — oktávové osminy (A), dlouhé pily (B)
    for part, off in ((0, 0), (1, 32)):
        for bar, root in enumerate(bassA):
            for e in range(8):
                f = nf(root) * (2 if e % 2 else 1)
                tone(buf, (off + bar * 4 + e * 0.5) * bt, 0.45 * bt, f, kind='saw', vol=0.13, curve=1.4, lp=0.3)
    for bar, root in enumerate(bassB):
        tone(buf, (64 + bar * 4) * bt, 3.9 * bt, nf(root), kind='saw', vol=0.16, curve=0.5, lp=0.12)
        tone(buf, (64 + bar * 4) * bt, 3.9 * bt, nf(root) * 1.006, kind='saw', vol=0.10, curve=0.5, lp=0.12)
    # bicí
    for beat in range(64):
        s = beat * bt
        if beat % 2 == 0:
            tone(buf, s, 0.14, 130, 38, 'sin', 0.55, curve=1.5)
        else:
            tone(buf, s, 0.11, 0, kind='noise', vol=0.20, curve=2, lp=0.45)
        tone(buf, s + bt / 2, 0.03, 0, kind='noise', vol=0.07, curve=2)
    for beat in range(64, 96, 4):
        tone(buf, beat * bt, 0.3, 90, 30, 'sin', 0.6, curve=1.2)
        tone(buf, (beat + 2.5) * bt, 0.05, 0, kind='noise', vol=0.08, curve=2)
    return buf


class Sound:
    def __init__(self):
        self.ok = False
        self.sfx = {}
        self.music_path = None
        self.music_on = True
        self.muted = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(20)
            self.ok = True
        except Exception as e:
            print("Zvuk nedostupný:", e)

    @staticmethod
    def _find(name):
        for ext in (".ogg", ".mp3", ".wav"):
            p = os.path.join(SND_DIR, name + ext)
            if os.path.exists(p):
                return p
        return None

    def load(self, progress=None):
        try:
            os.makedirs(SND_DIR, exist_ok=True)
        except OSError:
            pass
        items = list(SFX.items())
        for i, (name, fn) in enumerate(items):
            if progress:
                progress(i / (len(items) + 4), "Kalibruji sirény: " + name)
            path = self._find(name)
            if not path:
                path = os.path.join(SND_DIR, name + ".wav")
                try:
                    write_wav(path, fn())
                except OSError:
                    path = None
            if self.ok and path:
                try:
                    self.sfx[name] = pygame.mixer.Sound(path)
                except Exception as e:
                    print("Nelze načíst", path, e)
        path = self._find("music")
        if not path:
            if progress:
                progress(len(items) / (len(items) + 4), "Skládám hymnu sektoru… (jen při prvním spuštění)")
            path = os.path.join(SND_DIR, "music.wav")
            try:
                write_wav(path, gen_music())
            except OSError:
                path = None
        self.music_path = path
        if progress:
            progress(1.0, "Hotovo.")

    def play(self, name, vol=1.0):
        if self.ok and not self.muted and name in self.sfx:
            s = self.sfx[name]
            s.set_volume(vol)
            s.play()

    def music(self, on=True):
        if not self.ok or not self.music_path:
            return
        try:
            if on and self.music_on:
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.load(self.music_path)
                    pygame.mixer.music.set_volume(0.42)
                    pygame.mixer.music.play(-1)
            else:
                pygame.mixer.music.stop()
        except Exception as e:
            print("Hudba:", e)

    def toggle_music(self):
        self.music_on = not self.music_on
        self.music(self.music_on)


# ================================================================ SÍŤ
def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips = sorted(i for i in ips if not i.startswith("127."))
    return ips or ["127.0.0.1"]


class Net:
    """Řádkově oddělený JSON přes TCP."""

    def __init__(self, sock):
        self.sock = sock
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        sock.settimeout(None)
        self.q = queue.Queue()
        self.alive = True
        self.lock = threading.Lock()
        threading.Thread(target=self._rx, daemon=True).start()

    def _rx(self):
        buf = b""
        try:
            while True:
                d = self.sock.recv(65536)
                if not d:
                    break
                buf += d
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        try:
                            self.q.put(json.loads(line.decode("utf-8")))
                        except ValueError:
                            pass
        except OSError:
            pass
        self.alive = False

    def send(self, msg):
        if not self.alive:
            return
        try:
            data = (json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            with self.lock:
                self.sock.sendall(data)
        except OSError:
            self.alive = False

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class HostServer:
    def __init__(self, name):
        self.name = name
        self.conn = None
        self.error = None
        self.running = True
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.srv.bind(("", PORT))
            self.srv.listen(1)
            self.srv.settimeout(0.5)
        except OSError as e:
            self.error = "Port %d je obsazen (%s)" % (PORT, e)
            self.running = False
            return
        threading.Thread(target=self._accept, daemon=True).start()
        threading.Thread(target=self._beacon, daemon=True).start()

    def _accept(self):
        while self.running and self.conn is None:
            try:
                c, _ = self.srv.accept()
                self.conn = c
            except socket.timeout:
                continue
            except OSError:
                break
        try:
            self.srv.close()
        except OSError:
            pass

    def _beacon(self):
        try:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            return
        msg = ("KVOTA|%d|%s" % (PROTO, self.name)).encode("utf-8")
        while self.running and self.conn is None:
            targets = {"255.255.255.255", "127.0.0.1"}
            for ip in lan_ips():
                p = ip.split(".")
                if len(p) == 4:
                    targets.add(".".join(p[:3] + ["255"]))
            for t in targets:
                try:
                    u.sendto(msg, (t, DISC_PORT))
                except OSError:
                    pass
            time.sleep(1.0)
        u.close()

    def stop(self):
        self.running = False
        try:
            self.srv.close()
        except OSError:
            pass


class Discovery:
    def __init__(self):
        self.hosts = {}   # ip -> (jméno, čas)
        self.sock = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", DISC_PORT))
            s.setblocking(False)
            self.sock = s
        except OSError:
            self.sock = None

    def poll(self):
        if self.sock:
            while True:
                try:
                    data, addr = self.sock.recvfrom(1024)
                except (BlockingIOError, OSError):
                    break
                try:
                    tag, _v, name = data.decode("utf-8").split("|", 2)
                    if tag == "KVOTA":
                        self.hosts[addr[0]] = (name, time.time())
                except ValueError:
                    pass
        now = time.time()
        for ip in [i for i, (_, t) in self.hosts.items() if now - t > 4]:
            del self.hosts[ip]
        return sorted(self.hosts.items())

    def close(self):
        if self.sock:
            self.sock.close()


# ================================================================ VSTUP (DAS)
class DAS:
    def __init__(self):
        self.dir = 0
        self.t = 0.0

    def press(self, d, g):
        self.dir = d
        self.t = DAS_T
        g.move(d)

    def release(self, d):
        if self.dir != d:
            return
        keys = pygame.key.get_pressed()
        other = pygame.K_RIGHT if d == -1 else pygame.K_LEFT
        if keys[other]:
            self.dir = -d
            self.t = DAS_T
        else:
            self.dir = 0

    def update(self, dt, g):
        if not self.dir:
            return
        self.t -= dt
        while self.t <= 0:
            if not g.move(self.dir):
                self.t = 0
                break
            self.t += ARR_T


# ================================================================ APLIKACE
def _scale(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _font(size, bold=False):
    for name in ("consolas", "dejavusansmono", "couriernew", "lucidaconsole", "liberationmono"):
        try:
            p = pygame.font.match_font(name, bold=bold)
        except Exception:
            p = None
        if p:
            try:
                return pygame.font.Font(p, size)
            except Exception:
                pass
    f = pygame.font.Font(None, int(size * 1.3))
    f.set_bold(bold)
    return f


MENU = ["SAMOSTATNÁ SMĚNA", "LAN: ZALOŽIT SABOTÁŽ", "LAN: PŘIPOJIT SE",
        "ŽEBŘÍČEK VZORNÝCH OBČANŮ", "PRAVIDLA SABOTÁŽE", "OPUSTIT SEKTOR"]


class App:
    def __init__(self, screen, sound):
        self.screen = screen
        self.canvas = pygame.Surface((W, H))
        self.snd = sound
        self.f_huge = _font(92, True)
        self.f_big = _font(46, True)
        self.f_med = _font(26, True)
        self.f_norm = _font(19)
        self.f_normb = _font(19, True)
        self.f_small = _font(15)
        self.f_tiny = _font(12)
        self.block_cache = {}
        self._build_overlays()
        self.state = "menu"
        self.menu_i = 0
        self.t = 0.0
        self.quit = False
        self.das = DAS()
        self.particles = []
        self.flashes = []
        self.shake = 0.0
        self.glitch = 0.0
        self.banner = None      # (text, barva, čas)
        self.ticker_x = 0.0
        self.ticker_img = self.f_small.render("   ///   ".join(SLOGANY) + "   ///   ", True, AMBER)
        self.eye_blink = 0.0
        scores = load_scores()
        self.player_name = scores[0]["jmeno"] if scores else self._os_user()
        self.last_name = self._last_name() or self.player_name
        self.game = None
        self.paused = False
        self.net = None
        self.host = None
        self.disc = None
        self.join_i = 0
        self.join_ip = ""
        self.join_status = ""
        self.connecting = False
        self.connect_result = None
        self.entry_active = False
        self.entry_text = ""
        self.saved_rank = None
        self.danger_alarm = 0.0

    # ---------------------------------------------------------- pomocné
    @staticmethod
    def _os_user():
        try:
            return getpass.getuser()[:12].upper()
        except Exception:
            return "OBČAN"

    @staticmethod
    def _last_name():
        rows = load_scores()
        if not rows:
            return None
        return max(rows, key=lambda r: r["datum"])["jmeno"]

    def _build_overlays(self):
        self.scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 3):
            pygame.draw.line(self.scan, (0, 0, 0, 60), (0, y), (W, y))
        v = pygame.Surface((64, 40), pygame.SRCALPHA)
        for y in range(40):
            for x in range(64):
                dx, dy = (x - 31.5) / 32, (y - 19.5) / 20
                d = math.sqrt(dx * dx + dy * dy)
                v.set_at((x, y), (0, 0, 0, int(max(0, min(230, (d - 0.6) * 380)))))
        self.vig = pygame.transform.smoothscale(v, (W, H))
        self.bg = pygame.Surface((W, H))
        self.bg.fill(BG)
        for x in range(0, W, 40):
            pygame.draw.line(self.bg, (15, 17, 19), (x, 0), (x, H))
        for y in range(0, H, 40):
            pygame.draw.line(self.bg, (15, 17, 19), (0, y), (W, y))
        r = random.Random(3)
        for _ in range(900):
            c = r.randint(14, 30)
            self.bg.set_at((r.randrange(W), r.randrange(H)), (c, c, c - 2))
        big = _font(150, True).render("SEKTOR 7", True, (17, 19, 20))
        self.bg.blit(big, big.get_rect(center=(W // 2, H // 2 + 40)))

    def block(self, kind, size):
        key = (kind, size)
        s = self.block_cache.get(key)
        if s:
            return s
        c = PIECE_COL[kind]
        s = pygame.Surface((size, size))
        dark, light, mid = _scale(c, 0.42), _scale(c, 1.35), _scale(c, 0.72)
        s.fill(dark)
        pygame.draw.rect(s, c, (1, 1, size - 2, size - 2))
        pygame.draw.line(s, light, (1, 1), (size - 3, 1), 2)
        pygame.draw.line(s, light, (1, 1), (1, size - 3), 2)
        pygame.draw.line(s, dark, (2, size - 2), (size - 2, size - 2), 2)
        pygame.draw.line(s, dark, (size - 2, 2), (size - 2, size - 2), 2)
        if kind == 'G':
            for k in range(-size, size, 8):
                pygame.draw.line(s, (58, 60, 56), (k, size), (k + size, 0), 3)
            pygame.draw.rect(s, (40, 42, 40), (0, 0, size, size), 1)
        else:
            q = size // 4
            pygame.draw.rect(s, mid, (q, q, size - 2 * q, size - 2 * q), 1)
            pygame.draw.rect(s, light, (size // 2 - 1, size // 2 - 1, 2, 2))
        self.block_cache[key] = s
        return s

    def txt(self, s, font, color, pos, anchor="topleft", surf=None):
        img = font.render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        (surf or self.canvas).blit(img, r)
        return r

    def glitch_text(self, s, font, pos, color=TEXT, anchor="center", amt=3):
        j = amt + (random.randint(0, 8) if random.random() < 0.06 else 0)
        for off, col in (((-j, 0), (255, 0, 70)), ((j, 0), (0, 230, 220))):
            img = font.render(s, True, col)
            img.set_alpha(150)
            r = img.get_rect(**{anchor: (pos[0] + off[0], pos[1] + off[1])})
            self.canvas.blit(img, r)
        return self.txt(s, font, color, pos, anchor)

    def panel(self, x, y, w, h, title=None, col=AMBER):
        pygame.draw.rect(self.canvas, PANEL, (x, y, w, h))
        pygame.draw.rect(self.canvas, EDGE, (x, y, w, h), 1)
        for cx, cy, dx, dy in ((x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1), (x + w - 1, y + h - 1, -1, -1)):
            pygame.draw.line(self.canvas, col, (cx, cy), (cx + 8 * dx, cy), 2)
            pygame.draw.line(self.canvas, col, (cx, cy), (cx, cy + 8 * dy), 2)
        if title:
            self.txt(title, self.f_tiny, col, (x + 10, y + 6))

    def hazard(self, x, y, w, h):
        c = self.canvas
        old = c.get_clip()
        c.set_clip(pygame.Rect(x, y, w, h))
        pygame.draw.rect(c, (22, 20, 12), (x, y, w, h))
        off = int(self.t * 20) % 24
        for i in range(-h - 24, w + h, 24):
            xx = x + i + off
            pygame.draw.polygon(c, AMBER_D, [(xx, y + h), (xx + 12, y + h), (xx + 12 + h, y), (xx + h, y)])
        c.set_clip(old)

    def mini_piece(self, kind, cx, cy, cell=18, dim=False):
        if not kind:
            return
        cells = ROTS[kind][0]
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        w = (max(xs) - min(xs) + 1) * cell
        h = (max(ys) - min(ys) + 1) * cell
        img = self.block(kind, cell)
        for x, y in cells:
            px = cx - w // 2 + (x - min(xs)) * cell
            py = cy - h // 2 + (y - min(ys)) * cell
            if dim:
                s = img.copy()
                s.set_alpha(70)
                self.canvas.blit(s, (px, py))
            else:
                self.canvas.blit(img, (px, py))

    # ---------------------------------------------------------- deska
    def draw_board(self, ox, oy, rows, piece, kind, ghost, cell=CELL, blackout=False,
                   over=False, danger=False):
        c = self.canvas
        bw, bh = COLS * cell, ROWS * cell
        frame = WARN if (danger and int(self.t * 4) % 2 == 0) else EDGE
        pygame.draw.rect(c, (30, 33, 30), (ox - 6, oy - 6, bw + 12, bh + 12))
        pygame.draw.rect(c, frame, (ox - 6, oy - 6, bw + 12, bh + 12), 2)
        pygame.draw.rect(c, (7, 8, 9), (ox, oy, bw, bh))
        for x in range(1, COLS):
            pygame.draw.line(c, GRIDC, (ox + x * cell, oy), (ox + x * cell, oy + bh))
        for y in range(1, ROWS):
            pygame.draw.line(c, GRIDC, (ox, oy + y * cell), (ox + bw, oy + y * cell))
        if blackout:
            for _ in range(140):
                g = random.randint(10, 45)
                pygame.draw.rect(c, (g, g, g), (ox + random.randrange(bw - 4), oy + random.randrange(bh - 3), random.randint(2, 14), 2))
            self.txt("OBSAH CENZUROVÁN", self.f_normb, WARN, (ox + bw // 2, oy + bh // 2), "center")
            self.txt("ministerstvem pravdy", self.f_tiny, DIM, (ox + bw // 2, oy + bh // 2 + 22), "center")
        else:
            for y, row in enumerate(rows):
                for x, v in enumerate(row):
                    if v and v != '.':
                        k = v if v in PIECE_COL else 'G'
                        c.blit(self.block(k, cell), (ox + x * cell, oy + y * cell))
        if kind and ghost:
            col = PIECE_COL.get(kind, TEXT)
            for x, y in ghost:
                pygame.draw.rect(c, _scale(col, 0.55), (ox + x * cell + 2, oy + y * cell + 2, cell - 4, cell - 4), 1)
        if kind and piece:
            img = self.block(kind, cell)
            for x, y in piece:
                if 0 <= y < ROWS:
                    c.blit(img, (ox + x * cell, oy + y * cell))
        self.hazard(ox - 6, oy - 16, bw + 12, 10)
        if over:
            s = pygame.Surface((bw, bh), pygame.SRCALPHA)
            s.fill((60, 0, 0, 150))
            c.blit(s, (ox, oy))

    def garbage_bar(self, x, y, n, cell=CELL):
        h = min(ROWS, n) * cell
        pygame.draw.rect(self.canvas, (20, 10, 10), (x, y, 8, ROWS * cell))
        if n:
            col = WARN if int(self.t * 6) % 2 else (160, 30, 20)
            pygame.draw.rect(self.canvas, col, (x, y + ROWS * cell - h, 8, h))

    def local_board(self, g, ox, oy, blackout=False):
        danger = any(any(r) for r in g.visible_rows()[:4]) and not g.over
        self.draw_board(ox, oy, g.visible_rows(), g.piece_visible(), g.kind, g.ghost_visible(),
                        blackout=blackout, over=g.over, danger=danger)
        return danger

    # ---------------------------------------------------------- efekty
    def process_events(self, g, ox, oy, versus=False):
        for e in g.events:
            k = e[0]
            if k == 'move':
                self.snd.play('move', 0.6)
            elif k == 'rotate':
                self.snd.play('rotate', 0.7)
            elif k == 'lock':
                self.snd.play('lock', 0.8)
            elif k == 'drop':
                self.snd.play('drop', 0.8)
                self.shake = max(self.shake, 0.08)
            elif k == 'hold':
                self.snd.play('hold')
            elif k == 'levelup':
                self.snd.play('levelup')
                self.banner = ("POVÝŠENÍ: SMĚNA %d" % g.level, ACID, 2.0)
            elif k == 'clear':
                n, rows, combo, b2b = e[1], e[2], e[3], e[4]
                self.snd.play('quad' if n == 4 else 'clear')
                for ry, kinds in rows:
                    self.flashes.append([ox, oy + ry * CELL, COLS * CELL, CELL, 0.28])
                    for x, kd in enumerate(kinds):
                        col = PIECE_COL.get(kd, TEXT)
                        for _ in range(3):
                            self.particles.append([ox + x * CELL + CELL / 2, oy + ry * CELL + CELL / 2,
                                                   random.uniform(-260, 260), random.uniform(-380, -60),
                                                   random.uniform(0.5, 1.1), col])
                if n == 4:
                    self.shake = 0.35
                    self.glitch = 0.35
                    self.banner = ("ČTVEŘICE! KVÓTA PŘEKROČENA" + (" ×2" if b2b else ""), CYAN, 1.8)
                elif combo >= 2:
                    self.banner = ("SÉRIE ×%d" % (combo + 1), AMBER, 1.2)
            elif k == 'garbage':
                self.snd.play('garbage')
                self.shake = max(self.shake, 0.25)
            elif k == 'gameover':
                self.snd.play('gameover')
                self.glitch = 0.6
                self.shake = 0.5
        g.events.clear()

    def update_fx(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 900 * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for f in self.flashes:
            f[4] -= dt
        self.flashes = [f for f in self.flashes if f[4] > 0]
        self.shake = max(0.0, self.shake - dt)
        self.glitch = max(0.0, self.glitch - dt)
        if self.banner:
            t, c, life = self.banner
            life -= dt
            self.banner = (t, c, life) if life > 0 else None
        self.ticker_x -= 70 * dt
        if self.ticker_x < -self.ticker_img.get_width():
            self.ticker_x += self.ticker_img.get_width()

    def draw_fx(self):
        for p in self.particles:
            pygame.draw.rect(self.canvas, p[5], (int(p[0]), int(p[1]), 4, 4))
        for f in self.flashes:
            s = pygame.Surface((f[2], f[3]), pygame.SRCALPHA)
            s.fill((255, 255, 240, int(230 * f[4] / 0.28)))
            self.canvas.blit(s, (f[0], f[1]))
        if self.banner:
            t, c, life = self.banner
            a = min(1.0, life * 2)
            img = self.f_med.render(t, True, c)
            img.set_alpha(int(255 * a))
            r = img.get_rect(center=(W // 2, 118))
            bgs = pygame.Surface((r.w + 30, r.h + 10), pygame.SRCALPHA)
            bgs.fill((0, 0, 0, int(190 * a)))
            self.canvas.blit(bgs, (r.x - 15, r.y - 5))
            self.canvas.blit(img, r)

    def header(self, subtitle="MINISTERSTVO STAVEBNÍCH BLOKŮ // SEKTOR 7"):
        pygame.draw.rect(self.canvas, (14, 15, 16), (0, 0, W, 40))
        pygame.draw.line(self.canvas, EDGE, (0, 40), (W, 40))
        self.txt("KVÓTA", self.f_normb, AMBER, (18, 10))
        self.txt(subtitle, self.f_small, DIM, (100, 13))
        now = datetime.datetime.now().strftime("%H:%M:%S")
        r = self.txt("CYKLUS " + now, self.f_small, TEXT, (W - 18, 13), "topright")
        if int(self.t * 1.5) % 2 == 0:
            pygame.draw.circle(self.canvas, WARN, (r.x - 52, 21), 5)
        self.txt("REC", self.f_small, WARN, (r.x - 42, 13))

    def ticker(self):
        pygame.draw.rect(self.canvas, (14, 12, 6), (0, H - 30, W, 30))
        pygame.draw.line(self.canvas, AMBER_D, (0, H - 30), (W, H - 30))
        x = self.ticker_x
        while x < W:
            self.canvas.blit(self.ticker_img, (x, H - 23))
            x += self.ticker_img.get_width()

    def eye(self, cx, cy, look_x):
        c = self.canvas
        self.eye_blink -= 1 / FPS
        if self.eye_blink < -5.5:
            self.eye_blink = 0.15
        openk = 0.08 if self.eye_blink > 0 else 1.0
        col = (95, 22, 20)
        pts_top = [(cx + 90 * math.cos(a), cy - 42 * openk * math.sin(a)) for a in [i * math.pi / 20 for i in range(21)]]
        pts_bot = [(cx + 90 * math.cos(a), cy + 42 * openk * math.sin(a)) for a in [i * math.pi / 20 for i in range(21)]]
        pygame.draw.lines(c, col, False, pts_top, 2)
        pygame.draw.lines(c, col, False, pts_bot, 2)
        if openk > 0.5:
            px = cx + max(-40, min(40, (look_x - cx) * 0.08))
            pygame.draw.circle(c, (70, 16, 14), (int(px), cy), 28, 2)
            pygame.draw.circle(c, WARN if int(self.t * 2) % 2 else (150, 20, 16), (int(px), cy), 10)
        for i in range(3):
            pygame.draw.line(c, (45, 14, 12), (cx - 110 + i * 110, cy - 70), (cx - 90 + i * 90, cy - 52), 2)
        self.txt("DOHLED AKTIVNÍ", self.f_tiny, (120, 30, 26), (cx, cy + 62), "center")

    def present(self):
        sx = sy = 0
        if self.shake > 0:
            m = int(self.shake * 26)
            sx, sy = random.randint(-m, m), random.randint(-m, m)
        self.screen.fill((0, 0, 0))
        self.screen.blit(self.canvas, (sx, sy))
        if self.glitch > 0:
            for _ in range(7):
                y = random.randrange(0, H - 24)
                h = random.randint(3, 22)
                strip = self.canvas.subsurface((0, y, W, h)).copy()
                self.screen.blit(strip, (random.randint(-28, 28), y))
        if random.random() < 0.015:
            fl = pygame.Surface((W, H), pygame.SRCALPHA)
            fl.fill((255, 255, 255, 8))
            self.screen.blit(fl, (0, 0))
        self.screen.blit(self.scan, (0, 0))
        self.screen.blit(self.vig, (0, 0))

    # ---------------------------------------------------------- smyčka
    def step(self, events, dt):
        self.t += dt
        for e in events:
            if e.type == pygame.QUIT:
                self.cleanup_net()
                self.quit = True
                return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    try:
                        pygame.display.toggle_fullscreen()
                    except Exception:
                        pass
                    continue
                if e.key == pygame.K_m and not self.entry_active and self.state != "join":
                    self.snd.toggle_music()
                    continue
            getattr(self, "ev_" + self.state)(e)
        getattr(self, "up_" + self.state)(dt)
        self.update_fx(dt)
        self.canvas.blit(self.bg, (0, 0))
        getattr(self, "dr_" + self.state)()
        self.draw_fx()
        self.present()

    # ================================================================ MENU
    def ev_menu(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_UP:
            self.menu_i = (self.menu_i - 1) % len(MENU)
            self.snd.play('tick')
        elif e.key == pygame.K_DOWN:
            self.menu_i = (self.menu_i + 1) % len(MENU)
            self.snd.play('tick')
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.snd.play('select')
            [self.start_solo, self.start_host, self.start_join,
             lambda: self.goto("scores"), lambda: self.goto("rules"),
             self.do_quit][self.menu_i]()
        elif e.key == pygame.K_ESCAPE:
            self.do_quit()

    def do_quit(self):
        self.quit = True

    def goto(self, st):
        self.state = st

    def up_menu(self, dt):
        pass

    def dr_menu(self):
        self.header()
        self.glitch_text("KVÓTA", self.f_huge, (W // 2, 160), amt=4)
        self.txt("SKLÁDEJ. PLŇ. MLČ.", self.f_normb, AMBER, (W // 2, 225), "center")
        self.hazard(W // 2 - 260, 250, 520, 10)
        for i, m in enumerate(MENU):
            y = 300 + i * 46
            sel = i == self.menu_i
            if sel:
                pygame.draw.rect(self.canvas, (40, 34, 10), (W // 2 - 240, y - 6, 480, 38))
                pygame.draw.rect(self.canvas, AMBER, (W // 2 - 240, y - 6, 480, 38), 1)
                self.txt("▶" if int(self.t * 3) % 2 else " ", self.f_normb, AMBER, (W // 2 - 225, y + 13), "midleft")
            self.txt(m, self.f_normb, AMBER if sel else TEXT, (W // 2, y + 13), "center")
        self.txt("←→ pohyb   ↑ rotace   ↓ zrychlit   MEZERNÍK shoz   C drž   P pauza   M hudba   F11 celá obr.",
                 self.f_small, DIM, (W // 2, H - 58), "center")
        self.txt("Občan: " + self.player_name, self.f_small, DIM, (18, 52))
        self.ticker()

    # ================================================================ PRAVIDLA
    def ev_rules(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.state = "menu"

    def up_rules(self, dt):
        pass

    def dr_rules(self):
        self.header("PRAVIDLA LAN REŽIMU")
        self.glitch_text("SABOTÁŽ", self.f_big, (W // 2, 95))
        self.txt("Dva občané, dva počítače, jedna síť. Audit přežije jen jeden.", self.f_normb, AMBER, (W // 2, 140), "center")
        lines = [
            ("SPRAVEDLNOST", "Oba dostáváte stejné pořadí bloků (sdílené semínko). Rozhoduje jen um."),
            ("BETONOVÝ PŘÍDĚL", "Smazané řádky posílají soupeři beton: 2 řádky → 1, 3 → 2, 4 → 4."),
            ("", "Čtveřice po čtveřici +1, série 3+ smazání za sebou +1, série 5+ další +1."),
            ("OBRANA", "Příchozí beton (červený sloupec u desky) dopadne až po tvém dalším"),
            ("", "položení bez smazání. Když mezitím smažeš řádky, beton tím zrušíš."),
            ("CENZURA", "Mazáním plníš měřič. Když je plný, stiskni ENTER: soupeřova hromada"),
            ("", "na 5 sekund zčerná — vidí jen padající blok a jeho stín."),
            ("INFLACE KVÓTY", "Po 90 s kola začne systém oběma přidávat 1 řádek betonu každých 15 s."),
            ("VÍTĚZSTVÍ", "Kdo přeteče, prohrál kolo. Zápas se hraje na 2 vítězná kola."),
            ("PŘIPOJENÍ", "PC 1: LAN: ZALOŽIT. PC 2: LAN: PŘIPOJIT (hostitel se najde sám, nebo zadej IP)."),
            ("", "Port TCP 50505, hledání UDP 50506 — při prvním spuštění povol hru ve firewallu."),
        ]
        y = 185
        for head, body in lines:
            if head:
                self.txt(head, self.f_normb, ACID, (90, y))
            self.txt(body, self.f_norm, TEXT, (290, y))
            y += 38 if head else 30
            if not head:
                y += 8
        self.txt("ESC / ENTER — zpět", self.f_small, DIM, (W // 2, H - 58), "center")
        self.ticker()

    # ================================================================ ŽEBŘÍČEK
    def ev_scores(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.state = "menu"

    def up_scores(self, dt):
        pass

    def dr_scores(self):
        self.header("REGISTR VZORNÝCH OBČANŮ")
        self.glitch_text("ŽEBŘÍČEK", self.f_big, (W // 2, 95))
        rows = load_scores()[:10]
        x0 = 170
        cols = [("#", 0), ("OBČAN", 60), ("KVÓTA", 330), ("ŘÁDKY", 480), ("SMĚNA", 590), ("DATUM", 700)]
        self.panel(x0 - 30, 140, W - 2 * (x0 - 30), 470, "HIGHSCORE.CSV")
        for name, dx in cols:
            self.txt(name, self.f_small, AMBER, (x0 + dx, 170))
        pygame.draw.line(self.canvas, EDGE, (x0, 194), (W - x0, 194))
        if not rows:
            self.txt("Registr je prázdný. Buď první vzorný občan.", self.f_norm, DIM, (W // 2, 350), "center")
        for i, r in enumerate(rows):
            y = 208 + i * 38
            col = ACID if i == 0 else TEXT
            vals = [str(i + 1), r["jmeno"], str(r["skore"]), str(r["radky"]), str(r["smena"]), r["datum"]]
            for (name, dx), v in zip(cols, vals):
                self.txt(v, self.f_norm, col, (x0 + dx, y))
        self.txt("Soubor: " + HS_FILE, self.f_tiny, DIM, (W // 2, 625), "center")
        self.txt("ESC / ENTER — zpět", self.f_small, DIM, (W // 2, H - 58), "center")
        self.ticker()

    # ================================================================ SOLO
    def start_solo(self):
        self.game = Game(random.randrange(1 << 30))
        self.das = DAS()
        self.paused = False
        self.state = "solo"
        self.best = (load_scores() or [{"skore": 0}])[0]["skore"]
        self.snd.music(True)

    def game_key(self, g, key):
        if key == pygame.K_LEFT:
            self.das.press(-1, g)
        elif key == pygame.K_RIGHT:
            self.das.press(1, g)
        elif key in (pygame.K_UP, pygame.K_x):
            g.rotate(1)
        elif key in (pygame.K_z, pygame.K_y, pygame.K_LCTRL, pygame.K_RCTRL):
            g.rotate(-1)
        elif key == pygame.K_SPACE:
            g.hard_drop()
        elif key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
            g.do_hold()

    def game_keyup(self, key):
        if key == pygame.K_LEFT:
            self.das.release(-1)
        elif key == pygame.K_RIGHT:
            self.das.release(1)

    def ev_solo(self, e):
        g = self.game
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.snd.music(False)
                self.state = "menu"
                return
            if e.key == pygame.K_p:
                self.paused = not self.paused
                self.snd.play('select')
                if self.snd.ok:
                    (pygame.mixer.music.pause if self.paused else pygame.mixer.music.unpause)()
                return
            if not self.paused:
                self.game_key(g, e.key)
        elif e.type == pygame.KEYUP:
            self.game_keyup(e.key)

    def up_solo(self, dt):
        g = self.game
        if not self.paused:
            self.das.update(dt, g)
            g.update(dt, pygame.key.get_pressed()[pygame.K_DOWN])
        self.process_events(g, self.SOLO_X, self.SOLO_Y)
        if g.over:
            self.snd.music(False)
            self.state = "solo_over"
            self.over_t = 0.0
            self.saved_rank = None
            self.entry_active = qualifies(g.score)
            self.entry_text = self.last_name[:12] if self.entry_active else ""
            if self.entry_active:
                pygame.key.start_text_input()

    SOLO_X, SOLO_Y = 410, 70

    def dr_solo(self, overlay=True):
        g = self.game
        self.header()
        ox, oy = self.SOLO_X, self.SOLO_Y
        # levý panel
        self.panel(230, oy, 160, 130, "ZADRŽENO [C]")
        self.mini_piece(g.hold, 310, oy + 72, 22, dim=g.hold_used)
        self.panel(230, oy + 145, 160, 290, "OSOBNÍ SPIS")
        stats = [("KVÓTA", str(g.score)), ("ŘÁDKY", str(g.lines)), ("SMĚNA", str(g.level)),
                 ("ČAS", "%d:%02d" % (g.time // 60, g.time % 60)), ("REKORD", str(max(self.best, g.score)))]
        for i, (k, v) in enumerate(stats):
            y = oy + 172 + i * 52
            self.txt(k, self.f_tiny, DIM, (245, y))
            self.txt(v, self.f_med, ACID if k == "KVÓTA" else TEXT, (245, y + 14))
        # pravý panel — příděl
        self.panel(730, oy, 160, 400, "PŘÍDĚL")
        for i, k in enumerate(g.nexts[:5]):
            self.mini_piece(k, 810, oy + 60 + i * 72, 22 if i == 0 else 17)
        self.eye(1005, 560, ox + g.x * CELL)
        self.panel(230, oy + 450, 160, 150, "DIREKTIVA")
        for i, s in enumerate(["←→  přesun", "↑ / Z  rotace", "↓  zrychlit", "MEZERA shoz", "P  pauza", "ESC  menu"]):
            self.txt(s, self.f_tiny, DIM, (245, oy + 476 + i * 20))
        danger = self.local_board(g, ox, oy)
        if danger and not g.over:
            self.danger_alarm -= 1 / FPS
            if self.danger_alarm <= 0:
                self.snd.play('alarm', 0.35)
                self.danger_alarm = 3.0
            self.txt("! KRITICKÁ VÝŠKA HROMADY !", self.f_small, WARN, (ox + 150, oy + 612), "center")
        if self.paused:
            self.dim_box("PŘESTÁVKA", "Neplánovaná přestávka byla nahlášena. [P] pokračovat")
        self.ticker()

    def dim_box(self, title, sub, col=AMBER):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 170))
        self.canvas.blit(s, (0, 0))
        self.glitch_text(title, self.f_big, (W // 2, H // 2 - 30), col)
        self.txt(sub, self.f_norm, TEXT, (W // 2, H // 2 + 25), "center")

    # --- konec solo hry
    def ev_solo_over(self, e):
        g = self.game
        if self.entry_active:
            if e.type == pygame.TEXTINPUT:
                for ch in e.text:
                    if ch not in ";\n\r\t" and len(self.entry_text) < 12:
                        self.entry_text += ch.upper()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    self.entry_text = self.entry_text[:-1]
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    name = self.entry_text.strip() or "OBČAN"
                    self.saved_rank = save_score(name, g.score, g.lines, g.level, g.time)
                    self.last_name = name
                    self.player_name = name
                    self.entry_active = False
                    pygame.key.stop_text_input()
                    self.snd.play('select')
                elif e.key == pygame.K_ESCAPE:
                    self.entry_active = False
                    pygame.key.stop_text_input()
            return
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and self.over_t > 0.8:
                self.start_solo()
            elif e.key == pygame.K_ESCAPE:
                self.state = "menu"

    def up_solo_over(self, dt):
        self.over_t += dt

    def dr_solo_over(self):
        self.dr_solo()
        g = self.game
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((20, 0, 0, 175))
        self.canvas.blit(s, (0, 0))
        self.glitch_text("KVÓTA NESPLNĚNA", self.f_big, (W // 2, 200), WARN, amt=5)
        self.txt("Občan přeřazen do Sektoru 9 (nucené práce).", self.f_norm, TEXT, (W // 2, 250), "center")
        self.txt("KVÓTA %d   ·   ŘÁDKY %d   ·   SMĚNA %d" % (g.score, g.lines, g.level), self.f_med, ACID, (W // 2, 305), "center")
        if self.entry_active:
            self.panel(W // 2 - 230, 350, 460, 130, "ZÁPIS DO REGISTRU", ACID)
            self.txt("Výkon hodný registru. Zadej občanské jméno:", self.f_small, TEXT, (W // 2, 385), "center")
            cur = "_" if int(self.t * 3) % 2 else " "
            self.txt(self.entry_text + cur, self.f_med, AMBER, (W // 2, 430), "center")
            self.txt("ENTER uložit · ESC přeskočit", self.f_tiny, DIM, (W // 2, 465), "center")
        else:
            if self.saved_rank:
                self.txt("Zapsáno do registru na pozici #%d." % self.saved_rank, self.f_normb, ACID, (W // 2, 390), "center")
            self.txt("ENTER — nová směna      ESC — menu", self.f_normb, TEXT, (W // 2, 450), "center")

    # ================================================================ LAN — HOST
    def start_host(self):
        self.cleanup_net()
        self.host = HostServer(self.player_name)
        self.host_ips = lan_ips()
        self.state = "host_wait"

    def ev_host_wait(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.cleanup_net()
            self.state = "menu"

    def up_host_wait(self, dt):
        if self.host and self.host.conn:
            conn = self.host.conn
            self.host.stop()
            self.host = None
            self.snd.play('select')
            self.start_versus(Net(conn), True)

    def dr_host_wait(self):
        self.header("LAN // HOSTITEL")
        self.glitch_text("SABOTÁŽ", self.f_big, (W // 2, 130))
        self.panel(W // 2 - 300, 190, 600, 300, "STANOVIŠTĚ HOSTITELE")
        if self.host and self.host.error:
            self.txt(self.host.error, self.f_normb, WARN, (W // 2, 300), "center")
        else:
            dots = "." * (int(self.t * 2) % 4)
            self.txt("Čekám na druhého občana" + dots, self.f_med, AMBER, (W // 2, 240), "center")
            self.txt("Na druhém PC zvol  LAN: PŘIPOJIT SE", self.f_norm, TEXT, (W // 2, 295), "center")
            self.txt("Tvoje adresa v síti:", self.f_small, DIM, (W // 2, 340), "center")
            for i, ip in enumerate(self.host_ips[:3]):
                self.txt("%s : %d" % (ip, PORT), self.f_med, ACID, (W // 2, 375 + i * 34), "center")
        self.txt("ESC — zrušit", self.f_small, DIM, (W // 2, H - 58), "center")
        self.ticker()

    # ================================================================ LAN — JOIN
    def start_join(self):
        self.cleanup_net()
        self.disc = Discovery()
        self.join_i = 0
        self.join_status = ""
        self.connecting = False
        self.connect_result = None
        self.join_hosts = []
        self.state = "join"
        pygame.key.start_text_input()

    def join_options(self):
        hosts = self.disc.poll() if self.disc else []
        return hosts

    def connect_async(self, ip):
        self.connecting = True
        self.join_status = "Připojuji k %s…" % ip

        def run():
            try:
                s = socket.create_connection((ip, PORT), timeout=4)
                self.connect_result = ("ok", s)
            except OSError as ex:
                self.connect_result = ("err", str(ex))
        threading.Thread(target=run, daemon=True).start()

    def ev_join(self, e):
        if self.connecting:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.connecting = False
                self.join_status = "Zrušeno."
            return
        hosts = self.join_hosts
        n = len(hosts) + 1
        if e.type == pygame.TEXTINPUT and self.join_i == len(hosts):
            for ch in e.text:
                if (ch.isdigit() or ch == '.') and len(self.join_ip) < 15:
                    self.join_ip += ch
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                pygame.key.stop_text_input()
                self.cleanup_net()
                self.state = "menu"
            elif e.key == pygame.K_UP:
                self.join_i = (self.join_i - 1) % n
                self.snd.play('tick')
            elif e.key == pygame.K_DOWN:
                self.join_i = (self.join_i + 1) % n
                self.snd.play('tick')
            elif e.key == pygame.K_BACKSPACE and self.join_i == len(hosts):
                self.join_ip = self.join_ip[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.join_i < len(hosts):
                    self.connect_async(hosts[self.join_i][0])
                elif self.join_ip.count('.') == 3:
                    self.connect_async(self.join_ip)
                else:
                    self.join_status = "Neplatná IP adresa."

    def up_join(self, dt):
        self.join_hosts = self.join_options()
        self.join_i = min(self.join_i, len(self.join_hosts))
        if self.connect_result:
            kind, val = self.connect_result
            self.connect_result = None
            if not self.connecting:
                if kind == "ok":
                    val.close()
                return
            self.connecting = False
            if kind == "ok":
                pygame.key.stop_text_input()
                if self.disc:
                    self.disc.close()
                    self.disc = None
                self.snd.play('select')
                self.start_versus(Net(val), False)
            else:
                self.join_status = "Spojení selhalo: " + val

    def dr_join(self):
        self.header("LAN // PŘIPOJENÍ")
        self.glitch_text("SABOTÁŽ", self.f_big, (W // 2, 130))
        self.panel(W // 2 - 300, 185, 600, 330, "NALEZENÁ STANOVIŠTĚ V SÍTI")
        hosts = getattr(self, "join_hosts", [])
        y = 225
        if not hosts:
            self.txt("Hledám hostitele" + "." * (int(self.t * 2) % 4), self.f_norm, DIM, (W // 2, y + 10), "center")
            y += 50
        for i, (ip, (name, _)) in enumerate(hosts[:5]):
            sel = i == self.join_i
            if sel:
                pygame.draw.rect(self.canvas, (40, 34, 10), (W // 2 - 270, y - 4, 540, 34))
            self.txt("%s   —   %s" % (name, ip), self.f_normb, AMBER if sel else TEXT, (W // 2, y + 13), "center")
            y += 40
        sel = self.join_i == len(hosts)
        y = max(y + 10, 380)
        if sel:
            pygame.draw.rect(self.canvas, (40, 34, 10), (W // 2 - 270, y - 4, 540, 34))
        cur = "_" if sel and int(self.t * 3) % 2 else " "
        self.txt("Ručně IP:  " + (self.join_ip or "") + cur, self.f_normb, AMBER if sel else TEXT, (W // 2, y + 13), "center")
        if self.join_status:
            self.txt(self.join_status, self.f_small, WARN if "selhal" in self.join_status or "Neplat" in self.join_status else ACID,
                     (W // 2, 480), "center")
        self.txt("↑↓ výběr   ENTER připojit   ESC zpět   (test na 1 PC: 127.0.0.1)", self.f_small, DIM, (W // 2, H - 58), "center")
        self.ticker()

    def cleanup_net(self):
        if self.net:
            self.net.send({"t": "bye"})
            self.net.close()
            self.net = None
        if self.host:
            self.host.stop()
            self.host = None
        if self.disc:
            self.disc.close()
            self.disc = None

    # ================================================================ VERSUS
    VX, VY = 180, 70         # moje deska
    OX, OY = 640, 70         # soupeř

    def start_versus(self, net, is_host):
        self.net = net
        self.is_host = is_host
        self.wins = [0, 0]
        self.opp_name = "?"
        self.opp_state = None
        self.vg = None
        self.vs_phase = "wait"
        self.phase_t = 0.0
        self.blackout = 0.0
        self.opp_blackout = 0.0
        self.last_won = None
        self.state = "versus"
        net.send({"t": "hello", "name": self.player_name, "v": PROTO})
        if is_host:
            self.host_new_round(reset=True)

    def host_new_round(self, reset=False):
        if reset:
            self.wins = [0, 0]
        seed = random.randrange(1 << 30)
        self.net.send({"t": "start", "seed": seed, "wins": [self.wins[1], self.wins[0]]})
        self.begin_round(seed)

    def begin_round(self, seed):
        self.vg = Game(seed, versus=True)
        self.vs_phase = "countdown"
        self.countdown = 3.0
        self.blackout = 0.0
        self.opp_blackout = 0.0
        self.round_time = 0.0
        self.next_inflation = 90.0
        self.send_t = 0.0
        self.sent_dead = False
        self.opp_state = None
        self.das = DAS()
        self.snd.play('count')
        self.snd.music(True)

    def round_over(self, i_won):
        self.vs_phase = "round_end"
        self.phase_t = 3.0
        self.last_won = i_won
        self.blackout = self.opp_blackout = 0.0
        self.snd.play('win' if i_won else 'lose')
        if not i_won:
            self.glitch = 0.4

    def host_resolve(self, host_won):
        if self.vs_phase != "play":
            return
        if host_won:
            self.wins[0] += 1
        else:
            self.wins[1] += 1
        self.net.send({"t": "round", "you_won": not host_won, "wins": [self.wins[1], self.wins[0]]})
        self.round_over(host_won)

    def ev_versus(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.snd.music(False)
                self.cleanup_net()
                self.state = "menu"
                return
            if self.vs_phase == "play" and self.vg and not self.vg.over:
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.vg.hack >= 100:
                        self.vg.hack = 0
                        self.net.send({"t": "hack"})
                        self.opp_blackout = 5.0
                        self.snd.play('hack')
                        self.banner = ("CENZURA ODESLÁNA", CYAN, 1.5)
                elif e.key == pygame.K_p:
                    self.banner = ("PŘESTÁVKY BĚHEM AUDITU NEJSOU POVOLENY", WARN, 1.5)
                else:
                    self.game_key(self.vg, e.key)
            elif self.vs_phase == "match_end" and self.is_host and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.host_new_round(reset=True)
        elif e.type == pygame.KEYUP:
            self.game_keyup(e.key)

    def up_versus(self, dt):
        net = self.net
        if net is None:
            self.state = "menu"
            return
        for m in net.poll():
            t = m.get("t")
            if t == "hello":
                self.opp_name = str(m.get("name", "?"))[:14]
            elif t == "start" and not self.is_host:
                self.wins = list(m.get("wins", [0, 0]))
                self.begin_round(int(m["seed"]))
            elif t == "st":
                self.opp_state = m
            elif t == "garbage":
                if self.vg and self.vs_phase == "play" and not self.vg.over:
                    n = max(0, min(12, int(m.get("n", 0))))
                    self.vg.pending.append((n, int(m.get("gap", 0)) % COLS))
                    self.snd.play('alarm', 0.5)
                    self.banner = ("PŘÍCHOZÍ BETON: %d" % n, WARN, 1.0)
            elif t == "hack":
                if self.vs_phase == "play":
                    self.blackout = 5.0
                    self.glitch = 0.5
                    self.snd.play('hack')
            elif t == "dead" and self.is_host:
                self.host_resolve(True)
            elif t == "round" and not self.is_host:
                self.wins = list(m.get("wins", self.wins))
                self.round_over(bool(m.get("you_won")))
            elif t == "bye":
                net.alive = False
        if not net.alive and self.vs_phase != "disconnected":
            self.vs_phase = "disconnected"
            self.snd.music(False)
            self.snd.play('lose')
        g = self.vg
        ph = self.vs_phase
        if ph == "countdown":
            before = math.ceil(self.countdown)
            self.countdown -= dt
            after = math.ceil(self.countdown)
            if self.countdown <= 0:
                self.vs_phase = "play"
                self.snd.play('go')
            elif after != before:
                self.snd.play('count')
        elif ph == "play" and g:
            self.round_time += dt
            self.blackout = max(0.0, self.blackout - dt)
            self.opp_blackout = max(0.0, self.opp_blackout - dt)
            self.das.update(dt, g)
            g.update(dt, pygame.key.get_pressed()[pygame.K_DOWN])
            if g.outgoing > 0:
                net.send({"t": "garbage", "n": g.outgoing, "gap": random.randrange(COLS)})
                g.outgoing = 0
            if self.round_time >= self.next_inflation:
                self.next_inflation += 15
                g.pending.append((1, random.randrange(COLS)))
                self.banner = ("INFLACE KVÓTY: +1 ŘÁDEK", AMBER, 1.2)
                self.snd.play('alarm', 0.4)
            if g.over and not self.sent_dead:
                self.sent_dead = True
                if self.is_host:
                    self.host_resolve(False)
                else:
                    net.send({"t": "dead"})
        elif ph == "round_end":
            self.phase_t -= dt
            if self.phase_t <= 0:
                if max(self.wins) >= 2:
                    self.vs_phase = "match_end"
                    self.snd.music(False)
                    self.snd.play('win' if self.wins[0] >= 2 else 'gameover')
                elif self.is_host:
                    self.host_new_round()
                else:
                    self.vs_phase = "wait"
        if g:
            self.process_events(g, self.VX, self.VY, versus=True)
            self.send_t -= dt
            if self.send_t <= 0 and ph in ("countdown", "play", "round_end"):
                self.send_t = 1 / 15
                net.send({"t": "st", "b": g.board_string(), "p": g.piece_visible(), "gh": g.ghost_visible(),
                          "k": g.kind, "s": g.score, "l": g.lines, "h": g.hack,
                          "g": g.pending_total(), "o": g.over, "hd": g.hold, "bo": self.blackout > 0})

    def dr_versus(self):
        self.header("LAN // SABOTÁŽ")
        g = self.vg
        vx, vy, ox, oy = self.VX, self.VY, self.OX, self.OY
        # skóre zápasu
        self.txt("%s  %d : %d  %s" % (self.player_name, self.wins[0], self.wins[1], self.opp_name),
                 self.f_normb, AMBER, (W // 2, 20), "center")
        if g:
            self.local_board(g, vx, vy, blackout=self.blackout > 0)
            self.garbage_bar(vx - 20, vy, g.pending_total())
            # levý panel
            self.panel(30, vy, 120, 110, "ZADRŽENO")
            self.mini_piece(g.hold, 90, vy + 62, 18, dim=g.hold_used)
            self.panel(30, vy + 125, 120, 220, "SPIS")
            for i, (k, v) in enumerate([("KVÓTA", g.score), ("ŘÁDKY", g.lines), ("SMĚNA", g.level)]):
                self.txt(k, self.f_tiny, DIM, (42, vy + 150 + i * 62))
                self.txt(str(v), self.f_med, TEXT, (42, vy + 164 + i * 62))
            self.panel(30, vy + 360, 120, 150, "CENZURA", CYAN)
            full = g.hack >= 100
            bh = int(100 * g.hack / 100)
            pygame.draw.rect(self.canvas, (10, 30, 30), (75, vy + 390, 30, 100))
            pygame.draw.rect(self.canvas, CYAN if not full or int(self.t * 5) % 2 else (255, 255, 255),
                             (75, vy + 490 - bh, 30, bh))
            if full:
                self.txt("ENTER!", self.f_normb, CYAN, (90, vy + 520), "center")
            # příděl
            self.panel(500, vy, 110, 300, "PŘÍDĚL")
            for i, k in enumerate(g.nexts[:4]):
                self.mini_piece(k, 555, vy + 58 + i * 64, 18 if i == 0 else 15)
            t_left = max(0, self.next_inflation - self.round_time)
            self.panel(500, vy + 315, 110, 90, "INFLACE", AMBER)
            if self.round_time < 90:
                self.txt("za %ds" % t_left, self.f_normb, TEXT, (555, vy + 360), "center")
            else:
                self.txt("AKTIVNÍ", self.f_normb, WARN, (555, vy + 350), "center")
                self.txt("+1 za %ds" % t_left, self.f_small, TEXT, (555, vy + 378), "center")
        # soupeř
        st = self.opp_state
        if st:
            b = st.get("b", "." * 200)
            rows = [list(b[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]
            self.draw_board(ox, oy, rows, [tuple(p) for p in st.get("p", [])], st.get("k"),
                            [tuple(p) for p in st.get("gh", [])], over=st.get("o", False))
            self.garbage_bar(ox + COLS * CELL + 12, oy, int(st.get("g", 0)))
            if self.opp_blackout > 0:
                self.txt("CENZUROVÁNO %.1fs" % self.opp_blackout, self.f_normb, CYAN, (ox + 150, oy + 300), "center")
            self.panel(962, oy, 138, 250, "SOUPEŘ")
            self.txt(self.opp_name, self.f_normb, AMBER, (975, oy + 30))
            for i, (k, key) in enumerate([("KVÓTA", "s"), ("ŘÁDKY", "l"), ("CENZURA", "h")]):
                self.txt(k, self.f_tiny, DIM, (975, oy + 70 + i * 55))
                val = str(st.get(key, 0)) + ("%" if key == "h" else "")
                self.txt(val, self.f_med, TEXT, (975, oy + 84 + i * 55))
            self.mini_piece(st.get("hd"), 1031, oy + 300, 15)
        else:
            self.draw_board(ox, oy, [[None] * COLS for _ in range(ROWS)], [], None, [])
            self.txt("SIGNÁL SOUPEŘE…", self.f_normb, DIM, (ox + 150, oy + 300), "center")
        # překryvy fází
        ph = self.vs_phase
        if ph == "countdown":
            n = max(1, math.ceil(self.countdown))
            self.dim_box(str(n), "AUDIT ZAČÍNÁ · kolo %d" % (sum(self.wins) + 1))
        elif ph == "round_end":
            if self.last_won:
                self.dim_box("KOLO TVOJE", "Soupeř přeřazen. %d : %d" % tuple(self.wins), ACID)
            else:
                self.dim_box("KOLO ZTRACENO", "Tvoje hromada přetekla. %d : %d" % tuple(self.wins), WARN)
        elif ph == "match_end":
            won = self.wins[0] >= 2
            sub = ("ENTER — odveta   ESC — menu" if self.is_host else "Čekám, až hostitel spustí odvetu…   ESC — menu")
            self.dim_box("AUDIT PŘEŽIL: " + (self.player_name if won else self.opp_name), sub, ACID if won else WARN)
        elif ph == "wait":
            self.dim_box("SPOJENO", "Čekám na hostitele…")
        elif ph == "disconnected":
            self.dim_box("SPOJENÍ PŘERUŠENO", "Soupeř opustil sektor. ESC — menu", WARN)
        self.ticker()

    # ================================================================ NAČÍTÁNÍ
    def loading(self, frac, msg):
        pygame.event.pump()
        self.canvas.blit(self.bg, (0, 0))
        self.header()
        self.glitch_text("KVÓTA", self.f_huge, (W // 2, 250), amt=3)
        self.txt(msg, self.f_norm, TEXT, (W // 2, 360), "center")
        pygame.draw.rect(self.canvas, EDGE, (W // 2 - 250, 400, 500, 18), 1)
        pygame.draw.rect(self.canvas, AMBER, (W // 2 - 247, 403, int(494 * frac), 12))
        self.present()
        pygame.display.flip()


def main():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("KVÓTA — Ministerstvo stavebních bloků")
    try:
        screen = pygame.display.set_mode((W, H), pygame.SCALED)
    except pygame.error:
        screen = pygame.display.set_mode((W, H))
    snd = Sound()
    app = App(screen, snd)
    pygame.key.stop_text_input()
    snd.load(app.loading)
    clock = pygame.time.Clock()
    while not app.quit:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        app.step(pygame.event.get(), dt)
        pygame.display.flip()
    app.cleanup_net()
    pygame.quit()


if __name__ == "__main__":
    main()
