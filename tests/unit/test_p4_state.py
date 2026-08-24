"""Unit tests for immutable P4 state containers and authenticated restart data."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    StateFailureCode,
    StateTransitionError,
    begin_step,
    deserialize_restart,
    get_adapter,
    initialize_state,
    model_sha256,
    rollback,
    serialize_restart,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "tests" / "fixtures" / "adapters" / "frame-linear.json"


def _frame_model():
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    return result.model


def test_committed_state_owns_deeply_immutable_history_and_displacement():
    model = _frame_model()
    adapter = get_adapter(model)
    source_displacement = np.zeros(len(adapter.dof_map(model)))
    source_history = {"q": 0.2, "nested": {"marks": [0.2]}}

    state = initialize_state(
        adapter,
        model,
        displacement=source_displacement,
        history=source_history,
    )
    source_displacement[0] = 99.0
    source_history["q"] = 99.0
    source_history["nested"]["marks"].append(99.0)

    assert state.model_sha256 == model_sha256(model)
    assert state.step_index == 0
    assert state.iteration_index == 0
    assert state.displacement[0] == 0.0
    assert state.history["q"] == 0.2
    assert state.history["nested"]["marks"] == (0.2,)
    assert not state.displacement.flags.writeable
    with pytest.raises(ValueError):
        state.displacement[0] = 1.0
    with pytest.raises(TypeError):
        state.history["q"] = 1.0
    with pytest.raises(TypeError):
        state.history["nested"]["q"] = 1.0


def test_rollback_returns_exact_transaction_baseline():
    model = _frame_model()
    state = initialize_state(get_adapter(model), model)
    context = begin_step(state, target_load_factor=0.5)

    assert rollback(context) is state


def test_restart_round_trip_is_deterministic_and_model_authenticated():
    model = _frame_model()
    adapter = get_adapter(model)
    state = initialize_state(adapter, model, history={"q": 0.2, "marks": [1, 2]})

    encoded = serialize_restart(state)
    restored = deserialize_restart(
        encoded,
        model=model,
        expected_adapter_id=adapter.adapter_id,
    )

    assert restored.state_id == state.state_id
    assert restored.to_payload() == state.to_payload()
    assert serialize_restart(restored) == encoded
    assert not restored.displacement.flags.writeable
    assert restored.history["marks"] == (1, 2)


def test_restart_rejects_tampering_and_wrong_model():
    model = _frame_model()
    adapter = get_adapter(model)
    state = initialize_state(adapter, model, history={"q": 0.2})
    payload = json.loads(serialize_restart(state))
    payload["history"]["q"] = 0.9

    with pytest.raises(StateTransitionError) as tampered:
        deserialize_restart(json.dumps(payload))
    assert tampered.value.code is StateFailureCode.HASH_MISMATCH

    other_model = model.model_copy(update={"model_id": "other-frame"})
    with pytest.raises(StateTransitionError) as mismatch:
        deserialize_restart(serialize_restart(state), model=other_model)
    assert mismatch.value.code is StateFailureCode.MODEL_MISMATCH


def test_restart_rejects_unknown_fields_and_non_committed_documents():
    model = _frame_model()
    state = initialize_state(get_adapter(model), model)
    payload = json.loads(serialize_restart(state))
    payload["unexpected"] = True

    with pytest.raises(StateTransitionError) as unknown:
        deserialize_restart(json.dumps(payload))
    assert unknown.value.code is StateFailureCode.RESTART_INVALID

    payload.pop("unexpected")
    payload["state_type"] = "trial"
    with pytest.raises(StateTransitionError) as trial:
        deserialize_restart(json.dumps(payload))
    assert trial.value.code is StateFailureCode.RESTART_INVALID
