"""P5 load-control option and convergence-metric unit tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from nonlinear_core import (
    LineSearchOptions,
    MeritFunction,
    SolveStatus,
    build_equilibrium,
    convergence_metrics,
    get_adapter,
    solve_load_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "examples" / "adapters" / "frame-linear.json"


def _frame_model():
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    return result.model


def test_scaled_metrics_follow_the_math_guide_formulas():
    model = _frame_model()
    adapter = get_adapter(model)
    size = len(adapter.dof_map(model))
    current = np.zeros(size)
    response = adapter.evaluate(model, current, load_factor=0.25)
    evaluation = build_equilibrium(response, adapter.constraint_map(model))
    correction = np.linspace(0.0, 1.0e-4, size)

    metrics = convergence_metrics(evaluation, current, correction, model)
    free = evaluation.partition.free_dofs
    expected_residual = np.linalg.norm(evaluation.free_residual)
    expected_force_scale = (
        np.linalg.norm(response.external_force[free])
        + np.linalg.norm(response.internal_force[free])
        + model.analysis.tolerances.force_floor
    )
    expected_displacement_scale = model.analysis.tolerances.displacement_floor
    expected_energy = abs(correction[free] @ evaluation.free_residual)
    expected_energy_scale = (
        abs(correction[free] @ response.external_force[free])
        + model.analysis.tolerances.energy_floor
    )

    assert metrics.eta_residual == expected_residual / expected_force_scale
    assert (
        metrics.eta_displacement == np.linalg.norm(correction[free]) / expected_displacement_scale
    )
    assert metrics.eta_energy == expected_energy / expected_energy_scale


def test_load_control_records_p7_backtracking_merit_and_accepted_alpha():
    model = _frame_model()
    analysis = model.analysis.model_copy(update={"line_search": LineSearchOptions(enabled=True)})
    model = model.model_copy(update={"analysis": analysis})

    solution = solve_load_control(get_adapter(model), model, target_load_factor=0.1)

    assert solution.result.status is SolveStatus.SUCCEEDED
    first = solution.result.steps[0].iterations[0]
    assert first.accepted_alpha == 1.0
    assert first.diagnostics["line_search"]["enabled"] is True
    assert (
        first.diagnostics["line_search"]["merit_function"]
        == MeritFunction.RESIDUAL_L2_NONCONSERVATIVE.value
    )
    assert first.diagnostics["line_search"]["evaluations"] == 1
