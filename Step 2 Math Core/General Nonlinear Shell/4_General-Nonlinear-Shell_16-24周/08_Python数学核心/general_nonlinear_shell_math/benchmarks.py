"""Closed-form benchmark values used to check future shell implementations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PureBendingStripResult:
    curvature: float
    end_rotation: float
    end_x: float
    end_y: float
    strain_energy: float


def pure_bending_strip(
    *, length: float, bending_stiffness: float
) -> PureBendingStripResult:
    length_value = float(length)
    stiffness_value = float(bending_stiffness)
    if not np.isfinite(length_value) or length_value <= 0.0:
        raise ValueError("length must be finite and positive")
    if not np.isfinite(stiffness_value) or stiffness_value <= 0.0:
        raise ValueError("bending_stiffness must be finite and positive")
    curvature = float(np.pi / length_value)
    return PureBendingStripResult(
        curvature=curvature,
        end_rotation=float(np.pi),
        end_x=0.0,
        end_y=float(2.0 * length_value / np.pi),
        strain_energy=float(np.pi**2 * stiffness_value / (2.0 * length_value)),
    )
