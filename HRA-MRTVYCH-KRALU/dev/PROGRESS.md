# Hra mrtvých králů 1.0 – stav

## M1 – Infrastruktura: HOTOVO (gate PASS, 2026-10-16)
- M1-A: rozdělení na balík `hmk/` (§3.1), všechny švy §3.2, Rules háky §3.3, `make_rules`, stuby modulů.
- M1-B: testovací sada `dev/tests/` (run_fast, golden, fuzz, replay, perf, bal/*).
- Integrace: `hmk/net.py lan_ips` iteruje `sorted(ips)`; z ALLOW v `test_hashorder.py` odebráno `hmk/net.py`.
  Korektura textů: popis Ruin a typu Přežití přeformulován.

### Gate
| Kritérium | Výsledek |
|---|---|
| golden.py 10 seedů × {kral, strateg}, 600 s | 20/20 identické |
| run_fast.py (test_features, test_py38, hashorder, …) | 35 testů GREEN, 115 s |
| fuzz.py (4 seedy × 2 režimy × 400 s, ~200k akcí + lobby fuzz) | 0 chyb |
| perf.py --compare | 0.408 vs 0.415 ms, poměr 0.98 (OK); B7 OK |
| Prohlížeč, port 8097, 2 taby | zápas běžel, jednotky bojovaly, konec hry zobrazen, 0 chyb v konzoli i v logu serveru |

### Otevřené body
- perf.py je citlivý na zátěž: první běh souběžně s prohlížečem dal 1.37 (FAIL), opakovaný běh v klidu 0.98. Měřit bez paralelní zátěže.
- `Game(seed=None, rng=X)` nechává `g.seed = None` (záměrně kvůli golden); Session musí vždy předat seed.
- M2-A: přidat `'squad'` do `actions.ACT_TYPES`; ponechat cache `g.may_enter`; bfs/build kontroly přepnout na WALK/BUILD.
- M2-B: aktualizovat `lobby_fuzz()` a `_running_game()` ve `dev/tests/fuzz.py` po příchodu Session API.
- M3-G: v `bal/harness.py` zachovat `setc()`, `TICK_HOOKS`, `cost_of()`.
- Konzole Git Bash zobrazuje češtinu jako mojibake (jen kosmetika).

## M2 – Platforma: HOTOVO (gate PASS, 2026-10-19)
| Balík | Model | Výsledek |
|---|---|---|
| M2-A mapy, terén, počítadla, squad | sonnet | 5 map v `data/maps.json`, WALK/BUILD, `~` a `^`, počítadla §3.6, Četa na Relikvii, `sq`, kód `mat`; test_maps/terrain/counters/squad |
| M2-B sessions + lobby protokol | opus | `hmk/session.py`, `hmk/lobby.py`, `net.py`; test_lobby 8/8, lobby fuzz |
| M2-C AI jádro | opus | `hmk/ai/*` (Lehká/Střední/Těžká), `bal/novice.py`, `ai_ladder.py`, test_ai_fog, test_ai_determinism |
| M2-D klient: lobby, mapy, bus | sonnet | nové lobby, `maps.js`, bus, `css/lobby.css`, tlačítko a klávesa H, tipy k Relikvii |
| M2-E výkon vykreslování | opus | `js/render.js`: LAYER, fogPat, shade, okrajové vinětace, RS a kvalita Q0–Q2, `?perf` |
| M2-F meta jádro | sonnet | `hmk/meta.py` + test_meta (48 testů) |

Integrace (gate): `modes.py` Alfa buňky `in WALK` (na Mostu se Alfa teď objeví, ověřeno); `hmk/__init__.py` VERSION = '0.9'
(klient ji vyžaduje); `lobby.send_me` předává `name=c.name`; popis mapy Most („přejít ji lze“).
Hlášení M2-D „po quit jsou statistiky 0“ se nepotvrdilo (server je počítá správně, v prohlížeči po quit: Jednotek 1, Staveb 1).

### Gate
| Kritérium | Výsledek |
|---|---|
| run_fast (test_maps, test_lobby, test_meta, test_squad, AI testy, …) | 192 testů GREEN, 31 s |
| golden.py 10 seedů × 2 režimy, 600 s | 20/20 identické |
| fuzz.py (4 seedy × 2 režimy × 400 s + lobby fuzz se všemi §4.1 typy a nesmysly) | 204 798 akcí, 0 chyb |
| perf.py --compare --b7 (bez zátěže) | poměr 1.035 OK, p99 0.58 ms, B7 OK |
| ai_ladder --gate (ruiny+predmesti, 10 seedů × 2 režimy × 2 strany) | Těžká>Střední 83.8 %, Střední>Lehká 98.8 %, Lehká vs Novice 51.2 %; Těžká think průměr 0.26 ms; fog lint a determinismus OK |
| Prohlížeč 8097 | lobby 1366×768 i 1920×1080 bez vodorovného scrollu; 5 různých náhledů map; celý Výcvik (Stratég) vs Lehká na Mostu dohrán do konce (6 min); quit ukazuje správné statistiky; 0 chyb v konzoli i v logu serveru |
| `?perf` 1920×1080, DPR 1, Q2 | demo=40: medián přes 32s cyklus 2.91× (mimo zatmění 2.3–3.0×); demo=120: průměr 3.75×, max 4.17× |
| Snímky desky před/po M2-E | stejný vzhled (porovnáno canvas PNG z `render_before.js` a nového `render.js`) |

### Otevřené body
- Výkon: během zatmění v demu (20–30 s cyklu) má demo=40 3.5–4.4× (plošné DARK 0.9× + mlžné chuchvalce 0.33× + vinětace). Průměr cyklu 3.14×. Kandidát na M5-C / M4-B (např. vynechat chuchvalce pod tmou).
- Software canvas (`--disable-gpu`) p50 ≤ 16.7 ms nezměřeno (patří k §7.4, ověřit v M5).
- Rozhodnutí potvrzená na gate: NoviceBot podle `novice.py` (výzkum + utrácení přebytku, viz docstring) přijat; DIFF hodnoty z M2-C platí, M5-B je může doladit.
- `meta.xp_gain`: vítěz po `quit` dostává jen polovinu bonusu (jako po `disc`); ponecháno, případně změnit v M3-F.
- M3-C: `pick_fac` vrací jen 'bez', dokud není FACTION_PLAN (SPEC 2.2).
- M2-D: Přežití při 1366×768 má tlačítka pod ohybem (svislý scroll je povolený).
- AI: Králové se neléčí; nejhorší jednotlivý think 5–31 ms (průměr hluboko pod 2 ms).
- Records ve stats mají navíc datum (záměr M2-F).

### Jak pokračovat
- Spustit workflow „hmk-milestone“ pro M3 s balíky ze SPEC §6 (M3-A opus, M3-B1 sonnet, M3-B2 opus, M3-C sonnet, M3-D opus, M3-E1 sonnet, M3-E2 sonnet, M3-F sonnet, M3-G sonnet); pak M4 → M5.
- Prohlížečové testy: konfigurace `mrtvi-krale` (8097) a `hmk-p1`–`hmk-p5` (8101–8105) v `C:\!Data\!AI\!Code\.claude\launch.json`; po testu zavřít taby a zastavit server. Měření výkonu jen se zobrazeným panelem prohlížeče (skrytý panel nespouští rAF).
- Zmrazená 0.5 je v `dev/tests/golden/server_05.py`; kompletní kopie hratelné 0.5 je v `%TEMP%\hmk\release05_snapshot`.
- Složka teď obsahuje hratelnou verzi 0.9 (mapy, Výcvik proti AI, nové lobby). Frakce, Přežití, Puzzle a Výuka přijdou v M3.
- Nic není commitnuté (repo Games je veřejné, commit jen na pokyn uživatele).

### Aktualizace 19. 10. 2026 08:40 (zastaveno uživatelem kvůli rezervě tokenů, pokračovat po resetu limitu)
- HOTOVO: M2-A (189 testů GREEN), M2-B (test_lobby 8/8, golden 20/20), M2-D (lobby v prohlížeči OK, 1366/1920 bez posuvníku),
  M2-E (overdraw demo=40 2,2×, demo=120 ~3,9×; gate porovná screenshoty se zálohou %TEMP%\hmk\render_before_M2E.js),
  M2-F (test_meta 48 OK, run_fast 192 GREEN).
- ZBÝVÁ M2-C: kalibrace obtížností AI (dev/tests/ai_ladder.py --gate). Poslední stav: Střední > Lehká 90 % (OK),
  Lehká vs novice ~51 % (OK), Těžká > Střední ~62 % (cíl ≥ 70 %; Král ~50 %, Stratég ~88 %) – běželo plné měření po úpravách Těžké.
- Požadavky pro gate M2: modes.py DuelRules Alfa `== '.'` → `in maps.WALK`; hmk/__init__.py VERSION (M2-D chce '0.9');
  statistiky po `quit` ukazují 0 (session.finish); lobby.send_me → meta.profile_view(store, c.key, name=c.name);
  ověřit 404 na css/lobby.css.
- Pokračování: workflow jen s balíkem M2-C (opus) + gate M2, pak M3 (balíky a modely v SPEC §6).

### 19. 10. 2026 11:15
- M2 gate PASS. Spuštěno M3 (workflow `C:\!Data\!AI\!Code\.claude\workflows\hmk-milestones.js`, args `{"milestones":[{"milestone":"M3","packages":[...]}]}` – balíky a modely viz SPEC §6). Při přerušení stačí spustit znovu se stejnými args; balíky navazují podle dev/progress/M3-*.md.

### 20. 10. 2026 07:30
- M3: hotovo A, B1, B2, C, D, E1, F. M3-E2 dobíhá samostatně (bez gate). M3-G (boti pro vyvážení frakcí) POZASTAVEN na přání uživatele – pokračovat později podle dev/progress/M3-G.md; pak gate M3.
- 20. 10. 2026: M3-E2 HOTOVO (run_fast 301 testů GREEN, Přežití/Výuka/puzzle/úvodní okno ověřeny v prohlížeči). Požadavky pro gate M3:
  M3-B2 přidat `hit:[b,b,b]` do `end.puzzle` (jinak u 2 hvězd „nejisté“); ui.js používá `S.throneMax` pro oba trůny
  (puzzle p01 ukazuje 500/3000); nadpis konce hry v ui.js říká „Porážka/Vítězství“ i u Přežití a puzzlí.
- 21. 10. 2026: M3-G hotovo, gate M3 viz níže.

## M3 – Obsah: HOTOVO (gate PASS s výhradou B1 sanity, 2026-10-21)
| Balík | Model | Výsledek |
|---|---|---|
| M3-A frakce server | opus | `factions.py`, `facmech.py`, §2.3 pravidla, test_factions 29 |
| M3-B1 Přežití + Výuka | sonnet | `SurvivalRules`, `TutorialRules`, test_survival 30, test_tutorial 22 |
| M3-B2 hádanky | opus | 10 hádanek, `eval_stars`, `puzzle_solutions.py`, test_puzzles |
| M3-C AI obsah | sonnet | `facplay.py`, FACTION_PLAN, profil Přežití, mapové váhy, `planner.cross/_fit` |
| M3-D kresba frakcí | opus | FAC_ART, emblémy, 9 spritů, fx H E M Z W, 6 zvuků |
| M3-E1 klient frakce | sonnet | výběr frakce, balíčky per frakce, HUD emblémy, ceny ze `start` |
| M3-E2 klient režimy | sonnet | mřížka hádanek, HUD Přežití/hádanek, `#tutCard`, `#pauseOv`, `#welcomeOv` |
| M3-F meta server | sonnet | Store, `me`, `stats_q`, `cos`, `end.me/ser/lv`, test_session_meta 17 |
| M3-G nástroje vyvážení | sonnet | `facbots.py`, `facrun.py` (matrix crack spam ablate perf b6 fair selftest) |

Integrace na gate (log `progress/M3-GATE.md`):
- `hmk/puzzle.py`: `star_hits()`, `end.puzzle.hit:[b,b,b]` (i při nevyřešení/odchodu).
- `hmk/game.py start_info`: `thmax` (maximum trůnu za stranu), `relic_at` (kdy se Relikvie probudí; `None` = režim bez Relikvie, hádanky 0).
- `js/ui.js`: `S.thMax` pro oba trůny (throneBar, oznámení, `render.js` trůn), nadpis konce hry podle typu
  (Hádanka vyřešena/nevyřešena, Výuka dokončena/ukončena, Konec přežití, Vydržel jsi déle / Soupeř vydržel déle),
  čip a zóna Relikvie skryté bez Relikvie (`S.noRelic`, per-game `S.relicFrom`).
- `hmk/modes.py _fmt_time` zaokrouhluje stejně jako klient (dřív 3:54 vs 3:55).
- `dev/tests/fuzz.py --content N`: všechny typy her × frakce, 10 hádanek, Výuka (přes `session.build_game`, start/snap/end JSON strict).
- `dev/tests/test_puzzles.py`: kontrola `hit`, `thmax`, `relic_at`.
- Korektura češtiny (254 řetězců M3): „Vítej ve Hře mrtvých králů“, „Jsem připraven“ v uvozovkách.

### Gate
| Kritérium | Výsledek |
|---|---|
| golden.py 10 seedů × 2 režimy (compat05) | 20/20 identické (2×, před i po opravách) |
| run_fast (test_factions 29, test_puzzles, test_survival, test_tutorial, test_session_meta, …) | 301 testů GREEN (3×) |
| fuzz: 4×2 duel 400 s + content 26 konfigurací × 3 seedy × 400 s + lobby 6 | 703 737 akcí, 0 chyb |
| puzzle_solutions (v test_puzzles) | všech 10 na 3 hvězdy, 2× stejné metriky; idle nikdy 3 hvězdy |
| facrun all --quick (M3-G, 1493 s) | A9 PASS (exo 94,5 %, ostatní ≥ 99 %), B5 B6 B7 PASS |
| facrun matrix --quick sanity 30–70 % | **FAIL**: bez–kult Stratég 90 %, bez–prez Král 75 % (n=20) → M5-A |
| ai_ladder --fac 10 seedů × 2 režimy × 2 strany (předměstí) | prez 65,0 / korp 60,0 / kult 47,5 % PASS; usage OK (exo 80 %, nekromant 90 %) |
| perf.py --compare --b7 | B7 OK (p99 0,75 ms, max 1,08 ms, snapshot max 4,0 KB, 83 entit). Poměr k 0.5: s pravidly 1.0 1,27 (jiné hry), se `HMK_COMPAT05=1` 1,039 OK |
| Prohlížeč 8097, 1366×768 | úvodní okno; Výuka Král i Stratég dokončena (kroky řízené zprávami protokolu, ne klávesnicí); p01 a p02 na 3 hvězdy přes mřížku hádanek, hvězdy ✔✔✔; Esc pauza zastaví čas, „Začít znovu“ funguje; sólo Přežití (Kult, Stratég) dohráno do konce; Souboj prez–korp (Král) a kult–bez (Stratég) ve 2 tabech: frakční karty fungují, soupeřova frakce v lobby skrytá, odhalená ve `start`; 0 chyb v konzoli i v logu serveru |

### Rozbor B1 (pro M5-A)
- Kult ve Stratégovi: duel bot čeká skoro pořád na obnovu věží (křehké stavby Kultu), za celý zápas vyšle 1 jednotku;
  AI za Kult má ve Stratégovi taky jen 20 %. Varianty `first_unit` (scratchpad) 90 → 85/75 %, tedy nejde o jednu chybu bota.
  Ablace nekromant→medik dává Kultu ve Stratégovi 50 % (Nekromant v kompozici je slabý).
- Přeživší jako obránce: crack 10–60 %, útočník je neprolomí (B2). Přeživší v Králi proti Bez frakce 25 %.

### Otevřené body
- M5-A: B1–B4 z `_out/report_fac_q1.txt` (kult Stratég, prez turtle, spam proti Kultu, výhoda strany 0 ~55 % zděděná z 0.5).
- M3-G hlásil jeden neopakovatelný RED v run_fast při zátěži; v gate 3/3 GREEN.
- UI: popisek „Plamenomet“ v liště se při 1366×768 láme uvnitř slova (`#bar .bb b overflow-wrap:anywhere`) → M4-C;
  sólo Přežití ukazuje slot Tlupa a hádanky slot „Četa na Relikvii“ (server je odmítne) → M4;
  dlouhé nadpisy konce hry se zalomí na 2 řádky (vypadá dobře); „Puzzle“ vs „Hádanka“ sjednotit v M5-D.
- Dříve otevřené: výkon dema během zatmění, software canvas, `meta.xp_gain` po quit, zvuky neposlouchané.

### Jak pokračovat
- Další je **M4** (M4-A sonnet, M4-B sonnet, M4-C sonnet, M4-E haiku) workflow `hmk-milestones.js`, pak M5.
- Commit/push dělá jen vedoucí na pokyn uživatele (repo Games je veřejné).
