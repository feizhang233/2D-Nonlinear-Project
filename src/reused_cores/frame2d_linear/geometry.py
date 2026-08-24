"""Linear ``frame2d`` element length and direction cosines."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from reused_cores.frame2d_linear.models import FrameElement, Node


@dataclass(frozen=True, slots=True)
class ElementGeometry:
    L: float
    c: float
    s: float


def calculate_geometry(
    element: FrameElement,
    node_i: Node,
    node_j: Node,
) -> ElementGeometry:
    """Return reference length and i-to-j direction cosines."""

    if node_i.id != element.node_i:
        raise ValueError(f"node_i.id={node_i.id} does not match element.node_i={element.node_i}")
    if node_j.id != element.node_j:
        raise ValueError(f"node_j.id={node_j.id} does not match element.node_j={element.node_j}")
    dx = node_j.x - node_i.x
    dy = node_j.y - node_i.y
    length = float(np.hypot(dx, dy))
    if length == 0.0:
        raise ValueError(f"FrameElement {element.id} has zero length")
    return ElementGeometry(L=length, c=float(dx / length), s=float(dy / length))
