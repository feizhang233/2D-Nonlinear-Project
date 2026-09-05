from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from general_nonlinear_shell_math.benchmarks import pure_bending_strip
from general_nonlinear_shell_math.continuation import solve_scalar_arc_length_step
from general_nonlinear_shell_math.state import CommittedShellState, StateTransaction
from general_nonlinear_shell_math.verification import (
    AUDIT_RESULT,
    FAILED,
    NOT_RUN,
    PARTIAL,
    REFERENCE_ONLY,
    VERIFIED,
    _executed_status,
    run_all_verifications,
    write_reports,
)


class BenchmarkTests(unittest.TestCase):
    def test_v10_closed_form_reference(self) -> None:
        result = pure_bending_strip(length=10.0, bending_stiffness=2.0)
        self.assertAlmostEqual(result.end_rotation, np.pi)
        self.assertAlmostEqual(result.end_x, 0.0)
        self.assertAlmostEqual(result.end_y, 20.0 / np.pi)
        self.assertAlmostEqual(result.strain_energy, np.pi**2 / 10.0)

    def test_v11_arc_length_crosses_limit_point(self) -> None:
        result = solve_scalar_arc_length_step(
            q_n=0.5,
            load_factor_n=0.375,
            arc_length=0.1,
        )
        self.assertTrue(result.converged)
        self.assertAlmostEqual(result.predictor_q, 0.5970142500145332, places=12)
        self.assertAlmostEqual(
            result.predictor_load_factor, 0.3992535625036333, places=12
        )
        self.assertAlmostEqual(result.q, 0.5995912434, places=10)
        self.assertAlmostEqual(result.load_factor, 0.3840323999, places=10)
        self.assertGreater(result.q, 1.0 / np.sqrt(3.0))
        self.assertLess(result.load_factor, 2.0 / (3.0 * np.sqrt(3.0)))


class StateTests(unittest.TestCase):
    def test_v12_failed_trial_rolls_back_exactly(self) -> None:
        committed = CommittedShellState.create(
            load_factor=1.0,
            rotation=np.eye(3),
            thickness=2.0,
            plastic_strain=[0.001, 0.002],
            hardening=[10.0, 20.0],
        )
        before = committed.sha256()
        transaction = StateTransaction(committed)
        transaction.trial.load_factor = 1.2
        transaction.trial.thickness = 1.8
        transaction.trial.plastic_strain[0] = 0.5
        transaction.trial.trial_stress[1] = 999.0
        self.assertEqual(transaction.committed.sha256(), before)
        transaction.rollback()
        self.assertEqual(transaction.trial.commit().sha256(), before)

    def test_commit_is_explicit(self) -> None:
        committed = CommittedShellState.create(
            load_factor=1.0,
            rotation=np.eye(3),
            thickness=2.0,
            plastic_strain=[0.0],
            hardening=[0.0],
        )
        transaction = StateTransaction(committed)
        transaction.trial.load_factor = 1.1
        updated = transaction.commit()
        self.assertAlmostEqual(updated.load_factor, 1.1)
        self.assertNotEqual(updated.sha256(), committed.sha256())


class VerificationReportTests(unittest.TestCase):
    def test_executed_failure_is_not_reported_as_not_run(self) -> None:
        self.assertEqual(_executed_status(False, VERIFIED), FAILED)

    def test_all_ids_and_expected_boundaries(self) -> None:
        records = run_all_verifications()
        self.assertEqual(
            [record.test_id for record in records],
            [f"V{index:02d}" for index in range(15)],
        )
        by_id = {record.test_id: record for record in records}
        for test_id in ("V00", "V02", "V03", "V06", "V07", "V08", "V11", "V12"):
            self.assertEqual(by_id[test_id].status, VERIFIED)
        for test_id in ("V01", "V04", "V05"):
            self.assertEqual(by_id[test_id].status, PARTIAL)
        self.assertEqual(by_id["V10"].status, REFERENCE_ONLY)
        for test_id in ("V09", "V13"):
            self.assertEqual(by_id[test_id].status, NOT_RUN)
        self.assertEqual(by_id["V14"].status, AUDIT_RESULT)
        self.assertNotIn(FAILED, {record.status for record in records})
        self.assertTrue(by_id["V12"].computed["trial_caches_cleared"])
        self.assertTrue(by_id["V12"].computed["clean_restart_history_matches"])

    def test_json_and_markdown_reports_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            json_path, markdown_path = write_reports(Path(temporary))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["records"]), 15)
            self.assertEqual(payload["schema_version"], "1.1")
            self.assertEqual(payload["residual_convention"], "r = f_ext - f_int")
            self.assertEqual(payload["summary"]["passed_stage_gates"], [])
            self.assertEqual(
                set(payload["summary"]["stage_gates"]),
                {f"G{index}" for index in range(8)},
            )
            self.assertEqual(payload["summary"]["failed"], [])
            self.assertNotIn(
                "V14",
                payload["summary"]["stage_gates"]["G7"]["incomplete_checks"],
            )
            self.assertIn("python_version", payload["runtime"])
            self.assertIn("numpy_version", payload["runtime"])
            text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("V00 SO(3) 指数更新", text)
            self.assertIn("V13 大变形弹塑性方板系统基准", text)
            self.assertIn("没有把解析答案冒充真实非线性壳单元", text)
            self.assertIn("阶段闸门 G0-G7", text)
            self.assertIn("| G0 | 有限转动壳运动学 | NOT_PASSED", text)


if __name__ == "__main__":
    unittest.main()
