# SPEC 1.0 — Hra mrtvých králů (implementation contract)

Status: binding contract for every 1.0 engineer. **Precedence: this SPEC > the cited design-doc sections > the rest
of the design docs.** Where a section below says "adopt X §n", that section is part of this contract word for word,
except for the overrides listed here. Doc shorthands: **MAI** = `design-modes-ai-maps.md`,
**FAC** = `design-factions-balance.md`, **META** = `design-meta-ux.md`.
All numbers are starting values. Only the tuning packages in M5 may change them, and only through the listed knobs.

---

## 1. Scope

### 1.1 Ships in 1.0
| Area | Content |
|---|---|
| Maps | 5 symmetric 16×9 maps (Ruiny, Předměstí, Továrna, Most, Metro), new terrain `X w = ~ ^`, map pick plus "Náhodná" (MAI §3) |
| Game types | **Souboj** (PvP, 0.5 rules + 1.0 global rules), **Přežití** (solo, solo vs AI, 2 players; MAI §6), **Výcvik** vs AI (3 difficulties; MAI §5), **Puzzle** (10 puzzles, 3 stars; MAI §7), **Výuka** (11-step tutorial; META §5) |
| Factions | Bez frakce, Přeživší, Korporace, Kult, each with 3 cards, a King perk and a Stratég variant, plus 2 global rules (FAC §1–6) |
| Stratég relic help | button **Četa na Relikvii** (H) plus relic advice tips (MAI §5.5) |
| Meta | profiles in `stats.json`, XP/levels/titles, Elo and Síň slávy, history (50), records (6), achievements (12), end-screen graphs, Statistiky and Úspěchy tabs (META §1–2, trimmed in §2.4) |
| Cosmetics | 4 slots, 13 items (4 defaults + 9 unlockables), synced to the opponent (§5.5) |
| UX | new lobby, solo sessions next to PvP, VS splash, end overlay with graphs and XP, welcome modal, settings dialog with sound test and accessibility, pause in solo |
| Tech | `hmk/` stdlib package, render performance (overdraw ≤ 3×), dev test suite in `dev/tests/`, balance and AI gates, `dev/release.py` |

### 1.2 Explicitly out of 1.0 (do not build)
- Co-op or 2v2, spectators, replays, Internet play, accounts or passwords, server-side puzzle unlock enforcement.
- Board sizes other than 16×9, map editor, user maps, new zombie types, ramps, channels or radiation.
- Cosmetic slots `fig` (Figury) and `dlaz` (Dlažba). Also out: "Silné obrysy figur", key rebinding, faction music.
- Achievements `blesk, kralovrah, lovec_alf, veterani, nedotceny`, records `doba3, dmg`, "První výhra dne",
  clicking a record to open its match, lobby flag `fac_ok`.
- Přežití "Věčná noc", puzzle script op `night`.
- Balance suites `rush`, `rr`, `night` (criteria A2, A3, A6), AI runtime visibility assertion (the static lint stays),
  strategy adaptation for Střední (Těžká keeps it).
- META §7.2 rect-restore for decals: the decal sweep instead rebuilds the whole layer, at most once per second.
- Separate `RULES_05` module global (it is replaced by the `compat05` instance flag, §3.2).

---

## 2. Resolved conflicts and global decisions

### 2.1 IDs (used everywhere: protocol, stats, data)
| Kind | IDs |
|---|---|
| Game type `type` | `souboj` `preziti` `vycvik` `puzzle` `vyuka` |
| Control mode `mode` | `kral` `strateg` (unchanged) |
| Faction `fac` | `bez` `prez` `korp` `kult` |
| AI difficulty `diff` | `lehka` `stredni` `tezka`. AI names: „Zbloudilý mnich“, „Kastelán“, „Mrtvý velmistr“ |
| Map `map` | `ruiny` `predmesti` `tovarna` `most` `metro`, plus the lobby value `nahodna` |
| End code `code` | `throne` `both` `draw` `mat` `night` `disc` `quit` `error` `survive` `solved` `failed` |

### 2.2 Conflict resolutions
| Conflict | Decision |
|---|---|
| `Match` (MAI) vs `Session` (META) | **`Session`** in `hmk/session.py`, `kind ∈ room \| solo`. **`MAX_SOLO = 2`**, so at most 3 games run at once. |
| Lobby messages `map`/`play`/`mode` (MAI) vs `cfg` (META) | **`cfg {type, mode, map}`** replaces `mode`, `map` and `play`. |
| `leave` (MAI) vs `quit` (META) | **`quit`**. In PvP it means surrender, code `quit`. |
| Constants module `hmk/rules.py` vs Rules object `g.rules` | Constants go in **`hmk/defs.py`** (`from . import defs as D`). Mode rules are `hmk/modes.py`, held in `g.rules`. |
| `RULES_05` global | `Game(..., compat05=True)` instance flag. It sets Útok! to Doba I and makes owned zombies hostile to their owner. |
| `Game(... factions=)` vs `facs=` | `facs=('bez','bez')` keyword (§3.2). |
| Tutorial director with AI `hold`/`release` | **`TutorialRules`** with a fixed, preplaced enemy base and no AI (§6, M3-B1). |
| Puzzle/survival progress: localStorage (MAI) vs profile (META) | Both are written. The UI shows `max(local, profile)` for stars or best. The server profile is the source for achievements. |
| Emblem charge: faction (FAC §6) vs `ban` cosmetic (META §3) | The HUD and lobby **emblem charge = faction**. The `ban` cosmetic changes **only the throne banner** and the banner in the lobby slot. |
| Faction disc trim vs `fig` cosmetic | `fig` is cut. Faction trim owns pieces. |
| Name placeholder | Empty name, or a name whose key is `král`, means no profile. The display name is then "Král". |
| Stats recorded for short games | `len < 60 s` is not recorded, **except** `puzzle` and `vyuka`. |
| Default maps | `nahodna` for Souboj and Přežití, `predmesti` for Výcvik, solo Přežití and Výuka. A puzzle fixes its own map. |
| Factions in modes | Souboj, Přežití and Výcvik allow any faction. Puzzle and Výuka force `bez`. The Výcvik AI faction is `bez` at Lehká and `rnd.choice(FAC_IDS)` at Střední and Těžká. It is revealed at the start. |
| Version | `VERSION`/`CLIENT_VER` = `'0.9'` from M2, and **`'1.0'` only in M5-E**. |

### 2.3 Global 1.0 rule changes (affect Bez frakce too; off when `compat05`)
1. Útok! needs Doba II (`CMDS['utok']['doba'] = 2`). The cooldown stays 70 s.
2. Owned zombies (`own = side`) never target their owner. The owner's towers and throne never shoot them.

### 2.4 Meta trim (overrides META §1–3)
- Records: `fast_win, kills, crates, parry, relic_s, surv`.
- Achievements: 12, listed in §5.6.
- No `fwd`. The `by` key for Výcvik is `vycvik.<mode>.<diff>`.
- Counters: §3.6 lists exactly the ones to add. `alfa, promo, vet_max, doba_t` are not added.

---

## 3. Architecture and cross-file APIs

