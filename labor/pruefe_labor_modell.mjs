// Prüfung L1: das JavaScript-Modell des Labors gegen das Python-Modell (Modell/segway_modell.py) bei denselben
// Eingaben — drei Fälle aus Labor/referenz_python.json (Aufrichten 5°, Versatz 2 mm, Stoß 0,3 Nm), ohne Rauschen.
// Schranke: größte Abweichung der Neigung < 1e-6 Grad, der Schrittfrequenz < 1e-3 Hz, des Weges < 1e-7 m.
//   node Labor/pruefe_labor_modell.mjs
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const H = '/workspace/Regelungstechnik2_Segway/Labor/';
const SEG = require(H + 'segway_labor_modell.js');
const R = JSON.parse(fs.readFileSync(H + 'referenz_python.json', 'utf8'));
let fehler = 0; const BEF = [];
const sage = (gut, t) => { console.log(`  ${gut ? 'ok    ' : 'FEHLER'} ${t}`); BEF.push({ gut, text: t }); if (!gut) fehler++; };
const pp = Object.assign({}, R.param, { rausch_grad: 0, gyro_rausch: 0, gyro_bias: 0 });
delete pp.s_versatz; delete pp.mess_versatz;
for (const [name, F] of Object.entries(R.faelle)) {
  const p = SEG.parameter(Object.assign({}, pp, { s_versatz: F.s, J: R.param.J }));
  const st = F.stoss ? (t => (t >= 1.0 && t < 1.05 ? F.stoss : 0)) : null;
  const e = SEG.simuliere(p, { dauer: 4.0, theta0_grad: F.theta0, stoerung: st });
  let dTh = 0, dF = 0, dX = 0;
  const n = Math.min(e.t.length, F.theta.length);
  for (let i = 0; i < n; i++) { dTh = Math.max(dTh, Math.abs(e.theta[i] - F.theta[i])); dF = Math.max(dF, Math.abs(e.f[i] - F.f[i])); dX = Math.max(dX, Math.abs(e.x[i] - F.x[i])); }
  sage(n === F.theta.length && dTh < 1e-6 && dF < 1e-3 && dX < 1e-7, `${name}: ${n} Takte, Abweichung Neigung ${dTh.toExponential(2)} °, Schrittfrequenz ${dF.toExponential(2)} Hz, Weg ${dX.toExponential(2)} m (Ende θ = ${e.theta[n-1].toFixed(6)}° gegen Python ${F.theta[n-1].toFixed(6)}°)`);
}
fs.writeFileSync(H + 'pruefe_labor_modell.json', JSON.stringify({ datum: new Date().toISOString(), befunde: BEF, fehler }, null, 1));
console.log(fehler ? `${fehler} Beanstandung(en)` : 'alles in Ordnung');
process.exit(fehler ? 1 : 0);
