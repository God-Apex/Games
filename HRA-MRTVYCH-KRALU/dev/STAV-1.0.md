# Hra mrtvých králů 1.0 – co je hotové a co zbývá

Stav k 21. 10. 2026. Podrobný průběh je v [PROGRESS.md](PROGRESS.md), zadání v [SPEC-1.0.md](SPEC-1.0.md),
postup jednotlivých balíků v `progress/`. Nic není commitnuté.

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

### M3 – Obsah (7 z 9 balíků)
- **M3-A** frakce na serveru: Přeživší, Korporace, Kult, každá se 3 vlastními kartami, schopností Krále a příkazem Stratéga.
- **M3-B1** režimy Přežití a Výuka.
- **M3-B2** 10 hádanek (Puzzle) s hvězdičkovým hodnocením.
- **M3-C** AI umí hrát za frakce a v Přežití.
- **M3-D** kresba, efekty a zvuky frakcí.
- **M3-E1** frakce v klientovi (lobby, karty, HUD).
- **M3-E2** režimy v klientovi (výběr hádanek, Přežití, Výuka, pauza, úvodní okno).
- **M3-F** zápis statistik ze serveru.

## Zbývá dokončit

### M3 – dokončení
- **M3-G** boti pro vyvážení frakcí (pozastaveno, asi z poloviny): kód botů a sady scénářů je napsaný,
  ještě neběžel. Zbývá samotest, zkušební běhy, golden + run_fast. Postup v `progress/M3-G.md`.
- **Kontrola M3** a v ní 3 nahlášené drobnosti:
  - hádanky: server neposílá údaj pro hodnocení na 2 hvězdy (`hit` v `end.puzzle`), takže se místo hodnocení zobrazí „nejisté“,
  - hádanka p01 ukazuje špatné životy trůnu (500/3000), protože `ui.js` bere stejné maximum pro oba trůny,
  - nadpis konce hry říká „Porážka / Vítězství“ i u Přežití a hádanek.

### M4 – Meta v klientovi
- **M4-A** obrazovka Statistiky, Síň slávy, grafy na konci zápasu, úvodní „VS“ obrazovka.
- **M4-B** kosmetika: koruny, praporce, varianty kamene a efekty vítězství.
- **M4-C** nastavení se 4 záložkami, test zvuku, přístupnost.
- **M4-E** skript na vydání (kontrola verzí, hledání tajných údajů, zip bez .exe).
- Kontrola M4.

### M5 – Vydání
- **M5-A** vyvážení frakcí podle simulací (každá dvojice frakcí 40–60 % výher).
- **M5-B** doladění AI, map a Přežití.
- **M5-C** celková kontrola (fuzz, výkon, kontrolní seznam pro LAN).
- **M5-D** česká dokumentace (README, DESIGN, řádek v Games/README).
- **M5-E** verze 1.0 a zip. Zveřejnění až po souhlasu uživatele.
- Kontrola M5.

### Otevřené body z dřívějška
- Výkon v demu během zatmění (kandidát na M4/M5), ověřit plynulost na PC bez grafické akcelerace.
- `meta.xp_gain` po vzdání (`quit`).
- Zvuky zatím nikdo neposlouchal.

## Odhad
- Zbývá zhruba **10–15 hodin práce agentů**: M3-G a kontrola M3 asi 2–3 h, M4 asi 3 h, M5 asi 5–8 h.
  Nejdražší je vyvážení frakcí, simulace běží dlouho.
- Při dosavadním tempu (limit se vyčerpá zhruba po 2–2,5 mil. tokenů agentů) to jsou asi **3–4 okna limitu**,
  tedy realisticky **2–4 dny** podle toho, jak často se bude pokračovat.

## Jak pokračovat
1. Napsat „pokračuj na 1.0“.
2. Pustí se M3-G (naváže podle `progress/M3-G.md`), pak kontrola M3 včetně 3 drobností výše.
3. Potom M4 a M5 skriptem `C:\!Data\!AI\!Code\.claude\workflows\hmk-milestones.js` (balíky a modely v SPEC §6).

Hratelná verze pro mezitím: 0.5 v `%TEMP%\hmk\release05_snapshot` (`Spustit server.bat` v té složce).
Složka hry je teď rozpracovaná 0.9 a nemusí být úplně hratelná.
