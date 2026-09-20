"""P1 semantic validation: IDs, refs, units, materials, topology and geometry."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from reused_cores.shell3d_linear.constants import (
    DOF_OFFSET,
    DOF_PER_NODE_GLOBAL,
    EDGE_RATIO_ERROR,
    JHAT_ERROR,
    JHAT_WARNING,
    PRODUCTION_DRILLING,
    PRODUCTION_SHEAR,
    Q4_LOCAL_EDGES,
    RJ_WARNING,
    SCHEMA_VERSION,
    SI_UNITS,
    VERIFICATION_DRILLING,
    VERIFICATION_SHEAR,
    WARP_ERROR,
    WARP_WARNING,
)
from reused_cores.shell3d_linear.diagnostics import Diagnostic, json_path, make_diagnostic, sort_diagnostics
from reused_cores.shell3d_linear.geometry import evaluate_element_quality
from reused_cores.shell3d_linear.schema import schema_diagnostics
from reused_cores.shell3d_linear.serialize import canonical_sha256, load_document, load_json
from reused_cores.shell3d_linear.types import (
    AnalysisOptions,
    Constraint,
    DofName,
    ElementGeometryRecord,
    MaterialRecord,
    ModelInput,
    NodeRecord,
    NormalizedBodyForce,
    NormalizedConstraint,
    NormalizedEdgeTraction,
    NormalizedLoad,
    NormalizedNodalLoad,
    NormalizedSurfaceTraction,
    SectionRecord,
    Units,
    ValidatedModel,
    ValidationResult,
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_finite_float(value: Any) -> float | None:
    if not _is_number(value):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not math.isfinite(number):
        return None
    return number


def _walk_numbers(value: Any, parts: list[str | int]) -> Iterable[tuple[list[str | int], Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_numbers(child, [*parts, str(key)])
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_numbers(child, [*parts, index])
    elif _is_number(value):
        yield parts, value


def _finite_number_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    for parts, value in _walk_numbers(data, []):
        if _as_finite_float(value) is not None:
            continue
        items.append(
            make_diagnostic(
                "SHELL-NUM-E001",
                entity_type=_entity_type_from_parts(parts),
                entity_id=_entity_id_from_parts(data, parts),
                json_path=json_path(parts),
                observed=str(value),
                threshold="finite float64",
                unit=None,
            )
        )
    return items


def _entity_type_from_parts(parts: list[str | int]) -> Any:
    names = [part for part in parts if isinstance(part, str)]
    if "nodes" in names:
        return "node"
    if "materials" in names:
        return "material"
    if "sections" in names:
        return "section"
    if "elements" in names:
        return "element"
    if "constraints" in names:
        return "constraint"
    if "loads" in names or "load_case" in names:
        return "load"
    if "analysis_options" in names:
        return "analysis_options"
    return "document"


def _collection_item_id(data: Mapping[str, Any], collection: str, index: int) -> str | None:
    items = data.get(collection)
    if isinstance(items, list) and 0 <= index < len(items) and isinstance(items[index], Mapping):
        ident = items[index].get("id")
        return ident if isinstance(ident, str) else None
    return None


def _entity_id_from_parts(data: Mapping[str, Any], parts: list[str | int]) -> str | None:
    if not parts:
        ident = data.get("model_id")
        return ident if isinstance(ident, str) else None
    load_index = parts[2] if len(parts) >= 3 else None
    if (
        parts[0] == "load_case"
        and len(parts) >= 3
        and parts[1] == "loads"
        and isinstance(load_index, int)
    ):
        loads = data.get("load_case", {})
        if isinstance(loads, Mapping):
            items = loads.get("loads")
            if isinstance(items, list) and isinstance(items[parts[2]], Mapping):
                ident = items[parts[2]].get("id")
                return ident if isinstance(ident, str) else None
    if isinstance(parts[0], str) and len(parts) >= 2 and isinstance(parts[1], int):
        return _collection_item_id(data, parts[0], parts[1])
    return data.get("model_id") if isinstance(data.get("model_id"), str) else None


def _duplicate_id_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    collections = (
        ("nodes", "node"),
        ("materials", "material"),
        ("sections", "section"),
        ("elements", "element"),
        ("constraints", "constraint"),
    )
    for name, entity_type in collections:
        rows = data.get(name)
        if not isinstance(rows, list):
            continue
        seen: dict[str, int] = {}
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or not isinstance(row.get("id"), str):
                continue
            ident = row["id"]
            if ident in seen:
                items.append(
                    make_diagnostic(
                        "SHELL-ID-E001",
                        entity_type=entity_type,
                        entity_id=ident,
                        json_path=json_path([name, index, "id"]),
                        observed=ident,
                        threshold="unique within collection",
                        unit=None,
                    )
                )
            else:
                seen[ident] = index

    load_case = data.get("load_case")
    if isinstance(load_case, Mapping) and isinstance(load_case.get("loads"), list):
        seen_loads: dict[str, int] = {}
        for index, row in enumerate(load_case["loads"]):
            if not isinstance(row, Mapping) or not isinstance(row.get("id"), str):
                continue
            ident = row["id"]
            if ident in seen_loads:
                items.append(
                    make_diagnostic(
                        "SHELL-ID-E001",
                        entity_type="load",
                        entity_id=ident,
                        json_path=json_path(["load_case", "loads", index, "id"]),
                        observed=ident,
                        threshold="unique within collection",
                        unit=None,
                    )
                )
            else:
                seen_loads[ident] = index
    return items


def _unit_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    units = data.get("units")
    if units is None:
        return [
            make_diagnostic(
                "SHELL-UNIT-E001",
                entity_type="document",
                entity_id=data.get("model_id") if isinstance(data.get("model_id"), str) else None,
                json_path="$.units",
                observed=None,
                threshold=SI_UNITS,
                unit=None,
                message="units object is missing.",
            )
        ]
    if not isinstance(units, Mapping):
        return [
            make_diagnostic(
                "SHELL-UNIT-E001",
                entity_type="document",
                entity_id=data.get("model_id") if isinstance(data.get("model_id"), str) else None,
                json_path="$.units",
                observed=type(units).__name__,
                threshold=SI_UNITS,
                unit=None,
            )
        ]
    items: list[Diagnostic] = []
    for field, expected in SI_UNITS.items():
        if field not in units:
            items.append(
                make_diagnostic(
                    "SHELL-UNIT-E001",
                    entity_type="document",
                    entity_id=None,
                    json_path=json_path(["units", field]),
                    observed=None,
                    threshold=expected,
                    unit=expected,
                    message=f"units.{field} is missing.",
                )
            )
        elif units[field] != expected:
            items.append(
                make_diagnostic(
                    "SHELL-UNIT-E001",
                    entity_type="document",
                    entity_id=None,
                    json_path=json_path(["units", field]),
                    observed=units[field],
                    threshold=expected,
                    unit=expected,
                    message=f"units.{field} must be the frozen SI constant {expected!r}.",
                )
            )
    return items


def _material_section_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    for index, row in enumerate(data.get("materials") or []):
        if not isinstance(row, Mapping):
            continue
        ident = row.get("id") if isinstance(row.get("id"), str) else None
        young = row.get("young_modulus")
        if _is_number(young) and young <= 0:
            items.append(
                make_diagnostic(
                    "SHELL-MAT-E001",
                    entity_type="material",
                    entity_id=ident,
                    json_path=json_path(["materials", index, "young_modulus"]),
                    observed=young,
                    threshold=0,
                    unit="Pa",
                )
            )
        poisson = row.get("poisson_ratio")
        if _is_number(poisson) and (poisson <= -1 or poisson >= 0.5):
            items.append(
                make_diagnostic(
                    "SHELL-MAT-E002",
                    entity_type="material",
                    entity_id=ident,
                    json_path=json_path(["materials", index, "poisson_ratio"]),
                    observed=poisson,
                    threshold={"exclusiveMinimum": -1, "exclusiveMaximum": 0.5},
                    unit=None,
                )
            )
    for index, row in enumerate(data.get("sections") or []):
        if not isinstance(row, Mapping):
            continue
        ident = row.get("id") if isinstance(row.get("id"), str) else None
        thickness = row.get("thickness")
        if _is_number(thickness) and thickness <= 0:
            items.append(
                make_diagnostic(
                    "SHELL-SEC-E001",
                    entity_type="section",
                    entity_id=ident,
                    json_path=json_path(["sections", index, "thickness"]),
                    observed=thickness,
                    threshold=0,
                    unit="m",
                )
            )
        ks = row.get("shear_correction_factor")
        if _is_number(ks) and ks <= 0:
            items.append(
                make_diagnostic(
                    "SHELL-SEC-E002",
                    entity_type="section",
                    entity_id=ident,
                    json_path=json_path(["sections", index, "shear_correction_factor"]),
                    observed=ks,
                    threshold=0,
                    unit=None,
                )
            )
    return items


def _id_set(rows: Any) -> dict[str, int]:
    mapping: dict[str, int] = {}
    if not isinstance(rows, list):
        return mapping
    for index, row in enumerate(rows):
        if isinstance(row, Mapping) and isinstance(row.get("id"), str):
            mapping.setdefault(row["id"], index)
    return mapping


def _reference_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    node_ids = _id_set(data.get("nodes"))
    material_ids = _id_set(data.get("materials"))
    section_ids = _id_set(data.get("sections"))
    element_ids = _id_set(data.get("elements"))

    for index, row in enumerate(data.get("sections") or []):
        if not isinstance(row, Mapping):
            continue
        material_id = row.get("material_id")
        if isinstance(material_id, str) and material_id not in material_ids:
            items.append(
                make_diagnostic(
                    "SHELL-REF-E001",
                    entity_type="section",
                    entity_id=row.get("id") if isinstance(row.get("id"), str) else None,
                    json_path=json_path(["sections", index, "material_id"]),
                    observed=material_id,
                    threshold=sorted(material_ids),
                    unit=None,
                )
            )

    for index, row in enumerate(data.get("elements") or []):
        if not isinstance(row, Mapping):
            continue
        ident = row.get("id") if isinstance(row.get("id"), str) else None
        section_id = row.get("section_id")
        if isinstance(section_id, str) and section_id not in section_ids:
            items.append(
                make_diagnostic(
                    "SHELL-REF-E001",
                    entity_type="element",
                    entity_id=ident,
                    json_path=json_path(["elements", index, "section_id"]),
                    observed=section_id,
                    threshold=sorted(section_ids),
                    unit=None,
                )
            )
        node_ids_value = row.get("node_ids")
        if isinstance(node_ids_value, list):
            if len(node_ids_value) != 4 or len(set(node_ids_value)) != len(node_ids_value):
                items.append(
                    make_diagnostic(
                        "SHELL-TOP-E001",
                        entity_type="element",
                        entity_id=ident,
                        json_path=json_path(["elements", index, "node_ids"]),
                        observed=node_ids_value,
                        threshold=4,
                        unit=None,
                    )
                )
            for node_pos, node_id in enumerate(node_ids_value):
                if isinstance(node_id, str) and node_id not in node_ids:
                    items.append(
                        make_diagnostic(
                            "SHELL-REF-E001",
                            entity_type="element",
                            entity_id=ident,
                            json_path=json_path(["elements", index, "node_ids", node_pos]),
                            observed=node_id,
                            threshold=sorted(node_ids),
                            unit=None,
                        )
                    )

    for index, row in enumerate(data.get("constraints") or []):
        if not isinstance(row, Mapping):
            continue
        node_id = row.get("node_id")
        if isinstance(node_id, str) and node_id not in node_ids:
            items.append(
                make_diagnostic(
                    "SHELL-REF-E001",
                    entity_type="constraint",
                    entity_id=row.get("id") if isinstance(row.get("id"), str) else None,
                    json_path=json_path(["constraints", index, "node_id"]),
                    observed=node_id,
                    threshold=sorted(node_ids),
                    unit=None,
                )
            )

    load_case = data.get("load_case")
    loads = load_case.get("loads") if isinstance(load_case, Mapping) else None
    if isinstance(loads, list):
        for index, row in enumerate(loads):
            if not isinstance(row, Mapping):
                continue
            ident = row.get("id") if isinstance(row.get("id"), str) else None
            load_type = row.get("type")
            if load_type == "nodal_load":
                node_id = row.get("node_id")
                if isinstance(node_id, str) and node_id not in node_ids:
                    items.append(
                        make_diagnostic(
                            "SHELL-REF-E001",
                            entity_type="load",
                            entity_id=ident,
                            json_path=json_path(["load_case", "loads", index, "node_id"]),
                            observed=node_id,
                            threshold=sorted(node_ids),
                            unit=None,
                        )
                    )
            elif load_type in {"surface_traction", "body_force"}:
                field = "element_ids"
                for pos, element_id in enumerate(row.get(field) or []):
                    if isinstance(element_id, str) and element_id not in element_ids:
                        items.append(
                            make_diagnostic(
                                "SHELL-REF-E001",
                                entity_type="load",
                                entity_id=ident,
                                json_path=json_path(["load_case", "loads", index, field, pos]),
                                observed=element_id,
                                threshold=sorted(element_ids),
                                unit=None,
                            )
                        )
            elif load_type == "edge_traction":
                element_id = row.get("element_id")
                if isinstance(element_id, str) and element_id not in element_ids:
                    items.append(
                        make_diagnostic(
                            "SHELL-REF-E001",
                            entity_type="load",
                            entity_id=ident,
                            json_path=json_path(["load_case", "loads", index, "element_id"]),
                            observed=element_id,
                            threshold=sorted(element_ids),
                            unit=None,
                        )
                    )
                local_edge = row.get("local_edge")
                if local_edge is not None and local_edge not in {1, 2, 3, 4}:
                    items.append(
                        make_diagnostic(
                            "SHELL-LOAD-E001",
                            entity_type="load",
                            entity_id=ident,
                            json_path=json_path(["load_case", "loads", index, "local_edge"]),
                            observed=local_edge,
                            threshold=[1, 2, 3, 4],
                            unit=None,
                        )
                    )
            elif load_type is not None:
                items.append(
                    make_diagnostic(
                        "SHELL-LOAD-E001",
                        entity_type="load",
                        entity_id=ident,
                        json_path=json_path(["load_case", "loads", index, "type"]),
                        observed=load_type,
                        threshold=["nodal_load", "surface_traction", "edge_traction", "body_force"],
                        unit=None,
                    )
                )
    return items


def _option_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    options = data.get("analysis_options")
    if not isinstance(options, Mapping):
        return []
    items: list[Diagnostic] = []
    purpose = options.get("run_purpose")
    shear = options.get("shear_formulation")
    drilling = options.get("drilling")
    drilling_formulation = drilling.get("formulation") if isinstance(drilling, Mapping) else None
    diagnostic_switch = shear == VERIFICATION_SHEAR or drilling_formulation == VERIFICATION_DRILLING
    if purpose == "production" and diagnostic_switch:
        items.append(
            make_diagnostic(
                "SHELL-OPT-E001",
                entity_type="analysis_options",
                entity_id=None,
                json_path="$.analysis_options",
                observed={
                    "run_purpose": purpose,
                    "shear_formulation": shear,
                    "drilling": drilling_formulation,
                },
                threshold={
                    "shear_formulation": PRODUCTION_SHEAR,
                    "drilling": PRODUCTION_DRILLING,
                },
                unit=None,
            )
        )
    elif purpose == "verification" and diagnostic_switch:
        items.append(
            make_diagnostic(
                "SHELL-OPT-I001",
                entity_type="analysis_options",
                entity_id=None,
                json_path="$.analysis_options",
                observed={
                    "run_purpose": purpose,
                    "shear_formulation": shear,
                    "drilling": drilling_formulation,
                },
                threshold="verification-only comparison",
                unit=None,
            )
        )
    return items


def _constraint_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    seen: dict[tuple[str, str], tuple[float, int, str | None]] = {}
    for index, row in enumerate(data.get("constraints") or []):
        if not isinstance(row, Mapping):
            continue
        node_id = row.get("node_id")
        dof = row.get("dof")
        value = row.get("value")
        ident = row.get("id") if isinstance(row.get("id"), str) else None
        if not isinstance(node_id, str) or not isinstance(dof, str) or not _is_number(value):
            continue
        finite_value = _as_finite_float(value)
        if finite_value is None:
            continue
        key = (node_id, dof)
        if key in seen:
            previous_value, _, _ = seen[key]
            code = "SHELL-BC-W001" if previous_value == finite_value else "SHELL-BC-E001"
            items.append(
                make_diagnostic(
                    code,
                    entity_type="constraint",
                    entity_id=ident,
                    json_path=json_path(["constraints", index]),
                    observed={"node_id": node_id, "dof": dof, "value": value},
                    threshold=previous_value,
                    unit="m" if dof in {"UX", "UY", "UZ"} else "rad",
                )
            )
        else:
            seen[key] = (finite_value, index, ident)
    return items


def _geometry_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        return items
    node_coords: dict[str, list[float]] = {}
    for row in nodes:
        if isinstance(row, Mapping) and isinstance(row.get("id"), str):
            coords = row.get("coordinates")
            if isinstance(coords, list) and len(coords) == 3:
                finite_coords = [_as_finite_float(item) for item in coords]
                if all(item is not None for item in finite_coords):
                    node_coords[row["id"]] = [item for item in finite_coords if item is not None]

    directed_edges: dict[frozenset[str], list[tuple[str, tuple[str, str]]]] = {}
    for index, row in enumerate(data.get("elements") or []):
        if not isinstance(row, Mapping):
            continue
        ident = row.get("id") if isinstance(row.get("id"), str) else None
        node_ids = row.get("node_ids")
        if not isinstance(node_ids, list) or len(node_ids) != 4:
            continue
        if any(node_id not in node_coords for node_id in node_ids):
            continue
        points = [node_coords[node_id] for node_id in node_ids]
        quality = evaluate_element_quality(points)
        path = json_path(["elements", index])
        if quality is None:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E001",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed="cannot_build_local_basis",
                    threshold="distinct nodes 1,2,4 forming a right-handed triad",
                    unit="m",
                )
            )
            continue
        if quality.shape != "strictly_convex" or quality.r_edge <= EDGE_RATIO_ERROR:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E001",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed={
                        "shape": quality.shape,
                        "r_edge": quality.r_edge,
                        "l_char": quality.l_char,
                    },
                    threshold={"shape": "strictly_convex", "r_edge": EDGE_RATIO_ERROR},
                    unit="1",
                )
            )
        if quality.r_warp > WARP_ERROR:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E002",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed=quality.r_warp,
                    threshold=WARP_ERROR,
                    unit="1",
                )
            )
        elif quality.r_warp > WARP_WARNING:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-W001",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed=quality.r_warp,
                    threshold=WARP_WARNING,
                    unit="1",
                )
            )
        if min(quality.det_j) <= 0.0:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E003",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed=list(quality.det_j),
                    threshold=0,
                    unit="m^2",
                )
            )
        elif quality.jhat_min <= JHAT_ERROR:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E004",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed=quality.jhat_min,
                    threshold=JHAT_ERROR,
                    unit="1",
                )
            )
        elif quality.jhat_min <= JHAT_WARNING or quality.r_j < RJ_WARNING:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-W002",
                    entity_type="element",
                    entity_id=ident,
                    json_path=path,
                    observed={"jhat_min": quality.jhat_min, "r_j": quality.r_j},
                    threshold={"jhat_min": JHAT_WARNING, "r_j": RJ_WARNING},
                    unit="1",
                )
            )

        if ident is not None and all(isinstance(node_id, str) for node_id in node_ids):
            for local_a, local_b in Q4_LOCAL_EDGES:
                left = node_ids[local_a]
                right = node_ids[local_b]
                key = frozenset((left, right))
                directed_edges.setdefault(key, []).append((ident, (left, right)))

    for key, occurrences in directed_edges.items():
        if len(occurrences) < 2:
            continue
        if len(occurrences) > 2:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E001",
                    entity_type="element",
                    entity_id=occurrences[0][0],
                    json_path="$.elements",
                    observed={
                        "nodes": sorted(key),
                        "element_ids": [item[0] for item in occurrences],
                    },
                    threshold="at most two elements per interior edge",
                    unit=None,
                )
            )
            continue
        (_, first), (_, second) = occurrences
        if first == second:
            items.append(
                make_diagnostic(
                    "SHELL-GEO-E005",
                    entity_type="element",
                    entity_id=occurrences[1][0],
                    json_path="$.elements",
                    observed={
                        "nodes": list(first),
                        "element_ids": [item[0] for item in occurrences],
                    },
                    threshold="shared edges must be opposite",
                    unit=None,
                )
            )
    return items


def semantic_diagnostics(data: Mapping[str, Any]) -> list[Diagnostic]:
    items: list[Diagnostic] = []
    items.extend(_finite_number_diagnostics(data))
    items.extend(_unit_diagnostics(data))
    items.extend(_duplicate_id_diagnostics(data))
    items.extend(_material_section_diagnostics(data))
    items.extend(_reference_diagnostics(data))
    items.extend(_constraint_diagnostics(data))
    items.extend(_option_diagnostics(data))
    items.extend(_geometry_diagnostics(data))
    return items


def _try_model_input(data: Mapping[str, Any]) -> ModelInput | None:
    try:
        return ModelInput.from_dict(data)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _global_dof_index(node_index: int, dof: DofName) -> int:
    return DOF_PER_NODE_GLOBAL * node_index + DOF_OFFSET[dof]


def _build_validated_model(
    model: ModelInput,
    model_sha256: str,
    diagnostics: tuple[Diagnostic, ...],
) -> ValidatedModel:
    nodes: list[NodeRecord] = []
    node_index_by_id: dict[str, int] = {}
    for index, node in enumerate(model.nodes):
        node_index_by_id[node.id] = index
        base = DOF_PER_NODE_GLOBAL * index
        nodes.append(
            NodeRecord(
                id=node.id,
                index=index,
                coordinates=node.coordinates,
                dof_indices=(
                    base + 0,
                    base + 1,
                    base + 2,
                    base + 3,
                    base + 4,
                    base + 5,
                ),
            )
        )

    materials: list[MaterialRecord] = []
    material_index_by_id: dict[str, int] = {}
    for index, material in enumerate(model.materials):
        material_index_by_id[material.id] = index
        materials.append(
            MaterialRecord(
                id=material.id,
                index=index,
                type=material.type,
                young_modulus=material.young_modulus,
                poisson_ratio=material.poisson_ratio,
            )
        )

    sections: list[SectionRecord] = []
    section_index_by_id: dict[str, int] = {}
    for index, section in enumerate(model.sections):
        section_index_by_id[section.id] = index
        sections.append(
            SectionRecord(
                id=section.id,
                index=index,
                type=section.type,
                material_id=section.material_id,
                material_index=material_index_by_id[section.material_id],
                thickness=section.thickness,
                shear_correction_factor=section.shear_correction_factor,
            )
        )

    elements: list[ElementGeometryRecord] = []
    element_index_by_id: dict[str, int] = {}
    for index, element in enumerate(model.elements):
        element_index_by_id[element.id] = index
        points = [
            model.nodes[node_index_by_id[node_id]].coordinates for node_id in element.node_ids
        ]
        quality = evaluate_element_quality(points)
        if quality is None:
            raise RuntimeError(f"solvable model is missing geometry for {element.id}")
        node_indices = tuple(node_index_by_id[node_id] for node_id in element.node_ids)
        elements.append(
            ElementGeometryRecord(
                id=element.id,
                index=index,
                type=element.type,
                node_ids=element.node_ids,
                node_indices=(node_indices[0], node_indices[1], node_indices[2], node_indices[3]),
                section_id=element.section_id,
                section_index=section_index_by_id[element.section_id],
                l_char=quality.l_char,
                local_basis=quality.local_basis.lambda_rows,
                local_coordinates=quality.local_coordinates,
                r_warp=quality.r_warp,
                r_edge=quality.r_edge,
                det_j=quality.det_j,
                r_j=quality.r_j,
                jhat_min=quality.jhat_min,
            )
        )

    loads: list[NormalizedLoad] = []
    for load in model.load_case.loads:
        if load.type == "nodal_load":
            loads.append(
                NormalizedNodalLoad(
                    id=load.id,
                    type="nodal_load",
                    node_id=load.node_id,
                    node_index=node_index_by_id[load.node_id],
                    force_global=load.force_global,
                    moment_global=load.moment_global,
                )
            )
        elif load.type == "surface_traction":
            loads.append(
                NormalizedSurfaceTraction(
                    id=load.id,
                    type="surface_traction",
                    element_ids=load.element_ids,
                    element_indices=tuple(element_index_by_id[item] for item in load.element_ids),
                    traction_global=load.traction_global,
                )
            )
        elif load.type == "edge_traction":
            loads.append(
                NormalizedEdgeTraction(
                    id=load.id,
                    type="edge_traction",
                    element_id=load.element_id,
                    element_index=element_index_by_id[load.element_id],
                    local_edge=load.local_edge,
                    traction_global=load.traction_global,
                )
            )
        else:
            loads.append(
                NormalizedBodyForce(
                    id=load.id,
                    type="body_force",
                    element_ids=load.element_ids,
                    element_indices=tuple(element_index_by_id[item] for item in load.element_ids),
                    force_density_global=load.force_density_global,
                )
            )

    constraints: list[NormalizedConstraint] = []
    seen_dofs: set[tuple[str, str]] = set()
    for constraint in model.constraints:
        key = (constraint.node_id, constraint.dof)
        if key in seen_dofs:
            continue
        seen_dofs.add(key)
        node_index = node_index_by_id[constraint.node_id]
        constraints.append(
            NormalizedConstraint(
                id=constraint.id,
                node_id=constraint.node_id,
                node_index=node_index,
                dof=constraint.dof,
                dof_index=_global_dof_index(node_index, constraint.dof),
                value=constraint.value,
                unit="m" if constraint.dof in {"UX", "UY", "UZ"} else "rad",
            )
        )

    return ValidatedModel(
        model_id=model.model_id,
        schema_version=model.schema_version,
        model_sha256=model_sha256,
        title=model.title,
        units=model.units,
        nodes=tuple(nodes),
        materials=tuple(materials),
        sections=tuple(sections),
        elements=tuple(elements),
        load_case_id=model.load_case.id,
        loads=tuple(loads),
        constraints=tuple(constraints),
        analysis_options=model.analysis_options,
        diagnostics=tuple(item for item in diagnostics if item.severity != "error"),
    )


def validate_model(source: ModelInput | Mapping[str, Any] | str | Path) -> ValidationResult:
    """Validate a ModelInput document. Never mutates the caller object."""

    diagnostics: list[Diagnostic] = []
    raw: dict[str, Any] | None
    model_sha256: str | None = None
    if isinstance(source, ModelInput):
        raw = source.to_dict()
        input_model: ModelInput | None = source
        model_sha256 = canonical_sha256(raw)
    else:
        try:
            loaded = load_document(source)
            raw = loaded.data
            model_sha256 = loaded.sha256
            input_model = _try_model_input(raw)
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raw = None
            input_model = None
            diagnostics.append(
                make_diagnostic(
                    "SHELL-SCHEMA-E001",
                    entity_type="document",
                    entity_id=None,
                    json_path="$",
                    observed=str(exc),
                    threshold="JSON object matching contract 1.0.0",
                    unit=None,
                    message="Document is not a readable ModelInput JSON object.",
                )
            )

    model_id = None
    if raw is not None and isinstance(raw.get("model_id"), str):
        model_id = raw["model_id"]
    elif input_model is not None:
        model_id = input_model.model_id

    if raw is not None:
        if raw.get("document_type") not in {None, "model_input"}:
            diagnostics.append(
                make_diagnostic(
                    "SHELL-SCHEMA-E001",
                    entity_type="document",
                    entity_id=model_id,
                    json_path="$.document_type",
                    observed=raw.get("document_type"),
                    threshold="model_input",
                    unit=None,
                )
            )
        diagnostics.extend(schema_diagnostics(raw, target="ModelInput"))
        diagnostics.extend(semantic_diagnostics(raw))

    ordered = sort_diagnostics(diagnostics)
    errors = tuple(item for item in ordered if item.severity == "error")
    validated = None
    if not errors and input_model is not None and raw is not None:
        digest = model_sha256 if model_sha256 is not None else canonical_sha256(raw)
        validated = _build_validated_model(input_model, digest, ordered)

    return ValidationResult(
        schema_version=SCHEMA_VERSION,
        model_id=model_id,
        input_model=input_model,
        diagnostics=ordered,
        solvable=validated is not None,
        validated_model=validated,
    )


def validate_analysis_result(source: Mapping[str, Any] | str | Path) -> tuple[Diagnostic, ...]:
    try:
        raw = load_json(source)
    except (
        OSError,
        TypeError,
        ValueError,
        OverflowError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        return sort_diagnostics(
            [
                make_diagnostic(
                    "SHELL-SCHEMA-E001",
                    entity_type="document",
                    entity_id=None,
                    json_path="$",
                    observed=str(exc),
                    threshold="JSON object matching AnalysisResult 1.0.0",
                    unit=None,
                )
            ]
        )
    diagnostics = schema_diagnostics(raw, target="AnalysisResult")
    diagnostics.extend(_finite_number_diagnostics(raw))
    return sort_diagnostics(diagnostics)


# Imported by type checkers / tests; keep public names explicit.
__all__ = [
    "validate_model",
    "validate_analysis_result",
    "semantic_diagnostics",
    "AnalysisOptions",
    "Constraint",
    "Units",
]
