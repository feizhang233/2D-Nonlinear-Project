import { describe, expect, it } from 'vitest'
import { dofsForModel } from './modelFamilies'
import { cloneSampleModel } from './sampleModel'
import { addNodalLoadAtNode, addSupportAtNode, classifySupport, groupedSupports, nextPrefixedId, nextSupportNumber } from './supports'

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

describe('stable support and load identifiers', () => {
  it('appends the next unused prefixed id instead of filling gaps from 1', () => {
    expect(nextPrefixedId('P', ['P'])).toBe('P2')
    expect(nextPrefixedId('P', ['P1', 'P3'])).toBe('P4')
    expect(nextPrefixedId('N', ['N2', 'N10'])).toBe('N11')
  })

  it('numbers a new support after the highest existing support, not from 1', () => {
    const model = cloneSampleModel('continuum')
    expect(nextSupportNumber(model)).toBe(5)
    const next = addSupportAtNode(model, 'N2', dofsForModel(model))
    expect(next.constraints.filter((item) => item.node_id === 'N2').every((item) => item.extensions?.support_number === 5)).toBe(true)
  })

  it('appends a new load id after the sample load named P', () => {
    const model = cloneSampleModel('frame')
    const added = addNodalLoadAtNode(model, 'N2', 'UY', -1)
    expect(added.id).toBe('P2')
    expect(added.model.loads.map((item) => item.id)).toEqual(['P', 'P2'])
  })
})
