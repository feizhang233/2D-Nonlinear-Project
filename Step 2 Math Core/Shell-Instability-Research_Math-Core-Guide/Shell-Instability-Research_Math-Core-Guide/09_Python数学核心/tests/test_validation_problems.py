from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shell_instability_math.audit import (
    EVIDENCE_REQUIREMENTS,
    EvidenceRecord,
    audit_research_evidence,
)
from shell_instability_math.benchmarks import (
    cylinder_axial_buckling,
    sphere_external_pressure,
)
from shell_instability_math.buckling import generalized_symmetric_eigenpairs
from shell_instability_math.continuation import (
    branch_switching_seed,
    spherical_arc_length_step,
)
from shell_instability_math.critical import (
    classify_singular_point,
    modal_assurance_criterion,
    stability_indicators,
    subspace_principal_angles,
)
from shell_instability_math.differentiation import scan_tangent_error
from shell_instability_math.koiter import (
    koiter_two_thirds_law,
    logarithmic_slopes,
    single_mode_quartic_branches,
    two_mode_quartic_branches,
)
from run_validation_problems import calculate


class ValidationProblems(unittest.TestCase):
    def test_v00_consistent_tangent(self) -> None:
        def residual(q: np.ndarray, load_factor: float) -> np.ndarray:
            q1, q2 = q
            return np.asarray(
                [
                    q1 + q1 * q2 + q1**3 / 3.0 - load_factor,
                    2.0 * q2 + q1**2 / 2.0 + q2**3 / 3.0,
                ]
            )

        q = np.asarray([0.2, -0.1])
        direction = np.asarray([0.3, -0.4])
        tangent = np.asarray([[0.94, 0.2], [0.2, 2.01]])
        np.testing.assert_allclose(tangent @ direction, [0.202, -0.744], atol=1e-14)
        scan = scan_tangent_error(
            residual,
            tangent,
            q,
            0.1,
            direction,
            [1e-1, 5e-2, 2.5e-2, 1e-2, 1e-4, 1e-6, 1e-8, 1e-10, 1e-12],
        )
        self.assertAlmostEqual(scan[1].observed_order or 0.0, 2.0, places=8)
        errors = np.asarray([point.absolute_error for point in scan])
        self.assertLess(float(np.min(errors)), 1e-9)
        self.assertGreater(errors[-1], float(np.min(errors)))

    def test_v01_critical_point_classification(self) -> None:
        tangent = np.asarray([[0.0, 0.0], [0.0, 4.0]])
        null_vector = np.asarray([1.0, 0.0])
        case_a = classify_singular_point(tangent, [2.0, 1.0], null_vector)
        case_b = classify_singular_point(tangent, [0.0, 1.0], null_vector)
        self.assertEqual(case_a.kind, "limit_point")
        self.assertEqual(case_b.kind, "bifurcation_candidate")
        self.assertEqual(case_a.projection, 2.0)
        self.assertEqual(case_b.projection, 0.0)
        self.assertEqual(case_a.nullity, 1)
        self.assertEqual(case_b.nullity, 1)
        self.assertEqual(case_a.right_null_residual, 0.0)
        self.assertEqual(case_a.left_null_residual, 0.0)

    def test_v01_rejects_false_singular_point_classification(self) -> None:
        with self.assertRaisesRegex(ValueError, "未通过奇异性检查"):
            classify_singular_point(
                [[1.0, 0.0], [0.0, 1.0]],
                [0.0, 1.0],
                [1.0, 0.0],
            )
        with self.assertRaisesRegex(ValueError, "right_null_vector 残差"):
            classify_singular_point(
                [[0.0, 0.0], [0.0, 4.0]],
                [2.0, 1.0],
                [0.0, 1.0],
            )
        with self.assertRaisesRegex(ValueError, "多模态临界子空间"):
            classify_singular_point(
                [[0.0, 0.0], [0.0, 0.0]],
                [1.0, 1.0],
                [1.0, 0.0],
            )

    def test_v02_generalized_eigenbuckling(self) -> None:
        k_material = np.asarray([[12.0, -2.0], [-2.0, 6.0]])
        k_geometric = np.asarray([[1.0, 0.2], [0.2, 0.5]])
        result = generalized_symmetric_eigenpairs(k_material, k_geometric)
        np.testing.assert_allclose(
            result.eigenvalues, [7.1494134, 20.6766736], rtol=1e-8
        )
        self.assertLess(float(np.max(result.relative_residuals)), 1e-14)
        ratios = result.modes[1, :] / result.modes[0, :]
        np.testing.assert_allclose(ratios, [np.sqrt(2.0), -np.sqrt(2.0)], atol=1e-12)

    def test_v03_single_mode_koiter(self) -> None:
        case_a = single_mode_quartic_branches(1.2, 1.0)
        case_b = single_mode_quartic_branches(0.8, -1.0)
        np.testing.assert_allclose(np.abs(case_a.amplitudes), np.sqrt(0.1))
        np.testing.assert_allclose(np.abs(case_b.amplitudes), np.sqrt(0.1))
        self.assertAlmostEqual(case_a.hessian, 0.8)
        self.assertAlmostEqual(case_b.hessian, -0.8)
        self.assertTrue(case_a.locally_stable)
        self.assertFalse(case_b.locally_stable)

    def test_v04_two_mode_interaction(self) -> None:
        branches = two_mode_quartic_branches(1.2)
        single = branches["single_mode"]
        mixed = branches["symmetric_mixed"]
        np.testing.assert_allclose(single.amplitude, [np.sqrt(0.1), 0.0])
        np.testing.assert_allclose(mixed.amplitude, [np.sqrt(1.0 / 15.0)] * 2)
        self.assertAlmostEqual(single.energy, -0.01)
        self.assertAlmostEqual(mixed.energy, -0.0133333333333333)
        np.testing.assert_allclose(single.hessian_eigenvalues, [-0.2, 0.8])
        np.testing.assert_allclose(mixed.hessian_eigenvalues, [0.266666666666667, 0.8])
        self.assertFalse(single.locally_stable)
        self.assertTrue(mixed.locally_stable)

    def test_v05_two_thirds_imperfection_law(self) -> None:
        magnitudes = np.asarray([1e-6, 1e-4, 1e-2])
        load_factors = koiter_two_thirds_law(magnitudes)
        np.testing.assert_allclose(
            load_factors,
            [0.99985, 0.9967683475, 0.930376167],
            rtol=2e-9,
        )
        slopes = logarithmic_slopes(magnitudes, 1.0 - load_factors)
        np.testing.assert_allclose(slopes, [2.0 / 3.0, 2.0 / 3.0], atol=1e-13)

    def test_v06_spherical_arc_length(self) -> None:
        def residual(q: np.ndarray, load_factor: float) -> np.ndarray:
            return np.asarray([q[0] - q[0] ** 3 - load_factor])

        def tangent(q: np.ndarray, _load_factor: float) -> np.ndarray:
            return np.asarray([[1.0 - 3.0 * q[0] ** 2]])

        result = spherical_arc_length_step(
            residual,
            tangent,
            [0.5],
            0.375,
            [1.0],
            0.1,
            beta=1.0,
        )
        self.assertTrue(result.converged)
        self.assertAlmostEqual(result.predictor_q[0], 0.5970142500, places=9)
        self.assertAlmostEqual(result.predictor_load_factor, 0.3992535625, places=9)
        self.assertAlmostEqual(result.q[0], 0.5995912434, places=9)
        self.assertAlmostEqual(result.load_factor, 0.3840323999, places=9)
        self.assertLess(result.residual_norm, 1e-12)
        self.assertLess(result.constraint_error, 1e-12)

    def test_v07_branch_switching_seed(self) -> None:
        result = branch_switching_seed([1.0, 0.0], [1.0, 1.0])
        self.assertEqual(result.gamma, -1.0)
        np.testing.assert_allclose(result.seed, [0.0, -1.0])
        self.assertEqual(result.orthogonality_error, 0.0)

    def test_v08_cylinder_benchmark(self) -> None:
        result = cylinder_axial_buckling(70000.0, 0.33, 500.0, 1.0, 1000.0)
        self.assertAlmostEqual(result.critical_stress_mpa, 85.625710, places=6)
        self.assertAlmostEqual(result.critical_membrane_force_n_per_mm, 85.625710, places=6)
        self.assertAlmostEqual(result.total_critical_load_kn, 269.001102, places=6)
        self.assertAlmostEqual(result.alpha_per_mm, 0.08087083, places=8)
        self.assertAlmostEqual(result.full_wavelength_mm, 77.6941, places=4)
        self.assertAlmostEqual(result.half_wave_count, 25.742, places=3)

    def test_v09_sphere_benchmark(self) -> None:
        result = sphere_external_pressure(70000.0, 0.33, 500.0, 1.0)
        self.assertAlmostEqual(result.critical_pressure_mpa, 0.34250284, places=8)
        self.assertAlmostEqual(result.critical_membrane_force_n_per_mm, 85.625710, places=6)

    def test_v10_research_audit(self) -> None:
        incomplete = audit_research_evidence({})
        self.assertFalse(incomplete.complete)
        self.assertEqual(set(incomplete.missing_categories), set(EVIDENCE_REQUIREMENTS))
        self.assertEqual(
            len(incomplete.missing_requirements),
            sum(len(requirements) for requirements in EVIDENCE_REQUIREMENTS.values()),
        )
        first_category = next(iter(EVIDENCE_REQUIREMENTS))
        with self.assertRaisesRegex(TypeError, "逐项 EvidenceRecord"):
            audit_research_evidence({first_category: True})  # type: ignore[arg-type]

        evidence = {
            category: {
                requirement_id: EvidenceRecord(
                    artifact=f"evidence/{category}/{requirement_id}.json",
                    acceptance_criterion=f"满足 {description}",
                    observed=f"已核对 {description}",
                    accepted=True,
                )
                for requirement_id, description in requirements.items()
            }
            for category, requirements in EVIDENCE_REQUIREMENTS.items()
        }
        complete = audit_research_evidence(evidence)
        self.assertTrue(complete.complete)
        self.assertFalse(complete.missing_categories)
        self.assertFalse(complete.missing_requirements)
        self.assertFalse(complete.rejected_requirements)

        rejected_evidence = {
            category: dict(category_evidence)
            for category, category_evidence in evidence.items()
        }
        first_requirement = next(iter(EVIDENCE_REQUIREMENTS[first_category]))
        rejected_evidence[first_category][first_requirement] = EvidenceRecord(
            artifact="evidence/failed.json",
            acceptance_criterion="残差小于 1e-8",
            observed="残差为 1e-3",
            accepted=False,
        )
        rejected = audit_research_evidence(rejected_evidence)
        self.assertFalse(rejected.complete)
        self.assertEqual(
            rejected.rejected_requirements,
            (f"{first_category}.{first_requirement}",),
        )


