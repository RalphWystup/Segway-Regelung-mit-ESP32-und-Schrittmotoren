#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Das Segway-Labor bauen: eine HTML-Datei, die ohne Netz läuft (Stufe 1 des Auftrags vom 28.09.2026, Aufgabenblatt Teil G).

Inhalt der Seite:
  * Werkzeug zuerst: Regler-, Strecken- und Versuchsgrößen einstellen, simulieren, Bilder und Kennzahlen; „Auslegung durch
    Simulation“ sucht die Beiwerte K, Tn, Tv mit Reserven; „Firmware-Werte“ setzt die Beiwerte des Sketches.
  * Das Rechenmodell ist Labor/segway_labor_modell.js — Zeile für Zeile aus Modell/segway_modell.py, geprüft gegen
    das Python-Modell (Labor/pruefe_labor_modell.mjs, < 1e-6 Grad).
  * Verbindung zum Gerät (Stufe 2): Adresse, Werte lesen (`/werte`), Mitschnitt holen (`/log`); Parameter schreiben und Stoß
    kommen mit Firmware 2 — die Knöpfe sagen es.
  * Kamera (Stufe 4): angelegt, sagt, was fehlt.
  * Dokumentation: das ganze Manuskript (Fassung 5) als gesetzter Text mit Formeln (MathML) und Bildern in der Seite.
Fassung aus Labor/VERSION, Datum hier — eine Quelle.
  python3 Labor/erstelle_segway_labor.py
"""
from __future__ import annotations
import base64
import re
import subprocess
from pathlib import Path

H = Path(__file__).resolve().parent
P = H.parent
VERSION = (H / "VERSION").read_text(encoding="utf-8").strip()
DATUM = "29.09.2026"
NAMENSNENNUNG = "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
ZIEL = H / f"Segway_Labor_{VERSION}.html"


def daten_uri(pfad: Path) -> str:
    typ = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}[pfad.suffix.lower().lstrip(".")]
    return f"data:{typ};base64," + base64.b64encode(pfad.read_bytes()).decode()


def manuskript_html() -> str:
    """Manuskript → HTML-Fragment mit MathML; Bilder als data:-Adressen eingebettet; Fassungszeile mit."""
    md = (P / "MANUSKRIPT_Segway_Gesamt.md").read_text(encoding="utf-8")
    kopf = re.match(r"---\n(.*?)\n---\n", md, re.S)
    meta = kopf.group(1) if kopf else ""
    fassung = re.search(r'date:\s*"([^"]+)"', meta)
    md = md[kopf.end():] if kopf else md
    md = md.replace("\\newpage", "")
    html = subprocess.run(["pandoc", "-f", "markdown", "-t", "html", "--mathml", "--number-sections", "--toc", "--toc-depth=2"],
                          input=md, capture_output=True, text=True, check=True).stdout
    def ersetze(m):
        pfad = P / m.group(1)
        return f'src="{daten_uri(pfad)}"' if pfad.is_file() else m.group(0)
    html = re.sub(r'src="([^"]+\.(?:png|jpg|jpeg))"', ersetze, html)
    return f'<p class="small">{fassung.group(1) if fassung else ""}</p>\n' + html


def einfuehrung_html() -> str:
    """Das Einführungsdokument (Einfuehrung/EINFUEHRUNG_Segway.md) vor dem Manuskript: ohne Kopf, ohne LaTeX-Querformatblöcke,
    Bilder als data:-Adressen; die Seitenverweise gelten für das PDF des Manuskripts und werden so gesagt."""
    md = (P / "Einfuehrung" / "EINFUEHRUNG_Segway.md").read_text(encoding="utf-8")
    kopf = re.match(r"---\n(.*?)\n---\n", md, re.S)
    md = md[kopf.end():] if kopf else md
    md = re.sub(r"```\{=latex\}.*?```\n", "", md, flags=re.S).replace("\\newpage", "")
    md = md.replace("](../Bilder/", "](Bilder/")
    html = subprocess.run(["pandoc", "-f", "markdown", "-t", "html", "--mathml"], input=md, capture_output=True, text=True, check=True).stdout
    def ersetze(m):
        pfad = P / m.group(1)
        return f'src="{daten_uri(pfad)}"' if pfad.is_file() else m.group(0)
    return re.sub(r'src="([^"]+\.(?:png|jpg|jpeg))"', ersetze, html)


def seite() -> str:
    modell = (H / "segway_labor_modell.js").read_text(encoding="utf-8").replace("if (typeof module !== 'undefined') module.exports = SEGWAY;", "")
    doku = manuskript_html(); einf = einfuehrung_html()
    css = """
