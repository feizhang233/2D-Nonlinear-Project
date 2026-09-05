from __future__ import annotations

import unittest

import numpy as np

from general_nonlinear_shell_math.contracts import TangentContributions
from general_nonlinear_shell_math.loads import (
    follower_line_force,
    follower_line_tangent,
)
from general_nonlinear_shell_math.materials import BilinearIsotropic1D, MaterialState1D
from general_nonlinear_shell_math.section import (
    condense_plane_stress,
    integrate_linear_elastic_bending,
)
from general_nonlinear_shell_math.tangent import (
    directional_derivative_scan,
    polynomial_internal_minus_external_residual,
    polynomial_tangent,
)


class TangentTests(unittest.TestCase):
    def test_v04_analytic_tangent_and_canonical_residual_sign(self) -> None:
        point = np.array([0.2, -0.1])
        direction = np.array([0.3, -0.4])
        tangent = polynomial_tangent(point)
        np.testing.assert_allclose(tangent @ direction, [0.202, -0.744], atol=1.0e-14)
        samples = directional_derivative_scan(
            lambda q: -polynomial_internal_minus_external_residual(q, 0.1),
            tangent,
            point,
            direction,
            [1.0e-2, 1.0e-3, 1.0e-4, 1.0e-5, 1.0e-6, 1.0e-7, 1.0e-8],
            residual_sign=-1.0,
        )
        self.assertLess(samples[1].relative_error, samples[0].relative_error / 50.0)
        self.assertLess(min(sample.relative_error for sample in samples), 1.0e-10)

    def test_total_tangent_subtracts_load_contribution(self) -> None:
        parts = TangentContributions.from_arrays(
            material=np.eye(2) * 4.0,
            geometric=np.eye(2),
            rotational=np.zeros((2, 2)),
            stabilization=np.eye(2) * 0.5,
            load=np.array([[0.0, 2.0], [0.0, 0.0]]),
        )
        np.testing.assert_allclose(parts.total, [[5.5, -2.0], [0.0, 5.5]])
        self.assertFalse(parts.is_symmetric)


class FollowerLoadTests(unittest.TestCase):
    def test_v05_force_and_derivative(self) -> None:
        force = follower_line_force([0.0, 0.0], [2.0, 0.0], 3.0)
        tangent = follower_line_tangent(3.0)
        np.testing.assert_allclose(force, [0.0, 3.0, 0.0, 3.0])
        np.testing.assert_allclose(tangent[:, 3], [-1.5, 0.0, -1.5, 0.0])
        self.assertFalse(np.allclose(tangent, tangent.T))

    def test_v05_central_difference(self) -> None:
        epsilon = 1.0e-7
        plus = follower_line_force([0.0, 0.0], [2.0, epsilon], 3.0)
        minus = follower_line_force([0.0, 0.0], [2.0, -epsilon], 3.0)
        np.testing.assert_allclose(
            (plus - minus) / (2.0 * epsilon),
            follower_line_tangent(3.0)[:, 3],
            atol=1.0e-10,
        )


class SectionTests(unittest.TestCase):
    def test_v06_two_point_bending(self) -> None:
        result = integrate_linear_elastic_bending(
            elastic_modulus=210000.0,
            thickness=2.0,
            curvature=0.001,
            gauss_points=2,
        )
        self.assertAlmostEqual(result.surface_stress_top, 210.0)
        self.assertAlmostEqual(result.surface_stress_bottom, -210.0)
        self.assertAlmostEqual(result.membrane_force, 0.0)
        self.assertAlmostEqual(result.bending_moment, 140.0)

    def test_v06_one_point_cannot_integrate_bending_energy(self) -> None:
        result = integrate_linear_elastic_bending(
            elastic_modulus=210000.0,
            thickness=2.0,
            curvature=0.001,
            gauss_points=1,
        )
        self.assertAlmostEqual(result.bending_moment, 0.0)
        self.assertAlmostEqual(result.strain_energy_per_area, 0.0)

    def test_v08_plane_stress_condensation(self) -> None:
        result = condense_plane_stress([[100.0]], [[20.0]], [[20.0]], [[50.0]])
        self.assertAlmostEqual(float(result[0, 0]), 92.0)


class MaterialTests(unittest.TestCase):
    def test_v07_plastic_return_and_tangent(self) -> None:
        material = BilinearIsotropic1D(200000.0, 1000.0, 250.0)
        committed = MaterialState1D()
        response = material.evaluate(0.002, committed)
        self.assertTrue(response.yielded)
        self.assertAlmostEqual(response.trial_stress, 400.0)
        self.assertAlmostEqual(response.plastic_multiplier, 0.0007462686567164179)
        self.assertAlmostEqual(response.stress, 250.7462686567164)
        self.assertAlmostEqual(response.algorithmic_tangent, 995.0248756218906)
        self.assertEqual(committed, MaterialState1D())

    def test_elastic_trial_does_not_mutate_committed(self) -> None:
        material = BilinearIsotropic1D(200000.0, 1000.0, 250.0)
        committed = MaterialState1D(
            plastic_strain=0.001, accumulated_plastic_strain=0.001, stress=250.0
        )
        response = material.evaluate(0.0015, committed)
        self.assertFalse(response.yielded)
        self.assertEqual(committed.stress, 250.0)
        self.assertAlmostEqual(response.stress, 100.0)


if __name__ == "__main__":
    unittest.main()
