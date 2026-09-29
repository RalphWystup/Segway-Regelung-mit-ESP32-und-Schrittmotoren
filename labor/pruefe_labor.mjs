// Prüfung der Laborseite im echten Browser (Chromium): L2 Werkzeug vor Text, L3 keine Konsolenfehler, L4 Simulation und
// Auslegung liefern Zahlen, L5 Dokumentation enthält die Herleitung; Bilder nach Labor/seitenbilder/.
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('/tmp/node_modules/playwright');
const H = '/workspace/Regelungstechnik2_Segway/Labor/';
const V = fs.readFileSync(H + 'VERSION', 'utf8').trim();
const B = H + 'seitenbilder/'; fs.mkdirSync(B, { recursive: true });
let fehler = 0; const BEF = [];
const sage = (gut, t) => { console.log(`  ${gut ? 'ok    ' : 'FEHLER'} ${t}`); BEF.push({ gut, text: t }); if (!gut) fehler++; };
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  const konsole = []; p.on('pageerror', e => konsole.push('Seitenfehler: ' + e.message)); p.on('console', m => { if (m.type() === 'error') konsole.push(m.text()); });
  await p.goto('file://' + H + `Segway_Labor_${V}.html`, { waitUntil: 'load', timeout: 120000 }); await p.waitForTimeout(1500);
  const kopf = await p.$eval('#fassung', e => e.textContent);
  sage(new RegExp(`Fassung ${V} · 29\\.09\\.2026 · Prof\\. Dr\\.-Ing\\. Ralph Wystup`).test(kopf), `Kopf: „${kopf.slice(0, 70)}…“`);
  const y = await p.evaluate(() => document.getElementById('simulieren').getBoundingClientRect().top + window.scrollY);
  sage(y < 1000, `Werkzeug vor Text: Knopf „Simulieren“ bei ${y.toFixed(0)} px`);
  const kenn = await p.$eval('#kenn', e => e.textContent);
  sage(/Kippzeitkonstante/.test(kenn) && /106,7 ms/.test(kenn), 'Simulation beim Öffnen gerechnet: Kennzahlen mit T = 106,7 ms');
  const l = await p.evaluate(() => { const L = window.LABOR.letzter; return { n: L.e.t.length, gefallen: L.e.gefallen, thEnde: L.k.theta_ende, weg: L.k.weg_m }; });
  sage(l.n === 1500 && !l.gefallen && Math.abs(l.thEnde) < 0.05, `Standardlauf: ${l.n} Takte, steht, Endwinkel ${l.thEnde.toFixed(4)}°, Weg ${(1000*l.weg).toFixed(1)} mm`);
  await p.screenshot({ path: B + `labor_${V}_start.png` });
  // Versatz 2 mm → Gleichgewichtswinkel −arctan(2/44,48) = −2,575°
  await p.$eval('#s_mm', e => { e.value = '2'; }); await p.$eval('#dauer', e => { e.value = '20'; }); await p.click('#simulieren'); await p.waitForTimeout(500);
  const l2 = await p.evaluate(() => window.LABOR.letzter.k.theta_ende);
  sage(Math.abs(l2 - (-2.575)) < 0.05, `2 mm Versatz: Endwinkel ${l2.toFixed(3)}° (Gleichgewicht −2,575°)`);
  await p.$eval('#s_mm', e => { e.value = '0'; }); await p.$eval('#dauer', e => { e.value = '6'; });
  // Auslegung
  const t0 = Date.now(); await p.click('#auslegen');
  await p.waitForFunction(() => /Auslegung: K = |kein stabiler/.test(document.getElementById('stand').textContent), {}, { timeout: 600000 });
  const stand = await p.$eval('#stand', e => e.textContent);
  sage(/Auslegung: K = /.test(stand), `Auslegung (${((Date.now()-t0)/1000).toFixed(1)} s): ${stand.slice(0, 200)}`);
  const A = await p.evaluate(() => { const R = window.LABOR.auslegung; return R && R.best ? { K: R.best.K, Tn: R.best.Tn_ms, Tv: R.best.Tv_ms, hoch: R.best.reserve_hoch, ab: R.best.reserve_ab, n: R.tabelle.length } : null; });
  sage(A && A.hoch > 1.5 && A.ab < 0.7, `Reserven des Entwurfs: ${A && A.hoch.toFixed(2)} nach oben, ${A && A.ab.toFixed(3)} nach unten (${A && A.n} Kandidaten)`);
  await p.screenshot({ path: B + `labor_${V}_auslegung.png` });
  const doku = (await p.evaluate(() => document.body.textContent)).replace(/\s+/g, ' ');
  sage(doku.includes('Die Bewegungsgleichung') && doku.includes('Die Schnittstellen zum abgetasteten Regler') && doku.includes('Korrektur der Reglerparameter'), 'Dokumentation enthält Herleitung, Schnittstellen und Korrektur');
  sage(konsole.length === 0, 'keine Konsolenfehler' + (konsole.length ? ' — ' + konsole.slice(0, 3).join(' | ').slice(0, 300) : ''));
  await b.close();
  fs.writeFileSync(H + 'pruefe_labor.json', JSON.stringify({ datum: new Date().toISOString(), fassung: V, befunde: BEF, fehler }, null, 1));
  console.log(fehler ? `${fehler} Beanstandung(en)` : 'alles in Ordnung'); process.exit(fehler ? 1 : 0);
})().catch(e => { console.log('FEHLER', e.stack || e.message); process.exit(1); });
