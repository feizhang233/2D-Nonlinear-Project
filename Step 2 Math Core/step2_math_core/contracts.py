"""Public request, response, and metadata contracts for the Step 2 math cores."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA_VERSION = "1.0.0"
ADAPTER_VERSION = "0.1.0"


class InterfaceError(Exception):
    """A stable, machine-readable failure raised by the adapter boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


@dataclass(frozen=True)
class OperationSpec:
    name: str
    summary: str
    required_parameters: tuple[str, ...] = ()
    optional_parameters: tuple[str, ...] = ()
    example_parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CoreMetadata:
    core_id: str
    title: str
    version: str
    source_path: str
    scope: str
    residual_convention: str
    state_protocol: str
    verification_ids: tuple[str, ...]
    verification_meaning: str
    limitations: tuple[str, ...]
    operations: tuple[OperationSpec, ...]


@dataclass(frozen=True)
class MathCoreRequest:
    core: str
    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MathCoreRequest:
        if not isinstance(value, Mapping):
            raise InterfaceError("INVALID_REQUEST", "request must be a mapping")
        schema_version = value.get("schema_version", SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            raise InterfaceError(
                "UNSUPPORTED_SCHEMA_VERSION",
                f"schema_version must be {SCHEMA_VERSION!r}",
                details={"received": schema_version},
            )
        core = value.get("core")
        operation = value.get("operation")
        parameters = value.get("parameters", {})
        request_id = value.get("request_id")
        if not isinstance(core, str) or not core:
            raise InterfaceError("INVALID_REQUEST", "core must be a non-empty string")
        if not isinstance(operation, str) or not operation:
            raise InterfaceError("INVALID_REQUEST", "operation must be a non-empty string")
        if not isinstance(parameters, Mapping):
            raise InterfaceError("INVALID_REQUEST", "parameters must be a mapping")
        if request_id is not None and not isinstance(request_id, str):
            raise InterfaceError("INVALID_REQUEST", "request_id must be a string or null")
        return cls(
            core=core,
            operation=operation,
            parameters=dict(parameters),
            request_id=request_id,
            schema_version=SCHEMA_VERSION,
        )


@dataclass(frozen=True)
class MathCoreError:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MathCoreResponse:
    core: str
    operation: str
    status: str
    data: Any = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    error: MathCoreError | None = None
    request_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)


def to_jsonable(value: Any) -> Any:
    """Convert NumPy, dataclass, enum, tuple, and path results to JSON data."""

    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value
