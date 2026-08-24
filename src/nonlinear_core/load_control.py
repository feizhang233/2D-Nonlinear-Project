"""P5 Newton iteration and fixed-increment load-control driver."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from nonlinear_core.adapters import ModelAdapter, ModelResponse
from nonlinear_core.constants import PACKAGE_VERSION
from nonlinear_core.equilibrium import (
    EquilibriumEvaluation,
    build_equilibrium,
    solve_constrained_correction,
)
from nonlinear_core.globalization import LineSearchStatus, apply_line_search
from nonlinear_core.linear_solver import (
    LinearFailureCode,
    LinearSolveOptions,
)
from nonlinear_core.model import ControlMethod, ModelInput, NewtonMethod
from nonlinear_core.progress import ProgressCallback, emit_progress
from nonlinear_core.result import (
    FailureCode,
    FailureRecord,
    IterationRecord,
    IterationStatus,
    SolveResult,
    SolveStatus,
    StepResult,
    StepStatus,
)
from nonlinear_core.state import (
    CommittedState,
    StateTransitionError,
    begin_step,
    commit,
    evaluate_trial,
    initialize_state,
    model_sha256,
    rollback,
)


@dataclass(frozen=True, slots=True)
class ConvergenceMetrics:
    """Scaled P5 convergence indicators and their dimensional evidence."""

    eta_residual: float
    eta_displacement: float
    eta_energy: float
    residual_norm: float
    correction_norm: float
    energy_work: float
    force_scale: float
    displacement_scale: float
    energy_scale: float


@dataclass(frozen=True, slots=True)
class LoadControlSolution:
    """Serializable solve evidence plus the last safely committed runtime state."""

    result: SolveResult
    committed_state: CommittedState | None
    final_response: ModelResponse | None

    @property
    def succeeded(self) -> bool:
        return self.result.status is SolveStatus.SUCCEEDED


def convergence_metrics(
    evaluation: EquilibriumEvaluation,
    current_displacement: ArrayLike,
    correction: ArrayLike,
    model: ModelInput,
) -> ConvergenceMetrics:
    """Evaluate the guide's ``eta_R``, ``eta_u`` and ``eta_E`` on free DOFs."""

    current = np.asarray(current_displacement, dtype=float)
    update = np.asarray(correction, dtype=float)
    size = evaluation.partition.size
    if current.shape != (size,) or update.shape != (size,):
        raise ValueError("current displacement and correction must match the equilibrium size")
    free = evaluation.partition.free_dofs
    residual = evaluation.free_residual
    external = evaluation.response.external_force[free]
    internal = evaluation.response.internal_force[free]
    free_update = update[free]
    free_current = current[free]
    tolerances = model.analysis.tolerances

    residual_norm = float(np.linalg.norm(residual))
    correction_norm = float(np.linalg.norm(free_update))
    energy_work = float(abs(free_update @ residual))
    force_scale = float(
        np.linalg.norm(external) + np.linalg.norm(internal) + tolerances.force_floor
    )
    displacement_scale = float(np.linalg.norm(free_current) + tolerances.displacement_floor)
    energy_scale = float(abs(free_update @ external) + tolerances.energy_floor)
    values = np.asarray(
        [
            residual_norm,
            correction_norm,
            energy_work,
            force_scale,
            displacement_scale,
            energy_scale,
        ]
    )
    if not np.all(np.isfinite(values)):
        raise ValueError("convergence metrics contain NaN or Inf")
    return ConvergenceMetrics(
        eta_residual=residual_norm / force_scale,
        eta_displacement=correction_norm / displacement_scale,
        eta_energy=energy_work / energy_scale,
        residual_norm=residual_norm,
        correction_norm=correction_norm,
        energy_work=energy_work,
        force_scale=force_scale,
        displacement_scale=displacement_scale,
        energy_scale=energy_scale,
    )


def _failure(
    code: FailureCode,
    message: str,
    *,
    step_index: int | None = None,
    iteration_index: int | None = None,
    details: dict[str, Any] | None = None,
) -> FailureRecord:
    return FailureRecord(
        code=code,
        message=message,
        step_index=step_index,
        iteration_index=iteration_index,
        details=details or {},
    )


