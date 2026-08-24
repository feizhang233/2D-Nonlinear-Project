from __future__ import annotations

import json
from copy import deepcopy

from nonlinear_core import (
    ControlMethod,
    Dof,
    ModelFamily,
    canonical_model_json,
    validate_model_input,
)


def test_valid_model_round_trip_is_stable(valid_model_document: dict[str, object]) -> None:
    first = validate_model_input(valid_model_document)

    assert first.valid
    assert first.errors == ()
    assert first.model is not None
    assert first.model.model_family is ModelFamily.FRAME
    assert first.model.analysis.control_method is ControlMethod.LOAD

    serialized = canonical_model_json(first.model)
    second = validate_model_input(json.loads(serialized))

    assert second.valid
    assert second.model == first.model
    assert second.model is not None
    assert canonical_model_json(second.model) == serialized


def test_entity_and_dof_order_are_deterministic(
    valid_model_document: dict[str, object],
) -> None:
    result = validate_model_input(valid_model_document)
    assert result.model is not None
    model = result.model

    assert model.entity_order() == {
        "nodes": ("N1", "N2"),
        "elements": ("E1",),
        "materials": ("M1",),
        "loads": ("L1",),
        "constraints": ("C1", "C2", "C3"),
    }
    assert tuple((item.node_id, item.dof) for item in model.ordered_dof_refs()) == (
        ("N1", Dof.UX),
        ("N1", Dof.UY),
        ("N1", Dof.RZ),
        ("N2", Dof.UX),
        ("N2", Dof.UY),
        ("N2", Dof.RZ),
    )
    assert tuple((item.node_id, item.dof) for item in model.free_dof_refs()) == (
        ("N2", Dof.UX),
        ("N2", Dof.UY),
        ("N2", Dof.RZ),
    )


def test_units_are_metadata_and_values_are_not_converted(
    valid_model_document: dict[str, object],
) -> None:
    result = validate_model_input(valid_model_document)
    assert result.model is not None

    model = result.model
    assert model.units.length == "m"
    assert model.units.force == "N"
    assert model.units.stress == "Pa"
    assert model.materials[0].parameters["young"] == 210_000_000_000.0


def test_displacement_and_arc_length_options_parse_when_complete(
    valid_model_document: dict[str, object],
) -> None:
    displacement_document = deepcopy(valid_model_document)
    displacement_analysis = displacement_document["analysis"]
    assert isinstance(displacement_analysis, dict)
    displacement_analysis["control_method"] = "displacement"
    displacement_analysis["displacement_control"] = {
        "target": {"node_id": "N2", "dof": "UY"},
        "increment": -0.01,
    }

    displacement_result = validate_model_input(displacement_document)
    assert displacement_result.valid

    arc_document = deepcopy(valid_model_document)
    arc_analysis = arc_document["analysis"]
    assert isinstance(arc_analysis, dict)
    arc_analysis["control_method"] = "arc_length"
    arc_analysis["arc_length"] = {
        "radius": 0.05,
        "min_radius": 0.001,
        "max_radius": 0.1,
        "beta": 1.0,
    }

    arc_result = validate_model_input(arc_document)
    assert arc_result.valid
