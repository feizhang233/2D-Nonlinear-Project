import { describe, expect, it } from 'vitest'
import type { ModelFamily } from './domain'
import { dofsForModel, MODEL_FAMILY_ORDER } from './modelFamilies'
import { cloneSampleModel } from './sampleModel'

const expectedDofs: Record<ModelFamily, string[]> = {
  frame: ['UX', 'UY', 'RZ'],
  continuum: ['UX', 'UY'],
  plate: ['UX', 'UY', 'UZ', 'RX', 'RY'],
  shell: ['UX', 'UY', 'UZ', 'RX', 'RY', 'RZ'],
}

describe('four-family frontend model contracts', () => {
  it.each(MODEL_FAMILY_ORDER)('provides a complete %s analysis document', (family) => {
    const model = cloneSampleModel(family)
    expect(model.model_family).toBe(family)
    expect(model.nodes.length).toBeGreaterThanOrEqual(family === 'frame' ? 2 : 4)
    expect(model.elements[0].node_ids).toHaveLength(family === 'frame' ? 2 : 4)
    expect(dofsForModel(model)).toEqual(expectedDofs[family])
    expect(model.analysis.step_control.max_steps).toBeGreaterThan(0)
    expect(model.analysis.tolerances.linear_solver).toBeGreaterThan(0)
  })

  it('returns a deep clone so family resets cannot mutate the checked-in example', () => {
    const first = cloneSampleModel('shell')
    first.nodes[0].coordinates[0] = 99
    expect(cloneSampleModel('shell').nodes[0].coordinates[0]).toBe(0)
  })
})
