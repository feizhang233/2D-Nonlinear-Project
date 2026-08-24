"""P7 growth, cutback/retry, minimum-step, and failure-disposition evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AdapterState,
    AdapterValidation,
    AnalysisOptions,
    FailureAction,
    FailureCode,
    FailureRecord,
    LocalFailure,
    ModelFamily,
    ModelResponse,
    SolveStatus,
    StepControlOptions,
    StepStatus,
    failure_disposition,
    initialize_state,
    solve_adaptive_load_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "examples" / "adapters" / "frame-linear.json"
ACTIVE_DOF = 3


def _model(
    *,
    initial_step: float,
    min_step: float,
    max_step: float,
    growth_factor: float = 1.0,
    target_iterations: int = 2,
    max_retries: int = 8,
):
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    options = AnalysisOptions(
        max_iterations=8,
        step_control=StepControlOptions(
            initial_step=initial_step,
            min_step=min_step,
            max_step=max_step,
            max_steps=20,
            max_retries=max_retries,
            target_iterations=target_iterations,
            cutback_factor=0.5,
            growth_factor=growth_factor,
        ),
    )
    return result.model.model_copy(update={"analysis": options})


class IncrementLimitedAdapter:
    """Linear response whose local integration rejects increments above a threshold."""

    family = ModelFamily.FRAME
    adapter_id = "p7-increment-limited"
    core_package = "p7-reference"
    core_version = "1.0.0"

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def validate(self, model):
        return AdapterValidation()

    def initial_state(self, model):
        return AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id="p7-initial",
            committed=True,
            history={"load_factor": 0.0},
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
        committed_factor = (
            0.0 if committed_state is None else float(committed_state.history["load_factor"])
        )
        increment = abs(load_factor - committed_factor)
        local_failures = ()
        if increment > self.threshold + 1.0e-14:
            local_failures = (
                LocalFailure(
                    code="LOCAL_INCREMENT_TOO_LARGE",
                    message="reference local integration requests cutback",
                    element_id="E1",
                ),
            )
        internal = values.copy()
        external = np.zeros_like(values)
        external[ACTIVE_DOF] = load_factor
        digest = hashlib.sha256(
            f"{load_factor:.17g}:{values[ACTIVE_DOF]:.17g}".encode()
        ).hexdigest()
        return ModelResponse(
            internal_force=internal,
            tangent=np.eye(values.size),
            external_force=external,
            external_tangent=None,
            trial_state=AdapterState(
                model_id=model.model_id,
                model_family=model.model_family,
                adapter_id=self.adapter_id,
                core_package=self.core_package,
                core_version=self.core_version,
                state_id=f"p7:{digest}",
                history={"load_factor": load_factor},
            ),
            elements=(),
            strain_energy=0.5 * float(values @ values),
            local_failures=local_failures,
        )


def test_failed_attempt_is_retained_then_cutback_recovers_from_committed_state():
    model = _model(initial_step=0.2, min_step=0.05, max_step=0.2)
    adapter = IncrementLimitedAdapter(threshold=0.1)
    initial = initialize_state(adapter, model)

    solution = solve_adaptive_load_control(
        adapter,
        model,
        target_load_factor=0.2,
        initial_state=initial,
    )

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.committed_state is not None
    assert solution.committed_state.load_factor == pytest.approx(0.2)
    assert [step.status for step in solution.result.steps] == [
        StepStatus.REJECTED,
        StepStatus.ACCEPTED,
        StepStatus.ACCEPTED,
    ]
    rejected = solution.result.steps[0]
    assert rejected.failure is not None
    assert rejected.failure.code is FailureCode.LOCAL_MATERIAL_ERROR
    assert rejected.response["will_retry"] is True
    assert rejected.response["adaptive_step_size"] == pytest.approx(0.2)
    assert rejected.response["next_step_size"] == pytest.approx(0.1)
    assert solution.result.steps[1].step_index == rejected.step_index
    assert solution.result.steps[1].response["attempt_index"] == 1
    assert solution.result.metadata["cutbacks"] == 1


def test_fast_convergence_grows_step_within_maximum_bound():
    model = _model(
        initial_step=0.05,
        min_step=0.025,
        max_step=0.2,
        growth_factor=2.0,
    )
    adapter = IncrementLimitedAdapter(threshold=1.0)

    solution = solve_adaptive_load_control(adapter, model, target_load_factor=0.35)

    assert solution.succeeded
    accepted = [step for step in solution.result.steps if step.status is StepStatus.ACCEPTED]
    assert [step.response["adaptive_step_size"] for step in accepted] == pytest.approx(
        [0.05, 0.1, 0.2]
    )
    assert [step.load_factor for step in accepted] == pytest.approx([0.05, 0.15, 0.35])
    assert all(step.response["next_step_size"] <= 0.2 for step in accepted)
    assert solution.result.metadata["growths"] == 2


def test_repeated_failure_terminates_explicitly_at_minimum_step():
    model = _model(initial_step=0.2, min_step=0.05, max_step=0.2)
    adapter = IncrementLimitedAdapter(threshold=0.0)
    initial = initialize_state(adapter, model)

    solution = solve_adaptive_load_control(
        adapter,
        model,
        target_load_factor=0.2,
        initial_state=initial,
    )

    assert solution.result.status is SolveStatus.FAILED
    assert [step.response["adaptive_step_size"] for step in solution.result.steps] == pytest.approx(
        [0.2, 0.1, 0.05]
    )
    assert all(step.status is StepStatus.REJECTED for step in solution.result.steps)
    final_step = solution.result.steps[-1]
    assert final_step.response["will_retry"] is False
    assert final_step.response["adaptive_termination"] == "MIN_STEP_REACHED"
    assert solution.result.failures[0].details["adaptive_termination"] == "MIN_STEP_REACHED"
    assert solution.committed_state is initial


def test_retry_limit_terminates_before_minimum_when_budget_is_exhausted():
    model = _model(
        initial_step=0.2,
        min_step=0.01,
        max_step=0.2,
        max_retries=1,
    )
    adapter = IncrementLimitedAdapter(threshold=0.0)

    solution = solve_adaptive_load_control(adapter, model, target_load_factor=0.2)

    assert solution.result.status is SolveStatus.FAILED
    assert [step.response["adaptive_step_size"] for step in solution.result.steps] == pytest.approx(
        [0.2, 0.1]
    )
    assert solution.result.failures[0].details["adaptive_termination"] == "MAX_RETRIES_REACHED"


def test_every_public_failure_code_has_an_explicit_retry_disposition():
    expected = {
        FailureCode.MODEL_ERROR: FailureAction.TERMINATE,
        FailureCode.CONTROL_ERROR: FailureAction.RETRY_WITH_CUTBACK,
        FailureCode.TANGENT_ERROR: FailureAction.RETRY_WITH_CUTBACK,
        FailureCode.STATE_ERROR: FailureAction.TERMINATE,
        FailureCode.LINEAR_SOLVE_ERROR: FailureAction.RETRY_WITH_CUTBACK,
        FailureCode.LOCAL_MATERIAL_ERROR: FailureAction.RETRY_WITH_CUTBACK,
        FailureCode.NONCONVERGENCE: FailureAction.RETRY_WITH_CUTBACK,
    }
    assert set(expected) == set(FailureCode)
    for code, action in expected.items():
        disposition = failure_disposition(FailureRecord(code=code, message="reference failure"))
        assert disposition.action is action

    det_f = FailureRecord(
        code=FailureCode.MODEL_ERROR,
        message="current configuration inverted",
        details={"min_det_f": -0.1},
    )
    assert failure_disposition(det_f).action is FailureAction.RETRY_WITH_CUTBACK
