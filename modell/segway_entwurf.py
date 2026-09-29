# -*- coding: utf-8 -*-
"""
segway_entwurf.py — Auslegung des Segway-Reglers auf Stabilitaetsreserve

Grundlage ist nicht das Probieren, sondern der abgetastete geschlossene Kreis
als lineares Zustandsmodell. Es enthaelt jedes Glied, das im Geraet wirklich
vorkommt:

    Strecke        inverses Pendel auf geschwindigkeitsgefuehrtem Wagen
    Antrieb        Verzug erster Ordnung des Treibers
    Sensor         Tiefpass des MPU6050 auf Beschleunigung, Drehrate, Neigung
    Schicht 1      Kalman mit Winkel UND Kreiselnullpunkt, wahlweise mit
                   Abzug der bekannten eigenen Beschleunigung
    Schicht 2      PID auf den Istwinkel, D-Anteil wahlweise vom Kreisel
    Schicht 3      Motorausgabe (linear, also ohne Begrenzung und Totzone)
    Schicht 4      PI auf die ausgegebene Geschwindigkeit
    Rechenzeit     eine Taktverzoegerung der Stellgroesse

Aus den Eigenwerten der Zustandsmatrix folgt unmittelbar:

    stabil          alle |z| < 1
    Abklingzeit     -T / ln|z|max
    Reserve         um welchen Faktor die Reglerbeiwerte steigen oder
                    sinken duerfen, bis der Kreis instabil wird

Was hier NICHT drinsteht, weil es unstetig ist: die Frequenzbegrenzung,
die Totzone der Motorausgabe und die Aenderungsgrenze. Diese drei werden
nichtlinear geprueft, in pruefung_entwurf.py.

Das Modell wird gegen die nichtlineare Simulation geprueft, damit die
Linearisierung nicht fuer sich steht - siehe pruefe_gegen_simulation().
"""

import numpy as np


# ---------------------------------------------------------------------------
#  Ein Zustandsschritt des GESAMTEN Kreises, linearisiert
# ---------------------------------------------------------------------------
#  Zustandsvektor z (16 Groessen):
#    0 th        wahre Neigung                         [rad]
#    1 om        Drehrate                              [rad/s]
#    2 v         Wagengeschwindigkeit                  [m/s]
#    3 a_lp      Beschleunigung nach dem 42-Hz-Tiefpass [m/s2]
#    4 om_lp     Drehrate nach dem Tiefpass            [rad/s]
#    5 th_lp     Neigung nach dem Tiefpass             [rad]
#    6 a_glatt   geglaettete eigene Beschleunigung     [m/s2]
#    7 k_ang     Winkelschaetzung des Kalman           [Grad]
#    8 k_bias    Nullpunktschaetzung des Kalman        [Grad/s]
#    9 i_in      Integrator innerer Kreis              [m/s]
#   10 e_alt     letzter Istwinkel (fuer den D-Anteil)  [rad]
#   11 d_zust    geglaetteter D-Anteil                 [rad/s]
#   12 i_nk      Integrator Nullpunktkorrektur         [rad]
#   13 v_aus     zuletzt ausgegebene Geschwindigkeit   [m/s]
#   14 weg       Weg aus der Schrittfrequenz           [m]
#   15 v_vor     Geschwindigkeit des vorigen Feinschritts [m/s]
# ---------------------------------------------------------------------------

N_Z = 16
G2R = np.pi / 180.0
R2G = 180.0 / np.pi


_STATIONAER = {}


def kalman_stationaer(Q_ANGLE, Q_BIAS, R, dt, n=200000, toleranz=1e-14):
    """
    Stationaere Verstaerkungen K0, K1 des Filters aus dem Sketch.
    Die Kovarianzgleichung wird bis zum Stillstand iteriert; das ist die
    Loesung der zugehoerigen Riccati-Gleichung.
    """
    schluessel = (Q_ANGLE, Q_BIAS, R, dt)
    if schluessel in _STATIONAER:
        # Die Verstaerkungen haengen nur von Q, R und Takt ab, nicht von
        # der Mechanik. Ohne dieses Gedaechtnis wird die Riccati-Gleichung
        # in jedem Fall der Unsicherheitsspanne neu geloest.
        return _STATIONAER[schluessel]
    P = [[0.0, 0.0], [0.0, 0.0]]
    K0 = K1 = 0.0
    for i in range(n):
        K0_vor, K1_vor = K0, K1
        P[0][0] += dt * (dt * P[1][1] - P[0][1] - P[1][0] + Q_ANGLE)
        P[0][1] -= dt * P[1][1]
        P[1][0] -= dt * P[1][1]
        P[1][1] += Q_BIAS * dt
        S = P[0][0] + R
        K0 = P[0][0] / S
        K1 = P[1][0] / S
        t00, t01 = P[0][0], P[0][1]
        P[0][0] -= K0 * t00
        P[0][1] -= K0 * t01
        P[1][0] -= K1 * t00
        P[1][1] -= K1 * t01
        if i > 10 and abs(K0 - K0_vor) < toleranz and abs(K1 - K1_vor) < toleranz:
            break
    _STATIONAER[schluessel] = (K0, K1)
    return K0, K1


