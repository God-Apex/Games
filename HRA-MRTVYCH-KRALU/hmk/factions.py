"""Factions (FAC 2-5, SPEC 5.3): data, the cost rule, pools, recommended decks and the defs catalogue.
Faction cards are merged into D.DEFS at import (keyed by 'fac'); CARD_POOL and ABILITIES never contain them."""
import math

from . import defs as D

FAC_IDS = ('bez', 'prez', 'korp', 'kult')
OWNED_CAP = 30                # max owned zombies alive per side; spawns, raises and turns beyond it are skipped

FACTIONS = {
    'bez': {'name': 'Bez frakce', 'motto': 'Původní pravidla.', 'cards': [], 'mods': {}, 'perk': None, 'cmd': {},
            'desc': 'Hra bez zvláštních pravidel. Doporučeno na první zápasy.', 'passives': []},
    'prez': {'name': 'Přeživší', 'motto': 'Co spravíš, to vydrží.', 'cards': ['ostnata', 'dilna', 'mrchozrout'],
             'desc': 'Levné stavby, pevné zdi a šrot z ruin. Brání se dobře, útočí dráž.',
             'mods': {'bcost': 0.8, 'bcost_ex': ['gen', 'sniper'], 'zed_hp': 1.4, 'zed_cost': 10, 'ucost': 1.1,
                      'repair': 80.0, 'repair_hp': 20.0},
             'passives': ['Stavby kromě Generátoru a Odstřelovače stojí o 20 % méně energie.',
                          'Zdi mají o 40 % víc životů a stojí jen 10 🔩.',
                          'Jednotky stojí o 10 % víc energie.'],
             'perk': {'name': 'Kovář', 'desc': 'Král opravuje rychleji (80 životů/s) a za 1 🔩 opraví 20 životů místo 10.'},
             'cmd': {'oprava': {'name': 'Svépomoc', 'splash': 0.2,
                                'desc': 'Opraví tvou stavbu o 40 % životů a stavby kolem ní o 20 %.'}}},
    'korp': {'name': 'Korporace', 'motto': 'Technologie má svou cenu.', 'cards': ['hangar', 'exo', 'emp'],
             'desc': 'Rychlý výzkum, Tesla hned od začátku, drony a EMP. Všechno ostatní je dražší.',
             'mods': {'bcost': 1.1, 'bcost_ex': ['gen'], 'ucost': 1.1, 'res1': 1, 'doba': {'tesla': 1},
                      'dron': [30, 15, 3.0], 'arc': [3, 3, 1.6]},
             'passives': ['Výzkum 1. stupně stojí jen 1 🧪.',
                          'Tesla cívka už od Doby I. Průzkumný dron stojí 30 ⚡, obnova 15 s, poloměr 3 pole.',
                          'Sdílené stavby (kromě Generátoru) a jednotky stojí o 10 % víc energie.'],
             'perk': {'name': 'Tesla-rukavice', 'desc': 'Každý 3. výstřel Krále přeskočí až na 3 další nepřátele do 1,6 pole.'},
             'cmd': {'sber': {'name': 'Dronová letka', 'cd': 15, 'speed': 6.0, 'scan': 2.0,
                              'desc': 'Rychlý dron (obnova 15 s) cestou odhaluje okolí 2 polí. U bedny ji 3 s nakládá.'}}},
    'kult': {'name': 'Kult', 'motto': 'Mrtví slouží živým.', 'cards': ['hnizdo', 'nekromant', 'mor'],
             'desc': 'Posílá a obrací zombie proti soupeři. Jeho stavby jsou křehké.',
             'mods': {'bhp': 0.8, 'zdmg_in': 0.5, 'horde': [80, 18.0], 'horde_kinds': ['chodec'] * 4 + ['bezec'] * 2,
                      'noloot': True, 'cry_turn': 3.0},
             'passives': ['Tlupa stojí 80 ⚡ (obnova 18 s) a má 2 Běžce. Tvoje zombie soupeři nedají kořist.',
                          'Zombie dávají tvým jednotkám a Králi o 50 % menší poškození.',
                          'Tvoje stavby mají o 20 % méně životů.'],
             'perk': {'name': 'Pán mrtvých', 'desc': 'Válečný pokřik obrátí všechny zombie do 3 polí od Krále (kromě Alfy) proti soupeři.'},
             'cmd': {'utok': {'name': 'Volání mrtvých', 'turn': True,
                              'desc': 'Jako Útok! a navíc se všechny zombie v Mlze, které jdou na tebe, obrátí na soupeře.'}}},
}

