"""Difficulty table, strategies, decks and counters (MAI 5.3). Only the DIFF numbers are tuning knobs (M5-B)."""
DIFF_IDS = ('lehka', 'stredni', 'tezka')
AI_NAMES = {'lehka': 'Zbloudilý mnich', 'stredni': 'Kastelán', 'tezka': 'Mrtvý velmistr'}
DIFFS = [['lehka', 'Lehká', AI_NAMES['lehka']], ['stredni', 'Střední', AI_NAMES['stredni']],
         ['tezka', 'Těžká', AI_NAMES['tezka']]]

# gens: [(t_from, n)] generator target by game time; gen_l2/gen_l3: earliest time for generator upgrades
# (None = never; L2 also comes once gen_l2_towers attack towers stand). push: (first push time, budget floor, seconds of income).
# spend: energy per push as a multiple of the budget (0 = everything), cap: units per push, regap: seconds to the next
# push, lane: 'weak' (least defended rows) or 'random'. ecl_p: share of pushes timed to an eclipse.
# react / parry_ms: N(mean, sd) in s / ms. def_max: cap on standing template items, surplus: extra Kulomet/Plamenomet
# once the template stands, night_build / night_line: rebuild at night / fill local x 0-1 at night, horde_spare: send
# every ready Tlupa when energy >= this (0 = only with pushes). King: repair/escort/guard/king_relic switch goals,
# idle_lx = local column where he waits. Calibrated in M2-C with dev/tests/ai_ladder.py (Lehká vs NoviceBot 51 %).
DIFF = {
    'lehka': {
        'salt': 101, 'think': 1.2, 'acts': 1, 'react': (0.8, 0.3), 'apm': 30, 'steer': 0.35, 'misplace': 0.30,
        'gens': [(0, 3), (240, 4)], 'gen_l2': 600.0, 'gen_l2_towers': None, 'gen_l3': None, 'conv': 'never', 'scrap': False,
        'push': (300.0, 200.0, 0.0), 'spend': 1.0, 'cap': 2, 'regap': 60.0, 'lane': 'random', 'ecl_p': 0.0, 'allin': False, 'def_scale': 0.4, 'def_max': 12, 'surplus': 0, 'night_build': True, 'night_line': False, 'upg_max': 1,
        'scout': 1, 'drone_every': None, 'reflektor': False, 'relic': 'lehka', 'crates': 'own', 'cards': 'nalet',
        'horde': 'never', 'horde_spare': 0, 'anti_mate': False, 'parry_p': 0.25, 'parry_ms': (420, 90), 'dash_p': 0.0, 'retreat': 0.20, 'repair': True, 'escort': False, 'guard': False, 'idle_lx': 0, 'king_relic': True,
        'danger': 'never', 'strats': [('mixed', 1.0)], 'adapt': False, 'rush': False, 'emerg': 0.5,
    },
    'stredni': {
        'salt': 202, 'think': 0.6, 'acts': 2, 'react': (0.45, 0.15), 'apm': 60, 'steer': 0.2, 'misplace': 0.07,
        'gens': [(0, 3), (60, 4), (150, 5)], 'gen_l2': 240.0, 'gen_l2_towers': 5, 'gen_l3': None, 'conv': 'scrap', 'scrap': True,
        'push': (120.0, 300.0, 35.0), 'spend': 2.0, 'cap': 12, 'regap': 30.0, 'lane': 'weak', 'ecl_p': 0.5, 'allin': False, 'def_scale': 0.85, 'def_max': 99, 'surplus': 0, 'night_build': True, 'night_line': False, 'upg_max': 3,
        'scout': 1, 'drone_every': 90.0, 'reflektor': False, 'relic': 'contest', 'crates': 'free', 'cards': 'all',
        'horde': 'push', 'horde_spare': 0, 'anti_mate': True, 'parry_p': 0.60, 'parry_ms': (330, 60), 'dash_p': 0.30, 'retreat': 0.35, 'repair': True, 'escort': True, 'guard': True, 'idle_lx': 2, 'king_relic': True,
        'danger': 'hurt', 'strats': [('mixed', 0.6), ('turtle', 0.4)], 'adapt': False, 'rush': False, 'emerg': 1.0,
    },
    'tezka': {
        'salt': 303, 'think': 0.3, 'acts': 3, 'react': (0.25, 0.08), 'apm': 120, 'steer': 0.1, 'misplace': 0.0,
        'gens': [(0, 3), (45, 4), (90, 5)], 'gen_l2': 120.0, 'gen_l2_towers': 5, 'gen_l3': 0.0, 'conv': 'yes', 'scrap': True,
        'push': (90.0, 300.0, 40.0), 'spend': 0.0, 'cap': 24, 'regap': 15.0, 'lane': 'weak', 'ecl_p': 1.0, 'allin': True, 'def_scale': 1.0, 'def_max': 99, 'surplus': 9, 'night_build': True, 'night_line': True, 'upg_max': 3,
        'scout': 2, 'drone_every': 60.0, 'reflektor': True, 'relic': 'retake', 'crates': 'all', 'cards': 'smart',
        'horde': 'mist', 'horde_spare': 600, 'anti_mate': True, 'parry_p': 0.90, 'parry_ms': (280, 40), 'dash_p': 0.80, 'retreat': 0.45, 'repair': True, 'escort': True, 'guard': True, 'idle_lx': 2, 'king_relic': False,
        'danger': 'always', 'strats': [('mixed', 0.35), ('turtle', 0.5), ('rush', 0.15)], 'adapt': True, 'rush': True,
        'emerg': 1.0,
    },
}

