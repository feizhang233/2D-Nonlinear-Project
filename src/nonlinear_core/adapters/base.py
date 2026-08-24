"""Unified P2 adapter contracts for the four linear reference cores.

The adapter layer owns translation only.  Element mathematics remains in the
installed ``continuum_math``, ``frame2d``, ``mindlin_plate`` and ``shell_core``
packages.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nonlinear_core.contracts import canonical_model_json
from nonlinear_core.model import DofRef, ModelFamily, ModelInput

FloatArray = NDArray[np.float64]


def _readonly_vector(value: ArrayLike, *, size: int | None = None) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.ndim != 1 or (size is not None and result.shape != (size,)):
        expected = "a vector" if size is None else f"shape ({size},)"
        raise ValueError(f"expected {expected}; got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError("response vectors must contain only finite values")
    result.setflags(write=False)
    return result


def _readonly_matrix(value: ArrayLike, *, size: int | None = None) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    expected_shape = None if size is None else (size, size)
    if result.ndim != 2 or (expected_shape is not None and result.shape != expected_shape):
        expected = "a matrix" if size is None else f"shape {expected_shape}"
        raise ValueError(f"expected {expected}; got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError("response matrices must contain only finite values")
    result.setflags(write=False)
    return result


def _frozen_mapping(value: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class AdapterIssue:
    """One adapter-level validation or dependency issue."""

    code: str
    message: str
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class AdapterValidation:
    """Non-throwing validation result used at the solver/adapter boundary."""

    errors: tuple[AdapterIssue, ...] = ()
    warnings: tuple[AdapterIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class AdapterState:
    """Immutable trial/committed state token passed through nonlinear solvers."""

    model_id: str
    model_family: ModelFamily
    adapter_id: str
    core_package: str
    core_version: str
    state_id: str
    committed: bool = False
    history: Mapping[str, Any] = field(default_factory=_frozen_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "history", _frozen_mapping(self.history))


@dataclass(frozen=True, slots=True)
class LocalFailure:
    """Element-local failure retained as data instead of an untyped string."""

    code: str
    message: str
    element_id: str | None = None


@dataclass(frozen=True, slots=True)
class ElementResponse:
    """Unified element contribution in the model-global DOF basis."""

    element_id: str
    dof_indices: tuple[int, ...]
    internal_force: FloatArray
    tangent: FloatArray
    external_force: FloatArray
    energy: float
    min_det_j: float | None = None
    min_det_f: float | None = None
    local_failures: tuple[LocalFailure, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=_frozen_mapping)

    def __post_init__(self) -> None:
        size = len(self.dof_indices)
        object.__setattr__(self, "internal_force", _readonly_vector(self.internal_force, size=size))
        object.__setattr__(self, "external_force", _readonly_vector(self.external_force, size=size))
        object.__setattr__(self, "tangent", _readonly_matrix(self.tangent, size=size))
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """Unified global response consumed by later nonlinear solution drivers."""

    internal_force: FloatArray
    tangent: FloatArray
    external_force: FloatArray
    external_tangent: FloatArray | None
    trial_state: AdapterState
    elements: tuple[ElementResponse, ...]
    strain_energy: float
    min_det_j: float | None = None
    min_det_f: float | None = None
    local_failures: tuple[LocalFailure, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=_frozen_mapping)

    def __post_init__(self) -> None:
        size = int(np.asarray(self.internal_force).size)
        object.__setattr__(self, "internal_force", _readonly_vector(self.internal_force, size=size))
        object.__setattr__(self, "external_force", _readonly_vector(self.external_force, size=size))
        object.__setattr__(self, "tangent", _readonly_matrix(self.tangent, size=size))
        if self.external_tangent is not None:
            object.__setattr__(
                self,
                "external_tangent",
                _readonly_matrix(self.external_tangent, size=size),
            )
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class AdapterRecovery:
    """Common displacement, reaction and energy recovery result."""

    displacement: FloatArray
    reactions: FloatArray
    strain_energy: float
    element_data: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=_frozen_mapping)

    def __post_init__(self) -> None:
        displacement = _readonly_vector(self.displacement)
        object.__setattr__(self, "displacement", displacement)
        object.__setattr__(
            self,
            "reactions",
            _readonly_vector(self.reactions, size=displacement.size),
        )
        object.__setattr__(
            self,
            "element_data",
            tuple(_frozen_mapping(item) for item in self.element_data),
        )
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class NativeElement:
    """Private normalized element operator returned by one core translator."""

    element_id: str
    dof_indices: tuple[int, ...]
    stiffness: FloatArray
    force: FloatArray
    min_det_j: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=_frozen_mapping)


@dataclass(frozen=True, slots=True)
class NativeSystem:
    """Private common representation assembled only through a core public API."""

    stiffness: FloatArray
    force: FloatArray
    elements: tuple[NativeElement, ...]
    native_model: Any
    native_context: Mapping[str, Any] = field(default_factory=_frozen_mapping)


@runtime_checkable
class ModelAdapter(Protocol):
    """P2 protocol: later solvers depend on this, never on element type."""

    family: ModelFamily
    adapter_id: str
    core_package: str
    core_version: str

    def validate(self, model: ModelInput) -> AdapterValidation: ...

    def initial_state(self, model: ModelInput) -> AdapterState: ...

    def dof_map(self, model: ModelInput) -> tuple[DofRef, ...]: ...

    def constraint_map(self, model: ModelInput) -> Mapping[int, float]: ...

    def evaluate(
        self,
        model: ModelInput,
        displacement: ArrayLike,
        *,
        load_factor: float = 1.0,
        committed_state: AdapterState | None = None,
    ) -> ModelResponse: ...

    def recover(
        self,
        model: ModelInput,
        displacement: ArrayLike,
        *,
        load_factor: float = 1.0,
        committed_state: AdapterState | None = None,
    ) -> AdapterRecovery: ...


class LinearCoreAdapter(ABC):
    """Shared exact-linear behavior; subclasses only translate core inputs."""

    family: ClassVar[ModelFamily]
    adapter_id: ClassVar[str]
    core_package: ClassVar[str]
    core_version: ClassVar[str]

    def validate(self, model: ModelInput) -> AdapterValidation:
        try:
            self._require_family(model)
            self._build_native_system(model)
        except ModuleNotFoundError as error:
            return AdapterValidation(
                errors=(
                    AdapterIssue(
                        code="ADAPTER_DEPENDENCY_MISSING",
                        message=f"required package is not installed: {error.name}",
                    ),
                )
            )
        except (AssertionError, TypeError, ValueError, KeyError, RuntimeError) as error:
            return AdapterValidation(
                errors=(AdapterIssue(code="ADAPTER_MODEL_INVALID", message=str(error)),)
            )
        return AdapterValidation()

    def initial_state(self, model: ModelInput) -> AdapterState:
        self._require_family(model)
        digest = hashlib.sha256(canonical_model_json(model).encode("utf-8")).hexdigest()
        return AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=f"initial:{digest}",
        )

    def dof_map(self, model: ModelInput) -> tuple[DofRef, ...]:
        self._require_family(model)
        return model.ordered_dof_refs()

    def constraint_map(self, model: ModelInput) -> Mapping[int, float]:
        dof_lookup = {
            (reference.node_id, reference.dof): index
            for index, reference in enumerate(self.dof_map(model))
        }
        return MappingProxyType(
            {
                dof_lookup[(constraint.node_id, constraint.dof)]: float(constraint.value)
                for constraint in model.constraints
            }
        )

    def evaluate(
        self,
        model: ModelInput,
        displacement: ArrayLike,
        *,
        load_factor: float = 1.0,
        committed_state: AdapterState | None = None,
    ) -> ModelResponse:
        self._require_family(model)
        system = self._build_native_system(model)
        size = system.force.size
        vector = _readonly_vector(displacement, size=size)
        factor = float(load_factor)
        if not np.isfinite(factor):
            raise ValueError("load_factor must be finite")
        if committed_state is not None:
            self._require_compatible_state(model, committed_state)

        internal_force = system.stiffness @ vector
        external_force = factor * system.force
        element_responses: list[ElementResponse] = []
        for element in system.elements:
            dofs = np.asarray(element.dof_indices, dtype=np.intp)
            local_displacement = vector[dofs]
            local_internal = element.stiffness @ local_displacement
            element_responses.append(
                ElementResponse(
                    element_id=element.element_id,
                    dof_indices=element.dof_indices,
                    internal_force=local_internal,
                    tangent=element.stiffness,
                    external_force=factor * element.force,
                    energy=float(0.5 * local_displacement @ local_internal),
                    min_det_j=element.min_det_j,
                    min_det_f=None,
                    metadata=element.metadata,
                )
            )

        energy = float(0.5 * vector @ internal_force)
        digest_source = np.concatenate((vector, np.array([factor], dtype=float))).tobytes()
        trial_state = AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=f"trial:{hashlib.sha256(digest_source).hexdigest()}",
            history={"load_factor": factor, "strain_energy": energy},
        )
        det_j_values = [item.min_det_j for item in element_responses if item.min_det_j is not None]
        return ModelResponse(
            internal_force=internal_force,
            tangent=system.stiffness,
            external_force=external_force,
            external_tangent=None,
            trial_state=trial_state,
            elements=tuple(element_responses),
            strain_energy=energy,
            min_det_j=min(det_j_values) if det_j_values else None,
            min_det_f=None,
            metadata={
                "linear_reference": True,
                "dof_order": tuple(reference.dof.value for reference in self.dof_map(model)),
            },
        )

    def recover(
        self,
        model: ModelInput,
        displacement: ArrayLike,
        *,
        load_factor: float = 1.0,
        committed_state: AdapterState | None = None,
    ) -> AdapterRecovery:
        response = self.evaluate(
            model,
            displacement,
            load_factor=load_factor,
            committed_state=committed_state,
        )
        reactions = response.internal_force - response.external_force
        return AdapterRecovery(
            displacement=displacement,
            reactions=reactions,
            strain_energy=response.strain_energy,
            element_data=tuple(
                {
                    "element_id": item.element_id,
                    "energy": item.energy,
                    "min_det_j": item.min_det_j,
                }
                for item in response.elements
            ),
            metadata={"adapter_id": self.adapter_id, "load_factor": float(load_factor)},
        )

    @abstractmethod
    def native_reference(self, model: ModelInput) -> AdapterRecovery:
        """Solve through the original core for adapter/reference regression tests."""

    @abstractmethod
    def _build_native_system(self, model: ModelInput) -> NativeSystem:
        """Translate and assemble using only an installed core's public API."""

    def _require_family(self, model: ModelInput) -> None:
        if not isinstance(model, ModelInput):
            raise TypeError("model must be a validated nonlinear_core.ModelInput")
        if model.model_family is not self.family:
            raise ValueError(
                f"{self.adapter_id} requires family {self.family.value!r}; "
                f"got {model.model_family.value!r}"
            )

    def _require_compatible_state(self, model: ModelInput, state: AdapterState) -> None:
        if state.model_id != model.model_id or state.adapter_id != self.adapter_id:
            raise ValueError("committed_state belongs to a different model or adapter")


__all__ = [
    "AdapterIssue",
    "AdapterRecovery",
    "AdapterState",
    "AdapterValidation",
    "ElementResponse",
    "LinearCoreAdapter",
    "LocalFailure",
    "ModelAdapter",
    "ModelResponse",
    "NativeElement",
    "NativeSystem",
]
