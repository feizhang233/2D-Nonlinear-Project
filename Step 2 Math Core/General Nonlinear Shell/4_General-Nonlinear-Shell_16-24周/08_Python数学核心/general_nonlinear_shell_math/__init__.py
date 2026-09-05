"""Verification-oriented mathematical primitives for nonlinear-shell work."""

from .benchmarks import pure_bending_strip
from .constants import VERSION
from .continuation import solve_scalar_arc_length_step
from .kinematics import (
    green_lagrange_strain,
    infinitesimal_strain_from_deformation_gradient,
    push_forward_second_piola,
    q4_center_shell_kinematics,
)
from .loads import follower_line_force, follower_line_tangent
from .materials import BilinearIsotropic1D, MaterialState1D
from .rotations import rotation_metrics, so3_exp, update_rotation
from .section import condense_plane_stress, integrate_linear_elastic_bending

__all__ = [
    "BilinearIsotropic1D",
    "MaterialState1D",
    "condense_plane_stress",
    "follower_line_force",
    "follower_line_tangent",
    "green_lagrange_strain",
    "infinitesimal_strain_from_deformation_gradient",
    "integrate_linear_elastic_bending",
    "pure_bending_strip",
    "push_forward_second_piola",
    "q4_center_shell_kinematics",
    "rotation_metrics",
    "so3_exp",
    "solve_scalar_arc_length_step",
    "update_rotation",
]

__version__ = VERSION
