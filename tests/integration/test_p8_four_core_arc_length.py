"""P8 integration: spherical arc length remains adapter-independent."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AnalysisOptions,
    ArcLengthOptions,
    ControlMethod,
    SolveStatus,
    StepControlOptions,
    StepStatus,
    ToleranceOptions,
    get_adapter,
    solve_arc_length,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "tests" / "fixtures" / "adapters"
FILES = (
    "continuum-linear.json",
    "frame-linear.json",
    "plate-linear.json",
    "shell-linear.json",
)


def _model(filename: str):
    result = validate_model_json((EXAMPLES / filename).read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    analysis = AnalysisOptions(
        control_method=ControlMethod.ARC_LENGTH,
        arc_length=ArcLengthOptions(
            radius=0.1,
            min_radius=0.1,
            max_radius=0.1,
            beta=1.0e-3,
        ),
        max_iterations=8,
        tolerances=ToleranceOptions(
            residual=1.0e-9,
            displacement=1.0e-9,
            energy=1.0e-9,
            linear_solver=1.0e-10,
        ),
        step_control=StepControlOptions(
            initial_step=0.1,
            min_step=0.1,
            max_step=0.1,
            max_steps=2,
            growth_factor=1.0,
        ),
    )
    return result.model.model_copy(update={"analysis": analysis})


@pytest.mark.parametrize("filename", FILES)
def test_two_arc_steps_follow_each_native_linear_reference(filename: str):
    model = _model(filename)
    adapter = get_adapter(model)

    solution = solve_arc_length(adapter, model, number_of_steps=2)

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.committed_state is not None
    assert all(step.status is StepStatus.ACCEPTED for step in solution.result.steps)
    reference = adapter.native_reference(model)
    np.testing.assert_allclose(
        solution.committed_state.displacement,
        solution.committed_state.load_factor * reference.displacement,
        rtol=5.0e-9,
        atol=5.0e-11,
    )
    assert all(
        step.response["eta_arc"] <= model.analysis.tolerances.displacement
        for step in solution.result.steps
    )
    assert all(
        step.response["eta_R"] <= model.analysis.tolerances.residual
        for step in solution.result.steps
    )
