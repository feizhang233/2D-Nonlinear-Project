"""One error/limit boundary, while each spatial family retains its wire convention."""

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nonlinear_api.app import create_app
from nonlinear_api.iam_store import IdentityStore
from nonlinear_api.schemas import ApiLimits

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = ("frame3d", "continuum3d", "plate3d", "shell3d")


@pytest.mark.parametrize("family,dofs", list(zip(FAMILIES, (6, 3, 3, 6), strict=True)))
def test_spatial_openapi_documents_real_success_errors_and_limits(family, dofs):
    path = "3d" if family == "frame3d" else family
    with TestClient(
        create_app(limits=ApiLimits(max_dofs=24), identity_store=IdentityStore(":memory:"))
    ) as client:
        document = client.get("/openapi.json").json()
        capability = client.get(f"/api/v1/{path}/capabilities")
        assert capability.status_code == 200
        assert capability.json()["max_nodes"] == 24 // dofs
        published = document["paths"][f"/api/v1/{path}/capabilities"]["get"]
        assert "$ref" in published["responses"]["200"]["content"]["application/json"]["schema"]
        solve = document["paths"][f"/api/v1/{path}/solve"]["post"]
        for code in ("413", "422", "429", "500"):
            assert solve["responses"][code]["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/ApiErrorResponse"
            }
        invalid = client.post(f"/api/v1/{path}/solve", json={})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_spatial_families_do_not_import_each_others_routes_or_solvers():
    for package in ("nonlinear_core", "nonlinear_api"):
        for family in FAMILIES:
            path = ROOT / "src" / package / f"{family}.py"
            if not path.exists():
                continue
            imports = [
                node.module
                for node in ast.walk(ast.parse(path.read_text()))
                if isinstance(node, ast.ImportFrom)
            ]
            for other in set(FAMILIES) - {family}:
                assert f"{package}.{other}" not in imports, path
