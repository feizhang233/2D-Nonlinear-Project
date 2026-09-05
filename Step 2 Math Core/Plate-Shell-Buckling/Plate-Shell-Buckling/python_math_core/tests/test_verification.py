from __future__ import annotations

import unittest

from plate_shell_buckling_core.contracts import AnalysisLevel, analysis_level_for
from plate_shell_buckling_core.verification import run_validation_suite, validation_as_dict


class TestVerification(unittest.TestCase):
    def test_analysis_routes_v22(self) -> None:
        self.assertEqual(analysis_level_for("ideal_critical_mode"), AnalysisLevel.LBA)
        self.assertEqual(analysis_level_for("perfect_postbuckling_path"), AnalysisLevel.GNA)
        self.assertEqual(analysis_level_for("imperfect_geometric_limit_load"), AnalysisLevel.GNIA)
        self.assertEqual(
            analysis_level_for("imperfect_plastic_residual_stress_limit_load"), AnalysisLevel.GMNIA
        )

    def test_v10_to_v22_all_pass(self) -> None:
        records = run_validation_suite()
        self.assertEqual([record.test_id for record in records], [f"V{index}" for index in range(10, 23)])
        failures = [record.test_id for record in records if not record.passed]
        self.assertEqual(failures, [])
        envelope = validation_as_dict(records)
        self.assertEqual(envelope["summary"]["reference_checks_passed"], 13)
        self.assertEqual(envelope["summary"]["reference_checks_total"], 13)
        self.assertTrue(envelope["summary"]["all_reference_checks_passed"])
        self.assertFalse(envelope["summary"]["production_fe_gate_claimed"])
        self.assertEqual(
            envelope["summary"]["status_counts"],
            {"ANALYTICAL_PASS": 6, "REFERENCE_CORE_PASS": 7},
        )

    def test_v21_retains_full_path_and_step_sensitivity(self) -> None:
        record = next(record for record in run_validation_suite() if record.test_id == "V21")
        self.assertEqual(len(record.computed["step_sensitivity"]), 3)
        self.assertEqual(len(record.computed["finest_path_history"]), 136)
        self.assertLess(record.computed["fine_endpoint_relative_change"], 1e-3)
        self.assertIn("predictor_root_sign", record.computed["finest_path_history"][0])


if __name__ == "__main__":
    unittest.main()
