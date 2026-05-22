# -*- coding: utf-8 -*-
"""Fixed base finite-difference differential-equation solver. No GUI code."""
from __future__ import annotations
from .common import *
from .reinforcement import beam_deflection_fixed_base_nodal_supports, has_reinforcement


def _max_abs_diff(a, b):
    if not a or not b:
        return 0.0
    return max(abs(float(x) - float(y)) for x, y in zip(a, b))


def _max_abs(vals):
    return max([abs(float(v)) for v in vals] or [0.0])


def solve_fixed_base_differential_equation(model: ModelInput) -> SolverResult:
    """Fixed-base displacement-coupled CUT pressure solver.

    The coupling is explicit and iterative:
        1. calculate CUT mobilized pressures from the current wall displacement w(z),
        2. solve the fixed-base beam equation, including nodal reinforcement if present,
        3. relax/update w(z),
        4. repeat until the displacement field converges.

    This is not a constant passive-limit spring approximation.  The common CUT
    pressure path `_calculate_pressures_for_deflection()` is called every
    iteration with the current displacement field, so K(z), m(z), active/passive
    state and p_left/p_right are updated from Δx(z).
    """
    engine = load_cut_engine()
    H = max(float(model.geometry.H_R), 1.0e-9)
    n = max(6, int(model.controls.n_points))
    z = safe_profile_depths(H, n)
    EI = model.wall.effective_EI()
    if EI <= 0.0:
        raise ValueError('Wall EI must be positive for fixed-base differential-equation analysis.')

    w = [0.0 for _ in z]
    max_iter = max(1, int(model.controls.max_iterations))
    tol = max(0.0, float(model.controls.tolerance))
    relax = 0.65
    converged = False
    last_diff = float('inf')
    last_pressure_diff = float('inf')
    last_support_diff = float('inf')
    data = None
    history = []
    prev_net = None
    prev_support_forces = []

    for it in range(1, max_iter + 1):
        data = _calculate_pressures_for_deflection(model, z, w, engine)
        if prev_net is None:
            pressure_diff = _max_abs(data.get('net_pressure', []))
        else:
            pressure_diff = _max_abs_diff(data.get('net_pressure', []), prev_net)

        if has_reinforcement(model.reinforcement_supports):
            w_raw, support_reactions_iter = beam_deflection_fixed_base_nodal_supports(
                z, data['net_pressure'], H, EI, model.reinforcement_supports, w
            )
        else:
            support_reactions_iter = []
            w_raw = _beam_deflection_fixed_base_differential(z, data['net_pressure'], H, EI)

        cur_support_forces = [float(r.get('Fh', 0.0)) for r in support_reactions_iter]
        if prev_support_forces and len(prev_support_forces) == len(cur_support_forces):
            support_diff = _max_abs_diff(cur_support_forces, prev_support_forces)
        else:
            support_diff = _max_abs(cur_support_forces)

        w_new = [relax * wn + (1.0 - relax) * wo for wn, wo in zip(w_raw, w)]
        last_diff = _max_abs_diff(w_new, w)
        last_pressure_diff = float(pressure_diff)
        last_support_diff = float(support_diff)
        history.append({
            'iteration': float(it),
            'max_change_m': float(last_diff),
            'max_abs_deflection_m': float(_max_abs(w_new)),
            'max_net_pressure_change_kPa': float(last_pressure_diff),
            'max_support_force_change_kN_per_m': float(last_support_diff),
            'max_support_force_abs_kN_per_m': float(_max_abs(cur_support_forces)),
        })
        w = w_new
        prev_net = list(data.get('net_pressure', []))
        prev_support_forces = list(cur_support_forces)
        if last_diff <= tol:
            converged = True
            break

    data = _calculate_pressures_for_deflection(model, z, w, engine)
    if has_reinforcement(model.reinforcement_supports):
        w_final_check, support_reactions = beam_deflection_fixed_base_nodal_supports(
            z, data['net_pressure'], H, EI, model.reinforcement_supports, w
        )
        final_support_forces = [float(r.get('Fh', 0.0)) for r in support_reactions]
    else:
        support_reactions = []
        final_support_forces = []
    V, M = _integrate_shear_moment(z, data['net_pressure'])
    rotation = _gradient(w, z)
    status = 'ok' if converged else 'not_converged'
    msg = (
        f'Fixed base differential-equation solver completed in {it} iterations with CUT pressure update from current Δx(z).'
        if converged else
        f'Fixed base differential-equation solver reached {it} iterations; max Δw={last_diff:.3e}.'
    )
    return SolverResult(
        solver_mode='fixed_base_differential_equation',
        status=status,
        message=msg,
        z=z,
        p_left=data['p_left'],
        p_right=data['p_right'],
        sigma_left_eff=data.get('sigma_left_eff', []),
        sigma_right_eff=data.get('sigma_right_eff', []),
        u_left=data.get('u_left', []),
        u_right=data.get('u_right', []),
        sigma_left_OE=data['sigma_left_OE'],
        sigma_left_AE=data['sigma_left_AE'],
        sigma_left_PE=data['sigma_left_PE'],
        sigma_right_OE=data['sigma_right_OE'],
        sigma_right_AE=data['sigma_right_AE'],
        sigma_right_PE=data['sigma_right_PE'],
        net_pressure=data['net_pressure'],
        shear=V,
        moment=M,
        deflection=w,
        rotation=rotation,
        K_left=data['K_left'],
        K_right=data['K_right'],
        m_left=data['m_left'],
        m_right=data['m_right'],
        dxmax_left_A=data['dxmax_left_A'],
        dxmax_left_P=data['dxmax_left_P'],
        dxmax_right_A=data['dxmax_right_A'],
        dxmax_right_P=data['dxmax_right_P'],
        convergence_history=history,
        summary={
            'solver': 'Fixed base (differential equation) — displacement-coupled CUT pressures',
            'iterations': it,
            'converged': converged,
            'max_deflection_abs_m': _max_abs(w),
            'max_iteration_change_m': last_diff,
            'max_net_pressure_change_kPa': last_pressure_diff,
            'max_support_force_change_kN_per_m': last_support_diff,
            'pressure update formulation': 'CUT mobilized p_left/p_right recalculated every iteration from current Δx(z); K(z), m(z), and active/passive state are updated by _calculate_pressures_for_deflection.',
            'fixed-base boundary conditions': 'w(H_R)=0 and rotation(H_R)=0',
            'EI': EI,
            'H_R': model.geometry.H_R,
            'H_L': model.geometry.H_L,
            'k_h': max(0.0, float(model.seismic.k_h)),
            'k_v': float(model.seismic.k_v),
            'left layers': len(model.left_layers),
            'right layers': len(model.right_layers),
            'reinforcement supports active': len(model.reinforcement_supports),
            'reinforcement formulation': 'fixed-base nodal nonlinear supports assembled in beam solve (one-way spring/prestress/capacity); no pressure F/dz correction',
            'support reactions': support_reactions,
            'max_support_force_abs_kN_per_m': _max_abs(final_support_forces),
        },
    )
