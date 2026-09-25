# APEX Kasino

Budovatelská hra pro Windows: z malé herny v Litvínovicích postav kasino s pěti hvězdami.
Neoficiální firemní hra, napsaná v C# (WinForms), bez externích knihoven a bez instalace.

## Spuštění
1. Spusť `build.cmd`. Použije kompilátor `csc.exe`, který je součástí .NET Frameworku 4 ve Windows 10/11, a vytvoří `APEX Kasino.exe`.
2. Dvakrát klikni na `APEX Kasino.exe`.

Při prvním spuštění může Windows SmartScreen ukázat varování: *Další informace → Přesto spustit*.
Uložená hra: `%APPDATA%\APEX Kasino\save.txt` (automaticky každý den v 6:00 a při zavření).

## Jak se hraje
- **Stavět**: automaty, stoly, služby a dekorace. Před automatem nech volné pole, tam sedí hráč.
- **Personál**: technik opravuje stroje, uklízeč sbírá odpadky, ochranka chytá podvodníky.
- **Vylepšení**: rozšíření sálu, nové patro, reklamní kampaň, Clover Link jackpot a další.
- **Finance**: příjmy a výdaje za den, graf provozního zisku za 10 dní.
- **Cíle**: co chybí na další hvězdu a 18 cílů s odměnami.
- **Vedení**: čtyři manažeři, kteří za tebe najímají, staví, investují a rozhodují o událostech. Celý tým znamená **režim CEO**: kasino se řídí samo.

Od 2 hvězd jde otevřít 1. patro, od 4 hvězd 2. patro. Patra propojuje eskalátor vpravo od vchodu.
Hosté mají peníze, náladu, žízeň, potřebu toalety a energii. Kliknutím na hosta uvidíš, co si myslí.
Občas přijde událost (firemní večírek APEX, výpadek proudu, hygienická kontrola, slavný host…) a hra čeká na tvoje rozhodnutí.

### Ovládání
| Klávesa | Akce |
|---|---|
| levé / pravé tlačítko | stavět, vybrat / zrušit nástroj |
| R | otočit o 90° (při stavění i postavenou věc) |
| přetažení myší, V | přesunout postavenou věc (zdarma) |
| X, Delete | prodej (vrací 50 %) |
| N | mapa nálady |
| PageUp / PageDown | přepnout patro |
| B / P / U / F / C / L | záložky Stavět / Personál / Vylepšení / Finance / Cíle / Vedení |
| mezerník, 1–3 | pauza, rychlost 1× / 2× / 4× |
| F5 / F9 | uložit / načíst |
| M | zvuk |
| Esc | menu |

---

## Pro vývojáře

### Struktura
Celá hra je jedna třída `GameForm` rozdělená do `partial` souborů podle oblasti:

| Soubor | Obsah |
|---|---|
| `src/GameForm.cs` | vstupní bod (`Program.Main`), okno, herní smyčka (časovač 15 ms), myš a klávesnice, obrazovky (úvod, hra, menu, nápověda) |
| `src/Data.cs` | datové třídy a **katalog objektů** (`Catalog`): cena, údržba, sázka, výhoda kasina, poruchovost, místa pro hosty |
| `src/Sim.cs` | simulace: čas a dny, příchody hostů a jejich rozhodování, hraní a výplaty, personál, hledání cest, stavění, hvězdy, cíle, ukládání |
| `src/Team.cs` | režim CEO: provozní ředitel, architekt, finanční ředitel a manažer událostí |
| `src/Events.cs` | náhodné události s volbou a jejich dočasné efekty |
| `src/Ui.cs` | horní lišta, pravý panel se záložkami, spodní info panel, překryvy, menu a nápověda |
| `src/Draw.cs` | vykreslení sálu, objektů, hostů a personálu, škálování na velikost okna |
| `src/Art.cs` | paleta barev `Pal`, kreslicí pomůcky a vektorová grafika všech automatů a stolů |
| `src/Sound.cs` | krátké zvuky syntetizované do WAV v paměti (`SoundPlayer`) |

### Jak to funguje
- **Souřadnice:** logická plocha 1280 × 760 px, mřížka sálu 28 × 18 polí po 32 px. Okno se škáluje podle DPI a velikosti obrazovky.
- **Čas:** 1 s reálně = 8 herních minut při rychlosti 1× (`MinPerSec`). Rychlost 2× a 4× volá `Step()` vícekrát za snímek. Den se uzavírá v 6:00.
- **Patra:** každé patro (`Floor`) má vlastní mřížku obsazenosti, objekty a odpadky. `CF` je patro, se kterým simulace právě pracuje. Před zpracováním hosta nebo personálu se přepne na jeho patro.
- **Cesty:** BFS z pozice agenta (`Flood`, `PathTo`). `Validate()` před postavením ověří, že se nezablokuje vchod, eskalátor ani přístup k místům jiných objektů.
- **Hosté:** rozhodování v `Decide()` má pevné pořadí priorit: odchod (únava, nuda, dlouhá návštěva) → toaleta → bar → pohovka → bankomat nebo odchod bez peněz → hra. Automat vybírají podle atraktivity, vzdálenosti a sázky. VIP preferují vysoké sázky.
- **Ekonomika:** každá hra má výhodu kasina (`Edge`). U automatů se výplata dopočítá tak, aby dlouhodobě seděla na `1 − Edge` (`PlayRound`). S vylepšením Clover Link se 2 % sázek sypou do progresivního jackpotu.
- **Hodnocení:** počet hvězd je minimum ze spokojenosti odcházejících hostů (klouzavý průměr) a z požadavků na vybavení (`StarReqs`: místa u her, bar, toalety, stoly, dekorace…).
- **Režim CEO:** každých 30 herních minut (`TeamTick`) manažeři zkontrolují stav. Nikdy neutratí pod rezervu (větší z nastavené částky a 1,5 denních nákladů). Architekt staví do vzoru „řady zády k sobě, ulička každý 4. řádek a 7. sloupec“ (`FindSpot`).
- **Uložení:** textový soubor, jeden řádek na záznam (`G` hra, `L` patro, `O` objekt, `S` personál, `U` vylepšení, `M` tým, `E` efekty, `D`/`T` denní statistiky). Hlavička `APEXKASINO 2`; načítání umí převést i verzi 1.

### Jak přidat nový automat
1. V `Data.cs` přidej v konstruktoru `Catalog` nový `Add(...)`: id, název, kategorie, rozměry, cena, údržba, atraktivita, potřebné hvězdy, popis. Pak nastav `Bet`, `Edge`, `Break` a `Seats`.
2. V `Art.cs` doplň jeho grafiku do `DrawArt()`. Pokud má obrazovky s válci, i do výpočtu obrazovek v `Draw.cs` (`DrawDyn`).
3. Spusť `build.cmd`.

### Sestavení ručně
```
%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /optimize+ /win32icon:src\apex.ico /out:"APEX Kasino.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll src\*.cs
```
