"""GNA reference models and a dense spherical arc-length path follower."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PotentialBifurcationResult:
    critical_load_factor: float
    zero_branch_tangent: float
    positive_branch: float | None
    negative_branch: float | None
    nonzero_branch_tangent: float | None
    classification: str


def quartic_potential_bifurcation(load_factor: float) -> PotentialBifurcationResult:
    """Solve V10: Pi=(10-2 lambda)q^2/2+q^4/4 at one load factor."""

    if not math.isfinite(load_factor):
        raise ValueError("load_factor must be finite")
    branch_squared = 2.0 * load_factor - 10.0
    positive = math.sqrt(branch_squared) if branch_squared >= 0.0 else None
    negative = -positive if positive is not None else None
    branch_tangent = 4.0 * load_factor - 20.0 if positive is not None else None
    return PotentialBifurcationResult(
        critical_load_factor=5.0,
        zero_branch_tangent=10.0 - 2.0 * load_factor,
        positive_branch=positive,
        negative_branch=negative,
        nonzero_branch_tangent=branch_tangent,
        classification="symmetric_supercritical_bifurcation",
    )


@dataclass(frozen=True)
class TwoBarArchLimitPoint:
    original_bar_length_mm: float
    displacement_mm: float
    load_n: float
    nondimensional_alpha: float
    nondimensional_r: float
    nondimensional_s: float
    nondimensional_load: float


@dataclass(frozen=True)
class TwoBarArch:
    """Symmetric shallow two-bar truss with a vertical apex displacement."""

    half_span_mm: float
    initial_height_mm: float
    young_mpa: float
    area_mm2: float

    def __post_init__(self) -> None:
        for name in ("half_span_mm", "initial_height_mm", "young_mpa", "area_mm2"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")

    @property
    def original_bar_length_mm(self) -> float:
        return math.hypot(self.half_span_mm, self.initial_height_mm)

    def internal_force_n(self, displacement_mm: float) -> float:
        """Exact vertical restoring force P(w), positive downward."""

        y = self.initial_height_mm - float(displacement_mm)
        current_length = math.hypot(self.half_span_mm, y)
        original_length = self.original_bar_length_mm
        return 2.0 * self.young_mpa * self.area_mm2 * y * (original_length - current_length) / (
            original_length * current_length
        )

    def tangent_n_per_mm(self, displacement_mm: float) -> float:
        """Consistent derivative dP/dw of the exact restoring force."""

        original_length = self.original_bar_length_mm
        alpha = self.half_span_mm / original_length
        s = (self.initial_height_mm - float(displacement_mm)) / original_length
        r = math.sqrt(alpha**2 + s**2)
        return 2.0 * self.young_mpa * self.area_mm2 * (1.0 - alpha**2 / r**3) / original_length

    def limit_point(self) -> TwoBarArchLimitPoint:
        """Closed-form first positive-load limit point."""

        original_length = self.original_bar_length_mm
        alpha = self.half_span_mm / original_length
        r_star = alpha ** (2.0 / 3.0)
        s_squared = r_star**2 - alpha**2
        if s_squared <= 0.0:
            raise ValueError("geometry has no real shallow-arch limit point")
        s_star = math.sqrt(s_squared)
        p_star = s_star * (1.0 / r_star - 1.0)
        load = 2.0 * self.young_mpa * self.area_mm2 * p_star
        displacement = self.initial_height_mm - s_star * original_length
        return TwoBarArchLimitPoint(
            original_length,
            displacement,
            load,
            alpha,
            r_star,
            s_star,
            p_star,
        )


@dataclass(frozen=True)
class ArcLengthSettings:
    step_size: float
    beta: float
    max_steps: int
    max_iterations: int = 30
    residual_tolerance: float = 1e-10
    constraint_tolerance: float = 1e-10
    minimum_step_size: float | None = None
    maximum_step_size: float | None = None
    growth_factor: float = 1.15
    cutback_factor: float = 0.5
    maximum_cutbacks: int = 10

    def __post_init__(self) -> None:
        if not math.isfinite(self.step_size) or self.step_size <= 0.0:
            raise ValueError("step_size must be finite and positive")
        if not math.isfinite(self.beta) or self.beta <= 0.0:
            raise ValueError("beta must be finite and positive")
        if self.max_steps < 1 or self.max_iterations < 1 or self.maximum_cutbacks < 0:
            raise ValueError("iteration counts are invalid")
        if not (0.0 < self.cutback_factor < 1.0) or self.growth_factor < 1.0:
            raise ValueError("step adaptation factors are invalid")
        if self.residual_tolerance <= 0.0 or self.constraint_tolerance <= 0.0:
            raise ValueError("tolerances must be positive")


@dataclass(frozen=True)
class ArcLengthPoint:
    step: int
    displacement: FloatArray
    load_factor: float
    residual_norm: float
    constraint_error: float
    iterations: int
    accepted_step_size: float
    rejected_attempts: int
    minimum_tangent_eigenvalue: float
    predictor_load_increment: float
    predictor_orientation: float | None
    predictor_root_sign: int


def spherical_arc_constraint(
    displacement_increment: ArrayLike,
    load_increment: float,
    reference_load: ArrayLike,
    *,
    beta: float,
    step_size: float,
) -> float:
    """Evaluate g=dq.T dq + beta^2 dlambda^2 f.T f - ds^2."""

    dq = np.asarray(displacement_increment, dtype=float).reshape(-1)
    force = np.asarray(reference_load, dtype=float).reshape(-1)
    if dq.size != force.size:
        raise ValueError("displacement increment and reference load sizes differ")
    return float(dq @ dq + beta**2 * load_increment**2 * (force @ force) - step_size**2)


def arc_length_augmented_system(
    tangent: ArrayLike,
    reference_load: ArrayLike,
    displacement_increment: ArrayLike,
    load_increment: float,
    *,
    beta: float,
) -> FloatArray:
    """Build the Newton matrix for equilibrium plus spherical arc length."""

    matrix = np.asarray(tangent, dtype=float)
    force = np.asarray(reference_load, dtype=float).reshape(-1)
    dq = np.asarray(displacement_increment, dtype=float).reshape(-1)
    if matrix.shape != (force.size, force.size) or dq.size != force.size:
        raise ValueError("augmented-system dimensions do not agree")
    augmented = np.zeros((force.size + 1, force.size + 1), dtype=float)
    augmented[:-1, :-1] = matrix
    augmented[:-1, -1] = -force
    augmented[-1, :-1] = 2.0 * dq
    augmented[-1, -1] = 2.0 * beta**2 * load_increment * float(force @ force)
    return augmented


def _as_force(function: Callable[[FloatArray], ArrayLike], q: FloatArray) -> FloatArray:
    value = np.asarray(function(q), dtype=float).reshape(-1)
    if value.size != q.size or not np.all(np.isfinite(value)):
        raise ValueError("internal force callback returned invalid data")
    return value


def _as_tangent(function: Callable[[FloatArray], ArrayLike], q: FloatArray) -> FloatArray:
    value = np.asarray(function(q), dtype=float)
    if value.shape != (q.size, q.size) or not np.all(np.isfinite(value)):
        raise ValueError("tangent callback returned invalid data")
    return value


def trace_spherical_arc_length(
    internal_force: Callable[[FloatArray], ArrayLike],
    tangent: Callable[[FloatArray], ArrayLike],
    reference_load: ArrayLike,
    initial_displacement: ArrayLike,
    initial_load_factor: float,
    settings: ArcLengthSettings,
) -> list[ArcLengthPoint]:
    """Trace a conservative dead-load equilibrium path with cutback/rollback.

    The reference equation is ``r(q,lambda)=f_int(q)-lambda*f_ref=0``.
    Each failed trial is discarded before retrying with a smaller arc length.
    The routine returns committed states only.
    """

    force = np.asarray(reference_load, dtype=float).reshape(-1)
    q_committed = np.asarray(initial_displacement, dtype=float).reshape(-1).copy()
    if force.size != q_committed.size or force.size == 0:
        raise ValueError("reference load and initial displacement sizes must agree")
    if not np.all(np.isfinite(force)) or np.linalg.norm(force) == 0.0:
        raise ValueError("reference load must be finite and non-zero")
    if not math.isfinite(initial_load_factor):
        raise ValueError("initial_load_factor must be finite")
    lambda_committed = float(initial_load_factor)
    initial_residual = _as_force(internal_force, q_committed) - lambda_committed * force
    initial_scale = max(np.linalg.norm(lambda_committed * force), np.linalg.norm(initial_residual), 1.0)
    if np.linalg.norm(initial_residual) > settings.residual_tolerance * initial_scale:
        raise ValueError("initial state is not in equilibrium")

    minimum_step = settings.minimum_step_size or settings.step_size / 2.0**settings.maximum_cutbacks
    maximum_step = settings.maximum_step_size or settings.step_size
    if minimum_step <= 0.0 or maximum_step < minimum_step:
        raise ValueError("minimum/maximum step sizes are invalid")
    current_step = min(settings.step_size, maximum_step)
    previous_increment: tuple[FloatArray, float] | None = None
    points: list[ArcLengthPoint] = []

    for step_index in range(1, settings.max_steps + 1):
        rejected = 0
        accepted = False
        trial_step = current_step
        while rejected <= settings.maximum_cutbacks and trial_step >= minimum_step * (1.0 - 1e-14):
            tangent_committed = _as_tangent(tangent, q_committed)
            try:
                load_direction = np.linalg.solve(tangent_committed, force)
            except np.linalg.LinAlgError:
                load_direction = np.linalg.lstsq(tangent_committed, force, rcond=None)[0]
            denominator = math.sqrt(
                float(load_direction @ load_direction) + settings.beta**2 * float(force @ force)
            )
            if denominator <= 0.0 or not math.isfinite(denominator):
                raise RuntimeError("arc-length predictor has an invalid norm")
            delta_lambda_predictor = trial_step / denominator
            delta_q_predictor = delta_lambda_predictor * load_direction
            predictor_orientation: float | None = None
            predictor_root_sign = 1
            if previous_increment is not None:
                previous_q, previous_lambda = previous_increment
                predictor_orientation = float(delta_q_predictor @ previous_q) + (
                    settings.beta**2
                    * delta_lambda_predictor
                    * previous_lambda
                    * float(force @ force)
                )
                if predictor_orientation < 0.0:
                    delta_lambda_predictor *= -1.0
                    delta_q_predictor *= -1.0
                    predictor_root_sign = -1

            q_trial = q_committed + delta_q_predictor
            lambda_trial = lambda_committed + delta_lambda_predictor
            converged = False
            final_residual_norm = math.inf
            final_constraint_error = math.inf
            iteration = 0
            for iteration in range(1, settings.max_iterations + 1):
                delta_q = q_trial - q_committed
                delta_lambda = lambda_trial - lambda_committed
                internal = _as_force(internal_force, q_trial)
                residual = internal - lambda_trial * force
                constraint = spherical_arc_constraint(
                    delta_q,
                    delta_lambda,
                    force,
                    beta=settings.beta,
                    step_size=trial_step,
                )
                residual_scale = max(float(np.linalg.norm(internal)), float(np.linalg.norm(lambda_trial * force)), 1.0)
                final_residual_norm = float(np.linalg.norm(residual) / residual_scale)
                final_constraint_error = abs(constraint) / max(trial_step**2, 1.0)
                if (
                    final_residual_norm <= settings.residual_tolerance
                    and final_constraint_error <= settings.constraint_tolerance
                ):
                    converged = True
                    break
                tangent_trial = _as_tangent(tangent, q_trial)
                augmented = arc_length_augmented_system(
                    tangent_trial,
                    force,
                    delta_q,
                    delta_lambda,
                    beta=settings.beta,
                )
                right = -np.concatenate((residual, np.array([constraint])))
                try:
                    correction = np.linalg.solve(augmented, right)
                except np.linalg.LinAlgError:
                    converged = False
                    break
                q_trial += correction[:-1]
                lambda_trial += float(correction[-1])
                if not np.all(np.isfinite(q_trial)) or not math.isfinite(lambda_trial):
                    converged = False
                    break

            if converged:
                committed_delta_q = q_trial - q_committed
                committed_delta_lambda = lambda_trial - lambda_committed
                q_committed = q_trial.copy()
                lambda_committed = float(lambda_trial)
                previous_increment = (committed_delta_q.copy(), committed_delta_lambda)
                committed_tangent = _as_tangent(tangent, q_committed)
                tangent_eigenvalues = np.linalg.eigvalsh(
                    0.5 * (committed_tangent + committed_tangent.T)
                )
                points.append(
                    ArcLengthPoint(
                        step_index,
                        q_committed.copy(),
                        lambda_committed,
                        final_residual_norm,
                        final_constraint_error,
                        iteration,
                        trial_step,
                        rejected,
                        float(tangent_eigenvalues[0]),
                        float(delta_lambda_predictor),
                        predictor_orientation,
                        predictor_root_sign,
                    )
                )
                accepted = True
                if iteration <= 5:
                    current_step = min(maximum_step, trial_step * settings.growth_factor)
                else:
                    current_step = trial_step
                break

            rejected += 1
            trial_step *= settings.cutback_factor

        if not accepted:
            raise RuntimeError(
                f"arc-length step {step_index} failed after {rejected} rejected attempts; "
                f"last trial step was {trial_step:.6g}"
            )

    return points
