"""Configuration-consistent continuum and shell-point kinematics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _matrix3(value: ArrayLike, *, name: str) -> FloatArray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3), got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


def green_lagrange_strain(deformation_gradient: ArrayLike) -> FloatArray:
    deformation = _matrix3(deformation_gradient, name="deformation_gradient")
    return 0.5 * (deformation.T @ deformation - np.eye(3))


def infinitesimal_strain_from_deformation_gradient(
    deformation_gradient: ArrayLike,
) -> FloatArray:
    deformation = _matrix3(deformation_gradient, name="deformation_gradient")
    displacement_gradient = deformation - np.eye(3)
    return 0.5 * (displacement_gradient + displacement_gradient.T)


def push_forward_second_piola(
    deformation_gradient: ArrayLike,
    second_piola: ArrayLike,
) -> FloatArray:
    """Push second Piola-Kirchhoff stress to Cauchy stress."""

    deformation = _matrix3(deformation_gradient, name="deformation_gradient")
    stress = _matrix3(second_piola, name="second_piola")
    jacobian = float(np.linalg.det(deformation))
    if not np.isfinite(jacobian) or jacobian <= 0.0:
        raise ValueError(
            f"deformation gradient must have positive determinant, got {jacobian}"
        )
    return deformation @ stress @ deformation.T / jacobian


def deformation_gradient_from_shell_bases(
    reference_basis: ArrayLike,
    current_basis: ArrayLike,
) -> FloatArray:
    """Build ``F = g_current * inv(g_reference)`` from shell basis columns."""

    reference = _matrix3(reference_basis, name="reference_basis")
    current = _matrix3(current_basis, name="current_basis")
    determinant = float(np.linalg.det(reference))
    if abs(determinant) <= 1.0e-14:
        raise ValueError("reference shell basis is singular")
    return current @ np.linalg.inv(reference)


def _normalise(vector: FloatArray, *, name: str) -> FloatArray:
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1.0e-14:
        raise ValueError(f"{name} cannot be normalised")
    return vector / norm


def _q4_center_basis(
    nodes: FloatArray,
    directors: FloatArray,
) -> tuple[FloatArray, FloatArray, FloatArray, float, float]:
    if nodes.shape != (4, 3):
        raise ValueError(f"nodes must have shape (4, 3), got {nodes.shape}")
    if directors.shape != (4, 3):
        raise ValueError(f"directors must have shape (4, 3), got {directors.shape}")
    dshape_dxi = np.array([-0.25, 0.25, 0.25, -0.25])
    dshape_deta = np.array([-0.25, -0.25, 0.25, 0.25])
    a1 = dshape_dxi @ nodes
    a2 = dshape_deta @ nodes
    nodal_director_norms = np.linalg.norm(directors, axis=1)
    if not np.all(np.isfinite(nodal_director_norms)) or np.any(
        nodal_director_norms <= 1.0e-14
    ):
        raise ValueError("all nodal directors must have finite nonzero length")
    nodal_director_norm_error = float(np.max(np.abs(nodal_director_norms - 1.0)))
    interpolated_director = np.mean(directors, axis=0)
    interpolation_norm = float(np.linalg.norm(interpolated_director))
    director = _normalise(interpolated_director, name="interpolated director")
    basis = np.column_stack((a1, a2, director))
    director_gradient = np.column_stack(
        (dshape_dxi @ directors, dshape_deta @ directors)
    )
    return (
        basis,
        director,
        director_gradient,
        nodal_director_norm_error,
        interpolation_norm,
    )


@dataclass(frozen=True)
class ShellPointKinematics:
    deformation_gradient: FloatArray
    green_lagrange: FloatArray
    green_lagrange_local: FloatArray
    membrane_strain: FloatArray
    transverse_shear_strain: FloatArray
    thickness_strain: float
    reference_area_jacobian: float
    current_area_jacobian: float
    reference_signed_area_jacobian: float
    current_signed_area_jacobian: float
    deformation_jacobian: float
    director_norm_error: float
    director_interpolation_norm_before_normalisation: float
    director_gradient_change_norm: float


def q4_center_shell_kinematics(
    reference_nodes: ArrayLike,
    current_nodes: ArrayLike,
    reference_directors: ArrayLike,
    current_directors: ArrayLike,
) -> ShellPointKinematics:
    """Evaluate a Q4 center-point degenerate-shell kinematic diagnostic.

    This routine intentionally stops at the kinematic layer.  It is useful for
    rigid-motion/objectivity checks, but is not a production shell element.
    """

    reference_nodes_array = np.asarray(reference_nodes, dtype=float)
    current_nodes_array = np.asarray(current_nodes, dtype=float)
    reference_directors_array = np.asarray(reference_directors, dtype=float)
    current_directors_array = np.asarray(current_directors, dtype=float)
    (
        reference_basis,
        reference_director,
        reference_gradient,
        _,
        _,
    ) = _q4_center_basis(
        reference_nodes_array,
        reference_directors_array,
    )
    (
        current_basis,
        current_director,
        current_gradient,
        current_director_norm_error,
        current_interpolation_norm,
    ) = _q4_center_basis(
        current_nodes_array,
        current_directors_array,
    )
    reference_cross = np.cross(reference_basis[:, 0], reference_basis[:, 1])
    current_cross = np.cross(current_basis[:, 0], current_basis[:, 1])
    reference_area = float(np.linalg.norm(reference_cross))
    current_area = float(np.linalg.norm(current_cross))
    if reference_area <= 1.0e-14 or current_area <= 1.0e-14:
        raise ValueError("reference and current shell area magnitudes must be positive")
    reference_signed_area = float(reference_cross @ reference_director)
    current_signed_area = float(current_cross @ current_director)
    if reference_signed_area <= 1.0e-14:
        raise ValueError("reference shell basis has nonpositive signed area Jacobian")
    if current_signed_area <= 1.0e-14:
        raise ValueError(
            "current shell basis is inverted or has nonpositive signed area Jacobian"
        )

    deformation = deformation_gradient_from_shell_bases(reference_basis, current_basis)
    deformation_jacobian = float(np.linalg.det(deformation))
    if not np.isfinite(deformation_jacobian) or deformation_jacobian <= 0.0:
        raise ValueError(
            f"shell deformation gradient must have positive determinant, got {deformation_jacobian}"
        )
    green = green_lagrange_strain(deformation)
    e1 = _normalise(reference_basis[:, 0], name="reference tangent 1")
    e3 = _normalise(reference_cross, name="reference normal")
    e2 = _normalise(np.cross(e3, e1), name="reference tangent 2")
    local_basis = np.column_stack((e1, e2, e3))
    green_local = local_basis.T @ green @ local_basis

    # Compare director gradients after removing the rigid rotation carried by F.
    polar_u, _, polar_vt = np.linalg.svd(deformation)
    rigid_part = polar_u @ polar_vt
    if np.linalg.det(rigid_part) < 0.0:
        polar_u[:, -1] *= -1.0
        rigid_part = polar_u @ polar_vt
    gradient_change = current_gradient - rigid_part @ reference_gradient

    return ShellPointKinematics(
        deformation_gradient=deformation,
        green_lagrange=green,
        green_lagrange_local=green_local,
        membrane_strain=np.array(
            [green_local[0, 0], green_local[1, 1], 2.0 * green_local[0, 1]],
        ),
        transverse_shear_strain=np.array(
            [2.0 * green_local[0, 2], 2.0 * green_local[1, 2]],
        ),
        thickness_strain=float(green_local[2, 2]),
        reference_area_jacobian=reference_area,
        current_area_jacobian=current_area,
        reference_signed_area_jacobian=reference_signed_area,
        current_signed_area_jacobian=current_signed_area,
        deformation_jacobian=deformation_jacobian,
        director_norm_error=current_director_norm_error,
        director_interpolation_norm_before_normalisation=current_interpolation_norm,
        director_gradient_change_norm=float(np.linalg.norm(gradient_change)),
    )
