"""Coplanar spatial MITC4 bending; local generalized DOFs, explicit spatial frame.

SI units and director signs follow docs/3D-Plate_Math-Core-Guide/A00–A05.
No membrane, drilling, artificial stiffness, or nonlinear solver is implied.
"""

from collections import Counter
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, model_validator

from nonlinear_core.spatial_contracts import (
    Contract,
    EquilibriumChecks,
    Identifier,
    Number,
    SpatialNode,
    Vector,
)
from reused_cores.plate3d_linear import reference as core

DOFS = ("w", "theta_x", "theta_y")


class PlatePlane(Contract):
    origin: Vector = (0.0, 0.0, 0.0)
    ex: Vector = (1.0, 0.0, 0.0)
    ey: Vector = (0.0, 1.0, 0.0)

    @model_validator(mode="after")
    def orthonormal(self):
        q = np.array([self.ex, self.ey])
        if not np.allclose(q @ q.T, np.eye(2), rtol=0, atol=1e-10):
            raise ValueError("Plate ex and ey must be orthogonal unit vectors.")
        return self


class PlateMaterial(Contract):
    E: Annotated[Number, Field(gt=0)] = 210e9
    nu: Annotated[Number, Field(gt=-1, lt=0.5)] = 0.3
    thickness: Annotated[Number, Field(gt=0)] = 0.02
    shear_factor: Annotated[Number, Field(gt=0)] = 5 / 6


class PlateElement(Contract):
    id: Identifier
    nodes: tuple[Identifier, Identifier, Identifier, Identifier]


class PlateConstraint(Contract):
    node_id: Identifier
    dof: Literal["w", "theta_x", "theta_y"]
    value: Number = 0.0


class PlateNodalLoad(Contract):
    node_id: Identifier
    # Work-conjugate to [w, theta_x, theta_y], units [N, N m, N m].
    value: Vector


class PlatePressure(Contract):
    element_id: Identifier
    value: Number


class PlateModel(Contract):
    schema_version: Literal["plate3d-1"] = "plate3d-1"
    name: str = Field(default="Spatial plate", min_length=1, max_length=120)
    plane: PlatePlane = Field(default_factory=PlatePlane)
    material: PlateMaterial = Field(default_factory=PlateMaterial)
    nodes: list[SpatialNode] = Field(min_length=4, max_length=200)
    elements: list[PlateElement] = Field(min_length=1, max_length=400)
    constraints: list[PlateConstraint] = Field(default_factory=list, max_length=600)
    nodal_loads: list[PlateNodalLoad] = Field(default_factory=list, max_length=1200)
    pressures: list[PlatePressure] = Field(default_factory=list, max_length=1200)

    @model_validator(mode="after")
    def geometry_and_references(self):
        ids = {n.id for n in self.nodes}
        es = {e.id for e in self.elements}
        if len(ids) != len(self.nodes) or len(es) != len(self.elements):
            raise ValueError("Node and element IDs must be unique.")
        used, cells, edges = set(), set(), Counter()
        for e in self.elements:
            if len(set(e.nodes)) != 4 or not set(e.nodes) <= ids:
                raise ValueError(f"Element {e.id} needs four distinct existing node IDs.")
            key = tuple(sorted(e.nodes))
            if key in cells:
                raise ValueError("Duplicate plate elements are not allowed.")
            cells.add(key)
            used.update(e.nodes)
            edges.update(tuple(sorted((e.nodes[i], e.nodes[(i + 1) % 4]))) for i in range(4))
        if used != ids:
            raise ValueError("Remove unused plate nodes.")
        if max(edges.values()) > 2:
            raise ValueError("Non-manifold plate edge belongs to more than two elements.")
        prescribed = {}
        for c in self.constraints:
            key = (c.node_id, c.dof)
            if c.node_id not in ids or (key in prescribed and prescribed[key] != c.value):
                raise ValueError("Unknown support node or conflicting prescribed value.")
            prescribed[key] = c.value
        if any(load.node_id not in ids for load in self.nodal_loads):
            raise ValueError("Nodal load references a missing node.")
        if any(p.element_id not in es for p in self.pressures):
            raise ValueError("Pressure references a missing element.")
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            try:
                xy, _, _ = local_geometry(self)
                index = {n.id: i for i, n in enumerate(self.nodes)}
                for e in self.elements:
                    core.validate_xy(xy[[index[n] for n in e.nodes]])
            except (FloatingPointError, np.linalg.LinAlgError) as error:
                raise ValueError(
                    "Invalid geometric scale; use finite, well-scaled coordinates."
                ) from error
        return self


