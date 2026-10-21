# 1.0 design: factions and balance

Scope: three factions plus "Bez frakce" for both modes (Král, Stratég): data, rules, cards, King perks, command variants,
art brief, protocol, and the bot-harness balance gate. Everything here is a decision. The numbers are starting values, and
only the tuning knobs in section 9 may change them.
Global 1.0 rule changes that also affect "Bez frakce" are marked **[global]**.

---

## 1. Decisions at a glance

| | Přeživší (`prez`) | Korporace (`korp`) | Kult (`kult`) | Bez frakce (`bez`) |
|---|---|---|---|---|
| Identity | cheap buildings, strong walls, scrap | early tech, drones, Tesla, EMP | zombie control, weak buildings | 0.5 game |
| Malus | units +10 % ⚡ | shared buildings (not Generátor) and units +10 % ⚡ | own buildings −20 % HP | – |
| Cards | Ostnatá zeď, Dílna, Mrchožrout | Dronový hangár, Exoskelet, EMP výboj | Hnízdo, Nekromant, Mor | – |
| King perk (Král) | Kovář | Tesla-rukavice | Pán mrtvých | – |
| Stratég variant | Oprava → Svépomoc | Sběrný dron → Dronová letka | Útok! → Volání mrtvých | – |

- **[global] Útok! needs Doba II** (`CMDS['utok']['doba'] = 2`, cooldown stays 70 s). See section 10 for the evidence.
- **[global] Owned zombies.** A zombie sent by a player (Tlupa, Nákaza, Hnízdo, Nekromant, Mor, turned zombies) carries
  `own = side`. It never targets its owner's units, King or buildings, and its owner's towers and throne never shoot it.
- The opponent's faction stays hidden in the lobby and is revealed in the `start` message. HUD and lobby text are Czech.
- Faction cards appear only in their own faction's pool. Crate free charges come only from shared abilities.
- Shared rules (map, Doby, research tree, Relikvie, crates, Zatmění, Poslední noc) are the same for every faction.

---

## 2. Data model (server.py)

```python
FAC_IDS = ('bez', 'prez', 'korp', 'kult')
OWNED_CAP = 30            # max owned zombies alive per side; spawns, raises and turns beyond it are skipped
RULES_05 = False          # True: Útok! ungated + owned zombies hostile to owner -> byte-identical 0.5 sim (regression)

FACTIONS = {
  'bez':  {'name': 'Bez frakce', 'motto': 'Původní pravidla.', 'cards': [], 'mods': {}, 'perk': None, 'cmd': {},
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
```

Helpers (new): `fm(s)` returns `FACTIONS[self.sd[s].fac]['mods']`. `r5(v) = 5 * math.floor(v / 5 + 0.5)` rounds to the
nearest 5, with halves going up. Do not use Python's `round()`, because it rounds halves to even.

**Cost rule** (`fac_price(fac, kind, base) -> [e, s]`):
- Faction cards and `gen` are never modified.
- For `zed`, the price is `[0, zed_cost]` (default 15).
- Other buildings: when `bcost` exists and the kind is not in `bcost_ex`, the price is `r5(base_e * bcost)`.
- Units: `r5(base_e * ucost)`.
- Abilities: unchanged, except `dron`, which costs `dron[0]`.

`Game.price(s, kind)` applies the count escalation (`gen_price`, `sniper_price`) first and the faction modifier on top.
It is the only cost source used by `build`, `deploy`, `cast`, `horde` and the snapshot (`gp`, `sp`, `hc`).
**Upgrade costs** (`up`) are never faction-modified.

Resulting price list (⚡):

| | kulomet | plamen | sniper (n=1,2,3,4) | hlaska | tesla | mina | rusicka | zed 🔩 | pesak | jezdec | obrnenec | strelec | medik | saboter | dama |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bez, kult | 50 | 75 | 100,100,140,180 | 40 | 110 | 40 | 60 | 15 | 30 | 70 | 110 | 60 | 55 | 70 | 200 |
| prez | 40 | 60 | 100,100,140,180 | 30 | 90 | 30 | 50 | 10 | 35 | 75 | 120 | 65 | 60 | 75 | 220 |
| korp | 55 | 85 | 110,110,155,200 | 45 | 120 | 45 | 65 | 15 | 35 | 75 | 120 | 65 | 60 | 75 | 220 |

