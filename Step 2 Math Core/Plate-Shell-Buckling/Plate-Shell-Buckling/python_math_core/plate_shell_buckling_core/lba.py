"""Dense reference routines for ideal linear buckling analysis (LBA)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a finite positive value")
    return value


def _poisson(nu: float) -> float:
    nu = float(nu)
    if not math.isfinite(nu) or not (-1.0 < nu < 0.5):
        raise ValueError("Poisson ratio must satisfy -1 < nu < 0.5")
    return nu


def _square_symmetric(name: str, matrix: ArrayLike, *, atol: float = 1e-11) -> FloatArray:
    result = np.asarray(matrix, dtype=float)
    if result.ndim != 2 or result.shape[0] != result.shape[1]:
        raise ValueError(f"{name} must be a square matrix")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} contains non-finite values")
    if not np.allclose(result, result.T, atol=atol, rtol=atol):
        raise ValueError(f"{name} must be symmetric for this conservative reference solver")
    return result


@dataclass(frozen=True)
class PrebucklingResult:
    displacement: FloatArray
    reactions: FloatArray
    residual: FloatArray
    free_dofs: tuple[int, ...]
    constrained_dofs: tuple[int, ...]

    @property
    def free_residual_norm(self) -> float:
        if not self.free_dofs:
            return 0.0
        return float(np.linalg.norm(self.residual[list(self.free_dofs)]))


@dataclass(frozen=True)
class Eigenpair:
    value: float
    vector: FloatArray
    normalized_residual: float
    geometric_energy: float

    @property
    def is_compressive_candidate(self) -> bool:
        return self.value > 0.0 and self.geometric_energy > 0.0


@dataclass(frozen=True)
class UniaxialPlateResult:
    flexural_rigidity_n_mm: float
    critical_membrane_force_n_per_mm: float
    critical_stress_mpa: float
    total_edge_load_kn: float
    mode_m: int
    mode_n: int
    axial_halfwave_mm: float
    buckling_coefficient: float


@dataclass(frozen=True)
class BiaxialPlateResult:
    flexural_rigidity_n_mm: float
    critical_nx_n_per_mm: float
    critical_ny_n_per_mm: float
    critical_nx_stress_mpa: float
    mode_m: int
    mode_n: int


@dataclass(frozen=True)
class ShearPlateResult:
    truncation_m: int
    mode_count: int
    buckling_coefficient: float
    critical_shear_membrane_force_n_per_mm: float
    eigen_residual: float
    normalized_mode: FloatArray


@dataclass(frozen=True)
class CylinderBucklingResult:
    flexural_rigidity_n_mm: float
    critical_stress_mpa: float
    critical_membrane_force_n_per_mm: float
    total_axial_load_kn: float
    axisymmetric_wavenumber_per_mm: float
    axisymmetric_wavelength_mm: float
    continuous_axial_halfwaves: float
    nearest_axial_halfwaves: int


@dataclass(frozen=True)
class SphereBucklingResult:
    flexural_rigidity_n_mm: float
    critical_external_pressure_mpa: float
    critical_membrane_force_n_per_mm: float


@dataclass(frozen=True)
class DirectionalTangentPoint:
    epsilon: float
    absolute_error: float
    relative_error: float


def flexural_rigidity(young_mpa: float, thickness_mm: float, poisson: float) -> float:
    """Return isotropic thin-plate rigidity D in N mm."""

    young_mpa = _positive("young_mpa", young_mpa)
    thickness_mm = _positive("thickness_mm", thickness_mm)
    poisson = _poisson(poisson)
    return young_mpa * thickness_mm**3 / (12.0 * (1.0 - poisson**2))


def solve_linear_prebuckling(
    material_stiffness: ArrayLike,
    reference_load: ArrayLike,
    *,
    load_factor: float = 1.0,
    constraints: Mapping[int, float] | None = None,
) -> PrebucklingResult:
    """Solve a constrained linear prebuckling equilibrium state.

    The returned residual is ``K_M q - lambda_ref f_ref``.  Its constrained
    entries are reactions and its free entries must be approximately zero.
    """

    stiffness = _square_symmetric("material_stiffness", material_stiffness)
    load = np.asarray(reference_load, dtype=float).reshape(-1)
    if load.size != stiffness.shape[0]:
        raise ValueError("reference_load size must match the stiffness matrix")
    if not np.all(np.isfinite(load)) or not math.isfinite(load_factor):
        raise ValueError("load data must be finite")
    constraints = dict(constraints or {})
    size = load.size
    for dof, value in constraints.items():
        if dof < 0 or dof >= size or not math.isfinite(value):
            raise ValueError("constraint DOF/value is invalid")

    constrained = tuple(sorted(constraints))
    constrained_set = set(constrained)
    free = tuple(index for index in range(size) if index not in constrained_set)
    displacement = np.zeros(size, dtype=float)
    for dof, value in constraints.items():
        displacement[dof] = value

    if free:
        k_ff = stiffness[np.ix_(free, free)]
        right = load_factor * load[list(free)]
        if constrained:
            right = right - stiffness[np.ix_(free, constrained)] @ displacement[list(constrained)]
        displacement[list(free)] = np.linalg.solve(k_ff, right)

    residual = stiffness @ displacement - load_factor * load
    reactions = np.zeros_like(residual)
    if constrained:
        reactions[list(constrained)] = residual[list(constrained)]
    return PrebucklingResult(displacement, reactions, residual, free, constrained)


def integrate_plate_geometric_stiffness(
    slope_operators: ArrayLike,
    membrane_forces: ArrayLike,
    weights: ArrayLike,
    *,
    compression_positive: bool = True,
) -> FloatArray:
    """Integrate ``K_G = integral(B_g.T N B_g dA)`` for a thin plate.

    ``slope_operators`` has shape ``(n_point, 2, n_dof)``.  Membrane force may
    be one 2x2 matrix or one matrix per point.  With compression-positive input
    the result is the positive weakening matrix used in ``K_M phi=lambda K_G phi``.
    """

    bg = np.asarray(slope_operators, dtype=float)
    if bg.ndim != 3 or bg.shape[1] != 2:
        raise ValueError("slope_operators must have shape (n_point, 2, n_dof)")
    weight = np.asarray(weights, dtype=float).reshape(-1)
    if weight.size != bg.shape[0] or np.any(weight <= 0.0):
        raise ValueError("weights must be positive and match the integration points")
    forces = np.asarray(membrane_forces, dtype=float)
    if forces.shape == (2, 2):
        forces = np.repeat(forces[None, :, :], bg.shape[0], axis=0)
    if forces.shape != (bg.shape[0], 2, 2):
        raise ValueError("membrane_forces must be (2,2) or (n_point,2,2)")
    if not np.allclose(forces, np.swapaxes(forces, 1, 2), atol=1e-12, rtol=1e-12):
        raise ValueError("membrane force tensors must be symmetric")
    sign = 1.0 if compression_positive else -1.0
    result = np.zeros((bg.shape[2], bg.shape[2]), dtype=float)
    for operator, force, point_weight in zip(bg, forces, weight, strict=True):
        result += sign * point_weight * (operator.T @ force @ operator)
    return 0.5 * (result + result.T)


def recover_membrane_forces(
    displacement: ArrayLike,
    recovery_operators: ArrayLike,
) -> FloatArray:
    """Recover compression-positive ``[N_x, N_y, N_xy]`` at integration points.

    ``recovery_operators`` has shape ``(n_point, 3, n_dof)``.  This reference
    operation keeps the dependency on the equilibrated prebuckling displacement
    explicit instead of injecting an unrelated nominal stress field.
    """

    q = np.asarray(displacement, dtype=float).reshape(-1)
    operators = np.asarray(recovery_operators, dtype=float)
    if operators.ndim != 3 or operators.shape[1] != 3 or operators.shape[2] != q.size:
        raise ValueError("recovery_operators must have shape (n_point, 3, n_dof)")
    if not np.all(np.isfinite(q)) or not np.all(np.isfinite(operators)):
        raise ValueError("displacement and recovery operators must be finite")
    components = np.einsum("pij,j->pi", operators, q)
    tensors = np.zeros((operators.shape[0], 2, 2), dtype=float)
    tensors[:, 0, 0] = components[:, 0]
    tensors[:, 1, 1] = components[:, 1]
    tensors[:, 0, 1] = components[:, 2]
    tensors[:, 1, 0] = components[:, 2]
    return tensors


def directional_tangent_error(
    internal_force: Callable[[FloatArray], ArrayLike],
    tangent: ArrayLike,
    state: ArrayLike,
    direction: ArrayLike,
    *,
    epsilon: float = 1e-7,
) -> tuple[float, float]:
    """Return absolute and normalized forward-difference tangent errors."""

    epsilon = _positive("epsilon", epsilon)
    q = np.asarray(state, dtype=float).reshape(-1)
    vector = np.asarray(direction, dtype=float).reshape(-1)
    matrix = np.asarray(tangent, dtype=float)
    if q.size != vector.size or matrix.shape != (q.size, q.size):
        raise ValueError("state, direction and tangent dimensions must agree")
    finite_difference = (
        np.asarray(internal_force(q + epsilon * vector), dtype=float).reshape(-1)
        - np.asarray(internal_force(q), dtype=float).reshape(-1)
    ) / epsilon
    exact = matrix @ vector
    absolute = float(np.linalg.norm(finite_difference - exact))
    scale = max(float(np.linalg.norm(finite_difference)), float(np.linalg.norm(exact)), 1.0)
    return absolute, absolute / scale


def directional_tangent_curve(
    internal_force: Callable[[FloatArray], ArrayLike],
    tangent: ArrayLike,
    state: ArrayLike,
    direction: ArrayLike,
    *,
    epsilons: ArrayLike,
) -> list[DirectionalTangentPoint]:
    """Evaluate a forward directional-difference curve over several step sizes."""

    values = np.asarray(epsilons, dtype=float).reshape(-1)
    if values.size < 3 or np.any(~np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("epsilons must contain at least three finite positive values")
    if np.any(np.diff(values) >= 0.0):
        raise ValueError("epsilons must be strictly decreasing")
    curve: list[DirectionalTangentPoint] = []
    for epsilon in values:
        absolute, relative = directional_tangent_error(
            internal_force,
            tangent,
            state,
            direction,
            epsilon=float(epsilon),
        )
        curve.append(DirectionalTangentPoint(float(epsilon), absolute, relative))
    return curve


def solve_generalized_buckling(
    material_stiffness: ArrayLike,
    geometric_weakening: ArrayLike,
    *,
    spectral_tolerance: float = 1e-12,
) -> list[Eigenpair]:
    """Solve ``K_M phi = lambda K_G phi`` without taking absolute values.

    ``K_M`` must be symmetric positive definite in the already constrained free
    subspace. ``K_G`` may be indefinite. Cholesky whitening converts the pencil
    to a symmetric standard eigenproblem and retains positive and negative load
    directions separately.
    """

    k_m = _square_symmetric("material_stiffness", material_stiffness)
    k_g = _square_symmetric("geometric_weakening", geometric_weakening)
    if k_m.shape != k_g.shape:
        raise ValueError("K_M and K_G must have the same shape")
    spectral_tolerance = _positive("spectral_tolerance", spectral_tolerance)
    try:
        lower = np.linalg.cholesky(k_m)
    except np.linalg.LinAlgError as exc:
        raise ValueError("K_M must be positive definite after applying constraints") from exc

    left_whitened = np.linalg.solve(lower, k_g)
    whitened = np.linalg.solve(lower, left_whitened.T).T
    whitened = 0.5 * (whitened + whitened.T)
    mu_values, y_vectors = np.linalg.eigh(whitened)
    pairs: list[Eigenpair] = []
    for mu, y_vector in zip(mu_values, y_vectors.T, strict=True):
        if abs(mu) <= spectral_tolerance:
            continue
        value = float(1.0 / mu)
        vector = np.linalg.solve(lower.T, y_vector)
        vector /= np.linalg.norm(vector)
        material_action = k_m @ vector
        geometric_action = k_g @ vector
        residual = material_action - value * geometric_action
        denominator = np.linalg.norm(material_action) + abs(value) * np.linalg.norm(geometric_action)
        normalized_residual = float(np.linalg.norm(residual) / max(float(denominator), 1e-30))
        geometric_energy = float(vector @ k_g @ vector)
        pairs.append(Eigenpair(value, vector, normalized_residual, geometric_energy))
    pairs.sort(key=lambda pair: (pair.value <= 0.0, pair.value if pair.value > 0.0 else -pair.value))
    return pairs


def uniaxial_rectangular_plate(
    *,
    a_mm: float,
    b_mm: float,
    thickness_mm: float,
    young_mpa: float,
    poisson: float,
    max_m: int = 20,
    max_n: int = 6,
) -> UniaxialPlateResult:
    """Lowest Navier mode of a simply supported plate under x compression."""

    a_mm = _positive("a_mm", a_mm)
    b_mm = _positive("b_mm", b_mm)
    thickness_mm = _positive("thickness_mm", thickness_mm)
    if max_m < 1 or max_n < 1:
        raise ValueError("mode limits must be positive integers")
    rigidity = flexural_rigidity(young_mpa, thickness_mm, poisson)
    candidates: list[tuple[float, int, int]] = []
    for m in range(1, max_m + 1):
        alpha = m * math.pi / a_mm
        for n in range(1, max_n + 1):
            beta = n * math.pi / b_mm
            membrane_force = rigidity * (alpha**2 + beta**2) ** 2 / alpha**2
            candidates.append((membrane_force, m, n))
    critical, mode_m, mode_n = min(candidates)
    coefficient = critical * b_mm**2 / (math.pi**2 * rigidity)
    return UniaxialPlateResult(
        rigidity,
        critical,
        critical / thickness_mm,
        critical * b_mm / 1000.0,
        mode_m,
        mode_n,
        a_mm / mode_m,
        coefficient,
    )


def biaxial_rectangular_plate(
    *,
    a_mm: float,
    b_mm: float,
    thickness_mm: float,
    young_mpa: float,
    poisson: float,
    ny_over_nx: float,
    max_m: int = 12,
    max_n: int = 12,
) -> BiaxialPlateResult:
    """Lowest mode on the proportional path ``N_y = rho N_x``."""

    a_mm = _positive("a_mm", a_mm)
    b_mm = _positive("b_mm", b_mm)
    thickness_mm = _positive("thickness_mm", thickness_mm)
    if ny_over_nx < 0.0 or not math.isfinite(ny_over_nx):
        raise ValueError("ny_over_nx must be finite and non-negative")
    if max_m < 1 or max_n < 1:
        raise ValueError("mode limits must be positive integers")
    rigidity = flexural_rigidity(young_mpa, thickness_mm, poisson)
    candidates: list[tuple[float, int, int]] = []
    for m in range(1, max_m + 1):
        alpha = m * math.pi / a_mm
        for n in range(1, max_n + 1):
            beta = n * math.pi / b_mm
            denominator = alpha**2 + ny_over_nx * beta**2
            nx = rigidity * (alpha**2 + beta**2) ** 2 / denominator
            candidates.append((nx, m, n))
    nx, mode_m, mode_n = min(candidates)
    return BiaxialPlateResult(
        rigidity,
        nx,
        ny_over_nx * nx,
        nx / thickness_mm,
        mode_m,
        mode_n,
    )


def pure_shear_square_plate(
    *,
    truncation_m: int,
    side_mm: float = 1.0,
    rigidity_n_mm: float = 1.0,
) -> ShearPlateResult:
    """Galerkin/Navier solution for a simply supported square under pure shear.

    All modes ``1 <= m,n <= truncation_m`` are retained.  Shear couples only
    pairs for which both wave-number parities differ.  A one-mode truncation is
    singular by physics and is rejected instead of returning a false zero load.
    """

    if truncation_m < 2:
        raise ValueError("pure shear needs a coupled space; truncation_m must be at least 2")
    side_mm = _positive("side_mm", side_mm)
    rigidity_n_mm = _positive("rigidity_n_mm", rigidity_n_mm)
    modes = [(m, n) for m in range(1, truncation_m + 1) for n in range(1, truncation_m + 1)]
    diagonal = np.array(
        [rigidity_n_mm * math.pi**4 * (m * m + n * n) ** 2 / (4.0 * side_mm**2) for m, n in modes]
    )
    shear = np.zeros((len(modes), len(modes)), dtype=float)
    for row, (m, n) in enumerate(modes):
        for column, (p, q) in enumerate(modes):
            if (m + p) % 2 == 1 and (n + q) % 2 == 1:
                shear[row, column] = 8.0 * m * n * p * q / ((p * p - m * m) * (n * n - q * q))
    inverse_sqrt = 1.0 / np.sqrt(diagonal)
    whitened = inverse_sqrt[:, None] * shear * inverse_sqrt[None, :]
    mu_values, vectors = np.linalg.eigh(0.5 * (whitened + whitened.T))
    positive_indices = np.flatnonzero(mu_values > 1e-13)
    if positive_indices.size == 0:
        raise ValueError("the truncated space contains no positive shear-buckling direction")
    index = int(positive_indices[-1])
    critical_shear = float(1.0 / mu_values[index])
    mode = inverse_sqrt * vectors[:, index]
    mode /= np.max(np.abs(mode))
    residual_vector = diagonal * mode - critical_shear * (shear @ mode)
    scale = np.linalg.norm(diagonal * mode) + critical_shear * np.linalg.norm(shear @ mode)
    residual = float(np.linalg.norm(residual_vector) / scale)
    coefficient = critical_shear * side_mm**2 / (math.pi**2 * rigidity_n_mm)
    return ShearPlateResult(truncation_m, len(modes), coefficient, critical_shear, residual, mode)


def cylindrical_shell_mode_load(
    *,
    radius_mm: float,
    length_mm: float,
    thickness_mm: float,
    young_mpa: float,
    poisson: float,
    axial_halfwaves: int,
    circumferential_waves: int,
) -> float:
    """Donnell membrane force N(alpha,beta) for one discrete cylinder mode."""

    radius_mm = _positive("radius_mm", radius_mm)
    length_mm = _positive("length_mm", length_mm)
    thickness_mm = _positive("thickness_mm", thickness_mm)
    if axial_halfwaves < 1 or circumferential_waves < 0:
        raise ValueError("invalid cylinder wave numbers")
    rigidity = flexural_rigidity(young_mpa, thickness_mm, poisson)
    alpha = axial_halfwaves * math.pi / length_mm
    beta = circumferential_waves / radius_mm
    q_squared = alpha**2 + beta**2
    return (
        rigidity * q_squared**2 / alpha**2
        + young_mpa * thickness_mm * alpha**2 / (radius_mm**2 * q_squared**2)
    )


def cylindrical_shell_classical(
    *,
    radius_mm: float,
    length_mm: float,
    thickness_mm: float,
    young_mpa: float,
    poisson: float,
) -> CylinderBucklingResult:
    """Classical ideal axial-compression result for a thin cylinder."""

    radius_mm = _positive("radius_mm", radius_mm)
    length_mm = _positive("length_mm", length_mm)
    thickness_mm = _positive("thickness_mm", thickness_mm)
    young_mpa = _positive("young_mpa", young_mpa)
    poisson = _poisson(poisson)
    rigidity = flexural_rigidity(young_mpa, thickness_mm, poisson)
    denominator = math.sqrt(3.0 * (1.0 - poisson**2))
    stress = young_mpa * (thickness_mm / radius_mm) / denominator
    membrane_force = stress * thickness_mm
    total_load = 2.0 * math.pi * radius_mm * membrane_force / 1000.0
    alpha = (12.0 * (1.0 - poisson**2)) ** 0.25 / math.sqrt(radius_mm * thickness_mm)
    wavelength = 2.0 * math.pi / alpha
    continuous_m = alpha * length_mm / math.pi
    nearest_m = max(1, int(math.floor(continuous_m + 0.5)))
    return CylinderBucklingResult(
        rigidity,
        stress,
        membrane_force,
        total_load,
        alpha,
        wavelength,
        continuous_m,
        nearest_m,
    )


def spherical_shell_external_pressure(
    *,
    radius_mm: float,
    thickness_mm: float,
    young_mpa: float,
    poisson: float,
) -> SphereBucklingResult:
    """Classical ideal external pressure of a complete thin spherical shell."""

    radius_mm = _positive("radius_mm", radius_mm)
    thickness_mm = _positive("thickness_mm", thickness_mm)
    young_mpa = _positive("young_mpa", young_mpa)
    poisson = _poisson(poisson)
    rigidity = flexural_rigidity(young_mpa, thickness_mm, poisson)
    pressure = 2.0 * young_mpa * (thickness_mm / radius_mm) ** 2 / math.sqrt(
        3.0 * (1.0 - poisson**2)
    )
    membrane_force = pressure * radius_mm / 2.0
    return SphereBucklingResult(rigidity, pressure, membrane_force)
