# M2-D progress (client shell: lobby, maps, bus)
Plan / milestones (tick when done):
- [x] 1 base.js: BUS on/emit, CLIENT_VER 0.9, S fields (type, solo, kit, theme)
- [x] 2 maps.js: TERRAIN, isWalk, isBuild, paintTerrain, drawMapPreview, mapTheme
- [~] 3 css stubs done (modes/meta/settings), index.html new lobby + mount points + script order done; css/lobby.css MISSING (todo), style.css old lobby rules to review
- [ ] 4 lobby.js: lobby code moved from ui.js, new layout, cfg/solo sending, folio tabs, lobbyTab, LOBBY  (file exists 24KB, state unverified after interruption)
- [ ] 5 ui.js: lobby code removed, bus emits, start/end new fields, squad button, advisor relic tips (unverified)
- [ ] 6 input.js: WALK/BUILD, tooltips, H squad key, Esc emit, modal guard; main.js wiring; stubs modes/meta/settings (stubs done)
- [ ] 7 browser check on hmk-p4 (8104) with mock server (scratchpad), 1366x768 + 1920x1080, no hscroll, 0 console errors
- [ ] 8 run_fast + golden, final report
Notes: resumed after interruption (2nd attempt); verify steps 4,5 by reading files.
Resumed work log (attempt 2):
- reviewed base.js/maps.js/lobby.js/ui.js: steps 1,2,4,5 present and consistent. Renamed maps.js mapTheme -> terrainTheme (render.js owns a global mapTheme()).
- input.js done: WALK in kralBlocked, canal speed x1.25 prediction, terrain tips, H = squad (Strateg) / help, F1 help, Esc -> emit('esc','idle'|'modal'), modal guard (#pauseOv #setOv #welcomeOv).
- ui.js: S.relicZone per map in startGame, #endMeta cleared before emit('end').
- main.js: removed duplicate lobby wiring (lobby.js owns it); blur only in game.
- TODO: css/lobby.css (+ check style.css), browser check with mock server, run_fast + golden.
Attempt 3: css/lobby.css written (type seg, setgrid, map select+preview, dseg, ftabs). Next: syntax check JS, mock server in scratchpad, browser check hmk-p4 (8104), run_fast + golden.
Attempt 3: browser check on 8104 in progress: lobby layout 1366x768 OK (ready btn above fold), solo send OK, Vycvik Strateg game starts with squad button. TODO: relic tip + H squad check, Most map placement/tooltips, 1920x1080, run_fast+golden.
- run_fast GREEN (189 tests). golden started.
- Browser check DONE on 8104 (tabs closed, server stopped): lobby 1366x768 and 1920x1080 no hscroll, no text <14px, solo/cfg/ready messages OK, Vycvik Strateg + Metro game OK, H squad OK (deploys + cooldown), relic tip OK, canal/dais tooltips + refusal 'V kanalu staveti nejde.' OK, end overlay OK, 0 console errors. Remaining: golden result, final report.
- golden 20/20, run_fast GREEN (189). M2-D DONE (all 8 steps). Requests: hmk/__init__.py VERSION '0.9' (nobody owns it); quit-end stats show 0 (check session.finish).
