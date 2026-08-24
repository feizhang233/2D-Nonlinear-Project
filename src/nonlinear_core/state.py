"""P4 immutable trial/commit/rollback transactions and restart snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nonlinear_core.adapters import AdapterState, ModelAdapter, ModelResponse
from nonlinear_core.contracts import canonical_model_json
from nonlinear_core.model import ModelFamily, ModelInput

FloatArray = NDArray[np.float64]
STATE_SCHEMA_VERSION = "1.0.0"


class StateFailureCode(StrEnum):
    INVALID_STATE = "STATE_INVALID"
    MODEL_MISMATCH = "STATE_MODEL_MISMATCH"
    ADAPTER_MISMATCH = "STATE_ADAPTER_MISMATCH"
    STEP_MISMATCH = "STATE_STEP_MISMATCH"
    BASE_MISMATCH = "STATE_BASE_MISMATCH"
    CONVERGENCE_REQUIRED = "STATE_CONVERGENCE_REQUIRED"
    RESTART_INVALID = "STATE_RESTART_INVALID"
    HASH_MISMATCH = "STATE_HASH_MISMATCH"


class StateTransitionError(ValueError):
    """Classified state lifecycle or restart failure."""

    def __init__(self, code: StateFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = StateFailureCode(code)


def model_sha256(model: ModelInput) -> str:
    return hashlib.sha256(canonical_model_json(model).encode("utf-8")).hexdigest()


def _readonly_vector(value: ArrayLike) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.ndim != 1:
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            f"state displacement must be one-dimensional; got {result.shape}",
        )
    if not np.all(np.isfinite(result)):
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            "state displacement must contain only finite values",
        )
    result.setflags(write=False)
    return result


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE, f"{name} must be a finite number"
        )
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE, f"{name} must be a finite number"
        ) from error
    if not np.isfinite(result):
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE, f"{name} must be a finite number"
        )
    return result


def _freeze(value: Any, *, path: str = "history") -> Any:
    """Deep-copy JSON-like history into immutable containers."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (float, np.floating)):
        return _finite(path, float(value))
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.ndarray):
        return tuple(_freeze(item, path=f"{path}[]") for item in value.tolist())
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise StateTransitionError(
                    StateFailureCode.INVALID_STATE,
                    f"{path} keys must be strings; got {type(key).__name__}",
                )
            frozen[key] = _freeze(child, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child, path=f"{path}[]") for child in value)
    raise StateTransitionError(
        StateFailureCode.INVALID_STATE,
        f"{path} contains unsupported value type {type(value).__name__}",
    )


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _validate_identity(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE, f"{name} must be a non-empty string"
        )
    return value.strip()


def _validate_hash(name: str, value: str) -> str:
    normalized = _validate_identity(name, value)
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            f"{name} must be a lowercase SHA-256 hex digest",
        )
    return normalized


def _validate_index(name: str, value: int, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            f"{name} must be an integer greater than or equal to {minimum}",
        )
    normalized = int(value)
    if normalized < minimum:
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            f"{name} must be an integer greater than or equal to {minimum}",
        )
    return normalized


def _state_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _base_payload(
    *,
    state_type: str,
    model_id: str,
    model_family: ModelFamily,
    model_hash: str,
    adapter_id: str,
    core_package: str,
    core_version: str,
    core_state_id: str,
    step_index: int,
    iteration_index: int,
    displacement: FloatArray,
    load_factor: float,
    history: Mapping[str, Any],
    parent_or_base_id: str | None,
) -> dict[str, Any]:
    payload = {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "state_type": state_type,
        "model_id": model_id,
        "model_family": model_family.value,
        "model_sha256": model_hash,
        "adapter_id": adapter_id,
        "core_package": core_package,
        "core_version": core_version,
        "core_state_id": core_state_id,
        "step_index": step_index,
        "iteration_index": iteration_index,
        "displacement": [float(value) for value in displacement],
        "load_factor": load_factor,
        "history": _thaw(history),
    }
    if state_type == "committed":
        payload["parent_state_id"] = parent_or_base_id
    else:
        payload["base_state_id"] = parent_or_base_id
    return payload


