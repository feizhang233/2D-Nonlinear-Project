"""Through-thickness integration and plane-stress tangent condensation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ElasticBendingResult:
    surface_stress_bottom: float
    surface_stress_top: float
    membrane_force: float
    bending_moment: float
    strain_energy_per_area: float
    thickness_coordinates: FloatArray
    stresses: FloatArray


def integrate_linear_elastic_bending(
    *,
    elastic_modulus: float,
    thickness: float,
    curvature: float,
    gauss_points: int = 2,
) -> ElasticBendingResult:
    """Integrate ``sigma=E*z*kappa`` over a unit-width shell section."""

    modulus = float(elastic_modulus)
    h = float(thickness)
    kappa = float(curvature)
    if not np.isfinite(modulus) or modulus <= 0.0:
        raise ValueError("elastic_modulus must be finite and positive")
    if not np.isfinite(h) or h <= 0.0:
        raise ValueError("thickness must be finite and positive")
    if not np.isfinite(kappa):
        raise ValueError("curvature must be finite")
    if gauss_points < 1:
        raise ValueError("gauss_points must be at least one")

    natural_points, natural_weights = np.polynomial.legendre.leggauss(gauss_points)
    z = 0.5 * h * natural_points
    weights = 0.5 * h * natural_weights
    stress = modulus * z * kappa
    membrane = float(np.sum(weights * stress))
    moment = float(np.sum(weights * z * stress))
    energy = float(np.sum(weights * 0.5 * stress * (z * kappa)))
    return ElasticBendingResult(
        surface_stress_bottom=-0.5 * modulus * h * kappa,
        surface_stress_top=0.5 * modulus * h * kappa,
        membrane_force=membrane,
        bending_moment=moment,
        strain_energy_per_area=energy,
        thickness_coordinates=z,
        stresses=stress,
    )


def condense_plane_stress(
    active_active: ArrayLike,
    active_thickness: ArrayLike,
    thickness_active: ArrayLike,
    thickness_thickness: ArrayLike,
) -> FloatArray:
    """Apply the Schur complement after satisfying the local plane-stress equation."""

    c_aa = np.atleast_2d(np.asarray(active_active, dtype=float))
    c_a3 = np.atleast_2d(np.asarray(active_thickness, dtype=float))
    c_3a = np.atleast_2d(np.asarray(thickness_active, dtype=float))
    c_33 = np.atleast_2d(np.asarray(thickness_thickness, dtype=float))
    if c_aa.shape[0] != c_aa.shape[1]:
        raise ValueError("active_active must be square")
    if c_a3.shape[0] != c_aa.shape[0] or c_3a.shape[1] != c_aa.shape[1]:
        raise ValueError("coupling blocks do not match active block")
    if (
        c_33.shape[0] != c_33.shape[1]
        or c_a3.shape[1] != c_33.shape[0]
        or c_3a.shape[0] != c_33.shape[1]
    ):
        raise ValueError("thickness blocks have incompatible shapes")
    if not all(np.all(np.isfinite(value)) for value in (c_aa, c_a3, c_3a, c_33)):
        raise ValueError("all tangent blocks must contain finite values")
    correction = c_a3 @ np.linalg.solve(c_33, c_3a)
    return c_aa - correction
