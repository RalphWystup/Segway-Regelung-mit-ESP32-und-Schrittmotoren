#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gegenprobe Firmware = Modell, als Lauf (Anforderung A10, Anhang D Schritt 5).

Die Firmware-Kette aus gegenprobe_firmware.py (Zeile für Zeile aus segway_regelung.ino, Beiwerte aus dem Quelltext
gelesen) und die vier Schichten des Modells (segway_modell.py) bekommen über 3000 Takte dieselben Eingänge —
Rohwinkel und Drehrate als synthetische Verläufe mit Kreiselnullpunkt, Fahrbefehl null — und müssen denselben Istwinkel
und dieselbe Schrittfrequenz liefern. Streckenzahlen aus nachweis_gemessen (gemessen 28.09.2026), Reglerzahlen aus der
Firmware. Ausgabe: größte Abweichung in Grad und Hertz; ok, wenn < 1e-6 Grad (float32-Rundung der Firmware ist hier
nicht nachgebildet, beide rechnen in double).
  python3 gegenprobe_lauf.py
"""
import numpy as np
import segway_modell as M
import pruefung_entwurf as P
import gegenprobe_firmware as GF
import nachweis_gemessen as NG

w = GF.beiwerte_aus_sketch()
p = P.parameter({**NG.ENTWURF, **NG.GEMESSEN})
# Schnittstellenzahlen der Firmware gegen die Modellzahlen — dieselbe Quelle, hier nachgesehen
assert abs(p.v_je_hz - w["SCHRITTWEITE"]) < 1e-12 and p.MAX_SPEED == w["MAX_HZ"] and abs(p.a_max - w["A_MAX"]) < 1e-12 and abs(p.NK_MAX - w["GRENZE"]) < 1e-9, (p.v_je_hz, w["SCHRITTWEITE"], p.NK_MAX, w["GRENZE"])
dt = w["DT_SOLL"]; n = 3000
fw = GF.FirmwareKette(w); fw.eingeschwungen_starten(dt)
erf = M.Winkelerfassung(p); erf.start(0.0, dt)
reg = M.Winkelregler(p); mot = M.Motorausgabe(p); nk = M.Nullpunktkorrektur(p)
rng = np.random.default_rng(20260928)
dmax_w = dmax_f = 0.0
for k in range(n):
    t = k * dt
    roh = 2.0*np.sin(2*np.pi*0.7*t) + 0.3*np.sin(2*np.pi*5*t) + rng.normal(0, 0.05)
    rate = 2.0*2*np.pi*0.7*np.cos(2*np.pi*0.7*t) + 0.3*2*np.pi*5*np.cos(2*np.pi*5*t) + 0.2 + rng.normal(0, 0.05)
    # Firmware
    w_fw, f_fw = fw.takt(roh, rate, 0.0, dt)
    # Modell, in der Reihenfolge der Firmware: Schicht 4, 1, 2, 3
    erf.nullpunkt = nk.rechne(mot.v, mot.weg, 0.0, dt)
    winkel_ist, drehrate_ist = erf.rechne(roh, rate, mot.v, dt)
    v_soll = reg.rechne(winkel_ist, drehrate_ist, 0.0, p.v_max, dt)
    f_m = mot.ausgeben(v_soll, dt)
    dmax_w = max(dmax_w, abs(np.rad2deg(winkel_ist) - w_fw)); dmax_f = max(dmax_f, abs(f_m - f_fw))
gut = dmax_w < 1e-6 and dmax_f < 1e-3
print(f"{'ok    ' if gut else 'FEHLER'} Firmware = Modell über {n} Takte: größte Abweichung {dmax_w:.2e} Grad, {dmax_f:.2e} Hz "
      f"(Rad {2000*p.r_rad:.0f} mm, Schrittweite {1e3*w['SCHRITTWEITE']:.4f} mm, K {w['REGLER_K']}, Tn {w['REGLER_TN']}, Tv {w['REGLER_TV']})")
raise SystemExit(0 if gut else 1)
