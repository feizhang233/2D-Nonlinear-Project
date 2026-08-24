"""Q4 von Karman plate with a public-core MITC4 transverse operator.

The element uses the node-major order ``[u, v, w, theta_x, theta_y]``.  Its
membrane strain is von Karman (small in-plane strain, moderate transverse
rotation); bending and transverse shear remain the linear Reissner--Mindlin
operators supplied by ``mindlin-plate-core``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

_GAUSS = float(1.0 / np.sqrt(3.0))
Q4_GAUSS_POINTS: tuple[tuple[float, float], ...] = (
    (-_GAUSS, -_GAUSS),
    (_GAUSS, -_GAUSS),
    (_GAUSS, _GAUSS),
    (-_GAUSS, _GAUSS),
)
_PLATE_DOF_INDICES = np.asarray(
    [index for node in range(4) for index in (5 * node + 2, 5 * node + 3, 5 * node + 4)],
    dtype=np.intp,
)


@dataclass(frozen=True, slots=True)
class VonKarmanMITC4Response:
    """Element response with separately auditable energy/tangent terms."""

    internal_force: FloatArray
    tangent: FloatArray
    membrane_material_tangent: FloatArray
    membrane_geometric_tangent: FloatArray
    bending_tangent: FloatArray
    shear_tangent: FloatArray
    membrane_energy: float
    bending_energy: float
    shear_energy: float
    min_det_j: float
    gauss_points: tuple[dict[str, object], ...]

    @property
    def strain_energy(self) -> float:
        return self.membrane_energy + self.bending_energy + self.shear_energy


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


def _membrane_kinematics(
    gradients: FloatArray,
    nodal: FloatArray,
) -> tuple[FloatArray, FloatArray, float, float]:
    """Return engineering membrane strain, its derivative, and ``w,x/w,y``."""

    displacement_gradients = nodal[:, :3].T @ gradients
    du_dx, du_dy = displacement_gradients[0]
    dv_dx, dv_dy = displacement_gradients[1]
    dw_dx, dw_dy = displacement_gradients[2]
    strain = np.asarray(
        [
            du_dx + 0.5 * dw_dx**2,
            dv_dy + 0.5 * dw_dy**2,
            du_dy + dv_dx + dw_dx * dw_dy,
        ],
        dtype=float,
    )
    matrix = np.zeros((3, 20), dtype=float)
    for node, (dn_dx, dn_dy) in enumerate(gradients):
        column = 5 * node
        matrix[:, column] = [dn_dx, 0.0, dn_dy]
        matrix[:, column + 1] = [0.0, dn_dy, dn_dx]
        matrix[:, column + 2] = [
            dw_dx * dn_dx,
            dw_dy * dn_dy,
            dw_dy * dn_dx + dw_dx * dn_dy,
        ]
    return strain, matrix, float(dw_dx), float(dw_dy)


def evaluate_von_karman_mitc4(
    reference_coordinates: ArrayLike,
    displacement: ArrayLike,
    *,
    young: object,
    poisson: object,
    thickness: object,
    shear_correction: object = 5.0 / 6.0,
) -> VonKarmanMITC4Response:
    """Integrate one moderate-rotation von Karman/MITC4 plate response.

    This is not a finite-rotation shell formulation.  The reference planform is
    fixed, membrane strains use the von Karman quadratic ``grad(w)`` terms, and
    the bending/shear rotations use the existing linear plate-core convention.
    """

    from mindlin_plate import (
        MindlinMaterial,
        element_response,
        kinematic_matrices,
        plate_element_matrices,
    )

    coordinates = _finite_array(reference_coordinates, (4, 2), name="reference_coordinates")
    vector = _finite_array(displacement, (20,), name="displacement")
    elastic_modulus = _positive(young, name="young")
    poisson_ratio = _poisson(poisson)
    actual_thickness = _positive(thickness, name="thickness")
    actual_shear_correction = _positive(shear_correction, name="shear_correction")
    material = MindlinMaterial(
        young=elastic_modulus,
        poisson=poisson_ratio,
        thickness=actual_thickness,
        shear_correction=actual_shear_correction,
    )
    plate_matrices = plate_element_matrices(
        coordinates,
        material,
        plate_method="M",
        shear_scheme="mitc4",
    )
    plate_vector = vector[_PLATE_DOF_INDICES]

    internal = np.zeros(20, dtype=float)
    membrane_material = np.zeros((20, 20), dtype=float)
    membrane_geometric = np.zeros((20, 20), dtype=float)
    membrane_energy = 0.0
    determinants: list[float] = []
    gauss_points: list[dict[str, object]] = []
    membrane_constitutive = actual_thickness * material.plane_stress_matrix
    nodal = vector.reshape(4, 5)

    for xi, eta in Q4_GAUSS_POINTS:
        point, _, _ = kinematic_matrices(coordinates, xi, eta)
        gradients = np.asarray(point.physical_gradients, dtype=float)
        strain, matrix_b, dw_dx, dw_dy = _membrane_kinematics(gradients, nodal)
        resultant = membrane_constitutive @ strain
        integration = float(point.det_jacobian)
        internal += matrix_b.T @ resultant * integration
        membrane_material += matrix_b.T @ membrane_constitutive @ matrix_b * integration
        membrane_energy += 0.5 * float(strain @ resultant) * integration

        for node_a, (dna_dx, dna_dy) in enumerate(gradients):
            row = 5 * node_a + 2
            for node_b, (dnb_dx, dnb_dy) in enumerate(gradients):
                column = 5 * node_b + 2
                scalar = (
                    resultant[0] * dna_dx * dnb_dx
                    + resultant[1] * dna_dy * dnb_dy
                    + resultant[2] * (dna_dx * dnb_dy + dna_dy * dnb_dx)
                )
                membrane_geometric[row, column] += scalar * integration

        plate_point = element_response(
            coordinates,
            plate_vector,
            material,
            xi,
            eta,
            shear_scheme="mitc4",
            plate_method="M",
        )
        gauss_points.append(
            {
                "natural_point": [xi, eta],
                "physical_point": plate_point.physical_point.tolist(),
                "det_j": integration,
                "membrane_strain": strain.tolist(),
                "membrane_resultant": resultant.tolist(),
                "transverse_gradient": [dw_dx, dw_dy],
                "curvature": plate_point.curvature.tolist(),
                "bending_moment": plate_point.bending_moment.tolist(),
                "shear_strain": plate_point.shear_strain.tolist(),
                "shear_force": plate_point.shear_force.tolist(),
                "stress_top": plate_point.stress_top.tolist(),
                "stress_bottom": plate_point.stress_bottom.tolist(),
                "membrane_energy_density": 0.5 * float(strain @ resultant),
                "bending_energy_density": 0.5
                * float(plate_point.curvature @ plate_point.bending_moment),
                "shear_energy_density": 0.5
                * float(plate_point.shear_strain @ plate_point.shear_force),
            }
        )
        determinants.append(integration)

    bending_tangent = np.zeros((20, 20), dtype=float)
    shear_tangent = np.zeros((20, 20), dtype=float)
    bending_tangent[np.ix_(_PLATE_DOF_INDICES, _PLATE_DOF_INDICES)] = plate_matrices.bending
    shear_tangent[np.ix_(_PLATE_DOF_INDICES, _PLATE_DOF_INDICES)] = plate_matrices.shear
    plate_internal = (plate_matrices.bending + plate_matrices.shear) @ plate_vector
    internal[_PLATE_DOF_INDICES] += plate_internal
    bending_energy = 0.5 * float(plate_vector @ plate_matrices.bending @ plate_vector)
    shear_energy = 0.5 * float(plate_vector @ plate_matrices.shear @ plate_vector)

    tangent = membrane_material + membrane_geometric + bending_tangent + shear_tangent
    tangent = 0.5 * (tangent + tangent.T)
    for array in (
        internal,
        tangent,
        membrane_material,
        membrane_geometric,
        bending_tangent,
        shear_tangent,
    ):
        if not np.all(np.isfinite(array)):
            raise ValueError("von Karman MITC4 response contains non-finite values")
        array.setflags(write=False)
    return VonKarmanMITC4Response(
        internal_force=internal,
        tangent=tangent,
        membrane_material_tangent=membrane_material,
        membrane_geometric_tangent=membrane_geometric,
        bending_tangent=bending_tangent,
        shear_tangent=shear_tangent,
        membrane_energy=float(membrane_energy),
        bending_energy=float(bending_energy),
        shear_energy=float(shear_energy),
        min_det_j=min(determinants),
        gauss_points=tuple(gauss_points),
    )


__all__ = [
    "Q4_GAUSS_POINTS",
    "VonKarmanMITC4Response",
    "evaluate_von_karman_mitc4",
]
