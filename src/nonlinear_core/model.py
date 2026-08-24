"""P1 input and analysis-option contracts.

The models in this module describe data only. They do not assemble finite-element
operators, convert units, update material history, or solve equilibrium equations.
Cross-entity reference checks are performed by ``validate_model_input`` in
``nonlinear_core.contracts`` so failures can retain precise JSON paths.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFloat = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
Fraction = Annotated[float, Field(gt=0.0, lt=1.0, allow_inf_nan=False)]
Coordinates = Annotated[tuple[FiniteFloat, ...], Field(min_length=2, max_length=3)]


class ContractModel(BaseModel):
    """Strict, immutable-at-the-field-level base for public contract objects."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )


class ModelFamily(StrEnum):
    CONTINUUM = "continuum"
    FRAME = "frame"
    PLATE = "plate"
    SHELL = "shell"


class Dof(StrEnum):
    UX = "UX"
    UY = "UY"
    UZ = "UZ"
    RX = "RX"
    RY = "RY"
    RZ = "RZ"


MODEL_FAMILY_DOF_ORDER: dict[ModelFamily, tuple[Dof, ...]] = {
    ModelFamily.CONTINUUM: (Dof.UX, Dof.UY),
    ModelFamily.FRAME: (Dof.UX, Dof.UY, Dof.RZ),
    ModelFamily.PLATE: (Dof.UZ, Dof.RX, Dof.RY),
    ModelFamily.SHELL: (Dof.UX, Dof.UY, Dof.UZ, Dof.RX, Dof.RY, Dof.RZ),
}

VON_KARMAN_PLATE_DOF_ORDER: tuple[Dof, ...] = (
    Dof.UX,
    Dof.UY,
    Dof.UZ,
    Dof.RX,
    Dof.RY,
)


def is_von_karman_plate(model: ModelInput) -> bool:
    """Return whether a Plate model requests the P13 moderate-rotation contract."""

    return model.model_family is ModelFamily.PLATE and any(
        "von-karman" in element.formulation.strip().lower().replace("_", "-")
        for element in model.elements
    )


def model_dof_order(model: ModelInput) -> tuple[Dof, ...]:
    """Resolve formulation-specific DOFs without changing linear family defaults."""

    if is_von_karman_plate(model):
        return VON_KARMAN_PLATE_DOF_ORDER
    return MODEL_FAMILY_DOF_ORDER[model.model_family]


class ControlMethod(StrEnum):
    LOAD = "load"
    DISPLACEMENT = "displacement"
    ARC_LENGTH = "arc_length"


class NewtonMethod(StrEnum):
    FULL = "full"
    MODIFIED = "modified"


class LineSearchMethod(StrEnum):
    BACKTRACKING = "backtracking"
    ORTHOGONALITY = "orthogonality"


class ArcLengthRootSelection(StrEnum):
    DIRECTION_CONTINUITY = "direction_continuity"


class LoadKind(StrEnum):
    NODAL = "nodal"
    ELEMENT = "element"
    BODY = "body"
    EDGE = "edge"
    SURFACE = "surface"


class CoordinateSystem(StrEnum):
    GLOBAL = "global"
    LOCAL = "local"


class UnitMetadata(ContractModel):
    """Declared units; values are never converted by the contract layer."""

    length: NonEmptyString
    force: NonEmptyString
    stress: NonEmptyString
    angle: NonEmptyString = "rad"
    time: NonEmptyString | None = None
    system_label: NonEmptyString | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DofRef(ContractModel):
    node_id: Identifier
    dof: Dof


class NodeInput(ContractModel):
    id: Identifier
    coordinates: Coordinates
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class MaterialInput(ContractModel):
    id: Identifier
    model: NonEmptyString
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class ElementInput(ContractModel):
    id: Identifier
    formulation: NonEmptyString
    node_ids: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    material_id: Identifier
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class LoadInput(ContractModel):
    id: Identifier
    kind: LoadKind
    components: Annotated[dict[NonEmptyString, FiniteFloat], Field(min_length=1)]
    node_id: Identifier | None = None
    element_id: Identifier | None = None
    coordinate_system: CoordinateSystem = CoordinateSystem.GLOBAL
    pattern: Identifier = "default"
    scale: FiniteFloat = 1.0
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class ConstraintInput(ContractModel):
    id: Identifier
    node_id: Identifier
    dof: Dof
    value: FiniteFloat = 0.0
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class ToleranceOptions(ContractModel):
    residual: PositiveFloat = 1.0e-8
    displacement: PositiveFloat = 1.0e-8
    energy: PositiveFloat = 1.0e-10
    linear_solver: PositiveFloat = 1.0e-10
    force_floor: PositiveFloat = 1.0e-12
    displacement_floor: PositiveFloat = 1.0e-12
    energy_floor: PositiveFloat = 1.0e-16


