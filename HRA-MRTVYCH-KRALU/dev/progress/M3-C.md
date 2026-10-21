# M3-C progress (AI content: hmk/ai/**, dev/tests/ai_ladder.py)
Run 2 (run 1 only read SPEC). Read SPEC 1-7, FAC 2-5/8, MAI 3/5/6, all hmk/ai/*.py, ai_ladder.py, session hooks.
Engine note: M3-A landed factions.py/facmech.py mid-run (12:25); bez hashes changed from M2 because of 1.0 global rules.
- [x] step 1: read everything
- [x] profiles.py: FACTION_PLAN (prez/korp/kult: decks, insert, comps, P), PREZITI overlay, PREZITI_DECK, UP_PATH+
- [x] facplay.py (Dílna/Hnízdo/EMP/Mor/war cry/Volání mrtvých/Exo sub/squad kinds)
- [x] planner.py hooks (s_faction, s_surv_units, zombie_nalet, rcost, pace_free, comp, try_deploy sub); pilot/commander hooks
- [x] __init__.py: AIPlayer P merge (faction P, PREZITI), _detect_strat with faction decks, preziti deck swap; pick_fac via FAC_IDS
- [x] ai_ladder.py rewritten: tezka@fac specs, --gate7 (5 maps), --fac, --surv, usage report (A9)
- [ ] verify: fog lint OK; one faction match OK (kult built Hnízda, cast Mor)
- [ ] run --fac suite, tune; --gate7 on 5 maps -> map weights if needed
- [ ] preziti profile test (needs SurvivalRules from M3-B1)
- [ ] run_fast + golden
- [x] verified: fog lint + determinism tests OK; --fac suite (5 seeds, predmesti): prez 65, korp 65, kult 55 % vs bez (35-65 gate; M5-A balances); usage fine in samples
- [x] Přežití smoke (AI vs AI, solo `tezka:none`): median waves Lehká 19 / Střední 29 / Těžká 36 (clearing squads +2 waves on Těžká); both AIs reach wave 39 in 2p
- [x] planner._fit: fixed maps (not ruiny) move template cells that are not BUILD to nearest buildable cell (Metro 15->21 cells)
- [ ] gate7 on 5 maps: baseline running (g7a.txt, old _fit-less code, 4 seeds); then A/B with _fit
- [ ] run_fast + golden (at the end)
- [x] gate7 4 seeds, old code: Td>St 75, St>Le 100, Le/Novice 35 (tovarna 12!), St/Nov 97, Td/Turtle 86, median St:St 816 s FAIL
- [x] fixes: planner.cross (pushes only on rows crossable through the Mist; fixes water/pillar lanes on Most/Továrna), _fit
  -> gate7 4 seeds: Td>St 81, St>Le 96, Le/Nov 51, St/Nov 97, Td/Turtle 92; median St:St 814 s still FAIL (DIFF tuning = M5-B)
  map fairness tezka:tezka tovarna+metro 20 seeds x 2 modes: 53.8 % side 0
- [x] --fac 10 seeds: prez 67.5 (FAIL by 2.5pp), korp 45, kult 47.5; usage low for exo 50 %, nekromant 40 %, emp 85 %
- [x] facplay.unit(): lone faction unit every 60 s when none alive (Exo/Nekromant/Mrchožrout); EMP also defensively (>=3 foes in 3x3 in own half)
- [ ] rerun --fac 10 seeds + gate7; run_fast + golden; final answer
- [x] DONE (run 2): --fac 10 seeds after unit()/EMP changes: prez 65 / korp 60 / kult 47.5 % (OK), usage prez 100, korp exo 80 emp 100 hangar 100, kult nekromant 90 mor 100 hnizdo 100
- [x] run_fast GREEN (284 tests), golden 20/20, fog lint + determinism (also with factions, PYTHONHASHSEED 1 vs 2) OK
- [x] smoke all 5 maps x random factions (duel + Přežití, solo waves Těžká 29-41, Metro hardest): 0 errors
- Open for M5-B: median Střední:Střední 814 s (gate 480-780), per-map Lehká vs Novice noisy (n=16/cell), AI Přežití much stronger than harness targets
