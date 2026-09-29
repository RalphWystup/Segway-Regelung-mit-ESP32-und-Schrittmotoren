// =====================================================================
//  SEGWAY - Regelung in vier Schichten
//
//  Aufbau   : ESP32 WROOM-32, zwei Schrittmotoren an A3967, MPU6050
//  Grundlage: segway_esp32_Doku.ino von R. Wystup (Hardware, Sensor,
//             Motoransteuerung unveraendert uebernommen)
//  Neu      : Reglerstruktur, Beiwerte und Nullpunktbehandlung. Alles
//             davon wurde vorher am Modell gerechnet und geprueft,
//             siehe Modell/segway_modell.py und Modell/segway_entwurf.py
//
//  ------------------------------------------------------------------
//  DER AUFBAU
//  ------------------------------------------------------------------
//  Die Reihenfolge ist fest, jede Schicht kennt nur ihre Eingaenge:
//
//    Schicht 1  Winkelerfassung
//               Rohdaten des MPU6050 -> Kalman-Filter -> Istwinkel [rad]
//               und Drehrate [rad/s] ohne Kreiselnullpunkt.
//               Istwinkel null bedeutet Gleichgewicht, nicht senkrecht.
//
//    Schicht 2  Winkelregler
//               Istwinkel -> Stellgroesse. Die Stellgroesse ist eine
//               Radgeschwindigkeit in m/s, keine Zahl ohne Einheit.
//
//    Schicht 3  Motoreinheit
//               Radgeschwindigkeit -> Schrittfrequenz, begrenzt und
//               mit Rampe. Sie kennt als einzige den Zusammenhang
//               zwischen Hertz und Metern und meldet deshalb
//               Geschwindigkeit und Weg zurueck - ohne jeden Geber.
//
//    Schicht 4  Dynamische Nullpunktkorrektur (uebergeordnet)
//               Faehrt das Fahrzeug weg, obwohl null befohlen ist, dann
//               stimmt der Nullpunkt nicht. Richtung und Betrag der
//               Bewegung sind aus der Schrittfrequenz bekannt. Ein
//               langsamer PI verschiebt den Nullpunkt der Schicht 1,
//               bis Istwinkel null wirklich Stillstand bedeutet.
//
//  Sollwertvorgabe, Datenaufzeichnung und Weboberflaeche greifen NICHT
//  in diesen Ablauf ein. Die Regelung laeuft als eigene Aufgabe auf
//  Kern 1 in festem 4-ms-Takt; alles andere liegt auf Kern 0 und tauscht
//  nur fertige Zahlen aus.
//
//  ------------------------------------------------------------------
//  PINBELEGUNG (unveraendert)
//  ------------------------------------------------------------------
//    Stepper RECHTS  STEP=32  DIR=33  EN=14
//    Stepper LINKS   STEP=25  DIR=26  EN=27   (spiegelverkehrt montiert)
//    MPU6050         SDA=21   SCL=22
//
//  Bibliotheken: FastAccelStepper (gin66), Wire, WiFi, WebServer,
//                ArduinoOTA - alle ueber den Bibliotheksverwalter.
// =====================================================================

#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoOTA.h>
#include "FastAccelStepper.h"

// =====================================================================
//  1  EINSTELLUNGEN
// =====================================================================

// ---- Netz ----
// Netzname und Passwort stehen in wlan_zugang.h (nicht veroeffentlicht, siehe .gitignore);
// Vorlage: wlan_zugang.h.beispiel
#include "wlan_zugang.h"
static const char* OTA_NAME  = "segway";

// ---- Anschluesse ----
#define LED_SYNC 23   // blaue LED ueber 330 Ohm gegen GND: blitzt beim Start des Mitschnitts dreimal (Zeitmarke fuer die Kamera)
#define STEP_R 32
#define DIR_R  33
#define EN_R   14
#define STEP_L 25
#define DIR_L  26
#define EN_L   27
#define SDA_PIN 21
#define SCL_PIN 22
#define MPU_ADR 0x68

// ---- Mechanik und Antrieb ----
// Diese Groessen stehen einzeln da, weil jede von ihnen sich aendern
// kann, ohne dass die Beiwerte des Reglers angepasst werden muessen.
static const float RAD_DURCHMESSER = 0.064f;   // m, gemessen 28.09.2026 (vorher 0,066 aus dem Vorlesungsmanuskript)
static const int   SCHRITTE_JE_UMDREHUNG = 1600; // 200 * 8 Mikroschritte
static const float SCHRITTWEITE =                // m je Schritt
      (float)(M_PI * RAD_DURCHMESSER / SCHRITTE_JE_UMDREHUNG);

// ---- Takt ----
// Der Sollabstand betraegt 4 ms. vTaskDelayUntil haelt den Mittelwert
// genau ein, der einzelne Abstand schwankt aber um bis zu einen
// FreeRTOS-Takt (1 ms), also um 25 Prozent. Gerechnet wird deshalb mit
// der WIRKLICHEN Schrittweite aus der Uhr; die Grenzen fangen einen
// verschluckten Takt ab, ohne dass der Integrator springt.
static const uint32_t TAKT_MS  = 4;            // 250 Hz
static const float    DT_SOLL  = TAKT_MS * 0.001f;
static const float    DT_MIN   = 0.5f * DT_SOLL;
static const float    DT_MAX   = 3.0f * DT_SOLL;

// ---- Grenzen ----
// Groesste Schrittfrequenz. Der A3967 verliert bei hohen Frequenzen
// Drehmoment; 6000 Hz sind der am Geraet erprobte Wert.
static const float MAX_HZ = 6000.0f;
static const float V_MAX  = MAX_HZ * SCHRITTWEITE;   // m/s
// Totzone der Motorausgabe. Der frueher benutzte Wert 80 Hz erzeugt am
// Modell einen dauernden Grenzzyklus von 0,31 Grad; ohne Totzone sind es
// 0,014 Grad. Die Sperre ist also die Ursache des Zitterns, nicht das
// Mittel dagegen - im Code von xxxx war sie an allen drei Stellen
// unwirksam, und seine Maschine lief ruhig.
// Der Wert bleibt einstellbar, weil das Modell eines nicht sehen kann:
// ob der Motor bei wenigen Hertz mechanisch singt. Das ist am Geraet zu
// hoeren. Anhaltswerte: 0 Hz -> 0,014 Grad, 20 Hz -> 0,08 Grad,
// 40 Hz -> 0,15 Grad, 80 Hz -> 0,31 Grad.
static const float MIN_HZ = 0.0f;
// Sicherheitsabschaltung und Wiederfreigabe. Sie sind bewusst
// verschieden: abgeschaltet wird spaet (30 Grad), freigegeben aber erst,
// wenn das Fahrzeug ruhig innerhalb des Fangbereichs steht. Gaebe man bei
// 30 Grad wieder frei, liefen die Motoren an, waehrend das Fahrzeug noch
// faellt - der Fangbereich betraegt am Modell 20 Grad.
static const float KIPP_GRENZE  = 30.0f;   // Grad, sofort abschalten
static const float FREI_WINKEL  =  5.0f;   // Grad, darunter darf angefahren werden
static const float FREI_RATE    = 60.0f;   // Grad/s, und nur wenn es ruhig ist
static const uint16_t FREI_TAKTE = 125;    // 0,5 s lang beides erfuellt

