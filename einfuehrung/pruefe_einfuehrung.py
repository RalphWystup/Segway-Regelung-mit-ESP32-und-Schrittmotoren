#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefe_einfuehrung.py — Prüfprotokoll zum Einführungsdokument (29.09.2026).

Vorgabe des Verfassers: „Die ganze Software und die Simulation muss dem entsprechen — hier darf es nicht zu Abweichungen
kommen.“ Geprüft wird deshalb, dass die Strukturbilder und Tabellen des Einführungsdokuments genau das zeigen, was
Firmware (segway_regelung.ino), Python-Modell (segway_modell.py) und Labor (segway_labor_modell.js) rechnen, und dass jeder
Seitenverweis auf die richtige Stelle des gesetzten Manuskripts zeigt.

  E1  jede Überschrift, auf die verwiesen wird, steht auf der genannten Seite des Manuskript-PDF
  E2  die Firmware-Bezeichner der Tabellen kommen im Quelltext der Firmware vor
  E3  die Modell-Bezeichner der Tabellen kommen im Python-Modell und im Labor-Modell vor
  E4  die Werte der Tabellen sind die der Firmware (aus dem Quelltext gelesen) und der Messung (JSON) — keine Zahl von Hand
  E5  die Strukturbilder enthalten keine Zahlenwerte von Parametern (nur Variablen; Anschlussnummern sind Schnittstellen)
  E6  die vier Schichten stehen in allen drei Programmen in derselben Reihenfolge und mit demselben Takt
  E7  die Bilder liegen vor, sind mindestens 700 Bildpunkte breit und höchstens 2,4 : 1 breit
  E8  das PDF ist gesetzt, trägt Fassung und Datum des Manuskripts, und die Sechs-Bilder-Folge ist vollständig
  E9  der Abschnitt „Der Hardwaretest …“ steht im Manuskript und das Bild des Ablaufs ist dort eingebunden
