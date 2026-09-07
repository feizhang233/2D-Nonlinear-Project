import { describe, expect, it } from 'vitest'
import { addFrameMember, addFrameNode } from './geometrySketch'
import { cloneSampleModel } from './sampleModel'
import {
  addSection,
  assignSection,
  deleteSection,
  sectionError,
  sectionIdForElement,
  sectionLibrary,
  sectionProperties,
  setDefaultSection,
  updateSection,
} from './sections'

it('computes rectangular, circular, I and tube sections about the centroidal horizontal axis', () => {
  const s = {
    id: 'S1',
    name: 'Test',
    shape: 'rectangle' as const,
    dimensions: { width: 2, height: 3 },
  }
  expect(sectionProperties(s)).toEqual({ area: 6, second_moment: 4.5 })
  expect(
    sectionProperties({ ...s, shape: 'circle', dimensions: { diameter: 2 } }),
  ).toEqual({ area: Math.PI, second_moment: Math.PI / 4 })
  expect(
    sectionProperties({
      ...s,
      shape: 'tube',
      dimensions: { outer_diameter: 4, wall_thickness: 1 },
    }),
  ).toEqual({ area: 3 * Math.PI, second_moment: 3.75 * Math.PI })
  expect(
    sectionProperties({
      ...s,
      shape: 'i_section',
      dimensions: {
        width: 4,
        height: 6,
        web_thickness: 1,
        flange_thickness: 1,
      },
    }),
  ).toEqual({ area: 12, second_moment: 56 })
  expect(() =>
    sectionProperties({
      ...s,
      shape: 'tube',
      dimensions: { outer_diameter: 2, wall_thickness: 1 },
    }),
  ).toThrow(/less than half/)
})

describe('section assignment lifecycle', () => {
  it('reads legacy properties without changing the model, updates only assigned elements, and applies defaults to new members', () => {
    const source = cloneSampleModel('frame')
    const original = structuredClone(source)
    expect(sectionLibrary(source).definitions).toHaveLength(1)
    expect(source).toEqual(original)
    const added = addSection(source)
    let model = updateSection(added.model, {
      id: added.id,
      name: 'Beam',
      shape: 'rectangle',
      dimensions: { width: 0.2, height: 0.3 },
    })
    model = assignSection(model, added.id, ['E1'])
    expect(model.elements[0].properties.area).toBeCloseTo(0.06)
    expect(model.elements[1].properties).toEqual(source.elements[1].properties)
    model = setDefaultSection(model, added.id)
    const extra = addFrameNode(model, [3, 0])
    model = addFrameMember(extra.model, 'N3', extra.nodeId)
    expect(sectionIdForElement(model, model.elements.at(-1)!)).toBe(added.id)
    expect(model.elements.at(-1)!.properties.area).toBeCloseTo(0.06)
    expect(() => deleteSection(model, added.id)).toThrow(/another section/)
    model = updateSection(model, {
      id: added.id,
      name: 'Beam',
      shape: 'rectangle',
      dimensions: { width: 0.4, height: 0.3 },
    })
    expect(model.elements[0].properties.area).toBeCloseTo(0.12)
    expect(model.elements.at(-1)!.properties.area).toBeCloseTo(0.12)
    expect(sectionLibrary(JSON.parse(JSON.stringify(model)))).toEqual(
      sectionLibrary(model),
    )
  })
  it('preserves invalid edits as a draft and prevents committing them', () => {
    const source = cloneSampleModel('frame')
    const section = sectionLibrary(source).definitions[0]
    const invalid = updateSection(source, {
      ...section,
      dimensions: { ...section.dimensions, area: 0 },
    })
    expect(sectionError(invalid)).toMatch(/greater than zero/)
    expect(invalid.elements[0].properties).toEqual(
      source.elements[0].properties,
    )
  })
  it.each(['continuum', 'plate', 'shell'] as const)(
    'assigns reusable thickness to %s elements',
    (family) => {
      const model = cloneSampleModel(family)
      const section = sectionLibrary(model).definitions[0]
      const next = updateSection(model, {
        ...section,
        dimensions: { thickness: 0.23 },
      })
      expect(
        next.elements.every((item) => item.properties.thickness === 0.23),
      ).toBe(true)
    },
  )
})
