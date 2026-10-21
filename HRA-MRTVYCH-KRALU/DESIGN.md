# HRA MRTVÝCH KRÁLŮ — návrh hry

> PvP 1v1 po LAN v prohlížeči, v reálném čase. Dystopie: z města zbyly ruiny za karanténní zdí.
> Vládnou jim dva **mrtví králové** – vůdci, kteří zemřeli a vstali, ale nepodlehli nákaze.
> Každý brání svůj **Trůn**, mezi nimi leží Mlha plná nakažených.
> Strategie + tower defense + reakce + šachy + Plants vs. Zombies + Fortnite + zombie.

---

## 1. Hlavní myšlenka
Každý hráč brání svůj **Trůn** na vlastní polovině šachovnicového pole. Staví věže a zdi (PvZ / TD),
posílá jednotky s šachovými pohyby přes neutrální **Mlhu** plnou zombie a podle herního režimu
buď přímo ovládá svého **Krále** (reakce), nebo hraje čistě jako **Stratég** přes schopnosti.
Mlha se postupně stahuje jako bouře ve Fortnite.

## 2. Herní smyčka
**Délka zápasu je náhodná: 10–15 minut**, losuje se při každé hře a hráči ji neznají přesně.
Fáze se počítají v procentech zápasu, sirény ohlašují každou změnu.

1. **Příprava (30 s)** – výběr balíčku 8 karet (jednotky, věže, schopnosti), skrytě.
2. **Rozjezd (0–25 %)** – stavba generátorů energie, první obrana.
3. **Střed hry (25–60 %)** – výpady do Mlhy pro loot, posílání zombie vln soupeři, upgrady.
4. **Uzavírání (60–100 %)** – Mlha se zužuje, souboje jsou nucené.
5. **Poslední noc** – když čas vyprší, Mlha zaplaví celé pole, Trůny ztrácejí životy. Vyhrává ten, jehož Trůn vydrží déle.

**Výhra:** zničený soupeřův Trůn, **šach-mat** (viz 9), nebo Poslední noc.

## 3. Mapa
- Mřížka **9 řádků × 16 sloupců** (velikost se doladí).
- Sloupce 1–6: základna hráče A | **7–10: Mlha (neutrální)** | 11–16: základna hráče B.
- 5 **pruhů** (řádků s cestou) jako v PvZ, ostatní řádky jsou terén.
- Terén: *trosky* (blokují, rozeberou se na šrot), *kanál* (rychlejší pohyb), *radiace* (poškozuje), *vyvýšené místo* (dostřel +1).
- Symetrické mapy (Předměstí, Továrna, Metro, Nemocnice).

## 4. Reálný čas
- Vše běží plynule v reálném čase, žádné tahy.
- Jednotky se pohybují **po polích mřížky** podle svého šachového vzoru (viz 8). Každý krok trvá podle rychlosti jednotky, pohyb je animovaný plynule.
- Rychlost rozhodování a reakce rozhodují: kdo dřív postaví, odpálí schopnost nebo uhne.

## 5. Ekonomika
| Surovina | Získání | Použití |
|---|---|---|
| **Energie** ⚡ | generátory (jako slunečnice), pasivně | stavba, jednotky |
| **Šrot** 🔩 | rozebírání trosek, zabité zombie, Mlha | zdi, opravy, upgrady |
| **Vzorky** 🧪 | elitní zombie, zásobovací bedny | výzkum, legendární karty |

- Limit 3 generátorů za základní cenu, další dražší → volba mezi ekonomikou a obranou.
- **Přetížení generátoru**: stisk ve správný moment = dvojnásobný výnos, chyba = výpadek 10 s.

