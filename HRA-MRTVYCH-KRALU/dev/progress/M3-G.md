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
