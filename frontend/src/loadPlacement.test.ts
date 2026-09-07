import { expect, it } from 'vitest'
import { cloneSampleModel } from './sampleModel'
import { nearestBoundaryEdge, placeLoad } from './loadPlacement'
import { loadDisplayLabel } from './entityLabels'

it('places a point or member load at the clicked entity, keeping unique display numbers', () => {
  const model = cloneSampleModel('frame')
  const point = placeLoad(model, { kind: 'node', id: 'N3' }, { kind: 'load' })
  expect(point.model.loads.at(-1)).toMatchObject({
    node_id: 'N3',
    kind: 'nodal',
  })
  expect(loadDisplayLabel(point.model, point.id)).toBe('Load 2')
  const line = placeLoad(model, { kind: 'element', id: 'E2' }, { kind: 'load' })
  expect(line.model.loads.at(-1)).toMatchObject({
    element_id: 'E2',
    kind: 'element',
    coordinate_system: 'local',
    components: { qy_i: -1, qy_j: -1 },
  })
  expect(model.loads).toHaveLength(1)
})
it('moves a distributed load without converting it to nodal or losing intensity', () => {
  const created = placeLoad(
    cloneSampleModel('frame'),
    { kind: 'element', id: 'E2' },
    { kind: 'load' },
  )
  created.model.loads.at(-1)!.components.qy_i = -2.5e4
  const moved = placeLoad(
    created.model,
    { kind: 'element', id: 'E1' },
    { kind: 'load', targetId: created.id, loadKind: 'line' },
  )
  expect(moved.model.loads).toHaveLength(2)
  expect(moved.model.loads.at(-1)).toMatchObject({
    id: created.id,
    element_id: 'E1',
    components: { qy_i: -2.5e4 },
  })
  expect(() =>
    placeLoad(
      created.model,
      { kind: 'node', id: 'N1' },
      { kind: 'load', loadKind: 'line' },
    ),
  ).toThrow(/member/)
})
it('chooses the clicked Q4 edge and rejects an interior cell without a boundary edge', () => {
  const model = cloneSampleModel('continuum')
  const nodes = model.nodes.map((n) => n.coordinates)
  const edge = nearestBoundaryEdge(model, model.elements[0].id, [
    (nodes[1][0] + nodes[2][0]) / 2,
    (nodes[1][1] + nodes[2][1]) / 2,
  ])
  expect(edge).toBe(1)
  const loaded = placeLoad(
    model,
    { kind: 'element', id: model.elements[0].id, localEdge: edge },
    { kind: 'load' },
  )
  expect(loaded.model.loads.at(-1)).toMatchObject({
    kind: 'edge',
    coordinate_system: 'global',
    extensions: { local_edge: 1 },
  })
  expect(() =>
    placeLoad(
      model,
      { kind: 'element', id: model.elements[0].id },
      { kind: 'load' },
    ),
  ).toThrow(/boundary/)
})
