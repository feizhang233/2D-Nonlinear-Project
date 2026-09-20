"""P3-P4 kinematics for the local Q4 5-DOF field."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from reused_cores.shell3d_linear.constants import DOF_PER_NODE_LOCAL, NODES_PER_Q4
from reused_cores.shell3d_linear.types import Vec3

Matrix3x20 = tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
Matrix2x20 = tuple[tuple[float, ...], tuple[float, ...]]


class CartesianShapeDerivatives(Protocol):
    d_dx: Sequence[float]
    d_dy: Sequence[float]


class ShapeValues(Protocol):
    n: Sequence[float]


@dataclass(frozen=True, slots=True)
class MembraneBendingB:
    membrane: Matrix3x20
    bending: Matrix3x20


@dataclass(frozen=True, slots=True)
class MembraneBendingStrains:
    membrane: Vec3
    curvature: Vec3


@dataclass(frozen=True, slots=True)
class ShearB:
    """Raw or assumed transverse-shear matrix in local 20-DOF order."""

    shear: Matrix2x20


def _finite_values(name: str, values: Sequence[float], expected: int) -> tuple[float, ...]:
    if len(values) != expected:
        raise ValueError(f"{name} must contain {expected} values")
    converted: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool):
            raise ValueError(f"{name}[{index}] must be a finite float")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name}[{index}] must be a finite float") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name}[{index}] must be a finite float")
        converted.append(number)
    return tuple(converted)


def _mat_vec(matrix: Matrix3x20, vector: Sequence[float]) -> Vec3:
    return tuple(
        sum(matrix[row][column] * vector[column] for column in range(len(vector)))
        for row in range(3)
    )  # type: ignore[return-value]


def _mat2_vec(matrix: Matrix2x20, vector: Sequence[float]) -> tuple[float, float]:
    return (
        sum(matrix[0][column] * vector[column] for column in range(len(vector))),
        sum(matrix[1][column] * vector[column] for column in range(len(vector))),
    )


def build_membrane_bending_b(derivatives: CartesianShapeDerivatives) -> MembraneBendingB:
    """Build the frozen ``B_m`` and ``B_b`` matrices in local 20-DOF order."""

    d_dx = _finite_values("d_dx", derivatives.d_dx, NODES_PER_Q4)
    d_dy = _finite_values("d_dy", derivatives.d_dy, NODES_PER_Q4)
    membrane = [[0.0] * (NODES_PER_Q4 * DOF_PER_NODE_LOCAL) for _ in range(3)]
    bending = [[0.0] * (NODES_PER_Q4 * DOF_PER_NODE_LOCAL) for _ in range(3)]
    for node in range(NODES_PER_Q4):
        base = node * DOF_PER_NODE_LOCAL
        membrane[0][base] = d_dx[node]
        membrane[1][base + 1] = d_dy[node]
        membrane[2][base] = d_dy[node]
        membrane[2][base + 1] = d_dx[node]

        bending[0][base + 3] = d_dx[node]
        bending[1][base + 4] = d_dy[node]
        bending[2][base + 3] = d_dy[node]
        bending[2][base + 4] = d_dx[node]

    return MembraneBendingB(
        membrane=(tuple(membrane[0]), tuple(membrane[1]), tuple(membrane[2])),
        bending=(tuple(bending[0]), tuple(bending[1]), tuple(bending[2])),
    )


def evaluate_membrane_bending_strains(
    b_matrix: MembraneBendingB,
    local_dofs: Sequence[float],
) -> MembraneBendingStrains:
    values = _finite_values(
        "local_dofs",
        local_dofs,
        NODES_PER_Q4 * DOF_PER_NODE_LOCAL,
    )
    return MembraneBendingStrains(
        membrane=_mat_vec(b_matrix.membrane, values),
        curvature=_mat_vec(b_matrix.bending, values),
    )


def build_raw_shear_b(
    shape: ShapeValues,
    derivatives: CartesianShapeDerivatives,
) -> ShearB:
    """Build the verification-only full-interpolation ``B_s`` matrix.

    The frozen convention is ``gamma_xz = w_,x - theta_x`` and
    ``gamma_yz = w_,y - theta_y``. Production P4 stiffness uses the QLLL
    assumed field assembled from this matrix at the four tying points.
    """

    n = _finite_values("N", shape.n, NODES_PER_Q4)
    d_dx = _finite_values("d_dx", derivatives.d_dx, NODES_PER_Q4)
    d_dy = _finite_values("d_dy", derivatives.d_dy, NODES_PER_Q4)
    shear = [[0.0] * (NODES_PER_Q4 * DOF_PER_NODE_LOCAL) for _ in range(2)]
    for node in range(NODES_PER_Q4):
        base = node * DOF_PER_NODE_LOCAL
        shear[0][base + 2] = d_dx[node]
        shear[0][base + 3] = -n[node]
        shear[1][base + 2] = d_dy[node]
        shear[1][base + 4] = -n[node]
    return ShearB(shear=(tuple(shear[0]), tuple(shear[1])))


def evaluate_shear_strain(
    b_matrix: ShearB,
    local_dofs: Sequence[float],
) -> tuple[float, float]:
    values = _finite_values(
        "local_dofs",
        local_dofs,
        NODES_PER_Q4 * DOF_PER_NODE_LOCAL,
    )
    return _mat2_vec(b_matrix.shear, values)


__all__ = [
    "CartesianShapeDerivatives",
    "Matrix2x20",
    "Matrix3x20",
    "MembraneBendingB",
    "MembraneBendingStrains",
    "ShapeValues",
    "ShearB",
    "build_membrane_bending_b",
    "build_raw_shear_b",
    "evaluate_membrane_bending_strains",
    "evaluate_shear_strain",
]
