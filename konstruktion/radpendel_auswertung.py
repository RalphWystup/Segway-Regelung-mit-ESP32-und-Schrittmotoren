#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Radpendel.mp4 (28.09.2026): ein Rad wird von Hand festgehalten, der Aufbau hängt darunter und pendelt um die
Radachse — Kamera fest, Achse zur Kamera, Schwingung in der Bildebene. Gesucht: die Schwingungsdauer T_p, denn
T_kipp = T_p/(2π) ist unmittelbar die Kippzeitkonstante der Strecke (dieselbe Wurzel √(J/(m g l))).

Weg A (Hauptweg): Drehwinkel des starren Aufbaus je Bild aus vielen Merkmalspunkten (AKAZE) gegen das Bezugsbild,
  Ähnlichkeitstransformation mit RANSAC (cv2.estimateAffinePartial2D) → θ = atan2(M10, M00). Der Hintergrund wird
  über ein Medianbild der ganzen Aufnahme ausgeblendet (die Kamera steht fest), die Hand über die Bildhöhe.
Weg B (Gegenprobe): Richtung des Verbindungsvektors zweier Marken am Aufbau (Vorlagenverfolgung), wie zuvor.
Abschnitte: zusammenhängende Strecken ohne Lücke > 0,2 s und ohne Sprung > 25° je Bild (Anfassen), ≥ 1,5 s.
Je Abschnitt: Nulldurchgänge (zeitlich interpoliert) → Perioden; Ausgleich exponentiell/geradlinig abklingend.
Die stromlosen Motoren bremsen mit ihrem Rastmoment, dazu Lagerreibung: Coulomb-artig → geradlinige Hüllkurve,
zäh → exponentielle; beides wird angepasst und der Rest verglichen. Ausgabe radpendel_auswertung.{txt,json,png}."""
import json
import numpy as np, cv2
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

V = 'Videos/Radpendel.mp4'
T0, T1, TREF = 14.0, 37.0, 16.0
Y_HAND = 790                       # oberhalb: Hand und Rad, wird für Weg A ausgeblendet
PAAR = {'Orange_L': (195, 910, 16), 'Orange_R': (382, 915, 16)}
M_KG, G, L_SP = 1.248, 9.81, 0.04448
J_BAU = json.load(open('traegheit_aus_konstruktion.json'))['J_kgm2']

cap = cv2.VideoCapture(V); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; n_ges = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
# Hintergrund: Median aus 41 Bildern über die ganze Aufnahme (Anfang und Ende ohne Fahrzeug)
proben = []
for i in np.linspace(0, n_ges-1, 41).astype(int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, f = cap.read()
    if ok: proben.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
hintergrund = np.median(np.stack(proben), axis=0).astype(np.uint8)

def maske(g):
    m = (cv2.absdiff(g, hintergrund) > 25).astype(np.uint8)*255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)); m = cv2.dilate(m, np.ones((15, 15), np.uint8))
    m[:Y_HAND] = 0
    return m

akaze = cv2.AKAZE_create(threshold=0.0008)
bf = cv2.BFMatcher(cv2.NORM_HAMMING)
cap.set(cv2.CAP_PROP_POS_MSEC, TREF*1000); ok, fref = cap.read(); gref = cv2.cvtColor(fref, cv2.COLOR_BGR2GRAY)
kref, dref = akaze.detectAndCompute(gref, maske(gref))
vorl = {n: gref[y-h:y+h, x-h:x+h].copy() for n, (x, y, h) in PAAR.items()}
print(f'Bezugsbild: {len(kref)} Merkmale auf dem Aufbau')

cap.set(cv2.CAP_PROP_POS_MSEC, T0*1000)
lage = {n: (float(x), float(y)) for n, (x, y, h) in PAAR.items()}
T, THA, NIN, THB, SCB = [], [], [], [], []
while True:
    ok, f = cap.read()
    if not ok: break
    tt = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
    if tt > T1: break
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    # Weg A
    th_a, n_in = np.nan, 0
    k, d = akaze.detectAndCompute(g, maske(g))
    if d is not None and len(k) >= 12:
        paare = bf.knnMatch(dref, d, k=2)
        gut = [m for m, n in (p for p in paare if len(p) == 2) if m.distance < 0.75*n.distance]
        if len(gut) >= 12:
            src = np.float32([kref[m.queryIdx].pt for m in gut]); dst = np.float32([k[m.trainIdx].pt for m in gut])
            Mx, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
            if Mx is not None and inl is not None and inl.sum() >= 12:
                sk = np.hypot(Mx[0, 0], Mx[1, 0])
                if 0.8 < sk < 1.25: th_a, n_in = np.degrees(np.arctan2(Mx[1, 0], Mx[0, 0])), int(inl.sum())
    THA.append(th_a); NIN.append(n_in)
    # Weg B
    neu, sc = {}, {}
    for n, (x0, y0, h) in PAAR.items():
        lx, ly = lage[n]; S = 60
        xa, ya = int(max(0, lx-h-S)), int(max(0, ly-h-S)); xb, yb = int(min(g.shape[1], lx+h+S)), int(min(g.shape[0], ly+h+S))
        aus = g[ya:yb, xa:xb]
        if aus.shape[0] <= 2*h or aus.shape[1] <= 2*h: neu[n] = None; sc[n] = 0.0; continue
        r = cv2.matchTemplate(aus, vorl[n], cv2.TM_CCOEFF_NORMED); _, mx, _, ml = cv2.minMaxLoc(r); sc[n] = float(mx)
        if mx < 0.55: neu[n] = None; continue
        neu[n] = (xa+ml[0]+h, ya+ml[1]+h); lage[n] = neu[n]
    if neu['Orange_L'] and neu['Orange_R']:
        THB.append(np.degrees(np.arctan2(neu['Orange_R'][1]-neu['Orange_L'][1], neu['Orange_R'][0]-neu['Orange_L'][0])))
    else: THB.append(np.nan)
    SCB.append(min(sc.values())); T.append(tt)
cap.release(); T, THA, THB, NIN, SCB = map(np.array, (T, THA, THB, NIN, SCB))

def gedaempft(tt, A, tau, Tp, ph, c): return A*np.exp(-(tt-tt[0])/tau)*np.sin(2*np.pi*(tt-tt[0])/Tp + ph) + c
def geradlinig(tt, A, k, Tp, ph, c): return np.maximum(A - k*(tt-tt[0]), 0)*np.sin(2*np.pi*(tt-tt[0])/Tp + ph) + c

def abschnitte(tg, sg):
    grenzen = [0] + [i for i in range(1, len(tg)) if tg[i]-tg[i-1] > 0.2 or abs(sg[i]-sg[i-1]) > 25] + [len(tg)]
    return [(a, b) for a, b in zip(grenzen[:-1], grenzen[1:]) if tg[b-1]-tg[a] >= 1.5]

def auswerten(tg, sg, ax, farbe):
    aus, perioden = [], []
    for (i0, i1) in abschnitte(tg, sg):
        t_, s_ = tg[i0:i1], sg[i0:i1]; ruhe = np.median(s_); x = s_ - ruhe
        if x.std() < 1.0: continue
        zc = [i for i in range(1, len(x)) if x[i-1] < 0 <= x[i]]
        tz = np.array([t_[i-1] + (t_[i]-t_[i-1])*(-x[i-1])/(x[i]-x[i-1]) for i in zc])
        per = np.diff(tz); perg = per[(per > 0.3) & (per < 1.5)]
        A = dict(von=float(t_[0]), bis=float(t_[-1]), amplitude_grad=float(np.abs(x).max()), n_perioden=int(len(perg)), perioden=[float(v) for v in perg])
        if len(perg): A['T_nulld'] = float(np.median(perg)); A['T_nulld_std'] = float(perg.std())
        for nm, fn, p0, stil in (('exp', gedaempft, [np.abs(x).max(), 10, A.get('T_nulld', 0.66), 0, ruhe], '-'),
                                 ('lin', geradlinig, [np.abs(x).max(), 1.0, A.get('T_nulld', 0.66), 0, ruhe], '--')):
            try:
                p, c = curve_fit(fn, t_, s_, p0=p0, maxfev=40000)
                A[f'T_{nm}'] = float(abs(p[2])); A[f'dT_{nm}'] = float(np.sqrt(c[2, 2])); A[f'rest_{nm}'] = float((s_-fn(t_, *p)).std())
                A['tau_exp' if nm == 'exp' else 'k_lin_grad_je_s'] = float(p[1])
                ax.plot(t_, fn(t_, *p) - np.median(sg), stil, color=farbe, lw=1)
            except Exception as e: A[f'fehler_{nm}'] = str(e)[:60]
        ex = [abs(x[zc[i]:zc[i+1]]).max() for i in range(len(zc)-1)]
        if len(ex) > 3:
            ta, aa = tz[:-1], np.array(ex); pl = np.polyfit(ta, aa, 1); pe = np.polyfit(ta, np.log(np.maximum(aa, 1e-3)), 1)
            A.update(huelle_lin_rest=float((aa-np.polyval(pl, ta)).std()), huelle_lin_grad_je_s=float(-pl[0]),
                     huelle_exp_rest=float((aa-np.exp(np.polyval(pe, ta))).std()), huelle_exp_tau_s=float(-1/pe[0]) if pe[0] < 0 else None)
        aus.append(A); perioden += list(perg)
    return aus, np.array(perioden)

fig, axs = plt.subplots(3, 1, figsize=(13, 9.5), sharex=True)
E = {'video': V, 'abschnitt_s': [T0, T1], 'merkmale_bezug': len(kref)}
ga = ~np.isnan(THA); axs[0].plot(T[ga], THA[ga]-np.median(THA[ga]), '.', ms=3, color='#1f77b4', label='Weg A: Drehwinkel aus Merkmalspunkten (RANSAC)')
E['wegA'], PA = auswerten(T[ga], THA[ga], axs[0], 'r')
gb = ~np.isnan(THB); axs[1].plot(T[gb], THB[gb]-np.median(THB[gb]), '.', ms=3, color='#1f77b4', label='Weg B: Richtung Orange_L→Orange_R')
E['wegB'], PB = auswerten(T[gb], THB[gb], axs[1], 'g')
for ax in axs[:2]: ax.set_ylabel('[Grad]'); ax.legend(loc='upper right', fontsize=8); ax.grid(alpha=.3); ax.set_ylim(-30, 30)
axs[2].plot(T, NIN, lw=.8, label='Weg A: RANSAC-Inlier'); axs[2].plot(T, SCB*100, lw=.8, label='Weg B: Treffergüte ×100'); axs[2].set_xlabel('t [s]'); axs[2].legend(fontsize=8); axs[2].grid(alpha=.3)
# gemeinsame Bilder beider Wege: Übereinstimmung
gg = ga & gb
if gg.sum() > 20:
    dif = (THA[gg]-np.median(THA[gg])) - (THB[gg]-np.median(THB[gg])); E['A_gegen_B_grad'] = dict(n=int(gg.sum()), mittel=float(dif.mean()), streuung=float(dif.std()))

def zusammen(P):
    return dict(n=int(len(P)), median=float(np.median(P)), mittel=float(P.mean()), streuung=float(P.std()), unsicher_mittel=float(P.std()/np.sqrt(len(P)))) if len(P) > 1 else None
E['T_p_A'] = zusammen(PA); E['T_p_B'] = zusammen(PB)
# Maßgeblich: die Perioden des Sinus-Ausgleichs in den sauberen Abschnitten von Weg A (Rest < 7°, Unsicherheit < 20 ms,
# 0,5 s < T < 0,8 s, keine unphysikalische Abklingzeit), gewichtet mit 1/dT². Nulldurchgänge dienen als Gegenprobe.
gut = [A for A in E['wegA'] if A.get('rest_exp', 99) < 7 and A.get('dT_exp', 1) < 0.02 and 0.5 < A.get('T_exp', 0) < 0.8 and abs(A.get('tau_exp', 0)) > 0.5]
E['auswahl'] = [dict(von=A['von'], bis=A['bis'], T_exp=A['T_exp'], dT_exp=A['dT_exp'], rest_exp=A['rest_exp'], amplitude_grad=A['amplitude_grad']) for A in gut]
if len(gut) >= 2:
    Tg = np.array([A['T_exp'] for A in gut]); wg = 1/np.array([A['dT_exp'] for A in gut])**2
    Tp = float((wg*Tg).sum()/wg.sum()); E['T_p_unsicher'] = float(1/np.sqrt(wg.sum())); E['T_p_streuung_abschnitte'] = float(Tg.std())
else:
    Tp = E['T_p_A']['median'] if E['T_p_A'] else None; E['T_p_unsicher'] = None
E.update(T_p_s=Tp, T_kipp_s=Tp/(2*np.pi) if Tp else None, J_bau=J_BAU, T_p_bau=float(2*np.pi*np.sqrt(J_BAU/(M_KG*G*L_SP))))
if Tp: E['J_durch_ml_m'] = G*(Tp/(2*np.pi))**2; E['J_achse_mit_l_bau'] = M_KG*G*L_SP*(Tp/(2*np.pi))**2
fig.suptitle(f'Radpendel.mp4 — Pendeln um die Radachse: T_p = {Tp:.4f} ± {E.get("T_p_unsicher") or 0:.4f} s (Weg A, {len(gut)} saubere Abschnitte) → T_kipp = T_p/2π = {Tp/(2*np.pi)*1e3:.1f} ms; Konstruktion {E["T_p_bau"]:.3f} s' if Tp else V)
fig.tight_layout(); fig.savefig('radpendel_auswertung.png', dpi=110)
json.dump(E, open('radpendel_auswertung.json', 'w'), indent=1, ensure_ascii=False)
with open('radpendel_auswertung.txt', 'w') as f:
    f.write(f'Radpendel.mp4, {T0}–{T1} s, {fps:.0f} Bilder/s, Bezugsbild {TREF} s, {len(kref)} Merkmale; Weg A gültig in {ga.sum()} von {len(T)} Bildern, Weg B in {gb.sum()}\n')
    for weg in ('wegA', 'wegB'):
        f.write(f'\n{weg}:\n')
        for A in E[weg]:
            f.write(f"  {A['von']:5.2f}–{A['bis']:5.2f} s, Amplitude {A['amplitude_grad']:4.1f}°, {A['n_perioden']} Perioden: T_nulld = {A.get('T_nulld', float('nan')):.4f} ± {A.get('T_nulld_std', float('nan')):.4f} s; "
                    f"exp. T = {A.get('T_exp', float('nan')):.4f} ± {A.get('dT_exp', float('nan')):.4f} (τ {A.get('tau_exp', float('nan')):.1f} s, Rest {A.get('rest_exp', float('nan')):.2f}°); "
                    f"geradlinig T = {A.get('T_lin', float('nan')):.4f} ± {A.get('dT_lin', float('nan')):.4f} ({A.get('k_lin_grad_je_s', float('nan')):.2f} °/s, Rest {A.get('rest_lin', float('nan')):.2f}°)\n")
            if 'huelle_lin_rest' in A:
                f.write(f"        Hüllkurve: geradlinig Rest {A['huelle_lin_rest']:.2f}° ({A['huelle_lin_grad_je_s']:.2f} °/s) | exponentiell Rest {A['huelle_exp_rest']:.2f}° (τ {A['huelle_exp_tau_s']})\n")
    for w in ('T_p_A', 'T_p_B'):
        z = E[w]
        if z: f.write(f"\n{w}: {z['n']} Perioden, Median {z['median']:.4f} s, Mittel {z['mittel']:.4f} s, Streuung {z['streuung']:.4f} s, Unsicherheit des Mittels {z['unsicher_mittel']:.4f} s\n")
    if 'A_gegen_B_grad' in E: f.write(f"Weg A gegen Weg B in {E['A_gegen_B_grad']['n']} gemeinsamen Bildern: Mittel {E['A_gegen_B_grad']['mittel']:.2f}°, Streuung {E['A_gegen_B_grad']['streuung']:.2f}°\n")
    f.write('\nMaßgebliche Abschnitte (Weg A, Sinus-Ausgleich):\n')
    for A in E['auswahl']: f.write(f"  {A['von']:5.2f}–{A['bis']:5.2f} s: T = {A['T_exp']:.4f} ± {A['dT_exp']:.4f} s, Rest {A['rest_exp']:.2f}°, Amplitude {A['amplitude_grad']:.1f}°\n")
    if Tp and E.get('T_p_unsicher'): f.write(f"gewichtet: T_p = {Tp:.4f} ± {E['T_p_unsicher']:.4f} s (Streuung der Abschnitte {E['T_p_streuung_abschnitte']:.4f} s)\n")
    if Tp:
        f.write(f"\nT_p = {Tp:.4f} s → T_kipp = T_p/(2π) = {Tp/(2*np.pi)*1e3:.1f} ms;  J/(m l) = g (T_p/2π)² = {E['J_durch_ml_m']*1e3:.1f} mm\n")
        f.write(f"Konstruktion: J = {J_BAU*1e3:.2f}e-3 kg m², l = {L_SP*1e3:.1f} mm → T_p = {E['T_p_bau']:.3f} s, T_kipp = {np.sqrt(J_BAU/(M_KG*G*L_SP))*1e3:.1f} ms\n")
        f.write(f"Mit l der Konstruktion: J_Achse aus dem Video = {E['J_achse_mit_l_bau']*1e3:.2f}e-3 kg m²\n")
print(open('radpendel_auswertung.txt').read())
