#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""erstelle_einfuehrung.py — das Einführungsdokument zum Segway (Auftrag 29.09.2026).

Auftrag des Verfassers, wörtlich: „ein kleines Einführungsdokument: darauf zu sehen der reale Segway, darunter ein
Strukturbild mit realer Strecke, in der die Übertragungsfunktion oder die DGL wirklich drinsteht mit Verweis auf die
Seitenzahl; ein abgetastetes System, das die Strecke speist und auch misst, wobei das abgetastete System dem Aufbau im
ESP32 entspricht und auch die Reglerparameter enthält sowie die anderen Parameter — alle Parameter nur als Variablen mit
Verweis auf die Herkunft im Manuskript. Darunter die Struktur der Simulation, darunter dasselbe, nur anstelle der
Simulationsstrecke die IO-Peripherie des ESP32, dann die bildliche Beschreibung der Hardwaremodule (immer mit den realen
Schnittstellen) und dann das Bild des realen Segways. In den Tabellen auch die aktuellen Werte, in den Strukturbildern
nicht. Die ganze Software und die Simulation muss dem entsprechen — hier darf es nicht zu Abweichungen kommen.“

Quellen — keine Zahl von Hand:
  Werte      Modell/uebertragungsfunktion.json (Parameter, aus Firmware und Messung, geprüft M13) und
             Modell/gemessen_2026-09-28/nachweis_gemessen.json (Abschnitt firmware: aus dem Quelltext gelesen)
  Seiten     aus dem gesetzten Manuskript MANUSKRIPT_Segway_Gesamt_F<n>.pdf (pdftotext je Seite, Überschrift gesucht)
  Namen      die Bezeichner in segway_regelung.ino, segway_modell.py, segway_labor_modell.js (Tabelle „Schnittstellen“)
Erzeugt: Bilder/einf_struktur_real.png, einf_struktur_simulation.png, einf_struktur_esp32.png, einf_hardware.png,
         Einfuehrung/EINFUEHRUNG_Segway.md und .pdf, Einfuehrung/einfuehrung_seiten.json (Seitenverweise und Bildtexte für die Prüfung)
Aufruf: python3 Einfuehrung/erstelle_einfuehrung.py
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

H = Path(__file__).resolve().parent
W = H.parent
B = W / "Bilder"
U = json.load(open(W / "Modell/uebertragungsfunktion.json", encoding="utf-8"))
NG = json.load(open(W / "Modell/gemessen_2026-09-28/nachweis_gemessen.json", encoding="utf-8"))
P = U["parameter"]; FW = NG["firmware"]
MD = (W / "MANUSKRIPT_Segway_Gesamt.md").read_text(encoding="utf-8")
kopf = re.search(r'^date: "Fassung (\d+) · ([^(]+?)\s*\(', MD, re.M)
F, DATUM = kopf.group(1), kopf.group(2).strip()
PDF = W / f"MANUSKRIPT_Segway_Gesamt_F{F}.pdf"
NAMENSNENNUNG = "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
BLAU, ROT, GRUEN, ORANGE, GRAU, LILA = "#2b4c7e", "#b0171f", "#2e7d32", "#b06a00", "#666666", "#5b3d8a"
BILDTEXTE: dict[str, list[str]] = {}          # jeder Text, der in ein Strukturbild geschrieben wird — für die Prüfung


# ----------------------------------------------------------------------------- Seiten im Manuskript
def seiten_des_manuskripts() -> list[str]:
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout).group(1))
    aus = []
    for s in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(s), "-l", str(s), "-layout", str(PDF), "-"], capture_output=True, text=True).stdout
        aus.append(re.sub(r"\s+", " ", t))
    return aus


SEITEN: list[str] = []
SEITENVERWEIS = True


def seite(ueberschrift: str) -> int:
    """Die Seite, auf der eine Überschrift des Manuskripts steht (letztes Vorkommen: das erste ist das Inhaltsverzeichnis)."""
    such = re.sub(r"\s+", " ", ueberschrift.replace("$", "").replace("\\varphi", "φ")).strip()
    treffer = [i + 1 for i, t in enumerate(SEITEN) if such in t]
    if not treffer:
        raise SystemExit(f"Überschrift nicht im PDF gefunden: {ueberschrift}")
    return treffer[-1]


# Woher jede Größe und jedes Glied kommt: Überschrift im Manuskript (wörtlich, ohne Nummer) → Seite
HERKUNFT = {
    "dgl":        "Momentenbilanz über die virtuelle Arbeit",
    "zustand":    "Zustandsgleichungen",
    "G_u":        "Die Übertragungsfunktion im Laplace-Bereich",
    "abtast":     "Die Abtastform: was der Regler alle 4 ms vorfindet",
    "zahlen":     "Die Zahlen der Strecke: gemessen, gewogen, aus den Zeichnungen gerechnet",
    "antrieb":    "Der Antrieb: Schrittfrequenz als Stellgröße",
    "einbau":     "Die Einbaulage und die Sensorkette im Modell",
    "takt":       "Takt und Laufzeit — was feststeht und nicht geschätzt ist",
    "kalman":     "Der Kalman-Filter im Einzelnen",
    "beiwerte":   "Die gewählten Beiwerte",
    "schichten":  "Der Aufbau in vier Schichten",
    "s1":         "Schicht 1: Winkelerfassung",
    "s2":         "Schicht 2: Winkelregler",
    "s3":         "Schicht 3: Motorausgabe",
    "s4":         "Schicht 4: Nullpunktkorrektur",
    "freigabe":   "Wann darf angefahren werden",
    "kreis":      "Der geschlossene Kreis im Laplace-Bereich und in der z-Ebene",
    "simulation": "Das Simulationsmodell der Strecke",
    "sensorsim":  "Das Sensormodell in der Simulation",
    "sensor":     "Was der Beschleunigungsmesser wirklich misst",
    "gleichgew":  "Gleichgewichtswinkel und Kippzeitkonstante mit den gemessenen Zahlen",
    "inbetrieb":  "Inbetriebnahme am Gerät",
    "firmware":   "Die vier Schichten Zeile für Zeile — Modell und Firmware rechnen dasselbe",
    "hwtest":     "Der Hardwaretest: Kamera, Synchron-LED, Bildauswertung und das Nachziehen des Reglers",
    "pruefstand": "Der Prüfstand und die Maße",
    "korrektur":  "Korrektur der Reglerparameter",
}
S: dict[str, int] = {}


