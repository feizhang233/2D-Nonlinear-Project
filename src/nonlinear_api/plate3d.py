"""Bounded linear spatial plate API, separate from solid and nonlinear contracts."""

from threading import BoundedSemaphore

from fastapi import APIRouter, Request

from nonlinear_api.spatial_capabilities import PlateCapabilities
from nonlinear_api.spatial_execution import SPATIAL_ERROR_RESPONSES, SpatialExecution
from nonlinear_core.plate3d import PlateModel, PlateResult, solve_plate

router = APIRouter(
    prefix="/api/v1/plate3d", tags=["Linear spatial plate"], responses=SPATIAL_ERROR_RESPONSES
)
_solve_slot = BoundedSemaphore(1)
execution = SpatialExecution("PLATE3D", "Plate 3D", 3, 400)


@router.get("/capabilities", response_model=PlateCapabilities)
def capabilities(request: Request):
    return {
        "analysis": "linear-static",
        "formulation": "MITC4",
        "units": "m-N-Pa-rad",
        "dofs": ["w", "theta_x", "theta_y"],
        "integration": "2x2",
        "max_nodes": execution.max_nodes(request),
        "max_elements": execution.max_elements,
        "scope": "Arbitrarily oriented coplanar bending only.",
    }


@router.post("/validate", response_model=PlateModel)
def validate_model(payload: PlateModel):
    return payload


@router.post("/solve", response_model=PlateResult)
def solve(payload: PlateModel, request: Request):
    return execution.execute(
        request,
        node_count=len(payload.nodes),
        element_count=len(payload.elements),
        slot=_solve_slot,
        operation=lambda: solve_plate(payload),
    )
