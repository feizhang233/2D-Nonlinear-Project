"""Complete space-frame pipeline with the same solve_frame shape as frame2d."""

from dataclasses import dataclass
from numbers import Integral

import numpy as np

from .assembly import assemble_nodal_load_vector, calculate_element_dof_map
from .geometry import ElementGeometry, calculate_geometry
from .loads import equivalent_load_from_intensities, local_load_intensities
from .models import DistributedLoad, FrameElement, NodalLoad, Node, SectionPoint, Support, finite
from .postprocessing import (
    ElementEquilibriumValidation,
    ElementFieldResults,
    calculate_element_field_results,
)
from .recovery import recover_element_end_response
from .releases import condense_releases
from .solution import solve_system
from .stiffness import calculate_local_stiffness
from .transformation import calculate_transformation
from .validation import energy_check


@dataclass(frozen=True, slots=True)
class ElementAnalysisResult:
    element_id: int
    geometry: ElementGeometry
    local_displacements: np.ndarray
    local_end_forces: np.ndarray
    fields: ElementFieldResults
    validation: ElementEquilibriumValidation
    strain_energy: float


@dataclass(frozen=True, slots=True)
class GlobalValidation:
    stiffness_symmetry_ratio: float
    free_dof_residual_ratio: float
    free_force_residual_ratio: float
    free_moment_residual_ratio: float
    force_balance: list[float]
    moment_balance: list[float]
    force_balance_ratio: float
    moment_balance_ratio: float
    strain_energy: float
    external_work: float
    energy_residual_ratio: float
    energy_absolute_error: float
    energy_roundoff_bound: float
    scaled_condition_number: float
    passed: bool


@dataclass(frozen=True, slots=True)
class FrameAnalysisResult:
    displacements: np.ndarray
    nodal_displacements: np.ndarray
    reactions: np.ndarray
    free_dofs: np.ndarray
    restrained_dofs: np.ndarray
    inactive_dof_vectors: np.ndarray
    active_dof_count: int
    elements: tuple[ElementAnalysisResult, ...]
    validation: GlobalValidation


def _typed(name, values, expected):
    result = tuple(values)
    if not all(isinstance(item, expected) for item in result):
        raise TypeError(f"{name} must contain only {expected.__name__} objects")
    return result


def solve_frame(
    nodes,
    elements,
    supports,
    nodal_loads=(),
    distributed_loads=(),
    *,
    number_of_points=101,
    deformation_scale=1.0,
    section_points=(),
):
    """Linear static solve, including recovery and validation.

    Node IDs are contiguous from 1, as in frame2d. SectionPoint coordinates
    are local section y/z and apply to each element. Inactive released joint
    rotations have a zero gauge; member-end rotations are recovered separately.
    """
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        try:
            return _solve_frame(
                nodes,
                elements,
                supports,
                nodal_loads,
                distributed_loads,
                number_of_points,
                deformation_scale,
                section_points,
            )
        except (FloatingPointError, OverflowError) as error:
            raise ValueError(
                "numerical overflow; check coordinates, properties and load scales"
            ) from error


