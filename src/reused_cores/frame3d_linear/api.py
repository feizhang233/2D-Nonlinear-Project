"""3D analysis router plus standalone app, parallel to the existing 2D API."""

import os
from dataclasses import asdict, fields
from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .models import (
    DOF_NAMES,
    FORCE_NAMES,
    DistributedLoad,
    FrameElement,
    NodalLoad,
    Node,
    SectionPoint,
    Support,
)
from .plotting import COMPONENTS, png_data_uri, render_internal_force_plot
from .solver import solve_frame

PositiveInt = Annotated[int, Field(strict=True, gt=0)]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Vector3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Matrix3 = tuple[Vector3, Vector3, Vector3]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class NodeInput(ApiModel):
    id: PositiveInt
    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat


class ElementInput(ApiModel):
    id: PositiveInt
    node_i: PositiveInt
    node_j: PositiveInt
    E: PositiveFloat
    G: PositiveFloat
    A: PositiveFloat
    Iy: PositiveFloat
    Iz: PositiveFloat
    J: PositiveFloat
    reference_vector: Vector3
    theory: Literal["euler_bernoulli", "timoshenko"] = "euler_bernoulli"
    Asy: PositiveFloat | None = None
    Asz: PositiveFloat | None = None
    roll_angle: FiniteFloat = 0.0
    releases: list[Annotated[int, Field(strict=True)]] = Field(default_factory=list)


class SupportInput(ApiModel):
    node_id: PositiveInt
    u: StrictBool = False
    v: StrictBool = False
    w: StrictBool = False
    rx: StrictBool = False
    ry: StrictBool = False
    rz: StrictBool = False
    u_value: FiniteFloat = 0.0
    v_value: FiniteFloat = 0.0
    w_value: FiniteFloat = 0.0
    rx_value: FiniteFloat = 0.0
    ry_value: FiniteFloat = 0.0
    rz_value: FiniteFloat = 0.0
    axes: Matrix3 | None = None


class NodalLoadInput(ApiModel):
    node_id: PositiveInt
    fx: FiniteFloat = 0.0
    fy: FiniteFloat = 0.0
    fz: FiniteFloat = 0.0
    mx: FiniteFloat = 0.0
    my: FiniteFloat = 0.0
    mz: FiniteFloat = 0.0


class DistributedLoadInput(ApiModel):
    element_id: PositiveInt
    qx_i: FiniteFloat = 0.0
    qy_i: FiniteFloat = 0.0
    qz_i: FiniteFloat = 0.0
    mx_i: FiniteFloat = 0.0
    qx_j: FiniteFloat = 0.0
    qy_j: FiniteFloat = 0.0
    qz_j: FiniteFloat = 0.0
    mx_j: FiniteFloat = 0.0
    coordinate_system: Literal["local", "global"] = "local"


class SectionPointInput(ApiModel):
    y: FiniteFloat
    z: FiniteFloat


class SolveRequest(ApiModel):
    nodes: list[NodeInput] = Field(min_length=1)
    elements: list[ElementInput] = Field(min_length=1)
    supports: list[SupportInput] = Field(default_factory=list)
    nodal_loads: list[NodalLoadInput] = Field(default_factory=list)
    distributed_loads: list[DistributedLoadInput] = Field(default_factory=list)
    section_points: list[SectionPointInput] = Field(default_factory=list)
    number_of_points: Annotated[int, Field(strict=True, ge=2, le=2001)] = 101
    deformation_scale: FiniteFloat = 1.0
    include_plots: StrictBool = True
    plot_dpi: Annotated[int, Field(strict=True, ge=72, le=300)] = 140


class NodalDisplacementOutput(ApiModel):
    node_id: int
    u: float
    v: float
    w: float
    rx: float
    ry: float
    rz: float


class NodalReactionOutput(ApiModel):
    node_id: int
    fx: float
    fy: float
    fz: float
    mx: float
    my: float
    mz: float


class ElementFieldsOutput(ApiModel):
    x_local: list[float]
    axial_displacement: list[float]
    transverse_displacement_y: list[float]
    transverse_displacement_z: list[float]
    rotation_x: list[float]
    rotation_y: list[float]
    rotation_z: list[float]
    axial_force: list[float]
    shear_force_y: list[float]
    shear_force_z: list[float]
    torsional_moment: list[float]
    bending_moment_y: list[float]
    bending_moment_z: list[float]
    x_global: list[float]
    y_global: list[float]
    z_global: list[float]
    x_deformed: list[float]
    y_deformed: list[float]
    z_deformed: list[float]
    normal_stress: list[list[float]]


class ElementValidationOutput(ApiModel):
    force_residual: list[float]
    moment_residual: list[float]
    maximum_normalized_residual: float
    endpoint_translation_error: float
    endpoint_rotation_error: float
    release_residual: float
    energy_residual_ratio: float
    energy_absolute_error: float
    energy_roundoff_bound: float
    passed: bool


class ElementResultOutput(ApiModel):
    element_id: int
    length: float
    local_axes: list[list[float]]
    local_displacements: list[float]
    local_end_forces: list[float]
    fields: ElementFieldsOutput
    strain_energy: float
    validation: ElementValidationOutput


