"""P3 Q4 membrane/bending operators and Gauss-point response.

This module intentionally keeps the P3 membrane/bending boundary. P4 shear is
implemented in ``shell_core.shear`` and P5 transformation/drilling in their
own modules. Consistent loads and global assembly live in P6.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from reused_cores.shell3d_linear.constants import DOF_PER_NODE_LOCAL, NODES_PER_Q4
from reused_cores.shell3d_linear.constitutive import (
    ConstitutiveBlocks,
    SurfaceStresses,
    bending_resultant,
    generalized_energy_density,
    membrane_resultant,
    surface_stresses,
)
from reused_cores.shell3d_linear.geometry import ElementGeometry
from reused_cores.shell3d_linear.kinematics import (
    Matrix3x20,
    build_membrane_bending_b,
    evaluate_membrane_bending_strains,
)
from reused_cores.shell3d_linear.types import Vec2, Vec3

LOCAL_DOF_COUNT = NODES_PER_Q4 * DOF_PER_NODE_LOCAL
Matrix20 = tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class MembraneBendingOperator:
    """Local 20x20 membrane and bending stiffness blocks."""

    k_membrane: Matrix20
    k_bending: Matrix20
    k_local: Matrix20
    area: float


@dataclass(frozen=True, slots=True)
class MembraneBendingPoint:
    point_id: str
    natural: Vec2
    local_xy: Vec2
    det_j: float
    membrane_strain: Vec3
    curvature: Vec3
    membrane_resultant: Vec3
    bending_resultant: Vec3
    surface_stresses: SurfaceStresses
    membrane_energy_density: float
    bending_energy_density: float


@dataclass(frozen=True, slots=True)
class MembraneBendingEnergy:
    membrane: float
    bending: float
    total: float


@dataclass(frozen=True, slots=True)
class MembraneBendingResponse:
    gauss_points: tuple[
        MembraneBendingPoint,
        MembraneBendingPoint,
        MembraneBendingPoint,
        MembraneBendingPoint,
    ]
    energy: MembraneBendingEnergy


def _zero_matrix() -> list[list[float]]:
    return [[0.0] * LOCAL_DOF_COUNT for _ in range(LOCAL_DOF_COUNT)]


def _freeze_matrix(matrix: Sequence[Sequence[float]]) -> Matrix20:
    if len(matrix) != LOCAL_DOF_COUNT or any(len(row) != LOCAL_DOF_COUNT for row in matrix):
        raise ValueError(f"local stiffness matrix must be {LOCAL_DOF_COUNT}x{LOCAL_DOF_COUNT}")
    return tuple(tuple(float(value) for value in row) for row in matrix)


def _add_bt_db(
    target: list[list[float]],
    b_matrix: Matrix3x20,
    constitutive: tuple[Vec3, Vec3, Vec3],
    factor: float,
) -> None:
    db = [[0.0] * LOCAL_DOF_COUNT for _ in range(3)]
    for row in range(3):
        for column in range(LOCAL_DOF_COUNT):
            db[row][column] = sum(
                constitutive[row][inner] * b_matrix[inner][column] for inner in range(3)
            )
    for left in range(LOCAL_DOF_COUNT):
        for right in range(LOCAL_DOF_COUNT):
            target[left][right] += factor * sum(
                b_matrix[inner][left] * db[inner][right] for inner in range(3)
            )


def _add_matrices(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]) -> Matrix20:
    return tuple(
        tuple(left[row][column] + right[row][column] for column in range(LOCAL_DOF_COUNT))
        for row in range(LOCAL_DOF_COUNT)
    )


def _quadratic(matrix: Matrix20, vector: Sequence[float]) -> float:
    if len(vector) != LOCAL_DOF_COUNT:
        raise ValueError(f"local_dofs must contain {LOCAL_DOF_COUNT} values")
    return sum(
        vector[row] * sum(matrix[row][column] * vector[column] for column in range(LOCAL_DOF_COUNT))
        for row in range(LOCAL_DOF_COUNT)
    )


def build_membrane_bending_operator(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
) -> MembraneBendingOperator:
    """Integrate ``K_m`` and ``K_b`` with the frozen 2x2 Gauss rule."""

    membrane = _zero_matrix()
    bending = _zero_matrix()
    area = 0.0
    for point in geometry.gauss_points:
        factor = point.jacobian.det_j * point.weight
        if factor <= 0.0:
            raise ValueError("membrane/bending integration requires positive det(J) and weight")
        b_matrix = build_membrane_bending_b(point.jacobian)
        _add_bt_db(membrane, b_matrix.membrane, constitutive.d_m, factor)
        _add_bt_db(bending, b_matrix.bending, constitutive.d_b, factor)
        area += factor
    k_membrane = _freeze_matrix(membrane)
    k_bending = _freeze_matrix(bending)
    return MembraneBendingOperator(
        k_membrane=k_membrane,
        k_bending=k_bending,
        k_local=_add_matrices(k_membrane, k_bending),
        area=area,
    )


def membrane_bending_energy(
    operator: MembraneBendingOperator,
    local_dofs: Sequence[float],
) -> MembraneBendingEnergy:
    membrane = 0.5 * _quadratic(operator.k_membrane, local_dofs)
    bending = 0.5 * _quadratic(operator.k_bending, local_dofs)
    return MembraneBendingEnergy(
        membrane=membrane,
        bending=bending,
        total=membrane + bending,
    )


def evaluate_membrane_bending_response(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    local_dofs: Sequence[float],
) -> MembraneBendingResponse:
    """Evaluate the P3 membrane/bending portion without shear recovery."""

    points: list[MembraneBendingPoint] = []
    membrane_energy = 0.0
    bending_energy = 0.0
    for point in geometry.gauss_points:
        b_matrix = build_membrane_bending_b(point.jacobian)
        strains = evaluate_membrane_bending_strains(b_matrix, local_dofs)
        result_n = membrane_resultant(constitutive, strains.membrane)
        result_m = bending_resultant(constitutive, strains.curvature)
        surfaces = surface_stresses(constitutive, strains.membrane, strains.curvature)
        density = generalized_energy_density(
            constitutive,
            strains.membrane,
            strains.curvature,
            (0.0, 0.0),
        )
        factor = point.jacobian.det_j * point.weight
        membrane_energy += density.membrane * factor
        bending_energy += density.bending * factor
        points.append(
            MembraneBendingPoint(
                point_id=point.point_id,
                natural=point.natural,
                local_xy=point.local_xy,
                det_j=point.jacobian.det_j,
                membrane_strain=strains.membrane,
                curvature=strains.curvature,
                membrane_resultant=result_n,
                bending_resultant=result_m,
                surface_stresses=surfaces,
                membrane_energy_density=density.membrane,
                bending_energy_density=density.bending,
            )
        )
    if len(points) != 4:
        raise ValueError("P3 Q4 response requires exactly four Gauss points")
    energy = MembraneBendingEnergy(
        membrane=membrane_energy,
        bending=bending_energy,
        total=membrane_energy + bending_energy,
    )
    return MembraneBendingResponse(
        gauss_points=(points[0], points[1], points[2], points[3]),
        energy=energy,
    )


__all__ = [
    "LOCAL_DOF_COUNT",
    "Matrix20",
    "MembraneBendingEnergy",
    "MembraneBendingOperator",
    "MembraneBendingPoint",
    "MembraneBendingResponse",
    "build_membrane_bending_operator",
    "evaluate_membrane_bending_response",
    "membrane_bending_energy",
]
