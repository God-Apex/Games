# 1.0 design: game modes, AI, maps, server split

Scope: Výcvik vs AI, Přežití, Puzzle, maps, and the `server.py` to `hmk/` package split. Factions, cosmetics and
statistics live in other docs; this one only defines the hooks they plug into (`faction`, `stats.record`).
Everything here is Python 3.8 stdlib on the server and plain browser JS on the client. UI text is Czech.

## 0. Decisions at a glance
- **Board stays 16 × 9, HALF 6, Mist 6–9 on every map.** Maps vary terrain, the Relikvie rows and the crate rows. Reasons:
  the client fits `W+2` columns × `H` rows into `#board` (an 18:9 box that suits 16:9 screens), the balance numbers
  (sniper range 7, Mist stages 0–6) are tuned to this width, and AI/test code uses local columns. `start` still sends `w/h`.
- **5 maps**, mirror-symmetric (x ↔ 15−x, same y). The author writes the left 8 columns and the loader mirrors them,
  so a map cannot be unfair by mistake. The lobby can pick one map or `nahodna`.
- **AI = a virtual client.** It acts only through `Game.act(side, msg)` with the same messages a browser sends, and it
  only sees what the fog lets that side see. It never reads hidden entities, enemy decks or `g.length`, and no
  difficulty gets extra resources. Difficulty changes reaction time, APM, mistakes and how good its plans are.
- **Přežití is competitive.** Each player defends their own throne against the same escalating waves, a quarantine
  wall in the middle of the Mist stops units crossing, and the only way to hit the other player is Tlupa or Výpadek.
  Whoever lasts longer wins. It can be played solo, solo vs AI, or by 2 players. There is no co-op in 1.0, because every
  rule assumes one player per side.
- **Puzzle**: 10 handcrafted single-player challenges in `data/puzzles.json`, each with 3 stars. Progress is kept in
  `localStorage` and the server computes the stars. Every puzzle comes with a scripted solution that gets 3 stars in
  the tests.
- **Solo matches run alongside PvP.** The lobby keeps its two PvP seats and also runs up to `SOLO_MAX = 3` private
  matches (Výcvik, Přežití alone, Puzzle). Starting one frees your PvP seat.
- **Determinism.** Each Game has its own RNG `g.R`, and each AI has its own RNG. Same seed, same match.
- **Relic help for Stratég** (from the 0.6 roadmap): a "Četa na Relikvii" button (H) asks the server to deploy
  the AI's relic squad for you. Both players have it, so it is fair in PvP.

## 1. Server package split
```
server.py            entry point: sys.dont_write_bytecode = True; from hmk.net import main_cli; main_cli(sys.argv)
                     + re-exports for tooling: from hmk.rules import *; from hmk.game import Game; from hmk.maps import bfs, bfs_from
hmk/__init__.py      VERSION = '1.0'
hmk/rules.py         W H HALF MIST TICK ... all constants, DEFS CMDS RESEARCH RARITY BRANCHES DOBA_AT, gen_price sniper_price
                     home_col own_half local_x roman valid_deck, CARD_POOL ABILITIES ATTACK_TOWERS
hmk/maps.py          terrain sets, bfs/bfs_from, MapDef, load_maps(path), validate_map(m), make_ruins(R), pick_map(id, R)
hmk/entity.py        Ent(gid, kind, side, x, y, rng), Side
hmk/game.py          class Game(ActionsMixin, CombatMixin, MoveMixin, KingMixin, WorldMixin, VisionMixin):
                     __init__, helpers (say/event/spawn/remove/max_hp/dmg_of/step_of/cry/rng/vision/income/...),
                     step, timers (economy + cooldowns only), snapshot, visible_fx, state_hash
hmk/vision.py        VisionMixin: base_vis compute_vis hidden_kind detects can_see secret fx_of
hmk/actions.py       ActionsMixin: act build deploy upgrade sell convert scrap horde research cast command squad
hmk/combat.py        CombatMixin: passives damage kill enemy_kill make_vet foes_in near_key tower throne_gun mines strikes_tick charges_tick
hmk/movement.py      MoveMixin: blocked_cell can_enter kral_in target_at attack_cells move_cells mobile advance promote saboteur
hmk/king.py          KingMixin: king_input kral_blocked kral_slide dash kral_tick
hmk/world.py         WorldMixin: spawn_zombies wave drop_crate collect crates_tick at_crate drones_tick relic_tick eclipse dark mist checkmate
hmk/modes.py         Rules (base), DuelRules, SurvivalRules, PuzzleRules
hmk/puzzles.py       load_puzzles(path), Puzzle, eval_stars(puzzle, game, metrics)
hmk/ai/__init__.py   make_ai(game, side, diff, seed, play) -> AIPlayer
hmk/ai/profiles.py   DIFF table (section 5.3), STRATEGIES, DECKS, COUNTERS
hmk/ai/view.py       View: fog-honest perception + memory
hmk/ai/planner.py    Planner: economy, defence, scouting, attack, relic, crates, cards, research
hmk/ai/pilot.py      KingPilot (mode Král)
hmk/ai/commander.py  Commander (mode Stratég)
hmk/ai/actuator.py   Actuator: delayed, APM-limited message queue
hmk/factions.py      (factions doc)       hmk/stats.py   (stats doc; interface: record(summary: dict))
hmk/lobby.py         Lobby, Match, AISeat
hmk/net.py           ws frame/unmask, Client, read_headers, http_response, static_file, websocket, heartbeat, lan_ips, main_cli
data/maps.json  data/puzzles.json           (UTF-8 JSON, loaded once at start; bad entries are skipped with a console warning)
tests/  (unittest, stdlib)                  dev/tools/  (harness, fuzz, perf, ai_ladder: moved here from the scratchpad)
```
- **Mixins are pure moves**: the methods move into other files without changes, so `self.*` calls keep working.
  This lets 4–5 engineers edit different files without merge conflicts.