// ---------------------------------------------------------------------
//  A_MAX - die einzige Zahl, die aus einer Messung kommen muss
// ---------------------------------------------------------------------
//  Sie ist die groesste Beschleunigung, die die Raeder wirklich annehmen,
//  ohne dass Schritte verloren gehen. An ihr haengt zweierlei:
//
//    der FANGBEREICH   - aus wie viel Neigung sich das Fahrzeug noch
//                        aufrichtet. Am Modell nachgefahren:
//
//                          A_MAX  setAcceleration  Fangbereich  Stoss
//                          1,50       11 575          3,5 Grad  0,13 Nm
//                          2,00       15 433          4,5 Grad  0,18 Nm
//                          3,00       23 150          7,0 Grad  0,29 Nm
//                          4,00       30 867         16,5 Grad  0,34 Nm
//                          6,48       50 004         20,5 Grad  0,42 Nm
//                         10,00       77 166         23,5 Grad  0,42 Nm
//                         15,00      115 750         25,5 Grad  0,42 Nm
//                         25,00      192 916         27,0 Grad  0,42 Nm
//
//                        Der Sprung zwischen 3 und 4 m/s2 ist die Stelle,
//                        an der die Rampe aufhoert, das Aufrichten zu
//                        begrenzen. Ueber 10 m/s2 wird kaum noch etwas
//                        gewonnen, weil dann die Frequenzgrenze wirkt.
//
//    die GUELTIGKEIT   - fordert der Regler mehr, als die Motoren
//                        leisten, gehen Schritte verloren. Dann ist die
//                        ausgegebene Frequenz nicht mehr die
//                        Radgeschwindigkeit, und Schicht 3 und 4
//                        verlieren ihre Grundlage. Deshalb begrenzt die
//                        Motoreinheit die Aenderung selbst auf diesen
//                        Wert - gefordert wird dann nie mehr, als geht.
//
//  Die Reglerbeiwerte haengen NICHT davon ab. Ueber die ganze Spanne von
//  1,5 bis 25 m/s2 bleiben Restzittern (0,010 Grad) und
//  Nullpunkttoleranz (8,5 mm) unveraendert; nur der Fangbereich wandert
//  mit. A_MAX aendern heisst also, den Fangbereich zu aendern - nicht,
//  neu auslegen zu muessen.
//
//  MESSEN (Verfahren in ENTWURF_Segway_Regelung.md, Abschnitt 10.4):
//    Fahrzeug auf den Ruecken legen, Raeder frei, Freigabe AUS.
//    Im Browser  /rampentest?a=<Wert>  aufrufen; die Motoren fahren dann
//    zehnmal von +v auf -v und zurueck, mit genau dieser Beschleunigung.
//    Den Wert schrittweise erhoehen, bis der Motor beim Richtungswechsel
//    rasselt oder stehenbleibt. Vom letzten sauberen Wert 20 Prozent
//    abziehen und ueber  /rampe?a=<Wert>  dauerhaft setzen.
//
//  Der Startwert entspricht dem bisherigen setAcceleration(50000).
static const float A_MAX_VORGABE = 6.48f;      // m/s2
static const float A_MAX_KLEINST = 0.5f;       // m/s2, Untergrenze
static const float A_MAX_GROESST = 40.0f;      // m/s2, Obergrenze


// =====================================================================
//  2  DATENAUSTAUSCH ZWISCHEN DEN KERNEN
// =====================================================================
//  Die Regelung schreibt, die Bedienung liest. Umgekehrt gibt es genau
//  drei Stellgroessen von aussen: Fahrbefehl, Freigabe, Richtungsumkehr.
//  Alles laeuft ueber eine kurze kritische Sektion; die Regelung wird
//  dadurch um wenige Mikrosekunden aufgehalten und nie blockiert.

struct Messwerte {
  float winkel_ist;     // Grad, null = Gleichgewicht
  float winkel_roh;     // Grad, unmittelbar aus der Beschleunigung
  float drehrate;       // Grad/s, ohne Kreiselnullpunkt
  float nullpunkt;      // Grad, von Schicht 4 nachgefuehrt
  float kreisel_null;   // Grad/s, Schaetzung des Kalman
  float v_ausgabe;      // m/s
  float weg;            // m
  float frequenz;       // Hz
  float gefordert;      // m/s2, groesste geforderte Beschleunigung
  bool  gesperrt;       // true = Sicherheitsabschaltung
  bool  im_test;        // true = Rampentest laeuft
  uint32_t takt_us;     // gemessene Rechenzeit eines Regeltakts
};

static volatile Messwerte g_mess = {};
static volatile float     g_fahrbefehl = 0.0f;   // m/s, von aussen
static volatile bool      g_freigabe   = true;
static volatile bool      g_umkehr     = false;
// A_MAX ist im Betrieb verstellbar, damit sie sich am Geraet messen
// laesst, ohne jedes Mal neu aufzuspielen. Der zuletzt gesetzte Wert
// gehoert danach in A_MAX_VORGABE oben.
static volatile float     g_a_max      = A_MAX_VORGABE;
// Rampentest: Zahl der noch zu fahrenden Halbwellen, 0 = aus
static volatile int       g_test_rest  = 0;
static volatile float     g_test_v     = 0.20f;  // m/s Umkehrgeschwindigkeit
static portMUX_TYPE       g_mux = portMUX_INITIALIZER_UNLOCKED;

// =====================================================================
//  3  SENSOR - unmittelbarer Zugriff auf den MPU6050
// =====================================================================
//  Kein Umweg ueber eine Bibliothek: sechs Achsen in einem Zug, das
//  kostet bei 400 kHz rund 0,4 ms und ist damit im 4-ms-Takt sicher.

struct Rohwerte { float ax, ay, az, gx, gy, gz; };

static void mpuStarten() {
  auto schreibe = [](uint8_t reg, uint8_t wert) {
    Wire.beginTransmission(MPU_ADR);
    Wire.write(reg); Wire.write(wert);
    Wire.endTransmission();
  };
  schreibe(0x6B, 0x01);   // Ruhezustand aus, Takt vom X-Kreisel
  delay(100);
  schreibe(0x1B, 0x00);   // Kreisel +-250 Grad/s  -> 131 LSB je Grad/s
  schreibe(0x1C, 0x00);   // Beschleunigung +-2 g  -> 16384 LSB je g
  schreibe(0x1A, 0x03);   // Tiefpass 42 Hz, Laufzeit 4,8 ms
}

static bool mpuLesen(Rohwerte &r) {
  Wire.beginTransmission(MPU_ADR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADR, (uint8_t)14, (uint8_t)true) != 14)
    return false;
  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read();                 // Temperatur uebergehen
  int16_t gx = (Wire.read() << 8) | Wire.read();
  int16_t gy = (Wire.read() << 8) | Wire.read();
  int16_t gz = (Wire.read() << 8) | Wire.read();
  r.ax = ax / 16384.0f; r.ay = ay / 16384.0f; r.az = az / 16384.0f;
  r.gx = gx / 131.0f;   r.gy = gy / 131.0f;   r.gz = gz / 131.0f;
  return true;
}

