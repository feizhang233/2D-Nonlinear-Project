"""P6 prescribed-displacement Newton control and reaction recovery."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from nonlinear_core.adapters import ModelAdapter, ModelResponse
from nonlinear_core.constants import PACKAGE_VERSION
from nonlinear_core.equilibrium import (
    EquilibriumEvaluation,
    build_equilibrium,
    recover_constraint_reactions,
    solve_constrained_correction,
)
from nonlinear_core.globalization import LineSearchStatus, apply_line_search
from nonlinear_core.linear_solver import LinearSolveOptions
from nonlinear_core.load_control import (
    _basic_iteration_record,
    _failure,
    _iteration_record,
    _linear_failure_code,
    _response_failure,
    _reuse_tangent,
    convergence_metrics,
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
class DisplacementControlSolution:
    """P6 result evidence and last safely committed runtime state."""

    result: SolveResult
    committed_state: CommittedState | None
    final_response: ModelResponse | None

    @property
    def succeeded(self) -> bool:
        return self.result.status is SolveStatus.SUCCEEDED


def _result(
    model: ModelInput,
    *,
    status: SolveStatus,
    steps: list[StepResult],
    failures: list[FailureRecord],
    number_of_steps: int,
) -> SolveResult:
    settings = model.analysis.displacement_control
    target = None if settings is None else settings.target
    return SolveResult(
        model_id=model.model_id,
        model_sha256=model_sha256(model),
        solver_version=PACKAGE_VERSION,
        status=status,
        steps=tuple(steps),
        failures=tuple(failures),
        metadata={
            "control_method": ControlMethod.DISPLACEMENT.value,
            "newton_method": model.analysis.newton_method.value,
            "control_dof": (
                None if target is None else {"node_id": target.node_id, "dof": target.dof.value}
            ),
            "control_increment": None if settings is None else settings.increment,
            "requested_steps": number_of_steps,
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
    number_of_steps: int,
) -> DisplacementControlSolution:
    return DisplacementControlSolution(
        result=_result(
            model,
            status=SolveStatus.FAILED,
            steps=steps,
            failures=[failure],
            number_of_steps=number_of_steps,
        ),
        committed_state=state,
        final_response=response,
    )


def _control_record(
    record: IterationRecord,
    *,
    control_index: int,
    control_target: float,
    control_gap: float,
    eta_control: float,
    constraint_gap_norm: float,
    eta_constraints: float,
) -> IterationRecord:
    diagnostics = dict(record.diagnostics)
    diagnostics.update(
        {
            "control_dof_index": control_index,
            "control_target": control_target,
            "control_gap": control_gap,
            "eta_control": eta_control,
            "constraint_gap_norm": constraint_gap_norm,
            "eta_constraints": eta_constraints,
        }
    )
    return record.model_copy(update={"diagnostics": diagnostics})


def _controller_index(adapter: ModelAdapter, model: ModelInput) -> tuple[int | None, str | None]:
    settings = model.analysis.displacement_control
    if settings is None:
        return None, "displacement_control options are required"
    matches = [
        index
        for index, reference in enumerate(adapter.dof_map(model))
        if reference.node_id == settings.target.node_id and reference.dof is settings.target.dof
    ]
    if len(matches) != 1:
        return None, "control DOF must exist exactly once in the adapter DOF map"
    index = matches[0]
    if index in adapter.constraint_map(model):
        return None, "control DOF conflicts with an existing model constraint"
    return index, None


def solve_displacement_control(
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    number_of_steps: int = 1,
    initial_state: CommittedState | None = None,
    linear_options: LinearSolveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
    _increment_override: float | None = None,
) -> DisplacementControlSolution:
    """Advance fixed prescribed-displacement increments and recover controller reactions."""

    if isinstance(number_of_steps, bool) or not isinstance(number_of_steps, int):
        requested_steps = 0
    else:
        requested_steps = number_of_steps
    if requested_steps < 1:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "number_of_steps must be a positive integer",
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            number_of_steps=requested_steps,
        )
    if requested_steps > model.analysis.step_control.max_steps:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "number_of_steps exceeds analysis.step_control.max_steps",
            details={
                "number_of_steps": requested_steps,
                "max_steps": model.analysis.step_control.max_steps,
            },
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            number_of_steps=requested_steps,
        )
    if model.analysis.control_method is not ControlMethod.DISPLACEMENT:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "P6 solve_displacement_control requires control_method='displacement'",
            details={"configured_control_method": model.analysis.control_method.value},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            number_of_steps=requested_steps,
        )
    try:
        validation = adapter.validate(model)
    except (RuntimeError, TypeError, ValueError) as error:
        failure = _failure(FailureCode.MODEL_ERROR, f"adapter validation failed: {error}")
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            number_of_steps=requested_steps,
        )
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
            number_of_steps=requested_steps,
        )

    try:
        control_index, control_error = _controller_index(adapter, model)
    except (RuntimeError, TypeError, ValueError) as error:
        control_index, control_error = None, str(error)
    if control_index is None:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            control_error or "control DOF is invalid",
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            number_of_steps=requested_steps,
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
            number_of_steps=requested_steps,
        )

    settings = model.analysis.displacement_control
    assert settings is not None
    increment = (
        float(settings.increment) if _increment_override is None else float(_increment_override)
    )
    if not np.isfinite(increment) or increment == 0.0:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "control displacement increment must be finite and non-zero",
            details={"increment": str(increment)},
        )
        return _solution_failure(
            model,
            failure,
            state=committed,
            response=None,
            steps=[],
            number_of_steps=requested_steps,
        )
    base_constraints = dict(adapter.constraint_map(model))
    tolerance = model.analysis.tolerances
    linear_settings = replace(
        linear_options or LinearSolveOptions(),
        relative_residual_tolerance=tolerance.linear_solver,
    )
    steps: list[StepResult] = []
    final_response: ModelResponse | None = None

    for _ in range(requested_steps):
        control_target = float(committed.displacement[control_index] + increment)
        constraints = {**base_constraints, control_index: control_target}
        context = begin_step(
            committed,
            target_load_factor=committed.load_factor,
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
                current_evaluation = build_equilibrium(trial.response, constraints)
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
                        load_factor=committed.load_factor,
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
                        load_factor=committed.load_factor,
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
                        load_factor=committed.load_factor,
                        tangent_reassembled=tangent_reassembled,
                        tangent_assemblies=tangent_assemblies,
                        reason=failure.code.value,
                        details=failure.details,
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
            constrained = evaluation.partition.constrained_dofs
            constraint_gap = evaluation.partition.prescribed_values - current[constrained]
            control_gap = control_target - float(current[control_index])
            constraint_gap_norm = float(np.linalg.norm(constraint_gap))
            control_scale = abs(control_target) + tolerance.displacement_floor
            constraint_scale = (
                float(np.linalg.norm(evaluation.partition.prescribed_values))
                + tolerance.displacement_floor
            )
            eta_control = abs(control_gap) / control_scale
            eta_constraints = constraint_gap_norm / constraint_scale

            if (
                float(np.linalg.norm(evaluation.free_residual)) == 0.0
                and constraint_gap_norm == 0.0
            ):
                correction = np.zeros(evaluation.partition.size)
                linear_residual_norm = 0.0
                linear_relative_residual = 0.0
            else:
                correction_result = solve_constrained_correction(
                    evaluation,
                    current,
                    linear_settings,
                )
                if not correction_result.succeeded:
                    linear_failure = correction_result.linear_result.failure
                    linear_code = None if linear_failure is None else linear_failure.code
                    failure_code = _linear_failure_code(linear_code)
                    message = (
                        "selected control displacement cannot parameterize this path; the "
                        "remaining free tangent is singular or ill-conditioned"
                        if failure_code is FailureCode.CONTROL_ERROR
                        else "displacement-control Newton correction linear solve failed"
                    )
                    failure = _failure(
                        failure_code,
                        message,
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        details={
                            "control_dof_index": control_index,
                            "control_target": control_target,
                            "linear_failure_code": (
                                None if linear_code is None else linear_code.value
                            ),
                            "linear_failure_message": (
                                None if linear_failure is None else linear_failure.message
                            ),
                        },
                    )
                    iteration_records.append(
                        _basic_iteration_record(
                            step_index=context.step_index,
                            iteration_index=iteration_index,
                            load_factor=committed.load_factor,
                            tangent_reassembled=tangent_reassembled,
                            tangent_assemblies=tangent_assemblies,
                            reason=failure.code.value,
                            details={
                                **failure.details,
                                "residual": [float(value) for value in evaluation.residual],
                                "control_gap": control_gap,
                                "constraint_gap_norm": constraint_gap_norm,
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
                reaction_scale = float(np.linalg.norm(evaluation.constrained_residual))
                force_scale = metrics.force_scale + reaction_scale
                metrics = replace(
                    metrics,
                    eta_residual=metrics.residual_norm / force_scale,
                    force_scale=force_scale,
                )
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
                        load_factor=committed.load_factor,
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
                and eta_control <= tolerance.displacement
                and eta_constraints <= tolerance.displacement
                and linear_relative_residual <= tolerance.linear_solver
            )
            accepted_alpha = 1.0
            line_search_diagnostics: dict[str, Any] = {
                "enabled": False,
                "merit_function": "full_step",
                "evaluations": 0,
            }
            if not converged and iteration_index < model.analysis.max_iterations:
                try:

                    def evaluate_at(
                        candidate: np.ndarray,
                        *,
                        step_context=context,
                        sample_iteration=iteration_index,
                        sample_constraints=constraints,
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
                        return build_equilibrium(sampled.response, sample_constraints)

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
                    failed_record = _iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=committed.load_factor,
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
                    iteration_records.append(
                        _control_record(
                            failed_record,
                            control_index=control_index,
                            control_target=control_target,
                            control_gap=control_gap,
                            eta_control=eta_control,
                            constraint_gap_norm=constraint_gap_norm,
                            eta_constraints=eta_constraints,
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
                    failed_record = _iteration_record(
                        step_index=context.step_index,
                        iteration_index=iteration_index,
                        load_factor=committed.load_factor,
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
                    iteration_records.append(
                        _control_record(
                            failed_record,
                            control_index=control_index,
                            control_target=control_target,
                            control_gap=control_gap,
                            eta_control=eta_control,
                            constraint_gap_norm=constraint_gap_norm,
                            eta_constraints=eta_constraints,
                        )
                    )
                    break
                assert search.alpha is not None
                accepted_alpha = search.alpha
                correction = accepted_alpha * correction
                metrics = convergence_metrics(evaluation, current, correction, model)
                reaction_scale = float(np.linalg.norm(evaluation.constrained_residual))
                force_scale = metrics.force_scale + reaction_scale
                metrics = replace(
                    metrics,
                    eta_residual=metrics.residual_norm / force_scale,
                    force_scale=force_scale,
                )
            status = (
                IterationStatus.CONVERGED
                if converged
                else (
                    IterationStatus.REJECTED
                    if iteration_index == model.analysis.max_iterations
                    else IterationStatus.CONTINUE
                )
            )
            reason = (
                "CONVERGED"
                if status is IterationStatus.CONVERGED
                else ("MAX_ITERATIONS" if status is IterationStatus.REJECTED else "CONTINUE")
            )
            record = _iteration_record(
                step_index=context.step_index,
                iteration_index=iteration_index,
                load_factor=committed.load_factor,
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
            iteration_records.append(
                _control_record(
                    record,
                    control_index=control_index,
                    control_target=control_target,
                    control_gap=control_gap,
                    eta_control=eta_control,
                    constraint_gap_norm=constraint_gap_norm,
                    eta_constraints=eta_constraints,
                )
            )

            if converged:
                committed = commit(context, trial.state, converged=True)
                final_response = trial.response
                reactions = recover_constraint_reactions(evaluation)
                reaction_lookup = {
                    int(index): float(value)
                    for index, value in zip(
                        reactions.constrained_dofs,
                        reactions.constrained_reactions,
                        strict=True,
                    )
                }
                controller_reaction = reaction_lookup[control_index]
                dof_map = adapter.dof_map(model)
                support_reactions = [
                    {
                        "dof_index": index,
                        "node_id": dof_map[index].node_id,
                        "dof": dof_map[index].dof.value,
                        "reaction": value,
                    }
                    for index, value in reaction_lookup.items()
                    if index != control_index
                ]
                steps.append(
                    StepResult(
                        step_index=context.step_index,
                        status=StepStatus.ACCEPTED,
                        control_method=ControlMethod.DISPLACEMENT,
                        load_factor=committed.load_factor,
                        requested_step_size=abs(increment),
                        accepted_step_size=abs(increment),
                        state_id=committed.state_id,
                        iterations=tuple(iteration_records),
                        response={
                            "control_dof": {
                                "node_id": settings.target.node_id,
                                "dof": settings.target.dof.value,
                                "index": control_index,
                            },
                            "control_displacement_increment": increment,
                            "control_displacement": float(committed.displacement[control_index]),
                            "controller_reaction": controller_reaction,
                            "support_reactions": support_reactions,
                            "free_dofs": [int(value) for value in evaluation.partition.free_dofs],
                            "free_residual": [float(value) for value in evaluation.free_residual],
                            "full_imbalance": [float(value) for value in reactions.full_imbalance],
                            "load_factor": committed.load_factor,
                            "tangent_assemblies": tangent_assemblies,
                            "eta_R": metrics.eta_residual,
                            "eta_u": metrics.eta_displacement,
                            "eta_E": metrics.eta_energy,
                            "eta_control": eta_control,
                            "termination_reason": "CONVERGED",
                        },
                    )
                )
                break

            if status is IterationStatus.REJECTED:
                failure = _failure(
                    FailureCode.NONCONVERGENCE,
                    "maximum displacement-control Newton iterations reached",
                    step_index=context.step_index,
                    iteration_index=iteration_index,
                    details={
                        "eta_R": metrics.eta_residual,
                        "eta_u": metrics.eta_displacement,
                        "eta_E": metrics.eta_energy,
                        "eta_control": eta_control,
                        "eta_constraints": eta_constraints,
                        "tangent_assemblies": tangent_assemblies,
                    },
                )
                break
            current = current + correction
        else:  # pragma: no cover - loop always converges or creates a failure
            raise AssertionError("displacement-control loop terminated without a result")

        if steps and steps[-1].step_index == context.step_index:
            continue
        rolled_back = rollback(context, None if last_trial is None else last_trial.state)
        assert rolled_back is committed
        steps.append(
            StepResult(
                step_index=context.step_index,
                status=StepStatus.REJECTED,
                control_method=ControlMethod.DISPLACEMENT,
                load_factor=committed.load_factor,
                requested_step_size=abs(increment),
                iterations=tuple(iteration_records),
                failure=failure,
                response={
                    "control_dof": {
                        "node_id": settings.target.node_id,
                        "dof": settings.target.dof.value,
                        "index": control_index,
                    },
                    "control_displacement_increment": increment,
                    "control_target": control_target,
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
            number_of_steps=requested_steps,
        )

    return DisplacementControlSolution(
        result=_result(
            model,
            status=SolveStatus.SUCCEEDED,
            steps=steps,
            failures=[],
            number_of_steps=requested_steps,
        ),
        committed_state=committed,
        final_response=final_response,
    )


__all__ = ["DisplacementControlSolution", "solve_displacement_control"]
