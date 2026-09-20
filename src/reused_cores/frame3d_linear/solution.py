"""Prescribed displacements, released joint rotations and scaled direct solve."""

from dataclasses import dataclass

import numpy as np

from .assembly import calculate_node_dof_map
from .models import array, identifier


def support_data(number_of_nodes, supports):
    identifier("number_of_nodes", number_of_nodes)
    size = 6 * number_of_nodes
    transform = np.eye(size)
    fixed = np.zeros(size, dtype=bool)
    values = np.zeros(size)
    node_axes = {}
    for support in supports:
        if support.node_id > number_of_nodes:
            raise ValueError("support references an unknown node")
        q = np.eye(3) if support.axes is None else np.array(support.axes)
        old = node_axes.get(support.node_id)
        if old is not None and not np.allclose(q, old, rtol=0, atol=1e-12):
            raise ValueError("support records at one node must use the same axes")
        node_axes[support.node_id] = q
        dofs = calculate_node_dof_map(support.node_id)
        transform[np.ix_(dofs, dofs)] = np.kron(np.eye(2), q)
        for dof, flag, value in zip(
            dofs, support.restraints, support.prescribed_values, strict=False
        ):
            if flag:
                if fixed[dof] and values[dof] != value:
                    raise ValueError(f"conflicting prescribed displacement at DOF {dof}")
                fixed[dof], values[dof] = True, value
    return transform, fixed, values


def partition_dofs(number_of_nodes, supports):
    _, fixed, _ = support_data(number_of_nodes, supports)
    return np.flatnonzero(~fixed), np.flatnonzero(fixed)


def assemble_support_transformation(number_of_nodes, supports):
    return support_data(number_of_nodes, supports)[0]


def assemble_prescribed_displacement_vector(number_of_nodes, supports):
    return support_data(number_of_nodes, supports)[2]


@dataclass(frozen=True, slots=True)
class LinearSolution:
    displacements: np.ndarray
    reactions: np.ndarray
    free_dofs: np.ndarray
    restrained_dofs: np.ndarray
    inactive_dof_vectors: np.ndarray  # rows, global axes; unloaded rotations only
    active_dof_count: int
    scaled_condition_number: float
    support_transformation: np.ndarray


def solve_system(stiffness, load, supports, *, rotational_connectivity=None):
    k = np.asarray(stiffness, dtype=float)
    if k.ndim != 2 or k.shape[0] == 0 or k.shape[0] % 6 or k.shape[1] != k.shape[0]:
        raise ValueError("stiffness must be a nonempty square matrix with 6 DOFs/node")
    n = k.shape[0]
    k = array("stiffness", k, (n, n))
    f = array("load", load, (n,))
    if not np.allclose(k, k.T, rtol=1e-10, atol=1e-10):
        raise ValueError("stiffness must be symmetric")
    s, fixed, dc = support_data(n // 6, supports)
    ks, fs = s @ k @ s.T, s @ f
    columns, inactive = [], []
    # Connectivity, not stiffness eigenvalues, identifies omitted joint rotations.
    # Translational or coupled structural mechanisms must still fail the solve.
    for node in range(n // 6):
        base = 6 * node
        for dof in range(base, base + 3):
            if not fixed[dof]:
                columns.append(np.eye(1, n, dof).ravel())
        rdofs = np.arange(base + 3, base + 6)
        free_rot = np.flatnonzero(~fixed[rdofs])
        if not free_rot.size:
            continue
        q = s[base : base + 3, base : base + 3]
        directions = (
            np.eye(3)
            if rotational_connectivity is None
            else np.asarray(rotational_connectivity[node], dtype=float).reshape(-1, 3)
        )
        if not np.isfinite(directions).all():
            raise ValueError("rotational connectivity must be finite")
        directions = (directions @ q.T)[:, free_rot]
        # SVD of directions avoids squaring small angles in a Gram matrix.
        # Only machine-zero connectivity is removed; weak connected directions
        # remain in K_ff, where conditioning/equilibrium are checked normally.
        _, singular, vt = np.linalg.svd(directions, full_matrices=True)
        tolerance = max(directions.shape) * np.finfo(float).eps * max(singular, default=0)
        rank = int(np.count_nonzero(singular > tolerance))
        for j, vec in enumerate(vt):
            col = np.zeros(n)
            col[rdofs[free_rot]] = vec
            (columns if j < rank else inactive).append(col)
    b = np.column_stack(columns) if columns else np.zeros((n, 0))
    null = np.column_stack(inactive) if inactive else np.zeros((n, 0))
    rhs = fs - ks @ dc
    if null.shape[1]:
        projected = null.T @ rhs
        scales = np.abs(null).T @ (np.abs(fs) + np.abs(ks) @ np.abs(dc))
        if np.any(np.abs(projected) > 1e-9 * np.maximum(1.0, scales)):
            raise ValueError(
                "load acts on an inactive released joint rotation; no equilibrium exists"
            )
    condition = 1.0
    ds = dc.copy()
    if b.shape[1]:
        reduced = b.T @ ks @ b
        diag = np.diag(reduced)
        if np.any(diag <= 0):
            raise ValueError("singular K_ff: unsupported DOF or structural mechanism")
        scale = 1 / np.sqrt(diag)
        scaled = reduced * np.outer(scale, scale)
        eigenvalues = np.linalg.eigvalsh((scaled + scaled.T) / 2)
        if eigenvalues[0] <= 1e-12 * eigenvalues[-1]:
            raise ValueError(
                "singular or ill-conditioned K_ff: check supports, releases and connectivity"
            )
        condition = float(eigenvalues[-1] / eigenvalues[0])
        solved = scale * np.linalg.solve(scaled, scale * (b.T @ rhs))
        ds += b @ solved
    d = array("calculated displacements", s.T @ ds, (n,))
    return LinearSolution(
        d,
        k @ d - f,
        np.flatnonzero(~fixed),
        np.flatnonzero(fixed),
        (s.T @ null).T,
        b.shape[1],
        condition,
        s,
    )


def solve_displacements(global_stiffness, total_load, supports):
    return solve_system(global_stiffness, total_load, supports).displacements


def calculate_reaction_vector(global_stiffness, displacements, total_load):
    k = np.asarray(global_stiffness, dtype=float)
    if k.ndim != 2 or k.shape[0] != k.shape[1]:
        raise ValueError("global_stiffness must be square")
    n = len(k)
    return array("global_stiffness", k, (n, n)) @ array(
        "displacements", displacements, (n,)
    ) - array("total_load", total_load, (n,))
