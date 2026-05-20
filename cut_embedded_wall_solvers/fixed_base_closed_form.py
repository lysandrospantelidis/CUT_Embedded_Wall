# -*- coding: utf-8 -*-
"""Fixed base closed-form bending solver. No GUI code.

The beam deflection uses 3-point Gauss integration of the exact cantilever
point-load influence function over each linearly varying pressure interval.
For the adopted piecewise-linear pressure profile this is more accurate than
endpoint lumping of trapezoids and is kept intentionally.
"""
from __future__ import annotations
from .common import *
from .reinforcement import beam_deflection_fixed_base_nodal_supports, has_reinforcement

def solve_fixed_base_only_bending(model: ModelInput) -> SolverResult:
    engine = load_cut_engine()
    H = max(float(model.geometry.H_R), 1.0e-9)
    n = max(3, int(model.controls.n_points))
    z = safe_profile_depths(H, n)
    EI = model.wall.effective_EI()
    if EI <= 0.0:
        raise ValueError("Wall EI must be positive for fixed-base bending analysis.")

    # Start at-rest: zero wall deflection, hence m=1 at all points.
    w = [0.0 for _ in z]
    max_iter = max(1, int(model.controls.max_iterations))
    tol = max(0.0, float(model.controls.tolerance))
    relax = 0.65
    converged = False
    last_diff = float("inf")
    data = None
    history = []

    for it in range(1, max_iter + 1):
        data = _calculate_pressures_for_deflection(model, z, w, engine)
        if has_reinforcement(model.reinforcement_supports):
            w_raw, support_reactions_iter = beam_deflection_fixed_base_nodal_supports(
                z, data["net_pressure"], H, EI, model.reinforcement_supports, w
            )
        else:
            support_reactions_iter = []
            w_raw = _beam_deflection_fixed_base(z, data["net_pressure"], H, EI, model.controls.integration_method)
        w_new = [relax * wn + (1.0 - relax) * wo for wn, wo in zip(w_raw, w)]
        last_diff = max(abs(a - b) for a, b in zip(w_new, w))
        history.append({
            "iteration": float(it),
            "max_change_m": float(last_diff),
            "max_abs_deflection_m": float(max(abs(v) for v in w_new) if w_new else 0.0),
            "max_support_force_abs_kN_per_m": float(max([abs(float(r.get("Fh", 0.0))) for r in support_reactions_iter] or [0.0])),
        })
        w = w_new
        if last_diff <= tol:
            converged = True
            break

    data = _calculate_pressures_for_deflection(model, z, w, engine)
    if has_reinforcement(model.reinforcement_supports):
        w_final_check, support_reactions = beam_deflection_fixed_base_nodal_supports(
            z, data["net_pressure"], H, EI, model.reinforcement_supports, w
        )
    else:
        support_reactions = []
    V, M = _integrate_shear_moment(z, data["net_pressure"])
    rotation = _gradient(w, z)
    method = str(model.controls.integration_method or "Gauss")
    alt_method = "Lumped" if method.strip().lower().startswith("gauss") else "Gauss"
    if has_reinforcement(model.reinforcement_supports):
        w_compare, _support_reactions_compare = beam_deflection_fixed_base_nodal_supports(
            z, data["net_pressure"], H, EI, model.reinforcement_supports, w
        )
        alt_method = "Nodal support FE"
    else:
        w_compare = _beam_deflection_fixed_base(z, data["net_pressure"], H, EI, alt_method)
    status = "ok" if converged else "not_converged"
    msg = (
        f"Fixed base only-bending solver completed in {it} iterations."
        if converged else
        f"Fixed base only-bending solver reached {it} iterations; max Δw={last_diff:.3e}."
    )
    return SolverResult(
        solver_mode="fixed_base_only_bending",
        status=status,
        message=msg,
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
        deflection_compare=w_compare,
        deflection_compare_label=f"{alt_method} comparison",
        convergence_history=history,
        summary={
            "solver": "Fixed base (only bending)",
            "iterations": it,
            "converged": converged,
            "max_deflection_abs_m": max(abs(v) for v in w) if w else 0.0,
            "max_iteration_change_m": last_diff,
            "EI": EI,
            "H_R": model.geometry.H_R,
            "H_L": model.geometry.H_L,
            "k_h": max(0.0, float(model.seismic.k_h)),
            "k_v": float(model.seismic.k_v),
            "left layers": len(model.left_layers),
            "right layers": len(model.right_layers),
            "reinforcement supports active": len(model.reinforcement_supports),
            "reinforcement formulation": "fixed-base nodal nonlinear supports (one-way spring/prestress/capacity); no pressure F/dz correction",
            "support reactions": support_reactions,
            "integration_method": method,
            "comparison_method": alt_method,
        },
    )


