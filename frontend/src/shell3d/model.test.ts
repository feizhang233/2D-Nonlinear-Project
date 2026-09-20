import { describe, expect, it } from 'vitest'
import fixture from '../../../tests/fixtures/shell3d/cantilever.json'
import {
  defaultMesh,
  exampleShell,
  facetBasis,
  parseShell,
  shellMesh,
  targetNodes,
} from './model'
describe('spatial shell documents', () => {
  it('matches the actual independently solved frontend fixture', () =>
    expect(exampleShell()).toEqual(fixture))
  it('shares crease nodes and creates planar right-handed facets', () => {
    const m = exampleShell()
    expect(m.nodes).toHaveLength(25)
    expect(m.elements).toHaveLength(16)
    expect(targetNodes(m, 'x-')).toHaveLength(5)
    expect(targetNodes(m, 'boundary')).toHaveLength(16)
    for (const e of m.elements) {
      const [ex, ey, ez] = facetBasis(m, e.id)
      expect(Math.hypot(...ez)).toBeCloseTo(1, 12)
      expect(ex.reduce((s, v, i) => s + v * ey[i], 0)).toBeCloseTo(0, 12)
      const p = m.nodes.find((n) => n.id === e.nodes[0])!
      for (const id of e.nodes) {
        const n = m.nodes.find((n) => n.id === id)!
        expect(
          [n.x - p.x, n.y - p.y, n.z - p.z].reduce(
            (s, v, i) => s + v * ez[i],
            0,
          ),
        ).toBeCloseTo(0, 12)
      }
    }
    expect(facetBasis(m, 1)[2]).not.toEqual(facetBasis(m, 16)[2])
  })
  it('rejects geometry that would cross a crease or exceed resource limits', () => {
    expect(() => shellMesh({ ...defaultMesh, ny: 3 })).toThrow('even')
    expect(() => shellMesh({ ...defaultMesh, nx: 20, ny: 20 })).toThrow('100')
    expect(() => shellMesh({ ...defaultMesh, fold: 180 })).toThrow('170')
  })
  it('defensively parses portable models and rejects invalid references or conflicting constraints', () => {
    const m = exampleShell()
    expect(parseShell(m)).not.toBe(m)
    m.constraints.push({ ...m.constraints[0], value: 1 })
    expect(() => parseShell(m)).toThrow('Conflicting')
    m.constraints.pop()
    m.material.alpha_d = 0
    expect(() => parseShell(m)).toThrow('drilling')
    m.material.alpha_d = 1e-4
    m.elements[0].nodes[0] = 999
    expect(() => parseShell(m)).toThrow('four distinct')
  })
})
