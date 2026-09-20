"""Spatial plate host acceptance: independent analytic fields and real UI mesh."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from nonlinear_api import plate3d
from nonlinear_api.app import create_app
from nonlinear_api.iam_store import IdentityStore
from nonlinear_api.schemas import ApiLimits
from nonlinear_core.plate3d import PlateModel, solve_plate
from reused_cores.plate3d_linear import reference as core

FIXTURE = Path(__file__).parents[1] / "fixtures" / "plate3d" / "cantilever.json"
client = TestClient(create_app(identity_store=IdentityStore(":memory:")))


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


def mesh(n=4):
    return dict(
        nodes=[
            dict(id=j * (n + 1) + i + 1, x=i / n, y=j / n, z=0.0)
            for j in range(n + 1)
            for i in range(n + 1)
        ],
        elements=[
            dict(id=j * n + i + 1, nodes=[k, k + 1, k + n + 2, k + n + 1])
            for j in range(n)
            for i in range(n)
            for k in [j * (n + 1) + i + 1]
        ],
        material=dict(E=210e9, nu=0.3, thickness=0.1),
        constraints=[],
        nodal_loads=[],
    )


def test_frontend_fixture_free_solve_and_spatial_equilibrium(payload):
    before = deepcopy(payload)
    response = client.post("/api/v1/plate3d/solve", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["free_dof_count"] > 0
    assert result["validation"]["passed"]
    assert all(len(e["points"]) == 4 for e in result["elements"])
    assert result["strain_energy"] > 0
    normal = np.cross(payload["plane"]["ex"], payload["plane"]["ey"])
    np.testing.assert_allclose(
        np.sum([r["force"] for r in result["nodes"]], axis=0), 2000 * normal, atol=1e-6
    )
    for r in result["nodes"]:
        np.testing.assert_allclose(r["displacement"], r["local"][0] * normal, atol=1e-15)
        np.testing.assert_allclose(
            r["rotation"],
            -r["local"][1] * np.array(payload["plane"]["ey"])
            + r["local"][2] * np.array(payload["plane"]["ex"]),
            atol=1e-15,
        )
    assert payload == before


def test_rotation_invariance_and_nonzero_prescribed_twisting_patch():
    """w=w0+c*x*y, theta=(c*y,c*x), gamma=0, Mxy=D(1-nu)c.

    Interior nodes remain free. Four Gauss points per element, no applied load.
    Nonzero support work is necessary for the energy check.
    """
    p = mesh(3)
    c, w0 = 0.001, 0.002
    for node in p["nodes"]:
        x, y = node["x"], node["y"]
        if x in (0, 1) or y in (0, 1):
            for dof, value in zip(
                ["w", "theta_x", "theta_y"], [w0 + c * x * y, c * y, c * x], strict=True
            ):
                p["constraints"].append(dict(node_id=node["id"], dof=dof, value=value))
    reference = solve_plate(PlateModel.model_validate(p))
    d = 210e9 * 0.1**3 / (12 * (1 - 0.3**2))
    assert reference.strain_energy == pytest.approx(d * (1 - 0.3) * c * c, rel=1e-10)
    for node, r in zip(p["nodes"], reference.nodes, strict=True):
        x, y = node["x"], node["y"]
        np.testing.assert_allclose(r.local, [w0 + c * x * y, c * y, c * x], atol=1e-13)
    for e in reference.elements:
        for q in e.points:
            np.testing.assert_allclose(q.moment, [0, 0, d * (1 - 0.3) * c], atol=1e-6)
            np.testing.assert_allclose(q.shear, [0, 0], atol=1e-6)
            np.testing.assert_allclose(q.stress_top, -6 * np.array(q.moment) / 0.1**2, atol=1e-6)
    assert reference.validation.passed
    # Rotation around an oblique axis plus translation; rotate the declared plane too.
    axis = np.array([1.0, 2.0, 3.0])
    axis /= np.linalg.norm(axis)
    skew = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    rot = np.eye(3) + np.sin(0.71) * skew + (1 - np.cos(0.71)) * skew @ skew
    origin = np.array([3.0, -2.0, 7.0])
    p["plane"] = dict(origin=origin.tolist(), ex=rot[:, 0].tolist(), ey=rot[:, 1].tolist())
    for node in p["nodes"]:
        x = rot @ [node["x"], node["y"], node["z"]] + origin
        node.update(zip(["x", "y", "z"], x.tolist(), strict=True))
    transformed = solve_plate(PlateModel.model_validate(p))
    assert transformed.strain_energy == pytest.approx(reference.strain_energy, rel=1e-10)
    assert transformed.validation.passed
    for a, b in zip(reference.nodes, transformed.nodes, strict=True):
        np.testing.assert_allclose(b.displacement, rot @ a.displacement, atol=1e-13)
        np.testing.assert_allclose(b.rotation, rot @ a.rotation, atol=1e-13)
        np.testing.assert_allclose(b.force, rot @ a.force, atol=1e-6)
        np.testing.assert_allclose(b.moment, rot @ a.moment, atol=1e-6)


@pytest.mark.parametrize("thickness", [0.1, 0.01, 0.0001])
def test_sine_load_convergence_through_product_assembly(thickness):
    """Hard simply supported unit square, q=q0 sin(pi*x)sin(pi*y).

    Consistent nodal forces integrated independently with 3x3 quadrature.
    W=q0/(4 D pi^4)+q0/(2 S pi^2); 4/8/12 grids, final error <2%.
    """
    errors = []
    for n in (4, 8, 12):
        p = mesh(n)
        q0, t, E, nu = 1e8 * thickness**4, thickness, 210e9, 0.3
        p["material"]["thickness"] = thickness
        points, weights = np.polynomial.legendre.leggauss(3)
        forces = np.zeros(len(p["nodes"]))
        for j in range(n):
            for i in range(n):
                ids = [
                    j * (n + 1) + i,
                    j * (n + 1) + i + 1,
                    (j + 1) * (n + 1) + i + 1,
                    (j + 1) * (n + 1) + i,
                ]
                for xi, wx in zip(points, weights, strict=True):
                    for eta, wy in zip(points, weights, strict=True):
                        shape = (
                            np.array(
                                [
                                    (1 - xi) * (1 - eta),
                                    (1 + xi) * (1 - eta),
                                    (1 + xi) * (1 + eta),
                                    (1 - xi) * (1 + eta),
                                ]
                            )
                            / 4
                        )
                        x, y = (i + (xi + 1) / 2) / n, (j + (eta + 1) / 2) / n
                        forces[ids] += (
                            shape
                            * q0
                            * np.sin(np.pi * x)
                            * np.sin(np.pi * y)
                            * wx
                            * wy
                            / (4 * n * n)
                        )
        for node, force in zip(p["nodes"], forces, strict=True):
            p["nodal_loads"].append(dict(node_id=node["id"], value=[float(force), 0.0, 0.0]))
            dofs = set()
            if node["x"] in (0, 1):
                dofs.update(["w", "theta_y"])
            if node["y"] in (0, 1):
                dofs.update(["w", "theta_x"])
            p["constraints"].extend(dict(node_id=node["id"], dof=dof, value=0.0) for dof in dofs)
        result = solve_plate(PlateModel.model_validate(p))
        D, S = E * t**3 / (12 * (1 - nu**2)), (5 / 6) * E / (2 * (1 + nu)) * t
        exact = q0 / (4 * D * np.pi**4) + q0 / (2 * S * np.pi**2)
        actual = result.nodes[(n // 2) * (n + 1) + n // 2].local[0]
        errors.append(abs(actual / exact - 1))
        assert result.validation.passed
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] < 0.02


@pytest.mark.parametrize(
    "mutation",
    [
        "unrestrained",
        "warped",
        "flipped",
        "duplicate",
        "missing",
        "unused",
        "conflict",
        "thickness",
        "poisson",
        "bool",
        "axis",
        "unknown",
        "overflow",
    ],
)
def test_invalid_inputs_are_actionable(payload, mutation):
    if mutation == "unrestrained":
        payload["constraints"] = []
    elif mutation == "warped":
        payload["nodes"][5]["z"] += 0.1
    elif mutation == "flipped":
        payload["elements"][0]["nodes"].reverse()
    elif mutation == "duplicate":
        payload["elements"].append({**payload["elements"][0], "id": 999})
    elif mutation == "missing":
        payload["elements"][0]["nodes"][0] = 999
    elif mutation == "unused":
        payload["nodes"].append(dict(id=999, x=0.0, y=0.0, z=0.0))
    elif mutation == "conflict":
        payload["constraints"].append({**payload["constraints"][0], "value": 0.01})
    elif mutation == "thickness":
        payload["material"]["thickness"] = 0
    elif mutation == "poisson":
        payload["material"]["nu"] = 0.5
    elif mutation == "bool":
        payload["material"]["E"] = True
    elif mutation == "axis":
        payload["plane"]["ey"] = payload["plane"]["ex"]
    elif mutation == "unknown":
        payload["nonlinear"] = True
    elif mutation == "overflow":
        payload["material"]["thickness"] = 1e200
    response = client.post("/api/v1/plate3d/solve", json=payload)
    assert response.status_code == 422, response.text[:500]
    assert response.json()["error"]["message"]


def test_fully_constrained_pressure_and_nodal_generalized_moments(payload):
    payload["constraints"] = [
        dict(node_id=n["id"], dof=dof, value=0.0)
        for n in payload["nodes"]
        for dof in ["w", "theta_x", "theta_y"]
    ]
    payload["nodal_loads"] = [
        dict(node_id=1, value=[20.0, 30.0, 40.0]),
        dict(node_id=1, value=[10.0, 20.0, 30.0]),
    ]
    r = solve_plate(PlateModel.model_validate(payload))
    assert r.free_dof_count == 0
    assert r.validation.passed
    assert r.strain_energy == 0
    assert r.nodes[0].reaction[1:] == (-50.0, -70.0)
    assert sum(n.reaction[0] for n in r.nodes) == pytest.approx(1970.0)


def test_limits_busy_recovery_roundtrip_and_snapshot(payload, monkeypatch):
    limited = TestClient(
        create_app(limits=ApiLimits(max_dofs=12), identity_store=IdentityStore(":memory:"))
    )
    assert limited.get("/api/v1/plate3d/capabilities").json()["max_nodes"] == 4
    assert limited.post("/api/v1/plate3d/solve", json=payload).status_code == 413
    assert plate3d._solve_slot.acquire(blocking=False)
    try:
        assert client.post("/api/v1/plate3d/solve", json=payload).status_code == 429
    finally:
        plate3d._solve_slot.release()
    original = plate3d.solve_plate
    monkeypatch.setattr(
        plate3d, "solve_plate", lambda _: (_ for _ in ()).throw(ValueError("bad geometry"))
    )
    assert client.post("/api/v1/plate3d/solve", json=payload).status_code == 422
    monkeypatch.setattr(plate3d, "solve_plate", original)
    assert client.post("/api/v1/plate3d/solve", json=payload).status_code == 200
    assert client.post("/api/v1/plate3d/validate", json=payload).json() == payload
    root = Path(core.__file__).parent
    manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text())
    assert (
        hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest()
        == manifest["files"]["reference.py"]
    )