STRATEGIES = ('mixed', 'turtle', 'rush')
DECKS = {
    'mixed': ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'obrnenec', 'medik', 'nalet'],
    'turtle': ['sniper', 'hlaska', 'kulomet', 'plamen', 'pesak', 'obrnenec', 'nalet', 'vypadek'],
    'rush': ['kulomet', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'strelec', 'medik', 'vypadek'],
}
RESEARCH = {'def': ['ing1', 'arm1', 'ing2', 'ing3', 'arm2'], 'off': ['arm1', 'arm2', 'ing1', 'arm3']}
STRAT_RESEARCH = {'mixed': 'def', 'turtle': 'def', 'rush': 'off'}

# Defence templates (local x, row) in the harness Mixed order. Rows are remapped by the map weight at runtime.
L1 = [('kulomet', 2, 4), ('hlaska', 3, 4), ('plamen', 2, 3), ('plamen', 2, 5), ('sniper', 1, 4)]
L2 = [('kulomet', 2, 2), ('kulomet', 2, 6), ('plamen', 2, 1), ('plamen', 2, 7), ('kulomet', 2, 0), ('kulomet', 2, 8),
      ('sniper', 1, 2), ('sniper', 1, 6)]
WALLS = [('zed', 3, y) for y in (3, 5, 2, 6, 1, 7, 0, 8)]
TEMPLATES = {
    'mixed': L1 + L2 + WALLS,
    'turtle': [('kulomet', 2, 4), ('hlaska', 3, 4), ('sniper', 1, 4), ('sniper', 1, 2), ('sniper', 1, 6),
               ('plamen', 2, 3), ('plamen', 2, 5), ('sniper', 1, 3), ('sniper', 1, 5), ('kulomet', 2, 2),
               ('kulomet', 2, 6), ('plamen', 2, 1), ('plamen', 2, 7), ('kulomet', 2, 0), ('kulomet', 2, 8)] + WALLS,
    'rush': [('kulomet', 2, 4), ('hlaska', 3, 4), ('kulomet', 2, 2), ('kulomet', 2, 6), ('kulomet', 2, 3),
             ('kulomet', 2, 5), ('kulomet', 2, 1), ('kulomet', 2, 7)] + WALLS[:4],
}
# how many template items may stand by game time (before def_scale)
TEMPLATE_PACE = [(0, 5), (150, 9), (240, 13), (330, 21), (420, 99)]

# attack compositions (harness COMPS) and stagger delays
COMPS = {
    'mix': ['obrnenec', 'pesak', 'obrnenec', 'pesak', 'medik', 'strelec', 'pesak', 'jezdec'],
    'tank': ['obrnenec', 'obrnenec', 'medik', 'pesak', 'pesak', 'pesak'],
    'flank': ['jezdec', 'obrnenec', 'jezdec', 'pesak', 'jezdec', 'medik'],
    'mines': ['pesak', 'pesak', 'obrnenec', 'pesak', 'medik', 'obrnenec'],
    'rush': ['pesak', 'pesak', 'pesak', 'pesak', 'obrnenec'],
}
STAGGER = {'obrnenec': 0.0, 'dama': 0.0, 'pesak': 4.0, 'medik': 4.0, 'strelec': 5.0, 'jezdec': 8.0}
# upgrade paths at level 3
UP_PATH = {'kulomet': 'A', 'plamen': 'A', 'tesla': 'B', 'gen': 'A', 'hlaska': 'A', 'rusicka': 'B', 'mina': 'A',
           'dilna': 'A', 'hangar': 'B', 'hnizdo': 'A'}