// =====================================================================
//  4  SCHICHT 1 - WINKELERFASSUNG
// =====================================================================
//  Der Beschleunigungsmesser liefert einen absoluten, aber langsamen und
//  verfaelschten Winkel; der Kreisel liefert die schnelle Aenderung, hat
//  aber einen Nullpunktfehler. Der Kalman fuehrt beide zusammen und
//  schaetzt den Kreiselnullpunkt als eigene Groesse mit.
//
//  Zwei Dinge sind gegenueber der bisherigen Fassung geaendert, beide
//  am Modell belegt:
//
//  1) Die Fehlerkovarianz P startet auf ihrem Endwert. Mit P = 0 ist die
//     Verstaerkung anfangs null - der Filter hoert dem Beschleunigungs-
//     messer rund vier Sekunden lang nicht zu und haelt einen
//     Anfangsfehler fest.
//
//  2) R_MESS ist gross. Der Sensor kann Neigung und Beschleunigung nicht
//     unterscheiden: 2 m/s2 melden sich als 11,5 Grad Scheinneigung. Mit
//     dem bisherigen R = 0,03 stand die Haelfte davon schon nach 0,15 s
//     im gemeldeten Winkel, und der Kreis war dadurch schwach instabil
//     (groesster Eigenwertbetrag 1,0045). Mit dem grossen R traegt der
//     Beschleunigungsmesser nur noch den langsamen Nullpunkt bei; den
//     Winkel im Regelkreis liefert der Kreisel.
//
//  Erwogen und verworfen wurde, die eigene Beschleunigung abzuziehen -
//  sie ist bei Schrittmotoren als Ableitung der ausgegebenen Frequenz
//  bekannt. Mit dem langsamen Filter aendert sie die Stabilitaetsreserve
//  nur in der vierten Stelle, verlangt aber eine Verbindung von Schicht 3
//  zurueck nach Schicht 1, und ihr Vorzeichen haengt an der Einbaulage
//  des Sensors. Bei verdrehter Lage wird aus der Korrektur eine
//  Mitkopplung und der Kreis instabil. Sie ist deshalb nicht eingebaut.
//  Nachzulesen in ENTWURF_Segway_Regelung.md, Abschnitt 6.1.

class Winkelerfassung {
public:
  void beiwerte(float q_winkel, float q_null, float r_mess) {
    Q_WINKEL = q_winkel; Q_NULL = q_null; R_MESS = r_mess;
  }

  // Fehlerkovarianz auf den eingeschwungenen Wert setzen.
  // Die Zahl der Durchlaeufe ist NICHT fest: bei grossem R_MESS
  // konvergiert die Gleichung langsamer, und eine feste Zahl laesst dann
  // einen kleinen Rest stehen. Gerechnet wird bis zum Stillstand.
  // Der Aufwand faellt einmal beim Einschalten an, wenige Millisekunden.
  void eingeschwungenStarten(float dt) {
    double P00 = 0, P01 = 0, P10 = 0, P11 = 0, K0_vor = -1.0;
    for (int i = 0; i < 200000; i++) {
      P00 += dt * (dt * P11 - P01 - P10 + Q_WINKEL);
      P01 -= dt * P11;
      P10 -= dt * P11;
      P11 += Q_NULL * dt;
      double S = P00 + R_MESS;
      double K0 = P00 / S, K1 = P10 / S;
      double t00 = P00, t01 = P01;
      P00 -= K0 * t00; P01 -= K0 * t01;
      P10 -= K1 * t00; P11 -= K1 * t01;
      if (i > 10 && fabs(K0 - K0_vor) < 1e-14) break;
      K0_vor = K0;
    }
    m_P00 = P00; m_P01 = P01; m_P10 = P10; m_P11 = P11;
  }

  void start(float winkel_grad, float dt) {
    m_winkel = winkel_grad;
    m_kreisel_null = 0.0f;
    eingeschwungenStarten(dt);
  }

  // Eingang : Rohwinkel [Grad], Drehrate [Grad/s], Schrittweite [s]
  // Ausgang : Istwinkel [Grad] gegen den nachgefuehrten Nullpunkt
  float rechne(float roh_grad, float drehrate_grad, float dt) {
    // ---- Kalman ----
    float rate = drehrate_grad - m_kreisel_null;
    m_winkel += dt * rate;
    m_P00 += dt * (dt * m_P11 - m_P01 - m_P10 + Q_WINKEL);
    m_P01 -= dt * m_P11;
    m_P10 -= dt * m_P11;
    m_P11 += Q_NULL * dt;
    float S = m_P00 + R_MESS;
    float K0 = m_P00 / S, K1 = m_P10 / S;
    float y = roh_grad - m_winkel;
    m_winkel += K0 * y;
    m_kreisel_null += K1 * y;
    float t00 = m_P00, t01 = m_P01;
    m_P00 -= K0 * t00; m_P01 -= K0 * t01;
    m_P10 -= K1 * t00; m_P11 -= K1 * t01;

    m_drehrate = drehrate_grad - m_kreisel_null;
    return m_winkel - nullpunkt;
  }

  float nullpunkt = 0.0f;          // Grad, von Schicht 4 gesetzt
  float drehrate() const { return m_drehrate; }      // Grad/s
  float kreiselNull() const { return m_kreisel_null; }

  // Diese drei bestimmen, wie schnell der Filter ist. R_MESS ist der
  // wichtigste Wert: er sagt, wie sehr dem Beschleunigungsmesser
  // geglaubt wird. Gross = langsam und stur, klein = schnell und
  // anfaellig gegen die eigene Beschleunigung.
  float Q_WINKEL = 0.001f;
  float Q_NULL   = 0.003f;
  float R_MESS   = 1.0f;

private:
  float m_winkel = 0, m_kreisel_null = 0, m_drehrate = 0;
  float m_P00 = 0, m_P01 = 0, m_P10 = 0, m_P11 = 0;
};

// =====================================================================
//  5  SCHICHT 2 - WINKELREGLER
// =====================================================================
//  Normalform, alles in physikalischen Einheiten:
//
//      v = K * ( e + 1/Tn INT e dt + Tv de/dt )        [m/s]
//
//  K  in m/s je rad, Tn und Tv in Sekunden. Damit ueberleben die
//  Beiwerte jede Aenderung an Mikroschrittteilung, Radgroesse und Takt -
//  anders als Zahlen ohne Einheit, in denen die Abtastrate versteckt ist.
//
//  Zwei Punkte, die am Modell nachgewiesen sind:
//
//  * Die Strecke ist geschwindigkeitsgefuehrt, nicht kraftgefuehrt. Der
//    linearisierte Kreis lautet
//        (J + m l kd) th'' + m l kp th' + m l (ki - g) th = 0
//    Aufrichten kann also nur der INTEGRALANTEIL, und zwar nur, wenn
//        ki = K/Tn > g = 9,81 m/s je rad und Sekunde.
//    Der P-Anteil daempft, der D-Anteil wirkt wie zusaetzliche Traegheit.
//
//  * Der D-Anteil kommt vom Kreisel, nicht aus der Differenz des
//    Winkels. Die Drehrate liegt ohnehin vor; sie zu benutzen spart das
//    Differenzieren eines verrauschten Signals.

class Winkelregler {
public:
  void ruecksetzen() { m_integral = 0.0f; }

