"""切线稳定性、奇异点分类与模态相关性。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


Vector = NDArray[np.float64]
Matrix = NDArray[np.float64]


@dataclass(frozen=True)
class StabilityIndicators:
    symmetric: bool
    eigenvalues: Vector | None
    singular_values: Vector
    negative_count: int | None
    zero_count: int


@dataclass(frozen=True)
class SingularPointClassification:
    kind: str
    projection: float
    normalized_projection: float
    right_null_residual: float
    left_null_residual: float
    nullity: int
    smallest_relative_singular_value: float


def _matrix(values: ArrayLike, name: str) -> Matrix:
    result = np.asarray(values, dtype=float)
    if result.ndim != 2 or result.shape[0] != result.shape[1]:
        raise ValueError(f"{name} 必须是方阵")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} 必须只含有限实数")
    return result


def _vector(values: ArrayLike, name: str) -> Vector:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} 必须是一维有限实数向量")
    return result


def stability_indicators(
    tangent: ArrayLike,
    *,
    symmetry_tolerance: float = 1.0e-12,
    zero_tolerance: float = 1.0e-10,
) -> StabilityIndicators:
    """返回奇异值，以及对称切线的特征值与惯性。"""

    matrix = _matrix(tangent, "tangent")
    scale = max(float(np.linalg.norm(matrix, ord=2)), 1.0)
    symmetric = bool(
        np.linalg.norm(matrix - matrix.T, ord=2) <= symmetry_tolerance * scale
    )
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    zero_count = int(np.count_nonzero(singular_values <= zero_tolerance * scale))
    if not symmetric:
        return StabilityIndicators(
            symmetric=False,
            eigenvalues=None,
            singular_values=singular_values,
            negative_count=None,
            zero_count=zero_count,
        )
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    negative_count = int(np.count_nonzero(eigenvalues < -zero_tolerance * scale))
    return StabilityIndicators(
        symmetric=True,
        eigenvalues=eigenvalues,
        singular_values=singular_values,
        negative_count=negative_count,
        zero_count=zero_count,
    )


def classify_singular_point(
    tangent: ArrayLike,
    reference_load: ArrayLike,
    right_null_vector: ArrayLike,
    left_null_vector: ArrayLike | None = None,
    *,
    projection_tolerance: float = 1.0e-10,
    singular_value_tolerance: float = 1.0e-10,
    null_residual_tolerance: float = 1.0e-8,
) -> SingularPointClassification:
    """按 ``psi.T @ f_ref`` 区分普通极限点和分岔候选点。

    非对称切线必须显式提供左零向量。对称切线可以省略，此时使用右
    零向量。分类前必须证明切线存在单一数值零空间，且给定左右向量确实
    满足零向量残差容差。返回值中的“分岔”始终是候选分类，仍需高阶与
    分支证据；多重零空间应进入多模态分析，不能调用本函数强行分类。
    """

    matrix = _matrix(tangent, "tangent")
    tolerances = np.asarray(
        [
            projection_tolerance,
            singular_value_tolerance,
            null_residual_tolerance,
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(tolerances)) or np.any(tolerances <= 0.0):
        raise ValueError("所有分类容差必须为正")
    f_ref = _vector(reference_load, "reference_load")
    phi = _vector(right_null_vector, "right_null_vector")
    if f_ref.size != matrix.shape[0] or phi.size != matrix.shape[0]:
        raise ValueError("向量维数必须与 tangent 一致")
    is_symmetric = np.allclose(matrix, matrix.T, rtol=1.0e-12, atol=1.0e-14)
    if left_null_vector is None:
        if not is_symmetric:
            raise ValueError("非对称切线必须提供 left_null_vector")
        psi = phi.copy()
    else:
        psi = _vector(left_null_vector, "left_null_vector")
        if psi.size != matrix.shape[0]:
            raise ValueError("left_null_vector 维数必须与 tangent 一致")

    phi_norm = float(np.linalg.norm(phi))
    psi_norm = float(np.linalg.norm(psi))
    load_norm = float(np.linalg.norm(f_ref))
    if min(phi_norm, psi_norm, load_norm) == 0.0:
        raise ValueError("零向量不能用于临界点分类")
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    tangent_scale = float(singular_values[0]) if singular_values[0] > 0.0 else 1.0
    nullity = int(
        np.count_nonzero(singular_values <= singular_value_tolerance * tangent_scale)
    )
    smallest_relative_singular_value = float(singular_values[-1] / tangent_scale)
    if nullity == 0:
        raise ValueError(
            "tangent 未通过奇异性检查，不能进行极限点/分岔点分类"
        )
    if nullity > 1:
        raise ValueError(
            f"tangent 的数值零空间维数为 {nullity}，应进入多模态临界子空间分析"
        )

    right_null_residual = float(
        np.linalg.norm(matrix @ phi) / (tangent_scale * phi_norm)
    )
    left_null_residual = float(
        np.linalg.norm(psi @ matrix) / (tangent_scale * psi_norm)
    )
    if right_null_residual > null_residual_tolerance:
        raise ValueError(
            f"right_null_vector 残差 {right_null_residual:.3e} 超过容差 "
            f"{null_residual_tolerance:.3e}"
        )
    if left_null_residual > null_residual_tolerance:
        raise ValueError(
            f"left_null_vector 残差 {left_null_residual:.3e} 超过容差 "
            f"{null_residual_tolerance:.3e}"
        )

    projection = float(psi @ f_ref)
    normalized = abs(projection) / (psi_norm * load_norm)
    kind = "bifurcation_candidate" if normalized <= projection_tolerance else "limit_point"
    return SingularPointClassification(
        kind=kind,
        projection=projection,
        normalized_projection=normalized,
        right_null_residual=right_null_residual,
        left_null_residual=left_null_residual,
        nullity=nullity,
        smallest_relative_singular_value=smallest_relative_singular_value,
    )


def modal_assurance_criterion(
    mode_a: ArrayLike,
    mode_b: ArrayLike,
    metric: ArrayLike | None = None,
) -> float:
    """计算加权 MAC；返回值位于 ``[0, 1]``。"""

    first = _vector(mode_a, "mode_a")
    second = _vector(mode_b, "mode_b")
    if first.shape != second.shape:
        raise ValueError("两个模态必须同维")
    weight = np.eye(first.size) if metric is None else _matrix(metric, "metric")
    if weight.shape != (first.size, first.size):
        raise ValueError("metric 维数与模态不一致")
    numerator = abs(float(first @ weight @ second)) ** 2
    denominator = float(first @ weight @ first) * float(second @ weight @ second)
    if denominator <= 0.0:
        raise ValueError("metric 必须在给定模态上给出正范数")
    return float(np.clip(numerator / denominator, 0.0, 1.0))


def subspace_principal_angles(basis_a: ArrayLike, basis_b: ArrayLike) -> Vector:
    """返回两个列空间的主夹角（弧度），用于跟踪模态簇。"""

    first = np.asarray(basis_a, dtype=float)
    second = np.asarray(basis_b, dtype=float)
    if first.ndim != 2 or second.ndim != 2 or first.shape[0] != second.shape[0]:
        raise ValueError("两个基矩阵必须有相同的行数")
    if first.shape[1] == 0 or second.shape[1] == 0:
        raise ValueError("基矩阵必须至少包含一列")
    q_first, _ = np.linalg.qr(first, mode="reduced")
    q_second, _ = np.linalg.qr(second, mode="reduced")
    singular_values = np.linalg.svd(q_first.T @ q_second, compute_uv=False)
    return np.arccos(np.clip(singular_values, -1.0, 1.0))