def _result(
    model: ModelInput,
    *,
    status: SolveStatus,
    steps: list[StepResult],
    failures: list[FailureRecord],
    target_load_factor: float,
) -> SolveResult:
    return SolveResult(
        model_id=model.model_id,
        model_sha256=model_sha256(model),
        solver_version=PACKAGE_VERSION,
        status=status,
        steps=tuple(steps),
        failures=tuple(failures),
        metadata={
            "control_method": ControlMethod.LOAD.value,
            "newton_method": model.analysis.newton_method.value,
            "target_load_factor": target_load_factor,
            "fixed_step_size": model.analysis.step_control.initial_step,
            "automatic_cutback": False,
        },
    )


def _solution_failure(
    model: ModelInput,
    failure: FailureRecord,
    *,
    state: CommittedState | None,
    response: ModelResponse | None,
    steps: list[StepResult],
    target_load_factor: float,
) -> LoadControlSolution:
    return LoadControlSolution(
        result=_result(
            model,
            status=SolveStatus.FAILED,
            steps=steps,
            failures=[failure],
            target_load_factor=target_load_factor,
        ),
        committed_state=state,
        final_response=response,
    )


def _response_failure(
    response: ModelResponse,
    *,
    step_index: int,
    iteration_index: int,
) -> FailureRecord | None:
    scalar_diagnostics = {
        "strain_energy": response.strain_energy,
        "min_det_j": response.min_det_j,
        "min_det_f": response.min_det_f,
    }
    for element in response.elements:
        scalar_diagnostics[f"element:{element.element_id}:energy"] = element.energy
        scalar_diagnostics[f"element:{element.element_id}:min_det_j"] = element.min_det_j
        scalar_diagnostics[f"element:{element.element_id}:min_det_f"] = element.min_det_f
    nonfinite = {
        name: str(value)
        for name, value in scalar_diagnostics.items()
        if value is not None and not np.isfinite(value)
    }
    if nonfinite:
        return _failure(
            FailureCode.TANGENT_ERROR,
            "adapter response diagnostics contain NaN or Inf",
            step_index=step_index,
            iteration_index=iteration_index,
            details={"nonfinite_diagnostics": nonfinite},
        )
    local_failures = list(response.local_failures)
    for element in response.elements:
        local_failures.extend(element.local_failures)
    if local_failures:
        return _failure(
            FailureCode.LOCAL_MATERIAL_ERROR,
            "element or material-point evaluation reported a local failure",
            step_index=step_index,
            iteration_index=iteration_index,
            details={
                "local_failures": [
                    {
                        "code": item.code,
                        "message": item.message,
                        "element_id": item.element_id,
                    }
                    for item in local_failures
                ]
            },
        )
    if response.min_det_j is not None and response.min_det_j <= 0.0:
        return _failure(
            FailureCode.MODEL_ERROR,
            "element reference mapping has non-positive detJ",
            step_index=step_index,
            iteration_index=iteration_index,
            details={"min_det_j": response.min_det_j},
        )
    if response.min_det_f is not None and response.min_det_f <= 0.0:
        return _failure(
            FailureCode.MODEL_ERROR,
            "current configuration has non-positive detF",
            step_index=step_index,
            iteration_index=iteration_index,
            details={"min_det_f": response.min_det_f},
        )
    return None


def _reuse_tangent(
    current: EquilibriumEvaluation,
    frozen: EquilibriumEvaluation,
) -> EquilibriumEvaluation:
    return EquilibriumEvaluation(
        response=current.response,
        partition=current.partition,
        residual=current.residual,
        free_residual=current.free_residual,
        constrained_residual=current.constrained_residual,
        effective_tangent=frozen.effective_tangent,
        tangent_diagnostics=frozen.tangent_diagnostics,
    )