def schritt(z, p, K0, K1):
    """
    Ein Regeltakt, linearisiert um die aufrechte Lage.

    Bildet segway_modell Zeile fuer Zeile nach - Strecke, Sensornachbildung
    und die vier Schichten - nur mit sin(th)=th, cos(th)=1, arctan(a/g)=a/g
    und ohne Begrenzungen. Die Uebereinstimmung mit der nichtlinearen
    Simulation wird nachgewiesen und nicht angenommen.
    """
    z = np.array(z, dtype=float)
    T = 1.0 / p.f_gitter
    n_u = p.feinschritte
    dt = T / n_u
    tau_lp = p.t_dlpf

    th, om, v = z[0], z[1], z[2]
    a_lp, om_lp, th_lp = z[3], z[4], z[5]
    v_aus = z[13]                        # Ausgabe der Schicht 3, im Raster fest

    # ---- Strecke und Sensornachbildung im Feintakt ----
    for _ in range(n_u):
        dv = (v_aus - v) / p.tau_mot     # = Beschleunigung des Wagens
        v = v + dv * dt
        domega = (p.m * p.g * p.l * th - p.m * p.l * dv - p.d * om) / p.J
        om = om + domega * dt
        th = th + om * dt
        a_schein = dv + p.sensor_w * domega
        a_lp += (a_schein - a_lp) * dt / tau_lp
        th_lp += (th - th_lp) * dt / tau_lp
        om_lp += (om - om_lp) * dt / tau_lp

    roh = th_lp - a_lp / p.g             # gemeldeter Rohwinkel [rad]
    drehrate = om_lp                     # gemeldete Drehrate [rad/s]

    # ---- Schicht 4: Nullpunktkorrektur (liegt darueber) ----
    i_nk = z[12]
    weg = z[14] + v_aus * T
    v_wunsch = -p.NW_K * weg if p.nk_art == "weg" else 0.0
    if p.nk_art in ("geschwindigkeit", "weg"):
        e_v = v_wunsch - v_aus
        i_nk = i_nk + (p.NK_K / p.NK_TN) * e_v * T
        nullpunkt = p.NK_K * e_v + i_nk
    else:
        nullpunkt = 0.0

    # ---- Schicht 1: Winkelerfassung ----
    a_glatt = z[6]
    v_vor = z[15]
    if p.a_komp_anteil != 0.0:
        a_glatt = a_glatt + ((v_aus - v_vor) / T - a_glatt) * T / tau_lp
        roh = roh + p.a_komp_anteil * a_glatt / p.g
    v_vor = v_aus
    k_ang, k_bias = z[7], z[8]
    k_ang = k_ang + T * (drehrate * R2G - k_bias)
    y = roh * R2G - k_ang
    k_ang = k_ang + K0 * y
    k_bias = k_bias + K1 * y
    winkel_ist = k_ang * G2R - nullpunkt
    drehrate_ist = drehrate - k_bias * G2R

    # ---- Schicht 2: Winkelregler ----
    if p.d_quelle == "kreisel":
        d_zust = drehrate_ist
    else:
        d_zust = z[11] + ((winkel_ist - z[10]) / T - z[11]) * T / max(p.N_TD, T)
    i_in = z[9] + (p.N_K / p.N_TN) * winkel_ist * T
    v_cmd = p.N_K * winkel_ist + i_in + p.N_K * p.N_TV * d_zust

    # ---- Schicht 3: Motorausgabe ----
    # Im linearen Modell ohne Begrenzung und ohne Totzone; beides ist
    # unstetig und wird nichtlinear geprueft (pruefung_entwurf.py).
    return np.array([th, om, v, a_lp, om_lp, th_lp, a_glatt,
                     k_ang, k_bias, i_in, winkel_ist, d_zust, i_nk, v_cmd,
                     weg, v_vor])


def zustandsmatrix(p):
    """Systemmatrix des geschlossenen Kreises durch Anwendung auf Einheitsvektoren."""
    dt = 1.0 / p.f_gitter
    K0, K1 = kalman_stationaer(p.Q_ANGLE, p.Q_BIAS, p.R_MEASURE, dt)
    A = np.zeros((N_Z, N_Z))
    null = schritt(np.zeros(N_Z), p, K0, K1)
    for j in range(N_Z):
        e = np.zeros(N_Z)
        e[j] = 1.0
        A[:, j] = schritt(e, p, K0, K1) - null
    return A, K0, K1


