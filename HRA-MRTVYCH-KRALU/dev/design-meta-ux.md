# 1.0 design: meta, statistics, cosmetics, UX, polish

Scope: profiles and statistics, XP and levels, achievements, cosmetics, lobby and sessions, tutorial, settings and
accessibility, rendering performance, release packaging. Gameplay of modes, maps, factions and AI belongs to the other
`dev/design-*.md` docs. This doc fixes the lobby protocol and the meta layer that sits around them.

## 0. Interfaces with the other 1.0 docs

- The lobby renders whatever the server registries contain. `DEFS_MSG` gets these lists:
  `types`, `maps`, `factions`, `ai`, `puzzles` (each `[{id, name, desc, ...}]`), plus the meta catalogs `cosm`, `ach` and `levels`.
  Content and ids come from the owning doc. This doc uses these placeholder ids:
  - types `souboj` (PvP), `preziti`, `vycvik`, `puzzle`, `vyuka` (tutorial)
  - factions `prezivsi`, `korporace`, `kult`
  - AI levels: index 0, 1 and 2 of `defs.ai`, from easiest to hardest
  
  Where an owning doc names an id differently, its name wins. The meta code only uses the ids as keys.
- The AI plugs into a `Session` (section 4.2) as a controller for side 1. It calls `game.act(1, msg)` and sets
  `game.sd[1].inp`. The tutorial director (section 5) needs two things from the AI: a flag `ai.hold` (build defensively,
  send no units) and `ai.release()`.
- Every `Game.over` dict gets `'end'`, one of `throne | mat | both | draw | night | disc | error | survive | solved | failed | quit`.
  `night` means a throne fell while `g.night` was true.
- New files: `meta.py` (stdlib only: profiles, XP, achievements, Elo, persistence; no asyncio, unit-testable),
  `js/meta.js` (stats screen, cosmetics tab, achievements tab, end graphs, XP bar, tutorial card) and
  `js/settings.js` (settings dialog, sound test, quality). Script order:
  `base, paint, ui, render, input, audio, meta, settings, main`.

## 1. Profiles and statistics

### 1.1 Storage
- The file is `stats.json` next to `server.py`. `--stats PATH` overrides the path and `--no-stats` disables it (the bots, fuzz
  and balance harnesses must always pass `--no-stats` or a temp path).
  The env var `HMK_STATS` works like `--stats`.
- `meta.Store(path)`:
  - `load()`: try `path`. If it is missing, start a new file. If it is corrupt, try `path + '.bak'`.
    If both are corrupt, rename the bad file to `stats.corrupt-YYYYMMDD-HHMMSS.json`, print
    `  ! stats.json poskozen, zalozen novy (stary: <name>)` and start fresh.
    Then run `normalize()`: fill missing keys with defaults, drop wrongly typed values and clamp numbers.
    Never raise.
  - `save()`:
    1. Write `path.tmp` with `json.dump(ensure_ascii=False, separators=(',',':'))`, then `flush` and `os.fsync`.
    2. If `path` exists, `os.replace(path, path.bak)`.
    3. `os.replace(tmp, path)`.
    
    On `PermissionError` (Windows antivirus or an open editor), retry 3× at 50 ms. If it still fails, keep the data in
    memory, print a warning, and save again at the next trigger.
  - When to save: synchronously right after the `end` broadcast, and 2 s after a cosmetics change
    (`loop.call_later`, debounced).
- Profile key: `meta.key(name) = ' '.join(name.split()).casefold()`.
  - An empty name has no profile. The lobby then shows "Zadej si jméno, ať se ti počítají statistiky a odemykají odměny."
  - The default placeholder "Král" is not prefilled any more.
  - Max 500 profiles. On overflow, drop the profile with the oldest `last`.
- Duplicate names in a 2-player room: refuse `ready` and send `{t:'lerr', text:'Oba máte jméno „X“. Jeden si ho změňte, jinak se statistiky smíchají.'}`.
- Never stored: IP addresses, decks.
- `.gitignore` in the game folder: `stats.json`, `stats.json.*`, `stats.corrupt-*.json`, `dist/`, `__pycache__/`.

