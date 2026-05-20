# -*- coding: utf-8 -*-
"""
Lightweight CUT_Rigid constitutive engine for CUT_embedded_wall_anchors_LP.py.
No GUI, no Tkinter, no file/image loading.

Stress convention:
- sigma_v is TOTAL vertical stress, including surcharge q where applicable.
- u is pore pressure.
- sigma_v_eff = sigma_v - u.
- CUT equations receive sigma_v and u explicitly.
- slope correction is applied in effective stresses and returns total horizontal stress.
"""
from __future__ import annotations
import math
import cmath
from typing import Optional

M_FULL = 1.0e9
C_PRIME_MIN = 1.0e-5
PHI_PRIME_MIN_DEG = 1.0e-6

class SideData:
    def __init__(self, beta_deg=0.0, q_real=0.0, z_w=1.0e30, gamma=18.0, gamma_sat=20.0,
                 c_prime=1.0e-5, phi_prime_deg=30.0, E_s=20000.0, nu=0.3, layers=None):
        self.beta_deg = float(beta_deg)
        self.q_real = float(q_real)
        self.z_w = float(z_w)
        self.gamma = float(gamma)
        self.gamma_sat = float(gamma_sat)
        self.c_prime = max(float(c_prime), C_PRIME_MIN)
        self.phi_prime_deg = max(float(phi_prime_deg), PHI_PRIME_MIN_DEG)
        self.E_s = float(E_s)
        self.nu = float(nu)
        self.layers = [] if layers is None else layers

class SeismicData:
    def __init__(self, a_v=0.0, k_v=0.0, theta_eq_deg=0.0):
        self.a_v = float(a_v)
        self.k_v = float(k_v)
        self.theta_eq_deg = float(theta_eq_deg)

def _safe_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value}.")

def _regularize_side_data(sd: SideData) -> SideData:
    return SideData(sd.beta_deg, sd.q_real, sd.z_w, sd.gamma, sd.gamma_sat,
                    max(sd.c_prime, C_PRIME_MIN), max(sd.phi_prime_deg, PHI_PRIME_MIN_DEG),
                    sd.E_s, sd.nu, sd.layers)

def xi_parameters(m: float):
    m = max(float(m), 1.0)
    if m >= M_FULL:
        return 0.0, 1.0, -1.0
    xi = (m - 1.0) / (m + 1.0) - 1.0
    xi1 = 1.0 + xi
    xi2 = 2.0 / m - 1.0
    return xi, xi1, xi2

def delta_x_max(z_local, H_quad, E_s, nu, DeltaK, a_v, sigma_v, u):
    if z_local <= 0.0:
        return 0.0
    _safe_positive("H_quad", H_quad)
    _safe_positive("E_s", E_s)
    sigma_eff = sigma_v - u
    if sigma_eff <= 0.0:
        return 0.0
    z_over_H_eff = min(float(z_local) / float(H_quad), 0.5)
    den = z_over_H_eff if z_over_H_eff > 1e-12 else 1e-12
    shape = ((1.0 + z_over_H_eff) ** 3 * (1.0 - z_over_H_eff)) / den
    return (math.pi / 4.0) * (1.0 - float(nu) ** 2) / float(E_s) * shape * float(H_quad) * abs(float(DeltaK)) * (1.0 - float(a_v)) * sigma_eff

def delta_x_M(H_quad, E_s, nu, DeltaK, a_v, sigma_v_mid, u_mid):
    return delta_x_max(0.5 * float(H_quad), H_quad, E_s, nu, DeltaK, a_v, sigma_v_mid, u_mid)

def mobilization_m(dx_abs, dx_M, z_local, H_quad):
    dx_abs = abs(float(dx_abs))
    if dx_abs <= 0.0:
        return 1.0
    if dx_M is None or dx_M <= 0.0:
        return M_FULL
    if dx_abs >= dx_M:
        return M_FULL
    ratio = dx_abs / dx_M
    base = float(H_quad) / max(float(z_local), 1e-12)
    m = (1.0 + ratio * (base ** (1.0 + ratio))) / (1.0 - ratio)
    return max(1.0, m)

