"""V08-V09 的经典理想壳体解析基准。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CylinderBucklingResult:
    critical_stress_mpa: float
    critical_membrane_force_n_per_mm: float
    total_critical_load_kn: float
    alpha_per_mm: float
    full_wavelength_mm: float
    half_wave_count: float


@dataclass(frozen=True)
class SphereBucklingResult:
    critical_pressure_mpa: float
    critical_membrane_force_n_per_mm: float


def _validate_shell_inputs(
    elastic_modulus_mpa: float,
    poisson_ratio: float,
    radius_mm: float,
    thickness_mm: float,
) -> None:
    if elastic_modulus_mpa <= 0.0 or radius_mm <= 0.0 or thickness_mm <= 0.0:
        raise ValueError("E、R、h 必须为正")
    if not -1.0 < poisson_ratio < 0.5:
        raise ValueError("各向同性弹性泊松比必须满足 -1 < nu < 0.5")


def cylinder_axial_buckling(
    elastic_modulus_mpa: float,
    poisson_ratio: float,
    radius_mm: float,
    thickness_mm: float,
    length_mm: float,
) -> CylinderBucklingResult:
    """轴压完整圆柱壳的经典理想短波基准。"""

    _validate_shell_inputs(
        elastic_modulus_mpa, poisson_ratio, radius_mm, thickness_mm
    )
    if length_mm <= 0.0:
        raise ValueError("L 必须为正")
    denominator = np.sqrt(3.0 * (1.0 - poisson_ratio**2))
    stress = elastic_modulus_mpa * (thickness_mm / radius_mm) / denominator
    membrane_force = stress * thickness_mm
    total_load_kn = 2.0 * np.pi * radius_mm * membrane_force / 1000.0
    alpha = (
        (12.0 * (1.0 - poisson_ratio**2)) ** 0.25
        / np.sqrt(radius_mm * thickness_mm)
    )
    return CylinderBucklingResult(
        critical_stress_mpa=float(stress),
        critical_membrane_force_n_per_mm=float(membrane_force),
        total_critical_load_kn=float(total_load_kn),
        alpha_per_mm=float(alpha),
        full_wavelength_mm=float(2.0 * np.pi / alpha),
        half_wave_count=float(alpha * length_mm / np.pi),
    )


def sphere_external_pressure(
    elastic_modulus_mpa: float,
    poisson_ratio: float,
    radius_mm: float,
    thickness_mm: float,
) -> SphereBucklingResult:
    """完整球壳均匀外压的经典理想基准。"""

    _validate_shell_inputs(
        elastic_modulus_mpa, poisson_ratio, radius_mm, thickness_mm
    )
    denominator = np.sqrt(3.0 * (1.0 - poisson_ratio**2))
    pressure = (
        2.0
        * elastic_modulus_mpa
        * (thickness_mm / radius_mm) ** 2
        / denominator
    )
    membrane_force = pressure * radius_mm / 2.0
    return SphereBucklingResult(
        critical_pressure_mpa=float(pressure),
        critical_membrane_force_n_per_mm=float(membrane_force),
    )

