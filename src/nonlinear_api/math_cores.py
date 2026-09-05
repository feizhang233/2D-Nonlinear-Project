"""Bounded runtime bridge to the Step 2 mathematical-core package."""

from __future__ import annotations

import sys
from dataclasses import asdict
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any

MAX_PARAMETER_VALUES = 10_000
MAX_PARAMETER_DEPTH = 12
STEP2_ROOT = Path(__file__).resolve().parents[2] / "Step 2 Math Core"


class MathCoreBridgeError(RuntimeError):
    """Stable integration failure raised before a core operation can execute."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@lru_cache(maxsize=1)
def _interface():
    package = STEP2_ROOT / "step2_math_core"
    if not package.is_dir():
        raise MathCoreBridgeError(
            "MATH_CORE_UNAVAILABLE",
            "The Step 2 math-core runtime is not installed on this server",
            details={"expected_package": "Step 2 Math Core/step2_math_core"},
        )
    root_text = str(STEP2_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        return import_module("step2_math_core")
    except Exception as error:
        raise MathCoreBridgeError(
            "MATH_CORE_UNAVAILABLE",
            "The Step 2 math-core runtime could not be loaded",
            details={"exception_type": type(error).__name__},
        ) from error


def _count_parameter_values(value: Any, *, depth: int = 0) -> int:
    if depth > MAX_PARAMETER_DEPTH:
        raise MathCoreBridgeError(
            "MATH_CORE_INPUT_LIMIT_EXCEEDED",
            f"Math-core parameters may be nested at most {MAX_PARAMETER_DEPTH} levels",
            details={"max_parameter_depth": MAX_PARAMETER_DEPTH},
        )
    if isinstance(value, dict):
        count = sum(
            _count_parameter_values(item, depth=depth + 1) for item in value.values()
        )
    elif isinstance(value, list):
        count = sum(_count_parameter_values(item, depth=depth + 1) for item in value)
    else:
        count = 1
    if count > MAX_PARAMETER_VALUES:
        raise MathCoreBridgeError(
            "MATH_CORE_INPUT_LIMIT_EXCEEDED",
            f"Math-core parameters may contain at most {MAX_PARAMETER_VALUES} values",
            details={"max_parameter_values": MAX_PARAMETER_VALUES},
        )
    return count


def list_math_cores() -> list[dict[str, Any]]:
    interface = _interface()
    return [asdict(core) for core in interface.list_cores()]


def describe_math_core(core_id: str) -> dict[str, Any]:
    interface = _interface()
    try:
        return asdict(interface.describe_core(core_id))
    except interface.InterfaceError as error:
        raise MathCoreBridgeError(error.code, error.message, details=error.details) from error


def execute_math_core(request: dict[str, Any]) -> dict[str, Any]:
    _count_parameter_values(request.get("parameters", {}))
    return _interface().execute(request).to_dict()


def interface_version() -> tuple[str, str]:
    interface = _interface()
    return interface.SCHEMA_VERSION, interface.ADAPTER_VERSION


__all__ = [
    "MAX_PARAMETER_DEPTH",
    "MAX_PARAMETER_VALUES",
    "MathCoreBridgeError",
    "describe_math_core",
    "execute_math_core",
    "interface_version",
    "list_math_cores",
]
