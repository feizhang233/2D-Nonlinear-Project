"""P12 Total Lagrangian Q4 with plane-strain Saint-Venant--Kirchhoff elasticity."""

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


class TotalLagrangianQ4Error(ValueError):
    """One typed reference/current-configuration failure for a P12 element."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        element_id: str,
        min_det_j: float | None = None,
        min_det_f: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.element_id = element_id
        self.min_det_j = min_det_j
        self.min_det_f = min_det_f


@dataclass(frozen=True, slots=True)
class TotalLagrangianQ4Response:
    """Objective element response and raw Gauss-point evidence."""

    internal_force: FloatArray
    tangent: FloatArray
    material_tangent: FloatArray
    geometric_tangent: FloatArray
    strain_energy: float
    min_det_j: float
    min_det_f: float
    gauss_points: tuple[dict[str, object], ...]


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


def saint_venant_kirchhoff_plane_strain_matrix(
    young: object,
    poisson: object,
) -> FloatArray:
    """Return ``S=[S11,S22,S12]`` versus ``[E11,E22,2E12]``."""

    elastic_modulus = _positive(young, name="young")
    if isinstance(poisson, bool):
        raise ValueError("poisson must satisfy -1 < poisson < 0.5")
    ratio = float(poisson)
    if not np.isfinite(ratio) or not -1.0 < ratio < 0.5:
        raise ValueError("poisson must satisfy -1 < poisson < 0.5")
    lame_lambda = elastic_modulus * ratio / ((1.0 + ratio) * (1.0 - 2.0 * ratio))
    shear_modulus = elastic_modulus / (2.0 * (1.0 + ratio))
    return np.asarray(
        [
            [lame_lambda + 2.0 * shear_modulus, lame_lambda, 0.0],
            [lame_lambda, lame_lambda + 2.0 * shear_modulus, 0.0],
            [0.0, 0.0, shear_modulus],
        ],
        dtype=float,
    )


def q4_shape(
    xi: float,
    eta: float,
) -> tuple[FloatArray, FloatArray]:
    """Return Q4 shape functions and rows ``[dN/dxi,dN/deta]``."""

    shape = 0.25 * np.asarray(
        [
            (1.0 - xi) * (1.0 - eta),
            (1.0 + xi) * (1.0 - eta),
            (1.0 + xi) * (1.0 + eta),
            (1.0 - xi) * (1.0 + eta),
        ],
        dtype=float,
    )
    derivatives = 0.25 * np.asarray(
        [
            [-(1.0 - eta), -(1.0 - xi)],
            [1.0 - eta, -(1.0 + xi)],
            [1.0 + eta, 1.0 + xi],
            [-(1.0 + eta), 1.0 - xi],
        ],
        dtype=float,
    )
    return shape, derivatives


def _strain_displacement_matrix(gradient: FloatArray, deformation: FloatArray) -> FloatArray:
    matrix = np.zeros((3, 8), dtype=float)
    for node, (gradient_x, gradient_y) in enumerate(gradient):
        column = 2 * node
        matrix[:, column : column + 2] = np.asarray(
            [
                [deformation[0, 0] * gradient_x, deformation[1, 0] * gradient_x],
                [deformation[0, 1] * gradient_y, deformation[1, 1] * gradient_y],
                [
                    deformation[0, 0] * gradient_y
                    + deformation[0, 1] * gradient_x,
                    deformation[1, 0] * gradient_y
                    + deformation[1, 1] * gradient_x,
                ],
            ]
        )
    return matrix


def evaluate_total_lagrangian_q4(
    reference_coordinates: ArrayLike,
    displacement: ArrayLike,
    *,
    young: object,
    poisson: object,
    thickness: object,
    element_id: str = "Q4",
) -> TotalLagrangianQ4Response:
    """Integrate one objective plane-strain TL Q4 response in the reference volume."""

    coordinates = _finite_array(
        reference_coordinates,
        (4, 2),
        name="reference_coordinates",
    )
    vector = _finite_array(displacement, (8,), name="displacement")
    nodal_displacement = vector.reshape(4, 2)
    actual_thickness = _positive(thickness, name="thickness")
    constitutive = saint_venant_kirchhoff_plane_strain_matrix(young, poisson)
    poisson_ratio = float(poisson)
    elastic_modulus = float(young)
    lame_lambda = elastic_modulus * poisson_ratio / (
        (1.0 + poisson_ratio) * (1.0 - 2.0 * poisson_ratio)
    )

    characteristic_squared = float(
        max(np.dot(edge, edge) for edge in np.roll(coordinates, -1, axis=0) - coordinates)
    )
    jacobian_tolerance = max(np.finfo(float).tiny, 1.0e-12 * characteristic_squared)
    internal = np.zeros(8, dtype=float)
    material_tangent = np.zeros((8, 8), dtype=float)
    geometric_tangent = np.zeros((8, 8), dtype=float)
    energy = 0.0
    det_j_values: list[float] = []
    det_f_values: list[float] = []
    gauss_records: list[dict[str, object]] = []

    for gauss_index, (xi, eta) in enumerate(Q4_GAUSS_POINTS):
        shape, natural_gradient = q4_shape(xi, eta)
        reference_jacobian = coordinates.T @ natural_gradient
        det_j = float(np.linalg.det(reference_jacobian))
        det_j_values.append(det_j)
        if not np.isfinite(det_j) or det_j <= jacobian_tolerance:
            raise TotalLagrangianQ4Error(
                "CONTINUUM_REFERENCE_MAPPING_INVALID",
                (
                    f"element {element_id!r} has non-positive or near-degenerate "
                    f"reference detJ={det_j:.17g} at Gauss point {gauss_index}"
                ),
                element_id=element_id,
                min_det_j=det_j,
            )
        reference_gradient = natural_gradient @ np.linalg.inv(reference_jacobian)
        deformation = np.eye(2) + nodal_displacement.T @ reference_gradient
        det_f = float(np.linalg.det(deformation))
        det_f_values.append(det_f)
        if not np.isfinite(det_f) or det_f <= 0.0:
            raise TotalLagrangianQ4Error(
                "CONTINUUM_NONPOSITIVE_DETF",
                (
                    f"element {element_id!r} has detF={det_f:.17g} <= 0 "
                    f"at Gauss point {gauss_index}"
                ),
                element_id=element_id,
                min_det_j=min(det_j_values),
                min_det_f=det_f,
            )

        right_cauchy_green = deformation.T @ deformation
        green = 0.5 * (right_cauchy_green - np.eye(2))
        strain = np.asarray([green[0, 0], green[1, 1], 2.0 * green[0, 1]])
        second_piola_vector = constitutive @ strain
        second_piola = np.asarray(
            [
                [second_piola_vector[0], second_piola_vector[2]],
                [second_piola_vector[2], second_piola_vector[1]],
            ]
        )
        second_piola_33 = lame_lambda * (green[0, 0] + green[1, 1])
        first_piola = deformation @ second_piola
        cauchy = deformation @ second_piola @ deformation.T / det_f
        cauchy_33 = second_piola_33 / det_f
        matrix_b = _strain_displacement_matrix(reference_gradient, deformation)
        integration = det_j * actual_thickness

        internal += matrix_b.T @ second_piola_vector * integration
        material_tangent += matrix_b.T @ constitutive @ matrix_b * integration
        for node_a, gradient_a in enumerate(reference_gradient):
            for node_b, gradient_b in enumerate(reference_gradient):
                scalar = float(gradient_a @ second_piola @ gradient_b) * integration
                block_a = slice(2 * node_a, 2 * node_a + 2)
                block_b = slice(2 * node_b, 2 * node_b + 2)
                geometric_tangent[block_a, block_b] += scalar * np.eye(2)
        density = float(0.5 * strain @ second_piola_vector)
        energy += density * integration
        gauss_records.append(
            {
                "gauss_index": gauss_index,
                "natural_coordinates": [xi, eta],
                "shape_functions": [float(value) for value in shape],
                "det_j0": det_j,
                "deformation_gradient": deformation.tolist(),
                "det_f": det_f,
                "green_lagrange": [
                    float(green[0, 0]),
                    float(green[1, 1]),
                    float(green[0, 1]),
                    0.0,
                ],
                "second_piola": [
                    float(second_piola[0, 0]),
                    float(second_piola[1, 1]),
                    float(second_piola[0, 1]),
                    float(second_piola_33),
                ],
                "first_piola": first_piola.tolist(),
                "cauchy": [
                    float(cauchy[0, 0]),
                    float(cauchy[1, 1]),
                    float(cauchy[0, 1]),
                    float(cauchy_33),
                ],
                "strain_energy_density": density,
            }
        )

    tangent = material_tangent + geometric_tangent
    if not np.all(np.isfinite(internal)) or not np.all(np.isfinite(tangent)):
        raise ValueError(f"element {element_id!r} response overflowed; rescale the model")
    for array in (internal, tangent, material_tangent, geometric_tangent):
        array.setflags(write=False)
    return TotalLagrangianQ4Response(
        internal_force=internal,
        tangent=tangent,
        material_tangent=material_tangent,
        geometric_tangent=geometric_tangent,
        strain_energy=float(energy),
        min_det_j=min(det_j_values),
        min_det_f=min(det_f_values),
        gauss_points=tuple(gauss_records),
    )


__all__ = [
    "Q4_GAUSS_POINTS",
    "TotalLagrangianQ4Error",
    "TotalLagrangianQ4Response",
    "evaluate_total_lagrangian_q4",
    "q4_shape",
    "saint_venant_kirchhoff_plane_strain_matrix",
]
