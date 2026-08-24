"""P5 integration: fixed load steps solve all four P2 linear-core adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    IterationStatus,
    SolveStatus,
    StepStatus,
    get_adapter,
    solve_load_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "adapters"
FILES = (
    "continuum-linear.json",
    "frame-linear.json",
    "plate-linear.json",
    "shell-linear.json",
)


def _model(filename: str):
    result = validate_model_json((EXAMPLES / filename).read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    return result.model


@pytest.mark.parametrize("filename", FILES)
def test_fixed_load_steps_reach_scaled_native_reference(filename: str):
    model = _model(filename)
    adapter = get_adapter(model)
    solution = solve_load_control(adapter, model, target_load_factor=0.2)

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.result.failures == ()
    assert solution.committed_state is not None
    assert solution.committed_state.load_factor == pytest.approx(0.2)
    assert [step.load_factor for step in solution.result.steps] == pytest.approx([0.1, 0.2])
    assert [step.response["load_increment"] for step in solution.result.steps] == pytest.approx(
        [0.1, 0.1]
    )
    assert all(step.status is StepStatus.ACCEPTED for step in solution.result.steps)
    assert all(
        step.iterations[-1].status is IterationStatus.CONVERGED for step in solution.result.steps
    )
    assert all(step.response["tangent_assemblies"] == 2 for step in solution.result.steps)
    assert all(
        record.diagnostics["linear_relative_residual"] <= model.analysis.tolerances.linear_solver
        for step in solution.result.steps
        for record in step.iterations
    )
    reference = adapter.native_reference(model)
    np.testing.assert_allclose(
        solution.committed_state.displacement,
        0.2 * reference.displacement,
        rtol=3.0e-10,
        atol=3.0e-12,
    )
