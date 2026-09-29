# -*- coding: utf-8 -*-
"""
pruefung_entwurf.py — Nachweis des Entwurfs am vollstaendigen Modell

Die Eigenwerte in segway_entwurf.py sagen etwas ueber den linearisierten
Kreis. Alles, was daran nichtlinear ist, sagen sie nicht:

    Begrenzung der Schrittfrequenz     -> Fangbereich
    Beschleunigungsgrenze der Motoren  -> Schrittverlust
    Rauschen von Kreisel und Beschleunigungsmesser
    Kreiselnullpunkt
    Schwerpunktversatz als echtes Moment
    Anti-Windup in der Begrenzung

Deshalb wird jeder Entwurf hier zusaetzlich durchgefahren. Die Pruefungen
sind so geschrieben, dass sie einzeln aufgerufen werden koennen.
"""

import io

import numpy as np
import segway_modell as M


# ---------------------------------------------------------------------------
#  Aufbau des Nutzers, Zahlen aus dem Vorlesungsmanuskript 1.1
# ---------------------------------------------------------------------------
GRUND = dict(m=0.35, l=0.12, r_rad=0.033, Ns=1600, MAX_SPEED=6000,
             f_dmp=250.0, f_gitter=250.0, tau_mot=0.002,
             sensor_art="kalman", feinschritte=32, sensor_w=0.05,
             nk_art="geschwindigkeit", d_quelle="kreisel",
             a_komp_anteil=0.0,
             # Rampe: setAcceleration(50000) mal Schrittweite
             a_max=6.48,
             # Totzone: am Modell die Ursache des Zitterns, deshalb null
             MIN_SPEED=0,
             # Kreisel wird beim Start mitkalibriert, es bleibt ein Rest
             gyro_bias=0.05, rausch_grad=0.05, gyro_rausch=0.05)


def parameter(entwurf, **aenderungen):
    d = dict(GRUND)
    d.update(entwurf)
    d.update(aenderungen)
    return M.Parameter(**d)


# ---------------------------------------------------------------------------
#  Einzelne Pruefungen
# ---------------------------------------------------------------------------

# Die Suchlaeufe rechnen die Mechanik gruober (8 statt 32 Rechenschritte je
# Regeltakt). Der Streckenfehler steigt dadurch von 0,05 auf 0,19 Prozent
# ueber eine Viertelsekunde - fuer eine Suche ohne Belang, aber viermal so
# schnell. Der gefundene Wert wird anschliessend fein bestaetigt.
GROB = 8
FEIN = 32


def _suche(pruefe, werte):
    """Groesster Wert der Reihe, der die Pruefung besteht - grob, dann fein."""
    gut = 0.0
    for wert in werte:
        if pruefe(float(wert), GROB):
            gut = float(wert)
        else:
            break
    while gut > 0.0 and not pruefe(gut, FEIN):
        vorher = [w for w in werte if w < gut]
        if not vorher:
            return 0.0
        gut = float(vorher[-1])
    return gut


def fangbereich(entwurf, **aenderungen):
    """Groesste Anfangsneigung, aus der das Fahrzeug noch aufrichtet."""
    def pruefe(grad, fein):
        p = parameter(entwurf, feinschritte=fein, **aenderungen)
        return M.bewerte(M.simuliere(p, dauer=12.0, theta0_grad=grad,
                                     regler="entwurf"))["stabil"]
    return _suche(pruefe, np.arange(0.5, 30.1, 0.5))


def fangfeld(entwurf, winkel, raten, **aenderungen):
    """
    Aus welcher Kombination von Winkel und Drehrate richtet es noch auf?
    Aus der Ruhe zu pruefen genuegt nicht - beim Anfahren aus der Hand ist
    das Fahrzeug in Bewegung.
    """
    feld = {}
    for gr in winkel:
        for ra in raten:
            p = parameter(entwurf, feinschritte=GROB, **aenderungen)
            feld[(gr, ra)] = M.bewerte(M.simuliere(
                p, dauer=10.0, theta0_grad=float(gr),
                omega0_grad_s=float(ra), regler="entwurf"))["stabil"]
    return feld


def stossfestigkeit(entwurf, **aenderungen):
    """Groesstes kurzes Stoermoment (50 ms), das noch weggesteckt wird."""
    def pruefe(moment, fein):
        p = parameter(entwurf, feinschritte=fein, **aenderungen)
        st = lambda t, m=moment: m if 3.0 <= t < 3.05 else 0.0
        return M.bewerte(M.simuliere(p, dauer=15.0, theta0_grad=0.0,
                                     regler="entwurf", stoerung=st))["stabil"]
    return _suche(pruefe, np.arange(0.01, 0.61, 0.01))


