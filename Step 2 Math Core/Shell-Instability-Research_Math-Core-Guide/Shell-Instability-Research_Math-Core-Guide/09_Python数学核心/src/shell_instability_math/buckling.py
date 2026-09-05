"""小型稠密对称广义特征屈曲基准。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


Vector = NDArray[np.float64]
Matrix = NDArray[np.float64]


@dataclass(frozen=True)
class BucklingEigenpairs:
    eigenvalues: Vector
    modes: Matrix
    relative_residuals: Vector


def generalized_symmetric_eigenpairs(
    material_stiffness: ArrayLike,
    geometric_stiffness: ArrayLike,
    *,
    positive_only: bool = True,
    zero_tolerance: float = 1.0e-12,
) -> BucklingEigenpairs:
    """解 ``K_M phi = lambda K_G phi``。

    本实现采用 Cholesky 变换，因此 ``K_G`` 必须对称正定。它用于 V02
    及同类低维验证；真实壳模型的稀疏、不定广义特征问题应使用经过验证
    的专用 eigensolver，并继续检查约束、预应力来源和模态残差。
    """

    k_material = np.asarray(material_stiffness, dtype=float)
    k_geometric = np.asarray(geometric_stiffness, dtype=float)
    if (
        k_material.ndim != 2
        or k_material.shape[0] != k_material.shape[1]
        or k_geometric.shape != k_material.shape
    ):
        raise ValueError("两个刚度矩阵必须是同阶方阵")
    if not np.allclose(k_material, k_material.T, rtol=1.0e-12, atol=1.0e-14):
        raise ValueError("material_stiffness 必须对称")
    if not np.allclose(k_geometric, k_geometric.T, rtol=1.0e-12, atol=1.0e-14):
        raise ValueError("geometric_stiffness 必须对称")

    try:
        lower = np.linalg.cholesky(k_geometric)
    except np.linalg.LinAlgError as error:
        raise ValueError("该稠密基准实现要求 geometric_stiffness 正定") from error

    left_solved = np.linalg.solve(lower, k_material)
    transformed = np.linalg.solve(lower, left_solved.T).T
    transformed = 0.5 * (transformed + transformed.T)
    eigenvalues, transformed_modes = np.linalg.eigh(transformed)
    modes = np.linalg.solve(lower.T, transformed_modes)

    if positive_only:
        scale = max(float(np.max(np.abs(eigenvalues))), 1.0)
        keep = eigenvalues > zero_tolerance * scale
        eigenvalues = eigenvalues[keep]
        modes = modes[:, keep]

    order = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[order]
    modes = modes[:, order]
    residuals: list[float] = []
    for index, eigenvalue in enumerate(eigenvalues):
        mode = modes[:, index]
        norm = float(np.sqrt(mode @ k_geometric @ mode))
        mode /= norm
        pivot = int(np.argmax(np.abs(mode)))
        if mode[pivot] < 0.0:
            mode *= -1.0
        residual = k_material @ mode - eigenvalue * (k_geometric @ mode)
        denominator = (
            np.linalg.norm(k_material, ord=2)
            + abs(eigenvalue) * np.linalg.norm(k_geometric, ord=2)
        ) * np.linalg.norm(mode)
        residuals.append(float(np.linalg.norm(residual) / max(denominator, np.finfo(float).eps)))
    return BucklingEigenpairs(
        eigenvalues=eigenvalues,
        modes=modes,
        relative_residuals=np.asarray(residuals, dtype=float),
    )

