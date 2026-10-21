# M2-B progress (Sessions + lobby protocol)
- [x] read SPEC 1-7, MAI 4/7.1, META 4.2/9, current lobby/net/session/fuzz
- [x] hmk/session.py (Session, build_game, summary)
- [x] hmk/lobby.py (room cfg, solos, routing), hmk/net.py (Client fields, defs, flags), server.py doc
- [x] dev/tests/test_lobby.py (FakeClient), fuzz.py lobby part
- [x] run_fast (only test_meta fails = M2-F in progress) + golden 20/20; server smoke 8102 HTTP 200. DONE
Design notes: Session builds games via session.build_game(type, opts, humans, seed); AI via lobby.ai_factory
(default hmk.ai.make_ai, fallback IdleAI); optional hooks hmk.ai.pick_fac/pick_deck.
- [x] test_lobby 8/8 OK, fuzz (--lobby 4 --games 2 --secs 200) 0 failures (resume run)
- [x] re-verify (2026-10-19): test_lobby 8/8, run_fast 158 GREEN, golden 20/20. Final report sent.
