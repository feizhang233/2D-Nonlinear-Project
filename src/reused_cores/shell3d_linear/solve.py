"""Constrained linear static solve, reactions, residual and condition diagnostics.

The production path is ``solve_linear_static``. Constraints are applied by
symmetric elimination of prescribed global DOFs. Mixed translation/rotation
unknowns are scaled with the model characteristic length before the
symmetric-direct factorization. Reactions use the frozen residual definition
``R = (K a - f)_c``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from reused_cores.shell3d_linear.assembly import (
    AssembledSystem,
    assemble_system,
    extract_element_vector,
    matrix_vector_product,
    quadratic_form,
)
from reused_cores.shell3d_linear.constants import DOF_PER_NODE_GLOBAL, GLOBAL_DOF_ORDER
from reused_cores.shell3d_linear.diagnostics import Diagnostic, make_diagnostic, sort_diagnostics
from reused_cores.shell3d_linear.drilling import global_shell_energy
from reused_cores.shell3d_linear.sparse import SparseMatrix
from reused_cores.shell3d_linear.types import (
    AnalysisOptions,
    NodalDisplacement,
    NodalReaction,
    ResidualReport,
    SolveResult,
    ValidatedModel,
    Vec3,
)

_PIVOT_RELATIVE = 1e-18


@dataclass(frozen=True, slots=True)
class ConstrainedSolve:
    """Generic symmetric-direct solve of ``K a = f`` with prescribed DOFs."""

    status: Literal["succeeded", "failed"]
    displacement: tuple[float, ...]
    residual: tuple[float, ...]
    free_dof_indices: tuple[int, ...]
    constrained_dof_indices: tuple[int, ...]
    scaled_relative_backward_error: float | None
    condition_estimate: float | None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class LinearStaticResult:
    """P6 solve outcome. Failed runs keep diagnostics and omit ``SolveResult``."""

    status: Literal["succeeded", "failed"]
    diagnostics: tuple[Diagnostic, ...]
    solve_result: SolveResult | None
    displacement_vector: tuple[float, ...] | None
    residual_vector: tuple[float, ...] | None
    applied_load: tuple[float, ...] | None
    strain_energy: float | None
    external_work: float | None
    constraint_work: float | None
    assembled: AssembledSystem | None
    free_dof_indices: tuple[int, ...] | None
    moment_reference_point_global: Vec3 | None

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "error")

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "warning")


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


def _all_finite(values: Sequence[float]) -> bool:
    return all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        for value in values
    )


def norm2(values: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def characteristic_scales(dof_count: int, characteristic_length: float) -> tuple[float, ...]:
    if dof_count % DOF_PER_NODE_GLOBAL != 0:
        raise ValueError("DOF count must be a multiple of 6")
    length = _finite("characteristic_length", characteristic_length)
    if length <= 0.0:
        raise ValueError("characteristic_length must be greater than zero")
    scales: list[float] = []
    for _ in range(dof_count // DOF_PER_NODE_GLOBAL):
        scales.extend((length, length, length, 1.0, 1.0, 1.0))
    return tuple(scales)


def scale_stiffness(
    stiffness: Sequence[Sequence[float]],
    scales: Sequence[float],
) -> tuple[tuple[float, ...], ...]:
    size = len(scales)
    if len(stiffness) != size or any(len(row) != size for row in stiffness):
        raise ValueError("scaled stiffness must match the scale vector")
    return tuple(
        tuple(scales[row] * stiffness[row][column] * scales[column] for column in range(size))
        for row in range(size)
    )


def _norm1(matrix: Sequence[Sequence[float]]) -> float:
    size = len(matrix)
    return max(sum(abs(matrix[row][column]) for row in range(size)) for column in range(size))


def _cholesky_factor(matrix: Sequence[Sequence[float]]) -> list[list[float]] | None:
    size = len(matrix)
    if size == 0:
        return []
    scale = max(abs(matrix[index][index]) for index in range(size))
    floor = max(scale * _PIVOT_RELATIVE, 0.0)
    factor = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            accumulated = matrix[row][column] - sum(
                factor[row][inner] * factor[column][inner] for inner in range(column)
            )
            if row == column:
                if accumulated <= floor:
                    return None
                factor[row][column] = math.sqrt(accumulated)
            else:
                factor[row][column] = accumulated / factor[column][column]
    return factor


def _forward_substitute(
    factor: Sequence[Sequence[float]], right_hand_side: Sequence[float]
) -> list[float]:
    size = len(factor)
    result = [0.0] * size
    for row in range(size):
        accumulated = right_hand_side[row] - sum(
            factor[row][column] * result[column] for column in range(row)
        )
        result[row] = accumulated / factor[row][row]
    return result


def _back_substitute(
    factor: Sequence[Sequence[float]], right_hand_side: Sequence[float]
) -> list[float]:
    size = len(factor)
    result = [0.0] * size
    for row in range(size - 1, -1, -1):
        accumulated = right_hand_side[row] - sum(
            factor[column][row] * result[column] for column in range(row + 1, size)
        )
        result[row] = accumulated / factor[row][row]
    return result


def _solve_cholesky(
    factor: Sequence[Sequence[float]], right_hand_side: Sequence[float]
) -> list[float]:
    return _back_substitute(factor, _forward_substitute(factor, right_hand_side))


def _condition_estimate(
    matrix: Sequence[Sequence[float]], factor: Sequence[Sequence[float]]
) -> float:
    size = len(matrix)
    if size == 0:
        return 1.0
    inverse_columns: list[list[float]] = []
    identity_column = [0.0] * size
    for column in range(size):
        identity_column[column] = 1.0
        inverse_columns.append(_solve_cholesky(factor, identity_column))
        identity_column[column] = 0.0
    inverse = [[inverse_columns[column][row] for column in range(size)] for row in range(size)]
    return _norm1(matrix) * _norm1(inverse)


def _symmetric_lower_matvec(
    matrix: Sequence[Mapping[int, float]],
    vector: Sequence[float],
) -> list[float]:
    result = [0.0] * len(matrix)
    for row, entries in enumerate(matrix):
        for column, value in entries.items():
            result[row] += value * vector[column]
            if column != row:
                result[column] += value * vector[row]
    return result


def _symmetric_lower_norm1(matrix: Sequence[Mapping[int, float]]) -> float:
    sums = [0.0] * len(matrix)
    for row, entries in enumerate(matrix):
        for column, value in entries.items():
            magnitude = abs(value)
            sums[row] += magnitude
            if column != row:
                sums[column] += magnitude
    return max(sums, default=0.0)


def _sparse_cholesky_factor(
    matrix: Sequence[Mapping[int, float]],
) -> list[dict[int, float]] | None:
    size = len(matrix)
    work = [dict(row) for row in matrix]
    diagonal_scale = max((abs(work[index].get(index, 0.0)) for index in range(size)), default=0.0)
    floor = max(diagonal_scale * _PIVOT_RELATIVE, 0.0)
    column_rows: list[set[int]] = [set() for _ in range(size)]
    for row, entries in enumerate(work):
        for column, value in entries.items():
            if column < row and value != 0.0:
                column_rows[column].add(row)

    factor: list[dict[int, float]] = [{} for _ in range(size)]
    for column in range(size):
        pivot = work[column].get(column, 0.0)
        if pivot <= floor or not math.isfinite(pivot):
            return None
        diagonal = math.sqrt(pivot)
        factor[column][column] = diagonal
        neighbors = sorted(
            row for row in column_rows[column] if row > column and work[row].get(column, 0.0) != 0.0
        )
        multipliers = {row: work[row][column] / diagonal for row in neighbors}
        for row, value in multipliers.items():
            factor[row][column] = value
        for row_position, row in enumerate(neighbors):
            left = multipliers[row]
            for inner in neighbors[: row_position + 1]:
                updated = work[row].get(inner, 0.0) - left * multipliers[inner]
                if updated == 0.0:
                    work[row].pop(inner, None)
                    if inner < row:
                        column_rows[inner].discard(row)
                else:
                    work[row][inner] = updated
                    if inner < row:
                        column_rows[inner].add(row)
    return factor


def _solve_sparse_factor(
    factor: Sequence[Mapping[int, float]],
    right_hand_side: Sequence[float],
) -> list[float]:
    size = len(factor)
    forward = [0.0] * size
    for row in range(size):
        accumulated = right_hand_side[row] - sum(
            value * forward[column] for column, value in factor[row].items() if column < row
        )
        forward[row] = accumulated / factor[row][row]

    columns: list[list[tuple[int, float]]] = [[] for _ in range(size)]
    for row, entries in enumerate(factor):
        for column, value in entries.items():
            if column < row:
                columns[column].append((row, value))
    result = [0.0] * size
    for row in range(size - 1, -1, -1):
        accumulated = forward[row] - sum(value * result[column] for column, value in columns[row])
        result[row] = accumulated / factor[row][row]
    return result


def _sparse_condition_estimate(
    matrix: Sequence[Mapping[int, float]],
    factor: Sequence[Mapping[int, float]],
) -> float:
    size = len(matrix)
    if size == 0:
        return 1.0
    norm = _symmetric_lower_norm1(matrix)
    if size <= 128:
        inverse_norm = 0.0
        for column in range(size):
            basis = [0.0] * size
            basis[column] = 1.0
            inverse_column = _solve_sparse_factor(factor, basis)
            inverse_norm = max(inverse_norm, sum(abs(value) for value in inverse_column))
        return norm * inverse_norm
    pivots = [entries[index] for index, entries in enumerate(factor)]
    return (max(pivots) / min(pivots)) ** 2


def _solve_constrained_sparse(
    stiffness: SparseMatrix,
    load: Sequence[float],
    prescribed: Mapping[int, float],
    scales: Sequence[float],
) -> ConstrainedSolve:
    size = len(load)
    constrained = tuple(sorted(prescribed))
    free = tuple(index for index in range(size) if index not in prescribed)
    displacement = [0.0] * size
    for index, value in prescribed.items():
        displacement[index] = _finite(f"prescribed[{index}]", value)
    if not free:
        residual = tuple(
            left - right for left, right in zip(stiffness.matvec(displacement), load, strict=True)
        )
        return ConstrainedSolve(
            status="succeeded" if _all_finite(residual) else "failed",
            displacement=tuple(displacement),
            residual=residual,
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=0.0 if _all_finite(residual) else None,
            condition_estimate=1.0 if _all_finite(residual) else None,
            message=None if _all_finite(residual) else "non-finite residual",
        )

    free_position = {global_index: local for local, global_index in enumerate(free)}
    constrained_set = set(constrained)
    block: list[dict[int, float]] = [{} for _ in free]
    right_hand_side = [scales[index] * load[index] for index in free]
    for local_row, global_row in enumerate(free):
        row_scale = scales[global_row]
        for global_column, value in stiffness.row_items(global_row):
            if global_column in free_position:
                local_column = free_position[global_column]
                if local_column <= local_row:
                    block[local_row][local_column] = row_scale * value * scales[global_column]
            elif global_column in constrained_set:
                right_hand_side[local_row] -= row_scale * value * displacement[global_column]

    factor = _sparse_cholesky_factor(block)
    if factor is None:
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=tuple(0.0 for _ in range(size)),
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=None,
            message="sparse symmetric-direct factorization failed",
        )
    try:
        free_solution = _solve_sparse_factor(factor, right_hand_side)
        condition = _sparse_condition_estimate(block, factor)
    except (ValueError, ZeroDivisionError, OverflowError):
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=tuple(0.0 for _ in range(size)),
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=None,
            message="sparse symmetric-direct substitution failed",
        )
    if not _all_finite(free_solution) or not math.isfinite(condition):
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=tuple(0.0 for _ in range(size)),
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=None,
            message="non-finite sparse solution",
        )
    for local, global_index in enumerate(free):
        displacement[global_index] = free_solution[local] * scales[global_index]
    residual = tuple(
        left - right for left, right in zip(stiffness.matvec(displacement), load, strict=True)
    )
    predicted = _symmetric_lower_matvec(block, free_solution)
    scaled_residual = [predicted[index] - right_hand_side[index] for index in range(len(free))]
    denominator = max(
        _symmetric_lower_norm1(block) * norm2(free_solution),
        norm2(right_hand_side),
        1.0,
    )
    backward = norm2(scaled_residual) / denominator
    if not _all_finite(residual) or not _all_finite(displacement):
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=residual,
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=condition,
            message="non-finite sparse residual",
        )
    return ConstrainedSolve(
        status="succeeded",
        displacement=tuple(displacement),
        residual=residual,
        free_dof_indices=free,
        constrained_dof_indices=constrained,
        scaled_relative_backward_error=backward,
        condition_estimate=condition,
    )


def _submatrix(
    matrix: Sequence[Sequence[float]],
    rows: Sequence[int],
    columns: Sequence[int],
) -> list[list[float]]:
    return [[matrix[row][column] for column in columns] for row in rows]


def _subvector(vector: Sequence[float], indices: Sequence[int]) -> list[float]:
    return [vector[index] for index in indices]


def solve_constrained_symmetric(
    stiffness: Sequence[Sequence[float]],
    load: Sequence[float],
    prescribed: Mapping[int, float],
    *,
    scales: Sequence[float] | None = None,
) -> ConstrainedSolve:
    """Solve a dense symmetric system with prescribed DOFs by elimination."""

    size = len(load)
    if len(stiffness) != size or any(len(row) != size for row in stiffness):
        raise ValueError("stiffness must be square and match the load vector")
    scale_values = tuple(1.0 for _ in range(size)) if scales is None else tuple(scales)
    if len(scale_values) != size:
        raise ValueError("scale vector must match the system size")
    if any(value <= 0.0 or not math.isfinite(value) for value in scale_values):
        raise ValueError("scale entries must be positive and finite")

    constrained = tuple(sorted(prescribed))
    if any(index < 0 or index >= size for index in constrained):
        raise ValueError("prescribed DOF index is outside the system")
    free = tuple(index for index in range(size) if index not in prescribed)
    displacement = [0.0] * size
    for index, value in prescribed.items():
        displacement[index] = _finite(f"prescribed[{index}]", value)

    if isinstance(stiffness, SparseMatrix):
        return _solve_constrained_sparse(stiffness, load, prescribed, scale_values)

    scaled_stiffness = scale_stiffness(stiffness, scale_values)
    scaled_load = [scale_values[index] * load[index] for index in range(size)]
    scaled_unknowns = [
        displacement[index] / scale_values[index] if scale_values[index] != 0.0 else 0.0
        for index in range(size)
    ]

    if not free:
        residual = tuple(
            left - right
            for left, right in zip(
                matrix_vector_product(stiffness, displacement), load, strict=True
            )
        )
        if not _all_finite(residual):
            return ConstrainedSolve(
                status="failed",
                displacement=tuple(displacement),
                residual=residual,
                free_dof_indices=free,
                constrained_dof_indices=constrained,
                scaled_relative_backward_error=None,
                condition_estimate=None,
                message="non-finite residual",
            )
        return ConstrainedSolve(
            status="succeeded",
            displacement=tuple(displacement),
            residual=residual,
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=0.0,
            condition_estimate=1.0,
        )

    block = _submatrix(scaled_stiffness, free, free)
    coupling = _submatrix(scaled_stiffness, free, constrained)
    prescribed_scaled = _subvector(scaled_unknowns, constrained)
    right_hand_side = [
        _subvector(scaled_load, free)[row]
        - sum(
            coupling[row][column] * prescribed_scaled[column] for column in range(len(constrained))
        )
        for row in range(len(free))
    ]
    factor = _cholesky_factor(block)
    if factor is None:
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=tuple(0.0 for _ in range(size)),
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=None,
            message="symmetric-direct factorization failed",
        )

    try:
        free_solution = _solve_cholesky(factor, right_hand_side)
        condition = _condition_estimate(block, factor)
    except (ValueError, ZeroDivisionError):
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=tuple(0.0 for _ in range(size)),
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=None,
            message="symmetric-direct substitution failed",
        )

    if not _all_finite(free_solution) or not math.isfinite(condition):
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=tuple(0.0 for _ in range(size)),
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=None,
            message="non-finite solution",
        )

    for local, global_index in enumerate(free):
        displacement[global_index] = free_solution[local] * scale_values[global_index]
    residual = tuple(
        left - right
        for left, right in zip(matrix_vector_product(stiffness, displacement), load, strict=True)
    )
    if not _all_finite(residual) or not _all_finite(displacement):
        return ConstrainedSolve(
            status="failed",
            displacement=tuple(displacement),
            residual=residual,
            free_dof_indices=free,
            constrained_dof_indices=constrained,
            scaled_relative_backward_error=None,
            condition_estimate=condition,
            message="non-finite residual",
        )

    predicted = [
        sum(block[row][column] * free_solution[column] for column in range(len(free)))
        for row in range(len(free))
    ]
    scaled_residual = [predicted[row] - right_hand_side[row] for row in range(len(free))]
    denominator = max(
        _norm1(block) * norm2(free_solution),
        norm2(right_hand_side),
        1.0,
    )
    backward = norm2(scaled_residual) / denominator
    return ConstrainedSolve(
        status="succeeded",
        displacement=tuple(displacement),
        residual=residual,
        free_dof_indices=free,
        constrained_dof_indices=constrained,
        scaled_relative_backward_error=backward,
        condition_estimate=condition,
    )


def jacobi_symmetric_eigh(
    matrix: Sequence[Sequence[float]],
    *,
    tolerance: float = 1e-14,
    max_sweeps: int = 80,
) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """Cyclic Jacobi eigen-decomposition of a small dense symmetric matrix.

    Returns eigenvalues and a matrix whose columns are the corresponding
    eigenvectors. Used for V05 rank / null-space checks, not for production
    displacement solves.
    """

    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("eigenvalue matrix must be square")
    work = [list(row) for row in matrix]
    vectors = [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]
    if size == 0:
        return (), ()

    for _ in range(max_sweeps):
        off = 0.0
        for row in range(size):
            for column in range(row + 1, size):
                off += work[row][column] * work[row][column]
        diagonal_scale = max(max(abs(work[index][index]) for index in range(size)), 1.0)
        if math.sqrt(2.0 * off) <= tolerance * diagonal_scale:
            break
        for left in range(size):
            for right in range(left + 1, size):
                entry = work[left][right]
                if abs(entry) <= tolerance * max(
                    abs(work[left][left]), abs(work[right][right]), 1.0
                ):
                    work[left][right] = 0.0
                    work[right][left] = 0.0
                    continue
                tau = (work[right][right] - work[left][left]) / (2.0 * entry)
                tangent = math.copysign(1.0, tau) / (abs(tau) + math.sqrt(1.0 + tau * tau))
                cosine = 1.0 / math.sqrt(1.0 + tangent * tangent)
                sine = tangent * cosine
                left_diag = work[left][left]
                right_diag = work[right][right]
                work[left][left] = (
                    cosine * cosine * left_diag
                    - 2.0 * sine * cosine * entry
                    + sine * sine * right_diag
                )
                work[right][right] = (
                    sine * sine * left_diag
                    + 2.0 * sine * cosine * entry
                    + cosine * cosine * right_diag
                )
                work[left][right] = 0.0
                work[right][left] = 0.0
                for index in range(size):
                    if index == left or index == right:
                        continue
                    left_value = work[index][left]
                    right_value = work[index][right]
                    updated_left = cosine * left_value - sine * right_value
                    updated_right = sine * left_value + cosine * right_value
                    work[index][left] = updated_left
                    work[left][index] = updated_left
                    work[index][right] = updated_right
                    work[right][index] = updated_right
                for index in range(size):
                    left_value = vectors[index][left]
                    right_value = vectors[index][right]
                    vectors[index][left] = cosine * left_value - sine * right_value
                    vectors[index][right] = sine * left_value + cosine * right_value

    eigenvalues = tuple(work[index][index] for index in range(size))
    eigenvectors = tuple(tuple(row) for row in vectors)
    return eigenvalues, eigenvectors


def near_zero_eigenvalues(
    eigenvalues: Sequence[float],
    *,
    relative: float = 1e-10,
) -> tuple[float, float, tuple[float, ...]]:
    lambda_max = max((abs(value) for value in eigenvalues), default=0.0)
    threshold = relative * lambda_max
    zeros = tuple(value for value in eigenvalues if abs(value) <= threshold)
    return lambda_max, threshold, zeros


def _centroid(points: Sequence[Sequence[float]]) -> Vec3:
    count = len(points)
    if count == 0:
        return (0.0, 0.0, 0.0)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _cross(left: Sequence[float], right: Sequence[float]) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _add3(left: Sequence[float], right: Sequence[float]) -> Vec3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def _force_moment_errors(
    model: ValidatedModel,
    applied: Sequence[float],
    residual: Sequence[float],
    constrained_nodes: Sequence[str],
    reference: Sequence[float],
    characteristic_length: float,
) -> tuple[float, float]:
    applied_force = [0.0, 0.0, 0.0]
    reaction_force = [0.0, 0.0, 0.0]
    applied_moment = [0.0, 0.0, 0.0]
    reaction_moment = [0.0, 0.0, 0.0]
    applied_force_abs = 0.0
    reaction_force_abs = 0.0
    applied_moment_abs = 0.0
    reaction_moment_abs = 0.0
    constrained = set(constrained_nodes)
    for node in model.nodes:
        base = node.dof_indices[0]
        force = (applied[base], applied[base + 1], applied[base + 2])
        moment = (applied[base + 3], applied[base + 4], applied[base + 5])
        lever = (
            node.coordinates[0] - reference[0],
            node.coordinates[1] - reference[1],
            node.coordinates[2] - reference[2],
        )
        couple = _add3(_cross(lever, force), moment)
        applied_force = list(_add3(applied_force, force))
        applied_moment = list(_add3(applied_moment, couple))
        applied_force_abs += norm2(force)
        applied_moment_abs += norm2(couple)
        if node.id not in constrained:
            continue
        reaction = (residual[base], residual[base + 1], residual[base + 2])
        reaction_m = (residual[base + 3], residual[base + 4], residual[base + 5])
        reaction_couple = _add3(_cross(lever, reaction), reaction_m)
        reaction_force = list(_add3(reaction_force, reaction))
        reaction_moment = list(_add3(reaction_moment, reaction_couple))
        reaction_force_abs += norm2(reaction)
        reaction_moment_abs += norm2(reaction_couple)

    force_error = norm2(_add3(applied_force, reaction_force)) / max(
        applied_force_abs, reaction_force_abs, 1.0
    )
    moment_error = norm2(_add3(applied_moment, reaction_moment)) / max(
        applied_moment_abs,
        reaction_moment_abs,
        max(applied_force_abs, reaction_force_abs, 1.0) * characteristic_length,
        1.0,
    )
    return force_error, moment_error


def _solve_diagnostic(
    code: str,
    *,
    observed: object,
    threshold: object,
    unit: str | None,
    message: str | None = None,
) -> Diagnostic:
    return make_diagnostic(
        code,
        entity_type="solver",
        entity_id=None,
        json_path="$.analysis_options.solver",
        observed=observed,
        threshold=threshold,
        unit=unit,
        message=message,
    )


def _failed(
    diagnostics: Sequence[Diagnostic],
    assembled: AssembledSystem | None,
    *,
    displacement: tuple[float, ...] | None = None,
    residual: tuple[float, ...] | None = None,
    free: tuple[int, ...] | None = None,
    reference: Vec3 | None = None,
) -> LinearStaticResult:
    return LinearStaticResult(
        status="failed",
        diagnostics=sort_diagnostics(list(diagnostics)),
        solve_result=None,
        displacement_vector=displacement,
        residual_vector=residual,
        applied_load=None if assembled is None else assembled.applied_load,
        strain_energy=None,
        external_work=None,
        constraint_work=None,
        assembled=assembled,
        free_dof_indices=free,
        moment_reference_point_global=reference,
    )


def element_energy_sum(assembled: AssembledSystem, displacement: Sequence[float]) -> float:
    total = 0.0
    for element in assembled.elements:
        local = extract_element_vector(displacement, element.dof_indices)
        total += global_shell_energy(element.operator, local).total
    return total


def solve_linear_static(
    model: ValidatedModel,
    analysis_options: AnalysisOptions | None = None,
) -> LinearStaticResult:
    """Assemble, constrain and solve one validated linear static model."""

    options = analysis_options or model.analysis_options
    assembled = assemble_system(model, options)
    reference = _centroid([node.coordinates for node in model.nodes])
    prescribed = {item.dof_index: item.value for item in assembled.constraints}
    scales = characteristic_scales(assembled.dof_count, assembled.characteristic_length)
    raw = solve_constrained_symmetric(
        assembled.stiffness,
        assembled.applied_load,
        prescribed,
        scales=scales,
    )
    diagnostics = [item for item in model.diagnostics]
    if raw.status == "failed":
        diagnostics.append(
            _solve_diagnostic(
                "SHELL-SOLVE-E001",
                observed=raw.message or "singular",
                threshold="successful symmetric-direct factorization",
                unit=None,
            )
        )
        return _failed(
            diagnostics,
            assembled,
            displacement=raw.displacement,
            residual=raw.residual,
            free=raw.free_dof_indices,
            reference=reference,
        )

    backward = raw.scaled_relative_backward_error
    condition = raw.condition_estimate
    if backward is None or not math.isfinite(backward):
        diagnostics.append(
            _solve_diagnostic(
                "SHELL-SOLVE-E001",
                observed="non-finite backward error",
                threshold="finite scaled residual",
                unit=None,
            )
        )
        return _failed(
            diagnostics,
            assembled,
            displacement=raw.displacement,
            residual=raw.residual,
            free=raw.free_dof_indices,
            reference=reference,
        )
    if backward > options.solver.relative_backward_error_tolerance:
        diagnostics.append(
            _solve_diagnostic(
                "SHELL-SOLVE-E002",
                observed=backward,
                threshold=options.solver.relative_backward_error_tolerance,
                unit="1",
            )
        )
        return _failed(
            diagnostics,
            assembled,
            displacement=raw.displacement,
            residual=raw.residual,
            free=raw.free_dof_indices,
            reference=reference,
        )
    if condition is not None and condition >= options.solver.condition_warning_threshold:
        diagnostics.append(
            _solve_diagnostic(
                "SHELL-SOLVE-W001",
                observed=condition,
                threshold=options.solver.condition_warning_threshold,
                unit="1",
            )
        )

    constrained_nodes = []
    seen: set[str] = set()
    for node in model.nodes:
        if any(item.node_id == node.id for item in assembled.constraints) and node.id not in seen:
            constrained_nodes.append(node.id)
            seen.add(node.id)

    force_error, moment_error = _force_moment_errors(
        model,
        assembled.applied_load,
        raw.residual,
        constrained_nodes,
        reference,
        assembled.characteristic_length,
    )
    energy = 0.5 * quadratic_form(assembled.stiffness, raw.displacement)
    work = sum(
        raw.displacement[index] * assembled.applied_load[index]
        for index in range(assembled.dof_count)
    )
    constraint_work = sum(
        raw.displacement[index] * raw.residual[index] for index in raw.constrained_dof_indices
    )
    displacements = tuple(
        NodalDisplacement(
            node_id=node.id,
            translation_global=(
                raw.displacement[node.dof_indices[0]],
                raw.displacement[node.dof_indices[1]],
                raw.displacement[node.dof_indices[2]],
            ),
            rotation_global=(
                raw.displacement[node.dof_indices[3]],
                raw.displacement[node.dof_indices[4]],
                raw.displacement[node.dof_indices[5]],
            ),
        )
        for node in model.nodes
    )
    reactions = tuple(
        NodalReaction(
            node_id=node.id,
            force_global=(
                raw.residual[node.dof_indices[0]],
                raw.residual[node.dof_indices[1]],
                raw.residual[node.dof_indices[2]],
            ),
            moment_global=(
                raw.residual[node.dof_indices[3]],
                raw.residual[node.dof_indices[4]],
                raw.residual[node.dof_indices[5]],
            ),
        )
        for node in model.nodes
        if node.id in seen
    )
    solve_result = SolveResult(
        solver_status="succeeded",
        method="symmetric_direct",
        scaling="characteristic_length",
        precision="float64",
        dof_order_global=GLOBAL_DOF_ORDER,
        displacements=displacements,
        reactions=reactions,
        residual=ResidualReport(
            scaled_relative_backward_error=backward,
            force_equilibrium_relative_error=force_error,
            moment_equilibrium_relative_error=moment_error,
            condition_estimate=condition,
        ),
    )
    return LinearStaticResult(
        status="succeeded",
        diagnostics=sort_diagnostics(diagnostics),
        solve_result=solve_result,
        displacement_vector=raw.displacement,
        residual_vector=raw.residual,
        applied_load=assembled.applied_load,
        strain_energy=energy,
        external_work=work,
        constraint_work=constraint_work,
        assembled=assembled,
        free_dof_indices=raw.free_dof_indices,
        moment_reference_point_global=reference,
    )


__all__ = [
    "ConstrainedSolve",
    "LinearStaticResult",
    "characteristic_scales",
    "element_energy_sum",
    "jacobi_symmetric_eigh",
    "near_zero_eigenvalues",
    "norm2",
    "scale_stiffness",
    "solve_constrained_symmetric",
    "solve_linear_static",
]
