"""P8 derived nodal recovery, query, envelope and table export.

Gauss-point resultants are extrapolated to element corners with the bilinear
map that treats the 2x2 Gauss locations as a parent square, then averaged at
shared nodes with element-area weights. All derived tensors are rotated into
one reference basis per node. Raw ``ElementResult`` objects are never mutated.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from reused_cores.shell3d_linear.assembly import AssembledSystem, ElementContribution
from reused_cores.shell3d_linear.constants import GAUSS_2X2_ABSCISSA, Q4_LOCAL_EDGES, Q4_NATURAL_NODES
from reused_cores.shell3d_linear.diagnostics import Diagnostic, json_path, make_diagnostic
from reused_cores.shell3d_linear.q4 import q4_shape
from reused_cores.shell3d_linear.types import (
    AnalysisResult,
    DerivedNodalResult,
    ElementResult,
    GaussPointResult,
    Mat3,
    PostResult,
    ValidatedModel,
    Vec2,
    Vec3,
)

COLLINEAR_DOT = 0.999

ResultantField = Literal["membrane", "bending", "shear"]
EnvelopeSource = Literal["gauss_points", "derived_nodal"]


@dataclass(frozen=True, slots=True)
class ResultantEnvelope:
    """Derived min/max of one resultant component in one explicit basis."""

    field: ResultantField
    component_index: int
    minimum: float
    maximum: float
    min_entity_id: str
    max_entity_id: str
    source: EnvelopeSource
    is_derived: bool
    method: Literal["component_min_max_envelope"]
    reference_basis: Mat3


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(left[index] * right[index] for index in range(len(left)))


def _sub(left: Sequence[float], right: Sequence[float]) -> Vec3:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _unit(vector: Sequence[float]) -> Vec3 | None:
    length = _norm(vector)
    if length == 0.0:
        return None
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def element_area(contribution: ElementContribution) -> float:
    return sum(point.jacobian.det_j * point.weight for point in contribution.geometry.gauss_points)


def bilinear_extrapolation_weights() -> tuple[tuple[float, float, float, float], ...]:
    """Return ``W[node][gauss]`` for ``phi_node = sum_g W[node][g] phi_g``."""

    scale = 1.0 / GAUSS_2X2_ABSCISSA
    weights: list[tuple[float, float, float, float]] = []
    for xi_node, eta_node in Q4_NATURAL_NODES:
        shape = q4_shape(xi_node * scale, eta_node * scale)
        weights.append(shape.n)
    return (weights[0], weights[1], weights[2], weights[3])


def extrapolate_scalar(gauss_values: Sequence[float]) -> tuple[float, float, float, float]:
    if len(gauss_values) != 4:
        raise ValueError("Q4 extrapolation requires four Gauss-point values")
    weights = bilinear_extrapolation_weights()
    return tuple(
        sum(weights[node][gauss] * gauss_values[gauss] for gauss in range(4)) for node in range(4)
    )  # type: ignore[return-value]


def extrapolate_vector(
    gauss_vectors: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    if len(gauss_vectors) != 4:
        raise ValueError("Q4 extrapolation requires four Gauss-point vectors")
    size = len(gauss_vectors[0])
    if any(len(item) != size for item in gauss_vectors):
        raise ValueError("Gauss-point vectors must have a common length")
    nodal = []
    for component in range(size):
        nodal.append(extrapolate_scalar([item[component] for item in gauss_vectors]))
    return tuple(tuple(nodal[component][node] for component in range(size)) for node in range(4))


def transform_in_plane_vector(vector: Sequence[float], source: Mat3, target: Mat3) -> Vec2:
    """Rotate a tangent vector from ``source`` local axes into ``target`` axes."""

    if len(vector) != 2:
        raise ValueError("in-plane vector must have 2 components")
    world = (
        vector[0] * source[0][0] + vector[1] * source[1][0],
        vector[0] * source[0][1] + vector[1] * source[1][1],
        vector[0] * source[0][2] + vector[1] * source[1][2],
    )
    return (_dot(world, target[0]), _dot(world, target[1]))


def transform_in_plane_resultant(voigt: Sequence[float], source: Mat3, target: Mat3) -> Vec3:
    """Rotate membrane/bending Voigt components between local bases."""

    if len(voigt) != 3:
        raise ValueError("in-plane resultant must have 3 Voigt components")
    ex_s, ey_s = source[0], source[1]
    ex_t, ey_t = target[0], target[1]
    a_x, a_y = _dot(ex_s, ex_t), _dot(ey_s, ex_t)
    b_x, b_y = _dot(ex_s, ey_t), _dot(ey_s, ey_t)
    nxx, nyy, nxy = voigt
    return (
        nxx * a_x * a_x + nyy * a_y * a_y + 2.0 * nxy * a_x * a_y,
        nxx * b_x * b_x + nyy * b_y * b_y + 2.0 * nxy * b_x * b_y,
        nxx * a_x * b_x + nyy * a_y * b_y + nxy * (a_x * b_y + a_y * b_x),
    )


def _gauss_in_order(points: Sequence[GaussPointResult]) -> tuple[GaussPointResult, ...]:
    by_id = {point.point_id: point for point in points}
    try:
        return (by_id["G1"], by_id["G2"], by_id["G3"], by_id["G4"])
    except KeyError as exc:
        raise ValueError("element recovery must contain Gauss points G1-G4") from exc


def _element_nodal_resultants(
    element: ElementResult,
) -> tuple[tuple[Vec3, Vec3, Vec2], ...]:
    ordered = _gauss_in_order(element.gauss_points)
    membrane = extrapolate_vector([point.membrane_resultant for point in ordered])
    bending = extrapolate_vector([point.bending_resultant for point in ordered])
    shear = extrapolate_vector([point.shear_resultant for point in ordered])
    return tuple(
        (
            (membrane[node][0], membrane[node][1], membrane[node][2]),
            (bending[node][0], bending[node][1], bending[node][2]),
            (shear[node][0], shear[node][1]),
        )
        for node in range(4)
    )


def _boundary_edges(model: ValidatedModel) -> list[tuple[str, str]]:
    seen: dict[frozenset[str], tuple[str, str]] = {}
    duplicates: set[frozenset[str]] = set()
    for element in model.elements:
        for left, right in Q4_LOCAL_EDGES:
            pair = (element.node_ids[left], element.node_ids[right])
            key = frozenset(pair)
            if key in seen:
                duplicates.add(key)
            else:
                seen[key] = pair
    return [edge for key, edge in seen.items() if key not in duplicates]


def classify_singular_nodes(model: ValidatedModel) -> dict[str, tuple[str, ...]]:
    """Return node id -> reasons among load, support, corner, discontinuity."""

    reasons: dict[str, list[str]] = {node.id: [] for node in model.nodes}
    for load in model.loads:
        if load.type != "nodal_load":
            continue
        if any(component != 0.0 for component in (*load.force_global, *load.moment_global)):
            reasons[load.node_id].append("point_load")
    for constraint in model.constraints:
        if "support" not in reasons[constraint.node_id]:
            reasons[constraint.node_id].append("support")

    attached_sections: dict[str, set[int]] = {node.id: set() for node in model.nodes}
    for element in model.elements:
        for node_id in element.node_ids:
            attached_sections[node_id].add(element.section_index)
    for node_id, sections in attached_sections.items():
        if len(sections) > 1:
            reasons[node_id].append("discontinuity")

    by_id = {node.id: node.coordinates for node in model.nodes}
    at_node: dict[str, list[Vec3]] = {node.id: [] for node in model.nodes}
    for left, right in _boundary_edges(model):
        start = by_id[left]
        end = by_id[right]
        outgoing_left = _unit(_sub(end, start))
        outgoing_right = _unit(_sub(start, end))
        if outgoing_left is not None:
            at_node[left].append(outgoing_left)
        if outgoing_right is not None:
            at_node[right].append(outgoing_right)
    for node_id, directions in at_node.items():
        if not directions:
            continue
        if len(directions) != 2:
            reasons[node_id].append("corner")
            continue
        if _dot(directions[0], directions[1]) > -COLLINEAR_DOT:
            reasons[node_id].append("corner")

    return {node_id: tuple(items) for node_id, items in reasons.items() if items}


def derive_nodal_results(
    model: ValidatedModel,
    assembled: AssembledSystem,
    element_results: Sequence[ElementResult],
) -> tuple[DerivedNodalResult, ...]:
    """Area-weighted nodal average of extrapolated Gauss resultants."""

    by_id = {item.element_id: item for item in element_results}
    contributions = {item.element_id: item for item in assembled.elements}
    node_sources: dict[str, list[tuple[str, float, Mat3, Vec3, Vec3, Vec2]]] = {
        node.id: [] for node in model.nodes
    }
    for record in model.elements:
        element = by_id.get(record.id)
        contribution = contributions.get(record.id)
        if element is None or contribution is None:
            raise ValueError(f"missing recovered fields for element {record.id}")
        area = element_area(contribution)
        if area <= 0.0:
            raise ValueError(f"element {record.id} has non-positive area")
        nodal = _element_nodal_resultants(element)
        basis = element.local_basis
        for local, node_id in enumerate(record.node_ids):
            membrane, bending, shear = nodal[local]
            node_sources[node_id].append((record.id, area, basis, membrane, bending, shear))

    singular = classify_singular_nodes(model)
    derived: list[DerivedNodalResult] = []
    for node in model.nodes:
        samples = node_sources[node.id]
        if not samples:
            continue
        source_ids = tuple(sample[0] for sample in samples)
        reference = samples[0][2]
        membrane_acc = [0.0, 0.0, 0.0]
        bending_acc = [0.0, 0.0, 0.0]
        shear_acc = [0.0, 0.0]
        weight = 0.0
        for _element_id, area, basis, membrane, bending, shear in samples:
            rotated_n = transform_in_plane_resultant(membrane, basis, reference)
            rotated_m = transform_in_plane_resultant(bending, basis, reference)
            rotated_q = transform_in_plane_vector(shear, basis, reference)
            weight += area
            for index in range(3):
                membrane_acc[index] += area * rotated_n[index]
                bending_acc[index] += area * rotated_m[index]
            shear_acc[0] += area * rotated_q[0]
            shear_acc[1] += area * rotated_q[1]
        derived.append(
            DerivedNodalResult(
                node_id=node.id,
                is_derived=True,
                method="gauss_extrapolation_area_weighted_average",
                source_element_ids=source_ids,
                reference_basis=reference,
                membrane_resultant=(
                    membrane_acc[0] / weight,
                    membrane_acc[1] / weight,
                    membrane_acc[2] / weight,
                ),
                bending_resultant=(
                    bending_acc[0] / weight,
                    bending_acc[1] / weight,
                    bending_acc[2] / weight,
                ),
                shear_resultant=(shear_acc[0] / weight, shear_acc[1] / weight),
                singularity_warning=node.id in singular,
            )
        )
    return tuple(derived)


def derived_diagnostics(derived: Sequence[DerivedNodalResult]) -> list[Diagnostic]:
    items = [
        make_diagnostic(
            "SHELL-POST-I001",
            entity_type="postprocess",
            entity_id=None,
            json_path="$.post_result.derived_nodal_results",
            observed=len(derived),
            threshold="derived results marked is_derived=true",
            unit=None,
        )
    ]
    for index, item in enumerate(derived):
        if not item.singularity_warning:
            continue
        items.append(
            make_diagnostic(
                "SHELL-POST-W001",
                entity_type="node",
                entity_id=item.node_id,
                json_path=json_path(["post_result", "derived_nodal_results", index]),
                observed=item.node_id,
                threshold="prefer Gauss-point resultants near singularities",
                unit=None,
            )
        )
    return items


def query_element_result(
    element_results: Sequence[ElementResult],
    element_id: str,
) -> ElementResult | None:
    for item in element_results:
        if item.element_id == element_id:
            return item
    return None


def query_derived_nodal(post_result: PostResult, node_id: str) -> DerivedNodalResult | None:
    for item in post_result.derived_nodal_results:
        if item.node_id == node_id:
            return item
    return None


def _envelopes_from_samples(
    samples: Sequence[tuple[str, Sequence[float], Sequence[float], Sequence[float]]],
    source: EnvelopeSource,
    *,
    reference_basis: Mat3,
) -> tuple[ResultantEnvelope, ...]:
    specs: tuple[tuple[ResultantField, int], ...] = (
        ("membrane", 0),
        ("membrane", 1),
        ("membrane", 2),
        ("bending", 0),
        ("bending", 1),
        ("bending", 2),
        ("shear", 0),
        ("shear", 1),
    )
    envelopes: list[ResultantEnvelope] = []
    for field, component in specs:
        if field == "membrane":
            values = [(row[0], row[1][component]) for row in samples]
        elif field == "bending":
            values = [(row[0], row[2][component]) for row in samples]
        else:
            values = [(row[0], row[3][component]) for row in samples]
        minimum = min(values, key=lambda item: item[1])
        maximum = max(values, key=lambda item: item[1])
        envelopes.append(
            ResultantEnvelope(
                field=field,
                component_index=component,
                minimum=minimum[1],
                maximum=maximum[1],
                min_entity_id=minimum[0],
                max_entity_id=maximum[0],
                source=source,
                is_derived=True,
                method="component_min_max_envelope",
                reference_basis=reference_basis,
            )
        )
    return tuple(envelopes)


def envelope_gauss_resultants(
    element_results: Sequence[ElementResult],
    *,
    target_basis: Mat3 | None = None,
) -> tuple[ResultantEnvelope, ...]:
    if not element_results:
        raise ValueError("envelope requires at least one element result")
    reference = target_basis or element_results[0].local_basis
    samples: list[tuple[str, Sequence[float], Sequence[float], Sequence[float]]] = []
    for element in element_results:
        for point in element.gauss_points:
            samples.append(
                (
                    f"{element.element_id}:{point.point_id}",
                    transform_in_plane_resultant(
                        point.membrane_resultant,
                        element.local_basis,
                        reference,
                    ),
                    transform_in_plane_resultant(
                        point.bending_resultant,
                        element.local_basis,
                        reference,
                    ),
                    transform_in_plane_vector(
                        point.shear_resultant,
                        element.local_basis,
                        reference,
                    ),
                )
            )
    return _envelopes_from_samples(
        samples,
        "gauss_points",
        reference_basis=reference,
    )


def envelope_derived_resultants(
    derived: Sequence[DerivedNodalResult],
    *,
    target_basis: Mat3 | None = None,
) -> tuple[ResultantEnvelope, ...]:
    if not derived:
        raise ValueError("envelope requires at least one derived nodal result")
    reference = target_basis or derived[0].reference_basis
    samples = [
        (
            item.node_id,
            transform_in_plane_resultant(
                item.membrane_resultant,
                item.reference_basis,
                reference,
            ),
            transform_in_plane_resultant(
                item.bending_resultant,
                item.reference_basis,
                reference,
            ),
            transform_in_plane_vector(
                item.shear_resultant,
                item.reference_basis,
                reference,
            ),
        )
        for item in derived
    ]
    return _envelopes_from_samples(
        samples,
        "derived_nodal",
        reference_basis=reference,
    )


def _csv(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def analysis_tables(result: AnalysisResult) -> dict[str, str]:
    """Return versioned CSV tables. These are export adapters, not a new schema."""

    if result.status != "succeeded" or result.element_results is None or result.balance is None:
        raise ValueError("table export requires a succeeded AnalysisResult")
    gauss_rows: list[list[object]] = []
    for element in result.element_results:
        basis = [component for row in element.local_basis for component in row]
        for point in element.gauss_points:
            gauss_rows.append(
                [
                    element.element_id,
                    point.point_id,
                    False,
                    element.coordinate_system,
                    *basis,
                    *point.membrane_resultant,
                    *point.bending_resultant,
                    *point.shear_resultant,
                    *point.stress_top,
                    *point.stress_bottom,
                ]
            )
    metadata_rows: list[list[object]] = [
        ["schema_version", result.schema_version],
        ["core_version", result.source.core_version],
        ["model_id", result.source.model_id],
        ["load_case_id", result.source.load_case_id],
        ["model_sha256", result.source.model_sha256],
    ]
    metadata_rows.extend([f"unit.{key}", value] for key, value in result.units.to_dict().items())
    tables = {
        "schema_version": result.schema_version,
        "metadata": _csv(("key", "value"), metadata_rows),
        "gauss_points": _csv(
            (
                "element_id",
                "point_id",
                "is_derived",
                "coordinate_system",
                "basis_ex_x",
                "basis_ex_y",
                "basis_ex_z",
                "basis_ey_x",
                "basis_ey_y",
                "basis_ey_z",
                "basis_ez_x",
                "basis_ez_y",
                "basis_ez_z",
                "N_xx",
                "N_yy",
                "N_xy",
                "M_xx",
                "M_yy",
                "M_xy",
                "Q_x",
                "Q_y",
                "S_top_xx",
                "S_top_yy",
                "S_top_xy",
                "S_bot_xx",
                "S_bot_yy",
                "S_bot_xy",
            ),
            gauss_rows,
        ),
        "energy": _csv(
            ("element_id", "is_derived", "membrane", "bending", "shear", "drilling", "total"),
            [
                [
                    item.element_id,
                    False,
                    item.energy.membrane,
                    item.energy.bending,
                    item.energy.shear,
                    item.energy.drilling,
                    item.energy.total,
                ]
                for item in result.element_results
            ],
        ),
    }
    if result.post_result is not None and result.post_result.derived_nodal_results:
        tables["derived_nodal"] = _csv(
            (
                "node_id",
                "is_derived",
                "method",
                "source_element_ids",
                "singularity_warning",
                "basis_ex_x",
                "basis_ex_y",
                "basis_ex_z",
                "basis_ey_x",
                "basis_ey_y",
                "basis_ey_z",
                "basis_ez_x",
                "basis_ez_y",
                "basis_ez_z",
                "N_xx",
                "N_yy",
                "N_xy",
                "M_xx",
                "M_yy",
                "M_xy",
                "Q_x",
                "Q_y",
            ),
            [
                [
                    item.node_id,
                    True,
                    item.method,
                    " ".join(item.source_element_ids),
                    item.singularity_warning,
                    *(component for row in item.reference_basis for component in row),
                    *item.membrane_resultant,
                    *item.bending_resultant,
                    *item.shear_resultant,
                ]
                for item in result.post_result.derived_nodal_results
            ],
        )
    return tables


def dump_analysis_tables(
    result: AnalysisResult,
    directory: str | Path,
) -> dict[str, Path]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, text in analysis_tables(result).items():
        if name == "schema_version":
            continue
        path = target / f"{name}.csv"
        path.write_text(text, encoding="utf-8")
        written[name] = path
    return written


__all__ = [
    "ResultantEnvelope",
    "analysis_tables",
    "bilinear_extrapolation_weights",
    "classify_singular_nodes",
    "derive_nodal_results",
    "derived_diagnostics",
    "dump_analysis_tables",
    "element_area",
    "envelope_derived_resultants",
    "envelope_gauss_resultants",
    "extrapolate_scalar",
    "extrapolate_vector",
    "query_derived_nodal",
    "query_element_result",
    "transform_in_plane_resultant",
    "transform_in_plane_vector",
]
