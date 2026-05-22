# -*- coding: utf-8 -*-
"""
CUT Embedded Wall — common solver data/helpers v2.6

Clean solver-side module. No GUI code.

Implemented now:
    Fixed base (only bending)
    Fixed base (differential equation)

Concept:
    - Soil pressures are computed through the external CUT K-engine.
    - Wall deflection is computed from elastic cantilever-beam theory.
    - No Winkler springs are used.
    - The fixed base is at z = H_R; the free top is at z = 0.

Pending registered modes:
    - No bending
    - General case
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Any
import importlib.util
import math
import os
import sys

SolverMode = Literal["fixed_base_only_bending", "fixed_base_differential_equation", "base_spring_differential_equation", "no_bending", "general_case", "general_case_variational_beam"]
M_FULL = 1.0e9
C_PRIME_MIN = 0.001
PHI_PRIME_MIN_DEG = 1.0e-6


@dataclass
class SoilLayer:
    code: str = "S1"
    thickness: float = 1.0
    c_prime: float = 0.0
    phi_prime_deg: float = 30.0
    gamma: float = 18.0
    gamma_sat: float = 20.0
    E_s: float = 20000.0
    nu: float = 0.30


@dataclass
class GeometryInput:
    H_R: float = 10.0
    H_L: float = 6.0
    z_p: float = 4.0


@dataclass
class SideInput:
    beta_deg: float = 0.0
    q: float = 0.0
    z_w: float = 1.0e30


@dataclass
class SeismicInput:
    k_h: float = 0.0
    k_v: float = 0.0


@dataclass
class MovementInput:
    dx_trans: float = 0.0
    theta_rot_deg: float = 0.0
    z_pivot: float = 4.0


@dataclass
class WallStiffnessInput:
    stiffness_type: str = "EI"
    EI: float = 1.5e6
    E: float = 1.0e6
    I_or_t: float = 1.5

    def effective_EI(self) -> float:
        if self.stiffness_type == "EI":
            return float(self.EI)
        if self.stiffness_type == "E & I":
            return float(self.E) * float(self.I_or_t)
        if self.stiffness_type == "E & t":
            t = float(self.I_or_t)
            return float(self.E) * t**3 / 12.0
        return float(self.EI)


@dataclass
class SolverControls:
    dz: float = 0.05
    n_points: int = 401
    max_iterations: int = 100
    tolerance: float = 1.0e-8
    integration_method: str = "Gauss"
    no_bending_mode: str = "Manual"
    rigid_optimization_solver: str = "Fast equilibrium only"
    equilibrium_force_tol: float = 0.01
    equilibrium_moment_tol: float = 0.01
    work_band_tol: float = 0.05
    energy_balance_tol: float = 0.10
    general_case_bending_schemes: int = 10
    general_case_theta_refine_passes: int = 5
    general_case_theta_points: int = 41
    general_case_zp_points: int = 17
    general_case_pivot_margin_frac: float = 0.02
    general_case_parallel: bool = True
    general_case_max_workers: int = 0
    variational_base_condition: str = "Free-like"
    variational_base_spring_factor: float = 1.0e-4
    variational_spring_release_factor: float = 0.80


@dataclass
class ReinforcementSupport:
    type: str = "support"
    code: str = "S1"
    z: float = 0.0
    theta_deg: float = 0.0
    k: float = 0.0
    cap: float = 0.0
    prestress: float = 0.0
    L: float = 0.0


@dataclass
class ModelInput:
    geometry: GeometryInput
    left: SideInput
    right: SideInput
    seismic: SeismicInput
    movement: MovementInput
    wall: WallStiffnessInput
    controls: SolverControls
    gamma_w: float = 9.81
    left_layers: list[SoilLayer] = field(default_factory=list)
    right_layers: list[SoilLayer] = field(default_factory=list)
    reinforcement_supports: list[dict[str, Any]] = field(default_factory=list)
    solver_mode: SolverMode = "general_case"


@dataclass
class SolverResult:
    solver_mode: SolverMode
    status: str
    message: str
    z: list[float] = field(default_factory=list)

    p_left: list[float] = field(default_factory=list)
    p_right: list[float] = field(default_factory=list)
    sigma_left_eff: list[float] = field(default_factory=list)
    sigma_right_eff: list[float] = field(default_factory=list)
    u_left: list[float] = field(default_factory=list)
    u_right: list[float] = field(default_factory=list)
    sigma_left_OE: list[float] = field(default_factory=list)
    sigma_left_AE: list[float] = field(default_factory=list)
    sigma_left_PE: list[float] = field(default_factory=list)
    sigma_right_OE: list[float] = field(default_factory=list)
    sigma_right_AE: list[float] = field(default_factory=list)
    sigma_right_PE: list[float] = field(default_factory=list)

    net_pressure: list[float] = field(default_factory=list)
    shear: list[float] = field(default_factory=list)
    moment: list[float] = field(default_factory=list)
    deflection: list[float] = field(default_factory=list)
    rotation: list[float] = field(default_factory=list)
    K_left: list[float] = field(default_factory=list)
    K_right: list[float] = field(default_factory=list)
    m_left: list[float] = field(default_factory=list)
    m_right: list[float] = field(default_factory=list)
    dxmax_left_A: list[float] = field(default_factory=list)
    dxmax_left_P: list[float] = field(default_factory=list)
    dxmax_right_A: list[float] = field(default_factory=list)
    dxmax_right_P: list[float] = field(default_factory=list)
    deflection_compare: list[float] = field(default_factory=list)
    deflection_compare_label: str = ""

    convergence_history: list[dict[str, float]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


_ENGINE_CACHE = None


def load_cut_engine(engine_filename: str = "CUT_Embedded_Wall_ENGINE_v1_0.py"):
    """Load the external CUT constitutive K-engine from this folder."""
    global _ENGINE_CACHE
    if _ENGINE_CACHE is not None:
        return _ENGINE_CACHE
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, engine_filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing CUT constitutive engine: {path}\n"
            "Place CUT_Embedded_Wall_ENGINE_v1_0.py in the same folder."
        )
    spec = importlib.util.spec_from_file_location("cut_embedded_wall_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load engine module from: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _ENGINE_CACHE = mod
    return mod


def safe_profile_depths(H: float, n_points: int) -> list[float]:
    """Avoid exact z=0 singular states while retaining the visual top point very closely."""
    H = max(float(H), 1.0e-9)
    n = max(3, int(n_points))
    z_eps = 1.0e-6 * max(1.0, H)
    return [z_eps + (H - z_eps) * i / (n - 1) for i in range(n)]


def layer_height(layers: list[SoilLayer]) -> float:
    return sum(max(0.0, float(layer.thickness)) for layer in layers)


def _regular_layer(layer: SoilLayer) -> SoilLayer:
    return SoilLayer(
        code=layer.code,
        thickness=max(0.0, float(layer.thickness)),
        c_prime=max(float(layer.c_prime), C_PRIME_MIN),
        phi_prime_deg=max(float(layer.phi_prime_deg), PHI_PRIME_MIN_DEG),
        gamma=float(layer.gamma),
        gamma_sat=float(layer.gamma_sat),
        E_s=max(float(layer.E_s), 1.0e-12),
        nu=float(layer.nu),
    )


def _regular_layers(layers: list[SoilLayer]) -> list[SoilLayer]:
    out = [_regular_layer(layer) for layer in layers if float(layer.thickness) > 0.0]
    if not out:
        out = [SoilLayer(thickness=1.0, c_prime=C_PRIME_MIN, phi_prime_deg=30.0, gamma=18.0, gamma_sat=20.0)]
    return out


def _layer_at_local_depth(layers: list[SoilLayer], z_local: float) -> SoilLayer:
    z = max(0.0, float(z_local))
    acc = 0.0
    regs = _regular_layers(layers)
    for layer in regs:
        acc_next = acc + layer.thickness
        if z <= acc_next + 1.0e-12:
            return layer
        acc = acc_next
    return regs[-1]


def _sigma_v_total(layers: list[SoilLayer], z_local: float, z_w_local: float, q: float) -> float:
    """Total vertical stress from surcharge plus layered total unit weights.

    The declared layer thicknesses are normally expected to span the full side
    height.  Staged-excavation animation temporarily changes the excavation
    side height (H_L) without editing the user table.  In that case, depths
    below the declared layer stack must not be held constant: continue using
    the last layer properties down to the current wall depth.
    """
    z = max(0.0, float(z_local))
    sigma = max(0.0, float(q))
    acc = 0.0
    regs = _regular_layers(layers)
    zw = float(z_w_local)
    for layer in regs:
        if acc >= z:
            break
        seg_top = acc
        seg_bot = min(z, acc + layer.thickness)
        if seg_bot > seg_top:
            above_bot = min(seg_bot, zw)
            if above_bot > seg_top:
                sigma += (above_bot - seg_top) * layer.gamma
            if seg_bot > max(seg_top, zw):
                sigma += (seg_bot - max(seg_top, zw)) * layer.gamma_sat
        acc += layer.thickness

    # Staged-animation guard: if z is deeper than the declared layer stack,
    # extend the last layer rather than repeating a constant stress value.
    if z > acc and regs:
        layer = regs[-1]
        seg_top = acc
        seg_bot = z
        above_bot = min(seg_bot, zw)
        if above_bot > seg_top:
            sigma += (above_bot - seg_top) * layer.gamma
        if seg_bot > max(seg_top, zw):
            sigma += (seg_bot - max(seg_top, zw)) * layer.gamma_sat
    return sigma


def _pore_pressure(z_local: float, z_w_local: float, gamma_w: float) -> float:
    return max(0.0, float(gamma_w) * (float(z_local) - float(z_w_local)))


def _theta_eq_deg(k_h: float, k_v: float) -> float:
    return math.degrees(math.atan2(max(0.0, float(k_h)), 1.0 - float(k_v)))


def _side_geometry(model: ModelInput, side: Literal["left", "right"], z_global: float):
    H_R = float(model.geometry.H_R)
    H_L = float(model.geometry.H_L)
    z_left_surface = H_R - H_L
    if side == "right":
        return {
            "exists": 0.0 <= z_global <= H_R + 1.0e-12,
            "z_local": max(0.0, float(z_global)),
            "H_side": H_R,
            "surface_global": 0.0,
            "layers": model.right_layers,
            "side_input": model.right,
        }
    z_local = float(z_global) - z_left_surface
    return {
        "exists": z_local >= -1.0e-12 and z_local <= H_L + 1.0e-12,
        "z_local": max(0.0, z_local),
        "H_side": H_L,
        "surface_global": z_left_surface,
        "layers": model.left_layers,
        "side_input": model.left,
    }


def _qtype_from_deflection(side: Literal["left", "right"], w_left_positive: float) -> Literal["active", "passive"]:
    # Deflection sign convention in this solver:
    #   w > 0 means wall displacement toward the left.
    # Right soil: w > 0 means wall moves away from right soil -> active.
    # Left soil:  w > 0 means wall moves toward left soil -> passive.
    if side == "right":
        return "active" if w_left_positive >= 0.0 else "passive"
    return "passive" if w_left_positive >= 0.0 else "active"


def _engine_side_data(engine, side_input: SideInput, layer: SoilLayer, z_w_local: float):
    return engine.SideData(
        beta_deg=float(side_input.beta_deg),
        q_real=max(0.0, float(side_input.q)),
        z_w=float(z_w_local),
        gamma=float(layer.gamma),
        gamma_sat=float(layer.gamma_sat),
        c_prime=max(float(layer.c_prime), C_PRIME_MIN),
        phi_prime_deg=max(float(layer.phi_prime_deg), PHI_PRIME_MIN_DEG),
        E_s=max(float(layer.E_s), 1.0e-12),
        nu=float(layer.nu),
        layers=[],
    )


def _solve_state_for_qtype(engine, qtype: Literal["active", "passive"], sigma_v: float, u: float,
                           side_data, seismic_data, m: float):
    xi, xi1, xi2 = engine.xi_parameters(m)
    if qtype == "active":
        return engine.solve_active_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2)
    return engine.solve_passive_state(sigma_v, u, side_data, seismic_data, xi, xi1, xi2)


def _horizontal_stress_for_qtype(engine, qtype: Literal["active", "passive"], sigma_v: float, u: float,
                                 side_data, seismic_data, beta_deg: float, m: float):
    K_AE = engine.reference_K_limit("active", sigma_v, u, side_data, seismic_data)
    K_PE = engine.reference_K_limit("passive", sigma_v, u, side_data, seismic_data)
    state = _solve_state_for_qtype(engine, qtype, sigma_v, u, side_data, seismic_data, m)
    slope = engine.apply_slope_correction(
        quadrant="RA" if qtype == "active" else "RP",
        K_XE=state["K_XE"],
        K_AE=K_AE,
        K_PE=K_PE,
        beta_deg=beta_deg,
        sigma_v=sigma_v,
        u=u,
    )
    sigma_total = slope["sigma_h_corrected"]
    return engine.final_horizontal_pressure(qtype, sigma_total), state["K_XE"], slope, K_AE, K_PE


def _side_pressure_point(model: ModelInput, engine, seismic_data, side: Literal["left", "right"],
                         z_global: float, w_left_positive: float) -> dict[str, float]:
    geom = _side_geometry(model, side, z_global)
    if not geom["exists"]:
        return {k: 0.0 for k in ("p", "sigma_OE", "sigma_AE", "sigma_PE", "K", "m", "dxM", "dxmax_A", "dxmax_P", "sigma_v", "sigma_eff", "u")}

    side_input: SideInput = geom["side_input"]
    layers = _regular_layers(geom["layers"])
    z_local = geom["z_local"]
    H_side = max(float(geom["H_side"]), 1.0e-9)
    z_w_local = max(0.0, float(side_input.z_w) - float(geom["surface_global"]))
    layer = _layer_at_local_depth(layers, z_local)
    sigma_v = _sigma_v_total(layers, z_local, z_w_local, side_input.q)
    u = _pore_pressure(z_local, z_w_local, model.gamma_w)
    sigma_eff = sigma_v - u
    if sigma_eff <= 1.0e-12:
        return {k: 0.0 for k in ("p", "sigma_OE", "sigma_AE", "sigma_PE", "K", "m", "dxM", "dxmax_A", "dxmax_P", "sigma_v", "sigma_eff", "u")} | {"sigma_v": sigma_v, "sigma_eff": max(0.0, sigma_v-u), "u": u}

    side_data = _engine_side_data(engine, side_input, layer, z_w_local)
    beta = float(side_input.beta_deg)

    # Reference limits for diagrams.
    p_OE_default_qtype = "active" if side == "right" else "passive"
    sigma_OE, _, _, _, _ = _horizontal_stress_for_qtype(
        engine, p_OE_default_qtype, sigma_v, u, side_data, seismic_data, beta, 1.0
    )
    sigma_AE, _, _, _, _ = _horizontal_stress_for_qtype(
        engine, "active", sigma_v, u, side_data, seismic_data, beta, M_FULL
    )
    sigma_PE, _, _, _, _ = _horizontal_stress_for_qtype(
        engine, "passive", sigma_v, u, side_data, seismic_data, beta, M_FULL
    )

    # Displacement limits for full active/passive mobilization at this point.
    # These are used both by the CUT mobilization equation and by the deflection chart.
    K_OE_active = engine.reference_K_OE("active", sigma_v, u, side_data, seismic_data)
    K_OE_passive = engine.reference_K_OE("passive", sigma_v, u, side_data, seismic_data)
    K_AE_lim = engine.reference_K_limit("active", sigma_v, u, side_data, seismic_data)
    K_PE_lim = engine.reference_K_limit("passive", sigma_v, u, side_data, seismic_data)
    DeltaK_A = engine.delta_K("active", K_OE_active, K_AE_lim)
    DeltaK_P = engine.delta_K("passive", K_OE_passive, K_PE_lim)

    try:
        dxmax_A = engine.delta_x_max(
            z_local=max(z_local, 1.0e-9),
            H_quad=H_side,
            E_s=layer.E_s,
            nu=layer.nu,
            DeltaK=DeltaK_A,
            a_v=float(model.seismic.k_v),
            sigma_v=sigma_v,
            u=u,
        )
    except Exception:
        dxmax_A = 0.0
    try:
        dxmax_P = engine.delta_x_max(
            z_local=max(z_local, 1.0e-9),
            H_quad=H_side,
            E_s=layer.E_s,
            nu=layer.nu,
            DeltaK=DeltaK_P,
            a_v=float(model.seismic.k_v),
            sigma_v=sigma_v,
            u=u,
        )
    except Exception:
        dxmax_P = 0.0

    qtype = _qtype_from_deflection(side, w_left_positive)
    if qtype == "active":
        dxM = dxmax_A
    else:
        dxM = dxmax_P

    if abs(w_left_positive) <= 1.0e-12:
        m = 1.0
    else:
        m = engine.mobilization_m(abs(w_left_positive), dxM if dxM else 0.0, max(z_local, 1.0e-9), H_side)

    p, K, slope, _, _ = _horizontal_stress_for_qtype(engine, qtype, sigma_v, u, side_data, seismic_data, beta, m)
    return {
        "p": max(0.0, float(p)),
        "sigma_OE": max(0.0, float(sigma_OE)),
        "sigma_AE": max(0.0, float(sigma_AE)),
        "sigma_PE": max(0.0, float(sigma_PE)),
        "K": float(K),
        "m": float(m),
        "dxM": abs(float(dxM or 0.0)),
        "dxmax_A": abs(float(dxmax_A or 0.0)),
        "dxmax_P": abs(float(dxmax_P or 0.0)),
        "sigma_v": float(sigma_v),
        "sigma_eff": max(0.0, float(sigma_v - u)),
        "u": float(u),
    }


def _gauss_points_3(a: float, b: float):
    mid = 0.5 * (a + b)
    half = 0.5 * (b - a)
    r = math.sqrt(3.0 / 5.0)
    return [
        (mid - r * half, 5.0 / 9.0 * half),
        (mid, 8.0 / 9.0 * half),
        (mid + r * half, 5.0 / 9.0 * half),
    ]


def _point_load_influence_cantilever(x: float, xi: float, EI: float) -> float:
    """Deflection at x from a unit point load at xi, both measured from the fixed base."""
    if x <= xi:
        return x * x * (3.0 * xi - x) / (6.0 * EI)
    return xi * xi * (3.0 * x - xi) / (6.0 * EI)


def _beam_deflection_fixed_base(
    z_top_down: list[float],
    q_top_down: list[float],
    H: float,
    EI: float,
    integration_method: str = "Gauss",
) -> list[float]:
    """Elastic cantilever deflection, fixed at base z=H, no Winkler springs.

    Positive q gives positive deflection. Internally x = H-z is measured upward
    from the fixed base. Two integration modes are available:

    * Gauss: 3-point Gauss integration of q(xi) times the exact cantilever
      point-load influence function. The interval containing the evaluation
      point is split at xi=x, so the branch change in the influence function is
      handled exactly for a piecewise-linear q.
    * Lumped: endpoint load lumping of each trapezoidal pressure strip. This is
      useful for comparison with coarse nodal-load FE idealizations.
    """
    n = len(z_top_down)
    if n == 0:
        return []
    EI = max(float(EI), 1.0e-30)
    H = float(H)
    method = str(integration_method or "Gauss").strip().lower()
    x_desc = [H - float(z) for z in z_top_down]
    q_desc = [float(q) for q in q_top_down]
    x = list(reversed(x_desc))
    q = list(reversed(q_desc))

    if method.startswith("lump"):
        w_x = []
        for xt in x:
            wt = 0.0
            for j in range(len(x) - 1):
                x0, x1 = x[j], x[j + 1]
                dx = x1 - x0
                if dx <= 0.0:
                    continue
                for x_load, P in ((x0, q[j] * dx / 2.0), (x1, q[j + 1] * dx / 2.0)):
                    if abs(P) > 0.0:
                        wt += P * _point_load_influence_cantilever(xt, x_load, EI)
            w_x.append(wt)
        return list(reversed(w_x))

    def integrate_piece(xt: float, x0: float, x1: float, q0: float, q1: float) -> float:
        if x1 <= x0:
            return 0.0
        total = 0.0
        for xg, wg in _gauss_points_3(x0, x1):
            t = (xg - x0) / (x1 - x0)
            qg = q0 + t * (q1 - q0)
            total += qg * _point_load_influence_cantilever(xt, xg, EI) * wg
        return total

    w_x = []
    for xt in x:
        wt = 0.0
        for j in range(len(x) - 1):
            x0, x1 = x[j], x[j + 1]
            if x1 <= x0:
                continue
            q0, q1 = q[j], q[j + 1]
            if x0 < xt < x1:
                tq = (xt - x0) / (x1 - x0)
                qt = q0 + tq * (q1 - q0)
                wt += integrate_piece(xt, x0, xt, q0, qt)
                wt += integrate_piece(xt, xt, x1, qt, q1)
            else:
                wt += integrate_piece(xt, x0, x1, q0, q1)
        w_x.append(wt)
    return list(reversed(w_x))




def _solve_linear_system(A: list[list[float]], b: list[float]) -> list[float]:
    # Small dense Gaussian elimination solver; avoids a NumPy dependency in the solver module.
    n = len(b)
    M = [list(map(float, row)) + [float(bi)] for row, bi in zip(A, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) <= 1.0e-30:
            raise ValueError('Singular finite-difference beam system.')
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]
        piv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= piv
        for r in range(n):
            if r == col:
                continue
            fac = M[r][col]
            if fac == 0.0:
                continue
            for j in range(col, n + 1):
                M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]


def _beam_deflection_fixed_base_differential(z_top_down: list[float], q_top_down: list[float], H: float, EI: float) -> list[float]:
    # Elastic cantilever deflection from EI*d4w/dx4 = q.
    # Coordinate x is measured upward from the fixed base:
    # x=0 at z=H, x=H at z=0.
    # Boundary conditions: fixed base w=0,w'=0; free top w''=0,w'''=0.
    n = len(z_top_down)
    if n == 0:
        return []
    if n < 6:
        return _beam_deflection_fixed_base(z_top_down, q_top_down, H, EI)
    EI = max(float(EI), 1.0e-30)
    H = max(float(H), 1.0e-12)

    q_x = list(reversed([float(v) for v in q_top_down]))  # base -> top
    dx = H / (n - 1)
    A = [[0.0 for _ in range(n)] for __ in range(n)]
    b = [0.0 for _ in range(n)]

    # Fixed base at x=0.
    A[0][0] = 1.0
    A[1][0] = -3.0 / (2.0 * dx)
    A[1][1] = 4.0 / (2.0 * dx)
    A[1][2] = -1.0 / (2.0 * dx)

    # Interior fourth derivative.
    for i in range(2, n - 2):
        A[i][i - 2] = 1.0 / dx**4
        A[i][i - 1] = -4.0 / dx**4
        A[i][i] = 6.0 / dx**4
        A[i][i + 1] = -4.0 / dx**4
        A[i][i + 2] = 1.0 / dx**4
        b[i] = q_x[i] / EI

    # Free top at x=H: moment and shear are zero.
    A[n - 2][n - 3] = 1.0 / dx**2
    A[n - 2][n - 2] = -2.0 / dx**2
    A[n - 2][n - 1] = 1.0 / dx**2

    A[n - 1][n - 4] = -1.0 / dx**3
    A[n - 1][n - 3] = 3.0 / dx**3
    A[n - 1][n - 2] = -3.0 / dx**3
    A[n - 1][n - 1] = 1.0 / dx**3

    w_x = _solve_linear_system(A, b)
    return list(reversed(w_x))


def _gradient(values: list[float], z: list[float]) -> list[float]:
    n = len(values)
    if n < 2:
        return [0.0 for _ in values]
    out = []
    for i in range(n):
        if i == 0:
            dz = z[1] - z[0]
            out.append((values[1] - values[0]) / dz if abs(dz) > 0 else 0.0)
        elif i == n - 1:
            dz = z[-1] - z[-2]
            out.append((values[-1] - values[-2]) / dz if abs(dz) > 0 else 0.0)
        else:
            dz = z[i + 1] - z[i - 1]
            out.append((values[i + 1] - values[i - 1]) / dz if abs(dz) > 0 else 0.0)
    return out


def _integrate_shear_moment(z: list[float], q: list[float]) -> tuple[list[float], list[float]]:
    n = len(z)
    V = [0.0 for _ in z]
    M = [0.0 for _ in z]
    for i in range(1, n):
        dz = z[i] - z[i - 1]
        V[i] = V[i - 1] + 0.5 * (q[i - 1] + q[i]) * dz
        M[i] = M[i - 1] + 0.5 * (V[i - 1] + V[i]) * dz
    return V, M


def _calculate_pressures_for_deflection(model: ModelInput, z: list[float], w: list[float], engine):
    seis = engine.SeismicData(
        a_v=float(model.seismic.k_v),
        k_v=float(model.seismic.k_v),
        theta_eq_deg=_theta_eq_deg(model.seismic.k_h, model.seismic.k_v),
    )
    p_left = []
    p_right = []
    sigma_left_eff = []
    sigma_right_eff = []
    u_left = []
    u_right = []
    sig_l_oe = []
    sig_l_ae = []
    sig_l_pe = []
    sig_r_oe = []
    sig_r_ae = []
    sig_r_pe = []
    K_left = []
    K_right = []
    m_left = []
    m_right = []
    dxmax_left_A = []
    dxmax_left_P = []
    dxmax_right_A = []
    dxmax_right_P = []
    for zi, wi in zip(z, w):
        r = _side_pressure_point(model, engine, seis, "right", zi, wi)
        l = _side_pressure_point(model, engine, seis, "left", zi, wi)
        p_right.append(r["p"])
        p_left.append(l["p"])
        sigma_right_eff.append(max(0.0, r["p"] - r.get("u", 0.0)))
        sigma_left_eff.append(max(0.0, l["p"] - l.get("u", 0.0)))
        u_right.append(r.get("u", 0.0))
        u_left.append(l.get("u", 0.0))
        sig_r_oe.append(r["sigma_OE"])
        sig_r_ae.append(r["sigma_AE"])
        sig_r_pe.append(r["sigma_PE"])
        sig_l_oe.append(l["sigma_OE"])
        sig_l_ae.append(l["sigma_AE"])
        sig_l_pe.append(l["sigma_PE"])
        K_right.append(r["K"])
        K_left.append(l["K"])
        m_right.append(r["m"])
        m_left.append(l["m"])
        dxmax_right_A.append(r.get("dxmax_A", 0.0))
        dxmax_right_P.append(r.get("dxmax_P", 0.0))
        dxmax_left_A.append(l.get("dxmax_A", 0.0))
        dxmax_left_P.append(l.get("dxmax_P", 0.0))
    net = [pr - pl for pr, pl in zip(p_right, p_left)]
    return {
        "p_left": p_left,
        "p_right": p_right,
        "sigma_left_eff": sigma_left_eff,
        "sigma_right_eff": sigma_right_eff,
        "u_left": u_left,
        "u_right": u_right,
        "sigma_left_OE": sig_l_oe,
        "sigma_left_AE": sig_l_ae,
        "sigma_left_PE": sig_l_pe,
        "sigma_right_OE": sig_r_oe,
        "sigma_right_AE": sig_r_ae,
        "sigma_right_PE": sig_r_pe,
        "K_left": K_left,
        "K_right": K_right,
        "m_left": m_left,
        "m_right": m_right,
        "dxmax_left_A": dxmax_left_A,
        "dxmax_left_P": dxmax_left_P,
        "dxmax_right_A": dxmax_right_A,
        "dxmax_right_P": dxmax_right_P,
        "net_pressure": net,
    }




def make_placeholder_result(model: ModelInput, mode: SolverMode, message: str) -> SolverResult:
    z = safe_profile_depths(model.geometry.H_R, model.controls.n_points)
    zeros = [0.0 for _ in z]
    return SolverResult(
        solver_mode=mode,
        status="pending",
        message=message,
        z=z,
        p_left=zeros.copy(),
        p_right=zeros.copy(),
        sigma_left_eff=zeros.copy(),
        sigma_right_eff=zeros.copy(),
        u_left=zeros.copy(),
        u_right=zeros.copy(),
        sigma_left_OE=zeros.copy(),
        sigma_left_AE=zeros.copy(),
        sigma_left_PE=zeros.copy(),
        sigma_right_OE=zeros.copy(),
        sigma_right_AE=zeros.copy(),
        sigma_right_PE=zeros.copy(),
        net_pressure=zeros.copy(),
        shear=zeros.copy(),
        moment=zeros.copy(),
        deflection=zeros.copy(),
        rotation=zeros.copy(),
        K_left=zeros.copy(),
        K_right=zeros.copy(),
        m_left=[1.0 for _ in z],
        m_right=[1.0 for _ in z],
        summary={
            "solver": mode,
            "note": message,
            "H_R": model.geometry.H_R,
            "H_L": model.geometry.H_L,
            "z_pivot": model.movement.z_pivot,
            "k_h": model.seismic.k_h,
            "k_v": model.seismic.k_v,
            "EI": model.wall.effective_EI(),
            "left layers": len(model.left_layers),
            "right layers": len(model.right_layers),
            "reinforcement supports": len(model.reinforcement_supports),
        },
    )




# Export helper functions used by individual solver modules, including private-prefixed helpers.
__all__ = [name for name in globals() if not name.startswith("__")]
