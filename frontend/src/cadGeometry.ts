import type { ModelInput } from './domain'
import {
  getSketch,
  loopPoints,
  syncUnmeshedSurface,
  writeSketch,
  type SketchGeometry,
} from './geometrySketch'
import { nextPrefixedId } from './supports'

export interface HoleDimensions {
  kind: 'circle' | 'rectangle' | 'square'
  width: number
  height: number
  radius: number
}
export interface HoleShape extends HoleDimensions {
  center: number[]
}
export const defaultHoleDimensions: HoleDimensions = {
  kind: 'circle',
  width: 0.4,
  height: 0.2,
  radius: 0.15,
}
const cross = (a: number[], b: number[], c: number[]) =>
  (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
const distance = (a: number[], b: number[]) =>
  Math.hypot(a[0] - b[0], a[1] - b[1])
const onSegment = (a: number[], b: number[], c: number[]) =>
  Math.abs(cross(a, b, c)) < 1e-10 &&
  c[0] >= Math.min(a[0], b[0]) - 1e-10 &&
  c[0] <= Math.max(a[0], b[0]) + 1e-10 &&
  c[1] >= Math.min(a[1], b[1]) - 1e-10 &&
  c[1] <= Math.max(a[1], b[1]) + 1e-10
const intersects = (a: number[], b: number[], c: number[], d: number[]) =>
  (cross(a, b, c) * cross(a, b, d) < 0 &&
    cross(c, d, a) * cross(c, d, b) < 0) ||
  onSegment(a, b, c) ||
  onSegment(a, b, d) ||
  onSegment(c, d, a) ||
  onSegment(c, d, b)
const inside = (p: number[], polygon: number[][]) => {
  let result = false
  polygon.forEach((a, i) => {
    const b = polygon[(i + 1) % polygon.length]
    if (
      a[1] > p[1] !== b[1] > p[1] &&
      p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      result = !result
  })
  return result
}
export function polygonError(points: number[][]): string | null {
  if (points.length < 3) return 'An outline needs at least three vertices.'
  if (
    points.some(
      (p) => p.length < 2 || p.some((value) => !Number.isFinite(value)),
    )
  )
    return 'Coordinates must be finite numbers.'
  for (let i = 0; i < points.length; i++) {
    if (distance(points[i], points[(i + 1) % points.length]) < 1e-9)
      return 'Two adjacent vertices overlap.'
    for (let j = i + 1; j < points.length; j++) {
      if (j === i + 1 || (i === 0 && j === points.length - 1)) continue
      if (
        intersects(
          points[i],
          points[(i + 1) % points.length],
          points[j],
          points[(j + 1) % points.length],
        )
      )
        return 'Outline edges must not cross or touch each other.'
    }
  }
  const area = points.reduce(
    (sum, p, i) =>
      sum +
      p[0] * points[(i + 1) % points.length][1] -
      points[(i + 1) % points.length][0] * p[1],
    0,
  )
  return Math.abs(area) < 1e-12 ? 'The outline must enclose an area.' : null
}
export function holeDimensionError(shape: HoleDimensions): string | null {
  const values =
    shape.kind === 'circle'
      ? [shape.radius]
      : shape.kind === 'square'
        ? [shape.width]
        : [shape.width, shape.height]
  return values.some((value) => !Number.isFinite(value) || value <= 0)
    ? 'Dimensions must be finite and greater than zero.'
    : null
}
export function shapePoints(shape: HoleShape, circleSegments = 4): number[][] {
  const [x, y] = shape.center
  if (shape.kind === 'circle')
    return Array.from({ length: circleSegments }, (_, i) => [
      x + shape.radius * Math.cos((i * 2 * Math.PI) / circleSegments),
      y + shape.radius * Math.sin((i * 2 * Math.PI) / circleSegments),
    ])
  const w = shape.width / 2,
    h = (shape.kind === 'square' ? shape.width : shape.height) / 2
  return [
    [x - w, y - h],
    [x + w, y - h],
    [x + w, y + h],
    [x - w, y + h],
  ]
}
const segmentDistance = (p: number[], a: number[], b: number[]) => {
  const dx = b[0] - a[0],
    dy = b[1] - a[1]
  const t = Math.max(
    0,
    Math.min(
      1,
      ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy),
    ),
  )
  return distance(p, [a[0] + t * dx, a[1] + t * dy])
}
export function sketchError(sketch: SketchGeometry): string | null {
  const outer = sketch.loops.find((loop) => loop.kind === 'outer')
  if (!outer) return 'Draw a closed outer outline.'
  const outline = loopPoints(sketch, outer)
  const outerError = polygonError(outline)
  if (outerError) return outerError
  const holes = sketch.loops.filter((loop) => loop.kind === 'hole')
  const polygons = holes.map((loop) =>
    loop.shape?.kind === 'circle'
      ? shapePoints(loop.shape, 128)
      : loopPoints(sketch, loop),
  )
  for (let i = 0; i < holes.length; i++) {
    const shape = holes[i].shape,
      points = polygons[i]
    const error = shape ? holeDimensionError(shape) : polygonError(points)
    if (error) return error
    if (
      points.some((p) => !inside(p, outline)) ||
      points.some((a, k) =>
        outline.some((b, j) =>
          intersects(
            a,
            points[(k + 1) % points.length],
            b,
            outline[(j + 1) % outline.length],
          ),
        ),
      ) ||
      (shape?.kind === 'circle' &&
        outline.some(
          (a, j) =>
            segmentDistance(
              shape.center,
              a,
              outline[(j + 1) % outline.length],
            ) <= shape.radius,
        ))
    )
      return 'Keep each hole fully inside the outline without touching its edges.'
    for (let j = 0; j < i; j++) {
      const other = polygons[j],
        otherShape = holes[j].shape
      if (
        shape?.kind === 'circle' &&
        otherShape?.kind === 'circle' &&
        distance(shape.center, otherShape.center) <=
          shape.radius + otherShape.radius
      )
        return 'Holes must not overlap or touch.'
      if (
        (shape?.kind === 'circle' &&
          other.some(
            (a, k) =>
              segmentDistance(shape.center, a, other[(k + 1) % other.length]) <=
              shape.radius,
          )) ||
        (otherShape?.kind === 'circle' &&
          points.some(
            (a, k) =>
              segmentDistance(
                otherShape.center,
                a,
                points[(k + 1) % points.length],
              ) <= otherShape.radius,
          ))
      )
        return 'Holes must not overlap or touch.'
      if (
        points.some((p) => inside(p, other)) ||
        other.some((p) => inside(p, points)) ||
        points.some((a, k) =>
          other.some((b, l) =>
            intersects(
              a,
              points[(k + 1) % points.length],
              b,
              other[(l + 1) % other.length],
            ),
          ),
        )
      )
        return 'Holes must not overlap or touch.'
    }
  }
  return null
}
export function replaceOutline(
  model: ModelInput,
  points: number[][],
): ModelInput {
  const error = polygonError(points)
  if (error) throw new Error(error)
  const signedArea = points.reduce(
    (sum, p, i) =>
      sum +
      p[0] * points[(i + 1) % points.length][1] -
      points[(i + 1) % points.length][0] * p[1],
    0,
  )
  const ordered = signedArea < 0 ? [...points].reverse() : points
  const vertices = ordered.map((coordinates, i) => ({
    id: `G${i + 1}`,
    coordinates:
      model.model_family === 'shell'
        ? [...coordinates.slice(0, 2), model.nodes[0]?.coordinates[2] ?? 0]
        : coordinates.slice(0, 2),
  }))
  // A replacement domain starts without the previous domain's boundary conditions.
  return syncUnmeshedSurface(
    writeSketch(
      { ...model, constraints: [], loads: [] },
      {
        vertices,
        loops: [
          { id: 'outer', kind: 'outer', vertexIds: vertices.map((v) => v.id) },
        ],
      },
    ),
  )
}
export function upsertHole(
  model: ModelInput,
  shape: HoleShape,
  holeId?: string,
): { model: ModelInput; id: string } {
  const error = holeDimensionError(shape)
  if (error || shape.center.some((value) => !Number.isFinite(value)))
    throw new Error(error ?? 'Center coordinates must be finite.')
  // Only the active shape's dimensions participate in the stored definition.
  // A blank width from a previous Rectangle proposal must not poison a Circle.
  shape =
    shape.kind === 'circle'
      ? { ...shape, width: shape.radius * 2, height: shape.radius * 2 }
      : shape.kind === 'square'
        ? { ...shape, height: shape.width, radius: shape.width / 2 }
        : { ...shape, radius: Math.min(shape.width, shape.height) / 2 }
  const sketch = getSketch(model)
  const old = sketch.loops.find((loop) => loop.id === holeId)
  const id =
    old?.id ??
    nextPrefixedId(
      'H',
      sketch.loops.map((loop) => loop.id),
    )
  const retained = sketch.vertices.filter(
    (vertex) => !old?.vertexIds.includes(vertex.id),
  )
  const usedIds = sketch.vertices.map((vertex) => vertex.id)
  const vertices = shapePoints(shape).map((coordinates, i) => {
    const vertexId = old?.vertexIds[i] ?? nextPrefixedId('G', usedIds)
    usedIds.push(vertexId)
    return {
      id: vertexId,
      coordinates:
        model.model_family === 'shell'
          ? [...coordinates, sketch.vertices[0]?.coordinates[2] ?? 0]
          : coordinates,
    }
  })
  const loop = {
    id,
    kind: 'hole' as const,
    shape,
    vertexIds: vertices.map((vertex) => vertex.id),
  }
  const next = {
    vertices: [...retained, ...vertices],
    loops: old
      ? sketch.loops.map((item) => (item.id === id ? loop : item))
      : [...sketch.loops, loop],
  }
  const validation = sketchError(next)
  if (validation) throw new Error(validation)
  return { model: writeSketch(model, next), id }
}
