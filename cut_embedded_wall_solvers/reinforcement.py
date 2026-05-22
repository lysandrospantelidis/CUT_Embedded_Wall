# -*- coding: utf-8 -*-
"""Reinforcement/support utilities for CUT embedded wall solvers.

This module is intentionally independent from the GUI and from individual
solver strategies.  It receives the unified support dictionaries prepared by
GUI and converts them to equivalent horizontal loads on the wall.

Sign convention used here is the same as the solver net pressure convention:
    q_net = p_right - p_left
Positive q_net pushes the wall toward the left/excavation side.  Positive wall
movement w is the adopted positive displacement convention used by the CUT
mobilisation routines.  Anchors and MSE layers are placed on the right/retained
side and are tension-only. Props are placed on the left/excavation side and are
compression-only.
"""
from __future__ import annotations

import math
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else float(default)
    except Exception:
        return float(default)


def normalize_supports(supports: list[dict[str, Any]] | None) -> list[dict[str, float | str]]:
    """Return a clean list of support dictionaries with safe numeric fields."""
    out: list[dict[str, float | str]] = []
    for raw in supports or []:
        typ = str(raw.get("type", "support") or "support").strip().lower()
        code = str(raw.get("code", typ[:1].upper() or "S"))
        z = max(0.0, _as_float(raw.get("z", 0.0), 0.0))
        theta = _as_float(raw.get("theta_deg", 0.0), 0.0)
        k = max(0.0, _as_float(raw.get("k", 0.0), 0.0))
        cap = max(0.0, _as_float(raw.get("cap", 0.0), 0.0))
        prestress = max(0.0, _as_float(raw.get("prestress", 0.0), 0.0))
        L = max(0.0, _as_float(raw.get("L", 0.0), 0.0))
        # Optional staged-construction neutral displacement.  When a support is
        # installed after previous excavation movements, its elastic extension
        # must be measured from the wall position at installation, not from the
        # original undeformed wall.  Normal one-shot analyses omit this field and
        # therefore keep the previous behaviour.
        install_w = _as_float(raw.get("install_w", raw.get("w_install", 0.0)), 0.0)
        if k <= 0.0 and prestress <= 0.0:
            continue
        out.append({
            "type": typ,
            "code": code,
            "z": z,
            "theta_deg": theta,
            "k": k,
            "cap": cap,
            "prestress": prestress,
            "L": L,
            "install_w": install_w,
        })
    return out


def _interp(z: list[float], values: list[float], z0: float) -> float:
    if not z or not values:
        return 0.0
    if z0 <= z[0]:
        return float(values[0])
    if z0 >= z[-1]:
        return float(values[-1])
    for i in range(1, min(len(z), len(values))):
        if z[i] >= z0:
            z1, z2 = float(z[i-1]), float(z[i])
            v1, v2 = float(values[i-1]), float(values[i])
            if abs(z2-z1) <= 1e-15:
                return v2
            t = (z0-z1)/(z2-z1)
            return v1 + t*(v2-v1)
    return float(values[-1])


def _nearest_index(z: list[float], z0: float) -> int:
    if not z:
        return 0
    return min(range(len(z)), key=lambda i: abs(float(z[i]) - float(z0)))


def support_reactions(z: list[float], w: list[float], supports: list[dict[str, Any]] | None) -> list[dict[str, float | str]]:
    """Compute support reactions for the current wall displacement field.

    Returned force `Fh` is positive when it acts in the positive q_net sense;
    the equivalent distributed load contribution is Fh/dz at the nearest grid
    node.  For anchors/MSE on the retained side, tension resists positive wall
    movement, hence Fh is negative. For props on the excavation side,
    compression resists negative movement, hence Fh is positive.
    """
    clean = normalize_supports(supports)
    if not clean or not z or not w:
        return []
    reactions: list[dict[str, float | str]] = []
    for s in clean:
        typ = str(s["type"])
        z0 = float(s["z"])
        theta = math.radians(float(s.get("theta_deg", 0.0)))
        cth = max(0.0, abs(math.cos(theta)))
        wi = _interp(z, w, z0)
        wi_eff = wi - float(s.get("install_w", 0.0) or 0.0)
        k = float(s.get("k", 0.0))
        cap = float(s.get("cap", 0.0))
        prestress = float(s.get("prestress", 0.0))
        if typ == "prop":
            # Prop/strut on excavation side: compression-only in the current
            # fixed-base displacement convention.  The propped-wall benchmark
            # develops positive wall displacement at the support level, so the
            # strut engages for wi > 0 and its horizontal reaction opposes that
            # movement, i.e. Fh is negative, consistently with anchors.
            elong = max(0.0, wi_eff)
            axial = k * elong
            if cap > 0.0:
                axial = min(axial, cap)
            Fh = -axial
        else:
            # Anchor/MSE on retained/right side: tension-only. It engages when
            # the wall moves away from the retained side in the positive w
            # convention. Prestress is included as initial tension.
            elong = max(0.0, wi_eff * cth)
            axial = prestress + k * elong
            if cap > 0.0:
                axial = min(axial, cap)
            Fh = -axial * cth
        if abs(Fh) <= 1e-18:
            continue
        reactions.append({
            "type": typ,
            "code": str(s.get("code", typ)),
            "z": z0,
            "w": wi,
            "axial": axial,
            "Fh": Fh,
        })
    return reactions


