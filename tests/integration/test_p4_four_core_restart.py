"""P4 integration: the state transaction wrapper accepts all four P2 adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    begin_step,
    commit,
    deserialize_restart,
    evaluate_trial,
    get_adapter,
    initialize_state,
    serialize_restart,
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
def test_four_core_commits_restore_and_continue_identically(filename: str):
    model = _model(filename)
    adapter = get_adapter(model)
    initial = initialize_state(adapter, model)
    reference = adapter.native_reference(model)
    context = begin_step(initial, target_load_factor=1.0)
    trial = evaluate_trial(
        context,
        adapter,
        model,
        trial_displacement=reference.displacement,
        iteration_index=1,
    )
    committed = commit(context, trial.state, converged=True)
    restored = deserialize_restart(
        serialize_restart(committed),
        model=model,
        expected_adapter_id=adapter.adapter_id,
    )

    assert restored.to_payload() == committed.to_payload()
    continuous = evaluate_trial(
        begin_step(committed, target_load_factor=1.0),
        adapter,
        model,
        trial_displacement=reference.displacement,
        iteration_index=1,
    )
    restarted = evaluate_trial(
        begin_step(restored, target_load_factor=1.0),
        adapter,
        model,
        trial_displacement=reference.displacement,
        iteration_index=1,
    )
    np.testing.assert_array_equal(
        continuous.response.internal_force,
        restarted.response.internal_force,
    )
    assert continuous.state.to_payload() == restarted.state.to_payload()