def nullpunkttoleranz(entwurf, **aenderungen):
    """Groesster Schwerpunktversatz, der noch ausgeregelt wird."""
    def pruefe(s_mm, fein):
        p = parameter(entwurf, s_versatz=s_mm * 1e-3, feinschritte=fein,
                      **aenderungen)
        b = M.bewerte(M.simuliere(p, dauer=40.0, theta0_grad=1.0,
                                  regler="entwurf"))
        return b["stabil"] and b["weg"] < 2.0
    return _suche(pruefe, np.arange(0.5, 20.1, 0.5))


def steht_bei_null(entwurf, **aenderungen):
    """
    Forderung: ist der Istwinkel null, darf sich das Fahrzeug nicht bewegen.

    Geprueft wird am eingeschwungenen Zustand: wie weit laeuft das Fahrzeug
    in den letzten zwanzig Sekunden noch, und wie gross ist der Istwinkel
    im Mittel.
    """
    p = parameter(entwurf, **aenderungen)
    erg = M.simuliere(p, dauer=60.0, theta0_grad=1.0, regler="entwurf")
    if M.bewerte(erg)["stabil"] is False:
        return dict(stabil=False)
    n = len(erg["t"])
    ab = n - int(20.0 * p.f_gitter)
    weg = float(abs(erg["x"][-1] - erg["x"][ab]))
    ist = erg["theta_mess"][ab:] - erg["soll"][ab:]
    return dict(stabil=True, weg_20s=weg,
                istwinkel_mittel=float(np.mean(ist)),
                istwinkel_streuung=float(np.std(ist)),
                nullpunkt=float(erg["soll"][-1]),
                v_mittel=float(np.mean(erg["f"][ab:]) * p.v_je_hz))


def schrittverlust(entwurf, **aenderungen):
    """
    Groesste geforderte Beschleunigung im Betrieb. Liegt sie ueber dem, was
    die Motoren hergeben, gehen Schritte verloren und die Annahme
    "Frequenz = Radgeschwindigkeit" faellt.
    """
    p = parameter(entwurf, **aenderungen)
    erg = M.simuliere(p, dauer=20.0, theta0_grad=5.0, regler="entwurf")
    v = erg["f"] * p.v_je_hz
    a = np.diff(v) * p.f_gitter
    return dict(a_gefordert=float(np.max(np.abs(a))), a_moeglich=p.a_max,
                f_groesste=float(np.max(np.abs(erg["f"]))),
                f_grenze=p.MAX_SPEED)


def fahren(entwurf, v_wunsch_hz=1500.0, **aenderungen):
    """Fahrbefehl: erreicht das Fahrzeug die befohlene Geschwindigkeit?"""
    p = parameter(entwurf, **aenderungen)
    soll = lambda t: (v_wunsch_hz / p.SPEED_SKAL) if t > 5.0 else 0.0
    erg = M.simuliere(p, dauer=25.0, theta0_grad=0.0, regler="entwurf",
                      speed_sollverlauf=soll)
    b = M.bewerte(erg)
    if not b["stabil"]:
        return dict(stabil=False)
    n = len(erg["t"])
    ab = n - int(5.0 * p.f_gitter)
    return dict(stabil=True,
                v_soll=v_wunsch_hz * p.v_je_hz,
                v_ist=float(np.mean(erg["f"][ab:]) * p.v_je_hz),
                winkel=float(np.mean(erg["theta"][ab:])))


# ---------------------------------------------------------------------------
#  Bilder
# ---------------------------------------------------------------------------

