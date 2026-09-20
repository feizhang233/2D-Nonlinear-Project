import type { ApiSchemas, WithDefaults } from '../generated/api'
import { add, sub, mul, dot, norm, cross, type Vec3 } from './vector'
export { add, sub, mul, norm, type Vec3 } from './vector'
export type Plane = 'XY' | 'XZ' | 'YZ'
export type Tool = 'select' | 'node' | 'member' | 'material' | 'section' | 'support' | 'load' | 'tables'
export type Selection = { nodes: number[]; elements: number[] }
export type Node3D = ApiSchemas['reused_cores__frame3d_linear__api__NodeInput']
type WireMember = ApiSchemas['reused_cores__frame3d_linear__api__ElementInput']
export type Member = Omit<WithDefaults<WireMember>, 'Asy' | 'Asz'> & { Asy?: number; Asz?: number }
export const dofs = ['u', 'v', 'w', 'rx', 'ry', 'rz'] as const
export const forces = ['fx', 'fy', 'fz', 'mx', 'my', 'mz'] as const
export type Support = ApiSchemas['SupportInput']
export type NodalLoad = { node_id: number } & Record<typeof forces[number], number>
export const lineKeys = ['qx_i', 'qy_i', 'qz_i', 'mx_i', 'qx_j', 'qy_j', 'qz_j', 'mx_j'] as const
export type LineLoad = { element_id: number; coordinate_system: 'local' | 'global' } & Record<typeof lineKeys[number], number>
export type Model3D = {
  name: string; nodes: Node3D[]; elements: Member[]; supports: Support[]
  nodal_loads: NodalLoad[]; distributed_loads: LineLoad[]; section_points: { y: number; z: number }[]
  number_of_points: number; deformation_scale: number
}
export type Result3D = ApiSchemas['SolveResponse']
export const emptySelection = (): Selection => ({ nodes: [], elements: [] })
export const xyz = (n: Node3D): Vec3 => [n.x, n.y, n.z]
export const planePoint = (plane: Plane, a: number, b: number, offset: number): Vec3 => plane === 'XY' ? [a, b, offset] : plane === 'XZ' ? [a, offset, b] : [offset, a, b]
export const planeCoords = (plane: Plane, p: Vec3): Vec3 => plane === 'XY' ? p : plane === 'XZ' ? [p[0], p[2], p[1]] : [p[1], p[2], p[0]]
export const planeLabels = (plane: Plane) => plane === 'XY' ? ['X', 'Y', 'Z'] : plane === 'XZ' ? ['X', 'Z', 'Y'] : ['Y', 'Z', 'X']
export function autoReference(a: Vec3, b: Vec3): Vec3 {
  const d = sub(b, a); const L = norm(d)
  if (L < 1e-8) throw new Error('A member needs two different points.')
  return Math.abs(d[1] / L) < .9 ? [0, 1, 0] : [0, 0, 1]
}
export const defaultSection = (): Omit<Member, 'id' | 'node_i' | 'node_j'> => ({
  E: 210e9, G: 80.769230769e9, A: .01, Iy: 8.33e-5, Iz: 8.33e-5, J: 1.4e-4,
  reference_vector: [0, 1, 0], roll_angle: 0, theory: 'euler_bernoulli', releases: [], Asy: .0083, Asz: .0083,
})
export type MaterialProperties = Pick<Member, 'E' | 'G'>
export type SectionProperties = Pick<Member, 'A' | 'Iy' | 'Iz' | 'J' | 'Asy' | 'Asz'>
export function applyMaterial(source: Model3D, elementIds: number[], material: MaterialProperties): Model3D {
  if (![material.E, material.G].every(value => Number.isFinite(value) && value > 0)) throw new Error('E and G must be positive finite values.')
  if (!elementIds.length || elementIds.some(id => !source.elements.some(e => e.id === id))) throw new Error('Select an existing element to apply this material.')
  const model = structuredClone(source)
  model.elements = model.elements.map(e => elementIds.includes(e.id) ? { ...e, E: material.E, G: material.G } : e)
  return model
}
export function applySection(source: Model3D, elementIds: number[], section: SectionProperties): Model3D {
  if (![section.A, section.Iy, section.Iz, section.J].every(value => Number.isFinite(value) && value > 0) || [section.Asy, section.Asz].some(value => value !== undefined && (!Number.isFinite(value) || value <= 0))) throw new Error('Section properties must be positive finite values.')
  if (!elementIds.length || elementIds.some(id => !source.elements.some(e => e.id === id))) throw new Error('Select an existing element to apply this section.')
  if (source.elements.some(e => elementIds.includes(e.id) && e.theory === 'timoshenko') && (!section.Asy || !section.Asz)) throw new Error('Timoshenko elements require both shear areas.')
  const model = structuredClone(source)
  model.elements = model.elements.map(e => elementIds.includes(e.id) ? { ...e, A: section.A, Iy: section.Iy, Iz: section.Iz, J: section.J, Asy: section.Asy, Asz: section.Asz } : e)
  return model
}
export function blankModel(): Model3D {
  return { name: 'Untitled space frame', nodes: [], elements: [], supports: [], nodal_loads: [], distributed_loads: [], section_points: [], number_of_points: 51, deformation_scale: 1 }
}
export function example3D(): Model3D {
  const model = blankModel(); model.name = 'Space frame 01'
  model.nodes = [[0, 0, 0], [6, 0, 0], [6, 4, 0], [0, 4, 0], [0, 0, 3], [6, 0, 3], [6, 4, 3], [0, 4, 3]].map(([x, y, z], i) => ({ id: i + 1, x, y, z }))
  model.elements = [[1, 5], [2, 6], [3, 7], [4, 8], [5, 6], [6, 7], [7, 8], [8, 5]].map(([node_i, node_j], i) => ({ ...defaultSection(), id: i + 1, node_i, node_j, reference_vector: autoReference(xyz(model.nodes[node_i - 1]), xyz(model.nodes[node_j - 1])) }))
  model.supports = [1, 2, 3, 4].map(node_id => ({ node_id, u: true, v: true, w: true, rx: true, ry: true, rz: true }))
  model.nodal_loads = [5, 6, 7, 8].map(node_id => ({ node_id, fx: 4000, fy: 0, fz: -20000, mx: 0, my: 0, mz: 0 }))
  return model
}
const tol = 1e-8
const pointAt = (a: Vec3, b: Vec3, t: number) => add(a, mul(sub(b, a), t))
function parameter(p: Vec3, a: Vec3, b: Vec3): number | null {
  const d = sub(b, a); const t = dot(sub(p, a), d) / dot(d, d)
  return t >= -tol && t <= 1 + tol && norm(sub(p, pointAt(a, b, t))) < tol * Math.max(1, norm(d)) ? Math.max(0, Math.min(1, t)) : null
}
function ensureNode(model: Model3D, p: Vec3): number {
  if (!p.every(Number.isFinite)) throw new Error('Coordinates must be finite numbers.')
  const existing = model.nodes.find(n => norm(sub(xyz(n), p)) < tol)
  if (existing) return existing.id
  const id = model.nodes.length + 1
  model.nodes.push({ id, x: p[0], y: p[1], z: p[2] }); return id
}
function splitMembers(model: Model3D) {
  const originals = [...model.elements]
  let nextId = Math.max(0, ...originals.map(e => e.id)) + 1
  for (const e of originals) {
    const a = xyz(model.nodes[e.node_i - 1]); const b = xyz(model.nodes[e.node_j - 1])
    const cuts = model.nodes.map(n => ({ id: n.id, t: parameter(xyz(n), a, b) })).filter((c): c is { id: number; t: number } => c.t !== null).sort((a, b) => a.t - b.t)
    if (cuts.length <= 2) continue
    const loads = model.distributed_loads.filter(l => l.element_id === e.id)
    model.elements = model.elements.filter(m => m.id !== e.id)
    model.distributed_loads = model.distributed_loads.filter(l => l.element_id !== e.id)
    for (let i = 0; i < cuts.length - 1; i++) {
      const id = i === 0 ? e.id : nextId++
      model.elements.push({ ...structuredClone(e), id, node_i: cuts[i].id, node_j: cuts[i + 1].id,
        releases: e.releases.filter(r => (r < 6 && i === 0) || (r >= 6 && i === cuts.length - 2)) })
      for (const load of loads) {
        const part = { ...load, element_id: id }
        for (const component of ['qx', 'qy', 'qz', 'mx'] as const) {
          const first = load[`${component}_i`]; const delta = load[`${component}_j`] - first
          part[`${component}_i`] = first + delta * cuts[i].t
          part[`${component}_j`] = first + delta * cuts[i + 1].t
        }
        model.distributed_loads.push(part)
      }
    }
  }
  model.elements.sort((a, b) => a.id - b.id)
}
export function insertNode(source: Model3D, p: Vec3): { model: Model3D; id: number } {
  const model = structuredClone(source); const id = ensureNode(model, p); splitMembers(model); return { model, id }
}
export function insertMember(source: Model3D, a: Vec3, b: Vec3, section = defaultSection()): { model: Model3D; id: number } {
  if (norm(sub(b, a)) < tol) throw new Error('A member needs two different points.')
  const model = structuredClone(source); ensureNode(model, a); const id = ensureNode(model, b)
  // Closest points of two lines: only coincident points within both segments connect.
  const d = sub(b, a)
  for (const e of source.elements) {
    const c = xyz(source.nodes[e.node_i - 1]); const v = sub(xyz(source.nodes[e.node_j - 1]), c); const w = sub(a, c)
    const dd = dot(d, d); const vv = dot(v, v); const dv = dot(d, v); const det = dd * vv - dv * dv
    if (det < 1e-12 * dd * vv) continue
    const t = (dv * dot(v, w) - vv * dot(d, w)) / det
    const s = (dd * dot(v, w) - dv * dot(d, w)) / det
    if (t >= -tol && t <= 1 + tol && s >= -tol && s <= 1 + tol && norm(sub(pointAt(a, b, t), add(c, mul(v, s)))) < tol) ensureNode(model, pointAt(a, b, t))
  }
  splitMembers(model)
  const cuts = model.nodes.map(n => ({ id: n.id, t: parameter(xyz(n), a, b) })).filter((c): c is { id: number; t: number } => c.t !== null).sort((a, b) => a.t - b.t)
  let nextId = Math.max(0, ...model.elements.map(e => e.id)) + 1; let added = 0
  for (let i = 0; i < cuts.length - 1; i++) {
    const ni = cuts[i].id; const nj = cuts[i + 1].id
    if (model.elements.some(e => (e.node_i === ni && e.node_j === nj) || (e.node_i === nj && e.node_j === ni))) continue
    const reference = norm(cross(d, section.reference_vector)) / norm(d) < tol ? autoReference(a, b) : section.reference_vector
    model.elements.push({ ...structuredClone(section), reference_vector: [...reference], id: nextId++, node_i: ni, node_j: nj,
      releases: section.releases.filter(r => (r < 6 && i === 0) || (r >= 6 && i === cuts.length - 2)) }); added++
  }
  if (!added) throw new Error('This member already exists.')
  return { model, id }
}
export function deleteSelected(source: Model3D, selection: Selection): Model3D {
  const model = structuredClone(source)
  model.elements = model.elements.filter(e => !selection.elements.includes(e.id) && !selection.nodes.includes(e.node_i) && !selection.nodes.includes(e.node_j))
  const nodeMap = new Map<number, number>()
  model.nodes = model.nodes.filter(n => !selection.nodes.includes(n.id)).map((n, i) => { nodeMap.set(n.id, i + 1); return { ...n, id: i + 1 } })
  model.elements.forEach(e => { e.node_i = nodeMap.get(e.node_i)!; e.node_j = nodeMap.get(e.node_j)! })
  model.supports = model.supports.filter(s => nodeMap.has(s.node_id)).map(s => ({ ...s, node_id: nodeMap.get(s.node_id)! }))
  model.nodal_loads = model.nodal_loads.filter(l => nodeMap.has(l.node_id)).map(l => ({ ...l, node_id: nodeMap.get(l.node_id)! }))
  model.distributed_loads = model.distributed_loads.filter(l => model.elements.some(e => e.id === l.element_id))
  return model
}
export function modelIssues(model: Model3D): string[] {
  const errors: string[] = []
  if (!model.elements.length) errors.push('Draw at least one member before analysis.')
  for (const n of model.nodes) {
    if (!model.elements.some(e => e.node_i === n.id || e.node_j === n.id)) errors.push(`Node ${n.id} is not connected to a member.`)
  }
  for (const e of model.elements) {
    const a = model.nodes.find(n => n.id === e.node_i); const b = model.nodes.find(n => n.id === e.node_j)
    if (!a || !b) { errors.push(`Member ${e.id} references a missing node.`); continue }
    const d = sub(xyz(b), xyz(a))
    if (norm(d) < tol) errors.push(`Member ${e.id} has zero length.`)
    if (norm(cross(d, e.reference_vector)) < tol * norm(d) * Math.max(1, norm(e.reference_vector))) errors.push(`Member ${e.id}: reference vector is parallel to its axis. Edit its section orientation.`)
    if (e.theory === 'timoshenko' && model.distributed_loads.some(l => l.element_id === e.id)) errors.push(`Member ${e.id}: Timoshenko supports nodal loads only. Remove its line load or use Euler–Bernoulli.`)
  }
  if (!model.supports.some(s => dofs.some(d => s[d]))) errors.push('Assign supports before analysis.')
  return errors
}
export function parseModel3D(raw: unknown): Model3D {
  if (!raw || typeof raw !== 'object') throw new Error('Expected a 3D model object.')
  const r = raw as Record<string, unknown>; const model = blankModel()
  const finite = (value: unknown, label: string, fallback?: number): number => {
    if (value === undefined && fallback !== undefined) return fallback
    if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label} must be a finite number.`)
    return value
  }
  const positive = (value: unknown, label: string): number => { const v = finite(value, label); if (v <= 0) throw new Error(`${label} must be positive.`); return v }
  const array = (key: string, required = false): Record<string, unknown>[] => {
    const a = r[key] ?? (required ? null : []); if (!Array.isArray(a) || a.some(x => !x || typeof x !== 'object')) throw new Error(`${key} must be an array of objects.`); return a
  }
  model.name = typeof r.name === 'string' && r.name.trim() ? r.name : 'Imported space frame'
  model.nodes = array('nodes', true).map(n => ({ id: finite(n.id, 'Node ID'), x: finite(n.x, 'X'), y: finite(n.y, 'Y'), z: finite(n.z, 'Z (3D models only)') })).sort((a, b) => a.id - b.id)
  if (model.nodes.some((n, i) => n.id !== i + 1)) throw new Error('3D node IDs must be consecutive integers starting at 1.')
  model.elements = array('elements', true).map(e => {
    const m = { ...defaultSection(), id: finite(e.id, 'Member ID'), node_i: finite(e.node_i, 'Start node'), node_j: finite(e.node_j, 'End node') }
    for (const k of ['E', 'G', 'A', 'Iy', 'Iz', 'J'] as const) m[k] = positive(e[k], k)
    if (e.theory !== undefined && e.theory !== 'euler_bernoulli' && e.theory !== 'timoshenko') throw new Error('Unknown beam theory.')
    m.theory = e.theory as Member['theory'] ?? 'euler_bernoulli'
    if (!Array.isArray(e.reference_vector) || e.reference_vector.length !== 3) throw new Error('Each member needs a reference_vector with three components.')
    m.reference_vector = e.reference_vector.map(v => finite(v, 'Reference vector')) as Vec3
    m.roll_angle = finite(e.roll_angle, 'Roll angle', 0)
    if (m.theory === 'timoshenko' || e.Asy != null) m.Asy = positive(e.Asy, 'Asy')
    if (m.theory === 'timoshenko' || e.Asz != null) m.Asz = positive(e.Asz, 'Asz')
    if (e.releases !== undefined && (!Array.isArray(e.releases) || e.releases.some(v => ![3, 4, 5, 9, 10, 11].includes(v)))) throw new Error('Only local rotational releases 3, 4, 5, 9, 10, 11 are supported.')
    m.releases = [...new Set((e.releases ?? []) as number[])]
    if (!Number.isInteger(m.id) || m.id < 1 || !model.nodes.some(n => n.id === m.node_i) || !model.nodes.some(n => n.id === m.node_j) || m.node_i === m.node_j) throw new Error(`Member ${m.id} has invalid IDs.`)
    return m
  })
  if (new Set(model.elements.map(e => e.id)).size !== model.elements.length) throw new Error('Member IDs must be unique.')
  const nodeId = (v: unknown) => { const id = finite(v, 'Node ID'); if (!model.nodes.some(n => n.id === id)) throw new Error(`Node ${id} does not exist.`); return id }
  model.supports = array('supports').map(s => {
    const support: Support = { node_id: nodeId(s.node_id) }
    for (const d of dofs) {
      if (s[d] !== undefined && typeof s[d] !== 'boolean') throw new Error(`Support ${d} must be true or false.`)
      support[d] = s[d] === true; support[`${d}_value`] = finite(s[`${d}_value`], `${d} prescribed displacement`, 0)
      if (!support[d] && support[`${d}_value`] !== 0) throw new Error(`Only restrained ${d} can have a prescribed value.`)
    }
    if (s.axes !== undefined && s.axes !== null) {
      if (!Array.isArray(s.axes) || s.axes.length !== 3 || s.axes.some(row => !Array.isArray(row) || row.length !== 3)) throw new Error('Support axes must be a 3 × 3 matrix.')
      support.axes = s.axes.map(row => (row as unknown[]).map(v => finite(v, 'Support axis'))) as [Vec3, Vec3, Vec3]
      const [a, b, c] = support.axes as Vec3[]
      if ([a, b, c].some(v => Math.abs(norm(v) - 1) > 1e-8) || Math.abs(dot(a, b)) > 1e-8 || norm(sub(cross(a, b), c)) > 1e-8) throw new Error('Support axes must be orthonormal and right-handed.')
    }
    if (!dofs.some(d => support[d])) throw new Error('A support must restrain at least one direction.')
    return support
  })
  if (new Set(model.supports.map(s => s.node_id)).size !== model.supports.length) throw new Error('Only one support per node is allowed.')
  model.nodal_loads = array('nodal_loads').map(l => Object.fromEntries([['node_id', nodeId(l.node_id)], ...forces.map(f => [f, finite(l[f], f, 0)])]) as NodalLoad)
  model.distributed_loads = array('distributed_loads').map(l => {
    const id = finite(l.element_id, 'Line load member ID'); if (!model.elements.some(e => e.id === id)) throw new Error(`Member ${id} does not exist.`)
    if (l.coordinate_system !== undefined && l.coordinate_system !== 'local' && l.coordinate_system !== 'global') throw new Error('Load axes must be local or global.')
    return Object.fromEntries([['element_id', id], ['coordinate_system', l.coordinate_system ?? 'local'], ...lineKeys.map(k => [k, finite(l[k], k, 0)])]) as LineLoad
  })
  model.section_points = array('section_points').map(p => ({ y: finite(p.y, 'Section y'), z: finite(p.z, 'Section z') }))
  model.number_of_points = finite(r.number_of_points, 'Result stations', 51)
  if (!Number.isInteger(model.number_of_points) || model.number_of_points < 2 || model.number_of_points > 2001) throw new Error('Result stations must be an integer from 2 to 2001.')
  model.deformation_scale = finite(r.deformation_scale, 'Deformation scale', 1)
  return model
}

/** Model names belong to the workspace; the strict solver schema accepts numerical data only. */
export function toSpatialPayload(model: Model3D): ApiSchemas['SolveRequest'] {
  return {
    nodes: model.nodes, elements: model.elements, supports: model.supports,
    nodal_loads: model.nodal_loads, distributed_loads: model.distributed_loads,
    section_points: model.section_points, number_of_points: model.number_of_points,
    deformation_scale: 1, include_plots: false,
  }
}
