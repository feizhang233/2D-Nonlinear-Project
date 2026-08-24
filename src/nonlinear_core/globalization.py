"""P7 Newton full-step, backtracking, and conservative orthogonality searches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import ArrayLike

from nonlinear_core.equilibrium import EquilibriumEvaluation
from nonlinear_core.model import LineSearchMethod, LineSearchOptions


class LineSearchStatus(StrEnum):
    ACCEPTED = "accepted"
    FAILED = "failed"


class MeritFunction(StrEnum):
    FULL_STEP = "full_step"
    RESIDUAL_L2_NONCONSERVATIVE = "residual_l2_nonconservative"
    DIRECTIONAL_RESIDUAL_CONSERVATIVE = "directional_residual_conservative"


@dataclass(frozen=True, slots=True)
class LineSearchSample:
    alpha: float
    merit: float
    directional_residual: float

    def __post_init__(self) -> None:
        values = np.asarray([self.alpha, self.merit, self.directional_residual], dtype=float)
        if not np.all(np.isfinite(values)) or self.alpha <= 0.0:
            raise ValueError("line-search samples must contain finite values and positive alpha")


@dataclass(frozen=True, slots=True)
class LineSearchResult:
    status: LineSearchStatus
    method: LineSearchMethod | None
    merit_function: MeritFunction
    alpha: float | None
    samples: tuple[LineSearchSample, ...] = ()
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", LineSearchStatus(self.status))
        object.__setattr__(self, "merit_function", MeritFunction(self.merit_function))
        if self.method is not None:
            object.__setattr__(self, "method", LineSearchMethod(self.method))
        if self.status is LineSearchStatus.ACCEPTED:
            if self.alpha is None or not np.isfinite(self.alpha) or self.alpha <= 0.0:
                raise ValueError("accepted line searches require a positive finite alpha")
            if self.failure_reason is not None:
                raise ValueError("accepted line searches cannot carry a failure reason")
        elif self.alpha is not None or not self.failure_reason:
            raise ValueError("failed line searches require a reason and no accepted alpha")

    @property
    def accepted(self) -> bool:
        return self.status is LineSearchStatus.ACCEPTED


EvaluationFunction = Callable[[np.ndarray], EquilibriumEvaluation]


def _sample(
    alpha: float,
    current: np.ndarray,
    direction: np.ndarray,
    free_direction: np.ndarray,
    evaluate_at: EvaluationFunction,
) -> LineSearchSample:
    evaluation = evaluate_at(current + alpha * direction)
    residual = evaluation.free_residual
    return LineSearchSample(
        alpha=alpha,
        merit=0.5 * float(residual @ residual),
        directional_residual=float(free_direction @ residual),
    )


def _backtracking(
    current_evaluation: EquilibriumEvaluation,
    evaluate_at: EvaluationFunction,
    current: np.ndarray,
    direction: np.ndarray,
    options: LineSearchOptions,
) -> LineSearchResult:
    free = current_evaluation.partition.free_dofs
    free_direction = direction[free]
    residual = current_evaluation.free_residual
    initial_merit = 0.5 * float(residual @ residual)
    samples: list[LineSearchSample] = []
    alpha = 1.0
    for _ in range(options.max_iterations):
        alpha = max(float(alpha), float(options.min_alpha))
        sample = _sample(alpha, current, direction, free_direction, evaluate_at)
        samples.append(sample)
        sufficient_decrease = sample.merit <= initial_merit * (1.0 - 1.0e-4 * alpha)
        if initial_merit == 0.0 or sufficient_decrease:
            return LineSearchResult(
                status=LineSearchStatus.ACCEPTED,
                method=LineSearchMethod.BACKTRACKING,
                merit_function=MeritFunction.RESIDUAL_L2_NONCONSERVATIVE,
                alpha=alpha,
                samples=tuple(samples),
            )
        if alpha <= options.min_alpha:
            break
        alpha *= options.reduction_factor
    return LineSearchResult(
        status=LineSearchStatus.FAILED,
        method=LineSearchMethod.BACKTRACKING,
        merit_function=MeritFunction.RESIDUAL_L2_NONCONSERVATIVE,
        alpha=None,
        samples=tuple(samples),
        failure_reason="residual-L2 backtracking did not obtain sufficient decrease",
    )


def _orthogonality(
    current_evaluation: EquilibriumEvaluation,
    evaluate_at: EvaluationFunction,
    current: np.ndarray,
    direction: np.ndarray,
    options: LineSearchOptions,
    *,
    conservative: bool,
) -> LineSearchResult:
    if not conservative:
        return LineSearchResult(
            status=LineSearchStatus.FAILED,
            method=LineSearchMethod.ORTHOGONALITY,
            merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
            alpha=None,
            failure_reason="orthogonality search requires response metadata conservative=true",
        )
    free = current_evaluation.partition.free_dofs
    free_direction = direction[free]
    g_left = float(free_direction @ current_evaluation.free_residual)
    scale = max(1.0, abs(g_left))
    tolerance = 1.0e-10 * scale
    if abs(g_left) <= tolerance:
        return LineSearchResult(
            status=LineSearchStatus.ACCEPTED,
            method=LineSearchMethod.ORTHOGONALITY,
            merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
            alpha=1.0,
        )

    samples: list[LineSearchSample] = []
    right = 1.0
    right_sample = _sample(right, current, direction, free_direction, evaluate_at)
    samples.append(right_sample)
    if abs(right_sample.directional_residual) <= tolerance:
        return LineSearchResult(
            status=LineSearchStatus.ACCEPTED,
            method=LineSearchMethod.ORTHOGONALITY,
            merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
            alpha=right,
            samples=tuple(samples),
        )
    left = 0.0
    g_right = right_sample.directional_residual
    if g_left * g_right > 0.0:
        alpha = right * options.reduction_factor
        while len(samples) < options.max_iterations and alpha >= options.min_alpha:
            sample = _sample(alpha, current, direction, free_direction, evaluate_at)
            samples.append(sample)
            if abs(sample.directional_residual) <= tolerance:
                return LineSearchResult(
                    status=LineSearchStatus.ACCEPTED,
                    method=LineSearchMethod.ORTHOGONALITY,
                    merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
                    alpha=alpha,
                    samples=tuple(samples),
                )
            if g_left * sample.directional_residual <= 0.0:
                right = alpha
                g_right = sample.directional_residual
                break
            alpha *= options.reduction_factor
        else:
            return LineSearchResult(
                status=LineSearchStatus.FAILED,
                method=LineSearchMethod.ORTHOGONALITY,
                merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
                alpha=None,
                samples=tuple(samples),
                failure_reason="directional residual did not bracket an orthogonality root",
            )

    while len(samples) < options.max_iterations:
        alpha = 0.5 * (left + right)
        if alpha < options.min_alpha:
            break
        sample = _sample(alpha, current, direction, free_direction, evaluate_at)
        samples.append(sample)
        g_mid = sample.directional_residual
        if abs(g_mid) <= tolerance:
            return LineSearchResult(
                status=LineSearchStatus.ACCEPTED,
                method=LineSearchMethod.ORTHOGONALITY,
                merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
                alpha=alpha,
                samples=tuple(samples),
            )
        if g_left * g_mid <= 0.0:
            right = alpha
            g_right = g_mid
        else:
            left = alpha
            g_left = g_mid
    return LineSearchResult(
        status=LineSearchStatus.FAILED,
        method=LineSearchMethod.ORTHOGONALITY,
        merit_function=MeritFunction.DIRECTIONAL_RESIDUAL_CONSERVATIVE,
        alpha=None,
        samples=tuple(samples),
        failure_reason=(
            "orthogonality root did not reach the directional-residual tolerance; "
            f"last bracket residual={g_right:.6e}"
        ),
    )


def apply_line_search(
    current_evaluation: EquilibriumEvaluation,
    evaluate_at: EvaluationFunction,
    current_displacement: ArrayLike,
    direction: ArrayLike,
    options: LineSearchOptions,
    *,
    conservative: bool = False,
) -> LineSearchResult:
    """Globalize one Newton direction without committing any sampled trial state."""

    current = np.asarray(current_displacement, dtype=float)
    update = np.asarray(direction, dtype=float)
    size = current_evaluation.partition.size
    if current.shape != (size,) or update.shape != (size,):
        raise ValueError("line-search displacement and direction must match the system size")
    if not np.all(np.isfinite(current)) or not np.all(np.isfinite(update)):
        raise ValueError("line-search displacement and direction must be finite")
    if not options.enabled:
        return LineSearchResult(
            status=LineSearchStatus.ACCEPTED,
            method=None,
            merit_function=MeritFunction.FULL_STEP,
            alpha=1.0,
        )
    if options.method is LineSearchMethod.BACKTRACKING:
        return _backtracking(current_evaluation, evaluate_at, current, update, options)
    return _orthogonality(
        current_evaluation,
        evaluate_at,
        current,
        update,
        options,
        conservative=conservative,
    )


__all__ = [
    "LineSearchResult",
    "LineSearchSample",
    "LineSearchStatus",
    "MeritFunction",
    "apply_line_search",
]
