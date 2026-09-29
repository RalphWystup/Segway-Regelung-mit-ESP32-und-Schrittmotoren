// Segway-Labor — das Rechenmodell im Browser (Stufe 1). Zeile für Zeile aus Modell/segway_modell.py übernommen:
// Strecke (Feinschritte), Sensorkette (42-Hz-Tiefpass, Rohwinkel aus der Beschleunigung, Rauschen, Kreiselnullpunkt),
// Kalman-Filter und die vier Schichten des Entwurfs; Reihenfolge je Takt wie in der Firmware. Geprüft gegen das
// Python-Modell mit Labor/pruefe_labor_modell.mjs (dieselben Eingaben, Abweichung < 1e-6 Grad).
//
// Alle Winkel intern in rad (Strecke) bzw. Grad (Sensor, Kalman, Firmware-Schichten) — genau wie im Python-Modell.
'use strict';
const SEGWAY = (function () {
  const G2R = Math.PI / 180, R2G = 180 / Math.PI;

  // ------------------------------------------------------------- Parameter (Herkunft je Zeile im Manuskript)
  function parameter(aenderungen) {
    const p = {
      m: 1.248, l: 0.04448, J: null, d: 0.002, g: 9.81, s_versatz: 0.0,      // Strecke (gemessen / Konstruktion)
      r_rad: 0.032, Ns: 1600, a_max: 6.48, MIN_SPEED: 0, MAX_SPEED: 6000, tau_mot: 0.002,   // Antrieb (Firmware)
      f_gitter: 250, f_dmp: 250, feinschritte: 32, t_dlpf: 0.0048,           // Takt und Sensor
      sensor_w: 0.071, sensor_u: 0.039, rausch_grad: 0.05, gyro_rausch: 0.05, gyro_bias: 0.05, mess_versatz: 0.0,
      Q_ANGLE: 0.001, Q_BIAS: 0.003, R_MEASURE: 309.301675,                  // Kalman (Firmware)
      N_K: 2.325385, N_TN: 0.086638, N_TV: 0.008766,                        // Schicht 2 (Firmware)
      NK_K: 0.081265, NK_TN: 2.27226, NK_MAX: 0.105, KIPP_GRENZE: 30.0,     // Schicht 4, Abschaltung
      SPEED_SKAL: 200.0, a_komp_anteil: 0.0, WINKEL_SPERRE: 0.0,
      t_kipp: null,                                                          // wenn gesetzt: J = m g l t_kipp²
    };
    Object.assign(p, aenderungen || {});
    if (p.t_kipp) p.J = p.m * p.g * p.l * p.t_kipp * p.t_kipp;
    if (p.J === null) p.J = p.m * p.l * p.l * 4 / 3;
    p.v_je_hz = 2 * Math.PI * p.r_rad / p.Ns;
    p.v_max = p.v_je_hz * p.MAX_SPEED;
    p.T_kipp = Math.sqrt(p.J / (p.m * p.g * p.l));
    return p;
  }

  // ------------------------------------------------------------- Zufall (Mersenne-Twister-frei: xorshift, reproduzierbar)
  function zufall(saat) {
    let s = (saat >>> 0) || 1;
    const u = () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return (s >>> 0) / 4294967296; };
    return { normal(sigma) { if (!sigma) return 0; const a = Math.max(u(), 1e-12), b = u(); return sigma * Math.sqrt(-2 * Math.log(a)) * Math.cos(2 * Math.PI * b); } };
  }

  // ------------------------------------------------------------- Kalman (Zeile für Zeile wie im Sketch)
  class Kalman {
    constructor(q_angle, q_bias, r) { this.Q_ANGLE = q_angle; this.Q_BIAS = q_bias; this.R = r; this.angle = 0; this.bias = 0; this.P = [[0, 0], [0, 0]]; }
    eingeschwungenStarten(dt, n = 20000, tol = 1e-15) {
      const P = [[0, 0], [0, 0]]; let vor = null, K0 = 0, K1 = 0;
      for (let i = 0; i < n; i++) {
        P[0][0] += dt * (dt * P[1][1] - P[0][1] - P[1][0] + this.Q_ANGLE); P[0][1] -= dt * P[1][1]; P[1][0] -= dt * P[1][1]; P[1][1] += this.Q_BIAS * dt;
        const S = P[0][0] + this.R; K0 = P[0][0] / S; K1 = P[1][0] / S;
        const t00 = P[0][0], t01 = P[0][1];
        P[0][0] -= K0 * t00; P[0][1] -= K0 * t01; P[1][0] -= K1 * t00; P[1][1] -= K1 * t01;
        if (vor !== null && Math.abs(K0 - vor) < tol) break; vor = K0;
      }
      this.P = P; return [K0, K1];
    }
    update(meas, rate, dt) {
      const P = this.P;
      this.angle += dt * (rate - this.bias);
      P[0][0] += dt * (dt * P[1][1] - P[0][1] - P[1][0] + this.Q_ANGLE); P[0][1] -= dt * P[1][1]; P[1][0] -= dt * P[1][1]; P[1][1] += this.Q_BIAS * dt;
      const S = P[0][0] + this.R, K0 = P[0][0] / S, K1 = P[1][0] / S, y = meas - this.angle;
      this.angle += K0 * y; this.bias += K1 * y;
      const t00 = P[0][0], t01 = P[0][1];
      P[0][0] -= K0 * t00; P[0][1] -= K0 * t01; P[1][0] -= K1 * t00; P[1][1] -= K1 * t01;
      return this.angle;
    }
  }

  // ------------------------------------------------------------- die vier Schichten
  class Winkelerfassung {
    constructor(p) { this.p = p; this.kalman = new Kalman(p.Q_ANGLE, p.Q_BIAS, p.R_MEASURE); this.nullpunkt = 0; this.a_glatt = 0; this.v_vorher = 0; }
    start(winkel_grad, dt) { this.kalman.angle = winkel_grad; this.kalman.eingeschwungenStarten(dt); }
    rechne(roh_grad, drehrate_grad, v_ausgabe, dt) {
      const p = this.p;
      if (p.a_komp_anteil !== 0) {
        const a_roh = (v_ausgabe - this.v_vorher) / dt; this.v_vorher = v_ausgabe;
        this.a_glatt += (a_roh - this.a_glatt) * dt / p.t_dlpf;
        roh_grad += p.a_komp_anteil * Math.atan2(this.a_glatt, p.g) * R2G;
      }
      const winkel = this.kalman.update(roh_grad, drehrate_grad, dt);
      return [(winkel - this.nullpunkt) * G2R, (drehrate_grad - this.kalman.bias) * G2R];
    }
    drehrate() { return 0; }
  }
  class Winkelregler {
    constructor(p) { this.p = p; this.integral = 0; this.e_alt = 0; this.d_zustand = 0; }
    ruecksetzen() { this.integral = 0; this.e_alt = 0; this.d_zustand = 0; }
    rechne(winkel_ist, drehrate, soll, v_grenze, dt) {
      const p = this.p, e = winkel_ist - soll;
      if (p.WINKEL_SPERRE > 0 && Math.abs(e * R2G) < p.WINKEL_SPERRE) return 0;
      this.d_zustand = drehrate;                              // D-Anteil vom Kreisel
      this.e_alt = e;
      const anteil_p = p.N_K * e, anteil_d = p.N_K * p.N_TV * this.d_zustand;
      const roh = anteil_p + this.integral + anteil_d;
      if (Math.abs(roh) < v_grenze || roh * e < 0) this.integral = clip(this.integral + (p.N_K / p.N_TN) * e * dt, -v_grenze, v_grenze);
      return clip(anteil_p + this.integral + anteil_d, -v_grenze, v_grenze);
    }
  }
  class Motorausgabe {
    constructor(p) { this.p = p; this.f = 0; this.v = 0; this.weg = 0; }
    ausgeben(v_soll, dt) {
      const p = this.p;
      v_soll = clip(v_soll, this.v - p.a_max * dt, this.v + p.a_max * dt);
      let f = clip(v_soll / p.v_je_hz, -p.MAX_SPEED, p.MAX_SPEED);
      if (Math.abs(f) < p.MIN_SPEED) f = 0;
      this.f = f; this.v = f * p.v_je_hz; this.weg += this.v * dt;
      return this.f;
    }
    halt() { this.f = 0; this.v = 0; }
  }
  class Nullpunktkorrektur {
    constructor(p) { this.p = p; this.integral = 0; this.wert = 0; }
    ruecksetzen() { this.integral = 0; this.wert = 0; }
    rechne(v_ausgabe, weg, v_wunsch, dt) {
      const p = this.p, e_v = v_wunsch - v_ausgabe;
      const roh = p.NK_K * e_v + this.integral;
      if (Math.abs(roh) < p.NK_MAX || roh * e_v < 0) this.integral = clip(this.integral + (p.NK_K / p.NK_TN) * e_v * dt, -p.NK_MAX, p.NK_MAX);
      this.wert = clip(p.NK_K * e_v + this.integral, -p.NK_MAX, p.NK_MAX) * R2G;
      return this.wert;
    }
  }
  const clip = (x, a, b) => x < a ? a : (x > b ? b : x);

  // ------------------------------------------------------------- die Simulation (wie simuliere(..., regler="entwurf"))
  //   opt: dauer [s], theta0_grad, omega0_grad_s, stoerung(t) [Nm], speed(t) [Sollwert wie im Sketch], saat
  function simuliere(p, opt) {
    opt = Object.assign({ dauer: 6, theta0_grad: 3, omega0_grad_s: 0, stoerung: null, speed: null, saat: 20260823 }, opt || {});
    const dt_gitter = 1 / p.f_gitter, unter = p.feinschritte, dt = dt_gitter / unter, n_raster = Math.floor(opt.dauer * p.f_gitter);
    let theta = opt.theta0_grad * G2R, omega = opt.omega0_grad_s * G2R, x = 0, v_ist = 0, a_wagen = 0;
    const tau_lp = p.t_dlpf; let a_lp = 0, om_lp = 0, th_lp = theta;
    let n_dmp = 0, angle = theta * R2G, drehrate_gemeldet = 0, roh_grad = theta * R2G, theta_acc_grad = theta * R2G, neue_daten = false;
    let angleSetpoint = 0, speedSetpoint = 0, f_soll = 0, abgeschaltet = false;
    const erfassung = new Winkelerfassung(p), winkelregler = new Winkelregler(p), motor = new Motorausgabe(p), nullpunkt = new Nullpunktkorrektur(p);
    erfassung.start(theta * R2G, 1 / p.f_dmp);
    const rng = zufall(opt.saat);
    const t_r = [], th_r = [], thm_r = [], f_r = [], v_r = [], x_r = [], soll_r = [], null_r = [], a_r = [], roh_r = [];
    for (let k = 0; k < n_raster; k++) {
      const t = k * dt_gitter;
      t_r.push(t); th_r.push(theta * R2G); thm_r.push(angle); f_r.push(f_soll); v_r.push(v_ist); x_r.push(x); soll_r.push(angleSetpoint); null_r.push(nullpunkt.wert); a_r.push(a_wagen); roh_r.push(roh_grad);
      // ---- Strecke, ein Rasterschritt in Feinschritten
      const v_soll = f_soll * p.v_je_hz;
      for (let u = 0; u < unter; u++) {
        const dv = clip((v_soll - v_ist) / p.tau_mot, -p.a_max, p.a_max);
        a_wagen = dv; v_ist += dv * dt;
        const M = opt.stoerung ? opt.stoerung(t) : 0;
        const domega = (p.m * p.g * (p.l * Math.sin(theta) + p.s_versatz * Math.cos(theta))
                        - p.m * a_wagen * (p.l * Math.cos(theta) - p.s_versatz * Math.sin(theta)) - p.d * omega + M) / p.J;
        omega += domega * dt; theta += omega * dt; x += v_ist * dt;
        const a_schein = a_wagen + p.sensor_w * domega - p.sensor_u * omega * omega;
        a_lp += (a_schein - a_lp) * dt / tau_lp; th_lp += (theta - th_lp) * dt / tau_lp; om_lp += (omega - om_lp) * dt / tau_lp;
        theta_acc_grad = (th_lp - Math.atan2(a_lp, p.g)) * R2G;
      }
      // ---- Sensor liefert mit f_dmp
      if (t + 1e-12 >= n_dmp / p.f_dmp) {
        const messwert = theta_acc_grad + rng.normal(p.rausch_grad);
        const drehrate = om_lp * R2G + p.gyro_bias + rng.normal(p.gyro_rausch);
        drehrate_gemeldet = drehrate; roh_grad = messwert;
        angle = erfassung.kalman.angle;      // wird unten von Schicht 1 nachgeführt (im Python-Modell: kalman.update im Sensorzweig
        angle += p.mess_versatz;             //   nur für sensor_art != "kalman" außerhalb des Entwurfs; hier zählt der Entwurfszweig)
        n_dmp++; neue_daten = true;
      }
      // ---- Regler, nur bei neuen Daten (Entwurfszweig: Schicht 4, 1, Abschaltung, 2, 3)
      if (neue_daten) {
        neue_daten = false;
        if (opt.speed) speedSetpoint = opt.speed(t);
        const dt_r = 1 / p.f_dmp;
        nullpunkt.rechne(motor.v, motor.weg, speedSetpoint * p.SPEED_SKAL * p.v_je_hz, dt_r);
        erfassung.nullpunkt = nullpunkt.wert;
        const [winkel_ist, drehrate_ist] = erfassung.rechne(roh_grad, drehrate_gemeldet, motor.v, dt_r);
        angle = winkel_ist * R2G + nullpunkt.wert;
        angleSetpoint = nullpunkt.wert;
        if (Math.abs(angle) > p.KIPP_GRENZE) { motor.halt(); winkelregler.ruecksetzen(); nullpunkt.ruecksetzen(); abgeschaltet = true; f_soll = 0; }
        else { const v = winkelregler.rechne(winkel_ist, drehrate_ist, 0, p.v_max, dt_r); f_soll = motor.ausgeben(v, dt_r); }
      }
      if (Math.abs(theta * R2G) > 80) break;
    }
    return { t: t_r, theta: th_r, theta_mess: thm_r, f: f_r, v: v_r, x: x_r, soll: soll_r, nullpunkt: null_r, a: a_r, roh: roh_r,
             gefallen: Math.abs(th_r[th_r.length - 1]) > 80, abgeschaltet, bias: erfassung.kalman.bias };
  }

  // ------------------------------------------------------------- Kennzahlen eines Laufs
  function kennzahlen(erg, p) {
    const n = erg.t.length, ab = Math.floor(n * 0.5);
    const th = erg.theta, f = erg.f;
    let maxTh = 0, maxF = 0, zitter = 0, maxA = 0;
    for (let i = 0; i < n; i++) { maxTh = Math.max(maxTh, Math.abs(th[i])); maxF = Math.max(maxF, Math.abs(f[i])); maxA = Math.max(maxA, Math.abs(erg.a[i])); }
    let m = 0; for (let i = ab; i < n; i++) m += th[i]; m /= (n - ab);
    for (let i = ab; i < n; i++) zitter += (th[i] - m) ** 2; zitter = Math.sqrt(zitter / (n - ab));
    // Einschwingzeit: ab wann bleibt |θ − θ_end| < 0,1°
    const thEnd = m; let tEin = erg.t[n - 1];
    for (let i = n - 1; i >= 0; i--) { if (Math.abs(th[i] - thEnd) > 0.1) { tEin = erg.t[Math.min(i + 1, n - 1)]; break; } }
    return { gefallen: erg.gefallen, max_theta_grad: maxTh, einschwingzeit_s: tEin, restzittern_grad: zitter, weg_m: erg.x[n - 1], max_f_hz: maxF, max_a: maxA, theta_ende: thEnd };
  }

  // ------------------------------------------------------------- Auslegung durch Simulation
  // Suche über K und Tn (Tv = Anteil von Tn), Kriterium: stabil in allen Fällen der Spanne (T_kipp × 0,8 … 1,2,
  // Störmoment, Versatz), dann kleinste Kosten = Einschwingzeit + 20·Überschwingen [°] + 100·Restzittern [°].
  // Reserven: alle Beiwerte (K, NK_K) mit Faktor multipliziert, bis es kippt — nach oben und unten (Bisektion).
  function auslegen(basis, opt, fortschritt) {
    opt = Object.assign({ K: [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0], Tn_ms: [50, 65, 80, 100, 120, 150, 200], Tv_anteil: [0.05, 0.1, 0.15], dauer: 4, spanne: [0.8, 1.0, 1.2] }, opt || {});
    const faelle = (p) => [
      simuliere(p, { dauer: opt.dauer, theta0_grad: 5, saat: 1 }),
      simuliere(parameter(Object.assign({}, p, { t_kipp: p.T_kipp * opt.spanne[0] })), { dauer: opt.dauer, theta0_grad: 5, saat: 2 }),
      simuliere(parameter(Object.assign({}, p, { t_kipp: p.T_kipp * opt.spanne[2] })), { dauer: opt.dauer, theta0_grad: 5, saat: 3 }),
      simuliere(parameter(Object.assign({}, p, { s_versatz: 0.002 })), { dauer: opt.dauer, theta0_grad: 3, saat: 4 }),
      simuliere(p, { dauer: opt.dauer, theta0_grad: 0, stoerung: t => (t >= 1 && t < 1.05 ? 0.3 : 0), saat: 5 }),
    ];
    const bewerten = (p) => {
      let kosten = 0;
      for (const e of faelle(p)) {
        if (e.gefallen || e.abgeschaltet) return Infinity;
        const k = kennzahlen(e, p);
        kosten += k.einschwingzeit_s + 20 * Math.max(0, k.max_theta_grad - 5) / 5 + 100 * k.restzittern_grad;
      }
      return kosten;
    };
    // Stufe 1: Kosten aller Kandidaten (stabil in allen fünf Fällen, sonst unendlich)
    let versuche = 0; const gesamt = opt.K.length * opt.Tn_ms.length * opt.Tv_anteil.length, tabelle = [];
    for (const K of opt.K) for (const Tn of opt.Tn_ms) for (const tva of opt.Tv_anteil) {
      const p = parameter(Object.assign({}, basis, { N_K: K, N_TN: Tn / 1000, N_TV: tva * Tn / 1000 }));
      versuche++;
      if (K / (Tn / 1000) <= p.g) continue;                           // Aufrichtbedingung k_i > g
      const kosten = bewerten(p);
      if (kosten < Infinity) tabelle.push({ K, Tn_ms: Tn, Tv_ms: tva * Tn, kosten, p });
      if (fortschritt) fortschritt(0.5 * versuche / gesamt, null);
    }
    if (!tabelle.length) return { best: null, tabelle };
    tabelle.sort((a, b) => a.kosten - b.kosten);
    // Stufe 2: Reserven der zwölf günstigsten — alle Beiwerte (K und Nullpunkt-K) mit einem Faktor skaliert, bis ein Fall kippt
    const reserven = (p) => {
      const stabil = fak => bewerten(parameter(Object.assign({}, p, { N_K: p.N_K * fak, NK_K: p.NK_K * fak }))) < Infinity;
      let lo = 1, hi = 8; if (stabil(hi)) lo = hi; else for (let i = 0; i < 10; i++) { const m = (lo + hi) / 2; if (stabil(m)) lo = m; else hi = m; }
      const hoch = lo; lo = 0.05; hi = 1; if (stabil(lo)) hi = lo; else for (let i = 0; i < 10; i++) { const m = (lo + hi) / 2; if (stabil(m)) hi = m; else lo = m; }
      return { hoch, ab: hi };
    };
    const kandidaten = tabelle.slice(0, opt.reserveKandidaten || 12);
    kandidaten.forEach((k, i) => { Object.assign(k, reserven(k.p)); if (fortschritt) fortschritt(0.5 + 0.5 * (i + 1) / kandidaten.length, k); });
    // Wahl: günstigster mit Reserve ≥ 2 nach oben und ≤ 0,5 nach unten (wie die Auslegung im Manuskript); sonst der mit der größten Reserve nach oben
    const tauglich = kandidaten.filter(k => k.hoch >= (opt.reserveHochMin || 2.0) && k.ab <= (opt.reserveAbMax || 0.5));
    const best = tauglich.length ? tauglich[0] : kandidaten.slice().sort((a, b) => b.hoch - a.hoch)[0];
    best.reserve_hoch = best.hoch; best.reserve_ab = best.ab; best.reserve_gefordert = tauglich.length > 0;
    return { best, tabelle, kandidaten };
  }

  return { parameter, simuliere, kennzahlen, auslegen, Kalman, Winkelerfassung, Winkelregler, Motorausgabe, Nullpunktkorrektur, G2R, R2G };
})();
if (typeof module !== 'undefined') module.exports = SEGWAY;
