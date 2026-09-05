"""Lazy core registry and the public ``execute`` entry point."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .adapters import CoreAdapter, build_adapters
from .contracts import (
    ADAPTER_VERSION,
    CoreMetadata,
    InterfaceError,
    MathCoreError,
    MathCoreRequest,
    MathCoreResponse,
)

_ADAPTERS: dict[str, CoreAdapter] | None = None


def _adapters() -> dict[str, CoreAdapter]:
    global _ADAPTERS
    if _ADAPTERS is None:
        _ADAPTERS = build_adapters()
    return _ADAPTERS


def list_core_ids() -> tuple[str, ...]:
    return tuple(sorted(_adapters()))


def list_cores() -> tuple[CoreMetadata, ...]:
    return tuple(_adapters()[core_id].metadata for core_id in list_core_ids())


def describe_core(core_id: str) -> CoreMetadata:
    try:
        return _adapters()[core_id].metadata
    except KeyError as exc:
        raise InterfaceError(
            "UNKNOWN_CORE",
            f"unknown core {core_id!r}",
            details={"supported": list(list_core_ids())},
        ) from exc


def execute(request: MathCoreRequest | Mapping[str, Any]) -> MathCoreResponse:
    """Execute a request and always return a stable success/error envelope."""

    raw = request if isinstance(request, Mapping) else {}
    core_hint = str(raw.get("core", "")) if isinstance(raw, Mapping) else ""
    operation_hint = str(raw.get("operation", "")) if isinstance(raw, Mapping) else ""
    request_id_hint = raw.get("request_id") if isinstance(raw, Mapping) else None

    try:
        parsed = (
            request
            if isinstance(request, MathCoreRequest)
            else MathCoreRequest.from_mapping(request)
        )
    except InterfaceError as exc:
        return _error_response(
            core=core_hint,
            operation=operation_hint,
            request_id=request_id_hint if isinstance(request_id_hint, str) else None,
            error=exc,
        )

    try:
        adapter = _adapters()[parsed.core]
    except KeyError:
        return _error_response(
            core=parsed.core,
            operation=parsed.operation,
            request_id=parsed.request_id,
            error=InterfaceError(
                "UNKNOWN_CORE",
                f"unknown core {parsed.core!r}",
                details={"supported": list(list_core_ids())},
            ),
        )

    try:
        data = adapter.run(parsed.operation, parsed.parameters)
    except InterfaceError as exc:
        return _error_response(
            core=parsed.core,
            operation=parsed.operation,
            request_id=parsed.request_id,
            error=exc,
            adapter=adapter,
        )
    except (TypeError, ValueError) as exc:
        return _error_response(
            core=parsed.core,
            operation=parsed.operation,
            request_id=parsed.request_id,
            error=InterfaceError(
                "INVALID_PARAMETERS",
                str(exc),
                details={"exception_type": type(exc).__name__},
            ),
            adapter=adapter,
        )
    except np.linalg.LinAlgError as exc:
        return _error_response(
            core=parsed.core,
            operation=parsed.operation,
            request_id=parsed.request_id,
            error=InterfaceError(
                "NUMERICAL_FAILURE",
                str(exc),
                details={"exception_type": type(exc).__name__},
            ),
            adapter=adapter,
        )
    except (FloatingPointError, RuntimeError) as exc:
        return _error_response(
            core=parsed.core,
            operation=parsed.operation,
            request_id=parsed.request_id,
            error=InterfaceError(
                "CORE_EXECUTION_FAILED",
                str(exc),
                details={"exception_type": type(exc).__name__},
            ),
            adapter=adapter,
        )
    except Exception as exc:  # keep third-party/core failures inside the public envelope
        return _error_response(
            core=parsed.core,
            operation=parsed.operation,
            request_id=parsed.request_id,
            error=InterfaceError(
                "CORE_EXECUTION_FAILED",
                str(exc),
                details={"exception_type": type(exc).__name__},
            ),
            adapter=adapter,
        )

    return MathCoreResponse(
        core=parsed.core,
        operation=parsed.operation,
        status="ok",
        data=data,
        diagnostics=_diagnostics(adapter),
        request_id=parsed.request_id,
    )


def _diagnostics(adapter: CoreAdapter | None) -> dict[str, Any]:
    result: dict[str, Any] = {"adapter_version": ADAPTER_VERSION}
    if adapter is not None:
        result.update(
            {
                "core_version": adapter.metadata.version,
                "residual_convention": adapter.metadata.residual_convention,
                "state_protocol": adapter.metadata.state_protocol,
                "verification_meaning": adapter.metadata.verification_meaning,
                "limitations": adapter.metadata.limitations,
            }
        )
    return result


def _error_response(
    *,
    core: str,
    operation: str,
    request_id: str | None,
    error: InterfaceError,
    adapter: CoreAdapter | None = None,
) -> MathCoreResponse:
    return MathCoreResponse(
        core=core,
        operation=operation,
        status="error",
        diagnostics=_diagnostics(adapter),
        error=MathCoreError(error.code, error.message, error.details),
        request_id=request_id,
    )
