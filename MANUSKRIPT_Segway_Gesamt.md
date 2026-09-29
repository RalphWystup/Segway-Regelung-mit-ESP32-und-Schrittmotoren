---
title: "Segway — vom vorhandenen Code zur ausgelegten Regelung"
subtitle: "Strecke, Sensor, Entwurf und simulativer Nachweis"
author: "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
date: "Fassung 6 · 29. September 2026 (Erstfassung 25. August 2026; Fassung 5 am 28. September: Neuordnung entlang des roten Fadens und gemessene Streckengrößen; Fassung 6: Zustandsmodell, Übertragungsfunktion und geschlossener Kreis im Laplace- und z-Bereich, Prüfprotokoll des Modellkapitels, Bilder neu gezeichnet)"
lang: de
---

# Worum es geht

Ausgangspunkt sind drei laufende Fassungen einer Segway-Regelung: die von
xxxx xxxx aus dem Praxissemester, die studentische Laborarbeit von xxx
xxxxxxxxx und xxxxx xxxxxxx, und eine eigene Neuentwicklung. Alle drei
balancieren. Keine von ihnen ist ausgelegt — die Beiwerte sind erprobt, nicht
gerechnet, und sie sind untereinander weitergereicht worden, ohne dass
nachgeprüft worden wäre, was sie physikalisch bedeuten.

![Das Einachsfahrzeug: zwei Schrittmotoren treiben die Räder unmittelbar, der Lagesensor sitzt vorn über der Achse, oben der Akku. Regelung auf einem ESP32.](Bilder/foto_fahrzeug_front.jpg)

Dieses Manuskript tut beides. Es rechnet nach, was die vorhandenen Fassungen
tun und warum sie funktionieren, und es legt daraus eine Regelung aus, die
nicht erprobt, sondern gerechnet ist — nachgewiesen am Modell, bevor sie das
erste Mal läuft.

Die Leitlinie für den Entwurf:

1. Stabilität hat Vorrang vor jeder anderen Eigenschaft.
2. Die Einheiten sind strikt zu trennen, solange die Trennung das System
   nicht verschlechtert: Winkelerfassung mit Filterung, dann Regler, dann
   Motoreinheit. Darüber liegt die dynamische Nullpunktkorrektur.
3. Ist der Istwinkel null, darf sich das Fahrzeug nicht bewegen.
4. Sollwertvorgabe, Datenaufzeichnung und Weboberfläche dürfen diesen Ablauf
   nicht stören.
5. Kein toter Code, keine unbenutzten Größen.
6. Alles nachrechnen und simulieren, nichts annehmen.

## Der Aufbau des Manuskripts

| Teil | Inhalt |
|---|---|
| I | Das Gesamtsystem und der rote Faden: das Gerät, das Modell in einem Bild, das Vorgehen |
| II | Die Strecke: exakte Herleitung der Bewegungsgleichung, die gemessenen Zahlen, das lineare Zustandsmodell mit Ein- und Ausgang, die Übertragungsfunktion im Laplace-Bereich, die Abtastform, das Simulationsmodell |
| III | Der Sensor: was er misst, wie verschmolzen wird, seine Einbaulage |
| IV | Die Schnittstellen zum abgetasteten Regler: Antrieb, Sensor-Datenfluss, Takt |
| V | Die Anforderungen an den Regler — aus Strecke, Schnittstellen und Befunden abgeleitet |
| VI | Der digitale Regler in vier Schichten: Auslegung und Firmware |
| VII | Der geschlossene Regelkreis: Zustandsmodell des abgetasteten Kreises, charakteristisches Polynom im Laplace-Bereich, Eigenwerte in der z-Ebene, nichtlinearer Nachweis, Korrektur der Reglerparameter |
| VIII | Inbetriebnahme, Prüfstand und offene Messungen |
| Anhänge | Herleitungen, Umrechnungen, Kenngrößen, Programme, Empfindlichkeit der Reserven; F: die vorhandenen studentischen Fassungen (Bestandsaufnahme) |

Der rote Faden: erst das Gesamtsystem als reines Modell — hergeleitet, mit
den Mess- und Zeichnungsdetails belegt —, dann die Schnittstellen zur realen
Hardware und zum abgetasteten Regler, daraus die Anforderungen, dann der
digitale Regler und schließlich der geschlossene Kreis in der Simulation mit
der Korrektur der Reglerparameter.

Jede Aussage nennt, woher sie kommt: aus dem Quelltext, aus dem Datenblatt,
aus der Rechnung oder aus einer Schätzung. Wo etwas geschätzt ist, wird die
Empfindlichkeit dagegen mitgerechnet.

\newpage

# TEIL I — Das Gesamtsystem und der rote Faden

## Das Gerät, das modelliert wird

Gegenstand ist ein zweirädriges Einachsfahrzeug, das sich selbsttätig
aufrecht hält. Es entstand als studentisches Laborprojekt „Regelungstechnik 2"
(xxx xxxxxxxxx, xxxxx xxxxxxx, Stand 29. April 2026) und arbeitet im Versuch.

![Das Fahrzeug der Studierenden von schräg vorn: Radkästen mit den Schrittmotoren, Grundplatte mit Treibern und ESP32, Dachplatte mit Akkubügel. Das weiße Fahrzeug der Messungen ist baugleich.](Bilder/foto_fahrzeug_schraeg.jpg)

Der Aufbau besteht aus einem ESP32, zwei Schrittmotoren mit Treibern in
Schritt-Richtungs-Ansteuerung, einem MPU6050 als Lagesensor und einem
Akkupack. Bedient wird das Fahrzeug über eine Weboberfläche, die der ESP32
als eigenes WLAN bereitstellt.

Anlass der vorliegenden Untersuchung war die Frage, ob der vorhandene
Reglercode das tut, was seine Beschriftung und der Laborbericht angeben. Um
das zu klären, wurde ein physikalisches Modell des Fahrzeugs erstellt, in dem
der Regelcode Zeile für Zeile nachgebildet ist. Das Modell dient nicht der
Vorhersage einzelner Zahlenwerte, sondern der Beantwortung von Fragen, die am
laufenden Gerät nur schwer zu trennen sind: welcher Anteil des Reglers welche
Aufgabe erfüllt, wo die Grenzen liegen und welche Größe sie setzt.

Alle Kenngrößen sind in Anhang D nach ihrer Herkunft aufgeschlüsselt. Sechs
Größen des mechanischen Aufbaus sind geschätzt; ihre Wirkung ist jeweils
durchgerechnet und angegeben.

## Das Vorgehen — der rote Faden

Eine Regelung, die gerechnet und nicht erprobt ist, entsteht in einer festen
Reihenfolge; dieses Manuskript folgt ihr Teil für Teil:

| Schritt | Frage | Wo | Was dabei herauskommt |
|--:|:------------|:-----|:----------------------------------------|
| 1 | Wie bewegt sich das Gerät? | Teil II | die Bewegungsgleichung, exakt hergeleitet; Kippzeitkonstante $T=\sqrt{J/(m g l)}$; Gleichgewichtswinkel; das Zustandsmodell $\dot{\mathbf x}=\mathbf A\mathbf x+\mathbf B u$ und die Übertragungsfunktion $G_u(s)$ mit ihren Polen |
| 2 | Welche Zahlen gehören hinein? | Teil II, „Die Zahlen der Strecke“ | gewogen, aus den Zeichnungen gerechnet, am Radpendel gemessen — jede Zahl mit Herkunft und Unsicherheit |
| 3 | Was sieht der Sensor? | Teil III | der Beschleunigungswinkel ist kein Neigungswinkel; Kreisel und Nullpunkt; Einbaulage $w$, $u$ |
| 4 | Wo berührt der Regler die Hardware? | Teil IV | Schrittfrequenz als Stellgröße, Rohwerte mit 250 Hz, Takt 4 ms, eine Taktverzögerung |
| 5 | Was muss der Regler leisten? | Teil V | Aufrichtbedingung $k_i>g$ und der Pol bei $s=0$ aus der Übertragungsfunktion; Anforderungen mit Schranke: aufrichten, fangen, Stoß, stillstehen bei Istwinkel null, kein Zittern, in den Motorgrenzen, robust über die Unsicherheitsspanne |
| 6 | Wie sieht der Regler aus? | Teil VI | vier Schichten, Beiwerte aus der Auslegung auf den schlechtesten Fall, Firmware = Modell |
| 7 | Hält der Kreis, was gefordert ist? | Teil VII | charakteristisches Polynom und Wurzeln im Laplace-Bereich, Eigenwerte in der z-Ebene, Reserven, nichtlinearer Nachweis, Nachweis mit den gemessenen Zahlen, Korrektur der Reglerparameter |
| 8 | Wie kommt es ans Gerät? | Teil VIII | Inbetriebnahme, Prüfstand, die Messungen, die noch fehlen |

Was die studentischen Fassungen tun und warum sie funktionieren, ist im
Anhang F als Bestandsaufnahme festgehalten; der Faden oben braucht sie nicht.

## Das Modell in einem Bild

![Der modelltechnisch geschlossene Regelkreis: Strecke und Sensor als Modell, darüber die vier Schichten der Firmware im 4-ms-Takt. Rechts, was das Modell prüft.](Bilder/blockschaltbild_regelkreis.png)

Das Modell besteht aus fünf Gliedern, die im Takt der Firmware (4 ms)
hintereinander gerechnet werden; die Mechanik läuft dazwischen in 32
Feinschritten (125 µs):

| Glied | Eingang | Ausgang | Datei |
|:------------|:----------------|:--------------------------|:------------|
| Strecke (Mechanik) | ausgegebene Radgeschwindigkeit $v_\mathrm{aus}$, Störmoment | Neigung $\theta$, Drehrate $\dot\theta$, Beschleunigung $a$, Weg $x$ | `segway_modell.py`, Funktion `simuliere` |
| Antrieb | Sollgeschwindigkeit der Schicht 3 | $v$ mit Verzug $\tau_\mathrm{mot}$ und Rampe $a_\mathrm{max}$ | ebenda |
| Sensor (MPU6050) | $\theta$, $\dot\theta$, $a$ | Rohwinkel aus der Beschleunigung, Drehrate, beide durch den 42-Hz-Tiefpass, verrauscht, mit Kreiselnullpunkt | ebenda |
| Schicht 1: Winkelerfassung | Rohwinkel, Drehrate | Istwinkel und Drehrate ohne Kreiselnullpunkt, minus nachgeführter Nullpunkt | Klasse `Kalman`, `Winkelerfassung` |
| Schicht 2: Winkelregler | Istwinkel, Drehrate | Sollgeschwindigkeit $v$ in m/s | Klasse `Winkelregler` |
| Schicht 3: Motorausgabe | Sollgeschwindigkeit | Schrittfrequenz, begrenzt in Änderung und Betrag; meldet $v_\mathrm{aus}$ und Weg | Klasse `Motorausgabe` |
| Schicht 4: Nullpunkt-korrektur | $v_\mathrm{aus}$, Weg, Wunsch-geschwindigkeit | Nullpunkt in Grad für Schicht 1 | Klasse `Nullpunkt`-`korrektur` |

\newpage

# TEIL II — Die Strecke: exakte Herleitung, gemessene Zahlen, Zustandsmodell und Übertragungsfunktion

## Warum die Bauart des Antriebs die Modellklasse bestimmt

In der Lehrbuchaufgabe „inverses Pendel auf dem Wagen" ist die Stellgröße
eine **Kraft** auf den Wagen. Der Wagen hat eine Masse, die Kraft erzeugt
eine Beschleunigung, und die Rückwirkung des Pendels verändert die
Wagenbewegung.

Bei Schrittmotoren ist das anders. Der Treiber gibt Schrittimpulse aus; jeder
Impuls dreht die Welle um einen festen Winkel. Solange das Motormoment
ausreicht, folgt die Welle. Damit ist nicht die Kraft vorgegeben, sondern die
**Geschwindigkeit**:

$$v = \frac{2\pi r}{N_s}\, f$$

mit dem Radradius $r$, der Schrittzahl je Umdrehung $N_s$ und der
Schrittfrequenz $f$. Für den Aufbau ($r = 32$ mm gemessen, $N_s = 1600$: 200 Vollschritte, achtfacher Mikroschritt) sind das
$0,1257$ mm je Schritt — bei 1000 Hz also 0,126 m/s.

Das hat drei Folgen, die den ganzen Entwurf prägen:

1. Die Rückwirkung des Pendels auf den Wagen entfällt. Der Wagen fährt, was
   ihm befohlen wird — bis das Motormoment nicht mehr reicht.
2. Damit ist die Radgeschwindigkeit ohne Geber bekannt: sie ist die
   ausgegebene Frequenz. Darauf beruht die Nullpunktkorrektur in Teil VI.
3. Die Grenze der Gültigkeit ist die Beschleunigung. Fordert der Regler
   mehr, als das Moment hergibt, gehen Schritte verloren — und dann stimmt
   weder Punkt 1 noch Punkt 2. Deshalb ist $A_\mathrm{max}$ die einzige
   Größe, die gemessen werden muss.

Damit steht der **Eingang** der Strecke fest: die Sollgeschwindigkeit $u = v_\mathrm{soll}$ der Achse (in der Firmware als Schrittfrequenz ausgegeben). Der **Ausgang**, den der Regler braucht, ist die Neigung $\vartheta$; was der Sensor davon liefert, behandelt Teil III. Alles Weitere in diesem Teil dient dem einen Ziel, den Weg vom Eingang zum Ausgang ohne Lücke aufzuschreiben: erst als nichtlineare Bewegungsgleichung, dann mit den gemessenen Zahlen, dann linearisiert als Zustandsmodell und Übertragungsfunktion, schließlich als Rechenmodell mit Nachweis.

## Die Bewegungsgleichung

### Ansatz und Koordinaten

Betrachtet wird die Ebene: $x$ waagerecht in Fahrtrichtung, $y$ senkrecht
nach oben. Der Aufbau ist ein starrer Körper, drehbar um die Radachse. Der
Neigungswinkel $\vartheta$ wird von der Senkrechten aus gemessen und ist
positiv, wenn der Aufbau nach vorn kippt.

Der Schwerpunkt liegt im Abstand $l$ **längs** der Körperachse und um $s$
**quer** dazu versetzt. Der Querversatz ist der entscheidende Punkt: er ist
im wirklichen Aufbau nie null, und er ist die Ursache dessen, was später als
Nullpunktfehler behandelt wird.

Mit dem Einheitsvektor längs der Körperachse
$\mathbf{u} = (\sin\vartheta,\ \cos\vartheta)$ und dem dazu senkrechten
$\mathbf{w} = (\cos\vartheta,\ -\sin\vartheta)$ lautet die Lage des
Schwerpunkts gegenüber der Radachse

$$\mathbf{r} = l\,\mathbf{u} + s\,\mathbf{w}
  = \begin{pmatrix} l\sin\vartheta + s\cos\vartheta \\
                    l\cos\vartheta - s\sin\vartheta \end{pmatrix}$$

### Momentenbilanz über die virtuelle Arbeit

Die Radachse ist ein **beschleunigter** Drehpunkt. Im mitbewegten
Bezugssystem wirkt deshalb neben der Schwerkraft eine Trägheitskraft
$-m\ddot x$ am Schwerpunkt. Das verallgemeinerte Moment zu $\vartheta$ folgt
aus der virtuellen Arbeit, $Q_\vartheta = \mathbf{F}\cdot\partial\mathbf{r}/\partial\vartheta$,
mit

$$\frac{\partial\mathbf{r}}{\partial\vartheta}
  = \begin{pmatrix} l\cos\vartheta - s\sin\vartheta \\
                   -l\sin\vartheta - s\cos\vartheta \end{pmatrix}$$

Für die Schwerkraft $\mathbf{F}_g = (0,\ -mg)$:

$$Q_g = mg\,(l\sin\vartheta + s\cos\vartheta)$$

Für die Trägheitskraft $\mathbf{F}_i = (-m\ddot x,\ 0)$:

$$Q_i = -m\ddot x\,(l\cos\vartheta - s\sin\vartheta)$$

Mit der Lagerreibung $-d\,\dot\vartheta$ und einem äußeren Störmoment $M$
lautet die Bewegungsgleichung

$$\boxed{\;J\,\ddot\vartheta = mg\,(l\sin\vartheta + s\cos\vartheta)
  - m\,\ddot x\,(l\cos\vartheta - s\sin\vartheta)
  - d\,\dot\vartheta + M\;}$$

$J$ ist das Trägheitsmoment um die **Radachse**, also nach Steiner
$J = J_S + m(l^2+s^2)$. In der Gleichung treten die Größen nur in zwei
Verhältnissen auf: $J/(m\,l)$ bestimmt die Kippdynamik, $s/l$ den
Gleichgewichtswinkel. Genau das erste Verhältnis liefert das Radpendel
(Abschnitt „Die Zahlen der Strecke“), ohne dass $J$ und $l$ einzeln gemessen
werden müssten.

Kein Glied ist genähert. Der Anteil $+m\ddot x\,s\sin\vartheta$ ist mit 0,06
bis 0,13 Prozent des Schwerkraftmoments klein, steht aber mit da, damit die
Gleichung ohne Vorbehalt gilt.

\newpage

## Die Zahlen der Strecke: gemessen, gewogen, aus den Zeichnungen gerechnet

| Größe | Wert | Herkunft | Genauigkeit |
|:------------------|:-------------|:----------------------------------------|:-------------|
| Masse $m$ | 1,248 kg | gewogen 28.09.2026 | ± 1 g |
| Schwingungsdauer um die Radachse $T_p$ | 0,6702 ± 0,0041 s | Video `Radpendel.mp4`: ein Rad festgehalten, Aufbau hängt und pendelt; Drehwinkel je Bild aus Merkmalspunkten (AKAZE) und Ähnlichkeitstransformation mit RANSAC gegen ein Bezugsbild, Hintergrund per Medianbild ausgeblendet; vier Anstöße, Sinus-Ausgleich je Abschnitt, gewichtet | 0,6 % |
| Kippzeitkonstante $T=T_p/(2\pi)$ | 106,7 ms | daraus; dieselbe Wurzel $\sqrt{J/(m g l)}$ für hängendes und aufrechtes Pendel | 0,6 % |
| $J/(m\,l)=g\,T^2$ | 111,6 mm | daraus | 1,2 % |
| Schwerpunkthöhe $l$ | 44,5 mm | Konstruktion: neun STL-Teile ausgemessen, Massen aus Volumen und Datenblättern, auf die gewogene Gesamtmasse gestreckt; Akku 224 g gewogen, 112 mm über der Achse | Probe am Gerät offen (A6); zwei Lotlinien |
| Trägheitsmoment $J$ | 6,20·10⁻³ kg·m² | $J/(m l)$ gemessen, $l$ aus der Konstruktion; die Konstruktion allein gab 6,11·10⁻³ — zwei Wege, 1,5 % auseinander | folgt $l$ |
| seitlicher Versatz $s$ | ≈ 0,4 mm (Konstruktion), Video: Platten hängen lotrecht | Sensorpult 39 mm vor der Achse ist der einzige unsymmetrische Anteil | Schicht 4 verträgt 3 mm |
| Lagerreibung $d$ | 0,002 Nms (Nennwert), bis 0,012 Nms | Abklingen des Radpendels: 7–9° je Sekunde bei stromlosen Motoren (Rastmoment + Lager); im Betrieb sind die Motoren bestromt | Spanne, Empfindlichkeit gerechnet |
| Radradius | 32 mm gemessen | Lineal 28.09.; Firmware seit 28.09. abends auf 64 mm | — |
| Spurweite, Reifenbreite | 143 mm, 26,5 mm | Maßband 28.09. | Prüfstand |
| Rampe $a_\mathrm{max}$ | 6,48 m/s² | Firmware (`setAcceleration(50000)` Schritte/s² × Schrittweite) | Motorgrenze mit 1,25 kg nicht gemessen (F3) |
| Verzug $\tau_\mathrm{mot}$ | 2 ms | ANNAHME; 6 ms als Empfindlichkeit gerechnet | offen (F4) |

Warum das Radpendel die richtige Messung ist: für ein physikalisches Pendel um
die Radachse gilt $T_p = 2\pi\sqrt{J/(m g l)}$ — genau die Wurzel, die als
Kippzeitkonstante der aufgerichteten Strecke auftritt. Weder $l$ noch ein
Abstand einer Hilfsachse gehen ein. Das erste Video mit dem Fahrzeug an einer
von Hand gehaltenen Schnur war dagegen ein Doppelpendel (Schnur um die Hand,
Körper um die Schnur; Perioden 1,013 s und 0,510 s im Verhältnis 1,99) und
ließ nur eine Spanne zu; es ist im Maßblatt dokumentiert.

![Die Messung der Kippzeitkonstante: ein Rad wird festgehalten, der Aufbau hängt darunter und pendelt um die Radachse (Bild aus dem Video `Radpendel.mp4`).](Bilder/foto_radpendel_haengend.jpg)

![Auswertung des Radpendels: Drehwinkel je Bild aus Merkmalspunkten (oben), Gegenprobe mit einem Markenpaar (Mitte), Treffergüte (unten). Vier Anstöße, T_p = 0,670 ± 0,004 s.](Konstruktion/radpendel_auswertung.png)

![Das erste Pendelvideo: das Fahrzeug an einer von Hand gehaltenen Schnur — ein Doppelpendel, das nur eine Spanne für J zuließ.](Bilder/foto_schwerpunkt_schnur.jpg)

![Die Maße des Aufbaus aus den STL-Dateien der Konstruktion (Seitenansicht und Draufsicht) und die Messungen am Gerät; Quelle Maßblatt `Konstruktion/MASSE_UND_GEWICHTE.md`.](Konstruktion/skizze_masse.png){height=21cm}

## Gleichgewichtswinkel und Kippzeitkonstante mit den gemessenen Zahlen

Steht das Fahrzeug ($\ddot x = 0$, $\dot\vartheta = 0$, $\ddot\vartheta = 0$),
so verlangt die Bewegungsgleichung

$$l\sin\vartheta + s\cos\vartheta = 0
  \qquad\Longrightarrow\qquad
  \boxed{\vartheta_\mathrm{gl} = -\arctan\frac{s}{l}}$$