## 6. Obrana (Tower defense / PvZ)
| Věž | Role | Upgrade cesty (A / B) |
|---|---|---|
| **Kulomet** | levné DPS, 1 pruh | A: dvojhlaveň · B: průbojné střely |
| **Plamenomet** | krátký dosah, plošně | A: napalm na zemi · B: kužel na 2 pruhy |
| **Odstřelovač** | dlouhý dosah, pomalý | A: pronikne 3 cíli · B: označí cíl (+25 % poškození) |
| **Tesla cívka** | řetězový zásah | A: víc skoků · B: omráčí |
| **Minové pole** | jednorázové, skryté | A: chemické (zpomalí) · B: EMP (vyřadí stroje) |
| **Rušička** | podpora | A: skryje věže před průzkumem · B: zpomalí nepřátele v okolí |
| **Generátor** | ekonomika | A: vyšší výnos · B: štít pro okolí |
| **Hláska** | výhled | A: větší dohled · B: odhalí neviditelné |

- Každá věž má **3 úrovně** + na úrovni 3 nevratnou volbu **A nebo B**.
- Věže se dají **přesunout** za šrot.

## 7. Stavění (Fortnite)
- Rychlé stavění **zdí, ramp a barikád** ze šrotu, zkratky (Q zeď, E rampa, R barikáda).
- Materiály: **dřevo → plech → beton** (rychlost stavby vs. výdrž).
- Rampa = jednotky přelezou zeď / věž na rampě má dostřel +1.
- **Editace**: do zdi lze udělat střílnu (věž za ní střílí, ale je zranitelnější).

## 8. Jednotky a šachové pohyby
| Jednotka | Šachový vzor | Popis |
|---|---|---|
| **Pěšák** (Odpadlík) | 1 pole vpřed, útočí šikmo | levný, v Mlze se může **povýšit** |
| **Jezdec** (Skokan) | skok do L | přeskakuje zdi a věže |
| **Střelec** (Pašerák) | diagonálně | mění pruhy, krade energii |
| **Věž** (Obrněnec) | rovně, daleko | tank, ničí zdi |
| **Dáma** (Hlídka) | jakýkoli směr | drahá, silná, jen 1 naráz |
| **Medik** | 1 pole libovolně | léčí sousedy |
| **Sabotér** | jako pěšák, neviditelný 3 s | položí nálož na věž |

- **Povýšení**: pěšák, který projde celou Mlhou, si vybere novou podobu.
- **Rošáda**: jednou za hru prohodíš Trůn s jednou budovou.
- **Braní mimochodem**: bonus za zničení jednotky hned po jejím kroku.

## 9. Dva herní režimy ovládání

### Režim KRÁL (reakce)
- Hráč přímo ovládá svého **Mrtvého krále** (WASD + myš), kdekoli na mapě, Mlha je ale riskantní.
- Král střílí, sbírá loot, opravuje, **odrazí střelu** správně načasovaným blokem.
- Padlý Král se vrací za 15 s, mezitím nelze stavět.

### Režim STRATÉG (bez postavy)
- Žádná postava, vše se ovládá klikáním a kartami.
- Místo Krále **Velitelské schopnosti** s cooldownem: oprava, odstřel, dron pro loot, nouzový štít Trůnu.
- Sběr lootu v Mlze dělají jednotky nebo drony.

**Šach-mat** (oba režimy): Trůn je obklíčený ze 3 stran nepřáteli a Král je mrtvý (v režimu Stratég: všechny obranné schopnosti jsou na cooldownu) → upozornění **ŠACH**. Neubráníš-li do 10 s, prohráváš.

## 10. Zombie (neutrální třetí strana)
- Z Mlhy se v pravidelných vlnách šíří zombie **na obě strany**.
- **Infekce**: padlá jednotka může vstát jako zombie (proti oběma).
- **Posílání vln** soupeři: za energii vypustíš vlastní tlupu zombie do jeho poloviny.

| Zombie | Schopnost |
|---|---|
| Chodec | základní, hromadně |
| Běžec | rychlý, slabý |
| Nafouknutý | po smrti toxický oblak |
| Kopáč | jde pod zemí, obchází zdi |
| Křikloun | zrychlí okolní zombie |
| Obr | tank, láme zdi |
| **Alfa** (miniboss) | občas v Mlze, padá z něj legendární loot |