def compute_A0_B1_active(phi_prime_deg, c_prime, xi, theta_eq_deg, a_v, sigma_v, u):
    phi = math.radians(phi_prime_deg)
    sin_phi = math.sin(phi); tan_phi = math.tan(phi)
    theta_eq = math.radians(theta_eq_deg)
    denom = (1.0 - a_v) * (sigma_v - u)
    _safe_positive("(1-a_v)(sigma_v-u)", denom)
    A0 = ((1.0 - sin_phi) / (1.0 + sin_phi)) * (
        1.0 - xi * sin_phi + math.tan(theta_eq) * tan_phi * (2.0 + xi * (1.0 - sin_phi))
    )
    B1 = (2.0 * c_prime / denom) * math.tan(math.pi / 4.0 - phi / 2.0)
    return A0, B1

def compute_A0_B1_passive(phi_prime_deg, c_prime, xi, xi1, xi2, theta_eq_deg, a_v, sigma_v, u):
    phi = math.radians(phi_prime_deg)
    sin_phi = math.sin(phi); tan_phi = math.tan(phi)
    theta_eq = math.radians(theta_eq_deg)
    denom = (1.0 - a_v) * (sigma_v - u)
    _safe_positive("(1-a_v)(sigma_v-u)", denom)
    ratio = math.tan(math.pi / 4.0 + phi / 2.0) / math.tan(math.pi / 4.0 - phi / 2.0)
    A0 = (((1.0 + sin_phi) / (1.0 - sin_phi)) ** xi1) * (
        1.0 + xi * sin_phi + xi2 * math.tan(theta_eq) * tan_phi * (2.0 + xi * (1.0 + sin_phi))
    )
    B1 = (2.0 * c_prime / denom) * math.tan(math.pi / 4.0 - phi / 2.0) * (ratio ** xi1)
    return A0, B1

def compute_C1(A0, c_prime, phi_prime_deg, a_v, sigma_v, u):
    tan_phi = math.tan(math.radians(phi_prime_deg))
    _safe_positive("tan(phi')", abs(tan_phi))
    denom = (1.0 - a_v) * (sigma_v - u) * tan_phi
    _safe_positive("(1-a_v)(sigma_v-u)tan(phi')", abs(denom))
    return (2.0 * c_prime / denom) + 1.0 + A0

def _real_cuberoot(x):
    return x ** (1.0 / 3.0) if x >= 0 else -((-x) ** (1.0 / 3.0))

def _select_stable_root(a0, b0, c0, d0):
    # Robust real cubic fallback: solve depressed cubic and choose bounded root with smallest |phi_m|.
    A = b0 / a0; B = c0 / a0; C = d0 / a0
    p = B - A * A / 3.0
    q = 2.0 * A**3 / 27.0 - A * B / 3.0 + C
    disc = (q / 2.0) ** 2 + (p / 3.0) ** 3
    cand = []
    if disc >= -1e-18:
        disc = max(0.0, disc)
        y = _real_cuberoot(-q/2.0 + math.sqrt(disc)) + _real_cuberoot(-q/2.0 - math.sqrt(disc))
        cand.append(y - A/3.0)
    else:
        radius = 2.0 * math.sqrt(max(0.0, -p / 3.0))
        arg = (3.0*q/(2.0*p))*math.sqrt(-3.0/p) if abs(p) > 1e-300 else 0.0
        arg = max(-1.0, min(1.0, arg))
        angle = math.acos(arg)
        for k in range(3):
            y = radius * math.cos((angle - 2.0*math.pi*k) / 3.0)
            cand.append(y - A/3.0)
    bounded = [max(-1.0, min(1.0, x)) for x in cand if math.isfinite(x) and -1.0-1e-8 <= x <= 1.0+1e-8]
    if not bounded:
        return None
    return min(bounded, key=lambda x: abs(math.degrees(math.asin(max(-1.0, min(1.0, x))))))

