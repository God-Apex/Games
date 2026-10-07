// Ručně zadaná reálná data: Sluneční soustava, známé exoplanety, neutronové hvězdy,
// černé díry, vzdálení veleobři mimo katalog HYG a blízké galaxie.
// Souřadnice: ra/dec ve stupních (J2000) + vzdálenost v pc, nebo galaktické l/b.
// Hodnoty k roku 2026 (Wikipedia, NASA, literatura); u veleobrů nejistota desítky procent.
'use strict';

// Ložiska: fe železo, cu měď, si křemík, ti titan, ice led, h2 vodík, he3 helium-3 (číslo = bohatost)
// a: planety v AU, měsíce v km. R v km. P v dnech. mag = síla magnetosféry (Jupiter = 1).
const SOLAR_SYSTEM = [
  { id: 'mercury', n: ['Merkur', 'Mercury'], type: 'rocky', a: 0.387, R: 2439.7, P: 87.97, col: [0.62, 0.58, 0.55], dep: { fe: 1.6, ti: 0.8, si: 0.6 } },
  { id: 'venus', n: ['Venuše', 'Venus'], type: 'rocky', a: 0.723, R: 6051.8, P: 224.7, col: [0.93, 0.84, 0.62], atm: [1, 0.9, 0.6], dep: { si: 0.8, cu: 0.4 } },
  { id: 'earth', n: ['Země', 'Earth'], type: 'rocky', a: 1.0, R: 6371, P: 365.256, col: [0.22, 0.42, 0.78], atm: [0.45, 0.65, 1], dep: { fe: 0.5, cu: 0.5, si: 0.5, ice: 0.4 }, home: true, mag: 0.01,
    moons: [{ id: 'moon', n: ['Měsíc', 'Moon'], a: 384400, R: 1737.4, P: 27.32, col: [0.6, 0.6, 0.6], dep: { si: 1.0, ti: 1.2, fe: 0.6, he3: 0.3 } }] },
  { id: 'mars', n: ['Mars', 'Mars'], type: 'rocky', a: 1.524, R: 3389.5, P: 687.0, col: [0.8, 0.42, 0.26], atm: [1, 0.7, 0.5], dep: { fe: 1.2, ice: 0.6, si: 0.8, cu: 0.3 } },
  { id: 'belt', n: ['Hlavní pás asteroidů', 'Main asteroid belt'], type: 'belt', a: 2.7, a0: 2.2, a1: 3.3, R: 0, P: 1630, col: [0.55, 0.5, 0.45], dep: { fe: 2.0, cu: 1.2, ti: 1.0, ice: 0.5 } },
  { id: 'ceres', n: ['Ceres', 'Ceres'], type: 'dwarf', a: 2.77, R: 469.7, P: 1680, col: [0.5, 0.5, 0.5], dep: { ice: 1.2, cu: 0.4 } },
  { id: 'jupiter', n: ['Jupiter', 'Jupiter'], type: 'gas', a: 5.203, R: 69911, P: 4332.6, col: [0.85, 0.72, 0.55], bands: 1, dep: { h2: 2.0, he3: 0.6 }, mag: 1.0,
    moons: [
      { id: 'io', n: ['Io', 'Io'], a: 421700, R: 1821.6, P: 1.769, col: [0.95, 0.85, 0.4], dep: { cu: 0.8, fe: 0.8 } },
      { id: 'europa', n: ['Europa', 'Europa'], a: 671034, R: 1560.8, P: 3.551, col: [0.86, 0.8, 0.7], dep: { ice: 2.0 } },
      { id: 'ganymede', n: ['Ganymedes', 'Ganymede'], a: 1070412, R: 2634.1, P: 7.155, col: [0.6, 0.57, 0.52], dep: { ice: 1.4, fe: 0.4 } },
      { id: 'callisto', n: ['Callisto', 'Callisto'], a: 1882709, R: 2410.3, P: 16.69, col: [0.45, 0.42, 0.38], dep: { ice: 1.2, si: 0.4 } }] },
  { id: 'saturn', n: ['Saturn', 'Saturn'], type: 'gas', a: 9.537, R: 58232, P: 10759, col: [0.9, 0.8, 0.6], bands: 1, rings: [74500, 140220], dep: { h2: 1.8, he3: 0.5 }, mag: 0.1,
    moons: [{ id: 'titan', n: ['Titan', 'Titan'], a: 1221870, R: 2574.7, P: 15.95, col: [0.9, 0.65, 0.3], atm: [1, 0.7, 0.3], dep: { ice: 1.0, h2: 0.6 } }] },
  { id: 'uranus', n: ['Uran', 'Uranus'], type: 'gas', a: 19.19, R: 25362, P: 30687, col: [0.62, 0.86, 0.9], dep: { h2: 1.0, he3: 0.8, ice: 1.0 }, mag: 0.03 },
  { id: 'neptune', n: ['Neptun', 'Neptune'], type: 'gas', a: 30.07, R: 24622, P: 60190, col: [0.3, 0.45, 0.95], dep: { h2: 1.0, he3: 0.9, ice: 1.0 }, mag: 0.03,
    moons: [{ id: 'triton', n: ['Triton', 'Triton'], a: 354759, R: 1353.4, P: -5.877, col: [0.8, 0.76, 0.75], dep: { ice: 1.4 } }] },
  { id: 'pluto', n: ['Pluto', 'Pluto'], type: 'dwarf', a: 39.48, R: 1188.3, P: 90560, col: [0.8, 0.7, 0.6], dep: { ice: 1.5 } },
];

