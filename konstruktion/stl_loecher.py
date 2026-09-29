#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bohrungen und Ausschnitte in den ebenen Flächen der STL-Teile finden: in einer Ebene bilden die Randkanten
der Dreiecke geschlossene Schleifen — die äußere Kontur und jede Bohrung. Je Schleife Mittelpunkt, mittlerer
Radius und Streuung (klein = Kreis) bzw. Umriss. Ausgabe: stl_loecher.json"""
import json, struct, sys
import numpy as np
from collections import defaultdict
from pathlib import Path
H = Path(__file__).resolve().parent

def lies(p):
    d = Path(p).read_bytes(); n = struct.unpack('<I', d[80:84])[0]
    a = np.frombuffer(d[84:84+50*n], dtype=np.dtype([('n','<3f4'),('v','<9f4'),('a','<u2')]))
    return a['v'].reshape(-1,3,3).astype(float), a['n'].astype(float)

def schleifen(t, nrm, ax, wert, tol=0.05):
    m = (np.abs(np.abs(nrm[:, ax]) - 1) < 1e-3) & (np.abs(t[:, 0, ax] - wert) < tol)
    tri = t[m]
    andere = [i for i in range(3) if i != ax]
    P = np.round(tri[:, :, andere], 3)
    kanten = defaultdict(int); punkte = {}
    for d in P:
        for i in range(3):
            a, b = tuple(d[i]), tuple(d[(i+1) % 3])
            k = (a, b) if a < b else (b, a); kanten[k] += 1
    rand = [k for k, c in kanten.items() if c == 1]
    nb = defaultdict(list)
    for a, b in rand: nb[a].append(b); nb[b].append(a)
    gesehen, loops = set(), []
    for start in nb:
        if start in gesehen: continue
        loop, cur, prev = [start], start, None; gesehen.add(start)
        while True:
            nxt = [q for q in nb[cur] if q != prev and q not in gesehen]
            if not nxt: break
            prev, cur = cur, nxt[0]; loop.append(cur); gesehen.add(cur)
        loops.append(np.array(loop))
    aus = []
    for L in loops:
        if len(L) < 6: continue
        c = L.mean(0); r = np.linalg.norm(L - c, axis=1)
        lo, hi = L.min(0), L.max(0)
        aus.append(dict(n=len(L), mitte=c.round(2).tolist(), r_mittel=round(float(r.mean()), 2), r_streu=round(float(r.std()), 2),
                        umriss=(hi - lo).round(2).tolist(), achsen=''.join('xyz'[i] for i in andere)))
    return sorted(aus, key=lambda s: -s['n'])

TEILE = {'motorhalterung': [(1, 0.0), (2, 5.0), (2, -85.0)], 'radkasten': [(2, 0.0), (2, 43.0), (1, 0.0)],
         'grundplatte': [(2, 5.0)], 'dachplatte': [(2, 5.0)], 'stuetze': [(2, -20.0), (1, 0.0)],
         'akkubuegel': [(0, 0.0), (1, 0.0)], 'sensorpult': [(1, 0.0), (2, 0.0)], 'radnabe': [(2, None)]}
alles = {}
for name, ebenen in TEILE.items():
    t, nrm = lies(H / 'STL' / f'{name}.stl')
    alles[name] = {}
    print(f'== {name}')
    for ax, wert in ebenen:
        if wert is None: continue
        s = schleifen(t, nrm, ax, wert)
        alles[name][f'{"xyz"[ax]}={wert}'] = s
        print(f'  Ebene {"xyz"[ax]}={wert}: {len(s)} Schleifen')
        for L in s[:14]:
            art = 'Kreis' if L['r_streu'] < 0.15 * L['r_mittel'] and L['n'] >= 8 else 'Umriss'
            print(f"     {art:6s} Mitte({L['achsen']})={L['mitte']}  r={L['r_mittel']} ±{L['r_streu']}  Umriss {L['umriss']}  ({L['n']} Pkt)")
(H / 'stl_loecher.json').write_text(json.dumps(alles, indent=1))
