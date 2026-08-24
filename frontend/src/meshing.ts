import type {
  JsonValue, LoadInput, MeshBoundary, ModelInput, NodeInput, SurfaceMeshResponse,
} from './domain'

const objectValue = (value: JsonValue | undefined): Record<string, JsonValue> | undefined => (
  value && typeof value === 'object' && !Array.isArray(value) ? value : undefined
)

const segmentJson = (segment: MeshBoundary['segments'][number]): JsonValue => ({
  element_id: segment.element_id,
  local_edge: segment.local_edge,
  node_ids: segment.node_ids,
})

const boundaryJson = (boundary: MeshBoundary): JsonValue => ({
  id: boundary.id,
  label: boundary.label,
  node_ids: boundary.node_ids,
  segments: boundary.segments.map(segmentJson),
  length: boundary.length,
})

export interface MeshStatus {
  generatedByGmsh: boolean
  sourceLabel: string
  nodeCount: number
  elementCount: number
}

export function meshStatusForModel(model: ModelInput): MeshStatus {
  const gmsh = objectValue(model.extensions?.gmsh)
  const generatedByGmsh = gmsh?.engine === 'Gmsh'
  const engineVersion = typeof gmsh?.engine_version === 'string' ? gmsh.engine_version : ''
  return {
    generatedByGmsh,
    sourceLabel: generatedByGmsh ? `Gmsh${engineVersion ? ` ${engineVersion}` : ''}` : 'Current topology',
    nodeCount: model.nodes.length,
    elementCount: model.elements.length,
  }
}

export function meshSizeForModel(model: ModelInput): number {
  const gmsh = objectValue(model.extensions?.gmsh)
  const configured = Number(gmsh?.mesh_size)
  if (Number.isFinite(configured)) return configured
  const xs = model.nodes.map((node) => node.coordinates[0] ?? 0)
  const ys = model.nodes.map((node) => node.coordinates[1] ?? 0)
  const span = Math.max(
    xs.length ? Math.max(...xs) - Math.min(...xs) : 1,
    ys.length ? Math.max(...ys) - Math.min(...ys) : 1,
    1e-6,
  )
  return span / 4
}

export function withMeshSize(model: ModelInput, meshSize: number): ModelInput {
  const gmsh = objectValue(model.extensions?.gmsh) ?? {}
  return {
    ...model,
    extensions: {
      ...(model.extensions ?? {}),
      gmsh: { ...gmsh, mesh_size: meshSize },
    },
  }
}

export function meshBoundaries(model: ModelInput): MeshBoundary[] {
  const gmsh = objectValue(model.extensions?.gmsh)
  const raw = gmsh?.boundaries
  if (!Array.isArray(raw)) return []
  return raw.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return []
    const boundary = candidate as Record<string, JsonValue>
    if (typeof boundary.id !== 'string' || typeof boundary.label !== 'string'
      || !Array.isArray(boundary.node_ids) || !Array.isArray(boundary.segments)) return []
    const segments = boundary.segments.flatMap((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) return []
      const segment = item as Record<string, JsonValue>
      if (typeof segment.element_id !== 'string' || typeof segment.local_edge !== 'number'
        || !Array.isArray(segment.node_ids) || segment.node_ids.length !== 2
        || segment.node_ids.some((nodeId) => typeof nodeId !== 'string')) return []
      return [{
        element_id: segment.element_id,
        local_edge: segment.local_edge,
        node_ids: [String(segment.node_ids[0]), String(segment.node_ids[1])] as [string, string],
      }]
    })
    return [{
      id: boundary.id,
      label: boundary.label,
      node_ids: boundary.node_ids.map(String),
      segments,
      length: Number(boundary.length ?? 0),
    }]
  })
}

const distanceSquared = (left: number[], right: number[]) => {
  const size = Math.max(left.length, right.length)
  let result = 0
  for (let index = 0; index < size; index += 1) {
    const delta = (left[index] ?? 0) - (right[index] ?? 0)
    result += delta * delta
  }
  return result
}

const nearestNodeId = (coordinates: number[], nodes: NodeInput[]) => (
  nodes.reduce((best, candidate) => (
    distanceSquared(coordinates, candidate.coordinates) < distanceSquared(coordinates, best.coordinates)
      ? candidate : best
  ), nodes[0]).id
)

const edgeMidpoint = (load: LoadInput, model: ModelInput): number[] | null => {
  if (!load.element_id) return null
  const element = model.elements.find((candidate) => candidate.id === load.element_id)
  const localEdge = Number(load.extensions?.local_edge)
  if (!element || !Number.isInteger(localEdge) || localEdge < 0 || localEdge > 3) return null
  const edgeNodes = [[0, 1], [1, 2], [2, 3], [3, 0]][localEdge]
  const left = model.nodes.find((node) => node.id === element.node_ids[edgeNodes[0]])
  const right = model.nodes.find((node) => node.id === element.node_ids[edgeNodes[1]])
  if (!left || !right) return null
  return left.coordinates.map((value, index) => (value + (right.coordinates[index] ?? 0)) / 2)
}

