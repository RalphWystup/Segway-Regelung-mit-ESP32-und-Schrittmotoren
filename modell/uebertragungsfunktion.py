#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uebertragungsfunktion.py — die Strecke und der geschlossene Kreis als Übertragungssystem (29.09.2026).

Rechnet aus den GEMESSENEN Streckengrößen (nachweis_gemessen.GEMESSEN) und den Reglerbeiwerten der Firmware
(nachweis_gemessen.ENTWURF, aus dem Quelltext gelesen):

  1. das lineare Zustandsmodell der Strecke  x = (θ, ω, v),  u = v_soll,  Störung M, Versatz s:
         ẋ = A x + B u + B_M M + B_s s,   y = C x + D u
     mit A, B, C, D als Zahlen;
  2. die Übertragungsfunktionen im Laplace-Bereich  G_u(s) = Θ/U  und  G_M(s) = Θ/M, ihre Pole und Nullstellen,
     und die Probe, dass C (sI − A)⁻¹ B dieselbe Funktion ist (zwei Wege);
  3. die Abtastform (Halteglied nullter Ordnung, T = 4 ms):  x[k+1] = Φ x[k] + Γ u[k],  Φ = e^{AT};
     Probe gegen die Feinschritt-Rechnung des geprüften Simulators (segway_entwurf.schritt, Streckenanteil);
  4. die Sprungantwort der offenen Strecke: geschlossene Lösung über e^{At} gegen Runge-Kutta 4 der
     nichtlinearen Bewegungsgleichung (zwei Wege);
  5. den geschlossenen Kreis im Laplace-Bereich: charakteristisches Polynom mit dem Regler der Firmware
     (PID in Normalform, Antriebsverzug, Sensortiefpass), seine Wurzeln, gegen die Eigenwerte des geprüften
     16-Zustands-Modells des abgetasteten Kreises (segway_entwurf.zustandsmatrix), abgebildet mit s = ln(z)/T;
  6. die Reserven: größter Eigenwertbetrag über dem Verstärkungsfaktor, kontinuierlich und abgetastet.

Ergebnisse:  Modell/uebertragungsfunktion.json, Modell/uebertragungsfunktion.txt,
             Bilder/strecke_pole.png, Bilder/strecke_sprungantwort.png, Bilder/kreis_wurzeln.png, Bilder/kreis_reserven.png
Die geprüften Module (segway_modell, segway_entwurf, pruefung_entwurf, nachweis_gemessen) bleiben unverändert.

