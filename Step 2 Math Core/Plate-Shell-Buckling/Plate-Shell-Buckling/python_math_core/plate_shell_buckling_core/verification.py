"""Executable V10-V22 calculations and acceptance checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Any

import numpy as np

from .contracts import AnalysisLevel, analysis_level_for
from .imperfections import koiter_two_thirds, map_normal_imperfection
from .lba import (
    biaxial_rectangular_plate,
    cylindrical_shell_classical,
    directional_tangent_curve,
    integrate_plate_geometric_stiffness,
    pure_shear_square_plate,
    recover_membrane_forces,
    solve_generalized_buckling,
    solve_linear_prebuckling,
    uniaxial_rectangular_plate,
)
from .imperfections import apply_normal_imperfection, project_out_rigid_body_motion
from .modes import diagnose_mode, group_repeated_eigenvalues, mac, subspace_principal_angles
from .nonlinear import (
    ArcLengthSettings,
    TwoBarArch,
    arc_length_augmented_system,
    quartic_potential_bifurcation,
    spherical_arc_constraint,
    trace_spherical_arc_length,
)


@dataclass(frozen=True)
class VerificationRecord:
    test_id: str
    analysis_level: str
    title: str
    passed: bool
    computed: dict[str, Any]
    reference: dict[str, Any]
    evidence: str
    status: str
    scope: str


def _close(actual: float, expected: float, relative: float) -> bool:
    return math.isclose(actual, expected, rel_tol=relative, abs_tol=relative * max(abs(expected), 1.0))


def _record(
    test_id: str,
    level: str,
    title: str,
    passed: bool,
    computed: dict[str, Any],
    reference: dict[str, Any],
    evidence: str,
    *,
    status_kind: str = "ANALYTICAL",
    scope: str = "reference_math_core",
) -> VerificationRecord:
    status = f"{status_kind}_PASS" if passed else f"{status_kind}_FAIL"
    return VerificationRecord(test_id, level, title, bool(passed), computed, reference, evidence, status, scope)


def _run_arch_path(arch: TwoBarArch, step_size: float):
    force_scale_n = 1000.0

    def internal(q: np.ndarray) -> np.ndarray:
        return np.array([arch.internal_force_n(float(q[0]))])

    def tangent(q: np.ndarray) -> np.ndarray:
        return np.array([[arch.tangent_n_per_mm(float(q[0]))]])

    settings = ArcLengthSettings(
        step_size=step_size,
        beta=0.001,
        max_steps=math.ceil(136.0 / step_size),
        max_iterations=30,
        residual_tolerance=1e-11,
        constraint_tolerance=1e-11,
        minimum_step_size=step_size / 32.0,
        maximum_step_size=step_size,
    )
    points = trace_spherical_arc_length(
        internal,
        tangent,
        np.array([force_scale_n]),
        np.array([0.0]),
        0.0,
        settings,
    )
    return points, force_scale_n, settings


def run_arch_step_sensitivity(arch: TwoBarArch | None = None):
    """Run the V20/V21 arch with three decreasing spherical arc lengths."""

    model = arch or TwoBarArch(1000.0, 200.0, 210000.0, 100.0)
    return {
        step_size: _run_arch_path(model, step_size)
        for step_size in (4.0, 2.0, 1.0)
    }


def run_validation_suite() -> list[VerificationRecord]:
    """Calculate every source-package problem V10-V22 and evaluate its gate."""

    records: list[VerificationRecord] = []

    # V10 - analytic equilibrium and stability classification.
    v10 = quartic_potential_bifurcation(6.0)
    records.append(
        _record(
            "V10",
            "GNA foundation",
            "Equilibrium, stability and bifurcation",
            v10.critical_load_factor == 5.0
            and _close(v10.positive_branch or 0.0, math.sqrt(2.0), 1e-12)
            and (v10.nonzero_branch_tangent or 0.0) > 0.0,
            {
                "lambda_c": v10.critical_load_factor,
                "q_plus_at_lambda_6": v10.positive_branch,
                "q_minus_at_lambda_6": v10.negative_branch,
                "branch_tangent_at_lambda_6": v10.nonzero_branch_tangent,
                "classification": v10.classification,
            },
            {"lambda_c": 5.0, "classification": "symmetric_supercritical_bifurcation"},
            "All equilibrium branches are explicit; the non-zero branch tangent is positive for lambda>5.",
        )
    )

    # V11 - one connected load -> q0 -> membrane force -> K_G -> tangent chain.
    k_material = np.array([[10.0, -2.0], [-2.0, 6.0]])
    pre = solve_linear_prebuckling(k_material, np.array([0.0, 5.0]), constraints={0: 0.0})
    bg = np.array([[[1.0, 0.0], [0.0, 1.0]], [[0.5, 0.5], [-0.5, 0.5]]])
    recovery_operators = np.array(
        [
            [[0.0, 4.0], [0.0, 2.0], [0.0, 0.50]],
            [[0.0, 3.0], [0.0, 1.5], [0.0, 0.25]],
        ]
    )
    membrane = recover_membrane_forces(pre.displacement, recovery_operators)
    k_geo = integrate_plate_geometric_stiffness(bg, membrane, np.array([1.0, 1.0]))
    state = np.array([0.2, -0.1])
    direction = np.array([0.7, -0.4])
    nonlinear_scale = 3.0
    incremental_linear_tangent = k_material - k_geo

    def toy_internal(q: np.ndarray) -> np.ndarray:
        return incremental_linear_tangent @ q + nonlinear_scale * float(q @ q) * q

    toy_tangent = incremental_linear_tangent + nonlinear_scale * (
        float(state @ state) * np.eye(2) + 2.0 * np.outer(state, state)
    )
    tangent_curve = directional_tangent_curve(
        toy_internal,
        toy_tangent,
        state,
        direction,
        epsilons=[1e-3, 1e-4, 1e-5, 1e-6],
    )
    curve_ratios = [
        tangent_curve[index].relative_error / tangent_curve[index + 1].relative_error
        for index in range(len(tangent_curve) - 1)
    ]
    first_order_interval = all(7.5 < ratio < 12.5 for ratio in curve_ratios[:2])
    geo_symmetry_error = float(np.linalg.norm(k_geo - k_geo.T))
    records.append(
        _record(
            "V11",
            AnalysisLevel.LBA.value,
            "Prebuckling equilibrium and geometric stiffness",
            pre.free_residual_norm < 1e-12
            and geo_symmetry_error < 1e-12
            and first_order_interval
            and tangent_curve[-1].relative_error < 1e-6
            and float(np.min(np.linalg.eigvalsh(k_geo))) > 0.0,
            {
                "data_chain": [
                    "reference_load",
                    "equilibrated_q0",
                    "integration_point_membrane_forces",
                    "compression_positive_K_G",
                    "total_incremental_tangent",
                ],
                "free_residual_norm": pre.free_residual_norm,
                "reaction_dof_0": float(pre.reactions[0]),
                "prebuckling_displacement": pre.displacement.tolist(),
                "recovered_membrane_forces": membrane.tolist(),
                "geometric_symmetry_error": geo_symmetry_error,
                "geometric_min_eigenvalue": float(np.min(np.linalg.eigvalsh(k_geo))),
                "directional_tangent_curve": [asdict(point) for point in tangent_curve],
                "successive_error_ratios": curve_ratios,
                "first_order_interval_found": first_order_interval,
                "checks": [
                    "free residual",
                    "reaction",
                    "membrane units/sign",
                    "compression/tension direction",
                    "K_G symmetry",
                    "positive weakening energy",
                    "local operator ordering",
                    "multi-epsilon directional difference",
                ],
            },
            {"free_residual_norm": 0.0, "symmetric": True, "directional_difference": "first-order consistent"},
            "The same equilibrated q0 now drives membrane-force recovery and K_G; the total tangent includes that K_G and is checked across a decreasing epsilon sequence.",
            status_kind="REFERENCE_CORE",
        )
    )

    # V12 - generalized symmetric eigenproblem.
    k_m = np.array([[12.0, -2.0], [-2.0, 6.0]])
    k_g = np.array([[1.0, 0.2], [0.2, 0.5]])
    pairs = solve_generalized_buckling(k_m, k_g)
    values = [pair.value for pair in pairs if pair.is_compressive_candidate]
    max_residual = max(pair.normalized_residual for pair in pairs)
    records.append(
        _record(
            "V12",
            AnalysisLevel.LBA.value,
            "Two-DOF generalized eigenproblem and sign",
            len(values) == 2
            and _close(values[0], 7.1494, 1e-4)
            and _close(values[1], 20.6767, 1e-4)
            and max_residual < 1e-12,
            {"eigenvalues": values, "first_critical_load_kn": values[0] * 10.0, "max_residual": max_residual},
            {"eigenvalues": [7.1494, 20.6767], "first_critical_load_kn": 71.494},
            "The solver uses K_G=-K_sigma_ref and preserves eigenvalue signs; no absolute-value sorting is applied.",
            status_kind="REFERENCE_CORE",
        )
    )

    # V13 - uniaxial simply supported steel plate.
    v13 = uniaxial_rectangular_plate(
        a_mm=1200.0, b_mm=600.0, thickness_mm=6.0, young_mpa=210000.0, poisson=0.30
    )
    records.append(
        _record(
            "V13",
            AnalysisLevel.LBA.value,
            "Uniaxial simply supported rectangular plate",
            _close(v13.flexural_rigidity_n_mm, 4.153846e6, 1e-6)
            and _close(v13.critical_membrane_force_n_per_mm, 455.520, 2e-5)
            and (v13.mode_m, v13.mode_n) == (2, 1),
            asdict(v13),
            {"D_n_mm": 4.153846e6, "Ncr_n_per_mm": 455.520, "stress_mpa": 75.920, "load_kn": 273.312, "mode": [2, 1]},
            "All integer Navier modes in the configured search are compared; the selected axial half-wave is 600 mm.",
        )
    )

    # V14 - equal biaxial square plate and uniaxial comparison.
    v14 = biaxial_rectangular_plate(
        a_mm=400.0,
        b_mm=400.0,
        thickness_mm=2.0,
        young_mpa=70000.0,
        poisson=0.33,
        ny_over_nx=1.0,
    )
    v14_uniaxial = uniaxial_rectangular_plate(
        a_mm=400.0, b_mm=400.0, thickness_mm=2.0, young_mpa=70000.0, poisson=0.33
    )
    ratio = v14.critical_nx_n_per_mm / v14_uniaxial.critical_membrane_force_n_per_mm
    records.append(
        _record(
            "V14",
            AnalysisLevel.LBA.value,
            "Equal biaxial compression of a simply supported square",
            _close(v14.critical_nx_n_per_mm, 6.4609, 2e-5)
            and _close(v14.critical_nx_stress_mpa, 3.2304, 3e-5)
            and _close(ratio, 0.5, 1e-12)
            and (v14.mode_m, v14.mode_n) == (1, 1),
            {
                "D_n_mm": v14.flexural_rigidity_n_mm,
                "Ncr_each_direction_n_per_mm": v14.critical_nx_n_per_mm,
                "stress_mpa": v14.critical_nx_stress_mpa,
                "uniaxial_Ncr_n_per_mm": v14_uniaxial.critical_membrane_force_n_per_mm,
                "biaxial_to_uniaxial_ratio": ratio,
                "mode": [v14.mode_m, v14.mode_n],
            },
            {"Ncr_each_direction_n_per_mm": 6.4609, "stress_mpa": 3.2304, "uniaxial_Ncr_n_per_mm": 12.9217, "ratio": 0.5},
            "The same material and geometry are evaluated on two distinct proportional load paths.",
        )
    )

    # V15 - shear modal coupling and convergence.
    shear_2 = pure_shear_square_plate(truncation_m=2)
    shear_16 = pure_shear_square_plate(truncation_m=16)
    records.append(
        _record(
            "V15",
            AnalysisLevel.LBA.value,
            "Pure-shear square-plate modal coupling",
            _close(shear_2.buckling_coefficient, 11.1033, 1e-5)
            and _close(shear_16.buckling_coefficient, 9.3247, 1e-5)
            and shear_16.eigen_residual < 1e-12,
            {
                "M2_mode_count": shear_2.mode_count,
                "M2_ks": shear_2.buckling_coefficient,
                "M16_mode_count": shear_16.mode_count,
                "M16_ks": shear_16.buckling_coefficient,
                "M16_residual": shear_16.eigen_residual,
            },
            {"M2_ks": 11.1033, "M16_ks": 9.3247},
            "The code constructs the parity-coupled Navier matrix; it cannot produce a result from one uncoupled sine mode.",
        )
    )

    # V16 - ideal axial cylinder.
    v16 = cylindrical_shell_classical(
        radius_mm=500.0,
        length_mm=1000.0,
        thickness_mm=1.0,
        young_mpa=70000.0,
        poisson=0.33,
    )
    records.append(
        _record(
            "V16",
            AnalysisLevel.LBA.value,
            "Classical axially compressed thin cylinder",
            _close(v16.critical_stress_mpa, 85.626, 2e-5)
            and _close(v16.total_axial_load_kn, 269.00, 2e-4)
            and _close(v16.axisymmetric_wavelength_mm, 77.694, 2e-5)
            and v16.nearest_axial_halfwaves == 26,
            asdict(v16),
            {"stress_mpa": 85.626, "membrane_force_n_per_mm": 85.626, "load_kn": 269.00, "wavelength_mm": 77.694, "nearest_m": 26},
            "This is the perfect elastic Donnell benchmark only; imperfection, end, residual-stress and material effects are excluded.",
        )
    )

    # V17 - sign, MAC, subspace rotation, and executable candidate filters.
    basis_a = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
    root_two = math.sqrt(2.0)
    basis_b = np.array([[1.0 / root_two, 1.0 / root_two], [1.0 / root_two, -1.0 / root_two], [0.0, 0.0]])
    individual_mac = mac(basis_a[:, 0], basis_b[:, 0])
    sign_mac = mac(basis_a[:, 0], -basis_a[:, 0])
    angles = subspace_principal_angles(basis_a, basis_b)
    groups = group_repeated_eigenvalues([10.0, 10.005, 14.0], relative_tolerance=1e-3)
    diagnostic_k_m = np.diag([1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    diagnostic_k_g = np.diag([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0])
    rigid_basis = np.eye(8)[:, [0]]
    drilling_mask = np.array([False, True, False, False, False, False, False, False])
    constrained_mask = np.array([False, False, False, False, False, False, False, True])
    diagnostic_groups = ([0, 1, 2], [3, 4], [5, 6, 7])

    def diagnose(vector: list[float]):
        return diagnose_mode(
            vector,
            material_stiffness=diagnostic_k_m,
            geometric_weakening=diagnostic_k_g,
            rigid_basis=rigid_basis,
            drilling_mask=drilling_mask,
            constrained_mask=constrained_mask,
            groups=diagnostic_groups,
        )

    filter_cases = {
        "accepted": diagnose([0, 0, 0, 1, 0, 1, 0, 0]),
        "rigid": diagnose([1, 0, 0, 0, 0, 0, 0, 0]),
        "drilling": diagnose([0, 1, 0, 0, 0, 0, 0, 0]),
        "zero_energy": diagnose([0, 0, 1, 0, 0, 0, 0, 0]),
        "localized": diagnose([0, 0, 0, 0, 1, 0, 0, 0]),
        "constraint_leakage": diagnose([0, 0, 0, 0, 0, 0, 0, 1]),
        "wrong_load": diagnose([0, 0, 0, 0, 0, 0, 1, 0]),
    }
    filters_pass = (
        filter_cases["accepted"].accepted
        and "rigid_dominated" in filter_cases["rigid"].reasons
        and "drilling_dominated" in filter_cases["drilling"].reasons
        and "zero_energy" in filter_cases["zero_energy"].reasons
        and "single_group_localization" in filter_cases["localized"].reasons
        and "constraint_leakage" in filter_cases["constraint_leakage"].reasons
        and "wrong_load_direction" in filter_cases["wrong_load"].reasons
    )
    records.append(
        _record(
            "V17",
            AnalysisLevel.LBA.value,
            "Mode normalization, sign and repeated roots",
            _close(individual_mac, 0.5, 1e-12)
            and _close(sign_mac, 1.0, 1e-12)
            and float(np.max(angles)) < 1e-12
            and groups[0] == (0, 1)
            and filters_pass,
            {
                "individual_MAC_after_basis_rotation": individual_mac,
                "sign_reversed_MAC": sign_mac,
                "principal_angles_rad": angles.tolist(),
                "near_repeated_groups": [list(group) for group in groups],
                "filter_results": {
                    name: {"accepted": result.accepted, "reasons": list(result.reasons)}
                    for name, result in filter_cases.items()
                },
            },
            {"sign_reversed_MAC": 1.0, "repeated_subspace_max_angle_rad": 0.0},
            "Individual vectors rotate inside a repeated eigenspace; synthetic counterexamples now execute every required reference filter rather than listing filter names.",
            status_kind="REFERENCE_CORE",
        )
    )

    # V18 - length-valued normal imperfection and applied-geometry audit.
    v18 = map_normal_imperfection([0.0, 0.25, -0.50, 1.0], amplitude_mm=3.0, sign=-1)
    expected_offsets = np.array([0.0, -0.75, 1.50, -3.0])
    v18_geometry = apply_normal_imperfection(
        [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 100.0, 0.0], [0.0, 100.0, 0.0]],
        [[0.0, 0.0, 1.0]] * 4,
        [0.0, 0.25, -0.50, 1.0],
        amplitude_mm=3.0,
        sign=-1,
        fixed_mask=[True, False, False, False],
        elements=[[0, 1, 2, 3]],
        thickness_mm=2.0,
        source_id="V18-mode-1-normal-component",
    )
    rigid_test_coordinates = np.array(
        [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 100.0, 0.0], [0.0, 100.0, 0.0]]
    )
    centered = rigid_test_coordinates - np.mean(rigid_test_coordinates, axis=0)
    translation = np.array([1.0, -2.0, 0.5])
    rotation = np.array([0.002, -0.001, 0.003])
    rigid_contaminated = translation + np.cross(rotation, centered)
    rigid_contaminated[2, 2] += 1.0
    rigid_projection = project_out_rigid_body_motion(rigid_test_coordinates, rigid_contaminated)
    rigid_filter_passed = (
        rigid_projection.rigid_fraction_before > 0.5
        and rigid_projection.rigid_fraction_after < 1e-12
    )
    records.append(
        _record(
            "V18",
            "GNIA preparation",
            "Mode-to-geometric-imperfection mapping",
            np.allclose(v18.offsets_mm, expected_offsets, atol=1e-12, rtol=0.0)
            and v18.actual_max_amplitude_mm == 3.0
            and v18_geometry.geometry_valid
            and rigid_filter_passed,
            {
                "offsets_mm": v18.offsets_mm.tolist(),
                "actual_max_mm": v18.actual_max_amplitude_mm,
                "rms_amplitude_mm": v18_geometry.rms_amplitude_mm,
                "sign": v18.sign,
                "source_id": v18_geometry.source_id,
                "applied_coordinates_mm": v18_geometry.coordinates_mm.tolist(),
                "fixed_boundary_max_movement_mm": v18_geometry.fixed_boundary_max_movement_mm,
                "minimum_area_ratio": v18_geometry.minimum_area_ratio,
                "minimum_normal_alignment": v18_geometry.minimum_normal_alignment,
                "best_fit_rigid_fraction_diagnostic": v18_geometry.best_fit_rigid_fraction,
                "rigid_filter_counterexample": {
                    "fraction_before": rigid_projection.rigid_fraction_before,
                    "fraction_after": rigid_projection.rigid_fraction_after,
                    "passed": rigid_filter_passed,
                },
                "thickness_valid": v18_geometry.thickness_valid,
                "geometry_valid": v18_geometry.geometry_valid,
                "rigid_component_note": "reported as a diagnostic; the four-scalar exercise does not supply a full structural rigid-mode basis",
            },
            {"offsets_mm": expected_offsets.tolist(), "actual_max_mm": 3.0},
            "The filtered scalar mode is now applied along unit nodal normals and checked for fixed-boundary motion, area collapse, normal reversal, thickness, actual maximum and RMS amplitude.",
            status_kind="REFERENCE_CORE",
        )
    )

    # V19 - Koiter imperfection law.
    v19 = koiter_two_thirds(a4=-1.0, imperfection_mu=0.01)
    records.append(
        _record(
            "V19",
            AnalysisLevel.GNIA.value,
            "Koiter two-thirds imperfection reduction",
            _close(v19.limit_load_factor, 0.930376, 1e-5)
            and _close(v19.load_reduction_fraction, 0.069624, 1e-5)
            and _close(v19.modal_amplitude, 0.107722, 1e-5),
            asdict(v19),
            {"lambda_star": 0.930376, "reduction_percent": 6.9624, "modal_amplitude": 0.107722},
            "The formula is limited to the stated symmetric subcritical Koiter reduction near the critical point.",
        )
    )

    # V20 and V21 share the exact arch and a three-step-size arc-length audit.
    arch = TwoBarArch(1000.0, 200.0, 210000.0, 100.0)
    limit = arch.limit_point()
    path_runs = run_arch_step_sensitivity(arch)
    path_summaries: list[dict[str, Any]] = []
    run_arrays: dict[float, tuple[np.ndarray, np.ndarray]] = {}
    for step_size, (run_points, force_scale, settings) in path_runs.items():
        displacements = np.array([float(point.displacement[0]) for point in run_points])
        loads_n = np.array([point.load_factor * force_scale for point in run_points])
        maximum_index = int(np.argmax(loads_n))
        run_arrays[step_size] = (displacements, loads_n)
        path_summaries.append(
            {
                "step_size": step_size,
                "committed_steps": len(run_points),
                "nearest_peak_w_mm": float(displacements[maximum_index]),
                "nearest_peak_load_kn": float(loads_n[maximum_index] / 1000.0),
                "peak_w_relative_error": abs(float(displacements[maximum_index]) - limit.displacement_mm)
                / limit.displacement_mm,
                "peak_load_relative_error": abs(float(loads_n[maximum_index]) - limit.load_n) / limit.load_n,
                "path_max_w_mm": float(np.max(displacements)),
                "max_normalized_residual": max(point.residual_norm for point in run_points),
                "max_normalized_arc_constraint_error": max(point.constraint_error for point in run_points),
                "rejected_attempts": sum(point.rejected_attempts for point in run_points),
                "beta": settings.beta,
            }
        )
    path_summaries.sort(key=lambda summary: summary["step_size"], reverse=True)
    finest_summary = path_summaries[-1]
    fine_endpoint_change = abs(path_summaries[-1]["path_max_w_mm"] - path_summaries[-2]["path_max_w_mm"]) / abs(
        path_summaries[-1]["path_max_w_mm"]
    )
    all_paths_crossed = all(
        summary["path_max_w_mm"] > limit.displacement_mm + 5.0 for summary in path_summaries
    )
    all_paths_descend = True
    for _, (_, loads_n) in run_arrays.items():
        peak_index = int(np.argmax(loads_n))
        all_paths_descend = all_paths_descend and bool(np.any(np.diff(loads_n[peak_index:]) < -1e-6))
    records.append(
        _record(
            "V20",
            AnalysisLevel.GNA.value,
            "Shallow two-bar arch limit point",
            _close(limit.displacement_mm, 85.286, 2e-5)
            and _close(limit.load_n / 1000.0, 62.171, 2e-5)
            and finest_summary["peak_w_relative_error"] < 0.02
            and finest_summary["peak_load_relative_error"] < 0.02
            and fine_endpoint_change < 1e-3
            and all_paths_crossed
            and all_paths_descend,
            {
                "closed_form_w_mm": limit.displacement_mm,
                "closed_form_load_kn": limit.load_n / 1000.0,
                "step_sensitivity": path_summaries,
                "fine_endpoint_relative_change": fine_endpoint_change,
            },
            {"w_star_mm": 85.286, "load_star_kn": 62.171},
            "The closed form is independently checked at three decreasing arc lengths; the finest sampled peak is within 2% and all paths continue onto the descending segment.",
            status_kind="REFERENCE_CORE",
        )
    )

    all_points = [point for run_points, _, _ in path_runs.values() for point in run_points]
    max_residual = max(point.residual_norm for point in all_points)
    max_constraint = max(point.constraint_error for point in all_points)
    tangent_sign_change = all(
        any(point.minimum_tangent_eigenvalue < 0.0 for point in run_points)
        for run_points, _, _ in path_runs.values()
    )
    finest_points, finest_force_scale, finest_settings = path_runs[1.0]
    finest_path_history = [
        {
            "step": point.step,
            "displacement_mm": point.displacement.tolist(),
            "load_factor": point.load_factor,
            "load_n": point.load_factor * finest_force_scale,
            "normalized_residual": point.residual_norm,
            "normalized_arc_constraint_error": point.constraint_error,
            "iterations": point.iterations,
            "accepted_step_size": point.accepted_step_size,
            "rejected_attempts": point.rejected_attempts,
            "minimum_tangent_eigenvalue": point.minimum_tangent_eigenvalue,
            "predictor_load_increment": point.predictor_load_increment,
            "predictor_orientation": point.predictor_orientation,
            "predictor_root_sign": point.predictor_root_sign,
        }
        for point in finest_points
    ]
    sample_augmented = arc_length_augmented_system(
        np.array([[2.0]]), np.array([1.0]), np.array([0.5]), 0.25, beta=0.1
    )
    sample_constraint = spherical_arc_constraint(
        np.array([0.5]), 0.25, np.array([1.0]), beta=0.1, step_size=math.sqrt(0.250625)
    )
    records.append(
        _record(
            "V21",
            "GNA/GNIA",
            "Spherical arc length and branch evidence",
            all_paths_crossed
            and all_paths_descend
            and tangent_sign_change
            and max_residual < 1e-9
            and max_constraint < 1e-9
            and fine_endpoint_change < 1e-3
            and abs(sample_constraint) < 1e-14
            and sample_augmented.shape == (2, 2),
            {
                "control": "spherical_arc_length",
                "branch_definition": "continuous primary equilibrium path selected by positive weighted predictor orientation",
                "imperfection_definition": "none; perfect-geometry GNA shallow arch",
                "step_sensitivity": path_summaries,
                "finest_run_settings": asdict(finest_settings),
                "finest_path_history": finest_path_history,
                "max_normalized_residual": max_residual,
                "max_normalized_arc_constraint_error": max_constraint,
                "crossed_limit_point": all_paths_crossed,
                "descending_segment_found": all_paths_descend,
                "negative_tangent_found": tangent_sign_change,
                "minimum_tangent_n_per_mm": min(point.minimum_tangent_eigenvalue for point in all_points),
                "fine_endpoint_relative_change": fine_endpoint_change,
            },
            {"equilibrium_and_constraint_converged": True, "path_crosses_limit": True, "branch_stability_claim": False},
            "The complete finest-step history, predictor roots, step sizes, residuals and tangent eigenvalues are retained; convergence still does not prove physical stability, uniqueness or reachability.",
            status_kind="REFERENCE_CORE",
        )
    )

    # V22 - analysis-level conclusion boundary.
    routed = {
        "ideal_critical_mode": analysis_level_for("ideal_critical_mode").value,
        "perfect_postbuckling_path": analysis_level_for("perfect_postbuckling_path").value,
        "imperfect_geometric_limit_load": analysis_level_for("imperfect_geometric_limit_load").value,
        "imperfect_plastic_residual_stress_limit_load": analysis_level_for(
            "imperfect_plastic_residual_stress_limit_load"
        ).value,
    }
    expected_routes = {
        "ideal_critical_mode": "LBA",
        "perfect_postbuckling_path": "GNA",
        "imperfect_geometric_limit_load": "GNIA",
        "imperfect_plastic_residual_stress_limit_load": "GMNIA",
    }
    records.append(
        _record(
            "V22",
            "all levels",
            "Analysis-level conclusion boundary",
            routed == expected_routes,
            {"routes": routed, "LBA_is_design_strength": False},
            {"routes": expected_routes, "LBA_is_design_strength": False},
            "A linear eigenvalue is an ideal neutral multiplier, not a code design strength or an imperfection-reduced limit load.",
            status_kind="REFERENCE_CORE",
        )
    )

    return records


def validation_as_dict(records: list[VerificationRecord]) -> dict[str, Any]:
    """Return a JSON-ready evidence envelope."""

    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
    return {
        "analysis_contract": {
            "equilibrium": "r(q, lambda) = f_int(q) - lambda f_ref = 0",
            "eigenproblem": "K_M phi = lambda K_G phi",
            "geometric_mapping": "K_G = -K_sigma_ref",
            "compression_membrane_force": "positive",
        },
        "summary": {
            "reference_checks_passed": sum(record.passed for record in records),
            "reference_checks_total": len(records),
            "all_reference_checks_passed": all(record.passed for record in records),
            "status_counts": status_counts,
            "production_fe_gate_claimed": False,
        },
        "records": [asdict(record) for record in records],
    }


def validation_json(records: list[VerificationRecord]) -> str:
    return json.dumps(validation_as_dict(records), ensure_ascii=False, indent=2, sort_keys=True)


def validation_markdown(records: list[VerificationRecord]) -> str:
    envelope = validation_as_dict(records)
    lines = [
        "# Plate-Shell Buckling Python 数学核心演算报告",
        "",
        "## 分析层级与正号约定",
        "",
        "- 平衡：`r(q, λ) = f_int(q) - λ f_ref = 0`。",
        "- LBA：`K_M φ = λ K_G φ`，且 `K_G = -K_σ,ref`；压缩膜力取正。",
        "- 线性特征值仅表示完美基本路径上的局部中性倍率，不是设计强度。",
        "- GNA 弧长收敛表示增广方程找到平衡点，不证明分支稳定或唯一。",
        "",
        "## 汇总",
        "",
        f"参考核心检查：**{envelope['summary']['reference_checks_passed']}/{envelope['summary']['reference_checks_total']}**。",
        "这些状态不代表生产有限元闸门或软件认证通过。",
        "",
        "| ID | 层级 | 状态 | 演算主题 |",
        "|---|---|---|---|",
    ]
    for record in records:
        lines.append(f"| {record.test_id} | {record.analysis_level} | {record.status} | {record.title} |")
    lines.extend(["", "## 逐题数值证据", ""])
    for record in records:
        display_computed = dict(record.computed)
        path_history = display_computed.pop("finest_path_history", None)
        if path_history is not None:
            display_computed["finest_path_history"] = f"{len(path_history)} committed points; retained in JSON evidence"
        lines.extend(
            [
                f"### {record.test_id} - {record.title}",
                "",
                f"状态：**{record.status}**；层级：`{record.analysis_level}`；范围：`{record.scope}`。",
                "",
                "```json",
                json.dumps(display_computed, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
                f"证据边界：{record.evidence}",
                "",
            ]
        )
    lines.extend(
        [
            "## 尚未覆盖",
            "",
            "本实现没有声称通用曲壳有限元、材料塑性、接触、残余应力、制造缺陷统计或规范折减已经实现。",
            "V10-V22 的通过是本 Python 参考核心对知识包理论题的运行证据，不是任意生产模型或商业软件的认证证据。",
            "",
        ]
    )
    return "\n".join(lines)
