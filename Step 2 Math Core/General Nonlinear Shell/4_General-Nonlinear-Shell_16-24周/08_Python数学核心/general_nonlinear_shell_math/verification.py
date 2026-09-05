"""Executable V00-V14 calculations, checks, and evidence boundaries."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .benchmarks import pure_bending_strip
from .constants import REPORT_SCHEMA_VERSION, VERSION
from .continuation import solve_scalar_arc_length_step
from .kinematics import (
    green_lagrange_strain,
    infinitesimal_strain_from_deformation_gradient,
    push_forward_second_piola,
    q4_center_shell_kinematics,
)
from .loads import follower_line_force, follower_line_tangent
from .materials import BilinearIsotropic1D, MaterialState1D
from .rotations import axis_angle_rotation, rotation_metrics, so3_exp
from .section import condense_plane_stress, integrate_linear_elastic_bending
from .state import CommittedShellState, StateTransaction
from .tangent import (
    directional_derivative_scan,
    polynomial_internal_minus_external_residual,
    polynomial_tangent,
)

VERIFIED = "VERIFIED"
PARTIAL = "PARTIAL"
REFERENCE_ONLY = "REFERENCE_ONLY"
NOT_RUN = "NOT_RUN"
AUDIT_RESULT = "AUDIT_RESULT"
FAILED = "FAILED"


STAGE_GATE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "G0": {
        "name": "有限转动壳运动学",
        "checks": ("V00", "V01", "V02", "V03"),
        "external": (),
    },
    "G1": {
        "name": "弹性壳残量/切线",
        "checks": ("V04", "V06", "V08"),
        "external": ("真实壳单元全切线方向差分",),
    },
    "G2": {
        "name": "随动力分析",
        "checks": ("V05",),
        "external": ("真实受载壳面网格方向差分",),
    },
    "G3": {
        "name": "材料非线性壳",
        "checks": ("V07", "V08", "V12"),
        "external": ("真实壳截面厚度积分点收敛",),
    },
    "G4": {
        "name": "薄壳与曲壳单元",
        "checks": ("V01", "V04", "V09", "V10"),
        "external": (),
    },
    "G5": {
        "name": "snap-through/后屈曲",
        "checks": ("V04", "V05", "V10", "V11", "V12"),
        "external": (),
    },
    "G6": {
        "name": "系统参考解",
        "checks": ("V13",),
        "external": ("保存数字化来源和误差定义",),
    },
    "G7": {
        "name": "GNIA/GMNIA 结论",
        "checks": tuple(f"V{index:02d}" for index in range(15)),
        "external": ("真实模型网格/步长/缺陷/边界/材料敏感性矩阵",),
    },
}


@dataclass(frozen=True)
class VerificationRecord:
    test_id: str
    title: str
    status: str
    verified_scope: str
    individual_check_complete: bool
    computed: dict[str, Any]
    acceptance: str
    limitations: tuple[str, ...] = ()


def _plain(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _executed_status(passed: bool, success_status: str) -> str:
    """Distinguish an executed failure from a deliberately unexecuted check."""

    return success_status if passed else FAILED


def _runtime_metadata() -> dict[str, Any]:
    numpy_config = getattr(np.__config__, "CONFIG", {})
    build_dependencies = (
        numpy_config.get("Build Dependencies", {})
        if isinstance(numpy_config, dict)
        else {}
    )
    blas = (
        build_dependencies.get("blas", {})
        if isinstance(build_dependencies, dict)
        else {}
    )
    blas_name = (
        blas.get("name", "unavailable") if isinstance(blas, dict) else "unavailable"
    )
    return {
        "math_core_version": VERSION,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "numpy_version": np.__version__,
        "linear_algebra_api": "numpy.linalg",
        "blas_backend": blas_name,
        "platform": platform.platform(),
        "source_revision": "unavailable: workspace is not a Git checkout",
    }


def _record_v00() -> VerificationRecord:
    director_0 = np.array([1.0, 0.0, 0.0])
    increment = np.array([0.0, 0.0, np.pi / 2.0])
    rotation = so3_exp(increment)
    director_1 = rotation @ director_0
    metrics = rotation_metrics(rotation)
    additive = director_0 + np.cross(increment, director_0)
    passed = (
        np.allclose(director_1, [0.0, 1.0, 0.0], rtol=0.0, atol=1.0e-14)
        and metrics.orthogonality_error < 1.0e-14
        and abs(metrics.determinant - 1.0) < 1.0e-14
        and abs(np.linalg.norm(director_1) - 1.0) < 1.0e-14
    )
    return VerificationRecord(
        test_id="V00",
        title="SO(3) 指数更新",
        status=_executed_status(passed, VERIFIED),
        verified_scope="数学单元：空间增量左乘、Rodrigues 公式与小角度稳定分支",
        individual_check_complete=passed,
        computed={
            "rotation": rotation,
            "director_1": director_1,
            "orthogonality_error": metrics.orthogonality_error,
            "determinant": metrics.determinant,
            "director_norm": np.linalg.norm(director_1),
            "additive_update": additive,
            "additive_update_norm": np.linalg.norm(additive),
        },
        acceptance="d1=(0,1,0)，R^T R=I，detR=1，||d1||=1。",
    )


def _record_v01() -> VerificationRecord:
    reference_nodes = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
    )
    reference_directors = np.tile([0.0, 0.0, 1.0], (4, 1))
    rotation = axis_angle_rotation([0.0, 0.0, 1.0], 2.0 * np.pi / 3.0)
    translation = np.array([3.0, -2.0, 5.0])
    current_nodes = (rotation @ reference_nodes.T).T + translation
    current_directors = (rotation @ reference_directors.T).T
    response = q4_center_shell_kinematics(
        reference_nodes,
        current_nodes,
        reference_directors,
        current_directors,
    )
    strain_norm = float(np.linalg.norm(response.green_lagrange))
    passed = (
        np.allclose(response.deformation_gradient, rotation, rtol=0.0, atol=2.0e-15)
        and strain_norm < 1.0e-14
        and np.linalg.norm(response.membrane_strain) < 1.0e-14
        and np.linalg.norm(response.transverse_shear_strain) < 1.0e-14
        and abs(response.deformation_jacobian - 1.0) < 1.0e-14
        and response.reference_signed_area_jacobian > 0.0
        and response.current_signed_area_jacobian > 0.0
        and response.director_norm_error < 1.0e-14
        and response.director_gradient_change_norm < 1.0e-14
    )
    return VerificationRecord(
        test_id="V01",
        title="有限刚体运动零应变",
        status=_executed_status(passed, PARTIAL),
        verified_scope="Q4 中心点退化壳运动学与客观应变诊断",
        individual_check_complete=False,
        computed={
            "deformation_gradient": response.deformation_gradient,
            "green_lagrange_norm": strain_norm,
            "membrane_strain": response.membrane_strain,
            "transverse_shear_strain": response.transverse_shear_strain,
            "thickness_strain": response.thickness_strain,
            "deformation_jacobian": response.deformation_jacobian,
            "reference_signed_area_jacobian": response.reference_signed_area_jacobian,
            "current_signed_area_jacobian": response.current_signed_area_jacobian,
            "director_norm_error": response.director_norm_error,
            "director_interpolation_norm_before_normalisation": (
                response.director_interpolation_norm_before_normalisation
            ),
            "director_gradient_change_norm": response.director_gradient_change_norm,
            "area_jacobian_ratio": response.current_area_jacobian
            / response.reference_area_jacobian,
        },
        acceptance="运动学量达到舍入误差级。",
        limitations=(
            "尚无真实壳单元内力、弯曲能与应变能计算，因此 V01 壳单元门槛只完成运动学部分。",
        ),
    )


def _record_v02() -> VerificationRecord:
    rotation = axis_angle_rotation([0.0, 0.0, 1.0], np.pi / 2.0)
    green = green_lagrange_strain(rotation)
    small = infinitesimal_strain_from_deformation_gradient(rotation)
    passed = np.linalg.norm(green) < 1.0e-14 and np.allclose(
        small,
        np.diag([-1.0, -1.0, 0.0]),
        rtol=0.0,
        atol=1.0e-14,
    )
    return VerificationRecord(
        test_id="V02",
        title="小应变为何不客观",
        status=_executed_status(passed, VERIFIED),
        verified_scope="连续体运动学",
        individual_check_complete=passed,
        computed={"green_lagrange": green, "small_strain": small},
        acceptance="E=0；小应变=diag(-1,-1,0)。",
    )


def _record_v03() -> VerificationRecord:
    deformation = np.diag([1.2, 0.9, 1.0])
    second_piola = np.diag([100.0, 50.0, 0.0])
    cauchy = push_forward_second_piola(deformation, second_piola)
    jacobian = float(np.linalg.det(deformation))
    passed = abs(jacobian - 1.08) < 1.0e-14 and np.allclose(
        cauchy,
        np.diag([133.33333333333334, 37.5, 0.0]),
        rtol=0.0,
        atol=1.0e-12,
    )
    return VerificationRecord(
        test_id="V03",
        title="TL/UL 应力转换",
        status=_executed_status(passed, VERIFIED),
        verified_scope="功共轭构形转换",
        individual_check_complete=passed,
        computed={"J": jacobian, "cauchy_stress_MPa": cauchy},
        acceptance="J=1.08；sigma=diag(133.333333,37.5,0) MPa。",
    )


def _record_v04() -> VerificationRecord:
    point = np.array([0.2, -0.1])
    direction = np.array([0.3, -0.4])
    tangent = polynomial_tangent(point)
    analytic = tangent @ direction
    load_factor = 0.1
    samples = directional_derivative_scan(
        lambda q: -polynomial_internal_minus_external_residual(q, load_factor),
        tangent,
        point,
        direction,
        [10.0 ** (-power) for power in range(2, 9)],
        residual_sign=-1.0,
    )
    errors = np.array([sample.relative_error for sample in samples])
    passed = (
        np.allclose(analytic, [0.202, -0.744], rtol=0.0, atol=1.0e-14)
        and errors[1] < errors[0] / 50.0
        and float(np.min(errors)) < 1.0e-10
    )
    return VerificationRecord(
        test_id="V04",
        title="总切线方向差分",
        status=_executed_status(passed, PARTIAL),
        verified_scope="代数残量、规范负号和多步长中心差分",
        individual_check_complete=False,
        computed={
            "tangent": tangent,
            "K_times_p": analytic,
            "scan": [
                {
                    "h": sample.step,
                    "finite_difference": sample.finite_difference,
                    "relative_error": sample.relative_error,
                }
                for sample in samples
            ],
            "minimum_relative_error": float(np.min(errors)),
        },
        acceptance="Kp=(0.202,-0.744)，中心差分出现二阶区和舍入误差谷值。",
        limitations=(
            "这只验证代数基准；真实壳单元仍须把材料、几何、旋转、稳定化和外载切线放入同一次差分。",
        ),
    )


def _record_v05() -> VerificationRecord:
    x1 = np.array([0.0, 0.0])
    x2 = np.array([2.0, 0.0])
    force = follower_line_force(x1, x2, 3.0)
    tangent = follower_line_tangent(3.0)
    derivative_x2_y = tangent[:, 3]
    epsilon = 1.0e-7
    finite_difference = (
        follower_line_force(x1, x2 + [0.0, epsilon], 3.0)
        - follower_line_force(x1, x2 - [0.0, epsilon], 3.0)
    ) / (2.0 * epsilon)
    passed = (
        np.allclose(force, [0.0, 3.0, 0.0, 3.0], rtol=0.0, atol=1.0e-14)
        and np.allclose(
            derivative_x2_y,
            [-1.5, 0.0, -1.5, 0.0],
            rtol=0.0,
            atol=1.0e-14,
        )
        and np.allclose(finite_difference, derivative_x2_y, rtol=0.0, atol=1.0e-10)
    )
    return VerificationRecord(
        test_id="V05",
        title="二维随形压力载荷切线",
        status=_executed_status(passed, PARTIAL),
        verified_scope="两节点受压线的位形相关外力和非对称导数",
        individual_check_complete=False,
        computed={
            "nodal_force": force,
            "load_tangent": tangent,
            "derivative_wrt_x2_y": derivative_x2_y,
            "central_difference": finite_difference,
            "is_symmetric": bool(np.allclose(tangent, tangent.T)),
        },
        acceptance="每节点力=(0,3)，对 x2_y 的导数=(-1.5,0)。",
        limitations=("V05 完整门槛还需要真实受载壳面及其旋转/面积线性化。",),
    )


def _record_v06() -> VerificationRecord:
    two_point = integrate_linear_elastic_bending(
        elastic_modulus=210000.0,
        thickness=2.0,
        curvature=0.001,
        gauss_points=2,
    )
    one_point = integrate_linear_elastic_bending(
        elastic_modulus=210000.0,
        thickness=2.0,
        curvature=0.001,
        gauss_points=1,
    )
    passed = (
        abs(two_point.surface_stress_top - 210.0) < 1.0e-12
        and abs(two_point.surface_stress_bottom + 210.0) < 1.0e-12
        and abs(two_point.membrane_force) < 1.0e-12
        and abs(two_point.bending_moment - 140.0) < 1.0e-12
        and abs(one_point.bending_moment) < 1.0e-12
    )
    return VerificationRecord(
        test_id="V06",
        title="线弹性纯弯曲厚度积分",
        status=_executed_status(passed, VERIFIED),
        verified_scope="单位宽度截面 Gauss 厚度积分",
        individual_check_complete=passed,
        computed={
            "surface_stress_bottom_MPa": two_point.surface_stress_bottom,
            "surface_stress_top_MPa": two_point.surface_stress_top,
            "membrane_force_N_per_mm": two_point.membrane_force,
            "bending_moment_N": two_point.bending_moment,
            "strain_energy_N_per_mm": two_point.strain_energy_per_area,
            "one_point_bending_moment_N": one_point.bending_moment,
        },
        acceptance="表面应力 ±210 MPa，N=0，M=140 N；两点精确而一点失败。",
    )


def _record_v07() -> VerificationRecord:
    material = BilinearIsotropic1D(200000.0, 1000.0, 250.0)
    committed = MaterialState1D()
    response = material.evaluate(0.002, committed)
    passed = (
        abs(response.trial_stress - 400.0) < 1.0e-12
        and abs(response.plastic_multiplier - 0.0007462686567164179) < 1.0e-15
        and abs(response.stress - 250.7462686567164) < 1.0e-10
        and abs(response.algorithmic_tangent - 995.0248756218906) < 1.0e-10
        and committed == MaterialState1D()
    )
    return VerificationRecord(
        test_id="V07",
        title="一维弹塑性材料点",
        status=_executed_status(passed, VERIFIED),
        verified_scope="双线性各向同性硬化返回映射与不可变 committed 状态",
        individual_check_complete=passed,
        computed={
            "trial_stress_MPa": response.trial_stress,
            "plastic_multiplier": response.plastic_multiplier,
            "updated_stress_MPa": response.stress,
            "plastic_strain": response.trial_state.plastic_strain,
            "algorithmic_tangent_MPa": response.algorithmic_tangent,
            "committed_unchanged": committed == MaterialState1D(),
        },
        acceptance="sigma=250.746269 MPa；Calg=995.024876 MPa；试算不污染 committed。",
    )


def _record_v08() -> VerificationRecord:
    condensed = condense_plane_stress([[100.0]], [[20.0]], [[20.0]], [[50.0]])
    correct = float(condensed[0, 0])
    overestimate_percent = (100.0 / correct - 1.0) * 100.0
    passed = abs(correct - 92.0) < 1.0e-14
    return VerificationRecord(
        test_id="V08",
        title="平面应力静力凝聚",
        status=_executed_status(passed, VERIFIED),
        verified_scope="一致切线 Schur 补",
        individual_check_complete=passed,
        computed={
            "condensed_tangent": correct,
            "incorrect_deleted_value": 100.0,
            "overestimate_percent_relative_to_correct": overestimate_percent,
        },
        acceptance="凝聚切线=92；直接删除厚度分量会得到错误的 100。",
    )


def _record_v09() -> VerificationRecord:
    return VerificationRecord(
        test_id="V09",
        title="薄壳锁死与稳定化扫描",
        status=NOT_RUN,
        verified_scope="验证规格已路由，未执行壳单元扫描",
        individual_check_complete=False,
        computed={
            "required_thickness_ratios": [1.0e-1, 1.0e-2, 1.0e-3, 1.0e-4],
            "required_meshes": ["regular", "distorted"],
            "required_formulations": ["full_integration", "MITC_or_assumed_strain"],
            "required_metrics": [
                "normalised displacement or energy error",
                "membrane bending shear and stabilisation energy ratios",
                "smallest non-rigid eigenvalue and zero-mode count",
                "mesh and thickness-limit convergence",
            ],
        },
        acceptance="只有实际低阶壳单元、网格与稳定化参数扫描后才能通过。",
        limitations=("当前目录没有可运行的非线性壳单元实现或题目输入网格。",),
    )


def _record_v10() -> VerificationRecord:
    length = 10.0
    bending_stiffness = 2.0
    result = pure_bending_strip(length=length, bending_stiffness=bending_stiffness)
    passed = (
        abs(result.end_rotation - np.pi) < 1.0e-14
        and abs(result.end_x) < 1.0e-14
        and abs(result.end_y - 2.0 * length / np.pi) < 1.0e-14
        and abs(result.strain_energy - np.pi**2 * bending_stiffness / (2.0 * length))
        < 1.0e-14
    )
    return VerificationRecord(
        test_id="V10",
        title="大转动纯弯曲条带",
        status=_executed_status(passed, REFERENCE_ONLY),
        verified_scope="Euler-Bernoulli 极限的解析参考值",
        individual_check_complete=False,
        computed={
            "chosen_length": length,
            "chosen_EI": bending_stiffness,
            "curvature": result.curvature,
            "end_rotation": result.end_rotation,
            "end_point": [result.end_x, result.end_y],
            "strain_energy": result.strain_energy,
        },
        acceptance="解析值 theta=pi，端点=(0,2L/pi)，U=pi^2 EI/(2L)。",
        limitations=("尚未把该参考值施加到真实 Reissner-Mindlin 壳条带。",),
    )


def _record_v11() -> VerificationRecord:
    result = solve_scalar_arc_length_step(
        q_n=0.5,
        load_factor_n=0.375,
        arc_length=0.1,
        beta=1.0,
        reference_load=1.0,
    )
    limit_q = float(1.0 / np.sqrt(3.0))
    limit_load = float(2.0 / (3.0 * np.sqrt(3.0)))
    passed = (
        result.converged
        and abs(result.predictor_q - 0.5970142500145332) < 1.0e-12
        and abs(result.predictor_load_factor - 0.3992535625036333) < 1.0e-12
        and abs(result.q - 0.599591243412322) < 1.0e-10
        and abs(result.load_factor - 0.384032399860422) < 1.0e-10
    )
    return VerificationRecord(
        test_id="V11",
        title="球形弧长跨越极限点",
        status=_executed_status(passed, VERIFIED),
        verified_scope="一自由度球形弧长预测-校正",
        individual_check_complete=passed,
        computed={
            "predictor": [result.predictor_q, result.predictor_load_factor],
            "corrected": [result.q, result.load_factor],
            "theoretical_limit_point": [limit_q, limit_load],
            "crossed_limit_point": result.q > limit_q
            and result.load_factor < limit_load,
            "iterations": len(result.iterations),
            "final_equilibrium_residual": result.q - result.q**3 - result.load_factor,
            "final_arc_length_residual": (result.q - 0.5) ** 2
            + (result.load_factor - 0.375) ** 2
            - 0.01,
        },
        acceptance="校正交点约为 (0.5995912434,0.3840323999)，位于理论极限点后段。",
    )


def _deterministic_retry_history(transaction: StateTransaction) -> list[dict[str, Any]]:
    """Replay deterministic trial iterations from the immutable committed base."""

    history: list[dict[str, Any]] = []
    for iteration, correction in enumerate((0.08, 0.02, 0.005), start=1):
        trial = transaction.rollback()
        trial.load_factor = transaction.committed.load_factor + correction
        trial.thickness = transaction.committed.thickness - 0.1 * correction
        trial.plastic_strain = [
            value + correction * (index + 1) * 1.0e-3
            for index, value in enumerate(transaction.committed.plastic_strain)
        ]
        trial.hardening = [
            value + correction * (index + 1)
            for index, value in enumerate(transaction.committed.hardening)
        ]
        trial.plane_stress_unknowns = [
            value - correction * (index + 1) * 1.0e-4
            for index, value in enumerate(transaction.committed.plane_stress_unknowns)
        ]
        trial.trial_stress = [250.0 + 10.0 * iteration, 255.0 + 10.0 * iteration]
        trial.local_plastic_multiplier = [correction * 1.0e-3, correction * 2.0e-3]
        trial.local_newton_initial_guess = list(trial.plane_stress_unknowns)
        trial.director_normalization_cache = list(trial.director)
        trial.current_local_basis_cache = [list(row) for row in trial.local_basis]
        trial.trial_energy_increment = correction**2
        history.append(
            {
                "iteration": iteration,
                "committed_sha256": transaction.committed.sha256(),
                "load_factor": trial.load_factor,
                "thickness": trial.thickness,
                "plastic_strain": list(trial.plastic_strain),
                "hardening": list(trial.hardening),
                "plane_stress_unknowns": list(trial.plane_stress_unknowns),
                "trial_stress": list(trial.trial_stress),
                "plastic_multiplier": list(trial.local_plastic_multiplier),
                "trial_energy_increment": trial.trial_energy_increment,
            }
        )
    return history


def _record_v12() -> VerificationRecord:
    committed = CommittedShellState.create(
        load_factor=1.0,
        rotation=np.eye(3),
        director=[0.0, 0.0, 1.0],
        nodal_coordinates=[[0.0, 0.0, 0.0]],
        thickness=2.0,
        plastic_strain=[0.001, 0.002],
        hardening=[10.0, 20.0],
        plane_stress_unknowns=[0.0, 0.0],
        local_basis=np.eye(3),
        stabilization_history=[0.0, 0.0],
        energy_accumulator=0.0,
        active_flags=[False, False],
    )
    before_hash = committed.sha256()
    transaction = StateTransaction(committed)
    transaction.trial.load_factor = 1.2
    transaction.trial.rotation[0][0] = 0.5
    transaction.trial.director[:] = [1.0, 0.0, 0.0]
    transaction.trial.nodal_coordinates[0][2] = 0.25
    transaction.trial.thickness = 1.85
    transaction.trial.plastic_strain[0] = 0.015
    transaction.trial.hardening[1] = 90.0
    transaction.trial.plane_stress_unknowns[:] = [-0.02, -0.03]
    transaction.trial.local_basis[0][1] = 0.1
    transaction.trial.stabilization_history[:] = [1.0, 2.0]
    transaction.trial.energy_accumulator = 12.5
    transaction.trial.active_flags[:] = [True, True]
    transaction.trial.trial_stress[:] = [300.0, 400.0]
    transaction.trial.local_plastic_multiplier[:] = [0.01, 0.02]
    transaction.trial.local_newton_initial_guess[:] = [-0.02, -0.03]
    transaction.trial.director_normalization_cache[:] = [1.0, 0.0, 0.0]
    transaction.trial.current_local_basis_cache[:] = [[1.0, 0.1, 0.0]]
    transaction.trial.trial_energy_increment = 3.5
    unchanged_during_trial = transaction.committed.sha256() == before_hash
    restored_trial = transaction.rollback()
    trial_caches_cleared = (
        restored_trial.trial_stress == [0.0, 0.0]
        and restored_trial.local_plastic_multiplier == [0.0, 0.0]
        and restored_trial.local_newton_initial_guess == [0.0, 0.0]
        and restored_trial.director_normalization_cache == []
        and restored_trial.current_local_basis_cache == []
        and restored_trial.trial_energy_increment == 0.0
    )
    after_hash = transaction.committed.sha256()
    retry_state = restored_trial.commit()
    rollback_retry_history = _deterministic_retry_history(transaction)
    clean_retry_history = _deterministic_retry_history(StateTransaction(committed))
    histories_match = rollback_retry_history == clean_retry_history
    passed = (
        unchanged_during_trial
        and after_hash == before_hash
        and retry_state.sha256() == before_hash
        and trial_caches_cleared
        and histories_match
    )
    return VerificationRecord(
        test_id="V12",
        title="失败步回滚",
        status=_executed_status(passed, VERIFIED),
        verified_scope="完整 L0 状态快照、trial 缓存清理和干净重试历史对比",
        individual_check_complete=passed,
        computed={
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "retry_sha256": retry_state.sha256(),
            "committed_unchanged_during_trial": unchanged_during_trial,
            "trial_caches_cleared": trial_caches_cleared,
            "clean_restart_history_matches": histories_match,
            "retry_history": rollback_retry_history,
            "restored_state": retry_state.canonical_payload(),
        },
        acceptance="强制污染全部 trial 字段后，快照哈希、缓存清理和干净重试历史完全一致。",
        limitations=(
            "该题的 L0 事务已完成；接入真实壳求解器后仍需用真实全局迭代重复同一验收。",
        ),
    )


def _record_v13() -> VerificationRecord:
    return VerificationRecord(
        test_id="V13",
        title="大变形弹塑性方板系统基准",
        status=NOT_RUN,
        verified_scope="输入规格已提取，系统演算未执行",
        individual_check_complete=False,
        computed={
            "geometry_mm": [1000.0, 1000.0, 1.0],
            "material_MPa": {"E": 200000.0, "E_T": 2000.0, "sigma_y": 200.0, "nu": 0.3},
            "missing_evidence": [
                "selected nonlinear MITC shell element",
                "unambiguous simply-supported constraints and mesh",
                "local plane-stress/thickness update",
                "digitised reference curves from source page 311",
                "mesh, thickness-point, step and tolerance convergence",
                "surface and midsurface effective-stress comparison",
            ],
        },
        acceptance="必须完成参考曲线数字化和真实壳系统收敛研究；不得用曲线形状相似替代。",
        limitations=("资料明确说明原书只有图形曲线，没有可直接读取的完整数值表。",),
    )


def _record_v14() -> VerificationRecord:
    categories = [
        "运动学、有限转动和客观性 V00-V03",
        "残量以及材料/几何/旋转/稳定化/外载完整切线 V04-V05",
        "厚度积分、平面应力、材料返回与回滚 V06-V08/V12",
        "dead/follower 载荷定义、受载区、边界刚度与反力平衡",
        "锁死、稳定化、网格、畸变与零能模态 V09",
        "弧长尺度、根选择、临界点分类、分支身份 V10-V11",
        "多缺陷形状/符号/幅值、残余应力、材料和边界敏感性",
        "版本化输入、日志、文献/实验对照以及 GNIA/GMNIA 结论边界",
    ]
    return VerificationRecord(
        test_id="V14",
        title="GMNIA 证据审查",
        status=AUDIT_RESULT,
        verified_scope="对题设报告的证据充分性审查",
        individual_check_complete=True,
        computed={
            "claim_accepted": False,
            "missing_evidence_categories": categories,
            "verdict": "0.72 只能是待复核的单次模型输出，不能据此证明通用非线性壳实现正确或作为可靠承载力。",
        },
        acceptance="正确审查结果是拒绝现有结论，并补齐八类证据。",
        limitations=("本记录完成的是证据审查，不是 GMNIA 数值验证。",),
    )


def run_all_verifications() -> list[VerificationRecord]:
    """Run every calculation that the source folder makes honestly executable."""

    builders = [
        _record_v00,
        _record_v01,
        _record_v02,
        _record_v03,
        _record_v04,
        _record_v05,
        _record_v06,
        _record_v07,
        _record_v08,
        _record_v09,
        _record_v10,
        _record_v11,
        _record_v12,
        _record_v13,
        _record_v14,
    ]
    return [builder() for builder in builders]


def _summary(records: list[VerificationRecord]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.status] = counts.get(record.status, 0) + 1
    records_by_id = {record.test_id: record for record in records}
    stage_gates: dict[str, Any] = {}
    for gate_id, requirement in STAGE_GATE_REQUIREMENTS.items():
        incomplete_checks = [
            test_id
            for test_id in requirement["checks"]
            if not records_by_id[test_id].individual_check_complete
        ]
        unmet_external = list(requirement["external"])
        passed = not incomplete_checks and not unmet_external
        stage_gates[gate_id] = {
            "name": requirement["name"],
            "status": "PASSED" if passed else "NOT_PASSED",
            "required_checks": list(requirement["checks"]),
            "incomplete_checks": incomplete_checks,
            "unmet_external_requirements": unmet_external,
        }
    return {
        "status_counts": counts,
        "completed_individual_checks": [
            record.test_id for record in records if record.individual_check_complete
        ],
        "passed_stage_gates": [
            gate_id
            for gate_id, result in stage_gates.items()
            if result["status"] == "PASSED"
        ],
        "stage_gates": stage_gates,
        "not_run": [record.test_id for record in records if record.status == NOT_RUN],
        "failed": [record.test_id for record in records if record.status == FAILED],
        "scope_statement": (
            "This is a verification-oriented L0 math core. It is not a production nonlinear shell element, "
            "a V13 system solver, or a GMNIA design implementation."
        ),
    }


def write_reports(output_directory: Path) -> tuple[Path, Path]:
    records = run_all_verifications()
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "V00-V14_演算结果.json"
    markdown_path = output_directory / "V00-V14_演算报告.md"
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "residual_convention": "r = f_ext - f_int",
        "tangent_convention": "K_t = d(f_int)/dq - d(f_ext)/dq",
        "rotation_increment": "spatial increment, left multiplication",
        "runtime": _runtime_metadata(),
        "summary": _summary(records),
        "records": [_plain(asdict(record)) for record in records],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# V00-V14 Python 演算报告",
        "",
        "## 约定与结论",
        "",
        "- 残量：`r = f_ext - f_int`。",
        "- 切线：`K_t = ∂f_int/∂q - ∂f_ext/∂q`。",
        "- 旋转：空间增量左乘 `R_new = exp([Δθ]x) R_old`。",
        "- 本实现是可验证的 L0 数学核心；没有把解析答案冒充真实非线性壳单元或 GMNIA 结果。",
        "",
        "## 总览",
        "",
        "| ID | 状态 | 本次完成范围 | 本题完整验算 |",
        "|---|---|---|---|",
    ]
    for record in records:
        complete = "是" if record.individual_check_complete else "否"
        lines.append(
            f"| {record.test_id} | {record.status} | {record.verified_scope} | {complete} |"
        )
    summary = _summary(records)
    lines.extend(
        [
            "",
            "## 阶段闸门 G0-G7",
            "",
            "| Gate | 目标 | 状态 | 未完成 V 题 | 外部证据缺口 |",
            "|---|---|---|---|---|",
        ]
    )
    for gate_id, result in summary["stage_gates"].items():
        incomplete = ", ".join(result["incomplete_checks"]) or "无"
        external = "；".join(result["unmet_external_requirements"]) or "无"
        lines.append(
            f"| {gate_id} | {result['name']} | {result['status']} | {incomplete} | {external} |"
        )
    runtime = _runtime_metadata()
    lines.extend(
        [
            "",
            "## 运行环境",
            "",
            f"- 数学核心版本：`{runtime['math_core_version']}`；报告模式：`{REPORT_SCHEMA_VERSION}`。",
            f"- Python：`{runtime['python_version']}`（`{runtime['python_implementation']}`）。",
            f"- NumPy：`{runtime['numpy_version']}`；线性代数：`{runtime['linear_algebra_api']}`；BLAS：`{runtime['blas_backend']}`。",
            f"- 解释器：`{runtime['python_executable']}`。",
            f"- 平台：`{runtime['platform']}`。",
        ]
    )
    lines.extend(["", "## 分题结果", ""])
    for record in records:
        lines.extend(
            [
                f"### {record.test_id} {record.title}",
                "",
                f"状态：`{record.status}`。{record.acceptance}",
                "",
                "```json",
                json.dumps(_plain(record.computed), ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
        if record.limitations:
            lines.append("边界：" + "；".join(record.limitations))
            lines.append("")
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts"),
        help="directory for JSON and Markdown reports (default: artifacts)",
    )
    arguments = parser.parse_args()
    json_path, markdown_path = write_reports(arguments.output)
    records = run_all_verifications()
    summary = _summary(records)
    print(json.dumps(_plain(summary), ensure_ascii=False, indent=2))
    print(f"JSON: {json_path.resolve()}")
    print(f"Markdown: {markdown_path.resolve()}")


if __name__ == "__main__":
    main()
