"""Linear elastic 3D frame core (A00–A03); no web or database dependency."""

from .assembly import (
    assemble_equivalent_nodal_load_vector,
    assemble_global_stiffness,
    assemble_nodal_load_vector,
    calculate_element_dof_map,
    calculate_node_dof_map,
)
from .geometry import ElementGeometry, calculate_geometry
from .loads import calculate_local_equivalent_nodal_load
from .models import DistributedLoad, FrameElement, NodalLoad, Node, SectionPoint, Support
from .postprocessing import (
    ElementEquilibriumValidation,
    ElementFieldResults,
    calculate_normal_stress,
    reshape_nodal_displacements,
)
from .recovery import (
    ElementEndResponse,
    extract_element_displacements,
    recover_element_end_response,
    recover_local_displacements,
    recover_local_end_forces,
)
from .releases import CondensedElement, condense_releases
from .solution import (
    assemble_prescribed_displacement_vector,
    assemble_support_transformation,
    calculate_reaction_vector,
    partition_dofs,
    solve_displacements,
)
from .solver import ElementAnalysisResult, FrameAnalysisResult, GlobalValidation, solve_frame
from .stiffness import calculate_local_stiffness
from .transformation import (
    calculate_global_equivalent_nodal_load,
    calculate_global_stiffness,
    calculate_transformation,
)

__all__ = [
    "Node",
    "FrameElement",
    "Support",
    "NodalLoad",
    "DistributedLoad",
    "SectionPoint",
    "ElementGeometry",
    "calculate_geometry",
    "calculate_local_stiffness",
    "calculate_transformation",
    "calculate_global_stiffness",
    "calculate_global_equivalent_nodal_load",
    "calculate_node_dof_map",
    "calculate_element_dof_map",
    "assemble_global_stiffness",
    "assemble_nodal_load_vector",
    "assemble_equivalent_nodal_load_vector",
    "calculate_local_equivalent_nodal_load",
    "CondensedElement",
    "condense_releases",
    "partition_dofs",
    "assemble_support_transformation",
    "assemble_prescribed_displacement_vector",
    "solve_displacements",
    "calculate_reaction_vector",
    "ElementEndResponse",
    "extract_element_displacements",
    "recover_local_displacements",
    "recover_local_end_forces",
    "recover_element_end_response",
    "ElementFieldResults",
    "ElementEquilibriumValidation",
    "calculate_normal_stress",
    "reshape_nodal_displacements",
    "FrameAnalysisResult",
    "ElementAnalysisResult",
    "GlobalValidation",
    "solve_frame",
]
