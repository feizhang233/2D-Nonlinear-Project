"""V08 spherical arc length, V04 limit point, and snap-back evidence."""

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
    ArcLengthIncrement,
    ArcLengthOptions,
    ArcLengthRootStatus,
    ControlMethod,
    DisplacementControlOptions,
    Dof,
    DofRef,
    LocalFailure,
    ModelFamily,
    ModelResponse,
    SolveStatus,
    StepControlOptions,
    StepStatus,
    ToleranceOptions,
    initialize_state,
    select_arc_length_root,
    solve_arc_length,
    solve_displacement_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "tests" / "fixtures" / "adapters" / "frame-linear.json"
ACTIVE_DOF = 3
SECOND_DOF = 4
THIRD_DOF = 5


def _base_model():
    result = validate_model_json(FRAME.read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    return result.model


def _arc_model(
    *,
    radius: float,
    min_radius: float | None = None,
    max_radius: float | None = None,
    max_steps: int = 30,
    max_retries: int = 8,
    target_iterations: int = 6,
):
    radius_min = radius if min_radius is None else min_radius
    radius_max = radius if max_radius is None else max_radius
    analysis = AnalysisOptions(
        control_method=ControlMethod.ARC_LENGTH,
        arc_length=ArcLengthOptions(
            radius=radius,
            min_radius=radius_min,
            max_radius=radius_max,
            beta=1.0,
        ),
        max_iterations=20,
        tolerances=ToleranceOptions(
            residual=1.0e-11,
            displacement=1.0e-11,
            energy=1.0e-11,
            linear_solver=1.0e-12,
        ),
        step_control=StepControlOptions(
            initial_step=0.1,
            min_step=0.01,
            max_step=0.2,
            max_steps=max_steps,
            max_retries=max_retries,
            target_iterations=target_iterations,
            cutback_factor=0.5,
            growth_factor=1.5,
        ),
    )
    return _base_model().model_copy(update={"analysis": analysis})


class OneDofAdapter:
    family = ModelFamily.FRAME
    adapter_id = "p8-one-dof"
    core_package = "p8-reference"
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
            state_id="p8-initial",
        )

    def dof_map(self, model):
        return model.ordered_dof_refs()

    def constraint_map(self, model):
        return {index: 0.0 for index in range(len(self.dof_map(model))) if index != ACTIVE_DOF}

    def internal_and_tangent(self, value: float) -> tuple[float, float]:
        return value - value**3, 1.0 - 3.0 * value**2

    def local_failures(self, value: float, committed_state) -> tuple[LocalFailure, ...]:
        return ()

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        value = float(values[ACTIVE_DOF])
        force, stiffness = self.internal_and_tangent(value)
        internal = np.zeros_like(values)
        external = np.zeros_like(values)
        tangent = np.eye(values.size)
        internal[ACTIVE_DOF] = force
        external[ACTIVE_DOF] = load_factor
        tangent[ACTIVE_DOF, ACTIVE_DOF] = stiffness
        digest = hashlib.sha256(f"{value:.17g}:{load_factor:.17g}".encode()).hexdigest()
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
                state_id=f"p8:{digest}",
                history={"active_displacement": value},
            ),
            elements=(),
            strain_energy=0.5 * value**2 - 0.25 * value**4,
            local_failures=self.local_failures(value, committed_state),
        )


class RadiusLimitedAdapter(OneDofAdapter):
    adapter_id = "p8-radius-limited"

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def internal_and_tangent(self, value: float) -> tuple[float, float]:
        return value, 1.0

    def local_failures(self, value: float, committed_state) -> tuple[LocalFailure, ...]:
        committed_value = (
            0.0
            if committed_state is None
            else float(committed_state.history.get("active_displacement", 0.0))
        )
        if abs(value - committed_value) <= self.threshold + 1.0e-14:
            return ()
        return (
            LocalFailure(
                code="ARC_INCREMENT_TOO_LARGE",
                message="reference local response requests a smaller arc radius",
                element_id="E1",
            ),
        )


class NonProportionalLoadAdapter(OneDofAdapter):
    adapter_id = "p8-non-proportional-load"

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        response = super().evaluate(
            model,
            displacement,
            load_factor=load_factor,
            committed_state=committed_state,
        )
        external = np.array(response.external_force, copy=True)
        external[ACTIVE_DOF] = load_factor**2
        return replace(response, external_force=external)


