import { describe, expect, it } from 'vitest'
import { dofsForModel } from './modelFamilies'
import { cloneSampleModel } from './sampleModel'
import { classifySupport, groupedSupports } from './supports'

describe('constraint support classification', () => {
  it('groups the shallow-arch supports by class instead of individual DOF records', () => {
    const model = cloneSampleModel('frame')
    const grouped = groupedSupports(model, dofsForModel(model))
    expect(grouped.nodeCount).toBe(3)
    expect(grouped.recordCount).toBe(8)
    expect(grouped.groups.map((group) => group.label)).toEqual(['Fixed', 'Custom'])
    expect(grouped.groups[0].items.map((item) => item.nodeId)).toEqual(['N1', 'N3'])
    expect(grouped.groups[1].items.map((item) => item.nodeId)).toEqual(['N2'])
  })

  it('classifies continuum and shell supports', () => {
    const continuum = cloneSampleModel('continuum')
    const shell = cloneSampleModel('shell')
    expect(classifySupport(dofsForModel(continuum), continuum.constraints.filter((item) => item.node_id === 'N1'))).toBe('fixed')
    expect(classifySupport(dofsForModel(continuum), continuum.constraints.filter((item) => item.node_id === 'N4'))).toBe('roller')
    expect(groupedSupports(shell, dofsForModel(shell)).groups).toEqual([
      expect.objectContaining({ label: 'Fixed', items: [expect.objectContaining({ nodeId: 'N1' }), expect.objectContaining({ nodeId: 'N4' })] }),
    ])
  })
})
