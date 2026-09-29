#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auswertung des Pendelvideos als Doppelpendel: Schnur (Länge L, von der Hand zum Fenster) und Körper
(Trägheitsmoment J_cg um den Schwerpunkt, Abstand r Schnur–Schwerpunkt).

Eingabe: pendel_verfolgung.txt (Markenlagen je Bild aus pendel_verfolgung.py). Zwei Signale:
  Verschiebung — die x-Lage einer Körpermarke im Bild (das ganze Fahrzeug wandert): Mode 1
  Drehung      — Differenz zweier Körpermarken unterschiedlicher Tiefe, senkrecht zur Schnur: Mode 2
Beide Perioden aus Periodogramm und Sinus-Ausgleich im ruhigen Abschnitt 16,0–21,8 s.

Modell (kleine Winkel, φ Schnurwinkel, θ Körperwinkel gegen das Lot):
  T = ½ m (L φ' + r θ')² + ½ J_cg θ'²,   V = ½ m g (L φ² + r θ²)
  M = m·[[L², L r], [L r, r² + J_cg/m]],  K = m g·diag(L, r),  det(K − ω² M) = 0  → zwei Moden.
Unbekannt sind L, r, J_cg; gemessen sind zwei Perioden. Deshalb: (a) je angenommenem r werden L und J_cg
bestimmt; (b) mit dem J_cg der Konstruktion werden L und r bestimmt — stimmen sie mit der Aufnahme
überein, ist die Konstruktion durch das Video bestätigt. Ergebnis in pendel_doppelpendel.{json,txt,png}.
"""
import json
import numpy as np
from scipy.optimize import curve_fit, fsolve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

M_KG, G, L_SP = 1.248, 9.81, 0.04448                # gewogen 28.09.; Schwerpunkthöhe aus der Konstruktion
J_BAU = json.load(open('traegheit_aus_konstruktion.json'))['J_kgm2']
JCG_BAU = J_BAU - M_KG * L_SP**2
T_A, T_B = 16.0, 21.8                                # ruhiger Abschnitt (danach Kamerabewegung)
PHI = np.radians(-47.0)                              # Schnurrichtung im Bild
N_PERP = np.array([-np.sin(PHI), np.cos(PHI)])
NAMEN = ['Rad', 'Klemme_A', 'Klemme_B', 'Schraube', 'Schraube2', 'Nabe']

D = np.loadtxt('pendel_verfolgung.txt')
t = D[:, 0]
X = {n: D[:, 1 + i] for i, n in enumerate(NAMEN)}
Y = {n: D[:, 7 + i] for i, n in enumerate(NAMEN)}
seg = (t >= T_A) & (t <= T_B)


def periodogramm(tt, s, Tmin=0.3, Tmax=3.0, n=6000):
    Ts = np.linspace(Tmin, Tmax, n); s = s - s.mean(); P = np.empty(n)
    for i, T in enumerate(Ts):
        w = 2 * np.pi / T; c = np.cos(w * tt); sn = np.sin(w * tt)
        P[i] = (s @ c) ** 2 / (c @ c) + (s @ sn) ** 2 / (sn @ sn)
    return Ts, P


def sinus(tt, A, T, ph, c):
    return A * np.sin(2 * np.pi * tt / T + ph) + c


def periode(tt, s, T0):
    Ts, P = periodogramm(tt, s); i = P.argmax()
    p, cov = curve_fit(sinus, tt, s, p0=[s.std() * 1.4, Ts[i], 0, s.mean()], maxfev=20000)
    return Ts[i], abs(p[1]), float(np.sqrt(cov[1, 1])), abs(p[0]), (s - sinus(tt, *p)).std()


E = {'abschnitt_s': [T_A, T_B], 'm_kg': M_KG, 'l_m': L_SP, 'J_bau': J_BAU, 'Jcg_bau': JCG_BAU, 'verschiebung': {}, 'drehung': {}}
for n in ['Klemme_A', 'Klemme_B', 'Schraube2']:
    g = seg & ~np.isnan(X[n]); Tp, Tf, dTf, A, rest = periode(t[g], X[n][g], 1.0)
    E['verschiebung'][n] = dict(T_periodogramm=Tp, T_fit=Tf, dT_fit=dTf, A_px=A, rest_px=rest)
for a, b in [('Klemme_A', 'Nabe'), ('Klemme_B', 'Nabe'), ('Klemme_A', 'Schraube2')]:
    g = seg & ~np.isnan(X[a]) & ~np.isnan(X[b]); tt = t[g]
    s = (X[a][g] - X[b][g]) * N_PERP[0] + (Y[a][g] - Y[b][g]) * N_PERP[1]
    Tp, Tf, dTf, A, rest = periode(tt, s, 0.5)
    Ts, P = periodogramm(tt, s); i = P.argmax(); P2 = P.copy(); P2[(Ts > 0.9 * Ts[i]) & (Ts < 1.1 * Ts[i])] = 0; j = P2.argmax()
    E['drehung'][f'{a}−{b}'] = dict(T_periodogramm=Tp, T_fit=Tf, dT_fit=dTf, A_px=A, rest_px=rest, T_nebenmax=Ts[j], leistung_neben_zu_haupt=float(P[j] / P[i]))
T1 = float(np.mean([v['T_fit'] for v in E['verschiebung'].values()]))
T2 = float(np.mean([v['T_fit'] for v in E['drehung'].values()]))
E.update(T1_s=T1, T2_s=T2, verhaeltnis=T1 / T2)


def moden(L, r, Jcg):
    M = np.array([[M_KG * L * L, M_KG * L * r], [M_KG * L * r, M_KG * r * r + Jcg]]); K = np.diag([M_KG * G * L, M_KG * G * r])
    w2 = np.sort(np.linalg.eigvals(np.linalg.solve(M, K)).real)
    return 2 * np.pi / np.sqrt(w2)                    # [langsam, schnell]


def loese(f, starts):
    for x0 in starts:
        x, info, ier, msg = fsolve(f, x0, full_output=True)
        if ier == 1 and np.all(np.array(x) > 0) and max(abs(np.array(f(x)))) < 1e-8:
            return x
    return None


# (a) je r: L und J_cg
tab = []
for r in [0.010, 0.015, 0.020, 0.025, 0.030, 0.035, 0.040, 0.045, 0.050, 0.055, 0.060]:
    def f(x, r=r):
        L, J = x
        if L <= 0 or J <= 0: return [1.0, 1.0]
        Tl, Ts = moden(L, r, J); return [Tl - T1, Ts - T2]
    x = loese(f, [[L0, J0] for L0 in (0.1, 0.2, 0.3) for J0 in (1e-3, 3e-3, 6e-3)])
    if x is None: tab.append(dict(r_m=r)); continue
    L, J = x; JA = J + M_KG * L_SP**2
    tab.append(dict(r_m=r, L_m=float(L), Jcg=float(J), J_achse=float(JA), T_kipp_s=float(np.sqrt(JA / (M_KG * G * L_SP)))))
E['je_r'] = tab
# (b) mit J_cg der Konstruktion: L und r
def f2(x):
    L, r = x
    if L <= 0 or r <= 0: return [1.0, 1.0]
    Tl, Ts = moden(L, r, JCG_BAU); return [Tl - T1, Ts - T2]
x = loese(f2, [[0.2, 0.02], [0.25, 0.05], [0.15, 0.1]])
E['konstruktion'] = dict(L_m=float(x[0]), r_m=float(x[1]), moden=list(map(float, moden(x[0], x[1], JCG_BAU)))) if x is not None else None
# Kontrollen: entkoppelt
E['schnur_allein_L_m'] = G * (T1 / 2 / np.pi) ** 2
E['koerper_allein_Tmin_s'] = 2 * np.pi * np.sqrt(2 * np.sqrt(JCG_BAU / M_KG) / G)

json.dump(E, open('pendel_doppelpendel.json', 'w'), indent=1, ensure_ascii=False)
with open('pendel_doppelpendel.txt', 'w') as f:
    f.write(f'Pendel.mp4, Abschnitt {T_A}–{T_B} s, m = {M_KG} kg, l = {L_SP*1e3:.1f} mm, J_cg (Konstruktion) = {JCG_BAU*1e3:.2f}e-3 kg m²\n')
    f.write('Verschiebung (Mode 1):\n')
    for n, v in E['verschiebung'].items():
        f.write(f"  {n:<10} Periodogramm {v['T_periodogramm']:.3f} s, Ausgleich {v['T_fit']:.4f} ± {v['dT_fit']:.4f} s, A = {v['A_px']:.1f} px, Rest {v['rest_px']:.1f} px\n")
    f.write('Drehung (Mode 2):\n')
    for n, v in E['drehung'].items():
        f.write(f"  {n:<20} Periodogramm {v['T_periodogramm']:.3f} s, Ausgleich {v['T_fit']:.4f} ± {v['dT_fit']:.4f} s, A = {v['A_px']:.1f} px, Rest {v['rest_px']:.1f} px, Nebenmaximum {v['T_nebenmax']:.3f} s ({v['leistung_neben_zu_haupt']*100:.0f} % Leistung)\n")
    f.write(f'T1 = {T1:.4f} s, T2 = {T2:.4f} s, T1/T2 = {T1/T2:.3f}\n')
    f.write(f"Schnur allein mit T1: L = {E['schnur_allein_L_m']:.3f} m; Körper allein um die Schnur mit J_cg der Konstruktion: kleinstmögliche Periode {E['koerper_allein_Tmin_s']:.3f} s > T2\n\n")
    f.write('(a) je Abstand r Schnur–Schwerpunkt: Schnurlänge L und J aus beiden Perioden\n  r [mm]   L [m]   J_cg [e-3]  J_Achse [e-3]  T_kipp [ms]\n')
    for z in tab:
        if 'L_m' in z: f.write(f"  {z['r_m']*1e3:5.0f}   {z['L_m']:6.3f}   {z['Jcg']*1e3:8.3f}    {z['J_achse']*1e3:8.3f}      {z['T_kipp_s']*1e3:6.1f}\n")
        else: f.write(f"  {z['r_m']*1e3:5.0f}   keine Lösung\n")
    k = E['konstruktion']
    if k: f.write(f"\n(b) mit J_cg der Konstruktion: L = {k['L_m']:.3f} m, r = {k['r_m']*1e3:.1f} mm reproduzieren beide Perioden ({k['moden'][0]:.3f} s, {k['moden'][1]:.3f} s)\n")
print(open('pendel_doppelpendel.txt').read())

# Bild: die beiden Signale mit ihren Ausgleichskurven und das Periodogramm der Drehung
fig, ax = plt.subplots(3, 1, figsize=(11, 9))
g = seg & ~np.isnan(X['Klemme_A']); ax[0].plot(t[g], X['Klemme_A'][g], '.', ms=3, label='Klemme A, x-Lage im Bild (Verschiebung)')
v = E['verschiebung']['Klemme_A']; p, _ = curve_fit(sinus, t[g], X['Klemme_A'][g], p0=[v['A_px'], v['T_fit'], 0, X['Klemme_A'][g].mean()], maxfev=20000)
ax[0].plot(t[g], sinus(t[g], *p), 'r-', lw=1, label=f'Ausgleich T₁ = {abs(p[1]):.3f} s'); ax[0].set_ylabel('[px]'); ax[0].legend(loc='upper right'); ax[0].grid(alpha=.3)
g = seg & ~np.isnan(X['Klemme_A']) & ~np.isnan(X['Nabe']); tt = t[g]
s = (X['Klemme_A'][g] - X['Nabe'][g]) * N_PERP[0] + (Y['Klemme_A'][g] - Y['Nabe'][g]) * N_PERP[1]
v = E['drehung']['Klemme_A−Nabe']; p, _ = curve_fit(sinus, tt, s, p0=[v['A_px'], v['T_fit'], 0, s.mean()], maxfev=20000)
ax[1].plot(tt, s, '.', ms=3, label='Klemme A − Nabe, senkrecht zur Schnur (Drehung)'); ax[1].plot(tt, sinus(tt, *p), 'r-', lw=1, label=f'Ausgleich T₂ = {abs(p[1]):.3f} s')
ax[1].set_ylabel('[px]'); ax[1].set_xlabel('t [s]'); ax[1].legend(loc='upper right'); ax[1].grid(alpha=.3)
Ts, P = periodogramm(tt, s); ax[2].plot(Ts, P / P.max(), label='Periodogramm der Drehung')
Ts2, P2 = periodogramm(t[seg & ~np.isnan(X['Klemme_A'])], X['Klemme_A'][seg & ~np.isnan(X['Klemme_A'])]); ax[2].plot(Ts2, P2 / P2.max(), label='Periodogramm der Verschiebung')
ax[2].axvline(T1, color='k', lw=.6); ax[2].axvline(T2, color='k', lw=.6); ax[2].set_xlabel('Periode [s]'); ax[2].set_ylabel('bezogen'); ax[2].legend(); ax[2].grid(alpha=.3); ax[2].set_xlim(0.3, 2.0)
fig.suptitle(f'Pendel.mp4 als Doppelpendel: T₁ = {T1:.3f} s (Schnur), T₂ = {T2:.3f} s (Körper), Verhältnis {T1/T2:.2f}')
fig.tight_layout(); fig.savefig('pendel_doppelpendel.png', dpi=110)
