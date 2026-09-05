"""Directional-derivative checks for residual/tangent consistency."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
VectorFunction = Callable[[FloatArray], FloatArray]


def polynomial_internal_minus_external_residual(
    q: ArrayLike, load_factor: float
) -> FloatArray:
    values = np.asarray(q, dtype=float)
    if values.shape != (2,):
        raise ValueError("q must have shape (2,)")
    q1, q2 = values
    return np.array(
        [
            q1 + q1 * q2 + q1**3 / 3.0 - load_factor,
            2.0 * q2 + 0.5 * q1**2 + q2**3 / 3.0,
        ],
        dtype=float,
    )


def polynomial_tangent(q: ArrayLike) -> FloatArray:
    values = np.asarray(q, dtype=float)
    if values.shape != (2,):
        raise ValueError("q must have shape (2,)")
    q1, q2 = values
    return np.array(
        [[1.0 + q2 + q1**2, q1], [q1, 2.0 + q2**2]],
        dtype=float,
    )


@dataclass(frozen=True)
class DirectionalDerivativeSample:
    step: float
    finite_difference: FloatArray
    analytic: FloatArray
    absolute_error: float
    relative_error: float


def directional_derivative_scan(
    function: VectorFunction,
    tangent: ArrayLike,
    point: ArrayLike,
    direction: ArrayLike,
    steps: Iterable[float],
    *,
    residual_sign: float = 1.0,
) -> list[DirectionalDerivativeSample]:
    """Compare ``tangent @ p`` to a signed central residual difference.

    Use ``residual_sign=-1`` when ``function`` returns the canonical
    ``r=f_ext-f_int`` while ``tangent`` is ``d(f_int-f_ext)/dq``.
    """

    point_array = np.asarray(point, dtype=float)
    direction_array = np.asarray(direction, dtype=float)
    tangent_array = np.asarray(tangent, dtype=float)
    if point_array.ndim != 1 or direction_array.shape != point_array.shape:
        raise ValueError("point and direction must be vectors with equal shape")
    if tangent_array.shape != (point_array.size, point_array.size):
        raise ValueError("tangent shape does not match point size")
    analytic = tangent_array @ direction_array
    scale = max(float(np.linalg.norm(analytic)), 1.0)
    samples: list[DirectionalDerivativeSample] = []
    for raw_step in steps:
        step = float(raw_step)
        if not np.isfinite(step) or step <= 0.0:
            raise ValueError("all finite-difference steps must be finite and positive")
        plus = np.asarray(function(point_array + step * direction_array), dtype=float)
        minus = np.asarray(function(point_array - step * direction_array), dtype=float)
        finite_difference = residual_sign * (plus - minus) / (2.0 * step)
        absolute_error = float(np.linalg.norm(finite_difference - analytic))
        samples.append(
            DirectionalDerivativeSample(
                step=step,
                finite_difference=finite_difference,
                analytic=analytic.copy(),
                absolute_error=absolute_error,
                relative_error=absolute_error / scale,
            )
        )
    return samples