def equivalent_support_load(z: list[float], w: list[float], supports: list[dict[str, Any]] | None) -> list[float]:
    """Return equivalent distributed nodal load q_support(z) in kPa = kN/m².

    This is a numerical representation of concentrated support forces per metre
    wall length.  The force is applied to the nearest grid point and divided by a
    representative tributary depth.
    """
    q = [0.0 for _ in z]
    if len(z) < 2:
        return q
    reactions = support_reactions(z, w, supports)
    if not reactions:
        return q
    for r in reactions:
        i = _nearest_index(z, float(r["z"]))
        if i == 0:
            dz = abs(float(z[1]) - float(z[0]))
        elif i == len(z) - 1:
            dz = abs(float(z[-1]) - float(z[-2]))
        else:
            dz = 0.5 * abs(float(z[i+1]) - float(z[i-1]))
        dz = max(dz, 1.0e-12)
        q[i] += float(r["Fh"]) / dz
    return q


def _stabilizing_only_support_load(net: list[float], qsup_raw: list[float]) -> list[float]:
    """Clamp support load so reinforcement can only reduce the driving net pressure.

    Anchors, props and MSE layers are unilateral stabilizing elements.  They
    must not create a reversed pressure spike that drives the wall to the other
    side.  The raw nodal support force is therefore clipped locally:

    * if the unreinforced net pressure is positive, only a negative support
      contribution is admissible and it cannot reduce the net pressure below 0;
    * if the unreinforced net pressure is negative, only a positive support
      contribution is admissible and it cannot increase the net pressure above 0;
    * if the unreinforced net pressure is zero, the effective support load is 0.

    This keeps the concentrated reinforcement reaction in the force balance but
    prevents non-physical over-correction/backward wall movement caused by a
    support node being represented as q = F/dz.
    """
    qeff: list[float] = []
    n = min(len(net), len(qsup_raw))
    for i in range(n):
        qi = float(net[i])
        si = float(qsup_raw[i])
        if qi > 0.0:
            # Stabilizing support must act opposite to the positive driving load.
            si = min(0.0, si)
            si = max(si, -qi)
        elif qi < 0.0:
            # Stabilizing support must act opposite to the negative driving load.
            si = max(0.0, si)
            si = min(si, -qi)
        else:
            si = 0.0
        qeff.append(si)
    if len(qsup_raw) > n:
        qeff.extend(0.0 for _ in qsup_raw[n:])
    return qeff


def apply_reinforcement_to_pressure_data(data: dict, z: list[float], w: list[float], supports: list[dict[str, Any]] | None) -> dict:
    """Return a shallow copy of pressure data with stabilizing reinforcement added.

    The raw concentrated support reactions are first calculated from the
    unilateral laws in :func:`support_reactions`.  They are then clipped against
    the unreinforced net pressure so that reinforcement can reduce the driving
    pressure but cannot reverse it.  This avoids artificial backward movement
    from over-active reinforcement while preserving the one-way anchor/prop/MSE
    behaviour.
    """
    qsup_raw = equivalent_support_load(z, w, supports)
    out = dict(data)
    net = list(out.get("net_pressure", []))
    qsup = _stabilizing_only_support_load(net, qsup_raw)
    if not any(abs(v) > 0.0 for v in qsup):
        out["support_load_raw"] = qsup_raw
        out["support_load"] = qsup
        out["support_reactions"] = []
        return out
    n = min(len(net), len(qsup))
    out["net_pressure"] = [float(net[i]) + float(qsup[i]) for i in range(n)] + [float(v) for v in net[n:]]
    out["support_load_raw"] = qsup_raw
    out["support_load"] = qsup
    out["support_reactions"] = support_reactions(z, w, supports)
    return out


def has_reinforcement(supports: list[dict[str, Any]] | None) -> bool:
    return len(normalize_supports(supports)) > 0


