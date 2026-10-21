"""All game constants and rule tables (0.5 values). Tunables are read as D.NAME at the use site (tooling patches them here)."""
from . import VERSION  # noqa: F401  (re-exported for the defs message)

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
SAMPLE_DT = 5                 # time series step for the end graphs (game seconds)
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
    if _d['cat'] == 'b' and 'up' not in _d:
        _c = _d['cost'][0]
        _d['up'] = [[round(_c * 0.7), 15], [_c, 25]]
CARD_POOL = [k for k, d in DEFS.items() if d['cat'] in 'bua' and k not in BASE_KIT]
ABILITIES = [k for k, d in DEFS.items() if d['cat'] == 'a']
ATTACK_TOWERS = ('kulomet', 'plamen', 'sniper', 'tesla', 'hangar')   # hangar: Korporace card (hmk.factions)
KRAL = DEFS['kral']

# Stratég mode: commander abilities instead of a King
CMDS = {
    'oprava': {'name': 'Oprava', 'key': 'Q', 'cd': 20, 'target': 'own', 'desc': 'Opraví tvou stavbu o 40 % životů.'},
    'odstrel': {'name': 'Odstřel', 'key': 'W', 'cd': 12, 'target': 'vis', 'dmg': 90,
                'desc': 'Zasáhne viditelné pole (90 poškození) a 5 s ho osvětluje, i za tmy.'},
    'sber': {'name': 'Sběrný dron', 'key': 'E', 'cd': 25, 'target': 'crate',
             'desc': 'Dron doletí k bedně, osvětlí ji a 3 s ji nakládá. Sestřelí ho nepřítel blíž než 1,5 pole nebo Odstřel.'},
    'stit': {'name': 'Štít trůnu', 'key': 'R', 'cd': 45, 'target': None, 'dur': 6, 'desc': 'Trůn 6 s dostává o 80 % méně poškození.'},
    'utok': {'name': 'Útok!', 'key': 'G', 'cd': 70, 'target': None, 'dur': 6, 'doba': 2,   # [global] 1.0: Doba II (compat05: I)
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


def valid_deck(deck, fac='bez'):
    """8 distinct cards from pool_of(fac) (shared pool + the faction's own cards), else None."""
    from .factions import pool_of
    pool = pool_of(fac if isinstance(fac, str) else 'bez')
    if (isinstance(deck, list) and len(deck) == DECK_SIZE and all(isinstance(c, str) for c in deck)
            and len(set(deck)) == DECK_SIZE and all(c in pool for c in deck)):
        return list(deck)
    return None


# game types (lobby segment, defs message); ids per SPEC 2.1
TYPES = [
    {'id': 'souboj', 'name': 'Souboj', 'desc': 'Hra proti druhému hráči v síti.'},
    {'id': 'preziti', 'name': 'Přežití', 'desc': 'Ubraň trůn co nejdéle před sílícími vlnami zombií.'},
    {'id': 'vycvik', 'name': 'Výcvik', 'desc': 'Zápas proti počítači ve třech obtížnostech.'},
    {'id': 'puzzle', 'name': 'Puzzle', 'desc': 'Deset připravených úloh, každá až za tři hvězdy.'},
    {'id': 'vyuka', 'name': 'Výuka', 'desc': 'Krok za krokem se naučíš základy hry.'},
]
TYPE_IDS = tuple(t['id'] for t in TYPES)
