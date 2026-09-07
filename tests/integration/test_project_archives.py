"""Portable model/result archives, persistent account snapshots, and section contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_api.iam_store import IdentityStore

ROOT = Path(__file__).resolve().parents[2]


def model():
    return json.loads((ROOT / "tests/fixtures/p9/shallow-arch-snap-through.json").read_text())


def section_model():
    value = model()
    value["extensions"]["section_library"] = {
        "definitions": [
            {
                "id": "S1",
                "name": "Beam",
                "shape": "rectangle",
                "dimensions": {"width": 0.1, "height": 0.2},
            }
        ],
        "default_id": "S1",
    }
    for element in value["elements"]:
        element["extensions"] = {"section_id": "S1"}
        element["properties"].update(area=0.02, second_moment=0.1 * 0.2**3 / 12)
    return value


def project(client, value):
    response = client.post("/api/v1/analyses", json={"model": value, "target_load_factor": 0.01})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "succeeded", response.text
    return {
        "studio_project_version": "1.0.0",
        "model": value,
        "workspace": {
            "run_options": {"targetLoadFactor": 0.01, "numberOfSteps": 4},
            "record": response.json(),
            "selected_step": 0,
            "result_view": "deformation",
            "result_tab": "curves",
        },
    }


def test_archive_round_trip_survives_service_restart_and_remains_private(tmp_path):
    database = tmp_path / "projects.sqlite3"
    with TestClient(create_app(identity_store=IdentityStore(database))) as client:
        archive = project(client, section_model())
        valid = client.post("/api/v1/projects/validate", json=archive)
        assert valid.status_code == 200, valid.text
        for view in ("moment", "shear", "axial"):
            with_view = copy.deepcopy(archive)
            with_view["workspace"]["result_view"] = view
            checked = client.post("/api/v1/projects/validate", json=with_view)
            assert checked.status_code == 200, checked.text
            assert checked.json()["workspace"]["result_view"] == view
        assert valid.json()["workspace"]["record"] == archive["workspace"]["record"]
        assert (
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": "archive@example.com",
                    "display_name": "Archive test",
                    "password": "archive-test-1234",
                },
            ).status_code
            == 201
        )
        saved = client.post(
            "/api/v1/models",
            json={"name": "With results", **{key: archive[key] for key in ("model", "workspace")}},
        )
        assert saved.status_code == 201, saved.text
    with TestClient(create_app(identity_store=IdentityStore(database))) as client:
        assert client.get("/api/v1/models").status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "archive@example.com",
                    "password": "archive-test-1234",
                },
            ).status_code
            == 200
        )
        loaded = client.get("/api/v1/models").json()[0]
        assert loaded["workspace"] == valid.json()["workspace"]
        assert (
            loaded["model"]["extensions"]["section_library"]
            == archive["model"]["extensions"]["section_library"]
        )
        assert (
            client.post(
                "/api/v1/projects/validate",
                json={
                    "studio_project_version": "1.0.0",
                    "model": loaded["model"],
                    "workspace": loaded["workspace"],
                },
            ).status_code
            == 200
        )


def test_archive_rejects_mismatched_model_results_and_unfinished_jobs():
    with TestClient(create_app()) as client:
        archive = project(client, model())
        changed = copy.deepcopy(archive)
        changed["model"]["nodes"][0]["coordinates"][0] += 0.1
        assert client.post("/api/v1/projects/validate", json=changed).status_code == 422
        changed = copy.deepcopy(archive)
        changed["workspace"]["record"]["result"]["model_sha256"] = "0" * 64
        assert client.post("/api/v1/projects/validate", json=changed).status_code == 422
        changed = copy.deepcopy(archive)
        changed["workspace"]["record"].update(status="running", result=None, completed_at=None)
        assert client.post("/api/v1/projects/validate", json=changed).status_code == 422
        changed = copy.deepcopy(archive)
        changed["workspace"]["record"] = None
        assert client.post("/api/v1/projects/validate", json=changed).status_code == 200


def test_section_assignment_is_validated_by_model_and_solve_endpoints():
    with TestClient(create_app()) as client:
        good = section_model()
        assert client.post("/api/v1/models/validate", json=good).json()["valid"]
        bad = copy.deepcopy(good)
        bad["elements"][0]["properties"]["area"] *= 2
        assert not client.post("/api/v1/models/validate", json=bad).json()["valid"]
        assert (
            client.post(
                "/api/v1/analyses", json={"model": bad, "target_load_factor": 0.01}
            ).status_code
            == 422
        )
        bad = copy.deepcopy(good)
        bad["extensions"]["section_library"]["definitions"][0]["dimensions"]["height"] = 0
        assert not client.post("/api/v1/models/validate", json=bad).json()["valid"]
