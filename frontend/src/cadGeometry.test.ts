import { describe, expect, it } from 'vitest'
import { cloneSampleModel } from './sampleModel'
import {
  defaultHoleDimensions,
  polygonError,
  replaceOutline,
  sketchError,
  upsertHole,
} from './cadGeometry'
import {
  geometryNeedsMesh,
  getSketch,
  moveSketchVertex,
  parseSketch,
  sketchJson,
} from './geometrySketch'

const outline = [
  [0, 0],
  [4, 0],
  [4, 2],
  [2, 2],
  [2, 4],
  [0, 4],
]
describe('CAD geometry', () => {
  it('replaces the domain transactionally and requires a mesh for a concave contour', () => {
    const original = cloneSampleModel('continuum')
    const next = replaceOutline(original, outline)
    expect(getSketch(next).vertices.map((v) => v.coordinates)).toEqual(outline)
    expect(geometryNeedsMesh(next)).toBe(true)
    expect(next.constraints).toEqual([])
    expect(next.loads).toEqual([])
    expect(original.loads.length).toBeGreaterThan(0)
    expect(original.nodes).toHaveLength(4)
  })
  it('normalizes a clockwise outline and rejects crossing or collapsed polygons', () => {
    const next = replaceOutline(cloneSampleModel('continuum'), [
      [0, 0],
      [0, 2],
      [2, 2],
      [2, 0],
    ])
    expect(geometryNeedsMesh(next)).toBe(false)
    expect(
      polygonError([
        [0, 0],
        [2, 2],
        [0, 2],
        [2, 0],
      ]),
    ).toMatch(/cross/)
    expect(
      polygonError([
        [0, 0],
        [0, 0],
        [2, 2],
      ]),
    ).toMatch(/overlap/)
  })
  it.each(['circle', 'rectangle', 'square'] as const)(
    'preserves %s dimensions in project geometry and updates without orphan vertices',
    (kind) => {
      const model = replaceOutline(cloneSampleModel('continuum'), outline)
      const created = upsertHole(model, {
        ...defaultHoleDimensions,
        kind,
        center: [1, 1],
      })
      const saved = parseSketch(sketchJson(getSketch(created.model)))!
      expect(saved.loops[1].shape?.kind).toBe(kind)
      const updated = upsertHole(
        created.model,
        { ...saved.loops[1].shape!, center: [1.1, 1.2] },
        created.id,
      )
      expect(getSketch(updated.model).vertices).toHaveLength(10)
      expect(getSketch(updated.model).loops).toHaveLength(2)
      expect(sketchError(getSketch(updated.model))).toBeNull()
      expect(geometryNeedsMesh(updated.model)).toBe(true)
    },
  )
  it('rejects holes outside, intersecting or touching a concave outline or another hole', () => {
    const model = replaceOutline(cloneSampleModel('continuum'), outline)
    expect(() =>
      upsertHole(model, { ...defaultHoleDimensions, center: [3, 3] }),
    ).toThrow(/inside/)
    expect(() =>
      upsertHole(model, { ...defaultHoleDimensions, center: [0.15, 1] }),
    ).toThrow(/inside/)
    const created = upsertHole(model, {
      ...defaultHoleDimensions,
      center: [1, 1],
    })
    expect(() =>
      upsertHole(created.model, { ...defaultHoleDimensions, center: [1.1, 1] }),
    ).toThrow(/overlap/)
    expect(() =>
      upsertHole(model, {
        ...defaultHoleDimensions,
        radius: NaN,
        center: [1, 1],
      }),
    ).toThrow(/finite/)
  })
  it('keeps shell hole vertices in the outer XY plane', () => {
    const model = cloneSampleModel('shell')
    model.nodes.forEach((n) => {
      n.coordinates[2] = 3
    })
    const created = upsertHole(replaceOutline(model, outline), {
      ...defaultHoleDimensions,
      center: [1, 1],
    })
    expect(
      getSketch(created.model).vertices.every((v) => v.coordinates[2] === 3),
    ).toBe(true)
  })
  it('detects an invalid vertex edit without silently changing a parameterized hole', () => {
    const model = replaceOutline(cloneSampleModel('continuum'), outline)
    const edited = moveSketchVertex(model, 'G2', [2, 3])
    expect(sketchError(getSketch(edited))).toBeTruthy()
  })
})

it('discards inactive invalid dimensions after switching hole shape', () => {
  const model = replaceOutline(cloneSampleModel('continuum'), outline)
  const created = upsertHole(model, {
    ...defaultHoleDimensions,
    kind: 'circle',
    width: NaN,
    height: NaN,
    center: [1, 1],
  })
  const shape = getSketch(created.model).loops[1].shape!
  expect(Number.isFinite(shape.width)).toBe(true)
  expect(Number.isFinite(shape.height)).toBe(true)
  expect(shape.radius).toBe(0.15)
})
