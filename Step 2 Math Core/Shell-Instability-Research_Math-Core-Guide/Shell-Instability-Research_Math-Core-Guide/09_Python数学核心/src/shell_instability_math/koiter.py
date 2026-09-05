"""V03-V05 所需的 Koiter 低维势能模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray


Vector = NDArray[np.float64]


@dataclass(frozen=True)
class ScalarKoiterBranch:
    amplitudes: Vector
    amplitude_squared: float
    hessian: float
    branch_type: str
    locally_stable: bool


@dataclass(frozen=True)
class TwoModeBranch:
    name: str
    amplitude: Vector
    energy: float
    hessian: NDArray[np.float64]
    hessian_eigenvalues: Vector
    locally_stable: bool


def single_mode_quartic_branches(
    load_factor: float,
    quartic_coefficient: float,
) -> ScalarKoiterBranch:
    """分析 ``F=(1-lambda)a^2+A4*a^4`` 的非零分支。"""

    if quartic_coefficient == 0.0:
        raise ValueError("quartic_coefficient 不能为零")
    amplitude_squared = -(1.0 - load_factor) / (2.0 * quartic_coefficient)
    if amplitude_squared <= 0.0:
        return ScalarKoiterBranch(
            amplitudes=np.empty(0, dtype=float),
            amplitude_squared=amplitude_squared,
            hessian=float("nan"),
            branch_type="no_real_nonzero_branch",
            locally_stable=False,
        )
    amplitude = float(np.sqrt(amplitude_squared))
    hessian = -4.0 * (1.0 - load_factor)
    branch_type = "supercritical" if quartic_coefficient > 0.0 else "subcritical"
    return ScalarKoiterBranch(
        amplitudes=np.asarray([-amplitude, amplitude]),
        amplitude_squared=amplitude_squared,
        hessian=hessian,
        branch_type=branch_type,
        locally_stable=hessian > 0.0,
    )


def _two_mode_energy(
    amplitude: Vector,
    load_factor: float,
    self_quartic: float,
    cross_quartic: float,
) -> float:
    a1, a2 = amplitude
    return float(
        (1.0 - load_factor) * (a1**2 + a2**2)
        + self_quartic * (a1**4 + a2**4)
        + cross_quartic * a1**2 * a2**2
    )


def _two_mode_hessian(
    amplitude: Vector,
    load_factor: float,
    self_quartic: float,
    cross_quartic: float,
) -> NDArray[np.float64]:
    a1, a2 = amplitude
    return np.asarray(
        [
            [
                2.0 * (1.0 - load_factor)
                + 12.0 * self_quartic * a1**2
                + 2.0 * cross_quartic * a2**2,
                4.0 * cross_quartic * a1 * a2,
            ],
            [
                4.0 * cross_quartic * a1 * a2,
                2.0 * (1.0 - load_factor)
                + 12.0 * self_quartic * a2**2
                + 2.0 * cross_quartic * a1**2,
            ],
        ],
        dtype=float,
    )


def _branch(
    name: str,
    amplitude: Vector,
    load_factor: float,
    self_quartic: float,
    cross_quartic: float,
    stability_tolerance: float,
) -> TwoModeBranch:
    hessian = _two_mode_hessian(
        amplitude, load_factor, self_quartic, cross_quartic
    )
    hessian_eigenvalues = np.linalg.eigvalsh(hessian)
    return TwoModeBranch(
        name=name,
        amplitude=amplitude,
        energy=_two_mode_energy(
            amplitude, load_factor, self_quartic, cross_quartic
        ),
        hessian=hessian,
        hessian_eigenvalues=hessian_eigenvalues,
        locally_stable=bool(np.all(hessian_eigenvalues > stability_tolerance)),
    )


def two_mode_quartic_branches(
    load_factor: float,
    *,
    self_quartic: float = 1.0,
    cross_quartic: float = 1.0,
    stability_tolerance: float = 1.0e-12,
) -> dict[str, TwoModeBranch]:
    """返回 V04 势能的单模态代表分支和对称混合代表分支。"""

    delta = load_factor - 1.0
    if delta <= 0.0:
        raise ValueError("本函数的非零分支要求 load_factor > 1")
    if self_quartic <= 0.0:
        raise ValueError("self_quartic 必须为正")
    mixed_denominator = 2.0 * self_quartic + cross_quartic
    if mixed_denominator <= 0.0:
        raise ValueError("对称混合分支要求 2*self_quartic+cross_quartic > 0")
    single = np.asarray([np.sqrt(delta / (2.0 * self_quartic)), 0.0])
    mixed_value = np.sqrt(delta / mixed_denominator)
    mixed = np.asarray([mixed_value, mixed_value])
    return {
        "single_mode": _branch(
            "single_mode",
            single,
            load_factor,
            self_quartic,
            cross_quartic,
            stability_tolerance,
        ),
        "symmetric_mixed": _branch(
            "symmetric_mixed",
            mixed,
            load_factor,
            self_quartic,
            cross_quartic,
            stability_tolerance,
        ),
    }


def koiter_two_thirds_law(
    imperfection_magnitudes: ArrayLike,
    *,
    coefficient: float = 1.5,
) -> Vector:
    """计算 ``lambda*=1-C*|mu|^(2/3)``。"""

    magnitudes = np.asarray(imperfection_magnitudes, dtype=float)
    if magnitudes.ndim != 1 or np.any(magnitudes <= 0.0):
        raise ValueError("imperfection_magnitudes 必须是一维正数数组")
    if coefficient <= 0.0:
        raise ValueError("coefficient 必须为正")
    return 1.0 - coefficient * np.power(magnitudes, 2.0 / 3.0)


def logarithmic_slopes(x: Iterable[float], y: Iterable[float]) -> Vector:
    """计算相邻正数据点的对数斜率。"""

    x_values = np.asarray(list(x), dtype=float)
    y_values = np.asarray(list(y), dtype=float)
    if x_values.shape != y_values.shape or x_values.ndim != 1 or x_values.size < 2:
        raise ValueError("x、y 必须是至少含两点的同形一维数组")
    if np.any(x_values <= 0.0) or np.any(y_values <= 0.0):
        raise ValueError("对数斜率要求所有数据为正")
    return np.diff(np.log(y_values)) / np.diff(np.log(x_values))

