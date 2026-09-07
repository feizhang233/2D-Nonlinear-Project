import { describe, expect, it } from 'vitest'
import type { SolveResult } from './domain'
import { cloneSampleModel } from './sampleModel'
import { frameDiagrams } from './frameDiagrams'

export function diagramFixture(forces = [0, 10, 20, 0, -10, 0]) {
  const model = cloneSampleModel('frame')
  model.nodes = [{ id: 'N1', coordinates: [0, 0] }, { id: 'N2', coordinates: [2, 0] }]
  model.elements = [{ ...model.elements[0], node_ids: ['N1', 'N2'] }]
  model.loads = []
  const result = { schema_version: '1.0.0', status: 'succeeded', steps: [{ step_index: 1, status: 'accepted', load_factor: 1 }], failures: [], metadata: {},
    post_result: { raw_fields: [{ name: 'element_response', records: [{ element_id: model.elements[0].id, local_end_forces: forces, current_configuration: { length: 2 } }] }], derived_fields: [], metadata: {} },
  } as unknown as SolveResult
  return { model, result }
}

describe('Frame section-force recovery', () => {
  it('recovers a cantilever tip force with correct end signs and constant shear', () => {
    const { model, result } = diagramFixture()
    const points = frameDiagrams(model, result)[0].stations
    expect(points[0].moment).toBe(-20)
    expect(points.at(-1)!.moment).toBe(0)
    expect(points.every(p => p.shear === 10 && p.axial === 0)).toBe(true)
  })
  it('recovers a simply supported UDL parabola and zero midspan shear', () => {
    const { model, result } = diagramFixture([0, 0, -1, 0, 0, 1])
    model.loads = [{ id: 'Q', kind: 'element', element_id: model.elements[0].id, components: { qy_i: -3, qy_j: -3 } }]
    const points = frameDiagrams(model, result)[0].stations
    expect(points[0].moment).toBe(0)
    expect(points.at(-1)!.moment).toBe(0)
    expect(points[0].shear).toBe(3)
    expect(points.at(-1)!.shear).toBe(-3)
    expect(points.find(p => p.ratio === 0.5)!.moment).toBe(1.5)
    expect(points.find(p => p.ratio === 0.5)!.shear).toBe(0)
  })
  it('subtracts only member loads and includes the exact triangular-load bending extremum', () => {
    const { model, result } = diagramFixture([0, 0, -0.8, 0, 0, 1.2])
    model.loads = [{ id: 'Q', kind: 'element', element_id: model.elements[0].id, scale: 2, components: { qy_i: 0, qy_j: -3 } }, { id: 'P', kind: 'nodal', node_id: 'N1', components: { UY: -999 } }]
    const points = frameDiagrams(model, result)[0].stations
    const peak = points.find(p => Math.abs(p.ratio - 1 / Math.sqrt(3)) < 1e-9)!
    expect(peak).toBeTruthy()
    expect(peak.shear).toBeCloseTo(0)
    expect(peak.moment).toBeCloseTo(8 / (3 * Math.sqrt(3)))
  })
  it('does not manufacture missing element recovery or show a result without an accepted state', () => {
    const { model, result } = diagramFixture()
    expect(frameDiagrams(model, { ...result, post_result: null })).toEqual([])
    expect(frameDiagrams(model, { ...result, steps: [] })).toEqual([])
  })
})
