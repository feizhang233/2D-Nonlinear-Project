"""P5 local-20 to global-24 flat-shell transformations.

The frozen P0 chain is ``a_local = T a_global``,
``K_global = T^T K_local T`` and ``f_global = T^T f_local``. Local
director slopes are not same-name axial rotations:
``theta_x' = -e_y'^T omega`` and ``theta_y' = e_x'^T omega``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from reused_cores.shell3d_linear.constants import (
    DOF_PER_NODE_GLOBAL,
    DOF_PER_NODE_LOCAL,
    NODES_PER_Q4,
)
from reused_cores.shell3d_linear.geometry import LocalBasis
from reused_cores.shell3d_linear.membrane_bending import Matrix20

LOCAL_DOF_COUNT = NODES_PER_Q4 * DOF_PER_NODE_LOCAL
GLOBAL_DOF_COUNT = NODES_PER_Q4 * DOF_PER_NODE_GLOBAL

Matrix5x6 = tuple[tuple[float, ...], ...]
Matrix6 = tuple[tuple[float, ...], ...]
Matrix20x24 = tuple[tuple[float, ...], ...]
Matrix24 = tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class ElementTransform:
    """Physical and augmented local-from-global element transforms.

    ``local_from_global`` is the frozen 20x24 physical transform. The
    orthogonal 24x24 augmented transform adds only ``theta_z'=e_z'^T omega``
    for continuum-consistent drilling construction.
    """

    node_local_from_global: Matrix5x6
    local_from_global: Matrix20x24
    node_augmented_from_global: Matrix6
    augmented_local_from_global: Matrix24


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


def build_node_transform(basis: LocalBasis) -> Matrix5x6:
    """Return the frozen per-node 5x6 physical transform ``L_i``."""

    ex, ey, ez = basis.e_x, basis.e_y, basis.e_z
    return (
        (ex[0], ex[1], ex[2], 0.0, 0.0, 0.0),
        (ey[0], ey[1], ey[2], 0.0, 0.0, 0.0),
        (ez[0], ez[1], ez[2], 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, -ey[0], -ey[1], -ey[2]),
        (0.0, 0.0, 0.0, ex[0], ex[1], ex[2]),
    )


def build_augmented_node_transform(basis: LocalBasis) -> Matrix6:
    """Add the local axial drilling component ``theta_z'=e_z'^T omega``."""

    physical = build_node_transform(basis)
    ez = basis.e_z
    return (
        physical[0],
        physical[1],
        physical[2],
        physical[3],
        physical[4],
        (0.0, 0.0, 0.0, ez[0], ez[1], ez[2]),
    )


def _block_diagonal(
    block: Sequence[Sequence[float]],
    block_rows: int,
    block_columns: int,
) -> tuple[tuple[float, ...], ...]:
    if len(block) != block_rows or any(len(row) != block_columns for row in block):
        raise ValueError(f"node transform must be {block_rows}x{block_columns}")
    rows = [[0.0] * (NODES_PER_Q4 * block_columns) for _ in range(NODES_PER_Q4 * block_rows)]
    for node in range(NODES_PER_Q4):
        row_base = node * block_rows
        column_base = node * block_columns
        for row in range(block_rows):
            for column in range(block_columns):
                rows[row_base + row][column_base + column] = float(block[row][column])
    return tuple(tuple(row) for row in rows)


def build_element_transform(basis: LocalBasis) -> ElementTransform:
    """Build the block-diagonal 20x24 and augmented 24x24 transforms."""

    node = build_node_transform(basis)
    augmented_node = build_augmented_node_transform(basis)
    return ElementTransform(
        node_local_from_global=node,
        local_from_global=_block_diagonal(node, 5, 6),
        node_augmented_from_global=augmented_node,
        augmented_local_from_global=_block_diagonal(augmented_node, 6, 6),
    )


def global_to_local_dofs(
    transform: ElementTransform,
    global_dofs: Sequence[float],
) -> tuple[float, ...]:
    values = _finite_values("global_dofs", global_dofs, GLOBAL_DOF_COUNT)
    return tuple(
        sum(
            transform.local_from_global[row][column] * values[column]
            for column in range(GLOBAL_DOF_COUNT)
        )
        for row in range(LOCAL_DOF_COUNT)
    )


def global_to_augmented_local_dofs(
    transform: ElementTransform,
    global_dofs: Sequence[float],
) -> tuple[float, ...]:
    values = _finite_values("global_dofs", global_dofs, GLOBAL_DOF_COUNT)
    return tuple(
        sum(
            transform.augmented_local_from_global[row][column] * values[column]
            for column in range(GLOBAL_DOF_COUNT)
        )
        for row in range(GLOBAL_DOF_COUNT)
    )


def augmented_local_to_global_dofs(
    transform: ElementTransform,
    augmented_local_dofs: Sequence[float],
) -> tuple[float, ...]:
    """Apply the transpose of the orthogonal augmented transform."""

    values = _finite_values(
        "augmented_local_dofs",
        augmented_local_dofs,
        GLOBAL_DOF_COUNT,
    )
    return tuple(
        sum(
            transform.augmented_local_from_global[row][column] * values[row]
            for row in range(GLOBAL_DOF_COUNT)
        )
        for column in range(GLOBAL_DOF_COUNT)
    )


def local_force_to_global(
    transform: ElementTransform,
    local_force: Sequence[float],
) -> tuple[float, ...]:
    """Return ``f_global = T^T f_local`` with virtual-work consistency."""

    values = _finite_values("local_force", local_force, LOCAL_DOF_COUNT)
    return tuple(
        sum(
            transform.local_from_global[row][column] * values[row] for row in range(LOCAL_DOF_COUNT)
        )
        for column in range(GLOBAL_DOF_COUNT)
    )


def transform_local_stiffness(
    transform: ElementTransform,
    local_stiffness: Matrix20,
) -> Matrix24:
    """Return the 24x24 congruence ``T^T K_local T``."""

    if len(local_stiffness) != LOCAL_DOF_COUNT or any(
        len(row) != LOCAL_DOF_COUNT for row in local_stiffness
    ):
        raise ValueError("local_stiffness must be 20x20")
    intermediate = [[0.0] * GLOBAL_DOF_COUNT for _ in range(LOCAL_DOF_COUNT)]
    for row in range(LOCAL_DOF_COUNT):
        for column in range(GLOBAL_DOF_COUNT):
            intermediate[row][column] = sum(
                local_stiffness[row][inner] * transform.local_from_global[inner][column]
                for inner in range(LOCAL_DOF_COUNT)
            )
    return tuple(
        tuple(
            sum(
                transform.local_from_global[inner][row] * intermediate[inner][column]
                for inner in range(LOCAL_DOF_COUNT)
            )
            for column in range(GLOBAL_DOF_COUNT)
        )
        for row in range(GLOBAL_DOF_COUNT)
    )


def global_internal_force(
    stiffness: Matrix24,
    global_dofs: Sequence[float],
) -> tuple[float, ...]:
    values = _finite_values("global_dofs", global_dofs, GLOBAL_DOF_COUNT)
    if len(stiffness) != GLOBAL_DOF_COUNT or any(len(row) != GLOBAL_DOF_COUNT for row in stiffness):
        raise ValueError("global stiffness must be 24x24")
    return tuple(
        sum(stiffness[row][column] * values[column] for column in range(GLOBAL_DOF_COUNT))
        for row in range(GLOBAL_DOF_COUNT)
    )


__all__ = [
    "GLOBAL_DOF_COUNT",
    "LOCAL_DOF_COUNT",
    "ElementTransform",
    "Matrix20x24",
    "Matrix24",
    "Matrix5x6",
    "Matrix6",
    "augmented_local_to_global_dofs",
    "build_augmented_node_transform",
    "build_element_transform",
    "build_node_transform",
    "global_internal_force",
    "global_to_augmented_local_dofs",
    "global_to_local_dofs",
    "local_force_to_global",
    "transform_local_stiffness",
]