def s(k): return f"S. {S[k]}" if SEITENVERWEIS else ""


def rein(text: str) -> str:
    """Ohne Seitenverweise bleiben leere Klammern zurück — die verschwinden."""
    return re.sub(r"\s*\(\s*(?:,\s*)*\)", "", text)


# ----------------------------------------------------------------------------- Zeichenhilfen (Querformat, 11 Zoll breit)
def kasten(ax, x, y, w, h, titel, zeilen=(), farbe=BLAU, fuellung="#eef2fa", ts=10.5, zs=9.2, bild=""):
    titel = rein(titel); zeilen = [rein(z) for z in zeilen]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", lw=1.5, ec=farbe, fc=fuellung))
    BILDTEXTE.setdefault(bild, []).append(titel); BILDTEXTE[bild].extend(zeilen)
    if not zeilen:
        ax.text(x + w / 2, y + h / 2, titel, ha="center", va="center", fontsize=ts, fontweight="bold", color=farbe); return
    t1 = ax.text(x + w / 2, y + h - 0.15, titel, ha="center", va="top", fontsize=ts if len(titel) < 60 else ts - 1.2, fontweight="bold", color=farbe, linespacing=1.2)
    t2 = ax.text(x + w / 2, y + h / 2, "\n".join(zeilen), ha="center", va="center", fontsize=zs, linespacing=1.32)
    r = ax.figure.canvas.get_renderer(); inv = ax.transData.inverted()
    def mass(t):
        bb = t.get_window_extent(renderer=r); (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]]); return x1 - x0, y1 - y0
    n = 0
    for _ in range(30):
        w1, h1 = mass(t1); w2, h2 = mass(t2)
        if w1 <= w - 0.3 and w2 <= w - 0.3 and h1 + h2 <= h - 0.4: break
        t1.set_fontsize(t1.get_fontsize() - 0.25); t2.set_fontsize(t2.get_fontsize() - 0.25); n += 1
    if n: VERKLEINERT.append(f"{bild} · {titel.splitlines()[0][:40]}: Schrift {t2.get_fontsize():.1f} pt")
    w1, h1 = mass(t1); t2.set_position((x + w / 2, y + (h - h1 - 0.15) / 2))


def pfeil(ax, p0, p1, text="", farbe="#222", lage="oben", ts=8.8, dx=0.0, dy=0.0, bild=""):
    text = rein(text)
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13, lw=1.4, color=farbe, shrinkA=0, shrinkB=0))
    if text:
        BILDTEXTE.setdefault(bild, []).append(text)
        xm, ym = (p0[0] + p1[0]) / 2 + dx, (p0[1] + p1[1]) / 2 + dy
        va = {"oben": "bottom", "unten": "top", "mitte": "center"}[lage]; off = {"oben": 0.08, "unten": -0.08, "mitte": 0}[lage]
        ax.text(xm, ym + off, text, ha="center", va=va, fontsize=ts, color=farbe, bbox=dict(fc="white", ec="none", pad=0.8))


def wort(ax, x, y, text, bild, **k):
    text = rein(text); BILDTEXTE.setdefault(bild, []).append(text); ax.text(x, y, text, **k)


VERKLEINERT: list[str] = []


def regler_bloecke(ax, bild, titelzusatz=""):
    """Das abgetastete System — vier Schichten, wie im ESP32 (Firmware = Modell = Labor); nur Variablen, mit Seiten."""
    ax.add_patch(FancyBboxPatch((0.4, 7.3), 21.2, 7.4, boxstyle="round,pad=0.02", lw=1.2, ec="#888", fc="#fafafa", ls="--"))
    t = f"Abgetastetes System — Takt T, eine Taktverzögerung ({s('takt')}); Aufbau in vier Schichten ({s('schichten')})" + (("\n" + titelzusatz) if titelzusatz else "")
    wort(ax, 0.75, 14.55, t, bild, fontsize=9, color="#444", va="top", linespacing=1.25)
    kasten(ax, 5.6, 11.35, 10.8, 2.15, f"Schicht 4 · Nullpunktkorrektur ({s('s4')})",
           ["PI:  Nullpunkt = K_N·e + (K_N/T_n,N)·∫e dt,   e = v_wunsch − v_aus,   Anschlag ±θ_N,max",
            "findet den wahren Gleichgewichtswinkel −arctan(s/l) aus der Fahrgeschwindigkeit"], farbe=ORANGE, fuellung="#fdf3e3", bild=bild)
    kasten(ax, 0.7, 7.95, 6.6, 3.0, f"Schicht 1 · Winkelerfassung ({s('s1')})",
           ["Rohwinkel θ_roh = θ_lp − arctan(a_lp/g)", "Kalman-Filter (Q_θ, Q_b, R):  θ̂, b̂", "θ_ist = θ̂ − Nullpunkt,   θ̇_ist = ω − b̂"], farbe=BLAU, bild=bild)
    kasten(ax, 7.7, 7.95, 6.6, 3.0, f"Schicht 2 · Winkelregler ({s('s2')})",
           ["PID in Normalform (m/s je rad):", "v_soll = K·(e + (1/T_n)∫e dt + T_v·θ̇_ist)", "e = 0 − θ_ist;  D-Anteil aus dem Kreisel"], farbe=BLAU, bild=bild)
    kasten(ax, 14.7, 7.95, 6.6, 3.0, f"Schicht 3 · Motorausgabe ({s('s3')})",
           ["Änderungsgrenze a_max;  Grenzen f_max, f_min", "f = v_soll · N_s/(2π r)   →   f_L = f_R = f", "meldet v_aus = f·2πr/N_s und den Weg x"], farbe=BLAU, bild=bild)
    pfeil(ax, (7.3, 9.45), (7.7, 9.45)); wort(ax, 7.5, 9.75, "θ_ist, θ̇_ist", bild, ha="center", fontsize=8.8)
    pfeil(ax, (14.3, 9.45), (14.7, 9.45)); wort(ax, 14.5, 9.75, "v_soll", bild, ha="center", fontsize=8.8)
    ax.plot([18.0, 18.0], [10.95, 12.4], color=ORANGE, lw=1.4); pfeil(ax, (18.0, 12.4), (16.4, 12.4), "", farbe=ORANGE)
    wort(ax, 18.15, 11.6, "v_aus, x", bild, fontsize=8.8, color=ORANGE)
    ax.plot([5.6, 3.9], [12.4, 12.4], color=ORANGE, lw=1.4); pfeil(ax, (3.9, 12.4), (3.9, 10.95), "", farbe=ORANGE)
    wort(ax, 4.05, 11.6, "Nullpunkt", bild, fontsize=8.8, color=ORANGE)
    wort(ax, 0.75, 7.5, f"Abschaltung bei |θ_ist| > θ_ab;  Freigabe erst, wenn |θ_ist| < θ_frei und |θ̇| < ω_frei für t_frei gelten ({s('freigabe')})", bild, fontsize=8.3, color="#444")