Das ist die zentrale Aussage für die spätere Nullpunktkorrektur: der
Gleichgewichtspunkt ist **nicht** die Senkrechte, sobald der Schwerpunkt
seitlich versetzt ist. Mit der gemessenen Schwerpunkthöhe $l = 44{,}5$ mm
ist der Hebel kurz, und jeder Millimeter Versatz wiegt schwer:

| Querversatz $s$ | Gleichgewichtswinkel |
|:---------|----------:|
| 0,5 mm | -0,644° |
| 1,0 mm | -1,288° |
| 2,0 mm | -2,575° |
| 3,0 mm | -3,859° |
| 4,0 mm | -5,139° |

Ein halber Millimeter ist die Genauigkeit, mit der ein Akku sitzt oder ein
Kabel liegt. Keine Kalibrierung des Sensors kann das erfassen, denn der
Sensor misst richtig — falsch ist der Sollwert des Reglers. (Der Nachweis in
Teil VII zeigt, dass die Schicht 4 bis 3 mm Versatz verträgt und bei 4 mm an
ihren Anschlag von 6° stößt.)

Ohne Antrieb und für kleine Winkel wird aus der Bewegungsgleichung

$$J\,\ddot\vartheta = mgl\,\vartheta
  \qquad\Longrightarrow\qquad
  \vartheta(t) = \vartheta_0\cosh\frac{t}{T},\quad
  T = \sqrt{\frac{J}{mgl}}$$

$T$ ist das Maß dafür, wie schnell das Fahrzeug ist. Mit den gemessenen Zahlen
($m = 1,247$ kg, $l = 44{,}5$ mm, $J = 6,20\cdot10^{-3}$ kg m², also
$m g l = 0,5445$ Nm) sind es

$$T = 106,7\ \mathrm{ms}$$

— dieselbe Zahl, die das Radpendel unmittelbar liefert ($T_p/(2\pi)$), denn
hängend und aufgerichtet steht dieselbe Wurzel $\sqrt{J/(mgl)}$ in der
Lösung; nur wird aus dem $\cosh$ des Kippens der $\cos$ des Schwingens. Zum
Vergleich: der Aufbau von xxxx kommt mit einem Schwerpunkt 0,28 m über der
Achse auf 0,195 s und ist damit die deutlich leichtere Regelaufgabe; der
Entwurf vom 25. August rechnete mit geschätzten 128 ms.

## Die Strecke als Übertragungssystem: Zustandsmodell und Übertragungsfunktion

Für den Reglerentwurf wird die Strecke um die aufrechte Lage linearisiert
($\sin\vartheta\approx\vartheta$, $\cos\vartheta\approx 1$, Produkte kleiner
Größen gestrichen) und als System mit **Eingang, Zuständen und Ausgang**
aufgeschrieben. Der Antrieb wird dabei — wie in Teil IV begründet — als Verzug
erster Ordnung mit der Zeitkonstante $\tau_\mathrm{mot}$ zwischen befohlener
und ausgeführter Geschwindigkeit angesetzt.

![Die Strecke als Übertragungssystem: Sollgeschwindigkeit hinein, Neigung heraus. Störmoment und Schwerpunktversatz greifen am Summationspunkt der Momente an.](Bilder/strecke_signalfluss.png)

### Zustandsgleichungen

Zustände $\mathbf x = (\vartheta,\ \omega,\ v)^\mathsf T$ — Neigung,
Drehrate, Achsgeschwindigkeit; Eingang $u = v_\mathrm{soll}$; Störungen
das äußere Moment $M$ und der Schwerpunktversatz $s$:

$$\dot\vartheta = \omega,\qquad
  \dot v = \frac{u - v}{\tau_\mathrm{mot}},\qquad
  J\,\dot\omega = m g l\,\vartheta - m l\,\dot v - d\,\omega + M + m g\,s$$

Mit $\dot v$ eingesetzt lautet das in Matrixform $\dot{\mathbf x} = \mathbf A\mathbf x + \mathbf B u + \mathbf B_M M + \mathbf B_s s$:

$$\mathbf A = \begin{pmatrix} 0 & 1 & 0 \\[2pt]
  \dfrac{m g l}{J} & -\dfrac{d}{J} & \dfrac{m l}{J\tau_\mathrm{mot}} \\[6pt]
  0 & 0 & -\dfrac{1}{\tau_\mathrm{mot}} \end{pmatrix},\qquad
  \mathbf B = \begin{pmatrix} 0 \\[2pt] -\dfrac{m l}{J\tau_\mathrm{mot}} \\[6pt] \dfrac{1}{\tau_\mathrm{mot}} \end{pmatrix},\qquad
  \mathbf B_M = \begin{pmatrix} 0 \\ 1/J \\ 0 \end{pmatrix},\qquad
  \mathbf B_s = \begin{pmatrix} 0 \\ m g/J \\ 0 \end{pmatrix}$$

Mit den gemessenen Zahlen ($m = 1{,}248$ kg, $l = 44{,}5$ mm,
$J = 6,196\cdot10^{-3}$ kg m², $d = 0{,}002$ Nms, $\tau_\mathrm{mot} = 2$ ms):

$$\mathbf A = \begin{pmatrix} 0 & 1 & 0 \\ 87,88 & -0,3228 & 4479,2 \\ 0 & 0 & -500 \end{pmatrix}\ \frac{1}{\mathrm s},\qquad
  \mathbf B = \begin{pmatrix} 0 \\ -4479,2 \\ 500 \end{pmatrix}$$

Die **Ausgänge** sind die wahre Neigung $y_1 = \vartheta$ (was der Regler
eigentlich braucht), die Drehrate $y_2 = \omega$ (was der Kreisel liefert) und
der Beschleunigungswinkel des Sensors (Teil III), der vor dem Tiefpass linear

$$y_3 = \vartheta - \frac{a_s}{g},\qquad a_s = \dot v + w\,\dot\omega$$

lautet und damit über $\dot v$ und $\dot\omega$ auch direkt vom Eingang abhängt
($y = \mathbf C\mathbf x + \mathbf D u$ mit $\mathbf D \neq 0$ in dieser Zeile — der
Grund, warum die Stellgröße im Messwert erscheint, Teil V „Die schwierige
Stelle“). Die Zahlenwerte aller Matrizen stehen in
`Modell/uebertragungsfunktion.json`.

Die Eigenwerte von $\mathbf A$ sind die Pole der offenen Strecke:

$$\lambda_{1,2} = \frac{-d \pm \sqrt{d^2 + 4 J m g l}}{2J} = 9,21\ \mathrm{s^{-1}},\ -9,54\ \mathrm{s^{-1}},\qquad
  \lambda_3 = -\frac{1}{\tau_\mathrm{mot}} = -500\ \mathrm{s^{-1}}$$

Der positive Eigenwert ist das Kippen: $1/T = 9,37$ s⁻¹, um die
kleine Reibung verschoben ($\lambda_1\lambda_2 = -mgl/J = -1/T^2$ exakt).

### Die Übertragungsfunktion im Laplace-Bereich

Laplace-Transformation der Zustandsgleichungen (Anfangswerte null) und
Auflösen nach $\Theta(s)$ ergibt

$$\boxed{\;G_u(s) = \frac{\Theta(s)}{V_\mathrm{soll}(s)}
  = \frac{-\,m l\, s}{(1 + \tau_\mathrm{mot} s)\,(J s^2 + d s - m g l)}\;}
  \qquad
  G_M(s) = \frac{\Theta(s)}{M(s)} = \frac{1}{J s^2 + d s - m g l}$$

Mit $T^2 = J/(mgl)$ und $2\delta T = d/(mgl)$ in Normalform:

$$G_u(s) = -\,\frac{1}{g}\cdot\frac{s}{(1 + \tau_\mathrm{mot} s)\,(T^2 s^2 + 2\delta T s - 1)},
  \qquad T = 106,7\ \mathrm{ms},\ \delta = 0,0172$$

Drei Eigenschaften, die den ganzen Entwurf bestimmen, stehen darin offen:

| Eigenschaft | Woran man sie sieht | Was sie für den Regler heißt |
|:------------------|:-----------------------------|:-------------------------------------|
| **ein Pol rechts**, $s = +9,21$ s⁻¹ | Nenner $T^2 s^2 + 2\delta T s - 1$ hat ein negatives Absolutglied | die Strecke ist instabil; der Kreis muss diesen Pol nach links ziehen (Teil V, A1) |
| **eine Nullstelle in $s = 0$** | Zähler $-m l\,s$ | eine konstante Geschwindigkeit ändert die Neigung nicht — nur Beschleunigung wirkt. Ein I-Anteil im Winkelregler kürzt diese Nullstelle; im Kreis bleibt ein Pol bei $s=0$, den erst die Schicht 4 bindet (Teil V) |
| **negatives Vorzeichen** | $-1/g$ | Sollgeschwindigkeit nach vorn neigt den Aufbau nach hinten; der Regler muss „in die Fallrichtung fahren“ |

Der Antriebspol $-1/\tau_\mathrm{mot}$ liegt fünfzigmal weiter links als die
Kippbewegung und begrenzt den Kreis erst bei Verstärkungen weit über dem
Entwurf (Teil VII, Reserven).

![Pole und Nullstelle der Strecke in der s-Ebene, gemessene Zahlen.](Bilder/strecke_pole.png)

**Probe (zwei Wege).** Die Polynomform wurde an vier Stellen $s$ gegen
$\mathbf C(s\mathbf I - \mathbf A)^{-1}\mathbf B$ aus dem Zustandsmodell gerechnet:
Abweichung 1,0·10⁻14 relativ für $G_u$, 9,7·10⁻16 für $G_M$ — also
dieselbe Funktion, einmal von Hand hergeleitet, einmal numerisch aus den
Matrizen.

### Die Abtastform: was der Regler alle 4 ms vorfindet

Der Regler greift alle $T_a = 4$ ms ein und hält die Stellgröße dazwischen
fest (Halteglied nullter Ordnung, Teil IV). Dafür hat das lineare Modell eine
exakte Lösung:

$$\mathbf x[k+1] = \mathbf\Phi\,\mathbf x[k] + \mathbf\Gamma\,u[k],\qquad
  \mathbf\Phi = e^{\mathbf A T_a},\quad
  \mathbf\Gamma = \mathbf A^{-1}(\mathbf\Phi - \mathbf I)\,\mathbf B$$

$$\mathbf\Phi = \begin{pmatrix} 1,000703 & 0,003998 & 0,020335 \\ 0,351385 & 0,999412 & 7,7422 \\ 0 & 0 & 0,135335 \end{pmatrix},\qquad
  \mathbf\Gamma = \begin{pmatrix} -0,020335 \\ -7,7422 \\ 0,864665 \end{pmatrix}$$

Die Eigenwerte von $\mathbf\Phi$ sind $e^{\lambda_i T_a}$: 0,135335, 0,962569, 1,037546 — der
Kipp-Eigenwert $1{,}0375$ heißt: ohne Regler wächst eine Neigung je Takt um
3,75 Prozent. Der Simulator (nächster Abschnitt) rechnet dieselbe Strecke mit
32 expliziten Euler-Schritten je Takt; sein $\mathbf\Phi$ stimmt im
Mechanikblock ($\vartheta$, $\omega$) auf 2,2·10⁻5 relativ mit
$e^{\mathbf A T_a}$ überein. Nur die Antriebszeile ($e^{-T_a/\tau_\mathrm{mot}} = 0{,}135$)
trifft Euler bei $T_a/\tau_\mathrm{mot} = 2$ mit 6,3 Prozent Fehler — genau der
Wert, den $(1 - 2/32)^{32}$ gegen $e^{-2}$ erwarten lässt; er betrifft einen in
5 ms abgeklungenen Anteil und ist im Nachweis (Teil VII, Vergleich linear gegen
nichtlinear) enthalten.

### Sprungantwort der offenen Strecke — zwei Wege

Ein Sprung der Sollgeschwindigkeit um 10 mm/s aus der aufrechten Ruhe:
das lineare Modell (Fortschaltung mit $e^{\mathbf A\,\mathrm dt}$) gegen die
nichtlineare Bewegungsgleichung mit Runge-Kutta vierter Ordnung.

![Sprungantwort der offenen Strecke: erst kippt der Aufbau gegen die Fahrrichtung nach hinten, dann läuft die Neigung mit $e^{t/T}$ davon. Unten der Unterschied zwischen linearem und nichtlinearem Modell.](Bilder/strecke_sprungantwort.png)

Nach 0,3 s stehen -4,249° (nichtlinear) gegen -4,249° (linear);
die relative Abweichung von 1,1·10⁻4 ist der Preis der Linearisierung bei
vier Grad Neigung — und zugleich der Beleg, dass Matrizen und Gleichung
dasselbe System beschreiben. Das Bild zeigt auch, was die Nullstelle bedeutet:
der Sprung wirkt nur in seinem Moment (über $\dot v$); danach ist die
Geschwindigkeit konstant und die Strecke sich selbst überlassen.

## Das Simulationsmodell der Strecke

### Zustände und Schrittweite

Das Zeitmodell führt drei Zustände der Strecke:

| Zustand | Bedeutung | Einheit |
|---|---|---|
| $\vartheta$ | wahre Neigung | rad |
| $\omega$ | Drehrate | rad/s |
| $v$ | Wagengeschwindigkeit | m/s |

dazu $x$ als Weg. Gerechnet wird in zwei Ebenen: das **Regelraster** mit
$T = 4$ ms, in dem Sensor und Regler arbeiten, und darin `feinschritte`
**Rechenschritte** der Mechanik. Die Stellgröße bleibt innerhalb eines
Rasters konstant — genau wie im Gerät, wo die Schrittfrequenz zwischen zwei
Regelzyklen nicht verändert wird.

### Der Antrieb

    dv = clip( (v_soll - v) / tau_mot , -a_max , +a_max )
    v  = v + dv * dt
    a_wagen = dv

Zwei Größen bilden den Antrieb ab: `tau_mot` ist der Verzug erster Ordnung
zwischen Befehl und Ausführung (Rechenzeit des Treibers, Rampe der
Bibliothek), `a_max` die Beschleunigungsgrenze. Über `a_max` hinaus würde der
Motor Schritte verlieren — im Modell wird stattdessen abgeschnitten, und die
Motoreinheit des Reglers begrenzt ihre Forderung von sich aus auf denselben
Wert. Dadurch bleibt die ausgegebene Frequenz auch in der Simulation die
wahre Radgeschwindigkeit.

### Die Mechanik

    domega = ( m*g*(l*sin(th) + s*cos(th))
             - m*a_wagen*(l*cos(th) - s*sin(th))
             - d*om + M ) / J
    om = om + domega*dt
    th = th + om*dt

Das ist die hergeleitete Gleichung, Glied für Glied. Das Verfahren ist das
halbimplizite Euler-Verfahren: erst wird $\omega$ mit der neuen Beschleunigung
fortgeschrieben, dann $\vartheta$ mit dem neuen $\omega$. Es ist von erster
Ordnung und für dieses Problem gutmütig, weil es die Energie nicht
systematisch aufschaukelt.

### Nachweis, dass das Rechenmodell die Gleichung löst

Das Rechenmodell wird auf zwei Wegen gegen die Gleichung geprüft, die es lösen soll: gegen eine Runge-Kutta-Lösung derselben nichtlinearen Gleichung und — im Abschnitt „Die Strecke als Übertragungssystem“ — gegen die geschlossene Lösung $\mathbf\Phi=e^{\mathbf A T}$ des linearen Modells.

Geprüft wird gegen ein Runge-Kutta-Verfahren vierter Ordnung derselben
Gleichung mit 200 000 Schritten. Freies Kippen aus 0,2 Grad, mit Dämpfung und
2 mm Schwerpunktversatz, nach 0,2 s:

| Rechenschritte je Regeltakt | Schrittweite | Abweichung |
|---|---|---|
| 8 | 0,50 ms | 0,273 % |
| 16 | 0,25 ms | 0,136 % |
| 32 | 0,125 ms | 0,068 % |
| 64 | 0,0625 ms | 0,034 % |

Der Fehler halbiert sich mit der Schrittweite — das ist das erwartete
Verhalten erster Ordnung und belegt, dass kein Programmierfehler vorliegt,
sondern nur das Verfahren begrenzt. Gerechnet wird mit 32 Schritten; für
Suchläufe, bei denen es auf die dritte Stelle nicht ankommt, mit 8.

Zusätzlich geprüft wurde die geschlossene Lösung des freien Kippens,
$\vartheta = \vartheta_0\cosh(t/T)$, und die Sprungantwort auf ein konstantes
Störmoment, $\vartheta = M t^2/(2J)$. Beide werden im Rahmen der
Verfahrensordnung getroffen.

### Was das Streckenmodell nicht enthält

| Nicht abgebildet | Folge |
|---|---|
| Radschlupf | bei Schlupf ist die Frequenz nicht mehr die Geschwindigkeit — die Grundlage der Schichten 3 und 4 fällt |
| Einzelne Schritte statt stetiger Geschwindigkeit | ob der Motor bei wenigen Hertz rastet oder singt, ist nicht zu sehen |
| Nachgiebigkeit des Aufbaus | ein weicher Rahmen bringt eine zweite Eigenfrequenz mit |
| Rollreibung, Untergrund | wirkt wie zusätzliche Dämpfung, also gutmütig |
| Zweite Achse, Lenkung | die Aufgabe ist eben behandelt |

Die ersten beiden sind die einzigen, die im Betrieb wirklich ins Gewicht
fallen können, und beide sind am Gerät zu prüfen, nicht zu rechnen.

\newpage

# TEIL III — Der Sensor: Modell, Grenzen und Einbaulage

## Was der Beschleunigungsmesser wirklich misst

Ein Beschleunigungsmesser misst nicht die Beschleunigung, sondern die
**spezifische Kraft** — die Beschleunigung abzüglich der Schwerebeschleunigung.
Im Stillstand zeigt er deshalb nach oben und liefert die Lotrichtung. Wird er
waagerecht beschleunigt, kippt die scheinbare Lotrichtung um

$$\Delta\vartheta = \arctan\frac{a}{g}$$

| $a$ | Scheinneigung |
|---|---|
| 0,5 m/s² | 2,9° |
| 1 m/s² | 5,8° |
| 2 m/s² | 11,5° |
| 4 m/s² | 22,2° |
| 8 m/s² | 39,2° |

Das ist keine Störung, die sich wegfiltern ließe, sondern eine grundsätzliche
Mehrdeutigkeit: Neigung und Beschleunigung sind aus einer einzigen Messung
nicht zu trennen.

Und die Beschleunigung, die den Fehler erzeugt, ist die **Stellgröße des
Reglers selbst**. Über den Sensor läuft damit eine zweite, unerwünschte
Rückführung: der Regler beschleunigt, um aufzurichten, und genau diese
Beschleunigung meldet ihm der Sensor als zusätzliche Neigung zurück — mit
falschem Vorzeichen.

Sitzt der Sensor nicht auf der Drehachse, kommen zwei weitere Anteile hinzu.
Bei einer Höhe $w$ über der Achse und einem Versatz $u$ nach vorn misst er

$$a_\mathrm{schein} = \ddot x + w\,\ddot\vartheta - u\,\dot\vartheta^2$$

Der erste Zusatzanteil ist von erster Ordnung und wird im Modell geführt; der
zweite ist von zweiter Ordnung in der Drehrate und bei den auftretenden
Werten belanglos.

## Der Kreisel

Der Kreisel liefert die Drehrate unmittelbar, schnell und ohne
Mehrdeutigkeit. Sein Mangel ist der **Nullpunkt**: der MPU6050 hat laut
Datenblatt bis 20 °/s Nullpunktfehler. Integriert man die Drehrate zum
Winkel, wächst dieser Fehler linear mit der Zeit — 1 °/s sind nach einer
Minute 60 Grad.

Beide Messungen sind also für sich unbrauchbar: der eine ist absolut, aber
verfälscht; der andere ist genau, aber driftet. Erst zusammen ergeben sie
einen Winkel.

## Die drei Wege der Verschmelzung

| Weg | Aufbau | Nullpunkt des Kreisels |
|---|---|---|
| DMP im Baustein | Quaternionenfusion, feste lange Zeitkonstante | wird nicht geschätzt |
| Komplementärfilter | Hochpass Kreisel, Tiefpass Beschleunigung | wird nicht geschätzt |
| Kalman | zwei Zustände: Winkel **und** Nullpunkt | wird mitgeschätzt |

Der Komplementärfilter lautet

    theta_hat += (omega + bias)*dt + (theta_acc - theta_hat)*dt/tau

also Integration der Drehrate mit langsamem Zug auf den
Beschleunigungswinkel. Im Frequenzbereich ist das ein Hochpass auf den
Kreisel und ein Tiefpass auf den Beschleunigungsmesser, beide mit der
Eckfrequenz $1/\tau$.

Am Modell verglichen, Aufrichten aus 3 Grad mit dem Studentenregler:

| Sensorweg | Verhalten | größter Messfehler |
|---|---|---|
| idealer Sensor | balanciert | 0,39° |
| Kalman | balanciert | 0,57° |
| DMP, $\tau = 5$ s | balanciert | 2,25° |
| Komplementär, $\tau = 0{,}2$ s | **fällt** | 8,55° |
| Komplementär, $\tau = 0{,}5$ s | **fällt** | 6,89° |
| Komplementär, $\tau = 1{,}0$ s | balanciert | 0,92° |
| Komplementär, $\tau = 3{,}0$ s | balanciert | 1,57° |

Es gibt ein Optimum. Eine zu kurze Zeitkonstante lässt die eigene
Beschleunigung als Scheinneigung durch; eine zu lange lässt den
Nullpunktfehler des Kreisels einlaufen. Der Kalman schlägt alle
Komplementärfilter, weil er als einziger den Kreiselnullpunkt als eigenen
Zustand führt und ihn damit ausregelt statt ihn nur zu unterdrücken.

## Der Kalman-Filter im Einzelnen

Verwendet wird die Fassung, die im Quelltext steht — zwei Zustände, Winkel
$\hat\vartheta$ und Kreiselnullpunkt $\hat b$:

**Vorhersage** mit der gemessenen Drehrate $\omega_m$:

$$\hat\vartheta \leftarrow \hat\vartheta + T(\omega_m - \hat b)$$

