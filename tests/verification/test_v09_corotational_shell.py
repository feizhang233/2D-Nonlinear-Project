"""P14 Shell V09: assembled tangent, distortion, and thickness sensitivity."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import ModelInput, evaluate_corotational_flat_shell, get_adapter


def _two_element_model() -> ModelInput:
    return ModelInput.model_validate(
        {
            "schema_version": "1.0.0",
            "model_id": "p14-two-element-shell",
            "name": "P14 two-element shell tangent",
            "model_family": "shell",
            "units": {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"},
            "nodes": [
                {"id": "N1", "coordinates": [0.0, 0.0, 0.0]},
                {"id": "N2", "coordinates": [1.0, 0.0, 0.0]},
                {"id": "N3", "coordinates": [2.0, 0.0, 0.0]},
                {"id": "N4", "coordinates": [0.0, 1.0, 0.0]},
                {"id": "N5", "coordinates": [1.0, 1.0, 0.0]},
                {"id": "N6", "coordinates": [2.0, 1.0, 0.0]},
            ],
            "materials": [
                {
                    "id": "M1",
                    "model": "linear-elastic-isotropic",
                    "parameters": {"young": 21.0e6, "poisson": 0.3},
                }
            ],
            "elements": [
                {
                    "id": "E1",
                    "formulation": "Q4-corotational-flat-shell-RM",
                    "node_ids": ["N1", "N2", "N5", "N4"],
                    "material_id": "M1",
                    "properties": {"thickness": 0.05, "alpha_d": 1.0e-4},
                },
                {
                    "id": "E2",
                    "formulation": "Q4-corotational-flat-shell-RM",
                    "node_ids": ["N2", "N3", "N6", "N5"],
                    "material_id": "M1",
                    "properties": {"thickness": 0.05, "alpha_d": 1.0e-4},
                },
            ],
            "loads": [],
            "constraints": [],
            "analysis": {"control_method": "load"},
        }
    )


def test_v02_assembled_two_element_directional_derivative_has_error_valley():
    model = _two_element_model()
    adapter = get_adapter(model)
    displacement = 0.004 * np.sin(0.6 * np.arange(36, dtype=float))
    direction = np.cos(0.4 * np.arange(36, dtype=float))
    direction /= np.linalg.norm(direction)
    response = adapter.evaluate(model, displacement)
    target = response.tangent @ direction
    errors = []
    for step in (1.0e-3, 3.0e-4, 1.0e-4, 3.0e-5, 1.0e-5):
        plus = adapter.evaluate(model, displacement + step * direction)
        minus = adapter.evaluate(model, displacement - step * direction)
        difference = (plus.internal_force - minus.internal_force) / (2.0 * step)
        errors.append(float(np.linalg.norm(difference - target) / np.linalg.norm(target)))

    best = int(np.argmin(errors))
    assert 0 < best < len(errors) - 1
    assert errors[best] < 3.0e-9
    assert errors[0] > 3.0 * errors[best]


def _patch_displacement(coordinates: np.ndarray) -> np.ndarray:
    displacement = np.zeros((4, 6), dtype=float)
    for node, (x, y, _z) in enumerate(coordinates):
        displacement[node, 0] = 1.0e-4 * x
        displacement[node, 1] = -3.0e-5 * y
        displacement[node, 2] = 2.0e-3 * x * y
        theta_x = 2.0e-3 * y
        theta_y = 2.0e-3 * x
        displacement[node, 3] = theta_y
        displacement[node, 4] = -theta_x
    return displacement.ravel()


@pytest.mark.parametrize(
    "coordinates",
    [
        np.asarray([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 1.0, 0.0], [0.0, 1.0, 0.0]]),
        np.asarray(
            [[0.0, 0.0, 0.0], [2.0, 0.4, 0.0], [2.2, 1.7, 0.0], [-0.3, 1.4, 0.0]]
        ),
    ],
)
def test_v09_regular_and_distorted_elements_retain_thickness_scaling_and_raw_nmq(
    coordinates: np.ndarray,
):
    displacement = _patch_displacement(coordinates)
    thick = evaluate_corotational_flat_shell(
        coordinates,
        displacement,
        young=21.0e6,
        poisson=0.3,
        thickness=0.2,
        alpha_d=1.0e-4,
    )
    thin = evaluate_corotational_flat_shell(
        coordinates,
        displacement,
        young=21.0e6,
        poisson=0.3,
        thickness=0.02,
        alpha_d=1.0e-4,
    )

    assert thick.min_det_j > 0.0
    assert thin.min_det_j > 0.0
    assert len(thin.gauss_points) == 4
    assert all("membrane_resultant" in point for point in thin.gauss_points)
    assert all("bending_resultant" in point for point in thin.gauss_points)
    assert all("shear_resultant" in point for point in thin.gauss_points)
    assert thin.membrane_energy / thick.membrane_energy == pytest.approx(0.1, rel=2.0e-12)
    assert thin.bending_energy / thick.bending_energy == pytest.approx(0.001, rel=2.0e-12)
    if thick.shear_energy > 1.0e-20:
        assert thin.shear_energy / thick.shear_energy == pytest.approx(0.1, rel=5.0e-7)
    if thick.drilling_energy > 1.0e-20:
        assert thin.drilling_energy / thick.drilling_energy == pytest.approx(0.1, rel=5.0e-7)
