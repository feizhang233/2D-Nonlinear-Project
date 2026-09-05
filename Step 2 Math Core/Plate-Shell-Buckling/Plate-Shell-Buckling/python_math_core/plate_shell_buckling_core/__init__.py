"""Plate-shell buckling reference mathematics.

The package deliberately separates ideal linear buckling (LBA), geometrically
nonlinear perfect-geometry paths (GNA), and imperfection preparation (GNIA).
It is not a universal shell finite-element or GMNIA implementation.
"""

from .contracts import AnalysisLevel, analysis_level_for
from .imperfections import (
    AppliedImperfectionResult,
    ImperfectionResult,
    RigidProjectionResult,
    apply_normal_imperfection,
    koiter_two_thirds,
    map_normal_imperfection,
    project_out_rigid_body_motion,
)
from .lba import (
    BiaxialPlateResult,
    CylinderBucklingResult,
    Eigenpair,
    PrebucklingResult,
    ShearPlateResult,
    SphereBucklingResult,
    UniaxialPlateResult,
    biaxial_rectangular_plate,
    cylindrical_shell_classical,
    flexural_rigidity,
    recover_membrane_forces,
    pure_shear_square_plate,
    solve_generalized_buckling,
    spherical_shell_external_pressure,
    uniaxial_rectangular_plate,
)
from .modes import ModeFilterResult, diagnose_mode, mac, normalize_mode, subspace_principal_angles
from .nonlinear import (
    ArcLengthPoint,
    ArcLengthSettings,
    PotentialBifurcationResult,
    TwoBarArch,
    trace_spherical_arc_length,
)

__all__ = [
    "AnalysisLevel",
    "AppliedImperfectionResult",
    "ArcLengthPoint",
    "ArcLengthSettings",
    "BiaxialPlateResult",
    "CylinderBucklingResult",
    "Eigenpair",
    "ImperfectionResult",
    "ModeFilterResult",
    "PotentialBifurcationResult",
    "PrebucklingResult",
    "RigidProjectionResult",
    "ShearPlateResult",
    "SphereBucklingResult",
    "TwoBarArch",
    "UniaxialPlateResult",
    "analysis_level_for",
    "apply_normal_imperfection",
    "biaxial_rectangular_plate",
    "cylindrical_shell_classical",
    "flexural_rigidity",
    "diagnose_mode",
    "koiter_two_thirds",
    "mac",
    "map_normal_imperfection",
    "normalize_mode",
    "pure_shear_square_plate",
    "project_out_rigid_body_motion",
    "recover_membrane_forces",
    "solve_generalized_buckling",
    "spherical_shell_external_pressure",
    "subspace_principal_angles",
    "trace_spherical_arc_length",
    "uniaxial_rectangular_plate",
]

__version__ = "0.1.0"