### 3.1 Server layout (final)
```
server.py            sys.dont_write_bytecode=True; from hmk.net import main_cli; main_cli(sys.argv)
                     + re-exports for tooling: from hmk.defs import *; from hmk.game import Game; from hmk.entity import Ent, Side;
                       from hmk.maps import bfs, bfs_from, WALK, BUILD
hmk/__init__.py      VERSION
hmk/defs.py          all 0.5 constants, DEFS CMDS RESEARCH RARITY BRANCHES DOBA_AT, home_col own_half local_x roman
                     gen_price sniper_price valid_deck(deck, fac='bez'), CARD_POOL ABILITIES ATTACK_TOWERS, TYPES
hmk/maps.py          WALK BUILD, bfs bfs_from, MapDef, load_maps(path), validate_map(m), pick_map(id, R), MAPS, public_maps()
hmk/entity.py        Ent(gid, kind, side, x, y, rng), Side(idx, name, deck, fac='bez')
hmk/game.py          class Game(ActionsMixin, CombatMixin, MoveMixin, KingMixin, WorldMixin, VisionMixin, FactionMixin)
                     __init__, helpers, price/need_doba/cmd_of/horde_cost, timers (economy+cooldowns), step, sample, snapshot,
                     visible_fx, state_hash
hmk/vision.py actions.py combat.py movement.py king.py world.py      pure-move mixins (MAI §1 list)
hmk/factions.py      FAC_IDS FACTIONS FAC_DEFS (merged into D.DEFS at import) RECOMMENDED_F pool_of fac_price OWNED_CAP
hmk/facmech.py       FactionMixin: nest_tick clouds_tick raise_dead emp thorns exo_shield perks (stub until M3)
hmk/modes.py         Rules DuelRules SurvivalRules make_rules(type, opts)
hmk/puzzle.py        load_puzzles(path) PUZZLES public_puzzles() PuzzleRules eval_stars FOE_SCRIPTS
hmk/tutorial.py      TUT_STEPS TUT_DECK TUT_FOE TutorialRules
hmk/ai/              __init__ (make_ai, AIPlayer) profiles view planner pilot commander actuator facplay
hmk/meta.py          Store key need title xp_gain elo_update ACH COSM record profile_view public_catalogs
hmk/session.py       Session summary
hmk/lobby.py         Lobby (room seats, queue, cfg, solos, protocol)
hmk/net.py           ws frame/unmask, Client, read_headers, http_response, static_file, websocket, heartbeat, lan_ips, main_cli
data/maps.json data/puzzles.json
```
- Mixins are **pure moves**: method bodies stay identical except for the seams in §3.2.
- **Tunables** are read at the use site as `D.NAME`, never bound with `from .defs import NAME`. Tooling monkeypatches
  them through `hmk.defs`. The tunables are `THRONE_HP START_RES BASE_INCOME HORDE_COST HORDE_CD SCRAP_TIME
  SCRAP_GAIN CHECK_TIME ECLIPSES ECL_LEN ECL_WARN RELIC_FROM RELIC_TIME RELIC_SAMPLE CONV CRATE_CH`.
  Other constants (`W H HALF MIST TICK N4 N8 LVL_MULT …`) may be imported by name.
- `hmk/` runs on the stdlib only and on Python 3.8 (keyword-only args are fine; no `match`, no `X | Y` at runtime,
  no `removeprefix`, no dict `|`). Never iterate a `set` of `str` without `sorted()`.
- `server.py [port] [--no-browser] [--stats PATH] [--no-stats]`. The env var `HMK_STATS` works like `--stats`. The
  default stats path is `<game dir>/stats.json`. `Spustit server.bat` is unchanged.
- The server still serves only `.html .css .js` (now also from `css/` and `js/`). `data/*.json` reaches clients
  only through `defs`.

### 3.2 Game constructor and seams (M1 creates all of them; 0.5-identical until filled)
```python
Game(names, decks, mode, *, rules=None, map_def=None, seed=None, rng=None, facs=('bez', 'bez'), compat05=False)
  self.seed = seed if seed is not None else random.randrange(2**31)
  self.R = rng if rng is not None else random.Random(self.seed)     # EVERY draw in hmk/ uses self.R (incl. Ent cd/mcd, kill loot)
  self.rules = rules or modes.DuelRules();  self.map = map_def or maps.pick_map('ruiny', self.R)
  self.ter (mutable 9x16 lists, from map)   self.facs   self.compat05   self.play = self.rules.play
  # draw order MUST equal 0.5: map generation first, then length = R.uniform(600, 900)
g.price(s, kind) -> [e, s]        # 0.5: gen_price / sniper_price escalation or DEFS cost. M3 adds faction mods (FAC §2).
g.need_doba(s, kind) -> int       # 0.5: DEFS[kind].get('doba', 1)
g.cmd_of(s, cid) -> dict          # 0.5: CMDS[cid]
g.horde_cost(s) -> (cost, cd)     # 0.5: (HORDE_COST*(0.6 if bio1), 15 if bio1 else HORDE_CD)
Side.fac (str), Side.respawn_len (float|None; default KRAL['respawn']; None = never respawns)
g.visible_fx(side, fx) -> list    # the filter from 0.5 snapshot() incl. popping pfx[side]; snapshot() and the AI both call it
g.state_hash() -> str             # sha1 of json.dumps([round(t,6), [[e,s,v] per side], throne, sorted ents
                                  #   (id, kind, side, round(x,6), round(y,6), round(hp,6), lvl, path)]) - same algorithm as
                                  #   dev/tests/golden/statehash.py
g.over = {'winner', 'reason', 'code'} # code per §2.1 (M1: throne both draw mat night disc error)
g.start_info(s) -> dict           # the 0.5 'start' game fields + rules.start_extra; M3-A adds fac/costs/rcost/cmds/perk.
                                  #   The Session adds type, seed, map, ai, cos, lv, solo, tut.
g.end_info() -> dict              # the 0.5 'end' fields + code + rules.end_extra; the Session adds ser, me, rec_new, lv.
```
End codes: Přežití always ends with `survive`. A puzzle ends with `solved` or `failed`, and Výuka with `throne`.
Hard-coded board literals become `MapDef` fields:
- `relic` = `(x0, x1, y0, y1)`, `(7, 8, 3, 5)` on Ruiny.
- `mid` = `(7, 8)`, the crate and Alfa columns.
- `crate_rows` = rows 0–8.
- `spawn` = `((6, 7), (9, 8))`, the zombie spawn columns per target side.
- `relic_fx` = `7.5`.

List comprehensions keep the 0.5 iteration order (x outer, y inner).