@dataclass(frozen=True, slots=True)
class CommittedState:
    """Immutable state of the last globally converged step."""

    model_id: str
    model_family: ModelFamily
    model_sha256: str
    adapter_id: str
    core_package: str
    core_version: str
    core_state_id: str
    step_index: int
    iteration_index: int
    displacement: FloatArray
    load_factor: float
    history: Mapping[str, Any]
    parent_state_id: str | None = None
    state_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _validate_identity("model_id", self.model_id))
        try:
            family = ModelFamily(self.model_family)
        except ValueError as error:
            raise StateTransitionError(
                StateFailureCode.INVALID_STATE,
                f"model_family is invalid: {self.model_family!r}",
            ) from error
        object.__setattr__(self, "model_family", family)
        object.__setattr__(self, "model_sha256", _validate_hash("model_sha256", self.model_sha256))
        for name in ("adapter_id", "core_package", "core_version", "core_state_id"):
            object.__setattr__(self, name, _validate_identity(name, getattr(self, name)))
        object.__setattr__(
            self, "step_index", _validate_index("step_index", self.step_index, minimum=0)
        )
        object.__setattr__(
            self,
            "iteration_index",
            _validate_index("iteration_index", self.iteration_index, minimum=0),
        )
        if self.parent_state_id is not None:
            object.__setattr__(
                self,
                "parent_state_id",
                _validate_hash("parent_state_id", self.parent_state_id),
            )
        displacement = _readonly_vector(self.displacement)
        history = _freeze(self.history)
        if not isinstance(history, Mapping):
            raise StateTransitionError(StateFailureCode.INVALID_STATE, "history must be a mapping")
        load_factor = _finite("load_factor", self.load_factor)
        object.__setattr__(self, "displacement", displacement)
        object.__setattr__(self, "history", history)
        object.__setattr__(self, "load_factor", load_factor)
        payload = self.to_payload(include_state_id=False)
        computed = _state_digest(payload)
        supplied_state_id = _validate_hash("state_id", self.state_id) if self.state_id else ""
        if supplied_state_id and supplied_state_id != computed:
            raise StateTransitionError(
                StateFailureCode.HASH_MISMATCH,
                "committed state_id does not match its canonical payload",
            )
        object.__setattr__(self, "state_id", computed)

    def to_payload(self, *, include_state_id: bool = True) -> dict[str, Any]:
        payload = _base_payload(
            state_type="committed",
            model_id=self.model_id,
            model_family=self.model_family,
            model_hash=self.model_sha256,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            core_state_id=self.core_state_id,
            step_index=self.step_index,
            iteration_index=self.iteration_index,
            displacement=self.displacement,
            load_factor=self.load_factor,
            history=self.history,
            parent_or_base_id=self.parent_state_id,
        )
        if include_state_id:
            payload["state_id"] = self.state_id
        return payload

    def as_adapter_state(self) -> AdapterState:
        return AdapterState(
            model_id=self.model_id,
            model_family=self.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=self.core_state_id,
            committed=True,
            history=self.history,
        )