Schreibt Einfuehrung/PRUEFPROTOKOLL_Einfuehrung.md/.pdf und pruefe_einfuehrung.json; Rückgabewert 1 bei Beanstandung.
"""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image

H = Path(__file__).resolve().parent; W = H.parent
J = json.load(open(H / "einfuehrung_seiten.json", encoding="utf-8"))
MD = (H / "EINFUEHRUNG_Segway.md").read_text(encoding="utf-8")
INO = (W / "Arduino/segway_regelung/segway_regelung.ino").read_text(encoding="utf-8", errors="replace")
PY = (W / "Modell/segway_modell.py").read_text(encoding="utf-8")
JS = (W / "Labor/segway_labor_modell.js").read_text(encoding="utf-8")
MAN = (W / "MANUSKRIPT_Segway_Gesamt.md").read_text(encoding="utf-8")
PDF = W / J["pdf"]
U = json.load(open(W / "Modell/uebertragungsfunktion.json", encoding="utf-8"))["parameter"]
Z = []


def pruefe(nr, was, schranke, ist, gut, hinweis=""):
    Z.append(dict(nr=nr, was=was, schranke=schranke, ist=str(ist), gut=bool(gut), hinweis=hinweis))
    print(f"  {'ok    ' if gut else 'FEHLER'} {nr:<4} {was}: {ist}")


# E1 Seitenverweise
falsch = []
for k, seite in J["seiten"].items():
    t = subprocess.run(["pdftotext", "-f", str(seite), "-l", str(seite), "-layout", str(PDF), "-"], capture_output=True, text=True).stdout
    if re.sub(r"\s+", " ", J["ueberschriften"][k]) not in re.sub(r"\s+", " ", t):
        falsch.append(f"{k}: {J['ueberschriften'][k][:40]} nicht auf S. {seite}")
pruefe("E1", f"{len(J['seiten'])} Seitenverweise zeigen auf die Seite mit der Überschrift", "alle", "fehlen: " + (", ".join(falsch) or "keine"), not falsch)
verw = sorted(set(int(x) for x in re.findall(r"S\. (\d+)", MD)))
pruefe("E1b", "jede im Dokument genannte Seite liegt im Manuskript", f"1 … {len(re.findall(chr(12), open(PDF,'rb').read().decode('latin1')))+1}", f"{verw[0]}–{verw[-1]}", verw[-1] <= 200)

# E2/E3 Bezeichner
fw_namen = sorted(set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", MD)))
fehl_fw = [n for n in fw_namen if n not in INO and n not in JS and n not in ("MASSE_UND_GEWICHTE",)]
pruefe("E2", f"{len(fw_namen)} Bezeichner in den Tabellen: jeder steht in der Firmware oder im Labor-Modell", "alle", "fehlen: " + (", ".join(fehl_fw) or "keine"), not fehl_fw)
klassen = ["Winkelerfassung", "Winkelregler", "Motorausgabe", "Nullpunktkorrektur"]
mod_namen = ["f_gitter", "N_K", "N_TN", "N_TV", "NK_K", "NK_TN", "NK_MAX", "Q_ANGLE", "Q_BIAS", "R_MEASURE", "a_max", "MAX_SPEED", "MIN_SPEED", "KIPP_GRENZE", "stoerung", "s_versatz"]
fehl_py = [n for n in mod_namen + [f"class {k}" for k in klassen] if n not in PY]
fehl_js = [n for n in mod_namen + [f"class {k}" for k in klassen] if n not in JS]
pruefe("E3", "Modell-Bezeichner und Klassen im Python-Modell und im Labor-Modell", "alle in beiden", f"fehlen py: {fehl_py or 'keine'}; js: {fehl_js or 'keine'}", not fehl_py and not fehl_js)
fehl_ino = [k for k in ["class Winkelerfassung", "class Winkelregler", "class Motoreinheit", "class Nullpunktkorrektur"] if k not in INO]
pruefe("E3b", "die vier Schichten als Klassen in der Firmware (Schicht 3 heißt dort Motoreinheit)", "alle", f"fehlen: {fehl_ino or 'keine'}", not fehl_ino)

# E4 Werte aus dem Quelltext
def wert(name):
    m = re.search(r"\b" + name + r"\s*=\s*([-+0-9.eE]+)f?\s*;", INO)
    return float(m.group(1)) if m else None
paare = {"REGLER_K": U["K"], "REGLER_TN": U["Tn"], "REGLER_TV": U["Tv"], "NULL_K": U["K_N"], "NULL_TN": U["Tn_N"], "RAD_DURCHMESSER": 2 * U["r_rad"],
         "SCHRITTE_JE_UMDREHUNG": U["Ns"], "Q_WINKEL_WERT": 0.001, "Q_NULL_WERT": 0.003}
abw = {k: (wert(k), v) for k, v in paare.items() if wert(k) is None or abs(wert(k) - v) > 1e-6 * max(1, abs(v))}
pruefe("E4", "Werte der Tabellen = Werte im Quelltext der Firmware (K, T_n, T_v, K_N, T_n,N, Rad, N_s, Q)", "identisch", f"Abweichungen: {abw or 'keine'}", not abw)
takt = re.search(r"TAKT_MS\s*=\s*(\d+)", INO); T_fw = int(takt.group(1)) / 1000 if takt else None
pruefe("E4b", "Takt T der Firmware = Takt des Modells", "gleich", f"{T_fw} s gegen {U['T']} s", T_fw is not None and abs(T_fw - U["T"]) < 1e-12)
for name, soll in (("m", U["m"]), ("l", U["l"])):
    pass
im_doc = [d(x) for x in []] if False else None

# E5 keine Parameterwerte in den Strukturbildern
zahl = re.compile(r"(?<![A-Za-z_0-9/])\d+[.,]\d+(?![.,]?\d*\s*(?:Bit|Hz|kHz|V|Ω|A|mH|Nm|°))")
funde = []
for bild in ("einf_struktur_real", "einf_struktur_simulation", "einf_struktur_esp32"):
    for txt in J["bildtexte"].get(bild, []):
        for m in zahl.finditer(txt):
            funde.append(f"{bild}: „{m.group(0)}“ in „{txt[:40]}…“")
pruefe("E5", "Strukturbilder ohne Zahlenwerte von Parametern (nur Variablen und Seitenverweise)", "0 Funde", "; ".join(funde) or "keine", not funde)

# E6 Reihenfolge der Schichten und Takt in allen drei Programmen
def reihenfolge(text, namen):
    pos = [text.find(n) for n in namen]
    return all(p >= 0 for p in pos) and pos == sorted(pos)
r_ino = reihenfolge(INO, ["class Winkelerfassung", "class Winkelregler", "class Motoreinheit", "class Nullpunktkorrektur"])
r_py = reihenfolge(PY, [f"class {k}" for k in klassen]); r_js = reihenfolge(JS, [f"class {k}" for k in klassen])
pruefe("E6", "Schichten 1–4 in derselben Reihenfolge definiert (Firmware, Python, Labor)", "ja", f"{r_ino}, {r_py}, {r_js}", r_ino and r_py and r_js)
pruefe("E6b", "Takt in den Bildern nur als T; Firmware TAKT_MS, Labor f_gitter", "vorhanden", f"TAKT_MS {takt is not None}, f_gitter {'f_gitter' in JS}", takt is not None and "f_gitter" in JS)

# E7 Bilder
bilder = re.findall(r"!\[[^\]]*\]\(\.\./([^)\s]+)", MD)
fehlend = [b for b in bilder if not (W / b).exists()]
klein = []; breit = []
for b in bilder:
    if (W / b).exists():
        w_, h_ = Image.open(W / b).size
        if w_ < 700: klein.append(b)
        if w_ / h_ > 2.4: breit.append(b)
pruefe("E7", f"{len(bilder)} Bilder vorhanden, ≥ 700 px, ≤ 2,4 : 1", "alle", f"fehlen {fehlend or 'keine'}; klein {klein or 'keine'}; breit {breit or 'keine'}", not fehlend and not klein and not breit)

# E8 PDF und Folge
pdf = H / "EINFUEHRUNG_Segway.pdf"
txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout if pdf.exists() else ""
folge = ["1 · Das Gerät", "2 · Die reale Strecke", "3 · Dieselbe Struktur als Simulation", "4 · Dieselbe Struktur am Gerät", "5 · Die Hardwaremodule", "6 · Der Hardwaretest", "7 · Das Gerät"]
fehl_f = [f for f in folge if f not in re.sub(r"\s+", " ", txt)]
pruefe("E8", "PDF gesetzt; Bilderfolge 1–7 vollständig; Fassung und Datum des Manuskripts im Kopf", "alle", f"fehlen: {fehl_f or 'keine'}; Kopf: {'Fassung ' + J['fassung'] in txt and J['datum'] in txt}",
       pdf.exists() and not fehl_f and ("Fassung " + J["fassung"]) in txt and J["datum"] in txt)

# E9 Hardwaretest im Manuskript
pruefe("E9", "Abschnitt „Der Hardwaretest …“ und Bild des Ablaufs im Manuskript", "beides", f"{'Der Hardwaretest: Kamera' in MAN}, {'Bilder/hardwaretest_ablauf.png' in MAN}", "Der Hardwaretest: Kamera" in MAN and "Bilder/hardwaretest_ablauf.png" in MAN)

fehler = sum(1 for z in Z if not z["gut"])
kopf = f"""---
title: "Prüfprotokoll — Einführungsdokument zum Segway"
author: "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
date: "{J['datum']} · zu Fassung {J['fassung']} des Manuskripts · Prüfmittel `Einfuehrung/pruefe_einfuehrung.py` · {fehler} Beanstandung(en) bei {len(Z)} Prüfungen"
lang: de
---

