"""Q4 shape functions, 2x2 Gauss rule, Jacobian mapping and raw strains.

Formulas follow ADR-002 and the core-algorithm Q4 interpolation section.
This module does not assemble stiffness or assumed-shear tying.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from reused_cores.shell3d_linear.constants import (
    DOF_PER_NODE_LOCAL,
    GAUSS_2X2_ABSCISSA,
    GAUSS_2X2_POINTS,
    GAUSS_POINT_IDS,
    JHAT_ERROR,
    NODES_PER_Q4,
    Q4_NATURAL_NODES,
)
from reused_cores.shell3d_linear.kinematics import (
    build_membrane_bending_b,
    build_raw_shear_b,
    evaluate_membrane_bending_strains,
    evaluate_shear_strain,
)
from reused_cores.shell3d_linear.types import Vec2


class Q4MappingError(ValueError):
    """Raised when a Q4 natural-to-local map is not usable."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        det_j: float,
        xi: float,
        eta: float,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.det_j = det_j
        self.xi = xi
        self.eta = eta


@dataclass(frozen=True, slots=True)
class GaussSample:
    point_id: str
    natural: Vec2
    weight: float


@dataclass(frozen=True, slots=True)
class ShapeFunctions:
    n: tuple[float, float, float, float]
    d_dxi: tuple[float, float, float, float]
    d_deta: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class JacobianMap:
    """Maps natural derivatives to the local (x', y') plane.

    ``j`` stores rows ``[dx/dξ, dy/dξ]`` and ``[dx/dη, dy/dη]``, so
    ``[dN/dξ, dN/dη]^T = j [dN/dx', dN/dy']^T``.
    """

    j: tuple[Vec2, Vec2]
    det_j: float
    j_inv: tuple[Vec2, Vec2]
    d_dx: tuple[float, float, float, float]
    d_dy: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class MappedGaussPoint:
    point_id: str
    natural: Vec2
    local_xy: Vec2
    weight: float
    shape: ShapeFunctions
    jacobian: JacobianMap


@dataclass(frozen=True, slots=True)
class RawStrains:
    membrane: tuple[float, float, float]
    curvature: tuple[float, float, float]
    shear: tuple[float, float]


def q4_shape(xi: float, eta: float) -> ShapeFunctions:
    n = []
    d_dxi = []
    d_deta = []
    for xi_i, eta_i in Q4_NATURAL_NODES:
        n.append(0.25 * (1.0 + xi_i * xi) * (1.0 + eta_i * eta))
        d_dxi.append(0.25 * xi_i * (1.0 + eta_i * eta))
        d_deta.append(0.25 * eta_i * (1.0 + xi_i * xi))
    return ShapeFunctions(
        n=(n[0], n[1], n[2], n[3]),
        d_dxi=(d_dxi[0], d_dxi[1], d_dxi[2], d_dxi[3]),
        d_deta=(d_deta[0], d_deta[1], d_deta[2], d_deta[3]),
    )


def q4_natural_derivatives(xi: float, eta: float) -> tuple[list[float], list[float]]:
    shape = q4_shape(xi, eta)
    return list(shape.d_dxi), list(shape.d_deta)


def q4_gauss_2x2() -> tuple[GaussSample, GaussSample, GaussSample, GaussSample]:
    samples = []
    for point_id, (xi, eta) in zip(GAUSS_POINT_IDS, GAUSS_2X2_POINTS, strict=True):
        samples.append(GaussSample(point_id=point_id, natural=(xi, eta), weight=1.0))
    return (samples[0], samples[1], samples[2], samples[3])


def interpolate_scalar(n: Sequence[float], nodal: Sequence[float]) -> float:
    if len(n) != NODES_PER_Q4 or len(nodal) != NODES_PER_Q4:
        raise ValueError("Q4 interpolation requires 4 shape values and 4 nodal values")
    return sum(n[i] * nodal[i] for i in range(NODES_PER_Q4))


def interpolate_physical_xy(
    local_xy: Sequence[tuple[float, float]],
    n: Sequence[float],
) -> Vec2:
    if len(local_xy) != NODES_PER_Q4:
        raise ValueError("Q4 mapping requires 4 local (x', y') nodes")
    return (
        interpolate_scalar(n, [point[0] for point in local_xy]),
        interpolate_scalar(n, [point[1] for point in local_xy]),
    )


def _invert_2x2(j: tuple[Vec2, Vec2], det_j: float) -> tuple[Vec2, Vec2]:
    return (
        (j[1][1] / det_j, -j[0][1] / det_j),
        (-j[1][0] / det_j, j[0][0] / det_j),
    )


