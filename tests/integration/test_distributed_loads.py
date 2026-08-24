"""Consistent distributed-load integration across nonlinear model families."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import ModelInput, get_adapter, validate_model_input

ROOT = Path(__file__).resolve().parents[2]


def _document(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _validated(document: dict[str, object]) -> ModelInput:
    validation = validate_model_input(document)
    assert validation.valid and validation.model is not None, validation.errors
    return validation.model


def test_corotational_frame_uniform_member_load_uses_consistent_reference_vector():
    model = ModelInput.model_validate(
        {
            "schema_version": "1.0.0",
            "model_id": "uniform-frame",
            "name": "uniform frame load",
            "model_family": "frame",
            "units": {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"},
            "nodes": [
                {"id": "N1", "coordinates": [0.0, 0.0]},
                {"id": "N2", "coordinates": [2.0, 0.0]},
            ],
            "materials": [{"id": "M1", "model": "linear-elastic", "parameters": {"young": 2.1e11}}],
            "elements": [
                {
                    "id": "E1",
                    "formulation": "frame2d-corotational",
                    "node_ids": ["N1", "N2"],
                    "material_id": "M1",
                    "properties": {"area": 0.01, "second_moment": 1.0e-6},
                }
            ],
            "loads": [
                {
                    "id": "Q",
                    "kind": "element",
                    "element_id": "E1",
                    "coordinate_system": "local",
                    "components": {"qx_i": 0.0, "qy_i": -3.0, "qx_j": 0.0, "qy_j": -3.0},
                }
            ],
            "constraints": [],
            "analysis": {"control_method": "load"},
        }
    )
    adapter = get_adapter(model)
    response = adapter.evaluate(model, np.zeros(6))

    np.testing.assert_allclose(
        response.external_force,
        [0.0, -3.0, -1.0, 0.0, -3.0, 1.0],
        rtol=0.0,
        atol=1.0e-14,
    )


def test_total_lagrangian_continuum_edge_line_load_preserves_resultant():
    document = _document("examples/p12/q4-plane-strain-tension.json")
    document["loads"] = [
        {
            "id": "Q",
            "kind": "edge",
            "element_id": "E1",
            "components": {"UX": 1000.0, "UY": 0.0},
            "extensions": {"local_edge": 1},
        }
    ]
    model = _validated(document)
    adapter = get_adapter(model)
    response = adapter.evaluate(model, np.zeros(8))

    assert response.external_force[2] == pytest.approx(500.0)
    assert response.external_force[4] == pytest.approx(500.0)
    assert response.external_force[0::2].sum() == pytest.approx(1000.0)


@pytest.mark.parametrize(
    ("path", "family", "pressure"),
    (
        ("examples/p13/von-karman-mitc4-plate.json", "plate", -100.0),
        ("examples/p14/corotational-flat-shell.json", "shell", -2.0),
    ),
)
def test_plate_and_shell_surface_loads_preserve_area_resultant(
    path: str, family: str, pressure: float
):
    document = _document(path)
    document["loads"] = [
        {
            "id": "P",
            "kind": "surface",
            "element_id": "E1",
            "components": {"UZ": pressure},
        }
    ]
    model = _validated(document)
    adapter = get_adapter(model)
    response = adapter.evaluate(model, np.zeros(len(adapter.dof_map(model))))
    stride = 5 if family == "plate" else 6

    assert response.external_force[2::stride].sum() == pytest.approx(pressure)
