"""V03 Newton history and load-control boundary verification for P5."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AdapterState,
    AdapterValidation,
    AnalysisOptions,
    FailureCode,
    IterationStatus,
    LocalFailure,
    ModelFamily,
    ModelResponse,
    NewtonMethod,
    SolveStatus,
    StepControlOptions,
    ToleranceOptions,
    initialize_state,
    solve_load_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "tests" / "fixtures" / "adapters" / "frame-linear.json"
ACTIVE_DOF = 3


def _model(*, method: NewtonMethod = NewtonMethod.FULL, max_iterations: int = 30):
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    options = AnalysisOptions(
        newton_method=method,
        max_iterations=max_iterations,
        tolerances=ToleranceOptions(
            residual=1.0e-10,
            displacement=1.0e-10,
            energy=1.0e-10,
            linear_solver=1.0e-12,
        ),
        step_control=StepControlOptions(
            initial_step=1.0,
            min_step=1.0e-4,
            max_step=1.0,
            max_steps=1,
        ),
    )
    return result.model.model_copy(update={"analysis": options})


class ImperfectColumnAdapter:
    """One-active-DOF V03 column embedded in the frame DOF topology."""

    family = ModelFamily.FRAME
    adapter_id = "v03-imperfect-column"
    core_package = "v03-reference"
    core_version = "1.0.0"

    def validate(self, model):
        return AdapterValidation()

    def initial_state(self, model):
        return AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id="v03-initial",
            committed=True,
        )

    def dof_map(self, model):
        return model.ordered_dof_refs()

    def constraint_map(self, model):
        return {index: 0.0 for index in range(len(self.dof_map(model))) if index != ACTIVE_DOF}

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        theta = float(values[ACTIVE_DOF])
        stiffness = 10.0
        length = 10.0
        reference_load = 0.9
        theta_0 = 0.01
        internal = np.zeros_like(values)
        external = np.zeros_like(values)
        internal[ACTIVE_DOF] = stiffness * (theta - theta_0)
        external[ACTIVE_DOF] = load_factor * reference_load * length * np.sin(theta)
        internal_tangent = np.eye(values.size)
        external_tangent = np.zeros((values.size, values.size))
        internal_tangent[ACTIVE_DOF, ACTIVE_DOF] = stiffness
        external_tangent[ACTIVE_DOF, ACTIVE_DOF] = (
            load_factor * reference_load * length * np.cos(theta)
        )
        digest = hashlib.sha256(f"{theta:.17g}:{load_factor:.17g}".encode()).hexdigest()
        return ModelResponse(
            internal_force=internal,
            tangent=internal_tangent,
            external_force=external,
            external_tangent=external_tangent,
            trial_state=AdapterState(
                model_id=model.model_id,
                model_family=model.model_family,
                adapter_id=self.adapter_id,
                core_package=self.core_package,
                core_version=self.core_version,
                state_id=f"v03:{digest}",
                history={"theta": theta},
            ),
            elements=(),
            strain_energy=0.5 * stiffness * (theta - theta_0) ** 2,
        )


class LimitPointAdapter(ImperfectColumnAdapter):
    """Canonical load path lambda=u-u^3, evaluated exactly at its limit point."""

    adapter_id = "p5-limit-point"
    core_package = "p5-limit-reference"

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        u = float(values[ACTIVE_DOF])
        internal = np.zeros_like(values)
        external = np.zeros_like(values)
        internal[ACTIVE_DOF] = u - u**3
        external[ACTIVE_DOF] = load_factor
        tangent = np.eye(values.size)
        active_tangent = 1.0 - 3.0 * u**2
        tangent[ACTIVE_DOF, ACTIVE_DOF] = 0.0 if abs(active_tangent) <= 1.0e-12 else active_tangent
        digest = hashlib.sha256(f"{u:.17g}:{load_factor:.17g}".encode()).hexdigest()
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=external,
            external_tangent=None,
            trial_state=AdapterState(
                model_id=model.model_id,
                model_family=model.model_family,
                adapter_id=self.adapter_id,
                core_package=self.core_package,
                core_version=self.core_version,
                state_id=f"limit:{digest}",
            ),
            elements=(),
            strain_energy=0.5 * u**2 - 0.25 * u**4,
        )


class NonfiniteDiagnosticAdapter(ImperfectColumnAdapter):
    adapter_id = "p5-nonfinite-diagnostic"

    def evaluate(self, *args, **kwargs):
        return replace(super().evaluate(*args, **kwargs), strain_energy=float("nan"))


class LocalFailureAdapter(ImperfectColumnAdapter):
    adapter_id = "p5-local-failure"

    def evaluate(self, *args, **kwargs):
        return replace(
            super().evaluate(*args, **kwargs),
            local_failures=(
                LocalFailure(
                    code="RETURN_MAPPING_FAILED",
                    message="reference material point did not converge",
                    element_id="E1",
                ),
            ),
        )


def _initial_column_state(adapter, model, theta: float, load_factor: float = 0.0):
    displacement = np.zeros(len(adapter.dof_map(model)))
    displacement[ACTIVE_DOF] = theta
    return initialize_state(
        adapter,
        model,
        displacement=displacement,
        load_factor=load_factor,
    )


def test_v03_full_newton_matches_reference_iteration_history():
    model = _model()
    adapter = ImperfectColumnAdapter()
    initial = _initial_column_state(adapter, model, theta=0.01)

    solution = solve_load_control(adapter, model, initial_state=initial)

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.committed_state is not None
    step = solution.result.steps[0]
    assert step.response["tangent_assemblies"] == 4
    assert step.iterations[-1].status is IterationStatus.CONVERGED
    theta_history = [record.diagnostics["displacement"][ACTIVE_DOF] for record in step.iterations]
    residual_history = [-record.diagnostics["residual"][ACTIVE_DOF] for record in step.iterations]
    tangent_history = [
        record.diagnostics["effective_tangent_diagonal"][ACTIVE_DOF] for record in step.iterations
    ]
    np.testing.assert_allclose(
        theta_history,
        [0.01, 0.0999580192, 0.0985652083, 0.0985643775],
        rtol=0.0,
        atol=5.0e-11,
    )
    np.testing.assert_allclose(
        residual_history,
        [-0.0899985, 0.0014553826, 0.0000008671, 3.0e-13],
        rtol=0.0,
        atol=5.0e-11,
    )
    np.testing.assert_allclose(
        tangent_history,
        [1.0004499963, 1.0449248006, 1.0436825691, 1.0436818333],
        rtol=0.0,
        atol=5.0e-10,
    )
    theta = solution.committed_state.displacement[ACTIVE_DOF]
    assert theta == pytest.approx(0.0985643775, abs=5.0e-11)
    assert 10.0 * np.sin(theta) == pytest.approx(0.9840486391, abs=5.0e-10)


def test_modified_newton_reuses_one_tangent_and_converges_without_quadratic_expectation():
    full_model = _model(method=NewtonMethod.FULL)
    modified_model = _model(method=NewtonMethod.MODIFIED)
    adapter = ImperfectColumnAdapter()
    full = solve_load_control(
        adapter,
        full_model,
        initial_state=_initial_column_state(adapter, full_model, theta=0.01),
    )
    modified = solve_load_control(
        adapter,
        modified_model,
        initial_state=_initial_column_state(adapter, modified_model, theta=0.01),
    )

    assert full.succeeded and modified.succeeded
    full_step = full.result.steps[0]
    modified_step = modified.result.steps[0]
    assert len(modified_step.iterations) > len(full_step.iterations)
    assert modified_step.response["tangent_assemblies"] == 1
    assert modified_step.iterations[0].tangent_reassembled
    assert all(not record.tangent_reassembled for record in modified_step.iterations[1:])
    assert modified.committed_state is not None
    assert full.committed_state is not None
    np.testing.assert_allclose(
        modified.committed_state.displacement,
        full.committed_state.displacement,
        rtol=0.0,
        atol=1.0e-10,
    )


def test_load_control_classifies_singular_limit_point_and_rolls_back():
    model = _model(max_iterations=8)
    adapter = LimitPointAdapter()
    u_limit = 1.0 / np.sqrt(3.0)
    lambda_limit = u_limit - u_limit**3
    initial = _initial_column_state(
        adapter,
        model,
        theta=u_limit,
        load_factor=lambda_limit,
    )

    solution = solve_load_control(
        adapter,
        model,
        target_load_factor=lambda_limit + 0.01,
        initial_state=initial,
    )

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.failures[0].code is FailureCode.CONTROL_ERROR
    assert solution.result.failures[0].details["linear_failure_code"] == "LINEAR_SINGULAR_SYSTEM"
    assert solution.result.steps[0].status.value == "rejected"
    assert solution.committed_state is initial
    assert solution.committed_state.load_factor == pytest.approx(lambda_limit)


@pytest.mark.parametrize(
    ("adapter", "expected_code"),
    (
        (NonfiniteDiagnosticAdapter(), FailureCode.TANGENT_ERROR),
        (LocalFailureAdapter(), FailureCode.LOCAL_MATERIAL_ERROR),
    ),
)
def test_nonfinite_and_local_diagnostics_reject_without_committing(adapter, expected_code):
    model = _model(max_iterations=4)
    initial = _initial_column_state(adapter, model, theta=0.01)

    solution = solve_load_control(adapter, model, initial_state=initial)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.failures[0].code is expected_code
    assert solution.committed_state is initial
    assert solution.result.steps[0].iterations[-1].status is IterationStatus.REJECTED


def test_max_iterations_preserves_rejected_history_and_termination_reason():
    model = _model(max_iterations=1)
    adapter = ImperfectColumnAdapter()
    initial = _initial_column_state(adapter, model, theta=0.01)

    solution = solve_load_control(adapter, model, initial_state=initial)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.failures[0].code is FailureCode.NONCONVERGENCE
    step = solution.result.steps[0]
    assert step.iterations[-1].status is IterationStatus.REJECTED
    assert step.iterations[-1].diagnostics["termination_reason"] == "MAX_ITERATIONS"
    assert step.response["termination_reason"] == FailureCode.NONCONVERGENCE.value
    assert solution.committed_state is initial
