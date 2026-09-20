"""Published spatial capabilities retain each family's explicit physical conventions."""

from typing import Literal

from nonlinear_api.schemas import ApiModel


class SpatialCapabilities(ApiModel):
    analysis: Literal["linear-static"]
    max_nodes: int
    max_elements: int
    scope: str


class FrameCapabilities(SpatialCapabilities):
    dofs_per_node: tuple[Literal["u", "v", "w", "rx", "ry", "rz"], ...]
    theories: tuple[Literal["euler_bernoulli", "timoshenko"], ...]
    max_field_values: int


class SolidCapabilities(SpatialCapabilities):
    elements: tuple[Literal["tet4", "hex8"], ...]
    dofs: tuple[Literal["ux", "uy", "uz"], ...]
    units: Literal["m-N-Pa"]
    hex8_integration: Literal["2x2x2"]


class PlateCapabilities(SpatialCapabilities):
    formulation: Literal["MITC4"]
    units: Literal["m-N-Pa-rad"]
    dofs: tuple[Literal["w", "theta_x", "theta_y"], ...]
    integration: Literal["2x2"]


class ShellCapabilities(SpatialCapabilities):
    formulation: Literal["Q4-QLLL-flat-shell"]
    units: Literal["m-N-Pa-rad"]
    dofs: tuple[Literal["ux", "uy", "uz", "rx", "ry", "rz"], ...]
    integration: Literal["2x2"]
