"""Validated space-frame inputs; SI units and A00 right-hand conventions."""

from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np

DOF_NAMES = ("u", "v", "w", "rx", "ry", "rz")
FORCE_NAMES = ("fx", "fy", "fz", "mx", "my", "mz")


def finite(name, value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


def positive(name, value):
    finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def identifier(name, value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def array(name, value, shape):
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result


def basis(value):
    q = array("axes", value, (3, 3))
    if not np.allclose(q @ q.T, np.eye(3), rtol=0, atol=1e-10) or not np.isclose(
        np.linalg.det(q), 1, rtol=0, atol=1e-10
    ):
        raise ValueError("axes must be an orthonormal right-handed basis (rows)")
    return q


@dataclass(frozen=True, slots=True)
class Node:
    id: int
    x: float
    y: float
    z: float

    def __post_init__(self):
        identifier("Node.id", self.id)
        for name in ("x", "y", "z"):
            finite(f"Node.{name}", getattr(self, name))

    @property
    def coordinates(self):
        return np.array([self.x, self.y, self.z], dtype=float)


@dataclass(frozen=True, slots=True)
class FrameElement:
    """12 DOFs, principal-axis section; reference_vector projects onto local y.

    Releases are local rotational DOF indices (3,4,5,9,10,11).
    J is the Saint-Venant torsion constant, not the polar area moment.
    """

    id: int
    node_i: int
    node_j: int
    E: float
    G: float
    A: float
    Iy: float
    Iz: float
    J: float
    reference_vector: tuple[float, float, float]
    theory: str = "euler_bernoulli"
    Asy: float | None = None
    Asz: float | None = None
    roll_angle: float = 0.0  # degrees about local +x
    releases: tuple[int, ...] = ()

    def __post_init__(self):
        for name in ("id", "node_i", "node_j"):
            identifier(f"FrameElement.{name}", getattr(self, name))
        if self.node_i == self.node_j:
            raise ValueError("element end nodes must be different")
        for name in ("E", "G", "A", "Iy", "Iz", "J"):
            positive(f"FrameElement.{name}", getattr(self, name))
        ref = array("reference_vector", self.reference_vector, (3,))
        if np.max(np.abs(ref)) == 0:
            raise ValueError("reference_vector must be nonzero")
        object.__setattr__(self, "reference_vector", tuple(ref))
        finite("roll_angle", self.roll_angle)
        if self.theory not in ("euler_bernoulli", "timoshenko"):
            raise ValueError("theory must be euler_bernoulli or timoshenko")
        for name in ("Asy", "Asz"):
            value = getattr(self, name)
            if value is not None:
                positive(name, value)
            elif self.theory == "timoshenko":
                raise ValueError(f"{name} is required for timoshenko")
        releases = tuple(self.releases)
        if any(
            isinstance(r, (bool, np.bool_))
            or not isinstance(r, Integral)
            or r not in (3, 4, 5, 9, 10, 11)
            for r in releases
        ):
            raise ValueError("releases must contain local rotational indices 3,4,5,9,10,11")
        if len(set(releases)) != len(releases):
            raise ValueError("releases must be unique")
        object.__setattr__(self, "releases", tuple(sorted(releases)))


@dataclass(frozen=True, slots=True)
class Support:
    """Six prescribed DOFs, optionally in an explicitly supplied local basis."""

    node_id: int
    u: bool = False
    v: bool = False
    w: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False
    u_value: float = 0.0
    v_value: float = 0.0
    w_value: float = 0.0
    rx_value: float = 0.0
    ry_value: float = 0.0
    rz_value: float = 0.0
    axes: tuple[tuple[float, float, float], ...] | None = None

    def __post_init__(self):
        identifier("Support.node_id", self.node_id)
        for name in DOF_NAMES:
            flag, value = getattr(self, name), getattr(self, name + "_value")
            if not isinstance(flag, (bool, np.bool_)):
                raise TypeError(f"Support.{name} must be boolean")
            finite(f"Support.{name}_value", value)
            if not flag and value != 0:
                raise ValueError(f"Support.{name}_value requires a restrained DOF")
        if not any(self.restraints):
            raise ValueError("Support must restrain at least one DOF")
        if self.axes is not None:
            object.__setattr__(self, "axes", tuple(map(tuple, basis(self.axes))))

    @property
    def restraints(self):
        return tuple(getattr(self, n) for n in DOF_NAMES)

    @property
    def prescribed_values(self):
        return tuple(getattr(self, n + "_value") for n in DOF_NAMES)


@dataclass(frozen=True, slots=True)
class NodalLoad:
    node_id: int
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0

    def __post_init__(self):
        identifier("NodalLoad.node_id", self.node_id)
        for name in FORCE_NAMES:
            finite(f"NodalLoad.{name}", getattr(self, name))

    @property
    def vector(self):
        return np.array([getattr(self, name) for name in FORCE_NAMES], dtype=float)


@dataclass(frozen=True, slots=True)
class DistributedLoad:
    """Linear intensity per actual member length; mx is always local axial torque.

    coordinate_system rotates qx/qy/qz only. No distributed bending couples.
    Timoshenko distributed loads are deliberately rejected (A03 scope).
    """

    element_id: int
    qx_i: float = 0.0
    qy_i: float = 0.0
    qz_i: float = 0.0
    mx_i: float = 0.0
    qx_j: float = 0.0
    qy_j: float = 0.0
    qz_j: float = 0.0
    mx_j: float = 0.0
    coordinate_system: str = "local"

    def __post_init__(self):
        identifier("DistributedLoad.element_id", self.element_id)
        for end in ("i", "j"):
            for name in ("qx", "qy", "qz", "mx"):
                finite(f"{name}_{end}", getattr(self, f"{name}_{end}"))
        if self.coordinate_system not in ("local", "global"):
            raise ValueError("coordinate_system must be local or global")


@dataclass(frozen=True, slots=True)
class SectionPoint:
    y: float
    z: float

    def __post_init__(self):
        finite("SectionPoint.y", self.y)
        finite("SectionPoint.z", self.z)
