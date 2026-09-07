import type { LoadInput, ModelInput } from './domain'
import { geometryNeedsMesh, type PlacementState } from './geometrySketch'
import { meshBoundaries } from './meshing'
import { MODEL_FAMILIES } from './modelFamilies'
import { nextPrefixedId } from './supports'

export type LoadPlacementKind = 'auto' | 'nodal' | 'line' | 'surface'
export type PlacementTarget =
  | { kind: 'node'; id: string }
  | { kind: 'element'; id: string; localEdge?: number }

/** Only exposed Q4 edges are eligible. Interior cells cannot silently target another cell. */
export function nearestBoundaryEdge(
  model: ModelInput,
  elementId: string,
  point: number[],
): number | undefined {
  const element = model.elements.find((item) => item.id === elementId)
  if (!element || element.node_ids.length !== 4) return undefined
  const owners = new Map<string, number>()
  for (const cell of model.elements)
    cell.node_ids.forEach((id, index) => {
      const key = [id, cell.node_ids[(index + 1) % cell.node_ids.length]]
        .sort()
        .join(':')
      owners.set(key, (owners.get(key) ?? 0) + 1)
    })
  const candidates = element.node_ids.flatMap((id, edge) => {
    const other = element.node_ids[(edge + 1) % 4]
    if (owners.get([id, other].sort().join(':')) !== 1) return []
    const a = model.nodes.find((node) => node.id === id)!.coordinates
    const b = model.nodes.find((node) => node.id === other)!.coordinates
    const dx = b[0] - a[0],
      dy = b[1] - a[1]
    const t = Math.max(
      0,
      Math.min(
        1,
        ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy),
      ),
    )
    return [
      {
        edge,
        distance: Math.hypot(
          point[0] - a[0] - t * dx,
          point[1] - a[1] - t * dy,
        ),
      },
    ]
  })
  return candidates.sort((a, b) => a.distance - b.distance)[0]?.edge
}

export function placeLoad(
  model: ModelInput,
  target: PlacementTarget,
  placement: NonNullable<PlacementState>,
): { model: ModelInput; id: string } {
  if (geometryNeedsMesh(model))
    throw new Error('Generate the updated geometry mesh before placing loads.')
  const requested = placement.loadKind ?? 'auto'
  if (requested === 'nodal' && target.kind !== 'node')
    throw new Error('Click a node for a point load.')
  if (
    (requested === 'line' || requested === 'surface') &&
    target.kind !== 'element'
  )
    throw new Error('Click a member or a surface element for this load.')
  const kind: LoadInput['kind'] =
    target.kind === 'node'
      ? 'nodal'
      : model.model_family === 'frame'
        ? 'element'
        : requested === 'surface'
          ? 'surface'
          : 'edge'
  const previous = model.loads.find((load) => load.id === placement.targetId)
  const dof = MODEL_FAMILIES[model.model_family].primaryLoadDof
  const components =
    kind === 'element'
      ? { qx_i: 0, qy_i: -1, qx_j: 0, qy_j: -1 }
      : { [dof]: dof === 'UX' ? 1 : -1 }
  const id =
    previous?.id ??
    nextPrefixedId(
      'P',
      model.loads.map(
        (load, i) => `P${Number(load.id.match(/(\d+)$/)?.[1] ?? i + 1)}`,
      ),
    )
  const load: LoadInput = {
    id,
    kind,
    coordinate_system: kind === 'element' ? 'local' : 'global',
    components: previous?.kind === kind ? previous.components : components,
  }
  if (target.kind === 'node') {
    if (!model.nodes.some((node) => node.id === target.id))
      throw new Error('Choose a node from the current mesh.')
    load.node_id = target.id
  } else {
    if (!model.elements.some((element) => element.id === target.id))
      throw new Error('Choose an existing element.')
    load.element_id = target.id
    if (kind === 'surface') load.extensions = { element_ids: [target.id] }
    if (kind === 'edge') {
      if (target.localEdge === undefined)
        throw new Error(
          'Click an exposed boundary edge; this element is inside the mesh.',
        )
      const boundary = meshBoundaries(model).find((item) =>
        item.segments.some(
          (segment) =>
            segment.element_id === target.id &&
            segment.local_edge === target.localEdge,
        ),
      )
      load.extensions = boundary
        ? {
            boundary_id: boundary.id,
            edge_node_ids: boundary.node_ids,
            edge_segments: boundary.segments.map((segment) => ({ ...segment })),
            local_edge: target.localEdge,
          }
        : { local_edge: target.localEdge }
    }
  }
  return {
    id,
    model: {
      ...model,
      loads: previous
        ? model.loads.map((item) => (item.id === id ? load : item))
        : [...model.loads, load],
    },
  }
}