class BaselineFailureAdapter(OneDofAdapter):
    adapter_id = "p8-baseline-failure"

    def __init__(self) -> None:
        self.evaluation_count = 0

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        self.evaluation_count += 1
        if self.evaluation_count == 4:
            raise RuntimeError("intentional step-baseline evaluation failure")
        return super().evaluate(
            model,
            displacement,
            load_factor=load_factor,
            committed_state=committed_state,
        )


class V04ArcAdapter(OneDofAdapter):
    adapter_id = "p8-v04-limit-point"

    def internal_and_tangent(self, value: float) -> tuple[float, float]:
        sine = (8.0 - value) / 10.0
        theta = float(np.arcsin(sine))
        cosine = float(np.cos(theta))
        force = 5.0 * np.tan(theta) * (10.0 * cosine - 6.0)
        derivative_theta = 5.0 * (10.0 * cosine - 6.0 / cosine**2)
        derivative_displacement = -10.0 * cosine
        return force, derivative_theta / derivative_displacement


class SnapBackAdapter(OneDofAdapter):
    """Path lambda=x and c=x^2; the selected c coordinate reverses at x=0."""

    adapter_id = "p8-snap-back"

    def constraint_map(self, model):
        return {
            index: 0.0
            for index in range(len(self.dof_map(model)))
            if index not in (ACTIVE_DOF, SECOND_DOF, THIRD_DOF)
        }

    def evaluate(
        self,
        model,
        displacement,
        *,
        load_factor=1.0,
        committed_state=None,
    ):
        values = np.asarray(displacement, dtype=float)
        x_value = float(values[ACTIVE_DOF])
        control_value = float(values[SECOND_DOF])
        auxiliary_value = float(values[THIRD_DOF])
        internal = np.zeros_like(values)
        external = np.zeros_like(values)
        tangent = np.eye(values.size)
        internal[ACTIVE_DOF] = x_value
        internal[SECOND_DOF] = auxiliary_value
        internal[THIRD_DOF] = control_value - x_value**2
        external[ACTIVE_DOF] = load_factor
        tangent[SECOND_DOF, SECOND_DOF] = 0.0
        tangent[SECOND_DOF, THIRD_DOF] = 1.0
        tangent[THIRD_DOF, ACTIVE_DOF] = -2.0 * x_value
        tangent[THIRD_DOF, SECOND_DOF] = 1.0
        tangent[THIRD_DOF, THIRD_DOF] = 0.0
        digest = hashlib.sha256(
            (
                f"{x_value:.17g}:{control_value:.17g}:{auxiliary_value:.17g}:{load_factor:.17g}"
            ).encode()
        ).hexdigest()
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
                state_id=f"snap:{digest}",
                history={"x": x_value, "control": control_value},
            ),
            elements=(),
            strain_energy=0.0,
        )


def _initial_state(adapter, model, *, values: dict[int, float], load_factor: float = 0.0):
    displacement = np.zeros(len(adapter.dof_map(model)))
    for index, value in values.items():
        displacement[index] = value
    return initialize_state(
        adapter,
        model,
        displacement=displacement,
        load_factor=load_factor,
        history={
            "active_displacement": displacement[ACTIVE_DOF],
            "x": displacement[ACTIVE_DOF],
            "control": displacement[SECOND_DOF],
        },
    )


def test_v08_predictor_and_corrected_intersection_match_reference():
    model = _arc_model(radius=0.1)
    adapter = OneDofAdapter()

    solution = solve_arc_length(adapter, model)

    assert solution.result.status is SolveStatus.SUCCEEDED
    assert solution.committed_state is not None
    step = solution.result.steps[0]
    predictor = 0.1 / np.sqrt(2.0)
    assert step.response["predictor_displacement_increment"][ACTIVE_DOF] == pytest.approx(
        predictor, abs=1.0e-12
    )
    assert step.response["predictor_load_increment"] == pytest.approx(predictor, abs=1.0e-12)
    displacement = solution.committed_state.displacement[ACTIVE_DOF]
    load_factor = solution.committed_state.load_factor
    assert displacement == pytest.approx(0.0708885680, abs=2.0e-10)
    assert load_factor == pytest.approx(0.0705323396, abs=2.0e-10)
    assert load_factor - displacement + displacement**3 == pytest.approx(0.0, abs=1.0e-12)
    assert displacement**2 + load_factor**2 == pytest.approx(0.01, abs=1.0e-12)
    assert step.response["eta_arc"] <= model.analysis.tolerances.displacement
    assert step.response["eta_R"] <= model.analysis.tolerances.residual
    assert len(step.response["root_history"][0]["candidates"]) == 2
    assert step.response["linear_solves"] == 1 + 2 * len(step.iterations)
    assert step.response["linear_factorizations"] == 1 + len(step.iterations)


