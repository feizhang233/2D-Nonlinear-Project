import type { JsonValue, ModelInput, NodeInput } from './domain'
import { nextPrefixedId } from './supports'

export interface SketchVertex {
  id: string
  coordinates: number[]
}

export interface SketchLoop {
  id: string
  kind: 'outer' | 'hole'
  vertexIds: string[]
}

export interface SketchGeometry {
  vertices: SketchVertex[]
  loops: SketchLoop[]
}

export type CadTool = 'select' | 'add-vertex' | 'add-hole' | 'add-node' | 'add-member'
export type PlacementKind = 'support' | 'load'
export type PlacementState = { kind: PlacementKind; targetId?: string } | null

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const asStringArray = (value: unknown): string[] => (
  Array.isArray(value) ? value.map(String).filter(Boolean) : []
)

export const isSurfaceFamily = (model: ModelInput) => model.model_family !== 'frame'

export const isGeneratedMesh = (model: ModelInput) => {
  if (!isSurfaceFamily(model)) return false
  const gmsh = model.extensions?.gmsh
  return isRecord(gmsh) && gmsh.engine === 'Gmsh'
}

export function parseSketch(value: JsonValue | undefined): SketchGeometry | null {
  if (!isRecord(value)) return null
  const vertices = Array.isArray(value.vertices) ? value.vertices.flatMap((item) => {
    if (!isRecord(item) || typeof item.id !== 'string') return []
    const coordinates = Array.isArray(item.coordinates)
      ? item.coordinates.map(Number).filter((entry) => Number.isFinite(entry))
      : [Number(item.x), Number(item.y)].filter((entry) => Number.isFinite(entry))
    if (coordinates.length < 2) return []
    return [{ id: item.id, coordinates }]
  }) : []
  const loops = Array.isArray(value.loops) ? value.loops.flatMap((item) => {
    if (!isRecord(item) || typeof item.id !== 'string') return []
    const vertexIds = asStringArray(item.vertex_ids ?? item.vertexIds)
    if (vertexIds.length < 3) return []
    return [{
      id: item.id,
      kind: item.kind === 'hole' ? 'hole' as const : 'outer' as const,
      vertexIds,
    }]
  }) : []
  if (!vertices.length || !loops.some((loop) => loop.kind === 'outer')) return null
  return { vertices, loops }
}

export function sketchJson(sketch: SketchGeometry): JsonValue {
  return {
    vertices: sketch.vertices.map((vertex) => ({
      id: vertex.id,
      coordinates: vertex.coordinates,
    })),
    loops: sketch.loops.map((loop) => ({
      id: loop.id,
      kind: loop.kind,
      vertex_ids: loop.vertexIds,
    })),
  }
}

const uniqueOrdered = (ids: string[]) => {
  const seen = new Set<string>()
  return ids.filter((id) => {
    if (seen.has(id)) return false
    seen.add(id)
    return true
  })
}

export function deriveSketch(model: ModelInput): SketchGeometry {
  if (!isSurfaceFamily(model)) {
    return {
      vertices: model.nodes.map((node) => ({ id: node.id, coordinates: [...node.coordinates] })),
      loops: [],
    }
  }
  const edgeCount = new Map<string, [string, string][]>()
  for (const element of model.elements) {
    if (element.node_ids.length !== 4) continue
    const cycle = [...element.node_ids, element.node_ids[0]]
    for (let index = 0; index < 4; index += 1) {
      const start = cycle[index]
      const end = cycle[index + 1]
      const key = [start, end].sort().join('::')
      const owners = edgeCount.get(key) ?? []
      owners.push([start, end])
      edgeCount.set(key, owners)
    }
  }
  const exterior = [...edgeCount.values()].filter((owners) => owners.length === 1).map((owners) => owners[0])
  const adjacency = new Map<string, string[]>()
  for (const [start, end] of exterior) {
    adjacency.set(start, [...(adjacency.get(start) ?? []), end])
    adjacency.set(end, [...(adjacency.get(end) ?? []), start])
  }
  const ordered: string[] = []
  if (adjacency.size) {
    const origin = [...adjacency.keys()].sort((left, right) => {
      const a = model.nodes.find((node) => node.id === left)?.coordinates ?? [0, 0]
      const b = model.nodes.find((node) => node.id === right)?.coordinates ?? [0, 0]
      return (a[0] - b[0]) || (a[1] - b[1])
    })[0]
    let current = origin
    let previous = ''
    for (let step = 0; step < adjacency.size + 2; step += 1) {
      ordered.push(current)
      const next = (adjacency.get(current) ?? []).find((item) => item !== previous)
      if (!next || next === origin) break
      previous = current
      current = next
    }
  }
  const lookup = new Map(model.nodes.map((node) => [node.id, node.coordinates]))
  const vertexIds = collapseCollinear(
    uniqueOrdered(ordered.length >= 3 ? ordered : model.nodes.map((node) => node.id)),
    lookup,
  )
  const vertices = vertexIds.map((id, index) => {
    const node = model.nodes.find((item) => item.id === id)
    return {
      id: `G${index + 1}`,
      coordinates: node ? [...node.coordinates] : [0, 0],
    }
  })
  return {
    vertices,
    loops: [{ id: 'outer', kind: 'outer', vertexIds: vertices.map((vertex) => vertex.id) }],
  }
}