def compute_phi_m(A0, B1, C1, phi_prime_deg, lambda_value):
    phi = math.radians(phi_prime_deg)
    tan_phi = math.tan(phi)
    s = 2.0 * int(lambda_value) - 1.0
    if abs(B1) <= 1e-20 or not math.isfinite(B1):
        raise ValueError(f"Invalid B1: {B1}")
    e1 = (1.0 - A0) / B1
    e2 = C1 / B1
    tan2 = tan_phi ** 2
    a0 = s * (1.0 + e2 ** 2 * tan2)
    b0 = 1.0 - (2.0 * e1 * e2 + e2 ** 2) * tan2
    c0 = s * (e1 ** 2 + 2.0 * e1 * e2) * tan2
    d0 = -(e1 ** 2) * tan2
    if abs(a0) <= 1e-20:
        raise ValueError("Degenerate cubic: a0=0")
    D0 = b0*b0 - 3.0*a0*c0
    D1 = 2.0*b0**3 - 9.0*a0*b0*c0 + 27.0*(a0**2)*d0
    sqrt_term = cmath.sqrt(complex(D1*D1 - 4.0*(D0**3), 0.0))
    C0 = (0.5 * (complex(D1, 0.0) - sqrt_term)) ** (1.0/3.0)
    if abs(C0) <= 1e-30:
        C0 = (0.5 * (complex(D1, 0.0) + sqrt_term)) ** (1.0/3.0)
    if abs(C0) <= 1e-30:
        x_real = _select_stable_root(a0, b0, c0, d0)
        if x_real is None:
            raise ValueError("Invalid cubic solution")
    else:
        zeta = complex(-0.5, math.sqrt(3.0)/2.0)
        zlam = zeta ** int(lambda_value)
        x = -(b0 + D0/(C0*zlam) + C0*zlam) / (3.0*a0)
        x_real = max(-1.0, min(1.0, float(x.real)))
    phi_m_deg = math.degrees(math.asin(x_real))
    if abs(phi_m_deg) > 0.95 * 90.0:
        x_alt = _select_stable_root(a0, b0, c0, d0)
        if x_alt is not None:
            x_real = x_alt
            phi_m_deg = math.degrees(math.asin(x_real))
    return {"phi_m_deg": phi_m_deg, "e1": e1, "e2": e2, "a0": a0, "b0": b0, "c0": c0, "d0": d0, "D0": D0, "D1": D1, "C0": C0}

def compute_c_m(c_prime, phi_m_deg, phi_prime_deg):
    tan_phi_p = math.tan(math.radians(phi_prime_deg))
    if abs(tan_phi_p) <= 1e-20:
        return c_prime
    return c_prime * math.tan(math.radians(phi_m_deg)) / tan_phi_p

def compute_K_XE(phi_m_deg, c_m, sigma_v, u, k_v, lambda_value):
    phi_m = math.radians(phi_m_deg)
    s = 2.0 * int(lambda_value) - 1.0
    denom = (1.0 - k_v) * sigma_v - u
    _safe_positive("(1-k_v)sigma_v-u", denom)
    return ((1.0 - s*math.sin(phi_m)) / (1.0 + s*math.sin(phi_m))
            - s * (2.0*c_m/denom) * math.tan(math.pi/4.0 - s*phi_m/2.0))

def solve_active_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2):
    sd = _regularize_side_data(side_data)
    lam = 1
    A0, B1 = compute_A0_B1_active(sd.phi_prime_deg, sd.c_prime, xi, seismic_data.theta_eq_deg, seismic_data.a_v, sigma_v, u)
    C1 = compute_C1(A0, sd.c_prime, sd.phi_prime_deg, seismic_data.a_v, sigma_v, u)
    phi_m = compute_phi_m(A0, B1, C1, sd.phi_prime_deg, lam)
    c_m = compute_c_m(sd.c_prime, phi_m["phi_m_deg"], sd.phi_prime_deg)
    K_XE = compute_K_XE(phi_m["phi_m_deg"], c_m, sigma_v, u, seismic_data.k_v, lam)
    return {"lambda_value": lam, "A0": A0, "B1": B1, "C1": C1, "phi_m": phi_m, "c_m": c_m, "K_XE": K_XE}