### 3.3 Rules hooks (`hmk/modes.py`, base class written in M1)
```python
class Rules:
    play = 'souboj'; relic = True; checkmate = True; night = True; promotion = True
    eclipses = None                                  # None -> D.ECLIPSES; a tuple overrides (g.eclipse() reads it)
    def setup(self, g): pass                         # end of Game.__init__ (placement, resources, kings)
    def tick(self, g, dt): pass                      # DuelRules: the 0.5 world schedule moved out of timers
    def end_check(self, g): return None              # dict {'winner','reason','code'} or None -> default throne logic
    def allow(self, g, s, m): return True            # first line of Game.act; False = ignore (the rule calls g.say)
    def on_msg(self, g, s, m): pass                  # Game.act with an unknown 't' (tutorial 'tut')
    def unit_may_enter(self, g, e, x, y): return True   # extra test in can_enter and kral_blocked
    def horde(self, g, s): return False              # True = the mode handled Tlupa (Přežití)
    def alfa_crate(self, g, killer, x, y): return (x, y)
    def start_extra(self, g, s): return {}           # merged into 'start'
    def snap_extra(self, g, s): return {}            # merged into each snapshot
    def end_extra(self, g): return {}                # merged into 'end'
def make_rules(type, opts) -> Rules | None           # final dispatch written in M1, never edited later:
#   souboj, vycvik -> DuelRules(); preziti -> SurvivalRules(opts['players']); puzzle -> puzzle.PuzzleRules(PUZZLES[opts['puzzle']]);
#   vyuka -> tutorial.TutorialRules(opts['mode']). Lazy imports. A stub class raises NotImplementedError -> make_rules returns
#   None -> the lobby sends lerr „Tento režim zatím není hotový.“
```
`Game.step` order is `timers → rules.tick → passives → vision → entities → throne guns →
mines/strikes/charges/crates/drones → (relic_tick if rules.relic) → (checkmate if rules.checkmate) → rules.end_check
or default`. `promote()` returns at once when `not rules.promotion`.

### 3.4 Session, Lobby, AI and meta interfaces
```python
class Session:                       # hmk/session.py (M2-B)
    __init__(self, lobby, kind, type, game, clients, ais, opts, store=None)
    # clients: [Client|None]*2; ais: [AIPlayer|None]*2; opts = the dict that started it (used by restart); paused=False
    async run()                      # per tick: ai.on_tick() for each AI -> g.step(TICK) -> snapshot to own clients; paused: no step,
                                     # snapshot with ps:1 every 10 ticks
    finish(result)                   # g.sample(); summary; res = meta.record(store, summary) if store; per-client 'end'; lobby.session_done(self)
    simulate(seconds) -> g.over      # headless loop, no sleep, no sends (tests/tools)
summary(session) -> dict             # exact format §5.4
make_ai(g, side, diff, seed, type='vycvik', fac='bez') -> AIPlayer   # hmk/ai (M2-C). AIPlayer.on_tick(); .name; .diff
meta.record(store, summary) -> {side: {xp_parts, xp, lvl, cur, next, lvlup, new_ach, new_cos, new_rec, elo}}  # humans with a key only
meta.profile_view(store, key) -> dict | None         # the 'me' payload
```
- `Client` fields: `seat` (room seat 0/1 or None, which replaces 0.5 `side`), `session`, `gside` (side in the session),
  `fac`, `deck`, `ready`, `name`, `key` (`meta.key(name)` or None).
- Starting a solo session frees the room seat (`seat()` fills it from the queue). `session_done` re-seats or queues
  the player.
- The human in a solo session is always side 0. The AI controls side 1 only through `g.act(1, msg)` and
  `g.sd[1].inp` (MAI §5).
- Fog lint: no file in `hmk/ai/` except `view.py` may contain `g.ents`, `.ents.`, `.aim`, `.length`, `sd[1 - ` or the
  foe's `.deck`.

### 3.5 Client modules and the event bus
Script order (`index.html`):
`base, paint, maps, ui, lobby, render, input, audio, modes, meta, settings, main`.

Stylesheets: `style.css` plus `css/lobby.css css/modes.css css/meta.css css/settings.css`.

M2-D adds the bus to `base.js`:
```js
const BUS = {};
function on(ev, fn) { (BUS[ev] = BUS[ev] || []).push(fn); }
function emit(ev, ...a) { for (const f of BUS[ev] || []) { try { f(...a); } catch (e) { console.error(ev, e); } } }
```
`ui.js` emits these after its own handling:
- `'defs'(m)`, `'lobby'(m)`
- `'start'(m)`, `'snap'(m, prev)`, `'end'(m, endMetaEl)`
- `'m:'+m.t (m)` for every message type it does not handle (`me`, `stats`, `lerr`)

| Module (owner) | Public API |
|---|---|
| `maps.js` (M2-D) | `TERRAIN {ch: {name, walk, build, tip}}`, `isWalk(ch)`, `isBuild(ch)`, `paintTerrain(g, ch, X, Y, cs, x, y, theme)`, `drawMapPreview(canvas, ter, theme)` |
| `lobby.js` (M2-D) | `lobbyTab(id, label, render)` registers a right-folio tab; `emit('typePane', type, el)` lets modules fill the type pane; `soloStart(opts)`; `LOBBY` state |
| `modes.js` (M3-E2) | the bus handlers for `sv pz tu ps`, the puzzle grid (type pane `puzzle`), `#tutCard`, `#pauseOv`, `#welcomeOv` |
| `meta.js` (M4-A) | tabs Statistiky, Úspěchy, Vzhled; `#endMeta` graphs, XP and seals; `#vsSplash` |
| `settings.js` (M4-C) | `openSettings(tab)`; `#setOv`; `KEYMAP` lives in `base.js` (M4-C) |
| `render.js` | `boardCanvas` calls `paintTerrain` for `ch ∉ {'.', '#'}` (M2-E); `KILLFX[id]`, `WINFX[id]` (M4-B) |

M2-D creates every mount point in `index.html`: `#endMeta`, `#vsSplash`, `#tutCard`, `#pauseOv`, `#welcomeOv`, `#setOv`,
`#typePane`, `#folioTabs`. It also creates stub files for all new modules. Later packages never edit `index.html`
except where their ownership row says so.

Keys use `ev.code` (Czech QWERTZ). The new keys are `KeyH` (relic squad, Stratég) and `Escape` (pause menu in solo).
Y and Z are never used.

### 3.6 Engine counters and sampling (M2-A)
- `Side.stats` adds these keys:
  - `zk`, `uk`, `bk`, `kk`: zombie, enemy unit, enemy building and King kills, credited to the killer.
  - `lost`: own units and buildings lost, credited to the victim.
  - `parry`: successful parries.
  - `relic_s`: `+= dt` while holding the relic.
  - `spent`: ⚡ spent on build, deploy, cast, upgrade, horde and squad.
  - `cast`: abilities plus commands used.
  - `kills` stays `zk + uk`.
- `g.ecl_log` holds `[[start, end], …]` and `g.night_t` is a time or None.
- `g.sample()` runs at t = 0, then every 5.0 s of game time from inside `step`, and once more in `Session.finish`. It
  appends to `g.ser = {'dt': 5, 'th': [[], []], 'inc': [[], []], 'army': [[], []]}`:
  - `th` = `int(throne)`
  - `inc` = `round(income * 10)`
  - `army` = META §1.4 formula with the base `DEFS` costs
  - Series go only into `end`, never into snapshots.

---

## 4. Protocol delta (client ↔ server)