export function getSketch(model: ModelInput): SketchGeometry {
  return parseSketch(model.extensions?.geometry as JsonValue | undefined) ?? deriveSketch(model)
}

export function writeSketch(model: ModelInput, sketch: SketchGeometry): ModelInput {
  return {
    ...model,
    extensions: {
      ...(model.extensions ?? {}),
      geometry: sketchJson(sketch),
    },
  }
}

export function sketchSignature(sketch: SketchGeometry): string {
  return JSON.stringify(sketchJson(sketch))
}

export function geometryNeedsRemesh(model: ModelInput): boolean {
  if (!isGeneratedMesh(model)) return false
  const stored = typeof model.extensions?.geometry_meshed_signature === 'string'
    ? model.extensions.geometry_meshed_signature
    : ''
  return stored !== sketchSignature(getSketch(model))
}

export function geometryNeedsMesh(model: ModelInput): boolean {
  if (!isSurfaceFamily(model)) return false
  if (isGeneratedMesh(model)) return geometryNeedsRemesh(model)
  const sketch = getSketch(model)
  const outer = sketch.loops.find((loop) => loop.kind === 'outer')
  if (!outer || outer.vertexIds.length !== 4) return true
  return sketch.loops.some((loop) => loop.kind === 'hole')
}

export function withMeshedSignature(model: ModelInput): ModelInput {
  return {
    ...model,
    extensions: {
      ...(model.extensions ?? {}),
      geometry_meshed_signature: sketchSignature(getSketch(model)),
    },
  }
}

const vertexMap = (sketch: SketchGeometry) => new Map(sketch.vertices.map((vertex) => [vertex.id, vertex]))

const collapseCollinear = (ids: string[], lookup: Map<string, number[]>): string[] => {
  const points = ids.map((id) => ({ id, coordinates: lookup.get(id) ?? [0, 0] }))
  let changed = true
  while (changed && points.length > 4) {
    changed = false
    for (let index = 0; index < points.length; index += 1) {
      const before = points[(index + points.length - 1) % points.length].coordinates
      const point = points[index].coordinates
      const after = points[(index + 1) % points.length].coordinates
      const left = [point[0] - before[0], point[1] - before[1]]
      const right = [after[0] - point[0], after[1] - point[1]]
      const cross = Math.abs(left[0] * right[1] - left[1] * right[0])
      const scale = Math.max(Math.hypot(left[0], left[1]) * Math.hypot(right[0], right[1]), 1)
      if (cross <= 1e-10 * scale) {
        points.splice(index, 1)
        changed = true
        break
      }
    }
  }
  return points.map((point) => point.id)
}

const pointSegmentDistance = (point: number[], start: number[], end: number[]) => {
  const vx = end[0] - start[0]
  const vy = end[1] - start[1]
  const wx = point[0] - start[0]
  const wy = point[1] - start[1]
  const length2 = vx * vx + vy * vy
  const parameter = length2 <= 0 ? 0 : Math.max(0, Math.min(1, (wx * vx + wy * vy) / length2))
  const dx = point[0] - (start[0] + parameter * vx)
  const dy = point[1] - (start[1] + parameter * vy)
  return dx * dx + dy * dy
}

export function loopPoints(sketch: SketchGeometry, loop: SketchLoop): number[][] {
  const vertices = vertexMap(sketch)
  return loop.vertexIds.map((id) => vertices.get(id)?.coordinates ?? [0, 0])
}

export function nearestSketchVertex(sketch: SketchGeometry, coordinates: number[]): SketchVertex | null {
  if (!sketch.vertices.length) return null
  return sketch.vertices.reduce((best, vertex) => {
    const bestDistance = (best.coordinates[0] - coordinates[0]) ** 2 + (best.coordinates[1] - coordinates[1]) ** 2
    const nextDistance = (vertex.coordinates[0] - coordinates[0]) ** 2 + (vertex.coordinates[1] - coordinates[1]) ** 2
    return nextDistance < bestDistance ? vertex : best
  })
}

