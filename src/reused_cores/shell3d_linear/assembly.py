"""Global DOF scatter and multi-element assembly for the linear static core.

Assembly follows the input node/element array order. The stored matrix uses
row-sparse accumulation without materializing a global dense ``6N x 6N``
array. ``L_char`` used for mixed translation/rotation scaling is the model-wide
maximum node distance, not the per-element value.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from reused_cores.shell3d_linear.constitutive import ConstitutiveBlocks, build_isotropic_constitutive
from reused_cores.shell3d_linear.drilling import GlobalShellOperator, build_global_shell_operator
from reused_cores.shell3d_linear.geometry import (
    ElementGeometry,
    build_element_geometry,
    pairwise_characteristic_length,
)
from reused_cores.shell3d_linear.loads import (
    add_global_vectors,
    integrate_body_force,
    integrate_edge_traction,
    integrate_surface_traction,
    scatter_element_vector,
    scatter_nodal_load,
)
from reused_cores.shell3d_linear.sparse import SparseMatrix
from reused_cores.shell3d_linear.transformation import GLOBAL_DOF_COUNT
from reused_cores.shell3d_linear.types import (
    AnalysisOptions,
    ElementGeometryRecord,
    NormalizedBodyForce,
    NormalizedConstraint,
    NormalizedEdgeTraction,
    NormalizedNodalLoad,
    NormalizedSurfaceTraction,
    ValidatedModel,
)


@dataclass(frozen=True, slots=True)
class ElementContribution:
    """One element's global 24-DOF operator, consistent load and scatter map."""

    element_id: str
    element_index: int
    dof_indices: tuple[int, ...]
    geometry: ElementGeometry
    constitutive: ConstitutiveBlocks
    operator: GlobalShellOperator
    load_global: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class AssembledSystem:
    """Unconstrained global ``K`` and ``f`` plus the element source map."""

    model_id: str
    load_case_id: str
    model_sha256: str
    dof_count: int
    characteristic_length: float
    stiffness: SparseMatrix
    applied_load: tuple[float, ...]
    elements: tuple[ElementContribution, ...]
    constraints: tuple[NormalizedConstraint, ...]
    analysis_options: AnalysisOptions


def model_characteristic_length(model: ValidatedModel) -> float:
    return pairwise_characteristic_length([node.coordinates for node in model.nodes])


def element_dof_indices(model: ValidatedModel, element: ElementGeometryRecord) -> tuple[int, ...]:
    indices: list[int] = []
    for node_index in element.node_indices:
        indices.extend(model.nodes[node_index].dof_indices)
    if len(indices) != GLOBAL_DOF_COUNT:
        raise ValueError("each Q4 element must scatter onto 24 global DOFs")
    return tuple(indices)


def extract_element_vector(
    global_values: Sequence[float],
    dof_indices: Sequence[int],
) -> tuple[float, ...]:
    if any(index < 0 or index >= len(global_values) for index in dof_indices):
        raise ValueError("element DOF index is outside the assembled range")
    return tuple(global_values[index] for index in dof_indices)


def _element_geometry(model: ValidatedModel, element: ElementGeometryRecord) -> ElementGeometry:
    points = [model.nodes[index].coordinates for index in element.node_indices]
    return build_element_geometry(points)


def _element_constitutive(
    model: ValidatedModel,
    element: ElementGeometryRecord,
) -> ConstitutiveBlocks:
    section = model.sections[element.section_index]
    material = model.materials[section.material_index]
    return build_isotropic_constitutive(
        material.young_modulus,
        material.poisson_ratio,
        section.thickness,
        section.shear_correction_factor,
    )


def _drilling_args(options: AnalysisOptions) -> tuple[float | None, str]:
    drilling = options.drilling
    if drilling.formulation == "continuum_consistent":
        return drilling.alpha_d, "continuum_consistent"
    return None, "none"


def _zero_matrix(size: int) -> list[dict[int, float]]:
    return [{} for _ in range(size)]


def _scatter_stiffness(
    target: list[dict[int, float]],
    dof_indices: Sequence[int],
    element_stiffness: Sequence[Sequence[float]],
) -> None:
    if len(dof_indices) != len(element_stiffness):
        raise ValueError("element stiffness and scatter map must have the same size")
    for row, global_row in enumerate(dof_indices):
        if len(element_stiffness[row]) != len(dof_indices):
            raise ValueError("element stiffness must be square")
        for column, global_column in enumerate(dof_indices):
            value = element_stiffness[row][column]
            if value == 0.0:
                continue
            accumulated = target[global_row].get(global_column, 0.0) + value
            if accumulated == 0.0:
                target[global_row].pop(global_column, None)
            else:
                target[global_row][global_column] = accumulated


