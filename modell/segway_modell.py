# -*- coding: utf-8 -*-
"""
segway_modell.py — Physikalisches Modell des Segways zur Pruefung des Reglercodes

    Aufbau : ESP32, zwei Schrittmotoren, MPU6050 mit DMP
    Zweck  : Der Reglercode wird 1:1 nachgebildet und gegen ein physikalisches
             Streckenmodell laufen gelassen. Damit laesst sich am Schreibtisch
             pruefen, was der Code tut, ohne den Aufbau umzuwerfen.

===============================================================================
DIE DREI MODELLTEILE
===============================================================================

1. STRECKE — inverses Pendel auf einem GESCHWINDIGKEITSGEFUEHRTEN Wagen

   Entscheidend ist die Bauart des Antriebs. Schrittmotoren werden ueber die
   Schrittfrequenz gestellt; solange kein Schritt verloren geht, ist damit die
   Radgeschwindigkeit vorgegeben und nicht ein Moment:

       v = (2*pi*r / Ns) * f                        (Laborbericht, Gl. 3)

   Die Strecke ist also NICHT der kraftgefuehrte Wagen der Lehrbuecher. Die
   Grenze liegt in der Beschleunigung: fordert der Regler mehr, als das
   Motormoment hergibt, verliert der Motor Schritte. Das wird als
   Rampenbegrenzung a_max abgebildet.

       J * th'' = m*g*l*sin(th) - m*l*a*cos(th) - d*th' + M_stoer

2. SENSOR — MPU6050 mit DMP

   Der Beschleunigungsmesser kann Neigung und Beschleunigung nicht
   unterscheiden. Er misst die scheinbare Lotrichtung, und die kippt bei
   waagerechter Beschleunigung a um arctan(a/g):

       th_beschleunigungsmesser = th - arctan(a/g)

   Bei a = 3 m/s2 sind das bereits 17 Grad Messfehler. Der DMP zieht diesen
   Wert nur langsam nach (Zeitkonstante tau_dmp), sodass kurze Stoesse
   herausgefiltert werden, anhaltende Beschleunigung aber in den Messwert
   einlaeuft. Genau das ist die schwierige Stelle jedes Balancierfahrzeugs.

3. REGLER — 1:1 aus dem Quellcode uebernommen

   Kaskade: aussen PI auf die Geschwindigkeit (Kp, Ki der Weboberflaeche),
   innen PID auf den Winkel (feste Werte 45 / 12 / 30 im Quellcode).

===============================================================================
HERKUNFT DER ZAHLEN
===============================================================================
  AUS DEM QUELLCODE
     Raddurchmesser 63 mm, MAX_SPEED 4000 Hz, PERIOD 4 ms, Kippgrenze 30 Grad,
     alle Reglerbeiwerte und Begrenzungen

  AUS DER BIBLIOTHEK (MPU6050_6Axis_MotionApps20)
     setRate(4)                        -> Grundrate 200 Hz
     FIFO_RATE_DIVISOR = 0x01          -> DMP liefert 100 Hz
     setDLPFMode(MPU6050_DLPF_BW_42)   -> Tiefpass 42 Hz

  AUS DEM DATENBLATT MPU6050
     DLPF 42 Hz: Gruppenlaufzeit 4,8 ms

  GESCHAETZT (jeweils unten einzeln einstellbar, Empfindlichkeit wird gerechnet)
     Masse, Schwerpunktlage, Traegheitsmoment,
     Beschleunigungsgrenze, Zeitkonstante der DMP-Fusion, Rauschen

  VOM NUTZER BESTAETIGT
     16-fach Mikroschritt -> Ns = 3200 Schritte je Umdrehung

Aufruf:   python3 segway_modell.py
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# ===========================================================================
# 1  PARAMETER
# ===========================================================================

class Parameter:
    """Alle Kenngroessen an einer Stelle, Herkunft je Zeile vermerkt."""

    # --- Mechanik ----------------------------------------------------------
    m = 0.90          # kg    Masse des Aufbaus                   GESCHAETZT
    l = 0.11          # m     Radachse -> Schwerpunkt             GESCHAETZT
    J = None          # kg m2 Traegheitsmoment um die Radachse    berechnet
    d = 0.002         # Nms   Lagerreibung                        GESCHAETZT
    g = 9.81          # m/s2

    # --- Antrieb -----------------------------------------------------------
    r_rad   = 0.0315  # m     Radradius (63 mm Durchmesser)       AUS CODE
    Ns      = 3200    # -     Schritte je Umdrehung               BESTAETIGT
                      #       200 Vollschritte (1,8 Grad) mal 16-fach
                      #       Mikroschritt, vom Nutzer am Treiber abgelesen
    a_max   = 15.0    # m/s2  Beschleunigungsgrenze der Motoren   GESCHAETZT
                      #       In Ihrer Fassung steht setAcceleration(50000)
                      #       Schritte je s2; mal der Schrittweite sind das
                      #       6,5 m/s2. Der Wert wird unten durchgefahren.
    MIN_SPEED = 0     # Hz    Totzone der Motorausgabe. Ihre Fassung setzt
                      #       MIN_SPEED_HZ = 80 und haelt darunter an. Das
                      #       bricht die Annahme "Frequenz = Radgeschwindig-
                      #       keit", auf der Schicht 4 beruht.
    feinschritte = 32 # -     Rechenschritte der Mechanik je Regeltakt.
                      #       Das Verfahren ist explizit nach Euler; mit 8
                      #       Schritten lag der Fehler nach einer Kipp-
                      #       zeitkonstante bei rund 1 Prozent, mit 32 bei
                      #       0,07 Prozent. Nachgewiesen in pruefungen().
    tau_mot = 0.002   # s     Verzug des Treibers                 GESCHAETZT

    # --- Sensor ------------------------------------------------------------
    f_dmp       = 100.0   # Hz   Ausgaberate des DMP              AUS BIBLIOTHEK
    t_dlpf      = 0.0048  # s    Zeitkonstante des Sensortiefpasses AUS DATENBLATT
                          #      setDLPFMode(MPU6050_DLPF_BW_42) schaltet den
                          #      42-Hz-Tiefpass ein; das Datenblatt nennt dafuer
                          #      4,8 ms Gruppenlaufzeit. Der Tiefpass wirkt auf
                          #      Beschleunigung UND Drehrate und glaettet die
                          #      kurzen Spitzen der Schrittmotoransteuerung.
    tau_dmp     = 1.0     # s    Zeitkonstante der DMP-Fusion     GESCHAETZT

    # --- Kalman-Filter wie in segway_esp32.ino / _Doku.ino ---------------
    #     Werte unveraendert aus dem Sketch uebernommen.
    # Drei Wege der Sensorfusion, wie sie in den Fassungen vorkommen:
    #   "dmp"           Quaternionenfusion im MPU6050 selbst (xxxx, Studenten)
    #   "kalman"        Kalman ausserhalb, mit Bias-Schaetzung (Ihre Fassung)
    #   "komplementaer" Hochpass Kreisel / Tiefpass Beschleunigung
    sensor_art = "kalman"
    # Einbaulage des Sensors, bezogen auf die Radachse
    sensor_u  = 0.04   # m  Versatz nach vorn      VOM NUTZER
    sensor_w  = 0.0    # m  Hoehe ueber der Achse  NOCH UNBEKANNT

    Q_ANGLE   = 0.001
    Q_BIAS    = 0.003
    R_MEASURE = 0.03
    rausch_grad = 0.05    # Grad   Rauschen des Beschleunigungswinkels
    gyro_rausch = 0.05    # Grad/s Rauschen der Drehrate
    gyro_bias   = 0.5     # Grad/s Nullpunktfehler des Kreisels, typisch
    tau_dmp_int = 5.0     # s      Zeitkonstante der Fusion im DMP

    # --- Regelung (ALLES AUS DEM QUELLCODE) --------------------------------
    f_gitter    = 250.0   # Hz  Zeitraster der Hauptschleife (PERIOD 4 ms)
    MAX_SPEED   = 4000
    MAX_PID_OUT = 500
    MAX_PI_OUT  = 2.0e6
    KIPP_GRENZE = 30.0

    ANGLE_KP = 45.0       # fest im Quellcode
    ANGLE_KI = 12.0       # fest im Quellcode
    ANGLE_KD = 30.0       # fest im Quellcode

    Kp = 240.0            # ueber Weboberflaeche verstellbar (aeusserer Kreis)
    Ki = 5.0              # ueber Weboberflaeche verstellbar (aeusserer Kreis)
    Kd = 70.0             # ueber Weboberflaeche verstellbar, WIRD NICHT BENUTZT

    SPEED_SKAL  = 200.0
    WINKEL_SKAL = 2.0e-6

    # --- Beiwerte des ueberarbeiteten Reglers ------------------------------
    # Normalform  v = K * ( e + 1/Tn INT e dt + Tv de/dt ).
    # Zahlenwerte und Rechenweg sind mit dem Sketch Segway.ino identisch.
    W_K  = 1.28      # m/s je rad   Verstaerkung Winkelregler (daempft)
    W_TN = 37.6      # ms           Nachstellzeit (richtet auf)
    W_TV = 6.6       # ms           Vorhaltezeit (wirkt wie Traegheit)
    V_K  = 0.135     # rad je m/s   Verstaerkung Geschwindigkeitskreis
    V_TN = 479.0     # ms           Nachstellzeit Geschwindigkeitskreis
    V_WINKEL_MAX = 0.035  # rad     Begrenzung des Sollwinkels

    # --- Beiwerte der Fassung segway_esp32.ino (eigener Kalman, ---------
    #     FastAccelStepper, PID unmittelbar auf die Schrittfrequenz) ------
    E_KP = 500.0     # Hz je Grad
    E_KI = 2.0       # Hz je (Grad*s)
    E_KD = 20.0      # Hz je (Grad/s)
    E_I_MAX = 8000.0 # Hz, Begrenzung des Integrators
    E_TOTZONE = 80.0 # Hz, darunter Stillstand (MIN_SPEED_HZ)

    # --- Beiwerte der Fassung segway_esp32_Doku.ino ---------------------
    #     Wichtig: dort steht kein dt in der Rechnung. Der Integralanteil
    #     lautet  integralErr += KI*err , der D-Anteil  err-prev .
    D_KP = 710.0     # Hz je Grad
    D_KI = 15.0      # Gewicht im Integral, nicht je Sekunde
    D_KD = 147.0     # Hz je Grad und Zyklus
    D_OUT_MAX = 4000.0
    D_DRIFT = 0.0006 # Grad je Zyklus, Self-Balance
    # Umrechnung Reglerausgang -> Schrittfrequenz.
    #   xxxx und Studenten:  f = clamp(out, +-500) * (MAX_SPEED/500) = out*8
    #   segway_esp32_Doku :  f = out            (Ausgang IST die Frequenz)
    D_SKAL = 1.0
    D_SETPOINT0 = 0.0   # Grad, fester Versatz des Nullpunkts (Kalibrierfehler,
                        # Schwerpunktversatz, eingelaufener Kreisel-Bias)
    mess_versatz = 0.0  # Grad, dasselbe als Fehler des gemeldeten Winkels;
                        # wirkt auf jeden Reglerzweig gleich
    D_DRIFT_NUR_BEI_FAHRT = False   # True = Abhilfe gegen die Ratsche

    # --- Nullpunktfehler als MECHANIK ---------------------------------
    # Der kalibrierte Nullpunkt findet die Senkrechte. Gesucht ist aber der
    # Gleichgewichtspunkt. Beide fallen nur zusammen, wenn der Schwerpunkt
    # genau ueber der Radachse liegt. Ein seitlicher Versatz s erzeugt das
    # Zusatzmoment m*g*s*cos(theta); der Gleichgewichtswinkel liegt dann bei
    #     theta_gl = -arctan(s/l)
    # und der Sensor MELDET ihn richtig - der Nullpunkt des REGLERS ist falsch.
    s_versatz = 0.0    # m   seitlicher Schwerpunktversatz von der Radachse

    # --- Kompensation der eigenen Beschleunigung -----------------------
    # Der Beschleunigungsmesser kann Neigung und Beschleunigung nicht
    # unterscheiden; er meldet arctan(a/g) als Scheinneigung. Bei einem
    # Schrittmotorantrieb ist die eigene Beschleunigung aber BEKANNT - sie
    # ist die Ableitung der ausgegebenen Schrittfrequenz. Man kann sie also
    # abziehen, bevor der Winkel gebildet wird:
    #     theta_acc = theta_lp - arctan( (a_gemessen - a_eigen) / g )
    # a_komp_anteil ist der Bruchteil, der wirklich verschwindet. 1,0 waere
    # vollstaendige Kenntnis; real bleibt ein Rest durch Schrittverluste,
    # Radschlupf und Laufzeit. Der Wert wird unten durchgefahren.
    a_komp_anteil = 0.0   # 0 = keine Kompensation, 1 = vollstaendig

    # --- Entwurf mit dynamischer Nullpunktkorrektur --------------------
    # Innerer Kreis: PID auf den Winkel, Schrittweite ausgeschrieben,
    #   Stellgroesse ist eine Radgeschwindigkeit [m/s], Normalform K/Tn/Tv.
    #   Auslegung fuer den Aufbau des Nutzers (m=0,35 kg, l=0,12 m):
    #   ki = 30 m/s je rad (> g, Aufrichtbedingung), wn = 10,6 rad/s, zeta = 0,7
    N_K  = 2.67     # m/s je rad     Verstaerkung (daempft)
    N_TN = 0.089    # s              Nachstellzeit -> ki = K/Tn = 30 > g
    N_TV = 0.0075   # s              Vorhaltezeit
    N_TD = 0.008    # s              Glaettung des D-Anteils (Rauschen!)

    # Aeusserer Kreis: die dynamische Nullpunktkorrektur.
    #   Messgroesse ist die Radgeschwindigkeit, und die ist bei Schrittmotoren
    #   ohne Geber bekannt:  v = 2*pi*r/Ns * f_soll.
    #   Strecke von Sollwinkel zu Geschwindigkeit ist ein Integrator mit der
    #   Verstaerkung g:  dv/dt = g*(theta_soll - theta_gl).
    #   Daraus  g*NK_K = 2*zeta_a*wn_a  und  g*NK_K/NK_TN = wn_a^2
    #   mit wn_a = 1,0 rad/s und zeta_a = 0,8 (Faktor 10 langsamer als innen).
    NK_K   = 0.163   # rad je m/s
    NK_TN  = 1.6     # s
    NK_MAX = 0.105   # rad  Begrenzung des Sollwinkels (6 Grad)

    # Aeusserster Kreis: Ortshaltung (nur bei nk_art="weg").
    NW_K   = 0.20    # (m/s) je m   -> wn_o = 0,2 rad/s
    NW_MAX = 0.30    # m/s          Begrenzung der Geschwindigkeitsvorgabe

    # Art der Nullpunktkorrektur im Entwurf:
    #   "aus"            keine  - zeigt, was ein Nullpunktfehler anrichtet
    #   "drift"          Self-Balance wie in segway_esp32_Doku.ino (nur Vorzeichen)
    #   "geschwindigkeit" langsamer PI auf die Radgeschwindigkeit (Betrag)
    #   "weg"            wie oben, zusaetzlich Ortshaltung
    nk_art = "geschwindigkeit"

    # Woher der D-Anteil kommt:
    #   "kreisel"  unmittelbar aus der Drehrate, um die Nullpunktschaetzung
    #              des Kalman bereinigt. Rauschaermer und ohne den
    #              Phasenverlust der Glaettung.
    #   "differenz" Differenz des gemeldeten Winkels, wie ueblich.
    d_quelle = "kreisel"

    # Regelsperre um den Nullpunkt. Bei xxxx steht die Idee im Quelltext
    # ("Create a dead-band to stop the motors when the robot is balanced"),
    # ist aber auskommentiert. Hier einstellbar, um sie nachzurechnen:
    #   WINKEL_SPERRE  Grad, darunter gibt der Winkelregler nichts aus
    WINKEL_SPERRE = 0.0
    NK_DRIFT = 0.0006   # Grad je Zyklus, wenn nk_art = "drift"

    def __init__(self, **aenderungen):
        for name, wert in aenderungen.items():
            if not hasattr(Parameter, name):
                raise KeyError("unbekannter Parameter: " + name)
            setattr(self, name, wert)
        if self.J is None:
            # schlanker Stab der Laenge 2*l, gedreht um das untere Ende
            self.J = self.m * self.l ** 2 * 4.0 / 3.0

    @property
    def v_je_hz(self):
        """Radgeschwindigkeit je Hertz Schrittfrequenz [m/s/Hz]."""
        return 2.0 * np.pi * self.r_rad / self.Ns

    @property
    def v_max(self):
        return self.v_je_hz * self.MAX_SPEED

    @property
    def t_kipp(self):
        """Zeitkonstante des freien Umfallens [s]."""
        return np.sqrt(self.J / (self.m * self.g * self.l))


# ===========================================================================
# 1b  KALMAN-FILTER
# ===========================================================================

class Kalman:
    """
    Nachbildung des Filters aus segway_esp32.ino, Zeile fuer Zeile.

    Zustand: Winkel und Nullpunktfehler des Kreisels (bias). Der Kreisel
    liefert die schnelle Aenderung, der Beschleunigungsmesser den langsamen
    Bezug. Anders als ein Komplementaerfilter schaetzt der Kalman den
    Kreiselnullpunkt mit und gewichtet beide Quellen ueber die
    Fehlerkovarianz P.

    Alle Winkel in Grad, Drehraten in Grad je Sekunde.
    """

    def __init__(self, q_angle, q_bias, r_measure):
        self.Q_ANGLE = q_angle
        self.Q_BIAS = q_bias
        self.R_MEASURE = r_measure
        self.angle = 0.0
        self.bias = 0.0
        self.P = [[0.0, 0.0], [0.0, 0.0]]

    def eingeschwungen_starten(self, dt, n=20000, toleranz=1e-15):
        """
        Fehlerkovarianz gleich auf ihren Endwert setzen.

        Mit P = 0 ist die Verstaerkung K0 anfangs ebenfalls null: der Filter
        hoert dem Beschleunigungsmesser rund vier Sekunden lang kaum zu und
        integriert nur den Kreisel. Ein Anfangsfehler bleibt in dieser Zeit
        stehen. Wer P gleich richtig setzt, hat vom ersten Takt an dasselbe
        Verhalten - im Modell wie im Geraet.
        """
        P = [[0.0, 0.0], [0.0, 0.0]]
        vor = None
        for _ in range(n):
            P[0][0] += dt * (dt * P[1][1] - P[0][1] - P[1][0] + self.Q_ANGLE)
            P[0][1] -= dt * P[1][1]
            P[1][0] -= dt * P[1][1]
            P[1][1] += self.Q_BIAS * dt
            S = P[0][0] + self.R_MEASURE
            K0 = P[0][0] / S
            K1 = P[1][0] / S
            t00, t01 = P[0][0], P[0][1]
            P[0][0] -= K0 * t00
            P[0][1] -= K0 * t01
            P[1][0] -= K1 * t00
            P[1][1] -= K1 * t01
            if vor is not None and abs(K0 - vor) < toleranz:
                break
            vor = K0
        self.P = P
        return K0, K1

    def update(self, meas, rate, dt):
        P = self.P
        # --- Praediktion ---
        r = rate - self.bias
        self.angle += dt * r
        P[0][0] += dt * (dt * P[1][1] - P[0][1] - P[1][0] + self.Q_ANGLE)
        P[0][1] -= dt * P[1][1]
        P[1][0] -= dt * P[1][1]
        P[1][1] += self.Q_BIAS * dt
        # --- Korrektur ---
        S = P[0][0] + self.R_MEASURE
        K0 = P[0][0] / S
        K1 = P[1][0] / S
        y = meas - self.angle
        self.angle += K0 * y
        self.bias += K1 * y
        t00, t01 = P[0][0], P[0][1]
        P[0][0] -= K0 * t00
        P[0][1] -= K0 * t01
        P[1][0] -= K1 * t00
        P[1][1] -= K1 * t01
        return self.angle


# ===========================================================================
# 1c  DER ENTWURF IN VIER SCHICHTEN
# ===========================================================================
#
#  Die Trennung ist strikt und die Reihenfolge fest:
#
#      1  Winkelerfassung   Rohwerte -> gefilterter Istwinkel und Drehrate
#      2  Winkelregler      Istwinkel -> Sollgeschwindigkeit des Rades
#      3  Motorausgabe      Sollgeschwindigkeit -> Schrittfrequenz
#      4  Nullpunktkorrektur  liegt DARUEBER und fuehrt den Nullpunkt der
#                             Winkelerfassung so nach, dass gilt:
#                             Istwinkel null  =  Fahrzeug steht.
#
#  Jede Schicht kennt nur ihre Eingangsgroessen. Die einzige Verbindung
#  entgegen der Reihenfolge ist die bekannte eigene Beschleunigung, die
#  Schicht 1 von Schicht 3 erhaelt; sie ist einzeln abschaltbar, damit
#  sich pruefen laesst, ob sie ueberhaupt gebraucht wird.
# ---------------------------------------------------------------------------


class Winkelerfassung:
    """
    Schicht 1 - Istwinkel und Drehrate.

    Eingang : Rohwinkel aus der Beschleunigung [Grad], Drehrate [Grad/s],
              wahlweise die bekannte eigene Beschleunigung [m/s2]
    Ausgang : Istwinkel [rad] (null bedeutet Gleichgewicht) und
              Drehrate [rad/s] ohne Kreiselnullpunkt

    Der Kalman schaetzt Winkel und Kreiselnullpunkt. Vom Ergebnis wird der
    von Schicht 4 nachgefuehrte Nullpunkt abgezogen - erst dadurch heisst
    "Istwinkel null" wirklich "Gleichgewicht" und nicht "senkrecht".
    """

    def __init__(self, p):
        self.p = p
        self.kalman = Kalman(p.Q_ANGLE, p.Q_BIAS, p.R_MEASURE)
        self.nullpunkt = 0.0        # Grad, von Schicht 4 nachgefuehrt
        self.a_glatt = 0.0          # m/s2, geglaettete eigene Beschleunigung
        self.v_vorher = 0.0

    def start(self, winkel_grad, dt):
        self.kalman.angle = winkel_grad
        self.kalman.eingeschwungen_starten(dt)

    def rechne(self, roh_grad, drehrate_grad, v_ausgabe, dt):
        p = self.p
        if p.a_komp_anteil != 0.0:
            # Die eigene Beschleunigung ist bekannt: sie ist die Ableitung
            # der ausgegebenen Radgeschwindigkeit. Sie laeuft durch denselben
            # Tiefpass wie das Messsignal, damit die Phase zusammenpasst,
            # und wird dann als Scheinneigung wieder herausgerechnet.
            a_roh = (v_ausgabe - self.v_vorher) / dt
            self.v_vorher = v_ausgabe
            self.a_glatt += (a_roh - self.a_glatt) * dt / p.t_dlpf
            roh_grad += p.a_komp_anteil * np.rad2deg(
                np.arctan2(self.a_glatt, p.g))
        winkel = self.kalman.update(roh_grad, drehrate_grad, dt)
        return (np.deg2rad(winkel - self.nullpunkt),
                np.deg2rad(drehrate_grad - self.kalman.bias))


class Winkelregler:
    """
    Schicht 2 - PID auf den Istwinkel, Stellgroesse ist eine Geschwindigkeit.

        v = K * ( e + 1/Tn INT e dt + Tv de/dt )        [m/s]

    Der D-Anteil kommt wahlweise unmittelbar vom Kreisel; dann entfaellt das
    Differenzieren des verrauschten Winkels. Der Integrator laeuft in der
    Begrenzung nicht weiter (Anti-Windup).
    """

    def __init__(self, p):
        self.p = p
        self.integral = 0.0
        self.e_alt = 0.0
        self.d_zustand = 0.0

    def ruecksetzen(self):
        self.integral = 0.0
        self.e_alt = 0.0
        self.d_zustand = 0.0

    def rechne(self, winkel_ist, drehrate, soll, v_grenze, dt):
        p = self.p
        e = winkel_ist - soll
        if p.WINKEL_SPERRE > 0.0 and abs(np.rad2deg(e)) < p.WINKEL_SPERRE:
            # Regelsperre: innerhalb des Bandes wird nicht gestellt. Der
            # Integrator laeuft weiter, sonst verloere die Regelung den
            # Arbeitspunkt.
            return 0.0
        if p.d_quelle == "kreisel":
            self.d_zustand = drehrate
        else:
            self.d_zustand += ((e - self.e_alt) / dt - self.d_zustand) \
                              * dt / max(p.N_TD, dt)
        self.e_alt = e
        anteil_p = p.N_K * e
        anteil_d = p.N_K * p.N_TV * self.d_zustand
        roh = anteil_p + self.integral + anteil_d
        if abs(roh) < v_grenze or (roh * e) < 0.0:
            self.integral = np.clip(self.integral + (p.N_K / p.N_TN) * e * dt,
                                    -v_grenze, v_grenze)
        return np.clip(anteil_p + self.integral + anteil_d,
                       -v_grenze, v_grenze)


class Motorausgabe:
    """
    Schicht 3 - Geschwindigkeit in Schrittfrequenz, begrenzt.

    Die ausgegebene Frequenz IST die Radgeschwindigkeit, solange kein
    Schritt verloren geht. Deshalb kennt diese Schicht als einzige den
    Zusammenhang zwischen Hertz und Meter je Sekunde, und deshalb kann sie
    Weg und Geschwindigkeit ohne Geber melden.
    """

    def __init__(self, p):
        self.p = p
        self.f = 0.0
        self.v = 0.0
        self.weg = 0.0

    def ausgeben(self, v_soll, dt):
        p = self.p
        # Aenderungsgrenze: der Regler darf nicht mehr fordern, als die
        # Motoren leisten koennen. Sonst gehen Schritte verloren, und dann
        # ist die ausgegebene Frequenz NICHT mehr die Radgeschwindigkeit -
        # womit Schicht 3 und Schicht 4 die Grundlage verlieren. Die Grenze
        # gehoert deshalb hierher und nicht in den Regler.
        v_soll = float(np.clip(v_soll, self.v - p.a_max * dt,
                               self.v + p.a_max * dt))
        f = float(np.clip(v_soll / p.v_je_hz, -p.MAX_SPEED, p.MAX_SPEED))
        if abs(f) < p.MIN_SPEED:
            f = 0.0
        # Gemeldet wird, was wirklich ausgegeben wird - auch die Null in der
        # Totzone. Sonst rechnet Schicht 4 mit einer Bewegung, die es nicht
        # gibt, und der Nullpunkt wandert weg.
        self.f = f
        self.v = f * p.v_je_hz
        self.weg += self.v * dt
        return self.f

    def halt(self):
        self.f = 0.0
        self.v = 0.0


class Nullpunktkorrektur:
    """
    Schicht 4 - die dynamische Nullpunktkorrektur.

    Sie beantwortet die Frage: das Fahrzeug faehrt weg, obwohl null Grad
    befohlen ist - um wie viel liegt der Nullpunkt daneben?

        Nullpunkt' = PI-Regler auf ( v_wunsch - v_ausgabe )

    Richtung und Betrag der Bewegung sind bekannt, ohne jeden Geber: die
    ausgegebene Schrittfrequenz ist die Radgeschwindigkeit. Der Regler
    verschiebt den Nullpunkt so lange, bis das Fahrzeug bei Istwinkel null
    wirklich steht. Er ist bewusst rund zehnmal langsamer als Schicht 2.
    """

    def __init__(self, p):
        self.p = p
        self.integral = 0.0
        self.wert = 0.0          # Grad

    def ruecksetzen(self):
        self.integral = 0.0
        self.wert = 0.0

    def rechne(self, v_ausgabe, weg, v_wunsch, dt):
        p = self.p
        if p.nk_art == "aus":
            self.wert = 0.0
            return self.wert
        if p.nk_art == "drift":
            # Vergleichsfall: Self-Balance wie in segway_esp32_Doku.ino.
            # Sie kennt nur das Vorzeichen und tastet sich mit festem
            # Schritt heran.
            if v_ausgabe < 0.0:
                self.wert -= p.NK_DRIFT
            elif v_ausgabe > 0.0:
                self.wert += p.NK_DRIFT
            self.wert = float(np.clip(self.wert, -np.rad2deg(p.NK_MAX),
                                      np.rad2deg(p.NK_MAX)))
            return self.wert
        if p.nk_art == "weg" and v_wunsch == 0.0:
            # zusaetzlich Ortshaltung: nicht nur stehenbleiben, sondern
            # an den Ausgangspunkt zurueck
            v_wunsch = float(np.clip(-p.NW_K * weg, -p.NW_MAX, p.NW_MAX))
        e_v = v_wunsch - v_ausgabe
        roh = p.NK_K * e_v + self.integral
        if abs(roh) < p.NK_MAX or (roh * e_v) < 0.0:
            self.integral = float(np.clip(
                self.integral + (p.NK_K / p.NK_TN) * e_v * dt,
                -p.NK_MAX, p.NK_MAX))
        self.wert = np.rad2deg(float(np.clip(p.NK_K * e_v + self.integral,
                                             -p.NK_MAX, p.NK_MAX)))
        return self.wert


# ===========================================================================
# 2  SIMULATION
# ===========================================================================

def simuliere(p, dauer=6.0, theta0_grad=3.0, omega0_grad_s=0.0,
              speed_sollverlauf=None, stoerung=None, sensor_ideal=False,
              regler="alt"):
    """
    Faehrt eine Simulation.

      dauer              [s]
      theta0_grad        Anfangsneigung [Grad]
      omega0_grad_s      Anfangsdrehrate [Grad/s]. Wird gebraucht, um den
                         Fangbereich nicht nur aus der Ruhe zu bestimmen -
                         beim Anfahren aus der Hand ist das Fahrzeug in
                         Bewegung.
      speed_sollverlauf  Funktion t -> speedSetpoint (None = 0)
      stoerung           Funktion t -> Stoermoment am Pendel [Nm]
      sensor_ideal       True = Regler bekommt den wahren Winkel
                         (zum Trennen von Regler- und Sensorproblemen)
      regler             "alt" = Nachbildung des vorhandenen Quellcodes
                         "neu" = ueberarbeitete Fassung mit ausgeschriebener
                                 Schrittweite und Beiwerten in physikalischen
                                 Einheiten

    Rueckgabe: dict mit den Zeitreihen
    """
    dt_gitter = 1.0 / p.f_gitter          # 4-ms-Raster der Hauptschleife
    unter = p.feinschritte                # Feinschritte der Mechanik je Raster
    dt = dt_gitter / unter
    n_raster = int(dauer * p.f_gitter)

    # --- Strecke ---
    theta = np.deg2rad(theta0_grad)
    omega = np.deg2rad(omega0_grad_s)
    x = 0.0
    v_ist = 0.0
    a_wagen = 0.0

    # --- Sensor ---
    theta_hat = theta                     # Schaetzwert des DMP
    n_dmp = 0                             # Zaehler der Sensorabfragen

    # Der 42-Hz-Tiefpass des MPU6050 wird als Verzoegerung erster Ordnung
    # abgebildet. Seine Zeitkonstante wird so gewaehlt, dass die
    # Gruppenlaufzeit dem Datenblattwert entspricht (4,8 ms bei DLPF 42 Hz).
    # Frueher stand hier zusaetzlich eine Laufzeitkette - die zaehlte die
    # Verzoegerung ein zweites Mal, und fuer die Drehrate fehlte sie ganz.
    tau_lp = p.t_dlpf
    a_lp = 0.0                                # gefilterte Beschleunigung
    om_lp = 0.0                               # gefilterte Drehrate
    th_lp = theta                             # gefilterte Neigung

    kalman = Kalman(p.Q_ANGLE, p.Q_BIAS, p.R_MEASURE)
    kalman.angle = np.rad2deg(theta)      # Start auf dem wahren Winkel
    theta_acc_grad = np.rad2deg(theta)    # zuletzt gebildeter Rohwinkel
    angle = np.rad2deg(theta)             # zuletzt gelieferter Messwert
    drehrate_gemeldet = 0.0               # zuletzt gemeldete Drehrate [Grad/s]
    roh_grad = np.rad2deg(theta)          # Rohwinkel fuer Schicht 1 [Grad]
    neue_daten = False

    # --- Regler (Namen wie im Sketch) ---
    pidOutput = 0.0
    integralErrAngle = 0.0
    integralErrSpeed = 0.0
    pidLastError = 0.0
    angleSetpoint = 0.0
    speedSetpoint = 0.0
    f_soll = 0.0
    abgeschaltet = False

    # Zustand des Reglers aus segway_esp32_Doku.ino
    d_integral = 0.0
    d_prev = 0.0
    d_setpoint = p.D_SETPOINT0

    # Zustand des Reglers aus segway_esp32.ino
    e_integral = 0.0
    e_prev = 0.0

    # Die vier Schichten des Entwurfs (siehe Abschnitt 1c)
    erfassung    = Winkelerfassung(p)
    winkelregler = Winkelregler(p)
    motor        = Motorausgabe(p)
    nullpunkt    = Nullpunktkorrektur(p)
    erfassung.start(np.rad2deg(theta), 1.0 / p.f_dmp)

    # Zustand des ueberarbeiteten Reglers
    n_i_winkel = 0.0        # Integrator Winkel   [m/s]
    n_e_letzt = 0.0         # letzte Winkelabweichung [rad]
    n_i_speed = 0.0         # Integrator Geschwindigkeit [rad]
    n_v_cmd = 0.0           # Geschwindigkeitsvorgabe [m/s]

    rng = np.random.default_rng(20260823)

    t_r, th_r, thm_r, f_r, v_r, x_r, soll_r, hz_r = [], [], [], [], [], [], [], []
    bias_r = []          # Nullpunktschaetzung des Kalman [Grad/s]
    hz_letzt = np.nan
    t_letzt = -dt_gitter

    for k in range(n_raster):
        t = k * dt_gitter

        # ---- Aufzeichnung VOR dem Rechenschritt ----
        # Zustand und Zeitstempel gehoeren damit zusammen. f_soll ist die
        # Frequenz, die waehrend dieses Rasters wirklich ausgegeben wird -
        # gerechnet wurde sie im vorigen Durchlauf. Das ist die eine
        # Taktverzoegerung, die das Geraet auch hat.
        t_r.append(t)
        th_r.append(np.rad2deg(theta))
        thm_r.append(angle)
        f_r.append(f_soll)
        v_r.append(v_ist)
        x_r.append(x)
        soll_r.append(angleSetpoint)
        hz_r.append(hz_letzt)
        bias_r.append(kalman.bias)

        # ---------------- Strecke, ein Rasterschritt ----------------
        v_soll = f_soll * p.v_je_hz
        for _ in range(unter):
            dv = np.clip((v_soll - v_ist) / p.tau_mot, -p.a_max, p.a_max)
            a_wagen = dv
            v_ist += dv * dt
            M = stoerung(t) if stoerung is not None else 0.0
            # Momentenbilanz um die Radachse, aus der virtuellen Arbeit
            # Q = F * dr/dtheta mit
            #   r      = l*(sin th, cos th) + s*(cos th, -sin th)
            #   dr/dth = l*(cos th, -sin th) + s*(-sin th, -cos th)
            # Schwerkraft (0, -m g) und Traegheitskraft (-m a, 0) des
            # beschleunigten Drehpunkts ergeben:
            #   Q = m g (l sin th + s cos th) - m a (l cos th - s sin th)
            # Das Glied mit s ist der seitliche Schwerpunktversatz: er
            # verschiebt den Gleichgewichtswinkel weg von der Senkrechten
            # und ist damit der eigentliche Nullpunktfehler. Der Anteil
            # + m a s sin(th) ist klein (0,06 bis 0,13 Prozent), steht
            # aber mit da, damit keine Naeherung noetig ist.
            domega = (p.m * p.g * (p.l * np.sin(theta)
                                   + p.s_versatz * np.cos(theta))
                      - p.m * a_wagen * (p.l * np.cos(theta)
                                         - p.s_versatz * np.sin(theta))
                      - p.d * omega + M) / p.J
            omega += domega * dt
            theta += omega * dt
            x += v_ist * dt

            # ---- Sensorkette (laeuft im Feintakt) ----
            # Beschleunigungsmesser sieht die scheinbare Lotrichtung.
            # Sitzt er nicht auf der Drehachse, kommen die Beschleunigungen
            # der Kippbewegung hinzu:
            #   Hoehe w ueber der Achse  ->  Term mit theta''  (erster Ordnung)
            #   Versatz u nach vorn      ->  Term mit theta'^2 (zweiter Ordnung)
            a_schein = a_wagen + p.sensor_w * domega - p.sensor_u * omega ** 2

            # Tiefpass des MPU6050 auf Beschleunigung, Neigung und Drehrate.
            # Ohne ihn sieht das Modell die Millisekundenspitzen der
            # Schrittansteuerung, die der echte Sensor gar nicht mehr ausgibt.
            # Ein und derselbe Tiefpass wirkt auf alle drei Groessen -
            # so, wie ihn der Baustein wirklich schaltet.
            a_lp  += (a_schein - a_lp)  * dt / tau_lp
            th_lp += (theta    - th_lp) * dt / tau_lp
            om_lp += (omega    - om_lp) * dt / tau_lp

            # Das ist der Rohwert, den der Baustein wirklich meldet -
            # einschliesslich des Fehlers durch die eigene Beschleunigung.
            theta_acc = th_lp - np.arctan2(a_lp, p.g)
            theta_acc_grad = np.rad2deg(theta_acc)

            if p.sensor_art in ("komplementaer", "dmp"):
                # Hochpass auf den Kreisel, Tiefpass auf die Beschleunigung.
                # Der DMP arbeitet strukturell ebenso, nur mit deutlich
                # laengerer Zeitkonstante (Quaternionenfusion im Chip).
                tau = p.tau_dmp_int if p.sensor_art == "dmp" else p.tau_dmp
                theta_hat += (omega + np.deg2rad(p.gyro_bias)) * dt \
                             + (theta_acc - theta_hat) * dt / tau

        # ---------------- Sensor liefert nur mit f_dmp ----------------
        # Der Zeitpunkt wird aus dem Zaehler gerechnet, nicht fortlaufend
        # addiert. Sonst verschiebt sich die Abfrage durch Rundung gegen das
        # Raster, und bei gleicher Rate faellt gelegentlich ein Takt aus.
        if t + 1e-12 >= n_dmp / p.f_dmp:
            if sensor_ideal:
                angle = np.rad2deg(theta)
                drehrate_gemeldet = np.rad2deg(omega) + kalman.bias
                roh_grad = angle
            elif p.sensor_art == "kalman":
                # Filter laeuft mit der Abtastrate des Reglers
                messwert = theta_acc_grad + rng.normal(0.0, p.rausch_grad)
                drehrate = (np.rad2deg(om_lp) + p.gyro_bias
                            + rng.normal(0.0, p.gyro_rausch))
                drehrate_gemeldet = drehrate
                roh_grad = messwert
                angle = kalman.update(messwert, drehrate, 1.0 / p.f_dmp)
            else:
                angle = np.rad2deg(theta_hat) + rng.normal(0.0, p.rausch_grad)
                drehrate_gemeldet = (np.rad2deg(om_lp) + p.gyro_bias
                                     + rng.normal(0.0, p.gyro_rausch))
                roh_grad = theta_acc_grad + rng.normal(0.0, p.rausch_grad)
            # Kalibrierfehler des Sensors: wirkt auf jeden Weg gleich.
            # Er ist von aussen NICHT vom Schwerpunktversatz zu unterscheiden -
            # genau deshalb hilft nur eine Korrektur im Betrieb.
            angle += p.mess_versatz
            n_dmp += 1
            neue_daten = True

        # ---------------- Regler, nur bei neuen Daten ----------------
        if neue_daten:
            neue_daten = False
            hz = 1.0 / max(t - t_letzt, 1e-9)
            t_letzt = t

            if speed_sollverlauf is not None:
                speedSetpoint = speed_sollverlauf(t)

            # --- Nachbildung des vorhandenen Quellcodes ---------------
            # Dieser Block lief frueher in JEDEM Fall mit und wurde von
            # den anderen Zweigen nur ueberschrieben. Damit war weder
            # die freie Strecke pruefbar noch der Rechenweg eindeutig.
            if regler == "alt":
                # aeusserer Kreis: PI auf die Geschwindigkeit
                actualSpeed = np.clip(pidOutput, -p.MAX_PID_OUT, p.MAX_PID_OUT) \
                              * (p.MAX_SPEED / p.MAX_PID_OUT)
                piError = speedSetpoint * p.SPEED_SKAL - actualSpeed
                integralErrSpeed = np.clip(integralErrSpeed + p.Ki * piError,
                                           -p.MAX_PI_OUT, p.MAX_PI_OUT)
                angleSetpoint = (p.Kp * piError + integralErrSpeed) * p.WINKEL_SKAL

                # innerer Kreis: PID auf den Winkel
                pidError = angle - angleSetpoint
                integralErrAngle = np.clip(integralErrAngle + p.ANGLE_KI * pidError,
                                           -p.MAX_PID_OUT, p.MAX_PID_OUT)
                errorDerivative = pidError - pidLastError
                pidOutput = (p.ANGLE_KP * pidError + integralErrAngle
                             + p.ANGLE_KD * errorDerivative)

                if angle > p.KIPP_GRENZE or angle < -p.KIPP_GRENZE:
                    pidOutput = 0.0
                    integralErrAngle = 0.0
                    abgeschaltet = True

                pidLastError = pidError
                f_soll = np.clip(np.clip(pidOutput, -p.MAX_PID_OUT, p.MAX_PID_OUT)
                                 * (p.MAX_SPEED / p.MAX_PID_OUT),
                                 -p.MAX_SPEED, p.MAX_SPEED)
            if regler == "doku":
                # Nachbildung von segway_esp32_Doku.ino, Zeile fuer Zeile
                fehler = angle - d_setpoint
                d_integral = np.clip(d_integral + p.D_KI * fehler,
                                     -p.D_OUT_MAX, p.D_OUT_MAX)
                ableitung = fehler - d_prev
                d_prev = fehler
                out = np.clip(p.D_KP * fehler + d_integral
                              + p.D_KD * ableitung,
                              -p.D_OUT_MAX, p.D_OUT_MAX)
                f = out * p.D_SKAL
                if abs(f) < p.E_TOTZONE:
                    f = 0.0

                # Self-Balance: Sollwinkel driftet in Fahrtrichtung.
                # p.D_DRIFT_NUR_BEI_FAHRT = True laesst ihn nur laufen,
                # wenn die Raeder sich auch wirklich drehen. Sonst entsteht
                # mit der Totzone eine Ratsche: der Sollwert wandert dem
                # Kippwinkel hinterher, ohne dass gegengesteuert wird.
                if (not p.D_DRIFT_NUR_BEI_FAHRT) or f != 0.0:
                    if out < 0: d_setpoint -= p.D_DRIFT
                    if out > 0: d_setpoint += p.D_DRIFT
                f_soll = np.clip(f, -p.MAX_SPEED, p.MAX_SPEED)
                if abs(angle) > p.KIPP_GRENZE:
                    f_soll = 0.0; d_integral = 0.0; abgeschaltet = True

            if regler == "esp32":
                # ---------------------------------------------------------
                # Nachbildung von segway_esp32.ino, Zeile fuer Zeile:
                #   err = 0 - angle,  integral += err*dt (begrenzt),
                #   deriv = (err-prev)/dt,  out = KP*err + KI*I + KD*D  [Hz]
                #   |out| < MIN_SPEED_HZ  ->  Stillstand
                # Das Vorzeichen wird am Geraet ueber g_invert gestellt;
                # hier ist die richtige Richtung angenommen.
                # ---------------------------------------------------------
                dt_r = 1.0 / p.f_dmp
                err = -angle
                e_integral = np.clip(e_integral + err * dt_r,
                                     -p.E_I_MAX, p.E_I_MAX)
                deriv = (err - e_prev) / dt_r
                e_prev = err
                out = p.E_KP * err + p.E_KI * e_integral + p.E_KD * deriv

                f = -out                       # g_invert = true
                if abs(f) < p.E_TOTZONE:
                    f = 0.0
                f_soll = np.clip(f, -p.MAX_SPEED, p.MAX_SPEED)

                if abs(angle) > p.KIPP_GRENZE:
                    f_soll = 0.0
                    e_integral = 0.0
                    abgeschaltet = True

            if regler == "neu":
                # ---------------------------------------------------------
                # Ueberarbeitete Fassung - Rechenweg identisch mit Segway.ino
                #   - Schrittweite dt ausgeschrieben
                #   - Normalform K / Tn / Tv, Beiwerte physikalisch
                #   - Stellgroesse ist eine Geschwindigkeit in m/s;
                #     MAX_SPEED wirkt nur noch als Grenze
                #   - Integrator laeuft in der Begrenzung nicht weiter
                # ---------------------------------------------------------
                dt_r = 1.0 / p.f_dmp
                v_max = p.v_max
                ist_winkel = np.deg2rad(angle)

                if abs(angle) > p.KIPP_GRENZE:
                    n_v_cmd = 0.0
                    n_i_winkel = 0.0
                    n_i_speed = 0.0
                    abgeschaltet = True
                    f_soll = 0.0
                else:
                    # aeusserer Kreis
                    v_wunsch = speedSetpoint * p.SPEED_SKAL * p.v_je_hz
                    e_v = v_wunsch - n_v_cmd
                    n_i_speed = np.clip(
                        n_i_speed + (p.V_K / (p.V_TN * 0.001)) * e_v * dt_r,
                        -p.V_WINKEL_MAX, p.V_WINKEL_MAX)
                    soll_winkel = np.clip(p.V_K * e_v + n_i_speed,
                                          -p.V_WINKEL_MAX, p.V_WINKEL_MAX)

                    # innerer Kreis
                    e = ist_winkel - soll_winkel
                    d_e = (e - n_e_letzt) / dt_r
                    anteil_p = p.W_K * e
                    anteil_d = p.W_K * (p.W_TV * 0.001) * d_e

                    roh = anteil_p + n_i_winkel + anteil_d
                    if abs(roh) < v_max or (roh * e) < 0.0:
                        n_i_winkel = np.clip(
                            n_i_winkel + (p.W_K / (p.W_TN * 0.001)) * e * dt_r,
                            -v_max, v_max)

                    n_v_cmd = np.clip(anteil_p + n_i_winkel + anteil_d,
                                      -v_max, v_max)
                    n_e_letzt = e
                    angleSetpoint = np.rad2deg(soll_winkel)
                    f_soll = np.clip(n_v_cmd / p.v_je_hz,
                                     -p.MAX_SPEED, p.MAX_SPEED)

            if regler == "entwurf":
                dt_r = 1.0 / p.f_dmp

                # ---- Schicht 4: Nullpunkt nachfuehren (liegt darueber) ----
                nullpunkt.rechne(motor.v, motor.weg,
                                 speedSetpoint * p.SPEED_SKAL * p.v_je_hz,
                                 dt_r)
                erfassung.nullpunkt = nullpunkt.wert

                # ---- Schicht 1: Istwinkel und Drehrate ----
                winkel_ist, drehrate_ist = erfassung.rechne(
                    roh_grad, drehrate_gemeldet, motor.v, dt_r)
                angle = np.rad2deg(winkel_ist) + nullpunkt.wert
                angleSetpoint = nullpunkt.wert

                # ---- Sicherheitsabschaltung ----
                if abs(angle) > p.KIPP_GRENZE:
                    motor.halt()
                    winkelregler.ruecksetzen()
                    nullpunkt.ruecksetzen()
                    abgeschaltet = True
                    f_soll = 0.0
                else:
                    # ---- Schicht 2: Winkelregler ----
                    v_soll_rad = winkelregler.rechne(winkel_ist, drehrate_ist,
                                                     0.0, p.v_max, dt_r)
                    # ---- Schicht 3: Motorausgabe ----
                    f_soll = motor.ausgeben(v_soll_rad, dt_r)

        else:
            hz = np.nan

        hz_letzt = hz

        if abs(np.rad2deg(theta)) > 80:
            break

    return dict(t=np.array(t_r), theta=np.array(th_r), theta_mess=np.array(thm_r),
                f=np.array(f_r), v=np.array(v_r), x=np.array(x_r),
                soll=np.array(soll_r), hz=np.array(hz_r),
                bias=np.array(bias_r),
                gefallen=abs(np.array(th_r)[-1]) > 80, abgeschaltet=abgeschaltet)


def bewerte(erg, grenze=0.5, zyklus_grenze=0.5):
    """
    Kennzahlen einer Simulation.

    "stabil" heisst hier dreierlei: der Segway ist nicht umgefallen, die
    Sicherheitsabschaltung hat nicht angesprochen, und die Schwingung
    waechst am Ende nicht weiter an.

    Zum letzten Punkt: ein Grenzzyklus, der sich auf kleiner Amplitude
    einpendelt, ist kein Sturz. Die Totzone der Motorausgabe erzeugt
    genau so einen - bei MIN_SPEED = 80 Hz sind es rund 0,3 Grad. Als
    unstabil gilt deshalb nur, was BEIDES tut: weiter anwachsen UND dabei
    zyklus_grenze ueberschreiten. Beide Amplituden werden mitgegeben,
    damit das Urteil nachvollziehbar bleibt.
    """
    th, t = erg["theta"], erg["t"]
    fehler = float(np.max(np.abs(erg["theta_mess"] - erg["theta"])))
    n = len(th)
    a_mitte = float(np.max(np.abs(th[n // 3:2 * n // 3])))
    a_ende = float(np.max(np.abs(th[2 * n // 3:])))
    wachstum = a_ende / max(a_mitte, 1e-9)

    def nein(grund):
        return dict(stabil=False, grund=grund, t_ein=np.nan, rest=np.nan,
                    weg=abs(erg["x"][-1]), messfehler=fehler,
                    wachstum=wachstum, a_mitte=a_mitte, a_ende=a_ende)

    if erg["gefallen"]:
        return nein("umgefallen")
    if erg["abgeschaltet"]:
        return nein("Sicherheitsabschaltung")
    if wachstum > 1.2 and a_ende > zyklus_grenze:
        return nein("wachsende Schwingung")

    m = max(1, int(len(t) * 1.0 / max(t[-1] - t[0], 1e-9)))
    rest = float(np.std(th[-m:]))
    innen = np.abs(th) < grenze
    t_ein = np.nan
    for i in range(len(innen)):
        if innen[i:].all():
            t_ein = t[i]
            break
    return dict(stabil=True, grund="", t_ein=t_ein, rest=rest,
                weg=abs(erg["x"][-1]), messfehler=fehler, wachstum=wachstum,
                a_mitte=a_mitte, a_ende=a_ende)


# ===========================================================================
# 3  ANALYSE DES LINEARISIERTEN KREISES
# ===========================================================================

def analyse(p):
    """
    Rechnet die Beiwerte des Quellcodes in physikalische Einheiten um.

    Weil die Stellgroesse eine GESCHWINDIGKEIT ist, lautet der linearisierte
    geschlossene Kreis

        (J + m*l*kd) th'' + m*l*kp th' + m*l*(ki - g) th = 0

    Daraus folgt das wichtigste Ergebnis dieser Untersuchung:
    Stabil wird das System nur, wenn ki > g. Der INTEGRALANTEIL des
    Winkelreglers richtet den Segway auf, der P-Anteil daempft nur, und der
    D-Anteil wirkt wie zusaetzliche Traegheit.

    Zu beachten: In ki und kd steckt die Abtastrate, weil im Quellcode weder
    beim Integrieren noch beim Differenzieren durch dt geteilt wird.
    """
    G = 180.0 / np.pi
    skal = (p.MAX_SPEED / p.MAX_PID_OUT) * p.v_je_hz      # pidOutput -> m/s
    f = p.f_dmp                                           # tatsaechlicher Takt

    kp = p.ANGLE_KP * skal * G
    ki = p.ANGLE_KI * f * skal * G
    kd = p.ANGLE_KD / f * skal * G

    ml = p.m * p.l
    A = p.J + ml * kd
    B = ml * kp
    C = ml * (ki - p.g)

    stabil = C > 0
    wn = np.sqrt(C / A) if stabil else np.nan
    zeta = B / (2.0 * np.sqrt(A * C)) if stabil else np.nan

    return dict(kp=kp, ki=ki, kd=kd, stabil=stabil, wn=wn,
                f_n=wn / (2 * np.pi), zeta=zeta,
                a_bei_3grad=kp * np.deg2rad(3.0) * f)


# ===========================================================================
# 4  VERSUCHE
# ===========================================================================

def betriebsfenster(ns_werte, a_werte, **fest):
    """Karte ueber Schrittzahl und Beschleunigungsgrenze."""
    karte = np.full((len(a_werte), len(ns_werte)), np.nan)
    for i, a in enumerate(a_werte):
        for j, ns in enumerate(ns_werte):
            b = bewerte(simuliere(Parameter(Ns=ns, a_max=a, **fest),
                                  dauer=10.0, theta0_grad=3.0))
            if b["stabil"]:
                karte[i, j] = b["rest"]
    return karte


# ===========================================================================
# 5  BILDER
# ===========================================================================

def bild_verlauf(erg, titel, datei):
    fig, ax = plt.subplots(4, 1, figsize=(9, 9), sharex=True)
    ax[0].plot(erg["t"], erg["theta"], label="wahrer Winkel")
    ax[0].plot(erg["t"], erg["theta_mess"], lw=.9, label="vom DMP gemeldet")
    ax[0].plot(erg["t"], erg["soll"], "--", lw=.9, label="Sollwinkel")
    ax[0].set_ylabel("Winkel [Grad]"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
    ax[1].plot(erg["t"], erg["theta_mess"] - erg["theta"], color="tab:purple")
    ax[1].set_ylabel("Messfehler [Grad]"); ax[1].grid(alpha=.3)
    ax[2].plot(erg["t"], erg["f"], color="tab:orange")
    ax[2].set_ylabel("Schrittfrequenz [Hz]"); ax[2].grid(alpha=.3)
    ax[3].plot(erg["t"], erg["v"], color="tab:green", label="v [m/s]")
    ax[3].plot(erg["t"], erg["x"], color="tab:red", label="Weg [m]")
    ax[3].set_xlabel("Zeit [s]"); ax[3].legend(fontsize=8); ax[3].grid(alpha=.3)
    fig.suptitle(titel); fig.tight_layout()
    fig.savefig(datei, dpi=110); plt.close(fig)


def bild_fenster(karte, ns_werte, a_werte, datei, marke=None):
    fig, ax = plt.subplots(figsize=(8, 5.5))
    bild = ax.imshow(karte, origin="lower", aspect="auto", cmap="viridis",
                     extent=[0, len(ns_werte), a_werte[0], a_werte[-1]])
    ax.set_xticks(np.arange(len(ns_werte)) + 0.5)
    ax.set_xticklabels([str(n) for n in ns_werte])
    ax.set_xlabel("Schritte je Umdrehung Ns")
    ax.set_ylabel("Beschleunigungsgrenze a_max [m/s2]")
    ax.set_title("Betriebsfenster der festen Beiwerte 45 / 12 / 30\n"
                 "farbig = balanciert, grau = faellt um")
    ax.set_facecolor("0.72")
    if marke:
        ax.plot(list(ns_werte).index(marke[0]) + .5, marke[1], "r*", ms=18)
    fig.colorbar(bild, ax=ax, label="Restzittern [Grad]")
    fig.tight_layout(); fig.savefig(datei, dpi=110); plt.close(fig)


def bild_kd(ergebnisse, datei):
    fig, ax = plt.subplots(figsize=(9, 4))
    for (kd, erg), stil in zip(sorted(ergebnisse.items()), ["-", "--", ":"]):
        ax.plot(erg["t"], erg["theta"], stil, lw=2, label="Kd = %g" % kd)
    ax.set_xlabel("Zeit [s]"); ax.set_ylabel("Winkel [Grad]")
    ax.set_title("Kd der Weboberflaeche: drei Werte, ein einziger Verlauf")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(datei, dpi=110); plt.close(fig)


# ===========================================================================
# 6  HAUPTPROGRAMM
# ===========================================================================

def main():
    strich = "=" * 76
    print(strich)
    print("SEGWAY-MODELL - Pruefung des Reglercodes")
    print(strich)

    # -------------------------------------------------------------------
    print("\nA  DER TAKT DER REGELUNG")
    print("   PERIOD im Quellcode          4,0 ms  = 250 Hz")
    print("   DMP-Ausgaberate              %.0f Hz   (setRate(4) und"
          " FIFO_RATE_DIVISOR=0x01)" % Parameter.f_dmp)
    print("   -> Die PID-Rechnung laeuft nur, wenn ein neues DMP-Paket da ist.")
    print("      Der wirksame Regeltakt ist also %.0f Hz, nicht 250 Hz."
          % Parameter.f_dmp)
    print("      Weil im Code weder integriert noch differenziert durch dt")
    print("      geteilt wird, haengen ki und kd unmittelbar an diesem Takt.")

    # -------------------------------------------------------------------
    print("\nB  BETRIEBSFENSTER DER FESTEN BEIWERTE")
    ns_werte = [200, 400, 800, 1600, 3200, 6400]
    a_werte = np.linspace(2, 40, 20)
    karte = betriebsfenster(ns_werte, a_werte)
    print("   Ns   | v_max [m/s] | stabiler Anteil | ruhigster Punkt")
    for j, ns in enumerate(ns_werte):
        pp = Parameter(Ns=ns)
        spalte = karte[:, j]
        gut = ~np.isnan(spalte)
        if gut.any():
            i = int(np.nanargmin(spalte))
            print("   %5d|   %6.3f    |     %3.0f %%       |"
                  " a_max = %4.1f, Restzittern %.3f Grad"
                  % (ns, pp.v_max, 100.0 * gut.sum() / len(spalte),
                     a_werte[i], spalte[i]))
        else:
            print("   %5d|   %6.3f    |       0 %%      |  faellt immer um"
                  % (ns, pp.v_max))
    if np.all(np.isnan(karte)):
        bester = (800, 25.0)
    else:
        i, j = np.unravel_index(int(np.nanargmin(karte)), karte.shape)
        bester = (ns_werte[j], float(a_werte[i]))
    print("   Fuer die weiteren Versuche: Ns = %d, a_max = %.0f m/s2"
          % bester)
    bild_fenster(karte, ns_werte, a_werte, "bild1_betriebsfenster.png", bester)

    p = Parameter(Ns=bester[0], a_max=bester[1])

    # -------------------------------------------------------------------
    a = analyse(p)
    print("\nC  DER KREIS IN PHYSIKALISCHEN EINHEITEN")
    print("   Zeitkonstante des freien Umfallens   %6.3f s" % p.t_kipp)
    print("   Geschwindigkeit je Hertz             %.3e m/s" % p.v_je_hz)
    print("   kp aus ANGLE_KP = 45                 %8.2f m/s je rad" % a["kp"])
    print("   ki aus ANGLE_KI = 12                 %8.1f m/s je rad*s"
          % a["ki"])
    print("       Stabilitaetsbedingung: ki > g = 9,81            %s"
          % ("erfuellt" if a["ki"] > p.g else "NICHT erfuellt"))
    print("   kd aus ANGLE_KD = 30                 %8.4f m/s je rad/s"
          % a["kd"])
    print("   Kennkreisfrequenz                    %8.1f rad/s = %.2f Hz"
          % (a["wn"], a["f_n"]))
    print("   Daempfungsgrad                       %8.2f" % a["zeta"])

    # -------------------------------------------------------------------
    print("\nD  WELCHER ANTEIL RICHTET DEN SEGWAY AUF?")
    for ki in (0.0, 1.0, 3.0, 12.0):
        pp = Parameter(Ns=p.Ns, a_max=p.a_max, ANGLE_KI=ki)
        aa = analyse(pp)
        b = bewerte(simuliere(pp, dauer=10.0, theta0_grad=3.0))
        print("   ANGLE_KI = %5.1f -> ki = %7.1f  (%s)   %s"
              % (ki, aa["ki"], "ki > g" if aa["ki"] > p.g else "ki < g",
                 "balanciert" if b["stabil"] else "FAELLT UM"))
    print("   Ohne Integralanteil im Winkelregler faellt der Segway immer.")

    # -------------------------------------------------------------------
    print("\nE  WIRKUNG VON Kd AUS DER WEBOBERFLAECHE")
    e_kd = {kd: simuliere(Parameter(Ns=p.Ns, a_max=p.a_max, Kd=kd),
                          dauer=10.0, theta0_grad=3.0)
            for kd in (0.0, 70.0, 1000.0)}
    ref = e_kd[70.0]["theta"]
    for kd, erg in sorted(e_kd.items()):
        n = min(len(ref), len(erg["theta"]))
        print("   Kd = %7.1f  groesste Abweichung zu Kd = 70:  %.3e Grad"
              % (kd, float(np.max(np.abs(erg["theta"][:n] - ref[:n])))))
    print("   Kd wird im Quellcode nirgends verrechnet.")
    bild_kd(e_kd, "bild2_kd_ohne_wirkung.png")

    # -------------------------------------------------------------------
    print("\nF  DER LAGEWINKEL AUS DEM SENSOR")
    print("   Der Beschleunigungsmesser sieht die scheinbare Lotrichtung.")
    print("   Bei waagerechter Beschleunigung a betraegt der Fehler"
          " arctan(a/g):")
    for acc in (1, 2, 3, 5, 10):
        print("      a = %4.1f m/s2  ->  %5.1f Grad scheinbare Neigung"
              % (acc, np.rad2deg(np.arctan2(acc, 9.81))))
    print("   Die Fusion zieht das mit ihrer Zeitkonstante nach: kurze")
    print("   Stoesse werden herausgefiltert, anhaltende Beschleunigung")
    print("   laeuft ein. Deshalb haengt alles an dieser einen Zahl.")
    print()
    print("   Vergleich der Sensorwege (Aufrichten aus 3 Grad):")
    faelle = [("idealer Sensor      ", dict(), True)]
    faelle.append(("Kalman aus dem Code ", dict(sensor_art="kalman"), False))
    faelle.append(("DMP (tau = %.1f s)   " % Parameter.tau_dmp_int,
                   dict(sensor_art="dmp"), False))
    for tau in (0.2, 0.5, 1.0, 3.0):
        faelle.append(("Komplementaer tau = %.1f s" % tau,
                       dict(sensor_art="komplementaer", tau_dmp=tau), False))
    for name, zusatz, ideal in faelle:
        pp = Parameter(Ns=p.Ns, a_max=p.a_max, **zusatz)
        b = bewerte(simuliere(pp, dauer=10.0, theta0_grad=3.0,
                              sensor_ideal=ideal))
        print("      %-26s %s   groesster Messfehler %5.2f Grad%s"
              % (name,
                 "balanciert" if b["stabil"] else "FAELLT UM ",
                 b["messfehler"],
                 "" if not b["stabil"] else
                 "   Restzittern %.3f Grad" % b["rest"]))

    # -------------------------------------------------------------------
    print("\nG  BETRIEBSFAELLE (Ns = %d, a_max = %.0f m/s2)" % bester)
    e1 = simuliere(p, dauer=10.0, theta0_grad=3.0)
    b1 = bewerte(e1)
    print("   Aufrichten aus 3 Grad:   %s  Einschwingzeit %.2f s"
          "  Restzittern %.3f Grad  Weg %.2f m"
          % ("balanciert" if b1["stabil"] else "FAELLT UM", b1["t_ein"],
             b1["rest"], b1["weg"]))
    bild_verlauf(e1, "Aufrichten aus 3 Grad Neigung", "bild3_aufrichten.png")

    e2 = simuliere(p, dauer=5.0, theta0_grad=0.0,
                   stoerung=lambda t: 0.15 if 2.0 <= t < 2.05 else 0.0)
    b2 = bewerte(e2)
    print("   Stoss 0,15 Nm / 50 ms:   %s  groesster Ausschlag %.2f Grad"
          "  Weg %.2f m"
          % ("balanciert" if b2["stabil"] else "FAELLT UM",
             float(np.max(np.abs(e2["theta"]))), b2["weg"]))
    bild_verlauf(e2, "Stoerung durch einen Stoss", "bild4_stoss.png")

    e3 = simuliere(p, dauer=8.0, theta0_grad=0.0,
                   speed_sollverlauf=lambda t: 2.0 if t >= 2.0 else 0.0)
    b3 = bewerte(e3)
    print("   Fahrbefehl Sollwert 2:   %s  Endgeschwindigkeit %.3f m/s"
          "  groesster Winkel %.2f Grad"
          % ("balanciert" if b3["stabil"] else "FAELLT UM",
             float(e3["v"][-1]), float(np.max(np.abs(e3["theta"])))))
    bild_verlauf(e3, "Fahrbefehl ueber die Weboberflaeche", "bild5_fahren.png")

    # -------------------------------------------------------------------
    print("\nH  VERGLEICH: vorhandener Regler gegen ueberarbeiteten")
    print("   Der ueberarbeitete Regler rechnet mit ausgeschriebener")
    print("   Schrittweite und Beiwerten in physikalischen Einheiten.")
    print("   Rechenweg identisch mit Segway.ino.\n")

    def z(b): return "balanciert" if b["stabil"] else "FAELLT UM "
    def rr(b): return "   -   " if not b["stabil"] else "%5.3f  " % b["rest"]

    print("   H.1  Arbeitspunkt (Restzittern in Grad)")
    for reg in ("alt", "neu"):
        b = bewerte(simuliere(p, dauer=10.0, theta0_grad=3.0, regler=reg))
        print("        %s : %s  %s  Einschwingen %s"
              % (reg, z(b), rr(b),
                 " - " if not b["stabil"] else "%.2f s" % b["t_ein"]))

    print("\n   H.2  Mikroschrittteilung geaendert")
    for ns in (800, 1600, 3200, 6400):
        ba = bewerte(simuliere(Parameter(Ns=ns, a_max=p.a_max), dauer=10.0,
                               theta0_grad=3.0, regler="alt"))
        bn = bewerte(simuliere(Parameter(Ns=ns, a_max=p.a_max), dauer=10.0,
                               theta0_grad=3.0, regler="neu"))
        print("        Ns %5d | alt %s %s | neu %s %s"
              % (ns, z(ba), rr(ba), z(bn), rr(bn)))

    print("\n   H.3  Ausgaberate des Sensors geaendert")
    for f in (50, 100, 200, 250):
        ba = bewerte(simuliere(Parameter(f_dmp=f, a_max=p.a_max), dauer=10.0,
                               theta0_grad=3.0, regler="alt"))
        bn = bewerte(simuliere(Parameter(f_dmp=f, a_max=p.a_max), dauer=10.0,
                               theta0_grad=3.0, regler="neu"))
        print("        %4d Hz | alt %s %s | neu %s %s"
              % (f, z(ba), rr(ba), z(bn), rr(bn)))

    print("\n   H.4  Hoechste Schrittfrequenz geaendert (Fangbereich)")
    # Gerechnet wird am selben Arbeitspunkt wie der uebrige Bericht -
    # frueher stand hier eine eigene Beschleunigungsgrenze, was die Zeilen
    # mit den anderen Abschnitten unvergleichbar machte.
    for ms in (4000, 8000, 12000, 16000):
        aus = []
        for reg in ("alt", "neu"):
            g = 0
            for th0 in range(2, 36):
                if bewerte(simuliere(Parameter(MAX_SPEED=ms, Ns=p.Ns,
                                               a_max=p.a_max),
                                     dauer=8.0, theta0_grad=th0,
                                     regler=reg))["stabil"]:
                    g = th0
                else:
                    break
            aus.append(g)
        print("        %6d Hz | alt %2d Grad | neu %2d Grad"
              % (ms, aus[0], aus[1]))

    print("\n   Bilder geschrieben: bild1 bis bild5")
    print(strich)


if __name__ == "__main__":
    matplotlib.use("Agg")
    main()
