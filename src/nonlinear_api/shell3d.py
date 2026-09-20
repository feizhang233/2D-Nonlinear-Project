"""Bounded linear spatial shell API, separate from solid and nonlinear contracts."""

from threading import BoundedSemaphore

from fastapi import APIRouter, Request

from nonlinear_api.spatial_capabilities import ShellCapabilities
from nonlinear_api.spatial_execution import SPATIAL_ERROR_RESPONSES, SpatialExecution
from nonlinear_core.shell3d import ShellModel, ShellResult, solve_shell

router = APIRouter(
    prefix="/api/v1/shell3d", tags=["Linear spatial shell"], responses=SPATIAL_ERROR_RESPONSES
)
_solve_slot = BoundedSemaphore(1)
execution = SpatialExecution("SHELL3D", "Shell 3D", 6, 200)


@router.get("/capabilities", response_model=ShellCapabilities)
def capabilities(request: Request):
    return {
        "analysis": "linear-static",
        "formulation": "Q4-QLLL-flat-shell",
        "units": "m-N-Pa-rad",
        "dofs": ["ux", "uy", "uz", "rx", "ry", "rz"],
        "integration": "2x2",
        "max_nodes": execution.max_nodes(request),
        "max_elements": execution.max_elements,
        "scope": (
            "Linear planar Q4 facets, membrane + bending + shear; "
            "no nonlinear or buckling response."
        ),
    }


@router.post("/validate", response_model=ShellModel)
def validate_model(payload: ShellModel):
    return payload


@router.post("/solve", response_model=ShellResult)
def solve(payload: ShellModel, request: Request):
    return execution.execute(
        request,
        node_count=len(payload.nodes),
        element_count=len(payload.elements),
        slot=_solve_slot,
        operation=lambda: solve_shell(payload),
    )
