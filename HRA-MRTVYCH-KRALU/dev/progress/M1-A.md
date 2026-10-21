# M1-A progress (package split + seams)
- [x] read SPEC, server.py 0.5
- [x] hmk/defs.py entity.py maps.py data/maps.json
- [x] mixins vision actions combat movement king world + game.py
- [x] modes.py, stubs (factions facmech puzzle tutorial ai meta session)
- [x] lobby.py net.py server.py .gitignore
- [x] golden check (scratchpad gold/), features/fuzz/perf, browser 8101
Notes:
- Game(seed=None, rng=given) does NOT draw a seed (would shift the golden stream); self.seed = None then.
- tests.py (0.5 features, via scratchpad m1a/new shim) 0 failed; fuzz 4x300s 0 failures; golden 2 seeds identical
- golden 20/20 identical (m1a/gold.py); browser 8101: 2-tab match, units fight, end screen, 0 console errors
- perf: tick avg new vs old within ~1-2 % (parallel pairs, identical games); unit_may_enter cached as g.may_enter
- DONE. All deliverables in place; only final report left.
