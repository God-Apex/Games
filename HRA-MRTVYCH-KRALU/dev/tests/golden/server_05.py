#!/usr/bin/env python3
"""Hra mrtvych kralu - LAN server: serves the game and runs the authoritative 1v1 simulation.

Usage:  python server.py [port]        (default port 8095)
Needs only the Python 3.8+ standard library.
"""
import asyncio
import base64
import hashlib
import json
import math
import os
import random
import socket
import struct
import sys
import time
import traceback
import webbrowser
from collections import deque

PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8095
ROOT = os.path.dirname(os.path.abspath(__file__))
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
VERSION = '0.5'
MAX_CONN = 8          # 2 players + waiting queue
KICK_IDLE = 30        # a waiting player may free a slot held by someone idle (and not ready) this long
PING_EVERY = 5.0
DEAD_AFTER = 20.0

try:                  # player names may contain characters the console cannot print
    sys.stdout.reconfigure(errors='replace', line_buffering=True)
except (AttributeError, ValueError):
    pass

# ---------------------------------------------------------------- rules

W, H = 16, 9
HALF = 6                      # side 0 owns columns 0-5, side 1 owns 10-15
MIST = (6, 9)                 # neutral Mist columns at the start (inclusive)
TICK = 0.05
SNAP_EVERY = 1                # 20 snapshots/s, the King needs smooth movement
THRONE_HP = 3000
START_RES = (200.0, 40.0)
BASE_INCOME = 1.5
LVL_MULT = (1.0, 1.35, 1.7)
HORDE_COST, HORDE_CD = 120, 25.0
SCRAP_TIME, SCRAP_GAIN = 4.0, 25
CHECK_TIME = 10.0
ECLIPSES = (240, 420, 600)    # Zatmění: start times; skipped once Poslední noc has begun
ECL_LEN, ECL_WARN = 25, 15
RELIC = (7, 8, 3, 5)          # Relikvie zone: columns 7-8, rows 3-5
RELIC_FROM, RELIC_TIME, RELIC_SAMPLE = 120, 5.0, 40.0
CONV = (30, 10, 2)            # Přetavení: energy -> scrap, from Doba II (earlier it buys a 1-minute generator rush)
CRATE_CH = 3.0                # seconds of channelling to open a supply crate
STREAK = 4.0                  # max gap between kills in a kill streak
KING_DEAD = 'Tvůj Král je mrtvý, teď nemůžeš stavět.'
MODES = ('kral', 'strateg')
DECK_SIZE = 8
BASE_KIT = ('gen', 'zed')
RECOMMENDED = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'dron']
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))

DEFS = {
    # ---- buildings
    'gen': {'cat': 'b', 'name': 'Generátor', 'cost': [50, 0], 'hp': 180, 'vision': 1.5,
            'desc': 'Vyrábí energii (+2 ⚡/s). První 3 za základní cenu, další dražší.',
            'paths': {'A': ['Reaktor', '+3 ⚡/s navíc.'], 'B': ['Štítový uzel', 'Sousední stavby dostávají o 30 % méně poškození.']}},
    'zed': {'cat': 'b', 'name': 'Zeď', 'cost': [0, 15], 'hp': 350, 'vision': 1.5, 'hps': [350, 800, 1600],
            'levels': ['Dřevěná', 'Plechová', 'Betonová'], 'up': [[0, 25], [0, 45]],
            'desc': 'Blokuje nepřátele a zombie. Tvoje jednotky i Král projdou.'},
    'kulomet': {'cat': 'b', 'name': 'Kulomet', 'cost': [50, 0], 'hp': 220, 'range': 3.2, 'dmg': 9, 'rate': 0.45, 'vision': 2.5,
                'desc': 'Levná rychlá palba na nejbližší hrozbu.',
                'paths': {'A': ['Dvojhlaveň', 'Střílí dvakrát rychleji.'], 'B': ['Průbojné střely', 'Zasáhne i druhý cíl, +50 % poškození.']}},
    'plamen': {'cat': 'b', 'name': 'Plamenomet', 'cost': [75, 0], 'hp': 280, 'range': 1.6, 'dmg': 7, 'rate': 0.35, 'vision': 2.5,
               'desc': 'Krátký dosah, pálí všechno kolem sebe.',
               'paths': {'A': ['Napalm', 'Zapálí cíle: 6 poškození/s po 4 s.'], 'B': ['Široký kužel', 'Dosah 2,6 pole.']}},
    'sniper': {'cat': 'b', 'name': 'Odstřelovač', 'cost': [100, 0], 'hp': 160, 'range': 7.0, 'dmg': 70, 'rate': 2.6, 'vision': 3.0, 'aim': 0.5,
               'desc': 'Velký dosah, ale střílí jen na to, co vidíš. Před výstřelem 0,5 s míří rudou nití. '
                       'První 2 stojí 100 ⚡, každý další o 40 ⚡ víc.',
               'paths': {'A': ['Průstřel', 'Zasáhne 3 cíle naráz.'], 'B': ['Značkovač', 'Cíl dostává 5 s o 25 % víc poškození.']}},
    'hlaska': {'cat': 'b', 'name': 'Hláska', 'cost': [40, 0], 'hp': 150, 'vision': 4.5,
               'desc': 'Velký dohled do Mlhy a na soupeře (průzkum). Věže střílí jen tam, kam vidíš.',
               'paths': {'A': ['Dalekohled', 'Dohled 7 polí.'],
                         'B': ['Reflektor', 'Odhalí miny, sabotéry a maskované stavby. Nepřátelé v dohledu dostávají +15 % poškození. '
                                            'Za tmy svítí na 3 pole.']}},
    'tesla': {'cat': 'b', 'name': 'Tesla cívka', 'cost': [110, 0], 'hp': 240, 'range': 2.6, 'dmg': 16, 'rate': 1.1, 'vision': 2.5, 'doba': 2,
              'desc': 'Blesk přeskočí až na 3 cíle.',
              'paths': {'A': ['Bouře', 'Blesk přeskočí až na 5 cílů.'], 'B': ['Paralyzátor', 'Zasažené cíle omráčí na 0,8 s.']}},
    'mina': {'cat': 'b', 'name': 'Minové pole', 'cost': [40, 0], 'hp': 60, 'dmg': 130, 'vision': 0.8,
             'desc': 'Soupeř ji nevidí. Vybuchne, když na ni vstoupí nepřítel nebo zombie (130 poškození v okolí).',
             'paths': {'A': ['Chemická', 'Zasažené zpomalí o 50 % na 5 s.'], 'B': ['EMP', 'Zasažené omráčí na 2,5 s.']}},
    'rusicka': {'cat': 'b', 'name': 'Rušička', 'cost': [60, 0], 'hp': 160, 'vision': 2.0,
                'desc': 'Zpomaluje nepřátele i zombie v okolí (o 25 %, dosah 1,6).',
                'paths': {'A': ['Maskování', 'Tvoje stavby v okruhu 1,6 soupeř nevidí, dokud k nim nedojde.'],
                          'B': ['Silné rušení', 'Zpomalení o 45 % v okruhu 2,4.']}},
    # ---- units (chess movement)
    'pesak': {'cat': 'u', 'name': 'Pěšák', 'cost': [30, 0], 'hp': 90, 'dmg': 10, 'rate': 0.8, 'step': 1.6, 'vision': 2.2,
              'desc': 'Jde rovně vpřed, útočí šikmo jako v šachu. Za Mlhou se stane veteránem, '
                      'u soupeřova trůnu se promění v Dámu (když žádnou nemáš).'},
    'jezdec': {'cat': 'u', 'name': 'Jezdec', 'cost': [70, 0], 'hp': 120, 'dmg': 16, 'rate': 1.0, 'step': 2.0, 'vision': 2.6,
               'desc': 'Skáče do L, přeskočí zdi i věže.'},
    'obrnenec': {'cat': 'u', 'name': 'Obrněnec', 'cost': [110, 0], 'hp': 420, 'dmg': 22, 'rate': 1.2, 'step': 2.4, 'vision': 2.2, 'bld': 2.5,
                 'desc': 'Jde rovně a do stran. Tank: střely věží, trůnu a Krále mu ubírají o 40 % méně. '
                         'Stavbám dává 2,5× poškození.'},
    'strelec': {'cat': 'u', 'name': 'Pašerák', 'cost': [60, 0], 'hp': 100, 'dmg': 12, 'rate': 0.9, 'step': 1.4, 'vision': 2.4,
                'desc': 'Chodí šikmo jako střelec. Každý zásah stavby ukradne soupeři 4 ⚡.'},
    'medik': {'cat': 'u', 'name': 'Medik', 'cost': [55, 0], 'hp': 110, 'dmg': 5, 'rate': 1.0, 'step': 1.6, 'vision': 2.2,
              'desc': 'Léčí tvoje jednotky a Krále v okruhu 1,5 pole (6 životů/s).'},
    'saboter': {'cat': 'u', 'name': 'Sabotér', 'cost': [70, 0], 'hp': 70, 'dmg': 0, 'rate': 1.0, 'step': 1.3, 'vision': 2.0,
                'desc': 'Soupeř ho nevidí, dokud není blízko. U nepřátelské stavby nebo trůnu položí nálož (260 poškození).'},
    'dama': {'cat': 'u', 'name': 'Hlídka', 'cost': [200, 0], 'hp': 650, 'dmg': 28, 'rate': 0.9, 'step': 1.2, 'vision': 2.8, 'doba': 2, 'bld': 1.5,
             'desc': 'Dáma: chodí i útočí všemi směry. Velmi silná, smíš mít jen jednu.'},
    # ---- the King (mode Král)
    'kral': {'cat': 'k', 'name': 'Král', 'hp': 320, 'speed': 2.6, 'dmg': 14, 'rate': 0.4, 'range': 4.0, 'vision': 3.0,
             'respawn': 15.0, 'block': 1.2, 'parry': 0.3, 'block_cd': 1.5, 'repair': 50.0, 'radius': 0.28,
             'dash': 2.5, 'dash_cd': 7.0, 'dash_inv': 0.3, 'cry': 8.0, 'cry_r': 3.0,
             'desc': 'Tvoje postava. Střílí sám, WASD pohyb, mezerník blok (včas = odrazí střelu), F opravuje, '
                     'Shift výpad, Q válečný pokřik.'},
    # ---- zombies
    'chodec': {'cat': 'z', 'name': 'Chodec', 'hp': 60, 'dmg': 6, 'rate': 1.0, 'step': 1.5, 'loot': [3, 4]},
    'bezec': {'cat': 'z', 'name': 'Běžec', 'hp': 35, 'dmg': 4, 'rate': 0.7, 'step': 0.7, 'loot': [2, 3]},
    'obr': {'cat': 'z', 'name': 'Obr', 'hp': 520, 'dmg': 40, 'rate': 1.6, 'step': 2.6, 'bld': 3.0, 'loot': [20, 30], 'vz': 1},
    'alfa': {'cat': 'z', 'name': 'Alfa', 'hp': 1600, 'dmg': 50, 'rate': 1.5, 'step': 2.4, 'bld': 2.0, 'loot': [40, 40], 'vz': 4},
    # ---- abilities (cards)
    'nalet': {'cat': 'a', 'name': 'Nálet', 'cost': [120, 0], 'cd': 50, 'doba': 2, 'target': 'vis',
              'desc': 'Za 1,5 s zasáhne 3×3 pole (150 poškození nepřátelům i zombie). Cíl musíš vidět.'},
    'vypadek': {'cat': 'a', 'name': 'Výpadek proudu', 'cost': [100, 0], 'cd': 60, 'doba': 2, 'target': None,
                'desc': 'Soupeřovy věže 5 s nestřílí.'},
    'karantena': {'cat': 'a', 'name': 'Karanténa', 'cost': [60, 0], 'cd': 35, 'target': 'mist',
                  'desc': 'Uzavře jeden pruh v Mlze na 10 s. Nikdo jím neprojde.'},
    'navnada': {'cat': 'a', 'name': 'Návnada', 'cost': [50, 0], 'cd': 40, 'target': 'vis',
                'desc': 'Všechny zombie 15 s míří na zvolené pole.'},
    'dron': {'cat': 'a', 'name': 'Průzkumný dron', 'cost': [40, 0], 'cd': 25, 'target': 'any',
             'desc': 'Odhalí okolí zvoleného pole (poloměr 2,5) na 10 s.'},
    'mobilizace': {'cat': 'a', 'name': 'Mobilizace', 'cost': [50, 0], 'cd': 45, 'target': None,
                   'desc': 'Další 3 jednotky budou o 50 % rychlejší.'},
}
for _k, _d in DEFS.items():
    if _d['cat'] == 'b' and _k != 'zed':
        _c = _d['cost'][0]
        _d['up'] = [[round(_c * 0.7), 15], [_c, 25]]
