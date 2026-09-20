"""P5 continuum-consistent drilling stabilization and global element operator.

The stabilization penalizes only the difference between interpolated axial
drilling rotation and the in-plane continuum rotation,
``theta_z' - 0.5 * (v_,x' - u_,y')``. It therefore leaves exact rigid-body
rotation unpenalized while stabilizing the four nodal drilling components.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from reused_cores.shell3d_linear.constants import PRODUCTION_DRILLING, PRODUCTION_SHEAR
from reused_cores.shell3d_linear.constitutive import ConstitutiveBlocks
from reused_cores.shell3d_linear.geometry import ElementGeometry
from reused_cores.shell3d_linear.kinematics import CartesianShapeDerivatives, ShapeValues
from reused_cores.shell3d_linear.shear import (
    LocalShellOperator,
    ShearFormulation,
    build_local_shell_operator,
    local_shell_energy,
)
from reused_cores.shell3d_linear.transformation import (
    GLOBAL_DOF_COUNT,
    ElementTransform,
    Matrix24,
    build_element_transform,
    global_internal_force,
    global_to_local_dofs,
    transform_local_stiffness,
)
from reused_cores.shell3d_linear.types import Vec2

DrillingFormulation = Literal["continuum_consistent", "none"]


@dataclass(frozen=True, slots=True)
class DrillingB:
    """One-row drilling operators in augmented-local and global 24-DOF order."""

    augmented_local: tuple[float, ...]
    global_row: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DrillingOperator:
    k_drilling: Matrix24
    alpha_d: float
    stiffness_per_area: float
    area: float
    formulation: Literal["continuum_consistent"]


@dataclass(frozen=True, slots=True)
class GlobalShellOperator:
    """P5 element operator in four-node global 24-DOF order."""

    transform: ElementTransform
    local_operator: LocalShellOperator
    drilling_operator: DrillingOperator | None
    k_physical: Matrix24
    k_drilling: Matrix24
    k_global: Matrix24
    shear_formulation: ShearFormulation
    drilling_formulation: DrillingFormulation
    alpha_d: float | None


@dataclass(frozen=True, slots=True)
class DrillingEnergy:
    drilling: float


@dataclass(frozen=True, slots=True)
class GlobalShellEnergy:
    membrane: float
    bending: float
    shear: float
    drilling: float
    physical: float
    total: float


@dataclass(frozen=True, slots=True)
class DrillingPoint:
    point_id: str
    natural: Vec2
    mismatch: float
    energy_density: float


@dataclass(frozen=True, slots=True)
class DrillingResponse:
    gauss_points: tuple[DrillingPoint, DrillingPoint, DrillingPoint, DrillingPoint]
    energy: DrillingEnergy
    alpha_d: float


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


def _global_values(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != GLOBAL_DOF_COUNT:
        raise ValueError(f"global_dofs must contain {GLOBAL_DOF_COUNT} values")
    return tuple(_finite(f"global_dofs[{index}]", value) for index, value in enumerate(values))


def _positive_alpha(alpha_d: float) -> float:
    value = _finite("alpha_d", alpha_d)
    if value <= 0.0:
        raise ValueError("alpha_d must be greater than zero")
    return value


def _validate_drilling_formulation(formulation: str) -> DrillingFormulation:
    if formulation == PRODUCTION_DRILLING:
        return "continuum_consistent"
    if formulation == "none":
        return "none"
    raise ValueError(
        "drilling formulation must be 'continuum_consistent' or verification-only 'none'"
    )


def build_drilling_b(
    shape: ShapeValues,
    derivatives: CartesianShapeDerivatives,
    transform: ElementTransform,
) -> DrillingB:
    """Build ``theta_z' - 0.5(v_,x' - u_,y')`` at one point."""

    if len(shape.n) != 4 or len(derivatives.d_dx) != 4 or len(derivatives.d_dy) != 4:
        raise ValueError("drilling B requires four Q4 shape values and derivatives")
    local = [0.0] * GLOBAL_DOF_COUNT
    for node in range(4):
        base = 6 * node
        n = _finite(f"N[{node}]", shape.n[node])
        d_dx = _finite(f"dN_dx[{node}]", derivatives.d_dx[node])
        d_dy = _finite(f"dN_dy[{node}]", derivatives.d_dy[node])
        local[base] = 0.5 * d_dy
        local[base + 1] = -0.5 * d_dx
        local[base + 5] = n
    global_row = tuple(
        sum(
            local[row] * transform.augmented_local_from_global[row][column]
            for row in range(GLOBAL_DOF_COUNT)
        )
        for column in range(GLOBAL_DOF_COUNT)
    )
    return DrillingB(augmented_local=tuple(local), global_row=global_row)


def _zero_matrix() -> Matrix24:
    return tuple(tuple(0.0 for _ in range(GLOBAL_DOF_COUNT)) for _ in range(GLOBAL_DOF_COUNT))


def _add_matrices(left: Matrix24, right: Matrix24) -> Matrix24:
    return tuple(
        tuple(left[row][column] + right[row][column] for column in range(GLOBAL_DOF_COUNT))
        for row in range(GLOBAL_DOF_COUNT)
    )


