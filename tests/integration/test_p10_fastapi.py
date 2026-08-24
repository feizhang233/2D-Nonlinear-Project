"""P10 HTTP acceptance for OpenAPI, limits, success, and typed failures."""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient

from nonlinear_api import AnalysisService, ApiLimits, create_app
from nonlinear_core import get_adapter, solve_load_control

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "examples" / "p9" / "shallow-arch-snap-through.json"


def _model() -> dict[str, object]:
    return json.loads(ARCH.read_text(encoding="utf-8"))


def test_health_and_openapi_publish_only_the_planned_p10_paths():
    app = create_app()
    checked_in = json.loads((ROOT / "schemas" / "openapi-1.0.0.json").read_text(encoding="utf-8"))

    with TestClient(app) as client:
        health = client.get("/health")
        openapi = client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["execution_mode"] == "synchronous"
    assert health.json()["supported_execution_modes"] == [
        "synchronous",
        "asynchronous",
    ]
    assert health.json()["limits"] == {
        "max_request_bytes": 1_048_576,
        "max_dofs": 10_000,
    }
    assert openapi.status_code == 200
    assert openapi.json() == checked_in
    assert set(openapi.json()["paths"]) == {
        "/health",
        "/api/v1/auth/session",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/models",
        "/api/v1/models/validate",
        "/api/v1/models/{entry_id}",
        "/api/v1/meshes",
        "/api/v1/analyses",
        "/api/v1/analyses/{analysis_id}",
    }
    schemas = openapi.json()["components"]["schemas"]
    assert {"AnalysisRecord", "AnalysisStatus", "ApiErrorResponse"} <= set(schemas)


def test_validation_endpoint_retains_contract_locations_without_running_solver():
    app = create_app()
    invalid = _model()
    invalid["elements"][0]["material_id"] = "missing"

    with TestClient(app) as client:
        valid_response = client.post("/api/v1/models/validate", json=_model())
        invalid_response = client.post("/api/v1/models/validate", json=invalid)

    assert valid_response.status_code == 200
    assert valid_response.json()["valid"] is True
    assert valid_response.json()["execution_eligible"] is True
    assert valid_response.json()["dof_count"] == 9
    assert invalid_response.status_code == 200
    assert invalid_response.json()["valid"] is False
    assert invalid_response.json()["execution_eligible"] is False
    assert invalid_response.json()["errors"][0] == {
        "code": "CONTRACT_INVALID_REFERENCE",
        "json_path": "$.elements[0].material_id",
        "message": "unknown material_id 'missing'",
    }


def test_legal_frame_analysis_completes_and_is_retrievable():
    app = create_app()

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/analyses",
            json={"model": _model(), "target_load_factor": 0.1},
        )
        fetched = client.get(f"/api/v1/analyses/{created.json()['analysis_id']}")

    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "succeeded"
    assert payload["execution_mode"] == "synchronous"
    assert payload["dof_count"] == 9
    assert payload["error"] is None
    assert payload["result"]["status"] == "succeeded"
    assert payload["result"]["metadata"]["restart"]["restart_schema_version"] == "1.0.0"
    assert len(payload["result"]["steps"]) == 1
    assert payload["result"]["steps"][0]["response"]["displacement"][4] < -0.014
    post_result = payload["result"]["post_result"]
    assert post_result is not None
    fields = {field["name"]: field for field in post_result["raw_fields"]}
    assert {"displacement", "reaction", "element_response"} <= set(fields)
    displacement = fields["displacement"]["records"]
    assert displacement[4] == {
        "dof_index": 4,
        "node_id": "N2",
        "dof": "UY",
        "value": payload["result"]["steps"][0]["response"]["displacement"][4],
    }
    assert len(fields["reaction"]["records"]) == 9
    assert len(fields["element_response"]["records"]) == 2
    assert fetched.status_code == 200
    assert fetched.json() == payload