@dataclass(frozen=True, slots=True)
class TrialState:
    """Immutable result belonging to exactly one trial point and base state."""

    model_id: str
    model_family: ModelFamily
    model_sha256: str
    adapter_id: str
    core_package: str
    core_version: str
    core_state_id: str
    step_index: int
    iteration_index: int
    displacement: FloatArray
    load_factor: float
    history: Mapping[str, Any]
    base_state_id: str
    trial_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _validate_identity("model_id", self.model_id))
        try:
            family = ModelFamily(self.model_family)
        except ValueError as error:
            raise StateTransitionError(
                StateFailureCode.INVALID_STATE,
                f"model_family is invalid: {self.model_family!r}",
            ) from error
        object.__setattr__(self, "model_family", family)
        object.__setattr__(self, "model_sha256", _validate_hash("model_sha256", self.model_sha256))
        for name in (
            "adapter_id",
            "core_package",
            "core_version",
            "core_state_id",
        ):
            object.__setattr__(self, name, _validate_identity(name, getattr(self, name)))
        object.__setattr__(
            self, "base_state_id", _validate_hash("base_state_id", self.base_state_id)
        )
        object.__setattr__(
            self, "step_index", _validate_index("step_index", self.step_index, minimum=1)
        )
        object.__setattr__(
            self,
            "iteration_index",
            _validate_index("iteration_index", self.iteration_index, minimum=0),
        )
        displacement = _readonly_vector(self.displacement)
        history = _freeze(self.history)
        if not isinstance(history, Mapping):
            raise StateTransitionError(StateFailureCode.INVALID_STATE, "history must be a mapping")
        load_factor = _finite("load_factor", self.load_factor)
        object.__setattr__(self, "displacement", displacement)
        object.__setattr__(self, "history", history)
        object.__setattr__(self, "load_factor", load_factor)
        computed = _state_digest(self.to_payload(include_trial_id=False))
        supplied_trial_id = _validate_hash("trial_id", self.trial_id) if self.trial_id else ""
        if supplied_trial_id and supplied_trial_id != computed:
            raise StateTransitionError(
                StateFailureCode.HASH_MISMATCH,
                "trial_id does not match its canonical payload",
            )
        object.__setattr__(self, "trial_id", computed)

    def to_payload(self, *, include_trial_id: bool = True) -> dict[str, Any]:
        payload = _base_payload(
            state_type="trial",
            model_id=self.model_id,
            model_family=self.model_family,
            model_hash=self.model_sha256,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            core_state_id=self.core_state_id,
            step_index=self.step_index,
            iteration_index=self.iteration_index,
            displacement=self.displacement,
            load_factor=self.load_factor,
            history=self.history,
            parent_or_base_id=self.base_state_id,
        )
        if include_trial_id:
            payload["trial_id"] = self.trial_id
        return payload

    def as_adapter_state(self) -> AdapterState:
        return AdapterState(
            model_id=self.model_id,
            model_family=self.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=self.core_state_id,
            committed=False,
            history=self.history,
        )


@dataclass(frozen=True, slots=True)
class StepContext:
    """Read-only transaction baseline shared by all attempts/iterations of a step."""

    base_state: CommittedState
    step_index: int
    attempt_index: int
    target_load_factor: float
    predictor_displacement: FloatArray

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "step_index", _validate_index("step_index", self.step_index, minimum=1)
        )
        object.__setattr__(
            self,
            "attempt_index",
            _validate_index("attempt_index", self.attempt_index, minimum=0),
        )
        if self.step_index <= self.base_state.step_index:
            raise StateTransitionError(
                StateFailureCode.STEP_MISMATCH,
                "new step_index must be greater than the committed step_index",
            )
        predictor = _readonly_vector(self.predictor_displacement)
        if predictor.shape != self.base_state.displacement.shape:
            raise StateTransitionError(
                StateFailureCode.INVALID_STATE,
                "predictor_displacement must match the committed DOF count",
            )
        object.__setattr__(self, "predictor_displacement", predictor)
        object.__setattr__(
            self,
            "target_load_factor",
            _finite("target_load_factor", self.target_load_factor),
        )


@dataclass(frozen=True, slots=True)
class TrialEvaluation:
    state: TrialState
    response: ModelResponse


def initialize_state(
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    displacement: ArrayLike | None = None,
    load_factor: float = 0.0,
    history: Mapping[str, Any] | None = None,
) -> CommittedState:
    validation = adapter.validate(model)
    if not validation.valid:
        message = "; ".join(issue.message for issue in validation.errors)
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE, f"cannot initialize invalid adapter model: {message}"
        )
    core = adapter.initial_state(model)
    size = len(adapter.dof_map(model))
    values = np.zeros(size, dtype=float) if displacement is None else _readonly_vector(displacement)
    if values.shape != (size,):
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            f"initial displacement must have shape ({size},)",
        )
    return CommittedState(
        model_id=model.model_id,
        model_family=model.model_family,
        model_sha256=model_sha256(model),
        adapter_id=adapter.adapter_id,
        core_package=adapter.core_package,
        core_version=adapter.core_version,
        core_state_id=core.state_id,
        step_index=0,
        iteration_index=0,
        displacement=values,
        load_factor=load_factor,
        history=core.history if history is None else history,
    )


