from __future__ import annotations

import math
import unittest

import numpy as np

from plate_shell_buckling_core.nonlinear import (
    ArcLengthSettings,
    TwoBarArch,
    arc_length_augmented_system,
    quartic_potential_bifurcation,
    spherical_arc_constraint,
    trace_spherical_arc_length,
)


class TestNonlinear(unittest.TestCase):
    def test_quartic_bifurcation_v10(self) -> None:
        result = quartic_potential_bifurcation(6.0)
        self.assertEqual(result.critical_load_factor, 5.0)
        self.assertAlmostEqual(result.positive_branch or 0.0, math.sqrt(2.0))
        self.assertGreater(result.nonzero_branch_tangent or 0.0, 0.0)
        self.assertEqual(result.classification, "symmetric_supercritical_bifurcation")

    def test_arch_limit_v20(self) -> None:
        arch = TwoBarArch(1000.0, 200.0, 210000.0, 100.0)
        result = arch.limit_point()
        self.assertAlmostEqual(result.displacement_mm, 85.286, places=3)
        self.assertAlmostEqual(result.load_n / 1000.0, 62.171, places=3)
        self.assertAlmostEqual(arch.tangent_n_per_mm(result.displacement_mm), 0.0, places=9)

    def test_spherical_constraint_and_augmented_matrix(self) -> None:
        step = math.sqrt(0.250625)
        value = spherical_arc_constraint([0.5], 0.25, [1.0], beta=0.1, step_size=step)
        self.assertAlmostEqual(value, 0.0)
        matrix = arc_length_augmented_system([[2.0]], [1.0], [0.5], 0.25, beta=0.1)
        np.testing.assert_allclose(matrix, [[2.0, -1.0], [1.0, 0.005]])

    def test_arc_length_crosses_arch_limit(self) -> None:
        arch = TwoBarArch(1000.0, 200.0, 210000.0, 100.0)

        def internal(q: np.ndarray) -> np.ndarray:
            return np.array([arch.internal_force_n(float(q[0]))])

        def tangent(q: np.ndarray) -> np.ndarray:
            return np.array([[arch.tangent_n_per_mm(float(q[0]))]])

        points = trace_spherical_arc_length(
            internal,
            tangent,
            [1000.0],
            [0.0],
            0.0,
            ArcLengthSettings(
                step_size=4.0,
                beta=0.001,
                max_steps=34,
                residual_tolerance=1e-11,
                constraint_tolerance=1e-11,
                minimum_step_size=0.125,
                maximum_step_size=4.0,
            ),
        )
        displacement = np.array([point.displacement[0] for point in points])
        load = np.array([1000.0 * point.load_factor for point in points])
        peak = int(np.argmax(load))
        self.assertGreater(np.max(displacement), arch.limit_point().displacement_mm + 5.0)
        self.assertTrue(np.any(np.diff(load[peak:]) < 0.0))
        self.assertTrue(any(point.minimum_tangent_eigenvalue < 0.0 for point in points))
        self.assertLess(max(point.residual_norm for point in points), 1e-9)
        self.assertLess(max(point.constraint_error for point in points), 1e-9)


if __name__ == "__main__":
    unittest.main()