def build_drilling_operator(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    alpha_d: float,
    *,
    transform: ElementTransform | None = None,
) -> DrillingOperator:
    """Integrate the P0 continuum-consistent drilling stiffness with 2x2 Gauss."""

    alpha = _positive_alpha(alpha_d)
    element_transform = transform or build_element_transform(geometry.basis)
    stiffness_per_area = alpha * constitutive.young_modulus * constitutive.thickness
    matrix = [[0.0] * GLOBAL_DOF_COUNT for _ in range(GLOBAL_DOF_COUNT)]
    area = 0.0
    for point in geometry.gauss_points:
        factor = point.jacobian.det_j * point.weight
        if factor <= 0.0:
            raise ValueError("drilling integration requires positive det(J) and weight")
        b_matrix = build_drilling_b(point.shape, point.jacobian, element_transform).global_row
        weighted = stiffness_per_area * factor
        for row in range(GLOBAL_DOF_COUNT):
            for column in range(GLOBAL_DOF_COUNT):
                matrix[row][column] += weighted * b_matrix[row] * b_matrix[column]
        area += factor
    return DrillingOperator(
        k_drilling=tuple(tuple(value for value in row) for row in matrix),
        alpha_d=alpha,
        stiffness_per_area=stiffness_per_area,
        area=area,
        formulation="continuum_consistent",
    )


def build_global_shell_operator(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    *,
    alpha_d: float | None,
    shear_formulation: str = PRODUCTION_SHEAR,
    drilling_formulation: str = PRODUCTION_DRILLING,
) -> GlobalShellOperator:
    """Build the P5 global 24x24 element operator.

    Production requires ``continuum_consistent`` and an explicit positive
    ``alpha_d``. ``none`` is retained only for P0 verification comparisons and
    requires ``alpha_d=None``.
    """

    selected = _validate_drilling_formulation(drilling_formulation)
    if selected == "continuum_consistent" and alpha_d is None:
        raise ValueError("continuum_consistent drilling requires explicit alpha_d")
    if selected == "none" and alpha_d is not None:
        raise ValueError("verification drilling='none' requires alpha_d=None")
    transform = build_element_transform(geometry.basis)
    local = build_local_shell_operator(
        geometry,
        constitutive,
        shear_formulation=shear_formulation,
    )
    physical = transform_local_stiffness(transform, local.k_local)
    drilling = (
        build_drilling_operator(geometry, constitutive, alpha_d, transform=transform)
        if alpha_d is not None
        else None
    )
    k_drilling = drilling.k_drilling if drilling is not None else _zero_matrix()
    return GlobalShellOperator(
        transform=transform,
        local_operator=local,
        drilling_operator=drilling,
        k_physical=physical,
        k_drilling=k_drilling,
        k_global=_add_matrices(physical, k_drilling),
        shear_formulation=local.shear_formulation,
        drilling_formulation=selected,
        alpha_d=drilling.alpha_d if drilling is not None else None,
    )


def drilling_energy(
    operator: DrillingOperator,
    global_dofs: Sequence[float],
) -> DrillingEnergy:
    values = _global_values(global_dofs)
    force = global_internal_force(operator.k_drilling, values)
    return DrillingEnergy(
        drilling=0.5 * sum(values[index] * force[index] for index in range(GLOBAL_DOF_COUNT))
    )


def evaluate_drilling_response(
    geometry: ElementGeometry,
    constitutive: ConstitutiveBlocks,
    alpha_d: float,
    global_dofs: Sequence[float],
    *,
    transform: ElementTransform | None = None,
) -> DrillingResponse:
    values = _global_values(global_dofs)
    alpha = _positive_alpha(alpha_d)
    element_transform = transform or build_element_transform(geometry.basis)
    stiffness_per_area = alpha * constitutive.young_modulus * constitutive.thickness
    points: list[DrillingPoint] = []
    energy = 0.0
    for point in geometry.gauss_points:
        row = build_drilling_b(point.shape, point.jacobian, element_transform).global_row
        mismatch = sum(row[column] * values[column] for column in range(GLOBAL_DOF_COUNT))
        density = 0.5 * stiffness_per_area * mismatch * mismatch
        energy += density * point.jacobian.det_j * point.weight
        points.append(
            DrillingPoint(
                point_id=point.point_id,
                natural=point.natural,
                mismatch=mismatch,
                energy_density=density,
            )
        )
    if len(points) != 4:
        raise ValueError("P5 drilling response requires exactly four Gauss points")
    return DrillingResponse(
        gauss_points=(points[0], points[1], points[2], points[3]),
        energy=DrillingEnergy(drilling=energy),
        alpha_d=alpha,
    )


def global_shell_energy(
    operator: GlobalShellOperator,
    global_dofs: Sequence[float],
) -> GlobalShellEnergy:
    values = _global_values(global_dofs)
    local_dofs = global_to_local_dofs(operator.transform, values)
    physical = local_shell_energy(operator.local_operator, local_dofs)
    drilling = (
        drilling_energy(operator.drilling_operator, values).drilling
        if operator.drilling_operator is not None
        else 0.0
    )
    physical_total = physical.total
    return GlobalShellEnergy(
        membrane=physical.membrane,
        bending=physical.bending,
        shear=physical.shear,
        drilling=drilling,
        physical=physical_total,
        total=physical_total + drilling,
    )


def global_shell_internal_force(
    operator: GlobalShellOperator,
    global_dofs: Sequence[float],
) -> tuple[float, ...]:
    return global_internal_force(operator.k_global, global_dofs)


__all__ = [
    "DrillingB",
    "DrillingEnergy",
    "DrillingFormulation",
    "DrillingOperator",
    "DrillingPoint",
    "DrillingResponse",
    "GlobalShellEnergy",
    "GlobalShellOperator",
    "build_drilling_b",
    "build_drilling_operator",
    "build_global_shell_operator",
    "drilling_energy",
    "evaluate_drilling_response",
    "global_shell_energy",
    "global_shell_internal_force",
]