- **Migration step 0 (one engineer, lands first, no behaviour change):** split the files, add `rng` and `rules`, and
  route the hard-coded `(6, 7)`, `(7, 8)`, `(9, 8)` and `7.5` through map/rules fields. Gate it with a **golden test**:
  `Game(..., rng=random)` with `random.seed(s)` must give the same `state_hash` as the 0.5 `server.py` copy after 600 s
  of harness bots, seeds 1–10, both modes. The module `random` has the same methods as `random.Random`, so the draws
  happen in the same order.
- `Spustit server.bat` stays unchanged (it runs `server.py`). Add `__pycache__/` to `Games/.gitignore`. The server
  serves only `.html/.css/.js`, so `data/*.json` reaches the client through the `defs` message, not over HTTP.
- **Python 3.8 guard**: `tests/test_py38.py` runs `ast.parse(src, feature_version=(3, 8))` on every `hmk/**/*.py` and
  greps for the banned APIs `removeprefix`, `removesuffix`, `functools.cache`, `zoneinfo`, `match `/`case ` statements,
  runtime `X | None` annotations, and dict `|`.
- **Hash-order rule**: never iterate a `set` of `str` without `sorted()`, because `PYTHONHASHSEED` changes that order
  between processes. Today `sd.techs` is only used with `in` and `sorted`; keep it that way.

## 2. Core hooks (the contract every lane codes against)
```python
Game(names, decks, mode, rules=None, map_def=None, seed=None, rng=None, factions=None)
#  mode: 'kral'|'strateg' (control). rules default DuelRules(). map_def default maps.pick_map('ruiny', R).
#  seed None -> random.randrange(2**31) (so harness random.seed() still gives repeatable games). self.seed is kept.
#  self.R = rng or random.Random(seed). EVERY random draw in hmk/ (Ent.__init__ cd/mcd, waves, crates, picks) uses self.R.
g.map      # MapDef: id, name, theme, ter (9 lists of 16 chars), relic (x0, x1, y0, y1), crate_rows, spawn_cols ((6,7),(9,8))
g.play     # rules.play: 'duel' | 'vycvik' | 'preziti' | 'puzzle'
g.visible_fx(side, fx) -> list    # the filter now inside snapshot() (incl. popping pfx[side]); snapshot and AI both use it
g.state_hash() -> str             # sha1 of json [round(t,3), [[e,s,v]x2 rounded 3], throne rounded 3,
                                  #  sorted (id, kind, side, round(x,3), round(y,3), round(hp,3), lvl, path)]

class Rules:                      # hmk/modes.py
    play = 'duel'; checkmate = True; relic = True; night = True; eclipses = ECLIPSES
    def setup(self, g): pass                      # after sides + map exist (puzzle placement, survival tweaks)
    def tick(self, g, dt): pass                   # world schedule: waves, crates, alfa, eclipses, night, mist stage
    def end_check(self, g): return None           # or {'winner': 0|1|-1, 'reason': str}; None -> default throne check
    def allow(self, g, side, m): return True      # called first in Game.act; False = ignore (send refusal via g.say)
    def unit_may_enter(self, g, e, x, y): return True   # extra rule in can_enter and kral_blocked
    def start_extra(self, g, side): return {}     # merged into 'start'
    def snap_extra(self, g, side): return {}      # merged into each snapshot
    def end_extra(self, g): return {}             # merged into 'end'
```
`Game.step` order: `timers` (economy, cooldowns, scrap jobs, King respawn) → `rules.tick` → passives → vision →
entities → throne guns → mines/strikes/charges/crates/drones → `relic_tick` if `rules.relic` → `checkmate` if
`rules.checkmate` → `rules.end_check` or the default throne/both-fall logic. `DuelRules.tick` is the 0.5 code for
waves/crates/alfa/eclipses/night/mist taken out of `timers`, unchanged.

## 3. Maps
### 3.1 Terrain characters (snapshot `ter` string keeps one char per cell)
| char | Czech name | walk (unit, zombie, King) | build | rule |
|---|---|---|---|---|
| `.` | dlažba | yes | yes | |
| `#` | trosky | no | no | own half: scrap 4 s → `.` +25 🔩 (as 0.5) |
| `X` | sloup | no | no | permanent |
| `w` | voda | no | no | permanent (same rule as X, drawn as water) |
| `=` | most | yes | no | |
| `~` | kanál | yes | no | unit/zombie `step_of ×0.75` while standing on it; King speed ×1.25 |
| `^` | vyvýšené místo | yes | yes | a building on it: attack `rng +1.0`, `vision +1.0` |

