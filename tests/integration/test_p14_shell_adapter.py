"""P14 registry, recovery, option rejection, solve, and API integration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_core import (
    CorotationalShellAdapter,
    ShellAdapter,
    get_adapter,
    validate_model_input,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "tests" / "fixtures" / "p14" / "corotational-flat-shell.json"


def _document() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _model():
    validation = validate_model_input(_document())
    assert validation.valid and validation.model is not None
    return validation.model


def test_registry_selects_corotational_shell_without_changing_linear_shell_selection():
    nonlinear_model = _model()
    assert isinstance(get_adapter(nonlinear_model), CorotationalShellAdapter)

    linear_document = _document()
    linear_document["elements"][0]["formulation"] = "Q4-FLAT-SHELL-RM"
    linear_validation = validate_model_input(linear_document)
    assert linear_validation.valid and linear_validation.model is not None
    assert isinstance(get_adapter(linear_validation.model), ShellAdapter)


def test_adapter_retains_current_basis_energy_components_alpha_and_raw_nmq():
    model = _model()
    adapter = get_adapter(model)
    displacement = np.zeros(24, dtype=float)
    displacement[[8, 14]] = [-0.002, -0.0025]
    displacement[[9, 15]] = [0.003, 0.004]

    response = adapter.evaluate(model, displacement, load_factor=0.5)
    recovery = adapter.recover(model, displacement, load_factor=0.5)

    assert adapter.validate(model).valid
    assert response.strain_energy > 0.0
    assert response.strain_energy == (
        response.metadata["membrane_energy"]
        + response.metadata["bending_energy"]
        + response.metadata["shear_energy"]
        + response.metadata["drilling_energy"]
    )
    element = recovery.element_data[0]
    assert element["kinematic_scope"] == "large-rigid-rotation-small-local-strain"
    assert element["alpha_d"] == 1.0e-4
    assert len(element["current_basis"]) == 3
    assert len(element["gauss_points"]) == 4
    for point in element["gauss_points"]:
        assert len(point["membrane_resultant"]) == 3
        assert len(point["bending_resultant"]) == 3
        assert len(point["shear_resultant"]) == 2
        assert point["result_basis"] == "current-corotational-local"
    assert recovery.metadata["raw_resultants"] == ["N", "M", "Q"]
    assert recovery.metadata["nodal_averaging"] == "not-applied"


def test_surface_load_is_supported_and_non_si_request_is_rejected_without_fallback():
    distributed = _document()
    distributed["loads"][0] = {
        "id": "P1",
        "kind": "surface",
        "element_id": "E1",
        "components": {"UZ": -1.0},
    }
    distributed_validation = validate_model_input(distributed)
    assert distributed_validation.valid and distributed_validation.model is not None
    adapter = CorotationalShellAdapter()
    distributed_result = adapter.validate(distributed_validation.model)
    assert distributed_result.valid
    response = adapter.evaluate(distributed_validation.model, np.zeros(24))
    assert response.external_force[2::6].sum() == pytest.approx(-2.0)

    wrong_units = _document()
    wrong_units["units"]["length"] = "mm"
    unit_validation = validate_model_input(wrong_units)
    assert unit_validation.valid and unit_validation.model is not None
    unit_result = CorotationalShellAdapter().validate(unit_validation.model)
    assert not unit_result.valid
    assert "requires SI labels" in unit_result.errors[0].message


def test_api_solves_example_and_exposes_raw_nmq_without_nodal_overwrite():
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyses",
            json={"model": _document(), "target_load_factor": 1.0},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "succeeded"
    post_result = payload["result"]["post_result"]
    raw = {field["name"]: field for field in post_result["raw_fields"]}
    records = raw["gauss_point_response"]["records"]
    assert len(records) == 4
    assert all("membrane_resultant" in point for point in records)
    assert all("bending_resultant" in point for point in records)
    assert all("shear_resultant" in point for point in records)
    assert post_result["derived_fields"] == []
    assert post_result["metadata"]["nodal_averaging"] == "not-applied"