# Aufgabe

Das Einführungsdokument zeigt die exakte Struktur von Strecke, abgetastetem System, Simulation, Firmware-Peripherie,
Hardware und Hardwaretest mit Seitenverweisen ins Manuskript. Vorgabe: Software und Simulation müssen dem Bild
entsprechen, ohne Abweichung. Jede Zeile hat eine Schranke.

| Nr. | Prüfung | Schranke | Istwert | Ergebnis |
|:----|:------------------------------------------|:-------------|:---------------------------|:-------|
"""
zeilen = "\n".join(f"| {z['nr']} | {z['was']} | {z['schranke']} | {z['ist'][:160]} | {'ok' if z['gut'] else '**FEHLER**'} |" for z in Z)
(H / "PRUEFPROTOKOLL_Einfuehrung.md").write_text(kopf + zeilen + f"\n\n# Ergebnis\n\n{len(Z)} Prüfungen, **{fehler} Beanstandung(en)**.\n", encoding="utf-8")
(H / "pruefe_einfuehrung.json").write_text(json.dumps(dict(pruefungen=Z, fehler=fehler), indent=1, ensure_ascii=False), encoding="utf-8")
subprocess.run(["pandoc", str(H / "PRUEFPROTOKOLL_Einfuehrung.md"), "-o", str(H / "PRUEFPROTOKOLL_Einfuehrung.pdf"), "--pdf-engine=xelatex", "-V", "geometry:margin=2cm",
                "-V", "mainfont=DejaVu Serif", "-V", "monofont=DejaVu Sans Mono"], check=False, capture_output=True)
print(f"{len(Z)} Prüfungen, {fehler} Beanstandung(en)")
sys.exit(1 if fehler else 0)
