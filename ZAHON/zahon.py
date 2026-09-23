#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZÁHON — poslední skleník
Ministerstvo zemědělské asimilace · Sektor 7

Spuštění:   python zahon.py        (vyžaduje pygame-ce)

Ovládání:   myš — klik na balíček, pak na políčko
            klik na světlo = sebrat
            1–9 výběr balíčku · S lopata · pravé tlačítko zrušit výběr
            P / Esc pauza · M hudba · F11 celá obrazovka

Uložení:    zahon_save.json (vedle skriptu)
Zvuky:      složka sounds/ — při prvním spuštění se syntetizují jako WAV.
            Libovolný soubor můžeš nahradit vlastním (stejné jméno,
            .wav / .ogg / .mp3).
LAN režim:  TCP port 50515, hledání hostitelů UDP port 50516.
"""
import os
import sys
import json
import math
import time
import array
import wave
import queue
import random
import socket
import getpass
import threading

try:
    import pygame
except ImportError:
    print("Chybí knihovna pygame. Nainstaluj ji příkazem:\n    python -m pip install pygame-ce")
    sys.exit(1)

# ---------------------------------------------------------------- konstanty
BASE = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(BASE, "zahon_save.json")
SND_DIR = os.path.join(BASE, "sounds")

W, H = 1120, 720
FPS = 60
BX, BY = 200, 120
CW, CH = 88, 100
COLS, LANES = 9, 5
BOARD_R = BX + COLS * CW
SPAWN_X = BOARD_R + 70
HOUSE_X = BX - 55
PUZZLE_X = BX + 7 * CW + CW // 2
PORT, DISC_PORT, PROTO = 50515, 50516, 1
SNAP_DT = 1 / 20

PK_X0, PK_Y, PK_W, PK_H, PK_GAP = 112, 10, 70, 88, 6

BG = (10, 11, 10)
PANEL = (20, 22, 20)
EDGE = (60, 64, 56)
TEXT = (210, 214, 196)
DIM = (116, 120, 106)
ACID = (150, 240, 70)
HOPE = (255, 214, 90)
WARN = (255, 64, 50)
AMBER = (255, 170, 20)
CYAN = (60, 220, 210)
TOX = (170, 90, 220)
LEAF = (70, 170, 60)
LEAF_D = (36, 100, 36)
BLOOD = (120, 16, 16)
MSG_COL = {"warn": WARN, "hope": HOPE, "info": TEXT, "acid": ACID}


def lane_cy(l):
    return BY + l * CH + CH // 2


def lane_fy(l):
    return BY + l * CH + CH - 14


# ---------------------------------------------------------------- rostliny
PLANTS = {
    'lampa': dict(name="SVĚTLONOŠ", cost=50, cd=7.5, hp=300,
                  desc="Chytá poslední paprsky ze smogu. Každých 22 s vydá 25 světla."),
    'trn': dict(name="TRNOMET", cost=100, cd=7.5, hp=300, rate=1.4, dmg=20,
                desc="Střílí trny do své řady. Základ každé obrany."),
    'parez': dict(name="PAŘEZ V BETONU", cost=50, cd=30, hp=4000,
                  desc="Zarostl do betonu dřív, než vzniklo Ministerstvo. Vydrží dlouhé ožírání."),
    'ostruz': dict(name="OSTRUŽINÍK", cost=100, cd=7.5, hp=300, dmg=20,
                   desc="Plazí se po zemi a zraňuje každého, kdo po něm jde. Nedá se sníst."),
    'mina': dict(name="KOŘENOVÁ MINA", cost=25, cd=30, hp=300, arm=12, dmg=1800,
                 desc="Za 12 s zakoření. Pak vybuchne pod prvním, kdo na ni šlápne."),
    'jed': dict(name="JEDOVATKA", cost=150, cd=7.5, hp=300, rate=1.6, dmg=15,
                desc="Plive spóry, které zraní a na 3 s zpomalí."),
    'maso': dict(name="MASOŽRAVKA", cost=150, cd=7.5, hp=300, chew=25,
                 desc="Spolkne asimilovaného před sebou. Pak 25 s tráví a je bezbranná."),
    'pamp': dict(name="PAMPELIŠKA NADĚJE", cost=125, cd=15, hp=300, rate=2.0, dmg=10,
                 desc="Její pyl občas probudí zraněného asimilovaného. Sousední rostliny střílí rychleji."),
}
PLANT_ORDER = ['lampa', 'trn', 'parez', 'ostruz', 'mina', 'jed', 'maso', 'pamp']
PROJ_SPD = {'trn': 380, 'jed': 330, 'pamp': 300}

# ---------------------------------------------------------------- asimilovaní
ZOMBIES = {
    'zak': dict(name="ASIMILOVANÝ", hp=200, shield=0, speed=18, bite=100, cost=50, cd=3,
                desc="Bývalý občan. Čip v zátylku, prázdné oči. Jde dál."),
    'bez': dict(name="BĚŽEC", hp=150, shield=0, speed=38, bite=80, cost=75, cd=5,
                desc="Rychlý a křehký. Běží, dokud nepadne."),
    'doz': dict(name="DOZORCE", hp=200, shield=550, speed=16, bite=100, cost=125, cd=8,
                desc="Štít zachytí trny i spóry. Výbuch a ostružiník jdou přes něj."),
    'post': dict(name="POSTŘIKOVAČ", hp=300, shield=0, speed=16, bite=100, cost=150, cd=10,
                 desc="Z dálky stříká herbicid na nejbližší rostlinu v řadě."),
    'dron': dict(name="DRONOVÝ SKOKAN", hp=250, shield=0, speed=30, bite=100, cost=125, cd=8,
                 desc="Přeskočí první rostlinu v cestě. Pak už jen jde."),
    'kaz': dict(name="KAZATEL", hp=350, shield=0, speed=14, bite=100, cost=175, cd=15,
                desc="Megafon zrychluje a léčí okolní asimilované. Chrání je před probuzením."),
    'exe': dict(name="EXEKUTOR", hp=3000, shield=0, speed=10, bite=0, cost=450, cd=40,
                desc="Obří úředník s razítkem ZAMÍTNUTO. Rozdrtí cokoli. Když je zraněný, hodí běžce."),
    'boss': dict(name="KOMBAJN", hp=4500, shield=0, speed=3.5, bite=0, cost=0, cd=0,
                 desc="Stroj na sklizeň všeho živého. Zabírá tři řady."),
}
ZOMB_ORDER = ['zak', 'bez', 'doz', 'post', 'dron', 'kaz', 'exe']
ZCOL = {
    'zak': ((78, 84, 78), (52, 56, 52)),
    'bez': ((180, 96, 36), (70, 50, 34)),
    'doz': ((36, 46, 76), (24, 30, 50)),
    'post': ((196, 184, 58), (120, 112, 40)),
    'dron': ((66, 66, 70), (40, 40, 44)),
    'kaz': ((110, 24, 24), (40, 20, 20)),
    'exe': ((48, 48, 54), (30, 30, 34)),
}
AWAKENABLE = ('zak', 'bez', 'doz')

# ---------------------------------------------------------------- úrovně
LEVELS = [
    dict(name="SUTINY", new=['lampa', 'trn'], light=150, dark=False, sky=True, first=26,
         beams=1,
         story=["Rok 14 po Zhasnutí. Nebe je hnědé, slunce jen tušíš.",
                "Pod troskami Sektoru 7 stojí poslední skleník.",
                "Asimilovaní jdou po všem živém. Čip jim nařizuje: VYKOŘENIT.",
                "Zasaď Světlonoše a sbírej světlo ze smogu. Trnomety se postarají o zbytek."],
         waves=[[('zak', 1)], [('zak', 1)], [('zak', 2)], [('zak', 2)], [('zak', 3)],
                ['BIG', ('zak', 6)]]),
    dict(name="KANÁLY", new=['parez', 'ostruz'], light=150, dark=False, sky=True, first=26,
         beams=1,
         story=["Přišli kanály. Tentokrát s dozorci a štíty.",
                "Pařez v betonu je starší než Ministerstvo. A vydrží víc.",
                "Ostružiník nikdo nezasadil. Prostě vyrostl. Jako vždycky."],
         waves=[[('zak', 1)], [('zak', 2)], [('zak', 1), ('bez', 1)], [('zak', 2)],
                [('doz', 1), ('zak', 1)], [('zak', 2), ('bez', 1)],
                ['BIG', ('zak', 4), ('bez', 1), ('doz', 1)]]),
    dict(name="VÝPADEK", new=['mina', 'jed'], light=200, dark=True, sky=False, first=26,
         beams=1,
         story=["Ministerstvo vypnulo proud celé čtvrti.",
                "Ve tmě svítí jen Světlonoši. Ze smogu nespadne nic.",
                "V hlíně čekají Kořenové miny a Jedovatka."],
         waves=[[('zak', 1)], [('zak', 2)], [('post', 1), ('zak', 1)], [('dron', 1), ('zak', 1)],
                [('doz', 1), ('zak', 2)], [('dron', 1), ('bez', 1), ('zak', 1)],
                ['BIG', ('zak', 4), ('dron', 1), ('post', 1), ('doz', 1)]]),
    dict(name="HRADBA", new=['maso'], light=150, dark=False, sky=True, first=24,
         beams=1,
         story=["Ministerstvo poslalo Exekutora. Nese razítko ZAMÍTNUTO.",
                "Kazatelé řvou do megafonů a asimilovaní zrychlují.",
                "Masožravka má hlad."],
         waves=[[('zak', 2)], [('kaz', 1), ('zak', 2)], [('doz', 1), ('bez', 2)],
                [('post', 1), ('dron', 1), ('zak', 1)], [('exe', 1)],
                [('kaz', 1), ('doz', 1), ('zak', 2)],
                ['BIG', ('zak', 5), ('bez', 2), ('doz', 1), ('kaz', 1), ('exe', 1)]]),
    dict(name="KOMBAJN", new=['pamp'], light=200, dark=False, sky=True, first=24,
         beams=2,
         story=["Tohle už není úřad. Je to stroj na sklizeň.",
                "KOMBAJN srovná se zemí všechno, co roste.",
                "Na okraji skleníku ale rozkvetla pampeliška.",
                "Říká se, že její pyl dokáže člověka probudit."],
         waves=[[('zak', 2), ('bez', 1)], [('doz', 1), ('post', 1), ('dron', 1)], [('kaz', 1), ('zak', 3)],
                'BOSS', [('doz', 1), ('bez', 2)],
                ['BIG', ('zak', 5), ('doz', 1), ('exe', 1)]]),
]
SECRET_STORY = ["Pod skleníkem vedou kořeny až do Sektoru 9.",
                "Probuzení tudy nesou semínka domů. Staré obranné rostliny je ale nepoznají.",
                "Proveď je všemi pěti řadami. Každý, kdo projde, zasadí semínko.",
                "Rozpočet je pevný. Promysli to."]
ENDLESS_STORY = ["Nekonečná noc. Vlny nekončí, jen sílí.",
                 "Od šesté vlny padá kyselý déšť.",
                 "Kolik jich vydržíš?"]
ENDING = ["KOMBAJN utichl.",
          "Ticho. Pak ptačí zpěv, poprvé za čtrnáct let.",
          "Smog se protrhl a na skleník dopadl skutečný paprsek slunce.",
          "Probuzení se vracejí domů a nesou semínka.",
          "Ministerstvo pořád stojí. Ale už víme, že věci umí růst.",
          "— KONEC PRVNÍ SEZÓNY —",
          "Pod kořeny něco šeptá… (tajná úroveň odemčena)"]

PUZZLE_BUDGET = 1050
PUZZLE_LAYOUT = [
    (0, 0, 'trn'), (0, 3, 'parez'),
    (1, 0, 'trn'), (1, 2, 'trn'),
    (2, 1, 'jed'), (2, 3, 'ostruz'), (2, 4, 'ostruz'),
    (3, 0, 'trn'), (3, 2, 'maso'),
    (4, 0, 'lampa'), (4, 1, 'lampa'), (4, 3, 'mina'), (4, 4, 'trn'),
]
PUZZLE_ZOMBIES = ['zak', 'bez', 'doz', 'post', 'dron']

PVP_MODES = {
    'klasika': dict(name="KLASIKA", dur=300, light=150, zloba=150, mult=1.0, dark=False, rain=False,
                    exe_lock=90, desc="Kytky musí vydržet 5 minut. Zombie musí prorazit do skleníku."),
    'vypadek': dict(name="VÝPADEK PROUDU", dur=300, light=200, zloba=150, mult=1.0, dark=True, rain=False,
                    exe_lock=90, desc="Tma. Kytky vidí jen kolem Světlonošů. Ze smogu nic nepadá."),
    'dest': dict(name="KYSELÝ DÉŠŤ", dur=300, light=150, zloba=150, mult=1.5, dark=False, rain=True,
                 exe_lock=90, desc="Každých 25 s leje kyselina a leptá všechno. Obě strany mají o polovinu vyšší příjem."),
    'blesk': dict(name="BLESKOVKA", dur=180, light=300, zloba=300, mult=2.0, dark=False, rain=False,
                  exe_lock=0, desc="3 minuty, dvojnásobný příjem, Exekutor dostupný hned."),
}
PVP_ORDER = ['klasika', 'vypadek', 'dest', 'blesk']
PVP_GRACE = 20

SLOGANY = [
    "ZELEŇ JE NEPOVOLENÁ STAVBA", "KAŽDÝ KOŘEN HLAS SVÉMU DOZORCI",
    "ASIMILACE JE BEZBOLESTNÁ", "SMOG CHRÁNÍ PŘED SLUNCEM",
    "* na zdi někdo nasprejoval: NĚKDE POŘÁD ROSTE STROM *",
    "SEMENA JSOU MAJETKEM MINISTERSTVA", "DNEŠNÍ PŘÍDĚL KYSLÍKU: 91 %",
    "* graffiti: PAMATUJEŠ SI BARVU NEBE? *", "NAHLAS SOUSEDA, KTERÝ ZALÉVÁ",
    "* někdo nechal na lavičce jablko *", "SEKTOR 7 · SKLIZEŇ PROBÍHÁ PODLE PLÁNU",
    "KVÓTA SPLNĚNA NA 104 %",
]


def plants_for_level(n):
    out = []
    for i in range(n + 1):
        out += LEVELS[i]['new']
    return [k for k in PLANT_ORDER if k in out]


# ================================================================ SIMULACE
class Plant:
    __slots__ = ("k", "lane", "col", "hp", "mhp", "t", "st")

    def __init__(self, k, lane, col, armed=False):
        d = PLANTS[k]
        self.k, self.lane, self.col = k, lane, col
        self.hp = self.mhp = d["hp"]
        self.t = {'lampa': 7.0, 'mina': 0.0 if armed else d.get('arm', 0)}.get(k, 0.0)
        self.st = 0.0

    @property
    def cx(self):
        return BX + self.col * CW + CW / 2


class Zombie:
    def __init__(self, zid, k, lane, x, rng):
        d = ZOMBIES[k]
        self.id, self.k, self.lane, self.x = zid, k, lane, x
        self.hp = self.mhp = d['hp']
        self.shield = self.mshield = d['shield']
        self.speed = d['speed'] * rng.uniform(0.92, 1.08)
        self.bite = d['bite']
        self.slow = 0.0
        self.awake = False
        self.jumped = False
        self.jump_t = 0.0
        self.jump_from = 0.0
        self.eating = False
        self.spray = False
        self.wind = 0.0
        self.thrown = False
        self.buff = False
        self.snd_t = 0.0
        self.hurt = 0.0
        self.anim = rng.random() * 10
        self.lanes = (lane,)
        self.t1 = 0.0
        self.t2 = 0.0
        self.enraged = False
        self.silent = False
        if k == 'boss':
            self.lane = 2
            self.lanes = (1, 2, 3)
            self.t1, self.t2 = 8.0, 12.0

    def hostile(self):
        return not self.awake and self.hp > 0

    def airborne(self):
        return self.jump_t > 0

    def front(self):
        return self.x - 110 if self.k == 'boss' else self.x

    def jump_y(self):
        if self.jump_t <= 0:
            return 0.0
        f = 1 - self.jump_t / 0.7
        return math.sin(math.pi * f) * 60

    def flags(self):
        f = 0
        if self.eating:
            f |= 1
        if self.awake:
            f |= 2
        if self.slow > 0:
            f |= 4
        if self.buff:
            f |= 8
        if self.spray:
            f |= 16
        if self.enraged:
            f |= 32
        if self.hurt > 0:
            f |= 64
        return f


class Proj:
    __slots__ = ("k", "lane", "x", "dmg", "alive")

    def __init__(self, k, lane, x, dmg):
        self.k, self.lane, self.x, self.dmg = k, lane, x, dmg
        self.alive = True


class World:
    """Celá hra bez grafiky. kind: sp | pvp | puzzle | endless."""

    def __init__(self, kind, level=0, pvp_mode='klasika', seed=None):
        self.rng = random.Random(seed)
        self.kind = kind
        self.level = level
        self.pvp_mode = pvp_mode
        self.grid = [[None] * COLS for _ in range(LANES)]
        self.zombies = []
        self.projs = []
        self.lights = []
        self.barrels = []
        self.mowers = [0.0] * LANES
        self.seeds = [False] * LANES
        self.events = []
        self.time = 0.0
        self.countdown = 0.0
        self.result = None
        self.nid_c = 1
        self.beam = None
        self.beam_times = []
        self.rain = 0.0
        self.rain_on = False
        self.rain_t = 25.0
        self.dark = False
        self.sky = True
        self.duration = None
        self.mult = 1.0
        self.exe_lock = 0
        self.plant_list = []
        self.zomb_list = []
        self.light = 50
        self.zloba = 0.0
        self.cdp = {}
        self.cdz = {}
        self.zcd = {k: ZOMBIES[k]['cd'] for k in ZOMB_ORDER}
        self.script = []
        self.si = 0
        self.total_z = 0
        self.spawned = 0
        self.sky_t = 6.0
        self.wave = 0
        self.awakened = 0
        self.freed = 0
        self.last_lane = -1
        self.aura = set()
        self.lamp_period = 22.0
        if kind == 'sp':
            L = LEVELS[level]
            self.plant_list = plants_for_level(level)
            self.light = L['light']
            self.dark = L['dark']
            self.sky = L['sky']
            self.build_script(L)
            self.beam_times = sorted(self.rng.uniform(50, 130) + i * 70 for i in range(L['beams']))
        elif kind == 'pvp':
            M = PVP_MODES[pvp_mode]
            self.plant_list = PLANT_ORDER[:]
            self.zomb_list = ZOMB_ORDER[:]
            self.light = M['light']
            self.zloba = float(M['zloba'])
            self.duration = M['dur']
            self.dark = M['dark']
            self.sky = not M['dark']
            self.rain_on = M['rain']
            self.mult = M['mult']
            self.exe_lock = M['exe_lock']
            self.countdown = 3.0
            self.lamp_period = 20.0
            self.beam_times = [self.duration * 0.33, self.duration * 0.66]
        elif kind == 'puzzle':
            self.zomb_list = PUZZLE_ZOMBIES[:]
            self.zloba = float(PUZZLE_BUDGET)
            self.sky = False
            self.mowers = [-1.0] * LANES
            self.zcd = {k: 0.6 for k in ZOMB_ORDER}
            for lane, col, k in PUZZLE_LAYOUT:
                self.grid[lane][col] = Plant(k, lane, col, armed=True)
        elif kind == 'endless':
            self.plant_list = PLANT_ORDER[:]
            self.light = 150

    # ------------------------------------------------------------ pomocné
    def nid(self):
        self.nid_c += 1
        return self.nid_c

    def ev(self, *a):
        self.events.append(list(a))

    def pop_events(self):
        e = self.events
        self.events = []
        return e

    def hostile_count(self):
        return sum(1 for z in self.zombies if z.hostile())

    def plants(self):
        for row in self.grid:
            for p in row:
                if p:
                    yield p

    def build_script(self, L):
        t = L['first']
        out = []
        for w in L['waves']:
            if w == 'BOSS':
                out.append((t, 'flag', "POZOR: BLÍŽÍ SE KOMBAJN"))
                out.append((t + 4, 'boss', None))
                t += 34
                continue
            big = w[0] == 'BIG'
            items = w[1:] if big else w
            ks = [k for k, n in items for _ in range(n)]
            self.rng.shuffle(ks)
            if big:
                out.append((t, 'flag', "VELKÁ VLNA ASIMILOVANÝCH"))
                t += 3
            spread = 0.9 if big else 2.2
            for j, k in enumerate(ks):
                out.append((t + j * spread + self.rng.uniform(0, 0.6), 'z', k))
            t += len(ks) * spread + (0 if big else 20 + 2 * len(ks))
        out.sort(key=lambda e: e[0])
        self.script = out
        self.total_z = sum(1 for e in out if e[1] in ('z', 'boss'))

    def endless_wave(self):
        self.wave += 1
        n = self.wave
        budget = 60 + n * 70
        big = n % 5 == 0
        if big:
            budget = int(budget * 1.6)
        pool = ['zak']
        for k, need in (('bez', 2), ('doz', 3), ('post', 4), ('dron', 5), ('kaz', 7), ('exe', 9)):
            if n >= need:
                pool.append(k)
        cost = {'zak': 50, 'bez': 70, 'doz': 120, 'post': 140, 'dron': 110, 'kaz': 170, 'exe': 500}
        ks = []
        while budget >= 50:
            k = self.rng.choice(pool)
            if cost[k] <= budget:
                ks.append(k)
                budget -= cost[k]
            elif self.rng.random() < 0.3:
                break
        t = self.time + (25 if n == 1 else 8)
        self.script.append((t, 'flag', ("VELKÁ VLNA %d" % n) if big else ("VLNA %d" % n)))
        spread = 0.9 if big else 1.8
        for j, k in enumerate(ks):
            self.script.append((t + 2 + j * spread + self.rng.uniform(0, 0.5), 'z', k))
        self.script.sort(key=lambda e: e[0])
        if n >= 6:
            self.rain_on = True
        if n % 3 == 0:
            self.beam_times.append(t + 5)

    def pick_lane(self):
        lanes = list(range(LANES))
        if self.last_lane >= 0 and self.rng.random() < 0.7:
            lanes.remove(self.last_lane)
        l = self.rng.choice(lanes)
        self.last_lane = l
        return l

    def spawn_z(self, k, lane=None, x=None):
        if lane is None:
            lane = self.pick_lane()
        if x is None:
            x = SPAWN_X + self.rng.uniform(0, 30)
        z = Zombie(self.nid(), k, lane, x, self.rng)
        self.zombies.append(z)
        if k == 'boss':
            z.x = SPAWN_X + 60
            self.ev('snd', 'roar')
        elif self.rng.random() < 0.35:
            self.ev('snd', 'groan')
        return z

    def spawn_light(self, x, y, ty, val, falling):
        self.lights.append({'id': self.nid(), 'x': x, 'y': y, 'ty': ty, 'v': val,
                            'ttl': 9.0 if falling else 12.0, 'vy': 0.0 if falling else -110.0,
                            'fall': falling, 'land': False})

    def hope_beam(self):
        x = self.rng.uniform(BX + 60, BOARD_R - 60)
        self.beam = [x, 4.0]
        if self.kind != 'puzzle':
            for i in range(4):
                self.spawn_light(x + self.rng.uniform(-25, 25), BY - 30 - i * 50,
                                 self.rng.uniform(BY + 60, BY + LANES * CH - 40), 25, True)
        self.ev('snd', 'beam')
        self.ev('bird')
        self.ev('msg', "PAPRSEK NADĚJE — smog se na chvíli protrhl", 'hope')

    def enemy_ahead(self, lane, x):
        for z in self.zombies:
            if z.hostile() and lane in z.lanes and z.x > x - 10 and z.front() < W - 30:
                return True
        return False

    def hurt(self, z, dmg, proj=False):
        if z.hp <= 0:
            return
        if proj and z.shield > 0:
            z.shield -= dmg
            if z.shield <= 0:
                z.shield = 0
                self.ev('snd', 'shieldbreak')
                self.ev('fx', 'shield', z.x - 20, lane_cy(z.lane) - 20)
            else:
                self.ev('snd', 'clank')
            return
        z.hp -= dmg
        z.hurt = 0.08

    def kill_plant(self, p, fx='leaves'):
        if self.grid[p.lane][p.col] is p:
            self.grid[p.lane][p.col] = None
            self.ev('fx', fx, p.cx, lane_cy(p.lane))
            self.ev('snd', 'plantdie')

    # ------------------------------------------------------------ akce hráčů
    def act(self, side, a):
        if self.result or self.countdown > 0 or not a:
            return
        typ = a[0]
        try:
            if side == 'P':
                if typ == 'plant':
                    k, lane, col = a[1], int(a[2]), int(a[3])
                    if k not in self.plant_list or not (0 <= lane < LANES and 0 <= col < COLS):
                        return
                    cost = PLANTS[k]['cost']
                    if self.grid[lane][col] or self.cdp.get(k, 0) > 0 or self.light < cost:
                        return
                    for z in self.zombies:
                        if z.k == 'boss' and lane in z.lanes and BX + col * CW + CW / 2 > z.front() - 60:
                            return
                    self.grid[lane][col] = Plant(k, lane, col)
                    self.light -= cost
                    self.cdp[k] = PLANTS[k]['cd']
                    self.ev('snd', 'plant')
                    self.ev('fx', 'dust', BX + col * CW + CW / 2, lane_cy(lane))
                elif typ == 'shovel':
                    lane, col = int(a[1]), int(a[2])
                    if 0 <= lane < LANES and 0 <= col < COLS and self.grid[lane][col]:
                        p = self.grid[lane][col]
                        self.grid[lane][col] = None
                        self.ev('snd', 'plant')
                        self.ev('fx', 'dust', p.cx, lane_cy(lane))
                elif typ == 'collect':
                    lid = int(a[1])
                    for L in self.lights:
                        if L['id'] == lid:
                            self.light += L['v']
                            self.lights.remove(L)
                            self.ev('snd', 'collect')
                            self.ev('fx', 'spark', L['x'], L['y'])
                            break
            elif side == 'Z' and typ == 'zombie':
                k, lane = a[1], int(a[2])
                if k not in self.zomb_list or not (0 <= lane < LANES):
                    return
                cost = ZOMBIES[k]['cost']
                if self.cdz.get(k, 0) > 0 or self.zloba < cost:
                    return
                if self.kind == 'pvp' and (self.time < PVP_GRACE or (k == 'exe' and self.time < self.exe_lock)):
                    return
                self.zloba -= cost
                self.cdz[k] = self.zcd[k]
                x = PUZZLE_X + self.rng.uniform(-8, 8) if self.kind == 'puzzle' else None
                self.spawn_z(k, lane, x)
                self.ev('snd', 'groan')
        except (ValueError, TypeError, IndexError, KeyError):
            pass

    # ------------------------------------------------------------ krok simulace
    def update(self, dt):
        if self.result:
            return
        if self.countdown > 0:
            before = math.ceil(self.countdown)
            self.countdown -= dt
            if self.countdown <= 0:
                self.ev('snd', 'go')
            elif math.ceil(self.countdown) != before:
                self.ev('snd', 'count')
            return
        self.time += dt
        for d in (self.cdp, self.cdz):
            for k in d:
                d[k] = max(0.0, d[k] - dt)
        self._economy(dt)
        self._script()
        self._buffs(dt)
        self._plants(dt)
        self._zombies(dt)
        self._projs(dt)
        self._barrels(dt)
        self._mowers(dt)
        self._lights(dt)
        self._rain(dt)
        self._cleanup()
        self._check_end()

    def _economy(self, dt):
        if self.kind == 'pvp':
            self.zloba += (10 + 3 * self.time / 60) * self.mult * dt
        if self.sky and self.kind != 'puzzle':
            self.sky_t -= dt * self.mult
            if self.sky_t <= 0:
                self.sky_t = self.rng.uniform(8.5, 11.5)
                self.spawn_light(self.rng.uniform(BX + 30, BOARD_R - 30), BY - 30,
                                 self.rng.uniform(BY + 40, BY + LANES * CH - 30), 25, True)
        if self.beam_times and self.time >= self.beam_times[0]:
            self.beam_times.pop(0)
            self.hope_beam()
        if self.beam:
            self.beam[1] -= dt
            if self.beam[1] <= 0:
                self.beam = None

    def _script(self):
        if self.kind == 'endless' and self.si >= len(self.script) and self.hostile_count() == 0:
            self.endless_wave()
        while self.si < len(self.script) and self.time >= self.script[self.si][0]:
            t, kind, p = self.script[self.si]
            self.si += 1
            if kind == 'z':
                self.spawn_z(p)
                self.spawned += 1
            elif kind == 'boss':
                self.spawn_z('boss', 2)
                self.spawned += 1
                self.ev('msg', "KOMBAJN VJÍŽDÍ DO SEKTORU", 'warn')
            elif kind == 'flag':
                self.ev('snd', 'wave')
                self.ev('msg', p, 'warn')

    def _buffs(self, dt):
        for z in self.zombies:
            z.buff = False
        for c in self.zombies:
            if c.k != 'kaz' or not c.hostile():
                continue
            c.t1 -= dt
            heal = c.t1 <= 0
            if heal:
                c.t1 = 6.0
                self.ev('fx', 'ring', c.x, lane_cy(c.lane) - 30)
            for z in self.zombies:
                if z is not c and z.hostile() and z.k != 'boss' and abs(z.lane - c.lane) <= 1 and abs(z.x - c.x) < 140:
                    z.buff = True
                    if heal:
                        z.hp = min(z.mhp, z.hp + 30)
        self.aura = set()
        for p in self.plants():
            if p.k == 'pamp':
                for dl in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dl or dc:
                            self.aura.add((p.lane + dl, p.col + dc))

    def _plants(self, dt):
        for lane in range(LANES):
            for col in range(COLS):
                p = self.grid[lane][col]
                if not p:
                    continue
                if p.hp <= 0:
                    self.kill_plant(p)
                    continue
                rate = 1.25 if (lane, col) in self.aura else 1.0
                p.st = max(0.0, p.st - dt)
                k, cx, cy = p.k, p.cx, lane_cy(lane)
                if k == 'lampa':
                    if self.kind == 'puzzle':
                        continue
                    p.t -= dt * rate * self.mult
                    if p.t <= 0:
                        p.t = self.lamp_period
                        p.st = 0.6
                        self.spawn_light(cx + self.rng.uniform(-18, 18), cy - 10, cy + 22, 25, False)
                elif k in ('trn', 'jed', 'pamp'):
                    p.t -= dt * rate
                    if p.t <= 0:
                        if self.enemy_ahead(lane, cx):
                            d = PLANTS[k]
                            p.t = d['rate']
                            p.st = 0.18
                            self.projs.append(Proj(k, lane, cx + 24, d['dmg']))
                            self.ev('snd', 'shoot' if k == 'trn' else 'spit')
                        else:
                            p.t = 0.0
                elif k == 'mina':
                    if p.t > 0:
                        p.t -= dt
                        if p.t <= 0:
                            self.ev('snd', 'arm')
                    else:
                        for z in self.zombies:
                            if z.hostile() and lane in z.lanes and not z.airborne() and abs(z.front() - cx) < 40:
                                self.explode(p, cx, lane)
                                break
                elif k == 'maso':
                    if p.t > 0:
                        p.t -= dt
                    else:
                        best = None
                        for z in self.zombies:
                            if z.hostile() and lane in z.lanes and not z.airborne() and -10 <= z.front() - cx <= 105:
                                if best is None or z.x < best.x:
                                    best = z
                        if best:
                            if best.k in ('exe', 'boss'):
                                self.hurt(best, 400)
                            else:
                                best.hp = 0
                                best.silent = True
                                self.ev('fx', 'gulp', best.x, cy)
                            p.t = PLANTS['maso']['chew']
                            p.st = 0.3
                            self.ev('snd', 'chomp')
                elif k == 'ostruz':
                    p.t -= dt
                    if p.t <= 0:
                        p.t = 1.0
                        hit = False
                        for z in self.zombies:
                            if z.hostile() and lane in z.lanes and not z.airborne() and z.k != 'boss' and abs(z.x - cx) < CW * 0.55:
                                self.hurt(z, PLANTS['ostruz']['dmg'])
                                hit = True
                        if hit:
                            p.st = 0.2

    def explode(self, p, cx, lane):
        for z in self.zombies:
            if z.hostile() and lane in z.lanes and abs(z.front() - cx) < 80:
                self.hurt(z, PLANTS['mina']['dmg'])
        self.grid[p.lane][p.col] = None
        self.ev('snd', 'explode')
        self.ev('fx', 'boom', cx, lane_cy(lane))
        self.ev('shake', 0.35)

    def plant_at_front(self, z):
        f = z.front()
        for col in range(COLS - 1, -1, -1):
            p = self.grid[z.lane][col]
            if not p:
                continue
            if p.k == 'ostruz' and z.k != 'exe':
                continue
            if p.k == 'mina' and p.t <= 0:
                continue
            if 0 <= f - p.cx <= 44:
                return p
        return None

    def _chomp(self, z):
        if z.snd_t <= 0:
            z.snd_t = 0.45
            self.ev('snd', 'chomp')

    def _zombies(self, dt):
        for z in list(self.zombies):
            if z.hp <= 0:
                continue
            z.anim += dt
            z.snd_t -= dt
            z.hurt = max(0.0, z.hurt - dt)
            z.eating = False
            z.spray = False
            if z.k == 'boss':
                self._boss(z, dt)
                continue
            slowk = 0.5 if z.slow > 0 else 1.0
            z.slow = max(0.0, z.slow - dt)
            if z.awake:
                self._awake(z, dt)
                continue
            spd = z.speed * slowk * (1.4 if z.buff else 1.0)
            bite = z.bite * slowk * (1.2 if z.buff else 1.0)
            if z.jump_t > 0:
                z.jump_t -= dt
                f = 1 - max(0.0, z.jump_t) / 0.7
                z.x = z.jump_from - f * CW * 1.2
                if z.jump_t <= 0:
                    z.jump_t = 0.0
                    z.jumped = True
                    z.speed = 18
                continue
            foe = None
            for a in self.zombies:
                if a.awake and a.hp > 0 and a.lane == z.lane and 0 <= z.x - a.x <= 42:
                    foe = a
                    break
            if foe:
                z.eating = True
                foe.hp -= bite * dt
                self._chomp(z)
                continue
            if z.k == 'post':
                tgt = None
                for col in range(COLS):
                    p = self.grid[z.lane][col]
                    if p and p.k != 'ostruz' and p.cx < z.x and z.x - p.cx <= 170:
                        if tgt is None or p.cx > tgt.cx:
                            tgt = p
                if tgt:
                    z.spray = True
                    tgt.hp -= 35 * dt * slowk
                    if z.snd_t <= 0:
                        z.snd_t = 0.5
                        self.ev('snd', 'spray')
                    if tgt.hp <= 0:
                        self.kill_plant(tgt)
                    continue
            p = self.plant_at_front(z)
            if p:
                if z.k == 'dron' and not z.jumped:
                    z.jump_t = 0.7
                    z.jump_from = z.x
                    self.ev('snd', 'jump')
                    continue
                if z.k == 'exe':
                    z.wind += dt * slowk
                    if z.wind >= 1.1:
                        z.wind = 0.0
                        self.grid[p.lane][p.col] = None
                        self.ev('snd', 'smash')
                        self.ev('fx', 'smash', p.cx, lane_cy(p.lane))
                        self.ev('shake', 0.25)
                    continue
                z.eating = True
                p.hp -= bite * dt
                self._chomp(z)
                if p.hp <= 0:
                    self.kill_plant(p)
                continue
            z.wind = 0.0
            z.x -= spd * dt
            if z.k == 'exe' and not z.thrown and z.hp < z.mhp / 2:
                z.thrown = True
                nx = max(BX + CW * 0.8, z.x - 3 * CW)
                self.spawn_z('bez', z.lane, nx)
                self.ev('snd', 'throw')
                self.ev('fx', 'dust', nx, lane_cy(z.lane))
            if z.x < BX - 5:
                self._reach(z)

    def _reach(self, z):
        if self.kind == 'puzzle':
            if not self.seeds[z.lane]:
                self.seeds[z.lane] = True
                self.ev('msg', "Semínko zasazeno v řadě %d" % (z.lane + 1), 'hope')
                self.ev('snd', 'freed')
                self.ev('fx', 'bloom', BX - 60, lane_cy(z.lane))
            z.hp = 0
            z.silent = True
            return
        for l in z.lanes:
            if self.mowers[l] == 0:
                self.mowers[l] = BX - 30.0
                self.ev('snd', 'mower')
        if z.front() < HOUSE_X:
            self.result = 'Z'

    def _awake(self, z, dt):
        foe = None
        for h in self.zombies:
            if h.hostile() and h.k != 'boss' and h.lane == z.lane and 0 <= h.x - z.x <= 42 and not h.airborne():
                foe = h
                break
        if foe:
            z.eating = True
            self.hurt(foe, 60 * dt)
            self._chomp(z)
        else:
            z.x += 24 * dt
        if z.x > W + 30:
            z.hp = 0
            z.silent = True
            self.freed += 1
            if self.kind != 'puzzle':
                self.light += 50
            self.ev('snd', 'freed')
            self.ev('msg', "Probuzený odešel hledat svou rodinu. +50 světla", 'hope')

    def try_awaken(self, z):
        if z.k not in AWAKENABLE or z.buff or z.hp <= 0 or z.shield > 0:
            return
        if z.hp < 0.6 * z.mhp and self.rng.random() < 0.25:
            z.awake = True
            z.slow = 0.0
            z.eating = False
            self.awakened += 1
            self.ev('snd', 'awaken')
            self.ev('fx', 'awaken', z.x, lane_cy(z.lane) - 30)
            if self.awakened in (1, 5, 10, 20):
                self.ev('msg', "ASIMILOVANÝ SE PROBUDIL!", 'hope')

    def _boss(self, z, dt):
        z.x -= z.speed * dt * (1.3 if z.enraged else 1.0)
        f = z.front()
        for l in z.lanes:
            for col in range(COLS):
                p = self.grid[l][col]
                if p and abs(f - p.cx) < 40:
                    self.grid[l][col] = None
                    self.ev('snd', 'smash')
                    self.ev('fx', 'smash', p.cx, lane_cy(l))
            for a in self.zombies:
                if a.awake and a.hp > 0 and a.lane == l and abs(a.x - f) < 30:
                    a.hp = 0
        if not z.enraged and z.hp < z.mhp / 2:
            z.enraged = True
            self.ev('snd', 'roar')
            self.ev('msg', "KOMBAJN PŘEŠEL DO REŽIMU SKLIZNĚ", 'warn')
            self.ev('shake', 0.5)
        z.t1 -= dt
        if z.t1 <= 0:
            z.t1 = 6.0 if z.enraged else 9.0
            targets = list(self.plants())
            if targets:
                p = self.rng.choice(targets)
                self.barrels.append({'x0': z.x - 20, 'y0': lane_cy(1) - 60, 'x1': p.cx, 'y1': lane_cy(p.lane),
                                     't': 0.0, 'T': 1.4, 'lane': p.lane, 'col': p.col})
                self.ev('snd', 'throw')
        z.t2 -= dt
        if z.t2 <= 0:
            z.t2 = 10.0 if z.enraged else 15.0
            for _ in range(3 if z.enraged else 2):
                self.spawn_z(self.rng.choice(['zak', 'zak', 'bez', 'doz']))
        if f < BX - 5:
            self._reach(z)

    def _projs(self, dt):
        for pr in self.projs:
            pr.x += PROJ_SPD[pr.k] * dt
            hit = None
            for z in self.zombies:
                if not z.hostile() or pr.lane not in z.lanes or z.airborne():
                    continue
                if z.k == 'boss':
                    if pr.x >= z.front():
                        hit = z
                        break
                elif abs(z.x - pr.x) < 20:
                    if hit is None or z.x < hit.x:
                        hit = z
            if hit:
                pr.alive = False
                self.hurt(hit, pr.dmg, proj=True)
                if pr.k == 'jed':
                    hit.slow = 3.0
                elif pr.k == 'pamp':
                    self.try_awaken(hit)
                self.ev('fx', 'hit', pr.x, lane_cy(pr.lane) - 30, pr.k)
                self.ev('snd', 'hit')
            elif pr.x > W + 10:
                pr.alive = False
        self.projs = [p for p in self.projs if p.alive]

    def _barrels(self, dt):
        keep = []
        for b in self.barrels:
            b['t'] += dt
            if b['t'] >= b['T']:
                p = self.grid[b['lane']][b['col']]
                if p:
                    p.hp -= 600
                    if p.hp <= 0:
                        self.kill_plant(p, 'smash')
                self.ev('snd', 'explode')
                self.ev('fx', 'boom', b['x1'], b['y1'])
                self.ev('shake', 0.2)
            else:
                keep.append(b)
        self.barrels = keep

    def _mowers(self, dt):
        for l in range(LANES):
            m = self.mowers[l]
            if m <= 0:
                continue
            m += 430 * dt
            for z in self.zombies:
                if not z.hostile() or l not in z.lanes:
                    continue
                if z.k == 'boss':
                    if m >= z.front() - 20:
                        self.hurt(z, 800)
                        self.ev('snd', 'explode')
                        self.ev('fx', 'boom', m, lane_cy(l))
                        m = -1.0
                        break
                elif abs(z.x - m) < 40 and not z.airborne():
                    z.hp = 0
                    self.ev('fx', 'burn', z.x, lane_cy(l))
            if m > W + 40:
                m = -1.0
            self.mowers[l] = m

    def _lights(self, dt):
        for L in self.lights:
            if not L['land']:
                if L['fall']:
                    L['y'] += 75 * dt
                else:
                    L['vy'] += 320 * dt
                    L['y'] += L['vy'] * dt
                if L['y'] >= L['ty'] and (L['fall'] or L['vy'] > 0):
                    L['y'] = L['ty']
                    L['land'] = True
            else:
                L['ttl'] -= dt
        self.lights = [L for L in self.lights if L['ttl'] > 0]

    def _rain(self, dt):
        if not self.rain_on:
            return
        if self.rain > 0:
            self.rain -= dt
            for p in list(self.plants()):
                p.hp -= 7 * dt
                if p.hp <= 0:
                    self.kill_plant(p)
            for z in self.zombies:
                if z.hostile():
                    self.hurt(z, 7 * dt)
            if self.rain <= 0:
                self.rain_t = 25.0
        else:
            self.rain_t -= dt
            if self.rain_t <= 0:
                self.rain = 6.0
                self.ev('snd', 'rain')
                self.ev('msg', "KYSELÝ DÉŠŤ", 'warn')

    def _cleanup(self):
        alive = []
        for z in self.zombies:
            if z.hp <= 0:
                if not z.silent:
                    self.ev('snd', 'die')
                    self.ev('fx', 'die', z.x, lane_cy(z.lane), z.k, 1 if z.awake else 0)
                if z.k == 'boss':
                    self.ev('fx', 'bigboom', z.x, lane_cy(2))
                    self.ev('snd', 'explode')
                    self.ev('shake', 0.9)
                    self.ev('msg', "KOMBAJN JE NA ŠROT", 'hope')
            else:
                alive.append(z)
        self.zombies = alive

    def _check_end(self):
        if self.result:
            pass
        elif self.kind == 'pvp' and self.time >= self.duration:
            self.result = 'P'
        elif self.kind == 'sp' and self.si >= len(self.script) and self.hostile_count() == 0:
            self.result = 'P'
        elif self.kind == 'puzzle':
            if all(self.seeds):
                self.result = 'Z'
            elif self.hostile_count() == 0 and self.zloba < min(ZOMBIES[k]['cost'] for k in self.zomb_list):
                self.result = 'P'
        if self.result:
            self.ev('end', self.result)

    # ------------------------------------------------------------ export pro vykreslení / síť
    def snapshot(self):
        pl = []
        for row in self.grid:
            for p in row:
                if p:
                    pl.append([p.k, p.lane, p.col, round(p.hp), p.mhp, round(p.t, 2), round(p.st, 2)])
        zs = [[z.id, z.k, z.lane, round(z.x, 1), round(z.hp), z.mhp, round(z.shield), z.mshield,
               z.flags(), round(z.anim, 2), round(z.jump_y(), 1), round(z.wind, 2)]
              for z in self.zombies if z.hp > 0]
        pr = [[p.k, p.lane, round(p.x, 1)] for p in self.projs]
        li = [[L['id'], round(L['x']), round(L['y']), round(L['ttl'], 1)] for L in self.lights]
        ba = []
        for b in self.barrels:
            f = b['t'] / b['T']
            ba.append([round(b['x0'] + (b['x1'] - b['x0']) * f),
                       round(b['y0'] + (b['y1'] - b['y0']) * f - math.sin(math.pi * f) * 170), round(f * 8, 2)])
        prog = 0.0
        if self.kind == 'sp' and self.total_z:
            prog = self.spawned / self.total_z
        lk = {}
        if self.kind == 'pvp':
            for k in self.zomb_list:
                lock = max(PVP_GRACE, self.exe_lock) if k == 'exe' else PVP_GRACE
                if self.time < lock:
                    lk[k] = int(lock - self.time) + 1
        return {
            't': round(self.time, 2), 'cd': round(self.countdown, 2), 'pl': pl, 'z': zs, 'pr': pr, 'li': li,
            'ba': ba, 'mw': [round(m) for m in self.mowers], 'sd': self.seeds[:],
            'L': int(self.light), 'Z': int(self.zloba), 'pk': self.plant_list, 'zk': self.zomb_list,
            'cp': {k: round(self.cdp.get(k, 0) / PLANTS[k]['cd'], 3) for k in self.plant_list},
            'cz': {k: round(self.cdz.get(k, 0) / max(0.1, self.zcd[k]), 3) for k in self.zomb_list},
            'lk': lk, 'res': self.result, 'kind': self.kind, 'lvl': self.level, 'mode': self.pvp_mode,
            'dark': self.dark, 'rain': self.rain > 0, 'beam': self.beam, 'prog': round(prog, 3),
            'wave': self.wave, 'dur': self.duration, 'aw': self.awakened, 'fr': self.freed,
        }


# ================================================================ ULOŽENÍ
def load_save():
    d = {'done': [False] * 5, 'secret': False, 'endless': 0, 'puzzle': False}
    try:
        with open(SAVE_FILE, encoding='utf-8') as f:
            d.update(json.load(f))
    except (OSError, ValueError):
        pass
    d['done'] = (list(d.get('done', [])) + [False] * 5)[:5]
    return d


def write_save(d):
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print("Nelze uložit postup:", e)


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


def sfx_shoot():
    b = newbuf(0.09)
    tone(b, 0, 0.07, 0, kind='noise', vol=0.22, curve=2, lp=0.5)
    tone(b, 0, 0.06, 620, 260, 'sq', 0.07, duty=0.25, curve=1.5)
    return b


def sfx_spit():
    b = newbuf(0.15)
    tone(b, 0, 0.12, 300, 120, 'sin', 0.3, curve=1.2)
    tone(b, 0, 0.1, 0, kind='noise', vol=0.12, curve=2, lp=0.25)
    return b


def sfx_hit():
    b = newbuf(0.12)
    tone(b, 0, 0.1, 0, kind='noise', vol=0.3, curve=2.5, lp=0.3)
    tone(b, 0, 0.08, 200, 80, 'tri', 0.3, curve=2)
    return b


def sfx_clank():
    b = newbuf(0.18)
    tone(b, 0, 0.15, 1250, kind='sq', vol=0.07, duty=0.3, curve=2)
    tone(b, 0, 0.15, 1870, kind='sq', vol=0.05, duty=0.4, curve=2.5)
    return b


def sfx_shieldbreak():
    b = newbuf(0.5)
    tone(b, 0, 0.4, 0, kind='noise', vol=0.35, curve=1.5, lp=0.6)
    tone(b, 0, 0.35, 1400, 500, 'sq', 0.08, duty=0.3, curve=1.2)
    return b


def sfx_chomp():
    b = newbuf(0.22)
    for i in range(2):
        tone(b, i * 0.1, 0.07, 0, kind='noise', vol=0.3, curve=1.5, lp=0.35)
        tone(b, i * 0.1, 0.06, 140, 90, 'tri', 0.3, curve=1.5)
    return b


def sfx_plant():
    b = newbuf(0.2)
    tone(b, 0, 0.16, 170, 60, 'tri', 0.5, curve=1.8)
    tone(b, 0, 0.12, 0, kind='noise', vol=0.22, curve=2, lp=0.2)
    return b


def sfx_collect():
    return _arp([nf('E6'), nf('G6'), nf('B6')], 0.04, 0.14, kind='sin', vol=0.28)


def sfx_groan():
    b = newbuf(1.0)
    tone(b, 0, 0.9, 115, 88, 'saw', 0.14, curve=0.6, vib=0.04, lp=0.12, attack=0.12)
    tone(b, 0, 0.9, 117, 86, 'sq', 0.05, duty=0.3, curve=0.6, vib=0.05, lp=0.1, attack=0.15)
    return b


def sfx_explode():
    b = newbuf(1.0)
    tone(b, 0, 0.9, 0, kind='noise', vol=0.6, curve=1.3, lp=0.12)
    tone(b, 0, 0.5, 90, 28, 'sin', 0.7, curve=1.2)
    return b


def sfx_mower():
    b = newbuf(1.3)
    tone(b, 0, 1.2, 0, kind='noise', vol=0.35, curve=0.5, lp=0.4, attack=0.05)
    tone(b, 0, 1.2, 55, 70, 'saw', 0.12, curve=0.5, lp=0.2)
    return b


def sfx_wave():
    b = newbuf(2.0)
    tone(b, 0, 0.9, 380, 720, 'saw', 0.12, curve=0, lp=0.3, attack=0.05)
    tone(b, 0.9, 0.9, 720, 380, 'saw', 0.12, curve=0.4, lp=0.3)
    return b


def sfx_win():
    b = newbuf(2.4)
    for i, ch in enumerate((['C4', 'E4', 'G4'], ['F4', 'A4', 'C5'], ['G4', 'C5', 'E5'])):
        for n in ch:
            tone(b, i * 0.55, 0.9 if i < 2 else 1.6, nf(n), kind='sin', vol=0.12, curve=1, attack=0.03)
    for i, n in enumerate(['C5', 'E5', 'G5', 'C6', 'E6']):
        tone(b, 1.1 + i * 0.09, 0.3, nf(n), kind='tri', vol=0.14, curve=1.2)
    return b


def sfx_lose():
    b = _arp([nf(n) for n in ['E4', 'D#4', 'D4', 'C#4']], 0.22, 0.35, kind='saw', vol=0.18, total=1.8)
    tone(b, 0, 1.7, 55, 50, 'saw', 0.1, curve=0.8, lp=0.1)
    return b


def sfx_select():
    b = newbuf(0.13)
    tone(b, 0, 0.05, 660, kind='sq', vol=0.12, duty=0.25, curve=0.5)
    tone(b, 0.05, 0.07, 990, kind='sq', vol=0.12, duty=0.25, curve=1)
    return b


def sfx_tick():
    b = newbuf(0.03)
    tone(b, 0, 0.02, 900, kind='sq', vol=0.07, curve=1)
    return b


def sfx_count():
    b = newbuf(0.2)
    tone(b, 0, 0.15, 440, kind='sq', vol=0.16, duty=0.5, curve=0.8)
    return b


def sfx_go():
    b = newbuf(0.45)
    tone(b, 0, 0.4, 880, kind='sq', vol=0.16, duty=0.5, curve=1)
    tone(b, 0, 0.4, 440, kind='saw', vol=0.1, curve=1)
    return b


def sfx_awaken():
    b = newbuf(1.2)
    for i, n in enumerate(['C5', 'D5', 'E5', 'G5', 'A5', 'C6']):
        tone(b, i * 0.08, 0.5, nf(n), kind='sin', vol=0.14, curve=1.2, vib=0.01)
    tone(b, 0, 1.0, 0, kind='noise', vol=0.04, curve=1, lp=0.9, attack=0.2)
    return b


def sfx_spray():
    b = newbuf(0.4)
    tone(b, 0, 0.35, 0, kind='noise', vol=0.16, curve=0.8, lp=0.9, attack=0.03)
    return b


def sfx_smash():
    b = newbuf(0.6)
    tone(b, 0, 0.5, 0, kind='noise', vol=0.5, curve=2, lp=0.2)
    tone(b, 0, 0.35, 70, 35, 'sin', 0.7, curve=1.5)
    tone(b, 0, 0.05, 900, kind='sq', vol=0.1, curve=1)
    return b


def sfx_roar():
    b = newbuf(1.6)
    tone(b, 0, 1.5, 80, 48, 'saw', 0.3, curve=0.6, vib=0.06, lp=0.15, attack=0.1)
    tone(b, 0, 1.5, 0, kind='noise', vol=0.2, curve=0.8, lp=0.1)
    return b


def sfx_bird():
    b = newbuf(0.7)
    for i, (a, c) in enumerate(((2600, 3400), (2900, 3600), (2500, 3100))):
        tone(b, i * 0.18, 0.1, a, c, 'sin', 0.14, curve=0.8)
    return b


def sfx_freed():
    b = newbuf(1.4)
    for n in ('C5', 'E5', 'G5'):
        tone(b, 0, 1.3, nf(n), kind='sin', vol=0.1, curve=1, attack=0.08)
    tone(b, 0.3, 0.8, nf('C6'), kind='tri', vol=0.08, curve=1.2)
    return b


def sfx_jump():
    b = newbuf(0.4)
    tone(b, 0, 0.35, 250, 900, 'sq', 0.07, duty=0.25, curve=0.5)
    tone(b, 0, 0.3, 0, kind='noise', vol=0.1, curve=1, lp=0.6)
    return b


def sfx_throw():
    b = newbuf(0.4)
    tone(b, 0, 0.35, 200, 520, 'saw', 0.1, curve=0.8, lp=0.4)
    return b


def sfx_beam():
    b = newbuf(2.6)
    for n in ('C4', 'G4', 'E5'):
        tone(b, 0, 2.5, nf(n), kind='sin', vol=0.12, curve=0, attack=0.5, rel=0.9, vib=0.004)
    for i, n in enumerate(['G5', 'C6', 'E6', 'G6']):
        tone(b, 0.6 + i * 0.25, 0.5, nf(n), kind='sin', vol=0.06, curve=1)
    return b


def sfx_unlock():
    return _arp([nf(n) for n in ['C5', 'E5', 'G5', 'C6', 'G5', 'C6']], 0.09, 0.2, kind='tri', vol=0.25)


def sfx_arm():
    b = newbuf(0.2)
    tone(b, 0, 0.08, 600, kind='sq', vol=0.08, duty=0.25)
    tone(b, 0.09, 0.08, 900, kind='sq', vol=0.08, duty=0.25)
    return b


def sfx_plantdie():
    b = newbuf(0.3)
    tone(b, 0, 0.25, 0, kind='noise', vol=0.22, curve=1.5, lp=0.5)
    tone(b, 0, 0.2, 300, 150, 'tri', 0.15, curve=1)
    return b


def sfx_die():
    b = newbuf(0.5)
    tone(b, 0, 0.45, 140, 60, 'saw', 0.16, curve=1, lp=0.2, vib=0.05)
    tone(b, 0, 0.2, 0, kind='noise', vol=0.3, curve=2, lp=0.3)
    return b


def sfx_rain():
    b = newbuf(2.0)
    tone(b, 0, 1.9, 0, kind='noise', vol=0.18, curve=0, lp=0.7, attack=0.4, rel=0.5)
    return b


SFX = {
    "shoot": sfx_shoot, "spit": sfx_spit, "hit": sfx_hit, "clank": sfx_clank, "shieldbreak": sfx_shieldbreak,
    "chomp": sfx_chomp, "plant": sfx_plant, "collect": sfx_collect, "groan": sfx_groan,
    "explode": sfx_explode, "mower": sfx_mower, "wave": sfx_wave, "win": sfx_win, "lose": sfx_lose,
    "select": sfx_select, "tick": sfx_tick, "count": sfx_count, "go": sfx_go, "awaken": sfx_awaken,
    "spray": sfx_spray, "smash": sfx_smash, "roar": sfx_roar, "bird": sfx_bird, "freed": sfx_freed,
    "jump": sfx_jump, "throw": sfx_throw, "beam": sfx_beam, "unlock": sfx_unlock, "arm": sfx_arm,
    "plantdie": sfx_plantdie, "die": sfx_die, "rain": sfx_rain,
}


def gen_music():
    """Vlastní skladba: temný průmyslový motiv, uprostřed mezihra naděje."""
    bpm = 100
    bt = 60 / bpm
    A = [('A4', 1), ('C5', .5), ('E5', .5), ('D5', 1), ('C5', 1),
         ('B4', 1.5), ('G4', .5), ('A4', 2),
         ('E5', 1), ('F5', .5), ('E5', .5), ('D5', 1), ('B4', 1),
         ('C5', 2), (None, 1), ('E4', 1),
         ('A4', 1), ('C5', .5), ('E5', .5), ('A5', 1), ('G5', 1),
         ('F5', 1), ('E5', .5), ('D5', .5), ('E5', 2),
         ('D5', 1), ('C5', 1), ('B4', 1), ('G#4', 1),
         ('A4', 3), (None, 1)]
    HOPEM = [('A4', 1), ('C5', 1), ('F5', 2),
             ('E5', 1), ('D5', .5), ('C5', .5), ('G5', 2),
             ('G5', 1), ('A5', .5), ('G5', .5), ('D5', 1), ('B4', 1),
             ('C5', 2), ('E5', 2)]
    C = A[:15]
    bass = ['A2', 'E2', 'D2', 'A2', 'A2', 'F2', 'E2', 'A2', 'F2', 'C3', 'G2', 'A2', 'A2', 'E2', 'D2', 'E2']
    pads = [['F3', 'A3', 'C4'], ['C3', 'E3', 'G3'], ['G3', 'B3', 'D4'], ['A3', 'C4', 'E4']]
    total = 64
    buf = newbuf(total * bt + 0.2)
    lead = newbuf(total * bt + 0.2)

    def melody(seq, sb, kind, vol, duty, oct_k=1.0):
        b = sb
        for n, d in seq:
            if n:
                tone(lead, b * bt, d * bt * 0.9, nf(n) * oct_k, kind=kind, vol=vol, duty=duty, curve=0.7, vib=0.006)
            b += d

    melody(A, 0, 'sq', 0.11, 0.25)
    melody(HOPEM, 32, 'tri', 0.26, 0.5)
    melody(C, 48, 'sq', 0.09, 0.125, 0.5)
    dl = int(0.5 * bt * SR)
    for i in range(len(lead) - 1, dl - 1, -1):
        lead[i] += lead[i - dl] * 0.3
    for i in range(len(buf)):
        buf[i] += lead[i]
    for bar, root in enumerate(bass):
        f = nf(root)
        if 8 <= bar < 12:
            tone(buf, bar * 4 * bt, 3.9 * bt, f, kind='tri', vol=0.22, curve=0.4, attack=0.05)
            for n in pads[bar - 8]:
                tone(buf, bar * 4 * bt, 3.9 * bt, nf(n), kind='sin', vol=0.05, curve=0.2, attack=0.3, rel=0.3)
        else:
            for e in range(8):
                tone(buf, (bar * 4 + e * 0.5) * bt, 0.4 * bt, f * (1.5 if e == 6 else 1), kind='saw',
                     vol=0.12, curve=1.4, lp=0.25)
    for beat in range(total):
        s = beat * bt
        if 32 <= beat < 48:
            if beat % 4 == 0:
                tone(buf, s, 0.3, 90, 40, 'sin', 0.35, curve=1.2)
            continue
        if beat % 2 == 0:
            tone(buf, s, 0.16, 120, 36, 'sin', 0.6, curve=1.5)
        else:
            tone(buf, s, 0.12, 0, kind='noise', vol=0.22, curve=2, lp=0.5)
            tone(buf, s, 0.05, 1800, kind='sq', vol=0.03, curve=2)
        tone(buf, s + bt / 2, 0.03, 0, kind='noise', vol=0.06, curve=2)
    return buf


class Sound:
    def __init__(self):
        self.ok = False
        self.sfx = {}
        self.last = {}
        self.music_path = None
        self.music_on = True
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(24)
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
                progress(i / (len(items) + 6), "Ladím hlasy asimilovaných: " + name)
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
                progress(len(items) / (len(items) + 6), "Skládám hymnu skleníku… (jen při prvním spuštění)")
            path = os.path.join(SND_DIR, "music.wav")
            try:
                write_wav(path, gen_music())
            except OSError:
                path = None
        self.music_path = path
        if progress:
            progress(1.0, "Hotovo.")

    def play(self, name, vol=1.0):
        if not self.ok or name not in self.sfx:
            return
        now = time.time()
        if now - self.last.get(name, 0) < 0.05:
            return
        self.last[name] = now
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
                    pygame.mixer.music.set_volume(0.35)
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
        msg = ("ZAHON|%d|%s" % (PROTO, self.name)).encode("utf-8")
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
        self.hosts = {}
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
                    if tag == "ZAHON":
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


# ================================================================ GRAFIKA — pomocné
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


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


MENU = ["PŘÍBĚH SKLENÍKU", "LAN: ZALOŽIT HRU", "LAN: PŘIPOJIT SE", "ATLAS", "OPUSTIT SKLENÍK"]
MAP_NODES = [('lvl', 0), ('lvl', 1), ('lvl', 2), ('lvl', 3), ('lvl', 4), ('secret', 0), ('endless', 0)]
SECRET_CODE = "SEMINKO"


# ================================================================ APLIKACE
class App:
    def __init__(self, screen, sound):
        self.screen = screen
        self.canvas = pygame.Surface((W, H))
        self.snd = sound
        self.f_huge = _font(88, True)
        self.f_big = _font(44, True)
        self.f_med = _font(26, True)
        self.f_norm = _font(18)
        self.f_normb = _font(18, True)
        self.f_small = _font(15)
        self.f_smallb = _font(15, True)
        self.f_tiny = _font(12)
        self.save = load_save()
        self.name = self._os_user()
        self.state = "menu"
        self.menu_i = 0
        self.map_i = 0
        self.t = 0.0
        self.quit = False
        self.world = None
        self.snap = None
        self.snap_age = 0.0
        self.side = 'P'
        self.sel = None
        self.particles = []
        self.decals = []
        self.banner = None
        self.shake = 0.0
        self.birds = []
        self.zdisp = {}
        self.paused = False
        self.code_buf = ""
        self.ticker_x = 0.0
        self.ticker_img = self.f_small.render("   ///   ".join(SLOGANY) + "   ///   ", True, AMBER)
        self.net = None
        self.host = None
        self.disc = None
        self.join_ip = ""
        self.join_i = 0
        self.join_hosts = []
        self.join_status = ""
        self.connecting = False
        self.connect_result = None
        self.hs_i = 0
        self.hs_mode = 0
        self.hs_side = 0
        self.is_host = False
        self.opp_name = "?"
        self.pvp_mode = 'klasika'
        self.net_buf = []
        self.snap_t = 0.0
        self.pvp_phase = "play"
        self.story = None
        self.after_story = None
        self.result_info = None
        self.atlas_page = 0
        self.ending_t = 0.0
        self.flash = 0.0
        self._build_assets()

    @staticmethod
    def _os_user():
        try:
            return getpass.getuser()[:12].upper()
        except Exception:
            return "ZAHRADNÍK"

    # ---------------------------------------------------------- statické podklady
    def _build_assets(self):
        self.scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 3):
            pygame.draw.line(self.scan, (0, 0, 0, 35), (0, y), (W, y))
        v = pygame.Surface((64, 40), pygame.SRCALPHA)
        for y in range(40):
            for x in range(64):
                dx, dy = (x - 31.5) / 32, (y - 19.5) / 20
                d = math.sqrt(dx * dx + dy * dy)
                v.set_at((x, y), (0, 0, 0, int(max(0, min(200, (d - 0.65) * 360)))))
        self.vig = pygame.transform.smoothscale(v, (W, H))
        self.bg = self._build_bg()
        self.glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        for r in range(40, 0, -2):
            a = int(120 * (1 - r / 40) ** 1.5)
            pygame.draw.circle(self.glow, (255, 210, 80, a), (40, 40), r)
        self.stamps = {}
        for R in (170, 80, 45):
            s = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
            s.fill((0, 0, 0, 255))
            for r in range(R, 0, -3):
                a = int(235 * (r / R) ** 1.6)
                pygame.draw.circle(s, (0, 0, 0, a), (R, R), r)
            self.stamps[R] = s
        self.dark = pygame.Surface((W, LANES * CH + 20), pygame.SRCALPHA)
        self.beam_s = pygame.Surface((140, BY + LANES * CH), pygame.SRCALPHA)
        for x in range(140):
            k = 1 - abs(x - 70) / 70
            pygame.draw.line(self.beam_s, (255, 230, 150, int(90 * k ** 2)), (x, 0), (x, BY + LANES * CH))
        self.dimpk = pygame.Surface((PK_W, PK_H), pygame.SRCALPHA)
        self.dimpk.fill((0, 0, 0, 150))
        self.stamp_txt = _font(10, True).render("ZAMÍTNUTO", True, (230, 60, 50))
        self.boss_txt = _font(13, True).render("MINISTERSTVO SKLIZNĚ", True, (240, 200, 60))

    def _build_bg(self):
        s = pygame.Surface((W, H))
        s.fill(BG)
        for y in range(BY):
            pygame.draw.line(s, mix((24, 20, 16), (58, 48, 32), y / BY), (0, y), (W, y))
        r = random.Random(5)
        x = 0
        while x < W:
            w, h = r.randint(30, 80), r.randint(25, 80)
            pygame.draw.rect(s, (22, 22, 20), (x, BY - h, w, h))
            for _ in range(r.randint(0, 3)):
                pygame.draw.rect(s, (90, 70, 20), (x + r.randint(4, w - 8), BY - h + r.randint(4, h - 6), 3, 4))
            if r.random() < 0.3:
                pygame.draw.line(s, (22, 22, 20), (x + w // 2, BY - h), (x + w // 2 + r.randint(-8, 8), BY - h - 18), 2)
            x += w + r.randint(0, 12)
        pygame.draw.rect(s, (30, 28, 24), (0, BY + LANES * CH, W, H - BY - LANES * CH))
        for lane in range(LANES):
            for col in range(COLS):
                c = (44, 42, 34) if (lane + col) % 2 == 0 else (38, 36, 30)
                rr = pygame.Rect(BX + col * CW, BY + lane * CH, CW, CH)
                pygame.draw.rect(s, c, rr)
                for _ in range(3):
                    x0, y0 = rr.x + r.randint(5, CW - 5), rr.y + r.randint(5, CH - 5)
                    pygame.draw.line(s, (30, 28, 24), (x0, y0), (x0 + r.randint(-14, 14), y0 + r.randint(-10, 10)), 1)
                for _ in range(6):
                    pygame.draw.rect(s, (54, 50, 42), (rr.x + r.randint(0, CW - 3), rr.y + r.randint(0, CH - 3), 2, 2))
                if r.random() < 0.08:
                    pygame.draw.line(s, (60, 110, 50), (rr.x + 20, rr.bottom - 6), (rr.x + 24, rr.bottom - 16), 2)
        pygame.draw.rect(s, (24, 24, 22), (BOARD_R, BY, W - BOARD_R, LANES * CH))
        for y in range(BY, BY + LANES * CH, 14):
            pygame.draw.line(s, (70, 70, 64), (BOARD_R + 10, y), (BOARD_R + 16, y + 7), 1)
            pygame.draw.line(s, (70, 70, 64), (BOARD_R + 16, y + 7), (BOARD_R + 10, y + 14), 1)
        gx0, gx1 = 8, BX - 42
        pygame.draw.rect(s, (18, 26, 20), (gx0, BY - 10, gx1 - gx0, LANES * CH + 20))
        for l in range(LANES):
            y = lane_cy(l) + 25
            pygame.draw.rect(s, (52, 38, 26), (gx0 + 10, y, gx1 - gx0 - 20, 14))
            for i in range(5):
                xx = gx0 + 20 + i * 24
                pygame.draw.line(s, LEAF, (xx, y), (xx - 3, y - 14), 2)
                pygame.draw.ellipse(s, LEAF, (xx - 9, y - 18, 10, 6))
        for x in range(gx0, gx1 + 1, 36):
            pygame.draw.line(s, (90, 100, 96), (x, BY - 10), (x, BY + LANES * CH + 10), 2)
        pygame.draw.line(s, (90, 100, 96), (gx0, BY - 10), (gx1, BY - 40), 3)
        for i in range(8):
            px, py = r.randint(gx0, gx1 - 30), r.randint(BY, BY + LANES * CH - 40)
            pane = pygame.Surface((28, 36), pygame.SRCALPHA)
            pane.fill((140, 190, 200, 28))
            s.blit(pane, (px, py))
        return s

    # ---------------------------------------------------------- text
    def txt(self, s, font, color, pos, anchor="topleft", surf=None):
        img = font.render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        (surf or self.canvas).blit(img, r)
        return r

    def glitch_text(self, s, font, pos, color=TEXT, anchor="center", amt=3):
        j = amt + (random.randint(0, 8) if random.random() < 0.05 else 0)
        for off, col in (((-j, 0), (255, 0, 70)), ((j, 0), (0, 230, 150))):
            img = font.render(s, True, col)
            img.set_alpha(140)
            r = img.get_rect(**{anchor: (pos[0] + off[0], pos[1] + off[1])})
            self.canvas.blit(img, r)
        return self.txt(s, font, color, pos, anchor)

    def wrap(self, s, font, width):
        lines, cur = [], ""
        for w in s.split():
            t = (cur + " " + w).strip()
            if font.size(t)[0] <= width:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def panel(self, x, y, w, h, title=None, col=AMBER):
        pygame.draw.rect(self.canvas, PANEL, (x, y, w, h))
        pygame.draw.rect(self.canvas, EDGE, (x, y, w, h), 1)
        for cx, cy, dx, dy in ((x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1), (x + w - 1, y + h - 1, -1, -1)):
            pygame.draw.line(self.canvas, col, (cx, cy), (cx + 8 * dx, cy), 2)
            pygame.draw.line(self.canvas, col, (cx, cy), (cx, cy + 8 * dy), 2)
        if title:
            self.txt(title, self.f_tiny, col, (x + 10, y + 5))

    def header(self, subtitle="MINISTERSTVO ZEMĚDĚLSKÉ ASIMILACE // SEKTOR 7"):
        pygame.draw.rect(self.canvas, (14, 15, 14), (0, 0, W, 36))
        pygame.draw.line(self.canvas, EDGE, (0, 36), (W, 36))
        self.txt("ZÁHON", self.f_normb, ACID, (18, 9))
        self.txt(subtitle, self.f_small, DIM, (96, 11))

    def ticker(self):
        pygame.draw.rect(self.canvas, (14, 12, 6), (0, H - 28, W, 28))
        pygame.draw.line(self.canvas, (110, 76, 0), (0, H - 28), (W, H - 28))
        x = self.ticker_x
        while x < W:
            self.canvas.blit(self.ticker_img, (x, H - 22))
            x += self.ticker_img.get_width()

    # ---------------------------------------------------------- rostliny
    def draw_plant(self, c, k, cx, fy, t, hpr=1.0, pt=0.0, pst=0.0, s=1.0):
        def P(v):
            return int(round(v * s))
        cx, fy = int(cx), int(fy)
        sway = int(math.sin(t * 2 + cx * 0.05) * 2 * s)
        if k == 'ostruz':
            for i in range(5):
                x0 = cx - P(38) + P(i * 16)
                y1 = fy - P(12) - P((i % 2) * 7)
                pygame.draw.line(c, LEAF_D, (x0, fy - P(3)), (x0 + P(20), y1), max(1, P(4)))
                pygame.draw.line(c, (170, 190, 120), (x0 + P(10), fy - P(8)), (x0 + P(13), fy - P(14)), 1)
            for i in range(4):
                pygame.draw.circle(c, (150, 20, 50), (cx - P(28) + P(i * 18), fy - P(9) - P((i % 2) * 6)), max(1, P(4)))
            if pst > 0:
                pygame.draw.line(c, (220, 60, 60), (cx - P(36), fy - P(4)), (cx + P(36), fy - P(4)), 1)
            return
        if k == 'mina':
            pygame.draw.ellipse(c, (78, 58, 36), (cx - P(26), fy - P(14), P(52), P(20)))
            if pt <= 0:
                blink = int(t * 3) % 2
                pygame.draw.circle(c, WARN if blink else (140, 30, 20), (cx, fy - P(14)), max(2, P(8)))
                pygame.draw.circle(c, (255, 200, 180), (cx - P(2), fy - P(16)), max(1, P(2)))
                for dx in (-P(14), P(14)):
                    pygame.draw.line(c, (100, 70, 40), (cx, fy - P(8)), (cx + dx, fy), max(1, P(2)))
            else:
                pygame.draw.line(c, LEAF_D, (cx, fy - P(6)), (cx, fy - P(20)), max(1, P(3)))
                pygame.draw.ellipse(c, LEAF, (cx, fy - P(24), P(12), P(7)))
            return
        top = (cx + sway, fy - P(34))
        if k == 'parez':
            body = pygame.Rect(cx - P(27), fy - P(64), P(54), P(56))
            pygame.draw.rect(c, (104, 74, 46), body)
            for i in range(4):
                xx = body.x + P(8) + P(i * 12)
                pygame.draw.line(c, (80, 56, 34), (xx, body.y + P(6)), (xx, body.bottom), 1)
            pygame.draw.ellipse(c, (150, 112, 70), (body.x, body.y - P(8), body.w, P(16)))
            pygame.draw.ellipse(c, (120, 86, 52), (body.x + P(10), body.y - P(4), body.w - P(20), P(8)), 1)
            pygame.draw.rect(c, (110, 110, 104), (cx - P(33), fy - P(16), P(66), P(16)))
            pygame.draw.line(c, (150, 80, 40), (cx - P(20), fy - P(16)), (cx - P(26), fy - P(34)), max(1, P(2)))
            pygame.draw.line(c, (150, 80, 40), (cx + P(22), fy - P(16)), (cx + P(30), fy - P(30)), max(1, P(2)))
            if hpr < 0.66:
                pygame.draw.line(c, (40, 26, 16), (cx - P(10), body.y + P(4)), (cx - P(2), body.y + P(30)), max(1, P(2)))
            if hpr < 0.33:
                pygame.draw.line(c, (40, 26, 16), (cx + P(12), body.y + P(8)), (cx + P(4), body.bottom), max(1, P(2)))
            pygame.draw.line(c, LEAF, (cx + P(6), body.y - P(4)), (cx + P(10), body.y - P(16)), max(1, P(2)))
            pygame.draw.ellipse(c, LEAF, (cx + P(8), body.y - P(22), P(12), P(7)))
            return
        pygame.draw.line(c, LEAF_D, (cx, fy), top, max(2, P(5)))
        pygame.draw.ellipse(c, LEAF, (cx - P(24), fy - P(14), P(22), P(10)))
        pygame.draw.ellipse(c, LEAF, (cx + P(2), fy - P(16), P(22), P(10)))
        hx, hy = top
        if k == 'lampa':
            g = 0.5 + 0.5 * math.sin(t * 3 + cx)
            pygame.draw.circle(c, (70, 56, 14), (hx, hy - P(6)), P(24 + 3 * g))
            pygame.draw.circle(c, (255, 200, 60), (hx, hy - P(6)), P(15))
            pygame.draw.circle(c, (255, 244, 190), (hx, hy - P(6)), max(1, P(8 + 2 * g)))
            pygame.draw.circle(c, (90, 94, 90), (hx, hy - P(6)), P(19), max(1, P(2)))
            pygame.draw.line(c, (90, 94, 90), (hx, hy - P(25)), (hx, hy + P(13)), 1)
            pygame.draw.line(c, (90, 94, 90), (hx - P(19), hy - P(6)), (hx + P(19), hy - P(6)), 1)
            if pst > 0:
                for i in range(8):
                    a = i * math.pi / 4 + t
                    pygame.draw.line(c, HOPE, (hx + math.cos(a) * P(22), hy - P(6) + math.sin(a) * P(22)),
                                     (hx + math.cos(a) * P(34), hy - P(6) + math.sin(a) * P(34)), 2)
        elif k == 'trn':
            rx = hx - int(pst * 30 * s)
            pygame.draw.circle(c, (60, 150, 52), (rx, hy - P(4)), P(17))
            pygame.draw.rect(c, (40, 110, 40), (rx + P(8), hy - P(11), P(20), P(13)))
            pygame.draw.circle(c, (20, 50, 20), (rx + P(28), hy - P(5)), max(1, P(6)))
            for i in range(4):
                a = math.pi * (0.55 + 0.22 * i)
                bx, by = rx + math.cos(a) * P(16), hy - P(4) - math.sin(a) * P(16)
                ex, ey = rx + math.cos(a) * P(25), hy - P(4) - math.sin(a) * P(25)
                pygame.draw.line(c, (190, 200, 120), (bx, by), (ex, ey), max(1, P(2)))
            pygame.draw.circle(c, (230, 230, 210), (rx - P(2), hy - P(10)), max(1, P(4)))
            pygame.draw.circle(c, (10, 10, 10), (rx - P(1), hy - P(10)), max(1, P(2)))
        elif k == 'jed':
            pygame.draw.circle(c, (110, 50, 140), (hx, hy - P(4)), P(18))
            for dx, dy in ((-8, -12), (-10, 2), (2, -16)):
                pygame.draw.circle(c, (120, 200, 60), (hx + P(dx), hy + P(dy)), max(1, P(3)))
            pygame.draw.circle(c, (40, 10, 50), (hx + P(14), hy - P(2)), max(1, P(7 + pst * 20)))
            d = (t * 30 + cx) % 22
            pygame.draw.circle(c, (140, 220, 70), (hx + P(16), hy + P(4) + P(d)), max(1, P(3)))
        elif k == 'maso':
            head = (hx + P(4), hy - P(10))
            if pt > 0:
                bul = int(math.sin(t * 8) * P(3))
                pygame.draw.circle(c, (120, 36, 86), head, P(26) + bul)
                pygame.draw.circle(c, (100, 28, 70), (head[0] - P(6), head[1] + P(4)), P(12) - bul)
                pygame.draw.line(c, (60, 10, 30), (head[0] - P(10), head[1] - P(6)), (head[0] + P(24), head[1] - P(2)), 2)
            else:
                pygame.draw.circle(c, (130, 40, 90), head, P(24))
                pygame.draw.polygon(c, (70, 10, 30), [(head[0], head[1]), (head[0] + P(30), head[1] - P(16)),
                                                      (head[0] + P(30), head[1] + P(14))])
                for i in range(3):
                    yy = head[1] - P(12) + P(i * 5)
                    pygame.draw.polygon(c, (240, 236, 220), [(head[0] + P(14 + i * 5), yy), (head[0] + P(18 + i * 5), yy),
                                                             (head[0] + P(16 + i * 5), yy + P(6))])
                pygame.draw.circle(c, (240, 220, 80), (head[0] - P(8), head[1] - P(10)), max(1, P(3)))
        elif k == 'pamp':
            if pst > 0:
                for i in range(10):
                    a = i / 10 * 2 * math.pi
                    pygame.draw.circle(c, (250, 210, 40), (hx + int(math.cos(a) * P(11)), hy - P(8) + int(math.sin(a) * P(11))), max(1, P(5)))
                pygame.draw.circle(c, (220, 150, 20), (hx, hy - P(8)), max(1, P(5)))
            else:
                for i in range(14):
                    a = i / 14 * 2 * math.pi + t * 0.3
                    pygame.draw.circle(c, (240, 240, 230), (hx + int(math.cos(a) * P(15)), hy - P(8) + int(math.sin(a) * P(15))), max(1, P(4)))
                pygame.draw.circle(c, (220, 200, 120), (hx, hy - P(8)), max(1, P(5)))
            if int(t * 2 + cx) % 3 == 0:
                sx, sy = hx + P(20), hy - P(26)
                pygame.draw.line(c, HOPE, (sx - P(4), sy), (sx + P(4), sy), 1)
                pygame.draw.line(c, HOPE, (sx, sy - P(4)), (sx, sy + P(4)), 1)
        if hpr < 0.4:
            pygame.draw.line(c, (90, 60, 30), (cx - P(10), fy - P(4)), (cx - P(18), fy - P(12)), max(1, P(2)))

    # ---------------------------------------------------------- asimilovaní
    def draw_zombie(self, c, k, x, fy, t, fl=0, hpr=1.0, shr=0.0, anim=0.0, jy=0.0, wind=0.0, s=1.0):
        if k == 'exe':
            s *= 1.55

        def P(v):
            return int(round(v * s))
        x, fy = int(x), int(fy - jy)
        awake = fl & 2
        eating = fl & 1
        facing = 1 if awake else -1
        body_c, pants_c = ZCOL.get(k, ZCOL['zak'])
        head_c = (170, 150, 118) if awake else (112, 128, 104)
        if fl & 4:
            head_c = mix(head_c, (150, 90, 180), 0.45)
            body_c = mix(body_c, (110, 70, 140), 0.3)
        if fl & 64:
            head_c = mix(head_c, (255, 255, 255), 0.5)
        sp = anim * (7 if k == 'bez' else 4.5)
        step = 0 if eating else math.sin(sp)
        lean = P(8) * facing if k == 'bez' else 0
        hipy = fy - P(28)
        if k == 'dron':
            pygame.draw.rect(c, (50, 50, 54), (x - facing * P(18) - P(6), fy - P(62), P(12), P(26)))
            ra = math.cos(t * 40) * P(22)
            pygame.draw.line(c, (180, 180, 190), (x - facing * P(12) - ra, fy - P(66)), (x - facing * P(12) + ra, fy - P(66)), 2)
        if k == 'post':
            pygame.draw.rect(c, (60, 110, 50), (x - facing * P(16) - P(5), fy - P(60), P(10), P(28)))
        pygame.draw.line(c, pants_c, (x, hipy), (x + int(step * P(8)), fy), max(2, P(6)))
        pygame.draw.line(c, pants_c, (x, hipy), (x - int(step * P(8)), fy), max(2, P(6)))
        body = pygame.Rect(x - P(12) + lean // 2, fy - P(62), P(24), P(36))
        pygame.draw.rect(c, body_c, body)
        if k == 'zak':
            for i in range(3):
                pygame.draw.line(c, (40, 44, 40), (body.x + P(6) + P(i * 4), body.y + P(8)), (body.x + P(6) + P(i * 4), body.y + P(16)), 1)
        elif k == 'kaz':
            pygame.draw.rect(c, (200, 30, 30), (body.x, body.y + P(6), P(6), P(8)))
            pygame.draw.rect(c, body_c, (x - P(14), fy - P(30), P(28), P(10)))
        elif k == 'exe':
            pygame.draw.line(c, (170, 20, 20), (body.centerx, body.y + P(2)), (body.centerx, body.y + P(24)), max(2, P(4)))
            pygame.draw.rect(c, (220, 220, 214), (body.centerx - P(5), body.y, P(10), P(4)))
        bob = int(math.sin(anim * 10) * P(3)) if eating else 0
        hx, hy = x + lean + facing * P(2), fy - P(72) + bob
        pygame.draw.circle(c, head_c, (hx, hy), P(12))
        if k == 'doz':
            pygame.draw.circle(c, (30, 34, 50), (hx, hy - P(3)), P(13), draw_top_left=True, draw_top_right=True)
            pygame.draw.line(c, (30, 34, 50), (hx - P(14), hy - P(2)), (hx + P(14), hy - P(2)), max(1, P(3)))
        elif k == 'bez':
            pygame.draw.line(c, (200, 30, 30), (hx - P(12), hy - P(6)), (hx + P(12), hy - P(6)), max(1, P(3)))
        elif k == 'post':
            pygame.draw.circle(c, (60, 60, 60), (hx + facing * P(6), hy + P(4)), max(1, P(6)))
        eye = (90, 60, 30) if awake else (230, 30, 20)
        pygame.draw.circle(c, eye, (hx + facing * P(5), hy - P(2)), max(1, P(3)))
        pygame.draw.circle(c, eye, (hx + facing * P(-1), hy - P(3)), max(1, P(2)))
        pygame.draw.line(c, (40, 30, 30), (hx + facing * P(2), hy + P(5)), (hx + facing * P(8), hy + P(5)), 1)
        arm_y = fy - P(54)
        if awake:
            pygame.draw.line(c, head_c, (x, arm_y), (x + facing * P(10), arm_y + P(16)), max(2, P(4)))
            pygame.draw.line(c, head_c, (x, arm_y + P(3)), (x - facing * P(8), arm_y + P(16)), max(2, P(4)))
            for i in range(5):
                a = i / 5 * 2 * math.pi
                pygame.draw.circle(c, (250, 210, 60), (hx + int(math.cos(a) * P(5)), hy - P(15) + int(math.sin(a) * P(5))), max(1, P(3)))
            pygame.draw.circle(c, (240, 120, 30), (hx, hy - P(15)), max(1, P(2)))
            if eating:
                pygame.draw.line(c, head_c, (x, arm_y), (x + facing * P(22), arm_y - P(2)), max(2, P(4)))
        else:
            reach = P(22) if not eating else P(16 + 6 * math.sin(anim * 10))
            if k == 'exe':
                raise_k = min(1.0, wind / 1.1) if wind > 0 else 0.0
                sx = x + facing * P(10)
                sy = arm_y - P(10) - int(raise_k * P(30))
                pygame.draw.line(c, head_c, (x, arm_y), (sx, sy), max(2, P(4)))
                pygame.draw.rect(c, (70, 40, 20), (sx - P(3), sy - P(14), P(6), P(16)))
                pygame.draw.rect(c, (150, 24, 20), (sx - P(14), sy - P(22), P(28), P(10)))
                if s >= 1.2:
                    c.blit(self.stamp_txt, self.stamp_txt.get_rect(center=(sx, sy - P(17))))
            else:
                pygame.draw.line(c, head_c, (x, arm_y), (x + facing * reach, arm_y + P(4)), max(2, P(4)))
            if hpr >= 0.5:
                pygame.draw.line(c, head_c, (x, arm_y + P(4)), (x + facing * (reach - P(4)), arm_y + P(8)), max(2, P(4)))
            if k == 'kaz':
                mx = x + facing * P(18)
                pygame.draw.polygon(c, (200, 200, 190), [(mx, arm_y - P(4)), (mx + facing * P(14), arm_y - P(12)),
                                                         (mx + facing * P(14), arm_y + P(6))])
                if s >= 1:
                    rr = P(44 + 6 * math.sin(t * 4))
                    pygame.draw.circle(c, (120, 30, 30), (x, fy - P(40)), rr, 1)
            if k == 'post':
                pygame.draw.line(c, (40, 40, 40), (x + facing * P(10), arm_y + P(2)), (x + facing * P(30), arm_y + P(6)), max(1, P(3)))
        if k == 'doz' and shr > 0:
            sx = x + facing * P(20)
            rr = pygame.Rect(sx - P(5), fy - P(70), P(10), P(62))
            pygame.draw.rect(c, (130, 140, 160), rr)
            pygame.draw.rect(c, (70, 76, 90), rr, 1)
            pygame.draw.line(c, (220, 200, 60), (rr.x, rr.y + P(20)), (rr.right, rr.y + P(20)), max(1, P(3)))
            if shr < 0.5:
                pygame.draw.line(c, (50, 50, 60), (rr.x + P(2), rr.y + P(30)), (rr.right - P(2), rr.y + P(46)), 1)
        if fl & 8 and s >= 1:
            pygame.draw.line(c, WARN, (hx, hy - P(24)), (hx, hy - P(18)), 2)
            pygame.draw.circle(c, WARN, (hx, hy - P(15)), 1)

    def draw_boss(self, c, x, t, hpr, fl):
        top = BY + CH - 10
        bot = BY + 4 * CH - 8
        f = int(x - 110)
        en = fl & 32
        col = (150, 30, 24) if not (en and int(t * 6) % 2) else (200, 50, 30)
        pygame.draw.rect(c, col, (f + 40, top + 30, 210, bot - top - 50))
        pygame.draw.rect(c, (90, 20, 16), (f + 40, top + 30, 210, bot - top - 50), 3)
        pygame.draw.rect(c, (60, 60, 60), (f + 150, top - 10, 80, 70))
        pygame.draw.rect(c, (255, 190, 60), (f + 160, top, 30, 24))
        pygame.draw.rect(c, (50, 50, 50), (f + 210, top - 60, 16, 50))
        c.blit(self.boss_txt, (f + 60, top + 60))
        drum = pygame.Rect(f, top + 40, 50, bot - top - 70)
        pygame.draw.rect(c, (40, 40, 44), drum)
        for i in range(9):
            y = drum.y + int((i * 30 + t * 220) % drum.h)
            pygame.draw.line(c, (190, 190, 200), (f - 8, y), (f + 50, y), 3)
        pygame.draw.circle(c, WARN if int(t * 3) % 2 else (140, 20, 20), (f + 70, top + 44), 12)
        for wx in (f + 70, f + 150, f + 230):
            pygame.draw.circle(c, (20, 20, 20), (wx, bot - 10), 22)
            pygame.draw.circle(c, (70, 70, 70), (wx, bot - 10), 22, 4)
            a = t * 4
            pygame.draw.line(c, (90, 90, 90), (wx + math.cos(a) * 18, bot - 10 + math.sin(a) * 18),
                             (wx - math.cos(a) * 18, bot - 10 - math.sin(a) * 18), 3)
        pygame.draw.rect(c, (40, 10, 10), (f + 40, top - 26, 210, 10))
        pygame.draw.rect(c, WARN, (f + 40, top - 26, int(210 * max(0, hpr)), 10))
        if random.random() < 0.3:
            self.particles.append([f + 218, top - 60, random.uniform(-20, 20), random.uniform(-70, -40),
                                   1.6, 1.6, (60, 58, 54), random.randint(5, 9), -10, 'smoke'])

    # ---------------------------------------------------------- efekty
    def reset_fx(self):
        self.particles = []
        self.decals = []
        self.banner = None
        self.shake = 0.0
        self.birds = []
        self.zdisp = {}
        self.flash = 0.0

    def fx(self, kind, x, y, *a):
        P = self.particles
        r = random
        if kind == 'dust':
            for _ in range(10):
                P.append([x + r.uniform(-20, 20), y + r.uniform(10, 30), r.uniform(-60, 60), r.uniform(-120, -30),
                          0.5, 0.5, (110, 86, 56), 3, 300, 'sq'])
        elif kind == 'leaves':
            for _ in range(14):
                P.append([x + r.uniform(-15, 15), y + r.uniform(-20, 10), r.uniform(-90, 90), r.uniform(-160, -40),
                          0.9, 0.9, r.choice([LEAF, LEAF_D, (120, 90, 40)]), 4, 350, 'sq'])
        elif kind == 'hit':
            col = {'trn': (120, 20, 20), 'jed': (150, 80, 200), 'pamp': (255, 250, 220)}.get(a[0] if a else 'trn', BLOOD)
            for _ in range(6):
                P.append([x, y + r.uniform(-10, 10), r.uniform(-40, 120), r.uniform(-120, 40), 0.35, 0.35, col, 3, 400, 'sq'])
        elif kind == 'die':
            zk = a[0] if a else 'zak'
            awake = a[1] if len(a) > 1 else 0
            for _ in range(24):
                P.append([x + r.uniform(-10, 10), y + r.uniform(-40, 10), r.uniform(-160, 160), r.uniform(-260, -40),
                          r.uniform(0.5, 1.0), 1.0, r.choice([BLOOD, (80, 10, 10), (70, 74, 68)]), r.randint(3, 6), 700, 'sq'])
            P.append([x, y - 45, r.uniform(-120, 120), r.uniform(-340, -220), 1.4, 1.4,
                      (170, 150, 118) if awake else (112, 128, 104), 12, 800, 'head'])
            self.decals.append([x + r.uniform(-10, 10), y + 30 + r.uniform(-6, 6), r.randint(30, 50), r.randint(8, 14), 25.0])
            if len(self.decals) > 60:
                self.decals.pop(0)
            if awake:
                self.fx('bloom', x, y)
        elif kind == 'gulp':
            for _ in range(12):
                P.append([x - 20, y - 20, r.uniform(-80, 40), r.uniform(-150, -30), 0.6, 0.6, BLOOD, 4, 500, 'sq'])
        elif kind in ('boom', 'bigboom'):
            n = 40 if kind == 'boom' else 120
            spd = 260 if kind == 'boom' else 420
            for _ in range(n):
                a2 = r.uniform(0, 2 * math.pi)
                v = r.uniform(40, spd)
                P.append([x, y, math.cos(a2) * v, math.sin(a2) * v - 80, r.uniform(0.4, 1.0), 1.0,
                          r.choice([(255, 200, 60), (255, 120, 30), (200, 60, 20), (80, 76, 70)]), r.randint(3, 8), 200, 'sq'])
            for _ in range(8 if kind == 'boom' else 25):
                P.append([x + r.uniform(-30, 30), y + r.uniform(-20, 20), r.uniform(-30, 30), r.uniform(-60, -20),
                          2.0, 2.0, (70, 66, 60), r.randint(10, 16), -10, 'smoke'])
            self.decals.append([x, y + 30, 70, 18, 30.0, 'scorch'])
            self.flash = max(self.flash, 0.12 if kind == 'boom' else 0.4)
        elif kind == 'smash':
            self.fx('dust', x, y)
            self.fx('leaves', x, y)
        elif kind == 'awaken':
            for _ in range(22):
                P.append([x + r.uniform(-20, 20), y + r.uniform(-20, 20), r.uniform(-40, 40), r.uniform(-120, -30),
                          r.uniform(0.8, 1.4), 1.4, r.choice([HOPE, (255, 250, 200), (255, 180, 120)]), 3, -20, 'spark'])
            for _ in range(3):
                P.append([x + r.uniform(-15, 15), y - 10, r.uniform(-20, 20), r.uniform(-70, -40), 1.6, 1.6,
                          (255, 110, 150), 7, -10, 'heart'])
        elif kind == 'spark':
            for _ in range(10):
                P.append([x, y, r.uniform(-90, 90), r.uniform(-90, 90), 0.4, 0.4, HOPE, 3, 0, 'spark'])
        elif kind == 'shield':
            for _ in range(12):
                P.append([x, y, r.uniform(-50, 150), r.uniform(-200, -40), 0.9, 0.9, (130, 140, 160), 5, 600, 'sq'])
        elif kind == 'bloom':
            for _ in range(18):
                P.append([x + r.uniform(-20, 20), y + r.uniform(-10, 20), r.uniform(-60, 60), r.uniform(-120, -30),
                          r.uniform(1.0, 1.8), 1.8, r.choice([(255, 120, 160), (255, 220, 80), (180, 140, 255), (255, 255, 255)]),
                          4, 60, 'petal'])
        elif kind == 'burn':
            for _ in range(20):
                P.append([x, y - 30, r.uniform(-60, 120), r.uniform(-160, -40), 0.6, 0.6,
                          r.choice([(255, 180, 40), (255, 90, 20), (60, 40, 30)]), 5, 200, 'sq'])
            self.decals.append([x, y + 30, 40, 10, 25.0, 'scorch'])
        elif kind == 'ring':
            P.append([x, y, 0, 0, 0.6, 0.6, WARN, 10, 0, 'ring'])

    def handle_events(self, evs):
        for e in evs:
            k = e[0]
            if k == 'snd':
                self.snd.play(e[1])
            elif k == 'fx':
                self.fx(e[1], e[2], e[3], *e[4:])
            elif k == 'msg':
                self.banner = (e[1], MSG_COL.get(e[2], TEXT), 2.6)
            elif k == 'shake':
                self.shake = max(self.shake, e[1])
            elif k == 'bird':
                for i in range(3):
                    self.birds.append([-40 - i * 50, 50 + random.uniform(0, 40) + i * 10, random.random() * 6])
                self.snd.play('bird')

    def update_fx(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        if len(self.particles) > 900:
            self.particles = self.particles[-900:]
        for d in self.decals:
            d[4] -= dt
        self.decals = [d for d in self.decals if d[4] > 0]
        for b in self.birds:
            b[0] += 170 * dt
            b[2] += dt * 9
        self.birds = [b for b in self.birds if b[0] < W + 60]
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        if self.banner:
            t, col, life = self.banner
            life -= dt
            self.banner = (t, col, life) if life > 0 else None
        self.ticker_x -= 70 * dt
        if self.ticker_x < -self.ticker_img.get_width():
            self.ticker_x += self.ticker_img.get_width()

    def draw_particles(self):
        c = self.canvas
        for p in self.particles:
            x, y, life, ml, col, sz, kind = int(p[0]), int(p[1]), p[4], p[5], p[6], p[7], p[9]
            if kind == 'sq':
                pygame.draw.rect(c, col, (x, y, sz, sz))
            elif kind == 'spark':
                pygame.draw.circle(c, col, (x, y), max(1, int(sz * life / ml + 1)))
            elif kind == 'petal':
                pygame.draw.ellipse(c, col, (x, y, sz + 3, sz))
            elif kind == 'heart':
                pygame.draw.circle(c, col, (x - 3, y), 4)
                pygame.draw.circle(c, col, (x + 3, y), 4)
                pygame.draw.polygon(c, col, [(x - 7, y + 1), (x + 7, y + 1), (x, y + 9)])
            elif kind == 'head':
                pygame.draw.circle(c, col, (x, y), sz)
                pygame.draw.circle(c, (230, 30, 20), (x - 4, y - 2), 3)
                pygame.draw.circle(c, BLOOD, (x, y + sz), 4)
            elif kind == 'smoke':
                k = life / ml
                s = pygame.Surface((sz * 4, sz * 4), pygame.SRCALPHA)
                pygame.draw.circle(s, col + (int(110 * k),), (sz * 2, sz * 2), int(sz * (2 - k)))
                c.blit(s, (x - sz * 2, y - sz * 2))
            elif kind == 'ring':
                k = 1 - life / ml
                pygame.draw.circle(c, col, (x, y), int(20 + 90 * k), 2)

    def draw_decals(self):
        for d in self.decals:
            k = min(1.0, d[4] / 10)
            base = (40, 38, 31)
            col = mix(base, (20, 18, 16) if len(d) > 5 else (80, 10, 10), k)
            pygame.draw.ellipse(self.canvas, col, (int(d[0] - d[2] / 2), int(d[1] - d[3] / 2), d[2], d[3]))

    def draw_birds(self):
        for b in self.birds:
            x, y, ph = int(b[0]), int(b[1]), b[2]
            w = int(math.sin(ph) * 6)
            pygame.draw.line(self.canvas, (30, 30, 30), (x - 10, y - w), (x, y), 2)
            pygame.draw.line(self.canvas, (30, 30, 30), (x, y), (x + 10, y - w), 2)

    def present(self):
        sx = sy = 0
        if self.shake > 0:
            m = int(self.shake * 22)
            sx, sy = random.randint(-m, m), random.randint(-m, m)
        self.screen.fill((0, 0, 0))
        self.screen.blit(self.canvas, (sx, sy))
        if self.flash > 0:
            fl = pygame.Surface((W, H), pygame.SRCALPHA)
            fl.fill((255, 240, 200, int(min(1, self.flash * 3) * 90)))
            self.screen.blit(fl, (0, 0))
        self.screen.blit(self.scan, (0, 0))
        self.screen.blit(self.vig, (0, 0))

    # ---------------------------------------------------------- herní plocha
    @staticmethod
    def pk_rect(i):
        return pygame.Rect(PK_X0 + i * (PK_W + PK_GAP), PK_Y, PK_W, PK_H)

    @staticmethod
    def cell_at(pos):
        x, y = pos
        if BX <= x < BOARD_R and BY <= y < BY + LANES * CH:
            return (y - BY) // CH, (x - BX) // CW
        return None

    def packets(self, snap, side):
        if side == 'P':
            return list(snap['pk']) + ['shovel']
        return list(snap['zk'])

    def pk_ok(self, snap, side, key):
        if key == 'shovel':
            return True
        if side == 'P':
            return snap['L'] >= PLANTS[key]['cost'] and snap['cp'].get(key, 0) <= 0
        return (snap['Z'] >= ZOMBIES[key]['cost'] and snap['cz'].get(key, 0) <= 0
                and not snap['lk'].get(key))

    def dr_game(self, snap, side):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        self.draw_birds()
        self.draw_decals()
        t = self.t
        if snap.get('beam'):
            bx, life = snap['beam']
            self.beam_s.set_alpha(int(255 * min(1.0, life / 1.5)))
            c.blit(self.beam_s, (int(bx) - 70, 0))
        mouse = pygame.mouse.get_pos()
        cell = self.cell_at(mouse)
        if self.sel and cell and not snap.get('res'):
            lane, col = cell
            if side == 'P' and self.sel != 'shovel':
                g = pygame.Surface((CW, CH), pygame.SRCALPHA)
                self.draw_plant(g, self.sel, CW // 2, CH - 14, t)
                g.set_alpha(110)
                c.blit(g, (BX + col * CW, BY + lane * CH))
            elif side == 'P':
                pygame.draw.rect(c, WARN, (BX + col * CW + 2, BY + lane * CH + 2, CW - 4, CH - 4), 2)
            else:
                g = pygame.Surface((COLS * CW, CH), pygame.SRCALPHA)
                g.fill((200, 30, 20, 40))
                c.blit(g, (BX, BY + lane * CH))
        for l, m in enumerate(snap['mw']):
            cy = lane_cy(l)
            if m == 0:
                pygame.draw.rect(c, (120, 70, 40), (BX - 48, cy + 6, 30, 18))
                pygame.draw.rect(c, (70, 40, 24), (BX - 48, cy + 6, 30, 18), 2)
                pygame.draw.line(c, (90, 90, 90), (BX - 18, cy + 12), (BX - 6, cy + 12), 3)
                if int(t * 8 + l) % 2:
                    pygame.draw.circle(c, (80, 160, 255), (BX - 4, cy + 12), 2)
            elif m > 0:
                pygame.draw.rect(c, (120, 70, 40), (m - 15, cy + 6, 30, 18))
                for _ in range(3):
                    self.particles.append([m + 16, cy + 12, random.uniform(80, 220), random.uniform(-60, 30), 0.3, 0.3,
                                           random.choice([(255, 180, 40), (255, 90, 20)]), 6, 0, 'sq'])
        plants = {}
        for p in snap['pl']:
            plants.setdefault(p[1], []).append(p)
        zs = {}
        boss = None
        for z in snap['z']:
            if z[1] == 'boss':
                boss = z
                continue
            zs.setdefault(z[2], []).append(z)
        for lane in range(LANES):
            fy = lane_fy(lane)
            for p in sorted(plants.get(lane, []), key=lambda q: q[2]):
                k, _l, col, hp, mhp, pt, pst = p
                self.draw_plant(c, k, BX + col * CW + CW / 2, fy, t, hp / max(1, mhp), pt, pst)
            for z in sorted(zs.get(lane, []), key=lambda q: -q[3]):
                zid, k, _l, x, hp, mhp, sh, msh, fl, anim, jy, wind = z
                dx = self.zdisp.get(zid, x)
                if abs(dx - x) > 60:
                    dx = x
                self.draw_zombie(c, k, dx, fy + 4, t, fl, hp / max(1, mhp), sh / msh if msh else 0, anim, jy, wind)
                if fl & 16 and random.random() < 0.6:
                    self.particles.append([dx - 34, fy - 48, random.uniform(-180, -120), random.uniform(-20, 30), 0.5, 0.5,
                                           random.choice([(200, 220, 80), (160, 200, 60)]), 3, 60, 'sq'])
        age = min(0.1, self.snap_age)
        for k, lane, x in snap['pr']:
            x = int(x + PROJ_SPD[k] * age)
            y = lane_cy(lane) - 30
            if k == 'trn':
                pygame.draw.polygon(c, (150, 170, 80), [(x + 9, y), (x - 7, y - 4), (x - 7, y + 4)])
            elif k == 'jed':
                pygame.draw.circle(c, TOX, (x, y), 6)
                pygame.draw.circle(c, (220, 180, 255), (x - 2, y - 2), 2)
            else:
                pygame.draw.circle(c, (250, 250, 240), (x, y), 4)
                for i in range(4):
                    a = i * math.pi / 2 + t * 5
                    pygame.draw.line(c, (220, 220, 210), (x, y), (x + math.cos(a) * 8, y + math.sin(a) * 8), 1)
        if boss:
            zid, k, _l, x, hp, mhp, sh, msh, fl, anim, jy, wind = boss
            self.draw_boss(c, self.zdisp.get(zid, x), t, hp / max(1, mhp), fl)
        for bx, by, rot in snap['ba']:
            pygame.draw.rect(c, (80, 90, 60), (bx - 12, by - 14, 24, 28))
            pygame.draw.line(c, AMBER, (bx - 12, by - 4 + int(rot) % 4), (bx + 12, by - 4 + int(rot) % 4), 3)
        self.draw_particles()
        if snap.get('dark') and side == 'P':
            self.draw_darkness(snap)
        if snap.get('rain'):
            self.draw_rain()
        for lid, x, y, ttl in snap['li']:
            if ttl < 2 and int(t * 8) % 2:
                continue
            pul = 1 + 0.12 * math.sin(t * 5 + lid)
            c.blit(self.glow, (x - 40, y - 40))
            pygame.draw.circle(c, (255, 220, 90), (x, y), int(12 * pul))
            pygame.draw.circle(c, (255, 250, 220), (x, y), int(6 * pul))
            for i in range(6):
                a = i * math.pi / 3 + t
                pygame.draw.line(c, (255, 220, 90), (x + math.cos(a) * 15, y + math.sin(a) * 15),
                                 (x + math.cos(a) * 21, y + math.sin(a) * 21), 2)
        self.dr_hud(snap, side)
        if self.banner:
            txt, col, life = self.banner
            a = min(1.0, life * 2)
            img = self.f_med.render(txt, True, col)
            img.set_alpha(int(255 * a))
            r = img.get_rect(center=(BX + COLS * CW // 2, BY + 2 * CH + 50))
            bgs = pygame.Surface((r.w + 36, r.h + 14), pygame.SRCALPHA)
            bgs.fill((0, 0, 0, int(180 * a)))
            c.blit(bgs, (r.x - 18, r.y - 7))
            c.blit(img, r)

    def draw_darkness(self, snap):
        d = self.dark
        base = 150 if random.random() < 0.004 else 232
        d.fill((0, 0, 0, base))
        oy = BY - 10

        def hole(x, y, R):
            s = self.stamps[R]
            d.blit(s, (int(x) - R, int(y) - oy - R), special_flags=pygame.BLEND_RGBA_MIN)
        for p in snap['pl']:
            if p[0] == 'lampa':
                hole(BX + p[2] * CW + CW / 2, lane_cy(p[1]) - 10, 170)
            else:
                hole(BX + p[2] * CW + CW / 2, lane_cy(p[1]), 45)
        for lid, x, y, ttl in snap['li']:
            hole(x, y, 80)
        for k, lane, x in snap['pr']:
            hole(x, lane_cy(lane) - 30, 45)
        for p in self.particles:
            if p[9] == 'sq' and p[6] in ((255, 200, 60), (255, 120, 30)):
                hole(p[0], p[1], 45)
        if snap.get('beam'):
            for yy in range(BY, BY + LANES * CH, 60):
                hole(snap['beam'][0], yy, 80)
        self.canvas.blit(d, (0, oy))

    def draw_rain(self):
        c = self.canvas
        tint = pygame.Surface((COLS * CW, LANES * CH), pygame.SRCALPHA)
        tint.fill((90, 140, 30, 28))
        c.blit(tint, (BX, BY))
        for _ in range(70):
            x = random.randint(BX - 40, W)
            y = random.randint(BY - 60, BY + LANES * CH)
            pygame.draw.line(c, (150, 200, 80), (x, y), (x - 6, y + 14), 1)

    def dr_hud(self, snap, side):
        c = self.canvas
        if side == 'P':
            self.panel(14, PK_Y, 88, PK_H, "SVĚTLO", HOPE)
            pygame.draw.circle(c, (255, 210, 70), (58, 44), 13)
            pygame.draw.circle(c, (255, 250, 220), (58, 44), 6)
            self.txt(str(snap['L']), self.f_med, HOPE, (58, 76), "center")
        else:
            self.panel(14, PK_Y, 88, PK_H, "ZLOBA", WARN)
            pygame.draw.circle(c, (140, 20, 20), (58, 44), 13)
            pygame.draw.circle(c, (230, 40, 30), (58, 44), 5)
            self.txt(str(snap['Z']), self.f_med, WARN, (58, 76), "center")
        for i, key in enumerate(self.packets(snap, side)):
            r = self.pk_rect(i)
            pygame.draw.rect(c, (28, 30, 26), r)
            pygame.draw.rect(c, EDGE, r, 1)
            ok = self.pk_ok(snap, side, key)
            if key == 'shovel':
                pygame.draw.line(c, (120, 90, 50), (r.centerx - 14, r.y + 20), (r.centerx + 8, r.y + 50), 4)
                pygame.draw.polygon(c, (170, 170, 170), [(r.centerx + 4, r.y + 46), (r.centerx + 20, r.y + 50),
                                                         (r.centerx + 16, r.y + 66), (r.centerx + 2, r.y + 60)])
                self.txt("LOPATA", self.f_tiny, DIM, (r.centerx, r.bottom - 10), "center")
                self.txt("S", self.f_tiny, DIM, (r.x + 4, r.y + 3))
            elif side == 'P':
                self.draw_plant(c, key, r.centerx, r.y + 62, self.t, s=0.62)
                self.txt(str(PLANTS[key]['cost']), self.f_smallb, HOPE, (r.centerx, r.bottom - 10), "center")
                cdf = snap['cp'].get(key, 0)
            else:
                self.draw_zombie(c, key, r.centerx, r.y + 70, self.t, 0, 1, 1 if key == 'doz' else 0, self.t,
                                 s=0.36 if key == 'exe' else 0.55)
                self.txt(str(ZOMBIES[key]['cost']), self.f_smallb, WARN, (r.centerx, r.bottom - 10), "center")
                cdf = snap['cz'].get(key, 0)
            if key != 'shovel':
                if not ok:
                    c.blit(self.dimpk, r)
                if cdf > 0:
                    sh = pygame.Surface((PK_W, int(PK_H * cdf)), pygame.SRCALPHA)
                    sh.fill((0, 0, 0, 120))
                    c.blit(sh, r)
                lk = snap['lk'].get(key)
                if lk:
                    self.txt("%ds" % lk, self.f_smallb, AMBER, r.center, "center")
                self.txt(str(i + 1), self.f_tiny, DIM, (r.x + 4, r.y + 3))
            if self.sel == key:
                pygame.draw.rect(c, AMBER, r.inflate(4, 4), 2)
        ix = PK_X0 + len(self.packets(snap, side)) * (PK_W + PK_GAP) + 6
        iw = W - 14 - ix
        if iw > 120:
            kind = snap['kind']
            self.panel(ix, PK_Y, iw, PK_H, "HLÁŠENÍ", CYAN)
            cx = ix + iw // 2
            if kind == 'sp':
                self.txt("%d · %s" % (snap['lvl'] + 1, LEVELS[snap['lvl']]['name']), self.f_normb, TEXT, (cx, 40), "center")
                self.txt("probuzeno: %d" % snap['aw'], self.f_small, HOPE, (cx, 66), "center")
            elif kind == 'pvp':
                left = max(0, (snap['dur'] or 0) - snap['t'])
                self.txt("%d:%02d" % (left // 60, left % 60), self.f_med, TEXT, (cx, 44), "center")
                self.txt(PVP_MODES[snap['mode']]['name'], self.f_tiny, DIM, (cx, 70), "center")
                self.txt("TY: " + ("KYTKY" if side == 'P' else "ZOMBIE"), self.f_tiny, ACID if side == 'P' else WARN, (cx, 86), "center")
            elif kind == 'endless':
                self.txt("VLNA %d" % snap['wave'], self.f_med, TEXT, (cx, 44), "center")
                self.txt("rekord: %d" % self.save.get('endless', 0), self.f_small, DIM, (cx, 72), "center")
            elif kind == 'puzzle':
                self.txt("SEMÍNKA", self.f_tiny, DIM, (cx, 30), "center")
                for i, ok in enumerate(snap['sd']):
                    x = cx - 48 + i * 24
                    pygame.draw.circle(c, (255, 200, 80) if ok else (50, 44, 34), (x, 56), 8)
                    pygame.draw.circle(c, EDGE, (x, 56), 8, 1)
                self.txt("KOŘENY", self.f_small, HOPE, (cx, 80), "center")
        if snap['kind'] == 'sp':
            bw = 300
            bx, by = BOARD_R - bw, BY + LANES * CH + 12
            pygame.draw.rect(c, (30, 12, 10), (bx, by, bw, 12))
            pygame.draw.rect(c, WARN, (bx, by, int(bw * snap['prog']), 12))
            pygame.draw.rect(c, EDGE, (bx, by, bw, 12), 1)
            self.txt("POSTUP ÚTOKU", self.f_tiny, DIM, (bx - 8, by - 1), "topright")
        hint = ("klik = sebrat světlo · 1–9 balíček · S lopata · pravé tl. zrušit · P pauza" if side == 'P'
                else "vyber zombie (1–9) a klikni do řady · pravé tl. zrušit")
        self.txt(hint, self.f_tiny, DIM, (BX, BY + LANES * CH + 36))
        if snap.get('cd', 0) > 0:
            self.dim_box(str(max(1, math.ceil(snap['cd']))), "Připravte se…")

    def dim_box(self, title, sub, col=AMBER):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 165))
        self.canvas.blit(s, (0, 0))
        self.glitch_text(title, self.f_big, (W // 2, H // 2 - 30), col)
        self.txt(sub, self.f_norm, TEXT, (W // 2, H // 2 + 25), "center")

    def game_click(self, e, snap, side, send):
        if snap.get('res') or snap.get('cd', 0) > 0:
            return
        if e.button == 3:
            self.sel = None
            return
        if e.button != 1:
            return
        mx, my = e.pos
        if side == 'P':
            for lid, x, y, ttl in snap['li']:
                if (x - mx) ** 2 + (y - my) ** 2 < 34 ** 2:
                    send(['collect', lid])
                    return
        for i, key in enumerate(self.packets(snap, side)):
            if self.pk_rect(i).collidepoint(mx, my):
                if self.sel == key:
                    self.sel = None
                elif self.pk_ok(snap, side, key):
                    self.sel = key
                    self.snd.play('tick')
                return
        cell = self.cell_at((mx, my))
        if cell and self.sel:
            lane, col = cell
            if side == 'P':
                if self.sel == 'shovel':
                    send(['shovel', lane, col])
                else:
                    send(['plant', self.sel, lane, col])
                self.sel = None
            else:
                send(['zombie', self.sel, lane])
                if not self.pk_ok(snap, side, self.sel):
                    self.sel = None

    def game_key(self, e, snap, side):
        if e.key == pygame.K_s and side == 'P':
            self.sel = None if self.sel == 'shovel' else 'shovel'
            return True
        if pygame.K_1 <= e.key <= pygame.K_9:
            i = e.key - pygame.K_1
            pk = self.packets(snap, side)
            if i < len(pk) and self.pk_ok(snap, side, pk[i]):
                self.sel = pk[i]
                self.snd.play('tick')
            return True
        return False

    def smooth_zombies(self, snap, dt):
        seen = set()
        for z in snap['z']:
            zid, x = z[0], z[3]
            seen.add(zid)
            d = self.zdisp.get(zid, x)
            self.zdisp[zid] = d + (x - d) * min(1.0, dt * 14)
        for zid in list(self.zdisp):
            if zid not in seen:
                del self.zdisp[zid]

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
                if e.key == pygame.K_m and self.state not in ("join",):
                    self.snd.toggle_music()
                    continue
            getattr(self, "ev_" + self.state)(e)
        getattr(self, "up_" + self.state)(dt)
        self.update_fx(dt)
        getattr(self, "dr_" + self.state)()
        self.present()

    # ================================================================ MENU
    def ev_menu(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.unicode and e.unicode.isalpha():
            self.code_buf = (self.code_buf + e.unicode.upper())[-len(SECRET_CODE):]
            if self.code_buf == SECRET_CODE:
                self.save['done'] = [True] * 5
                self.save['secret'] = True
                write_save(self.save)
                self.snd.play('unlock')
                self.banner = ("SEMÍNKO ZASAZENO — vše odemčeno", HOPE, 3.0)
                self.code_buf = ""
        if e.key == pygame.K_UP:
            self.menu_i = (self.menu_i - 1) % len(MENU)
            self.snd.play('tick')
        elif e.key == pygame.K_DOWN:
            self.menu_i = (self.menu_i + 1) % len(MENU)
            self.snd.play('tick')
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.snd.play('select')
            [lambda: self.goto("map"), lambda: self.goto("host_setup"), self.start_join,
             lambda: self.goto("atlas"), self.do_quit][self.menu_i]()
        elif e.key == pygame.K_ESCAPE:
            self.do_quit()

    def do_quit(self):
        self.quit = True

    def goto(self, st):
        self.state = st

    def up_menu(self, dt):
        pass

    def dr_menu(self):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        self.draw_birds()
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 120))
        c.blit(dim, (0, 0))
        self.header()
        self.draw_plant(c, 'lampa', 150, 560, self.t, s=1.6)
        self.draw_plant(c, 'pamp', 260, 600, self.t, s=1.2)
        self.draw_zombie(c, 'zak', 900 + math.sin(self.t * 0.3) * 20, 600, self.t, 0, 1, 0, self.t)
        self.draw_zombie(c, 'exe', 1010, 610, self.t, 0, 1, 0, self.t * 0.6)
        self.glitch_text("ZÁHON", self.f_huge, (W // 2, 150), ACID, amt=4)
        self.txt("poslední skleník", self.f_med, HOPE, (W // 2, 212), "center")
        for i, m in enumerate(MENU):
            y = 290 + i * 48
            sel = i == self.menu_i
            if sel:
                pygame.draw.rect(c, (30, 40, 14), (W // 2 - 230, y - 6, 460, 38))
                pygame.draw.rect(c, ACID, (W // 2 - 230, y - 6, 460, 38), 1)
            self.txt(m, self.f_normb, ACID if sel else TEXT, (W // 2, y + 13), "center")
        self.txt("Zahradník: " + self.name, self.f_small, DIM, (18, 48))
        self.txt("↑↓ výběr · ENTER potvrdit · M hudba · F11 celá obrazovka", self.f_small, DIM, (W // 2, H - 52), "center")
        if self.banner:
            self.txt(self.banner[0], self.f_normb, self.banner[1], (W // 2, 540), "center")
        self.ticker()

    # ================================================================ MAPA
    def node_open(self, node):
        kind, n = node
        d = self.save['done']
        if kind == 'lvl':
            return n == 0 or d[n - 1]
        if kind == 'secret':
            return self.save.get('secret')
        return d[4]

    def ev_map(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.state = "menu"
        elif e.key in (pygame.K_LEFT, pygame.K_UP):
            self.map_i = (self.map_i - 1) % len(MAP_NODES)
            self.snd.play('tick')
        elif e.key in (pygame.K_RIGHT, pygame.K_DOWN):
            self.map_i = (self.map_i + 1) % len(MAP_NODES)
            self.snd.play('tick')
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            node = MAP_NODES[self.map_i]
            if not self.node_open(node):
                self.snd.play('clank')
                return
            self.snd.play('select')
            kind, n = node
            if kind == 'lvl':
                self.show_story(LEVELS[n]['name'], LEVELS[n]['story'], lambda: self.start_level(n))
            elif kind == 'secret':
                self.show_story("KOŘENY", [s.replace("{b}", str(PUZZLE_BUDGET)) for s in SECRET_STORY], self.start_puzzle)
            else:
                self.show_story("NEKONEČNÁ NOC", ENDLESS_STORY, self.start_endless)

    def up_map(self, dt):
        pass

    def dr_map(self):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        c.blit(dim, (0, 0))
        self.header("PŘÍBĚH SKLENÍKU")
        self.glitch_text("SEKTOR 7", self.f_big, (W // 2, 90), TEXT)
        pts = [(130 + i * 175, 300 + (40 if i % 2 else -20)) for i in range(5)]
        for i in range(4):
            pygame.draw.line(c, (70, 64, 50), pts[i], pts[i + 1], 3)
        for i, node in enumerate(MAP_NODES):
            kind, n = node
            if kind == 'lvl':
                x, y = pts[n]
                label = "%d. %s" % (n + 1, LEVELS[n]['name'])
            elif kind == 'secret':
                x, y = 330, 500
                label = "KOŘENY" if self.save.get('secret') else "???"
            else:
                x, y = 790, 500
                label = "NEKONEČNÁ NOC"
            opened = self.node_open(node)
            sel = i == self.map_i
            col = ACID if opened else (70, 70, 64)
            pygame.draw.circle(c, (26, 30, 22), (x, y), 36)
            pygame.draw.circle(c, AMBER if sel else col, (x, y), 36, 3 if sel else 2)
            if kind == 'lvl' and self.save['done'][n]:
                self.draw_plant(c, LEVELS[n]['new'][-1], x, y + 26, self.t, s=0.7)
            elif opened:
                pygame.draw.circle(c, col, (x, y), 8)
            else:
                pygame.draw.rect(c, (90, 90, 84), (x - 9, y - 2, 18, 14))
                pygame.draw.circle(c, (90, 90, 84), (x, y - 4), 7, 2)
            self.txt(label, self.f_smallb, AMBER if sel else (TEXT if opened else DIM), (x, y + 52), "center")
        node = MAP_NODES[self.map_i]
        kind, n = node
        if kind == 'lvl':
            info = "Nové rostliny: " + ", ".join(PLANTS[k]['name'] for k in LEVELS[n]['new'])
        elif kind == 'secret':
            info = ("Puzzle: hraješ za probuzené a neseš semínka domů." if self.save.get('secret')
                    else "Odemkne se po dohrání příběhu. Nebo znáš kód…")
        else:
            info = "Přežij co nejvíc vln. Rekord: %d" % self.save.get('endless', 0)
        self.txt(info, self.f_norm, DIM, (W // 2, 620), "center")
        self.txt("←→ výběr · ENTER hrát · ESC zpět", self.f_small, DIM, (W // 2, H - 52), "center")
        self.ticker()

    # ================================================================ PŘÍBĚH
    def show_story(self, title, lines, then):
        self.story = (title, lines, self.t)
        self.after_story = then
        self.state = "story"

    def ev_story(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.snd.play('select')
                self.after_story()
            elif e.key == pygame.K_ESCAPE:
                self.state = "map"

    def up_story(self, dt):
        pass

    def dr_story(self):
        c = self.canvas
        c.fill(BG)
        self.header()
        title, lines, t0 = self.story
        self.glitch_text(title, self.f_big, (W // 2, 150), ACID)
        el = self.t - t0
        for i, s in enumerate(lines):
            k = max(0.0, min(1.0, (el - i * 0.8) * 1.5))
            if k <= 0:
                continue
            img = self.f_norm.render(s, True, TEXT)
            img.set_alpha(int(255 * k))
            c.blit(img, img.get_rect(center=(W // 2, 250 + i * 40)))
        if int(self.t * 2) % 2:
            self.txt("ENTER — do skleníku", self.f_normb, AMBER, (W // 2, 560), "center")
        self.ticker()

    # ================================================================ HRA (lokální)
    def start_level(self, n):
        self.world = World('sp', level=n, seed=random.randrange(1 << 30))
        self._start_local('P')

    def start_puzzle(self):
        self.world = World('puzzle', seed=random.randrange(1 << 30))
        self._start_local('Z')

    def start_endless(self):
        self.world = World('endless', seed=random.randrange(1 << 30))
        self._start_local('P')

    def _start_local(self, side):
        self.side = side
        self.sel = None
        self.paused = False
        self.reset_fx()
        self.snap = self.world.snapshot()
        self.snap_age = 0.0
        self.state = "play"
        self.snd.music(True)

    def local_send(self, a):
        self.world.act(self.side, a)

    def ev_play(self, e):
        w = self.world
        if e.type == pygame.KEYDOWN:
            if self.paused:
                if e.key in (pygame.K_p, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.paused = False
                elif e.key == pygame.K_r:
                    self.restart_local()
                elif e.key == pygame.K_ESCAPE:
                    self.snd.music(False)
                    self.state = "map"
                return
            if e.key in (pygame.K_p, pygame.K_ESCAPE):
                self.paused = True
                self.snd.play('select')
                return
            self.game_key(e, self.snap, self.side)
        elif e.type == pygame.MOUSEBUTTONDOWN and not self.paused:
            self.game_click(e, self.snap, self.side, self.local_send)
            self.snap = w.snapshot()

    def restart_local(self):
        w = self.world
        if w.kind == 'sp':
            self.start_level(w.level)
        elif w.kind == 'puzzle':
            self.start_puzzle()
        else:
            self.start_endless()

    def up_play(self, dt):
        w = self.world
        if not self.paused:
            w.update(dt)
        self.handle_events(w.pop_events())
        self.snap = w.snapshot()
        self.smooth_zombies(self.snap, dt)
        if w.result:
            self.finish_local()

    def dr_play(self):
        self.dr_game(self.snap, self.side)
        if self.paused:
            self.dim_box("PAUZA", "P / ENTER pokračovat · R znovu · ESC na mapu")
        self.ticker()

    def finish_local(self):
        w = self.world
        self.snd.music(False)
        win = (w.result == 'P') if w.kind in ('sp', 'endless') else (w.result == 'Z')
        info = {'win': win, 'kind': w.kind, 'lvl': w.level, 'unlock': []}
        if w.kind == 'sp' and win:
            self.save['done'][w.level] = True
            if w.level + 1 < len(LEVELS):
                info['unlock'] = LEVELS[w.level + 1]['new']
            write_save(self.save)
        elif w.kind == 'endless':
            score = max(0, w.wave - 1)
            info['score'] = score
            if score > self.save.get('endless', 0):
                self.save['endless'] = score
                info['record'] = True
                write_save(self.save)
        elif w.kind == 'puzzle' and win:
            self.save['puzzle'] = True
            write_save(self.save)
        self.snd.play('win' if win else 'lose')
        if info['unlock']:
            self.snd.play('unlock')
        self.result_info = info
        self.state = "result"

    def ev_result(self, e):
        if e.type != pygame.KEYDOWN:
            return
        info = self.result_info
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if info['kind'] == 'sp' and info['win']:
                n = info['lvl']
                if n == len(LEVELS) - 1:
                    self.start_ending()
                else:
                    self.map_i = n + 1
                    self.show_story(LEVELS[n + 1]['name'], LEVELS[n + 1]['story'], lambda: self.start_level(n + 1))
            elif info['kind'] == 'puzzle' and info['win']:
                self.state = "map"
            else:
                self.restart_local()
        elif e.key == pygame.K_ESCAPE:
            self.state = "map"

    def up_result(self, dt):
        self.handle_events(self.world.pop_events())
        self.snap = self.world.snapshot()

    def dr_result(self):
        self.dr_game(self.snap, self.side)
        info = self.result_info
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 12, 0, 170) if info['win'] else (24, 0, 0, 180))
        self.canvas.blit(s, (0, 0))
        k = info['kind']
        if k == 'sp':
            if info['win']:
                self.glitch_text("SKLENÍK VYDRŽEL", self.f_big, (W // 2, 200), ACID)
                self.txt("Za oknem sutin něco zelená.", self.f_norm, TEXT, (W // 2, 250), "center")
                if info['unlock']:
                    self.panel(W // 2 - 300, 290, 600, 180, "NOVÉ SEMENO", HOPE)
                    for i, pk in enumerate(info['unlock']):
                        x = W // 2 - 140 + i * 280 if len(info['unlock']) > 1 else W // 2 - 140
                        self.draw_plant(self.canvas, pk, x - 80, 420, self.t, s=1.2)
                        self.txt(PLANTS[pk]['name'], self.f_normb, HOPE, (x - 30, 330))
                        for j, ln in enumerate(self.wrap(PLANTS[pk]['desc'], self.f_tiny, 200)[:4]):
                            self.txt(ln, self.f_tiny, TEXT, (x - 30, 356 + j * 16))
                nxt = "ENTER — pokračovat" if info['lvl'] < len(LEVELS) - 1 else "ENTER — co bude dál?"
                self.txt(nxt + "      ESC — mapa", self.f_normb, TEXT, (W // 2, 520), "center")
            else:
                self.glitch_text("SKLENÍK PADL", self.f_big, (W // 2, 220), WARN, amt=5)
                self.txt("Asimilovaní pronikli dovnitř. Semínka byla zabavena.", self.f_norm, TEXT, (W // 2, 275), "center")
                self.txt("ENTER — znovu      ESC — mapa", self.f_normb, TEXT, (W // 2, 360), "center")
        elif k == 'endless':
            self.glitch_text("NOC TĚ POHLTILA", self.f_big, (W // 2, 220), WARN)
            self.txt("Přežité vlny: %d" % info.get('score', 0), self.f_med, ACID, (W // 2, 280), "center")
            if info.get('record'):
                self.txt("NOVÝ REKORD", self.f_normb, HOPE, (W // 2, 320), "center")
            self.txt("ENTER — znovu      ESC — mapa", self.f_normb, TEXT, (W // 2, 380), "center")
        else:
            if info['win']:
                self.glitch_text("VŠECHNA SEMÍNKA DOMA", self.f_big, (W // 2, 210), HOPE)
                self.txt("Pod Sektorem 9 vyrazily první klíčky. Tam, kde je nikdo nehledá.", self.f_norm, TEXT, (W // 2, 265), "center")
                self.txt("Děkujeme, zahradníku.", self.f_normb, ACID, (W // 2, 300), "center")
                self.txt("ENTER — mapa", self.f_normb, TEXT, (W // 2, 380), "center")
            else:
                self.glitch_text("ZLOBA DOŠLA", self.f_big, (W // 2, 220), WARN)
                self.txt("Semínka zůstala v kořenech. Zkus jiné pořadí nebo jiné řady.", self.f_norm, TEXT, (W // 2, 275), "center")
                self.txt("ENTER — znovu      ESC — mapa", self.f_normb, TEXT, (W // 2, 360), "center")
        self.ticker()

    # ================================================================ ZÁVĚR
    def start_ending(self):
        self.save['secret'] = True
        write_save(self.save)
        self.ending_t = 0.0
        self.reset_fx()
        self.state = "ending"
        self.snd.play('beam')
        self.handle_events([['bird']])

    def ev_ending(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
            if self.ending_t > len(ENDING) * 3.0 or e.key == pygame.K_ESCAPE:
                self.map_i = 5
                self.state = "map"
            else:
                self.ending_t = len(ENDING) * 3.0 + 0.1

    def up_ending(self, dt):
        before = int(self.ending_t / 3.0)
        self.ending_t += dt
        if int(self.ending_t / 3.0) != before and int(self.ending_t / 3.0) < len(ENDING):
            if random.random() < 0.6:
                self.handle_events([['bird']])
            if int(self.ending_t / 3.0) == len(ENDING) - 1:
                self.snd.play('unlock')
        if random.random() < 0.08:
            self.fx('bloom', random.uniform(BX, BOARD_R), random.uniform(BY + 50, BY + LANES * CH))

    def dr_ending(self):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        k = min(1.0, self.ending_t / 12)
        sun = pygame.Surface((W, H), pygame.SRCALPHA)
        sun.fill((255, 220, 140, int(70 * k)))
        c.blit(sun, (0, 0))
        pygame.draw.circle(c, mix((60, 50, 30), (255, 230, 150), k), (W - 180, 60), int(20 + 30 * k))
        self.beam_s.set_alpha(int(255 * k))
        c.blit(self.beam_s, (W // 2 - 70, 0))
        for i in range(int(k * 18)):
            r = random.Random(i)
            self.draw_plant(c, r.choice(['pamp', 'lampa', 'trn']), BX + r.randint(0, COLS - 1) * CW + CW // 2,
                            lane_fy(r.randint(0, LANES - 1)), self.t, s=0.9)
        self.draw_particles()
        self.draw_birds()
        box = pygame.Surface((W, 260), pygame.SRCALPHA)
        box.fill((0, 0, 0, 150))
        c.blit(box, (0, 230))
        n = min(len(ENDING), int(self.ending_t / 3.0) + 1)
        for i in range(n):
            col = HOPE if i >= len(ENDING) - 2 else TEXT
            self.txt(ENDING[i], self.f_normb, col, (W // 2, 250 + i * 32), "center")
        if self.ending_t > len(ENDING) * 3.0 and int(self.t * 2) % 2:
            self.txt("ENTER — mapa", self.f_small, AMBER, (W // 2, H - 52), "center")

    # ================================================================ ATLAS
    def ev_atlas(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                self.atlas_page = 1 - self.atlas_page
                self.snd.play('tick')
            elif e.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "menu"

    def up_atlas(self, dt):
        pass

    def dr_atlas(self):
        c = self.canvas
        c.fill(BG)
        self.header("ATLAS // " + ("ROSTLINY" if self.atlas_page == 0 else "ASIMILOVANÍ"))
        keys = PLANT_ORDER if self.atlas_page == 0 else ZOMB_ORDER + ['boss']
        for i, k in enumerate(keys):
            col, row = i % 2, i // 2
            x, y = 40 + col * 530, 50 + row * 150
            self.panel(x, y, 510, 140)
            if self.atlas_page == 0:
                d = PLANTS[k]
                self.draw_plant(c, k, x + 60, y + 110, self.t, s=1.0)
                self.txt(d['name'], self.f_normb, ACID, (x + 120, y + 12))
                self.txt("cena %d · obnova %.1fs · výdrž %d" % (d['cost'], d['cd'], d['hp']), self.f_tiny, HOPE, (x + 120, y + 36))
            else:
                d = ZOMBIES[k]
                if k == 'boss':
                    pygame.draw.rect(c, (150, 30, 24), (x + 20, y + 40, 80, 70))
                    pygame.draw.rect(c, (40, 40, 44), (x + 10, y + 50, 16, 50))
                else:
                    self.draw_zombie(c, k, x + 60, y + 128, self.t, 0, 1, 1 if k == 'doz' else 0, self.t,
                                     s=0.6 if k == 'exe' else 1.0)
                self.txt(d['name'], self.f_normb, WARN, (x + 120, y + 12))
                extra = " · štít %d" % d['shield'] if d['shield'] else ""
                self.txt("výdrž %d%s · cena v LAN %s" % (d['hp'], extra, d['cost'] or "—"), self.f_tiny, AMBER, (x + 120, y + 36))
            for j, ln in enumerate(self.wrap(d['desc'], self.f_small, 370)[:4]):
                self.txt(ln, self.f_small, TEXT, (x + 120, y + 58 + j * 19))
        self.txt("←→ přepnout stránku · ESC zpět", self.f_small, DIM, (W // 2, H - 52), "center")
        self.ticker()

    # ================================================================ LAN — NASTAVENÍ HOSTITELE
    def ev_host_setup(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.state = "menu"
        elif e.key == pygame.K_UP:
            self.hs_i = (self.hs_i - 1) % 3
            self.snd.play('tick')
        elif e.key == pygame.K_DOWN:
            self.hs_i = (self.hs_i + 1) % 3
            self.snd.play('tick')
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            d = -1 if e.key == pygame.K_LEFT else 1
            if self.hs_i == 0:
                self.hs_mode = (self.hs_mode + d) % len(PVP_ORDER)
            elif self.hs_i == 1:
                self.hs_side = 1 - self.hs_side
            self.snd.play('tick')
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.hs_i < 2:
                self.hs_i += 1
            else:
                self.snd.play('select')
                self.start_host()

    def up_host_setup(self, dt):
        pass

    def dr_host_setup(self):
        c = self.canvas
        c.fill(BG)
        self.header("LAN // NOVÁ HRA")
        self.glitch_text("SOUBOJ O SKLENÍK", self.f_big, (W // 2, 110), TEXT)
        m = PVP_MODES[PVP_ORDER[self.hs_mode]]
        rows = [("MÓD", "◀ " + m['name'] + " ▶"),
                ("TVOJE STRANA", "◀ " + ("KYTKY" if self.hs_side == 0 else "ZOMBIE") + " ▶"),
                ("", "ZALOŽIT HRU")]
        for i, (lab, val) in enumerate(rows):
            y = 200 + i * 70
            sel = i == self.hs_i
            if sel:
                pygame.draw.rect(c, (30, 40, 14), (W // 2 - 300, y - 8, 600, 44))
                pygame.draw.rect(c, ACID, (W // 2 - 300, y - 8, 600, 44), 1)
            if lab:
                self.txt(lab, self.f_small, DIM, (W // 2 - 280, y + 6))
            self.txt(val, self.f_med, ACID if sel else TEXT, (W // 2 + (60 if lab else 0), y + 14), "center")
        for j, ln in enumerate(self.wrap(m['desc'], self.f_norm, 700)):
            self.txt(ln, self.f_norm, HOPE, (W // 2, 430 + j * 26), "center")
        self.txt("Kytky vyhrají, když vydrží do konce limitu. Zombie, když prorazí do skleníku.", self.f_small, DIM, (W // 2, 520), "center")
        self.txt("Zombie mohou útočit až po 20 s přípravy. V odvetě se strany prohodí.", self.f_small, DIM, (W // 2, 545), "center")
        self.txt("↑↓ řádek · ←→ změna · ENTER · ESC zpět", self.f_small, DIM, (W // 2, H - 52), "center")
        self.ticker()

    # ================================================================ LAN — HOST
    def start_host(self):
        self.cleanup_net()
        self.pvp_mode = PVP_ORDER[self.hs_mode]
        self.host = HostServer(self.name)
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
            self.net = Net(conn)
            self.is_host = True
            self.net.send({"t": "hello", "name": self.name, "v": PROTO})
            self.snd.play('select')
            self.host_new_match('P' if self.hs_side == 0 else 'Z')

    def dr_host_wait(self):
        c = self.canvas
        c.fill(BG)
        self.header("LAN // HOSTITEL")
        self.glitch_text("SOUBOJ O SKLENÍK", self.f_big, (W // 2, 120))
        self.panel(W // 2 - 300, 180, 600, 300, "STANOVIŠTĚ HOSTITELE")
        if self.host and self.host.error:
            self.txt(self.host.error, self.f_normb, WARN, (W // 2, 300), "center")
        else:
            self.txt("Čekám na druhého hráče" + "." * (int(self.t * 2) % 4), self.f_med, AMBER, (W // 2, 230), "center")
            self.txt("Na druhém PC zvol  LAN: PŘIPOJIT SE", self.f_norm, TEXT, (W // 2, 285), "center")
            self.txt("Tvoje adresa v síti:", self.f_small, DIM, (W // 2, 330), "center")
            for i, ip in enumerate(self.host_ips[:3]):
                self.txt("%s : %d" % (ip, PORT), self.f_med, ACID, (W // 2, 365 + i * 34), "center")
        self.txt("ESC — zrušit", self.f_small, DIM, (W // 2, H - 52), "center")
        self.ticker()

    def host_new_match(self, my_side):
        self.side = my_side
        self.world = World('pvp', pvp_mode=self.pvp_mode, seed=random.randrange(1 << 30))
        self.net.send({"t": "setup", "mode": self.pvp_mode, "side": 'Z' if my_side == 'P' else 'P', "name": self.name})
        self.snap = self.world.snapshot()
        self.snap_age = 0.0
        self.net_buf = []
        self.snap_t = 0.0
        self.sel = None
        self.reset_fx()
        self.pvp_phase = "play"
        self.state = "pvp"
        self.snd.music(True)

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
            elif e.key == pygame.K_DOWN:
                self.join_i = (self.join_i + 1) % n
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
        self.join_hosts = self.disc.poll() if self.disc else []
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
                self.net = Net(val)
                self.is_host = False
                self.world = None
                self.snap = None
                self.net.send({"t": "hello", "name": self.name, "v": PROTO})
                self.snd.play('select')
                self.pvp_phase = "wait"
                self.state = "pvp"
            else:
                self.join_status = "Spojení selhalo: " + val

    def dr_join(self):
        c = self.canvas
        c.fill(BG)
        self.header("LAN // PŘIPOJENÍ")
        self.glitch_text("SOUBOJ O SKLENÍK", self.f_big, (W // 2, 120))
        self.panel(W // 2 - 300, 175, 600, 330, "NALEZENÉ SKLENÍKY V SÍTI")
        hosts = self.join_hosts
        y = 215
        if not hosts:
            self.txt("Hledám hostitele" + "." * (int(self.t * 2) % 4), self.f_norm, DIM, (W // 2, y + 10), "center")
            y += 50
        for i, (ip, (name, _)) in enumerate(hosts[:5]):
            sel = i == self.join_i
            if sel:
                pygame.draw.rect(c, (30, 40, 14), (W // 2 - 270, y - 4, 540, 34))
            self.txt("%s   —   %s" % (name, ip), self.f_normb, ACID if sel else TEXT, (W // 2, y + 13), "center")
            y += 40
        sel = self.join_i == len(hosts)
        y = max(y + 10, 380)
        if sel:
            pygame.draw.rect(c, (30, 40, 14), (W // 2 - 270, y - 4, 540, 34))
        cur = "_" if sel and int(self.t * 3) % 2 else " "
        self.txt("Ručně IP:  " + self.join_ip + cur, self.f_normb, ACID if sel else TEXT, (W // 2, y + 13), "center")
        if self.join_status:
            bad = "selhal" in self.join_status or "Neplat" in self.join_status
            self.txt(self.join_status, self.f_small, WARN if bad else ACID, (W // 2, 470), "center")
        self.txt("↑↓ výběr · ENTER připojit · ESC zpět · (test na 1 PC: 127.0.0.1)", self.f_small, DIM, (W // 2, H - 52), "center")
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

    # ================================================================ LAN — HRA
    def pvp_send(self, a):
        if self.is_host:
            self.world.act(self.side, a)
        elif self.net:
            self.net.send({"t": "act", "a": a})

    def ev_pvp(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.snd.music(False)
                self.cleanup_net()
                self.state = "menu"
                return
            if self.pvp_phase == "over" and self.is_host and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.host_new_match('Z' if self.side == 'P' else 'P')
                return
            if self.snap and self.pvp_phase == "play":
                self.game_key(e, self.snap, self.side)
        elif e.type == pygame.MOUSEBUTTONDOWN and self.snap and self.pvp_phase == "play":
            self.game_click(e, self.snap, self.side, self.pvp_send)

    def up_pvp(self, dt):
        net = self.net
        if net is None:
            self.state = "menu"
            return
        self.snap_age += dt
        for m in net.poll():
            t = m.get("t")
            if t == "hello":
                self.opp_name = str(m.get("name", "?"))[:14]
            elif t == "bye":
                net.alive = False
            elif self.is_host and t == "act" and self.world:
                self.world.act('Z' if self.side == 'P' else 'P', m.get("a"))
            elif not self.is_host and t == "setup":
                self.side = m.get("side", 'Z')
                self.pvp_mode = m.get("mode", 'klasika')
                self.opp_name = str(m.get("name", self.opp_name))[:14]
                self.reset_fx()
                self.sel = None
                self.pvp_phase = "play"
                self.snd.music(True)
            elif not self.is_host and t == "st":
                self.snap = m.get("s")
                self.snap_age = 0.0
                self.handle_events(m.get("ev", []))
        if not net.alive and self.pvp_phase != "gone":
            self.pvp_phase = "gone"
            self.snd.music(False)
            self.snd.play('lose')
            return
        if self.is_host and self.world:
            w = self.world
            w.update(dt)
            evs = w.pop_events()
            self.handle_events(evs)
            self.net_buf.extend(evs)
            self.snap = w.snapshot()
            self.snap_age = 0.0
            self.snap_t -= dt
            if self.snap_t <= 0 or w.result:
                self.snap_t = SNAP_DT
                net.send({"t": "st", "s": self.snap, "ev": self.net_buf})
                self.net_buf = []
        if self.snap:
            self.smooth_zombies(self.snap, dt)
            if self.snap.get('res') and self.pvp_phase == "play":
                self.pvp_phase = "over"
                self.snd.music(False)
                self.snd.play('win' if self.snap['res'] == self.side else 'lose')

    def dr_pvp(self):
        if not self.snap or self.pvp_phase == "wait":
            self.canvas.fill(BG)
            self.header("LAN // SOUBOJ")
            self.dim_box("SPOJENO", "Čekám, až hostitel spustí hru…")
            if self.pvp_phase == "gone":
                self.dim_box("SPOJENÍ PŘERUŠENO", "Soupeř opustil skleník. ESC — menu", WARN)
            self.ticker()
            return
        self.dr_game(self.snap, self.side)
        self.txt("vs " + self.opp_name, self.f_tiny, DIM, (W - 20, BY + LANES * CH + 30), "topright")
        if self.pvp_phase == "over":
            won = self.snap['res'] == self.side
            who = "KYTKY" if self.snap['res'] == 'P' else "ZOMBIE"
            sub = ("ENTER — odveta (strany se prohodí)   ESC — menu" if self.is_host
                   else "Čekám, až hostitel spustí odvetu…   ESC — menu")
            self.dim_box(("VÍTĚZSTVÍ — " if won else "PROHRA — ") + "VYHRÁLY " + who, sub, ACID if won else WARN)
        elif self.pvp_phase == "gone":
            self.dim_box("SPOJENÍ PŘERUŠENO", "Soupeř opustil skleník. ESC — menu", WARN)
        self.ticker()

    # ================================================================ NAČÍTÁNÍ
    def loading(self, frac, msg):
        pygame.event.pump()
        self.canvas.blit(self.bg, (0, 0))
        self.header()
        self.glitch_text("ZÁHON", self.f_huge, (W // 2, 250), ACID, amt=3)
        self.txt(msg, self.f_norm, TEXT, (W // 2, 360), "center")
        pygame.draw.rect(self.canvas, EDGE, (W // 2 - 250, 400, 500, 18), 1)
        pygame.draw.rect(self.canvas, ACID, (W // 2 - 247, 403, int(494 * frac), 12))
        self.present()
        pygame.display.flip()


def main():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("ZÁHON — poslední skleník")
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
