"""壳体失稳研究数学核心。

本包实现资料包 V00-V10 所需的低维算法与解析基准。它不是壳单元、
GMNIA、设计规范校核或生产级非线性有限元求解器。
"""

from .audit import (
    EVIDENCE_REQUIREMENTS,
    AuditResult,
    EvidenceRecord,
    audit_research_evidence,
)
from .benchmarks import cylinder_axial_buckling, sphere_external_pressure
from .buckling import generalized_symmetric_eigenpairs
from .continuation import branch_switching_seed, spherical_arc_length_step
from .critical import (
    classify_singular_point,
    modal_assurance_criterion,
    stability_indicators,
    subspace_principal_angles,
)
from .differentiation import centered_directional_derivative, scan_tangent_error
from .koiter import (
    koiter_two_thirds_law,
    logarithmic_slopes,
    single_mode_quartic_branches,
    two_mode_quartic_branches,
)

__all__ = [
    "branch_switching_seed",
    "AuditResult",
    "EVIDENCE_REQUIREMENTS",
    "EvidenceRecord",
    "audit_research_evidence",
    "centered_directional_derivative",
    "classify_singular_point",
    "cylinder_axial_buckling",
    "generalized_symmetric_eigenpairs",
    "koiter_two_thirds_law",
    "logarithmic_slopes",
    "modal_assurance_criterion",
    "scan_tangent_error",
    "single_mode_quartic_branches",
    "sphere_external_pressure",
    "spherical_arc_length_step",
    "stability_indicators",
    "subspace_principal_angles",
    "two_mode_quartic_branches",
]
