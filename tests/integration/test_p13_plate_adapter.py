"""P13 contract, registry, core limit, recovery, validation, and API integration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_core import (
    PlateAdapter,
    VonKarmanPlateAdapter,
    get_adapter,
    validate_model_input,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "p13" / "von-karman-mitc4-plate.json"


def _document() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _model():
    validation = validate_model_input(_document())
    assert validation.valid and validation.model is not None
    return validation.model


def _plate_indices() -> np.ndarray:
    return np.asarray(
        [index for node in range(4) for index in (5 * node + 2, 5 * node + 3, 5 * node + 4)]
    )


def test_von_karman_formulation_expands_plate_dofs_without_changing_linear_plate_contract():
    nonlinear = _model()
    nonlinear_order = tuple(reference.dof.value for reference in nonlinear.ordered_dof_refs())
    assert nonlinear_order[:5] == ("UX", "UY", "UZ", "RX", "RY")
    assert len(nonlinear_order) == 20

    linear_document = _document()
    linear_document["elements"][0]["formulation"] = "Q4-plate"
    linear_document["constraints"] = [
        constraint
        for constraint in linear_document["constraints"]
        if constraint["dof"] in {"UZ", "RX", "RY"}
    ]
    linear_validation = validate_model_input(linear_document)
    assert linear_validation.valid and linear_validation.model is not None
    linear_order = tuple(
        reference.dof.value for reference in linear_validation.model.ordered_dof_refs()
    )
    assert linear_order[:3] == ("UZ", "RX", "RY")
    assert len(linear_order) == 12


def test_registry_selects_von_karman_adapter_and_retains_energy_and_raw_gauss_results():
    model = _model()
    adapter = get_adapter(model)
    displacement = np.zeros(20, dtype=float)
    displacement[[7, 12]] = -0.05
    displacement[[8, 13]] = 0.03

    response = adapter.evaluate(model, displacement, load_factor=0.5)
    recovery = adapter.recover(model, displacement, load_factor=0.5)

    assert isinstance(adapter, VonKarmanPlateAdapter)
    assert adapter.validate(model).valid
    assert response.min_det_j is not None and response.min_det_j > 0.0
    assert response.strain_energy > 0.0
    assert response.metadata["membrane_energy"] > 0.0
    assert response.strain_energy == (
        response.metadata["membrane_energy"]
        + response.metadata["bending_energy"]
        + response.metadata["shear_energy"]
    )
    element = recovery.element_data[0]
    assert element["formulation"] == "Q4-von-karman-MITC4"
    assert element["kinematic_scope"] == "moderate-rotation-small-strain"
    assert len(element["gauss_points"]) == 4
    assert all("membrane_resultant" in point for point in element["gauss_points"])
    assert recovery.metadata["nodal_averaging"] == "not-applied"


def test_small_displacement_transverse_limit_matches_installed_linear_plate_adapter():
    nonlinear_model = _model()
    linear_document = _document()
    linear_document["elements"][0]["formulation"] = "Q4-plate"
    linear_document["constraints"] = [
        constraint
        for constraint in linear_document["constraints"]
        if constraint["dof"] in {"UZ", "RX", "RY"}
    ]
    linear_validation = validate_model_input(linear_document)
    assert linear_validation.valid and linear_validation.model is not None
    linear_model = linear_validation.model
    plate_displacement = 1.0e-8 * np.linspace(-0.5, 0.6, 12)
    nonlinear_displacement = np.zeros(20, dtype=float)
    nonlinear_displacement[_plate_indices()] = plate_displacement

    nonlinear = get_adapter(nonlinear_model).evaluate(
        nonlinear_model,
        nonlinear_displacement,
    )
    linear_adapter = get_adapter(linear_model)
    linear = linear_adapter.evaluate(linear_model, plate_displacement)

    assert isinstance(linear_adapter, PlateAdapter)
    np.testing.assert_allclose(
        nonlinear.tangent[np.ix_(_plate_indices(), _plate_indices())],
        linear.tangent,
        rtol=3.0e-15,
        atol=2.0e-9,
    )
    assert (
        np.linalg.norm(nonlinear.internal_force[_plate_indices()] - linear.internal_force)
        / np.linalg.norm(linear.internal_force)
        < 1.0e-7
    )


def test_non_mitc4_plate_request_is_rejected_without_fallback():
    document = _document()
    document["elements"][0]["properties"]["shear_scheme"] = "reduced"
    validation = validate_model_input(document)
    assert validation.valid and validation.model is not None

    result = VonKarmanPlateAdapter().validate(validation.model)

    assert not result.valid
    assert "shear_scheme='mitc4'" in result.errors[0].message


def test_api_exposes_raw_plate_gauss_results_without_nodal_overwrite():
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
    assert len(raw["gauss_point_response"]["records"]) == 4
    assert all(
        "membrane_resultant" in point
        for point in raw["gauss_point_response"]["records"]
    )
    assert post_result["derived_fields"] == []
    assert post_result["metadata"]["nodal_averaging"] == "not-applied"