def begin_step(
    committed: CommittedState,
    *,
    target_load_factor: float,
    predictor_displacement: ArrayLike | None = None,
    step_index: int | None = None,
    attempt_index: int = 0,
) -> StepContext:
    predictor = (
        committed.displacement
        if predictor_displacement is None
        else _readonly_vector(predictor_displacement)
    )
    return StepContext(
        base_state=committed,
        step_index=committed.step_index + 1 if step_index is None else step_index,
        attempt_index=attempt_index,
        target_load_factor=target_load_factor,
        predictor_displacement=predictor,
    )


def _validate_context(
    context: StepContext,
    adapter: ModelAdapter,
    model: ModelInput,
) -> None:
    base = context.base_state
    if model.model_id != base.model_id or model_sha256(model) != base.model_sha256:
        raise StateTransitionError(
            StateFailureCode.MODEL_MISMATCH,
            "step model does not match the committed model snapshot",
        )
    if adapter.adapter_id != base.adapter_id:
        raise StateTransitionError(
            StateFailureCode.ADAPTER_MISMATCH,
            "step adapter does not match the committed adapter",
        )


def evaluate_trial(
    context: StepContext,
    adapter: ModelAdapter,
    model: ModelInput,
    *,
    trial_displacement: ArrayLike | None = None,
    load_factor: float | None = None,
    iteration_index: int = 0,
) -> TrialEvaluation:
    """Recompute a trial response from the immutable committed baseline."""

    _validate_context(context, adapter, model)
    values = (
        context.predictor_displacement
        if trial_displacement is None
        else _readonly_vector(trial_displacement)
    )
    if values.shape != context.base_state.displacement.shape:
        raise StateTransitionError(
            StateFailureCode.INVALID_STATE,
            "trial_displacement must match the committed DOF count",
        )
    factor = (
        context.target_load_factor if load_factor is None else _finite("load_factor", load_factor)
    )
    response = adapter.evaluate(
        model,
        values,
        load_factor=factor,
        committed_state=context.base_state.as_adapter_state(),
    )
    core_trial = response.trial_state
    if core_trial.adapter_id != adapter.adapter_id or core_trial.model_id != model.model_id:
        raise StateTransitionError(
            StateFailureCode.ADAPTER_MISMATCH,
            "adapter returned a trial state for a different model or adapter",
        )
    state = TrialState(
        model_id=model.model_id,
        model_family=model.model_family,
        model_sha256=context.base_state.model_sha256,
        adapter_id=adapter.adapter_id,
        core_package=adapter.core_package,
        core_version=adapter.core_version,
        core_state_id=core_trial.state_id,
        step_index=context.step_index,
        iteration_index=iteration_index,
        displacement=values,
        load_factor=factor,
        history=core_trial.history,
        base_state_id=context.base_state.state_id,
    )
    return TrialEvaluation(state=state, response=response)


def _validate_trial_context(context: StepContext, trial: TrialState) -> None:
    if trial.base_state_id != context.base_state.state_id:
        raise StateTransitionError(
            StateFailureCode.BASE_MISMATCH,
            "trial state was not derived from this transaction baseline",
        )
    if trial.step_index != context.step_index:
        raise StateTransitionError(
            StateFailureCode.STEP_MISMATCH,
            "trial state belongs to a different step",
        )
    if (
        trial.model_sha256 != context.base_state.model_sha256
        or trial.adapter_id != context.base_state.adapter_id
    ):
        raise StateTransitionError(
            StateFailureCode.MODEL_MISMATCH,
            "trial state identity does not match the transaction baseline",
        )