### 4.1 Client → server
| `t` | Fields | Who / when | Effect |
|---|---|---|---|
| `hello` | `name` | anyone | as 0.5. Server answers `me` (300 ms debounce after a change) |
| `cfg` | `type∈{souboj,preziti}`, `mode`, `map∈ids∪{nahodna}` (each optional) | seated, no room match running | updates the room cfg, unreadies both, broadcasts `lobby`. **Replaces `mode`**, which is now ignored |
| `ready` | `v`, `deck[8]`, `fac` | seated | `fac` invalid → `bez`; deck checked with `valid_deck(deck, fac)` else `RECOMMENDED_F[fac]`. Same non-empty key in both seats → `lerr` „Oba máte jméno „X“. Jeden si ho změňte, jinak se statistiky smíchají.“ |
| `solo` | `type∈{vycvik,preziti,puzzle,vyuka}`, `mode`, `map`, `ai` (diff\|null), `fac`, `deck`, `puzzle` (id) | any client not in a session | new solo Session. When `len(solos) == MAX_SOLO`: `lerr` „Server už hostí 2 cvičné hry, zkus to za chvíli.“ |
| `pause` | `v` bool | solo only | freezes the sim |
| `restart` | – | solo only | puzzle: same seed; others: new seed, same opts |
| `quit` | – | in a session | PvP: the opponent wins, code `quit`. Solo: ends; Výcvik ≥ 60 s counts as a loss; puzzle/vyuka not recorded |
| `squad` | `id:'relic'` | in a match, Stratég | §4.4 |
| `tut` | `skip:1` | vyuka | `rules.on_msg` skips the step |
| `cos` | `v:{ban,kor,zab,vit}` | profile only | locked or unknown id → slot default; save debounced 2 s |
| `stats_q` | `who` (key\|null) | anyone | replies `stats` |

### 4.2 Server → client
| `t` | Added fields |
|---|---|
| `defs` | `types:[{id,name,desc}]`, `maps:[{id,name,desc,theme,ter(144 chars \| null for random rubble),relic:[y0,y1],crates:[rows]}]`, `puzzles:[{id,name,desc,mode,time,goal_text,stars_text[3]}]`, `diffs:[[id,label,ainame]]`, `factions:{id:{name,motto,desc,passives,cards,perk,cmdv}}`, `facPool`, `facCosts`, `facRec`, `cosm:[{id,slot,name,unlock:{lvl}\|{ach}\|null}]`, `ach:[{id,name,desc,xp,goal}]`, `lvls:[need(1..30)]`, `titles:[[lvl,title]]`, `squad:[20]`, `soloMax:2` |
| `lobby` | `cfg:{type,mode,map}`, `solo:[running,max]`, `players[i]+{lv,ttl,cos:{ban,kor}}`, `queue[i]+{busy}`; `you` = seat; field `mode` removed |
| `me` | `prof:{key,name,lvl,ttl,xp,cur,next,elo,cos,own:[ids],ach:[ids],tut,m,puz:{id:[stars,best_t]},surv:{"map\|mode":[wave,t]}} \| null` |
| `stats` | adopt META §1.6 (`prof`, `hist`, `hof`, `h2h`) |
| `lerr` | `text` (lobby refusal, shown in `#err`) |
| `start` | `type`, `map:{id,name,theme}`, `seed`, `ai:{diff,name}\|null`, `kit:[ids]`, `puzzle:{…public}\|null`, `surv:{players}\|null`, `fac:[f0,f1]`, `costs:{kind:[e,s]}`, `rcost:{rid:n}`, `cmds:{cid:merged}`, `perk:{name,desc}\|null`, `cos:[c0,c1]`, `lv:[[lvl,ttl]\|null]×2`, `tut:bool`, `solo:bool` (plus the 0.5 fields) |
| `s` (snapshot) | `ps:1` paused; `pz:[secs_left,progress,target]`; `sv:[wave,secs_to_next,z_mine,z_foe]`; `sq:[cost_e,cd]` (Stratég, relic on); `tu:[step,total,hx,hy,ui]`; `sinc` (scrap/s when > 0); `mc:[[x,y,t,s]]` (when non-empty). Each field is sent only when it applies. Entity flags: `2048` owned zombie, `4096` owner is side 1, `8192` building EMP-off; bit `16` also set for an Exo with shield |
| `end` | `type`, `code`, `seed`, `map`, `fac`, `puzzle:{id,ok,stars,t,metrics}\|null`, `surv:{wave:[a,b],t:[a,b]}\|null`, `ser`, `lv`; per client: `me:{xp_parts,xp,lvl,cur,next,lvlup,new_ach,new_cos,elo}\|null`, `rec_new:[ids]` |

New fx come from FAC §5: `H E M Z W`. `H` joins the endpoint-visible set `'ksmtqazD'`. New event: `turn [own, n]`.

### 4.3 Session routing
- `Lobby.handle` stays the single entry point.
- Messages from a client with `session` go to the session layer first (`pause`, `restart`, `quit`).
- All other in-session messages go to `session.game.act(c.gside, m)`, wrapped in try/except as in 0.5.
- A disconnect inside a session behaves like `quit`, with code `disc`.

### 4.4 Relic squad (`squad`, M2-A, actions.py)
- The action is Stratég-only.
- It is refused with `g.say` in these cases:
  - before `g.relic['on']`: „Relikvie ještě není aktivní.“
  - while `sd.cd['squad']` runs: cooldown 20 s
  - when the deck has no unit card: „V balíčku nemáš jednotky.“
- Composition:
  - Obrněnec + 2 Pěšák when both are in the deck.
  - Otherwise the 3 cheapest unit cards in the deck, ties broken by DEFS order.
- Deployment:
  - Members go out at +0, +4 and +5 s through `g.pending: [[t_due, s, kind, row]]`, which `timers` processes.
  - Each one is placed by normal `deploy()` in the furthest-forward own buildable column. The row is 4/4/3 or the
    nearest free row.
  - Each member pays its normal price at its deploy time. An unaffordable member is skipped with „Na člena čety
    nemáš energii.“
- The Výcvik AI and the puzzle script `relic_squads` use the same message.

---

## 5. Data formats

### 5.1 `data/maps.json`
- Adopt MAI §3.2 and the five boards of MAI §3.3 verbatim, plus `validate_map` rules.
- Loader: `load_maps(path)` mirrors `half` (x ↔ 15−x). A bad entry is skipped with the console line
  `  ! mapa <id> preskocena: <reason>`.
- Ruiny keeps `random: {"base":[1,4,4],"mist":[6,7,3]}`, and `pick_map('ruiny', R)` reproduces 0.5 `make_map` exactly
  (200 retries, same draw order).
- Terrain rules, as in MAI §3.1:
  - `WALK = frozenset('.~^=')`, `BUILD = frozenset('.^')`
  - `~`: unit and zombie `step_of ×0.75`, King speed ×1.25
  - `^`: building `rng +1.0`, `vision +1.0`
  - scrap only on `#`

### 5.2 `data/puzzles.json`
Adopt MAI §7.1 and the ten puzzles of MAI §7.2, with these changes:
- Each puzzle has `"fac": "bez"`.
- Script ops are `zombies unit crate say eclipse reveal`. `night` is removed.
- `foe.ai` names a server script in `puzzle.FOE_SCRIPTS`. The only one is `relic_squads`, which sends
  `{t:'squad',id:'relic'}` for side 1 every 20 s. It never uses `hmk/ai`.
