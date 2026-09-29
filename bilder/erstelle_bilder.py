#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""erstelle_bilder.py — die gezeichneten Bilder des Manuskripts (Blockschaltbilder), lesbar bei Seitenbreite.

Erzeugt in Bilder/:
  blockschaltbild_regelkreis.png   der modelltechnisch geschlossene Kreis: Strecke, Sensor, vier Schichten, Takt (Hochformat)
  strecke_signalfluss.png          die Strecke als Übertragungssystem: Ein- und Ausgänge, Blöcke im Laplace-Bereich
  kreis_signalfluss.png            der geschlossene Kreis im Laplace-Bereich: Regler, Tiefpass, Antrieb, Mechanik

Regel: die Bilder sind höchstens 8,5 Zoll breit gezeichnet, damit die Schrift bei 16 cm Satzbreite noch mindestens
7 pt hat; Kastentexte werden nur verkleinert, wenn sie nicht hineinpassen (dann steht es in der Ausgabe). Jedes Bild
wird nach dem Bau angesehen.  Aufruf: python3 Bilder/erstelle_bilder.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

H = Path(__file__).resolve().parent
BLAU, ROT, GRUEN, ORANGE, GRAU = "#2b4c7e", "#b0171f", "#2e7d32", "#b06a00", "#666666"
VERKLEINERT = []