def bild_struktur(name, titel, strecke_titel, strecke_zeilen, sensor_titel, sensor_zeilen, farbe_s=GRUEN, fuell_s="#eaf5ea",
                  titelzusatz="", unten_txt="", farbe_sensor=ROT, fuell_sensor="#fbeaea", pfeil_txt="θ, θ̇, θ̈, v̇", sensor_aus="a_lp, θ̇_lp, θ_lp", strecke_ein="Schrittimpulse f_L, f_R"):
    fig, ax = plt.subplots(figsize=(11, 7.9)); ax.set_xlim(0, 22); ax.set_ylim(0, 15.8); ax.axis("off")
    wort(ax, 11, 15.55, titel, name, ha="center", va="top", fontsize=12, fontweight="bold")
    regler_bloecke(ax, name, titelzusatz)
    kasten(ax, 0.4, 1.0, 7.4, 5.6, sensor_titel, sensor_zeilen, farbe=farbe_sensor, fuellung=fuell_sensor, bild=name)
    kasten(ax, 8.4, 1.0, 13.2, 5.6, strecke_titel, strecke_zeilen, farbe=farbe_s, fuellung=fuell_s, bild=name)
    pfeil(ax, (18.0, 7.3), (18.0, 6.6)); wort(ax, 18.15, 6.95, strecke_ein, name, fontsize=8.8, va="center")
    pfeil(ax, (8.4, 1.9), (7.8, 1.9)); wort(ax, 8.1, 2.15, pfeil_txt, name, ha="center", fontsize=8.8)
    pfeil(ax, (3.9, 6.6), (3.9, 7.3)); wort(ax, 4.05, 6.95, sensor_aus, name, fontsize=8.8, va="center")
    pfeil(ax, (21.95, 1.5), (21.6, 1.5), "", farbe=GRAU); wort(ax, 21.95, 1.2, "Störmoment M", name, fontsize=8.3, color=GRAU, ha="right", va="top")
    if unten_txt:
        wort(ax, 11, 0.55, unten_txt, name, ha="center", va="top", fontsize=8.6, color="#333")
    fig.savefig(B / f"{name}.png", dpi=170, bbox_inches="tight", pad_inches=0.12); plt.close(fig)