$$P \leftarrow \begin{pmatrix}1 & -T\\ 0 & 1\end{pmatrix} P
              \begin{pmatrix}1 & 0\\ -T & 1\end{pmatrix}
              + \begin{pmatrix}Q_\vartheta T & 0\\ 0 & Q_b T\end{pmatrix}$$

**Korrektur** mit dem Beschleunigungswinkel $\vartheta_\mathrm{acc}$:

$$S = P_{11} + R,\qquad K_0 = \frac{P_{11}}{S},\qquad K_1 = \frac{P_{21}}{S}$$

$$y = \vartheta_\mathrm{acc} - \hat\vartheta,\qquad
  \hat\vartheta \leftarrow \hat\vartheta + K_0 y,\qquad
  \hat b \leftarrow \hat b + K_1 y$$

Die drei Beiwerte bestimmen das Verhalten. $R$ ist der wichtigste: er sagt,
wie sehr dem Beschleunigungsmesser geglaubt wird. Die eingeschwungenen
Verstärkungen bei 250 Hz:

| $R$ | $K_0$ | Zeitkonstante der Fusion | Gewicht je Takt |
|---|---|---|---|
| 0,03 | 0,01698 | 0,232 s | 1,70 % |
| 1 | 0,00562 | 0,708 s | 0,56 % |
| 30 | 0,00228 | 1,753 s | 0,23 % |
| 100 | 0,00168 | 2,384 s | 0,17 % |
| 309 | 0,00126 | 3,17 s | 0,13 % |

**Der bisherige Wert $R = 0{,}03$ ergibt eine Zeitkonstante von 0,232 s — der
Filter ist damit langsamer, als das Fahrzeug kippt (106,7 ms), und lässt
trotzdem die eigene Beschleunigung durch.** Das ist die schlechteste beider
Welten und der Grund, aus dem der Kreis mit diesen Werten schwach instabil
ist.

### Zwei Punkte, die am Gerät zählen

**Der Filter braucht vier Sekunden, bis er eingeschwungen ist.** Mit $P = 0$
beim Start ist $K_0$ zunächst ebenfalls null: der Filter hört dem
Beschleunigungsmesser nicht zu und integriert nur den Kreisel. Ein
Anfangsfehler bleibt in dieser Zeit stehen.

| nach | $K_0$ | Anteil des Endwerts |
|---|---|---|
| 0,1 s | 0,00326 | 19 % |
| 0,5 s | 0,01192 | 70 % |
| 1,0 s | 0,01548 | 91 % |
| 2,0 s | 0,01666 | 98 % |

Abhilfe: die Fehlerkovarianz gleich auf ihren Endwert setzen. Die Firmware
iteriert dazu beim Einschalten die Kovarianzgleichung bis zum Stillstand —
das kostet wenige Millisekunden und macht das Verhalten vom ersten Takt an
gleich.

**Der Kreiselnullpunkt muss kalibriert werden.** Der Filter findet ihn zwar
selbst, braucht dafür aber rund zwanzig Sekunden, und so lange steht der
Fehler im gemeldeten Winkel:

| Kreiselnullpunkt beim Start | Ergebnis |
|---|---|
| bis 3 °/s | wird gefunden, Fahrzeug bleibt stehen |
| ab 4 °/s | Sicherheitsabschaltung |

Da der MPU6050 bis 20 °/s haben darf, ist die Kalibrierung beim Einschalten
keine Feinheit, sondern notwendig. Aus 200 Messungen bei 0,05 °/s Streuung
bleiben etwa 0,004 °/s übrig; langsame Wärmedrift bis 2 °/s steckt der Filter
danach weg.

## Takt und Laufzeit — was feststeht und nicht geschätzt ist

Vier Zahlen der Sensorkette mussten nicht geschätzt werden. Sie ergeben sich
aus der verwendeten Bibliothek und aus dem Datenblatt:

| Größe | Wert | Quelle |
|---|---|---|
| Grundabtastrate | 200 Hz | `setRate(4)` |
| Ausgaberate des Bewegungsprozessors | 100 Hz | `MPU6050_DMP_FIFO_RATE_DIVISOR = 0x01` |
| Tiefpass der Rohsignale | 42 Hz | `setDLPFMode(MPU6050_DLPF_BW_42)` |
| Gruppenlaufzeit dieses Tiefpasses | 4,8 ms | Datenblatt MPU6050 |

Die Ausgaberate von 100 Hz hat eine Folge, die über die Sensorik hinausgeht:
sie ist der wirkliche Regeltakt der studentischen Fassung, nicht die 250 Hz
der Hauptschleife. Da im Code weder beim Integrieren noch beim Differenzieren
durch die Schrittweite geteilt wird, hängen $k_i$ und $k_d$ unmittelbar
daran. Der neue Entwurf ist davon frei — er rechnet mit der Schrittweite aus
der Uhr und ist von 100 bis 500 Hz unempfindlich.

Die eigene Fassung greift nicht auf den Bewegungsprozessor zurück, sondern
liest die Rohwerte unmittelbar mit dem Regeltakt von 250 Hz. Dort gilt von
den vier Zeilen nur die letzte: der 42-Hz-Tiefpass mit seinen 4,8 ms.

## Das Sensormodell in der Simulation

Der Baustein wird mit seinen wirklichen Eigenschaften nachgebildet:

    a_schein = a_wagen + w*domega - u*om^2
    a_lp  += (a_schein - a_lp )*dt/tau_lp
    th_lp += (theta    - th_lp)*dt/tau_lp
    om_lp += (omega    - om_lp)*dt/tau_lp
    theta_acc = th_lp - arctan2(a_lp, g)

`tau_lp` ist der eingeschaltete Tiefpass des MPU6050. `setDLPFMode(42 Hz)`
gibt laut Datenblatt 4,8 ms Gruppenlaufzeit; genau dieser Wert wird als
Zeitkonstante einer Verzögerung erster Ordnung angesetzt, und zwar für
Beschleunigung, Neigung und Drehrate gleichermaßen — so, wie der Baustein ihn
wirklich schaltet.

Auf die Rohwerte kommt Rauschen (0,05° auf den Beschleunigungswinkel,
0,05 °/s auf die Drehrate) und der Kreiselnullpunkt. Die Abfrage geschieht
mit der Ausgaberate des Sensors, die vom Regelraster verschieden sein darf;
zwischen zwei Abfragen rechnet der Regler mit dem zuletzt gemeldeten Wert
weiter — genau wie im Gerät.

## Was das Sensormodell nicht enthält

Die Erschütterung der Schrittmotoren. Sie liegt unmittelbar auf dem
Beschleunigungsmesser, und ihre Amplitude ist nicht bekannt. Der 42-Hz-
Tiefpass ist im Modell, ihre Anregung nicht. Das ist die größte verbleibende
Unsicherheit der Sensorkette und der Grund, aus dem der Entwurf so ausgelegt
ist, dass er auch bei zwanzigfachem Rauschen noch trägt.

\newpage

## Die Einbaulage und die Sensorkette im Modell

Der MPU6050 liefert im Modell drei Größen, alle durch denselben Tiefpass
erster Ordnung mit der Gruppenlaufzeit 4,8 ms des 42-Hz-Filters (Datenblatt,
`setDLPFMode(MPU6050_DLPF_BW_42)`): die Neigung $\theta_\mathrm{lp}$, die
Drehrate $\omega_\mathrm{lp}$ und die scheinbare Beschleunigung. Weil der
Sensor nicht auf der Achse sitzt, sondern $w=71$ mm darüber und $u=39$ mm
davor (gemessen 28.09.), sieht er zusätzlich zur Wagenbeschleunigung die
Beschleunigungen der Kippbewegung:

$$
a_\mathrm{schein} = a + w\,\ddot\theta - u\,\dot\theta^2 .
$$

Der Rohwinkel aus der Beschleunigung ist
$\theta_\mathrm{acc} = \theta_\mathrm{lp} - \arctan(a_\mathrm{lp}/g)$; bei
$a=3$ m/s² sind das 17° Messfehler — die schwierige Stelle jedes
Balancierfahrzeugs. Dazu kommen weißes Rauschen (0,05° und 0,05 °/s als
Nennwerte, zu messen: F5) und ein Kreiselnullpunkt (0,05 °/s nach der
Startkalibrierung). Der Sensor liefert mit 250 Hz; der Zeitpunkt wird aus dem
Zähler gerechnet, nicht fortlaufend addiert, damit kein Takt durch Rundung
ausfällt.

\newpage

# TEIL IV — Die Schnittstellen zum abgetasteten Regler

Der digitale Regler berührt die Hardware an drei Stellen: er bekommt vom
Sensor Rohwerte, er gibt an den Antrieb eine Schrittfrequenz, und er tut
beides in einem festen Takt. Alles, was der Regler von der Welt weiß und in
der Welt bewirkt, läuft über diese drei Schnittstellen — deshalb werden sie
hier genau festgelegt, mit Zahlen, bevor der Regler entworfen wird.

| Schnittstelle | Richtung | Größe | Zahl | Herkunft |
|:--------|:-----|:------------------|:------------------|:---------|
| Sensor → Regler | Eingang | Rohwinkel aus der Beschleunigung, Drehrate (Grad, Grad/s), nach dem 42-Hz-Tiefpass | 250 Hz, Laufzeit 4,8 ms | Bibliothek, Datenblatt MPU6050 |
| Regler → Antrieb | Ausgang | Schrittfrequenz je Motor, mit Rampe und Grenze | 0,1257 mm je Schritt (Ø 64 mm gemessen, 1600 Schritte je Umdrehung), höchstens 6000 Hz = 0,75 m/s, Rampe 6,48 m/s² | Firmware, FastAccelStepper |
| Takt | — | Regeltakt und Verzögerung | 4 ms; die Stellgröße wirkt einen Takt später | Firmware (`TAKT_MS`) |
| Regler → Gerät | Ausgang | Weg und Geschwindigkeit ohne Geber | aus der ausgegebenen Schrittfrequenz, solange kein Schritt verloren geht | Bauart des Schrittantriebs |

## Der Antrieb: Schrittfrequenz als Stellgröße

Die Schicht 3 gibt eine Schrittfrequenz aus; die Bibliothek FastAccelStepper
fährt sie mit einer Rampe an. Im Modell steht dafür ein Verzug erster Ordnung
$\dot v = (v_\mathrm{soll}-v)/\tau_\mathrm{mot}$, begrenzt auf
$|\dot v|\le a_\mathrm{max}$, und die Umrechnung
$v = f\cdot 2\pi r/N_s$ mit $N_s=1600$ Schritten je Umdrehung und $r$ dem
Radradius. Die Schrittweite ist $\pi\cdot 64\,\mathrm{mm}/1600 = 0{,}1257$ mm
(Rad Ø 64 mm gemessen am 28.09.2026; die Firmware rechnet seit dem Bau vom
selben Abend damit, vorher mit 66 mm). Die Schrittquantisierung selbst — dass die
Geschwindigkeit nur in Sprüngen von einem Schritt je Takt vorliegt — ist im
Modell nicht abgebildet (Aufgabe F2); sie bestimmt das Restzittern bei
kleinen Geschwindigkeiten.

Die Konsequenz für den Regler steht in Teil II: die Strecke ist
geschwindigkeitsgeführt, die Stellgröße ist eine Geschwindigkeit, und der
Integralanteil richtet auf. Die Grenzen des Antriebs — Rampe und
Höchstfrequenz — sind harte Grenzen der Schnittstelle; ein Regler, der mehr
fordert, verliert Schritte, und dann ist die ausgegebene Frequenz nicht mehr
die Radgeschwindigkeit.

## Der Sensor als Datenquelle

Die Firmware liest die Rohwerte des MPU6050 mit dem Regeltakt (250 Hz) und
verschmilzt sie selbst (Kalman-Filter, Teil VI); der Bewegungsprozessor des
Bausteins wird nicht benutzt. Vom Sensor gilt an der Schnittstelle nur der
42-Hz-Tiefpass mit 4,8 ms Gruppenlaufzeit (Teil III, „Takt und Laufzeit“)
und die Einbaulage: 71 mm über der Achse, 39 mm nach vorn (gemessen). Was der
Beschleunigungsmesser meldet, ist der Winkel der scheinbaren Lotrichtung —
bei 3 m/s² eigener Beschleunigung 17° neben der Neigung. Diese Eigenschaft
der Schnittstelle bestimmt die Filterung (Teil III) und den Nullpunkt (Teil VI).

## Takt, Reihenfolge und Verzögerung

Die Reihenfolge je Takt ist die der Firmware: erst wird aufgezeichnet, was
gerade ausgegeben wird, dann rechnet die Mechanik einen Takt mit dieser
Ausgabe, dann liefert der Sensor, dann rechnen die Schichten 4, 1, 2, 3 den
nächsten Stellwert. Der Stellwert wirkt also einen Takt später — das ist die
Rechenzeitverzögerung des Geräts, nicht nachträglich hineingesetzt, sondern
Folge der Reihenfolge.

Das Modell hält diese Reihenfolge Zeile für Zeile ein (Teil I, Bild); der
Nachweis, dass Firmware und Modell dasselbe rechnen, steht in Teil VII.

\newpage

# TEIL V — Die Anforderungen an den Regler

Aus der Strecke (Teil II), dem Sensor (Teil III) und den Schnittstellen
(Teil IV) folgen die Anforderungen; die Befunde an den vorhandenen Fassungen
(Anhang F) sagen, woran es bisher scheiterte. Jede Anforderung hat eine
Schranke und ein Prüfmittel — so wird sie in Teil VII nachgewiesen.

| Nr. | Anforderung | Woher | Schranke | Nachweis |
|--:|:----------------------------------------|:--------------|:---------|:--------|
| A1 | **Aufrichten**: der Kreis muss den instabilen Pol der Strecke ($1/T$ = 9,4 s⁻¹) binden; bei geschwindigkeitsgeführter Strecke heißt das $k_i = K/T_n > g$ | Übertragungsfunktion (Teil II), Aufrichtbedingung (unten) | $k_i > 9{,}81$ m/s² je rad | Eigenwerte (Teil VII) |
| A2 | **Fangbereich**: aus der Ruhe mindestens 15° aufrichten, mit Drehrate ein Fangfeld, das das Anfahren aus der Hand erlaubt | Bedienung; Kippgrenze 30° der Firmware | ≥ 15° aus der Ruhe | nichtlinear (Teil VII) |
| A3 | **Stoßfestigkeit**: ein Stoß von 50 ms Dauer darf nicht umwerfen | Betrieb auf dem Prüfstand | ≥ 0,3 Nm über 50 ms | nichtlinear |
| A4 | **Istwinkel null bedeutet Stillstand**: ein Schwerpunktversatz oder Kalibrierfehler darf nicht zum Wegfahren führen (Leitlinie 3) | Sensor kann Gleichgewicht nicht sehen (Teil III); Versatz s der Konstruktion ≈ 0,4 mm | Weg in 20 s < 5 mm; Toleranz ≥ 2 mm Versatz | nichtlinear, Schicht 4 |
| A5 | **Kein Zittern im Stand**: die Totzone der Motorausgabe erzeugt das Zittern, sie verhindert es nicht | Befund (Anhang F, „Die Totzone erzeugt das Zittern“) | Totzone 0 Hz; Restzittern < 0,05° bei Nennrauschen | nichtlinear |
| A6 | **In den Grenzen des Antriebs**: geforderte Beschleunigung ≤ Rampe, Schrittfrequenz ≤ 6000 Hz, sonst Schrittverlust | Teil IV | a ≤ 6,48 m/s², f ≤ 6000 Hz | nichtlinear |
| A7 | **Robust über die Unsicherheitsspanne**: stabil für Kippzeitkonstanten 87–191 ms, Treiberverzug 1–6 ms, Sensorhöhe 0–100 mm | Zahlen waren geschätzt; seit 28.09. gemessen (106,7 ms) | Reserve ≥ 2 nach oben, ≤ 0,5 nach unten | Eigenwerte über die Spanne |
| A8 | **Kreiselnullpunkt versorgt**: der Nullpunkt des Kreisels muss geschätzt und abgezogen werden | Befund (Anhang F) | bis 3 °/s ohne Kalibrierung stabil | nichtlinear |
| A9 | **Takt und Rechenzeit**: unempfindlich gegen 100–500 Hz; eine Taktverzögerung ist eingerechnet | Teil IV | stabil bei 100 und 500 Hz | Eigenwerte |
| A10 | **Firmware = Modell**: was nachgewiesen ist, muss das Gerät auch rechnen | Grundsatz | Abweichung < 10⁻⁶ ° über 3000 Takte | `gegenprobe_lauf.py` |

## Die erste Anforderung: Aufrichten — aus der Übertragungsfunktion

Die Übertragungsfunktion der Strecke (Teil II) hat einen Pol rechts; der Regler muss ihn binden. Die Stellgröße ist eine Geschwindigkeit. Setzt man einen Regler in der Form

$$v = k_p\,\vartheta + k_i\!\int\!\vartheta\,\mathrm{d}t + k_d\,\dot\vartheta$$

an, so ist die Wagenbeschleunigung deren Ableitung,
$\ddot x = \dot v = k_p\dot\vartheta + k_i\vartheta + k_d\ddot\vartheta$.
Eingesetzt in die um $\vartheta = 0$, $s = 0$ linearisierte Gleichung
$J\ddot\vartheta = mgl\vartheta - ml\ddot x - d\dot\vartheta$ folgt

$$\boxed{\;(J + m l k_d)\,\ddot\vartheta
  + (m l k_p + d)\,\dot\vartheta
  + m l\,(k_i - g)\,\vartheta = 0\;}$$

Damit sind die Rollen vertauscht gegenüber dem, was man erwartet:

| Anteil | steht bei | Wirkung |
|---|---|---|
| $k_i$ | $\vartheta$ | **richtet auf** — die Rückstellung |
| $k_p$ | $\dot\vartheta$ | dämpft |
| $k_d$ | $\ddot\vartheta$ | wirkt wie zusätzliche Trägheit |

Nach Hurwitz ist ein System zweiter Ordnung genau dann stabil, wenn alle drei
Beiwerte dasselbe Vorzeichen haben. $J + m l k_d > 0$ und $m l k_p + d > 0$
sind unkritisch. Bleibt die eine Bedingung, die alles entscheidet:

$$\boxed{\;k_i > g = 9{,}81\ \frac{\mathrm{m/s}}{\mathrm{rad}}\;}$$

**Ohne Integralanteil im Winkelregler fällt das Fahrzeug immer**, gleich wie
groß $k_p$ und $k_d$ gewählt werden. Das ist keine Feinheit, sondern die
Kernaussage: bei geschwindigkeitsgeführtem Antrieb richtet nur der
Integralanteil auf.

Die Bedingung ist an drei laufenden Maschinen bestätigt:

| Fassung | $k_p$ | $k_i$ | $k_i > g$ | läuft |
|---|---|---|---|---|
| xxxx | 2,71 | 72,4 | ja | einwandfrei |
| Studenten | 1,28 | 34,0 | ja | ja |
| eigene Fassung | 5,27 | 27,8 | ja | ja |
| Umschreibung `segway_esp32.ino` | 3,71 | **0,015** | **nein** | nie erprobt |

Kennkreisfrequenz und Dämpfungsgrad folgen unmittelbar:

$$\omega_n = \sqrt{\frac{m l (k_i-g)}{J + m l k_d}},\qquad
  \zeta = \frac{m l k_p + d}{2\sqrt{(J + m l k_d)\,m l (k_i-g)}}$$

Mit den Beiwerten der Firmware ($K = 2,325$ m/s je rad, $T_n = 86,6$ ms, $T_v = 8,8$ ms, also $k_p = K$, $k_i = K/T_n = 26,84$, $k_d = K T_v = 0,0204$) und der gemessenen Strecke: $\omega_n = 11,36$ s⁻¹ (1,81 Hz), $\zeta = 0,787$ — ohne die Verzüge von Antrieb und Sensor; mit ihnen rechnet Teil VII.

## Die zweite Anforderung: der Pol bei $s = 0$ — warum es die Schicht 4 braucht

Im geschlossenen Kreis kürzt die Nullstelle $s = 0$ der Strecke den Integrator des Winkelreglers: aus $1 - G_u(s)\,C(s) = 0$ fällt der Faktor $s$ heraus, und eine Wurzel $s = 0$ bleibt als Eigenbewegung des Kreises stehen. Anschaulich: hält der Winkelregler die Neigung auf seinem Sollwert, ist jede **konstante** Fahrgeschwindigkeit mit diesem Zustand verträglich — der innere Kreis sieht sie nicht. Fällt der Sollwinkel nicht mit dem wahren Gleichgewichtswinkel zusammen, wächst die Geschwindigkeit sogar ohne Grenze. Für die übergeordnete Schicht wird deshalb ein zweiter Zusammenhang gebraucht:
wie hängt die Fahrgeschwindigkeit vom **Sollwinkel** ab?

Hält der innere Kreis den Winkel fest ($\ddot\vartheta = \dot\vartheta = 0$),
so verlangt die Bewegungsgleichung

$$\ddot x = g\,\frac{l\sin\vartheta + s\cos\vartheta}
                    {l\cos\vartheta - s\sin\vartheta}
        \;\approx\; g\left(\vartheta + \frac{s}{l}\right)
        = g\,(\vartheta - \vartheta_\mathrm{gl})$$

Die Strecke vom Sollwinkel zur Geschwindigkeit ist also ein **Integrator mit
der Verstärkung $g$**. Ein Winkelfehler von einem Grad erzeugt
$9{,}81 \cdot 0{,}0175 = 0{,}171$ m/s² dauernde Beschleunigung — nach zehn
Sekunden 1,7 m/s. Daran zeigt sich, warum ein Zehntelgrad Nullpunktfehler
nicht hinnehmbar ist, und daraus wird in Teil VI die äußere Schleife auf
$\omega_n = 1$ rad/s und $\zeta = 0{,}8$ ausgelegt:

$$g\,K = 2\zeta\omega_n,\qquad \frac{g\,K}{T_n} = \omega_n^2$$

Damit ist der Pol bei $s = 0$ gebunden: im 16-Zustands-Modell des Teils VII erscheint er als Eigenwert $z = 0{,}99936$ (Abklingzeit 6,2 s) — der langsamste des Kreises, und mit Absicht: die Nullpunktkorrektur darf die Kippregelung nicht stören.

## Die schwierige Stelle