const boundaryMidpoint = (boundary: MeshBoundary, nodes: Map<string, NodeInput>): number[] => {
  const points = boundary.node_ids.map((id) => nodes.get(id)).filter(Boolean) as NodeInput[]
  if (!points.length) return [0, 0]
  const size = Math.max(...points.map((point) => point.coordinates.length))
  return Array.from({ length: size }, (_, index) => (
    points.reduce((sum, point) => sum + (point.coordinates[index] ?? 0), 0) / points.length
  ))
}

const bindEdgeLoad = (
  load: LoadInput,
  previous: ModelInput,
  response: SurfaceMeshResponse,
): LoadInput => {
  if (!response.boundaries.length) return load
  const requestedBoundaryId = typeof load.extensions?.boundary_id === 'string'
    ? load.extensions.boundary_id : null
  const nodeById = new Map(response.nodes.map((node) => [node.id, node]))
  const oldMidpoint = edgeMidpoint(load, previous)
  const boundary = response.boundaries.find((item) => item.id === requestedBoundaryId)
    ?? (oldMidpoint
      ? response.boundaries.reduce((best, candidate) => (
        distanceSquared(oldMidpoint, boundaryMidpoint(candidate, nodeById))
          < distanceSquared(oldMidpoint, boundaryMidpoint(best, nodeById)) ? candidate : best
      ), response.boundaries[0])
      : response.boundaries[0])
  if (!boundary?.segments.length) return load
  return {
    ...load,
    element_id: boundary.segments[0].element_id,
    extensions: {
      ...(load.extensions ?? {}),
      boundary_id: boundary.id,
      edge_node_ids: boundary.node_ids,
      edge_segments: boundary.segments.map(segmentJson),
      local_edge: boundary.segments[0].local_edge,
    },
  }
}

export function applySurfaceMesh(model: ModelInput, response: SurfaceMeshResponse): ModelInput {
  if (!response.nodes.length || !response.elements.length) throw new Error('Gmsh returned an empty mesh')
  const oldNodeById = new Map(model.nodes.map((node) => [node.id, node]))
  const remapNode = (nodeId: string) => {
    const oldNode = oldNodeById.get(nodeId)
    return oldNode ? nearestNodeId(oldNode.coordinates, response.nodes) : response.nodes[0].id
  }
  const remappedConstraints = model.constraints.map((constraint) => ({
    ...constraint, node_id: remapNode(constraint.node_id),
  })).filter((constraint, index, all) => (
    all.findIndex((candidate) => candidate.node_id === constraint.node_id && candidate.dof === constraint.dof) === index
  ))
  for (const boundary of response.boundaries) {
    const first = boundary.node_ids[0]
    const last = boundary.node_ids[boundary.node_ids.length - 1]
    const firstConstraints = remappedConstraints.filter((constraint) => constraint.node_id === first)
    for (const firstConstraint of firstConstraints) {
      const matchingLast = remappedConstraints.find((constraint) => (
        constraint.node_id === last && constraint.dof === firstConstraint.dof
          && Number(constraint.value ?? 0) === Number(firstConstraint.value ?? 0)
      ))
      if (!matchingLast) continue
      for (const [index, nodeId] of boundary.node_ids.slice(1, -1).entries()) {
        if (remappedConstraints.some((constraint) => (
          constraint.node_id === nodeId && constraint.dof === firstConstraint.dof
        ))) continue
        remappedConstraints.push({
          ...firstConstraint,
          id: `GM-${boundary.id}-${firstConstraint.dof}-${index + 1}`,
          node_id: nodeId,
          extensions: { ...(firstConstraint.extensions ?? {}), gmsh_boundary_id: boundary.id },
        })
      }
    }
  }
  const remappedLoads = model.loads.map((load) => {
    if (load.kind === 'nodal' && load.node_id) return { ...load, node_id: remapNode(load.node_id) }
    if (load.kind === 'surface') return {
      ...load,
      element_id: response.elements[0].id,
      extensions: { ...(load.extensions ?? {}), element_ids: response.elements.map((element) => element.id) },
    }
    if (load.kind === 'edge') return bindEdgeLoad(load, model, response)
    return load
  })
  const displacement = model.analysis.displacement_control
  return {
    ...model,
    nodes: response.nodes,
    elements: response.elements,
    loads: remappedLoads,
    constraints: remappedConstraints,
    analysis: displacement ? {
      ...model.analysis,
      displacement_control: {
        ...displacement,
        target: { ...displacement.target, node_id: remapNode(displacement.target.node_id) },
      },
    } : model.analysis,
    extensions: {
      ...(model.extensions ?? {}),
      gmsh: {
        engine: response.engine,
        engine_version: response.engine_version,
        mesh_size: response.mesh_size,
        formulation: response.formulation,
        node_count: response.nodes.length,
        element_count: response.elements.length,
        boundaries: response.boundaries.map(boundaryJson),
      },
    },
  }
}
