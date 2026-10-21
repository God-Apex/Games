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
LAN režimy: SABOTÁŽ (souboj s betonem), ZÁVOD SMĚN (sprint / časovka)
            a MINISTERSTVO (jeden skládá, druhý jako úředník vybírá bloky
            a vydává direktivy), podmínky zápasu volí hostitel.
            TCP port 50505, hledání hostitelů UDP port 50506.
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
PROTO = 3
DAS_T, ARR_T = 0.16, 0.045
LOCK_DELAY = 0.5
# MINISTERSTVO — direktivy úředníka
LOCK_COLS = (0, 1, 2, 7, 8, 9)   # zamknout jdou jen krajní sloupce, prostředkem padají nové bloky
COL_LOCK_T = 10.0                # zámek sloupce
RUSH_T, RUSH_LEVELS = 10.0, 7    # zrychlený pád: 10 s jako o 7 směn výš
CENSOR_T = 5.0                   # cenzura hromady

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


def fall_interval(level):
    """Sekundy na pád o jeden řádek pro danou směnu."""
    lv = min(level, 20)
    return (0.8 - (lv - 1) * 0.007) ** (lv - 1)


# ================================================================ HERNÍ LOGIKA
class Game:
    """Jedna hrací plocha. Bez grafiky, bez vstupu — čistá logika."""

    def __init__(self, seed=None, versus=False, level=1, atk=100, censor=True, ministry=False):
        self.rng = random.Random(seed)
        self.board = [[None] * COLS for _ in range(TR)]
        self.bag = []
        self.nexts = [self._draw() for _ in range(5)]
        self.hold = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = self.start_level = max(1, level)
        self.combo = -1
        self.b2b = False
        self.over = False
        self.events = []
        self.versus = versus
        self.pending = []      # příchozí beton [(počet, díra)]
        self.outgoing = 0      # odchozí útok
        self.atk_mult = atk / 100.0
        self.atk_frac = 0.0    # zlomky útoku při síle ×0,5 / ×1,5 se sčítají
        self.censor = censor
        self.hack = 0          # měřič cenzury 0..100
        # MINISTERSTVO: další blok vybírá úředník ze dvou nabídnutých
        self.ministry = False      # zapne se až po prvním bloku, ten i příděl jsou z pytle
        self.offer = []
        self.offer_id = 0
        self.picked = None         # index schváleného bloku z nabídky
        self.auto_picks = 0        # kolikrát úředník nestihl a rozhodl automat
        self.lock_col = None       # sloupec zamčený direktivou
        self.lock_col_t = 0.0
        self.lock_col_next = None  # zámek čeká, až aktuální blok dopadne
        self.rush_t = 0.0          # zrychlený pád
        self.time = 0.0
        self.grav_t = 0.0
        self.lock_t = 0.0
        self.lock_moves = 0
        self.spawn()
        if ministry:
            self.ministry = True
            del self.nexts[1:]     # skladatel vidí jen jeden blok dopředu
            self._new_offer()

    # --- generátor 7-bag
    def _draw(self):
        if not self.bag:
            self.bag = list("IOTSZJL")
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _new_offer(self):
        self.offer = self.rng.sample("IOTSZJL", 2)
        self.offer_id += 1
        self.picked = None

    def _from_desk(self):
        """Ministerstvo: do přídělu jde blok, který úředník schválil; nestihl-li to, rozhodne automat."""
        if self.picked is None:
            self.picked = self.rng.randrange(2)
            self.auto_picks += 1
        kind = self.offer[self.picked]
        self._new_offer()
        return kind

    def spawn(self, kind=None):
        if self.lock_col_next is not None:
            self.lock_col, self.lock_col_t, self.lock_col_next = self.lock_col_next, COL_LOCK_T, None
        if kind is None:
            kind = self.nexts.pop(0)
            self.nexts.append(self._from_desk() if self.ministry else self._draw())
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
            if X < 0 or X >= COLS or Y >= TR or X == self.lock_col:
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
        return fall_interval(self.level + (RUSH_LEVELS if self.rush_t > 0 else 0))

    def directive(self, kind, col=None):
        """Ministerstvo: zrychlení pádu nebo zámek krajního sloupce. True = direktiva platí."""
        if self.over:
            return False
        if kind == "rush":
            self.rush_t = RUSH_T
            return True
        if kind == "col" and col in LOCK_COLS:
            if any(x == col for x, _ in self.cells()):
                self.lock_col_next = col       # padající blok ve sloupci stojí, zamkne se po dopadu
            else:
                self.lock_col, self.lock_col_t, self.lock_col_next = col, COL_LOCK_T, None
            return True
        return False

    def update(self, dt, soft=False):
        if self.over:
            return
        self.time += dt
        if self.rush_t > 0:
            self.rush_t = max(0.0, self.rush_t - dt)
        if self.lock_col is not None:
            self.lock_col_t -= dt
            if self.lock_col_t <= 0:
                self.lock_col = None
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
            nl = self.start_level + self.lines // 10
            if nl > self.level:
                self.level = nl
                self.events.append(('levelup',))
            self.events.append(('clear', n, rows, self.combo, b2b_bonus))
            if self.versus:
                atk = [0, 0, 1, 2, 4][n] + (1 if b2b_bonus else 0)
                atk += (1 if self.combo >= 2 else 0) + (1 if self.combo >= 4 else 0)
                raw = atk * self.atk_mult + self.atk_frac
                atk = int(raw)
                self.atk_frac = raw - atk
                while atk > 0 and self.pending:
                    c, g = self.pending[0]
                    if c <= atk:
                        atk -= c
                        self.pending.pop(0)
                    else:
                        self.pending[0] = (c - atk, g)
                        atk = 0
                self.outgoing += atk
                if self.censor:
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