export function nearestModelNode(model: ModelInput, coordinates: number[]): NodeInput | undefined {
  if (!model.nodes.length) return undefined
  return model.nodes.reduce((best, node) => {
    const bestDistance = (best.coordinates[0] - coordinates[0]) ** 2 + (best.coordinates[1] - coordinates[1]) ** 2
    const nextDistance = (node.coordinates[0] - coordinates[0]) ** 2 + (node.coordinates[1] - coordinates[1]) ** 2
    return nextDistance < bestDistance ? node : best
  })
}

export function nodeForSketchVertex(model: ModelInput, vertex: SketchVertex): NodeInput | undefined {
  const tagged = model.nodes.find((node) => node.extensions?.geometry_vertex_id === vertex.id)
  return tagged ?? nearestModelNode(model, vertex.coordinates)
}

export function addOuterVertex(model: ModelInput, coordinates: number[], afterId?: string): ModelInput {
  const sketch = getSketch(model)
  const id = nextPrefixedId('G', sketch.vertices.map((vertex) => vertex.id))
  const outer = sketch.loops.find((loop) => loop.kind === 'outer')
  const vertexIds = outer ? [...outer.vertexIds] : []
  const insertAt = afterId ? vertexIds.indexOf(afterId) + 1 : vertexIds.length
  vertexIds.splice(Math.max(0, insertAt), 0, id)
  const next: SketchGeometry = {
    vertices: [...sketch.vertices, { id, coordinates }],
    loops: outer
      ? sketch.loops.map((loop) => (loop.kind === 'outer' ? { ...loop, vertexIds } : loop))
      : [{ id: 'outer', kind: 'outer', vertexIds }, ...sketch.loops],
  }
  return syncUnmeshedSurface(writeSketch(model, next))
}

export function addOuterVertexAt(model: ModelInput, coordinates: number[]): ModelInput {
  const sketch = getSketch(model)
  const outer = sketch.loops.find((loop) => loop.kind === 'outer')
  if (!outer || outer.vertexIds.length < 2) return addOuterVertex(model, coordinates)
  const vertices = vertexMap(sketch)
  let bestAfter = outer.vertexIds[outer.vertexIds.length - 1]
  let best = Infinity
  for (let index = 0; index < outer.vertexIds.length; index += 1) {
    const start = vertices.get(outer.vertexIds[index])?.coordinates ?? [0, 0]
    const end = vertices.get(outer.vertexIds[(index + 1) % outer.vertexIds.length])?.coordinates ?? [0, 0]
    const distance = pointSegmentDistance(coordinates, start, end)
    if (distance < best) {
      best = distance
      bestAfter = outer.vertexIds[index]
    }
  }
  return addOuterVertex(model, coordinates, bestAfter)
}

export function addRectangularHole(model: ModelInput, center: number[], size: number): ModelInput {
  const sketch = getSketch(model)
  const half = Math.max(size, 1e-6) / 2
  const used = [...sketch.vertices.map((vertex) => vertex.id)]
  const holeVertices: SketchVertex[] = [
    { coordinates: [center[0] - half, center[1] - half] },
    { coordinates: [center[0] + half, center[1] - half] },
    { coordinates: [center[0] + half, center[1] + half] },
    { coordinates: [center[0] - half, center[1] + half] },
  ].map((vertex) => {
    const id = nextPrefixedId('G', used)
    used.push(id)
    return { id, coordinates: vertex.coordinates }
  })
  const hole: SketchLoop = {
    id: nextPrefixedId('H', sketch.loops.map((loop) => loop.id)),
    kind: 'hole',
    vertexIds: holeVertices.map((vertex) => vertex.id),
  }
  return syncUnmeshedSurface(writeSketch(model, {
    vertices: [...sketch.vertices, ...holeVertices],
    loops: [...sketch.loops, hole],
  }))
}

export function moveSketchVertex(model: ModelInput, vertexId: string, coordinates: number[]): ModelInput {
  const sketch = getSketch(model)
  const next = {
    ...sketch,
    vertices: sketch.vertices.map((vertex) => (
      vertex.id === vertexId ? { ...vertex, coordinates } : vertex
    )),
  }
  return syncUnmeshedSurface(writeSketch(model, next))
}

export function deleteSketchVertex(model: ModelInput, vertexId: string): ModelInput {
  const sketch = getSketch(model)
  const nextLoops = sketch.loops
    .map((loop) => ({ ...loop, vertexIds: loop.vertexIds.filter((id) => id !== vertexId) }))
    .filter((loop) => loop.kind === 'outer' || loop.vertexIds.length >= 3)
  const outer = nextLoops.find((loop) => loop.kind === 'outer')
  if (!outer || outer.vertexIds.length < 3) return model
  const remaining = new Set(nextLoops.flatMap((loop) => loop.vertexIds))
  return syncUnmeshedSurface(writeSketch(model, {
    vertices: sketch.vertices.filter((vertex) => remaining.has(vertex.id)),
    loops: nextLoops,
  }))
}