def commit(
    context: StepContext,
    trial: TrialState,
    *,
    converged: bool,
) -> CommittedState:
    """Promote exactly one converged trial state to an immutable committed state."""

    _validate_trial_context(context, trial)
    if converged is not True:
        raise StateTransitionError(
            StateFailureCode.CONVERGENCE_REQUIRED,
            "commit requires explicit global convergence confirmation",
        )
    return CommittedState(
        model_id=trial.model_id,
        model_family=trial.model_family,
        model_sha256=trial.model_sha256,
        adapter_id=trial.adapter_id,
        core_package=trial.core_package,
        core_version=trial.core_version,
        core_state_id=trial.core_state_id,
        step_index=trial.step_index,
        iteration_index=trial.iteration_index,
        displacement=trial.displacement,
        load_factor=trial.load_factor,
        history=trial.history,
        parent_state_id=context.base_state.state_id,
    )


def rollback(
    context: StepContext,
    trial: TrialState | None = None,
) -> CommittedState:
    """Discard trial data and return the exact committed transaction baseline."""

    if trial is not None:
        _validate_trial_context(context, trial)
    return context.base_state


def serialize_restart(state: CommittedState) -> str:
    """Return deterministic JSON for committed state only."""

    return (
        json.dumps(
            state.to_payload(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def deserialize_restart(
    text: str,
    *,
    model: ModelInput | None = None,
    expected_adapter_id: str | None = None,
) -> CommittedState:
    """Restore and authenticate one committed-state restart document."""

    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise StateTransitionError(
            StateFailureCode.RESTART_INVALID, f"restart is not valid JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise StateTransitionError(
            StateFailureCode.RESTART_INVALID, "restart root must be a JSON object"
        )
    expected_keys = {
        "state_schema_version",
        "state_type",
        "model_id",
        "model_family",
        "model_sha256",
        "adapter_id",
        "core_package",
        "core_version",
        "core_state_id",
        "step_index",
        "iteration_index",
        "displacement",
        "load_factor",
        "history",
        "parent_state_id",
        "state_id",
    }
    if set(payload) != expected_keys:
        missing = sorted(expected_keys - set(payload))
        unknown = sorted(set(payload) - expected_keys)
        raise StateTransitionError(
            StateFailureCode.RESTART_INVALID,
            f"restart fields do not match the frozen schema; missing={missing}, unknown={unknown}",
        )
    if (
        payload["state_schema_version"] != STATE_SCHEMA_VERSION
        or payload["state_type"] != "committed"
    ):
        raise StateTransitionError(
            StateFailureCode.RESTART_INVALID,
            "restart must be a committed state with schema version 1.0.0",
        )
    try:
        state = CommittedState(
            model_id=payload["model_id"],
            model_family=payload["model_family"],
            model_sha256=payload["model_sha256"],
            adapter_id=payload["adapter_id"],
            core_package=payload["core_package"],
            core_version=payload["core_version"],
            core_state_id=payload["core_state_id"],
            step_index=int(payload["step_index"]),
            iteration_index=int(payload["iteration_index"]),
            displacement=payload["displacement"],
            load_factor=payload["load_factor"],
            history=payload["history"],
            parent_state_id=payload["parent_state_id"],
            state_id=payload["state_id"],
        )
    except StateTransitionError:
        raise
    except (TypeError, ValueError, KeyError, OverflowError) as error:
        raise StateTransitionError(
            StateFailureCode.RESTART_INVALID, f"restart field validation failed: {error}"
        ) from error
    if model is not None and (
        state.model_id != model.model_id or state.model_sha256 != model_sha256(model)
    ):
        raise StateTransitionError(
            StateFailureCode.MODEL_MISMATCH,
            "restart state does not belong to the supplied model",
        )
    if expected_adapter_id is not None and state.adapter_id != expected_adapter_id:
        raise StateTransitionError(
            StateFailureCode.ADAPTER_MISMATCH,
            "restart state does not belong to the expected adapter",
        )
    return state


__all__ = [
    "STATE_SCHEMA_VERSION",
    "CommittedState",
    "StateFailureCode",
    "StateTransitionError",
    "StepContext",
    "TrialEvaluation",
    "TrialState",
    "begin_step",
    "commit",
    "deserialize_restart",
    "evaluate_trial",
    "initialize_state",
    "model_sha256",
    "rollback",
    "serialize_restart",
]