def local_geometry(model: PlateModel):
    ex, ey = np.array(model.plane.ex), np.array(model.plane.ey)
    normal = np.cross(ex, ey)
    x = np.array([[n.x, n.y, n.z] for n in model.nodes])
    offset = x - model.plane.origin
    length = float(np.linalg.norm(np.ptp(x, axis=0)))
    if not np.isfinite(length) or length <= 0:
        raise ValueError("Plate geometry has zero or invalid extent.")
    if np.max(np.abs(offset @ normal)) > 1e-10 * length:
        raise ValueError(
            "All plate nodes must lie in the declared plane; warped shells are unsupported."
        )
    return offset @ np.array([ex, ey]).T, normal, x


class PlateNodalResult(Contract):
    node_id: Identifier
    local: Vector
    displacement: Vector
    rotation: Vector
    reaction: Vector
    force: Vector
    moment: Vector


class PlatePointResult(Contract):
    natural: tuple[Number, Number]
    position: Vector
    curvature: Vector
    shear_strain: tuple[Number, Number]
    moment: Vector
    shear: tuple[Number, Number]
    stress_top: Vector
    stress_bottom: Vector
    det_j: Number


class PlateElementResult(Contract):
    element_id: Identifier
    area: Number
    points: list[PlatePointResult]


class PlateResult(Contract):
    analysis: Literal["linear-static"] = "linear-static"
    formulation: Literal["MITC4"] = "MITC4"
    units: Literal["m-N-Pa-rad"] = "m-N-Pa-rad"
    dof_count: int
    free_dof_count: int
    nodes: list[PlateNodalResult]
    elements: list[PlateElementResult]
    strain_energy: Number
    bending_energy: Number
    shear_energy: Number
    max_w_over_t: Number
    validation: EquilibriumChecks
    warnings: list[str]


def solve_plate(model: PlateModel) -> PlateResult:
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        return _solve(model)


