# M3-A progress (Factions server)
- [x] step 0: read SPEC, PROGRESS, FAC doc
- [x] step 0b (attempt 2): read all engine files; plan below
Plan / decisions:
- compat05: owned zombies never get `own` set (stays -1) -> no cap, no friendliness = 0.5 exact; cmd_of gives utok doba 1.
- `g.facon` = any faction != bez; faction passives/timers/damage hooks guarded by it (perf + golden).
- Hnízdo ticks from tower() (non-attack branch). Plague: rise if died <0.2 s after a cloud tick hit it.
- King perk tesla chain includes buildings (same filter as King target).
Steps:
- [x] 1 factions.py data + defs (CMDS utok doba 2, valid_deck fac, up loop, ATTACK_TOWERS hangar)
- [x] 2 entity fields; game.py price/need_doba/cmd_of/horde_cost/max_hp/income/timers/snapshot/start/end
- [x] 3 actions (max, emp, mor, rcost, cmd variants, doba check, horde own)
- [x] 4 combat/movement/king/world/vision mechanics; facmech
- [x] 5 test_factions.py; run_fast + golden
  (steps 1-3 done in files; helper for CRLF-safe replace: scratchpad/rep.py)
  step 4 code written (facmech full); next: smoke + run_fast + golden, then test_factions
- golden after step 4: see below
- golden 20/20 OK after step 4; run_fast 192 GREEN; test_factions 29 OK. Next: run_fast again, perf compare, fuzz quick
- facfuzz (scratchpad/facfuzz.py, 12 games x 500 s random actions, all factions): 0 exceptions; deterministic across PYTHONHASHSEED. perf --compare ratio 1.068 OK (B7 max 33 ms = machine load, recheck)
- run_fast GREEN (test_tutorial errors were M3-B1 mid-edit, green on rerun); test_factions slow test shortened
- perf: A/B identical compat05 games (scratchpad/ab.py, CPU time, min of 3): tick 0.519 (0.5) vs 0.541 ms = 1.04; snapshot flags guarded by facon. perf.py --compare is too noisy now (parallel agents)
- FINAL: golden 20/20, run_fast GREEN, test_factions 29 OK. M3-A DONE (only the final answer/requests left).