### 1.2 Schema (`v: 1`)
```json
{ "v": 1, "next_id": 138,
  "players": { "jarda": {
      "name": "Jarda", "created": "2026-10-20", "last": "2026-10-20T18:03",
      "xp": 1234, "lvl": 7, "elo": 1032, "elo_n": 9, "fwd": "2026-10-20",
      "tot":  {"m":12,"w":7,"l":5,"d":0,"time":7200,"zk":610,"uk":95,"bk":31,"kk":6,"cr":41,"parry":17,"alfa":2,"promo":3,"relic_s":930,"tech":44},
      "by":   {"souboj.kral":[8,5,3,0], "souboj.strateg":[2,1,1,0], "vycvik.kral.1":[2,1,1,0], "preziti.kral":[1,0,0,0]},
      "fac":  {"prezivsi":[5,3], "korporace":[4,2], "kult":[3,2]},
      "h2h":  {"petr":[4,2,0]},
      "rec":  {"fast_win":[288,131], "kills":[74,120], "crates":[7,133], "parry":[9,128], "relic_s":[310,133], "doba3":[402,129], "dmg":[6400,131], "surv":[611,135]},
      "streak": [2, 4],
      "ach":  {"korunovace":"2026-10-18", "zrcadlo":"2026-10-20"},
      "puz":  {"p01":[3,41], "p02":[1,88]},
      "cos":  {"fig":"goticke","ban":"lebka","kor":"zlata","dlaz":"piskovec","zab":"jiskry","vit":"zlate"},
      "tut": 1 } },
  "matches": [ { "id":137, "at":"2026-10-20T18:03", "type":"souboj", "mode":"kral", "map":"krypta", "len":712, "end":"throne",
      "ai":null, "win":0,
      "p":[{"k":"jarda","n":"Jarda","fac":"kult","res":"w","th":1820,"zk":40,"uk":22,"bk":5,"kk":2,"cr":6,"tech":5,"doba":3,
            "dmg":5400,"inc":[7.4,11.5],"lost":19,"xp":178,"elo":[1016,1032]}, {"k":"petr", "...": "..."}],
      "ser": {"dt":5, "th":[[...],[...]], "inc":[[...],[...]], "army":[[...],[...]], "ecl":[[240,265],[420,445]], "night":702} } ] }
```
- `matches` keeps the newest 50, newest first. Only the newest 10 keep `ser`. A stats file is about 100 KB.
- `res` is `w | l | d`. `inc` is `[average, peak]` ⚡/s. `by` keys are `type.mode[.aiIndex]` and the values are `[m, w, l, d]`.
  - Přežití solo uses `[m, best_s]`.
  - Puzzle uses `puz[id] = [stars, best_s]`.
- Every `rec` value is `[value, matchId]`. The end screen lists records broken in that match as "Nový rekord: …".

### 1.3 Per-match counters (server)
Extend `Side.stats`. Existing keys: `kills units built crates techs`. New keys:

| key | incremented in |
|---|---|
| `zk` | `kill()`, zombie branch |
| `uk` | `kill()`, enemy unit branch |
| `bk` | `kill()`, building of the enemy side |
| `kk` | `kill()`, King branch, credited to the killer |
| `lost` | `kill()`, any own unit or building, credited to the victim side |
| `parry` | `damage()`, successful parry |
| `alfa` | `kill()`, `alfa` |
| `promo` | `promote()` |
| `relic_s` | `relic_tick()`, `+= dt` while `own == s` |
| `vet_max` | `make_vet()`: count own live veterans, keep the max |
| `doba_t` | `[t2, t3]`, game time when Doba II and III were reached (`research()`) |

`kills` stays `zk + uk`, because the end table uses it.

### 1.4 Time series (end-screen graphs)
- Call `Game.sample()` at `t = 0`, then every 5.0 s (`self.next_sample`), and once more inside `finish()`.
- Per side it records three values:
  - `th`: `int(throne)`
  - `inc`: `round(income(s) * 10)`
  - `army`: Σ over live own units of `(cost_e + 3·cost_s)`, plus Σ over own `ATTACK_TOWERS` of `(cost_e + 3·cost_s)·LVL_MULT[lvl-1]`.
    The King, generators and walls are excluded.
- Store `g.ecl_log` (`[start, end]` of each eclipse that ran) and `g.night_t`.
- The series go only into the `end` payload, never into snapshots, so the fog of war is safe.
  A 20-minute match has 241 samples × 6 ints.

### 1.5 XP, levels, Elo (`meta.py`)
- Matches shorter than 60 s are not recorded: no XP, no history entry.
- `xp_gain(rec, side)` returns `[[label, n], ...]`:
  - Base: souboj 50, preziti 40, vycvik 30, vyuka 100 (first time only).
    Puzzle: first solve 40, a repeat solve 5.
  - "Čas ve hře": +4 per full minute, max 60.
  - "Vítězství": souboj +80, Přežití 1v1 (outlasted the opponent) +60, Výcvik +40. A souboj draw gives +30.
  - Výcvik multiplies base, time and win by `[0.5, 0.8, 1.0][aiIndex]`.
  - "První výhra dne": +60 for the first win on the host's local date (`fwd`), in souboj or in Výcvik with aiIndex ≥ 1.
  - "Úspěch: <name>": the XP of each newly unlocked achievement.
  - Disconnect (`end == 'disc'`): the leaver gets 0 XP and `res = l`. The stayer gets base + time + 50 % of the win bonus.
    Win-dependent achievements do not count.
- Level: `need(L) = 100·(L−1) + 25·(L−1)·(L−2)`, so level 2 at 100, 3 at 250, 5 at 700, 10 at 2700, 15 at 5950, 20 at 10450.
  The level cap is 30. A typical match gives about 100–240 XP.
- Titles shown next to the level:

  | level | 1 | 3 | 5 | 8 | 12 | 16 | 20 | 25 | 30 |
  |---|---|---|---|---|---|---|---|---|---|
  | title | Panoš | Zbrojnoš | Rytíř | Pán hradu | Baron | Hrabě | Vévoda | Kníže | Mrtvý král |
- Elo: only souboj matches between two named players. Start at 1000.
  `E = 1/(1+10^((Rb−Ra)/400))`, `K = 40` while `elo_n < 10`, otherwise 24. A draw counts 0.5.
  Round to int and update both profiles from the pre-match values.
