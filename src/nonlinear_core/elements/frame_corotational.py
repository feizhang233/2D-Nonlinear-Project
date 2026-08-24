"""Small-strain, large-rotation 2D corotational Euler-Bernoulli frame.

The inherited ``frame2d`` signs are ``[u, v, phi]`` per node, local +x from
i to j, local +y counter-clockwise from +x, and positive rotation/moment
counter-clockwise.  The response is derived from one elastic basic energy,
so the returned tangent is the exact derivative of the returned internal
force for the principal chord-rotation branch.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from reused_cores.frame2d_linear import FrameElement, Node, calculate_geometry

FloatArray = NDArray[np.float64]


def _readonly(value: ArrayLike, *, shape: tuple[int, ...]) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"corotational frame value must be finite with shape {shape}")
    result.setflags(write=False)
    return result


class CorotationalFrameCollapseError(ValueError):
    """The current chord is too short to define a corotational frame."""

    def __init__(self, element_id: int, current_length: float, reference_length: float) -> None:
        super().__init__(
            f"FrameElement {element_id} current length {current_length:.17g} "
            f"is too small relative to reference length {reference_length:.17g}"
        )
        self.element_id = element_id
        self.current_length = current_length
        self.reference_length = reference_length


@dataclass(frozen=True, slots=True)
class CorotationalFrameResponse:
    """Element response in global DOFs plus current/reference recovery data."""

    internal_force: FloatArray
    tangent: FloatArray
    material_tangent: FloatArray
    geometric_tangent: FloatArray
    basic_deformation: FloatArray
    basic_force: FloatArray
    local_end_forces: FloatArray
    reference_length: float
    current_length: float
    reference_angle: float
    current_angle: float
    chord_rotation: float
    axial_stretch: float
    strain_energy: float

    def __post_init__(self) -> None:
        for name, shape in (
            ("internal_force", (6,)),
            ("tangent", (6, 6)),
            ("material_tangent", (6, 6)),
            ("geometric_tangent", (6, 6)),
            ("basic_deformation", (3,)),
            ("basic_force", (3,)),
            ("local_end_forces", (6,)),
        ):
            object.__setattr__(self, name, _readonly(getattr(self, name), shape=shape))
        scalars = (
            self.reference_length,
            self.current_length,
            self.reference_angle,
            self.current_angle,
            self.chord_rotation,
            self.axial_stretch,
            self.strain_energy,
        )
        if not np.all(np.isfinite(scalars)) or self.reference_length <= 0.0:
            raise ValueError("corotational frame scalar response must be finite")


def _translation_hessian(block: np.ndarray) -> FloatArray:
    result = np.zeros((6, 6), dtype=float)
    first = np.asarray([0, 1], dtype=np.intp)
    second = np.asarray([3, 4], dtype=np.intp)
    result[np.ix_(first, first)] = block
    result[np.ix_(first, second)] = -block
    result[np.ix_(second, first)] = -block
    result[np.ix_(second, second)] = block
    return result


def evaluate_corotational_frame(
    element: FrameElement,
    node_i: Node,
    node_j: Node,
    global_displacement: ArrayLike,
) -> CorotationalFrameResponse:
    """Return objective internal force and consistent tangent for one element."""

    displacement = _readonly(global_displacement, shape=(6,))
    reference = calculate_geometry(element, node_i, node_j)
    reference_angle = float(np.arctan2(reference.s, reference.c))
    current_i = np.asarray([node_i.x + displacement[0], node_i.y + displacement[1]])
    current_j = np.asarray([node_j.x + displacement[3], node_j.y + displacement[4]])
    chord = current_j - current_i
    current_length = float(np.linalg.norm(chord))
    collapse_tolerance = max(np.finfo(float).tiny, 1.0e-12 * reference.L)
    if not np.isfinite(current_length) or current_length <= collapse_tolerance:
        raise CorotationalFrameCollapseError(element.id, current_length, reference.L)

    c = float(chord[0] / current_length)
    s = float(chord[1] / current_length)
    current_angle = float(np.arctan2(s, c))
    angle_difference = current_angle - reference_angle
    chord_rotation = float(np.arctan2(np.sin(angle_difference), np.cos(angle_difference)))
    extension = current_length - reference.L
    basic_deformation = np.asarray(
        [
            extension,
            displacement[2] - chord_rotation,
            displacement[5] - chord_rotation,
        ],
        dtype=float,
    )

    constitutive = np.array(
        [
            [element.E * element.A / reference.L, 0.0, 0.0],
            [
                0.0,
                4.0 * element.E * element.I / reference.L,
                2.0 * element.E * element.I / reference.L,
            ],
            [
                0.0,
                2.0 * element.E * element.I / reference.L,
                4.0 * element.E * element.I / reference.L,
            ],
        ],
        dtype=float,
    )
    basic_force = constitutive @ basic_deformation
    axial_force, moment_i, moment_j = (float(value) for value in basic_force)

    tangent_operator = np.array(
        [
            [-c, -s, 0.0, c, s, 0.0],
            [
                -s / current_length,
                c / current_length,
                1.0,
                s / current_length,
                -c / current_length,
                0.0,
            ],
            [
                -s / current_length,
                c / current_length,
                0.0,
                s / current_length,
                -c / current_length,
                1.0,
            ],
        ],
        dtype=float,
    )
    internal_force = tangent_operator.T @ basic_force
    material_tangent = tangent_operator.T @ constitutive @ tangent_operator

    normal = np.asarray([c, s])
    transverse = np.asarray([-s, c])
    length_hessian = _translation_hessian(np.outer(transverse, transverse) / current_length)
    angle_hessian_block = (
        np.array(
            [
                [2.0 * c * s, s * s - c * c],
                [s * s - c * c, -2.0 * c * s],
            ],
            dtype=float,
        )
        / current_length**2
    )
    angle_hessian = _translation_hessian(angle_hessian_block)
    geometric_tangent = axial_force * length_hessian - (moment_i + moment_j) * angle_hessian
    tangent = material_tangent + geometric_tangent

    shear_force = (moment_i + moment_j) / current_length
    local_end_forces = np.asarray(
        [-axial_force, shear_force, moment_i, axial_force, -shear_force, moment_j]
    )
    strain_energy = float(0.5 * basic_deformation @ basic_force)
    axial_stretch = current_length / reference.L
    if not np.all(
        np.isfinite(
            (
                *internal_force,
                *tangent.ravel(),
                strain_energy,
                axial_stretch,
                *normal,
            )
        )
    ):
        raise ValueError("corotational frame response overflowed; rescale the model")
    return CorotationalFrameResponse(
        internal_force=internal_force,
        tangent=tangent,
        material_tangent=material_tangent,
        geometric_tangent=geometric_tangent,
        basic_deformation=basic_deformation,
        basic_force=basic_force,
        local_end_forces=local_end_forces,
        reference_length=reference.L,
        current_length=current_length,
        reference_angle=reference_angle,
        current_angle=current_angle,
        chord_rotation=chord_rotation,
        axial_stretch=axial_stretch,
        strain_energy=strain_energy,
    )


__all__ = [
    "CorotationalFrameCollapseError",
    "CorotationalFrameResponse",
    "evaluate_corotational_frame",
]
