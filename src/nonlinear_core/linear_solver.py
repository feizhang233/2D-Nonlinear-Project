"""P3 classified linear solves with dense and sparse-LU verification paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


class LinearSolverBackend(StrEnum):
    AUTO = "auto"
    DENSE = "dense"
    SPARSE_LU = "sparse_lu"


class LinearSolveStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LinearFailureCode(StrEnum):
    DIMENSION_MISMATCH = "LINEAR_DIMENSION_MISMATCH"
    NONFINITE_INPUT = "LINEAR_NONFINITE_INPUT"
    SINGULAR_SYSTEM = "LINEAR_SINGULAR_SYSTEM"
    ILL_CONDITIONED_SYSTEM = "LINEAR_ILL_CONDITIONED_SYSTEM"
    BACKEND_UNAVAILABLE = "LINEAR_BACKEND_UNAVAILABLE"
    FACTORIZATION_FAILED = "LINEAR_FACTORIZATION_FAILED"
    NONFINITE_RESULT = "LINEAR_NONFINITE_RESULT"
    EXCESSIVE_RESIDUAL = "LINEAR_EXCESSIVE_RESIDUAL"


@dataclass(frozen=True, slots=True)
class LinearSolveOptions:
    """Numerical gates for one Newton correction solve."""

    backend: LinearSolverBackend = LinearSolverBackend.AUTO
    dense_threshold: int = 64
    equilibrate: bool = True
    rank_tolerance_factor: float = 10.0
    condition_warning_threshold: float = 1.0e10
    condition_error_threshold: float = 1.0e15
    relative_residual_tolerance: float = 1.0e-10

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend", LinearSolverBackend(self.backend))
        if self.dense_threshold < 1:
            raise ValueError("dense_threshold must be positive")
        for name in (
            "rank_tolerance_factor",
            "condition_warning_threshold",
            "condition_error_threshold",
            "relative_residual_tolerance",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be a positive finite number")
        if self.condition_warning_threshold >= self.condition_error_threshold:
            raise ValueError("condition_warning_threshold must be below condition_error_threshold")


@dataclass(frozen=True, slots=True)
class LinearSolveFailure:
    code: LinearFailureCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True, slots=True)
class LinearSolveResult:
    """Linear result retaining the actual equation residual ``A x - b``."""

    status: LinearSolveStatus
    backend: LinearSolverBackend
    size: int
    solution: FloatArray | None
    residual: FloatArray | None
    residual_norm: float | None
    relative_residual: float | None
    rank: int | None
    nullity: int | None
    condition_estimate: float | None
    raw_condition_estimate: float | None
    warnings: tuple[str, ...] = ()
    failure: LinearSolveFailure | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", LinearSolveStatus(self.status))
        object.__setattr__(self, "backend", LinearSolverBackend(self.backend))
        if self.solution is not None:
            solution = np.array(self.solution, dtype=float, copy=True)
            solution.setflags(write=False)
            object.__setattr__(self, "solution", solution)
        if self.residual is not None:
            residual = np.array(self.residual, dtype=float, copy=True)
            residual.setflags(write=False)
            object.__setattr__(self, "residual", residual)
        if self.status is LinearSolveStatus.SUCCEEDED:
            if self.solution is None or self.residual is None or self.failure is not None:
                raise ValueError(
                    "successful linear solves require solution/residual and no failure"
                )
        elif self.failure is None:
            raise ValueError("failed linear solves require classified failure data")

    @property
    def succeeded(self) -> bool:
        return self.status is LinearSolveStatus.SUCCEEDED


def _as_dense_matrix(matrix: Any) -> FloatArray:
    if hasattr(matrix, "toarray"):
        return np.asarray(matrix.toarray(), dtype=float)
    return np.asarray(matrix, dtype=float)


def _failed(
    code: LinearFailureCode,
    message: str,
    *,
    backend: LinearSolverBackend,
    size: int,
    details: dict[str, Any] | None = None,
    solution: ArrayLike | None = None,
    residual: ArrayLike | None = None,
    residual_norm: float | None = None,
    relative_residual: float | None = None,
    rank: int | None = None,
    nullity: int | None = None,
    condition_estimate: float | None = None,
    raw_condition_estimate: float | None = None,
    warnings: tuple[str, ...] = (),
) -> LinearSolveResult:
    return LinearSolveResult(
        status=LinearSolveStatus.FAILED,
        backend=backend,
        size=size,
        solution=None if solution is None else np.asarray(solution, dtype=float),
        residual=None if residual is None else np.asarray(residual, dtype=float),
        residual_norm=residual_norm,
        relative_residual=relative_residual,
        rank=rank,
        nullity=nullity,
        condition_estimate=condition_estimate,
        raw_condition_estimate=raw_condition_estimate,
        warnings=warnings,
        failure=LinearSolveFailure(code=code, message=message, details=details or {}),
    )


def _actual_backend(options: LinearSolveOptions, size: int) -> LinearSolverBackend:
    if options.backend is not LinearSolverBackend.AUTO:
        return options.backend
    return (
        LinearSolverBackend.DENSE
        if size <= options.dense_threshold
        else LinearSolverBackend.SPARSE_LU
    )


def _condition(values: FloatArray) -> float:
    if values.size == 0:
        return 1.0
    largest = float(values[0])
    smallest = float(values[-1])
    return float("inf") if smallest == 0.0 else largest / smallest


def solve_linear_system(
    matrix: Any,
    right_hand_side: ArrayLike,
    options: LinearSolveOptions | None = None,
) -> LinearSolveResult:
    """Solve ``A X = B`` for one or more right-hand sides with one factorization."""

    settings = options or LinearSolveOptions()
    requested_backend = settings.backend
    try:
        coefficients = _as_dense_matrix(matrix)
        rhs = np.asarray(right_hand_side, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        return _failed(
            LinearFailureCode.DIMENSION_MISMATCH,
            f"matrix and right_hand_side must be numeric arrays: {error}",
            backend=requested_backend,
            size=0,
        )
    size = int(coefficients.shape[0]) if coefficients.ndim >= 1 else 0
    backend = _actual_backend(settings, size)
    rhs_shape_valid = (
        rhs.ndim in (1, 2) and rhs.shape[0] == size and (rhs.ndim == 1 or rhs.shape[1] > 0)
    )
    if coefficients.ndim != 2 or coefficients.shape != (size, size) or not rhs_shape_valid:
        return _failed(
            LinearFailureCode.DIMENSION_MISMATCH,
            (
                "matrix must be square and right_hand_side must be a vector or non-empty "
                "column matrix matching its row count"
            ),
            backend=backend,
            size=size,
            details={"matrix_shape": coefficients.shape, "rhs_shape": rhs.shape},
        )
    if not np.all(np.isfinite(coefficients)) or not np.all(np.isfinite(rhs)):
        return _failed(
            LinearFailureCode.NONFINITE_INPUT,
            "matrix and right_hand_side must contain only finite values",
            backend=backend,
            size=size,
        )
    if size == 0:
        empty = np.empty_like(rhs, dtype=float)
        return LinearSolveResult(
            status=LinearSolveStatus.SUCCEEDED,
            backend=LinearSolverBackend.DENSE,
            size=0,
            solution=empty,
            residual=empty,
            residual_norm=0.0,
            relative_residual=0.0,
            rank=0,
            nullity=0,
            condition_estimate=1.0,
            raw_condition_estimate=1.0,
        )

    try:
        raw_singular_values = np.linalg.svd(coefficients, compute_uv=False)
    except np.linalg.LinAlgError as error:
        return _failed(
            LinearFailureCode.FACTORIZATION_FAILED,
            f"SVD diagnostics failed: {error}",
            backend=backend,
            size=size,
        )
    raw_condition = _condition(raw_singular_values)

    row_factors = np.ones(size, dtype=float)
    column_factors = np.ones(size, dtype=float)
    scaled = coefficients.copy()
    scaled_rhs = rhs.copy()
    if settings.equilibrate:
        row_norms = np.max(np.abs(scaled), axis=1)
        if np.any(row_norms == 0.0):
            zero_rows = tuple(int(index) for index in np.flatnonzero(row_norms == 0.0))
            return _failed(
                LinearFailureCode.SINGULAR_SYSTEM,
                "matrix contains zero rows and cannot define a unique correction",
                backend=backend,
                size=size,
                details={"zero_rows": zero_rows, "estimated_nullity": len(zero_rows)},
                rank=size - len(zero_rows),
                nullity=len(zero_rows),
                condition_estimate=float("inf"),
                raw_condition_estimate=raw_condition,
            )
        row_factors = 1.0 / row_norms
        scaled = row_factors[:, None] * scaled
        scaled_rhs = (
            row_factors * scaled_rhs if rhs.ndim == 1 else row_factors[:, None] * scaled_rhs
        )
        column_norms = np.max(np.abs(scaled), axis=0)
        if np.any(column_norms == 0.0):
            zero_columns = tuple(int(index) for index in np.flatnonzero(column_norms == 0.0))
            return _failed(
                LinearFailureCode.SINGULAR_SYSTEM,
                "matrix contains zero columns and cannot define a unique correction",
                backend=backend,
                size=size,
                details={"zero_columns": zero_columns, "estimated_nullity": len(zero_columns)},
                rank=size - len(zero_columns),
                nullity=len(zero_columns),
                condition_estimate=float("inf"),
                raw_condition_estimate=raw_condition,
            )
        column_factors = 1.0 / column_norms
        scaled = scaled * column_factors[None, :]

    try:
        singular_values = np.linalg.svd(scaled, compute_uv=False)
    except np.linalg.LinAlgError as error:
        return _failed(
            LinearFailureCode.FACTORIZATION_FAILED,
            f"scaled SVD diagnostics failed: {error}",
            backend=backend,
            size=size,
            raw_condition_estimate=raw_condition,
        )
    largest = float(singular_values[0])
    rank_threshold = settings.rank_tolerance_factor * np.finfo(float).eps * max(size, 1) * largest
    rank = int(np.count_nonzero(singular_values > rank_threshold))
    nullity = size - rank
    condition = _condition(singular_values)
    diagnostics = {
        "rank_threshold": rank_threshold,
        "smallest_singular_value": float(singular_values[-1]),
        "estimated_nullity": nullity,
    }
    if rank < size:
        return _failed(
            LinearFailureCode.SINGULAR_SYSTEM,
            f"linear system is rank deficient: rank {rank} of {size}",
            backend=backend,
            size=size,
            details=diagnostics,
            rank=rank,
            nullity=nullity,
            condition_estimate=condition,
            raw_condition_estimate=raw_condition,
        )
    if condition >= settings.condition_error_threshold:
        return _failed(
            LinearFailureCode.ILL_CONDITIONED_SYSTEM,
            "scaled condition estimate exceeds the configured error threshold",
            backend=backend,
            size=size,
            details={**diagnostics, "threshold": settings.condition_error_threshold},
            rank=rank,
            nullity=nullity,
            condition_estimate=condition,
            raw_condition_estimate=raw_condition,
        )
    warnings = ()
    if condition >= settings.condition_warning_threshold:
        warnings = ("scaled condition estimate exceeds condition_warning_threshold",)

    try:
        if backend is LinearSolverBackend.DENSE:
            scaled_solution = np.linalg.solve(scaled, scaled_rhs)
        else:
            try:
                from scipy.sparse import csc_matrix
                from scipy.sparse.linalg import splu
            except ImportError as error:
                return _failed(
                    LinearFailureCode.BACKEND_UNAVAILABLE,
                    f"SciPy sparse LU is unavailable: {error}",
                    backend=backend,
                    size=size,
                    rank=rank,
                    nullity=nullity,
                    condition_estimate=condition,
                    raw_condition_estimate=raw_condition,
                )
            factor = splu(csc_matrix(scaled), permc_spec="COLAMD", diag_pivot_thresh=1.0)
            scaled_solution = factor.solve(scaled_rhs)
    except (np.linalg.LinAlgError, RuntimeError, ValueError) as error:
        return _failed(
            LinearFailureCode.FACTORIZATION_FAILED,
            f"{backend.value} factorization/solve failed: {error}",
            backend=backend,
            size=size,
            rank=rank,
            nullity=nullity,
            condition_estimate=condition,
            raw_condition_estimate=raw_condition,
            warnings=warnings,
        )

    scaled_solution = np.asarray(scaled_solution, dtype=float)
    solution = (
        column_factors * scaled_solution
        if rhs.ndim == 1
        else column_factors[:, None] * scaled_solution
    )
    if not np.all(np.isfinite(solution)):
        return _failed(
            LinearFailureCode.NONFINITE_RESULT,
            "linear solve produced a non-finite correction",
            backend=backend,
            size=size,
            rank=rank,
            nullity=nullity,
            condition_estimate=condition,
            raw_condition_estimate=raw_condition,
            warnings=warnings,
        )
    residual = coefficients @ solution - rhs
    if not np.all(np.isfinite(residual)):
        return _failed(
            LinearFailureCode.NONFINITE_RESULT,
            "linear residual contains non-finite values",
            backend=backend,
            size=size,
            solution=solution,
            rank=rank,
            nullity=nullity,
            condition_estimate=condition,
            raw_condition_estimate=raw_condition,
            warnings=warnings,
        )
    residual_norm = float(np.linalg.norm(residual))
    relative_residual = residual_norm / max(
        float(np.linalg.norm(rhs)),
        float(np.linalg.norm(coefficients, ord=np.inf)) * float(np.linalg.norm(solution)),
        np.finfo(float).tiny,
    )
    if relative_residual > settings.relative_residual_tolerance:
        return _failed(
            LinearFailureCode.EXCESSIVE_RESIDUAL,
            "actual linear residual exceeds the configured tolerance",
            backend=backend,
            size=size,
            details={"threshold": settings.relative_residual_tolerance},
            solution=solution,
            residual=residual,
            residual_norm=residual_norm,
            relative_residual=relative_residual,
            rank=rank,
            nullity=nullity,
            condition_estimate=condition,
            raw_condition_estimate=raw_condition,
            warnings=warnings,
        )
    return LinearSolveResult(
        status=LinearSolveStatus.SUCCEEDED,
        backend=backend,
        size=size,
        solution=solution,
        residual=residual,
        residual_norm=residual_norm,
        relative_residual=relative_residual,
        rank=rank,
        nullity=nullity,
        condition_estimate=condition,
        raw_condition_estimate=raw_condition,
        warnings=warnings,
    )


__all__ = [
    "LinearFailureCode",
    "LinearSolveFailure",
    "LinearSolveOptions",
    "LinearSolveResult",
    "LinearSolveStatus",
    "LinearSolverBackend",
    "solve_linear_system",
]
