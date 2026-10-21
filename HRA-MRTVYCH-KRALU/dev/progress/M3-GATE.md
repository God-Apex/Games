# M3 GATE log
- 2026-10-21 start: read PROGRESS/STAV; next: collect requests from M3-*.md, read SPEC §6/§7

- step 1 DONE: requests applied: puzzle.py star_hits + end.puzzle.hit; game.start_info thmax + ui.js S.thMax per side (throneBar, annDiff, render throne); ui.js end title per type (puzzle/vyuka/preziti). Other requests from logs: none for M3 (M5-B/M5-A items only). next: check other Porážka texts, run tests
- step 2a: run_fast 301 GREEN after request fixes. fuzz.py gained --content (all types x factions, puzzles, vyuka; 1 seed x 120 s = 0 failures). Running in bg: fuzz --content 3 --csecs 400 --lobby 6 -> _out/gate3_fuzz.txt; golden -> _out/gate3_golden.txt
- step 2b: golden 20/20 identical; fuzz (4x2 duel 400 s + content 26 cfgs x 3 seeds x 400 s + lobby 6) 703737 actions, 0 failures.
- step 2c: facrun quick B1 sanity FAIL analysed: bez-kult strateg -> kult duel bot plan waits on rebuilding sniper/hlaska layout (fragile kult towers), u_n=1 in most games; ablate nekromant->medik gives kult strateg 50 %. Testing first_unit gate (scratchpad m3gate/).
- step 2d: B1 sanity: first_unit variants (scratchpad m3gate/exp.py, bez-kult strateg n=20): base 90, nowait 85, late 75 -> no single bot bug; kult Stratég weak (fragile towers, plan rebuilds, nekromant comp; ablate nekro->medik 50 %). Classified balance -> M5-A, no bot change.
- step 2e: Czech proofread (scratchpad m3gate/texts.txt, 254 strings): fixed 'Vítej ve Hře' (modes.js), quotes „Jsem připraven“ (lobby.js 251). Running ai_ladder --fac (bg) -> _out/gate3_aifac.txt
- step 3a: ai_ladder --fac 10 seeds: prez 65.0 / korp 60.0 / kult 47.5 % PASS (kult Stratég 20 %), usage OK (exo 80 %, nekromant 90 %).
- step 3b: browser 8097 (preview 'mrtvi-krale', tab seed, 1366x768): welcome modal ('Vítej ve Hře'), Výuka Král + Stratég completed via send() driver (all steps, title 'Výuka dokončena', foe throne bar 1200/1200 = per-side max OK). 0 console errors so far. Next: faction pick + Souboj per faction (2 tabs), Přežití, p01 3 stars + another puzzle, pause/restart.
- step 3c: browser: p01 via lobby Puzzle grid -> Začít; Esc pause stops tm (17.8==17.8), Začít znovu restarts; p01 3 stars (hit flags ✔✔✔ shown, hmk_puzzle saved), p02 3 stars via Další (throne max 1200/3000 OK). 0 console errors. Seen: relic chip 'probudí se za' shown in puzzles without relic (checking).
- step 3d: fix: relic chip/zone showed in puzzles/Přežití/Výuka -> game.start_info 'relic_at' (None = no relic, puzzles 0) + ui.js S.noRelic/S.relicFrom per game + render.js relicZone skip. Server restarted.
- step 3e: browser: solo Přežití Stratég with Kult to the end ('Konec přežití', record saved, relic chip hidden); Souboj prez vs korp (Král, Předměstí) and kult vs bez (Stratég, Most) in 2 tabs: faction cards built/deployed (ostnata, dilna, mrchozrout, hangar, hnizdo, Tlupa 80/18 s), foe faction absent from lobby msg and revealed at start, quit -> Vítězství/Porážka. 0 console errors (only my injected test snippet), 0 server errors. Tabs closed, server stopped, localStorage cleared.
- fix: modes._fmt_time rounds (was 3:54 vs client 3:55).
- next: run_fast + golden + test_survival after fixes; perf; docs.
- step 4a: test_puzzles extended (hit, thmax, relic_at) OK; run_fast 301 GREEN after fixes; STAV-1.0.md rewritten. Waiting golden2 + perf (_out/gate3_golden2.txt, gate3_perf.txt), then PROGRESS.md.
- step 4b DONE: golden2 20/20, perf B7 OK (ratio 1.27 with 1.0 rules; compat05 1.039 OK), PROGRESS.md M3 section written. GATE COMPLETE.