- `eclipse` appends `g.t` to the rules' `eclipses` tuple, so darkness starts at once for `ECL_LEN`.

### 5.3 Factions (Python data, `hmk/factions.py`)
Adopt FAC §2 (FACTIONS dict, cost and HP rules, price table), §3 (9 DEFS entries and mechanics), §4 (perks, command
variants) and §5 (deck rules, `RECOMMENDED_F`, client storage). Overrides:
- `RULES_05` becomes `g.compat05`.
- Faction cards are merged into `D.DEFS` at import, keyed by `'fac'`. `CARD_POOL` and `ABILITIES` exclude them.
- Faction code draws randomness only from `g.R`, and never when both factions are `bez`.

### 5.4 Session summary (input of `meta.record`, built by `session.summary`)
```python
{'type': 'souboj', 'mode': 'kral', 'map': 'most', 'len': 712, 'code': 'throne', 'winner': 0,
 'ai': None | {'side': 1, 'diff': 'tezka', 'fac': 'kult'},
 'puzzle': None | {'id': 'p04', 'ok': True, 'stars': 2, 't': 31.5},
 'surv': None | {'players': 1, 'wave': [17, 0], 't': [751.0, 0.0]},
 'ecl': [[240, 265]], 'night': 702.0 | None, 'ser': g.ser,
 'p': [{'n': 'Jarda', 'k': 'jarda' | None, 'human': True, 'fac': 'kult', 'th': 1820, 'dmg': 5400, 'doba': 3,
        'st': dict(sd.stats), 'inc': [7.4, 11.5]}, {...}]}
```

### 5.5 `stats.json` (`v: 1`) and cosmetics
- Adopt the META §1.1 Store (atomic save, `.bak`, corrupt rename, PermissionError retry, 500 profiles) and the §1.2
  schema with these changes:
  - `by` keys: `souboj.<mode>`, `preziti.<mode>` and `vycvik.<mode>.<diff>`, each `[m,w,l,d]`.
  - `fac` keys are faction ids.
  - New `surv: {"<map>|<mode>": [wave, t]}`.
  - No `fwd`.
  - `cos` has the slots `ban kor zab vit`.
  - `tot` keys: `m w l d time zk uk bk kk cr parry relic_s`.
  - `rec` keys as in §2.4.
- `matches` keeps the newest 50, and only the newest 10 keep `ser`.
- `.gitignore` in the game folder lists `stats.json`, `stats.json.*`, `stats.corrupt-*.json`, `dist/` and
  `__pycache__/`.

`meta.COSM` (slot, id, name, unlock):

