"""Flat-Q4 local basis, projection and geometry quality.

Formulas follow ADR-002 / ADR-006. Q4 interpolation lives in ``q4``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from reused_cores.shell3d_linear.constants import (
    COLLINEAR_AREA_RATIO,
    EDGE_RATIO_ERROR,
    JHAT_ERROR,
    Q4_LOCAL_EDGES,
    WARP_ERROR,
)
from reused_cores.shell3d_linear.q4 import (
    MappedGaussPoint,
    Q4MappingError,
    map_q4_gauss_points,
    q4_det_jacobian,
    q4_gauss_2x2,
)
from reused_cores.shell3d_linear.types import Mat3, Vec3


@dataclass(frozen=True, slots=True)
class LocalBasis:
    e_x: Vec3
    e_y: Vec3
    e_z: Vec3

    @property
    def lambda_rows(self) -> Mat3:
        return (self.e_x, self.e_y, self.e_z)

    def to_local(self, vector: Sequence[float]) -> Vec3:
        return (
            _dot(vector, self.e_x),
            _dot(vector, self.e_y),
            _dot(vector, self.e_z),
        )

    def director_slopes(self, omega_global: Sequence[float]) -> tuple[float, float]:
        theta_x = -_dot(self.e_y, omega_global)
        theta_y = _dot(self.e_x, omega_global)
        return (theta_x, theta_y)

    def gram_deviation(self) -> float:
        """||Λ Λ^T - I||_F."""

        lam = self.lambda_rows
        gram = tuple(
            tuple(sum(lam[i][k] * lam[j][k] for k in range(3)) for j in range(3)) for i in range(3)
        )
        deviation = 0.0
        for i in range(3):
            for j in range(3):
                value = gram[i][j] - (1.0 if i == j else 0.0)
                deviation += value * value
        return math.sqrt(deviation)

    def determinant(self) -> float:
        ex, ey, ez = self.e_x, self.e_y, self.e_z
        return (
            ex[0] * (ey[1] * ez[2] - ey[2] * ez[1])
            - ex[1] * (ey[0] * ez[2] - ey[2] * ez[0])
            + ex[2] * (ey[0] * ez[1] - ey[1] * ez[0])
        )


@dataclass(frozen=True, slots=True)
class ElementQuality:
    l_char: float
    local_basis: LocalBasis
    local_coordinates: tuple[Vec3, Vec3, Vec3, Vec3]
    r_warp: float
    r_edge: float
    det_j: tuple[float, float, float, float]
    r_j: float
    jhat_min: float
    shape: Literal["strictly_convex", "concave", "self_intersecting", "degenerate"]


@dataclass(frozen=True, slots=True)
class ElementGeometry:
    """Production geometry for one flat Q4. Built only when the map is usable."""

    basis: LocalBasis
    local_coordinates: tuple[Vec3, Vec3, Vec3, Vec3]
    l_char: float
    r_warp: float
    r_edge: float
    r_j: float
    jhat_min: float
    gauss_points: tuple[MappedGaussPoint, MappedGaussPoint, MappedGaussPoint, MappedGaussPoint]


def _sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Sequence[float]) -> Vec3 | None:
    magnitude = _norm(a)
    if magnitude == 0.0:
        return None
    return (a[0] / magnitude, a[1] / magnitude, a[2] / magnitude)


def pairwise_characteristic_length(points: Sequence[Sequence[float]]) -> float:
    longest = 0.0
    for i, left in enumerate(points):
        for right in points[i + 1 :]:
            longest = max(longest, _norm(_sub(left, right)))
    return longest


def build_local_basis(
    x1: Sequence[float], x2: Sequence[float], x4: Sequence[float]
) -> LocalBasis | None:
    e_x = _unit(_sub(x2, x1))
    if e_x is None:
        return None
    e_z = _unit(_cross(e_x, _sub(x4, x1)))
    if e_z is None:
        return None
    e_y = _cross(e_z, e_x)
    return LocalBasis(e_x=e_x, e_y=e_y, e_z=e_z)


def project_nodes(points: Sequence[Sequence[float]], basis: LocalBasis) -> tuple[Vec3, ...]:
    origin = points[0]
    projected: list[Vec3] = []
    for point in points:
        delta = _sub(point, origin)
        projected.append(
            (
                _dot(delta, basis.e_x),
                _dot(delta, basis.e_y),
                _dot(delta, basis.e_z),
            )
        )
    return tuple(projected)


def _cross2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _orient(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return _cross2((b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1]))


def _segments_properly_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
    area_eps: float,
) -> bool:
    o1 = _orient(p1, p2, p3)
    o2 = _orient(p1, p2, p4)
    o3 = _orient(p3, p4, p1)
    o4 = _orient(p3, p4, p2)
    if abs(o1) <= area_eps or abs(o2) <= area_eps or abs(o3) <= area_eps or abs(o4) <= area_eps:
        return False
    return (o1 > 0.0) != (o2 > 0.0) and (o3 > 0.0) != (o4 > 0.0)


def classify_quad(
    local_xy: Sequence[tuple[float, float]],
    l_char: float,
) -> Literal["strictly_convex", "concave", "self_intersecting", "degenerate"]:
    area_eps = COLLINEAR_AREA_RATIO * l_char * l_char
    crosses: list[float] = []
    for i in range(4):
        a = local_xy[i]
        b = local_xy[(i + 1) % 4]
        c = local_xy[(i + 2) % 4]
        crosses.append(_orient(a, b, c))
    if any(abs(value) <= area_eps for value in crosses):
        return "degenerate"
    opposite = (
        (local_xy[0], local_xy[1], local_xy[2], local_xy[3]),
        (local_xy[1], local_xy[2], local_xy[3], local_xy[0]),
    )
    if any(_segments_properly_intersect(*pair, area_eps) for pair in opposite):
        return "self_intersecting"
    if all(value > 0.0 for value in crosses):
        return "strictly_convex"
    return "concave"


def evaluate_element_quality(points: Sequence[Sequence[float]]) -> ElementQuality | None:
    if len(points) != 4:
        return None
    l_char = pairwise_characteristic_length(points)
    if l_char == 0.0:
        return None
    basis = build_local_basis(points[0], points[1], points[3])
    if basis is None:
        return None
    local = project_nodes(points, basis)
    if len(local) != 4:
        return None
    local_xy = [(item[0], item[1]) for item in local]
    edge_lengths = [
        math.hypot(
            local_xy[j][0] - local_xy[i][0],
            local_xy[j][1] - local_xy[i][1],
        )
        for i, j in Q4_LOCAL_EDGES
    ]
    r_edge = min(edge_lengths) / l_char
    r_warp = max(abs(item[2]) for item in local) / l_char
    det_values = tuple(
        q4_det_jacobian(local_xy, sample.natural[0], sample.natural[1]) for sample in q4_gauss_2x2()
    )
    max_det = max(det_values)
    min_det = min(det_values)
    r_j = 0.0 if max_det == 0.0 else min_det / max_det
    jhat_min = min_det / (l_char * l_char)
    return ElementQuality(
        l_char=l_char,
        local_basis=basis,
        local_coordinates=(local[0], local[1], local[2], local[3]),
        r_warp=r_warp,
        r_edge=r_edge,
        det_j=det_values,
        r_j=r_j,
        jhat_min=jhat_min,
        shape=classify_quad(local_xy, l_char),
    )


def mid_surface_dofs_from_global(
    translation_global: Sequence[float],
    rotation_global: Sequence[float],
    basis: LocalBasis,
) -> tuple[float, float, float, float, float]:
    """Map global [u,v,w,ω] to local [u',v',w',θ_x',θ_y']."""

    u_local = basis.to_local(translation_global)
    theta_x, theta_y = basis.director_slopes(rotation_global)
    return (u_local[0], u_local[1], u_local[2], theta_x, theta_y)


def rigid_rotation_global_displacement(
    point: Sequence[float],
    omega: Sequence[float],
) -> Vec3:
    return _cross(omega, point)


def build_element_geometry(points: Sequence[Sequence[float]]) -> ElementGeometry:
    """Build a usable flat-Q4 geometry or raise ``Q4MappingError``."""

    quality = evaluate_element_quality(points)
    if quality is None:
        raise Q4MappingError(
            "SHELL-GEO-E001",
            "cannot build a right-handed local basis from nodes 1,2,4",
            det_j=0.0,
            xi=0.0,
            eta=0.0,
        )
    if quality.shape != "strictly_convex" or quality.r_edge <= EDGE_RATIO_ERROR:
        raise Q4MappingError(
            "SHELL-GEO-E001",
            f"Q4 shape is {quality.shape} or has a near-zero edge",
            det_j=min(quality.det_j),
            xi=0.0,
            eta=0.0,
        )
    if quality.r_warp > WARP_ERROR:
        raise Q4MappingError(
            "SHELL-GEO-E002",
            f"r_warp={quality.r_warp} exceeds {WARP_ERROR}",
            det_j=min(quality.det_j),
            xi=0.0,
            eta=0.0,
        )
    local_xy = [(item[0], item[1]) for item in quality.local_coordinates]
    try:
        gauss = map_q4_gauss_points(local_xy, l_char=quality.l_char)
    except Q4MappingError:
        raise
    if min(point.jacobian.det_j for point in gauss) <= 0.0:
        raise Q4MappingError(
            "SHELL-GEO-E003",
            "a Gauss point has det(J) <= 0",
            det_j=min(point.jacobian.det_j for point in gauss),
            xi=0.0,
            eta=0.0,
        )
    if quality.jhat_min <= JHAT_ERROR:
        raise Q4MappingError(
            "SHELL-GEO-E004",
            f"Jhat_min={quality.jhat_min} is at or below {JHAT_ERROR}",
            det_j=min(quality.det_j),
            xi=0.0,
            eta=0.0,
        )
    return ElementGeometry(
        basis=quality.local_basis,
        local_coordinates=quality.local_coordinates,
        l_char=quality.l_char,
        r_warp=quality.r_warp,
        r_edge=quality.r_edge,
        r_j=quality.r_j,
        jhat_min=quality.jhat_min,
        gauss_points=gauss,
    )
