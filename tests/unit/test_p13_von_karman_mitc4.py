"""P13 element kinematics, core reuse, energy split, and tangent evidence."""

from __future__ import annotations

import numpy as np

from nonlinear_core import evaluate_von_karman_mitc4


def _coordinates() -> np.ndarray:
    return np.asarray([[0.0, 0.0], [2.0, 0.0], [2.1, 1.0], [0.1, 1.1]])


def _plate_indices() -> np.ndarray:
    return np.asarray(
        [index for node in range(4) for index in (5 * node + 2, 5 * node + 3, 5 * node + 4)]
    )


def test_zero_state_transverse_tangent_matches_mindlin_plate_core_exactly():
    from mindlin_plate import MindlinMaterial, plate_element_matrices

    coordinates = _coordinates()
    material = MindlinMaterial(210.0e9, 0.3, 0.02)
    core = plate_element_matrices(
        coordinates,
        material,
        plate_method="M",
        shear_scheme="mitc4",
    )
    response = evaluate_von_karman_mitc4(
        coordinates,
        np.zeros(20),
        young=material.young,
        poisson=material.poisson,
        thickness=material.thickness,
    )
    indices = _plate_indices()

    np.testing.assert_allclose(
        response.tangent[np.ix_(indices, indices)],
        core.total,
        rtol=3.0e-15,
        atol=2.0e-8,
    )
    np.testing.assert_allclose(
        response.bending_tangent[np.ix_(indices, indices)],
        core.bending,
        rtol=3.0e-15,
        atol=2.0e-8,
    )
    np.testing.assert_allclose(
        response.shear_tangent[np.ix_(indices, indices)],
        core.shear,
        rtol=3.0e-15,
        atol=2.0e-8,
    )


def test_von_karman_membrane_strain_contains_quadratic_transverse_terms():
    coordinates = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    displacement = np.zeros((4, 5), dtype=float)
    displacement[:, 2] = coordinates @ np.asarray([0.2, -0.3])

    response = evaluate_von_karman_mitc4(
        coordinates,
        displacement.ravel(),
        young=10.0e6,
        poisson=0.25,
        thickness=0.1,
    )

    for point in response.gauss_points:
        np.testing.assert_allclose(
            point["membrane_strain"],
            [0.5 * 0.2**2, 0.5 * 0.3**2, 0.2 * -0.3],
            atol=2.0e-16,
        )


def test_v02_directional_derivative_has_second_order_error_valley():
    coordinates = _coordinates()
    displacement = np.asarray(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.01,
            -0.02,
            0.08,
            0.03,
            -0.04,
            0.02,
            0.01,
            0.12,
            0.06,
            -0.03,
            -0.01,
            0.03,
            0.05,
            -0.02,
            0.02,
        ]
    )
    direction = np.linspace(-0.4, 0.5, 20)
    direction /= np.linalg.norm(direction)
    response = evaluate_von_karman_mitc4(
        coordinates,
        displacement,
        young=10.0e6,
        poisson=0.3,
        thickness=0.1,
    )
    target = response.tangent @ direction
    np.testing.assert_allclose(response.tangent, response.tangent.T, rtol=0.0, atol=0.0)
    errors = []
    for step in np.logspace(-2, -8, 7):
        plus = evaluate_von_karman_mitc4(
            coordinates,
            displacement + step * direction,
            young=10.0e6,
            poisson=0.3,
            thickness=0.1,
        )
        minus = evaluate_von_karman_mitc4(
            coordinates,
            displacement - step * direction,
            young=10.0e6,
            poisson=0.3,
            thickness=0.1,
        )
        difference = (plus.internal_force - minus.internal_force) / (2.0 * step)
        errors.append(float(np.linalg.norm(difference - target) / np.linalg.norm(target)))

    best = int(np.argmin(errors))
    assert 0 < best < len(errors) - 1
    assert errors[best] < 1.0e-9
    assert errors[0] > 100.0 * errors[best]
    assert errors[-1] > errors[best]


def test_membrane_bending_and_shear_energies_are_separate_and_sum_to_total():
    coordinates = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    displacement = np.zeros((4, 5), dtype=float)
    displacement[:, 0] = 0.01 * coordinates[:, 0]
    displacement[:, 2] = coordinates[:, 0] * coordinates[:, 1]
    displacement[:, 3] = coordinates[:, 1] + 0.1 * coordinates[:, 0]
    displacement[:, 4] = coordinates[:, 0] - 0.05

    response = evaluate_von_karman_mitc4(
        coordinates,
        displacement.ravel(),
        young=10.0e6,
        poisson=0.3,
        thickness=0.1,
    )

    assert response.membrane_energy > 0.0
    assert response.bending_energy > 0.0
    assert response.shear_energy > 0.0
    assert response.strain_energy == (
        response.membrane_energy + response.bending_energy + response.shear_energy
    )
    assert len(response.gauss_points) == 4


def test_mitc4_pure_bending_shear_energy_remains_roundoff_for_thin_and_thick_plate():
    coordinates = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    curvature = 1.7
    displacement = np.zeros((4, 5), dtype=float)
    displacement[:, 2] = 0.5 * curvature * coordinates[:, 0] ** 2
    displacement[:, 3] = curvature * coordinates[:, 0]

    for thickness in (0.2, 0.002):
        response = evaluate_von_karman_mitc4(
            coordinates,
            displacement.ravel(),
            young=210.0e9,
            poisson=0.3,
            thickness=thickness,
        )
        assert response.bending_energy > 0.0
        assert abs(response.shear_energy) < response.bending_energy * 1.0e-10
        for point in response.gauss_points:
            np.testing.assert_allclose(point["shear_strain"], 0.0, atol=1.0e-14)
