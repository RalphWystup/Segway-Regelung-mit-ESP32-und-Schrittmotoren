#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prüfstand für die Standstabilität des Segway: Fangleine von oben, Führungsleisten, Kamera in Seitenansicht.
Maße gemessen am 28.09.2026 (H, B, Reifenbreite); Gehäusetiefe = Plattenlänge aus den STL-Dateien. Erzeugt halterung.png."""
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch

H = 134.0        # gemessen 28.09.: Akkubügel-Oberkante 155 mm über der Motorunterkante, Motor 42 mm mittig auf der Achse → 134 mm über der Achse
R = 32.0         # Radradius: Ø 64 mm gemessen 28.09.
B = 143.0        # gemessen 28.09.: Spurweite Reifenmitte–Reifenmitte [mm]
REIFEN = 26.5    # gemessen 28.09.: Reifenbreite [mm]
LUFT = 5.0       # Luft je Seite zwischen Reifen und Leiste [mm]
T = 160.0        # Plattenlänge in Fahrtrichtung aus STL [mm]
PLATTE = 600.0   # Grundplatte Länge [mm]
FAHRWEG = 100.0  # zulässiger Fahrweg ±
HOOK = 620.0     # gezeichnet verkürzt; wirklich ≥ 1000 mm über der Radachse (Portal), siehe Text
KIPP = 25.0      # Fangwinkel [Grad]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 7.5), gridspec_kw=dict(width_ratios=[1.25, 1]))
# ---------------------------------------------------------------- Seitenansicht (Kamera-Blick)
a = a1
a.set_title("Seitenansicht = Blick der Kamera (senkrecht zur Radachse)", fontsize=11)
a.add_patch(Rectangle((-PLATTE/2, -R-19), PLATTE, 19, color="#c8b07a"))                 # Grundplatte
a.add_patch(Rectangle((-PLATTE/2, -R), PLATTE, 4, color="#555"))                         # Gummimatte
for x in (-FAHRWEG-25, FAHRWEG+5):                                                       # Endanschläge Schaum
    a.add_patch(Rectangle((x, -R), 20, 2*R+20, color="#9fd1a3"))
a.add_patch(Circle((0, 0), R, fill=False, lw=2, color="k"))                              # Rad
a.add_patch(Circle((0, 0), 3, color="k"))
a.add_patch(Rectangle((-T/2, 0), T, H, fill=False, lw=2, color="k"))                     # Gehäuse/Mast
# Fangleine
a.plot([0, 0], [H, HOOK], color="#b0171f", lw=1.2)
a.plot([0], [HOOK], marker="v", color="#b0171f", ms=9)
a.text(12, HOOK-30, "Haken am Portal ≥ 1 m über der Achse\n(gezeichnet verkürzt); Fangleine lose,\nwird erst bei ±25° straff", color="#b0171f", fontsize=9)
a.plot([-12, 12], [HOOK-120, HOOK-100], color="w", lw=6); a.plot([-12, 12], [HOOK-120, HOOK-100], color="#b0171f", lw=1)
# Kippgrenze gestrichelt
for s in (-1, 1):
    a.plot([0, s*H*np.sin(np.radians(KIPP))], [0, H*np.cos(np.radians(KIPP))], "--", color="#b0171f", lw=1)
a.text(H*np.sin(np.radians(KIPP))+45, H*np.cos(np.radians(KIPP))+40, "25°: Leine straff\n(Abschaltung 30°)", fontsize=9, color="#b0171f")
# Marken für die Bildauswertung
a.add_patch(Circle((0, 0), 6, color="#1769aa")); a.add_patch(Circle((0, H-15), 6, color="#1769aa"))
a.add_patch(Circle((R*0.7, 0), 3, color="#e6a100"))
a.text(-T/2-8, H-15, "Marke 2 (Mastoberkante)", fontsize=9, color="#1769aa", ha="right")
a.text(-T/2-8, 10, "Marke 1 (Achse)", fontsize=9, color="#1769aa", ha="right")
a.text(R+6, -14, "Radmarke", fontsize=8, color="#e6a100")
# Maßstab auf der Platte
a.plot([150, 250], [-R-8, -R-8], color="w", lw=2); a.text(320, -R-40, "← Maßstab 100 mm (weiß auf der Platte)", ha="left", fontsize=9)
# LED
a.add_patch(Circle((-T/2+8, H*0.6), 4, color="#2ecc40")); a.text(-T/2-8, H*0.6, "Synchronblitz (LED)", fontsize=9, color="#237a2b", ha="right")
# Bemaßung
a.annotate("", (-FAHRWEG, -R-40), (FAHRWEG, -R-40), arrowprops=dict(arrowstyle="<->")); a.text(0, -R-58, f"Fahrweg ±{FAHRWEG:.0f} mm", ha="center", fontsize=9)
a.annotate("", (T/2+30, 0), (T/2+30, H), arrowprops=dict(arrowstyle="<->")); a.text(T/2+36, H/2, f"H = {H:.0f} mm\n(gemessen 28.09.)", fontsize=9)
a.set_xlim(-PLATTE/2-60, PLATTE/2+120); a.set_ylim(-110, HOOK+40); a.set_aspect("equal"); a.axis("off")
# Kamera
a.add_patch(Rectangle((PLATTE/2+50, 250), 40, 30, color="#333")); a.add_patch(Circle((PLATTE/2+50, 265), 8, color="#333"))
a.text(PLATTE/2+50, 300, "Kamera steht seitlich, 1,0–1,5 m vor der\nSpurmitte, auf Achshöhe, waagerecht\n(hier nur angedeutet)", fontsize=9, ha="center")
# ---------------------------------------------------------------- Draufsicht
a = a2
a.set_title("Draufsicht", fontsize=11)
a.add_patch(Rectangle((-PLATTE/2, -150), PLATTE, 300, color="#c8b07a"))
for y in (-B/2-REIFEN/2-LUFT-15, B/2+REIFEN/2+LUFT):                                    # Führungsleisten, lichte Weite B+REIFEN+2·LUFT
    a.add_patch(Rectangle((-PLATTE/2, y), PLATTE, 15, color="#8a6d3b"))
for x in (-FAHRWEG-25, FAHRWEG+5):
    a.add_patch(Rectangle((x, -B/2-REIFEN/2-LUFT), 20, B+REIFEN+2*LUFT, color="#9fd1a3"))
for y in (-B/2, B/2):                                                                    # Räder
    a.add_patch(Rectangle((-R, y-REIFEN/2), 2*R, REIFEN, color="k"))
a.add_patch(Rectangle((-T/2, -B/2+10), T, B-20, fill=False, lw=2, color="k"))
a.plot([0], [0], "o", color="#b0171f", ms=6); a.text(6, 6, "Leine", color="#b0171f", fontsize=9)
a.add_patch(Rectangle((PLATTE/2+40, -20), 40, 40, color="#333")); a.text(PLATTE/2+40, 30, "Kamera", fontsize=9)
a.plot([PLATTE/2+40, T/2], [0, 0], ":", color="#333")
a.annotate("", (-PLATTE/2, -180), (PLATTE/2, -180), arrowprops=dict(arrowstyle="<->")); a.text(0, -198, "Grundplatte 600 × 300 mm", ha="center", fontsize=9)
a.annotate("", (-PLATTE/2-25, -B/2), (-PLATTE/2-25, B/2), arrowprops=dict(arrowstyle="<->")); a.text(-PLATTE/2-40, 0, f"B = {B:.0f} mm\nReifen {REIFEN:.1f}\n(gemessen)", ha="right", va="center", fontsize=9)
a.text(0, B/2+REIFEN/2+30, f"Führungsleisten, lichte Weite {B+REIFEN+2*LUFT:.1f} mm ({LUFT:.0f} mm Luft je Seite):\nkein Gieren, kein seitliches Wandern", ha="center", fontsize=9)
a.text(0, -B/2-REIFEN/2-45, "weiche Endanschläge (Schaumstoff)", ha="center", fontsize=9)
a.set_xlim(-PLATTE/2-120, PLATTE/2+100); a.set_ylim(-220, 200); a.set_aspect("equal"); a.axis("off")
fig.suptitle("Prüfstand Standstabilität — Fangleine von oben, Führung unten, Kamera von der Seite (Maße vom 28.09.2026: H = 134, B = 143, Reifen 26,5 mm)", fontsize=12)
fig.tight_layout()
fig.savefig("/workspace/Regelungstechnik2_Segway/Pruefstand/halterung.png", dpi=110)
print("halterung.png geschrieben")