- `meta.record(store, game_summary) -> per_side_result` builds the match record, updates `tot/by/fac/h2h/rec/streak/elo`,
  runs `check_achievements`, applies the XP and computes new unlocks.
  It returns `{xp_parts, xp, lvl, next, lvlup, new_ach, new_cos, new_rec, elo}` per human side.
  It is pure apart from mutating `store.data`.

### 1.6 Protocol
- After `hello` (and after a name change, 300 ms debounce), the server sends
  `{t:'me', prof:{key, name, lvl, ttl, xp, cur, next, elo, cos, own:[cosmetic ids], ach:[ids], tut, m}}`.
  `prof` is `null` for an empty name. `cur` and `next` are the XP bounds of the current level, used by the XP bar.
- The `lobby` message `players[i]` adds `lv`, `ttl`, `cos` (banner, crown and piece set, for the slot preview),
  `fac_ok` (bool: a faction is chosen; the faction itself is never shown) and `busy` (true while in a solo session).
- `{t:'stats_q', who: key | null}` gets back
  `{t:'stats', prof:{full profile minus h2h of others}, hist:[≤50 summaries involving who], hof:[top 10], h2h:{...}}`.
  `null` means self.
  - `hof` (Síň slávy): profiles with ≥ 5 souboj matches, sorted by Elo, as `[name, lvl, ttl, elo, m, w]`.
  - The stats are in the clear: on a LAN anyone may view anyone.
- The `end` message adds `ser`, `rec_new`, and per receiving client
  `me:{xp_parts, xp, lvl, cur, next, lvlup, new_ach, new_cos, elo}`. It also adds `lv: [a, b]`.

### 1.7 Statistiky screen (lobby, right folio, tab "Statistiky")
1. Header: name, level badge "Úr. 7 · Pán hradu", XP bar "1234 / 1350 XP", Elo "Elo 1032".
2. Four tiles: "Zápasy", "Výhry" (%), "Nejlepší série", "Průměrná délka".
3. Table "Podle režimu":
   - rows Souboj · Král, Souboj · Stratég, Výcvik · each AI level, Přežití (nejdéle), Puzzle (vyřešeno n/N)
   - columns Zápasy, V, P, R, Úspěšnost
4. Table "Podle frakce": 3 rows (Zápasy, Výhry, Úspěšnost). A bar shows the rate and the number is always printed.
5. "Rekordy": 8 rows (Nejrychlejší výhra, Nejvíc zabití, Nejvíc beden, Nejvíc odrazů, Nejdéle držená Relikvie,
   Nejrychlejší Doba III, Nejvíc škody, Nejdelší Přežití). Each row shows the value and the date. Clicking it opens that match.
6. "Proti soupeřům": opponent name with V–P–R, top 8 by matches.
7. "Historie": the last 50 matches, one per row. A row shows date, type and mode icon, map, my faction vs theirs,
   opponent, result chip (Výhra/Porážka/Remíza, as text, not only colour) and length.
   Clicking a row expands its numbers. If it has `ser`, the expanded row shows the same 3-tab graph as the end screen.
8. "Síň slávy (tento server)": top 10.

- Viewing someone else: clicking an opponent's name in a lobby slot opens their profile read-only. "Zpět na můj profil" returns.
- Render with plain DOM and the existing folio styles. Text is at least 14 px. Under 1100 px width the tab takes the full column and scrolls.

## 2. Achievements (`meta.ACH`, evaluated server-side after each recorded match)

`ACH = [(id, name, desc, xp, test)]`. `test(prof, mrec, side_stats)` reads the updated `tot` and the match record.
Cumulative ones expose `prog(prof) -> [n, goal]` for the progress bar in the Úspěchy tab.

| id | name | condition | XP | unlocks |
|---|---|---|---|---|
| `korunovace` | Korunovace | first win: souboj, Přežití 1v1, or Výcvik aiIndex ≥ 1 | 100 | – |
| `ucednik` | Učedník | finish the Výuka | 50 | `lebka` |
| `sach_mat` | Šach a mat | win with `end == 'mat'` | 150 | `vrany` |
| `zrcadlo` | Zrcadlo | `parry ≥ 10` in one match | 150 | `trnova` |
| `hrobnik` | Hrobník | `tot.zk ≥ 1000` | 200 | `havran` |
| `lovec_alf` | Lovec Alf | `tot.alfa ≥ 5` | 150 | – |
| `relikvie` | Strážce relikvie | `relic_s ≥ 240` in one match | 150 | `klice` |
| `sberatel` | Sběratel | `crates ≥ 6` in one match | 100 | – |
| `veterani` | Ostřílení | `vet_max ≥ 3` | 150 | `litinove` |
| `noc` | Přežil jsem noc | win with `end == 'night'` | 100 | `nahrobni` |
| `nedotceny` | Nedotčený trůn | win a souboj with throne ≥ 90 % | 200 | `svatozar` |
| `blesk` | Blesková válka | win a souboj in under 360 s | 200 | – |
| `kralovrah` | Královrah | `kk ≥ 3` in one match | 150 | – |
| `tri_cesty` | Tři cesty | a win with every faction (souboj, or Výcvik at the top AI level) | 300 | – |
| `mistr_vycviku` | Mistr výcviku | beat the top AI level | 200 | – |
| `nezlomny` | Nezlomný | Přežití: last 720 s | 200 | – |
| `velmistr` | Velmistr | every puzzle solved | 300 | – |

