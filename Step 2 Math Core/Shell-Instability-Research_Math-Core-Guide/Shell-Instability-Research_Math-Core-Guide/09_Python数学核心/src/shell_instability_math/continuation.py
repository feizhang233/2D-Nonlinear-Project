"""球形弧长一步校正与单模态分支切换种子。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray


Vector = NDArray[np.float64]
Residual = Callable[[Vector, float], ArrayLike]
Tangent = Callable[[Vector, float], ArrayLike]


@dataclass(frozen=True)
class ArcLengthResult:
    q: Vector
    load_factor: float
    predictor_q: Vector
    predictor_load_factor: float
    iterations: int
    residual_norm: float
    constraint_error: float
    converged: bool


@dataclass(frozen=True)
class BranchSeed:
    gamma: float
    seed: Vector
    orthogonality_error: float


def _vector(values: ArrayLike, name: str) -> Vector:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} 必须是一维有限实数向量")
    return result


def spherical_arc_length_step(
    residual: Residual,
    tangent: Tangent,
    q_n: ArrayLike,
    load_factor_n: float,
    reference_load: ArrayLike,
    arc_length: float,
    *,
    beta: float = 1.0,
    direction_sign: float = 1.0,
    tolerance: float = 1.0e-12,
    max_iterations: int = 30,
) -> ArcLengthResult:
    """从已收敛点执行一个球形弧长预测-校正步。

    残量约定为 ``R(q,lambda)=f_int(q)-lambda*f_ref``，增广系统与资料包
    A01 第 5 节一致。这里不包含材料状态的 trial/commit/rollback；调用真实
    有历史变量的模型时必须在外层实现该状态契约。
    """

    q_previous = _vector(q_n, "q_n")
    f_ref = _vector(reference_load, "reference_load")
    if q_previous.shape != f_ref.shape:
        raise ValueError("q_n 与 reference_load 必须同维")
    if arc_length <= 0.0 or beta <= 0.0 or tolerance <= 0.0:
        raise ValueError("arc_length、beta、tolerance 必须为正")
    if max_iterations < 1:
        raise ValueError("max_iterations 必须至少为 1")

    tangent_previous = np.asarray(tangent(q_previous, load_factor_n), dtype=float)
    if tangent_previous.shape != (q_previous.size, q_previous.size):
        raise ValueError("tangent 返回的矩阵形状不正确")
    q_tangent = np.linalg.solve(tangent_previous, f_ref)
    weighted_load_norm = beta**2 * float(f_ref @ f_ref)
    delta_load_predictor = (
        np.copysign(1.0, direction_sign)
        * arc_length
        / np.sqrt(float(q_tangent @ q_tangent) + weighted_load_norm)
    )
    delta_q_predictor = delta_load_predictor * q_tangent
    predictor_q = q_previous + delta_q_predictor
    predictor_load = float(load_factor_n + delta_load_predictor)

    q = predictor_q.copy()
    load_factor = predictor_load
    residual_norm = float("inf")
    constraint_error = float("inf")
    for iteration in range(max_iterations + 1):
        equilibrium = _vector(residual(q, load_factor), "residual")
        delta_q = q - q_previous
        delta_load = load_factor - load_factor_n
        constraint = float(
            delta_q @ delta_q
            + weighted_load_norm * delta_load**2
            - arc_length**2
        )
        residual_norm = float(np.linalg.norm(equilibrium))
        constraint_error = abs(constraint)
        if residual_norm <= tolerance and constraint_error <= tolerance:
            return ArcLengthResult(
                q=q,
                load_factor=load_factor,
                predictor_q=predictor_q,
                predictor_load_factor=predictor_load,
                iterations=iteration,
                residual_norm=residual_norm,
                constraint_error=constraint_error,
                converged=True,
            )
        if iteration == max_iterations:
            break
        current_tangent = np.asarray(tangent(q, load_factor), dtype=float)
        augmented = np.block(
            [
                [current_tangent, -f_ref[:, None]],
                [
                    2.0 * delta_q[None, :],
                    np.asarray([[2.0 * weighted_load_norm * delta_load]]),
                ],
            ]
        )
        correction = np.linalg.solve(
            augmented, -np.concatenate([equilibrium, [constraint]])
        )
        q += correction[:-1]
        load_factor += float(correction[-1])

    return ArcLengthResult(
        q=q,
        load_factor=load_factor,
        predictor_q=predictor_q,
        predictor_load_factor=predictor_load,
        iterations=max_iterations,
        residual_norm=residual_norm,
        constraint_error=constraint_error,
        converged=False,
    )


def branch_switching_seed(
    basic_path_increment: ArrayLike,
    null_vector: ArrayLike,
    *,
    denominator_tolerance: float = 1.0e-14,
) -> BranchSeed:
    """构造与基本路径增量正交的单零模态搜索种子。"""

    increment = _vector(basic_path_increment, "basic_path_increment")
    mode = _vector(null_vector, "null_vector")
    if increment.shape != mode.shape:
        raise ValueError("基本路径增量与零向量必须同维")
    denominator = float(mode @ increment)
    scale = max(float(np.linalg.norm(mode) * np.linalg.norm(increment)), 1.0)
    if abs(denominator) <= denominator_tolerance * scale:
        raise ValueError("v.T@Deltaq 过小，应改用显式正交/幅值约束")
    gamma = -float(increment @ increment) / denominator
    seed = increment + gamma * mode
    return BranchSeed(
        gamma=gamma,
        seed=seed,
        orthogonality_error=abs(float(increment @ seed)),
    )

