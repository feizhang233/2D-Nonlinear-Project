"""Mode normalization, sign-insensitive correlation and repeated-root tools."""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ModeFilterResult:
    accepted: bool
    reasons: tuple[str, ...]
    rigid_fraction: float
    drilling_fraction: float
    relative_material_energy: float
    constraint_leakage: float
    maximum_group_fraction: float
    geometric_energy: float


def _weight_matrix(weight: ArrayLike | None, size: int) -> FloatArray:
    if weight is None:
        return np.eye(size)
    matrix = np.asarray(weight, dtype=float)
    if matrix.shape != (size, size) or not np.allclose(matrix, matrix.T, atol=1e-12, rtol=1e-12):
        raise ValueError("weight must be a symmetric matrix matching the mode size")
    return matrix


def normalize_mode(mode: ArrayLike, *, method: str = "euclidean", weight: ArrayLike | None = None) -> FloatArray:
    """Normalize a mode by Euclidean, weighted, or maximum-absolute norm."""

    vector = np.asarray(mode, dtype=float).reshape(-1)
    if vector.size == 0 or not np.all(np.isfinite(vector)):
        raise ValueError("mode must contain finite values")
    if method == "euclidean":
        scale = float(np.linalg.norm(vector))
    elif method == "weighted":
        matrix = _weight_matrix(weight, vector.size)
        energy = float(vector @ matrix @ vector)
        scale = math.sqrt(energy) if energy > 0.0 else 0.0
    elif method == "max_abs":
        scale = float(np.max(np.abs(vector)))
    else:
        raise ValueError("method must be 'euclidean', 'weighted', or 'max_abs'")
    if scale <= 0.0:
        raise ValueError("zero mode cannot be normalized")
    return vector / scale


def mac(mode_a: ArrayLike, mode_b: ArrayLike, *, weight: ArrayLike | None = None) -> float:
    """Return the modal assurance criterion, invariant to overall sign/scale."""

    a = np.asarray(mode_a, dtype=float).reshape(-1)
    b = np.asarray(mode_b, dtype=float).reshape(-1)
    if a.size != b.size or a.size == 0:
        raise ValueError("modes must have the same non-zero size")
    matrix = _weight_matrix(weight, a.size)
    numerator = abs(float(a @ matrix @ b)) ** 2
    denominator = float(a @ matrix @ a) * float(b @ matrix @ b)
    if denominator <= 0.0:
        raise ValueError("mode norm must be positive")
    return min(1.0, max(0.0, numerator / denominator))


def subspace_principal_angles(
    modes_a: ArrayLike,
    modes_b: ArrayLike,
    *,
    weight: ArrayLike | None = None,
) -> FloatArray:
    """Return principal angles in radians between two mode subspaces."""

    a = np.asarray(modes_a, dtype=float)
    b = np.asarray(modes_b, dtype=float)
    if a.ndim != 2 or b.ndim != 2 or a.shape[0] != b.shape[0] or min(a.shape[1], b.shape[1]) < 1:
        raise ValueError("mode sets must be 2-D with equal row counts and at least one column")
    if weight is not None:
        matrix = _weight_matrix(weight, a.shape[0])
        try:
            transform = np.linalg.cholesky(matrix).T
        except np.linalg.LinAlgError as exc:
            raise ValueError("weight must be positive definite for subspace angles") from exc
        a = transform @ a
        b = transform @ b
    rank_a = int(np.linalg.matrix_rank(a))
    rank_b = int(np.linalg.matrix_rank(b))
    if rank_a != a.shape[1] or rank_b != b.shape[1]:
        raise ValueError("mode sets must have full column rank")
    qa, _ = np.linalg.qr(a, mode="reduced")
    qb, _ = np.linalg.qr(b, mode="reduced")
    singular_values = np.linalg.svd(qa.T @ qb, compute_uv=False)
    return np.arccos(np.clip(singular_values, -1.0, 1.0))


def group_repeated_eigenvalues(values: ArrayLike, *, relative_tolerance: float = 1e-3) -> list[tuple[int, ...]]:
    """Group adjacent sorted eigenvalues into near-repeated clusters."""

    eigenvalues = np.asarray(values, dtype=float).reshape(-1)
    if eigenvalues.size == 0 or np.any(np.diff(eigenvalues) < 0.0):
        raise ValueError("values must be a non-empty sorted sequence")
    if relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be positive")
    groups: list[list[int]] = [[0]]
    for index in range(1, eigenvalues.size):
        previous = eigenvalues[groups[-1][0]]
        scale = max(abs(previous), abs(eigenvalues[index]), 1.0)
        if abs(eigenvalues[index] - previous) <= relative_tolerance * scale:
            groups[-1].append(index)
        else:
            groups.append([index])
    return [tuple(group) for group in groups]