  // Eingang : Istwinkel [rad], Drehrate [rad/s], Grenze [m/s]
  // Ausgang : Radgeschwindigkeit [m/s]
  float rechne(float winkel_ist, float drehrate, float grenze, float dt) {
    float anteil_p = K * winkel_ist;
    float anteil_d = K * TV * drehrate;
    float roh = anteil_p + m_integral + anteil_d;

    // Anti-Windup: in der Begrenzung laeuft der Integrator nicht weiter,
    // ausser er arbeitet gerade aus ihr heraus.
    if (fabsf(roh) < grenze || (roh * winkel_ist) < 0.0f) {
      m_integral += (K / TN) * winkel_ist * dt;
      m_integral = constrain(m_integral, -grenze, grenze);
    }
    float v = anteil_p + m_integral + anteil_d;
    return constrain(v, -grenze, grenze);
  }

  float K  = 0.0f;    // m/s je rad
  float TN = 0.0f;    // s
  float TV = 0.0f;    // s

private:
  float m_integral = 0.0f;
};

// =====================================================================
//  6  SCHICHT 3 - MOTOREINHEIT
// =====================================================================
//  Sie setzt die Stellgroesse um und ist die einzige Stelle, die Hertz
//  und Meter miteinander verbindet. Deshalb kann sie Geschwindigkeit und
//  Weg melden, ohne dass ein Geber verbaut waere: solange kein Schritt
//  verloren geht, IST die ausgegebene Frequenz die Radgeschwindigkeit.
//
//  Gemeldet wird, was wirklich ausgegeben wird - auch die Null in der
//  Totzone. Sonst rechnet Schicht 4 mit einer Bewegung, die es nicht
//  gibt, und verschiebt den Nullpunkt ins Leere.
//
//  Zur Rampe: setAcceleration begrenzt, wie schnell die Frequenz
//  geaendert werden darf. Am Modell haengt der Fangbereich unmittelbar
//  daran - 50000 Schritte/s2 ergeben 9 Grad, 80000 ergeben ueber 20.
//  Die Rampe darf aber nicht groesser sein, als das Motormoment
//  hergibt, sonst gehen Schritte verloren und die Grundannahme faellt.

class Motoreinheit {
public:
  void start() {
    m_engine.init();
    m_rechts = m_engine.stepperConnectToPin(STEP_R, DRIVER_RMT);
    m_links  = m_engine.stepperConnectToPin(STEP_L, DRIVER_RMT);
    if (!m_rechts || !m_links) { m_bereit = false; return; }
    m_rechts->setDirectionPin(DIR_R);
    m_links->setDirectionPin(DIR_L);
    // Der EN-Pin wird von Hand geschaltet und NICHT der Bibliothek
    // ueberlassen; so ist an jeder Stelle sichtbar, wann die Treiber
    // Strom bekommen.
    rampeNachfuehren();
    m_bereit = true;
  }

  void freigeben() {
    digitalWrite(EN_R, LOW);
    digitalWrite(EN_L, LOW);
  }

  // Die Rampe der Bibliothek wird bewusst hoeher gesetzt als A_MAX, damit
  // sie nicht ein zweites Mal begrenzt. Begrenzt wird in ausgeben(), wo
  // es nachvollziehbar ist und wo die gemeldete Geschwindigkeit entsteht.
  void rampeNachfuehren() {
    if (!m_rechts || !m_links) return;
    float a = g_a_max;
    if (a == m_a_gesetzt) return;
    int32_t schritte = (int32_t)(1.5f * a / SCHRITTWEITE);
    m_rechts->setAcceleration(schritte);
    m_links->setAcceleration(schritte);
    m_a_gesetzt = a;
  }

  void sperren() {
    if (m_bereit) {
      m_rechts->forceStopAndNewPosition(0);
      m_links->forceStopAndNewPosition(0);
    }
    digitalWrite(EN_R, HIGH);
    digitalWrite(EN_L, HIGH);
    m_v = 0.0f;
    m_f = 0.0f;
  }

  // Eingang : Radgeschwindigkeit [m/s]
  // Ausgang : tatsaechlich ausgegebene Geschwindigkeit [m/s]
  float ausgeben(float v_soll, float dt) {
    if (!m_bereit) { m_v = 0.0f; m_f = 0.0f; return 0.0f; }
    rampeNachfuehren();

    // Aenderungsgrenze: nur fordern, was die Motoren leisten koennen.
    // Sonst gehen Schritte verloren, und dann ist die ausgegebene
    // Frequenz nicht mehr die Radgeschwindigkeit - womit diese Schicht
    // und die Nullpunktkorrektur darueber ihre Grundlage verlieren.
    // Wie viel wirklich gefordert wurde, wird mitgeschrieben: liegt der
    // Wert dauernd an der Grenze, ist A_MAX zu klein gemessen.
    float a_gefordert = (v_soll - m_v) / dt;
    if (fabsf(a_gefordert) > m_gefordert) m_gefordert = fabsf(a_gefordert);
    float grenze = g_a_max;
    v_soll = constrain(v_soll, m_v - grenze * dt, m_v + grenze * dt);

    float f = v_soll / SCHRITTWEITE;
    f = constrain(f, -MAX_HZ, MAX_HZ);
    if (fabsf(f) < MIN_HZ) f = 0.0f;

    m_f = f;
    m_v = f * SCHRITTWEITE;
    m_weg += m_v * dt;

    if (f == 0.0f) {
      m_rechts->forceStopAndNewPosition(0);
      m_links->forceStopAndNewPosition(0);
      return m_v;
    }
    uint32_t betrag = (uint32_t)fabsf(f);
    m_rechts->setSpeedInHz(betrag);
    m_links->setSpeedInHz(betrag);
    if (f > 0.0f) { m_rechts->runForward();  m_links->runForward(); }
    else          { m_rechts->runBackward(); m_links->runBackward(); }
    return m_v;
  }

  void wegNullen() { m_weg = 0.0f; }
  float gefordert() const { return m_gefordert; }
  void gefordertNullen() { m_gefordert = 0.0f; }
  float v()   const { return m_v; }
  float weg() const { return m_weg; }
  float f()   const { return m_f; }
  bool bereit() const { return m_bereit; }

private:
  FastAccelStepperEngine m_engine = FastAccelStepperEngine();
  FastAccelStepper* m_rechts = nullptr;
  FastAccelStepper* m_links  = nullptr;
  bool  m_bereit = false;
  float m_v = 0.0f, m_weg = 0.0f, m_f = 0.0f;
  float m_gefordert = 0.0f;      // groesste geforderte Beschleunigung
  float m_a_gesetzt = -1.0f;     // zuletzt an die Bibliothek gegebene Rampe
};

// =====================================================================
//  7  SCHICHT 4 - DYNAMISCHE NULLPUNKTKORREKTUR
// =====================================================================
//  Die Kalibrierung beim Einschalten findet die SENKRECHTE. Gesucht ist
//  aber der GLEICHGEWICHTSPUNKT, und beide fallen nur zusammen, wenn der
//  Schwerpunkt genau ueber der Radachse liegt. Ein halber Millimeter
//  seitlicher Versatz sind bei l = 0,12 m schon 0,24 Grad - und 0,15
//  Grad genuegen ohne diese Korrektur zum Umfallen.
//
//  Der Nullpunkt laesst sich nicht messen, aber erschliessen: faehrt das
//  Fahrzeug weg, obwohl null befohlen ist, liegt er daneben. Richtung
//  und Betrag der Bewegung sind bekannt. Ein langsamer PI verschiebt ihn,
//  bis das Fahrzeug bei Istwinkel null wirklich steht.
//
//  Die Strecke von Sollwinkel zu Geschwindigkeit ist ein Integrator mit
//  der Verstaerkung g:   dv/dt = g * (theta - theta_gleichgewicht).
//  Daraus die Auslegung:  g*K = 2*zeta*wn  und  g*K/Tn = wn^2 .