def test_root_selection_retains_candidates_and_rejects_complex_roots():
    first = select_arc_length_root(
        np.zeros(1),
        0.0,
        np.ones(1),
        np.zeros(1),
        np.ones(1),
        radius=0.1,
        beta=1.0,
    )
    assert first.status is ArcLengthRootStatus.SELECTED
    assert first.selected is not None
    assert first.selected.total_load_increment == pytest.approx(0.1 / np.sqrt(2.0))
    assert len(first.candidates) == 2

    previous = ArcLengthIncrement(
        displacement=first.selected.displacement_increment,
        load_factor=first.selected.total_load_increment,
        radius=0.1,
    )
    continued = select_arc_length_root(
        np.zeros(1),
        0.0,
        np.ones(1),
        np.zeros(1),
        np.ones(1),
        radius=0.1,
        beta=1.0,
        previous_increment=previous,
    )
    assert continued.selected is not None
    assert continued.selected.augmented_continuity > 0.0

    complex_result = select_arc_length_root(
        np.zeros(1),
        0.0,
        np.zeros(1),
        np.asarray([2.0]),
        np.ones(1),
        radius=1.0,
        beta=1.0,
    )
    assert complex_result.status is ArcLengthRootStatus.COMPLEX_ROOTS
    assert complex_result.discriminant < 0.0


def test_root_selection_is_scale_invariant_for_small_valid_directions():
    previous = ArcLengthIncrement(
        displacement=np.zeros(1),
        load_factor=1.0,
        radius=1.0e-8,
    )

    result = select_arc_length_root(
        np.zeros(1),
        0.0,
        np.zeros(1),
        np.zeros(1),
        np.asarray([1.0e-8]),
        radius=1.0e-8,
        beta=1.0,
        previous_increment=previous,
    )

    assert result.status is ArcLengthRootStatus.SELECTED
    assert result.selected is not None
    assert result.selected.total_load_increment == pytest.approx(1.0)
    assert result.selected.augmented_continuity == pytest.approx(1.0e-16)


def test_small_negative_discriminant_is_not_clamped_to_a_real_root():
    result = select_arc_length_root(
        np.zeros(1),
        0.0,
        np.zeros(1),
        np.asarray([2.0e-8]),
        np.asarray([1.0e-8]),
        radius=1.0e-8,
        beta=1.0,
    )

    assert result.status is ArcLengthRootStatus.COMPLEX_ROOTS
    assert result.discriminant == pytest.approx(-1.2e-31)


def test_root_coefficient_overflow_requests_model_rescaling():
    with pytest.raises(ValueError, match="coefficients overflowed; rescale the model"):
        select_arc_length_root(
            np.asarray([1.0e200]),
            0.0,
            np.ones(1),
            np.zeros(1),
            np.ones(1),
            radius=1.0e200,
            beta=1.0,
        )


def test_inconsistent_saved_increment_is_rejected_before_a_step_starts():
    model = _arc_model(radius=0.1)
    adapter = OneDofAdapter()
    displacement = np.zeros(len(adapter.dof_map(model)))
    displacement[ACTIVE_DOF] = 0.2
    previous = ArcLengthIncrement(displacement=displacement, load_factor=0.2, radius=0.1)

    solution = solve_arc_length(adapter, model, previous_increment=previous)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.steps == ()
    failure = solution.result.failures[0]
    assert failure.code.value == "STATE_ERROR"
    assert failure.details["retryable"] is False
    assert failure.details["radius_error"] > 0.1