export function deleteSketchLoop(model: ModelInput, loopId: string): ModelInput {
  const sketch = getSketch(model)
  const loop = sketch.loops.find((item) => item.id === loopId)
  if (!loop || loop.kind !== 'hole') return model
  const nextLoops = sketch.loops.filter((item) => item.id !== loopId)
  const remaining = new Set(nextLoops.flatMap((item) => item.vertexIds))
  return syncUnmeshedSurface(writeSketch(model, {
    vertices: sketch.vertices.filter((vertex) => remaining.has(vertex.id)),
    loops: nextLoops,
  }))
}

function rebuildQuadIfPossible(model: ModelInput, sketch: SketchGeometry): ModelInput {
  const outer = sketch.loops.find((loop) => loop.kind === 'outer')
  if (!outer || outer.vertexIds.length !== 4 || sketch.loops.some((loop) => loop.kind === 'hole')) {
    return model
  }
  const family = model.model_family
  const materialId = model.materials[0]?.id ?? 'M1'
  const nodes: NodeInput[] = outer.vertexIds.map((id, index) => {
    const vertex = sketch.vertices.find((item) => item.id === id)
    const coordinates = vertex?.coordinates ?? [0, 0]
    return {
      id: `N${index + 1}`,
      coordinates: family === 'shell'
        ? [coordinates[0], coordinates[1], coordinates[2] ?? 0]
        : [coordinates[0], coordinates[1]],
      extensions: { geometry_vertex_id: id },
    }
  })
  const template = model.elements[0]
  return {
    ...model,
    nodes,
    elements: [{
      id: template?.id ?? 'E1',
      formulation: template?.formulation ?? 'Q4-total-lagrangian',
      node_ids: nodes.map((node) => node.id),
      material_id: template?.material_id ?? materialId,
      properties: structuredClone(template?.properties ?? { thickness: 0.1 }),
    }],
  }
}

export function syncUnmeshedSurface(model: ModelInput): ModelInput {
  if (!isSurfaceFamily(model) || isGeneratedMesh(model)) return model
  return rebuildQuadIfPossible(model, getSketch(model))
}

export function addFrameNode(model: ModelInput, coordinates: number[]): { model: ModelInput; nodeId: string } {
  const id = nextPrefixedId('N', model.nodes.map((node) => node.id))
  const node: NodeInput = {
    id,
    coordinates: model.model_family === 'shell' ? [coordinates[0], coordinates[1], 0] : [coordinates[0], coordinates[1]],
  }
  return { model: { ...model, nodes: [...model.nodes, node] }, nodeId: id }
}

export function addFrameMember(model: ModelInput, startId: string, endId: string): ModelInput {
  if (startId === endId) return model
  if (model.elements.some((element) => (
    (element.node_ids[0] === startId && element.node_ids[1] === endId)
    || (element.node_ids[0] === endId && element.node_ids[1] === startId)
  ))) return model
  const familyFormulation = model.elements[0]?.formulation ?? 'frame2d-corotational'
  const properties = structuredClone(model.elements[0]?.properties ?? { area: 0.01, second_moment: 1e-8 })
  const id = nextPrefixedId('E', model.elements.map((element) => element.id))
  return {
    ...model,
    elements: [
      ...model.elements,
      {
        id,
        formulation: familyFormulation,
        node_ids: [startId, endId],
        material_id: model.materials[0]?.id ?? 'M1',
        properties,
      },
    ],
  }
}

export function moveFrameNode(model: ModelInput, nodeId: string, coordinates: number[]): ModelInput {
  return {
    ...model,
    nodes: model.nodes.map((node) => (
      node.id === nodeId
        ? {
            ...node,
            coordinates: node.coordinates.length > 2
              ? [coordinates[0], coordinates[1], node.coordinates[2] ?? 0]
              : [coordinates[0], coordinates[1]],
          }
        : node
    )),
  }
}

export function editablePlacementNodes(model: ModelInput): Array<{ id: string; label: string; coordinates: number[] }> {
  if (isSurfaceFamily(model)) {
    const sketch = getSketch(model)
    return sketch.vertices.map((vertex, index) => ({
      id: nodeForSketchVertex(model, vertex)?.id ?? vertex.id,
      label: `V${index + 1}`,
      coordinates: vertex.coordinates,
    }))
  }
  return model.nodes.map((node, index) => ({
    id: node.id,
    label: `Node ${Number(node.id.replace(/\D/g, '')) || index + 1}`,
    coordinates: node.coordinates,
  }))
}

export function firstFreePlacementNodeId(model: ModelInput): string | undefined {
  const used = new Set(model.constraints.map((item) => item.node_id))
  return editablePlacementNodes(model).find((node) => !used.has(node.id))?.id
}