**HP rule** (`max_hp`):
- Buildings with `'hps'` use the level table; this replaces the `kind == 'zed'` test.
- `zed` gets ×`zed_hp`.
- Every building of the side gets ×`bhp`, including faction cards. The throne is not affected.

**Other mods:**
- `res1`: tier-1 research costs that many 🧪.
- `doba[kind]`: overrides the card's Doba requirement. This goes through `need_doba(s, kind)` and is used by build, deploy, cast and the client lock.
- `zdmg_in`: damage multiplier when `src.cat == 'z'` and the target is a unit or King of that side.
- `horde`: `[cost, cd]`. Levná tlupa (bio1) still applies ×0.6 to the cost and sets the cd to 12 s instead of 15 s.
- `noloot`: when a zombie with `own == s` dies, its killer gets no ⚡/🔩/🧪.

---

## 3. Faction cards (exact DEFS entries)

All of them carry `'fac'`. `CARD_POOL` excludes them, and `pool_of(fac) = CARD_POOL + FACTIONS[fac]['cards']`.
`ABILITIES` (crate charges) excludes them.
The generic `up` loop at server.py:140 changes to `if _d['cat'] == 'b' and 'up' not in _d`, so walls that carry their own `up` keep it.
New key `'max'` is a per-side count limit, checked in `build` and `deploy` with the refusal `'%s smíš mít nejvýš %d.'`.

```python
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
              'desc': 'Kdo padne do 2 polí od něj (soupeřova jednotka nebo zombie mířící na tebe), vstane jako tvůj Chodec. Nejvýš 1 za 3 s.'},
'mor': {'cat': 'a', 'fac': 'kult', 'name': 'Mor', 'cost': [80, 0], 'cd': 40, 'target': 'vis', 'dur': 8.0, 'dps': 10,
        'desc': 'Morový mrak na 3×3 polích na 8 s: soupeřovy jednotky a Král v něm ztrácejí 10 životů/s. Kdo v něm padne, vstane jako tvůj Chodec.'},
```

Kult `bhp` makes the Hnízdo's effective HP 200.

**Mechanics** (function, rule):
- `attack_cells` / `move_cells`:
  - `mrchozrout`: moves like `medik`; attacks `(f,0),(f,1),(f,-1),(0,1),(0,-1)`.
  - `exo`: moves and attacks like `dama`.
  - `nekromant`: moves and attacks like `medik`.
- `damage()`:
  - Thorns: if the target is a building with `thorns`, the attack is melee (`not ranged`), and `src.cat in 'uz'` is alive, call
    `self.damage(src, dealt * thorns, tgt.side)`. Here `dealt = amount * mult`. Pass no `src` and no `ranged`, so war-cry and Pancíř multipliers do not apply.
  - Exo shield: absorb from `e.sh` first. Only hits of 1 or more reset `e.sh_t`.
  - `zdmg_in` is applied here (see section 2).
- `passives()`:
  - Exo: when `sh_t >= sh_wait`, `sh = min(120, sh + 15*dt)`.
  - Opravna (Dílna B): buildings within Chebyshev distance 1 heal 5 hp/s.
  - `e.off` (EMP) counts down. `rcd` (Nekromant) counts down.
- `timers()`: `sd.s += scrap_income(s) * dt`, where `scrap_income = Σ dilna scrap[lvl-1] + 0.6 * (path A)`. Dílny with `off > 0` produce nothing.
- `crates_tick` / `at_crate`: `at_crate` returns `{side: rate}`. The rate is `chan` (2.0) when the unit on the crate cell is a Mrchožrout, otherwise 1.0. The channel adds `dt * rate`.
- `kill()`: the zombie loot multiplier is `zloot` when `src.kind == 'mrchozrout'`. If the zombie is owned and its owner's faction has `noloot`, there is no loot at all.
- `tower()`:
  - `hangar` is added to `ATTACK_TOWERS`. It targets the nearest visible foe; path A hits 2 targets; path B sets `slow_t = 1.5, slowk = 0.4`. Each shot emits fx `H`.
    New `Ent.slowk` (default 0.5; Chemická mina sets 0.5). `passives` uses `slowk` in place of the fixed 0.5 while `slow_t > 0`.
  - Any building with `off > 0` returns at once and clears `aim`.
  - `income()` skips generators that are off. Rušička and Generátor B are inactive while off.