Aufruf:  python3 Modell/uebertragungsfunktion.py [--kurz]   (--kurz: ohne die Reservenkurve, ca. 40 s gespart)
"""
import json, sys, time
from pathlib import Path
import numpy as np
from scipy.linalg import expm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import segway_entwurf as E
import pruefung_entwurf as P
import nachweis_gemessen as NG          # liefert GEMESSEN, ENTWURF, FW — führt nichts aus

BILDER = H.parent / "Bilder"
KURZ = "--kurz" in sys.argv


def strecke(p):
    """A, B, B_M, B_s, C, D des linearen Streckenmodells (θ, ω, v), Eingang v_soll."""
    m, l, J, d, g, tau, w = p.m, p.l, p.J, p.d, p.g, p.tau_mot, p.sensor_w
    A = np.array([[0.0, 1.0, 0.0],
                  [m * g * l / J, -d / J, m * l / (J * tau)],
                  [0.0, 0.0, -1.0 / tau]])
    B = np.array([[0.0], [-m * l / (J * tau)], [1.0 / tau]])
    B_M = np.array([[0.0], [1.0 / J], [0.0]])
    B_s = np.array([[0.0], [m * g / J], [0.0]])
    # Ausgänge: wahre Neigung θ; Drehrate ω; Beschleunigungswinkel des Sensors θ − a_s/g mit a_s = v̇ + w ω̇
    # (linear, vor dem Tiefpass). v̇ = (u − v)/τ, ω̇ = zweite Zeile von A x + B u.
    C = np.zeros((3, 3)); D = np.zeros((3, 1))
    C[0] = [1, 0, 0]
    C[1] = [0, 1, 0]
    C[2] = np.array([1, 0, 0]) - (np.array([0, 0, -1 / tau]) + w * A[1]) / g
    D[2, 0] = -(1 / tau + w * B[1, 0]) / g
    return A, B, B_M, B_s, C, D


def polynom_strecke(p):
    """Zähler und Nenner von G_u(s) = Θ/U und G_M(s) = Θ/M, Koeffizienten nach fallender Potenz."""
    m, l, J, d, g, tau = p.m, p.l, p.J, p.d, p.g, p.tau_mot
    Dq = np.array([J, d, -m * g * l])                       # J s² + d s − m g l
    nenner = np.polymul([tau, 1.0], Dq)                     # (1 + τ s)(J s² + d s − m g l)
    zaehler_u = np.array([-m * l, 0.0])                     # − m l s
    return zaehler_u, nenner, np.array([1.0]), Dq


def G_aus_zustand(A, B, C0, s):
    """C0 (sI − A)⁻¹ B an der Stelle s — der zweite Weg zur Übertragungsfunktion."""
    n = A.shape[0]
    return complex((C0 @ np.linalg.solve(s * np.eye(n) - A, B))[0, 0])


def euler_fein(p, T):
    """Φ und Γ, wie sie der geprüfte Simulator rechnet (Streckenanteil von segway_entwurf.schritt, 32 Feinschritte)."""
    n_u = p.feinschritte; dt = T / n_u
    def lauf(th, om, v, u):
        for _ in range(n_u):
            dv = (u - v) / p.tau_mot
            v = v + dv * dt
            dom = (p.m * p.g * p.l * th - p.m * p.l * dv - p.d * om) / p.J
            om = om + dom * dt
            th = th + om * dt
        return np.array([th, om, v])
    Phi = np.column_stack([lauf(*e, 0.0) for e in np.eye(3)])
    Gam = lauf(0, 0, 0, 1.0).reshape(3, 1)
    return Phi, Gam


def rk4_nichtlinear(p, u, dauer, dt, s_versatz=0.0):
    """Runge-Kutta 4 der vollständigen Bewegungsgleichung, Antrieb mit Verzug, Eingang u konstant."""
    def f(z):
        th, om, v = z
        dv = (u - v) / p.tau_mot
        dom = (p.m * p.g * (p.l * np.sin(th) + s_versatz * np.cos(th))
               - p.m * dv * (p.l * np.cos(th) - s_versatz * np.sin(th)) - p.d * om) / p.J
        return np.array([om, dom, dv])
    n = int(round(dauer / dt)); z = np.zeros(3); t = np.zeros(n + 1); TH = np.zeros(n + 1)
    for k in range(n):
        k1 = f(z); k2 = f(z + dt / 2 * k1); k3 = f(z + dt / 2 * k2); k4 = f(z + dt * k3)
        z = z + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4); t[k + 1] = (k + 1) * dt; TH[k + 1] = z[0]
    return t, TH


def kreis_polynom(p, faktor=1.0, mit_verzug=True):
    """Charakteristisches Polynom des geschlossenen Kreises im Laplace-Bereich.

    Regler der Firmware (Schicht 2) in Normalform  u = K (θ_m + (1/Tn)∫θ_m dt + Tv θ̇_m),  θ_m = θ/(1 + τ_lp s);
    Strecke G_u(s) = −m l s / ((1+τ s)(J s² + d s − m g l)).  Aus 1 − G_u C = 0 folgt
        (1+τ s)(1+τ_lp s)(J s² + d s − m g l) Tn  +  m l K (Tn Tv s² + Tn s + 1)  =  0.
    Der Faktor s des Streckenzählers kürzt sich gegen den Integrator des Reglers: eine Wurzel bei s = 0 bleibt
    im Kreis (siehe Manuskript, Teil V) — sie ist hier NICHT enthalten, das Polynom beschreibt den Rest.
    Mit τ = τ_lp = 0 bleibt  (J + m l K Tv) s² + (d + m l K) s + m l (K/Tn − g).
    """
    m, l, J, d, g = p.m, p.l, p.J, p.d, p.g
    K, Tn, Tv = p.N_K * faktor, p.N_TN, p.N_TV
    Dq = np.array([J, d, -m * g * l])
    if mit_verzug:
        links = np.polymul(np.polymul([p.tau_mot, 1.0], [p.t_dlpf, 1.0]), Dq) * Tn
    else:
        links = Dq * Tn
    rechts = m * l * K * np.array([Tn * Tv, Tn, 1.0])
    return np.polyadd(links, rechts)


def main():
    t0 = time.time()
    p = P.parameter({**NG.ENTWURF, **NG.GEMESSEN})
    T = 1.0 / p.f_gitter
    m, l, J, d, g, tau = p.m, p.l, p.J, p.d, p.g, p.tau_mot
    aus = {"datum": "2026-09-29", "parameter": dict(m=m, l=l, J=J, d=d, g=g, tau_mot=tau, t_dlpf=p.t_dlpf,
                                                   sensor_w=p.sensor_w, sensor_u=p.sensor_u, T=T,
                                                   K=p.N_K, Tn=p.N_TN, Tv=p.N_TV, K_N=p.NK_K, Tn_N=p.NK_TN,
                                                   r_rad=p.r_rad, Ns=p.Ns, v_je_hz=2 * np.pi * p.r_rad / p.Ns)}
    Z = []                                   # Zeilen des Textberichts
    def zeile(s=""): Z.append(s)

    # ---- 1. Zustandsmodell --------------------------------------------------------------------------------------
    A, B, B_M, B_s, C, D = strecke(p)
    ew_A = np.sort_complex(np.linalg.eigvals(A))
    T_kipp = np.sqrt(J / (m * g * l))
    aus["zustandsmodell"] = dict(A=A.tolist(), B=B.ravel().tolist(), B_M=B_M.ravel().tolist(), B_s=B_s.ravel().tolist(),
                                 C=C.tolist(), D=D.ravel().tolist(), eigenwerte=[complex(z).real for z in ew_A],
                                 T_kipp_s=T_kipp, mgl_Nm=m * g * l, ml_kgm=m * l)
    zeile("1  ZUSTANDSMODELL DER STRECKE  x = (θ, ω, v), u = v_soll")
    zeile(f"   m = {m:.4f} kg, l = {l*1e3:.1f} mm, J = {J:.5e} kg m², d = {d} Nms, τ_mot = {tau*1e3:.1f} ms, w = {p.sensor_w*1e3:.0f} mm")
    zeile(f"   m g l = {m*g*l:.5f} Nm, m l = {m*l:.5f} kg m, T = sqrt(J/(m g l)) = {T_kipp*1e3:.2f} ms")
    for i, name in enumerate(["θ̇", "ω̇", "v̇"]):
        zeile(f"   {name} = " + " ".join(f"{A[i,j]:+12.4f}·{v}" for j, v in enumerate(["θ", "ω", "v"])) + f" {B[i,0]:+12.4f}·u")
    zeile(f"   Eigenwerte von A: {', '.join(f'{z.real:+.4f}' for z in ew_A)} 1/s   (1/T = {1/T_kipp:.4f}, 1/τ = {1/tau:.1f})")

    # ---- 2. Übertragungsfunktionen ------------------------------------------------------------------------------
    zu, ne, zM, Dq = polynom_strecke(p)
    pole = np.sort_complex(np.roots(ne)); nullst = np.roots(zu)
    pole_D = np.roots(Dq)
    s_probe = [0.5j, 3.0 + 2.0j, -20.0 + 15.0j, 300.0j]
    abw = max(float(abs(np.polyval(zu, s) / np.polyval(ne, s) - G_aus_zustand(A, B, C[0:1], s))) /
              abs(G_aus_zustand(A, B, C[0:1], s)) for s in s_probe)
    abwM = max(float(abs(1.0 / np.polyval(Dq, s) - G_aus_zustand(A, B_M, C[0:1], s))) /
               abs(G_aus_zustand(A, B_M, C[0:1], s)) for s in s_probe)
    # Normalform  G_u = −(s/g) / ((1+τ s)(T² s² + 2 δ T s − 1)),  2 δ T = d/(m g l)
    delta = d / (m * g * l) / (2 * T_kipp)
    aus["uebertragungsfunktion"] = dict(
        G_u=dict(zaehler=zu.tolist(), nenner=ne.tolist(), pole=[complex(z).real for z in pole], nullstellen=[float(nullst[0].real)],
                 pol_instabil=float(max(pole_D.real)), pol_stabil=float(min(pole_D.real)), pol_antrieb=-1 / tau,
                 normalform=dict(T=T_kipp, delta=delta, verstaerkung_1_durch_g=1 / g)),
        G_M=dict(zaehler=[1.0], nenner=Dq.tolist(), pole=[float(z.real) for z in pole_D]),
        probe_zwei_wege=dict(abweichung_rel_G_u=float(abw), abweichung_rel_G_M=float(abwM), stellen=[str(s) for s in s_probe]),
        gleichgewicht=dict(theta_gl_rad_je_m=-1 / l, tafel=[dict(s_mm=s, theta_grad=float(np.degrees(-np.arctan(s * 1e-3 / l))))
                                                             for s in (0.5, 1.0, 2.0, 3.0, 4.0)]))
    zeile(""); zeile("2  ÜBERTRAGUNGSFUNKTIONEN (Laplace)")
    zeile(f"   G_u(s) = Θ/U = −m l s / ((1 + τ s)(J s² + d s − m g l)) = ({zu[0]:.5f} s) / ({ne[0]:.4e} s³ + {ne[1]:.4e} s² + {ne[2]:.4e} s + {ne[3]:.4e})")
    zeile(f"   Pole: {', '.join(f'{z.real:+.4f}' for z in pole)} 1/s; Nullstelle s = 0")
    zeile(f"   Normalform: −(s/g) / ((1+τ s)(T² s² + 2δT s − 1)),  T = {T_kipp*1e3:.2f} ms, δ = {delta:.5f}")
    zeile(f"   G_M(s) = Θ/M = 1 / (J s² + d s − m g l), Pole {pole_D[0].real:+.4f}, {pole_D[1].real:+.4f} 1/s")
    zeile(f"   Probe C(sI−A)⁻¹B gegen die Polynomform an {len(s_probe)} Stellen: {abw:.1e} (G_u), {abwM:.1e} (G_M) relativ")

    # ---- 3. Abtastform ------------------------------------------------------------------------------------------
    Phi = expm(A * T); Gam = np.linalg.solve(A, (Phi - np.eye(3)) @ B)
    Phi_e, Gam_e = euler_fein(p, T)
    ew_Phi = np.sort_complex(np.linalg.eigvals(Phi)); ew_Phi_e = np.sort_complex(np.linalg.eigvals(Phi_e))
    rel = lambda a, b: float(abs(a - b) / max(abs(b), 1e-300))
    d_mech = max(rel(Phi_e[i, j], Phi[i, j]) for i in (0, 1) for j in (0, 1))
    d_antrieb = rel(Phi_e[2, 2], Phi[2, 2])
    aus["abtastform"] = dict(T=T, Phi=Phi.tolist(), Gamma=Gam.ravel().tolist(), Phi_euler=Phi_e.tolist(), Gamma_euler=Gam_e.ravel().tolist(),
                             eigenwerte_Phi=[complex(z).real for z in ew_Phi], eigenwerte_Phi_euler=[complex(z).real for z in ew_Phi_e],
                             abweichung_mechanik_rel=d_mech, abweichung_antrieb_rel=d_antrieb,
                             erwartet_antrieb_rel=float(abs((1 - T / p.feinschritte / tau) ** p.feinschritte - np.exp(-T / tau)) / np.exp(-T / tau)))
    zeile(""); zeile(f"3  ABTASTFORM  x[k+1] = Φ x[k] + Γ u[k],  T = {T*1e3:.0f} ms, Φ = e^(AT)")
    for i in range(3):
        zeile("   " + " ".join(f"{Phi[i,j]:+.6f}" for j in range(3)) + f"   | Γ {Gam[i,0]:+.6f}")
    zeile(f"   Eigenwerte Φ: {', '.join(f'{z.real:.6f}' for z in ew_Phi)}  (= e^(λT): {', '.join(f'{np.exp(z.real*T):.6f}' for z in ew_A)})")
    zeile(f"   Feinschritt-Euler des Simulators (32 Schritte): Mechanikblock {d_mech:.2e} relativ, Antriebszeile {d_antrieb:.2e} "
          f"(erwartet für Euler mit λτ-Schritt {aus['abtastform']['erwartet_antrieb_rel']:.2e})")

    # ---- 4. Sprungantwort der offenen Strecke -------------------------------------------------------------------
    u0 = 0.01; dauer = 0.35; dt_f = T / p.feinschritte
    t_l = np.arange(0, dauer + 1e-12, dt_f); Phi_f = expm(A * dt_f); Gam_f = np.linalg.solve(A, (Phi_f - np.eye(3)) @ B)
    x = np.zeros((3, 1)); th_l = [0.0]
    for _ in t_l[1:]:
        x = Phi_f @ x + Gam_f * u0; th_l.append(float(x[0, 0]))
    th_l = np.array(th_l)
    t_n, th_n = rk4_nichtlinear(p, u0, dauer, dt_f)
    i_ref = int(round(0.3 / dt_f)); i_max = int(np.argmax(np.abs(th_n)))
    abw_sprung = float(abs(th_l[i_ref] - th_n[i_ref]) / abs(th_n[i_ref]))
    aus["sprungantwort"] = dict(u0_m_s=u0, dauer_s=dauer, t=t_l[::32].tolist(), theta_linear_grad=np.degrees(th_l[::32]).tolist(),
                                theta_rk4_grad=np.degrees(th_n[::32]).tolist(), theta_bei_0_3s_grad=float(np.degrees(th_n[i_ref])),
                                abweichung_rel_bei_0_3s=abw_sprung, theta_min_grad=float(np.degrees(th_n.min())),
                                t_theta_min_s=float(t_n[int(np.argmin(th_n))]))
    zeile(""); zeile(f"4  SPRUNGANTWORT  u = {u0} m/s Sprung, offene Strecke, θ(0) = 0")
    zeile(f"   θ(0,3 s) = {np.degrees(th_n[i_ref]):+.4f}° (RK4 nichtlinear) gegen {np.degrees(th_l[i_ref]):+.4f}° (e^(At)); Abweichung {abw_sprung:.2e}")
    zeile(f"   erst nach hinten (θ_min = {np.degrees(th_n.min()):+.4f}° bei {t_n[int(np.argmin(th_n))]:.3f} s), dann Kippen mit e^(t/T)")

    # ---- 5. Geschlossener Kreis im Laplace-Bereich ----------------------------------------------------------------
    pk = kreis_polynom(p); wk = np.roots(pk)
    pk0 = kreis_polynom(p, mit_verzug=False); wk0 = np.roots(pk0)
    a2, a1, a0 = pk0
    omega_n = np.sqrt(a0 / a2); zeta = a1 / (2 * np.sqrt(a0 * a2))
    k_i = p.N_K / p.N_TN
    A16, K0, K1 = E.zustandsmatrix(p)
    lose = [j for j in range(A16.shape[0]) if np.max(np.abs(np.delete(A16[:, j], j))) < 1e-12]
    A16r = np.delete(np.delete(A16, lose, axis=0), lose, axis=1) if lose else A16
    z16 = np.linalg.eigvals(A16r)
    s16 = np.log(z16.astype(complex)) / T
    # Zuordnung: zu jeder kontinuierlichen Wurzel die nächste abgebildete diskrete
    paare = []
    for w in wk:
        j = int(np.argmin(np.abs(s16 - w)))
        paare.append(dict(s_kontinuierlich=[float(w.real), float(w.imag)], s_diskret=[float(s16[j].real), float(s16[j].imag)],
                          z_diskret=[float(z16[j].real), float(z16[j].imag)], abstand_rel=float(abs(s16[j] - w) / abs(w))))
    # die Kippbewegung: das konjugierte Paar mit dem kleinsten Betrag unter den schnellen Wurzeln
    kipp = sorted([pp for pp in paare if abs(pp["s_kontinuierlich"][1]) > 1e-9], key=lambda pp: abs(complex(*pp["s_kontinuierlich"])))
    aus["kreis"] = dict(polynom=pk.tolist(), wurzeln=[[float(w.real), float(w.imag)] for w in wk],
                        polynom_ohne_verzug=pk0.tolist(), wurzeln_ohne_verzug=[[float(w.real), float(w.imag)] for w in wk0],
                        omega_n=float(omega_n), zeta=float(zeta), f_n_hz=float(omega_n / 2 / np.pi), k_i=k_i, k_i_groesser_g=bool(k_i > g),
                        k_p=p.N_K, k_d=p.N_K * p.N_TV,
                        diskret=dict(z=[[float(z.real), float(z.imag)] for z in z16], s=[[float(s.real), float(s.imag)] for s in s16],
                                     zmax=float(np.max(np.abs(z16))), K0=K0, K1=K1, zustaende=int(A16r.shape[0]), abgetrennt=lose),
                        paare=paare, kipp=kipp[0] if kipp else None)
    zeile(""); zeile("5  GESCHLOSSENER KREIS (Laplace) mit dem Regler der Firmware")
    zeile(f"   K = {p.N_K:.4f} m/s je rad, Tn = {p.N_TN:.4f} s, Tv = {p.N_TV:.4f} s → k_p = {p.N_K:.3f}, k_i = K/Tn = {k_i:.2f} (> g = {g}: {k_i > g}), k_d = {p.N_K*p.N_TV:.4f}")
    zeile(f"   ohne Verzüge: ({a2:.5e}) s² + ({a1:.5e}) s + ({a0:.5e}) = 0 → ω_n = {omega_n:.3f} 1/s ({omega_n/2/np.pi:.3f} Hz), ζ = {zeta:.3f}")
    zeile(f"   mit τ_mot = {tau*1e3:.0f} ms und τ_lp = {p.t_dlpf*1e3:.1f} ms, Grad 4: Wurzeln " + ", ".join(f"{w.real:+.3f}{w.imag:+.3f}j" for w in wk))
    zeile(f"   16-Zustands-Modell (abgetastet, {A16r.shape[0]} Zustände nach Abtrennen von {lose}): |z|max = {np.max(np.abs(z16)):.5f}")
    for pp in paare:
        zeile(f"   s = {pp['s_kontinuierlich'][0]:+8.3f}{pp['s_kontinuierlich'][1]:+8.3f}j  ↔  ln(z)/T = {pp['s_diskret'][0]:+8.3f}{pp['s_diskret'][1]:+8.3f}j   Abstand {pp['abstand_rel']:.3f} relativ")

    # ---- 6. Reserven über dem Verstärkungsfaktor -------------------------------------------------------------------
    if not KURZ:
        fakt = np.concatenate([np.linspace(0.3, 1.0, 15), np.linspace(1.0, 3.0, 21)[1:]])
        zmax_d = []; smax_k = []
        from copy import copy
        for f in fakt:
            q = copy(p); q.N_K = p.N_K * f; q.NK_K = p.NK_K * f
            zmax_d.append(E.kennzahlen(q)["zmax"])
            smax_k.append(float(np.max(np.roots(kreis_polynom(p, f)).real)))
        zmax_d = np.array(zmax_d); smax_k = np.array(smax_k)
        def nullstelle(x, y, ziel, seite):
            idx = np.where(np.sign(y[:-1] - ziel) != np.sign(y[1:] - ziel))[0]
            if seite == "oben": idx = [i for i in idx if x[i] >= 1.0]
            else: idx = [i for i in idx if x[i] < 1.0]
            if not len(idx): return None
            i = idx[0] if seite == "oben" else idx[-1]
            return float(x[i] + (ziel - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
        aus["reserven"] = dict(faktor=fakt.tolist(), zmax_diskret=zmax_d.tolist(), re_smax_kontinuierlich=smax_k.tolist(),
                               grenze_oben_diskret=nullstelle(fakt, zmax_d, 1.0, "oben"), grenze_unten_diskret=nullstelle(fakt, zmax_d, 1.0, "unten"),
                               grenze_oben_kont=nullstelle(fakt, smax_k, 0.0, "oben"), grenze_unten_kont=nullstelle(fakt, smax_k, 0.0, "unten"),
                               reserve_oben_bisektion=E.verstaerkungsreserve(p), reserve_unten_bisektion=E.abschwaechreserve(p))
        r = aus["reserven"]
        zeile(""); zeile("6  RESERVEN über dem Faktor an K und K_N")
        zeile(f"   abgetastet (|z|max = 1): oben {r['grenze_oben_diskret']}, unten {r['grenze_unten_diskret']}; Bisektion {r['reserve_oben_bisektion']:.3f} / {r['reserve_unten_bisektion']:.3f}")
        zeile(f"   kontinuierlich (Re s = 0, Kreis Grad 4 ohne Schicht 4): oben {r['grenze_oben_kont']}, unten {r['grenze_unten_kont']}")

    # ---- Bilder -------------------------------------------------------------------------------------------------
    BILDER.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 11})
    # Pole der Strecke
    fig, ax = plt.subplots(figsize=(8, 5.4))
    ax.axhline(0, color="#999", lw=0.8); ax.axvline(0, color="#999", lw=0.8)
    ax.plot([z.real for z in pole_D], [0, 0], "x", ms=12, mew=2.5, color="#1b3a8f", label="Pole der Mechanik  J s² + d s − m g l = 0")
    ax.plot([0], [0], "o", ms=10, mfc="none", mew=2, color="#b0171f", label="Nullstelle s = 0 (Geschwindigkeit wirkt nur über ihre Änderung)")
    ax.annotate(f"instabil: s = +{pole_D.real.max():.2f} 1/s ≈ 1/T\nT = {T_kipp*1e3:.1f} ms (Radpendel)", (pole_D.real.max(), 0), (pole_D.real.max() - 1, 4),
                arrowprops=dict(arrowstyle="->"), fontsize=10, ha="right")
    ax.annotate(f"stabil: s = {pole_D.real.min():.2f} 1/s", (pole_D.real.min(), 0), (pole_D.real.min() - 1, -4), arrowprops=dict(arrowstyle="->"), fontsize=10, ha="right")
    ax.text(-13.5, 8.5, f"dritter Pol: Antrieb, s = −1/τ = {-1/tau:.0f} 1/s (außerhalb des Bildes)", fontsize=10, color="#555")
    ax.set_xlim(-14, 14); ax.set_ylim(-10, 10); ax.set_xlabel("Re s  [1/s]"); ax.set_ylabel("Im s  [1/s]"); ax.grid(alpha=0.3)
    ax.set_title("Pole und Nullstelle der Strecke  G_u(s) = Θ(s)/V_soll(s), gemessene Größen 28.09.2026", fontsize=11)
    ax.legend(loc="lower left", fontsize=9); fig.tight_layout(); fig.savefig(BILDER / "strecke_pole.png", dpi=150); plt.close(fig)
    # Sprungantwort
    fig, ax = plt.subplots(2, 1, figsize=(8, 6.4), sharex=True)
    ax[0].plot(t_n, np.degrees(th_n), color="#1b3a8f", lw=2, label="Runge-Kutta 4 der nichtlinearen Bewegungsgleichung")
    ax[0].plot(t_l, np.degrees(th_l), "--", color="#b0171f", lw=1.5, label="lineares Zustandsmodell, x[k+1] = e^{A dt} x[k] + Γ u")
    ax[0].axhline(0, color="#999", lw=0.8); ax[0].set_ylabel("Neigung θ  [°]"); ax[0].legend(fontsize=9); ax[0].grid(alpha=0.3)
    ax[0].set_title(f"Offene Strecke: Sprung der Sollgeschwindigkeit um {u0*1e3:.0f} mm/s, θ(0) = 0", fontsize=11)
    ax[1].plot(t_n, np.degrees(th_l - th_n) * 1e3, color="#2e7d32"); ax[1].set_ylabel("Unterschied  [10⁻³ °]"); ax[1].set_xlabel("Zeit  [s]"); ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(BILDER / "strecke_sprungantwort.png", dpi=150); plt.close(fig)
    # Wurzeln des Kreises
    fig, ax = plt.subplots(2, 1, figsize=(8, 10))
    ax[0].axhline(0, color="#999", lw=0.8); ax[0].axvline(0, color="#999", lw=0.8)
    ax[0].plot([z.real for z in pole_D], [0, 0], "x", ms=11, mew=2, color="#888", label="offene Strecke (Pole)")
    ax[0].plot(wk.real, wk.imag, "x", ms=12, mew=2.5, color="#1b3a8f", label="Kreis, Laplace (Grad 4, ohne Schicht 4)")
    ax[0].plot(s16.real, s16.imag, "o", ms=7, mfc="none", mew=1.8, color="#b0171f", label="16-Zustands-Modell, s = ln(z)/T")
    ax[0].set_xlim(-60, 12); ax[0].set_ylim(-30, 30); ax[0].set_xlabel("Re s  [1/s]"); ax[0].set_ylabel("Im s  [1/s]"); ax[0].grid(alpha=0.3)
    ax[0].set_title("s-Ebene: der Regler zieht den instabilen Pol nach links", fontsize=10); ax[0].legend(fontsize=8, loc="lower left")
    if kipp:
        kk = kipp[0]; ax[0].annotate(f"Kippbewegung\n{abs(kk['s_kontinuierlich'][1])/2/np.pi:.2f} Hz, Abklingen {-1/kk['s_kontinuierlich'][0]*1e3:.0f} ms",
                                     (kk["s_kontinuierlich"][0], kk["s_kontinuierlich"][1]), (-45, 20), arrowprops=dict(arrowstyle="->"), fontsize=9)
    th = np.linspace(0, 2 * np.pi, 400); ax[1].plot(np.cos(th), np.sin(th), color="#999", lw=0.8)
    ax[1].plot(z16.real, z16.imag, "o", ms=7, mfc="none", mew=1.8, color="#b0171f", label="Eigenwerte des abgetasteten Kreises")
    zk = np.exp(wk * T); ax[1].plot(zk.real, zk.imag, "x", ms=11, mew=2, color="#1b3a8f", label="Laplace-Wurzeln, z = e^{sT}")
    ax[1].set_aspect("equal"); ax[1].set_xlim(-0.2, 1.1); ax[1].set_ylim(-0.65, 0.65); ax[1].set_xlabel("Re z"); ax[1].set_ylabel("Im z"); ax[1].grid(alpha=0.3)
    ax[1].set_title(f"z-Ebene, T = 4 ms: alle |z| < 1, größter Betrag {np.max(np.abs(z16)):.5f}", fontsize=10); ax[1].legend(fontsize=8, loc="lower left")
    fig.tight_layout(); fig.savefig(BILDER / "kreis_wurzeln.png", dpi=150); plt.close(fig)
    if not KURZ:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(fakt, zmax_d, color="#b0171f", lw=2, label="abgetasteter Kreis, 16 Zustände: größter Eigenwertbetrag |z|max")
        ax.plot(fakt, np.exp(smax_k * T), "--", color="#1b3a8f", lw=1.6, label="Laplace-Kreis Grad 4: e^{T·max Re s}")
        ax.axhline(1.0, color="#333", lw=1); ax.axvline(1.0, color="#999", lw=0.8)
        for gz, txt in ((r["grenze_unten_diskret"], "untere Grenze"), (r["grenze_oben_diskret"], "obere Grenze")):
            if gz: ax.axvline(gz, color="#b0171f", lw=0.8, ls=":"); ax.text(gz, 1.0035, f"{txt}\n×{gz:.2f}", ha="center", fontsize=9, color="#b0171f")
        ax.set_xlabel("Faktor an allen Reglerbeiwerten (K und K_N)"); ax.set_ylabel("größter Eigenwertbetrag"); ax.grid(alpha=0.3)
        ax.set_ylim(0.99, 1.012); ax.legend(fontsize=9, loc="upper center")
        ax.set_title("Verstärkungsreserve: stabil, solange die Kurve unter 1 bleibt", fontsize=11)
        fig.tight_layout(); fig.savefig(BILDER / "kreis_reserven.png", dpi=150); plt.close(fig)

    aus["dauer_s"] = time.time() - t0
    (H / "uebertragungsfunktion.json").write_text(json.dumps(aus, indent=1, ensure_ascii=False), encoding="utf-8")
    kopf = ["ÜBERTRAGUNGSFUNKTION, ZUSTANDSMODELL UND GESCHLOSSENER KREIS — gemessene Strecke, Regler der Firmware",
            f"erzeugt von Modell/uebertragungsfunktion.py am {aus['datum']}, Rechenzeit {aus['dauer_s']:.1f} s", ""]
    (H / "uebertragungsfunktion.txt").write_text("\n".join(kopf + Z) + "\n", encoding="utf-8")
    print("\n".join(kopf + Z))


if __name__ == "__main__":
    main()