## 11. Mlha války a průzkum
- **Soupeřova polovina je skrytá.** Vidíš jen svou polovinu a to, na co dohlédnou tvé jednotky, věže a Král.
- Průzkum: **Hláska** (věž s dohledem), **Průzkumný dron** (karta), jednotky v Mlze, Jezdec.
- Co jsi jednou viděl, zůstane zašedle zobrazené v posledním známém stavu (může být zastaralé).
- **Rušička** umí skrýt věže i před průzkumem → hra na blafování.

## 12. Mlha a loot (Fortnite)
- **Zásobovací bedny** padají do Mlhy (oznámené 10 s předem) → závod o ně.
- Rarity: ⚪ běžná · 🟢 neobvyklá · 🔵 vzácná · 🟣 epická · 🟡 legendární.
- **Stahování**: v 50 %, 70 % a 85 % zápasu postoupí toxická hranice o 1 sloupec do obou základen. Co tam stojí, chátrá.

## 13. Schopnosti (karty)
| Karta | Efekt |
|---|---|
| Nálet | zasáhne 3×3 pole |
| Výpadek proudu | soupeřovy věže 5 s nestřílí |
| Karanténa | uzavře 1 pruh na 10 s |
| Návnada | zombie míří 15 s na zvolené pole |
| Průzkumný dron | odhalí kus soupeřovy poloviny na 10 s |
| Mobilizace | příští 3 jednotky jsou o 50 % rychlejší |

## 14. Upgrady a progrese
**V zápase**
- Úrovně věží (1→3 + volba A/B).
- **Výzkumný strom** za Vzorky: *Inženýrství* (stavby), *Armáda* (jednotky), *Biotech* (ovládání zombie).
- **Doby** (jako věky): po 2 výzkumech další Doba → silnější karty.

**Mimo zápas (férově)**
- Žádná síla navíc, jen **odemykání karet do balíčku** a **kosmetika** (barvy, vzhled Krále, efekty).
- Statistiky a historie zápasů, žebříček v síti (ELO).

## 15. Herní módy
- **Král** 1v1 – s přímým ovládáním postavy.
- **Stratég** 1v1 – bez postavy, jen schopnosti.
- **Přežití** – oba proti zesilujícím zombie, kdo vydrží déle.
- **Puzzle** – šachové úlohy („obraň Trůn do 30 s“), i pro jednoho hráče.
- **Výcvik** proti AI.

## 16. Frakce (pozdější fáze)
- **Přeživší** – levné stavby, silné zdi.
- **Korporace** – drahé technologie (drony, Tesla).
- **Kult** – ovládají zombie, slabší obrana.

## 17. Vzhled a čitelnost
- Od verze 0.5 **„Iluminovaná krypta“** (viz 0.5 níže); původní neonová dystopie hráče nebavila.
- **Text vždy čitelný**: vysoký kontrast, žádný text přes textury, min. 14 px, žádné svítící písmo.
- Hráč A kost + lazurová modrá, hráč B eben + žhavě oranžová (rozlišitelné i pro barvoslepé a v odstínech šedi), zombie zelenavé.
- Nebezpečí se nikdy neukazuje jen barvou: šrafy, zmenšující se zaměřovač, otřesy.
- Ikony místo textu, kde to jde; tooltipy s čísly.
- Zvuky: zvon a poplach při ŠACHU, Geigerův počítač, když Král stojí v Mlze.

## 18. Technologie
- **Klient**: `index.html` (HTML5 Canvas + JavaScript), bez instalace.
- **Server**: `server.py` (Python 3.8+, jen standardní knihovna, WebSocket), stejně jako Neon Roj.
- **Autoritativní server**: počítá celou hru, klienti posílají jen akce → nejde podvádět a mlhu války nejde obejít (server posílá jen to, co hráč vidí).
- Spuštění: jeden hráč spustí `Spustit server.bat`, druhý otevře `http://IP:port`.

