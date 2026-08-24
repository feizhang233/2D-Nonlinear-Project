"""Shared target parsing for fixed reference distributed surface loads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from nonlinear_core.model import LoadInput


@dataclass(frozen=True, slots=True)
class EdgeTarget:
    element_id: str
    local_edge: int


def edge_targets(load: LoadInput, element_ids: set[str]) -> tuple[EdgeTarget, ...]:
    raw_targets = load.extensions.get("edge_segments")
    if raw_targets is None:
        raw_edge = load.extensions.get("local_edge")
        if isinstance(raw_edge, bool) or not isinstance(raw_edge, int):
            raise ValueError(f"edge load {load.id!r} requires integer extensions.local_edge")
        if load.element_id is None:
            raise ValueError(f"edge load {load.id!r} requires element_id")
        targets = (EdgeTarget(load.element_id, raw_edge),)
    else:
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError(
                f"edge load {load.id!r} extensions.edge_segments must be a non-empty array"
            )
        parsed: list[EdgeTarget] = []
        for index, raw_target in enumerate(raw_targets):
            if not isinstance(raw_target, Mapping):
                raise ValueError(f"edge load {load.id!r} edge_segments[{index}] must be an object")
            element_id = raw_target.get("element_id")
            local_edge = raw_target.get("local_edge")
            if not isinstance(element_id, str) or not element_id:
                raise ValueError(
                    f"edge load {load.id!r} edge_segments[{index}].element_id is required"
                )
            if isinstance(local_edge, bool) or not isinstance(local_edge, int):
                raise ValueError(
                    f"edge load {load.id!r} edge_segments[{index}].local_edge must be an integer"
                )
            parsed.append(EdgeTarget(element_id, local_edge))
        targets = tuple(parsed)
    for target in targets:
        if target.element_id not in element_ids:
            raise ValueError(
                f"edge load {load.id!r} references unknown element {target.element_id!r}"
            )
        if target.local_edge not in {0, 1, 2, 3}:
            raise ValueError(f"edge load {load.id!r} local_edge must be in {{0,1,2,3}}")
    if len(set(targets)) != len(targets):
        raise ValueError(f"edge load {load.id!r} repeats one element edge")
    return targets


def surface_element_ids(load: LoadInput, element_ids: set[str]) -> tuple[str, ...]:
    raw_ids = load.extensions.get("element_ids")
    if raw_ids is None:
        if load.element_id is None:
            raise ValueError(f"surface load {load.id!r} requires element_id")
        targets = (load.element_id,)
    else:
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError(
                f"surface load {load.id!r} extensions.element_ids must be a non-empty array"
            )
        if any(not isinstance(item, str) or not item for item in raw_ids):
            raise ValueError(
                f"surface load {load.id!r} extensions.element_ids must contain element IDs"
            )
        targets = tuple(raw_ids)
    if len(set(targets)) != len(targets):
        raise ValueError(f"surface load {load.id!r} repeats one element target")
    missing = [element_id for element_id in targets if element_id not in element_ids]
    if missing:
        raise ValueError(f"surface load {load.id!r} references unknown element {missing[0]!r}")
    return targets


__all__ = ["EdgeTarget", "edge_targets", "surface_element_ids"]
