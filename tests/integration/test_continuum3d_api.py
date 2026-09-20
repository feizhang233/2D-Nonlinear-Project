"""Product-level solves, independent analytic oracles and actual frontend fixtures."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from nonlinear_api import continuum3d
from nonlinear_api.app import create_app
from nonlinear_api.iam_store import IdentityStore
from nonlinear_api.schemas import ApiLimits
from nonlinear_core.continuum3d import SolidModel, solve_solid
from reused_cores.continuum3d_linear import reference as core

client = TestClient(create_app(identity_store=IdentityStore(":memory:")))
FIXTURES = Path(__file__).parents[1] / "fixtures" / "continuum3d"


@pytest.fixture(params=["hex8", "tet4"])
def payload(request):
    return json.loads((FIXTURES / f"{request.param}.json").read_text())


def test_actual_frontend_mesh_uniaxial_free_solve(payload):
    """Roller planes permit Poisson contraction; 1 MPa traction, E=200 GPa.

    Free interior DOFs exist. u=(sigma*x/E,-nu*sigma*y/E,-nu*sigma*z/E).
    Absolute displacement tolerance 1e-14 m; stress relative tolerance 1e-10.
    """
    before = deepcopy(payload)
    response = client.post("/api/v1/continuum3d/solve", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["free_dof_count"] > 0
    assert result["validation"]["passed"]
    for node, displacement in zip(payload["nodes"], result["nodal_displacements"], strict=True):
        expected = np.array([node["x"], -0.3 * node["y"], -0.3 * node["z"]]) * 5e-6
        np.testing.assert_allclose(displacement["value"], expected, atol=1e-14)
    for element in result["elements"]:
        assert len(element["points"]) == (8 if payload["elements"][0]["kind"] == "hex8" else 1)
        for point in element["points"]:
            np.testing.assert_allclose(point["stress"], [1e6, 0, 0, 0, 0, 0], atol=1e-4)
            assert point["von_mises"] == pytest.approx(1e6, rel=1e-10)
    reactions = np.array([n["value"] for n in result["nodal_reactions"]])
    np.testing.assert_allclose(reactions.sum(axis=0), [-1e6, 0, 0], atol=1e-6)
    assert result["strain_energy"] == pytest.approx(5.0, rel=1e-10)
    assert payload == before


def test_nonzero_prescribed_displacement_couples_free_equations(payload):
    payload["tractions"] = []
    for c in payload["constraints"]:
        if c["dof"] == "ux":
            c["value"] = 0.001
    for n in payload["nodes"]:
        if n["x"] == 2:
            payload["constraints"].append({"node_id": n["id"], "dof": "ux", "value": 0.00101})
    result = solve_solid(SolidModel.model_validate(payload))
    for node, displacement in zip(payload["nodes"], result["nodal_displacements"], strict=True):
        expected = [0.001 + 5e-6 * node["x"], -1.5e-6 * node["y"], -1.5e-6 * node["z"]]
        np.testing.assert_allclose(displacement["value"], expected, atol=1e-14)
    assert result["strain_energy"] == pytest.approx(5, rel=1e-8)
    assert result["validation"]["passed"]


@pytest.mark.parametrize(
    "mutation",
    [
        "unrestrained",
        "wrong_node",
        "duplicate_node",
        "duplicate_cell",
        "bad_material",
        "wrong_material",
        "unknown_field",
        "bool_E",
        "inverted",
        "collapsed",
        "conflict",
        "bad_face",
        "unknown_load_node",
        "overflow",
        "internal_face",
        "unused_node",
    ],
)
def test_invalid_models_are_actionable_422(payload, mutation):
    if mutation == "unrestrained":
        payload["constraints"] = []
    elif mutation == "wrong_node":
        payload["elements"][0]["nodes"][0] = 999
    elif mutation == "duplicate_node":
        payload["nodes"][1]["id"] = payload["nodes"][0]["id"]
    elif mutation == "duplicate_cell":
        payload["elements"].append({**payload["elements"][0], "id": 999})
    elif mutation == "bad_material":
        payload["materials"][0]["nu"] = 0.5
    elif mutation == "wrong_material":
        payload["elements"][0]["material_id"] = 999
    elif mutation == "unknown_field":
        payload["nonlinear"] = True
    elif mutation == "bool_E":
        payload["materials"][0]["E"] = True
    elif mutation == "inverted":
        for n in payload["nodes"]:
            n["z"] *= -1
    elif mutation == "collapsed":
        for n in payload["nodes"]:
            n["z"] = 0
    elif mutation == "conflict":
        payload["constraints"].append({**payload["constraints"][0], "value": 1})
    elif mutation == "bad_face":
        payload["tractions"][0]["face"] = 8
    elif mutation == "unknown_load_node":
        payload["nodal_loads"] = [{"node_id": 999, "force": [1, 0, 0]}]
    elif mutation == "overflow":
        payload["materials"][0]["E"] = 1e308
    elif mutation == "internal_face":
        from nonlinear_core.continuum3d import FACES

        counts = {}
        for e in payload["elements"]:
            for i, face in enumerate(FACES[e["kind"]]):
                key = tuple(sorted(e["nodes"][j] for j in face))
                if key in counts:
                    payload["tractions"] = [
                        {"element_id": e["id"], "face": i, "traction": [1, 0, 0]}
                    ]
                    break
                counts[key] = 1
            else:
                continue
            break
    elif mutation == "unused_node":
        payload["nodes"].append({"id": 999, "x": 5, "y": 5, "z": 5})
    response = client.post("/api/v1/continuum3d/solve", json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["message"]


def test_body_force_nodal_force_moments_and_fully_constrained(payload):
    payload["tractions"] = []
    payload["constraints"] = [
        {"node_id": n["id"], "dof": dof, "value": 0}
        for n in payload["nodes"]
        for dof in ["ux", "uy", "uz"]
    ]
    payload["body_force"] = [100, -200, 300]
    payload["nodal_loads"] = [{"node_id": payload["nodes"][-1]["id"], "force": [10, 20, 30]}]
    result = solve_solid(SolidModel.model_validate(payload))
    r = np.array([n["value"] for n in result["nodal_reactions"]])
    x = np.array([[n["x"], n["y"], n["z"]] for n in payload["nodes"]])
    np.testing.assert_allclose(r.sum(axis=0), -np.array([210, -380, 630]), atol=1e-10)
    expected_moment = -np.cross([1, 0.5, 0.5], [200, -400, 600]) - np.cross(x[-1], [10, 20, 30])
    np.testing.assert_allclose(np.cross(x, r).sum(axis=0), expected_moment, atol=1e-10)
    assert result["validation"]["passed"]
    assert result["free_dof_count"] == 0


def test_resource_limit_and_busy_slot_release(payload, monkeypatch):
    limited = TestClient(
        create_app(limits=ApiLimits(max_dofs=12), identity_store=IdentityStore(":memory:"))
    )
    assert limited.get("/api/v1/continuum3d/capabilities").json()["max_nodes"] == 4
    assert limited.post("/api/v1/continuum3d/solve", json=payload).status_code == 413
    assert continuum3d._solve_slot.acquire(blocking=False)
    try:
        assert client.post("/api/v1/continuum3d/solve", json=payload).status_code == 429
    finally:
        continuum3d._solve_slot.release()
    original = continuum3d.solve_solid
    monkeypatch.setattr(
        continuum3d, "solve_solid", lambda _: (_ for _ in ()).throw(ValueError("bad"))
    )
    assert client.post("/api/v1/continuum3d/solve", json=payload).status_code == 422
    monkeypatch.setattr(continuum3d, "solve_solid", original)
    assert client.post("/api/v1/continuum3d/solve", json=payload).status_code == 200


def test_manufactured_hex_body_force_convergence_with_free_interior_nodes():
    """u=(a*x²,0,0), E=1000, nu=.25, b=(-2a*1200,0,0).

    Exact boundary displacements; 2³ and 4³ meshes. L2 error ratio 4,
    energy-norm ratio 2. Integration uses independent 3-point quadrature.
    """
    errors = []
    a = 0.001
    for divisions in [2, 4]:
        x, cells = core.structured(divisions)
        model = SolidModel.model_validate(
            {
                "nodes": [{"id": i + 1, "x": p[0], "y": p[1], "z": p[2]} for i, p in enumerate(x)],
                "elements": [
                    {"id": i + 1, "kind": "hex8", "nodes": (cell + 1).tolist(), "material_id": 1}
                    for i, cell in enumerate(cells)
                ],
                "materials": [{"id": 1, "E": 1000, "nu": 0.25}],
                "constraints": [
                    {"node_id": i + 1, "dof": dof, "value": a * p[0] ** 2 if j == 0 else 0}
                    for i, p in enumerate(x)
                    if np.any((p == 0) | (p == 1))
                    for j, dof in enumerate(["ux", "uy", "uz"])
                ],
                "body_force": [-2 * a * 1200, 0, 0],
            }
        )
        result = solve_solid(model)
        assert result["free_dof_count"] > 0
        assert result["validation"]["passed"]
        u = np.array([n["value"] for n in result["nodal_displacements"]])
        l2 = energy = 0
        for cell in cells:
            for q, w in core.gauss("hex8", 3):
                shape, b, jac = core.point("hex8", x[cell], q)
                position = shape @ x[cell]
                du = shape @ u[cell] - [a * position[0] ** 2, 0, 0]
                de = b @ u[cell].ravel() - [2 * a * position[0], 0, 0, 0, 0, 0]
                l2 += du @ du * w * jac
                energy += de @ core.elastic(1000, 0.25) @ de * w * jac
        errors.append(np.sqrt([l2, energy]))
    np.testing.assert_allclose(errors[0] / errors[1], [4, 2], rtol=1e-7)


@pytest.mark.parametrize("kind,x,rank", [("tet4", core.TET, 6), ("hex8", core.CUBE, 18)])
def test_element_affine_skew_patch_rigid_modes_and_energy(kind, x, rank):
    x = x @ np.array([[1, 0.2, 0.3], [0.1, 1.2, 0.2], [0.2, 0.1, 0.9]]).T + [3, 4, 5]
    h = np.array([[0.001, 0.003, -0.001], [0.001, 0.002, 0.004], [-0.001, 0.001, -0.001]])
    k, _, volume = core.element(kind, x)
    values = np.linalg.eigvalsh(k)
    assert np.count_nonzero(values > max(values) * 1e-9) == rank
    for q, _ in core.gauss(kind):
        _, b, _ = core.point(kind, x, q)
        np.testing.assert_allclose(
            b @ (x @ h.T).ravel(), [0.001, 0.002, -0.001, 0.004, 0.005, -0.002], atol=1e-14
        )
        for axis in np.eye(3):
            np.testing.assert_allclose(b @ np.tile(axis, len(x)), 0, atol=1e-14)
            np.testing.assert_allclose(
                b @ np.cross(np.tile(axis, (len(x), 1)), x).ravel(), 0, atol=1e-14
            )
    u = (x @ h.T).ravel()
    assert 0.5 * u @ k @ u == pytest.approx(0.0122 * volume, rel=1e-10)


def test_reference_snapshot_hash_and_roundtrip(payload):
    import hashlib

    root = Path(core.__file__).parent
    manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text())
    assert (
        hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest()
        == manifest["files"]["reference.py"]
    )
    response = client.post("/api/v1/continuum3d/validate", json=payload)
    assert response.status_code == 200
    assert response.json() == payload
