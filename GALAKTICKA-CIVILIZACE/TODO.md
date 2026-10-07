# TODO

## Rozhodnuto (2026-10-07)
- Název: **Galaktická civilizace**, UI česky i anglicky (přepínač)
- Reálný čas s pauzou a zrychlením (1× = 1 herní hodina za sekundu, až 10 000×)
- Katalog HYG v4.1 stažen do `data/raw/` (necommitovat, je v .gitignore), skript `data/build_stars.py` -> `js/data-stars.js`
- Měřítko pokroku: Kardaševova škála (cíl = typ III, galaktická civilizace)
- 2D pohled shora, WebGL2 + HDR + bloom; kamera ukazuje vrstvu prostoru tlustou jako šířka záběru (jinak by se promítly hvězdy z celého sloupce nad/pod rovinou)

## Hotovo (verze 0.1)
- [x] Engine: plynulý zoom přes 25 řádů, lety mezi objekty, HDR, bloom, nekonečné pozadí
- [x] 107 798 reálných hvězd, ověřené hodnoty známých obrů, exotické objekty, galaxie Místní skupiny
- [x] Sluneční soustava v reálném měřítku, procedurální soustavy, známé exoplanety
- [x] Mléčná dráha (model s příčkou), procedurální hvězdy za hranicí katalogu, nekonečné pole galaxií
- [x] Těžba, výroba (9 receptů), 17 typů staveb, energie po soustavách, 14 technologií
- [x] Dysonův roj a sféra (vizuálně i ekonomicky), antihmota ze 4 zdrojů, Penningovy pasti
- [x] Sondy (0,1 / 0,2 / 0,5 c, dilatace času), brány a červí díry, sdílený sklad sítě
- [x] Uložení hry (localStorage), CZ/EN

## Verze 0.5 alfa (2026-10-07): vydáno do repa Games

## Hotovo (verze 0.2, po prvním hraní)
- [x] Tlačítka reagují na stisk (panely se překreslují 4×/s, klik se dřív ztrácel)
- [x] Konečná ložiska: zásoba, rychlost těžby a čas do vyčerpání u každého tělesa (plynní obři nevyčerpatelní)
- [x] 28 úkolů s odměnami a tlačítkem „Ukaž mi“ (karta vlevo dole + záložka Úkoly)
- [x] Příručka: odkud se bere každá surovina a k čemu slouží; klik na surovinu ve skladu nebo v ceně ji otevře
- [x] Výzkum: co technologie odemkne, splněné/chybějící požadavky, odhad času
- [x] Při nedostatku surovin hra napíše, co chybí
- [x] Vyhledávání hvězd, planet a galaxií (klávesa /), české aliasy (Alfa Centauri, Polárka…)
- [x] Sandbox: vše vyzkoumané, nekonečné suroviny, sondy za hodinu
- [x] Oprava: kruh v Mléčné dráze (skok jasu na 3,2 kpc)

## Další nápady
- [x] Zoom na hvězdu mimo střed vrstvy: kamera plynule sjede do její hloubky, ostatní hvězdy slábnou pozvolna (měkký okraj do 3× tloušťky vrstvy)
- [x] Požadavky a odemčení ve výzkumu jako barevné štítky (červená chybí, zelená splněno)
- [x] Ukazatel energie: spotřeba / výroba; po najetí myší rozpis zdrojů (typ, těleso, počet) a spotřebičů po soustavách
- [x] Bublina nad hvězdou: vzdálenost, svítivost, poloměr, cena červí díry, stav; nad planetou dráha, tok záření, ložiska
- [x] Texty v panelech jdou označit a kopírovat (překreslení se při označování pozastaví)
- [x] U nepřipojené hvězdy kontrolní seznam „Cesta sem červí dírou“ s odkazem na další krok
- [x] Tlačítko + u postavených staveb
- [x] Skrytí Dysonových staveb (tlačítko v panelu hvězdy, klávesa D), zůstane jen čárkovaný obrys
- [x] Výkon: nastavení kvality grafiky (auto/vysoká/střední/nízká) s ukazatelem FPS; auto snižuje rozlišení, když snímek trvá přes 30 ms; ořez částic roje mimo obrazovku, levnější pozadí
- [x] Výkon 2: Mléčná dráha předpočítaná do textury, pozadí se přepočítá jen při posunu, halo hvězd podle jasu, neviditelné hvězdy se nekreslí, hledání pod kurzorem max. 20×/s. GPU čas (měřeno): soustava 6,6 → 2,7 ms, okolí 300 ly 22 → 6,7 ms, galaxie 7,7 → 3,1 ms
- [x] Bubliny u ⚡ ✦ ⚗ jdou posouvat (kolečko i posuvník), antihmota: zdroje, pasti, kapacita; výzkum: laboratoře, spotřeba obvodů, odhad času
- [ ] Vyvážení ekonomiky po prvním hraní (rychlost těžby, ceny staveb a technologií)
- [ ] Gravitační čočka u černých děr (zkreslení pozadí přes texturu scény)
- [ ] Dysonova sféra kolem pulsaru (výkon z rotace: Krabí pulsar 45 QW)
- [ ] Logistika mezi soustavami (kapacita červí díry), události (supernova Betelgeuse?)
- [ ] Vizuál staveb na planetách při velkém přiblížení
- [ ] Kosmická síť: vlákna a prázdnoty jako souvislá struktura místo bodů
- [ ] Export/import uložené hry do souboru
- [ ] Zvuky a ambientní hudba