:root { --tinte:#1a1a1a; --leise:#666; --blau:#1b3a8f; --rot:#b0171f; --gruen:#2e7d32; --karte:#fff; --grund:#fbfaf7; --linie:#d8d4cc; }
body { font-family: "DejaVu Serif", Georgia, serif; color: var(--tinte); background: var(--grund); margin: 0; line-height: 1.45; }
header { padding: 14px 24px 6px; border-bottom: 1px solid var(--linie); background: #f3f1ea; }
h1 { margin: 0 0 4px; font-size: 22px; } h2 { font-size: 17px; margin: 18px 0 8px; } h3 { font-size: 15px; margin: 14px 0 6px; }
.small { color: var(--leise); font-size: 13px; margin: 2px 0; }
main { padding: 12px 24px 40px; max-width: 1500px; margin: 0 auto; }
.zeile { display: flex; gap: 18px; flex-wrap: wrap; align-items: flex-start; }
.karte { background: var(--karte); border: 1px solid var(--linie); border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
.bedien { flex: 0 0 360px; } .bilder { flex: 1 1 640px; min-width: 520px; }
.control { display: grid; grid-template-columns: 1fr 96px 46px; gap: 4px 8px; align-items: center; font-size: 13px; margin: 3px 0; }
.control label { color: #333; } .control input { width: 90px; font: inherit; font-size: 13px; padding: 2px 4px; border: 1px solid #bbb; border-radius: 4px; }
.control .einheit { color: var(--leise); }
.gruppe { border-top: 1px dashed var(--linie); margin-top: 8px; padding-top: 6px; }
.gruppe h3 { margin: 4px 0 6px; font-size: 14px; color: var(--blau); } details.gruppe > summary { cursor: pointer; list-style: none; } details.gruppe > summary::before { content: "▸ "; color: var(--leise); } details.gruppe[open] > summary::before { content: "▾ "; }
button { font: inherit; font-size: 13px; padding: 6px 10px; margin: 4px 4px 0 0; border: 1px solid #8a8f98; border-radius: 6px; background: #eef1f6; cursor: pointer; }
button.haupt { background: var(--blau); color: #fff; border-color: var(--blau); } button:disabled { opacity: .5; cursor: default; }
canvas { width: 100%; height: 200px; display: block; background: #fff; border: 1px solid var(--linie); border-radius: 6px; margin-bottom: 8px; }
table.kenn { border-collapse: collapse; font-size: 13px; margin: 6px 0; } table.kenn td, table.kenn th { border-bottom: 1px solid var(--linie); padding: 3px 10px 3px 0; text-align: left; }
.bar { height: 8px; background: #e6e6e6; border-radius: 4px; overflow: hidden; margin: 6px 0; } .bar div { height: 100%; background: var(--blau); width: 0%; transition: width .2s; }
#stand { min-height: 18px; }
details.doku { margin-top: 20px; } details.doku > summary { cursor: pointer; font-size: 16px; font-weight: bold; padding: 8px 0; }
article.documentation { max-width: 900px; } article.documentation img { max-width: 100%; height: auto; }
article.documentation table { border-collapse: collapse; font-size: 13px; } article.documentation td, article.documentation th { border-bottom: 1px solid var(--linie); padding: 3px 8px; vertical-align: top; }
article.documentation h1 { font-size: 20px; margin-top: 28px; } article.documentation h2 { font-size: 17px; } article.documentation h3 { font-size: 15px; }
#TOC { column-count: 2; font-size: 13px; } #TOC ul { margin: 0; padding-left: 16px; }
.hinweis { background: #fff6e0; border-left: 3px solid #b06a00; padding: 6px 10px; font-size: 13px; margin: 6px 0; }
"""
    js_ui = r"""
const $ = id => document.getElementById(id);
const f = (x, n=2) => Number.isFinite(x) ? x.toLocaleString('de-DE', {minimumFractionDigits: n, maximumFractionDigits: n}) : '—';
// ---- Eingabefelder → Parameter
const FELDER = [
  ['gruppe', 'Regler (Schicht 2 und 4)'],
  ['N_K', 'K — Verstärkung', 'm/s je rad', 2.325385, 6], ['N_TN_ms', 'Tn — Nachstellzeit', 'ms', 86.638, 3], ['N_TV_ms', 'Tv — Vorhaltezeit', 'ms', 8.766, 3],
  ['NK_K', 'Nullpunkt K', 'rad je m/s', 0.081265, 6], ['NK_TN', 'Nullpunkt Tn', 's', 2.27226, 5], ['NK_MAX_grad', 'Nullpunkt-Anschlag', '°', 6.0, 1],
  ['Q_ANGLE', 'Kalman Q Winkel', '', 0.001, 4], ['Q_BIAS', 'Kalman Q Nullpunkt', '', 0.003, 4], ['R_MEASURE', 'Kalman R', '', 309.301675, 3],
  ['gruppe', 'Strecke (gemessen 28.09.2026)'],
  ['m', 'Masse m', 'kg', 1.248, 3], ['l_mm', 'Schwerpunkthöhe l', 'mm', 44.48, 2], ['t_kipp_ms', 'Kippzeitkonstante T', 'ms', 106.7, 1],
  ['d', 'Lagerreibung d', 'Nms', 0.002, 4], ['s_mm', 'Schwerpunktversatz s', 'mm', 0.0, 2], ['sensor_w_mm', 'Sensor w über Achse', 'mm', 71, 0], ['sensor_u_mm', 'Sensor u nach vorn', 'mm', 39, 0],
  ['gruppe', 'Antrieb und Takt (Firmware)'],
  ['rad_mm', 'Raddurchmesser', 'mm', 64, 1], ['Ns', 'Schritte je Umdrehung', '', 1600, 0], ['a_max', 'Rampe a_max', 'm/s²', 6.48, 2], ['MAX_SPEED', 'Frequenzgrenze', 'Hz', 6000, 0],
  ['tau_mot_ms', 'Verzug des Treibers', 'ms', 2.0, 1], ['takt_ms', 'Regeltakt', 'ms', 4.0, 1], ['t_dlpf_ms', 'Sensortiefpass (Laufzeit)', 'ms', 4.8, 1],
  ['gruppe', 'Versuch'],
  ['theta0', 'Anfangsneigung', '°', 5.0, 1], ['omega0', 'Anfangsdrehrate', '°/s', 0.0, 1], ['stoss', 'Stoß über 50 ms bei t = 1 s', 'Nm', 0.0, 2],
  ['rausch_grad', 'Rauschen Winkel (σ)', '°', 0.05, 3], ['gyro_rausch', 'Rauschen Drehrate (σ)', '°/s', 0.05, 3], ['gyro_bias', 'Kreiselnullpunkt', '°/s', 0.05, 3],
  ['dauer', 'Dauer', 's', 6.0, 1],
];
function felderBauen() {
  const z = $('felder'); let html = '';
  let offen = 0;
  for (const F of FELDER) {
    if (F[0] === 'gruppe') { if (offen) html += '</details>'; const auf = /Versuch|Regler/.test(F[1]) ? ' open' : ''; html += `<details class="gruppe"${auf}><summary><h3 style="display:inline">${F[1]}</h3></summary>`; offen = 1; continue; }
    html += `<div class="control"><label for="${F[0]}">${F[1]}</label><input id="${F[0]}" type="number" step="any" value="${F[3]}"><span class="einheit">${F[2]}</span></div>`;
  }
  if (offen) html += '</details>';
  z.innerHTML = html;
}
function werte() { const w = {}; for (const F of FELDER) if (F[0] !== 'gruppe') w[F[0]] = Number($(F[0]).value); return w; }
function parameterAus(w) {
  return SEGWAY.parameter({ N_K: w.N_K, N_TN: w.N_TN_ms/1000, N_TV: w.N_TV_ms/1000, NK_K: w.NK_K, NK_TN: w.NK_TN, NK_MAX: w.NK_MAX_grad*Math.PI/180,
    Q_ANGLE: w.Q_ANGLE, Q_BIAS: w.Q_BIAS, R_MEASURE: w.R_MEASURE, m: w.m, l: w.l_mm/1000, t_kipp: w.t_kipp_ms/1000, d: w.d, s_versatz: w.s_mm/1000,
    sensor_w: w.sensor_w_mm/1000, sensor_u: w.sensor_u_mm/1000, r_rad: w.rad_mm/2000, Ns: w.Ns, a_max: w.a_max, MAX_SPEED: w.MAX_SPEED,
    tau_mot: w.tau_mot_ms/1000, f_gitter: 1000/w.takt_ms, f_dmp: 1000/w.takt_ms, t_dlpf: w.t_dlpf_ms/1000,
    rausch_grad: w.rausch_grad, gyro_rausch: w.gyro_rausch, gyro_bias: w.gyro_bias });
}
// ---- Zeichnen
function plot(canvas, reihen, opt) {
  opt = opt || {};
  const c = canvas, ctx = c.getContext('2d'); const W = c.width = c.clientWidth * devicePixelRatio, Hh = c.height = c.clientHeight * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0); const w = c.clientWidth, h = c.clientHeight;
  ctx.clearRect(0, 0, w, h); const L = 52, R = 12, T = 22, B = 26;
  const t = reihen[0].t; let ymin = Infinity, ymax = -Infinity;
  for (const r of reihen) for (const v of r.y) { if (Number.isFinite(v)) { ymin = Math.min(ymin, v); ymax = Math.max(ymax, v); } }
  if (opt && opt.null) { ymin = Math.min(ymin, 0); ymax = Math.max(ymax, 0); }
  if (ymax - ymin < 1e-9) { ymax += 1; ymin -= 1; } const pad = (ymax - ymin) * 0.08; ymin -= pad; ymax += pad;
  const tmax = t[t.length-1] || 1; const X = tt => L + (w - L - R) * tt / tmax, Y = v => T + (h - T - B) * (1 - (v - ymin) / (ymax - ymin));
  ctx.strokeStyle = '#ddd'; ctx.lineWidth = 1; ctx.fillStyle = '#666'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
  for (let k = 0; k <= 4; k++) { const v = ymin + (ymax - ymin) * k / 4, y = Y(v); ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(w - R, y); ctx.stroke(); ctx.fillText(v.toLocaleString('de-DE', {maximumFractionDigits: 3}), L - 4, y + 4); }
  ctx.textAlign = 'center'; for (let k = 0; k <= 6; k++) { const tt = tmax * k / 6, x = X(tt); ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, h - B); ctx.stroke(); ctx.fillText(tt.toLocaleString('de-DE', {maximumFractionDigits: 2}) + ' s', x, h - 8); }
  if (ymin < 0 && ymax > 0) { ctx.strokeStyle = '#999'; ctx.beginPath(); ctx.moveTo(L, Y(0)); ctx.lineTo(w - R, Y(0)); ctx.stroke(); }
  ctx.lineWidth = 1.4; let lx = L + 6;
  const bis = Number.isFinite(opt.bis) ? opt.bis : Infinity;
  for (const r of reihen) { ctx.strokeStyle = r.farbe; ctx.beginPath(); let erst = true; for (let i = 0; i < r.y.length; i++) { if (r.t[i] > bis) break; if (!Number.isFinite(r.y[i])) continue; const x = X(r.t[i]), y = Y(r.y[i]); if (erst) { ctx.moveTo(x, y); erst = false; } else ctx.lineTo(x, y); } ctx.stroke();
    ctx.fillStyle = r.farbe; ctx.textAlign = 'left'; ctx.fillText(r.name, lx, 13); lx += ctx.measureText(r.name).width + 16; }
  if (Number.isFinite(opt.bis)) { const xb = X(Math.min(bis, tmax)); ctx.strokeStyle = '#b0171f'; ctx.lineWidth = 1; ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(xb, T); ctx.lineTo(xb, h - B); ctx.stroke(); ctx.setLineDash([]); }
  ctx.fillStyle = '#333'; ctx.textAlign = 'left'; ctx.fillText(opt.titel || '', L, h - 8);
}
// ---- das Fahrzeug, vereinfacht, in Seitenansicht: Rad, Aufbau (Platten, Akku oben, Sensor vorn), Lot und Neigung
function zeichneSegway(canvas, p, theta_grad, x_m, nullpunkt_grad, t, f_hz) {
  const c = canvas, ctx = c.getContext('2d'); c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0); const w = c.clientWidth, h = c.clientHeight; ctx.clearRect(0, 0, w, h);
  const S = 1000 * (h - 60) / 260;                   // Bildpunkte je Meter: Aufbau (0,17 m über der Achse) plus Rad füllen die Höhe
  const boden = h - 30, xm = w / 2 + x_m * S, r = p.r_rad * S, yA = boden - r;
  const ueberh = 5, th = theta_grad * ueberh * Math.PI / 180;
  ctx.fillStyle = '#c8b07a'; ctx.fillRect(0, boden, w, 8); ctx.fillStyle = '#555'; ctx.fillRect(0, boden, w, 2);
  ctx.strokeStyle = '#999'; ctx.fillStyle = '#666'; ctx.font = '11px sans-serif'; ctx.textAlign = 'center'; ctx.lineWidth = 1;
  for (let k = -10; k <= 10; k++) { const xx = k / 10, px = w / 2 + xx * S; if (px < 0 || px > w) continue; ctx.beginPath(); ctx.moveTo(px, boden + 8); ctx.lineTo(px, boden + (k % 5 === 0 ? 16 : 12)); ctx.stroke(); if (k % 5 === 0) ctx.fillText((xx * 1000).toFixed(0) + ' mm', px, boden + 27); }
  ctx.setLineDash([4, 4]); ctx.strokeStyle = '#999'; ctx.beginPath(); ctx.moveTo(xm, yA); ctx.lineTo(xm, yA - 0.19 * S); ctx.stroke(); ctx.setLineDash([]);
  ctx.save(); ctx.translate(xm, yA); ctx.fillStyle = '#222'; ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.fill(); ctx.fillStyle = '#ddd'; ctx.beginPath(); ctx.arc(0, 0, r * 0.72, 0, 2 * Math.PI); ctx.fill();
  const phi = x_m / p.r_rad; ctx.strokeStyle = '#777'; ctx.lineWidth = 2; for (let k = 0; k < 6; k++) { const a = phi + k * Math.PI / 3; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(r * 0.7 * Math.cos(a), r * 0.7 * Math.sin(a)); ctx.stroke(); }
  ctx.fillStyle = '#333'; ctx.beginPath(); ctx.arc(0, 0, 3, 0, 2 * Math.PI); ctx.fill(); ctx.restore();
  ctx.save(); ctx.translate(xm, yA); ctx.rotate(th);
  const mm = S / 1000;
  ctx.fillStyle = '#e8e4d8'; ctx.strokeStyle = '#2b4c7e'; ctx.lineWidth = 1.5;
  ctx.fillRect(-25 * mm, -62 * mm, 50 * mm, 52 * mm); ctx.strokeRect(-25 * mm, -62 * mm, 50 * mm, 52 * mm);
  ctx.fillRect(-80 * mm, -47 * mm, 160 * mm, 5 * mm); ctx.strokeRect(-80 * mm, -47 * mm, 160 * mm, 5 * mm);
  ctx.fillRect(-80 * mm, -97 * mm, 160 * mm, 5 * mm); ctx.strokeRect(-80 * mm, -97 * mm, 160 * mm, 5 * mm);
  ctx.fillStyle = '#2b4c7e'; ctx.fillRect(-30 * mm, -92 * mm, 4 * mm, 45 * mm); ctx.fillRect(26 * mm, -92 * mm, 4 * mm, 45 * mm);
  ctx.fillStyle = '#b0171f'; ctx.fillRect(-52 * mm, -129 * mm, 104 * mm, 32 * mm);
  ctx.fillStyle = '#2e7d32'; ctx.fillRect(-60 * mm, -134 * mm, 120 * mm, 4 * mm);
  ctx.fillStyle = '#7a1f1f'; ctx.fillRect(35 * mm, -75 * mm, 8 * mm, 8 * mm);
  ctx.fillStyle = '#c00'; ctx.beginPath(); ctx.arc(0, -p.l * S, 4, 0, 2 * Math.PI); ctx.fill();
  ctx.restore();
  ctx.fillStyle = '#1a1a1a'; ctx.textAlign = 'left'; ctx.font = '13px sans-serif';
  ctx.fillText(`t = ${t.toFixed(2)} s   Neigung θ = ${theta_grad.toFixed(2)}°   Nullpunkt ${nullpunkt_grad.toFixed(3)}°   Weg ${(1000 * x_m).toFixed(0)} mm   Schrittfrequenz ${Math.round(f_hz)} Hz`, 10, 18);
  ctx.fillStyle = '#666'; ctx.font = '11px sans-serif'; ctx.fillText('Seitenansicht wie die Kamera am Prüfstand · rot der Schwerpunkt (l), dunkelrot der Sensor (w, u), grün die Bügel-Oberkante', 10, 34);
}
let ANIM = { laeuft: false, t0: 0, tSim: 0, tempo: 1 };
function bild(tSim) {
  if (!LETZTER) return; const e = LETZTER.e, p = LETZTER.p;
  const i = Math.min(e.t.length - 1, Math.max(0, Math.floor(tSim * p.f_gitter)));
  zeichneSegway($('cAnim'), p, e.theta[i], e.x[i], e.nullpunkt[i], e.t[i], e.f[i]);
  plot($('c1'), [{ t: e.t, y: e.theta, name: 'wahre Neigung θ [°]', farbe: '#1b3a8f' }, { t: e.t, y: e.theta_mess, name: 'Istwinkel des Reglers [°]', farbe: '#b0171f' }, { t: e.t, y: e.nullpunkt, name: 'nachgeführter Nullpunkt [°]', farbe: '#b06a00' }], { null: true, bis: tSim });
  plot($('c2'), [{ t: e.t, y: e.f, name: 'Schrittfrequenz [Hz]', farbe: '#2e7d32' }], { null: true, bis: tSim });
  plot($('c3'), [{ t: e.t, y: e.x.map(v => v * 1000), name: 'Weg [mm]', farbe: '#5b3d8a' }, { t: e.t, y: e.v.map(v => v * 1000), name: 'Geschwindigkeit [mm/s]', farbe: '#888' }], { null: true, bis: tSim });
  $('zeit').textContent = `${e.t[i].toFixed(2)} s von ${e.t[e.t.length - 1].toFixed(2)} s`;
}
function schritt() {
  if (!ANIM.laeuft) return;
  ANIM.tSim = (performance.now() - ANIM.t0) / 1000 * ANIM.tempo;
  const ende = LETZTER.e.t[LETZTER.e.t.length - 1];
  if (ANIM.tSim >= ende) { ANIM.tSim = ende; ANIM.laeuft = false; }
  bild(ANIM.tSim); window.LABOR.animT = ANIM.tSim;
  if (ANIM.laeuft) requestAnimationFrame(schritt);
}
function abspielen() { if (!LETZTER) return; ANIM.tempo = Number($('tempo').value); ANIM.t0 = performance.now(); ANIM.laeuft = true; requestAnimationFrame(schritt); }
function anhalten() { ANIM.laeuft = false; }
let LETZTER = null;
function simulieren() {
  const w = werte(), p = parameterAus(w);
  const st = w.stoss ? (t => (t >= 1.0 && t < 1.05 ? w.stoss : 0)) : null;
  const t0 = performance.now();
  const e = SEGWAY.simuliere(p, { dauer: w.dauer, theta0_grad: w.theta0, omega0_grad_s: w.omega0, stoerung: st, saat: 20260823 });
  const k = SEGWAY.kennzahlen(e, p); LETZTER = { p, e, k };
  ANIM.laeuft = false; bild(0); abspielen();
  const ki = p.N_K / p.N_TN;
  $('kenn').innerHTML = `<tr><th>Größe</th><th>Wert</th></tr>
    <tr><td>Kippzeitkonstante T = √(J/(m g l))</td><td>${f(p.T_kipp*1000,1)} ms (J = ${(p.J*1e3).toLocaleString('de-DE',{maximumFractionDigits:2})}·10⁻³ kg·m²)</td></tr>
    <tr><td>Aufrichtbedingung k_i = K/Tn &gt; g</td><td>${f(ki,2)} ${ki > p.g ? '&gt; 9,81 — erfüllt' : '≤ 9,81 — <b>verletzt</b>'}</td></tr>
    <tr><td>Ausgang</td><td>${e.gefallen ? '<b>gefallen</b>' : (e.abgeschaltet ? '<b>Sicherheitsabschaltung</b>' : 'steht')}</td></tr>
    <tr><td>größte Neigung</td><td>${f(k.max_theta_grad,2)} °</td></tr>
    <tr><td>Einschwingzeit (|θ − θ_Ende| &lt; 0,1°)</td><td>${f(k.einschwingzeit_s,2)} s</td></tr>
    <tr><td>Endwinkel (Gleichgewicht −arctan(s/l) = ${f(-Math.atan2(p.s_versatz, p.l)*180/Math.PI,3)} °)</td><td>${f(k.theta_ende,3)} °</td></tr>
    <tr><td>Restzittern (σ, zweite Hälfte)</td><td>${f(k.restzittern_grad,4)} °</td></tr>
    <tr><td>Weg am Ende</td><td>${f(k.weg_m*1000,1)} mm</td></tr>
    <tr><td>größte Schrittfrequenz / Beschleunigung</td><td>${f(k.max_f_hz,0)} Hz (Grenze ${f(p.MAX_SPEED,0)}) / ${f(k.max_a,2)} m/s² (Rampe ${f(p.a_max,2)})</td></tr>
    <tr><td>Kreiselnullpunkt geschätzt</td><td>${f(e.bias,3)} °/s (wahr ${f(p.gyro_bias,3)})</td></tr>
    <tr><td>Rechenzeit</td><td>${f(performance.now()-t0,0)} ms für ${e.t.length} Takte × ${p.feinschritte} Feinschritte</td></tr>`;
  $('stand').textContent = `gerechnet: ${e.t.length} Takte à ${f(1000/p.f_gitter,1)} ms, ${p.feinschritte} Feinschritte je Takt (Euler, wie Modell/segway_modell.py)`;
}
function firmwareWerte() { for (const F of FELDER) if (F[0] !== 'gruppe') $(F[0]).value = F[3]; $('stand').textContent = 'Beiwerte der Firmware (segway_regelung.ino, 28.09.2026) und die gemessene Strecke gesetzt'; }
async function auslegen() {
  $('auslegen').disabled = true; $('simulieren').disabled = true; const w = werte(), basis = parameterAus(w); const t0 = performance.now();
  $('bar').style.width = '0%'; $('stand').textContent = 'Auslegung durch Simulation läuft — Suche über K, Tn, Tv, je Kandidat fünf Läufe (Nennfall, T_kipp × 0,8 und × 1,2, 2 mm Versatz, Stoß 0,3 Nm)';
  await new Promise(r => setTimeout(r, 20));
  // in Häppchen rechnen, damit die Seite atmet
  const opt = { K: [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0], Tn_ms: [50, 65, 80, 100, 120, 150, 200], Tv_anteil: [0.05, 0.1, 0.15], dauer: 4 };
  let zaehler = 0; const gesamt = opt.K.length * opt.Tn_ms.length * opt.Tv_anteil.length;
  const R = SEGWAY.auslegen(basis, opt, (anteil, best) => { zaehler++; if (zaehler % 7 === 0) { $('bar').style.width = (100*anteil).toFixed(0) + '%'; } });
  $('bar').style.width = '100%';
  if (!R.best) { $('stand').textContent = 'kein stabiler Entwurf im Suchraster gefunden'; }
  else {
    const b = R.best; $('N_K').value = b.K; $('N_TN_ms').value = b.Tn_ms; $('N_TV_ms').value = b.Tv_ms.toFixed(3);
    window.LABOR.auslegung = R;
    simulieren();
    $('stand').textContent = `Auslegung: K = ${f(b.K,2)} m/s je rad, Tn = ${f(b.Tn_ms,1)} ms, Tv = ${f(b.Tv_ms,2)} ms (Kosten ${f(b.kosten,2)}); Reserve nach oben ${f(b.reserve_hoch,2)}-fach, nach unten ${f(b.reserve_ab,3)}-fach${b.reserve_gefordert ? '' : ' — KEIN Kandidat erreicht 2,0 / 0,5, gewählt ist der mit der größten Reserve'}; ${R.tabelle.length} stabile Kandidaten, Reserven der ${R.kandidaten.length} günstigsten, in ${f((performance.now()-t0)/1000,1)} s. Beiwerte eingetragen, der Verlauf oben ist damit gerechnet.`;
  }
  $('auslegen').disabled = false; $('simulieren').disabled = false;
}
// ---- Verbindung zum Gerät (Stufe 2)
async function geraetLesen() {
  const adr = $('adresse').value.replace(/\/$/, '');
  $('geraetStand').textContent = 'lese ' + adr + '/werte …';
  try {
    const r = await fetch(adr + '/werte', { cache: 'no-store' }); const t = await r.text();
    $('geraetStand').textContent = 'Antwort von ' + adr + ':'; $('geraetWerte').textContent = t.slice(0, 2000);
  } catch (e) { $('geraetStand').textContent = 'keine Verbindung zu ' + adr + ' — ' + e.message + '. Das Gerät muss im selben Netz stehen (oder sein eigenes Netz „Einachsfahrzeug“ aufspannen: Firmware 2).'; }
}
function start() {
  felderBauen(); $('simulieren').onclick = simulieren; $('auslegen').onclick = auslegen; $('firmware').onclick = firmwareWerte; $('lesen').onclick = geraetLesen; $('abspielen').onclick = abspielen; $('anhalten').onclick = anhalten;
  window.addEventListener('resize', () => bild(ANIM.tSim));
  window.LABOR = { SEGWAY, werte, parameterAus, simulieren, auslegen, abspielen, anhalten, bild, get letzter() { return LETZTER; }, get anim() { return ANIM; } };
  simulieren();
}
document.addEventListener('DOMContentLoaded', start);
"""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Segway-Labor · Fassung {VERSION}</title>
<style>{css}</style>
</head>
<body>
<header>
<h1>Segway-Labor: Modell, Simulation, Auslegung, Gerät</h1>
<p class="small" id="fassung">Fassung {VERSION} · {DATUM} · {NAMENSNENNUNG}</p>
<p class="small">Erst das Gesamtsystem als reines Modell (unten die Herleitung), dann die Schnittstellen zum abgetasteten Regler, dann Auslegung durch Simulation, dann das Gerät. Alles rechnet im Browser, ohne Netz; das Modell ist Zeile für Zeile das der Firmware und wurde gegen das Python-Modell geprüft.</p>
</header>
<main>
<div class="zeile">
  <div class="karte bedien">
    <h2 style="margin-top:0">Einstellen und rechnen</h2>
    <div>
      <button id="simulieren" class="haupt">Simulieren</button>
      <button id="auslegen" title="sucht K, Tn und Tv über ein Raster; jeder Kandidat muss den Nennfall, T_kipp × 0,8 und × 1,2, 2 mm Versatz und einen Stoß von 0,3 Nm bestehen; dann kleinste Kosten aus Einschwingzeit, Überschwingen und Restzittern; für die zwölf günstigsten die Reserven durch Skalieren aller Beiwerte; gewählt wird der günstigste mit mindestens 2-facher Reserve nach oben und 0,5-facher nach unten">Regler automatisch auslegen</button>
      <button id="firmware">Firmware-Werte</button>
      <div class="bar"><div id="bar"></div></div>
      <p class="small" id="stand"></p>
    </div>
    <div id="felder"></div>
  </div>
  <div class="karte bilder">
    <h2 style="margin-top:0">Der Versuch</h2>
    <canvas id="cAnim" style="height:280px"></canvas>
    <div style="margin:-2px 0 10px">
      <button id="abspielen" class="haupt">Abspielen</button><button id="anhalten">Anhalten</button>
      <label class="small" style="margin-left:8px">Tempo <select id="tempo"><option value="0.25">¼</option><option value="0.5">½</option><option value="1" selected>1 : 1</option><option value="2">2×</option></select></label>
      <span class="small" id="zeit" style="margin-left:12px"></span>
      <span class="small" style="margin-left:12px">Neigung 5-fach überhöht gezeichnet; Weg 1 : 1 zur Fahrzeuggröße</span>
    </div>
    <h2>Verlauf — läuft mit</h2>
    <canvas id="c1"></canvas>
    <canvas id="c2"></canvas>
    <canvas id="c3"></canvas>
    <h3>Kennzahlen dieses Laufs</h3>
    <table class="kenn" id="kenn"></table>
  </div>
</div>

<div class="zeile" style="margin-top:18px">
  <div class="karte" style="flex:1 1 480px">
    <h2 style="margin-top:0">Verbindung zum Gerät (Stufe 2)</h2>
    <div class="control" style="grid-template-columns: 1fr 220px 46px"><label for="adresse">Adresse des Segways</label><input id="adresse" type="text" value="http://segway.local" style="width:210px"><span></span></div>
    <button id="lesen">Werte lesen (/werte)</button>
    <button disabled title="kommt mit Firmware 2: /param schreibt K, Tn, Tv, Nullpunkt-Beiwerte in den Flash">Beiwerte auf das Gerät schreiben</button>
    <button disabled title="kommt mit Firmware 2: /stoss löst einen Geschwindigkeitsimpuls aus, /log liefert den Mitschnitt">Stoß auslösen und Mitschnitt holen</button>
    <p class="small" id="geraetStand">Das Gerät hat heute die Endpunkte /werte, /log, /rampe, /rampentest, /nullpunkt, /fahr (Firmware vom 28.09.2026). Beiwerte setzen, Stoß und Zugangspunkt-Rückfall („Einachsfahrzeug“, wenn kein Heimnetz da ist) kommen mit Firmware 2; die Seite auf dem Telefon bekommt der ESP32 aus derselben Quelle.</p>
    <pre id="geraetWerte" style="font-size:12px;white-space:pre-wrap"></pre>
  </div>
  <div class="karte" style="flex:1 1 480px">
    <h2 style="margin-top:0">Kamera (Stufe 4)</h2>
    <p class="small">Vorgesehen: die Laptopkamera aus dieser Seite (getUserMedia), Marken am Fahrzeug verfolgen wie in <code>radpendel_auswertung.py</code>, der Synchronblitz an GPIO 23 setzt den Zeitversatz; der Kamerawinkel wird gegen den Kalman-Winkel des Geräts gestellt, die Stoßantwort gegen die Simulation. Noch nicht gebaut — die Reihenfolge steht im Aufgabenblatt, Teil G.</p>
    <div class="hinweis">Was hier läuft, ist Stufe 1: das Modell mit Auslegung. Stufe 2 (Gerät), 3 (Brücke), 4 (Kamera) und 5 (Nachziehen des Modells) folgen; jede Stufe bekommt ihr Prüfmittel.</div>
  </div>
</div>

<details class="doku">
<summary>Einführung — der Segway im Bild: Gerät, Strukturbilder mit der realen Strecke, der Simulation und der Peripherie des ESP32, Hardwaremodule, Hardwaretest; alle Größen als Variablen mit Verweis auf die Seite im Manuskript-PDF</summary>
<article class="documentation">
{einf}
</article>
</details>

<details class="doku">
<summary>Dokumentation — das Manuskript in dieser Seite: Herleitung der Strecke aus Theorie und Messung, Sensor, Schnittstellen, Anforderungen, Regler, geschlossener Kreis, Hardwaretest</summary>
<article class="documentation">
{doku}
</article>
</details>
</main>
<script>
{modell}
</script>
<script>
{js_ui}
</script>
</body>
</html>
"""


def main() -> int:
    ZIEL.write_text(seite(), encoding="utf-8")
    print(f"{ZIEL.name}: {ZIEL.stat().st_size/1024/1024:.2f} MB (Fassung {VERSION}, {DATUM})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
