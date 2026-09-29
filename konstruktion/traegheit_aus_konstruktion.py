#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trägheitsmoment um die Radachse, Schwerpunkthöhe und Kippzeitkonstante aus der Konstruktion — als Rechnung mit
offengelegten Annahmen, solange nicht gependelt wird. Lagen aus den STL-Maßen (Stapel), Massen aus stl_masse.json
(25 % Füllung) bzw. Datenblatt/Annahme. Jeder Beitrag: m·(z² + x²) + Eigenträgheit (Platte/Quader um die eigene Achse).
Ausgabe: traegheit_aus_konstruktion.json und Tabelle."""
import json
import numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
st = json.loads((H / 'stl_masse.json').read_text())
g = 9.81; ACHSE = 31.5
M_GEWOGEN = 1.248                                # gewogen 28.09.2026
# Bekannt: Motoren 0,400 (Datenblatt), Akku 0,224 (gewogen), Druckteile aus STL (voll). Der Rest (Räder, Elektronik, Schrauben)
# wird mit einem Faktor so gestreckt, dass die Summe die gewogene Gesamtmasse trifft.
_bekannt = 0.400 + 0.224 + sum(st[n]['masse_voll_g']/1000 * k for n, k in (('radkasten',2),('motorhalterung',1),('grundplatte',1),('stuetze',2),('dachplatte',1),('akkubuegel',1),('sensorpult',1))) + 0.003
REST = (M_GEWOGEN - _bekannt) / (0.050 + 0.100 + 0.030)
print(f'bekannte Massen {_bekannt:.3f} kg, Rest {M_GEWOGEN-_bekannt:.3f} kg auf 180 g Annahmen → Faktor {REST:.2f}')
def m25(name): return st[name]['masse_voll_g'] / 1000   # gewogen 28.09.: 1248 g gesamt -> Druckteile als Vollkörper angesetzt
# (Name, Masse kg, z über Achse [m], x vor Achse [m], Länge in Fahrtrichtung [m], Höhe [m], Quelle)
T = [
 ('2 Motoren SM-42BYG011-25',      2*0.200,        0.0,              0.0,   0.042, 0.042, 'Datenblatt ≈ 200 g; Achse (ANNAHME Masse)'),
 ('2 Räder mit Naben',              0.050*REST,     0.0,              0.0,   0.063, 0.063, 'ANNAHME 2 × 25 g × Restfaktor; drehen frei, nur Masse'),
 ('2 Radkästen',                    2*m25('radkasten'), (10.5+31.25-ACHSE)/1e3, 0.0, 0.083, 0.0625, 'STL, voll'),
 ('Motorhalterung',                 m25('motorhalterung'), 0.020,       0.0,   0.065, 0.090, 'STL; Lage ANNAHME'),
 ('Grundplatte',                    m25('grundplatte'), (73+2.5-ACHSE)/1e3, 0.0, 0.160, 0.005, 'STL'),
 ('2 Stützen',                      2*m25('stuetze'), (78+22.5-ACHSE)/1e3, 0.0, 0.060, 0.045, 'STL'),
 ('Dachplatte',                     m25('dachplatte'), (123+2.5-ACHSE)/1e3, 0.0, 0.160, 0.005, 'STL'),
 ('Akkubügel',                      m25('akkubuegel'), (128+30-ACHSE)/1e3, 0.0, 0.060, 0.025, 'STL; Lage ANNAHME'),
 ('Akku LiPo 4S 2400 mAh (Conrad 1414138)', 0.224,  (128+16-ACHSE)/1e3, 0.0,  0.105, 0.032, 'gewogen 28.09.: 224 g; Maße ANNAHME 105 × 34 × 32'),
 ('Sensorpult + MPU6050',           m25('sensorpult')+0.003, (103-ACHSE)/1e3, 0.039, 0.060, 0.022, 'STL; Lage gemessen'),
 ('ESP32, 2 Treiber, Grundplatine, Schalter, Kabel', 0.100*REST, (78+12-ACHSE)/1e3, 0.0, 0.100, 0.020, 'ANNAHME 100 g × Restfaktor'),
 ('Schrauben, Stangen, Muttern',    0.030*REST,     (78+40-ACHSE)/1e3, 0.0,  0.100, 0.050, 'ANNAHME 30 g × Restfaktor'),
]
m = sum(t[1] for t in T); mz = sum(t[1]*t[2] for t in T); mx = sum(t[1]*t[3] for t in T)
l = mz / m; s = mx / m
J = 0.0; zeilen = []
for name, mi, z, x, L, Hh, q in T:
    eigen = mi * (L**2 + Hh**2) / 12          # Quader um die eigene Querachse
    steiner = mi * (z**2 + x**2)
    J += eigen + steiner
    zeilen.append((name, mi, z, x, eigen, steiner, q))
Tk = np.sqrt(J / (m * g * l))
print(f"{'Baugruppe':<48} {'m [g]':>6} {'z [mm]':>7} {'x [mm]':>6} {'Eigen':>10} {'m(z²+x²)':>10}")
for n, mi, z, x, e, st_, q in zeilen:
    print(f"{n:<48} {mi*1e3:>6.0f} {z*1e3:>7.1f} {x*1e3:>6.1f} {e:>10.2e} {st_:>10.2e}   {q}")
print(f"\nMasse m = {m:.3f} kg, Schwerpunkt l = {l*1e3:.1f} mm über der Achse, s = {s*1e3:.1f} mm vor der Achse")
print(f"J um die Radachse = {J:.4e} kg·m², m·l = {m*l:.4e} kg·m, Kippzeitkonstante T = √(J/(m g l)) = {Tk*1e3:.1f} ms")
print(f"Pendeldauer um die Achse, die dazu gehört: T_p = 2π·T = {2*np.pi*Tk:.3f} s")
(H / 'traegheit_aus_konstruktion.json').write_text(json.dumps(dict(m_kg=m, l_m=l, s_m=s, J_kgm2=J, T_kipp_s=Tk, T_pendel_s=2*np.pi*Tk,
    beitraege=[dict(name=n, m_kg=mi, z_m=z, x_m=x, eigen=e, steiner=st_, quelle=q) for n, mi, z, x, e, st_, q in zeilen]), indent=1))
