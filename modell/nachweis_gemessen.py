#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nachweis_gemessen.py — Aufgabe F1 (28.09.2026): der vorhandene Regler gegen die GEMESSENE Strecke.

Die geprüften Bausteine (segway_modell, segway_entwurf, pruefung_entwurf, gegenprobe_firmware) bleiben
unverändert; dieses Programm setzt nur andere Zahlen ein und lässt denselben Nachweis laufen. Ergebnisse in
einem eigenen Ordner, damit der Nachweis vom 25.08. (bericht_entwurf.txt, entwurf1..3.png) als Vergleich stehen bleibt.

Herkunft der Zahlen (jede Zeile eine Quelle):
  Reglerbeiwerte, Filter, Rampe, Rad, Schritte, Takt   aus dem Quelltext der Firmware gelesen (gegenprobe_firmware)
  m = 1,248 kg                                          gewogen 28.09.
  J/(m l) = g (T_p/2π)²                                 Radpendel.mp4, T_p = 0,6702 ± 0,0041 s (radpendel_auswertung.json)
  l = 44,5 mm                                           Konstruktion (traegheit_aus_konstruktion.json); J folgt aus J/(m l) und l
  w = 71 mm, u = 39 mm                                  Sensorlage gemessen 28.09. (103 mm über Boden, Rad Ø 64)
  Rad Ø 64 mm gemessen; die Firmware rechnet noch mit 66 (r_rad wird aus der Firmware gelesen; 3 % Maßstab)
  d = 0,002 … 0,012 Nms                                 Spanne aus dem Abklingen des Radpendels (Motoren stromlos); Nennfall 0,002
  tau_mot = 2 ms                                        ANNAHME wie bisher (Verzug des Treibers), Empfindlichkeit wird gerechnet
  a_max = A_MAX_VORGABE der Firmware                    Rampe; die Motorgrenze mit 1,25 kg ist noch zu messen (F3)