def test_non_proportional_load_is_rejected_during_preflight():
    model = _arc_model(radius=0.1)

    solution = solve_arc_length(NonProportionalLoadAdapter(), model)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.result.steps == ()
    failure = solution.result.failures[0]
    assert failure.code.value == "CONTROL_ERROR"
    assert failure.details["retryable"] is False
    assert failure.details["proportional_load_error"] == pytest.approx(0.25)


def test_step_baseline_exception_is_classified_and_preserves_committed_state():
    model = _arc_model(radius=0.1)

    solution = solve_arc_length(BaselineFailureAdapter(), model)

    assert solution.result.status is SolveStatus.FAILED
    assert solution.committed_state is not None
    assert solution.committed_state.step_index == 0
    assert solution.committed_state.load_factor == 0.0
    assert len(solution.result.steps) == 1
    step = solution.result.steps[0]
    assert step.status is StepStatus.REJECTED
    assert step.response["adaptive_termination"] == "NONRETRYABLE_FAILURE"
    failure = solution.result.failures[0]
    assert failure.code.value == "STATE_ERROR"
    assert failure.details["retryable"] is False
    assert "step-baseline evaluation failure" in failure.message


def test_failed_large_radius_is_retained_then_cutback_recovers():
    model = _arc_model(radius=0.2, min_radius=0.05, max_radius=0.2)
    adapter = RadiusLimitedAdapter(threshold=0.12)
    initial = _initial_state(adapter, model, values={ACTIVE_DOF: 0.0})

    solution = solve_arc_length(adapter, model, initial_state=initial)

    assert solution.succeeded
    assert [step.status for step in solution.result.steps] == [
        StepStatus.REJECTED,
        StepStatus.ACCEPTED,
    ]
    rejected, accepted = solution.result.steps
    assert rejected.failure is not None
    assert rejected.response["arc_radius"] == pytest.approx(0.2)
    assert rejected.response["next_arc_radius"] == pytest.approx(0.1)
    assert rejected.response["will_retry"] is True
    assert accepted.response["arc_radius"] == pytest.approx(0.1)
    assert accepted.step_index == rejected.step_index
    assert solution.result.metadata["cutbacks"] == 1


def test_saved_increment_restarts_with_the_same_root_direction():
    model = _arc_model(radius=0.1, max_steps=2)
    adapter = OneDofAdapter()

    continuous = solve_arc_length(adapter, model, number_of_steps=2)
    first = solve_arc_length(adapter, model, number_of_steps=1)
    assert first.committed_state is not None and first.last_increment is not None
    restarted = solve_arc_length(
        adapter,
        model,
        number_of_steps=1,
        initial_state=first.committed_state,
        previous_increment=first.last_increment,
    )

    assert continuous.succeeded and restarted.succeeded
    assert continuous.committed_state is not None and restarted.committed_state is not None
    np.testing.assert_allclose(
        restarted.committed_state.displacement,
        continuous.committed_state.displacement,
        rtol=0.0,
        atol=1.0e-13,
    )
    assert restarted.committed_state.load_factor == pytest.approx(
        continuous.committed_state.load_factor,
        abs=1.0e-13,
    )
    assert restarted.result.steps[-1].response["attempt_index"] == 0


def test_strong_curvature_is_recorded_and_reduces_the_next_radius():
    model = _arc_model(radius=0.1, min_radius=0.05, max_radius=0.1)
    adapter = OneDofAdapter()
    displacement = np.zeros(len(adapter.dof_map(model)))
    displacement[ACTIVE_DOF] = 0.0743294146
    previous = ArcLengthIncrement(
        displacement=displacement,
        load_factor=-0.0668964731,
        radius=0.1,
    )

    solution = solve_arc_length(adapter, model, previous_increment=previous)

    assert solution.succeeded
    step = solution.result.steps[-1]
    assert step.response["strong_curvature"] is True
    assert step.response["next_arc_radius"] == pytest.approx(0.05)
    assert solution.result.metadata["curvature_reductions"] == 1


def test_repeated_failure_terminates_at_minimum_radius_with_all_attempts():
    model = _arc_model(radius=0.2, min_radius=0.05, max_radius=0.2)
    adapter = RadiusLimitedAdapter(threshold=0.0)

    solution = solve_arc_length(adapter, model)

    assert solution.result.status is SolveStatus.FAILED
    assert [step.response["arc_radius"] for step in solution.result.steps] == pytest.approx(
        [0.2, 0.1, 0.05]
    )
    assert all(step.status is StepStatus.REJECTED for step in solution.result.steps)
    final = solution.result.steps[-1]
    assert final.response["adaptive_termination"] == "MIN_RADIUS_REACHED"
    assert solution.result.failures[0].details["adaptive_termination"] == "MIN_RADIUS_REACHED"


