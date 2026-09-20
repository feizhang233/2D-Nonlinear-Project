"""Homogeneous isotropic shell constitutive blocks for the P04 baseline.

The sign chain follows P0 contract 1.0.0:
``epsilon_p(z) = epsilon_m - z * kappa`` and ``M = D_b * kappa``.
All inputs and outputs use the frozen SI units.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from reused_cores.shell3d_linear.types import Mat3, Vec2, Vec3

Mat2 = tuple[Vec2, Vec2]


@dataclass(frozen=True, slots=True)
class ConstitutiveBlocks:
    """Thickness-integrated blocks for a symmetric, constant-thickness shell.

    ``d_p`` is in Pa, ``d_m`` and ``d_s`` are in N/m, and ``d_b`` is in N*m.
    """

    young_modulus: float
    poisson_ratio: float
    thickness: float
    shear_correction_factor: float
    shear_modulus: float
    d_p: Mat3
    d_m: Mat3
    d_b: Mat3
    d_s: Mat2


@dataclass(frozen=True, slots=True)
class GeneralizedResultants:
    membrane: Vec3
    bending: Vec3
    shear: Vec2


@dataclass(frozen=True, slots=True)
class SurfaceStresses:
    top: Vec3
    bottom: Vec3


@dataclass(frozen=True, slots=True)
class GeneralizedEnergyDensity:
    """Strain-energy components per unit middle-surface area, in J/m^2."""

    membrane: float
    bending: float
    shear: float
    total: float


def _finite_float(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite float")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite float") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite float")
    return number


def _vector(name: str, values: Sequence[float], size: int) -> tuple[float, ...]:
    if len(values) != size:
        raise ValueError(f"{name} must contain {size} components")
    return tuple(_finite_float(f"{name}[{index}]", value) for index, value in enumerate(values))


def _scale3(matrix: Mat3, factor: float) -> Mat3:
    return tuple(tuple(factor * matrix[row][column] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def _mat3_vec(matrix: Mat3, vector: Sequence[float]) -> Vec3:
    values = _vector("vector", vector, 3)
    return tuple(
        sum(matrix[row][column] * values[column] for column in range(3)) for row in range(3)
    )  # type: ignore[return-value]


def _mat2_vec(matrix: Mat2, vector: Sequence[float]) -> Vec2:
    values = _vector("vector", vector, 2)
    return tuple(
        sum(matrix[row][column] * values[column] for column in range(2)) for row in range(2)
    )  # type: ignore[return-value]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("dot-product vectors must have the same length")
    return sum(left[index] * right[index] for index in range(len(left)))


def build_isotropic_constitutive(
    young_modulus: float,
    poisson_ratio: float,
    thickness: float,
    shear_correction_factor: float,
) -> ConstitutiveBlocks:
    """Build ``D_p``, ``D_m``, ``D_b`` and ``D_s`` for the P0 material scope."""

    e = _finite_float("young_modulus", young_modulus)
    nu = _finite_float("poisson_ratio", poisson_ratio)
    t = _finite_float("thickness", thickness)
    k_s = _finite_float("shear_correction_factor", shear_correction_factor)
    if e <= 0.0:
        raise ValueError("young_modulus must be greater than zero")
    if not -1.0 < nu < 0.5:
        raise ValueError("poisson_ratio must satisfy -1 < nu < 0.5")
    if t <= 0.0:
        raise ValueError("thickness must be greater than zero")
    if k_s <= 0.0:
        raise ValueError("shear_correction_factor must be greater than zero")

    shear_modulus = e / (2.0 * (1.0 + nu))
    factor = e / (1.0 - nu * nu)
    d_p: Mat3 = (
        (factor, factor * nu, 0.0),
        (factor * nu, factor, 0.0),
        (0.0, 0.0, shear_modulus),
    )
    d_m = _scale3(d_p, t)
    d_b = _scale3(d_p, t**3 / 12.0)
    shear_scale = k_s * shear_modulus * t
    d_s: Mat2 = ((shear_scale, 0.0), (0.0, shear_scale))
    return ConstitutiveBlocks(
        young_modulus=e,
        poisson_ratio=nu,
        thickness=t,
        shear_correction_factor=k_s,
        shear_modulus=shear_modulus,
        d_p=d_p,
        d_m=d_m,
        d_b=d_b,
        d_s=d_s,
    )


def membrane_resultant(blocks: ConstitutiveBlocks, membrane_strain: Sequence[float]) -> Vec3:
    return _mat3_vec(blocks.d_m, membrane_strain)


def bending_resultant(blocks: ConstitutiveBlocks, curvature: Sequence[float]) -> Vec3:
    return _mat3_vec(blocks.d_b, curvature)


def shear_resultant(blocks: ConstitutiveBlocks, shear_strain: Sequence[float]) -> Vec2:
    return _mat2_vec(blocks.d_s, shear_strain)


def generalized_resultants(
    blocks: ConstitutiveBlocks,
    membrane_strain: Sequence[float],
    curvature: Sequence[float],
    shear_strain: Sequence[float],
) -> GeneralizedResultants:
    return GeneralizedResultants(
        membrane=membrane_resultant(blocks, membrane_strain),
        bending=bending_resultant(blocks, curvature),
        shear=shear_resultant(blocks, shear_strain),
    )


def in_plane_stress(
    blocks: ConstitutiveBlocks,
    membrane_strain: Sequence[float],
    curvature: Sequence[float],
    z: float,
) -> Vec3:
    """Return ``sigma_p(z) = D_p * (epsilon_m - z * kappa)`` in Pa."""

    membrane = _vector("membrane_strain", membrane_strain, 3)
    bending = _vector("curvature", curvature, 3)
    z_value = _finite_float("z", z)
    strain = tuple(membrane[index] - z_value * bending[index] for index in range(3))
    return _mat3_vec(blocks.d_p, strain)


def surface_stresses(
    blocks: ConstitutiveBlocks,
    membrane_strain: Sequence[float],
    curvature: Sequence[float],
) -> SurfaceStresses:
    half_thickness = 0.5 * blocks.thickness
    return SurfaceStresses(
        top=in_plane_stress(blocks, membrane_strain, curvature, half_thickness),
        bottom=in_plane_stress(blocks, membrane_strain, curvature, -half_thickness),
    )


def generalized_energy_density(
    blocks: ConstitutiveBlocks,
    membrane_strain: Sequence[float],
    curvature: Sequence[float],
    shear_strain: Sequence[float],
) -> GeneralizedEnergyDensity:
    membrane = _vector("membrane_strain", membrane_strain, 3)
    bending = _vector("curvature", curvature, 3)
    shear = _vector("shear_strain", shear_strain, 2)
    resultants = generalized_resultants(blocks, membrane, bending, shear)
    membrane_energy = 0.5 * _dot(membrane, resultants.membrane)
    bending_energy = 0.5 * _dot(bending, resultants.bending)
    shear_energy = 0.5 * _dot(shear, resultants.shear)
    return GeneralizedEnergyDensity(
        membrane=membrane_energy,
        bending=bending_energy,
        shear=shear_energy,
        total=membrane_energy + bending_energy + shear_energy,
    )


__all__ = [
    "ConstitutiveBlocks",
    "GeneralizedEnergyDensity",
    "GeneralizedResultants",
    "SurfaceStresses",
    "bending_resultant",
    "build_isotropic_constitutive",
    "generalized_energy_density",
    "generalized_resultants",
    "in_plane_stress",
    "membrane_resultant",
    "shear_resultant",
    "surface_stresses",
]