Der Beschleunigungsmesser kann Neigung und Beschleunigung nicht
unterscheiden. Er misst die scheinbare Lotrichtung, und die kippt bei
waagerechter Beschleunigung um $\arctan(a/g)$:

| Beschleunigung | Scheinneigung |
|---|---|
| 0,5 m/s² | 2,9° |
| 1 m/s² | 5,8° |
| 2 m/s² | 11,5° |
| 4 m/s² | 22,2° |

Die Beschleunigung, die diesen Fehler erzeugt, ist die Stellgröße des
Reglers selbst. Über den Sensor läuft damit eine zweite, unerwünschte
Rückführung.

Mit den bisherigen Werten ($R_\mathrm{MEASURE} = 0{,}03$) ist der Filter mit
0,236 s Zeitkonstante **langsamer als das Fahrzeug kippt** (106,7 ms), und ein
Beschleunigungssprung steht nach 0,15 s zur Hälfte im Messwert. Die exakte
Eigenwertrechnung des abgetasteten Kreises ergibt dafür

$$|z|_\mathrm{max} = 1{,}0033$$

also einen langsam aufklingenden Grenzzyklus bei 0,48 Hz. Das deckt sich mit
dem, was die Simulation als Zittern meldete.

Zwei Wege beheben das:

| Weg | wirkt in | Trennung |
|---|---|---|
| A: $R_\mathrm{MEASURE}$ anheben, dem Kreisel mehr vertrauen | nur Schicht 1 | strikt gewahrt |
| B: die bekannte eigene Beschleunigung abziehen | Schicht 1 erhält einen Wert aus Schicht 3 | eine Verbindung entgegen der Reihenfolge |

Nach der Vorgabe „strikt trennen, wenn es das System nicht verschlechtert"
ist Weg A zu wählen, sofern er nicht schlechter ist. Der Abschnitt zur
Auslegung weiter unten zeigt, dass er es nicht ist.

## Was das Modell leistet und was nicht

Alle Zahlen dieses Berichts stammen aus zwei Modellen, die gegeneinander
geprüft sind.

**Nichtlineares Zeitmodell** (`Modell/segway_modell.py`). Strecke, Sensor,
alle vier Schichten, Begrenzungen, Rauschen. Geprüft gegen eine
Runge-Kutta-Lösung vierter Ordnung derselben Bewegungsgleichung: der Fehler
halbiert sich mit der Schrittweite, bei 32 Rechenschritten je Regeltakt
beträgt er 0,047 % über eine Viertelsekunde.

**Lineares Zustandsmodell des abgetasteten Kreises**
(`Modell/segway_entwurf.py`). Sechzehn Zustände: Strecke, Antriebsverzug,
Sensortiefpass, Kalman mit Winkel und Kreiselnullpunkt, alle vier Schichten,
eine Taktverzögerung. Aus den Eigenwerten folgt unmittelbar, ob der Kreis
stabil ist und mit welcher Reserve.

Beide stimmen auf 0,002 bis 0,1 % überein. Damit stehen die Eigenwertaussagen
nicht für sich.

Was das Modell **nicht** kann: es rechnet die Motorausgabe als stetige
Geschwindigkeit. Ob der Motor bei wenigen Hertz mechanisch singt, ob ein Rad
durchrutscht, ob der Untergrund nachgibt — das ist am Gerät zu prüfen.

## Zwei Befunde am vorhandenen Aufbau, die Anforderungen wurden

### Die Totzone erzeugt das Zittern, sie verhindert es nicht

`MIN_SPEED_HZ = 80` hält die Motoren unterhalb von 1,04 cm/s an. Das
erzeugt einen dauernden Grenzzyklus:

| `MIN_SPEED_HZ` | Grenzzyklus |
|---|---|
| 0 | 0,014° |
| 20 | 0,08° |
| 40 | 0,15° |
| 80 | 0,31° |

Eine Regelsperre um den Istwinkel — also nicht am Ausgang, sondern am
Eingang des Reglers — ist noch deutlich schlechter:

| Regelsperre | Grenzzyklus | mittlere Schrittfrequenz |
|---|---|---|
| keine | 0,014° | 6,5 Hz |
| 0,05° | 1,15° | 389 Hz |
| 0,50° | 2,29° | 398 Hz |

Innerhalb des Bandes ist der Kreis offen, das Fahrzeug fällt frei, und beim
Verlassen braucht es einen großen Ruck. Die Sperre verschlechtert das
Zittern um zwei Größenordnungen und lässt die Motoren sechzigmal mehr
arbeiten.

Im Quellcode von xxxx xxxx steht die Idee an drei Stellen, aber im
Balancierbetrieb ist keine davon wirksam: die eigentliche Sperre
(`pidOutput` ±20) ist auskommentiert, `disableL(sL < MAX_SPEED / 12000)`
ergibt bei Ganzzahlrechnung mit `#define MAX_SPEED 4000` genau null, und die
50-Hz-Sperre greift nur im Handbetrieb. Seine Maschine lief also ohne
Sperre — und lief ruhig.

Warum es bei ihm nicht zitterte, ergibt die Rechnung mit den Ursachen
einzeln zu- und abgeschaltet:

| Fall | Zittern |
|---|---|
| Aufbau Wystup mit Totzone 80 Hz | 0,307° |
| derselbe ohne Totzone | 0,014° |
| Schrittweite wie xxxx (0,066 mm statt 0,130 mm) | 0,160° |
| Mechanik wie xxxx (l = 0,28 m statt der am 25.08. angenommenen 0,12 m) | 0,240° |
| alles zusammen wie xxxx | 0,022° |

Der Hauptgrund ist die fehlende Sperre; halb so große Schrittweite und ein
träger Aufbau kommen hinzu.

Vorbehalt: das Modell rechnet die Motorausgabe als stetige Geschwindigkeit.
Ob der Motor bei wenigen Hertz mechanisch singt — der eigentliche Grund, aus
dem solche Sperren eingebaut werden — kann es nicht zeigen. Der Wert bleibt
deshalb in der Firmware einstellbar, steht aber auf null.

### Der Kreiselnullpunkt bleibt unversorgt

Die bisherige Firmware kalibriert beim Einschalten den Beschleunigungsmesser,
nicht aber den Kreisel. Der MPU6050 hat davon laut Datenblatt bis 20 °/s.

| Kreiselnullpunkt beim Start | Ergebnis |
|---|---|
| bis 3 °/s | wird vom Filter gefunden, bleibt stehen |
| ab 4 °/s | Sicherheitsabschaltung |

Der Kalman findet den Nullpunkt zwar selbst, braucht dafür aber rund
zwanzig Sekunden — und so lange steht der Fehler im gemeldeten Winkel. Die
neue Firmware misst ihn beim Start mit; aus 200 Messungen bleiben etwa
0,004 °/s übrig, und langsame Wärmedrift bis 2 °/s steckt der Filter weg.

### Der Regler forderte mehr, als die Motoren leisten

Beim Aufrichten aus 5 Grad fordert der Winkelregler bis 39,8 m/s²
Radbeschleunigung. `setAcceleration(50000)` entspricht 6,48 m/s². Über
dieser Grenze gehen Schritte verloren — und dann ist die ausgegebene
Frequenz **nicht mehr** die Radgeschwindigkeit. Damit fällt die Grundlage
der Schichten 3 und 4: der Weg, den die Motoreinheit meldet, hat mit dem
gefahrenen nichts mehr zu tun, und die Nullpunktkorrektur verschiebt den
Nullpunkt nach falschen Zahlen.

Die Abhilfe gehört in die Motoreinheit, nicht in den Regler: eine
Änderungsgrenze auf die ausgegebene Geschwindigkeit. Damit ist die
gemeldete Geschwindigkeit unter allen Umständen die wahre.

Mit der Änderungsgrenze ist die geforderte Beschleunigung immer genau die
zulässige und nie mehr:

| `A_MAX` | entspricht `setAcceleration` | Fangbereich | Stoß | tatsächlich gefordert |
|---|---|---|---|---|
| 3,0 m/s² | 23 150 | 9° | ≥ 0,2 Nm | 3,00 m/s² |
| 6,5 m/s² | 50 000 | 20° | ≥ 0,2 Nm | 6,48 m/s² |
| 10,0 m/s² | 77 166 | 23° | ≥ 0,2 Nm | 10,00 m/s² |
| 15,0 m/s² | 115 749 | 25° | ≥ 0,2 Nm | 15,00 m/s² |

Mit dem bisherigen `setAcceleration(50000)` ergibt der neue Regler 20 Grad
Fangbereich; der alte erreichte damit 9 Grad.

Der Zahlenwert `A_MAX` ist am Gerät zu messen — Frequenzrampe steigern, bis
der Motor stehenbleibt. Er ist keine Software-Einstellung, sondern eine
Eigenschaft von Motor, Treiber und Spannung.

\newpage

# TEIL VI — Der digitale Regler in vier Schichten

## Der Aufbau in vier Schichten

Das Blockschaltbild des ganzen Kreises steht in Teil I (Bild „Der modelltechnisch geschlossene Regelkreis“); hier die vier Schichten im Einzelnen.

    Schicht 1  Winkelerfassung
               Rohdaten des Sensors. Verarbeitung wahlweise im Baustein
               selbst oder außerhalb im Kalman-Filter. Übergeben wird ein
               sauberer Istwinkel mit der geforderten Dynamik und die um
               den Kreiselnullpunkt bereinigte Drehrate.

    Schicht 2  Winkelregler
               Bekommt den Istwinkel, gibt die Stellgröße aus. Die
               Stellgröße ist eine Radgeschwindigkeit in m/s.

    Schicht 3  Motoreinheit
               Setzt die Stellgröße dynamisch sauber um. Sie kennt als
               einzige den Zusammenhang zwischen Hertz und Metern und
               meldet deshalb Geschwindigkeit und Weg zurück, ohne dass
               ein Geber verbaut wäre.

    Schicht 4  Dynamische Nullpunktkorrektur, übergeordnet
               Fährt das Fahrzeug weg, obwohl null befohlen ist, stimmt
               der Nullpunkt nicht. Richtung und Betrag der Bewegung sind
               aus der Schrittfrequenz bekannt. Ein langsamer PI
               verschiebt den Nullpunkt der Schicht 1, bis Istwinkel null
               wirklich Stillstand bedeutet.

Die Reihenfolge ist fest. Jede Schicht kennt nur ihre Eingangsgrößen.
Sollwertvorgabe, Aufzeichnung und Bedienung greifen nicht ein: die Regelung
läuft als eigene Aufgabe auf Kern 1 in festem 4-ms-Takt, alles andere auf
Kern 0, und ausgetauscht werden nur fertige Zahlen.

## Die vier Schichten Zeile für Zeile — Modell und Firmware rechnen dasselbe

### Schicht 1: Winkelerfassung

Kalman-Filter mit dem Zustand (Winkel, Kreiselnullpunkt) in Grad und Grad/s,
Zeile für Zeile aus dem Sketch übernommen.

Prädiktion: $\hat\theta \leftarrow \hat\theta + \Delta t\,(\omega - \hat b)$;
$P_{00} \leftarrow P_{00} + \Delta t\,(\Delta t\,P_{11} - P_{01} - P_{10} + Q_\theta)$,
$P_{01} \leftarrow P_{01} - \Delta t\,P_{11}$, $P_{10} \leftarrow P_{10} - \Delta t\,P_{11}$,
$P_{11} \leftarrow P_{11} + Q_b\,\Delta t$.
Korrektur: $S = P_{00}+R$, $K_0 = P_{00}/S$, $K_1 = P_{10}/S$,
$y = \theta_\mathrm{acc} - \hat\theta$, $\hat\theta \leftarrow \hat\theta + K_0 y$,
$\hat b \leftarrow \hat b + K_1 y$, dann $P$ nachgeführt.

Beiwerte aus der Firmware: $Q_\theta = 0{,}001$, $Q_b = 0{,}003$,
$R = 309{,}30$. Das große $R$ ist Absicht: der Beschleunigungsmesser kann
Neigung und Beschleunigung nicht unterscheiden, also wird ihm wenig geglaubt.
Die stationären Verstärkungen (Riccati-Gleichung bis zum Stillstand
iteriert, im Gerät ebenso beim Start) sind
$K_0 = 1{,}2596\cdot10^{-3}$ und $K_1 = -1{,}9685\cdot10^{-4}$ je Takt; die
Zeitkonstante, mit der der Beschleunigungswinkel den Kreiselwinkel
nachzieht, ist $\Delta t/K_0 \approx 3{,}2$ s. Modell und Gerät starten den
Filter mit der eingeschwungenen Kovarianz, sonst hörte er vier Sekunden lang
nur dem Kreisel zu. Der Istwinkel ist $\hat\theta$ minus dem von Schicht 4
nachgeführten Nullpunkt; die Drehrate ist $\omega - \hat b$.

### Schicht 2: Winkelregler

PID in Normalform, Stellgröße eine Geschwindigkeit:

$$
v = K\Big(e + \frac{1}{T_n}\int e\,\mathrm dt + T_v\,\dot e\Big),\qquad e = \theta_\mathrm{ist} - \theta_\mathrm{soll},
$$

mit $K = 2{,}325385$ m/s je rad, $T_n = 86{,}638$ ms, $T_v = 8{,}766$ ms
(Firmware, gelesen). Der D-Anteil kommt unmittelbar von der Drehrate des
Kreisels — nichts wird differenziert. Der Integrator läuft in der Begrenzung
nicht weiter (Anti-Windup: nur wenn $|v_\mathrm{roh}| < v_\mathrm{max}$ oder
der Fehler dem Ausgang entgegenwirkt). Die Aufrichtbedingung aus Teil V,
$k_i = K/T_n > g$, ist mit 26,84 > 9,81 erfüllt: bei einer
geschwindigkeitsgeführten Strecke richtet der Integralanteil auf, der
P-Anteil dämpft nur.

### Schicht 3: Motorausgabe

Sollgeschwindigkeit → Schrittfrequenz. Erst die Änderungsgrenze
($|\Delta v| \le a_\mathrm{max}\Delta t$ je Takt), dann die Frequenzgrenze
(6000 Hz = 0,778 m/s), dann die Totzone (0 Hz — abgeschaltet, denn sie erzeugt
das Zittern, Teil VI). Gemeldet wird, was wirklich ausgegeben wird; daraus
folgen $v_\mathrm{aus}$ und der Weg ohne jeden Geber. Diese Schicht ist die
einzige, die Hertz und Meter je Sekunde ineinander umrechnet.

### Schicht 4: Nullpunktkorrektur

PI-Regler auf die Geschwindigkeit: $e_v = v_\mathrm{wunsch} - v_\mathrm{aus}$,
Nullpunkt $= K_N e_v + \frac{K_N}{T_{n,N}}\int e_v\,\mathrm dt$, begrenzt auf
±6°, mit $K_N = 0{,}081265$ rad je m/s und $T_{n,N} = 2{,}27226$ s (Firmware).
Sie verschiebt den Nullpunkt der Schicht 1 so lange, bis das Fahrzeug bei
Istwinkel null wirklich steht — der Gleichgewichtswinkel ist
$-\arctan(s/l)$, nicht die Senkrechte, und der Sensor kann den Unterschied
nicht sehen. Sie ist rund zehnmal langsamer als Schicht 2 und trägt den
langsamsten Eigenwert des Kreises (unten).

## Auslegung auf den schlechtesten Fall

Ein Entwurf, der nur im Nennfall stabil ist, taugt nichts: Masse,
Schwerpunkthöhe und Trägheitsmoment des Aufbaus sind nicht gemessen,
sondern geschätzt. Bewertet wurde deshalb die ganze Spanne:

| Größe | Spanne | Herkunft |
|---|---|---|
| Masse | 0,25 bis 0,50 kg | Manuskript nennt 0,35 |
| Schwerpunkthöhe | 0,08 bis 0,18 m | Manuskript nennt 0,12 |
| Trägheitsmoment | 0,7 bis 1,5 × Stabnäherung | nicht gemessen |
| Treiberverzug | 1 bis 6 ms | geschätzt |
| Sensoreinbauhöhe | 0 bis 0,10 m | nicht gemessen |

Jede Ecke dieser Spanne wird einzeln durchgerechnet, dazu der Nennfall —
33 Fälle je Entwurf. Ein Entwurf gilt nur dann als brauchbar, wenn er in
**jedem** dieser Fälle stabil ist. Unter den brauchbaren wird der mit der
größten Reserve gewählt, und zwar der **symmetrischen**:

- nach oben: um welchen Faktor dürfen alle Reglerbeiwerte steigen,
- nach unten: um welchen Faktor dürfen sie sinken,

bevor der Kreis instabil wird. Die Reserve nach unten ist bei dieser
Strecke die schärfere, weil unter $k_i = g$ das Aufrichten aufhört.

### Die Entscheidung zwischen Weg A und Weg B

Beide Wege wurden getrennt ausgelegt. Weg B führt die Güte der Kompensation
als zusätzliche Unsicherheit mit (0,6 bis 1,0), weil sie nicht bekannt ist.

Die Entscheidung fällt aber nicht an der Reserve, sondern an einer
Empfindlichkeit. Nimmt man den nach Weg A ausgelegten Regler und schaltet
die Kompensation nachträglich zu:

| Güte der Kompensation | Weg A, langsamer Filter (R = 30) | gleiche Beiwerte, schneller Filter (R = 0,03) |
|---|---|---|
| −1,0 (Vorzeichen verdreht) | instabil, 1,00096 | — |
| −0,5 | instabil, 1,00002 | — |
| 0 (aus) | stabil, 0,99907 | **instabil, 1,00451** |
| +0,5 | stabil, 0,99875 | — |
| +0,85 | stabil, 0,99877 | stabil, 0,99841 |
| +1,0 | stabil, 0,99897 | stabil, 0,99794 |
| +1,3 (Überkompensation) | stabil, 0,99919 | — |

Bei Weg A ist die Kompensation entbehrlich: sie ändert die Reserve in der
vierten Stelle. Beim schnellen Filter ist sie dagegen tragend — ohne sie
fällt der Kreis um.

Und sie bringt eine Fehlerquelle mit, die es sonst nicht gäbe: das
Vorzeichen hängt an der Einbaulage des Sensors. Ist es verdreht, wird aus
der Kompensation eine Mitkopplung, und der Kreis wird instabil. Bei Weg A
ist dieser Fall unmöglich, weil es die Verbindung gar nicht gibt.

Gewählt wird deshalb **Weg A**: langsamer Filter, keine Verbindung von
Schicht 3 zurück nach Schicht 1. Die strikte Trennung kostet nichts und
erspart eine Fehlermöglichkeit.

Der Preis ist ein träger Winkelmesswert — die Fusion hat bei R = 30 eine
Zeitkonstante von 1,75 s. Das ist unbedenklich, weil der Winkel im
Regelkreis vom Kreisel kommt und der Beschleunigungsmesser nur den langsamen
Nullpunkt stützt. Genau dafür ist er auch geeignet, und für nichts anderes.

### Die gewählten Beiwerte

Von 12 000 gewürfelten Entwürfen sind 5 297 in jeder Ecke der Spanne stabil.
Unter diesen wurde gewählt:

| Größe | Wert | Einheit |
|---|---|---|
| Winkelregler K | 2,3254 | m/s je rad |
| Winkelregler Tn | 86,64 | ms |
| Winkelregler Tv | 8,77 | ms |
| daraus $k_i = K/T_n$ | 26,84 | m/s je rad·s (Bedingung: > 9,81) |
| Nullpunktkorrektur K | 0,08126 | rad je m/s |
| Nullpunktkorrektur Tn | 2,2723 | s |
| Q_ANGLE / Q_BIAS | 0,001 / 0,003 | wie im bisherigen Code |
| R_MEASURE | 309,3 | statt bisher 0,03 |

Reserven im schlechtesten Fall der Spanne: die Beiwerte dürfen um den
Faktor 2,09 steigen und auf das 0,49-fache sinken, bevor der Kreis instabil
wird. Größter Eigenwertbetrag 0,99936.

Die Auswahlregel war die größte symmetrische Reserve. Davon wurde einmal
abgewichen, und zwar begründet: der Entwurf mit der größten Reserve (2,12)
hat eine dreimal langsamere Nullpunktkorrektur (Tn = 7,29 s). Er ist im
Modell stabil, fährt aber bei 5 mm Schwerpunktversatz 3,34 m weit, bevor er
steht. Der gewählte Entwurf braucht dafür 1,17 m.

| | größte Reserve | gewählt |
|---|---|---|
| symmetrische Reserve | 2,12 | 2,05 |
| Fangbereich | 20,5° | 20,5° |
| Stoßfestigkeit | 0,410 Nm | 0,420 Nm |
| Nullpunkttoleranz | 3,0 mm | 8,5 mm |
| Weg bei 5 mm Versatz | 3,34 m | 1,17 m |

Der Unterschied in der Reserve — drei Prozent — liegt unter der Auflösung
einer Zufallssuche. Der Unterschied im Weg liegt es nicht: drei Meter durch
den Raum zu fahren, bevor der Nullpunkt gefunden ist, ist am realen Aufbau
ein Fehler, auch wenn das Modell dazu „stabil" sagt.

Auffällig ist der Wert von R_MEASURE. Er ist tausendmal größer als bisher und
bedeutet, dass der Beschleunigungsmesser mit 0,13 Prozent je Takt in den
Winkel eingeht, die Fusion also eine Zeitkonstante von 3,2 s hat. Das ist
kein Versehen, sondern die Aussage des Entwurfs: **der Beschleunigungsmesser
taugt nicht zur Winkelmessung im Regelkreis, sondern nur zur Stützung des
langsamen Nullpunkts.** Den Winkel liefert der Kreisel.

## Worauf die neue Firmware beruht

Die Frage, welche der drei vorhandenen Fassungen der neuen zugrunde liegt,
hat eine zweigeteilte Antwort: die Hardwareschicht stammt vollständig aus
einer von ihnen, der Regelteil aus keiner.

### Übernommen aus `segway_esp32_Doku.ino`

Zeile für Zeile verglichen, findet sich das Folgende unverändert oder nur
umbenannt wieder:

| Bestandteil | Zustand |
|---|---|
| Pinbelegung: STEP 32/25, DIR 33/26, EN 14/27, I²C 21/22 | unverändert |
| Unmittelbarer Registerzugriff auf den MPU6050 (0x6B, 0x1B, 0x1C, 0x1A, Burst-Lesen ab 0x3B) | unverändert |
| Winkelformel $\arctan(a_y / \sqrt{a_x^2+a_z^2})$ | unverändert |
| Kalman-Filter mit den zwei Zuständen Winkel und Kreiselnullpunkt | Struktur unverändert, $Q_\vartheta$ und $Q_b$ unverändert, $R$ neu ausgelegt |
| FastAccelStepper mit `DRIVER_RMT`, `setDirectionPin`, `forceStopAndNewPosition` | unverändert |
| Nullpunktkalibrierung, 200 Messungen à 5 ms | übernommen, um den Kreisel erweitert |
| Sicherheitsabschaltung bei 30° | unverändert |
| Zwei Prozessorkerne mit `portMUX` | übernommen, Aufteilung geändert |
| Mitschnitt im Arbeitsspeicher | übernommen |

Aus der studentischen Fassung stammt **keine einzige Zeile** — sie enthält
keines dieser Elemente, weil sie über den Bewegungsprozessor und über
`ledcWriteTone` arbeitet. Von xxxx stammt mittelbar nur die Abschaltgrenze
von 30 Grad, die über die Doku-Fassung durchgereicht wurde.

### Neu

Der gesamte Regelteil: die vier Schichten, die Beiwerte in physikalischen
Einheiten, die Änderungsgrenze in der Motoreinheit, die Kalibrierung des
Kreiselnullpunkts, das eingeschwungene Starten der Fehlerkovarianz und
$R_\mathrm{MEASURE} = 309$ statt $0{,}03$. Nichts davon steht in einem der
Ausgangsprogramme; alles kommt aus der Auslegung am Modell.

### Die Herkunft der Nullpunktkorrektur

Der Gedanke selbst ist nicht neu. Er hat drei Vorläufer, die alle dieselbe
Frage beantworten wollten — was tun, wenn das Fahrzeug wegfährt, obwohl null
befohlen ist:

| Fassung | Umsetzung | Zustand |
|---|---|---|
| xxxx | `selfBalanceAngleSetpoint` und `positionErr` | beide im Quelltext vorhanden, **beide auskommentiert** |
| Studenten | äußerer PI-Geschwindigkeitskreis `piSpeedCalc` | eigene Zutat, neu erfunden, ohne Kenntnis des Vorgängers |
| eigene Doku-Fassung | Self-Balance-Drift, 0,0006° je Zyklus | die sparsamste, arbeitet aber nur mit dem Vorzeichen der Stellgröße |

Schicht 4 ist die vierte Fassung derselben Antwort. Sie unterscheidet sich in
drei Punkten von allen dreien: sie kennt Vorzeichen **und** Betrag der
Bewegung, sie ist aus der Streckenverstärkung ausgelegt statt eingestellt,
und sie ist die erste, die im Betrieb wirklich läuft, statt auskommentiert
dazustehen oder blind zu tasten.

In einem Satz: **Hardware und Sensorik aus der eigenen Vorgängerfassung, die
Regelung aus dem Modell, die Grundidee der Nullpunktkorrektur von xxxx — über
zwei Umwege.**

\newpage

## Was die Firmware anders macht

`Arduino/segway_regelung/segway_regelung.ino`, übersetzt mit
arduino-cli 1.5.2 und esp32:esp32 3.3.11 warnungsfrei, 81 % Programm-
speicher, 28 % Arbeitsspeicher.

| Punkt | bisher | jetzt | Grund |
|---|---|---|---|
| Beiwerte | Zahlen ohne Einheit, Abtastrate darin versteckt | K in m/s je rad, Tn und Tv in Sekunden | überleben Änderungen an Teilung, Radgröße und Takt |
| D-Anteil | Differenz des gefilterten Winkels | unmittelbar vom Kreisel | kein Differenzieren eines verrauschten Signals |
| Kalman-Start | P = 0 | eingeschwungener Endwert | sonst hört der Filter vier Sekunden lang nicht auf den Beschleunigungsmesser |
| Kreiselnullpunkt | nicht kalibriert | beim Start gemessen | ab 4 °/s fällt der Segway sonst |
| Nullpunkt | fester Schritt nach Vorzeichen (Self-Balance) | PI auf die gemeldete Geschwindigkeit | kennt Betrag und Vorzeichen statt nur das Vorzeichen |
| Nullpunkt nach Sturz | verworfen | bleibt stehen | er beschreibt die Mechanik, und die ändert sich nicht |
| Richtungsumkehr | am Motor | am Sensor | sonst zeigen Schicht 3 und 4 in die falsche Richtung |
| Änderungsgrenze | keine | in der Motoreinheit | sonst gehen Schritte verloren |
| Totzone | 80 Hz | 0 Hz, einstellbar | die Totzone erzeugt das Zittern |
| Rechenkerne | Regelung und Webserver auf Kern 1 | Regelung allein auf Kern 1, Bedienung auf Kern 0 | `loop()` liegt bei Arduino auf Kern 1 |
| Aufzeichnung | aus `loop()`, ungleiche Abstände | im Regeltakt, als Ganzzahl | ungleich getaktete Daten sind nicht auswertbar |
| Anti-Windup | keines | Integrator hält in der Begrenzung an | sonst Nachlaufen nach jedem Anschlag |

### Dauerlauf

Fünf Minuten, 2 mm Schwerpunktversatz, volles Rauschen:

| Größe | Wert |
|---|---|
| mittlere Neigung, letzte Minute | −0,9549° |
| berechneter Gleichgewichtswinkel | −0,9548° |
| Schwankung darum | 0,0060° Streuung, 0,030° Spitze-Spitze |
| Weg in den letzten 60 s | 2,4 mm |
| Schätzung des Kreiselnullpunkts | 0,0510 °/s bei wahren 0,050 |

Das Fahrzeug steht auf drei Hundertstel Grad genau auf seinem
Gleichgewichtswinkel, und der Filter hat den Kreiselnullpunkt auf ein
Prozent gefunden.

### Sensoraussetzer

Der Regeltakt bleibt bei 250 Hz, der Sensor liefert langsamer; der Regler
rechnet dann mit dem zuletzt gemeldeten Wert weiter.

| Sensorrate | Ergebnis | Zittern |
|---|---|---|
| 250 Hz | stabil | 0,018° |
| 200 Hz | stabil | 0,012° |
| 125 Hz | stabil | 0,010° |
| 100 Hz | stabil | 0,014° |
| 50 Hz | stabil | 0,023° |
| 25 Hz | stabil | 0,027° |

Selbst bei einem Zehntel der Rate bleibt der Kreis stabil. Einzelne
verlorene I²C-Züge sind damit unkritisch. Die Firmware sperrt trotzdem nach
fünf Fehlversuchen in Folge — nicht wegen der Regelung, sondern weil ein
dauerhaft stummer Sensor bedeutet, dass niemand mehr weiß, wo oben ist.

\newpage

# TEIL VII — Der geschlossene Regelkreis: Zustandsmodell, Simulation, Nachweis und Korrektur

## Der geschlossene Kreis als Zustandsmodell

Für die lineare Analyse (`segway_entwurf.py`) wird derselbe Rechenweg um die
aufrechte Lage linearisiert ($\sin\theta=\theta$, $\cos\theta=1$,
$\arctan(a/g)=a/g$, keine Begrenzungen) und als Abbildung eines
Zustandsvektors mit 16 Größen auf den nächsten Takt geschrieben:

| Nr. | Zustand | Nr. | Zustand |
|--:|:--|--:|:--|
| 0 | $\theta$ wahre Neigung | 8 | Nullpunktschätzung des Kalman |
| 1 | $\dot\theta$ | 9 | Integrator des Winkelreglers |
| 2 | $v$ Wagengeschwindigkeit | 10 | letzter Istwinkel |
| 3 | $a$ nach dem Tiefpass | 11 | geglätteter D-Anteil |
| 4 | $\dot\theta$ nach dem Tiefpass | 12 | Integrator der Nullpunktkorrektur |
| 5 | $\theta$ nach dem Tiefpass | 13 | ausgegebene Geschwindigkeit (ein Takt alt) |
| 6 | geglättete Eigenbeschleunigung | 14 | Weg |
| 7 | Winkelschätzung des Kalman | 15 | vorige Ausgabe |

Die Systemmatrix $A$ (16 × 16) entsteht, indem der linearisierte Taktschritt
auf jeden Einheitsvektor angewandt wird — es gibt keine zweite, von Hand
aufgestellte Matrix, die vom Simulator abweichen könnte. Zustände, die
mitlaufen, ohne zurückzuwirken (Weg, geglättete Beschleunigung ohne
Kompensation, alter Istwinkel bei D-Anteil vom Kreisel), werden vor der
Eigenwertrechnung abgetrennt, nachdem geprüft ist, dass ihre Spalte außer der
Diagonale leer ist. Stabil ist der Kreis, wenn alle Eigenwerte $|z|<1$
haben; die Abklingzeit des langsamsten Anteils ist $-T/\ln|z|_\mathrm{max}$.

Mit den gemessenen Zahlen (28.09.2026):

| Eigenwertpaar | Betrag | Abklingzeit | Frequenz | Zugehörigkeit |
|:--|--:|--:|--:|:--|
| 1 | 0,99936 | 6,22 s | 0,021 Hz | Nullpunktkorrektur (Schicht 4, $T_{n,N}$ = 2,27 s) |
| 2 | 0,99842 | 2,54 s | 0,112 Hz | Kalman-Nullpunkt und Weg |
| 3 | 0,96200 | 0,103 s | 1,34 Hz | die Kippbewegung selbst — Zeitkonstante in der Größe von $T$ = 106,7 ms |
| 4 | 0,42983 | 5 ms | — | Sensortiefpass und Antriebsverzug |

Die Verstärkungsreserve wird gemessen, indem alle Reglerbeiwerte ($K$ und
$K_N$) mit einem Faktor multipliziert werden, bis ein Eigenwert den
Einheitskreis erreicht (Bisektion): nach oben 2,43-fach, nach unten
0,459-fach. Ändert man die Strecke innerhalb ihrer Messunsicherheit
($T_p$ ± 0,004 s, $l$ 40–50 mm bei festem $J/(m l)$, $d$ bis 0,012 Nms), ändern
sich die Reserven in der dritten Stelle; nur ein Treiberverzug von 6 ms statt
2 ms drückt die obere Reserve auf 2,20 (Anhang E).

## Der geschlossene Kreis im Laplace-Bereich und in der z-Ebene

Bevor das vollständige Zustandsmodell des abgetasteten Kreises (oben) gerechnet
wird, lässt sich der Kreis mit Papier und Bleistift schließen. Der Winkelregler
der Schicht 2 lautet in Normalform $C(s) = K\,(1 + 1/(T_n s) + T_v s)$; der
Sensor wirkt für die schnelle Kippbewegung als Tiefpass $S(s) = 1/(1+\tau_\mathrm{lp} s)$
mit $\tau_\mathrm{lp} = 4{,}8$ ms (der Kalman-Filter mit $K_0 = 1,3·10⁻3 je Takt
folgt dem Kreisel praktisch verzögerungsfrei); die Strecke ist $G_u(s)$ aus
Teil II. Die langsame Schicht 4 bleibt hier außen vor.

![Der geschlossene Kreis im Laplace-Bereich.](Bilder/kreis_signalfluss.png)

Aus $1 - G_u(s)\,C(s)\,S(s) = 0$ folgt nach Ausmultiplizieren das
charakteristische Polynom

$$(1 + \tau_\mathrm{mot} s)(1 + \tau_\mathrm{lp} s)\,(J s^2 + d s - m g l)\,T_n
  \;+\; m l K\,(T_n T_v s^2 + T_n s + 1) = 0$$

vom Grad 4 — der Faktor $s$ von Zähler der Strecke und Integrator des Reglers
hat sich gekürzt (Teil V). Ohne die beiden Verzüge bleibt die Gleichung zweiter
Ordnung aus Teil V mit $\omega_n = 11,36$ s⁻¹ und $\zeta = 0,787$. Mit den
Verzügen und den gemessenen Zahlen lauten die Koeffizienten
5,2·10⁻9, 3,7·10⁻6, 6,4·10⁻4, 1,1·10⁻2, 8,2·10⁻2, und die Wurzeln sind:

| Wurzel im Laplace-Bereich | Eigenwert des 16-Zustands-Modells, $s = \ln z / T_a$ | Frequenz | Abstand |
|:--------------------|:--------------------|:--------------|------:|
| $-9,25 ± 7,64j$ | $-9,69 ± 8,40j$ | 1,91 / 2,04 Hz | 7,3 % |
| $-252,03$ | $-211,09$ | 40,11 / 33,60 Hz | 16,2 % |
| $-438,13$ | $-650,06$ | 69,73 / 103,46 Hz | 48,4 % |

Die **Kippbewegung** — das konjugierte Paar mit dem kleinsten Betrag — trifft das
vollständige Modell auf 7 Prozent: $1/|\mathrm{Re}\,s|$ = 108 ms
Abklingzeit gegen 103 ms, 1,22 Hz gegen 1,34 Hz. Die
beiden schnellen reellen Wurzeln (Antrieb und Sensortiefpass) weichen stärker
ab — dort wirken die Taktverzögerung um einen Schritt, der Kalman-Filter und der
Euler-Fehler der Antriebszeile (Teil II), alles Anteile, die nach wenigen
Millisekunden abgeklungen sind. Der Kreis aus vier Zeilen Rechnung sagt also die
Bewegung voraus, die man am Gerät sieht; das Zustandsmodell mit 16 Größen
liefert die Feinheiten und die Reserven.

![Wurzeln des Kreises: links in der s-Ebene (Strecke offen, Kreis nach Laplace, Eigenwerte des abgetasteten Modells zurückgerechnet), rechts in der z-Ebene mit dem Einheitskreis.](Bilder/kreis_wurzeln.png)

**Die Reserven.** Werden alle Reglerbeiwerte ($K$ und $K_N$) mit einem Faktor
multipliziert, bleibt der abgetastete Kreis zwischen dem 0,46-fachen und dem
2,40-fachen stabil (Bisektion: 0,459 und 2,43). Der Laplace-Kreis
vierten Grades kippt nach unten beim 0,36-fachen — dort geht $k_i$ gegen $g$ —,
nach oben aber bis zum Dreifachen nicht: **die obere Grenze setzt die Abtastung**
(Taktverzögerung und Halteglied), nicht die kontinuierliche Dynamik. Das ist der
Grund, warum die Auslegung in Teil VI am abgetasteten Modell und nicht an der
Übertragungsfunktion erfolgt.

![Größter Eigenwertbetrag über dem Faktor an den Reglerbeiwerten. Der abgetastete Kreis läuft im Nennbereich auf dem Eigenwert der Schicht 4 (0,99936); der Laplace-Kreis ohne Schicht 4 liegt darunter.](Bilder/kreis_reserven.png)

## Nichtlineare Nachprüfung

Die Eigenwerte gelten für den linearisierten Kreis. Frequenzbegrenzung,
Totzone, Änderungsgrenze, Rauschen, Kreiselnullpunkt und der
Schwerpunktversatz als echtes Moment sind unstetig oder nichtlinear und
werden am vollständigen Modell durchgefahren.

### Grenzen

| Prüfung | Ergebnis |
|---|---|
| Fangbereich aus der Ruhe (mit der Rampe 6,48 m/s²) | 22,0° |
| Sicherheitsabschaltung | 30° |
| Stoßfestigkeit über 50 ms | 0,520 Nm |
| Nullpunkttoleranz | 3,0 mm Schwerpunktversatz, entspricht 3,9° (Anschlag der Schicht 4: 6°) |
| größte geforderte Beschleunigung | 6,48 m/s² — genau die zulässige |
| größte Schrittfrequenz | 1957 Hz von 6000 |
| Kreiselnullpunkt beim Start | bis 3 °/s ohne Kalibrierung, mit Kalibrierung unkritisch |

Alle Zahlen dieses Abschnitts sind mit den **gemessenen** Streckengrößen
gerechnet (`Modell/nachweis_gemessen.py`, 28.09.2026); der Vergleich mit dem
Entwurf vom 25.08. steht weiter unten. Zum Vergleich: **ohne** Schicht 4 fällt
das Fahrzeug schon bei 0,05 mm Schwerpunktversatz (Tafel „Mit und ohne
Schicht 4“); mit ihr verträgt es 3 mm — sechzigmal so viel.

### Wann darf angefahren werden

Abgeschaltet wird bei 30 Grad, freigegeben aber nicht dort — der
Fangbereich beträgt 22 Grad. Würde bei 30 Grad wieder freigegeben, liefen
die Motoren an, während das Fahrzeug noch fällt.

Aus welchem Zustand es wirklich noch aufrichtet (a_max = 6,48 m/s²):

| Winkel \ Drehrate | 0 | 30 | 60 | 90 | 120 | 180 °/s |
|---|---|---|---|---|---|---|
| 0° | ja | ja | ja | ja | ja | ja |
| 2° | ja | ja | ja | ja | ja | ja |
| 5° | ja | ja | ja | ja | ja | nein |
| 8° | ja | ja | ja | ja | ja | nein |
| 10° | ja | ja | ja | ja | ja | nein |
| 15° | ja | ja | nein | nein | nein | nein |
| 20° | ja | nein | nein | nein | nein | nein |

Die Firmware gibt frei, wenn eine halbe Sekunde lang beides gilt:
Winkel unter 5 Grad und Drehrate unter 60 °/s. Bei 5 Grad reicht es bis
120 °/s — also Faktor zwei Reserve. In der Handhabung heißt das: Fahrzeug
aufrichten, kurz ruhig halten, dann übernimmt es.

### Die Forderung „Istwinkel null, also keine Bewegung"

Nach 60 s eingeschwungen, gemessen über die letzten 20 s:

| Größe | Wert |
|---|---|
| zurückgelegter Weg in 20 s | 1,6 mm |
| mittlerer Istwinkel | 0,00004° |
| Streuung des Istwinkels | 0,0017° |
| mittlere Geschwindigkeit | 0,08 mm/s |

Der nachgeführte Nullpunkt trifft dabei den berechneten
Gleichgewichtswinkel: bei 2 mm Schwerpunktversatz läuft er auf −2,586°,
und $-\arctan(2\,\mathrm{mm}/44{,}5\,\mathrm{mm}) = -2{,}575°$; der Rest von
0,011° ist der verbliebene Kreiselnullpunkt.

### Schicht 4 findet den berechneten Gleichgewichtswinkel

| Schwerpunktversatz | berechnet | gefunden | Weg bis zum Stehen |
|---|---|---|---|
| 0,5 mm | −0,6441° | −0,6550° | 0,32 m |
| 1,0 mm | −1,2880° | −1,2989° | 0,63 m |
| 2,0 mm | −2,5747° | −2,5856° | 1,26 m |
| 4,0 mm | −5,1391° | fällt (Anschlag 6° reicht nicht) | — |

Der Rest von 0,011° ist der verbliebene Kreiselnullpunkt. Das Wandern
während der Suche ist genau das, was am laufenden Gerät zu sehen war — mit
dem Unterschied, dass es hier nach knapp einer Minute an einem festen Punkt
endet.

### Mit und ohne Schicht 4

Gleicher Versatz, 40 s:

| Versatz | ohne Korrektur | mit Korrektur |
|---|---|---|
| 0,05 mm | fällt (nach 2,98 m) | steht, 0,03 m |
| 0,10 mm | fällt (2,47 m) | steht, 0,06 m |
| 0,20 mm | fällt (1,76 m) | steht, 0,13 m |
| 0,50 mm | fällt (1,15 m) | steht, 0,31 m |
| 1,00 mm | fällt (0,81 m) | steht, 0,63 m |
| 2,00 mm | fällt (0,56 m) | steht, 1,26 m |
| 5,00 mm | fällt (0,33 m) | fällt (0,47 m) |

Ein halber Millimeter ist die Genauigkeit, mit der ein Akku sitzt oder ein
Kabel liegt. Ohne Schicht 4 ist das Fahrzeug damit nicht betreibbar; mit ihr
braucht es bei 44,5 mm Schwerpunkthöhe 0,3 m Fahrweg je halben Millimeter, bis
der Nullpunkt gefunden ist — deshalb die Empfehlung in „Korrektur der
Reglerparameter“, den gefundenen Nullpunkt im Gerät zu speichern.

### Rauschen

Die beiden folgenden Tafeln (Rauschen, Abtastrate) stammen aus dem Nachweis vom
25.08. mit den damals geschätzten Streckengrößen; sie sind mit den gemessenen
Zahlen noch nicht wiederholt (offene Aufgabe F8). Die Aussage — der Kreis bleibt
über zwanzigfaches Rauschen und ein Verhältnis 1 : 5 in der Abtastrate stabil —
hängt nicht an der dritten Stelle der Streckengrößen.

| Winkelrauschen | Kreiselrauschen | Zittern | mittlere Schrittfrequenz |
|---|---|---|---|
| 0 | 0 | 0,000° | 0 Hz |
| 0,05° | 0,05 °/s | 0,014° | 6,4 Hz |
| 0,20° | 0,20 °/s | 0,057° | 25,6 Hz |
| 0,50° | 1,00 °/s | 0,271° | 123 Hz |
| 1,00° | 3,00 °/s | 0,801° | 368 Hz |

Erwartet werden die Werte der zweiten Zeile. Auch bei zwanzigfachem
Rauschen bleibt der Kreis stabil, das Zittern wächst nur mit.

### Fahrbefehl

| befohlen | erreicht | dabei Neigung |
|---|---|---|
| 0,063 m/s | 0,064 m/s | 0,001° |
| 0,126 m/s | 0,127 m/s | 0,002° |
| 0,251 m/s | 0,252 m/s | 0,004° |
| 0,377 m/s | 0,378 m/s | 0,005° |

### Abtastrate

Beiwerte unverändert, nur der Takt geändert:

| Takt | Fangbereich | Zittern |
|---|---|---|
| 100 Hz | 20,0° | 0,015° |
| 125 Hz | 20,0° | 0,016° |
| 200 Hz | 20,5° | 0,021° |
| 250 Hz | 20,5° | 0,018° |
| 333 Hz | 20,5° | 0,015° |
| 500 Hz | 21,0° | 0,009° |

