"""JSON Schema Draft 2020-12 validation against the frozen P0 contract."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from reused_cores.shell3d_linear.constants import resolve_contract_schema_path
from reused_cores.shell3d_linear.diagnostics import Diagnostic, json_path, make_diagnostic


@lru_cache(maxsize=1)
def load_contract_schema() -> dict[str, Any]:
    schema_path = resolve_contract_schema_path()
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _definition_schema(name: str) -> dict[str, Any]:
    root = load_contract_schema()
    return {
        "$schema": root["$schema"],
        "$ref": f"#/$defs/{name}",
        "$defs": root["$defs"],
    }


@lru_cache(maxsize=4)
def _validator(target: str) -> Draft202012Validator:
    if target == "document":
        schema = load_contract_schema()
    else:
        schema = _definition_schema(target)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def iter_schema_errors(
    instance: Mapping[str, Any],
    *,
    target: str = "document",
) -> Iterator[ValidationError]:
    yield from _validator(target).iter_errors(instance)


def _path_from_error(error: ValidationError) -> str:
    return json_path(list(error.absolute_path))


def _map_schema_error(error: ValidationError) -> Diagnostic:
    path = _path_from_error(error)
    parts = [str(item) for item in error.absolute_path]
    joined = ".".join(parts)
    entity_type = "document"
    entity_id = None
    code = "SHELL-SCHEMA-E001"
    unit = None
    observed: Any = error.message
    threshold: Any = error.validator_value

    if joined == "units" or joined.startswith("units."):
        code = "SHELL-UNIT-E001"
        observed = error.instance
        unit = None
    elif joined.endswith("young_modulus"):
        code = "SHELL-MAT-E001"
        entity_type = "material"
        observed = error.instance
        unit = "Pa"
        threshold = 0
    elif joined.endswith("poisson_ratio"):
        code = "SHELL-MAT-E002"
        entity_type = "material"
        observed = error.instance
        threshold = {"exclusiveMinimum": -1, "exclusiveMaximum": 0.5}
    elif joined.endswith("thickness"):
        code = "SHELL-SEC-E001"
        entity_type = "section"
        observed = error.instance
        unit = "m"
        threshold = 0
    elif joined.endswith("shear_correction_factor"):
        code = "SHELL-SEC-E002"
        entity_type = "section"
        observed = error.instance
        threshold = 0
    elif "node_ids" in parts:
        code = "SHELL-TOP-E001"
        entity_type = "element"
        observed = error.instance
        threshold = 4
    elif "analysis_options" in parts and error.validator in {"const", "if", "then"}:
        code = "SHELL-OPT-E001"
        entity_type = "analysis_options"
        observed = error.instance
    elif joined.endswith("local_edge"):
        code = "SHELL-LOAD-E001"
        entity_type = "load"
        observed = error.instance
        threshold = [1, 2, 3, 4]

    if "materials" in parts:
        entity_type = "material"
    elif "sections" in parts:
        entity_type = "section"
    elif "elements" in parts:
        entity_type = "element"
    elif "nodes" in parts:
        entity_type = "node"
    elif "constraints" in parts:
        entity_type = "constraint"
    elif "loads" in parts or joined.startswith("load_case"):
        entity_type = "load"
    elif joined.startswith("analysis_options"):
        entity_type = "analysis_options"
    elif joined.startswith("units"):
        entity_type = "document"

    return make_diagnostic(
        code,
        entity_type=entity_type,
        entity_id=entity_id,
        json_path=path,
        observed=observed,
        threshold=threshold,
        unit=unit,
        message=error.message,
    )


def schema_diagnostics(
    instance: Mapping[str, Any],
    *,
    target: str = "ModelInput",
) -> list[Diagnostic]:
    return [_map_schema_error(error) for error in iter_schema_errors(instance, target=target)]
