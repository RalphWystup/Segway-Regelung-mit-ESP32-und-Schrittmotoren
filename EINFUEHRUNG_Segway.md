---
title: "Der Segway im Bild — Einführung"
subtitle: "Vom realen Gerät zum Modell, zur Simulation, zur Firmware und zurück"
author: "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
date: "Einführung zu Fassung 6 des Manuskripts · 29. September 2026"
lang: de
header-includes:
  - \usepackage{pdflscape}
---

Dieses Blatt geht dem Manuskript *Segway — vom vorhandenen Code zur ausgelegten Regelung* (Fassung 6, 29. September 2026) voran.
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

```{=latex}
\begin{landscape}
```

![Reale Strecke mit Bewegungsgleichung und Übertragungsfunktion, gemessen vom MPU6050, gespeist vom abgetasteten System im ESP32. Nur Variablen; Werte in den Tabellen.](../Bilder/einf_struktur_real.png){width=100%}

```{=latex}
\end{landscape}
```

# 3 · Dieselbe Struktur als Simulation

An die Stelle der realen Strecke tritt das Rechenmodell; das abgetastete System bleibt Zeile für Zeile dasselbe.

```{=latex}
\begin{landscape}
```

![Struktur der Simulation: Rechenmodell der Strecke und Sensormodell, die vier Schichten als Klassen wie in der Firmware.](../Bilder/einf_struktur_simulation.png){width=100%}

```{=latex}
\end{landscape}
```

# 4 · Dieselbe Struktur am Gerät: die Peripherie des ESP32

```{=latex}
\begin{landscape}
```

![Struktur am Gerät: die Firmware im ESP32, der Sensor über I²C, die Treiber über STEP/DIR/ENABLE, die Motoren an den Rädern.](../Bilder/einf_struktur_esp32.png){width=100%}

```{=latex}
\end{landscape}
```

# 5 · Die Hardwaremodule

```{=latex}
\begin{landscape}
```

![Die Module und ihre realen Schnittstellen.](../Bilder/einf_hardware.png){width=100%}

```{=latex}
\end{landscape}
```

# 6 · Der Hardwaretest und das Nachziehen des Reglers

Was das Modell vorhersagt, wird am Gerät gemessen: die Laptop-Kamera filmt die Seitenansicht, die Synchron-LED des ESP32
setzt dieselbe Zeitmarke ins Video und in den Mitschnitt, die Bildauswertung liefert den Winkel unabhängig vom Sensor, und
die Stoßantwort gibt Eigenfrequenz und Abklingzeit des realen Kreises. Stimmen sie mit dem Modell, ist es belegt; wenn nicht,
werden erst die Streckengrößen nachgeführt und dann die Beiwerte in der Simulation neu ausgelegt und in den ESP32 geschrieben.

```{=latex}
\begin{landscape}
```

![Der Hardwaretest als Schleife: Prüfstand, Kamera und Mitschnitt, gemeinsame Zeitachse über die LED, Vergleich mit dem Modell, Neueinstellung.](../Bilder/einf_hardwaretest.png){width=100%}

```{=latex}
\end{landscape}
```

# 7 · Das Gerät

![Der Segway von schräg vorn.](../Bilder/foto_fahrzeug_schraeg.jpg)

\newpage

# Tabellen: die Größen, ihre Werte und ihre Herkunft

## Die Größen der Strecke (Werte: Messung 28.09.2026 und Konstruktion, S. 11)

| Symbol | Bedeutung | Wert | Herkunft |
|:--|:--|--:|:--|
| $m$ | Masse des Aufbaus | 1,248 kg | gewogen, S. 11 |
| $l$ | Schwerpunkthöhe über der Radachse | 44,5 mm | Konstruktion, S. 11 |
| $J$ | Trägheitsmoment um die Radachse | 6,20·10⁻³ kg m² | Radpendel ($J/(ml)$) und $l$, S. 11 |
| $T=\sqrt{J/(mgl)}$ | Kippzeitkonstante | 106,7 ms | Radpendel-Video, S. 16 |
| $d$ | Lagerreibung | 0,002 Nms | Abklingen des Radpendels (Spanne), S. 11 |
| $s$ | Querversatz des Schwerpunkts | ≈ 0,4 mm (Konstruktion) | Ursache des Nullpunktfehlers, S. 16 |
| $\tau_\mathrm{mot}$ | Verzug des Antriebs | 2 ms | Annahme, Empfindlichkeit gerechnet, S. 11 |
| $r$ | Radradius | 32 mm | gemessen; Firmware `RAD_DURCHMESSER`, S. 29 |
| $N_s$ | Schritte je Radumdrehung | 1600 | 200 Vollschritte × 8 Mikroschritte; Firmware `SCHRITTE_JE_UMDREHUNG`, S. 29 |
| $w$, $u$ | Sensorlage über / vor der Achse | 71 mm / 39 mm | gemessen, S. 28 |
| $\tau_\mathrm{lp}$ | Tiefpass des Sensors (42 Hz) | 4,8 ms | Datenblatt MPU6050, S. 26 |
| Pole von $G_u(s)$ | Kippen, Rückstellung, Antrieb | 9,21, -9,54, -500 s⁻¹ | S. 18 |