def diagnose_mode(
    mode: ArrayLike,
    *,
    material_stiffness: ArrayLike,
    geometric_weakening: ArrayLike,
    rigid_basis: ArrayLike | None = None,
    drilling_mask: ArrayLike | None = None,
    constrained_mask: ArrayLike | None = None,
    groups: Sequence[ArrayLike] | None = None,
    rigid_fraction_limit: float = 0.90,
    drilling_fraction_limit: float = 0.80,
    zero_energy_limit: float = 1e-10,
    constraint_leakage_limit: float = 1e-8,
    localization_limit: float = 0.90,
) -> ModeFilterResult:
    """Apply executable reference filters to one candidate buckling mode.

    The localization check is deliberately a diagnostic heuristic: callers must
    define physically meaningful element or region groups for their mesh.
    """

    vector = np.asarray(mode, dtype=float).reshape(-1)
    if vector.size == 0 or not np.all(np.isfinite(vector)):
        raise ValueError("mode must be finite and non-empty")
    norm_squared = float(vector @ vector)
    if norm_squared <= 0.0:
        raise ValueError("zero mode cannot be diagnosed")
    k_m = np.asarray(material_stiffness, dtype=float)
    k_g = np.asarray(geometric_weakening, dtype=float)
    if k_m.shape != (vector.size, vector.size) or k_g.shape != k_m.shape:
        raise ValueError("stiffness matrices must match the mode size")
    if not np.allclose(k_m, k_m.T, atol=1e-12, rtol=1e-12):
        raise ValueError("material_stiffness must be symmetric")
    if not np.allclose(k_g, k_g.T, atol=1e-12, rtol=1e-12):
        raise ValueError("geometric_weakening must be symmetric")

    rigid_fraction = 0.0
    if rigid_basis is not None:
        basis = np.asarray(rigid_basis, dtype=float)
        if basis.ndim == 1:
            basis = basis[:, None]
        if basis.shape[0] != vector.size or np.linalg.matrix_rank(basis) != basis.shape[1]:
            raise ValueError("rigid_basis must have full-rank columns matching the mode size")
        orthonormal, _ = np.linalg.qr(basis, mode="reduced")
        rigid_fraction = float(np.linalg.norm(orthonormal.T @ vector) ** 2 / norm_squared)

    drilling_fraction = 0.0
    if drilling_mask is not None:
        mask = np.asarray(drilling_mask, dtype=bool).reshape(-1)
        if mask.size != vector.size:
            raise ValueError("drilling_mask must match the mode size")
        drilling_fraction = float(vector[mask] @ vector[mask] / norm_squared)

    constraint_leakage = 0.0
    if constrained_mask is not None:
        mask = np.asarray(constrained_mask, dtype=bool).reshape(-1)
        if mask.size != vector.size:
            raise ValueError("constrained_mask must match the mode size")
        constraint_leakage = math.sqrt(float(vector[mask] @ vector[mask] / norm_squared))

    maximum_group_fraction = 0.0
    if groups:
        fractions: list[float] = []
        covered: set[int] = set()
        for group in groups:
            indices = np.asarray(group, dtype=int).reshape(-1)
            if indices.size == 0 or np.any(indices < 0) or np.any(indices >= vector.size):
                raise ValueError("mode groups contain invalid indices")
            if any(int(index) in covered for index in indices):
                raise ValueError("mode groups must not overlap")
            covered.update(int(index) for index in indices)
            fractions.append(float(vector[indices] @ vector[indices] / norm_squared))
        maximum_group_fraction = max(fractions)

    spectral_scale = max(float(np.max(np.abs(np.linalg.eigvalsh(k_m)))), 1e-30)
    relative_material_energy = abs(float(vector @ k_m @ vector)) / (spectral_scale * norm_squared)
    geometric_energy = float(vector @ k_g @ vector)
    reasons: list[str] = []
    if rigid_fraction >= rigid_fraction_limit:
        reasons.append("rigid_dominated")
    if drilling_fraction >= drilling_fraction_limit:
        reasons.append("drilling_dominated")
    if relative_material_energy <= zero_energy_limit:
        reasons.append("zero_energy")
    if constraint_leakage > constraint_leakage_limit:
        reasons.append("constraint_leakage")
    if maximum_group_fraction >= localization_limit:
        reasons.append("single_group_localization")
    if geometric_energy <= 0.0:
        reasons.append("wrong_load_direction")
    return ModeFilterResult(
        not reasons,
        tuple(reasons),
        rigid_fraction,
        drilling_fraction,
        relative_material_energy,
        constraint_leakage,
        maximum_group_fraction,
        geometric_energy,
    )