Derselbe Regler läuft über ein Verhältnis von 1 zu 5 in der Abtastrate ohne
jede Anpassung. Das ist der Lohn der physikalischen Einheiten — bei der
alten Fassung fiel der Segway bereits um, wenn man nur die
Mikroschrittteilung änderte.

Daraus folgt zugleich, dass der Schwankungsbereich des Regeltakts unkritisch
ist: `vTaskDelayUntil` hält den Mittelwert von 4 ms genau, der einzelne
Abstand schwankt um bis zu einen FreeRTOS-Takt, also 25 Prozent. Das liegt
weit innerhalb der geprüften Spanne. Gerechnet wird trotzdem mit der
wirklichen Schrittweite aus der Uhr.

## Bilder

![Aufrichten aus 5 Grad bei 2 mm Schwerpunktversatz, gemessene Streckengrößen. Oben Neigung und nachgeführter Nullpunkt gegen den berechneten Gleichgewichtswinkel −2,575°, darunter Schrittfrequenz und Weg.](Modell/gemessen_2026-09-28/gemessen1_aufrichten.png)

![Schicht 4 findet den Gleichgewichtswinkel. Gepunktet der berechnete Wert $-\arctan(s/l)$ für jeden Schwerpunktversatz.](Modell/gemessen_2026-09-28/gemessen2_nullpunkt.png)

![Ein Millimeter Schwerpunktversatz, mit und ohne Nullpunktkorrektur. Ohne sie fällt das Fahrzeug nach 0,8 m.](Modell/gemessen_2026-09-28/gemessen3_vergleich.png)

## Der Nachweis mit den gemessenen Streckengrößen (28. September 2026)

Alle Streckengrößen dieses Manuskripts waren bis zum 28. September geschätzt (0,25–0,50 kg, Schwerpunkt
0,08–0,18 m); der Entwurf in Teil VI wurde deshalb auf die ganze Spanne ausgelegt, Kippzeitkonstante 87 bis
191 ms. Am 28. September wurden gewogen und gemessen: Masse 1,248 kg; Spurweite 143 mm, Reifenbreite
26,5 mm, Raddurchmesser 64 mm; Sensor 71 mm über der Achse und 39 mm nach vorn; Akkubügel 134 mm über der Achse; und — als die
eine Größe, die in der Kippdynamik steht — die Schwingungsdauer des um die Radachse hängenden Aufbaus
(Räder festgehalten, Motoren stromlos, Handyvideo, Bildauswertung mit Merkmalspunkten und RANSAC):

$$T_p = 0{,}6702 \pm 0{,}0041\ \mathrm{s} \quad\Rightarrow\quad T = \frac{T_p}{2\pi} = \sqrt{\frac{J}{m\,g\,l}} = 106{,}7\ \mathrm{ms}, \qquad \frac{J}{m\,l} = g\left(\frac{T_p}{2\pi}\right)^2 = 111{,}6\ \mathrm{mm}.$$

Die Rechnung aus der Konstruktion (STL-Dateien, gewogene Massen von Gesamtgerät und Akku) hatte zuvor
0,666 s und 105,9 ms ergeben — zwei unabhängige Wege, Abweichung 0,6 %. Ein erstes Video mit dem
Fahrzeug an einer von Hand gehaltenen Schnur war dagegen ein Doppelpendel (Perioden 1,013 s und 0,510 s im
Verhältnis 1,99) und ließ nur eine Spanne zu; es ist in `Konstruktion/MASSE_UND_GEWICHTE.md` dokumentiert.

Mit diesen Zahlen wurde der Nachweis aus Teil VII unverändert wiederholt (`Modell/nachweis_gemessen.py`,
Programme aus Anhang D unverändert; Beiwerte aus der Firmware gelesen; Ergebnisse in
`Modell/gemessen_2026-09-28/`, Blatt `NACHWEIS_gemessen_2026-09-28.pdf`):

| Prüfung | 25.08. (geschätzt) | 28.09. (gemessen) |
|---|---|---|
| Kippzeitkonstante | 127,7 ms | 106,7 ms |
| größter Eigenwertbetrag / Abklingzeit | 0,9994 / 6,22 s | 0,9994 / 6,22 s (Schicht 4, nicht die Strecke) |
| Verstärkungsreserve nach oben / unten | 2,46 / 0,453 | 2,43 / 0,459 |
| Fangbereich aus der Ruhe | 20,5° | 22,0° |
| Stoßfestigkeit über 50 ms | 0,420 Nm | 0,520 Nm |
| Nullpunkttoleranz | 8,5 mm (4,1°) | 3,0 mm (3,9°) |
| Weg bis zum Stehen bei 1 mm Schwerpunktversatz | 0,23 m | 0,63 m |
| größte Schrittfrequenz | 2083 Hz | 1957 Hz |
| Istwinkel null → Stillstand, 20 s | 1,6 mm | 1,6 mm |

Der Regler bleibt: stabil, dieselben Reserven, größerer Fangbereich. Was sich ändert, ist der Maßstab des
Schwerpunktversatzes — bei 44,5 mm Schwerpunkthöhe ist 1 mm Versatz schon 1,3°, die Schicht 4 verträgt
3 mm und braucht dafür 0,3 m Fahrweg je 0,5 mm. Für den Prüfstand heißt das: entweder ±0,5 m Fahrweg oder
den gefundenen Nullpunkt im Gerät speichern und beim Start vorgeben. Der Anschlag des Sollwinkels (6°)
kann auf 10° gesetzt werden, ohne den Fangbereich zu berühren — eine Entscheidung für die Neueinstellung
am Gerät. Nicht gerechnet, weil nicht gemessen: die Beschleunigungsgrenze der Motoren mit 1,25 kg (die
Rampe 6,48 m/s² verlangt 0,27 Nm an beiden Rädern zusammen), der Treiberverzug und das Sensorrauschen.

## Korrektur der Reglerparameter

Der Regler wurde auf die Spanne der geschätzten Strecke ausgelegt (Teil VI); die
Messungen vom 28.09.2026 setzen die Strecke in diese Spanne hinein
(Kippzeitkonstante 106,7 ms bei 87–191 ms). Der Nachweis mit den gemessenen
Zahlen (Abschnitt oben) sagt, was zu korrigieren ist und was nicht:

| Größe | Befund am Modell mit gemessener Strecke | Korrektur |
|:--|:--|:--|
| Beiwerte K, Tn, Tv des Winkelreglers | Kreis stabil, Reserven 2,43 / 0,459 wie im Entwurf; Fangbereich 22,0°, Stoß 0,52 Nm — größer als am 25.08. | **keine**: die Beiwerte bleiben; die Kippdynamik hängt nur an $J/(m l)$, und das liegt mitten in der ausgelegten Spanne |
| Anschlag des Sollwinkels der Schicht 4 (6°) | bei 44,5 mm Schwerpunkthöhe entspricht 1 mm Versatz 1,3°; 3 mm sind die Grenze, 4 mm fallen | **6° → 10°** prüfen (D5): der Fangbereich 22,5° lässt es zu; Wirkung am Modell nachweisen, dann in die Firmware (C5) |
| Nullpunkt beim Start | Schicht 4 braucht 0,3 m Fahrweg je 0,5 mm Versatz, bis der Nullpunkt gefunden ist | **gefundenen Nullpunkt im Gerät speichern** und beim Start vorgeben (C5); bis dahin ±0,5 m Fahrweg am Prüfstand |
| Schrittweite | Firmware rechnete mit Ø 66 mm, gemessen 64 mm | **erledigt 28.09. abends**: `RAD_DURCHMESSER` 0,064, übersetzt, Gegenprobe Firmware = Modell wiederholt; Fangbereich 22,0° statt 22,5°, größte Schrittfrequenz 1957 Hz |
| Rampe 6,48 m/s² | die Rampe der Firmware; ob die Motoren sie mit 1,25 kg halten, ist nicht gemessen | Rampentest am Gerät (`/rampentest`), dann A_MAX setzen (F3) |
| Treiberverzug, Rauschen | angenommen 2 ms, 0,05°; Empfindlichkeit gerechnet (6 ms drückt die obere Reserve auf 2,20) | aus dem Mitschnitt messen (F4, F5) |

Die eigentliche Korrekturschleife schließt sich am Gerät: die Stoßantwort des
stehenden Fahrzeugs (Prüfstand, Teil VIII) liefert Eigenfrequenz und Dämpfung
des realen Kreises; das Modell sagt sie voraus (1,34 Hz mit 0,10 s
Abklingzeit für die Kippbewegung, 0,11 Hz mit 2,5 s für Nullpunkt und Weg).
Stimmen sie, ist das Modell belegt und die Beiwerte folgen aus ihm; weichen sie
ab, nennt die Abweichung die falsch angenommene Größe. Erst dann wird an den
Beiwerten gedreht — nicht am Gerät nach Gefühl, sondern im Modell mit
derselben Auslegung wie in Teil VI.

## Wie das Modell geprüft ist

Ein Modell, das nur behauptet, ist nichts wert; jeder Baustein hat eine
unabhängige Gegenprobe:

| Baustein | Gegenprobe | Ergebnis |
|:--|:--|:--|
| Mechanik (explizit, 32 Feinschritte je Takt) | Runge-Kutta 4. Ordnung derselben Gleichung | 0,068 % über 0,2 s; mit 8 Feinschritten 1 % (deshalb 32) |
| Vollständigkeit der Gleichung | Glied $+m\,a\,s\sin\theta$ mitgeführt statt genähert | 0,06–0,13 % — klein, aber vorhanden (Vorfall 26.09.: veraltete Tafel H.2) |
| lineares Zustandsmodell | gegen die nichtlineare Simulation bei 0,02° Anfangsneigung | 0,001–0,1 % über 4 s |
| Firmware | Rechenweg der Firmware ein zweites Mal unabhängig aufgeschrieben (`gegenprobe_firmware.py`), Beiwerte aus dem Quelltext gelesen, dieselben Eingänge | 1,1·10⁻⁸ Grad über 3000 Takte |
| Strecke gegen das Gerät | Radpendel-Video gegen die Konstruktion | 106,7 gegen 105,9 ms, zwei Wege |
| Sensormodell | Datenblatt (Gruppenlaufzeit), Bibliothek (Raten) | keine Schätzung mehr in der Sensorkette außer Rauschen und Nullpunkt |

Was das Modell nicht enthält und warum: Schrittquantisierung und
Schrittverlust als Ereignis (F2, F3), Elastizität der Reifen, Spiel in den
Naben, Rechenzeitschwankungen des ESP32 (F4), das Rastmoment der Motoren im
Betrieb (bestromt entfällt es), die Dynamik des Prüfstands (Fangleine,
Führungsleisten). Alles davon ist am Gerät messbar und kommt mit der
Stoßantwort (D4) als Beleg.

## Wie weit die Aussagen tragen

Die Kette der Nachweise ist so aufgebaut, dass jede Stufe die vorige stützt:

1. Das Streckenmodell trifft eine Runge-Kutta-Lösung derselben
   Bewegungsgleichung auf 0,047 % über eine Viertelsekunde.
2. Das lineare Zustandsmodell und das nichtlineare Zeitmodell liefern
   denselben Verlauf auf 0,002 bis 0,1 %.
3. Die Auslegung fordert Stabilität in jeder Ecke der Unsicherheitsspanne,
   nicht nur im Nennfall.
4. Der gewählte Entwurf wird am vollständigen nichtlinearen Modell
   nachgefahren.
5. Die Firmware wurde unabhängig ein zweites Mal in Python aufgeschrieben —
   die Beiwerte werden dabei aus dem Quelltext gelesen, nicht abgeschrieben —
   und rechnet auf 10⁻⁸ Grad dasselbe wie das Modell.

Damit gilt: **was das Modell sagt, sagt es auch über das Gerät** — soweit das
Modell die Wirklichkeit trifft.

Und da bleiben Lücken, die ehrlich zu benennen sind:

| Nicht im Modell | Warum es zählt |
|---|---|
| Die Motorausgabe wird als stetige Geschwindigkeit gerechnet, nicht als Folge einzelner Schritte | Ob der Motor bei wenigen Hertz singt oder rastet, ist nicht zu sehen. Genau darum gibt es Totzonen. |
| Radschlupf und Untergrund | Bei Schlupf ist die Frequenz nicht mehr die Geschwindigkeit — die Grundlage der Schichten 3 und 4 |
| Massenverteilung als starrer Körper | Ein weicher Aufbau schwingt zusätzlich mit |
| Motorvibration auf dem Sensor | Sie liegt unmittelbar auf dem Beschleunigungsmesser; der 42-Hz-Tiefpass ist im Modell, ihre Amplitude nicht |
| Rechenzeit der Regelschleife | Als Frist angenommen, am Gerät zu messen (die Anzeige gibt sie aus) |
| Masse, Schwerpunkthöhe, Trägheitsmoment | Geschätzt. Der Entwurf ist über eine weite Spanne ausgelegt, aber die Spanne ist eine Annahme. |

Der Entwurf ist so gebaut, dass er diese Lücken verträgt: er ist über eine
Spanne von Faktor zwei in Masse, Schwerpunkthöhe und Trägheitsmoment stabil,
über ein Verhältnis von 1 zu 5 in der Abtastrate, und bei zwanzigfachem
Rauschen. Das ersetzt die Messung nicht, aber es macht sie zur Bestätigung
statt zur Voraussetzung.

\newpage

# TEIL VIII — Inbetriebnahme, Prüfstand und offene Messungen

## Inbetriebnahme am Gerät

Die Reihenfolge ist wichtig — jeder Schritt setzt den vorigen voraus.

**1. Aufspielen.** Ordner `Arduino/segway_regelung`, Board „ESP32 Dev
Module", 115200 Baud, Partitionsschema mit OTA. Steht das Fahrzeug im Netz,
gehen weitere Übertragungen über OTA unter dem Namen `segway`.

*Falle aus dem letzten Mal:* liegt neben `MPU6050` noch ein Ordner
`I2Cdev` in `Documents\Arduino\libraries`, bricht das Binden mit
„multiple definition" ab. Diese Fassung braucht **keine** MPU-Bibliothek —
sie spricht den Baustein unmittelbar an.

**2. Motoren aus, Sensor prüfen.** Treiber stromlos lassen (Stecker ab),
Fahrzeug von Hand neigen und im Browser den Istwinkel beobachten. Er muss
dem tatsächlichen Winkel folgen, und er muss beim Vorwärtsneigen **positiv**
werden. Wird er negativ, ist die Schaltfläche „Richtung" zu betätigen —
das dreht den Sensor, nicht den Motor, und ist die einzige richtige Stelle
dafür.

**3. Rechenzeit ablesen.** Die Anzeige „Rechenzeit je Takt" muss deutlich
unter 4000 µs liegen. Erwartet werden rund 500 bis 900 µs, davon etwa 400
für den I²C-Zug.

**4. Größte Beschleunigung messen — siehe den folgenden Abschnitt.** Das ist die
einzige Zahl, die nicht aus dem Modell kommen kann.

**5. Nullpunkte messen.** Beim Einschalten hält man das Fahrzeug eine
Sekunde lang senkrecht und **ruhig** — gemessen werden Senkrechte und
Kreiselnullpunkt. Ruhig ist wichtiger als senkrecht: die Senkrechte findet
Schicht 4 nach, den Kreiselnullpunkt nicht.

**6. Erster Balancierversuch, festgehalten.** Freigabe erteilen, Fahrzeug an
der Oberkante lose führen. Beobachten:

- Der Istwinkel muss um null pendeln, nicht davonlaufen.
- Der angezeigte Nullpunkt wandert in den ersten zwanzig Sekunden langsam
  auf einen festen Wert zu. Das ist Schicht 4 bei der Arbeit. Bleibt er bei
  null stehen, obwohl das Fahrzeug wegfährt, stimmt das Vorzeichen nicht.
- Der Weg darf sich nicht dauernd in eine Richtung vergrößern.

**7. Freistehend.** Erst wenn Schritt 6 sauber läuft.

**8. Mitschnitt.** Schaltfläche „Mitschnitt", 30 s stehen lassen, dann kommt
die Tabelle über die serielle Schnittstelle. Damit lässt sich das Modell
gegen das Gerät abgleichen — bis dahin sind Masse, Schwerpunkthöhe und
Trägheitsmoment geschätzt.

### Die Messung von A_MAX

`A_MAX` ist die größte Beschleunigung, die die Räder wirklich annehmen, ohne
dass Schritte verloren gehen. Sie ist keine Softwareeinstellung, sondern eine
Eigenschaft von Motor, Treiber, Spannung und Radträgheit.

Sie ist deshalb im Betrieb verstellbar, damit sie sich messen lässt, ohne für
jeden Versuch neu aufzuspielen.

**Vorgehen**

1. Fahrzeug auf den Rücken legen, Räder frei drehbar, „Halt" drücken.
2. Im Browser den Schieber „A_MAX" auf einen kleinen Wert stellen, etwa
   2 m/s². Er wirkt sofort; alternativ `/rampe?a=2.0` aufrufen.
3. „Rampentest" drücken. Die Motoren fahren dann zehnmal von +0,2 m/s auf
   −0,2 m/s und zurück, mit genau dieser Beschleunigung, unter Umgehung der
   vier Schichten. Alternativ `/rampentest?a=2.0&v=0.2`.
4. Zuhören und zusehen. Solange der Motor sauber durchdreht, ist der Wert
   zulässig. Sobald er beim Richtungswechsel rasselt, stehenbleibt oder
   hörbar Schritte verliert, ist die Grenze überschritten.
5. Den Wert schrittweise erhöhen und Schritt 3 wiederholen, bis das
   eintritt. Vom letzten sauberen Wert **20 Prozent abziehen** — die
   Reserve ist für Last, warme Motoren und schwächere Akkuspannung.
6. Den gefundenen Wert in `A_MAX_VORGABE` im Quelltext eintragen, damit er
   das Einschalten überlebt.

**Was davon abhängt — und was nicht**

Die Reglerbeiwerte hängen nicht davon ab. Über die ganze Spanne von 1,5 bis
25 m/s² bleiben Restzittern und Nullpunkttoleranz unverändert; nur der
Fangbereich wandert mit:

Die folgende Tafel stammt aus dem Nachweis vom 25.08. mit den damals geschätzten Streckengrößen (Fangbereich 20,5° statt 22,0° heute); sie zeigt die Abhängigkeit von der Rampe, nicht die heutigen Absolutwerte.

| A_MAX | `setAcceleration` | Fangbereich | Stoßfestigkeit | Restzittern | Nullpunkttoleranz |
|---|---|---|---|---|---|
| 1,50 m/s² | 11 575 | 3,5° | 0,13 Nm | 0,010° | 8,5 mm |
| 2,00 m/s² | 15 433 | 4,5° | 0,18 Nm | 0,010° | 8,5 mm |
| 3,00 m/s² | 23 150 | 7,0° | 0,29 Nm | 0,010° | 8,5 mm |
| 4,00 m/s² | 30 867 | 16,5° | 0,34 Nm | 0,010° | 8,5 mm |
| 6,48 m/s² | 50 004 | 20,5° | 0,42 Nm | 0,010° | 8,5 mm |
| 10,00 m/s² | 77 166 | 23,5° | 0,42 Nm | 0,010° | 8,5 mm |
| 15,00 m/s² | 115 750 | 25,5° | 0,42 Nm | 0,010° | 8,5 mm |
| 25,00 m/s² | 192 916 | 27,0° | 0,42 Nm | 0,010° | 8,5 mm |

`A_MAX` zu ändern heißt also, den Fangbereich zu ändern — nicht, neu auslegen
zu müssen. Das ist die praktische Folge davon, dass die Beiwerte in
physikalischen Einheiten stehen.

Der Sprung zwischen 3 und 4 m/s² ist die Stelle, an der die Rampe aufhört,
das Aufrichten zu begrenzen. Oberhalb von 10 m/s² wird kaum noch etwas
gewonnen, weil dann die Frequenzgrenze wirkt und nicht mehr die Rampe.

**Die Gegenprobe im Betrieb**

Die Bedienseite zeigt „gefordert (Spitze)": die größte Beschleunigung, die
der Regler seit dem letzten Zurücksetzen verlangt hat. Nach einem
Balancierversuch gilt:

- liegt sie deutlich unter `A_MAX`, ist Reserve da;
- liegt sie dauernd genau auf `A_MAX`, begrenzt die Rampe das Aufrichten —
  dann lohnt es, `A_MAX` zu erhöhen, sofern die Motoren es hergeben;
- lässt sich `A_MAX` nicht weiter erhöhen, ist der Fangbereich mechanisch
  ausgereizt. Dann hilft nur ein stärkerer Motor, eine höhere Spannung oder
  ein leichteres Rad.

Am Modell fordert der Regler beim Aufrichten aus 5 Grad bis zu 40 m/s², wenn
man ihn ließe. Die Begrenzung in der Motoreinheit sorgt dafür, dass er nie
mehr verlangt, als die Räder annehmen — und nur deshalb bleibt die
ausgegebene Frequenz die wahre Radgeschwindigkeit, auf der Schicht 3 und
Schicht 4 beruhen.

## Der Hardwaretest: Kamera, Synchron-LED, Bildauswertung und das Nachziehen des Reglers

Das Modell sagt voraus, wie sich der Kreis bewegt (Teil VII: Kippbewegung mit
Eigenfrequenz und Abklingzeit, Nullpunktkorrektur mit ihrer Zeitkonstante). Der
Hardwaretest misst genau diese Größen am Gerät, mit zwei voneinander
unabhängigen Winkelmessungen, und schließt daraus die Schleife zurück auf die
Beiwerte. Das Bild zeigt den Ablauf; die Abschnitte darunter nennen jeden
Schritt mit seinem Mittel.

![Der Hardwaretest als Schleife: Prüfstand, Kamera und Mitschnitt, gemeinsame Zeitachse über die LED, Vergleich mit dem Modell, Neueinstellung.](Bilder/hardwaretest_ablauf.png)

**Aufbau.** Das Fahrzeug steht auf dem Prüfstand (Abschnitt „Der Prüfstand und
die Maße“) an der Fangleine zwischen den Führungsleisten; der Fahrweg muss die
Nullpunktsuche zulassen (0,3 m je 0,5 mm Schwerpunktversatz, Teil VII). Die
Laptop-Kamera steht seitlich in Achshöhe und fest; der Maßstab im Bild kommt
aus dem Raddurchmesser $2r$, der Drehwinkel braucht ihn nicht.

