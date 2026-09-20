"""A01/A03: EB or closed homogeneous Timoshenko 12x12 stiffness."""

import numpy as np

from .models import array, positive


def calculate_local_stiffness(element, length):
    positive("length", length)
    L = float(length)
    k = np.zeros((12, 12))
    for dofs, rigidity in (([0, 6], element.E * element.A), ([3, 9], element.G * element.J)):
        k[np.ix_(dofs, dofs)] = rigidity / L * np.array([[1, -1], [-1, 1]])
    for dofs, inertia, shear_area, signs in (
        ([1, 5, 7, 11], element.Iz, element.Asy, [1, 1, 1, 1]),
        ([2, 4, 8, 10], element.Iy, element.Asz, [1, -1, 1, -1]),
    ):
        EI = element.E * inertia
        phi = 12 * EI / (element.G * shear_area * L**2) if element.theory == "timoshenko" else 0
        block = (
            EI
            / (L**3 * (1 + phi))
            * np.array(
                [
                    [12, 6 * L, -12, 6 * L],
                    [6 * L, (4 + phi) * L**2, -6 * L, (2 - phi) * L**2],
                    [-12, -6 * L, 12, -6 * L],
                    [6 * L, (2 - phi) * L**2, -6 * L, (4 + phi) * L**2],
                ]
            )
        )
        k[np.ix_(dofs, dofs)] = block * np.outer(signs, signs)
    return array("calculated stiffness", k, (12, 12))
