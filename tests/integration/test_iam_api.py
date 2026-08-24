"""IAM and private model-history acceptance outside the mathematical core."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_api.iam_store import MODEL_HISTORY_LIMIT, IdentityStore

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "tests" / "fixtures" / "p9" / "shallow-arch-snap-through.json"


def _model() -> dict[str, object]:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def _register(client: TestClient, email: str, name: str = "Frame Engineer"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": "correct-horse-42"},
    )
    assert response.status_code == 201
    return response


def test_guest_can_analyze_but_cannot_use_model_history(tmp_path: Path) -> None:
    app = create_app(identity_store=IdentityStore(tmp_path / "iam.sqlite3"))
    with TestClient(app) as client:
        session = client.get("/api/v1/auth/session")
        listed = client.get("/api/v1/models")
        saved = client.post("/api/v1/models", json={"name": "Guest model", "model": _model()})
        analysis = client.post(
            "/api/v1/analyses",
            json={"model": _model(), "target_load_factor": 0.1},
        )

    assert session.json() == {"authenticated": False, "user": None}
    assert listed.status_code == 401
    assert listed.json()["error"]["code"] == "AUTH_REQUIRED"
    assert saved.status_code == 401
    assert analysis.status_code == 201


def test_register_login_logout_and_password_storage(tmp_path: Path) -> None:
    database = tmp_path / "iam.sqlite3"
    app = create_app(identity_store=IdentityStore(database))
    with TestClient(app) as client:
        registered = _register(client, "ENGINEER@example.com")
        assert registered.json()["authenticated"] is True
        assert registered.json()["user"]["email"] == "engineer@example.com"
        assert "httponly" in registered.headers["set-cookie"].lower()
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True

        duplicate = client.post(
            "/api/v1/auth/register",
            json={
                "email": "engineer@example.com",
                "display_name": "Other Engineer",
                "password": "another-password-42",
            },
        )
        assert duplicate.status_code == 409

        assert client.post("/api/v1/auth/logout").status_code == 204
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False
        invalid = client.post(
            "/api/v1/auth/login",
            json={"email": "engineer@example.com", "password": "wrong-password"},
        )
        assert invalid.status_code == 401
        logged_in = client.post(
            "/api/v1/auth/login",
            json={"email": "engineer@example.com", "password": "correct-horse-42"},
        )
        assert logged_in.status_code == 200

    with sqlite3.connect(database) as connection:
        password_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    assert password_hash.startswith("scrypt$")
    assert "correct-horse-42" not in database.read_bytes().decode("latin-1")


def test_model_history_is_persistent_bounded_and_user_isolated(tmp_path: Path) -> None:
    store = IdentityStore(tmp_path / "iam.sqlite3")
    app = create_app(identity_store=store)

    with TestClient(app) as alice, TestClient(app) as bob:
        _register(alice, "alice@example.com", "Alice")
        _register(bob, "bob@example.com", "Bob")

        created_ids: list[str] = []
        for index in range(MODEL_HISTORY_LIMIT + 1):
            response = alice.post(
                "/api/v1/models",
                json={"name": f"Alice model {index + 1}", "model": _model()},
            )
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        alice_models = alice.get("/api/v1/models")
        assert alice_models.status_code == 200
        assert len(alice_models.json()) == MODEL_HISTORY_LIMIT
        assert alice_models.json()[0]["name"] == f"Alice model {MODEL_HISTORY_LIMIT + 1}"
        assert created_ids[0] not in {entry["id"] for entry in alice_models.json()}

        assert bob.get("/api/v1/models").json() == []
        assert bob.delete(f"/api/v1/models/{created_ids[-1]}").status_code == 404
        assert alice.delete(f"/api/v1/models/{created_ids[-1]}").status_code == 204
        assert len(alice.get("/api/v1/models").json()) == MODEL_HISTORY_LIMIT - 1


def test_custom_display_names_round_trip_through_private_history(tmp_path: Path) -> None:
    app = create_app(identity_store=IdentityStore(tmp_path / "iam.sqlite3"))
    model = _model()
    model["extensions"] = {
        "ui": {
            "entity_names": {
                "materials": {"M1": "High-strength steel"},
                "constraints": {"N1": "West support"},
                "loads": {"P": "Service load"},
            }
        }
    }

    with TestClient(app) as client:
        _register(client, "names@example.com")
        created = client.post(
            "/api/v1/models",
            json={"name": "Named shallow arch", "model": model},
        )
        listed = client.get("/api/v1/models")

    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()[0]["model"]["extensions"] == model["extensions"]
