import type { ApiSchemas } from '../generated/api'
import type { Vec3 as Vec } from '../spatial/vector'
export type { Vec }
export type Kind = ApiSchemas['SolidElement']['kind']
export type SolidModel = ApiSchemas['SolidModel-Output']
export type SolidResult = ApiSchemas['SolidResult']

const faces: Record<Kind, number[][]> = {
  tet4: [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
  hex8: [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
}
export type BoundaryFace = { element: number; face: number; nodes: number[] }
export function boundaryFaces(model: SolidModel): BoundaryFace[] {
  const map = new Map<string, BoundaryFace[]>()
  for (const e of model.elements) faces[e.kind].forEach((f, face) => {
    const nodes = f.map(i => e.nodes[i]); const key = [...nodes].sort((a, b) => a - b).join(',')
    map.set(key, [...(map.get(key) ?? []), { element: e.id, face, nodes }])
  })
  return [...map.values()].filter(v => v.length === 1).map(v => v[0])
}
export function faceNodes(model: SolidModel, side: string): number[] {
  const axis = side[0] as 'x' | 'y' | 'z'; const values = model.nodes.map(n => n[axis])
  const min = Math.min(...values); const max = Math.max(...values); const at = side[1] === '+' ? max : min
  const tolerance = Math.max(max - min, 1e-20) * 1e-8
  return model.nodes.filter(n => Math.abs(n[axis] - at) <= tolerance).map(n => n.id)
}
export function blockModel(lengths: Vec = [2, 1, 1], divisions: Vec = [4, 2, 2], kind: Kind = 'hex8'): SolidModel {
  if (lengths.some(v => !Number.isFinite(v) || v <= 0) || divisions.some(v => !Number.isInteger(v) || v < 1)) throw new Error('Enter positive dimensions and whole-number divisions.')
  const [nx, ny, nz] = divisions
  if ((nx + 1) * (ny + 1) * (nz + 1) > 200 || nx * ny * nz * (kind === 'tet4' ? 6 : 1) > 1200) throw new Error('Use at most 200 nodes and 1,200 elements. Reduce mesh divisions.')
  const nodes: SolidModel['nodes'] = []; const elements: SolidModel['elements'] = []
  const id = (i: number, j: number, k: number) => (i * (ny + 1) + j) * (nz + 1) + k + 1
  for (let i = 0; i <= nx; i++) for (let j = 0; j <= ny; j++) for (let k = 0; k <= nz; k++) nodes.push({ id: id(i, j, k), x: lengths[0] * i / nx, y: lengths[1] * j / ny, z: lengths[2] * k / nz })
  for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) for (let k = 0; k < nz; k++) {
    const hex = [id(i, j, k), id(i+1, j, k), id(i+1, j+1, k), id(i, j+1, k), id(i, j, k+1), id(i+1, j, k+1), id(i+1, j+1, k+1), id(i, j+1, k+1)]
    const cells = kind === 'hex8' ? [hex] : [[0,1,2,6],[0,2,3,6],[0,3,7,6],[0,7,4,6],[0,4,5,6],[0,5,1,6]].map(c => c.map(v => hex[v]))
    for (const cell of cells) elements.push({ id: elements.length + 1, kind, nodes: cell, material_id: 1 })
  }
  return { schema_version: 'continuum3d-1', name: 'Solid block', nodes, elements, materials: [{ id: 1, E: 200e9, nu: 0.3 }], constraints: [], nodal_loads: [], tractions: [], body_force: [0, 0, 0] }
}
export function exampleSolid(kind: Kind = 'hex8'): SolidModel {
  const m = blockModel([2, 1, 1], [4, 2, 2], kind)
  m.name = 'Uniaxial solid specimen'
  for (const [axis, dof] of [['x', 'ux'], ['y', 'uy'], ['z', 'uz']] as const) for (const node of faceNodes(m, `${axis}-`)) m.constraints.push({ node_id: node, dof, value: 0 })
  const loaded = new Set(faceNodes(m, 'x+'))
  m.tractions = boundaryFaces(m).filter(f => f.nodes.every(n => loaded.has(n))).map(f => ({ element_id: f.element, face: f.face, traction: [1e6, 0, 0] }))
  return m
}
/** Cheap defensive shape check; imported documents also pass the host schema before use. */
export function parseSolid(value: unknown): SolidModel {
  const m = value as SolidModel
  if (!m || m.schema_version !== 'continuum3d-1' || typeof m.name !== 'string' || !m.name.trim() || m.name.length > 120 || !Array.isArray(m.nodes) || m.nodes.length < 4 || m.nodes.length > 200 || !Array.isArray(m.elements) || !m.elements.length || m.elements.length > 1200 || !Array.isArray(m.materials) || !m.materials.length || !Array.isArray(m.constraints) || !Array.isArray(m.nodal_loads) || !Array.isArray(m.tractions)) throw new Error('Open a continuum3d-1 solid project with nodes, elements and materials.')
  const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
  const vector = (v: unknown): v is Vec => Array.isArray(v) && v.length === 3 && v.every(finite)
  const validId = (v: number) => Number.isInteger(v) && v > 0
  for (const rows of [m.nodes, m.elements, m.materials]) if (new Set(rows.map(r => r.id)).size !== rows.length || rows.some(r => !validId(r.id))) throw new Error('Each entity needs a unique positive integer ID.')
  const ids = new Set(m.nodes.map(n => n.id)); const mats = new Set(m.materials.map(v => v.id))
  if (m.nodes.some(n => ![n.x, n.y, n.z].every(finite)) || m.materials.some(v => !finite(v.E) || v.E <= 0 || !finite(v.nu) || v.nu <= -1 || v.nu >= 0.5) || !vector(m.body_force)) throw new Error('Check finite coordinates, body force and isotropic material values.')
  if (m.elements.some(e => !faces[e.kind] || !Array.isArray(e.nodes) || e.nodes.length !== (e.kind === 'tet4' ? 4 : 8) || new Set(e.nodes).size !== e.nodes.length || e.nodes.some(n => !ids.has(n)) || !mats.has(e.material_id))) throw new Error('Check element type, connectivity and material references.')
  if (m.constraints.some(c => !ids.has(c.node_id) || !['ux','uy','uz'].includes(c.dof) || !finite(c.value)) || m.nodal_loads.some(l => !ids.has(l.node_id) || !vector(l.force))) throw new Error('Check supports and nodal loads.')
  const es = new Map(m.elements.map(e => [e.id, e]))
  if (m.tractions.some(t => !es.has(t.element_id) || !Number.isInteger(t.face) || t.face < 0 || t.face >= faces[es.get(t.element_id)!.kind].length || !vector(t.traction))) throw new Error('Check face traction references and values.')
  return structuredClone(m)
}
