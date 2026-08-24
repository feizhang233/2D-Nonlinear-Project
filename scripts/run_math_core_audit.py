"""Run the Math-Core-Guide V00-V09 examples against the current project.

This is a source-tree audit tool.  It deliberately reuses the verification
scenario builders under ``tests/verification`` while all solves and element
evaluations go through the public ``nonlinear_core`` API.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from nonlinear_core import (
    AdapterState,
    LineSearchMethod,
    LineSearchOptions,
    ModelFamily,
    ModelResponse,
    StepStatus,
    __version__,
    apply_line_search,
    begin_step,
    build_equilibrium,
    commit,
    evaluate_total_lagrangian_q4,
    evaluate_trial,
    get_adapter,
    initialize_state,
    rollback,
    solve_arc_length,
    solve_constrained_correction,
    solve_displacement_control,
    solve_load_control,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "validation" / "math-core-audit.json"


def _load_verification_module(filename: str) -> ModuleType:
    path = ROOT / "tests" / "verification" / filename
    module_name = f"_math_core_audit_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verification scenario: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _max_abs(actual: Any, reference: Any) -> float:
    return float(
        np.max(np.abs(np.asarray(actual, dtype=float) - np.asarray(reference, dtype=float)))
    )


def _relative_error(actual: np.ndarray, reference: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(reference)), np.finfo(float).tiny)
    return float(np.linalg.norm(actual - reference) / denominator)


def _v00() -> dict[str, Any]:
    coordinates = np.asarray([[0.0, 0.0], [2.0, 0.0], [2.2, 1.0], [0.1, 1.1]])
    angle = np.deg2rad(30.0)
    rotation = np.asarray([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    right_cauchy_green = rotation.T @ rotation
    green_lagrange = 0.5 * (right_cauchy_green - np.eye(2))
    displacement = (coordinates @ rotation.T - coordinates).ravel()
    response = evaluate_total_lagrangian_q4(
        coordinates,
        displacement,
        young=210.0e9,
        poisson=0.3,
        thickness=0.2,
        element_id="V00-Q4",
    )
    max_gauss_strain = max(
        float(np.max(np.abs(point["green_lagrange"]))) for point in response.gauss_points
    )
    deviations = {
        "abs_J_minus_1": abs(float(np.linalg.det(rotation)) - 1.0),
        "max_abs_C_minus_I": _max_abs(right_cauchy_green, np.eye(2)),
        "max_abs_analytic_E": float(np.max(np.abs(green_lagrange))),
        "abs_project_min_detF_minus_1": abs(float(response.min_det_f) - 1.0),
        "max_abs_project_gauss_E": max_gauss_strain,
        "project_internal_force_l2": float(np.linalg.norm(response.internal_force)),
        "abs_project_strain_energy": abs(float(response.strain_energy)),
    }
    passed = (
        deviations["abs_J_minus_1"] <= 3.0e-16
        and deviations["max_abs_C_minus_I"] <= 3.0e-16
        and deviations["max_abs_project_gauss_E"] <= 4.0e-16
        and deviations["project_internal_force_l2"] < 3.0e-6
        and deviations["abs_project_strain_energy"] < 1.0e-21
    )
    return {
        "id": "V00",
        "name": "finite rigid-rotation objectivity",
        "reference": {"J": 1.0, "C": np.eye(2).tolist(), "E": np.zeros((2, 2)).tolist()},
        "computed": {
            "rotation": rotation.tolist(),
            "J": float(np.linalg.det(rotation)),
            "C": right_cauchy_green.tolist(),
            "E": green_lagrange.tolist(),
            "project_min_detF": float(response.min_det_f),
            "project_internal_force_l2": float(np.linalg.norm(response.internal_force)),
            "project_strain_energy": float(response.strain_energy),
        },
        "deviation": deviations,
        "passed": passed,
        "interpretation": (
            "nonzero project force is constitutive-scale amplification of roundoff strain"
        ),
    }


def _linear_response(matrix: np.ndarray, force: np.ndarray, displacement: np.ndarray):
    return ModelResponse(
        internal_force=matrix @ displacement,
        tangent=matrix,
        external_force=force,
        external_tangent=None,
        trial_state=AdapterState(
            model_id="V01",
            model_family=ModelFamily.CONTINUUM,
            adapter_id="math-core-audit",
            core_package="analytic",
            core_version="1",
            state_id="trial",
        ),
        elements=(),
        strain_energy=float(0.5 * displacement @ matrix @ displacement),
    )


def _v01() -> dict[str, Any]:
    matrix = np.asarray([[4.0, 1.0], [1.0, 3.0]])
    force = np.asarray([1.0, 2.0])
    initial = np.zeros(2)
    correction = solve_constrained_correction(
        build_equilibrium(_linear_response(matrix, force, initial), {}),
        initial,
    )
    updated = initial + correction.correction
    final = build_equilibrium(_linear_response(matrix, force, updated), {})
    wrong = build_equilibrium(_linear_response(matrix, force, initial - correction.correction), {})
    reference_displacement = np.asarray([1.0 / 11.0, 7.0 / 11.0])
    reference_energy = 15.0 / 22.0
    deviations = {
        "max_abs_displacement": _max_abs(updated, reference_displacement),
        "residual_l2": float(np.linalg.norm(final.residual)),
        "abs_energy": abs(float(final.response.strain_energy) - reference_energy),
        "wrong_sign_residual_vs_2f": _max_abs(wrong.residual, 2.0 * force),
    }
    passed = correction.succeeded and max(deviations.values()) <= 5.0e-16
    return {
        "id": "V01",
        "name": "linear one-correction recovery and sign",
        "reference": {
            "displacement": reference_displacement.tolist(),
            "strain_energy": reference_energy,
            "wrong_sign_residual": (2.0 * force).tolist(),
        },
        "computed": {
            "displacement": updated.tolist(),
            "residual": final.residual.tolist(),
            "strain_energy": float(final.response.strain_energy),
            "wrong_sign_residual": wrong.residual.tolist(),
        },
        "deviation": deviations,
        "passed": passed,
        "interpretation": "project convention K*du=r is consistent; K*du=-r doubles the residual",
    }


def _polynomial_internal(displacement: np.ndarray) -> np.ndarray:
    u_1, u_2 = displacement
    return np.asarray([2.0 * u_1 + u_1**3 + u_2, u_1 + 3.0 * u_2 + 0.5 * u_2**3])


def _v02() -> dict[str, Any]:
    displacement = np.asarray([0.2, -0.4])
    direction = np.asarray([0.6, 0.8])
    internal = _polynomial_internal(displacement)
    tangent = np.asarray(
        [[2.0 + 3.0 * displacement[0] ** 2, 1.0], [1.0, 3.0 + 1.5 * displacement[1] ** 2]]
    )
    target = tangent @ direction
    steps = np.logspace(-2, -8, 7)
    analytic_errors = []
    for step in steps:
        difference = (
            _polynomial_internal(displacement + step * direction)
            - _polynomial_internal(displacement - step * direction)
        ) / (2.0 * step)
        analytic_errors.append(_relative_error(difference, target))

    coordinates = np.asarray([[0.0, 0.0], [2.0, 0.0], [2.2, 1.0], [0.1, 1.1]])
    element_displacement = np.asarray([0.0, 0.0, 0.08, -0.02, 0.12, 0.06, -0.01, 0.04])
    element_direction = np.asarray([0.2, -0.3, 0.4, 0.1, -0.2, 0.5, 0.3, -0.4])
    element_direction /= np.linalg.norm(element_direction)
    element_response = evaluate_total_lagrangian_q4(
        coordinates,
        element_displacement,
        young=10.0e6,
        poisson=0.25,
        thickness=0.2,
    )
    element_target = element_response.tangent @ element_direction
    project_errors = []
    for step in steps:
        plus = evaluate_total_lagrangian_q4(
            coordinates,
            element_displacement + step * element_direction,
            young=10.0e6,
            poisson=0.25,
            thickness=0.2,
        )
        minus = evaluate_total_lagrangian_q4(
            coordinates,
            element_displacement - step * element_direction,
            young=10.0e6,
            poisson=0.25,
            thickness=0.2,
        )
        difference = (plus.internal_force - minus.internal_force) / (2.0 * step)
        project_errors.append(_relative_error(difference, element_target))

    analytic_best = int(np.argmin(analytic_errors))
    project_best = int(np.argmin(project_errors))
    deviations = {
        "max_abs_internal_force": _max_abs(internal, [0.008, -1.032]),
        "max_abs_tangent": _max_abs(tangent, [[2.12, 1.0], [1.0, 3.24]]),
        "max_abs_directional_derivative": _max_abs(target, [2.072, 3.192]),
        "analytic_best_relative_error": analytic_errors[analytic_best],
        "project_best_relative_error": project_errors[project_best],
    }
    passed = (
        deviations["max_abs_internal_force"] <= 3.0e-16
        and deviations["max_abs_tangent"] <= 5.0e-16
        and deviations["max_abs_directional_derivative"] <= 5.0e-16
        and 0 < analytic_best < len(steps) - 1
        and 0 < project_best < len(steps) - 1
        and project_errors[project_best] < 1.0e-8
        and project_errors[0] > 100.0 * project_errors[project_best]
        and project_errors[-1] > project_errors[project_best]
    )
    return {
        "id": "V02",
        "name": "consistent-tangent directional derivative",
        "reference": {
            "internal_force": [0.008, -1.032],
            "tangent": [[2.12, 1.0], [1.0, 3.24]],
            "tangent_times_direction": [2.072, 3.192],
        },
        "computed": {
            "internal_force": internal.tolist(),
            "tangent": tangent.tolist(),
            "tangent_times_direction": target.tolist(),
            "step_sizes": steps.tolist(),
            "analytic_relative_errors": analytic_errors,
            "project_q4_relative_errors": project_errors,
            "analytic_best_h": float(steps[analytic_best]),
            "project_best_h": float(steps[project_best]),
        },
        "deviation": deviations,
        "passed": passed,
        "interpretation": (
            "the error valley is truncation-error descent followed by floating-point growth"
        ),
    }


def _v03(module: ModuleType) -> dict[str, Any]:
    adapter = module.ImperfectColumnAdapter()
    model = module._model()
    initial = module._initial_column_state(adapter, model, theta=0.01)
    solution = solve_load_control(adapter, model, initial_state=initial)
    step = solution.result.steps[0]
    project_theta = [
        record.diagnostics["displacement"][module.ACTIVE_DOF] for record in step.iterations
    ]
    project_r = [record.diagnostics["residual"][module.ACTIVE_DOF] for record in step.iterations]
    project_math_r = [-value for value in project_r]
    project_tangent = [
        record.diagnostics["effective_tangent_diagonal"][module.ACTIVE_DOF]
        for record in step.iterations
    ]

    theta = 0.01
    reference_theta = []
    reference_r = []
    reference_tangent = []
    for _ in range(4):
        residual = 10.0 * (theta - 0.01) - 9.0 * math.sin(theta)
        tangent = 10.0 - 9.0 * math.cos(theta)
        reference_theta.append(theta)
        reference_r.append(residual)
        reference_tangent.append(tangent)
        theta -= residual / tangent
    final_theta = float(solution.committed_state.displacement[module.ACTIVE_DOF])
    transverse = 10.0 * math.sin(final_theta)
    deviations = {
        "max_abs_theta_history": _max_abs(project_theta, reference_theta),
        "max_abs_math_residual_history": _max_abs(project_math_r, reference_r),
        "max_abs_tangent_history": _max_abs(project_tangent, reference_tangent),
        "abs_final_theta": abs(final_theta - reference_theta[-1]),
        "abs_transverse_vs_guide": abs(transverse - 0.9840486391),
    }
    passed = solution.succeeded and max(deviations.values()) <= 5.0e-10
    return {
        "id": "V03",
        "name": "imperfect-column full Newton history",
        "reference": {
            "theta": reference_theta,
            "R_fint_minus_fext": reference_r,
            "tangent": reference_tangent,
            "guide_transverse_displacement": 0.9840486391,
        },
        "computed": {
            "theta": project_theta,
            "project_r_fext_minus_fint": project_r,
            "reported_R_fint_minus_fext": project_math_r,
            "tangent": project_tangent,
            "final_theta": final_theta,
            "transverse_displacement": transverse,
        },
        "deviation": deviations,
        "passed": passed,
        "interpretation": "the guide's V03 R is the negative of the project's global residual r",
    }


def _v04(module_v05: ModuleType, module_v08: ModuleType) -> dict[str, Any]:
    cosine = 0.6 ** (1.0 / 3.0)
    theta_limit = math.acos(cosine)
    displacement_limit = 8.0 - 10.0 * math.sin(theta_limit)
    force_limit = 5.0 * math.tan(theta_limit) * (10.0 * cosine - 6.0)

    displacement_model = module_v05._model(
        target=module_v05.DofRef(node_id="N2", dof=module_v05.Dof.UX),
        increment=-1.0,
    )
    displacement_adapter = module_v05.V04LimitPointAdapter()
    displacement_initial = module_v05._initial_state(
        displacement_adapter,
        displacement_model,
        control_index=module_v05.FREE_DOF,
        value=8.0,
    )
    displacement_solution = solve_displacement_control(
        displacement_adapter,
        displacement_model,
        number_of_steps=6,
        initial_state=displacement_initial,
    )
    displacement_path = [
        {
            "v": float(step.response["control_displacement"]),
            "force": float(step.response["controller_reaction"]),
        }
        for step in displacement_solution.result.steps
    ]

    arc_model = module_v08._arc_model(
        radius=0.75,
        min_radius=0.046875,
        max_radius=0.75,
        max_steps=30,
    )
    arc_adapter = module_v08.V04ArcAdapter()
    arc_initial = module_v08._initial_state(
        arc_adapter,
        arc_model,
        values={module_v08.ACTIVE_DOF: 8.0},
        load_factor=0.0,
    )
    arc_solution = solve_arc_length(
        arc_adapter,
        arc_model,
        number_of_steps=20,
        initial_state=arc_initial,
    )
    accepted = [step for step in arc_solution.result.steps if step.status is StepStatus.ACCEPTED]
    arc_loads = [float(step.load_factor) for step in accepted]
    arc_displacements = [
        float(step.response["displacement"][module_v08.ACTIVE_DOF]) for step in accepted
    ]
    deviations = {
        "abs_theta_vs_guide": abs(theta_limit - 0.5671552863),
        "abs_v_vs_guide": abs(displacement_limit - 2.6276509877),
        "abs_force_vs_guide": abs(force_limit - 7.7528728303),
        "arc_peak_relative": abs(max(arc_loads) - force_limit) / force_limit,
    }
    passed = (
        displacement_solution.succeeded
        and arc_solution.succeeded
        and displacement_path[-2]["v"] > displacement_limit > displacement_path[-1]["v"]
        and displacement_path[-1]["force"] < displacement_path[-2]["force"]
        and min(arc_displacements) < displacement_limit
        and arc_loads[-1] < max(arc_loads)
        and deviations["arc_peak_relative"] < 2.0e-3
        and deviations["abs_force_vs_guide"] < 1.0e-10
    )
    return {
        "id": "V04",
        "name": "limit point and control boundary",
        "reference": {
            "cos_theta": cosine,
            "theta": theta_limit,
            "v": displacement_limit,
            "force": force_limit,
        },
        "computed": {
            "displacement_control_path": displacement_path,
            "arc_length_peak_force": max(arc_loads),
            "arc_length_last_force": arc_loads[-1],
            "arc_length_last_v": arc_displacements[-1],
        },
        "deviation": deviations,
        "passed": passed,
        "interpretation": (
            "load control loses a local parameter at the zero tangent; "
            "the expected failure is not a solver defect"
        ),
    }


def _v05(module: ModuleType) -> dict[str, Any]:
    target = module.DofRef(node_id="N2", dof=module.Dof.UY)
    model = module._model(target=target, increment=0.1)
    solution = solve_displacement_control(module.V05Adapter(), model)
    step = solution.result.steps[0]
    free = float(solution.committed_state.displacement[module.FREE_DOF])
    control = float(solution.committed_state.displacement[module.CONTROL_DOF])
    reaction = float(step.response["controller_reaction"])
    deviations = {
        "abs_free_increment": abs(free + 0.025),
        "abs_control_increment": abs(control - 0.1),
        "abs_controller_reaction": abs(reaction - 0.275),
        "free_residual_l2": float(np.linalg.norm(step.response["free_residual"])),
    }
    return {
        "id": "V05",
        "name": "displacement-control block solve and reaction",
        "reference": {"du1": -0.025, "du2": 0.1, "controller_reaction": 0.275},
        "computed": {"du1": free, "du2": control, "controller_reaction": reaction},
        "deviation": deviations,
        "passed": solution.succeeded and max(deviations.values()) < 1.0e-14,
        "interpretation": "the constrained row is retained until controller reaction recovery",
    }


def _v06(module: ModuleType) -> dict[str, Any]:
    current = np.zeros(2)
    direction = np.ones(2)
    result = apply_line_search(
        module._v06_at(current),
        module._v06_at,
        current,
        direction,
        LineSearchOptions(
            enabled=True,
            method=LineSearchMethod.ORTHOGONALITY,
            max_iterations=12,
        ),
        conservative=True,
    )
    accepted = current + result.alpha * direction
    equilibrium = module._v06_at(accepted)
    phi_prime = 3.0 * result.alpha - 5.0 + 2.0 * result.alpha**3
    phi_second = 3.0 + 6.0 * result.alpha**2
    deviations = {
        "abs_alpha": abs(result.alpha - 1.0),
        "abs_phi_prime": abs(phi_prime),
        "abs_directional_project_residual": abs(float(direction @ equilibrium.free_residual)),
        "abs_phi_second_minus_9": abs(phi_second - 9.0),
    }
    return {
        "id": "V06",
        "name": "line-search orthogonality",
        "reference": {"alpha": 1.0, "phi_prime": 0.0, "phi_second": 9.0},
        "computed": {
            "alpha": float(result.alpha),
            "accepted_position": accepted.tolist(),
            "phi_prime": phi_prime,
            "phi_second": phi_second,
            "directional_project_residual": float(direction @ equilibrium.free_residual),
        },
        "deviation": deviations,
        "passed": result.accepted and max(deviations.values()) <= 1.0e-14,
        "interpretation": (
            "the project residual has the opposite sign to the potential gradient, "
            "but both vanish at the accepted root"
        ),
    }


def _v07(module: ModuleType) -> dict[str, Any]:
    model = module._frame_model()
    adapter = module.HistoryAdapter()
    committed = initialize_state(adapter, model)
    size = len(adapter.dof_map(model))
    failed_context = begin_step(
        committed,
        target_load_factor=1.0,
        predictor_displacement=module._trial_vector(size, 0.5),
    )
    failed = evaluate_trial(failed_context, adapter, model, iteration_index=4)
    restored = rollback(failed_context, failed.state)
    retry_context = begin_step(
        restored,
        target_load_factor=0.5,
        predictor_displacement=module._trial_vector(size, 0.3),
        attempt_index=1,
    )
    retry = evaluate_trial(retry_context, adapter, model, iteration_index=2)
    committed_retry = commit(retry_context, retry.state, converged=True)
    direct_context = begin_step(
        committed,
        target_load_factor=0.5,
        predictor_displacement=module._trial_vector(size, 0.3),
    )
    direct = evaluate_trial(direct_context, adapter, model, iteration_index=2)
    deviations = {
        "abs_failed_q": abs(float(failed.state.history["q"]) - 0.5),
        "abs_failed_force": abs(float(failed.response.internal_force[0]) - 0.75),
        "abs_rollback_q": abs(float(restored.history["q"]) - 0.2),
        "abs_retry_q": abs(float(retry.state.history["q"]) - 0.3),
        "abs_retry_force": abs(float(retry.response.internal_force[0]) - 0.39),
        "abs_committed_q": abs(float(committed_retry.history["q"]) - 0.3),
        "retry_vs_direct_force": _max_abs(
            retry.response.internal_force, direct.response.internal_force
        ),
    }
    return {
        "id": "V07",
        "name": "trial, rollback, and commit isolation",
        "reference": {
            "failed_trial": {"q": 0.5, "force": 0.75},
            "rollback_q": 0.2,
            "retry": {"q": 0.3, "force": 0.39},
            "committed_q": 0.3,
        },
        "computed": {
            "failed_trial": {
                "q": float(failed.state.history["q"]),
                "force": float(failed.response.internal_force[0]),
            },
            "rollback_q": float(restored.history["q"]),
            "retry": {
                "q": float(retry.state.history["q"]),
                "force": float(retry.response.internal_force[0]),
            },
            "committed_q": float(committed_retry.history["q"]),
        },
        "deviation": deviations,
        "passed": max(deviations.values()) <= 1.0e-15
        and retry.state.to_payload() == direct.state.to_payload(),
        "interpretation": "the failed q=0.5 trial never enters the immutable committed baseline",
    }


def _v08(module: ModuleType) -> dict[str, Any]:
    model = module._arc_model(radius=0.1)
    solution = solve_arc_length(module.OneDofAdapter(), model)
    step = solution.result.steps[0]
    predictor = 0.1 / math.sqrt(2.0)
    displacement = float(solution.committed_state.displacement[module.ACTIVE_DOF])
    load_factor = float(solution.committed_state.load_factor)
    limit_displacement = 1.0 / math.sqrt(3.0)
    limit_load = 2.0 / (3.0 * math.sqrt(3.0))
    deviations = {
        "abs_predictor_displacement": abs(
            float(step.response["predictor_displacement_increment"][module.ACTIVE_DOF]) - predictor
        ),
        "abs_predictor_load": abs(float(step.response["predictor_load_increment"]) - predictor),
        "abs_intersection_u_vs_guide": abs(displacement - 0.0708885680),
        "abs_intersection_lambda_vs_guide": abs(load_factor - 0.0705323396),
        "abs_equilibrium": abs(load_factor - displacement + displacement**3),
        "abs_arc_constraint": abs(displacement**2 + load_factor**2 - 0.01),
        "abs_limit_u_vs_guide": abs(limit_displacement - 0.5773502692),
        "abs_limit_lambda_vs_guide": abs(limit_load - 0.3849001795),
    }
    return {
        "id": "V08",
        "name": "one-DOF spherical arc length",
        "reference": {
            "predictor_du": predictor,
            "predictor_dlambda": predictor,
            "intersection_u": 0.0708885680,
            "intersection_lambda": 0.0705323396,
            "limit_u": limit_displacement,
            "limit_lambda": limit_load,
        },
        "computed": {
            "predictor_du": float(
                step.response["predictor_displacement_increment"][module.ACTIVE_DOF]
            ),
            "predictor_dlambda": float(step.response["predictor_load_increment"]),
            "intersection_u": displacement,
            "intersection_lambda": load_factor,
            "equilibrium_residual": load_factor - displacement + displacement**3,
            "arc_constraint_residual": displacement**2 + load_factor**2 - 0.01,
            "root_candidates_first_iteration": len(step.response["root_history"][0]["candidates"]),
        },
        "deviation": deviations,
        "passed": solution.succeeded and max(deviations.values()) < 2.0e-10,
        "interpretation": (
            "reported guide values are rounded; simultaneous equilibrium and arc residuals "
            "are near machine zero"
        ),
    }


def _v09(
    frame: ModuleType, continuum: ModuleType, plate: ModuleType, shell: ModuleType
) -> dict[str, Any]:
    load_model = frame._load_model(step=0.1, max_steps=1)
    adapter = get_adapter(load_model)
    load_solution = solve_load_control(adapter, load_model, target_load_factor=0.1)
    load_displacement = float(load_solution.committed_state.displacement[frame.APEX_UY])
    displacement_solution = solve_displacement_control(
        adapter,
        frame._displacement_model(load_displacement),
    )
    reaction = float(displacement_solution.result.steps[0].response["controller_reaction"])
    displacement_lambda = reaction / -1000.0
    radius = math.hypot(load_displacement, 1.0e-5 * 1000.0 * 0.1)
    arc_model = frame._arc_model(radius=radius, max_steps=1)
    arc_solution = solve_arc_length(get_adapter(arc_model), arc_model, number_of_steps=1)
    arc_displacement = float(arc_solution.committed_state.displacement[frame.APEX_UY])
    arc_lambda = float(arc_solution.committed_state.load_factor)

    frame_peaks = []
    for step_size in (0.02, 0.01, 0.005):
        model = frame._displacement_model(-step_size)
        solution = solve_displacement_control(
            get_adapter(model),
            model,
            number_of_steps=round(0.12 / step_size),
        )
        frame_peaks.append(
            max(-float(item.response["controller_reaction"]) for item in solution.result.steps)
        )

    limit_model = frame._load_model(step=0.05, max_steps=20)
    failed_load = solve_load_control(
        get_adapter(limit_model),
        limit_model,
        target_load_factor=0.31,
    )
    descending_model = frame._arc_model(radius=0.01, max_steps=20)
    descending = solve_arc_length(
        get_adapter(descending_model),
        descending_model,
        number_of_steps=20,
    )
    descending_loads = [
        float(item.load_factor)
        for item in descending.result.steps
        if item.status is StepStatus.ACCEPTED
    ]

    continuum_steps = []
    for step_size in (0.5, 0.25, 0.125):
        model = continuum._tension_model(2, step_size)
        solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)
        continuum_steps.append(
            continuum._right_edge_displacement(model, solution.committed_state.displacement)
        )
    continuum_mesh = []
    continuum_detf = []
    for divisions in (1, 2, 4):
        model = continuum._tension_model(divisions)
        solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)
        continuum_mesh.append(
            continuum._right_edge_displacement(model, solution.committed_state.displacement)
        )
        continuum_detf.append(float(solution.final_response.min_det_f))

    plate_steps = []
    for step_size in (0.5, 0.25, 0.125):
        model = plate._plate_model(2, step_size)
        solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)
        plate_steps.append(
            plate._free_edge_displacement(model, solution.committed_state.displacement)
        )
    plate_mesh = []
    for divisions in (1, 2, 4):
        model = plate._plate_model(divisions)
        solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)
        plate_mesh.append(
            plate._free_edge_displacement(model, solution.committed_state.displacement)
        )

    shell_scaling = []
    shell_coordinates = [
        np.asarray([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 1.0, 0.0], [0.0, 1.0, 0.0]]),
        np.asarray([[0.0, 0.0, 0.0], [2.0, 0.4, 0.0], [2.2, 1.7, 0.0], [-0.3, 1.4, 0.0]]),
    ]
    for label, coordinates in zip(("regular", "distorted"), shell_coordinates, strict=True):
        displacement = shell._patch_displacement(coordinates)
        thick = shell.evaluate_corotational_flat_shell(
            coordinates,
            displacement,
            young=21.0e6,
            poisson=0.3,
            thickness=0.2,
            alpha_d=1.0e-4,
        )
        thin = shell.evaluate_corotational_flat_shell(
            coordinates,
            displacement,
            young=21.0e6,
            poisson=0.3,
            thickness=0.02,
            alpha_d=1.0e-4,
        )
        shell_scaling.append(
            {
                "geometry": label,
                "min_detJ_thick": float(thick.min_det_j),
                "min_detJ_thin": float(thin.min_det_j),
                "membrane_energy_ratio_thin_over_thick": float(
                    thin.membrane_energy / thick.membrane_energy
                ),
                "bending_energy_ratio_thin_over_thick": float(
                    thin.bending_energy / thick.bending_energy
                ),
                "shear_energy_ratio_thin_over_thick": (
                    None
                    if thick.shear_energy <= 1.0e-20
                    else float(thin.shear_energy / thick.shear_energy)
                ),
            }
        )

    deviations = {
        "stable_load_vs_displacement_lambda": abs(0.1 - displacement_lambda),
        "stable_load_vs_arc_lambda": abs(0.1 - arc_lambda),
        "stable_load_vs_arc_displacement": abs(load_displacement - arc_displacement),
        "frame_peak_spread": max(frame_peaks) - min(frame_peaks),
        "continuum_step_spread": max(continuum_steps) - min(continuum_steps),
        "continuum_mesh_spread": max(continuum_mesh) - min(continuum_mesh),
        "plate_step_spread": max(plate_steps) - min(plate_steps),
        "plate_refinement_last_change_ratio": abs(plate_mesh[2] - plate_mesh[1])
        / abs(plate_mesh[1] - plate_mesh[0]),
        "shell_max_membrane_scaling_error": max(
            abs(item["membrane_energy_ratio_thin_over_thick"] - 0.1) for item in shell_scaling
        ),
        "shell_max_bending_scaling_error": max(
            abs(item["bending_energy_ratio_thin_over_thick"] - 0.001) for item in shell_scaling
        ),
    }
    passed = (
        load_solution.succeeded
        and displacement_solution.succeeded
        and arc_solution.succeeded
        and deviations["stable_load_vs_displacement_lambda"] < 2.0e-12
        and deviations["stable_load_vs_arc_lambda"] < 2.0e-11
        and deviations["frame_peak_spread"] < 1.0
        and not failed_load.succeeded
        and float(failed_load.committed_state.load_factor) == 0.25
        and descending.succeeded
        and max(descending_loads) > 0.295
        and descending_loads[-1] < 0.01
        and deviations["continuum_step_spread"] < 1.0e-10
        and deviations["continuum_mesh_spread"] < 1.0e-10
        and deviations["plate_step_spread"] < 1.0e-10
        and deviations["plate_refinement_last_change_ratio"] < 1.0
        and deviations["shell_max_membrane_scaling_error"] < 2.0e-12
        and deviations["shell_max_bending_scaling_error"] < 2.0e-12
    )
    return {
        "id": "V09",
        "name": "integrated two-dimensional model evidence",
        "reference": {
            "stable_frame_point": {"lambda": 0.1, "apex_uy": -0.01480115361358},
            "continuum_endpoint": 0.1618288167,
            "plate_two_by_two_endpoint": -0.03811696908,
            "shell_thickness_scaling": {"membrane": 0.1, "bending": 0.001},
        },
        "computed": {
            "stable_frame_controls": {
                "load": {"lambda": 0.1, "apex_uy": load_displacement},
                "displacement": {
                    "lambda_from_reaction": displacement_lambda,
                    "apex_uy": load_displacement,
                },
                "arc_length": {"lambda": arc_lambda, "apex_uy": arc_displacement},
            },
            "frame_limit_loads_by_displacement_step": dict(
                zip(("0.02", "0.01", "0.005"), frame_peaks, strict=True)
            ),
            "frame_load_control_above_limit": {
                "requested_lambda": 0.31,
                "succeeded": failed_load.succeeded,
                "last_committed_lambda": float(failed_load.committed_state.load_factor),
                "failure_code": failed_load.result.failures[-1].code.value,
            },
            "frame_arc_length_descending": {
                "accepted_steps": len(descending_loads),
                "max_lambda": max(descending_loads),
                "last_lambda": descending_loads[-1],
            },
            "continuum_endpoints_by_step": dict(
                zip(("0.5", "0.25", "0.125"), continuum_steps, strict=True)
            ),
            "continuum_endpoints_by_mesh": dict(zip(("1", "2", "4"), continuum_mesh, strict=True)),
            "continuum_min_detF_by_mesh": dict(zip(("1", "2", "4"), continuum_detf, strict=True)),
            "plate_endpoints_by_step": dict(
                zip(("0.5", "0.25", "0.125"), plate_steps, strict=True)
            ),
            "plate_endpoints_by_mesh": dict(zip(("1", "2", "4"), plate_mesh, strict=True)),
            "shell_thickness_scaling": shell_scaling,
        },
        "deviation": deviations,
        "passed": passed,
        "interpretation": (
            "step/mesh spreads measure discretization sensitivity; expected control failures "
            "are retained as evidence"
        ),
    }


def build_audit() -> dict[str, Any]:
    v03 = _load_verification_module("test_v03_newton_load_control.py")
    v05 = _load_verification_module("test_v05_displacement_control.py")
    v06 = _load_verification_module("test_v06_line_search.py")
    v07 = _load_verification_module("test_v07_state_transactions.py")
    v08 = _load_verification_module("test_v08_arc_length.py")
    frame = _load_verification_module("test_v09_corotational_frame.py")
    continuum = _load_verification_module("test_v09_total_lagrangian_continuum.py")
    plate = _load_verification_module("test_v09_von_karman_plate.py")
    shell = _load_verification_module("test_v09_corotational_shell.py")
    cases = [
        _v00(),
        _v01(),
        _v02(),
        _v03(v03),
        _v04(v05, v08),
        _v05(v05),
        _v06(v06),
        _v07(v07),
        _v08(v08),
        _v09(frame, continuum, plate, shell),
    ]
    failed = [case["id"] for case in cases if not case["passed"]]
    return {
        "artifact": "math-core-audit",
        "artifact_version": "1.0.0",
        "solver_version": __version__,
        "residual_convention": "r = f_ext - f_int; K_t * du = r",
        "oracle": "tests/verification",
        "status": "passed" if not failed else "failed",
        "failed_cases": failed,
        "cases": cases,
    }


def _render(document: dict[str, Any]) -> str:
    return f"{json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)}\n"


def _first_semantic_difference(checked: Any, fresh: Any, *, path: str = "$") -> str | None:
    """Allow harmless cross-platform floating variation, but not structural drift."""

    if isinstance(checked, bool) or isinstance(fresh, bool):
        return None if checked is fresh else path
    if isinstance(checked, (int, float)) and isinstance(fresh, (int, float)):
        return (
            None
            if math.isclose(float(checked), float(fresh), rel_tol=1.0e-7, abs_tol=1.0e-12)
            else path
        )
    if isinstance(checked, dict) and isinstance(fresh, dict):
        if checked.keys() != fresh.keys():
            return path
        for name in checked:
            difference = _first_semantic_difference(
                checked[name],
                fresh[name],
                path=f"{path}.{name}",
            )
            if difference is not None:
                return difference
        return None
    if isinstance(checked, list) and isinstance(fresh, list):
        if len(checked) != len(fresh):
            return path
        for index, (left, right) in enumerate(zip(checked, fresh, strict=True)):
            difference = _first_semantic_difference(
                left,
                right,
                path=f"{path}[{index}]",
            )
            if difference is not None:
                return difference
        return None
    return None if checked == fresh else path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="compare a fresh run with checked evidence"
    )
    args = parser.parse_args()
    document = build_audit()
    if document["status"] != "passed":
        raise SystemExit(f"Math-core audit failed: {document['failed_cases']}")
    if args.check:
        if not OUTPUT.exists():
            raise SystemExit(f"missing math-core audit evidence: {OUTPUT.relative_to(ROOT)}")
        checked = json.loads(OUTPUT.read_text(encoding="utf-8"))
        difference = _first_semantic_difference(checked, document)
        if difference is not None:
            raise SystemExit(
                f"stale math-core audit evidence: {OUTPUT.relative_to(ROOT)} at {difference}"
            )
        print("Math-core audit: passed and evidence is current")
        return
    rendered = _render(document)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"Math-core audit: passed ({len(document['cases'])} cases)")
    print(OUTPUT)


if __name__ == "__main__":
    main()
