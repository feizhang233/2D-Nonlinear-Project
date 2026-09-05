"""一致切线的方向差分校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray


Vector = NDArray[np.float64]
Residual = Callable[[Vector, float], ArrayLike]


@dataclass(frozen=True)
class TangentErrorPoint:
    """一个差分步长对应的校验记录。"""

    step: float
    approximation: Vector
    absolute_error: float
    relative_error: float
    observed_order: float | None


def _vector(values: ArrayLike, name: str) -> Vector:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} 必须是一维有限实数向量")
    return result


def centered_directional_derivative(
    residual: Residual,
    q: ArrayLike,
    load_factor: float,
    direction: ArrayLike,
    step: float,
) -> Vector:
    """计算 ``[R(q+h p)-R(q-h p)]/(2h)``。"""

    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("差分步长 step 必须为正的有限数")
    q_vector = _vector(q, "q")
    p_vector = _vector(direction, "direction")
    if q_vector.shape != p_vector.shape:
        raise ValueError("q 与 direction 的维数必须一致")
    plus = _vector(residual(q_vector + step * p_vector, load_factor), "R(q+h p)")
    minus = _vector(residual(q_vector - step * p_vector, load_factor), "R(q-h p)")
    if plus.shape != minus.shape:
        raise ValueError("残量函数在正负扰动处返回了不同维数")
    return (plus - minus) / (2.0 * step)


def scan_tangent_error(
    residual: Residual,
    tangent: ArrayLike,
    q: ArrayLike,
    load_factor: float,
    direction: ArrayLike,
    steps: Iterable[float],
) -> list[TangentErrorPoint]:
    """扫描多个 ``h``，与解析 ``K_T p`` 比较并估计收敛阶。

    ``observed_order`` 使用相邻两点计算。步长应按严格递减顺序给出；
    当舍入误差开始主导时，估计阶次自然会下降或变为负数。
    """

    q_vector = _vector(q, "q")
    p_vector = _vector(direction, "direction")
    matrix = np.asarray(tangent, dtype=float)
    if matrix.shape != (q_vector.size, q_vector.size):
        raise ValueError("tangent 的形状必须为 (n, n)")
    reference = matrix @ p_vector
    scale = max(float(np.linalg.norm(reference)), np.finfo(float).eps)
    step_values = [float(value) for value in steps]
    if not step_values or any(value <= 0.0 for value in step_values):
        raise ValueError("steps 必须包含正步长")
    if any(next_step >= step for step, next_step in zip(step_values, step_values[1:])):
        raise ValueError("steps 必须严格递减")

    points: list[TangentErrorPoint] = []
    previous_step: float | None = None
    previous_error: float | None = None
    for step in step_values:
        approximation = centered_directional_derivative(
            residual, q_vector, load_factor, p_vector, step
        )
        error = float(np.linalg.norm(approximation - reference))
        order: float | None = None
        if previous_error is not None and error > 0.0 and previous_error > 0.0:
            order = float(
                np.log(previous_error / error) / np.log(previous_step / step)
            )
        points.append(
            TangentErrorPoint(
                step=step,
                approximation=approximation,
                absolute_error=error,
                relative_error=error / scale,
                observed_order=order,
            )
        )
        previous_step = step
        previous_error = error
    return points

