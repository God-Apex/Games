# Hra mrtvých králů

Temná PvP strategie 1v1 po LAN v prohlížeči, ve stylu iluminované krypty. Kombinuje tower defense, šachové figury
jako jednotky, zombie z neutrální Mlhy, mlhu války, sbírání beden a souboj dvou mrtvých králů. **Verze 0.5 „Krypta“ (alfa).**

## Spuštění
1. Jeden hráč spustí **`Spustit server.bat`** (potřeba Python 3.8+, nic dalšího). Otevře se prohlížeč.
2. Druhý hráč na stejné síti otevře adresu, kterou server vypíše (např. `http://192.168.1.20:8095`).
3. V lobby zvolte režim (**Král** nebo **Stratég**), složte si balíček 8 karet a oba klikněte na **Jsem připraven**.

Pro vyzkoušení na jednom PC stačí otevřít `http://localhost:8095` ve dvou oknech.
Jiný port: `python server.py 8096`.

## Jak se hraje
- Znič soupeřův **Trůn** (svůj máš vždy vlevo), nebo mu dej **šach-mat**.
- Stavíš a nasazuješ jen na své polovině. Uprostřed je **Mlha**, odkud lezou zombie na oba hráče. Od poloviny zápasu se rozšiřuje.
- Soupeře vidíš jen průzkumem. **Věže střílí jen tam, kam vidíš.**
- Ve 4., 7. a 10. minutě přijde **Zatmění**: 25 s tmy, věže vidí jen 1,5 pole. Ohlásí se 15 s předem.
- Do Mlhy padají **zásobovací bedny** (první ve 40. s). Sebrat bednu trvá 3 s; když u ní stojí oba hráči, je **sporná**
  a nikdo ji nesebere, dokud druhého nevyžene (Stratég sestřelí soupeřův dron Odstřelem).
- Od 2. minuty je uprostřed Mlhy **Relikvie**: kdo ji 5 s drží jen svými jednotkami nebo Králem, dostává +2 ⚡/s a každých 40 s 🧪.
- Za **🧪 Vzorky** se vyzkoumávají technologie a přicházejí **Doby** se silnějšími kartami.
- Pěšák u soupeřova trůnu se **promění v Dámu** (když žádnou nemáš), jednotka se 3 zářezy se stane **veteránem**.
- Délka zápasu je náhodná 10–15 min, pak přijde **Poslední noc**: tma, Mlha každých 20 s pohltí další sloupec a trůny ztrácejí životy.
  Padnou-li oba trůny naráz, vyhraje ten, kdo nadělal víc škody.
- Nová hra? Nech zapnuté **Rady pro nové hráče**: ve hře tě provede checklist prvních kroků a rady podle situace.

| | Král | Stratég |
|---|---|---|
| Postava | Král (WASD), střílí sám | žádná |
| Reakce | Mezerník = blok, včas odrazí střelu; Shift = výpad | Q oprava, W odstřel (cíl i posvítí), E sběrný dron, R štít trůnu, G Útok! |
| Opravy | F u stavby (stojí šrot) | Q |
| Speciál | Q = válečný pokřik, když je nabitý | G = Útok! (jednotky 6 s odolnější a rychlejší) |
| Šach | když je Král mrtvý | když se Odstřel i Štít obnovují |

Ostatní klávesy: **1–0** karty z lišty, **T** tlupa, **V** výzkum, **U** vylepšit (na úrovni 2 **U** a pak **A** nebo **B**),
**X** prodat, **C** přetavit 30 ⚡ na 10 🔩 (od Doby II), **M** zvuk, **Esc** zrušit, **H** nápověda.
Hlasitost a efekty (otřesy, záblesky, čísla poškození, **Klidné efekty**) nastavíš ikonou reproduktoru vpravo nahoře.

## Co je nového v 0.5 „Krypta“
- **Nový vzhled**: iluminovaná krypta místo neonu. Šachové figury na kotoučích, shrbené zombie, netopýří drony, relikviáře.
  Strana A je kost a lazur, strana B eben se žhavým okrajem (rozlišitelné i v odstínech šedi).
- **Šťáva**: otřesy, zásahy, čísla poškození, padající figury, korunka padlého Krále, hlasatel (ŠACH!, PRVNÍ KREV…), finále zápasu.
  Procedurální zvuky a hudba, která houstne s bojem.
- **Opraveno**: vylepšení na cestu A/B v režimu Král (U a pak A/B funguje i při držení F).
- **Vyvážení**: Odstřelovač od třetího dražší, Obrněnec má Pancíř (−40 % od střel), cesta A/B stojí 25 🔩.
  Dvě řady odstřelovačů už nejsou nedobytné: Zatmění, Útok!, Relikvie a Poslední noc s vítězem.
- **Nové**: Výpad a Válečný pokřik (Král), Útok! (Stratég), Relikvie, sporné bedny, Přetavení, proměna pěšce, veteráni.

## Když se soupeř nemůže připojit
- V lobby je u každého hráče IP adresa. Kdo přijde navíc (třetí okno), čeká ve **frontě** a připojí se, až se místo uvolní.
- Místo drží zapomenuté okno? Hráč ho může tlačítkem **Vyhodit** uvolnit (jen pokud není připravený).
- Stránka se po ztrátě spojení zkouší připojit 10× (asi 20 s), pak čeká na **Připojit znovu**.
- Stránka se vůbec nenačte: povol Python ve Windows Firewallu, nebo příchozí TCP port 8095.

Podrobný návrh a plán dalších verzí: [DESIGN.md](DESIGN.md).
