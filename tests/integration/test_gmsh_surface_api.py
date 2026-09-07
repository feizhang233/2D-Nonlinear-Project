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
        "tests/fixtures/p12/q4-plane-strain-tension.json",
        "tests/fixtures/p13/von-karman-mitc4-plate.json",
        "tests/fixtures/p14/corotational-flat-shell.json",
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


def _cad_model(hole_kind="circle"):
    from math import cos, pi, sin

    model = json.loads((ROOT / "tests/fixtures/p12/q4-plane-strain-tension.json").read_text())
    # Concave L-shaped domain: arbitrary outline, not the example rectangle.
    outer = [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]]
    shape = {"kind": hole_kind, "center": [1, 1], "radius": 0.35, "width": 0.6, "height": 0.4}
    if hole_kind == "circle":
        hole = [[1 + 0.35 * cos(i * pi / 2), 1 + 0.35 * sin(i * pi / 2)] for i in range(4)]
    else:
        h = 0.3 if hole_kind == "square" else 0.2
        hole = [[0.7, 1 - h], [1.3, 1 - h], [1.3, 1 + h], [0.7, 1 + h]]
    model.setdefault("extensions", {})["geometry"] = {
        "vertices": [{"id": f"G{i}", "coordinates": p} for i, p in enumerate(outer + hole)],
        "loops": [
            {"id": "outer", "kind": "outer", "vertex_ids": [f"G{i}" for i in range(6)]},
            {
                "id": "H1",
                "kind": "hole",
                "vertex_ids": [f"G{i}" for i in range(6, 10)],
                "shape": shape,
            },
        ],
    }
    return model


@pytest.mark.parametrize("kind", ["circle", "rectangle", "square"])
def test_cad_concave_outline_and_dimensioned_holes(kind):
    from math import hypot, pi

    from nonlinear_api.meshing import generate_surface_mesh
    from nonlinear_api.schemas import SurfaceMeshRequest

    mesh = generate_surface_mesh(
        SurfaceMeshRequest.model_validate({"model": _cad_model(kind), "mesh_size": 0.25})
    )
    used = {node_id for element in mesh.elements for node_id in element.node_ids}
    assert used == {node.id for node in mesh.nodes}  # Arc centers must not create free DOFs.
    assert len(mesh.boundaries) == 10
    assert all(len(element.node_ids) == 4 for element in mesh.elements)
    nodes = {node.id: node.coordinates for node in mesh.nodes}
    hole_nodes = {node_id for boundary in mesh.boundaries[6:] for node_id in boundary.node_ids}
    if kind == "circle":
        assert all(
            hypot(nodes[node][0] - 1, nodes[node][1] - 1) == pytest.approx(0.35, abs=1e-8)
            for node in hole_nodes
        )
        assert sum(b.length for b in mesh.boundaries[6:]) == pytest.approx(2 * pi * 0.35, rel=0.025)
    for boundary in mesh.boundaries:
        assert all(
            a.node_ids[1] == b.node_ids[0]
            for a, b in zip(boundary.segments, boundary.segments[1:], strict=False)
        )
        assert len(boundary.node_ids) == len(boundary.segments) + 1
    for element in mesh.elements:
        x, y = [sum(nodes[n][axis] for n in element.node_ids) / 4 for axis in range(2)]
        assert x < 2 or y < 2
        if kind == "circle":
            assert hypot(x - 1, y - 1) > 0.34


@pytest.mark.parametrize("bad", ["outside", "crossing", "radius", "mismatch"])
def test_rejects_invalid_cad_before_native_meshing(bad):
    from nonlinear_api.meshing import SurfaceMeshError, generate_surface_mesh
    from nonlinear_api.schemas import SurfaceMeshRequest

    model = _cad_model()
    geometry = model["extensions"]["geometry"]
    if bad == "outside":
        for vertex in geometry["vertices"][6:]:
            vertex["coordinates"][0] += 5
        geometry["loops"][1]["shape"]["center"][0] += 5
    elif bad == "crossing":
        geometry["loops"][0]["vertex_ids"][1:3] = ["G2", "G1"]
    elif bad == "radius":
        geometry["loops"][1]["shape"]["radius"] = -1
    else:
        geometry["loops"][1]["shape"]["radius"] = 0.5
    with pytest.raises(SurfaceMeshError, match="Invalid CAD geometry"):
        generate_surface_mesh(
            SurfaceMeshRequest.model_validate({"model": model, "mesh_size": 0.25})
        )


def test_cad_mesh_boundary_load_preserves_force_resultant_and_linear_direction():
    import numpy as np

    from nonlinear_api.meshing import generate_surface_mesh
    from nonlinear_api.schemas import SurfaceMeshRequest
    from nonlinear_core import ModelInput, get_adapter

    document = _cad_model()
    mesh = generate_surface_mesh(
        SurfaceMeshRequest.model_validate({"model": document, "mesh_size": 0.5})
    )
    boundary = mesh.boundaries[1]
    document["nodes"] = [node.model_dump(mode="json") for node in mesh.nodes]
    document["elements"] = [element.model_dump(mode="json") for element in mesh.elements]
    document["constraints"] = []
    document["analysis"] = {"control_method": "load"}
    document["loads"] = [
        {
            "id": "Q",
            "kind": "edge",
            "element_id": boundary.segments[0].element_id,
            "coordinate_system": "global",
            "components": {"UX": 2500, "UY": -3000},
            "extensions": {
                "local_edge": boundary.segments[0].local_edge,
                "boundary_id": boundary.id,
                "edge_segments": [segment.model_dump(mode="json") for segment in boundary.segments],
            },
        }
    ]
    model = ModelInput.model_validate(document)
    adapter = get_adapter(model)
    response = adapter.evaluate(model, np.zeros(len(adapter.dof_map(model))))
    assert boundary.length == pytest.approx(2)
    assert response.external_force[0::2].sum() == pytest.approx(5000)
    assert response.external_force[1::2].sum() == pytest.approx(-6000)