- `compute_vis` (dark): `hangar` keeps `dark_vis` (3.0), the same as Reflektor.
- `cast('emp')`: for every enemy building with |dx| ≤ 1 and |dy| ≤ 1, `off = 4.0`. Every enemy unit, the King and every zombie in that square gets `stun = max(stun, 1.5)`. Emits fx `E`.
- `cast('mor')`: appends `[s, x, y, 8.0]` to `self.clouds`.
  - `clouds_tick(dt)` deals 10·dt to foe units and the King within |dx|, |dy| ≤ 1.5 and sets `o.plague = s`.
  - In `kill()`, a unit with `plague >= 0` that dies rises (see raise).
- `nest_tick(e, dt)` is called from `step` for `hnizdo` and is paused while `off`. Every `every[lvl-1]` s it calls `spawn_zombies(kinds, horde cols of foe, foe, own=s)`.
  - Kinds are `['chodec']`; path A gives `['bezec','bezec']`; path B makes every 5th release `['obr']`.
- **Raise** (Nekromant and Mor): spawn a `chodec` at the dead entity's cell if it is free and `'.'`, with `own = s` and `tgt = foe`, then emit fx `Z`.
  - Nekromant raises trigger on a foe unit, or on a zombie with `tgt == s and own != s`, dying within 2.0 of a Nekromant whose `rcd <= 0`. Then set `rcd = 3`.
- `spawn_zombies(kinds, cols, target, own=-1)`: stops at `OWNED_CAP`. Bio2 Nákaza now sets `own = killer`.
- `target_at` and tower/throne target lists skip zombies with `own == attacker side`, and zombies with `own >= 0` skip their owner's things. This is the **[global]** rule; it is skipped when `RULES_05` is set.

---

## 4. King perks (Král) and command variants (Stratég)

| Faction | Král perk (implementation) | Stratég variant (implementation) |
|---|---|---|
| prez | **Kovář**: `kral_tick` repair uses `mods.repair` (80 hp/s) and `mods.repair_hp` (20 hp per 🔩). | **Svépomoc** (Q, cd 20): target +40 % max HP, other own buildings within Chebyshev 1 +20 %. |
| korp | **Tesla-rukavice**: count `k.shots`. Every 3rd shot chains up to 3 more visible foes within 1.6 of the previous target (pick with `near_key`), 14 dmg each, fx `z`. | **Dronová letka** (E, cd 15): the drone dict gets `'v': 6.0`. `compute_vis` adds every own korp drone as a radius-2.0 source while flying (1.0 while hovering, as now). |
| kult | **Pán mrtvých**: on war-cry activation, every zombie except `alfa` within 3.0 of the King gets `tgt = foe`, `own = s` (capped), fx `W`, and event `turn [s, n]` when n ≥ 3. Passive `zdmg_in` also protects the King. | **Volání mrtvých** (G, cd 70, Doba II): the Útok! effect, plus every zombie except `alfa` with `lo <= cx <= hi` and `tgt == s` turns as in Pán mrtvých. |

`cmd_of(s, cid)` merges `CMDS[cid]` with `FACTIONS[fac]['cmd'].get(cid, {})`. `command()` reads `cd`, `doba`, `splash`,
`speed`, `scan` and `turn` only through it.

---

## 5. Bez frakce, deck rules, lobby, protocol

- **Bez frakce** has no mods, cards, perk or variant. Its only differences from 0.5 are the two **[global]** rules.
  It is the lobby default, labelled "Doporučeno na první hru".
- **Deck**: exactly 8 distinct cards from `pool_of(fac)` (20 shared cards plus 3 own). There is no cap on faction cards.
  `valid_deck(deck, fac)`; when invalid, the server uses `RECOMMENDED_F[fac]`. The base kit (Generátor, Zeď, Tlupa) is unchanged.