CARD_POOL = [k for k, d in DEFS.items() if d['cat'] in 'bua' and k not in BASE_KIT]
ABILITIES = [k for k, d in DEFS.items() if d['cat'] == 'a']
ATTACK_TOWERS = ('kulomet', 'plamen', 'sniper', 'tesla')
KRAL = DEFS['kral']

# Stratég mode: commander abilities instead of a King
CMDS = {
    'oprava': {'name': 'Oprava', 'key': 'Q', 'cd': 20, 'target': 'own', 'desc': 'Opraví tvou stavbu o 40 % životů.'},
    'odstrel': {'name': 'Odstřel', 'key': 'W', 'cd': 12, 'target': 'vis', 'dmg': 90,
                'desc': 'Zasáhne viditelné pole (90 poškození) a 5 s ho osvětluje, i za tmy.'},
    'sber': {'name': 'Sběrný dron', 'key': 'E', 'cd': 25, 'target': 'crate',
             'desc': 'Dron doletí k bedně, osvětlí ji a 3 s ji nakládá. Sestřelí ho nepřítel blíž než 1,5 pole nebo Odstřel.'},
    'stit': {'name': 'Štít trůnu', 'key': 'R', 'cd': 45, 'target': None, 'dur': 6, 'desc': 'Trůn 6 s dostává o 80 % méně poškození.'},
    'utok': {'name': 'Útok!', 'key': 'G', 'cd': 70, 'target': None, 'dur': 6,
             'desc': 'Tvoje jednotky 6 s dostávají od věží o 50 % méně a jsou rychlejší.'},
}

BRANCHES = {'ing': 'Inženýrství', 'arm': 'Armáda', 'bio': 'Biotech'}
RESEARCH = {
    'ing1': {'branch': 'ing', 'tier': 1, 'cost': 2, 'name': 'Zesílené konstrukce', 'desc': 'Stavby mají o 25 % víc životů.'},
    'ing2': {'branch': 'ing', 'tier': 2, 'cost': 3, 'name': 'Automatické opravy', 'desc': 'Stavby se samy opravují 3 životy/s.'},
    'ing3': {'branch': 'ing', 'tier': 3, 'cost': 4, 'name': 'Dalekonosnost', 'desc': 'Věže +0,6 dosahu, stavby +0,5 dohledu.'},
    'arm1': {'branch': 'arm', 'tier': 1, 'cost': 2, 'name': 'Výcvik', 'desc': 'Jednotky dávají o 20 % víc poškození.'},
    'arm2': {'branch': 'arm', 'tier': 2, 'cost': 3, 'name': 'Pancíř', 'desc': 'Jednotky mají o 30 % víc životů.'},
    'arm3': {'branch': 'arm', 'tier': 3, 'cost': 4, 'name': 'Blesková válka', 'desc': 'Jednotky jsou o 25 % rychlejší.'},
    'bio1': {'branch': 'bio', 'tier': 1, 'cost': 2, 'name': 'Levná tlupa', 'desc': 'Tlupa stojí o 40 % méně, obnova 15 s.'},
    'bio2': {'branch': 'bio', 'tier': 2, 'cost': 3, 'name': 'Nákaza', 'desc': 'Nepřátelské jednotky, které zabiješ, vstanou jako zombie a jdou na soupeře.'},
    'bio3': {'branch': 'bio', 'tier': 3, 'cost': 4, 'name': 'Feromony', 'desc': 'Každá vlna pošle na soupeře 2 zombie navíc.'},
}
DOBA_AT = (2, 5)              # researches needed for Doba II and III

# supply crate rarities: name, weight, energy, scrap, samples, free ability charges
RARITY = [
    ('běžná', 45, 80, 20, 0, 0),
    ('neobvyklá', 28, 120, 35, 1, 0),
    ('vzácná', 15, 150, 50, 2, 0),
    ('epická', 9, 200, 60, 3, 1),
    ('legendární', 3, 250, 80, 5, 2),
]


def home_col(side):
    return 0 if side == 0 else W - 1


def own_half(side, x):
    return x < HALF if side == 0 else x >= W - HALF


def local_x(side, x):
    """Column counted from the side's own throne, so both sides compare positions the same way."""
    return x if side == 0 else W - 1 - x


def gen_price(n):
    return 50 if n < 3 else 50 + 40 * (n - 2)


def sniper_price(n):
    return 100 + 40 * max(0, n - 1)


def roman(n):
    return ('I', 'II', 'III')[max(1, min(3, n)) - 1]


def bfs_from(ter, starts):
    inf = 999
    d = [[inf] * W for _ in range(H)]
    q = deque()
    for x, y in starts:
        if 0 <= x < W and 0 <= y < H and ter[y][x] == '.':
            d[y][x] = 0
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in N4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and ter[ny][nx] == '.' and d[ny][nx] > d[y][x] + 1:
                d[ny][nx] = d[y][x] + 1
                q.append((nx, ny))
    return d


def bfs(ter, col):
    return bfs_from(ter, [(col, y) for y in range(H)])


def make_map():
    for _ in range(200):
        ter = [['.'] * W for _ in range(H)]
        picks = random.sample([(x, y) for x in range(1, 5) for y in range(H)], 4)
        picks += random.sample([(x, y) for x in (6, 7) for y in range(H)], 3)
        for x, y in picks:
            ter[y][x] = '#'
            ter[y][W - 1 - x] = '#'
        d0, d1 = bfs(ter, 0), bfs(ter, W - 1)
        if all(ter[y][x] == '#' or (d0[y][x] < 999 and d1[y][x] < 999) for y in range(H) for x in range(W)):
            return ter
    return [['.'] * W for _ in range(H)]


def valid_deck(deck):
    if (isinstance(deck, list) and len(deck) == DECK_SIZE and all(isinstance(c, str) for c in deck)
            and len(set(deck)) == DECK_SIZE and all(c in CARD_POOL for c in deck)):
        return list(deck)
    return None


class Ent:
    def __init__(self, gid, kind, side, x, y):
        d = DEFS[kind]
        self.id = gid
        self.kind = kind
        self.cat = d['cat']
        self.side = side          # 0, 1, or 2 = zombie
        self.cx, self.cy = int(round(x)), int(round(y))
        self.x, self.y = float(x), float(y)
        self.ax, self.ay, self.at, self.adur = self.x, self.y, 1.0, 1.0
        self.lvl = 1
        self.path = ''
        self.maxhp = self.hp = float(d['hp'])
        self.cd = random.uniform(0.1, 0.5)
        self.mcd = random.uniform(0.2, 0.8)
        self.wait = 0.0
        self.burn = 0.0
        self.burn_src = None
        self.mark = 0.0
        self.lit = False
        self.shield = False
        self.stun = 0.0
        self.slow_t = 0.0
        self.slowf = 1.0
        self.vet = False
        self.kills = 0
        self.fast = False
        self.tgt = 0              # zombie: which throne it marches to
        self.spent = list(d.get('cost', [0, 0]))
        self.dead = False
        self.aim = None           # sniper target while aiming
        self.aim_t = 0.0
        self.fx_t = 0.0

    def fwd(self):
        if self.cat == 'z':
            return -1 if self.tgt == 0 else 1
        return 1 if self.side == 0 else -1


class Side:
    def __init__(self, idx, name, deck):
        self.idx = idx
        self.name = name
        self.deck = deck
        self.e, self.s, self.v = START_RES[0], START_RES[1], 0
        self.techs = set()
        self.cd = {}              # card id or 'cmd_<id>' -> seconds left
        self.free = {}            # ability id -> free charges from crates
        self.mobil = 0
        self.outage = 0.0         # own towers silenced by enemy Výpadek proudu
        self.shield = 0.0         # Stratég: throne shield time left
        self.check = 0.0          # seconds in check
        self.kral = None
        self.respawn = 0.0
        self.inp = {'mx': 0, 'my': 0, 'b': False, 'r': False, 'd': False, 'u': False}
        self.block_t = -1.0       # game time the current block started, -1 = not blocking
        self.block_cd = 0.0
        self.dash = False         # Výpad requested, done on the next tick
        self.dash_cd = 0.0
        self.dash_t = 0.0         # invulnerable after a Výpad
        self.ult = 0.0            # Válečný pokřik meter 0-100
        self.ult_t = 0.0          # war cry aura time left
        self.cry_t = 0.0          # Stratég: Útok! time left
        self.conv_t = 0.0         # earliest game time of the next Přetavení
        self.streak, self.streak_t = 0, -99.0
        self.horde_cd = 0.0
        self.job = None
        self.reveals = []         # [x, y, seconds, radius] from Průzkumný dron and Odstřel
        self.stats = {'kills': 0, 'units': 0, 'built': 0, 'crates': 0, 'techs': 0}

    @property
    def doba(self):
        n = len(self.techs)
        return 3 if n >= DOBA_AT[1] else 2 if n >= DOBA_AT[0] else 1


