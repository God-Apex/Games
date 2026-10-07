"""Předzpracování katalogu HYG v4.1 -> js/data-stars.js

Zdroj: HYG Database (astronexus), CC BY-SA 4.0, https://github.com/astronexus/HYG-Database
Spuštění: python data/build_stars.py   (raw CSV musí být v data/raw/hygdata_v41.csv)

Výstup: galaktické souřadnice (pc), teplota (K), poloměr (R_sun), bolometrická svítivost (L_sun).
- Teplota z barevného indexu B-V (Ballesteros 2012).
- Bolometrická korekce podle teploty (Flower 1996, koeficienty Torres 2010).
- Poloměr ze Stefan-Boltzmannova zákona: R = sqrt(L) * (T_sun / T)^2.
- Známé hvězdy mají ručně ověřené hodnoty (OVERRIDES), protože odhad z fotometrie
  u veleobrů a dvojhvězd výrazně ujíždí.
"""
import csv, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "raw", "hygdata_v41.csv")
OUT = os.path.join(HERE, "..", "js", "data-stars.js")
T_SUN = 5772.0

# Rovníkové (J2000) -> galaktické souřadnice
M = [[-0.0548755604, -0.8734370902, -0.4838350155],
     [0.4941094279, -0.4448296300, 0.7469822445],
     [-0.8676661490, -0.1980763734, 0.4559837762]]

# HIP: (poloměr R_sun, teplota K, svítivost L_sun, [vzdálenost pc pokud je v katalogu chybná])
# Hodnoty: literatura / Wikipedia k 2026, u veleobrů jsou nejistoty desítky procent.
OVERRIDES = {
    "32349": (1.711, 9940, 25.4),        # Sirius A
    "30438": (71.0, 7350, 10700),        # Canopus
    "69673": (25.4, 4286, 170),          # Arcturus
    "71683": (1.2234, 5790, 1.519),      # Alpha Centauri A (Rigil Kentaurus)
    "71681": (0.8632, 5260, 0.500),      # Alpha Centauri B (Toliman)
    "70890": (0.1542, 3042, 0.00155),    # Proxima Centauri
    "91262": (2.73, 9602, 40.1),         # Vega (střední poloměr, rychle rotuje)
    "24608": (11.98, 4970, 78.7),        # Capella Aa
    "24436": (78.9, 12100, 120000),      # Rigel
    "37279": (2.048, 6530, 6.93),        # Procyon A
    "27989": (764, 3600, 88000),         # Betelgeuse (Joyce et al. 2020)
    "97649": (1.79, 7670, 10.6),         # Altair
    "21421": (45.1, 3900, 439),          # Aldebaran
    "80763": (680, 3660, 75900),         # Antares
    "65474": (7.47, 25300, 20500),       # Spica A
    "37826": (9.06, 4586, 43),           # Pollux
    "102098": (203, 8525, 196000),       # Deneb
    "11767": (37.5, 6015, 1260),         # Polaris
    "107259": (1260, 3750, 283000, 641), # Mu Cephei (Herschelova granátová hvězda)
    "35793": (1420, 3490, 270000, 1170), # VY Canis Majoris
    "87937": (0.187, 3195, 0.0035),      # Barnardova šipka
}
NAMES_FIX = {"107259": "Mu Cephei", "35793": "VY Canis Majoris"}


def bv_to_temp(bv):
    bv = max(-0.4, min(2.0, bv))
    return 4600.0 * (1.0 / (0.92 * bv + 1.7) + 1.0 / (0.92 * bv + 0.62))


def bolometric_correction(t):
    lt = math.log10(t)
    if lt >= 3.90:
        a = [-0.118115450538963e6, 0.137145973583929e6, -0.636233812100225e5,
             0.147412923562646e5, -0.170587278406872e4, 0.788731721804990e2]
    elif lt >= 3.70:
        a = [-0.370510203809015e5, 0.385672629965804e5, -0.150651486316025e5,
             0.261724637119416e4, -0.170623810323864e3]
    else:
        a = [-0.190537291496456e5, 0.155144866764412e5, -0.421278819301717e4,
             0.381476328422343e3]
    bc = sum(c * lt ** i for i, c in enumerate(a))
    return max(-6.0, min(0.3, bc))


def sig(v, n=3):
    if v == 0:
        return 0
    return float(f"{v:.{n}g}")


def main():
    gx, gy, gz, temp, rad, lum, spect = [], [], [], [], [], [], []
    names = {}
    with open(SRC, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hip = r["hip"]
            ov = OVERRIDES.get(hip)
            dist = float(r["dist"])
            if ov and len(ov) == 4:
                # chybná vzdálenost v katalogu: přepočet z RA/Dec
                ra, dec, dist = float(r["rarad"]), float(r["decrad"]), ov[3]
                x = dist * math.cos(dec) * math.cos(ra)
                y = dist * math.cos(dec) * math.sin(ra)
                z = dist * math.sin(dec)
            else:
                if dist <= 0 and r["proper"] != "Sol":
                    continue
                if dist >= 1000:   # nad 1 kpc je paralaxa Hipparcosu nespolehlivá
                    continue
                x, y, z = float(r["x"]), float(r["y"]), float(r["z"])
            ci = r["ci"]
            if ov:
                R, T, L = ov[0], ov[1], ov[2]
            else:
                if not ci:
                    continue
                T = bv_to_temp(float(ci))
                absmag = float(r["absmag"])
                L = 10 ** (-0.4 * (absmag + bolometric_correction(T) - 4.74))
                R = math.sqrt(L) * (T_SUN / T) ** 2
                if float(ci) >= 1.9 and R > 300:
                    continue   # extrémně červené + obří = zčervenání prachem / chybná data
                R = min(R, 700.0)
            if r["proper"] == "Sol":
                R, T, L = 1.0, 5772, 1.0
            g = [M[i][0] * x + M[i][1] * y + M[i][2] * z for i in range(3)]
            idx = len(gx)
            gx.append(round(g[0], 3)); gy.append(round(g[1], 3)); gz.append(round(g[2], 3))
            temp.append(int(round(T))); rad.append(sig(R)); lum.append(sig(L))
            spect.append((r["spect"] or "")[:3])
            name = NAMES_FIX.get(hip) or r["proper"]
            if not name and r["bayer"] and r["con"]:
                name = f"{r['bayer']} {r['con']}"
            elif not name and r["gl"]:
                name = r["gl"]
            if name:
                names[idx] = name
    data = {"source": "HYG Database v4.1 (astronexus), CC BY-SA 4.0",
            "x": gx, "y": gy, "z": gz, "t": temp, "r": rad, "l": lum, "s": spect,
            "n": names}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// Vygenerováno skriptem data/build_stars.py, needitovat ručně.\n")
        f.write("// Data: HYG Database v4.1 (astronexus), licence CC BY-SA 4.0.\n")
        f.write("window.STAR_DATA=")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"{len(gx)} hvězd, {os.path.getsize(OUT)/1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