- Disconnect wins do not count for win-based achievements.
- The end screen shows each new achievement as a parchment seal card, at most 3, plus "+N dalších".
- Úspěchy tab: a grid of cards, each with icon, name, condition, reward, unlock date or progress bar.
  Locked cards show a padlock and the word "Zamčeno".

## 3. Cosmetics

### 3.1 Rules
- Purely visual. Server-validated: a locked or unknown id falls back to the slot default.
- Chosen in the lobby with `{t:'cos', v:{fig,ban,kor,dlaz,zab,vit}}`. Stored in `prof.cos`.
  Sent to both clients in `start` as `cos: [a, b]`, so the opponent sees them.
- Readability is locked. Cosmetics never change:
  - side material (bone vs ebony), team enamel colour or emblem field shape (shield vs roundel)
  - silhouette size (at most +4 % height), hitbox or danger cues
  
  A cosmetic only changes ornaments, the emblem charge, the crown shape, stone texture and short effects.
- Players without a profile, and the AI, use the defaults.

### 3.2 Catalog (`meta.COSM`, also sent in `defs.cosm`)

| slot | id | name | unlock |
|---|---|---|---|
| fig (Figury) | `krypta` | Krypta | default |
| | `goticke` | Gotické (spire finial and lancet notches on the base disc) | level 3 |
| | `litinove` | Litinové (rivet ring and hammered rim on the disc) | Ostřílení |
| ban (Znak praporu: charge on the throne banner and on the emblem in UI and lobby) | `rod` | Rodový znak (crescent / flame) | default |
| | `lebka` | Lebka | Učedník |
| | `havran` | Havran | Hrobník |
| | `klice` | Zkřížené klíče | Strážce relikvie |
| kor (Koruna Krále, also the lobby crown logo) | `zlata` | Zlatá | default |
| | `trnova` | Trnová | Zrcadlo |
| | `kostena` | Kostěná | level 10 |
| dlaz (Dlažba of the own half; Mist columns stay neutral) | `piskovec` | Pískovec | default |
| | `mramor` | Mramor (veins) | level 6 |
| | `nahrobni` | Náhrobní desky (slab seams, faint inscription lines) | Přežil jsem noc |
| zab (Efekt zabití: enemy unit, building or King killed by this side; zombies excluded) | `jiskry` | Jiskry | default (current) |
| | `duse` | Odcházející duše (one wisp rises 0.8 cell, 700 ms) | level 8 |
| | `vrany` | Vrány (3 birds fly outward, 900 ms) | Šach a mat |
| vit (Efekt vítězství: the winner's throne during the 6 s finale) | `zlate` | Zlaté jiskry | default |
| | `zvony` | Zvony (3 swinging bells, 3× `bready` peal) | level 15 |
| | `svatozar` | Svatozář (halo ring and 8 slow rays) | Nedotčený trůn |

That is 13 unlockables and 6 defaults.

### 3.3 Rendering
- Global `COS = [{...}, {...}]`, set in `startGame(m)` from `m.cos`. All variants are painted at sprite-cache time, so they
  cost nothing per frame.
- Sprite keys gain the variant:
  - `sprUnit`: `U|kind|side|vet|face|variant|COS[side].fig`
  - `sprKing`: `K|side|face|COS[side].kor`
  - `throneCol`: key `+|COS[side].ban`
  - `boardCanvas`: key `+|COS[0].dlaz|COS[1].dlaz`
- Paint hooks in `paint.js`:
  - `FIG_DECOR[id](g, s, kind)` runs after `paintPiece`.
  - `CROWN[id](g, x, y, k)` replaces the body of `paintCrown`.
  - `CHARGE[id](g, x, y, r, s)` draws the banner and emblem charge.
  - `STONE[id](g, X, Y, CS, light, x, y)` runs after the base tile fill.
- Lobby SVG emblems get a `CHARGE_SVG[id]` path.
- Stone variants keep the mean relative luminance within ±8 % of `stoneL`/`stoneD`, so the fog-of-war contrast holds.
  A test renders one tile per variant and checks this.
- Kill and victory effects live in `render.js`:
  - `KILLFX[id](x, y, side)` is called from `onDeath` when `killer` is a side and the victim is not a zombie.
    It uses at most 6 particles. It is skipped (default sparks only) when `PART` is over 500, at quality level 0, or in Klidné efekty.
  - `WINFX[id](side, now)` is called from `runFinale` for the winner.
- Faction kits (other doc) set the base piece silhouettes. `fig` ornaments must apply to any kit: they are anchored to the
  disc and the top point returned by the kit painter.
- Vzhled tab (lobby):
  - 6 rows, one per slot. Each tile is a 72×72 canvas preview painted with the real sprite function.
  - Locked tiles are dimmed, with a padlock and the rule ("Úroveň 6" / "Úspěch: Hrobník").
  - Preview pane: King, 3 pieces and the banner. A toggle "Strana A / B" previews both materials.
  - With no profile, the tab shows only the defaults and the "Zadej si jméno" hint.

## 4. Lobby, sessions, UX

### 4.1 Layout (`index.html` `#lobby`)
- Left folio "Zápas", top to bottom:
  1. Name input with level badge.
  2. **Typ hry** segment: Souboj · Přežití · Výcvik · Puzzle. Each segment has an icon and a one-line description under the segment bar.
  3. **Ovládání**: Král / Stratég, as the existing cards in a compact 2-column form. Hidden for Puzzle, where each puzzle fixes it.
  4. **Mapa**: a select with a 120×68 procedural thumbnail drawn from `ter`, plus "Náhodná". Puzzle replaces this with a puzzle
     list showing stars and best time.
  5. **Obtížnost** (Výcvik only): a 3-button segment from `defs.ai`.
  6. **Frakce**: 3 cards with name, one line and 2 strength icons. The opponent sees only "✔ frakce vybrána".
  7. Slots, shown for Souboj and Přežití: emblem with the player's charge, name, "Úr. 7", ready state. Clicking a name opens their stats.
  8. Ready button.
     - Souboj and Přežití: "Jsem připraven".
     - Výcvik and Puzzle: "Začít". Přežití has an extra button "Hrát sám".
  9. Links "Jak se hraje" and "Výuka (8 min)", the tips checkbox, URLs, and the tip of the day.
- Right folio tabs: **Balíček** (existing) · **Vzhled** · **Statistiky** · **Úspěchy**.
  The last tab is remembered in localStorage `hmk_tab`.
- Ownership of the settings:
  - Shared room settings (any seated player may change them; a change unreadies both, as `mode` does today):
    `cfg = {type ∈ souboj|preziti, mode, map}`.
  - Per player: deck, faction, cosmetics.
  - Solo settings live only in the client and are sent with `solo`.
- `{t:'cfg', type, mode, map}` replaces `{t:'mode'}`. `ready` adds `fac`.
- Map "Náhodná" is resolved by the server at `start`, and the map name is announced in the VS splash.

### 4.2 Sessions (server)
- `class Session`: holds `game`, `clients[2]` (None for the AI side), `ai`, `kind ∈ room|solo` and `task`.
  `run()` and `finish()` move from `Lobby` into it unchanged, except that they push snapshots only to their own clients.
- `Lobby.room` is the 2 seats plus the queue, as today. `Lobby.room.session` is the PvP or 1v1 Přežití match.
  `Lobby.solos` is a set of solo sessions.
- `{t:'solo', type, mode, map, ai, fac, deck, puzzle}`:
  - Allowed for any client not currently playing, including queued players: "Zatímco čekáš, zahraj si Výcvik."
  - Starting a solo session releases the player's room seat: the queue head is seated, or the seat is left free.
  - The human is always side 0.
  - `MAX_SOLO = 2` (3 games in total). Measure `Game.step` p95 with 3 games. If it is above 10 ms, set `MAX_SOLO = 1`.
  - When the cap is reached, reply `lerr` "Server už hostí 2 cvičné hry, zkus to za chvíli."
- `{t:'quit'}` leaves a solo session:
  - Výcvik: counts as a loss when ≥ 60 s.
  - Puzzle: `end = 'quit'`, not recorded.
  
  The lobby then re-seats the player (free seat) or queues them.
- In-game messages route through `c.session`. `Lobby.handle` stays the single entry point.

### 4.3 Match start and end
- **VS splash**: a 2.2 s parchment band shown over the board as it renders.
  - Both emblems with their charges, names, "Úr. N · title", faction names (revealed now), the mode, and the map name.
  - Sound: `banner2`. Input is accepted from t=0 (server time has already started), and any key dismisses the splash.
  - Skipped when Klidné efekty is on, in which case a toast shows the same text.
- **End overlay**, `#endOv` widened to `wide`:
  - Left: the existing table plus new rows "Ztráty", "Odrazy" (Král only), "Relikvie (s)", "Veteráni".
  - Right: the graph card.
    - Tabs "Trůn · Příjem · Armáda". The chart is 520×150 CSS px, canvas at DPR.
    - x axis: time with ticks every 2:00. y axis: 0 to nice max, 3 gridlines.
    - Lines are 2 px. A is solid `--a`, B is dashed `[6,4]` `--b`, with names at the line ends.
    - Bands: eclipses as dark bands labelled "Zatmění", Poslední noc as a red band labelled "Noc".
    - Hover or tap shows a crosshair and the tooltip "5:35 · Jarda 1820 · Petr 940".
    - The data is from the server, so the graph works for both players.
    - Under 1100 px width the graph goes below the table and the card scrolls.
  - Below: an XP bar animating `xp_parts` one by one (`tick` sound per part), "Nová úroveň!" seal on level up,
    achievement seals, and "Odemčeno: Trnová koruna" with a tile preview plus a button "Nastavit" (opens Vzhled with it selected).
  - Buttons: "Zpět do lobby", "Odveta" (rooms: sets ready on with the same deck and faction), and "Znovu" (solo: same settings).

## 5. Onboarding and tutorial (`type: 'vyuka'`)

- **First visit**: no `hmk_seen` in localStorage and `prof.m == 0`. Show the modal "Vítej v Hře mrtvých králů" with three buttons:
  "Výuka (asi 8 min)" (primary), "Výcvik proti AI", "Rovnou hrát". Set `hmk_seen = 1` after any choice.
  The Výuka link stays in the lobby.
- **Rules** (server `Tutorial` director in `Game`, active when `type == 'vyuka'`):
  - Solo session, AI level index 0 with `ai.hold = True`.
  - No eclipses, Relikvie, random crates, Mist advance or Poslední noc (`length = inf`). Enemy throne 1200 HP.
  - Fixed deck `kulomet, hlaska, pesak, jezdec, plamen, sniper, obrnenec, dron` (so Kulomet is key 3, Hláska 4, Pěšák 5).
    Fixed map: the first map in `defs.maps`. The mode is the one selected.
- **Steps**: `TUT_STEPS = [{id, text, hint:[x,y]|None, ui, done}]`.
  - `done` is a predicate name evaluated every tick.
  - A step whose `done` is already true is skipped.
  - If a step is open for 20 s, the hint pulse turns on.
  - Each step can grant something on entry (`give`).

| # | id | text (Czech, shown on the card) | done when | on entry |
|---|---|---|---|---|
| 1 | `pohyb` / Stratég `rozkazy` | Pohni Králem klávesami W A S D. / Tvé rozkazy jsou na liště: Q W E R G. | King ≥ 2 cells from spawn / 6 s elapsed | – |
| 2 | `gen` | Postav Generátor: klávesa 1, pak klikni na zvýrazněné pole. | own gen ≥ 1 | hint at local (1,4) |
| 3 | `vez` | Postav Kulomet blízko Mlhy (klávesa 3). | own attack tower ≥ 1 | hint at local (4,4) |
| 4 | `vlna` | Z Mlhy jdou zombie! Věž a Král je zastaví. | the 3 spawned chodci are dead | spawn 3 `chodec` at the target side |
| 5 | `blok` / `odstrel` | Podrž mezerník: blok sníží poškození. / Zmáčkni W a klikni na zombie. | block used / `odstrel` cast | Stratég: spawn 1 `obr` |
| 6 | `bedna` | Do Mlhy spadla bedna. Dojdi k ní a počkej 3 s. | `stats.crates ≥ 1` | `drop_crate` at local (6,4), rarity 2, land 2 s |
| 7 | `hlaska` | Postav Hlásku (klávesa 4). Uvidíš soupeře. | own hlaska ≥ 1 and an enemy building seen | – |
| 8 | `upg` | Klikni na Kulomet a zmáčkni U. | any own building at lvl ≥ 2 | +40 🔩 |
| 9 | `vyzkum` | Za Vzorky se vyzkoumávají technologie. Zmáčkni V a jednu vyber. | techs ≥ 1 | +2 🧪 |
| 10 | `jednotka` | Vyšli Pěšáka (klávesa 5). Jde sám k soupeři. | own units deployed ≥ 1 | – |
| 11 | `utok` | Znič soupeřův trůn! | win | `ai.release()`; AI sends 2 Pěšáci once |

- Snapshot field `tu: [step, total, hx, hy, ui]`.
  - `hx` and `hy` are -1 when there is no cell hint.
  - `ui` is `slot:N | key:V | cmd:odstrel | ''`.
- Client UI:
  - `#tutCard` is a parchment card 380 px wide, centred under the top bar and outside the board centre.
    It shows "Krok 3/11", the text with `<kbd>` keys, and the buttons "Přeskočit krok" (`{t:'tut', skip:1}`) and "Ukončit výuku".
  - The hint cell gets pulsing `cornerMarks` in gilt. A hinted bar button gets the `.tut` pulse class.
  - Steps advance with the `select` sound and a ✔ animation.
- Completion: `end = 'throne'` win, `prof.tut = 1`, achievement Učedník, a toast in the end overlay
  "Teď zkus Výcvik proti AI, nebo hru s kamarádem."
- The tips checklist (`STEPS`) stays for normal matches. It is hidden in Výuka.

## 6. Settings and accessibility

- **The speaker popover stays**, for quick volume and mute. It gets the link "Další nastavení…", which opens `#setOv`.
- `#setOv` is a modal from the lobby (gear button next to the speaker) and from in-game. Game keys are blocked while it is open,
  except Esc. It has 4 tabs:
  - **Zvuk**: Efekty, Hudba, Ztlumit vše, and **Test zvuku**: buttons "Rozhraní" (`click, select, ready`), "Boj" (`gun, snipe, boom`),
    "Výstrahy" (`alarm, eclWarn, banner1`), "Vlevo / Vpravo" (`ping` at x=0, then x=W−1 after 0.6 s) and "Hudba 8 s".
    - The status line reads `AudioContext.state`: "Zvuk běží." or "Prohlížeč zvuk zablokoval, klikni kamkoli do stránky."
    - New in `audio.js`: `audioTest(group)` and `musPreview(sec)`. Sounds play at the current volumes.
  - **Obraz**:
    - Kvalita (Automaticky / Vysoká / Střední / Nízká, see section 7)
    - Ukazovat FPS (a small corner counter with the quality level)
    - Otřesy, Záblesky, Čísla poškození, Klidné efekty (moved here)
  - **Přístupnost**:
    - Velikost rozhraní 100 / 115 / 130 %: CSS `zoom` on `.lwrap, #top, #side, #bar, .ov .card, #optPop, #setOv .card`.
      Never on `#board`, because pointer maths stays unscaled.
    - Silné obrysy figur: the sprite keyline width ×2, sprite cache cleared.
    - Kontrastnější mlha války: fog fill alpha 0.80 → 0.90, the gilt edge 1.2 → 2 px.
    - Blok mezerníkem: Držet / Přepnout. Toggle mode flips `inp.b` on keydown, and the server is unchanged.
    - Rady pro nové hráče (mirrors the lobby checkbox).
    - Zopakovat výuku.
  - **Ovládání**: a read-only key table for Král and for Stratég, generated from one `KEYMAP` array that the help overlay also uses.
    Key labels are physical keys on Czech QWERTZ: `ev.code` everywhere, and no Y/Z keys are used. There is no rebinding in 1.0.
- `hmk_opt` gets these new keys: `q` ('auto'|2|1|0), `fps` (bool), `ui` (1|1.15|1.3), `outl` (bool), `fogc` (bool), `blk` ('hold'|'toggle').
  `loadOpt()` validates each key, as it does today.
- Lobby keyboard use:
  - All controls are tabbable with a `:focus-visible` gilt ring.
  - Segments are `role="radiogroup"` and work with the arrow keys.
  - The click-blur behaviour stays for in-game buttons only.
- All new text is at least 14 px, never only colour: result chips carry text, graphs use dash patterns, and locked items show a padlock and text.
- `aria-live="polite"` is set on the tutorial card and on the XP and achievement area.

## 7. Rendering performance (canvas overdraw 7.7× → ≤ 3×)

Measured in 0.5 at `?demo=120`, canvas 1616×913 (1.475 Mpx):
- 9.48 Mpx of drawImage, 1.92 Mpx of fillRect and 0.49 Mpx of `lighter` per frame
- 34 ms per frame on software canvas

The four full-canvas layers are board, scars, base vignette and red vignette. The target is ≤ 4.5 Mpx per frame typical, so
software canvas can hold 60 fps at 1080p.

1. **One static layer.** `LAYER` is `BOARD` plus decals plus the base vignette.
   - The vignette is baked at fixed alpha 0.58 and the pulse is dropped. It is now under the units, which also improves legibility at the edges.
   - The Mist tint (`rgba(185,203,191,0.06)`, or the night red) is baked into `BOARD`. It is already keyed by stage and night.
   - Per frame there is **one opaque blit** with an identity transform: `ctx.setTransform(1,0,0,1,ox,oy); ctx.drawImage(LAYER,0,0)`.
     The shake offsets `ox` and `oy` are rounded to whole device pixels, which keeps the copy fast path.
     During the finale zoom, the scaled path is used as today.
   - The redundant opaque `fillRect` stays skipped and is only drawn when shaking.
2. **Decals without full rebuilds.**
   - Decal alpha is quantized to 4 steps (1, .75, .5, .25 of the current linear curve).
   - `addDecal` paints straight into `LAYER`.
   - The 1 s sweep repaints only decals whose step changed or that expired. For each such decal it restores its bounding rect from
     `BASE` (BOARD with vignette, kept as a second cached canvas) with `drawImage(BASE, r, r)`, then repaints the decals that intersect that rect.
   - A full rebuild happens only when `BOARD_KEY` changes.
3. **Fog in one pass.** `fogPat()` pre-blends `rgba(9,7,6,0.80)` with the hatch lines into one 8×8 pattern with per-pixel alpha.
   `ctx.fill(fog.cells)` is then called once, not twice. The edge strokes stay.
4. **One shade blit.** Darkness (eclipse and night), the dim while the King is dead (0.2) and the outage dim (0.18) are combined into
   the existing quarter-resolution `DARK` canvas. It is blitted once per frame, only when one of them is active.
5. **Vignettes only where needed.** The red (low throne HP) and dark (eclipse warning) vignettes become 4 edge strips of
   thickness `0.2·min(w,h)`, cached per size. That is 0.72 Mpx, not 1.475. They are drawn only when active.
6. **Render scale (DPR handling).** `DPR` becomes the render scale `RS`. The canvas CSS size is unchanged and the browser upscales.
   - Quality levels:
     - Q2 Vysoká: `RS = min(devicePixelRatio, 2, sqrt(2.2e6 / (cssW·cssH)))`. This caps the canvas at 2.2 Mpx, so DPR 2 on a
       1080p-CSS screen renders at RS ≈ 1.22, not 2.
     - Q1 Střední: `RS = min(devicePixelRatio, 1)`.
     - Q0 Nízká: `RS = 0.75`, `PMAX` 700 → 300, Mist wisps ×0.5, no screen flash, no particle `lighter` glows.
   - Automaticky:
     - Start a match at the level saved in `hmk_qa` (default Q2).
     - Every 2 s, while visible and outside the finale, if the median rAF interval of the last 120 frames is over 18 ms,
       step down one level and toast "Kvalita obrazu snížena kvůli plynulosti (Nastavení › Obraz)."
     - Save the level and never step up during a match. Every 5th match, start one level higher to re-probe.
   - Every level change calls `resize()` (it already clears `SPR`, `BOARD_KEY`, `VIG` and `THR`).
7. **Instrumentation**: `?perf` (works with `?demo`) wraps `drawImage`, `fillRect`, `fill` and `stroke`.
   The demo HUD then shows dest Mpx per frame, overdraw ×, the draw JS ms and the RS.
   - Acceptance at 1920×1080, DPR 1, Q2:
     - `?demo=40` ≤ 3.0×; `?demo=120` ≤ 4.5×
     - software canvas (Chrome `--disable-gpu`) `?demo=60` p50 frame ≤ 16.7 ms with Automaticky
   - No visual change beyond the vignette moving under the units (judge with screenshots before and after).

## 8. Release 1.0

- Version strings must all equal `1.0`:
  - `VERSION` in `server.py`
  - `CLIENT_VER` in `js/base.js`
  - `#ver` in `index.html`
  - the README heading "Verze 1.0"
  - the `## Verze 1.0` section in `DESIGN.md`
  - `meta.SCHEMA = 1`
  
  The existing mismatch message covers an old server process.
- `dev/release.py` (stdlib):
  1. **Check** all version strings. Run `py_compile` on every `.py`, and `node --check` on `js/*.js` if node exists.
     Scan the included files for `ghp_|github_pat_|AKIA|-----BEGIN|password\s*=` and fail on a hit.
  2. **Build** `dist/HRA-MRTVYCH-KRALU.zip` with the top folder `HRA-MRTVYCH-KRALU/`, from an allowlist:
     `server.py, meta.py` (and any new server modules), `index.html, style.css, js/*.js, README.md, DESIGN.md, Spustit server.bat`.
     The allowlist keeps out `.exe`, `stats.json*`, `dev/`, `dist/` and `__pycache__`.
  3. **Print** the file count, the size and the SHA-256.
- Publishing is done by the user or the orchestrator after the user agrees:
  `gh release create hmk-v1.0 dist/HRA-MRTVYCH-KRALU.zip --repo God-Apex/Games --title "Hra mrtvých králů 1.0" --notes-file dev/release-notes.md`.
  The tag follows the `zahon-v1.1` naming. The notes are Czech, 5–8 lines, ending "Rozbal a spusť Spustit server.bat."
- README:
  - Update "Co je nového v 1.0".
  - Add a "Statistiky" note: they are saved in `stats.json` on the PC running the server. Delete the file to reset them.
  - In `Games/README.md` the row badge becomes **v1.0** and the description mentions frakce, Výcvik, Přežití, Puzzle, statistiky and kosmetika.
- The `dev/` design docs contain no secrets, so committing them is fine. They are excluded from the zip.
- `dev/stats_report.py`: reads a `stats.json` and prints faction × mode win rates and the average length.
  The balance work uses it on real LAN data.

## 9. Tests

`dev/test_meta.py` (unittest, stdlib) covers:
- **Store**:
  - a round trip
  - a crash between the tmp write and replace (simulated): the original stays readable
  - a corrupt main file falls back to `.bak`; with both corrupt, the file is renamed and a fresh one starts
  - `PermissionError` retry
  - `normalize` on garbage types
- **Rules**:
  - the `need(L)` table values from section 1.5
  - the XP parts for 6 fixture matches (souboj win/loss/draw, Výcvik at all 3 levels, disconnect, under 60 s)
  - Elo symmetry (the sum is conserved without the K asymmetry) and the K switch at 10
  - every achievement against fixtures, positive and negative
  - a locked cosmetic falls back to the default
- **History and keys**: the history cap at 50 and `ser` cap at 10; name key normalization; refusal of duplicate names.

Integration (existing `integ` bots against `server.py --stats <tmp>`):
- Two room matches and one solo Výcvik: 3 matches recorded, profiles updated, and `end.ser.th[0]` has `len ≈ floor(t/5)+2`.
- `me` arrives after `hello`.
- `stats_q` returns the history.
- While a room match runs, a queued client can play a solo session, and both get snapshots only from their own session.
- Lobby fuzz extended with `cfg/solo/quit/cos/stats_q/tut` and malformed values.

Browser (port 8097; close the tabs and stop the server afterwards):
- the lobby at 1366×768 and 1920×1080, no horizontal scroll
- the Vzhled previews render, and the VS splash shows the opponent's banner
- end graphs with hover; the tutorial run through all 11 steps in both modes
- every sound test button; quality steps
- 0 console errors

## 10. Work packages (for parallel agents)

| WP | content | depends on | size |
|---|---|---|---|
| M1 | `meta.py`: Store, schema, normalize, XP/levels/titles, Elo, ACH, COSM, record() + `dev/test_meta.py` | – | M |
| M2 | server: Side.stats counters, `over.end`, `sample()`, Session/solos refactor, protocol (`me, cfg, solo, quit, cos, stats_q, lerr`), `end` additions, `--stats/--no-stats` | M1 | L |
| M3 | lobby UI: typ hry / mapa / obtížnost / frakce controls, Session messages, right-folio tabs, Statistiky + Úspěchy tabs (`js/meta.js`) | M2 protocol | L |
| M4 | cosmetics paint hooks (`paint.js`, `render.js` KILLFX/WINFX) + Vzhled tab + luminance test | M1 catalog | M |
| M5 | end overlay: graphs, XP bar, seals, Odveta/Znovu; VS splash | M2 | M |
| M6 | tutorial director (server) + `#tutCard` client | M2, AI `hold/release` | M |
| M7 | `#setOv` settings, sound test (`audioTest`, `musPreview`), accessibility options, KEYMAP | – | M |
| M8 | rendering performance items 1–7 + `?perf` | – (touches `render.js` only) | M |
| M9 | release.py, .gitignore, README/DESIGN 1.0 texts, stats_report.py | all | S |

M1, M7 and M8 can start at once. M8 and M4 both edit `render.js`/`paint.js` caches, so M4 rebases on M8.