def bilder():
    bild_struktur("einf_struktur_real",
                  "Der Segway als Regelkreis: die reale Strecke, gemessen vom Sensor und gespeist vom abgetasteten System im ESP32",
                  f"Reale Strecke  —  Bewegungsgleichung {s('dgl')}, Zustandsmodell {s('zustand')}, Übertragungsfunktion {s('G_u')}",
                  ["J θ̈ = m g (l sinθ + s cosθ) − m v̇ (l cosθ − s sinθ) − d θ̇ + M",
                   "Antrieb:  v̇ = (v_soll − v)/τ_mot,   v = f · 2πr/N_s,   x = ∫v dt",
                   "linearisiert:  ẋ = A x + B u,   x = (θ, ω, v),   u = v_soll",
                   "G_u(s) = Θ(s)/V_soll(s) = −m l s / [ (1 + τ_mot s)(J s² + d s − m g l) ]",
                   "Pole ±1/T mit T = √(J/(m g l)), dazu −1/τ_mot;  Nullstelle s = 0",
                   f"Größen m, l, J, d, s: {s('zahlen')};   r, N_s, τ_mot: {s('antrieb')}"],
                  f"Sensor MPU6050 bei (w, u)\n({s('einbau')}, {s('sensor')})",
                  ["Beschleunigung am Sensor:", "a_s = v̇ + w θ̈ − u θ̇²", "Beschleunigungsmesser misst a_s + g·sinθ", "Kreisel misst θ̇ + b (Nullpunkt b)",
                   f"Tiefpass τ_lp, Abtastung mit T ({s('takt')})", "→ a_lp, θ̇_lp, θ_lp an Schicht 1"],
                  unten_txt="Alle Größen sind Variablen; ihre Werte und ihre Herkunft stehen in den Tabellen dieses Blattes und auf den genannten Seiten des Manuskripts.")
    bild_struktur("einf_struktur_simulation",
                  "Dieselbe Struktur als Simulation: segway_modell.py (Python) und segway_labor_modell.js (Labor im Browser)",
                  f"Simulationsstrecke ({s('simulation')})",
                  ["dieselbe Bewegungsgleichung, Glied für Glied, explizites Euler-Verfahren mit n_fein Rechenschritten je Takt T",
                   "Antrieb:  v̇ = (v_soll − v)/τ_mot,  |v̇| ≤ a_max;   Störmoment M(t), Schwerpunktversatz s, Anfangslage θ_0, ω_0 einstellbar",
                   f"geprüft gegen Runge-Kutta 4 derselben Gleichung und gegen die Abtastform e^{{AT}} ({s('abtast')})"],
                  f"Sensormodell ({s('sensorsim')})",
                  ["a_s = v̇ + w θ̈ − u θ̇²", "Rohwinkel θ − arctan(a_s/g)", "Tiefpass τ_lp auf a, θ̇, θ", "Rauschen σ_θ, σ_ω;  Nullpunkt b", "Abtastung mit T →", "Rohwinkel, Drehrate an Schicht 1"],
                  farbe_s=LILA, fuell_s="#efe9f6", farbe_sensor=LILA, fuell_sensor="#efe9f6",
                  titelzusatz=f"Klassen Winkelerfassung, Winkelregler, Motorausgabe (Firmware: Motoreinheit), Nullpunktkorrektur — Zeile für Zeile wie die Firmware ({s('firmware')})",
                  unten_txt="Firmware = Modell = Labor: dieselben Zeilen, dieselben Bezeichner — nachgewiesen über 3000 Takte (Firmware gegen Python) und gegen das Python-Modell (Labor), siehe Prüfprotokolle.")
    bild_struktur("einf_struktur_esp32",
                  "Dieselbe Struktur am Gerät: die Firmware segway_regelung.ino und die Peripherie des ESP32",
                  "Antriebsseite  —  Schrittmotortreiber und Motoren",
                  ["FastAccelStepper  →  2 × A3967 (Mikroschritt 1/8  →  N_s Schritte je Radumdrehung)",
                   "rechts: STEP GPIO 32, DIR GPIO 33, ENABLE GPIO 14",
                   "links:  STEP GPIO 25, DIR GPIO 26, ENABLE GPIO 27",
                   "Motoren SM-42BYG011-25 unmittelbar an den Rädern (Ø 2r)  →  die reale Strecke",
                   "Synchron-LED an GPIO 23: Zeitmarke für die Kamera (Hardwaretest)"],
                  "Sensorseite  —  MPU6050 über I²C",
                  ["SDA GPIO 21, SCL GPIO 22", "Takt 400 kHz, Adresse 0x68", "Register: a_x, a_y, a_z, ω (16 Bit)", "Tiefpass DLPF (τ_lp) im Sensor", "Abfrage in jedem Takt T →", "Rohwinkel, Drehrate an Schicht 1"],
                  titelzusatz="Regelaufgabe auf Kern 1 mit vTaskDelayUntil(T), Bedienung und Mitschnitt auf Kern 0",
                  unten_txt=f"Bedienung und Mitschnitt über WLAN — WebServer: /werte, /log, /rampe, /rampentest, /nullpunkt, /fahr, /frei, /stop; OTA-Name „segway“ ({s('inbetrieb')}).",
                  strecke_ein="Schrittimpulse f_L, f_R (STEP/DIR)")


