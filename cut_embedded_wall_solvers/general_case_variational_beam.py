# -*- coding: utf-8 -*-
"""General-case variational beam solver with nonlinear CUT pressures and nodal supports.

This solver is intentionally separate from the older general_case mechanism/work
selector and from the base-spring release solver.  It solves a real beam problem:

    [K_beam + K_base + K_support(active)] w = P_soil(w_old) + P_support(prestress/install)

The CUT mobilized pressure field is recalculated from the current displacement
field at every iteration.  Anchors/props/MSE supports are assembled as nodal
restoring stiffnesses, not as pressure spikes.  Capacity is treated by limiting
support stiffness through a secant cap, so a support cannot become an imposed
free force that pulls the wall backwards.
"""
from __future__ import annotations

from .common import *
from .reinforcement import normalize_supports, has_reinforcement
import math


def _max_abs(vals):
    return max([abs(float(v)) for v in vals] or [0.0])


def _max_abs_diff(a, b):
    if not a or not b:
        return 0.0
    return max(abs(float(x) - float(y)) for x, y in zip(a, b))


def _trapz(z, y):
    if len(z) < 2:
        return 0.0
    s = 0.0
    for i in range(1, len(z)):
        dz = float(z[i]) - float(z[i - 1])
        s += 0.5 * (float(y[i - 1]) + float(y[i])) * dz
    return float(s)


def _interp(z, values, z0):
    if not z or not values:
        return 0.0
    z0 = float(z0)
    if z0 <= float(z[0]):
        return float(values[0])
    if z0 >= float(z[-1]):
        return float(values[-1])
    for i in range(1, min(len(z), len(values))):
        if float(z[i]) >= z0:
            z1 = float(z[i - 1]); z2 = float(z[i])
            v1 = float(values[i - 1]); v2 = float(values[i])
            if abs(z2 - z1) <= 1.0e-30:
                return v2
            t = (z0 - z1) / (z2 - z1)
            return v1 + t * (v2 - v1)
    return float(values[-1])


def _nearest_index(z, z0):
    return min(range(len(z)), key=lambda i: abs(float(z[i]) - float(z0))) if z else 0


