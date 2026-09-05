"""Configuration-dependent load primitives and their analytic derivatives."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
ROTATE_90 = np.array([[0.0, -1.0], [1.0, 0.0]], dtype=float)


def _point2(value: ArrayLike, *, name: str) -> FloatArray:
    point = np.asarray(value, dtype=float)
    if point.shape != (2,):
        raise ValueError(f"{name} must have shape (2,), got {point.shape}")
    if not np.all(np.isfinite(point)):
        raise ValueError(f"{name} must contain only finite values")
    return point


def follower_line_force(x1: ArrayLike, x2: ArrayLike, pressure: float) -> FloatArray:
    """Return ``[f1x,f1y,f2x,f2y]`` for a two-node follower-pressure line."""

    first = _point2(x1, name="x1")
    second = _point2(x2, name="x2")
    pressure_value = float(pressure)
    if not np.isfinite(pressure_value):
        raise ValueError("pressure must be finite")
    nodal_force = 0.5 * pressure_value * (ROTATE_90 @ (second - first))
    return np.concatenate((nodal_force, nodal_force))


def follower_line_tangent(pressure: float) -> FloatArray:
    """Return ``d f_ext / d[x1,x2]`` for :func:`follower_line_force`."""

    pressure_value = float(pressure)
    if not np.isfinite(pressure_value):
        raise ValueError("pressure must be finite")
    block = 0.5 * pressure_value * ROTATE_90
    return np.block([[-block, block], [-block, block]])