## 19. Plán vývoje
| Fáze | Obsah |
|---|---|
| **0.1 MVP** ✅ | mapa, reálný čas, 3 věže, 3 jednotky, energie, LAN, mlha války, výhra zničením Trůnu, náhodná délka |
| **0.2** ✅ | zombie z Mlhy, šrot, zdi, upgrady věží |
| **0.3** ✅ | režim Král i Stratég, loot, stahování Mlhy, Poslední noc |
| **0.4** ✅ | karty a balíček, výzkum, šach-mat, rady pro nové hráče |
| **0.5 „Krypta“** ✅ | nový vzhled, šťáva a zvuky, oprava vylepšení v režimu Král, vyvážení odstřelovačů, Zatmění, Relikvie, sporné bedny, Výpad, pokřik, Útok!, Přetavení, proměna pěšce |
| **0.6** | další mapy, Přežití, Puzzle, AI pro výcvik, rada/AI pro boj o Relikvii ve Stratégovi |
| **1.0** | frakce, vyvážení, kosmetika, statistiky |

## Jak je to udělané ve verzi 0.4
Kde se hra liší od návrhu výše, platí tohle:
- **Věže střílí jen do viditelných polí** (po testu 0.2 byl Odstřelovač moc silný). Odstřelovač navíc 0,5 s míří laserem.
- **Trůn** je celý zadní sloupec. **Šach** = soupeřovy jednotky stojí u trůnu aspoň ve 3 řadách a hráč se nemůže bránit (Král mrtvý / Odstřel i Štít na cooldownu). Po 10 s **mat**.
- **Král** střílí automaticky na nejbližší viditelný cíl, myš zůstává na stavění. WASD pohyb s klouzáním kolem rohů, mezerník blok (první 0,3 s odrazí střelu věže zpět), F oprava za šrot. Mrtvý Král se vrací za 15 s, mezitím nejde stavět.
- **Stratég** má 4 velitelské schopnosti: Oprava, Odstřel, Sběrný dron, Štít trůnu.
- **Balíček**: Generátor, Zeď a Tlupa jsou vždy k dispozici, k nim 8 karet z 20. Doba II odemyká Teslu, Hlídku, Nálet a Výpadek proudu.
- **Výzkum**: 3 větve × 3 stupně za Vzorky (2/3/4). Doba II po 2 výzkumech, Doba III po 5 (+2 ⚡/s).
- **Bedny** padají do Mlhy asi každou minutu (ohlášené 10 s předem), 5 rarit, epické a legendární obsahují i kartu zdarma. **Alfa** se objeví v 5. minutě a pak každé 4 minuty, padá z ní legendární bedna.
- **Mlha** ubírá jednotkám a Králi pomalu životy. V 50 %, 70 % a 85 % zápasu postoupí o sloupec do obou základen, stavby v ní chátrají.
- **Rady pro nové hráče**: checklist „První kroky“ v panelu a rady podle situace (vypínatelné).
- Zatím chybí: přetížení generátoru, rampy a editace zdí, kanály a radiace, další zombie (Nafouknutý, Kopáč, Křikloun), frakce.

## Verze 0.5 „Krypta“ (15. 10. 2026)
Reakce na první LAN hry: (1) vylepšení na cestu A/B v režimu Král nefungovalo, (2) dvě řady odstřelovačů nešlo prorazit,
(3) hra byla „nudná“, (4) hráči chtěli úplně jiný vzhled.

### Vzhled „Iluminovaná krypta“
- Kamenné dlaždice ve svitu svíček, Mlha jako plující duchové s železnými ploty, mlha války jako rytinová šrafa se zlaceným okrajem.
  Naposledy viděné soupeřovy stavby jsou sépiové skici s „?“ nad mlhou.
- Jednotky jsou šachové figury na kotoučích (Medik = morový doktor, Sabotér v kápi s bombou), zombie shrbené bez kotouče,
  Král se zlatou korunou a pláštěm, drony jsou netopýři, bedny relikviáře (počet cvočků = rarita + 1).
