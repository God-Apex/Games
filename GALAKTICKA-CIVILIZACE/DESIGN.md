# GALAKTICKÁ CIVILIZACE: návrh hry

Budovatelská strategie ve vesmíru. Hráč těží suroviny, vyrábí komponenty, staví Dysonovy roje a sféry
a přes červí díry se šíří k dalším hvězdám. Inspirace: Dyson Sphere Program, ale ve 2D.
Hlavní dojem má být **nekonečnost a prázdnota vesmíru** v **reálném měřítku**.

## Technologie
- HTML + JavaScript, vykreslování přes WebGL2 (HDR, bloom, aditivní záře, procedurální shadery), popisky a dráhy na 2D canvasu.
- Bez instalace: hra se otevře v prohlížeči (`index.html`), později půjde i přes GitHub Pages.
- Ukládání hry do `localStorage` (export/import do souboru je v plánu).

## Měřítko a vizuál (hlavní pilíř)
- **Plynulý zoom přes ~15 řádů**: od stavby (km) přes planetu, soustavu (AU) až po mezihvězdný prostor (světelné roky).
- Všechno v **reálných proporcích**. Planety jsou při pohledu na soustavu jen tečky, mezi hvězdami je
  skutečná prázdnota. Aby se hráč neztratil, ukazují polohu objektů ikony a popisky; samotné tělesa se nezvětšují.
- Hvězdy mají reálný poloměr, barvu podle teploty (černé těleso) a svítivost. Například Betelgeuse
  vedle Slunce je vidět jako obří koule.
- Pozadí tvoří paralaxní vrstvy hvězd, mlhoviny a vzdálené galaxie generované šumem. Celé je nekonečné
  a pokaždé stejné díky seedu.
- Nekonečnost: kolem domova jsou reálné hvězdy z katalogu, dál navazuje procedurálně generovaná galaxie
  (bez konce).

## Data hvězd
- Zdroj: katalog **HYG** (astronexus, licence CC BY-SA 4.0, nutné uvést autora). Obsahuje polohy, magnitudy,
  spektrální třídy a barevný index.
- Poloměr hvězdy se dopočítá ze svítivosti a teploty (Stefan–Boltzmann: L = 4πR²σT⁴). Pro známé hvězdy
  (Betelgeuse, Antares, VY CMa, Rigel, Sirius…) se použijí ručně ověřené hodnoty.
- Exotické objekty: neutronové hvězdy a pulsary (Krabí pulsar, Vela), magnetary, černé díry (Cygnus X-1,
  Gaia BH1, Sgr A* jako konečný cíl ve středu galaxie). Kde reálná data chybí, doplní se procedurálně.
- Předzpracování: Python skript vytvoří kompaktní `stars.json` (jen potřebná pole).

## Herní smyčka
1. **Těžba**: na planetách, měsících a asteroidech (železo, křemík, titan, vodík, helium-3, vzácné kovy, led).
2. **Výroba**: suroviny → komponenty (plechy, procesory, solární plachty, supravodiče…) → stavby.
3. **Energie**: od solárních panelů přes Dysonův roj (jednotlivé satelity na oběžné dráze) k Dysonově sféře.
   Výnos závisí na reálné svítivosti hvězdy, takže velká hvězda je cennější, ale stavba stojí víc materiálu.
4. **Antihmota** (viz níže) slouží k otevírání červích děr.
5. **Expanze**: nová soustava → nové suroviny a exotické objekty.

## Antihmota: jak ji získat (od snadného po extrémní)
| Úroveň | Zdroj | Reálný základ | Herní mechanika |
|--------|-------|---------------|-----------------|
| 1 | **Urychlovač částic** | CERN vyrábí antiprotony, ale účinnost je cca 10⁻⁹ | Pohltí obrovské množství energie, a proto potřebuješ Dysonovu sféru |
| 2 | **Magnetosférický sběrač** | Van Allenovy pásy zachycují antiprotony (měření sondy PAMELA) | Orbitální sběrače u plynných obrů se silným magnetickým polem, pomalý a stálý zdroj |
| 3 | **Sběrač u pulsaru / magnetaru** | Magnetosféry neutronových hvězd tvoří páry elektron–pozitron | Vysoký výnos, ale radiace ničí stavby, takže je potřeba stínění |
| 4 | **Akreční disk černé díry** | Výtrysky a disky tvoří pozitrony (čára 511 keV ze středu galaxie) | Endgame zdroj s nebezpečím pádu za horizont událostí |

- **Skladování**: Penningovy pasti potřebují nepřetržitý přísun energie. Když dojde energie, antihmota
  anihiluje a zničí okolí. To vytváří napětí a důvod mít energetické zálohy.

## Červí díry
- Otevření a stabilizace stojí antihmotu. Cena roste se vzdáleností.
- Brána musí stát na obou koncích. Do první soustavy se proto letí pomalou sondou (desítky let herního
  času se urychlí), která tam postaví protější bránu. Tak bude vidět, jak je vesmír obrovský a prázdný.

## Ekonomika (verze 0.1)
- Všechny soustavy propojené červími děrami sdílejí jeden sklad. Energie se nepřenáší, každá soustava má vlastní síť.
- Plachta roje zachytí 1/100 000 svítivosti Slunce a postupně zaniká (poločas 20 let). Uzel sféry zachytí 1/10 000 a je trvalý.
  Velká hvězda tedy pojme víc staveb: Proxima je plná po 155 plachtách, Betelgeuse prakticky nikdy.
- Červí díra stojí 10 g antihmoty na světelný rok.
- Výpadek energie v pastech: antihmota uniká a anihilace ničí stavby.

## Stav
Viz [TODO.md](TODO.md).
