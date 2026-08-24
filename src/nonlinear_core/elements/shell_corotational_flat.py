"""Energy-consistent corotational Q4 flat shell using ``shell-core`` operators.

The element accepts node-major global ``[u, v, w, rx, ry, rz]`` rotation-vector
DOFs.  A current frame removes finite rigid translation/rotation; the remaining
local deformation is evaluated by the frozen linear Q4/QLLL flat-shell core.
The response is therefore intended for large rigid-body rotation with small
local shell strain, not a general finite-rotation curved-shell theory.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.spatial.transform import Rotation

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class CorotationalFlatShellResponse:
    """One objective flat-shell response with raw core recovery evidence."""

    internal_force: FloatArray
    tangent: FloatArray
    membrane_energy: float
    bending_energy: float
    shear_energy: float
    drilling_energy: float
    min_det_j: float
    local_deformation: FloatArray
    current_basis: FloatArray
    rigid_rotation_vector: FloatArray
    gauss_points: tuple[dict[str, object], ...]
    alpha_d: float
    differentiation_step: float

    @property
    def strain_energy(self) -> float:
        return (
            self.membrane_energy
            + self.bending_energy
            + self.shear_energy
            + self.drilling_energy
        )


def _finite_array(value: ArrayLike, shape: tuple[int, ...], *, name: str) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite array with shape {shape}")
    return result


def _positive(value: object, *, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive finite number")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


def _poisson(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("poisson must satisfy -1 < poisson < 0.5")
    result = float(value)
    if not np.isfinite(result) or not -1.0 < result < 0.5:
        raise ValueError("poisson must satisfy -1 < poisson < 0.5")
    return result


def _basis_rows(points: FloatArray) -> FloatArray:
    edge_x = points[1] - points[0]
    length_x = float(np.linalg.norm(edge_x))
    if length_x <= np.finfo(float).eps:
        raise ValueError("corotational shell current edge 1-2 is degenerate")
    e_x = edge_x / length_x
    normal = np.cross(e_x, points[3] - points[0])
    length_normal = float(np.linalg.norm(normal))
    if length_normal <= np.finfo(float).eps:
        raise ValueError("corotational shell current nodes 1,2,4 are collinear")
    e_z = normal / length_normal
    e_y = np.cross(e_z, e_x)
    return np.vstack((e_x, e_y, e_z))


def _embed_physical_matrix(matrix: ArrayLike) -> FloatArray:
    source = np.asarray(matrix, dtype=float)
    if source.shape != (20, 20):
        raise ValueError("shell-core physical matrix must have shape (20,20)")
    target = np.zeros((24, 24), dtype=float)
    physical = np.asarray(
        [index for node in range(4) for index in range(6 * node, 6 * node + 5)],
        dtype=np.intp,
    )
    target[np.ix_(physical, physical)] = source
    return target


def _physical_vector(augmented: FloatArray) -> FloatArray:
    return np.asarray(
        [augmented[6 * node + local] for node in range(4) for local in range(5)],
        dtype=float,
    )


@lru_cache(maxsize=128)
def _reference_data(
    coordinate_key: tuple[float, ...],
    young: float,
    poisson: float,
    thickness: float,
    shear_correction: float,
    alpha_d: float,
) -> tuple[
    object,
    object,
    object,
    FloatArray,
    FloatArray,
    FloatArray,
    FloatArray,
    FloatArray,
    FloatArray,
]:
    from shell_core import (
        build_element_geometry,
        build_global_shell_operator,
        build_isotropic_constitutive,
    )

    coordinates = np.asarray(coordinate_key, dtype=float).reshape(4, 3)
    geometry = build_element_geometry(coordinates.tolist())
    constitutive = build_isotropic_constitutive(
        young,
        poisson,
        thickness,
        shear_correction,
    )
    operator = build_global_shell_operator(
        geometry,
        constitutive,
        alpha_d=alpha_d,
        shear_formulation="qlll_assumed_strain",
        drilling_formulation="continuum_consistent",
    )
    transform = np.asarray(operator.transform.augmented_local_from_global, dtype=float)
    membrane = _embed_physical_matrix(operator.local_operator.k_membrane)
    bending = _embed_physical_matrix(operator.local_operator.k_bending)
    shear = _embed_physical_matrix(operator.local_operator.k_shear)
    drilling_global = np.asarray(operator.k_drilling, dtype=float)
    drilling = transform @ drilling_global @ transform.T
    total = membrane + bending + shear + drilling
    for array in (transform, membrane, bending, shear, drilling, total):
        array.setflags(write=False)
    return geometry, constitutive, operator, transform, membrane, bending, shear, drilling, total


def _corotated_deformation(
    reference_coordinates: FloatArray,
    displacement: FloatArray,
    reference_basis: FloatArray,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    nodal = displacement.reshape(4, 6)
    current_coordinates = reference_coordinates + nodal[:, :3]
    current_basis = _basis_rows(current_coordinates)
    reference_relative = reference_coordinates - reference_coordinates[0]
    current_relative = current_coordinates - current_coordinates[0]
    reference_local = reference_relative @ reference_basis.T
    current_local = current_relative @ current_basis.T
    translation_local = current_local - reference_local

    frame_rotation = current_basis.T @ reference_basis
    rigid_rotation_vector = Rotation.from_matrix(frame_rotation).as_rotvec()
    local = np.zeros((4, 6), dtype=float)
    local[:, :3] = translation_local
    for node in range(4):
        nodal_rotation = Rotation.from_rotvec(nodal[node, 3:]).as_matrix()
        relative_rotation = current_basis @ nodal_rotation @ reference_basis.T
        relative_vector = Rotation.from_matrix(relative_rotation).as_rotvec()
        local[node, 3:] = (-relative_vector[1], relative_vector[0], relative_vector[2])
    return local.ravel(), current_basis, rigid_rotation_vector, current_coordinates


def _quadratic(matrix: FloatArray, vector: FloatArray) -> float:
    return 0.5 * float(vector @ matrix @ vector)


def _numerical_energy_derivatives(
    energy: Callable[[FloatArray], float],
    vector: FloatArray,
    scales: FloatArray,
    relative_step: float,
) -> tuple[FloatArray, FloatArray]:
    """Return a fourth-order gradient and symmetric energy Hessian.

    The local constitutive operator is exact; only the nonlinear corotational
    coordinate map is differentiated numerically. Translation increments are
    scaled by the reference characteristic length and rotations by one radian.
    """

    size = vector.size
    steps = relative_step * scales
    origin = energy(vector)
    plus: list[float] = []
    minus: list[float] = []
    plus_two: list[float] = []
    minus_two: list[float] = []
    gradient = np.zeros(size, dtype=float)
    hessian = np.zeros((size, size), dtype=float)
    for index, step in enumerate(steps):
        direction = np.zeros(size, dtype=float)
        direction[index] = step
        value_plus = energy(vector + direction)
        value_minus = energy(vector - direction)
        value_plus_two = energy(vector + 2.0 * direction)
        value_minus_two = energy(vector - 2.0 * direction)
        plus.append(value_plus)
        minus.append(value_minus)
        plus_two.append(value_plus_two)
        minus_two.append(value_minus_two)
        gradient[index] = (
            -value_plus_two + 8.0 * value_plus - 8.0 * value_minus + value_minus_two
        ) / (12.0 * step)
        hessian[index, index] = (
            -value_plus_two
            + 16.0 * value_plus
            - 30.0 * origin
            + 16.0 * value_minus
            - value_minus_two
        ) / (12.0 * step * step)

    for left in range(size):
        left_direction = np.zeros(size, dtype=float)
        left_direction[left] = steps[left]
        for right in range(left + 1, size):
            right_direction = np.zeros(size, dtype=float)
            right_direction[right] = steps[right]
            value = (
                energy(vector + left_direction + right_direction)
                - energy(vector + left_direction - right_direction)
                - energy(vector - left_direction + right_direction)
                + energy(vector - left_direction - right_direction)
            ) / (4.0 * steps[left] * steps[right])
            hessian[left, right] = value
            hessian[right, left] = value
    return gradient, hessian


def evaluate_corotational_flat_shell(
    reference_coordinates: ArrayLike,
    displacement: ArrayLike,
    *,
    young: object,
    poisson: object,
    thickness: object,
    shear_correction: object = 5.0 / 6.0,
    alpha_d: object = 1.0e-4,
    differentiation_step: object = 2.0e-5,
) -> CorotationalFlatShellResponse:
    """Evaluate one corotational flat shell and raw ``N/M/Q`` recovery."""

    from shell_core import (
        LocalBasis,
        build_element_transform,
        evaluate_drilling_response,
        evaluate_membrane_bending_response,
        evaluate_shear_response,
    )

    coordinates = _finite_array(reference_coordinates, (4, 3), name="reference_coordinates")
    vector = _finite_array(displacement, (24,), name="displacement")
    elastic_modulus = _positive(young, name="young")
    poisson_ratio = _poisson(poisson)
    actual_thickness = _positive(thickness, name="thickness")
    actual_shear_correction = _positive(shear_correction, name="shear_correction")
    actual_alpha = _positive(alpha_d, name="alpha_d")
    actual_step = _positive(differentiation_step, name="differentiation_step")
    if actual_step >= 1.0e-2:
        raise ValueError("differentiation_step must be less than 1e-2")

    coordinate_key = tuple(float(value) for value in coordinates.ravel())
    (
        geometry,
        constitutive,
        operator,
        reference_transform,
        membrane_matrix,
        bending_matrix,
        shear_matrix,
        drilling_matrix,
        total_matrix,
    ) = _reference_data(
        coordinate_key,
        elastic_modulus,
        poisson_ratio,
        actual_thickness,
        actual_shear_correction,
        actual_alpha,
    )
    reference_basis = np.asarray(geometry.basis.lambda_rows, dtype=float)

    def deformation_at(candidate: FloatArray) -> FloatArray:
        return _corotated_deformation(coordinates, candidate, reference_basis)[0]

    def energy_at(candidate: FloatArray) -> float:
        local = deformation_at(candidate)
        return _quadratic(total_matrix, local)

    local, current_basis, rigid_rotation_vector, current_coordinates = _corotated_deformation(
        coordinates,
        vector,
        reference_basis,
    )
    local_norm = float(np.linalg.norm(local))
    if local_norm <= 2.0e-12 * max(float(geometry.l_char), 1.0):
        internal = np.zeros(24, dtype=float)
        current_local_basis = LocalBasis(
            e_x=tuple(float(value) for value in current_basis[0]),
            e_y=tuple(float(value) for value in current_basis[1]),
            e_z=tuple(float(value) for value in current_basis[2]),
        )
        current_transform = np.asarray(
            build_element_transform(current_local_basis).augmented_local_from_global,
            dtype=float,
        )
        tangent = current_transform.T @ total_matrix @ current_transform
    else:
        scales = np.asarray(
            [float(geometry.l_char) if index % 6 < 3 else 1.0 for index in range(24)],
            dtype=float,
        )
        internal, tangent = _numerical_energy_derivatives(
            energy_at,
            vector,
            scales,
            actual_step,
        )
        tangent = 0.5 * (tangent + tangent.T)

    membrane_energy = _quadratic(membrane_matrix, local)
    bending_energy = _quadratic(bending_matrix, local)
    shear_energy = _quadratic(shear_matrix, local)
    drilling_energy = _quadratic(drilling_matrix, local)
    physical = _physical_vector(local)
    membrane_response = evaluate_membrane_bending_response(
        geometry,
        constitutive,
        physical,
    )
    shear_response = evaluate_shear_response(
        geometry,
        constitutive,
        physical,
        formulation="qlll_assumed_strain",
    )
    artificial_global = reference_transform.T @ local
    drilling_response = evaluate_drilling_response(
        geometry,
        constitutive,
        actual_alpha,
        artificial_global,
        transform=operator.transform,
    )
    gauss_points: list[dict[str, object]] = []
    for geometry_point, membrane_point, shear_point, drilling_point in zip(
        geometry.gauss_points,
        membrane_response.gauss_points,
        shear_response.gauss_points,
        drilling_response.gauss_points,
        strict=True,
    ):
        current_point = np.asarray(geometry_point.shape.n, dtype=float) @ current_coordinates
        gauss_points.append(
            {
                "point_id": geometry_point.point_id,
                "natural_point": list(geometry_point.natural),
                "current_global_point": current_point.tolist(),
                "det_j": float(geometry_point.jacobian.det_j),
                "membrane_strain": list(membrane_point.membrane_strain),
                "curvature": list(membrane_point.curvature),
                "assumed_shear_strain": list(shear_point.shear_strain),
                "membrane_resultant": list(membrane_point.membrane_resultant),
                "bending_resultant": list(membrane_point.bending_resultant),
                "shear_resultant": list(shear_point.shear_resultant),
                "stress_top": list(membrane_point.surface_stresses.top),
                "stress_bottom": list(membrane_point.surface_stresses.bottom),
                "drilling_mismatch": float(drilling_point.mismatch),
                "membrane_energy_density": float(membrane_point.membrane_energy_density),
                "bending_energy_density": float(membrane_point.bending_energy_density),
                "shear_energy_density": float(shear_point.shear_energy_density),
                "drilling_energy_density": float(drilling_point.energy_density),
                "result_basis": "current-corotational-local",
            }
        )

    min_det_j = min(float(point.jacobian.det_j) for point in geometry.gauss_points)
    for array in (internal, tangent, local, current_basis, rigid_rotation_vector):
        if not np.all(np.isfinite(array)):
            raise ValueError("corotational shell response contains non-finite values")
        array.setflags(write=False)
    return CorotationalFlatShellResponse(
        internal_force=internal,
        tangent=tangent,
        membrane_energy=float(membrane_energy),
        bending_energy=float(bending_energy),
        shear_energy=float(shear_energy),
        drilling_energy=float(drilling_energy),
        min_det_j=min_det_j,
        local_deformation=local,
        current_basis=current_basis,
        rigid_rotation_vector=rigid_rotation_vector,
        gauss_points=tuple(gauss_points),
        alpha_d=actual_alpha,
        differentiation_step=actual_step,
    )


__all__ = ["CorotationalFlatShellResponse", "evaluate_corotational_flat_shell"]