def _solve(model):
    xy, normal, xyz = local_geometry(model)
    ex, ey = np.array(model.plane.ex), np.array(model.plane.ey)
    index = {n.id: i for i, n in enumerate(model.nodes)}
    nd = 3 * len(model.nodes)
    k, kb, ks, f = np.zeros((nd, nd)), np.zeros((nd, nd)), np.zeros((nd, nd)), np.zeros(nd)
    m = model.material
    db, ds = core.constitutive(m.E, m.nu, m.thickness, m.shear_factor)
    pressures = Counter()
    for p in model.pressures:
        pressures[p.element_id] += p.value
    cells = []
    for e in model.elements:
        cell = np.array([index[n] for n in e.nodes])
        ix = (3 * cell[:, None] + np.arange(3)).ravel()
        ke, fe, be, se = core.element(
            xy[cell], m.E, m.nu, m.thickness, m.shear_factor, pressure=pressures[e.id]
        )
        k[np.ix_(ix, ix)] += ke
        kb[np.ix_(ix, ix)] += be
        ks[np.ix_(ix, ix)] += se
        f[ix] += fe
        cells.append((e, cell, ix))
    for load in model.nodal_loads:
        i = index[load.node_id] * 3
        f[i : i + 3] += load.value
    prescribed = {3 * index[c.node_id] + DOFS.index(c.dof): c.value for c in model.constraints}
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(nd), fixed)
    d = np.zeros(nd)
    d[fixed] = [prescribed[i] for i in fixed]
    if len(free):
        a = k[np.ix_(free, free)]
        diag = np.diag(a)
        if np.any(diag <= 0):
            raise ValueError(
                "Unrestrained plate. Restrain bending rigid modes on every connected part."
            )
        scale = 1 / np.sqrt(diag)
        a = scale[:, None] * a * scale[None, :]
        eigenvalues = np.linalg.eigvalsh(a)
        if eigenvalues[0] <= 1e-13 * eigenvalues[-1]:
            raise ValueError(
                "Singular or ill-conditioned plate. Check supports, connectivity and thickness."
            )
        rhs = f[free] - k[np.ix_(free, fixed)] @ d[fixed]
        d[free] = scale * np.linalg.solve(a, rhs * scale)
    r = k @ d - f
    support = np.zeros(nd)
    support[fixed] = r[fixed]
    recovery, integrated = [], 0.0
    for e, cell, ix in cells:
        points, area = [], 0.0
        for xi, eta, wt in core.quadrature(2):
            shape, _, det, bb, bs = core.matrices(xy[cell], xi, eta)
            curvature, gamma = bb @ d[ix], bs @ d[ix]
            moment, shear = db @ curvature, ds @ gamma
            stress = -6 * moment / m.thickness**2
            integrated += 0.5 * (curvature @ moment + gamma @ shear) * det * wt
            area += det * wt
            points.append(
                dict(
                    natural=[xi, eta],
                    position=shape @ xyz[cell],
                    curvature=curvature,
                    shear_strain=gamma,
                    moment=moment,
                    shear=shear,
                    stress_top=stress,
                    stress_bottom=-stress,
                    det_j=det,
                )
            )
        recovery.append(dict(element_id=e.id, area=area, points=points))
    # Lift only the three modeled directions, preserving virtual work and moment signs.
    u = d.reshape(-1, 3)
    reactions = support.reshape(-1, 3)
    balance = (f + support).reshape(-1, 3)
    forces = balance[:, :1] * normal
    moments = -balance[:, 1:2] * ey + balance[:, 2:3] * ex
    centered = xyz - xyz.mean(axis=0)
    force_balance = forces.sum(axis=0)
    moment_balance = (np.cross(centered, forces) + moments).sum(axis=0)
    length = np.linalg.norm(np.ptp(xy, axis=0))
    # Scale generalized moments by length before comparing their norms to forces.
    units = np.tile([1.0, 1 / length, 1 / length], len(u))
    force_scale = max(np.linalg.norm(f * units), np.linalg.norm((k @ d) * units), 1e-30)
    residual = np.linalg.norm(r[free] * units[free]) / force_scale
    force_error = np.linalg.norm(force_balance) / force_scale
    moment_error = np.linalg.norm(moment_balance) / (force_scale * length)
    energy = float(0.5 * d @ k @ d)
    work = float(d @ (f + support))
    energy_error = abs(2 * energy - work) / max(abs(2 * energy), abs(work), 1e-30)
    recovery_error = abs(energy - integrated) / max(abs(energy), abs(integrated), 1e-30)
    ratio = float(np.max(np.abs(u[:, 0])) / m.thickness)
    warnings = [
        "Coplanar small-deflection bending only; "
        "no membrane, drilling, shell or nonlinear response.",
        "Moments and surface stresses use local plate axes; contours are element means.",
    ]
    if ratio > 0.2:
        warnings.append(
            "Deflection exceeds 0.2 thickness. Review small-deflection validity; "
            "membrane effects are absent."
        )
    return PlateResult.model_validate(
        dict(
            dof_count=nd,
            free_dof_count=len(free),
            elements=recovery,
            strain_energy=energy,
            bending_energy=float(0.5 * d @ kb @ d),
            shear_energy=float(0.5 * d @ ks @ d),
            max_w_over_t=ratio,
            warnings=warnings,
            nodes=[
                dict(
                    node_id=node.id,
                    local=u[i],
                    displacement=u[i, 0] * normal,
                    rotation=-u[i, 1] * ey + u[i, 2] * ex,
                    reaction=reactions[i],
                    force=reactions[i, 0] * normal,
                    moment=-reactions[i, 1] * ey + reactions[i, 2] * ex,
                )
                for i, node in enumerate(model.nodes)
            ],
            validation=dict(
                passed=max(residual, force_error, moment_error, energy_error, recovery_error)
                < 1e-7,
                relative_residual=residual,
                force_balance=force_balance,
                moment_balance=moment_balance,
                relative_force_error=force_error,
                relative_moment_error=moment_error,
                relative_energy_error=energy_error,
                relative_recovery_energy_error=recovery_error,
            ),
        )
    )
