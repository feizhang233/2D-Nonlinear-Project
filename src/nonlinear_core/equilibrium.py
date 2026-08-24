"""P3 residual, effective-tangent, constraint, correction and reaction algebra."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nonlinear_core.adapters import ModelAdapter, ModelResponse
from nonlinear_core.linear_solver import (
    LinearSolveOptions,
    LinearSolveResult,
    solve_linear_system,
)
from nonlinear_core.model import ModelInput

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def _readonly_float(value: ArrayLike, *, ndim: int | None = None) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if ndim is not None and result.ndim != ndim:
        raise ValueError(f"expected a {ndim}-dimensional float array; got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError("equilibrium arrays must contain only finite values")
    result.setflags(write=False)
    return result


def _readonly_int(value: ArrayLike) -> IntArray:
    result = np.array(value, dtype=np.int64, copy=True)
    if result.ndim != 1:
        raise ValueError("DOF index arrays must be one-dimensional")
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class ConstraintPartition:
    """Stable full/free/constrained DOF partition with prescribed values."""

    size: int
    free_dofs: IntArray
    constrained_dofs: IntArray
    prescribed_values: FloatArray

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("partition size must be non-negative")
        free = _readonly_int(self.free_dofs)
        constrained = _readonly_int(self.constrained_dofs)
        prescribed = _readonly_float(self.prescribed_values, ndim=1)
        if prescribed.shape != constrained.shape:
            raise ValueError("prescribed_values must match constrained_dofs")
        all_indices = np.concatenate((free, constrained))
        if (
            all_indices.size != self.size
            or np.any(all_indices < 0)
            or np.any(all_indices >= self.size)
            or len(set(int(value) for value in all_indices)) != self.size
        ):
            raise ValueError("free and constrained DOFs must partition the complete system")
        object.__setattr__(self, "free_dofs", free)
        object.__setattr__(self, "constrained_dofs", constrained)
        object.__setattr__(self, "prescribed_values", prescribed)

    @classmethod
    def from_mapping(
        cls,
        size: int,
        constraints: Mapping[int, float],
    ) -> ConstraintPartition:
        normalized: dict[int, float] = {}
        for raw_index, raw_value in constraints.items():
            if isinstance(raw_index, bool) or not isinstance(raw_index, (int, np.integer)):
                raise TypeError("constraint DOF indices must be integers")
            index = int(raw_index)
            if index < 0 or index >= size:
                raise ValueError(f"constraint DOF {index} is outside [0,{size - 1}]")
            value = float(raw_value)
            if not np.isfinite(value):
                raise ValueError(f"constraint value at DOF {index} must be finite")
            normalized[index] = value
        constrained = np.asarray(sorted(normalized), dtype=np.int64)
        free = np.setdiff1d(np.arange(size, dtype=np.int64), constrained, assume_unique=True)
        prescribed = np.asarray([normalized[int(index)] for index in constrained], dtype=float)
        return cls(size, free, constrained, prescribed)


@dataclass(frozen=True, slots=True)
class TangentDiagnostics:
    symmetry_error: float
    symmetry_tolerance: float
    is_symmetric: bool
    definiteness_evaluated: bool = False

    def __post_init__(self) -> None:
        if self.symmetry_tolerance <= 0.0 or not np.isfinite(self.symmetry_tolerance):
            raise ValueError("symmetry_tolerance must be positive and finite")
        if self.symmetry_error < 0.0 or not np.isfinite(self.symmetry_error):
            raise ValueError("symmetry_error must be non-negative and finite")
        if self.definiteness_evaluated:
            raise ValueError("P3 interface does not evaluate or assume tangent definiteness")


@dataclass(frozen=True, slots=True)
class EquilibriumEvaluation:
    """One full and partitioned residual/effective-tangent evaluation."""

    response: ModelResponse
    partition: ConstraintPartition
    residual: FloatArray
    free_residual: FloatArray
    constrained_residual: FloatArray
    effective_tangent: FloatArray
    tangent_diagnostics: TangentDiagnostics

    def __post_init__(self) -> None:
        size = self.partition.size
        residual = _readonly_float(self.residual, ndim=1)
        free_residual = _readonly_float(self.free_residual, ndim=1)
        constrained_residual = _readonly_float(self.constrained_residual, ndim=1)
        tangent = _readonly_float(self.effective_tangent, ndim=2)
        if residual.shape != (size,):
            raise ValueError("residual size does not match the DOF partition")
        if free_residual.shape != self.partition.free_dofs.shape:
            raise ValueError("free_residual size does not match free_dofs")
        if constrained_residual.shape != self.partition.constrained_dofs.shape:
            raise ValueError("constrained_residual size does not match constrained_dofs")
        if tangent.shape != (size, size):
            raise ValueError("effective_tangent size does not match the DOF partition")
        object.__setattr__(self, "residual", residual)
        object.__setattr__(self, "free_residual", free_residual)
        object.__setattr__(self, "constrained_residual", constrained_residual)
        object.__setattr__(self, "effective_tangent", tangent)


@dataclass(frozen=True, slots=True)
class ReactionRecovery:
    """Algebraic support/controller forces with the structural sign convention."""

    full_imbalance: FloatArray
    constrained_dofs: IntArray
    constrained_reactions: FloatArray

    def __post_init__(self) -> None:
        full = _readonly_float(self.full_imbalance, ndim=1)
        constrained = _readonly_int(self.constrained_dofs)
        reactions = _readonly_float(self.constrained_reactions, ndim=1)
        if constrained.shape != reactions.shape:
            raise ValueError("constrained reaction values must match constrained DOFs")
        object.__setattr__(self, "full_imbalance", full)
        object.__setattr__(self, "constrained_dofs", constrained)
        object.__setattr__(self, "constrained_reactions", reactions)


class CorrectionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NewtonCorrectionResult:
    """One constrained Newton equation result; this is not a convergence claim."""

    status: CorrectionStatus
    linear_result: LinearSolveResult
    correction: FloatArray | None
    free_correction: FloatArray | None
    constrained_correction: FloatArray
    predicted_residual: FloatArray | None
    predicted_free_residual: FloatArray | None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", CorrectionStatus(self.status))
        constrained = _readonly_float(self.constrained_correction, ndim=1)
        object.__setattr__(self, "constrained_correction", constrained)
        for name in (
            "correction",
            "free_correction",
            "predicted_residual",
            "predicted_free_residual",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _readonly_float(value, ndim=1))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))
        if self.status is CorrectionStatus.SUCCEEDED:
            if not self.linear_result.succeeded or self.correction is None:
                raise ValueError("successful corrections require a successful linear solve")
        elif self.linear_result.succeeded:
            raise ValueError("failed corrections require a failed linear solve")

    @property
    def succeeded(self) -> bool:
        return self.status is CorrectionStatus.SUCCEEDED


def build_equilibrium(
    response: ModelResponse,
    constraints: Mapping[int, float],
    *,
    symmetry_tolerance: float = 1.0e-12,
) -> EquilibriumEvaluation:
    """Build ``r=f_ext-f_int`` and ``K_eff=K_int-K_ext`` without elimination."""

    size = response.internal_force.size
    partition = ConstraintPartition.from_mapping(size, constraints)
    residual = response.external_force - response.internal_force
    external_tangent = (
        np.zeros_like(response.tangent)
        if response.external_tangent is None
        else response.external_tangent
    )
    effective_tangent = response.tangent - external_tangent
    matrix_norm = float(np.linalg.norm(effective_tangent, ord="fro"))
    symmetry_error = float(
        np.linalg.norm(effective_tangent - effective_tangent.T, ord="fro")
        / max(matrix_norm, np.finfo(float).tiny)
    )
    diagnostics = TangentDiagnostics(
        symmetry_error=symmetry_error,
        symmetry_tolerance=float(symmetry_tolerance),
        is_symmetric=symmetry_error <= symmetry_tolerance,
    )
    return EquilibriumEvaluation(
        response=response,
        partition=partition,
        residual=residual,
        free_residual=residual[partition.free_dofs],
        constrained_residual=residual[partition.constrained_dofs],
        effective_tangent=effective_tangent,
        tangent_diagnostics=diagnostics,
    )


def evaluate_equilibrium(
    adapter: ModelAdapter,
    model: ModelInput,
    displacement: ArrayLike,
    *,
    load_factor: float = 1.0,
    symmetry_tolerance: float = 1.0e-12,
) -> EquilibriumEvaluation:
    response = adapter.evaluate(model, displacement, load_factor=load_factor)
    return build_equilibrium(
        response,
        adapter.constraint_map(model),
        symmetry_tolerance=symmetry_tolerance,
    )


def solve_constrained_correction(
    evaluation: EquilibriumEvaluation,
    current_displacement: ArrayLike,
    options: LinearSolveOptions | None = None,
) -> NewtonCorrectionResult:
    """Solve the free block while enforcing absolute zero/nonzero prescribed values."""

    partition = evaluation.partition
    current = _readonly_float(current_displacement, ndim=1)
    if current.shape != (partition.size,):
        raise ValueError("current_displacement size does not match the equilibrium system")
    constrained_correction = partition.prescribed_values - current[partition.constrained_dofs]
    free = partition.free_dofs
    constrained = partition.constrained_dofs
    free_tangent = evaluation.effective_tangent[np.ix_(free, free)]
    coupling = evaluation.effective_tangent[np.ix_(free, constrained)]
    free_rhs = evaluation.free_residual - coupling @ constrained_correction
    linear_result = solve_linear_system(free_tangent, free_rhs, options)
    diagnostics: dict[str, Any] = {
        "free_dofs": tuple(int(value) for value in free),
        "constrained_dofs": tuple(int(value) for value in constrained),
    }
    if not linear_result.succeeded:
        if linear_result.nullity is not None:
            diagnostics["estimated_rigid_or_unconstrained_modes"] = linear_result.nullity
        return NewtonCorrectionResult(
            status=CorrectionStatus.FAILED,
            linear_result=linear_result,
            correction=None,
            free_correction=None,
            constrained_correction=constrained_correction,
            predicted_residual=None,
            predicted_free_residual=None,
            diagnostics=diagnostics,
        )
    assert linear_result.solution is not None
    correction = np.zeros(partition.size, dtype=float)
    correction[free] = linear_result.solution
    correction[constrained] = constrained_correction
    predicted_residual = evaluation.residual - evaluation.effective_tangent @ correction
    return NewtonCorrectionResult(
        status=CorrectionStatus.SUCCEEDED,
        linear_result=linear_result,
        correction=correction,
        free_correction=linear_result.solution,
        constrained_correction=constrained_correction,
        predicted_residual=predicted_residual,
        predicted_free_residual=predicted_residual[free],
        diagnostics=diagnostics,
    )


def recover_constraint_reactions(evaluation: EquilibriumEvaluation) -> ReactionRecovery:
    """Return ``f_int-f_ext=-r`` at constrained DOFs after equilibrium."""

    full_imbalance = -evaluation.residual
    constrained = evaluation.partition.constrained_dofs
    return ReactionRecovery(
        full_imbalance=full_imbalance,
        constrained_dofs=constrained,
        constrained_reactions=full_imbalance[constrained],
    )


__all__ = [
    "ConstraintPartition",
    "CorrectionStatus",
    "EquilibriumEvaluation",
    "NewtonCorrectionResult",
    "ReactionRecovery",
    "TangentDiagnostics",
    "build_equilibrium",
    "evaluate_equilibrium",
    "recover_constraint_reactions",
    "solve_constrained_correction",
]