class Game:
    def __init__(self, names, decks, mode):
        self.names = names
        self.mode = mode
        self.sd = [Side(0, names[0], decks[0]), Side(1, names[1], decks[1])]
        self.ents = {}
        self.nid = 1
        self.ter = make_map()
        self.dist = [bfs(self.ter, 0), bfs(self.ter, W - 1)]
        self.bld = [[None] * W for _ in range(H)]
        self.mob = [[None] * W for _ in range(H)]
        self.throne = [float(THRONE_HP), float(THRONE_HP)]
        self.throne_cd = [0.0, 0.0]
        self.t = self.prev_t = 0.0
        self.length = random.uniform(600, 900)
        self.stage = 0            # how far the Mist has advanced (0-3 by day, 4-6 in Poslední noc)
        self.night = False
        self.over = None
        self.fx = []
        self.pfx = [[], []]       # fx only the owner may see (hidden things)
        self.msgs = [[], []]      # (text, kind) per side
        self.evs = [[], []]       # events per side since the last snapshot
        self.dealt = [0.0, 0.0]   # damage to the enemy throne and buildings (Poslední noc tie-break)
        self.first_blood = False
        self.next_wave = 40.0
        self.wave_n = 0
        self.next_crate = 40.0
        self.crate_n = 0
        self.next_alfa = 300.0
        self.relic = {'on': False, 'own': -1, 'by': -1, 'p': 0.0, 'vt': 0.0}
        self.crates = {}
        self.strikes = []         # Nálet: [side, x, y, seconds]
        self.charges = []         # sabotage: [side, ('e', id) or ('t', side), seconds, x, y]
        self.barriers = []        # Karanténa: [row, seconds]
        self.drones = []          # Sběrný dron
        self.lure = None          # Návnada: [x, y, seconds, dist grid]
        self.masked = set()
        self.reflectors = [[], []]
        self.vis = [self.base_vis(0), self.base_vis(1)]
        if mode == 'kral':
            for s in (0, 1):
                self.spawn_kral(s)

    # ------------------------------------------------ helpers
    def say(self, text, side=None, kind='i'):
        """kind: 'e' refusal, 'w' warning, 'i' info."""
        for s in ((0, 1) if side is None else (side,)):
            self.msgs[s].append((text, kind))

    def event(self, side, *ev):
        for s in ((0, 1) if side is None else (side,)):
            self.evs[s].append(list(ev))

    def secret(self, e):
        """Mines, saboteurs and buildings masked by a Rušička: the enemy must not learn about them from fx."""
        if e.kind in ('mina', 'saboter') or e.id in self.masked:
            return True
        return e.cat == 'b' and any(j.kind == 'rusicka' and j.path == 'A' and j.side == e.side
                                    and (e.x - j.x) ** 2 + (e.y - j.y) ** 2 <= 2.56 for j in self.ents.values())

    def fx_of(self, e, f, public=False):
        if not public and e.side in (0, 1) and self.secret(e):
            self.pfx[e.side].append(f)
        else:
            self.fx.append(f)

    def crossed(self, at):
        return self.prev_t < at <= self.t

    def mist(self):
        return max(0, MIST[0] - self.stage), min(W - 1, MIST[1] + self.stage)

    def eclipse(self):
        """[phase, secs]: 0 none left, 1 next eclipse starts in secs, 2 eclipse active for secs more."""
        if not self.night:
            for a in ECLIPSES:
                if self.t < a:
                    return [1, int(math.ceil(a - self.t))]
                if self.t < a + ECL_LEN:
                    return [2, int(math.ceil(a + ECL_LEN - self.t))]
        return [0, 0]

    def dark(self):
        return self.night or self.eclipse()[0] == 2

    def in_mist(self, x):
        lo, hi = self.mist()
        return lo <= x <= hi

    def buildable(self, side, x):
        return own_half(side, x) and not self.in_mist(x)

    def count(self, side, kind):
        return sum(1 for e in self.ents.values() if e.kind == kind and e.side == side)

    def income(self, side):
        inc = BASE_INCOME + (2.0 if self.sd[side].doba >= 3 else 0.0) + (2.0 if self.relic['own'] == side else 0.0)
        for e in self.ents.values():
            if e.kind == 'gen' and e.side == side:
                inc += (2, 3, 3)[e.lvl - 1] + (3 if e.path == 'A' else 0)
        return inc

    def techs(self, side):
        return self.sd[side].techs if side in (0, 1) else ()

    def spawn(self, kind, side, x, y):
        e = Ent(self.nid, kind, side, x, y)
        self.nid += 1
        self.ents[e.id] = e
        if e.cat == 'b':
            self.bld[y][x] = e
        elif e.cat in 'uz':
            self.mob[y][x] = e
        if e.cat in 'bu':
            self.refresh_hp(e, full=True)
        return e

    def spawn_kral(self, s):
        k = Ent(self.nid, 'kral', s, home_col(s), H // 2)
        self.nid += 1
        self.ents[k.id] = k
        self.sd[s].kral = k
        return k

    def remove(self, e):
        e.dead = True
        self.ents.pop(e.id, None)
        if e.cat == 'b':
            if self.bld[e.cy][e.cx] is e:
                self.bld[e.cy][e.cx] = None
        elif e.cat in 'uz':
            if self.mob[e.cy][e.cx] is e:
                self.mob[e.cy][e.cx] = None

    def max_hp(self, e):
        d = DEFS[e.kind]
        techs = self.techs(e.side)
        if e.cat == 'b':
            hp = d['hps'][e.lvl - 1] if e.kind == 'zed' else d['hp'] * LVL_MULT[e.lvl - 1]
            if 'ing1' in techs:
                hp *= 1.25
        elif e.cat == 'u':
            hp = d['hp'] * (1.5 if e.vet else 1.0)
            if 'arm2' in techs:
                hp *= 1.3
        else:
            hp = d['hp']
        return float(hp)

    def refresh_hp(self, e, full=False):
        new = self.max_hp(e)
        e.hp = new if full else max(1.0, e.hp + new - e.maxhp)
        e.maxhp = new

    def dmg_of(self, e):
        v = DEFS[e.kind].get('dmg', 0)
        if e.cat == 'b':
            v *= LVL_MULT[e.lvl - 1]
        elif e.cat == 'u':
            if e.vet:
                v *= 1.5
            if 'arm1' in self.techs(e.side):
                v *= 1.2
        return v

    def step_of(self, e):
        st = DEFS[e.kind]['step']
        if e.cat == 'u':
            if e.fast:
                st *= 0.67
            if 'arm3' in self.techs(e.side):
                st *= 0.8
            if self.cry(e) < 1.0:
                st *= 0.7
        return st * e.slowf

    def cry(self, e):
        """Tower damage multiplier for unit e: King's war cry aura 0.4, Stratég's Útok! 0.5, otherwise 1."""
        if e.cat != 'u':
            return 1.0
        sd = self.sd[e.side]
        k = sd.kral
        if sd.ult_t > 0 and k and (k.x - e.x) ** 2 + (k.y - e.y) ** 2 <= KRAL['cry_r'] ** 2:
            return 0.4
        return 0.5 if sd.cry_t > 0 else 1.0

    def rng(self, e):
        r = DEFS[e.kind].get('range', 0)
        if e.kind == 'plamen' and e.path == 'B':
            r = 2.6
        else:
            r += (e.lvl - 1) * 0.2
        if 'ing3' in self.techs(e.side):
            r += 0.6
        return r

    def vision(self, e):
        d = DEFS[e.kind]
        v = d.get('vision', 1.5)
        if e.kind == 'hlaska':
            v = 7.0 if e.path == 'A' else (4.5 + (e.lvl - 1) * 0.75 if e.lvl < 3 else 6.0)
        elif e.cat == 'b' and e.kind not in ('zed', 'mina'):
            v += (e.lvl - 1) * 0.25
        if e.cat == 'b' and 'ing3' in self.techs(e.side):
            v += 0.5
        return v

    # ------------------------------------------------ fog of war
    def base_vis(self, side):
        return [[own_half(side, x) for x in range(W)] for _ in range(H)]

    def compute_vis(self, side, ents):
        """In darkness (Zatmění, Poslední noc) only the throne lights its 2 back columns, buildings see 1.5
        (Reflektor 3), units half; the King is the lamp and keeps his full vision."""
        dark = self.dark()
        if dark:
            hc = home_col(side)
            vis = [[abs(x - hc) <= 1 for x in range(W)] for _ in range(H)]
        else:
            vis = self.base_vis(side)
        srcs = []
        for e in ents:
            if e.side != side or e.dead:
                continue
            r = self.vision(e)
            if dark and e.cat == 'b':
                r = 3.0 if e.kind == 'hlaska' and e.path == 'B' else min(r, 1.5)
            elif dark and e.cat == 'u':
                r *= 0.5
            srcs.append((e.x, e.y, r))
        srcs += [(r[0], r[1], r[3]) for r in self.sd[side].reveals]
        srcs += [(d['x'], d['y'], 1.0) for d in self.drones if d['s'] == side and d['h']]   # Odstřel can break a contested crate
        for sx, sy, r in srcs:
            ri = int(math.ceil(r))
            cx, cy = int(round(sx)), int(round(sy))
            r2 = r * r + 0.01
            for y in range(max(0, cy - ri), min(H, cy + ri + 1)):
                dy2 = (y - sy) ** 2
                row = vis[y]
                for x in range(max(0, cx - ri), min(W, cx + ri + 1)):
                    if (x - sx) ** 2 + dy2 <= r2:
                        row[x] = True
        return vis

    def hidden_kind(self, e):
        return e.kind in ('mina', 'saboter') or e.id in self.masked

    def detects(self, side, e):
        """Hidden things are found by a Reflektor (Hláska B), or by walking right next to them."""
        for h in self.reflectors[side]:
            if (h.x - e.x) ** 2 + (h.y - e.y) ** 2 <= self.vision(h) ** 2:
                return True
        if e.kind == 'mina':
            return False
        r2 = 2.25 if e.kind == 'saboter' else 1.44
        for o in self.ents.values():
            if o.side == side and not o.dead and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= r2:
                return True
        return False

    def can_see(self, side, e):
        if e.side == side:
            return True
        if not (0 <= e.cy < H and 0 <= e.cx < W) or not self.vis[side][e.cy][e.cx]:
            return False
        return not self.hidden_kind(e) or self.detects(side, e)

    # ------------------------------------------------ actions
    def act(self, s, m):
        if self.over:
            return
        t = m.get('t')
        if t == 'in':
            return self.king_input(s, m)
        if t == 'res':
            return self.research(s, m.get('id'))
        if t == 'horde':
            return self.horde(s)
        if t == 'conv':
            return self.convert(s)
        if t in ('upg', 'sell'):
            eid = m.get('id')
            e = self.ents.get(eid) if isinstance(eid, int) else None
            if not e or e.side != s or e.cat != 'b':
                return
            return self.upgrade(s, e, m.get('path')) if t == 'upg' else self.sell(s, e)
        try:
            x, y = int(m.get('x', -1)), int(m.get('y', -1))
        except (TypeError, ValueError, OverflowError):
            return
        kind = m.get('kind') if t in ('build', 'unit') else m.get('id')
        if not isinstance(kind, str) and t != 'scrap':
            return
        if t == 'build':
            self.build(s, kind, x, y)
        elif t == 'unit':
            self.deploy(s, kind, x, y)
        elif t == 'card':
            self.cast(s, kind, x, y)
        elif t == 'cmd':
            self.command(s, kind, x, y)
        elif t == 'scrap':
            self.scrap(s, x, y)

    def kral_near(self, x, y):
        return any(sd.kral and abs(sd.kral.x - x) < 0.8 and abs(sd.kral.y - y) < 0.8 for sd in self.sd)

    def build(self, s, kind, x, y):
        sd = self.sd[s]
        d = DEFS.get(kind)
        if not d or d['cat'] != 'b' or not (0 <= x < W and 0 <= y < H):
            return
        if kind not in BASE_KIT and kind not in sd.deck:
            return
        if sd.doba < d.get('doba', 1):
            return self.say('%s vyžaduje Dobu %s.' % (d['name'], roman(d['doba'])), s, 'e')
        if self.mode == 'kral' and sd.kral is None:
            return self.say(KING_DEAD, s, 'e')
        if not self.buildable(s, x):
            return self.say('Stavět můžeš jen na své polovině mimo Mlhu.', s, 'e')
        if self.ter[y][x] != '.' or self.bld[y][x] or self.mob[y][x] or self.kral_near(x, y):
            return self.say('Tady stavět nejde.', s, 'e')
        cost = list(d['cost'])
        if kind == 'gen':
            cost[0] = gen_price(self.count(s, 'gen'))
        elif kind == 'sniper':
            cost[0] = sniper_price(self.count(s, 'sniper'))
        if sd.e < cost[0] or sd.s < cost[1]:
            return self.say('Nedostatek surovin.', s, 'e')
        sd.e -= cost[0]
        sd.s -= cost[1]
        e = self.spawn(kind, s, x, y)
        e.spent = cost
        sd.stats['built'] += 1
        self.fx_of(e, ['n', x, y, 0, 0, s, kind])

    def deploy(self, s, kind, x, y):
        sd = self.sd[s]
        d = DEFS.get(kind)
        if not d or d['cat'] != 'u' or kind not in sd.deck or not (0 <= x < W and 0 <= y < H):
            return
        if sd.doba < d.get('doba', 1):
            return self.say('%s vyžaduje Dobu %s.' % (d['name'], roman(d['doba'])), s, 'e')
        if not self.buildable(s, x):
            return self.say('Jednotky nasazuješ jen na své polovině mimo Mlhu.', s, 'e')
        b = self.bld[y][x]
        if self.ter[y][x] != '.' or self.mob[y][x] or (b and b.side != s):
            return self.say('Sem jednotku nepostavíš.', s, 'e')
        if kind == 'dama' and self.count(s, 'dama'):
            return self.say('Hlídku smíš mít jen jednu.', s, 'e')
        if sd.e < d['cost'][0]:
            return self.say('Nedostatek energie.', s, 'e')
        sd.e -= d['cost'][0]
        e = self.spawn(kind, s, x, y)
        if sd.mobil > 0:
            e.fast = True
            sd.mobil -= 1
        sd.stats['units'] += 1
        self.fx_of(e, ['n', x, y, 1, 0, s, kind])

    def upgrade(self, s, e, path):
        sd = self.sd[s]
        if e.lvl >= 3:
            return self.say('Stavba už má maximální úroveň.', s, 'e')
        if self.mode == 'kral' and sd.kral is None:
            return self.say(KING_DEAD, s, 'e')
        needs_path = e.lvl == 2 and e.kind != 'zed'
        if needs_path and path not in ('A', 'B'):
            return self.say('Na úroveň 3 vyber cestu A nebo B.', s, 'e')
        ce, cs = DEFS[e.kind]['up'][e.lvl - 1]
        if sd.e < ce or sd.s < cs:
            return self.say('Nedostatek surovin na vylepšení.', s, 'e')
        sd.e -= ce
        sd.s -= cs
        e.spent[0] += ce
        e.spent[1] += cs
        e.lvl += 1
        if needs_path:
            e.path = path
        self.refresh_hp(e)
        self.fx_of(e, ['u', e.cx, e.cy, e.lvl, 0, s, e.path])

    def sell(self, s, e):
        sd = self.sd[s]
        if self.mode == 'kral' and sd.kral is None:
            return self.say(KING_DEAD, s, 'e')
        k = 0.5 * max(0.0, e.hp / e.maxhp)
        sd.e += e.spent[0] * k
        sd.s += e.spent[1] * k
        self.fx_of(e, ['r', e.cx, e.cy, 0, 0, s])
        self.remove(e)

    def convert(self, s):
        sd = self.sd[s]
        if self.t < sd.conv_t:
            return
        if sd.doba < CONV[2]:
            return self.say('Přetavení vyžaduje Dobu %s.' % roman(CONV[2]), s, 'e')
        if sd.e < CONV[0]:
            return self.say('Přetavení stojí %d ⚡.' % CONV[0], s, 'e')
        sd.e -= CONV[0]
        sd.s += CONV[1]
        sd.conv_t = self.t + 0.5

    def scrap(self, s, x, y):
        if not (0 <= x < W and 0 <= y < H) or not own_half(s, x) or self.ter[y][x] != '#':
            return
        if self.sd[s].job:
            return self.say('Čety už rozebírají jiné trosky.', s, 'e')
        self.sd[s].job = [x, y, 0.0]

    def horde(self, s):
        sd = self.sd[s]
        cheap = 'bio1' in sd.techs
        cost = round(HORDE_COST * (0.6 if cheap else 1.0))
        if sd.horde_cd > 0:
            return
        if sd.e < cost:
            return self.say('Tlupa stojí %d energie.' % cost, s, 'e')
        sd.e -= cost
        sd.horde_cd = 15.0 if cheap else HORDE_CD
        foe = 1 - s
        kinds = ['chodec'] * 4 + ['bezec']
        if self.t > 360:
            kinds.append('obr')
        n = self.spawn_zombies(kinds, (9, 8) if foe == 1 else (6, 7), foe)
        self.say('Vypustil jsi tlupu (%d zombie).' % n, s)
        self.say('Soupeř na tebe poslal tlupu zombie!', foe, 'w')
        self.event(foe, 'horde', s)

    def research(self, s, rid):
        sd = self.sd[s]
        r = RESEARCH.get(rid) if isinstance(rid, str) else None
        if not r or rid in sd.techs:
            return
        if r['tier'] > 1 and '%s%d' % (r['branch'], r['tier'] - 1) not in sd.techs:
            return self.say('Nejdřív vyzkoumej předchozí stupeň.', s, 'e')
        if sd.v < r['cost']:
            return self.say('Nemáš dost Vzorků 🧪.', s, 'e')
        sd.v -= r['cost']
        old = sd.doba
        sd.techs.add(rid)
        sd.stats['techs'] += 1
        if rid in ('ing1', 'arm2'):
            cat = 'b' if rid == 'ing1' else 'u'
            for e in self.ents.values():
                if e.side == s and e.cat == cat:
                    self.refresh_hp(e)
        self.say('Vyzkoumáno: %s.' % r['name'], s)
        if sd.doba > old:
            self.say('Nastala Doba %s!%s' % (roman(sd.doba), ' Odemkly se silnější karty.' if sd.doba == 2 else ' +2 ⚡/s.'), s)
            self.say('Soupeř vstoupil do Doby %s.' % roman(sd.doba), 1 - s, 'w')

    def cast(self, s, card, x, y):
        sd = self.sd[s]
        d = DEFS.get(card)
        if not d or d['cat'] != 'a':
            return
        free = sd.free.get(card, 0) > 0
        if not free:
            if card not in sd.deck or sd.cd.get(card, 0) > 0:
                return
            if sd.doba < d.get('doba', 1):
                return self.say('%s vyžaduje Dobu %s.' % (d['name'], roman(d['doba'])), s, 'e')
            if sd.e < d['cost'][0]:
                return self.say('Nedostatek energie.', s, 'e')
        tg = d.get('target')
        if tg is not None:
            if not (0 <= x < W and 0 <= y < H):
                return
            if tg == 'vis' and not self.vis[s][y][x]:
                return self.say('Cíl musíš vidět.', s, 'e')
            if tg == 'mist' and not (MIST[0] <= x <= MIST[1]):
                return self.say('Karanténu jde použít jen v Mlze.', s, 'e')
            if card == 'navnada' and self.ter[y][x] != '.':
                return self.say('Návnadu polož na volné pole.', s, 'e')
        if free:
            sd.free[card] -= 1
            if sd.free[card] <= 0:
                del sd.free[card]
        else:
            sd.e -= d['cost'][0]
            sd.cd[card] = d['cd']
        foe = 1 - s
        if card == 'nalet':
            self.strikes.append([s, x, y, 1.5])
        elif card == 'vypadek':
            self.sd[foe].outage = 5.0
            self.say('Výpadek proudu! Tvoje věže 5 s nestřílí.', foe, 'w')
            self.say('Soupeřovy věže jsou 5 s bez proudu.', s)
        elif card == 'karantena':
            self.barriers = [b for b in self.barriers if b[0] != y] + [[y, 10.0]]
        elif card == 'navnada':
            self.lure = [x, y, 15.0, bfs_from(self.ter, [(x, y)])]
        elif card == 'dron':
            sd.reveals.append([x, y, 10.0, 2.5])
        elif card == 'mobilizace':
            sd.mobil = 3

    def command(self, s, cid, x, y):
        sd = self.sd[s]
        c = CMDS.get(cid)
        if self.mode != 'strateg' or not c or sd.cd.get('cmd_' + cid, 0) > 0:
            return
        inside = 0 <= x < W and 0 <= y < H
        if cid == 'oprava':
            b = self.bld[y][x] if inside else None
            if not b or b.side != s:
                return self.say('Klikni na svou stavbu.', s, 'e')
            b.hp = min(b.maxhp, b.hp + 0.4 * b.maxhp)
            self.fx.append(['h', x, y, 0, 0, s])
        elif cid == 'odstrel':
            if not inside or not self.vis[s][y][x]:
                return self.say('Cíl musíš vidět.', s, 'e')
            for o in list(self.ents.values()):
                if not o.dead and o.side != s and o.cx == x and o.cy == y and o.kind != 'mina':
                    self.damage(o, c['dmg'], s)
            self.drones = [d for d in self.drones if d['s'] == s or (round(d['x']), round(d['y'])) != (x, y)]
            sd.reveals.append([x, y, 5.0, 1.5])
            self.fx.append(['b', x, y, 0.6, 0, s])
        elif cid == 'sber':
            crate = next((c2 for c2 in self.crates.values() if c2['x'] == x and c2['y'] == y), None)
            if not crate:
                return self.say('Klikni na zásobovací bednu.', s, 'e')
            self.drones.append({'s': s, 'x': -0.5 if s == 0 else W - 0.5, 'y': float(H // 2), 'cid': crate['id'], 'h': False})
        elif cid == 'stit':
            sd.shield = c['dur']
        elif cid == 'utok':
            sd.cry_t = c['dur']
            self.event(None, 'utok', s)
        sd.cd['cmd_' + cid] = c['cd']

    def king_input(self, s, m):
        if self.mode != 'kral':
            return
        sd = self.sd[s]

        def axis(v):
            try:
                return max(-1, min(1, int(v)))
            except (TypeError, ValueError, OverflowError):
                return 0
        b, d, u = bool(m.get('b')), bool(m.get('d')), bool(m.get('u'))
        old = sd.inp
        sd.inp = {'mx': axis(m.get('mx')), 'my': axis(m.get('my')), 'b': b, 'r': bool(m.get('r')), 'd': d, 'u': u}
        if b and not old['b'] and sd.kral and sd.block_cd <= 0 and sd.block_t < 0:
            sd.block_t = self.t
        elif not b and old['b'] and sd.block_t >= 0:
            sd.block_t = -1.0
            sd.block_cd = KRAL['block_cd']
        if d and not old['d'] and sd.kral:
            sd.dash = True
        k = sd.kral
        if u and not old['u'] and k and sd.ult >= 100:
            sd.ult = 0.0
            sd.ult_t = KRAL['cry']
            self.fx.append(['U', round(k.x, 2), round(k.y, 2), KRAL['cry_r'], 0, s])
            self.event(None, 'ult', s)

    # ------------------------------------------------ zombies, crates, events
    def spawn_zombies(self, kinds, cols, target):
        n = 0
        for kind in kinds:
            free = [(x, y) for x in cols for y in range(H)
                    if self.ter[y][x] == '.' and not self.mob[y][x] and not self.bld[y][x]]
            if not free:
                break
            x, y = random.choice(free)
            z = self.spawn(kind, 2, x, y)
            z.tgt = target
            n += 1
        return n

    def wave(self):
        self.wave_n += 1
        n = 1 + self.wave_n // 2
        kinds = ['bezec' if self.t > 120 and random.random() < 0.3 else 'chodec' for _ in range(n)]
        if self.t > 300 and self.wave_n % 3 == 0:
            kinds.append('obr')
        for kind in kinds:
            pairs = [(x, y) for x in (6, 7) for y in range(H)
                     if self.ter[y][x] == '.' and not self.mob[y][x] and not self.mob[y][W - 1 - x]]
            if not pairs:
                break
            x, y = random.choice(pairs)
            first = random.randint(0, 1)          # neither side may always get the older (lower id) zombie
            for tgt in (first, 1 - first):
                self.spawn(kind, 2, x if tgt == 0 else W - 1 - x, y).tgt = tgt
        for s in (0, 1):
            if 'bio3' in self.sd[s].techs:
                foe = 1 - s
                self.spawn_zombies(['chodec', 'chodec'], (9, 8) if foe == 1 else (6, 7), foe)
        self.say('Z Mlhy se valí vlna %d!' % self.wave_n)
        self.event(None, 'wave', self.wave_n)

    def drop_crate(self, x=None, y=None, rarity=None, land=10.0, min_rar=0):
        if x is None:
            cells = [(cx, cy) for cx in (7, 8) for cy in range(H)
                     if self.ter[cy][cx] == '.' and not any(c['x'] == cx and c['y'] == cy for c in self.crates.values())]
            if not cells:
                return
            x, y = random.choice(cells)
        if rarity is None:
            roll = random.uniform(0, sum(r[1] for r in RARITY))
            rarity = 0
            for i, r in enumerate(RARITY):
                roll -= r[1]
                if roll <= 0:
                    rarity = i
                    break
            rarity = max(min_rar, rarity)
        cid = self.nid
        self.nid += 1
        self.crates[cid] = {'id': cid, 'x': x, 'y': y, 'r': rarity, 'land': land, 'ttl': 60.0, 'ch': [0.0, 0.0], 'con': False, 'now': False}
        if land > 0:
            self.crate_n += 1
            self.say('Do Mlhy padá zásobovací bedna (%s)!' % RARITY[rarity][0])
            self.event(None, 'crate', cid, rarity)

    def collect(self, s, c):
        self.crates.pop(c['id'], None)
        name, _, e, sc, v, n = RARITY[c['r']]
        sd = self.sd[s]
        sd.e += e
        sd.s += sc
        sd.v += v
        got = []
        for _ in range(n):
            card = random.choice(ABILITIES)
            sd.free[card] = sd.free.get(card, 0) + 1
            got.append(DEFS[card]['name'])
        sd.stats['crates'] += 1
        text = 'Bedna (%s): +%d ⚡ +%d 🔩' % (name, e, sc)
        if v:
            text += ' +%d 🧪' % v
        if got:
            text += ', zdarma: ' + ', '.join(got)
        self.say(text, s)
        self.say('Soupeř sebral zásobovací bednu (%s).' % name, 1 - s)
        self.fx.append(['o', c['x'], c['y'], c['r'], 0, s])

    def timers(self, dt):
        for s in (0, 1):
            sd = self.sd[s]
            sd.e += self.income(s) * dt
            sd.horde_cd = max(0.0, sd.horde_cd - dt)
            sd.outage = max(0.0, sd.outage - dt)
            sd.shield = max(0.0, sd.shield - dt)
            sd.block_cd = max(0.0, sd.block_cd - dt)
            sd.dash_cd = max(0.0, sd.dash_cd - dt)
            sd.dash_t = max(0.0, sd.dash_t - dt)
            sd.ult_t = max(0.0, sd.ult_t - dt)
            sd.cry_t = max(0.0, sd.cry_t - dt)
            if sd.kral and not own_half(s, sd.kral.cx):
                sd.ult = min(100.0, sd.ult + dt)
            for k in list(sd.cd):
                sd.cd[k] -= dt
                if sd.cd[k] <= 0:
                    del sd.cd[k]
            sd.reveals = [[x, y, t - dt, r] for x, y, t, r in sd.reveals if t - dt > 0]
            j = sd.job
            if j:
                j[2] += dt
                if self.ter[j[1]][j[0]] != '#':
                    sd.job = None
                elif j[2] >= SCRAP_TIME:
                    self.ter[j[1]][j[0]] = '.'
                    sd.s += SCRAP_GAIN
                    sd.job = None
                    self.dist = [bfs(self.ter, 0), bfs(self.ter, W - 1)]
                    self.say('Trosky rozebrány: +%d šrotu.' % SCRAP_GAIN, s)
            if self.mode == 'kral' and sd.kral is None:
                sd.respawn -= dt
                if sd.respawn <= 0:
                    self.spawn_kral(s)
                    self.say('Tvůj Král znovu povstal.', s)
                    self.event(None, 'kr', s)
            if sd.block_t >= 0 and self.t - sd.block_t > KRAL['block']:
                sd.block_t = -1.0
                sd.block_cd = KRAL['block_cd']
        if self.t >= self.next_wave:
            self.wave()
            self.next_wave += max(22.0, 38.0 - self.wave_n)
        if self.t >= self.next_crate and not self.night:
            self.drop_crate(min_rar=0 if self.crate_n else 1)
            self.next_crate = self.t + random.uniform(50, 70)
        if self.t >= self.next_alfa and not self.night:
            self.next_alfa += 240.0
            cells = [(x, y) for x in (7, 8) for y in range(H) if self.ter[y][x] == '.' and not self.mob[y][x]]
            if cells:
                x, y = random.choice(cells)
                a = self.spawn('alfa', 2, x, y)
                a.tgt = 0 if self.throne[0] > self.throne[1] else 1 if self.throne[1] > self.throne[0] else random.randint(0, 1)
                self.say('V Mlze se probudila Alfa! Míří na tvůj trůn.', a.tgt, 'w')
                self.say('V Mlze se probudila Alfa! Míří na trůn hráče %s.' % self.names[a.tgt], 1 - a.tgt)
                self.event(None, 'alfa', a.tgt)
        if not self.night:
            for a in ECLIPSES:
                if self.crossed(a - ECL_WARN):
                    self.event(None, 'ecl_warn', ECL_WARN)
                elif self.crossed(a):
                    self.event(None, 'ecl', 1)
                elif self.crossed(a + ECL_LEN):
                    self.event(None, 'ecl', 0)
        if not self.night and self.t >= self.length:
            self.night = True
            self.say('POSLEDNÍ NOC! Padla tma a Mlha každých 20 s pohltí další sloupec. Vydrž déle než soupeř.', None, 'w')
            self.event(None, 'night', 1)
        if self.night:
            tau = self.t - self.length
            want = min(6, 4 + int(tau / 20))
            drain = (5.0 + tau * 0.2) * dt
            self.throne[0] -= drain
            self.throne[1] -= drain
        else:
            frac = self.t / self.length
            want = 3 if frac >= 0.85 else 2 if frac >= 0.7 else 1 if frac >= 0.5 else 0
        if want > self.stage:
            self.stage = want
            if want != 4:
                self.say('Mlha pohltila další sloupec v obou základnách! Stavby v ní chátrají.', None, 'w')
            self.event(None, 'mist', want)
        self.barriers = [[y, t - dt] for y, t in self.barriers if t - dt > 0]
        if self.lure:
            self.lure[2] -= dt
            if self.lure[2] <= 0:
                self.lure = None

    # ------------------------------------------------ simulation
    def step(self, dt):
        if self.over:
            return
        self.prev_t = self.t
        self.t += dt
        self.timers(dt)
        ents = list(self.ents.values())
        self.passives(ents, dt)
        self.vis = [self.compute_vis(0, ents), self.compute_vis(1, ents)]
        for e in ents:
            if e.dead:
                continue
            if e.cat == 'b':
                self.tower(e, dt)
            elif e.cat == 'k':
                self.kral_tick(e, dt)
            else:
                self.mobile(e, dt)
        for s in (0, 1):
            self.throne_gun(s, dt)
        self.mines()
        self.strikes_tick(dt)
        self.charges_tick(dt)
        self.crates_tick(dt)
        self.drones_tick(dt)
        self.relic_tick(dt)
        self.checkmate(dt)
        for s in (0, 1):
            self.throne[s] = max(0.0, self.throne[s])
        if not self.over and (self.throne[0] <= 0 or self.throne[1] <= 0):
            if self.throne[0] <= 0 and self.throne[1] <= 0:
                d = self.dealt
                if abs(d[0] - d[1]) < 1:
                    self.over = {'winner': -1, 'reason': 'Oba trůny padly současně. Remíza.'}
                else:
                    w = 0 if d[0] > d[1] else 1
                    self.over = {'winner': w, 'reason': 'Oba trůny padly naráz, víc škody nadělal hráč %s.' % self.names[w]}
            else:
                w = 0 if self.throne[1] <= 0 else 1
                self.over = {'winner': w, 'reason': 'Trůn hráče %s padl.' % self.names[1 - w]}

    def passives(self, ents, dt):
        self.reflectors = [[e for e in ents if e.kind == 'hlaska' and e.path == 'B' and e.side == s] for s in (0, 1)]
        lights = self.reflectors[0] + self.reflectors[1]
        shields = [e for e in ents if e.kind == 'gen' and e.path == 'B']
        jammers = [e for e in ents if e.kind == 'rusicka']
        self.masked = set()
        for j in jammers:
            if j.path == 'A':
                for e in ents:
                    if e.cat == 'b' and e.side == j.side and (e.x - j.x) ** 2 + (e.y - j.y) ** 2 <= 2.56:
                        self.masked.add(e.id)
        lo, hi = self.mist()
        for e in ents:
            if e.dead:
                continue
            e.mark = max(0.0, e.mark - dt)
            e.slow_t = max(0.0, e.slow_t - dt)
            if e.cat == 'b':
                e.shield = any(g.side == e.side and g is not e and max(abs(g.cx - e.cx), abs(g.cy - e.cy)) <= 1 for g in shields)
                if 'ing2' in self.techs(e.side) and e.hp < e.maxhp:
                    e.hp = min(e.maxhp, e.hp + 3 * dt)
                if lo <= e.cx <= hi:
                    self.damage(e, max(3.0, 0.02 * e.maxhp) * dt, None)
            else:
                e.lit = any(h.side != e.side and (h.x - e.x) ** 2 + (h.y - e.y) ** 2 <= self.vision(h) ** 2 for h in lights)
                slow = 0.5 if e.slow_t > 0 else 0.0
                for j in jammers:
                    if j.side == e.side:
                        continue
                    r, f = (2.4, 0.45) if j.path == 'B' else ((2.0, 0.30) if j.lvl >= 2 else (1.6, 0.25))
                    if (j.x - e.x) ** 2 + (j.y - e.y) ** 2 <= r * r:
                        slow = max(slow, f)
                e.slowf = 1.0 / (1.0 - slow)
                if e.cat in 'uk' and lo <= e.cx <= hi:
                    self.damage(e, (2.0 if e.cat == 'k' else 1.5) * dt, None)
            if e.burn > 0 and not e.dead:
                e.burn -= dt
                self.damage(e, 6 * dt, e.burn_src)
            if e.kind == 'medik' and not e.dead:
                for o in ents:
                    if (o.side == e.side and o.cat in 'uk' and o is not e and not o.dead and o.hp < o.maxhp
                            and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= 2.25):
                        o.hp = min(o.maxhp, o.hp + 6 * dt)

    # ------------------------------------------------ combat
    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if isinstance(tgt, int):          # a throne
            if self.sd[tgt].shield > 0:
                amount *= 0.2
            if src_side in (0, 1) and src_side != tgt:
                self.dealt[src_side] += max(0.0, min(amount, self.throne[tgt]))
            self.throne[tgt] -= amount
            return
        if tgt.dead:
            return
        if tgt.cat == 'k':
            sd = self.sd[tgt.side]
            if sd.dash_t > 0:
                return
            if sd.block_t >= 0:
                if ranged and self.t - sd.block_t <= KRAL['parry']:
                    back = src is not None and not src.dead
                    self.fx.append(['p', round(tgt.x, 2), round(tgt.y, 2), round(src.x, 2) if back else -1,
                                    round(src.y, 2) if back else -1, tgt.side])   # -1 = no return shot (0,0 is a real cell)
                    sd.ult = min(100.0, sd.ult + 20)
                    if back:
                        self.damage(src, amount, tgt.side, None, tgt)
                    return
                if amount >= 1:           # a real hit, not a tick of Mist or burn damage
                    self.fx.append(['g', round(tgt.x, 2), round(tgt.y, 2), 0, 0, tgt.side])
                amount *= 0.3
        mult = 1.0
        if ranged and tgt.kind == 'obrnenec':
            mult *= 0.6                   # Pancíř
        if tgt.cat == 'u' and ((src is not None and src.cat == 'b') or (ranged and src is None)):
            mult *= self.cry(tgt)         # towers and the throne gun vs war cry / Útok!
        if tgt.mark > 0:
            mult *= 1.25
        if tgt.lit:
            mult *= 1.15
        if tgt.cat == 'b':
            if tgt.shield:
                mult *= 0.7
            if src_kind:
                mult *= DEFS[src_kind].get('bld', 1.0)
            if src_side in (0, 1) and src_side != tgt.side:
                self.dealt[src_side] += min(tgt.hp, amount * mult)
        tgt.hp -= amount * mult
        if tgt.hp <= 0:
            self.kill(tgt, src_side, src)

    def kill(self, e, src_side, src=None):
        self.remove(e)
        killer = src_side if src_side in (0, 1) else -1
        self.fx_of(e, ['x', round(e.x, 2), round(e.y, 2), 0, 0, e.cat, e.id, e.kind, e.side, killer],
                   public=killer >= 0 and killer != e.side)
        if src is not None and not src.dead and src.side != e.side:
            if src.cat == 'k':
                self.sd[src.side].ult = min(100.0, self.sd[src.side].ult + 6)
            elif src.cat == 'u':
                src.kills += 1
                if src.kills >= 3 and not src.vet:
                    self.make_vet(src)
        if killer >= 0 and e.side == 1 - killer:
            self.enemy_kill(killer)
        if e.cat == 'k':
            sd = self.sd[e.side]
            sd.kral = None
            sd.respawn = KRAL['respawn']
            sd.block_t = -1.0
            sd.dash = False
            sd.ult_t = 0.0
            self.say('Tvůj Král padl! Vrátí se za 15 s, do té doby nemůžeš stavět.', e.side, 'w')
            self.event(None, 'kk', killer)
            if killer == 1 - e.side:
                self.sd[killer].s += 20
                self.say('Zabil jsi soupeřova Krále! +20 🔩', killer)
            return
        if killer >= 0:
            sd = self.sd[killer]
            if e.cat == 'z':
                le, ls = DEFS[e.kind]['loot']
                sd.e += le
                sd.s += ls
                v = DEFS[e.kind].get('vz', 0) or (1 if random.random() < 0.05 else 0)
                sd.v += v
                sd.stats['kills'] += 1
            elif e.cat == 'u' and e.side != killer:
                sd.s += 15 if e.vet else 6
                sd.stats['kills'] += 1
                if 'bio2' in sd.techs and self.ter[e.cy][e.cx] == '.' and not self.mob[e.cy][e.cx]:
                    self.spawn('chodec', 2, e.cx, e.cy).tgt = e.side
        if e.kind == 'alfa':
            self.drop_crate(e.cx, e.cy, len(RARITY) - 1, land=0.0)
            self.say('Alfa padla! Na jejím místě leží legendární bedna.')
            self.event(None, 'alfa_dead', killer)

    def enemy_kill(self, s):
        """First blood and kill streaks: enemy units, buildings and Kings, each at most STREAK s after the last."""
        if not self.first_blood:
            self.first_blood = True
            self.event(None, 'fb', s)
        sd = self.sd[s]
        sd.streak = sd.streak + 1 if self.t - sd.streak_t <= STREAK else 1
        sd.streak_t = self.t
        if sd.streak in (2, 3) or sd.streak >= 5:
            self.event(s, 'streak', sd.streak)

    def make_vet(self, e):
        e.vet = True
        self.refresh_hp(e)
        self.fx_of(e, ['v', e.cx, e.cy, 0, 0, e.side])

    def foes_in(self, e, r2):
        return [o for o in self.ents.values()
                if not o.dead and o.cat in 'uzk' and o.side != e.side
                and (o.x - e.cx) ** 2 + (o.y - e.cy) ** 2 <= r2 and self.can_see(e.side, o)]

    def near_key(self, side, x, y):
        """Sort key for picking targets: nearest to (x, y), then nearest to own throne, then row.
        Never the entity id, so neither side gets the older targets first."""
        return lambda o: ((o.x - x) ** 2 + (o.y - y) ** 2, local_x(side, o.x), o.y)

    def tower(self, e, dt):
        k = e.kind
        if k not in ATTACK_TOWERS:
            return
        if self.sd[e.side].outage > 0:
            e.aim = None
            return
        r = self.rng(e)
        r2 = r * r
        dmg = self.dmg_of(e)
        rate = DEFS[k]['rate']
        if k == 'sniper' and e.aim is not None:
            o = e.aim
            if o.dead or (o.x - e.cx) ** 2 + (o.y - e.cy) ** 2 > r2 or not self.can_see(e.side, o):
                e.aim = None
                e.cd = 0.3
                return
            e.aim_t -= dt
            if e.aim_t > 0:
                return
            hits = [o]
            if e.path == 'A':
                near = self.near_key(e.side, e.cx, e.cy)
                hits += sorted((f for f in self.foes_in(e, r2) if f is not o), key=lambda f: (-f.hp,) + near(f))[:2]
            for h in hits:
                self.fx.append(['s', e.cx, e.cy, round(h.x, 2), round(h.y, 2), e.side])
                if e.path == 'B':
                    h.mark = 5.0
                self.damage(h, dmg, e.side, None, e, ranged=True)
            e.aim = None
            e.cd = rate
            return
        e.cd -= dt
        if e.cd > 0:
            return
        foes = self.foes_in(e, r2)
        if not foes:
            e.cd = 0.1
            return
        near = self.near_key(e.side, e.cx, e.cy)
        if k == 'kulomet':
            foes.sort(key=lambda o: (local_x(e.side, o.x),) + near(o))
            hits = foes[:2] if e.path == 'B' else foes[:1]
            if e.path == 'B':
                dmg *= 1.5
            if e.path == 'A':
                rate /= 2
            for o in hits:
                self.fx.append(['k', e.cx, e.cy, round(o.x, 2), round(o.y, 2), e.side])
                self.damage(o, dmg, e.side, None, e, ranged=True)
        elif k == 'plamen':
            self.fx.append(['f', e.cx, e.cy, round(r, 2), 0, e.side])
            for o in foes:
                self.damage(o, dmg, e.side, None, e)
                if e.path == 'A' and not o.dead:
                    o.burn = 4.0
                    o.burn_src = e.side
        elif k == 'sniper':
            o = min(foes, key=lambda f: (-f.hp,) + near(f))
            e.aim = o
            e.aim_t = DEFS[k]['aim']
            self.fx.append(['a', e.cx, e.cy, round(o.x, 2), round(o.y, 2), e.side, o.id])
            return
        elif k == 'tesla':
            n = 5 if e.path == 'A' else 3
            foes.sort(key=near)
            chain = [foes[0]]
            pool = [o for o in self.ents.values() if not o.dead and o.cat in 'uzk' and o.side != e.side and self.can_see(e.side, o)]
            while len(chain) < n:
                last = chain[-1]
                nxt = min((o for o in pool if o not in chain and (o.x - last.x) ** 2 + (o.y - last.y) ** 2 <= 2.56),
                          key=self.near_key(e.side, last.x, last.y), default=None)
                if nxt is None:
                    break
                chain.append(nxt)
            px, py = e.cx, e.cy
            for o in chain:
                self.fx.append(['z', round(px, 2), round(py, 2), round(o.x, 2), round(o.y, 2), e.side])
                px, py = o.x, o.y
                if e.path == 'B':
                    o.stun = max(o.stun, 0.8)
                self.damage(o, dmg, e.side, None, e, ranged=True)
        e.cd = rate

    def throne_gun(self, s, dt):
        self.throne_cd[s] -= dt
        if self.throne_cd[s] > 0:
            return
        best = min((e for e in self.ents.values() if e.cat in 'uzk' and e.side != s and not e.dead
                    and local_x(s, e.x) <= 1.5 and self.can_see(s, e)),
                   key=lambda e: (local_x(s, e.x), abs(e.y - H // 2), e.y), default=None)
        if best:
            self.throne_cd[s] = 0.6
            sx = -0.7 if s == 0 else W - 0.3
            self.fx.append(['t', sx, round(best.y, 2), round(best.x, 2), round(best.y, 2), s])
            self.damage(best, 16, s, None, None, ranged=True)

    # ------------------------------------------------ units and zombies
    def blocked_cell(self, x, y):
        return MIST[0] <= x <= MIST[1] and any(b[0] == y for b in self.barriers)

    def can_enter(self, e, x, y):
        if not (0 <= x < W and 0 <= y < H) or self.ter[y][x] != '.' or self.mob[y][x] is not None or self.blocked_cell(x, y):
            return False
        b = self.bld[y][x]
        if b is None or b.kind == 'mina':     # traps never block: enemies walk onto them
            return True
        return e.cat == 'u' and b.side == e.side

    def kral_in(self, x, y, side):
        for sd in self.sd:
            k = sd.kral
            if k and not k.dead and k.side != side and k.cx == x and k.cy == y:
                return k
        return None

    def target_at(self, e, x, y):
        """Hostile thing in cell (x, y) for attacker e, or None. Off-board columns are thrones."""
        if not (0 <= y < H):
            return None
        if x < 0 or x >= W:
            side = 0 if x < 0 else 1
            return side if (e.cat == 'z' or side != e.side) else None
        m = self.mob[y][x]
        if m is not None and not m.dead and m.side != e.side and not (e.cat == 'z' and m.cat == 'z'):
            return m
        k = self.kral_in(x, y, e.side)
        if k:
            return k
        b = self.bld[y][x]
        if b is not None and not b.dead and b.side != e.side and b.kind != 'mina':
            return b
        return None

    def attack_cells(self, e):
        f = e.fwd()
        k = e.kind
        if k == 'pesak':
            return ((f, 1), (f, -1), (f, 0))
        if k == 'jezdec':
            return ((2 * f, 1), (2 * f, -1), (f, 2), (f, -2), (f, 0), (-f, 2), (-f, -2), (-2 * f, 1), (-2 * f, -1))
        if k == 'obrnenec':
            return ((f, 0), (0, 1), (0, -1), (-f, 0))
        if k == 'strelec':
            return ((f, 1), (f, -1), (-f, 1), (-f, -1), (f, 0))
        if k == 'medik':
            return ((f, 0), (0, 1), (0, -1))
        if k == 'dama':
            return N8
        return ((f, 0),) + N8

    def move_cells(self, e):
        f = e.fwd()
        k = e.kind
        if k in ('pesak', 'saboter'):
            return ((f, 0),), ((0, 1), (0, -1))
        if k == 'jezdec':
            return ((2 * f, 1), (2 * f, -1), (f, 2), (f, -2)), ((0, 1), (0, -1))
        if k == 'strelec':
            return ((f, 1), (f, -1)), ((0, 1), (0, -1))
        if k == 'medik':
            return ((f, 0), (f, 1), (f, -1)), ((0, 1), (0, -1))
        if k == 'dama':
            return ((f, 0), (f, 1), (f, -1), (0, 1), (0, -1)), ((-f, 0), (-f, 1), (-f, -1))
        if e.cat == 'z' and self.lure:
            return N4, N4
        return ((f, 0), (0, 1), (0, -1)), ((0, 1), (0, -1), (-f, 0))

    def mobile(self, e, dt):
        if e.at < 1.0:
            e.at = min(1.0, e.at + dt / e.adur)
            e.x = e.ax + (e.cx - e.ax) * e.at
            e.y = e.ay + (e.cy - e.ay) * e.at
        e.cd -= dt
        e.mcd -= dt
        if e.stun > 0:
            e.stun -= dt
            return
        if e.kind == 'saboter':
            return self.saboteur(e)
        tgt = None
        for dx, dy in self.attack_cells(e):
            tgt = self.target_at(e, e.cx + dx, e.cy + dy)
            if tgt is not None:
                break
        if tgt is not None:
            if e.cd <= 0 and e.at >= 1.0:
                e.cd = DEFS[e.kind]['rate']
                if isinstance(tgt, int):
                    tx, ty = (-0.5 if tgt == 0 else W - 0.5), e.y
                else:
                    tx, ty = tgt.x, tgt.y
                self.fx.append(['m', round(e.x, 2), round(e.y, 2), round(tx, 2), round(ty, 2), e.side])
                self.damage(tgt, self.dmg_of(e), e.side, e.kind, e)
                if e.kind == 'strelec' and not isinstance(tgt, int) and tgt.cat == 'b':
                    foe = self.sd[tgt.side]
                    stolen = min(foe.e, 4.0)
                    foe.e -= stolen
                    self.sd[e.side].e += stolen
            e.wait = 0.0
            return
        if e.mcd > 0 or e.at < 1.0:
            return
        self.advance(e, dt)

    def advance(self, e, dt):
        if e.cat == 'z':
            dist = self.lure[3] if self.lure else self.dist[e.tgt]
        else:
            dist = self.dist[1 - e.side]
        cur = dist[e.cy][e.cx]
        main, side_moves = self.move_cells(e)
        best = None
        for dx, dy in main:
            nx, ny = e.cx + dx, e.cy + dy
            if self.can_enter(e, nx, ny) and dist[ny][nx] < cur:
                score = dist[ny][nx] + random.random() * 0.5
                if best is None or score < best[0]:
                    best = (score, nx, ny)
        if best is None and e.wait > 1.5:
            for dx, dy in side_moves:
                nx, ny = e.cx + dx, e.cy + dy
                if self.can_enter(e, nx, ny) and dist[ny][nx] <= cur + 1:
                    score = dist[ny][nx] + random.random() * 2
                    if best is None or score < best[0]:
                        best = (score, nx, ny)
        if best is None:
            e.wait += dt
            return
        _, nx, ny = best
        self.mob[e.cy][e.cx] = None
        e.ax, e.ay = e.x, e.y
        e.cx, e.cy = nx, ny
        self.mob[ny][nx] = e
        e.at = 0.0
        step = self.step_of(e)
        e.adur = min(0.45, step * 0.6)
        e.mcd = step
        e.wait = 0.0
        if e.kind == 'pesak':
            if nx == home_col(1 - e.side):
                self.promote(e)
            elif not e.vet and (nx > MIST[1] if e.side == 0 else nx < MIST[0]):
                self.make_vet(e)

    def promote(self, e):
        """Proměna pěšce: on the enemy throne column a Pěšák becomes a Dáma, keeping its wounds.
        Only one Dáma per side, so a stream of pawns cannot turn into a wall of tanks on the throne."""
        if self.count(e.side, 'dama'):
            return
        frac = e.hp / e.maxhp
        self.remove(e)
        n = self.spawn('dama', e.side, e.cx, e.cy)
        n.hp = max(1.0, n.maxhp * frac)
        n.kills, n.fast = e.kills, e.fast
        n.x, n.y, n.ax, n.ay, n.at, n.adur = e.x, e.y, e.ax, e.ay, e.at, e.adur     # finish the pawn's step
        self.fx.append(['P', e.cx, e.cy, 0, 0, e.side])
        self.event(None, 'promo', e.side)

    def saboteur(self, e):
        if e.at >= 1.0:
            f = e.fwd()
            if e.cx == home_col(1 - e.side):
                self.charges.append([e.side, ('t', 1 - e.side), 2.0, e.cx + f * 0.5, e.cy])
                self.fx.append(['c', e.cx, e.cy, 0, 0, e.side])
                return self.remove(e)
            for dx, dy in ((f, 0), (0, 1), (0, -1), (-f, 0)):
                x, y = e.cx + dx, e.cy + dy
                if 0 <= x < W and 0 <= y < H:
                    b = self.bld[y][x]
                    if b and not b.dead and b.side in (0, 1) and b.side != e.side and b.kind != 'mina':
                        self.charges.append([e.side, ('e', b.id), 2.0, x, y])
                        self.fx.append(['c', x, y, 0, 0, e.side])
                        return self.remove(e)
        if e.mcd > 0 or e.at < 1.0:
            return
        self.advance(e, TICK)

    def mines(self):
        for m in [e for e in self.ents.values() if e.kind == 'mina']:
            o = self.mob[m.cy][m.cx]
            hit = o is not None and o.side != m.side
            if not hit:
                for sd in self.sd:
                    k = sd.kral
                    if k and k.side != m.side and (k.x - m.cx) ** 2 + (k.y - m.cy) ** 2 <= 0.25:
                        hit = True
            if hit:
                self.remove(m)
                dmg = self.dmg_of(m)
                for v in list(self.ents.values()):
                    if v.cat in 'uzk' and v.side != m.side and not v.dead and (v.x - m.cx) ** 2 + (v.y - m.cy) ** 2 <= 1.44:
                        if m.path == 'A':
                            v.slow_t = 5.0
                        elif m.path == 'B':
                            v.stun = max(v.stun, 2.5)
                        self.damage(v, dmg, m.side)
                self.fx.append(['b', m.cx, m.cy, 1.2, 0, m.side])

    def strikes_tick(self, dt):
        keep = []
        for st in self.strikes:
            st[3] -= dt
            if st[3] > 0:
                keep.append(st)
                continue
            s, x, y = st[0], st[1], st[2]
            for o in list(self.ents.values()):
                if not o.dead and o.side != s and abs(o.x - x) <= 1.5 and abs(o.y - y) <= 1.5:
                    self.damage(o, 150, s)
            self.fx.append(['b', x, y, 1.6, 0, s])
        self.strikes = keep

    def charges_tick(self, dt):
        keep = []
        for c in self.charges:
            c[2] -= dt
            if c[2] > 0:
                keep.append(c)
                continue
            kind, ref = c[1]
            if kind == 't':
                self.damage(ref, 260, c[0])
            else:
                b = self.ents.get(ref)
                if b is None or b.dead:
                    continue
                self.damage(b, 260, c[0])
            self.fx.append(['b', c[3], c[4], 1.0, 0, c[0]])
        self.charges = keep

    def crates_tick(self, dt):
        for c in list(self.crates.values()):
            if c['land'] > 0:
                c['land'] -= dt
                continue
            c['ttl'] -= dt
            if c['ttl'] <= 0:
                del self.crates[c['id']]
                continue
            here = self.at_crate(c)
            c['now'] = len(here) == 2
            if c['now']:                  # contested: both channels freeze
                if not c['con']:
                    c['con'] = True
                    self.event(None, 'contest', c['id'])
                continue
            ch = c['ch']
            for s in (0, 1):
                ch[s] = ch[s] + dt if s in here else max(0.0, ch[s] - dt)
                if ch[s] >= CRATE_CH:
                    self.collect(s, c)
                    break

    def at_crate(self, c):
        """Sides channelling crate c: a unit on its cell, the King within 0.7 or a drone hovering over it."""
        here = set()
        m = self.mob[c['y']][c['x']]
        if m is not None and m.cat == 'u':
            here.add(m.side)
        for sd in self.sd:
            k = sd.kral
            if k and (k.x - c['x']) ** 2 + (k.y - c['y']) ** 2 <= 0.49:
                here.add(k.side)
        for d in self.drones:
            if d['h'] and d['cid'] == c['id']:
                here.add(d['s'])
        return here

    def drones_tick(self, dt):
        keep = []
        for d in self.drones:
            c = self.crates.get(d['cid'])
            if c is None:
                continue
            if any(o.side == 1 - d['s'] and o.cat in 'uk' and (o.x - d['x']) ** 2 + (o.y - d['y']) ** 2 <= 2.25
                   for o in self.ents.values()):
                self.fx.append(['b', round(d['x'], 2), round(d['y'], 2), 0.4, 0, d['s']])
                continue
            dx, dy = c['x'] - d['x'], c['y'] - d['y']
            dist = math.hypot(dx, dy)
            step = 4.0 * dt
            if dist <= step:
                d['x'], d['y'], d['h'] = float(c['x']), float(c['y']), True
            else:
                d['x'] += dx / dist * step
                d['y'] += dy / dist * step
            keep.append(d)
        self.drones = keep

    def relic_tick(self, dt):
        """Relikvie: units or the King of exactly one side (no zombies) hold the zone RELIC_TIME s to take it."""
        rl = self.relic
        if self.t < RELIC_FROM:
            return
        if not rl['on']:
            rl['on'] = True
            self.event(None, 'relic_on', 1)
            self.say('V Mlze se probudila Relikvie! Obsaď ji ' + ('jednotkou nebo Králem.' if self.mode == 'kral' else 'jednotkou – pošli 2–3 jednotky do Mlhy.'))
        x0, x1, y0, y1 = RELIC
        sides, zombies = set(), False
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                m = self.mob[y][x]
                if m is not None:
                    zombies |= m.cat == 'z'
                    if m.cat == 'u':
                        sides.add(m.side)
        for sd in self.sd:
            k = sd.kral
            if k and x0 <= k.cx <= x1 and y0 <= k.cy <= y1:
                sides.add(k.side)
        s = next(iter(sides)) if len(sides) == 1 else -1
        if s >= 0 and s != rl['own'] and not zombies:
            if rl['by'] != s:
                rl['by'], rl['p'] = s, 0.0
            rl['p'] += dt
            if rl['p'] >= RELIC_TIME:
                rl.update(own=s, by=-1, p=0.0, vt=0.0)
                self.fx.append(['R', 7.5, 4, 0, 0, s])
                self.event(None, 'relic', s)
                self.say('Relikvie je tvoje: +2 ⚡/s a 🧪 každých 40 s.', s)
                self.say('Soupeř obsadil Relikvii!', 1 - s, 'w')
        elif not zombies and len(sides) < 2:
            rl['p'] = max(0.0, rl['p'] - dt)
            if rl['p'] <= 0:
                rl['by'] = -1
        if rl['own'] >= 0:
            rl['vt'] += dt
            if rl['vt'] >= RELIC_SAMPLE:
                rl['vt'] -= RELIC_SAMPLE
                self.sd[rl['own']].v += 1
                self.say('Relikvie: +1 🧪', rl['own'])

    # ------------------------------------------------ the King
    def kral_blocked(self, k, x, y):
        r = KRAL['radius']
        if x < -0.5 + r or x > W - 0.5 - r or y < -0.5 + r or y > H - 0.5 - r:
            return True
        for cy in range(int(math.floor(y - r + 0.5)), int(math.floor(y + r + 0.5)) + 1):
            for cx in range(int(math.floor(x - r + 0.5)), int(math.floor(x + r + 0.5)) + 1):
                if 0 <= cx < W and 0 <= cy < H:
                    if self.ter[cy][cx] == '#' or self.blocked_cell(cx, cy):
                        return True
                    b = self.bld[cy][cx]
                    if b is not None and b.side != k.side and b.kind != 'mina':
                        return True
        return False

    def kral_slide(self, k, v, step, ahead, here, prefer):
        """Blocked head-on: drift towards the centre of a neighbouring free lane so the King slips around corners.
        Ties go towards `prefer` (own throne column for sideways slides) so both sides behave the same."""
        r = int(round(v))
        lanes = {math.floor(v), math.ceil(v), r - 1, r + 1}
        for c in sorted((c for c in lanes if abs(c - v) <= 1.0), key=lambda c: (abs(c - v), abs(c - prefer))):
            if not self.kral_blocked(k, *ahead(c)):
                nv = v + max(-step, min(step, c - v))
                return nv if not self.kral_blocked(k, *here(nv)) else v
        return v

    def dash(self, k, sd):
        """Výpad: up to KRAL['dash'] cells in the WASD direction (forward if none), stopping where the King would be blocked.
        Applied within one tick; clients draw it as a 0.18 s streak from the 'D' fx."""
        mx, my = sd.inp['mx'], sd.inp['my']
        if not (mx or my):
            mx = k.fwd()
        n = math.hypot(mx, my)
        x0, y0 = k.x, k.y
        for i in range(1, 26):
            nx, ny = x0 + mx / n * KRAL['dash'] * i / 25, y0 + my / n * KRAL['dash'] * i / 25
            if self.kral_blocked(k, nx, ny):
                break
            k.x, k.y = nx, ny
        if (k.x - x0) ** 2 + (k.y - y0) ** 2 < 0.04:
            k.x, k.y = x0, y0
            return
        k.cx, k.cy = int(round(k.x)), int(round(k.y))
        sd.dash_cd = KRAL['dash_cd']
        sd.dash_t = KRAL['dash_inv']
        self.fx.append(['D', round(x0, 2), round(y0, 2), round(k.x, 2), round(k.y, 2), k.side])

    def kral_tick(self, k, dt):
        sd = self.sd[k.side]
        k.fx_t -= dt
        if k.stun > 0:
            k.stun -= dt
            sd.dash = False
            return
        if sd.dash:
            sd.dash = False
            if sd.dash_cd <= 0:
                self.dash(k, sd)
        blocking = sd.block_t >= 0
        mx, my = sd.inp['mx'], sd.inp['my']
        if mx or my:
            sp = KRAL['speed'] * (0.4 if blocking else 1.0) / k.slowf
            if mx and my:
                sp *= 0.7071
            step = sp * dt
            stuck = self.kral_blocked(k, k.x, k.y)
            nx = k.x + mx * step
            if stuck or not self.kral_blocked(k, nx, k.y):
                k.x = nx
            elif not my:
                k.y = self.kral_slide(k, k.y, step, lambda c: (nx, c), lambda c: (k.x, c), 0)
            ny = k.y + my * step
            if stuck or not self.kral_blocked(k, k.x, ny):
                k.y = ny
            elif not mx:
                k.x = self.kral_slide(k, k.x, step, lambda c: (c, ny), lambda c: (c, k.y), home_col(k.side))
            r = KRAL['radius']
            k.x = min(W - 0.5 - r, max(-0.5 + r, k.x))
            k.y = min(H - 0.5 - r, max(-0.5 + r, k.y))
            k.cx, k.cy = int(round(k.x)), int(round(k.y))
        if sd.inp['r'] and sd.s >= 0.1:
            best, bd = None, 2.25
            for b in self.ents.values():
                if b.cat == 'b' and b.side == k.side and b.hp < b.maxhp:
                    d2 = (b.x - k.x) ** 2 + (b.y - k.y) ** 2
                    if d2 <= bd:
                        best, bd = b, d2
            if best:
                heal = min(KRAL['repair'] * dt, best.maxhp - best.hp, sd.s * 10)
                best.hp += heal
                sd.s -= heal / 10
                if k.fx_t <= 0:
                    k.fx_t = 0.5
                    self.fx.append(['h', best.cx, best.cy, 0, 0, k.side])
        k.cd -= dt
        if k.cd <= 0 and not blocking:
            r2 = KRAL['range'] ** 2
            best = min((o for o in self.ents.values() if o.side != k.side and not o.dead and o.kind != 'mina'
                        and (o.x - k.x) ** 2 + (o.y - k.y) ** 2 <= r2 and self.can_see(k.side, o)),
                       key=self.near_key(k.side, k.x, k.y), default=None)
            if best:
                k.cd = KRAL['rate'] * (0.5 if sd.ult_t > 0 else 1.0)
                self.fx.append(['q', round(k.x, 2), round(k.y, 2), round(best.x, 2), round(best.y, 2), k.side])
                self.damage(best, KRAL['dmg'], k.side, None, k, ranged=True)
            else:
                k.cd = 0.1

    # ------------------------------------------------ check and checkmate
    def checkmate(self, dt):
        for s in (0, 1):
            foe = 1 - s
            sd = self.sd[s]
            hc = home_col(s)
            rows = {e.cy for e in self.ents.values() if e.cat == 'u' and e.side == foe and e.cx == hc}
            if self.mode == 'kral':
                helpless = sd.kral is None
            else:
                helpless = sd.cd.get('cmd_odstrel', 0) > 0 and sd.cd.get('cmd_stit', 0) > 0 and sd.shield <= 0
            if len(rows) >= 3 and helpless:
                if sd.check == 0:
                    self.say('ŠACH! Ubraň aspoň jednu řadu u trůnu, jinak za 10 s prohraješ.', s, 'w')
                    self.say('Dáváš ŠACH! Udrž útok u trůnu 10 s.', foe)
                sd.check += dt
                if sd.check >= CHECK_TIME and not self.over:
                    self.over = {'winner': foe, 'reason': 'Šach-mat! Trůn hráče %s byl obklíčen.' % self.names[s]}
            elif sd.check > 0:
                sd.check = 0.0
                self.say('Šach odvrácen.', s)
                self.say('Soupeř se ze šachu vymanil.', foe)

    # ------------------------------------------------ views
    def snapshot(self, side, fx):
        vis = self.vis[side]
        sd = self.sd[side]
        out = []
        for e in self.ents.values():
            if e.side == side or self.can_see(side, e):
                flags = ((1 if e.vet else 0) | (2 if e.burn > 0 else 0) | (4 if e.mark > 0 else 0) | (8 if e.lit else 0)
                         | (16 if e.shield else 0) | (32 if e.stun > 0 else 0) | (64 if e.slowf > 1.0 else 0)
                         | (128 if e.side == side and self.hidden_kind(e) else 0) | (512 if e.fast else 0))
                if e.cat == 'k':
                    ks = self.sd[e.side]
                    flags |= (256 if ks.block_t >= 0 else 0) | (1024 if ks.ult_t > 0 else 0)
                elif e.cat == 'u' and self.cry(e) < 1.0:
                    flags |= 1024
                out.append([e.id, e.kind, e.side, round(e.x, 2), round(e.y, 2), int(math.ceil(e.hp)), int(e.maxhp), e.lvl, e.path,
                            flags, e.kills if e.side == side else 0])

        def seen(x, y):
            xi, yi = int(round(x)), int(round(y))
            return 0 <= yi < H and 0 <= xi < W and vis[yi][xi]
        my_fx = [f for f in fx if f[5] == side or f[0] in 'oR' or seen(f[1], f[2]) or (f[0] in 'ksmtqazD' and seen(f[3], f[4]))]
        my_fx += self.pfx[side]
        self.pfx[side] = []
        j = sd.job
        k = sd.kral
        rl = self.relic
        msg = {
            't': 's', 'tm': round(self.t, 1), 'ni': self.night, 'st': self.stage, 'nw': int(max(0, self.next_wave - self.t)),
            'r': [int(sd.e), int(sd.s), int(sd.v)], 'inc': round(self.income(side), 1), 'gp': gen_price(self.count(side, 'gen')),
            'sp': sniper_price(self.count(side, 'sniper')), 'ec': self.eclipse(), 'dl': [int(self.dealt[0]), int(self.dealt[1])],
            'rl': [rl['own'], rl['by'], round(rl['p'] / RELIC_TIME, 2), int(math.ceil(RELIC_SAMPLE - rl['vt'])) if rl['own'] >= 0 else 0],
            'doba': sd.doba, 'tech': sorted(sd.techs), 'cd': {c: round(v, 1) for c, v in sd.cd.items()},
            'free': dict(sd.free), 'mob': sd.mobil, 'stc': sd.stats['crates'],
            'th': [int(math.ceil(self.throne[0])), int(math.ceil(self.throne[1]))],
            'sh': [round(self.sd[0].shield, 1), round(self.sd[1].shield, 1)],
            'ck': [round(self.sd[0].check, 1), round(self.sd[1].check, 1)],
            'out': [round(self.sd[0].outage, 1), round(self.sd[1].outage, 1)],
            'v': ''.join('1' if vis[y][x] else '0' for y in range(H) for x in range(W)),
            'ter': ''.join(''.join(row) for row in self.ter),
            'en': out, 'fx': my_fx,
            'cr': [[c['id'], c['x'], c['y'], c['r'], round(c['land'], 1), int(c['ttl']),
                    round(c['ch'][0] / CRATE_CH, 2), round(c['ch'][1] / CRATE_CH, 2), 1 if c['now'] else 0] for c in self.crates.values()],
            'dr': [[round(d['x'], 2), round(d['y'], 2), d['s'], 1 if d['h'] else 0] for d in self.drones],
            'ns': [[x, y, round(t, 1), s] for s, x, y, t in self.strikes],
            'qb': [[y, round(t, 1)] for y, t in self.barriers],
            'lu': [self.lure[0], self.lure[1], round(self.lure[2], 1)] if self.lure else None,
            'rv': [[x, y, round(t, 1), r] for x, y, t, r in sd.reveals],
            'job': [j[0], j[1], round(j[2] / SCRAP_TIME, 2)] if j else None,
            'hcd': round(sd.horde_cd, 1), 'hc': round(HORDE_COST * (0.6 if 'bio1' in sd.techs else 1.0)),
        }
        if self.mode == 'kral':
            msg['kr'] = {'id': k.id if k else 0, 'dead': round(sd.respawn, 1) if k is None else 0,
                         'blk': (2 if self.t - sd.block_t <= KRAL['parry'] else 1) if sd.block_t >= 0 else 0,
                         'bcd': round(sd.block_cd, 1), 'ult': int(sd.ult), 'ua': round(sd.ult_t, 1), 'dcd': round(sd.dash_cd, 1),
                         'sf': round(k.slowf, 3) if k else 1}
        if self.msgs[side]:
            msg['msg'] = [t for t, _ in self.msgs[side]]
            msg['mk'] = [kind for _, kind in self.msgs[side]]
            self.msgs[side] = []
        if self.evs[side]:
            msg['ev'] = self.evs[side]
            self.evs[side] = []
        return msg


# ---------------------------------------------------------------- networking

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


DEFS_MSG = {'t': 'defs', 'ver': VERSION, 'defs': DEFS, 'research': RESEARCH, 'branches': BRANCHES, 'cmds': CMDS,
            'base': BASE_KIT, 'pool': CARD_POOL, 'recommended': RECOMMENDED, 'deckSize': DECK_SIZE,
            'rarity': [r[0] for r in RARITY], 'modes': MODES, 'dobaAt': DOBA_AT,
            'relic': RELIC, 'relicFrom': RELIC_FROM, 'eclipses': ECLIPSES, 'eclLen': ECL_LEN, 'conv': CONV}


class Client:
    def __init__(self, writer):
        self.writer = writer
        peer = writer.get_extra_info('peername')
        self.ip = str(peer[0]) if peer else '?'
        if self.ip.startswith('::ffff:'):
            self.ip = self.ip[7:]
        self.name = 'Král'
        self.side = None
        self.ready = False
        self.deck = None
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


class Lobby:
    """Two player slots plus a waiting queue, so an extra or forgotten browser tab never locks anyone out."""

    def __init__(self):
        self.slots = [None, None]
        self.waiting = []
        self.game = None
        self.task = None
        self.mode = 'kral'
        self.last_log = ''

    def clients(self):
        return [c for c in self.slots if c] + self.waiting

    def info(self, c, now):
        return {'name': c.name, 'ip': c.ip, 'ready': c.ready, 'idle': int(now - c.acted)}

    def broadcast(self, obj):
        for c in self.slots:
            if c:
                c.send(obj)

    def update(self):
        now = time.monotonic()
        players = [dict(self.info(c, now), side=i) if c else None for i, c in enumerate(self.slots)]
        queue = [self.info(c, now) for c in self.waiting]
        for c in self.clients():
            c.send({'t': 'lobby', 'players': players, 'queue': queue, 'you': c.side, 'mode': self.mode,
                    'pos': self.waiting.index(c) + 1 if c in self.waiting else 0, 'kickIdle': KICK_IDLE,
                    'playing': self.game is not None, 'urls': URLS, 'ver': VERSION})
        self.log()

    def log(self):
        parts = ['%d) %s [%s]%s' % (i + 1, c.name, c.ip, ' - pripraven' if c.ready else '') if c else '%d) volno' % (i + 1)
                 for i, c in enumerate(self.slots)]
        if self.waiting:
            parts.append('fronta: ' + ', '.join('%s [%s]' % (c.name, c.ip) for c in self.waiting))
        line = '  Lobby (%s): ' % self.mode + ' | '.join(parts)
        if line != self.last_log:
            self.last_log = line
            print(line)

    def join(self, c):
        if len(self.clients()) >= MAX_CONN:
            return False
        for i in (0, 1):
            if self.slots[i] is None:
                self.slots[i] = c
                c.side = i
                return True
        self.waiting.append(c)
        return True

    def seat(self, side, c=None):
        """Give a free slot to c, or to whoever waits longest."""
        if self.slots[side] is not None or self.game is not None:
            return
        if c is None:
            if not self.waiting:
                return
            c = self.waiting[0]
        if c in self.waiting:
            self.waiting.remove(c)
        self.slots[side] = c
        c.side = side
        c.ready = False

    def leave(self, c):
        if c in self.waiting:
            self.waiting.remove(c)
            self.update()
            return
        if c.side is None or self.slots[c.side] is not c:
            return
        side = c.side
        self.slots[side] = None
        c.side = None
        if self.game and not self.game.over:
            self.finish({'winner': 1 - side, 'reason': 'Soupeř se odpojil.'})
        for o in self.slots:
            if o:
                o.ready = False
        self.seat(side)
        self.update()

    def kick(self, c, side):
        """A player may remove an opponent who is not ready; a waiting player only one idle for KICK_IDLE s."""
        if self.game or side not in (0, 1):
            return
        t = self.slots[side]
        if t is None or t is c or t.ready:
            return
        if c.side is None and time.monotonic() - t.acted < KICK_IDLE:
            return
        print('  %s [%s] uvolnil misto hrace %s [%s]' % (c.name, c.ip, t.name, t.ip))
        self.slots[side] = None
        t.side = None
        t.send({'t': 'kicked', 'by': c.name})
        asyncio.get_running_loop().call_later(0.5, t.drop)
        self.seat(side, c if c in self.waiting else None)
        self.update()

    def handle(self, c, text):
        try:
            m = json.loads(text)
        except ValueError:
            return
        if not isinstance(m, dict):
            return
        c.acted = time.monotonic()
        t = m.get('t')
        if t == 'hello':
            name = m.get('name')
            c.name = ((name if isinstance(name, str) else '').strip() or 'Král')[:16]
            self.update()
        elif t == 'ready':
            if self.game or c.side is None:
                return
            c.ready = bool(m.get('v'))
            if c.ready:
                c.deck = valid_deck(m.get('deck')) or list(RECOMMENDED)
            self.update()
            if all(s and s.ready for s in self.slots):
                self.start()
        elif t == 'mode':
            if self.game or c.side is None or m.get('v') not in MODES or m.get('v') == self.mode:
                return
            self.mode = m.get('v')
            for o in self.slots:
                if o:
                    o.ready = False
            self.update()
        elif t == 'kick':
            self.kick(c, m.get('side'))
        elif self.game and not self.game.over and c.side is not None:
            try:
                self.game.act(c.side, m)
            except Exception:
                traceback.print_exc()

    def start(self):
        names = [self.slots[0].name, self.slots[1].name]
        decks = [self.slots[0].deck or list(RECOMMENDED), self.slots[1].deck or list(RECOMMENDED)]
        self.game = Game(names, decks, self.mode)
        for c in self.slots:
            c.ready = False
            c.send({'t': 'start', 'side': c.side, 'names': names, 'w': W, 'h': H, 'half': HALF, 'mist': MIST,
                    'mode': self.mode, 'deck': decks[c.side], 'throne': THRONE_HP, 'horde': [HORDE_COST, HORDE_CD]})
        self.task = asyncio.ensure_future(self.run())
        print('  Zapas zacal (%s): %s vs %s (delka %.0f s)' % (self.mode, names[0], names[1], self.game.length))
        self.update()

    def finish(self, result):
        g = self.game
        if not g:
            return
        g.over = result
        payload = {'t': 'end', 'winner': result['winner'], 'reason': result['reason'], 'tm': round(g.t),
                   'stats': [g.sd[0].stats, g.sd[1].stats], 'names': g.names, 'th': [int(g.throne[0]), int(g.throne[1])],
                   'dl': [int(g.dealt[0]), int(g.dealt[1])]}
        self.broadcast(payload)
        self.game = None
        print('  Zapas skoncil: %s' % result['reason'])
        self.update()

    async def run(self):
        g = self.game
        n = 0
        nxt = time.perf_counter()
        while self.game is g and not g.over:
            try:
                g.step(TICK)
            except Exception:
                traceback.print_exc()
                self.finish({'winner': -1, 'reason': 'Chyba serveru, zápas byl ukončen.'})
                break
            n += 1
            if n % SNAP_EVERY == 0 or g.over:
                fx = g.fx
                g.fx = []
                for c in self.slots:
                    if c:
                        c.send(g.snapshot(c.side, fx), droppable=True)
            if g.over:
                self.finish(g.over)
                break
            nxt += TICK
            delay = nxt - time.perf_counter()
            if delay < -0.5:
                nxt = time.perf_counter()
                delay = 0
            await asyncio.sleep(max(0.0, delay))


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
    print('  + %s pripojen %s' % (c.ip, 'jako hrac %d' % (c.side + 1) if c.side is not None else 'do fronty'))
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
        if LOBBY.waiting and LOBBY.game is None:
            LOBBY.update()


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


async def main():
    global URLS
    server = await asyncio.start_server(handle, '0.0.0.0', PORT)
    URLS = ['http://%s:%d' % (ip, PORT) for ip in lan_ips()]
    print('')
    print('  HRA MRTVYCH KRALU %s - server bezi.' % VERSION)
    print('  Ty:       http://localhost:%d' % PORT)
    for u in URLS:
        print('  Souper:   %s' % u)
    print('')
    print('  Server ukoncis klavesami Ctrl+C.')
    print('')
    if '--no-browser' not in sys.argv:
        try:
            webbrowser.open('http://localhost:%d' % PORT)
        except Exception:
            pass
    asyncio.ensure_future(heartbeat())
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Server ukoncen.')
    except OSError as e:
        print('Server se nepodarilo spustit: %s' % e)
        print('Port %d je mozna obsazeny. Zkus: python server.py 8096' % PORT)
