"""Linear spatial flat-facet shell contract, host solve and unsmoothed recovery."""

from collections import defaultdict
from dataclasses import asdict
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
from reused_cores import shell3d_linear as core
from reused_cores.shell3d_linear.constants import SI_UNITS

DOFS = ("ux", "uy", "uz", "rx", "ry", "rz")


class ShellMaterial(Contract):
    E: Annotated[Number, Field(gt=0)] = 210e9
    nu: Annotated[Number, Field(gt=-1, lt=0.5)] = 0.3
    thickness: Annotated[Number, Field(gt=0)] = 0.02
    shear_factor: Annotated[Number, Field(gt=0)] = 5 / 6
    alpha_d: Annotated[Number, Field(ge=1e-6, le=1e-2)] = 1e-4


class ShellElement(Contract):
    id: Identifier
    nodes: tuple[Identifier, Identifier, Identifier, Identifier]


class ShellConstraint(Contract):
    node_id: Identifier
    dof: Literal["ux", "uy", "uz", "rx", "ry", "rz"]
    value: Number = 0


class ShellLoad(Contract):
    node_id: Identifier
    force: Vector
    moment: Vector = (0, 0, 0)


class ShellPressure(Contract):
    element_id: Identifier
    value: Number


class ShellModel(Contract):
    schema_version: Literal["shell3d-1"] = "shell3d-1"
    name: str = Field(min_length=1, max_length=120)
    material: ShellMaterial
    nodes: list[SpatialNode] = Field(min_length=4, max_length=100)
    elements: list[ShellElement] = Field(min_length=1, max_length=200)
    constraints: list[ShellConstraint] = Field(default_factory=list, max_length=600)
    nodal_loads: list[ShellLoad] = Field(default_factory=list, max_length=1200)
    pressures: list[ShellPressure] = Field(default_factory=list, max_length=600)

    @model_validator(mode="after")
    def integrity(self):
        if not self.name.strip():
            raise ValueError("Enter a project name.")
        ns = {n.id for n in self.nodes}
        es = {e.id for e in self.elements}
        if len(ns) != len(self.nodes) or len(es) != len(self.elements):
            raise ValueError("Node and element IDs must be unique.")
        used, cells, edges = set(), set(), defaultdict(list)
        xyz = {n.id: np.array([n.x, n.y, n.z]) for n in self.nodes}
        for e in self.elements:
            if len(set(e.nodes)) != 4 or not set(e.nodes) <= ns:
                raise ValueError("Each Q4 needs four distinct existing nodes.")
            key = tuple(sorted(e.nodes))
            if key in cells:
                raise ValueError("Duplicate shell facets are not allowed.")
            cells.add(key)
            used.update(e.nodes)
            points = [xyz[n] for n in e.nodes]
            # Core strict_flat_q4_v1 geometry plus positive corner Jacobians.
            geo = core.build_element_geometry(points)
            for xi, eta in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                core.map_q4_jacobian(
                    [v[:2] for v in geo.local_coordinates], xi, eta, l_char=geo.l_char
                )
            for a, b in zip(e.nodes, (*e.nodes[1:], e.nodes[0]), strict=True):
                edges[tuple(sorted((a, b)))].append((a, b))
        if used != ns:
            raise ValueError("Remove unused nodes.")
        if any(len(v) > 2 or (len(v) == 2 and v[0] == v[1]) for v in edges.values()):
            raise ValueError(
                "Facets must have consistent shared-edge orientation and manifold edges."
            )
        constraints = {}
        for c in self.constraints:
            if c.node_id not in ns:
                raise ValueError("Support references an unknown node.")
            key = (c.node_id, c.dof)
            if key in constraints and constraints[key] != c.value:
                raise ValueError("Conflicting prescribed values.")
            constraints[key] = c.value
        if any(load.node_id not in ns for load in self.nodal_loads):
            raise ValueError("Load references an unknown node.")
        if any(p.element_id not in es for p in self.pressures):
            raise ValueError("Pressure references an unknown element.")
        return self


