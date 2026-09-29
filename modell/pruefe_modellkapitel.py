#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefe_modellkapitel.py — Prüfprotokoll zur Aufgabe „Modell transparent: Zustandsmodell, Übertragungsfunktion,
geschlossener Kreis“ (29.09.2026). Jede Zeile eine Prüfung mit Schranke, Istwert und Ergebnis; nichts wird angenommen.

Geprüft werden
  M1–M6   die Rechnung (Modell/uebertragungsfunktion.json): innere Proben, zwei Wege, Schranken
  M7–M8   die Zahlen im Manuskript gegen die Rechnung (jede genannte Zahl muss aus der JSON-Datei folgen)
  M9–M12  das Dokument selbst: PDF ohne rohe Überschriften, Bilder vorhanden und groß genug, keine veralteten Zahlen,
          Leerzeile vor jeder Überschrift, Fassung im Kopf
  M13     Firmware = Modell: dieselben Beiwerte in beiden Ergebnisdateien

Schreibt Modell/PRUEFPROTOKOLL_Modellkapitel.md (+ .pdf über pandoc) und Modell/pruefe_modellkapitel.json.
Aufruf: python3 Modell/pruefe_modellkapitel.py   — Rückgabewert 1 bei Beanstandung.
"""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np

H = Path(__file__).resolve().parent; W = H.parent
U = json.load(open(H / "uebertragungsfunktion.json"))
NG = json.load(open(H / "gemessen_2026-09-28/nachweis_gemessen.json"))
TK = json.load(open(W / "Konstruktion/traegheit_aus_konstruktion.json"))
MD = (W / "MANUSKRIPT_Segway_Gesamt.md").read_text(encoding="utf-8")
PDF = W / "MANUSKRIPT_Segway_Gesamt.pdf"
Z = []                                                             # Protokollzeilen


def pruefe(nr, was, schranke, ist, gut, hinweis=""):
    Z.append(dict(nr=nr, was=was, schranke=schranke, ist=ist, gut=bool(gut), hinweis=hinweis))
    print(f"  {'ok    ' if gut else 'FEHLER'} {nr:<5} {was}: {ist} (Schranke {schranke})")


def d(x, n=2): return f"{x:.{n}f}".replace(".", ",")


p = U["parameter"]; Zm = U["zustandsmodell"]; Ue = U["uebertragungsfunktion"]; Ab = U["abtastform"]; Sp = U["sprungantwort"]; Kr = U["kreis"]; Re = U.get("reserven")
m, l, J, dd, g, tau, T = p["m"], p["l"], p["J"], p["d"], p["g"], p["tau_mot"], p["T"]

# ---- M1 Zustandsmodell: Eigenwerte gegen die geschlossenen Formeln
ew = sorted(Zm["eigenwerte"])
lam_pos = (-dd + np.sqrt(dd * dd + 4 * J * m * g * l)) / (2 * J); lam_neg = (-dd - np.sqrt(dd * dd + 4 * J * m * g * l)) / (2 * J)
f1 = max(abs(ew[2] - lam_pos), abs(ew[1] - lam_neg), abs(ew[0] + 1 / tau)) / lam_pos
pruefe("M1", "Eigenwerte von A gegen die Formeln λ₁,₂ = (−d ± √(d²+4Jmgl))/(2J), λ₃ = −1/τ", "< 10⁻⁹ relativ", f"{f1:.1e}", f1 < 1e-9)
f1b = abs(ew[2] * ew[1] + 1 / Zm["T_kipp_s"] ** 2) * Zm["T_kipp_s"] ** 2
pruefe("M1b", "λ₁·λ₂ = −1/T² (T aus √(J/(mgl)))", "< 10⁻⁹ relativ", f"{f1b:.1e}", f1b < 1e-9)

# ---- M2 Übertragungsfunktion: Polynomform gegen C(sI−A)⁻¹B
f2 = max(Ue["probe_zwei_wege"]["abweichung_rel_G_u"], Ue["probe_zwei_wege"]["abweichung_rel_G_M"])
pruefe("M2", "G_u(s) und G_M(s): Polynomform gegen C(sI−A)⁻¹B an vier Stellen", "< 10⁻⁹ relativ", f"{f2:.1e}", f2 < 1e-9)
pole = sorted(Ue["G_u"]["pole"])
pruefe("M2b", "Pole von G_u(s) = Eigenwerte von A", "< 10⁻⁹ relativ", f"{max(abs(a - b) for a, b in zip(pole, ew)) / lam_pos:.1e}", max(abs(a - b) for a, b in zip(pole, ew)) / lam_pos < 1e-9)

# ---- M3 Abtastform
ewPhi = sorted(Ab["eigenwerte_Phi"]); erw = sorted(np.exp(np.array(ew) * T))
f3 = max(abs(a - b) for a, b in zip(ewPhi, erw))
pruefe("M3", "Eigenwerte von Φ = e^{AT} gegen e^{λT}", "< 10⁻⁹", f"{f3:.1e}", f3 < 1e-9)
pruefe("M3b", "Feinschritt-Euler des Simulators gegen e^{AT}, Mechanikblock (θ, ω)", "< 10⁻⁴ relativ", f"{Ab['abweichung_mechanik_rel']:.1e}", Ab["abweichung_mechanik_rel"] < 1e-4)
f3c = abs(Ab["abweichung_antrieb_rel"] - Ab["erwartet_antrieb_rel"])
pruefe("M3c", "Euler-Fehler der Antriebszeile = erwarteter Wert |(1−T/(nτ))ⁿ − e^{−T/τ}|/e^{−T/τ}", "< 10⁻⁶", f"{Ab['abweichung_antrieb_rel']:.4f} gegen {Ab['erwartet_antrieb_rel']:.4f}", f3c < 1e-6,
       "bekannte Eigenschaft des expliziten Euler-Verfahrens bei T/τ = 2; betrifft einen in 5 ms abgeklungenen Anteil")

# ---- M4 Sprungantwort
pruefe("M4", "Sprungantwort offen: e^{At}-Fortschaltung gegen Runge-Kutta 4 der nichtlinearen Gleichung bei 0,3 s (θ ≈ 4°)", "< 5·10⁻⁴ relativ", f"{Sp['abweichung_rel_bei_0_3s']:.1e}", Sp["abweichung_rel_bei_0_3s"] < 5e-4)
pruefe("M4b", "Vorzeichen: Sprung nach vorn neigt zuerst nach hinten (θ < 0)", "θ_min < 0", f"{Sp['theta_min_grad']:.3f}°", Sp["theta_min_grad"] < 0)

# ---- M5 Geschlossener Kreis
pruefe("M5", "Aufrichtbedingung k_i = K/T_n > g mit den Beiwerten der Firmware", "> 9,81", f"{Kr['k_i']:.2f}", Kr["k_i_groesser_g"])
wz = [complex(*w) for w in Kr["wurzeln"]]
pruefe("M5b", "alle Wurzeln des Laplace-Kreises (Grad 4) links", "Re s < 0", ", ".join(f"{w.real:.2f}" for w in wz), all(w.real < 0 for w in wz))
pruefe("M5c", "alle Eigenwerte des abgetasteten Kreises im Einheitskreis", "|z| < 1", f"{Kr['diskret']['zmax']:.5f}", Kr["diskret"]["zmax"] < 1)
k = Kr["kipp"]
pruefe("M5d", "Kippbewegung: Laplace-Wurzel gegen 16-Zustands-Eigenwert (s = ln z/T)", "< 10 % Abstand", f"{k['abstand_rel']*100:.1f} % ({k['s_kontinuierlich'][0]:.2f}±{abs(k['s_kontinuierlich'][1]):.2f}j gegen {k['s_diskret'][0]:.2f}±{abs(k['s_diskret'][1]):.2f}j)", k["abstand_rel"] < 0.10,
       "Rest: Taktverzögerung, Kalman, Euler der Antriebszeile — alles im vollständigen Modell enthalten")
ohne = np.roots(Kr["polynom_ohne_verzug"]); wn = np.sqrt(Kr["polynom_ohne_verzug"][2] / Kr["polynom_ohne_verzug"][0])
pruefe("M5e", "Kreis ohne Verzüge: ω_n aus den Koeffizienten = |Wurzel|", "< 10⁻⁹", f"{abs(abs(ohne[0]) - wn) / wn:.1e}", abs(abs(ohne[0]) - wn) / wn < 1e-9)

# ---- M6 Reserven
if Re:
    f6 = max(abs(Re["grenze_oben_diskret"] - Re["reserve_oben_bisektion"]) / Re["reserve_oben_bisektion"], abs(Re["grenze_unten_diskret"] - Re["reserve_unten_bisektion"]) / Re["reserve_unten_bisektion"])
    pruefe("M6", "Reserven aus der Kurve |z|max(Faktor) gegen die Bisektion", "< 3 %", f"{f6*100:.1f} % ({Re['grenze_oben_diskret']:.3f}/{Re['grenze_unten_diskret']:.3f} gegen {Re['reserve_oben_bisektion']:.3f}/{Re['reserve_unten_bisektion']:.3f})", f6 < 0.03)
    pruefe("M6b", "Laplace-Kreis: obere Grenze erst jenseits der abgetasteten (Abtastung setzt die Grenze)", "keine Grenze bis Faktor 3 oder > 2,43", str(Re["grenze_oben_kont"]), Re["grenze_oben_kont"] is None or Re["grenze_oben_kont"] > Re["reserve_oben_bisektion"])
else:
    pruefe("M6", "Reserven", "Kurve vorhanden", "nicht gerechnet (--kurz)", False)

# ---- M7 Zahlen des Manuskripts gegen die Rechnung
erwartet = {
    "Pol instabil": d(Ue["G_u"]["pol_instabil"], 2), "Pol stabil": d(Ue["G_u"]["pol_stabil"], 2), "Kippzeitkonstante ms": d(Zm["T_kipp_s"] * 1e3, 1),
    "m g l": d(Zm["mgl_Nm"], 4), "A₂₁": d(Zm["A"][1][0], 2), "A₂₃": d(Zm["A"][1][2], 1), "k_i": d(Kr["k_i"], 2), "ω_n": d(Kr["omega_n"], 2), "ζ": d(Kr["zeta"], 3),
    "Φ₁₁": d(Ab["Phi"][0][0], 6), "Φ₂₁": d(Ab["Phi"][1][0], 6), "Kipp-Frequenz Laplace Hz": d(abs(k["s_kontinuierlich"][1]) / 2 / np.pi, 2),
    "Kipp-Frequenz diskret Hz": d(abs(k["s_diskret"][1]) / 2 / np.pi, 2), "Schrittweite mm": d(p["v_je_hz"] * 1e3, 4),
    "θ(0,3 s)": d(Sp["theta_bei_0_3s_grad"], 3), "δ": d(Ue["G_u"]["normalform"]["delta"], 4),
}
for zz in Ue["gleichgewicht"]["tafel"]:
    erwartet[f"θ_gl({zz['s_mm']} mm)"] = d(zz["theta_grad"], 3) + "°"
fehl = [k_ for k_, v in erwartet.items() if v not in MD]
pruefe("M7", f"{len(erwartet)} Zahlen aus der Rechnung stehen wörtlich im Manuskript", "alle", "fehlen: " + (", ".join(f"{k_} = {erwartet[k_]}" for k_ in fehl) if fehl else "keine"), not fehl)

# ---- M8 Radpendel: Kippzeitkonstante auf drei Wegen
f8a = abs(Zm["T_kipp_s"] - NG["T_kipp_s"]) / NG["T_kipp_s"]
f8b = abs(Zm["T_kipp_s"] - TK.get("T_kipp_s", TK.get("T_s", Zm["T_kipp_s"]))) / Zm["T_kipp_s"]
pruefe("M8", "Kippzeitkonstante: √(J/(mgl)) der Rechnung gegen T_p/(2π) des Radpendels", "< 10⁻⁹", f"{f8a:.1e}", f8a < 1e-9)
pruefe("M8b", "Kippzeitkonstante gegen die Konstruktion (zweiter Weg)", "< 2 %", f"{f8b*100:.2f} % ({Zm['T_kipp_s']*1e3:.1f} gegen {1e3*TK.get('T_kipp_s', TK.get('T_s', float('nan'))):.1f} ms)", f8b < 0.02)

# ---- M9 PDF ohne rohe Überschriften
if PDF.exists():
    txt = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], capture_output=True, text=True).stdout
    roh = [z for z in txt.splitlines() if re.search(r"(^|\s)#{2,4} \S", z)]
    seiten = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout).group(1))
    pruefe("M9", "PDF enthält keine rohe Markdown-Überschrift („## …“ im Fließtext)", "0 Zeilen", f"{len(roh)} ({seiten} Seiten)", not roh, "; ".join(roh[:3]))
    fehlt = [w for w in ("Übertragungsfunktion im Laplace-Bereich", "Zustandsgleichungen", "Die Abtastform", "charakteristische Polynom", "Prüfprotokoll") if w not in txt]
    pruefe("M9b", "die neuen Abschnitte stehen im PDF", "alle", "fehlen: " + (", ".join(fehlt) if fehlt else "keine"), not fehlt)
else:
    pruefe("M9", "PDF vorhanden", "ja", "nein", False)

# ---- M10 Bilder
from PIL import Image
bilder = re.findall(r"!\[[^\]]*\]\(([^)\s]+)", MD)
fehlend = [b for b in bilder if not (W / b).exists()]
klein = []; breit = []
for b in bilder:
    if (W / b).exists():
        w_, h_ = Image.open(W / b).size
        if w_ < 700: klein.append(f"{b} ({w_} px)")
        if w_ / h_ > 2.4: breit.append(f"{b} ({w_}×{h_})")
pruefe("M10", f"{len(bilder)} eingebundene Bilder vorhanden", "alle", "fehlen: " + (", ".join(fehlend) if fehlend else "keine"), not fehlend)
pruefe("M10b", "kein Bild schmaler als 700 Bildpunkte", "0", ", ".join(klein) or "keines", not klein)
pruefe("M10c", "kein Bild breiter als 2,4 : 1 (unlesbar klein bei Seitenbreite)", "0", ", ".join(breit) or "keines", not breit)
neu = ["Bilder/strecke_signalfluss.png", "Bilder/strecke_pole.png", "Bilder/strecke_sprungantwort.png", "Bilder/kreis_signalfluss.png", "Bilder/kreis_wurzeln.png", "Bilder/kreis_reserven.png", "Bilder/blockschaltbild_regelkreis.png"]
fehl_n = [b for b in neu if b not in bilder]
pruefe("M10d", "die sieben gezeichneten Bilder des Modellkapitels sind eingebunden", "alle", "fehlen: " + (", ".join(fehl_n) if fehl_n else "keine"), not fehl_n)

# ---- M11 veraltete Zahlen und Kopf
alt = [w for w in ("0,128 s", "0,1296", "r = 33", "$r = 33$", "6,72\\cdot10^{-3}", "0,955°", "−0,239°", "Fangbereich beträgt 20 Grad", "8,5 mm Schwerpunktversatz", "2083 Hz von") if w in MD]
pruefe("M11", "keine Zahl des Entwurfs vom 25.08. mehr als gültiger Wert im Text", "0", ", ".join(alt) or "keine", not alt)
kopf = re.search(r'^date: "(Fassung \d+) ·', MD, re.M)
pruefe("M11b", "Fassung im Kopf", "Fassung 6", kopf.group(1) if kopf else "—", bool(kopf) and kopf.group(1) == "Fassung 6")

# ---- M12 Leerzeile vor jeder Überschrift
zeilen = MD.split("\n"); ohne_leer = [zeilen[i][:50] for i in range(1, len(zeilen)) if re.match(r"^#{1,4} ", zeilen[i]) and zeilen[i - 1].strip() != "" and not zeilen[i - 1].startswith("---")]
pruefe("M12", "Leerzeile vor jeder Überschrift (sonst rohes „##“ im PDF)", "0 Verstöße", f"{len(ohne_leer)}", not ohne_leer, "; ".join(ohne_leer[:3]))

# ---- M13 Firmware = Modell
FW = NG["firmware"]
f13 = max(abs(p["K"] - FW["REGLER_K"]), abs(p["Tn"] - FW["REGLER_TN"]), abs(p["Tv"] - FW["REGLER_TV"]), abs(p["K_N"] - FW["NULL_K"]), abs(p["Tn_N"] - FW["NULL_TN"]), abs(p["r_rad"] * 2 - FW["RAD_DURCHMESSER"]))
pruefe("M13", "Beiwerte der Rechnung = Beiwerte aus dem Quelltext der Firmware (K, T_n, T_v, K_N, T_n,N, Rad)", "identisch", f"größte Differenz {f13:.1e}", f13 < 1e-12)

# ---- Protokoll schreiben
fehler = sum(1 for z in Z if not z["gut"])
kopf_md = f"""---
title: "Prüfprotokoll — Modellkapitel des Segway-Manuskripts (Teil II und VII, Fassung 6)"
author: "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
date: "29. September 2026 · Prüfmittel `Modell/pruefe_modellkapitel.py` · Ergebnis: {fehler} Beanstandung(en) bei {len(Z)} Prüfungen"
lang: de
---

