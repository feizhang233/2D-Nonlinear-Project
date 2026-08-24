"""V01 exact linear one-step recovery and residual/Newton sign gate."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import (
    AdapterState,
    ModelFamily,
    ModelResponse,
    build_equilibrium,
    solve_constrained_correction,
)


def _linear_response(matrix: np.ndarray, force: np.ndarray, displacement: np.ndarray):
    return ModelResponse(
        internal_force=matrix @ displacement,
        tangent=matrix,
        external_force=force,
        external_tangent=None,
        trial_state=AdapterState(
            model_id="V01",
            model_family=ModelFamily.CONTINUUM,
            adapter_id="V01",
            core_package="analytic",
            core_version="1",
            state_id="trial",
        ),
        elements=(),
        strain_energy=float(0.5 * displacement @ matrix @ displacement),
    )


def test_v01_exact_tangent_reaches_linear_solution_in_one_correction():
    matrix = np.array([[4.0, 1.0], [1.0, 3.0]])
    force = np.array([1.0, 2.0])
    initial = np.zeros(2)
    first = build_equilibrium(_linear_response(matrix, force, initial), {})

    correction = solve_constrained_correction(first, initial)

    assert correction.succeeded
    np.testing.assert_allclose(correction.correction, [1.0 / 11.0, 7.0 / 11.0])
    updated = initial + correction.correction
    final = build_equilibrium(_linear_response(matrix, force, updated), {})
    np.testing.assert_allclose(final.residual, np.zeros(2), atol=2.3e-16)
    assert final.response.strain_energy == pytest.approx(15.0 / 22.0)

    wrong_update = initial - correction.correction
    wrong = build_equilibrium(_linear_response(matrix, force, wrong_update), {})
    np.testing.assert_allclose(wrong.residual, 2.0 * force)
