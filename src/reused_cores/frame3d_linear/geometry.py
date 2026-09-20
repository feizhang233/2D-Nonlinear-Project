"""A01: explicit right-handed section orientation and length."""

from dataclasses import dataclass

import numpy as np

from .models import FrameElement, Node, positive


@dataclass(frozen=True, slots=True)
class ElementGeometry:
    L: float
    Q: np.ndarray  # rows = local basis vectors in global coordinates


def calculate_geometry(
    element: FrameElement,
    node_i: Node,
    node_j: Node,
    *,
    length_tolerance=1e-12,
    direction_tolerance=1e-10,
):
    if (node_i.id, node_j.id) != (element.node_i, element.node_j):
        raise ValueError("geometry nodes must match the element ends in order")
    positive("length_tolerance", length_tolerance)
    positive("direction_tolerance", direction_tolerance)
    delta = node_j.coordinates - node_i.coordinates
    length = float(np.linalg.norm(delta))
    if not np.isfinite(length) or length <= length_tolerance:
        raise ValueError(f"element {element.id}: zero or invalid length")
    ex = delta / length
    a = np.array(element.reference_vector)
    a /= np.max(np.abs(a))
    a /= np.linalg.norm(a)
    b = a - np.dot(a, ex) * ex
    if np.linalg.norm(b) <= direction_tolerance:
        raise ValueError(f"element {element.id}: reference_vector is parallel to its axis")
    ey = b / np.linalg.norm(b)
    ez = np.cross(ex, ey)
    angle = np.deg2rad(element.roll_angle % 360)
    q = np.array(
        [ex, np.cos(angle) * ey + np.sin(angle) * ez, -np.sin(angle) * ey + np.cos(angle) * ez]
    )
    return ElementGeometry(length, q)