FAC_DEFS = {
    # ---- Přeživší
    'ostnata': {'cat': 'b', 'fac': 'prez', 'name': 'Ostnatá zeď', 'cost': [0, 20], 'hp': 450, 'vision': 1.5,
                'hps': [450, 1000, 1800], 'levels': ['Ostnatá', 'Drátěná', 'Ocelová'], 'up': [[0, 25], [0, 45]], 'thorns': 0.35,
                'desc': 'Zeď s ostny. Kdo do ní bije zblízka, dostane zpět 35 % poškození. Tvoje jednotky i Král projdou.'},
    'dilna': {'cat': 'b', 'fac': 'prez', 'name': 'Dílna', 'cost': [70, 0], 'hp': 200, 'vision': 1.5, 'max': 2, 'scrap': [0.6, 0.9, 1.2],
              'desc': 'Vyrábí šrot: 0,6 🔩/s, na úrovni 3 1,2 🔩/s. Smíš mít nejvýš 2.',
              'paths': {'A': ['Šrotiště', '+0,6 🔩/s navíc.'],
                        'B': ['Opravna', 'Tvoje stavby do 1 pole kolem se opravují 5 životů/s.']}},
    'mrchozrout': {'cat': 'u', 'fac': 'prez', 'name': 'Mrchožrout', 'cost': [40, 0], 'hp': 100, 'dmg': 9, 'rate': 0.8, 'step': 1.5,
                   'vision': 2.4, 'chan': 2.0, 'zloot': 2.0,
                   'desc': 'Sběrač z ruin, chodí vpřed i šikmo vpřed. Bednu otevře za 1,5 s místo 3 a zombie, '
                           'které zabije, dají dvojnásobnou kořist.'},
    # ---- Korporace
    'hangar': {'cat': 'b', 'fac': 'korp', 'name': 'Dronový hangár', 'cost': [130, 0], 'hp': 200, 'range': 4.0, 'dmg': 15, 'rate': 0.7,
               'vision': 3.5, 'dark_vis': 3.0,
               'desc': 'Útočné drony: dosah 4 pole, dohled 3,5 pole, za tmy 3.',
               'paths': {'A': ['Roj', 'Zasáhne 2 cíle naráz.'], 'B': ['Rušivý dron', 'Zasažený cíl zpomalí o 40 % na 1,5 s.']}},
    'exo': {'cat': 'u', 'fac': 'korp', 'name': 'Exoskelet', 'cost': [160, 0], 'hp': 360, 'dmg': 20, 'rate': 0.8, 'step': 1.7, 'vision': 2.6,
            'doba': 2, 'bld': 1.5, 'max': 3, 'sh': 120, 'sh_regen': 15.0, 'sh_wait': 3.0,
            'desc': 'Chodí i útočí o 1 pole všemi směry. Štít pohltí 120 poškození a obnovuje se, když 3 s nedostane zásah. Nejvýš 3.'},
    'emp': {'cat': 'a', 'fac': 'korp', 'name': 'EMP výboj', 'cost': [90, 0], 'cd': 50, 'target': 'vis', 'dur': 4.0, 'stun': 1.5,
            'desc': 'Zasáhne 3×3 pole: soupeřovy stavby tam 4 s nefungují, jednotky, Král i zombie jsou 1,5 s omráčení. Cíl musíš vidět.'},
    # ---- Kult
    'hnizdo': {'cat': 'b', 'fac': 'kult', 'name': 'Hnízdo', 'cost': [90, 0], 'hp': 250, 'vision': 1.5, 'max': 2, 'every': [15, 12, 10],
               'desc': 'Každých 15 s (na úrovni 3 každých 10 s) vypustí z Mlhy Chodce na soupeře. Smíš mít nejvýš 2.',
               'paths': {'A': ['Líheň', 'Místo Chodce vypustí 2 Běžce.'], 'B': ['Obří plod', 'Každý 5. vypuštěný je Obr.']}},
    'nekromant': {'cat': 'u', 'fac': 'kult', 'name': 'Nekromant', 'cost': [90, 0], 'hp': 110, 'dmg': 6, 'rate': 1.0, 'step': 1.8,
                  'vision': 2.4, 'raise': 2.0, 'raise_cd': 3.0,
                  'desc': 'Kdo padne do 2 polí od něj (soupeřova jednotka nebo zombie mířící na tebe), vstane jako tvůj Chodec. '
                          'Nejvýš 1 za 3 s.'},
    'mor': {'cat': 'a', 'fac': 'kult', 'name': 'Mor', 'cost': [80, 0], 'cd': 40, 'target': 'vis', 'dur': 8.0, 'dps': 10,
            'desc': 'Morový mrak na 3×3 polích na 8 s: soupeřovy jednotky a Král v něm ztrácejí 10 životů/s. '
                    'Kdo v něm padne, vstane jako tvůj Chodec.'},
}
for _k, _d in FAC_DEFS.items():
    if _d['cat'] == 'b' and 'up' not in _d:
        _c = _d['cost'][0]
        _d['up'] = [[round(_c * 0.7), 15], [_c, 25]]
    D.DEFS.setdefault(_k, _d)

