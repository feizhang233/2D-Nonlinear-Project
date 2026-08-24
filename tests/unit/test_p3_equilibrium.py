from __future__ import annotations

import numpy as np

from nonlinear_core import (
    AdapterState,
    CorrectionStatus,
    LinearFailureCode,
    ModelFamily,
    ModelResponse,
    build_equilibrium,
    recover_constraint_reactions,
    solve_constrained_correction,
)


def _response(
    stiffness: np.ndarray,
    displacement: np.ndarray,
    external_force: np.ndarray,
    external_tangent: np.ndarray | None = None,
) -> ModelResponse:
    return ModelResponse(
        internal_force=stiffness @ displacement,
        tangent=stiffness,
        external_force=external_force,
        external_tangent=external_tangent,
        trial_state=AdapterState(
            model_id="analytic",
            model_family=ModelFamily.FRAME,
            adapter_id="analytic",
            core_package="analytic",
            core_version="1",
            state_id="trial",
        ),
        elements=(),
        strain_energy=float(0.5 * displacement @ stiffness @ displacement),
    )


def test_residual_sign_and_full_free_constrained_storage():
    stiffness = np.array([[4.0, 1.0], [1.0, 3.0]])
    displacement = np.array([0.1, -0.2])
    force = np.array([1.0, 2.0])
    response = _response(stiffness, displacement, force)

    evaluation = build_equilibrium(response, {1: 0.0})

    expected = force - stiffness @ displacement
    np.testing.assert_allclose(evaluation.residual, expected)
    np.testing.assert_allclose(evaluation.free_residual, expected[[0]])
    np.testing.assert_allclose(evaluation.constrained_residual, expected[[1]])
    np.testing.assert_array_equal(evaluation.partition.free_dofs, [0])
    np.testing.assert_array_equal(evaluation.partition.constrained_dofs, [1])


def test_effective_tangent_subtracts_external_tangent_and_records_nonsymmetry():
    internal = np.array([[2.0, 1.0], [1.0, 3.0]])
    external = np.array([[0.0, 2.0], [0.0, 0.0]])
    evaluation = build_equilibrium(
        _response(internal, np.zeros(2), np.ones(2), external),
        {},
    )

    np.testing.assert_allclose(evaluation.effective_tangent, internal - external)
    assert not evaluation.tangent_diagnostics.is_symmetric
    assert not evaluation.tangent_diagnostics.definiteness_evaluated


def test_symmetric_indefinite_tangent_is_not_rejected_by_interface():
    stiffness = np.diag([2.0, -1.0])
    evaluation = build_equilibrium(
        _response(stiffness, np.zeros(2), np.array([2.0, -1.0])),
        {},
    )
    correction = solve_constrained_correction(evaluation, np.zeros(2))

    assert evaluation.tangent_diagnostics.is_symmetric
    assert correction.succeeded
    np.testing.assert_allclose(correction.correction, [1.0, 1.0])


def test_nonzero_prescribed_displacement_and_reaction_follow_v05_sign():
    stiffness = np.array([[4.0, 1.0], [1.0, 3.0]])
    initial = np.zeros(2)
    evaluation = build_equilibrium(
        _response(stiffness, initial, np.zeros(2)),
        {1: 0.1},
    )

    correction = solve_constrained_correction(evaluation, initial)

    assert correction.status is CorrectionStatus.SUCCEEDED
    np.testing.assert_allclose(correction.correction, [-0.025, 0.1])
    np.testing.assert_allclose(correction.predicted_free_residual, [0.0], atol=1.0e-16)

    updated = initial + correction.correction
    converged = build_equilibrium(
        _response(stiffness, updated, np.zeros(2)),
        {1: 0.1},
    )
    reactions = recover_constraint_reactions(converged)
    np.testing.assert_array_equal(reactions.constrained_dofs, [1])
    np.testing.assert_allclose(reactions.constrained_reactions, [0.275])
    np.testing.assert_allclose(reactions.full_imbalance, [0.0, 0.275])


def test_singular_correction_remains_a_linear_failure_not_a_convergence_status():
    stiffness = np.array([[1.0, 1.0], [1.0, 1.0]])
    evaluation = build_equilibrium(
        _response(stiffness, np.zeros(2), np.ones(2)),
        {},
    )

    correction = solve_constrained_correction(evaluation, np.zeros(2))

    assert correction.status is CorrectionStatus.FAILED
    assert correction.correction is None
    assert correction.linear_result.failure is not None
    assert correction.linear_result.failure.code is LinearFailureCode.SINGULAR_SYSTEM
    assert correction.diagnostics["estimated_rigid_or_unconstrained_modes"] == 1
