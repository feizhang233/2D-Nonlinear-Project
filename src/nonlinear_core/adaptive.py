"""P7 adaptive growth, cutback, retry, and failure-disposition policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from nonlinear_core.adapters import ModelAdapter, ModelResponse
from nonlinear_core.constants import PACKAGE_VERSION
from nonlinear_core.displacement_control import (
    DisplacementControlSolution,
    solve_displacement_control,
)
from nonlinear_core.linear_solver import LinearSolveOptions
from nonlinear_core.load_control import LoadControlSolution, solve_load_control
from nonlinear_core.model import ControlMethod, ModelInput
from nonlinear_core.progress import ProgressCallback
from nonlinear_core.result import (
    FailureCode,
    FailureRecord,
    SolveResult,
    SolveStatus,
    StepResult,
)
from nonlinear_core.state import CommittedState, initialize_state, model_sha256


class FailureAction(StrEnum):
    RETRY_WITH_CUTBACK = "retry_with_cutback"
    TERMINATE = "terminate"


@dataclass(frozen=True, slots=True)
class FailureDisposition:
    code: FailureCode
    action: FailureAction
    reason: str

    @property
    def retryable(self) -> bool:
        return self.action is FailureAction.RETRY_WITH_CUTBACK


def failure_disposition(failure: FailureRecord) -> FailureDisposition:
    """Map every public failure class to an explicit P7 retry policy."""

    code = failure.code
    if code is FailureCode.STATE_ERROR:
        return FailureDisposition(
            code,
            FailureAction.TERMINATE,
            "state identity or rollback failures cannot be repaired by reducing step size",
        )
    if code is FailureCode.MODEL_ERROR:
        retryable = "min_det_f" in failure.details
        return FailureDisposition(
            code,
            FailureAction.RETRY_WITH_CUTBACK if retryable else FailureAction.TERMINATE,
            (
                "current-configuration geometry may recover after cutback"
                if retryable
                else "reference model or geometry errors are independent of step size"
            ),
        )
    reasons = {
        FailureCode.CONTROL_ERROR: "a smaller increment may remain inside the control path",
        FailureCode.TANGENT_ERROR: "a smaller increment may restore a usable tangent/search",
        FailureCode.LINEAR_SOLVE_ERROR: "a smaller increment may improve the linearized system",
        FailureCode.LOCAL_MATERIAL_ERROR: "a smaller increment may recover local integration",
        FailureCode.NONCONVERGENCE: "a smaller increment may enter the Newton convergence radius",
    }
    return FailureDisposition(code, FailureAction.RETRY_WITH_CUTBACK, reasons[code])


def _annotate_step(
    step: StepResult,
    *,
    attempt_index: int,
    current_step_size: float,
    next_step_size: float | None,
    will_retry: bool,
    adaptive_termination: str | None = None,
    failure: FailureRecord | None = None,
) -> StepResult:
    response = dict(step.response)
    response.update(
        {
            "attempt_index": attempt_index,
            "adaptive_step_size": current_step_size,
            "next_step_size": next_step_size,
            "will_retry": will_retry,
            "adaptive_termination": adaptive_termination,
        }
    )
    updates: dict[str, object] = {"response": response}
    if failure is not None:
        updates["failure"] = failure
    return step.model_copy(update=updates)


def _aggregate(
    model: ModelInput,
    *,
    control_method: ControlMethod,
    status: SolveStatus,
    steps: list[StepResult],
    failures: list[FailureRecord],
    metadata: dict[str, object],
) -> SolveResult:
    return SolveResult(
        model_id=model.model_id,
        model_sha256=model_sha256(model),
        solver_version=PACKAGE_VERSION,
        status=status,
        steps=tuple(steps),
        failures=tuple(failures),
        metadata={
            "control_method": control_method.value,
            "adaptive_step_control": True,
            **metadata,
        },
    )


def _terminal_failure(
    failure: FailureRecord,
    *,
    termination: str,
    current_step_size: float,
    retry_count: int,
) -> FailureRecord:
    details = dict(failure.details)
    details.update(
        {
            "adaptive_termination": termination,
            "terminal_step_size": current_step_size,
            "retry_count": retry_count,
        }
    )
    return failure.model_copy(update={"details": details})


def solve_adaptive_load_control(
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    target_load_factor: float = 1.0,
    initial_state: CommittedState | None = None,
    linear_options: LinearSolveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> LoadControlSolution:
    """Advance load control with growth after fast convergence and cutback on rejection."""

    start_factor = 0.0 if initial_state is None else initial_state.load_factor
    probe = solve_load_control(
        adapter,
        model,
        target_load_factor=start_factor,
        initial_state=initial_state,
        linear_options=linear_options,
        progress_callback=progress_callback,
    )
    if not probe.succeeded or probe.committed_state is None:
        return probe
    try:
        target = float(target_load_factor)
    except (TypeError, ValueError, OverflowError):
        target = float("nan")
    if not np.isfinite(target):
        return solve_load_control(
            adapter,
            model,
            target_load_factor=target_load_factor,
            initial_state=probe.committed_state,
            linear_options=linear_options,
            progress_callback=progress_callback,
        )

    controls = model.analysis.step_control
    committed = probe.committed_state
    final_response: ModelResponse | None = probe.final_response
    all_steps: list[StepResult] = []
    current_size = float(controls.initial_step)
    retry_count = 0
    accepted_steps = 0
    cutbacks = 0
    growths = 0
    tolerance = np.finfo(float).eps * max(1.0, abs(target)) * 8.0

    while abs(target - committed.load_factor) > tolerance:
        if accepted_steps >= controls.max_steps:
            failure = FailureRecord(
                code=FailureCode.CONTROL_ERROR,
                message="maximum accepted load-step count reached before target",
                step_index=committed.step_index + 1,
                details={
                    "adaptive_termination": "MAX_STEPS_REACHED",
                    "accepted_steps": accepted_steps,
                    "target_load_factor": target,
                    "current_load_factor": committed.load_factor,
                },
            )
            result = _aggregate(
                model,
                control_method=ControlMethod.LOAD,
                status=SolveStatus.FAILED,
                steps=all_steps,
                failures=[failure],
                metadata={"cutbacks": cutbacks, "growths": growths},
            )
            return LoadControlSolution(result, committed, final_response)

        remaining = target - committed.load_factor
        attempt_size = min(current_size, abs(remaining))
        attempt_target = committed.load_factor + float(np.copysign(attempt_size, remaining))
        attempt = solve_load_control(
            adapter,
            model,
            target_load_factor=attempt_target,
            initial_state=committed,
            linear_options=linear_options,
            progress_callback=progress_callback,
            _step_size_override=attempt_size,
        )
        step = attempt.result.steps[-1] if attempt.result.steps else None
        if attempt.succeeded and attempt.committed_state is not None and step is not None:
            iterations = len(step.iterations)
            next_size = current_size
            if iterations <= controls.target_iterations:
                grown = min(float(controls.max_step), current_size * controls.growth_factor)
                if grown > current_size:
                    growths += 1
                next_size = grown
            all_steps.append(
                _annotate_step(
                    step,
                    attempt_index=retry_count,
                    current_step_size=attempt_size,
                    next_step_size=next_size,
                    will_retry=False,
                )
            )
            committed = attempt.committed_state
            final_response = attempt.final_response
            current_size = next_size
            retry_count = 0
            accepted_steps += 1
            continue

        failure = attempt.result.failures[0]
        disposition = failure_disposition(failure)
        at_minimum = attempt_size <= controls.min_step * (1.0 + 1.0e-12)
        retries_exhausted = retry_count >= controls.max_retries
        will_retry = disposition.retryable and not at_minimum and not retries_exhausted
        next_size = (
            max(float(controls.min_step), attempt_size * controls.cutback_factor)
            if will_retry
            else None
        )
        termination = None
        terminal_failure = failure
        if not will_retry:
            if not disposition.retryable:
                termination = "NONRETRYABLE_FAILURE"
            elif at_minimum:
                termination = "MIN_STEP_REACHED"
            else:
                termination = "MAX_RETRIES_REACHED"
            terminal_failure = _terminal_failure(
                failure,
                termination=termination,
                current_step_size=attempt_size,
                retry_count=retry_count,
            )
        if step is not None:
            all_steps.append(
                _annotate_step(
                    step,
                    attempt_index=retry_count,
                    current_step_size=attempt_size,
                    next_step_size=next_size,
                    will_retry=will_retry,
                    adaptive_termination=termination,
                    failure=None if will_retry else terminal_failure,
                )
            )
        if not will_retry:
            result = _aggregate(
                model,
                control_method=ControlMethod.LOAD,
                status=SolveStatus.FAILED,
                steps=all_steps,
                failures=[terminal_failure],
                metadata={"cutbacks": cutbacks, "growths": growths},
            )
            return LoadControlSolution(result, committed, final_response)
        assert next_size is not None
        current_size = next_size
        retry_count += 1
        cutbacks += 1

    result = _aggregate(
        model,
        control_method=ControlMethod.LOAD,
        status=SolveStatus.SUCCEEDED,
        steps=all_steps,
        failures=[],
        metadata={
            "target_load_factor": target,
            "accepted_steps": accepted_steps,
            "rejected_attempts": sum(step.status.value == "rejected" for step in all_steps),
            "cutbacks": cutbacks,
            "growths": growths,
        },
    )
    return LoadControlSolution(result, committed, final_response)


def solve_adaptive_displacement_control(
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    number_of_steps: int = 1,
    initial_state: CommittedState | None = None,
    linear_options: LinearSolveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> DisplacementControlSolution:
    """Advance displacement control with scaled growth and cutback multipliers."""

    if (
        isinstance(number_of_steps, bool)
        or not isinstance(number_of_steps, int)
        or number_of_steps < 1
        or number_of_steps > model.analysis.step_control.max_steps
    ):
        return solve_displacement_control(
            adapter,
            model,
            number_of_steps=number_of_steps,
            initial_state=initial_state,
            linear_options=linear_options,
            progress_callback=progress_callback,
        )
    try:
        committed = initial_state or initialize_state(adapter, model)
    except (RuntimeError, TypeError, ValueError):
        return solve_displacement_control(
            adapter,
            model,
            number_of_steps=1,
            initial_state=initial_state,
            linear_options=linear_options,
            progress_callback=progress_callback,
        )
    settings = model.analysis.displacement_control
    if settings is None:
        return solve_displacement_control(
            adapter,
            model,
            number_of_steps=1,
            initial_state=committed,
            linear_options=linear_options,
            progress_callback=progress_callback,
        )

    controls = model.analysis.step_control
    direction = float(np.sign(settings.increment))
    base_size = abs(float(settings.increment))
    minimum = base_size * controls.min_step / controls.initial_step
    maximum = base_size * controls.max_step / controls.initial_step
    current_size = base_size
    final_response: ModelResponse | None = None
    all_steps: list[StepResult] = []
    retry_count = 0
    accepted_steps = 0
    cutbacks = 0
    growths = 0

    while accepted_steps < number_of_steps:
        attempt = solve_displacement_control(
            adapter,
            model,
            number_of_steps=1,
            initial_state=committed,
            linear_options=linear_options,
            progress_callback=progress_callback,
            _increment_override=direction * current_size,
        )
        step = attempt.result.steps[-1] if attempt.result.steps else None
        if attempt.succeeded and attempt.committed_state is not None and step is not None:
            iterations = len(step.iterations)
            next_size = current_size
            if iterations <= controls.target_iterations:
                grown = min(maximum, current_size * controls.growth_factor)
                if grown > current_size:
                    growths += 1
                next_size = grown
            all_steps.append(
                _annotate_step(
                    step,
                    attempt_index=retry_count,
                    current_step_size=current_size,
                    next_step_size=next_size,
                    will_retry=False,
                )
            )
            committed = attempt.committed_state
            final_response = attempt.final_response
            current_size = next_size
            retry_count = 0
            accepted_steps += 1
            continue

        failure = attempt.result.failures[0]
        disposition = failure_disposition(failure)
        at_minimum = current_size <= minimum * (1.0 + 1.0e-12)
        retries_exhausted = retry_count >= controls.max_retries
        will_retry = disposition.retryable and not at_minimum and not retries_exhausted
        next_size = max(minimum, current_size * controls.cutback_factor) if will_retry else None
        termination = None
        terminal_failure = failure
        if not will_retry:
            if not disposition.retryable:
                termination = "NONRETRYABLE_FAILURE"
            elif at_minimum:
                termination = "MIN_STEP_REACHED"
            else:
                termination = "MAX_RETRIES_REACHED"
            terminal_failure = _terminal_failure(
                failure,
                termination=termination,
                current_step_size=current_size,
                retry_count=retry_count,
            )
        if step is not None:
            all_steps.append(
                _annotate_step(
                    step,
                    attempt_index=retry_count,
                    current_step_size=current_size,
                    next_step_size=next_size,
                    will_retry=will_retry,
                    adaptive_termination=termination,
                    failure=None if will_retry else terminal_failure,
                )
            )
        if not will_retry:
            result = _aggregate(
                model,
                control_method=ControlMethod.DISPLACEMENT,
                status=SolveStatus.FAILED,
                steps=all_steps,
                failures=[terminal_failure],
                metadata={"cutbacks": cutbacks, "growths": growths},
            )
            return DisplacementControlSolution(result, committed, final_response)
        assert next_size is not None
        current_size = next_size
        retry_count += 1
        cutbacks += 1

    result = _aggregate(
        model,
        control_method=ControlMethod.DISPLACEMENT,
        status=SolveStatus.SUCCEEDED,
        steps=all_steps,
        failures=[],
        metadata={
            "requested_steps": number_of_steps,
            "accepted_steps": accepted_steps,
            "rejected_attempts": sum(step.status.value == "rejected" for step in all_steps),
            "cutbacks": cutbacks,
            "growths": growths,
            "minimum_increment": minimum,
            "maximum_increment": maximum,
        },
    )
    return DisplacementControlSolution(result, committed, final_response)


__all__ = [
    "FailureAction",
    "FailureDisposition",
    "failure_disposition",
    "solve_adaptive_displacement_control",
    "solve_adaptive_load_control",
]
