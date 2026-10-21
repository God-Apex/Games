# M3-G progress (Faction balance tooling)
- [x] step 0: read SPEC §6/§7.2, FAC §8-9; M3-A done (factions server exists)
- [x] step 0b: read harness/run/fair/perf/factions/facmech/actions/game. Design decisions:
  - harness.run_game: side cfg 'fac' + deck role name -> FAC_DECKS; task 'swap' (mirrored seating), 'knobs'; out adds fac, swap, wa (score of scenario-p0 owner, draw 0.5), used (card usage per side via Game.act wrapper)
  - reset_rules also restores FACTIONS + OWNED_CAP
  - facbots.py: FAC_DECKS (roles def/att/mix/att_sn/spam + my extra 'duel' with all 3 own cards), FacMixin (fac_tick, fac steps), bots, scenarios registered into run.SCEN
  - facrun.py: suites matrix crack spam ablate perf fair selftest, --quick, report + PASS/FAIL (B1-B5,B7); no rush/rr/night (SPEC 1.2)
- [x] step 0c (attempt 2): re-read harness/run/perf/engine; harness.py had only reset_rules(FM) + install_tracking(used/noloot) done, run_game/bots untouched; facbots/facrun not yet written
  Plan: (1) harness.py: step tags (gens/layout/upg), king_tweak hook, utok Doba check, Attacker pick()/fallback/q_timeout/emprush/no_units, FAC_BOTS+make_bot, deck roles, fac/swap/knobs/wa/ws/used in run_game, install_usage split
        (2) facbots.py  (3) facrun.py suites + selftest  (4) smoke runs, golden + run_fast
- [x] step 1: harness.py patched (install_usage split, apply_knobs, step tags+items, king_tweak hook, utok_ok, contest_inf, Attacker pick()/q_timeout/emprush/no_units/comp list, FAC_BOTS/FAC_DECKS/load_fac/side_cfg/make_bot, run_game: swap+facs+knobs+ws/wa/used). Backup of the pre-M3-G file: scratchpad/m3g/harness_before_m3g.py. NOT yet verified (next: test_harness + golden)
- [x] step 2: facbots.py written (FAC_DECKS incl. duel/flood roles, FacMixin: plans prez/korp/kult, EMP/Tlupa/Mor/Volání/war cry, comps, ablate, builders turtle/mixed/att/emprush/spam/flood/duel, R.SCEN f_kk/f_flood/f_emprush)
- [x] step 3: facrun.py written (matrix crack spam ablate perf b6 fair selftest, --quick/--seeds/--knob/--rejudge/--tag). NOT yet run; next: selftest, smoke, golden + run_fast, A9 usage check
- [ ] step 4 (attempt 3, resume): started; running selftest first
- [x] step 4a: facrun selftest PASS (12 s, 45 checks). next: test_harness, golden, run_fast, smoke runs
- [x] step 4b: run_fast 301 GREEN (48 s) with the patched harness. next: full golden, then smoke runs
- [x] step 4c: golden 20/20 identical. next: smoke runs (facrun suites --seeds 1)
- [x] step 4d: crack smoke (--seeds 1) runs OK, no crash; kult/prez-turtle cells fail B2 = balance (M5-A), not tooling. next: smoke matrix/spam/ablate/b6/perf
- [ ] step 5: smoke matrix found bot bugs: (a) kult Tlupa rule starves the plan (kult duel side never pushed, u_n 0) -> Tlupa only when plan not waiting (+ push active for attackers); (b) korp EMP never fires (<2 enemy towers visible) -> fallback rules; (c) mirror pairs: swapped leg is an identical game -> use another seed. Fixing in facbots.py/facrun.py
- [x] step 5: fixed (facbots.py) Tlupa starvation (plan_state/push_on), EMP fallbacks (>=1 tower with >=5 units; defender rule), first_unit (exo/nekromant bought once ahead of the push); facrun.py mirrors get seed+100 on the swapped leg. matrix smoke --seeds 2: A9 PASS (exo 95%, others 100%). next: selftest again, smoke spam/ablate/b6/perf/fair
- [x] step 5b: smoke ablate/b6 OK; selftest 48 checks PASS. next: smoke spam, perf, fair; then quick full run + report
- [x] step 5c: smoke spam/perf/fair run OK (B7 PASS: tick avg 0.58 ms, p99 1.48, max 5.1; snap avg 1673 B max 3792 B; ents 87). fair smoke n=80: side A 65% (noise or engine bias, judge on quick n=400). next: facrun all --quick --tag q1 (background, ~25 min), then analyse report, update docs
- [x] step 6a: quick matrix (400 games, 462 s) judged: A9 PASS (exo 94.5%, rest >=99%), B1-quick fails only bez-prez kral 75%, bez-kult strateg 90% (balance); pooled kult 33%; fair n=400 side A 55.5%, loot B/A 0.982. Waiting for crack/spam/ablate/b6/perf of the all --quick run (tag q1)
- [x] step 6b: facrun all --quick --tag q1 DONE in 1493 s: PASS A9 B5 B6 B7; FAIL B1-quick (bez-prez kral 75, bez-kult strateg 90), B2 (prez turtles uncrackable, kult att weak), B3 (spam vs kult mixed strateg 60%), B4 (side A 55.5%). Report: dev/tests/_out/report_fac_q1.txt. next: B4 side-bias check (compat05 vs 1.0 rules, bez-bez mirror), then docs/final answer
- [x] step 7 (attempt 3): DONE. selftest 48 checks PASS; golden 20/20 identical; run_fast 301 GREEN (5 of 6 runs, one unreproduced RED while the PC was loaded); smoke of every suite OK.
  Bot fixes from smoke: Tlupa starved the plan (plan_state + push_on), EMP never fired (fallbacks), exo/nekromant bought once by first_unit(); mirror pairs get seed+100 on the swapped leg (swapped identical game = repeat); selftest checks flood and korp exo/emp.
  Quick run (facrun all --quick --tag q1, 1493 s, report dev/tests/_out/report_fac_q1.txt): PASS A9 (exo 94.5 %, others >= 99 %), B5, B6 (18/20 vs 19/20), B7 (tick avg 0.53 ms, p99 1.40, max 2.2; snapshot avg 1673 B, max 3792 B; 87 entities).
  FAIL (balance, for M5-A): B1-quick bez-prez kral 75 %, bez-kult strateg 90 %, pooled kult 33 %; B2 prez turtles hold (10-60 % crack wins), kult attacker weak, medians out of band; B3 spam vs kult mixed strateg 60 % (bez), 20 % (prez); B4 side A 55.5 % (n=400), loot B/A 0.982.
  B4 note: side 0 edge (about +4-5 pp, kral) is also there with compat05 (bez-bez duel mirror n=100: 1.0 rules 55 %, compat05 54 %), so it is inherited from the engine/harness order, not from M3.
