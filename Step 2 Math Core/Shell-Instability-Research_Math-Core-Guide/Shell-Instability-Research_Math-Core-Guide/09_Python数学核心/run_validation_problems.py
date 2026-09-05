#!/usr/bin/env python3
"""演算资料包 V00-V10，并生成 Markdown 与 JSON 证据。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from shell_instability_math.audit import EVIDENCE_REQUIREMENTS, audit_research_evidence
from shell_instability_math.benchmarks import (
    cylinder_axial_buckling,
    sphere_external_pressure,
)
from shell_instability_math.buckling import generalized_symmetric_eigenpairs
from shell_instability_math.continuation import (
    branch_switching_seed,
    spherical_arc_length_step,
)
from shell_instability_math.critical import classify_singular_point
from shell_instability_math.differentiation import scan_tangent_error
from shell_instability_math.koiter import (
    koiter_two_thirds_law,
    logarithmic_slopes,
    single_mode_quartic_branches,
    two_mode_quartic_branches,
)


def _close(actual: Any, expected: Any, *, rtol: float = 1e-8, atol: float = 1e-10) -> None:
    np.testing.assert_allclose(actual, expected, rtol=rtol, atol=atol)


def calculate() -> tuple[dict[str, Any], str]:
    results: dict[str, Any] = {}
    sections: list[str] = [
        "# V00-V10 Python 演算与校验结果",
        "",
        "公式与验收值来自 `03_验证题目与答案/验证题目.md`、`配套答案.md` 和 `验证矩阵.md`。",
        "本报告只证明低维数学核心通过资料包题目，不代表已经实现生产级壳单元、GNIA/GMNIA 或设计规范校核。",
        "",
    ]

    def v00_residual(q: np.ndarray, load_factor: float) -> np.ndarray:
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
    tangent_product = tangent @ direction
    centered_error_coefficient = np.asarray(
        [direction[0] ** 3 / 3.0, direction[1] ** 3 / 3.0]
    )
    _close(tangent_product, [0.202, -0.744])
    scan = scan_tangent_error(
        v00_residual,
        tangent,
        q,
        0.1,
        direction,
        [1e-1, 3e-2, 1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11, 1e-12],
    )
    errors = np.asarray([point.absolute_error for point in scan])
    if not (abs((scan[1].observed_order or 0.0) - 2.0) < 1e-7 and errors[-1] > np.min(errors)):
        raise AssertionError("V00 未观察到中心差分二阶区与舍入误差反弹")
    results["V00"] = {
        "status": "PASS",
        "tangent_formula": "[[1+q2+q1^2, q1], [q1, 2+q2^2]]",
        "tangent": tangent.tolist(),
        "tangent_times_direction": tangent_product.tolist(),
        "centered_error_coefficient": centered_error_coefficient.tolist(),
        "minimum_error": float(np.min(errors)),
        "minimum_error_step": scan[int(np.argmin(errors))].step,
        "scan": [
            {
                "h": point.step,
                "approximation": point.approximation.tolist(),
                "absolute_error": point.absolute_error,
                "observed_order": point.observed_order,
            }
            for point in scan
        ],
    }
    sections.extend(
        [
            "## V00 一致切线方向差分 — PASS",
            "",
            "由逐项求导得到：",
            "",
            "$$",
            "\\mathbf K_T=\\frac{\\partial\\mathbf R}{\\partial\\mathbf q}",
            "=\\begin{bmatrix}",
            "1+q_2+q_1^2&q_1\\\\",
            "q_1&2+q_2^2",
            "\\end{bmatrix}.",
            "$$",
            "",
            f"解析切线为 `[[0.94, 0.2], [0.2, 2.01]]`，`K_T p = ({tangent_product[0]:.12f}, {tangent_product[1]:.12f})`。",
            f"本题中心差分的解析截断误差为 `h^2*({centered_error_coefficient[0]:.12f}, {centered_error_coefficient[1]:.12f})`，因此舍入误差主导前应呈二阶收敛。",
            "",
            "| h | 差分第1分量 | 差分第2分量 | 绝对误差 | 相邻阶次 |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for point in scan:
        order_text = "—" if point.observed_order is None else f"{point.observed_order:.3f}"
        sections.append(
            f"| {point.step:.0e} | {point.approximation[0]:.10f} | {point.approximation[1]:.10f} | {point.absolute_error:.3e} | {order_text} |"
        )
    sections.extend(
        [
            "",
            f"误差谷值为 `{np.min(errors):.3e}`（`h={scan[int(np.argmin(errors))].step:.0e}`）；大步长区呈二阶收敛，小步长区出现舍入误差反弹。",
            "",
        ]
    )

    singular_tangent = np.asarray([[0.0, 0.0], [0.0, 4.0]])
    null_vector = np.asarray([1.0, 0.0])
    case_a = classify_singular_point(singular_tangent, [2.0, 1.0], null_vector)
    case_b = classify_singular_point(singular_tangent, [0.0, 1.0], null_vector)
    if case_a.kind != "limit_point" or case_b.kind != "bifurcation_candidate":
        raise AssertionError("V01 分类不匹配")
    results["V01"] = {
        "status": "PASS",
        "case_a": {
            "projection": case_a.projection,
            "classification": case_a.kind,
            "nullity": case_a.nullity,
            "right_null_residual": case_a.right_null_residual,
            "left_null_residual": case_a.left_null_residual,
        },
        "case_b": {
            "projection": case_b.projection,
            "classification": case_b.kind,
            "nullity": case_b.nullity,
            "right_null_residual": case_b.right_null_residual,
            "left_null_residual": case_b.left_null_residual,
        },
    }
    sections.extend(
        [
            "## V01 极限点与分岔点分类 — PASS",
            "",
            f"奇异值检查给出数值零空间维数 `{case_a.nullity}`，左右零向量相对残差均为 `{case_a.right_null_residual:.1e}`。A：`psi^T f_ref={case_a.projection:.1f}`，分类为普通极限点；B：`psi^T f_ref={case_b.projection:.1f}`，分类为分岔候选点。`det(K_T)=0` 只能说明奇异，不能完成分类。",
            "",
        ]
    )

    eigenpairs = generalized_symmetric_eigenpairs(
        [[12.0, -2.0], [-2.0, 6.0]], [[1.0, 0.2], [0.2, 0.5]]
    )
    _close(eigenpairs.eigenvalues, [7.1494134, 20.6766736])
    mode_ratios = eigenpairs.modes[1, :] / eigenpairs.modes[0, :]
    _close(mode_ratios, [np.sqrt(2.0), -np.sqrt(2.0)], atol=1e-12)
    critical_loads = 10.0 * eigenpairs.eigenvalues
    results["V02"] = {
        "status": "PASS",
        "characteristic_polynomial": "0.46*lambda^2 - 12.8*lambda + 68 = 0",
        "eigenvalues": eigenpairs.eigenvalues.tolist(),
        "mode_second_to_first_ratios": mode_ratios.tolist(),
        "critical_loads_kn": critical_loads.tolist(),
        "relative_residuals": eigenpairs.relative_residuals.tolist(),
    }
    sections.extend(
        [
            "## V02 二自由度广义特征屈曲 — PASS",
            "",
            "特征方程展开为：",
            "",
            "$$",
            "\\det(\\mathbf K_M-\\lambda\\mathbf K_G)",
            "=0.46\\lambda^2-12.8\\lambda+68=0.",
            "$$",
            "",
            f"特征值为 `{eigenpairs.eigenvalues[0]:.10f}`、`{eigenpairs.eigenvalues[1]:.10f}`；模态方向比为 `(1,{mode_ratios[0]:.10f})`、`(1,{mode_ratios[1]:.10f})`；10 kN 参考载荷对应 `{critical_loads[0]:.6f} kN`、`{critical_loads[1]:.6f} kN`。最大相对特征残差 `{np.max(eigenpairs.relative_residuals):.3e}`。这些值不能单独回答缺陷极限载荷、后屈曲稳定性或实际工程失效。",
            "",
        ]
    )

    v03_a = single_mode_quartic_branches(1.2, 1.0)
    v03_b = single_mode_quartic_branches(0.8, -1.0)
    _close(np.abs(v03_a.amplitudes), [np.sqrt(0.1)] * 2)
    _close(np.abs(v03_b.amplitudes), [np.sqrt(0.1)] * 2)
    _close([v03_a.hessian, v03_b.hessian], [0.8, -0.8])
    results["V03"] = {
        "status": "PASS",
        "case_a": {"amplitudes": v03_a.amplitudes.tolist(), "hessian": v03_a.hessian, "type": v03_a.branch_type, "stable": v03_a.locally_stable},
        "case_b": {"amplitudes": v03_b.amplitudes.tolist(), "hessian": v03_b.hessian, "type": v03_b.branch_type, "stable": v03_b.locally_stable},
    }
    sections.extend(
        [
            "## V03 单模态 Koiter 分支 — PASS",
            "",
            f"两例均有 `a=±{np.sqrt(0.1):.9f}`。A 的幅值 Hessian 为 `{v03_a.hessian:.1f}`，超临界且局部稳定；B 为 `{v03_b.hessian:.1f}`，次临界且局部不稳定。",
            "",
        ]
    )

    v04 = two_mode_quartic_branches(1.2)
    single = v04["single_mode"]
    mixed = v04["symmetric_mixed"]
    _close(single.hessian_eigenvalues, [-0.2, 0.8])
    _close(mixed.hessian_eigenvalues, [0.266666666666667, 0.8])
    results["V04"] = {
        "status": "PASS",
        "single_mode": {"amplitude": single.amplitude.tolist(), "energy": single.energy, "hessian_eigenvalues": single.hessian_eigenvalues.tolist(), "stable": single.locally_stable},
        "symmetric_mixed": {"amplitude": mixed.amplitude.tolist(), "energy": mixed.energy, "hessian_eigenvalues": mixed.hessian_eigenvalues.tolist(), "stable": mixed.locally_stable},
    }
    sections.extend(
        [
            "## V04 双模态交互 — PASS",
            "",
            f"单模态代表分支 `a=({single.amplitude[0]:.9f},0)`，能量 `{single.energy:.9f}`，Hessian 特征值 `{single.hessian_eigenvalues.tolist()}`，全幅值空间不稳定。混合分支 `a1=a2={mixed.amplitude[0]:.9f}`，能量 `{mixed.energy:.9f}`，Hessian 特征值 `{mixed.hessian_eigenvalues.tolist()}`，局部稳定且能量更低。",
            "",
        ]
    )

    magnitudes = np.asarray([1e-6, 1e-4, 1e-2])
    v05_loads = koiter_two_thirds_law(magnitudes)
    slopes = logarithmic_slopes(magnitudes, 1.0 - v05_loads)
    _close(slopes, [2.0 / 3.0, 2.0 / 3.0], atol=1e-13)
    results["V05"] = {"status": "PASS", "imperfections": magnitudes.tolist(), "load_factors": v05_loads.tolist(), "log_slopes": slopes.tolist()}
    sections.extend(
        [
            "## V05 Koiter 2/3 缺陷律 — PASS",
            "",
            f"`|mu|=[1e-6,1e-4,1e-2]` 得 `lambda*=[{v05_loads[0]:.9f},{v05_loads[1]:.9f},{v05_loads[2]:.9f}]`；相邻对数斜率为 `{slopes[0]:.12f}`、`{slopes[1]:.12f}`。该标量律不能替代多模态缺陷方向扫描。",
            "",
        ]
    )

    def v06_residual(q_value: np.ndarray, load_factor: float) -> np.ndarray:
        return np.asarray([q_value[0] - q_value[0] ** 3 - load_factor])

    def v06_tangent(q_value: np.ndarray, _load_factor: float) -> np.ndarray:
        return np.asarray([[1.0 - 3.0 * q_value[0] ** 2]])

    v06 = spherical_arc_length_step(v06_residual, v06_tangent, [0.5], 0.375, [1.0], 0.1)
    if not v06.converged:
        raise AssertionError("V06 弧长校正未收敛")
    _close([v06.q[0], v06.load_factor], [0.5995912434, 0.3840323999], atol=1e-9)
    predictor_delta_q = float(v06.predictor_q[0] - 0.5)
    predictor_delta_load = v06.predictor_load_factor - 0.375
    predictor_residual = float(
        v06_residual(v06.predictor_q, v06.predictor_load_factor)[0]
    )
    theoretical_q = 1.0 / np.sqrt(3.0)
    theoretical_load = 2.0 / (3.0 * np.sqrt(3.0))
    results["V06"] = {
        "status": "PASS",
        "predictor": [float(v06.predictor_q[0]), v06.predictor_load_factor],
        "predictor_increment": [predictor_delta_q, predictor_delta_load],
        "predictor_residual": predictor_residual,
        "augmented_newton_system": {
            "matrix": "[[1-3*q^2, -1], [2*(q-0.5), 2*(lambda-0.375)]]",
            "right_hand_side": "-[q-q^3-lambda, (q-0.5)^2+(lambda-0.375)^2-0.01]",
        },
        "corrected": [float(v06.q[0]), v06.load_factor],
        "theoretical_limit": [float(theoretical_q), float(theoretical_load)],
        "iterations": v06.iterations,
        "residual_norm": v06.residual_norm,
        "constraint_error": v06.constraint_error,
        "past_limit_point": bool(v06.q[0] > theoretical_q and v06.load_factor < theoretical_load),
    }
    sections.extend(
        [
            "## V06 球形弧长跨越极限点 — PASS",
            "",
            f"起点 `K_T=0.25`、`q_t=4`；正向预测增量为 `Delta q_p={predictor_delta_q:.10f}`、`Delta lambda_p={predictor_delta_load:.10f}`，预测点 `({v06.predictor_q[0]:.10f},{v06.predictor_load_factor:.10f})`，预测残量 `{predictor_residual:.10f}`。",
            "",
            "校正时求解以下增广 Newton 系统：",
            "",
            "$$",
            "\\begin{bmatrix}",
            "1-3q^2&-1\\\\",
            "2(q-0.5)&2(\\lambda-0.375)",
            "\\end{bmatrix}",
            "\\begin{bmatrix}\\delta q\\\\\\delta\\lambda\\end{bmatrix}",
            "=-\\begin{bmatrix}",
            "q-q^3-\\lambda\\\\",
            "(q-0.5)^2+(\\lambda-0.375)^2-0.01",
            "\\end{bmatrix}.",
            "$$",
            "",
            f"经 {v06.iterations} 次校正得到 `({v06.q[0]:.10f},{v06.load_factor:.10f})`，平衡残量 `{v06.residual_norm:.3e}`、弧长约束误差 `{v06.constraint_error:.3e}`。理论极限点为 `({theoretical_q:.10f},{theoretical_load:.10f})`，新点已进入载荷下降段。",
            "",
        ]
    )

    v07 = branch_switching_seed([1.0, 0.0], [1.0, 1.0])
    _close(v07.seed, [0.0, -1.0])
    results["V07"] = {"status": "PASS", "gamma": v07.gamma, "seed": v07.seed.tolist(), "orthogonality_error": v07.orthogonality_error}
    sections.extend(
        [
            "## V07 单模态分支切换种子 — PASS",
            "",
            f"`gamma={v07.gamma:.1f}`，种子 `({v07.seed[0]:.1f},{v07.seed[1]:.1f})`，正交误差 `{v07.orthogonality_error:.1e}`。它仍不是已收敛分支，还需要全阶平衡校正、分支身份约束以及种子/反向/网格复核。",
            "",
        ]
    )

    v08 = cylinder_axial_buckling(70000.0, 0.33, 500.0, 1.0, 1000.0)
    _close([v08.critical_stress_mpa, v08.total_critical_load_kn], [85.625710, 269.001102], atol=1e-6)
    results["V08"] = {"status": "PASS", "critical_stress_mpa": v08.critical_stress_mpa, "membrane_force_n_per_mm": v08.critical_membrane_force_n_per_mm, "total_load_kn": v08.total_critical_load_kn, "alpha_per_mm": v08.alpha_per_mm, "full_wavelength_mm": v08.full_wavelength_mm, "half_wave_count": v08.half_wave_count}
    sections.extend(
        [
            "## V08 轴压圆柱壳解析基准 — PASS",
            "",
            f"`sigma_cr={v08.critical_stress_mpa:.6f} MPa`，`N_cr={v08.critical_membrane_force_n_per_mm:.6f} N/mm`，`P_cr={v08.total_critical_load_kn:.6f} kN`；`alpha={v08.alpha_per_mm:.8f} 1/mm`，全波长 `{v08.full_wavelength_mm:.4f} mm`，半波数 `{v08.half_wave_count:.3f}`。网格应从每半波约 6–10 个低阶单元起步并继续做收敛检查。",
            "",
        ]
    )

    v09 = sphere_external_pressure(70000.0, 0.33, 500.0, 1.0)
    _close([v09.critical_pressure_mpa, v09.critical_membrane_force_n_per_mm], [0.34250284, 85.625710], atol=1e-7)
    _close(v09.critical_membrane_force_n_per_mm, v08.critical_membrane_force_n_per_mm, atol=1e-12)
    results["V09"] = {"status": "PASS", "critical_pressure_mpa": v09.critical_pressure_mpa, "membrane_force_n_per_mm": v09.critical_membrane_force_n_per_mm, "same_ideal_membrane_scale_as_v08": True}
    sections.extend(
        [
            "## V09 完整球壳外压解析基准 — PASS",
            "",
            f"`p_cr={v09.critical_pressure_mpa:.8f} MPa`，`N={v09.critical_membrane_force_n_per_mm:.6f} N/mm`，与 V08 的理想膜力尺度相等。该等式不能推出两类真实壳体具有相同工程承载力。",
            "",
        ]
    )

    v10 = audit_research_evidence({})
    if v10.complete or len(v10.missing_categories) != 8:
        raise AssertionError("V10 应识别出八类缺失证据")
    results["V10"] = {
        "status": "PASS",
        "audit_logic_status": "PASS",
        "subject_report_status": "FAIL",
        "given_report_reaches_gate": v10.complete,
        "missing_categories": list(v10.missing_categories),
        "missing_requirements": list(v10.missing_requirements),
        "requirements": EVIDENCE_REQUIREMENTS,
    }
    sections.extend(
        [
            "## V10 端到端壳体失稳研究审查 — 审查逻辑 PASS；题干报告 FAIL",
            "",
            "题干报告八类证据全部不足，因此 `1.00/0.72 + 平滑曲线` 不能支持可靠极限载荷结论。必须补齐：",
            "",
        ]
    )
    for category, requirements in EVIDENCE_REQUIREMENTS.items():
        sections.append(f"- `{category}`：{'；'.join(requirements.values())}。")
    sections.extend(
        [
            "",
            "## 汇总",
            "",
            "| 题目 | 数学/审查逻辑 | 被审查对象 |",
            "|---|---|---|",
        ]
    )
    for test_id in results:
        subject_status = "FAIL" if test_id == "V10" else "—"
        sections.append(
            f"| {test_id} | {results[test_id]['status']} | {subject_status} |"
        )
    sections.extend(
        [
            "",
            "结论：V00–V09 的低维数值/解析验收全部通过；V10 审查逻辑正确拒绝了证据不足的题干报告。当前实现的结论层级仍是算法单元验证与 L1 解析基准，不能外推为具体壳体的 GNIA/GMNIA 承载力。",
            "",
        ]
    )
    return results, "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="演算结果目录",
    )
    arguments = parser.parse_args()
    results, markdown = calculate()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = arguments.output_dir / "V00-V10_演算结果.md"
    json_path = arguments.output_dir / "V00-V10_演算结果.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"PASS: {len(results)}/11 validation problems")
    print(markdown_path)
    print(json_path)


if __name__ == "__main__":
    main()
