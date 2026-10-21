# M2-F progress (meta core: hmk/meta.py + dev/tests/test_meta.py)
Read SPEC 1-5,7 + §6 M2-F, META §1-3, §9. Stub meta.py replaced step by step.
- [x] hmk/meta.py: Store/normalize, key/need/title, xp_gain, elo_update, ACH, COSM, record, profile_view, stats_view, hof, set_cos, public_catalogs
- [x] dev/tests/test_meta.py
- [x] run_fast + golden green
Design decisions (see end of file for final notes).
## Resume note (2nd run)
- hmk/meta.py (1009 lines) and dev/tests/test_meta.py (44 KB) already exist from the interrupted run; verifying them now.
- [x] test_meta: 6 test bugs fixed (stale profile refs, sort order, helper kwarg dup); 48 tests OK.
- [x] review meta.py vs META 1-3/9 (edge cases), run_fast + golden
## 3rd run
- meta.py reviewed against META 1-3/9 + SPEC 5.4-5.6: complete (Store, key, need, title, xp_gain, elo_update, ACH, COSM, record, views, public_catalogs).
- Decision: Store.load with a MISSING main file starts fresh (SPEC/META 1.1: "missing -> new file"; .bak only on corrupt). Test test_main_missing_uses_bak updated.
- Request for M2-B: lobby.send_me should call meta.profile_view(store, c.key, name=c.name) so a not-yet-recorded profile shows the display name, not the casefolded key.
- [x] hmk/meta.py + dev/tests/test_meta.py DONE: test_meta 48 OK, run_fast 192 GREEN (31 s), golden 20/20. M2-F finished.
