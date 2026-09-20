"""P4 QLLL assumed transverse shear and verification-only raw Q4 shear.

The implementation follows the canonical four-edge-midpoint tying construction:
raw Cartesian shear is transformed to natural covariant components at the tying
points, interpolated in the appropriate natural direction, and transformed back
at each 2x2 Gauss point. All matrices use local nodal order
``[u', v', w', theta_x', theta_y']``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from reused_cores.shell3d_linear.constants import (
    DOF_PER_NODE_LOCAL,
    NODES_PER_Q4,
    PRODUCTION_SHEAR,
    VERIFICATION_SHEAR,
)
from reused_cores.shell3d_linear.constitutive import ConstitutiveBlocks, shear_resultant
from reused_cores.shell3d_linear.geometry import ElementGeometry
from reused_cores.shell3d_linear.kinematics import (
    Matrix2x20,
    ShearB,
    build_raw_shear_b,
    evaluate_shear_strain,
)
from reused_cores.shell3d_linear.membrane_bending import Matrix20, build_membrane_bending_operator
from reused_cores.shell3d_linear.q4 import JacobianMap, map_q4_jacobian, q4_shape
from reused_cores.shell3d_linear.types import Vec2

LOCAL_DOF_COUNT = NODES_PER_Q4 * DOF_PER_NODE_LOCAL
ShearFormulation = Literal["qlll_assumed_strain", "raw_q4_full"]


@dataclass(frozen=True, slots=True)
class QLLLTyingB:
    """Covariant natural-shear rows sampled at the four edge midpoints."""

    gamma_xi_bottom: tuple[float, ...]
    gamma_xi_top: tuple[float, ...]
    gamma_eta_right: tuple[float, ...]
    gamma_eta_left: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ShearOperator:
    """Local 20x20 transverse-shear stiffness for one explicit formulation."""

    k_shear: Matrix20
    area: float
    formulation: ShearFormulation


@dataclass(frozen=True, slots=True)
class LocalShellOperator:
    """P4 local physical operator consumed by the P5 global element builder."""

    k_membrane: Matrix20
    k_bending: Matrix20
    k_shear: Matrix20
    k_local: Matrix20
    area: float
    shear_formulation: ShearFormulation


@dataclass(frozen=True, slots=True)
class ShearEnergy:
    shear: float


@dataclass(frozen=True, slots=True)
class LocalShellEnergy:
    membrane: float
    bending: float
    shear: float
    total: float


@dataclass(frozen=True, slots=True)
class ShearPoint:
    point_id: str
    natural: Vec2
    local_xy: Vec2
    det_j: float
    shear_strain: Vec2
    shear_resultant: Vec2
    shear_energy_density: float


@dataclass(frozen=True, slots=True)
class ShearResponse:
    gauss_points: tuple[ShearPoint, ShearPoint, ShearPoint, ShearPoint]
    energy: ShearEnergy
    formulation: ShearFormulation


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite float")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite float") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite float")
    return number


def _local_dofs(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != LOCAL_DOF_COUNT:
        raise ValueError(f"local_dofs must contain {LOCAL_DOF_COUNT} values")
    return tuple(_finite(f"local_dofs[{index}]", value) for index, value in enumerate(values))


def _validate_formulation(formulation: str) -> ShearFormulation:
    if formulation == PRODUCTION_SHEAR:
        return "qlll_assumed_strain"
    if formulation == VERIFICATION_SHEAR:
        return "raw_q4_full"
    raise ValueError(
        "shear formulation must be 'qlll_assumed_strain' or verification-only 'raw_q4_full'"
    )


def _covariant_row(b_matrix: ShearB, jacobian_row: Vec2) -> tuple[float, ...]:
    return tuple(
        jacobian_row[0] * b_matrix.shear[0][column] + jacobian_row[1] * b_matrix.shear[1][column]
        for column in range(LOCAL_DOF_COUNT)
    )


def _tying_covariant_row(
    local_xy: Sequence[tuple[float, float]],
    xi: float,
    eta: float,
    natural_component: int,
    *,
    l_char: float | None,
) -> tuple[float, ...]:
    shape = q4_shape(xi, eta)
    jacobian = map_q4_jacobian(local_xy, xi, eta, l_char=l_char)
    raw = build_raw_shear_b(shape, jacobian)
    return _covariant_row(raw, jacobian.j[natural_component])


def build_qlll_tying_b(
    local_xy: Sequence[tuple[float, float]],
    *,
    l_char: float | None = None,
) -> QLLLTyingB:
    """Sample the four QLLL covariant shear constraints at edge midpoints."""

    return QLLLTyingB(
        gamma_xi_bottom=_tying_covariant_row(local_xy, 0.0, -1.0, 0, l_char=l_char),
        gamma_xi_top=_tying_covariant_row(local_xy, 0.0, 1.0, 0, l_char=l_char),
        gamma_eta_right=_tying_covariant_row(local_xy, 1.0, 0.0, 1, l_char=l_char),
        gamma_eta_left=_tying_covariant_row(local_xy, -1.0, 0.0, 1, l_char=l_char),
    )


def interpolate_qlll_shear_b(
    tying: QLLLTyingB,
    xi: float,
    eta: float,
    jacobian: JacobianMap,
) -> ShearB:
    """Interpolate covariant tying rows and return Cartesian ``B_s_tilde``."""

    xi_value = _finite("xi", xi)
    eta_value = _finite("eta", eta)
    gamma_xi = tuple(
        0.5
        * (
            (1.0 - eta_value) * tying.gamma_xi_bottom[column]
            + (1.0 + eta_value) * tying.gamma_xi_top[column]
        )
        for column in range(LOCAL_DOF_COUNT)
    )
    gamma_eta = tuple(
        0.5
        * (
            (1.0 + xi_value) * tying.gamma_eta_right[column]
            + (1.0 - xi_value) * tying.gamma_eta_left[column]
        )
        for column in range(LOCAL_DOF_COUNT)
    )
    cartesian: Matrix2x20 = (
        tuple(
            jacobian.j_inv[0][0] * gamma_xi[column] + jacobian.j_inv[0][1] * gamma_eta[column]
            for column in range(LOCAL_DOF_COUNT)
        ),
        tuple(
            jacobian.j_inv[1][0] * gamma_xi[column] + jacobian.j_inv[1][1] * gamma_eta[column]
            for column in range(LOCAL_DOF_COUNT)
        ),
    )
    return ShearB(shear=cartesian)


def build_qlll_shear_b(
    local_xy: Sequence[tuple[float, float]],
    xi: float,
    eta: float,
    *,
    l_char: float | None = None,
) -> ShearB:
    """Convenience builder for one QLLL assumed-shear evaluation point."""

    jacobian = map_q4_jacobian(local_xy, xi, eta, l_char=l_char)
    tying = build_qlll_tying_b(local_xy, l_char=l_char)
    return interpolate_qlll_shear_b(tying, xi, eta, jacobian)


def _zero_matrix() -> list[list[float]]:
    return [[0.0] * LOCAL_DOF_COUNT for _ in range(LOCAL_DOF_COUNT)]


def _freeze_matrix(matrix: Sequence[Sequence[float]]) -> Matrix20:
    if len(matrix) != LOCAL_DOF_COUNT or any(len(row) != LOCAL_DOF_COUNT for row in matrix):
        raise ValueError(f"local stiffness matrix must be {LOCAL_DOF_COUNT}x{LOCAL_DOF_COUNT}")
    return tuple(tuple(float(value) for value in row) for row in matrix)


def _add_bt_db(
    target: list[list[float]],
    b_matrix: Matrix2x20,
    constitutive: tuple[Vec2, Vec2],
    factor: float,
) -> None:
    db = [[0.0] * LOCAL_DOF_COUNT for _ in range(2)]
    for row in range(2):
        for column in range(LOCAL_DOF_COUNT):
            db[row][column] = sum(
                constitutive[row][inner] * b_matrix[inner][column] for inner in range(2)
            )
    for left in range(LOCAL_DOF_COUNT):
        for right in range(LOCAL_DOF_COUNT):
            target[left][right] += factor * sum(
                b_matrix[inner][left] * db[inner][right] for inner in range(2)
            )


def _add_matrices(*matrices: Matrix20) -> Matrix20:
    return tuple(
        tuple(sum(matrix[row][column] for matrix in matrices) for column in range(LOCAL_DOF_COUNT))
        for row in range(LOCAL_DOF_COUNT)
    )


def _quadratic(matrix: Matrix20, vector: Sequence[float]) -> float:
    values = _local_dofs(vector)
    return sum(
        values[row] * sum(matrix[row][column] * values[column] for column in range(LOCAL_DOF_COUNT))
        for row in range(LOCAL_DOF_COUNT)
    )


def _local_xy(geometry: ElementGeometry) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    return tuple((item[0], item[1]) for item in geometry.local_coordinates)  # type: ignore[return-value]


def _point_b(
    formulation: ShearFormulation,
    point_shape,
    point_jacobian: JacobianMap,
    natural: Vec2,
    tying: QLLLTyingB | None,
) -> ShearB:
    if formulation == "raw_q4_full":
        return build_raw_shear_b(point_shape, point_jacobian)
    if tying is None:
        raise ValueError("QLLL shear requires four tying-point rows")
    return interpolate_qlll_shear_b(tying, natural[0], natural[1], point_jacobian)


def build_shear_operator(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    *,
    formulation: str = PRODUCTION_SHEAR,
) -> ShearOperator:
    """Integrate P4 shear stiffness with the frozen 2x2 Gauss rule.

    ``qlll_assumed_strain`` is the production default. ``raw_q4_full`` is
    exposed only as the P0-approved locking-failure comparison.
    """

    selected = _validate_formulation(formulation)
    tying = (
        build_qlll_tying_b(_local_xy(geometry), l_char=geometry.l_char)
        if selected == "qlll_assumed_strain"
        else None
    )
    shear = _zero_matrix()
    area = 0.0
    for point in geometry.gauss_points:
        factor = point.jacobian.det_j * point.weight
        if factor <= 0.0:
            raise ValueError("shear integration requires positive det(J) and weight")
        b_matrix = _point_b(
            selected,
            point.shape,
            point.jacobian,
            point.natural,
            tying,
        )
        _add_bt_db(shear, b_matrix.shear, constitutive.d_s, factor)
        area += factor
    return ShearOperator(
        k_shear=_freeze_matrix(shear),
        area=area,
        formulation=selected,
    )


def build_local_shell_operator(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    *,
    shear_formulation: str = PRODUCTION_SHEAR,
) -> LocalShellOperator:
    """Build ``K_m + K_b + K_s`` in local 20-DOF space.

    This remains the local physical part of the P5 operator. It contains no
    drilling stabilization, loads, assembly or solve state; use
    ``build_global_shell_operator`` for the transformed 24-DOF element matrix.
    """

    membrane_bending = build_membrane_bending_operator(geometry, constitutive)
    shear = build_shear_operator(
        geometry,
        constitutive,
        formulation=shear_formulation,
    )
    return LocalShellOperator(
        k_membrane=membrane_bending.k_membrane,
        k_bending=membrane_bending.k_bending,
        k_shear=shear.k_shear,
        k_local=_add_matrices(
            membrane_bending.k_membrane,
            membrane_bending.k_bending,
            shear.k_shear,
        ),
        area=membrane_bending.area,
        shear_formulation=shear.formulation,
    )


def shear_energy(operator: ShearOperator, local_dofs: Sequence[float]) -> ShearEnergy:
    return ShearEnergy(shear=0.5 * _quadratic(operator.k_shear, local_dofs))


def local_shell_energy(
    operator: LocalShellOperator,
    local_dofs: Sequence[float],
) -> LocalShellEnergy:
    membrane = 0.5 * _quadratic(operator.k_membrane, local_dofs)
    bending = 0.5 * _quadratic(operator.k_bending, local_dofs)
    shear = 0.5 * _quadratic(operator.k_shear, local_dofs)
    return LocalShellEnergy(
        membrane=membrane,
        bending=bending,
        shear=shear,
        total=membrane + bending + shear,
    )


def evaluate_shear_response(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    local_dofs: Sequence[float],
    *,
    formulation: str = PRODUCTION_SHEAR,
) -> ShearResponse:
    """Return assumed or raw shear strain, ``Q`` and energy at Gauss points."""

    values = _local_dofs(local_dofs)
    selected = _validate_formulation(formulation)
    tying = (
        build_qlll_tying_b(_local_xy(geometry), l_char=geometry.l_char)
        if selected == "qlll_assumed_strain"
        else None
    )
    points: list[ShearPoint] = []
    integrated_energy = 0.0
    for point in geometry.gauss_points:
        b_matrix = _point_b(
            selected,
            point.shape,
            point.jacobian,
            point.natural,
            tying,
        )
        strain = evaluate_shear_strain(b_matrix, values)
        resultant = shear_resultant(constitutive, strain)
        density = 0.5 * (strain[0] * resultant[0] + strain[1] * resultant[1])
        factor = point.jacobian.det_j * point.weight
        integrated_energy += density * factor
        points.append(
            ShearPoint(
                point_id=point.point_id,
                natural=point.natural,
                local_xy=point.local_xy,
                det_j=point.jacobian.det_j,
                shear_strain=strain,
                shear_resultant=resultant,
                shear_energy_density=density,
            )
        )
    if len(points) != 4:
        raise ValueError("P4 Q4 shear response requires exactly four Gauss points")
    return ShearResponse(
        gauss_points=(points[0], points[1], points[2], points[3]),
        energy=ShearEnergy(shear=integrated_energy),
        formulation=selected,
    )


__all__ = [
    "LocalShellEnergy",
    "LocalShellOperator",
    "QLLLTyingB",
    "ShearEnergy",
    "ShearFormulation",
    "ShearOperator",
    "ShearPoint",
    "ShearResponse",
    "build_local_shell_operator",
    "build_qlll_shear_b",
    "build_qlll_tying_b",
    "build_shear_operator",
    "evaluate_shear_response",
    "interpolate_qlll_shear_b",
    "local_shell_energy",
    "shear_energy",
]