- `RECOMMENDED_F`:
  - `bez`: the current RECOMMENDED.
  - `prez`: `['kulomet','plamen','sniper','hlaska','ostnata','dilna','pesak','mrchozrout']`
  - `korp`: `['kulomet','sniper','hlaska','tesla','hangar','pesak','obrnenec','emp']`
  - `kult`: `['kulomet','plamen','sniper','hlaska','hnizdo','pesak','nekromant','mor']`
- **Lobby**: client sends `{t:'ready', v:true, deck:[…], fac:'prez'}` and the server stores `c.fac` (falling back to `'bez'`).
  Lobby broadcasts never include the faction.
  `Lobby.start` calls `Game(names, decks, mode, facs)` with the signature `Game(names, decks, mode, facs=('bez','bez'))`,
  so the harness and tests keep working. `Side(idx, name, deck, fac='bez')`.
- **defs** message adds:
  - `factions`: per id, `name, motto, desc, passives, cards, perk, cmdv` (`{cid:{name, desc}}`).
  - `facPool {id:[cards]}`.
  - `facCosts {id:{kind:[e,s]}}` (base prices, no escalation).
  - `facRec`.
- **start** message adds:
  - `fac [f0,f1]`.
  - `costs {kind:[e,s]}` for the own side.
  - `rcost {rid:n}`.
  - `cmds` (own commands, merged).
  - `perk`.
- **end** message adds `fac`, for the statistics design.
- **Snapshot**:
  - `hc`, `gp` and `sp` come from `price()`.
  - New `sinc` (scrap income /s, 1 decimal).
  - New `mc [[x,y,t,s]]`: Mor clouds whose centre is visible or which are own.
  - Entity flags: 2048 = owned zombie, 4096 = owner is side 1, 8192 = building off (EMP). Bit 16 is also set for Exo with `sh > 0`.
- **fx**:
  - `['H',x0,y0,x1,y1,side]` hangar shot; add `H` to the snapshot's endpoint-visible set `'ksmtqazD'`.
  - `['E',x,y,1.5,0,side]` EMP.
  - `['M',x,y,1.5,0,side]` Mor cast.
  - `['Z',x,y,0,0,own]` raise.
  - `['W',x,y,0,0,own]` turn.
- **Events**: `turn [own, n]`. The announcer shows "MRTVÍ POSLECHLI!".
- **Client storage**: `hmk_fac`, and `hmk_deck_<fac>`. The old `hmk_deck` migrates to `hmk_deck_bez`.
- **Client UI**:
  - Lobby faction picker: 4 tiles styled like `.mode` buttons, each with the emblem, motto and 3 passives.
  - Deck view: the "Frakční karty" group comes first.
  - In game: the faction emblem sits next to both names in the HUD, with a passives tooltip.
  - The research panel uses `rcost`. The G button shows a lock until Doba II.
  - Help gets a "Frakce" section.
  - Tips: 2 per faction in `TIPS`. Examples: "Kult: Mor promění padlé nepřátele v tvé Chodce.", "Korporace: EMP vypne věže před tvým útokem."
- **Other 0.6/1.0 modes**: Výcvik and Přežití allow any faction. Puzzles fix `fac` per puzzle (default `bez`). The Výcvik AI uses the faction behaviours from section 8.

---

## 6. Art brief (js/paint.js, js/render.js)

Side identity stays exactly as in 0.5: A is bone material with lapis enamel and a heater shield; B is ebony with ember
enamel, a roundel and the mandatory ember rim. A faction never recolours the base material or the team enamel.
Faction identity is carried by **shape first** and accent colour second. Accents cover at most 10 % of a sprite.