**Zeitmarke.** Der Befehl `/log` startet den Mitschnitt mit $f_\mathrm{log}$
(Spalten: Zeit, Istwinkel, Drehrate, Schrittfrequenz, Nullpunkt, `led`) und
lässt die Synchron-LED an GPIO 23 dreimal blitzen (12 Takte an, 38 aus). Der
Blitz steht im Video als hellster Bildpunktbereich und im Mitschnitt als Spalte
`led`; aus beiden folgt der Zeitversatz $\Delta t$ zwischen Kamera und ESP32
auf ein Bild genau. Damit liegen $\theta_\mathrm{ist}(t)$ des Kalman-Filters
und $\theta_\mathrm{cam}(t)$ der Kamera auf derselben Zeitachse.

**Bildauswertung.** Je Bild werden Merkmalspunkte (AKAZE) auf dem Aufbau
gefunden und gegen ein Bezugsbild mit einer Ähnlichkeitstransformation
(RANSAC) verglichen; der Drehwinkel der Transformation ist
$\theta_\mathrm{cam}$. Der Hintergrund wird über ein Medianbild ausgeblendet.
Das ist dasselbe Verfahren, mit dem die Kippzeitkonstante aus dem
Radpendel-Video gemessen wurde (`Konstruktion/radpendel_auswertung.py`,
0,6 Prozent); es läuft heute als Skript und ist für die Laborseite
(`getUserMedia`, Stufe 4 des Laborplans) vorgesehen.

**Zwei Winkel.** $\theta_\mathrm{cam}$ misst die Neigung des Aufbaus gegen die
Senkrechte des Bildes, $\theta_\mathrm{ist}$ ist der geschätzte Winkel des
Kalman-Filters abzüglich des nachgeführten Nullpunkts. Im Stand müssen beide bis
auf den Gleichgewichtswinkel $-\arctan(s/l)$ und den Restfehler der Kamera
(Bildrate, Kantenlage) übereinstimmen; ein Versatz zeigt einen Sensorfehler oder
eine falsche Einbaulage $w$, $u$, eine Verzögerung einen zu langsamen Filter.

**Stoßantwort.** Ein kurzer Stoß von Hand (später `/stoss` als kurzer
Sollwertsprung, Stufe 2) lenkt den Aufbau aus; aus $\theta_\mathrm{cam}(t)$ und
$\theta_\mathrm{ist}(t)$ werden durch Ausgleich einer abklingenden Schwingung
$\theta_0 e^{-t/\tau_K}\cos(2\pi f_K t+\varphi)$ die Eigenfrequenz $f_K$, die
Abklingzeit $\tau_K$ und aus den letzten Sekunden das Restzittern bestimmt.
Vorhergesagt sind sie in Teil VII (Wurzeln des Kreises); die Schranke für
„stimmt“ ist $\pm 15$ Prozent in $f_K$ und $\pm 30$ Prozent in $\tau_K$, weil
die Kamera bei 30 Bildern je Sekunde eine Schwingung von rund 1,3 Hz mit etwa
23 Bildern je Periode auflöst.

**Entscheidung und Nachziehen.** Stimmen die Kennwerte, ist das Modell belegt
und die Beiwerte bleiben. Weichen sie ab, wird nicht am Regler gedreht, sondern
zuerst die Strecke nachgeführt: mit festen Beiwerten hängen $f_K$ und $\tau_K$
im linearen Modell des Teils VII an $J/(m\,l)$, $d$ und $\tau_\mathrm{mot}$;
die drei Größen werden so bestimmt, dass das Modell die gemessene Stoßantwort
trifft (Ausgleich mit dem Zustandsmodell, `Modell/segway_entwurf.py`). Erst mit
der nachgeführten Strecke werden die Beiwerte neu ausgelegt — in der Laborseite
über „Regler automatisch auslegen“ (Suche über $K$, $T_n$, $T_v$ mit
Verstärkungsreserven, Teil VI) — und mit `/param` in den Flash des ESP32
geschrieben (Stufe 2). Dann wieder Freigabe, Stoß, Vergleich: die Schleife
endet, wenn Gerät und Modell dieselben Kennwerte liefern.

| Schritt | Mittel | Stand |
|:--|:--|:--|
| Zeitmarke | Synchron-LED GPIO 23, Spalte `led`, `/log` | in der Firmware (übersetzt) |
| Mitschnitt | `/log`, $f_\mathrm{log}$ | in der Firmware |
| Bildauswertung | AKAZE + RANSAC gegen Bezugsbild, Medianhintergrund | Skript vorhanden, Laborseite geplant (Stufe 4) |
| Stoß | von Hand; `/stoss` | Firmware Stufe 2 |
| Beiwerte schreiben | `/param`, im Flash gespeichert | Firmware Stufe 2 |
| Auslegung | Laborseite „Regler automatisch auslegen“ | vorhanden (Labor 1.1) |
| Nachführen der Strecke | Ausgleich der Stoßantwort mit dem Zustandsmodell | Stufe 5 |

## Was am Gerät zu messen bleibt

| Größe | wie | wozu |
|---|---|---|
| Masse | Waage | geht in jede Rechnung ein |
| Schwerpunkthöhe l über der Achse | Fahrzeug auf eine Kante legen, Gleichgewichtspunkt suchen | bestimmt die Kippzeitkonstante |
| Trägheitsmoment J | als Pendel um die Radachse schwingen lassen, $J = m g l (T/2\pi)^2$ | bestimmt die Kippzeitkonstante |
| Sensoreinbauhöhe über der Achse | Maßband | geht in die Scheinneigung ein |
| größte Beschleunigung A_MAX | Rampentest, siehe „Die Messung von A_MAX“ | bestimmt den Fangbereich |
| Rechenzeit je Takt | Anzeige | prüft, ob 250 Hz gehalten werden |

Mit diesen sechs Zahlen ist im Modell nichts mehr geschätzt, und die
Unsicherheitsspanne aus Teil VI schrumpft auf einen Punkt. Der Entwurf
ist so ausgelegt, dass er die ganze Spanne trägt — die Messung macht ihn
nicht erst brauchbar, sondern erlaubt schärfere Aussagen.

## Was bleibt zu tun

1. Aufspielen und nach Teil VIII in Betrieb nehmen.
2. `A_MAX` am Gerät messen (Teil VIII) — die einzige Zahl, die nicht
   gerechnet werden kann. Der gefundene Wert gehört danach in
   `A_MAX_VORGABE` im Quelltext.
3. Mitschnitt fahren und die sechs Größen aus „Was am Gerät zu messen
   bleibt“ messen. Damit
   wird aus der Auslegung über eine Spanne eine Auslegung für dieses Gerät.
4. Wenn der Motor bei kleiner Frequenz hörbar rastet: `MIN_HZ` schrittweise
   erhöhen und den Grenzzyklus in Kauf nehmen. Der Zusammenhang steht in
   Teil VI, „Zwei Befunde am vorhandenen Aufbau“.

\newpage

## Der Prüfstand und die Maße

Für die Standprüfung mit Kamera und Fangleine (Aufgabenblatt `AUFGABEN_Segway_2026-09-28.md`, Teil B) ist ein Prüfstand
gezeichnet; die Maße darin sind die am 28.09.2026 gemessenen. Das Maßblatt `Konstruktion/MASSE_UND_GEWICHTE.md` trägt
alle Maße und Massen mit ihrer Herkunft.

![Der Prüfstand für die Standstabilität: Fangleine von oben, Führungsleisten unten, Kamera von der Seite; Maße vom 28.09.2026.](Pruefstand/halterung.png)

Die Maße des Aufbaus aus der Konstruktion und den Messungen zeigt das Bild in Teil II („Die Zahlen der Strecke“).

\newpage

## Der Weg zum Gerät

Das Modell ist damit der Maßstab für die Inbetriebnahme: Die Stoßantwort des
stehenden Fahrzeugs (Aufgabe C4/D4: kurzer Geschwindigkeitsimpuls aus der
Firmware, Mitschnitt mit 250 Hz, dazu die Laptopkamera mit Synchronblitz)
liefert Eigenfrequenz und Dämpfung des realen Kreises; das Modell sagt sie
voraus (Eigenwertpaar 3: 1,34 Hz, Abklingzeit 0,10 s; Paar 2: 0,11 Hz,
2,5 s). Stimmen beide, ist das Modell belegt, und die Neueinstellung (D5) kann
aus ihm heraus erfolgen — nicht aus dem Probieren am Gerät. Weichen sie ab,
sagt die Abweichung, welche der noch angenommenen Größen ($\tau_\mathrm{mot}$,
$a_\mathrm{max}$, Rauschen) falsch ist.

\newpage

# Anhänge

## Anhang A — Der Beschleunigungswinkel, exakt hergeleitet

Der Beschleunigungsmesser misst die spezifische Kraft, also die Differenz aus
Beschleunigung und Schwerebeschleunigung, ausgedrückt im Gehäusesystem. Bei
Neigung $\theta$ und waagerechter Beschleunigung $a$ lauten die Komponenten

$$a_y = g\sin\theta - a\cos\theta, \qquad a_z = g\cos\theta + a\sin\theta$$

Der daraus gebildete Winkel ist

$$\theta_{\text{acc}} = \arctan\frac{g\sin\theta - a\cos\theta}{g\cos\theta + a\sin\theta}$$

Mit $a = g\tan\alpha$, also $\alpha = \arctan(a/g)$, wird der Bruch zu

$$\frac{g\sin\theta - g\tan\alpha\cos\theta}{g\cos\theta + g\tan\alpha\sin\theta}
= \frac{\sin\theta\cos\alpha - \sin\alpha\cos\theta}{\cos\theta\cos\alpha + \sin\alpha\sin\theta}
= \frac{\sin(\theta-\alpha)}{\cos(\theta-\alpha)} = \tan(\theta-\alpha)$$

und damit

$$\theta_{\text{acc}} = \theta - \arctan\frac{a}{g}$$

Der Ausdruck ist exakt. Für kleine Beschleunigungen gilt die handliche Form
$\Delta\theta \approx a/g$, entsprechend 5,84 Grad je Meter pro
Sekundenquadrat.

## Anhang B — Umrechnung der Codegrößen

Mit $r = 0{,}0315$ m, $N_s = 3200$, MAX\_SPEED $= 4000$ Hz,
MAX\_PID\_OUTPUT $= 500$ und $f_T = 100$ Hz:

| Zwischengröße | Wert |
|---|---|
| Geschwindigkeit je Schritt-Hertz $2\pi r/N_s$ | $6{,}185\cdot 10^{-5}$ m/s |
| Umrechnungsfaktor $s$ | $4{,}948\cdot 10^{-4}$ m/s je Einheit pidOutput |

| Codegröße alt | Wert | physikalischer Beiwert | Normalform neu |
|---|---|---|---|
| ANGLE\_KP | 45 | $k_p = 1{,}28$ m/s je rad | $K = 1{,}28$ |
| ANGLE\_KI | 12 | $k_i = 34{,}0$ m/s je rad·s | $T_n = K/k_i = 37{,}6$ ms |
| ANGLE\_KD | 30 | $k_d = 0{,}0085$ m/s je rad/s | $T_v = k_d/K = 6{,}6$ ms |
| Kp (äußerer Kreis) | 240 | $0{,}135$ rad je m/s | $K_v = 0{,}135$ |
| Ki (äußerer Kreis) | 5 | $0{,}282$ rad je m/s·s | $T_{n,v} = 479$ ms |

Die Umrechnung gilt für den Arbeitspunkt mit $N_s = 3200$, MAX\_SPEED
$= 4000$ Hz und 100 Hz Regeltakt. Der überarbeitete Regler benutzt
ausschließlich die rechte Spalte; die linke hängt an allen drei genannten
Größen, die rechte an keiner.

## Anhang C — Verzeichnis der Kenngrößen (Stand 29. September 2026)

| Größe | Wert | Herkunft |
|:------------------------------|:---------------|:--------------------------------------------|
| Masse des Aufbaus $m$ | 1,248 kg | gewogen 28.09.2026 |
| Schwingungsdauer um die Radachse $T_p$ | 0,6702 ± 0,0041 s | Radpendel-Video, Bildauswertung |
| Kippzeitkonstante $T = \sqrt{J/(mgl)}$ | 106,7 ms | $T_p/(2\pi)$; Konstruktion 105,9 ms |
| Schwerpunkthöhe $l$ | 44,5 mm | Konstruktion (STL-Massen, gewogener Akku) |
| Trägheitsmoment um die Achse $J$ | 6,20·10⁻³ kg m² | $J/(ml)$ gemessen, $l$ aus der Konstruktion |
| Sensorlage $w$, $u$ | 71 mm über, 39 mm vor der Achse | gemessen 28.09.2026 |
| Lagerreibung $d$ | 0,002 Nms (bis 0,012) | Abklingen des Radpendels, Spanne |
| Raddurchmesser | 64 mm | gemessen 28.09.2026; in der Firmware |
| Schritte je Umdrehung $N_s$ | 1600 | 200 Vollschritte, achtfacher Mikroschritt (Firmware) |
| Schrittweite | 0,1257 mm | $2\pi r/N_s$ |
| Höchste Schrittfrequenz | 6000 Hz | Firmware |
| Rampe $a_\mathrm{max}$ | 6,48 m/s² | Firmware; Motorgrenze mit 1,25 kg nicht gemessen (F3) |
| Treiberverzug $\tau_\mathrm{mot}$ | 2 ms | Annahme, Empfindlichkeit gerechnet (Anhang E) |
| Regeltakt $T_a$ | 4 ms (250 Hz) | Firmware |
| Laufzeit des Sensortiefpasses $\tau_\mathrm{lp}$ | 4,8 ms | Datenblatt MPU6050, 42-Hz-Einstellung |
| Winkelregler $K$, $T_n$, $T_v$ | 2,325 m/s je rad; 86,6 ms; 8,8 ms | Firmware (aus dem Quelltext gelesen) |
| Nullpunktkorrektur $K_N$, $T_{n,N}$ | 0,0813 rad je m/s; 2,27 s | Firmware |
| Kalman $Q_\mathrm{angle}$, $Q_\mathrm{bias}$, $R$ | 0,001; 0,003; 309,3 | Firmware |
| Pole der Strecke | +9,21; −9,54; −500 s⁻¹ | Teil II |
| Kippbewegung im Kreis | 1,34 Hz, 103 ms Abklingzeit | Teil VII |
| Reserven | 2,43-fach / 0,459-fach | Teil VII |

Die Werte des Entwurfs vom 25. August (geschätzt: 0,35 kg, 0,12 m, Stab-Trägheitsmoment, Rad 63 mm, 3200 Schritte des studentischen Codes) stehen in den Berichten `Modell/bericht_entwurf.txt` und `Modell/bericht_lauf.txt`; Anhang F behandelt die studentischen Fassungen mit ihren eigenen Kenngrößen.

## Anhang D — Die Programme und ihre Reihenfolge

Die Aussagen dieses Manuskripts bauen aufeinander auf. Die Reihenfolge, in
der sie geprüft wurden, ist zugleich die Reihenfolge, in der die Programme
voneinander abhängen:

| Schritt | Datei | Was sie leistet | Wogegen sie geprüft ist |
|--:|:------------------------------------|:------------------------|:--------------|
| 1 | `Modell/segway_modell.py` | Strecke, Sensor, die vier Schichten und die Nachbildung aller vorhandenen Reglerfassungen | Runge-Kutta vierter Ordnung derselben Bewegungsgleichung, 0,068 % über 0,2 s |
| 2 | `Modell/segway_entwurf.py` | exakte lineare Analyse des abgetasteten Kreises, 16 Zustände, Eigenwerte und Reserven | gegen Schritt 1, 0,001 bis 0,1 % |
| 3 | `Modell/suche_entwurf.py` | Auslegung: sucht Beiwerte, die in jeder Ecke der Unsicherheitsspanne stabil sind | benutzt Schritt 2 |
| 4 | `Modell/pruefung_entwurf.py` | nichtlinearer Nachweis: Fangbereich, Stoß, Nullpunkt, Rauschen, Fahrbefehl; erzeugt `bericht_entwurf.txt` und die Bilder | benutzt Schritt 1 |
| 5 | `Modell/gegenprobe_firmware.py` | schreibt die Firmware unabhängig ein zweites Mal auf und vergleicht sie mit Schritt 1 | Abweichung 1,1·10⁻⁸ Grad über 3000 Takte |
| 6 | `Konstruktion/radpendel_auswertung.py`, `traegheit_aus_konstruktion.py` | die gemessenen Streckengrößen: Schwingungsdauer aus dem Video, $l$ und $J$ aus der Konstruktion | zwei Wege, 106,7 gegen 105,9 ms |
| 7 | `Modell/nachweis_gemessen.py` | der Nachweis der Schritte 2 und 4 mit den gemessenen Zahlen, Empfindlichkeit (Anhang E) | benutzt 1, 2, 4, 5 unverändert |
| 8 | `Modell/uebertragungsfunktion.py` | Zustandsmodell, Übertragungsfunktion, Abtastform, Sprungantwort, Kreis im Laplace-Bereich, Reserven (Teil II und VII) | gegen 1 (RK4), 2 (Eigenwerte), Polynom gegen Matrizen |
| 9 | `Modell/pruefe_modellkapitel.py` | das Prüfprotokoll zu Teil II und VII: jede Zahl des Manuskripts gegen die Rechnung, Bilder und Überschriften des PDF | 29 Prüfungen mit Schranke; Protokoll siehe Ergebnisdateien |
| 10 | `Bilder/erstelle_bilder.py`, `baue_manuskript.sh` | die gezeichneten Bilder; der Bau von PDF und DOCX mit anschließender Prüfung | Bilder werden angesehen, Protokoll muss ohne Beanstandung sein |

Die Beiwerte werden in Schritt 5 aus dem Quelltext der Firmware **gelesen**,
nicht abgeschrieben — ein Tippfehler in der Übertragung fiele damit auf.

Die Firmware selbst:

| Datei | Inhalt |
|:--------------------------------------------|:----------------------|
| `Arduino/segway_regelung/segway_regelung.ino` | der ausgelegte Regler in vier Schichten |
| `Arduino/Segway/Segway.ino` | Ein-Datei-Fassung des studentischen Codes, unverändert im Verhalten |
| `Arduino/segway_esp32_Doku/segway_esp32_Doku.ino` | die eigene Vorgängerfassung mit eingebautem Mitschnitt |

Ergebnisdateien:

| Datei | Inhalt |
|:--------------------------------------------|:----------------------|
| `Modell/bericht_lauf.txt` | vollständiger Rechenlauf zu den vorhandenen Fassungen |
| `Modell/bericht_entwurf.txt` | vollständiger Nachweis des neuen Entwurfs |
| `Modell/bild1` bis `bild5` | Bilder zu den vorhandenen Fassungen |
| `Modell/entwurf1` bis `entwurf3` | Bilder zum neuen Entwurf (25.08., geschätzte Strecke) |
| `Modell/gemessen_2026-09-28/` | Nachweis mit den gemessenen Größen: Bericht, JSON, Bilder `gemessen1` bis `gemessen3`, Blatt `NACHWEIS_gemessen_2026-09-28.pdf` |
| `Modell/uebertragungsfunktion.json`, `.txt` | alle Matrizen, Pole, Wurzeln und Proben aus Teil II und VII |
| `Modell/PRUEFPROTOKOLL_Modellkapitel.md`, `.pdf` | das Prüfprotokoll des Modellkapitels |

## Anhang E — Empfindlichkeit der Reserven gegenüber der Messunsicherheit

Die lineare Analyse des abgetasteten Kreises (Teil VII) mit den gemessenen
Streckengrößen und ihren Unsicherheitsgrenzen (`Modell/nachweis_gemessen.py`,
Ergebnis `Modell/gemessen_2026-09-28/nachweis_gemessen.json`):

| Fall | Kippzeitkonstante | größter Eigenwertbetrag | Reserve oben / unten |
|:--------------------------------------|----------:|----------:|:-----------|
| Nachweis 25.08. (m 0,35, l 0,12, Stab-J) | 127,7 ms | 0,99936 | 2,46 / 0,453 |
| gemessen, Nennfall (d = 0,002) | 106,7 ms | 0,99936 | 2,43 / 0,459 |
| gemessen, d = 0,012 Nms | 106,7 ms | 0,99936 | 2,44 / 0,472 |
| gemessen, T_p − Unsicherheit | 106,0 ms | 0,99936 | 2,43 / 0,459 |
| gemessen, T_p + Unsicherheit | 107,3 ms | 0,99936 | 2,43 / 0,459 |
| gemessen, l = 40 mm (J/(m l) fest) | 106,7 ms | 0,99936 | 2,43 / 0,459 |
| gemessen, l = 50 mm (J/(m l) fest) | 106,7 ms | 0,99936 | 2,43 / 0,459 |
| gemessen, tau_mot = 6 ms | 106,7 ms | 0,99936 | 2,20 / 0,465 |
| gemessen, Sensor w = 0 (zum Vergleich) | 106,7 ms | 0,99936 | 2,50 / 0,443 |

Innerhalb der Messunsicherheit ändern sich die Reserven in der dritten Stelle;
nur der Treiberverzug — die eine noch angenommene Größe — verschiebt die obere
Reserve spürbar (2,43 auf 2,20 bei 6 ms statt 2 ms). Er ist am Gerät aus dem
Mitschnitt zu messen (F4).

## Anhang F — Die vorhandenen studentischen Fassungen: Bestandsaufnahme

Drei Fassungen liefen vor dieser Auslegung: die von xxxx xxxx aus dem
Praxissemester, die Laborarbeit von xxx xxxxxxxxx und xxxxx xxxxxxx und eine
eigene Vorgängerfassung. Sie balancieren, aber sie sind erprobt, nicht
gerechnet. Was sie tun, warum sie funktionieren und woran sie scheitern, steht
hier — als Bestandsaufnahme, aus der die Befunde und Anforderungen in Teil V
hervorgegangen sind. Der rote Faden des Manuskripts braucht diesen Anhang
nicht; wer die Fassungen kennt, findet hier den Bezug.

### Der Regelcode

