from __future__ import annotations

import math
import unittest

import numpy as np

from plate_shell_buckling_core.imperfections import (
    apply_normal_imperfection,
    koiter_two_thirds,
    map_normal_imperfection,
    project_out_rigid_body_motion,
)
from plate_shell_buckling_core.modes import (
    diagnose_mode,
    group_repeated_eigenvalues,
    mac,
    normalize_mode,
    subspace_principal_angles,
)


class TestModesAndImperfections(unittest.TestCase):
    def test_normalization(self) -> None:
        np.testing.assert_allclose(normalize_mode([3.0, 4.0]), [0.6, 0.8])
        np.testing.assert_allclose(normalize_mode([-2.0, 1.0], method="max_abs"), [-1.0, 0.5])

    def test_mac_is_sign_invariant(self) -> None:
        self.assertAlmostEqual(mac([1.0, 2.0], [-1.0, -2.0]), 1.0)

    def test_repeated_subspace_rotation(self) -> None:
        a = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
        b = np.array(
            [[1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0)], [1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0)], [0.0, 0.0]]
        )
        self.assertAlmostEqual(mac(a[:, 0], b[:, 0]), 0.5)
        self.assertLess(np.max(subspace_principal_angles(a, b)), 1e-12)

    def test_subspace_rejects_rank_deficiency(self) -> None:
        with self.assertRaises(ValueError):
            subspace_principal_angles([[1.0, 2.0], [0.0, 0.0]], [[1.0], [0.0]])

    def test_group_repeated_roots(self) -> None:
        self.assertEqual(group_repeated_eigenvalues([10.0, 10.005, 14.0], relative_tolerance=1e-3), [(0, 1), (2,)])

    def test_imperfection_mapping_v18(self) -> None:
        result = map_normal_imperfection([0.0, 0.25, -0.50, 1.0], amplitude_mm=3.0, sign=-1)
        np.testing.assert_allclose(result.offsets_mm, [0.0, -0.75, 1.5, -3.0])
        self.assertEqual(result.actual_max_amplitude_mm, 3.0)

    def test_imperfection_rejects_fixed_boundary_motion(self) -> None:
        with self.assertRaises(ValueError):
            map_normal_imperfection([0.1, 1.0], amplitude_mm=3.0, sign=1, fixed_mask=[True, False])

    def test_applied_imperfection_geometry_v18(self) -> None:
        result = apply_normal_imperfection(
            [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 100.0, 0.0], [0.0, 100.0, 0.0]],
            [[0.0, 0.0, 1.0]] * 4,
            [0.0, 0.25, -0.5, 1.0],
            amplitude_mm=3.0,
            sign=-1,
            fixed_mask=[True, False, False, False],
            elements=[[0, 1, 2, 3]],
            thickness_mm=2.0,
            source_id="V18",
        )
        self.assertTrue(result.geometry_valid)
        self.assertEqual(result.fixed_boundary_max_movement_mm, 0.0)
        self.assertGreater(result.minimum_area_ratio, 0.0)
        self.assertGreater(result.minimum_normal_alignment, 0.0)

    def test_rigid_body_projection(self) -> None:
        coordinates = np.array(
            [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 100.0, 0.0], [0.0, 100.0, 0.0]]
        )
        centered = coordinates - np.mean(coordinates, axis=0)
        displacement = np.array([1.0, -2.0, 0.5]) + np.cross([0.002, -0.001, 0.003], centered)
        displacement[2, 2] += 1.0
        result = project_out_rigid_body_motion(coordinates, displacement)
        self.assertGreater(result.rigid_fraction_before, 0.5)
        self.assertLess(result.rigid_fraction_after, 1e-12)

    def test_executable_mode_filters(self) -> None:
        k_m = np.diag([1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        k_g = np.diag([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0])
        common = {
            "material_stiffness": k_m,
            "geometric_weakening": k_g,
            "rigid_basis": np.eye(8)[:, [0]],
            "drilling_mask": [False, True, False, False, False, False, False, False],
            "constrained_mask": [False, False, False, False, False, False, False, True],
            "groups": ([0, 1, 2], [3, 4], [5, 6, 7]),
        }
        self.assertTrue(diagnose_mode([0, 0, 0, 1, 0, 1, 0, 0], **common).accepted)
        self.assertIn("rigid_dominated", diagnose_mode([1, 0, 0, 0, 0, 0, 0, 0], **common).reasons)
        self.assertIn("drilling_dominated", diagnose_mode([0, 1, 0, 0, 0, 0, 0, 0], **common).reasons)
        self.assertIn("zero_energy", diagnose_mode([0, 0, 1, 0, 0, 0, 0, 0], **common).reasons)
        self.assertIn("wrong_load_direction", diagnose_mode([0, 0, 0, 0, 0, 0, 1, 0], **common).reasons)

    def test_koiter_v19(self) -> None:
        result = koiter_two_thirds(a4=-1.0, imperfection_mu=0.01)
        self.assertAlmostEqual(result.limit_load_factor, 0.930376, places=6)
        self.assertAlmostEqual(100.0 * result.load_reduction_fraction, 6.9624, places=4)
        self.assertAlmostEqual(result.modal_amplitude, 0.107722, places=6)


if __name__ == "__main__":
    unittest.main()
