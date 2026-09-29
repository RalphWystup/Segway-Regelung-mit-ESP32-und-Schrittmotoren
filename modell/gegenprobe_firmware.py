# -*- coding: utf-8 -*-
"""
gegenprobe_firmware.py — rechnet die Firmware gegen das Modell

Das Modell ist geprueft, die Firmware ist geschrieben. Was noch fehlt, ist
der Nachweis, dass beide DASSELBE rechnen. Dazu wird der Rechenweg der
Firmware hier ein zweites Mal aufgeschrieben - unabhaengig, Zeile fuer Zeile
aus dem Quelltext des Sketches - und mit denselben Eingangsgroessen
gefuettert wie die Bausteine des Modells.

Stimmen beide auf Rechengenauigkeit ueberein, dann gilt jede Aussage des
Modells auch fuer das Geraet. Weichen sie ab, ist einer von beiden falsch.

Die Beiwerte werden aus dem Sketch GELESEN, nicht abgeschrieben - sonst
prueft man nur seine eigene Abschrift.
"""

import re
import io
import numpy as np

import segway_modell as M

SKETCH = "../Arduino/segway_regelung/segway_regelung.ino"


def beiwerte_aus_sketch(pfad=SKETCH):
    """Liest die Zahlenwerte unmittelbar aus dem Quelltext."""
    quelle = io.open(pfad, encoding="utf-8").read()
    werte = {}
    muster = re.compile(
        r"static\s+const\s+float\s+(\w+)\s*=\s*([-+0-9.eE]+)f?\s*;")
    for name, zahl in muster.findall(quelle):
        werte[name] = float(zahl)
    # Werte, die als constexpr in den Klassen stehen
    for name, zahl in re.findall(
            r"static\s+constexpr\s+float\s+(\w+)\s*=\s*([-+0-9.eE]+)f?\s*;",
            quelle):
        werte[name] = float(zahl)
    # Groessen, die im Sketch gerechnet und nicht hingeschrieben werden.
    # Sie werden hier auf demselben Weg gebildet, damit auch ein Tippfehler
    # in der Formel auffiele.
    werte["SCHRITTE_JE_UMDREHUNG"] = float(re.search(
        r"SCHRITTE_JE_UMDREHUNG\s*=\s*(\d+)", quelle).group(1))
    werte["SCHRITTWEITE"] = (np.pi * werte["RAD_DURCHMESSER"]
                             / werte["SCHRITTE_JE_UMDREHUNG"])
    werte["V_MAX"] = werte["MAX_HZ"] * werte["SCHRITTWEITE"]
    werte["DT_SOLL"] = float(re.search(
        r"TAKT_MS\s*=\s*(\d+)", quelle).group(1)) * 0.001
    # A_MAX ist im Geraet verstellbar; geprueft wird gegen den Startwert.
    werte["A_MAX"] = werte["A_MAX_VORGABE"]
    return werte


class FirmwareKette:
    """
    Die vier Schichten, wie sie im Sketch stehen - unabhaengig nachgebaut.
    Alle Namen und Rechenschritte sind aus segway_regelung.ino uebernommen.
    """

    def __init__(self, w):
        self.w = w
        # Schicht 1
        self.m_winkel = 0.0
        self.m_kreisel_null = 0.0
        self.m_drehrate = 0.0
        self.nullpunkt = 0.0
        self.P00 = self.P01 = self.P10 = self.P11 = 0.0
        # Schicht 2
        self.i_regler = 0.0
        # Schicht 3
        self.m_v = 0.0
        self.m_f = 0.0
        self.m_weg = 0.0
        # Schicht 4
        self.i_null = 0.0

    def eingeschwungen_starten(self, dt):
        w = self.w
        P00 = P01 = P10 = P11 = 0.0
        K0_vor = -1.0
        for i in range(200000):
            P00 += dt * (dt * P11 - P01 - P10 + w["Q_WINKEL_WERT"])
            P01 -= dt * P11
            P10 -= dt * P11
            P11 += w["Q_NULL_WERT"] * dt
            S = P00 + w["R_MESS_WERT"]
            K0 = P00 / S
            K1 = P10 / S
            t00, t01 = P00, P01
            P00 -= K0 * t00
            P01 -= K0 * t01
            P10 -= K1 * t00
            P11 -= K1 * t01
            if i > 10 and abs(K0 - K0_vor) < 1e-14:
                break
            K0_vor = K0
        self.P00, self.P01, self.P10, self.P11 = P00, P01, P10, P11

    def takt(self, roh_grad, drehrate_grad, fahrbefehl, dt):
        w = self.w

        # ---- Schicht 4 ----
        e = fahrbefehl - self.m_v
        roh_nk = w["NULL_K"] * e + self.i_null
        if abs(roh_nk) < w["GRENZE"] or (roh_nk * e) < 0.0:
            self.i_null += (w["NULL_K"] / w["NULL_TN"]) * e * dt
            self.i_null = float(np.clip(self.i_null, -w["GRENZE"], w["GRENZE"]))
        self.nullpunkt = float(np.clip(w["NULL_K"] * e + self.i_null,
                                       -w["GRENZE"], w["GRENZE"])) * 57.2957795

        # ---- Schicht 1 ----
        rate = drehrate_grad - self.m_kreisel_null
        self.m_winkel += dt * rate
        self.P00 += dt * (dt * self.P11 - self.P01 - self.P10 + w["Q_WINKEL_WERT"])
        self.P01 -= dt * self.P11
        self.P10 -= dt * self.P11
        self.P11 += w["Q_NULL_WERT"] * dt
        S = self.P00 + w["R_MESS_WERT"]
        K0 = self.P00 / S
        K1 = self.P10 / S
        y = roh_grad - self.m_winkel
        self.m_winkel += K0 * y
        self.m_kreisel_null += K1 * y
        t00, t01 = self.P00, self.P01
        self.P00 -= K0 * t00
        self.P01 -= K0 * t01
        self.P10 -= K1 * t00
        self.P11 -= K1 * t01
        self.m_drehrate = drehrate_grad - self.m_kreisel_null
        winkel_grad = self.m_winkel - self.nullpunkt

        # ---- Schicht 2 ----
        winkel_ist = winkel_grad * 0.0174532925
        drehrate = self.m_drehrate * 0.0174532925
        anteil_p = w["REGLER_K"] * winkel_ist
        anteil_d = w["REGLER_K"] * w["REGLER_TV"] * drehrate
        roh_r = anteil_p + self.i_regler + anteil_d
        if abs(roh_r) < w["V_MAX"] or (roh_r * winkel_ist) < 0.0:
            self.i_regler += (w["REGLER_K"] / w["REGLER_TN"]) * winkel_ist * dt
            self.i_regler = float(np.clip(self.i_regler, -w["V_MAX"], w["V_MAX"]))
        v_soll = float(np.clip(anteil_p + self.i_regler + anteil_d,
                               -w["V_MAX"], w["V_MAX"]))

        # ---- Schicht 3 ----
        v_soll = float(np.clip(v_soll, self.m_v - w["A_MAX"] * dt,
                               self.m_v + w["A_MAX"] * dt))
        f = v_soll / w["SCHRITTWEITE"]
        f = float(np.clip(f, -w["MAX_HZ"], w["MAX_HZ"]))
        if abs(f) < w["MIN_HZ"]:
            f = 0.0
        self.m_f = f
        self.m_v = f * w["SCHRITTWEITE"]
        self.m_weg += self.m_v * dt
        return winkel_grad, self.m_f
