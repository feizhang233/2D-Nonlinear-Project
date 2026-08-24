import { describe, expect, it } from 'vitest'
import type { SurfaceMeshResponse } from './domain'
import { getSketch } from './geometrySketch'
import { applySurfaceMesh, meshBoundaries, meshSizeForModel, meshStatusForModel, withMeshSize } from './meshing'
import { cloneSampleModel } from './sampleModel'

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

describe('Gmsh model bridge', () => {
  it('replaces Q4 topology and propagates matching endpoint supports along a boundary', () => {
    const model = cloneSampleModel('continuum')
    const remeshed = applySurfaceMesh(model, response)

    expect(remeshed.nodes).toHaveLength(9)
    expect(remeshed.elements).toHaveLength(4)
    expect(remeshed.constraints.some((item) => item.node_id === 'N4' && item.dof === 'UX')).toBe(true)
    expect(remeshed.constraints.some((item) => item.node_id === 'N4' && item.dof === 'UY')).toBe(false)
    expect(meshBoundaries(remeshed)).toHaveLength(4)
    expect(meshStatusForModel(remeshed)).toEqual({
      generatedByGmsh: true,
      sourceLabel: 'Gmsh 4.15.2',
      nodeCount: 9,
      elementCount: 4,
    })
    expect(getSketch(remeshed).vertices).toHaveLength(4)
    expect(remeshed.nodes.filter((node) => node.extensions?.geometry_vertex_id)).toHaveLength(4)
  })

  it('distinguishes the sample topology from a Gmsh-generated mesh', () => {
    expect(meshStatusForModel(cloneSampleModel('continuum'))).toEqual({
      generatedByGmsh: false,
      sourceLabel: 'Current topology',
      nodeCount: 4,
      elementCount: 1,
    })
  })

  it('preserves a temporarily invalid mesh-size edit instead of snapping back to the sample default', () => {
    const model = cloneSampleModel('continuum')
    expect(meshSizeForModel(withMeshSize(model, 0))).toBe(0)
    expect(meshSizeForModel(withMeshSize(model, 0.1))).toBe(0.1)
  })

  it('rebinds an edge load to every generated segment of its Gmsh boundary', () => {
    const model = cloneSampleModel('continuum')
    model.loads = [{
      id: 'Q', kind: 'edge', element_id: 'E1', components: { UX: 1000 },
      extensions: { boundary_id: 'B2', local_edge: 1 },
    }]
    const remeshed = applySurfaceMesh(model, response)
    const load = remeshed.loads[0]

    expect(load.element_id).toBe('E2')
    expect(load.extensions?.boundary_id).toBe('B2')
    expect(load.extensions?.edge_segments).toHaveLength(2)
  })
})