def test_invalid_analysis_and_missing_id_return_stable_4xx_errors():
    app = create_app()

    with TestClient(app) as client:
        invalid = client.post(
            "/api/v1/analyses",
            json={"model": {"schema_version": "1.0.0"}},
        )
        malformed = client.post(
            "/api/v1/analyses",
            json={"model": _model(), "number_of_steps": 0},
        )
        missing = client.get(f"/api/v1/analyses/{uuid4()}")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["category"] == "input"
    assert invalid.json()["error"]["code"] == "MODEL_VALIDATION_FAILED"
    assert invalid.json()["error"]["location"] == "$.model_id"
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert malformed.json()["error"]["location"] == "$.number_of_steps"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


def test_nonconvergence_is_a_failed_analysis_record_instead_of_http_500():
    app = create_app()
    model = _model()
    model["analysis"]["max_iterations"] = 1
    model["analysis"]["step_control"] = {"max_retries": 0}

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyses",
            json={"model": model, "target_load_factor": 0.31},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error"]["category"] == "computation"
    assert payload["error"]["code"] == "NONCONVERGENCE"
    assert payload["result"]["status"] == "failed"
    assert payload["result"]["failures"][-1]["code"] == "NONCONVERGENCE"
    assert payload["result"]["post_result"] is None
    assert "displacement" not in payload


def test_request_bytes_and_dof_limits_return_413_before_execution():
    byte_limited = create_app(limits=ApiLimits(max_request_bytes=1024))
    dof_limited = create_app(limits=ApiLimits(max_dofs=8))

    with TestClient(byte_limited) as client:
        oversized = client.post(
            "/api/v1/models/validate",
            json={"padding": "x" * 2048},
        )
    with TestClient(dof_limited) as client:
        validation = client.post("/api/v1/models/validate", json=_model())
        analysis = client.post("/api/v1/analyses", json={"model": _model()})

    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert validation.json()["execution_eligible"] is False
    assert validation.json()["limit_error"]["code"] == "DOF_LIMIT_EXCEEDED"
    assert analysis.status_code == 413
    assert analysis.json()["error"]["code"] == "DOF_LIMIT_EXCEEDED"


def test_async_analysis_exposes_running_progress_and_cooperative_cancel():
    started = Event()
    release = Event()

    def blocking_runner(model, payload):
        started.set()
        assert release.wait(timeout=2.0)
        return solve_load_control(
            get_adapter(model),
            model,
            target_load_factor=payload.target_load_factor or 0.1,
        ).result

    app = create_app(service=AnalysisService(runner=blocking_runner))
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/analyses",
            json={
                "model": _model(),
                "target_load_factor": 0.1,
                "execution_mode": "asynchronous",
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "queued"
        assert started.wait(timeout=1.0)
        analysis_id = created.json()["analysis_id"]
        running = client.get(f"/api/v1/analyses/{analysis_id}")
        assert running.json()["status"] == "running"
        assert running.json()["progress"]["current_step"] == 0
        cancelled = client.delete(f"/api/v1/analyses/{analysis_id}")
        assert cancelled.json()["status"] == "cancelled"
        release.set()
        time.sleep(0.05)
        assert client.get(f"/api/v1/analyses/{analysis_id}").json()["status"] == "cancelled"


def test_restart_payload_continues_from_the_authenticated_committed_state():
    app = create_app()
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/analyses",
            json={"model": _model(), "target_load_factor": 0.1},
        ).json()
        restart = first["result"]["metadata"]["restart"]
        continued = client.post(
            "/api/v1/analyses",
            json={
                "model": _model(),
                "target_load_factor": 0.2,
                "restart": restart,
            },
        )

    assert continued.status_code == 201
    payload = continued.json()
    assert payload["status"] == "succeeded"
    assert payload["result"]["steps"][0]["step_index"] > first["result"]["steps"][-1]["step_index"]
    committed = payload["result"]["metadata"]["restart"]["committed_state"]
    assert committed["load_factor"] == 0.2


def test_explicit_cors_origin_is_opt_in_and_supports_frontend_requests():
    app = create_app(cors_origins=("http://127.0.0.1:5173",))
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/analyses",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
