"""Linear ``frame2d`` global-to-local transformation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from reused_cores.frame2d_linear.geometry import ElementGeometry


def calculate_transformation(geometry: ElementGeometry) -> NDArray[np.float64]:
    """Return ``d_local = T @ d_global`` for ``[u, v, phi]`` node order."""

    c = float(geometry.c)
    s = float(geometry.s)
    if not (np.isfinite(c) and np.isfinite(s)):
        raise ValueError("direction cosines must be finite")
    if not np.isclose(c * c + s * s, 1.0, rtol=1.0e-12, atol=1.0e-12):
        raise ValueError("direction cosines must satisfy c^2 + s^2 = 1")
    return np.array(
        [
            [c, s, 0.0, 0.0, 0.0, 0.0],
            [-s, c, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, c, s, 0.0],
            [0.0, 0.0, 0.0, -s, c, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
