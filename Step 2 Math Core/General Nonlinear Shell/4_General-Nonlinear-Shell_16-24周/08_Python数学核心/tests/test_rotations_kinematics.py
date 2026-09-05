from __future__ import annotations

import unittest

import numpy as np

from general_nonlinear_shell_math.kinematics import (
    green_lagrange_strain,
    infinitesimal_strain_from_deformation_gradient,
    push_forward_second_piola,
    q4_center_shell_kinematics,
)
from general_nonlinear_shell_math.rotations import (
    axis_angle_rotation,
    rotation_metrics,
    so3_exp,
    update_rotation,
)


class RotationTests(unittest.TestCase):
    def test_v00_quarter_turn(self) -> None:
        rotation = so3_exp([0.0, 0.0, np.pi / 2.0])
        np.testing.assert_allclose(
            rotation @ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], atol=1.0e-14
        )
        metrics = rotation_metrics(rotation)
        self.assertLess(metrics.orthogonality_error, 1.0e-14)
        self.assertAlmostEqual(metrics.determinant, 1.0, places=14)

    def test_small_angle_branch(self) -> None:
        vector = np.array([1.0e-12, -2.0e-12, 3.0e-12])
        rotation = so3_exp(vector)
        metrics = rotation_metrics(rotation)
        self.assertLess(metrics.orthogonality_error, 1.0e-15)
        self.assertAlmostEqual(metrics.determinant, 1.0, places=15)

    def test_spatial_and_material_updates_are_explicit(self) -> None:
        current = axis_angle_rotation([1.0, 0.0, 0.0], 0.3)
        increment = [0.0, 0.2, 0.0]
        spatial = update_rotation(current, increment, increment_type="spatial")
        material = update_rotation(current, increment, increment_type="material")
        self.assertFalse(np.allclose(spatial, material))
        self.assertLess(rotation_metrics(spatial).orthogonality_error, 1.0e-14)
        self.assertLess(rotation_metrics(material).orthogonality_error, 1.0e-14)

    def test_invalid_increment_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            update_rotation(np.eye(3), [0.0, 0.0, 0.0], increment_type="mixed")


class KinematicsTests(unittest.TestCase):
    def test_v01_rigid_q4_motion(self) -> None:
        nodes = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        )
        directors = np.tile([0.0, 0.0, 1.0], (4, 1))
        rotation = axis_angle_rotation([0.0, 0.0, 1.0], 2.0 * np.pi / 3.0)
        current_nodes = (rotation @ nodes.T).T + [3.0, -2.0, 5.0]
        current_directors = (rotation @ directors.T).T
        result = q4_center_shell_kinematics(
            nodes, current_nodes, directors, current_directors
        )
        np.testing.assert_allclose(result.deformation_gradient, rotation, atol=2.0e-15)
        self.assertLess(np.linalg.norm(result.green_lagrange), 1.0e-14)
        self.assertLess(np.linalg.norm(result.membrane_strain), 1.0e-14)
        self.assertLess(np.linalg.norm(result.transverse_shear_strain), 1.0e-14)
        self.assertAlmostEqual(result.deformation_jacobian, 1.0)
        self.assertGreater(result.reference_signed_area_jacobian, 0.0)
        self.assertGreater(result.current_signed_area_jacobian, 0.0)
        self.assertLess(result.director_norm_error, 1.0e-14)
        self.assertLess(result.director_gradient_change_norm, 1.0e-14)

    def test_reflected_q4_configuration_is_rejected(self) -> None:
        nodes = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        )
        reflected = nodes.copy()
        reflected[:, 0] *= -1.0
        directors = np.tile([0.0, 0.0, 1.0], (4, 1))
        with self.assertRaisesRegex(ValueError, "inverted|nonpositive"):
            q4_center_shell_kinematics(nodes, reflected, directors, directors)

    def test_nonunit_nodal_directors_are_reported_before_normalisation(self) -> None:
        nodes = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        )
        reference_directors = np.tile([0.0, 0.0, 1.0], (4, 1))
        current_directors = np.tile([0.0, 0.0, 1.2], (4, 1))
        result = q4_center_shell_kinematics(
            nodes,
            nodes,
            reference_directors,
            current_directors,
        )
        self.assertAlmostEqual(result.director_norm_error, 0.2)
        self.assertAlmostEqual(
            result.director_interpolation_norm_before_normalisation, 1.2
        )

    def test_v02_small_strain_is_not_objective(self) -> None:
        rotation = axis_angle_rotation([0.0, 0.0, 1.0], np.pi / 2.0)
        np.testing.assert_allclose(
            green_lagrange_strain(rotation), np.zeros((3, 3)), atol=1.0e-14
        )
        np.testing.assert_allclose(
            infinitesimal_strain_from_deformation_gradient(rotation),
            np.diag([-1.0, -1.0, 0.0]),
            atol=1.0e-14,
        )

    def test_v03_second_piola_push_forward(self) -> None:
        deformation = np.diag([1.2, 0.9, 1.0])
        second_piola = np.diag([100.0, 50.0, 0.0])
        cauchy = push_forward_second_piola(deformation, second_piola)
        np.testing.assert_allclose(cauchy, np.diag([133.33333333333334, 37.5, 0.0]))

    def test_nonpositive_jacobian_rejected(self) -> None:
        with self.assertRaises(ValueError):
            push_forward_second_piola(np.diag([-1.0, 1.0, 1.0]), np.eye(3))


if __name__ == "__main__":
    unittest.main()
