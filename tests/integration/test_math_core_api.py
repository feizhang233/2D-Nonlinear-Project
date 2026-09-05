"""HTTP acceptance for the bounded Step 2 Math Core bridge."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_api.math_cores import MAX_PARAMETER_VALUES


def test_math_core_catalog_exposes_all_operations_and_executable_examples():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/math-cores")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0.0"
    assert payload["limits"]["max_parameter_values"] == MAX_PARAMETER_VALUES
    assert {core["core_id"] for core in payload["cores"]} == {
        "plate_shell_buckling",
        "shell_instability",
        "constitutive_nonlinearity",
        "general_nonlinear_shell",
    }
    assert all(core["operations"] for core in payload["cores"])
    assert all(
        isinstance(operation["example_parameters"], dict)
        for core in payload["cores"]
        for operation in core["operations"]
    )


def test_math_core_execute_preserves_the_unified_response_envelope():
    request = {
        "schema_version": "1.0.0",
        "request_id": "web-lba-1",
        "core": "plate_shell_buckling",
        "operation": "linear_buckling",
        "parameters": {
            "material_stiffness": [[12.0, -2.0], [-2.0, 6.0]],
            "geometric_stiffness": [[1.0, 0.2], [0.2, 0.5]],
        },
    }
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/math-cores/execute", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "web-lba-1"
    assert payload["status"] == "ok"
    assert payload["error"] is None
    assert payload["data"]["analysis_level"] == "LBA"
    assert payload["diagnostics"]["residual_convention"].startswith("R=f_int")


def test_math_core_operation_errors_remain_machine_readable_and_input_is_bounded():
    with TestClient(create_app()) as client:
        unknown = client.post(
            "/api/v1/math-cores/execute",
            json={"core": "plate_shell_buckling", "operation": "missing"},
        )
        oversized = client.post(
            "/api/v1/math-cores/execute",
            json={
                "core": "plate_shell_buckling",
                "operation": "linear_buckling",
                "parameters": {"values": list(range(MAX_PARAMETER_VALUES + 1))},
            },
        )
        missing = client.get("/api/v1/math-cores/not-a-core")

    assert unknown.status_code == 200
    assert unknown.json()["status"] == "error"
    assert unknown.json()["error"]["code"] == "UNKNOWN_OPERATION"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "MATH_CORE_INPUT_LIMIT_EXCEEDED"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "UNKNOWN_CORE"
