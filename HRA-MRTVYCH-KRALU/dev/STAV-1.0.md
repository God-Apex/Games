# Hra mrtvých králů 1.0 – co je hotové a co zbývá

Stav k 21. 10. 2026. Podrobný průběh je v [PROGRESS.md](PROGRESS.md), zadání v [SPEC-1.0.md](SPEC-1.0.md),
postup jednotlivých balíků v `progress/`. Rozpracovaná verze 0.9 je v repu Games (commit 3150675),
změny z M3-G a z kontroly M3 zatím commitnuté nejsou.

## Hotovo

### M1 – Základy (kontrola prošla)
- Server rozdělený do balíčku `hmk/`, `server.py` je jen spouštěč (`Spustit server.bat` funguje dál).
- Testy přesunuté do `dev/tests/`. Kontrolní test ověřuje, že hra s pravidly 0.5 hraje přesně jako 0.5 (20/20).

### M2 – Platforma (kontrola prošla)
- 5 map: Ruiny, Předměstí, Továrna, Most, Metro. Nový terén: sloup, voda, most, kanál, vyvýšené místo.
- Sólo hry běží vedle zápasu dvou hráčů. Ve hře jde pauza, restart a vzdání.
- AI soupeř ve třech obtížnostech (Těžká porazí Střední v 83 % her, Střední Lehkou v 98 %).
- Nové lobby s výběrem mapy a typu hry, rychlejší vykreslování (překreslování asi o polovinu menší).
- Základ statistik, úrovní a úspěchů na serveru.

### M3 – Obsah (hotovo, kontrola prošla s výhradou u vyvážení frakcí)
- Tři frakce (Přeživší, Korporace, Kult), každá se 3 vlastními kartami, schopností Krále a příkazem Stratéga.
- Režimy Přežití a Výuka, 10 hádanek s hvězdičkami, AI hraje za frakce i v Přežití.
- Kresba, efekty a zvuky frakcí, výběr frakce v lobby, statistiky ze serveru.
- Boti a sady simulací pro vyvážení frakcí (M3-G).
- Kontrola M3 opravila: hodnocení hvězd u hádanek (už žádné „nejisté“), správné maximum trůnu u hádanek
  a ve Výuce (dřív 500/3000), nadpis konce hry u Přežití, hádanek a Výuky, ukazatel Relikvie se už
  nezobrazuje tam, kde Relikvie není. Čeština prošla korekturou.
- Výsledky kontroly: testy (301) zelené, regrese 0.5 20/20, fuzz 0 chyb (nově i všechny režimy a frakce),
  AI za frakce 47–65 %, v prohlížeči prošly oba zápasy s frakcemi, Přežití, Výuka v obou ovládáních,
  hádanky p01 a p02 na 3 hvězdy, pauza a restart, 0 chyb v konzoli.
- **Výhrada:** rychlá simulace frakcí má 2 z 20 dvojic mimo pásmo 30–70 % (Bez frakce proti Kultu
  ve Stratégovi 90 %, proti Přeživším v Králi 75 %). Rozbor: nejde o chybu botů, Kult je ve Stratégovi
  slabý (křehké stavby, AI za Kult tam vyhrává jen 20 %). Doladění patří do M5-A.

## Zbývá dokončit

### M4 – Meta v klientovi (další krok)
- **M4-A** obrazovka Statistiky, Síň slávy, grafy na konci zápasu, úvodní „VS“ obrazovka.
- **M4-B** kosmetika: koruny, praporce, varianty kamene a efekty vítězství.
- **M4-C** nastavení se 4 záložkami, test zvuku, přístupnost.
- **M4-E** skript na vydání (kontrola verzí, hledání tajných údajů, zip bez .exe).
- Kontrola M4.

### M5 – Vydání
- **M5-A** vyvážení frakcí podle simulací (každá dvojice frakcí 40–60 % výher). Hlavně Kult ve Stratégovi
  a Přeživší jako obránce (útočník je skoro neprolomí).
- **M5-B** doladění AI, map a Přežití.
- **M5-C** celková kontrola (fuzz, výkon, kontrolní seznam pro LAN).
- **M5-D** česká dokumentace (README, DESIGN, řádek v Games/README).
- **M5-E** verze 1.0 a zip. Zveřejnění až po souhlasu uživatele.
- Kontrola M5.

### Drobnosti k vyřešení později
- Popisek „Plamenomet“ se ve spodní liště při 1366×768 láme uprostřed slova (M4-C).
- V sólo Přežití je vidět tlačítko Tlupa a v hádankách bez Relikvie „Četa na Relikvii“, server je odmítne (M4).
- Hra střídá názvy „Puzzle“ a „Hádanka“, sjednotit (M5-D).
- Výkon v demu během zatmění, plynulost na PC bez grafické akcelerace, `meta.xp_gain` po vzdání,
  zvuky zatím nikdo neposlouchal.

## Odhad
- Zbývá zhruba **8–12 hodin práce agentů**: M4 asi 3 h, M5 asi 5–8 h (nejdražší je vyvážení frakcí).
- To jsou asi **2–3 okna limitu**, realisticky **2–3 dny** podle toho, jak často se bude pokračovat.

## Jak pokračovat
1. Napsat „pokračuj na 1.0“.
2. Pustí se M4 skriptem `C:\!Data\!AI\!Code\.claude\workflows\hmk-milestones.js` (balíky a modely v SPEC §6), pak M5.

Hratelná verze pro mezitím: 0.5 v `%TEMP%\hmk\release05_snapshot` (`Spustit server.bat` v té složce).
Složka hry je teď 0.9 s frakcemi, Přežitím, Výukou a hádankami. Hratelná je, vyvážení frakcí ještě není hotové.