def _dense_solve(A, b):
    n = len(b)
    if n == 0:
        return []
    try:
        import numpy as _np  # type: ignore
        return [float(v) for v in _np.linalg.solve(_np.asarray(A, dtype=float), _np.asarray(b, dtype=float)).tolist()]
    except Exception:
        pass
    M = [list(map(float, row)) + [float(bi)] for row, bi in zip(A, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) <= 1.0e-28:
            raise ValueError('Singular variational beam system.')
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


def _gauss3(a, b):
    mid = 0.5 * (a + b)
    half = 0.5 * (b - a)
    r = math.sqrt(3.0 / 5.0)
    for xi, wi in [(-r, 5.0 / 9.0), (0.0, 8.0 / 9.0), (r, 5.0 / 9.0)]:
        yield mid + half * xi, half * wi


def _bending_energy(z, w, EI):
    if len(z) < 3 or len(w) < 3:
        return 0.0
    curv = [0.0 for _ in z]
    for i in range(1, len(z) - 1):
        dz1 = float(z[i]) - float(z[i - 1])
        dz2 = float(z[i + 1]) - float(z[i])
        if abs(dz1) <= 1.0e-30 or abs(dz2) <= 1.0e-30:
            continue
        s1 = (float(w[i]) - float(w[i - 1])) / dz1
        s2 = (float(w[i + 1]) - float(w[i])) / dz2
        curv[i] = 2.0 * (s2 - s1) / (dz1 + dz2)
    if len(curv) >= 2:
        curv[0] = curv[1]
        curv[-1] = curv[-2]
    return 0.5 * float(EI) * _trapz(z, [c * c for c in curv])


def _support_active_terms(s, wi):
    """Return (kt, rhs, Fh, axial, status) for one horizontal nodal support.

    The variational solver must be insensitive to the global displacement sign
    convention used by the pressure engine/plots.  Therefore anchors/MSE are
    assembled as one-way *stabilising* nodal springs: once the wall has moved
    away from its installation position, the support reaction is opposite to
    the current displacement increment.  This avoids the previous pathology in
    which a sign mismatch made anchors remain inactive and reinforced/unreinforced
    runs produced identical diagrams.

    In assembled form the support contribution is

        F_support = rhs - kt*w

    where F_support is the horizontal nodal reaction applied to the wall.  The
    stiffness is capped by a secant capacity limit; capacity is never inserted as
    an unconstrained free force.
    """
    typ = str(s.get('type', 'support')).lower()
    theta = math.radians(float(s.get('theta_deg', 0.0) or 0.0))
    cth = max(0.0, abs(math.cos(theta)))
    k = max(0.0, float(s.get('k', 0.0) or 0.0))
    cap = max(0.0, float(s.get('cap', 0.0) or 0.0))
    prestress = max(0.0, float(s.get('prestress', 0.0) or 0.0))
    install_w = float(s.get('install_w', 0.0) or 0.0)
    wi_eff = float(wi) - install_w

    if typ == 'prop':
        # Compression-only prop/strut.  It engages when the wall closes toward
        # the prop side; because the sign convention may differ between models,
        # use a stabilising secant law against the current displacement once a
        # non-zero closure has developed.  Prestress engages it immediately.
        if abs(wi_eff) <= 1.0e-12 and prestress <= 0.0:
            return 0.0, 0.0, 0.0, 0.0, 'inactive prop'
        sign = 1.0 if wi_eff >= 0.0 else -1.0
        kt = k
        closure = abs(wi_eff)
        if cap > 0.0 and closure > 1.0e-12:
            remaining = max(cap - prestress, 0.0)
            kt = min(kt, remaining / max(closure, 1.0e-12))
        rhs = kt * install_w - prestress * sign
        Fh = rhs - kt * float(wi)
        axial = abs(Fh)
        return kt, rhs, Fh, axial, 'elastic/secant stabilising prop'

    # Anchor/MSE: tension-only stabilising element.  The extension is taken as
    # the absolute movement away from the installation position; the reaction
    # sign is chosen to oppose the current movement.  This keeps the support
    # active for either plotting/pressure sign convention while still preventing
    # a support from becoming a load that drives the wall further in the same
    # direction.
    extension_h = abs(wi_eff)
    if extension_h <= 1.0e-12 and prestress <= 0.0:
        return 0.0, 0.0, 0.0, 0.0, 'inactive tension-only'

    # If only prestress exists at zero displacement, assume the usual retained-
    # side anchor direction opposing excavation-side movement.
    sign = 1.0 if wi_eff >= 0.0 else -1.0
    if extension_h <= 1.0e-12 and prestress > 0.0:
        sign = -1.0

    kt = k * cth * cth
    axial_elastic = max(0.0, k * extension_h * cth)
    axial_trial = prestress + axial_elastic
    if cap > 0.0 and axial_trial > cap:
        remaining = max(cap - prestress, 0.0)
        if extension_h > 1.0e-12:
            kt = min(kt, remaining * cth / max(extension_h, 1.0e-12))
        else:
            kt = 0.0

    rhs = kt * install_w - prestress * cth * sign
    Fh = rhs - kt * float(wi)

    # Numerical safety: if the assembled force still has the same sign as the
    # movement, remove the prestress part for this iteration rather than letting
    # a support destabilise the wall.  The elastic stiffness remains restoring.
    if abs(wi_eff) > 1.0e-12 and Fh * wi_eff > 0.0:
        rhs = kt * install_w
        Fh = rhs - kt * float(wi)

    axial = abs(Fh) / max(cth, 1.0e-12)
    return kt, rhs, Fh, axial, 'elastic/secant stabilising anchor'

def _assemble_variational_beam(z_top_down, q_top_down, H, EI, supports, w_ref, k_y_base, k_theta_base, k_y_gauge=0.0):
    n = len(z_top_down)
    if n < 2:
        return [0.0 for _ in z_top_down], []
    ndof = 2 * n
    K = [[0.0 for _ in range(ndof)] for __ in range(ndof)]
    P = [0.0 for _ in range(ndof)]

    # FE node order is base -> top. Input/result profiles are top -> base.
    z_x = list(reversed([float(v) for v in z_top_down]))
    q_x = list(reversed([float(v) for v in q_top_down]))

    def add(i, j, v):
        K[i][j] += float(v)

    for e in range(n - 1):
        L = abs(float(z_x[e + 1]) - float(z_x[e]))
        if L <= 1.0e-12:
            L = float(H) / max(n - 1, 1)
        ke = float(EI) / (L ** 3)
        k_local = [
            [12.0, 6.0 * L, -12.0, 6.0 * L],
            [6.0 * L, 4.0 * L * L, -6.0 * L, 2.0 * L * L],
            [-12.0, -6.0 * L, 12.0, -6.0 * L],
            [6.0 * L, 2.0 * L * L, -6.0 * L, 4.0 * L * L],
        ]
        dofs = [2 * e, 2 * e + 1, 2 * (e + 1), 2 * (e + 1) + 1]
        for a in range(4):
            for b in range(4):
                add(dofs[a], dofs[b], ke * k_local[a][b])

        q1 = q_x[e]
        q2 = q_x[e + 1]
        fe = [0.0, 0.0, 0.0, 0.0]
        for xx, ww in _gauss3(0.0, L):
            r = xx / L
            N1 = 1.0 - 3.0 * r * r + 2.0 * r * r * r
            N2 = L * (r - 2.0 * r * r + r * r * r)
            N3 = 3.0 * r * r - 2.0 * r * r * r
            N4 = L * (-r * r + r * r * r)
            qg = q1 + r * (q2 - q1)
            for a, Na in enumerate([N1, N2, N3, N4]):
                fe[a] += Na * qg * ww
        for a in range(4):
            P[dofs[a]] += fe[a]

    # Physical elastic base restraint used by the continuation path.
    # This is deliberately the same philosophy as the base-spring solver:
    # both translational and rotational base stiffnesses start from a stable
    # reference level and are progressively released by the outer loop.
    # In earlier test builds k_y_base was passed into this function but was
    # not assembled, which left a free rigid-translation mode and produced
    # runaway deflections.
    K[0][0] += max(0.0, float(k_y_base))
    K[1][1] += max(0.0, float(k_theta_base))

    # Optional numerical translation gauge. Normally zero when physical k_y is
    # active; retained only as a last-resort regularisation hook.
    if k_y_gauge > 0.0:
        K[0][0] += float(k_y_gauge)

    reactions = []
    clean = normalize_supports(supports)
    for s in clean:
        z0 = float(s.get('z', 0.0) or 0.0)
        j_top = _nearest_index(z_top_down, z0)
        j = n - 1 - j_top
        wi = float(w_ref[j_top]) if j_top < len(w_ref) else 0.0
        kt, rhs, Fh, axial, status = _support_active_terms(s, wi)
        dof = 2 * j
        if kt > 0.0:
            K[dof][dof] += kt
        if abs(rhs) > 0.0:
            P[dof] += rhs
        cap = max(0.0, float(s.get('cap', 0.0) or 0.0))
        reactions.append({
            'type': str(s.get('type', 'support')), 'code': str(s.get('code', 'S')),
            'z': z0, 'node_z': float(z_top_down[j_top]), 'w_reference': wi,
            'kt_horizontal': kt, 'rhs_force': rhs, 'Fh': Fh, 'axial': axial,
            'cap': cap, 'util': axial / cap if cap > 0.0 else 0.0,
            'status': status,
        })

    sol = _dense_solve(K, P)
    w_base_to_top = [sol[2 * i] for i in range(n)]
    return list(reversed(w_base_to_top)), reactions


def _default_base_springs(model, H, EI):
    """Return (k_theta, k_y, k_y_gauge, condition, factor) for the variational beam base.

    The physical base-restraint control is rotational only.  The translational
    base spring is kept equal to zero so the solver does not impose a hidden
    base reaction against rigid translation.  A very small numerical translation
    gauge is used only to remove the singular rigid-body mode of the beam matrix.
    """
    # Use embedded length, not total retained height, for the physical scale.
    D = max(float(model.geometry.H_R) - float(model.geometry.H_L), 0.10 * float(H), 1.0e-6)
    k_theta_ref = float(EI) / D
    k_y_ref = 12.0 * float(EI) / (D ** 3)

    controls = getattr(model, 'controls', None)
    condition = str(getattr(controls, 'variational_base_condition', 'Free-like') or 'Free-like')
    condition_l = condition.strip().lower()
    if condition_l in {'free', 'free-like', 'freelike', 'soft'}:
        condition = 'Free-like'
        factor = 2.0e-2
    elif condition_l in {'elastic', 'elastic base', 'calibrated'}:
        condition = 'Elastic base'
        factor = 5.0e-2
    elif condition_l in {'fixed', 'fixed-like', 'fixedlike', 'stiff'}:
        condition = 'Fixed-like'
        factor = 1.0
    elif condition_l in {'custom', 'user'}:
        condition = 'Custom'
        factor = float(getattr(controls, 'variational_base_spring_factor', 1.0e-4) or 1.0e-4)
    else:
        condition = 'Free-like'
        factor = 2.0e-2

    factor = max(1.0e-8, min(float(factor), 1.0e3))
    k_theta = factor * k_theta_ref
    k_y = 0.0
    k_y_gauge = max(1.0e-10 * k_y_ref, 1.0e-12)
    return k_theta, k_y, k_y_gauge, condition, factor


def solve_general_case_variational_beam(model: ModelInput, progress_callback=None) -> SolverResult:
    """Nonlinear FE variational beam solver with base-spring continuation.

    The base springs are not used as a hidden fixed-base assumption.  They form a
    continuation path: the solver starts from a stable stiff base and progressively
    releases both translational and rotational restraint.  The final reported
    response is the lowest accepted release level, while the beam formulation,
    nodal rotations and support stiffness assembly remain the variational/FE model.
    """
    def _progress(**kw):
        if progress_callback is not None:
            progress_callback(dict(kw))

    engine = load_cut_engine()
    H = max(float(model.geometry.H_R), 1.0e-9)
    n = max(11, int(model.controls.n_points))
    z = safe_profile_depths(H, n)
    EI = model.wall.effective_EI()
    if EI <= 0.0:
        raise ValueError('Wall EI must be positive for variational beam general-case analysis.')

    max_iter = max(1, int(model.controls.max_iterations))
    tol = max(0.0, float(model.controls.tolerance))
    engineering_dw_tol_m = max(5.0e-5, 10.0 * tol)   # 0.05 mm lower bound
    engineering_dp_tol_kpa = 5.0e-2

    D = max(float(model.geometry.H_R) - float(model.geometry.H_L), 0.10 * float(H), 1.0e-6)
    k_theta_ref = float(EI) / D
    k_y_ref = 12.0 * float(EI) / (D ** 3)

    controls = getattr(model, 'controls', None)
    base_condition = str(getattr(controls, 'variational_base_condition', 'Free-like') or 'Free-like')
    release_factor = max(0.20, min(0.98, float(getattr(controls, 'variational_spring_release_factor', 0.80) or 0.80)))

    def _make_release_factors(target_factor):
        target = max(1.0e-8, min(float(target_factor), 1.0))
        vals = [1.0]
        x = 1.0
        guard = 0
        while x * release_factor > target * 1.0001 and guard < 200:
            x *= release_factor
            vals.append(float(x))
            guard += 1
        if vals[-1] > target * 1.0001:
            vals.append(float(target))
        elif abs(vals[-1] - target) / max(target, 1.0e-12) > 1.0e-6:
            vals.append(float(target))
        # Remove accidental duplicates while preserving order.
        clean = []
        for v in vals:
            if not clean or abs(float(v) - float(clean[-1])) > 1.0e-12:
                clean.append(float(v))
        return clean

    cond_l = base_condition.strip().lower()
    if cond_l in {'fixed', 'fixed-like', 'fixedlike', 'stiff'}:
        base_condition = 'Fixed-like'
        spring_factors = [1.0]
    elif cond_l in {'elastic', 'elastic base', 'calibrated'}:
        base_condition = 'Elastic base'
        spring_factors = _make_release_factors(0.0625)
    elif cond_l in {'custom', 'user'}:
        base_condition = 'Custom'
        f = max(1.0e-8, min(float(getattr(controls, 'variational_base_spring_factor', 0.015625) or 0.015625), 1.0))
        spring_factors = _make_release_factors(f)
    else:
        base_condition = 'Free-like'
        spring_factors = _make_release_factors(0.001953125)

    all_history = []
    release_history = []
    supports = model.reinforcement_supports if has_reinforcement(model.reinforcement_supports) else []

    # Optional warm start.
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

    def _raw_shape_admissibility_reason(w_profile, *, strict=False):
        """Return a reason if a continuation state has lost the expected mechanism shape.

        For a retained excavation wall, a spring-release level is physically
        admissible only while the dominant movement remains in the exposed/upper
        mechanism region.  If the largest displacement migrates to the deep
        embedded/base zone, that level is a numerical mechanism and must be
        rejected in favour of the previous accepted release state.
        """
        if not w_profile or len(w_profile) != len(z):
            return ''
        abs_w = [abs(float(v)) for v in w_profile]
        max_abs = max(abs_w) if abs_w else 0.0
        if max_abs <= 1.0e-12:
            return ''
        i_max = max(range(len(abs_w)), key=lambda i: abs_w[i])
        z_max = float(z[i_max])
        w_top_abs = abs(float(w_profile[0]))
        w_base_abs = abs(float(w_profile[-1]))
        z_exc = max(0.0, min(float(H), float(model.geometry.H_R) - float(model.geometry.H_L)))
        embed = max(float(H) - z_exc, 0.0)

        # A very robust detector: once the maximum absolute movement is in the
        # lower half of the embedded zone, or at the last node, the release has
        # passed into an inadmissible base-drift mode.  The comparison is strict
        # enough to preserve ordinary bending shapes but rejects the observed
        # "maximum at the base" pathology.
        lower_embed_start = max(z_exc + 0.45 * embed, 0.62 * float(H))
        deep_base_start = max(z_exc + 0.65 * embed, 0.75 * float(H))
        if z_max >= lower_embed_start and max_abs > max(0.85 * max(w_top_abs, 1.0e-12), 0.0015):
            return (
                'rejected by physical-shape criterion: max|Δx| migrated to deep embedded/base zone '
                f'(z={z_max:.3g} m, max|Δx|={1000.0*max_abs:.4g} mm, '
                f'|Δx_top|={1000.0*w_top_abs:.4g} mm)'
            )
        if z_max >= deep_base_start and max_abs > 0.50 * max(w_top_abs, 1.0e-12) and max_abs > 0.001:
            return (
                'rejected by deep-base maximum criterion: dominant displacement is below admissible mechanism zone '
                f'(z={z_max:.3g} m, max|Δx|={1000.0*max_abs:.4g} mm)'
            )
        if w_base_abs > max(0.75 * max(w_top_abs, 1.0e-12), 0.60 * max_abs) and w_base_abs > 0.0015:
            return (
                'rejected by base-drift criterion: base displacement became dominant '
                f'(|Δx_base|={1000.0*w_base_abs:.4g} mm, |Δx_top|={1000.0*w_top_abs:.4g} mm)'
            )
        if strict and len(abs_w) >= 5:
            lower = max(abs_w[int(0.70 * (len(abs_w)-1)):])
            upper = max(abs_w[:max(2, int(0.45 * len(abs_w)))])
            if lower > max(0.90 * upper, 0.0015):
                return (
                    'rejected by lower-zone dominance criterion: lower embedded displacement exceeded upper mechanism displacement '
                    f'(lower={1000.0*lower:.4g} mm, upper={1000.0*upper:.4g} mm)'
                )
        return ''

    def _run_level(w_initial, spring_factor: float, level_index: int):
        w = list(w_initial)
        relax = 0.25
        relax_min = 0.02
        relax_max = 0.32
        prev_trial_change = None
        prev_trial_step = None
        prev_net = None
        prev_support_forces = []
        local_history = []
        last_shape_ok_w = list(w)
        shape_failed = False
        shape_failure_reason = ''
        converged = False
        last_diff = float('inf')
        last_pressure_diff = float('inf')
        last_support_diff = float('inf')
        data = None
        support_reactions_iter = []
        cur_support_forces = []
        k_theta = max(0.0, k_theta_ref * float(spring_factor))
        k_y = max(0.0, k_y_ref * float(spring_factor))
        k_y_gauge = 0.0

        for it in range(1, max_iter + 1):
            _progress(status='running', message=f'Variational beam release {level_index}/{len(spring_factors)}, iteration {it}/{max_iter}', stage='variational_beam', current=len(all_history)+len(local_history), total=max_iter*max(1,len(spring_factors)), fraction=min(0.999, (len(all_history)+len(local_history))/max(max_iter*max(1,len(spring_factors)), 1)))
            data = _calculate_pressures_for_deflection(model, z, w, engine)
            net = list(data.get('net_pressure', []))
            if prev_net is None:
                pressure_diff = _max_abs(net)
            else:
                pressure_diff = _max_abs_diff(net, prev_net)

            w_raw, support_reactions_iter = _assemble_variational_beam(
                z, net, H, EI, supports, w,
                k_y_base=k_y, k_theta_base=k_theta, k_y_gauge=k_y_gauge
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
                dot = sum(float(a) * float(b) for a, b in zip(prev_trial_step, trial_step))
                norm_prev = sum(float(a) * float(a) for a in prev_trial_step) ** 0.5
                norm_cur = sum(float(b) * float(b) for b in trial_step) ** 0.5
                if norm_prev > 0.0 and norm_cur > 0.0:
                    oscillating = dot < -0.10 * norm_prev * norm_cur

            if prev_trial_change is not None:
                if oscillating or trial_change > 1.15 * max(prev_trial_change, 1.0e-30):
                    relax = max(relax_min, 0.55 * relax)
                elif trial_change < 0.85 * max(prev_trial_change, 1.0e-30):
                    relax = min(relax_max, 1.06 * relax + 0.005)

            # Displacement increment limiter to prevent a failed low-restraint
            # level from contaminating the accepted previous state.
            max_step = max(0.02 * H, 0.20)  # m per nonlinear iteration
            if trial_change > max_step and trial_change > 0.0:
                scale = max_step / trial_change
                w_raw = [float(wo) + scale * (float(wr) - float(wo)) for wr, wo in zip(w_raw, w)]
                trial_step = [float(wn) - float(wo) for wn, wo in zip(w_raw, w)]
                trial_change = _max_abs(trial_step)

            w_new = [relax * float(wn) + (1.0 - relax) * float(wo) for wn, wo in zip(w_raw, w)]

            # Do not allow an otherwise converging release level to walk into
            # the nonphysical base-drift mode.  The current level is stopped
            # immediately and the outer continuation loop will retain the
            # previous accepted spring level.
            shape_reason_now = _raw_shape_admissibility_reason(w_new, strict=True)
            if shape_reason_now:
                shape_failed = True
                shape_failure_reason = shape_reason_now
                w = list(last_shape_ok_w)
                last_diff = _max_abs_diff(w_new, w)
                break

            last_shape_ok_w = list(w_new)
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
            prev_net = list(net)
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
        runaway = (not (converged or engineering_converged)) and (deflection_ratio > 0.20 or oscillation_count >= 10)
        accepted_level = (converged or engineering_converged) and not runaway and not shape_failed
        reason = shape_failure_reason if shape_failed else ('ok' if converged else engineering_reason if engineering_converged else 'not converged')
        return {
            'accepted': accepted_level,
            'converged': converged,
            'engineering_converged': engineering_converged,
            'engineering_reason': engineering_reason,
            'reason': reason,
            'runaway': runaway,
            'shape_failed': shape_failed,
            'shape_failure_reason': shape_failure_reason,
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

    def _level_energy_metrics(w_level, data_level, support_reactions_level):
        try:
            U_b_level = _bending_energy(z, w_level, EI)
            W_ext_level = _trapz(z, [float(qi) * float(wi) for qi, wi in zip(data_level.get('net_pressure', []), w_level)])
            U_sup_level = 0.0
            for rr in support_reactions_level or []:
                kt = max(0.0, float(rr.get('kt_horizontal', 0.0)))
                wi = float(rr.get('w_reference', 0.0))
                U_sup_level += 0.5 * kt * wi * wi
            residual = W_ext_level - U_b_level - U_sup_level
            scale = max(abs(W_ext_level), abs(U_b_level) + abs(U_sup_level), 1.0e-12)
            return {
                'beam_strain_energy_kNm_per_m': float(U_b_level),
                'support_strain_energy_kNm_per_m': float(U_sup_level),
                'external_work_kNm_per_m': float(W_ext_level),
                'energy_residual_kNm_per_m': float(residual),
                'energy_residual_norm': float(abs(residual) / scale),
            }
        except Exception:
            return {
                'beam_strain_energy_kNm_per_m': float('nan'),
                'support_strain_energy_kNm_per_m': float('nan'),
                'external_work_kNm_per_m': float('nan'),
                'energy_residual_kNm_per_m': float('nan'),
                'energy_residual_norm': float('inf'),
            }

    accepted_levels = []

    def _shape_admissibility_reason(w_profile):
        return _raw_shape_admissibility_reason(w_profile, strict=True)

    def _release_instability_reason(candidate, previous_levels):
        """Return empty string when the release level remains admissible.

        This is the variational counterpart of the base-spring continuation stop:
        the solver does not stop merely because a scheduled factor has been
        reached.  It keeps releasing until the next level shows a clear loss of
        admissibility: excessive mechanism drift, sudden displacement jump,
        energy-residual deterioration, or migration of the deformation maximum
        to the lower embedded/base region.  In that case the previous accepted
        level is retained as the lowest stable and physically admissible state.
        """
        max_defl = float(candidate.get('max_deflection_abs_m', 0.0))
        ratio_H = float(candidate.get('max_deflection_ratio_H', 0.0))
        energy_norm = float(candidate.get('energy_residual_norm', float('inf')))
        last_dw = float(candidate.get('last_diff', float('inf')))

        shape_reason = _shape_admissibility_reason(candidate.get('w', []))
        if shape_reason:
            return shape_reason

        # Hard guardrails: these catch runaway rigid-body drift.
        if ratio_H > 0.35:
            return f'rejected by mechanism-drift criterion: max|w|/H={ratio_H:.3g} > 0.35'
        if max_defl > max(2.0, 0.35 * H):
            return f'rejected by displacement magnitude criterion: max|w|={1000.0*max_defl:.4g} mm'
        if last_dw > max(5.0e-4, 50.0 * tol):
            return f'rejected by residual-displacement criterion: final Δw={1000.0*last_dw:.4g} mm'

        if len(previous_levels) >= 2:
            prev_defls = [float(lv.get('max_deflection_abs_m', 0.0)) for lv in previous_levels]
            prev = prev_defls[-1]
            cur_jump = max_defl - prev
            prev_jumps = [max(prev_defls[i] - prev_defls[i - 1], 0.0) for i in range(1, len(prev_defls))]
            positive = [j for j in prev_jumps if j > 1.0e-9]
            if positive:
                baseline = sorted(positive)[len(positive) // 2]
                if cur_jump > max(0.05, 2.50 * baseline) and cur_jump > 0.10 * max(prev, 1.0e-9):
                    return (
                        f'rejected by release-jump criterion: Δmax|w|={1000.0*cur_jump:.4g} mm, '
                        f'baseline={1000.0*baseline:.4g} mm'
                    )

            prev_energy = float(previous_levels[-1].get('energy_residual_norm', float('inf')))
            if energy_norm > 0.25 and energy_norm > 3.0 * max(prev_energy, 1.0e-12):
                return (
                    f'rejected by energy-admissibility criterion: |ΔE|/scale={energy_norm:.4g}, '
                    f'previous={prev_energy:.4g}'
                )

        return ''

    last_level = None
    for level_index, factor in enumerate(spring_factors, start=1):
        level = _run_level(w_start, factor, level_index)
        last_level = level
        energy_metrics = _level_energy_metrics(level.get('w', []), level.get('data', {}) or {}, level.get('support_reactions', []))
        level.update(energy_metrics)

        stability_reason = ''
        if level['accepted']:
            stability_reason = _release_instability_reason(level, accepted_levels)
            if stability_reason:
                level['accepted'] = False
                level['reason'] = stability_reason

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
            'energy_residual_norm': float(level.get('energy_residual_norm', float('nan'))),
            'max_deflection_depth_m': float(z[max(range(len(level.get('w', []) or [0])), key=lambda i: abs(float((level.get('w', []) or [0])[i])))]) if level.get('w', []) else 0.0,
            'base_deflection_m': float((level.get('w', []) or [0.0])[-1]),
            'top_deflection_m': float((level.get('w', []) or [0.0])[0]),
            'k_theta_base': float(level['k_theta']),
            'k_y_base': float(level['k_y']),
            'reason': str(level['reason']),
        })
        if level['accepted']:
            all_history.extend(level['history'])
            accepted = level
            accepted_levels.append(dict(level))
            w_start = list(level['w'])
        else:
            rejected_factor = factor
            rejected_reason = str(level['reason'])
            break

    if accepted is None:
        # Never publish a physically inadmissible base-drift state.  If all
        # scheduled release levels were rejected, fall back to the least-released
        # level only when its shape is acceptable; otherwise return the initial
        # no-drift state with an explicit diagnostic instead of a misleading
        # mechanism plot.
        accepted = last_level
        if accepted is None:
            raise ValueError('Variational beam continuation did not run any spring-release level.')
        if _raw_shape_admissibility_reason(accepted.get('w', []), strict=True):
            accepted = dict(accepted)
            accepted['w'] = list(w_start)
            accepted['data'] = _calculate_pressures_for_deflection(model, z, accepted['w'], engine)
            accepted['support_reactions'] = []
            accepted['reason'] = 'all release levels rejected by physical-shape criterion; returned previous safe state'
            rejected_reason = accepted['reason']
        all_history.extend(accepted.get('history', []))

    w = list(accepted['w'])
    data = _calculate_pressures_for_deflection(model, z, w, engine)
    w_check, support_reactions = _assemble_variational_beam(
        z, data['net_pressure'], H, EI, supports, w,
        k_y_base=float(accepted['k_y']), k_theta_base=float(accepted['k_theta']), k_y_gauge=0.0
    )
    fixed_point_residual = _max_abs_diff(w_check, w)
    V, M = _integrate_shear_moment(z, data['net_pressure'])
    rotation = _gradient(w, z)

    U_b = _bending_energy(z, w, EI)
    W_ext = _trapz(z, [float(qi) * float(wi) for qi, wi in zip(data['net_pressure'], w)])
    U_sup = 0.0
    for r in support_reactions:
        try:
            kt = max(0.0, float(r.get('kt_horizontal', 0.0)))
            wi = float(r.get('w_reference', 0.0))
            U_sup += 0.5 * kt * wi * wi
        except Exception:
            pass
    energy_residual = W_ext - U_b - U_sup
    energy_scale = max(abs(W_ext), abs(U_b) + abs(U_sup), 1.0e-12)

    final_spring_factor = float(accepted['spring_factor'])
    spring_factors_tried = [float(rec.get('spring_factor', 0.0)) for rec in release_history]
    spring_factors_accepted = [float(rec.get('spring_factor', 0.0)) for rec in release_history if bool(rec.get('accepted', False))]
    release_completed = final_spring_factor == float(spring_factors[-1]) and rejected_factor is None
    spring_release_msg = (
        f'variational spring-release continuation retained factor {final_spring_factor:g} '
        f'(kθ={float(accepted["k_theta"]):.4g}, ky={float(accepted["k_y"]):.4g})'
    )
    if rejected_factor is not None:
        spring_release_msg += f'; next factor {float(rejected_factor):g} rejected ({rejected_reason})'
    elif release_completed:
        spring_release_msg += '; minimum scheduled spring level reached'

    status = 'ok' if bool(accepted.get('accepted', False)) or fixed_point_residual <= max(tol, 1.0e-7) else 'not_converged'
    message = (
        f'General-case variational beam solver completed; {spring_release_msg}.' if status == 'ok'
        else f'General-case variational beam solver did not fully converge; fixed-point residual={fixed_point_residual:.3e} m. {spring_release_msg}.'
    )

    return SolverResult(
        solver_mode='general_case_variational_beam',
        status=status,
        message=message,
        z=z,
        p_left=data['p_left'], p_right=data['p_right'],
        sigma_left_eff=data.get('sigma_left_eff', []), sigma_right_eff=data.get('sigma_right_eff', []),
        u_left=data.get('u_left', []), u_right=data.get('u_right', []),
        sigma_left_OE=data['sigma_left_OE'], sigma_left_AE=data['sigma_left_AE'], sigma_left_PE=data['sigma_left_PE'],
        sigma_right_OE=data['sigma_right_OE'], sigma_right_AE=data['sigma_right_AE'], sigma_right_PE=data['sigma_right_PE'],
        net_pressure=data['net_pressure'], shear=V, moment=M,
        deflection=w, rotation=rotation,
        K_left=data['K_left'], K_right=data['K_right'],
        m_left=data['m_left'], m_right=data['m_right'],
        dxmax_left_A=data['dxmax_left_A'], dxmax_left_P=data['dxmax_left_P'],
        dxmax_right_A=data['dxmax_right_A'], dxmax_right_P=data['dxmax_right_P'],
        convergence_history=all_history,
        summary={
            'solver': 'General case — variational nonlinear FE beam with spring-release base continuation',
            'iterations': len(all_history),
            'converged': bool(status == 'ok'),
            'max_deflection_abs_m': _max_abs(w),
            'max_iteration_change_m': float(accepted.get('last_diff', float('nan'))),
            'fixed_point_residual_m': float(fixed_point_residual),
            'max_net_pressure_change_kPa': float(accepted.get('last_pressure_diff', float('nan'))),
            'reinforcement supports active': len(supports),
            'support reactions': support_reactions,
            'max_support_force_abs_kN_per_m': _max_abs([float(r.get('Fh', 0.0)) for r in support_reactions]),
            'beam_strain_energy_kNm_per_m': float(U_b),
            'support_strain_energy_kNm_per_m': float(U_sup),
            'external_work_kNm_per_m': float(W_ext),
            'energy_residual_kNm_per_m': float(energy_residual),
            'energy_residual_norm': float(abs(energy_residual) / energy_scale),
            'variational base condition': base_condition,
            'spring_release_enabled': True,
            'variational_spring_release_factor': float(release_factor),
            'spring_release_factors': spring_factors,
            'spring_release_history': release_history,
            'final_spring_factor': final_spring_factor,
            'spring_release_completed': release_completed,
            'spring_release_stop_is_adaptive': bool(rejected_factor is not None),
            'spring_release_stop_reason': rejected_reason,
            'physical_admissibility_stop': bool(rejected_reason and ('deformation-shape' in rejected_reason or 'base-drift' in rejected_reason)),
            'rejected_next_spring_factor': rejected_factor,
            'spring_release_message': spring_release_msg,
            'spring_factors_tried_text': ' → '.join(f'{x:g}' for x in spring_factors_tried),
            'spring_factors_accepted_text': ' → '.join(f'{x:g}' for x in spring_factors_accepted),
            'base rotational spring k_theta': float(accepted['k_theta']),
            'base translational spring k_y': float(accepted['k_y']),
            'base_spring_reference_k_theta': float(k_theta_ref),
            'base_spring_reference_k_y': float(k_y_ref),
            'formulation': 'Nonlinear CUT pressure iteration with Euler-Bernoulli finite-element beam stiffness, nodal rotations, unilateral/secant nodal support stiffness and staged release of translational/rotational base springs; final solution is the lowest stable/admissible release level using adaptive release-stop criteria.',
            'EI': EI,
            'H_R': model.geometry.H_R,
            'H_L': model.geometry.H_L,
            'left layers': len(model.left_layers),
            'right layers': len(model.right_layers),
        },
    )

def compute_work_heatmap(model: ModelInput, *args, **kwargs) -> dict:
    """Small compatibility diagnostic for the UI heatmap call."""
    return {
        'solver_family': 'general_case_variational_beam',
        'note': 'Heatmap is not used by the variational beam solver; run the solver and inspect convergence/energy diagnostics.',
        'theta_values': [], 'dx_values': [], 'z_pivot_values': [],
        'work_matrices': [], 'n_eval': 0,
    }