def _solve_frame(
    nodes,
    elements,
    supports,
    nodal_loads,
    distributed_loads,
    number_of_points,
    deformation_scale,
    section_points,
):
    nodes = _typed("nodes", nodes, Node)
    elements = _typed("elements", elements, FrameElement)
    supports = _typed("supports", supports, Support)
    nodal_loads = _typed("nodal_loads", nodal_loads, NodalLoad)
    distributed_loads = _typed("distributed_loads", distributed_loads, DistributedLoad)
    section_points = _typed("section_points", section_points, SectionPoint)
    if isinstance(number_of_points, (bool, np.bool_)) or not isinstance(number_of_points, Integral):
        raise TypeError("number_of_points must be an integer")
    if not 2 <= number_of_points <= 2001:
        raise ValueError("number_of_points must be between 2 and 2001")
    finite("deformation_scale", deformation_scale)
    if not nodes or not elements:
        raise ValueError("nodes and elements must be nonempty")
    if sorted(n.id for n in nodes) != list(range(1, len(nodes) + 1)):
        raise ValueError("Node.id values must be unique and contiguous from 1")
    by_node = {n.id: n for n in nodes}
    by_element = {e.id: e for e in elements}
    if len(by_element) != len(elements):
        raise ValueError("FrameElement.id values must be unique")
    connected = set()
    for e in elements:
        if e.node_i not in by_node or e.node_j not in by_node:
            raise ValueError(f"element {e.id} references an unknown node")
        connected.update((e.node_i, e.node_j))
    if connected != set(by_node):
        raise ValueError("isolated nodes are not supported; remove or connect them")
    for item in supports + nodal_loads:
        if item.node_id not in by_node:
            raise ValueError(f"unknown node {item.node_id} in support/load")
    loads_by_element = {e.id: [] for e in elements}
    for load in distributed_loads:
        if load.element_id not in by_element:
            raise ValueError(f"unknown element {load.element_id} in distributed load")
        loads_by_element[load.element_id].append(load)

    size = 6 * len(nodes)
    k = np.zeros((size, size))
    fnodal = assemble_nodal_load_vector(len(nodes), nodal_loads)
    f, physical_load = fnodal.copy(), fnodal.copy()
    rotational_connectivity = [[] for _ in nodes]
    matrices = []
    for e in elements:
        geom = calculate_geometry(e, by_node[e.node_i], by_node[e.node_j])
        kl = calculate_local_stiffness(e, geom.L)
        t = calculate_transformation(geom)
        intensities = local_load_intensities(e, loads_by_element[e.id], geom)
        fl = equivalent_load_from_intensities(geom.L, intensities)
        condensed = condense_releases(kl, fl, e.releases)
        dofs = calculate_element_dof_map(e)
        k[np.ix_(dofs, dofs)] += t.T @ condensed.stiffness @ t
        f[dofs] += t.T @ condensed.load
        physical_load[dofs] += t.T @ fl
        for end, node_id in enumerate((e.node_i, e.node_j)):
            for axis in range(3):
                if end * 6 + axis + 3 not in e.releases:
                    rotational_connectivity[node_id - 1].append(geom.Q[axis])
        matrices.append((e, geom, kl, t, fl, condensed, intensities))
    solution = solve_system(k, f, supports, rotational_connectivity=rotational_connectivity)
    d, reactions = solution.displacements, solution.reactions
    recovered, distributed_work = [], 0.0
    for e, geom, kl, t, fl, condensed, intensities in matrices:
        end = recover_element_end_response(e, d, kl, t, fl, condensation=condensed)
        fields, validation, energy, line_work = calculate_element_field_results(
            e,
            by_node[e.node_i],
            geom,
            end.local_displacements,
            end.local_end_forces,
            intensities,
            number_of_points=number_of_points,
            deformation_scale=deformation_scale,
            section_points=section_points,
            local_stiffness=kl,
        )
        distributed_work += line_work
        recovered.append(
            ElementAnalysisResult(
                e.id,
                geom,
                end.local_displacements,
                end.local_end_forces,
                fields,
                validation,
                energy,
            )
        )
    s = solution.support_transformation
    ks, ds, fs = s @ k @ s.T, s @ d, s @ f
    residual = s @ reactions
    scales = np.abs(ks) @ np.abs(ds) + np.abs(fs)
    free = solution.free_dofs
    force_free, moment_free = free[free % 6 < 3], free[free % 6 >= 3]

    def ratio(dofs):
        return float(np.max(np.abs(residual[dofs]) / np.maximum(1.0, scales[dofs]), initial=0))

    force_ratio, moment_ratio = ratio(force_free), ratio(moment_free)
    # Use actual, uncondensed external load resultants and r x F about node 1.
    xyz = np.array([by_node[i].coordinates for i in range(1, len(nodes) + 1)])
    xyz -= xyz[0]
    external, support = physical_load.reshape(-1, 6), reactions.reshape(-1, 6)
    total = external + support
    force_balance = total[:, :3].sum(axis=0)
    moment_balance = (total[:, 3:] + np.cross(xyz, total[:, :3])).sum(axis=0)
    force_scale = max(1.0, np.abs(external[:, :3]).sum() + np.abs(support[:, :3]).sum())
    moment_scale = max(
        1.0,
        np.abs(external[:, 3:]).sum()
        + np.abs(support[:, 3:]).sum()
        + np.abs(np.cross(xyz, external[:, :3])).sum()
        + np.abs(np.cross(xyz, support[:, :3])).sum(),
    )
    balance_f = float(np.max(np.abs(force_balance)) / force_scale)
    balance_m = float(np.max(np.abs(moment_balance)) / moment_scale)
    energy = sum(e.strain_energy for e in recovered)
    work = float(fnodal @ d + reactions @ d + distributed_work)
    energy_ratio, energy_error, energy_roundoff = energy_check(
        energy,
        work,
        d,
        k,
        float((np.abs(fnodal) + np.abs(reactions)) @ np.abs(d)) + abs(distributed_work),
    )
    # Length scaling gives translation/rotation stiffness entries compatible units.
    ell = max(item[1].L for item in matrices)
    scale = np.tile([ell, ell, ell, 1, 1, 1], len(nodes))
    khat = k * np.outer(scale, scale)
    symmetry = float(
        np.linalg.norm(khat - khat.T) / max(np.finfo(float).tiny, np.linalg.norm(khat))
    )
    passed = (
        all(e.validation.passed for e in recovered)
        and max(symmetry, force_ratio, moment_ratio, balance_f, balance_m, energy_ratio) <= 1e-8
    )
    validation = GlobalValidation(
        symmetry,
        max(force_ratio, moment_ratio),
        force_ratio,
        moment_ratio,
        force_balance.tolist(),
        moment_balance.tolist(),
        balance_f,
        balance_m,
        float(energy),
        work,
        energy_ratio,
        energy_error,
        energy_roundoff,
        solution.scaled_condition_number,
        bool(passed),
    )
    return FrameAnalysisResult(
        d,
        d.reshape(-1, 6),
        reactions,
        free,
        solution.restrained_dofs,
        solution.inactive_dof_vectors,
        solution.active_dof_count,
        tuple(recovered),
        validation,
    )