def kennzahlen(p):
    """Eigenwerte und daraus die Stabilitaetsreserve."""
    A, K0, K1 = zustandsmatrix(p)
    # Je nach Bauart laufen einzelne Zustaende mit, ohne zum Kreis zu
    # gehoeren - der Wegschaetzer bei nk_art="geschwindigkeit", die
    # geglaettete Eigenbeschleunigung ohne Kompensation, der alte Istwinkel
    # bei D-Anteil aus dem Kreisel. Ihre Eigenwerte liegen auf 0 oder 1 und
    # wuerden das Ergebnis verdecken. Sie werden abgetrennt - aber erst,
    # nachdem geprueft ist, dass sie wirklich nicht zurueckwirken.
    lose = [j for j in range(A.shape[0])
            if np.max(np.abs(np.delete(A[:, j], j))) < 1e-12]
    if lose:
        A = np.delete(np.delete(A, lose, axis=0), lose, axis=1)
    ew = np.linalg.eigvals(A)
    betrag = np.abs(ew)
    imax = int(np.argmax(betrag))
    zmax = betrag[imax]
    T = 1.0 / p.f_gitter
    if zmax >= 1.0:
        t_ab = np.inf
    else:
        t_ab = -T / np.log(zmax)
    # Frequenz des langsamsten Anteils
    w = np.angle(ew[imax]) / T
    return dict(zmax=zmax, stabil=zmax < 1.0, t_abkling=t_ab,
                f_langsam=abs(w) / (2 * np.pi), ew=ew, K0=K0, K1=K1)


def verstaerkungsreserve(p, bis=20.0):
    """Um welchen Faktor duerfen alle Reglerbeiwerte steigen, bis es kippt."""
    from copy import copy
    lo, hi = 1.0, bis
    q = copy(p)
    q.N_K = p.N_K * hi
    q.NK_K = p.NK_K * hi
    if kennzahlen(q)["stabil"]:
        return hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        q = copy(p)
        q.N_K = p.N_K * mid
        q.NK_K = p.NK_K * mid
        if kennzahlen(q)["stabil"]:
            lo = mid
        else:
            hi = mid
    return lo


def abschwaechreserve(p, ab=0.02):
    """Um welchen Faktor duerfen die Beiwerte sinken, bis es kippt."""
    from copy import copy
    lo, hi = ab, 1.0
    q = copy(p)
    q.N_K = p.N_K * lo
    q.NK_K = p.NK_K * lo
    if kennzahlen(q)["stabil"]:
        return lo
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        q = copy(p)
        q.N_K = p.N_K * mid
        q.NK_K = p.NK_K * mid
        if kennzahlen(q)["stabil"]:
            hi = mid
        else:
            lo = mid
    return hi


# ---------------------------------------------------------------------------
#  Nachweis: lineares Modell gegen die nichtlineare Simulation
# ---------------------------------------------------------------------------

def pruefe_gegen_simulation(p, theta0_grad=0.02, dauer=4.0):
    """
    Beide Modelle mit derselben kleinen Anfangsneigung starten, ohne Rauschen,
    ohne Sensorfehler. Bei kleinem Winkel muessen sie denselben Verlauf
    liefern; tun sie das nicht, stimmt eines von beiden nicht.
    """
    import segway_modell as M

    q = M.Parameter(**{k: getattr(p, k) for k in dir(p)
                       if not k.startswith("_") and
                       not callable(getattr(p, k)) and
                       k not in ("J", "v_je_hz", "v_max", "t_kipp")})
    q.J = p.J
    q.rausch_grad = 0.0
    q.gyro_rausch = 0.0
    q.gyro_bias = 0.0
    q.s_versatz = 0.0
    erg = M.simuliere(q, dauer=dauer, theta0_grad=theta0_grad,
                      regler="entwurf")

    A = zustandsmatrix(p)[0]
    z = np.zeros(N_Z)
    z[0] = np.deg2rad(theta0_grad)       # Neigung
    z[5] = z[0]                          # Tiefpass startet auf demselben Wert
    z[7] = theta0_grad                   # Kalman startet auf dem wahren Winkel
    lin = []
    for _ in range(len(erg["t"])):
        lin.append(np.rad2deg(z[0]))
        z = A @ z
    lin = np.array(lin)

    fehler = np.max(np.abs(lin - erg["theta"]))
    bezug = max(np.max(np.abs(erg["theta"])), 1e-12)
    return dict(linear=lin, nichtlinear=erg["theta"], t=erg["t"],
                fehler=fehler, fehler_rel=fehler / bezug)
