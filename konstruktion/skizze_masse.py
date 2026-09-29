#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bemaßte Skizze des Mini-Segway aus den STL-Maßen (Seitenansicht und Draufsicht) mit Quellenkennzeichnung.
Quellen: STL (exakt), abgeleitet (aus STL-Maßen zusammengesetzt), ANNAHME (Foto/Datenblatt, am Gerät zu messen)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon

R = 31.5                 # Radradius, Ø 63 (Angabe Nutzer/Manuskript)
ACHSE = R                # Achshöhe über Boden
RK_UNTEN = ACHSE - 21.0  # Radkasten-Unterkante: Achse liegt 21 mm über seiner Unterkante (STL)
RK_OBEN = RK_UNTEN + 62.5
GP_U, GP_O = RK_OBEN, RK_OBEN + 5          # Grundplatte auf dem Radkasten (Foto) — 5 mm (STL)
ST_H = 45.0                                 # Stütze (STL)
DP_U, DP_O = GP_O + ST_H, GP_O + ST_H + 5   # Dachplatte
AKKU_H = 28.0                               # ANNAHME LiPo-Höhe
AB_O = DP_O + AKKU_H + 5                    # Akkubügel-Oberkante (Bügel 5 mm über dem Akku, STL: Bügel 60×25, Schenkel 90)
SP_H = 21.6                                 # Sensorpult (STL)
L_PLATTE = 160.0; T_PLATTE = 110.0

fig, (a, b) = plt.subplots(2, 1, figsize=(10, 11.5), gridspec_kw=dict(height_ratios=[1.15, 1]))
a.set_title("Seitenansicht (Fahrrichtung nach rechts) — Höhen aus den STL-Maßen zusammengesetzt", fontsize=11)
a.plot([-140, 140], [0, 0], color="k", lw=2)
a.add_patch(Circle((0, ACHSE), R, fill=False, lw=2, color="k")); a.add_patch(Circle((0, ACHSE), 2.5, color="k"))
# Radkasten (Bogen) als Rechteck angedeutet
a.add_patch(Rectangle((-41.5, RK_UNTEN), 83, 62.5, fill=False, lw=1, ls="--", color="#555"))
a.add_patch(Rectangle((-L_PLATTE/2, GP_U), L_PLATTE, 5, color="#4a63c8"))
a.add_patch(Rectangle((-L_PLATTE/2, DP_U), L_PLATTE, 5, color="#4a63c8"))
for x in (-50, 50):
    a.add_patch(Rectangle((x-10, GP_O), 20, ST_H, color="#7f93d9"))
a.add_patch(Rectangle((-50, DP_O), 100, AKKU_H, color="#bbb"))             # Akku
a.add_patch(Rectangle((-30, DP_O+AKKU_H), 60, 5, color="#4a63c8"))          # Akkubügel oben
a.add_patch(Rectangle((-30, GP_O), 60, SP_H, color="#6a7fd0"))             # Sensorpult (mittig)
a.add_patch(Circle((0, GP_O+SP_H+2), 3, color="#b0171f")); a.text(0, GP_O+SP_H+16, "MPU6050 (Sensorpult, STL 21,6 hoch)", fontsize=8, color="#b0171f", ha="center")
a.add_patch(Rectangle((-60, GP_O+5), 30, 20, color="#8d3f2f")); a.add_patch(Rectangle((30, GP_O+5), 30, 20, color="#8d3f2f"))
a.text(-45, GP_O+27, "Treiber", fontsize=7, ha="center"); a.text(45, GP_O+27, "Treiber", fontsize=7, ha="center")
a.add_patch(Rectangle((-25, GP_O+5), 50, 12, color="#333")); a.text(0, GP_O+19, "ESP32", fontsize=7, ha="center", color="w")
a.add_patch(Rectangle((-21, ACHSE-21), 42, 42, fill=False, lw=1, color="#888")); a.text(24, ACHSE-18, "Motor NEMA 17\n42 × 42 (Lochbild STL)\nLänge/Masse: messen", fontsize=8, color="#666")
def mass(y, text, x=92):
    a.plot([x, x+10], [y, y], color="k", lw=0.8); a.text(x+13, y, text, fontsize=8.5, va="center")
