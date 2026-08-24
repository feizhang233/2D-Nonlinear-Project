"""P14 element objectivity, core limit, work, tangent, and drilling evidence."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from nonlinear_core import evaluate_corotational_flat_shell


def _coordinates() -> np.ndarray:
    return np.asarray([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 1.0, 0.0], [0.0, 1.0, 0.0]])


def _parameters() -> dict[str, float]:
    return {
        "young": 21.0e6,
        "poisson": 0.3,
        "thickness": 0.05,
        "alpha_d": 1.0e-4,
    }


def _deformed_state() -> np.ndarray:
    displacement = np.zeros(24, dtype=float)
    displacement[8] = 0.03
    displacement[14] = 0.05
    displacement[20] = 0.01
    displacement[9:12] = [0.01, -0.02, 0.005]
    displacement[15:18] = [0.02, 0.01, -0.003]
    return displacement


def test_v00_finite_rigid_rotation_has_roundoff_local_deformation_and_zero_internal_force():
    coordinates = _coordinates()
    axis = np.asarray([0.2, 0.6, 0.3])
    axis /= np.linalg.norm(axis)
    rotation = Rotation.from_rotvec(np.deg2rad(30.0) * axis)
    matrix = rotation.as_matrix()
    displacement = np.zeros((4, 6), dtype=float)
    displacement[:, :3] = coordinates @ matrix.T - coordinates
    displacement[:, 3:] = rotation.as_rotvec()

    response = evaluate_corotational_flat_shell(
        coordinates,
        displacement.ravel(),
        **_parameters(),
    )

    assert response.strain_energy == pytest.approx(0.0, abs=1.0e-20)
    assert np.linalg.norm(response.local_deformation) < 1.0e-14
    np.testing.assert_allclose(response.internal_force, 0.0, atol=0.0)
    np.testing.assert_allclose(response.rigid_rotation_vector, rotation.as_rotvec(), atol=2.0e-15)
    for point in response.gauss_points:
        np.testing.assert_allclose(point["membrane_resultant"], 0.0, atol=2.0e-9)
        np.testing.assert_allclose(point["bending_resultant"], 0.0, atol=2.0e-9)
        np.testing.assert_allclose(point["shear_resultant"], 0.0, atol=2.0e-9)


def test_zero_state_tangent_matches_shell_core_global_operator_exactly():
    from shell_core import (
        build_element_geometry,
        build_global_shell_operator,
        build_isotropic_constitutive,
    )

    coordinates = _coordinates()
    geometry = build_element_geometry(coordinates.tolist())
    constitutive = build_isotropic_constitutive(21.0e6, 0.3, 0.05, 5.0 / 6.0)
    operator = build_global_shell_operator(
        geometry,
        constitutive,
        alpha_d=1.0e-4,
        shear_formulation="qlll_assumed_strain",
        drilling_formulation="continuum_consistent",
    )
    response = evaluate_corotational_flat_shell(
        coordinates,
        np.zeros(24),
        **_parameters(),
    )

    np.testing.assert_allclose(response.tangent, operator.k_global, rtol=0.0, atol=0.0)


def test_small_rotation_internal_force_reduces_to_shell_core_linear_response():
    from shell_core import (
        build_element_geometry,
        build_global_shell_operator,
        build_isotropic_constitutive,
    )

    coordinates = _coordinates()
    displacement = 1.0e-8 * np.sin(np.arange(24, dtype=float))
    geometry = build_element_geometry(coordinates.tolist())
    constitutive = build_isotropic_constitutive(21.0e6, 0.3, 0.05, 5.0 / 6.0)
    operator = build_global_shell_operator(geometry, constitutive, alpha_d=1.0e-4)
    expected = np.asarray(operator.k_global) @ displacement

    response = evaluate_corotational_flat_shell(
        coordinates,
        displacement,
        **_parameters(),
    )

    assert np.linalg.norm(response.internal_force - expected) / np.linalg.norm(expected) < 2.0e-8


def test_v02_directional_derivative_and_virtual_work_have_an_interior_error_valley():
    coordinates = _coordinates()
    displacement = _deformed_state()
    direction = np.sin(np.arange(24, dtype=float))
    direction /= np.linalg.norm(direction)
    response = evaluate_corotational_flat_shell(
        coordinates,
        displacement,
        **_parameters(),
    )
    target = response.tangent @ direction
    errors = []
    work_errors = []
    for step in (1.0e-3, 3.0e-4, 1.0e-4, 3.0e-5, 1.0e-5):
        plus = evaluate_corotational_flat_shell(
            coordinates,
            displacement + step * direction,
            **_parameters(),
        )
        minus = evaluate_corotational_flat_shell(
            coordinates,
            displacement - step * direction,
            **_parameters(),
        )
        force_difference = (plus.internal_force - minus.internal_force) / (2.0 * step)
        errors.append(float(np.linalg.norm(force_difference - target) / np.linalg.norm(target)))
        energy_difference = (plus.strain_energy - minus.strain_energy) / (2.0 * step)
        work_errors.append(abs(energy_difference - float(direction @ response.internal_force)))

    best = int(np.argmin(errors))
    assert 0 < best < len(errors) - 1
    assert errors[best] < 2.0e-9
    assert errors[0] > 5.0 * errors[best]
    assert min(work_errors) < 1.0e-7
    np.testing.assert_allclose(response.tangent, response.tangent.T, rtol=0.0, atol=0.0)


def test_drilling_alpha_is_explicit_and_scales_only_the_drilling_mode():
    coordinates = _coordinates()
    displacement = np.zeros(24, dtype=float)
    displacement[11] = 0.01
    low = evaluate_corotational_flat_shell(
        coordinates,
        displacement,
        **(_parameters() | {"alpha_d": 1.0e-5}),
    )
    high = evaluate_corotational_flat_shell(
        coordinates,
        displacement,
        **(_parameters() | {"alpha_d": 1.0e-3}),
    )

    assert low.alpha_d == 1.0e-5
    assert high.alpha_d == 1.0e-3
    assert high.drilling_energy / low.drilling_energy == pytest.approx(100.0, rel=2.0e-15)
    assert low.membrane_energy == low.bending_energy == low.shear_energy == 0.0
    assert high.membrane_energy == high.bending_energy == high.shear_energy == 0.0
