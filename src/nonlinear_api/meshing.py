"""Gmsh-backed Q4 surface meshing for Continuum, Plate, and flat Shell models."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from math import hypot
from threading import RLock

import gmsh
import numpy as np

from nonlinear_api.schemas import (
    MeshBoundary,
    MeshBoundarySegment,
    SurfaceMeshRequest,
    SurfaceMeshResponse,
)
from nonlinear_core.model import ElementInput, ModelFamily, NodeInput

_GMSH_LOCK = RLock()
_GMSH_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gmsh-mesher")
_LOCAL_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0))
_SURFACE_FAMILIES = {ModelFamily.CONTINUUM, ModelFamily.PLATE, ModelFamily.SHELL}
_MAX_MESH_NODES = 10_000


class SurfaceMeshError(ValueError):
    """Raised when the current model cannot define a supported Q4 Gmsh surface."""


@contextmanager
def _gmsh_runtime() -> Iterator[None]:
    with _GMSH_LOCK:
        owns_runtime = not bool(gmsh.isInitialized())
        if owns_runtime:
            gmsh.initialize(interruptible=False)
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.option.setNumber("General.NumThreads", 1)
            yield
        finally:
            if owns_runtime and gmsh.isInitialized():
                gmsh.finalize()


def _surface_boundary(model: SurfaceMeshRequest) -> list[tuple[str, np.ndarray]]:
    document = model.model
    if document.model_family not in _SURFACE_FAMILIES:
        raise SurfaceMeshError("Gmsh surface meshing is available for Continuum, Plate, and Shell")
    if not document.elements:
        raise SurfaceMeshError(
            "surface meshing requires at least one Q4 element as a boundary source"
        )

    node_by_id = {node.id: np.asarray(node.coordinates, dtype=float) for node in document.nodes}
    edge_owners: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for element in document.elements:
        if len(element.node_ids) != 4:
            raise SurfaceMeshError(f"element {element.id!r} is not a four-node surface element")
        for left, right in _LOCAL_EDGES:
            start = element.node_ids[left]
            end = element.node_ids[right]
            edge_owners[tuple(sorted((start, end)))].append((start, end))

    exterior = [owners[0] for owners in edge_owners.values() if len(owners) == 1]
    if len(exterior) < 4:
        raise SurfaceMeshError("the current elements do not define a closed exterior boundary")
    adjacency: dict[str, list[str]] = defaultdict(list)
    for start, end in exterior:
        adjacency[start].append(end)
        adjacency[end].append(start)
    if any(len(neighbours) != 2 for neighbours in adjacency.values()):
        raise SurfaceMeshError("only one non-branching exterior boundary is currently supported")

    start_id = min(adjacency, key=lambda node_id: tuple(node_by_id[node_id][:2]))
    ordered = [start_id]
    previous: str | None = None
    current = start_id
    while True:
        candidates = [item for item in adjacency[current] if item != previous]
        if not candidates:
            raise SurfaceMeshError("the exterior boundary is open")
        next_id = candidates[0]
        if next_id == start_id:
            break
        if next_id in ordered:
            raise SurfaceMeshError("the exterior boundary contains more than one loop")
        ordered.append(next_id)
        previous, current = current, next_id
        if len(ordered) > len(adjacency):
            raise SurfaceMeshError("the exterior boundary could not be ordered")
    if len(ordered) != len(adjacency):
        raise SurfaceMeshError("only one exterior loop without holes is currently supported")

    points = [node_by_id[node_id] for node_id in ordered]
    if document.model_family is ModelFamily.SHELL:
        z_values = [float(point[2]) if point.size > 2 else 0.0 for point in points]
        span = max(1.0, max(np.ptp(np.asarray([point[:2] for point in points]), axis=0)))
        if max(z_values) - min(z_values) > 1.0e-9 * span:
            raise SurfaceMeshError(
                "the current Gmsh bridge supports XY-parallel flat Shell geometry"
            )

    signed_area = sum(
        float(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
        )
        for index in range(len(points))
    )
    if signed_area < 0.0:
        ordered.reverse()
        points.reverse()

    # A previous structured mesh contributes collinear boundary nodes. Collapse them
    # back to geometric corners before asking Gmsh to remesh the domain.
    changed = True
    while changed and len(points) > 4:
        changed = False
        for index in range(len(points)):
            before = points[index - 1][:2]
            point = points[index][:2]
            after = points[(index + 1) % len(points)][:2]
            left = point - before
            right = after - point
            cross = abs(float(left[0] * right[1] - left[1] * right[0]))
            scale = max(float(np.linalg.norm(left) * np.linalg.norm(right)), 1.0)
            if cross <= 1.0e-10 * scale:
                del points[index]
                del ordered[index]
                changed = True
                break

    if len(points) < 4:
        raise SurfaceMeshError("the exterior boundary needs at least four non-collinear corners")
    return list(zip(ordered, points, strict=True))


def _edge_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[float, float]:
    vector = end - start
    denominator = float(vector @ vector)
    if denominator <= 0.0:
        return float("inf"), 0.0
    parameter = float((point - start) @ vector / denominator)
    projection = start + min(1.0, max(0.0, parameter)) * vector
    return float(np.linalg.norm(point - projection)), parameter


def _generate_surface_mesh_serialized(request: SurfaceMeshRequest) -> SurfaceMeshResponse:
    """Generate one first-order all-Q4 mesh on the dedicated Gmsh thread."""

    boundary = _surface_boundary(request)
    template = request.model.elements[0]
    z_value = float(boundary[0][1][2]) if boundary[0][1].size > 2 else 0.0

    with _gmsh_runtime():
        gmsh.clear()
        gmsh.model.add("nonlinear-surface")
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMin", request.mesh_size)
        gmsh.option.setNumber("Mesh.MeshSizeMax", request.mesh_size)
        gmsh.option.setNumber("Mesh.Algorithm", 8)
        gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 2)

        point_tags = [
            gmsh.model.geo.addPoint(float(point[0]), float(point[1]), z_value, request.mesh_size)
            for _, point in boundary
        ]
        line_tags = [
            gmsh.model.geo.addLine(point_tags[index], point_tags[(index + 1) % len(point_tags)])
            for index in range(len(point_tags))
        ]
        loop_tag = gmsh.model.geo.addCurveLoop(line_tags)
        surface_tag = gmsh.model.geo.addPlaneSurface([loop_tag])
        gmsh.model.geo.synchronize()

        if len(boundary) == 4:
            lengths = [
                hypot(
                    float(boundary[(index + 1) % 4][1][0] - boundary[index][1][0]),
                    float(boundary[(index + 1) % 4][1][1] - boundary[index][1][1]),
                )
                for index in range(4)
            ]
            divisions = [
                max(1, round((lengths[0] + lengths[2]) / (2.0 * request.mesh_size))),
                max(1, round((lengths[1] + lengths[3]) / (2.0 * request.mesh_size))),
            ]
            for index, line_tag in enumerate(line_tags):
                gmsh.model.mesh.setTransfiniteCurve(line_tag, divisions[index % 2] + 1)
            gmsh.model.mesh.setTransfiniteSurface(surface_tag, cornerTags=point_tags)
        gmsh.model.mesh.setRecombine(2, surface_tag)
        gmsh.model.mesh.generate(2)

        node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
        if len(node_tags) > _MAX_MESH_NODES:
            raise SurfaceMeshError(
                f"Gmsh produced {len(node_tags)} nodes; the interactive limit is {_MAX_MESH_NODES}"
            )
        coordinates_by_tag = {
            int(tag): np.asarray(coordinates[3 * index : 3 * index + 3], dtype=float)
            for index, tag in enumerate(node_tags)
        }
        ordered_tags = sorted(coordinates_by_tag)
        node_id_by_tag = {tag: f"N{index + 1}" for index, tag in enumerate(ordered_tags)}
        nodes = tuple(
            NodeInput(
                id=node_id_by_tag[tag],
                coordinates=(
                    tuple(float(value) for value in coordinates_by_tag[tag])
                    if request.model.model_family is ModelFamily.SHELL
                    else tuple(float(value) for value in coordinates_by_tag[tag][:2])
                ),
                extensions={"gmsh_node_tag": tag},
            )
            for tag in ordered_tags
        )

        element_types, element_tags, element_node_tags = gmsh.model.mesh.getElements(2, surface_tag)
        quads: list[tuple[int, tuple[int, int, int, int]]] = []
        unsupported: list[str] = []
        for element_type, tags, connectivities in zip(
            element_types, element_tags, element_node_tags, strict=True
        ):
            name, _, _, node_count, _, _ = gmsh.model.mesh.getElementProperties(element_type)
            if node_count != 4 or not name.lower().startswith("quad"):
                unsupported.append(f"{name}:{len(tags)}")
                continue
            for index, element_tag in enumerate(tags):
                raw = tuple(int(value) for value in connectivities[index * 4 : index * 4 + 4])
                quad_xy = [coordinates_by_tag[tag][:2] for tag in raw]
                area = sum(
                    float(
                        quad_xy[item][0] * quad_xy[(item + 1) % 4][1]
                        - quad_xy[(item + 1) % 4][0] * quad_xy[item][1]
                    )
                    for item in range(4)
                )
                if area < 0.0:
                    raw = (raw[0], raw[3], raw[2], raw[1])
                quads.append((int(element_tag), raw))
        if unsupported:
            raise SurfaceMeshError(
                "Gmsh did not produce an all-Q4 mesh; unsupported cells: " + ", ".join(unsupported)
            )
        if not quads:
            raise SurfaceMeshError("Gmsh produced no Q4 elements")

        elements = tuple(
            ElementInput(
                id=f"E{index + 1}",
                formulation=template.formulation,
                node_ids=tuple(node_id_by_tag[tag] for tag in connectivity),
                material_id=template.material_id,
                properties=dict(template.properties),
                extensions={"gmsh_element_tag": element_tag},
            )
            for index, (element_tag, connectivity) in enumerate(quads)
        )

    element_by_edge: dict[tuple[str, str], tuple[str, int, tuple[str, str]]] = {}
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    for element in elements:
        for local_edge, (left, right) in enumerate(_LOCAL_EDGES):
            pair = (element.node_ids[left], element.node_ids[right])
            key = tuple(sorted(pair))
            edge_counts[key] += 1
            element_by_edge[key] = (element.id, local_edge, pair)

    node_coordinates = {node.id: np.asarray(node.coordinates[:2], dtype=float) for node in nodes}
    boundary_segments: list[list[tuple[float, MeshBoundarySegment]]] = [[] for _ in boundary]
    for key, count in edge_counts.items():
        if count != 1:
            continue
        element_id, local_edge, pair = element_by_edge[key]
        midpoint = (node_coordinates[pair[0]] + node_coordinates[pair[1]]) / 2.0
        distances = [
            _edge_distance(
                midpoint,
                item[1][:2],
                boundary[(index + 1) % len(boundary)][1][:2],
            )
            for index, item in enumerate(boundary)
        ]
        boundary_index = min(range(len(distances)), key=lambda index: distances[index][0])
        _, start_parameter = _edge_distance(
            node_coordinates[pair[0]],
            boundary[boundary_index][1][:2],
            boundary[(boundary_index + 1) % len(boundary)][1][:2],
        )
        _, end_parameter = _edge_distance(
            node_coordinates[pair[1]],
            boundary[boundary_index][1][:2],
            boundary[(boundary_index + 1) % len(boundary)][1][:2],
        )
        ordered_pair = pair if start_parameter <= end_parameter else (pair[1], pair[0])
        boundary_segments[boundary_index].append(
            (
                min(start_parameter, end_parameter),
                MeshBoundarySegment(
                    element_id=element_id,
                    local_edge=local_edge,
                    node_ids=ordered_pair,
                ),
            )
        )

    boundaries: list[MeshBoundary] = []
    for index, segments_with_parameter in enumerate(boundary_segments):
        segments = tuple(
            item[1] for item in sorted(segments_with_parameter, key=lambda item: item[0])
        )
        if not segments:
            raise SurfaceMeshError(f"Gmsh boundary {index + 1} has no Q4 edge segments")
        ordered_node_ids = (segments[0].node_ids[0],) + tuple(
            segment.node_ids[1] for segment in segments
        )
        length = sum(
            float(
                np.linalg.norm(
                    node_coordinates[segment.node_ids[1]] - node_coordinates[segment.node_ids[0]]
                )
            )
            for segment in segments
        )
        boundaries.append(
            MeshBoundary(
                id=f"B{index + 1}",
                label=f"边界 {index + 1}",
                node_ids=ordered_node_ids,
                segments=segments,
                length=length,
            )
        )

    return SurfaceMeshResponse(
        engine_version=str(gmsh.__version__),
        model_family=request.model.model_family,
        formulation=template.formulation,
        mesh_size=request.mesh_size,
        nodes=nodes,
        elements=elements,
        boundaries=tuple(boundaries),
    )


def generate_surface_mesh(request: SurfaceMeshRequest) -> SurfaceMeshResponse:
    """Generate an all-Q4 mesh while keeping every Gmsh call on one worker thread."""

    return _GMSH_EXECUTOR.submit(_generate_surface_mesh_serialized, request).result()


__all__ = ["SurfaceMeshError", "generate_surface_mesh"]