def map_q4_jacobian(
    local_xy: Sequence[tuple[float, float]],
    xi: float,
    eta: float,
    *,
    l_char: float | None = None,
    reject_non_positive: bool = True,
) -> JacobianMap:
    if len(local_xy) != NODES_PER_Q4:
        raise ValueError("Q4 Jacobian requires 4 local (x', y') nodes")
    shape = q4_shape(xi, eta)
    dx_dxi = sum(shape.d_dxi[i] * local_xy[i][0] for i in range(NODES_PER_Q4))
    dy_dxi = sum(shape.d_dxi[i] * local_xy[i][1] for i in range(NODES_PER_Q4))
    dx_deta = sum(shape.d_deta[i] * local_xy[i][0] for i in range(NODES_PER_Q4))
    dy_deta = sum(shape.d_deta[i] * local_xy[i][1] for i in range(NODES_PER_Q4))
    j = ((dx_dxi, dy_dxi), (dx_deta, dy_deta))
    det_j = dx_dxi * dy_deta - dx_deta * dy_dxi
    if reject_non_positive and det_j <= 0.0:
        raise Q4MappingError(
            "SHELL-GEO-E003",
            f"det(J)={det_j} is not positive at (xi, eta)=({xi}, {eta})",
            det_j=det_j,
            xi=xi,
            eta=eta,
        )
    if (
        reject_non_positive
        and l_char is not None
        and l_char > 0.0
        and det_j / (l_char * l_char) <= JHAT_ERROR
    ):
        raise Q4MappingError(
            "SHELL-GEO-E004",
            f"normalized det(J)={det_j / (l_char * l_char)} is at or below {JHAT_ERROR}",
            det_j=det_j,
            xi=xi,
            eta=eta,
        )
    if det_j == 0.0:
        raise Q4MappingError(
            "SHELL-GEO-E003",
            "det(J) is zero; Cartesian derivatives are undefined",
            det_j=det_j,
            xi=xi,
            eta=eta,
        )
    j_inv = _invert_2x2(j, det_j)
    d_dx = []
    d_dy = []
    for i in range(NODES_PER_Q4):
        d_dx.append(j_inv[0][0] * shape.d_dxi[i] + j_inv[0][1] * shape.d_deta[i])
        d_dy.append(j_inv[1][0] * shape.d_dxi[i] + j_inv[1][1] * shape.d_deta[i])
    return JacobianMap(
        j=j,
        det_j=det_j,
        j_inv=j_inv,
        d_dx=(d_dx[0], d_dx[1], d_dx[2], d_dx[3]),
        d_dy=(d_dy[0], d_dy[1], d_dy[2], d_dy[3]),
    )


def q4_det_jacobian(local_xy: Sequence[tuple[float, float]], xi: float, eta: float) -> float:
    mapped = map_q4_jacobian(local_xy, xi, eta, reject_non_positive=False)
    return mapped.det_j


def map_q4_gauss_points(
    local_xy: Sequence[tuple[float, float]],
    *,
    l_char: float | None = None,
    reject_non_positive: bool = True,
) -> tuple[MappedGaussPoint, MappedGaussPoint, MappedGaussPoint, MappedGaussPoint]:
    points: list[MappedGaussPoint] = []
    for sample in q4_gauss_2x2():
        shape = q4_shape(*sample.natural)
        jacobian = map_q4_jacobian(
            local_xy,
            sample.natural[0],
            sample.natural[1],
            l_char=l_char,
            reject_non_positive=reject_non_positive,
        )
        points.append(
            MappedGaussPoint(
                point_id=sample.point_id,
                natural=sample.natural,
                local_xy=interpolate_physical_xy(local_xy, shape.n),
                weight=sample.weight,
                shape=shape,
                jacobian=jacobian,
            )
        )
    return (points[0], points[1], points[2], points[3])


def check_q4_operator_sizes(
    shape: ShapeFunctions,
    jacobian: JacobianMap,
    local_dofs: Sequence[float] | None = None,
) -> None:
    if len(shape.n) != NODES_PER_Q4:
        raise ValueError(f"N must have {NODES_PER_Q4} entries")
    if len(shape.d_dxi) != NODES_PER_Q4 or len(shape.d_deta) != NODES_PER_Q4:
        raise ValueError("natural derivatives must have 4 entries each")
    if len(jacobian.j) != 2 or any(len(row) != 2 for row in jacobian.j):
        raise ValueError("J must be 2x2")
    if len(jacobian.j_inv) != 2 or any(len(row) != 2 for row in jacobian.j_inv):
        raise ValueError("J inverse must be 2x2")
    if len(jacobian.d_dx) != NODES_PER_Q4 or len(jacobian.d_dy) != NODES_PER_Q4:
        raise ValueError("Cartesian derivatives must have 4 entries each")
    if local_dofs is not None and len(local_dofs) != NODES_PER_Q4 * DOF_PER_NODE_LOCAL:
        raise ValueError("local element DOFs must have length 20")


def pack_local_element_dofs(
    nodal: Sequence[Sequence[float]],
) -> tuple[float, ...]:
    if len(nodal) != NODES_PER_Q4:
        raise ValueError("local element DOFs require 4 nodes")
    values: list[float] = []
    for node in nodal:
        if len(node) != DOF_PER_NODE_LOCAL:
            raise ValueError("each local node must have 5 DOFs")
        values.extend(float(value) for value in node)
    return tuple(values)


def raw_generalized_strains(
    shape: ShapeFunctions,
    jacobian: JacobianMap,
    local_dofs: Sequence[float],
) -> RawStrains:
    """Evaluate raw Reissner-Mindlin strains from interpolated local 5-DOF fields.

    Shear here is the unmodified Q4 operator, used for V00 rigid-body checks.
    Production QLLL locking control is implemented in ``shell_core.shear``.
    """

    check_q4_operator_sizes(shape, jacobian, local_dofs)
    membrane_bending = evaluate_membrane_bending_strains(
        build_membrane_bending_b(jacobian),
        local_dofs,
    )
    shear = evaluate_shear_strain(build_raw_shear_b(shape, jacobian), local_dofs)
    return RawStrains(
        membrane=membrane_bending.membrane,
        curvature=membrane_bending.curvature,
        shear=shear,
    )


def integrate_scalar(values: Sequence[float], mapped: Sequence[MappedGaussPoint]) -> float:
    if len(values) != len(mapped):
        raise ValueError("integrand length must match the Gauss-point list")
    total = 0.0
    for value, point in zip(values, mapped, strict=True):
        total += value * point.jacobian.det_j * point.weight
    return total


# Keep the frozen 2x2 abscissa visible for tests that compare the table itself.
GAUSS_ABSCISSA = GAUSS_2X2_ABSCISSA
