"""V05 block solve, V04 limit-point path, and P6 control-boundary evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AdapterState,
    AdapterValidation,
    AnalysisOptions,
    ControlMethod,
    DisplacementControlOptions,
    Dof,
    DofRef,
    FailureCode,
    IterationStatus,
    ModelFamily,
    ModelResponse,
    SolveStatus,
    ToleranceOptions,
    initialize_state,
    solve_displacement_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "tests" / "fixtures" / "adapters" / "frame-linear.json"
FREE_DOF = 3
CONTROL_DOF = 4


def _model(*, target: DofRef, increment: float, max_iterations: int = 12):
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    options = AnalysisOptions(
        control_method=ControlMethod.DISPLACEMENT,
        displacement_control=DisplacementControlOptions(
            target=target,
            increment=increment,
        ),
        max_iterations=max_iterations,
        tolerances=ToleranceOptions(
            residual=1.0e-12,
            displacement=1.0e-12,
            energy=1.0e-12,
            linear_solver=1.0e-12,
        ),
    )
    return result.model.model_copy(update={"analysis": options})


class V05Adapter:
    """The V05 2x2 stiffness embedded at global indices 3 and 4."""

    family = ModelFamily.FRAME
    adapter_id = "v05-block-adapter"
    core_package = "v05-reference"
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
            state_id="v05-initial",
            committed=True,
        )

    def dof_map(self, model):
        return model.ordered_dof_refs()

    def constraint_map(self, model):
        return {index: 0.0 for index in (0, 1, 2, 5)}

    def stiffness(self, size: int) -> np.ndarray:
        matrix = np.eye(size)
        matrix[np.ix_((FREE_DOF, CONTROL_DOF), (FREE_DOF, CONTROL_DOF))] = (
            (4.0, 1.0),
            (1.0, 3.0),
        )
        return matrix

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        tangent = self.stiffness(values.size)
        internal = tangent @ values
        digest = hashlib.sha256(values.tobytes()).hexdigest()
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=np.zeros_like(values),
            external_tangent=None,
            trial_state=AdapterState(
                model_id=model.model_id,
                model_family=model.model_family,
                adapter_id=self.adapter_id,
                core_package=self.core_package,
                core_version=self.core_version,
                state_id=f"v05:{digest}",
            ),
            elements=(),
            strain_energy=0.5 * float(values @ tangent @ values),
        )


class ReversingControlAdapter(V05Adapter):
    """Path c=x^2 at its turning point: a negative c increment has no solution."""

    adapter_id = "p6-reversing-control"

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        free_value = float(values[FREE_DOF])
        control_value = float(values[CONTROL_DOF])
        tangent = np.eye(values.size)
        tangent[FREE_DOF, FREE_DOF] = 2.0 * free_value
        tangent[FREE_DOF, CONTROL_DOF] = -1.0
        tangent[CONTROL_DOF, FREE_DOF] = -1.0
        internal = np.zeros_like(values)
        internal[FREE_DOF] = free_value**2 - control_value
        internal[CONTROL_DOF] = control_value - free_value
        digest = hashlib.sha256(values.tobytes()).hexdigest()
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=np.zeros_like(values),
            external_tangent=None,
            trial_state=AdapterState(
                model_id=model.model_id,
                model_family=model.model_family,
                adapter_id=self.adapter_id,
                core_package=self.core_package,
                core_version=self.core_version,
                state_id=f"reverse:{digest}",
            ),
            elements=(),
            strain_energy=0.0,
        )


class V04LimitPointAdapter(V05Adapter):
    """V04 force-displacement path with vertical displacement as the controller."""

    adapter_id = "v04-limit-point"

    def constraint_map(self, model):
        return {index: 0.0 for index in range(len(self.dof_map(model))) if index != FREE_DOF}

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        vertical_displacement = float(values[FREE_DOF])
        sine = (8.0 - vertical_displacement) / 10.0
        theta = float(np.arcsin(sine))
        cosine = float(np.cos(theta))
        force = 5.0 * np.tan(theta) * (10.0 * cosine - 6.0)
        force_derivative_theta = 5.0 * (10.0 * cosine - 6.0 / cosine**2)
        displacement_derivative_theta = -10.0 * cosine
        tangent = np.eye(values.size)
        tangent[FREE_DOF, FREE_DOF] = force_derivative_theta / displacement_derivative_theta
        internal = np.zeros_like(values)
        internal[FREE_DOF] = force
        digest = hashlib.sha256(values.tobytes()).hexdigest()
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=np.zeros_like(values),
            external_tangent=None,
            trial_state=AdapterState(
                model_id=model.model_id,
                model_family=model.model_family,
                adapter_id=self.adapter_id,
                core_package=self.core_package,
                core_version=self.core_version,
                state_id=f"v04:{digest}",
                history={"theta": theta, "force": force},
            ),
            elements=(),
            strain_energy=0.0,
        )


def _initial_state(adapter, model, *, control_index: int, value: float):
    displacement = np.zeros(len(adapter.dof_map(model)))
    displacement[control_index] = value
    return initialize_state(adapter, model, displacement=displacement)


def test_v05_block_solve_and_controller_reaction_match_reference():
    target = DofRef(node_id="N2", dof=Dof.UY)
    model = _model(target=target, increment=0.1)
    adapter = V05Adapter()

    solution = solve_displacement_control(adapter, model)

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.committed_state is not None
    step = solution.result.steps[0]
    assert len(step.iterations) == 2
    assert step.iterations[-1].status is IterationStatus.CONVERGED
    assert solution.committed_state.displacement[FREE_DOF] == pytest.approx(-0.025)
    assert solution.committed_state.displacement[CONTROL_DOF] == pytest.approx(0.1)
    assert step.response["controller_reaction"] == pytest.approx(0.275)
    assert step.response["full_imbalance"][CONTROL_DOF] == pytest.approx(0.275)
    np.testing.assert_allclose(step.response["free_residual"], [0.0], atol=1.0e-14)
    assert step.response["load_factor"] == 0.0
    assert step.response["control_displacement_increment"] == pytest.approx(0.1)


def test_v04_displacement_control_crosses_load_limit_and_traces_descending_force():
    target = DofRef(node_id="N2", dof=Dof.UX)
    model = _model(target=target, increment=-1.0)
    adapter = V04LimitPointAdapter()
    initial = _initial_state(adapter, model, control_index=FREE_DOF, value=8.0)

    solution = solve_displacement_control(
        adapter,
        model,
        number_of_steps=6,
        initial_state=initial,
    )

    assert solution.succeeded
    displacements = [step.response["control_displacement"] for step in solution.result.steps]
    reactions = [step.response["controller_reaction"] for step in solution.result.steps]
    assert displacements == pytest.approx([7.0, 6.0, 5.0, 4.0, 3.0, 2.0])
    theta_limit = np.arccos(0.6 ** (1.0 / 3.0))
    displacement_limit = 8.0 - 10.0 * np.sin(theta_limit)
    force_limit = 5.0 * np.tan(theta_limit) * (10.0 * np.cos(theta_limit) - 6.0)
    assert displacement_limit == pytest.approx(2.6276509877, abs=1.0e-10)
    assert force_limit == pytest.approx(7.7528728303, abs=1.0e-10)
    assert displacements[-2] > displacement_limit > displacements[-1]
    assert reactions[-2] < force_limit
    assert reactions[-1] < reactions[-2]


def test_reversing_control_coordinate_reports_method_failure_and_rolls_back():
    target = DofRef(node_id="N2", dof=Dof.UY)
    model = _model(target=target, increment=-0.1)
    adapter = ReversingControlAdapter()
    initial = initialize_state(adapter, model)

    solution = solve_displacement_control(adapter, model, initial_state=initial)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.failures[0].code is FailureCode.CONTROL_ERROR
    assert "cannot parameterize this path" in solution.result.failures[0].message
    assert solution.committed_state is initial


def test_control_dof_conflict_is_rejected_before_iteration():
    target = DofRef(node_id="N1", dof=Dof.UX)
    model = _model(target=target, increment=0.1)
    adapter = V05Adapter()

    solution = solve_displacement_control(adapter, model)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.failures[0].code is FailureCode.CONTROL_ERROR
    assert "conflicts" in solution.result.failures[0].message
    assert solution.result.steps == ()
