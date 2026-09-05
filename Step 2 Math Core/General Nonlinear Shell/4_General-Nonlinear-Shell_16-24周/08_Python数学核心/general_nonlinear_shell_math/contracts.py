"""Residual/tangent contracts shared by future shell-element implementations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _square(value: ArrayLike, *, name: str) -> FloatArray:
    matrix = np.asarray(value, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{name} must be square, got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


@dataclass(frozen=True)
class TangentContributions:
    """Canonical decomposition for ``r=f_ext-f_int``.

    ``total = material + geometric + rotational + stabilization - load``.
    """

    material: FloatArray
    geometric: FloatArray
    rotational: FloatArray
    stabilization: FloatArray
    load: FloatArray

    @classmethod
    def from_arrays(
        cls,
        *,
        material: ArrayLike,
        geometric: ArrayLike,
        rotational: ArrayLike,
        stabilization: ArrayLike,
        load: ArrayLike,
    ) -> TangentContributions:
        values = {
            "material": _square(material, name="material"),
            "geometric": _square(geometric, name="geometric"),
            "rotational": _square(rotational, name="rotational"),
            "stabilization": _square(stabilization, name="stabilization"),
            "load": _square(load, name="load"),
        }
        shapes = {value.shape for value in values.values()}
        if len(shapes) != 1:
            raise ValueError(
                f"all tangent contributions must share a shape, got {sorted(shapes)}"
            )
        return cls(**values)

    @property
    def total(self) -> FloatArray:
        return (
            self.material
            + self.geometric
            + self.rotational
            + self.stabilization
            - self.load
        )

    @property
    def is_symmetric(self) -> bool:
        return bool(np.allclose(self.total, self.total.T))