mass(0, "0 — Boden")
mass(ACHSE, f"{ACHSE:.1f} — Radachse (Ø 63)")
mass(RK_UNTEN, f"{RK_UNTEN:.1f} — Radkasten unten (STL: Achse 21 über Unterkante)")
mass(GP_U, f"{GP_U:.1f} — Grundplatte unten (auf dem Radkasten, Foto)")
mass(GP_O, f"{GP_O:.1f} — Grundplatte oben (5 mm, STL)")
mass(GP_O+SP_H, f"{GP_O+SP_H:.1f} — Sensor (Pult 21,6, STL) → w ≈ {GP_O+SP_H-ACHSE:.0f} über Achse")
mass(DP_U, f"{DP_U:.1f} — Dachplatte unten (Stütze 45, STL)")
mass(DP_O, f"{DP_O:.1f} — Dachplatte oben")
mass(AB_O, f"{AB_O:.1f} — Akkubügel oben (ANNAHME Akku 28 hoch) → H ≈ {AB_O-ACHSE:.0f} über Achse")
a.annotate("", (-L_PLATTE/2, -18), (L_PLATTE/2, -18), arrowprops=dict(arrowstyle="<->")); a.text(0, -30, "Platte 160 (STL)", ha="center", fontsize=9)
a.set_xlim(-150, 330); a.set_ylim(-40, AB_O+25); a.set_aspect("equal"); a.axis("off")

b.set_title("Draufsicht — Spurweite 143 mm (gemessen 28.09.2026)", fontsize=11)
b.add_patch(Rectangle((-L_PLATTE/2, -T_PLATTE/2), L_PLATTE, T_PLATTE, fill=False, lw=2, color="#4a63c8"))
B = 143.0   # Spurweite, gemessen 28.09.2026
for s in (-1, 1):
    y0 = s*(T_PLATTE/2 + 43/2)
    b.add_patch(Rectangle((-41.5, y0-21.5), 83, 43, fill=False, lw=1, ls="--", color="#555"))   # Radkasten 83 × 43 (STL)
    b.add_patch(Rectangle((-R, s*B/2 - 13), 2*R, 26, color="k"))                                  # Rad auf B/2, Breite ANNAHME 26
b.add_patch(Rectangle((-30, -5), 60, 10, color="#6a7fd0")); b.text(0, 10, "Sensorpult 60 × 10 (STL), mittig", ha="center", fontsize=8)
b.annotate("", (-L_PLATTE/2, -T_PLATTE/2-90), (L_PLATTE/2, -T_PLATTE/2-90), arrowprops=dict(arrowstyle="<->")); b.text(0, -T_PLATTE/2-105, "160 (STL)", ha="center", fontsize=9)
b.annotate("", (L_PLATTE/2+15, -T_PLATTE/2), (L_PLATTE/2+15, T_PLATTE/2), arrowprops=dict(arrowstyle="<->")); b.text(L_PLATTE/2+20, 0, "110 (STL)", va="center", fontsize=9)
b.annotate("", (-L_PLATTE/2-20, -71.5), (-L_PLATTE/2-20, 71.5), arrowprops=dict(arrowstyle="<->")); b.text(-L_PLATTE/2-26, 0, "Spurweite B = 143\n(gemessen 28.09.)", ha="right", va="center", fontsize=9)
b.text(0, T_PLATTE/2+43+40, "Radkasten je Seite 83 × 43 (STL); Räder laufen darin, Mitte bei ±71,5", ha="center", fontsize=8)
b.set_xlim(-190, 210); b.set_ylim(-190, 180); b.set_aspect("equal"); b.axis("off")
fig.suptitle("Mini-Segway (STL-Konstruktion 2018): Maße für Modell und Prüfstand — STL exakt, Foto/ANNAHME zu messen", fontsize=12)
fig.tight_layout(); fig.savefig("skizze_masse.png", dpi=110); print("skizze_masse.png geschrieben")
print(f"Stapel: Achse {ACHSE}, GP {GP_U:.1f}-{GP_O:.1f}, DP {DP_U:.1f}-{DP_O:.1f}, Bügel oben {AB_O:.1f}; über Achse: Sensor {GP_O+SP_H-ACHSE:.1f}, H {AB_O-ACHSE:.1f}")
