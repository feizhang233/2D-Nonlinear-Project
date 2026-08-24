"""Validated frame records adapted from sibling ``2D-Frame-Project`` 0.2.0.

Only records consumed by the P9 corotational adapter are retained.  The
source provenance and full-file hashes are recorded in ``PROVENANCE.md``.
"""

# ruff: noqa: E741 -- retain the sibling frame2d public property name ``I``.

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np


def _validate_id(name: str, value: int) -> None:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_finite(name: str, value: float) -> None:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _validate_positive(name: str, value: float) -> None:
    _validate_finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class Node:
    """Frame node in the global X-Y plane; DOFs are ``[u, v, phi]``."""

    id: int
    x: float
    y: float

    def __post_init__(self) -> None:
        _validate_id("Node.id", self.id)
        _validate_finite("Node.x", self.x)
        _validate_finite("Node.y", self.y)


@dataclass(frozen=True, slots=True)
class FrameElement:
    """Two-node prismatic Euler-Bernoulli frame element."""

    id: int
    node_i: int
    node_j: int
    E: float
    A: float
    I: float

    def __post_init__(self) -> None:
        _validate_id("FrameElement.id", self.id)
        _validate_id("FrameElement.node_i", self.node_i)
        _validate_id("FrameElement.node_j", self.node_j)
        if self.node_i == self.node_j:
            raise ValueError("FrameElement.node_i and node_j must be different")
        _validate_positive("FrameElement.E", self.E)
        _validate_positive("FrameElement.A", self.A)
        _validate_positive("FrameElement.I", self.I)


@dataclass(frozen=True, slots=True)
class NodalLoad:
    """Global concentrated force/moment using ``[FX, FY, MZ]`` signs."""

    node_id: int
    fx: float = 0.0
    fy: float = 0.0
    mz: float = 0.0

    def __post_init__(self) -> None:
        _validate_id("NodalLoad.node_id", self.node_id)
        _validate_finite("NodalLoad.fx", self.fx)
        _validate_finite("NodalLoad.fy", self.fy)
        _validate_finite("NodalLoad.mz", self.mz)
