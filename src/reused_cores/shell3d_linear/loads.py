"""Consistent load integration in the same Q4 map used for stiffness.

Nodal loads scatter in global 6-DOF order. Surface traction, edge traction
and body force are integrated with the mid-surface shape functions, then
transformed by ``f_global = T^T f_local``. Mid-surface resultants load only
the local translation DOFs; uniform-through-thickness body force produces no
first-order director moments.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from reused_cores.shell3d_linear.constants import DOF_PER_NODE_LOCAL, GAUSS_2X2_ABSCISSA, NODES_PER_Q4
from reused_cores.shell3d_linear.geometry import ElementGeometry
from reused_cores.shell3d_linear.q4 import q4_shape
from reused_cores.shell3d_linear.transformation import (
    GLOBAL_DOF_COUNT,
    LOCAL_DOF_COUNT,
    ElementTransform,
    build_element_transform,
    local_force_to_global,
)
from reused_cores.shell3d_linear.types import Vec3

# Edge 1-4 in ADR-002 order, parameterized by s in [-1, 1] from first to second node.
_EDGE_NATURAL: tuple[tuple[float, float, float, float], ...] = (
    (1.0, 0.0, 0.0, -1.0),  # xi=s, eta=-1
    (0.0, 1.0, 1.0, 0.0),  # xi=1, eta=s
    (-1.0, 0.0, 0.0, 1.0),  # xi=-s, eta=1
    (0.0, -1.0, -1.0, 0.0),  # xi=-1, eta=-s
)
_EDGE_GAUSS: tuple[float, float] = (-GAUSS_2X2_ABSCISSA, GAUSS_2X2_ABSCISSA)


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


def _vec3(name: str, values: Sequence[float]) -> Vec3:
    if len(values) != 3:
        raise ValueError(f"{name} must contain 3 components")
    return (
        _finite(f"{name}[0]", values[0]),
        _finite(f"{name}[1]", values[1]),
        _finite(f"{name}[2]", values[2]),
    )


def _zero_local() -> list[float]:
    return [0.0] * LOCAL_DOF_COUNT


def _add_mid_surface_load(
    local_force: list[float],
    shape_n: Sequence[float],
    traction_local: Sequence[float],
    factor: float,
) -> None:
    if len(shape_n) != NODES_PER_Q4:
        raise ValueError("consistent load shape values must have length 4")
    for node in range(NODES_PER_Q4):
        weight = shape_n[node] * factor
        base = node * DOF_PER_NODE_LOCAL
        local_force[base] += weight * traction_local[0]
        local_force[base + 1] += weight * traction_local[1]
        local_force[base + 2] += weight * traction_local[2]


def integrate_surface_traction(
    geometry: ElementGeometry,
    traction_global: Sequence[float],
    *,
    transform: ElementTransform | None = None,
) -> tuple[float, ...]:
    """Integrate a constant global mid-surface traction ``N/m^2``."""

    traction = _vec3("traction_global", traction_global)
    traction_local = geometry.basis.to_local(traction)
    local_force = _zero_local()
    for point in geometry.gauss_points:
        factor = point.jacobian.det_j * point.weight
        if factor <= 0.0:
            raise ValueError("surface traction integration requires positive det(J) and weight")
        _add_mid_surface_load(local_force, point.shape.n, traction_local, factor)
    element_transform = transform or build_element_transform(geometry.basis)
    return local_force_to_global(element_transform, local_force)


def integrate_body_force(
    geometry: ElementGeometry,
    force_density_global: Sequence[float],
    thickness: float,
    *,
    transform: ElementTransform | None = None,
) -> tuple[float, ...]:
    """Integrate a constant global body-force density ``N/m^3`` through thickness."""

    thickness_value = _finite("thickness", thickness)
    if thickness_value <= 0.0:
        raise ValueError("body-force integration requires thickness > 0")
    density = _vec3("force_density_global", force_density_global)
    density_local = geometry.basis.to_local(density)
    local_force = _zero_local()
    for point in geometry.gauss_points:
        factor = point.jacobian.det_j * point.weight * thickness_value
        if factor <= 0.0:
            raise ValueError(
                "body-force integration requires positive det(J), weight and thickness"
            )
        _add_mid_surface_load(local_force, point.shape.n, density_local, factor)
    element_transform = transform or build_element_transform(geometry.basis)
    return local_force_to_global(element_transform, local_force)


def integrate_edge_traction(
    geometry: ElementGeometry,
    local_edge: int,
    traction_global: Sequence[float],
    *,
    transform: ElementTransform | None = None,
) -> tuple[float, ...]:
    """Integrate a constant global edge traction ``N/m`` on local edge 1-4."""

    if local_edge not in {1, 2, 3, 4}:
        raise ValueError("local_edge must be in {1, 2, 3, 4}")
    traction = _vec3("traction_global", traction_global)
    traction_local = geometry.basis.to_local(traction)
    dxi_ds, deta_ds, xi0, eta0 = _EDGE_NATURAL[local_edge - 1]
    local_xy = tuple((point[0], point[1]) for point in geometry.local_coordinates)
    local_force = _zero_local()
    for sample in _EDGE_GAUSS:
        xi = xi0 + dxi_ds * sample
        eta = eta0 + deta_ds * sample
        shape = q4_shape(xi, eta)
        dx_ds = 0.0
        dy_ds = 0.0
        for node in range(NODES_PER_Q4):
            d_ds = shape.d_dxi[node] * dxi_ds + shape.d_deta[node] * deta_ds
            dx_ds += d_ds * local_xy[node][0]
            dy_ds += d_ds * local_xy[node][1]
        jacobian = math.hypot(dx_ds, dy_ds)
        if jacobian <= 0.0:
            raise ValueError("edge traction integration requires a positive edge Jacobian")
        _add_mid_surface_load(local_force, shape.n, traction_local, jacobian)
    element_transform = transform or build_element_transform(geometry.basis)
    return local_force_to_global(element_transform, local_force)


def scatter_nodal_load(
    dof_count: int,
    node_index: int,
    force_global: Sequence[float],
    moment_global: Sequence[float],
) -> tuple[float, ...]:
    """Scatter one nodal force/moment into a global load vector."""

    if dof_count % 6 != 0:
        raise ValueError("global load vectors must have 6 DOFs per node")
    if node_index < 0 or 6 * node_index + 5 >= dof_count:
        raise ValueError("node_index is outside the assembled DOF range")
    force = _vec3("force_global", force_global)
    moment = _vec3("moment_global", moment_global)
    load = [0.0] * dof_count
    base = 6 * node_index
    load[base] = force[0]
    load[base + 1] = force[1]
    load[base + 2] = force[2]
    load[base + 3] = moment[0]
    load[base + 4] = moment[1]
    load[base + 5] = moment[2]
    return tuple(load)


def add_global_vectors(
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[float, ...]:
    if len(left) != len(right):
        raise ValueError("load vectors must have the same length")
    return tuple(left[index] + right[index] for index in range(len(left)))


def scatter_element_vector(
    dof_count: int,
    dof_indices: Sequence[int],
    element_values: Sequence[float],
) -> tuple[float, ...]:
    if len(dof_indices) != len(element_values):
        raise ValueError("element scatter map and values must have the same length")
    if len(element_values) != GLOBAL_DOF_COUNT:
        raise ValueError(f"element load must contain {GLOBAL_DOF_COUNT} values")
    load = [0.0] * dof_count
    for local, global_index in enumerate(dof_indices):
        if global_index < 0 or global_index >= dof_count:
            raise ValueError("element DOF index is outside the assembled range")
        load[global_index] += _finite(f"element_values[{local}]", element_values[local])
    return tuple(load)


__all__ = [
    "add_global_vectors",
    "integrate_body_force",
    "integrate_edge_traction",
    "integrate_surface_traction",
    "scatter_element_vector",
    "scatter_nodal_load",
]