- Strana A kost + lazur + štít s půlměsícem, strana B eben + žár + kulatý znak s plamenem a vlaštovčí prapor; žhavý okraj B je vždy plně vidět.
- UI: tmavá zlacená kůže ve hře, pergamenové folie v lobby, nápovědě, výzkumu a na konci. Písma Cinzel, Alegreya Sans, Grenze Gotisch.
- Vše se kreslí procedurálně (`js/paint.js`), sprity se kešují; žádný `shadowBlur` za běhu.

### Šťáva
- Otřesy (strop 7 px, volba v nastavení), zastavení obrazu při velkých zásazích, záblesky, čísla poškození (strop 48),
  bílý záblesk a postrčení při zásahu, skoky figur po polích, padající a tříštící se figury, Králova koruna odlétá.
- Odraz střely: zmenšující se kruh na Králi, „ODRAŽENO!“ a střela letí zpět. Bedny padají po paprsku, otevírají se s drahokamy.
- Hlasatel v pruhu nad polem (ŠACH!, PRVNÍ KREV, ŘEŽBA, ZATMĚNÍ…), finále: poražený trůn se zhroutí shora dolů.
- Zvuky a hudba jsou procedurální Web Audio (`js/audio.js`): 84 zvuků, hudba ve 4 vrstvách podle napětí, noční varianta,
  tlumení, když je Král mrtvý.
- **Klidné efekty** vypnou otřesy, záblesky a zpomalení (zapnou se samy při `prefers-reduced-motion`). M ztlumí zvuk.

### Vyvážení (důkazy z botích simulací, 20 her na scénář a režim)
- **Odstřelovač** stojí 100, 100, 140, 180 … ⚡ (100 + 40·(n−1)). **Obrněnec** má Pancíř: −40 % od věží, trůnu a Krále.
  **Cesta A/B** stojí 25 🔩 místo 35. Čistá obrana dvěma řadami odstřelovačů dřív často vydržela do 6.–7. minuty
  (útočník vyhrál 13/20 v Králi); teď padne ve 20/20 hrách, v Králi kolem 295 s, ve Stratégovi kolem 189 s.
- **Férovost**: výběr cíle a vlny zombie jsou souměrné; strana B dřív dostávala o 21 % víc kořisti ze zombie, teď 0,95–1,04.
- **Přetavení až od Doby II**: bez omezení měl útočník generátory na úrovni 3 už v 60. s a čistá obrana padla za 175 s.
- **Proměna jen na jednu Dámu** se zachovanými zraněními: dřív spam vytvořil Dámu + 8 Obrněnců na sloupci trůnu
  a porazil smíšenou obranu (2–5/20 her), teď 0/20 v Králi a 1/20 ve Stratégovi.
- **Poslední noc** má vítěze: zrcadlené pasivní obrany dřív skončily remízou 40/40, teď 39/40 rozhodne noc za 64–146 s.

### Nové mechaniky (G2–G9)
- **G2 Zatmění**: ve 240, 420 a 600 s na 25 s, ohlášené 15 s předem. Ve tmě vlastní polovina není vidět, trůn svítí na 2 zadní sloupce,
  stavby vidí nejvýš 1,5 pole (Reflektor 3), jednotky polovinu, Král celý dohled.
- **G3 Poslední noc**: trvalá tma, Mlha každých 20 s +1 sloupec (stupeň 4 → 6), trůny ztrácejí (5 + 0,2·τ) životů/s.
  Padnou-li oba naráz, vyhraje větší škoda na soupeřově trůnu a stavbách za celý zápas.
- **G4 Král**: **Výpad** (Shift) 2,5 pole, 0,3 s nezranitelnost, cooldown 7 s. **Válečný pokřik** (Q): měřák +6 za zabití Králem,
  +20 za odraz, +1/s mimo vlastní polovinu; plný dá na 8 s auru r = 3: jednotky dostávají od věží ×0,4, krok ×0,7, Král střílí 2× rychleji.
- **G5 Stratég**: 5. rozkaz **Útok!** (G, cooldown 70 s): všechny vlastní jednotky 6 s ×0,5 od věží a krok ×0,7.
  Odstřel posvítí 3×3 na 5 s i ve tmě.
