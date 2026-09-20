"""Real ASGI requests through both the existing backend and standalone 3D app."""

import base64
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nonlinear_api.app import create_app
from nonlinear_api.iam_store import IdentityStore
from reused_cores.frame3d_linear.api import app as standalone

app = create_app(identity_store=IdentityStore(":memory:"))


@pytest.fixture
def payload():
    return {
        "nodes": [{"id": 1, "x": 0, "y": 0, "z": 0}, {"id": 2, "x": 2, "y": 0, "z": 0}],
        "elements": [
            {
                "id": 1,
                "node_i": 1,
                "node_j": 2,
                "E": 200e9,
                "G": 80e9,
                "A": 0.01,
                "Iy": 8e-6,
                "Iz": 5e-6,
                "J": 1e-5,
                "reference_vector": [0, 1, 0],
            }
        ],
        "supports": [
            {"node_id": 1, "u": True, "v": True, "w": True, "rx": True, "ry": True, "rz": True}
        ],
        "nodal_loads": [{"node_id": 2, "fy": 1000, "fz": 1000, "mx": 2000}],
        "section_points": [{"y": 0.05, "z": 0}],
        "number_of_points": 5,
        "include_plots": False,
    }


@pytest.mark.parametrize(
    "application,path", [(app, "/api/v1/3d/solve"), (standalone, "/api/v1/solve")]
)
def test_solve_response_contract(application, path, payload):
    before = deepcopy(payload)
    response = TestClient(application).post(path, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["nodal_displacements"][1]["v"] == pytest.approx(8e3 / 3e6)
    assert body["nodal_displacements"][1]["w"] == pytest.approx(8e3 / 4.8e6)
    assert body["nodal_displacements"][1]["rx"] == pytest.approx(0.005)
    assert body["nodal_reactions"][0]["my"] == pytest.approx(2000)
    assert body["validation"]["passed"]
    assert body["active_dof_count"] == 6
    assert body["inactive_dof_vectors"] == []
    assert body["plots"] is None
    assert body["section_points"] == payload["section_points"]
    element = body["elements"][0]
    assert len(element["local_end_forces"]) == 12
    assert len(element["fields"]["normal_stress"][0]) == 5
    assert element["fields"]["normal_stress"][0][0] == pytest.approx(-20e6)
    assert element["validation"]["passed"]
    assert payload == before


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_z",
        "unknown_field",
        "negative_J",
        "bool_number",
        "parallel_axis",
        "zero_length",
        "no_supports",
        "translation_support_only",
        "unknown_node",
        "missing_shear_area",
        "timoshenko_line",
        "bad_release",
        "singular_release",
        "conflicting_settlement",
        "loaded_inactive",
        "oversized_sampling",
        "overflow",
    ],
)
def test_invalid_models_return_422(mutation, payload):
    element = payload["elements"][0]
    if mutation == "missing_z":
        del payload["nodes"][1]["z"]
    if mutation == "unknown_field":
        payload["nonlinear"] = True
    if mutation == "negative_J":
        element["J"] = -1
    if mutation == "bool_number":
        element["E"] = True
    if mutation == "parallel_axis":
        element["reference_vector"] = [1, 0, 0]
    if mutation == "zero_length":
        payload["nodes"][1]["x"] = 0
    if mutation == "no_supports":
        payload["supports"] = []
    if mutation == "translation_support_only":
        payload["supports"] = [{"node_id": 1, "u": True, "v": True, "w": True}]
    if mutation == "unknown_node":
        element["node_j"] = 3
    if mutation == "missing_shear_area":
        element["theory"] = "timoshenko"
    if mutation == "timoshenko_line":
        element.update(theory="timoshenko", Asy=0.008, Asz=0.008)
        payload["distributed_loads"] = [{"element_id": 1, "qy_i": 1000}]
    if mutation == "bad_release":
        element["releases"] = [7]
    if mutation == "singular_release":
        element["releases"] = [3, 9]
    if mutation == "conflicting_settlement":
        payload["supports"].append({"node_id": 1, "u": True, "u_value": 0.001})
    if mutation == "loaded_inactive":
        element["releases"] = [11]
        payload["nodal_loads"] = [{"node_id": 2, "mz": 100}]
    if mutation == "oversized_sampling":
        payload["number_of_points"] = 2002
    if mutation == "overflow":
        element.update(E=1e308, A=1e308)
    response = TestClient(app).post("/api/v1/3d/solve", json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["message"]


def test_timoshenko_and_settlement_are_exposed(payload):
    payload["elements"][0].update(theory="timoshenko", Asy=0.008, Asz=0.008)
    payload["supports"][0]["v_value"] = 0.001
    result = TestClient(app).post("/api/v1/3d/solve", json=payload)
    assert result.status_code == 200
    body = result.json()
    assert body["nodal_displacements"][1]["v"] == pytest.approx(
        0.001 + 8e3 / 3e6 + 2000 / (80e9 * 0.008)
    )
    assert body["validation"]["passed"]


def test_released_end_returned_separately_from_joint_gauge(payload):
    payload["elements"][0]["releases"] = [11]
    payload["nodal_loads"] = []
    payload["supports"].append({"node_id": 2, "u": True, "v": True, "w": True})
    payload["distributed_loads"] = [{"element_id": 1, "qy_i": 1000, "qy_j": 1000}]
    response = TestClient(app).post("/api/v1/3d/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body["inactive_dof_vectors"]) == 1
    assert body["nodal_displacements"][1]["rz"] == 0
    assert body["elements"][0]["local_displacements"][11] == pytest.approx(-1 / 6000)
    assert body["validation"]["passed"]


def test_plots_and_direct_png_endpoint(payload):
    client = TestClient(app)
    payload.update(include_plots=True, plot_dpi=72)
    response = client.post("/api/v1/3d/solve", json=payload)
    assert response.status_code == 200
    plots = response.json()["plots"]
    assert set(plots) == {
        "axial_force",
        "shear_force_y",
        "shear_force_z",
        "torsional_moment",
        "bending_moment_y",
        "bending_moment_z",
    }
    for plot in plots.values():
        assert base64.b64decode(plot["data_uri"].split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")
    direct = client.post("/api/v1/3d/plots/bending_moment_z", json=payload)
    assert direct.status_code == 200
    assert direct.headers["content-type"] == "image/png"
    assert direct.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert client.post("/api/v1/3d/plots/invalid", json=payload).status_code == 422


def test_openapi_and_2d_schema_are_kept_separate(payload):
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert "/api/v1/analyses" in schema["paths"]
    assert "/api/v1/3d/solve" in schema["paths"]
    assert client.post("/api/v1/analyses", json=payload).status_code == 422
    assert TestClient(standalone).get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("name", ["cantilever_3d.json", "space_frame_3d.json"])
def test_documented_examples(name):
    path = Path(__file__).resolve().parents[1] / "fixtures" / "frame3d" / name
    response = TestClient(app).post("/api/v1/3d/solve", json=json.loads(path.read_text()))
    assert response.status_code == 200, response.text
    assert response.json()["validation"]["passed"]


def test_host_limits_and_error_envelope(payload):
    from nonlinear_api.schemas import ApiLimits

    bounded = create_app(limits=ApiLimits(max_dofs=6))
    client = TestClient(bounded)
    response = client.post("/api/v1/3d/solve", json=payload)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FRAME3D_MODEL_LIMIT"
    assert client.get("/api/v1/3d/capabilities").json()["max_nodes"] == 1
    payload["number_of_points"] = 2001
    payload["section_points"] = [{"y": 0.0, "z": 0.0}] * 500
    response = TestClient(app).post("/api/v1/3d/solve", json=payload)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FRAME3D_RECOVERY_LIMIT"


def test_busy_analysis_releases_slot_after_failure(payload):
    from nonlinear_api.frame3d import _solve_slot

    assert _solve_slot.acquire(blocking=False)
    try:
        response = TestClient(app).post("/api/v1/3d/solve", json=payload)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "FRAME3D_BUSY"
    finally:
        _solve_slot.release()
    invalid = deepcopy(payload)
    invalid["supports"] = []
    assert TestClient(app).post("/api/v1/3d/solve", json=invalid).status_code == 422
    assert TestClient(app).post("/api/v1/3d/solve", json=payload).status_code == 200
