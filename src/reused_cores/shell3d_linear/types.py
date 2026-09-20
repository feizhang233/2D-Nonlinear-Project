"""Immutable contract objects for ModelInput, ValidatedModel and results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from reused_cores.shell3d_linear.constants import SCHEMA_VERSION
from reused_cores.shell3d_linear.diagnostics import Diagnostic

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Vec6 = tuple[float, float, float, float, float, float]
Mat3 = tuple[Vec3, Vec3, Vec3]
DofName = Literal["UX", "UY", "UZ", "RX", "RY", "RZ"]


def as_vec2(values: Sequence[float]) -> Vec2:
    if len(values) != 2:
        raise ValueError(f"expected 2 components, got {len(values)}")
    return (float(values[0]), float(values[1]))


def as_vec3(values: Sequence[float]) -> Vec3:
    if len(values) != 3:
        raise ValueError(f"expected 3 components, got {len(values)}")
    return (float(values[0]), float(values[1]), float(values[2]))


def as_vec6(values: Sequence[float]) -> Vec6:
    if len(values) != 6:
        raise ValueError(f"expected 6 components, got {len(values)}")
    return tuple(float(value) for value in values)  # type: ignore[return-value]


def as_mat3(values: Sequence[Sequence[float]]) -> Mat3:
    if len(values) != 3:
        raise ValueError(f"expected 3 rows, got {len(values)}")
    return (as_vec3(values[0]), as_vec3(values[1]), as_vec3(values[2]))


@dataclass(frozen=True, slots=True)
class Units:
    system: Literal["SI"]
    length: Literal["m"]
    angle: Literal["rad"]
    force: Literal["N"]
    moment: Literal["N*m"]
    bending_resultant: Literal["N"]
    stress: Literal["Pa"]
    line_load: Literal["N/m"]
    surface_load: Literal["N/m^2"]
    body_force: Literal["N/m^3"]
    energy: Literal["J"]

    def to_dict(self) -> dict[str, str]:
        return {
            "system": self.system,
            "length": self.length,
            "angle": self.angle,
            "force": self.force,
            "moment": self.moment,
            "bending_resultant": self.bending_resultant,
            "stress": self.stress,
            "line_load": self.line_load,
            "surface_load": self.surface_load,
            "body_force": self.body_force,
            "energy": self.energy,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Units:
        return cls(
            system=data["system"],
            length=data["length"],
            angle=data["angle"],
            force=data["force"],
            moment=data["moment"],
            bending_resultant=data["bending_resultant"],
            stress=data["stress"],
            line_load=data["line_load"],
            surface_load=data["surface_load"],
            body_force=data["body_force"],
            energy=data["energy"],
        )


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    coordinates: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "coordinates": list(self.coordinates)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Node:
        return cls(id=data["id"], coordinates=as_vec3(data["coordinates"]))


@dataclass(frozen=True, slots=True)
class Material:
    id: str
    type: Literal["linear_elastic_isotropic"]
    young_modulus: float
    poisson_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "young_modulus": self.young_modulus,
            "poisson_ratio": self.poisson_ratio,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Material:
        return cls(
            id=data["id"],
            type=data["type"],
            young_modulus=float(data["young_modulus"]),
            poisson_ratio=float(data["poisson_ratio"]),
        )


@dataclass(frozen=True, slots=True)
class Section:
    id: str
    type: Literal["homogeneous_constant_thickness"]
    material_id: str
    thickness: float
    shear_correction_factor: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "material_id": self.material_id,
            "thickness": self.thickness,
            "shear_correction_factor": self.shear_correction_factor,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Section:
        return cls(
            id=data["id"],
            type=data["type"],
            material_id=data["material_id"],
            thickness=float(data["thickness"]),
            shear_correction_factor=float(data["shear_correction_factor"]),
        )


@dataclass(frozen=True, slots=True)
class Element:
    id: str
    type: Literal["Q4_FLAT_SHELL_RM"]
    node_ids: tuple[str, str, str, str]
    section_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "node_ids": list(self.node_ids),
            "section_id": self.section_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Element:
        node_ids = tuple(str(item) for item in data["node_ids"])
        if len(node_ids) != 4:
            raise ValueError(f"element {data.get('id')!r} must have 4 node_ids")
        return cls(
            id=data["id"],
            type=data["type"],
            node_ids=(node_ids[0], node_ids[1], node_ids[2], node_ids[3]),
            section_id=data["section_id"],
        )


@dataclass(frozen=True, slots=True)
class NodalLoad:
    id: str
    type: Literal["nodal_load"]
    node_id: str
    force_global: Vec3
    moment_global: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "node_id": self.node_id,
            "force_global": list(self.force_global),
            "moment_global": list(self.moment_global),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NodalLoad:
        return cls(
            id=data["id"],
            type="nodal_load",
            node_id=data["node_id"],
            force_global=as_vec3(data["force_global"]),
            moment_global=as_vec3(data["moment_global"]),
        )


@dataclass(frozen=True, slots=True)
class SurfaceTraction:
    id: str
    type: Literal["surface_traction"]
    element_ids: tuple[str, ...]
    traction_global: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "element_ids": list(self.element_ids),
            "traction_global": list(self.traction_global),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SurfaceTraction:
        return cls(
            id=data["id"],
            type="surface_traction",
            element_ids=tuple(str(item) for item in data["element_ids"]),
            traction_global=as_vec3(data["traction_global"]),
        )


@dataclass(frozen=True, slots=True)
class EdgeTraction:
    id: str
    type: Literal["edge_traction"]
    element_id: str
    local_edge: int
    traction_global: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "element_id": self.element_id,
            "local_edge": self.local_edge,
            "traction_global": list(self.traction_global),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EdgeTraction:
        return cls(
            id=data["id"],
            type="edge_traction",
            element_id=data["element_id"],
            local_edge=int(data["local_edge"]),
            traction_global=as_vec3(data["traction_global"]),
        )


@dataclass(frozen=True, slots=True)
class BodyForce:
    id: str
    type: Literal["body_force"]
    element_ids: tuple[str, ...]
    force_density_global: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "element_ids": list(self.element_ids),
            "force_density_global": list(self.force_density_global),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BodyForce:
        return cls(
            id=data["id"],
            type="body_force",
            element_ids=tuple(str(item) for item in data["element_ids"]),
            force_density_global=as_vec3(data["force_density_global"]),
        )


Load = NodalLoad | SurfaceTraction | EdgeTraction | BodyForce


def load_from_dict(data: Mapping[str, Any]) -> Load:
    load_type = data.get("type")
    if load_type == "nodal_load":
        return NodalLoad.from_dict(data)
    if load_type == "surface_traction":
        return SurfaceTraction.from_dict(data)
    if load_type == "edge_traction":
        return EdgeTraction.from_dict(data)
    if load_type == "body_force":
        return BodyForce.from_dict(data)
    raise ValueError(f"unsupported load type {load_type!r}")


@dataclass(frozen=True, slots=True)
class LoadCase:
    id: str
    loads: tuple[Load, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "loads": [load.to_dict() for load in self.loads]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LoadCase:
        return cls(
            id=data["id"],
            loads=tuple(load_from_dict(item) for item in data["loads"]),
        )


@dataclass(frozen=True, slots=True)
class Constraint:
    id: str
    node_id: str
    dof: DofName
    value: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "dof": self.dof,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Constraint:
        return cls(
            id=data["id"],
            node_id=data["node_id"],
            dof=data["dof"],
            value=float(data["value"]),
        )


@dataclass(frozen=True, slots=True)
class DrillingOn:
    formulation: Literal["continuum_consistent"]
    alpha_d: float

    def to_dict(self) -> dict[str, Any]:
        return {"formulation": self.formulation, "alpha_d": self.alpha_d}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DrillingOn:
        return cls(formulation="continuum_consistent", alpha_d=float(data["alpha_d"]))


@dataclass(frozen=True, slots=True)
class DrillingOff:
    formulation: Literal["none"]

    def to_dict(self) -> dict[str, Any]:
        return {"formulation": self.formulation}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DrillingOff:
        return cls(formulation="none")


Drilling = DrillingOn | DrillingOff


def drilling_from_dict(data: Mapping[str, Any]) -> Drilling:
    formulation = data.get("formulation")
    if formulation == "continuum_consistent":
        return DrillingOn.from_dict(data)
    if formulation == "none":
        return DrillingOff.from_dict(data)
    raise ValueError(f"unsupported drilling formulation {formulation!r}")


@dataclass(frozen=True, slots=True)
class SolverOptions:
    method: Literal["symmetric_direct"]
    scaling: Literal["characteristic_length"]
    relative_backward_error_tolerance: float
    condition_warning_threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "scaling": self.scaling,
            "relative_backward_error_tolerance": self.relative_backward_error_tolerance,
            "condition_warning_threshold": self.condition_warning_threshold,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SolverOptions:
        return cls(
            method=data["method"],
            scaling=data["scaling"],
            relative_backward_error_tolerance=float(data["relative_backward_error_tolerance"]),
            condition_warning_threshold=float(data["condition_warning_threshold"]),
        )


@dataclass(frozen=True, slots=True)
class AnalysisOptions:
    run_purpose: Literal["production", "verification"]
    kinematics: Literal["linear_small_rotation"]
    element_formulation: Literal["q4_reissner_mindlin_flat_shell"]
    shear_formulation: Literal["qlll_assumed_strain", "raw_q4_full"]
    integration_rule: Literal["gauss_2x2"]
    drilling: Drilling
    geometry_policy: Literal["strict_flat_q4_v1"]
    solver: SolverOptions
    precision: Literal["float64"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_purpose": self.run_purpose,
            "kinematics": self.kinematics,
            "element_formulation": self.element_formulation,
            "shear_formulation": self.shear_formulation,
            "integration_rule": self.integration_rule,
            "drilling": self.drilling.to_dict(),
            "geometry_policy": self.geometry_policy,
            "solver": self.solver.to_dict(),
            "precision": self.precision,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AnalysisOptions:
        return cls(
            run_purpose=data["run_purpose"],
            kinematics=data["kinematics"],
            element_formulation=data["element_formulation"],
            shear_formulation=data["shear_formulation"],
            integration_rule=data["integration_rule"],
            drilling=drilling_from_dict(data["drilling"]),
            geometry_policy=data["geometry_policy"],
            solver=SolverOptions.from_dict(data["solver"]),
            precision=data["precision"],
        )


@dataclass(frozen=True, slots=True)
class PostOptions:
    """Recovery options. Derived nodal averaging is the P8 switch."""

    include_derived_nodal_results: bool = False
    moment_reference_point_global: Vec3 | None = None


@dataclass(frozen=True, slots=True)
class ModelInput:
    document_type: Literal["model_input"]
    schema_version: str
    model_id: str
    title: str
    units: Units
    nodes: tuple[Node, ...]
    materials: tuple[Material, ...]
    sections: tuple[Section, ...]
    elements: tuple[Element, ...]
    load_case: LoadCase
    constraints: tuple[Constraint, ...]
    analysis_options: AnalysisOptions

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "title": self.title,
            "units": self.units.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "materials": [material.to_dict() for material in self.materials],
            "sections": [section.to_dict() for section in self.sections],
            "elements": [element.to_dict() for element in self.elements],
            "load_case": self.load_case.to_dict(),
            "constraints": [item.to_dict() for item in self.constraints],
            "analysis_options": self.analysis_options.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelInput:
        return cls(
            document_type="model_input",
            schema_version=str(data["schema_version"]),
            model_id=data["model_id"],
            title=data["title"],
            units=Units.from_dict(data["units"]),
            nodes=tuple(Node.from_dict(item) for item in data["nodes"]),
            materials=tuple(Material.from_dict(item) for item in data["materials"]),
            sections=tuple(Section.from_dict(item) for item in data["sections"]),
            elements=tuple(Element.from_dict(item) for item in data["elements"]),
            load_case=LoadCase.from_dict(data["load_case"]),
            constraints=tuple(Constraint.from_dict(item) for item in data["constraints"]),
            analysis_options=AnalysisOptions.from_dict(data["analysis_options"]),
        )


@dataclass(frozen=True, slots=True)
class NodeRecord:
    id: str
    index: int
    coordinates: Vec3
    dof_indices: Vec6


@dataclass(frozen=True, slots=True)
class MaterialRecord:
    id: str
    index: int
    type: Literal["linear_elastic_isotropic"]
    young_modulus: float
    poisson_ratio: float


@dataclass(frozen=True, slots=True)
class SectionRecord:
    id: str
    index: int
    type: Literal["homogeneous_constant_thickness"]
    material_id: str
    material_index: int
    thickness: float
    shear_correction_factor: float


@dataclass(frozen=True, slots=True)
class ElementGeometryRecord:
    id: str
    index: int
    type: Literal["Q4_FLAT_SHELL_RM"]
    node_ids: tuple[str, str, str, str]
    node_indices: tuple[int, int, int, int]
    section_id: str
    section_index: int
    l_char: float
    local_basis: Mat3
    local_coordinates: tuple[Vec3, Vec3, Vec3, Vec3]
    r_warp: float
    r_edge: float
    det_j: tuple[float, float, float, float]
    r_j: float
    jhat_min: float


@dataclass(frozen=True, slots=True)
class NormalizedNodalLoad:
    id: str
    type: Literal["nodal_load"]
    node_id: str
    node_index: int
    force_global: Vec3
    moment_global: Vec3


@dataclass(frozen=True, slots=True)
class NormalizedSurfaceTraction:
    id: str
    type: Literal["surface_traction"]
    element_ids: tuple[str, ...]
    element_indices: tuple[int, ...]
    traction_global: Vec3


@dataclass(frozen=True, slots=True)
class NormalizedEdgeTraction:
    id: str
    type: Literal["edge_traction"]
    element_id: str
    element_index: int
    local_edge: int
    traction_global: Vec3


@dataclass(frozen=True, slots=True)
class NormalizedBodyForce:
    id: str
    type: Literal["body_force"]
    element_ids: tuple[str, ...]
    element_indices: tuple[int, ...]
    force_density_global: Vec3


NormalizedLoad = (
    NormalizedNodalLoad | NormalizedSurfaceTraction | NormalizedEdgeTraction | NormalizedBodyForce
)


@dataclass(frozen=True, slots=True)
class NormalizedConstraint:
    id: str
    node_id: str
    node_index: int
    dof: DofName
    dof_index: int
    value: float
    unit: Literal["m", "rad"]


@dataclass(frozen=True, slots=True)
class ValidatedModel:
    """Read-only model that may be passed to later solve stages.

    Constructed only when validation produced zero error-level diagnostics.
    """

    model_id: str
    schema_version: str
    model_sha256: str
    title: str
    units: Units
    nodes: tuple[NodeRecord, ...]
    materials: tuple[MaterialRecord, ...]
    sections: tuple[SectionRecord, ...]
    elements: tuple[ElementGeometryRecord, ...]
    load_case_id: str
    loads: tuple[NormalizedLoad, ...]
    constraints: tuple[NormalizedConstraint, ...]
    analysis_options: AnalysisOptions
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    schema_version: str
    model_id: str | None
    input_model: ModelInput | None
    diagnostics: tuple[Diagnostic, ...]
    solvable: bool
    validated_model: ValidatedModel | None

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "error")

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "warning")

    def has_code(self, code: str) -> bool:
        return any(item.code == code for item in self.diagnostics)


@dataclass(frozen=True, slots=True)
class ResultSource:
    model_id: str
    load_case_id: str
    model_sha256: str
    core_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "load_case_id": self.load_case_id,
            "model_sha256": self.model_sha256,
            "core_version": self.core_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResultSource:
        return cls(
            model_id=data["model_id"],
            load_case_id=data["load_case_id"],
            model_sha256=data["model_sha256"],
            core_version=data["core_version"],
        )


@dataclass(frozen=True, slots=True)
class NodalDisplacement:
    node_id: str
    translation_global: Vec3
    rotation_global: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "translation_global": list(self.translation_global),
            "rotation_global": list(self.rotation_global),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NodalDisplacement:
        return cls(
            node_id=data["node_id"],
            translation_global=as_vec3(data["translation_global"]),
            rotation_global=as_vec3(data["rotation_global"]),
        )


@dataclass(frozen=True, slots=True)
class NodalReaction:
    node_id: str
    force_global: Vec3
    moment_global: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "force_global": list(self.force_global),
            "moment_global": list(self.moment_global),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NodalReaction:
        return cls(
            node_id=data["node_id"],
            force_global=as_vec3(data["force_global"]),
            moment_global=as_vec3(data["moment_global"]),
        )


@dataclass(frozen=True, slots=True)
class ResidualReport:
    scaled_relative_backward_error: float
    force_equilibrium_relative_error: float
    moment_equilibrium_relative_error: float
    condition_estimate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scaled_relative_backward_error": self.scaled_relative_backward_error,
            "force_equilibrium_relative_error": self.force_equilibrium_relative_error,
            "moment_equilibrium_relative_error": self.moment_equilibrium_relative_error,
            "condition_estimate": self.condition_estimate,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResidualReport:
        estimate = data["condition_estimate"]
        return cls(
            scaled_relative_backward_error=float(data["scaled_relative_backward_error"]),
            force_equilibrium_relative_error=float(data["force_equilibrium_relative_error"]),
            moment_equilibrium_relative_error=float(data["moment_equilibrium_relative_error"]),
            condition_estimate=None if estimate is None else float(estimate),
        )


@dataclass(frozen=True, slots=True)
class SolveResult:
    solver_status: Literal["succeeded"]
    method: Literal["symmetric_direct"]
    scaling: Literal["characteristic_length"]
    precision: Literal["float64"]
    dof_order_global: tuple[str, str, str, str, str, str]
    displacements: tuple[NodalDisplacement, ...]
    reactions: tuple[NodalReaction, ...]
    residual: ResidualReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "solver_status": self.solver_status,
            "method": self.method,
            "scaling": self.scaling,
            "precision": self.precision,
            "dof_order_global": list(self.dof_order_global),
            "displacements": [item.to_dict() for item in self.displacements],
            "reactions": [item.to_dict() for item in self.reactions],
            "residual": self.residual.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SolveResult:
        order = tuple(data["dof_order_global"])
        if order != ("UX", "UY", "UZ", "RX", "RY", "RZ"):
            raise ValueError("dof_order_global must remain the frozen P0 sequence")
        return cls(
            solver_status="succeeded",
            method=data["method"],
            scaling=data["scaling"],
            precision=data["precision"],
            dof_order_global=order,
            displacements=tuple(
                NodalDisplacement.from_dict(item) for item in data["displacements"]
            ),
            reactions=tuple(NodalReaction.from_dict(item) for item in data["reactions"]),
            residual=ResidualReport.from_dict(data["residual"]),
        )


@dataclass(frozen=True, slots=True)
class GaussPointResult:
    point_id: Literal["G1", "G2", "G3", "G4"]
    natural_coordinates: Vec2
    local_coordinates: Vec2
    weight: float
    det_jacobian: float
    membrane_strain: Vec3
    curvature: Vec3
    assumed_shear_strain: Vec2
    membrane_resultant: Vec3
    bending_resultant: Vec3
    shear_resultant: Vec2
    stress_top: Vec3
    stress_bottom: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "natural_coordinates": list(self.natural_coordinates),
            "local_coordinates": list(self.local_coordinates),
            "weight": self.weight,
            "det_jacobian": self.det_jacobian,
            "membrane_strain": list(self.membrane_strain),
            "curvature": list(self.curvature),
            "assumed_shear_strain": list(self.assumed_shear_strain),
            "membrane_resultant": list(self.membrane_resultant),
            "bending_resultant": list(self.bending_resultant),
            "shear_resultant": list(self.shear_resultant),
            "stress_top": list(self.stress_top),
            "stress_bottom": list(self.stress_bottom),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GaussPointResult:
        return cls(
            point_id=data["point_id"],
            natural_coordinates=as_vec2(data["natural_coordinates"]),
            local_coordinates=as_vec2(data["local_coordinates"]),
            weight=float(data["weight"]),
            det_jacobian=float(data["det_jacobian"]),
            membrane_strain=as_vec3(data["membrane_strain"]),
            curvature=as_vec3(data["curvature"]),
            assumed_shear_strain=as_vec2(data["assumed_shear_strain"]),
            membrane_resultant=as_vec3(data["membrane_resultant"]),
            bending_resultant=as_vec3(data["bending_resultant"]),
            shear_resultant=as_vec2(data["shear_resultant"]),
            stress_top=as_vec3(data["stress_top"]),
            stress_bottom=as_vec3(data["stress_bottom"]),
        )


@dataclass(frozen=True, slots=True)
class ElementEnergy:
    membrane: float
    bending: float
    shear: float
    drilling: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "membrane": self.membrane,
            "bending": self.bending,
            "shear": self.shear,
            "drilling": self.drilling,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ElementEnergy:
        return cls(
            membrane=float(data["membrane"]),
            bending=float(data["bending"]),
            shear=float(data["shear"]),
            drilling=float(data["drilling"]),
            total=float(data["total"]),
        )


@dataclass(frozen=True, slots=True)
class ElementResult:
    element_id: str
    coordinate_system: Literal["element_local"]
    local_basis: Mat3
    local_dofs: tuple[float, ...]
    gauss_points: tuple[GaussPointResult, ...]
    energy: ElementEnergy

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "coordinate_system": self.coordinate_system,
            "local_basis": [list(row) for row in self.local_basis],
            "local_dofs": list(self.local_dofs),
            "gauss_points": [item.to_dict() for item in self.gauss_points],
            "energy": self.energy.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ElementResult:
        dofs = tuple(float(value) for value in data["local_dofs"])
        if len(dofs) != 20:
            raise ValueError("local_dofs must contain 20 entries")
        points = tuple(GaussPointResult.from_dict(item) for item in data["gauss_points"])
        if len(points) != 4:
            raise ValueError("gauss_points must contain 4 entries")
        return cls(
            element_id=data["element_id"],
            coordinate_system="element_local",
            local_basis=as_mat3(data["local_basis"]),
            local_dofs=dofs,
            gauss_points=points,
            energy=ElementEnergy.from_dict(data["energy"]),
        )


@dataclass(frozen=True, slots=True)
class BalanceReport:
    moment_reference_point_global: Vec3
    applied_force_global: Vec3
    applied_moment_global: Vec3
    reaction_force_global: Vec3
    reaction_moment_global: Vec3
    force_relative_error: float
    moment_relative_error: float
    total_strain_energy: float
    external_work_u_dot_f: float
    energy_identity_relative_error: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "moment_reference_point_global": list(self.moment_reference_point_global),
            "applied_force_global": list(self.applied_force_global),
            "applied_moment_global": list(self.applied_moment_global),
            "reaction_force_global": list(self.reaction_force_global),
            "reaction_moment_global": list(self.reaction_moment_global),
            "force_relative_error": self.force_relative_error,
            "moment_relative_error": self.moment_relative_error,
            "total_strain_energy": self.total_strain_energy,
            "external_work_u_dot_f": self.external_work_u_dot_f,
            "energy_identity_relative_error": self.energy_identity_relative_error,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BalanceReport:
        return cls(
            moment_reference_point_global=as_vec3(data["moment_reference_point_global"]),
            applied_force_global=as_vec3(data["applied_force_global"]),
            applied_moment_global=as_vec3(data["applied_moment_global"]),
            reaction_force_global=as_vec3(data["reaction_force_global"]),
            reaction_moment_global=as_vec3(data["reaction_moment_global"]),
            force_relative_error=float(data["force_relative_error"]),
            moment_relative_error=float(data["moment_relative_error"]),
            total_strain_energy=float(data["total_strain_energy"]),
            external_work_u_dot_f=float(data["external_work_u_dot_f"]),
            energy_identity_relative_error=float(data["energy_identity_relative_error"]),
        )


@dataclass(frozen=True, slots=True)
class DerivedNodalResult:
    node_id: str
    is_derived: Literal[True]
    method: Literal["gauss_extrapolation_area_weighted_average"]
    source_element_ids: tuple[str, ...]
    reference_basis: Mat3
    membrane_resultant: Vec3
    bending_resultant: Vec3
    shear_resultant: Vec2
    singularity_warning: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "is_derived": True,
            "method": self.method,
            "source_element_ids": list(self.source_element_ids),
            "reference_basis": [list(row) for row in self.reference_basis],
            "membrane_resultant": list(self.membrane_resultant),
            "bending_resultant": list(self.bending_resultant),
            "shear_resultant": list(self.shear_resultant),
            "singularity_warning": self.singularity_warning,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DerivedNodalResult:
        return cls(
            node_id=data["node_id"],
            is_derived=True,
            method=data["method"],
            source_element_ids=tuple(str(item) for item in data["source_element_ids"]),
            reference_basis=as_mat3(data["reference_basis"]),
            membrane_resultant=as_vec3(data["membrane_resultant"]),
            bending_resultant=as_vec3(data["bending_resultant"]),
            shear_resultant=as_vec2(data["shear_resultant"]),
            singularity_warning=bool(data["singularity_warning"]),
        )


@dataclass(frozen=True, slots=True)
class PostResult:
    raw_element_results_ref: Literal["element_results"]
    derived_nodal_results: tuple[DerivedNodalResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_element_results_ref": self.raw_element_results_ref,
            "derived_nodal_results": [item.to_dict() for item in self.derived_nodal_results],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PostResult:
        return cls(
            raw_element_results_ref="element_results",
            derived_nodal_results=tuple(
                DerivedNodalResult.from_dict(item) for item in data["derived_nodal_results"]
            ),
        )


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    document_type: Literal["analysis_result"]
    schema_version: str
    status: Literal["succeeded", "failed"]
    source: ResultSource
    units: Units
    diagnostics: tuple[Diagnostic, ...]
    solve_result: SolveResult | None = None
    element_results: tuple[ElementResult, ...] | None = None
    balance: BalanceReport | None = None
    post_result: PostResult | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_type": self.document_type,
            "schema_version": self.schema_version,
            "status": self.status,
            "source": self.source.to_dict(),
            "units": self.units.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
        if self.status == "succeeded":
            if (
                self.solve_result is None
                or self.element_results is None
                or self.balance is None
                or self.post_result is None
            ):
                raise ValueError("succeeded AnalysisResult is missing required payloads")
            payload["solve_result"] = self.solve_result.to_dict()
            payload["element_results"] = [item.to_dict() for item in self.element_results]
            payload["balance"] = self.balance.to_dict()
            payload["post_result"] = self.post_result.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AnalysisResult:
        status = data["status"]
        if status == "failed":
            return cls(
                document_type="analysis_result",
                schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
                status="failed",
                source=ResultSource.from_dict(data["source"]),
                units=Units.from_dict(data["units"]),
                diagnostics=tuple(Diagnostic.from_dict(item) for item in data["diagnostics"]),
            )
        return cls(
            document_type="analysis_result",
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            status="succeeded",
            source=ResultSource.from_dict(data["source"]),
            units=Units.from_dict(data["units"]),
            diagnostics=tuple(Diagnostic.from_dict(item) for item in data["diagnostics"]),
            solve_result=SolveResult.from_dict(data["solve_result"]),
            element_results=tuple(
                ElementResult.from_dict(item) for item in data["element_results"]
            ),
            balance=BalanceReport.from_dict(data["balance"]),
            post_result=PostResult.from_dict(data["post_result"]),
        )
