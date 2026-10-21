# M2-A progress (engine: maps, terrain, counters, squad)
- [x] data/maps.json 5 maps (validate OK), maps.bfs_from WALK
- [x] WALK/BUILD in actions/movement/king/world/combat; ~ (step_of x0.75, King x1.25) and ^ (rng, vision +1.0)
- [x] counters (entity.Side.stats, combat kill/damage, world relic_s, actions spent/cast), ecl_log/night_t/sample/ser (game.py)
- [x] squad (actions.py squad/squad_kit/squad_cell/squad_member, g.pending in timers), snapshot 'sq'; checkmate code 'mat' added
- [x] run_fast GREEN after the code changes (48 s)
- [ ] tests: test_maps test_terrain test_counters test_squad
- [ ] full golden 20/20, final report
Requests for lead: modes.py DuelRules Alfa cells `== '.'` -> `in maps.WALK` (Most has only bridge cells in mid columns).
- [x] tests: test_maps (25 OK), test_terrain (17 OK, cleaned) -- resume: test_counters, test_squad, golden, report
- [x] golden 20/20 identical (after all engine changes); test_counters 25 OK
- [ ] test_squad, final run_fast, report
- [x] test_squad (31 OK) -- resume: final run_fast, report
- [x] final run_fast GREEN (189 tests, 28 s). M2-A DONE; only the modes.py request is left for the lead.
