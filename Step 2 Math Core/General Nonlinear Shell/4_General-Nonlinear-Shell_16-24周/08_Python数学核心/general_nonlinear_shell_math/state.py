"""Transactional committed/trial shell state with deterministic hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

import numpy as np
from numpy.typing import ArrayLike


def _float_token(value: float) -> str:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("state values must be finite")
    return number.hex()


def _matrix3_tuple(
    value: ArrayLike, *, name: str
) -> tuple[tuple[float, float, float], ...]:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3), got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return tuple(tuple(float(component) for component in row) for row in matrix)


def _rotation_tuple(value: ArrayLike) -> tuple[tuple[float, float, float], ...]:
    result = _matrix3_tuple(value, name="rotation")
    matrix = np.asarray(result, dtype=float)
    if (
        np.linalg.norm(matrix.T @ matrix - np.eye(3)) > 1.0e-10
        or abs(np.linalg.det(matrix) - 1.0) > 1.0e-10
    ):
        raise ValueError("rotation must be a proper orthogonal matrix")
    return result


def _vector3_tuple(
    value: ArrayLike, *, name: str, require_unit: bool = False
) -> tuple[float, float, float]:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    if require_unit and abs(np.linalg.norm(vector) - 1.0) > 1.0e-10:
        raise ValueError(f"{name} must have unit length")
    return tuple(float(component) for component in vector)


def _points3_tuple(
    values: Sequence[ArrayLike],
) -> tuple[tuple[float, float, float], ...]:
    return tuple(_vector3_tuple(value, name="nodal coordinate") for value in values)


@dataclass(frozen=True)
class CommittedShellState:
    load_factor: float
    rotation: tuple[tuple[float, float, float], ...]
    director: tuple[float, float, float]
    nodal_coordinates: tuple[tuple[float, float, float], ...]
    thickness: float
    plastic_strain: tuple[float, ...]
    hardening: tuple[float, ...]
    plane_stress_unknowns: tuple[float, ...]
    local_basis: tuple[tuple[float, float, float], ...]
    stabilization_history: tuple[float, ...]
    energy_accumulator: float
    active_flags: tuple[bool, ...]

    @classmethod
    def create(
        cls,
        *,
        load_factor: float,
        rotation: ArrayLike,
        thickness: float,
        plastic_strain: Sequence[float],
        hardening: Sequence[float],
        director: ArrayLike = (0.0, 0.0, 1.0),
        nodal_coordinates: Sequence[ArrayLike] = (),
        plane_stress_unknowns: Sequence[float] = (),
        local_basis: Optional[ArrayLike] = None,
        stabilization_history: Sequence[float] = (),
        energy_accumulator: float = 0.0,
        active_flags: Sequence[bool] = (),
    ) -> CommittedShellState:
        if len(plastic_strain) != len(hardening):
            raise ValueError("plastic_strain and hardening must have the same length")
        if len(plane_stress_unknowns) > 0 and len(plane_stress_unknowns) != len(
            plastic_strain
        ):
            raise ValueError(
                "plane_stress_unknowns must be empty or match the material-point count"
            )
        if len(active_flags) > 0 and len(active_flags) != len(plastic_strain):
            raise ValueError(
                "active_flags must be empty or match the material-point count"
            )
        local_basis_value = np.eye(3) if local_basis is None else local_basis
        state = cls(
            load_factor=float(load_factor),
            rotation=_rotation_tuple(rotation),
            director=_vector3_tuple(director, name="director", require_unit=True),
            nodal_coordinates=_points3_tuple(nodal_coordinates),
            thickness=float(thickness),
            plastic_strain=tuple(float(value) for value in plastic_strain),
            hardening=tuple(float(value) for value in hardening),
            plane_stress_unknowns=tuple(
                float(value) for value in plane_stress_unknowns
            ),
            local_basis=_matrix3_tuple(local_basis_value, name="local_basis"),
            stabilization_history=tuple(
                float(value) for value in stabilization_history
            ),
            energy_accumulator=float(energy_accumulator),
            active_flags=tuple(bool(value) for value in active_flags),
        )
        state.canonical_payload()
        if state.thickness <= 0.0:
            raise ValueError("thickness must be positive")
        return state

    def canonical_payload(self) -> dict[str, object]:
        return {
            "active_flags": list(self.active_flags),
            "director": [_float_token(value) for value in self.director],
            "energy_accumulator": _float_token(self.energy_accumulator),
            "hardening": [_float_token(value) for value in self.hardening],
            "load_factor": _float_token(self.load_factor),
            "local_basis": [
                [_float_token(value) for value in row] for row in self.local_basis
            ],
            "nodal_coordinates": [
                [_float_token(value) for value in point]
                for point in self.nodal_coordinates
            ],
            "plane_stress_unknowns": [
                _float_token(value) for value in self.plane_stress_unknowns
            ],
            "plastic_strain": [_float_token(value) for value in self.plastic_strain],
            "rotation": [
                [_float_token(value) for value in row] for row in self.rotation
            ],
            "stabilization_history": [
                _float_token(value) for value in self.stabilization_history
            ],
            "thickness": _float_token(self.thickness),
        }

    def sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()


@dataclass
class TrialShellState:
    load_factor: float
    rotation: list[list[float]]
    director: list[float]
    nodal_coordinates: list[list[float]]
    thickness: float
    plastic_strain: list[float]
    hardening: list[float]
    plane_stress_unknowns: list[float]
    local_basis: list[list[float]]
    stabilization_history: list[float]
    energy_accumulator: float
    active_flags: list[bool]
    trial_stress: list[float]
    local_plastic_multiplier: list[float]
    local_newton_initial_guess: list[float]
    director_normalization_cache: list[float]
    current_local_basis_cache: list[list[float]]
    trial_energy_increment: float

    @classmethod
    def from_committed(cls, committed: CommittedShellState) -> TrialShellState:
        return cls(
            load_factor=committed.load_factor,
            rotation=[list(row) for row in committed.rotation],
            director=list(committed.director),
            nodal_coordinates=[list(point) for point in committed.nodal_coordinates],
            thickness=committed.thickness,
            plastic_strain=list(committed.plastic_strain),
            hardening=list(committed.hardening),
            plane_stress_unknowns=list(committed.plane_stress_unknowns),
            local_basis=[list(row) for row in committed.local_basis],
            stabilization_history=list(committed.stabilization_history),
            energy_accumulator=committed.energy_accumulator,
            active_flags=list(committed.active_flags),
            trial_stress=[0.0 for _ in committed.plastic_strain],
            local_plastic_multiplier=[0.0 for _ in committed.plastic_strain],
            local_newton_initial_guess=[0.0 for _ in committed.plastic_strain],
            director_normalization_cache=[],
            current_local_basis_cache=[],
            trial_energy_increment=0.0,
        )

    def commit(self) -> CommittedShellState:
        return CommittedShellState.create(
            load_factor=self.load_factor,
            rotation=self.rotation,
            director=self.director,
            nodal_coordinates=self.nodal_coordinates,
            thickness=self.thickness,
            plastic_strain=self.plastic_strain,
            hardening=self.hardening,
            plane_stress_unknowns=self.plane_stress_unknowns,
            local_basis=self.local_basis,
            stabilization_history=self.stabilization_history,
            energy_accumulator=self.energy_accumulator,
            active_flags=self.active_flags,
        )


@dataclass
class StateTransaction:
    """Keep the base snapshot immutable until :meth:`commit` is called."""

    committed: CommittedShellState

    def __post_init__(self) -> None:
        self.trial = TrialShellState.from_committed(self.committed)

    def rollback(self) -> TrialShellState:
        self.trial = TrialShellState.from_committed(self.committed)
        return self.trial

    def commit(self) -> CommittedShellState:
        self.committed = self.trial.commit()
        self.trial = TrialShellState.from_committed(self.committed)
        return self.committed