def admissible_pivot_range(H_L: float, H_R: float, supports: list[dict[str, Any]] | None) -> tuple[float, float, str]:
    """Return recommended z_pivot search range and a readable reason.

    For an unsupported free embedded wall, a pivot above excavation level is
    generally a suspicious mechanism.  For supported/reinforced systems, the
    mechanism can rotate about support levels, so the upper bound is relaxed.
    """
    HL = max(0.0, float(H_L))
    HR = max(HL, float(H_R))
    clean = normalize_supports(supports)
    if not clean:
        return HL, HR, "no reinforcement: pivot constrained to embedded/passive zone [H_L, H_R]"
    zmin = 0.0
    zmax = HR
    ztop = min(float(s["z"]) for s in clean)
    return zmin, zmax, f"reinforcement/supports active: pivot range relaxed to [0, H_R]; upper support z≈{ztop:.3g} m"


# ---------------------------------------------------------------------------
# v6.7 fixed-base formulation: true nodal nonlinear supports
# ---------------------------------------------------------------------------
def _dense_solve(A: list[list[float]], b: list[float]) -> list[float]:
    """Dense linear solve for the FE support solver.

    v6.9.49 keeps the v33 support mechanics, but uses NumPy/LAPACK when
    available for speed; the original v33 Gauss-Jordan solver remains the
    fallback.
    """
    n = len(b)
    if n == 0:
        return []
    try:
        import numpy as _np  # type: ignore
        AA = _np.asarray(A, dtype=float)
        bb = _np.asarray(b, dtype=float)
        sol = _np.linalg.solve(AA, bb)
        return [float(v) for v in sol.tolist()]
    except Exception:
        pass
    M = [list(map(float, row)) + [float(bi)] for row, bi in zip(A, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) <= 1.0e-28:
            raise ValueError("Singular fixed-base nodal-support beam system.")
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


def _gauss3(a: float, b: float):
    mid = 0.5 * (a + b)
    half = 0.5 * (b - a)
    r = math.sqrt(3.0 / 5.0)
    for xi, wi in [(-r, 5.0 / 9.0), (0.0, 8.0 / 9.0), (r, 5.0 / 9.0)]:
        yield mid + half * xi, half * wi


def _support_node_index_top_down(z_top_down: list[float], z0: float) -> int:
    return _nearest_index(z_top_down, z0)


def _support_status_from_displacement(s: dict[str, float | str], wi: float) -> tuple[float, float, float, str]:
    """Return (kt, f0, force, status) for one nodal support.

    The support force acting on the wall is represented as
        F_support = f0 - kt * w_i
    so that the linearized global equation is
        (K + kt) w = P + f0
    at the support node.

    Anchors/MSE on the retained/right side are tension-only and act in the
    negative net-pressure direction. Props on the excavation/left side are
    compression-only and act in the positive net-pressure direction.
    """
    typ = str(s.get("type", "support"))
    theta = math.radians(float(s.get("theta_deg", 0.0)))
    cth = max(0.0, abs(math.cos(theta)))
    k = max(0.0, float(s.get("k", 0.0)))
    cap = max(0.0, float(s.get("cap", 0.0)))
    prestress = max(0.0, float(s.get("prestress", 0.0)))

    install_w = float(s.get("install_w", 0.0) or 0.0)
    wi_eff = wi - install_w

    if typ == "prop":
        # Same sign convention as the fixed-base anchored case: positive wall
        # displacement at the strut level closes the prop/strut and mobilizes
        # compression.  For staged construction, wi_eff is measured relative to
        # the wall position at installation so a newly inserted strut/anchor does
        # not artificially pull the wall back to the undeformed position.
        # F_support = -k*wi_eff in the elastic range.  With the assembled equation
        # (K + kt) w = P + f0, this is represented by kt=k and f0=k*install_w.
        if wi_eff <= 0.0:
            return 0.0, 0.0, 0.0, "inactive compression-only"
        elastic = k * wi_eff
        if cap > 0.0 and elastic >= cap:
            return 0.0, -cap, -cap, "capacity"
        return k, k * install_w, -elastic, "elastic"

    # Anchor/MSE/strip/grid: right-side tensile element. Prestress is a permanent
    # initial tension, while additional elastic force develops only for positive
    # wall movement. Horizontal stiffness is k*cos²(theta), and prestress/capacity
    # are projected by cos(theta) into the wall horizontal equation.
    if wi_eff <= 0.0:
        axial = prestress
        force = -axial * cth
        if cap > 0.0 and axial >= cap:
            force = -cap * cth
            return 0.0, force, force, "prestress at capacity"
        return 0.0, force, force, "prestress only" if axial > 0.0 else "inactive tension-only"
    axial = prestress + k * wi_eff * cth
    if cap > 0.0 and axial >= cap:
        force = -cap * cth
        return 0.0, force, force, "capacity"
    kt = k * cth * cth
    f0 = kt * install_w - prestress * cth
    force = f0 - kt * wi
    return kt, f0, force, "elastic"


def beam_deflection_fixed_base_nodal_supports(
    z_top_down: list[float],
    q_top_down: list[float],
    H: float,
    EI: float,
    supports: list[dict[str, Any]] | None,
    w_reference_top_down: list[float] | None = None,
) -> tuple[list[float], list[dict[str, float | str]]]:
    """Solve a fixed-base Euler-Bernoulli beam with true nodal nonlinear supports.

    This is the replacement for the old reinforcement pressure correction in
    fixed-base analyses.  Distributed soil pressure remains an element load;
    anchors, props and MSE layers are assembled at wall nodes as one-way spring
    reactions with prestress and capacity.  No F/dz pressure spike is generated.
    """
    n = len(z_top_down)
    if n == 0:
        return [], []
    if n < 2:
        return [0.0 for _ in z_top_down], []
    H = max(float(H), 1.0e-12)
    EI = max(float(EI), 1.0e-30)
    ndof = 2 * n
    K = [[0.0 for _ in range(ndof)] for __ in range(ndof)]
    P = [0.0 for _ in range(ndof)]

    # FE coordinate is x measured upward from the fixed base. Node order is base -> top.
    z_x = list(reversed([float(v) for v in z_top_down]))
    q_x = list(reversed([float(v) for v in q_top_down]))

    def add(i: int, j: int, v: float):
        K[i][j] += float(v)

    for e in range(n - 1):
        x1 = H - z_x[e]
        x2 = H - z_x[e + 1]
        # Since z_x is base->top decreasing in physical depth, x increases base->top.
        # Uniform safe fallback for the normal equally-spaced grid.
        L = abs(float(z_x[e + 1]) - float(z_x[e]))
        if L <= 1.0e-12:
            L = H / max(n - 1, 1)
        ke = EI / (L ** 3)
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
        # Consistent nodal loads for linearly varying distributed pressure.
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

    # Nonlinear supports are active-set linearized from the previous/current wall shape.
    w_ref = list(w_reference_top_down or [0.0 for _ in z_top_down])
    clean = normalize_supports(supports)
    reactions: list[dict[str, float | str]] = []
    for s in clean:
        z0 = float(s.get("z", 0.0))
        j_top = _support_node_index_top_down(z_top_down, z0)
        # Convert top-down node to base->top FE node.
        j = n - 1 - j_top
        wi = float(w_ref[j_top]) if j_top < len(w_ref) else 0.0
        kt, f0, force, status = _support_status_from_displacement(s, wi)
        dof = 2 * j
        if kt > 0.0:
            K[dof][dof] += kt
        if abs(f0) > 0.0:
            P[dof] += f0
        elif kt <= 0.0 and abs(force) > 0.0:
            # Capacity or prestress-only force is constant in this active set.
            P[dof] += force
        theta_deg = float(s.get("theta_deg", 0.0) or 0.0)
        cth = max(1.0e-12, abs(math.cos(math.radians(theta_deg))))
        cap = max(0.0, float(s.get("cap", 0.0) or 0.0))
        axial = abs(force) / cth
        reactions.append({
            "type": str(s.get("type", "support")),
            "code": str(s.get("code", "S")),
            "z": z0,
            "node_z": float(z_top_down[j_top]),
            "w_reference": wi,
            "theta_deg": theta_deg,
            "k": float(s.get("k", 0.0) or 0.0),
            "cap": cap,
            "prestress": float(s.get("prestress", 0.0) or 0.0),
            "L": float(s.get("L", 0.0) or 0.0),
            "install_w": float(s.get("install_w", 0.0) or 0.0),
            "kt_horizontal": kt,
            "Fh": force,
            "axial": axial,
            "util": abs(axial) / cap if cap > 0.0 else 0.0,
            "status": status,
        })

    # Fixed base: w=0 and rotation=0 at base node (FE node 0).
    fixed = {0: 0.0, 1: 0.0}
    free = [i for i in range(ndof) if i not in fixed]
    A = [[K[i][j] for j in free] for i in free]
    b = [P[i] - sum(K[i][j] * val for j, val in fixed.items()) for i in free]
    sol_free = _dense_solve(A, b)
    U = [0.0 for _ in range(ndof)]
    for j, val in fixed.items():
        U[j] = val
    for idx, dof in enumerate(free):
        U[dof] = sol_free[idx]
    w_base_to_top = [U[2 * i] for i in range(n)]
    return list(reversed(w_base_to_top)), reactions


def beam_deflection_base_spring_nodal_supports(
    z_top_down: list[float],
    q_top_down: list[float],
    H: float,
    EI: float,
    supports: list[dict[str, Any]] | None,
    w_reference_top_down: list[float] | None = None,
    k_theta_base: float | None = None,
    k_y_base: float | None = None,
) -> tuple[list[float], list[dict[str, float | str]], float, float]:
    """Euler-Bernoulli beam with elastic translational and rotational base springs.

    Base boundary condition: R(H_R)=k_y*w(H_R) and M(H_R)=k_theta*theta(H_R).
    This is the controlled intermediate stage after rotational spring verification:
    base translation is no longer fixed, but it is restrained by a finite spring.
    Reinforcement/support elements are kept identical to the fixed-base nodal-support
    formulation.
    """
    n = len(z_top_down)
    if n == 0:
        return [], [], 0.0
    if n < 2:
        return [0.0 for _ in z_top_down], [], 0.0
    H = max(float(H), 1.0e-12)
    EI = max(float(EI), 1.0e-30)
    # Conservative stabilising base restraints. Same units as FE nodal DOF stiffnesses.
    k_theta = float(k_theta_base) if k_theta_base is not None else EI / H
    k_theta = max(0.0, k_theta)
    k_y = float(k_y_base) if k_y_base is not None else 12.0 * EI / (H ** 3)
    k_y = max(0.0, k_y)

    ndof = 2 * n
    K = [[0.0 for _ in range(ndof)] for __ in range(ndof)]
    P = [0.0 for _ in range(ndof)]
    z_x = list(reversed([float(v) for v in z_top_down]))
    q_x = list(reversed([float(v) for v in q_top_down]))

    def add(i: int, j: int, v: float):
        K[i][j] += float(v)

    for e in range(n - 1):
        L = abs(float(z_x[e + 1]) - float(z_x[e]))
        if L <= 1.0e-12:
            L = H / max(n - 1, 1)
        ke = EI / (L ** 3)
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

    # Elastic base restraints. Translation is now controlled by k_y rather than fixed.
    K[0][0] += k_y
    K[1][1] += k_theta

    w_ref = list(w_reference_top_down or [0.0 for _ in z_top_down])
    clean = normalize_supports(supports)
    reactions: list[dict[str, float | str]] = []
    for s in clean:
        z0 = float(s.get("z", 0.0))
        j_top = _support_node_index_top_down(z_top_down, z0)
        j = n - 1 - j_top
        wi = float(w_ref[j_top]) if j_top < len(w_ref) else 0.0
        kt, f0, force, status = _support_status_from_displacement(s, wi)
        dof = 2 * j
        if kt > 0.0:
            K[dof][dof] += kt
        if abs(f0) > 0.0:
            P[dof] += f0
        elif kt <= 0.0 and abs(force) > 0.0:
            P[dof] += force
        theta_deg = float(s.get("theta_deg", 0.0) or 0.0)
        cth = max(1.0e-12, abs(math.cos(math.radians(theta_deg))))
        cap = max(0.0, float(s.get("cap", 0.0) or 0.0))
        axial = abs(force) / cth
        reactions.append({
            "type": str(s.get("type", "support")),
            "code": str(s.get("code", "S")),
            "z": z0,
            "node_z": float(z_top_down[j_top]),
            "w_reference": wi,
            "theta_deg": theta_deg,
            "k": float(s.get("k", 0.0) or 0.0),
            "cap": cap,
            "prestress": float(s.get("prestress", 0.0) or 0.0),
            "L": float(s.get("L", 0.0) or 0.0),
            "install_w": float(s.get("install_w", 0.0) or 0.0),
            "kt_horizontal": kt,
            "Fh": force,
            "axial": axial,
            "util": abs(axial) / cap if cap > 0.0 else 0.0,
            "status": status,
        })

    free = list(range(ndof))
    A = [[K[i][j] for j in free] for i in free]
    b = [P[i] for i in free]
    sol_free = _dense_solve(A, b)
    U = [0.0 for _ in range(ndof)]
    for idx, dof in enumerate(free):
        U[dof] = sol_free[idx]
    w_base_to_top = [U[2 * i] for i in range(n)]
    return list(reversed(w_base_to_top)), reactions, k_theta, k_y
