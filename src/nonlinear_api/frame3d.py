"""Bounded linear space-frame endpoints in the Nonlinear Studio host API."""

from threading import BoundedSemaphore

from fastapi import APIRouter, Request, Response

from nonlinear_api.spatial_capabilities import FrameCapabilities
from nonlinear_api.spatial_execution import (
    SPATIAL_ERROR_RESPONSES,
    SpatialExecution,
    spatial_problem,
)
from reused_cores.frame3d_linear.api import (
    ForceComponent,
    SolveRequest,
    SolveResponse,
    force_plot,
    solve,
)

router = APIRouter(
    prefix="/api/v1/3d", tags=["Linear space frame"], responses=SPATIAL_ERROR_RESPONSES
)
# The reference kernel uses dense factorization and condition estimation.
execution = SpatialExecution("FRAME3D", "Frame 3D", 6, 400)
MAX_FIELD_VALUES = 1_000_000
_solve_slot = BoundedSemaphore(1)


def _execute(payload: SolveRequest, request: Request, operation):
    values = len(payload.elements) * payload.number_of_points * (18 + len(payload.section_points))
    if values > MAX_FIELD_VALUES:
        raise spatial_problem(
            "FRAME3D_RECOVERY_LIMIT", "Reduce result stations or section stress points.", 413
        )
    return execution.execute(
        request,
        node_count=len(payload.nodes),
        element_count=len(payload.elements),
        slot=_solve_slot,
        operation=operation,
    )


@router.post("/solve", response_model=SolveResponse)
def solve_space_frame(payload: SolveRequest, request: Request):
    return _execute(payload, request, lambda: solve(payload))


@router.post(
    "/plots/{component}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def plot_space_frame(component: ForceComponent, payload: SolveRequest, request: Request):
    return _execute(payload, request, lambda: force_plot(component, payload))


@router.get("/capabilities", response_model=FrameCapabilities)
def capabilities(request: Request):
    return {
        "analysis": "linear-static",
        "dofs_per_node": ["u", "v", "w", "rx", "ry", "rz"],
        "theories": ["euler_bernoulli", "timoshenko"],
        "max_nodes": execution.max_nodes(request),
        "max_elements": execution.max_elements,
        "max_field_values": MAX_FIELD_VALUES,
        "scope": "Linear elastic, small displacement/rotation, straight prismatic beams. "
        "Timoshenko members support nodal loads only. No geometric nonlinearity, "
        "buckling, dynamics or restrained warping.",
    }
