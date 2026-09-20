"""Validated host model, assembly and recovery for linear three-dimensional solids.

SI units: m, N, Pa. The reference kernel is unit-consistent; no implicit conversion.
"""

from collections import Counter
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, StrictInt, model_validator

from nonlinear_core.spatial_contracts import (
    Contract,
    EquilibriumChecks,
    Identifier,
    Number,
    SpatialNode,
    Vector,
)
from reused_cores.continuum3d_linear import reference as core

FACES = {
    "tet4": ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)),
    "hex8": ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)),
}


class SolidMaterial(Contract):
    id: Identifier
    E: Annotated[Number, Field(gt=0)]
    nu: Annotated[Number, Field(gt=-1, lt=0.5)]


class SolidElement(Contract):
    id: Identifier
    kind: Literal["tet4", "hex8"]
    nodes: list[Identifier] = Field(min_length=4, max_length=8)
    material_id: Identifier

    @model_validator(mode="after")
    def connectivity(self):
        count = 4 if self.kind == "tet4" else 8
        if len(self.nodes) != count or len(set(self.nodes)) != count:
            raise ValueError(f"{self.kind} needs {count} distinct ordered node IDs.")
        return self


class SolidConstraint(Contract):
    node_id: Identifier
    dof: Literal["ux", "uy", "uz"]
    value: Number = 0.0


class SolidLoad(Contract):
    node_id: Identifier
    force: Vector


class SolidTraction(Contract):
    element_id: Identifier
    face: Annotated[StrictInt, Field(ge=0, le=5)]
    traction: Vector


class PointResult(Contract):
    natural: Vector
    position: Vector
    strain: list[Number] = Field(min_length=6, max_length=6)
    stress: list[Number] = Field(min_length=6, max_length=6)
    von_mises: Number
    principal: Vector
    det_j: Number


class ElementResult(Contract):
    element_id: Identifier
    volume: Number
    points: list[PointResult]


class NodalResult(Contract):
    node_id: Identifier
    value: Vector


class SolidResult(Contract):
    analysis: Literal["linear-static"]
    units: Literal["m-N-Pa"]
    dof_count: int
    free_dof_count: int
    nodal_displacements: list[NodalResult]
    nodal_reactions: list[NodalResult]
    elements: list[ElementResult]
    strain_energy: Number
    validation: EquilibriumChecks
    warnings: list[str]


class SolidModel(Contract):
    schema_version: Literal["continuum3d-1"] = "continuum3d-1"
    name: str = Field(default="Solid model", min_length=1, max_length=120)
    nodes: list[SpatialNode] = Field(min_length=4, max_length=200)
    elements: list[SolidElement] = Field(min_length=1, max_length=1200)
    materials: list[SolidMaterial] = Field(min_length=1, max_length=1200)
    constraints: list[SolidConstraint] = Field(default_factory=list, max_length=600)
    nodal_loads: list[SolidLoad] = Field(default_factory=list, max_length=1200)
    tractions: list[SolidTraction] = Field(default_factory=list, max_length=7200)
    body_force: Vector = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def references(self):
        for label, records in (
            ("node", self.nodes),
            ("element", self.elements),
            ("material", self.materials),
        ):
            if len({item.id for item in records}) != len(records):
                raise ValueError(f"Duplicate {label} IDs.")
        nodes = {n.id for n in self.nodes}
        materials = {m.id for m in self.materials}
        elements = {e.id: e for e in self.elements}
        used = set()
        cells = set()
        for e in self.elements:
            if not set(e.nodes) <= nodes or e.material_id not in materials:
                raise ValueError(f"Element {e.id} references missing nodes or material.")
            key = tuple(sorted(e.nodes))
            if key in cells:
                raise ValueError("Duplicate elements are not allowed.")
            cells.add(key)
            used.update(e.nodes)
        if used != nodes:
            raise ValueError("Remove unused nodes before analysis.")
        prescribed = {}
        for c in self.constraints:
            key = (c.node_id, c.dof)
            if c.node_id not in nodes or (key in prescribed and prescribed[key] != c.value):
                raise ValueError("Unknown constrained node or conflicting prescribed displacement.")
            prescribed[key] = c.value
        if any(load.node_id not in nodes for load in self.nodal_loads):
            raise ValueError("A nodal load references a missing node.")
        faces = Counter(
            tuple(sorted(e.nodes[i] for i in face)) for e in self.elements for face in FACES[e.kind]
        )
        if max(faces.values()) > 2:
            raise ValueError("Non-manifold mesh face belongs to more than two elements.")
        for t in self.tractions:
            e = elements.get(t.element_id)
            if e is None or t.face >= len(FACES[e.kind]):
                raise ValueError("A traction references an unknown element or face.")
            key = tuple(sorted(e.nodes[i] for i in FACES[e.kind][t.face]))
            if faces[key] != 1:
                raise ValueError("Face traction must act on an exposed boundary face.")
        return self