def _iteration_record(
    *,
    step_index: int,
    iteration_index: int,
    load_factor: float,
    current_displacement: np.ndarray,
    evaluation: EquilibriumEvaluation,
    correction: np.ndarray,
    metrics: ConvergenceMetrics,
    linear_residual_norm: float,
    linear_relative_residual: float,
    tangent_reassembled: bool,
    tangent_assemblies: int,
    status: IterationStatus,
    termination_reason: str,
    accepted_alpha: float = 1.0,
    line_search_diagnostics: dict[str, Any] | None = None,
) -> IterationRecord:
    diagonal = np.diag(evaluation.effective_tangent)
    return IterationRecord(
        step_index=step_index,
        iteration_index=iteration_index,
        load_factor=load_factor,
        residual_norm=metrics.eta_residual,
        displacement_correction_norm=metrics.eta_displacement,
        energy_norm=metrics.eta_energy,
        linear_residual_norm=linear_residual_norm,
        accepted_alpha=accepted_alpha,
        tangent_reassembled=tangent_reassembled,
        status=status,
        diagnostics={
            "eta_R": metrics.eta_residual,
            "eta_u": metrics.eta_displacement,
            "eta_E": metrics.eta_energy,
            "raw_residual_norm": metrics.residual_norm,
            "raw_correction_norm": metrics.correction_norm,
            "raw_energy_work": metrics.energy_work,
            "force_scale": metrics.force_scale,
            "displacement_scale": metrics.displacement_scale,
            "energy_scale": metrics.energy_scale,
            "linear_relative_residual": linear_relative_residual,
            "displacement": [float(value) for value in current_displacement],
            "residual": [float(value) for value in evaluation.residual],
            "correction": [float(value) for value in correction],
            "effective_tangent_diagonal": [float(value) for value in diagonal],
            "tangent_symmetry_error": evaluation.tangent_diagnostics.symmetry_error,
            "tangent_assemblies": tangent_assemblies,
            "termination_reason": termination_reason,
            "line_search": line_search_diagnostics
            or {
                "enabled": False,
                "merit_function": "full_step",
                "evaluations": 0,
            },
        },
    )


def _basic_iteration_record(
    *,
    step_index: int,
    iteration_index: int,
    load_factor: float,
    tangent_reassembled: bool,
    tangent_assemblies: int,
    reason: str,
    details: dict[str, Any] | None = None,
) -> IterationRecord:
    diagnostics: dict[str, Any] = {
        "tangent_assemblies": tangent_assemblies,
        "termination_reason": reason,
    }
    diagnostics.update(details or {})
    return IterationRecord(
        step_index=step_index,
        iteration_index=iteration_index,
        load_factor=load_factor,
        residual_norm=0.0,
        displacement_correction_norm=0.0,
        energy_norm=0.0,
        linear_residual_norm=0.0,
        tangent_reassembled=tangent_reassembled,
        status=IterationStatus.REJECTED,
        diagnostics=diagnostics,
    )


def _linear_failure_code(linear_code: LinearFailureCode | None) -> FailureCode:
    if linear_code in {
        LinearFailureCode.SINGULAR_SYSTEM,
        LinearFailureCode.ILL_CONDITIONED_SYSTEM,
    }:
        return FailureCode.CONTROL_ERROR
    return FailureCode.LINEAR_SOLVE_ERROR


