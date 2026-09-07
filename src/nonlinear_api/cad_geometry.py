"""Validate user-drawn planar loops before they reach the native mesher."""

from __future__ import annotations

from math import cos, hypot, isfinite, pi, sin


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _touch(a, b, p):
    return abs(_cross(a, b, p)) <= 1e-10 and all(
        min(a[i], b[i]) - 1e-10 <= p[i] <= max(a[i], b[i]) + 1e-10 for i in (0, 1)
    )


def _intersects(a, b, c, d):
    return (_cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0) or any(
        (_touch(a, b, c), _touch(a, b, d), _touch(c, d, a), _touch(c, d, b))
    )


def _edges(points):
    return list(zip(points, points[1:] + points[:1], strict=True))


def _inside(p, points):
    result = False
    for a, b in _edges(points):
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (
            b[1] - a[1]
        ) + a[0]:
            result = not result
    return result


def _segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def validate_geometry(geometry: dict) -> dict[frozenset[str], dict]:
    """Return validated circle definitions indexed by their four arc endpoints."""
    vertices, loops = geometry.get("vertices"), geometry.get("loops")
    if not isinstance(vertices, list) or not isinstance(loops, list) or not loops:
        raise ValueError("Geometry needs vertices and one closed outer loop")
    lookup = {}
    for vertex in vertices:
        if not isinstance(vertex, dict) or not isinstance(vertex.get("id"), str):
            raise ValueError("Geometry vertices need unique IDs and finite coordinates")
        coords = vertex.get("coordinates")
        if (
            not isinstance(coords, list)
            or len(coords) not in (2, 3)
            or any(not isinstance(v, (int, float)) or not isfinite(v) for v in coords)
        ):
            raise ValueError("Geometry coordinates must be finite 2D or 3D points")
        if vertex["id"] in lookup:
            raise ValueError("Geometry vertex IDs must be unique")
        lookup[vertex["id"]] = coords
    if sum(loop.get("kind") == "outer" for loop in loops if isinstance(loop, dict)) != 1:
        raise ValueError("Geometry needs exactly one outer loop")
    if len({p[2] if len(p) == 3 else 0 for p in lookup.values()}) > 1:
        raise ValueError("Surface geometry must be planar and parallel to XY")
    circles, polygons, shapes = {}, [], []
    for loop in sorted(loops, key=lambda item: item.get("kind") != "outer"):
        ids = loop.get("vertex_ids", loop.get("vertexIds"))
        if (
            not isinstance(ids, list)
            or len(ids) < 3
            or len(set(ids)) != len(ids)
            or any(key not in lookup for key in ids)
        ):
            raise ValueError("Each geometry loop needs at least three distinct existing vertices")
        points = [lookup[key][:2] for key in ids]
        shape = loop.get("shape")
        if shape:
            kind, center = shape.get("kind"), shape.get("center")
            if (
                kind not in ("circle", "rectangle", "square")
                or not isinstance(center, list)
                or len(center) != 2
                or any(not isinstance(n, (int, float)) or not isfinite(n) for n in center)
            ):
                raise ValueError("Hole shape and center are invalid")
            names = (
                ["radius"]
                if kind == "circle"
                else ["width"]
                if kind == "square"
                else ["width", "height"]
            )
            if any(
                not isinstance(shape.get(key), (int, float))
                or not isfinite(shape[key])
                or shape[key] <= 0
                for key in names
            ):
                raise ValueError("Hole dimensions must be finite and positive")
            if loop.get("kind") != "hole" or len(ids) != 4:
                raise ValueError("Parameterized holes need four defining vertices")
            x, y = center
            if kind == "circle":
                r = shape["radius"]
                expected = [[x + r * cos(i * pi / 2), y + r * sin(i * pi / 2)] for i in range(4)]
                circles[frozenset(ids)] = shape
            else:
                w, h = shape["width"] / 2, shape["width" if kind == "square" else "height"] / 2
                expected = [[x - w, y - h], [x + w, y - h], [x + w, y + h], [x - w, y + h]]
            if any(
                hypot(a[0] - b[0], a[1] - b[1]) > 1e-8 * max(1, abs(x), abs(y))
                for a, b in zip(points, expected, strict=True)
            ):
                raise ValueError("Hole dimensions do not match the stored geometry vertices")
        edges = _edges(points)
        if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < 1e-12:
            raise ValueError("Geometry loops must enclose a nonzero area")
        for i, (a, b) in enumerate(edges):
            if hypot(a[0] - b[0], a[1] - b[1]) < 1e-9:
                raise ValueError("Adjacent geometry vertices overlap")
            for j, (c, d) in enumerate(edges):
                if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if _intersects(a, b, c, d):
                    raise ValueError("Geometry edges must not cross or touch")
        if shape and shape["kind"] == "circle":
            x, y = shape["center"]
            points = [
                [x + shape["radius"] * cos(i * pi / 64), y + shape["radius"] * sin(i * pi / 64)]
                for i in range(128)
            ]
        polygons.append(points)
        shapes.append(shape)
    outer = polygons[0]
    for i in range(1, len(polygons)):
        points, shape = polygons[i], shapes[i]
        if not all(_inside(p, outer) for p in points) or any(
            _intersects(a, b, c, d) for a, b in _edges(points) for c, d in _edges(outer)
        ):
            raise ValueError("Holes must lie strictly inside the outer outline")
        if (
            shape
            and shape["kind"] == "circle"
            and any(
                _segment_distance(shape["center"], a, b) <= shape["radius"]
                for a, b in _edges(outer)
            )
        ):
            raise ValueError("Circle holes must not touch the outer outline")
        for j in range(1, i):
            other, other_shape = polygons[j], shapes[j]
            if (
                shape
                and other_shape
                and shape["kind"] == other_shape["kind"] == "circle"
                and hypot(
                    shape["center"][0] - other_shape["center"][0],
                    shape["center"][1] - other_shape["center"][1],
                )
                <= shape["radius"] + other_shape["radius"]
            ):
                raise ValueError("Holes must not overlap or touch")
            if (
                any(_inside(p, other) for p in points)
                or any(_inside(p, points) for p in other)
                or any(_intersects(a, b, c, d) for a, b in _edges(points) for c, d in _edges(other))
            ):
                raise ValueError("Holes must not overlap or touch")
    return circles
