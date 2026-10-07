# Neon Roj

Neonová arkádová střílečka ve stylu „přežij roj“. Létáš lodí uprostřed sílícího roje nepřátel, sbíráš krystaly
a po každé úrovni si vybíráš zbraně a vylepšení. Zbraně se dají vyvinout v silnější verze (například Pulzní
dělo → Hyperpulz, Orbitální čepele → Prstenec smrti). Úlomky z každého běhu odemykají trvalá vylepšení a další lodě.

- **Zbraně:** pulzní dělo, orbitální čepele, řetězový blesk, naváděné rakety, laser, rázová vlna, plazmové miny,
  bumerangový disk, toxické pole, bojové drony a jejich vyvinuté verze
- **Vylepšení:** poškození, přebíjení, dosah, počet projektilů, rychlost, pancíř, léčení, magnet, kritické zásahy…
- **Ovládání:** klávesnice, herní ovladač i dotyk
- Úlomky, úspěchy a lodě se ukládají v prohlížeči

## Hra pro jednoho
Otevři `index.html` v prohlížeči a v menu zvol **Hrát**.

## Co-op v síti (2–4 hráči)
1. Na jednom počítači spusť `Spustit co-op server.bat` (nebo `python server.py`). Stačí Python 3.8+, žádné
   další knihovny.
2. Otevře se prohlížeč s hrou. V menu zvol **Co-op v síti**.
3. Ostatní ve stejné síti otevřou adresu, kterou server vypíše (např. `http://192.168.1.23:8090`), a také zvolí
   **Co-op v síti**.
4. Až jsou všichni připravení, hostitel (kdo se připojil první) spustí let.

Společný roj a úrovně, každý si vybírá vlastní vylepšení a sbírá vlastní truhly. Sestřeleného spoluhráče
oživíš, když k němu přiletíš a chvíli u něj zůstaneš.

**Když se ostatní nemůžou připojit:** Windows se při prvním spuštění zeptá, jestli povolit Python v síti,
povol „Soukromé sítě“. Všichni musí být ve stejné síti. Při obsazeném portu: `python server.py 8091`.

Podrobnosti i v [README.txt](README.txt).
