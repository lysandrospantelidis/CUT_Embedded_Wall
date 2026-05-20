# -*- coding: utf-8 -*-
"""No-bending rigid-wall solver. No GUI code.

Two modes are supported:

1. Manual
   Uses the rigid movement entered by the user:
       w(z) = dx_trans + tan(theta_rot) * (z_pivot - z)

2. ΣF=0 & ΣM=0
   Searches the rigid-body parameters dx_trans, theta_rot and z_pivot so that
   the mobilized CUT pressures satisfy approximate global equilibrium:
       ΣF = ∫ p_net dz ≈ 0
       ΣM = ∫ p_net (z_pivot - z) dz ≈ 0

No EI, no Winkler springs and no bending compatibility are used.  Shear and
moment are resultants of the final pressure field only.
"""
from __future__ import annotations
import math
from .common import *
from .reinforcement import apply_reinforcement_to_pressure_data, admissible_pivot_range, has_reinforcement


def _rigid_wall_deflection_from_params(z: list[float], dx: float, theta_deg: float, z_pivot: float) -> list[float]:
    ttheta = math.tan(math.radians(float(theta_deg)))
    zp = float(z_pivot)
    return [float(dx) + ttheta * (zp - float(zi)) for zi in z]


def _rigid_wall_deflection(model: ModelInput, z: list[float]) -> list[float]:
    return _rigid_wall_deflection_from_params(
        z,
        float(model.movement.dx_trans),
        float(model.movement.theta_rot_deg),
        float(model.movement.z_pivot),
    )


def _trapz(z: list[float], y: list[float]) -> float:
    if len(z) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(z)):
        dz = float(z[i]) - float(z[i - 1])
        total += 0.5 * (float(y[i - 1]) + float(y[i])) * dz
    return float(total)


def _force_moment_score(z: list[float], q: list[float], z_pivot: float) -> dict[str, float]:
    F = _trapz(z, q)
    arms = [float(z_pivot) - float(zi) for zi in z]
    M = _trapz(z, [qi * ai for qi, ai in zip(q, arms)])
    Fscale = max(_trapz(z, [abs(qi) for qi in q]), 1.0)
    Mscale = max(_trapz(z, [abs(qi * ai) for qi, ai in zip(q, arms)]), Fscale * max(float(z[-1] - z[0]), 1.0) * 0.05, 1.0)
    score = (F / Fscale) ** 2 + (M / Mscale) ** 2
    return {"F": F, "M": M, "Fscale": Fscale, "Mscale": Mscale, "score": score}


def _work_index(z: list[float], q: list[float], w: list[float]) -> float:
    """Legacy absolute net-work index used by the fast rigid solver."""
    return _trapz(z, [abs(float(qi) * float(wi)) for qi, wi in zip(q, w)])


def _rigid_energy_metrics(z: list[float], data: dict, w: list[float]) -> dict[str, float]:
    """Left/right virtual-work bookkeeping for a rigid wall.

    Sign convention: q_net = p_right - p_left, therefore
        W_right = ∫ p_right w dz
        W_left  = ∫ p_left  w dz
        W_net   = W_right - W_left = ∫ q_net w dz
    For a pure rigid wall there is no bending strain energy, so U_int = 0 and
    the variational residual is E_residual = W_net.
    """
    p_left = data.get("p_left", [])
    p_right = data.get("p_right", [])
    q = data.get("net_pressure", [])
    WL = _trapz(z, [float(pi) * float(wi) for pi, wi in zip(p_left, w)])
    WR = _trapz(z, [float(pi) * float(wi) for pi, wi in zip(p_right, w)])
    Wnet = WR - WL
    Wabs_sides = _trapz(z, [(abs(float(pr) * float(wi)) + abs(float(pl) * float(wi))) for pr, pl, wi in zip(p_right, p_left, w)])
    Wabs_net = _trapz(z, [abs(float(qi) * float(wi)) for qi, wi in zip(q, w)])
    Escale = max(abs(Wnet), abs(WR) + abs(WL), Wabs_sides, 1.0e-12)
    return {
        "W_left_signed": WL,
        "W_right_signed": WR,
        "W_net_signed": Wnet,
        "W_sides_abs": Wabs_sides,
        "W_net_abs": Wabs_net,
        "U_internal": 0.0,
        "energy_balance_residual": Wnet,
        "energy_balance_norm": abs(Wnet) / Escale,
    }


