"""P12 element objectivity, constitutive boundary, tangent, and detF evidence."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import (
    TotalLagrangianQ4Error,
    evaluate_total_lagrangian_q4,
    saint_venant_kirchhoff_plane_strain_matrix,
)


def _coordinates() -> np.ndarray:
    return np.asarray([[0.0, 0.0], [2.0, 0.0], [2.2, 1.0], [0.1, 1.1]])


def test_plane_strain_saint_venant_kirchhoff_matrix_matches_lame_constants():
    matrix = saint_venant_kirchhoff_plane_strain_matrix(210.0e9, 0.3)
    lame_lambda = 210.0e9 * 0.3 / (1.3 * 0.4)
    shear = 210.0e9 / 2.6

    np.testing.assert_allclose(
        matrix,
        [
            [lame_lambda + 2.0 * shear, lame_lambda, 0.0],
            [lame_lambda, lame_lambda + 2.0 * shear, 0.0],
            [0.0, 0.0, shear],
        ],
    )


def test_v00_finite_rigid_rotation_has_unit_detf_and_roundoff_energy():
    coordinates = _coordinates()
    angle = np.deg2rad(30.0)
    rotation = np.asarray(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    displacement = (coordinates @ rotation.T - coordinates).ravel()

    response = evaluate_total_lagrangian_q4(
        coordinates,
        displacement,
        young=210.0e9,
        poisson=0.3,
        thickness=0.2,
        element_id="E1",
    )

    assert response.min_det_f == pytest.approx(1.0, abs=4.0e-16)
    assert response.strain_energy == pytest.approx(0.0, abs=1.0e-21)
    assert np.linalg.norm(response.internal_force) < 3.0e-6
    for point in response.gauss_points:
        np.testing.assert_allclose(point["green_lagrange"], 0.0, atol=4.0e-16)


def test_v02_element_directional_derivative_has_second_order_error_valley():
    coordinates = _coordinates()
    displacement = np.asarray([0.0, 0.0, 0.08, -0.02, 0.12, 0.06, -0.01, 0.04])
    direction = np.asarray([0.2, -0.3, 0.4, 0.1, -0.2, 0.5, 0.3, -0.4])
    direction /= np.linalg.norm(direction)
    response = evaluate_total_lagrangian_q4(
        coordinates,
        displacement,
        young=10.0e6,
        poisson=0.25,
        thickness=0.2,
    )
    target = response.tangent @ direction
    errors = []
    for step in np.logspace(-2, -8, 7):
        plus = evaluate_total_lagrangian_q4(
            coordinates,
            displacement + step * direction,
            young=10.0e6,
            poisson=0.25,
            thickness=0.2,
        )
        minus = evaluate_total_lagrangian_q4(
            coordinates,
            displacement - step * direction,
            young=10.0e6,
            poisson=0.25,
            thickness=0.2,
        )
        finite_difference = (plus.internal_force - minus.internal_force) / (2.0 * step)
        errors.append(float(np.linalg.norm(finite_difference - target) / np.linalg.norm(target)))

    best = int(np.argmin(errors))
    assert 0 < best < len(errors) - 1
    assert errors[best] < 1.0e-8
    assert errors[0] > 100.0 * errors[best]
    assert errors[-1] > errors[best]


def test_tangent_is_material_plus_geometric_and_symmetric():
    response = evaluate_total_lagrangian_q4(
        _coordinates(),
        [0.0, 0.0, 0.04, 0.01, 0.06, 0.03, -0.01, 0.02],
        young=10.0e6,
        poisson=0.3,
        thickness=0.2,
    )

    np.testing.assert_allclose(
        response.tangent,
        response.material_tangent + response.geometric_tangent,
        rtol=2.0e-15,
        atol=2.0e-9,
    )
    np.testing.assert_allclose(response.tangent, response.tangent.T, rtol=2.0e-15, atol=2e-9)


def test_nonpositive_detf_is_a_typed_rejection():
    coordinates = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    displacement = np.asarray([0.0, 0.0, -1.2, 0.0, -1.2, 0.0, 0.0, 0.0])

    with pytest.raises(TotalLagrangianQ4Error, match="detF") as caught:
        evaluate_total_lagrangian_q4(
            coordinates,
            displacement,
            young=1.0e6,
            poisson=0.3,
            thickness=1.0,
            element_id="E-collapse",
        )

    assert caught.value.code == "CONTINUUM_NONPOSITIVE_DETF"
    assert caught.value.element_id == "E-collapse"
    assert caught.value.min_det_f is not None and caught.value.min_det_f <= 0.0


def test_clockwise_reference_mapping_is_rejected_before_analysis():
    clockwise = np.asarray([[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0]])

    with pytest.raises(TotalLagrangianQ4Error) as caught:
        evaluate_total_lagrangian_q4(
            clockwise,
            np.zeros(8),
            young=1.0e6,
            poisson=0.3,
            thickness=1.0,
        )

    assert caught.value.code == "CONTINUUM_REFERENCE_MAPPING_INVALID"