### Aufbau

Der Code enthält eine Kaskade aus zwei Kreisen:

Der äußere Kreis (`piSpeedCalc`) bildet aus der Abweichung zwischen Soll- und
Istgeschwindigkeit einen Sollwinkel. Er benutzt die über die Weboberfläche
verstellbaren Größen Kp und Ki.

Der innere Kreis (`pidAngleCalc`) regelt den Winkel auf diesen Sollwert. Er
benutzt die im Programm eingetragenen Werte 45, 12 und 30.

#### Umrechnung in physikalische Einheiten

Der Reglerausgang wird über

$$f = \operatorname{clamp}(\text{pidOutput}, \pm 500)\cdot\frac{\text{MAX\_SPEED}}{\text{MAX\_PID\_OUTPUT}}$$

in eine Schrittfrequenz und über Gleichung (1) in eine Geschwindigkeit
umgesetzt. Mit dem Umrechnungsfaktor

$$s = \frac{\text{MAX\_SPEED}}{\text{MAX\_PID\_OUTPUT}}\cdot\frac{2\pi r}{N_s}$$

und dem Regeltakt $f_T$ ergeben sich die physikalischen Beiwerte zu

$$k_p = \text{ANGLE\_KP}\cdot s, \qquad
  k_i = \text{ANGLE\_KI}\cdot f_T\cdot s, \qquad
  k_d = \frac{\text{ANGLE\_KD}}{f_T}\cdot s$$

Der Regeltakt tritt in $k_i$ und $k_d$ auf, weil der Code weder beim
Integrieren noch beim Differenzieren durch die Schrittweite teilt. Die
Zahlenwerte stehen in Anhang C.

#### Was der äußere Kreis leistet

Der äußere Kreis erscheint auf den ersten Blick als Zutat für den Fahrbetrieb.
Er ist es nicht. Ohne ihn hält der innere Kreis zwar den Winkel, aber nichts
hindert die Räder daran, davonzulaufen, bis die Frequenzgrenze erreicht ist
und der Aufbau nicht mehr eingeholt werden kann.

Aus dem Modell, Start aus drei Grad Neigung:

| Kp | Ki | Verhalten | Restzittern [Grad] | Wegdrift nach 10 s [m] |
|---|---|---|---|---|
| 0 | 0 | fällt | — | 0,632 |
| 60 | 5 | fällt | — | 0,055 |
| 120 | 5 | fällt | — | 0,020 |
| 240 | 5 | balanciert | 0,047 | 0,000 |
| 480 | 5 | balanciert | 0,021 | 0,000 |
| 960 | 5 | fällt | — | 0,038 |
| 240 | 0 | balanciert | 0,007 | 0,029 |
| 240 | 2 | balanciert | 0,013 | 0,000 |
| 240 | 10 | fällt | — | 0,003 |
| 240 | 20 | fällt | — | 0,160 |

Der stabile Bereich liegt bei Kp zwischen 240 und 480 und bei Ki zwischen 0
und 5. Die im Code eingetragene Einstellung 240 und 5 liegt darin, aber im
Ki nicht in der Mitte, sondern am Rand: bei 10 fällt der Segway. Nach oben im
Kp ist dagegen noch Raum — 480 balanciert ruhiger als 240.

Bemerkenswert ist die Zeile Kp = 240, Ki = 0: sie balanciert am ruhigsten von
allen, fährt aber als einzige weg (29 mm in zehn Sekunden). Genau dafür ist
der Integralanteil des äußeren Kreises da, und genau das ist die Aufgabe, die
eine Nullpunktkorrektur zu lösen hat.

Dieses Ergebnis ordnet zugleich die Arbeit ein, die im Laborbericht
beschrieben ist. Dort wird berichtet, das Zittern um den Nullpunkt sei durch
Neueinstellung deutlich verringert worden. Das trifft zu — und es ist genau
die Aufgabe des äußeren Kreises. Die Zuordnung im Bericht, es handle sich um
den Winkelregler, trifft nicht zu.

### Befunde am Quellcode

Der Aufbau arbeitet. Die folgenden Punkte sind daher keine Fehlerliste,
sondern Beobachtungen, die für das Weiterarbeiten und für den Vergleich mit
dem Laborbericht von Bedeutung sind.

#### Kd wirkte auf nichts

In der geprüften Fassung benutzte der Winkelregler die eingetragene 30; die
Eingabe Kd der Weboberfläche wurde nirgends verrechnet. Im Modell
nachgewiesen: die Werte 0, 70 und 1000 lieferten denselben Verlauf bis auf die
letzte Stelle. Dieser Punkt ist mit der Überarbeitung entfallen, siehe Teil V.

![Nachweis der Wirkungslosigkeit: drei stark verschiedene Werte für Kd, ein einziger Verlauf.](Modell/bild2_kd_ohne_wirkung.png)

#### Der wirksame Regeltakt beträgt 100 Hz

Die Hauptschleife arbeitet im 4-Millisekunden-Raster, die PID-Rechnung läuft
aber nur bei einem neuen Datenpaket des Bewegungsprozessors, also mit 100 Hz.
Da im Code weder beim Integrieren noch beim Differenzieren durch die
Schrittweite geteilt wird, hängen $k_i$ und $k_d$ unmittelbar an dieser Rate.
Ein anderer Teiler in der Bibliothek verändert die Regelung, ohne dass ein
Beiwert angefasst wird.

Hinzu kommt, dass der 10-Millisekunden-Takt auf das 4-Millisekunden-Raster
fällt und dadurch abwechselnd 8 und 12 Millisekunden lang wird. Das moduliert
den Differentialanteil um etwa zwanzig Prozent — bei dessen geringer Wirkung
allerdings ohne Folgen.

Am Gerät prüfbar: die Anzeige `sampleHzx` sollte ungefähr 100 zeigen.

#### MAX\_SPEED ist zugleich Verstärkungsfaktor

Siehe Teil V, „Ergebnisse“.

#### Die Ansprechschwelle ist wirkungslos

In `setSpeed` steht `disableL(sL < MAX_SPEED / 12000)`. Der Ausdruck ist eine
Ganzzahldivision und ergibt null; der Vergleich ist nach der Betragsbildung
nie erfüllt.

Die Folge ist, dass die Motoren dauerhaft bestromt bleiben. Für ein
Balancierfahrzeug ist das die günstigere Betriebsart: ein bestromter
Schrittmotor hält seine Stellung mit vollem Haltemoment, während die
beabsichtigte Freigabe die Räder ausgerechnet bei kleinen Stellgrößen
freilaufen ließe. Bezahlt wird es mit Dauerstrom, also Wärme in Motoren und
Treibern und Entnahme aus dem Akku im Stillstand.

#### Weitere Punkte

| Punkt | Befund |
|---|---|
| `ypr` | wird aus zwei Prozessorkernen ohne Absicherung gelesen |
| Dateisystem | ein fehlgeschlagener SPIFFS-Start ließ die Regelung stillschweigend nicht anlaufen |
| Speicheranzeige | `snprintf` benutzte `%u` für `ESP.getFreeHeap()`, das `uint32_t` liefert |
| `mpuDataCounter++` | Inkrement auf einer `volatile`-Größe, in neueren C++-Fassungen abgekündigt |
| `notValid` | war global und konnte bei zwei gleichzeitigen Anfragen auf die jeweils andere durchschlagen |
| `angleSim`, `angleSimCre` | Bedienfelder für einen Simulationsbetrieb, der im Code nirgends ausgeführt war |

Alle diese Punkte sind in der Ein-Datei-Fassung bereinigt. Dort liegt die
Bedienoberfläche außerdem im Programmspeicher statt im SPIFFS — ein
gesonderter Datei-Upload entfällt —, die LEDC-Schnittstelle wird für
ESP32-Core 2.x und 3.x bedient, und ArduinoOTA ist eingebaut, wobei beim
Beginn eines Uploads die Motoren gesperrt werden.

#### Abweichung zwischen Laborbericht und Quellcode

Der Laborbericht führt in Abschnitt 2.4 die Werte Kp = 240, Ki = 5 und
Kd = 70 als Beiwerte des Winkelreglers auf und hält fest, die Codefassung
arbeite ohne Reglerkaskade. Beides trifft nicht zu: Der Code enthält eine
Kaskade, und die genannten Werte gehören zum äußeren Kreis.

Die Einstellarbeit selbst ist davon unberührt. Sie wurde, wie Abschnitt 4.3
zeigt, an der richtigen Stelle geleistet und hat das beschriebene Ergebnis
erbracht.

\newpage

### Ergebnisse der Nachbildung

### Arbeitspunkt

Mit 3200 Schritten je Umdrehung, entsprechend 200 Vollschritten bei 16-facher
Mikroschrittteilung:

| Größe | Wert |
|---|---|
| Geschwindigkeit je Hertz | $6{,}19\cdot 10^{-5}$ m/s |
| Höchstgeschwindigkeit bei 4000 Hz | 0,247 m/s, entsprechend 0,89 km/h |
| $k_p$ | 1,28 m/s je rad |
| $k_i$ | 34,0 m/s je rad·s |
| $k_d$ | 0,0085 m/s je rad/s |
| Kennkreisfrequenz | 12,5 rad/s, entsprechend 1,99 Hz |
| Dämpfungsgrad | 0,33 |

Die Kennkreisfrequenz liegt damit etwa um den Faktor 1,5 über dem Kehrwert
der Kippzeitkonstante — die Regelung ist der Strecke also merklich, aber
nicht übermäßig überlegen.

#### Betriebsfälle

![Aufrichten aus drei Grad Neigung. Von oben: Winkel, Messfehler des Sensors, Schrittfrequenz, Geschwindigkeit und Weg.](Modell/bild3_aufrichten.png)

| Fall | Ergebnis |
|---|---|
| Aufrichten aus 3 Grad | eingeschwungen nach 1,10 s, Restzittern 0,047 Grad |
| Stoß von 0,15 Nm über 50 ms | größter Ausschlag 2,25 Grad |
| Fahrbefehl | folgt, größter Winkel 0,64 Grad |

![Verhalten bei einer Stoßstörung.](Modell/bild4_stoss.png)

#### Betriebsfenster

![Betriebsfenster über Schrittzahl je Umdrehung und Beschleunigungsgrenze der Motoren. Farbig hinterlegt sind die stabilen Punkte mit ihrem Restzittern.](Modell/bild1_betriebsfenster.png)

Die Karte zeigt, unter welchen Bedingungen die fest eingetragenen Beiwerte
arbeiten können. Bemerkenswert ist, dass die tatsächlich eingestellte
Mikroschrittteilung als einzige im geprüften Raster über den gesamten
untersuchten Bereich der Motorleistung stabil bleibt. Bei gröberer Teilung
steigt die Schleifenverstärkung und verlangt Beschleunigungen, die der Antrieb
nicht liefert; bei feinerer sinkt sie unter das Nötige.

Der Antrieb ist dabei nicht die Grenze. Ab etwa 2 m/s² Beschleunigungsvermögen
balanciert das Fahrzeug, darüber ändert sich nichts mehr. Begrenzend ist die
Schrittfrequenz: mit 4000 Hz bei 16-facher Teilung drehen die Motoren 250
Vollschritte je Sekunde, und das Fahrzeug fängt sich bis etwa 9 Grad
Anfangsneigung. Die Sicherheitsabschaltung bei 30 Grad liegt weit jenseits
dessen, was noch zu retten ist.

#### Höchstgeschwindigkeit und Verstärkung

Die Größe MAX\_SPEED begrenzt nicht nur die Fahrgeschwindigkeit, sondern
skaliert über den Umrechnungsfaktor $s$ den gesamten Regler mit. Eine
Anhebung ohne Ausgleich verändert daher das Regelverhalten erheblich:

| MAX\_SPEED [Hz] | Beiwerte unverändert | Beiwerte im gleichen Verhältnis gesenkt |
|---|---|---|
| 4 000 | 9 Grad Fangbereich | 9 Grad (45 / 12 / 30) |
| 6 000 | 13 Grad | 13 Grad (30 / 8 / 20) |
| 8 000 | 17 Grad | 17 Grad (22,5 / 6 / 15) |
| 12 000 | fällt bereits bei 2 Grad | 22 Grad (15 / 4 / 10) |
| 16 000 | fällt bereits bei 2 Grad | 12 Grad (11,2 / 3 / 7,5) |

Bis 8000 Hz verhält sich die Anhebung gutmütig, weil die Begrenzung auf
$\pm 500$ den Zuwachs auffängt. Der günstigste Punkt liegt bei etwa 12 000 Hz
mit auf 15 / 4 / 10 gesenkten Beiwerten; 750 Vollschritte je Sekunde sind für
Motoren dieser Baugröße unkritisch.

#### Wirkung des Differentialanteils

Aus der Kennwertgleichung folgt, dass der Differentialanteil als scheinbare
Trägheit wirkt. Sein Einfluss auf den Dämpfungsgrad ist entsprechend gering:

| ANGLE\_KD | 0 | 30 | 60 | 120 | 200 | 400 |
|---|---|---|---|---|---|---|
| Dämpfungsgrad | 0,34 | 0,33 | 0,32 | 0,30 | 0,29 | 0,25 |
| Fangbereich [Grad] | 8 | 8 | 8 | 8 | 0 | fällt |

Zwischen 0 und 120 ändert sich praktisch nichts; oberhalb etwa 200 verliert
das Fahrzeug seinen Fangbereich. Wer die Dämpfung verstellen will, muss den
Proportionalanteil des Winkelreglers ändern, nicht den Differentialanteil.

### Überarbeitung der Software

Die Befunde des vorigen Abschnitts betreffen sämtlich nicht die Auslegung,
sondern die Schreibweise des Reglers. Sie lassen sich beheben, ohne das
erprobte Verhalten zu verändern. Der Regler wurde daher neu gefasst und jede
Änderung im Modell nachgewiesen, bevor sie in die Firmware übernommen wurde.

#### Was geändert wurde

Erstens ist die Schrittweite ausgeschrieben. Integral- und Differentialanteil
werden mit der tatsächlich verstrichenen Zeit gerechnet, die aus der Uhr des
Rechners genommen wird. Damit hängen die Beiwerte nicht mehr an der
Ausgaberate des Sensors, und der Wechsel zwischen 8 und 12 Millisekunden
Taktabstand wirkt sich nicht mehr aus.

Zweitens ist die Stellgröße eine Geschwindigkeit in Meter je Sekunde. Erst am
Schluss wird sie über die Radgeometrie in eine Schrittfrequenz umgerechnet.
MAX\_SPEED ist dadurch nur noch eine Grenze und keine Verstärkung mehr.

Drittens stehen die Beiwerte in physikalischen Einheiten und in der
Normalform

$$v = K\left(e + \frac{1}{T_n}\int e\,\mathrm{d}t + T_v\,\frac{\mathrm{d}e}{\mathrm{d}t}\right)$$

Der Zusammenhang zur bisherigen Einstellung ist in Anhang C angegeben. Die
Werte sind so gewählt, dass sie am vorhandenen Aufbau genau das leisten wie
zuvor.

Viertens läuft der Integrator nicht weiter, solange die Stellgröße in der
Begrenzung steht und der Fehler nicht aus ihr herausführt. Bisher wurde er
starr begrenzt, was nach längerer Sättigung ein Überschwingen zur Folge hatte.

Fünftens werden Mikroschrittteilung und Raddurchmesser als eigene Größen
geführt. Wird am Treiber eine andere Teilung eingestellt, ist nur diese eine
Zeile anzupassen; die Reglerbeiwerte bleiben gültig.

#### Nachweis im Modell

Das Modell rechnet den überarbeiteten Regler mit demselben Rechenweg wie die
Firmware. Alle folgenden Zahlen stammen aus demselben Programmlauf.

Am vorhandenen Arbeitspunkt verhalten sich beide Fassungen gleich — das war
die Bedingung für die Übernahme:

| Fassung | Verhalten | Einschwingzeit | Restzittern |
|---|---|---|---|
| vorhanden | balanciert | 1,10 s | 0,047 Grad |
| überarbeitet | balanciert | 1,10 s | 0,047 Grad |

Bei geänderter Mikroschrittteilung zeigt sich der Unterschied:

| $N_s$ | vorhanden | überarbeitet |
|---|---|---|
| 800 | balanciert, 1,303 Grad | balanciert, 0,047 Grad |
| 1600 | fällt | balanciert, 0,047 Grad |
| 3200 | balanciert, 0,047 Grad | balanciert, 0,047 Grad |
| 6400 | fällt | balanciert, 0,049 Grad |

Der überarbeitete Regler liefert an allen vier Teilungen praktisch dasselbe
Ergebnis. Der vorhandene fällt an zwei von vier, weil sich mit der Teilung
seine Schleifenverstärkung ändert; bei 800 bleibt er zwar stehen, aber mit
1,3 Grad Restzittern — dem Achtundzwanzigfachen des überarbeiteten Reglers.
Auch das ist kein brauchbarer Betrieb, nur eben kein Sturz.

Bei geänderter Ausgaberate des Sensors:

| Rate | vorhanden | überarbeitet |
|---|---|---|
| 50 Hz | balanciert, 0,030 Grad | balanciert, 0,023 Grad |
| 100 Hz | balanciert, 0,047 Grad | balanciert, 0,047 Grad |
| 200 Hz | fällt | fällt |
| 250 Hz | fällt | fällt |

Bei 50 und 100 Hz bleiben beide stabil. Bei 200 und 250 Hz fallen beide — und
das aus verschiedenen Gründen. Beim vorhandenen Regler wächst mit der Rate
seine Integral- und Differentialwirkung mit, weil im Code nicht durch die
Schrittweite geteilt wird. Beim überarbeiteten Regler ist das behoben; er
fällt, weil die Beiwerte für 100 Hz ausgelegt sind und der Kalman des
Studentencodes mit seiner kurzen Zeitkonstante bei höherer Rate mehr von der
eigenen Beschleunigung durchlässt. Der Neuentwurf, beschrieben in
`ENTWURF_Segway_Regelung.md`, behebt genau diesen Punkt und ist von 100 bis
500 Hz unempfindlich.

Beim Anheben der höchsten Schrittfrequenz, ohne sonst etwas zu ändern:

| MAX\_SPEED | vorhanden | überarbeitet |
|---|---|---|
| 4 000 Hz | 10 Grad Fangbereich | 10 Grad |
| 8 000 Hz | 18 Grad | 18 Grad |
| 12 000 Hz | 24 Grad | 24 Grad |
| 16 000 Hz | fällt | 29 Grad |

Bis 12 000 Hz verhalten sich beide gleich; bei 16 000 Hz fällt der vorhandene
Regler, weil dort seine Schleifenverstärkung über die Stabilitätsgrenze
wächst — MAX\_SPEED ist bei ihm nicht nur Obergrenze, sondern zugleich
Verstärkungsfaktor. Beim überarbeiteten Regler ist das getrennt: die
Fangreserve lässt sich allein durch Anheben der Frequenzgrenze vergrößern,
ohne die Beiwerte nachzuziehen.

Fangbereich und Störverhalten am Arbeitspunkt sind unverändert: 10 Grad
Anfangsneigung, 2,24 gegenüber 2,25 Grad Ausschlag beim Stoß.

#### Bedienung

Die Weboberfläche zeigt jetzt fünf Größen mit physikalischer Bedeutung
anstelle der drei zuvor teils wirkungslosen:

| Feld | Einheit | Wirkung |
|---|---|---|
| Winkelregler K | m/s je rad | dämpft |
| Winkelregler $T_n$ | ms | richtet auf; kleiner ist stärker |
| Winkelregler $T_v$ | ms | wirkt wie zusätzliche Trägheit |
| Fahrtregler K | rad je m/s | hält auf der Stelle |
| Fahrtregler $T_n$ | ms | dito, langsamer Anteil |

Alle Eingaben sind auf Bereiche begrenzt, in denen das Fahrzeug im Modell
nicht umfällt.

#### Was bewusst nicht geändert wurde

Die Dauerbestromung der Motoren im Stillstand bleibt. Sie war, wie in
oben dargelegt, die Folge eines Rechenfehlers, aber die günstigere
Betriebsart; sie ist jetzt als Absicht ausgewiesen.

Die Zahlenwerte der Regelung bleiben so, dass der Aufbau sich verhält wie
bisher. Wer die Empfehlungen des folgenden Abschnitts umsetzen will, ändert
dazu eine Zeile.

#### Erprobung am Gerät

Der Sketch wurde am 24. August auf einem ESP32 ohne Sensor und ohne Motoren
in Betrieb genommen: Er bootet, WLAN und Webserver laufen, die Bedienseite
erscheint im Browser. Fünf daraus folgende Nachbesserungen betreffen die
Betriebsführung, nicht den Regelkern — Sensor-Wiedersuche alle fünf Sekunden,
Entkopplung des Handbetriebs von der Sensorabfrage, Netzname ohne
Anführungszeichen, Auffangpfad für beliebige Adressen und eine gesammelte
Startmeldung. Einzelheiten in der Kurzdokumentation.

Die Erprobung am vollständigen Aufbau mit Sensor und Motoren steht aus.

### Auslegungsempfehlungen

1. Soll die Fangreserve vergrößert werden, genügt jetzt das Anheben von
   MAX\_SPEED. Bei 12 000 Hz sind es 22 Grad, bei 16 000 Hz 26 Grad. Zu
   prüfen ist dabei, ob die Motoren die Frequenz bei Last noch mitgehen —
   16 000 Hz bei 16-facher Teilung sind 1000 Vollschritte je Sekunde.
2. Soll die Dämpfung verändert werden, ist die Verstärkung K des
   Winkelreglers zu verstellen, nicht die Vorhaltezeit.
3. Die Sicherheitsabschaltung bei 30 Grad könnte auf etwa 15 Grad
   herabgesetzt werden. Oberhalb des Fangbereichs läuft das Fahrzeug ohnehin
   nur noch mit voller Frequenz davon, ohne sich zu fangen.
4. Die Dauerbestromung der Motoren im Stillstand ist zu bedenken, wenn die
   Betriebsdauer aus dem Akku eine Rolle spielt.
5. Wird am Treiber die Mikroschrittteilung geändert, ist im Sketch die Zeile
   SCHRITTE\_JE\_UMDREHUNG anzupassen. Die Reglerbeiwerte bleiben gültig.

\newpage