| slot | default | unlockables |
|---|---|---|
| `ban` (throne banner charge) | `rod` Rodový znak | `lebka` Lebka (ach `ucednik`) · `havran` Havran (ach `hrobnik`) · `klice` Zkřížené klíče (ach `relikvie`) |
| `kor` (King crown, lobby crown logo) | `zlata` Zlatá | `trnova` Trnová (ach `zrcadlo`) · `kostena` Kostěná (lvl 6) |
| `zab` (kill effect on enemy unit, building or King; not zombies) | `jiskry` Jiskry | `duse` Odcházející duše (lvl 3) · `vrany` Vrány (ach `sach_mat`) |
| `vit` (winner's throne in the 6 s finale) | `zlate` Zlaté jiskry | `zvony` Zvony (lvl 10) · `svatozar` Svatozář (ach `tri_cesty`) |

Readability lock (META §3.1): cosmetics never change side material, enamel, emblem field, silhouette, hitbox or
danger cues.

### 5.6 XP, levels, Elo, achievements (`hmk/meta.py`)
- XP, levels, titles and Elo: adopt META §1.5 without "První výhra dne".
- Puzzle XP: 40 for the first solve, 5 for a repeat solve. Výuka XP: 100 the first time only.
- Time XP and win XP do not apply to puzzle and vyuka.
- The level cap is 30.

| id | Name | Condition | XP |
|---|---|---|---|
| `korunovace` | Korunovace | first win: souboj, Přežití 1v1, or Výcvik ≥ `stredni` | 100 |
| `ucednik` | Učedník | finish the Výuka | 50 |
| `sach_mat` | Šach a mat | win with code `mat` | 150 |
| `zrcadlo` | Zrcadlo | `parry ≥ 10` in one match | 150 |
| `hrobnik` | Hrobník | `tot.zk ≥ 1000` | 200 |
| `relikvie` | Strážce relikvie | `relic_s ≥ 240` in one match | 150 |
| `sberatel` | Sběratel | `crates ≥ 6` in one match | 100 |
| `noc` | Přežil jsem noc | win with code `night` | 100 |
| `tri_cesty` | Tři cesty | a win with each of `prez korp kult` (souboj, or Výcvik `tezka`) | 300 |
| `mistr_vycviku` | Mistr výcviku | beat `tezka` | 200 |
| `nezlomny` | Nezlomný | Přežití: last ≥ 720 s | 200 |
| `velmistr` | Velmistr | every puzzle ≥ 1 star | 300 |

Disconnect and quit wins do not count for win-based achievements.

### 5.7 localStorage keys (client)
- Kept: `hmk_name`, `hmk_tips`.
- `hmk_opt` gains `q ('auto'|2|1|0)`, `fps`, `ui (1|1.15|1.3)`, `fogc`, `blk ('hold'|'toggle')`.
- `hmk_deck_<fac>`: the old `hmk_deck` migrates once to `hmk_deck_bez`.
- `hmk_fac`, `hmk_cfg` (last solo choice `{type,mode,map,ai}`), `hmk_tab`, `hmk_seen`, `hmk_qa`.
- `hmk_puzzle`: `{"v":1,"p":{"p02":{"s":3,"t":21.4}}}`.
- `hmk_surv`: `{"<map>|<mode>":{"w":17,"t":751}}`.
- Every access is wrapped in try/catch (existing `load`/`save`).

---

## 6. Milestones and work packages

Rules for every package:
- An engineer edits **only the files in its "owns" list**. Any other change goes back to the orchestrator as a
  request in the package's final answer.
- Every package keeps `python dev/tests/run_fast.py` green and **`dev/tests/golden/golden.py` green** (§7.1).
- No commits, pushes or releases by engineers.
- Browser checks run on port **8097**. Afterwards close every test tab and stop the server.
- Python is `%LOCALAPPDATA%\Programs\Python\Python314\python.exe`. Run tools with relative paths from the game folder.
- UI text is Czech and is reviewed with the `kontrola-cestiny` skill before the milestone gate.

Max 5 engineers at once. Start order inside a milestone = list order.

### M1 — Infrastructure (no behaviour change)
| WP | Model | Owns | Deliverables |
|---|---|---|---|
| **M1-A** Package split + seams | **opus** | `server.py`, `hmk/**` (all, including stubs), `data/` (empty dir + `maps.json` with Ruiny only), game-folder `.gitignore` | The §3.1 layout. Mixins as pure moves. Every §3.2 seam (RNG, map fields, tunables via `D.`, price/need_doba/cmd_of/horde_cost, respawn_len, `over.code`, visible_fx, state_hash). The §3.3 Rules base, with DuelRules taking the 0.5 world schedule and `make_rules`. Lobby, run and finish moved as-is into `hmk/lobby.py`. `net.main_cli`. Stub modules with the exact §3 signatures (meta, session, ai, factions, facmech, puzzle, tutorial). |
| **M1-B** Dev test suite | **sonnet** | `dev/tests/**` | Move these from the scratchpad: `integ/tests.py→test_features.py`, `fuzz.py`, `replay.py`, and `bal/{harness,run,variants,fair}.py→dev/tests/bal/`, `bal/perf.py→dev/tests/perf.py`. Paths are relative only (`_paths.py`: game dir = `../..`; `HMK_SERVER` env overrides). Harness constants go through `hmk.defs`. `reset_rules()` also restores mixin overrides. `golden/server_05.py` is a frozen copy of the 0.5 `server.py` and is never edited. `golden/statehash.py`, `golden/golden.py`, `test_golden.py` (short form). `test_py38.py` is the MAI §1 guard. `test_hashorder.py` greps for set iteration without `sorted` in `hmk/`. `run_fast.py` runs unittest discover, target ≤ 3 min. |

**M1 gate**
- `golden.py`: harness Mixed vs Attacker, seeds 1–10 × {kral, strateg}, 600 s, with `random.seed(s)` and new
  `Game(..., rng=random)`. The state_hash at every 60 s must equal the 0.5 copy: **20/20 runs identical**.
- `test_features.py` passes (all 0.5 feature tests). `fuzz.py` gives 0 exceptions over 4 seeds × 3000 random actions.
  `test_py38` passes.
- `perf.py`: tick average within ±10 % of 0.5 (0.34–0.61 ms reference).
- Browser: `server.py 8097` serves the game, a 2-tab match starts, units fight, and the end screen appears. 0 console
  errors.

### M2 — Platform (maps, sessions, AI core, client shell, render perf, meta core)
| WP | Model | Owns | Deliverables |
|---|---|---|---|
| **M2-A** Engine: maps, terrain, counters, squad | **sonnet** | `hmk/{maps,game,entity,actions,combat,movement,king,world,vision,defs}.py`, `data/maps.json`, `dev/tests/test_{maps,terrain,counters,squad}.py` | 5 maps. WALK/BUILD everywhere (MAI §3.1 list of checks). `~` and `^` effects. `pick_map` with `nahodna`. §3.6 counters, `ecl_log`, `night_t`, `sample()`. §4.4 squad plus the `sq` snapshot field. |
| **M2-B** Sessions + lobby protocol | **opus** | `hmk/{session,lobby,net}.py`, `server.py`, `dev/tests/test_lobby.py`, `dev/tests/fuzz.py` (lobby part) | Session (§3.4) with pause, restart and quit. Room and solos (`MAX_SOLO=2`). §4.1 and §4.2 messages, except the meta and faction payloads (send defaults: `fac 'bez'`, `me null`). `--stats/--no-stats` flags parsed but no Store yet. A `FakeClient` test harness drives `Lobby.handle` without sockets. Until M2-C lands, it uses a stub `IdleAI`. |
| **M2-C** AI core | **opus** | `hmk/ai/**`, `dev/tests/{test_ai_fog,test_ai_determinism,ai_ladder}.py`, `dev/tests/bal/novice.py` | MAI §5 complete for `souboj`/`vycvik` with faction `bez`: View, Actuator, Planner, KingPilot, Commander, DIFF table, relic squad through `squad`. NoviceBot. It may copy logic from `dev/tests/bal/harness.py` (it must not import from `dev/`). |
| **M2-D** Client shell: lobby, maps, bus | **sonnet** | `index.html`, `style.css`, `css/*.css` (creates all 4), `js/{base,maps,lobby,ui,input,main}.js`, stubs `js/{modes,meta,settings}.js` | Bus (§3.5). Move the lobby code (renderLobby, renderDeck, deckChanged, drawLobbyBg, updateReady) from `ui.js` to `lobby.js`. New lobby layout per META §4.1: type segment, mode, map select with preview, difficulty, slots, ready/start buttons, "Hrát sám", folio tabs (Balíček only). `cfg` and `solo` sending. `maps.js` terrain painters and preview. WALK/BUILD in placement and tooltips (MAI §3.3 texts). H squad button and key. Relic advice tips in `advisor()`: Stratég, relic on, not ours. All mount points. |
| **M2-E** Render performance | **opus** | `js/render.js` | META §7 items 1, 3, 4, 5, 6, 7. Item 2 replaced: `addDecal` paints into LAYER, and the 1 s sweep rebuilds LAYER from BASE + live decals only when a decal changed step or expired. `paintTerrain` call in `boardCanvas`. Quality levels and auto-step (settings UI comes in M4-C; read `hmk_opt.q` now). Reads `OPT.fogc` (fog alpha 0.80 → 0.90, gilt edge 1.2 → 2 px) and `OPT.fps` (corner counter). |
| **M2-F** Meta core (pure) | **sonnet** | `hmk/meta.py`, `dev/tests/test_meta.py` | Store, key, need, title, xp_gain, elo_update, ACH (§5.6), COSM (§5.5), `record(store, summary)` on the §5.4 format, `profile_view`, `public_catalogs()` (for defs). Tests per META §9 "Store", "Rules", "History". |

**M2 gate**
- `test_maps`:
  - `validate_map` passes for all 5 maps; every WALK cell is reachable from both throne columns.
  - `~`: a Pěšák crossing 4 canal cells takes ×0.75 ± 2 % of the time.
  - `^`: a Kulomet on `^` hits at range `rng + 1.0`.
  - `nahodna` over 500 seeds picks each map 20 ± 4 %.
- Golden stays 20/20.
- `test_lobby` covers each of these, with explicit assertions:
  - 1 room match + 2 solo Výcvik run concurrently, and each client receives snapshots only from its own session
  - the 3rd solo gets `lerr`
  - a seated player who starts a solo frees the seat, and the queue head takes it
  - a queued player who starts a solo leaves the queue; on return it is seated if a seat is free, otherwise it is
    appended to the queue
  - `pause` stops `g.t`
  - `restart` of a puzzle keeps the seed
  - `quit` in PvP gives `code:'quit'` and the opponent wins
  - a disconnect gives `code:'disc'`
- Fuzz with all §4.1 types plus malformed values: 0 exceptions.
- AI gates on `ruiny` and `predmesti`, bez vs bez, 10 seeds × 2 modes × 2 sides:
  - Těžká beats Střední ≥ 70 %
  - Střední beats Lehká ≥ 75 %
  - Lehká vs NoviceBot 40–60 %
- AI checks:
  - fog lint passes
  - determinism: Těžká vs Střední, 300 s, seed 5, `PYTHONHASHSEED` 1 vs 2 → equal `state_hash`
  - ≤ 2 ms per Těžká think
- `test_meta` passes.
- Browser:
  - lobby at 1366×768 and 1920×1080, no horizontal scroll
  - 5 map previews render
  - a full Výcvik vs Lehká match played to the end on Most
  - `?perf`: at 1920×1080, DPR 1, Q2: `?demo=40` ≤ 3.0× overdraw, `?demo=120` ≤ 4.5×
  - screenshots of the board before and after M2-E show no visual change except the vignette under the units
  - 0 console errors

### M3 — Content (factions, modes, AI content, art, meta wiring)
| WP | Model | Owns | Deliverables |
|---|---|---|---|
| **M3-A** Factions server | **opus** | `hmk/{factions,facmech,defs,game,entity,actions,combat,movement,king,world,vision}.py`, `dev/tests/test_factions.py` | FAC §2–5 server side in the FAC §7 order, with `compat05`. The §2.3 global rules. `start_info` fields `fac/costs/rcost/cmds/perk`, `factions.public()` for defs (M3-F wires it), snapshot `sinc mc` and flags, fx and events. |
| **M3-B1** Přežití + Výuka rules | **sonnet** | `hmk/{modes,tutorial}.py`, `dev/tests/{test_survival,test_tutorial}.py` | `SurvivalRules(players)` per MAI §6, using only the §3.3 hooks: quarantine wall via `unit_may_enter`, Tlupa via `horde` + `g.horde_cost`, crates and waves in `tick`, `sv`, end, no Věčná noc. With `players=1` only side 0 gets waves, and side 1 is untouchable and has no King. `TutorialRules` per META §5 steps (Czech texts verbatim). The fixed foe `TUT_FOE` (throne 1200, gen at local (1,2),(1,4),(1,6); Kulomet (4,3),(4,5); Hláska (3,4); no King, no AI). Step 11 spawns 2 foe Pěšák once. `tu`, and `tut` skip via `on_msg`. `make_rules` for `preziti` and `vyuka`. |
| **M3-B2** Puzzles | **opus** | `hmk/puzzle.py`, `data/puzzles.json`, `dev/tests/{test_puzzles,puzzle_solutions}.py` | `PuzzleRules` and the 10 puzzles per §5.2 and MAI §7. `eval_stars`, `pz`, `end.puzzle`, `public_puzzles()` (for defs). `FOE_SCRIPTS['relic_squads']`. |
| **M3-C** AI content | **sonnet** | `hmk/ai/**`, `dev/tests/ai_ladder.py` | `facplay.py`: faction rules ported from FAC §8 FacMixin through View/Actuator. AI faction choice per §2.2. `preziti` profile (no pushes; units only for crates and clearing its Mist half; Tlupa at Střední/Těžká). Map weights for all 5 maps. |
| **M3-D** Faction art, fx, sfx | **opus** | `js/{paint,render,audio}.js` | FAC §6 complete: `FAC_ART`, `paintEmblem(g,s,r,fac)`, `emblemImg(fac, side, px) -> dataURL` (for the HUD and lobby DOM, used by M3-E1), `paintFacTrim`, 9 sprites, fx `H E M Z W`, `mc` clouds, owned-zombie collar, EMP-off and Exo shield visuals, 6 sfx. Cache keys gain `fac`. |
| **M3-E1** Client factions UI | **sonnet** | `js/{lobby,ui,base,input}.js`, `index.html` (help "Frakce" section only), `css/lobby.css`, `style.css` | Faction picker (4 tiles, Bez frakce first, "Doporučeno na první hru"). Deck per faction, with "Frakční karty" first. HUD emblems with a passives tooltip. Costs from `start.costs`, `rcost`, merged `cmds`, G lock before Doba II. TIPS (2 per faction). `hmk_deck_<fac>` migration. |
| **M3-E2** Client modes UI | **sonnet** | `js/modes.js`, `css/modes.css` | Puzzle grid (type pane), stars from `max(local, me.puz)`, unlock rule MAI §7.1. Přežití HUD (`sv`, record). Puzzle HUD (`pz`, goal and star texts). `#tutCard` (META §5 client part). `#pauseOv` (Esc in solo: Pokračovat / Začít znovu / Ukončit). `#welcomeOv` first-visit modal. Writes `hmk_puzzle` and `hmk_surv` on `end`. |
| **M3-F** Meta server wiring | **sonnet** | `hmk/{session,lobby,net}.py`, `server.py`, `dev/tests/test_session_meta.py` | Store load at start (the path rules in §3.1). Adds `factions.public()` (M3-A), `public_puzzles()` (M3-B2) and `meta.public_catalogs()` to `defs`. `session.summary`. `meta.record` in `finish`. `me`, `stats_q`/`stats`, `cos`, the lobby `lv/ttl/cos` fields, duplicate-name `lerr`, `end.me/rec_new/ser/lv`, defs meta catalogs. |
| **M3-G** Faction balance tooling | **sonnet** | `dev/tests/bal/{facbots,facrun}.py`, `dev/tests/bal/harness.py` | FAC §8 bots, `FAC_DECKS`, mirrored seating, draws = ½. Suites `matrix crack(mix) spam ablate perf` + `fair` (§7.2). `--quick`. |

**M3 gate**
- Golden stays 20/20 (`compat05`, bez, ruiny).
- `test_factions` passes:
  - FAC §2 price table exact for all 3 factions
  - HP rules
  - thorns 35 %
  - EMP: 4 s off, 1.5 s stun
  - raise capped at `OWNED_CAP`
  - owned zombies never hit their owner
  - `noloot`
  - each perk and command variant fires
- `facrun matrix --quick`: no pair outside 30–70 % (sanity only).
- A9 usage: each faction card used in ≥ 80 % of games where it is in the deck.
- `test_puzzles`:
  - every scripted solution earns 3 stars, twice with identical metrics
  - idle play (no actions) never earns 3 stars on any puzzle
- `test_survival`:
  - the MAI §6 wave table matches (counts per listed wave)
  - the wall blocks units, not zombies
  - solo Přežití ends with code `survive` when the throne falls
- `test_tutorial`: scripted inputs complete all 11 steps in both modes in ≤ 600 s of game time, and `end.code` is
  `throne` with winner 0.
- `test_session_meta`:
  - 2 room matches + 1 Výcvik recorded in a temp Store
  - `end.ser.th[0]` has `floor(t/5)+2` samples
  - `me` arrives after `hello`
- AI: Těžká(f) vs Těžká(bez) on `predmesti` stays at 35–65 % for each faction (10 seeds × 2 modes × 2 sides).
- Browser:
  - one Souboj per faction (2 tabs)
  - the opponent faction is hidden until `start`
  - p01 solved with 3 stars
  - solo Přežití played to the end
  - Výuka completed in Král and Stratég
  - pause and restart work
  - 0 console errors

### M4 — Meta client, cosmetics, settings, release tooling
| WP | Model | Owns | Deliverables |
|---|---|---|---|
| **M4-A** Meta client | **sonnet** | `js/meta.js`, `css/meta.css`, `js/lobby.js` (slots: level badge, cosmetic banner, click a name to open the profile) | Tabs Statistiky (META §1.7 without records click-through), Úspěchy (§2 UI) and Vzhled (META §3.3 UI for 4 slots, 72×72 previews using the real paint functions). End overlay content in `#endMeta`: META §4.3 graphs (3 tabs, dashed B line, eclipse and night bands, hover tooltip), XP bar, seals, unlock card with "Nastavit", Odveta/Znovu buttons. VS splash (META §4.3). Name-required hint. |
| **M4-B** Cosmetics art | **sonnet** | `js/{paint,render}.js` | `CROWN[id]`, `CHARGE[id]` (throne banner + `CHARGE_SVG` for lobby slots), `KILLFX[id]` (≤ 6 particles; skipped at Q0, in calm mode or when PART > 500), `WINFX[id]`. Cache keys gain the cosmetic id. |
| **M4-C** Settings + accessibility | **sonnet** | `js/{settings,audio,input,base}.js`, `css/settings.css` | `#setOv` with the 4 tabs per META §6, minus "Silné obrysy". `audioTest(group)`, `musPreview(sec)`. Block toggle mode. UI zoom. Fog contrast (a flag read by `render.js` through `OPT.fogc`; the render read was added in M2-E). `KEYMAP` shared with help. Focus rings and radiogroups in the lobby (CSS + `settings.js` key handling). |
| **M4-E** Release tooling | **haiku** | `dev/release.py`, `dev/stats_report.py` | META §8 with this allowlist: `server.py, hmk/**/*.py, data/*.json, index.html, style.css, css/*.css, js/*.js, README.md, DESIGN.md, Spustit server.bat`. Secret scan, version check (expects `1.0`; `--allow-dev` accepts `0.9`), zip `dist/HRA-MRTVYCH-KRALU.zip`, SHA-256. |

**M4 gate**
- Browser:
  - end graphs with hover in both clients, and both see the same data
  - XP bar animates
  - an unlocked cosmetic can be set from the end card
  - the opponent sees my banner, crown, kill and victory effects
  - the VS splash shows both factions
  - each sound-test button plays
  - UI 130 % shows no horizontal scroll at 1366×768
  - block toggle works
  - Statistiky shows history, Síň slávy and another player's profile
  - 0 console errors
- A locked cosmetic sent via `cos` falls back to the default (unit test in `test_session_meta`).
- `release.py --allow-dev` builds the zip. The zip contains no `.exe`, `stats.json*`, `dev/` or `__pycache__`.

### M5 — Balance, QA, docs, release
| WP | Model | Owns | Deliverables |
|---|---|---|---|
| **M5-A** Faction balance | **opus** | knob values in `hmk/factions.py` and the global Útok! `cd` in `hmk/defs.py`, `dev/tests/bal/report_fac.txt` | FAC §9 procedure with the trimmed suites until §7.2 passes. |
| **M5-B** AI, maps, Přežití tuning | **sonnet** | `hmk/ai/profiles.py` (DIFF numbers only), `SURV_C` in `hmk/modes.py`, `dev/tests/ai_report.txt` | Full AI ladder (5 maps) and Přežití targets (§7.3). |
| **M5-C** Integration QA | **sonnet** | `dev/tests/{fuzz,perf}.py`, `dev/tests/lan_check.md` (checklist, not code) | Fuzz all types × every game type. Perf with 3 concurrent sessions. 2-browser LAN test. Bugs found are filed to the owning package and fixed by the orchestrator's assignee. |
| **M5-D** Docs (Czech) | **sonnet** | `README.md`, `DESIGN.md` (sections 15, 16, 19, new "Verze 1.0"), `../README.md` (Games row), `dev/release-notes.md` | README "Co je nového v 1.0" and the "Statistiky" note (META §8). DESIGN gets final numbers from the M5-A, M5-B and M5-C reports. Texts checked with `kontrola-cestiny`. |
| **M5-E** Version + build | **haiku** | `hmk/__init__.py`, `js/base.js` (`CLIENT_VER` only), `index.html` (`#ver` only) | VERSION and CLIENT_VER = `'1.0'`. `release.py` (strict) passes. The zip is built. **Publishing (`gh release create hmk-v1.0 …`) waits for the user's explicit OK.** |

**M5 gate = §7 all green + a 2-PC LAN match + release.py strict OK.**

---

## 7. Acceptance numbers (gates referenced above)

### 7.1 Regression
`dev/tests/golden/golden.py` must stay 20/20 identical after every package.
- New side: `Game(..., rng=random, compat05=True)`, Ruiny, bez/bez.
- Old side: `golden/server_05.py`.

### 7.2 Faction balance (`facrun.py all`; FAC §8 criteria, renumbered)
| # | Criterion |
|---|---|
| B1 | `matrix` (10 pairs × 2 modes × 20 seeds × 2 seatings = 800): every non-mirror pair per mode at **40–60 %**. Each faction pooled at 45–55 %. A cell at 37–63 % is re-run with 80 games before tuning. |
| B2 | `crack` (mix: 16 ordered pairs × 2 modes × 10 × 2 = 640): attacker wins before the night in **≥ 85 %**. Median 180–420 s. Stratég/Král median ratio 0.70–1.30 for bez-bez, 0.60–1.40 for the rest. |
| B3 | `spam` (16 × 2 × 10 × 2 + `flood` 4 × 2 × 10 × 2 = 800): the spammer wins before the night in **≤ 15 %**. |
| B4 | `fair` over the mirrored suites: side A 45–55 %; zombie loot B/A 0.93–1.07. |
| B5 | `ablate` (360): no faction card is **> 15 pp** better than its replacement; usage ≥ 80 %. |
| B6 | 1.0 rules, bez-bez `mix` Král: within ±2 wins/20 of 0.5. |
| B7 | perf: tick avg ≤ 1.0 ms, p99 ≤ 3.0 ms, max ≤ 15 ms; snapshot avg ≤ 2.5 KB, max ≤ 6 KB; entities ≤ 160. |

### 7.3 AI, maps, Přežití, server load
- Ladder, 10 seeds × 2 modes × 2 sides × 5 maps:
  - Těžká > Střední ≥ 70 %
  - Střední > Lehká ≥ 75 %
  - Lehká vs NoviceBot 40–60 %
  - Střední vs NoviceBot ≥ 85 %
  - Těžká vs harness Turtle ≥ 80 %
  - median Střední match 8–13 min
- Map fairness:
  - Těžká vs Těžká, 20 seeds × 2 modes per map: side 0 at 40–60 %
  - harness Mixed vs Attacker per map within ±10 pp of Ruiny
- Přežití (harness bots, 20 seeds; tune only `SURV_C`):
  - Mixed defender dies at wave 18–22 (median ≈ 20)
  - Turtle at waves 16–20
  - idle at waves 4–6
  - two equal Mixed: side 0 at 45–55 %
- Load: 1 room match (2 harness bots through `g.act`) + 2 solo Výcvik Těžká in one process. Summed CPU per 50 ms
  tick: **avg ≤ 4 ms, p99 ≤ 10 ms**. If p99 > 10 ms, set `MAX_SOLO = 1`.

### 7.4 Client
- Render: META §7.7 numbers. Software canvas (`--disable-gpu`), `?demo=60`, Automaticky: p50 frame ≤ 16.7 ms.
- Layout: every new text ≥ 14 px. No information carried by colour alone (chips carry text, B is dashed, locks carry
  text). No horizontal scroll at 1366×768 and 1920×1080. 0 console errors in every browser check.
