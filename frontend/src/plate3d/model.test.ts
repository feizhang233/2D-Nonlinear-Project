import { describe, expect, it } from 'vitest'
import fixture from '../../../tests/fixtures/plate3d/cantilever.json'
import {
  cross,
  dot,
  edgeNodes,
  examplePlate,
  localNodes,
  parsePlate,
  rectangularPlate,
} from './model'
describe('spatial plate model', () => {
  it('pins the actual frontend example used in API tests', () =>
    expect(examplePlate()).toEqual(fixture))
  it('generates an oriented coplanar mesh with a right-handed frame', () => {
    const m = rectangularPlate(3, 2, 6, 4, 53, -19),
      n = cross(m.plane.ex, m.plane.ey)
    expect(m.nodes).toHaveLength(35)
    expect(m.elements).toHaveLength(24)
    for (const p of m.nodes) expect(dot([p.x, p.y, p.z], n)).toBeCloseTo(0, 12)
    const local = localNodes(m)
    expect(Math.max(...local.map((n) => n.x))).toBeCloseTo(3, 12)
    expect(edgeNodes(m, 'x-')).toHaveLength(5)
    expect(edgeNodes(m, 'y+')).toHaveLength(7)
  })
  it('rejects over-limit meshes and invalid saved models', () => {
    expect(() => rectangularPlate(1, 1, 20, 20)).toThrow('200 nodes')
    expect(() => rectangularPlate(1, 1, 2.5, 2)).toThrow('whole-number')
    const m = examplePlate()
    m.material.nu = 0.5
    expect(() => parsePlate(m)).toThrow('material')
    m.material.nu = 0.3
    m.elements[0].nodes[0] = 999
    expect(() => parsePlate(m)).toThrow('distinct existing')
  })
  it('rejects conflicting supports and clones committed data', () => {
    const m = examplePlate(),
      copy = parsePlate(m)
    copy.name = 'changed'
    expect(m.name).not.toBe(copy.name)
    m.constraints.push({ ...m.constraints[0], value: 1 })
    expect(() => parsePlate(m)).toThrow('Conflicting')
  })
})