class Nullpunktkorrektur {
public:
  void ruecksetzen() { m_integral = 0.0f; }

  // Eingang : ausgegebene Geschwindigkeit [m/s], Fahrbefehl [m/s]
  // Ausgang : Nullpunkt [Grad], den Schicht 1 abzieht
  // Der Integrator laeuft doppelt genau. Sein Zuwachs betraegt im
  // eingeschwungenen Zustand wenige 1e-9 rad je Takt, die Aufloesung von
  // float liegt dort bei 1,9e-9 - er bliebe sonst bei kleinen
  // Geschwindigkeitsfehlern stehen. Auf dem ESP32 kostet das ein paar
  // Mikrosekunden je Sekunde.
  float rechne(float v_ausgabe, float v_wunsch, float dt) {
    double e = (double)v_wunsch - (double)v_ausgabe;
    double roh = K * e + m_integral;
    if (fabs(roh) < GRENZE || (roh * e) < 0.0) {
      m_integral += ((double)K / TN) * e * dt;
      m_integral = constrain(m_integral, -(double)GRENZE, (double)GRENZE);
    }
    double wert = constrain(K * e + m_integral, -(double)GRENZE, (double)GRENZE);
    return (float)(wert * 57.2957795);
  }

  float K  = 0.0f;     // rad je m/s
  float TN = 0.0f;     // s
  static constexpr float GRENZE = 0.105f;   // rad, entspricht 6 Grad

private:
  double m_integral = 0.0;
};

// =====================================================================
//  8  AUFZEICHNUNG
// =====================================================================
//  Mitschnitt im Arbeitsspeicher, Ausgabe erst hinterher. Die Regelung
//  merkt davon nichts: im Takt wird nur in ein Feld geschrieben, die
//  serielle Ausgabe laeuft spaeter aus loop() auf dem anderen Kern.

// Der Mitschnitt liegt als Ganzzahl mit fester Teilung im Speicher. Als
// Gleitkomma waeren es 75 kB und der ESP32 haette keinen Platz mehr; so
// sind es 37 kB. Die Teilung ist feiner als jedes Rauschen, das gemessen
// werden soll.
#define LOG_N 3750                 // 30 s bei 125 Hz
static const float LOG_HZ = 125.0f;

static int16_t logWinkel[LOG_N];   // 0,01 Grad je Einheit
static int16_t logRoh[LOG_N];      // 0,01 Grad
static int16_t logRate[LOG_N];     // 0,1 Grad/s
static int16_t logFreq[LOG_N];     // 1 Hz
static int16_t logNull[LOG_N];     // 0,001 Grad
static int8_t  logLed[LOG_N];      // 1 = Synchron-LED an (Zeitmarke fuer die Kamera)
static volatile int g_blitz = 0;   // noch auszugebende Blitze; wird im Regeltakt abgearbeitet
static volatile int  logIndex  = -1;
static volatile bool logFertig = false;

static int16_t begrenzen(float wert) {
  if (wert >  32767.0f) return  32767;
  if (wert < -32768.0f) return -32768;
  return (int16_t)lroundf(wert);
}

static void logSchreiben(float winkel, float roh, float rate,
                         float freq, float null_grad) {
  static uint8_t teiler = 0;
  int i = logIndex;                 // einmal lesen, dann damit rechnen
  if (i < 0 || i >= LOG_N) return;
  if (++teiler < 2) return;         // jeden zweiten Takt -> 125 Hz
  teiler = 0;
  logWinkel[i] = begrenzen(winkel    * 100.0f);
  logRoh[i]    = begrenzen(roh       * 100.0f);
  logRate[i]   = begrenzen(rate      *  10.0f);
  logFreq[i]   = begrenzen(freq);
  logNull[i]   = begrenzen(null_grad * 1000.0f);
  logLed[i]    = digitalRead(LED_SYNC) ? 1 : 0;
  logIndex = i + 1;
  if (i + 1 >= LOG_N) logFertig = true;
}

static void logAusgeben() {
  Serial.println();
  Serial.println("### MITSCHNITT BEGINN");
  Serial.println("t_s;istwinkel_grad;rohwinkel_grad;drehrate_grad_s;"
                 "frequenz_hz;nullpunkt_grad;led");
  for (int i = 0; i < LOG_N; i++) {
    Serial.printf("%.4f;%.2f;%.2f;%.1f;%d;%.3f;%d\n",
                  i / LOG_HZ, logWinkel[i] * 0.01f, logRoh[i] * 0.01f,
                  logRate[i] * 0.1f, (int)logFreq[i], logNull[i] * 0.001f,
                  (int)logLed[i]);
    if ((i & 0x3F) == 0) delay(1);       // dem Netzstapel Luft lassen
  }
  Serial.println("### MITSCHNITT ENDE");
}

// =====================================================================
//  9  DIE VIER SCHICHTEN ALS EINE AUFGABE
// =====================================================================

static Winkelerfassung    erfassung;
static Winkelregler       regler;
static Motoreinheit       motor;
static Nullpunktkorrektur nullpunkt;
static WebServer          server(80);
static TaskHandle_t       h_regelung = nullptr;
static TaskHandle_t       h_bedienung = nullptr;

// Beim Einschalten werden ZWEI Nullpunkte gemessen, nicht einer:
//
//   Senkrechte   aus dem Beschleunigungsmesser. Sie erfasst die Schiefe
//                der Sensormontage.
//   Kreisel      der Nullpunkt der Drehrate. Der MPU6050 hat davon laut
//                Datenblatt bis 20 Grad/s. Der Kalman findet ihn zwar
//                selbst, braucht dafuer aber rund zwanzig Sekunden - und
//                so lange steht der Fehler im gemeldeten Winkel. Am
//                Modell faellt der Segway ab 4 Grad/s. Kalibriert bleiben
//                aus 200 Messungen etwa 0,004 Grad/s uebrig.
//
// Was beide NICHT erfassen, ist die Mechanik: der Schwerpunkt liegt nie
// genau ueber der Achse. Dafuer ist Schicht 4 da.
static float g_senkrecht   = 0.0f;   // Grad
static float g_kreiselNull = 0.0f;   // Grad/s

static void nullpunkteMessen() {
  float summe_winkel = 0.0f, summe_rate = 0.0f;
  int gute = 0;
  for (int i = 0; i < 200; i++) {
    Rohwerte r;
    if (mpuLesen(r)) {
      summe_winkel += atan2f(r.ay, sqrtf(r.ax * r.ax + r.az * r.az))
                      * 57.2957795f;
      summe_rate += r.gx;
      gute++;
    }
    delay(5);
  }
  if (gute > 0) {
    g_senkrecht   = summe_winkel / gute;
    g_kreiselNull = summe_rate / gute;
  }
}