def solve_passive_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2):
    sd = _regularize_side_data(side_data)
    def solve_lam(lam):
        A0, B1 = compute_A0_B1_passive(sd.phi_prime_deg, sd.c_prime, xi, xi1, xi2, seismic_data.theta_eq_deg, seismic_data.a_v, sigma_v, u)
        C1 = compute_C1(A0, sd.c_prime, sd.phi_prime_deg, seismic_data.a_v, sigma_v, u)
        phi_m = compute_phi_m(A0, B1, C1, sd.phi_prime_deg, lam)
        c_m = compute_c_m(sd.c_prime, phi_m["phi_m_deg"], sd.phi_prime_deg)
        K_XE = compute_K_XE(phi_m["phi_m_deg"], c_m, sigma_v, u, seismic_data.k_v, lam)
        return {"lambda_value": lam, "A0": A0, "B1": B1, "C1": C1, "phi_m": phi_m, "c_m": c_m, "K_XE": K_XE}
    trial = solve_lam(0)
    return trial if trial["K_XE"] >= 1.0 else solve_lam(1)

def reference_K_OE(qtype, sigma_v, u, side_data, seismic_data):
    xi, xi1, xi2 = xi_parameters(1.0)
    if qtype == "active":
        return solve_active_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2)["K_XE"]
    return solve_passive_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2)["K_XE"]

def reference_K_limit(qtype, sigma_v, u, side_data, seismic_data):
    xi, xi1, xi2 = xi_parameters(M_FULL)
    if qtype == "active":
        return solve_active_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2)["K_XE"]
    return solve_passive_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2)["K_XE"]

def delta_K(qtype, K_OE, K_limit):
    return (K_OE - K_limit) if qtype == "active" else (K_limit - K_OE)

def slope_correction_factor(K_XE, K_AE, K_PE):
    denom = K_PE - K_AE
    if abs(denom) <= 1e-20:
        return 1.0
    r = max(0.0, min(1.0, (K_XE - K_AE) / denom))
    return 1.0 + 1.5 * (3.0*r*r - 2.0*r*r*r)

def apply_slope_correction(quadrant, K_XE, K_AE, K_PE, beta_deg, sigma_v, u):
    sigma_v_eff = sigma_v - u
    _safe_positive("sigma'_v", sigma_v_eff)
    fK = slope_correction_factor(K_XE, K_AE, K_PE)
    sigma_h_eff = sigma_v_eff * (K_XE + fK * math.tan(math.radians(beta_deg)))
    return {"fK": fK, "sigma_v_eff": sigma_v_eff, "sigma_h_eff_corrected": sigma_h_eff, "sigma_h_corrected": sigma_h_eff + u}

def final_horizontal_pressure(qtype, sigma_h_value):
    # Cohesion can mathematically produce tensile/negative horizontal stresses.
    # Soil-wall contact cannot transfer tensile pressure in this model, so they are ignored.
    return max(0.0, float(sigma_h_value))

