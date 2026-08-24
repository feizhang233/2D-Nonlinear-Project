import { describe, expect, it } from 'vitest'
import {
  elementDisplayLabel,
  loadDisplayLabel,
  materialDisplayLabel,
  modelDisplayLabel,
  nodeDisplayLabel,
  supportDisplayLabel,
  withEntityDisplayName,
} from './entityLabels'
import { dofsForModel } from './modelFamilies'
import { addNodalLoadAtNode, addSupportAtNode } from './supports'
import { cloneSampleModel } from './sampleModel'

describe('entity display labels', () => {
  it('keeps solver IDs internal and exposes stable numbered names', () => {
    const model = cloneSampleModel('frame')

    expect(modelDisplayLabel()).toBe('Model 1')
    expect(nodeDisplayLabel(model, 'N1')).toBe('Node 1')
    expect(elementDisplayLabel(model, 'E2')).toBe('Element 2')
    expect(materialDisplayLabel(model, 'M1')).toBe('Material 1')
    expect(supportDisplayLabel(model, 'N3')).toBe('Support 3')
    expect(loadDisplayLabel(model, 'P')).toBe('Load 1')
  })

  it('persists custom names in UI metadata without changing solver IDs', () => {
    const model = cloneSampleModel('frame')
    const renamedMaterial = withEntityDisplayName(model, 'materials', 'M1', 'High-strength steel')
    const renamedSupport = withEntityDisplayName(renamedMaterial, 'constraints', 'N1', 'West abutment')
    const renamedLoad = withEntityDisplayName(renamedSupport, 'loads', 'P', 'Service load')

    expect(materialDisplayLabel(renamedLoad, 'M1')).toBe('High-strength steel')
    expect(supportDisplayLabel(renamedLoad, 'N1')).toBe('West abutment')
    expect(loadDisplayLabel(renamedLoad, 'P')).toBe('Service load')
    expect(renamedLoad.materials[0].id).toBe('M1')
    expect(renamedLoad.constraints[0].node_id).toBe('N1')
    expect(renamedLoad.loads[0].id).toBe('P')
    expect(renamedLoad.extensions?.ui).toBeTruthy()
  })

  it('keeps existing load and support numbers when a later entity is added', () => {
    const model = cloneSampleModel('frame')
    const withLoad = addNodalLoadAtNode(model, 'N2', 'UY', -50)
    expect(loadDisplayLabel(withLoad.model, 'P')).toBe('Load 1')
    expect(loadDisplayLabel(withLoad.model, withLoad.id)).toBe('Load 2')

    const continuum = cloneSampleModel('continuum')
    const withSupport = addSupportAtNode(continuum, 'N2', dofsForModel(continuum))
    expect(supportDisplayLabel(withSupport, 'N1')).toBe('Support 1')
    expect(supportDisplayLabel(withSupport, 'N4')).toBe('Support 4')
    expect(supportDisplayLabel(withSupport, 'N2')).toBe('Support 5')
  })
})