// ---------------------------------------------------------------------
//  Der Regeltakt. Reihenfolge fest, keine Ausgabe, keine Wartezeit.
// ---------------------------------------------------------------------
static void taskRegelung(void*) {
  TickType_t weckzeit = xTaskGetTickCount();
  bool gesperrt = true;
  uint16_t sensorfehler = 0;
  uint16_t ruhig = 0;          // Takte innerhalb des Freigabefensters
  uint32_t t_vorher = micros();

  for (;;) {
    uint32_t t0 = micros();
    float DT = constrain((t0 - t_vorher) * 1e-6f, DT_MIN, DT_MAX);
    t_vorher = t0;

    Rohwerte r;
    if (!mpuLesen(r)) {
      // Ein einzelner verlorener Zug darf nicht zum Sturz fuehren, ein
      // dauerhafter Ausfall aber auch nicht zum Weglaufen. Nach fuenf
      // Fehlversuchen in Folge wird gesperrt.
      if (++sensorfehler >= 5 && !gesperrt) {
        motor.sperren();
        regler.ruecksetzen();
        gesperrt = true;
      }
      vTaskDelayUntil(&weckzeit, pdMS_TO_TICKS(TAKT_MS));
      continue;
    }
    sensorfehler = 0;

    // ---- Vorgaben von aussen (stoeren den Ablauf nicht) ----
    float fahrbefehl;
    bool freigabe, umkehr;
    portENTER_CRITICAL(&g_mux);
    fahrbefehl = g_fahrbefehl;
    freigabe   = g_freigabe;
    umkehr     = g_umkehr;
    portEXIT_CRITICAL(&g_mux);

    // ---- Rampentest zum Messen von A_MAX ----
    // Er umgeht die vier Schichten und stellt die Motoreinheit
    // unmittelbar. Nur bei ausgeschalteter Freigabe erlaubt: das Fahrzeug
    // muss dabei auf dem Ruecken liegen, die Raeder frei.
    if (g_test_rest > 0) {
      if (freigabe) {
        g_test_rest = 0;                 // Freigabe hebt den Test auf
      } else {
        if (gesperrt) { motor.freigeben(); gesperrt = false; }
        // Dreieckverlauf: von -v auf +v und zurueck, mit A_MAX
        static float ziel = 0.0f;
        if (ziel == 0.0f) ziel = g_test_v;
        motor.ausgeben(ziel, DT);
        if (fabsf(motor.v() - ziel) < 1e-4f) {
          ziel = -ziel;
          g_test_rest = g_test_rest - 1;
          if (g_test_rest <= 0) {
            motor.sperren();
            gesperrt = true;
            ziel = 0.0f;
            Serial.printf("[TEST] fertig bei A_MAX = %.2f m/s2\n", g_a_max);
          }
        }
        portENTER_CRITICAL(&g_mux);
        g_mess.v_ausgabe = motor.v();
        g_mess.frequenz  = motor.f();
        g_mess.gefordert = motor.gefordert();
        g_mess.gesperrt  = gesperrt;
        g_mess.im_test   = true;
        g_mess.takt_us   = micros() - t0;
        portEXIT_CRITICAL(&g_mux);
        vTaskDelayUntil(&weckzeit, pdMS_TO_TICKS(TAKT_MS));
        continue;
      }
    }

    // ---- Schicht 4: Nullpunkt nachfuehren (liegt darueber) ----
    // Bei gesperrten Motoren wird nicht nachgefuehrt: es gibt dann keine
    // Bewegung, aus der sich etwas erschliessen liesse, und ein
    // Fahrbefehl wuerde den Integrator nur volllaufen lassen.
    if (!gesperrt)
      erfassung.nullpunkt = nullpunkt.rechne(motor.v(), fahrbefehl, DT);

    // ---- Schicht 1: Winkelerfassung ----
    // Die Richtungsumkehr wirkt HIER, am Sensor - nicht am Motor. Nur so
    // zeigen Winkel, Drehrate und ausgegebene Geschwindigkeit alle in
    // dieselbe Richtung. Saesse sie in der Motoreinheit, dann meldete
    // Schicht 3 eine Geschwindigkeit mit falschem Vorzeichen, und
    // Schicht 4 verschoebe den Nullpunkt in die falsche Richtung - das
    // Fahrzeug liefe weg statt stehenzubleiben.
    float vz = umkehr ? -1.0f : 1.0f;
    float roh = vz * (atan2f(r.ay, sqrtf(r.ax * r.ax + r.az * r.az))
                      * 57.2957795f - g_senkrecht);
    float winkel_grad = erfassung.rechne(roh, vz * (r.gx - g_kreiselNull),
                                         DT);
    float winkel_absolut = winkel_grad + erfassung.nullpunkt;

    // ---- Sicherheitsabschaltung und Wiederfreigabe ----
    if (fabsf(winkel_absolut) < FREI_WINKEL &&
        fabsf(erfassung.drehrate()) < FREI_RATE)
      ruhig++;
    else
      ruhig = 0;

    if (fabsf(winkel_absolut) > KIPP_GRENZE || !freigabe) {
      if (!gesperrt) {
        motor.sperren();
        regler.ruecksetzen();
        motor.wegNullen();
        gesperrt = true;
        // Der gelernte Nullpunkt bleibt stehen. Er beschreibt die Lage
        // des Schwerpunkts, und die aendert sich durch das Umfallen
        // nicht. Ihn wegzuwerfen hiesse, nach jedem Aufheben wieder
        // zwanzig Sekunden lang zu suchen. Zuruecksetzen laesst er sich
        // von Hand ueber /nullpunkt, wenn am Aufbau etwas geaendert wurde.
      }
    } else if (gesperrt && ruhig < FREI_TAKTE) {
      // Noch nicht ruhig genug: Motoren bleiben stromlos. So laeuft das
      // Fahrzeug nicht an, waehrend es noch faellt oder getragen wird.
    } else {
      if (gesperrt) {
        motor.freigeben();
        motor.wegNullen();
        gesperrt = false;
      }

      // ---- Schicht 2: Winkelregler ----
      float v_soll = regler.rechne(winkel_grad * 0.0174532925f,
                                   erfassung.drehrate() * 0.0174532925f,
                                   V_MAX, DT);

      // ---- Schicht 3: Motoreinheit ----
      motor.ausgeben(v_soll, DT);
    }

    // ---- Messwerte weiterreichen (kurze kritische Sektion) ----
    portENTER_CRITICAL(&g_mux);
    g_mess.winkel_ist   = winkel_grad;
    g_mess.winkel_roh   = roh;
    g_mess.drehrate     = erfassung.drehrate();
    g_mess.nullpunkt    = erfassung.nullpunkt;
    g_mess.kreisel_null = erfassung.kreiselNull() + g_kreiselNull;
    g_mess.v_ausgabe    = motor.v();
    g_mess.weg          = motor.weg();
    g_mess.frequenz     = motor.f();
    g_mess.gefordert    = motor.gefordert();
    g_mess.gesperrt     = gesperrt;
    g_mess.im_test      = false;
    g_mess.takt_us      = micros() - t0;
    portEXIT_CRITICAL(&g_mux);

    // Aufzeichnung: nur ein Schreiben in ein Feld, wenige Nanosekunden.
    // Sie gehoert in den Takt, sonst waeren die Abstaende ungleich und
    // der Mitschnitt fuer eine Auswertung wertlos. Die serielle Ausgabe
    // geschieht spaeter aus loop() auf dem anderen Kern.
    // Synchronblitz: die LED wird hier im Regeltakt geschaltet, damit ihr
    // Zustand mit derselben Uhr in den Mitschnitt kommt wie die Messwerte.
    // Ein Blitz = 12 Takte an (48 ms), 38 Takte aus (152 ms); dreimal.
    {
      static int blitzTakt = 0;
      if (g_blitz > 0) {
        digitalWrite(LED_SYNC, blitzTakt < 12 ? HIGH : LOW);
        if (++blitzTakt >= 50) { blitzTakt = 0; g_blitz--; if (g_blitz == 0) digitalWrite(LED_SYNC, LOW); }
      }
    }
    logSchreiben(winkel_grad, roh, erfassung.drehrate(), motor.f(),
                 erfassung.nullpunkt);

    vTaskDelayUntil(&weckzeit, pdMS_TO_TICKS(TAKT_MS));
  }
}

