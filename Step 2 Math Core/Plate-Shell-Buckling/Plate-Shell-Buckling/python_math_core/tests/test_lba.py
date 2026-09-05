from __future__ import annotations

import math
import unittest

import numpy as np

from plate_shell_buckling_core.lba import (
    biaxial_rectangular_plate,
    cylindrical_shell_classical,
    cylindrical_shell_mode_load,
    directional_tangent_curve,
    flexural_rigidity,
    integrate_plate_geometric_stiffness,
    pure_shear_square_plate,
    recover_membrane_forces,
    solve_generalized_buckling,
    solve_linear_prebuckling,
    spherical_shell_external_pressure,
    uniaxial_rectangular_plate,
)


class TestLBA(unittest.TestCase):
    def test_flexural_rigidity_v13(self) -> None:
        self.assertAlmostEqual(flexural_rigidity(210000.0, 6.0, 0.3), 4.153846153846154e6, places=6)

    def test_prebuckling_constraints_and_reaction(self) -> None:
        result = solve_linear_prebuckling(
            [[10.0, -2.0], [-2.0, 6.0]], [0.0, 5.0], constraints={0: 0.0}
        )
        self.assertLess(result.free_residual_norm, 1e-13)
        self.assertAlmostEqual(result.displacement[1], 5.0 / 6.0)
        self.assertAlmostEqual(result.reactions[0], -5.0 / 3.0)

    def test_plate_geometric_stiffness_is_symmetric(self) -> None:
        bg = np.array([[[1.0, 0.0], [0.0, 1.0]], [[0.5, 0.5], [-0.5, 0.5]]])
        result = integrate_plate_geometric_stiffness(bg, [[4.0, 0.5], [0.5, 2.0]], [1.0, 1.0])
        np.testing.assert_allclose(result, result.T)
        self.assertGreater(np.linalg.eigvalsh(result)[0], 0.0)

    def test_v11_connected_recovery_and_difference_curve(self) -> None:
        pre = solve_linear_prebuckling(
            [[10.0, -2.0], [-2.0, 6.0]], [0.0, 5.0], constraints={0: 0.0}
        )
        recovery = np.array([[[0.0, 4.0], [0.0, 2.0], [0.0, 0.5]]])
        membrane = recover_membrane_forces(pre.displacement, recovery)
        np.testing.assert_allclose(membrane[0], [[10.0 / 3.0, 5.0 / 12.0], [5.0 / 12.0, 5.0 / 3.0]])
        base = np.array([[3.0, 0.2], [0.2, 2.0]])
        state = np.array([0.2, -0.1])
        direction = np.array([0.7, -0.4])

        def internal(q: np.ndarray) -> np.ndarray:
            return base @ q + 3.0 * float(q @ q) * q

        tangent = base + 3.0 * (float(state @ state) * np.eye(2) + 2.0 * np.outer(state, state))
        curve = directional_tangent_curve(
            internal, tangent, state, direction, epsilons=[1e-3, 1e-4, 1e-5, 1e-6]
        )
        ratios = [curve[index].relative_error / curve[index + 1].relative_error for index in range(3)]
        self.assertTrue(all(7.5 < ratio < 12.5 for ratio in ratios))

    def test_generalized_eigenproblem_v12(self) -> None:
        pairs = solve_generalized_buckling([[12.0, -2.0], [-2.0, 6.0]], [[1.0, 0.2], [0.2, 0.5]])
        self.assertEqual(len(pairs), 2)
        self.assertAlmostEqual(pairs[0].value, 7.149413397346066, places=12)
        self.assertAlmostEqual(pairs[1].value, 20.67667355917567, places=12)
        self.assertLess(max(pair.normalized_residual for pair in pairs), 1e-14)

    def test_generalized_eigenproblem_preserves_negative_sign(self) -> None:
        pairs = solve_generalized_buckling(np.eye(2), np.diag([1.0, -0.5]))
        self.assertEqual([pair.value for pair in pairs], [1.0, -2.0])

    def test_uniaxial_plate_v13(self) -> None:
        result = uniaxial_rectangular_plate(
            a_mm=1200.0, b_mm=600.0, thickness_mm=6.0, young_mpa=210000.0, poisson=0.30
        )
        self.assertEqual((result.mode_m, result.mode_n), (2, 1))
        self.assertAlmostEqual(result.critical_membrane_force_n_per_mm, 455.520, places=3)
        self.assertAlmostEqual(result.critical_stress_mpa, 75.920, places=3)
        self.assertAlmostEqual(result.total_edge_load_kn, 273.312, places=3)

    def test_biaxial_plate_v14(self) -> None:
        result = biaxial_rectangular_plate(
            a_mm=400.0,
            b_mm=400.0,
            thickness_mm=2.0,
            young_mpa=70000.0,
            poisson=0.33,
            ny_over_nx=1.0,
        )
        self.assertEqual((result.mode_m, result.mode_n), (1, 1))
        self.assertAlmostEqual(result.critical_nx_n_per_mm, 6.4609, places=4)
        self.assertAlmostEqual(result.critical_nx_stress_mpa, 3.2304, places=4)

    def test_pure_shear_requires_coupling_and_converges(self) -> None:
        with self.assertRaises(ValueError):
            pure_shear_square_plate(truncation_m=1)
        self.assertAlmostEqual(pure_shear_square_plate(truncation_m=2).buckling_coefficient, 11.1033, places=4)
        result = pure_shear_square_plate(truncation_m=16)
        self.assertAlmostEqual(result.buckling_coefficient, 9.3247, places=4)
        self.assertLess(result.eigen_residual, 1e-13)

    def test_classical_cylinder_v16(self) -> None:
        result = cylindrical_shell_classical(
            radius_mm=500.0,
            length_mm=1000.0,
            thickness_mm=1.0,
            young_mpa=70000.0,
            poisson=0.33,
        )
        self.assertAlmostEqual(result.critical_stress_mpa, 85.626, places=3)
        self.assertAlmostEqual(result.total_axial_load_kn, 269.00, places=2)
        self.assertAlmostEqual(result.axisymmetric_wavelength_mm, 77.694, places=3)
        self.assertEqual(result.nearest_axial_halfwaves, 26)
        discrete_axisymmetric = cylindrical_shell_mode_load(
            radius_mm=500.0,
            length_mm=1000.0,
            thickness_mm=1.0,
            young_mpa=70000.0,
            poisson=0.33,
            axial_halfwaves=26,
            circumferential_waves=0,
        )
        self.assertLess(abs(discrete_axisymmetric - result.critical_membrane_force_n_per_mm) / result.critical_membrane_force_n_per_mm, 0.001)

    def test_sphere_and_cylinder_share_classical_membrane_force(self) -> None:
        cylinder = cylindrical_shell_classical(
            radius_mm=500.0,
            length_mm=1000.0,
            thickness_mm=1.0,
            young_mpa=70000.0,
            poisson=0.33,
        )
        sphere = spherical_shell_external_pressure(
            radius_mm=500.0, thickness_mm=1.0, young_mpa=70000.0, poisson=0.33
        )
        self.assertTrue(
            math.isclose(
                sphere.critical_membrane_force_n_per_mm,
                cylinder.critical_membrane_force_n_per_mm,
                rel_tol=1e-14,
            )
        )


if __name__ == "__main__":
    unittest.main()