class SupportingIndicators(unittest.TestCase):
    def test_stability_and_modal_metrics(self) -> None:
        indicators = stability_indicators([[0.0, 0.0], [0.0, 4.0]])
        self.assertTrue(indicators.symmetric)
        self.assertEqual(indicators.zero_count, 1)
        self.assertEqual(indicators.negative_count, 0)
        self.assertAlmostEqual(modal_assurance_criterion([1, 0], [-1, 0]), 1.0)
        angles = subspace_principal_angles(
            np.asarray([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]),
            np.asarray([[1.0, 1.0], [1.0, -1.0], [0.0, 0.0]]),
        )
        np.testing.assert_allclose(angles, [0.0, 0.0], atol=3e-8)


class GeneratedReport(unittest.TestCase):
    def test_required_derivations_and_v10_status_are_preserved(self) -> None:
        results, markdown = calculate()
        self.assertIn(
            r"\mathbf K_T=\frac{\partial\mathbf R}{\partial\mathbf q}",
            markdown,
        )
        self.assertIn(r"0.46\lambda^2-12.8\lambda+68=0", markdown)
        self.assertIn("Delta q_p=0.0970142500", markdown)
        self.assertIn(r"\begin{bmatrix}\delta q\\\delta\lambda\end{bmatrix}", markdown)
        self.assertIn("审查逻辑 PASS；题干报告 FAIL", markdown)
        self.assertEqual(results["V10"]["audit_logic_status"], "PASS")
        self.assertEqual(results["V10"]["subject_report_status"], "FAIL")
        self.assertFalse(results["V10"]["given_report_reaches_gate"])


if __name__ == "__main__":
    unittest.main()