Aufruf: python3 nachweis_gemessen.py [--kurz]   (--kurz: nur die lineare Analyse, ohne die langen Simulationen)
"""
import json, sys, time
from pathlib import Path
import numpy as np
import segway_modell as M
import segway_entwurf as E
import pruefung_entwurf as P
import gegenprobe_firmware as GF

H = Path(__file__).resolve().parent
AUS = H / 'gemessen_2026-09-28'; AUS.mkdir(exist_ok=True)
K = H.parent / 'Konstruktion'
RP = json.load(open(K / 'radpendel_auswertung.json'))
TK = json.load(open(K / 'traegheit_aus_konstruktion.json'))
FW = GF.beiwerte_aus_sketch()

G = 9.81
M_KG = 1.248
L_M = TK['l_m']
T_P = RP['T_p_s']; DT_P = RP.get('T_p_unsicher') or 0.0
T_KIPP = T_P / (2*np.pi)
J_DURCH_ML = G * T_KIPP**2
J_M = J_DURCH_ML * M_KG * L_M
W_S, U_S = 0.071, 0.039                     # Sensor 103 mm über Boden, Rad Ø 64 gemessen → 71 mm über der Achse

# Regler und Antrieb aus der Firmware
ENTWURF = dict(N_K=FW['REGLER_K'], N_TN=FW['REGLER_TN'], N_TV=FW['REGLER_TV'], NK_K=FW['NULL_K'], NK_TN=FW['NULL_TN'],
               Q_ANGLE=FW['Q_WINKEL_WERT'], Q_BIAS=FW['Q_NULL_WERT'], R_MEASURE=FW['R_MESS_WERT'],
               a_max=FW['A_MAX'], MAX_SPEED=FW['MAX_HZ'], r_rad=FW['RAD_DURCHMESSER']/2, Ns=int(FW['SCHRITTE_JE_UMDREHUNG']),
               f_gitter=1/FW['DT_SOLL'], f_dmp=1/FW['DT_SOLL'])
GEMESSEN = dict(m=M_KG, l=L_M, J=J_M, sensor_w=W_S, sensor_u=U_S, d=0.002)
ALT = dict(m=0.35, l=0.12, J=0.35*0.12**2*4/3, sensor_w=0.05, sensor_u=0.04, d=0.002)      # der Nachweis vom 25.08.

def linear(fall):
    p = P.parameter({**ENTWURF, **fall})
    k = E.kennzahlen(p)
    return dict(t_kipp_ms=1e3*p.t_kipp, zmax=k['zmax'], abkling_s=k.get('t_abkling'),
                reserve_hoch=E.verstaerkungsreserve(p), reserve_ab=E.abschwaechreserve(p), k=k)

def main():
    kurz = '--kurz' in sys.argv
    z = []
    def sag(t=''): z.append(t); print(t, flush=True)
    sag('NACHWEIS DES VORHANDENEN REGLERS GEGEN DIE GEMESSENE STRECKE — 28.09.2026 (Aufgabe F1)')
    sag('=' * 96)
    sag(f'Firmware gelesen: K = {ENTWURF["N_K"]:.6f} m/s je rad, Tn = {ENTWURF["N_TN"]:.6f} s, Tv = {ENTWURF["N_TV"]:.6f} s, '
        f'Nullpunkt K = {ENTWURF["NK_K"]:.6f}, Tn = {ENTWURF["NK_TN"]:.6f} s; Q = {ENTWURF["Q_ANGLE"]}/{ENTWURF["Q_BIAS"]}, R = {ENTWURF["R_MEASURE"]:.3f}')
    sag(f'                  Rad Ø {2000*ENTWURF["r_rad"]:.0f} mm, {ENTWURF["Ns"]} Schritte/U, Takt {1e3/ENTWURF["f_gitter"]:.0f} ms, Rampe {ENTWURF["a_max"]:.2f} m/s², Grenze {ENTWURF["MAX_SPEED"]:.0f} Hz')
    sag(f'Gemessen:         m = {M_KG:.3f} kg; T_p = {T_P:.4f} ± {DT_P:.4f} s → T_kipp = {1e3*T_KIPP:.1f} ms, J/(m l) = {1e3*J_DURCH_ML:.1f} mm;'
        f' l = {1e3*L_M:.1f} mm (Konstruktion) → J = {1e3*J_M:.2f}e-3 kg m²; w = {1e3*W_S:.1f} mm, u = {1e3*U_S:.0f} mm')
    sag()
    sag('A  LINEARE ANALYSE (abgetasteter Kreis, 16 Zustände) — alt gegen gemessen und Empfindlichkeiten')
    sag('-' * 96)
    sag(f'{"Fall":<58}{"T_kipp":>8}{"|z|max":>9}{"Abkling":>9}{"Res.hoch":>10}{"Res.ab":>8}')
    faelle = [('Nachweis 25.08. (m 0,35, l 0,12, Stab-J)', ALT), ('gemessen, Nennfall (d = 0,002)', GEMESSEN),
              ('gemessen, d = 0,012 Nms', {**GEMESSEN, 'd': 0.012}),
              ('gemessen, T_p − Unsicherheit', {**GEMESSEN, 'J': G*((T_P-DT_P)/(2*np.pi))**2*M_KG*L_M}),
              ('gemessen, T_p + Unsicherheit', {**GEMESSEN, 'J': G*((T_P+DT_P)/(2*np.pi))**2*M_KG*L_M}),
              ('gemessen, l = 40 mm (J/(m l) fest)', {**GEMESSEN, 'l': 0.040, 'J': J_DURCH_ML*M_KG*0.040}),
              ('gemessen, l = 50 mm (J/(m l) fest)', {**GEMESSEN, 'l': 0.050, 'J': J_DURCH_ML*M_KG*0.050}),
              ('gemessen, tau_mot = 6 ms', {**GEMESSEN, 'tau_mot': 0.006}),
              ('gemessen, Sensor w = 0 (zum Vergleich)', {**GEMESSEN, 'sensor_w': 0.0})]
    LIN = {}
    for name, fall in faelle:
        r = linear(fall); LIN[name] = {k: v for k, v in r.items() if k != 'k'}
        ab = r['abkling_s']
        sag(f'{name:<58}{r["t_kipp_ms"]:>7.1f}ms{r["zmax"]:>9.4f}{(f"{ab:.3f} s" if ab else "—"):>9}{r["reserve_hoch"]:>10.2f}{r["reserve_ab"]:>8.3f}')
    sag()
    sag('Res.hoch = Faktor, um den alle Reglerbeiwerte steigen dürfen, bis der Kreis instabil wird; Res.ab = Faktor, auf den sie sinken dürfen.')
    ergebnis = dict(datum='2026-09-28', firmware=FW, entwurf=ENTWURF, gemessen=GEMESSEN, alt=ALT, T_p_s=T_P, dT_p_s=DT_P,
                    T_kipp_s=T_KIPP, J_durch_ml_m=J_DURCH_ML, J_kgm2=J_M, linear=LIN)
    json.dump(ergebnis, open(AUS / 'nachweis_gemessen.json', 'w'), indent=1, ensure_ascii=False, default=float)
    (AUS / 'nachweis_gemessen_linear.txt').write_text('\n'.join(z) + '\n', encoding='utf-8')
    if kurz: return 0
    # B: der vollständige nichtlineare Nachweis mit den gemessenen Zahlen (dasselbe Programm wie am 25.08.)
    t0 = time.time()
    P.bericht({**ENTWURF, **GEMESSEN}, datei=str(AUS / 'bericht_gemessen.txt'))
    P.bild_aufrichten({**ENTWURF, **GEMESSEN}, datei=str(AUS / 'gemessen1_aufrichten.png'))
    P.bild_nullpunkt({**ENTWURF, **GEMESSEN}, datei=str(AUS / 'gemessen2_nullpunkt.png'))
    P.bild_vergleich({**ENTWURF, **GEMESSEN}, datei=str(AUS / 'gemessen3_vergleich.png'))
    print(f'\nnichtlinearer Nachweis fertig, {time.time()-t0:.0f} s; Ergebnisse in {AUS}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
