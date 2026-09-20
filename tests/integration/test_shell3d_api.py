"""Independent physical gates for the spatial shell host and its actual UI example."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from nonlinear_api import shell3d
from nonlinear_api.app import create_app
from nonlinear_api.iam_store import IdentityStore
from nonlinear_api.schemas import ApiLimits
from nonlinear_core.shell3d import DOFS, ShellModel, native_model, solve_shell
from reused_cores import shell3d_linear as core

ROOT = Path(__file__).parents[1] / "fixtures" / "shell3d"
client = TestClient(create_app(identity_store=IdentityStore(":memory:")))


@pytest.fixture
def payload():
    return json.loads((ROOT / "cantilever.json").read_text())


def grid(n=2, thickness=0.1):
    return dict(
        schema_version="shell3d-1",
        name="Analytical patch",
        material=dict(E=2.1e7, nu=0.3, thickness=thickness, shear_factor=5 / 6, alpha_d=1e-4),
        nodes=[
            dict(id=j * (n + 1) + i + 1, x=i / n, y=j / n, z=0)
            for j in range(n + 1)
            for i in range(n + 1)
        ],
        elements=[
            dict(
                id=j * n + i + 1,
                nodes=[
                    j * (n + 1) + i + 1,
                    j * (n + 1) + i + 2,
                    (j + 1) * (n + 1) + i + 2,
                    (j + 1) * (n + 1) + i + 1,
                ],
            )
            for j in range(n)
            for i in range(n)
        ],
        constraints=[],
        nodal_loads=[],
        pressures=[],
    )


def test_actual_folded_ui_example(payload):
    response = client.post("/api/v1/shell3d/solve", json=payload)
    assert response.status_code == 200, response.text
    r = response.json()
    assert r["validation"]["passed"]
    assert r["dof_count"] == 150
    assert r["strain_energy"] == pytest.approx(0.05638295246675, rel=1e-8)
    assert len(r["elements"]) == 16
    assert all(len(e["points"]) == 4 for e in r["elements"])
    assert r["energy"]["membrane"] > 0 and r["energy"]["bending"] > 0
    assert r["drilling_fraction"] < 0.001
    assert client.post("/api/v1/shell3d/validate", json=payload).json() == payload


@pytest.mark.parametrize("distort", [False, True])
def test_membrane_patch_with_free_interior_and_prescribed_work(distort):
    p = grid()
    E, nu, t = 2.1e7, 0.3, 0.1
    if distort:
        p["nodes"][4]["x"] += 0.13
        p["nodes"][4]["y"] -= 0.09

    def exact(n):
        x, y = n["x"], n["y"]
        return np.array([0.001 * x + 0.002 * y, -0.003 * x + 0.004 * y, 0, 0, 0, -0.0025])

    for n in p["nodes"]:
        if n["id"] != 5:
            p["constraints"] += [
                dict(node_id=n["id"], dof=d, value=float(v))
                for d, v in zip(DOFS, exact(n), strict=True)
            ]
    r = solve_shell(ShellModel.model_validate(p))
    assert r.validation.passed
    for n, row in zip(p["nodes"], r.nodes, strict=True):
        np.testing.assert_allclose([*row.displacement, *row.rotation], exact(n), atol=1e-12)
    D = E / (1 - nu**2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    strain = np.array([0.001, 0.004, -0.001])
    stress = D @ strain
    tensor = np.array([[stress[0], stress[2], 0], [stress[2], stress[1], 0], [0, 0, 0]])
    for e in r.elements:
        basis = np.array(e.local_basis)
        local = basis @ tensor @ basis.T
        expected = np.array([local[0, 0], local[1, 1], local[0, 1]])
        for q in e.points:
            np.testing.assert_allclose(q.membrane, t * expected, rtol=1e-10)
            np.testing.assert_allclose(q.stress_top, expected, rtol=1e-10)
            np.testing.assert_allclose(q.stress_bottom, expected, rtol=1e-10)
    assert r.energy.total == pytest.approx(0.5 * t * strain @ stress, rel=1e-10)
    assert r.energy.drilling < 1e-20


def test_twisting_patch_signs_and_zero_assumed_shear():
    p = grid()
    c = 0.002
    for n in p["nodes"]:
        x, y = n["x"], n["y"]
        if n["id"] != 5:
            p["constraints"] += [
                dict(node_id=n["id"], dof=d, value=v)
                for d, v in zip(DOFS, [0, 0, c * x * y, c * x, -c * y, 0], strict=True)
            ]
    r = solve_shell(ShellModel.model_validate(p))
    assert r.validation.passed
    expected = 2.1e7 / (2 * 1.3) * 0.1**3 / 12 * 2 * c
    for e in r.elements:
        for q in e.points:
            assert q.moment[2] == pytest.approx(expected, rel=1e-10)
            assert q.stress_top[2] == pytest.approx(-6 * expected / 0.1**2, rel=1e-10)
            assert q.stress_bottom[2] == pytest.approx(6 * expected / 0.1**2, rel=1e-10)
            np.testing.assert_allclose(q.shear_strain, 0, atol=1e-14)
    assert r.energy.shear < 1e-20


def test_folded_rotation_covariance_and_drilling_sensitivity(payload):
    base = solve_shell(ShellModel.model_validate(payload))
    angle = 0.61
    q = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    rotated = deepcopy(payload)
    for n in rotated["nodes"]:
        n["x"], n["y"], n["z"] = q @ np.array([n["x"], n["y"], n["z"]]) + [3, -2, 7]
    rr = solve_shell(ShellModel.model_validate(rotated))
    assert rr.validation.passed
    assert rr.strain_energy == pytest.approx(base.strain_energy, rel=1e-8)
    for a, b in zip(base.nodes, rr.nodes, strict=True):
        np.testing.assert_allclose(b.displacement, q @ a.displacement, rtol=1e-7, atol=1e-12)
        np.testing.assert_allclose(b.rotation, q @ a.rotation, rtol=1e-7, atol=1e-12)
        np.testing.assert_allclose(b.force, q @ a.force, rtol=1e-7, atol=1e-7)
    for alpha in (1e-5, 1e-3):
        p = deepcopy(payload)
        p["material"]["alpha_d"] = alpha
        r = solve_shell(ShellModel.model_validate(p))
        assert r.validation.passed
        assert abs(r.strain_energy / base.strain_energy - 1) < 0.002
        np.testing.assert_allclose(
            [n.displacement for n in r.nodes],
            [n.displacement for n in base.nodes],
            rtol=0.003,
            atol=1e-7,
        )


def test_element_rank_symmetry_and_six_rigid_modes():
    p = grid(1)
    v = core.validate_model(native_model(ShellModel.model_validate(p)))
    k = np.array(core.assemble_system(v.validated_model).stiffness.to_dense())
    np.testing.assert_allclose(k, k.T, atol=1e-10)
    eigen = np.linalg.eigvalsh(k)
    assert np.count_nonzero(eigen > eigen[-1] * 1e-10) == 18
    xyz = np.array([[n["x"], n["y"], n["z"]] for n in p["nodes"]])
    for i in range(6):
        d = np.zeros((4, 6))
        if i < 3:
            d[:, i] = 1
        else:
            rot = np.eye(3)[i - 3]
            d[:, :3] = np.cross(rot, xyz)
            d[:, 3:] = rot
        assert np.linalg.norm(k @ d.ravel()) < np.linalg.norm(k) * 1e-12


@pytest.mark.parametrize("thickness", [0.01, 0.001])
def test_thin_square_uniform_load_converges_without_locking(thickness):
    errors = []
    for n in (2, 4, 8):
        p = grid(n, thickness)
        for node in p["nodes"]:
            fixed = {"ux", "uy", "rz"}
            if node["x"] in (0, 1):
                fixed.update(["uz", "rx"])
            if node["y"] in (0, 1):
                fixed.update(["uz", "ry"])
            p["constraints"] += [dict(node_id=node["id"], dof=d, value=0) for d in sorted(fixed)]
        p["pressures"] = [dict(element_id=e["id"], value=1) for e in p["elements"]]
        r = solve_shell(ShellModel.model_validate(p))
        assert r.validation.passed
        w = r.nodes[(n // 2) * (n + 1) + n // 2].displacement[2]
        D = p["material"]["E"] * thickness**3 / (12 * (1 - 0.3**2))
        errors.append(abs(w / (0.00406235 / D) - 1))
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] < 0.035


@pytest.mark.parametrize(
    "mutation",
    [
        "unrestrained",
        "warp",
        "flip",
        "duplicate",
        "missing",
        "unused",
        "conflict",
        "thickness",
        "alpha",
        "bool",
        "overflow",
        "unknown",
    ],
)
def test_bad_models_rejected(payload, mutation):
    if mutation == "unrestrained":
        payload["constraints"] = []
    elif mutation == "warp":
        payload["nodes"][6]["z"] += 0.1
    elif mutation == "flip":
        payload["elements"][0]["nodes"].reverse()
    elif mutation == "duplicate":
        payload["elements"].append({**payload["elements"][0], "id": 999})
    elif mutation == "missing":
        payload["elements"][0]["nodes"][0] = 999
    elif mutation == "unused":
        payload["nodes"].append(dict(id=999, x=9, y=9, z=9))
    elif mutation == "conflict":
        payload["constraints"].append({**payload["constraints"][0], "value": 1})
    elif mutation == "thickness":
        payload["material"]["thickness"] = 0
    elif mutation == "alpha":
        payload["material"]["alpha_d"] = 0
    elif mutation == "bool":
        payload["material"]["E"] = True
    elif mutation == "overflow":
        payload["material"]["thickness"] = 1e200
    elif mutation == "unknown":
        payload["buckling"] = True
    r = client.post("/api/v1/shell3d/solve", json=payload)
    assert r.status_code == 422, r.text[:300]
    assert r.json()["error"]["message"]


def test_fully_restrained_accumulated_loads(payload):
    payload["constraints"] = [
        dict(node_id=n["id"], dof=d, value=0) for n in payload["nodes"] for d in DOFS
    ]
    payload["nodal_loads"] = [dict(node_id=1, force=[10, 20, 30], moment=[40, 50, 60])] * 2
    r = solve_shell(ShellModel.model_validate(payload))
    assert r.free_dof_count == 0 and r.validation.passed
    assert r.strain_energy == 0
    np.testing.assert_allclose(r.nodes[0].moment, [-80, -100, -120])


def test_resource_limits_busy_and_frozen_source(payload):
    limited = TestClient(
        create_app(limits=ApiLimits(max_dofs=24), identity_store=IdentityStore(":memory:"))
    )
    assert limited.get("/api/v1/shell3d/capabilities").json()["max_nodes"] == 4
    assert limited.post("/api/v1/shell3d/solve", json=payload).status_code == 413
    assert shell3d._solve_slot.acquire(False)
    try:
        assert client.post("/api/v1/shell3d/solve", json=payload).status_code == 429
    finally:
        shell3d._solve_slot.release()
    root = Path(core.__file__).parent
    manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text())
    for record in manifest["files"]:
        assert (
            hashlib.sha256((root / record["path"]).read_bytes()).hexdigest()
            == record["vendored_sha256"]
        )
    assert core.constants.resolve_contract_schema_path().is_file()