# ================================================================ PODMÍNKY ZÁPASU (LAN)
def fmt_clock(sec):
    """Sekundy → 3:05."""
    sec = max(0, int(sec))
    return "%d:%02d" % (sec // 60, sec % 60)


def fmt_race(sec):
    """Sekundy → 1:23,4 (desetiny s českou čárkou)."""
    d = max(0, int(sec * 10))
    return "%d:%02d,%d" % (d // 600, d % 600 // 10, d % 10)


MODE_NAMES = {"sabotaz": "SABOTÁŽ", "sprint": "ZÁVOD SMĚN · SPRINT", "casovka": "ZÁVOD SMĚN · ČASOVKA",
              "ministr": "MINISTERSTVO"}
DEFAULT_CFG = {"mode": "sabotaz", "wins": 2, "level": 1, "censor": True, "infl": 90,
               "atk": 100, "lines": 40, "limit": 180, "half": 120, "dirs": 30}
# (klíč, popisek, [(hodnota, text)], režimy, ve kterých se řádek ukazuje — None = ve všech)
SETUP_ROWS = [
    ("mode", "REŽIM", [("sabotaz", "SABOTÁŽ"), ("sprint", "ZÁVOD: SPRINT"), ("casovka", "ZÁVOD: ČASOVKA"),
                       ("ministr", "MINISTERSTVO")], None),
    ("lines", "CÍL SPRINTU", [(n, "%d ŘÁDKŮ" % n) for n in (20, 40, 60, 100)], ("sprint",)),
    ("limit", "LIMIT ČASOVKY", [(s, fmt_clock(s)) for s in (120, 180, 300)], ("casovka",)),
    ("half", "DÉLKA POLOČASU", [(s, fmt_clock(s)) for s in (60, 120, 180)], ("ministr",)),
    ("wins", "VÍTĚZNÁ KOLA", [(n, str(n)) for n in range(1, 6)], None),
    ("level", "STARTOVNÍ SMĚNA", [(n, str(n)) for n in range(1, 16)], None),
    ("censor", "CENZURA", [(True, "ZAPNUTA"), (False, "VYPNUTA")], ("sabotaz",)),
    ("infl", "INFLACE KVÓTY", [(0, "VYPNUTA"), (60, "OD 60 s"), (90, "OD 90 s"), (120, "OD 120 s")], ("sabotaz",)),
    ("atk", "SÍLA ÚTOKŮ", [(50, "MÍRNÁ ×0,5"), (100, "BĚŽNÁ ×1"), (150, "TVRDÁ ×1,5"), (200, "DRTIVÁ ×2")], ("sabotaz",)),
    ("dirs", "DIREKTIVY", [(0, "VYPNUTY"), (20, "KAŽDÝCH 20 s"), (30, "KAŽDÝCH 30 s"), (45, "KAŽDÝCH 45 s")],
     ("ministr",)),
]
MODE_HINTS = {
    "sabotaz": "Souboj: smazané řádky posílají soupeři beton.",
    "sprint": "Bez útoků. Vyhrává, kdo první smaže cílový počet řádků.",
    "casovka": "Bez útoků. Vyhrává vyšší kvóta po uplynutí limitu.",
    "ministr": "Jeden skládá, druhý jako úředník vybírá bloky a vydává direktivy.",
}
SETUP_HINTS = {
    "lines": "Kolik řádků musí občan smazat, aby kolo vyhrál.",
    "limit": "Délka kola. Při shodné kvótě rozhodují smazané řádky.",
    "half": "Jak dlouho skládá každý z vás. Kdo přeteče, končí dřív.",
    "wins": "Kolik vyhraných kol je potřeba k vítězství v zápase.",
    "censor": "Plný měřič + ENTER: soupeřova hromada na 5 s zčerná.",
    "infl": "Od zvolené chvíle dostávají oba každých 15 s řádek betonu.",
    "atk": "Násobí beton posílaný soupeři i rušení příchozího betonu.",
    "dirs": "Jak často smí úředník zrychlit pád, cenzurovat hromadu nebo zamknout sloupec.",
}
DIRECTIVE_NAMES = {"rush": "ZRYCHLENÍ PÁDU", "cens": "CENZURA HROMADY", "col": "ZÁMEK SLOUPCE"}
# úředník zamyká sloupce číselnou řadou (podle polohy klávesy, ať funguje i česká klávesnice) nebo numerickým blokem
COL_SCANCODES = {pygame.KSCAN_1: 0, pygame.KSCAN_2: 1, pygame.KSCAN_3: 2,
                 pygame.KSCAN_8: 7, pygame.KSCAN_9: 8, pygame.KSCAN_0: 9}
COL_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_8: 7, pygame.K_9: 8, pygame.K_0: 9,
            pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2, pygame.K_KP8: 7, pygame.K_KP9: 8, pygame.K_KP0: 9}
COL_LABELS = {0: "1", 1: "2", 2: "3", 7: "8", 8: "9", 9: "0"}


def kola(n):
    if n == 1:
        return "1 vítězné kolo"
    return "%d vítězná kola" % n if n < 5 else "%d vítězných kol" % n


def radky(n):
    if n == 1:
        return "1 řádek"
    return "%d řádky" % n if 2 <= n <= 4 else "%d řádků" % n


def shift_text(st):
    """Výsledek skladatele v Ministerstvu: jak dlouho vydržel a kolik smazal."""
    head = "přetečení v " + fmt_race(st.get("tm", 0)) if st.get("top") else "celý poločas"
    return "%s, %s" % (head, radky(st.get("l", 0)))


def ministry_key(st):
    """Kdo vydržel celý poločas > kdo vydržel déle > víc řádků > vyšší kvóta."""
    return (0 if st.get("top") else 1, round(st.get("tm", 0), 1), st.get("l", 0), st.get("s", 0))


def cfg_parts(cfg):
    m = cfg["mode"]
    parts = []
    if m == "sprint":
        parts.append("cíl %d řádků" % cfg["lines"])
    elif m == "casovka":
        parts.append("limit " + fmt_clock(cfg["limit"]))
    elif m == "ministr":
        parts.append("poločas " + fmt_clock(cfg["half"]))
    parts += ["na " + kola(cfg["wins"]), "start. směna %d" % cfg["level"]]
    if m == "sabotaz":
        parts += ["cenzura " + ("ZAP" if cfg["censor"] else "VYP"),
                  "inflace " + ("od %d s" % cfg["infl"] if cfg["infl"] else "VYP"),
                  "útoky ×" + ("%g" % (cfg["atk"] / 100)).replace(".", ",")]
    elif m == "ministr":
        parts.append("direktivy po %d s" % cfg["dirs"] if cfg["dirs"] else "direktivy VYP")
    return parts


def cfg_summary(cfg):
    return " · ".join(cfg_parts(cfg))


def cfg_label(cfg):
    """Krátký popis zápasu pro seznam hostitelů v síti."""
    if cfg["mode"] == "sprint":
        return "SPRINT %d" % cfg["lines"]
    if cfg["mode"] == "casovka":
        return "ČASOVKA " + fmt_clock(cfg["limit"])
    if cfg["mode"] == "ministr":
        return "MINISTERSTVO"
    return "SABOTÁŽ"


def clean_cfg(raw):
    """Podmínky přišlé po síti — nesmyslné hodnoty nahradí výchozími."""
    cfg = dict(DEFAULT_CFG)
    if not isinstance(raw, dict):
        return cfg
    if raw.get("mode") in MODE_NAMES:
        cfg["mode"] = raw["mode"]
    cfg["censor"] = bool(raw.get("censor", True))
    for key, lo, hi in (("wins", 1, 9), ("level", 1, 20), ("infl", 0, 600), ("atk", 25, 400),
                        ("lines", 1, 999), ("limit", 30, 1800), ("half", 30, 600), ("dirs", 0, 300)):
        try:
            cfg[key] = max(lo, min(hi, int(raw.get(key, cfg[key]))))
        except (TypeError, ValueError, OverflowError):
            pass
    return cfg


def clean_stats(raw):
    """Výsledek kola ze sítě: kvóta, řádky, čas (a v Ministerstvu, zda skladatel přetekl)."""
    raw = raw if isinstance(raw, dict) else {}
    out = {"top": bool(raw.get("top"))}
    for key, kind in (("s", int), ("l", int), ("tm", float)):
        try:
            out[key] = max(0, min(10 ** 9, kind(raw.get(key, 0))))
        except (TypeError, ValueError, OverflowError):
            out[key] = 0
    return out


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
    def __init__(self, name, label=""):
        self.name = name
        self.label = label     # režim zápasu, ukáže se v seznamu hostitelů
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
        msg = ("KVOTA|%d|%s|%s" % (PROTO, self.label, self.name)).encode("utf-8")
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


def parse_beacon(data):
    """'KVOTA|verze|režim|jméno' → (jméno, verze, režim). Verze 1 posílala jen 'KVOTA|1|jméno'."""
    try:
        parts = data.decode("utf-8").split("|", 3)
        if parts[0] != "KVOTA" or len(parts) < 3:
            return None
        ver = int(parts[1])
    except (UnicodeDecodeError, ValueError):
        return None
    if ver >= 2 and len(parts) == 4:
        return parts[3], ver, parts[2]
    return "|".join(parts[2:]), ver, ""


class Discovery:
    def __init__(self):
        self.hosts = {}   # ip -> (jméno, verze, režim, čas)
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
                info = parse_beacon(data)
                if info:
                    self.hosts[addr[0]] = info + (time.time(),)
        now = time.time()
        for ip in [i for i, h in self.hosts.items() if now - h[-1] > 4]:
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


MENU = ["SAMOSTATNÁ SMĚNA", "LAN: ZALOŽIT ZÁPAS", "LAN: PŘIPOJIT SE",
        "ŽEBŘÍČEK VZORNÝCH OBČANŮ", "PRAVIDLA LAN REŽIMŮ", "OPUSTIT SEKTOR"]


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
        self.cfg = dict(DEFAULT_CFG)   # podmínky, které hostitel nabídne
        self.cfg_backup = None
        self.mcfg = None               # podmínky právě hraného zápasu
        self.setup_i = 0
        self.setup_live = False
        self.rules_page = 0

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
            [self.start_solo, self.start_setup, self.start_join,
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
    RULES = [
        ("SABOTÁŽ", "Dva občané, dva počítače, jedna síť. Audit přežije jen jeden.", [
            ("SPRAVEDLNOST", "Oba dostáváte stejné pořadí bloků (sdílené semínko). Rozhoduje jen um."),
            ("BETONOVÝ PŘÍDĚL", "Smazané řádky posílají soupeři beton: 2 řádky → 1, 3 → 2, 4 → 4."),
            ("", "Čtveřice po čtveřici +1, série 3+ smazání za sebou +1, série 5+ další +1."),
            ("OBRANA", "Příchozí beton (červený sloupec u desky) dopadne až po tvém dalším"),
            ("", "položení bez smazání. Když mezitím smažeš řádky, beton tím zrušíš."),
            ("CENZURA", "Mazáním plníš měřič. Když je plný, stiskni ENTER: soupeřova hromada"),
            ("", "na 5 sekund zčerná — vidí jen padající blok a jeho stín."),
            ("INFLACE KVÓTY", "Po 90 s kola začne systém oběma přidávat 1 řádek betonu každých 15 s."),
            ("VÍTĚZSTVÍ", "Kdo přeteče, prohrál kolo. Výchozí zápas se hraje na 2 vítězná kola."),
        ]),
        ("ZÁVOD SMĚN", "Stejné bloky, žádné útoky. Čistý souboj v rychlosti.", [
            ("SPRINT", "Vyhrává, kdo první smaže cílový počet řádků (výchozí 40)."),
            ("ČASOVKA", "Vyhrává vyšší kvóta po uplynutí limitu (výchozí 3:00)."),
            ("", "Při shodné kvótě rozhodují řádky, jinak je kolo remíza a nepočítá se."),
            ("BEZ SABOTÁŽE", "Nikdo nikomu neposílá beton, cenzura ani inflace neběží."),
            ("", "Soupeřovu desku i jeho postup k cíli vidíš vedle své."),
            ("PŘETEČENÍ", "Kdo přeteče dřív, než splní cíl, prohrál kolo."),
            ("PRO KOHO", "Na rozehřátí, nebo pro občany, které betonové útoky stresují."),
        ]),
        ("MINISTERSTVO", "Jeden skládá, druhý úřaduje. Pak se role prohodí.", [
            ("ÚŘEDNÍK", "Nemá vlastní desku. Vidí skladatelovu a ze dvou nabídnutých bloků"),
            ("", "šipkou ← nebo → vybere, který skladatel dostane; jinak rozhodne automat."),
            ("DIREKTIVY", "Jednou za čas: Z zrychlí pád, C cenzuruje hromadu, klávesy 1 2 3 / 8 9 0"),
            ("", "zamknou krajní sloupec. Vše platí jen pár sekund."),
            ("SKLADATEL", "Skládá jako obvykle. Vidí stůl úředníka i nabíjení jeho razítka."),
            ("POLOČASY", "Kolo má dva poločasy (výchozí 2:00), v každém skládá jeden z vás."),
            ("VÍTĚZSTVÍ", "Kolo vyhrává, kdo jako skladatel vydržel déle. Když oba vydrží"),
            ("", "celý poločas, rozhodují smazané řádky, pak kvóta."),
        ]),
        ("PODMÍNKY ZÁPASU", "Volí hostitel, druhý počítač je dostane se startem kola.", [
            ("ZALOŽENÍ", "LAN: ZALOŽIT ZÁPAS → ↑↓ vyber řádek, ←→ změň hodnotu, ENTER založ."),
            ("VŠECHNY REŽIMY", "Vítězná kola 1–5 a startovní směna 1–15 (rychlost pádu)."),
            ("SABOTÁŽ", "Cenzura zap/vyp, inflace vyp / od 60 / 90 / 120 s a síla útoků"),
            ("", "×0,5 až ×2 — násobí beton pro soupeře i rušení příchozího betonu."),
            ("ZÁVOD SMĚN", "Sprint na 20 / 40 / 60 / 100 řádků, časovka na 2 / 3 / 5 minut."),
            ("MINISTERSTVO", "Poločas 1 / 2 / 3 minuty, direktivy po 20 / 30 / 45 s nebo vypnuté."),
            ("ODVETA", "Po zápase hostitel: ENTER odveta, N změnit podmínky."),
            ("PŘIPOJENÍ", "PC 1: LAN: ZALOŽIT ZÁPAS. PC 2: LAN: PŘIPOJIT SE (najde se sám,"),
            ("", "nebo zadej IP). TCP 50505, UDP 50506 — povol hru ve firewallu."),
            ("", "Oba počítače musí mít stejnou verzi hry."),
        ]),
    ]

    def ev_rules(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.rules_page = (self.rules_page + (1 if e.key == pygame.K_RIGHT else -1)) % len(self.RULES)
            self.snd.play('tick')
        elif e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.state = "menu"

    def up_rules(self, dt):
        pass

    def dr_rules(self):
        self.header("PRAVIDLA LAN REŽIMŮ")
        title, motto, lines = self.RULES[self.rules_page]
        self.glitch_text(title, self.f_big, (W // 2, 95))
        self.txt(motto, self.f_normb, AMBER, (W // 2, 140), "center")
        y = 185
        for head, body in lines:
            if head:
                self.txt(head, self.f_normb, ACID, (90, y))
            self.txt(body, self.f_norm, TEXT, (290, y))
            y += 38 if head else 30
            if not head:
                y += 8
        # záložky stran
        imgs = [self.f_normb.render(t, True, AMBER if i == self.rules_page else DIM)
                for i, (t, _, _) in enumerate(self.RULES)]
        x = W // 2 - (sum(i.get_width() for i in imgs) + 50 * (len(imgs) - 1)) // 2
        for i, img in enumerate(imgs):
            self.canvas.blit(img, (x, H - 104))
            if i == self.rules_page:
                pygame.draw.line(self.canvas, AMBER, (x, H - 80), (x + img.get_width(), H - 80), 2)
            x += img.get_width() + 50
        self.txt("←→ další strana   ESC / ENTER — zpět", self.f_small, DIM, (W // 2, H - 58), "center")
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

    def dim_box(self, title, sub, col=AMBER, extra=None):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 170))
        self.canvas.blit(s, (0, 0))
        self.glitch_text(title, self.f_big, (W // 2, H // 2 - 30), col)
        self.txt(sub, self.f_norm, TEXT, (W // 2, H // 2 + 25), "center")
        if extra:
            self.txt(extra, self.f_small, AMBER, (W // 2, H // 2 + 62), "center")

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

    # ================================================================ LAN — PODMÍNKY ZÁPASU
    def start_setup(self, live=False):
        """live=True: zápas už běží a hostitel mění podmínky odvety."""
        self.setup_live = live
        self.setup_i = 0
        self.cfg_backup = dict(self.cfg)
        self.state = "setup"
        if live:
            self.net.send({"t": "setup", "on": True})

    def setup_rows(self):
        m = self.cfg["mode"]
        return [r for r in SETUP_ROWS if r[3] is None or m in r[3]]

    def setup_hint(self, key):
        if key == "mode":
            return MODE_HINTS[self.cfg["mode"]]
        if key == "level":
            sec = ("%.2f" % fall_interval(self.cfg["level"])).replace(".", ",")
            return "Blok padá o řádek za %s s, každých 10 smazaných řádků rychleji." % sec
        return SETUP_HINTS[key]

    def ev_setup(self, e):
        if e.type != pygame.KEYDOWN:
            return
        rows = self.setup_rows()
        if e.key == pygame.K_ESCAPE:
            if self.setup_live:
                self.cfg = self.cfg_backup
                self.net.send({"t": "setup", "on": False})
                self.state = "versus"
            else:
                self.state = "menu"
        elif e.key in (pygame.K_UP, pygame.K_DOWN):
            self.setup_i = (self.setup_i + (1 if e.key == pygame.K_DOWN else -1)) % len(rows)
            self.snd.play('tick')
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            key, _, opts, _ = rows[self.setup_i]
            vals = [v for v, _ in opts]
            i = vals.index(self.cfg[key]) if self.cfg[key] in vals else 0
            self.cfg[key] = vals[(i + (1 if e.key == pygame.K_RIGHT else -1)) % len(vals)]
            self.setup_i = min(self.setup_i, len(self.setup_rows()) - 1)
            self.snd.play('tick')
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.snd.play('select')
            if self.setup_live:
                self.state = "versus"
                self.host_new_round(reset=True)
            else:
                self.start_host()

    def up_setup(self, dt):
        if self.setup_live and not (self.net and self.net.alive):
            self.state = "versus"      # tam se ukáže přerušené spojení

    def dr_setup(self):
        self.header("LAN // PODMÍNKY ZÁPASU")
        self.glitch_text(MODE_NAMES[self.cfg["mode"]], self.f_big, (W // 2, 95))
        rows = self.setup_rows()
        px, pw = W // 2 - 330, 660
        self.panel(px, 145, pw, 420, "VOLÍ HOSTITEL · DRUHÝ POČÍTAČ JE DOSTANE SE STARTEM KOLA")
        for i, (key, label, opts, _) in enumerate(rows):
            y = 180 + i * 46
            sel = i == self.setup_i
            if sel:
                pygame.draw.rect(self.canvas, (40, 34, 10), (px + 20, y - 6, pw - 40, 38))
                pygame.draw.rect(self.canvas, AMBER, (px + 20, y - 6, pw - 40, 38), 1)
            self.txt(label, self.f_normb, AMBER if sel else TEXT, (px + 45, y + 13), "midleft")
            vx = px + pw - 175
            self.txt(dict(opts).get(self.cfg[key], str(self.cfg[key])), self.f_normb,
                     ACID if sel else TEXT, (vx, y + 13), "center")
            if sel:
                self.txt("◄", self.f_normb, AMBER, (vx - 125, y + 13), "center")
                self.txt("►", self.f_normb, AMBER, (vx + 125, y + 13), "center")
        self.txt(self.setup_hint(rows[self.setup_i][0]), self.f_small, TEXT, (W // 2, 500), "center")
        self.txt(cfg_summary(self.cfg), self.f_small, AMBER, (W // 2, 532), "center")
        go = "ENTER — SPUSTIT ODVETU" if self.setup_live else "ENTER — ZALOŽIT ZÁPAS"
        self.txt(go, self.f_normb, ACID, (W // 2, 592), "center")
        self.txt("↑↓ řádek   ←→ změnit   ESC zpět", self.f_small, DIM, (W // 2, H - 58), "center")
        self.ticker()

    # ================================================================ LAN — HOST
    def start_host(self):
        self.cleanup_net()
        self.host = HostServer(self.player_name, cfg_label(self.cfg))
        self.host_ips = lan_ips()
        self.state = "host_wait"

    def ev_host_wait(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.cleanup_net()
            self.state = "setup"

    def up_host_wait(self, dt):
        if self.host and self.host.conn:
            conn = self.host.conn
            self.host.stop()
            self.host = None
            self.snd.play('select')
            self.start_versus(Net(conn), True)

    def dr_host_wait(self):
        self.header("LAN // HOSTITEL")
        self.glitch_text(MODE_NAMES[self.cfg["mode"]], self.f_big, (W // 2, 130))
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
        self.txt("Podmínky: " + cfg_summary(self.cfg), self.f_small, AMBER, (W // 2, 520), "center")
        self.txt("ESC — zpět k podmínkám", self.f_small, DIM, (W // 2, H - 58), "center")
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
                    ip, (_, ver, _, _) = hosts[self.join_i]
                    if ver == PROTO:
                        self.connect_async(ip)
                    else:
                        self.join_status = "Hostitel má jinou verzi hry — stáhněte si oba stejnou."
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
        self.glitch_text("PŘIPOJIT SE", self.f_big, (W // 2, 130))
        self.panel(W // 2 - 300, 185, 600, 330, "NALEZENÁ STANOVIŠTĚ V SÍTI")
        hosts = getattr(self, "join_hosts", [])
        y = 225
        if not hosts:
            self.txt("Hledám hostitele" + "." * (int(self.t * 2) % 4), self.f_norm, DIM, (W // 2, y + 10), "center")
            y += 50
        for i, (ip, (name, ver, label, _)) in enumerate(hosts[:5]):
            sel = i == self.join_i
            if sel:
                pygame.draw.rect(self.canvas, (40, 34, 10), (W // 2 - 270, y - 4, 540, 34))
            if ver == PROTO:
                self.txt("%s — %s — %s" % (name, label or "?", ip), self.f_normb, AMBER if sel else TEXT,
                         (W // 2, y + 13), "center")
            else:
                self.txt("%s — JINÁ VERZE HRY — %s" % (name, ip), self.f_normb, DIM, (W // 2, y + 13), "center")
            y += 40
        sel = self.join_i == len(hosts)
        y = max(y + 10, 380)
        if sel:
            pygame.draw.rect(self.canvas, (40, 34, 10), (W // 2 - 270, y - 4, 540, 34))
        cur = "_" if sel and int(self.t * 3) % 2 else " "
        self.txt("Ručně IP:  " + (self.join_ip or "") + cur, self.f_normb, AMBER if sel else TEXT, (W // 2, y + 13), "center")
        if self.join_status:
            bad = any(w in self.join_status for w in ("selhal", "Neplat", "verzi"))
            self.txt(self.join_status, self.f_small, WARN if bad else ACID, (W // 2, 480), "center")
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
        self.round_no = 0
        self.mcfg = dict(self.cfg) if is_host else None   # klient je dostane se startem kola
        self.opp_name = "?"
        self.opp_state = None
        self.vg = None
        self.vs_phase = "wait"
        self.phase_t = 0.0
        self.blackout = 0.0
        self.opp_blackout = 0.0
        self.last_won = None
        self.last_draw = False
        self.round_note = ""
        self.host_in_setup = False
        self.my_done = False
        self.my_final = self.opp_final = None
        # MINISTERSTVO: kolo má dva poločasy, v každém jeden skládá a druhý úřaduje
        self.half = 1
        self.i_stack = False
        self.prev = None           # výsledek 1. poločasu (+ "mine": skládal jsem já)
        self.half_res = {}         # hostitel: výsledky skladatelů v tomto kole
        self.half_note = self.half_next = ""
        self.state = "versus"
        # hostitel odstartuje, až se soupeř ohlásí a má stejnou verzi hry
        net.send({"t": "hello", "name": self.player_name, "v": PROTO})

    def host_new_round(self, reset=False):
        if reset:
            self.wins = [0, 0]
            self.round_no = 0
        self.mcfg = dict(self.cfg)
        self.round_no += 1
        self.half = 1
        self.half_res = {}
        self.prev = None
        self.host_start()

    def host_start(self):
        """Hostitel rozešle start kola (v Ministerstvu poločasu) a sám ho začne."""
        seed = random.randrange(1 << 30)
        msg = {"t": "start", "seed": seed, "wins": [self.wins[1], self.wins[0]],
               "rnd": self.round_no, "cfg": self.mcfg}
        if self.mcfg["mode"] == "ministr":
            # v lichém kole skládá hostitel první, v sudém druhý
            self.i_stack = (self.round_no % 2 == 1) == (self.half == 1)
            prev = dict(self.prev, mine=not self.prev["mine"]) if self.prev else None
            msg.update(half=self.half, you_stack=not self.i_stack, prev=prev)
        self.net.send(msg)
        self.begin_round(seed)

    def begin_round(self, seed):
        c = self.mcfg
        sab = c["mode"] == "sabotaz"
        mini = c["mode"] == "ministr"
        if mini and not self.i_stack:
            self.vg = None             # úředník nemá vlastní desku
        else:
            self.vg = Game(seed, versus=sab, level=c["level"], atk=c["atk"], censor=sab and c["censor"],
                           ministry=mini)
        self.dir_charge = 0.0          # skladatel: nabíjení úředníkova razítka (počítá se tady)
        self.desk_sig = None
        self.my_pick = None            # úředník: (číslo nabídky, index), co právě odeslal
        self.dir_sent_t = -9.0
        self.seen = {"au": 0, "l": 0, "o": False}
        self.vs_phase = "countdown"
        self.countdown = 3.0
        self.blackout = 0.0
        self.opp_blackout = 0.0
        self.round_time = 0.0
        self.next_inflation = float(c["infl"]) if sab and c["infl"] else None
        self.my_done = False
        self.my_final = self.opp_final = None
        self.host_in_setup = False
        self.send_t = 0.0
        self.sent_dead = False
        self.opp_state = None
        self.das = DAS()
        self.snd.play('count')
        self.snd.music(True)

    def my_stats(self):
        return {"s": self.vg.score, "l": self.vg.lines, "tm": round(self.round_time, 2)}

    def race_done(self):
        """Závod: splněný cíl sprintu nebo vypršený limit časovky — deska zamrzne."""
        self.my_done = True
        self.my_final = self.my_stats()
        self.das = DAS()
        if self.mcfg["mode"] == "casovka":
            self.snd.play('alarm', 0.5)
        if self.is_host:
            self.host_race_check()
        else:
            self.net.send(dict(self.my_final, t="fin"))

    def host_race_check(self):
        if self.mcfg["mode"] == "sprint":
            # kdo první splní cíl, vyhrál — o pořadí rozhoduje hostitel
            if self.my_final:
                self.host_resolve(True, "fin")
            elif self.opp_final:
                self.host_resolve(False, "fin")
        elif self.my_final and self.opp_final:
            mine = (self.my_final["s"], self.my_final["l"])
            theirs = (self.opp_final["s"], self.opp_final["l"])
            self.host_resolve(mine > theirs, "time", draw=mine == theirs)

    # ---------------------------------------------------------- MINISTERSTVO
    def shift_done(self, top):
        """Skladateli skončil poločas — přetekl, nebo vydržel celý limit."""
        self.my_done = True
        self.my_final = dict(self.my_stats(), top=top)
        self.das = DAS()
        self.send_t = 0.0
        if self.is_host:
            self.host_half_done(True, self.my_final)
        else:
            self.net.send(dict(self.my_final, t="fin"))

    def host_half_done(self, host_stacked, res):
        if self.vs_phase != "play":
            return
        self.half_res["host" if host_stacked else "client"] = res
        if self.half == 1:
            self.net.send({"t": "half", "res": res, "mine": not host_stacked})
            self.half_over(res, host_stacked)
        else:
            self.my_final, self.opp_final = self.half_res.get("host"), self.half_res.get("client")
            mine, theirs = ministry_key(self.my_final), ministry_key(self.opp_final)
            self.host_resolve(mine > theirs, "min", draw=mine == theirs)

    def half_over(self, res, mine):
        """Konec 1. poločasu: výsledek skladatele, pak se role prohodí."""
        self.vs_phase = "half_end"
        self.phase_t = 3.5
        self.prev = dict(res, mine=mine)
        who, nxt = (self.player_name, self.opp_name) if mine else (self.opp_name, self.player_name)
        self.half_note = "%s: %s, kvóta %d." % (who, shift_text(res), res.get("s", 0))
        self.half_next = nxt
        self.blackout = self.opp_blackout = 0.0
        self.banner = None
        self.snd.play('levelup')

    def apply_directive(self, kind, col):
        """Skladatel: úředníkova direktiva platí jen s nabitým razítkem."""
        c = self.mcfg
        g = self.vg
        if not c["dirs"] or self.dir_charge < c["dirs"]:
            return
        if kind == "cens":
            self.blackout = CENSOR_T
            text = "DIREKTIVA: CENZURA HROMADY"
        elif g.directive(kind, col):
            if kind == "rush":
                text = "DIREKTIVA: ZRYCHLENÍ PÁDU"
            elif g.lock_col_next == col:
                text = "DIREKTIVA: SLOUPEC %d SE ZAMKNE PO DOPADU BLOKU" % (col + 1)
            else:
                text = "DIREKTIVA: SLOUPEC %d ZAMČEN" % (col + 1)
        else:
            return
        self.dir_charge = 0.0
        self.banner = (text, WARN, 1.8)
        self.glitch = 0.3
        self.snd.play('hack' if kind == "cens" else 'alarm', 0.7)
        self.send_t = 0.0

    def official_key(self, key, scancode):
        """Úředník: ←/→ přidělí blok z nabídky, Z/C/číslice vydají direktivu."""
        st = self.opp_state
        if not st or st.get("dn") or st.get("o"):
            return
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            oid = st.get("oid")
            if st.get("pk", -1) < 0 and (self.my_pick or (None,))[0] != oid:
                i = 0 if key == pygame.K_LEFT else 1
                self.net.send({"t": "pick", "oid": oid, "i": i})
                self.my_pick = (oid, i)
                self.snd.play('select')
            return
        if self.vs_phase != "play":
            return
        col = COL_KEYS.get(key, COL_SCANCODES.get(scancode))
        if key in (pygame.K_z, pygame.K_y):
            kind = "rush"
        elif key == pygame.K_c:
            kind = "cens"
        elif col is not None:
            kind = "col"
        else:
            return
        if not self.mcfg["dirs"]:
            self.banner = ("DIREKTIVY JSOU V TOMTO ZÁPASE VYPNUTÉ", DIM, 1.2)
        elif st.get("ch", 0) < 1 or self.t - self.dir_sent_t < 0.4:
            self.banner = ("RAZÍTKO SE JEŠTĚ NABÍJÍ", AMBER, 1.0)
            self.snd.play('tick')
        else:
            self.net.send({"t": "dir", "k": kind, "c": col})
            self.dir_sent_t = self.t
            self.banner = ("DIREKTIVA ODESLÁNA: " + DIRECTIVE_NAMES[kind]
                           + (" %d" % (col + 1) if kind == "col" else ""), CYAN, 1.4)
            self.snd.play('hack' if kind == "cens" else 'select')

    def official_watch(self):
        """Úředník: zvuky a hlášky podle toho, co se děje na skladatelově desce."""
        st = self.opp_state
        if not st:
            return
        seen = self.seen
        if st.get("au", 0) > seen["au"]:
            self.banner = ("NESTIHL JSI — BLOK PŘIDĚLIL AUTOMAT", AMBER, 1.2)
        if st.get("l", 0) > seen["l"]:
            self.snd.play('clear', 0.5)
        if st.get("o") and not seen["o"]:
            self.snd.play('gameover', 0.7)
        seen.update(au=st.get("au", 0), l=st.get("l", 0), o=bool(st.get("o")))

    def up_ministry(self, dt):
        c = self.mcfg
        g = self.vg
        if not self.i_stack:
            self.official_watch()
            return
        if self.my_done:
            return
        self.round_time += dt
        self.blackout = max(0.0, self.blackout - dt)
        if c["dirs"]:
            self.dir_charge = min(float(c["dirs"]), self.dir_charge + dt)
        if self.round_time >= c["half"]:
            self.round_time = float(c["half"])
            self.shift_done(False)
            return
        self.das.update(dt, g)
        g.update(dt, pygame.key.get_pressed()[pygame.K_DOWN])
        if g.over:
            self.shift_done(True)
        elif (g.offer_id, g.picked) != self.desk_sig:
            self.desk_sig = (g.offer_id, g.picked)
            self.send_t = 0.0          # nový stůl úředníkovi hned, ne až za 1/15 s

    def round_over(self, i_won, why="top", me=None, op=None, draw=False):
        self.vs_phase = "round_end"
        self.phase_t = 3.0
        self.last_won = i_won
        self.last_draw = draw
        self.round_note = self.round_text(i_won, why, me or {}, op or {}, draw)
        self.blackout = self.opp_blackout = 0.0
        self.banner = None
        self.snd.play('select' if draw else 'win' if i_won else 'lose')
        if not i_won and not draw:
            self.glitch = 0.4

    def round_text(self, won, why, me, op, draw):
        if draw:
            return "Kvóta %d : %d, řádky %d : %d. Kolo se nepočítá." % (
                me.get("s", 0), op.get("s", 0), me.get("l", 0), op.get("l", 0))
        if why == "fin":
            if won:
                return "Kvóta %d řádků splněna za %s." % (self.mcfg["lines"], fmt_race(me.get("tm", 0)))
            return "Soupeř splnil %d řádků za %s." % (self.mcfg["lines"], fmt_race(op.get("tm", 0)))
        if why == "time":
            s = "Kvóta po limitu %d : %d" % (me.get("s", 0), op.get("s", 0))
            if me.get("s") == op.get("s"):
                s += ", rozhodly řádky %d : %d" % (me.get("l", 0), op.get("l", 0))
            return s + "."
        if why == "min":
            return "Ty: %s · soupeř: %s." % (shift_text(me), shift_text(op))
        return "Soupeř přeřazen." if won else "Tvoje hromada přetekla."

    def host_resolve(self, host_won, why="top", draw=False):
        if self.vs_phase != "play":
            return
        if not draw:
            self.wins[0 if host_won else 1] += 1
        mine = self.my_final or self.my_stats()
        theirs = self.opp_final or clean_stats(self.opp_state)
        self.net.send({"t": "round", "you_won": not host_won and not draw, "draw": draw, "why": why,
                       "wins": [self.wins[1], self.wins[0]], "me": theirs, "op": mine})
        self.round_over(host_won and not draw, why, mine, theirs, draw)

    def ev_versus(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.snd.music(False)
                self.cleanup_net()
                self.state = "menu"
                return
            if self.vs_phase == "play" and self.vg and not self.vg.over and not self.my_done:
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
            elif (self.vs_phase in ("countdown", "play") and self.mcfg and self.mcfg["mode"] == "ministr"
                  and not self.i_stack):
                self.official_key(e.key, getattr(e, "scancode", 0))
            elif self.vs_phase == "match_end" and self.is_host:
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.host_new_round(reset=True)
                elif e.key == pygame.K_n:
                    self.snd.play('select')
                    self.start_setup(live=True)
        elif e.type == pygame.KEYUP:
            self.game_keyup(e.key)

    def up_versus(self, dt):
        net = self.net
        if net is None:
            self.state = "menu"
            return
        for m in net.poll():
            if self.vs_phase == "badver":
                break
            t = m.get("t")
            if t == "hello":
                self.opp_name = str(m.get("name", "?"))[:14]
                if m.get("v") != PROTO:
                    self.vs_phase = "badver"
                    self.snd.music(False)
                    self.snd.play('lose')
                    net.send({"t": "bye"})
                    net.close()
                    break
                if self.is_host and self.vs_phase == "wait":
                    self.host_new_round(reset=True)
            elif t == "start" and not self.is_host:
                self.wins = list(m.get("wins", [0, 0]))
                self.mcfg = clean_cfg(m.get("cfg"))
                self.round_no = int(m.get("rnd", sum(self.wins) + 1))
                self.half = 2 if m.get("half") == 2 else 1
                self.i_stack = bool(m.get("you_stack"))
                prev = m.get("prev")
                self.prev = dict(clean_stats(prev), mine=bool(prev.get("mine"))) if isinstance(prev, dict) else None
                self.begin_round(int(m["seed"]))
            elif t == "st":
                self.opp_state = m
            elif t == "pick":
                g = self.vg
                if (g and g.ministry and self.vs_phase in ("countdown", "play") and not self.my_done
                        and m.get("oid") == g.offer_id and g.picked is None and m.get("i") in (0, 1)):
                    g.picked = int(m["i"])
            elif t == "dir":
                if self.vg and self.vg.ministry and self.vs_phase == "play" and not self.my_done:
                    try:
                        col = int(m.get("c"))
                    except (TypeError, ValueError):
                        col = -1
                    self.apply_directive(str(m.get("k")), col)
            elif t == "half" and not self.is_host:
                self.half_over(clean_stats(m.get("res")), bool(m.get("mine")))
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
            elif t == "fin" and self.is_host:
                if self.mcfg["mode"] == "ministr":
                    if not self.i_stack:
                        self.host_half_done(False, clean_stats(m))
                elif self.vs_phase == "play" and self.opp_final is None:
                    self.opp_final = clean_stats(m)
                    self.host_race_check()
            elif t == "round" and not self.is_host:
                self.wins = list(m.get("wins", self.wins))
                self.round_over(bool(m.get("you_won")), str(m.get("why", "top")),
                                clean_stats(m.get("me")), clean_stats(m.get("op")), bool(m.get("draw")))
            elif t == "setup" and not self.is_host:
                self.host_in_setup = bool(m.get("on"))
            elif t == "bye":
                net.alive = False
        if not net.alive and self.vs_phase not in ("disconnected", "badver"):
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
        elif ph == "play" and self.mcfg["mode"] == "ministr":
            self.up_ministry(dt)
        elif ph == "play" and g:
            mode = self.mcfg["mode"]
            if not self.my_done:
                self.round_time += dt
                if mode == "casovka" and self.round_time >= self.mcfg["limit"]:
                    self.round_time = float(self.mcfg["limit"])
                    self.race_done()
            self.blackout = max(0.0, self.blackout - dt)
            self.opp_blackout = max(0.0, self.opp_blackout - dt)
            if not self.my_done:
                self.das.update(dt, g)
                g.update(dt, pygame.key.get_pressed()[pygame.K_DOWN])
                if mode == "sprint" and g.lines >= self.mcfg["lines"]:
                    self.race_done()
            if g.outgoing > 0:
                net.send({"t": "garbage", "n": g.outgoing, "gap": random.randrange(COLS)})
                g.outgoing = 0
            if self.next_inflation is not None and self.round_time >= self.next_inflation:
                self.next_inflation += 15
                g.pending.append((1, random.randrange(COLS)))
                self.banner = ("INFLACE KVÓTY: +1 ŘÁDEK", AMBER, 1.2)
                self.snd.play('alarm', 0.4)
            if g.over and not self.sent_dead and not self.my_done:
                self.sent_dead = True
                if self.is_host:
                    self.host_resolve(False)
                else:
                    net.send({"t": "dead"})
        elif ph == "round_end":
            self.phase_t -= dt
            if self.phase_t <= 0:
                if max(self.wins) >= self.mcfg["wins"]:
                    self.vs_phase = "match_end"
                    self.snd.music(False)
                    self.snd.play('win' if self.wins[0] >= self.mcfg["wins"] else 'gameover')
                elif self.is_host:
                    self.host_new_round()
                else:
                    self.vs_phase = "wait"
        elif ph == "half_end":
            self.phase_t -= dt
            if self.phase_t <= 0 and self.is_host:
                self.half = 2
                self.host_start()
        if g:
            self.process_events(g, self.VX, self.VY, versus=True)
            self.send_t -= dt
            if self.send_t <= 0 and ph in ("countdown", "play", "round_end", "half_end"):
                self.send_t = 1 / 15
                msg = {"t": "st", "b": g.board_string(), "p": g.piece_visible(), "gh": g.ghost_visible(),
                       "k": g.kind, "s": g.score, "l": g.lines, "lv": g.level, "h": g.hack,
                       "g": g.pending_total(), "o": g.over, "dn": self.my_done, "hd": g.hold,
                       "bo": self.blackout > 0}
                if g.ministry:
                    dirs = self.mcfg["dirs"]
                    msg.update(nx=g.nexts[:1], of=g.offer, oid=g.offer_id, au=g.auto_picks,
                               pk=-1 if g.picked is None else g.picked,
                               lc=-1 if g.lock_col is None else g.lock_col, lct=round(g.lock_col_t, 1),
                               lcn=-1 if g.lock_col_next is None else g.lock_col_next,
                               rs=round(g.rush_t, 1), bt=round(self.blackout, 1), tm=round(self.round_time, 2),
                               ch=round(self.dir_charge / dirs, 3) if dirs else 0)
                net.send(msg)

    def board_tag(self, ox, oy, title, sub, col):
        """Štítek přes zamrzlou desku (splněný cíl / vypršený čas)."""
        s = pygame.Surface((COLS * CELL, 80), pygame.SRCALPHA)
        s.fill((0, 0, 0, 200))
        self.canvas.blit(s, (ox, oy + 250))
        self.txt(title, self.f_normb, col, (ox + COLS * CELL // 2, oy + 276), "center")
        self.txt(sub, self.f_small, TEXT, (ox + COLS * CELL // 2, oy + 306), "center")

    def censor_panel(self, g, x, y):
        self.panel(x, y, 120, 150, "CENZURA", CYAN)
        if not self.mcfg["censor"]:
            self.txt("VYPNUTA", self.f_normb, DIM, (x + 60, y + 75), "center")
            return
        full = g.hack >= 100
        bh = int(100 * g.hack / 100)
        pygame.draw.rect(self.canvas, (10, 30, 30), (x + 45, y + 30, 30, 100))
        pygame.draw.rect(self.canvas, CYAN if not full or int(self.t * 5) % 2 else (255, 255, 255),
                         (x + 45, y + 130 - bh, 30, bh))
        if full:
            self.txt("ENTER!", self.f_normb, CYAN, (x + 60, y + 160), "center")

    def race_panel(self, g, st, x, y):
        """Dva sloupce TY / SOUPEŘ: řádky k cíli sprintu, nebo kvóta v časovce."""
        c = self.mcfg
        self.panel(x, y, 120, 150, "ZÁVOD", ACID)
        if c["mode"] == "sprint":
            mine, theirs, top = g.lines, int(st.get("l", 0)) if st else 0, c["lines"]
        else:
            mine, theirs = g.score, int(st.get("s", 0)) if st else 0
            top = max(mine, theirs, 1)
        for i, (val, label, col) in enumerate(((mine, "TY", ACID), (theirs, "SOUPEŘ", AMBER))):
            cx = x + 33 + i * 54
            fill = int(90 * min(1.0, val / top))
            self.txt(str(val), self.f_tiny, col, (cx, y + 22), "midtop")
            pygame.draw.rect(self.canvas, (20, 24, 18), (cx - 11, y + 38, 22, 90))
            pygame.draw.rect(self.canvas, col, (cx - 11, y + 128 - fill, 22, fill))
            self.txt(label, self.f_tiny, DIM, (cx, y + 132), "midtop")

    def clock_panel(self, x, y):
        c = self.mcfg
        if c["mode"] == "sprint":
            self.panel(x, y, 110, 90, "ČAS", ACID)
            self.txt(fmt_race(self.round_time), self.f_normb, TEXT, (x + 55, y + 40), "center")
            self.txt("do cíle %d" % max(0, c["lines"] - self.vg.lines), self.f_small, DIM, (x + 55, y + 66), "center")
        elif c["mode"] == "casovka":
            left = max(0.0, c["limit"] - self.round_time)
            self.panel(x, y, 110, 90, "ZBÝVÁ", AMBER)
            col = WARN if left < 10 and int(self.t * 4) % 2 else TEXT
            self.txt(fmt_clock(math.ceil(left)), self.f_med, col, (x + 55, y + 47), "center")
        else:
            self.panel(x, y, 110, 90, "INFLACE", AMBER)
            if self.next_inflation is None:
                self.txt("VYPNUTA", self.f_normb, DIM, (x + 55, y + 45), "center")
                return
            t_left = max(0, self.next_inflation - self.round_time)
            if self.round_time < c["infl"]:
                self.txt("za %ds" % t_left, self.f_normb, TEXT, (x + 55, y + 45), "center")
            else:
                self.txt("AKTIVNÍ", self.f_normb, WARN, (x + 55, y + 35), "center")
                self.txt("+1 za %ds" % t_left, self.f_small, TEXT, (x + 55, y + 63), "center")

    # ---------------------------------------------------------- MINISTERSTVO: kreslení
    def lock_marks(self, ox, oy, col, t_left, col_next):
        """Zamčený sloupec (červeně, se zbývajícími sekundami) a zámek čekající na dopad bloku."""
        if col is not None and col >= 0:
            x = ox + col * CELL
            s = pygame.Surface((CELL, ROWS * CELL), pygame.SRCALPHA)
            s.fill((255, 58, 48, 60))
            self.canvas.blit(s, (x, oy))
            pygame.draw.rect(self.canvas, WARN, (x, oy, CELL, ROWS * CELL), 2)
            self.txt(str(max(1, math.ceil(t_left))), self.f_normb, WARN, (x + CELL // 2, oy + 16), "center")
        if col_next is not None and col_next >= 0:
            x = ox + col_next * CELL
            pygame.draw.rect(self.canvas, AMBER, (x, oy, CELL, ROWS * CELL), 1)
            self.txt("…", self.f_normb, AMBER, (x + CELL // 2, oy + 16), "center")

    def stats_panel(self, x, y, title, vals):
        self.panel(x, y, 120, 220, title)
        for i, (k, v) in enumerate(vals):
            self.txt(k, self.f_tiny, DIM, (x + 12, y + 25 + i * 62))
            self.txt(str(v), self.f_med, TEXT, (x + 12, y + 39 + i * 62))

    def lines_panel(self, x, y, w, h, title, lines, col=ACID):
        """Panel s několika řádky textu: [(text, písmo, barva)]."""
        self.panel(x, y, w, h, title, col)
        yy = y + 26
        for text, font, color in lines:
            self.txt(text, font, color, (x + 12, yy))
            yy += font.get_linesize() + 2

    def half_clock(self, x, y, elapsed):
        left = max(0.0, self.mcfg["half"] - elapsed)
        self.panel(x, y, 110, 90, "ZBÝVÁ", AMBER)
        col = WARN if left < 10 and int(self.t * 4) % 2 else TEXT
        self.txt(fmt_clock(math.ceil(left)), self.f_med, col, (x + 55, y + 42), "center")
        self.txt("%d. poločas" % self.half, self.f_tiny, DIM, (x + 55, y + 70), "center")

    def effects_panel(self, g, x, y):
        """Skladatel: co úředník právě nařídil a jak má nabité razítko."""
        dirs = self.mcfg["dirs"]
        self.panel(x, y, 120, 150, "DIREKTIVY", WARN)
        if not dirs:
            self.txt("VYPNUTY", self.f_normb, DIM, (x + 60, y + 75), "center")
            return
        charge = self.dir_charge / dirs
        full = charge >= 1
        self.txt("RAZÍTKO ÚŘEDNÍKA", self.f_tiny, DIM, (x + 12, y + 24))
        pygame.draw.rect(self.canvas, (30, 14, 12), (x + 12, y + 42, 96, 10))
        pygame.draw.rect(self.canvas, WARN if not full or int(self.t * 4) % 2 else (255, 255, 255),
                         (x + 12, y + 42, int(96 * min(1.0, charge)), 10))
        self.txt("HROZÍ ZÁSAH" if full else "nabíjí se", self.f_tiny, WARN if full else DIM, (x + 12, y + 56))
        act = []
        if g.rush_t > 0:
            act.append("ZRYCHLENO %ds" % math.ceil(g.rush_t))
        if g.lock_col is not None:
            act.append("ZÁMEK %d: %ds" % (g.lock_col + 1, math.ceil(g.lock_col_t)))
        if g.lock_col_next is not None:
            act.append("ZÁMEK %d ČEKÁ" % (g.lock_col_next + 1))
        if self.blackout > 0:
            act.append("CENZURA %ds" % math.ceil(self.blackout))
        for i, s in enumerate(act[:3]):
            self.txt(s, self.f_small, WARN, (x + 12, y + 80 + i * 21))

    def desk_small(self, g, x, y):
        """Skladatel: co má úředník na stole a co už přidělil."""
        self.panel(x, y, 110, 160, "STŮL ÚŘEDNÍKA", CYAN)
        for i, k in enumerate(g.offer[:2]):
            cx = x + 30 + i * 50
            chosen = g.picked == i
            if chosen:
                pygame.draw.rect(self.canvas, ACID, (cx - 24, y + 42, 48, 48), 1)
            self.mini_piece(k, cx, y + 66, 11, dim=g.picked is not None and not chosen)
        done = g.picked is not None
        self.txt("PŘIDĚLENO" if done else "vybírá…", self.f_small, ACID if done else DIM, (x + 55, y + 112), "center")
        self.txt("až po přídělu", self.f_tiny, DIM, (x + 55, y + 136), "center")

    def desk_big(self, st, x, y):
        """Úředník: dva bloky na stole, ←/→ jeden z nich přidělí skladateli."""
        offer = st.get("of") or []
        oid = st.get("oid")
        picked = st.get("pk", -1)
        if picked < 0 and self.my_pick and self.my_pick[0] == oid:
            picked = self.my_pick[1]       # odesláno, potvrzení skladatele ještě letí sítí
        self.panel(x, y, 460, 290, "ÚŘEDNÍ STŮL · PŘIDĚL SKLADATELI DALŠÍ BLOK", CYAN)
        for i, k in enumerate(offer[:2]):
            cx = x + 110 + i * 240
            chosen = picked == i
            rect = (cx - 85, y + 35, 170, 170)
            pygame.draw.rect(self.canvas, (12, 14, 15), rect)
            pygame.draw.rect(self.canvas, ACID if chosen else EDGE, rect, 3 if chosen else 1)
            self.mini_piece(k, cx, y + 120, 30, dim=picked >= 0 and not chosen)
            self.txt("◄  ←" if i == 0 else "→  ►", self.f_normb, AMBER if picked < 0 else DIM, (cx, y + 228), "center")
        self.txt("nebo", self.f_small, DIM, (x + 230, y + 120), "center")
        if picked >= 0:
            self.txt("SCHVÁLENO — další nabídka po dopadu bloku", self.f_small, ACID, (x + 230, y + 264), "center")
        else:
            self.txt("Vyber dřív, než skladatel položí blok.", self.f_small, TEXT, (x + 230, y + 264), "center")

    def directive_panel(self, st, x, y):
        """Úředník: nabíjení razítka, klávesy direktiv a co právě platí."""
        dirs = self.mcfg["dirs"]
        self.panel(x, y, 300, 235, "DIREKTIVY", WARN)
        if not dirs:
            self.txt("V tomto zápase vypnuté.", self.f_small, DIM, (x + 150, y + 110), "center")
            return
        ch = min(1.0, st.get("ch", 0))
        ready = ch >= 1
        self.txt("RAZÍTKO", self.f_tiny, DIM, (x + 15, y + 24))
        pygame.draw.rect(self.canvas, (30, 14, 12), (x + 15, y + 42, 270, 12))
        pygame.draw.rect(self.canvas, WARN if not ready or int(self.t * 4) % 2 else (255, 255, 255),
                         (x + 15, y + 42, int(270 * ch), 12))
        self.txt("PŘIPRAVENO — vydej direktivu!" if ready else "nabije se za %d s" % math.ceil((1 - ch) * dirs),
                 self.f_small, ACID if ready else DIM, (x + 15, y + 62))
        for i, (k, name) in enumerate((("Z", "ZRYCHLENÍ PÁDU · 10 s"), ("C", "CENZURA HROMADY · 5 s"),
                                       ("1–3 8–0", "ZÁMEK SLOUPCE · 10 s"))):
            yy = y + 96 + i * 28
            self.txt(k, self.f_normb, AMBER if ready else DIM, (x + 15, yy))
            self.txt(name, self.f_small, TEXT if ready else DIM, (x + 105, yy + 3))
        act = []
        if st.get("rs", 0) > 0:
            act.append("zrychlení %ds" % math.ceil(st["rs"]))
        if st.get("lc", -1) >= 0:
            act.append("zámek %d: %ds" % (st["lc"] + 1, math.ceil(st.get("lct", 0))))
        if st.get("lcn", -1) >= 0:
            act.append("zámek %d čeká na dopad" % (st["lcn"] + 1))
        if st.get("bt", 0) > 0:
            act.append("cenzura %ds" % math.ceil(st["bt"]))
        self.txt("PLATÍ: " + (", ".join(act) if act else "nic"), self.f_small, WARN if act else DIM,
                 (x + 15, y + 190))

    def dr_ministry(self):
        c = self.mcfg
        vx, vy = self.VX, self.VY
        p = self.prev
        if self.i_stack:
            g = self.vg
            if not g:
                return
            self.local_board(g, vx, vy, blackout=self.blackout > 0)
            self.lock_marks(vx, vy, g.lock_col, g.lock_col_t, g.lock_col_next)
            self.panel(30, vy, 120, 110, "ZADRŽENO")
            self.mini_piece(g.hold, 90, vy + 62, 18, dim=g.hold_used)
            self.stats_panel(30, vy + 125, "SPIS", [("KVÓTA", g.score), ("ŘÁDKY", g.lines), ("SMĚNA", g.level)])
            self.effects_panel(g, 30, vy + 360)
            self.panel(500, vy, 110, 110, "PŘÍDĚL")
            self.mini_piece(g.nexts[0], 555, vy + 62, 18)
            self.desk_small(g, 500, vy + 125)
            self.half_clock(500, vy + 300, self.round_time)
            self.panel(640, vy, 460, 260, "ÚŘEDNÍK MINISTERSTVA")
            self.txt(self.opp_name, self.f_med, AMBER, (870, vy + 38), "center")
            self.eye(870, vy + 140, vx + g.x * CELL + CELL)
            self.txt("nestihl vybrat: %d×" % g.auto_picks, self.f_tiny, DIM, (870, vy + 236), "center")
            if p and not p["mine"]:
                lines = [("Překonej výkon %s:" % self.opp_name, self.f_small, TEXT),
                         ("přetečení v " + fmt_race(p["tm"]) if p["top"] else "celý poločas", self.f_normb, ACID),
                         ("%s · kvóta %d" % (radky(p["l"]), p["s"]), self.f_small, TEXT)]
            else:
                lines = [("Skládáš jako první —", self.f_small, TEXT),
                         ("nastavuješ laťku.", self.f_normb, ACID),
                         ("Vydrž co nejdéle a maž řádky.", self.f_small, DIM)]
            self.lines_panel(640, vy + 275, 300, 110, "LAŤKA", lines)
            return
        st = self.opp_state
        if not st:
            self.draw_board(vx, vy, [[None] * COLS for _ in range(ROWS)], [], None, [])
            self.txt("SIGNÁL SKLADATELE…", self.f_normb, DIM, (vx + 150, vy + 300), "center")
            return
        b = st.get("b", "." * 200)
        rows = [list(b[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]
        self.draw_board(vx, vy, rows, [tuple(q) for q in st.get("p", [])], st.get("k"),
                        [tuple(q) for q in st.get("gh", [])], over=st.get("o", False))
        self.lock_marks(vx, vy, st.get("lc", -1), st.get("lct", 0), st.get("lcn", -1))
        ready = bool(c["dirs"]) and st.get("ch", 0) >= 1
        for col, label in COL_LABELS.items():
            self.txt(label, self.f_tiny, AMBER if ready else DIM,
                     (vx + col * CELL + CELL // 2, vy + ROWS * CELL + 13), "center")
        if st.get("bt", 0) > 0:
            self.txt("CENZUROVÁNO %.1fs" % st["bt"], self.f_normb, CYAN, (vx + 150, vy + 300), "center")
        self.panel(30, vy, 120, 110, "ZADRŽENO")
        self.mini_piece(st.get("hd"), 90, vy + 62, 18)
        self.stats_panel(30, vy + 125, "SPIS SKLADATELE",
                         [("KVÓTA", st.get("s", 0)), ("ŘÁDKY", st.get("l", 0)), ("SMĚNA", st.get("lv", 1))])
        if p and p["mine"]:
            lines = [("TVŮJ VÝKON:", self.f_tiny, DIM),
                     ("přetečení" if p["top"] else "celý poločas", self.f_small, ACID)]
            if p["top"]:
                lines.append(("v " + fmt_race(p["tm"]), self.f_small, ACID))
            lines += [(radky(p["l"]), self.f_small, TEXT), ("kvóta %d" % p["s"], self.f_tiny, DIM),
                      ("Nedovol mu ho", self.f_tiny, DIM), ("překonat.", self.f_tiny, DIM)]
        else:
            lines = [("Skladatel teprve", self.f_tiny, TEXT), ("nastavuje laťku.", self.f_tiny, TEXT),
                     ("", self.f_tiny, DIM), ("Pak se role", self.f_tiny, DIM), ("prohodí.", self.f_tiny, DIM)]
        self.lines_panel(30, vy + 360, 120, 150, "LAŤKA", lines)
        self.panel(500, vy, 110, 110, "PŘÍDĚL")
        nx = st.get("nx") or []
        self.mini_piece(nx[0] if nx else None, 555, vy + 62, 18)
        self.half_clock(500, vy + 125, st.get("tm", 0))
        self.desk_big(st, 640, vy)
        self.directive_panel(st, 640, vy + 305)

    def dr_versus(self):
        c = self.mcfg
        mini = bool(c) and c["mode"] == "ministr"
        race = bool(c) and c["mode"] in ("sprint", "casovka")
        self.header("LAN // " + (MODE_NAMES[c["mode"]] if c else "SPOJENO"))
        g = self.vg
        st = self.opp_state
        vx, vy, ox, oy = self.VX, self.VY, self.OX, self.OY
        # skóre zápasu
        self.txt("%s  %d : %d  %s" % (self.player_name, self.wins[0], self.wins[1], self.opp_name),
                 self.f_normb, AMBER, (W // 2, 20), "center")
        if mini:
            self.dr_ministry()
        elif g:
            self.local_board(g, vx, vy, blackout=self.blackout > 0)
            if not race:
                self.garbage_bar(vx - 20, vy, g.pending_total())
            # levý panel
            self.panel(30, vy, 120, 110, "ZADRŽENO")
            self.mini_piece(g.hold, 90, vy + 62, 18, dim=g.hold_used)
            self.panel(30, vy + 125, 120, 220, "SPIS")
            lines = "%d/%d" % (g.lines, c["lines"]) if c["mode"] == "sprint" else str(g.lines)
            for i, (k, v) in enumerate([("KVÓTA", g.score), ("ŘÁDKY", lines), ("SMĚNA", g.level)]):
                self.txt(k, self.f_tiny, DIM, (42, vy + 150 + i * 62))
                self.txt(str(v), self.f_med, TEXT, (42, vy + 164 + i * 62))
            if race:
                self.race_panel(g, st, 30, vy + 360)
            else:
                self.censor_panel(g, 30, vy + 360)
            # příděl
            self.panel(500, vy, 110, 300, "PŘÍDĚL")
            for i, k in enumerate(g.nexts[:4]):
                self.mini_piece(k, 555, vy + 58 + i * 64, 18 if i == 0 else 15)
            self.clock_panel(500, vy + 315)
            if self.my_done and self.vs_phase == "play":
                if c["mode"] == "sprint":
                    self.board_tag(vx, vy, "KVÓTA SPLNĚNA", fmt_race(self.my_final["tm"]), ACID)
                else:
                    self.board_tag(vx, vy, "ČAS VYPRŠEL", "kvóta %d · čekám na soupeře…" % g.score, AMBER)
        # soupeř
        if mini:
            pass                       # v Ministerstvu kreslí desku i stůl dr_ministry
        elif st:
            b = st.get("b", "." * 200)
            rows = [list(b[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]
            self.draw_board(ox, oy, rows, [tuple(p) for p in st.get("p", [])], st.get("k"),
                            [tuple(p) for p in st.get("gh", [])], over=st.get("o", False))
            if not race:
                self.garbage_bar(ox + COLS * CELL + 12, oy, int(st.get("g", 0)))
            if self.opp_blackout > 0:
                self.txt("CENZUROVÁNO %.1fs" % self.opp_blackout, self.f_normb, CYAN, (ox + 150, oy + 300), "center")
            if st.get("dn") and self.vs_phase == "play":
                if c["mode"] == "sprint":
                    self.board_tag(ox, oy, "CÍL SPLNĚN", "", ACID)
                else:
                    self.board_tag(ox, oy, "ČAS VYPRŠEL", "kvóta %s" % st.get("s", 0), AMBER)
            self.panel(962, oy, 138, 250, "SOUPEŘ")
            self.txt(self.opp_name, self.f_normb, AMBER, (975, oy + 30))
            if race:
                third = ("SMĚNA", str(st.get("lv", 1)))
            elif c and not c["censor"]:
                third = ("CENZURA", "VYP")
            else:
                third = ("CENZURA", "%s%%" % st.get("h", 0))
            lines = str(st.get("l", 0)) + ("/%d" % c["lines"] if c and c["mode"] == "sprint" else "")
            for i, (k, val) in enumerate([("KVÓTA", str(st.get("s", 0))), ("ŘÁDKY", lines), third]):
                self.txt(k, self.f_tiny, DIM, (975, oy + 70 + i * 55))
                self.txt(val, self.f_med, TEXT, (975, oy + 84 + i * 55))
            self.mini_piece(st.get("hd"), 1031, oy + 300, 15)
        else:
            self.draw_board(ox, oy, [[None] * COLS for _ in range(ROWS)], [], None, [])
            self.txt("SIGNÁL SOUPEŘE…", self.f_normb, DIM, (ox + 150, oy + 300), "center")
        if c:
            parts = cfg_parts(c)
            self.panel(962, oy + 340, 138, 30 + 18 * len(parts), "PODMÍNKY")
            for i, s in enumerate(parts):
                self.txt(s, self.f_tiny, TEXT, (970, oy + 362 + i * 18))
        # překryvy fází
        ph = self.vs_phase
        if ph == "countdown" and mini:
            n = max(1, math.ceil(self.countdown))
            if self.i_stack:
                role = "SKLÁDÁŠ TY"
                hint = "Vydrž %s. Úředník %s ti vybírá bloky a vydává direktivy." % (fmt_clock(c["half"]),
                                                                                     self.opp_name)
            else:
                role = "ÚŘADUJEŠ TY"
                hint = "←/→ přiděluj bloky, Z · C · 1–3 / 8–0 vydávej direktivy. Skládá %s." % self.opp_name
            self.dim_box(str(n), "MINISTERSTVO · kolo %d · %d. poločas · %s" % (self.round_no, self.half, role),
                         extra=hint)
        elif ph == "countdown":
            n = max(1, math.ceil(self.countdown))
            what = "ZÁVOD SMĚN ZAČÍNÁ" if race else "AUDIT ZAČÍNÁ"
            self.dim_box(str(n), "%s · kolo %d" % (what, self.round_no), extra=cfg_summary(c))
        elif ph == "half_end":
            self.dim_box("KONEC POLOČASU", self.half_note, AMBER,
                         extra="Role se prohodí — teď skládá %s." % self.half_next)
        elif ph == "round_end":
            score = "   %d : %d" % tuple(self.wins)
            if self.last_draw:
                self.dim_box("REMÍZA", self.round_note + score, AMBER)
            elif self.last_won:
                self.dim_box("KOLO TVOJE", self.round_note + score, ACID)
            else:
                self.dim_box("KOLO ZTRACENO", self.round_note + score, WARN)
        elif ph == "match_end":
            won = self.wins[0] >= c["wins"]
            if self.is_host:
                sub = "ENTER — odveta   N — změnit podmínky   ESC — menu"
            elif self.host_in_setup:
                sub = "Hostitel upravuje podmínky odvety…   ESC — menu"
            else:
                sub = "Čekám, až hostitel spustí odvetu…   ESC — menu"
            head = "NEJLEPŠÍ SKLADATEL: " if mini else "ZÁVOD VYHRÁL: " if race else "AUDIT PŘEŽIL: "
            self.dim_box(head + (self.player_name if won else self.opp_name), sub, ACID if won else WARN)
        elif ph == "wait":
            self.dim_box("SPOJENO", "Čekám na soupeře…" if self.is_host else "Čekám na hostitele…")
        elif ph == "badver":
            self.dim_box("JINÁ VERZE HRY", "Soupeř má jinou verzi KVÓTY, stáhněte si oba stejnou.   ESC — menu", WARN)
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