`maps.py`: `WALK = frozenset('.~^=')`, `BUILD = frozenset('.^')`. Every `ter[y][x] == '.'` / `!= '.'` in the server
becomes `in WALK` / `in BUILD` (build, deploy), and the `'#'` check in `kral_blocked` becomes `not in WALK`. `scrap`
stays `== '#'`. Navnada needs a WALK cell. Jezdec still checks only its landing cell, so it can jump over X/w/#.

### 3.2 `data/maps.json`
```json
{"v": 1, "default": "nahodna", "maps": [
 {"id": "predmesti", "name": "Předměstí", "theme": "predmesti",
  "desc": "Otevřené ulice a rychlý kanál středem Mlhy. Nejlepší na první hry.",
  "half": ["........", "..^.#...", "....#...", ".#......", "......~~", ".#......", "....#...", "..^.#...", "........"],
  "relic": [3, 5], "crates": [0, 1, 2, 3, 4, 5, 6, 7, 8], "random": null}
]}
```
`half` = 9 rows × 8 chars (columns 0–7), mirrored to 15–8. `relic` = rows; the columns are always 7–8 because the zone
must be symmetric. `crates` = rows allowed for drops at x 7/8. `random` (only Ruiny) =
`{"base": [1, 4, 4], "mist": [6, 7, 3]}`: put 4 rubble in columns 1–4 and 3 in columns 6–7, mirrored, with the 0.5
`make_map` retry loop using `g.R`.

**`validate_map` (unit test over all maps)**: 9×8 chars, all of column 0 is `.` (throne column, King spawn),
every WALK cell is reachable by BFS from both throne columns, ≥ 36 BUILD cells in columns 0–5, ≥ 7 BUILD cells in
column 5, all relic cells are WALK, every crate-row cell at x = 7 is WALK, ≥ 8 WALK cells in columns 6–7 (zombie spawns).

### 3.3 The five maps (full boards, already checked against the rules above)
```
Ruiny (ruiny)        Předměstí (predmesti)  Továrna (tovarna)     Most (most)           Metro (metro)
random 0.5 rubble    ................       ......XXXX......      .......ww.......      ....#......#....
relic 3-5            ..^.#......#.^..       ......XXXX......      .......==.......      .#............#.
crates 0-8           ....#......#....       ................      ..#....ww....#..      .~~~~~~~~~~~~~~.
                     .#............#.       ...#..X..X..#...      ...^...ww...^...      ....#......#....
                     ......~~~~......       ...#........#...      .......==.......      ...^........^...
                     .#............#.       ...#..X..X..#...      ...^...ww...^...      ....#......#....
                     ....#......#....       ................      ..#....ww....#..      .~~~~~~~~~~~~~~.
                     ..^.#......#.^..       ......XXXX......      .......==.......      .#............#.
                     ................       ......XXXX......      .......ww.......      ....#......#....
relic rows           3-5                    3-5                   4-4 (centre bridge)   3-5
crate rows           0-8                    2-6                   1, 7 (bridges)        0,1,3,4,5,7,8
character            open, beginner         3 gates in the Mist   3 bridges, high       2 fast canal lanes,
                                            per side              ground covers them    small bases (38 cells)
```
- **Lobby**: `{t:'map', v:id|'nahodna'}` works like `mode` (seated players only, outside a match, resets ready).
  Default: `nahodna` for PvP, `predmesti` for Výcvik and Puzzle. `nahodna` picks uniformly from the 5 maps with `g.R`.
- **Fairness gate (dev/tools/ai_ladder.py)**: on every map, Těžká vs Těžká, 20 seeds × 2 modes, side 0 must win
  40–60 %. Harness Mixed vs Attacker must also stay inside ±10 % of the Ruiny numbers.
- **Client**: new `js/maps.js` with `drawMapPreview(canvas, ter)` for the lobby (16×9, 8 px cells) and
  `TERRAIN_SPR` painters (pillar, water with ripples, planks, canal with flow chevrons, raised flagstone dais),
  plus a theme floor tint per map. `input.js`/`render.js`: passability uses `WALK`, buildability uses `BUILD`, and
  tooltips read "Kanál: jednotky a zombie jsou tu rychlejší", "Vyvýšené místo: věž tu má +1 dosah a dohled",
  "Sloup / Voda: neprůchozí".

## 4. Lobby and matches
- `Match` (hmk/lobby.py): `game`, `seats` [Client|AISeat|None, ×2], `play`, `solo: bool`, `paused`, `task`,
  `run()` (the 0.5 loop: `for ai in ais: ai.on_tick()` → `g.step(TICK)` → snapshots to human seats),
  `finish(result)` (sends `end`, calls `stats.record(summary)`, puts the humans back into the lobby with
  `Lobby.join`). Headless `Match.simulate(seconds)` is used by tests and tools.
- `Lobby`: `pvp: Match|None` (seats as in 0.5) plus `solos: list[Match]` (max `SOLO_MAX = 3`). Each `Client` has a
  `match` field, and in-match messages go to `c.match.game.act(c.side, m)`. In a solo match the human is always side 0.
