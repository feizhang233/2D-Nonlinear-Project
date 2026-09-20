"""A02: consistent EB loads, integrated by exact polynomial quadrature."""

import numpy as np

from .models import array, positive


def local_load_intensities(element, loads, geometry):
    """Return summed endpoint [qx,qy,qz,mx] values, in local axes."""
    result = np.zeros((2, 4))
    for load in loads:
        if load.element_id != element.id:
            raise ValueError("load element_id does not match element")
        if element.theory != "euler_bernoulli":
            raise ValueError("Timoshenko distributed loads are not supported; use nodal loads")
        for i, end in enumerate(("i", "j")):
            force = np.array([getattr(load, f"q{axis}_{end}") for axis in "xyz"])
            if load.coordinate_system == "global":
                force = geometry.Q @ force
            result[i, :3] += force
            result[i, 3] += getattr(load, f"mx_{end}")
    return array("summed load intensities", result, (2, 4))


def equivalent_load_from_intensities(length, intensities):
    positive("length", length)
    values = array("intensities", intensities, (2, 4))
    L = float(length)
    f = np.zeros(12)
    points, weights = np.polynomial.legendre.leggauss(3)
    for point, weight in zip(points, weights, strict=True):
        t = (point + 1) / 2
        q = (1 - t) * values[0] + t * values[1]
        h = np.array(
            [
                1 - 3 * t * t + 2 * t**3,
                L * (t - 2 * t * t + t**3),
                3 * t * t - 2 * t**3,
                L * (-t * t + t**3),
            ]
        )
        factor = weight * L / 2
        f[[0, 6]] += factor * q[0] * np.array([1 - t, t])
        f[[3, 9]] += factor * q[3] * np.array([1 - t, t])
        f[[1, 5, 7, 11]] += factor * q[1] * h
        f[[2, 4, 8, 10]] += factor * q[2] * h * np.array([1, -1, 1, -1])
    return f


def calculate_local_equivalent_nodal_load(element, load, length, *, geometry=None):
    if geometry is None:
        if load.coordinate_system == "global":
            raise ValueError("global distributed loads require element geometry")
        from .geometry import ElementGeometry

        geometry = ElementGeometry(length, np.eye(3))
    return equivalent_load_from_intensities(
        length, local_load_intensities(element, [load], geometry)
    )