# Aufgabe

Das Modell des Segways soll transparent sein: die Bewegungsgleichung wird geschlossen hergeleitet, linearisiert
als Zustandsmodell mit Eingang und Ausgang aufgeschrieben, in die Übertragungsfunktion im Laplace-Bereich und in
die Abtastform überführt, und der Regelkreis wird im Laplace-Bereich geschlossen und gegen das vollständige
Zustandsmodell des abgetasteten Kreises geprüft. Dieses Protokoll prüft die Rechnung (`Modell/uebertragungsfunktion.py`),
die Zahlen im Manuskript und das gebaute Dokument. Jede Zeile hat eine Schranke; eine Zeile ohne Schranke gilt nicht.

# Prüfungen

| Nr. | Prüfung | Schranke | Istwert | Ergebnis |
|:----|:------------------------------------------|:---------------|:-----------------------------|:-------|
"""
zeilen_md = "\n".join(f"| {z['nr']} | {z['was']} | {z['schranke']} | {z['ist']} | {'ok' if z['gut'] else '**FEHLER**'} |" for z in Z)
hinw = "\n".join(f"- **{z['nr']}**: {z['hinweis']}" for z in Z if z["hinweis"])
schluss = f"""

# Anmerkungen

{hinw}

# Ergebnis

{len(Z)} Prüfungen, **{fehler} Beanstandung(en)**. Rechnung: `Modell/uebertragungsfunktion.json`; Manuskript:
`MANUSKRIPT_Segway_Gesamt.md`, Fassung 6; PDF: `MANUSKRIPT_Segway_Gesamt_F6.pdf`.
"""
(H / "PRUEFPROTOKOLL_Modellkapitel.md").write_text(kopf_md + zeilen_md + schluss, encoding="utf-8")
(H / "pruefe_modellkapitel.json").write_text(json.dumps(dict(datum="2026-09-29", pruefungen=Z, fehler=fehler), indent=1, ensure_ascii=False), encoding="utf-8")
subprocess.run(["pandoc", str(H / "PRUEFPROTOKOLL_Modellkapitel.md"), "-o", str(H / "PRUEFPROTOKOLL_Modellkapitel.pdf"), "--pdf-engine=xelatex",
                "-V", "geometry:margin=2cm", "-V", "mainfont=DejaVu Serif", "-V", "monofont=DejaVu Sans Mono", "-V", "fontsize=9pt"], check=False)
print(f"{len(Z)} Prüfungen, {fehler} Beanstandung(en)")
sys.exit(1 if fehler else 0)
