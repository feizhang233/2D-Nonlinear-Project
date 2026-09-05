"""SO(3) operations with an explicit spatial/material increment convention."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _vector3(value: ArrayLike, *, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def skew(vector: ArrayLike) -> FloatArray:
    """Return the cross-product matrix ``[vector]_x``."""

    x, y, z = _vector3(vector, name="vector")
    return np.array(
        [[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]],
        dtype=float,
    )


def so3_exp(rotation_vector: ArrayLike) -> FloatArray:
    """Evaluate the SO(3) exponential using stable small-angle series."""

    theta_vector = _vector3(rotation_vector, name="rotation_vector")
    theta_squared = float(theta_vector @ theta_vector)
    theta = float(np.sqrt(theta_squared))
    omega = skew(theta_vector)

    if theta < 1.0e-8:
        # sin(theta)/theta and (1-cos(theta))/theta^2 through O(theta^6).
        a = (
            1.0
            - theta_squared / 6.0
            + theta_squared**2 / 120.0
            - theta_squared**3 / 5040.0
        )
        b = (
            0.5
            - theta_squared / 24.0
            + theta_squared**2 / 720.0
            - theta_squared**3 / 40320.0
        )
    else:
        a = float(np.sin(theta) / theta)
        b = float((1.0 - np.cos(theta)) / theta_squared)

    return np.eye(3) + a * omega + b * (omega @ omega)


def update_rotation(
    current_rotation: ArrayLike,
    increment: ArrayLike,
    *,
    increment_type: str = "spatial",
) -> FloatArray:
    """Update a rotation by left-spatial or right-material multiplication."""

    current = np.asarray(current_rotation, dtype=float)
    if current.shape != (3, 3):
        raise ValueError(
            f"current_rotation must have shape (3, 3), got {current.shape}"
        )
    delta = so3_exp(increment)
    if increment_type == "spatial":
        return delta @ current
    if increment_type == "material":
        return current @ delta
    raise ValueError("increment_type must be 'spatial' or 'material'")


@dataclass(frozen=True)
class RotationMetrics:
    orthogonality_error: float
    determinant: float


def rotation_metrics(rotation: ArrayLike) -> RotationMetrics:
    matrix = np.asarray(rotation, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"rotation must have shape (3, 3), got {matrix.shape}")
    return RotationMetrics(
        orthogonality_error=float(np.linalg.norm(matrix.T @ matrix - np.eye(3))),
        determinant=float(np.linalg.det(matrix)),
    )


def axis_angle_rotation(axis: ArrayLike, angle: float) -> FloatArray:
    axis_vector = _vector3(axis, name="axis")
    norm = float(np.linalg.norm(axis_vector))
    if norm <= 0.0:
        raise ValueError("axis must have nonzero length")
    return so3_exp(axis_vector * (float(angle) / norm))
