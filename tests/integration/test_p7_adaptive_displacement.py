"""P7 adaptive increment growth remains compatible with the P6 four-core path."""

from __future__ import annotations

from pathlib import Path

import pytest

from nonlinear_core import (
    AnalysisOptions,
    ControlMethod,
    DisplacementControlOptions,
    SolveStatus,
    StepControlOptions,
    get_adapter,
    solve_adaptive_displacement_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "examples" / "adapters" / "frame-linear.json"


def test_displacement_control_growth_uses_scaled_increment_bounds():
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    model = result.model
    target = model.free_dof_refs()[0]
    analysis = AnalysisOptions(
        control_method=ControlMethod.DISPLACEMENT,
        displacement_control=DisplacementControlOptions(target=target, increment=1.0e-6),
        max_iterations=10,
        step_control=StepControlOptions(
            initial_step=0.1,
            min_step=0.05,
            max_step=0.2,
            max_steps=3,
            target_iterations=2,
            growth_factor=2.0,
        ),
    )
    model = model.model_copy(update={"analysis": analysis})

    solution = solve_adaptive_displacement_control(
        get_adapter(model),
        model,
        number_of_steps=3,
    )

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert [step.response["adaptive_step_size"] for step in solution.result.steps] == pytest.approx(
        [1.0e-6, 2.0e-6, 2.0e-6]
    )
    assert [
        step.response["control_displacement"] for step in solution.result.steps
    ] == pytest.approx([1.0e-6, 3.0e-6, 5.0e-6])
    assert solution.result.metadata["growths"] == 1