## Die Größen des abgetasteten Systems (Werte aus dem Quelltext der Firmware gelesen, S. 37)

| Symbol | Bedeutung | Wert | Firmware | Modell / Labor | Herkunft |
|:--|:--|--:|:--|:--|:--|
| $T$ | Regeltakt | 4 ms (250 Hz) | `TAKT_MS`, `DT_SOLL` | `f_gitter` | S. 26 |
| $K$ | Verstärkung des Winkelreglers | 2,3254 m/s je rad | `REGLER_K` | `N_K` | S. 39 |
| $T_n$ | Nachstellzeit | 86,64 ms | `REGLER_TN` | `N_TN` | S. 39 |
| $T_v$ | Vorhaltzeit | 8,77 ms | `REGLER_TV` | `N_TV` | S. 39 |
| $k_i = K/T_n$ | Aufrichtbedingung $k_i > g$ | 26,84 m/s² je rad | — | — | S. 45 |
| $K_N$ | Verstärkung der Nullpunktkorrektur | 0,08127 rad je m/s | `NULL_K` | `NK_K` | S. 39 |
| $T_{n,N}$ | Nachstellzeit der Nullpunktkorrektur | 2,272 s | `NULL_TN` | `NK_TN` | S. 39 |
| $\theta_{N,\mathrm{max}}$ | Anschlag des Nullpunkts | 6,0° (0,105 rad) | `GRENZE` | `NK_MAX` | S. 38 |
| $Q_\theta$, $Q_b$, $R$ | Kalman: Rauschmaße Winkel, Nullpunkt, Messung | 0.001, 0.003, 309,30 | `Q_WINKEL_WERT`, `Q_NULL_WERT`, `R_MESS_WERT` | `Q_ANGLE`, `Q_BIAS`, `R_MEASURE` | S. 25, S. 39 |
| $a_\mathrm{max}$ | Änderungsgrenze (Rampe) | 6,48 m/s² | `A_MAX_VORGABE` | `a_max` | S. 29 |
| $f_\mathrm{max}$, $f_\mathrm{min}$ | Frequenzgrenze, Totzone | 6000 Hz, 0 Hz | `MAX_HZ`, `MIN_HZ` | `MAX_SPEED`, `MIN_SPEED` | S. 29 |
| $\theta_\mathrm{ab}$ | Sicherheitsabschaltung | 30° | `KIPP_GRENZE` | `KIPP_GRENZE` | S. 46 |
| $\theta_\mathrm{frei}$, $\omega_\mathrm{frei}$ | Wiederfreigabe (eine halbe Sekunde lang) | 5°, 60 °/s | `FREI_WINKEL`, `FREI_RATE` | — | S. 46 |
| $f_\mathrm{log}$ | Mitschnittrate | 125 Hz | `LOG_HZ` | — | S. 57 |

## Die Signale zwischen den Blöcken

| Signal | Richtung | Einheit | In der Firmware | Im Modell / Labor |
|:--|:--|:--|:--|:--|
| $a_x, a_y, a_z$, $\omega$ | MPU6050 → Schicht 1 (I²C, jeden Takt) | m/s², °/s | `mpuLesen`, Rohwinkel `atan2` | Sensormodell: `roh`, `drehrate` |
| $\theta_\mathrm{ist}$, $\dot\theta_\mathrm{ist}$ | Schicht 1 → Schicht 2 | rad, rad/s | Klasse `Winkelerfassung` | Klasse `Winkelerfassung` |
| $v_\mathrm{soll}$ | Schicht 2 → Schicht 3 | m/s | Klasse `Winkelregler` | Klasse `Winkelregler` |
| $f$ (Schrittfrequenz), $v_\mathrm{aus}$, $x$ | Schicht 3 → Treiber; Schicht 3 → Schicht 4 | Hz, m/s, m | Klasse `Motoreinheit`, FastAccelStepper | Klasse `Motorausgabe` |
| Nullpunkt | Schicht 4 → Schicht 1 | rad | Klasse `Nullpunktkorrektur` | Klasse `Nullpunktkorrektur` |
| $M$, $s$ | Störmoment, Schwerpunktversatz (nur im Modell einstellbar) | Nm, m | — | `stoerung`, `s_versatz` |


Die Seitenzahlen beziehen sich auf `MANUSKRIPT_Segway_Gesamt_F6.pdf`; sie werden beim Bau aus dem gesetzten PDF gelesen.