- `{t:'solo', what, mode, diff, map, puzzle, deck, faction}` with `what` = `vycvik` | `preziti` | `puzzle`. It
  frees the PvP seat (`seat()` fills it from the queue) and is refused while `len(solos) == SOLO_MAX` with
  "Server je vytížený, zkus to za chvíli.". Přežití for 2 players uses the PvP seats:
  `{t:'play', v:'duel'|'preziti'}` (resets ready, like `mode`).
- Solo only: `{t:'pause', v:bool}` freezes `run()` and snapshots carry `ps: 1`; `{t:'restart'}` rebuilds the match
  (puzzle: same seed; others: new seed). For everyone: `{t:'leave'}` means surrender (PvP: the opponent wins;
  solo: the match ends and you return to the lobby).
- **Lobby UI (`js/solo.js`, new)**: the left folio gets tabs **Souboj** (mode, Typ hry Souboj/Přežití, Mapa,
  Připraven) | **Výcvik** (Obtížnost Lehká/Střední/Těžká, mode, map, Hrát) | **Přežití sám** (mode, map,
  Soupeř: nikdo/Lehká/Střední/Těžká) | **Puzzle** (grid of 10 cards with stars). AI names: Lehká „Zbloudilý mnich“,
  Střední „Kastelán“, Těžká „Mrtvý velmistr“.

## 5. AI (Výcvik, Přežití opponent, puzzle enemies)
### 5.1 Structure (per tick, inside `Match.run`)
```python
class AIPlayer:                           # hmk/ai/__init__.py
    def __init__(self, g, side, diff, seed, play, deck=None, faction=None):
        self.rnd = random.Random(seed * 1000003 + side * 7919 + DIFF[diff]['salt'])
        self.view, self.act = View(g, side), Actuator(g, side, DIFF[diff], self.rnd)
        self.plan = Planner(...); self.pilot = KingPilot(...) if g.mode == 'kral' else None
        self.cmd = Commander(...) if g.mode == 'strateg' else None
    def on_tick(self):                    # before g.step; uses g.t only, never the wall clock
        fx = self.view.feed()             # g.visible_fx(side, g.fx) of the last tick
        if g.t >= self.next_think: self.plan.think(); (self.cmd or self.pilot).think(); self.next_think += DIFF.think
        if self.pilot: self.pilot.reflex(fx)   # every tick: parry/dash scheduling, steering
        self.act.flush()                  # sends due messages through g.act(side, msg)
```
- **View is the only way the AI may touch the game.** It exposes `mine()`, `seen()` (filtered by
  `g.can_see(side, e)`), `ghosts` (last-seen enemy buildings `{id: (kind, x, y, lvl, path, t_seen)}`, dropped when
  the cell is visible and empty), public state (`throne`, `relic`, `crates`, `eclipse()`, `night`, `stage`,
  `next_wave`), own `Side` resources and cooldowns, and the fx stream. `tests/test_ai_fog.py` fails if any file in
  `hmk/ai/` other than `view.py` contains `g.ents`, `.ents.`, `.aim`, `.length`, `sd[1 - ` or `.deck` of the foe.
  At runtime it also checks that every entity id the planner targeted was visible to that side at that tick.
- **Actuator**: every message gets `due = t + delay` with `delay ~ N(react, react_sd)`, clamped to ≥ 0.12 s. At most one
  non-movement message per `60 / APM` s. A refused action (no new entity next think) is not retried for 3 s.
  King `in` messages are exempt from APM, but the direction may change only every `steer` s.

### 5.2 Planner (think)
Priority order. Each think executes the first affordable items, up to `acts` items per think.
1. **Emergency**: rows where the threat (Σ hp × dps of visible enemy units/zombies at own local x ≤ 7) is not
   covered by an own attack tower within ±1 row. Build the counter at `(front_lx − 1, row)`: zombies or Pěšák mass →
   Plamenomet, Obrněnec → Kulomet (Odstřelovač when Doba II and energy ≥ 200), Jezdec → Plamenomet or Mina,
   Sabotér seen → Hláska B. Stratég: also Commander rules.
2. **Economy**: generator target by time (5.3). Gen L2 when ≥ 5 attack towers stand; L3 via Přetavení from Doba II (Těžká).
3. **Defence template** (the harness `Mixed` layout L1, L2, walls, in local coordinates). Rows are re-ordered by a
   map weight (number of WALK cells at x 6/9 within ±1 row, so Továrna/Most gates come first), and cells that are not
   BUILD are skipped. `^` cells go first for Odstřelovač and Hláska.
4. **Scouting**: Hláska at (3, 4) by 45 s, then L2. Průzkumný dron card if it is in the deck (period in 5.3). Hláska
   B (Reflektor) when a mine/sabotér has been seen or an eclipse is ≤ 60 s away (Těžká).
5. **Attack**: see 5.4. **6. Relic** and **7. Crates**: see 5.5. **8. Upgrades**: attack towers in the most-threatened
   rows → L2 → L3 with paths Kulomet A, Plamenomet A, Odstřelovač A if ≥ 3 else B, Tesla B, Zeď L2.
   **9. Research** by strategy (5.3). The AI never reads `g.length`: it learns the phase from public events
   (Mist stage, night).

