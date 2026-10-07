# Galaktická civilizace

> **Verze 0.5, alfa, ve vývoji.** Hra je hratelná, ale ekonomika ještě není vyvážená a obsah přibývá.

Budovatelská strategie ve vesmíru ve **skutečném měřítku**. Těž suroviny, vyráběj komponenty, obklop Slunce
Dysonovým rojem a sférou, získávej antihmotu a otevírej červí díry k dalším hvězdám. Cílem je vystoupat po
Kardaševově škále až k civilizaci typu III.

## Spuštění
Otevři `index.html` v prohlížeči (Chrome, Edge nebo Firefox s WebGL2). Nic se neinstaluje.

Pro vývoj (server bez cache): `python data/serve.py`, potom http://localhost:8765

## Co je na hře reálné
- **107 798 skutečných hvězd** z katalogu HYG v4.1 s polohou, teplotou, poloměrem a svítivostí. Ověřené
  hodnoty mají například Betelgeuse (764 R☉), VY Canis Majoris (1 420 R☉) nebo Mu Cephei.
- Hvězdy i planety mají **skutečnou velikost** a vzdálenosti odpovídají realitě. Zoom plynule přechází
  přes 25 řádů, od metrů po hranici pozorovatelného vesmíru.
- Sluneční soustava je reálná včetně měsíců. Ve hře jsou i známé exoplanety (Proxima b, d, Barnardova
  hvězda, ε Eridani b) a planety pulsaru PSR B1257+12.
- **Černé díry**: Sgr A* s hvězdami S2, S62 a S4711, Gaia BH1–3, Cygnus X-1, V404 Cygni, A0620-00.
- **Neutronové hvězdy**: Krabí pulsar s mlhovinou, Vela, Geminga, RX J1856.5−3754 a magnetar SGR 1806−20.
- Mléčná dráha s příčkou a spirálními rameny, kolem ní Magellanova mračna, Andromeda, M33, M81,
  Centaurus A a M87. Dál pokračuje nekonečné procedurální pole galaxií.
- Energie solárních panelů se řídí skutečným tokem záření ve vzdálenosti tělesa od hvězdy. Lety sond
  trvají reálnou dobu a hra ukazuje i dilataci času na palubě.

## Jak začít
Vlevo dole je karta **úkolů**. Každý úkol vysvětlí další krok, tlačítko „Ukaž mi“ tě přenese na správné místo
a za splnění dostaneš suroviny. V záložce **Příručka** najdeš u každé suroviny, kde ji vzít a k čemu slouží.
Hvězdy a planety vyhledáš klávesou `/`. Pro volné hraní zvol při nové hře **Sandbox**.

## Antihmota
| Zdroj | Reálný základ |
|-------|---------------|
| Magnetosférický sběrač (Jupiter) | antiprotony v radiačních pásech (měření sondy PAMELA) |
| Urychlovač částic | účinnost jako v CERNu (10⁻⁹), proto potřebuje energii Dysonova roje |
| Pulsarový sběrač | páry elektron–pozitron v magnetosféře neutronové hvězdy |
| Akreční sběrač | pozitrony z disků a výtrysků černých děr |

Antihmota se skladuje v Penningových pastech. Když jim dojde energie, antihmota anihiluje.

## Ovládání
| | |
|---|---|
| kolečko myši | zoom ke kurzoru |
| tažení | posun |
| klik / dvojklik | výběr / přiletět k objektu |
| mezerník, 1–5 | pauza, rychlost času (1× = 1 herní hodina za sekundu, až 10 000×) |
| H, F, Esc | domů, přiletět k výběru, zrušit výběr |

## Technika
Čisté HTML a JavaScript bez knihoven. WebGL2 vykresluje do HDR bufferu, pak přidá bloom a tónování ACES.
Všechny hvězdy, planety, černé díry a galaxie jsou procedurální shadery.

- `data/build_stars.py`: převod katalogu HYG na `js/data-stars.js`. Surové CSV se necommituje, stáhneš ho
  z https://github.com/astronexus/HYG-Database.
- `js/galaxy.js`: model vesmíru, `js/economy.js`: ekonomika, `js/render.js` + `js/shaders.js`: grafika.
- Návrh hry: [DESIGN.md](DESIGN.md), plán: [TODO.md](TODO.md).

## Licence dat
Data hvězd: [HYG Database](https://github.com/astronexus/HYG-Database) v4.1 (astronexus),
licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Odvozený soubor
`js/data-stars.js` je šířen pod stejnou licencí.
