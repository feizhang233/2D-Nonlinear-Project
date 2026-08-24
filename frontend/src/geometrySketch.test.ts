import { describe, expect, it } from 'vitest'
import {
  addOuterVertexAt,
  addRectangularHole,
  editablePlacementNodes,
  geometryNeedsMesh,
  getSketch,
  isGeneratedMesh,
  moveSketchVertex,
} from './geometrySketch'
import { applySurfaceMesh } from './meshing'
import { cloneSampleModel } from './sampleModel'
import type { SurfaceMeshResponse } from './domain'

describe('geometry sketch CAD', () => {
  it('derives a four-vertex contour from the continuum sample', () => {
    const sketch = getSketch(cloneSampleModel('continuum'))
    expect(sketch.vertices).toHaveLength(4)
    expect(sketch.loops).toEqual([
      expect.objectContaining({ kind: 'outer', vertexIds: expect.any(Array) }),
    ])
    expect(sketch.loops[0].vertexIds).toHaveLength(4)
  })

  it('inserts outer vertices and rectangular holes without using mesh nodes', () => {
    const model = cloneSampleModel('continuum')
    const withVertex = addOuterVertexAt(model, [1, -0.2])
    const sketch = getSketch(withVertex)
    expect(sketch.vertices.length).toBe(5)
    expect(geometryNeedsMesh(withVertex)).toBe(true)

    const withHole = addRectangularHole(withVertex, [1, 0.5], 0.3)
    const holed = getSketch(withHole)
    expect(holed.loops.some((loop) => loop.kind === 'hole')).toBe(true)
    expect(holed.vertices.length).toBe(9)
  })

  it('keeps geometry vertices after a Gmsh mesh replaces the FE nodes', () => {
    const model = addRectangularHole(cloneSampleModel('continuum'), [1, 0.5], 0.3)
    const response: SurfaceMeshResponse = {
      engine: 'Gmsh',
      engine_version: '4.15.2',
      model_family: 'continuum',
      formulation: 'Q4-total-lagrangian',
      mesh_size: 0.5,
      nodes: [
        { id: 'N1', coordinates: [0, 0] }, { id: 'N2', coordinates: [1, 0] }, { id: 'N3', coordinates: [2, 0] },
        { id: 'N4', coordinates: [0, 0.5] }, { id: 'N5', coordinates: [1, 0.5] }, { id: 'N6', coordinates: [2, 0.5] },
        { id: 'N7', coordinates: [0, 1] }, { id: 'N8', coordinates: [1, 1] }, { id: 'N9', coordinates: [2, 1] },
      ],
      elements: [
        { id: 'E1', formulation: 'Q4-total-lagrangian', node_ids: ['N1', 'N2', 'N5', 'N4'], material_id: 'M1', properties: { thickness: 0.1 } },
        { id: 'E2', formulation: 'Q4-total-lagrangian', node_ids: ['N2', 'N3', 'N6', 'N5'], material_id: 'M1', properties: { thickness: 0.1 } },
        { id: 'E3', formulation: 'Q4-total-lagrangian', node_ids: ['N4', 'N5', 'N8', 'N7'], material_id: 'M1', properties: { thickness: 0.1 } },
        { id: 'E4', formulation: 'Q4-total-lagrangian', node_ids: ['N5', 'N6', 'N9', 'N8'], material_id: 'M1', properties: { thickness: 0.1 } },
      ],
      boundaries: [
        { id: 'B1', label: 'Boundary 1', node_ids: ['N1', 'N2', 'N3'], length: 2, segments: [
          { element_id: 'E1', local_edge: 0, node_ids: ['N1', 'N2'] },
          { element_id: 'E2', local_edge: 0, node_ids: ['N2', 'N3'] },
        ] },
        { id: 'B2', label: 'Boundary 2', node_ids: ['N3', 'N6', 'N9'], length: 1, segments: [
          { element_id: 'E2', local_edge: 1, node_ids: ['N3', 'N6'] },
          { element_id: 'E4', local_edge: 1, node_ids: ['N6', 'N9'] },
        ] },
        { id: 'B3', label: 'Boundary 3', node_ids: ['N9', 'N8', 'N7'], length: 2, segments: [
          { element_id: 'E4', local_edge: 2, node_ids: ['N9', 'N8'] },
          { element_id: 'E3', local_edge: 2, node_ids: ['N8', 'N7'] },
        ] },
        { id: 'B4', label: 'Boundary 4', node_ids: ['N7', 'N4', 'N1'], length: 1, segments: [
          { element_id: 'E3', local_edge: 3, node_ids: ['N7', 'N4'] },
          { element_id: 'E1', local_edge: 3, node_ids: ['N4', 'N1'] },
        ] },
      ],
    }
    const meshed = applySurfaceMesh(model, response)
    expect(isGeneratedMesh(meshed)).toBe(true)
    expect(getSketch(meshed).vertices.length).toBe(getSketch(model).vertices.length)
    expect(editablePlacementNodes(meshed).map((node) => node.label)).toEqual(
      getSketch(meshed).vertices.map((_, index) => `V${index + 1}`),
    )
    expect(meshed.nodes.some((node) => node.extensions?.geometry_vertex_id)).toBe(true)
    expect(geometryNeedsMesh(moveSketchVertex(meshed, getSketch(meshed).vertices[0].id, [-0.1, 0]))).toBe(true)
  })
})