### 5.3 Difficulty table (`profiles.DIFF`)
| param | Lehká | Střední | Těžká |
|---|---|---|---|
| think period / acts per think | 1.2 s / 1 | 0.6 s / 2 | 0.3 s / 3 |
| reaction delay N(mean, sd) | 0.8, 0.3 s | 0.45, 0.15 s | 0.25, 0.08 s |
| APM cap / steer period | 30 / 0.35 s | 60 / 0.2 s | 120 / 0.1 s |
| misplace build (random valid own cell) | 20 % | 7 % | 0 |
| generators | 3, +1 at 240 s, L2 only | 3 → 4 (60 s) → 5 (150 s), L2 | 3 → 5 by 90 s, L2 120 s, L3 |
| Přetavení | never | when scrap blocks an upgrade | yes, plus generator L3 |
| first push / push budget | ≥ 210 s / 200 ⚡ | ≥ 120 s / max(300, 35 s of income) | ≥ 90 s / max(300, 40 s of income) |
| eclipse / night timing | never | 50 % of pushes | always + all-in at night |
| scouting | Hláska only | + dron every 90 s | 2 Hlásky + dron every 60 s + adaptation |
| relic | from 300 s, King / 1 Pěšák every 60 s | harness `contest()` | contest + Odstřel on the capturer + retake |
| crates | only crates at own x (7 for side 0) | all uncontested | all + Odstřel the hovering enemy drone |
| cards | Nálet only | all, simple triggers | all, cluster-value targeting |
| Tlupa | never | with each push | when the push enters the Mist |
| Stratég anti-mate (never both Odstřel and Štít on cooldown) | no | yes | yes |
| parry attempt / reaction N(ms) | 25 % / 420, 90 | 60 % / 330, 60 | 90 % / 280, 40 (all clamped 180–700) |
| dash dodge when block is on cooldown | no | 30 % | 80 % |
| King retreats at HP | 20 % | 35 % | 45 % |
| strategies (picked by `rnd` per match) | mixed | mixed 60 %, turtle-push 40 % | mixed 40, turtle-push 35, rush 25 |

Decks (`profiles.DECKS`): mixed `kulomet plamen sniper hlaska pesak obrnenec medik nalet`; turtle-push
`sniper hlaska kulomet plamen pesak obrnenec nalet vypadek`; rush `kulomet hlaska pesak jezdec obrnenec strelec medik vypadek`.
Těžká swaps `nalet` for `dron` when the deck has no Hláska. Research: defensive `ing1 arm1 ing2 ing3 arm2`, offensive
`arm1 arm2 ing1 arm3`. Factions: `profiles.FACTION_PLAN[faction]` can override deck, research and template; that
table is filled in once the factions doc fixes the content.

### 5.4 Attack
- **Composition** from `COUNTERS` using seen and ghost defence: ≥ 3 Odstřelovač → `obrnenec obrnenec medik pesak pesak pesak`
  + Útok!/war cry at the wall + Nálet on the sniper cluster; ≥ 2 Plamenomet → Jezdec flank on rows without Plamenomet;
  mines suspected (a unit died with no visible shooter) → Pěšák in front; otherwise the harness `mix` COMP.
  Stagger as in the harness (tanks 0 s, Pěšák/Medik +4, Pašerák +5, Jezdec +8).
- **Lane**: the 3 adjacent rows with the lowest known defence power (Σ dps of seen/ghost towers whose range covers
  that row).
- **Timing** (Střední at 50 %, Těžká always): when the next eclipse `E` is ≤ 30 s away, launch the tanks at `E − 18 s`
  so the push reaches the enemy front at the start of the darkness. Night start = all-in. Otherwise push when
  energy ≥ budget. Rush (Těžká): at 70–90 s, 4 Pěšák + 1 Obrněnec, only if scouting saw < 2 enemy attack towers.
- **At the push**: Výpadek when ≥ 3 own units are at enemy local x ≤ 6. Nálet on the visible cell with the highest
  value (2 per Hláska and 1 per other building in 3×3, −0.5 per own unit there), cast at value ≥ 2. Tlupa when the
  push enters the Mist. Útok! (G) when ≥ 3 units are at enemy local x ≤ 8. War cry when the meter is full, the King
  is outside his half and ≥ 2 own units are within 3 cells.
- **Adaptation** (Těžká, Střední only at 360 s): at 180 s and 360 s, re-pick the strategy from the seen-kind
  counts (foe turtles → turtle-push timing; foe rushes → +2 Plamenomet, +1 Kulomet in the front rows).

### 5.5 KingPilot, Commander, relic, crates
- **KingPilot goals** (in this order): retreat home at low HP (table) → stand 2 cells behind the threatened row
  while enemies are in the own half (the King shoots automatically) → crate (distance ≤ 6, not contested by more
  power) → Relikvie (HP > 60 %, base not under threat) → repair (hold `r` next to the most damaged building, needs
  scrap) → escort 1.5 cells behind the leading unit → idle at local (2, 4).
  **Path**: A* on the cell grid over cells the King can enter (`kral_blocked` at the cell centre), following
  waypoints with `mx/my ∈ {−1, 0, 1}`. **Danger**: cells inside the range of seen/ghost enemy attack towers cost
  +3 (Těžká always, Střední below 50 % HP, Lehká never).
