"""V07 path-dependent counterexample for trial/commit/rollback isolation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AdapterState,
    AdapterValidation,
    ModelFamily,
    ModelResponse,
    StateFailureCode,
    StateTransitionError,
    begin_step,
    commit,
    deserialize_restart,
    evaluate_trial,
    initialize_state,
    rollback,
    serialize_restart,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "examples" / "adapters" / "frame-linear.json"


def _frame_model():
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    return result.model


class HistoryAdapter:
    """Minimal irreversible material-point surrogate from V07."""

    family = ModelFamily.FRAME
    adapter_id = "v07-history-adapter"
    core_package = "v07-history-core"
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
            state_id="v07-initial",
            committed=True,
            history={"q": 0.2, "audit": {"values": [0.2]}},
        )

    def dof_map(self, model):
        return model.ordered_dof_refs()

    def constraint_map(self, model):
        return {}

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        q_n = 0.2 if committed_state is None else float(committed_state.history["q"])
        u_trial = float(values[0])
        q_trial = max(q_n, abs(u_trial))
        internal = np.zeros_like(values)
        internal[0] = (1.0 + q_trial) * u_trial
        tangent = np.eye(values.size)
        tangent[0, 0] = 1.0 + q_trial
        digest = hashlib.sha256(
            f"{model.model_id}:{q_trial:.17g}:{u_trial:.17g}".encode()
        ).hexdigest()
        trial = AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=f"v07:{digest}",
            committed=False,
            history={"q": q_trial, "audit": {"values": [q_trial]}},
        )
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=np.zeros_like(values),
            external_tangent=None,
            trial_state=trial,
            elements=(),
            strain_energy=0.5 * (1.0 + q_trial) * u_trial**2,
        )


def _trial_vector(size: int, value: float) -> np.ndarray:
    result = np.zeros(size)
    result[0] = value
    return result


def test_v07_failed_trial_rollback_and_cutback_match_direct_path():
    model = _frame_model()
    adapter = HistoryAdapter()
    committed = initialize_state(adapter, model)
    size = len(adapter.dof_map(model))

    failed_context = begin_step(
        committed,
        target_load_factor=1.0,
        predictor_displacement=_trial_vector(size, 0.5),
    )
    failed = evaluate_trial(failed_context, adapter, model, iteration_index=4)
    assert failed.state.history["q"] == pytest.approx(0.5)
    assert failed.response.internal_force[0] == pytest.approx(0.75)
    assert committed.history["q"] == pytest.approx(0.2)
    with pytest.raises(StateTransitionError) as not_converged:
        commit(failed_context, failed.state, converged=False)
    assert not_converged.value.code is StateFailureCode.CONVERGENCE_REQUIRED

    restored_base = rollback(failed_context, failed.state)
    assert restored_base is committed
    assert restored_base.history["q"] == pytest.approx(0.2)

    cutback_context = begin_step(
        restored_base,
        target_load_factor=0.5,
        predictor_displacement=_trial_vector(size, 0.3),
        attempt_index=1,
    )
    after_rollback = evaluate_trial(cutback_context, adapter, model, iteration_index=2)

    direct_context = begin_step(
        committed,
        target_load_factor=0.5,
        predictor_displacement=_trial_vector(size, 0.3),
    )
    direct = evaluate_trial(direct_context, adapter, model, iteration_index=2)

    assert after_rollback.state.history["q"] == pytest.approx(0.3)
    assert after_rollback.response.internal_force[0] == pytest.approx(0.39)
    assert after_rollback.state.to_payload() == direct.state.to_payload()
    np.testing.assert_array_equal(
        after_rollback.response.internal_force,
        direct.response.internal_force,
    )


def test_v07_each_iteration_recomputes_from_same_committed_state():
    model = _frame_model()
    adapter = HistoryAdapter()
    committed = initialize_state(adapter, model)
    context = begin_step(committed, target_load_factor=1.0)
    size = len(adapter.dof_map(model))

    high_trial = evaluate_trial(
        context,
        adapter,
        model,
        trial_displacement=_trial_vector(size, 0.5),
        iteration_index=1,
    )
    low_trial = evaluate_trial(
        context,
        adapter,
        model,
        trial_displacement=_trial_vector(size, 0.3),
        iteration_index=2,
    )

    assert high_trial.state.history["q"] == pytest.approx(0.5)
    assert low_trial.state.history["q"] == pytest.approx(0.3)
    assert low_trial.response.internal_force[0] == pytest.approx(0.39)
    assert committed.history["q"] == pytest.approx(0.2)


def test_v07_restart_and_continuous_calculation_are_equivalent():
    model = _frame_model()
    adapter = HistoryAdapter()
    size = len(adapter.dof_map(model))
    initial = initialize_state(adapter, model)
    first_context = begin_step(initial, target_load_factor=0.5)
    first_trial = evaluate_trial(
        first_context,
        adapter,
        model,
        trial_displacement=_trial_vector(size, 0.3),
        iteration_index=3,
    )
    first_committed = commit(first_context, first_trial.state, converged=True)
    assert first_committed.history["q"] == pytest.approx(0.3)

    restored = deserialize_restart(
        serialize_restart(first_committed),
        model=model,
        expected_adapter_id=adapter.adapter_id,
    )
    continuous_context = begin_step(first_committed, target_load_factor=0.75)
    restart_context = begin_step(restored, target_load_factor=0.75)
    displacement = _trial_vector(size, 0.4)
    continuous = evaluate_trial(
        continuous_context,
        adapter,
        model,
        trial_displacement=displacement,
        iteration_index=2,
    )
    restarted = evaluate_trial(
        restart_context,
        adapter,
        model,
        trial_displacement=displacement,
        iteration_index=2,
    )

    assert continuous.state.to_payload() == restarted.state.to_payload()
    np.testing.assert_array_equal(
        continuous.response.internal_force,
        restarted.response.internal_force,
    )
    continuous_commit = commit(continuous_context, continuous.state, converged=True)
    restarted_commit = commit(restart_context, restarted.state, converged=True)
    assert continuous_commit.to_payload() == restarted_commit.to_payload()
