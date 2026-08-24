from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from nonlinear_core import validate_model_input, validate_model_json

CONTRACT_EXAMPLES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "contracts"


def load_contract_example(name: str) -> dict[str, object]:
    return json.loads((CONTRACT_EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("example_name", "expected_code", "expected_path"),
    [
        (
            "invalid-unknown-field.json",
            "CONTRACT_UNKNOWN_FIELD",
            "$.unexpected",
        ),
        (
            "invalid-duplicate-id.json",
            "CONTRACT_DUPLICATE_ID",
            "$.nodes[1].id",
        ),
        (
            "invalid-reference.json",
            "CONTRACT_INVALID_REFERENCE",
            "$.elements[0].node_ids[1]",
        ),
        (
            "invalid-missing-units.json",
            "CONTRACT_MISSING_FIELD",
            "$.units",
        ),
    ],
)
def test_invalid_contract_examples_have_structured_json_paths(
    example_name: str,
    expected_code: str,
    expected_path: str,
) -> None:
    result = validate_model_input(load_contract_example(example_name))

    assert not result.valid
    assert result.model is None
    assert any(
        error.code == expected_code and error.json_path == expected_path for error in result.errors
    )


def test_all_invalid_references_are_reported() -> None:
    result = validate_model_input(load_contract_example("invalid-reference.json"))

    paths = {error.json_path for error in result.errors}
    assert paths == {
        "$.elements[0].node_ids[1]",
        "$.elements[0].material_id",
        "$.loads[0].node_id",
        "$.constraints[0].node_id",
    }


def test_family_incompatible_dof_has_precise_path(
    valid_model_document: dict[str, object],
) -> None:
    document = deepcopy(valid_model_document)
    constraints = document["constraints"]
    assert isinstance(constraints, list)
    assert isinstance(constraints[0], dict)
    constraints[0]["dof"] = "UZ"

    result = validate_model_input(document)

    assert not result.valid
    assert any(
        error.code == "CONTRACT_INVALID_DOF" and error.json_path == "$.constraints[0].dof"
        for error in result.errors
    )


def test_missing_nodal_target_is_not_silently_accepted(
    valid_model_document: dict[str, object],
) -> None:
    document = deepcopy(valid_model_document)
    loads = document["loads"]
    assert isinstance(loads, list)
    assert isinstance(loads[0], dict)
    loads[0].pop("node_id")

    result = validate_model_input(document)

    assert any(
        error.code == "CONTRACT_MISSING_TARGET" and error.json_path == "$.loads[0].node_id"
        for error in result.errors
    )


def test_nodal_load_component_must_match_model_family_dof(
    valid_model_document: dict[str, object],
) -> None:
    document = deepcopy(valid_model_document)
    loads = document["loads"]
    assert isinstance(loads, list)
    assert isinstance(loads[0], dict)
    loads[0]["components"] = {"UZ": -1.0}

    result = validate_model_input(document)

    assert any(
        error.code == "CONTRACT_INVALID_DOF" and error.json_path == "$.loads[0].components['UZ']"
        for error in result.errors
    )


def test_control_specific_options_are_required(
    valid_model_document: dict[str, object],
) -> None:
    document = deepcopy(valid_model_document)
    analysis = document["analysis"]
    assert isinstance(analysis, dict)
    analysis["control_method"] = "displacement"

    result = validate_model_input(document)

    assert not result.valid
    assert any(error.json_path == "$.analysis" for error in result.errors)


def test_invalid_json_is_returned_as_a_contract_issue() -> None:
    result = validate_model_json('{"schema_version":')

    assert not result.valid
    assert result.errors[0].code == "CONTRACT_INVALID_JSON"
    assert result.errors[0].json_path == "$"