- **Reflexes**: when the fx `['a', sx, sy, tx, ty, side, target_id]` targets my King, attempt with probability
  `parry_p`: press `b` at `t0 + reaction`, hold 0.35 s, release. The parry works when the reaction falls in 0.2–0.5 s
  (aim 0.5 s, parry window 0.3 s). If the block is on cooldown, dash with probability `dash_p` (perpendicular to the
  laser) at the same reaction time. `d`, `u` and `b` are sent as rising edges, exactly like the client.
- **Commander**: the harness `commands()` with `SMART` on (Střední/Těžká). Oprava below 60 % HP, Odstřel on the
  strongest enemy unit in the own half (attacker: weakest visible building), Sběr on a crate with `land ≤ 3 s`,
  Štít when the throne lost ≥ 15 HP since the last think or when in check, Útok! as in 5.4.
- **Relic squad**: `planner.relic_squad()` = Obrněnec + 2 Pěšák (or the 3 cheapest units in the deck) deployed at
  `front_lx`, rows 4/4/3, staggered 0/4/5 s. It goes out when the relic is not ours, ≤ 3 foes are in columns 6–9,
  energy ≥ 170 and ≤ 1 own unit is on the way. The same function backs the human **Četa na Relikvii (H)**:
  `{t:'squad', id:'relic'}`, Stratég only, normal costs and deploy rules, cooldown 20 s, refused before 120 s.
  The snapshot sends `sq: [cost, cd]` when it is available.

### 5.6 Verification (`dev/tools/ai_ladder.py`, multiprocessing, 10 seeds × 2 modes × 2 sides × 5 maps)
- Těžká beats Střední ≥ 70 %. Střední beats Lehká ≥ 75 %.
- Lehká vs `NoviceBot` (new scripted baseline that plays like a first-time player: 3 generators, 3 Kulomets at x 4,
  2 Pěšák every 60 s, no upgrades) wins 40–60 %. Střední vs NoviceBot ≥ 85 %.
- Těžká vs harness Turtle (2 sniper columns) ≥ 80 %. Median Střední match length is 8–13 min.
- **Determinism**: `tests/test_ai_determinism.py` runs Těžká vs Střední for 300 s with seed 5 in two subprocesses
  with different `PYTHONHASHSEED`; the `state_hash` must be equal.
- **Performance**: AI ≤ 2 ms per think at Těžká, and the whole tick with 2 AIs at p99 ≤ 5 ms (dev/tools/perf.py).

## 6. Přežití
- `SurvivalRules(players=1|2)`: `play='preziti'`, `relic=False`, `checkmate=False`, `night=False`, no Alfa timer
  (bosses come with the waves). Any map and either control mode. Start: 200 ⚡ 40 🔩, throne 3000, normal income.
- **Quarantine wall**: `unit_may_enter` blocks side-0 units/King at x ≥ 8 and side-1 at x ≤ 7. Zombies are not
  affected. Units may still clear their own half of the Mist and pick up crates. Pěšák promotion never happens.
  `allow` refuses Sběr on a crate in the other half ("Tahle bedna patří soupeři.").
- **Crates**: mirrored pairs with the same rarity, one at x = 7 for side 0 and one at x = 8 for side 1 (map crate
  rows), every `R.uniform(45, 60)` s, first one at 40 s (at least neobvyklá). The Alfa reward crate lands in the
  killer's own crate column.
- **Waves** (`SURV` constants in `modes.py`, the same waves for both sides, spawned as mirrored pairs exactly like 0.5 `wave()`):
```python
t_1 = 30.0;  t_(k+1) = t_k + max(18.0, 32.0 - 0.6*k)
budget(k) = round(2.0 + 1.6*k + 0.07*k*k)          # SURV_C = 0.07 is the single tuning knob
obr  = int(budget*0.25 // 8) if k >= 8 else 0;  n = budget - 8*obr
if n > 36: obr += ceil((n-36)/8); n = 36          # entity cap: 36 small zombies + obři per side
run  = round(n * min(0.45, 0.05*k)) if k >= 4 else 0;  walk = n - run
alfa = k // 10 if k % 10 == 0 else 0              # boss waves 10, 20, 30… (Alfa on top of the budget)
hp, dmg multipliers from wave 12: ×(1 + 0.05*(k-11)), ×(1 + 0.03*(k-11))   # loot unchanged
spawn: ≤ 6 zombies per side every 0.5 s into free WALK cells of the spawn columns (queue the rest)
```
  | wave | 1 | 5 | 10 | 15 | 20 | 25 | 30 |
  |---|---|---|---|---|---|---|---|
  | time (s) | 30 | 152 | 291 | 415 | 524 | 618 | 708 |
  | Chodec / Běžec / Obr / Alfa | 4/0/0/0 | 9/3/0/0 | 14/11/0/1 | 19/15/1/0 | 20/16/4/2 | 20/16/7/0 | 20/16/10/3 |
  | HP × | 1 | 1 | 1 | 1.2 | 1.45 | 1.7 | 1.95 |
- **Events**: an eclipse (25 s, warned 15 s ahead) starts with waves 5, 10, 15, …. The Mist advances one column
  (stage +1) at waves 10, 20 and 30. After wave 30 comes "Věčná noc" (permanent darkness, no throne drain).
