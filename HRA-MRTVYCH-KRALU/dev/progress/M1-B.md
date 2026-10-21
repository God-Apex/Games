# M1-B progress (dev test suite)
Sources: scratchpad integ/{tests,fuzz,replay}.py, integ/bal/*.py (ported). HMK_SERVER = path to server.py or game dir.
Harness default = 1.0 rules (HMK_COMPAT05=1 -> 0.5 rules on 1.0 engine). Harness tunables via H.setc()/H.D (hmk.defs).
- [x] _paths.py, golden/statehash.py (literal SPEC form: e,s,throne unrounded; M1-A's Game.state_hash matches), .gitignore
- [x] bal/harness+run+variants+fair ported; reset_rules() MRO-wide; TICK_HOOKS; price()/need_doba()/horde_cost() used when present
- [x] golden/golden.py (worker subprocess per server) + test_golden.py: 20/20 identical vs M1-A hmk (45 s)
- [x] test_features.py (14 groups, 97 checks, compat05), fuzz.py, replay.py, perf.py (--compare, --b7), test_py38.py,
      test_hashorder.py (static + PYTHONHASHSEED), test_harness.py, test_tools.py, run_fast.py (35 tests, ~25 s, GREEN)
- [x] long gates on M1-A hmk: golden 20/20 (45 s), fuzz 4x2x400 s 0 exceptions (205k actions), perf --compare ratio 1.02 (B7 OK), run_fast GREEN (~25 s)
- DONE; waiting for orchestrator. Notes: lan_ips set-filter allowlisted in test_hashorder; harness default = 1.0 rules.
