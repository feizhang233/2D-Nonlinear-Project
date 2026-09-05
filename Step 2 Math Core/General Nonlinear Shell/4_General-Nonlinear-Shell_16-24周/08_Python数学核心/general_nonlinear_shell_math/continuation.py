"""A minimal spherical arc-length corrector for the V11 scalar benchmark."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ArcLengthIteration:
    iteration: int
    q: float
    load_factor: float
    equilibrium_residual: float
    constraint_residual: float
    correction_norm: float


@dataclass(frozen=True)
class ArcLengthResult:
    q: float
    load_factor: float
    predictor_q: float
    predictor_load_factor: float
    converged: bool
    iterations: tuple[ArcLengthIteration, ...]


def scalar_equilibrium(q: float, load_factor: float) -> float:
    return q - q**3 - load_factor


def scalar_tangent(q: float) -> float:
    return 1.0 - 3.0 * q**2


def solve_scalar_arc_length_step(
    *,
    q_n: float,
    load_factor_n: float,
    arc_length: float,
    beta: float = 1.0,
    reference_load: float = 1.0,
    direction: float = 1.0,
    tolerance: float = 1.0e-13,
    max_iterations: int = 20,
) -> ArcLengthResult:
    """Solve one spherical arc-length step for ``q-q^3-lambda=0``."""

    q_base = float(q_n)
    load_base = float(load_factor_n)
    ds = float(arc_length)
    beta_value = float(beta)
    reference_value = float(reference_load)
    direction_value = 1.0 if direction >= 0.0 else -1.0
    if not all(
        np.isfinite(v) for v in (q_base, load_base, ds, beta_value, reference_value)
    ):
        raise ValueError("arc-length inputs must be finite")
    if ds <= 0.0 or beta_value <= 0.0 or reference_value == 0.0:
        raise ValueError(
            "arc_length and beta must be positive and reference_load nonzero"
        )

    tangent = scalar_tangent(q_base)
    if abs(tangent) <= 1.0e-14:
        raise ValueError("predictor tangent is singular at the supplied base point")
    q_per_load = reference_value / tangent
    load_increment = (
        direction_value
        * ds
        / np.sqrt(q_per_load**2 + (beta_value * reference_value) ** 2)
    )
    q_increment = q_per_load * load_increment
    q = q_base + q_increment
    load_factor = load_base + load_increment
    predictor_q = q
    predictor_load = load_factor

    history: list[ArcLengthIteration] = []
    converged = False
    for iteration in range(max_iterations + 1):
        delta_q = q - q_base
        delta_load = load_factor - load_base
        equilibrium = scalar_equilibrium(q, load_factor)
        constraint = (
            delta_q**2 + (beta_value * reference_value * delta_load) ** 2 - ds**2
        )
        if max(abs(equilibrium), abs(constraint)) <= tolerance:
            history.append(
                ArcLengthIteration(
                    iteration=iteration,
                    q=q,
                    load_factor=load_factor,
                    equilibrium_residual=equilibrium,
                    constraint_residual=constraint,
                    correction_norm=0.0,
                )
            )
            converged = True
            break

        jacobian = np.array(
            [
                [scalar_tangent(q), -1.0],
                [2.0 * delta_q, 2.0 * (beta_value * reference_value) ** 2 * delta_load],
            ],
            dtype=float,
        )
        correction = np.linalg.solve(jacobian, -np.array([equilibrium, constraint]))
        q += float(correction[0])
        load_factor += float(correction[1])
        corrected_delta_q = q - q_base
        corrected_delta_load = load_factor - load_base
        history.append(
            ArcLengthIteration(
                iteration=iteration,
                q=q,
                load_factor=load_factor,
                equilibrium_residual=scalar_equilibrium(q, load_factor),
                constraint_residual=(
                    corrected_delta_q**2
                    + (beta_value * reference_value * corrected_delta_load) ** 2
                    - ds**2
                ),
                correction_norm=float(np.linalg.norm(correction)),
            )
        )

    return ArcLengthResult(
        q=q,
        load_factor=load_factor,
        predictor_q=predictor_q,
        predictor_load_factor=predictor_load,
        converged=converged,
        iterations=tuple(history),
    )