def bild_aufrichten(entwurf, datei="entwurf1_aufrichten.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    p = parameter(entwurf, s_versatz=2e-3)
    erg = M.simuliere(p, dauer=25.0, theta0_grad=5.0, regler="entwurf")
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    ax[0].plot(erg["t"], erg["theta"], lw=1.5, label="wahre Neigung")
    ax[0].plot(erg["t"], erg["soll"], lw=1.5,
               label="Nullpunkt (Schicht 4)")
    ax[0].axhline(-np.rad2deg(np.arctan(2e-3 / p.l)), ls=":", color="k",
                  label="Gleichgewichtswinkel")
    ax[0].set_ylabel("Grad")
    ax[0].legend(fontsize=8)
    ax[0].set_title("Aufrichten aus 5 Grad bei 2 mm Schwerpunktversatz")
    ax[1].plot(erg["t"], erg["f"], lw=1.0)
    ax[1].set_ylabel("Schrittfrequenz [Hz]")
    ax[2].plot(erg["t"], erg["x"], lw=1.5)
    ax[2].set_ylabel("Weg [m]")
    ax[2].set_xlabel("Zeit [s]")
    for a in ax:
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(datei, dpi=110)
    plt.close(fig)


def bild_nullpunkt(entwurf, datei="entwurf2_nullpunkt.png"):
    """Der Nullpunkt findet den Gleichgewichtswinkel - fuer mehrere Versaetze."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5))
    for s_mm in (0.5, 1.0, 2.0, 4.0):
        p = parameter(entwurf, s_versatz=s_mm * 1e-3)
        erg = M.simuliere(p, dauer=60.0, theta0_grad=0.5, regler="entwurf")
        linie, = ax.plot(erg["t"], erg["soll"], lw=1.5,
                         label="%.1f mm Versatz" % s_mm)
        ax.axhline(-np.rad2deg(np.arctan(s_mm * 1e-3 / p.l)), ls=":",
                   color=linie.get_color())
    ax.set_xlabel("Zeit [s]")
    ax.set_ylabel("nachgefuehrter Nullpunkt [Grad]")
    ax.set_title("Schicht 4 findet den Gleichgewichtswinkel "
                 "(gepunktet: der berechnete Wert)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(datei, dpi=110)
    plt.close(fig)


def bild_vergleich(entwurf, datei="entwurf3_vergleich.png"):
    """Mit und ohne Nullpunktkorrektur, gleicher Versatz."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for art, name in (("aus", "ohne Nullpunktkorrektur"),
                      ("geschwindigkeit", "mit Nullpunktkorrektur")):
        p = parameter(entwurf, s_versatz=1e-3, nk_art=art)
        erg = M.simuliere(p, dauer=30.0, theta0_grad=0.5, regler="entwurf")
        ax[0].plot(erg["t"], erg["theta"], lw=1.5, label=name)
        ax[1].plot(erg["t"], erg["x"], lw=1.5, label=name)
    ax[0].set_ylabel("Neigung [Grad]")
    ax[0].set_title("1 mm Schwerpunktversatz - der Unterschied macht Schicht 4")
    ax[1].set_ylabel("Weg [m]")
    ax[1].set_xlabel("Zeit [s]")
    for a in ax:
        a.grid(alpha=0.3)
        a.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(datei, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
#  Vollstaendiger Nachweis
# ---------------------------------------------------------------------------

def bericht(entwurf, datei="bericht_entwurf.txt"):
    """Faehrt alle Pruefungen und schreibt das Ergebnis als Tabelle."""
    z = []
    def sag(t=""):
        z.append(t)
        print(t, flush=True)

    p = parameter(entwurf)
    sag("=" * 78)
    sag("NACHWEIS DES ENTWURFS AM VOLLSTAENDIGEN MODELL")
    sag("=" * 78)
    sag()
    sag("Aufbau     m = %.2f kg, l = %.3f m, J = %.5f kg m2" % (p.m, p.l, p.J))
    sag("           Rad %.1f mm, %d Schritte je Umdrehung -> %.4f mm je Schritt"
        % (2000 * p.r_rad, p.Ns, 1000 * p.v_je_hz))
    sag("           Kippzeitkonstante %.4f s" % p.t_kipp)
    sag("           Rampe %.2f m/s2, Totzone %d Hz, Grenze %d Hz"
        % (p.a_max, p.MIN_SPEED, p.MAX_SPEED))
    sag()
    sag("Regler     K  = %.3f m/s je rad   Tn = %.4f s   Tv = %.4f s"
        % (p.N_K, p.N_TN, p.N_TV))
    sag("           ki = K/Tn = %.2f  (Bedingung ki > g = 9,81 %s)"
        % (p.N_K / p.N_TN, "erfuellt" if p.N_K / p.N_TN > p.g else "VERLETZT"))
    sag("Nullpunkt  K  = %.4f rad je m/s   Tn = %.3f s   Grenze %.1f Grad"
        % (p.NK_K, p.NK_TN, np.rad2deg(p.NK_MAX)))
    sag("Filter     Q_ANGLE = %.4f  Q_BIAS = %.4f  R_MEASURE = %.2f"
        % (p.Q_ANGLE, p.Q_BIAS, p.R_MEASURE))
    sag("           Beschleunigungskompensation: %s"
        % ("aus" if p.a_komp_anteil == 0 else "%.0f %%" % (100 * p.a_komp_anteil)))
    sag()

    sag("-" * 78)
    sag("A  GRENZEN")
    sag("-" * 78)
    sag("   Fangbereich aus der Ruhe          %5.1f Grad" % fangbereich(entwurf))
    sag("   Sicherheitsabschaltung            %5.1f Grad" % p.KIPP_GRENZE)
    sag("   Stossfestigkeit (50 ms)           %5.3f Nm" % stossfestigkeit(entwurf))
    sag("   Nullpunkttoleranz                 %5.1f mm Schwerpunktversatz"
        % nullpunkttoleranz(entwurf))
    r = schrittverlust(entwurf)
    sag("   groesste geforderte Beschleunigung %5.2f m/s2 (zulaessig %.2f)"
        % (r["a_gefordert"], r["a_moeglich"]))
    sag("   groesste Schrittfrequenz          %5.0f Hz (Grenze %d)"
        % (r["f_groesste"], r["f_grenze"]))
    sag()

    sag("   Fangfeld (ja = richtet auf), Winkel senkrecht, Drehrate waagerecht")
    raten = (0, 30, 60, 90, 120, 180)
    winkel = (0, 2, 5, 8, 10, 15, 20)
    feld = fangfeld(entwurf, winkel, raten)
    sag("        " + "".join("%8.0f" % r for r in raten) + "  Grad/s")
    for gr in winkel:
        sag("   %3.0f  " % gr
            + "".join("%8s" % ("ja" if feld[(gr, r)] else "nein")
                      for r in raten))
    sag()

    sag("-" * 78)
    sag("B  ISTWINKEL NULL BEDEUTET STILLSTAND")
    sag("-" * 78)
    r = steht_bei_null(entwurf)
    if r["stabil"]:
        sag("   Weg in den letzten 20 s           %8.4f m" % r["weg_20s"])
        sag("   mittlerer Istwinkel               %8.5f Grad" % r["istwinkel_mittel"])
        sag("   Streuung des Istwinkels           %8.5f Grad" % r["istwinkel_streuung"])
        sag("   mittlere Geschwindigkeit          %8.5f m/s" % r["v_mittel"])
        sag("   gefundener Nullpunkt              %8.4f Grad" % r["nullpunkt"])
    else:
        sag("   NICHT STABIL")
    sag()

    sag("-" * 78)
    sag("C  SCHICHT 4 FINDET DEN GLEICHGEWICHTSWINKEL")
    sag("-" * 78)
    sag("   Versatz   berechnet    gefunden    Weg")
    for s_mm in (0.5, 1.0, 2.0, 4.0):
        q = parameter(entwurf, s_versatz=s_mm * 1e-3)
        erg = M.simuliere(q, dauer=60.0, theta0_grad=0.5, regler="entwurf")
        b = M.bewerte(erg)
        soll = -np.rad2deg(np.arctan(s_mm * 1e-3 / q.l))
        sag("   %4.1f mm  %8.4f Grad %8.4f Grad %7.3f m  %s"
            % (s_mm, soll, erg["soll"][-1], b["weg"],
               "stabil" if b["stabil"] else "FAELLT"))
    sag()

    sag("-" * 78)
    sag("D  MIT UND OHNE SCHICHT 4")
    sag("-" * 78)
    sag("   Versatz   ohne Korrektur          mit Korrektur")
    for s_mm in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0):
        zeile = []
        for art in ("aus", "geschwindigkeit"):
            q = parameter(entwurf, s_versatz=s_mm * 1e-3, nk_art=art)
            b = M.bewerte(M.simuliere(q, dauer=40.0, theta0_grad=0.5,
                                      regler="entwurf"))
            zeile.append("%-8s Weg %6.2f m" %
                         ("stabil" if b["stabil"] else "FAELLT", b["weg"]))
        sag("   %4.2f mm  %s   %s" % (s_mm, zeile[0], zeile[1]))
    sag()

    sag("-" * 78)
    sag("E  FAHRBEFEHL")
    sag("-" * 78)
    for hz in (500.0, 1000.0, 2000.0, 3000.0):
        r = fahren(entwurf, v_wunsch_hz=hz)
        if r["stabil"]:
            sag("   befohlen %.3f m/s -> erreicht %.3f m/s bei %.3f Grad Neigung"
                % (r["v_soll"], r["v_ist"], r["winkel"]))
        else:
            sag("   befohlen %.3f m/s -> FAELLT" % (hz * p.v_je_hz))
    sag()
    sag("=" * 78)

    io.open(datei, "w", encoding="utf-8").write("\n".join(z) + "\n")
    return "\n".join(z)
