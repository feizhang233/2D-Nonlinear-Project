"""P9 element-level objectivity, linear limit, and consistent-tangent evidence."""

from __future__ import annotations

from importlib.resources import files

import numpy as np
import pytest

from nonlinear_core import (
    CorotationalFrameCollapseError,
    evaluate_corotational_frame,
)
from reused_cores.frame2d_linear import (
    FrameElement,
    Node,
    calculate_geometry,
    calculate_local_stiffness,
    calculate_transformation,
)


def _element() -> tuple[FrameElement, Node, Node]:
    return (
        FrameElement(1, 1, 2, E=210.0e9, A=3.0e-3, I=8.0e-6),
        Node(1, 0.0, 0.0),
        Node(2, 2.0, 0.3),
    )


def test_reused_linear_core_is_isolated_and_carries_source_provenance():
    provenance = files("reused_cores.frame2d_linear").joinpath("PROVENANCE.md")

    text = provenance.read_text(encoding="utf-8")

    assert "2D-Frame-Project" in text
    assert "b8276a1ced4fd5a2913efb23c981f4ec43e59f6e" in text
    assert "reused_cores/frame2d_linear" in text
    assert "nonlinear corotational mathematics is not copied" in text


def test_v00_finite_rigid_rotation_has_zero_deformation_force_and_energy():
    element = FrameElement(1, 1, 2, E=210.0e9, A=3.0e-3, I=8.0e-6)
    node_i = Node(1, 0.0, 0.0)
    node_j = Node(2, 2.0, 0.0)
    angle = np.deg2rad(30.0)
    displacement = np.array(
        [0.0, 0.0, angle, 2.0 * np.cos(angle) - 2.0, 2.0 * np.sin(angle), angle]
    )

    response = evaluate_corotational_frame(element, node_i, node_j, displacement)

    np.testing.assert_allclose(response.basic_deformation, 0.0, atol=2.0e-16)
    np.testing.assert_allclose(response.internal_force, 0.0, atol=2.0e-7)
    assert response.strain_energy == pytest.approx(0.0, abs=2.0e-16)
    assert response.current_length == pytest.approx(response.reference_length)


def test_zero_state_tangent_is_exactly_the_reused_linear_frame_stiffness():
    element, node_i, node_j = _element()
    geometry = calculate_geometry(element, node_i, node_j)
    transformation = calculate_transformation(geometry)
    expected = transformation.T @ calculate_local_stiffness(element, geometry.L) @ transformation

    response = evaluate_corotational_frame(element, node_i, node_j, np.zeros(6))

    np.testing.assert_allclose(response.internal_force, 0.0, atol=0.0)
    np.testing.assert_allclose(response.tangent, expected, rtol=2.0e-15, atol=2.0e-7)
    np.testing.assert_allclose(response.geometric_tangent, 0.0, atol=0.0)


def test_element_directional_derivative_has_an_interior_error_valley():
    element, node_i, node_j = _element()
    displacement = np.array([0.01, -0.02, 0.03, -0.015, 0.025, -0.02])
    direction = np.array([0.3, -0.7, 0.2, -0.4, 0.5, -0.6])
    direction /= np.linalg.norm(direction)
    exact = evaluate_corotational_frame(element, node_i, node_j, displacement)
    target = exact.tangent @ direction
    step_sizes = np.logspace(-2, -8, 7)
    errors = []
    for step_size in step_sizes:
        plus = evaluate_corotational_frame(
            element, node_i, node_j, displacement + step_size * direction
        )
        minus = evaluate_corotational_frame(
            element, node_i, node_j, displacement - step_size * direction
        )
        difference = (plus.internal_force - minus.internal_force) / (2.0 * step_size)
        errors.append(float(np.linalg.norm(difference - target) / np.linalg.norm(target)))

    best_index = int(np.argmin(errors))
    assert 0 < best_index < len(errors) - 1
    assert errors[best_index] < 1.0e-8
    assert errors[0] > 100.0 * errors[best_index]
    assert errors[-1] > errors[best_index]


def test_collapsed_current_chord_is_a_typed_local_failure():
    element = FrameElement(7, 1, 2, E=1000.0, A=1.0, I=0.1)

    with pytest.raises(CorotationalFrameCollapseError, match="current length") as caught:
        evaluate_corotational_frame(
            element,
            Node(1, 0.0, 0.0),
            Node(2, 2.0, 0.0),
            [0.0, 0.0, 0.0, -2.0, 0.0, 0.0],
        )

    assert caught.value.element_id == 7
    assert caught.value.reference_length == pytest.approx(2.0)