| | Emblem charge (inside the side's shield/roundel) | Accent `acc` / `acc2` | Building trim | Unit trim | King sceptre | Throne foot prop |
|---|---|---|---|---|---|---|
| bez | A crescent / B flame (unchanged) | – | – | – | gilt sceptre | – |
| prez | crossed hammer and crowbar | rust `#9a6a3c` / iron `#5a5d63` | 2 riveted planks across the slab, patched pennant | rope-wrapped disc rim (rust dashes), cap with goggles | hammer | sandbags |
| korp | lightning bolt in a hexagon | steel `#aab4be` / arc white `#e9f2ff` | steel band on the slab, antenna with a white tip | steel disc ring with 4 rivets, visor slit in `acc2` | coil rod with a spark ring | steel crate with antenna |
| kult | horned skull | ash violet `#6a4a9a` / grave-light `#e6f2c8` | rope with 3 bone fetishes; Generátor candle flames in `acc2` | 3 hanging bones on the disc rim, hood in `acc` | bone staff with a pale lantern | ring of 3 pale candles |

- **Data**: `FAC_ART = {fac: {charge: svgPath, acc, acc2}}`, with charges in the same 20×22 box as `EMB_PATH`.
  `paintEmblem(g, s, r, fac)` fills the charge as it does now (A `MAT[0].hi`, B `PAL.flame`), so the side contrast survives
  when both players pick the same faction.
  The emblem is used in the HUD `EMB`, lobby slots, throne banner, end screen and the faction tiles (neutral skin 2).
- **Trim pass**: `paintFacTrim(g, cat, kind, s, fac)` runs after `paintBuilding` / `paintPiece` / `paintKing`.
  Sprite cache keys gain `|fac`: `B|kind|side|lvl|path|fac`, `U|…|fac`, `K|side|face|fac`, `TH|side|fac`.
- **New sprites**:
  - `ostnata`: the wall with spikes; the 3 levels go wood → wire → steel.
  - `dilna`: a workbench under an awning, with a gear on the A badge and a wrench on the B badge.
  - `mrchozrout`: a hunched piece carrying a sack.
  - `hangar`: a bell-tower hatch with 2 perched bats (the drones).
  - `exo`: a piece with a steel frame and a glowing chest node in `acc2`.
  - `emp`: icon, a shattered coil inside a ring.
  - `hnizdo`: a grave mound with clawed hands; path A adds eggs, path B adds a big hand.
  - `nekromant`: a hooded piece with a skull lantern.
  - `mor`: icon, a beak mask in a cloud.
- **fx**:
  - `H`: a small bat dart along the shot line.
  - `E`: a 3×3 square outline flash plus a white-violet ring, with spark glyphs.
  - `M` plus the persistent `mc` cloud: a grey-green hatched 3×3 (hatch, not colour only) that thins as `t` drops.
  - `Z`: a hand rising from the ground, then the zombie.
  - `W`: the zombie's eyes flip, and a short side-coloured ring appears.
- **Owned zombies** (flag 2048): a 2 px collar in the owner's team colour, plus the owner's emblem body shape on the
  shoulder (shield or roundel), so they read in greyscale too.
- **EMP-off buildings** (flag 8192): a desaturated sprite with blue-white crackle lines. Not shown by colour alone.
- **Exo shield**: a dashed bubble.
- **Audio**: new procedural sfx `emp, mor, raise, turn, hangar, thorns`. Faction music is not planned.

---

## 7. Server implementation checklist (order)

1. Add `FACTIONS`, `fm`, `r5`, `fac_price`, `Game.price`, `need_doba`, `cmd_of`, `pool_of`, `valid_deck(deck, fac)`,
   `RECOMMENDED_F`, `RULES_05`, `OWNED_CAP`, the 9 DEFS entries, and set `CMDS['utok']['doba']=2`.
2. In `Side.fac`, add the `Ent` fields `own=-1, off=0.0, sh, sh_t, rcd, plague=-1, ht, hn` (nest timer and count), and `shots` on the King.
3. Switch `build/deploy/cast/horde/research/command` to `price` / `need_doba` / `cmd_of`, and add the `max` limits.
4. Update `max_hp`, `damage`, `kill`, `tower`, `income`, `timers`, `passives`, `compute_vis`, `crates_tick`, `at_crate`,
   `kral_tick`, `king_input`, `spawn_zombies`, `target_at`, `throne_gun`, `foes_in` as described in sections 3 and 4.
   Add `clouds_tick` and `nest_tick` to `step()`.
5. Extend snapshot, start, end and defs (section 5).
6. Faction code must not call `random` when both sides are `bez`, so the `RULES_05` regression stays byte-identical.
7. Set `VERSION = '1.0'`.

---

## 8. Balance harness (moved into the repo)

- **Location**: copy `scratchpad/integ/bal/{harness,run,variants,fair,perf}.py` to `dev/bal/` in the repo. The public repo is fine; there are no secrets.
  - `GAME_DIR = os.environ.get('HMK_SERVER') or <repo game dir>`.
  - `reset_rules()` also deep-restores `FACTIONS` and `CMDS`.
  - New files: `dev/bal/facbots.py` (mixin and decks), `dev/bal/facrun.py` (suites and the PASS/FAIL report), and `dev/bal/baseline_05.json` (the 0.5 server's regression output).
- **run_game**:
  - Each scenario side takes `'fac'` (default `'bez'`). The game is created with `S.Game(..., facs=[f0, f1])`.
  - `'deck'` may be a role name, resolved through `FAC_DECKS[fac][role]`.
  - **Mirrored seating**: every seed runs twice with sides swapped and the same seed, which gives the same symmetric map and length.
  - Draws count as ½ of a win.
- **FAC_DECKS** (roles `def / att / mix / att_sn / spam`):
  - `bez`: the current `DEF_DECK, ATT_DECK_D2, MIX_DECK, ATT_DECK_SN, ATT_DECK`.
  - `prez`:
    - def `['sniper','hlaska','kulomet','plamen','ostnata','dilna','pesak','obrnenec']`
    - att `['kulomet','hlaska','pesak','obrnenec','medik','mrchozrout','dilna','nalet']`
    - mix `['kulomet','plamen','sniper','hlaska','ostnata','dilna','obrnenec','mrchozrout']`
    - att_sn `['sniper','hlaska','pesak','jezdec','obrnenec','mrchozrout','medik','nalet']`
    - spam `['kulomet','hlaska','pesak','jezdec','obrnenec','strelec','medik','mrchozrout']`
  - `korp`:
    - def `['sniper','hlaska','kulomet','tesla','hangar','emp','pesak','obrnenec']`
    - att `['kulomet','hlaska','pesak','obrnenec','medik','exo','emp','vypadek']`
    - mix `['kulomet','tesla','sniper','hlaska','hangar','pesak','obrnenec','emp']`
    - att_sn `['sniper','hlaska','pesak','obrnenec','exo','medik','emp','nalet']`
    - spam `['kulomet','hlaska','pesak','jezdec','obrnenec','strelec','medik','exo']`
  - `kult`:
    - def `['sniper','hlaska','kulomet','plamen','hnizdo','pesak','obrnenec','mor']`
    - att `['kulomet','hlaska','pesak','obrnenec','medik','nekromant','hnizdo','mor']`
    - mix `['kulomet','plamen','sniper','hlaska','hnizdo','pesak','obrnenec','mor']`
    - att_sn `['sniper','hlaska','pesak','obrnenec','nekromant','medik','mor','nalet']`
    - spam `['kulomet','hlaska','pesak','jezdec','obrnenec','medik','nekromant','hnizdo']`
- **FacMixin.fac_tick()** is called at the start of every bot `tick()`. Each rule fires only if the card is in the deck.
  - **prez**:
    - Turtle/Mixed: after the first tower block, build `ostnata` at local column 3, rows 4,3,5,2,6, and upgrade them to level 3 when 🔩 ≥ 60.
    - Dílna 1 after the 3rd Generátor, Dílna 2 after the 5th, both path A.
    - The contest squad uses Mrchožrout instead of Pěšák.
    - The Král bot always uses `repair` mode.
  - **korp**:
    - Turtle/Mixed: 2 Tesla at local (3,3) and (3,5) once affordable, and a Hangár (path B) on the 2nd Hláska spot.
    - Attacker: cast EMP on the 3×3 centre with the most enemy attack towers (≥ 2) when ≥ 3 own units are within 3 columns of it.
    - Comp `korp`: `['obrnenec','pesak','exo','pesak','medik','pesak']`. Exo becomes Obrněnec before Doba II.
  - **kult**:
    - Tlupa whenever off cooldown and ⚡ ≥ cost + 60.
    - 2 Hnízda (path A) after the 4th Generátor.
    - Comp `kult`: `['obrnenec','pesak','nekromant','pesak','obrnenec','pesak']`.
    - Mor on the visible 3×3 holding the most enemy units (≥ 2), or on the tower front where its push fights.
    - Král: escort, and war cry when ≥ 4 zombies are within 3.
    - Stratég: Volání mrtvých when ≥ 4 zombies with `tgt == s` are in the Mist, or the push has ≥ 3 units.
  - **Faction-only strategies**:
    - `wallturtle` (prez): two `ostnata` columns in front of the snipers.
    - `emprush` (korp): attacker that saves EMP for every push.
    - `flood` (kult): no units; Tlupa, 2 Hnízda path B, Mor.

### Suites (`python facrun.py <suite|all> [--quick]`)

`--quick` halves the seeds. Python 3.14, `WORKERS=11`. Full run is about 2.3 h, quick about 1.2 h.
The estimate is based on the measured 0.5 rate: about 1.9 s of wall time per long game and 0.6 s per crack game.

| Suite | Games | Content |
|---|---|---|
| `matrix` | 10 faction pairs (incl. mirrors) × 2 modes × 20 seeds × 2 seatings = 800 | `duel` (both 1 sniper column + pushes, random length, played to the end) |
| `rush` | 10 × 2 × 10 × 2 = 400 | both sides `ATT` (light defence) |
| `crack` | 16 ordered pairs × {`mix`,`mixeco`} × 2 modes × 10 × 2 = 1280 | ATT(f) vs TURTLE(g); prez turtles use `wallturtle` for half the seeds |
| `spam` | (16 ordered pairs + 4 `flood`(kult) vs MIXED(g)) × 2 × 10 × 2 = 800 | SPAM(f) vs MIXED(g) |
| `rr` | 27 entries × field 8 × 2 seeds × 2 seatings × 2 modes = 1728 | entries are {turtle, mixed, att, att_sn, spam, duel} × 4 factions plus the 3 faction-only strategies; field is {mixed, duel} × 4 factions |
| `night` | 10 × 2 × 10 × 2 = 400 | `sym` turtle vs turtle |
| `ablate` | 9 cards × 2 modes × 10 × 2 = 360 | `duel` F vs `bez`, compared to the same `matrix` cell, with the card replaced by the nearest shared card: ostnata→zed, dilna→gen, mrchozrout→pesak, hangar→kulomet, exo→obrnenec, emp→vypadek, hnizdo→rusicka, nekromant→medik, mor→nalet |
| `regress` | 0.5 scenario set, seeds 0–9 | with `RULES_05=True` and `bez`: compared to `baseline_05.json` |
| `perf` | `perf.py` on kult-kult `duel`, `flood` vs mixed, korp `emprush`, 2 seeds per mode | |

### Acceptance criteria (all must pass on a full run)

| # | Criterion |
|---|---|
| A1 | `matrix`: every non-mirror pair, each mode, faction win rate **40–60 %** (40 games). Each faction pooled over its 3 opponents and both modes: 45–55 %. A miss in the 37–63 % zone is re-run with 80 games before any tuning (the 95 % CI at n = 40 is ±15 pp). |
| A2 | `rush`: every pair, each mode, 35–65 %. |
| A3 | `rr`: no (strategy, faction) entry wins **> 70 %** against the field, per mode. |
| A4 | `crack`: the attacker wins before Poslední noc in **≥ 85 %** of games for every (f, g) pair and mode. Median crack time 180–420 s. Stratég/Král median ratio 0.70–1.30 for bez-vs-bez and 0.60–1.40 for every pair. |
| A5 | `spam`: the spammer (and `flood`) wins before the night in **≤ 15 %** of games, for every pair and mode. |
| A6 | `night`: ≥ 95 % of games decided (not a draw), per pair. |
| A7 | Side fairness (`fair.py` on all mirrored suites): side A wins 45–55 % pooled; zombie loot B/A 0.93–1.07. |
| A8 | `regress`: byte-identical `(winner, t, throne, dealt)` per seed. With the 1.0 rules, bez-vs-bez `mix` Král stays within ±2 wins/20 of 0.5. |
| A9 | `ablate`: no faction card raises win rate by **> 15 pp** over its replacement. Each faction card is used (built, deployed or cast) in ≥ 80 % of games where it is in the deck. A card below 80 % means a bot bug, fixed before any tuning. |
| A10 | Perf (this PC): tick avg ≤ 1.0 ms, p99 ≤ 3.0 ms, max ≤ 15 ms; snapshot JSON avg ≤ 2.5 KB, max ≤ 6 KB; entities ≤ 160. 0.5 reference: tick avg 0.34–0.61 ms, max 3.9 KB, 80 entities. |

---

## 9. Tuning procedure and knobs

1. Implement, then run `facrun.py all --quick`. Fix bot bugs first, so that A9 usage passes.
2. In each iteration, change **one knob per out-of-band faction**, taking the knobs in the order listed. Prefer nerfing the
   overperformer's highest-ablation card over buffing the others. Re-run only the failing suites plus `matrix`.
3. When everything passes on quick, run `facrun.py all` (full). Record the final numbers in DESIGN.md under "Verze 1.0 – Frakce" (Czech),
   and store the report in `dev/bal/report_fac.txt`.
4. If a faction is still out of band after 6 iterations, cut its highest-ablation card's main number by 15 % and restart at step 2.

| Faction | Knobs in order (start → step, bounds) |
|---|---|
| prez | `zed_hp` 1.4 → ±0.1 (1.2–1.6) · `bcost` 0.8 → ±0.05 (0.75–0.9) · `ucost` 1.1 → ±0.05 (1.0–1.2) · Dílna `scrap` ±0.1/level · `thorns` 0.35 → ±0.05 (0.2–0.5) |
| korp | `ucost`/`bcost` 1.1 → ±0.05 (1.05–1.2) · EMP `dur` 4 → ±0.5 (3–5), `cd` 50 → ±5 (40–60) · Hangár `dmg` 15 → ±1.5 (12–18) · Exo `sh` 120 → ±20 (80–160) · `res1` 1 → 2 (off) |
| kult | `bhp` 0.8 → ±0.05 (0.7–0.9) · `zdmg_in` 0.5 → ±0.1 (0.4–0.7) · `horde` 80/18 → ±10 ⚡/±2 s (70–100 / 15–22) · Hnízdo `every` ±2 s · `OWNED_CAP` 30 → ±5 (20–40) · Mor `dps` 10 → ±2 (8–14) |
| global | Útok! `cd` 70 → +10 only if A4's ratio is < 0.70 after the faction tuning |

---

## 10. Open 0.5 balance items: decisions

1. **Stratég cracks the turtle faster than Král.** Decision: **Útok! requires Doba II, cooldown stays 70 s.**
   Evidence: a probe run today on the 0.5 server (`scratchpad/facprobe/utok_probe.py`), 20 seeds per cell:

   | Setup | Mean crack time | Attacker wins |
   |---|---|---|
   | `mix` Stratég, 0.5 | 201 s | 20/20 |
   | `mix` Stratég, Doba II | 242 s | 20/20 |
   | `mixeco` Stratég, 0.5 | 221 s | 20/20 |
   | `mixeco` Stratég, Doba II | 268 s | 19/20 |
   | `mix` Král (reference) | 330 s | 19/20 |
   | `mixeco` Král (reference) | 348 s | 18/20 |

   - The Stratég/Král ratio goes from 0.61 to 0.73–0.77, and the turtle stays crackable.
   - Against a mixed defence the attacker won 1/20 → 3/20, mostly decided at night, which is noise.
   - A 90 s cooldown on top changed nothing, because bots fire Útok! about 0.7× before winning, so the cooldown is not a lever.
   - Criterion A4 guards the result.
2. **Stratég punishes a defender who ignores the Relikvie.** Not changed by the factions. That is the 0.6 Relikvie advice and AI work.
   Kult zombies standing in the zone block capture for both sides. This is intended denial, and Nálet or Mor counter it.
