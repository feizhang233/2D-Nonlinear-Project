from __future__ import annotations

import numpy as np
from scipy.sparse import csc_matrix

from nonlinear_core import (
    LinearFailureCode,
    LinearSolveOptions,
    LinearSolverBackend,
    LinearSolveStatus,
    solve_linear_system,
)


def test_dense_solver_returns_actual_equation_residual():
    matrix = np.array([[4.0, 1.0], [1.0, 3.0]])
    rhs = np.array([1.0, 2.0])

    result = solve_linear_system(
        matrix,
        rhs,
        LinearSolveOptions(backend=LinearSolverBackend.DENSE),
    )

    assert result.succeeded
    assert result.status is LinearSolveStatus.SUCCEEDED
    assert result.backend is LinearSolverBackend.DENSE
    np.testing.assert_allclose(result.solution, [1.0 / 11.0, 7.0 / 11.0])
    assert result.residual is not None
    np.testing.assert_allclose(result.residual, matrix @ result.solution - rhs, atol=0.0)
    assert result.relative_residual is not None and result.relative_residual < 1.0e-15
    assert not result.solution.flags.writeable
    assert not result.residual.flags.writeable


def test_multiple_right_hand_sides_share_one_factorization_contract(monkeypatch):
    matrix = np.array([[4.0, 1.0], [1.0, 3.0]])
    right_hand_sides = np.array([[1.0, 2.0], [2.0, -1.0]])
    original_solve = np.linalg.solve
    calls = 0

    def counted_solve(coefficients, rhs):
        nonlocal calls
        calls += 1
        return original_solve(coefficients, rhs)

    monkeypatch.setattr(np.linalg, "solve", counted_solve)

    result = solve_linear_system(
        matrix,
        right_hand_sides,
        LinearSolveOptions(backend=LinearSolverBackend.DENSE),
    )

    assert result.succeeded
    assert calls == 1
    assert result.solution is not None and result.solution.shape == (2, 2)
    assert result.residual is not None and result.residual.shape == (2, 2)
    np.testing.assert_allclose(matrix @ result.solution, right_hand_sides, atol=1.0e-15)
    np.testing.assert_allclose(result.residual, matrix @ result.solution - right_hand_sides)


def test_sparse_lu_accepts_scipy_sparse_input_and_uses_pivoted_backend():
    matrix = csc_matrix(
        np.array(
            [
                [0.0, 2.0, 0.0],
                [1.0, 0.0, 3.0],
                [0.0, 4.0, 5.0],
            ]
        )
    )
    rhs = np.array([2.0, 4.0, 9.0])

    result = solve_linear_system(
        matrix,
        rhs,
        LinearSolveOptions(backend=LinearSolverBackend.SPARSE_LU),
    )

    assert result.succeeded
    assert result.backend is LinearSolverBackend.SPARSE_LU
    np.testing.assert_allclose(matrix @ result.solution, rhs, rtol=1.0e-14, atol=1.0e-14)


def test_auto_backend_switches_to_sparse_above_threshold():
    result = solve_linear_system(
        np.eye(5),
        np.arange(5.0),
        LinearSolveOptions(backend=LinearSolverBackend.AUTO, dense_threshold=4),
    )

    assert result.succeeded
    assert result.backend is LinearSolverBackend.SPARSE_LU


def test_singular_system_is_classified_with_nullity():
    result = solve_linear_system([[1.0, 1.0], [2.0, 2.0]], [1.0, 2.0])

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.code is LinearFailureCode.SINGULAR_SYSTEM
    assert result.rank == 1
    assert result.nullity == 1
    assert result.failure.details["estimated_nullity"] == 1


def test_ill_conditioned_system_has_distinct_failure_code():
    options = LinearSolveOptions(
        equilibrate=False,
        condition_warning_threshold=1.0e6,
        condition_error_threshold=1.0e8,
    )
    result = solve_linear_system(np.diag([1.0, 1.0e-12]), [1.0, 1.0], options)

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.code is LinearFailureCode.ILL_CONDITIONED_SYSTEM
    assert result.condition_estimate is not None and result.condition_estimate >= 1.0e12


def test_nonfinite_and_dimension_failures_are_classified_before_factorization():
    nonfinite = solve_linear_system([[1.0, np.nan], [0.0, 1.0]], [1.0, 2.0])
    mismatch = solve_linear_system(np.eye(2), [1.0, 2.0, 3.0])

    assert nonfinite.failure is not None
    assert nonfinite.failure.code is LinearFailureCode.NONFINITE_INPUT
    assert mismatch.failure is not None
    assert mismatch.failure.code is LinearFailureCode.DIMENSION_MISMATCH