def kasten(ax, x, y, w, h, titel, zeilen=(), farbe=BLAU, fuellung="#eef2fa", ts=10.5, zs=9):
    """Kasten mit Titel und Zeilen; passt die Schrift nur an, wenn sie nicht hineinpasst, und meldet das."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", lw=1.6, ec=farbe, fc=fuellung))
    if not zeilen:
        ax.text(x + w / 2, y + h / 2, titel, ha="center", va="center", fontsize=ts, fontweight="bold", color=farbe)
        return
    t1 = ax.text(x + w / 2, y + h - 0.16, titel, ha="center", va="top", fontsize=ts, fontweight="bold", color=farbe)
    t2 = ax.text(x + w / 2, y + h / 2, "\n".join(zeilen), ha="center", va="center", fontsize=zs, linespacing=1.3)
    r = ax.figure.canvas.get_renderer(); inv = ax.transData.inverted()
    def mass(t):
        bb = t.get_window_extent(renderer=r); (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]]); return x1 - x0, y1 - y0
    n = 0
    for _ in range(30):
        w1, h1 = mass(t1); w2, h2 = mass(t2)
        if w1 <= w - 0.25 and w2 <= w - 0.25 and h1 + h2 <= h - 0.4: break
        t1.set_fontsize(t1.get_fontsize() - 0.25); t2.set_fontsize(t2.get_fontsize() - 0.25); n += 1
    if n: VERKLEINERT.append(f"{titel.splitlines()[0]}: Schrift auf {t2.get_fontsize():.1f} pt")
    w1, h1 = mass(t1)
    t2.set_position((x + w / 2, y + (h - h1 - 0.16) / 2))


def pfeil(ax, p0, p1, text="", farbe="#222", lage="oben", ts=8.5, dx=0.0, dy=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13, lw=1.4, color=farbe, shrinkA=0, shrinkB=0))
    if text:
        xm, ym = (p0[0] + p1[0]) / 2 + dx, (p0[1] + p1[1]) / 2 + dy
        va = {"oben": "bottom", "unten": "top", "mitte": "center"}[lage]; off = {"oben": 0.08, "unten": -0.08, "mitte": 0}[lage]
        ax.text(xm, ym + off, text, ha="center", va=va, fontsize=ts, color=farbe, bbox=dict(fc="white", ec="none", pad=1.0))


def blockschaltbild():
    fig, ax = plt.subplots(figsize=(8.5, 10.6))
    ax.set_xlim(0, 17); ax.set_ylim(0, 21.2); ax.axis("off")
    ax.text(8.5, 20.9, "Der modelltechnisch geschlossene Regelkreis:\nStrecke, Sensor und die vier Schichten der Firmware", ha="center", va="top", fontsize=12, fontweight="bold", linespacing=1.3)
    ax.add_patch(FancyBboxPatch((0.4, 8.6), 16.2, 10.6, boxstyle="round,pad=0.02", lw=1.2, ec="#888", fc="#fafafa", ls="--"))
    ax.text(0.8, 19.05, "Firmware auf dem ESP32 — ein Takt T = 4 ms (250 Hz)", fontsize=9.5, color="#444", va="top")
    kasten(ax, 3.0, 15.2, 11.0, 3.2, "Schicht 4 · Nullpunktkorrektur",
           ["PI auf e = v_wunsch − v_aus  →  Nullpunkt in Grad,  Anschlag ±6°",
            "Istwinkel null muss Stillstand bedeuten: die Fahrgeschwindigkeit",
            "verrät den wahren Gleichgewichtswinkel −arctan(s/l)"], farbe=ORANGE, fuellung="#fdf3e3")
    kasten(ax, 0.8, 9.6, 4.9, 4.2, "Schicht 1\nWinkelerfassung", ["Kalman-Filter:", "Winkel und Kreisel-", "nullpunkt; Istwinkel =", "Schätzung − Nullpunkt"], farbe=BLAU, ts=10)
    kasten(ax, 6.05, 9.6, 4.9, 4.2, "Schicht 2\nWinkelregler", ["PID in Normalform,", "m/s und rad:", "v = K(e + ∫e/T_n + T_v ė)", "D-Anteil vom Kreisel"], farbe=BLAU, ts=10)
    kasten(ax, 11.3, 9.6, 4.9, 4.2, "Schicht 3\nMotorausgabe", ["Rampe a_max, Grenze", "6000 Hz; f = v·N_s/(2πr)", "→ Schrittimpulse;", "meldet v_aus, Weg x"], farbe=BLAU, ts=10)
    pfeil(ax, (5.7, 11.7), (6.05, 11.7)); ax.text(5.88, 11.95, "θ_ist, θ̇", ha="center", fontsize=8.5)
    pfeil(ax, (10.95, 11.7), (11.3, 11.7)); ax.text(11.12, 11.95, "v_soll", ha="center", fontsize=8.5)
    ax.plot([13.75, 13.75], [13.8, 16.8], color=ORANGE, lw=1.4); pfeil(ax, (13.75, 16.8), (14.0, 16.8), "", farbe=ORANGE)
    ax.text(13.95, 14.6, "v_aus, Weg", fontsize=8.5, color=ORANGE, ha="left")
    ax.plot([3.0, 3.25], [16.8, 16.8], color=ORANGE, lw=1.4); ax.plot([3.25, 3.25], [16.8, 14.4], color=ORANGE, lw=1.4)
    pfeil(ax, (3.25, 14.4), (3.25, 13.8), "", farbe=ORANGE); ax.text(3.45, 14.6, "Nullpunkt [°]", fontsize=8.5, color=ORANGE, ha="left")
    kasten(ax, 9.4, 1.6, 7.2, 5.6, "Strecke (Modell)",
           ["Antrieb:  v̇ = (v_soll − v)/τ_mot,  |v̇| ≤ a_max", "Mechanik:", "J θ̈ = m g (l sinθ + s cosθ)", "     − m v̇ (l cosθ − s sinθ) − d θ̇ + M",
            "32 Feinschritte je Takt; Zustände θ, θ̇, v, x", "gemessen: m, J/(m l), l, w, u, r"], farbe=GRUEN, fuellung="#eaf5ea", zs=8.8)
    kasten(ax, 0.4, 1.6, 7.2, 5.6, "Sensor MPU6050 (Modell)",
           ["Beschleunigung am Sensor:", "a_s = v̇ + w θ̈ − u θ̇²", "Rohwinkel θ_roh = θ − arctan(a_s/g)", "Drehrate mit Nullpunkt  θ̇ + b",
            "Tiefpass 42 Hz (4,8 ms), Rauschen,", "Abtastung 250 Hz"], farbe=ROT, fuellung="#fbeaea", zs=8.8)
    pfeil(ax, (13.75, 9.6), (13.75, 7.2)); ax.text(13.95, 8.4, "Schrittfrequenz f ⇒ v_aus", fontsize=8.5, ha="left")
    pfeil(ax, (9.4, 4.4), (7.6, 4.4), "θ, θ̇, θ̈, v̇", lage="oben")
    pfeil(ax, (3.25, 7.2), (3.25, 9.6)); ax.text(3.45, 8.4, "Rohwinkel, Drehrate", fontsize=8.5, ha="left")
    pfeil(ax, (16.95, 3.0), (16.6, 3.0), "", farbe=GRAU); ax.text(16.95, 3.3, "Störmoment M", fontsize=8, color=GRAU, ha="right", va="bottom")
    ax.text(8.5, 0.9, "Nachgewiesen: Eigenwerte des linearisierten Kreises (16 Zustände) · Fangbereich, Stoß, Nullpunkttoleranz (nichtlinear)\n"
            "· Firmware = Modell (10⁻⁸ °) · Strecke = Gerät (Radpendel)", ha="center", va="top", fontsize=8.5, color="#333", linespacing=1.3)
    fig.savefig(H / "blockschaltbild_regelkreis.png", dpi=170, bbox_inches="tight", pad_inches=0.12); plt.close(fig)


def strecke_signalfluss():
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    ax.set_xlim(0, 17); ax.set_ylim(0, 11.2); ax.axis("off")
    ax.text(8.5, 11.0, "Die Strecke als Übertragungssystem: Eingang Sollgeschwindigkeit,\nAusgang Neigung (linearisiert, Laplace-Bereich)", ha="center", va="top", fontsize=11, fontweight="bold", linespacing=1.3)
    y = 6.6
    ax.text(0.2, y, "V_soll(s)\n[m/s]", ha="left", va="center", fontsize=9)
    pfeil(ax, (1.5, y), (2.3, y))
    kasten(ax, 2.3, y - 0.95, 2.9, 1.9, "Antrieb", ["1/(1 + τ_mot s)", "τ_mot = 2 ms"], farbe=GRUEN, fuellung="#eaf5ea", ts=9.5, zs=8.5)
    pfeil(ax, (5.2, y), (6.0, y), "V", lage="oben")
    kasten(ax, 6.0, y - 0.95, 1.9, 1.9, "d/dt", ["s"], farbe=GRUEN, fuellung="#eaf5ea", ts=9.5, zs=9)
    pfeil(ax, (7.9, y), (8.7, y), "V̇", lage="oben")
    kasten(ax, 8.7, y - 0.95, 2.2, 1.9, "Hebel", ["−m l"], farbe=GRUEN, fuellung="#eaf5ea", ts=9.5, zs=9)
    ax.add_patch(plt.Circle((11.8, y), 0.38, ec="#222", fc="white", lw=1.4)); ax.text(11.8, y, "Σ", ha="center", va="center", fontsize=12)
    pfeil(ax, (10.9, y), (11.42, y))
    kasten(ax, 12.7, y - 0.95, 3.9, 1.9, "Mechanik", ["1/(J s² + d s − m g l)"], farbe=GRUEN, fuellung="#eaf5ea", ts=9.5, zs=8.5)
    pfeil(ax, (12.18, y), (12.7, y))
    pfeil(ax, (16.6, y), (16.95, y)); ax.text(16.3, y + 1.2, "Θ(s) [rad]", ha="center", fontsize=9)
    pfeil(ax, (11.8, 9.3), (11.8, y + 0.38), "", farbe=GRAU); ax.text(12.0, 8.6, "Störmoment M(s)", fontsize=8.5, color=GRAU, ha="left")
    pfeil(ax, (11.8, 4.0), (11.8, y - 0.38), "", farbe=GRAU); ax.text(12.0, 4.7, "Versatz: m g s (konstant)", fontsize=8.5, color=GRAU, ha="left")
    ax.text(0.2, 3.5, "G_u(s) = Θ(s)/V_soll(s) = −m l s / [ (1 + τ_mot s)(J s² + d s − m g l) ]", fontsize=10, va="center")
    ax.text(0.2, 2.6, "Nullstelle s = 0: eine konstante Geschwindigkeit ändert die Neigung nicht, nur ihre Änderung wirkt.\n"
            "Ein Pol rechts (+1/T, T = 106,7 ms): ohne Regler kippt der Aufbau mit e^{t/T}.\n"
            "Vorzeichen: Sollgeschwindigkeit nach vorn (u > 0) neigt den Aufbau nach hinten (θ < 0).\n"
            "Der Versatz s wirkt wie ein Störmoment und verschiebt das Gleichgewicht auf θ_gl = −arctan(s/l).", fontsize=8.5, va="top", color="#333", linespacing=1.4)
    fig.savefig(H / "strecke_signalfluss.png", dpi=170, bbox_inches="tight", pad_inches=0.12); plt.close(fig)


def kreis_signalfluss():
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    ax.set_xlim(0, 17); ax.set_ylim(0, 11.2); ax.axis("off")
    ax.text(8.5, 11.0, "Der geschlossene Kreis im Laplace-Bereich\n(Schicht 2 mit Sensor-Tiefpass, ohne die langsame Schicht 4)", ha="center", va="top", fontsize=11, fontweight="bold", linespacing=1.3)
    y = 7.0
    ax.add_patch(plt.Circle((1.7, y), 0.38, ec="#222", fc="white", lw=1.4)); ax.text(1.7, y, "Σ", ha="center", va="center", fontsize=12)
    ax.text(0.15, y + 0.05, "Soll\n= 0", ha="left", va="center", fontsize=9); pfeil(ax, (0.95, y), (1.32, y))
    ax.text(2.25, y + 0.5, "e", fontsize=9); pfeil(ax, (2.08, y), (2.9, y))
    kasten(ax, 2.9, y - 1.1, 4.2, 2.2, "Regler (Schicht 2)", ["K (1 + 1/(T_n s) + T_v s)", "K = 2,325 m/s je rad", "T_n = 86,6 ms, T_v = 8,8 ms"], farbe=BLAU, ts=9.5, zs=8.3)
    pfeil(ax, (7.1, y), (7.9, y), "V_soll", lage="oben", ts=8)
    kasten(ax, 7.9, y - 1.1, 3.1, 2.2, "Antrieb", ["1/(1 + τ_mot s)"], farbe=GRUEN, fuellung="#eaf5ea", ts=9.5, zs=8.5)
    pfeil(ax, (11.0, y), (11.8, y), "V", lage="oben")
    kasten(ax, 11.8, y - 1.1, 4.4, 2.2, "Mechanik", ["−m l s /(J s² + d s − m g l)"], farbe=GRUEN, fuellung="#eaf5ea", ts=9.5, zs=8.3)
    pfeil(ax, (16.2, y), (16.7, y)); ax.text(16.75, y, "Θ", ha="left", va="center", fontsize=10)
    ax.plot([16.45, 16.45], [y, 3.4], color="#222", lw=1.4); pfeil(ax, (16.45, 3.4), (12.2, 3.4))
    kasten(ax, 8.2, 2.35, 4.0, 2.1, "Sensor", ["1/(1 + τ_lp s)", "τ_lp = 4,8 ms (42 Hz)"], farbe=ROT, fuellung="#fbeaea", ts=9.5, zs=8.5)
    pfeil(ax, (8.2, 3.4), (1.7, 3.4)); pfeil(ax, (1.7, 3.4), (1.7, y - 0.38))
    ax.text(4.95, 3.6, "Θ_m  (Kalman ≈ 1 für die Kippbewegung)", ha="center", va="bottom", fontsize=8.3)
    ax.text(1.05, 5.8, "−", fontsize=13)
    ax.text(0.2, 1.5, "1 − G_u(s)·C(s)·S(s) = 0   ⇒   (1 + τ_mot s)(1 + τ_lp s)(J s² + d s − m g l) T_n  +  m l K (T_n T_v s² + T_n s + 1) = 0\n"
            "Grad 4; ohne die Verzüge bleibt  (J + m l K T_v) s² + (d + m l K) s + m l (K/T_n − g) = 0  — stabil genau dann, wenn K/T_n > g.",
            fontsize=8.3, va="top", linespacing=1.5)
    fig.savefig(H / "kreis_signalfluss.png", dpi=170, bbox_inches="tight", pad_inches=0.12); plt.close(fig)


if __name__ == "__main__":
    blockschaltbild(); strecke_signalfluss(); kreis_signalfluss()
    for n in ("blockschaltbild_regelkreis.png", "strecke_signalfluss.png", "kreis_signalfluss.png"):
        print(n, (H / n).stat().st_size, "Byte")
    for v in VERKLEINERT:
        print("verkleinert:", v)