// =====================================================================
//  10  BEDIENUNG
// =====================================================================
//  Sie liest nur die weitergereichten Zahlen und setzt drei Stellgroessen.
//  In den Regelablauf greift sie nicht ein.

static const char SEITE[] PROGMEM = R"HTML(
<!doctype html><html><head><meta charset="utf-8">
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Segway</title><style>
body{font-family:system-ui,sans-serif;margin:0;padding:16px;background:#111;color:#eee}
h1{font-size:20px;margin:0 0 12px}
.z{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #333}
.w{font-variant-numeric:tabular-nums;color:#8cf}
button{font-size:16px;padding:10px 16px;margin:6px 6px 0 0;border:0;border-radius:6px;background:#2a4;color:#fff}
button.aus{background:#a33}
input[type=range]{width:100%}
</style></head><body>
<h1>Segway</h1>
<div class=z><span>Istwinkel</span><span class=w id=aWinkel>--</span></div>
<div class=z><span>Nullpunkt</span><span class=w id=aNull>--</span></div>
<div class=z><span>Drehrate</span><span class=w id=aRate>--</span></div>
<div class=z><span>Kreiselnullpunkt</span><span class=w id=aKreisel>--</span></div>
<div class=z><span>Geschwindigkeit</span><span class=w id=aTempo>--</span></div>
<div class=z><span>Weg</span><span class=w id=aWeg>--</span></div>
<div class=z><span>Rechenzeit je Takt</span><span class=w id=aTakt>--</span></div>
<div class=z><span>Zustand</span><span class=w id=aZustand>--</span></div>
<div class=z><span>A_MAX (Rampe)</span><span class=w id=aRampe>--</span></div>
<div class=z><span>gefordert (Spitze)</span><span class=w id=aGef>--</span></div>
<p>Fahrbefehl <span id=aFahr>0.00</span> m/s<br>
<input type=range id=schieber min=-40 max=40 value=0 step=1></p>
<p>A_MAX <span id=aSoll>6.5</span> m/s&sup2;<br>
<input type=range id=rampe min=10 max=300 value=65 step=5></p>
<button onclick="ruf('/frei')">Freigabe</button>
<button class=aus onclick="ruf('/stop')">Halt</button>
<button onclick="ruf('/umkehr')">Richtung</button>
<button onclick="ruf('/nullpunkt')">Nullpunkt neu</button>
<button onclick="ruf('/log')">Mitschnitt</button>
<button onclick="ruf('/rampentest')">Rampentest</button>
<button onclick="ruf('/spitze')">Spitze zuruecksetzen</button>
<script>
const e=n=>document.getElementById(n);
function ruf(u){fetch(u)}
e('schieber').oninput=function(){const v=this.value/50;
  e('aFahr').textContent=v.toFixed(2); fetch('/fahr?v='+v)};
e('rampe').oninput=function(){const a=this.value/10;
  e('aSoll').textContent=a.toFixed(1); fetch('/rampe?a='+a)};
setInterval(async()=>{
 try{const d=await(await fetch('/werte')).json();
 e('aWinkel').textContent=d.w.toFixed(3)+' Grad';
 e('aNull').textContent=d.n.toFixed(3)+' Grad';
 e('aRate').textContent=d.r.toFixed(2)+' Grad/s';
 e('aKreisel').textContent=d.k.toFixed(3)+' Grad/s';
 e('aTempo').textContent=d.v.toFixed(3)+' m/s';
 e('aWeg').textContent=d.s.toFixed(2)+' m';
 e('aTakt').textContent=d.t+' us';
 e('aRampe').textContent=d.a.toFixed(2)+' m/s2';
 e('aGef').textContent=d.q.toFixed(2)+' m/s2';
 e('aZustand').textContent=d.t2?'Rampentest':(d.g?'gesperrt':'laeuft');}catch(x){}},250);
</script></body></html>)HTML";

// Die Messwerte werden in einem Zug kopiert, damit die Anzeige nicht
// Zahlen aus zwei verschiedenen Takten mischt.
static Messwerte messwerteHolen() {
  Messwerte m;
  portENTER_CRITICAL(&g_mux);
  memcpy(&m, (const void*)&g_mess, sizeof(Messwerte));
  portEXIT_CRITICAL(&g_mux);
  return m;
}

static void werteSenden() {
  Messwerte m = messwerteHolen();
  char puffer[320];
  snprintf(puffer, sizeof(puffer),
           "{\"w\":%.4f,\"n\":%.4f,\"r\":%.3f,\"k\":%.4f,"
           "\"v\":%.4f,\"s\":%.3f,\"t\":%lu,\"g\":%d,"
           "\"a\":%.3f,\"q\":%.3f,\"t2\":%d}",
           m.winkel_ist, m.nullpunkt, m.drehrate, m.kreisel_null,
           m.v_ausgabe, m.weg, (unsigned long)m.takt_us, m.gesperrt ? 1 : 0,
           g_a_max, m.gefordert, m.im_test ? 1 : 0);
  server.send(200, "application/json", puffer);
}

// ---------------------------------------------------------------------
//  Bedienung, Netz und serielle Ausgabe - alles auf Kern 0
// ---------------------------------------------------------------------
static void taskBedienung(void*) {
  for (;;) {
    ArduinoOTA.handle();
    server.handleClient();
    if (logFertig) {
      logFertig = false;
      logIndex = -1;
      logAusgeben();
    }
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}


// =====================================================================
//  11  BEIWERTE
// =====================================================================
//  Alle Zahlen stammen aus der Auslegung am Modell. Der Entwurf wurde
//  nicht am Nennfall bewertet, sondern am schlechtesten Fall einer
//  Unsicherheitsspanne:
//
//     Masse            0,25 bis 0,50 kg
//     Schwerpunkthoehe 0,08 bis 0,18 m
//     Traegheitsmoment 0,7 bis 1,5 mal Stabnaeherung
//     Treiberverzug    1 bis 6 ms
//     Sensoreinbauhoehe 0 bis 0,10 m
//
//  Gefordert war Stabilitaet in JEDER Ecke dieser Spanne. Unter allen
//  Entwuerfen, die das erfuellen, wurde der mit der groessten
//  Verstaerkungsreserve gewaehlt.
//
//  Ergebnis der Suche: von 12000 gewuerfelten Entwuerfen sind 5297 in
//  jeder Ecke der Spanne stabil; dieser hat die groesste symmetrische
//  Reserve. Die Beiwerte duerfen um den Faktor 2.12 steigen und auf das
//  0.46-fache sinken, bevor der Kreis instabil wird - im SCHLECHTESTEN
//  Fall der Spanne, nicht im Nennfall.

static const float Q_WINKEL_WERT = 0.001f;
static const float Q_NULL_WERT   = 0.003f;
static const float R_MESS_WERT   = 309.301675f;
static const float REGLER_K      = 2.325385f;    // m/s je rad
static const float REGLER_TN     = 0.086638f;  // s
static const float REGLER_TV     = 0.008766f;  // s
static const float NULL_K        = 0.081265f;   // rad je m/s
static const float NULL_TN       = 2.272260f;    // s

static void beiwerteSetzen() {
  erfassung.beiwerte(Q_WINKEL_WERT, Q_NULL_WERT, R_MESS_WERT);
  regler.K  = REGLER_K;
  regler.TN = REGLER_TN;
  regler.TV = REGLER_TV;
  nullpunkt.K  = NULL_K;
  nullpunkt.TN = NULL_TN;
}

// =====================================================================
//  12  START UND HAUPTSCHLEIFE
// =====================================================================

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("Segway - Regelung in vier Schichten");

  pinMode(EN_R, OUTPUT); pinMode(EN_L, OUTPUT);
  pinMode(LED_SYNC, OUTPUT); digitalWrite(LED_SYNC, LOW);
  digitalWrite(EN_R, HIGH); digitalWrite(EN_L, HIGH);   // Treiber aus

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);
  mpuStarten();

  // ---- Beiwerte eintragen (Herkunft: Auslegung am Modell) ----
  beiwerteSetzen();

  // ---- Senkrechte messen, Filter eingeschwungen starten ----
  Serial.println("Nullpunkte messen - senkrecht und ruhig halten ...");
  nullpunkteMessen();
  Serial.printf("Senkrechte %.3f Grad, Kreiselnullpunkt %.3f Grad/s\n",
                g_senkrecht, g_kreiselNull);
  erfassung.start(0.0f, DT_SOLL);
  nullpunkt.ruecksetzen();
  regler.ruecksetzen();

  motor.start();
  if (!motor.bereit()) Serial.println("ACHTUNG: Schrittmotortreiber meldet sich nicht");

  // ---- Netz, OTA, Bedienung ----
  WiFi.mode(WIFI_STA);
  WiFi.begin(WLAN_NAME, WLAN_WORT);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("Bedienung: http://%s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("kein Netz - Regelung laeuft trotzdem");

  ArduinoOTA.setHostname(OTA_NAME);
  ArduinoOTA.begin();
  digitalWrite(LED_SYNC, HIGH); delay(300); digitalWrite(LED_SYNC, LOW);   // ein Blitz: Netz steht, OTA bereit

  server.on("/", []() { server.send_P(200, "text/html", SEITE); });
  server.on("/werte", werteSenden);
  server.on("/frei", []() {
    portENTER_CRITICAL(&g_mux); g_freigabe = true; portEXIT_CRITICAL(&g_mux);
    server.send(200, "text/plain", "frei");
  });
  server.on("/stop", []() {
    portENTER_CRITICAL(&g_mux); g_freigabe = false; portEXIT_CRITICAL(&g_mux);
    server.send(200, "text/plain", "halt");
  });
  server.on("/rampe", []() {
    // A_MAX im Betrieb setzen. Der gefundene Wert gehoert danach in
    // A_MAX_VORGABE, damit er das Einschalten ueberlebt.
    float a = server.hasArg("a") ? server.arg("a").toFloat() : A_MAX_VORGABE;
    a = constrain(a, A_MAX_KLEINST, A_MAX_GROESST);
    portENTER_CRITICAL(&g_mux); g_a_max = a; portEXIT_CRITICAL(&g_mux);
    Serial.printf("[RAMPE] A_MAX = %.2f m/s2 (entspricht setAcceleration %ld)\n",
                  a, (long)(a / SCHRITTWEITE));
    server.send(200, "text/plain", "A_MAX gesetzt");
  });
  server.on("/rampentest", []() {
    // Zehn Richtungswechsel mit der eingestellten Rampe. Nur bei
    // ausgeschalteter Freigabe - das Fahrzeug muss auf dem Ruecken liegen.
    bool frei;
    portENTER_CRITICAL(&g_mux); frei = g_freigabe; portEXIT_CRITICAL(&g_mux);
    if (frei) {
      server.send(200, "text/plain",
                  "Erst Halt druecken - der Test laeuft nur mit freien Raedern");
      return;
    }
    float v = server.hasArg("v") ? server.arg("v").toFloat() : 0.20f;
    portENTER_CRITICAL(&g_mux);
    g_test_v = constrain(v, 0.02f, V_MAX);
    g_test_rest = 10;
    portEXIT_CRITICAL(&g_mux);
    Serial.printf("[TEST] zehn Wechsel mit A_MAX = %.2f m/s2\n", g_a_max);
    server.send(200, "text/plain", "Rampentest laeuft");
  });
  server.on("/spitze", []() {
    motor.gefordertNullen();
    server.send(200, "text/plain", "Spitzenwert zurueckgesetzt");
  });
  server.on("/nullpunkt", []() {
    // Den gelernten Nullpunkt verwerfen. Sinnvoll, wenn am Aufbau etwas
    // verschoben wurde - dann stimmt der alte Wert nicht mehr.
    nullpunkt.ruecksetzen();
    erfassung.nullpunkt = 0.0f;
    server.send(200, "text/plain", "Nullpunkt zurueckgesetzt");
  });
  server.on("/umkehr", []() {
    portENTER_CRITICAL(&g_mux); g_umkehr = !g_umkehr; portEXIT_CRITICAL(&g_mux);
    server.send(200, "text/plain", "umgekehrt");
  });
  server.on("/fahr", []() {
    float v = server.hasArg("v") ? server.arg("v").toFloat() : 0.0f;
    v = constrain(v, -0.5f, 0.5f);
    portENTER_CRITICAL(&g_mux); g_fahrbefehl = v; portEXIT_CRITICAL(&g_mux);
    server.send(200, "text/plain", "ok");
  });
  server.on("/log", []() {
    logFertig = false; logIndex = 0; g_blitz = 3;        // drei Blitze zu Beginn des Mitschnitts
    server.send(200, "text/plain", "Mitschnitt laeuft - 30 s stehen lassen");
  });
  server.onNotFound([]() { server.send_P(200, "text/html", SEITE); });
  server.begin();

  // ---- Aufgabenverteilung ----
  //  Kern 1: nur die Regelung. Sie ist die einzige Aufgabe mit fester
  //          Frist und bekommt den Kern fuer sich.
  //  Kern 0: Bedienung, Netz, serielle Ausgabe. Alles, was warten darf.
  //
  //  Wichtig: die Arduino-Hauptschleife loop() laeuft von Haus aus
  //  ebenfalls auf Kern 1. Sie bleibt deshalb leer; die Bedienung
  //  bekommt eine eigene Aufgabe auf Kern 0. Sonst teilten sich
  //  Regelung und Webserver einen Kern - genau das, was nicht sein soll.
  xTaskCreatePinnedToCore(taskBedienung, "Bedienung", 8192, nullptr,
                          1, &h_bedienung, 0);
  xTaskCreatePinnedToCore(taskRegelung, "Regelung", 4096, nullptr,
                          10, &h_regelung, 1);
  Serial.println("Regelung auf Kern 1 mit 250 Hz, Bedienung auf Kern 0");
}

void loop() {
  // Bleibt leer: loop() liegt auf Kern 1, und dieser Kern gehoert der
  // Regelung. Eine lange Wartezeit statt eines Leerlaufs, damit die
  // Aufgabe den Kern gar nicht erst anfasst.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