def _element_load(
    model: ValidatedModel,
    contribution: ElementContribution,
) -> tuple[float, ...]:
    load = [0.0] * GLOBAL_DOF_COUNT
    transform = contribution.operator.transform
    thickness = contribution.constitutive.thickness
    for item in model.loads:
        if isinstance(item, NormalizedSurfaceTraction):
            if contribution.element_index not in item.element_indices:
                continue
            added = integrate_surface_traction(
                contribution.geometry,
                item.traction_global,
                transform=transform,
            )
        elif isinstance(item, NormalizedEdgeTraction):
            if item.element_index != contribution.element_index:
                continue
            added = integrate_edge_traction(
                contribution.geometry,
                item.local_edge,
                item.traction_global,
                transform=transform,
            )
        elif isinstance(item, NormalizedBodyForce):
            if contribution.element_index not in item.element_indices:
                continue
            added = integrate_body_force(
                contribution.geometry,
                item.force_density_global,
                thickness,
                transform=transform,
            )
        else:
            continue
        for index, value in enumerate(added):
            load[index] += value
    return tuple(load)


def assemble_system(
    model: ValidatedModel,
    analysis_options: AnalysisOptions | None = None,
) -> AssembledSystem:
    """Assemble the unconstrained global stiffness and consistent load."""

    dof_count = 6 * len(model.nodes)
    options = analysis_options or model.analysis_options
    stiffness = _zero_matrix(dof_count)
    applied = [0.0] * dof_count
    contributions: list[ElementContribution] = []
    alpha_d, drilling_formulation = _drilling_args(options)

    for element in model.elements:
        geometry = _element_geometry(model, element)
        constitutive = _element_constitutive(model, element)
        operator = build_global_shell_operator(
            geometry,
            constitutive,
            alpha_d=alpha_d,
            shear_formulation=options.shear_formulation,
            drilling_formulation=drilling_formulation,
        )
        dof_indices = element_dof_indices(model, element)
        contribution = ElementContribution(
            element_id=element.id,
            element_index=element.index,
            dof_indices=dof_indices,
            geometry=geometry,
            constitutive=constitutive,
            operator=operator,
            load_global=(0.0,) * GLOBAL_DOF_COUNT,
        )
        load_global = _element_load(model, contribution)
        contribution = ElementContribution(
            element_id=element.id,
            element_index=element.index,
            dof_indices=dof_indices,
            geometry=geometry,
            constitutive=constitutive,
            operator=operator,
            load_global=load_global,
        )
        _scatter_stiffness(stiffness, dof_indices, operator.k_global)
        added = scatter_element_vector(dof_count, dof_indices, load_global)
        applied = list(add_global_vectors(applied, added))
        contributions.append(contribution)

    for item in model.loads:
        if not isinstance(item, NormalizedNodalLoad):
            continue
        added = scatter_nodal_load(
            dof_count,
            item.node_index,
            item.force_global,
            item.moment_global,
        )
        applied = list(add_global_vectors(applied, added))

    return AssembledSystem(
        model_id=model.model_id,
        load_case_id=model.load_case_id,
        model_sha256=model.model_sha256,
        dof_count=dof_count,
        characteristic_length=model_characteristic_length(model),
        stiffness=SparseMatrix(stiffness),
        applied_load=tuple(applied),
        elements=tuple(contributions),
        constraints=model.constraints,
        analysis_options=options,
    )


def stiffness_symmetry_error(stiffness: Sequence[Sequence[float]]) -> float:
    """Return ``max|K_ij-K_ji| / max|K|``. Zero for an empty matrix."""

    if isinstance(stiffness, SparseMatrix):
        return stiffness.symmetry_error()
    size = len(stiffness)
    if any(len(row) != size for row in stiffness):
        raise ValueError("stiffness must be square")
    worst = 0.0
    scale = 0.0
    for row in range(size):
        for column in range(size):
            value = stiffness[row][column]
            scale = max(scale, abs(value))
            if column > row:
                worst = max(worst, abs(value - stiffness[column][row]))
    if scale == 0.0:
        return 0.0
    return worst / scale


def matrix_vector_product(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
) -> tuple[float, ...]:
    if isinstance(matrix, SparseMatrix):
        return matrix.matvec(vector)
    if len(matrix) != len(vector) or any(len(row) != len(vector) for row in matrix):
        raise ValueError("matrix and vector sizes are incompatible")
    return tuple(
        sum(matrix[row][column] * vector[column] for column in range(len(vector)))
        for row in range(len(vector))
    )


def quadratic_form(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
) -> float:
    product = matrix_vector_product(matrix, vector)
    return sum(vector[index] * product[index] for index in range(len(vector)))


__all__ = [
    "AssembledSystem",
    "ElementContribution",
    "assemble_system",
    "element_dof_indices",
    "extract_element_vector",
    "matrix_vector_product",
    "model_characteristic_length",
    "quadratic_form",
    "stiffness_symmetry_error",
]
