"""Canonical P1 parsing, semantic validation, and schema helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import ValidationError

from nonlinear_core.constants import SCHEMA_VERSION
from nonlinear_core.model import (
    ContractModel,
    DofRef,
    ElementInput,
    LoadInput,
    LoadKind,
    ModelInput,
    model_dof_order,
)


class ContractIssue(ContractModel):
    code: str
    json_path: str
    message: str


class ModelValidationResult(ContractModel):
    model: ModelInput | None = None
    errors: tuple[ContractIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return self.model is not None and not self.errors


def validate_model_json(text: str) -> ModelValidationResult:
    """Parse a JSON document and retain syntax or contract failures as data."""

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        return ModelValidationResult(
            errors=(
                ContractIssue(
                    code="CONTRACT_INVALID_JSON",
                    json_path="$",
                    message=f"{error.msg} at line {error.lineno}, column {error.colno}",
                ),
            )
        )
    return validate_model_input(document)


def validate_model_input(document: Any) -> ModelValidationResult:
    """Validate structure, identifiers, references, targets, and family DOFs."""

    try:
        model = ModelInput.model_validate(document)
    except ValidationError as error:
        return ModelValidationResult(errors=tuple(_pydantic_issues(error)))

    semantic_errors = tuple(_semantic_issues(model))
    if semantic_errors:
        return ModelValidationResult(errors=semantic_errors)
    return ModelValidationResult(model=model)


def canonical_model_json(model: ModelInput) -> str:
    """Serialize a validated model deterministically without changing entity order."""

    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def model_input_json_schema() -> dict[str, Any]:
    """Return the public Draft 2020-12 schema for ``ModelInput``."""

    schema = ModelInput.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = (
        f"https://schemas.feizhang233.com/nonlinear-core/model-input-{SCHEMA_VERSION}.schema.json"
    )
    schema["title"] = f"Nonlinear Core ModelInput {SCHEMA_VERSION}"
    schema["$comment"] = (
        "Duplicate identifiers, cross-entity references, load targets, and model-family DOFs "
        "are semantic rules enforced by nonlinear_core.validate_model_input."
    )
    return schema


def _pydantic_issues(error: ValidationError) -> Iterable[ContractIssue]:
    code_map = {
        "extra_forbidden": "CONTRACT_UNKNOWN_FIELD",
        "missing": "CONTRACT_MISSING_FIELD",
        "json_invalid": "CONTRACT_INVALID_JSON",
        "literal_error": "CONTRACT_INVALID_VALUE",
    }
    for item in error.errors(include_url=False):
        error_type = str(item["type"])
        yield ContractIssue(
            code=code_map.get(error_type, "CONTRACT_INVALID_VALUE"),
            json_path=_loc_to_json_path(item.get("loc", ())),
            message=str(item["msg"]),
        )


def _loc_to_json_path(location: Sequence[Any]) -> str:
    path = "$"
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            path += f".{part}"
        else:
            escaped = str(part).replace("\\", "\\\\").replace("'", "\\'")
            path += f"['{escaped}']"
    return path


def _semantic_issues(model: ModelInput) -> Iterable[ContractIssue]:
    groups: tuple[tuple[str, Sequence[Any]], ...] = (
        ("nodes", model.nodes),
        ("elements", model.elements),
        ("materials", model.materials),
        ("loads", model.loads),
        ("constraints", model.constraints),
    )
    for group_name, items in groups:
        yield from _duplicate_id_issues(group_name, items)

    node_ids = {node.id for node in model.nodes}
    element_ids = {element.id for element in model.elements}
    material_ids = {material.id for material in model.materials}
    allowed_dofs = set(model_dof_order(model))

    for index, element in enumerate(model.elements):
        yield from _element_reference_issues(index, element, node_ids, material_ids)

    for index, load in enumerate(model.loads):
        yield from _load_target_issues(
            index,
            load,
            node_ids,
            element_ids,
            allowed_dofs,
            model.model_family.value,
        )

    seen_constraint_targets: set[tuple[str, Any]] = set()
    for index, constraint in enumerate(model.constraints):
        if constraint.node_id not in node_ids:
            yield _issue(
                "CONTRACT_INVALID_REFERENCE",
                f"$.constraints[{index}].node_id",
                f"unknown node_id {constraint.node_id!r}",
            )
        if constraint.dof not in allowed_dofs:
            yield _issue(
                "CONTRACT_INVALID_DOF",
                f"$.constraints[{index}].dof",
                f"DOF {constraint.dof.value!r} is not available for {model.model_family.value}",
            )
        target = (constraint.node_id, constraint.dof)
        if target in seen_constraint_targets:
            yield _issue(
                "CONTRACT_DUPLICATE_CONSTRAINT",
                f"$.constraints[{index}]",
                f"duplicate constraint target {constraint.node_id!r}/{constraint.dof.value}",
            )
        seen_constraint_targets.add(target)

    displacement = model.analysis.displacement_control
    if displacement is not None:
        yield from _dof_ref_issues(
            displacement.target,
            "$.analysis.displacement_control.target",
            node_ids,
            allowed_dofs,
            model.model_family.value,
        )


def _duplicate_id_issues(group_name: str, items: Sequence[Any]) -> Iterable[ContractIssue]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if item.id in seen:
            yield _issue(
                "CONTRACT_DUPLICATE_ID",
                f"$.{group_name}[{index}].id",
                f"duplicate {group_name[:-1]} id {item.id!r}",
            )
        seen.add(item.id)


def _element_reference_issues(
    index: int,
    element: ElementInput,
    node_ids: set[str],
    material_ids: set[str],
) -> Iterable[ContractIssue]:
    seen_nodes: set[str] = set()
    for node_index, node_id in enumerate(element.node_ids):
        path = f"$.elements[{index}].node_ids[{node_index}]"
        if node_id not in node_ids:
            yield _issue(
                "CONTRACT_INVALID_REFERENCE",
                path,
                f"unknown node_id {node_id!r}",
            )
        if node_id in seen_nodes:
            yield _issue(
                "CONTRACT_DUPLICATE_REFERENCE",
                path,
                f"node_id {node_id!r} is repeated in the element connectivity",
            )
        seen_nodes.add(node_id)
    if element.material_id not in material_ids:
        yield _issue(
            "CONTRACT_INVALID_REFERENCE",
            f"$.elements[{index}].material_id",
            f"unknown material_id {element.material_id!r}",
        )


def _load_target_issues(
    index: int,
    load: LoadInput,
    node_ids: set[str],
    element_ids: set[str],
    allowed_dofs: set[Any],
    family_name: str,
) -> Iterable[ContractIssue]:
    base = f"$.loads[{index}]"
    if load.kind is LoadKind.NODAL:
        allowed_component_names = {dof.value for dof in allowed_dofs}
        for component_name in load.components:
            component_path = f"{base}.components['{component_name}']"
            if component_name not in allowed_component_names:
                yield _issue(
                    "CONTRACT_INVALID_DOF",
                    component_path,
                    f"nodal component {component_name!r} is not available for {family_name}",
                )
        if load.node_id is None:
            yield _issue(
                "CONTRACT_MISSING_TARGET",
                f"{base}.node_id",
                "nodal loads require node_id",
            )
        elif load.node_id not in node_ids:
            yield _issue(
                "CONTRACT_INVALID_REFERENCE",
                f"{base}.node_id",
                f"unknown node_id {load.node_id!r}",
            )
        if load.element_id is not None:
            yield _issue(
                "CONTRACT_INVALID_TARGET",
                f"{base}.element_id",
                "nodal loads cannot define element_id",
            )
        return

    if load.kind in {LoadKind.ELEMENT, LoadKind.EDGE, LoadKind.SURFACE}:
        if load.element_id is None:
            yield _issue(
                "CONTRACT_MISSING_TARGET",
                f"{base}.element_id",
                f"{load.kind.value} loads require element_id",
            )
        elif load.element_id not in element_ids:
            yield _issue(
                "CONTRACT_INVALID_REFERENCE",
                f"{base}.element_id",
                f"unknown element_id {load.element_id!r}",
            )
        if load.node_id is not None:
            yield _issue(
                "CONTRACT_INVALID_TARGET",
                f"{base}.node_id",
                f"{load.kind.value} loads cannot define node_id",
            )
        return

    if load.node_id is not None or load.element_id is not None:
        path = f"{base}.node_id" if load.node_id is not None else f"{base}.element_id"
        yield _issue(
            "CONTRACT_INVALID_TARGET",
            path,
            "body loads apply to the model and cannot define node_id or element_id",
        )


def _dof_ref_issues(
    dof_ref: DofRef,
    base_path: str,
    node_ids: set[str],
    allowed_dofs: set[Any],
    family_name: str,
) -> Iterable[ContractIssue]:
    if dof_ref.node_id not in node_ids:
        yield _issue(
            "CONTRACT_INVALID_REFERENCE",
            f"{base_path}.node_id",
            f"unknown node_id {dof_ref.node_id!r}",
        )
    if dof_ref.dof not in allowed_dofs:
        yield _issue(
            "CONTRACT_INVALID_DOF",
            f"{base_path}.dof",
            f"DOF {dof_ref.dof.value!r} is not available for {family_name}",
        )


def _issue(code: str, json_path: str, message: str) -> ContractIssue:
    return ContractIssue(code=code, json_path=json_path, message=message)


__all__ = [
    "ContractIssue",
    "ModelValidationResult",
    "canonical_model_json",
    "model_input_json_schema",
    "validate_model_input",
    "validate_model_json",
]
