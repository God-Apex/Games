# M3-D progress (faction art, fx, sfx) — js/{paint,render,audio}.js
- [x] step 0: read SPEC §1-7, FAC §6 (art brief)
- resume 1 (19.10.): originals backed up in scratchpad\m3d\{paint,render,audio}_before.js
- [x] step 1: paint.js — FAC_ART {charge, acc, acc2}, facOf/setSideFacs, paintEmblem(g,s,r,fac), emblemImg(fac,side,px),
      paintFacTrim (b/u/th; King sceptre via paintSceptre in paintKing), 'off' variant (desaturate), zombie collar (sprZombie own),
      sprites ostnata(3 lvls) dilna hangar hnizdo mrchozrout exo nekromant + icons emp mor; cache keys B|..|fac U|..|fac K|..|fac TH|side|fac Z|..|own;
      Kult Generátor grave-light flames
- [x] step 2: render.js — on('start') -> setSideFacs(m.fac); fx H E M Z W (onFx + drawFx, FX_LIFE); mc clouds (showCloud);
      collar 2048/4096 (ownOf); EMP-off 8192 ('off' sprite + crackle, no live flames); Exo shield = dashed bubble (flag 16 on exo);
      raised zombie emerges after the hand (FXS.raise)
- [x] step 3: audio.js 6 sfx (SND emp mor raise turn hangar thorns; FX_ANY H, FX_SIDE E M Z W; thorns on m-fx into ostnata)
- [x] step 4: run_fast GREEN, golden 20/20; browser 8105: sprite sheets (all facs x sides), emblems, demo with injected flags/fx/mc, 0 console errors; tab closed, server stopped
- DONE
