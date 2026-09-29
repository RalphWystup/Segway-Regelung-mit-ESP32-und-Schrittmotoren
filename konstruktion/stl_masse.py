#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Die STL-Konstruktionsdateien des Mini-Segway (2018, C:\\Sicherungskopien\\Segway_mini\\3_Segway) ausmessen:
Umfang (Bounding-Box), Volumen (Divergenzsatz über die Dreiecke), Oberfläche; daraus die Masse als Bereich
für PLA (1,24 g/cm³): Vollkörper und 25 % Füllung (Hüllen 1,2 mm angenommen). Eigener Leser für binäres STL,
weil numpy-stl/trimesh nicht installiert sind. Ausgabe: stl_masse.json und Tabelle."""
import json, struct, sys
import numpy as np
from pathlib import Path

H = Path(__file__).resolve().parent / "STL"
PLA = 1.24e-3          # g/mm³
HUELLE = 1.2           # mm Wandstärke bei Teildruck (ANNAHME)
FUELLUNG = 0.25        # ANNAHME

def lies(p: Path):
    d = p.read_bytes()
    if d[:5] == b"solid" and b"facet" in d[:300]:
        # ASCII
        v = []
        for z in d.decode("ascii", "replace").splitlines():
            z = z.strip()
            if z.startswith("vertex"):
                v.append([float(x) for x in z.split()[1:4]])
        return np.array(v).reshape(-1, 3, 3)
    n = struct.unpack("<I", d[80:84])[0]
    a = np.frombuffer(d[84:84 + 50 * n], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return a["v"].reshape(-1, 3, 3).astype(float)

def kennwerte(t):
    v0, v1, v2 = t[:, 0], t[:, 1], t[:, 2]
    vol = np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0
    fl = 0.5 * np.sum(np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1))
    lo, hi = t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)
    # Schwerpunkt des Vollkörpers (Divergenzsatz, je Tetraeder gegen den Ursprung)
    tv = np.einsum("ij,ij->i", v0, np.cross(v1, v2)) / 6.0
    sp = np.sum(((v0 + v1 + v2) / 4.0) * tv[:, None], axis=0) / vol
    return abs(vol), fl, lo, hi, sp, len(t)

aus = {}
print(f"{'Teil':<16} {'Dreiecke':>8} {'Lx':>7} {'Ly':>7} {'Lz':>7}  {'Volumen':>9} {'Fläche':>9}  {'Masse voll':>10} {'Masse 25 %':>10}")
for p in sorted(H.glob("*.stl")):
    t = lies(p)
    vol, fl, lo, hi, sp, n = kennwerte(t)
    L = hi - lo
    m_voll = vol * PLA
    # Teildruck: Hülle voll, Inneres mit Füllung — Hülle als Oberfläche × Wandstärke, gedeckelt durch das Volumen
    huelle = min(vol, fl * HUELLE)
    m_teil = (huelle + (vol - huelle) * FUELLUNG) * PLA
    aus[p.stem] = dict(dreiecke=n, laenge_mm=L.round(2).tolist(), min_mm=lo.round(2).tolist(), max_mm=hi.round(2).tolist(),
                       volumen_mm3=round(vol, 1), flaeche_mm2=round(fl, 1), schwerpunkt_mm=sp.round(2).tolist(),
                       masse_voll_g=round(m_voll, 1), masse_25prozent_g=round(m_teil, 1))
    print(f"{p.stem:<16} {n:>8} {L[0]:>7.1f} {L[1]:>7.1f} {L[2]:>7.1f}  {vol/1000:>7.1f} cm³ {fl/100:>7.1f} cm² {m_voll:>8.1f} g {m_teil:>8.1f} g")
(H.parent / "stl_masse.json").write_text(json.dumps(aus, indent=1))
print("→ stl_masse.json")