RECOMMENDED_F = {
    'bez': list(D.RECOMMENDED),
    'prez': ['kulomet', 'plamen', 'sniper', 'hlaska', 'ostnata', 'dilna', 'pesak', 'mrchozrout'],
    'korp': ['kulomet', 'sniper', 'hlaska', 'tesla', 'hangar', 'pesak', 'obrnenec', 'emp'],
    'kult': ['kulomet', 'plamen', 'sniper', 'hlaska', 'hnizdo', 'pesak', 'nekromant', 'mor'],
}


def r5(v):
    """Round to the nearest 5, halves up (never Python's round(), which rounds halves to even)."""
    return int(5 * math.floor(v / 5 + 0.5))


def mods(fac):
    return FACTIONS.get(fac, FACTIONS['bez'])['mods']


def pool_of(fac):
    return D.CARD_POOL + list(FACTIONS.get(fac, FACTIONS['bez'])['cards'])


def fac_price(fac, kind, base):
    """[e, s] after the faction cost rule (FAC 2). `base` already holds the count escalation (gen, sniper)."""
    m = mods(fac)
    d = D.DEFS[kind]
    if not m or 'fac' in d or kind == 'gen':
        return list(base)
    cat = d['cat']
    if kind == 'zed':
        return [0, m.get('zed_cost', 15)]
    if cat == 'b':
        if 'bcost' in m and kind not in m.get('bcost_ex', ()):
            return [r5(base[0] * m['bcost']), base[1]]
    elif cat == 'u':
        if 'ucost' in m:
            return [r5(base[0] * m['ucost']), base[1]]
    elif cat == 'a' and kind == 'dron' and 'dron' in m:
        return [m['dron'][0], base[1]]
    return list(base)


def base_costs(fac):
    """{kind: [e, s]} base prices (no count escalation) for the faction's whole pool plus the base kit."""
    return {k: fac_price(fac, k, D.DEFS[k]['cost']) for k in list(D.BASE_KIT) + pool_of(fac)}


def research_costs(fac):
    """{rid: samples} for the faction (Korporace: tier 1 costs res1)."""
    m = mods(fac)
    return {rid: (m['res1'] if r['tier'] == 1 and 'res1' in m else r['cost']) for rid, r in D.RESEARCH.items()}


def merged_cmds(fac, compat05=False):
    """{cid: CMDS[cid] merged with the faction's command variant}. compat05: Útok! is not gated."""
    out = {}
    var = FACTIONS.get(fac, FACTIONS['bez'])['cmd']
    for cid, c in D.CMDS.items():
        m = dict(c)
        m.update(var.get(cid, {}))
        if compat05 and cid == 'utok':
            m['doba'] = 1
        out[cid] = m
    return out


def public():
    """Faction catalogue for the defs message (M3-F does msg.update(factions.public()))."""
    facs = {}
    for f in FAC_IDS:
        F = FACTIONS[f]
        facs[f] = {'name': F['name'], 'motto': F['motto'], 'desc': F['desc'], 'passives': list(F['passives']),
                   'cards': list(F['cards']), 'perk': F['perk'],
                   'cmdv': {cid: {'name': v['name'], 'desc': v['desc']} for cid, v in F['cmd'].items()}}
    return {'factions': facs, 'facPool': {f: pool_of(f) for f in FAC_IDS},
            'facCosts': {f: base_costs(f) for f in FAC_IDS}, 'facRec': {f: list(RECOMMENDED_F[f]) for f in FAC_IDS}}
