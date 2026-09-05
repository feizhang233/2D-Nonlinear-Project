"""GNIA preparation and Koiter imperfection-sensitivity reference formulas."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ImperfectionResult:
    offsets_mm: FloatArray
    target_amplitude_mm: float
    actual_max_amplitude_mm: float
    sign: int
    normalization_factor: float


@dataclass(frozen=True)
class KoiterResult:
    limit_load_factor: float
    load_reduction_fraction: float
    modal_amplitude: float


@dataclass(frozen=True)
class AppliedImperfectionResult:
    coordinates_mm: FloatArray
    displacement_vectors_mm: FloatArray
    scalar_offsets_mm: FloatArray
    actual_max_amplitude_mm: float
    rms_amplitude_mm: float
    fixed_boundary_max_movement_mm: float
    minimum_area_ratio: float
    minimum_normal_alignment: float
    best_fit_rigid_fraction: float
    thickness_valid: bool
    geometry_valid: bool
    source_id: str


@dataclass(frozen=True)
class RigidProjectionResult:
    deformation_only_mm: FloatArray
    fitted_rigid_motion_mm: FloatArray
    rigid_parameters: FloatArray
    rigid_fraction_before: float
    rigid_fraction_after: float


def map_normal_imperfection(
    normal_mode: ArrayLike,
    *,
    amplitude_mm: float,
    sign: int,
    fixed_mask: ArrayLike | None = None,
) -> ImperfectionResult:
    """Map a normal translational mode to a length-valued imperfection.

    Rotational and drilling DOFs must be removed before calling this function.
    A supplied ``fixed_mask`` is checked, not silently zeroed, so an invalid mode
    cannot move a constrained boundary unnoticed.
    """

    mode = np.asarray(normal_mode, dtype=float).reshape(-1)
    if mode.size == 0 or not np.all(np.isfinite(mode)):
        raise ValueError("normal_mode must be a finite non-empty vector")
    if not math.isfinite(amplitude_mm) or amplitude_mm <= 0.0:
        raise ValueError("amplitude_mm must be a finite positive length")
    if sign not in (-1, 1):
        raise ValueError("sign must be -1 or +1")
    scale = float(np.max(np.abs(mode)))
    if scale <= 0.0:
        raise ValueError("normal_mode has no geometric amplitude")
    if fixed_mask is not None:
        mask = np.asarray(fixed_mask, dtype=bool).reshape(-1)
        if mask.size != mode.size:
            raise ValueError("fixed_mask must match normal_mode")
        if np.any(np.abs(mode[mask]) > 1e-12 * scale):
            raise ValueError("normal_mode would move a fixed boundary")
    offsets = sign * float(amplitude_mm) * mode / scale
    return ImperfectionResult(offsets, float(amplitude_mm), float(np.max(np.abs(offsets))), sign, scale)


def _polygon_area_vector(points: FloatArray) -> FloatArray:
    area = np.zeros(3, dtype=float)
    for current, following in zip(points, np.roll(points, -1, axis=0), strict=True):
        area += np.cross(current, following)
    return 0.5 * area


def _rigid_fit_operator(coordinates: FloatArray) -> FloatArray:
    centered = coordinates - np.mean(coordinates, axis=0)
    operator = np.zeros((3 * coordinates.shape[0], 6), dtype=float)
    for index, (x, y, z) in enumerate(centered):
        row = 3 * index
        operator[row : row + 3, :3] = np.eye(3)
        operator[row : row + 3, 3:] = np.array(
            [[0.0, z, -y], [-z, 0.0, x], [y, -x, 0.0]], dtype=float
        )
    return operator


def _best_fit_rigid_fraction(coordinates: FloatArray, displacements: FloatArray) -> float:
    operator = _rigid_fit_operator(coordinates)
    flattened = displacements.reshape(-1)
    denominator = float(np.linalg.norm(flattened))
    if denominator == 0.0:
        return 0.0
    coefficients = np.linalg.lstsq(operator, flattened, rcond=None)[0]
    fitted = operator @ coefficients
    return float(np.linalg.norm(fitted) / denominator)


def project_out_rigid_body_motion(
    coordinates_mm: ArrayLike,
    displacement_vectors_mm: ArrayLike,
) -> RigidProjectionResult:
    """Remove the least-squares infinitesimal translation/rotation component."""

    coordinates = np.asarray(coordinates_mm, dtype=float)
    displacements = np.asarray(displacement_vectors_mm, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3 or displacements.shape != coordinates.shape:
        raise ValueError("coordinates and displacement_vectors must have shape (n_node, 3)")
    if coordinates.shape[0] < 3 or not np.all(np.isfinite(coordinates)) or not np.all(np.isfinite(displacements)):
        raise ValueError("at least three finite nodes are required")
    operator = _rigid_fit_operator(coordinates)
    flattened = displacements.reshape(-1)
    parameters = np.linalg.lstsq(operator, flattened, rcond=None)[0]
    fitted = (operator @ parameters).reshape(displacements.shape)
    deformation = displacements - fitted
    before = _best_fit_rigid_fraction(coordinates, displacements)
    after = _best_fit_rigid_fraction(coordinates, deformation)
    return RigidProjectionResult(deformation, fitted, parameters, before, after)


def apply_normal_imperfection(
    coordinates_mm: ArrayLike,
    nodal_normals: ArrayLike,
    normal_mode: ArrayLike,
    *,
    amplitude_mm: float,
    sign: int,
    fixed_mask: ArrayLike,
    elements: Sequence[ArrayLike],
    thickness_mm: float,
    source_id: str,
) -> AppliedImperfectionResult:
    """Apply a scalar normal mode to coordinates and audit the resulting mesh."""

    coordinates = np.asarray(coordinates_mm, dtype=float)
    normals = np.asarray(nodal_normals, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3 or normals.shape != coordinates.shape:
        raise ValueError("coordinates and nodal_normals must both have shape (n_node, 3)")
    if not np.all(np.isfinite(coordinates)) or not np.all(np.isfinite(normals)):
        raise ValueError("coordinates and normals must be finite")
    normal_lengths = np.linalg.norm(normals, axis=1)
    if np.any(normal_lengths <= 0.0):
        raise ValueError("nodal normals must be non-zero")
    unit_normals = normals / normal_lengths[:, None]
    mask = np.asarray(fixed_mask, dtype=bool).reshape(-1)
    if mask.size != coordinates.shape[0]:
        raise ValueError("fixed_mask must match the node count")
    mapping = map_normal_imperfection(
        normal_mode,
        amplitude_mm=amplitude_mm,
        sign=sign,
        fixed_mask=mask,
    )
    if mapping.offsets_mm.size != coordinates.shape[0]:
        raise ValueError("normal_mode must contain one scalar per node")
    displacement_vectors = mapping.offsets_mm[:, None] * unit_normals
    updated = coordinates + displacement_vectors
    fixed_movement = (
        float(np.max(np.linalg.norm(displacement_vectors[mask], axis=1))) if np.any(mask) else 0.0
    )
    area_ratios: list[float] = []
    normal_alignments: list[float] = []
    for element in elements:
        indices = np.asarray(element, dtype=int).reshape(-1)
        if indices.size < 3 or np.any(indices < 0) or np.any(indices >= coordinates.shape[0]):
            raise ValueError("elements contain invalid node indices")
        original_area = _polygon_area_vector(coordinates[indices])
        updated_area = _polygon_area_vector(updated[indices])
        original_norm = float(np.linalg.norm(original_area))
        updated_norm = float(np.linalg.norm(updated_area))
        if original_norm <= 0.0:
            raise ValueError("reference element has zero area")
        area_ratios.append(updated_norm / original_norm)
        normal_alignments.append(float(updated_area @ original_area / max(updated_norm * original_norm, 1e-30)))
    minimum_area_ratio = min(area_ratios)
    minimum_normal_alignment = min(normal_alignments)
    thickness_valid = math.isfinite(thickness_mm) and thickness_mm > 0.0
    geometry_valid = (
        fixed_movement <= 1e-12
        and minimum_area_ratio > 1e-6
        and minimum_normal_alignment > 0.0
        and thickness_valid
    )
    return AppliedImperfectionResult(
        updated,
        displacement_vectors,
        mapping.offsets_mm,
        mapping.actual_max_amplitude_mm,
        float(math.sqrt(np.mean(mapping.offsets_mm**2))),
        fixed_movement,
        minimum_area_ratio,
        minimum_normal_alignment,
        _best_fit_rigid_fraction(coordinates, displacement_vectors),
        thickness_valid,
        geometry_valid,
        str(source_id),
    )


def koiter_two_thirds(*, a4: float, imperfection_mu: float) -> KoiterResult:
    """Symmetric subcritical Koiter 2/3-law limit-point estimate."""

    if not math.isfinite(a4) or a4 >= 0.0:
        raise ValueError("the 2/3-law used here requires a finite A4 < 0")
    if not math.isfinite(imperfection_mu) or imperfection_mu == 0.0:
        raise ValueError("imperfection_mu must be finite and non-zero")
    magnitude_a4 = abs(a4)
    magnitude_mu = abs(imperfection_mu)
    reduction = 1.5 * magnitude_a4 ** (1.0 / 3.0) * magnitude_mu ** (2.0 / 3.0)
    amplitude = (magnitude_mu / (8.0 * magnitude_a4)) ** (1.0 / 3.0)
    return KoiterResult(1.0 - reduction, reduction, amplitude)
