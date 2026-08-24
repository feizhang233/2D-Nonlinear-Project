"""P6 integration: one prescribed free DOF works through every P2 adapter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AnalysisOptions,
    ControlMethod,
    DisplacementControlOptions,
    SolveStatus,
    get_adapter,
    solve_displacement_control,
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
    model = result.model
    target = model.free_dof_refs()[0]
    analysis = AnalysisOptions(
        control_method=ControlMethod.DISPLACEMENT,
        displacement_control=DisplacementControlOptions(
            target=target,
            increment=1.0e-6,
        ),
        max_iterations=model.analysis.max_iterations,
        tolerances=model.analysis.tolerances,
        step_control=model.analysis.step_control,
    )
    return model.model_copy(update={"analysis": analysis}), target


@pytest.mark.parametrize("filename", FILES)
def test_four_cores_prescribe_free_dof_and_recover_reaction(filename: str):
    model, target = _model(filename)
    adapter = get_adapter(model)
    dof_map = adapter.dof_map(model)
    control_index = next(index for index, reference in enumerate(dof_map) if reference == target)

    solution = solve_displacement_control(adapter, model)

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.committed_state is not None
    assert solution.committed_state.displacement[control_index] == pytest.approx(1.0e-6)
    step = solution.result.steps[0]
    assert step.response["control_displacement"] == pytest.approx(1.0e-6)
    assert np.isfinite(step.response["controller_reaction"])
    np.testing.assert_allclose(
        step.response["free_residual"],
        np.zeros(len(step.response["free_residual"])),
        rtol=0.0,
        atol=2.0e-8,
    )
    assert control_index not in step.response["free_dofs"]
