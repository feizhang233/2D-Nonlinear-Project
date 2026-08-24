"""Gmsh Q4 surface-mesh service and HTTP contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nonlinear_api import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    (
        "examples/p12/q4-plane-strain-tension.json",
        "examples/p13/von-karman-mitc4-plate.json",
        "examples/p14/corotational-flat-shell.json",
    ),
)
def test_gmsh_endpoint_returns_q4_mesh_and_boundary_segment_ownership(path: str):
    model = json.loads((ROOT / path).read_text(encoding="utf-8"))

    with TestClient(create_app()) as client:
        response = client.post("/api/v1/meshes", json={"model": model, "mesh_size": 0.5})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["engine"] == "Gmsh"
    assert payload["nodes"]
    assert payload["elements"]
    assert all(len(element["node_ids"]) == 4 for element in payload["elements"])
    assert len(payload["boundaries"]) == 4
    assert all(boundary["segments"] for boundary in payload["boundaries"])
    element_ids = {element["id"] for element in payload["elements"]}
    assert all(
        segment["element_id"] in element_ids
        for boundary in payload["boundaries"]
        for segment in boundary["segments"]
    )