def bild_hardware():
    name = "einf_hardware"
    fig, ax = plt.subplots(figsize=(11, 7.4)); ax.set_xlim(0, 22); ax.set_ylim(0, 14.8); ax.axis("off")
    wort(ax, 11, 14.55, "Die Hardwaremodule und ihre realen Schnittstellen", name, ha="center", va="top", fontsize=12, fontweight="bold")
    kasten(ax, 7.6, 9.4, 6.8, 4.2, "ESP32 WROOM-32 (DevKit)", ["I²C: GPIO 21 SDA, GPIO 22 SCL", "Treiber rechts: GPIO 32 / 33 / 14", "Treiber links: GPIO 25 / 26 / 27", "LED: GPIO 23 über 330 Ω", "WLAN 2,4 GHz: Weboberfläche, OTA", "zwei Kerne: Regelung / Bedienung"], farbe=BLAU, bild=name)
    kasten(ax, 0.4, 9.9, 6.2, 3.7, "MPU6050", ["3-Achs-Beschleunigung, 3-Achs-Kreisel", "I²C-Adresse 0x68 (AD0 = 0)", "3,3 V, GND, SDA, SCL", "Einbau: w über, u vor der Achse"], farbe=ROT, fuellung="#fbeaea", bild=name)
    pfeil(ax, (6.6, 11.75), (7.6, 11.75), "I²C", bild=name)
    kasten(ax, 15.4, 11.5, 6.2, 2.3, "Treiber rechts · A3967", ["STEP, DIR, ENABLE vom ESP32", "MS1/MS2: 1/8 Schritt;  Ausgang A+/A−/B+/B−"], farbe=GRUEN, fuellung="#eaf5ea", bild=name, ts=9.4, zs=8.4)
    kasten(ax, 15.4, 8.9, 6.2, 2.3, "Treiber links · A3967", ["STEP, DIR, ENABLE vom ESP32", "MS1/MS2: 1/8 Schritt;  Ausgang A+/A−/B+/B−"], farbe=GRUEN, fuellung="#eaf5ea", bild=name, ts=9.4, zs=8.4)
    pfeil(ax, (14.4, 12.65), (15.4, 12.65), "", bild=name); wort(ax, 14.9, 12.85, "STEP/DIR/EN", name, ha="center", va="bottom", fontsize=8.2)
    pfeil(ax, (14.4, 10.05), (15.4, 10.05), "", bild=name); wort(ax, 14.9, 10.25, "STEP/DIR/EN", name, ha="center", va="bottom", fontsize=8.2)
    kasten(ax, 15.4, 5.0, 6.2, 2.9, "Motor rechts · SM-42BYG011-25", ["bipolar, 1,8° Vollschritt (200/U)", "12 V, 0,33 A, 34 Ω, 46 mH, 0,23 Nm", "Rad Ø 2r direkt auf der Welle"], farbe=GRUEN, fuellung="#eaf5ea", bild=name, ts=9.0, zs=8.6)
    kasten(ax, 7.6, 5.0, 6.8, 2.9, "Motor links · SM-42BYG011-25", ["bipolar, 1,8° Vollschritt (200/U)", "12 V, 0,33 A, 34 Ω, 46 mH, 0,23 Nm", "Rad Ø 2r direkt auf der Welle"], farbe=GRUEN, fuellung="#eaf5ea", bild=name, ts=9.0, zs=8.6)
    pfeil(ax, (18.5, 8.9), (18.5, 7.9), "A/B-Wicklungen", lage="mitte", dx=1.6, bild=name)
    ax.plot([15.4, 14.9, 14.9], [10.05, 10.05, 8.6], color="#222", lw=1.4); pfeil(ax, (14.9, 8.6), (11.0, 7.9), "A/B-Wicklungen", lage="mitte", dx=-1.6, dy=0.3, bild=name)
    kasten(ax, 0.4, 5.0, 6.2, 4.3, "Akku", ["Versorgung: Treiber (V_mot) und ESP32", "Lage: oben im Bügel (Höhe H)", "Masse im Maßblatt; Spannung und", "Verteilung am Gerät nachzutragen"], farbe=ORANGE, fuellung="#fdf3e3", bild=name)
    pfeil(ax, (6.6, 7.2), (7.6, 7.2), "V_mot", farbe=ORANGE, bild=name); ax.plot([6.6, 7.1, 7.1], [8.6, 8.6, 9.4], color=ORANGE, lw=1.1, ls=":"); pfeil(ax, (7.1, 9.4), (7.6, 9.4), "", farbe=ORANGE)
    ax.plot([14.4, 15.4], [6.2, 6.2], color=ORANGE, lw=1.1, ls=":")
    kasten(ax, 0.4, 0.6, 21.2, 3.6, "Mechanik", ["Räder Ø 2r, Spurweite B;  Aufbau aus Grundplatte, Dachplatte und Bügel mit dem Akku;  Sensorpult an der Stelle (w, u)",
           "Schwerpunkt l über der Achse mit Querversatz s;  Trägheitsmoment J um die Radachse (Radpendel);  Masse m",
           f"Maße und Massen: Maßblatt MASSE_UND_GEWICHTE und {s('zahlen')}"], farbe=GRAU, fuellung="#f2f2f2", bild=name)
    fig.savefig(B / f"{name}.png", dpi=170, bbox_inches="tight", pad_inches=0.12); plt.close(fig)


def bild_hardwaretest(datei="einf_hardwaretest"):
    """Übersicht: Prüfstand, Kamera, Synchron-LED, Mitschnitt, Bildauswertung, Vergleich mit dem Modell, Nachziehen des Reglers."""
    name = datei
    fig, ax = plt.subplots(figsize=(11.5, 8.3)); ax.set_xlim(0, 23); ax.set_ylim(0, 16.6); ax.axis("off")
    wort(ax, 11, 16.35, f"Der Hardwaretest: Kamera, Synchron-LED, Bildauswertung und das Nachziehen des Reglers ({s('hwtest')})", name, ha="center", va="top", fontsize=12, fontweight="bold")
    kasten(ax, 0.4, 10.9, 6.8, 4.4, f"Prüfstand ({s('pruefstand')})", ["Fahrzeug an der Fangleine zwischen", "Führungsleisten, Fahrweg ±x_max", "Kamera seitlich in Achshöhe, fest", "Maßstab: Raddurchmesser 2r im Bild"], farbe=GRAU, fuellung="#f2f2f2", bild=name)
    kasten(ax, 7.6, 10.9, 6.8, 4.4, "Laptop-Kamera → Bildauswertung", ["Video der Seitenansicht, Bildrate f_cam", "Merkmalspunkte (AKAZE), Ähnlichkeits-", "transformation (RANSAC) gegen Bezugsbild", f"→ θ_cam(t) je Bild (wie Radpendel, {s('zahlen')})"], farbe=ROT, fuellung="#fbeaea", bild=name)
    kasten(ax, 14.8, 10.9, 6.8, 4.4, "ESP32: Mitschnitt und Zeitmarke", ["/log startet den Mitschnitt (f_log):", "t, θ_ist, θ̇_ist, f, Nullpunkt, led", "Synchron-LED (GPIO 23) blitzt dreimal:", "gleiche Zeitmarke in Video und Mitschnitt"], farbe=BLAU, bild=name)
    pfeil(ax, (7.2, 13.1), (7.6, 13.1), "Video", bild=name)
    kasten(ax, 7.6, 5.5, 6.8, 4.4, "Gemeinsame Zeitachse, Vergleich", ["LED-Blitz im Bild = Spalte led → Δt", "θ_cam(t) gegen θ_ist(t) (Kalman-Filter)", "Stoßantwort (Anstoßen, später /stoss):", "Eigenfrequenz f_K, Abklingzeit τ_K,", "Restzittern"], farbe=LILA, fuellung="#efe9f6", bild=name)
    pfeil(ax, (9.4, 10.9), (9.4, 9.9), "θ_cam(t)", lage="mitte", dx=-1.1, bild=name)
    ax.plot([16.0, 16.0, 12.6], [10.9, 10.4, 10.4], color="#222", lw=1.4); pfeil(ax, (12.6, 10.4), (12.6, 9.9), "", bild=name); wort(ax, 14.3, 10.5, "Mitschnitt (CSV)", name, ha="center", va="bottom", fontsize=8.4)
    kasten(ax, 0.4, 5.5, 6.8, 4.4, f"Entscheidung ({s('korrektur')})", [f"f_K, τ_K gegen das Modell ({s('kreis')})", "innerhalb der Schranken?", "ja → Modell belegt, Beiwerte bleiben", "nein → J/(m l), d, τ_mot aus der", "Stoßantwort nachführen, neu auslegen"], farbe=ORANGE, fuellung="#fdf3e3", bild=name)
    pfeil(ax, (7.6, 7.7), (7.2, 7.7), "", bild=name); wort(ax, 7.4, 7.9, "Kennwerte", name, ha="center", va="bottom", fontsize=8.4)
    kasten(ax, 14.8, 5.5, 6.8, 4.4, "Neueinstellung des Reglers", ["Auslegung in der Simulation (Labor:", "„Regler automatisch auslegen“, Suche", "über K, T_n, T_v mit Reserven)", "→ /param schreibt K, T_n, T_v, K_N, T_n,N", "→ Freigabe, Stoß, Vergleich"], farbe=GRUEN, fuellung="#eaf5ea", bild=name)
    ax.plot([3.8, 3.8, 18.2], [5.5, 4.95, 4.95], color="#222", lw=1.4); pfeil(ax, (18.2, 4.95), (18.2, 5.5), "", bild=name); wort(ax, 11.0, 5.1, "nein: nachgeführte Streckengrößen", name, ha="center", fontsize=8.8, bbox=dict(fc="white", ec="none", pad=0.8))
    ax.plot([21.6, 22.2, 22.2], [7.7, 7.7, 13.1], color="#222", lw=1.2, ls="--"); pfeil(ax, (22.2, 13.1), (21.6, 13.1), "", bild=name)
    wort(ax, 22.6, 10.4, "Schleife, bis Gerät und Modell dieselben Kennwerte liefern", name, rotation=90, ha="center", va="center", fontsize=8.3)
    kasten(ax, 0.4, 0.7, 22.2, 3.9, "Stand der Umsetzung (Laborplan, Stufen 2–5)",
           ["vorhanden: Synchron-LED und Spalte led in der Firmware; /log, /rampe, /rampentest; Bildauswertung als Skript (radpendel_auswertung.py);",
            "Auslegung durch Simulation in der Laborseite",
            "geplant: /param (Beiwerte im Flash) und /stoss in der Firmware (Stufe 2); Kamera in der Laborseite (getUserMedia) mit Blitzerkennung (Stufe 4);",
            "Nachführen der Strecke aus der Stoßantwort (Stufe 5)"],
           farbe=GRAU, fuellung="#f7f7f7", bild=name, zs=8.8)
    fig.savefig(B / f"{name}.png", dpi=170, bbox_inches="tight", pad_inches=0.12); plt.close(fig)


