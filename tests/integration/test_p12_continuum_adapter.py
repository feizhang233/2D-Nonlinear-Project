"""P12 registry, linear-limit, recovery, validation, and API integration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_core import (
    ContinuumAdapter,
    TotalLagrangianContinuumAdapter,
    get_adapter,
    validate_model_input,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "p12" / "q4-plane-strain-tension.json"


def _document() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _model():
    validation = validate_model_input(_document())
    assert validation.valid and validation.model is not None
    return validation.model


def test_registry_selects_total_lagrangian_adapter_and_retains_raw_gauss_results():
    model = _model()
    adapter = get_adapter(model)
    displacement = np.asarray([0.0, 0.0, 0.1, 0.01, 0.12, -0.03, 0.0, -0.02])

    response = adapter.evaluate(model, displacement, load_factor=0.5)
    recovery = adapter.recover(model, displacement, load_factor=0.5)

    assert isinstance(adapter, TotalLagrangianContinuumAdapter)
    assert adapter.validate(model).valid
    assert response.min_det_f is not None and response.min_det_f > 0.0
    assert response.min_det_j is not None and response.min_det_j > 0.0
    assert response.strain_energy > 0.0
    assert len(recovery.element_data) == 1
    element = recovery.element_data[0]
    assert element["formulation"] == "Q4-total-lagrangian"
    assert element["plane_mode"] == "plane_strain"
    assert len(element["gauss_points"]) == 4
    for point in element["gauss_points"]:
        assert point["det_f"] > 0.0
        assert len(point["second_piola"]) == 4
        assert len(point["cauchy"]) == 4


def test_small_strain_limit_matches_installed_continuum_math_q4():
    nonlinear_model = _model()
    linear_document = _document()
    linear_document["elements"][0]["formulation"] = "Q4"
    linear_document["materials"][0]["model"] = "linear-elastic"
    linear_validation = validate_model_input(linear_document)
    assert linear_validation.valid and linear_validation.model is not None
    linear_model = linear_validation.model
    displacement = 1.0e-7 * np.asarray([0.0, 0.0, 1.0, 0.2, 1.1, -0.1, 0.1, 0.3])

    nonlinear = get_adapter(nonlinear_model).evaluate(nonlinear_model, displacement)
    linear_adapter = get_adapter(linear_model)
    linear = linear_adapter.evaluate(linear_model, displacement)
    zero = get_adapter(nonlinear_model).evaluate(nonlinear_model, np.zeros(8))

    assert isinstance(linear_adapter, ContinuumAdapter)
    np.testing.assert_allclose(zero.tangent, linear.tangent, rtol=3.0e-15, atol=2.0e-9)
    assert (
        np.linalg.norm(nonlinear.internal_force - linear.internal_force)
        / np.linalg.norm(linear.internal_force)
        < 8.0e-8
    )


def test_plane_stress_and_non_tl_formulations_are_rejected_without_guessing():
    plane_stress = _document()
    plane_stress["materials"][0]["parameters"]["plane_mode"] = "plane_stress"
    plane_validation = validate_model_input(plane_stress)
    assert plane_validation.valid and plane_validation.model is not None

    not_tl = _document()
    not_tl["elements"][0]["formulation"] = "Q4-updated-lagrangian"
    not_tl_validation = validate_model_input(not_tl)
    assert not_tl_validation.valid and not_tl_validation.model is not None

    plane_result = TotalLagrangianContinuumAdapter().validate(plane_validation.model)
    assert not plane_result.valid
    assert "plane_mode='plane_strain'" in plane_result.errors[0].message
    assert isinstance(get_adapter(not_tl_validation.model), ContinuumAdapter)


def test_api_exposes_raw_gauss_stress_and_marks_nodal_smoothing_as_derived():
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyses",
            json={"model": _document(), "target_load_factor": 0.25},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "succeeded"
    post_result = payload["result"]["post_result"]
    raw = {field["name"]: field for field in post_result["raw_fields"]}
    derived = {field["name"]: field for field in post_result["derived_fields"]}
    assert len(raw["gauss_point_response"]["records"]) == 4
    assert all(point["det_f"] > 0.0 for point in raw["gauss_point_response"]["records"])
    smoothed = derived["nodal_smoothed_cauchy"]
    assert smoothed["is_derived"] is True
    assert "visualization only" in smoothed["source"]
    assert len(smoothed["records"]) == 4
