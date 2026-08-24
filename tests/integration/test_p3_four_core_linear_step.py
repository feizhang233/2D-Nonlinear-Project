"""P3 acceptance: one exact correction reproduces every P2 native reference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    CorrectionStatus,
    LinearFailureCode,
    evaluate_equilibrium,
    get_adapter,
    recover_constraint_reactions,
    solve_constrained_correction,
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
def test_one_exact_newton_correction_matches_original_core(filename: str):
    model = _model(filename)
    adapter = get_adapter(model)
    initial = np.zeros(len(adapter.dof_map(model)))
    evaluation = evaluate_equilibrium(adapter, model, initial)

    correction = solve_constrained_correction(evaluation, initial)

    assert correction.status is CorrectionStatus.SUCCEEDED
    assert correction.linear_result.relative_residual is not None
    assert correction.linear_result.relative_residual <= 1.0e-10
    assert correction.correction is not None
    updated = initial + correction.correction
    original = adapter.native_reference(model)
    np.testing.assert_allclose(updated, original.displacement, rtol=2.0e-10, atol=2.0e-12)

    converged = evaluate_equilibrium(adapter, model, updated)
    np.testing.assert_allclose(
        converged.free_residual,
        np.zeros_like(converged.free_residual),
        rtol=0.0,
        atol=2.0e-8,
    )
    reactions = recover_constraint_reactions(converged)
    np.testing.assert_allclose(
        reactions.full_imbalance,
        original.reactions,
        rtol=2.0e-10,
        atol=2.0e-8,
    )


def test_underconstrained_frame_reports_rigid_modes_as_linear_failure():
    model = _model("frame-linear.json").model_copy(update={"constraints": ()})
    adapter = get_adapter(model)
    initial = np.zeros(len(adapter.dof_map(model)))
    evaluation = evaluate_equilibrium(adapter, model, initial)

    correction = solve_constrained_correction(evaluation, initial)

    assert correction.status is CorrectionStatus.FAILED
    assert correction.linear_result.failure is not None
    assert correction.linear_result.failure.code is LinearFailureCode.SINGULAR_SYSTEM
    assert correction.linear_result.nullity is not None
    assert correction.linear_result.nullity >= 3