- **G6 Relikvie**: sloupce 7–8, řádky 3–5, od 120 s. Obsazení 5 s jen jednou stranou (bez zombie); držitel +2 ⚡/s a 1 🧪 za 40 s.
- **G7 Přetavení** (C): 30 ⚡ → 10 🔩, nejvýš 2× za sekundu, až od Doby II.
- **G8 Sporné bedny**: první bedna ve 40 s (rarita aspoň neobvyklá), další po 50–70 s. Sebrání = 3 s kanálu (jednotka na poli,
  Král do 0,7 pole, vznášející se dron). Jsou-li u bedny obě strany, kanál zamrzne. Dron sestřelí nepřítel blíž než 1,5 pole nebo Odstřel;
  vznášející se dron osvětlí pole bedny (r = 1), aby šel Odstřel použít.
- **G9 Proměna a veteráni**: Pěšák na sloupci soupeřova trůnu se změní v Dámu (jen když strana žádnou nemá, zachová poměr životů).
  Jednotka se 3 zářezy je veterán; soupeřův veterán vynese 15 🔩 místo 6.

### Protokol (pro další práci)
- Klient posílá `{t:'in', mx, my, b, r, d, u}` (d výpad, u pokřik, reagují na náběžnou hranu), `{t:'conv'}`, `{t:'cmd', id:'utok'}` a dřívější akce.
- `defs` navíc: `relic [7,8,3,5]`, `relicFrom 120`, `eclipses`, `eclLen 25`, `conv [30,10,2]` (energie, šrot, potřebná Doba).
- Snapshot navíc: `sp` cena odstřelovače, `ec [fáze, s]` (0 nic, 1 odpočet, 2 zatmění), `dl [škoda A, B]`,
  `rl [držitel, kdo obsazuje, postup 0–1, s do 🧪]`, `kr.ult/ua/dcd`, `mk` (druh zprávy: e odmítnutí, i info, w varování), `ev` (události).
- Řádky: `en[10]` zářezy (jen vlastní), příznak 1024 = pokřik / Útok!; `cr [id, x, y, rarita, dopad, ttl, ch0, ch1, sporná]`;
  `dr [x, y, strana, vznáší se]`; `rv [x, y, s, poloměr]`.
- Nové fx: `p` odraz, `g` blok, `x` smrt (s druhem a zabijákem), `n` postaveno, `u` vylepšeno, `r` prodáno, `D` výpad, `U` pokřik,
  `R` relikvie, `P` proměna.
- Události `ev`: wave, alfa, alfa_dead, horde, fb, streak, kk, kr, ecl_warn, ecl, night, mist, ult, utok, relic_on, relic, promo, crate, contest.
- Klient: `?demo` (volitelně `=noc`, `strateg`, `konec`, počet entit) přehraje ukázkovou scénu bez soupeře (potřebuje běžící server kvůli kartám).

### Známé problémy
- Stratég trestá obránce, který nebojuje o Relikvii: bez boje o střed padne smíšená obrana před nocí ve 12/20 simulacích,
  s 2–3 jednotkami poslanými na Relikvii (a Odstřelem na obsazujícího) jen v 1/20 (Král 3/20). Pravidla se neměnila, jen to
  musí hra hráči říct (rada k Relikvii ve Stratégovi a rada, když ji soupeř drží).
- Čistá obrana odstřelovači padá ve Stratégovi dřív než v Králi (medián asi 3 min proti 5,5 min, kvůli Útoku! a proměně pěšce).
  Původní stížnost byla, že je neporazitelná, proto beze změny. Kdyby to v testech bylo moc rychlé: Útok! až od Doby II.
- Zvuky jsou ověřené jen měřením, ne poslechem.

## Rozhodnuto (13. 10. 2026)
- Král s přímým ovládáním i Stratég → **dva samostatné režimy**.
- **Reálný čas**, žádné tiky.
- Soupeř je vidět **jen s průzkumem**.
- Délka zápasu **náhodně 10–15 min** při každé hře.
- Název: **Hra mrtvých králů**.
