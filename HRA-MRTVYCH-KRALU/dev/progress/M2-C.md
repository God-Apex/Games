# M2-C progress (AI core)
Plan: profiles(DIFF) -> view -> actuator -> planner -> pilot -> commander -> __init__ -> bal/novice.py -> ai_ladder.py -> tests -> calibrate gates.
- [x] read SPEC + MAI 5, engine API (actions, king, combat, world)
- [x] profiles.py, view.py, actuator.py, planner.py, pilot.py written (run 1; untested)
- [ ] commander.py, __init__.py AIPlayer, novice.py, ai_ladder.py, tests, calibration
- [x] (run 2 found) commander.py, __init__.py AIPlayer, bal/novice.py already written in run 1 (untested)
- run 2: smoke test -> tests (fog, determinism) -> ai_ladder.py -> calibration
- [x] smoke: AI vs AI runs without errors; wrote dev/tests/ai_ladder.py (pool, --one, --gate)
- ladder run 1 (5 seeds): T>S 47.5 % FAIL, S>L 90 % OK, L vs novice 100 % FAIL (novice dies ~300 s); tezka think max 47 ms (outlier)
- fixes: DIFF spend/cap/regap (push size), eclipse timing only when E in (18,30] s, hurt King keeps guarding/repairing
  -> T>S 62.5 % (kral 40, strateg 85; rush 42 %, B:turtle 45 %). Next: kral weakness, rush, Lehká vs novice.
- novice.py: literal spec novice loses 100 % (hoards, no research). Added: spends spare energy on random towers/units,
  researches (documented in docstring; report to lead). Lehká weakened (upg_max 1, def_scale .4, misplace .3, push cap 4,
  gen_l2 300 s w/o tower rule). Actuator.queued() fixes double gen builds. Now L vs N 90 %.
- new DIFF knobs: gen_l2_towers lane def_max night_build repair escort guard idle_lx; ai_ladder env HMK_AI_PATCH.
  Key finding: AI games mostly end at night (symmetric zombie drain); the tie-break is King position + defence.
  Lehká now: push 300 s cap 2 regap 60, gen_l2 600, King passive (no guard/escort, idles at home) -> L vs N ~51 %
  (kral 57.5, strateg 45; 10 seeds). novice.py NOVICE_TOWERS=18. NEXT: Těžká vs Střední >= 70 %.
- Těžká: surplus towers (knob surplus=9), Kings stay home at night, king_relic knob (Těžká default True still),
  strats -> mixed .35 turtle .5 rush .15 (turtle strongest). T>S before: kral ~50, strateg ~88. Running full gate.
- night_line (Těžká fills local x 0-1 at night), Těžká king_relic False. Full gate 10 seeds:
  T>S 71.2 % OK (marginal; kral ~50, strateg ~90), S>L 97.5 % OK, L vs N 51.2 % OK. NEXT: tests fog/determinism, run_fast, golden.
- [x] test_ai_fog.py, test_ai_determinism.py (+ ai_ladder --hash) pass. NEXT run_fast + golden
- [x] run_fast GREEN 192 tests, golden 20/20, all 5 maps 0 errors, Session path with real AI OK
- Těžká horde_spare=600 (Tlupa whenever rich / at night): T>S 82.5 % (kral 70-75). checking seeds 11-20 + S>L
- [x] DONE (run 2): official gate (seeds 1-10, ruiny+predmesti, 2 modes, 2 sides): T>S 82.5 %, S>L 97.5 %, L vs N 51.2 %
  (seeds 11-20: 92.5 / 98.8 / 50.0). Těžká think avg 0.23 ms. fog + determinism tests OK. run_fast GREEN, golden 20/20.
- run 3: verified already complete; run_fast GREEN again. No changes made.