def solve_solid(model: SolidModel) -> dict:
    """Solve the actual constrained system and retain raw integration-point evidence."""
    index = {node.id: i for i, node in enumerate(model.nodes)}
    materials = {m.id: m for m in model.materials}
    elements = {e.id: e for e in model.elements}
    x = np.array([[n.x, n.y, n.z] for n in model.nodes])
    n = 3 * len(x)
    k = np.zeros((n, n))
    f = np.zeros(n)
    volumes = {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for e in model.elements:
            cell = np.array([index[i] for i in e.nodes])
            material = materials[e.material_id]
            try:
                ke, fe, volume = core.element(
                    e.kind, x[cell], material.E, material.nu, model.body_force, order=2
                )
            except ValueError as error:
                raise ValueError(
                    f"Element {e.id}: {error}. Check its ordered connectivity."
                ) from error
            ix = core.dofs(cell)
            k[np.ix_(ix, ix)] += ke
            f[ix] += fe
            volumes[e.id] = volume
        for load in model.nodal_loads:
            i = index[load.node_id] * 3
            f[i : i + 3] += load.force
        for load in model.tractions:
            e = elements[load.element_id]
            cell = np.array([index[e.nodes[i]] for i in FACES[e.kind][load.face]])
            f[core.dofs(cell)] += core.face_load(x[cell], load.traction).ravel()
        prescribed = {
            index[c.node_id] * 3 + ("ux", "uy", "uz").index(c.dof): c.value
            for c in model.constraints
        }
        try:
            u, reactions = core.solve(k, f, prescribed)
        except ValueError as error:
            raise ValueError(
                f"{error}. Check supports on every connected part and remove mechanisms."
            ) from error
        recovery = []
        integrated_energy = 0.0
        for e in model.elements:
            cell = np.array([index[i] for i in e.nodes])
            ue = u[core.dofs(cell)]
            material = materials[e.material_id]
            d = core.elastic(material.E, material.nu)
            points = []
            for q, weight in core.gauss(e.kind, order=2):
                shape, b, jacobian = core.point(e.kind, x[cell], q)
                strain = b @ ue
                stress = d @ strain
                integrated_energy += 0.5 * strain @ stress * jacobian * weight
                points.append(
                    {
                        "natural": q.tolist(),
                        "position": (shape @ x[cell]).tolist(),
                        "strain": strain.tolist(),
                        "stress": stress.tolist(),
                        "von_mises": float(core.mises(stress)),
                        "principal": np.linalg.eigvalsh(core.stress_tensor(stress))[::-1].tolist(),
                        "det_j": jacobian,
                    }
                )
            recovery.append({"element_id": e.id, "volume": volumes[e.id], "points": points})
        free = np.setdiff1d(np.arange(n), list(prescribed))
        support = np.zeros(n)
        support[list(prescribed)] = reactions[list(prescribed)]
        balance = (f + support).reshape(-1, 3)
        force_balance = balance.sum(axis=0)
        # Translation-invariant moment reference avoids cancellation at remote origins.
        centered = x - x.mean(axis=0)
        moment_balance = np.cross(centered, balance).sum(axis=0)
        energy = float(0.5 * u @ k @ u)
        external_work = float(u @ (f + support))
        scale = max(float(np.linalg.norm(f)), float(np.linalg.norm(k @ u)), 1e-30)
        residual = float(np.linalg.norm(reactions[free]) / scale)
        length = max(float(np.linalg.norm(np.ptp(x, axis=0))), 1e-30)
        force_error = float(np.linalg.norm(force_balance) / scale)
        moment_error = float(np.linalg.norm(moment_balance) / (scale * length))
        energy_error = float(
            abs(2 * energy - external_work) / max(abs(2 * energy), abs(external_work), 1e-30)
        )
        recovery_error = float(
            abs(energy - integrated_energy) / max(abs(energy), abs(integrated_energy), 1e-30)
        )
    if not np.isfinite(u).all() or not np.isfinite(reactions).all():
        raise ValueError("Non-finite solution; check material and geometric scales.")
    warnings = [
        "Small-strain linear static solids; no contact, plasticity or dynamics.",
        "Stress is reported at integration points; contour colors use element means.",
        "Jacobian checks sample corners, center and integration points; "
        "they do not certify arbitrary warped geometry everywhere.",
    ]
    if any(m.nu > 0.45 for m in model.materials):
        warnings.append("Near-incompressible material: displacement elements may lock.")
    if any(e.kind == "tet4" for e in model.elements):
        warnings.append("Tet4 is constant-strain; refine and check convergence in bending.")
    return {
        "analysis": "linear-static",
        "units": "m-N-Pa",
        "dof_count": n,
        "free_dof_count": len(free),
        "nodal_displacements": [
            {"node_id": node.id, "value": u[3 * i : 3 * i + 3].tolist()}
            for i, node in enumerate(model.nodes)
        ],
        "nodal_reactions": [
            {"node_id": node.id, "value": support[3 * i : 3 * i + 3].tolist()}
            for i, node in enumerate(model.nodes)
        ],
        "elements": recovery,
        "strain_energy": energy,
        "validation": {
            "passed": max(residual, force_error, moment_error, energy_error, recovery_error) < 1e-7,
            "relative_residual": residual,
            "force_balance": force_balance.tolist(),
            "moment_balance": moment_balance.tolist(),
            "relative_force_error": force_error,
            "relative_moment_error": moment_error,
            "relative_energy_error": energy_error,
            "relative_recovery_energy_error": recovery_error,
        },
        "warnings": warnings,
    }