- **Interaction (2 players only)**: Tlupa costs 120 ⚡ (Biotech discount applies), cooldown 25 s, and sends
  `round(0.35 × budget(k_current))` points with the wave composition rules into the opponent's Mist half. Výpadek
  proudu works on the opponent. In solo games both are hidden and refused.
- **End**: 2 players, a throne falls → the other player wins ("Hráč X vydržel déle."). Both fall in the same tick →
  more zombie kills wins, else a draw. Solo → ends when the throne falls. vs AI → like 2 players (the AI uses its
  `play='preziti'` profile: no pushes, units only for crates and clearing its Mist half, Tlupa at Střední/Těžká).
- **Snapshot** `sv: [wave, secs_to_next, zombies_alive_mine, zombies_alive_foe]`. **End** `surv: {wave: [a, b],
  t: [a, b]}`, where wave = the last wave fully cleared. The client keeps a best result in `localStorage`
  `hmk_surv` = `{"<map>|<mode>": {"w": 17, "t": 751}}` and shows „Rekord: 17 vln (12:31)“.
- **Tuning targets** (harness bots, 20 seeds): Mixed defender dies at wave 18–22 (median ~20, ~9 min), Turtle at
  16–20, an idle player at wave 4–6. Change only `SURV_C` to hit them. Two equal Mixed bots: side 0 wins 45–55 %.

## 7. Puzzle
### 7.1 Rules and format
`PuzzleRules(puzzle)`: the player is side 0 and the board is the named map. Waves, crates, Alfa, relic, eclipses and
night are off unless the puzzle's `world` turns them on. The enemy is side 1 with no King unless `foe.king` is set,
and no AI unless `foe.ai` names a script. The deck may have fewer than 8 cards and skips `valid_deck`. The base kit
(gen, zed) is included only with `"kit": true`; `start` sends `kit` and `deck`, and the client builds the bar from
`kit + deck`. The seed is fixed per puzzle.
```json
{"id": "p02", "name": "Obraň trůn 30 s", "mode": "kral", "map": "predmesti", "seed": 2, "time": 30,
 "desc": "Soupeřova četa už prošla Mlhou. Vydrž 30 sekund.",
 "goal": {"type": "survive"},
 "you": {"res": [250, 40, 0], "income": 0, "throne": 1200, "deck": ["kulomet", "plamen", "mina", "zed"], "kit": false,
         "doba": 1, "techs": [], "king": true, "respawn": 15},
 "foe": {"res": [0, 0, 0], "income": 0, "throne": 3000, "king": false, "helpless": false, "ai": null},
 "place": [{"k": "obrnenec", "s": 1, "x": 9, "y": 3}, {"k": "obrnenec", "s": 1, "x": 9, "y": 5},
           {"k": "pesak", "s": 1, "x": 10, "y": 2}, {"k": "pesak", "s": 1, "x": 10, "y": 4}, {"k": "pesak", "s": 1, "x": 10, "y": 6}],
 "script": [{"t": 12, "do": "zombies", "kinds": ["chodec", "chodec", "bezec"], "rows": [2, 4, 6], "x": 7, "tgt": 0}],
 "world": {"waves": false, "crates": false, "alfa": false, "relic": false, "eclipses": [], "night": false},
 "stars": [{"k": "win"}, {"k": "throne_min", "v": 900}, {"k": "lost_max", "v": 0}]}
```
- `place` options: `lvl`, `path`, `hp` (fraction), `stun` (s), `vet`, `tag`. Mines are hidden as usual.
- `script.do`: `zombies` · `unit` (k, s, x, y) · `crate` (x, y, r, land) · `say` (text) · `eclipse` (len: dark now)
  · `night` (start Poslední noc now) · `reveal` (x, y, r, secs, for the player).
- `goal.type`: `survive` (win at `time` with throne > 0 and the `keep` tags alive) · `destroy` (`tags` | `"what": "towers"|"throne"`)
  · `mate` (the enemy stays in check for 10 s; `foe.helpless: true` forces helpless) · `collect` (n crates) ·
  `relic` (`hold` s of total ownership) · `promote` (any own Dáma from a promotion) · `win` (the enemy throne falls).
  It fails on timeout (all goals except survive), when the own throne reaches 0, or when the King dies if
  `"king_must_live": true`.
- Star keys: `win`, `throne_min`, `time_max`, `spent_max` (energy spent), `lost_max` (own units and buildings lost),
  `king_hp_min` (fraction at the end), `parries_min`, `left_min` (energy left), `cards_max` (abilities cast),
  `units_max` (units deployed), `alive_min` (own units alive at the end). Star 1 is always `win`.
  The server computes `metrics` and stars, and `end` carries `puzzle: {id, ok, stars, t, metrics}`. The snapshot
  carries `pz: [secs_left, progress, target]`.
- **Progress**: `localStorage` key `hmk_puzzle` = `{"v": 1, "p": {"p02": {"s": 3, "t": 21.4}}}`. The best stars
  are kept. Puzzles p01–p03 are always open; p(n) opens when p(n−1) has ≥ 1 star. The client enforces this (local
  progress only).