# ----------------------------------------------------------------------------- Tabellen
def d(x, n=2): return f"{x:.{n}f}".replace(".", ",")


def tabellen() -> str:
    T = P["T"]; grad = 180 / 3.141592653589793
    z = []
    z.append(f"""## Die Größen der Strecke (Werte: Messung 28.09.2026 und Konstruktion, {s('zahlen')})

| Symbol | Bedeutung | Wert | Herkunft |
|:--|:--|--:|:--|
| $m$ | Masse des Aufbaus | {d(P['m'],3)} kg | gewogen, {s('zahlen')} |
| $l$ | Schwerpunkthöhe über der Radachse | {d(P['l']*1e3,1)} mm | Konstruktion, {s('zahlen')} |
| $J$ | Trägheitsmoment um die Radachse | {d(P['J']*1e3,2)}·10⁻³ kg m² | Radpendel ($J/(ml)$) und $l$, {s('zahlen')} |
| $T=\\sqrt{{J/(mgl)}}$ | Kippzeitkonstante | {d(U['zustandsmodell']['T_kipp_s']*1e3,1)} ms | Radpendel-Video, {s('gleichgew')} |
| $d$ | Lagerreibung | {d(P['d'],3)} Nms | Abklingen des Radpendels (Spanne), {s('zahlen')} |
| $s$ | Querversatz des Schwerpunkts | ≈ 0,4 mm (Konstruktion) | Ursache des Nullpunktfehlers, {s('gleichgew')} |
| $\\tau_\\mathrm{{mot}}$ | Verzug des Antriebs | {d(P['tau_mot']*1e3,0)} ms | Annahme, Empfindlichkeit gerechnet, {s('zahlen')} |
| $r$ | Radradius | {d(P['r_rad']*1e3,0)} mm | gemessen; Firmware `RAD_DURCHMESSER`, {s('antrieb')} |
| $N_s$ | Schritte je Radumdrehung | {P['Ns']} | 200 Vollschritte × 8 Mikroschritte; Firmware `SCHRITTE_JE_UMDREHUNG`, {s('antrieb')} |
| $w$, $u$ | Sensorlage über / vor der Achse | {d(P['sensor_w']*1e3,0)} mm / {d(P['sensor_u']*1e3,0)} mm | gemessen, {s('einbau')} |
| $\\tau_\\mathrm{{lp}}$ | Tiefpass des Sensors (42 Hz) | {d(P['t_dlpf']*1e3,1)} ms | Datenblatt MPU6050, {s('takt')} |
| Pole von $G_u(s)$ | Kippen, Rückstellung, Antrieb | {d(U['uebertragungsfunktion']['G_u']['pol_instabil'],2)}, {d(U['uebertragungsfunktion']['G_u']['pol_stabil'],2)}, {d(-1/P['tau_mot'],0)} s⁻¹ | {s('G_u')} |
""")
    z.append(f"""## Die Größen des abgetasteten Systems (Werte aus dem Quelltext der Firmware gelesen, {s('firmware')})

| Symbol | Bedeutung | Wert | Firmware | Modell / Labor | Herkunft |
|:--|:--|--:|:--|:--|:--|
| $T$ | Regeltakt | {d(T*1e3,0)} ms ({d(1/T,0)} Hz) | `TAKT_MS`, `DT_SOLL` | `f_gitter` | {s('takt')} |
| $K$ | Verstärkung des Winkelreglers | {d(P['K'],4)} m/s je rad | `REGLER_K` | `N_K` | {s('beiwerte')} |
| $T_n$ | Nachstellzeit | {d(P['Tn']*1e3,2)} ms | `REGLER_TN` | `N_TN` | {s('beiwerte')} |
| $T_v$ | Vorhaltzeit | {d(P['Tv']*1e3,2)} ms | `REGLER_TV` | `N_TV` | {s('beiwerte')} |
| $k_i = K/T_n$ | Aufrichtbedingung $k_i > g$ | {d(U['kreis']['k_i'],2)} m/s² je rad | — | — | {s('kreis')} |
| $K_N$ | Verstärkung der Nullpunktkorrektur | {d(P['K_N'],5)} rad je m/s | `NULL_K` | `NK_K` | {s('beiwerte')} |
| $T_{{n,N}}$ | Nachstellzeit der Nullpunktkorrektur | {d(P['Tn_N'],3)} s | `NULL_TN` | `NK_TN` | {s('beiwerte')} |
| $\\theta_{{N,\\mathrm{{max}}}}$ | Anschlag des Nullpunkts | {d(FW['GRENZE']*grad,1)}° ({d(FW['GRENZE'],3)} rad) | `GRENZE` | `NK_MAX` | {s('s4')} |
| $Q_\\theta$, $Q_b$, $R$ | Kalman: Rauschmaße Winkel, Nullpunkt, Messung | {FW['Q_WINKEL_WERT']}, {FW['Q_NULL_WERT']}, {d(FW['R_MESS_WERT'],2)} | `Q_WINKEL_WERT`, `Q_NULL_WERT`, `R_MESS_WERT` | `Q_ANGLE`, `Q_BIAS`, `R_MEASURE` | {s('kalman')}, {s('beiwerte')} |
| $a_\\mathrm{{max}}$ | Änderungsgrenze (Rampe) | {d(FW['A_MAX_VORGABE'],2)} m/s² | `A_MAX_VORGABE` | `a_max` | {s('antrieb')} |
| $f_\\mathrm{{max}}$, $f_\\mathrm{{min}}$ | Frequenzgrenze, Totzone | {d(FW['MAX_HZ'],0)} Hz, {d(FW['MIN_HZ'],0)} Hz | `MAX_HZ`, `MIN_HZ` | `MAX_SPEED`, `MIN_SPEED` | {s('antrieb')} |
| $\\theta_\\mathrm{{ab}}$ | Sicherheitsabschaltung | {d(FW['KIPP_GRENZE'],0)}° | `KIPP_GRENZE` | `KIPP_GRENZE` | {s('freigabe')} |
| $\\theta_\\mathrm{{frei}}$, $\\omega_\\mathrm{{frei}}$ | Wiederfreigabe (eine halbe Sekunde lang) | {d(FW['FREI_WINKEL'],0)}°, {d(FW['FREI_RATE'],0)} °/s | `FREI_WINKEL`, `FREI_RATE` | — | {s('freigabe')} |
| $f_\\mathrm{{log}}$ | Mitschnittrate | {d(FW['LOG_HZ'],0)} Hz | `LOG_HZ` | — | {s('inbetrieb')} |
""")
    z.append(f"""## Die Signale zwischen den Blöcken

| Signal | Richtung | Einheit | In der Firmware | Im Modell / Labor |
|:--|:--|:--|:--|:--|
| $a_x, a_y, a_z$, $\\omega$ | MPU6050 → Schicht 1 (I²C, jeden Takt) | m/s², °/s | `mpuLesen`, Rohwinkel `atan2` | Sensormodell: `roh`, `drehrate` |
| $\\theta_\\mathrm{{ist}}$, $\\dot\\theta_\\mathrm{{ist}}$ | Schicht 1 → Schicht 2 | rad, rad/s | Klasse `Winkelerfassung` | Klasse `Winkelerfassung` |
| $v_\\mathrm{{soll}}$ | Schicht 2 → Schicht 3 | m/s | Klasse `Winkelregler` | Klasse `Winkelregler` |
| $f$ (Schrittfrequenz), $v_\\mathrm{{aus}}$, $x$ | Schicht 3 → Treiber; Schicht 3 → Schicht 4 | Hz, m/s, m | Klasse `Motoreinheit`, FastAccelStepper | Klasse `Motorausgabe` |
| Nullpunkt | Schicht 4 → Schicht 1 | rad | Klasse `Nullpunktkorrektur` | Klasse `Nullpunktkorrektur` |
| $M$, $s$ | Störmoment, Schwerpunktversatz (nur im Modell einstellbar) | Nm, m | — | `stoerung`, `s_versatz` |
""")
    return "\n".join(z)


