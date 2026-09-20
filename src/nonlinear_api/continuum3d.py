"""Bounded continuum endpoint, independent of the nonlinear and space-frame contracts."""

from threading import BoundedSemaphore

from fastapi import APIRouter, Request

from nonlinear_api.spatial_capabilities import SolidCapabilities
from nonlinear_api.spatial_execution import SPATIAL_ERROR_RESPONSES, SpatialExecution
from nonlinear_core.continuum3d import SolidModel, SolidResult, solve_solid

router = APIRouter(
    prefix="/api/v1/continuum3d", tags=["Linear 3D continuum"], responses=SPATIAL_ERROR_RESPONSES
)
_solve_slot = BoundedSemaphore(1)
execution = SpatialExecution("CONTINUUM3D", "Continuum 3D", 3, 1200)


@router.get("/capabilities", response_model=SolidCapabilities)
def capabilities(request: Request):
    return {
        "analysis": "linear-static",
        "elements": ["tet4", "hex8"],
        "dofs": ["ux", "uy", "uz"],
        "units": "m-N-Pa",
        "max_nodes": execution.max_nodes(request),
        "max_elements": execution.max_elements,
        "hex8_integration": "2x2x2",
        "scope": "Small-strain isotropic elasticity. No reduced integration, "
        "nonlinearity, contact, buckling or dynamics.",
    }


@router.post("/validate", response_model=SolidModel)
def validate_model(payload: SolidModel):
    return payload


@router.post("/solve", response_model=SolidResult)
def solve(payload: SolidModel, request: Request):
    return execution.execute(
        request,
        node_count=len(payload.nodes),
        element_count=len(payload.elements),
        slot=_solve_slot,
        operation=lambda: SolidResult.model_validate(solve_solid(payload)),
    )
