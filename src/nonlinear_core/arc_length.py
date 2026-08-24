"""P8 spherical arc-length prediction, correction, root choice, and retry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nonlinear_core.adapters import ModelAdapter, ModelResponse
from nonlinear_core.adaptive import failure_disposition
from nonlinear_core.constants import PACKAGE_VERSION
from nonlinear_core.equilibrium import (
    EquilibriumEvaluation,
    build_equilibrium,
    recover_constraint_reactions,
)
from nonlinear_core.linear_solver import (
    LinearFailureCode,
    LinearSolveOptions,
    LinearSolveResult,
    solve_linear_system,
)
from nonlinear_core.load_control import ConvergenceMetrics, convergence_metrics
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

FloatArray = NDArray[np.float64]
_CURVATURE_COSINE_LIMIT = 0.25
ARC_INCREMENT_SCHEMA_VERSION = "1.0.0"


def _vector(value: ArrayLike, *, name: str, size: int | None = None) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.ndim != 1 or (size is not None and result.shape != (size,)):
        expected = "a vector" if size is None else f"shape ({size},)"
        raise ValueError(f"{name} must have {expected}; got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    result.setflags(write=False)
    return result


class ArcLengthRootStatus(StrEnum):
    SELECTED = "selected"
    COMPLEX_ROOTS = "complex_roots"
    DEGENERATE_QUADRATIC = "degenerate_quadratic"
    NO_CONTINUOUS_ROOT = "no_continuous_root"


@dataclass(frozen=True, slots=True)
class ArcLengthIncrement:
    """One converged augmented load-displacement increment."""

    displacement: FloatArray
    load_factor: float
    radius: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "displacement",
            _vector(self.displacement, name="arc-length displacement increment"),
        )
        for name in ("load_factor", "radius"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or (name == "radius" and value <= 0.0):
                raise ValueError(f"arc-length {name} must be finite and radius must be positive")
            object.__setattr__(self, name, value)

    def to_payload(self) -> dict[str, object]:
        """Return the frozen JSON-compatible continuation contract."""

        return {
            "arc_increment_schema_version": ARC_INCREMENT_SCHEMA_VERSION,
            "displacement": [float(value) for value in self.displacement],
            "load_factor": self.load_factor,
            "radius": self.radius,
        }

    @classmethod
    def from_payload(cls, payload: object) -> ArcLengthIncrement:
        """Restore one strictly versioned continuation increment."""

        if not isinstance(payload, dict):
            raise ValueError("arc-length increment must be a JSON object")
        expected = {
            "arc_increment_schema_version",
            "displacement",
            "load_factor",
            "radius",
        }
        if set(payload) != expected:
            missing = sorted(expected - set(payload))
            unknown = sorted(set(payload) - expected)
            raise ValueError(
                "arc-length increment fields do not match the frozen schema; "
                f"missing={missing}, unknown={unknown}"
            )
        if payload["arc_increment_schema_version"] != ARC_INCREMENT_SCHEMA_VERSION:
            raise ValueError("unsupported arc-length increment schema version")
        return cls(
            displacement=payload["displacement"],
            load_factor=payload["load_factor"],
            radius=payload["radius"],
        )


@dataclass(frozen=True, slots=True)
class ArcLengthRootCandidate:
    correction_load_factor: float
    total_load_increment: float
    displacement_increment: FloatArray
    displacement_continuity: float
    augmented_continuity: float
    direction_cosine: float | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "displacement_increment",
            _vector(self.displacement_increment, name="root displacement increment"),
        )
        values = [
            self.correction_load_factor,
            self.total_load_increment,
            self.displacement_continuity,
            self.augmented_continuity,
        ]
        if self.direction_cosine is not None:
            values.append(self.direction_cosine)
        if not np.all(np.isfinite(values)):
            raise ValueError("arc-length root candidate values must be finite")


@dataclass(frozen=True, slots=True)
class ArcLengthRootResult:
    status: ArcLengthRootStatus
    coefficients: tuple[float, float, float]
    discriminant: float
    candidates: tuple[ArcLengthRootCandidate, ...] = ()
    selected_index: int | None = None
    selection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ArcLengthRootStatus(self.status))
        if not np.all(np.isfinite((*self.coefficients, self.discriminant))):
            raise ValueError("arc-length quadratic evidence must be finite")
        if self.status is ArcLengthRootStatus.SELECTED:
            if self.selected_index is None or not 0 <= self.selected_index < len(self.candidates):
                raise ValueError("selected root results require a valid candidate index")
            if not self.selection_reason:
                raise ValueError("selected root results require a selection reason")
        elif self.selected_index is not None or not self.selection_reason:
            raise ValueError("failed root results require a reason and no selected index")

    @property
    def selected(self) -> ArcLengthRootCandidate | None:
        if self.selected_index is None:
            return None
        return self.candidates[self.selected_index]


@dataclass(frozen=True, slots=True)
class ArcLengthSolution:
    """Serializable P8 evidence plus the last safely committed runtime state."""

    result: SolveResult
    committed_state: CommittedState | None
    final_response: ModelResponse | None
    last_increment: ArcLengthIncrement | None

    @property
    def succeeded(self) -> bool:
        return self.result.status is SolveStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class _ArcAttempt:
    step: StepResult
    committed_state: CommittedState | None
    final_response: ModelResponse | None
    increment: ArcLengthIncrement | None
    failure: FailureRecord | None

    @property
    def succeeded(self) -> bool:
        return self.failure is None and self.committed_state is not None


def _augmented_dot(
    displacement_a: np.ndarray,
    load_a: float,
    displacement_b: np.ndarray,
    load_b: float,
    *,
    beta: float,
    reference_norm_sq: float,
) -> float:
    return float(displacement_a @ displacement_b + beta**2 * reference_norm_sq * load_a * load_b)


def select_arc_length_root(
    accumulated_displacement: ArrayLike,
    accumulated_load_factor: float,
    load_direction: ArrayLike,
    residual_direction: ArrayLike,
    reference_load: ArrayLike,
    *,
    radius: float,
    beta: float,
    previous_increment: ArcLengthIncrement | None = None,
) -> ArcLengthRootResult:
    """Solve the Crisfield spherical quadratic and retain both candidate roots."""

    accumulated = _vector(accumulated_displacement, name="accumulated displacement")
    size = accumulated.size
    load_vector = _vector(load_direction, name="load direction", size=size)
    residual_vector = _vector(residual_direction, name="residual direction", size=size)
    reference = _vector(reference_load, name="reference load", size=size)
    radius = float(radius)
    beta = float(beta)
    accumulated_load_factor = float(accumulated_load_factor)
    if (
        not np.isfinite(radius)
        or radius <= 0.0
        or not np.isfinite(beta)
        or beta <= 0.0
        or not np.isfinite(accumulated_load_factor)
    ):
        raise ValueError("arc-length radius and beta must be positive and all inputs finite")
    if previous_increment is not None and previous_increment.displacement.shape != (size,):
        raise ValueError("previous arc-length increment must match the system size")

    with np.errstate(over="ignore", invalid="ignore"):
        reference_norm_sq = float(reference @ reference)
        beta_sq = float(np.square(beta))
        radius_sq = float(np.square(radius))
        base = accumulated + residual_vector
        a_1 = float(load_vector @ load_vector + beta_sq * reference_norm_sq)
        a_2 = float(
            2.0 * (base @ load_vector) + 2.0 * beta_sq * accumulated_load_factor * reference_norm_sq
        )
        a_3 = float(
            base @ base
            + beta_sq * np.square(accumulated_load_factor) * reference_norm_sq
            - radius_sq
        )
    coefficients = (a_1, a_2, a_3)
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("arc-length quadratic coefficients overflowed; rescale the model")
    if a_1 <= np.finfo(float).tiny:
        return ArcLengthRootResult(
            status=ArcLengthRootStatus.DEGENERATE_QUADRATIC,
            coefficients=coefficients,
            discriminant=0.0,
            selection_reason="spherical constraint produced a degenerate quadratic",
        )

    with np.errstate(over="ignore", invalid="ignore"):
        squared_linear_term = float(np.square(a_2))
        quadratic_constant_term = float(4.0 * a_1 * a_3)
    if not np.all(np.isfinite((squared_linear_term, quadratic_constant_term))):
        raise ValueError("arc-length quadratic discriminant overflowed; rescale the model")
    discriminant = float(squared_linear_term - quadratic_constant_term)
    discriminant_scale = max(
        abs(squared_linear_term),
        abs(quadratic_constant_term),
        np.finfo(float).tiny,
    )
    discriminant_tolerance = np.finfo(float).eps * discriminant_scale * 128.0
    if discriminant < -discriminant_tolerance:
        return ArcLengthRootResult(
            status=ArcLengthRootStatus.COMPLEX_ROOTS,
            coefficients=coefficients,
            discriminant=discriminant,
            selection_reason="spherical correction has two complex roots; reduce the radius",
        )
    discriminant = max(0.0, discriminant)
    square_root = float(np.sqrt(discriminant))
    roots = ((-a_2 + square_root) / (2.0 * a_1), (-a_2 - square_root) / (2.0 * a_1))
    candidates: list[ArcLengthRootCandidate] = []
    for correction_load in roots:
        total_load = accumulated_load_factor + correction_load
        total_displacement = base + correction_load * load_vector
        displacement_continuity = 0.0
        augmented_continuity = total_load
        cosine = None
        if previous_increment is not None:
            displacement_continuity = float(total_displacement @ previous_increment.displacement)
            augmented_continuity = _augmented_dot(
                total_displacement,
                total_load,
                previous_increment.displacement,
                previous_increment.load_factor,
                beta=beta,
                reference_norm_sq=reference_norm_sq,
            )
            previous_norm = np.sqrt(
                _augmented_dot(
                    previous_increment.displacement,
                    previous_increment.load_factor,
                    previous_increment.displacement,
                    previous_increment.load_factor,
                    beta=beta,
                    reference_norm_sq=reference_norm_sq,
                )
            )
            current_norm = np.sqrt(
                max(
                    0.0,
                    _augmented_dot(
                        total_displacement,
                        total_load,
                        total_displacement,
                        total_load,
                        beta=beta,
                        reference_norm_sq=reference_norm_sq,
                    ),
                )
            )
            denominator = previous_norm * current_norm
            cosine = None if denominator == 0.0 else augmented_continuity / denominator
        candidates.append(
            ArcLengthRootCandidate(
                correction_load_factor=float(correction_load),
                total_load_increment=float(total_load),
                displacement_increment=total_displacement,
                displacement_continuity=displacement_continuity,
                augmented_continuity=augmented_continuity,
                direction_cosine=None if cosine is None else float(np.clip(cosine, -1.0, 1.0)),
            )
        )

    if previous_increment is None:
        selected_index = max(
            range(len(candidates)),
            key=lambda index: (
                candidates[index].total_load_increment,
                -abs(candidates[index].correction_load_factor),
            ),
        )
        reason = "first step selects the positive load-factor direction"
    else:
        selected_index = max(
            range(len(candidates)),
            key=lambda index: (
                candidates[index].augmented_continuity,
                candidates[index].displacement_continuity,
            ),
        )
        selected = candidates[selected_index]
        continuity_scale = max(
            *(abs(candidate.augmented_continuity) for candidate in candidates),
            np.finfo(float).tiny,
        )
        continuity_tolerance = np.finfo(float).eps * continuity_scale * 128.0
        if selected.augmented_continuity <= continuity_tolerance:
            return ArcLengthRootResult(
                status=ArcLengthRootStatus.NO_CONTINUOUS_ROOT,
                coefficients=coefficients,
                discriminant=discriminant,
                candidates=tuple(candidates),
                selection_reason=(
                    "neither quadratic root preserves the previous augmented increment direction"
                ),
            )
        reason = "selected the root with maximum previous-increment continuity"
    return ArcLengthRootResult(
        status=ArcLengthRootStatus.SELECTED,
        coefficients=coefficients,
        discriminant=discriminant,
        candidates=tuple(candidates),
        selected_index=selected_index,
        selection_reason=reason,
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


def _response_failure(
    response: ModelResponse,
    *,
    step_index: int,
    iteration_index: int,
) -> FailureRecord | None:
    scalars = {
        "strain_energy": response.strain_energy,
        "min_det_j": response.min_det_j,
        "min_det_f": response.min_det_f,
    }
    for element in response.elements:
        scalars[f"element:{element.element_id}:energy"] = element.energy
        scalars[f"element:{element.element_id}:min_det_j"] = element.min_det_j
        scalars[f"element:{element.element_id}:min_det_f"] = element.min_det_f
    nonfinite = {
        name: str(value)
        for name, value in scalars.items()
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


def _linear_failure(
    result: LinearSolveResult,
    *,
    step_index: int,
    iteration_index: int,
    rhs_role: str,
) -> FailureRecord:
    failure = result.failure
    code = None if failure is None else failure.code
    failure_code = (
        FailureCode.TANGENT_ERROR
        if code in {LinearFailureCode.SINGULAR_SYSTEM, LinearFailureCode.ILL_CONDITIONED_SYSTEM}
        else FailureCode.LINEAR_SOLVE_ERROR
    )
    return _failure(
        failure_code,
        f"arc-length {rhs_role} tangent solve failed",
        step_index=step_index,
        iteration_index=iteration_index,
        details={
            "rhs_role": rhs_role,
            "linear_failure_code": None if code is None else code.value,
            "linear_failure_message": None if failure is None else failure.message,
            "condition_estimate": (
                None
                if result.condition_estimate is None or not np.isfinite(result.condition_estimate)
                else result.condition_estimate
            ),
        },
    )


def _linear_residual_metrics(
    matrix: np.ndarray,
    solution: np.ndarray,
    right_hand_side: np.ndarray,
) -> tuple[float, float]:
    residual = matrix @ solution - right_hand_side
    residual_norm = float(np.linalg.norm(residual))
    relative_residual = residual_norm / max(
        float(np.linalg.norm(right_hand_side)),
        float(np.linalg.norm(matrix, ord=np.inf)) * float(np.linalg.norm(solution)),
        np.finfo(float).tiny,
    )
    return residual_norm, relative_residual


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


def _root_diagnostics(root: ArcLengthRootResult) -> dict[str, Any]:
    return {
        "status": root.status.value,
        "coefficients": [float(value) for value in root.coefficients],
        "discriminant": root.discriminant,
        "selected_index": root.selected_index,
        "selection_reason": root.selection_reason,
        "candidates": [
            {
                "correction_load_factor": candidate.correction_load_factor,
                "total_load_increment": candidate.total_load_increment,
                "displacement_increment": [
                    float(value) for value in candidate.displacement_increment
                ],
                "displacement_continuity": candidate.displacement_continuity,
                "augmented_continuity": candidate.augmented_continuity,
                "direction_cosine": candidate.direction_cosine,
            }
            for candidate in root.candidates
        ],
    }


def _iteration_record(
    *,
    step_index: int,
    iteration_index: int,
    load_factor: float,
    current_displacement: np.ndarray,
    evaluation: EquilibriumEvaluation,
    correction: np.ndarray,
    correction_load_factor: float,
    metrics: ConvergenceMetrics,
    arc_constraint: float,
    eta_arc: float,
    linear_residual_norm: float,
    linear_relative_residual: float,
    tangent_reassembled: bool,
    tangent_assemblies: int,
    status: IterationStatus,
    reason: str,
    root: ArcLengthRootResult,
) -> IterationRecord:
    return IterationRecord(
        step_index=step_index,
        iteration_index=iteration_index,
        load_factor=load_factor,
        residual_norm=metrics.eta_residual,
        displacement_correction_norm=metrics.eta_displacement,
        energy_norm=metrics.eta_energy,
        linear_residual_norm=linear_residual_norm,
        tangent_reassembled=tangent_reassembled,
        status=status,
        diagnostics={
            "eta_R": metrics.eta_residual,
            "eta_u": metrics.eta_displacement,
            "eta_E": metrics.eta_energy,
            "eta_arc": eta_arc,
            "raw_residual_norm": metrics.residual_norm,
            "raw_correction_norm": metrics.correction_norm,
            "arc_constraint": arc_constraint,
            "load_factor_correction": correction_load_factor,
            "linear_relative_residual": linear_relative_residual,
            "displacement": [float(value) for value in current_displacement],
            "residual": [float(value) for value in evaluation.residual],
            "correction": [float(value) for value in correction],
            "tangent_assemblies": tangent_assemblies,
            "two_rhs_same_tangent": True,
            "termination_reason": reason,
            "arc_length_root": _root_diagnostics(root),
        },
    )


def _rejected_record(
    *,
    step_index: int,
    iteration_index: int,
    load_factor: float,
    reason: str,
    tangent_assemblies: int,
    details: dict[str, Any] | None = None,
) -> IterationRecord:
    diagnostics = {
        "termination_reason": reason,
        "tangent_assemblies": tangent_assemblies,
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
        tangent_reassembled=True,
        status=IterationStatus.REJECTED,
        diagnostics=diagnostics,
    )


def _arc_constraint(
    displacement_increment: np.ndarray,
    load_increment: float,
    *,
    beta: float,
    reference_norm_sq: float,
    radius: float,
) -> float:
    return float(
        displacement_increment @ displacement_increment
        + beta**2 * load_increment**2 * reference_norm_sq
        - radius**2
    )


def _proportional_load_failure(
    response: ModelResponse,
    load_factor: float,
    reference_load: np.ndarray,
    *,
    step_index: int,
    iteration_index: int,
) -> FailureRecord | None:
    expected = load_factor * reference_load
    scale = max(
        1.0, float(np.linalg.norm(expected)), float(np.linalg.norm(response.external_force))
    )
    error = float(np.linalg.norm(response.external_force - expected))
    tangent_norm = (
        0.0
        if response.external_tangent is None
        else float(np.linalg.norm(response.external_tangent))
    )
    if error > 1.0e-10 * scale or tangent_norm > 1.0e-12 * scale:
        return _failure(
            FailureCode.CONTROL_ERROR,
            "basic spherical arc length requires a fixed proportional external load lambda*f_hat",
            step_index=step_index,
            iteration_index=iteration_index,
            details={
                "retryable": False,
                "proportional_load_error": error,
                "external_tangent_norm": tangent_norm,
            },
        )
    return None


def _attempt_arc_step(
    adapter: ModelAdapter,
    model: ModelInput,
    committed: CommittedState,
    reference_load: np.ndarray,
    *,
    radius: float,
    attempt_index: int,
    previous_increment: ArcLengthIncrement | None,
    linear_options: LinearSolveOptions | None,
    progress_callback: ProgressCallback | None,
    accepted_steps: int,
) -> _ArcAttempt:
    settings = model.analysis.arc_length
    assert settings is not None
    step_index = committed.step_index + 1
    try:
        constraints = adapter.constraint_map(model)
    except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
        failure = _failure(
            FailureCode.MODEL_ERROR,
            f"arc-length constraint mapping failed: {error}",
            step_index=step_index,
            details={"retryable": False},
        )
        step = StepResult(
            step_index=step_index,
            status=StepStatus.REJECTED,
            control_method=ControlMethod.ARC_LENGTH,
            load_factor=committed.load_factor,
            requested_step_size=radius,
            failure=failure,
            response={"arc_radius": radius, "attempt_index": attempt_index},
        )
        return _ArcAttempt(step, None, None, None, failure)
    try:
        base_context = begin_step(
            committed,
            target_load_factor=committed.load_factor,
            step_index=step_index,
            attempt_index=attempt_index,
        )
        base_trial = evaluate_trial(
            base_context,
            adapter,
            model,
            trial_displacement=committed.displacement,
            load_factor=committed.load_factor,
            iteration_index=0,
        )
        base_evaluation = build_equilibrium(base_trial.response, constraints)
    except (
        ArithmeticError,
        np.linalg.LinAlgError,
        RuntimeError,
        StateTransitionError,
        TypeError,
        ValueError,
    ) as error:
        failure = _failure(
            FailureCode.STATE_ERROR,
            f"arc-length step baseline evaluation failed: {error}",
            step_index=step_index,
            details={"retryable": False},
        )
        step = StepResult(
            step_index=step_index,
            status=StepStatus.REJECTED,
            control_method=ControlMethod.ARC_LENGTH,
            load_factor=committed.load_factor,
            requested_step_size=radius,
            failure=failure,
            response={"arc_radius": radius, "attempt_index": attempt_index},
        )
        return _ArcAttempt(step, None, None, None, failure)
    base_failure = _response_failure(base_trial.response, step_index=step_index, iteration_index=0)
    if base_failure is None:
        base_failure = _proportional_load_failure(
            base_trial.response,
            committed.load_factor,
            reference_load,
            step_index=step_index,
            iteration_index=0,
        )
    if base_failure is not None:
        step = StepResult(
            step_index=step_index,
            status=StepStatus.REJECTED,
            control_method=ControlMethod.ARC_LENGTH,
            load_factor=committed.load_factor,
            requested_step_size=radius,
            failure=base_failure,
            response={"arc_radius": radius, "attempt_index": attempt_index},
        )
        return _ArcAttempt(step, None, None, None, base_failure)

    free = base_evaluation.partition.free_dofs
    constrained = base_evaluation.partition.constrained_dofs
    prescribed_error = float(
        np.linalg.norm(
            committed.displacement[constrained] - base_evaluation.partition.prescribed_values
        )
    )
    if prescribed_error > model.analysis.tolerances.displacement:
        failure = _failure(
            FailureCode.STATE_ERROR,
            "arc-length committed state does not satisfy prescribed displacements",
            step_index=step_index,
            details={"prescribed_displacement_error": prescribed_error, "retryable": False},
        )
        step = StepResult(
            step_index=step_index,
            status=StepStatus.REJECTED,
            control_method=ControlMethod.ARC_LENGTH,
            load_factor=committed.load_factor,
            requested_step_size=radius,
            failure=failure,
            response={"arc_radius": radius, "attempt_index": attempt_index},
        )
        return _ArcAttempt(step, None, None, None, failure)

    free_tangent = base_evaluation.effective_tangent[np.ix_(free, free)]
    free_reference = reference_load[free]
    predictor_solve = solve_linear_system(free_tangent, free_reference, linear_options)
    if not predictor_solve.succeeded:
        failure = _linear_failure(
            predictor_solve,
            step_index=step_index,
            iteration_index=0,
            rhs_role="predictor-load",
        )
        step = StepResult(
            step_index=step_index,
            status=StepStatus.REJECTED,
            control_method=ControlMethod.ARC_LENGTH,
            load_factor=committed.load_factor,
            requested_step_size=radius,
            failure=failure,
            response={"arc_radius": radius, "attempt_index": attempt_index},
        )
        return _ArcAttempt(step, None, None, None, failure)
    assert predictor_solve.solution is not None
    predictor_direction = np.zeros_like(committed.displacement)
    predictor_direction[free] = predictor_solve.solution
    reference_norm_sq = float(free_reference @ free_reference)
    denominator = float(
        np.sqrt(predictor_direction @ predictor_direction + settings.beta**2 * reference_norm_sq)
    )
    if not np.isfinite(denominator) or denominator <= np.finfo(float).tiny:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "arc-length predictor has zero augmented direction",
            step_index=step_index,
            details={"retryable": False},
        )
        step = StepResult(
            step_index=step_index,
            status=StepStatus.REJECTED,
            control_method=ControlMethod.ARC_LENGTH,
            load_factor=committed.load_factor,
            requested_step_size=radius,
            failure=failure,
            response={"arc_radius": radius, "attempt_index": attempt_index},
        )
        return _ArcAttempt(step, None, None, None, failure)

    predictor_load = radius / denominator
    positive_displacement = predictor_load * predictor_direction
    predictor_cosine = None
    if previous_increment is not None:
        positive_dot = _augmented_dot(
            positive_displacement,
            predictor_load,
            previous_increment.displacement,
            previous_increment.load_factor,
            beta=settings.beta,
            reference_norm_sq=reference_norm_sq,
        )
        if positive_dot < 0.0:
            predictor_load = -predictor_load
            positive_displacement = -positive_displacement
            positive_dot = -positive_dot
        previous_norm = np.sqrt(
            _augmented_dot(
                previous_increment.displacement,
                previous_increment.load_factor,
                previous_increment.displacement,
                previous_increment.load_factor,
                beta=settings.beta,
                reference_norm_sq=reference_norm_sq,
            )
        )
        predictor_cosine = positive_dot / max(radius * previous_norm, np.finfo(float).tiny)
        predictor_cosine = float(np.clip(predictor_cosine, -1.0, 1.0))

    predictor_displacement = committed.displacement + positive_displacement
    predictor_factor = committed.load_factor + predictor_load
    context = begin_step(
        committed,
        target_load_factor=predictor_factor,
        predictor_displacement=predictor_displacement,
        step_index=step_index,
        attempt_index=attempt_index,
    )
    current = np.array(predictor_displacement, copy=True)
    current_factor = float(predictor_factor)
    records: list[IterationRecord] = []
    tangent_assemblies = 0
    linear_factorizations = 1
    linear_rhs_solves = 1
    frozen_evaluation: EquilibriumEvaluation | None = None
    last_trial = None
    failure: FailureRecord | None = None

    for iteration_index in range(1, model.analysis.max_iterations + 1):
        emit_progress(
            progress_callback,
            step_index=step_index,
            iteration_index=iteration_index,
            accepted_steps=accepted_steps,
        )
        try:
            trial = evaluate_trial(
                context,
                adapter,
                model,
                trial_displacement=current,
                load_factor=current_factor,
                iteration_index=iteration_index,
            )
            last_trial = trial
            current_evaluation = build_equilibrium(trial.response, constraints)
        except (
            ArithmeticError,
            np.linalg.LinAlgError,
            RuntimeError,
            StateTransitionError,
            TypeError,
            ValueError,
        ) as error:
            failure = _failure(
                FailureCode.STATE_ERROR,
                f"arc-length trial evaluation failed: {error}",
                step_index=step_index,
                iteration_index=iteration_index,
            )
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason=failure.code.value,
                    tangent_assemblies=tangent_assemblies,
                    details={"message": str(error)},
                )
            )
            break

        response_failure = _response_failure(
            trial.response,
            step_index=step_index,
            iteration_index=iteration_index,
        )
        if response_failure is None:
            response_failure = _proportional_load_failure(
                trial.response,
                current_factor,
                reference_load,
                step_index=step_index,
                iteration_index=iteration_index,
            )
        if response_failure is not None:
            failure = response_failure
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason=failure.code.value,
                    tangent_assemblies=tangent_assemblies,
                    details={
                        **failure.details,
                        "residual": [float(v) for v in current_evaluation.residual],
                    },
                )
            )
            break

        if frozen_evaluation is None:
            frozen_evaluation = base_evaluation
        evaluation = (
            current_evaluation
            if model.analysis.newton_method is NewtonMethod.FULL
            else _reuse_tangent(current_evaluation, frozen_evaluation)
        )
        tangent_reassembled = (
            model.analysis.newton_method is NewtonMethod.FULL or tangent_assemblies == 0
        )
        if tangent_reassembled:
            tangent_assemblies += 1
        tangent = evaluation.effective_tangent[np.ix_(free, free)]
        coupled_right_hand_sides = np.column_stack((free_reference, evaluation.free_residual))
        coupled_solve = solve_linear_system(tangent, coupled_right_hand_sides, linear_options)
        linear_factorizations += 1
        linear_rhs_solves += 2
        if not coupled_solve.succeeded:
            failure = _linear_failure(
                coupled_solve,
                step_index=step_index,
                iteration_index=iteration_index,
                rhs_role="coupled-load-and-residual",
            )
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason=failure.code.value,
                    tangent_assemblies=tangent_assemblies,
                    details=failure.details,
                )
            )
            break
        assert coupled_solve.solution is not None
        load_solution = coupled_solve.solution[:, 0]
        residual_solution = coupled_solve.solution[:, 1]
        load_linear_norm, load_linear_relative = _linear_residual_metrics(
            tangent,
            load_solution,
            free_reference,
        )
        residual_linear_norm, residual_linear_relative = _linear_residual_metrics(
            tangent,
            residual_solution,
            evaluation.free_residual,
        )
        configured_linear_tolerance = (
            linear_options or LinearSolveOptions()
        ).relative_residual_tolerance
        linear_norm = max(load_linear_norm, residual_linear_norm)
        linear_relative = max(load_linear_relative, residual_linear_relative)
        if linear_relative > configured_linear_tolerance:
            failure = _failure(
                FailureCode.LINEAR_SOLVE_ERROR,
                "one coupled arc-length right-hand side exceeds the linear residual tolerance",
                step_index=step_index,
                iteration_index=iteration_index,
                details={
                    "rhs_role": "coupled-load-and-residual",
                    "load_relative_residual": load_linear_relative,
                    "residual_relative_residual": residual_linear_relative,
                    "threshold": configured_linear_tolerance,
                },
            )
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason=failure.code.value,
                    tangent_assemblies=tangent_assemblies,
                    details=failure.details,
                )
            )
            break
        load_direction = np.zeros_like(current)
        residual_direction = np.zeros_like(current)
        load_direction[free] = load_solution
        residual_direction[free] = residual_solution
        accumulated = current - committed.displacement
        accumulated_factor = current_factor - committed.load_factor
        try:
            root = select_arc_length_root(
                accumulated,
                accumulated_factor,
                load_direction,
                residual_direction,
                np.where(np.isin(np.arange(reference_load.size), free), reference_load, 0.0),
                radius=radius,
                beta=settings.beta,
                previous_increment=previous_increment,
            )
        except (ArithmeticError, TypeError, ValueError) as error:
            failure = _failure(
                FailureCode.TANGENT_ERROR,
                f"arc-length quadratic construction failed: {error}",
                step_index=step_index,
                iteration_index=iteration_index,
                details={"retryable": True},
            )
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason="ARC_LENGTH_ROOT_FAILED",
                    tangent_assemblies=tangent_assemblies,
                    details={"message": str(error)},
                )
            )
            break
        if root.status is not ArcLengthRootStatus.SELECTED:
            failure = _failure(
                FailureCode.TANGENT_ERROR,
                root.selection_reason or "arc-length root selection failed",
                step_index=step_index,
                iteration_index=iteration_index,
                details={"arc_length_root": _root_diagnostics(root)},
            )
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason="ARC_LENGTH_ROOT_FAILED",
                    tangent_assemblies=tangent_assemblies,
                    details={"arc_length_root": _root_diagnostics(root)},
                )
            )
            break
        selected = root.selected
        assert selected is not None
        correction = selected.displacement_increment - accumulated
        correction_factor = selected.total_load_increment - accumulated_factor
        arc_value = _arc_constraint(
            accumulated,
            accumulated_factor,
            beta=settings.beta,
            reference_norm_sq=reference_norm_sq,
            radius=radius,
        )
        eta_arc = abs(arc_value) / radius**2
        try:
            metrics = convergence_metrics(evaluation, current, correction, model)
        except ValueError as error:
            failure = _failure(
                FailureCode.TANGENT_ERROR,
                str(error),
                step_index=step_index,
                iteration_index=iteration_index,
            )
            records.append(
                _rejected_record(
                    step_index=step_index,
                    iteration_index=iteration_index,
                    load_factor=current_factor,
                    reason=failure.code.value,
                    tangent_assemblies=tangent_assemblies,
                )
            )
            break
        tolerance = model.analysis.tolerances
        converged = (
            metrics.eta_residual <= tolerance.residual
            and metrics.eta_displacement <= tolerance.displacement
            and metrics.eta_energy <= tolerance.energy
            and eta_arc <= tolerance.displacement
            and linear_relative <= tolerance.linear_solver
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
            if converged
            else ("MAX_ITERATIONS" if status is IterationStatus.REJECTED else "CONTINUE")
        )
        records.append(
            _iteration_record(
                step_index=step_index,
                iteration_index=iteration_index,
                load_factor=current_factor,
                current_displacement=current,
                evaluation=evaluation,
                correction=correction,
                correction_load_factor=correction_factor,
                metrics=metrics,
                arc_constraint=arc_value,
                eta_arc=eta_arc,
                linear_residual_norm=linear_norm,
                linear_relative_residual=linear_relative,
                tangent_reassembled=tangent_reassembled,
                tangent_assemblies=tangent_assemblies,
                status=status,
                reason=reason,
                root=root,
            )
        )
        if converged:
            accepted = commit(context, trial.state, converged=True)
            increment = ArcLengthIncrement(
                displacement=accepted.displacement - committed.displacement,
                load_factor=accepted.load_factor - committed.load_factor,
                radius=radius,
            )
            reactions = recover_constraint_reactions(current_evaluation)
            step = StepResult(
                step_index=step_index,
                status=StepStatus.ACCEPTED,
                control_method=ControlMethod.ARC_LENGTH,
                load_factor=accepted.load_factor,
                requested_step_size=radius,
                accepted_step_size=radius,
                state_id=accepted.state_id,
                iterations=tuple(records),
                response={
                    "arc_radius": radius,
                    "beta": settings.beta,
                    "attempt_index": attempt_index,
                    "load_increment": increment.load_factor,
                    "displacement_increment": [float(v) for v in increment.displacement],
                    "displacement": [float(v) for v in accepted.displacement],
                    "reference_load": [float(v) for v in reference_load],
                    "predictor_load_increment": predictor_load,
                    "predictor_displacement_increment": [float(v) for v in positive_displacement],
                    "predictor_direction_cosine": predictor_cosine,
                    "strong_curvature": (
                        previous_increment is not None
                        and selected.direction_cosine is not None
                        and selected.direction_cosine < _CURVATURE_COSINE_LIMIT
                    ),
                    "curvature_cosine_limit": _CURVATURE_COSINE_LIMIT,
                    "arc_constraint": arc_value,
                    "eta_arc": eta_arc,
                    "eta_R": metrics.eta_residual,
                    "eta_u": metrics.eta_displacement,
                    "eta_E": metrics.eta_energy,
                    "free_residual": [float(v) for v in current_evaluation.free_residual],
                    "support_reactions": [
                        {
                            "dof_index": int(index),
                            "value": float(value),
                        }
                        for index, value in zip(
                            reactions.constrained_dofs,
                            reactions.constrained_reactions,
                            strict=True,
                        )
                    ],
                    "tangent_assemblies": tangent_assemblies,
                    "linear_solves": linear_rhs_solves,
                    "linear_factorizations": linear_factorizations,
                    "root_history": [
                        record.diagnostics.get("arc_length_root") for record in records
                    ],
                    "termination_reason": "CONVERGED",
                },
            )
            return _ArcAttempt(step, accepted, trial.response, increment, None)
        if status is IterationStatus.REJECTED:
            failure = _failure(
                FailureCode.NONCONVERGENCE,
                "maximum arc-length Newton iterations reached",
                step_index=step_index,
                iteration_index=iteration_index,
                details={
                    "eta_R": metrics.eta_residual,
                    "eta_u": metrics.eta_displacement,
                    "eta_E": metrics.eta_energy,
                    "eta_arc": eta_arc,
                },
            )
            break
        current = committed.displacement + selected.displacement_increment
        current_factor = committed.load_factor + selected.total_load_increment

    assert failure is not None
    rolled_back = rollback(context, None if last_trial is None else last_trial.state)
    assert rolled_back is committed
    step = StepResult(
        step_index=step_index,
        status=StepStatus.REJECTED,
        control_method=ControlMethod.ARC_LENGTH,
        load_factor=current_factor,
        requested_step_size=radius,
        iterations=tuple(records),
        failure=failure,
        response={
            "arc_radius": radius,
            "beta": settings.beta,
            "attempt_index": attempt_index,
            "predictor_load_increment": predictor_load,
            "predictor_displacement_increment": [float(v) for v in positive_displacement],
            "predictor_direction_cosine": predictor_cosine,
            "tangent_assemblies": tangent_assemblies,
            "linear_solves": linear_rhs_solves,
            "linear_factorizations": linear_factorizations,
            "termination_reason": failure.code.value,
        },
    )
    return _ArcAttempt(step, None, None, None, failure)


def _solve_result(
    model: ModelInput,
    *,
    status: SolveStatus,
    steps: list[StepResult],
    failures: list[FailureRecord],
    metadata: dict[str, Any],
) -> SolveResult:
    return SolveResult(
        model_id=model.model_id,
        model_sha256=model_sha256(model),
        solver_version=PACKAGE_VERSION,
        status=status,
        steps=tuple(steps),
        failures=tuple(failures),
        metadata={
            "control_method": ControlMethod.ARC_LENGTH.value,
            "newton_method": model.analysis.newton_method.value,
            "spherical_arc_length": True,
            **metadata,
        },
    )


def _solution_failure(
    model: ModelInput,
    failure: FailureRecord,
    *,
    state: CommittedState | None,
    response: ModelResponse | None,
    steps: list[StepResult],
    last_increment: ArcLengthIncrement | None,
    metadata: dict[str, Any] | None = None,
) -> ArcLengthSolution:
    return ArcLengthSolution(
        _solve_result(
            model,
            status=SolveStatus.FAILED,
            steps=steps,
            failures=[failure],
            metadata=metadata or {},
        ),
        state,
        response,
        last_increment,
    )


def _preflight_reference_load(
    adapter: ModelAdapter,
    model: ModelInput,
    committed: CommittedState,
) -> tuple[np.ndarray | None, ModelResponse | None, FailureRecord | None]:
    step_index = committed.step_index + 1
    try:
        context = begin_step(
            committed,
            target_load_factor=committed.load_factor,
            step_index=step_index,
        )
        base = evaluate_trial(
            context,
            adapter,
            model,
            trial_displacement=committed.displacement,
            load_factor=committed.load_factor,
            iteration_index=0,
        )
        shifted = evaluate_trial(
            context,
            adapter,
            model,
            trial_displacement=committed.displacement,
            load_factor=committed.load_factor + 1.0,
            iteration_index=0,
        )
        midpoint = evaluate_trial(
            context,
            adapter,
            model,
            trial_displacement=committed.displacement,
            load_factor=committed.load_factor + 0.5,
            iteration_index=0,
        )
    except (
        ArithmeticError,
        np.linalg.LinAlgError,
        RuntimeError,
        StateTransitionError,
        TypeError,
        ValueError,
    ) as error:
        return (
            None,
            None,
            _failure(
                FailureCode.STATE_ERROR,
                f"arc-length reference-load evaluation failed: {error}",
                step_index=step_index,
                details={"retryable": False},
            ),
        )
    for response in (base.response, shifted.response, midpoint.response):
        diagnostic = _response_failure(response, step_index=step_index, iteration_index=0)
        if diagnostic is not None:
            return None, base.response, diagnostic
    reference = np.asarray(shifted.response.external_force - base.response.external_force)
    failure = _proportional_load_failure(
        base.response,
        committed.load_factor,
        reference,
        step_index=step_index,
        iteration_index=0,
    )
    if failure is not None:
        return None, base.response, failure
    shifted_failure = _proportional_load_failure(
        shifted.response,
        committed.load_factor + 1.0,
        reference,
        step_index=step_index,
        iteration_index=0,
    )
    if shifted_failure is not None:
        return None, base.response, shifted_failure
    midpoint_failure = _proportional_load_failure(
        midpoint.response,
        committed.load_factor + 0.5,
        reference,
        step_index=step_index,
        iteration_index=0,
    )
    if midpoint_failure is not None:
        return None, base.response, midpoint_failure
    try:
        evaluation = build_equilibrium(base.response, adapter.constraint_map(model))
    except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
        return (
            None,
            base.response,
            _failure(
                FailureCode.MODEL_ERROR,
                f"arc-length constraint/equilibrium setup failed: {error}",
                step_index=step_index,
                details={"retryable": False},
            ),
        )
    free_reference = reference[evaluation.partition.free_dofs]
    if float(np.linalg.norm(free_reference)) <= np.finfo(float).tiny:
        return (
            None,
            base.response,
            _failure(
                FailureCode.CONTROL_ERROR,
                "arc length requires a non-zero proportional reference load on free DOFs",
                step_index=step_index,
                details={"retryable": False},
            ),
        )
    force_scale = float(
        np.linalg.norm(base.response.external_force[evaluation.partition.free_dofs])
        + np.linalg.norm(base.response.internal_force[evaluation.partition.free_dofs])
        + model.analysis.tolerances.force_floor
    )
    eta_residual = float(np.linalg.norm(evaluation.free_residual)) / force_scale
    if eta_residual > model.analysis.tolerances.residual:
        return (
            None,
            base.response,
            _failure(
                FailureCode.CONTROL_ERROR,
                "arc-length analysis must start from a converged equilibrium state",
                step_index=step_index,
                details={"initial_eta_R": eta_residual, "retryable": False},
            ),
        )
    reference = np.array(reference, copy=True)
    reference.setflags(write=False)
    return reference, base.response, None


def _previous_increment_failure(
    adapter: ModelAdapter,
    model: ModelInput,
    committed: CommittedState,
    response: ModelResponse,
    reference_load: np.ndarray,
    previous_increment: ArcLengthIncrement,
) -> FailureRecord | None:
    settings = model.analysis.arc_length
    assert settings is not None
    try:
        evaluation = build_equilibrium(response, adapter.constraint_map(model))
    except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
        return _failure(
            FailureCode.MODEL_ERROR,
            f"arc-length restart constraint/equilibrium setup failed: {error}",
            step_index=committed.step_index + 1,
            details={"retryable": False},
        )
    free = evaluation.partition.free_dofs
    constrained = evaluation.partition.constrained_dofs
    reference_norm_sq = float(reference_load[free] @ reference_load[free])
    augmented_norm = float(
        np.sqrt(
            max(
                0.0,
                _augmented_dot(
                    previous_increment.displacement,
                    previous_increment.load_factor,
                    previous_increment.displacement,
                    previous_increment.load_factor,
                    beta=settings.beta,
                    reference_norm_sq=reference_norm_sq,
                ),
            )
        )
    )
    relative_tolerance = 1.0e-8
    radius_scale = max(previous_increment.radius, augmented_norm, np.finfo(float).tiny)
    radius_error = abs(augmented_norm - previous_increment.radius)
    constrained_norm = float(np.linalg.norm(previous_increment.displacement[constrained]))
    constrained_tolerance = relative_tolerance * previous_increment.radius
    if radius_error > relative_tolerance * radius_scale or constrained_norm > constrained_tolerance:
        return _failure(
            FailureCode.STATE_ERROR,
            (
                "previous arc-length increment is inconsistent with its spherical radius "
                "or constraints"
            ),
            step_index=committed.step_index + 1,
            details={
                "retryable": False,
                "recorded_radius": previous_increment.radius,
                "augmented_increment_norm": augmented_norm,
                "radius_error": radius_error,
                "relative_radius_tolerance": relative_tolerance,
                "constrained_increment_norm": constrained_norm,
            },
        )
    return None


def solve_arc_length(
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    number_of_steps: int = 1,
    initial_state: CommittedState | None = None,
    previous_increment: ArcLengthIncrement | None = None,
    linear_options: LinearSolveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ArcLengthSolution:
    """Trace fixed proportional loading with adaptive spherical arc-length steps."""

    if isinstance(number_of_steps, bool) or not isinstance(number_of_steps, int):
        requested_steps = 0
    else:
        requested_steps = number_of_steps
    if requested_steps < 1 or requested_steps > model.analysis.step_control.max_steps:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "number_of_steps must be positive and no greater than step_control.max_steps",
            details={"number_of_steps": requested_steps, "retryable": False},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )
    if (
        model.analysis.control_method is not ControlMethod.ARC_LENGTH
        or model.analysis.arc_length is None
    ):
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "solve_arc_length requires control_method='arc_length' and arc_length settings",
            details={"retryable": False},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )
    if model.analysis.line_search.enabled:
        failure = _failure(
            FailureCode.CONTROL_ERROR,
            "P8 does not combine the coupled arc-length correction with P7 line search",
            details={"retryable": False},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )
    try:
        validation = adapter.validate(model)
    except (RuntimeError, TypeError, ValueError) as error:
        failure = _failure(
            FailureCode.MODEL_ERROR,
            f"adapter validation raised an error: {error}",
            details={"retryable": False},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )
    if not validation.valid:
        failure = _failure(
            FailureCode.MODEL_ERROR,
            "adapter validation failed",
            details={
                "retryable": False,
                "adapter_errors": [
                    {"code": issue.code, "message": issue.message, "entity_id": issue.entity_id}
                    for issue in validation.errors
                ],
            },
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )
    try:
        committed = initial_state or initialize_state(adapter, model)
    except (RuntimeError, StateTransitionError, TypeError, ValueError) as error:
        failure = _failure(
            FailureCode.STATE_ERROR,
            f"arc-length state initialization failed: {error}",
            details={"retryable": False},
        )
        return _solution_failure(
            model,
            failure,
            state=initial_state,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )
    if (
        previous_increment is not None
        and previous_increment.displacement.shape != committed.displacement.shape
    ):
        failure = _failure(
            FailureCode.STATE_ERROR,
            "previous arc-length increment does not match the committed DOF count",
            details={"retryable": False},
        )
        return _solution_failure(
            model,
            failure,
            state=committed,
            response=None,
            steps=[],
            last_increment=previous_increment,
        )

    reference_load, final_response, preflight_failure = _preflight_reference_load(
        adapter,
        model,
        committed,
    )
    if preflight_failure is not None or reference_load is None:
        assert preflight_failure is not None
        return _solution_failure(
            model,
            preflight_failure,
            state=committed,
            response=final_response,
            steps=[],
            last_increment=previous_increment,
        )
    assert final_response is not None
    if previous_increment is not None:
        increment_failure = _previous_increment_failure(
            adapter,
            model,
            committed,
            final_response,
            reference_load,
            previous_increment,
        )
        if increment_failure is not None:
            return _solution_failure(
                model,
                increment_failure,
                state=committed,
                response=final_response,
                steps=[],
                last_increment=previous_increment,
            )

    arc = model.analysis.arc_length
    controls = model.analysis.step_control
    current_radius = float(arc.radius)
    last_increment = previous_increment
    steps: list[StepResult] = []
    accepted_steps = 0
    retry_count = 0
    cutbacks = 0
    growths = 0
    curvature_reductions = 0

    while accepted_steps < requested_steps:
        attempt = _attempt_arc_step(
            adapter,
            model,
            committed,
            reference_load,
            radius=current_radius,
            attempt_index=retry_count,
            previous_increment=last_increment,
            linear_options=linear_options,
            progress_callback=progress_callback,
            accepted_steps=accepted_steps,
        )
        if attempt.succeeded:
            assert attempt.committed_state is not None and attempt.increment is not None
            next_radius = current_radius
            if attempt.step.response.get("strong_curvature") is True:
                reduced = max(float(arc.min_radius), current_radius * controls.cutback_factor)
                if reduced < current_radius:
                    curvature_reductions += 1
                next_radius = reduced
            elif len(attempt.step.iterations) <= controls.target_iterations:
                grown = min(float(arc.max_radius), current_radius * controls.growth_factor)
                if grown > current_radius:
                    growths += 1
                next_radius = grown
            response = dict(attempt.step.response)
            response.update(
                {
                    "next_arc_radius": next_radius,
                    "will_retry": False,
                    "adaptive_termination": None,
                }
            )
            steps.append(attempt.step.model_copy(update={"response": response}))
            committed = attempt.committed_state
            final_response = attempt.final_response
            last_increment = attempt.increment
            current_radius = next_radius
            accepted_steps += 1
            retry_count = 0
            continue

        assert attempt.failure is not None
        disposition = failure_disposition(attempt.failure)
        explicitly_retryable = attempt.failure.details.get("retryable", True) is not False
        at_minimum = current_radius <= float(arc.min_radius) * (1.0 + 1.0e-12)
        retries_exhausted = retry_count >= controls.max_retries
        will_retry = (
            disposition.retryable
            and explicitly_retryable
            and not at_minimum
            and not retries_exhausted
        )
        next_radius = (
            max(float(arc.min_radius), current_radius * controls.cutback_factor)
            if will_retry
            else None
        )
        termination = None
        terminal_failure = attempt.failure
        if not will_retry:
            if not disposition.retryable or not explicitly_retryable:
                termination = "NONRETRYABLE_FAILURE"
            elif at_minimum:
                termination = "MIN_RADIUS_REACHED"
            else:
                termination = "MAX_RETRIES_REACHED"
            details = dict(attempt.failure.details)
            details.update(
                {
                    "adaptive_termination": termination,
                    "terminal_arc_radius": current_radius,
                    "retry_count": retry_count,
                }
            )
            terminal_failure = attempt.failure.model_copy(update={"details": details})
        response = dict(attempt.step.response)
        response.update(
            {
                "next_arc_radius": next_radius,
                "will_retry": will_retry,
                "adaptive_termination": termination,
            }
        )
        updates: dict[str, object] = {"response": response}
        if not will_retry:
            updates["failure"] = terminal_failure
        steps.append(attempt.step.model_copy(update=updates))
        if not will_retry:
            return _solution_failure(
                model,
                terminal_failure,
                state=committed,
                response=final_response,
                steps=steps,
                last_increment=last_increment,
                metadata={
                    "requested_steps": requested_steps,
                    "accepted_steps": accepted_steps,
                    "cutbacks": cutbacks,
                    "growths": growths,
                    "curvature_reductions": curvature_reductions,
                },
            )
        assert next_radius is not None
        current_radius = next_radius
        retry_count += 1
        cutbacks += 1

    return ArcLengthSolution(
        _solve_result(
            model,
            status=SolveStatus.SUCCEEDED,
            steps=steps,
            failures=[],
            metadata={
                "requested_steps": requested_steps,
                "accepted_steps": accepted_steps,
                "rejected_attempts": sum(step.status is StepStatus.REJECTED for step in steps),
                "cutbacks": cutbacks,
                "growths": growths,
                "curvature_reductions": curvature_reductions,
                "initial_radius": arc.radius,
                "minimum_radius": arc.min_radius,
                "maximum_radius": arc.max_radius,
                "beta": arc.beta,
                "root_selection": arc.root_selection.value,
                "reference_load": [float(value) for value in reference_load],
            },
        ),
        committed,
        final_response,
        last_increment,
    )


__all__ = [
    "ARC_INCREMENT_SCHEMA_VERSION",
    "ArcLengthIncrement",
    "ArcLengthRootCandidate",
    "ArcLengthRootResult",
    "ArcLengthRootStatus",
    "ArcLengthSolution",
    "select_arc_length_root",
    "solve_arc_length",
]