# ----------------------------------------------------------------------------- Dokument
def main():
    global SEITEN, SEITENVERWEIS
    B.mkdir(exist_ok=True)
    if "--manuskriptbild" in sys.argv:
        SEITENVERWEIS = False
        bild_hardwaretest("hardwaretest_ablauf")
        print("Bilder/hardwaretest_ablauf.png (ohne Seitenverweise, für das Manuskript)")
        return
    SEITEN = seiten_des_manuskripts()
    S.update({k: seite(v) for k, v in HERKUNFT.items()})
    bilder(); bild_hardware(); bild_hardwaretest()
    for v in VERKLEINERT: print("verkleinert:", v)
    text = f"""---
title: "Der Segway im Bild — Einführung"
subtitle: "Vom realen Gerät zum Modell, zur Simulation, zur Firmware und zurück"
author: "{NAMENSNENNUNG}"
date: "Einführung zu Fassung {F} des Manuskripts · {DATUM}"
lang: de
header-includes:
  - \\usepackage{{pdflscape}}
---

Dieses Blatt geht dem Manuskript *Segway — vom vorhandenen Code zur ausgelegten Regelung* (Fassung {F}, {DATUM}) voran.
Es zeigt in sieben Bildern, wie das Gerät, sein Modell, die Simulation, die Firmware und der Hardwaretest zusammenhängen. In den Bildern
stehen alle Größen als Variablen; die Tabellen nennen ihre Werte und die Seite des Manuskripts, auf der sie hergeleitet
oder gemessen sind. Was in den Bildern steht, ist die Struktur der Firmware `segway_regelung.ino`, des Python-Modells
`segway_modell.py` und des Labors `segway_labor_modell.js` — nachgewiesen im Prüfprotokoll `PRUEFPROTOKOLL_Einfuehrung.pdf`.

# 1 · Das Gerät

![Der Segway: zwei Schrittmotoren treiben die Räder unmittelbar, der Lagesensor sitzt vorn über der Achse, oben der Akku, im Aufbau der ESP32 und die Treiber.](../Bilder/foto_fahrzeug_front.jpg)

# 2 · Die reale Strecke und das abgetastete System

Die Strecke ist das Fahrzeug selbst: sein Aufbau kippt um die Radachse, angetrieben über die Geschwindigkeit der Räder.
Im Streckenblock steht die Bewegungsgleichung, aus ihr die Übertragungsfunktion; der Sensor misst, das abgetastete System
im ESP32 rechnet in vier Schichten und speist die Strecke mit der Schrittfrequenz.

```{{=latex}}
\\begin{{landscape}}
```

![Reale Strecke mit Bewegungsgleichung und Übertragungsfunktion, gemessen vom MPU6050, gespeist vom abgetasteten System im ESP32. Nur Variablen; Werte in den Tabellen.](../Bilder/einf_struktur_real.png){{width=100%}}

```{{=latex}}
\\end{{landscape}}
```

# 3 · Dieselbe Struktur als Simulation

An die Stelle der realen Strecke tritt das Rechenmodell; das abgetastete System bleibt Zeile für Zeile dasselbe.

```{{=latex}}
\\begin{{landscape}}
```

![Struktur der Simulation: Rechenmodell der Strecke und Sensormodell, die vier Schichten als Klassen wie in der Firmware.](../Bilder/einf_struktur_simulation.png){{width=100%}}

```{{=latex}}
\\end{{landscape}}
```

# 4 · Dieselbe Struktur am Gerät: die Peripherie des ESP32

```{{=latex}}
\\begin{{landscape}}
```

![Struktur am Gerät: die Firmware im ESP32, der Sensor über I²C, die Treiber über STEP/DIR/ENABLE, die Motoren an den Rädern.](../Bilder/einf_struktur_esp32.png){{width=100%}}

```{{=latex}}
\\end{{landscape}}
```

# 5 · Die Hardwaremodule

```{{=latex}}
\\begin{{landscape}}
```

![Die Module und ihre realen Schnittstellen.](../Bilder/einf_hardware.png){{width=100%}}

```{{=latex}}
\\end{{landscape}}
```

# 6 · Der Hardwaretest und das Nachziehen des Reglers

Was das Modell vorhersagt, wird am Gerät gemessen: die Laptop-Kamera filmt die Seitenansicht, die Synchron-LED des ESP32
setzt dieselbe Zeitmarke ins Video und in den Mitschnitt, die Bildauswertung liefert den Winkel unabhängig vom Sensor, und
die Stoßantwort gibt Eigenfrequenz und Abklingzeit des realen Kreises. Stimmen sie mit dem Modell, ist es belegt; wenn nicht,
werden erst die Streckengrößen nachgeführt und dann die Beiwerte in der Simulation neu ausgelegt und in den ESP32 geschrieben.

```{{=latex}}
\\begin{{landscape}}
```

![Der Hardwaretest als Schleife: Prüfstand, Kamera und Mitschnitt, gemeinsame Zeitachse über die LED, Vergleich mit dem Modell, Neueinstellung.](../Bilder/einf_hardwaretest.png){{width=100%}}

```{{=latex}}
\\end{{landscape}}
```

# 7 · Das Gerät

![Der Segway von schräg vorn.](../Bilder/foto_fahrzeug_schraeg.jpg)

\\newpage

# Tabellen: die Größen, ihre Werte und ihre Herkunft

{tabellen()}

Die Seitenzahlen beziehen sich auf `MANUSKRIPT_Segway_Gesamt_F{F}.pdf`; sie werden beim Bau aus dem gesetzten PDF gelesen.
"""
    (H / "EINFUEHRUNG_Segway.md").write_text(text, encoding="utf-8")
    (H / "einfuehrung_seiten.json").write_text(json.dumps(dict(fassung=F, datum=DATUM, pdf=PDF.name, seiten=S, ueberschriften=HERKUNFT, bildtexte=BILDTEXTE),
                                                          indent=1, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["pandoc", "EINFUEHRUNG_Segway.md", "-o", "EINFUEHRUNG_Segway.pdf", "--pdf-engine=xelatex", "-V", "geometry:margin=2.2cm",
                        "-V", "mainfont=DejaVu Serif", "-V", "monofont=DejaVu Sans Mono", "-V", "fontsize=10pt"], cwd=H, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    n = re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(H / "EINFUEHRUNG_Segway.pdf")], capture_output=True, text=True).stdout).group(1)
    print(f"EINFUEHRUNG_Segway.pdf: {n} Seiten · zu Fassung {F} · Seitenverweise: " + ", ".join(f"{k} {v}" for k, v in S.items()))


if __name__ == "__main__":
    main()