class StepControlOptions(ContractModel):
    initial_step: PositiveFloat = 0.1
    min_step: PositiveFloat = 1.0e-4
    max_step: PositiveFloat = 0.25
    max_steps: Annotated[int, Field(ge=1)] = 100
    max_retries: Annotated[int, Field(ge=0)] = 8
    target_iterations: Annotated[int, Field(ge=1)] = 6
    cutback_factor: Fraction = 0.5
    growth_factor: Annotated[float, Field(ge=1.0, allow_inf_nan=False)] = 1.5

    @model_validator(mode="after")
    def check_step_range(self) -> Self:
        if not self.min_step <= self.initial_step <= self.max_step:
            raise ValueError("min_step <= initial_step <= max_step is required")
        return self


class LineSearchOptions(ContractModel):
    enabled: bool = False
    method: LineSearchMethod = LineSearchMethod.BACKTRACKING
    max_iterations: Annotated[int, Field(ge=1)] = 8
    min_alpha: Fraction = 1.0e-3
    reduction_factor: Fraction = 0.5


class DisplacementControlOptions(ContractModel):
    target: DofRef
    increment: FiniteFloat

    @field_validator("increment")
    @classmethod
    def reject_zero_increment(cls, value: float) -> float:
        if value == 0.0:
            raise ValueError("displacement-control increment must be non-zero")
        return value


class ArcLengthOptions(ContractModel):
    radius: PositiveFloat
    min_radius: PositiveFloat
    max_radius: PositiveFloat
    beta: PositiveFloat = 1.0
    root_selection: ArcLengthRootSelection = ArcLengthRootSelection.DIRECTION_CONTINUITY

    @model_validator(mode="after")
    def check_radius_range(self) -> Self:
        if not self.min_radius <= self.radius <= self.max_radius:
            raise ValueError("min_radius <= radius <= max_radius is required")
        return self


class AnalysisOptions(ContractModel):
    control_method: ControlMethod = ControlMethod.LOAD
    newton_method: NewtonMethod = NewtonMethod.FULL
    max_iterations: Annotated[int, Field(ge=1)] = 30
    tolerances: ToleranceOptions = Field(default_factory=ToleranceOptions)
    step_control: StepControlOptions = Field(default_factory=StepControlOptions)
    line_search: LineSearchOptions = Field(default_factory=LineSearchOptions)
    displacement_control: DisplacementControlOptions | None = None
    arc_length: ArcLengthOptions | None = None
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_control_specific_options(self) -> Self:
        if self.control_method is ControlMethod.DISPLACEMENT:
            if self.displacement_control is None:
                raise ValueError(
                    "displacement_control is required when control_method='displacement'"
                )
        elif self.displacement_control is not None:
            raise ValueError(
                "displacement_control is only valid when control_method='displacement'"
            )

        if self.control_method is ControlMethod.ARC_LENGTH:
            if self.arc_length is None:
                raise ValueError("arc_length is required when control_method='arc_length'")
        elif self.arc_length is not None:
            raise ValueError("arc_length is only valid when control_method='arc_length'")
        return self


class ModelInput(ContractModel):
    schema_version: Literal["1.0.0"]
    model_id: Identifier
    name: NonEmptyString
    model_family: ModelFamily
    units: UnitMetadata
    nodes: Annotated[tuple[NodeInput, ...], Field(min_length=1)]
    elements: Annotated[tuple[ElementInput, ...], Field(min_length=1)]
    materials: Annotated[tuple[MaterialInput, ...], Field(min_length=1)]
    loads: tuple[LoadInput, ...] = ()
    constraints: tuple[ConstraintInput, ...] = ()
    analysis: AnalysisOptions
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    def ordered_dof_refs(self) -> tuple[DofRef, ...]:
        """Return the deterministic node-major, family-DOF-minor global order."""

        family_order = model_dof_order(self)
        return tuple(
            DofRef(node_id=node.id, dof=dof) for node in self.nodes for dof in family_order
        )

    def free_dof_refs(self) -> tuple[DofRef, ...]:
        """Return deterministic unconstrained DOFs without modifying input order."""

        constrained = {(constraint.node_id, constraint.dof) for constraint in self.constraints}
        return tuple(
            dof_ref
            for dof_ref in self.ordered_dof_refs()
            if (dof_ref.node_id, dof_ref.dof) not in constrained
        )

    def entity_order(self) -> dict[str, tuple[str, ...]]:
        """Expose the preserved entity order used by assembly adapters."""

        return {
            "nodes": tuple(node.id for node in self.nodes),
            "elements": tuple(element.id for element in self.elements),
            "materials": tuple(material.id for material in self.materials),
            "loads": tuple(load.id for load in self.loads),
            "constraints": tuple(constraint.id for constraint in self.constraints),
        }


__all__ = [
    "AnalysisOptions",
    "ArcLengthOptions",
    "ArcLengthRootSelection",
    "ConstraintInput",
    "ControlMethod",
    "CoordinateSystem",
    "DisplacementControlOptions",
    "Dof",
    "DofRef",
    "ElementInput",
    "LineSearchMethod",
    "LineSearchOptions",
    "LoadInput",
    "LoadKind",
    "MaterialInput",
    "ModelFamily",
    "ModelInput",
    "NewtonMethod",
    "NodeInput",
    "VON_KARMAN_PLATE_DOF_ORDER",
    "is_von_karman_plate",
    "model_dof_order",
    "StepControlOptions",
    "ToleranceOptions",
    "UnitMetadata",
]
