import { expect, it } from 'vitest'
import {
  deleteSelection,
  parseSplitPositions,
  splitFrameElement,
} from './modelOperations'
import { cloneSampleModel } from './sampleModel'
import { assignSection, sectionIdForElement } from './sections'

it('splits a member at custom fractions, retains sections and interpolates loads without changing their resultant', () => {
  const model = assignSection(cloneSampleModel('frame'), 'S1', ['E1', 'E2'])
  model.loads.push({
    id: 'Q',
    kind: 'element',
    element_id: 'E1',
    coordinate_system: 'local',
    scale: 2,
    pattern: 'live',
    components: { qx_i: 2, qx_j: 6, qy_i: -10, qy_j: -30 },
  })
  const before = structuredClone(model)
  const next = splitFrameElement(
    model,
    'E1',
    parseSplitPositions('1/4, 1/2, 0.75'),
  )
  expect(model).toEqual(before)
  expect(next.nodes).toHaveLength(6)
  expect(next.elements).toHaveLength(5)
  const children = next.elements.filter((e) => e.id !== 'E2')
  expect(
    children.every(
      (e) => sectionIdForElement(next, e) === 'S1' && e.material_id === 'M1',
    ),
  ).toBe(true)
  const loads = next.loads.filter((l) => l.kind === 'element')
  expect(loads).toHaveLength(4)
  expect(loads.map((l) => l.components.qy_i)).toEqual([-10, -15, -20, -25])
  expect(loads.map((l) => l.components.qy_j)).toEqual([-15, -20, -25, -30])
  expect(
    loads.reduce(
      (sum, l) => sum + ((l.components.qy_i + l.components.qy_j) / 2) * 0.25,
      0,
    ),
  ).toBe(-20)
  expect(loads.every((l) => l.scale === 2 && l.pattern === 'live')).toBe(true)
  expect(next.constraints).toEqual(model.constraints)
  expect(next.loads[0]).toEqual(model.loads[0])
})
it.each(['', '0', '1', '1/0', 'NaN', '-1/2', '1/2, 0.5'])(
  'rejects invalid cut positions %s',
  (value) => {
    expect(() => parseSplitPositions(value)).toThrow()
  },
)
it('deletes a whole support and attached member loads as reversible model changes', () => {
  const model = cloneSampleModel('frame')
  expect(
    deleteSelection(model, { kind: 'constraints', id: 'N1' }).constraints.some(
      (c) => c.node_id === 'N1',
    ),
  ).toBe(false)
  expect(model.constraints.some((c) => c.node_id === 'N1')).toBe(true)
  expect(deleteSelection(model, { kind: 'loads', id: 'P' }).loads).toHaveLength(
    0,
  )
  expect(() => deleteSelection(model, { kind: 'materials', id: 'M1' })).toThrow(
    /another material/,
  )
  expect(() => deleteSelection(model, { kind: 'nodes', id: 'N1' })).toThrow(
    /connected/,
  )
  expect(() =>
    deleteSelection(cloneSampleModel('plate'), { kind: 'elements', id: 'E1' }),
  ).toThrow(/regenerate/)
})