// Známé exoplanety u hvězd z katalogu (klíč = jméno hvězdy v katalogu). Rp v poloměrech Země (odhad).
const KNOWN_EXOPLANETS = {
  'Proxima Centauri': [
    { n: 'Proxima d', a: 0.02885, P: 5.12, Rp: 0.81, type: 'rocky' },
    { n: 'Proxima b', a: 0.04857, P: 11.19, Rp: 1.07, type: 'rocky' }],
  'Ran': [ // Epsilon Eridani
    { n: 'AEgir (ε Eri b)', a: 3.48, P: 2692, Rp: 11.2, type: 'gas' }],
  "Barnard's Star": [
    { n: 'Barnard b', a: 0.0229, P: 3.15, Rp: 0.6, type: 'rocky' },
    { n: 'Barnard c', a: 0.0274, P: 4.12, Rp: 0.65, type: 'rocky' },
    { n: 'Barnard d', a: 0.0188, P: 2.34, Rp: 0.55, type: 'rocky' },
    { n: 'Barnard e', a: 0.038, P: 6.74, Rp: 0.5, type: 'rocky' }],
};

// Exotické a vzdálené objekty. kind: ns (neutronová hvězda), bh (černá díra), star (hvězda mimo HYG)
// ns: P perioda rotace [s], Lsd výkon ze zpomalování rotace [W], B magnetar
// bh: M hmotnost [M_sun], disk = aktivní akreční disk, comp = průvodce {R, T, a [AU]}
const EXOTIC = [
  { kind: 'bh', name: 'Sagittarius A*', l: 359.944, b: -0.046, d: 8178, M: 4.3e6, disk: 0.3, core: true,
    note: ['Supermasivní černá díra ve středu Galaxie', 'Supermassive black hole at the Galactic Centre'] },
  { kind: 'bh', name: 'Gaia BH1', ra: 262.171, dec: -0.581, d: 480, M: 9.62, comp: { R: 1.0, T: 5850, a: 1.4 },
    note: ['Nejbližší známá černá díra, spící', 'Nearest known black hole, dormant'] },
  { kind: 'bh', name: 'Gaia BH2', ra: 207.570, dec: -59.239, d: 1160, M: 8.94, comp: { R: 7.8, T: 4600, a: 4.96 },
    note: ['Spící černá díra s rudým obrem', 'Dormant black hole with a red giant'] },
  { kind: 'bh', name: 'Gaia BH3', ra: 294.829, dec: 14.932, d: 590, M: 32.7, comp: { R: 4.9, T: 5200, a: 16 },
    note: ['Nejhmotnější hvězdná černá díra v Galaxii', 'Most massive stellar black hole in the Galaxy'] },
  { kind: 'bh', name: 'Cygnus X-1', ra: 299.590, dec: 35.202, d: 2220, M: 21.2, disk: 1, comp: { R: 22, T: 31000, a: 0.2 },
    note: ['První potvrzená černá díra, aktivní akreční disk', 'First confirmed black hole, active accretion disk'] },
  { kind: 'bh', name: 'V404 Cygni', ra: 306.016, dec: 33.867, d: 2390, M: 9.0, disk: 0.6, comp: { R: 6, T: 4300, a: 0.15 },
    note: ['Rentgenová dvojhvězda s výbuchy', 'X-ray binary with outbursts'] },
  { kind: 'bh', name: 'A0620-00', ra: 95.685, dec: -0.346, d: 1060, M: 6.6, disk: 0.3, comp: { R: 1.0, T: 4400, a: 0.02 },
    note: ['Jedna z nejbližších rentgenových dvojhvězd', 'One of the nearest X-ray binaries'] },

  { kind: 'ns', name: 'RX J1856.5−3754', ra: 284.146, dec: -37.910, d: 123, P: 7.06, Lsd: 3e24, T: 434000,
    note: ['Nejbližší známá izolovaná neutronová hvězda', 'Nearest known isolated neutron star'] },
  { kind: 'ns', name: 'Vela Pulsar', ra: 128.836, dec: -45.176, d: 287, P: 0.0893, Lsd: 6.9e29, nebula: [0.5, 0.6, 1],
    note: ['Pulsar v pozůstatku supernovy Vela', 'Pulsar in the Vela supernova remnant'] },
  { kind: 'ns', name: 'Geminga', ra: 98.476, dec: 17.770, d: 250, P: 0.237, Lsd: 3.3e27,
    note: ['Radiově tichý gama pulsar', 'Radio-quiet gamma-ray pulsar'] },
  { kind: 'ns', name: 'PSR J0437−4715', ra: 69.316, dec: -47.253, d: 156.8, P: 0.005757, Lsd: 1.2e27, comp: { R: 0.013, T: 4000, a: 0.04, wd: 1 },
    note: ['Nejbližší milisekundový pulsar, s bílým trpaslíkem', 'Nearest millisecond pulsar, with a white dwarf'] },
  { kind: 'ns', name: 'PSR B1919+21', ra: 290.437, dec: 21.884, d: 300, P: 1.3373, Lsd: 2.2e23,
    note: ['První objevený pulsar (1967, J. Bell Burnell)', 'First pulsar discovered (1967, J. Bell Burnell)'] },
  { kind: 'ns', name: 'PSR B1257+12', ra: 195.015, dec: 12.682, d: 710, P: 0.00622, Lsd: 2e27,
    planets: [{ n: 'Draugr', a: 0.19, P: 25.3, Rp: 0.3, type: 'rocky' }, { n: 'Poltergeist', a: 0.36, P: 66.5, Rp: 1.5, type: 'rocky' }, { n: 'Phobetor', a: 0.46, P: 98.2, Rp: 1.5, type: 'rocky' }],
    note: ['První objevené exoplanety (1992) obíhají pulsar', 'First exoplanets ever found (1992) orbit this pulsar'] },
  { kind: 'ns', name: 'Crab Pulsar', ra: 83.633, dec: 22.015, d: 2000, P: 0.0335, Lsd: 4.5e31, nebula: [1, 0.55, 0.4],
    note: ['Pozůstatek supernovy z roku 1054', 'Remnant of the supernova of 1054'] },
  { kind: 'ns', name: 'SGR 1806−20', ra: 272.164, dec: -20.411, d: 8700, P: 7.6, Lsd: 4e27, magnetar: 1,
    note: ['Magnetar, nejsilnější magnetické pole ve vesmíru', 'Magnetar, strongest magnetic field known'] },

  { kind: 'star', name: 'UY Scuti', ra: 276.902, dec: -12.466, d: 1500, R: 909, T: 3365, L: 95000,
    note: ['Rudý veleobr (Healy et al. 2023)', 'Red supergiant (Healy et al. 2023)'] },
  { kind: 'star', name: 'NML Cygni', ra: 311.606, dec: 40.116, d: 1610, R: 1640, T: 3834, L: 270000,
    note: ['Rudý hyperobr', 'Red hypergiant'] },
  { kind: 'star', name: 'Stephenson 2-18', ra: 279.760, dec: -6.086, d: 5800, R: 2150, T: 3200, L: 437000,
    note: ['Možná největší známá hvězda (velmi nejisté)', 'Possibly the largest known star (very uncertain)'] },
  { kind: 'star', name: 'Eta Carinae', ra: 161.265, dec: -59.685, d: 2300, R: 240, T: 15000, L: 2.6e6,
    note: ['Svítivá modrá proměnná, kandidát na supernovu', 'Luminous blue variable, supernova candidate'] },
  { kind: 'star', name: 'R136a1', l: 279.47, b: -31.67, d: 49970, R: 42.7, T: 46000, L: 4.7e6,
    note: ['Nejhmotnější známá hvězda (Velký Magellanův oblak)', 'Most massive known star (Large Magellanic Cloud)'] },
];

