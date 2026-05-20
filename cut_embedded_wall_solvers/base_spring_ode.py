# -*- coding: utf-8 -*-
"""Fixed base finite-difference differential-equation solver. No GUI code."""
from __future__ import annotations
from .common import *
from .reinforcement import beam_deflection_base_spring_nodal_supports, has_reinforcement


def _max_abs_diff(a, b):
    if not a or not b:
        return 0.0
    return max(abs(float(x) - float(y)) for x, y in zip(a, b))


def _max_abs(vals):
    return max([abs(float(v)) for v in vals] or [0.0])


def solve_base_spring_differential_equation(model: ModelInput) -> SolverResult:
    """Base-spring displacement-coupled CUT pressure solver with spring-release continuation.

    The 5th solver uses base springs only as a controlled regularisation path.
    It starts from the stabilising bilateral base-spring level and progressively
    releases both kθ and ky.  The final reported solution is the lowest accepted
    spring level, not necessarily the stiff starting level.
    """
    engine = load_cut_engine()
    H = max(float(model.geometry.H_R), 1.0e-9)
    n = max(6, int(model.controls.n_points))
    z = safe_profile_depths(H, n)
    EI = model.wall.effective_EI()
    if EI <= 0.0:
        raise ValueError('Wall EI must be positive for base-spring differential-equation analysis.')

    max_iter = max(1, int(model.controls.max_iterations))
    tol = max(0.0, float(model.controls.tolerance))
    engineering_dw_tol_m = 1.0e-4      # 0.10 mm
    engineering_dp_tol_kpa = 5.0e-2    # 0.05 kPa

    # Reference stabilising springs used by beam_deflection_base_spring_nodal_supports.
    # The continuation below multiplies both of them by spring_factor.
    k_theta_ref = EI / H
    k_y_ref = 12.0 * EI / (H ** 3)
    spring_factors = [1.0, 0.50, 0.25, 0.125, 0.0625, 0.03125, 0.015625]

    all_history = []
    release_history = []

    # Optional warm-start used by the water-level animation.  Consecutive
    # water frames are very close problems, so reusing the previous frame
    # displacement field avoids repeatedly starting the nonlinear contact/CUT
    # iteration from zero.  Normal one-off analyses are unchanged.
    _initial_w = getattr(model, 'initial_deflection', None) or getattr(model, '_initial_deflection', None)
    try:
        if _initial_w is not None and len(_initial_w) == len(z):
            w_start = [float(v) for v in _initial_w]
        else:
            w_start = [0.0 for _ in z]
    except Exception:
        w_start = [0.0 for _ in z]

    accepted = None
    rejected_factor = None
    rejected_reason = ''

    def _run_level(w_initial, spring_factor: float, level_index: int):
        """Solve one spring-release level using the previous accepted field as initial guess."""
        w = list(w_initial)
        relax = 0.30
        relax_min = 0.03
        relax_max = 0.35
        prev_trial_change = None
        prev_trial_step = None
        prev_net = None
        prev_support_forces = []
        local_history = []
        converged = False
        last_diff = float('inf')
        last_pressure_diff = float('inf')
        last_support_diff = float('inf')
        data = None
        support_reactions_iter = []
        cur_support_forces = []
        k_theta = max(0.0, k_theta_ref * spring_factor)
        k_y = max(0.0, k_y_ref * spring_factor)

        for it in range(1, max_iter + 1):
            data = _calculate_pressures_for_deflection(model, z, w, engine)
            if prev_net is None:
                pressure_diff = _max_abs(data.get('net_pressure', []))
            else:
                pressure_diff = _max_abs_diff(data.get('net_pressure', []), prev_net)

            w_raw, support_reactions_iter, _kth_iter, _ky_iter = beam_deflection_base_spring_nodal_supports(
                z, data['net_pressure'], H, EI, model.reinforcement_supports if has_reinforcement(model.reinforcement_supports) else [],
                w, k_theta_base=k_theta, k_y_base=k_y
            )

            cur_support_forces = [float(r.get('Fh', 0.0)) for r in support_reactions_iter]
            if prev_support_forces and len(prev_support_forces) == len(cur_support_forces):
                support_diff = _max_abs_diff(cur_support_forces, prev_support_forces)
            else:
                support_diff = _max_abs(cur_support_forces)

            trial_step = [float(wn) - float(wo) for wn, wo in zip(w_raw, w)]
            trial_change = _max_abs(trial_step)
            oscillating = False
            if prev_trial_step is not None and len(prev_trial_step) == len(trial_step):
                dot = sum(a * b for a, b in zip(prev_trial_step, trial_step))
                norm_prev = sum(a * a for a in prev_trial_step) ** 0.5
                norm_cur = sum(b * b for b in trial_step) ** 0.5
                if norm_prev > 0.0 and norm_cur > 0.0:
                    oscillating = dot < -0.10 * norm_prev * norm_cur

            if prev_trial_change is not None:
                if oscillating or trial_change > 1.10 * max(prev_trial_change, 1.0e-30):
                    relax = max(relax_min, 0.55 * relax)
                elif trial_change < 0.85 * max(prev_trial_change, 1.0e-30):
                    relax = min(relax_max, 1.08 * relax + 0.01)

            w_new = [relax * wn + (1.0 - relax) * wo for wn, wo in zip(w_raw, w)]
            last_diff = _max_abs_diff(w_new, w)
            last_pressure_diff = float(pressure_diff)
            last_support_diff = float(support_diff)
            rec = {
                'iteration': float(len(all_history) + len(local_history) + 1),
                'local_iteration': float(it),
                'spring_release_level': float(level_index),
                'spring_factor': float(spring_factor),
                'k_theta_base': float(k_theta),
                'k_y_base': float(k_y),
                'max_change_m': float(last_diff),
                'max_abs_deflection_m': float(_max_abs(w_new)),
                'max_net_pressure_change_kPa': float(last_pressure_diff),
                'max_support_force_change_kN_per_m': float(last_support_diff),
                'max_support_force_abs_kN_per_m': float(_max_abs(cur_support_forces)),
                'relaxation_factor': float(relax),
                'trial_update_m': float(trial_change),
                'oscillation_detected': float(1.0 if oscillating else 0.0),
            }
            local_history.append(rec)
            w = w_new
            prev_trial_change = float(trial_change)
            prev_trial_step = list(trial_step)
            prev_net = list(data.get('net_pressure', []))
            prev_support_forces = list(cur_support_forces)
            if last_diff <= tol:
                converged = True
                break

        data = _calculate_pressures_for_deflection(model, z, w, engine)
        engineering_converged = False
        engineering_reason = ''
        if (not converged) and last_diff <= engineering_dw_tol_m and last_pressure_diff <= engineering_dp_tol_kpa:
            engineering_converged = True
            engineering_reason = (
                f'asymptotic engineering convergence accepted: final Δw={1000.0*last_diff:.4g} mm, '
                f'final Δp={last_pressure_diff:.4g} kPa'
            )

        max_defl = _max_abs(w)
        deflection_ratio = max_defl / max(H, 1.0e-9)
        oscillation_count = sum(1 for rec in local_history if float(rec.get('oscillation_detected', 0.0)) > 0.5)
        runaway = (not (converged or engineering_converged)) and (deflection_ratio > 0.10 or oscillation_count >= 8)
        accepted_level = (converged or engineering_converged) and not runaway
        reason = 'ok' if converged else engineering_reason if engineering_converged else 'not converged'
        return {
            'accepted': accepted_level,
            'converged': converged,
            'engineering_converged': engineering_converged,
            'engineering_reason': engineering_reason,
            'reason': reason,
            'runaway': runaway,
            'w': w,
            'data': data,
            'history': local_history,
            'last_diff': last_diff,
            'last_pressure_diff': last_pressure_diff,
            'last_support_diff': last_support_diff,
            'k_theta': k_theta,
            'k_y': k_y,
            'spring_factor': spring_factor,
            'iterations': len(local_history),
            'max_deflection_abs_m': max_defl,
            'max_deflection_ratio_H': deflection_ratio,
            'oscillation_count': oscillation_count,
            'support_reactions': support_reactions_iter,
            'support_forces': cur_support_forces,
        }

    for level_index, factor in enumerate(spring_factors, start=1):
        level = _run_level(w_start, factor, level_index)
        release_history.append({
            'spring_release_level': level_index,
            'spring_factor': float(factor),
            'accepted': bool(level['accepted']),
            'converged': bool(level['converged']),
            'engineering_converged': bool(level['engineering_converged']),
            'iterations': int(level['iterations']),
            'max_change_m': float(level['last_diff']),
            'max_net_pressure_change_kPa': float(level['last_pressure_diff']),
            'max_deflection_abs_m': float(level['max_deflection_abs_m']),
            'max_deflection_ratio_H': float(level['max_deflection_ratio_H']),
            'k_theta_base': float(level['k_theta']),
            'k_y_base': float(level['k_y']),
            'reason': str(level['reason']),
        })
        if level['accepted']:
            all_history.extend(level['history'])
            accepted = level
            w_start = list(level['w'])
        else:
            rejected_factor = factor
            rejected_reason = str(level['reason'])
            break

    if accepted is None:
        # Fall back to the first attempted level even if it failed, so the UI can show diagnostics.
        accepted = level
        all_history.extend(level['history'])

    w = list(accepted['w'])
    data = _calculate_pressures_for_deflection(model, z, w, engine)
    w_final_check, support_reactions, k_theta_base, k_y_base = beam_deflection_base_spring_nodal_supports(
        z, data['net_pressure'], H, EI, model.reinforcement_supports if has_reinforcement(model.reinforcement_supports) else [],
        w, k_theta_base=float(accepted['k_theta']), k_y_base=float(accepted['k_y'])
    )
    final_support_forces = [float(r.get('Fh', 0.0)) for r in support_reactions]
    V, M = _integrate_shear_moment(z, data['net_pressure'])
    rotation = _gradient(w, z)

    # --- Spring influence diagnostics ------------------------------------
    # These quantities make the artificial/supporting role of the residual
    # base springs explicit.  The spring-release solver is only fair if the
    # user can see how far the springs were released and how much force/moment
    # they still contribute to the final equilibrium.
    def _trapz_abs(vals, xs):
        try:
            if len(vals) < 2 or len(xs) < 2:
                return abs(float(vals[0])) if vals else 0.0
            total = 0.0
            for a, b, za, zb in zip(vals[:-1], vals[1:], xs[:-1], xs[1:]):
                total += 0.5 * (abs(float(a)) + abs(float(b))) * abs(float(zb) - float(za))
            return float(total)
        except Exception:
            return 0.0

    try:
        base_translation_m = float(w[-1])
    except Exception:
        base_translation_m = 0.0
    try:
        base_rotation_rad = float(rotation[-1])
    except Exception:
        base_rotation_rad = 0.0
    residual_base_spring_force = float(k_y_base) * base_translation_m
    residual_base_spring_moment = float(k_theta_base) * base_rotation_rad
    total_driving_force_scale = max(_trapz_abs(data.get('net_pressure', []), z), 1.0e-12)
    total_driving_moment_scale = max(_trapz_abs([float(pv) * abs(H - float(zz)) for pv, zz in zip(data.get('net_pressure', []), z)], z), 1.0e-12)
    max_wall_moment_scale = max(_max_abs(M), 1.0e-12)
    spring_force_ratio = abs(residual_base_spring_force) / total_driving_force_scale
    spring_moment_ratio_driving = abs(residual_base_spring_moment) / total_driving_moment_scale
    spring_moment_ratio_wall = abs(residual_base_spring_moment) / max_wall_moment_scale
    spring_influence_ratio = max(spring_force_ratio, spring_moment_ratio_driving, spring_moment_ratio_wall)
    if spring_influence_ratio < 0.05:
        spring_influence_class = 'nearly free-base'
    elif spring_influence_ratio <= 0.20:
        spring_influence_class = 'spring-influenced'
    else:
        spring_influence_class = 'spring-dominated'

    spring_factors_tried = [float(rec.get('spring_factor', 0.0)) for rec in release_history]
    spring_factors_accepted = [float(rec.get('spring_factor', 0.0)) for rec in release_history if bool(rec.get('accepted', False))]

    converged = bool(accepted['converged'])
    engineering_converged = bool(accepted['engineering_converged'])
    engineering_reason = str(accepted['engineering_reason'])
    last_diff = float(accepted['last_diff'])
    last_pressure_diff = float(accepted['last_pressure_diff'])
    last_support_diff = float(accepted['last_support_diff'])
    max_defl = _max_abs(w)
    deflection_ratio = max_defl / max(H, 1.0e-9)
    final_relax = float(all_history[-1].get('relaxation_factor', 0.0)) if all_history else 0.0
    oscillation_count = sum(1 for rec in all_history if float(rec.get('oscillation_detected', 0.0)) > 0.5)
    final_spring_factor = float(accepted['spring_factor'])
    release_completed = final_spring_factor == float(spring_factors[-1]) and rejected_factor is None

    spring_release_msg = (
        f'spring-release continuation retained factor {final_spring_factor:g} '
        f'(kθ={float(accepted["k_theta"]):.4g}, ky={float(accepted["k_y"]):.4g})'
    )
    if rejected_factor is not None:
        spring_release_msg += f'; next factor {float(rejected_factor):g} rejected ({rejected_reason})'
    else:
        spring_release_msg += '; minimum scheduled spring level reached'

    if engineering_converged and deflection_ratio >= 0.02:
        response_class = 'engineering-converged large-displacement spring-release response'
        diagnostic_warning = (
            'Engineering convergence was accepted and the wall response is very flexible. '
            'Treat this as a serviceability/stress-test case and inspect displacements. '
            + spring_release_msg
        )
    elif engineering_converged:
        response_class = 'engineering-converged spring-release response'
        diagnostic_warning = 'Engineering convergence was accepted. ' + spring_release_msg
    elif (not converged) and (deflection_ratio >= 0.02 or oscillation_count >= 3):
        response_class = 'mechanism-like / unstable very-flexible spring-release response'
        diagnostic_warning = (
            'The base-spring release could not find a fully admissible lower-restraint state. '
            + spring_release_msg
        )
    elif deflection_ratio >= 0.02:
        response_class = 'large-displacement spring-release response'
        diagnostic_warning = 'Large displacement relative to retained height. ' + spring_release_msg
    elif oscillation_count >= 3:
        response_class = 'oscillation-controlled spring-release response'
        diagnostic_warning = 'Adaptive relaxation detected repeated oscillation. ' + spring_release_msg
    else:
        response_class = 'stable spring-release base response'
        diagnostic_warning = spring_release_msg

    if converged:
        status = 'ok'
        msg = f'Base-spring release solver completed; {spring_release_msg}.'
    elif engineering_converged:
        status = 'engineering_converged'
        msg = f'Base-spring release solver accepted as engineering-converged; {engineering_reason}. {spring_release_msg}.'
    else:
        status = 'not_converged'
        msg = f'Base-spring release solver did not converge; max Δw={last_diff:.3e}. {spring_release_msg}.'

    return SolverResult(
        solver_mode='base_spring_differential_equation',
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
        convergence_history=all_history,
        summary={
            'solver': 'Base spring (differential equation) — spring-release continuation',
            'iterations': len(all_history),
            'converged': converged,
            'engineering_converged': engineering_converged,
            'engineering_convergence_reason': engineering_reason,
            'engineering_displacement_tolerance_m': engineering_dw_tol_m,
            'engineering_pressure_tolerance_kPa': engineering_dp_tol_kpa,
            'max_deflection_abs_m': max_defl,
            'max_deflection_ratio_H': deflection_ratio,
            'response_classification': response_class,
            'diagnostic_warning': diagnostic_warning,
            'oscillation_count': oscillation_count,
            'max_iteration_change_m': last_diff,
            'max_net_pressure_change_kPa': last_pressure_diff,
            'max_support_force_change_kN_per_m': last_support_diff,
            'pressure update formulation': 'CUT mobilized p_left/p_right recalculated every iteration from current Δx(z); K(z), m(z), and active/passive state are updated by _calculate_pressures_for_deflection.',
            'base-spring boundary conditions': 'R(H_R)=ky·w(H_R) and M(H_R)=kθ·θ(H_R); kθ and ky are progressively released before final acceptance',
            'spring_release_enabled': True,
            'spring_release_factors': spring_factors,
            'spring_release_history': release_history,
            'final_spring_factor': final_spring_factor,
            'spring_release_completed': release_completed,
            'rejected_next_spring_factor': rejected_factor,
            'spring_release_message': spring_release_msg,
            'spring_factors_tried': spring_factors_tried,
            'spring_factors_accepted': spring_factors_accepted,
            'spring_factors_tried_text': ' → '.join(f'{x:g}' for x in spring_factors_tried),
            'spring_factors_accepted_text': ' → '.join(f'{x:g}' for x in spring_factors_accepted),
            'base_translation_m': base_translation_m,
            'base_rotation_rad': base_rotation_rad,
            'residual_base_spring_force_kN_per_m': residual_base_spring_force,
            'residual_base_spring_moment_kNm_per_m': residual_base_spring_moment,
            'total_driving_force_scale_kN_per_m': total_driving_force_scale,
            'total_driving_moment_scale_kNm_per_m': total_driving_moment_scale,
            'max_wall_moment_scale_kNm_per_m': max_wall_moment_scale,
            'spring_force_ratio': spring_force_ratio,
            'spring_moment_ratio_driving': spring_moment_ratio_driving,
            'spring_moment_ratio_wall': spring_moment_ratio_wall,
            'spring_influence_ratio': spring_influence_ratio,
            'spring_influence_percent': 100.0 * spring_influence_ratio,
            'spring_influence_classification': spring_influence_class,
            'spring_influence_rule': '<5% nearly free-base; 5–20% spring-influenced; >20% spring-dominated',
            'relaxation_factor_final': final_relax,
            'relaxation_factor_bounds': (0.03, 0.35),
            'stabilization': 'adaptive under-relaxation plus spring-release continuation; springs are reduced and only the lowest accepted restraint level is reported',
            'EI': EI,
            'H_R': model.geometry.H_R,
            'H_L': model.geometry.H_L,
            'k_h': max(0.0, float(model.seismic.k_h)),
            'k_v': float(model.seismic.k_v),
            'left layers': len(model.left_layers),
            'right layers': len(model.right_layers),
            'reinforcement supports active': len(model.reinforcement_supports),
            'reinforcement formulation': 'base-spring nodal nonlinear supports assembled in beam solve (one-way spring/prestress/capacity); no pressure F/dz correction',
            'support reactions': support_reactions,
            'base rotational spring k_theta': k_theta_base,
            'base translational spring k_y': k_y_base,
            'reference base rotational spring k_theta': k_theta_ref,
            'reference base translational spring k_y': k_y_ref,
            'max_support_force_abs_kN_per_m': _max_abs(final_support_forces),
        },
    )