def test_repeated_failure_honors_the_maximum_retry_count():
    model = _arc_model(
        radius=0.2,
        min_radius=0.01,
        max_radius=0.2,
        max_retries=1,
    )

    solution = solve_arc_length(RadiusLimitedAdapter(threshold=0.0), model)

    assert solution.result.status is SolveStatus.FAILED
    assert [step.response["arc_radius"] for step in solution.result.steps] == pytest.approx(
        [0.2, 0.1]
    )
    assert solution.result.steps[-1].response["adaptive_termination"] == "MAX_RETRIES_REACHED"
    assert solution.result.failures[0].details["retry_count"] == 1


def test_v04_arc_length_crosses_positive_load_limit():
    model = _arc_model(radius=0.75, min_radius=0.046875, max_radius=0.75, max_steps=30)
    adapter = V04ArcAdapter()
    initial = _initial_state(adapter, model, values={ACTIVE_DOF: 8.0}, load_factor=0.0)

    solution = solve_arc_length(
        adapter,
        model,
        number_of_steps=20,
        initial_state=initial,
    )

    assert solution.succeeded
    accepted = [step for step in solution.result.steps if step.status is StepStatus.ACCEPTED]
    displacements = [step.response["displacement"][ACTIVE_DOF] for step in accepted]
    loads = [step.load_factor for step in accepted]
    theta_limit = np.arccos(0.6 ** (1.0 / 3.0))
    displacement_limit = 8.0 - 10.0 * np.sin(theta_limit)
    load_limit = 5.0 * np.tan(theta_limit) * (10.0 * np.cos(theta_limit) - 6.0)
    assert min(displacements) < displacement_limit
    assert max(loads) == pytest.approx(load_limit, rel=2.0e-3)
    peak_index = int(np.argmax(loads))
    assert loads[-1] < loads[peak_index]
    assert displacements[-1] < displacements[peak_index]


def test_arc_length_continues_when_selected_displacement_control_cannot():
    adapter = SnapBackAdapter()
    arc_model = _arc_model(radius=0.1, min_radius=0.025, max_radius=0.1)
    arc_initial = _initial_state(
        adapter,
        arc_model,
        values={ACTIVE_DOF: -0.05, SECOND_DOF: 0.0025},
        load_factor=-0.05,
    )

    arc_solution = solve_arc_length(
        adapter,
        arc_model,
        number_of_steps=2,
        initial_state=arc_initial,
    )

    assert arc_solution.succeeded
    path = [
        (
            step.response["displacement"][ACTIVE_DOF],
            step.response["displacement"][SECOND_DOF],
        )
        for step in arc_solution.result.steps
        if step.status is StepStatus.ACCEPTED
    ]
    assert path[0][0] > 0.0
    assert path[0][1] < 0.0025
    assert path[1][1] > path[0][1]

    target = DofRef(node_id="N2", dof=Dof.UY)
    displacement_analysis = AnalysisOptions(
        control_method=ControlMethod.DISPLACEMENT,
        displacement_control=DisplacementControlOptions(target=target, increment=-0.005),
        max_iterations=10,
        tolerances=ToleranceOptions(
            residual=1.0e-11,
            displacement=1.0e-11,
            energy=1.0e-11,
            linear_solver=1.0e-12,
        ),
    )
    displacement_model = _base_model().model_copy(update={"analysis": displacement_analysis})
    displacement_initial = _initial_state(
        adapter,
        displacement_model,
        values={ACTIVE_DOF: -0.05, SECOND_DOF: 0.0025},
        load_factor=-0.05,
    )
    displacement_solution = solve_displacement_control(
        adapter,
        displacement_model,
        initial_state=displacement_initial,
    )

    assert displacement_solution.result.status is SolveStatus.FAILED
    assert displacement_solution.result.failures[0].code.value == "CONTROL_ERROR"
    assert displacement_solution.committed_state is displacement_initial