def _evaluate_candidate(model: ModelInput, engine, z: list[float], dx: float, theta_deg: float, z_pivot: float):
    w = _rigid_wall_deflection_from_params(z, dx, theta_deg, z_pivot)
    data = _calculate_pressures_for_deflection(model, z, w, engine)
    data = apply_reinforcement_to_pressure_data(data, z, w, model.reinforcement_supports)
    fm = _force_moment_score(z, data["net_pressure"], z_pivot)
    work = _work_index(z, data["net_pressure"], w)
    em = _rigid_energy_metrics(z, data, w)
    return fm | em | {"work_index": work, "w": w, "data": data, "dx": float(dx), "theta_deg": float(theta_deg), "z_pivot": float(z_pivot)}


def _linspace(a: float, b: float, n: int) -> list[float]:
    n = max(1, int(n))
    if n == 1 or abs(b - a) <= 1.0e-15:
        return [0.5 * (a + b)]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def _clip(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


def _select_transparent_equilibrium_candidate(candidates: list[dict], controls: SolverControls) -> tuple[dict, dict]:
    """Transparent selection for non-unique equilibrium/work valleys.

    User-visible tolerances control the process:
      1. equilibrium band: |ΣF|/Fscale <= tol_F and |ΣM|/Mscale <= tol_M,
      2. work band: W <= Wmin*(1+tol_W),
      3. kinematic regularization: smallest |theta|, then smallest |dx|, then pivot closest to mid-height.

    If no candidate satisfies the explicit equilibrium tolerances, the solver
    falls back to a near-best normalized residual band and reports this in the
    summary so the result is not presented as fully tolerance-admissible.
    """
    if not candidates:
        raise RuntimeError("No candidates available for equilibrium selection.")

    tol_F = max(0.0, float(getattr(controls, "equilibrium_force_tol", 0.01)))
    tol_M = max(0.0, float(getattr(controls, "equilibrium_moment_tol", 0.01)))
    tol_W = max(0.0, float(getattr(controls, "work_band_tol", 0.05)))

    def score(r):
        return float(r.get("score", 1.0e99))
    def work(r):
        return float(r.get("work_index", 1.0e99))
    def theta_abs(r):
        return abs(float(r.get("theta_deg", 0.0)))
    def dx_abs(r):
        return abs(float(r.get("dx", 0.0)))
    def F_ratio(r):
        return abs(float(r.get("F", 0.0))) / max(float(r.get("Fscale", 1.0)), 1.0e-30)
    def M_ratio(r):
        return abs(float(r.get("M", 0.0))) / max(float(r.get("Mscale", 1.0)), 1.0e-30)

    best_score = min(score(r) for r in candidates)
    explicit_band = [r for r in candidates if F_ratio(r) <= tol_F and M_ratio(r) <= tol_M]
    used_fallback = False
    if explicit_band:
        equilibrium_band = explicit_band
        score_limit = max(score(r) for r in equilibrium_band)
    else:
        # Fallback: near-minimum normalized residual band, reported clearly.
        used_fallback = True
        score_limit = max(best_score * 1.02, best_score + 1.0e-10)
        equilibrium_band = [r for r in candidates if score(r) <= score_limit]
        if not equilibrium_band:
            equilibrium_band = [min(candidates, key=score)]

    min_work = min(work(r) for r in equilibrium_band)
    work_limit = max(min_work * (1.0 + tol_W), min_work + 1.0e-12)
    work_band = [r for r in equilibrium_band if work(r) <= work_limit]
    if not work_band:
        work_band = equilibrium_band

    H = max(float(max((r.get("z_pivot", 0.0) for r in candidates), default=1.0)), 1.0)
    selected = min(work_band, key=lambda r: (theta_abs(r), dx_abs(r), abs(float(r.get("z_pivot", 0.0)) - 0.5 * H), score(r), work(r)))
    info = {
        "selection rule": "|ΣF|/scale<=tol_F and |ΣM|/scale<=tol_M -> min work band -> min |theta| -> min |dx|",
        "equilibrium force tolerance": tol_F,
        "equilibrium moment tolerance": tol_M,
        "work-band tolerance": tol_W,
        "selection used fallback residual band": bool(used_fallback),
        "selection best score": best_score,
        "selection score limit": score_limit,
        "selection equilibrium candidates": len(equilibrium_band),
        "selection explicit equilibrium candidates": len(explicit_band),
        "selection min work in equilibrium band": min_work,
        "selection work limit": work_limit,
        "selection work-band candidates": len(work_band),
        "selected |ΣF|/scale": F_ratio(selected),
        "selected |ΣM|/scale": M_ratio(selected),
    }
    return selected, info


def _select_energy_aware_candidate(candidates: list[dict], controls: SolverControls) -> tuple[dict, dict]:
    """Energy-aware rigid selection.

    This keeps equilibrium as the first admissibility test, then applies the
    rigid-wall variational condition W_net ≈ U_int = 0 before selecting the
    least side-work mechanism. It is intentionally optional because it adds an
    extra criterion and may select a different member of a near-equilibrium
    valley than the fast legacy-style equilibrium solver.
    """
    if not candidates:
        raise RuntimeError("No candidates available for energy-aware rigid selection.")
    tol_F = max(0.0, float(getattr(controls, "equilibrium_force_tol", 0.01)))
    tol_M = max(0.0, float(getattr(controls, "equilibrium_moment_tol", 0.01)))
    tol_E = max(0.0, float(getattr(controls, "energy_balance_tol", 0.10)))

    def score(r): return float(r.get("score", 1.0e99))
    def F_ratio(r): return abs(float(r.get("F", 0.0))) / max(float(r.get("Fscale", 1.0)), 1.0e-30)
    def M_ratio(r): return abs(float(r.get("M", 0.0))) / max(float(r.get("Mscale", 1.0)), 1.0e-30)
    def E_norm(r): return abs(float(r.get("energy_balance_norm", 1.0e99)))
    def action(r): return float(r.get("W_sides_abs", r.get("work_index", 1.0e99)))
    def theta_abs(r): return abs(float(r.get("theta_deg", 0.0)))
    def dx_abs(r): return abs(float(r.get("dx", 0.0)))

    best_score = min(score(r) for r in candidates)
    explicit_eq = [r for r in candidates if F_ratio(r) <= tol_F and M_ratio(r) <= tol_M]
    used_eq_fallback = False
    if explicit_eq:
        eq_band = explicit_eq
        score_limit = max(score(r) for r in eq_band)
    else:
        used_eq_fallback = True
        score_limit = max(best_score * 1.02, best_score + 1.0e-10)
        eq_band = [r for r in candidates if score(r) <= score_limit] or [min(candidates, key=score)]

    energy_band = [r for r in eq_band if E_norm(r) <= tol_E]
    used_energy_fallback = False
    if not energy_band:
        used_energy_fallback = True
        Emin = min(E_norm(r) for r in eq_band)
        Elim = max(Emin * 1.05, Emin + 1.0e-10)
        energy_band = [r for r in eq_band if E_norm(r) <= Elim] or [min(eq_band, key=E_norm)]
    else:
        Elim = tol_E

    selected = min(energy_band, key=lambda r: (action(r), E_norm(r), theta_abs(r), dx_abs(r), score(r)))
    info = {
        "rigid optimization solver": "Energy-aware variational",
        "rigid energy formula": "W_net = W_R - W_L ≈ U_int = 0",
        "selection rule": "equilibrium band -> energy band |W_net|≈0 -> minimum |W_left|+|W_right|",
        "energy balance tolerance": tol_E,
        "selection used fallback residual band": bool(used_eq_fallback),
        "selection used fallback energy band": bool(used_energy_fallback),
        "selection best score": best_score,
        "selection score limit": score_limit,
        "selection equilibrium candidates": len(eq_band),
        "selection explicit equilibrium candidates": len(explicit_eq),
        "selection energy candidates": len(energy_band),
        "selection energy limit": Elim,
        "selected |ΣF|/scale": F_ratio(selected),
        "selected |ΣM|/scale": M_ratio(selected),
        "selected |E|/scale": E_norm(selected),
    }
    return selected, info

def _optimize_rigid_movement(model: ModelInput, engine, H: float):
    """Coarse-to-fine search for dx, theta and z_pivot.

    The search is intentionally conservative and does not introduce extra GUI
    parameters.  Bounds are derived from the current manual inputs and wall
    height.  Final pressures are recalculated on the full user grid after the
    optimum is found on a lighter search grid.
    """
    n_opt = min(max(31, int(model.controls.n_points // 3)), 91)
    z_opt = safe_profile_depths(H, n_opt)

    dx0 = max(0.0, float(model.movement.dx_trans))
    th0 = max(0.0, float(model.movement.theta_rot_deg))
    zp0 = _clip(float(model.movement.z_pivot), 0.0, H)

    # Positive dx and positive theta follow the adopted wall-movement convention.
    dx_max = max(dx0 * 3.0, 0.02 * H, 0.05)
    dx_max = min(dx_max, 0.20 * H)  # avoid meaningless very large rigid translations
    th_max = max(th0 * 3.0, 5.0)
    th_max = min(th_max, 20.0)
    zp_min, zp_max, zp_reason = admissible_pivot_range(model.geometry.H_L, H, model.reinforcement_supports)

    best = None
    candidates = []
    n_eval = 0

    def register(dx, th, zp):
        nonlocal best, n_eval
        rec = _evaluate_candidate(model, engine, z_opt, _clip(dx, 0.0, dx_max), _clip(th, 0.0, th_max), _clip(zp, zp_min, zp_max))
        candidates.append(rec)
        n_eval += 1
        if best is None or rec["score"] < best["score"]:
            best = rec
        return rec

    # Always include the user-entered movement as a candidate.
    register(dx0, th0, zp0)

    # Global coarse search.
    for dx in _linspace(0.0, dx_max, 9):
        for th in _linspace(0.0, th_max, 9):
            for zp in _linspace(zp_min, zp_max, 11):
                register(dx, th, zp)

    # Local refinements around current best.
    dx_span = 0.30 * dx_max
    th_span = 0.30 * th_max
    zp_span = 0.25 * H
    for _ in range(4):
        bc = best
        for dx in _linspace(bc["dx"] - dx_span, bc["dx"] + dx_span, 5):
            for th in _linspace(bc["theta_deg"] - th_span, bc["theta_deg"] + th_span, 5):
                for zp in _linspace(bc["z_pivot"] - zp_span, bc["z_pivot"] + zp_span, 5):
                    register(dx, th, zp)
        dx_span *= 0.45
        th_span *= 0.45
        zp_span *= 0.45

    if best is None:
        raise RuntimeError("No-bending optimization failed to evaluate any candidate.")

    opt_solver = str(getattr(model.controls, "rigid_optimization_solver", "Fast equilibrium only") or "Fast equilibrium only").strip().lower()
    if opt_solver.startswith("energy"):
        selected, selection_info = _select_energy_aware_candidate(candidates, model.controls)
    else:
        selected, selection_info = _select_transparent_equilibrium_candidate(candidates, model.controls)
        selection_info = {"rigid optimization solver": "Fast equilibrium only"} | selection_info
    return selected, {
        "optimization evaluations": n_eval,
        "optimization grid points": n_opt,
        "dx search max (m)": dx_max,
        "theta search max (deg)": th_max,
        "z_pivot search min (m)": zp_min,
        "z_pivot search max (m)": zp_max,
        "z_pivot admissibility rule": zp_reason,
        "reinforcement supports active": len(model.reinforcement_supports),
    } | selection_info


def _build_result(model: ModelInput, z: list[float], w: list[float], data: dict, message: str, extra_summary: dict, movement_used: dict | None = None, convergence_history=None) -> SolverResult:
    rotation = _gradient(w, z)
    V, M = _integrate_shear_moment(z, data["net_pressure"])
    mv = movement_used or {
        "dx_trans_m": float(model.movement.dx_trans),
        "theta_rot_deg": float(model.movement.theta_rot_deg),
        "z_pivot_m": float(model.movement.z_pivot),
    }
    theta_tan = math.tan(math.radians(float(mv["theta_rot_deg"])))
    return SolverResult(
        solver_mode="no_bending",
        status="ok",
        message=message,
        z=z,
        p_left=data["p_left"],
        p_right=data["p_right"],
        sigma_left_eff=data.get("sigma_left_eff", []),
        sigma_right_eff=data.get("sigma_right_eff", []),
        u_left=data.get("u_left", []),
        u_right=data.get("u_right", []),
        sigma_left_OE=data["sigma_left_OE"],
        sigma_left_AE=data["sigma_left_AE"],
        sigma_left_PE=data["sigma_left_PE"],
        sigma_right_OE=data["sigma_right_OE"],
        sigma_right_AE=data["sigma_right_AE"],
        sigma_right_PE=data["sigma_right_PE"],
        net_pressure=data["net_pressure"],
        shear=V,
        moment=M,
        deflection=w,
        rotation=rotation,
        K_left=data["K_left"],
        K_right=data["K_right"],
        m_left=data["m_left"],
        m_right=data["m_right"],
        dxmax_left_A=data["dxmax_left_A"],
        dxmax_left_P=data["dxmax_left_P"],
        dxmax_right_A=data["dxmax_right_A"],
        dxmax_right_P=data["dxmax_right_P"],
        deflection_compare=[],
        deflection_compare_label="",
        convergence_history=(convergence_history if convergence_history is not None else [{"iteration": 1.0, "max_change_m": 0.0, "max_abs_deflection_m": float(max(abs(v) for v in w) if w else 0.0)}]),
        summary={
            "solver": "No bending",
            "mode": str(getattr(model.controls, "no_bending_mode", "Manual")),
            "iterations": 1,
            "converged": True,
            "dx_trans_m": float(mv["dx_trans_m"]),
            "theta_rot_deg": float(mv["theta_rot_deg"]),
            "tan_theta_rot": theta_tan,
            "z_pivot": float(mv["z_pivot_m"]),
            "rigid dx_trans reference": "dx_trans is reported at the z_pivot level; for a straight rigid wall line, equivalent z_pivot-dx_trans pairs exist if theta is unchanged and dx is shifted consistently",
            "max_deflection_abs_m": max(abs(v) for v in w) if w else 0.0,
            "EI ignored": model.wall.effective_EI(),
            "H_R": model.geometry.H_R,
            "H_L": model.geometry.H_L,
            "k_h": max(0.0, float(model.seismic.k_h)),
            "k_v": float(model.seismic.k_v),
            "left layers": len(model.left_layers),
            "right layers": len(model.right_layers),
            "reinforcement supports active in net pressure": len(model.reinforcement_supports),
        } | dict(extra_summary),
    )


def solve_no_bending(model: ModelInput) -> SolverResult:
    engine = load_cut_engine()
    H = max(float(model.geometry.H_R), 1.0e-9)
    n = max(3, int(model.controls.n_points))
    z = safe_profile_depths(H, n)
    mode = str(getattr(model.controls, "no_bending_mode", "Manual") or "Manual").strip().lower()

    if not mode.startswith("man"):
        best, opt_summary = _optimize_rigid_movement(model, engine, H)
        # Recalculate the optimum on the full requested output grid.
        dx = best["dx"]
        theta = best["theta_deg"]
        zp = best["z_pivot"]
        w = _rigid_wall_deflection_from_params(z, dx, theta, zp)
        data = _calculate_pressures_for_deflection(model, z, w, engine)
        data = apply_reinforcement_to_pressure_data(data, z, w, model.reinforcement_supports)
        fm = _force_moment_score(z, data["net_pressure"], zp)
        msg = "Rigid-wall optimized solver completed. Selection is transparent: equilibrium band first, then near-minimum work band, then the smallest |theta|/|dx| solution."
        return _build_result(model, z, w, data, msg, opt_summary | {
            "optimized dx_trans_m": dx,
            "optimized theta_rot_deg": theta,
            "optimized z_pivot_m": zp,
            "ΣF kN/m": fm["F"],
            "ΣM kNm/m": fm["M"],
            "normalized equilibrium score": fm["score"],
            "work index kN·m/m": _work_index(z, data["net_pressure"], w),
            "W_left signed kN·m/m": _rigid_energy_metrics(z, data, w)["W_left_signed"],
            "W_right signed kN·m/m": _rigid_energy_metrics(z, data, w)["W_right_signed"],
            "W_net signed kN·m/m": _rigid_energy_metrics(z, data, w)["W_net_signed"],
            "U_internal kN·m/m": 0.0,
            "E_residual = W_net - U_internal": _rigid_energy_metrics(z, data, w)["energy_balance_residual"],
            "energy balance norm": _rigid_energy_metrics(z, data, w)["energy_balance_norm"],
        }, movement_used={"dx_trans_m": dx, "theta_rot_deg": theta, "z_pivot_m": zp})

    # Manual prescribed rigid-body displacement. No EI, no beam update, no iteration.
    w = _rigid_wall_deflection(model, z)
    data = _calculate_pressures_for_deflection(model, z, w, engine)
    data = apply_reinforcement_to_pressure_data(data, z, w, model.reinforcement_supports)
    fm = _force_moment_score(z, data["net_pressure"], float(model.movement.z_pivot))
    msg = "No-bending manual rigid-wall solver completed. Deflection is prescribed from dx_trans, theta_rot and z_pivot; EI is not used."
    return _build_result(model, z, w, data, msg, {
        "ΣF kN/m": fm["F"],
        "ΣM kNm/m": fm["M"],
        "normalized equilibrium score": fm["score"],
        "work index kN·m/m": _work_index(z, data["net_pressure"], w),
        "W_left signed kN·m/m": _rigid_energy_metrics(z, data, w)["W_left_signed"],
        "W_right signed kN·m/m": _rigid_energy_metrics(z, data, w)["W_right_signed"],
        "W_net signed kN·m/m": _rigid_energy_metrics(z, data, w)["W_net_signed"],
        "U_internal kN·m/m": 0.0,
        "E_residual = W_net - U_internal": _rigid_energy_metrics(z, data, w)["energy_balance_residual"],
        "energy balance norm": _rigid_energy_metrics(z, data, w)["energy_balance_norm"],
    })


def compute_work_heatmap(model: ModelInput, theta_values: list[float] | None = None, dx_values: list[float] | None = None, z_pivot_values: list[float] | None = None, n_z: int = 61) -> dict:
    """Compute diagnostic heatmaps for the no-bending rigid-wall family.

    Each theta value produces one row of three maps in the GUI:
      1. normalized work index, W / max(W)
      2. normalized force residual, |ΣF| / ∫|p_net| dz
      3. normalized moment residual, |ΣM| / ∫|p_net * arm| dz

    The normalized quantities are dimensionless and can therefore share a common
    visual scale.  The raw values are also returned for reporting and future
    diagnostics.
    """
    engine = load_cut_engine()
    H = max(float(model.geometry.H_R), 1.0e-9)
    z = safe_profile_depths(H, max(11, int(n_z)))

    dx0 = max(0.0, float(model.movement.dx_trans))
    th0 = max(0.0, float(model.movement.theta_rot_deg))
    dx_max = max(dx0 * 3.0, 0.02 * H, 0.05)
    dx_max = min(dx_max, 0.20 * H)
    th_max = max(th0 * 3.0, 5.0)
    th_max = min(th_max, 20.0)

    if theta_values is None:
        theta_values = _linspace(0.0, th_max, 6)
    if dx_values is None:
        dx_values = _linspace(0.0, dx_max, 25)
    if z_pivot_values is None:
        zp_min, zp_max, _ = admissible_pivot_range(model.geometry.H_L, H, model.reinforcement_supports)
        z_pivot_values = _linspace(zp_min, zp_max, 25)

    work_raw_matrices = []
    force_norm_matrices = []
    moment_norm_matrices = []
    force_raw_matrices = []
    moment_raw_matrices = []
    score_matrices = []
    best_equilibrium = None
    best_work = None
    n_eval = 0

    all_work = []
    for theta in theta_values:
        Wmat = []
        Fnmat = []
        Mnmat = []
        Frawmat = []
        Mrawmat = []
        Scoremat = []
        for zp in z_pivot_values:
            Wrow = []
            Fnrow = []
            Mnrow = []
            Frawrow = []
            Mrawrow = []
            Scorerow = []
            for dx in dx_values:
                rec = _evaluate_candidate(model, engine, z, float(dx), float(theta), float(zp))
                n_eval += 1
                W = float(rec.get("work_index", 0.0))
                F = float(rec.get("F", 0.0))
                M = float(rec.get("M", 0.0))
                Fn = abs(F) / max(float(rec.get("Fscale", 1.0)), 1.0e-30)
                Mn = abs(M) / max(float(rec.get("Mscale", 1.0)), 1.0e-30)
                score = float(rec.get("score", Fn * Fn + Mn * Mn))

                Wrow.append(W)
                Fnrow.append(Fn)
                Mnrow.append(Mn)
                Frawrow.append(F)
                Mrawrow.append(M)
                Scorerow.append(score)
                all_work.append(W)

                current = {
                    "dx": float(dx), "theta_deg": float(theta), "z_pivot": float(zp),
                    "work_index": W, "F": F, "M": M,
                    "F_norm": Fn, "M_norm": Mn, "score": score,
                }
                if best_work is None or W < best_work.get("work_index", 1.0e99):
                    best_work = dict(current)
                if best_equilibrium is None:
                    best_equilibrium = dict(current)
                else:
                    # Primary criterion: equilibrium residuals. Work breaks near ties.
                    tol = 0.02 * max(best_equilibrium.get("score", 1.0e-18), 1.0e-18)
                    if score < best_equilibrium.get("score", 1.0e99) - tol:
                        best_equilibrium = dict(current)
                    elif abs(score - best_equilibrium.get("score", 1.0e99)) <= tol and W < best_equilibrium.get("work_index", 1.0e99):
                        best_equilibrium = dict(current)
            Wmat.append(Wrow)
            Fnmat.append(Fnrow)
            Mnmat.append(Mnrow)
            Frawmat.append(Frawrow)
            Mrawmat.append(Mrawrow)
            Scoremat.append(Scorerow)
        work_raw_matrices.append(Wmat)
        force_norm_matrices.append(Fnmat)
        moment_norm_matrices.append(Mnmat)
        force_raw_matrices.append(Frawmat)
        moment_raw_matrices.append(Mrawmat)
        score_matrices.append(Scoremat)

    Wmax = max([abs(v) for v in all_work] or [1.0])
    if Wmax <= 1.0e-30:
        Wmax = 1.0
    work_norm_matrices = []
    for mat in work_raw_matrices:
        work_norm_matrices.append([[float(v) / Wmax for v in row] for row in mat])

    return {
        "theta_values": [float(v) for v in theta_values],
        "dx_values": [float(v) for v in dx_values],
        "z_pivot_values": [float(v) for v in z_pivot_values],
        "work_matrices": work_norm_matrices,
        "work_raw_matrices": work_raw_matrices,
        "force_norm_matrices": force_norm_matrices,
        "moment_norm_matrices": moment_norm_matrices,
        "force_raw_matrices": force_raw_matrices,
        "moment_raw_matrices": moment_raw_matrices,
        "score_matrices": score_matrices,
        "work_normalization": Wmax,
        "best_work": best_work or {},
        "best_equilibrium": best_equilibrium or {},
        "n_eval": n_eval,
        "n_z": len(z),
    }