class GlobalValidationOutput(ApiModel):
    stiffness_symmetry_ratio: float
    free_dof_residual_ratio: float
    free_force_residual_ratio: float
    free_moment_residual_ratio: float
    force_balance: list[float]
    moment_balance: list[float]
    force_balance_ratio: float
    moment_balance_ratio: float
    strain_energy: float
    external_work: float
    energy_residual_ratio: float
    energy_absolute_error: float
    energy_roundoff_bound: float
    scaled_condition_number: float
    passed: bool


class PlotOutput(ApiModel):
    filename: str
    media_type: str
    data_uri: str


class SolveResponse(ApiModel):
    displacement_dof_order: str
    force_dof_order: str
    section_force_convention: str
    field_recovery: str
    free_dofs: list[int]
    restrained_dofs: list[int]
    inactive_dof_vectors: list[list[float]]
    active_dof_count: int
    nodal_displacements: list[NodalDisplacementOutput]
    nodal_reactions: list[NodalReactionOutput]
    section_points: list[SectionPointInput]
    elements: list[ElementResultOutput]
    validation: GlobalValidationOutput
    plots: dict[str, PlotOutput] | None


router = APIRouter(tags=["3d-analysis"])


def _solve(payload):
    return solve_frame(
        [Node(**v.model_dump()) for v in payload.nodes],
        [FrameElement(**v.model_dump()) for v in payload.elements],
        [Support(**v.model_dump()) for v in payload.supports],
        [NodalLoad(**v.model_dump()) for v in payload.nodal_loads],
        [DistributedLoad(**v.model_dump()) for v in payload.distributed_loads],
        number_of_points=payload.number_of_points,
        deformation_scale=payload.deformation_scale,
        section_points=[SectionPoint(**v.model_dump()) for v in payload.section_points],
    )


@router.post("/solve", response_model=SolveResponse)
def solve(payload: SolveRequest):
    result = _solve(payload)
    plots = None
    if payload.include_plots:
        plots = {
            name: {
                "filename": name + ".png",
                "media_type": "image/png",
                "data_uri": png_data_uri(
                    render_internal_force_plot(result.elements, name, dpi=payload.plot_dpi)
                ),
            }
            for name in COMPONENTS
        }
    return {
        "displacement_dof_order": (
            "global [u,v,w,rx,ry,rz] per node; support partitions use support axes"
        ),
        "force_dof_order": "[Fx,Fy,Fz,Mx,My,Mz] per node",
        "section_force_convention": (
            "A00 positive-x face [N,Vy,Vz,Tx,My,Mz]; s_local=k_local*d_local-f_local"
        ),
        "field_recovery": (
            "equilibrium-integrated prismatic beam fields "
            "including supported load particular solutions"
        ),
        "free_dofs": result.free_dofs.tolist(),
        "restrained_dofs": result.restrained_dofs.tolist(),
        "inactive_dof_vectors": result.inactive_dof_vectors.tolist(),
        "active_dof_count": result.active_dof_count,
        "nodal_displacements": [
            {"node_id": i + 1, **dict(zip(DOF_NAMES, row, strict=False))}
            for i, row in enumerate(result.nodal_displacements)
        ],
        "nodal_reactions": [
            {"node_id": i + 1, **dict(zip(FORCE_NAMES, row, strict=False))}
            for i, row in enumerate(result.reactions.reshape(-1, 6))
        ],
        "section_points": [p.model_dump() for p in payload.section_points],
        "elements": [
            {
                "element_id": e.element_id,
                "length": e.geometry.L,
                "local_axes": e.geometry.Q.tolist(),
                "local_displacements": e.local_displacements.tolist(),
                "local_end_forces": e.local_end_forces.tolist(),
                "fields": {f.name: getattr(e.fields, f.name).tolist() for f in fields(e.fields)},
                "strain_energy": e.strain_energy,
                "validation": asdict(e.validation),
            }
            for e in result.elements
        ],
        "validation": asdict(result.validation),
        "plots": plots,
    }


ForceComponent = Literal[
    "axial_force",
    "shear_force_y",
    "shear_force_z",
    "torsional_moment",
    "bending_moment_y",
    "bending_moment_z",
]


@router.post(
    "/plots/{component}", response_class=Response, responses={200: {"content": {"image/png": {}}}}
)
def force_plot(component: ForceComponent, payload: SolveRequest):
    result = _solve(payload)
    return Response(
        render_internal_force_plot(result.elements, component, dpi=payload.plot_dpi),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{component}.png"'},
    )


app = FastAPI(
    title="frame3d API",
    version="0.1.0",
    description="Linear static EB/Timoshenko space-frame core; A00–A03 scope.",
)
app.include_router(router, prefix="/api/v1")


@app.exception_handler(ValueError)
@app.exception_handler(TypeError)
@app.exception_handler(np.linalg.LinAlgError)
async def invalid_model_handler(request: Request, exception: Exception):
    return JSONResponse(status_code=422, content={"detail": str(exception)})


@app.get("/health")
def health():
    return {"status": "ok"}


def run():
    import uvicorn

    uvicorn.run(
        "frame3d.api:app",
        host=os.environ.get("FRAME3D_HOST", "0.0.0.0"),
        port=int(os.environ.get("FRAME3D_API_PORT", "8001")),
    )
