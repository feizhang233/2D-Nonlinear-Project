"""A00/A02: positive-x section actions and equilibrium-integrated exact fields.

For a prismatic EB member under linear line loads this integrates the beam
ODEs (including the particular solution). For Timoshenko it uses the same
homogeneous solution as its closed stiffness; only nodal loads are accepted.
"""

from dataclasses import dataclass

import numpy as np
from numpy.polynomial import Polynomial as P

from .validation import energy_check


@dataclass(frozen=True, slots=True)
class ElementFieldResults:
    x_local: np.ndarray
    axial_displacement: np.ndarray
    transverse_displacement_y: np.ndarray
    transverse_displacement_z: np.ndarray
    rotation_x: np.ndarray
    rotation_y: np.ndarray
    rotation_z: np.ndarray
    axial_force: np.ndarray
    shear_force_y: np.ndarray
    shear_force_z: np.ndarray
    torsional_moment: np.ndarray
    bending_moment_y: np.ndarray
    bending_moment_z: np.ndarray
    x_global: np.ndarray
    y_global: np.ndarray
    z_global: np.ndarray
    x_deformed: np.ndarray
    y_deformed: np.ndarray
    z_deformed: np.ndarray
    normal_stress: np.ndarray  # [section point, station], Pa


@dataclass(frozen=True, slots=True)
class ElementEquilibriumValidation:
    force_residual: list[float]
    moment_residual: list[float]
    maximum_normalized_residual: float
    endpoint_translation_error: float
    endpoint_rotation_error: float
    release_residual: float
    energy_residual_ratio: float
    energy_absolute_error: float
    energy_roundoff_bound: float
    passed: bool


def calculate_normal_stress(element, axial_force, moment_y, moment_z, y, z):
    from .models import finite

    finite("section y", y)
    finite("section z", z)
    return (
        np.asarray(axial_force) / element.A
        + np.asarray(moment_y) * z / element.Iy
        - np.asarray(moment_z) * y / element.Iz
    )


def calculate_element_field_results(
    element,
    node_i,
    geometry,
    local_displacements,
    local_end_forces,
    intensities,
    *,
    number_of_points=101,
    deformation_scale=1.0,
    section_points=(),
    local_stiffness=None,
):
    d, s, L = local_displacements, local_end_forces, geometry.L
    loads = [P([intensities[0, i], (intensities[1, i] - intensities[0, i]) / L]) for i in range(4)]
    n, vy, vz, tx = [-s[i] - loads[i].integ() for i in range(4)]
    my, mz = -s[4] + vz.integ(), -s[5] - vy.integ()
    u = d[0] + n.integ() / (element.E * element.A)
    rx = d[3] + tx.integ() / (element.G * element.J)
    ry = d[4] + my.integ() / (element.E * element.Iy)
    rz = d[5] + mz.integ() / (element.E * element.Iz)
    v, w = d[1] + rz.integ(), d[2] - ry.integ()
    energy_density = (
        n * n / (element.E * element.A)
        + tx * tx / (element.G * element.J)
        + my * my / (element.E * element.Iy)
        + mz * mz / (element.E * element.Iz)
    )
    if element.theory == "timoshenko":
        v += vy.integ() / (element.G * element.Asy)
        w += vz.integ() / (element.G * element.Asz)
        energy_density += vy * vy / (element.G * element.Asy) + vz * vz / (element.G * element.Asz)
    displacement = [u, v, w, rx, ry, rz]
    actions = [n, vy, vz, tx, my, mz]
    line_work = sum(q * a for q, a in zip(loads, [u, v, w, rx], strict=True)).integ()(L)
    strain_energy = float(energy_density.integ()(L) / 2)
    boundary_work = float(s @ d)
    if local_stiffness is None:
        from .stiffness import calculate_local_stiffness

        local_stiffness = calculate_local_stiffness(element, L)
    energy_ratio, energy_error, energy_roundoff = energy_check(
        strain_energy,
        boundary_work + line_work,
        d,
        local_stiffness,
        float(np.abs(s) @ np.abs(d)) + abs(line_work),
    )
    end_error = np.array([p(L) for p in displacement]) - d[6:]
    action_error = np.array([p(L) for p in actions]) - s[6:]
    # Separate force [N] and moment [N m] scales; never compare mixed units.
    force_scale = max(
        1.0, np.max(np.abs(s[[0, 1, 2, 6, 7, 8]])), L * np.max(np.abs(intensities[:, :3]))
    )
    moment_scale = max(
        1.0,
        np.max(np.abs(s[[3, 4, 5, 9, 10, 11]])),
        force_scale * L,
        L * np.max(np.abs(intensities[:, 3])),
    )
    normalized = max(
        np.max(np.abs(action_error[:3])) / force_scale,
        np.max(np.abs(action_error[3:])) / moment_scale,
    )
    release_error = float(max((abs(s[i]) for i in element.releases), default=0))
    translation_error = float(np.max(np.abs(end_error[:3])))
    rotation_error = float(np.max(np.abs(end_error[3:])))
    translation_scale = max(1e-9, np.max(np.abs(d[[0, 1, 2, 6, 7, 8]])))
    rotation_scale = max(1e-9, np.max(np.abs(d[[3, 4, 5, 9, 10, 11]])))
    passed = (
        normalized <= 1e-8
        and release_error / moment_scale <= 1e-8
        and translation_error <= 1e-10 + 1e-8 * translation_scale
        and rotation_error <= 1e-10 + 1e-8 * rotation_scale
        and energy_ratio <= 1e-8
    )
    validation = ElementEquilibriumValidation(
        action_error[:3].tolist(),
        action_error[3:].tolist(),
        float(normalized),
        translation_error,
        rotation_error,
        release_error,
        energy_ratio,
        energy_error,
        energy_roundoff,
        bool(passed),
    )
    x = np.linspace(0, L, number_of_points)
    values = [p(x) for p in displacement + actions]
    points = node_i.coordinates + x[:, None] * geometry.Q[0]
    displaced = points + deformation_scale * np.column_stack(values[:3]) @ geometry.Q
    stress = np.array(
        [
            calculate_normal_stress(element, values[6], values[10], values[11], p.y, p.z)
            for p in section_points
        ]
    ).reshape(len(section_points), len(x))
    fields = ElementFieldResults(x, *values, *points.T, *displaced.T, stress)
    if not all(np.isfinite(a).all() for a in values + [points, displaced, stress]):
        raise ValueError("non-finite recovered fields; check property/load scales")
    return fields, validation, strain_energy, float(line_work)


def reshape_nodal_displacements(displacements):
    d = np.asarray(displacements, dtype=float)
    if d.ndim != 1 or not d.size or d.size % 6 or not np.isfinite(d).all():
        raise ValueError("displacements must be finite with 6 DOFs/node")
    return d.reshape(-1, 6).copy()