### 7.2 The ten puzzles (x/y absolute; the player is on the left)
| id | name | mode | goal / time | you | enemy setup | ★2 / ★3 |
|---|---|---|---|---|---|---|
| p01 | Hlídka u brány | stratég | survive 40 s | throne 500, 175 ⚡ 30 🔩, Kulomet Plamen Mina + kit | zombies t3: 3 Chodec rows 3–5; t15: 4 Chodec 2 Běžec rows 2–6; t28: 6 Chodec 2 Běžec | throne ≥ 400 / throne 500 |
| p02 | Obraň trůn 30 s | král | survive 30 s | as in 7.1 | as in 7.1 | throne ≥ 900 / lost 0 |
| p03 | Rudá nit | král | collect 1 crate at (8,4) in 40 s, king_must_live, respawn off | 0 ⚡ | Odstřelovač (11,2) (11,6), Hláska (12,4) | parries ≥ 2 / King HP ≥ 50 % |
| p04 | Přes zeď | stratég | destroy tag `h` in 60 s | 300 ⚡, Jezdec Pěšák Obrněnec | betonová Zeď x 11 rows 0–8, Kulomet (12,3) (12,5), Hláska `h` (13,4) | time ≤ 35 / spent ≤ 210 |
| p05 | Proraz obranu s 300 energie | stratég | destroy towers in 90 s | 300 ⚡, Pěšák Obrněnec Medik Pašerák, commands ready | Odstřelovač (12,3) (12,5), Kulomet (11,4), Hláska (13,4) | time ≤ 60 / `alive_min` 2 |
| p06 | Šach-mat za 60 s | král | mate in 60 s, foe helpless | 400 ⚡, Pěšák Jezdec Obrněnec Medik | Kulomet (14,1), Plamenomet (14,7), Zeď (14,3–5) | time ≤ 45 / lost ≤ 3 |
| p07 | Zatmění | stratég | destroy towers in 40 s; script eclipse at t 8 for 25 s | 450 ⚡, Pěšák Obrněnec Jezdec Sabotér | Odstřelovač (12,2) (12,4) (12,6), Hláska L3 (13,4) | time ≤ 33 / spent ≤ 350 |
| p08 | Relikvie | stratég | relic hold 25 s in 100 s; world.relic on from t 0 | 350 ⚡, income 3/s, Pěšák Obrněnec Medik Kulomet | foe.ai `relic_squads`: Obrněnec + 2 Pěšák to the relic every 20 s | time ≤ 70 / never lose it after the first capture |
| p09 | Pastýř mrtvých | stratég | destroy tags `g1 g2` in 80 s, no unit cards | Návnada (cd 20 here) Karanténa, throne 3000 | 20 Chodec in the Mist at t 0 heading to you; Generátor `g1` (13,2) `g2` (13,6), Kulomet (11,4) | throne ≥ 2500 / time ≤ 60 |
| p10 | Dáma | král | promote in 50 s | 260 ⚡, Pěšák Obrněnec Medik Jezdec | Odstřelovač (13,4), Hláska (14,4), Plamenomet (12,2) (12,6), Mina (11,3) (11,5); desc warns about mines | time ≤ 35 / `units_max` 4 |

Each puzzle ships with `tests/puzzle_solutions.py`: a list of timed messages. `tests/test_puzzles.py` replays it
and asserts 3 stars, which proves the puzzle is solvable and deterministic. A designer who changes a puzzle must
update its solution. Puzzle text is Czech and reviewed with `kontrola-cestiny`.

## 8. Protocol delta (VERSION and CLIENT_VER '1.0')
- `defs` + `maps: [{id, name, desc, theme, ter (144 chars), relic, crates}]`, `puzzles: [{id, name, desc, mode, time,
  goal_text, stars_text: [3]}]`, `diffs: [['lehka', 'Lehká'], ['stredni', 'Střední'], ['tezka', 'Těžká']]`, `squad: [cd, from]`.
- `lobby` + `map`, `play`, `solo: [running, SOLO_MAX]`.
- Client → server new: `map`, `play`, `solo`, `pause`, `restart`, `leave`, `squad` (sections 3, 4, 5.5).
- `start` + `play`, `map: {id, name, theme}`, `seed`, `ai: {diff, name}|null`, `kit`, `puzzle: {...}|null`, `surv: {players}|null`.
- Snapshot + `ps`, `pz`, `sv`, `sq` (each only when it applies). `end` + `play`, `seed`, `map`, `puzzle`, `surv`.

## 9. Work order (parallel lanes after step 0)
0. **Split + RNG + Rules hooks + golden test** (blocks everything; 1 engineer, ~1 day).
1. **Maps**: `maps.py`, `data/maps.json`, WALK/BUILD refactor, `~`/`^` effects, client `js/maps.js` and terrain sprites.
2. **Lobby/Match/net**: Match, solos, pause/restart/leave, protocol, `js/solo.js` tabs.
3. **AI**: `hmk/ai/*`, `dev/tools/ai_ladder.py`, NoviceBot, fog lint, determinism test. It starts on Ruiny and
   needs lane 1's `WALK` before map work.
4. **Modes**: SurvivalRules + tuning, PuzzleRules + `puzzles.json` + solutions (the p08 enemy uses lane 3's squad code).
5. **Integration**: fuzz (new message types, every play type), perf with 2 AIs + 3 solo matches, LAN test on port 8097
   (close the test tabs afterwards), README/DESIGN updates in Czech.