# ---------------------------------------------------------------------------------------------------------------
# M3-C: faction plans (FAC 8 FacMixin, ported to the AI). Per faction:
#   decks   strategy -> 8 cards (valid_deck for that faction)
#   insert  strategy -> template items put right after the first tower block (index 5 of the template)
#   comps   comp name -> attack composition (items not in the deck are dropped, unit cards that cannot be deployed yet
#           are swapped by facplay.sub: Exo -> Obrněnec before Doba II or at 3 Exos)
#   P       DIFF overrides for this faction (copied into the AI's own profile)
# The logic (Dílna/Hnízdo timing, EMP, Mor, war cry, Volání mrtvých) is in facplay.py.
# ---------------------------------------------------------------------------------------------------------------
FACTION_PLAN = {
    'prez': {
        'decks': {
            'mixed': ['kulomet', 'plamen', 'sniper', 'hlaska', 'ostnata', 'dilna', 'pesak', 'obrnenec'],
            'turtle': ['sniper', 'hlaska', 'kulomet', 'plamen', 'ostnata', 'dilna', 'pesak', 'obrnenec'],
            'rush': ['kulomet', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'mrchozrout', 'medik', 'vypadek'],
        },
        'insert': {s: [('ostnata', 3, 3), ('ostnata', 3, 5), ('ostnata', 3, 2), ('ostnata', 3, 6)]
                   for s in ('mixed', 'turtle')},
        'comps': {
            'mix': ['obrnenec', 'pesak', 'obrnenec', 'mrchozrout', 'medik', 'strelec', 'pesak', 'jezdec'],
            'tank': ['obrnenec', 'obrnenec', 'medik', 'pesak', 'mrchozrout', 'pesak'],
            'mines': ['mrchozrout', 'pesak', 'obrnenec', 'pesak', 'medik', 'obrnenec'],
            'rush': ['pesak', 'mrchozrout', 'pesak', 'pesak', 'obrnenec'],
        },
        'P': {'repair_hp': 0.95},
    },
    'korp': {
        'decks': {
            'mixed': ['kulomet', 'tesla', 'sniper', 'hlaska', 'hangar', 'pesak', 'obrnenec', 'emp'],
            'turtle': ['sniper', 'hlaska', 'kulomet', 'tesla', 'hangar', 'emp', 'pesak', 'obrnenec'],
            'rush': ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'exo', 'emp', 'vypadek'],
        },
        'insert': {s: [('tesla', 3, 3), ('tesla', 3, 5), ('hangar', 3, 2), ('hangar', 3, 6)] for s in ('mixed', 'turtle')},
        'comps': {
            'mix': ['obrnenec', 'pesak', 'exo', 'pesak', 'medik', 'strelec', 'pesak', 'jezdec'],
            'tank': ['obrnenec', 'exo', 'medik', 'pesak', 'pesak', 'pesak'],
            'mines': ['pesak', 'pesak', 'exo', 'pesak', 'medik', 'obrnenec'],
            'rush': ['pesak', 'pesak', 'pesak', 'exo', 'obrnenec'],
        },
        'P': {},
    },
    'kult': {
        'decks': {
            'mixed': ['kulomet', 'plamen', 'sniper', 'hlaska', 'hnizdo', 'pesak', 'obrnenec', 'mor'],
            'turtle': ['sniper', 'hlaska', 'kulomet', 'plamen', 'hnizdo', 'pesak', 'obrnenec', 'mor'],
            'rush': ['kulomet', 'hlaska', 'pesak', 'obrnenec', 'medik', 'nekromant', 'hnizdo', 'mor'],
        },
        'insert': {},
        'comps': {
            'mix': ['obrnenec', 'pesak', 'nekromant', 'pesak', 'medik', 'strelec', 'pesak', 'jezdec'],
            'tank': ['obrnenec', 'obrnenec', 'nekromant', 'pesak', 'pesak', 'pesak'],
            'mines': ['pesak', 'pesak', 'obrnenec', 'nekromant', 'medik', 'obrnenec'],
            'rush': ['pesak', 'pesak', 'nekromant', 'pesak', 'obrnenec'],
        },
        'P': {'horde_spare': 60},        # Tlupa whenever off cooldown and energy >= cost + 60 (FAC 8)
    },
}

# ---------------------------------------------------------------------------------------------------------------
# M3-C: Přežití profile (MAI 6): no pushes, no Relikvie. Units only for crates (a runner Pěšák when neither the King
# nor the Sběrný dron will fetch it) and for clearing the own Mist half (clear_n zombies there and clear_e energy);
# Tlupa from Střední up (horde_spare = energy kept in reserve). pace_free: the defence template is not paced by time
# (nothing is spent on pushes), surplus: extra towers once the template stands.
# ---------------------------------------------------------------------------------------------------------------
PREZITI = {
    'lehka': {'crates': 'own', 'horde': 'never', 'horde_spare': 0, 'pace_free': False, 'surplus': 0,
              'clear_n': 99, 'clear_e': 9999, 'runner': True},
    'stredni': {'crates': 'own', 'horde': 'push', 'horde_spare': 300, 'pace_free': True, 'surplus': 6, 'def_scale': 1.0,
                'clear_n': 8, 'clear_e': 320, 'runner': True},
    'tezka': {'crates': 'own', 'horde': 'push', 'horde_spare': 150, 'pace_free': True, 'surplus': 14, 'def_scale': 1.0,
              'clear_n': 5, 'clear_e': 260, 'runner': True},
}
PREZITI_DECK = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'obrnenec', 'medik', 'nalet']