# -------- Backward-compatible API used by the original embedded program --------
def mobilized_friction_angle_geo(side, gamma, z, av, u, c_prime, phi_prime_deg, a_H, pore_pressure=False,
                                 E=None, nu=None, H=None, DeltaK=None, delta_x=None, m=None,
                                 use_A0a_B1a=False, use_A0p_B1p=False):
    sigma_v = float(gamma) * float(z)
    theta_eq_deg = math.degrees(math.atan2(float(a_H), 1.0 - float(av)))
    sd = SideData(c_prime=c_prime, phi_prime_deg=phi_prime_deg, E_s=E or 20000.0, nu=nu or 0.3)
    seis = SeismicData(a_v=av, k_v=av, theta_eq_deg=theta_eq_deg)
    if m is None:
        if E is None or nu is None or H is None or DeltaK is None or delta_x is None:
            raise ValueError("m is required, or provide E, nu, H, DeltaK, and delta_x.")
        dxM = delta_x_M(H, E, nu, DeltaK, av, sigma_v, u)
        m = mobilization_m(abs(delta_x), dxM, z, H)
    xi, xi1, xi2 = xi_parameters(m)
    force_passive = bool(use_A0p_B1p)
    force_active = bool(use_A0a_B1a)
    if force_passive:
        state = solve_passive_state(sigma_v, u, sd, seis, xi, xi1, xi2)
        param_type = "A0p/B1p"
    elif force_active:
        state = solve_active_state(sigma_v, u, sd, seis, xi, xi1, xi2)
        param_type = "A0a/B1a"
    elif str(side).lower() == "passive":
        state = solve_passive_state(sigma_v, u, sd, seis, xi, xi1, xi2)
        param_type = "A0p/B1p"
    else:
        state = solve_active_state(sigma_v, u, sd, seis, xi, xi1, xi2)
        param_type = "A0a/B1a"
    dxM = None
    if E is not None and nu is not None and H is not None and DeltaK is not None:
        dxM = delta_x_M(H, E, nu, DeltaK, av, sigma_v, u)
    phi_m = state["phi_m"]
    return {"phi_m_deg": phi_m["phi_m_deg"], "lambda": state["lambda_value"], "A0": state["A0"], "B1": state["B1"],
            "A0a": state["A0"] if param_type == "A0a/B1a" else float('nan'),
            "B1a": state["B1"] if param_type == "A0a/B1a" else float('nan'),
            "A0p": state["A0"] if param_type == "A0p/B1p" else float('nan'),
            "B1p": state["B1"] if param_type == "A0p/B1p" else float('nan'),
            "param_type": param_type, "theta_eq_deg": theta_eq_deg, "sigma_v": sigma_v, "m": m, "xi": xi, "xi1": xi1, "xi2": xi2,
            "delta_x_max": dxM, "delta_chi_M": dxM, "z_over_H": (float(z)/float(H)) if H else None,
            **{k: phi_m[k] for k in ("e1","e2","a0","b0","c0","d0","D0","D1","C0")}}

def _compute_KXE_at_m(side, gamma, z, av, u, c_prime, phi_prime_deg, a_H, pore_pressure,
                      E, nu, H, DeltaK, m_value, use_A0a_B1a=False, use_A0p_B1p=False):
    res = mobilized_friction_angle_geo(side, gamma, z, av, u, c_prime, phi_prime_deg, a_H, pore_pressure,
                                       E=None, nu=None, H=None, DeltaK=None, delta_x=None, m=m_value,
                                       use_A0a_B1a=use_A0a_B1a, use_A0p_B1p=use_A0p_B1p)
    phi_m_rad = math.radians(res["phi_m_deg"])
    c_m = compute_c_m(c_prime, res["phi_m_deg"], phi_prime_deg)
    K_XE = compute_K_XE(res["phi_m_deg"], c_m, res["sigma_v"], u, av, int(res["lambda"]))
    sigma_XE = K_XE * (1.0 - av) * (res["sigma_v"] - u) + u
    return K_XE, sigma_XE, res

def compute_deltaK(side, gamma, z, av, u, c_prime, phi_prime_deg, a_H, pore_pressure,
                   E, nu, H, DeltaK, m_unused=None, use_A0a_B1a=False, use_A0p_B1p=False):
    K_OE, _, _ = _compute_KXE_at_m(side, gamma, z, av, u, c_prime, phi_prime_deg, a_H, pore_pressure,
                                   None, None, None, None, 1.0, use_A0a_B1a, use_A0p_B1p)
    K_M, _, _ = _compute_KXE_at_m(side, gamma, z, av, u, c_prime, phi_prime_deg, a_H, pore_pressure,
                                  None, None, None, None, M_FULL, use_A0a_B1a, use_A0p_B1p)
    dK = (K_OE - K_M) if str(side).lower() == "active" else (K_M - K_OE)
    return abs(dK), K_OE, K_M, None
