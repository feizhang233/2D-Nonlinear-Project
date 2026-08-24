"""V06 orthogonality and P7 residual-merit line-search verification."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import (
    AdapterState,
    LineSearchMethod,
    LineSearchOptions,
    LineSearchStatus,
    MeritFunction,
    ModelFamily,
    ModelResponse,
    apply_line_search,
    build_equilibrium,
)


def _evaluation(
    residual: np.ndarray,
    tangent: np.ndarray,
    *,
    conservative: bool,
):
    size = residual.size
    return build_equilibrium(
        ModelResponse(
            internal_force=-residual,
            tangent=tangent,
            external_force=np.zeros(size),
            external_tangent=None,
            trial_state=AdapterState(
                model_id="line-search-reference",
                model_family=ModelFamily.FRAME,
                adapter_id="line-search-adapter",
                core_package="line-search-reference",
                core_version="1.0.0",
                state_id="trial",
            ),
            elements=(),
            strain_energy=0.0,
            metadata={"conservative": conservative},
        ),
        {},
    )


def _v06_at(position: np.ndarray):
    x_1, x_2 = position
    potential_gradient = np.asarray([2.0 * x_1 - 3.0 + x_1**3, x_2 - 2.0 + x_2**3])
    residual = -potential_gradient
    hessian = np.diag([2.0 + 3.0 * x_1**2, 1.0 + 3.0 * x_2**2])
    return _evaluation(residual, hessian, conservative=True)


def test_v06_orthogonality_search_reaches_reference_minimum():
    current = np.zeros(2)
    direction = np.ones(2)
    initial = _v06_at(current)
    options = LineSearchOptions(
        enabled=True,
        method=LineSearchMethod.ORTHOGONALITY,
        max_iterations=12,
    )

    result = apply_line_search(
        initial,
        _v06_at,
        current,
        direction,
        options,
        conservative=True,
    )

    assert result.status is LineSearchStatus.ACCEPTED
    assert result.merit_function is MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE
    assert result.alpha == pytest.approx(1.0)
    accepted = current + result.alpha * direction
    np.testing.assert_allclose(accepted, [1.0, 1.0], atol=0.0)
    evaluation = _v06_at(accepted)
    assert direction @ evaluation.free_residual == pytest.approx(0.0, abs=1.0e-14)
    assert result.samples[-1].directional_residual == pytest.approx(0.0, abs=1.0e-14)


def test_nonconservative_backtracking_uses_explicit_residual_l2_merit():
    def evaluate(position: np.ndarray):
        residual = np.asarray([1.0 - position[0]])
        return _evaluation(residual, np.ones((1, 1)), conservative=False)

    current = np.zeros(1)
    initial = evaluate(current)
    options = LineSearchOptions(
        enabled=True,
        method=LineSearchMethod.BACKTRACKING,
        reduction_factor=0.5,
        max_iterations=4,
    )

    result = apply_line_search(initial, evaluate, current, np.asarray([2.0]), options)

    assert result.accepted
    assert result.merit_function is MeritFunction.RESIDUAL_L2_NONCONSERVATIVE
    assert result.alpha == pytest.approx(0.5)
    assert [sample.alpha for sample in result.samples] == pytest.approx([1.0, 0.5])
    assert result.samples[-1].merit == pytest.approx(0.0)


def test_disabled_line_search_is_full_step_without_extra_evaluation():
    calls = 0

    def unexpected(_position: np.ndarray):
        nonlocal calls
        calls += 1
        raise AssertionError("disabled full step must not evaluate samples")

    initial = _evaluation(np.asarray([1.0]), np.ones((1, 1)), conservative=False)
    result = apply_line_search(
        initial,
        unexpected,
        np.zeros(1),
        np.ones(1),
        LineSearchOptions(enabled=False),
    )

    assert result.accepted
    assert result.alpha == 1.0
    assert result.merit_function is MeritFunction.FULL_STEP
    assert result.samples == ()
    assert calls == 0


def test_orthogonality_rejects_unmarked_nonconservative_response():
    initial = _evaluation(np.asarray([1.0]), np.ones((1, 1)), conservative=False)
    result = apply_line_search(
        initial,
        lambda position: initial,
        np.zeros(1),
        np.ones(1),
        LineSearchOptions(enabled=True, method=LineSearchMethod.ORTHOGONALITY),
        conservative=False,
    )

    assert result.status is LineSearchStatus.FAILED
    assert "conservative=true" in result.failure_reason