// Galaxie: l, b, d [kpc], průměr D [kpc], typ, sklon disku incl [°], natočení rot [°]
const GALAXIES = [
  { name: ['Velký Magellanův oblak', 'Large Magellanic Cloud'], l: 280.47, b: -32.89, d: 50, D: 9.9, type: 'irr', incl: 35, rot: 20 },
  { name: ['Malý Magellanův oblak', 'Small Magellanic Cloud'], l: 302.80, b: -44.30, d: 62, D: 5.8, type: 'irr', incl: 50, rot: 70 },
  { name: ['Galaxie v Andromedě (M31)', 'Andromeda Galaxy (M31)'], l: 121.17, b: -21.57, d: 765, D: 46.6, type: 'spiral', incl: 77, rot: 38, arms: 2 },
  { name: ['Galaxie v Trojúhelníku (M33)', 'Triangulum Galaxy (M33)'], l: 133.61, b: -31.33, d: 840, D: 18.7, type: 'spiral', incl: 55, rot: 23, arms: 2 },
  { name: ['M81 (Bodeho galaxie)', "M81 (Bode's Galaxy)"], l: 142.09, b: 40.90, d: 3600, D: 27, type: 'spiral', incl: 59, rot: 157, arms: 2 },
  { name: ['Centaurus A', 'Centaurus A'], l: 309.52, b: 19.42, d: 3800, D: 18, type: 'ell', incl: 30, rot: 10 },
  { name: ['M87 (Panna A)', 'M87 (Virgo A)'], l: 283.78, b: 74.49, d: 16400, D: 40, type: 'ell', incl: 10, rot: 0, bh: 6.5e9 },
];
