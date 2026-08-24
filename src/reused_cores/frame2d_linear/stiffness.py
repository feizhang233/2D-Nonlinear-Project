"""Linear ``frame2d`` Euler-Bernoulli local stiffness matrix."""

from __future__ import annotations

from numbers import Real

import numpy as np
from numpy.typing import NDArray

from reused_cores.frame2d_linear.models import FrameElement


def calculate_local_stiffness(
    element: FrameElement,
    length: float,
) -> NDArray[np.float64]:
    """Return the 6x6 local stiffness in ``[u_i,v_i,phi_i,u_j,v_j,phi_j]`` order."""

    if isinstance(length, (bool, np.bool_)) or not isinstance(length, Real):
        raise TypeError("length must be a real number")
    if not np.isfinite(length):
        raise ValueError("length must be finite")
    if length <= 0.0:
        raise ValueError("length must be greater than zero")
    E = float(element.E)
    A = float(element.A)
    inertia = float(element.I)
    L = float(length)
    axial = E * A / L
    bending_12 = 12.0 * E * inertia / L**3
    bending_6 = 6.0 * E * inertia / L**2
    bending_4 = 4.0 * E * inertia / L
    bending_2 = 2.0 * E * inertia / L
    return np.array(
        [
            [axial, 0.0, 0.0, -axial, 0.0, 0.0],
            [0.0, bending_12, bending_6, 0.0, -bending_12, bending_6],
            [0.0, bending_6, bending_4, 0.0, -bending_6, bending_2],
            [-axial, 0.0, 0.0, axial, 0.0, 0.0],
            [0.0, -bending_12, -bending_6, 0.0, bending_12, -bending_6],
            [0.0, bending_6, bending_2, 0.0, -bending_6, bending_4],
        ],
        dtype=float,
    )