def native_model(m: ShellModel):
    """Pressure is dead traction along each undeformed facet normal, in Pa."""
    xyz = {n.id: [n.x, n.y, n.z] for n in m.nodes}
    by_id = {e.id: e for e in m.elements}
    loads = [
        dict(
            id=f"L{i}",
            type="nodal_load",
            node_id=f"N{load.node_id}",
            force_global=list(load.force),
            moment_global=list(load.moment),
        )
        for i, load in enumerate(m.nodal_loads)
    ]
    for i, p in enumerate(m.pressures):
        geo = core.build_element_geometry([xyz[n] for n in by_id[p.element_id].nodes])
        normal = geo.basis.lambda_rows[2]
        loads.append(
            dict(
                id=f"P{i}",
                type="surface_traction",
                element_ids=[f"E{p.element_id}"],
                traction_global=[p.value * x for x in normal],
            )
        )
    constraints = {(c.node_id, c.dof): c.value for c in m.constraints}
    return dict(
        document_type="model_input",
        schema_version="1.0.0",
        model_id="Shell3D",
        title=m.name,
        units=SI_UNITS,
        nodes=[dict(id=f"N{n.id}", coordinates=[n.x, n.y, n.z]) for n in m.nodes],
        materials=[
            dict(
                id="M1",
                type="linear_elastic_isotropic",
                young_modulus=m.material.E,
                poisson_ratio=m.material.nu,
            )
        ],
        sections=[
            dict(
                id="S1",
                type="homogeneous_constant_thickness",
                material_id="M1",
                thickness=m.material.thickness,
                shear_correction_factor=m.material.shear_factor,
            )
        ],
        elements=[
            dict(
                id=f"E{e.id}",
                type="Q4_FLAT_SHELL_RM",
                node_ids=[f"N{n}" for n in e.nodes],
                section_id="S1",
            )
            for e in m.elements
        ],
        load_case=dict(id="LC1", loads=loads),
        constraints=[
            dict(id=f"C{i}", node_id=f"N{n}", dof=dof.upper(), value=value)
            for i, ((n, dof), value) in enumerate(constraints.items())
        ],
        analysis_options=dict(
            run_purpose="production",
            kinematics="linear_small_rotation",
            element_formulation="q4_reissner_mindlin_flat_shell",
            shear_formulation="qlll_assumed_strain",
            integration_rule="gauss_2x2",
            drilling=dict(formulation="continuum_consistent", alpha_d=m.material.alpha_d),
            geometry_policy="strict_flat_q4_v1",
            precision="float64",
            solver=dict(
                method="symmetric_direct",
                scaling="characteristic_length",
                relative_backward_error_tolerance=1e-10,
                condition_warning_threshold=1e12,
            ),
        ),
    )


class ShellPoint(Contract):
    natural: tuple[Number, Number]
    membrane_strain: Vector
    curvature: Vector
    shear_strain: tuple[Number, Number]
    membrane: Vector
    moment: Vector
    shear: tuple[Number, Number]
    stress_top: Vector
    stress_bottom: Vector
    det_j: Number


class ShellEnergy(Contract):
    membrane: Number
    bending: Number
    shear: Number
    drilling: Number
    total: Number


class ShellElementResult(Contract):
    element_id: Identifier
    area: Number
    local_basis: tuple[Vector, Vector, Vector]
    points: list[ShellPoint]
    energy: ShellEnergy


class ShellNodeResult(Contract):
    node_id: Identifier
    displacement: Vector
    rotation: Vector
    force: Vector
    moment: Vector


class ShellResult(Contract):
    analysis: Literal["linear-static"] = "linear-static"
    formulation: Literal["Q4-QLLL-flat-shell"] = "Q4-QLLL-flat-shell"
    dof_count: int
    free_dof_count: int
    nodes: list[ShellNodeResult]
    elements: list[ShellElementResult]
    energy: ShellEnergy
    strain_energy: Number
    drilling_fraction: Number
    max_displacement_over_t: Number
    validation: EquilibriumChecks
    warnings: list[str]


def solve_shell(m: ShellModel) -> ShellResult:
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        return _solve(m)


