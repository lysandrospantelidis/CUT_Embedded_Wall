# -*- coding: utf-8 -*-
"""CUT Embedded Wall — solver dispatcher v6.

GUI-facing module only. It dispatches to one independent solver file per method.
No GUI code and no solver equations are implemented here.
"""
from __future__ import annotations

from cut_embedded_wall_solvers.common import (
    SoilLayer, GeometryInput, SideInput, SeismicInput, MovementInput,
    WallStiffnessInput, SolverControls, ReinforcementSupport,
    ModelInput, SolverResult, SolverMode, make_placeholder_result,
)
from cut_embedded_wall_solvers.fixed_base_closed_form import solve_fixed_base_only_bending
from cut_embedded_wall_solvers.fixed_base_ode import solve_fixed_base_differential_equation
from cut_embedded_wall_solvers.base_spring_ode import solve_base_spring_differential_equation
from cut_embedded_wall_solvers.no_bending import solve_no_bending, compute_work_heatmap as compute_no_bending_work_heatmap
from cut_embedded_wall_solvers.general_case import solve_general_case, compute_work_heatmap as compute_general_work_heatmap
from cut_embedded_wall_solvers.general_case_variational_beam import (
    solve_general_case_variational_beam,
    compute_work_heatmap as compute_general_variational_work_heatmap,
)


def solve(model: ModelInput, progress_callback=None) -> SolverResult:
    mode = model.solver_mode
    if getattr(model, "reinforcement_supports", None) and mode not in {"fixed_base_differential_equation", "base_spring_differential_equation", "general_case_variational_beam"}:
        raise ValueError(
            "Reinforcement/supports require a differential-equation solver with nodal support formulation. "
            "Closed-form, rigid-wall and legacy general-case solvers are disabled for reinforcement until their nonlinear support formulation is implemented."
        )
    if mode == "fixed_base_only_bending":
        return solve_fixed_base_only_bending(model)
    if mode == "fixed_base_differential_equation":
        return solve_fixed_base_differential_equation(model)
    if mode == "base_spring_differential_equation":
        return solve_base_spring_differential_equation(model)
    if mode == "no_bending":
        return solve_no_bending(model)
    if mode == "general_case":
        return solve_general_case(model, progress_callback=progress_callback)
    if mode == "general_case_variational_beam":
        return solve_general_case_variational_beam(model, progress_callback=progress_callback)
    raise ValueError(f"Unknown solver mode: {mode!r}")


SOLVER_DISPLAY_NAMES: dict[str, SolverMode] = {
    "Flexible wall - Fixed base (closed-form bending)": "fixed_base_only_bending",
    "Flexible wall - Fixed base (differential equation)": "fixed_base_differential_equation",
    "Flexible wall - Base spring (differential equation)": "base_spring_differential_equation",
    "Rigid wall (no bending)": "no_bending",

    "Any wall (general case)": "general_case",

    # New flagship solver
    "Any wall (general variational)": "general_case_variational_beam",
    "General variational": "general_case_variational_beam",

    # Backward-compatible aliases
    "Any wall (general case variational)": "general_case_variational_beam",
    "General case variational": "general_case_variational_beam",
    "General case — variational beam": "general_case_variational_beam",

    "Fixed base (closed-form bending)": "fixed_base_only_bending",
    "Fixed base (differential equation)": "fixed_base_differential_equation",
    "Base spring (differential equation)": "base_spring_differential_equation",
    "No bending": "no_bending",
    "General case": "general_case",
}
