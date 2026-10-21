# M2-E progress
- [x] start; backup of original render.js: scratchpad\m2e\render_before.js

- [x] read SPEC/META §7; baseline (old code, ?demo=40, 1616x910 DPR1, manual draw x60): drawImage+fillRect 8.0 Mpx/frame = 5.44x, lighter 0.23 Mpx, draw 3.9 ms
- plan: QUAL (q/hmk_qa/auto-step, RS), LAYER+decal steps, fogPat, shade() combo, edge-strip vignettes, PERF (?perf, PERF.bench(n)), fps counter, paintTerrain pass, '^' range rings, canPlace isBuild
- [x] implementation written in js/render.js (QUAL/RS/auto-step, LAYER+decal steps, fogPat+fogc, shade(), edge-strip vigs, PERF ?perf + bench, fpsCorner, paintTerrain, '^' rings, terBuild/terWalk) — found done on resume
- [ ] syntax check, browser verify (?perf demo=40/120, screenshots, console), then done
- resume 2: node not installed -> syntax check via browser; starting browser verify on hmk-p5
- [x] browser: render.js loads w/o JS errors; demo=40 1616x910 RS1 Q2: 3.28 Mpx 2.23x, lighter .15, 3.2 ms (was 5.44x). only 404 = css/lobby.css (not mine)
- demo=120 sampled over the 32 s cycle: mean ~4.4x, peak 4.9x (eclipse DARK blit 0.9x + red vig 0.5x + shake stack). 3.39x at start.
- [x] shade(): outage/king-dead without darkness now fillRect directly (no full DARK blit) -> re-measure
- [x] re-measure demo=120 over cycle: 3.1-4.65x, mean ~3.9x; demo=40 2.23x; noc,40 3.58x; Q0/Q1/Q2 switch OK; 0 JS errors (only 404 css/lobby.css, not mine)
- [x] run_fast GREEN (189 tests). Tabs closed, hmk-p5 stopped. M2-E DONE (gate does before/after screenshots vs scratchpad\m2e\render_before.js)
