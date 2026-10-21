# M3-F progress (Meta server wiring) - owns hmk/{session,lobby,net}.py, server.py, dev/tests/test_session_meta.py
- [x] 0 read SPEC, META 1.1/1.6/3.1/4.2, current session/lobby/net/meta (attempt 1; no earlier log)
State found: session.finish already calls meta.record(store,...) and fills end.me/rec_new; lobby.hello/send_me/dup-name lerr exist;
net.DEFS_MSG has types/maps/puzzles/diffs but no factions.public()/meta.public_catalogs(); LOBBY has no Store; no stats_q/cos; start/end lv+cos are None.
Plan:
- [ ] 1 net.py: defs += factions.public() + meta.public_catalogs(); open Store from STATS_PATH (None -> memory-only); save on exit, retry in heartbeat
- [ ] 2 session.py: humans snapshot (name,key,human) so summary survives disc; start.cos/lv; end.lv; save after end broadcast
- [ ] 3 lobby.py: player_info lv/ttl/cos{ban,kor}; handle cos (debounced 2s save), stats_q -> stats; queue lv?
- [ ] 4 dev/tests/test_session_meta.py (2 room + 1 Vycvik recorded, ser len, me after hello, cos fallback, stats_q, dup name, disc)
- [ ] 5 run_fast + golden + test_lobby + fuzz --lobby quick; final answer
- [x] 1 net.py DONE: defs += factions.public()+meta.public_catalogs(); open_store(STATS_PATH) in main_cli (None -> memory-only Store); save on exit (finally); heartbeat calls LOBBY.store_tick()
- [x] 2 session.py DONE: session.who snapshot (key/human) used by summary (disc leaver still recorded), prof_lv(), start.cos/lv, end.lv after record, _save_store after end, rec_sides
- [x] 3 lobby.py DONE: player_info lv/ttl/cos{ban,kor}; handle cos (debounced 2 s save), stats_q->stats (+who), save_store/schedule_save/store_tick, fresh 'me' after recorded game
- test_lobby after steps 1-3: see next line
- [x] 4 dev/tests/test_session_meta.py DONE: 17 tests OK (defs catalogues, open_store, me after hello/name change, lobby lv/ttl/cos, dup name, 2 room + 1 Vycvik recorded
  with ser len floor(t/5)+2 (float-safe), short game, disc leaver, no store, cos fallback + 2 s save + opponent sees cos in start, stats_q, hof, save retry)
- [ ] 5 real-socket smoke on port 8103 (scratch script), then run_fast + golden + fuzz --lobby quick, final answer
- step 5 started: running test_session_meta, test_lobby, run_fast
- step 5: smoke script in scratchpad/m3f (smoke.py ok: defs, me, cos, stats_q, solo; MIN_LEN 60 s so quit after 2 s not recorded = OK); next smoke2 = room game 63 s + restart persistence
- [x] 5a real-socket smoke on 8103 DONE (defs cats, me, dup-name lerr on ready, cos, stats_q, 63 s room game: end.me/ser/lv, stats.json written, restart persistence, server stopped). next: run_fast + golden + fuzz --lobby
- [x] 5 DONE: run_fast 301 tests GREEN (47 s, incl. short golden, py38, test_session_meta 17, test_lobby 8); fuzz --games 0 --lobby 6: no exception. M3-F COMPLETE; final answer returned.
