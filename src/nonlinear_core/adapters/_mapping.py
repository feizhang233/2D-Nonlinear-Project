"""Small, mathematics-free helpers shared by P2 core translators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from nonlinear_core.model import ElementInput, MaterialInput, ModelInput


def material_lookup(model: ModelInput) -> dict[str, MaterialInput]:
    return {material.id: material for material in model.materials}


def element_lookup(model: ModelInput) -> dict[str, ElementInput]:
    return {element.id: element for element in model.elements}


def node_index_lookup(model: ModelInput) -> dict[str, int]:
    return {node.id: index for index, node in enumerate(model.nodes)}


def float_value(
    values: Mapping[str, Any],
    *names: str,
    default: float | None = None,
) -> float:
    for name in names:
        if name in values:
            value = values[name]
            if isinstance(value, bool):
                raise ValueError(f"{name} must be a finite number")
            try:
                result = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(f"{name} must be a finite number") from error
            if not np.isfinite(result):
                raise ValueError(f"{name} must be a finite number")
            return result
    if default is not None:
        return float(default)
    joined = "/".join(names)
    raise ValueError(f"required numeric property is missing: {joined}")


def scaled_components(load: Any) -> dict[str, float]:
    return {name: float(value) * float(load.scale) for name, value in load.components.items()}


def first_connected_elements(model: ModelInput) -> dict[str, str]:
    """Assign each node to one element for a non-duplicating load decomposition."""

    result: dict[str, str] = {}
    for element in model.elements:
        for node_id in element.node_ids:
            result.setdefault(node_id, element.id)
    return result


__all__ = [
    "element_lookup",
    "first_connected_elements",
    "float_value",
    "material_lookup",
    "node_index_lookup",
    "scaled_components",
]
