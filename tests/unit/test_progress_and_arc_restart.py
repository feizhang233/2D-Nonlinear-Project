"""Progress callbacks and arc continuation payloads are stable public contracts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    ArcLengthIncrement,
    SolverCancelled,
    get_adapter,
    solve_load_control,
    validate_model_input,
)

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests" / "fixtures" / "p9" / "shallow-arch-snap-through.json"


def _model():
    validation = validate_model_input(json.loads(ARCH.read_text(encoding="utf-8")))
    assert validation.model is not None
    return validation.model


def test_load_solver_reports_real_step_and_iteration_indices():
    model = _model()
    progress = []

    solution = solve_load_control(
        get_adapter(model),
        model,
        target_load_factor=0.1,
        progress_callback=progress.append,
    )

    assert solution.succeeded
    assert progress
    assert progress[0].step_index == 1
    assert progress[0].iteration_index == 0
    assert progress[-1].accepted_steps == 0


def test_progress_callback_can_cooperatively_cancel_without_being_classified_as_numerics():
    model = _model()

    def cancel(_):
        raise SolverCancelled

    with pytest.raises(SolverCancelled):
        solve_load_control(
            get_adapter(model),
            model,
            target_load_factor=0.1,
            progress_callback=cancel,
        )


def test_arc_length_increment_payload_is_strict_and_round_trips():
    increment = ArcLengthIncrement(
        displacement=np.array([0.0, -0.1, 0.02]),
        load_factor=0.25,
        radius=0.12,
    )

    restored = ArcLengthIncrement.from_payload(increment.to_payload())

    assert np.array_equal(restored.displacement, increment.displacement)
    assert restored.load_factor == increment.load_factor
    assert restored.radius == increment.radius
    with pytest.raises(ValueError, match="unknown"):
        ArcLengthIncrement.from_payload({**increment.to_payload(), "unknown": 1})
