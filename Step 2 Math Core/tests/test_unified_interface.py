from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

STEP2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STEP2_ROOT))

from step2_math_core import execute, list_core_ids, list_cores  # noqa: E402


class RegistryTests(unittest.TestCase):
    def test_all_four_cores_are_registered(self) -> None:
        self.assertEqual(
            list_core_ids(),
            (
                "constitutive_nonlinearity",
                "general_nonlinear_shell",
                "plate_shell_buckling",
                "shell_instability",
            ),
        )

    def test_unknown_core_returns_stable_error(self) -> None:
        response = execute({"core": "missing", "operation": "verify"})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, "UNKNOWN_CORE")
        json.dumps(response.to_dict())


class OperationTests(unittest.TestCase):
    def test_plate_linear_buckling(self) -> None:
        response = execute(
            {
                "core": "plate_shell_buckling",
                "operation": "linear_buckling",
                "parameters": {
                    "material_stiffness": [[12.0, -2.0], [-2.0, 6.0]],
                    "geometric_stiffness": [[1.0, 0.2], [0.2, 0.5]],
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        pairs = response.to_dict()["data"]["eigenpairs"]
        self.assertAlmostEqual(pairs[0]["value"], 7.1494134, places=7)
        self.assertAlmostEqual(pairs[1]["value"], 20.6766736, places=7)

    def test_instability_classification(self) -> None:
        response = execute(
            {
                "core": "shell_instability",
                "operation": "classify_critical_point",
                "parameters": {
                    "tangent": [[0.0, 0.0], [0.0, 4.0]],
                    "reference_load": [2.0, 1.0],
                    "right_null_vector": [1.0, 0.0],
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.to_dict()["data"]["kind"], "limit_point")

    def test_constitutive_update_returns_trial_state(self) -> None:
        response = execute(
            {
                "core": "constitutive_nonlinearity",
                "operation": "material_update",
                "parameters": {
                    "model": "combined_1d",
                    "total_strain": 0.002,
                    "committed_state": {
                        "plastic_strain": 0.0,
                        "alpha": 0.0,
                        "backstress": 0.0,
                    },
                    "material": {
                        "E": 210000.0,
                        "sigma_y0": 250.0,
                        "H_iso": 1000.0,
                        "H_kin": 0.0,
                    },
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        data = response.to_dict()["data"]
        self.assertAlmostEqual(data["stress"], 250.80568720379148)
        self.assertTrue(data["commit_required"])
        self.assertEqual(data["diagnostics"]["branch"], "plastic")

    def test_general_shell_rotation_preserves_so3(self) -> None:
        response = execute(
            {
                "core": "general_nonlinear_shell",
                "operation": "rotation_update",
                "parameters": {
                    "current_rotation": np.eye(3).tolist(),
                    "increment": [0.0, 0.0, math.pi / 2.0],
                    "increment_type": "spatial",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        data = response.to_dict()["data"]
        np.testing.assert_allclose(
            data["rotation"],
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            atol=1.0e-12,
        )
        self.assertLess(data["metrics"]["orthogonality_error"], 1.0e-12)

    def test_unknown_parameter_is_not_silently_ignored(self) -> None:
        response = execute(
            {
                "core": "plate_shell_buckling",
                "operation": "analysis_level",
                "parameters": {"question_kind": "ideal_critical_mode", "typo": True},
            }
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, "UNKNOWN_PARAMETER")


class VerificationTests(unittest.TestCase):
    def test_every_published_example_is_executable(self) -> None:
        for core in list_cores():
            for operation in core.operations:
                with self.subTest(core=core.core_id, operation=operation.name):
                    response = execute(
                        {
                            "core": core.core_id,
                            "operation": operation.name,
                            "parameters": operation.example_parameters,
                        }
                    )
                    self.assertTrue(response.ok, response.error)

    def test_all_original_verification_entry_points_are_reachable(self) -> None:
        expected_counts = {
            "plate_shell_buckling": 13,
            "shell_instability": 11,
            "constitutive_nonlinearity": 12,
            "general_nonlinear_shell": 15,
        }
        for core_id, expected_count in expected_counts.items():
            with self.subTest(core_id=core_id):
                response = execute({"core": core_id, "operation": "verify"})
                self.assertTrue(response.ok, response.error)
                data = response.to_dict()["data"]
                self.assertTrue(data["execution_ok"])
                self.assertEqual(len(data["verification_ids"]), expected_count)
                json.dumps(response.to_dict(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
