# -*- coding: utf-8 -*-
"""
suche_entwurf.py — Auslegung auf Stabilitaetsreserve im schlechtesten Fall

Nicht der Nennfall wird bewertet, sondern die ganze Spanne der Groessen, die
am Geraet nicht genau bekannt sind. Ein Entwurf gilt nur dann als brauchbar,
wenn er in JEDER Ecke dieser Spanne stabil ist. Unter den brauchbaren wird
der mit der groessten Verstaerkungsreserve gewaehlt.
"""

import itertools
import numpy as np
import segway_modell as M
import segway_entwurf as E


# --- Spanne der unsicheren Groessen ---------------------------------------
#  Alle Werte sind entweder gemessen (dann eng) oder geschaetzt (dann weit).
SPANNE = dict(
    m        = (0.25, 0.50),    # kg  Masse, Manuskript nennt 0,35
    l        = (0.08, 0.18),    # m   Schwerpunkthoehe, Manuskript 0,12
    j_faktor = (0.70, 1.50),    # -   Traegheitsmoment gegen Stabnaeherung
    tau_mot  = (0.001, 0.006),  # s   Verzug des Treibers
    sensor_w = (0.00, 0.10),    # m   Einbauhoehe des Sensors
)
NENN = dict(m=0.35, l=0.12, j_faktor=1.0, tau_mot=0.002, sensor_w=0.05)

# Guete der Beschleunigungskompensation. Sie ist keine Eigenschaft des
# Fahrzeugs, sondern der Bauart des Reglers, deshalb steht sie getrennt:
#   0,0        Weg A - strikte Trennung, Schicht 1 bekommt nichts von Schicht 3
#   0,6 - 1,0  Weg B - Kompensation eingebaut, Guete aber unsicher
KOMP_A = (0.0,)
KOMP_B = (0.60, 0.80, 1.00)


def ecken(spanne=SPANNE, komp=KOMP_A, mit_mitte=True):
    """Alle Ecken der Unsicherheitsspanne, dazu der Nennfall."""
    namen = list(spanne)
    faelle = []
    for kombi in itertools.product(*[spanne[n] for n in namen]):
        for a in komp:
            f = dict(zip(namen, kombi))
            f["a_komp_anteil"] = a
            faelle.append(f)
    if mit_mitte:
        for a in komp:
            f = dict(NENN)
            f["a_komp_anteil"] = a
            faelle.append(f)
    return faelle


def parameter(fall, entwurf):
    d = dict(m=fall["m"], l=fall["l"], r_rad=0.033, Ns=1600, MAX_SPEED=6000,
             f_dmp=250.0, f_gitter=250.0, a_max=15.0, sensor_art="kalman",
             feinschritte=32, tau_mot=fall["tau_mot"],
             sensor_w=fall["sensor_w"], a_komp_anteil=fall["a_komp_anteil"])
    d.update(entwurf)
    p = M.Parameter(**d)
    p.J = fall["j_faktor"] * p.m * p.l ** 2 * 4.0 / 3.0
    return p


def bewerte_entwurf(entwurf, faelle, mit_reserve=False):
    """
    Schlechtester Fall der ganzen Spanne.

    Erst wird nur auf Stabilitaet geprueft - das ist billig. Die Reserven
    kosten das Vierzigfache und werden deshalb nur fuer Entwuerfe
    gerechnet, die die erste Huerde genommen haben.
    """
    zmax = 0.0
    for fall in faelle:
        p = parameter(fall, entwurf)
        if p.N_K / p.N_TN <= p.g:
            return dict(gueltig=False, grund="ki <= g")
        k = E.kennzahlen(p)
        zmax = max(zmax, k["zmax"])
        if k["zmax"] >= 1.0:
            return dict(gueltig=False, grund="instabil", zmax=zmax, fall=fall)
    if not mit_reserve:
        return dict(gueltig=True, zmax=zmax)
    hoch = min(E.verstaerkungsreserve(parameter(f, entwurf)) for f in faelle)
    ab = max(E.abschwaechreserve(parameter(f, entwurf)) for f in faelle)
    return dict(gueltig=True, zmax=zmax, reserve=hoch, reserve_ab=ab)