def solve_load_control(
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    target_load_factor: float = 1.0,
    initial_state: CommittedState | None = None,
    linear_options: LinearSolveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
    _step_size_override: float | None = None,
) -> LoadControlSolution:
    """Solve fixed load-factor increments without P7 retry/cutback behavior."""

    try:
        target = float(target_load_factor)
    except (TypeError, ValueError, OverflowError):
        target = float("nan")
    if not np.isfinite(target):
        failure = _failure(FailureCode.CONTROL_ERROR, "target_load_factor must be finite")
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            target_load_factor=0.0,
        )
    if model.analysis.control_method is not ControlMethod.LOAD:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "P5 solve_load_control requires control_method='load'",
            details={"configured_control_method": model.analysis.control_method.value},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            target_load_factor=target,
        )
    validation = adapter.validate(model)
    if not validation.valid:
        failure = _failure(
            FailureCode.MODEL_ERROR,
            "adapter rejected the model",
            details={
                "adapter_errors": [
                    {"code": issue.code, "message": issue.message, "entity_id": issue.entity_id}
                    for issue in validation.errors
                ]
            },
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            target_load_factor=target,
        )

    try:
        committed = initial_state or initialize_state(adapter, model)
        if (
            committed.model_id != model.model_id
            or committed.model_sha256 != model_sha256(model)
            or committed.adapter_id != adapter.adapter_id
        ):
            raise ValueError("initial_state does not match the model and adapter")
    except (StateTransitionError, ValueError) as error:
        failure = _failure(FailureCode.STATE_ERROR, str(error))
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            target_load_factor=target,
        )

    steps: list[StepResult] = []
    final_response: ModelResponse | None = None
    tolerance = model.analysis.tolerances
    settings = replace(
        linear_options or LinearSolveOptions(),
        relative_residual_tolerance=tolerance.linear_solver,
    )
    step_size = (
        model.analysis.step_control.initial_step
        if _step_size_override is None
        else float(_step_size_override)
    )
    if not np.isfinite(step_size) or step_size <= 0.0:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "load step size must be positive and finite",
            details={"step_size": str(step_size)},
        )
        return _solution_failure(
            model,
            failure,
            state=committed,
            response=None,
            steps=steps,
            target_load_factor=target,
        )
    target_tolerance = np.finfo(float).eps * max(1.0, abs(target)) * 8.0

    for _ in range(model.analysis.step_control.max_steps):
        remaining = target - committed.load_factor
        if abs(remaining) <= target_tolerance:
            return LoadControlSolution(
                result=_result(
                    model,
                    status=SolveStatus.SUCCEEDED,
                    steps=steps,
                    failures=[],
                    target_load_factor=target,
                ),
                committed_state=committed,
                final_response=final_response,
            )
        increment = float(np.copysign(min(step_size, abs(remaining)), remaining))
        step_target = committed.load_factor + increment
        context = begin_step(
            committed,
            target_load_factor=step_target,
            predictor_displacement=committed.displacement,
        )
        current = np.array(context.predictor_displacement, copy=True)
        iteration_records: list[IterationRecord] = []
        frozen_evaluation: EquilibriumEvaluation | None = None
        tangent_assemblies = 0
        last_trial = None

        for iteration_index in range(model.analysis.max_iterations + 1):
            emit_progress(
                progress_callback,
                step_index=context.step_index,
                iteration_index=iteration_index,
                accepted_steps=sum(step.status is StepStatus.ACCEPTED for step in steps),
            )
            tangent_reassembled = (
                model.analysis.newton_method is NewtonMethod.FULL or frozen_evaluation is None
            )
            if tangent_reassembled:
                tangent_assemblies += 1
            try:
                trial = evaluate_trial(
                    context,
                    adapter,
                    model,
                    trial_displacement=current,
                    iteration_index=iteration_index,
                )
                last_trial = trial
                current_evaluation = build_equilibrium(
                    trial.response,
                    adapter.constraint_map(model),
                )
            except StateTransitionError as error:
                failure = _failure(
                    FailureCode.STATE_ERROR,
                    str(error),
                    step_index=context.step_index,
                    iteration_index=iteration_index,
                    details={"state_code": error.code.value},
                )
                iteration_records.append(
                    _basic_iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=step_target,
                        tangent_reassembled=tangent_reassembled,
                        tangent_assemblies=tangent_assemblies,
                        reason=failure.code.value,
                    )
                )
                break
            except (
                ArithmeticError,
                np.linalg.LinAlgError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                failure = _failure(
                    FailureCode.TANGENT_ERROR,
                    f"non-finite or invalid adapter response: {error}",
                    step_index=context.step_index,
                    iteration_index=iteration_index,
                )
                iteration_records.append(
                    _basic_iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=step_target,
                        tangent_reassembled=tangent_reassembled,
                        tangent_assemblies=tangent_assemblies,
                        reason=failure.code.value,
                    )
                )
                break

            diagnostic_failure = _response_failure(
                trial.response,
                step_index=context.step_index,
                iteration_index=iteration_index,
            )
            if diagnostic_failure is not None:
                failure = diagnostic_failure
                iteration_records.append(
                    _basic_iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=step_target,
                        tangent_reassembled=tangent_reassembled,
                        tangent_assemblies=tangent_assemblies,
                        reason=failure.code.value,
                        details={
                            **failure.details,
                            "residual": [float(value) for value in current_evaluation.residual],
                            "raw_residual_norm": float(
                                np.linalg.norm(current_evaluation.free_residual)
                            ),
                        },
                    )
                )
                break

            if frozen_evaluation is None:
                frozen_evaluation = current_evaluation
            evaluation = (
                current_evaluation
                if model.analysis.newton_method is NewtonMethod.FULL
                else _reuse_tangent(current_evaluation, frozen_evaluation)
            )
            if float(np.linalg.norm(evaluation.free_residual)) == 0.0:
                correction = np.zeros(evaluation.partition.size)
                linear_residual_norm = 0.0
                linear_relative_residual = 0.0
            else:
                correction_result = solve_constrained_correction(
                    evaluation,
                    current,
                    settings,
                )
                if not correction_result.succeeded:
                    linear_failure = correction_result.linear_result.failure
                    linear_code = None if linear_failure is None else linear_failure.code
                    failure_code = _linear_failure_code(linear_code)
                    message = (
                        "load control cannot continue through a singular or ill-conditioned "
                        "tangent; use a smaller step or a path-capable control method"
                        if failure_code is FailureCode.CONTROL_ERROR
                        else "Newton correction linear solve failed"
                    )
                    failure = _failure(
                        failure_code,
                        message,
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        details={
                            "linear_failure_code": (
                                None if linear_code is None else linear_code.value
                            ),
                            "linear_failure_message": (
                                None if linear_failure is None else linear_failure.message
                            ),
                            "condition_estimate": (
                                None
                                if correction_result.linear_result.condition_estimate is None
                                or not np.isfinite(
                                    correction_result.linear_result.condition_estimate
                                )
                                else correction_result.linear_result.condition_estimate
                            ),
                        },
                    )
                    iteration_records.append(
                        _basic_iteration_record(
                            step_index=context.step_index,
                            iteration_index=iteration_index,
                            load_factor=step_target,
                            tangent_reassembled=tangent_reassembled,
                            tangent_assemblies=tangent_assemblies,
                            reason=failure.code.value,
                            details={
                                **failure.details,
                                "residual": [float(value) for value in evaluation.residual],
                                "raw_residual_norm": float(
                                    np.linalg.norm(evaluation.free_residual)
                                ),
                                "effective_tangent_diagonal": [
                                    float(value) for value in np.diag(evaluation.effective_tangent)
                                ],
                            },
                        )
                    )
                    break
                assert correction_result.correction is not None
                correction = np.asarray(correction_result.correction)
                linear = correction_result.linear_result
                linear_residual_norm = float(linear.residual_norm or 0.0)
                linear_relative_residual = float(linear.relative_residual or 0.0)

            try:
                metrics = convergence_metrics(evaluation, current, correction, model)
            except ValueError as error:
                failure = _failure(
                    FailureCode.TANGENT_ERROR,
                    str(error),
                    step_index=context.step_index,
                    iteration_index=iteration_index,
                )
                iteration_records.append(
                    _basic_iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=step_target,
                        tangent_reassembled=tangent_reassembled,
                        tangent_assemblies=tangent_assemblies,
                        reason=failure.code.value,
                    )
                )
                break

            converged = (
                metrics.eta_residual <= tolerance.residual
                and metrics.eta_displacement <= tolerance.displacement
                and metrics.eta_energy <= tolerance.energy
                and linear_relative_residual <= tolerance.linear_solver
            )
            accepted_alpha = 1.0
            line_search_diagnostics: dict[str, Any] = {
                "enabled": False,
                "merit_function": "full_step",
                "evaluations": 0,
            }
            if converged:
                iteration_records.append(
                    _iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=step_target,
                        current_displacement=current,
                        evaluation=evaluation,
                        correction=correction,
                        metrics=metrics,
                        linear_residual_norm=linear_residual_norm,
                        linear_relative_residual=linear_relative_residual,
                        tangent_reassembled=tangent_reassembled,
                        tangent_assemblies=tangent_assemblies,
                        status=IterationStatus.CONVERGED,
                        termination_reason="CONVERGED",
                        accepted_alpha=accepted_alpha,
                        line_search_diagnostics=line_search_diagnostics,
                    )
                )
                committed = commit(context, trial.state, converged=True)
                final_response = trial.response
                steps.append(
                    StepResult(
                        step_index=context.step_index,
                        status=StepStatus.ACCEPTED,
                        control_method=ControlMethod.LOAD,
                        load_factor=step_target,
                        requested_step_size=abs(increment),
                        accepted_step_size=abs(increment),
                        state_id=committed.state_id,
                        iterations=tuple(iteration_records),
                        response={
                            "load_increment": increment,
                            "displacement": [float(value) for value in committed.displacement],
                            "internal_force": [
                                float(value) for value in trial.response.internal_force
                            ],
                            "external_force": [
                                float(value) for value in trial.response.external_force
                            ],
                            "strain_energy": trial.response.strain_energy,
                            "tangent_assemblies": tangent_assemblies,
                            "eta_R": metrics.eta_residual,
                            "eta_u": metrics.eta_displacement,
                            "eta_E": metrics.eta_energy,
                            "termination_reason": "CONVERGED",
                        },
                    )
                )
                break

            if iteration_index < model.analysis.max_iterations:
                try:

                    def evaluate_at(
                        candidate: np.ndarray,
                        *,
                        step_context=context,
                        sample_iteration=iteration_index,
                    ) -> EquilibriumEvaluation:
                        sampled = evaluate_trial(
                            step_context,
                            adapter,
                            model,
                            trial_displacement=candidate,
                            iteration_index=sample_iteration,
                        )
                        sampled_failure = _response_failure(
                            sampled.response,
                            step_index=step_context.step_index,
                            iteration_index=sample_iteration,
                        )
                        if sampled_failure is not None:
                            raise ValueError(sampled_failure.message)
                        return build_equilibrium(
                            sampled.response,
                            adapter.constraint_map(model),
                        )

                    search = apply_line_search(
                        evaluation,
                        evaluate_at,
                        current,
                        correction,
                        model.analysis.line_search,
                        conservative=trial.response.metadata.get("conservative") is True,
                    )
                except (
                    ArithmeticError,
                    np.linalg.LinAlgError,
                    RuntimeError,
                    StateTransitionError,
                    TypeError,
                    ValueError,
                ) as error:
                    failure = _failure(
                        FailureCode.TANGENT_ERROR,
                        f"line-search trial evaluation failed: {error}",
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                    )
                    iteration_records.append(
                        _iteration_record(
                            step_index=context.step_index,
                            iteration_index=iteration_index,
                            load_factor=step_target,
                            current_displacement=current,
                            evaluation=evaluation,
                            correction=correction,
                            metrics=metrics,
                            linear_residual_norm=linear_residual_norm,
                            linear_relative_residual=linear_relative_residual,
                            tangent_reassembled=tangent_reassembled,
                            tangent_assemblies=tangent_assemblies,
                            status=IterationStatus.REJECTED,
                            termination_reason="LINE_SEARCH_FAILED",
                            line_search_diagnostics={
                                "enabled": model.analysis.line_search.enabled,
                                "failure_reason": str(error),
                                "evaluations": 0,
                            },
                        )
                    )
                    break
                line_search_diagnostics = {
                    "enabled": model.analysis.line_search.enabled,
                    "method": None if search.method is None else search.method.value,
                    "merit_function": search.merit_function.value,
                    "evaluations": len(search.samples),
                    "samples": [
                        {
                            "alpha": sample.alpha,
                            "merit": sample.merit,
                            "directional_residual": sample.directional_residual,
                        }
                        for sample in search.samples
                    ],
                    "failure_reason": search.failure_reason,
                }
                if search.status is LineSearchStatus.FAILED:
                    failure_code = (
                        FailureCode.CONTROL_ERROR
                        if "conservative=true" in (search.failure_reason or "")
                        else FailureCode.TANGENT_ERROR
                    )
                    failure = _failure(
                        failure_code,
                        search.failure_reason or "line search failed",
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        details=line_search_diagnostics,
                    )
                    iteration_records.append(
                        _iteration_record(
                            step_index=context.step_index,
                            iteration_index=iteration_index,
                            load_factor=step_target,
                            current_displacement=current,
                            evaluation=evaluation,
                            correction=correction,
                            metrics=metrics,
                            linear_residual_norm=linear_residual_norm,
                            linear_relative_residual=linear_relative_residual,
                            tangent_reassembled=tangent_reassembled,
                            tangent_assemblies=tangent_assemblies,
                            status=IterationStatus.REJECTED,
                            termination_reason="LINE_SEARCH_FAILED",
                            line_search_diagnostics=line_search_diagnostics,
                        )
                    )
                    break
                assert search.alpha is not None
                accepted_alpha = search.alpha
                correction = accepted_alpha * correction
                metrics = convergence_metrics(evaluation, current, correction, model)

            status = (
                IterationStatus.REJECTED
                if iteration_index == model.analysis.max_iterations
                else IterationStatus.CONTINUE
            )
            reason = "MAX_ITERATIONS" if status is IterationStatus.REJECTED else "CONTINUE"
            iteration_records.append(
                _iteration_record(
                    step_index=context.step_index,
                    iteration_index=iteration_index,
                    load_factor=step_target,
                    current_displacement=current,
                    evaluation=evaluation,
                    correction=correction,
                    metrics=metrics,
                    linear_residual_norm=linear_residual_norm,
                    linear_relative_residual=linear_relative_residual,
                    tangent_reassembled=tangent_reassembled,
                    tangent_assemblies=tangent_assemblies,
                    status=status,
                    termination_reason=reason,
                    accepted_alpha=accepted_alpha,
                    line_search_diagnostics=line_search_diagnostics,
                )
            )
            if status is IterationStatus.REJECTED:
                failure = _failure(
                    FailureCode.NONCONVERGENCE,
                    "maximum Newton iterations reached",
                    step_index=context.step_index,
                    iteration_index=iteration_index,
                    details={
                        "eta_R": metrics.eta_residual,
                        "eta_u": metrics.eta_displacement,
                        "eta_E": metrics.eta_energy,
                        "tangent_assemblies": tangent_assemblies,
                    },
                )
                break
            current = current + correction
        else:  # pragma: no cover - loop always converges or creates a failure
            raise AssertionError("Newton loop terminated without a result")

        if steps and steps[-1].step_index == context.step_index:
            continue
        rolled_back = rollback(context, None if last_trial is None else last_trial.state)
        assert rolled_back is committed
        steps.append(
            StepResult(
                step_index=context.step_index,
                status=StepStatus.REJECTED,
                control_method=ControlMethod.LOAD,
                load_factor=step_target,
                requested_step_size=abs(increment),
                iterations=tuple(iteration_records),
                failure=failure,
                response={
                    "load_increment": increment,
                    "tangent_assemblies": tangent_assemblies,
                    "termination_reason": failure.code.value,
                },
            )
        )
        return _solution_failure(
            model,
            failure,
            state=committed,
            response=final_response,
            steps=steps,
            target_load_factor=target,
        )

    remaining = target - committed.load_factor
    if abs(remaining) <= target_tolerance:
        return LoadControlSolution(
            result=_result(
                model,
                status=SolveStatus.SUCCEEDED,
                steps=steps,
                failures=[],
                target_load_factor=target,
            ),
            committed_state=committed,
            final_response=final_response,
        )
    failure = _failure(
        FailureCode.CONTROL_ERROR,
        "maximum load-step count reached before the target load factor",
        step_index=committed.step_index + 1,
        details={
            "current_load_factor": committed.load_factor,
            "target_load_factor": target,
            "remaining_load_increment": remaining,
            "max_steps": model.analysis.step_control.max_steps,
        },
    )
    return _solution_failure(
        model,
        failure,
        state=committed,
        response=final_response,
        steps=steps,
        target_load_factor=target,
    )


__all__ = [
    "ConvergenceMetrics",
    "LoadControlSolution",
    "convergence_metrics",
    "solve_load_control",
]