def _solve(m):
    validation = core.validate_model(native_model(m))
    if not validation.solvable or validation.validated_model is None:
        raise ValueError("; ".join(f"{e.code}: {e.message}" for e in validation.errors))
    assembled = core.assemble_system(validation.validated_model)
    k, f = np.array(assembled.stiffness.to_dense()), np.array(assembled.applied_load)
    nd = len(f)
    index = {n.id: i for i, n in enumerate(m.nodes)}
    prescribed = {6 * index[c.node_id] + DOFS.index(c.dof): c.value for c in m.constraints}
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(nd), fixed)
    d = np.zeros(nd)
    d[fixed] = [prescribed[i] for i in fixed]
    if len(free):
        a = k[np.ix_(free, free)]
        if np.any(np.diag(a) <= 0):
            raise ValueError("Unrestrained shell. Restrain rigid modes on every connected part.")
        scale = 1 / np.sqrt(np.diag(a))
        a = scale[:, None] * a * scale[None, :]
        ev = np.linalg.eigvalsh(a)
        if ev[0] <= 1e-13 * ev[-1]:
            raise ValueError("Singular or ill-conditioned shell. Check supports and thickness.")
        rhs = f[free] - k[np.ix_(free, fixed)] @ d[fixed]
        d[free] = scale * np.linalg.solve(a, scale * rhs)
    r = k @ d - f
    support = np.zeros(nd)
    support[fixed] = r[fixed]
    recovered = []
    total = {key: 0.0 for key in ("membrane", "bending", "shear", "drilling", "total")}
    for e, c in zip(m.elements, assembled.elements, strict=True):
        er = core.recover_element_result(c, d, shear_formulation="qlll_assumed_strain")
        energy = asdict(er.energy)
        for key in total:
            total[key] += energy[key]
        recovered.append(
            dict(
                element_id=e.id,
                local_basis=er.local_basis,
                energy=energy,
                area=sum(p.det_jacobian * p.weight for p in er.gauss_points),
                points=[
                    dict(
                        natural=p.natural_coordinates,
                        membrane_strain=p.membrane_strain,
                        curvature=p.curvature,
                        shear_strain=p.assumed_shear_strain,
                        membrane=p.membrane_resultant,
                        moment=p.bending_resultant,
                        shear=p.shear_resultant,
                        stress_top=p.stress_top,
                        stress_bottom=p.stress_bottom,
                        det_j=p.det_jacobian,
                    )
                    for p in er.gauss_points
                ],
            )
        )
    xyz = np.array([[n.x, n.y, n.z] for n in m.nodes])
    xyz -= xyz.mean(axis=0)
    length = assembled.characteristic_length
    b = (f + support).reshape(-1, 6)
    fb = b[:, :3].sum(axis=0)
    mb = (np.cross(xyz, b[:, :3]) + b[:, 3:]).sum(axis=0)
    units = np.tile([1, 1, 1, 1 / length, 1 / length, 1 / length], len(m.nodes))
    magnitude = max(np.linalg.norm(f * units), np.linalg.norm((k @ d) * units), 1e-30)
    residual = np.linalg.norm(r[free] * units[free]) / magnitude
    fe, me = np.linalg.norm(fb) / magnitude, np.linalg.norm(mb) / (magnitude * length)
    energy = float(0.5 * d @ k @ d)
    work = float(d @ (f + support))
    ee = abs(2 * energy - work) / max(abs(2 * energy), abs(work), 1e-30)
    re = abs(energy - total["total"]) / max(abs(energy), abs(total["total"]), 1e-30)
    drilling = total["drilling"] / max(abs(total["total"]), 1e-30)
    u = d.reshape(-1, 6)
    reactions = support.reshape(-1, 6)
    ratio = float(np.max(np.linalg.norm(u[:, :3], axis=1)) / m.material.thickness)
    warnings = [item.message for item in validation.warnings]
    warnings += [
        "Linear planar facets only; no general curved-shell, nonlinear or buckling solve.",
        "N, M, Q and surface stresses use each element local axes; contours are element means.",
        "Drilling is numerical stabilization. Compare alpha_d / 10 and alpha_d × 10.",
    ]
    if drilling > 0.01:
        warnings.append("Drilling energy exceeds 1% of total. Review stabilization sensitivity.")
    if ratio > 0.2 or np.max(np.linalg.norm(u[:, 3:], axis=1)) > 0.1:
        warnings.append(
            "Displacement/thickness or rotation is large. Review small-motion validity."
        )
    return ShellResult.model_validate(
        dict(
            dof_count=nd,
            free_dof_count=len(free),
            nodes=[
                dict(
                    node_id=n.id,
                    displacement=u[i, :3],
                    rotation=u[i, 3:],
                    force=reactions[i, :3],
                    moment=reactions[i, 3:],
                )
                for i, n in enumerate(m.nodes)
            ],
            elements=recovered,
            energy=total,
            strain_energy=energy,
            drilling_fraction=drilling,
            max_displacement_over_t=ratio,
            warnings=warnings,
            validation=dict(
                passed=max(residual, fe, me, ee, re) < 1e-7,
                relative_residual=residual,
                force_balance=fb,
                moment_balance=mb,
                relative_force_error=fe,
                relative_moment_error=me,
                relative_energy_error=ee,
                relative_recovery_energy_error=re,
            ),
        )
    )
