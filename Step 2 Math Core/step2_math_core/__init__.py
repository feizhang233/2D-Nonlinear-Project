"""Unified integration boundary for the four Step 2 mathematical cores."""

from .contracts import (
    ADAPTER_VERSION,
    SCHEMA_VERSION,
    CoreMetadata,
    InterfaceError,
    MathCoreError,
    MathCoreRequest,
    MathCoreResponse,
    OperationSpec,
)
from .registry import describe_core, execute, list_core_ids, list_cores

__all__ = [
    "ADAPTER_VERSION",
    "SCHEMA_VERSION",
    "CoreMetadata",
    "InterfaceError",
    "MathCoreError",
    "MathCoreRequest",
    "MathCoreResponse",
    "OperationSpec",
    "describe_core",
    "execute",
    "list_core_ids",
    "list_cores",
]

__version__ = ADAPTER_VERSION
